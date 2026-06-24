package com.localagentbridge.android

import com.localagentbridge.android.runtime.RuntimeModel
import com.localagentbridge.android.runtime.RuntimeUiState
import com.localagentbridge.android.ui.reasoningPreview
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class AppNavigationTest {
    @Test
    fun freshInstallStartsOnPairing() {
        val destination = resolveAppDestination(
            current = AppDestination.Chat,
            hasTrustedRuntime = false,
            pairingOnboardingCompleted = false,
        )

        assertEquals(AppDestination.Pairing, destination)
    }

    @Test
    fun trustedRuntimeLoadedFromPairingOnboardingGoesToChat() {
        val destination = resolveAppDestination(
            current = AppDestination.Pairing,
            hasTrustedRuntime = true,
            pairingOnboardingCompleted = false,
        )

        assertEquals(AppDestination.Chat, destination)
    }

    @Test
    fun settingsRemainsStableDuringPairingManagement() {
        val unpairedDestination = resolveAppDestination(
            current = AppDestination.Settings,
            hasTrustedRuntime = false,
            pairingOnboardingCompleted = false,
        )
        val trustedDestination = resolveAppDestination(
            current = AppDestination.Settings,
            hasTrustedRuntime = true,
            pairingOnboardingCompleted = true,
        )

        assertEquals(AppDestination.Settings, unpairedDestination)
        assertEquals(AppDestination.Settings, trustedDestination)
    }

    @Test
    fun completedOnboardingMovesPairingRouteToSettingsWhenRuntimeIsForgotten() {
        val destination = resolveAppDestination(
            current = AppDestination.Pairing,
            hasTrustedRuntime = false,
            pairingOnboardingCompleted = true,
        )

        assertEquals(AppDestination.Settings, destination)
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

        assertEquals(
            listOf("application/*", "text/*"),
            attachmentPickerMimeTypes(state).toList(),
        )
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

        assertEquals(
            listOf("application/*", "text/*", "image/*"),
            attachmentPickerMimeTypes(state).toList(),
        )
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
    fun chatModelPickerClosedLabelUsesRuntimeModelNameWhenAvailable() {
        val state = RuntimeUiState(
            selectedModelId = "ollama:qwen3:8b",
            models = listOf(
                RuntimeModel(
                    id = "ollama:qwen3:8b",
                    name = "Qwen3 8B",
                    modelKind = "chat",
                    capabilities = listOf("chat"),
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
    fun pairingDeepLinkAcceptsAetherLinkPairUris() {
        val rawUri = "aetherlink://pair?pairing_code=123456&relay_host=relay.example.test"

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
    fun pairingDeepLinkAcceptsLegacyLabPairUris() {
        val rawUri = "lab://pair?pairing_code=123456"

        assertEquals(
            rawUri,
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
}
