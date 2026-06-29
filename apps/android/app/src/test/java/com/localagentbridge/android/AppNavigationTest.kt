package com.localagentbridge.android

import android.content.Intent
import android.net.Uri
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import com.localagentbridge.android.core.transport.RuntimeEndpointSource
import com.localagentbridge.android.runtime.RuntimeActiveRouteKind
import com.localagentbridge.android.runtime.RuntimeDiscoveredRuntime
import com.localagentbridge.android.runtime.RuntimeAppLanguage
import com.localagentbridge.android.runtime.RuntimeAppTheme
import com.localagentbridge.android.runtime.RuntimeChatMessage
import com.localagentbridge.android.runtime.RuntimeChatSession
import com.localagentbridge.android.runtime.RuntimeModel
import com.localagentbridge.android.runtime.RuntimePendingAttachment
import com.localagentbridge.android.runtime.RuntimeProviderStatus
import com.localagentbridge.android.runtime.RuntimeTrustedRuntime
import com.localagentbridge.android.runtime.RuntimeUiError
import com.localagentbridge.android.runtime.RuntimeUiState
import com.localagentbridge.android.ui.AetherLinkInteractionFeedback
import com.localagentbridge.android.ui.aetherLinkHapticFeedbackType
import com.localagentbridge.android.ui.appLanguagePreferenceOptionSelected
import com.localagentbridge.android.ui.appLanguagePreferenceOptions
import com.localagentbridge.android.ui.appThemePreferenceOptions
import com.localagentbridge.android.ui.assistantShowsTypingPlaceholder
import com.localagentbridge.android.ui.CHAT_COMPOSER_CONTAINER_ALPHA
import com.localagentbridge.android.ui.CHAT_COMPOSER_CONTAINER_CORNER_RADIUS_DP
import com.localagentbridge.android.ui.ChatEmptyPrimaryAction
import com.localagentbridge.android.ui.chatComposerCanEdit
import com.localagentbridge.android.ui.chatComposerCanSend
import com.localagentbridge.android.ui.chatComposerHasSendableContent
import com.localagentbridge.android.ui.chatComposerHasUnsupportedImageAttachment
import com.localagentbridge.android.ui.chatComposerInputContentDescriptionRes
import com.localagentbridge.android.ui.chatInputHintRes
import com.localagentbridge.android.ui.chatComposerShouldShowStatus
import com.localagentbridge.android.ui.chatComposerVisualPlaceholderRes
import com.localagentbridge.android.ui.chatEmptyPrimaryAction
import com.localagentbridge.android.ui.chatEmptyTextRes
import com.localagentbridge.android.ui.chatHistoryArchiveAllEnabled
import com.localagentbridge.android.ui.chatHistoryBulkActionsAvailable
import com.localagentbridge.android.ui.chatHistoryPermanentDeleteArchivedEnabled
import com.localagentbridge.android.ui.chatHistoryPermanentDeleteChatEnabled
import com.localagentbridge.android.ui.chatHistorySessionStatusRes
import com.localagentbridge.android.ui.connectRuntimeActionLabelRes
import com.localagentbridge.android.ui.connectionStatusHeroDetailRes
import com.localagentbridge.android.ui.connectionStatusHeroTitleRes
import com.localagentbridge.android.ui.chatEmptyStaticPromptRes
import com.localagentbridge.android.ui.discoveredRuntimeActionLabelRes
import com.localagentbridge.android.ui.discoveredRuntimeSelectable
import com.localagentbridge.android.ui.filterChatHistorySessions
import com.localagentbridge.android.ui.hasConnectableTrustedRuntimeRoute
import com.localagentbridge.android.ui.hasRelayRouteMaterial
import com.localagentbridge.android.ui.hasRelayRouteWithoutSecret
import com.localagentbridge.android.ui.hasUsableRelayRoute
import com.localagentbridge.android.ui.memoryActionsEnabled
import com.localagentbridge.android.ui.memoryEmptyStateTextRes
import com.localagentbridge.android.ui.memoryLockNoticeTextRes
import com.localagentbridge.android.ui.MessageContentPart
import com.localagentbridge.android.ui.newUserMessageAddedSince
import com.localagentbridge.android.ui.normalizedSuggestedQuestions
import com.localagentbridge.android.ui.parseMessageContent
import com.localagentbridge.android.ui.providerDiagnosticCode
import com.localagentbridge.android.ui.providerDiagnosticMessage
import com.localagentbridge.android.ui.providerDiagnosticsVisible
import com.localagentbridge.android.ui.REASONING_COLLAPSED_ALPHA
import com.localagentbridge.android.ui.REASONING_EXPANDED_ALPHA
import com.localagentbridge.android.ui.REASONING_PREVIEW_MAX_CHARS
import com.localagentbridge.android.ui.REASONING_PREVIEW_MAX_LINES
import com.localagentbridge.android.ui.reasoningDisplayPolicy
import com.localagentbridge.android.ui.reasoningNeedsExpansion
import com.localagentbridge.android.ui.reasoningPreview
import com.localagentbridge.android.ui.runtimeVisibleErrorDetail
import com.localagentbridge.android.ui.runtimeRouteNotice
import com.localagentbridge.android.ui.RouteNoticePrimaryAction
import com.localagentbridge.android.ui.RuntimeRouteNoticeTone
import com.localagentbridge.android.ui.routeAvailabilityCompactLabelRes
import com.localagentbridge.android.ui.routeNoticeActionLabelRes
import com.localagentbridge.android.ui.routeNoticePrimaryAction
import com.localagentbridge.android.ui.shouldAutoScrollChat
import com.localagentbridge.android.ui.shouldShowAssistantSuggestions
import com.localagentbridge.android.ui.shouldShowAssistantSuggestionsForMessage
import com.localagentbridge.android.ui.shouldShowChatBottomError
import com.localagentbridge.android.ui.shouldShowChatEmptyState
import com.localagentbridge.android.ui.shouldShowJumpToLatestChatButton
import com.localagentbridge.android.ui.shouldScanLatestQrFromEmptyChat
import com.localagentbridge.android.ui.shouldPerformSelectionChangeHaptic
import com.localagentbridge.android.ui.SUGGESTED_QUESTION_MAX_ITEMS
import com.localagentbridge.android.ui.settingsPrimaryConnectionSectionInitiallyExpanded
import com.localagentbridge.android.ui.settingsPrimaryConnectionSectionSubtitleRes
import com.localagentbridge.android.ui.settingsPrimaryConnectionSectionTitleRes
import com.localagentbridge.android.ui.settingsLowerPrioritySectionInitiallyExpanded
import com.localagentbridge.android.ui.settingsScreenShowsGenericHeader
import com.localagentbridge.android.ui.settingsScreenShowsTroubleshootingSection
import com.localagentbridge.android.ui.suggestedQuestionMaxLines
import com.localagentbridge.android.ui.usableManualPairingPayload
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.util.Calendar

@RunWith(RobolectricTestRunner::class)
class AppNavigationTest {
    @Test
    fun freshInstallStartsInSettingsForPairing() {
        val destination = resolveAppDestination(
            current = AppDestination.Chat,
            hasTrustedRuntime = false,
        )

        assertEquals(AppDestination.Settings, destination)
    }

    @Test
    fun trustedRuntimeLoadedKeepsChatAsPrimarySurface() {
        val destination = resolveAppDestination(
            current = AppDestination.Chat,
            hasTrustedRuntime = true,
        )

        assertEquals(AppDestination.Chat, destination)
    }

    @Test
    fun settingsRemainsStableDuringPairingManagement() {
        val unpairedDestination = resolveAppDestination(
            current = AppDestination.Settings,
            hasTrustedRuntime = false,
        )
        val trustedDestination = resolveAppDestination(
            current = AppDestination.Settings,
            hasTrustedRuntime = true,
        )

        assertEquals(AppDestination.Settings, unpairedDestination)
        assertEquals(AppDestination.Settings, trustedDestination)
    }

    @Test
    fun completedOnboardingReturnsToSettingsWhenRuntimeIsForgotten() {
        val destination = resolveAppDestination(
            current = AppDestination.Chat,
            hasTrustedRuntime = false,
        )

        assertEquals(AppDestination.Settings, destination)
    }

    @Test
    fun connectedPairingFlowReturnsToChat() {
        assertEquals(
            true,
            shouldReturnToChatAfterPairing(
                returnToChatAfterPairing = true,
                hasTrustedRuntime = true,
                isConnected = true,
                isConnecting = false,
                isPairingAwaitingRoute = false,
            ),
        )
        assertEquals(
            true,
            shouldLeavePairingSettingsAfterTrustedRuntimeReady(
                destination = AppDestination.Settings,
                hasTrustedRuntime = true,
                settingsOpenedForPairingOnboarding = true,
                isPairingAwaitingRoute = false,
            ),
        )
    }

    @Test
    fun newChatActionRequiresTrustedRuntimeAndIdleStream() {
        assertFalse(newChatActionEnabled(RuntimeUiState()))

        assertFalse(
            newChatActionEnabled(
                RuntimeUiState(
                    trustedRuntime = RuntimeTrustedRuntime(
                        deviceId = "runtime-1",
                        name = "AetherLink Runtime",
                    ),
                    isStreaming = true,
                ),
            ),
        )

        assertTrue(
            newChatActionEnabled(
                RuntimeUiState(
                    trustedRuntime = RuntimeTrustedRuntime(
                        deviceId = "runtime-1",
                        name = "AetherLink Runtime",
                    ),
                ),
            ),
        )
    }

    @Test
    fun pendingQrRouteKeepsPairingSettingsUntilRouteResolved() {
        assertEquals(
            false,
            shouldReturnToChatAfterPairing(
                returnToChatAfterPairing = true,
                hasTrustedRuntime = true,
                isConnected = false,
                isConnecting = false,
                isPairingAwaitingRoute = true,
            ),
        )
        assertEquals(
            false,
            shouldLeavePairingSettingsAfterTrustedRuntimeReady(
                destination = AppDestination.Settings,
                hasTrustedRuntime = true,
                settingsOpenedForPairingOnboarding = true,
                isPairingAwaitingRoute = true,
            ),
        )
    }

    @Test
    fun manualSettingsManagementDoesNotAutoJumpToChat() {
        assertEquals(
            false,
            shouldReturnToChatAfterPairing(
                returnToChatAfterPairing = false,
                hasTrustedRuntime = true,
                isConnected = true,
                isConnecting = false,
                isPairingAwaitingRoute = false,
            ),
        )
        assertEquals(
            false,
            shouldLeavePairingSettingsAfterTrustedRuntimeReady(
                destination = AppDestination.Settings,
                hasTrustedRuntime = true,
                settingsOpenedForPairingOnboarding = false,
                isPairingAwaitingRoute = false,
            ),
        )
    }

    @Test
    fun settingsQrRefreshForTrustedRuntimeStaysInSettings() {
        assertEquals(
            false,
            shouldTreatPairingQrAsOnboarding(
                destination = AppDestination.Settings,
                hasTrustedRuntime = true,
                isPairingAwaitingRoute = false,
            ),
        )
    }

    @Test
    fun firstPairingChatQrAndPendingRouteQrUseOnboardingFlow() {
        assertEquals(
            true,
            shouldTreatPairingQrAsOnboarding(
                destination = AppDestination.Settings,
                hasTrustedRuntime = false,
                isPairingAwaitingRoute = false,
            ),
        )
        assertEquals(
            true,
            shouldTreatPairingQrAsOnboarding(
                destination = AppDestination.Chat,
                hasTrustedRuntime = true,
                isPairingAwaitingRoute = false,
            ),
        )
        assertEquals(
            true,
            shouldTreatPairingQrAsOnboarding(
                destination = AppDestination.Settings,
                hasTrustedRuntime = true,
                isPairingAwaitingRoute = true,
            ),
        )
    }

    @Test
    fun settingsTitleShowsPairingWhenRuntimeIsNotTrusted() {
        assertEquals(
            R.string.pairing_title,
            appDestinationTitleRes(
                destination = AppDestination.Settings,
                hasTrustedRuntime = false,
                isPairingAwaitingRoute = false,
            ),
        )
    }

    @Test
    fun settingsTitleShowsPairingWhileRouteFromQrIsPending() {
        assertEquals(
            R.string.pairing_title,
            appDestinationTitleRes(
                destination = AppDestination.Settings,
                hasTrustedRuntime = true,
                isPairingAwaitingRoute = true,
            ),
        )
    }

    @Test
    fun settingsTitleRemainsSettingsForTrustedRuntimeManagement() {
        assertEquals(
            R.string.tab_settings,
            appDestinationTitleRes(
                destination = AppDestination.Settings,
                hasTrustedRuntime = true,
                isPairingAwaitingRoute = false,
            ),
        )
    }

    @Test
    fun unpairedSettingsScreenStartsWithPairingHierarchy() {
        val state = RuntimeUiState()

        assertEquals(false, settingsScreenShowsGenericHeader(state))
        assertEquals(R.string.pairing_title, settingsPrimaryConnectionSectionTitleRes(state))
        assertEquals(R.string.pairing_subtitle, settingsPrimaryConnectionSectionSubtitleRes(state))
        assertEquals(true, settingsPrimaryConnectionSectionInitiallyExpanded(state))
    }

    @Test
    fun pendingQrRouteSettingsScreenKeepsPairingHierarchy() {
        val state = RuntimeUiState(
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "runtime-1",
                name = "AetherLink Runtime",
                fingerprint = "fingerprint",
            ),
            isPairingAwaitingRoute = true,
        )

