package com.localagentbridge.android.ui

import android.content.Context
import android.content.res.Configuration
import android.os.LocaleList
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.width
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.assert
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.hasClickAction
import androidx.compose.ui.test.hasContentDescription
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performScrollToIndex
import androidx.compose.ui.test.performScrollToNode
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.DpRect
import androidx.compose.ui.unit.dp
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.localagentbridge.android.AetherLinkNavigationDrawerContent
import com.localagentbridge.android.AppDestination
import com.localagentbridge.android.DRAWER_CHAT_SEARCH_NO_RESULTS_TEST_TAG
import com.localagentbridge.android.DRAWER_EMPTY_HISTORY_TEST_TAG
import com.localagentbridge.android.DRAWER_HISTORY_TEST_TAG
import com.localagentbridge.android.PAIRING_QR_FLASHLIGHT_BUTTON_TEST_TAG
import com.localagentbridge.android.PAIRING_QR_SCANNER_CAMERA_SURFACE_TEST_TAG
import com.localagentbridge.android.PAIRING_QR_SCANNER_CANCEL_BUTTON_TEST_TAG
import com.localagentbridge.android.PAIRING_QR_SCANNER_CHROME_TEST_TAG
import com.localagentbridge.android.PAIRING_QR_SCANNER_CLOSE_BUTTON_TEST_TAG
import com.localagentbridge.android.PAIRING_QR_SCANNER_FEEDBACK_TEST_TAG
import com.localagentbridge.android.PAIRING_QR_SCANNER_PERMISSION_ACTION_TEST_TAG
import com.localagentbridge.android.PAIRING_QR_SCANNER_PERMISSION_CANCEL_BUTTON_TEST_TAG
import com.localagentbridge.android.PAIRING_QR_SCANNER_PERMISSION_PANEL_TEST_TAG
import com.localagentbridge.android.PAIRING_QR_SCANNER_TARGET_TEST_TAG
import com.localagentbridge.android.PairingQrScannerChrome
import com.localagentbridge.android.PairingQrScannerFeedback
import com.localagentbridge.android.R
import com.localagentbridge.android.drawerChatRowTestTag
import com.localagentbridge.android.runtime.MODEL_KIND_CHAT
import com.localagentbridge.android.runtime.RuntimeAppTheme
import com.localagentbridge.android.runtime.RuntimeChatMessage
import com.localagentbridge.android.runtime.RuntimeChatSession
import com.localagentbridge.android.runtime.RuntimeMemoryEntry
import com.localagentbridge.android.runtime.RuntimeModel
import com.localagentbridge.android.runtime.RuntimeTrustedRuntime
import com.localagentbridge.android.runtime.RuntimeUiState
import java.util.Locale
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config

