package com.localagentbridge.android.ui

import android.content.Context
import android.content.res.Configuration
import android.os.LocaleList
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
import androidx.compose.ui.test.assertHeightIsAtLeast
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertWidthIsAtLeast
import androidx.compose.ui.test.hasClickAction
import androidx.compose.ui.test.hasStateDescription
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onFirst
import androidx.compose.ui.test.onLast
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTouchInput
import androidx.compose.ui.test.performTextInput
import androidx.compose.ui.test.swipeUp
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.unit.dp
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.localagentbridge.android.ChatSessionDrawerItem
import com.localagentbridge.android.ChatTopAppBarTitle
import com.localagentbridge.android.runtime.MODEL_KIND_CHAT
import com.localagentbridge.android.runtime.MODEL_KIND_EMBEDDING
import com.localagentbridge.android.runtime.RuntimeAppTheme
import com.localagentbridge.android.runtime.RuntimeChatMessage
import com.localagentbridge.android.runtime.RuntimeChatSession
import com.localagentbridge.android.runtime.RuntimeModel
import com.localagentbridge.android.runtime.RuntimeTrustedRuntime
import com.localagentbridge.android.runtime.RuntimeUiState
import org.junit.Assert.assertEquals
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
        assertNoVisibleText("Diagnostic QR text")
        assertNoVisibleText("Enter QR text")
        assertNoVisibleText("USB connection")
        assertNoVisibleText("Emulator connection")
        assertNoVisibleText("Connection address")
        assertNoVisibleText("Connection port")

        compose.onNodeWithTag(DEVELOPER_DIAGNOSTICS_TOGGLE_ROW_TAG).performClick()
        compose.waitForIdle()
        compose.onNodeWithTag(DEVELOPER_DIAGNOSTICS_SWITCH_ENABLED_TAG).assertExists()
        assertNoVisibleText("Enter QR text")
    }

    @Test
    fun settingsScreenKeepsBulkChatHistoryActionsHiddenAndTwoStepConfirmed() {
        var archiveAllClicks = 0
        var deleteArchivedClicks = 0

        compose.setContent {
            MaterialTheme {
                SettingsScreen(
                    state = RuntimeUiState(
                        chatSessions = listOf(
                            RuntimeChatSession(
                                id = "active-chat",
                                title = "Active project chat",
                                messageCount = 4,
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
                    onArchiveChatSession = {},
                    onRestoreChatSession = {},
                    onPermanentlyDeleteChatSession = {},
                    onArchiveAllChatSessions = { archiveAllClicks += 1 },
                    onPermanentlyDeleteArchivedChatSessions = { deleteArchivedClicks += 1 },
                    showDeveloperDiagnostics = false,
                )
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
        scrollUntilTextIsVisible("Manage all chats")

        compose.onNodeWithText("Manage all chats")
            .performScrollTo()
            .assertIsDisplayed()
        assertNoVisibleText("Archive all chats")
        assertNoVisibleText("Permanently delete archived chats")

        compose.onNodeWithText("Manage all chats").performClick()
        compose.waitForIdle()
        scrollUntilTextIsVisible("Archive all chats")

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
        compose.onNodeWithText("Continue").performClick()
        compose.onNodeWithText("Confirm again to archive every active chat. Archived chats can be restored later.")
            .assertIsDisplayed()
        compose.onNodeWithText("Archive").performClick()

        assertEquals(1, archiveAllClicks)
        assertEquals(0, deleteArchivedClicks)

        compose.onNodeWithText("Permanently delete archived chats")
            .performScrollTo()
            .performClick()
        compose.onNodeWithText("Permanently delete all archived chats? Active chats stay saved.")
            .assertIsDisplayed()
        compose.onNodeWithText("Continue").performClick()
        compose.onNodeWithText("Confirm permanent deletion of every archived chat. This cannot be undone.")
            .assertIsDisplayed()
        compose.onAllNodesWithText("Permanently delete").onLast().performClick()

        assertEquals(1, archiveAllClicks)
        assertEquals(1, deleteArchivedClicks)
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
                }
            }
        }

        compose.onNodeWithText("Trip plan").assertIsDisplayed()
        compose.onNodeWithText("3 messages - Needs attention").assertIsDisplayed()
        compose.onNodeWithText("Connection notes").assertIsDisplayed()
        compose.onNodeWithText("2 messages - In progress").assertIsDisplayed()
    }

    @Test
    fun chatScreenAcceptsInputAndSendWhenConnectedModelIsReady() {
        var sendClicks = 0
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
                        onAttachFiles = {},
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
        compose.onNodeWithContentDescription("Send message")
            .assertIsEnabled()
            .performClick()

        assertEquals("Hello", state.value.chatInput)
        assertEquals(1, sendClicks)
        assertEquals(listOf(HapticFeedbackType.TextHandleMove), hapticFeedback.events)
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

        compose.onNode(hasStateDescription("Show thinking") and hasClickAction())
            .performClick()

        compose.onNodeWithText("first step\nsecond step\nthird step\nfourth step").assertIsDisplayed()
        compose.onNodeWithText("Hide thinking").assertIsDisplayed()
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
        compose.onNodeWithText("Korean")
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
    fun chatTopBarModelPickerSeparatesChatAndEmbeddingModels() {
        val selectedChatModelIds = mutableListOf<String>()
        val selectedEmbeddingModelIds = mutableListOf<String?>()
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
                    onSelectEmbeddingModel = { selectedEmbeddingModelIds += it },
                )
            }
        }

        compose.onNodeWithText("Qwen3 8B").assertIsDisplayed()
        compose.onNodeWithText("Qwen3 8B").performClick()
        compose.waitForIdle()

        compose.onNodeWithText("Refresh models").assertIsDisplayed()
        assertEquals(2, compose.onAllNodesWithText("Qwen3 8B").fetchSemanticsNodes().size)
        compose.onNodeWithText("Llama 3.1 8B").assertIsDisplayed()
        compose.onNodeWithText("Memory indexing model").assertIsDisplayed()
        assertEquals(
            2,
            compose.onAllNodesWithText("No memory indexing model selected.").fetchSemanticsNodes().size,
        )
        compose.onNodeWithText("Nomic Embed Text")
            .performScrollTo()
            .assertIsDisplayed()

        compose.onNodeWithText("Nomic Embed Text").performClick()
        compose.waitForIdle()

        assertEquals(emptyList<String>(), selectedChatModelIds)
        assertEquals(listOf("ollama:nomic-embed-text"), selectedEmbeddingModelIds)
        assertEquals(0, requestModelsClicks)

        compose.onNodeWithText("Qwen3 8B").performClick()
        compose.waitForIdle()
        compose.onNodeWithText("Llama 3.1 8B").performClick()
        compose.waitForIdle()

        assertEquals(listOf("ollama:llama3.1:8b"), selectedChatModelIds)
        assertEquals(listOf("ollama:nomic-embed-text"), selectedEmbeddingModelIds)
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
                        }
                    }
                }
            }
        }

        val localizedAnchors = listOf(
            LocalizedSmokeAnchors(languageTag = "en", chatAnchor = "Next questions", settingsAnchor = "Settings"),
            LocalizedSmokeAnchors(languageTag = "ko", chatAnchor = "다음 질문", settingsAnchor = "설정"),
            LocalizedSmokeAnchors(languageTag = "ja", chatAnchor = "次の質問", settingsAnchor = "設定"),
            LocalizedSmokeAnchors(languageTag = "zh-CN", chatAnchor = "后续问题", settingsAnchor = "设置"),
            LocalizedSmokeAnchors(languageTag = "fr", chatAnchor = "Questions suivantes", settingsAnchor = "Réglages"),
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
                .assertIsDisplayed()
        }
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
    )

    private enum class RenderSmokeSurface {
        Chat,
        Settings,
    }

    private class RecordingHapticFeedback : HapticFeedback {
        val events = mutableListOf<HapticFeedbackType>()

        override fun performHapticFeedback(hapticFeedbackType: HapticFeedbackType) {
            events += hapticFeedbackType
        }
    }
}
