package com.localagentbridge.android

import android.Manifest
import android.app.LocaleManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.res.Configuration
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.LocaleList
import android.provider.Settings
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
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.hapticfeedback.HapticFeedback
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.disabled
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.onClick
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import com.localagentbridge.android.runtime.RuntimeClientViewModel
import com.localagentbridge.android.runtime.RuntimeChatSession
import com.localagentbridge.android.runtime.RuntimeModel
import com.localagentbridge.android.runtime.RuntimeAppLanguage
import com.localagentbridge.android.runtime.RuntimeAppTheme
import com.localagentbridge.android.runtime.RuntimeUiState
import com.localagentbridge.android.runtime.isChatModel
import com.localagentbridge.android.runtime.isRuntimeHostLocalModel
import com.localagentbridge.android.runtime.supportsImageInput
import com.localagentbridge.android.core.pairing.RuntimePairingPayloadParser
import com.localagentbridge.android.ui.AetherLinkInteractionFeedback
import com.localagentbridge.android.ui.ChatScreen
import com.localagentbridge.android.ui.SettingsScreen
import com.localagentbridge.android.ui.aetherLinkHapticFeedbackType
import com.localagentbridge.android.ui.chatHistorySessionModelDisplayName
import com.localagentbridge.android.ui.chatHistorySessionStatusRes
import com.localagentbridge.android.ui.filterChatHistorySessions
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
    private val sharedChatDraftState = mutableStateOf<SharedChatDraft?>(null)
    private val developerDiagnosticsState = mutableStateOf(false)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        pairingUriState.value = intent.pairingUriOrNull()
        sharedChatDraftState.value = intent.sharedChatDraftOrNull()
        developerDiagnosticsState.value = shouldEnableDeveloperDiagnostics(
            isDebugBuild = BuildConfig.DEBUG,
            requestedByLaunch = intent.developerDiagnosticsRequested(),
        )
        setContent {
            LocalAgentBridgeApp(
                pairingUri = pairingUriState.value,
                sharedChatDraft = sharedChatDraftState.value,
                showDeveloperDiagnostics = developerDiagnosticsState.value,
                onPairingUriConsumed = { pairingUriState.value = null },
                onSharedChatDraftConsumed = { sharedChatDraftState.value = null },
            )
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        pairingUriState.value = intent.pairingUriOrNull()
        sharedChatDraftState.value = intent.sharedChatDraftOrNull()
        developerDiagnosticsState.value = shouldEnableDeveloperDiagnostics(
            isDebugBuild = BuildConfig.DEBUG,
            requestedByLaunch = intent.developerDiagnosticsRequested(),
        )
    }
}

internal const val DEVELOPER_DIAGNOSTICS_EXTRA = "aetherlink.dev_diagnostics"

internal data class SharedChatDraft(
    val text: String = "",
    val attachmentUris: List<Uri> = emptyList(),
)

internal fun Intent?.sharedChatDraftOrNull(): SharedChatDraft? {
    val intent = this ?: return null
    val streams = buildList {
        intent.streamExtraUriOrNull()?.let(::add)
        addAll(intent.streamExtraUris())
        val clipData = intent.clipData
        if (clipData != null) {
            repeat(clipData.itemCount) { index ->
                clipData.getItemAt(index).uri?.let(::add)
            }
        }
    }
    return sharedChatDraftOrNull(
        action = intent.action,
        sharedText = intent.getStringExtra(Intent.EXTRA_TEXT),
        attachmentUris = streams,
    )
}

internal fun sharedChatDraftOrNull(
    action: String?,
    sharedText: String?,
    attachmentUris: List<Uri>,
): SharedChatDraft? {
    if (action != Intent.ACTION_SEND && action != Intent.ACTION_SEND_MULTIPLE) {
        return null
    }
    return SharedChatDraft(
        text = sharedText.orEmpty().trim(),
        attachmentUris = attachmentUris.distinct(),
    )
        .takeIf { it.text.isNotBlank() || it.attachmentUris.isNotEmpty() }
}

internal fun sharedChatDraftComposerText(currentText: String, sharedText: String): String {
    val trimmedSharedText = sharedText.trim()
    if (trimmedSharedText.isBlank()) return currentText

    val trimmedCurrentText = currentText.trimEnd()
    return if (trimmedCurrentText.isBlank()) {
        trimmedSharedText
    } else {
        "$trimmedCurrentText\n\n$trimmedSharedText"
    }
}

@Suppress("DEPRECATION")
private fun Intent.streamExtraUriOrNull(): Uri? {
    return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
        getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
    } else {
        getParcelableExtra(Intent.EXTRA_STREAM) as? Uri
    }
}

@Suppress("DEPRECATION")
private fun Intent.streamExtraUris(): List<Uri> {
    return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
        getParcelableArrayListExtra(Intent.EXTRA_STREAM, Uri::class.java).orEmpty()
    } else {
        getParcelableArrayListExtra<Uri>(Intent.EXTRA_STREAM).orEmpty()
    }
}

internal fun shouldEnableDeveloperDiagnostics(
    isDebugBuild: Boolean,
    requestedByLaunch: Boolean,
): Boolean {
    return isDebugBuild && requestedByLaunch
}

private fun Intent.developerDiagnosticsRequested(): Boolean {
    return getBooleanExtra(DEVELOPER_DIAGNOSTICS_EXTRA, false)
}

internal fun androidSystemAppLanguageTag(context: Context): String? {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return null
    val localeManager = context.getSystemService(LocaleManager::class.java) ?: return null
    val locales = localeManager.applicationLocales
    if (locales.size() == 0) return null
    return locales.get(0).toLanguageTag()
}