@RunWith(AndroidJUnit4::class)
@Config(sdk = [35])
class AndroidCoreSurfaceFontScaleQualificationTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun coreSurfacesRemainUsableAt100PercentFontScale() {
        runCoreSurfaceQualification(fontScale = 1f)
    }

    @Test
    fun coreSurfacesRemainUsableAt150PercentFontScale() {
        runCoreSurfaceQualification(fontScale = 1.5f)
    }

    @Test
    fun coreSurfacesRemainUsableAt200PercentFontScale() {
        runCoreSurfaceQualification(fontScale = 2f)
    }

    private fun runCoreSurfaceQualification(fontScale: Float) {
        require(fontScale in canonicalFontScales)

        val languageTag = mutableStateOf(supportedLanguageTags.first())
        val surfaceCase = mutableStateOf(SurfaceCase.ScannerActive)
        val renderGeneration = mutableStateOf(0)
        val chatModel = RuntimeModel(
            id = "ollama:qwen3:8b",
            name = "Qwen3 8B",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = true,
            source = "local",
        )
        val chatSessions = listOf(
            RuntimeChatSession(
                id = "font-scale-chat",
                title = "Font scale release check",
                modelId = chatModel.id,
                messageCount = 8,
                updatedAtMillis = 1_782_707_400_000L,
            ),
        )
        val chatMessages = (1..12).map { index ->
            RuntimeChatMessage(
                id = "font-scale-message-$index",
                role = if (index % 2 == 0) "assistant" else "user",
                content = if (index == 12) {
                    "The latest response and composer remain reachable."
                } else {
                    "Representative font scale message $index."
                },
            )
        }
        val memoryEntry = RuntimeMemoryEntry(
            id = "font-scale-memory",
            content = "Prefer concise release summaries.",
            enabled = true,
            createdAtMillis = 1_782_703_800_000L,
            updatedAtMillis = 1_782_707_400_000L,
        )
        val trustedRuntime = RuntimeTrustedRuntime(
            deviceId = "font-scale-runtime",
            name = "AetherLink Runtime",
        )

        compose.setContent {
            MaterialTheme {
                LocalizedQualificationContent(
                    languageTag = languageTag.value,
                    fontScale = fontScale,
                ) {
                    key(
                        fontScale,
                        languageTag.value,
                        surfaceCase.value,
                        renderGeneration.value,
                    ) {
                        when (surfaceCase.value) {
                            SurfaceCase.ScannerActive,
                            SurfaceCase.ScannerInvalid,
                            SurfaceCase.ScannerPermission,
                            SurfaceCase.ScannerSettingsRecovery,
                            -> ScannerQualificationSurface(surfaceCase.value)

                            SurfaceCase.DrawerEmpty,
                            SurfaceCase.DrawerPopulated,
                            SurfaceCase.DrawerSearchNoResults,
                            -> DrawerQualificationSurface(
                                surfaceCase = surfaceCase.value,
                                chatSessions = chatSessions,
                                trustedRuntime = trustedRuntime,
                            )

                            SurfaceCase.ChatPopulated,
                            SurfaceCase.ChatStreaming,
                            -> ChatQualificationSurface(
                                surfaceCase = surfaceCase.value,
                                languageTag = languageTag.value,
                                model = chatModel,
                                messages = chatMessages,
                                trustedRuntime = trustedRuntime,
                            )

                            SurfaceCase.SettingsPairing,
                            SurfaceCase.SettingsData,
                            -> SettingsQualificationSurface(
                                surfaceCase = surfaceCase.value,
                                languageTag = languageTag.value,
                                model = chatModel,
                                chatSessions = chatSessions,
                                memoryEntry = memoryEntry,
                                trustedRuntime = trustedRuntime,
                            )
                        }
                    }
                }
            }
        }

        fun show(nextSurface: SurfaceCase, nextLanguageTag: String) {
            compose.runOnUiThread {
                surfaceCase.value = nextSurface
                languageTag.value = nextLanguageTag
                renderGeneration.value += 1
            }
            compose.waitForIdle()
            compose.onNodeWithTag(QUALIFICATION_ROOT_TEST_TAG).assertIsDisplayed()
        }

        supportedLanguageTags.forEach { nextLanguageTag ->
            val localizedContext = localizedContext(nextLanguageTag, fontScale)

            show(SurfaceCase.ScannerActive, nextLanguageTag)
            assertScannerActive(
                label = "$fontScale $nextLanguageTag scanner active",
                localizedContext = localizedContext,
            )

            show(SurfaceCase.DrawerEmpty, nextLanguageTag)
            assertDrawerEmpty(
                label = "$fontScale $nextLanguageTag drawer empty",
                localizedContext = localizedContext,
            )

            show(SurfaceCase.ChatPopulated, nextLanguageTag)
            assertChatPopulated(
                label = "$fontScale $nextLanguageTag chat populated",
                localizedContext = localizedContext,
                messages = chatMessages,
            )

            show(SurfaceCase.SettingsPairing, nextLanguageTag)
            assertSettingsPairing(
                label = "$fontScale $nextLanguageTag settings pairing",
                localizedContext = localizedContext,
            )

            show(SurfaceCase.SettingsData, nextLanguageTag)
            assertSettingsDataHeaders(
                localizedContext = localizedContext,
                expandDetails = false,
                memoryEntry = memoryEntry,
                chatSession = chatSessions.single(),
            )
        }

        fullCoverageLanguageTags.forEach { nextLanguageTag ->
            val localizedContext = localizedContext(nextLanguageTag, fontScale)

            show(SurfaceCase.ScannerInvalid, nextLanguageTag)
            assertScannerInvalid("$fontScale $nextLanguageTag scanner invalid")

            show(SurfaceCase.ScannerPermission, nextLanguageTag)
            assertScannerPermission("$fontScale $nextLanguageTag scanner permission")

            show(SurfaceCase.ScannerSettingsRecovery, nextLanguageTag)
            assertScannerPermission("$fontScale $nextLanguageTag scanner settings recovery")

            show(SurfaceCase.DrawerPopulated, nextLanguageTag)
            assertDrawerPopulated(
                label = "$fontScale $nextLanguageTag drawer populated",
                chatSession = chatSessions.single(),
            )

            show(SurfaceCase.DrawerSearchNoResults, nextLanguageTag)
            compose.onNodeWithTag(DRAWER_HISTORY_TEST_TAG)
                .performScrollToNode(hasTestTag(DRAWER_CHAT_SEARCH_NO_RESULTS_TEST_TAG))
            assertTaggedInside(
                label = "$fontScale $nextLanguageTag drawer search no results",
                tag = DRAWER_CHAT_SEARCH_NO_RESULTS_TEST_TAG,
            )

            show(SurfaceCase.ChatStreaming, nextLanguageTag)
            assertChatStreaming(
                label = "$fontScale $nextLanguageTag chat streaming",
                localizedContext = localizedContext,
            )

            show(SurfaceCase.SettingsData, nextLanguageTag)
            assertSettingsDataHeaders(
                localizedContext = localizedContext,
                expandDetails = true,
                memoryEntry = memoryEntry,
                chatSession = chatSessions.single(),
            )
        }
    }

    @Composable
    private fun ScannerQualificationSurface(surfaceCase: SurfaceCase) {
        Surface(
            modifier = Modifier
                .width(320.dp)
                .height(560.dp)
                .testTag(QUALIFICATION_ROOT_TEST_TAG),
        ) {
            val hasCameraPermission = surfaceCase == SurfaceCase.ScannerActive ||
                surfaceCase == SurfaceCase.ScannerInvalid
            PairingQrScannerChrome(
                hasCameraPermission = hasCameraPermission,
                cameraPermissionPermanentlyDenied =
                    surfaceCase == SurfaceCase.ScannerSettingsRecovery,
                torchAvailable = surfaceCase == SurfaceCase.ScannerActive,
                torchEnabled = false,
                scannerFeedback = if (surfaceCase == SurfaceCase.ScannerInvalid) {
                    PairingQrScannerFeedback.InvalidPairingQr
                } else {
                    null
                },
                onTorchToggle = {},
                onCancel = {},
                onRequestCameraPermission = {},
                onOpenAppSettings = {},
                modifier = Modifier.fillMaxSize(),
            ) {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .testTag(CAMERA_PREVIEW_TEST_TAG),
                )
            }
        }
    }

    @Composable
    private fun DrawerQualificationSurface(
        surfaceCase: SurfaceCase,
        chatSessions: List<RuntimeChatSession>,
        trustedRuntime: RuntimeTrustedRuntime,
    ) {
        val populated = surfaceCase == SurfaceCase.DrawerPopulated
        val searchingWithoutResults = surfaceCase == SurfaceCase.DrawerSearchNoResults
        val visibleSessions = if (populated) chatSessions else emptyList()

        Surface(
            modifier = Modifier
                .width(320.dp)
                .height(900.dp)
                .testTag(QUALIFICATION_ROOT_TEST_TAG),
        ) {
            AetherLinkNavigationDrawerContent(
                state = RuntimeUiState(
                    isConnected = true,
                    runtimeStatus = "ready",
                    trustedRuntime = trustedRuntime,
                    backendAvailable = true,
                    chatSessions = if (populated || searchingWithoutResults) {
                        chatSessions
                    } else {
                        emptyList()
                    },
                ),
                effectiveDestination = AppDestination.Chat,
                chatSearchQuery = if (searchingWithoutResults) "no-match" else "",
                hasAnyChatSessions = populated || searchingWithoutResults,
                hasChatSearchQuery = searchingWithoutResults,
                hasChatSearchResults = populated,
                filteredChatSessions = visibleSessions,
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

    @Composable
    private fun ChatQualificationSurface(
        surfaceCase: SurfaceCase,
        languageTag: String,
        model: RuntimeModel,
        messages: List<RuntimeChatMessage>,
        trustedRuntime: RuntimeTrustedRuntime,
    ) {
        val streaming = surfaceCase == SurfaceCase.ChatStreaming

        Surface(
            modifier = Modifier
                .width(320.dp)
                .height(720.dp)
                .testTag(QUALIFICATION_ROOT_TEST_TAG),
        ) {
            ChatScreen(
                state = RuntimeUiState(
                    isConnected = true,
                    runtimeStatus = "ready",
                    trustedRuntime = trustedRuntime,
                    backendAvailable = true,
                    selectedLanguageTag = languageTag,
                    selectedModelId = model.id,
                    models = listOf(model),
                    chatInput = if (streaming) {
                        "Streaming response"
                    } else {
                        "Ready to send"
                    },
                    isStreaming = streaming,
                    activeRequestId = if (streaming) "font-scale-request" else null,
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
                onScanLatestQr = {},
                onRegenerateLatestResponse = {},
                onReuseLatestUserMessage = {},
            )
        }
    }

    @Composable
    private fun SettingsQualificationSurface(
        surfaceCase: SurfaceCase,
        languageTag: String,
        model: RuntimeModel,
        chatSessions: List<RuntimeChatSession>,
        memoryEntry: RuntimeMemoryEntry,
        trustedRuntime: RuntimeTrustedRuntime,
    ) {
        val showsData = surfaceCase == SurfaceCase.SettingsData

        Surface(
            modifier = Modifier
                .width(260.dp)
                .height(760.dp)
                .testTag(QUALIFICATION_ROOT_TEST_TAG),
        ) {
            SettingsScreen(
                state = RuntimeUiState(
                    isConnected = showsData,
                    runtimeStatus = if (showsData) "ready" else "disconnected",
                    trustedRuntime = trustedRuntime.takeIf { showsData },
                    backendAvailable = showsData,
                    selectedLanguageTag = languageTag,
                    selectedTheme = RuntimeAppTheme.System,
                    selectedModelId = model.id.takeIf { showsData },
                    models = if (showsData) listOf(model) else emptyList(),
                    chatSessions = if (showsData) chatSessions else emptyList(),
                    memoryEntries = if (showsData) listOf(memoryEntry) else emptyList(),
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
                modifier = Modifier
                    .fillMaxSize()
                    .testTag(SETTINGS_SCROLL_TEST_TAG),
            )
        }
    }

    private fun assertScannerActive(label: String, localizedContext: Context) {
        compose.onNodeWithText(localizedContext.getString(R.string.qr_scanner_title))
            .assertIsDisplayed()
        listOf(
            PAIRING_QR_SCANNER_CHROME_TEST_TAG,
            PAIRING_QR_SCANNER_CAMERA_SURFACE_TEST_TAG,
            PAIRING_QR_SCANNER_TARGET_TEST_TAG,
            CAMERA_PREVIEW_TEST_TAG,
        ).forEach { tag ->
            assertTaggedInside("$label $tag", tag)
        }
        listOf(
            PAIRING_QR_SCANNER_CLOSE_BUTTON_TEST_TAG,
            PAIRING_QR_FLASHLIGHT_BUTTON_TEST_TAG,
            PAIRING_QR_SCANNER_CANCEL_BUTTON_TEST_TAG,
        ).forEach { tag ->
            assertActionInside("$label $tag", tag)
        }
    }

    private fun assertScannerInvalid(label: String) {
        assertTaggedInside(
            "$label feedback",
            PAIRING_QR_SCANNER_FEEDBACK_TEST_TAG,
        )
        assertActionInside(
            "$label cancel",
            PAIRING_QR_SCANNER_CANCEL_BUTTON_TEST_TAG,
        )
    }

    private fun assertScannerPermission(label: String) {
        assertTaggedInside(
            "$label panel",
            PAIRING_QR_SCANNER_PERMISSION_PANEL_TEST_TAG,
        )
        assertActionInside(
            "$label primary action",
            PAIRING_QR_SCANNER_PERMISSION_ACTION_TEST_TAG,
        )
        assertActionInside(
            "$label cancel action",
            PAIRING_QR_SCANNER_PERMISSION_CANCEL_BUTTON_TEST_TAG,
        )
    }

    private fun assertDrawerEmpty(label: String, localizedContext: Context) {
        val emptyText = localizedContext.getString(R.string.no_previous_chats)
        compose.onNodeWithTag(DRAWER_HISTORY_TEST_TAG)
            .performScrollToNode(hasTestTag(DRAWER_EMPTY_HISTORY_TEST_TAG))
        compose.onNodeWithTag(DRAWER_EMPTY_HISTORY_TEST_TAG, useUnmergedTree = true)
            .assert(hasText(emptyText))
            .assert(hasContentDescription(emptyText))
            .assertIsDisplayed()
        assertTaggedInside(
            "$label empty-history message",
            DRAWER_EMPTY_HISTORY_TEST_TAG,
            useUnmergedTree = true,
        )
    }

    private fun assertDrawerPopulated(label: String, chatSession: RuntimeChatSession) {
        val rowTag = drawerChatRowTestTag(chatSession.id)
        compose.onNodeWithTag(DRAWER_HISTORY_TEST_TAG)
            .performScrollToNode(hasText(chatSession.title))
        compose.waitForIdle()
        assertTaggedInside("$label chat row", rowTag, useUnmergedTree = true)
    }

    private fun assertChatPopulated(
        label: String,
        localizedContext: Context,
        messages: List<RuntimeChatMessage>,
    ) {
        compose.onNodeWithTag(CHAT_MESSAGE_LIST_TEST_TAG)
            .performScrollToIndex(messages.lastIndex - 1)
        compose.waitForIdle()

        assertTaggedInside(
            "$label latest message",
            chatMessageRowTestTag(messages.last().id),
        )
        assertTaggedInside(
            "$label composer",
            CHAT_COMPOSER_CONTAINER_TEST_TAG,
            useUnmergedTree = true,
        )
        assertActionInside(
            "$label attach action",
            CHAT_COMPOSER_ATTACH_ACTION_TEST_TAG,
            useUnmergedTree = true,
        )
        assertActionInside(
            "$label send action",
            CHAT_COMPOSER_SEND_ACTION_TEST_TAG,
            useUnmergedTree = true,
        )
        compose.onNodeWithTag(CHAT_COMPOSER_INPUT_TEST_TAG, useUnmergedTree = true)
            .assert(
                hasContentDescription(localizedContext.getString(R.string.message)),
            )
            .assertIsDisplayed()
    }

    private fun assertChatStreaming(label: String, localizedContext: Context) {
        assertActionInside(
            "$label cancel action",
            CHAT_COMPOSER_CANCEL_ACTION_TEST_TAG,
            useUnmergedTree = true,
        )
        compose.onNodeWithTag(CHAT_COMPOSER_CANCEL_ACTION_TEST_TAG, useUnmergedTree = true)
            .assertIsEnabled()
        compose.onNodeWithTag(CHAT_COMPOSER_INPUT_TEST_TAG, useUnmergedTree = true)
            .assert(
                hasContentDescription(localizedContext.getString(R.string.message)),
            )
            .assertIsDisplayed()
            .assertIsNotEnabled()
    }

    private fun assertSettingsPairing(label: String, localizedContext: Context) {
        compose.onNodeWithText(localizedContext.getString(R.string.qr_pairing_title))
            .assertIsDisplayed()
        assertTaggedInside(
            "$label pairing panel",
            SETTINGS_QR_PAIRING_PANEL_TEST_TAG,
            useUnmergedTree = true,
        )
        assertActionInside(
            "$label scan action",
            SETTINGS_QR_PAIRING_SCAN_BUTTON_TEST_TAG,
            useUnmergedTree = true,
        )
    }

    private fun assertSettingsDataHeaders(
        localizedContext: Context,
        expandDetails: Boolean,
        memoryEntry: RuntimeMemoryEntry,
        chatSession: RuntimeChatSession,
    ) {
        val memoryTitle = localizedContext.getString(R.string.memory_title)
        val historyTitle = localizedContext.getString(R.string.chat_history_settings_title)

        compose.onNodeWithTag(SETTINGS_SCROLL_TEST_TAG)
            .performScrollToNode(hasText(memoryTitle))
        compose.onNodeWithText(memoryTitle)
            .performScrollTo()
            .assertIsDisplayed()
            .let { node ->
                if (expandDetails) {
                    node.performClick()
                    compose.waitForIdle()
                    compose.onNodeWithText(memoryEntry.content)
                        .performScrollTo()
                        .assertIsDisplayed()
                }
            }

        compose.onNodeWithTag(SETTINGS_SCROLL_TEST_TAG)
            .performScrollToNode(hasText(historyTitle))
        compose.onNodeWithText(historyTitle)
            .performScrollTo()
            .assertIsDisplayed()
            .let { node ->
                if (expandDetails) {
                    node.performClick()
                    compose.waitForIdle()
                    compose.onNodeWithText(chatSession.title)
                        .performScrollTo()
                        .assertIsDisplayed()
                }
            }
    }

    private fun assertActionInside(
        label: String,
        tag: String,
        useUnmergedTree: Boolean = false,
    ) {
        val bounds = compose.onNodeWithTag(tag, useUnmergedTree = useUnmergedTree)
            .assertIsDisplayed()
            .getUnclippedBoundsInRoot()
        assertTrue(
            "$label height should be at least 48dp. bounds=$bounds",
            bounds.bottom - bounds.top >= 48.dp,
        )
        assertTrue(
            "$label width should be at least 48dp. bounds=$bounds",
            bounds.right - bounds.left >= 48.dp,
        )
        assertBoundsInside(label, bounds, qualificationRootBounds())
    }

    private fun assertTaggedInside(
        label: String,
        tag: String,
        useUnmergedTree: Boolean = false,
    ) {
        val bounds = compose.onNodeWithTag(tag, useUnmergedTree = useUnmergedTree)
            .assertIsDisplayed()
            .getUnclippedBoundsInRoot()
        assertBoundsInside(label, bounds, qualificationRootBounds())
    }

    private fun qualificationRootBounds(): DpRect {
        return compose.onNodeWithTag(QUALIFICATION_ROOT_TEST_TAG)
            .assertIsDisplayed()
            .getUnclippedBoundsInRoot()
    }

    private fun assertBoundsInside(label: String, bounds: DpRect, container: DpRect) {
        assertTrue(
            "$label should stay inside the qualification root horizontally. " +
                "bounds=$bounds container=$container",
            bounds.left >= container.left && bounds.right <= container.right,
        )
        assertTrue(
            "$label should stay inside the qualification root vertically. " +
                "bounds=$bounds container=$container",
            bounds.top >= container.top && bounds.bottom <= container.bottom,
        )
    }

    @Composable
    private fun LocalizedQualificationContent(
        languageTag: String,
        fontScale: Float,
        content: @Composable () -> Unit,
    ) {
        val baseContext = LocalContext.current
        val localizedContext = remember(baseContext, languageTag, fontScale) {
            baseContext.localizedContext(languageTag, fontScale)
        }
        val baseDensity = LocalDensity.current
        val scaledDensity = remember(baseDensity.density, fontScale) {
            Density(density = baseDensity.density, fontScale = fontScale)
        }
        CompositionLocalProvider(
            LocalContext provides localizedContext,
            LocalDensity provides scaledDensity,
        ) {
            check(LocalDensity.current.fontScale == fontScale)
            content()
        }
    }

    private fun localizedContext(languageTag: String, fontScale: Float): Context {
        return ApplicationProvider
            .getApplicationContext<Context>()
            .localizedContext(languageTag, fontScale)
    }

    private fun Context.localizedContext(languageTag: String, fontScale: Float): Context {
        val locale = Locale.forLanguageTag(languageTag)
        val configuration = Configuration(resources.configuration)
        configuration.setLocale(locale)
        configuration.setLocales(LocaleList(locale))
        configuration.fontScale = fontScale
        return createConfigurationContext(configuration)
    }

    private enum class SurfaceCase {
        ScannerActive,
        ScannerInvalid,
        ScannerPermission,
        ScannerSettingsRecovery,
        DrawerEmpty,
        DrawerPopulated,
        DrawerSearchNoResults,
        ChatPopulated,
        ChatStreaming,
        SettingsPairing,
        SettingsData,
    }

    private companion object {
        val canonicalFontScales = listOf(1f, 1.5f, 2f)
        val supportedLanguageTags = listOf("en", "ko", "ja", "zh-CN", "fr")
        val fullCoverageLanguageTags = listOf("en", "ko")
        const val QUALIFICATION_ROOT_TEST_TAG = "android_core_surface_font_scale_qualification_root"
        const val CAMERA_PREVIEW_TEST_TAG = "android_core_surface_font_scale_camera_preview"
        const val SETTINGS_SCROLL_TEST_TAG = "android_core_surface_font_scale_settings_scroll"
    }
}