        assertEquals(false, settingsScreenShowsGenericHeader(state))
        assertEquals(R.string.pairing_title, settingsPrimaryConnectionSectionTitleRes(state))
        assertEquals(R.string.pairing_subtitle, settingsPrimaryConnectionSectionSubtitleRes(state))
        assertEquals(true, settingsPrimaryConnectionSectionInitiallyExpanded(state))
    }

    @Test
    fun pendingQrRouteHeroExplainsThatLatestQrNeedsConnectionDetails() {
        val state = RuntimeUiState(
            pendingPairingRuntimeName = "AetherLink Runtime",
            isPairingAwaitingRoute = true,
        )

        assertEquals(R.string.status_route_needed_title, connectionStatusHeroTitleRes(state))
        assertEquals(R.string.pending_pairing_route_detail, connectionStatusHeroDetailRes(state))
    }

    @Test
    fun trustedSettingsScreenKeepsGenericSettingsHeader() {
        val state = RuntimeUiState(
            isConnected = true,
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "runtime-1",
                name = "AetherLink Runtime",
                fingerprint = "fingerprint",
            ),
        )

        assertEquals(true, settingsScreenShowsGenericHeader(state))
        assertEquals(R.string.status_title, settingsPrimaryConnectionSectionTitleRes(state))
        assertEquals(R.string.status_subtitle, settingsPrimaryConnectionSectionSubtitleRes(state))
        assertEquals(false, settingsPrimaryConnectionSectionInitiallyExpanded(state))
    }

    @Test
    fun settingsTroubleshootingSectionStaysDebugOnly() {
        assertEquals(false, settingsScreenShowsTroubleshootingSection(showDeveloperDiagnostics = false))
        assertEquals(true, settingsScreenShowsTroubleshootingSection(showDeveloperDiagnostics = true))
    }

    @Test
    fun developerDiagnosticsRequireDebugBuildAndExplicitLaunchRequest() {
        assertEquals(false, shouldEnableDeveloperDiagnostics(isDebugBuild = false, requestedByLaunch = false))
        assertEquals(false, shouldEnableDeveloperDiagnostics(isDebugBuild = false, requestedByLaunch = true))
        assertEquals(false, shouldEnableDeveloperDiagnostics(isDebugBuild = true, requestedByLaunch = false))
        assertEquals(true, shouldEnableDeveloperDiagnostics(isDebugBuild = true, requestedByLaunch = true))
    }

    @Test
    fun settingsLowerPrioritySectionsStartCollapsed() {
        assertEquals(false, settingsLowerPrioritySectionInitiallyExpanded())
    }

    @Test
    fun settingsLanguageOptionsKeepCurrentLaunchLanguageSetAndOrder() {
        assertEquals(
            listOf(
                RuntimeAppLanguage.English to R.string.language_english,
                RuntimeAppLanguage.Korean to R.string.language_korean,
                RuntimeAppLanguage.Japanese to R.string.language_japanese,
                RuntimeAppLanguage.SimplifiedChinese to R.string.language_simplified_chinese,
                RuntimeAppLanguage.French to R.string.language_french,
            ),
            appLanguagePreferenceOptions(),
        )
    }

    @Test
    fun settingsLanguageSelectionNormalizesStoredAliases() {
        assertEquals(
            true,
            appLanguagePreferenceOptionSelected(
                selectedLanguageTag = "zh-Hans",
                language = RuntimeAppLanguage.SimplifiedChinese,
            ),
        )
        assertEquals(
            true,
            appLanguagePreferenceOptionSelected(
                selectedLanguageTag = " zh_rCN ",
                language = RuntimeAppLanguage.SimplifiedChinese,
            ),
        )
        assertEquals(
            false,
            appLanguagePreferenceOptionSelected(
                selectedLanguageTag = "zh-Hans",
                language = RuntimeAppLanguage.English,
            ),
        )
    }

    @Test
    fun androidSystemAppLanguageSyncNormalizesCurrentAndSelectedTags() {
        assertFalse(shouldSynchronizeAndroidSystemAppLanguage(null, "en"))
        assertFalse(shouldSynchronizeAndroidSystemAppLanguage("  ", "en"))
        assertTrue(shouldSynchronizeAndroidSystemAppLanguage(null, "ko"))
        assertTrue(shouldSynchronizeAndroidSystemAppLanguage("  ", "fr"))
        assertFalse(shouldSynchronizeAndroidSystemAppLanguage("en-US", "en"))
        assertFalse(shouldSynchronizeAndroidSystemAppLanguage("ko-KR", "ko"))
        assertFalse(shouldSynchronizeAndroidSystemAppLanguage("zh-Hans", "zh-CN"))
        assertTrue(shouldSynchronizeAndroidSystemAppLanguage("fr-FR", "ko"))
        assertTrue(shouldSynchronizeAndroidSystemAppLanguage("de-DE", "en"))
    }

    @Test
    fun settingsThemeOptionsKeepSystemLightDarkOrder() {
        assertEquals(
            listOf(
                RuntimeAppTheme.System to R.string.appearance_system,
                RuntimeAppTheme.Light to R.string.appearance_light,
                RuntimeAppTheme.Dark to R.string.appearance_dark,
            ),
            appThemePreferenceOptions(),
        )
    }

    @Test
    fun permanentNavigationRailUsesExpandedWidthOnly() {
        assertEquals(false, shouldUsePermanentNavigationRail(839))
        assertEquals(true, shouldUsePermanentNavigationRail(840))
        assertEquals(true, shouldUsePermanentNavigationRail(1200))
    }

    @Test
    fun aetherLinkHapticPolicyKeepsOrdinaryActionsLightweight() {
        assertEquals(
            HapticFeedbackType.TextHandleMove,
            aetherLinkHapticFeedbackType(AetherLinkInteractionFeedback.PrimaryAction),
        )
        assertEquals(
            HapticFeedbackType.TextHandleMove,
            aetherLinkHapticFeedbackType(AetherLinkInteractionFeedback.SelectionChange),
        )
        assertEquals(
            HapticFeedbackType.TextHandleMove,
            aetherLinkHapticFeedbackType(AetherLinkInteractionFeedback.Toggle),
        )
    }

    @Test
    fun aetherLinkHapticPolicyKeepsStrongActionsDistinct() {
        assertEquals(
            HapticFeedbackType.LongPress,
            aetherLinkHapticFeedbackType(AetherLinkInteractionFeedback.Destructive),
        )
        assertEquals(
            HapticFeedbackType.LongPress,
            aetherLinkHapticFeedbackType(AetherLinkInteractionFeedback.Clipboard),
        )
    }

    @Test
    fun selectionChangeHapticOnlyRunsWhenSelectionChanges() {
        assertEquals(true, shouldPerformSelectionChangeHaptic(selected = false))
        assertEquals(false, shouldPerformSelectionChangeHaptic(selected = true))
    }

    @Test
    fun runtimeVisibleErrorDetailKeepsOnlyUserInputAttachmentDetails() {
        assertEquals(
            "report.pdf",
            runtimeVisibleErrorDetail(
                RuntimeUiError(
                    code = "attachment_too_large",
                    detail = "  report.pdf  ",
                ),
            ),
        )
        assertNull(runtimeVisibleErrorDetail(RuntimeUiError(code = "send_failed", detail = "relay timed out")))
        assertNull(runtimeVisibleErrorDetail(RuntimeUiError(code = "pairing_relay_route_rejected", detail = "Relay host is not reachable for remote pairing")))
        assertNull(runtimeVisibleErrorDetail(RuntimeUiError(code = "invalid_pairing_qr")))
        assertNull(runtimeVisibleErrorDetail(RuntimeUiError(code = "invalid_pairing_qr", detail = "   ")))
    }

    @Test
    fun runtimeVisibleErrorDetailRedactsBackendEndpointDetails() {
        val unsafeDetails = listOf(
            "Ollama returned http://127.0.0.1:11434/api/tags",
            "Ollama returned http://192.168.1.23:11434/api/tags",
            "Provider failed at model-provider.example.test:1234/v1/models",
            "Provider failed at localhost:1234/v1",
            "LM Studio URL rejected by provider",
            "Runtime tried /api/chat directly",
        )

        unsafeDetails.forEach { detail ->
            assertNull(runtimeVisibleErrorDetail(RuntimeUiError(code = "backend_unavailable", detail = detail)))
        }
    }

    @Test
    fun runtimeVisibleErrorDetailRedactsRouteSecretDetails() {
        val unsafeDetails = listOf(
            "Route refresh failed route_token=route-secret-token",
            "Relay allocation returned relay_secret=relay-secret-value",
            "Pairing rejected pairing_secret=pairing-secret-value",
            "Relay URL rejected ?rt=compact-route-token&rs=compact-relay-secret",
            "{\"routeToken\":\"camel-route-token\",\"relaySecret\":\"camel-relay-secret\"}",
            "Relay alias returned remote_secret=remote-secret-value",
            "Route alias returned route_secret=route-secret-value",
            "Rendezvous alias returned rendezvous_secret=rendezvous-secret-value",
            "Relay identity leaked relay_id=relay-room-secret",
            "Route identity leaked route_id=route-room-secret",
            "Network identity leaked network_id=private-network-secret",
            "Relay nonce leaked relay_nonce=nonce-secret-value",
            "Compact relay metadata leaked ri=compact-route-id&rrn=compact-nonce",
        )

        unsafeDetails.forEach { detail ->
            assertNull(runtimeVisibleErrorDetail(RuntimeUiError(code = "remote_route_unreachable", detail = detail)))
        }
    }

    @Test
    fun providerDiagnosticMessageRedactsBackendEndpointDetails() {
        assertEquals(
            "Provider is reachable through AetherLink Runtime",
            providerDiagnosticMessage(
                RuntimeProviderStatus(
                    id = "ollama",
                    name = "Ollama",
                    available = true,
                    message = " Provider is reachable through AetherLink Runtime ",
                ),
            ),
        )

        val unsafeMessages = listOf(
            "Ollama returned http://127.0.0.1:11434/api/tags",
            "LM Studio failed at localhost:1234/v1/models",
            "Provider tried /api/chat directly",
        )

        unsafeMessages.forEach { message ->
            assertNull(
                providerDiagnosticMessage(
                    RuntimeProviderStatus(
                        id = "provider",
                        name = "Provider",
                        available = false,
                        message = message,
                    ),
                ),
            )
        }
    }

    @Test
    fun providerDiagnosticMessageRedactsRouteSecretDetails() {
        val unsafeMessages = listOf(
            "Route refresh failed route_token=route-secret-token",
            "Relay allocation returned relay_secret=relay-secret-value",
            "Pairing rejected pairing_secret=pairing-secret-value",
            "Relay URL rejected ?rt=compact-route-token&rs=compact-relay-secret",
            "{\"routeToken\":\"camel-route-token\",\"relaySecret\":\"camel-relay-secret\"}",
            "Relay alias returned remote_secret=remote-secret-value",
            "Route alias returned route_secret=route-secret-value",
            "Rendezvous alias returned rendezvous_secret=rendezvous-secret-value",
            "Relay identity leaked relay_id=relay-room-secret",
            "Route identity leaked route_id=route-room-secret",
            "Network identity leaked network_id=private-network-secret",
            "Relay nonce leaked relay_nonce=nonce-secret-value",
            "Compact relay metadata leaked ri=compact-route-id&rrn=compact-nonce",
        )

        unsafeMessages.forEach { message ->
            assertNull(
                providerDiagnosticMessage(
                    RuntimeProviderStatus(
                        id = "provider",
                        name = "Provider",
                        available = false,
                        message = message,
                    ),
                ),
            )
        }
    }

    @Test
    fun providerDiagnosticCodeRedactsUnsafeCodes() {
        assertEquals(
            "backend_unavailable",
            providerDiagnosticCode(
                RuntimeProviderStatus(
                    id = "provider",
                    name = "Provider",
                    available = false,
                    code = " backend_unavailable ",
                ),
            ),
        )

        val unsafeCodes = listOf(
            "http://127.0.0.1:11434/api/tags",
            "localhost:1234",
            "route_token=route-secret-token",
            "relay_secret=relay-secret-value",
            "remote_secret=remote-secret-value",
            "rendezvous_secret=rendezvous-secret-value",
            "pairing_secret=pairing-secret-value",
            "relay_id=relay-room-secret",
            "network_id=private-network-secret",
            "relay_nonce=nonce-secret-value",
            "rt=compact-route-token",
            "ri=compact-route-id",
            "rrn=compact-nonce",
            "backend unavailable",
        )

        unsafeCodes.forEach { code ->
            assertNull(
                providerDiagnosticCode(
                    RuntimeProviderStatus(
                        id = "provider",
                        name = "Provider",
                        available = false,
                        code = code,
                    ),
                ),
            )
        }
    }

    @Test
    fun providerDiagnosticsHiddenWhenAllDetailsAreRedacted() {
        assertFalse(
            providerDiagnosticsVisible(
                RuntimeProviderStatus(
                    id = "provider",
                    name = "Provider",
                    available = false,
                    message = "Relay allocation returned relay_secret=relay-secret-value",
                    code = "route_token=route-secret-token",
                ),
            ),
        )
        assertTrue(
            providerDiagnosticsVisible(
                RuntimeProviderStatus(
                    id = "provider",
                    name = "Provider",
                    available = false,
                    message = "Provider is reachable through AetherLink Runtime",
                ),
            ),
        )
    }

    @Test
    fun attachmentPickerUsesDocumentTypesWhenSelectedModelIsNotVisionCapable() {
        val state = RuntimeUiState(
            selectedModelId = "chat-1",
            models = listOf(
                RuntimeModel(
                    id = "chat-1",
                    name = "Local Chat",
                    modelKind = "chat",
                    capabilities = listOf("chat"),
                )
            ),
        )

        val mimeTypes = attachmentPickerMimeTypes(state).toList()

        assertEquals(false, "image/*" in mimeTypes)
        assertEquals(false, "application/*" in mimeTypes)
        assertEquals(true, "application/pdf" in mimeTypes)
        assertEquals(
            true,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in mimeTypes,
        )
        assertEquals(true, "application/vnd.ms-word.document.macroenabled.12" in mimeTypes)
        assertEquals(true, "application/vnd.hancom.hwpx" in mimeTypes)
        assertEquals(true, "application/hwp+zip" in mimeTypes)
        assertEquals(true, "application/x-hwpml" in mimeTypes)
        assertEquals(true, "application/vnd.hancom.hwpml" in mimeTypes)
        assertEquals(true, "application/vnd.apple.pages" in mimeTypes)
        assertEquals(true, "application/vnd.apple.numbers" in mimeTypes)
        assertEquals(true, "application/vnd.apple.keynote" in mimeTypes)
        assertEquals(true, "application/x-webarchive" in mimeTypes)
        assertEquals(true, "application/x-ndjson" in mimeTypes)
        assertEquals(true, "application/yaml" in mimeTypes)
        assertEquals(true, "application/toml" in mimeTypes)
        assertEquals(true, "text/html" in mimeTypes)
        assertEquals(true, "text/rtf" in mimeTypes)
        assertEquals(true, "application/xhtml+xml" in mimeTypes)
        assertEquals(true, "text/csv" in mimeTypes)
        assertEquals(true, "text/tab-separated-values" in mimeTypes)
        assertEquals(true, "text/markdown" in mimeTypes)
        assertEquals(true, "text/x-rst" in mimeTypes)
        assertEquals(true, "text/asciidoc" in mimeTypes)
        assertEquals(true, "text/*" in mimeTypes)
    }

    @Test
    fun attachmentPickerIncludesImageTypesWhenSelectedModelIsVisionCapable() {
        val state = RuntimeUiState(
            selectedModelId = "vision-1",
            models = listOf(
                RuntimeModel(
                    id = "vision-1",
                    name = "Local Vision",
                    modelKind = "chat",
                    capabilities = listOf("chat", "vision"),
                )
            ),
        )

        val mimeTypes = attachmentPickerMimeTypes(state).toList()

        assertEquals(true, "application/pdf" in mimeTypes)
        assertEquals(true, "image/*" in mimeTypes)
        assertEquals("image/*", mimeTypes.last())
    }

    @Test
    fun attachmentPickerCallbackAddsPickedUrisOnceAndIgnoresEmptySelections() {
        val pickedUris = listOf(
            Uri.parse("content://aetherlink/document/one"),
            Uri.parse("content://aetherlink/document/two"),
        )
        val addedBatches = mutableListOf<List<Uri>>()

        handlePickedAttachments(pickedUris) { uris ->
            addedBatches += uris
        }
        handlePickedAttachments(emptyList()) { uris ->
            addedBatches += uris
        }

        assertEquals(listOf(pickedUris), addedBatches)
    }

    @Test
    fun shareIntentTextBecomesChatDraftWithoutBackendAccess() {
        val draft = sharedChatDraftOrNull(
            action = Intent.ACTION_SEND,
            sharedText = "  Summarize this article  ",
            attachmentUris = emptyList(),
        )

        assertEquals("Summarize this article", draft?.text)
        assertEquals(emptyList<Uri>(), draft?.attachmentUris)
    }

    @Test
    fun shareIntentStreamsBecomeDistinctChatAttachments() {
        val sharedUri = Uri.parse("content://aetherlink/shared/one.pdf")
        val draft = sharedChatDraftOrNull(
            action = Intent.ACTION_SEND_MULTIPLE,
            sharedText = "",
            attachmentUris = listOf(sharedUri, sharedUri),
        )

        assertEquals("", draft?.text)
        assertEquals(listOf(sharedUri), draft?.attachmentUris)
    }

    @Test
    fun shareIntentStreamsKeepOnlyContentAttachmentUris() {
        val contentUri = Uri.parse("content://aetherlink/shared/one.pdf")
        val draft = sharedChatDraftOrNull(
            action = Intent.ACTION_SEND_MULTIPLE,
            sharedText = "  Summarize this  ",
            attachmentUris = listOf(
                contentUri,
                Uri.parse("file:///sdcard/Download/private.pdf"),
                Uri.parse("https://example.test/private.pdf"),
                Uri.parse("aetherlink://pair?pairing_code=123456"),
                contentUri,
            ),
        )

        assertEquals("Summarize this", draft?.text)
        assertEquals(listOf(contentUri), draft?.attachmentUris)
        assertNull(
            sharedChatDraftOrNull(
                action = Intent.ACTION_SEND_MULTIPLE,
                sharedText = "   ",
                attachmentUris = listOf(
                    Uri.parse("file:///sdcard/Download/private.pdf"),
                    Uri.parse("https://example.test/private.pdf"),
                    Uri.parse("aetherlink://pair?pairing_code=123456"),
                ),
            ),
        )
    }

    @Test
    fun shareIntentParserRejectsNonShareAndEmptyShareIntents() {
        assertNull(
            sharedChatDraftOrNull(
                action = Intent.ACTION_VIEW,
                sharedText = "Summarize this",
                attachmentUris = emptyList(),
            ),
        )
        assertNull(
            sharedChatDraftOrNull(
                action = Intent.ACTION_SEND,
                sharedText = "   ",
                attachmentUris = emptyList(),
            ),
        )
    }

    @Test
    fun sharedChatDraftComposerTextAppendsWithoutDroppingExistingDraft() {
        assertEquals(
            "Summarize this",
            sharedChatDraftComposerText(currentText = "", sharedText = "  Summarize this  "),
        )
        assertEquals(
            "Existing draft\n\nNew shared text",
            sharedChatDraftComposerText(
                currentText = "Existing draft   ",
                sharedText = " New shared text ",
            ),
        )
    }

    @Test
    fun sharedChatDraftConfirmationMessageMatchesImportedContentType() {
        val sharedUri = Uri.parse("content://aetherlink/shared/one.pdf")

        assertEquals(
            R.string.shared_draft_added_text_snackbar,
            sharedChatDraftConfirmationMessageRes(
                SharedChatDraft(text = "Summarize this", attachmentUris = emptyList()),
            ),
        )
        assertEquals(
            R.string.shared_draft_added_files_snackbar,
            sharedChatDraftConfirmationMessageRes(
                SharedChatDraft(text = "", attachmentUris = listOf(sharedUri)),
            ),
        )
        assertEquals(
            R.string.shared_draft_added_mixed_snackbar,
            sharedChatDraftConfirmationMessageRes(
                SharedChatDraft(text = "Summarize this", attachmentUris = listOf(sharedUri)),
            ),
        )
    }

    @Test
    fun sharedChatDraftConfirmationFeedbackUsesLightweightHaptic() {
        assertEquals(
            AetherLinkInteractionFeedback.PrimaryAction,
            sharedChatDraftConfirmationFeedback(),
        )
        assertEquals(
            HapticFeedbackType.TextHandleMove,
            aetherLinkHapticFeedbackType(sharedChatDraftConfirmationFeedback()),
        )
    }

    @Test
    fun chatComposerAllowsAttachmentOnlySendWhenConnectedModelIsUsable() {
        val state = RuntimeUiState(
            isConnected = true,
            trustedRuntime = RuntimeTrustedRuntime(deviceId = "runtime-1", name = "AetherLink Runtime"),
            selectedModelId = "chat-1",
            models = listOf(
                RuntimeModel(
                    id = "chat-1",
                    name = "Local Chat",
                    modelKind = "chat",
                    capabilities = listOf("chat"),
                    installed = true,
                )
            ),
            chatInput = "   ",
            pendingAttachments = listOf(documentAttachment()),
        )

        assertEquals(true, chatComposerHasSendableContent(state))
        assertEquals(false, chatComposerHasUnsupportedImageAttachment(state))
        assertEquals(true, chatComposerCanEdit(state))
        assertEquals(true, chatComposerCanSend(state))
    }

    @Test
    fun chatComposerEditingRequiresTrustedConnectedUsableModel() {
        val readyState = RuntimeUiState(
            isConnected = true,
            trustedRuntime = RuntimeTrustedRuntime(deviceId = "runtime-1", name = "AetherLink Runtime"),
            selectedModelId = "chat-1",
            models = listOf(
                RuntimeModel(
                    id = "chat-1",
                    name = "Local Chat",
                    modelKind = "chat",
                    capabilities = listOf("chat"),
                    installed = true,
                )
            ),
        )

        assertEquals(false, chatComposerCanEdit(RuntimeUiState()))
        assertEquals(false, chatComposerCanEdit(readyState.copy(trustedRuntime = null)))
        assertEquals(false, chatComposerCanEdit(readyState.copy(isConnected = false)))
        assertEquals(false, chatComposerCanEdit(readyState.copy(selectedModelId = null)))
        assertEquals(false, chatComposerCanEdit(readyState.copy(isStreaming = true)))
        assertEquals(
            false,
            chatComposerCanEdit(
                readyState.copy(
                    activeChatSessionId = "runtime-session",
                    loadingChatSessionId = "runtime-session",
                )
            )
        )
        assertEquals(true, chatComposerCanEdit(readyState))
    }

    @Test
    fun chatComposerStatusShowsReadinessHintsWhenInputIsLocked() {
        assertEquals(
            true,
            chatComposerShouldShowStatus(
                enabled = false,
                isStreaming = false,
                hint = "Select a model before sending.",
                hasWarning = false,
            ),
        )
        assertEquals(
            true,
            chatComposerShouldShowStatus(
                enabled = true,
                isStreaming = false,
                hint = "Choose a vision-capable model before sending an image.",
                hasWarning = true,
            ),
        )
        assertEquals(
            false,
            chatComposerShouldShowStatus(
                enabled = true,
                isStreaming = false,
                hint = "Ready to send.",
                hasWarning = false,
            ),
        )
        assertEquals(
            false,
            chatComposerShouldShowStatus(
                enabled = false,
                isStreaming = true,
                hint = "Wait for the current response or cancel it.",
                hasWarning = false,
            ),
        )
    }

    @Test
    fun chatComposerBlocksImageAttachmentUntilSelectedModelSupportsVision() {
        val textOnlyState = RuntimeUiState(
            isConnected = true,
            trustedRuntime = RuntimeTrustedRuntime(deviceId = "runtime-1", name = "AetherLink Runtime"),
            selectedModelId = "chat-1",
            models = listOf(
                RuntimeModel(
                    id = "chat-1",
                    name = "Local Chat",
                    modelKind = "chat",
                    capabilities = listOf("chat"),
                    installed = true,
                )
            ),
            chatInput = "Describe this",
            pendingAttachments = listOf(imageAttachment()),
        )
        val visionState = textOnlyState.copy(
            selectedModelId = "vision-1",
            models = listOf(
                RuntimeModel(
                    id = "vision-1",
                    name = "Local Vision",
                    modelKind = "chat",
                    capabilities = listOf("chat", "vision"),
                    installed = true,
                )
            ),
        )

        assertEquals(true, chatComposerHasUnsupportedImageAttachment(textOnlyState))
        assertEquals(false, chatComposerCanSend(textOnlyState))
        assertEquals(false, chatComposerHasUnsupportedImageAttachment(visionState))
        assertEquals(true, chatComposerCanSend(visionState))
    }

    @Test
    fun chatComposerRequiresInstalledChatModelForAttachmentSends() {
        val missingModelState = RuntimeUiState(
            isConnected = true,
            selectedModelId = "chat-1",
            models = emptyList(),
            pendingAttachments = listOf(documentAttachment()),
        )
        val uninstalledModelState = missingModelState.copy(
            models = listOf(
                RuntimeModel(
                    id = "chat-1",
                    name = "Local Chat",
                    modelKind = "chat",
                    capabilities = listOf("chat"),
                    installed = false,
                )
            ),
        )
        val noContentState = uninstalledModelState.copy(
            models = listOf(
                RuntimeModel(
                    id = "chat-1",
                    name = "Local Chat",
                    modelKind = "chat",
                    capabilities = listOf("chat"),
                    installed = true,
                )
            ),
            pendingAttachments = emptyList(),
            chatInput = "   ",
        )

        assertEquals(false, chatComposerCanSend(missingModelState))
        assertEquals(false, chatComposerCanSend(uninstalledModelState))
        assertEquals(false, chatComposerHasSendableContent(noContentState))
        assertEquals(false, chatComposerCanSend(noContentState))
    }

    @Test
    fun savedModelDisplayNameKeepsModelTagWhenNoProviderPrefixExists() {
        assertEquals("qwen3:8b", savedModelDisplayName("qwen3:8b"))
    }

    @Test
    fun savedModelDisplayNameRemovesKnownProviderPrefix() {
        assertEquals("qwen3:8b", savedModelDisplayName("ollama:qwen3:8b"))
        assertEquals("qwen2.5-vl-7b", savedModelDisplayName("lm_studio:qwen2.5-vl-7b"))
    }

    @Test
    fun chatModelPickerClosedLabelShowsSavedModelWhileModelListIsRestoring() {
        val state = RuntimeUiState(
            isLoadingModels = true,
            selectedModelId = "ollama:qwen3:8b",
            models = emptyList(),
        )

        assertEquals(
            "qwen3:8b",
            chatModelPickerClosedLabel(
                state = state,
                loadingModelsLabel = "Loading models",
                chooseModelLabel = "Choose model",
            ),
        )
    }

    @Test
    fun chatModelPickerClosedLabelHidesSavedModelWhenDisconnectedAndNotRestoring() {
        val state = RuntimeUiState(
            isConnected = false,
            isConnecting = false,
            isLoadingModels = false,
            selectedModelId = "ollama:dev-mock",
            models = emptyList(),
        )

        assertEquals(
            "Choose model",
            chatModelPickerClosedLabel(
                state = state,
                loadingModelsLabel = "Loading models",
                chooseModelLabel = "Choose model",
            ),
        )
        assertNull(chatModelPickerFallbackDisplayName(state))
    }

    @Test
    fun chatModelPickerClosedLabelUsesRuntimeModelNameWhenAvailable() {
        val state = RuntimeUiState(
            selectedModelId = "ollama:qwen3:8b",
            models = listOf(
                RuntimeModel(
                    id = "ollama:qwen3:8b",
                    name = "Qwen3 8B",
                    modelKind = "chat",
                    capabilities = listOf("chat"),
                    source = "local",
                )
            ),
        )

        assertEquals(
            "Qwen3 8B",
            chatModelPickerClosedLabel(
                state = state,
                loadingModelsLabel = "Loading models",
                chooseModelLabel = "Choose model",
            ),
        )
    }

    @Test
    fun chatModelPickerClosedLabelIgnoresProviderManagedChatModel() {
        val state = RuntimeUiState(
            selectedModelId = "ollama:qwen3:8b",
            models = listOf(
                RuntimeModel(
                    id = "ollama:qwen3:8b",
                    name = "Provider Managed Qwen",
                    modelKind = "chat",
                    capabilities = listOf("chat"),
                    source = "cloud",
                ),
            ),
        )

        assertEquals(
            "Choose model",
            chatModelPickerClosedLabel(
                state = state,
                loadingModelsLabel = "Loading models",
                chooseModelLabel = "Choose model",
            ),
        )
        assertEquals(null, chatModelPickerFallbackDisplayName(state))
        assertEquals(emptyList<RuntimeModel>(), chatModelMenuModels(state.models))
    }

    @Test
    fun chatModelMenuEnablesLocalChatModelsSoUninstalledModelsCanRequestInstall() {
        val installedModel = RuntimeModel(
            id = "chat-1",
            name = "Local Chat",
            modelKind = "chat",
            capabilities = listOf("chat"),
            installed = true,
            source = "local",
        )
        val notInstalledModel = installedModel.copy(
            id = "chat-2",
            installed = false,
        )
        val providerManagedModel = installedModel.copy(
            id = "chat-provider-managed",
            source = "cloud",
        )
        val unknownSourceModel = installedModel.copy(
            id = "chat-unknown-source",
            source = null,
        )
        val embeddingModel = installedModel.copy(
            id = "embedding-1",
            modelKind = "embedding",
            capabilities = listOf("embedding"),
            installed = true,
        )

        assertEquals(true, chatModelMenuItemEnabled(installedModel, installing = false))
        assertEquals(false, chatModelMenuItemEnabled(installedModel, installing = true))
        assertEquals(true, chatModelMenuItemEnabled(notInstalledModel, installing = false))
        assertEquals(false, chatModelMenuItemEnabled(notInstalledModel, installing = true))
        assertEquals(false, chatModelMenuItemEnabled(providerManagedModel, installing = false))
        assertEquals(false, chatModelMenuItemEnabled(unknownSourceModel, installing = false))
        assertEquals(false, chatModelMenuItemEnabled(embeddingModel, installing = false))
    }

    @Test
    fun chatModelMenuShowsLocalChatModelsAndPrioritizesRunningThenInstalled() {
        val unavailableChatModel = RuntimeModel(
            id = "chat-unavailable",
            name = "Unavailable Chat",
            modelKind = "chat",
            capabilities = listOf("chat"),
            installed = false,
            running = false,
            source = "local",
        )
        val providerManagedChatModel = RuntimeModel(
            id = "chat-provider-managed",
            name = "Provider Managed Chat",
            modelKind = "chat",
            capabilities = listOf("chat"),
            installed = true,
            running = true,
            source = "cloud",
        )
        val unknownSourceChatModel = providerManagedChatModel.copy(
            id = "chat-unknown-source",
            name = "Unknown Source Chat",
            source = null,
        )
        val embeddingModel = RuntimeModel(
            id = "embedding-1",
            name = "Embedding Model",
            modelKind = "embedding",
            capabilities = listOf("embedding"),
            installed = true,
            running = true,
        )
        val installedChatModel = RuntimeModel(
            id = "chat-installed",
            name = "Installed Chat",
            modelKind = "chat",
            capabilities = listOf("chat"),
            installed = true,
            running = false,
            source = "local",
        )
        val runningChatModel = RuntimeModel(
            id = "chat-running",
            name = "Running Chat",
            modelKind = "chat",
            capabilities = listOf("chat"),
            installed = true,
            running = true,
            source = "local",
        )

        assertEquals(
            listOf("chat-running", "chat-installed", "chat-unavailable"),
            chatModelMenuModels(
                listOf(
                    unavailableChatModel,
                    providerManagedChatModel,
                    unknownSourceChatModel,
                    embeddingModel,
                    installedChatModel,
                    runningChatModel,
                ),
            ).map { it.id },
        )
    }

    @Test
    fun chatModelMenuSearchAvailabilityUsesChatModelsOnly() {
        val embeddingModel = RuntimeModel(
            id = "embedding-only",
            name = "Embedding Only",
            modelKind = "embedding",
            capabilities = listOf("embedding"),
            installed = true,
            source = "local",
        )
        val unavailableChatModel = RuntimeModel(
            id = "chat-unavailable",
            name = "Unavailable Chat",
            modelKind = "chat",
            capabilities = listOf("chat"),
            installed = false,
            source = "local",
        )

        assertEquals(false, modelMenuSearchAvailable(listOf(embeddingModel)))
        assertEquals(true, modelMenuSearchAvailable(listOf(embeddingModel, unavailableChatModel)))
        assertEquals(true, modelMenuSearchAvailable(listOf(unavailableChatModel)))
    }

    @Test
    fun chatModelMenuPinsSelectedChatModelBeforeRunningModel() {
        val selectedInstalledModel = RuntimeModel(
            id = "chat-selected",
            name = "Selected Chat",
            modelKind = "chat",
            capabilities = listOf("chat"),
            installed = true,
            running = false,
            source = "local",
        )
        val runningModel = selectedInstalledModel.copy(
            id = "chat-running",
            name = "Running Chat",
            running = true,
        )

        assertEquals(
            listOf("chat-selected", "chat-running"),
            chatModelMenuModels(
                models = listOf(runningModel, selectedInstalledModel),
                selectedModelId = "chat-selected",
            ).map { it.id },
        )
    }

    @Test
    fun chatModelMenuSearchMatchesModelIdentityProviderAndSource() {
        val ollamaModel = RuntimeModel(
            id = "ollama:qwen3:8b",
            name = "Qwen3 8B",
            backend = "ollama",
            provider = "ollama",
            providerModelId = "qwen3:8b",
            source = "local",
            description = "General chat model",
        )
        val lmStudioModel = RuntimeModel(
            id = "chat-2",
            name = "DeepSeek Coder",
            backend = "openai_compatible",
            provider = "lm_studio",
            providerModelId = "deepseek-coder",
            source = "local",
            description = "Code assistant",
        )

        assertEquals(
            listOf("ollama:qwen3:8b"),
            chatModelMenuModels(listOf(ollamaModel, lmStudioModel), query = "qwen")
                .map { it.id },
        )
        assertEquals(
            listOf("ollama:qwen3:8b"),
            chatModelMenuModels(listOf(ollamaModel, lmStudioModel), query = "qwen3:8b")
                .map { it.id },
        )
        assertEquals(
            listOf("chat-2"),
            chatModelMenuModels(listOf(ollamaModel, lmStudioModel), query = "studio")
                .map { it.id },
        )
        assertEquals(
            listOf("chat-2"),
            chatModelMenuModels(listOf(ollamaModel, lmStudioModel), query = "deepseek-coder")
                .map { it.id },
        )
        assertEquals(
            listOf("chat-2", "ollama:qwen3:8b"),
            chatModelMenuModels(listOf(ollamaModel, lmStudioModel), query = "local")
                .map { it.id },
        )
    }

    @Test
    fun chatModelMenuKeepsSelectedModelVisibleDuringSearch() {
        val selectedModel = RuntimeModel(
            id = "ollama:qwen3:8b",
            name = "Qwen3 8B",
            backend = "ollama",
            provider = "ollama",
            providerModelId = "qwen3:8b",
            source = "local",
            installed = true,
            modelKind = "chat",
            capabilities = listOf("chat"),
        )
        val matchingModel = RuntimeModel(
            id = "lm_studio:deepseek-coder",
            name = "DeepSeek Coder",
            backend = "openai_compatible",
            provider = "lm_studio",
            providerModelId = "deepseek-coder",
            source = "local",
            installed = true,
            modelKind = "chat",
            capabilities = listOf("chat"),
        )

        assertEquals(
            listOf("ollama:qwen3:8b", "lm_studio:deepseek-coder"),
            chatModelMenuModels(
                models = listOf(matchingModel, selectedModel),
                query = "deepseek",
                selectedModelId = "ollama:qwen3:8b",
            ).map { it.id },
        )
    }

    @Test
    fun chatModelPickerClosedLabelIgnoresEmbeddingModelWithSavedChatModelId() {
        val state = RuntimeUiState(
            isLoadingModels = true,
            selectedModelId = "ollama:qwen3:8b",
            models = listOf(
                RuntimeModel(
                    id = "ollama:qwen3:8b",
                    name = "Qwen Embedding",
                    modelKind = "embedding",
                    capabilities = listOf("embedding"),
                ),
            ),
        )

        assertEquals(
            "qwen3:8b",
            chatModelPickerClosedLabel(
                state = state,
                loadingModelsLabel = "Loading models",
                chooseModelLabel = "Choose model",
            ),
        )
    }

    @Test
    fun pairingDeepLinkAcceptsAetherLinkPairUris() {
        val rawUri = "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
            "&runtime_device_id=runtime-1&runtime_key_fingerprint=fp-1" +
            "&relay_host=relay.example.test&relay_port=443&relay_id=relay-1" +
            "&relay_secret=secret-1&relay_expires_at=4102444800000&relay_nonce=nonce-route-1"

        assertEquals(
            rawUri,
            pairingUriStringOrNull(
                scheme = "aetherlink",
                host = "pair",
                path = "",
                rawUri = rawUri,
            ),
        )
    }

    @Test
    fun pairingDeepLinkAcceptsCompactRelayQrUris() {
        val rawUri = "aetherlink://pair?v=1&n=nonce-1&c=123456" +
            "&rid=runtime-1&rn=AetherLink%20Runtime&rf=fp-1&rk=runtime-public-key" +
            "&rt=route-1&rh=relay.example.test&rp=443&ri=relay-1&rs=secret-1" +
            "&rx=4102444800000&rrn=nonce-route-1&rsc=remote"

        assertEquals(
            rawUri,
            pairingUriStringOrNull(
                scheme = "aetherlink",
                host = "pair",
                path = "",
                rawUri = rawUri,
            ),
        )
    }

    @Test
    fun pairingQrRawValueAcceptsCompactRelayPayloadsFromScanner() {
        val rawUri = "aetherlink://pair?v=1&n=nonce-1&c=123456" +
            "&rid=runtime-1&rn=AetherLink%20Runtime&rf=fp-1&rk=runtime-public-key" +
            "&rt=route-1&rh=relay.example.test&rp=443&ri=relay-1&rs=secret-1" +
            "&rx=4102444800000&rrn=nonce-route-1&rsc=remote"
        val completeLegacyUri = "lab://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
            "&runtime_device_id=runtime-1&runtime_key_fingerprint=fp-1"

        assertEquals(true, "\n  $rawUri  ".isAetherLinkPairingQrValue())
        assertEquals(true, completeLegacyUri.isAetherLinkPairingQrValue())
        assertEquals(false, "lab://pair?pairing_code=123456".isAetherLinkPairingQrValue())
        assertEquals(false, "https://example.test/pair?code=123456".isAetherLinkPairingQrValue())
        assertEquals(false, "aetherlink://settings?pairing_code=123456".isAetherLinkPairingQrValue())
    }

    @Test
    fun pairingQrCandidateAllowsInvalidAetherLinkPairUrisToReachStructuredErrors() {
        val incompletePairQr = "lab://pair?pairing_code=123456"
        val unversionedPairQr = "lab://pair?pairing_nonce=nonce-1&pairing_code=123456" +
            "&runtime_device_id=runtime-1&runtime_key_fingerprint=fp-1"
        val localDiagnosticPairQr = "aetherlink://pair?version=1&pairing_nonce=nonce-1" +
            "&pairing_code=123456&runtime_device_id=runtime-1&runtime_key_fingerprint=fp-1" +
            "&host=192.168.1.20&port=43170"

        assertEquals(true, incompletePairQr.isAetherLinkPairingQrCandidateValue())
        assertEquals(false, incompletePairQr.isAetherLinkPairingQrValue())
        assertEquals(true, unversionedPairQr.isAetherLinkPairingQrCandidateValue())
        assertEquals(false, unversionedPairQr.isAetherLinkPairingQrValue())
        assertEquals(true, localDiagnosticPairQr.isAetherLinkPairingQrCandidateValue())
        assertEquals(false, localDiagnosticPairQr.isAetherLinkPairingQrValue())
        assertEquals(false, "https://example.test/pair?code=123456".isAetherLinkPairingQrCandidateValue())
        assertEquals(false, "aetherlink://settings?pairing_code=123456".isAetherLinkPairingQrCandidateValue())
        assertEquals(false, "aetherlink:/pair?pairing_code=123456".isAetherLinkPairingQrCandidateValue())
    }

    @Test
    fun pairingQrScannerClassifiesRawValuesBeforeConsumingCameraResult() {
        val validQr = "aetherlink://pair?v=1&n=nonce-1&c=123456" +
            "&rid=runtime-1&rn=AetherLink%20Runtime&rf=fp-1&rk=runtime-public-key" +
            "&rt=route-1&rh=relay.example.test&rp=443&ri=relay-1&rs=secret-1" +
            "&rx=4102444800000&rrn=nonce-route-1&rsc=remote"
        val invalidPairQr = "aetherlink://pair?pairing_code=123456"
        val expiredPairQr = "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
            "&runtime_device_id=runtime-1&runtime_key_fingerprint=fp-1" +
            "&relay_host=relay.example.test&relay_port=443&relay_id=relay-1" +
            "&relay_secret=secret-1&relay_expires_at=1000&relay_nonce=nonce-route-1"

        assertEquals(
            PairingQrRawValueScanResult.Valid,
            "\n  $validQr  ".aetherLinkPairingQrRawValueScanResult(),
        )
        assertEquals(
            PairingQrRawValueScanResult.InvalidPairingQr,
            invalidPairQr.aetherLinkPairingQrRawValueScanResult(),
        )
        assertEquals(
            PairingQrRawValueScanResult.InvalidPairingQr,
            expiredPairQr.aetherLinkPairingQrRawValueScanResult(),
        )
        assertEquals(
            PairingQrRawValueScanResult.UnsupportedQr,
            "https://example.test/pair?pairing_code=123456".aetherLinkPairingQrRawValueScanResult(),
        )
    }

    @Test
    fun pairingDeepLinkAcceptsPairActionCaseInsensitively() {
        val rawUri = "aetherlink://PAIR?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
            "&runtime_device_id=runtime-1&runtime_key_fingerprint=fp-1"

        assertEquals(
            rawUri,
            pairingUriStringOrNull(
                scheme = "aetherlink",
                host = "PAIR",
                path = "",
                rawUri = rawUri,
            ),
        )
    }

    @Test
    fun pairingDeepLinkRejectsPathOnlyPairingUris() {
        assertNull(
            pairingUriStringOrNull(
                scheme = "aetherlink",
                host = null,
                path = "/pair",
                rawUri = "aetherlink:/pair?pairing_code=123456",
            ),
        )
    }

    @Test
    fun pairingDeepLinkRejectsLegacyLabPairUris() {
        val rawUri = "lab://pair?pairing_code=123456"

        assertNull(
            pairingUriStringOrNull(
                scheme = "lab",
                host = "pair",
                path = "",
                rawUri = rawUri,
            ),
        )
    }

    @Test
    fun pairingDeepLinkRejectsUnsupportedSchemeOrAction() {
        assertNull(
            pairingUriStringOrNull(
                scheme = "https",
                host = "pair",
                path = "",
                rawUri = "https://pair?pairing_code=123456",
            ),
        )
        assertNull(
            pairingUriStringOrNull(
                scheme = "aetherlink",
                host = "settings",
                path = "",
                rawUri = "aetherlink://settings",
            ),
        )
    }

    @Test
    fun manualPairingPayloadTrimsCopiedQrText() {
        val rawUri = "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
            "&runtime_device_id=runtime-1&runtime_key_fingerprint=fp-1"

        assertEquals(rawUri, usableManualPairingPayload("\n  $rawUri  \n"))
    }

    @Test
    fun manualPairingPayloadLetsAetherLinkPairQrReachStructuredParserErrors() {
        val rawUri = "aetherlink://pair?pairing_code=123456"

        assertEquals(rawUri, usableManualPairingPayload("\n  $rawUri  \n"))
    }

    @Test
    fun manualPairingPayloadRejectsUnsupportedUrlsOrActions() {
        assertNull(usableManualPairingPayload("https://example.test/pair?pairing_code=123456"))
        assertNull(usableManualPairingPayload("aetherlink://settings?pairing_code=123456"))
    }

    @Test
    fun manualPairingPayloadRejectsBlankText() {
        assertNull(usableManualPairingPayload(" \n\t "))
    }

    @Test
    fun chatHistoryBulkArchiveRequiresEnabledActiveChats() {
        assertEquals(true, chatHistoryArchiveAllEnabled(isActionEnabled = true, activeSessionCount = 1))
        assertEquals(false, chatHistoryArchiveAllEnabled(isActionEnabled = false, activeSessionCount = 1))
        assertEquals(false, chatHistoryArchiveAllEnabled(isActionEnabled = true, activeSessionCount = 0))
    }

    @Test
    fun chatHistoryPermanentBulkDeleteRequiresEnabledArchivedChats() {
        assertEquals(
            true,
            chatHistoryPermanentDeleteArchivedEnabled(isActionEnabled = true, archivedSessionCount = 1),
        )
        assertEquals(
            false,
            chatHistoryPermanentDeleteArchivedEnabled(isActionEnabled = false, archivedSessionCount = 1),
        )
        assertEquals(
            false,
            chatHistoryPermanentDeleteArchivedEnabled(isActionEnabled = true, archivedSessionCount = 0),
        )
    }

    @Test
    fun chatHistoryPermanentDeleteRequiresEnabledArchivedChat() {
        assertEquals(true, chatHistoryPermanentDeleteChatEnabled(isActionEnabled = true, isArchived = true))
        assertEquals(false, chatHistoryPermanentDeleteChatEnabled(isActionEnabled = false, isArchived = true))
        assertEquals(false, chatHistoryPermanentDeleteChatEnabled(isActionEnabled = true, isArchived = false))
    }

    @Test
    fun chatHistoryBulkActionsOnlyAppearWhenChatsExist() {
        assertEquals(true, chatHistoryBulkActionsAvailable(activeSessionCount = 1, archivedSessionCount = 0))
        assertEquals(true, chatHistoryBulkActionsAvailable(activeSessionCount = 0, archivedSessionCount = 1))
        assertEquals(false, chatHistoryBulkActionsAvailable(activeSessionCount = 0, archivedSessionCount = 0))
    }

    @Test
    fun chatSessionDrawerGroupLabelUsesLocalCalendarDays() {
        val now = testLocalMillis(2026, Calendar.JUNE, 29, 12)

        assertEquals(
            R.string.chat_history_group_today,
            chatSessionDrawerGroupLabelRes(
                updatedAtMillis = testLocalMillis(2026, Calendar.JUNE, 29, 0),
                nowMillis = now,
            ),
        )
        assertEquals(
            R.string.chat_history_group_yesterday,
            chatSessionDrawerGroupLabelRes(
                updatedAtMillis = testLocalMillis(2026, Calendar.JUNE, 28, 23),
                nowMillis = now,
            ),
        )
        assertEquals(
            R.string.chat_history_group_previous_7_days,
            chatSessionDrawerGroupLabelRes(
                updatedAtMillis = testLocalMillis(2026, Calendar.JUNE, 22, 0),
                nowMillis = now,
            ),
        )
        assertEquals(
            R.string.chat_history_group_older,
            chatSessionDrawerGroupLabelRes(
                updatedAtMillis = testLocalMillis(2026, Calendar.JUNE, 21, 23),
                nowMillis = now,
            ),
        )
        assertEquals(
            R.string.chat_history_group_older,
            chatSessionDrawerGroupLabelRes(updatedAtMillis = 0L, nowMillis = now),
        )
    }

    @Test
    fun chatSessionDrawerGroupsUseStableBucketOrderAndPreserveOrderInsideBuckets() {
        val now = testLocalMillis(2026, Calendar.JUNE, 29, 12)
        val sessions = listOf(
            RuntimeChatSession(id = "today-1", title = "Today first", updatedAtMillis = testLocalMillis(2026, Calendar.JUNE, 29, 11), messageCount = 1),
            RuntimeChatSession(id = "previous", title = "Earlier this week", updatedAtMillis = testLocalMillis(2026, Calendar.JUNE, 26, 9), messageCount = 1),
            RuntimeChatSession(id = "yesterday", title = "Yesterday", updatedAtMillis = testLocalMillis(2026, Calendar.JUNE, 28, 10), messageCount = 1),
            RuntimeChatSession(id = "today-2", title = "Today second", updatedAtMillis = testLocalMillis(2026, Calendar.JUNE, 29, 8), messageCount = 1),
            RuntimeChatSession(id = "older", title = "Older", updatedAtMillis = testLocalMillis(2026, Calendar.JUNE, 1, 8), messageCount = 1),
        )

        val groups = chatSessionDrawerGroups(sessions = sessions, nowMillis = now)

        assertEquals(
            listOf(
                R.string.chat_history_group_today,
                R.string.chat_history_group_yesterday,
                R.string.chat_history_group_previous_7_days,
                R.string.chat_history_group_older,
            ),
            groups.map { it.labelRes },
        )
        assertEquals(listOf("today-1", "today-2"), groups[0].sessions.map { it.id })
        assertEquals(listOf("yesterday"), groups[1].sessions.map { it.id })
        assertEquals(listOf("previous"), groups[2].sessions.map { it.id })
        assertEquals(listOf("older"), groups[3].sessions.map { it.id })
    }

    @Test
    fun chatHistorySearchMatchesTitleModelAndRuntimeMetadata() {
        val sessions = listOf(
            RuntimeChatSession(
                id = "session-research",
                title = "Deep research notes",
                modelId = "ollama:qwen3:8b",
                updatedAtMillis = 3_000L,
                messageCount = 8,
                lastEvent = "chat.done",
                lastFinishReason = "stop",
            ),
            RuntimeChatSession(
                id = "session-error",
                title = "Trip plan",
                modelId = "lm_studio:local-model",
                updatedAtMillis = 2_000L,
                messageCount = 3,
                lastEvent = "chat.error",
                lastErrorCode = "backend_unavailable",
            ),
            RuntimeChatSession(
                id = "session-untitled",
                title = "New chat",
                modelId = null,
                updatedAtMillis = 1_000L,
                messageCount = 1,
            ),
        )

        assertEquals(
            listOf("session-research"),
            filterChatHistorySessions(
                sessions = sessions,
                query = "research qwen",
                untitledTitle = "Untitled chat",
            ).map { it.id },
        )
        assertEquals(
            listOf("session-error"),
            filterChatHistorySessions(
                sessions = sessions,
                query = "backend unavailable",
                untitledTitle = "Untitled chat",
            ).map { it.id },
        )
        assertEquals(
            listOf("session-untitled"),
            filterChatHistorySessions(
                sessions = sessions,
                query = "untitled",
                untitledTitle = "Untitled chat",
            ).map { it.id },
        )
        assertEquals(
            sessions,
            filterChatHistorySessions(
                sessions = sessions,
                query = " \n ",
                untitledTitle = "Untitled chat",
            ),
        )
    }

    @Test
    fun chatTopBarActiveTitleHidesOnlyUnprovenanceDefaultTitle() {
        fun stateFor(session: RuntimeChatSession): RuntimeUiState {
            return RuntimeUiState(
                activeChatSessionId = session.id,
                chatSessions = listOf(session),
            )
        }

        val defaultSession = RuntimeChatSession(
            id = "default",
            title = "New chat",
            updatedAtMillis = 1_000L,
            messageCount = 1,
        )
        val manualDefaultTitleSession = defaultSession.copy(
            id = "manual-default",
            titleManuallyEdited = true,
        )
        val generatedDefaultTitleSession = defaultSession.copy(
            id = "generated-default",
            titleGenerated = true,
        )
        val namedSession = defaultSession.copy(
            id = "named",
            title = "Runtime roadmap",
        )

        assertNull(chatTopBarActiveTitle(RuntimeUiState(), untitledTitle = "New Chat"))
        assertNull(chatTopBarActiveTitle(stateFor(defaultSession), untitledTitle = "New Chat"))
        assertEquals("New Chat", chatTopBarActiveTitle(stateFor(manualDefaultTitleSession), "New Chat"))
        assertEquals("New Chat", chatTopBarActiveTitle(stateFor(generatedDefaultTitleSession), "New Chat"))
        assertEquals("Runtime roadmap", chatTopBarActiveTitle(stateFor(namedSession), "New Chat"))
    }

    private fun testLocalMillis(
        year: Int,
        month: Int,
        dayOfMonth: Int,
        hourOfDay: Int,
    ): Long {
        return Calendar.getInstance().apply {
            clear()
            set(year, month, dayOfMonth, hourOfDay, 0, 0)
        }.timeInMillis
    }

    @Test
    fun chatHistorySearchMatchesResolvedModelDisplayName() {
        val model = RuntimeModel(
            id = "runtime-model-opaque-1",
            name = "Qwen3 8B",
        )
        val sessions = listOf(
            RuntimeChatSession(
                id = "session-model-display-name",
                title = "Runtime roadmap",
                modelId = model.id,
                updatedAtMillis = 2_000L,
                messageCount = 4,
            ),
            RuntimeChatSession(
                id = "session-other",
                title = "Trip plan",
                modelId = "runtime-model-opaque-2",
                updatedAtMillis = 1_000L,
                messageCount = 2,
            ),
        )

        assertEquals(
            listOf("session-model-display-name"),
            filterChatHistorySessions(
                sessions = sessions,
                query = "qwen",
                untitledTitle = "Untitled chat",
                models = listOf(model),
            ).map { it.id },
        )
    }

    @Test
    fun chatHistorySessionStatusSummarizesRuntimeProcessingMetadata() {
        fun session(
            lastEvent: String? = null,
            lastFinishReason: String? = null,
            lastErrorCode: String? = null,
        ) = RuntimeChatSession(
            id = "session",
            title = "Runtime session",
            updatedAtMillis = 1_000L,
            messageCount = 1,
            lastEvent = lastEvent,
            lastFinishReason = lastFinishReason,
            lastErrorCode = lastErrorCode,
        )

        assertEquals(
            R.string.chat_session_status_failed,
            chatHistorySessionStatusRes(
                session(
                    lastEvent = "chat.done",
                    lastFinishReason = "stop",
                    lastErrorCode = "backend_unavailable",
                ),
            ),
        )
        assertEquals(
            R.string.chat_session_status_cancelled,
            chatHistorySessionStatusRes(session(lastFinishReason = "cancelled")),
        )
        assertEquals(
            R.string.chat_session_status_failed,
            chatHistorySessionStatusRes(session(lastFinishReason = "failed")),
        )
        assertEquals(
            R.string.chat_session_status_completed,
            chatHistorySessionStatusRes(session(lastFinishReason = "stop")),
        )
        assertEquals(
            R.string.chat_session_status_in_progress,
            chatHistorySessionStatusRes(session(lastEvent = "chat.delta")),
        )
        assertEquals(
            R.string.chat_session_status_failed,
            chatHistorySessionStatusRes(session(lastEvent = "chat.error")),
        )
        assertNull(chatHistorySessionStatusRes(session()))
    }

    @Test
    fun discoveredRuntimeSelectionRequiresTrustedIdentityMatch() {
        val trusted = trustedRuntime()
        val matchingPeer = discoveredRuntime(routeToken = "route-token")
        val metadataLessPeer = discoveredRuntime()
        val differentPeer = discoveredRuntime(routeToken = "other-route")

        assertEquals(true, discoveredRuntimeSelectable(matchingPeer, trusted))
        assertEquals(false, discoveredRuntimeSelectable(metadataLessPeer, trusted))
        assertEquals(false, discoveredRuntimeSelectable(differentPeer, trusted))
        assertEquals(false, discoveredRuntimeSelectable(matchingPeer, trustedRuntime = null))
    }

    @Test
    fun discoveredRuntimeActionCopyStaysQrTrustFirst() {
        val trusted = trustedRuntime()
        val matchingPeer = discoveredRuntime(routeToken = "route-token")
        val metadataLessPeer = discoveredRuntime()
        val differentPeer = discoveredRuntime(routeToken = "other-route")

        assertEquals(R.string.use_trusted_connection, discoveredRuntimeActionLabelRes(matchingPeer, trusted))
        assertEquals(R.string.discovery_route_qr_required, discoveredRuntimeActionLabelRes(metadataLessPeer, trusted))
        assertEquals(R.string.discovery_route_not_trusted, discoveredRuntimeActionLabelRes(differentPeer, trusted))
        assertEquals(R.string.discovery_route_qr_required, discoveredRuntimeActionLabelRes(matchingPeer, trustedRuntime = null))
    }

    @Test
    fun privateOverlayRelayRouteWithScopeIsUsableInConnectionUi() {
        val trusted = trustedRuntime(
            relayHost = "100.64.1.10",
            relayScope = "private_overlay",
            relayExpiresAtEpochMillis = Long.MAX_VALUE,
            relayNonce = "nonce-1",
        )
        val state = RuntimeUiState(trustedRuntime = trusted)

        assertEquals(true, trusted.hasRelayRouteMaterial())
        assertEquals(true, trusted.hasUsableRelayRoute())
        assertEquals(R.string.connect_remote_route, connectRuntimeActionLabelRes(state))
    }

    @Test
    fun privateOverlayRelayLiteralWithoutScopeStaysUnusableInConnectionUi() {
        val trusted = trustedRuntime(
            relayHost = "100.64.1.10",
            relayScope = null,
            relayExpiresAtEpochMillis = Long.MAX_VALUE,
            relayNonce = "nonce-1",
        )
        val state = RuntimeUiState(trustedRuntime = trusted)

        assertEquals(false, trusted.hasRelayRouteMaterial())
        assertEquals(false, trusted.hasUsableRelayRoute())
        assertEquals(R.string.connect_runtime, connectRuntimeActionLabelRes(state))
    }

    @Test
    fun malformedRelayScopeStaysUnusableInConnectionUi() {
        val trusted = trustedRuntime(
            relayHost = "relay.example.test",
            relayScope = "public",
            relayExpiresAtEpochMillis = Long.MAX_VALUE,
            relayNonce = "nonce-1",
        )
        val state = RuntimeUiState(trustedRuntime = trusted)

        assertEquals(false, trusted.hasRelayRouteMaterial())
        assertEquals(false, trusted.hasUsableRelayRoute())
        assertEquals(R.string.connect_runtime, connectRuntimeActionLabelRes(state))
    }

    @Test
    fun privateOverlayRelayWithoutSecretUsesScopeAwareWarningPath() {
        val trusted = trustedRuntime(
            relayHost = "100.64.1.10",
            relaySecret = null,
            relayScope = "private_overlay",
            relayExpiresAtEpochMillis = Long.MAX_VALUE,
            relayNonce = "nonce-1",
        )

        assertEquals(true, trusted.hasRelayRouteWithoutSecret())
    }

    @Test
    fun routeNoticeActionScansQrWhenNoRuntimeIsTrusted() {
        val state = RuntimeUiState()

        assertEquals(RouteNoticePrimaryAction.ScanLatestQr, routeNoticePrimaryAction(state))
        assertEquals(R.string.route_notice_action_scan_qr, routeNoticeActionLabelRes(RouteNoticePrimaryAction.ScanLatestQr))
    }

    @Test
    fun routeNoticeActionScansQrWhenTrustedRuntimeNeedsDifferentNetworkRouteRefresh() {
        val missingRouteState = RuntimeUiState(
            trustedRuntime = trustedRuntime(
                relayHost = null,
                relayPort = null,
                relayId = null,
                relaySecret = null,
                relayExpiresAtEpochMillis = null,
                relayNonce = null,
            ),
        )
        val expiredRouteState = RuntimeUiState(
            trustedRuntime = trustedRuntime(
                relayExpiresAtEpochMillis = 1L,
                relayNonce = "nonce-1",
            ),
        )

        val missingRouteNotice = runtimeRouteNotice(missingRouteState, missingRouteState.trustedRuntime)
        val expiredRouteNotice = runtimeRouteNotice(expiredRouteState, expiredRouteState.trustedRuntime)

        assertEquals(RouteNoticePrimaryAction.ScanLatestQr, routeNoticePrimaryAction(missingRouteState))
        assertEquals(R.string.route_notice_remote_pending, missingRouteNotice?.detailRes)
        assertEquals(RouteNoticePrimaryAction.ScanLatestQr, missingRouteNotice?.action)
        assertEquals(RouteNoticePrimaryAction.ScanLatestQr, routeNoticePrimaryAction(expiredRouteState))
        assertEquals(R.string.route_notice_relay_expired, expiredRouteNotice?.detailRes)
        assertEquals(RuntimeRouteNoticeTone.Warning, expiredRouteNotice?.tone)
        assertEquals(RouteNoticePrimaryAction.ScanLatestQr, expiredRouteNotice?.action)
    }

    @Test
    fun routeNoticeActionConnectsWhenTrustedRuntimeHasUsableRelayRoute() {
        val state = RuntimeUiState(
            trustedRuntime = trustedRuntime(
                relayExpiresAtEpochMillis = Long.MAX_VALUE,
                relayNonce = "nonce-1",
            ),
        )

        val notice = runtimeRouteNotice(state, state.trustedRuntime)

        assertEquals(RouteNoticePrimaryAction.Connect, routeNoticePrimaryAction(state))
        assertEquals(R.string.connect_remote_route, routeNoticeActionLabelRes(RouteNoticePrimaryAction.Connect))
        assertEquals(R.string.route_notice_relay_encrypted, notice?.detailRes)
        assertEquals(RouteNoticePrimaryAction.Connect, notice?.action)
    }

    @Test
    fun routeNoticeActionIgnoresManualDiagnosticHostForNormalQrFirstRecovery() {
        val state = RuntimeUiState(
            trustedRuntime = trustedRuntime(
                relayHost = null,
                relayPort = null,
                relayId = null,
                relaySecret = null,
                relayExpiresAtEpochMillis = null,
                relayNonce = null,
            ),
            runtimeHost = "192.0.2.10",
            runtimePort = "43170",
            runtimeEndpointSource = RuntimeEndpointSource.Manual,
        )

        val notice = runtimeRouteNotice(state, state.trustedRuntime)

        assertEquals(false, hasConnectableTrustedRuntimeRoute(state))
        assertEquals(RouteNoticePrimaryAction.ScanLatestQr, routeNoticePrimaryAction(state))
        assertEquals(R.string.route_notice_remote_pending, notice?.detailRes)
        assertEquals(RouteNoticePrimaryAction.ScanLatestQr, notice?.action)
    }

    @Test
    fun routeNoticeActionStillConnectsForNonManualTrustedEndpointHints() {
        val state = RuntimeUiState(
            trustedRuntime = trustedRuntime(
                relayHost = null,
                relayPort = null,
                relayId = null,
                relaySecret = null,
                relayExpiresAtEpochMillis = null,
                relayNonce = null,
            ),
            runtimeHost = "192.0.2.20",
            runtimePort = "43170",
            runtimeEndpointSource = RuntimeEndpointSource.PairingQr,
        )

        val notice = runtimeRouteNotice(state, state.trustedRuntime)

        assertEquals(true, hasConnectableTrustedRuntimeRoute(state))
        assertEquals(RouteNoticePrimaryAction.Connect, routeNoticePrimaryAction(state))
        assertEquals(R.string.route_notice_development_route, notice?.detailRes)
        assertEquals(RouteNoticePrimaryAction.Connect, notice?.action)
    }

    @Test
    fun chatComposerHintRequestsLatestQrWhenTrustedRuntimeNeedsRouteRefresh() {
        val manualDiagnosticOnly = RuntimeUiState(
            trustedRuntime = trustedRuntime(
                relayHost = null,
                relayPort = null,
                relayId = null,
                relaySecret = null,
                relayExpiresAtEpochMillis = null,
                relayNonce = null,
            ),
            runtimeHost = "192.0.2.10",
            runtimePort = "43170",
            runtimeEndpointSource = RuntimeEndpointSource.Manual,
        )
        val expiredRelay = RuntimeUiState(
            trustedRuntime = trustedRuntime(
                relayExpiresAtEpochMillis = 1L,
                relayNonce = "nonce-1",
            ),
            error = RuntimeUiError(
                code = "remote_route_expired",
                diagnosticCode = "route_diagnostic_remote_route_expired",
            ),
        )

        assertEquals(R.string.chat_hint_scan_latest_qr, chatInputHintRes(manualDiagnosticOnly))
        assertEquals(R.string.chat_hint_scan_latest_qr, chatInputHintRes(expiredRelay))
    }

    @Test
    fun chatComposerHintStillRequestsConnectWhenTrustedRuntimeHasRouteCandidate() {
        val state = RuntimeUiState(
            trustedRuntime = trustedRuntime(
                relayExpiresAtEpochMillis = Long.MAX_VALUE,
                relayNonce = "nonce-1",
            ),
        )

        assertEquals(R.string.chat_hint_connect, chatInputHintRes(state))
    }

    @Test
    fun chatComposerHintExplainsActiveTranscriptLoadingLockout() {
        val state = RuntimeUiState(
            isConnected = true,
            trustedRuntime = trustedRuntime(
                relayExpiresAtEpochMillis = Long.MAX_VALUE,
                relayNonce = "nonce-1",
            ),
            activeChatSessionId = "runtime-session",
            loadingChatSessionId = "runtime-session",
            selectedModelId = "chat-1",
            models = listOf(
                RuntimeModel(
                    id = "chat-1",
                    name = "Local Chat",
                    modelKind = "chat",
                    capabilities = listOf("chat"),
                    installed = true,
                )
            ),
        )

        assertEquals(R.string.chat_hint_loading_chat, chatInputHintRes(state))
        assertEquals(false, chatComposerCanEdit(state))
        assertEquals(false, chatComposerCanSend(state.copy(chatInput = "Hello")))
    }

    @Test
    fun routeNoticeActionStaysInformationalWhenAlreadyConnected() {
        val state = RuntimeUiState(
            trustedRuntime = trustedRuntime(
                relayExpiresAtEpochMillis = Long.MAX_VALUE,
                relayNonce = "nonce-1",
            ),
            isConnected = true,
            activeRouteKind = RuntimeActiveRouteKind.Relay,
        )

        val notice = runtimeRouteNotice(state, state.trustedRuntime)

        assertNull(routeNoticePrimaryAction(state))
        assertEquals(R.string.route_notice_relay_active, notice?.detailRes)
        assertEquals(R.string.route_notice_status_connected, notice?.statusRes)
        assertEquals(RuntimeRouteNoticeTone.Ready, notice?.tone)
        assertNull(notice?.action)
    }

    @Test
    fun routeNoticeStatusLabelsDistinguishSavedRefreshDiagnosticsAndQrStates() {
        val savedConnection = RuntimeUiState(
            trustedRuntime = trustedRuntime(
                relayExpiresAtEpochMillis = Long.MAX_VALUE,
                relayNonce = "nonce-1",
            ),
        )
        val expiredConnection = RuntimeUiState(
            trustedRuntime = trustedRuntime(
                relayExpiresAtEpochMillis = 1L,
                relayNonce = "nonce-1",
            ),
        )
        val diagnosticRoute = RuntimeUiState(
            trustedRuntime = trustedRuntime(
                relayHost = null,
                relayPort = null,
                relayId = null,
                relaySecret = null,
            ),
            runtimeHost = "127.0.0.1",
            runtimeEndpointSource = RuntimeEndpointSource.UsbReverse,
        )
        val scanQr = RuntimeUiState(
            trustedRuntime = trustedRuntime(
                relayHost = null,
                relayPort = null,
                relayId = null,
                relaySecret = null,
            ),
        )

        assertEquals(
            R.string.route_notice_status_saved_connection,
            runtimeRouteNotice(savedConnection, savedConnection.trustedRuntime)?.statusRes,
        )
        assertEquals(
            R.string.route_notice_status_refresh_needed,
            runtimeRouteNotice(expiredConnection, expiredConnection.trustedRuntime)?.statusRes,
        )
        assertEquals(
            R.string.route_notice_status_diagnostics,
            runtimeRouteNotice(diagnosticRoute, diagnosticRoute.trustedRuntime)?.statusRes,
        )
        assertEquals(
            R.string.route_notice_status_scan_qr,
            runtimeRouteNotice(scanQr, scanQr.trustedRuntime)?.statusRes,
        )
    }

    @Test
    fun routeAvailabilityNoticeUsesScanQrForRemoteRouteFailureInsteadOfGenericConnect() {
        val state = RuntimeUiState(
            trustedRuntime = trustedRuntime(
                relayExpiresAtEpochMillis = Long.MAX_VALUE,
                relayNonce = "nonce-1",
            ),
            error = RuntimeUiError(
                code = "remote_route_unreachable",
                diagnosticCode = "route_diagnostic_relay_failed",
            ),
        )

        assertEquals(RouteNoticePrimaryAction.ScanLatestQr, routeNoticePrimaryAction(state))
        assertEquals(
            R.string.route_diagnostic_relay_failed,
            routeAvailabilityCompactLabelRes(requireNotNull(state.error)),
        )
    }

    @Test
    fun routeAvailabilityNoticeUsesDeviceReachabilityDiagnosticForRelayQrPreflightFailure() {
        val state = RuntimeUiState(
            trustedRuntime = trustedRuntime(
                relayExpiresAtEpochMillis = Long.MAX_VALUE,
                relayNonce = "nonce-1",
            ),
            error = RuntimeUiError(
                code = "remote_route_unreachable_from_device",
                diagnosticCode = "route_diagnostic_relay_unreachable_from_device",
            ),
        )

        assertEquals(RouteNoticePrimaryAction.ScanLatestQr, routeNoticePrimaryAction(state))
        assertEquals(
            R.string.route_diagnostic_relay_unreachable_from_device,
            routeAvailabilityCompactLabelRes(requireNotNull(state.error)),
        )
    }

    @Test
    fun routeAvailabilityNoticeExplainsIdentityOnlyQrNeedsConnectionRoute() {
        val state = RuntimeUiState(
            trustedRuntime = trustedRuntime(),
            error = RuntimeUiError(code = "pairing_endpoint_unavailable"),
        )

        assertEquals(RouteNoticePrimaryAction.ScanLatestQr, routeNoticePrimaryAction(state))
        assertEquals(
            R.string.route_notice_pairing_endpoint_unavailable,
            routeAvailabilityCompactLabelRes(requireNotNull(state.error)),
        )
    }

    @Test
    fun routeAvailabilityNoticeExplainsUnreachableRelayQrRoute() {
        val state = RuntimeUiState(
            trustedRuntime = trustedRuntime(),
            error = RuntimeUiError(
                code = "pairing_relay_route_rejected",
                diagnosticCode = "route_diagnostic_relay_qr_unreachable",
            ),
        )

        assertEquals(RouteNoticePrimaryAction.ScanLatestQr, routeNoticePrimaryAction(state))
        assertEquals(
            R.string.route_diagnostic_relay_qr_unreachable,
            routeAvailabilityCompactLabelRes(requireNotNull(state.error)),
        )
    }

    @Test
    fun memoryActionsRequireConnectedTrustedRuntime() {
        assertEquals(
            true,
            memoryActionsEnabled(
                RuntimeUiState(
                    isConnected = true,
                    trustedRuntime = trustedRuntime(),
                ),
            ),
        )
        assertEquals(
            false,
            memoryActionsEnabled(
                RuntimeUiState(
                    isConnected = false,
                    trustedRuntime = trustedRuntime(),
                ),
            ),
        )
        assertEquals(
            false,
            memoryActionsEnabled(
                RuntimeUiState(
                    isConnected = true,
                    isStreaming = true,
                    trustedRuntime = trustedRuntime(),
                ),
            ),
        )
        assertEquals(
            false,
            memoryActionsEnabled(
                RuntimeUiState(
                    isConnected = true,
                    trustedRuntime = null,
                ),
            ),
        )
        assertEquals(false, memoryActionsEnabled(RuntimeUiState()))
    }

    @Test
    fun memoryCopyDistinguishesDisconnectedCacheFromEmptyRuntimeMemory() {
        assertEquals(R.string.memory_empty, memoryEmptyStateTextRes(actionsEnabled = true))
        assertEquals(R.string.memory_empty_disconnected, memoryEmptyStateTextRes(actionsEnabled = false))
        assertEquals(R.string.memory_connect_to_load, memoryLockNoticeTextRes(hasEntries = false))
        assertEquals(R.string.memory_read_only_notice, memoryLockNoticeTextRes(hasEntries = true))
    }

    @Test
    fun reasoningDisplayPolicyKeepsCollapsedPreviewDimAndThreeLines() {
        val policy = reasoningDisplayPolicy(
            reasoning = "first step\nsecond step\nthird step\nfourth step",
            expanded = false,
        )

        assertEquals("first step\nsecond step\nthird step", policy.text)
        assertEquals(REASONING_COLLAPSED_ALPHA, policy.contentAlpha, 0.0f)
        assertEquals(REASONING_PREVIEW_MAX_LINES, policy.maxLines)
        assertEquals(true, policy.expandable)
    }

    @Test
    fun reasoningDisplayPolicyExpandsOnlyWhenExpandable() {
        val expanded = reasoningDisplayPolicy(
            reasoning = "first step\nsecond step\nthird step\nfourth step",
            expanded = true,
        )
        val short = reasoningDisplayPolicy(
            reasoning = "first step\nsecond step",
            expanded = true,
        )

        assertEquals("first step\nsecond step\nthird step\nfourth step", expanded.text)
        assertEquals(REASONING_EXPANDED_ALPHA, expanded.contentAlpha, 0.0f)
        assertEquals(Int.MAX_VALUE, expanded.maxLines)
        assertEquals(true, expanded.expandable)
        assertEquals("first step\nsecond step", short.text)
        assertEquals(REASONING_COLLAPSED_ALPHA, short.contentAlpha, 0.0f)
        assertEquals(REASONING_PREVIEW_MAX_LINES, short.maxLines)
        assertEquals(false, short.expandable)
    }

    @Test
    fun reasoningPreviewStaysShortAndDimUntilExpanded() {
        val longReasoning = "first step\nsecond step\nthird step\nfourth step"
        val collapsed = reasoningDisplayPolicy(
            reasoning = longReasoning,
            expanded = false,
        )
        val expanded = reasoningDisplayPolicy(
            reasoning = longReasoning,
            expanded = true,
        )

        assertEquals("first step\nsecond step\nthird step", collapsed.text)
        assertEquals(REASONING_COLLAPSED_ALPHA, collapsed.contentAlpha, 0.0f)
        assertEquals(REASONING_PREVIEW_MAX_LINES, collapsed.maxLines)
        assertEquals(longReasoning, expanded.text)
        assertEquals(REASONING_EXPANDED_ALPHA, expanded.contentAlpha, 0.0f)
        assertEquals(Int.MAX_VALUE, expanded.maxLines)
    }

    @Test
    fun typingPlaceholderHidesWhileReasoningIsOpen() {
        val reasoningMessage = RuntimeChatMessage(
            role = "assistant",
            content = "",
            reasoning = "Checking context",
            isReasoningOpen = true,
        )
        val blankMessage = reasoningMessage.copy(reasoning = "", isReasoningOpen = false)
        val answeredMessage = reasoningMessage.copy(content = "Answer", isReasoningOpen = false)

        assertEquals(false, assistantShowsTypingPlaceholder(reasoningMessage, isStreaming = true))
        assertEquals(true, assistantShowsTypingPlaceholder(blankMessage, isStreaming = true))
        assertEquals(false, assistantShowsTypingPlaceholder(answeredMessage, isStreaming = true))
        assertEquals(false, assistantShowsTypingPlaceholder(blankMessage, isStreaming = false))
    }

    @Test
    fun reasoningPreviewKeepsOnlyFirstThreeNonBlankLines() {
        val reasoning = """
            first step

            second step
            third step
            fourth step
        """.trimIndent()

        assertEquals(
            "first step\nsecond step\nthird step",
            reasoningPreview(reasoning),
        )
    }

    @Test
    fun reasoningPreviewFallsBackToCollapsedWhitespaceForSingleParagraph() {
        assertEquals(
            "first second third",
            reasoningPreview("  first   second   third  ", maxLines = 3),
        )
    }

    @Test
    fun reasoningPreviewReturnsBlankForWhitespaceOnlyReasoning() {
        assertEquals("", reasoningPreview(" \n\t\n "))
    }

    @Test
    fun reasoningExpansionAppearsOnlyWhenPreviewDiffersFromFullText() {
        assertEquals(false, reasoningNeedsExpansion("first step\nsecond step\nthird step"))
        assertEquals(true, reasoningNeedsExpansion("first step\nsecond step\nthird step\nfourth step"))
        assertEquals(false, reasoningNeedsExpansion("first step\n\nsecond step"))
        assertEquals(false, reasoningNeedsExpansion(" \n\t\n "))
    }

    @Test
    fun reasoningExpansionAppearsForLongSingleParagraph() {
        val reasoning = List(50) { "step" }.joinToString(separator = " ")

        assertEquals(true, reasoningNeedsExpansion(reasoning))
    }

    @Test
    fun reasoningPreviewCapsLongSingleParagraphBeforeExpansion() {
        val reasoning = List(80) { "planning" }.joinToString(separator = " ")
        val preview = reasoningPreview(reasoning)

        assertEquals(true, preview.endsWith("..."))
        assertEquals(true, preview.length <= REASONING_PREVIEW_MAX_CHARS + 3)
        assertEquals(false, preview.contains("\n"))
    }

    @Test
    fun reasoningExpansionAppearsForLongWrappedPreviewEvenWhenLineCountIsShort() {
        val reasoning = """
            ${List(28) { "planning" }.joinToString(separator = " ")}
            ${List(28) { "checking" }.joinToString(separator = " ")}
        """.trimIndent()

        assertEquals(true, reasoningNeedsExpansion(reasoning))
    }

    @Test
    fun suggestedQuestionChipsStayCompact() {
        assertEquals(2, suggestedQuestionMaxLines())
    }

    @Test
    fun messageContentParserSeparatesTextAndFencedCodeBlocks() {
        val parts = parseMessageContent(
            """
            Intro
            ```kotlin
            val answer = 42
            ```
            Outro
            """.trimIndent(),
        )

        assertEquals(
            listOf(
                MessageContentPart.Text("Intro"),
                MessageContentPart.Code(language = "kotlin", code = "val answer = 42"),
                MessageContentPart.Text("Outro"),
            ),
            parts,
        )
    }

    @Test
    fun messageContentParserKeepsUnclosedFenceAsCodeBlock() {
        val parts = parseMessageContent(
            """
            Intro
            ```sql
            select 1
            """.trimIndent(),
        )

        assertEquals(
            listOf(
                MessageContentPart.Text("Intro"),
                MessageContentPart.Code(language = "sql", code = "select 1"),
            ),
            parts,
        )
    }

    @Test
    fun messageContentParserTreatsFenceWithoutNewlineAsPlainText() {
        assertEquals(
            listOf(MessageContentPart.Text("```kotlin")),
            parseMessageContent("```kotlin"),
        )
    }

    @Test
    fun chatComposerKeepsAccessibilityLabelWithoutVisualPlaceholder() {
        assertEquals(R.string.message, chatComposerInputContentDescriptionRes())
        assertNull(chatComposerVisualPlaceholderRes())
        assertEquals(28, CHAT_COMPOSER_CONTAINER_CORNER_RADIUS_DP)
        assertEquals(0.98f, CHAT_COMPOSER_CONTAINER_ALPHA, 0.0f)
    }

    @Test
    fun emptyChatKeepsStaticExamplePromptsOutOfCenterState() {
        assertNull(chatEmptyStaticPromptRes())
    }

    @Test
    fun emptyChatPrefersQrRefreshWhenSavedRemoteRouteFailed() {
        val state = RuntimeUiState(
            isConnected = false,
            trustedRuntime = trustedRuntime(),
            error = RuntimeUiError(
                code = "remote_route_unreachable",
                diagnosticCode = "route_diagnostic_relay_failed",
            ),
        )

        assertEquals(true, shouldScanLatestQrFromEmptyChat(state))
        assertEquals(false, shouldShowChatBottomError(state))
        assertEquals(
            R.string.empty_chat_relay_route_unreachable,
            chatEmptyTextRes(state, preferQrRouteRefresh = true),
        )
    }

    @Test
    fun emptyChatPrefersQrRefreshWhenDeviceCannotReachRelayQrRoute() {
        val state = RuntimeUiState(
            isConnected = false,
            trustedRuntime = trustedRuntime(),
            error = RuntimeUiError(
                code = "remote_route_unreachable_from_device",
                diagnosticCode = "route_diagnostic_relay_unreachable_from_device",
            ),
        )

        assertEquals(true, shouldScanLatestQrFromEmptyChat(state))
        assertEquals(false, shouldShowChatBottomError(state))
        assertEquals(
            R.string.route_diagnostic_relay_unreachable_from_device,
            chatEmptyTextRes(state, preferQrRouteRefresh = true),
        )
    }

    @Test
    fun emptyChatPrefersQrRefreshForEndpointUnavailable() {
        val state = RuntimeUiState(
            isConnected = false,
            trustedRuntime = trustedRuntime(),
            error = RuntimeUiError(code = "pairing_endpoint_unavailable"),
        )

        assertEquals(true, shouldScanLatestQrFromEmptyChat(state))
        assertEquals(
            R.string.route_notice_pairing_endpoint_unavailable,
            chatEmptyTextRes(state, preferQrRouteRefresh = true),
        )
    }

    @Test
    fun emptyChatPrefersQrRefreshForRejectedDirectQrRoute() {
        val state = RuntimeUiState(
            isConnected = false,
            trustedRuntime = trustedRuntime(),
            error = RuntimeUiError(
                code = "pairing_direct_route_rejected",
                diagnosticCode = "route_diagnostic_direct_qr_rejected",
            ),
        )

        assertEquals(true, shouldScanLatestQrFromEmptyChat(state))
        assertEquals(false, shouldShowChatBottomError(state))
        assertEquals(
            R.string.route_diagnostic_direct_qr_rejected,
            chatEmptyTextRes(state, preferQrRouteRefresh = true),
        )
    }

    @Test
    fun emptyChatPrefersQrRefreshForUnreachableRelayQrRoute() {
        val state = RuntimeUiState(
            isConnected = false,
            trustedRuntime = trustedRuntime(),
            error = RuntimeUiError(
                code = "pairing_relay_route_rejected",
                diagnosticCode = "route_diagnostic_relay_qr_unreachable",
            ),
        )

        assertEquals(true, shouldScanLatestQrFromEmptyChat(state))
        assertEquals(false, shouldShowChatBottomError(state))
        assertEquals(
            R.string.empty_chat_relay_qr_unreachable,
            chatEmptyTextRes(state, preferQrRouteRefresh = true),
        )
    }

    @Test
    fun emptyChatPrefersQrRefreshForRelayAuthenticationFailure() {
        val state = RuntimeUiState(
            isConnected = false,
            trustedRuntime = trustedRuntime(),
            error = RuntimeUiError(
                code = "remote_route_auth_failed",
                diagnosticCode = "route_diagnostic_relay_auth_failed",
            ),
        )

        assertEquals(true, shouldScanLatestQrFromEmptyChat(state))
        assertEquals(false, shouldShowChatBottomError(state))
        assertEquals(
            R.string.route_diagnostic_relay_auth_failed,
            chatEmptyTextRes(state, preferQrRouteRefresh = true),
        )
    }

    @Test
    fun emptyChatPrefersQrRefreshForExpiredRemoteRoute() {
        val state = RuntimeUiState(
            isConnected = false,
            trustedRuntime = trustedRuntime(),
            error = RuntimeUiError(
                code = "remote_route_expired",
                diagnosticCode = "route_diagnostic_remote_route_expired",
            ),
        )

        assertEquals(true, shouldScanLatestQrFromEmptyChat(state))
        assertEquals(false, shouldShowChatBottomError(state))
        assertEquals(
            R.string.route_diagnostic_remote_route_expired,
            chatEmptyTextRes(state, preferQrRouteRefresh = true),
        )
    }

    @Test
    fun emptyChatPrefersQrRefreshWhenRuntimeRequiresPairingAgain() {
        listOf("pairing_required", "authentication_required").forEach { code ->
            val state = RuntimeUiState(
                isConnected = false,
                trustedRuntime = trustedRuntime(),
                error = RuntimeUiError(code = code),
            )

            assertEquals(true, shouldScanLatestQrFromEmptyChat(state))
            assertEquals(ChatEmptyPrimaryAction.ScanQr, chatEmptyPrimaryAction(state))
            assertEquals(false, shouldShowChatBottomError(state))
        }
    }

    @Test
    fun emptyChatPrefersQrRefreshForDiagnosticOnlyRouteFailure() {
        val state = RuntimeUiState(
            isConnected = false,
            trustedRuntime = trustedRuntime(),
            error = RuntimeUiError(
                code = "connection_failed",
                diagnosticCode = "route_diagnostic_remote_pending",
            ),
        )

        assertEquals(true, shouldScanLatestQrFromEmptyChat(state))
    }

    @Test
    fun emptyChatDoesNotPreferQrRefreshWhenAlreadyConnected() {
        val state = RuntimeUiState(
            isConnected = true,
            trustedRuntime = trustedRuntime(),
            error = RuntimeUiError(
                code = "remote_route_unreachable",
                diagnosticCode = "route_diagnostic_relay_failed",
            ),
        )

        assertEquals(false, shouldScanLatestQrFromEmptyChat(state))
        assertEquals(true, shouldShowChatBottomError(state))
    }

    @Test
    fun emptyChatDoesNotPreferQrRefreshWithoutTrustedRuntime() {
        val state = RuntimeUiState(
            isConnected = false,
            trustedRuntime = null,
            error = RuntimeUiError(
                code = "remote_route_unreachable",
                diagnosticCode = "route_diagnostic_relay_failed",
            ),
        )

        assertEquals(false, shouldScanLatestQrFromEmptyChat(state))
        assertEquals(true, shouldShowChatBottomError(state))
    }

    @Test
    fun emptyChatKeepsConnectActionWithoutRouteRefreshError() {
        val state = RuntimeUiState(
            isConnected = false,
            trustedRuntime = trustedRuntime(
                relayExpiresAtEpochMillis = Long.MAX_VALUE,
                relayNonce = "nonce-1",
            ),
            error = null,
        )

        assertEquals(false, shouldScanLatestQrFromEmptyChat(state))
        assertEquals(true, shouldShowChatEmptyState(state))
        assertEquals(ChatEmptyPrimaryAction.Connect, chatEmptyPrimaryAction(state))
    }

    @Test
    fun emptyChatPrefersLatestQrWhenTrustedRuntimeHasNoConnectableRoute() {
        val state = RuntimeUiState(
            isConnected = false,
            trustedRuntime = trustedRuntime(
                relayHost = null,
                relayPort = null,
                relayId = null,
                relaySecret = null,
            ),
            error = null,
        )

        assertEquals(false, hasConnectableTrustedRuntimeRoute(state))
        assertEquals(true, shouldScanLatestQrFromEmptyChat(state))
        assertEquals(ChatEmptyPrimaryAction.ScanQr, chatEmptyPrimaryAction(state))
        assertEquals(R.string.chat_hint_scan_latest_qr, chatInputHintRes(state))
    }

    @Test
    fun emptyChatKeepsConnectActionWhenTrustedRuntimeHasConnectableRoute() {
        val state = RuntimeUiState(
            isConnected = false,
            trustedRuntime = trustedRuntime(
                relayExpiresAtEpochMillis = Long.MAX_VALUE,
                relayNonce = "nonce-1",
            ),
            error = null,
        )

        assertEquals(true, hasConnectableTrustedRuntimeRoute(state))
        assertEquals(false, shouldScanLatestQrFromEmptyChat(state))
        assertEquals(ChatEmptyPrimaryAction.Connect, chatEmptyPrimaryAction(state))
        assertEquals(R.string.chat_hint_connect, chatInputHintRes(state))
    }

    @Test
    fun emptyChatKeepsQrActionWhenNoRuntimeIsTrusted() {
        val state = RuntimeUiState(
            isConnected = false,
            trustedRuntime = null,
            error = null,
        )

        assertEquals(true, shouldShowChatEmptyState(state))
        assertEquals(ChatEmptyPrimaryAction.ScanQr, chatEmptyPrimaryAction(state))
    }

    @Test
    fun emptyChatUsesQrActionForRouteRefresh() {
        val state = RuntimeUiState(
            isConnected = false,
            trustedRuntime = trustedRuntime(),
            error = RuntimeUiError(code = "remote_route_unreachable"),
        )

        assertEquals(ChatEmptyPrimaryAction.ScanQr, chatEmptyPrimaryAction(state))
    }

    @Test
    fun emptyChatPrimaryActionHidesWhenChatHasContent() {
        val state = RuntimeUiState(
            isConnected = false,
            trustedRuntime = trustedRuntime(),
            messages = listOf(RuntimeChatMessage(role = "user", content = "Hello")),
        )

        assertNull(chatEmptyPrimaryAction(state))
    }

    @Test
    fun emptyChatHidesStaticPromptWhenReadyToType() {
        val state = RuntimeUiState(
            isConnected = true,
            selectedModelId = "chat-model",
            models = listOf(RuntimeModel(id = "chat-model", name = "Chat Model")),
        )

        assertEquals(false, shouldShowChatEmptyState(state))
        assertNull(chatEmptyPrimaryAction(state))
    }

    @Test
    fun emptyChatShowsModelPickerHintWhenConnectedWithoutSelectedModel() {
        val state = RuntimeUiState(
            isConnected = true,
            selectedModelId = null,
            models = listOf(RuntimeModel(id = "chat-model", name = "Chat Model")),
        )

        assertEquals(true, shouldShowChatEmptyState(state))
        assertNull(chatEmptyPrimaryAction(state))
    }

    @Test
    fun emptyChatShowsModelPickerHintWhenSelectedModelIsUnavailable() {
        val missingState = RuntimeUiState(
            isConnected = true,
            selectedModelId = "missing-model",
            models = listOf(RuntimeModel(id = "chat-model", name = "Chat Model")),
        )
        val uninstalledState = RuntimeUiState(
            isConnected = true,
            selectedModelId = "chat-model",
            models = listOf(
                RuntimeModel(id = "chat-model", name = "Chat Model", installed = false),
            ),
        )
        val embeddingState = RuntimeUiState(
            isConnected = true,
            selectedModelId = "embed-model",
            models = listOf(
                RuntimeModel(id = "embed-model", name = "Embedding Model", modelKind = "embedding"),
            ),
        )

        assertEquals(true, shouldShowChatEmptyState(missingState))
        assertEquals(true, shouldShowChatEmptyState(uninstalledState))
        assertEquals(true, shouldShowChatEmptyState(embeddingState))
    }

    @Test
    fun chatAutoScrollFollowsStreamingWhenAlreadyNearLatestMessage() {
        assertEquals(
            true,
            shouldAutoScrollChat(
                lastVisibleItemIndex = 8,
                totalItemsCount = 10,
                messageCountChanged = false,
            ),
        )
        assertEquals(
            true,
            shouldAutoScrollChat(
                lastVisibleItemIndex = 9,
                totalItemsCount = 10,
                messageCountChanged = false,
            ),
        )
    }

    @Test
    fun chatAutoScrollDoesNotPullUserFromEarlierMessagesForStreamingDeltas() {
        assertEquals(
            false,
            shouldAutoScrollChat(
                lastVisibleItemIndex = 5,
                totalItemsCount = 10,
                messageCountChanged = false,
            ),
        )
    }

    @Test
    fun chatAutoScrollKeepsInitialAndNewMessageJumpBehavior() {
        assertEquals(
            true,
            shouldAutoScrollChat(
                lastVisibleItemIndex = null,
                totalItemsCount = 10,
                messageCountChanged = false,
            ),
        )
        assertEquals(
            true,
            shouldAutoScrollChat(
                lastVisibleItemIndex = 2,
                totalItemsCount = 10,
                messageCountChanged = true,
                newUserMessageAdded = true,
            ),
        )
        assertEquals(
            false,
            shouldAutoScrollChat(
                lastVisibleItemIndex = null,
                totalItemsCount = 0,
                messageCountChanged = false,
            ),
        )
    }

    @Test
    fun chatAutoScrollDoesNotPullUserFromEarlierMessagesForAssistantOnlyAppends() {
        assertEquals(
            false,
            shouldAutoScrollChat(
                lastVisibleItemIndex = 2,
                totalItemsCount = 10,
                messageCountChanged = true,
                newUserMessageAdded = false,
            ),
        )
    }

    @Test
    fun chatAutoScrollDetectsUserSendBurstOnlyWhileStreaming() {
        val messages = listOf(
            RuntimeChatMessage(role = "user", content = "Earlier question"),
            RuntimeChatMessage(role = "assistant", content = "Earlier answer"),
            RuntimeChatMessage(role = "user", content = "New question"),
            RuntimeChatMessage(role = "assistant", content = ""),
        )

        assertEquals(
            true,
            newUserMessageAddedSince(
                previousMessageCount = 2,
                messages = messages,
                isStreaming = true,
            ),
        )
        assertEquals(
            false,
            newUserMessageAddedSince(
                previousMessageCount = 2,
                messages = messages,
                isStreaming = false,
            ),
        )
        assertEquals(
            false,
            newUserMessageAddedSince(
                previousMessageCount = 4,
                messages = messages,
                isStreaming = true,
            ),
        )
    }

    @Test
    fun jumpToLatestChatButtonShowsOnlyWhenScrolledAwayFromLatestMessage() {
        assertEquals(
            true,
            shouldShowJumpToLatestChatButton(
                lastVisibleItemIndex = 5,
                totalItemsCount = 10,
            ),
        )
        assertEquals(
            false,
            shouldShowJumpToLatestChatButton(
                lastVisibleItemIndex = 8,
                totalItemsCount = 10,
            ),
        )
        assertEquals(
            false,
            shouldShowJumpToLatestChatButton(
                lastVisibleItemIndex = 9,
                totalItemsCount = 10,
            ),
        )
        assertEquals(
            false,
            shouldShowJumpToLatestChatButton(
                lastVisibleItemIndex = null,
                totalItemsCount = 10,
            ),
        )
        assertEquals(
            false,
            shouldShowJumpToLatestChatButton(
                lastVisibleItemIndex = null,
                totalItemsCount = 0,
            ),
        )
    }

    @Test
    fun assistantSuggestionsShowWhileGeneratingBeforeRowsArrive() {
        assertEquals(
            true,
            shouldShowAssistantSuggestions(
                isLatestAssistant = true,
                hasAssistantOutput = true,
                isStreaming = false,
                isLoadingSuggestions = true,
                suggestions = emptyList(),
            ),
        )
    }

    @Test
    fun assistantSuggestionsHideForStreamingOrOlderMessages() {
        assertEquals(
            false,
            shouldShowAssistantSuggestions(
                isLatestAssistant = true,
                hasAssistantOutput = true,
                isStreaming = true,
                isLoadingSuggestions = true,
                suggestions = emptyList(),
            ),
        )
        assertEquals(
            false,
            shouldShowAssistantSuggestions(
                isLatestAssistant = false,
                hasAssistantOutput = true,
                isStreaming = false,
                isLoadingSuggestions = true,
                suggestions = listOf("Follow up?"),
            ),
        )
    }

    @Test
    fun assistantSuggestionsHideUntilAssistantOutputExists() {
        assertEquals(
            false,
            shouldShowAssistantSuggestions(
                isLatestAssistant = true,
                hasAssistantOutput = false,
                isStreaming = false,
                isLoadingSuggestions = true,
                suggestions = emptyList(),
            ),
        )
        assertEquals(
            false,
            shouldShowAssistantSuggestions(
                isLatestAssistant = true,
                hasAssistantOutput = false,
                isStreaming = false,
                isLoadingSuggestions = false,
                suggestions = listOf("Follow up?"),
            ),
        )
    }

    @Test
    fun assistantSuggestionsUseOnlyLatestAssistantWithRealOutputFromState() {
        val olderAssistant = RuntimeChatMessage(
            id = "assistant-old",
            role = "assistant",
            content = "Earlier answer",
            suggestions = listOf("Old follow-up?"),
        )
        val userMessage = RuntimeChatMessage(
            id = "user-new",
            role = "user",
            content = "Next prompt",
        )
        val latestAssistant = RuntimeChatMessage(
            id = "assistant-new",
            role = "assistant",
            content = "Latest answer",
            suggestions = listOf("New follow-up?"),
        )
        val state = RuntimeUiState(
            messages = listOf(olderAssistant, userMessage, latestAssistant),
        )

        assertEquals(false, shouldShowAssistantSuggestionsForMessage(state, olderAssistant))
        assertEquals(false, shouldShowAssistantSuggestionsForMessage(state, userMessage))
        assertEquals(true, shouldShowAssistantSuggestionsForMessage(state, latestAssistant))
    }

    @Test
    fun assistantSuggestionsStayHiddenForReasoningOnlyAssistantRows() {
        val reasoningOnlyAssistant = RuntimeChatMessage(
            id = "assistant-thinking",
            role = "assistant",
            content = "",
            reasoning = "Checking the route.",
            suggestions = listOf("Follow-up should wait"),
        )
        val state = RuntimeUiState(
            messages = listOf(
                RuntimeChatMessage(id = "user", role = "user", content = "Prompt"),
                reasoningOnlyAssistant,
            ),
            isLoadingSuggestions = true,
        )

        assertEquals(false, shouldShowAssistantSuggestionsForMessage(state, reasoningOnlyAssistant))
    }

    @Test
    fun assistantSuggestionsNormalizeBlankDuplicatesAndMaximumRows() {
        val suggestions = listOf(
            "  Follow up?  ",
            "",
            "follow   up?",
            "Compare options?",
            "Summarize this\nagain?",
            "Draft next step?",
            "Extra row should be hidden",
        )

        assertEquals(
            listOf(
                "Follow up?",
                "Compare options?",
                "Summarize this again?",
                "Draft next step?",
            ),
            normalizedSuggestedQuestions(suggestions),
        )
        assertEquals(SUGGESTED_QUESTION_MAX_ITEMS, normalizedSuggestedQuestions(suggestions).size)
    }

    @Test
    fun assistantSuggestionsHideWhenRowsNormalizeToBlank() {
        assertEquals(
            false,
            shouldShowAssistantSuggestions(
                isLatestAssistant = true,
                hasAssistantOutput = true,
                isStreaming = false,
                isLoadingSuggestions = false,
                suggestions = listOf(" ", "\n\t"),
            ),
        )
        assertEquals(
            true,
            shouldShowAssistantSuggestions(
                isLatestAssistant = true,
                hasAssistantOutput = true,
                isStreaming = false,
                isLoadingSuggestions = true,
                suggestions = listOf(" ", "\n\t"),
            ),
        )
    }

    private fun trustedRuntime(
        relayHost: String? = "relay.example.test",
        relayPort: Int? = 443,
        relayId: String? = "relay-1",
        relaySecret: String? = "secret-1",
        relayExpiresAtEpochMillis: Long? = null,
        relayNonce: String? = null,
        relayScope: String? = null,
    ): RuntimeTrustedRuntime {
        return RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            relayHost = relayHost,
            relayPort = relayPort,
            relayId = relayId,
            relaySecret = relaySecret,
            relayExpiresAtEpochMillis = relayExpiresAtEpochMillis,
            relayNonce = relayNonce,
            relayScope = relayScope,
        )
    }

    private fun discoveredRuntime(routeToken: String? = null): RuntimeDiscoveredRuntime {
        return RuntimeDiscoveredRuntime(
            serviceName = "AetherLink Runtime",
            host = "192.168.1.20",
            port = 43170,
            routeToken = routeToken,
            deviceId = "runtime-1".takeIf { routeToken != null },
            fingerprint = "runtime-fingerprint".takeIf { routeToken != null },
        )
    }

    private fun documentAttachment(): RuntimePendingAttachment {
        return RuntimePendingAttachment(
            id = "attachment-document",
            type = "document",
            name = "notes.txt",
            mimeType = "text/plain",
            sizeBytes = 12L,
            dataBase64 = "bm90ZXM=",
        )
    }

    private fun imageAttachment(): RuntimePendingAttachment {
        return RuntimePendingAttachment(
            id = "attachment-image",
            type = "image",
            name = "diagram.png",
            mimeType = "image/png",
            sizeBytes = 24L,
            dataBase64 = "aW1hZ2U=",
        )
    }
}
