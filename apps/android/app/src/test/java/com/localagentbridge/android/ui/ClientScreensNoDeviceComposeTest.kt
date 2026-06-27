package com.localagentbridge.android.ui

import android.content.Context
import android.content.res.Configuration
import android.os.LocaleList
import android.text.format.Formatter
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.width
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.key
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
import androidx.compose.ui.test.hasSetTextAction
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
import androidx.compose.ui.test.performImeAction
import androidx.compose.ui.test.performScrollToIndex
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performSemanticsAction
import androidx.compose.ui.test.performTextClearance
import androidx.compose.ui.test.performTouchInput
import androidx.compose.ui.test.performTextInput
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.swipeUp
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.unit.dp
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.localagentbridge.android.AetherLinkNavigationDrawerContent
import com.localagentbridge.android.AetherLinkPermanentNavigationRail
import com.localagentbridge.android.AetherLinkTopAppBar
import com.localagentbridge.android.AppDestination
import com.localagentbridge.android.CHAT_MODEL_SEARCH_TEST_TAG
import com.localagentbridge.android.ChatSessionDrawerItem
import com.localagentbridge.android.ChatTopAppBarTitle
import com.localagentbridge.android.DRAWER_CHAT_SEARCH_TEST_TAG
import com.localagentbridge.android.DRAWER_HISTORY_TEST_TAG
import com.localagentbridge.android.DRAWER_SETTINGS_FOOTER_TEST_TAG
import com.localagentbridge.android.R
import com.localagentbridge.android.RenameChatSessionDialog
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
import com.localagentbridge.android.runtime.RuntimeProviderStatus
import com.localagentbridge.android.runtime.RuntimeTrustedRuntime
import com.localagentbridge.android.runtime.RuntimeUiError
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

        compose.onNode(
            hasText("Scan QR") and
                hasStateDescription("Ready to scan QR."),
        ).performClick()

        assertEquals(1, scanClicks)
    }

    @Test
    fun trustedRouteConnectLabelDiffersFromGenericConnectAcrossSupportedLanguages() {
        val expectations = listOf(
            "en" to "Connect trusted route",
            "ko" to "신뢰된 경로 연결",
            "ja" to "信頼済み経路に接続",
            "zh-CN" to "连接可信路径",
            "fr" to "Connecter l’itinéraire approuvé",
        )

        expectations.forEach { (languageTag, expectedRemoteRouteLabel) ->
            val localizedContext = ApplicationProvider
                .getApplicationContext<Context>()
                .localizedContext(languageTag)
            val genericConnect = localizedContext.getString(R.string.connect_runtime)
            val trustedRouteConnect = localizedContext.getString(R.string.connect_remote_route)

            assertEquals(expectedRemoteRouteLabel, trustedRouteConnect)
            assertTrue(
                "connect_remote_route should distinguish trusted route copy for $languageTag",
                trustedRouteConnect != genericConnect,
            )
        }
    }

    @Test
    fun settingsConnectionStatusHeroExposesLocalizedAccessibilitySummaries() {
        data class HeroScenario(
            val state: RuntimeUiState,
            val titleRes: Int,
            val detailRes: Int,
            val runtimeName: String,
        )

        val runtimeName = "Studio Runtime"
        val languageTags = listOf("en", "ko", "ja", "zh-CN", "fr")
        val languageTag = mutableStateOf(languageTags.first())
        val heroScenario = mutableStateOf(
            HeroScenario(
                state = RuntimeUiState(),
                titleRes = R.string.status_pairing_needed_title,
                detailRes = R.string.status_pairing_needed_detail,
                runtimeName = runtimeName,
            ),
        )

        compose.setContent {
            MaterialTheme {
                val selectedLanguageTag = languageTag.value
                LocalizedTestContent(languageTag = selectedLanguageTag) {
                    ConnectionStatusScreen(
                        state = heroScenario.value.state.copy(selectedLanguageTag = selectedLanguageTag),
                        onConnect = {},
                        onRefreshHealth = {},
                        onDisconnect = {},
                        onScanLatestQr = {},
                    )
                }
            }
        }

        val scenarios = listOf(
            HeroScenario(
                state = RuntimeUiState(),
                titleRes = R.string.status_pairing_needed_title,
                detailRes = R.string.status_pairing_needed_detail,
                runtimeName = runtimeName,
            ),
            HeroScenario(
                state = RuntimeUiState(
                    trustedRuntime = RuntimeTrustedRuntime(deviceId = "runtime-1", name = runtimeName),
                ),
                titleRes = R.string.status_route_needed_title,
                detailRes = R.string.status_route_needed_detail,
                runtimeName = runtimeName,
            ),
            HeroScenario(
                state = RuntimeUiState(
                    trustedRuntime = RuntimeTrustedRuntime(
                        deviceId = "runtime-1",
                        name = runtimeName,
                        relayHost = "relay.aetherlink.example",
                        relayPort = 43171,
                        relayId = "relay-1",
                        relaySecret = "secret-1",
                        relayExpiresAtEpochMillis = 9_999_999_999_999L,
                        relayNonce = "nonce-1",
                        relayScope = "public",
                    ),
                ),
                titleRes = R.string.status_relay_ready_title,
                detailRes = R.string.status_relay_ready_detail,
                runtimeName = runtimeName,
            ),
            HeroScenario(
                state = RuntimeUiState(
                    isConnected = true,
                    trustedRuntime = RuntimeTrustedRuntime(deviceId = "runtime-1", name = runtimeName),
                ),
                titleRes = R.string.status_connected_trusted_title,
                detailRes = R.string.status_connected_trusted_detail,
                runtimeName = runtimeName,
            ),
        )

        languageTags.forEach { nextLanguageTag ->
            scenarios.forEach { scenario ->
                compose.runOnUiThread {
                    languageTag.value = nextLanguageTag
                    heroScenario.value = scenario
                }
                compose.waitForIdle()

                val context = ApplicationProvider
                    .getApplicationContext<Context>()
                    .localizedContext(nextLanguageTag)
                val title = context.getString(scenario.titleRes)
                val detail = context.getString(scenario.detailRes, scenario.runtimeName)
                val summary = context.getString(
                    R.string.status_hero_accessibility_summary,
                    title,
                    detail,
                )
                compose.onNode(hasContentDescription(summary))
                    .assertIsDisplayed()
            }
        }
    }

    @Test
    fun settingsPairingScanQrActionExplainsDisabledConnectingState() {
        var scanClicks = 0

        compose.setContent {
            MaterialTheme {
                SettingsScreen(
                    state = RuntimeUiState(isConnecting = true),
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

        compose.onNode(
            hasText("Scan QR") and
                hasStateDescription("Wait for the current connection attempt before scanning again."),
        ).assertIsNotEnabled()

        assertEquals(0, scanClicks)
    }

    @Test
    fun settingsPairingConnectActionExplainsDisabledConnectingState() {
        var connectClicks = 0

        compose.setContent {
            MaterialTheme {
                SettingsScreen(
                    state = RuntimeUiState(
                        isConnecting = true,
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

        compose.onNode(
            hasText("Connecting") and
                hasStateDescription("Connection attempt in progress."),
        ).assertIsNotEnabled()

        assertEquals(0, connectClicks)
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

        compose.onNode(
            hasText("Pairing & Connection") and
                hasStateDescription("Collapsed") and
                hasClickActionLabel("Expand section"),
        )
            .assertIsDisplayed()
        compose.onAllNodesWithContentDescription(
            "Expand section",
            useUnmergedTree = true,
        ).assertCountEquals(0)
        compose.onNode(
            hasText("Pairing & Connection") and
                hasStateDescription("Collapsed") and
                hasClickActionLabel("Expand section"),
        )
            .performClick()

        compose.onNode(
            hasText("Pairing & Connection") and
                hasStateDescription("Expanded") and
                hasClickActionLabel("Collapse section"),
        )
            .assertIsDisplayed()
        compose.onAllNodesWithContentDescription(
            "Collapse section",
            useUnmergedTree = true,
        ).assertCountEquals(0)
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
    fun settingsTrustedRuntimeForgetActionNamesRuntimeAcrossSupportedLanguages() {
        val languageTags = listOf("en", "ko", "ja", "zh-CN", "fr")
        val currentLanguage = mutableStateOf(languageTags.first())
        val runtimeName = "Desk Runtime"

        compose.setContent {
            MaterialTheme {
                LocalizedTestContent(languageTag = currentLanguage.value) {
                    key(currentLanguage.value) {
                        SettingsScreen(
                            state = RuntimeUiState(
                                isConnected = true,
                                runtimeStatus = "authenticated",
                                trustedRuntime = RuntimeTrustedRuntime(
                                    deviceId = "runtime-1",
                                    name = runtimeName,
                                ),
                                selectedLanguageTag = currentLanguage.value,
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

        languageTags.forEach { languageTag ->
            val localizedContext = ApplicationProvider
                .getApplicationContext<Context>()
                .localizedContext(languageTag)
            val connectionSection = localizedContext.getString(R.string.status_title)
            val collapsedState = localizedContext.getString(R.string.section_state_collapsed)
            val expectedActionLabel = localizedContext.getString(
                R.string.forget_trusted_runtime_named,
                runtimeName,
            )

            compose.runOnUiThread {
                currentLanguage.value = languageTag
            }
            compose.waitForIdle()
            scrollUntilTextIsVisible(connectionSection)
            compose.onNode(hasText(connectionSection) and hasStateDescription(collapsedState))
                .performScrollTo()
                .performClick()
            compose.waitForIdle()

            compose.onNodeWithContentDescription(expectedActionLabel)
                .performScrollTo()
                .assertIsDisplayed()
                .assertIsEnabled()
        }
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
    fun navigationDrawerChatSearchFiltersClearsAndUsesHapticFeedback() {
        val hapticFeedback = RecordingHapticFeedback()
        val searchChanges = mutableListOf<String>()
        var clearClicks = 0
        val query = mutableStateOf("")
        val sessions = listOf(
            RuntimeChatSession(
                id = "session-trip",
                title = "Trip plan",
                modelId = "ollama:qwen3:8b",
                updatedAtMillis = 2_000L,
                messageCount = 4,
            ),
            RuntimeChatSession(
                id = "session-code",
                title = "Code review",
                modelId = "ollama:llama3.1:8b",
                updatedAtMillis = 1_000L,
                messageCount = 2,
            ),
        )

        compose.setContent {
            MaterialTheme {
                CompositionLocalProvider(LocalHapticFeedback provides hapticFeedback) {
                    Surface(modifier = Modifier.fillMaxSize()) {
                        val searchQuery = query.value
                        val filteredSessions = sessions.filter { session ->
                            session.title.orEmpty().contains(searchQuery, ignoreCase = true)
                        }
                        AetherLinkNavigationDrawerContent(
                            state = RuntimeUiState(
                                isConnected = true,
                                runtimeStatus = "authenticated",
                                trustedRuntime = RuntimeTrustedRuntime(
                                    deviceId = "runtime-1",
                                    name = "AetherLink Runtime",
                                ),
                                chatSessions = sessions,
                                activeChatSessionId = "session-trip",
                            ),
                            effectiveDestination = AppDestination.Chat,
                            chatSearchQuery = searchQuery,
                            hasAnyChatSessions = sessions.isNotEmpty(),
                            hasChatSearchQuery = searchQuery.isNotBlank(),
                            hasChatSearchResults = filteredSessions.isNotEmpty(),
                            filteredChatSessions = filteredSessions,
                            onChatSearchQueryChange = {
                                query.value = it
                                searchChanges += it
                            },
                            onClearChatSearch = {
                                clearClicks += 1
                                query.value = ""
                            },
                            onNewChat = {},
                            onSelectChatSession = {},
                            onRenameChatSession = {},
                            onArchiveChatSession = {},
                            onSelectSettings = {},
                        )
                    }
                }
            }
        }

        compose.onNodeWithTag(DRAWER_CHAT_SEARCH_TEST_TAG)
            .performScrollTo()
            .assertIsDisplayed()
            .performTextInput("missing")
        compose.waitForIdle()
        compose.onNodeWithText("No matching chats.")
            .performScrollTo()
            .assertIsDisplayed()
        compose.onNodeWithTag(DRAWER_CHAT_SEARCH_TEST_TAG)
            .performScrollTo()
        compose.onNodeWithContentDescription("Clear chat search for missing", useUnmergedTree = true)
            .assertIsDisplayed()
            .assert(hasClickActionLabel("Clear chat search for missing"))

        compose.runOnIdle {
            assertEquals("missing", searchChanges.last())
        }
        hapticFeedback.events.clear()
        compose.onNodeWithContentDescription("Clear chat search for missing", useUnmergedTree = true)
            .performClick()
        compose.waitForIdle()

        compose.runOnIdle {
            assertEquals(1, clearClicks)
            assertEquals("", query.value)
        }
        assertEquals(listOf(HapticFeedbackType.TextHandleMove), hapticFeedback.events)
        compose.onNodeWithText("Trip plan")
            .performScrollTo()
            .assertIsDisplayed()
        compose.onNodeWithText("Code review")
            .performScrollTo()
            .assertIsDisplayed()
        compose.onAllNodesWithText("No matching chats.").assertCountEquals(0)
    }

    @Test
    fun navigationDrawerChatSearchLocalizesClearAndNoResultsAcrossSupportedLanguages() {
        data class ExpectedSearchCopy(
            val languageTag: String,
            val searchLabel: String,
            val clearLabel: String,
            val noResults: String,
        )

        val searchQuery = "missing"
        val expectedCopies = listOf(
            ExpectedSearchCopy(
                languageTag = "en",
                searchLabel = "Search chats",
                clearLabel = "Clear chat search for missing",
                noResults = "No matching chats.",
            ),
            ExpectedSearchCopy(
                languageTag = "ko",
                searchLabel = "채팅 검색",
                clearLabel = "missing 검색어로 된 채팅 검색 지우기",
                noResults = "일치하는 채팅이 없습니다.",
            ),
            ExpectedSearchCopy(
                languageTag = "ja",
                searchLabel = "チャットを検索",
                clearLabel = "「missing」のチャット検索をクリア",
                noResults = "一致するチャットはありません。",
            ),
            ExpectedSearchCopy(
                languageTag = "zh-CN",
                searchLabel = "搜索聊天",
                clearLabel = "清除“missing”的聊天搜索",
                noResults = "没有匹配的聊天。",
            ),
            ExpectedSearchCopy(
                languageTag = "fr",
                searchLabel = "Rechercher des chats",
                clearLabel = "Effacer la recherche de chats pour missing",
                noResults = "Aucun chat correspondant.",
            ),
        )
        val currentCopy = mutableStateOf(expectedCopies.first())
        val sessions = listOf(
            RuntimeChatSession(
                id = "session-trip",
                title = "Trip plan",
                modelId = "ollama:qwen3:8b",
                updatedAtMillis = 2_000L,
                messageCount = 4,
            ),
        )

        compose.setContent {
            MaterialTheme {
                val expected = currentCopy.value
                LocalizedTestContent(languageTag = expected.languageTag) {
                    Surface(modifier = Modifier.fillMaxSize()) {
                        AetherLinkNavigationDrawerContent(
                            state = RuntimeUiState(
                                isConnected = true,
                                runtimeStatus = "authenticated",
                                trustedRuntime = RuntimeTrustedRuntime(
                                    deviceId = "runtime-1",
                                    name = "AetherLink Runtime",
                                ),
                                chatSessions = sessions,
                                activeChatSessionId = "session-trip",
                            ),
                            effectiveDestination = AppDestination.Chat,
                            chatSearchQuery = searchQuery,
                            hasAnyChatSessions = true,
                            hasChatSearchQuery = true,
                            hasChatSearchResults = false,
                            filteredChatSessions = emptyList(),
                            onChatSearchQueryChange = {},
                            onClearChatSearch = {},
                            onNewChat = {},
                            onSelectChatSession = {},
                            onRenameChatSession = {},
                            onArchiveChatSession = {},
                            onSelectSettings = {},
                        )
                    }
                }
            }
        }

        expectedCopies.forEach { expected ->
            compose.runOnUiThread {
                currentCopy.value = expected
            }
            compose.waitForIdle()
            compose.onNodeWithTag(DRAWER_CHAT_SEARCH_TEST_TAG)
                .performScrollTo()
                .assertIsDisplayed()
            compose.onNodeWithText(expected.searchLabel).assertIsDisplayed()
            compose.onNodeWithText(expected.noResults)
                .performScrollTo()
                .assertIsDisplayed()
            compose.onNodeWithTag(DRAWER_CHAT_SEARCH_TEST_TAG)
                .performScrollTo()
            compose.onNodeWithContentDescription(expected.clearLabel, useUnmergedTree = true)
                .assertIsDisplayed()
        }
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

        compose.onNode(
            hasContentDescription("Open navigation menu") and
                hasClickActionLabel("Open navigation menu"),
        ).assertIsDisplayed().performClick()
        compose.onNodeWithText("Qwen3 8B").assertIsDisplayed()
        compose.onNode(
            hasContentDescription("New Chat") and
                hasStateDescription("Ready to start a new chat.") and
                hasClickActionLabel("New Chat"),
        )
            .assertIsDisplayed()
            .performClick()
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
    fun newChatActionsExplainDisabledStreamingStateAcrossSupportedLanguages() {
        data class ExpectedNewChatState(
            val languageTag: String,
            val label: String,
            val disabledState: String,
        )

        val expectedStates = listOf(
            ExpectedNewChatState(
                languageTag = "en",
                label = "New Chat",
                disabledState = "Wait for the current response or cancel it before starting a new chat.",
            ),
            ExpectedNewChatState(
                languageTag = "ko",
                label = "새 채팅",
                disabledState = "새 채팅을 시작하기 전에 현재 응답을 기다리거나 취소하세요.",
            ),
            ExpectedNewChatState(
                languageTag = "ja",
                label = "新しいチャット",
                disabledState = "新しいチャットを開始する前に、現在の応答を待つかキャンセルしてください。",
            ),
            ExpectedNewChatState(
                languageTag = "zh-CN",
                label = "新聊天",
                disabledState = "开始新聊天前，请等待当前回复完成或取消它。",
            ),
            ExpectedNewChatState(
                languageTag = "fr",
                label = "Nouveau chat",
                disabledState = "Attendez la réponse en cours ou annulez-la avant de démarrer un nouveau chat.",
            ),
        )
        val currentState = mutableStateOf(expectedStates.first())
        var topBarNewChatClicks = 0
        var drawerNewChatClicks = 0

        compose.setContent {
            MaterialTheme {
                val expected = currentState.value
                LocalizedTestContent(languageTag = expected.languageTag) {
                    key(expected.languageTag) {
                        Column {
                            AetherLinkTopAppBar(
                                state = RuntimeUiState(
                                    isConnected = true,
                                    runtimeStatus = "authenticated",
                                    backendAvailable = true,
                                    trustedRuntime = RuntimeTrustedRuntime(
                                        deviceId = "runtime-1",
                                        name = "AetherLink Runtime",
                                    ),
                                    isStreaming = true,
                                ),
                                effectiveDestination = AppDestination.Chat,
                                destinationTitle = "Chat",
                                onOpenNavigation = {},
                                onStartNewChat = { topBarNewChatClicks++ },
                                onRequestModels = {},
                                onSelectModel = {},
                            )
                            AetherLinkNavigationDrawerContent(
                                state = RuntimeUiState(
                                    isConnected = true,
                                    runtimeStatus = "authenticated",
                                    trustedRuntime = RuntimeTrustedRuntime(
                                        deviceId = "runtime-1",
                                        name = "AetherLink Runtime",
                                    ),
                                    isStreaming = true,
                                ),
                                effectiveDestination = AppDestination.Chat,
                                chatSearchQuery = "",
                                hasAnyChatSessions = false,
                                hasChatSearchQuery = false,
                                hasChatSearchResults = false,
                                filteredChatSessions = emptyList(),
                                onChatSearchQueryChange = {},
                                onClearChatSearch = {},
                                onNewChat = { drawerNewChatClicks++ },
                                onSelectChatSession = {},
                                onRenameChatSession = {},
                                onArchiveChatSession = {},
                                onSelectSettings = {},
                            )
                        }
                    }
                }
            }
        }

        expectedStates.forEach { expected ->
            compose.runOnUiThread {
                currentState.value = expected
            }
            compose.waitForIdle()

            compose.onNode(
                hasContentDescription(expected.label) and hasStateDescription(expected.disabledState),
            )
                .assertIsDisplayed()
                .assertIsNotEnabled()
            compose.onNode(
                hasText(expected.label) and hasStateDescription(expected.disabledState),
            )
                .assertIsDisplayed()
                .assertIsNotEnabled()
        }

        assertEquals(0, topBarNewChatClicks)
        assertEquals(0, drawerNewChatClicks)
    }

    @Test
    fun newChatActionsExplainPairingRequiredStateAcrossSupportedLanguages() {
        data class ExpectedNewChatState(
            val languageTag: String,
            val label: String,
            val disabledState: String,
        )

        val expectedStates = listOf(
            ExpectedNewChatState(
                languageTag = "en",
                label = "New Chat",
                disabledState = "Pair with AetherLink Runtime before starting a new chat.",
            ),
            ExpectedNewChatState(
                languageTag = "ko",
                label = "새 채팅",
                disabledState = "새 채팅을 시작하기 전에 AetherLink Runtime과 페어링하세요.",
            ),
            ExpectedNewChatState(
                languageTag = "ja",
                label = "新しいチャット",
                disabledState = "新しいチャットを開始する前に AetherLink Runtime とペアリングしてください。",
            ),
            ExpectedNewChatState(
                languageTag = "zh-CN",
                label = "新聊天",
                disabledState = "开始新聊天前，请先与 AetherLink Runtime 配对。",
            ),
            ExpectedNewChatState(
                languageTag = "fr",
                label = "Nouveau chat",
                disabledState = "Jumelez AetherLink Runtime avant de démarrer un nouveau chat.",
            ),
        )
        val currentState = mutableStateOf(expectedStates.first())
        var topBarNewChatClicks = 0
        var drawerNewChatClicks = 0

        compose.setContent {
            MaterialTheme {
                val expected = currentState.value
                LocalizedTestContent(languageTag = expected.languageTag) {
                    key(expected.languageTag) {
                        Column {
                            AetherLinkTopAppBar(
                                state = RuntimeUiState(),
                                effectiveDestination = AppDestination.Chat,
                                destinationTitle = "Chat",
                                onOpenNavigation = {},
                                onStartNewChat = { topBarNewChatClicks++ },
                                onRequestModels = {},
                                onSelectModel = {},
                            )
                            AetherLinkNavigationDrawerContent(
                                state = RuntimeUiState(),
                                effectiveDestination = AppDestination.Settings,
                                chatSearchQuery = "",
                                hasAnyChatSessions = false,
                                hasChatSearchQuery = false,
                                hasChatSearchResults = false,
                                filteredChatSessions = emptyList(),
                                onChatSearchQueryChange = {},
                                onClearChatSearch = {},
                                onNewChat = { drawerNewChatClicks++ },
                                onSelectChatSession = {},
                                onRenameChatSession = {},
                                onArchiveChatSession = {},
                                onSelectSettings = {},
                            )
                        }
                    }
                }
            }
        }

        expectedStates.forEach { expected ->
            compose.runOnUiThread {
                currentState.value = expected
            }
            compose.waitForIdle()

            compose.onNode(
                hasContentDescription(expected.label) and hasStateDescription(expected.disabledState),
            )
                .assertIsDisplayed()
                .assertIsNotEnabled()
            compose.onNode(
                hasText(expected.label) and hasStateDescription(expected.disabledState),
            )
                .assertIsDisplayed()
                .assertIsNotEnabled()
        }

        assertEquals(0, topBarNewChatClicks)
        assertEquals(0, drawerNewChatClicks)
    }

    @Test
    fun permanentNavigationRailUsesNewChatPairingGateAndHaptics() {
        val hapticFeedback = RecordingHapticFeedback()
        var newChatClicks = 0
        val selectedDestinations = mutableListOf<AppDestination>()
        val pairingRequiredState = "Pair with AetherLink Runtime before starting a new chat."
        val newChatEnabledState = mutableStateOf(false)
        val newChatStateDescription = mutableStateOf(pairingRequiredState)

        compose.setContent {
            CompositionLocalProvider(LocalHapticFeedback provides hapticFeedback) {
                MaterialTheme {
                    AetherLinkPermanentNavigationRail(
                        selectedDestination = AppDestination.Chat,
                        newChatEnabled = newChatEnabledState.value,
                        newChatStateDescription = newChatStateDescription.value,
                        onNewChat = { newChatClicks += 1 },
                        onSelectDestination = { selectedDestinations += it },
                    )
                }
            }
        }

        compose.onNode(
            hasContentDescription("New Chat") and
                hasStateDescription(pairingRequiredState) and
                hasClickActionLabel("New Chat"),
        )
            .assertIsDisplayed()
            .assertIsNotEnabled()
        compose.runOnUiThread {
            newChatEnabledState.value = true
            newChatStateDescription.value = "Ready to start a new chat."
        }
        compose.waitForIdle()
        compose.onNode(
            hasContentDescription("New Chat") and
                hasStateDescription("Ready to start a new chat.") and
                hasClickActionLabel("New Chat"),
        )
            .assertIsDisplayed()
            .assertIsEnabled()
            .performClick()
        compose.onAllNodesWithText("Settings")
            .onFirst()
            .performClick()

        assertEquals(1, newChatClicks)
        assertEquals(listOf(AppDestination.Settings), selectedDestinations)
        assertEquals(
            listOf(
                HapticFeedbackType.TextHandleMove,
                HapticFeedbackType.TextHandleMove,
            ),
            hapticFeedback.events,
        )
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
        val pendingDetail =
            "This QR identified AetherLink Runtime, but it cannot reconnect across networks without protected connection details. Generate the latest QR in AetherLink Runtime and scan it again."
        compose.onAllNodesWithText(pendingDetail).onFirst().assertExists()
        compose.onNodeWithText("Waiting for AetherLink Runtime").assertExists()
        compose.onNode(
            hasContentDescription("QR scanned. $pendingDetail Waiting for AetherLink Runtime") and
                hasPoliteLiveRegion(),
            useUnmergedTree = true,
        ).assertExists()
        compose.onAllNodesWithText("Scan latest QR").onFirst().assertExists()
    }

    @Test
    fun settingsScreenAnnouncesRouteRefreshSavedNotice() {
        compose.setContent {
            MaterialTheme {
                SettingsScreen(
                    state = RuntimeUiState(
                        routeRefreshNoticeRuntimeName = "AetherLink Runtime",
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

        val notice = "Latest QR saved for AetherLink Runtime. Restoring the trusted connection."
        compose.onNodeWithText(notice).assertExists()
        compose.onNode(
            hasContentDescription(notice) and
                hasPoliteLiveRegion(),
            useUnmergedTree = true,
        ).assertExists()
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
    fun connectionStatusConnectedActionsExplainStateAcrossSupportedLanguages() {
        data class ExpectedCopy(
            val languageTag: String,
            val refreshAction: String,
            val refreshState: String,
            val disconnectAction: String,
            val disconnectState: String,
        )

        val expectedCopies = listOf(
            ExpectedCopy(
                languageTag = "en",
                refreshAction = "Refresh health",
                refreshState = "Ready to refresh runtime health.",
                disconnectAction = "Disconnect",
                disconnectState = "Ready to disconnect from the trusted runtime.",
            ),
            ExpectedCopy(
                languageTag = "ko",
                refreshAction = "상태 새로고침",
                refreshState = "런타임 상태를 새로고침할 준비가 되었습니다.",
                disconnectAction = "연결 해제",
                disconnectState = "신뢰된 런타임 연결을 해제할 준비가 되었습니다.",
            ),
            ExpectedCopy(
                languageTag = "ja",
                refreshAction = "ヘルスを更新",
                refreshState = "ランタイムのヘルスを更新できます。",
                disconnectAction = "切断",
                disconnectState = "信頼済みランタイムから切断できます。",
            ),
            ExpectedCopy(
                languageTag = "zh-CN",
                refreshAction = "刷新健康状态",
                refreshState = "可以刷新运行时健康状态。",
                disconnectAction = "断开连接",
                disconnectState = "可以断开受信任运行时连接。",
            ),
            ExpectedCopy(
                languageTag = "fr",
                refreshAction = "Actualiser l’état",
                refreshState = "Prêt à actualiser l’état du runtime.",
                disconnectAction = "Déconnecter",
                disconnectState = "Prêt à se déconnecter du runtime de confiance.",
            ),
        )
        val currentCase = mutableStateOf(expectedCopies.first())

        compose.setContent {
            MaterialTheme {
                LocalizedTestContent(languageTag = currentCase.value.languageTag) {
                    key(currentCase.value.languageTag) {
                        ConnectionStatusScreen(
                            state = RuntimeUiState(
                                isConnected = true,
                                backendAvailable = true,
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

        expectedCopies.forEach { expected ->
            compose.runOnUiThread {
                currentCase.value = expected
            }
            compose.waitForIdle()
            repeat(3) {
                compose.onRoot().performTouchInput { swipeUp() }
                compose.waitForIdle()
            }

            compose.onNodeWithText(expected.refreshAction)
                .assertIsDisplayed()
            compose.onNode(hasStateDescription(expected.refreshState) and hasClickAction())
                .assertIsDisplayed()
                .assertIsEnabled()
            compose.onNodeWithText(expected.disconnectAction)
                .assertIsDisplayed()
            compose.onNode(hasStateDescription(expected.disconnectState) and hasClickAction())
                .assertIsDisplayed()
                .assertIsEnabled()
        }
    }

    @Test
    fun connectionStatusProviderRowsExposeLocalizedAccessibilitySummariesAcrossSupportedLanguages() {
        data class ExpectedProviderRowCopy(
            val languageTag: String,
            val availableSummary: String,
            val unavailableRetryableSummary: String,
            val unavailableNonRetryableSummary: String,
        )

        val expectedCopies = listOf(
            ExpectedProviderRowCopy(
                languageTag = "en",
                availableSummary = "Ollama, Ready. Ollama is responding through AetherLink Runtime.",
                unavailableRetryableSummary = "LM Studio, Unavailable. LM Studio is not responding through the runtime. Check the provider in AetherLink Runtime, then refresh health. Try again after the provider is running.",
                unavailableNonRetryableSummary = "Custom Provider, Unavailable. Custom Provider is not responding through the runtime. Check the provider in AetherLink Runtime, then refresh health.",
            ),
            ExpectedProviderRowCopy(
                languageTag = "ko",
                availableSummary = "Ollama, 준비됨. Ollama이(가) AetherLink Runtime을 통해 응답 중입니다.",
                unavailableRetryableSummary = "LM Studio, 사용 불가. LM Studio가 런타임을 통해 응답하지 않습니다. AetherLink Runtime에서 제공자 상태를 확인한 다음 상태를 새로고침하세요. 제공자를 실행한 뒤 다시 시도할 수 있습니다.",
                unavailableNonRetryableSummary = "Custom Provider, 사용 불가. Custom Provider이(가) 런타임을 통해 응답하지 않습니다. AetherLink Runtime에서 제공자 상태를 확인한 다음 상태를 새로고침하세요.",
            ),
            ExpectedProviderRowCopy(
                languageTag = "ja",
                availableSummary = "Ollama、準備完了。Ollama は AetherLink Runtime 経由で応答しています。",
                unavailableRetryableSummary = "LM Studio、利用不可。LM Studio がランタイム経由で応答していません。AetherLink Runtime でプロバイダー状態を確認し、ヘルスを更新してください。プロバイダーを起動した後に再試行できます。",
                unavailableNonRetryableSummary = "Custom Provider、利用不可。Custom Provider がランタイム経由で応答していません。AetherLink Runtime でプロバイダー状態を確認し、ヘルスを更新してください。",
            ),
            ExpectedProviderRowCopy(
                languageTag = "zh-CN",
                availableSummary = "Ollama，就绪。Ollama 正通过 AetherLink Runtime 响应。",
                unavailableRetryableSummary = "LM Studio，不可用。LM Studio 未通过运行时响应。请在 AetherLink Runtime 中检查提供方状态，然后刷新健康状态。提供方运行后可以重试。",
                unavailableNonRetryableSummary = "Custom Provider，不可用。Custom Provider 未通过运行时响应。请在 AetherLink Runtime 中检查提供方状态，然后刷新健康状态。",
            ),
            ExpectedProviderRowCopy(
                languageTag = "fr",
                availableSummary = "Ollama, Prêt. Ollama répond via AetherLink Runtime.",
                unavailableRetryableSummary = "LM Studio, Indisponible. LM Studio ne répond pas via le runtime. Vérifiez le fournisseur dans AetherLink Runtime, puis actualisez l’état. Réessayez une fois le fournisseur lancé.",
                unavailableNonRetryableSummary = "Custom Provider, Indisponible. Custom Provider ne répond pas via le runtime. Vérifiez le fournisseur dans AetherLink Runtime, puis actualisez l’état.",
            ),
        )
        val currentCase = mutableStateOf(expectedCopies.first())

        compose.setContent {
            MaterialTheme {
                LocalizedTestContent(languageTag = currentCase.value.languageTag) {
                    key(currentCase.value.languageTag) {
                        ConnectionStatusScreen(
                            state = RuntimeUiState(
                                isConnected = true,
                                backendAvailable = false,
                                providerStatuses = listOf(
                                    RuntimeProviderStatus(
                                        id = "ollama",
                                        name = "Ollama",
                                        available = true,
                                    ),
                                    RuntimeProviderStatus(
                                        id = "lm_studio",
                                        name = "LM Studio",
                                        available = false,
                                        retryable = true,
                                    ),
                                    RuntimeProviderStatus(
                                        id = "custom",
                                        name = "Custom Provider",
                                        available = false,
                                        retryable = false,
                                    ),
                                ),
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

        expectedCopies.forEach { expected ->
            compose.runOnUiThread {
                currentCase.value = expected
            }
            compose.waitForIdle()

            compose.onNode(
                hasContentDescription(expected.availableSummary),
                useUnmergedTree = true,
            ).assertExists()
            compose.onNode(
                hasContentDescription(expected.unavailableRetryableSummary),
                useUnmergedTree = true,
            ).assertExists()
            compose.onNode(
                hasContentDescription(expected.unavailableNonRetryableSummary),
                useUnmergedTree = true,
            ).assertExists()
        }
    }

    @Test
    fun connectionStatusProviderDiagnosticsToggleExposesExpandedState() {
        val hapticFeedback = RecordingHapticFeedback()

        compose.setContent {
            CompositionLocalProvider(LocalHapticFeedback provides hapticFeedback) {
                MaterialTheme {
                    ConnectionStatusScreen(
                        state = RuntimeUiState(
                            isConnected = true,
                            backendAvailable = false,
                            providerStatuses = listOf(
                                RuntimeProviderStatus(
                                    id = "ollama",
                                    name = "Ollama",
                                    available = false,
                                    message = "Connection refused",
                                    code = "provider_unavailable",
                                    retryable = true,
                                ),
                                RuntimeProviderStatus(
                                    id = "lm-studio",
                                    name = "LM Studio",
                                    available = false,
                                    message = "Server stopped",
                                    code = "provider_stopped",
                                    retryable = true,
                                ),
                            ),
                        ),
                        onConnect = {},
                        onRefreshHealth = {},
                        onDisconnect = {},
                        onScanLatestQr = {},
                    )
                }
            }
        }

        scrollUntilTextIsVisible("Show details")
        compose.onNode(
            hasText("Show details") and
                hasContentDescription("Show details for Ollama") and
                hasStateDescription("Collapsed") and
                hasClickAction(),
        )
            .performScrollTo()
            .assertIsDisplayed()
            .performClick()
        compose.waitForIdle()

        assertEquals(listOf(HapticFeedbackType.TextHandleMove), hapticFeedback.events)
        compose.onNode(
            hasText("Hide details") and
                hasContentDescription("Hide details for Ollama") and
                hasStateDescription("Expanded") and
                hasClickAction(),
        )
            .performScrollTo()
            .assertIsDisplayed()
        compose.onNode(
            hasText("Show details") and
                hasContentDescription("Show details for LM Studio") and
                hasStateDescription("Collapsed") and
                hasClickAction(),
        )
            .performScrollTo()
            .assertIsDisplayed()
        compose.onNodeWithText("Status detail: Connection refused")
            .performScrollTo()
            .assertIsDisplayed()
        compose.onNodeWithText("Reference code: provider_unavailable")
            .performScrollTo()
            .assertIsDisplayed()
        compose.onAllNodesWithText("Status detail: Server stopped").assertCountEquals(0)

        compose.onNode(
            hasText("Show details") and
                hasContentDescription("Show details for LM Studio") and
                hasStateDescription("Collapsed") and
                hasClickAction(),
        )
            .performScrollTo()
            .performClick()
        compose.waitForIdle()

        compose.onNode(
            hasText("Hide details") and
                hasContentDescription("Hide details for LM Studio") and
                hasStateDescription("Expanded") and
                hasClickAction(),
        )
            .performScrollTo()
            .assertIsDisplayed()
        compose.onNodeWithText("Status detail: Server stopped")
            .performScrollTo()
            .assertIsDisplayed()
        compose.onNodeWithText("Reference code: provider_stopped")
            .performScrollTo()
            .assertIsDisplayed()
    }

    @Test
    fun connectionStatusScreenShowsPlatformNeutralConnectGuidanceAcrossSupportedLanguages() {
        data class ExpectedConnectionCopy(
            val languageTag: String,
            val savedRouteDetail: String,
            val autoReconnectPaused: String,
        )

        val expectedCopies = listOf(
            ExpectedConnectionCopy(
                languageTag = "en",
                savedRouteDetail = "Use Connect to restore Desk Runtime.",
                autoReconnectPaused = "Auto reconnect is paused. Use Connect to resume trusted runtime restore.",
            ),
            ExpectedConnectionCopy(
                languageTag = "ko",
                savedRouteDetail = "연결을 사용해 Desk Runtime에 다시 연결하세요.",
                autoReconnectPaused = "자동 재연결이 일시 중지되었습니다. 연결을 사용하면 신뢰된 런타임 복구가 다시 켜집니다.",
            ),
            ExpectedConnectionCopy(
                languageTag = "ja",
                savedRouteDetail = "接続を使って Desk Runtime を復元します。",
                autoReconnectPaused = "自動再接続は一時停止中です。接続を使うと、信頼済みランタイムの復元を再開します。",
            ),
            ExpectedConnectionCopy(
                languageTag = "zh-CN",
                savedRouteDetail = "使用“连接”以恢复 Desk Runtime。",
                autoReconnectPaused = "自动重连已暂停。使用“连接”可恢复受信任运行时恢复。",
            ),
            ExpectedConnectionCopy(
                languageTag = "fr",
                savedRouteDetail = "Utilisez Connecter pour restaurer Desk Runtime.",
                autoReconnectPaused = "Reconnexion en pause. Utilisez Connecter pour restaurer le runtime.",
            ),
        )
        val currentCopy = mutableStateOf(expectedCopies.first())

        compose.setContent {
            MaterialTheme {
                val expected = currentCopy.value
                LocalizedTestContent(languageTag = expected.languageTag) {
                    ConnectionStatusScreen(
                        state = RuntimeUiState(
                            trustedRuntime = RuntimeTrustedRuntime(
                                deviceId = "runtime-1",
                                name = "Desk Runtime",
                                endpointHint = RuntimeEndpointHint(
                                    host = "192.0.2.10",
                                    port = 43170,
                                    source = RuntimeEndpointSource.TrustedLastKnown,
                                ),
                            ),
                            trustedRuntimeAutoReconnectEnabled = false,
                            backendAvailable = true,
                        ),
                        onConnect = {},
                        onRefreshHealth = {},
                        onDisconnect = {},
                        onScanLatestQr = {},
                    )
                }
            }
        }

        expectedCopies.forEach { expected ->
            compose.runOnUiThread {
                currentCopy.value = expected
            }
            compose.waitForIdle()

            compose.onNodeWithText(expected.savedRouteDetail)
                .performScrollTo()
                .assertIsDisplayed()
            compose.onNodeWithText(expected.autoReconnectPaused)
                .performScrollTo()
                .assertIsDisplayed()
        }
        compose.onAllNodesWithText("Tap Connect to restore Desk Runtime.").assertCountEquals(0)
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

        compose.onNode(
            hasStateDescription("Saved connection") and
                hasClickAction() and
                hasClickActionLabel("Connect trusted route"),
            useUnmergedTree = true,
        )
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

        compose.onNode(
            hasStateDescription("Refresh needed") and
                hasClickAction() and
                hasClickActionLabel("Scan latest QR"),
            useUnmergedTree = true,
        )
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
            .assert(
                hasStateDescription("Off") and
                    hasClickActionLabel("Enable Connection troubleshooting")
            )
        assertNoVisibleText("Diagnostic QR text")
        assertNoVisibleText("Enter QR text")
        assertNoVisibleText("USB connection")
        assertNoVisibleText("Emulator connection")
        assertNoVisibleText("Connection address")
        assertNoVisibleText("Connection port")

        compose.onNodeWithTag(DEVELOPER_DIAGNOSTICS_TOGGLE_ROW_TAG).performClick()
        compose.waitForIdle()
        compose.onNodeWithTag(DEVELOPER_DIAGNOSTICS_SWITCH_ENABLED_TAG, useUnmergedTree = true)
            .assert(
                hasStateDescription("On") and
                    hasClickActionLabel("Disable Connection troubleshooting")
            )
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
                hasClickAction() and
                hasClickActionLabel("Show troubleshooting"),
        )
        endpointToggle
            .assert(SemanticsMatcher.expectValue(SemanticsProperties.Role, Role.Button))
            .performClick()

        compose.waitForIdle()
        compose.onNode(
            hasContentDescription("Connection troubleshooting") and
                hasStateDescription("Expanded") and
                hasClickAction() and
                hasClickActionLabel("Hide troubleshooting"),
        ).assert(SemanticsMatcher.expectValue(SemanticsProperties.Role, Role.Button))
        compose.onNodeWithText("USB connection").assertIsDisplayed()
        compose.onNodeWithText("Emulator connection").assertIsDisplayed()
        compose.onNodeWithText("Connection address").assertIsDisplayed()
        compose.onNodeWithText("Connection port").assertIsDisplayed()
    }

    @Test
    fun diagnosticQrTextDialogExplainsEmptyInvalidAndReadyStates() {
        val submittedPayloads = mutableListOf<String>()
        val invalidPayload = "https://example.test/pair?pairing_code=123456"
        val validPayload = "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
            "&runtime_device_id=runtime-1&runtime_key_fingerprint=fingerprint-1"

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
                    onSubmitPairingPayload = { submittedPayloads += it },
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
        compose.onNodeWithTag(DEVELOPER_DIAGNOSTICS_TOGGLE_ROW_TAG).performClick()
        compose.waitForIdle()
        compose.onNodeWithText("Diagnostic QR text")
            .performScrollTo()
            .assertIsDisplayed()
            .performClick()

        compose.onNode(hasSetTextAction() and hasStateDescription("Paste AetherLink Runtime QR text before continuing."))
            .assertIsDisplayed()
        compose.onNode(
            hasText("Use QR text") and
                hasStateDescription("Paste AetherLink Runtime QR text before continuing."),
        )
            .assertIsNotEnabled()

        compose.onNode(hasSetTextAction())
            .performTextInput(invalidPayload)
        compose.waitForIdle()
        compose.onNodeWithText("Use AetherLink Runtime QR text that starts with aetherlink://pair.")
            .assertIsDisplayed()
        compose.onNode(
            hasText("Use QR text") and
                hasStateDescription("Use AetherLink Runtime QR text that starts with aetherlink://pair."),
        )
            .assertIsNotEnabled()

        compose.onNode(hasSetTextAction())
            .performTextClearance()
        compose.onNode(hasSetTextAction())
            .performTextInput(validPayload)
        compose.waitForIdle()
        compose.onNodeWithText("Ready to use QR text.")
            .assertIsDisplayed()
        compose.onNode(
            hasText("Use QR text") and hasStateDescription("Ready to use QR text."),
        )
            .assertIsEnabled()
            .performClick()

        assertEquals(listOf(validPayload), submittedPayloads)
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
            .assert(
                hasStateDescription("On") and
                    hasClickActionLabel("Disable Auto reconnect")
            )

        autoReconnectEnabled.value = false
        compose.waitForIdle()
        compose.onNodeWithContentDescription("Auto reconnect", useUnmergedTree = true)
            .assert(
                hasStateDescription("Off") and
                    hasClickActionLabel("Enable Auto reconnect")
            )
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
    fun settingsDiscoveredRuntimeUnavailableRowsExposeContextualAccessibilityLabels() {
        val trustedRuntime = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            routeToken = "route-token-1",
        )
        val qrRequiredRuntime = RuntimeDiscoveredRuntime(
            serviceName = "Studio Runtime",
            host = "192.0.2.10",
            port = 43170,
        )
        val notTrustedRuntime = RuntimeDiscoveredRuntime(
            serviceName = "Desk Runtime",
            host = "192.0.2.11",
            port = 43170,
            routeToken = "route-token-2",
            deviceId = "runtime-2",
        )

        compose.setContent {
            MaterialTheme {
                SettingsScreen(
                    state = RuntimeUiState(
                        trustedRuntime = trustedRuntime,
                        discoveredRuntimes = listOf(qrRequiredRuntime, notTrustedRuntime),
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
            "Studio Runtime. Trust details hidden. QR required.",
        ).assertExists()
        scrollUntilTextIsVisible("Desk Runtime")
        compose.onNodeWithContentDescription(
            "Desk Runtime. Different trusted runtime. Not trusted.",
        ).assertExists()
    }

    @Test
    fun settingsDiscoveryActionsExplainIdleAndRunningStatesAcrossSupportedLanguages() {
        data class ExpectedCopy(
            val languageTag: String,
            val troubleshootingTitle: String,
            val expandSectionAction: String,
            val collapseSectionAction: String,
            val startLabel: String,
            val runningLabel: String,
            val stopLabel: String,
            val startReadyState: String,
            val startRunningState: String,
            val stopReadyState: String,
            val stopIdleState: String,
        )

        val expectedCopies = listOf(
            ExpectedCopy(
                languageTag = "en",
                troubleshootingTitle = "Troubleshooting",
                expandSectionAction = "Expand section",
                collapseSectionAction = "Collapse section",
                startLabel = "Find trusted routes",
                runningLabel = "Discovering runtimes",
                stopLabel = "Stop",
                startReadyState = "Ready to find trusted routes.",
                startRunningState = "Trusted route discovery is already running.",
                stopReadyState = "Ready to stop trusted route discovery.",
                stopIdleState = "Start trusted route discovery before stopping it.",
            ),
            ExpectedCopy(
                languageTag = "ko",
                troubleshootingTitle = "문제 해결",
                expandSectionAction = "섹션 펼치기",
                collapseSectionAction = "섹션 접기",
                startLabel = "신뢰된 경로 찾기",
                runningLabel = "런타임 검색 중",
                stopLabel = "중지",
                startReadyState = "신뢰된 경로를 찾을 준비가 되었습니다.",
                startRunningState = "신뢰된 경로 검색이 이미 진행 중입니다.",
                stopReadyState = "신뢰된 경로 검색을 중지할 수 있습니다.",
                stopIdleState = "중지하려면 먼저 신뢰된 경로 검색을 시작하세요.",
            ),
            ExpectedCopy(
                languageTag = "ja",
                troubleshootingTitle = "トラブルシューティング",
                expandSectionAction = "セクションを展開",
                collapseSectionAction = "セクションを折りたたむ",
                startLabel = "信頼済み経路を検索",
                runningLabel = "ランタイムを検出中",
                stopLabel = "停止",
                startReadyState = "信頼済み経路を検索できます。",
                startRunningState = "信頼済み経路の検索はすでに実行中です。",
                stopReadyState = "信頼済み経路の検索を停止できます。",
                stopIdleState = "停止する前に信頼済み経路の検索を開始してください。",
            ),
            ExpectedCopy(
                languageTag = "zh-CN",
                troubleshootingTitle = "故障排查",
                expandSectionAction = "展开分区",
                collapseSectionAction = "收起分区",
                startLabel = "查找可信路径",
                runningLabel = "正在发现运行时",
                stopLabel = "停止",
                startReadyState = "可以查找可信路径。",
                startRunningState = "可信路径发现已在运行。",
                stopReadyState = "可以停止可信路径发现。",
                stopIdleState = "请先开始可信路径发现，然后再停止。",
            ),
            ExpectedCopy(
                languageTag = "fr",
                troubleshootingTitle = "Dépannage",
                expandSectionAction = "Développer la section",
                collapseSectionAction = "Réduire la section",
                startLabel = "Chercher les routes de confiance",
                runningLabel = "Découverte des runtimes",
                stopLabel = "Arrêter",
                startReadyState = "Prêt à chercher des routes de confiance.",
                startRunningState = "La découverte des routes de confiance est déjà en cours.",
                stopReadyState = "Prêt à arrêter la découverte des routes de confiance.",
                stopIdleState = "Démarrez la découverte des routes de confiance avant de l’arrêter.",
            ),
        )
        val currentCase = mutableStateOf(expectedCopies.first())
        val isDiscovering = mutableStateOf(false)

        compose.setContent {
            MaterialTheme {
                LocalizedTestContent(languageTag = currentCase.value.languageTag) {
                    key(currentCase.value.languageTag) {
                        SettingsScreen(
                            state = RuntimeUiState(
                                isDiscovering = isDiscovering.value,
                                selectedLanguageTag = currentCase.value.languageTag,
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
                            showDeveloperDiagnostics = true,
                        )
                    }
                }
            }
        }

        expectedCopies.forEach { expected ->
            compose.runOnUiThread {
                currentCase.value = expected
                isDiscovering.value = false
            }
            compose.waitForIdle()
            scrollUntilTextIsVisible(expected.troubleshootingTitle)
            compose.onNode(
                hasText(expected.troubleshootingTitle) and
                    hasClickActionLabel(expected.expandSectionAction),
            )
                .performScrollTo()
                .performClick()
            compose.waitForIdle()
            compose.onNode(
                hasText(expected.troubleshootingTitle) and
                    hasClickActionLabel(expected.collapseSectionAction),
            )
                .performScrollTo()
                .assertIsDisplayed()
            compose.onNode(hasText(expected.startLabel) and hasStateDescription(expected.startReadyState))
                .performScrollTo()
                .assertIsEnabled()
            compose.onNode(hasText(expected.stopLabel) and hasStateDescription(expected.stopIdleState))
                .performScrollTo()
                .assertIsNotEnabled()

            compose.runOnUiThread {
                isDiscovering.value = true
            }
            compose.waitForIdle()
            compose.onNode(hasText(expected.runningLabel) and hasStateDescription(expected.startRunningState))
                .performScrollTo()
                .assertIsNotEnabled()
            compose.onNode(hasText(expected.stopLabel) and hasStateDescription(expected.stopReadyState))
                .performScrollTo()
                .assertIsEnabled()
        }
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

        compose.onNode(
            hasText("Manage all chats") and
                hasStateDescription("Collapsed") and
                hasClickActionLabel("Expand section"),
        )
            .performScrollTo()
            .assertIsDisplayed()
        assertNoVisibleText("Archive all chats")
        assertNoVisibleText("Permanently delete archived chats")

        compose.onNode(
            hasText("Manage all chats") and
                hasStateDescription("Collapsed") and
                hasClickActionLabel("Expand section"),
        )
            .performClick()
        compose.waitForIdle()
        scrollUntilTextIsVisible("Archive all chats")
        compose.onNode(
            hasText("Manage all chats") and
                hasStateDescription("Expanded") and
                hasClickActionLabel("Collapse section"),
        )
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
    fun settingsBulkChatHistoryActionsExplainStreamingDisabledStateAcrossSupportedLanguages() {
        data class ExpectedBulkCopy(
            val languageTag: String,
            val chatHistoryTitle: String,
            val bulkActionsTitle: String,
            val archiveAction: String,
            val archiveState: String,
            val deleteAction: String,
            val deleteState: String,
        )

        val expectedCopies = listOf(
            ExpectedBulkCopy(
                languageTag = "en",
                chatHistoryTitle = "Chat history",
                bulkActionsTitle = "Manage all chats",
                archiveAction = "Archive all chats",
                archiveState = "Wait for the current response before archiving chats.",
                deleteAction = "Permanently delete archived chats",
                deleteState = "Wait for the current response before permanently deleting archived chats.",
            ),
            ExpectedBulkCopy(
                languageTag = "ko",
                chatHistoryTitle = "채팅 기록",
                bulkActionsTitle = "전체 채팅 관리",
                archiveAction = "모든 채팅 보관",
                archiveState = "채팅을 보관하기 전에 현재 응답이 끝날 때까지 기다리세요.",
                deleteAction = "보관된 채팅 영구 삭제",
                deleteState = "보관된 채팅을 영구 삭제하기 전에 현재 응답이 끝날 때까지 기다리세요.",
            ),
            ExpectedBulkCopy(
                languageTag = "ja",
                chatHistoryTitle = "チャット履歴",
                bulkActionsTitle = "すべてのチャットを管理",
                archiveAction = "すべてのチャットをアーカイブ",
                archiveState = "チャットをアーカイブする前に、現在の応答が終わるまでお待ちください。",
                deleteAction = "アーカイブ済みチャットを完全に削除",
                deleteState = "アーカイブ済みチャットを完全に削除する前に、現在の応答が終わるまでお待ちください。",
            ),
            ExpectedBulkCopy(
                languageTag = "zh-CN",
                chatHistoryTitle = "聊天记录",
                bulkActionsTitle = "管理所有聊天",
                archiveAction = "归档所有聊天",
                archiveState = "归档聊天前，请等待当前回复完成。",
                deleteAction = "永久删除已归档聊天",
                deleteState = "永久删除已归档聊天前，请等待当前回复完成。",
            ),
            ExpectedBulkCopy(
                languageTag = "fr",
                chatHistoryTitle = "Historique des chats",
                bulkActionsTitle = "Gérer tous les chats",
                archiveAction = "Archiver tous les chats",
                archiveState = "Attendez la fin de la réponse en cours avant d’archiver les chats.",
                deleteAction = "Supprimer définitivement les chats archivés",
                deleteState = "Attendez la fin de la réponse en cours avant de supprimer définitivement les chats archivés.",
            ),
        )
        val currentCopy = mutableStateOf(expectedCopies.first())

        compose.setContent {
            MaterialTheme {
                val expected = currentCopy.value
                LocalizedTestContent(languageTag = expected.languageTag) {
                    SettingsScreen(
                        state = RuntimeUiState(
                            selectedLanguageTag = expected.languageTag,
                            isStreaming = true,
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
                                    messageCount = 3,
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
                        onArchiveAllChatSessions = {},
                        onPermanentlyDeleteArchivedChatSessions = {},
                        showDeveloperDiagnostics = false,
                    )
                }
            }
        }

        scrollUntilTextIsVisible(expectedCopies.first().chatHistoryTitle)
        compose.onNodeWithText(expectedCopies.first().chatHistoryTitle)
            .assertIsDisplayed()
            .performClick()
        compose.waitForIdle()
        scrollUntilTextIsVisible(expectedCopies.first().bulkActionsTitle)
        compose.onNode(hasText(expectedCopies.first().bulkActionsTitle) and hasStateDescription("Collapsed"))
            .performScrollTo()
            .performClick()
        compose.waitForIdle()

        expectedCopies.forEach { expected ->
            compose.runOnUiThread {
                currentCopy.value = expected
            }
            compose.waitForIdle()
            scrollUntilTextIsVisible(expected.archiveAction)
            compose.onNode(hasText(expected.archiveAction) and hasStateDescription(expected.archiveState))
                .performScrollTo()
                .assertIsNotEnabled()
            compose.onNode(hasText(expected.deleteAction) and hasStateDescription(expected.deleteState))
                .performScrollTo()
                .assertIsNotEnabled()
        }
    }

    @Test
    fun settingsPerChatHistoryActionsExplainStreamingDisabledStateAcrossSupportedLanguages() {
        val languageTags = listOf("en", "ko", "ja", "zh-CN", "fr")
        val languageTag = mutableStateOf(languageTags.first())
        val activeTitle = "Active project chat"
        val archivedTitle = "Archived project chat"

        compose.setContent {
            MaterialTheme {
                val selectedLanguageTag = languageTag.value
                LocalizedTestContent(languageTag = selectedLanguageTag) {
                    SettingsScreen(
                        state = RuntimeUiState(
                            selectedLanguageTag = selectedLanguageTag,
                            isStreaming = true,
                            chatSessions = listOf(
                                RuntimeChatSession(
                                    id = "active-chat",
                                    title = activeTitle,
                                    messageCount = 1,
                                    updatedAtMillis = 2_000L,
                                ),
                            ),
                            archivedChatSessions = listOf(
                                RuntimeChatSession(
                                    id = "archived-chat",
                                    title = archivedTitle,
                                    messageCount = 3,
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

        languageTags.forEach { nextLanguageTag ->
            compose.runOnUiThread {
                languageTag.value = nextLanguageTag
            }
            compose.waitForIdle()

            val context = ApplicationProvider
                .getApplicationContext<Context>()
                .localizedContext(nextLanguageTag)
            val disabledState = context.getString(R.string.chat_history_action_state_wait_for_stream)

            compose.onNode(
                hasContentDescription(context.getString(R.string.archive_chat_named, activeTitle)) and
                    hasClickActionLabel(context.getString(R.string.archive_chat_named, activeTitle)) and
                    hasStateDescription(disabledState),
                useUnmergedTree = true,
            )
                .performScrollTo()
                .assertIsNotEnabled()
            compose.onNode(
                hasContentDescription(context.getString(R.string.restore_chat_named, archivedTitle)) and
                    hasClickActionLabel(context.getString(R.string.restore_chat_named, archivedTitle)) and
                    hasStateDescription(disabledState),
                useUnmergedTree = true,
            )
                .performScrollTo()
                .assertIsNotEnabled()
            compose.onNode(
                hasContentDescription(context.getString(R.string.permanently_delete_chat_named, archivedTitle)) and
                    hasClickActionLabel(context.getString(R.string.permanently_delete_chat_named, archivedTitle)) and
                    hasStateDescription(disabledState),
                useUnmergedTree = true,
            )
                .performScrollTo()
                .assertIsNotEnabled()
        }
    }

    @Test
    fun settingsChatHistoryRowsExposeLocalizedAccessibilitySummaries() {
        val languageTags = listOf("en", "ko", "ja", "zh-CN", "fr")
        val languageTag = mutableStateOf(languageTags.first())
        val activeTitle = "Active project chat"
        val archivedTitle = "Archived project chat"

        compose.setContent {
            MaterialTheme {
                val selectedLanguageTag = languageTag.value
                LocalizedTestContent(languageTag = selectedLanguageTag) {
                    SettingsScreen(
                        state = RuntimeUiState(
                            selectedLanguageTag = selectedLanguageTag,
                            chatSessions = listOf(
                                RuntimeChatSession(
                                    id = "active-chat",
                                    title = activeTitle,
                                    messageCount = 1,
                                    updatedAtMillis = 2_000L,
                                ),
                            ),
                            archivedChatSessions = listOf(
                                RuntimeChatSession(
                                    id = "archived-chat",
                                    title = archivedTitle,
                                    messageCount = 3,
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

        languageTags.forEach { nextLanguageTag ->
            compose.runOnUiThread {
                languageTag.value = nextLanguageTag
            }
            compose.waitForIdle()

            val context = ApplicationProvider
                .getApplicationContext<Context>()
                .localizedContext(nextLanguageTag)
            val activeStatus = context.resources.getQuantityString(R.plurals.chat_message_count, 1, 1)
            val archivedStatus = context.getString(R.string.archived_chat)
            val activeSummary = context.getString(
                R.string.chat_session_row_summary,
                activeTitle,
                activeStatus,
            )
            val archivedSummary = context.getString(
                R.string.chat_session_row_summary,
                archivedTitle,
                archivedStatus,
            )

            compose.onNode(hasContentDescription(activeSummary), useUnmergedTree = true)
                .performScrollTo()
                .assertIsDisplayed()
            compose.onNode(hasContentDescription(archivedSummary), useUnmergedTree = true)
                .performScrollTo()
                .assertIsDisplayed()
        }
    }

    @Test
    fun settingsBulkChatHistoryActionsExplainMissingChatDisabledStates() {
        val uiState = mutableStateOf(
            RuntimeUiState(
                archivedChatSessions = listOf(
                    RuntimeChatSession(
                        id = "archived-chat",
                        title = "Archived project chat",
                        messageCount = 3,
                        archivedAtMillis = 3_000L,
                        updatedAtMillis = 3_000L,
                    ),
                ),
            ),
        )

        compose.setContent {
            MaterialTheme {
                SettingsScreen(
                    state = uiState.value,
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

        scrollUntilTextIsVisible("Chat history")
        compose.onNodeWithText("Chat history")
            .assertIsDisplayed()
            .performClick()
        compose.waitForIdle()
        scrollUntilTextIsVisible("Manage all chats")
        compose.onNode(hasText("Manage all chats") and hasStateDescription("Collapsed"))
            .performScrollTo()
            .performClick()
        compose.waitForIdle()

        scrollUntilTextIsVisible("Archive all chats")
        compose.onNode(hasText("Archive all chats") and hasStateDescription("No active chats to archive."))
            .performScrollTo()
            .assertIsNotEnabled()
        compose.onNode(
            hasText("Permanently delete archived chats") and
                hasStateDescription("Ready to permanently delete archived chats."),
        )
            .performScrollTo()
            .assertIsEnabled()

        compose.runOnUiThread {
            uiState.value = RuntimeUiState(
                chatSessions = listOf(
                    RuntimeChatSession(
                        id = "active-chat",
                        title = "Active project chat",
                        messageCount = 1,
                        updatedAtMillis = 2_000L,
                    ),
                ),
            )
        }
        compose.waitForIdle()

        compose.onNode(hasText("Archive all chats") and hasStateDescription("Ready to archive all active chats."))
            .performScrollTo()
            .assertIsEnabled()
        compose.onNode(
            hasText("Permanently delete archived chats") and
                hasStateDescription("No archived chats to permanently delete."),
        )
            .performScrollTo()
            .assertIsNotEnabled()
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
    fun renameChatSessionDialogExposesTitleReadinessAndHaptics() {
        val hapticFeedback = RecordingHapticFeedback()
        val title = mutableStateOf("")
        var confirmClicks = 0
        var dismissClicks = 0

        compose.setContent {
            MaterialTheme {
                CompositionLocalProvider(LocalHapticFeedback provides hapticFeedback) {
                    RenameChatSessionDialog(
                        title = title.value,
                        onTitleChange = { title.value = it },
                        onDismiss = { dismissClicks += 1 },
                        onConfirm = { confirmClicks += 1 },
                    )
                }
            }
        }

        compose.onNode(
            hasContentDescription("Chat title") and
                hasStateDescription("Enter a title before saving.") and
                hasSetTextAction(),
        ).assertIsDisplayed()

        compose.onNode(
            hasText("Save") and
                hasStateDescription("Enter a title before saving.") and
                hasClickAction(),
        ).assertIsNotEnabled()

        compose.onNode(hasContentDescription("Chat title") and hasSetTextAction())
            .performTextInput("Project Alpha")

        compose.onNode(
            hasContentDescription("Chat title") and
                hasStateDescription("Ready to save.") and
                hasSetTextAction(),
        ).assertIsDisplayed()

        hapticFeedback.events.clear()
        compose.onNode(
            hasText("Save") and
                hasStateDescription("Ready to save.") and
                hasClickAction(),
        ).assertIsEnabled().performClick()

        assertEquals(1, confirmClicks)
        assertEquals(0, dismissClicks)
        assertEquals(listOf(HapticFeedbackType.TextHandleMove), hapticFeedback.events)
    }

    @Test
    fun settingsChatHistorySearchClearsWithContextAndHapticFeedback() {
        val hapticFeedback = RecordingHapticFeedback()

        compose.setContent {
            MaterialTheme {
                CompositionLocalProvider(LocalHapticFeedback provides hapticFeedback) {
                    SettingsScreen(
                        state = RuntimeUiState(
                            chatSessions = listOf(
                                RuntimeChatSession(
                                    id = "session-trip",
                                    title = "Trip plan",
                                    messageCount = 4,
                                    updatedAtMillis = 2_000L,
                                ),
                                RuntimeChatSession(
                                    id = "session-code",
                                    title = "Code review",
                                    messageCount = 2,
                                    updatedAtMillis = 1_000L,
                                ),
                            ),
                            archivedChatSessions = listOf(
                                RuntimeChatSession(
                                    id = "session-archive",
                                    title = "Archived notes",
                                    messageCount = 8,
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
        compose.onNodeWithTag(SETTINGS_CHAT_HISTORY_SEARCH_TEST_TAG)
            .performScrollTo()
            .assertIsDisplayed()
            .performTextInput("missing")
        compose.waitForIdle()
        compose.onNodeWithText("No matching chats.")
            .performScrollTo()
            .assertIsDisplayed()
        compose.onNodeWithContentDescription("Clear chat search for missing", useUnmergedTree = true)
            .assertIsDisplayed()
            .assert(hasClickActionLabel("Clear chat search for missing"))

        hapticFeedback.events.clear()
        compose.onNodeWithContentDescription("Clear chat search for missing", useUnmergedTree = true)
            .performClick()
        compose.waitForIdle()

        assertEquals(listOf(HapticFeedbackType.TextHandleMove), hapticFeedback.events)
        compose.onNodeWithText("Trip plan")
            .performScrollTo()
            .assertIsDisplayed()
        compose.onNodeWithText("Code review")
            .performScrollTo()
            .assertIsDisplayed()
        compose.onNodeWithText("Archived notes")
            .performScrollTo()
            .assertIsDisplayed()
        compose.onAllNodesWithText("No matching chats.").assertCountEquals(0)
    }

    @Test
    fun settingsChatHistorySearchLocalizesClearAndNoResultsAcrossSupportedLanguages() {
        data class ExpectedSearchCopy(
            val languageTag: String,
            val searchLabel: String,
            val clearLabel: String,
            val noResults: String,
        )

        val searchQuery = "missing"
        val expectedCopies = listOf(
            ExpectedSearchCopy(
                languageTag = "en",
                searchLabel = "Search chats",
                clearLabel = "Clear chat search for missing",
                noResults = "No matching chats.",
            ),
            ExpectedSearchCopy(
                languageTag = "ko",
                searchLabel = "채팅 검색",
                clearLabel = "missing 검색어로 된 채팅 검색 지우기",
                noResults = "일치하는 채팅이 없습니다.",
            ),
            ExpectedSearchCopy(
                languageTag = "ja",
                searchLabel = "チャットを検索",
                clearLabel = "「missing」のチャット検索をクリア",
                noResults = "一致するチャットはありません。",
            ),
            ExpectedSearchCopy(
                languageTag = "zh-CN",
                searchLabel = "搜索聊天",
                clearLabel = "清除“missing”的聊天搜索",
                noResults = "没有匹配的聊天。",
            ),
            ExpectedSearchCopy(
                languageTag = "fr",
                searchLabel = "Rechercher des chats",
                clearLabel = "Effacer la recherche de chats pour missing",
                noResults = "Aucun chat correspondant.",
            ),
        )
        val currentCopy = mutableStateOf(expectedCopies.first())

        compose.setContent {
            MaterialTheme {
                val expected = currentCopy.value
                LocalizedTestContent(languageTag = expected.languageTag) {
                    SettingsScreen(
                        state = RuntimeUiState(
                            chatSessions = listOf(
                                RuntimeChatSession(
                                    id = "session-trip",
                                    title = "Trip plan",
                                    messageCount = 4,
                                    updatedAtMillis = 2_000L,
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
        compose.onNodeWithTag(SETTINGS_CHAT_HISTORY_SEARCH_TEST_TAG)
            .performScrollTo()
            .assertIsDisplayed()
            .performTextInput(searchQuery)

        expectedCopies.forEach { expected ->
            compose.runOnUiThread {
                currentCopy.value = expected
            }
            compose.waitForIdle()
            compose.onNodeWithTag(SETTINGS_CHAT_HISTORY_SEARCH_TEST_TAG)
                .performScrollTo()
                .assertIsDisplayed()
            compose.onNodeWithText(expected.searchLabel).assertIsDisplayed()
            compose.onNodeWithText(expected.noResults)
                .performScrollTo()
                .assertIsDisplayed()
            compose.onNodeWithContentDescription(expected.clearLabel, useUnmergedTree = true)
                .assertIsDisplayed()
                .assert(hasClickActionLabel(expected.clearLabel))
        }
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
    fun chatDrawerItemsLocalizeAccessibilitySummariesAcrossSupportedLanguages() {
        data class ExpectedSummary(
            val languageTag: String,
            val failedChat: String,
            val activeChat: String,
            val selectedChat: String,
        )

        val expectedSummaries = listOf(
            ExpectedSummary(
                languageTag = "en",
                failedChat = "Chat Trip plan. 3 messages - Needs attention.",
                activeChat = "Chat Connection notes. 2 messages - In progress.",
                selectedChat = "Selected chat One note. 1 message.",
            ),
            ExpectedSummary(
                languageTag = "ko",
                failedChat = "채팅 Trip plan. 메시지 3개 - 확인 필요.",
                activeChat = "채팅 Connection notes. 메시지 2개 - 진행 중.",
                selectedChat = "선택된 채팅 One note. 메시지 1개.",
            ),
            ExpectedSummary(
                languageTag = "ja",
                failedChat = "チャット「Trip plan」。メッセージ 3 件 - 確認が必要。",
                activeChat = "チャット「Connection notes」。メッセージ 2 件 - 進行中。",
                selectedChat = "選択中のチャット「One note」。メッセージ 1 件。",
            ),
            ExpectedSummary(
                languageTag = "zh-CN",
                failedChat = "聊天“Trip plan”。3 条消息 - 需要注意。",
                activeChat = "聊天“Connection notes”。2 条消息 - 进行中。",
                selectedChat = "已选择聊天“One note”。1 条消息。",
            ),
            ExpectedSummary(
                languageTag = "fr",
                failedChat = "Chat « Trip plan ». 3 messages - À vérifier.",
                activeChat = "Chat « Connection notes ». 2 messages - En cours.",
                selectedChat = "Chat sélectionné « One note ». 1 message.",
            ),
        )
        val currentSummary = mutableStateOf(expectedSummaries.first())

        compose.setContent {
            MaterialTheme {
                val expected = currentSummary.value
                LocalizedTestContent(languageTag = expected.languageTag) {
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
        }

        expectedSummaries.forEach { expected ->
            compose.runOnUiThread {
                currentSummary.value = expected
            }
            compose.waitForIdle()
            compose.onNodeWithContentDescription(expected.failedChat)
                .assertIsDisplayed()
            compose.onNodeWithContentDescription(expected.activeChat)
                .assertIsDisplayed()
            compose.onNodeWithContentDescription(expected.selectedChat)
                .assertIsDisplayed()
        }
    }

    @Test
    fun chatDrawerOverflowMenuActionsKeepChatContextAcrossSupportedLanguages() {
        data class ExpectedMenuCopy(
            val languageTag: String,
            val options: String,
            val rename: String,
            val archive: String,
            val restore: String,
            val delete: String,
        )

        val expectedCopies = listOf(
            ExpectedMenuCopy(
                languageTag = "en",
                options = "Chat options for Trip plan",
                rename = "Rename chat Trip plan",
                archive = "Archive chat Trip plan",
                restore = "Restore chat Trip plan",
                delete = "Delete chat Trip plan",
            ),
            ExpectedMenuCopy(
                languageTag = "ko",
                options = "Trip plan 채팅 옵션",
                rename = "Trip plan 채팅 이름 변경",
                archive = "Trip plan 채팅 보관",
                restore = "Trip plan 채팅 복원",
                delete = "Trip plan 채팅 삭제",
            ),
            ExpectedMenuCopy(
                languageTag = "ja",
                options = "「Trip plan」のチャットオプション",
                rename = "「Trip plan」の名前を変更",
                archive = "「Trip plan」をアーカイブ",
                restore = "「Trip plan」を復元",
                delete = "「Trip plan」を削除",
            ),
            ExpectedMenuCopy(
                languageTag = "zh-CN",
                options = "聊天“Trip plan”的选项",
                rename = "重命名聊天“Trip plan”",
                archive = "归档聊天“Trip plan”",
                restore = "恢复聊天“Trip plan”",
                delete = "删除聊天“Trip plan”",
            ),
            ExpectedMenuCopy(
                languageTag = "fr",
                options = "Options du chat « Trip plan »",
                rename = "Renommer le chat « Trip plan »",
                archive = "Archiver le chat « Trip plan »",
                restore = "Restaurer le chat « Trip plan »",
                delete = "Supprimer le chat « Trip plan »",
            ),
        )
        val currentCopy = mutableStateOf(expectedCopies.first())
        var renameClicks = 0
        var archiveClicks = 0
        var restoreClicks = 0
        var deleteClicks = 0

        compose.setContent {
            MaterialTheme {
                val expected = currentCopy.value
                LocalizedTestContent(languageTag = expected.languageTag) {
                    ChatSessionDrawerItem(
                        session = RuntimeChatSession(
                            id = "trip-chat",
                            title = "Trip plan",
                            updatedAtMillis = 2_000L,
                            messageCount = 4,
                        ),
                        selected = false,
                        enabled = true,
                        onClick = {},
                        onRename = { renameClicks += 1 },
                        onArchive = { archiveClicks += 1 },
                        onRestore = { restoreClicks += 1 },
                        onDelete = { deleteClicks += 1 },
                    )
                }
            }
        }

        expectedCopies.forEachIndexed { index, expected ->
            compose.runOnUiThread {
                currentCopy.value = expected
            }
            compose.waitForIdle()

            compose.onNodeWithContentDescription(expected.options, useUnmergedTree = true)
                .assertIsDisplayed()
                .performClick()
            compose.waitForIdle()

            listOf(expected.rename, expected.archive, expected.restore, expected.delete).forEach { label ->
                compose.onNode(
                    hasContentDescription(label) and hasClickActionLabel(label),
                    useUnmergedTree = true,
                ).assertIsDisplayed()
            }

            compose.onNode(
                hasContentDescription(expected.rename) and hasClickActionLabel(expected.rename),
                useUnmergedTree = true,
            ).performClick()
            compose.waitForIdle()
            assertEquals(index + 1, renameClicks)
        }
        assertEquals(0, archiveClicks)
        assertEquals(0, restoreClicks)
        assertEquals(0, deleteClicks)
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
        compose.onNodeWithContentDescription("Message")
            .performImeAction()
        compose.onNode(
            hasContentDescription("Attach files") and
                hasStateDescription("Ready to attach files.") and
                hasClickActionLabel("Attach files"),
        )
            .assertIsDisplayed()
            .assertIsEnabled()
            .performClick()
        compose.onNode(
            hasContentDescription("Send message") and
                hasClickActionLabel("Send message"),
        )
            .assertIsEnabled()
            .performClick()

        assertEquals("Hello", state.value.chatInput)
        assertEquals(1, attachmentClicks)
        assertEquals(2, sendClicks)
        assertEquals(
            listOf(
                HapticFeedbackType.TextHandleMove,
                HapticFeedbackType.TextHandleMove,
                HapticFeedbackType.TextHandleMove,
            ),
            hapticFeedback.events,
        )
    }

    @Test
    fun chatScreenBackendUnavailableBannerExposesAccessibilitySummaryAndRefreshCallback() {
        var refreshClicks = 0
        val unsafeProviderDetail = "http://127.0.0.1:11434 refused route-token-secret"
        val state = RuntimeUiState(
            isConnected = true,
            runtimeStatus = "authenticated",
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "runtime-1",
                name = "AetherLink Runtime",
            ),
            backendAvailable = false,
            providerStatuses = listOf(
                RuntimeProviderStatus(
                    id = "ollama",
                    name = "Ollama",
                    available = false,
                    message = unsafeProviderDetail,
                    code = "provider_unavailable",
                    retryable = true,
                )
            ),
        )

        compose.setContent {
            MaterialTheme {
                ChatScreen(
                    state = state,
                    onInputChange = {},
                    onSend = {},
                    onCancel = {},
                    onConnect = {},
                    onScanPairingQr = {},
                    onRefreshHealth = { refreshClicks += 1 },
                    onAttachFiles = {},
                    onRemoveAttachment = {},
                    onSuggestionClick = {},
                    onScanLatestQr = {},
                )
            }
        }

        val title = "Model service needs attention"
        val detail = "Ollama is not responding through the runtime. Check the provider in AetherLink Runtime, then refresh health."
        compose.onNodeWithText(title).assertIsDisplayed()
        compose.onNodeWithText(detail).assertIsDisplayed()
        compose.onNodeWithContentDescription("$title. $detail", useUnmergedTree = true)
            .assertIsDisplayed()
            .assert(hasPoliteLiveRegion())
        compose.onAllNodesWithText(unsafeProviderDetail, useUnmergedTree = true).assertCountEquals(0)

        compose.onNodeWithText("Refresh health")
            .assertIsDisplayed()
        compose.onNode(hasStateDescription("Ready to refresh runtime health.") and hasClickAction())
            .assertIsDisplayed()
            .assertIsEnabled()
            .performClick()

        assertEquals(1, refreshClicks)
    }

    @Test
    fun chatScreenBackendUnavailableRefreshActionExplainsStateAcrossSupportedLanguages() {
        data class ExpectedCopy(
            val languageTag: String,
            val refreshAction: String,
            val refreshState: String,
        )

        val expectedCopies = listOf(
            ExpectedCopy(
                languageTag = "en",
                refreshAction = "Refresh health",
                refreshState = "Ready to refresh runtime health.",
            ),
            ExpectedCopy(
                languageTag = "ko",
                refreshAction = "상태 새로고침",
                refreshState = "런타임 상태를 새로고침할 준비가 되었습니다.",
            ),
            ExpectedCopy(
                languageTag = "ja",
                refreshAction = "ヘルスを更新",
                refreshState = "ランタイムのヘルスを更新できます。",
            ),
            ExpectedCopy(
                languageTag = "zh-CN",
                refreshAction = "刷新健康状态",
                refreshState = "可以刷新运行时健康状态。",
            ),
            ExpectedCopy(
                languageTag = "fr",
                refreshAction = "Actualiser l’état",
                refreshState = "Prêt à actualiser l’état du runtime.",
            ),
        )
        val currentCase = mutableStateOf(expectedCopies.first())

        compose.setContent {
            MaterialTheme {
                LocalizedTestContent(languageTag = currentCase.value.languageTag) {
                    key(currentCase.value.languageTag) {
                        ChatScreen(
                            state = RuntimeUiState(
                                isConnected = true,
                                runtimeStatus = "authenticated",
                                trustedRuntime = RuntimeTrustedRuntime(
                                    deviceId = "runtime-1",
                                    name = "AetherLink Runtime",
                                ),
                                backendAvailable = false,
                                providerStatuses = listOf(
                                    RuntimeProviderStatus(
                                        id = "ollama",
                                        name = "Ollama",
                                        available = false,
                                        code = "provider_unavailable",
                                        retryable = true,
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
            }
        }

        expectedCopies.forEach { expected ->
            compose.runOnUiThread {
                currentCase.value = expected
            }
            compose.waitForIdle()

            compose.onNodeWithText(expected.refreshAction)
                .assertIsDisplayed()
            compose.onNode(hasStateDescription(expected.refreshState) and hasClickAction())
                .assertIsDisplayed()
                .assertIsEnabled()
        }
    }

    @Test
    fun chatScreenBackendUnavailableSummaryResourceFormatsAcrossSupportedLanguages() {
        data class ExpectedSummary(
            val languageTag: String,
            val summary: String,
        )

        val expectedSummaries = listOf(
            ExpectedSummary(
                languageTag = "en",
                summary = "Model service needs attention. Check the model service in AetherLink Runtime, then refresh health.",
            ),
            ExpectedSummary(
                languageTag = "ko",
                summary = "모델 서비스 확인 필요. AetherLink Runtime에서 모델 서비스 상태를 확인한 다음 상태를 새로고침하세요.",
            ),
            ExpectedSummary(
                languageTag = "ja",
                summary = "モデルサービスの確認が必要です。AetherLink Runtime でモデルサービスの状態を確認し、ヘルスを更新してください。",
            ),
            ExpectedSummary(
                languageTag = "zh-CN",
                summary = "模型服务需要处理。请在 AetherLink Runtime 中检查模型服务状态，然后刷新健康状态。",
            ),
            ExpectedSummary(
                languageTag = "fr",
                summary = "Le service de modèles demande une vérification. Vérifiez le service de modèles dans AetherLink Runtime, puis actualisez l’état.",
            ),
        )

        expectedSummaries.forEach { expected ->
            val context = ApplicationProvider
                .getApplicationContext<Context>()
                .localizedContext(expected.languageTag)
            assertEquals(
                expected.summary,
                context.getString(
                    R.string.chat_backend_unavailable_summary,
                    context.getString(R.string.chat_backend_unavailable_title),
                    context.getString(R.string.chat_backend_unavailable_detail),
                ),
            )
        }
    }

    @Test
    fun chatScreenGenericErrorBannerExposesAccessibilitySummaryAndRedactsUnsafeDetail() {
        val unsafeDetail = "http://127.0.0.1:11434/api/tags route_token=secret"
        val chatModel = RuntimeModel(
            id = "ollama:llama3.1:8b",
            name = "Llama 3.1 8B",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = true,
            source = "local",
        )
        val uiState = mutableStateOf(
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
                error = RuntimeUiError(
                    code = "send_failed",
                    detail = "relay timed out",
                ),
            )
        )

        compose.setContent {
            MaterialTheme {
                Surface(modifier = Modifier.width(360.dp).height(720.dp)) {
                    ChatScreen(
                        state = uiState.value,
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

        compose.onNodeWithContentDescription(
            "Error. Could not send the message to AetherLink Runtime. More information: relay timed out",
        )
            .assertExists()
            .assert(hasPoliteLiveRegion())

        uiState.value = uiState.value.copy(
            error = RuntimeUiError(
                code = "qr_scan_failed",
                detail = unsafeDetail,
            )
        )
        compose.waitForIdle()

        compose.onNodeWithContentDescription(
            "Error. QR scanning failed. More information: The QR scanner could not start. Check camera permission or reopen the app.",
        )
            .assertExists()
            .assert(hasPoliteLiveRegion())
        compose.onAllNodesWithText(unsafeDetail, useUnmergedTree = true).assertCountEquals(0)
        compose.onAllNodesWithContentDescription(unsafeDetail, useUnmergedTree = true).assertCountEquals(0)
    }

    @Test
    fun chatScreenGenericErrorAccessibilitySummaryLocalizesAcrossSupportedLanguages() {
        data class ExpectedSummary(
            val languageTag: String,
            val summary: String,
        )

        val expectedSummaries = listOf(
            ExpectedSummary(
                languageTag = "en",
                summary = "Error. Could not send the message to AetherLink Runtime.",
            ),
            ExpectedSummary(
                languageTag = "ko",
                summary = "오류. AetherLink Runtime으로 메시지를 보낼 수 없습니다.",
            ),
            ExpectedSummary(
                languageTag = "ja",
                summary = "エラー。AetherLink Runtime にメッセージを送信できませんでした。",
            ),
            ExpectedSummary(
                languageTag = "zh-CN",
                summary = "错误。无法向 AetherLink Runtime 发送消息。",
            ),
            ExpectedSummary(
                languageTag = "fr",
                summary = "Erreur. Impossible d’envoyer le message à AetherLink Runtime.",
            ),
        )

        expectedSummaries.forEach { expected ->
            val context = ApplicationProvider
                .getApplicationContext<Context>()
                .localizedContext(expected.languageTag)
            assertEquals(
                expected.summary,
                context.getString(
                    R.string.error_accessibility_summary,
                    context.getString(R.string.error_title),
                    context.getString(R.string.error_send_failed),
                ),
            )
        }
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
        compose.onNode(
            hasText("Scan QR") and
                hasStateDescription("Ready to scan QR."),
        ).assertIsDisplayed().performClick()

        assertEquals(1, scanQrClicks)
        assertEquals(0, connectClicks)
        assertNoVisibleText("Connect to continue")
        assertNoVisibleText("Connect to the trusted runtime before chatting.")
        assertNoVisibleText("Scan latest QR")
        assertNoVisibleText("Connection address")
    }

    @Test
    fun chatScreenConnectActionExplainsDisabledConnectingState() {
        var scanQrClicks = 0
        var connectClicks = 0

        compose.setContent {
            MaterialTheme {
                ChatScreen(
                    state = RuntimeUiState(
                        isConnecting = true,
                        trustedRuntime = RuntimeTrustedRuntime(
                            deviceId = "runtime-1",
                            name = "AetherLink Runtime",
                        ),
                    ),
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

        compose.onNode(
            hasText("Connecting") and
                hasStateDescription("Connection attempt in progress."),
        ).assertIsNotEnabled()

        assertEquals(0, connectClicks)
        assertEquals(0, scanQrClicks)
    }

    @Test
    fun chatScreenRouteRecoveryEmptyStateShowsFullGuidanceOnNarrowWidth() {
        var scanQrClicks = 0
        var connectClicks = 0
        val routeGuidance = "This network cannot reach the saved route. Prepare a reachable connection route in AetherLink Runtime, then scan the latest QR."

        compose.setContent {
            MaterialTheme {
                Surface(modifier = Modifier.width(260.dp).height(720.dp)) {
                    ChatScreen(
                        state = RuntimeUiState(
                            isConnected = false,
                            trustedRuntime = RuntimeTrustedRuntime(
                                deviceId = "runtime-1",
                                name = "AetherLink Runtime",
                            ),
                            error = RuntimeUiError(
                                code = "remote_route_unreachable",
                                diagnosticCode = "route_diagnostic_relay_failed",
                            ),
                        ),
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
        }

        compose.onAllNodesWithText("Scan latest QR").onFirst().assertIsDisplayed()
        compose.onNodeWithText(routeGuidance).assertIsDisplayed()
        compose.onAllNodesWithText("Scan latest QR").onLast().assertIsDisplayed().performClick()

        assertEquals(1, scanQrClicks)
        assertEquals(0, connectClicks)
    }

    @Test
    fun chatScreenRouteAvailabilityNoticeExposesStateAndAction() {
        val hapticFeedback = RecordingHapticFeedback()
        var scanQrClicks = 0
        var connectClicks = 0
        val routeGuidance = "Saved connection did not answer. Prepare remote connection details in AetherLink Runtime, then scan the latest QR with connection details."

        compose.setContent {
            CompositionLocalProvider(LocalHapticFeedback provides hapticFeedback) {
                MaterialTheme {
                    ChatScreen(
                        state = RuntimeUiState(
                            isConnected = false,
                            trustedRuntime = RuntimeTrustedRuntime(
                                deviceId = "runtime-1",
                                name = "AetherLink Runtime",
                                relayHost = "relay.example.test",
                                relayPort = 443,
                                relayId = "relay-1",
                                relaySecret = "secret-1",
                                relayExpiresAtEpochMillis = Long.MAX_VALUE,
                                relayNonce = "nonce-1",
                                relayScope = "remote",
                            ),
                            messages = listOf(
                                RuntimeChatMessage(
                                    id = "message-1",
                                    role = "user",
                                    content = "Keep this chat visible while the route recovers.",
                                ),
                                RuntimeChatMessage(
                                    id = "message-2",
                                    role = "assistant",
                                    content = "The response remains in history.",
                                ),
                            ),
                            error = RuntimeUiError(
                                code = "remote_route_unreachable",
                                diagnosticCode = "route_diagnostic_relay_failed",
                            ),
                        ),
                        onInputChange = {},
                        onSend = {},
                        onCancel = {},
                        onConnect = { connectClicks += 1 },
                        onScanPairingQr = {},
                        onRefreshHealth = {},
                        onAttachFiles = {},
                        onRemoveAttachment = {},
                        onSuggestionClick = {},
                        onScanLatestQr = { scanQrClicks += 1 },
                    )
                }
            }
        }

        compose.onNodeWithText("The response remains in history.").assertIsDisplayed()
        compose.onNode(
            hasStateDescription(routeGuidance) and
                hasClickAction(),
            useUnmergedTree = true,
        )
            .assertIsDisplayed()
            .performClick()

        assertEquals(1, scanQrClicks)
        assertEquals(0, connectClicks)
        assertEquals(listOf(HapticFeedbackType.TextHandleMove), hapticFeedback.events)
    }

    @Test
    fun routeNoticeShowsQrRefreshForRelayAuthenticationFailure() {
        val state = RuntimeUiState(
            isConnected = false,
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "runtime-1",
                name = "AetherLink Runtime",
                relayHost = "relay.example.test",
                relayPort = 443,
                relayId = "relay-1",
                relaySecret = "secret-1",
                relayExpiresAtEpochMillis = Long.MAX_VALUE,
                relayNonce = "nonce-1",
                relayScope = "remote",
            ),
            error = RuntimeUiError(
                code = "remote_route_auth_failed",
                diagnosticCode = "route_diagnostic_relay_auth_failed",
            ),
        )

        val notice = runtimeRouteNotice(state, state.trustedRuntime)

        assertEquals(R.string.route_notice_status_refresh_needed, notice?.statusRes)
        assertEquals(R.string.route_diagnostic_relay_auth_failed, notice?.detailRes)
        assertEquals(RuntimeRouteNoticeTone.Warning, notice?.tone)
        assertEquals(RouteNoticePrimaryAction.ScanLatestQr, notice?.action)
    }

    @Test
    fun chatScreenRelayAuthFailureAfterRouteClearKeepsLatestQrRecoveryAction() {
        val hapticFeedback = RecordingHapticFeedback()
        var scanQrClicks = 0
        var scanLatestQrClicks = 0
        var connectClicks = 0

        compose.setContent {
            CompositionLocalProvider(LocalHapticFeedback provides hapticFeedback) {
                MaterialTheme {
                    ChatScreen(
                        state = RuntimeUiState(
                            isConnected = false,
                            trustedRuntime = RuntimeTrustedRuntime(
                                deviceId = "runtime-1",
                                name = "AetherLink Runtime",
                                fingerprint = "runtime-fingerprint",
                            ),
                            error = RuntimeUiError(
                                code = "remote_route_auth_failed",
                                diagnosticCode = "route_diagnostic_relay_auth_failed",
                            ),
                        ),
                        onInputChange = {},
                        onSend = {},
                        onCancel = {},
                        onConnect = { connectClicks += 1 },
                        onScanPairingQr = { scanQrClicks += 1 },
                        onRefreshHealth = {},
                        onAttachFiles = {},
                        onRemoveAttachment = {},
                        onSuggestionClick = {},
                        onScanLatestQr = { scanLatestQrClicks += 1 },
                    )
                }
            }
        }

        compose.onAllNodesWithText("Scan latest QR").onFirst().assertIsDisplayed()
        compose.onNodeWithText(
            "Saved connection details could not be authenticated. Scan a fresh QR from the trusted runtime."
        )
            .assertIsDisplayed()
        compose.onNode(
            hasText("Scan latest QR") and
                hasStateDescription("Ready to scan the latest QR."),
        ).performClick()

        assertEquals(1, scanQrClicks)
        assertEquals(0, scanLatestQrClicks)
        assertEquals(0, connectClicks)
        assertEquals(listOf(HapticFeedbackType.TextHandleMove), hapticFeedback.events)
    }

    @Test
    fun chatScreenExpiredRemoteRouteShowsLatestQrRecoveryAction() {
        val hapticFeedback = RecordingHapticFeedback()
        var scanQrClicks = 0
        var connectClicks = 0

        compose.setContent {
            CompositionLocalProvider(LocalHapticFeedback provides hapticFeedback) {
                MaterialTheme {
                    ChatScreen(
                        state = RuntimeUiState(
                            isConnected = false,
                            trustedRuntime = RuntimeTrustedRuntime(
                                deviceId = "runtime-1",
                                name = "AetherLink Runtime",
                                relayHost = "relay.example.test",
                                relayPort = 443,
                                relayId = "relay-1",
                                relaySecret = "secret-1",
                                relayExpiresAtEpochMillis = 1L,
                                relayNonce = "nonce-1",
                                relayScope = "remote",
                            ),
                            error = RuntimeUiError(
                                code = "remote_route_expired",
                                diagnosticCode = "route_diagnostic_remote_route_expired",
                            ),
                        ),
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
        }

        compose.onAllNodesWithText("Scan latest QR").onFirst().assertIsDisplayed()
        compose.onNodeWithText(
            "Saved connection details expired. Scan the latest AetherLink Runtime QR with fresh connection details."
        )
            .assertIsDisplayed()
        compose.onNode(
            hasText("Scan latest QR") and
                hasStateDescription("Ready to scan the latest QR."),
        ).performClick()

        assertEquals(1, scanQrClicks)
        assertEquals(0, connectClicks)
        assertEquals(listOf(HapticFeedbackType.TextHandleMove), hapticFeedback.events)
    }

    @Test
    fun chatScreenExpiredRemoteRouteRecoveryLocalizesAcrossSupportedLanguages() {
        data class ExpectedCopy(
            val languageTag: String,
            val action: String,
            val detail: String,
            val readyState: String,
        )

        val expectedCopies = listOf(
            ExpectedCopy(
                languageTag = "en",
                action = "Scan latest QR",
                detail = "Saved connection details expired. Scan the latest AetherLink Runtime QR with fresh connection details.",
                readyState = "Ready to scan the latest QR.",
            ),
            ExpectedCopy(
                languageTag = "ko",
                action = "최신 QR 스캔",
                detail = "저장된 연결 정보가 만료되었습니다. 새 연결 정보가 포함된 최신 AetherLink Runtime QR을 스캔하세요.",
                readyState = "최신 QR을 스캔할 준비가 되었습니다.",
            ),
            ExpectedCopy(
                languageTag = "ja",
                action = "最新 QR をスキャン",
                detail = "保存済み接続情報の有効期限が切れました。新しい接続情報を含む最新の AetherLink Runtime QR をスキャンしてください。",
                readyState = "最新の QR をスキャンできます。",
            ),
            ExpectedCopy(
                languageTag = "zh-CN",
                action = "扫描最新二维码",
                detail = "已保存的连接信息已过期。请扫描包含新连接信息的最新 AetherLink Runtime 二维码。",
                readyState = "已准备好扫描最新 QR。",
            ),
            ExpectedCopy(
                languageTag = "fr",
                action = "Scanner dernier QR",
                detail = "Les informations de connexion enregistrées ont expiré. Scannez le dernier QR AetherLink Runtime avec de nouvelles informations de connexion.",
                readyState = "Prêt à scanner le dernier QR.",
            ),
        )
        val hapticFeedback = RecordingHapticFeedback()
        val currentCase = mutableStateOf(expectedCopies.first())
        var scanQrClicks = 0
        var connectClicks = 0

        compose.setContent {
            CompositionLocalProvider(LocalHapticFeedback provides hapticFeedback) {
                MaterialTheme {
                    LocalizedTestContent(languageTag = currentCase.value.languageTag) {
                        key(currentCase.value.languageTag) {
                            ChatScreen(
                                state = RuntimeUiState(
                                    isConnected = false,
                                    selectedLanguageTag = currentCase.value.languageTag,
                                    trustedRuntime = RuntimeTrustedRuntime(
                                        deviceId = "runtime-1",
                                        name = "AetherLink Runtime",
                                        relayHost = "relay.example.test",
                                        relayPort = 443,
                                        relayId = "relay-1",
                                        relaySecret = "secret-1",
                                        relayExpiresAtEpochMillis = 1L,
                                        relayNonce = "nonce-1",
                                        relayScope = "remote",
                                    ),
                                    error = RuntimeUiError(
                                        code = "remote_route_expired",
                                        diagnosticCode = "route_diagnostic_remote_route_expired",
                                    ),
                                ),
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
                }
            }
        }

        expectedCopies.forEachIndexed { index, expected ->
            compose.runOnUiThread {
                currentCase.value = expected
            }
            compose.waitForIdle()

            compose.onNodeWithText(expected.detail).assertIsDisplayed()
            compose.onNode(
                hasText(expected.action) and
                    hasStateDescription(expected.readyState) and
                    hasClickAction(),
            ).assertIsDisplayed()
                .performClick()

            assertEquals(index + 1, scanQrClicks)
            assertEquals(0, connectClicks)
        }
        assertEquals(
            List(expectedCopies.size) { HapticFeedbackType.TextHandleMove },
            hapticFeedback.events,
        )
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
        var removeAttachmentClicks = 0
        val chatModel = RuntimeModel(
            id = "ollama:qwen3:8b",
            name = "Qwen3 8B",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = true,
            source = "local",
        )
        val pendingAttachment = RuntimePendingAttachment(
            id = "attachment-document",
            type = "document",
            name = "brief.pdf",
            mimeType = "application/pdf",
            sizeBytes = 0L,
            dataBase64 = "ZmlsZQ==",
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
                        pendingAttachments = listOf(pendingAttachment),
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
                    onRemoveAttachment = { removeAttachmentClicks += 1 },
                    onSuggestionClick = {},
                    onScanLatestQr = {},
                )
            }
        }

        compose.onNodeWithText("The runtime route needs a selected model before continuing.").assertIsDisplayed()
        compose.onNodeWithText("Select a model before sending.").assertIsDisplayed()
        compose.onNodeWithContentDescription("Message")
            .assert(hasStateDescription("Select a model before sending."))
            .assertIsNotEnabled()
        compose.onNode(
            hasContentDescription("Attach files") and
                hasStateDescription("Select a model before sending.") and
                hasClickActionLabel("Attach files"),
        )
            .assertIsNotEnabled()
        compose.onNode(
            hasContentDescription("Remove attachment brief.pdf") and
                hasStateDescription("Select a model before sending.") and
                hasClickActionLabel("Remove attachment brief.pdf")
        )
            .assertIsNotEnabled()
        compose.onNode(
            hasContentDescription("Send message") and
                hasStateDescription("Select a model before sending.") and
                hasClickActionLabel("Send message"),
        ).assertIsNotEnabled()

        assertEquals(0, attachmentClicks)
        assertEquals(0, removeAttachmentClicks)
    }

    @Test
    fun chatScreenSendButtonLocalizesReadinessStateAcrossSupportedLanguages() {
        data class ExpectedSendState(
            val languageTag: String,
            val messageField: String,
            val sendAction: String,
            val emptyState: String,
            val readyState: String,
        )

        val expectedStates = listOf(
            ExpectedSendState("en", "Message", "Send message", "Enter a message to send.", "Ready to send."),
            ExpectedSendState("ko", "메시지", "메시지 전송", "전송할 메시지를 입력하세요.", "전송할 준비가 되었습니다."),
            ExpectedSendState("ja", "メッセージ", "メッセージを送信", "送信するメッセージを入力してください。", "送信できます。"),
            ExpectedSendState("zh-CN", "消息", "发送消息", "输入要发送的消息。", "已准备好发送。"),
            ExpectedSendState("fr", "Message", "Envoyer le message", "Saisissez un message à envoyer.", "Prêt à envoyer."),
        )
        val currentState = mutableStateOf(expectedStates.first())
        val currentInput = mutableStateOf("")
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
                val expected = currentState.value
                LocalizedTestContent(languageTag = expected.languageTag) {
                    key(expected.languageTag, currentInput.value) {
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
                                chatInput = currentInput.value,
                                selectedLanguageTag = expected.languageTag,
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
        }

        expectedStates.forEach { expected ->
            compose.runOnUiThread {
                currentState.value = expected
                currentInput.value = ""
            }
            compose.waitForIdle()
            compose.onNode(
                hasContentDescription(expected.sendAction) and
                    hasStateDescription(expected.emptyState) and
                    hasClickActionLabel(expected.sendAction),
            ).assertIsNotEnabled()
            compose.onNode(
                hasContentDescription(expected.messageField) and hasStateDescription(expected.emptyState),
            ).assertIsEnabled()

            compose.runOnUiThread {
                currentInput.value = "Hello"
            }
            compose.waitForIdle()
            compose.onNode(
                hasContentDescription(expected.sendAction) and
                    hasStateDescription(expected.readyState) and
                    hasClickActionLabel(expected.sendAction),
            ).assertIsEnabled()
            compose.onNode(
                hasContentDescription(expected.messageField) and hasStateDescription(expected.readyState),
            ).assertIsEnabled()
        }
    }

    @Test
    fun chatScreenComposerReadinessStatusAnnouncesAcrossSupportedLanguages() {
        val languageTag = mutableStateOf("en")
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
                LocalizedTestContent(languageTag = languageTag.value) {
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
                            selectedLanguageTag = languageTag.value,
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

        listOf("en", "ko", "ja", "zh-CN", "fr").forEach { nextLanguageTag ->
            compose.runOnUiThread {
                languageTag.value = nextLanguageTag
            }
            compose.waitForIdle()

            val expectedStatus = ApplicationProvider
                .getApplicationContext<Context>()
                .localizedContext(nextLanguageTag)
                .getString(R.string.chat_hint_select_model)
            compose.onNodeWithText(expectedStatus).assertIsDisplayed()
            compose.onNodeWithContentDescription(expectedStatus, useUnmergedTree = true)
                .assertIsDisplayed()
                .assert(hasPoliteLiveRegion())
        }
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

        compose.onNodeWithContentDescription("Message")
            .assert(hasStateDescription("Wait for the current response or cancel it."))
            .assertIsNotEnabled()
        compose.onNode(
            hasContentDescription("Attach files") and
                hasStateDescription("Wait for the current response or cancel it.") and
                hasClickActionLabel("Attach files"),
        )
            .assertIsNotEnabled()
        compose.onAllNodesWithContentDescription("Send message").assertCountEquals(0)
        compose.onNode(
            hasContentDescription("Cancel generation") and
                hasStateDescription("Ready to stop the current response.") and
                hasClickActionLabel("Cancel generation"),
        )
            .assertIsDisplayed()
            .assertIsEnabled()
            .performClick()

        assertEquals(0, sendClicks)
        assertEquals(0, attachmentClicks)
        assertEquals(1, cancelClicks)
        assertEquals(listOf(HapticFeedbackType.LongPress), hapticFeedback.events)
    }

    @Test
    fun chatScreenStreamingCancelActionExplainsStateAcrossSupportedLanguages() {
        data class ExpectedCopy(
            val languageTag: String,
            val cancelAction: String,
            val cancelState: String,
        )

        val expectedCopies = listOf(
            ExpectedCopy(
                languageTag = "en",
                cancelAction = "Cancel generation",
                cancelState = "Ready to stop the current response.",
            ),
            ExpectedCopy(
                languageTag = "ko",
                cancelAction = "생성 취소",
                cancelState = "현재 응답을 중지할 준비가 되었습니다.",
            ),
            ExpectedCopy(
                languageTag = "ja",
                cancelAction = "生成をキャンセル",
                cancelState = "現在の応答を停止できます。",
            ),
            ExpectedCopy(
                languageTag = "zh-CN",
                cancelAction = "取消生成",
                cancelState = "可以停止当前回复。",
            ),
            ExpectedCopy(
                languageTag = "fr",
                cancelAction = "Annuler la génération",
                cancelState = "Prêt à arrêter la réponse en cours.",
            ),
        )
        val chatModel = RuntimeModel(
            id = "ollama:qwen3:8b",
            name = "Qwen3 8B",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = true,
            source = "local",
        )
        val currentCase = mutableStateOf(expectedCopies.first())

        compose.setContent {
            MaterialTheme {
                LocalizedTestContent(languageTag = currentCase.value.languageTag) {
                    key(currentCase.value.languageTag) {
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
        }

        expectedCopies.forEach { expected ->
            compose.runOnUiThread {
                currentCase.value = expected
            }
            compose.waitForIdle()

            compose.onNode(
                hasContentDescription(expected.cancelAction) and
                    hasStateDescription(expected.cancelState) and
                    hasClickActionLabel(expected.cancelAction),
            )
                .assertIsDisplayed()
                .assertIsEnabled()
        }
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
        compose.onNode(
            hasClickActionLabel("Remove attachment brief.pdf"),
            useUnmergedTree = true,
        )
            .assertExists()
        compose.onNode(
            hasClickActionLabel("Remove attachment diagram.png"),
            useUnmergedTree = true,
        )
            .assertExists()
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
        compose.onNode(
            hasContentDescription("Thinking. Collapsed. first step second step third step") and
                hasStateDescription("Collapsed") and
                hasClickActionLabel("Show thinking") and
                hasClickAction(),
            useUnmergedTree = true,
        ).assertIsDisplayed()

        compose.onNode(hasText("Thinking") and hasStateDescription("Collapsed") and hasClickAction())
            .performClick()

        compose.onNodeWithText("first step\nsecond step\nthird step\nfourth step").assertIsDisplayed()
        compose.onNodeWithText("Hide thinking").assertIsDisplayed()
        compose.onNode(hasText("Thinking") and hasStateDescription("Expanded") and hasClickAction())
            .assertIsDisplayed()
        compose.onNode(
            hasContentDescription("Thinking. Expanded. first step second step third step fourth step") and
                hasStateDescription("Expanded") and
                hasClickActionLabel("Hide thinking") and
                hasClickAction(),
            useUnmergedTree = true,
        ).assertIsDisplayed()
        assertEquals(listOf(HapticFeedbackType.TextHandleMove), hapticFeedback.events)
    }

    @Test
    fun chatScreenReasoningSummaryLocalizesAcrossSupportedLanguages() {
        val languageTags = listOf("en", "ko", "ja", "zh-CN", "fr")
        val chatModel = RuntimeModel(
            id = "ollama:reasoning",
            name = "Reasoning Model",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = true,
            source = "local",
        )
        val reasoningPreview = "first step second step third step"
        val language = mutableStateOf(languageTags.first())

        compose.setContent {
            LocalizedTestContent(languageTag = language.value) {
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
                            selectedLanguageTag = language.value,
                            selectedModelId = chatModel.id,
                            models = listOf(chatModel),
                            messages = listOf(
                                RuntimeChatMessage(
                                    id = "assistant-1",
                                    role = "assistant",
                                    reasoning = "first step\nsecond step\nthird step\nfourth step",
                                    content = "The trusted runtime mediates model access.",
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
        }

        languageTags.forEach { languageTag ->
            language.value = languageTag
            compose.waitForIdle()

            val localizedContext = ApplicationProvider
                .getApplicationContext<Context>()
                .localizedContext(languageTag)
            val expectedSummary = localizedContext.getString(
                R.string.assistant_reasoning_summary,
                localizedContext.getString(R.string.assistant_reasoning_label),
                localizedContext.getString(R.string.section_state_collapsed),
                reasoningPreview,
            )
            val expectedShowAction = localizedContext.getString(R.string.assistant_reasoning_show)

            compose.onNode(
                hasContentDescription(expectedSummary) and
                    hasStateDescription(localizedContext.getString(R.string.section_state_collapsed)) and
                    hasClickActionLabel(expectedShowAction) and
                    hasClickAction(),
                useUnmergedTree = true,
            ).assertIsDisplayed()
        }
    }

    @Test
    fun chatScreenStreamingAssistantPlaceholderAnnouncesLiveStatusAcrossSupportedLanguages() {
        val languageTags = listOf("en", "ko", "ja", "zh-CN", "fr")
        val language = mutableStateOf(languageTags.first())
        val chatModel = RuntimeModel(
            id = "ollama:qwen3:8b",
            name = "Qwen3 8B",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = true,
            source = "local",
        )

        compose.setContent {
            LocalizedTestContent(languageTag = language.value) {
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
                            selectedLanguageTag = language.value,
                            selectedModelId = chatModel.id,
                            models = listOf(chatModel),
                            messages = listOf(
                                RuntimeChatMessage(
                                    id = "assistant-streaming",
                                    role = "assistant",
                                    content = "",
                                ),
                            ),
                            isStreaming = true,
                            activeRequestId = "request-1",
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

        languageTags.forEach { languageTag ->
            language.value = languageTag
            compose.waitForIdle()

            val localizedContext = ApplicationProvider
                .getApplicationContext<Context>()
                .localizedContext(languageTag)
            val expectedTyping = localizedContext.getString(R.string.assistant_typing)

            compose.onNodeWithText(expectedTyping).assertIsDisplayed()
            compose.onNode(
                hasContentDescription(expectedTyping) and hasPoliteLiveRegion(),
                useUnmergedTree = true,
            ).assertIsDisplayed()
        }
    }

    @Test
    fun chatScreenMessageCopyActionsExposeLocalizedActionLabels() {
        data class ExpectedCopyAction(
            val languageTag: String,
            val copyAction: String,
            val copiedResult: String,
        )

        val expectedCopies = listOf(
            ExpectedCopyAction("en", "Copy message", "Copied"),
            ExpectedCopyAction("ko", "메시지 복사", "복사됨"),
            ExpectedCopyAction("ja", "メッセージをコピー", "コピーしました"),
            ExpectedCopyAction("zh-CN", "复制消息", "已复制"),
            ExpectedCopyAction("fr", "Copier le message", "Copié"),
        )
        val currentCopy = mutableStateOf(expectedCopies.first())
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
                val expected = currentCopy.value
                LocalizedTestContent(languageTag = expected.languageTag) {
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
                                    id = "user-copy",
                                    role = "user",
                                    content = "Copyable user message",
                                ),
                                RuntimeChatMessage(
                                    id = "assistant-copy",
                                    role = "assistant",
                                    content = "Copyable assistant reply",
                                ),
                            ),
                            selectedTheme = RuntimeAppTheme.System,
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

        expectedCopies.forEach { expected ->
            compose.runOnUiThread {
                currentCopy.value = expected
            }
            compose.waitForIdle()
            compose.onNodeWithText("Copyable user message").assertExists()
            compose.onNodeWithText("Copyable assistant reply").assertExists()
            compose.onAllNodes(hasLongClickActionLabel(expected.copyAction), useUnmergedTree = true)
                .assertCountEquals(2)
                .onFirst()
                .performSemanticsAction(SemanticsActions.OnLongClick)
            waitForCopiedAnnouncement(expected.copiedResult)
            compose.onNodeWithContentDescription(expected.copiedResult, useUnmergedTree = true)
                .assert(hasPoliteLiveRegion())
        }
    }

    @Test
    fun chatScreenCodeBlockCopyUsesLocalizedCodeActionLabels() {
        data class ExpectedCodeCopy(
            val languageTag: String,
            val codeCopyAction: String,
            val messageCopyAction: String,
            val copiedResult: String,
        )

        val expectedCopies = listOf(
            ExpectedCodeCopy("en", "Copy code block", "Copy message", "Copied"),
            ExpectedCodeCopy("ko", "코드 블록 복사", "메시지 복사", "복사됨"),
            ExpectedCodeCopy("ja", "コードブロックをコピー", "メッセージをコピー", "コピーしました"),
            ExpectedCodeCopy("zh-CN", "复制代码块", "复制消息", "已复制"),
            ExpectedCodeCopy("fr", "Copier le bloc de code", "Copier le message", "Copié"),
        )
        val currentCopy = mutableStateOf(expectedCopies.first())
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
                val expected = currentCopy.value
                LocalizedTestContent(languageTag = expected.languageTag) {
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
                                    id = "assistant-code",
                                    role = "assistant",
                                    content = """
                                        Use this helper:
                                        ```kotlin
                                        val route = "runtime"
                                        ```
                                    """.trimIndent(),
                                ),
                            ),
                            selectedTheme = RuntimeAppTheme.System,
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

        expectedCopies.forEach { expected ->
            compose.runOnUiThread {
                currentCopy.value = expected
            }
            compose.waitForIdle()
            compose.onNodeWithText("kotlin").assertExists()
            compose.onNodeWithText("val route = \"runtime\"").assertExists()
            compose.onAllNodesWithContentDescription(expected.codeCopyAction, useUnmergedTree = true)
                .assertCountEquals(1)
            compose.onNodeWithContentDescription(expected.codeCopyAction, useUnmergedTree = true)
                .assert(hasClickActionLabel(expected.codeCopyAction))
                .performClick()
            waitForCopiedAnnouncement(expected.copiedResult)
            compose.onNodeWithContentDescription(expected.copiedResult, useUnmergedTree = true)
                .assert(hasPoliteLiveRegion())
            compose.onAllNodesWithContentDescription(expected.messageCopyAction, useUnmergedTree = true)
                .assertCountEquals(0)
        }
    }

    @Test
    fun chatScreenMultipleCodeBlockCopyActionsLocalizeDistinctContextAcrossSupportedLanguages() {
        data class ExpectedCodeCopy(
            val languageTag: String,
            val firstCodeCopyAction: String,
            val secondCodeCopyAction: String,
            val genericCodeCopyAction: String,
        )

        val expectedCopies = listOf(
            ExpectedCodeCopy("en", "Copy Kotlin code block 1", "Copy SQL code block 2", "Copy code block"),
            ExpectedCodeCopy("ko", "Kotlin 코드 블록 1 복사", "SQL 코드 블록 2 복사", "코드 블록 복사"),
            ExpectedCodeCopy("ja", "Kotlin コードブロック 1 をコピー", "SQL コードブロック 2 をコピー", "コードブロックをコピー"),
            ExpectedCodeCopy("zh-CN", "复制 Kotlin 代码块 1", "复制 SQL 代码块 2", "复制代码块"),
            ExpectedCodeCopy("fr", "Copier le bloc de code Kotlin 1", "Copier le bloc de code SQL 2", "Copier le bloc de code"),
        )
        val currentCopy = mutableStateOf(expectedCopies.first())
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
                val expected = currentCopy.value
                LocalizedTestContent(languageTag = expected.languageTag) {
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
                                    id = "assistant-multi-code",
                                    role = "assistant",
                                    content = """
                                        Use both snippets:
                                        ```Kotlin
                                        val route = "runtime"
                                        ```
                                        Then inspect:
                                        ```SQL
                                        select 1
                                        ```
                                    """.trimIndent(),
                                ),
                            ),
                            selectedTheme = RuntimeAppTheme.System,
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

        expectedCopies.forEach { expected ->
            compose.runOnUiThread {
                currentCopy.value = expected
            }
            compose.waitForIdle()
            compose.onNodeWithText("Kotlin").assertExists()
            compose.onNodeWithText("SQL").assertExists()
            compose.onNodeWithContentDescription(expected.firstCodeCopyAction, useUnmergedTree = true)
                .assert(hasClickActionLabel(expected.firstCodeCopyAction))
            compose.onNodeWithContentDescription(expected.secondCodeCopyAction, useUnmergedTree = true)
                .assert(hasClickActionLabel(expected.secondCodeCopyAction))
            compose.onAllNodesWithContentDescription(expected.genericCodeCopyAction, useUnmergedTree = true)
                .assertCountEquals(0)
        }
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
            .assert(hasStateDescription("Ready to return to the latest message."))
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
    fun chatScreenJumpToLatestActionExplainsStateAcrossSupportedLanguages() {
        data class ExpectedCopy(
            val languageTag: String,
            val jumpAction: String,
            val jumpState: String,
        )

        val expectedCopies = listOf(
            ExpectedCopy(
                languageTag = "en",
                jumpAction = "Jump to latest message",
                jumpState = "Ready to return to the latest message.",
            ),
            ExpectedCopy(
                languageTag = "ko",
                jumpAction = "최신 메시지로 이동",
                jumpState = "최신 메시지로 돌아갈 준비가 되었습니다.",
            ),
            ExpectedCopy(
                languageTag = "ja",
                jumpAction = "最新のメッセージへ移動",
                jumpState = "最新のメッセージに戻れます。",
            ),
            ExpectedCopy(
                languageTag = "zh-CN",
                jumpAction = "跳到最新消息",
                jumpState = "可以返回最新消息。",
            ),
            ExpectedCopy(
                languageTag = "fr",
                jumpAction = "Aller au dernier message",
                jumpState = "Prêt à revenir au dernier message.",
            ),
        )
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
        val currentCase = mutableStateOf(expectedCopies.first())

        compose.setContent {
            MaterialTheme {
                LocalizedTestContent(languageTag = currentCase.value.languageTag) {
                    key(currentCase.value.languageTag) {
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
        }

        expectedCopies.forEach { expected ->
            compose.runOnUiThread {
                currentCase.value = expected
            }
            compose.waitForIdle()
            compose.onNodeWithTag(CHAT_MESSAGE_LIST_TEST_TAG)
                .performScrollToIndex(0)
            compose.waitForIdle()

            compose.onNode(
                hasContentDescription(expected.jumpAction) and hasStateDescription(expected.jumpState),
            )
                .assertIsDisplayed()
                .assertIsEnabled()
        }
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
        val uninstalledEmbeddingModel = RuntimeModel(
            id = "ollama:mxbai-embed-large",
            name = "Mxbai Embed Large",
            modelKind = MODEL_KIND_EMBEDDING,
            capabilities = listOf("embedding"),
            installed = false,
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
        data class ExpectedPreferenceRows(
            val languageTag: String,
            val selectedLanguageTag: String,
            val appearanceSummary: String,
            val languageSummary: String,
            val selectedState: String,
        )

        val expectedRows = listOf(
            ExpectedPreferenceRows(
                languageTag = "en",
                selectedLanguageTag = "ja",
                appearanceSummary = "Appearance: Dark",
                languageSummary = "Language: 日本語",
                selectedState = "Selected",
            ),
            ExpectedPreferenceRows(
                languageTag = "ko",
                selectedLanguageTag = "ko",
                appearanceSummary = "화면 모드: 다크",
                languageSummary = "언어: 한국어",
                selectedState = "선택됨",
            ),
        )
        val currentRows = mutableStateOf(expectedRows.first())

        compose.setContent {
            MaterialTheme {
                val expected = currentRows.value
                LocalizedTestContent(languageTag = expected.languageTag) {
                    key(expected.languageTag, expected.selectedLanguageTag) {
                        SettingsScreen(
                            state = RuntimeUiState(
                                isConnected = true,
                                runtimeStatus = "authenticated",
                                trustedRuntime = RuntimeTrustedRuntime(
                                    deviceId = "runtime-1",
                                    name = "AetherLink Runtime",
                                ),
                                backendAvailable = true,
                                selectedLanguageTag = expected.selectedLanguageTag,
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
        }

        expectedRows.forEach { expected ->
            compose.runOnUiThread {
                currentRows.value = expected
            }
            compose.waitForIdle()

            compose.onNode(
                hasContentDescription(expected.appearanceSummary) and hasStateDescription(expected.selectedState),
                useUnmergedTree = true,
            )
                .assertIsDisplayed()
            compose.onNode(
                hasContentDescription(expected.languageSummary) and hasStateDescription(expected.selectedState),
                useUnmergedTree = true,
            )
                .performScrollTo()
                .assertIsDisplayed()
        }
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
        val uninstalledEmbeddingModel = RuntimeModel(
            id = "ollama:mxbai-embed-large",
            name = "Mxbai Embed Large",
            modelKind = MODEL_KIND_EMBEDDING,
            capabilities = listOf("embedding"),
            installed = false,
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
                        models = listOf(chatModel, embeddingModel, uninstalledEmbeddingModel),
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

        compose.onNode(
            hasContentDescription("Selected memory indexing model Nomic Embed Text. Ollama - Installed.") and
                hasStateDescription("Selected"),
            useUnmergedTree = true,
        )
            .performScrollTo()
            .assertIsDisplayed()
        compose.onNodeWithContentDescription(
            "Memory indexing option. No model selected. No memory indexing model selected.",
            useUnmergedTree = true,
        )
            .performScrollTo()
            .assertIsDisplayed()
        compose.onNodeWithContentDescription(
            "Memory indexing model Mxbai Embed Large. Ollama - Not installed.",
            useUnmergedTree = true,
        )
            .performScrollTo()
            .assertIsNotEnabled()
    }

    @Test
    fun settingsModelRefreshActionLocalizesReadinessStates() {
        data class ExpectedModelRefreshState(
            val languageTag: String,
            val sectionTitle: String,
            val buttonLabel: String,
            val stateDescription: String,
            val isConnected: Boolean,
            val isLoadingModels: Boolean,
            val enabled: Boolean,
        )

        val embeddingModel = RuntimeModel(
            id = "ollama:nomic-embed-text",
            name = "Nomic Embed Text",
            modelKind = MODEL_KIND_EMBEDDING,
            capabilities = listOf("embedding"),
            installed = true,
            source = "local",
        )
        val expectedStates = listOf(
            ExpectedModelRefreshState(
                languageTag = "en",
                sectionTitle = "Memory indexing model",
                buttonLabel = "Refresh models",
                stateDescription = "Ready to refresh models.",
                isConnected = true,
                isLoadingModels = false,
                enabled = true,
            ),
            ExpectedModelRefreshState(
                languageTag = "ko",
                sectionTitle = "메모리 색인 모델",
                buttonLabel = "모델 새로고침",
                stateDescription = "모델을 새로고침할 준비가 되었습니다.",
                isConnected = true,
                isLoadingModels = false,
                enabled = true,
            ),
            ExpectedModelRefreshState(
                languageTag = "ja",
                sectionTitle = "メモリ インデックスモデル",
                buttonLabel = "モデルを更新",
                stateDescription = "モデルを更新できます。",
                isConnected = true,
                isLoadingModels = false,
                enabled = true,
            ),
            ExpectedModelRefreshState(
                languageTag = "zh-CN",
                sectionTitle = "记忆索引模型",
                buttonLabel = "刷新模型",
                stateDescription = "可以刷新模型。",
                isConnected = true,
                isLoadingModels = false,
                enabled = true,
            ),
            ExpectedModelRefreshState(
                languageTag = "fr",
                sectionTitle = "Modèle d’indexation de la mémoire",
                buttonLabel = "Actualiser les modèles",
                stateDescription = "Prêt à actualiser les modèles.",
                isConnected = true,
                isLoadingModels = false,
                enabled = true,
            ),
            ExpectedModelRefreshState(
                languageTag = "en",
                sectionTitle = "Memory indexing model",
                buttonLabel = "Loading models...",
                stateDescription = "Model refresh in progress.",
                isConnected = true,
                isLoadingModels = true,
                enabled = false,
            ),
            ExpectedModelRefreshState(
                languageTag = "ko",
                sectionTitle = "메모리 색인 모델",
                buttonLabel = "모델 불러오는 중...",
                stateDescription = "모델 새로고침이 진행 중입니다.",
                isConnected = true,
                isLoadingModels = true,
                enabled = false,
            ),
            ExpectedModelRefreshState(
                languageTag = "ja",
                sectionTitle = "メモリ インデックスモデル",
                buttonLabel = "モデルを読み込み中...",
                stateDescription = "モデルを更新中です。",
                isConnected = true,
                isLoadingModels = true,
                enabled = false,
            ),
            ExpectedModelRefreshState(
                languageTag = "zh-CN",
                sectionTitle = "记忆索引模型",
                buttonLabel = "正在加载模型...",
                stateDescription = "模型刷新正在进行。",
                isConnected = true,
                isLoadingModels = true,
                enabled = false,
            ),
            ExpectedModelRefreshState(
                languageTag = "fr",
                sectionTitle = "Modèle d’indexation de la mémoire",
                buttonLabel = "Chargement des modèles...",
                stateDescription = "Actualisation des modèles en cours.",
                isConnected = true,
                isLoadingModels = true,
                enabled = false,
            ),
            ExpectedModelRefreshState(
                languageTag = "en",
                sectionTitle = "Memory indexing model",
                buttonLabel = "Refresh models",
                stateDescription = "Connect to the trusted runtime before refreshing models.",
                isConnected = false,
                isLoadingModels = false,
                enabled = false,
            ),
            ExpectedModelRefreshState(
                languageTag = "ko",
                sectionTitle = "메모리 색인 모델",
                buttonLabel = "모델 새로고침",
                stateDescription = "모델을 새로고침하기 전에 신뢰된 런타임에 연결하세요.",
                isConnected = false,
                isLoadingModels = false,
                enabled = false,
            ),
            ExpectedModelRefreshState(
                languageTag = "ja",
                sectionTitle = "メモリ インデックスモデル",
                buttonLabel = "モデルを更新",
                stateDescription = "モデルを更新する前に、信頼済みランタイムに接続してください。",
                isConnected = false,
                isLoadingModels = false,
                enabled = false,
            ),
            ExpectedModelRefreshState(
                languageTag = "zh-CN",
                sectionTitle = "记忆索引模型",
                buttonLabel = "刷新模型",
                stateDescription = "刷新模型前，请先连接受信任的运行时。",
                isConnected = false,
                isLoadingModels = false,
                enabled = false,
            ),
            ExpectedModelRefreshState(
                languageTag = "fr",
                sectionTitle = "Modèle d’indexation de la mémoire",
                buttonLabel = "Actualiser les modèles",
                stateDescription = "Connectez-vous au runtime de confiance avant d’actualiser les modèles.",
                isConnected = false,
                isLoadingModels = false,
                enabled = false,
            ),
        )
        val currentState = mutableStateOf(expectedStates.first())
        var requestModelsClicks = 0

        compose.setContent {
            MaterialTheme {
                val expected = currentState.value
                LocalizedTestContent(languageTag = expected.languageTag) {
                    key(expected.languageTag, expected.isConnected, expected.isLoadingModels) {
                        SettingsScreen(
                            state = RuntimeUiState(
                                isConnected = expected.isConnected,
                                isLoadingModels = expected.isLoadingModels,
                                runtimeStatus = if (expected.isConnected) "authenticated" else "disconnected",
                                trustedRuntime = RuntimeTrustedRuntime(
                                    deviceId = "runtime-1",
                                    name = "AetherLink Runtime",
                                ),
                                backendAvailable = expected.isConnected,
                                selectedLanguageTag = expected.languageTag,
                                selectedTheme = RuntimeAppTheme.System,
                                models = if (expected.isConnected) listOf(embeddingModel) else emptyList(),
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
                            onRequestModels = { requestModelsClicks++ },
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

        expectedStates.forEach { expected ->
            compose.runOnUiThread {
                currentState.value = expected
            }
            compose.waitForIdle()
            repeat(3) {
                compose.onRoot().performTouchInput { swipeUp() }
                compose.waitForIdle()
            }
            compose.onNodeWithText(expected.sectionTitle)
                .assertIsDisplayed()
                .performClick()
            compose.waitForIdle()
            repeat(2) {
                compose.onRoot().performTouchInput { swipeUp() }
                compose.waitForIdle()
            }
            val refreshAction = compose.onNode(
                hasText(expected.buttonLabel) and hasStateDescription(expected.stateDescription),
            ).performScrollTo()
            if (expected.enabled) {
                refreshAction.assertIsEnabled().performClick()
            } else {
                refreshAction.assertIsNotEnabled()
            }
        }

        assertEquals(5, requestModelsClicks)
    }

    @Test
    fun settingsEmbeddingModelRowsLocalizeAccessibilitySummariesAcrossSupportedLanguages() {
        data class ExpectedEmbeddingModelSummary(
            val languageTag: String,
            val selectedModel: String,
            val noneOption: String,
            val uninstalledModel: String,
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
        val uninstalledEmbeddingModel = RuntimeModel(
            id = "ollama:mxbai-embed-large",
            name = "Mxbai Embed Large",
            modelKind = MODEL_KIND_EMBEDDING,
            capabilities = listOf("embedding"),
            installed = false,
            source = "local",
        )
        val expectedSummaries = listOf(
            ExpectedEmbeddingModelSummary(
                languageTag = "en",
                selectedModel = "Selected memory indexing model Nomic Embed Text. Ollama - Installed.",
                noneOption = "Memory indexing option. No model selected. No memory indexing model selected.",
                uninstalledModel = "Memory indexing model Mxbai Embed Large. Ollama - Not installed.",
            ),
            ExpectedEmbeddingModelSummary(
                languageTag = "ko",
                selectedModel = "선택된 메모리 색인 모델 Nomic Embed Text. Ollama - 설치됨.",
                noneOption = "메모리 색인 옵션. 없음. 메모리 색인 모델을 선택하지 않았습니다.",
                uninstalledModel = "메모리 색인 모델 Mxbai Embed Large. Ollama - 설치되지 않음.",
            ),
            ExpectedEmbeddingModelSummary(
                languageTag = "ja",
                selectedModel = "選択中のメモリ インデックスモデル「Nomic Embed Text」。Ollama - インストール済み。",
                noneOption = "メモリ インデックスの選択肢。なし。メモリ インデックスモデルは選択されていません。",
                uninstalledModel = "メモリ インデックスモデル「Mxbai Embed Large」。Ollama - 未インストール。",
            ),
            ExpectedEmbeddingModelSummary(
                languageTag = "zh-CN",
                selectedModel = "已选择记忆索引模型“Nomic Embed Text”。Ollama - 已安装。",
                noneOption = "记忆索引选项。无。未选择记忆索引模型。",
                uninstalledModel = "记忆索引模型“Mxbai Embed Large”。Ollama - 未安装。",
            ),
            ExpectedEmbeddingModelSummary(
                languageTag = "fr",
                selectedModel = "Modèle d’indexation de la mémoire sélectionné « Nomic Embed Text ». Ollama - Installé.",
                noneOption = "Option d’indexation de la mémoire. Aucun modèle sélectionné. Aucun modèle d’indexation de la mémoire sélectionné.",
                uninstalledModel = "Modèle d’indexation de la mémoire « Mxbai Embed Large ». Ollama - Non installé.",
            ),
        )
        val currentSummary = mutableStateOf(expectedSummaries.first())

        compose.setContent {
            MaterialTheme {
                val expected = currentSummary.value
                LocalizedTestContent(languageTag = expected.languageTag) {
                    key(expected.languageTag) {
                        SettingsScreen(
                            state = RuntimeUiState(
                                isConnected = true,
                                runtimeStatus = "authenticated",
                                trustedRuntime = RuntimeTrustedRuntime(
                                    deviceId = "runtime-1",
                                    name = "AetherLink Runtime",
                                ),
                                backendAvailable = true,
                                selectedLanguageTag = expected.languageTag,
                                selectedTheme = RuntimeAppTheme.System,
                                selectedEmbeddingModelId = embeddingModel.id,
                                models = listOf(chatModel, embeddingModel, uninstalledEmbeddingModel),
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

        expectedSummaries.forEach { expected ->
            compose.runOnUiThread {
                currentSummary.value = expected
            }
            compose.waitForIdle()
            repeat(3) {
                compose.onRoot().performTouchInput { swipeUp() }
                compose.waitForIdle()
            }
            compose.onNodeWithText(
                when (expected.languageTag) {
                    "ko" -> "메모리 색인 모델"
                    "ja" -> "メモリ インデックスモデル"
                    "zh-CN" -> "记忆索引模型"
                    "fr" -> "Modèle d’indexation de la mémoire"
                    else -> "Memory indexing model"
                },
            )
                .assertIsDisplayed()
                .performClick()
            compose.waitForIdle()
            repeat(2) {
                compose.onRoot().performTouchInput { swipeUp() }
                compose.waitForIdle()
            }
            compose.onNodeWithContentDescription(expected.selectedModel, useUnmergedTree = true)
                .performScrollTo()
                .assert(hasStateDescription(
                    when (expected.languageTag) {
                        "ko" -> "선택됨"
                        "ja" -> "選択済み"
                        "zh-CN" -> "已选择"
                        "fr" -> "Sélectionné"
                        else -> "Selected"
                    },
                ))
                .assertIsDisplayed()
            compose.onNodeWithContentDescription(expected.noneOption, useUnmergedTree = true)
                .performScrollTo()
                .assertIsDisplayed()
            compose.onNodeWithContentDescription(expected.uninstalledModel, useUnmergedTree = true)
                .performScrollTo()
                .assertIsNotEnabled()
        }
    }

    @Test
    fun settingsSavedEmbeddingModelRowLocalizesAccessibilitySummaryAcrossSupportedLanguages() {
        data class ExpectedSavedEmbeddingModelSummary(
            val languageTag: String,
            val sectionTitle: String,
            val savedModel: String,
            val selectedState: String,
        )

        val savedModelId = "ollama:nomic-embed-text"
        val savedModelName = "nomic-embed-text"
        val chatModel = RuntimeModel(
            id = "ollama:qwen3:8b",
            name = "Qwen3 8B",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = true,
            source = "local",
        )
        val expectedSummaries = listOf(
            ExpectedSavedEmbeddingModelSummary(
                languageTag = "en",
                sectionTitle = "Memory indexing model",
                savedModel = "Saved memory indexing model $savedModelName. Saved memory indexing model is missing from the runtime list. Refresh or choose another.",
                selectedState = "Selected",
            ),
            ExpectedSavedEmbeddingModelSummary(
                languageTag = "ko",
                sectionTitle = "메모리 색인 모델",
                savedModel = "저장된 메모리 색인 모델 $savedModelName. 저장된 메모리 색인 모델이 런타임 목록에 없습니다. 새로고침하거나 다른 모델을 선택하세요.",
                selectedState = "선택됨",
            ),
            ExpectedSavedEmbeddingModelSummary(
                languageTag = "ja",
                sectionTitle = "メモリ インデックスモデル",
                savedModel = "保存済みのメモリ インデックスモデル「$savedModelName」。保存済みのメモリ インデックスモデルはランタイム一覧にありません。更新するか別のモデルを選択してください。",
                selectedState = "選択済み",
            ),
            ExpectedSavedEmbeddingModelSummary(
                languageTag = "zh-CN",
                sectionTitle = "记忆索引模型",
                savedModel = "已保存的记忆索引模型“$savedModelName”。已保存的记忆索引模型不在运行时列表中。请刷新或选择其他模型。",
                selectedState = "已选择",
            ),
            ExpectedSavedEmbeddingModelSummary(
                languageTag = "fr",
                sectionTitle = "Modèle d’indexation de la mémoire",
                savedModel = "Modèle d’indexation de la mémoire enregistré « $savedModelName ». Le modèle d’indexation de la mémoire enregistré manque dans la liste du runtime. Actualisez ou choisissez-en un autre.",
                selectedState = "Sélectionné",
            ),
        )
        val currentSummary = mutableStateOf(expectedSummaries.first())

        compose.setContent {
            MaterialTheme {
                val expected = currentSummary.value
                LocalizedTestContent(languageTag = expected.languageTag) {
                    key(expected.languageTag) {
                        SettingsScreen(
                            state = RuntimeUiState(
                                isConnected = true,
                                runtimeStatus = "authenticated",
                                trustedRuntime = RuntimeTrustedRuntime(
                                    deviceId = "runtime-1",
                                    name = "AetherLink Runtime",
                                ),
                                backendAvailable = true,
                                selectedLanguageTag = expected.languageTag,
                                selectedTheme = RuntimeAppTheme.System,
                                selectedEmbeddingModelId = savedModelId,
                                models = listOf(chatModel),
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

        expectedSummaries.forEach { expected ->
            compose.runOnUiThread {
                currentSummary.value = expected
            }
            compose.waitForIdle()
            repeat(3) {
                compose.onRoot().performTouchInput { swipeUp() }
                compose.waitForIdle()
            }
            compose.onNodeWithText(expected.sectionTitle)
                .assertIsDisplayed()
                .performClick()
            compose.waitForIdle()
            compose.onNodeWithContentDescription(expected.savedModel, useUnmergedTree = true)
                .performScrollTo()
                .assert(hasStateDescription(expected.selectedState))
                .assertIsDisplayed()
        }
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
            .assert(hasClickActionLabel("Pause memory Project Alpha prefers concise Korean summaries"))
            .performClick()
        assertEquals(listOf(HapticFeedbackType.TextHandleMove), hapticFeedback.events)
        compose.onNodeWithContentDescription(
            "Enable memory Use metric units for travel planning",
            useUnmergedTree = true,
        )
            .performScrollTo()
            .assert(hasStateDescription("Paused"))
            .assert(hasClickActionLabel("Enable memory Use metric units for travel planning"))
            .assertIsDisplayed()
        compose.onNodeWithContentDescription(
            "Remove memory Project Alpha prefers concise Korean summaries",
            useUnmergedTree = true,
        )
            .performScrollTo()
            .assert(hasClickActionLabel("Remove memory Project Alpha prefers concise Korean summaries"))
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
    fun settingsMemoryRowsCapLongActionAccessibilityLabels() {
        val longMemory = "Project Alpha prefers concise Korean summaries with exact release notes, route diagnostics, accessibility checks, and model-provider caveats before every handoff."
        val cappedMemory = longMemory.take(MEMORY_ACTION_LABEL_MAX_CHARS).trimEnd() + "..."
        val activeMemory = RuntimeMemoryEntry(
            id = "memory-long",
            content = longMemory,
            enabled = true,
            createdAtMillis = 1_000L,
            updatedAtMillis = 2_000L,
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
                        memoryEntries = listOf(activeMemory),
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

        scrollUntilTextIsVisible("Memory")
        compose.onNodeWithText("Memory")
            .performScrollTo()
            .performClick()
        compose.waitForIdle()

        compose.onNodeWithText(longMemory).assertExists()
        compose.onNodeWithContentDescription(
            "Pause memory $cappedMemory",
            useUnmergedTree = true,
        )
            .assert(hasStateDescription("Enabled"))
            .assertExists()
        compose.onNodeWithContentDescription(
            "Remove memory $cappedMemory",
            useUnmergedTree = true,
        ).assertExists()
        compose.onAllNodesWithContentDescription(
            "Pause memory $longMemory",
            useUnmergedTree = true,
        ).assertCountEquals(0)
        compose.onAllNodesWithContentDescription(
            "Remove memory $longMemory",
            useUnmergedTree = true,
        ).assertCountEquals(0)
    }

    @Test
    fun settingsMemoryAddControlsLocalizeReadinessStateAcrossSupportedLanguages() {
        val languageTags = listOf("en", "ko", "ja", "zh-CN", "fr")
        val currentLanguage = mutableStateOf(languageTags.first())
        val connected = mutableStateOf(false)
        var addClicks = 0

        compose.setContent {
            MaterialTheme {
                LocalizedTestContent(languageTag = currentLanguage.value) {
                    key(currentLanguage.value, connected.value) {
                        SettingsScreen(
                            state = RuntimeUiState(
                                isConnected = connected.value,
                                runtimeStatus = if (connected.value) "authenticated" else "disconnected",
                                trustedRuntime = RuntimeTrustedRuntime(
                                    deviceId = "runtime-1",
                                    name = "AetherLink Runtime",
                                ),
                                selectedLanguageTag = currentLanguage.value,
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
                            onAddMemoryEntry = {
                                addClicks += 1
                            },
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

        languageTags.forEach { languageTag ->
            val localizedContext = ApplicationProvider
                .getApplicationContext<Context>()
                .localizedContext(languageTag)
            val memorySection = localizedContext.getString(R.string.memory_title)
            val memoryAddLabel = localizedContext.getString(R.string.memory_add_label)
            val addButton = localizedContext.getString(R.string.memory_add)
            val lockedState = localizedContext.getString(R.string.memory_connect_to_load)
            val emptyState = localizedContext.getString(R.string.memory_add_state_enter_memory)
            val readyState = localizedContext.getString(R.string.memory_add_state_ready)
            val draft = "Remember concise answers"

            compose.runOnUiThread {
                currentLanguage.value = languageTag
                connected.value = false
            }
            compose.waitForIdle()
            scrollUntilTextIsVisible(memorySection)
            compose.onNodeWithText(memorySection)
                .performScrollTo()
                .performClick()
            compose.waitForIdle()
            compose.onNode(hasContentDescription(memoryAddLabel) and hasStateDescription(lockedState))
                .performScrollTo()
                .assertIsNotEnabled()
            compose.onNode(
                hasText(addButton) and
                    hasStateDescription(lockedState) and
                    SemanticsMatcher.expectValue(SemanticsProperties.Role, Role.Button),
            )
                .performScrollTo()
                .assertIsNotEnabled()

            compose.runOnUiThread {
                connected.value = true
            }
            compose.waitForIdle()
            scrollUntilTextIsVisible(memorySection)
            compose.onNodeWithText(memorySection)
                .performScrollTo()
                .performClick()
            compose.waitForIdle()
            compose.onNode(
                hasContentDescription(memoryAddLabel) and hasSetTextAction() and hasStateDescription(emptyState),
            )
                .performScrollTo()
                .assertIsEnabled()
            compose.onNode(
                hasText(addButton) and
                    hasStateDescription(emptyState) and
                    SemanticsMatcher.expectValue(SemanticsProperties.Role, Role.Button),
            )
                .performScrollTo()
                .assertIsNotEnabled()

            compose.onNode(hasContentDescription(memoryAddLabel) and hasSetTextAction())
                .performTextInput(draft)
            compose.waitForIdle()
            compose.onNode(
                hasContentDescription(memoryAddLabel) and hasSetTextAction() and hasStateDescription(readyState),
            )
                .performScrollTo()
                .assertIsEnabled()
            compose.onNode(
                hasText(addButton) and
                    hasStateDescription(readyState) and
                    SemanticsMatcher.expectValue(SemanticsProperties.Role, Role.Button),
            )
                .performScrollTo()
                .assertIsEnabled()
        }

        assertEquals(0, addClicks)
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
    fun chatTopBarModelPickerExplainsDisabledStreamingStateAcrossSupportedLanguages() {
        data class ExpectedModelPickerStreamingState(
            val languageTag: String,
            val stateDescription: String,
        )
        val expectations = listOf(
            ExpectedModelPickerStreamingState(
                languageTag = "en",
                stateDescription = "Wait for the current response or cancel it before changing models.",
            ),
            ExpectedModelPickerStreamingState(
                languageTag = "ko",
                stateDescription = "현재 응답을 기다리거나 취소한 뒤 모델을 변경하세요.",
            ),
            ExpectedModelPickerStreamingState(
                languageTag = "ja",
                stateDescription = "現在の応答を待つかキャンセルしてから、モデルを変更してください。",
            ),
            ExpectedModelPickerStreamingState(
                languageTag = "zh-CN",
                stateDescription = "请等待当前回复完成或取消后再更改模型。",
            ),
            ExpectedModelPickerStreamingState(
                languageTag = "fr",
                stateDescription = "Attendez la réponse en cours ou annulez-la avant de changer de modèle.",
            ),
        )
        val currentLanguage = mutableStateOf(expectations.first().languageTag)
        val selectedChatModel = RuntimeModel(
            id = "ollama:qwen3:8b",
            name = "Qwen3 8B",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = true,
            source = "local",
        )

        compose.setContent {
            MaterialTheme {
                LocalizedTestContent(languageTag = currentLanguage.value) {
                    key(currentLanguage.value) {
                        ChatTopAppBarTitle(
                            state = RuntimeUiState(
                                isConnected = true,
                                runtimeStatus = "authenticated",
                                backendAvailable = true,
                                isStreaming = true,
                                selectedModelId = selectedChatModel.id,
                                models = listOf(selectedChatModel),
                            ),
                            onRequestModels = {},
                            onSelectModel = {},
                        )
                    }
                }
            }
        }

        expectations.forEach { expectation ->
            val localizedContext = ApplicationProvider
                .getApplicationContext<Context>()
                .localizedContext(expectation.languageTag)
            assertEquals(
                expectation.stateDescription,
                localizedContext.getString(R.string.model_picker_state_wait_for_stream),
            )
            compose.runOnUiThread {
                currentLanguage.value = expectation.languageTag
            }
            compose.waitForIdle()

            compose.onNode(hasText("Qwen3 8B") and hasStateDescription(expectation.stateDescription))
                .assertIsDisplayed()
                .assertIsNotEnabled()
        }
    }

    @Test
    fun chatTopBarModelPickerSearchClearsWithContextAndHapticFeedback() {
        val hapticFeedback = RecordingHapticFeedback()
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

        compose.setContent {
            MaterialTheme {
                CompositionLocalProvider(LocalHapticFeedback provides hapticFeedback) {
                    ChatTopAppBarTitle(
                        state = RuntimeUiState(
                            isConnected = true,
                            runtimeStatus = "authenticated",
                            backendAvailable = true,
                            models = listOf(qwenChatModel, llamaChatModel),
                        ),
                        onRequestModels = {},
                        onSelectModel = {},
                    )
                }
            }
        }

        compose.onNodeWithText("Choose model").assertIsDisplayed().performClick()
        compose.waitForIdle()
        compose.onNodeWithTag(CHAT_MODEL_SEARCH_TEST_TAG)
            .assertIsDisplayed()
            .performTextInput("missing")
        compose.waitForIdle()

        compose.onAllNodesWithText(
            "Try another model name, provider, service, or source.",
            useUnmergedTree = true,
        )
            .assertCountEquals(1)
        compose.onNodeWithContentDescription("Clear model search for missing", useUnmergedTree = true)
            .assertIsDisplayed()
            .assert(hasClickActionLabel("Clear model search for missing"))
        hapticFeedback.events.clear()
        compose.onNodeWithContentDescription("Clear model search for missing", useUnmergedTree = true)
            .performClick()
        compose.waitForIdle()

        assertEquals(listOf(HapticFeedbackType.TextHandleMove), hapticFeedback.events)
        compose.onNodeWithText("Llama 3.1 8B", useUnmergedTree = true).assertIsDisplayed()
        compose.onAllNodesWithText(
            "Try another model name, provider, service, or source.",
            useUnmergedTree = true,
        )
            .assertCountEquals(0)
    }

    @Test
    fun chatTopBarModelPickerSearchLocalizesClearAndNoResultsAcrossSupportedLanguages() {
        data class ExpectedModelSearchCopy(
            val languageTag: String,
            val clearLabel: String,
            val noResults: String,
            val chooseModelLabel: String,
        )

        val searchQuery = "missing"
        val expectedCopies = listOf(
            ExpectedModelSearchCopy(
                languageTag = "en",
                clearLabel = "Clear model search for missing",
                noResults = "Try another model name, provider, service, or source.",
                chooseModelLabel = "Choose model",
            ),
            ExpectedModelSearchCopy(
                languageTag = "ko",
                clearLabel = "missing 검색어로 된 모델 검색 지우기",
                noResults = "다른 모델 이름, 제공자, 서비스 또는 소스로 검색해보세요.",
                chooseModelLabel = "모델 선택",
            ),
            ExpectedModelSearchCopy(
                languageTag = "ja",
                clearLabel = "missing のモデル検索をクリア",
                noResults = "別のモデル名、プロバイダー、サービス、またはソースで検索してください。",
                chooseModelLabel = "モデルを選択",
            ),
            ExpectedModelSearchCopy(
                languageTag = "zh-CN",
                clearLabel = "清除“missing”的模型搜索",
                noResults = "请尝试其他模型名称、提供方、服务或来源。",
                chooseModelLabel = "选择模型",
            ),
            ExpectedModelSearchCopy(
                languageTag = "fr",
                clearLabel = "Effacer la recherche de modèles pour missing",
                noResults = "Essayez un autre nom de modèle, fournisseur, service ou source.",
                chooseModelLabel = "Choisir un modèle",
            ),
        )
        val currentCopy = mutableStateOf(expectedCopies.first())
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

        expectedCopies.forEach { expected ->
            val context = ApplicationProvider
                .getApplicationContext<Context>()
                .localizedContext(expected.languageTag)
            assertEquals(
                expected.clearLabel,
                context.getString(R.string.clear_model_search_named, searchQuery),
            )
            assertEquals(
                expected.noResults,
                context.getString(R.string.no_model_search_results),
            )
        }

        compose.setContent {
            MaterialTheme {
                val expected = currentCopy.value
                LocalizedTestContent(languageTag = expected.languageTag) {
                    key(expected.languageTag) {
                        ChatTopAppBarTitle(
                            state = RuntimeUiState(
                                isConnected = true,
                                runtimeStatus = "authenticated",
                                backendAvailable = true,
                                models = listOf(qwenChatModel, llamaChatModel),
                            ),
                            onRequestModels = {},
                            onSelectModel = {},
                        )
                    }
                }
            }
        }

        expectedCopies.forEach { expected ->
            compose.runOnUiThread {
                currentCopy.value = expected
            }
            compose.waitForIdle()
            compose.onNodeWithText(expected.chooseModelLabel).assertIsDisplayed().performClick()
            compose.waitForIdle()
            compose.onNodeWithTag(CHAT_MODEL_SEARCH_TEST_TAG)
                .assertIsDisplayed()
                .performTextInput(searchQuery)
            compose.waitForIdle()

            compose.onNodeWithContentDescription(expected.clearLabel, useUnmergedTree = true)
                .assertIsDisplayed()
                .assert(hasClickActionLabel(expected.clearLabel))
        }
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
    fun chatTopBarModelPickerRowsExposeAccessibilitySummaries() {
        val selectedChatModel = RuntimeModel(
            id = "ollama:qwen3:8b",
            name = "Qwen3 8B",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = true,
            source = "local",
        )
        val runningChatModel = RuntimeModel(
            id = "ollama:llama3.1:8b",
            name = "Llama 3.1 8B",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = true,
            running = true,
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
                        selectedModelId = selectedChatModel.id,
                        models = listOf(
                            selectedChatModel,
                            runningChatModel,
                            uninstalledChatModel,
                        ),
                    ),
                    onRequestModels = {},
                    onSelectModel = {},
                )
            }
        }

        compose.onNodeWithText("Qwen3 8B").assertIsDisplayed().performClick()
        compose.waitForIdle()

        compose.onNode(
            hasContentDescription("Selected chat model Qwen3 8B. Ollama - Installed.") and
                hasStateDescription("Selected") and
                hasClickActionLabel("Choose model") and
                hasClickAction(),
            useUnmergedTree = true,
        ).assertIsDisplayed()
        compose.onNode(
            hasContentDescription("Chat model Llama 3.1 8B. Ollama - Running.") and
                hasClickActionLabel("Choose model") and
                hasClickAction(),
            useUnmergedTree = true,
        ).assertIsDisplayed()
        compose.onNode(
            hasContentDescription("Chat model Gemma 4 26B. Ollama - Not installed.") and
                hasStateDescription("Install model") and
                hasClickActionLabel("Install model") and
                hasClickAction(),
            useUnmergedTree = true,
        ).assertIsDisplayed()
    }

    @Test
    fun chatTopBarModelPickerRowsLocalizeAccessibilitySummariesAcrossSupportedLanguages() {
        data class ExpectedSummary(
            val languageTag: String,
            val selectedSummary: String,
        )

        val expectedSummaries = listOf(
            ExpectedSummary(
                languageTag = "en",
                selectedSummary = "Selected chat model Qwen3 8B. Ollama - Installed.",
            ),
            ExpectedSummary(
                languageTag = "ko",
                selectedSummary = "선택된 채팅 모델 Qwen3 8B. Ollama - 설치됨.",
            ),
            ExpectedSummary(
                languageTag = "ja",
                selectedSummary = "選択中のチャットモデル「Qwen3 8B」。Ollama - インストール済み。",
            ),
            ExpectedSummary(
                languageTag = "zh-CN",
                selectedSummary = "已选择聊天模型“Qwen3 8B”。Ollama - 已安装。",
            ),
            ExpectedSummary(
                languageTag = "fr",
                selectedSummary = "Modèle de chat sélectionné « Qwen3 8B ». Ollama - Installé.",
            ),
        )

        expectedSummaries.forEach { expected ->
            val context = ApplicationProvider
                .getApplicationContext<Context>()
                .localizedContext(expected.languageTag)
            val statusLine = context.getString(
                R.string.model_status_value,
                "Ollama",
                context.getString(R.string.model_installed),
            )

            assertEquals(
                expected.selectedSummary,
                context.getString(
                    R.string.chat_model_row_summary_selected,
                    "Qwen3 8B",
                    statusLine,
                ),
            )
        }
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
            MaterialTheme {
                CompositionLocalProvider(LocalHapticFeedback provides hapticFeedback) {
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
        }

        compose.onNodeWithText("Follow up?").assertIsDisplayed()
        compose.onNodeWithText("Summarize again?").assertIsDisplayed()
        compose.onNodeWithContentDescription("Suggested question: Summarize again?", useUnmergedTree = true)
            .assertIsDisplayed()
            .assert(hasClickActionLabel("Insert suggested question"))
        compose.onNodeWithText("Check route status").assertIsDisplayed()
        compose.onNodeWithText("Draft a test plan").assertIsDisplayed()
        assertNoVisibleText("follow up?")
        assertNoVisibleText("Hidden extra suggestion")

        hapticFeedback.events.clear()
        compose.onNodeWithText("Summarize again?").performClick()

        assertEquals(listOf("Summarize again?"), clickedSuggestions)
        assertEquals(listOf(HapticFeedbackType.TextHandleMove), hapticFeedback.events)
    }

    @Test
    fun chatScreenGeneratingSuggestionsRowAnnouncesAcrossSupportedLanguages() {
        val languageTag = mutableStateOf("en")
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
                LocalizedTestContent(languageTag = languageTag.value) {
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
                            isLoadingSuggestions = true,
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
        }

        listOf("en", "ko", "ja", "zh-CN", "fr").forEach { nextLanguageTag ->
            compose.runOnUiThread {
                languageTag.value = nextLanguageTag
            }
            compose.waitForIdle()

            val expectedAnnouncement = ApplicationProvider
                .getApplicationContext<Context>()
                .localizedContext(nextLanguageTag)
                .getString(R.string.generating_suggestions)
            compose.onNodeWithText(expectedAnnouncement).assertIsDisplayed()
            compose.onNodeWithContentDescription(expectedAnnouncement, useUnmergedTree = true)
                .assertIsDisplayed()
                .assert(hasPoliteLiveRegion())
        }
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

    private fun hasLongClickActionLabel(label: String): SemanticsMatcher {
        return SemanticsMatcher("has long-click action label $label") { node ->
            node.config.getOrNull(SemanticsActions.OnLongClick)?.label == label
        }
    }

    private fun hasClickActionLabel(label: String): SemanticsMatcher {
        return SemanticsMatcher("has click action label $label") { node ->
            node.config.getOrNull(SemanticsActions.OnClick)?.label == label
        }
    }

    private fun hasPoliteLiveRegion(): SemanticsMatcher {
        return SemanticsMatcher.expectValue(
            SemanticsProperties.LiveRegion,
            LiveRegionMode.Polite,
        )
    }

    private fun waitForCopiedAnnouncement(message: String) {
        compose.waitUntil(timeoutMillis = 2_000) {
            compose.onAllNodesWithContentDescription(message, useUnmergedTree = true)
                .fetchSemanticsNodes()
                .isNotEmpty()
        }
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
