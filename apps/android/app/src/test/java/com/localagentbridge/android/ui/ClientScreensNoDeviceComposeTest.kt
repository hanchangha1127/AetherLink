package com.localagentbridge.android.ui

import android.content.Context
import android.content.res.Configuration
import android.os.LocaleList
import android.text.format.Formatter
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.hapticfeedback.HapticFeedback
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.test.assert
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.assertHeightIsAtLeast
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.assertWidthIsAtLeast
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.hasClickAction
import androidx.compose.ui.test.hasContentDescription
import androidx.compose.ui.test.hasStateDescription
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onAllNodesWithContentDescription
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onFirst
import androidx.compose.ui.test.onLast
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollToIndex
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTouchInput
import androidx.compose.ui.test.performTextInput
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.swipeUp
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.unit.dp
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.localagentbridge.android.AetherLinkNavigationDrawerContent
import com.localagentbridge.android.AetherLinkTopAppBar
import com.localagentbridge.android.AppDestination
import com.localagentbridge.android.ChatSessionDrawerItem
import com.localagentbridge.android.ChatTopAppBarTitle
import com.localagentbridge.android.DRAWER_HISTORY_TEST_TAG
import com.localagentbridge.android.DRAWER_SETTINGS_FOOTER_TEST_TAG
import com.localagentbridge.android.R
import com.localagentbridge.android.runtime.MODEL_KIND_CHAT
import com.localagentbridge.android.runtime.MODEL_KIND_EMBEDDING
import com.localagentbridge.android.runtime.RuntimeAppTheme
import com.localagentbridge.android.runtime.RuntimeChatMessage
import com.localagentbridge.android.runtime.RuntimeChatSession
import com.localagentbridge.android.runtime.RuntimeDiscoveredRuntime
import com.localagentbridge.android.runtime.RuntimeMemoryEntry
import com.localagentbridge.android.runtime.RuntimeMessageAttachment
import com.localagentbridge.android.runtime.RuntimeModel
import com.localagentbridge.android.runtime.RuntimePendingAttachment
import com.localagentbridge.android.runtime.RuntimeTrustedRuntime
import com.localagentbridge.android.runtime.RuntimeUiState
import com.localagentbridge.android.core.transport.RuntimeEndpointHint
import com.localagentbridge.android.core.transport.RuntimeEndpointSource
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import java.util.Locale

@RunWith(AndroidJUnit4::class)
@Config(sdk = [35])
class ClientScreensNoDeviceComposeTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun settingsScreenRendersPairingFirstFlowAndQrAction() {
        var scanClicks = 0

        compose.setContent {
            MaterialTheme {
                SettingsScreen(
                    state = RuntimeUiState(),
                    onHostChange = {},
                    onPortChange = {},
                    onUseUsbReverse = {},
                    onUseEmulator = {},
                    onStartDiscovery = {},
                    onStopDiscovery = {},
                    onUseDiscoveredRuntime = {},
                    onForgetTrustedRuntime = {},
                    onScanPairingQr = { scanClicks += 1 },
                    onSubmitPairingPayload = {},
                    onConnect = {},
                    onRefreshHealth = {},
                    onRequestModels = {},
                    onDisconnect = {},
                    onSetAutoReconnectEnabled = {},
                    onSetLanguageTag = {},
                    onSetTheme = {},
                    onSelectEmbeddingModel = {},
                    onAddMemoryEntry = {},
                    onRemoveMemoryEntry = {},
                    onSetMemoryEntryEnabled = { _, _ -> },
                    onArchiveChatSession = {},
                    onRestoreChatSession = {},
                    onPermanentlyDeleteChatSession = {},
                    onArchiveAllChatSessions = {},
                    onPermanentlyDeleteArchivedChatSessions = {},
                    showDeveloperDiagnostics = false,
                )
            }
        }

        compose.onNodeWithText("Pair AetherLink").assertIsDisplayed()
        compose.onNodeWithText("Scan Pairing QR").assertIsDisplayed()
        compose.onNodeWithText("No trusted runtime saved").assertExists()

        compose.onAllNodesWithText("Scan QR").onFirst().performClick()

