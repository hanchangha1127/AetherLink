package com.localagentbridge.android

import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.localagentbridge.android.runtime.RuntimeAppTheme
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config

@RunWith(AndroidJUnit4::class)
@Config(sdk = [35])
class AetherLinkThemeNoDeviceComposeTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun aetherLinkThemeLightUsesAetherLinkLightColors() {
        assertLightColors(captureThemeColors(RuntimeAppTheme.Light))
    }

    @Test
    fun aetherLinkThemeDarkUsesAetherLinkDarkColors() {
        assertDarkColors(captureThemeColors(RuntimeAppTheme.Dark))
    }

    @Test
    @Config(sdk = [35], qualifiers = "notnight")
    fun aetherLinkThemeSystemUsesLightColorsWhenSystemIsLight() {
        assertLightColors(captureThemeColors(RuntimeAppTheme.System))
    }

    @Test
    @Config(sdk = [35], qualifiers = "night")
    fun aetherLinkThemeSystemUsesDarkColorsWhenSystemIsDark() {
        assertDarkColors(captureThemeColors(RuntimeAppTheme.System))
    }

    private fun captureThemeColors(theme: RuntimeAppTheme): CapturedThemeColors {
        var capturedColors: CapturedThemeColors? = null

        compose.setContent {
            AetherLinkTheme(theme = theme) {
                val colorScheme = MaterialTheme.colorScheme
                capturedColors = CapturedThemeColors(
                    primary = colorScheme.primary,
                    background = colorScheme.background,
                    surface = colorScheme.surface,
                    onSurface = colorScheme.onSurface,
                )
            }
        }
        compose.waitForIdle()

        return checkNotNull(capturedColors)
    }

    private fun assertLightColors(colors: CapturedThemeColors) {
        assertEquals(Color(0xFF0F7B5F), colors.primary)
        assertEquals(Color(0xFFFCFCFA), colors.background)
        assertEquals(Color(0xFFFCFCFA), colors.surface)
        assertEquals(Color(0xFF1B1C1A), colors.onSurface)
    }

    private fun assertDarkColors(colors: CapturedThemeColors) {
        assertEquals(Color(0xFF8BDDBF), colors.primary)
        assertEquals(Color(0xFF111312), colors.background)
        assertEquals(Color(0xFF111312), colors.surface)
        assertEquals(Color(0xFFE2E4E0), colors.onSurface)
    }

    private data class CapturedThemeColors(
        val primary: Color,
        val background: Color,
        val surface: Color,
        val onSurface: Color,
    )
}