internal fun shouldSynchronizeAndroidSystemAppLanguage(
    currentLanguageTag: String?,
    selectedLanguageTag: String,
): Boolean {
    val selected = RuntimeAppLanguage.normalizeLanguageTag(selectedLanguageTag)
    val current = RuntimeAppLanguage.supportedLanguageTagOrNull(currentLanguageTag)
    return current != selected
}

internal fun synchronizeAndroidSystemAppLanguageTag(
    context: Context,
    selectedLanguageTag: String,
) {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
    val localeManager = context.getSystemService(LocaleManager::class.java) ?: return
    val normalizedLanguageTag = RuntimeAppLanguage.normalizeLanguageTag(selectedLanguageTag)
    if (
        !shouldSynchronizeAndroidSystemAppLanguage(
            currentLanguageTag = androidSystemAppLanguageTag(context),
            selectedLanguageTag = normalizedLanguageTag,
        )
    ) {
        return
    }
    localeManager.applicationLocales = LocaleList.forLanguageTags(normalizedLanguageTag)
}

@Composable
@OptIn(ExperimentalMaterial3Api::class)
private fun LocalAgentBridgeApp(
    pairingUri: String? = null,
    sharedChatDraft: SharedChatDraft? = null,
    showDeveloperDiagnostics: Boolean = false,
    onPairingUriConsumed: () -> Unit = {},
    onSharedChatDraftConsumed: () -> Unit = {},
) {
    val viewModel: RuntimeClientViewModel = viewModel()
    val state by viewModel.state.collectAsStateWithLifecycle()
    val baseContext = LocalContext.current
    var systemLanguageReconciled by remember { mutableStateOf(false) }
    LaunchedEffect(viewModel, baseContext) {
        viewModel.reconcileSystemAppLanguageTag(androidSystemAppLanguageTag(baseContext))
        systemLanguageReconciled = true
    }
    LaunchedEffect(baseContext, state.selectedLanguageTag, systemLanguageReconciled) {
        if (systemLanguageReconciled) {
            synchronizeAndroidSystemAppLanguageTag(baseContext, state.selectedLanguageTag)
        }
    }
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
                filterChatHistorySessions(
                    sessions = state.chatSessions,
                    query = trimmedChatSearchQuery,
                    untitledTitle = untitledChatTitle,
                    models = state.models,
                )
            } else {
                state.chatSessions
            }
            val hasChatSearchResults = filteredChatSessions.isNotEmpty()
            val attachmentPickerLauncher = rememberLauncherForActivityResult(
                contract = ActivityResultContracts.OpenMultipleDocuments(),
            ) { uris ->
                handlePickedAttachments(uris, viewModel::addAttachments)
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

            LaunchedEffect(sharedChatDraft) {
                val draft = sharedChatDraft ?: return@LaunchedEffect
                val updatedText = sharedChatDraftComposerText(
                    currentText = state.chatInput,
                    sharedText = draft.text,
                )
                if (updatedText != state.chatInput) {
                    viewModel.updateChatInput(updatedText)
                }
                handlePickedAttachments(draft.attachmentUris, viewModel::addAttachments)
                destination = AppDestination.Chat
                onSharedChatDraftConsumed()
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
                    AetherLinkNavigationDrawerContent(
                        state = state,
                        effectiveDestination = effectiveDestination,
                        chatSearchQuery = chatSearchQuery,
                        hasAnyChatSessions = hasAnyChatSessions,
                        hasChatSearchQuery = hasChatSearchQuery,
                        hasChatSearchResults = hasChatSearchResults,
                        filteredChatSessions = filteredChatSessions,
                        onChatSearchQueryChange = { chatSearchQuery = it },
                        onClearChatSearch = { chatSearchQuery = "" },
                        onNewChat = {
                            viewModel.startNewChat()
                            destination = AppDestination.Chat
                            scope.launch { drawerState.close() }
                        },
                        onSelectChatSession = { session ->
                            viewModel.selectChatSession(session.id)
                            destination = AppDestination.Chat
                            scope.launch { drawerState.close() }
                        },
                        onRenameChatSession = { session ->
                            renamingSessionId = session.id
                            renameDraft = session.editableTitle()
                        },
                        onArchiveChatSession = { session ->
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
                        onSelectSettings = {
                            returnToChatAfterPairing = false
                            settingsOpenedForPairingOnboarding = false
                            destination = AppDestination.Settings
                            scope.launch { drawerState.close() }
                        },
                    )
                },
            ) {
                Row(modifier = Modifier.fillMaxSize()) {
                    if (usePermanentNavigation) {
                        val newChatEnabled = newChatActionEnabled(state)
                        val newChatStateDescription = newChatActionStateDescription(state)
                        AetherLinkPermanentNavigationRail(
                            selectedDestination = effectiveDestination,
                            chatEnabled = state.trustedRuntime != null,
                            chatStateDescription = if (state.trustedRuntime == null) {
                                stringResource(R.string.new_chat_state_pairing_required)
                            } else {
                                stringResource(R.string.chat_destination_state_ready)
                            },
                            newChatEnabled = newChatEnabled,
                            newChatStateDescription = newChatStateDescription,
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
                            AetherLinkTopAppBar(
                                state = state,
                                effectiveDestination = effectiveDestination,
                                destinationTitle = destinationTitle,
                                onOpenNavigation = {
                                    scope.launch { drawerState.open() }
                                },
                                onStartNewChat = {
                                    viewModel.startNewChat()
                                    destination = AppDestination.Chat
                                },
                                onRequestModels = viewModel::requestModels,
                                onSelectModel = viewModel::selectModel,
                            )
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
                                onRegenerateLatestResponse = viewModel::regenerateLatestResponse,
                                onReuseLatestUserMessage = viewModel::reuseLatestUserMessageAsDraft,
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
@OptIn(ExperimentalMaterial3Api::class)
internal fun AetherLinkTopAppBar(
    state: RuntimeUiState,
    effectiveDestination: AppDestination,
    destinationTitle: String,
    onOpenNavigation: () -> Unit,
    onStartNewChat: () -> Unit,
    onRequestModels: () -> Unit,
    onSelectModel: (String) -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current
    val newChatEnabled = newChatActionEnabled(state)
    val newChatStateDescription = newChatActionStateDescription(state)
    val openNavigationActionLabel = stringResource(R.string.content_desc_open_navigation)
    val newChatActionLabel = stringResource(R.string.new_chat)

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
                        onRequestModels = onRequestModels,
                        onSelectModel = onSelectModel,
                    )
                } else {
                    Text(
                        text = destinationTitle,
                        modifier = Modifier.semantics {
                            heading()
                        },
                    )
                }
            },
            navigationIcon = {
                IconButton(
                    onClick = {
                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                        onOpenNavigation()
                    },
                    modifier = Modifier.semantics {
                        onClick(label = openNavigationActionLabel, action = null)
                    },
                ) {
                    Icon(
                        imageVector = Icons.Filled.Menu,
                        contentDescription = openNavigationActionLabel,
                    )
                }
            },
            actions = {
                if (effectiveDestination == AppDestination.Chat) {
                    IconButton(
                        onClick = {
                            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                            onStartNewChat()
                        },
                        enabled = newChatEnabled,
                        modifier = Modifier.semantics {
                            stateDescription = newChatStateDescription
                            onClick(label = newChatActionLabel, action = null)
                        },
                    ) {
                        Icon(
                            imageVector = Icons.Filled.Edit,
                            contentDescription = newChatActionLabel,
                        )
                    }
                }
            },
        )
        HorizontalDivider(
            color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.36f),
        )
    }
}