        assertEquals(1, scanClicks)
    }

    @Test
    fun settingsExpandableSectionsExposeLocalizedExpandedState() {
        compose.setContent {
            MaterialTheme {
                SettingsScreen(
                    state = RuntimeUiState(
                        isConnected = true,
                        runtimeStatus = "authenticated",
                        trustedRuntime = RuntimeTrustedRuntime(
                            deviceId = "runtime-1",
                            name = "AetherLink Runtime",
                        ),
                    ),
                    onHostChange = {},
                    onPortChange = {},
                    onUseUsbReverse = {},
                    onUseEmulator = {},
                    onStartDiscovery = {},
                    onStopDiscovery = {},
                    onUseDiscoveredRuntime = {},
                    onForgetTrustedRuntime = {},
                    onScanPairingQr = {},
                    onSubmitPairingPayload = {},
                    onConnect = {},
                    onRefreshHealth = {},
                    onRequestModels = {},
                    onDisconnect = {},
                    onSetAutoReconnectEnabled = {},
                    onSetLanguageTag = {},
                    onSetTheme = {},
                    onSelectEmbeddingModel = {},
                    onAddMemoryEntry = {},
                    onRemoveMemoryEntry = {},
                    onSetMemoryEntryEnabled = { _, _ -> },
                    onArchiveChatSession = {},
                    onRestoreChatSession = {},
                    onPermanentlyDeleteChatSession = {},
                    onArchiveAllChatSessions = {},
                    onPermanentlyDeleteArchivedChatSessions = {},
                    showDeveloperDiagnostics = false,
                )
            }
        }

        compose.onNode(hasText("Pairing & Connection") and hasStateDescription("Collapsed"))
            .assertIsDisplayed()
            .performClick()

        compose.onNode(hasText("Pairing & Connection") and hasStateDescription("Expanded"))
            .assertIsDisplayed()
    }

    @Test
    fun settingsTrustedRuntimeForgetRequiresConfirmation() {
        val hapticFeedback = RecordingHapticFeedback()
        var forgetClicks = 0

        compose.setContent {
            CompositionLocalProvider(LocalHapticFeedback provides hapticFeedback) {
                MaterialTheme {
                    SettingsScreen(
                        state = RuntimeUiState(
                            isConnected = true,
                            runtimeStatus = "authenticated",
                            trustedRuntime = RuntimeTrustedRuntime(
                                deviceId = "runtime-1",
                                name = "AetherLink Runtime",
                            ),
                        ),
                        onHostChange = {},
                        onPortChange = {},
                        onUseUsbReverse = {},
                        onUseEmulator = {},
                        onStartDiscovery = {},
                        onStopDiscovery = {},
                        onUseDiscoveredRuntime = {},
                        onForgetTrustedRuntime = { forgetClicks += 1 },
                        onScanPairingQr = {},
                        onSubmitPairingPayload = {},
                        onConnect = {},
                        onRefreshHealth = {},
                        onRequestModels = {},
                        onDisconnect = {},
                        onSetAutoReconnectEnabled = {},
                        onSetLanguageTag = {},
                        onSetTheme = {},
                        onSelectEmbeddingModel = {},
                        onAddMemoryEntry = {},
                        onRemoveMemoryEntry = {},
                        onSetMemoryEntryEnabled = { _, _ -> },
                        onArchiveChatSession = {},
                        onRestoreChatSession = {},
                        onPermanentlyDeleteChatSession = {},
                        onArchiveAllChatSessions = {},
                        onPermanentlyDeleteArchivedChatSessions = {},
                        showDeveloperDiagnostics = false,
                    )
                }
            }
        }

        compose.onNode(hasText("Pairing & Connection") and hasStateDescription("Collapsed"))
            .performClick()
        hapticFeedback.events.clear()
        compose.onNodeWithText("Forget")
            .performScrollTo()
            .assertIsDisplayed()
            .performClick()

        compose.onNodeWithText("Forget trusted runtime?").assertIsDisplayed()
        assertEquals(0, forgetClicks)
        assertEquals(listOf(HapticFeedbackType.TextHandleMove), hapticFeedback.events)

        compose.onNodeWithText("Cancel").performClick()
        compose.onAllNodesWithText("Forget trusted runtime?").assertCountEquals(0)
        assertEquals(0, forgetClicks)
        assertEquals(
            listOf(HapticFeedbackType.TextHandleMove, HapticFeedbackType.TextHandleMove),
            hapticFeedback.events,
        )
        hapticFeedback.events.clear()

        compose.onNodeWithText("Forget")
            .performScrollTo()
            .performClick()
        compose.onNodeWithText("Forget runtime").performClick()

        assertEquals(1, forgetClicks)
        assertEquals(
            listOf(HapticFeedbackType.TextHandleMove, HapticFeedbackType.LongPress),
            hapticFeedback.events,
        )
    }

    @Test
    fun navigationDrawerKeepsSettingsAsFooterBelowChatHistory() {
        var settingsClicks = 0
        val sessions = listOf(
            RuntimeChatSession(
                id = "session-1",
                title = "Runtime pairing notes",
                modelId = "ollama:qwen3:8b",
                updatedAtMillis = 2_000L,
                messageCount = 4,
            ),
            RuntimeChatSession(
                id = "session-2",
                title = "Travel plan",
                modelId = "ollama:llama3.1:8b",
                updatedAtMillis = 1_000L,
                messageCount = 2,
            ),
        )
        val state = RuntimeUiState(
            isConnected = true,
            runtimeStatus = "authenticated",
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "runtime-1",
                name = "AetherLink Runtime",
            ),
            chatSessions = sessions,
            activeChatSessionId = "session-1",
        )

        compose.setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    AetherLinkNavigationDrawerContent(
                        state = state,
                        effectiveDestination = AppDestination.Chat,
                        chatSearchQuery = "",
                        hasAnyChatSessions = sessions.isNotEmpty(),
                        hasChatSearchQuery = false,
                        hasChatSearchResults = true,
                        filteredChatSessions = sessions,
                        onChatSearchQueryChange = {},
                        onClearChatSearch = {},
                        onNewChat = {},
                        onSelectChatSession = {},
                        onRenameChatSession = {},
                        onArchiveChatSession = {},
                        onSelectSettings = { settingsClicks += 1 },
                    )
                }
            }
        }

        val historyTop = compose
            .onNodeWithTag(DRAWER_HISTORY_TEST_TAG)
            .getUnclippedBoundsInRoot()
            .top
        val settingsTop = compose
            .onNodeWithTag(DRAWER_SETTINGS_FOOTER_TEST_TAG)
            .getUnclippedBoundsInRoot()
            .top

        assertTrue(settingsTop > historyTop)
        compose.onNodeWithText("Settings").assertIsDisplayed().performClick()
        assertEquals(1, settingsClicks)
    }

    @Test
    fun appTopBarKeepsNavigationModelPickerAndNewChatChrome() {
        var navigationClicks = 0
        var newChatClicks = 0
        var requestModelClicks = 0
        val selectedModels = mutableListOf<String>()
        val chatModel = RuntimeModel(
            id = "ollama:qwen3:8b",
            name = "Qwen3 8B",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = true,
            source = "local",
        )
        val embeddingModel = RuntimeModel(
            id = "ollama:nomic-embed-text",
            name = "Nomic Embed Text",
            modelKind = MODEL_KIND_EMBEDDING,
            capabilities = listOf("embedding"),
            installed = true,
            source = "local",
        )

        compose.setContent {
            MaterialTheme {
                Surface {
                    AetherLinkTopAppBar(
                        state = RuntimeUiState(
                            isConnected = true,
                            runtimeStatus = "authenticated",
                            backendAvailable = true,
                            trustedRuntime = RuntimeTrustedRuntime(
                                deviceId = "runtime-1",
                                name = "AetherLink Runtime",
                            ),
                            selectedModelId = chatModel.id,
                            models = listOf(chatModel, embeddingModel),
                        ),
                        effectiveDestination = AppDestination.Chat,
                        destinationTitle = "Chat",
                        onOpenNavigation = { navigationClicks += 1 },
                        onStartNewChat = { newChatClicks += 1 },
                        onRequestModels = { requestModelClicks += 1 },
                        onSelectModel = { selectedModels += it },
                    )
                }
            }
        }

        compose.onNodeWithContentDescription("Open navigation menu").assertIsDisplayed().performClick()
        compose.onNodeWithText("Qwen3 8B").assertIsDisplayed()
        compose.onNodeWithContentDescription("New Chat").assertIsDisplayed().performClick()
        compose.onNodeWithText("Qwen3 8B").performClick()
        compose.waitForIdle()
        assertNoVisibleText("Memory indexing model")
        assertNoVisibleText("Nomic Embed Text")

        assertEquals(1, navigationClicks)
        assertEquals(1, newChatClicks)
        assertEquals(0, requestModelClicks)
        assertEquals(emptyList<String>(), selectedModels)
        assertNoVisibleText("Enter a message to send.")
        assertNoVisibleText("Ask anything")
    }

    @Test
    fun settingsPrimaryConnectionSectionReopensWhenPairingBecomesRequired() {
        val settingsState = mutableStateOf(
            RuntimeUiState(
                isConnected = true,
                runtimeStatus = "authenticated",
                trustedRuntime = RuntimeTrustedRuntime(
                    deviceId = "runtime-1",
                    name = "AetherLink Runtime",
                ),
                backendAvailable = true,
            )
        )

        compose.setContent {
            MaterialTheme {
                SettingsScreen(
                    state = settingsState.value,
                    onHostChange = {},
                    onPortChange = {},
                    onUseUsbReverse = {},
                    onUseEmulator = {},
                    onStartDiscovery = {},
                    onStopDiscovery = {},
                    onUseDiscoveredRuntime = {},
                    onForgetTrustedRuntime = {},
                    onScanPairingQr = {},
                    onSubmitPairingPayload = {},
                    onConnect = {},
                    onRefreshHealth = {},
                    onRequestModels = {},
                    onDisconnect = {},
                    onSetAutoReconnectEnabled = {},
                    onSetLanguageTag = {},
                    onSetTheme = {},
                    onSelectEmbeddingModel = {},
                    onAddMemoryEntry = {},
                    onRemoveMemoryEntry = {},
                    onSetMemoryEntryEnabled = { _, _ -> },
                    onArchiveChatSession = {},
                    onRestoreChatSession = {},
                    onPermanentlyDeleteChatSession = {},
                    onArchiveAllChatSessions = {},
                    onPermanentlyDeleteArchivedChatSessions = {},
                    showDeveloperDiagnostics = false,
                )
            }
        }

        compose.onNodeWithText("Pairing & Connection").assertIsDisplayed()
        assertNoVisibleText("Scan Pairing QR")

        compose.runOnUiThread {
            settingsState.value = RuntimeUiState()
        }
        compose.waitForIdle()

        compose.onNodeWithText("Pair AetherLink").assertIsDisplayed()
        compose.onNodeWithText("Scan Pairing QR").assertIsDisplayed()
    }

    @Test
    fun settingsScreenRendersPendingPairingRouteState() {
        compose.setContent {
            MaterialTheme {
                SettingsScreen(
                    state = RuntimeUiState(
                        isPairingAwaitingRoute = true,
                        pendingPairingRuntimeName = "AetherLink Runtime",
                    ),
                    onHostChange = {},
                    onPortChange = {},
                    onUseUsbReverse = {},
                    onUseEmulator = {},
                    onStartDiscovery = {},
                    onStopDiscovery = {},
                    onUseDiscoveredRuntime = {},
                    onForgetTrustedRuntime = {},
                    onScanPairingQr = {},
                    onSubmitPairingPayload = {},
                    onConnect = {},
                    onRefreshHealth = {},
                    onRequestModels = {},
                    onDisconnect = {},
                    onSetAutoReconnectEnabled = {},
                    onSetLanguageTag = {},
                    onSetTheme = {},
                    onSelectEmbeddingModel = {},
                    onAddMemoryEntry = {},
                    onRemoveMemoryEntry = {},
                    onSetMemoryEntryEnabled = { _, _ -> },
                    onArchiveChatSession = {},
                    onRestoreChatSession = {},
                    onPermanentlyDeleteChatSession = {},
                    onArchiveAllChatSessions = {},
                    onPermanentlyDeleteArchivedChatSessions = {},
                    showDeveloperDiagnostics = false,
                )
            }
        }

        compose.onNodeWithText("QR scanned").assertExists()
        compose.onAllNodesWithText(
            "This QR identified AetherLink Runtime, but it cannot reconnect across networks without protected connection details. Generate the latest QR in AetherLink Runtime and scan it again."
        ).onFirst().assertExists()
        compose.onNodeWithText("Waiting for AetherLink Runtime").assertExists()
        compose.onAllNodesWithText("Scan latest QR").onFirst().assertExists()
    }

    @Test
    fun connectionStatusNoticeExposesRouteStatusPillAndAccessibilityState() {
        compose.setContent {
            MaterialTheme {
                ConnectionStatusScreen(
                    state = RuntimeUiState(
                        trustedRuntime = RuntimeTrustedRuntime(
                            deviceId = "runtime-1",
                            name = "AetherLink Runtime",
                            relayHost = "relay.example.test",
                            relayPort = 443,
                            relayId = "relay-1",
                            relaySecret = "secret-1",
                            relayExpiresAtEpochMillis = Long.MAX_VALUE,
                            relayNonce = "nonce-1",
                        ),
                        backendAvailable = true,
                    ),
                    onConnect = {},
                    onRefreshHealth = {},
                    onDisconnect = {},
                    onScanLatestQr = {},
                )
            }
        }

        compose.onNodeWithText("Saved connection")
            .performScrollTo()
            .assertIsDisplayed()
        compose.onNode(hasStateDescription("Saved connection"), useUnmergedTree = true)
            .performScrollTo()
            .assertIsDisplayed()
    }

    @Test
    fun connectionStatusRefreshHealthActionUsesActionCopyAndCallback() {
        var refreshClicks = 0

        compose.setContent {
            MaterialTheme {
                ConnectionStatusScreen(
                    state = RuntimeUiState(
                        isConnected = true,
                        backendAvailable = true,
                    ),
                    onConnect = {},
                    onRefreshHealth = { refreshClicks += 1 },
                    onDisconnect = {},
                    onScanLatestQr = {},
                )
            }
        }

        repeat(3) {
            compose.onRoot().performTouchInput { swipeUp() }
            compose.waitForIdle()
        }
        compose.onNodeWithText("Refresh health")
            .assertIsDisplayed()
            .performClick()

        assertEquals(1, refreshClicks)
    }

    @Test
    fun connectionStatusSavedRouteNoticeClickConnectsWithHaptic() {
        val hapticFeedback = RecordingHapticFeedback()
        var connectClicks = 0
        var scanQrClicks = 0

        compose.setContent {
            CompositionLocalProvider(LocalHapticFeedback provides hapticFeedback) {
                MaterialTheme {
                    ConnectionStatusScreen(
                        state = RuntimeUiState(
                            trustedRuntime = RuntimeTrustedRuntime(
                                deviceId = "runtime-1",
                                name = "AetherLink Runtime",
                                endpointHint = RuntimeEndpointHint(
                                    host = "192.0.2.10",
                                    port = 43170,
                                    source = RuntimeEndpointSource.TrustedLastKnown,
                                ),
                                relayHost = "relay.example.test",
                                relayPort = 443,
                                relayId = "relay-1",
                                relaySecret = "secret-1",
                                relayExpiresAtEpochMillis = Long.MAX_VALUE,
                                relayNonce = "nonce-1",
                            ),
                            backendAvailable = true,
                        ),
                        onConnect = { connectClicks += 1 },
                        onRefreshHealth = {},
                        onDisconnect = {},
                        onScanLatestQr = { scanQrClicks += 1 },
                    )
                }
            }
        }

        compose.onNode(hasStateDescription("Saved connection") and hasClickAction(), useUnmergedTree = true)
            .performScrollTo()
            .performClick()

        assertEquals(1, connectClicks)
        assertEquals(0, scanQrClicks)
        assertEquals(listOf(HapticFeedbackType.TextHandleMove), hapticFeedback.events)
    }

    @Test
    fun connectionStatusRefreshNeededRouteNoticeClickScansLatestQrWithHaptic() {
        val hapticFeedback = RecordingHapticFeedback()
        var connectClicks = 0
        var scanQrClicks = 0

        compose.setContent {
            CompositionLocalProvider(LocalHapticFeedback provides hapticFeedback) {
                MaterialTheme {
                    ConnectionStatusScreen(
                        state = RuntimeUiState(
                            trustedRuntime = RuntimeTrustedRuntime(
                                deviceId = "runtime-1",
                                name = "AetherLink Runtime",
                                relayHost = "relay.example.test",
                                relayPort = 443,
                                relayId = "relay-1",
                                relayExpiresAtEpochMillis = Long.MAX_VALUE,
                                relayNonce = "nonce-1",
                            ),
                            backendAvailable = true,
                        ),
                        onConnect = { connectClicks += 1 },
                        onRefreshHealth = {},
                        onDisconnect = {},
                        onScanLatestQr = { scanQrClicks += 1 },
                    )
                }
            }
        }

        compose.onNode(hasStateDescription("Refresh needed") and hasClickAction(), useUnmergedTree = true)
            .performScrollTo()
            .performClick()

        assertEquals(0, connectClicks)
        assertEquals(1, scanQrClicks)
        assertEquals(listOf(HapticFeedbackType.TextHandleMove), hapticFeedback.events)
    }

    @Test
    fun settingsExpiredRelayRoutePrimaryActionScansLatestQrWithHaptic() {
        val hapticFeedback = RecordingHapticFeedback()
        var connectClicks = 0
        var scanQrClicks = 0

        compose.setContent {
            CompositionLocalProvider(LocalHapticFeedback provides hapticFeedback) {
                MaterialTheme {
                    SettingsScreen(
                        state = RuntimeUiState(
                            trustedRuntime = RuntimeTrustedRuntime(
                                deviceId = "runtime-1",
                                name = "AetherLink Runtime",
                                relayHost = "relay.example.test",
                                relayPort = 443,
                                relayId = "relay-1",
                                relaySecret = "secret-1",
                                relayExpiresAtEpochMillis = 1L,
                                relayNonce = "nonce-1",
                            ),
                            backendAvailable = true,
                        ),
                        onHostChange = {},
                        onPortChange = {},
                        onUseUsbReverse = {},
                        onUseEmulator = {},
                        onStartDiscovery = {},
                        onStopDiscovery = {},
                        onUseDiscoveredRuntime = {},
                        onForgetTrustedRuntime = {},
                        onScanPairingQr = { scanQrClicks += 1 },
                        onSubmitPairingPayload = {},
                        onConnect = { connectClicks += 1 },
                        onRefreshHealth = {},
                        onRequestModels = {},
                        onDisconnect = {},
                        onSetAutoReconnectEnabled = {},
                        onSetLanguageTag = {},
                        onSetTheme = {},
                        onSelectEmbeddingModel = {},
                        onAddMemoryEntry = {},
                        onRemoveMemoryEntry = {},
                        onSetMemoryEntryEnabled = { _, _ -> },
                        onArchiveChatSession = {},
                        onRestoreChatSession = {},
                        onPermanentlyDeleteChatSession = {},
                        onArchiveAllChatSessions = {},
                        onPermanentlyDeleteArchivedChatSessions = {},
                        showDeveloperDiagnostics = false,
                    )
                }
            }
        }

        compose.onNodeWithText("Refresh needed")
            .performScrollTo()
            .assertIsDisplayed()
        compose.onAllNodesWithText("Scan latest QR")
            .onLast()
            .performScrollTo()
            .performClick()

        assertEquals(0, connectClicks)
        assertEquals(1, scanQrClicks)
        assertEquals(listOf(HapticFeedbackType.TextHandleMove), hapticFeedback.events)
    }

    @Test
    fun settingsConnectedTrustedRuntimeDoesNotExposePairingConnectButton() {
        var connectClicks = 0
        var refreshClicks = 0
        var disconnectClicks = 0

        compose.setContent {
            MaterialTheme {
                SettingsScreen(
                    state = RuntimeUiState(
                        isConnected = true,
                        runtimeStatus = "authenticated",
                        trustedRuntime = RuntimeTrustedRuntime(
                            deviceId = "runtime-1",
                            name = "AetherLink Runtime",
                        ),
                        backendAvailable = true,
                    ),
                    onHostChange = {},
                    onPortChange = {},
                    onUseUsbReverse = {},
                    onUseEmulator = {},
                    onStartDiscovery = {},
                    onStopDiscovery = {},
                    onUseDiscoveredRuntime = {},
                    onForgetTrustedRuntime = {},
                    onScanPairingQr = {},
                    onSubmitPairingPayload = {},
                    onConnect = { connectClicks += 1 },
                    onRefreshHealth = { refreshClicks += 1 },
                    onRequestModels = {},
                    onDisconnect = { disconnectClicks += 1 },
                    onSetAutoReconnectEnabled = {},
                    onSetLanguageTag = {},
                    onSetTheme = {},
                    onSelectEmbeddingModel = {},
                    onAddMemoryEntry = {},
                    onRemoveMemoryEntry = {},
                    onSetMemoryEntryEnabled = { _, _ -> },
                    onArchiveChatSession = {},
                    onRestoreChatSession = {},
                    onPermanentlyDeleteChatSession = {},
                    onArchiveAllChatSessions = {},
                    onPermanentlyDeleteArchivedChatSessions = {},
                    showDeveloperDiagnostics = false,
                )
            }
        }

        compose.onNode(hasText("Pairing & Connection") and hasStateDescription("Collapsed"))
            .assertIsDisplayed()
            .performClick()

        compose.onNodeWithText("Refresh health")
            .performScrollTo()
            .assertIsDisplayed()
            .performClick()
        compose.onNodeWithText("Disconnect")
            .performScrollTo()
            .assertIsDisplayed()
            .performClick()

        compose.onAllNodesWithText("Connect").assertCountEquals(0)
        assertEquals(0, connectClicks)
        assertEquals(1, refreshClicks)
        assertEquals(1, disconnectClicks)
    }

    @Test
    fun settingsScreenHidesDiagnosticEndpointControlsByDefault() {
        compose.setContent {
            MaterialTheme {
                SettingsScreen(
                    state = RuntimeUiState(),
                    onHostChange = {},
                    onPortChange = {},
                    onUseUsbReverse = {},
                    onUseEmulator = {},
                    onStartDiscovery = {},
                    onStopDiscovery = {},
                    onUseDiscoveredRuntime = {},
                    onForgetTrustedRuntime = {},
                    onScanPairingQr = {},
                    onSubmitPairingPayload = {},
                    onConnect = {},
                    onRefreshHealth = {},
                    onRequestModels = {},
                    onDisconnect = {},
                    onSetAutoReconnectEnabled = {},
                    onSetLanguageTag = {},
                    onSetTheme = {},
                    onSelectEmbeddingModel = {},
                    onAddMemoryEntry = {},
                    onRemoveMemoryEntry = {},
                    onSetMemoryEntryEnabled = { _, _ -> },
                    onArchiveChatSession = {},
                    onRestoreChatSession = {},
                    onPermanentlyDeleteChatSession = {},
                    onArchiveAllChatSessions = {},
                    onPermanentlyDeleteArchivedChatSessions = {},
                    showDeveloperDiagnostics = false,
                )
            }
        }

        compose.onNodeWithText("Pair AetherLink").assertIsDisplayed()
        assertNoVisibleText("Troubleshooting")
        assertNoVisibleText("Connection troubleshooting")
        assertNoVisibleText("Diagnostic QR text")
        assertNoVisibleText("Enter QR text")
        assertNoVisibleText("USB connection")
        assertNoVisibleText("Emulator connection")
        assertNoVisibleText("Connection address")
        assertNoVisibleText("Connection port")
    }

    @Test
    fun settingsScreenKeepsEndpointInputsBehindDeveloperDiagnosticsSwitch() {
        compose.setContent {
            MaterialTheme {
                SettingsScreen(
                    state = RuntimeUiState(),
                    onHostChange = {},
                    onPortChange = {},
                    onUseUsbReverse = {},
                    onUseEmulator = {},
                    onStartDiscovery = {},
                    onStopDiscovery = {},
                    onUseDiscoveredRuntime = {},
                    onForgetTrustedRuntime = {},
                    onScanPairingQr = {},
                    onSubmitPairingPayload = {},
                    onConnect = {},
                    onRefreshHealth = {},
                    onRequestModels = {},
                    onDisconnect = {},
                    onSetAutoReconnectEnabled = {},
                    onSetLanguageTag = {},
                    onSetTheme = {},
                    onSelectEmbeddingModel = {},
                    onAddMemoryEntry = {},
                    onRemoveMemoryEntry = {},
                    onSetMemoryEntryEnabled = { _, _ -> },
                    onArchiveChatSession = {},
                    onRestoreChatSession = {},
                    onPermanentlyDeleteChatSession = {},
                    onArchiveAllChatSessions = {},
                    onPermanentlyDeleteArchivedChatSessions = {},
                    showDeveloperDiagnostics = true,
                )
            }
        }

        repeat(2) {
            compose.onRoot().performTouchInput { swipeUp() }
            compose.waitForIdle()
        }
        compose.onNodeWithText("Troubleshooting")
            .assertIsDisplayed()
            .performClick()

        compose.onNodeWithText("Connection troubleshooting").assertIsDisplayed()
        compose.onNodeWithContentDescription("Connection troubleshooting", useUnmergedTree = true)
            .assert(hasStateDescription("Off"))
        assertNoVisibleText("Diagnostic QR text")
        assertNoVisibleText("Enter QR text")
        assertNoVisibleText("USB connection")
        assertNoVisibleText("Emulator connection")
        assertNoVisibleText("Connection address")
        assertNoVisibleText("Connection port")

        compose.onNodeWithTag(DEVELOPER_DIAGNOSTICS_TOGGLE_ROW_TAG).performClick()
        compose.waitForIdle()
        compose.onNodeWithTag(DEVELOPER_DIAGNOSTICS_SWITCH_ENABLED_TAG, useUnmergedTree = true)
            .assert(hasStateDescription("On"))
        assertNoVisibleText("Enter QR text")
        assertNoVisibleText("USB connection")
        assertNoVisibleText("Emulator connection")
        assertNoVisibleText("Connection address")
        assertNoVisibleText("Connection port")

        compose.onRoot().performTouchInput { swipeUp() }
        compose.waitForIdle()
        val endpointToggle = compose.onNode(
            hasContentDescription("Connection troubleshooting") and
                hasStateDescription("Collapsed") and
                hasClickAction(),
        )
        endpointToggle
            .assert(SemanticsMatcher.expectValue(SemanticsProperties.Role, Role.Button))
            .performClick()

        compose.waitForIdle()
        compose.onNode(
            hasContentDescription("Connection troubleshooting") and
                hasStateDescription("Expanded") and
                hasClickAction(),
        ).assert(SemanticsMatcher.expectValue(SemanticsProperties.Role, Role.Button))
        compose.onNodeWithText("USB connection").assertIsDisplayed()
        compose.onNodeWithText("Emulator connection").assertIsDisplayed()
        compose.onNodeWithText("Connection address").assertIsDisplayed()
        compose.onNodeWithText("Connection port").assertIsDisplayed()
    }

    @Test
    fun settingsAutoReconnectSwitchExposesAccessibilityState() {
        val autoReconnectEnabled = mutableStateOf(true)

        compose.setContent {
            MaterialTheme {
                SettingsScreen(
                    state = RuntimeUiState(
                        trustedRuntime = RuntimeTrustedRuntime(
                            deviceId = "runtime-1",
                            name = "AetherLink Runtime",
                        ),
                        trustedRuntimeAutoReconnectEnabled = autoReconnectEnabled.value,
                    ),
                    onHostChange = {},
                    onPortChange = {},
                    onUseUsbReverse = {},
                    onUseEmulator = {},
                    onStartDiscovery = {},
                    onStopDiscovery = {},
                    onUseDiscoveredRuntime = {},
                    onForgetTrustedRuntime = {},
                    onScanPairingQr = {},
                    onSubmitPairingPayload = {},
                    onConnect = {},
                    onRefreshHealth = {},
                    onRequestModels = {},
                    onDisconnect = {},
                    onSetAutoReconnectEnabled = {},
                    onSetLanguageTag = {},
                    onSetTheme = {},
                    onSelectEmbeddingModel = {},
                    onAddMemoryEntry = {},
                    onRemoveMemoryEntry = {},
                    onSetMemoryEntryEnabled = { _, _ -> },
                    onArchiveChatSession = {},
                    onRestoreChatSession = {},
                    onPermanentlyDeleteChatSession = {},
                    onArchiveAllChatSessions = {},
                    onPermanentlyDeleteArchivedChatSessions = {},
                    showDeveloperDiagnostics = false,
                )
            }
        }

        compose.onNodeWithContentDescription("Auto reconnect", useUnmergedTree = true)
            .assert(hasStateDescription("On"))

        autoReconnectEnabled.value = false
        compose.waitForIdle()
        compose.onNodeWithContentDescription("Auto reconnect", useUnmergedTree = true)
            .assert(hasStateDescription("Off"))
    }

    @Test
    fun settingsDiscoveredRuntimeActionsUseContextualAccessibilityLabels() {
        val trustedRuntime = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            routeToken = "route-token-1",
        )
        val discoveredRuntime = RuntimeDiscoveredRuntime(
            serviceName = "Studio Runtime",
            host = "192.0.2.10",
            port = 43170,
            routeToken = "route-token-1",
            deviceId = "runtime-1",
        )
        var selectedRuntime: RuntimeDiscoveredRuntime? = null

        compose.setContent {
            MaterialTheme {
                SettingsScreen(
                    state = RuntimeUiState(
                        trustedRuntime = trustedRuntime,
                        discoveredRuntimes = listOf(discoveredRuntime),
                    ),
                    onHostChange = {},
                    onPortChange = {},
                    onUseUsbReverse = {},
                    onUseEmulator = {},
                    onStartDiscovery = {},
                    onStopDiscovery = {},
                    onUseDiscoveredRuntime = { selectedRuntime = it },
                    onForgetTrustedRuntime = {},
                    onScanPairingQr = {},
                    onSubmitPairingPayload = {},
                    onConnect = {},
                    onRefreshHealth = {},
                    onRequestModels = {},
                    onDisconnect = {},
                    onSetAutoReconnectEnabled = {},
                    onSetLanguageTag = {},
                    onSetTheme = {},
                    onSelectEmbeddingModel = {},
                    onAddMemoryEntry = {},
                    onRemoveMemoryEntry = {},
                    onSetMemoryEntryEnabled = { _, _ -> },
                    onArchiveChatSession = {},
                    onRestoreChatSession = {},
                    onPermanentlyDeleteChatSession = {},
                    onArchiveAllChatSessions = {},
                    onPermanentlyDeleteArchivedChatSessions = {},
                    showDeveloperDiagnostics = true,
                )
            }
        }

        scrollUntilTextIsVisible("Troubleshooting")
        compose.onNodeWithText("Troubleshooting")
            .assertIsDisplayed()
            .performClick()
        scrollUntilTextIsVisible("Studio Runtime")

        compose.onNodeWithContentDescription(
            "Use trusted connection for Studio Runtime",
            useUnmergedTree = true,
        )
            .assertIsDisplayed()
            .performClick()

        assertEquals(discoveredRuntime, selectedRuntime)
    }

    @Test
    fun settingsScreenKeepsBulkChatHistoryActionsHiddenAndTwoStepConfirmed() {
        val hapticFeedback = RecordingHapticFeedback()
        var archiveAllClicks = 0
        var deleteArchivedClicks = 0
        var archiveChatClicks = 0
        var deleteChatClicks = 0

        compose.setContent {
            MaterialTheme {
                CompositionLocalProvider(LocalHapticFeedback provides hapticFeedback) {
                    SettingsScreen(
                        state = RuntimeUiState(
                            chatSessions = listOf(
                                RuntimeChatSession(
                                    id = "active-chat",
                                    title = "Active project chat",
                                    messageCount = 1,
                                    updatedAtMillis = 2_000L,
                                ),
                            ),
                            archivedChatSessions = listOf(
                                RuntimeChatSession(
                                    id = "archived-chat",
                                    title = "Archived project chat",
                                    messageCount = 6,
                                    archivedAtMillis = 3_000L,
                                    updatedAtMillis = 3_000L,
                                ),
                            ),
                        ),
                        onHostChange = {},
                        onPortChange = {},
                        onUseUsbReverse = {},
                        onUseEmulator = {},
                        onStartDiscovery = {},
                        onStopDiscovery = {},
                        onUseDiscoveredRuntime = {},
                        onForgetTrustedRuntime = {},
                        onScanPairingQr = {},
                        onSubmitPairingPayload = {},
                        onConnect = {},
                        onRefreshHealth = {},
                        onRequestModels = {},
                        onDisconnect = {},
                        onSetAutoReconnectEnabled = {},
                        onSetLanguageTag = {},
                        onSetTheme = {},
                        onSelectEmbeddingModel = {},
                        onAddMemoryEntry = {},
                        onRemoveMemoryEntry = {},
                        onSetMemoryEntryEnabled = { _, _ -> },
                        onArchiveChatSession = { archiveChatClicks += 1 },
                        onRestoreChatSession = {},
                        onPermanentlyDeleteChatSession = { deleteChatClicks += 1 },
                        onArchiveAllChatSessions = { archiveAllClicks += 1 },
                        onPermanentlyDeleteArchivedChatSessions = { deleteArchivedClicks += 1 },
                        showDeveloperDiagnostics = false,
                    )
                }
            }
        }

        assertNoVisibleText("Manage all chats")
        assertNoVisibleText("Archive all chats")
        assertNoVisibleText("Permanently delete archived chats")

        scrollUntilTextIsVisible("Chat history")
        compose.onNodeWithText("Chat history")
            .assertIsDisplayed()
            .performClick()
        compose.waitForIdle()
        compose.onNodeWithText("1 message", useUnmergedTree = true).assertExists()
        compose.onNodeWithContentDescription("Archive chat Active project chat", useUnmergedTree = true)
            .performScrollTo()
            .assertIsDisplayed()
        compose.onNodeWithContentDescription("Restore chat Archived project chat", useUnmergedTree = true)
            .performScrollTo()
            .assertIsDisplayed()
        compose.onNodeWithContentDescription("Permanently delete chat Archived project chat", useUnmergedTree = true)
            .performScrollTo()
            .assertIsDisplayed()
        scrollUntilTextIsVisible("Manage all chats")

        compose.onNode(hasText("Manage all chats") and hasStateDescription("Collapsed"))
            .performScrollTo()
            .assertIsDisplayed()
        assertNoVisibleText("Archive all chats")
        assertNoVisibleText("Permanently delete archived chats")

        compose.onNode(hasText("Manage all chats") and hasStateDescription("Collapsed"))
            .performClick()
        compose.waitForIdle()
        scrollUntilTextIsVisible("Archive all chats")
        compose.onNode(hasText("Manage all chats") and hasStateDescription("Expanded"))
            .assertIsDisplayed()
        hapticFeedback.events.clear()

        compose.onNodeWithText("Archive all chats")
            .performScrollTo()
            .assertIsDisplayed()
        compose.onNodeWithText("Permanently delete archived chats")
            .performScrollTo()
            .assertIsDisplayed()

        compose.onNodeWithText("Archive all chats").performClick()
        compose.onNodeWithText(
            "Archive all active chats? They stay saved, leave the main list, and stop contributing to Memory.",
        ).assertIsDisplayed()
        assertEquals(listOf(HapticFeedbackType.TextHandleMove), hapticFeedback.events)
        compose.onNodeWithText("Continue").performClick()
        compose.waitForIdle()
        assertEquals(
            listOf(HapticFeedbackType.TextHandleMove, HapticFeedbackType.TextHandleMove),
            hapticFeedback.events,
        )
        compose.onNodeWithText("Confirm again to archive every active chat. Archived chats can be restored later.")
            .assertIsDisplayed()
        compose.onNodeWithText("Archive").performClick()
        assertEquals(
            listOf(
                HapticFeedbackType.TextHandleMove,
                HapticFeedbackType.TextHandleMove,
                HapticFeedbackType.LongPress,
            ),
            hapticFeedback.events,
        )

        assertEquals(1, archiveAllClicks)
        assertEquals(0, deleteArchivedClicks)
        hapticFeedback.events.clear()

        compose.onNodeWithText("Permanently delete archived chats")
            .performScrollTo()
            .performClick()
        compose.onNodeWithText("Permanently delete all archived chats? Active chats stay saved.")
            .assertIsDisplayed()
        assertEquals(listOf(HapticFeedbackType.TextHandleMove), hapticFeedback.events)
        compose.onNodeWithText("Continue").performClick()
        assertEquals(
            listOf(HapticFeedbackType.TextHandleMove, HapticFeedbackType.TextHandleMove),
            hapticFeedback.events,
        )
        compose.onNodeWithText("Confirm permanent deletion of every archived chat. This cannot be undone.")
            .assertIsDisplayed()
        compose.onAllNodesWithText("Permanently delete").onLast().performClick()
        assertEquals(
            listOf(
                HapticFeedbackType.TextHandleMove,
                HapticFeedbackType.TextHandleMove,
                HapticFeedbackType.LongPress,
            ),
            hapticFeedback.events,
        )

        assertEquals(1, archiveAllClicks)
        assertEquals(1, deleteArchivedClicks)
        assertEquals(0, archiveChatClicks)
        assertEquals(0, deleteChatClicks)
    }

    @Test
    fun settingsScreenPerChatHistoryActionsUseConfirmationHaptics() {
        val hapticFeedback = RecordingHapticFeedback()
        var archiveChatClicks = 0
        var deleteChatClicks = 0

        compose.setContent {
            MaterialTheme {
                CompositionLocalProvider(LocalHapticFeedback provides hapticFeedback) {
                    SettingsScreen(
                        state = RuntimeUiState(
                            chatSessions = listOf(
                                RuntimeChatSession(
                                    id = "active-chat",
                                    title = "Active project chat",
                                    messageCount = 1,
                                    updatedAtMillis = 2_000L,
                                ),
                            ),
                            archivedChatSessions = listOf(
                                RuntimeChatSession(
                                    id = "archived-chat",
                                    title = "Archived project chat",
                                    messageCount = 6,
                                    archivedAtMillis = 3_000L,
                                    updatedAtMillis = 3_000L,
                                ),
                            ),
                        ),
                        onHostChange = {},
                        onPortChange = {},
                        onUseUsbReverse = {},
                        onUseEmulator = {},
                        onStartDiscovery = {},
                        onStopDiscovery = {},
                        onUseDiscoveredRuntime = {},
                        onForgetTrustedRuntime = {},
                        onScanPairingQr = {},
                        onSubmitPairingPayload = {},
                        onConnect = {},
                        onRefreshHealth = {},
                        onRequestModels = {},
                        onDisconnect = {},
                        onSetAutoReconnectEnabled = {},
                        onSetLanguageTag = {},
                        onSetTheme = {},
                        onSelectEmbeddingModel = {},
                        onAddMemoryEntry = {},
                        onRemoveMemoryEntry = {},
                        onSetMemoryEntryEnabled = { _, _ -> },
                        onArchiveChatSession = { archiveChatClicks += 1 },
                        onRestoreChatSession = {},
                        onPermanentlyDeleteChatSession = { deleteChatClicks += 1 },
                        onArchiveAllChatSessions = {},
                        onPermanentlyDeleteArchivedChatSessions = {},
                        showDeveloperDiagnostics = false,
                    )
                }
            }
        }

        scrollUntilTextIsVisible("Chat history")
        compose.onNodeWithText("Chat history")
            .assertIsDisplayed()
            .performClick()
        compose.waitForIdle()
        hapticFeedback.events.clear()

        compose.onNodeWithContentDescription("Archive chat Active project chat", useUnmergedTree = true)
            .performScrollTo()
            .performClick()
        assertEquals(1, archiveChatClicks)
        assertEquals(listOf(HapticFeedbackType.TextHandleMove), hapticFeedback.events)
        hapticFeedback.events.clear()

        compose.onNodeWithContentDescription("Permanently delete chat Archived project chat", useUnmergedTree = true)
            .performScrollTo()
            .performClick()
        compose.onNodeWithText("Permanently delete chat").assertExists()
        assertEquals(listOf(HapticFeedbackType.TextHandleMove), hapticFeedback.events)
        compose.onNodeWithText("Continue").performClick()
        compose.waitForIdle()
        assertEquals(
            listOf(HapticFeedbackType.TextHandleMove, HapticFeedbackType.TextHandleMove),
            hapticFeedback.events,
        )
        compose.onAllNodesWithText("Permanently delete").onLast().performClick()

        assertEquals(1, deleteChatClicks)
        assertEquals(
            listOf(
                HapticFeedbackType.TextHandleMove,
                HapticFeedbackType.TextHandleMove,
                HapticFeedbackType.LongPress,
            ),
            hapticFeedback.events,
        )
    }

    @Test
    fun chatDrawerItemsShowRuntimeProcessingStatus() {
        compose.setContent {
            MaterialTheme {
                Column {
                    ChatSessionDrawerItem(
                        session = RuntimeChatSession(
                            id = "failed-chat",
                            title = "Trip plan",
                            updatedAtMillis = 2_000L,
                            messageCount = 3,
                            lastEvent = "chat.error",
                            lastErrorCode = "backend_unavailable",
                        ),
                        selected = false,
                        enabled = true,
                        onClick = {},
                        onRename = null,
                        onArchive = null,
                        onRestore = null,
                        onDelete = null,
                    )
                    ChatSessionDrawerItem(
                        session = RuntimeChatSession(
                            id = "active-chat",
                            title = "Connection notes",
                            updatedAtMillis = 3_000L,
                            messageCount = 2,
                            lastEvent = "chat.delta",
                        ),
                        selected = false,
                        enabled = true,
                        onClick = {},
                        onRename = null,
                        onArchive = null,
                        onRestore = null,
                        onDelete = null,
                    )
                    ChatSessionDrawerItem(
                        session = RuntimeChatSession(
                            id = "single-message-chat",
                            title = "One note",
                            updatedAtMillis = 4_000L,
                            messageCount = 1,
                        ),
                        selected = true,
                        enabled = true,
                        onClick = {},
                        onRename = null,
                        onArchive = null,
                        onRestore = null,
                        onDelete = null,
                    )
                }
            }
        }

        compose.onNodeWithText("Trip plan").assertIsDisplayed()
        compose.onNodeWithText("3 messages - Needs attention").assertIsDisplayed()
        compose.onNodeWithContentDescription("Chat Trip plan. 3 messages - Needs attention.")
            .assertIsDisplayed()
        compose.onNodeWithContentDescription("Chat options for Trip plan", useUnmergedTree = true)
            .assertIsDisplayed()
        compose.onNodeWithText("Connection notes").assertIsDisplayed()
        compose.onNodeWithText("2 messages - In progress").assertIsDisplayed()
        compose.onNodeWithContentDescription("Chat Connection notes. 2 messages - In progress.")
            .assertIsDisplayed()
        compose.onNodeWithContentDescription("Chat options for Connection notes", useUnmergedTree = true)
            .assertIsDisplayed()
        compose.onNodeWithText("One note").assertIsDisplayed()
        compose.onNodeWithText("1 message").assertIsDisplayed()
        compose.onNodeWithContentDescription("Selected chat One note. 1 message.")
            .assertIsDisplayed()
        compose.onNodeWithContentDescription("Chat options for One note", useUnmergedTree = true)
            .assertIsDisplayed()
    }

    @Test
    fun chatScreenAcceptsInputAndSendWhenConnectedModelIsReady() {
        var sendClicks = 0
        var attachmentClicks = 0
        val hapticFeedback = RecordingHapticFeedback()
        val chatModel = RuntimeModel(
            id = "ollama:llama3.1:8b",
            name = "Llama 3.1 8B",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = true,
            source = "local",
        )
        val state = mutableStateOf(
            RuntimeUiState(
                isConnected = true,
                runtimeStatus = "authenticated",
                trustedRuntime = RuntimeTrustedRuntime(
                    deviceId = "runtime-1",
                    name = "AetherLink Runtime",
                ),
                backendAvailable = true,
                selectedModelId = chatModel.id,
                models = listOf(chatModel),
                selectedTheme = RuntimeAppTheme.System,
            )
        )

        compose.setContent {
            CompositionLocalProvider(LocalHapticFeedback provides hapticFeedback) {
                MaterialTheme {
                    ChatScreen(
                        state = state.value,
                        onInputChange = { text -> state.value = state.value.copy(chatInput = text) },
                        onSend = { sendClicks += 1 },
                        onCancel = {},
                        onConnect = {},
                        onScanPairingQr = {},
                        onRefreshHealth = {},
                        onAttachFiles = { attachmentClicks += 1 },
                        onRemoveAttachment = {},
                        onSuggestionClick = {},
                        onScanLatestQr = {},
                    )
                }
            }
        }

        compose.onNodeWithContentDescription("Message")
            .assertIsDisplayed()
            .performTextInput("Hello")
        compose.onNode(hasContentDescription("Attach files") and hasStateDescription("Ready to attach files."))
            .assertIsDisplayed()
            .assertIsEnabled()
            .performClick()
        compose.onNodeWithContentDescription("Send message")
            .assertIsEnabled()
            .performClick()

        assertEquals("Hello", state.value.chatInput)
        assertEquals(1, attachmentClicks)
        assertEquals(1, sendClicks)
        assertEquals(
            listOf(HapticFeedbackType.TextHandleMove, HapticFeedbackType.TextHandleMove),
            hapticFeedback.events,
        )
    }

    @Test
    fun chatScreenUntrustedRuntimeShowsQrFirstPairingCallToAction() {
        var scanQrClicks = 0
        var connectClicks = 0

        compose.setContent {
            MaterialTheme {
                ChatScreen(
                    state = RuntimeUiState(),
                    onInputChange = {},
                    onSend = {},
                    onCancel = {},
                    onConnect = { connectClicks += 1 },
                    onScanPairingQr = { scanQrClicks += 1 },
                    onRefreshHealth = {},
                    onAttachFiles = {},
                    onRemoveAttachment = {},
                    onSuggestionClick = {},
                    onScanLatestQr = {},
                )
            }
        }

        compose.onNodeWithText("Scan QR to start").assertIsDisplayed()
        compose
            .onNodeWithText("Pair with AetherLink Runtime first. Model providers stay private behind the trusted runtime.")
            .assertIsDisplayed()
        compose.onNodeWithContentDescription("Message").assertIsNotEnabled()
        compose.onNodeWithContentDescription("Attach files").assertIsNotEnabled()
        compose.onNodeWithText("Scan QR").assertIsDisplayed().performClick()

        assertEquals(1, scanQrClicks)
        assertEquals(0, connectClicks)
        assertNoVisibleText("Connect to continue")
        assertNoVisibleText("Connect to the trusted runtime before chatting.")
        assertNoVisibleText("Scan latest QR")
        assertNoVisibleText("Connection address")
    }

    @Test
    fun chatScreenUntrustedRuntimeUsesLocalizedQrFirstCopy() {
        val localizedQrFirstCopy = listOf(
            Triple("en", "Scan QR to start", "Scan QR"),
            Triple("ko", "QR 스캔으로 시작", "QR 스캔"),
            Triple("ja", "QR スキャンで開始", "QR をスキャン"),
            Triple("zh-Hans", "扫描 QR 开始", "扫描 QR"),
            Triple("fr", "Scannez le QR pour démarrer", "Scanner le QR"),
        )
        val language = mutableStateOf(localizedQrFirstCopy.first())

        compose.setContent {
            MaterialTheme {
                val (languageTag, _, _) = language.value
                LocalizedTestContent(languageTag = languageTag) {
                    ChatScreen(
                        state = RuntimeUiState(selectedLanguageTag = languageTag),
                        onInputChange = {},
                        onSend = {},
                        onCancel = {},
                        onConnect = {},
                        onScanPairingQr = {},
                        onRefreshHealth = {},
                        onAttachFiles = {},
                        onRemoveAttachment = {},
                        onSuggestionClick = {},
                        onScanLatestQr = {},
                    )
                }
            }
        }

        localizedQrFirstCopy.forEach { expectedCopy ->
            compose.runOnUiThread {
                language.value = expectedCopy
            }
            compose.waitForIdle()
            compose.onNodeWithText(expectedCopy.second).assertIsDisplayed()
            compose.onNodeWithText(expectedCopy.third).assertIsDisplayed()
        }
    }

    @Test
    fun chatScreenShowsComposerReadinessHintWhenPreviousChatCannotSend() {
        var attachmentClicks = 0
        val chatModel = RuntimeModel(
            id = "ollama:qwen3:8b",
            name = "Qwen3 8B",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = true,
            source = "local",
        )

        compose.setContent {
            MaterialTheme {
                ChatScreen(
                    state = RuntimeUiState(
                        isConnected = true,
                        runtimeStatus = "authenticated",
                        trustedRuntime = RuntimeTrustedRuntime(
                            deviceId = "runtime-1",
                            name = "AetherLink Runtime",
                        ),
                        backendAvailable = true,
                        selectedModelId = null,
                        models = listOf(chatModel),
                        messages = listOf(
                            RuntimeChatMessage(
                                id = "user-1",
                                role = "user",
                                content = "Summarize the route status.",
                            ),
                            RuntimeChatMessage(
                                id = "assistant-1",
                                role = "assistant",
                                content = "The runtime route needs a selected model before continuing.",
                            ),
                        ),
                    ),
                    onInputChange = {},
                    onSend = {},
                    onCancel = {},
                    onConnect = {},
                    onScanPairingQr = {},
                    onRefreshHealth = {},
                    onAttachFiles = { attachmentClicks += 1 },
                    onRemoveAttachment = {},
                    onSuggestionClick = {},
                    onScanLatestQr = {},
                )
            }
        }

        compose.onNodeWithText("The runtime route needs a selected model before continuing.").assertIsDisplayed()
        compose.onNodeWithText("Select a model before sending.").assertIsDisplayed()
        compose.onNodeWithContentDescription("Message").assertIsNotEnabled()
        compose.onNodeWithContentDescription("Attach files")
            .assert(hasStateDescription("Select a model before sending."))
            .assertIsNotEnabled()
        compose.onNodeWithContentDescription("Send message").assertIsNotEnabled()

        assertEquals(0, attachmentClicks)
    }

    @Test
    fun chatScreenStreamingShowsCancelActionInsteadOfSend() {
        var sendClicks = 0
        var cancelClicks = 0
        var attachmentClicks = 0
        val hapticFeedback = RecordingHapticFeedback()
        val chatModel = RuntimeModel(
            id = "ollama:qwen3:8b",
            name = "Qwen3 8B",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = true,
            source = "local",
        )

        compose.setContent {
            CompositionLocalProvider(LocalHapticFeedback provides hapticFeedback) {
                MaterialTheme {
                    ChatScreen(
                        state = RuntimeUiState(
                            isConnected = true,
                            runtimeStatus = "authenticated",
                            trustedRuntime = RuntimeTrustedRuntime(
                                deviceId = "runtime-1",
                                name = "AetherLink Runtime",
                            ),
                            backendAvailable = true,
                            selectedModelId = chatModel.id,
                            models = listOf(chatModel),
                            isStreaming = true,
                            messages = listOf(
                                RuntimeChatMessage(
                                    id = "assistant-streaming",
                                    role = "assistant",
                                    content = "Streaming response",
                                ),
                            ),
                        ),
                        onInputChange = {},
                        onSend = { sendClicks += 1 },
                        onCancel = { cancelClicks += 1 },
                        onConnect = {},
                        onScanPairingQr = {},
                        onRefreshHealth = {},
                        onAttachFiles = { attachmentClicks += 1 },
                        onRemoveAttachment = {},
                        onSuggestionClick = {},
                        onScanLatestQr = {},
                    )
                }
            }
        }

        compose.onNodeWithContentDescription("Message").assertIsNotEnabled()
        compose.onNodeWithContentDescription("Attach files")
            .assert(hasStateDescription("Wait for the current response or cancel it."))
            .assertIsNotEnabled()
        compose.onAllNodesWithContentDescription("Send message").assertCountEquals(0)
        compose.onNodeWithContentDescription("Cancel generation")
            .assertIsDisplayed()
            .assertIsEnabled()
            .performClick()

        assertEquals(0, sendClicks)
        assertEquals(0, attachmentClicks)
        assertEquals(1, cancelClicks)
        assertEquals(listOf(HapticFeedbackType.LongPress), hapticFeedback.events)
    }

    @Test
    fun chatScreenAttachmentChipsExposeFileStateToAccessibility() {
        val chatModel = RuntimeModel(
            id = "ollama:qwen3:8b",
            name = "Qwen3 8B",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = true,
            source = "local",
        )
        val documentAttachment = RuntimePendingAttachment(
            id = "attachment-document",
            type = "document",
            name = "brief.pdf",
            mimeType = "application/pdf",
            sizeBytes = 0L,
            dataBase64 = "ZmlsZQ==",
        )
        val imageAttachment = RuntimePendingAttachment(
            id = "attachment-image",
            type = "image",
            name = "diagram.png",
            mimeType = "image/png",
            sizeBytes = 0L,
            dataBase64 = "aW1hZ2U=",
        )

        compose.setContent {
            MaterialTheme {
                ChatScreen(
                    state = RuntimeUiState(
                        isConnected = true,
                        runtimeStatus = "authenticated",
                        trustedRuntime = RuntimeTrustedRuntime(
                            deviceId = "runtime-1",
                            name = "AetherLink Runtime",
                        ),
                        backendAvailable = true,
                        selectedModelId = chatModel.id,
                        models = listOf(chatModel),
                        pendingAttachments = listOf(documentAttachment, imageAttachment),
                    ),
                    onInputChange = {},
                    onSend = {},
                    onCancel = {},
                    onConnect = {},
                    onScanPairingQr = {},
                    onRefreshHealth = {},
                    onAttachFiles = {},
                    onRemoveAttachment = {},
                    onSuggestionClick = {},
                    onScanLatestQr = {},
                )
            }
        }

        compose.onNodeWithContentDescription("Attachment brief.pdf, Document", useUnmergedTree = true)
            .assert(hasStateDescription("Document"))
            .assertIsDisplayed()
        compose.onNodeWithContentDescription("Attachment diagram.png, Vision model required", useUnmergedTree = true)
            .assert(hasStateDescription("Vision model required"))
            .assertIsDisplayed()
        compose.onNodeWithContentDescription("Remove attachment brief.pdf", useUnmergedTree = true)
            .assertIsDisplayed()
        compose.onNodeWithContentDescription("Remove attachment diagram.png", useUnmergedTree = true)
            .assertIsDisplayed()
    }

    @Test
    fun chatScreenAttachmentSizeUsesSelectedAppLanguageContext() {
        val languageTag = "fr"
        val localizedContext = ApplicationProvider
            .getApplicationContext<Context>()
            .localizedContext(languageTag)
        val chatModel = RuntimeModel(
            id = "ollama:qwen3:8b",
            name = "Qwen3 8B",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = true,
            source = "local",
        )
        val attachment = RuntimePendingAttachment(
            id = "attachment-document",
            type = "document",
            name = "brief.pdf",
            mimeType = "application/pdf",
            sizeBytes = 1_536L,
            dataBase64 = "ZmlsZQ==",
        )
        val expectedMetadata = localizedContext.getString(
            R.string.attachment_metadata_with_size,
            localizedContext.getString(R.string.attachment_type_document),
            Formatter.formatFileSize(localizedContext, attachment.sizeBytes),
        )
        val expectedContentDescription = localizedContext.getString(
            R.string.content_desc_attachment_chip,
            attachment.name,
            expectedMetadata,
        )

        compose.setContent {
            MaterialTheme {
                LocalizedTestContent(languageTag = languageTag) {
                    ChatScreen(
                        state = RuntimeUiState(
                            isConnected = true,
                            runtimeStatus = "authenticated",
                            trustedRuntime = RuntimeTrustedRuntime(
                                deviceId = "runtime-1",
                                name = "AetherLink Runtime",
                            ),
                            backendAvailable = true,
                            selectedModelId = chatModel.id,
                            models = listOf(chatModel),
                            pendingAttachments = listOf(attachment),
                        ),
                        onInputChange = {},
                        onSend = {},
                        onCancel = {},
                        onConnect = {},
                        onScanPairingQr = {},
                        onRefreshHealth = {},
                        onAttachFiles = {},
                        onRemoveAttachment = {},
                        onSuggestionClick = {},
                        onScanLatestQr = {},
                    )
                }
            }
        }

        compose.onNodeWithText(expectedMetadata).assertIsDisplayed()
        compose.onNodeWithContentDescription(expectedContentDescription, useUnmergedTree = true)
            .assert(hasStateDescription(expectedMetadata))
            .assertIsDisplayed()
    }

    @Test
    fun chatScreenMessageAttachmentChipsExposeFileStateToAccessibility() {
        val chatModel = RuntimeModel(
            id = "ollama:qwen3:8b",
            name = "Qwen3 8B",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = true,
            source = "local",
        )

        compose.setContent {
            MaterialTheme {
                ChatScreen(
                    state = RuntimeUiState(
                        isConnected = true,
                        runtimeStatus = "authenticated",
                        trustedRuntime = RuntimeTrustedRuntime(
                            deviceId = "runtime-1",
                            name = "AetherLink Runtime",
                        ),
                        backendAvailable = true,
                        selectedModelId = chatModel.id,
                        models = listOf(chatModel),
                        messages = listOf(
                            RuntimeChatMessage(
                                id = "user-with-attachments",
                                role = "user",
                                content = "Review these files.",
                                attachments = listOf(
                                    RuntimeMessageAttachment(
                                        id = "document-1",
                                        type = "document",
                                        name = "brief.pdf",
                                        mimeType = "application/pdf",
                                    ),
                                    RuntimeMessageAttachment(
                                        id = "image-1",
                                        type = "image",
                                        name = "diagram.png",
                                        mimeType = "image/png",
                                    ),
                                ),
                            ),
                        ),
                    ),
                    onInputChange = {},
                    onSend = {},
                    onCancel = {},
                    onConnect = {},
                    onScanPairingQr = {},
                    onRefreshHealth = {},
                    onAttachFiles = {},
                    onRemoveAttachment = {},
                    onSuggestionClick = {},
                    onScanLatestQr = {},
                )
            }
        }

        compose.onNodeWithContentDescription("Attachment brief.pdf, Document", useUnmergedTree = true)
            .assert(hasStateDescription("Document"))
            .assertIsDisplayed()
        compose.onNodeWithContentDescription("Attachment diagram.png, Image", useUnmergedTree = true)
            .assert(hasStateDescription("Image"))
            .assertIsDisplayed()
    }

    @Test
    fun chatScreenRendersReasoningCollapsedAndExpandable() {
        val hapticFeedback = RecordingHapticFeedback()
        val chatModel = RuntimeModel(
            id = "ollama:reasoning",
            name = "Reasoning Model",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = true,
            source = "local",
        )
        val state = RuntimeUiState(
            isConnected = true,
            runtimeStatus = "authenticated",
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "runtime-1",
                name = "AetherLink Runtime",
            ),
            backendAvailable = true,
            selectedModelId = chatModel.id,
            models = listOf(chatModel),
            messages = listOf(
                RuntimeChatMessage(
                    id = "user-1",
                    role = "user",
                    content = "Explain the connection flow.",
                ),
                RuntimeChatMessage(
                    id = "assistant-1",
                    role = "assistant",
                    reasoning = "first step\nsecond step\nthird step\nfourth step",
                    content = "The trusted runtime mediates model access.",
                ),
            ),
            selectedTheme = RuntimeAppTheme.System,
        )

        compose.setContent {
            CompositionLocalProvider(LocalHapticFeedback provides hapticFeedback) {
                MaterialTheme {
                    ChatScreen(
                        state = state,
                        onInputChange = {},
                        onSend = {},
                        onCancel = {},
                        onConnect = {},
                        onScanPairingQr = {},
                        onRefreshHealth = {},
                        onAttachFiles = {},
                        onRemoveAttachment = {},
                        onSuggestionClick = {},
                        onScanLatestQr = {},
                    )
                }
            }
        }

        compose.onNodeWithText("Thinking").assertIsDisplayed()
        compose.onNodeWithText("first step\nsecond step\nthird step").assertIsDisplayed()
        assertEquals(0, compose.onAllNodesWithText("fourth step").fetchSemanticsNodes().size)

        compose.onNode(hasText("Thinking") and hasStateDescription("Collapsed") and hasClickAction())
            .performClick()

        compose.onNodeWithText("first step\nsecond step\nthird step\nfourth step").assertIsDisplayed()
        compose.onNodeWithText("Hide thinking").assertIsDisplayed()
        compose.onNode(hasText("Thinking") and hasStateDescription("Expanded") and hasClickAction())
            .assertIsDisplayed()
        assertEquals(listOf(HapticFeedbackType.TextHandleMove), hapticFeedback.events)
    }

    @Test
    fun chatScreenJumpToLatestAppearsAfterScrollingAwayAndReturnsToLatestMessage() {
        val hapticFeedback = RecordingHapticFeedback()
        val chatModel = RuntimeModel(
            id = "ollama:qwen3:8b",
            name = "Qwen3 8B",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = true,
            source = "local",
        )
        val messages = (1..28).map { index ->
            RuntimeChatMessage(
                id = "message-$index",
                role = if (index % 2 == 0) "assistant" else "user",
                content = "Scroll regression message $index. This row keeps enough height for the chat list.",
            )
        }

        compose.setContent {
            CompositionLocalProvider(LocalHapticFeedback provides hapticFeedback) {
                MaterialTheme {
                    ChatScreen(
                        state = RuntimeUiState(
                            isConnected = true,
                            runtimeStatus = "authenticated",
                            trustedRuntime = RuntimeTrustedRuntime(
                                deviceId = "runtime-1",
                                name = "AetherLink Runtime",
                            ),
                            backendAvailable = true,
                            selectedModelId = chatModel.id,
                            models = listOf(chatModel),
                            messages = messages,
                        ),
                        onInputChange = {},
                        onSend = {},
                        onCancel = {},
                        onConnect = {},
                        onScanPairingQr = {},
                        onRefreshHealth = {},
                        onAttachFiles = {},
                        onRemoveAttachment = {},
                        onSuggestionClick = {},
                        onScanLatestQr = {},
                    )
                }
            }
        }

        compose.waitForIdle()
        compose.onNodeWithTag(CHAT_MESSAGE_LIST_TEST_TAG)
            .performScrollToIndex(messages.lastIndex)
        compose.waitForIdle()
        compose.onNodeWithText("Scroll regression message 28. This row keeps enough height for the chat list.")
            .assertIsDisplayed()
        assertEquals(
            0,
            compose.onAllNodesWithContentDescription("Jump to latest message")
                .fetchSemanticsNodes().size,
        )

        compose.onNodeWithTag(CHAT_MESSAGE_LIST_TEST_TAG)
            .performScrollToIndex(0)
        compose.waitForIdle()

        compose.onNodeWithText("Scroll regression message 1. This row keeps enough height for the chat list.")
            .assertIsDisplayed()
        compose.onNodeWithContentDescription("Jump to latest message")
            .assertIsDisplayed()
            .performClick()
        compose.waitForIdle()

        compose.onNodeWithText("Scroll regression message 28. This row keeps enough height for the chat list.")
            .assertIsDisplayed()
        assertEquals(
            0,
            compose.onAllNodesWithContentDescription("Jump to latest message")
                .fetchSemanticsNodes().size,
        )
        assertEquals(listOf(HapticFeedbackType.TextHandleMove), hapticFeedback.events)
    }

    @Test
    fun settingsScreenRendersPairingCopyAcrossLaunchLanguages() {
        val language = mutableStateOf("en")
        val expectedPairingTitles = mapOf(
            "en" to "Pair AetherLink",
            "ko" to "AetherLink 페어링",
            "ja" to "AetherLink をペアリング",
            "zh-CN" to "配对 AetherLink",
            "fr" to "Jumeler AetherLink",
        )

        compose.setContent {
            LocalizedTestContent(languageTag = language.value) {
                MaterialTheme {
                    SettingsScreen(
                        state = RuntimeUiState(selectedLanguageTag = language.value),
                        onHostChange = {},
                        onPortChange = {},
                        onUseUsbReverse = {},
                        onUseEmulator = {},
                        onStartDiscovery = {},
                        onStopDiscovery = {},
                        onUseDiscoveredRuntime = {},
                        onForgetTrustedRuntime = {},
                        onScanPairingQr = {},
                        onSubmitPairingPayload = {},
                        onConnect = {},
                        onRefreshHealth = {},
                        onRequestModels = {},
                        onDisconnect = {},
                        onSetAutoReconnectEnabled = {},
                        onSetLanguageTag = {},
                        onSetTheme = {},
                        onSelectEmbeddingModel = {},
                        onAddMemoryEntry = {},
                        onRemoveMemoryEntry = {},
                        onSetMemoryEntryEnabled = { _, _ -> },
                        onArchiveChatSession = {},
                        onRestoreChatSession = {},
                        onPermanentlyDeleteChatSession = {},
                        onArchiveAllChatSessions = {},
                        onPermanentlyDeleteArchivedChatSessions = {},
                        showDeveloperDiagnostics = false,
                    )
                }
            }
        }

        expectedPairingTitles.forEach { (languageTag, expectedTitle) ->
            compose.runOnUiThread {
                language.value = languageTag
            }
            compose.waitForIdle()
            compose.onNodeWithText(expectedTitle).assertIsDisplayed()
        }
    }

    @Test
    fun settingsScreenPreferenceAndEmbeddingControlsInvokeCallbacks() {
        var selectedTheme: RuntimeAppTheme? = null
        var selectedLanguageTag: String? = null
        val selectedEmbeddingModelIds = mutableListOf<String?>()
        val chatModel = RuntimeModel(
            id = "ollama:qwen3:8b",
            name = "Qwen3 8B",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = true,
            source = "local",
        )
        val embeddingModel = RuntimeModel(
            id = "ollama:nomic-embed-text",
            name = "Nomic Embed Text",
            modelKind = MODEL_KIND_EMBEDDING,
            capabilities = listOf("embedding"),
            installed = true,
            source = "local",
        )

        compose.setContent {
            MaterialTheme {
                SettingsScreen(
                    state = RuntimeUiState(
                        isConnected = true,
                        runtimeStatus = "authenticated",
                        trustedRuntime = RuntimeTrustedRuntime(
                            deviceId = "runtime-1",
                            name = "AetherLink Runtime",
                        ),
                        backendAvailable = true,
                        selectedLanguageTag = "en",
                        selectedTheme = RuntimeAppTheme.System,
                        models = listOf(chatModel, embeddingModel),
                    ),
                    onHostChange = {},
                    onPortChange = {},
                    onUseUsbReverse = {},
                    onUseEmulator = {},
                    onStartDiscovery = {},
                    onStopDiscovery = {},
                    onUseDiscoveredRuntime = {},
                    onForgetTrustedRuntime = {},
                    onScanPairingQr = {},
                    onSubmitPairingPayload = {},
                    onConnect = {},
                    onRefreshHealth = {},
                    onRequestModels = {},
                    onDisconnect = {},
                    onSetAutoReconnectEnabled = {},
                    onSetLanguageTag = { selectedLanguageTag = it },
                    onSetTheme = { selectedTheme = it },
                    onSelectEmbeddingModel = { selectedEmbeddingModelIds += it },
                    onAddMemoryEntry = {},
                    onRemoveMemoryEntry = {},
                    onSetMemoryEntryEnabled = { _, _ -> },
                    onArchiveChatSession = {},
                    onRestoreChatSession = {},
                    onPermanentlyDeleteChatSession = {},
                    onArchiveAllChatSessions = {},
                    onPermanentlyDeleteArchivedChatSessions = {},
                    showDeveloperDiagnostics = false,
                )
            }
        }

        compose.onNodeWithText("Preferences").assertIsDisplayed()
        compose.onNodeWithText("Appearance").assertIsDisplayed()
        compose.onNodeWithText("Follows system").assertIsDisplayed()
        compose.onNodeWithText("Dark").performClick()
        assertEquals(RuntimeAppTheme.Dark, selectedTheme)

        compose.onNodeWithText("Language")
            .performScrollTo()
            .assertIsDisplayed()
        compose.onNodeWithText("한국어")
            .performScrollTo()
            .performClick()
        assertEquals("ko", selectedLanguageTag)

        repeat(3) {
            compose.onRoot().performTouchInput { swipeUp() }
            compose.waitForIdle()
        }
        compose.onNodeWithText("Memory indexing model")
            .assertIsDisplayed()
            .performClick()
        compose.waitForIdle()

        compose.onNodeWithText("Selected memory indexing model").assertIsDisplayed()
        compose.onNodeWithText("No memory indexing model selected.").assertIsDisplayed()
        repeat(2) {
            compose.onRoot().performTouchInput { swipeUp() }
            compose.waitForIdle()
        }
        compose.onNodeWithText("Nomic Embed Text").assertIsDisplayed()
        compose.onNodeWithText("Nomic Embed Text").performClick()
        compose.onNode(hasText("No model selected") and hasClickAction())
            .performScrollTo()
            .performClick()

        assertEquals(listOf("ollama:nomic-embed-text", null), selectedEmbeddingModelIds)
    }

    @Test
    fun settingsPreferenceRowsExposeSelectedStateToAccessibility() {
        compose.setContent {
            MaterialTheme {
                LocalizedTestContent(languageTag = "en") {
                    SettingsScreen(
                        state = RuntimeUiState(
                            isConnected = true,
                            runtimeStatus = "authenticated",
                            trustedRuntime = RuntimeTrustedRuntime(
                                deviceId = "runtime-1",
                                name = "AetherLink Runtime",
                            ),
                            backendAvailable = true,
                            selectedLanguageTag = "ja",
                            selectedTheme = RuntimeAppTheme.Dark,
                        ),
                        onHostChange = {},
                        onPortChange = {},
                        onUseUsbReverse = {},
                        onUseEmulator = {},
                        onStartDiscovery = {},
                        onStopDiscovery = {},
                        onUseDiscoveredRuntime = {},
                        onForgetTrustedRuntime = {},
                        onScanPairingQr = {},
                        onSubmitPairingPayload = {},
                        onConnect = {},
                        onRefreshHealth = {},
                        onRequestModels = {},
                        onDisconnect = {},
                        onSetAutoReconnectEnabled = {},
                        onSetLanguageTag = {},
                        onSetTheme = {},
                        onSelectEmbeddingModel = {},
                        onAddMemoryEntry = {},
                        onRemoveMemoryEntry = {},
                        onSetMemoryEntryEnabled = { _, _ -> },
                        onArchiveChatSession = {},
                        onRestoreChatSession = {},
                        onPermanentlyDeleteChatSession = {},
                        onArchiveAllChatSessions = {},
                        onPermanentlyDeleteArchivedChatSessions = {},
                        showDeveloperDiagnostics = false,
                    )
                }
            }
        }

        compose.onNode(hasText("Dark") and hasStateDescription("Selected"))
            .assertIsDisplayed()
        compose.onNode(hasText("日本語") and hasStateDescription("Selected"))
            .performScrollTo()
            .assertIsDisplayed()
    }

    @Test
    fun settingsEmbeddingModelRowsExposeSelectedStateToAccessibility() {
        val chatModel = RuntimeModel(
            id = "ollama:qwen3:8b",
            name = "Qwen3 8B",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = true,
            source = "local",
        )
        val embeddingModel = RuntimeModel(
            id = "ollama:nomic-embed-text",
            name = "Nomic Embed Text",
            modelKind = MODEL_KIND_EMBEDDING,
            capabilities = listOf("embedding"),
            installed = true,
            source = "local",
        )

        compose.setContent {
            MaterialTheme {
                SettingsScreen(
                    state = RuntimeUiState(
                        isConnected = true,
                        runtimeStatus = "authenticated",
                        trustedRuntime = RuntimeTrustedRuntime(
                            deviceId = "runtime-1",
                            name = "AetherLink Runtime",
                        ),
                        backendAvailable = true,
                        selectedLanguageTag = "en",
                        selectedTheme = RuntimeAppTheme.System,
                        selectedEmbeddingModelId = embeddingModel.id,
                        models = listOf(chatModel, embeddingModel),
                    ),
                    onHostChange = {},
                    onPortChange = {},
                    onUseUsbReverse = {},
                    onUseEmulator = {},
                    onStartDiscovery = {},
                    onStopDiscovery = {},
                    onUseDiscoveredRuntime = {},
                    onForgetTrustedRuntime = {},
                    onScanPairingQr = {},
                    onSubmitPairingPayload = {},
                    onConnect = {},
                    onRefreshHealth = {},
                    onRequestModels = {},
                    onDisconnect = {},
                    onSetAutoReconnectEnabled = {},
                    onSetLanguageTag = {},
                    onSetTheme = {},
                    onSelectEmbeddingModel = {},
                    onAddMemoryEntry = {},
                    onRemoveMemoryEntry = {},
                    onSetMemoryEntryEnabled = { _, _ -> },
                    onArchiveChatSession = {},
                    onRestoreChatSession = {},
                    onPermanentlyDeleteChatSession = {},
                    onArchiveAllChatSessions = {},
                    onPermanentlyDeleteArchivedChatSessions = {},
                    showDeveloperDiagnostics = false,
                )
            }
        }

        repeat(3) {
            compose.onRoot().performTouchInput { swipeUp() }
            compose.waitForIdle()
        }
        compose.onNodeWithText("Memory indexing model")
            .assertIsDisplayed()
            .performClick()
        compose.waitForIdle()
        repeat(2) {
            compose.onRoot().performTouchInput { swipeUp() }
            compose.waitForIdle()
        }

        compose.onNode(hasText("Nomic Embed Text") and hasStateDescription("Selected"))
            .performScrollTo()
            .assertIsDisplayed()
    }

    @Test
    fun settingsMemoryRowsExposeContextualActionAccessibility() {
        val hapticFeedback = RecordingHapticFeedback()
        val toggledMemory = mutableListOf<Pair<String, Boolean>>()
        var removeClicks = 0
        val activeMemory = RuntimeMemoryEntry(
            id = "memory-active",
            content = "Project Alpha prefers concise Korean summaries",
            enabled = true,
            createdAtMillis = 1_000L,
            updatedAtMillis = 2_000L,
        )
        val pausedMemory = RuntimeMemoryEntry(
            id = "memory-paused",
            content = "Use metric units for travel planning",
            enabled = false,
            createdAtMillis = 3_000L,
            updatedAtMillis = 4_000L,
        )

        compose.setContent {
            MaterialTheme {
                CompositionLocalProvider(LocalHapticFeedback provides hapticFeedback) {
                    SettingsScreen(
                        state = RuntimeUiState(
                            isConnected = true,
                            runtimeStatus = "authenticated",
                            trustedRuntime = RuntimeTrustedRuntime(
                                deviceId = "runtime-1",
                                name = "AetherLink Runtime",
                            ),
                            memoryEntries = listOf(activeMemory, pausedMemory),
                        ),
                        onHostChange = {},
                        onPortChange = {},
                        onUseUsbReverse = {},
                        onUseEmulator = {},
                        onStartDiscovery = {},
                        onStopDiscovery = {},
                        onUseDiscoveredRuntime = {},
                        onForgetTrustedRuntime = {},
                        onScanPairingQr = {},
                        onSubmitPairingPayload = {},
                        onConnect = {},
                        onRefreshHealth = {},
                        onRequestModels = {},
                        onDisconnect = {},
                        onSetAutoReconnectEnabled = {},
                        onSetLanguageTag = {},
                        onSetTheme = {},
                        onSelectEmbeddingModel = {},
                        onAddMemoryEntry = {},
                        onRemoveMemoryEntry = {
                            removeClicks += 1
                        },
                        onSetMemoryEntryEnabled = { id, enabled ->
                            toggledMemory += id to enabled
                        },
                        onArchiveChatSession = {},
                        onRestoreChatSession = {},
                        onPermanentlyDeleteChatSession = {},
                        onArchiveAllChatSessions = {},
                        onPermanentlyDeleteArchivedChatSessions = {},
                        showDeveloperDiagnostics = false,
                    )
                }
            }
        }

        scrollUntilTextIsVisible("Memory")
        compose.onNodeWithText("Memory")
            .performScrollTo()
            .performClick()
        compose.waitForIdle()
        hapticFeedback.events.clear()

        compose.onNodeWithContentDescription(
            "Pause memory Project Alpha prefers concise Korean summaries",
            useUnmergedTree = true,
        )
            .performScrollTo()
            .assert(hasStateDescription("Enabled"))
            .performClick()
        assertEquals(listOf(HapticFeedbackType.TextHandleMove), hapticFeedback.events)
        compose.onNodeWithContentDescription(
            "Enable memory Use metric units for travel planning",
            useUnmergedTree = true,
        )
            .performScrollTo()
            .assert(hasStateDescription("Paused"))
            .assertIsDisplayed()
        compose.onNodeWithContentDescription(
            "Remove memory Project Alpha prefers concise Korean summaries",
            useUnmergedTree = true,
        )
            .performScrollTo()
            .assertIsDisplayed()
            .performClick()
        compose.onNodeWithText("Remove memory?").assertIsDisplayed()
        assertEquals(
            listOf(HapticFeedbackType.TextHandleMove, HapticFeedbackType.TextHandleMove),
            hapticFeedback.events,
        )
        compose.onNodeWithText("Cancel").performClick()
        assertEquals(
            listOf(
                HapticFeedbackType.TextHandleMove,
                HapticFeedbackType.TextHandleMove,
                HapticFeedbackType.TextHandleMove,
            ),
            hapticFeedback.events,
        )
        compose.onNodeWithContentDescription(
            "Remove memory Project Alpha prefers concise Korean summaries",
            useUnmergedTree = true,
        )
            .performScrollTo()
            .assertIsDisplayed()
            .performClick()
        compose.onNodeWithText("Delete").performClick()

        assertEquals(listOf("memory-active" to false), toggledMemory)
        assertEquals(1, removeClicks)
        assertEquals(
            listOf(
                HapticFeedbackType.TextHandleMove,
                HapticFeedbackType.TextHandleMove,
                HapticFeedbackType.TextHandleMove,
                HapticFeedbackType.TextHandleMove,
                HapticFeedbackType.LongPress,
            ),
            hapticFeedback.events,
        )
    }

    @Test
    fun settingsLanguagePickerUsesNativeLabelsAcrossLaunchLanguages() {
        val launchLanguageTags = listOf("en", "ko", "ja", "zh-Hans", "fr")
        val nativeLanguageLabels = listOf(
            "English",
            "한국어",
            "日本語",
            "简体中文",
            "Français",
        )
        val language = mutableStateOf(launchLanguageTags.first())
        val selectedLanguageTags = mutableListOf<String>()

        compose.setContent {
            MaterialTheme {
                LocalizedTestContent(languageTag = language.value) {
                    SettingsScreen(
                        state = RuntimeUiState(
                            isConnected = true,
                            runtimeStatus = "authenticated",
                            trustedRuntime = RuntimeTrustedRuntime(
                                deviceId = "runtime-1",
                                name = "AetherLink Runtime",
                            ),
                            backendAvailable = true,
                            selectedLanguageTag = language.value,
                            selectedTheme = RuntimeAppTheme.System,
                        ),
                        onHostChange = {},
                        onPortChange = {},
                        onUseUsbReverse = {},
                        onUseEmulator = {},
                        onStartDiscovery = {},
                        onStopDiscovery = {},
                        onUseDiscoveredRuntime = {},
                        onForgetTrustedRuntime = {},
                        onScanPairingQr = {},
                        onSubmitPairingPayload = {},
                        onConnect = {},
                        onRefreshHealth = {},
                        onRequestModels = {},
                        onDisconnect = {},
                        onSetAutoReconnectEnabled = {},
                        onSetLanguageTag = { selectedLanguageTags += it },
                        onSetTheme = {},
                        onSelectEmbeddingModel = {},
                        onAddMemoryEntry = {},
                        onRemoveMemoryEntry = {},
                        onSetMemoryEntryEnabled = { _, _ -> },
                        onArchiveChatSession = {},
                        onRestoreChatSession = {},
                        onPermanentlyDeleteChatSession = {},
                        onArchiveAllChatSessions = {},
                        onPermanentlyDeleteArchivedChatSessions = {},
                        showDeveloperDiagnostics = false,
                    )
                }
            }
        }

        launchLanguageTags.forEach { languageTag ->
            compose.runOnUiThread {
                language.value = languageTag
            }
            compose.waitForIdle()
            scrollUntilTextIsVisible("English")
            nativeLanguageLabels.forEach { label ->
                assertTrue(
                    "Expected native language label '$label' for launch language '$languageTag'.",
                    compose.onAllNodesWithText(label).fetchSemanticsNodes().isNotEmpty(),
                )
            }
        }

        compose.onNodeWithText("한국어")
            .performScrollTo()
            .performClick()

        assertEquals("ko", selectedLanguageTags.last())
    }

    @Test
    fun chatTopBarModelPickerShowsOnlyChatModels() {
        val selectedChatModelIds = mutableListOf<String>()
        var requestModelsClicks = 0
        val qwenChatModel = RuntimeModel(
            id = "ollama:qwen3:8b",
            name = "Qwen3 8B",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = true,
            source = "local",
        )
        val llamaChatModel = RuntimeModel(
            id = "ollama:llama3.1:8b",
            name = "Llama 3.1 8B",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = true,
            source = "local",
        )
        val embeddingModel = RuntimeModel(
            id = "ollama:nomic-embed-text",
            name = "Nomic Embed Text",
            modelKind = MODEL_KIND_EMBEDDING,
            capabilities = listOf("embedding"),
            installed = true,
            source = "local",
        )

        compose.setContent {
            MaterialTheme {
                ChatTopAppBarTitle(
                    state = RuntimeUiState(
                        isConnected = true,
                        runtimeStatus = "authenticated",
                        backendAvailable = true,
                        selectedModelId = qwenChatModel.id,
                        models = listOf(qwenChatModel, llamaChatModel, embeddingModel),
                    ),
                    onRequestModels = { requestModelsClicks += 1 },
                    onSelectModel = { selectedChatModelIds += it },
                )
            }
        }

        compose.onNodeWithText("Qwen3 8B").assertIsDisplayed()
        compose.onNodeWithText("Qwen3 8B").performClick()
        compose.waitForIdle()

        compose.onNodeWithText("Refresh models").assertIsDisplayed()
        assertEquals(2, compose.onAllNodesWithText("Qwen3 8B").fetchSemanticsNodes().size)
        compose.onNodeWithText("Llama 3.1 8B").assertIsDisplayed()
        assertNoVisibleText("Memory indexing model")
        assertNoVisibleText("No memory indexing model selected.")
        assertNoVisibleText("Nomic Embed Text")
        assertEquals(0, requestModelsClicks)

        compose.onNodeWithText("Llama 3.1 8B").performClick()
        compose.waitForIdle()

        assertEquals(listOf("ollama:llama3.1:8b"), selectedChatModelIds)
    }

    @Test
    fun chatTopBarModelPickerExposesInstallActionForUninstalledLocalChatModel() {
        val selectedChatModelIds = mutableListOf<String>()
        val installedChatModel = RuntimeModel(
            id = "ollama:qwen3:8b",
            name = "Qwen3 8B",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = true,
            source = "local",
        )
        val uninstalledChatModel = RuntimeModel(
            id = "ollama:gemma4:26b",
            name = "Gemma 4 26B",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = false,
            source = "local",
        )

        compose.setContent {
            MaterialTheme {
                ChatTopAppBarTitle(
                    state = RuntimeUiState(
                        isConnected = true,
                        runtimeStatus = "authenticated",
                        backendAvailable = true,
                        selectedModelId = installedChatModel.id,
                        models = listOf(installedChatModel, uninstalledChatModel),
                    ),
                    onRequestModels = {},
                    onSelectModel = { selectedChatModelIds += it },
                )
            }
        }

        compose.onNodeWithText("Qwen3 8B").assertIsDisplayed().performClick()
        compose.waitForIdle()

        compose.onNode(
            hasText("Gemma 4 26B") and
                hasStateDescription("Install model") and
                hasClickAction(),
        )
            .assertIsDisplayed()
            .assertIsEnabled()
        compose.onNodeWithText("Install model").assertIsDisplayed()

        compose.onNodeWithText("Gemma 4 26B").performClick()
        compose.waitForIdle()

        assertEquals(listOf("ollama:gemma4:26b"), selectedChatModelIds)
    }

    @Test
    fun chatTopBarModelPickerExposesSelectedRowsToAccessibility() {
        val chatModel = RuntimeModel(
            id = "ollama:qwen3:8b",
            name = "Qwen3 8B",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = true,
            source = "local",
        )
        val otherChatModel = RuntimeModel(
            id = "ollama:llama3.1:8b",
            name = "Llama 3.1 8B",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = true,
            source = "local",
        )
        val embeddingModel = RuntimeModel(
            id = "ollama:nomic-embed-text",
            name = "Nomic Embed Text",
            modelKind = MODEL_KIND_EMBEDDING,
            capabilities = listOf("embedding"),
            installed = true,
            source = "local",
        )

        compose.setContent {
            MaterialTheme {
                ChatTopAppBarTitle(
                    state = RuntimeUiState(
                        isConnected = true,
                        runtimeStatus = "authenticated",
                        backendAvailable = true,
                        selectedModelId = chatModel.id,
                        selectedEmbeddingModelId = embeddingModel.id,
                        models = listOf(chatModel, otherChatModel, embeddingModel),
                    ),
                    onRequestModels = {},
                    onSelectModel = {},
                )
            }
        }

        compose.onNodeWithText("Qwen3 8B").assertIsDisplayed().performClick()
        compose.waitForIdle()

        compose.onNode(hasText("Qwen3 8B") and hasStateDescription("Selected"))
            .assertIsDisplayed()
        assertNoVisibleText("Nomic Embed Text")
    }

    @Test
    fun chatTopBarModelPickerStatusLineUsesLocalizedResources() {
        val context = ApplicationProvider
            .getApplicationContext<Context>()
            .localizedContext("fr")

        assertEquals(
            "Ollama - Installé",
            context.getString(
                R.string.model_status_value,
                "Ollama",
                context.getString(R.string.model_installed),
            )
        )
    }

    @Test
    fun primaryScreensRenderAcrossLocaleThemeSurfaceMatrix() {
        val renderCase = mutableStateOf(
            RenderSmokeCase(
                languageTag = "en",
                dark = false,
                surface = RenderSmokeSurface.Chat,
            )
        )
        val chatModel = RuntimeModel(
            id = "ollama:qwen3:8b",
            name = "Qwen3 8B",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = true,
            source = "local",
        )
        val embeddingModel = RuntimeModel(
            id = "ollama:nomic-embed-text",
            name = "Nomic Embed Text",
            modelKind = MODEL_KIND_EMBEDDING,
            capabilities = listOf("embedding"),
            installed = true,
            source = "local",
        )
        val trustedRuntime = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = Long.MAX_VALUE,
            relayNonce = "nonce-1",
        )

        compose.setContent {
            val currentCase = renderCase.value
            LocalizedTestContent(languageTag = currentCase.languageTag) {
                MaterialTheme(
                    colorScheme = if (currentCase.dark) darkColorScheme() else lightColorScheme(),
                ) {
                    Surface(modifier = Modifier.fillMaxSize()) {
                        when (currentCase.surface) {
                            RenderSmokeSurface.Chat -> ChatScreen(
                                state = RuntimeUiState(
                                    isConnected = true,
                                    runtimeStatus = "authenticated",
                                    trustedRuntime = trustedRuntime,
                                    backendAvailable = true,
                                    selectedLanguageTag = currentCase.languageTag,
                                    selectedTheme = if (currentCase.dark) {
                                        RuntimeAppTheme.Dark
                                    } else {
                                        RuntimeAppTheme.Light
                                    },
                                    selectedModelId = chatModel.id,
                                    selectedEmbeddingModelId = embeddingModel.id,
                                    models = listOf(chatModel, embeddingModel),
                                    messages = listOf(
                                        RuntimeChatMessage(
                                            id = "user-1",
                                            role = "user",
                                            content = "Draft a connection checklist.",
                                        ),
                                        RuntimeChatMessage(
                                            id = "assistant-1",
                                            role = "assistant",
                                            reasoning = "check trusted runtime\ncheck model selection",
                                            content = "Use the paired runtime, then choose a local chat model.",
                                            suggestions = listOf(
                                                "Show trusted runtime status",
                                                "Choose a memory indexing model",
                                            ),
                                        ),
                                    ),
                                ),
                                onInputChange = {},
                                onSend = {},
                                onCancel = {},
                                onConnect = {},
                                onScanPairingQr = {},
                                onRefreshHealth = {},
                                onAttachFiles = {},
                                onRemoveAttachment = {},
                                onSuggestionClick = {},
                                onScanLatestQr = {},
                            )

                            RenderSmokeSurface.Settings -> SettingsScreen(
                                state = RuntimeUiState(
                                    isConnected = true,
                                    runtimeStatus = "authenticated",
                                    trustedRuntime = trustedRuntime,
                                    backendAvailable = true,
                                    selectedLanguageTag = currentCase.languageTag,
                                    selectedTheme = if (currentCase.dark) {
                                        RuntimeAppTheme.Dark
                                    } else {
                                        RuntimeAppTheme.Light
                                    },
                                    selectedModelId = chatModel.id,
                                    selectedEmbeddingModelId = embeddingModel.id,
                                    models = listOf(chatModel, embeddingModel),
                                ),
                                onHostChange = {},
                                onPortChange = {},
                                onUseUsbReverse = {},
                                onUseEmulator = {},
                                onStartDiscovery = {},
                                onStopDiscovery = {},
                                onUseDiscoveredRuntime = {},
                                onForgetTrustedRuntime = {},
                                onScanPairingQr = {},
                                onSubmitPairingPayload = {},
                                onConnect = {},
                                onRefreshHealth = {},
                                onRequestModels = {},
                                onDisconnect = {},
                                onSetAutoReconnectEnabled = {},
                                onSetLanguageTag = {},
                                onSetTheme = {},
                                onSelectEmbeddingModel = {},
                                onAddMemoryEntry = {},
                                onRemoveMemoryEntry = {},
                                onSetMemoryEntryEnabled = { _, _ -> },
                                onArchiveChatSession = {},
                                onRestoreChatSession = {},
                                onPermanentlyDeleteChatSession = {},
                                onArchiveAllChatSessions = {},
                                onPermanentlyDeleteArchivedChatSessions = {},
                                showDeveloperDiagnostics = false,
                            )

                            RenderSmokeSurface.Connection -> ConnectionStatusScreen(
                                state = RuntimeUiState(
                                    runtimeStatus = "disconnected",
                                    trustedRuntime = trustedRuntime,
                                    backendAvailable = true,
                                    selectedLanguageTag = currentCase.languageTag,
                                    selectedTheme = if (currentCase.dark) {
                                        RuntimeAppTheme.Dark
                                    } else {
                                        RuntimeAppTheme.Light
                                    },
                                    selectedModelId = chatModel.id,
                                    selectedEmbeddingModelId = embeddingModel.id,
                                    models = listOf(chatModel, embeddingModel),
                                ),
                                onConnect = {},
                                onRefreshHealth = {},
                                onDisconnect = {},
                                onScanLatestQr = {},
                            )
                        }
                    }
                }
            }
        }

        val localizedAnchors = listOf(
            LocalizedSmokeAnchors(
                languageTag = "en",
                chatAnchor = "Next questions",
                settingsAnchor = "Settings",
                connectionAnchor = "Saved connection",
            ),
            LocalizedSmokeAnchors(
                languageTag = "ko",
                chatAnchor = "다음 질문",
                settingsAnchor = "설정",
                connectionAnchor = "저장된 연결",
            ),
            LocalizedSmokeAnchors(
                languageTag = "ja",
                chatAnchor = "次の質問",
                settingsAnchor = "設定",
                connectionAnchor = "保存済み接続",
            ),
            LocalizedSmokeAnchors(
                languageTag = "zh-CN",
                chatAnchor = "后续问题",
                settingsAnchor = "设置",
                connectionAnchor = "已保存连接",
            ),
            LocalizedSmokeAnchors(
                languageTag = "fr",
                chatAnchor = "Questions suivantes",
                settingsAnchor = "Réglages",
                connectionAnchor = "Connexion enregistrée",
            ),
        )
        val smokeCases = localizedAnchors.flatMap { anchors ->
            listOf(false, true).flatMap { dark ->
                listOf(
                    RenderSmokeCase(
                        languageTag = anchors.languageTag,
                        dark = dark,
                        surface = RenderSmokeSurface.Chat,
                        visibleAnchor = anchors.chatAnchor,
                    ),
                    RenderSmokeCase(
                        languageTag = anchors.languageTag,
                        dark = dark,
                        surface = RenderSmokeSurface.Settings,
                        visibleAnchor = anchors.settingsAnchor,
                    ),
                    RenderSmokeCase(
                        languageTag = anchors.languageTag,
                        dark = dark,
                        surface = RenderSmokeSurface.Connection,
                        visibleAnchor = anchors.connectionAnchor,
                    ),
                )
            }
        }

        smokeCases.forEach { nextCase ->
            compose.runOnUiThread {
                renderCase.value = nextCase
            }
            compose.waitForIdle()
            assertRootHasStableLayout()
            compose.onNodeWithText(requireNotNull(nextCase.visibleAnchor))
                .performScrollTo()
                .assertIsDisplayed()
        }
    }

    @Test
    fun chatScreenNormalizesSuggestedQuestionChips() {
        val clickedSuggestions = mutableListOf<String>()
        val chatModel = RuntimeModel(
            id = "ollama:qwen3:8b",
            name = "Qwen3 8B",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = true,
            source = "local",
        )

        compose.setContent {
            MaterialTheme {
                ChatScreen(
                    state = RuntimeUiState(
                        isConnected = true,
                        runtimeStatus = "authenticated",
                        trustedRuntime = RuntimeTrustedRuntime(
                            deviceId = "runtime-1",
                            name = "AetherLink Runtime",
                        ),
                        backendAvailable = true,
                        selectedModelId = chatModel.id,
                        models = listOf(chatModel),
                        messages = listOf(
                            RuntimeChatMessage(
                                id = "user-1",
                                role = "user",
                                content = "Plan the next step.",
                            ),
                            RuntimeChatMessage(
                                id = "assistant-1",
                                role = "assistant",
                                content = "The next step is to verify QR pairing.",
                                suggestions = listOf(
                                    "  Follow up?  ",
                                    "",
                                    "follow   up?",
                                    "Summarize\nagain?",
                                    "Check route status",
                                    "Draft a test plan",
                                    "Hidden extra suggestion",
                                ),
                            ),
                        ),
                    ),
                    onInputChange = {},
                    onSend = {},
                    onCancel = {},
                    onConnect = {},
                    onScanPairingQr = {},
                    onRefreshHealth = {},
                    onAttachFiles = {},
                    onRemoveAttachment = {},
                    onSuggestionClick = { clickedSuggestions += it },
                    onScanLatestQr = {},
                )
            }
        }

        compose.onNodeWithText("Follow up?").assertIsDisplayed()
        compose.onNodeWithText("Summarize again?").assertIsDisplayed()
        compose.onNodeWithContentDescription("Suggested question: Summarize again?", useUnmergedTree = true)
            .assertIsDisplayed()
        compose.onNodeWithText("Check route status").assertIsDisplayed()
        compose.onNodeWithText("Draft a test plan").assertIsDisplayed()
        assertNoVisibleText("follow up?")
        assertNoVisibleText("Hidden extra suggestion")

        compose.onNodeWithText("Summarize again?").performClick()

        assertEquals(listOf("Summarize again?"), clickedSuggestions)
    }

    @Test
    fun chatScreenSuggestionClickFillsComposerWithoutSending() {
        var sendClicks = 0
        val chatModel = RuntimeModel(
            id = "ollama:qwen3:8b",
            name = "Qwen3 8B",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = true,
            source = "local",
        )
        val state = mutableStateOf(
            RuntimeUiState(
                isConnected = true,
                runtimeStatus = "authenticated",
                trustedRuntime = RuntimeTrustedRuntime(
                    deviceId = "runtime-1",
                    name = "AetherLink Runtime",
                ),
                backendAvailable = true,
                selectedModelId = chatModel.id,
                models = listOf(chatModel),
                messages = listOf(
                    RuntimeChatMessage(
                        id = "user-1",
                        role = "user",
                        content = "Plan the next step.",
                    ),
                    RuntimeChatMessage(
                        id = "assistant-1",
                        role = "assistant",
                        content = "Use the latest QR route.",
                        suggestions = listOf("Check route status"),
                    ),
                ),
            ),
        )

        compose.setContent {
            MaterialTheme {
                ChatScreen(
                    state = state.value,
                    onInputChange = { text -> state.value = state.value.copy(chatInput = text) },
                    onSend = { sendClicks += 1 },
                    onCancel = {},
                    onConnect = {},
                    onScanPairingQr = {},
                    onRefreshHealth = {},
                    onAttachFiles = {},
                    onRemoveAttachment = {},
                    onSuggestionClick = { suggestion ->
                        state.value = state.value.copy(chatInput = suggestion)
                    },
                    onScanLatestQr = {},
                )
            }
        }

        compose.onNodeWithText("Check route status").assertIsDisplayed().performClick()

        assertEquals("Check route status", state.value.chatInput)
        assertEquals(0, sendClicks)
        compose.onNodeWithContentDescription("Send message").assertIsEnabled()
    }

    @Composable
    private fun LocalizedTestContent(
        languageTag: String,
        content: @Composable () -> Unit,
    ) {
        val baseContext = LocalContext.current
        val localizedContext = remember(baseContext, languageTag) {
            baseContext.localizedContext(languageTag)
        }
        CompositionLocalProvider(LocalContext provides localizedContext) {
            content()
        }
    }

    private fun Context.localizedContext(languageTag: String): Context {
        val locale = Locale.forLanguageTag(languageTag)
        val configuration = Configuration(resources.configuration)
        configuration.setLocale(locale)
        configuration.setLocales(LocaleList(locale))
        return createConfigurationContext(configuration)
    }

    private fun assertRootHasStableLayout() {
        compose.onRoot()
            .assertWidthIsAtLeast(240.dp)
            .assertHeightIsAtLeast(320.dp)
    }

    private fun assertNoVisibleText(text: String) {
        assertEquals(0, compose.onAllNodesWithText(text).fetchSemanticsNodes().size)
    }

    private fun scrollUntilTextIsVisible(text: String, maxSwipes: Int = 8) {
        repeat(maxSwipes) {
            if (compose.onAllNodesWithText(text).fetchSemanticsNodes().isNotEmpty()) return
            compose.onRoot().performTouchInput { swipeUp() }
            compose.waitForIdle()
        }
    }

    private data class RenderSmokeCase(
        val languageTag: String,
        val dark: Boolean,
        val surface: RenderSmokeSurface,
        val visibleAnchor: String? = null,
    )

    private data class LocalizedSmokeAnchors(
        val languageTag: String,
        val chatAnchor: String,
        val settingsAnchor: String,
        val connectionAnchor: String,
    )

    private enum class RenderSmokeSurface {
        Chat,
        Settings,
        Connection,
    }

    private class RecordingHapticFeedback : HapticFeedback {
        val events = mutableListOf<HapticFeedbackType>()

        override fun performHapticFeedback(hapticFeedbackType: HapticFeedbackType) {
            events += hapticFeedbackType
        }
    }
}