@Composable
private fun newChatActionStateDescription(state: RuntimeUiState): String {
    return when {
        state.trustedRuntime == null -> stringResource(R.string.new_chat_state_pairing_required)
        state.isStreaming -> stringResource(R.string.new_chat_state_wait_for_stream)
        else -> stringResource(R.string.new_chat_state_ready)
    }
}

internal fun newChatActionEnabled(state: RuntimeUiState): Boolean {
    return state.trustedRuntime != null && !state.isStreaming
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
internal fun AetherLinkPermanentNavigationRail(
    selectedDestination: AppDestination,
    chatEnabled: Boolean,
    chatStateDescription: String,
    newChatEnabled: Boolean,
    newChatStateDescription: String,
    onNewChat: () -> Unit,
    onSelectDestination: (AppDestination) -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current
    val newChatActionLabel = stringResource(R.string.new_chat)
    val chatActionLabel = stringResource(AppDestination.Chat.labelRes)
    val settingsActionLabel = stringResource(AppDestination.Settings.labelRes)
    val settingsStateDescription = stringResource(R.string.settings_destination_state_ready)

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
                modifier = Modifier.semantics {
                    stateDescription = newChatStateDescription
                    onClick(label = newChatActionLabel, action = null)
                },
            ) {
                Icon(
                    imageVector = Icons.Filled.Edit,
                    contentDescription = newChatActionLabel,
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
            enabled = chatEnabled,
            modifier = Modifier.semantics {
                stateDescription = chatStateDescription
                onClick(label = chatActionLabel, action = null)
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
            modifier = Modifier.semantics {
                stateDescription = settingsStateDescription
                onClick(label = settingsActionLabel, action = null)
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
) {
    val activeChatTitle = chatTopBarActiveTitle(
        state = state,
        untitledTitle = stringResource(R.string.untitled_chat),
    )
    val activeChatTitleSummary = activeChatTitle?.let { title ->
        stringResource(R.string.chat_top_bar_active_title_summary, title)
    }
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
    ) {
        ChatModelTopBarMenu(
            state = state,
            onRequestModels = onRequestModels,
            onSelectModel = onSelectModel,
        )
        if (activeChatTitle != null) {
            Text(
                text = activeChatTitle,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier
                    .weight(1f)
                    .semantics {
                        contentDescription = activeChatTitleSummary ?: activeChatTitle
                        heading()
                    },
            )
        }
    }
}

internal fun chatTopBarActiveTitle(state: RuntimeUiState, untitledTitle: String): String? {
    val activeSessionId = state.activeChatSessionId ?: return null
    return state.chatSessions
        .firstOrNull { it.id == activeSessionId }
        ?.localizedTitle(untitledTitle)
        ?: untitledTitle
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
    val chatModels = chatModelMenuModels(
        models = state.models,
        selectedModelId = state.selectedModelId,
    )
    val selectedModel = chatModels.firstOrNull { it.id == state.selectedModelId }
    val selectedModelUnavailable = state.selectedModelId != null &&
        selectedModel == null &&
        (state.isConnected || state.isLoadingModels)
    val selectedModelUnavailableLabel = state.selectedModelId
        ?.takeIf { selectedModelUnavailable }
        ?.let(::savedModelDisplayName)
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
        state.isStreaming -> stringResource(R.string.model_picker_state_wait_for_stream)
        selectedModel != null -> selectedModel.name
        state.isLoadingModels -> stringResource(R.string.loading_models)
        !state.isConnected -> stringResource(R.string.chat_status_disconnected)
        selectedModelUnavailable -> selectedModelRecoveryMessage
        else -> stringResource(R.string.chat_hint_select_model)
    }
    val modelPickerContentDescription = if (selectedModel != null && !state.isStreaming) {
        stringResource(R.string.chat_model_picker_summary_selected, selectedModel.name)
    } else {
        stringResource(
            R.string.chat_model_picker_summary,
            selectedLabel,
            modelPickerStateDescription,
        )
    }
    val modelPickerActionLabel = stringResource(R.string.choose_model)
    val modelMenuActionsEnabled = !state.isStreaming
    LaunchedEffect(state.isStreaming) {
        if (state.isStreaming) {
            isExpanded = false
        }
    }
    val modelRefreshEnabled = modelMenuActionsEnabled && state.isConnected && !state.isLoadingModels
    val modelRefreshLabel = if (state.isLoadingModels) {
        stringResource(R.string.loading_models)
    } else {
        stringResource(R.string.load_models)
    }
    val modelRefreshStateDescription = when {
        state.isStreaming -> stringResource(R.string.model_picker_state_wait_for_stream)
        state.isLoadingModels -> stringResource(R.string.model_refresh_state_loading)
        state.isConnected -> stringResource(R.string.model_refresh_state_ready)
        else -> stringResource(R.string.model_refresh_state_connect_first)
    }
    val trimmedModelSearchQuery = modelSearchQuery.trim()
    val clearModelSearchContentDescription = stringResource(
        R.string.clear_model_search_named,
        trimmedModelSearchQuery.ifBlank { modelSearchQuery },
    )
    val visibleModels = chatModelMenuModels(
        models = state.models,
        query = trimmedModelSearchQuery,
        selectedModelId = state.selectedModelId,
    )
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
                    contentDescription = modelPickerContentDescription
                    stateDescription = modelPickerStateDescription
                    onClick(label = modelPickerActionLabel, action = null)
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
            expanded = isExpanded && modelMenuActionsEnabled,
            onDismissRequest = { isExpanded = false },
            modifier = Modifier
                .widthIn(min = 260.dp, max = 360.dp)
                .heightIn(max = 420.dp),
        ) {
            DropdownMenuItem(
                modifier = Modifier.semantics(mergeDescendants = true) {
                    contentDescription = modelRefreshLabel
                    stateDescription = modelRefreshStateDescription
                    if (modelRefreshEnabled) {
                        onClick(label = modelRefreshLabel, action = null)
                    }
                },
                text = {
                    Column {
                        Text(
                            text = modelRefreshLabel,
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
                enabled = modelRefreshEnabled,
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
                            text = selectedModelUnavailableLabel
                                ?: stringResource(R.string.selected_model),
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
                                modifier = Modifier.semantics {
                                    contentDescription = clearModelSearchContentDescription
                                    onClick(label = clearModelSearchContentDescription, action = null)
                                },
                            ) {
                                Icon(
                                    imageVector = Icons.Filled.Close,
                                    contentDescription = null,
                                )
                            }
                        }
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag(CHAT_MODEL_SEARCH_TEST_TAG)
                        .padding(horizontal = 12.dp, vertical = 8.dp),
                )
            }
            if (chatModels.isEmpty()) {
                val emptyStateTitle = stringResource(
                    if (state.isConnected) {
                        R.string.no_models_connected_title
                    } else {
                        R.string.no_models_disconnected_title
                    },
                )
                val emptyStateDetail = stringResource(
                    if (state.isConnected) {
                        R.string.no_models_connected
                    } else {
                        R.string.no_models_disconnected
                    },
                )
                val emptyStateSummary = stringResource(
                    R.string.model_picker_empty_state_summary,
                    emptyStateTitle,
                    emptyStateDetail,
                )
                DropdownInfoItem {
                    Column(
                        modifier = Modifier.semantics(mergeDescendants = true) {
                            contentDescription = emptyStateSummary
                            liveRegion = LiveRegionMode.Polite
                        },
                    ) {
                        Text(
                            text = emptyStateTitle,
                            style = MaterialTheme.typography.labelLarge,
                            fontWeight = FontWeight.SemiBold,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                        Text(
                            text = emptyStateDetail,
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
            } else {
                if (visibleModels.isEmpty()) {
                    val noModelSearchResultsText = stringResource(R.string.no_model_search_results)
                    DropdownInfoItem {
                        Text(
                            text = noModelSearchResultsText,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                            modifier = Modifier.semantics {
                                contentDescription = noModelSearchResultsText
                                liveRegion = LiveRegionMode.Polite
                            },
                        )
                    }
                }
                visibleModels.forEach { model ->
                    ChatModelMenuItem(
                        model = model,
                        selected = model.id == state.selectedModelId,
                        installing = model.id == state.installingModelId,
                        actionsEnabled = modelMenuActionsEnabled,
                        onSelect = {
                            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.SelectionChange)
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
    actionsEnabled: Boolean = true,
    onSelect: () -> Unit,
) {
    val statusLine = modelMenuStatusLine(model = model, installing = installing)
    val rowContentDescription = chatModelMenuItemContentDescription(
        model = model,
        selected = selected,
        statusLine = statusLine,
    )
    val rowActionLabel = stringResource(
        if (!model.installed && !installing) {
            R.string.install_model
        } else {
            R.string.choose_model
        }
    )
    DropdownMenuItem(
        modifier = chatModelMenuItemSemanticsModifier(
            model = model,
            selected = selected,
            installing = installing,
            actionsEnabled = actionsEnabled,
            contentDescription = rowContentDescription,
            actionLabel = rowActionLabel,
        ),
        text = {
            Column {
                Text(
                    text = model.name,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = statusLine,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        },
        trailingIcon = {
            if (!model.installed && !installing) {
                Text(
                    text = stringResource(R.string.install_model),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.primary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.widthIn(max = 96.dp),
                )
            } else if (selected) {
                Icon(
                    imageVector = Icons.Filled.CheckCircle,
                    contentDescription = null,
                )
            }
        },
        enabled = actionsEnabled && chatModelMenuItemEnabled(model, installing),
        onClick = onSelect,
    )
}

@Composable
private fun chatModelMenuItemSemanticsModifier(
    model: RuntimeModel,
    selected: Boolean,
    installing: Boolean,
    actionsEnabled: Boolean,
    contentDescription: String,
    actionLabel: String,
): Modifier {
    val enabled = actionsEnabled && chatModelMenuItemEnabled(model, installing)
    val stateDescriptionRes = when {
        !actionsEnabled -> R.string.model_picker_state_wait_for_stream
        selected -> R.string.selection_state_selected
        !model.installed && !installing -> R.string.install_model
        else -> null
    }
    val selectedStateDescription = stateDescriptionRes?.let { stringResource(it) }
    return Modifier.semantics {
        this.contentDescription = contentDescription
        if (enabled) {
            onClick(label = actionLabel, action = null)
        }
        if (selectedStateDescription != null) {
            stateDescription = selectedStateDescription
        }
    }
}

@Composable
private fun chatModelMenuItemContentDescription(
    model: RuntimeModel,
    selected: Boolean,
    statusLine: String,
): String {
    return stringResource(
        if (selected) {
            R.string.chat_model_row_summary_selected
        } else {
            R.string.chat_model_row_summary
        },
        model.name,
        statusLine,
    )
}

internal fun chatModelMenuItemEnabled(model: RuntimeModel, installing: Boolean): Boolean {
    return model.isChatModel() && model.isRuntimeHostLocalModel() && !installing
}

internal fun modelMenuSearchAvailable(models: List<RuntimeModel>): Boolean {
    return chatModelMenuModels(models).isNotEmpty()
}

@Composable
private fun modelMenuStatusLine(model: RuntimeModel, installing: Boolean): String {
    val availability = when {
        installing -> stringResource(R.string.installing_model)
        !model.installed -> stringResource(R.string.model_not_installed)
        model.running -> stringResource(R.string.model_running)
        else -> stringResource(R.string.model_installed)
    }
    return stringResource(
        R.string.model_status_value,
        runtimeProviderDisplayName(model.provider),
        availability,
    )
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

internal fun handlePickedAttachments(
    uris: List<Uri>,
    addAttachments: (List<Uri>) -> Unit,
) {
    if (uris.isNotEmpty()) {
        addAttachments(uris)
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
    val fallbackDisplayName = chatModelPickerFallbackDisplayName(state)
    return when {
        selectedModel != null -> selectedModel.name
        fallbackDisplayName != null -> fallbackDisplayName
        state.isLoadingModels -> loadingModelsLabel
        else -> chooseModelLabel
    }
}

internal fun chatModelPickerFallbackDisplayName(state: RuntimeUiState): String? {
    val selectedId = state.selectedModelId ?: return null
    val canShowSavedModelName = state.isLoadingModels ||
        state.isConnecting ||
        (state.isConnected && state.models.isEmpty())
    return if (canShowSavedModelName) {
        savedModelDisplayName(selectedId)
    } else {
        null
    }
}

private val modelDisplayProviderPrefixes = setOf(
    "ollama",
    "lmstudio",
    "lm_studio",
    "companion",
    "runtime",
)

internal const val DRAWER_HISTORY_TEST_TAG = "aetherlink_drawer_history"
internal const val DRAWER_CHAT_SEARCH_TEST_TAG = "aetherlink_drawer_chat_search"
internal const val DRAWER_SETTINGS_FOOTER_TEST_TAG = "aetherlink_drawer_settings_footer"
internal const val CHAT_MODEL_SEARCH_TEST_TAG = "aetherlink_chat_model_search"

@Composable
internal fun AetherLinkNavigationDrawerContent(
    state: RuntimeUiState,
    effectiveDestination: AppDestination,
    chatSearchQuery: String,
    hasAnyChatSessions: Boolean,
    hasChatSearchQuery: Boolean,
    hasChatSearchResults: Boolean,
    filteredChatSessions: List<RuntimeChatSession>,
    onChatSearchQueryChange: (String) -> Unit,
    onClearChatSearch: () -> Unit,
    onNewChat: () -> Unit,
    onSelectChatSession: (RuntimeChatSession) -> Unit,
    onRenameChatSession: (RuntimeChatSession) -> Unit,
    onArchiveChatSession: (RuntimeChatSession) -> Unit,
    onSelectSettings: () -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current
    val newChatEnabled = newChatActionEnabled(state)
    val newChatStateDescription = newChatActionStateDescription(state)
    val newChatActionLabel = stringResource(R.string.new_chat)
    val settingsStateDescription = stringResource(R.string.settings_destination_state_ready)

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
                    onNewChat()
                },
                enabled = newChatEnabled,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 12.dp, vertical = 8.dp)
                    .semantics {
                        stateDescription = newChatStateDescription
                        onClick(label = newChatActionLabel, action = null)
                    },
            ) {
                Icon(Icons.Filled.Add, contentDescription = null)
                Spacer(Modifier.size(8.dp))
                Text(newChatActionLabel)
            }
            Column(
                modifier = Modifier
                    .weight(1f)
                    .verticalScroll(rememberScrollState())
                    .testTag(DRAWER_HISTORY_TEST_TAG),
            ) {
                DrawerSectionLabel(text = stringResource(R.string.previous_chats))
                if (hasAnyChatSessions) {
                    ChatHistorySearchField(
                        query = chatSearchQuery,
                        onQueryChange = onChatSearchQueryChange,
                        onClear = {
                            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                            onClearChatSearch()
                        },
                    )
                }
                if (hasChatSearchQuery && !hasChatSearchResults) {
                    val noSearchResultsText = stringResource(R.string.no_chat_search_results)
                    Text(
                        text = noSearchResultsText,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier
                            .padding(horizontal = 28.dp, vertical = 8.dp)
                            .semantics {
                                liveRegion = LiveRegionMode.Polite
                            },
                    )
                } else if (!hasChatSearchQuery && state.chatSessions.isEmpty()) {
                    val noPreviousChatsText = stringResource(R.string.no_previous_chats)
                    Text(
                        text = noPreviousChatsText,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier
                            .padding(horizontal = 28.dp, vertical = 8.dp)
                            .semantics {
                                contentDescription = noPreviousChatsText
                                liveRegion = LiveRegionMode.Polite
                            },
                    )
                } else {
                    filteredChatSessions.forEach { session ->
                        ChatSessionDrawerItem(
                            session = session,
                            models = state.models,
                            selected = effectiveDestination == AppDestination.Chat &&
                                session.id == state.activeChatSessionId,
                            enabled = !state.isStreaming,
                            onClick = { onSelectChatSession(session) },
                            onRename = {
                                hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                                onRenameChatSession(session)
                            },
                            onArchive = {
                                hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                                onArchiveChatSession(session)
                            },
                            onRestore = null,
                            onDelete = null,
                        )
                    }
                }
            }
            HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))
            Box(modifier = Modifier.testTag(DRAWER_SETTINGS_FOOTER_TEST_TAG)) {
                DrawerDestinationItem(
                    destination = AppDestination.Settings,
                    selected = effectiveDestination == AppDestination.Settings,
                    stateDescription = settingsStateDescription,
                    onClick = {
                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.SelectionChange)
                        onSelectSettings()
                    },
                )
            }
        }
    }
}

@Composable
private fun DrawerRuntimeSummary(state: RuntimeUiState) {
    val chatModels = chatModelMenuModels(state.models)
    val selectedModel = chatModels.firstOrNull { it.id == state.selectedModelId }
    val selectedModelUnavailable = state.selectedModelId != null &&
        selectedModel == null &&
        (state.isConnected || state.isLoadingModels)
    val runtimeName = state.trustedRuntime?.name ?: stringResource(R.string.no_trusted_runtime)
    val modelName = selectedModel?.name
        ?: state.selectedModelId
            ?.takeIf { selectedModelUnavailable }
            ?.let(::savedModelDisplayName)
        ?: chatModelPickerFallbackDisplayName(state)
        ?: stringResource(R.string.model_none)
    val modelDetail = when {
        !selectedModelUnavailable -> null
        state.isLoadingModels -> stringResource(R.string.selected_model_restoring)
        else -> stringResource(R.string.selected_model_unavailable)
    }
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
    val runtimeSummaryAccessibility = modelDetail?.let { detail ->
        stringResource(
            R.string.drawer_runtime_summary_accessibility_with_detail,
            runtimeName,
            connectionLabel,
            modelName,
            detail,
        )
    } ?: stringResource(
        R.string.drawer_runtime_summary_accessibility,
        runtimeName,
        connectionLabel,
        modelName,
    )

    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 2.dp)
            .clearAndSetSemantics {
                contentDescription = runtimeSummaryAccessibility
            },
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
            if (modelDetail != null) {
                Text(
                    text = modelDetail,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

@Composable
private fun ChatHistorySearchField(
    query: String,
    onQueryChange: (String) -> Unit,
    onClear: () -> Unit,
) {
    val clearChatSearchContentDescription = stringResource(R.string.clear_chat_search_named, query)
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
                    modifier = Modifier.semantics {
                        contentDescription = clearChatSearchContentDescription
                        onClick(label = clearChatSearchContentDescription, action = null)
                    },
                ) {
                    Icon(
                        imageVector = Icons.Filled.Close,
                        contentDescription = null,
                    )
                }
            }
        },
        modifier = Modifier
            .fillMaxWidth()
            .testTag(DRAWER_CHAT_SEARCH_TEST_TAG)
            .padding(horizontal = 12.dp, vertical = 4.dp),
    )
}

@Composable
private fun DrawerSectionLabel(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.labelMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier
            .padding(horizontal = 28.dp, vertical = 8.dp)
            .semantics {
                heading()
            },
    )
}

@Composable
internal fun ChatSessionDrawerItem(
    session: RuntimeChatSession,
    models: List<RuntimeModel> = emptyList(),
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
    val chatSessionOptionsContentDescription = stringResource(R.string.chat_session_more_named, title)
    val baseSubtitle = when {
        session.archivedAtMillis != null -> stringResource(R.string.archived_chat)
        session.messageCount > 0 -> pluralStringResource(
            R.plurals.chat_message_count,
            session.messageCount,
            session.messageCount,
        )
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
    val modelText = chatHistorySessionModelDisplayName(session = session, models = models)
        ?.let { modelName -> stringResource(R.string.chat_session_model_value, modelName) }
    val accessibleSubtitle = subtitle.ifBlank { stringResource(R.string.new_chat) }
    val chatSessionContentDescription = when {
        selected && modelText != null -> {
            stringResource(
                R.string.chat_session_row_summary_selected_with_model,
                title,
                accessibleSubtitle,
                modelText,
            )
        }
        selected -> stringResource(R.string.chat_session_row_summary_selected, title, accessibleSubtitle)
        modelText != null -> stringResource(R.string.chat_session_row_summary_with_model, title, accessibleSubtitle, modelText)
        else -> stringResource(R.string.chat_session_row_summary, title, accessibleSubtitle)
    }
    val renameActionContentDescription = stringResource(R.string.rename_chat_named, title)
    val archiveActionContentDescription = stringResource(R.string.archive_chat_named, title)
    val restoreActionContentDescription = stringResource(R.string.restore_chat_named, title)
    val deleteActionContentDescription = stringResource(R.string.delete_chat_named, title)
    val disabledStateDescription = if (enabled) {
        null
    } else {
        stringResource(R.string.chat_history_action_state_wait_for_stream)
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
                    if (modelText != null) {
                        Text(
                            text = modelText,
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
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
                    modifier = Modifier
                        .size(32.dp)
                        .semantics {
                            contentDescription = chatSessionOptionsContentDescription
                            onClick(label = chatSessionOptionsContentDescription, action = null)
                            disabledStateDescription?.let { stateDescription = it }
                        },
                ) {
                    Icon(
                        imageVector = Icons.Filled.MoreVert,
                        contentDescription = null,
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
                            modifier = Modifier.semantics {
                                contentDescription = renameActionContentDescription
                                onClick(label = renameActionContentDescription, action = null)
                            },
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
                            modifier = Modifier.semantics {
                                contentDescription = archiveActionContentDescription
                                onClick(label = archiveActionContentDescription, action = null)
                            },
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
                            modifier = Modifier.semantics {
                                contentDescription = restoreActionContentDescription
                                onClick(label = restoreActionContentDescription, action = null)
                            },
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
                            modifier = Modifier.semantics {
                                contentDescription = deleteActionContentDescription
                                onClick(label = deleteActionContentDescription, action = null)
                            },
                            onClick = {
                                isMenuExpanded = false
                                onDelete()
                            },
                        )
                    }
                }
            }
        },
        modifier = Modifier
            .padding(horizontal = 12.dp)
            .alpha(if (enabled) 1f else 0.46f)
            .semantics {
                contentDescription = chatSessionContentDescription
                disabledStateDescription?.let {
                    stateDescription = it
                    disabled()
                }
            },
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
internal fun RenameChatSessionDialog(
    title: String,
    onTitleChange: (String) -> Unit,
    onDismiss: () -> Unit,
    onConfirm: () -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current
    val trimmedTitle = title.trim()
    val titleStateDescription = if (trimmedTitle.isBlank()) {
        stringResource(R.string.rename_chat_title_state_empty)
    } else {
        stringResource(R.string.rename_chat_title_state_ready)
    }
    val titleContentDescription = stringResource(R.string.chat_title_label)
    val renameSubject = stringResource(R.string.rename_chat)
    val confirmRenameActionLabel = stringResource(
        R.string.confirmation_final_action_named,
        renameSubject,
    )
    val cancelRenameActionLabel = stringResource(
        R.string.confirmation_cancel_action_named,
        renameSubject,
    )

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(renameSubject) },
        text = {
            OutlinedTextField(
                value = title,
                onValueChange = onTitleChange,
                label = { Text(stringResource(R.string.chat_title_label)) },
                singleLine = true,
                modifier = Modifier
                    .fillMaxWidth()
                    .semantics {
                        contentDescription = titleContentDescription
                        stateDescription = titleStateDescription
                    },
            )
        },
        confirmButton = {
            TextButton(
                onClick = {
                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                    onConfirm()
                },
                enabled = trimmedTitle.isNotBlank(),
                modifier = Modifier.semantics {
                    contentDescription = confirmRenameActionLabel
                    stateDescription = titleStateDescription
                    onClick(label = confirmRenameActionLabel, action = null)
                },
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
                modifier = Modifier.semantics {
                    contentDescription = cancelRenameActionLabel
                    onClick(label = cancelRenameActionLabel, action = null)
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
    stateDescription: String? = null,
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
        modifier = Modifier
            .padding(horizontal = 12.dp)
            .semantics {
                stateDescription?.let { this.stateDescription = it }
                onClick(label = label, action = null)
            },
    )
}

@Composable
internal fun AetherLinkTheme(theme: RuntimeAppTheme, content: @Composable () -> Unit) {
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
    val activity = context as? ComponentActivity
    val lifecycleOwner = LocalLifecycleOwner.current
    var torchEnabled by rememberSaveable { mutableStateOf(false) }
    var torchAvailable by rememberSaveable { mutableStateOf(false) }
    var cameraPermissionRequested by rememberSaveable { mutableStateOf(false) }
    var hasCameraPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) ==
                PackageManager.PERMISSION_GRANTED,
        )
    }
    var shouldShowCameraPermissionRationale by remember {
        mutableStateOf(
            activity?.let {
                ActivityCompat.shouldShowRequestPermissionRationale(it, Manifest.permission.CAMERA)
            } == true,
        )
    }
    val refreshCameraPermissionState = {
        hasCameraPermission = ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) ==
            PackageManager.PERMISSION_GRANTED
        shouldShowCameraPermissionRationale = activity?.let {
            ActivityCompat.shouldShowRequestPermissionRationale(it, Manifest.permission.CAMERA)
        } == true
        if (hasCameraPermission) {
            cameraPermissionRequested = false
        }
    }
    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission(),
    ) { granted ->
        cameraPermissionRequested = true
        hasCameraPermission = granted
        shouldShowCameraPermissionRationale = activity?.let {
            ActivityCompat.shouldShowRequestPermissionRationale(it, Manifest.permission.CAMERA)
        } == true
    }
    val requestCameraPermission = {
        cameraPermissionRequested = true
        permissionLauncher.launch(Manifest.permission.CAMERA)
    }
    val cameraPermissionPermanentlyDenied = !hasCameraPermission &&
        cameraPermissionRequested &&
        !shouldShowCameraPermissionRationale
    val openAppSettings = {
        context.startActivity(
            Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                data = Uri.fromParts("package", context.packageName, null)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            },
        )
    }

    DisposableEffect(lifecycleOwner, context) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                refreshCameraPermissionState()
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
        }
    }

    LaunchedEffect(Unit) {
        if (!hasCameraPermission) {
            requestCameraPermission()
        }
    }

    PairingQrScannerChrome(
        hasCameraPermission = hasCameraPermission,
        cameraPermissionPermanentlyDenied = cameraPermissionPermanentlyDenied,
        torchAvailable = torchAvailable,
        torchEnabled = torchEnabled,
        onTorchToggle = {
            torchEnabled = !torchEnabled
        },
        onCancel = onCancel,
        onRequestCameraPermission = requestCameraPermission,
        onOpenAppSettings = openAppSettings,
        modifier = modifier,
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
    }
}

@Composable
@OptIn(ExperimentalMaterial3Api::class)
internal fun PairingQrScannerChrome(
    hasCameraPermission: Boolean,
    cameraPermissionPermanentlyDenied: Boolean = false,
    torchAvailable: Boolean,
    torchEnabled: Boolean,
    onTorchToggle: () -> Unit,
    onCancel: () -> Unit,
    onRequestCameraPermission: () -> Unit,
    onOpenAppSettings: () -> Unit = {},
    modifier: Modifier = Modifier,
    cameraContent: @Composable () -> Unit = {},
) {
    val hapticFeedback = LocalHapticFeedback.current

    Scaffold(
        modifier = modifier,
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = stringResource(R.string.qr_scanner_title),
                        modifier = Modifier.semantics {
                            heading()
                        },
                    )
                },
                navigationIcon = {
                    val closeScannerActionLabel = stringResource(R.string.qr_scanner_close_action)
                    IconButton(
                        onClick = {
                            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Toggle)
                            onCancel()
                        },
                        modifier = Modifier.semantics {
                            onClick(label = closeScannerActionLabel, action = null)
                        },
                    ) {
                        Icon(
                            imageVector = Icons.Filled.Close,
                            contentDescription = closeScannerActionLabel,
                        )
                    }
                },
                actions = {
                    if (torchAvailable) {
                        val torchStateDescription = stringResource(
                            if (torchEnabled) {
                                R.string.qr_scanner_flashlight_state_on
                            } else {
                                R.string.qr_scanner_flashlight_state_off
                            }
                        )
                        IconButton(
                            onClick = {
                                hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Toggle)
                                onTorchToggle()
                            },
                            modifier = Modifier
                                .testTag(PAIRING_QR_FLASHLIGHT_BUTTON_TEST_TAG)
                                .semantics {
                                    stateDescription = torchStateDescription
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
                cameraContent()
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
                                hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Toggle)
                                onCancel()
                            },
                        ) {
                            Text(stringResource(R.string.cancel))
                        }
                    }
                }
            }
        } else {
            val permissionTitle = stringResource(
                if (cameraPermissionPermanentlyDenied) {
                    R.string.qr_scanner_permission_blocked_title
                } else {
                    R.string.qr_scanner_permission_title
                },
            )
            val permissionDetail = stringResource(
                if (cameraPermissionPermanentlyDenied) {
                    R.string.qr_scanner_permission_blocked_detail
                } else {
                    R.string.qr_scanner_permission_detail
                },
            )
            val permissionAction = stringResource(
                if (cameraPermissionPermanentlyDenied) {
                    R.string.qr_scanner_permission_settings_action
                } else {
                    R.string.qr_scanner_permission_action
                },
            )
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(24.dp),
                verticalArrangement = Arrangement.Center,
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text(
                    text = permissionTitle,
                    style = MaterialTheme.typography.titleLarge,
                    color = MaterialTheme.colorScheme.onSurface,
                    modifier = Modifier.semantics {
                        heading()
                    },
                )
                Spacer(Modifier.size(12.dp))
                Text(
                    text = permissionDetail,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                )
                Spacer(Modifier.size(18.dp))
                Button(
                    onClick = {
                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                        if (cameraPermissionPermanentlyDenied) {
                            onOpenAppSettings()
                        } else {
                            onRequestCameraPermission()
                        }
                    },
                ) {
                    Text(permissionAction)
                }
                Spacer(Modifier.size(8.dp))
                TextButton(
                    onClick = {
                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Toggle)
                        onCancel()
                    },
                ) {
                    Text(stringResource(R.string.cancel))
                }
            }
        }
    }
}

internal const val PAIRING_QR_FLASHLIGHT_BUTTON_TEST_TAG = "pairing_qr_flashlight_button"

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
