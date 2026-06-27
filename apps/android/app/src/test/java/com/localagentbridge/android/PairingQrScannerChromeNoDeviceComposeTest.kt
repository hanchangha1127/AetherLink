package com.localagentbridge.android

import android.content.Context
import android.content.res.Configuration
import android.os.LocaleList
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.hapticfeedback.HapticFeedback
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.assert
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.hasStateDescription
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onAllNodesWithContentDescription
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import java.util.Locale
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config

@RunWith(AndroidJUnit4::class)
@Config(sdk = [35])
class PairingQrScannerChromeNoDeviceComposeTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun scannerChromeShowsPermissionStateWithoutCameraPreview() {
        val hapticFeedback = RecordingHapticFeedback()
        val currentExpectation = mutableStateOf(scannerLocaleExpectations().first())
        var requestPermissionClicks = 0
        var cancelClicks = 0

        compose.setContent {
            CompositionLocalProvider(LocalHapticFeedback provides hapticFeedback) {
                LocalizedScannerContent(languageTag = currentExpectation.value.languageTag) {
                    PairingQrScannerChrome(
                        hasCameraPermission = false,
                        torchAvailable = false,
                        torchEnabled = false,
                        onTorchToggle = {},
                        onCancel = { cancelClicks += 1 },
                        onRequestCameraPermission = { requestPermissionClicks += 1 },
                    )
                }
            }
        }

        scannerLocaleExpectations().forEachIndexed { index, expected ->
            currentExpectation.value = expected
            compose.waitForIdle()

            compose.onNodeWithText(expected.title).assertIsDisplayed()
            compose.onNodeWithText(expected.permissionTitle).assertIsDisplayed()
            compose.onNodeWithText(expected.permissionDetail).assertIsDisplayed()
            compose.onAllNodesWithTag(CAMERA_PREVIEW_TAG).assertCountEquals(0)
            compose.onAllNodesWithContentDescription(expected.flashlightOn).assertCountEquals(0)
            compose.onNodeWithText(expected.cancel).assertIsDisplayed()

            hapticFeedback.events.clear()
            compose.onNodeWithText(expected.permissionAction).performClick()

            assertEquals(index + 1, requestPermissionClicks)
            assertEquals(index, cancelClicks)
            assertEquals(listOf(HapticFeedbackType.TextHandleMove), hapticFeedback.events)

            hapticFeedback.events.clear()
            compose.onNodeWithText(expected.cancel).performClick()

            assertEquals(index + 1, requestPermissionClicks)
            assertEquals(index + 1, cancelClicks)
            assertEquals(listOf(HapticFeedbackType.TextHandleMove), hapticFeedback.events)
        }
    }

    @Test
    fun scannerChromeShowsSettingsRecoveryWhenCameraPermissionIsBlocked() {
        val hapticFeedback = RecordingHapticFeedback()
        val currentExpectation = mutableStateOf(scannerLocaleExpectations().first())
        var requestPermissionClicks = 0
        var openSettingsClicks = 0
        var cancelClicks = 0

        compose.setContent {
            CompositionLocalProvider(LocalHapticFeedback provides hapticFeedback) {
                LocalizedScannerContent(languageTag = currentExpectation.value.languageTag) {
                    PairingQrScannerChrome(
                        hasCameraPermission = false,
                        cameraPermissionPermanentlyDenied = true,
                        torchAvailable = false,
                        torchEnabled = false,
                        onTorchToggle = {},
                        onCancel = { cancelClicks += 1 },
                        onRequestCameraPermission = { requestPermissionClicks += 1 },
                        onOpenAppSettings = { openSettingsClicks += 1 },
                    )
                }
            }
        }

        scannerLocaleExpectations().forEachIndexed { index, expected ->
            currentExpectation.value = expected
            compose.waitForIdle()

            compose.onNodeWithText(expected.title).assertIsDisplayed()
            compose.onNodeWithText(expected.blockedPermissionTitle).assertIsDisplayed()
            compose.onNodeWithText(expected.blockedPermissionDetail).assertIsDisplayed()
            compose.onAllNodesWithTag(CAMERA_PREVIEW_TAG).assertCountEquals(0)
            compose.onAllNodesWithContentDescription(expected.flashlightOn).assertCountEquals(0)
            compose.onNodeWithText(expected.cancel).assertIsDisplayed()

            hapticFeedback.events.clear()
            compose.onNodeWithText(expected.settingsAction).performClick()

            assertEquals(0, requestPermissionClicks)
            assertEquals(index + 1, openSettingsClicks)
            assertEquals(index, cancelClicks)
            assertEquals(listOf(HapticFeedbackType.TextHandleMove), hapticFeedback.events)

            hapticFeedback.events.clear()
            compose.onNodeWithText(expected.cancel).performClick()

            assertEquals(0, requestPermissionClicks)
            assertEquals(index + 1, openSettingsClicks)
            assertEquals(index + 1, cancelClicks)
            assertEquals(listOf(HapticFeedbackType.TextHandleMove), hapticFeedback.events)
        }
    }

    @Test
    fun scannerChromeShowsCameraStateWithTorchAndCancelActions() {
        val hapticFeedback = RecordingHapticFeedback()
        val currentExpectation = mutableStateOf(scannerLocaleExpectations().first())
        val torchEnabled = mutableStateOf(false)
        var torchToggleClicks = 0
        var cancelClicks = 0
        var requestPermissionClicks = 0

        compose.setContent {
            CompositionLocalProvider(LocalHapticFeedback provides hapticFeedback) {
                LocalizedScannerContent(languageTag = currentExpectation.value.languageTag) {
                    PairingQrScannerChrome(
                        hasCameraPermission = true,
                        torchAvailable = true,
                        torchEnabled = torchEnabled.value,
                        onTorchToggle = {
                            torchToggleClicks += 1
                            torchEnabled.value = !torchEnabled.value
                        },
                        onCancel = { cancelClicks += 1 },
                        onRequestCameraPermission = { requestPermissionClicks += 1 },
                    ) {
                        Box(
                            modifier = Modifier
                                .fillMaxSize()
                                .testTag(CAMERA_PREVIEW_TAG),
                        )
                    }
                }
            }
        }

        scannerLocaleExpectations().forEachIndexed { index, expected ->
            currentExpectation.value = expected
            torchEnabled.value = false
            compose.waitForIdle()

            compose.onNodeWithText(expected.title).assertIsDisplayed()
            compose.onNodeWithText(expected.detail).assertIsDisplayed()
            compose.onNodeWithTag(CAMERA_PREVIEW_TAG).assertIsDisplayed()
            compose.onNodeWithTag(PAIRING_QR_FLASHLIGHT_BUTTON_TEST_TAG, useUnmergedTree = true)
                .assert(hasStateDescription(expected.flashlightStateOff))

            hapticFeedback.events.clear()
            compose.onNodeWithContentDescription(expected.flashlightOn).performClick()
            compose.onNodeWithTag(PAIRING_QR_FLASHLIGHT_BUTTON_TEST_TAG, useUnmergedTree = true)
                .assert(hasStateDescription(expected.flashlightStateOn))
            compose.onNodeWithContentDescription(expected.flashlightOff).assertIsDisplayed()
            compose.onNodeWithText(expected.cancel).performClick()

            assertEquals(index + 1, torchToggleClicks)
            assertEquals(index + 1, cancelClicks)
            assertEquals(0, requestPermissionClicks)
            assertEquals(
                listOf(HapticFeedbackType.TextHandleMove, HapticFeedbackType.TextHandleMove),
                hapticFeedback.events,
            )
        }
    }

    @Composable
    private fun LocalizedScannerContent(
        languageTag: String,
        content: @Composable () -> Unit,
    ) {
        val baseContext = LocalContext.current
        val localizedContext = remember(baseContext, languageTag) {
            baseContext.localizedContext(languageTag)
        }
        CompositionLocalProvider(LocalContext provides localizedContext) {
            MaterialTheme {
                content()
            }
        }
    }

    private fun scannerLocaleExpectations(): List<ScannerLocaleExpectation> {
        val baseContext = ApplicationProvider.getApplicationContext<Context>()
        return listOf("en", "ko", "ja", "zh-CN", "fr").map { languageTag ->
            val localizedContext = baseContext.localizedContext(languageTag)
            ScannerLocaleExpectation(
                languageTag = languageTag,
                title = localizedContext.getString(R.string.qr_scanner_title),
                detail = localizedContext.getString(R.string.qr_scanner_detail),
                permissionTitle = localizedContext.getString(R.string.qr_scanner_permission_title),
                permissionDetail = localizedContext.getString(R.string.qr_scanner_permission_detail),
                permissionAction = localizedContext.getString(R.string.qr_scanner_permission_action),
                blockedPermissionTitle = localizedContext.getString(
                    R.string.qr_scanner_permission_blocked_title
                ),
                blockedPermissionDetail = localizedContext.getString(
                    R.string.qr_scanner_permission_blocked_detail
                ),
                settingsAction = localizedContext.getString(
                    R.string.qr_scanner_permission_settings_action
                ),
                flashlightOn = localizedContext.getString(R.string.qr_scanner_flashlight_on),
                flashlightOff = localizedContext.getString(R.string.qr_scanner_flashlight_off),
                flashlightStateOn = localizedContext.getString(
                    R.string.qr_scanner_flashlight_state_on
                ),
                flashlightStateOff = localizedContext.getString(
                    R.string.qr_scanner_flashlight_state_off
                ),
                cancel = localizedContext.getString(R.string.cancel),
            )
        }
    }

    private fun Context.localizedContext(languageTag: String): Context {
        val locale = Locale.forLanguageTag(languageTag)
        val configuration = Configuration(resources.configuration)
        configuration.setLocale(locale)
        configuration.setLocales(LocaleList(locale))
        return createConfigurationContext(configuration)
    }

    private class RecordingHapticFeedback : HapticFeedback {
        val events = mutableListOf<HapticFeedbackType>()

        override fun performHapticFeedback(hapticFeedbackType: HapticFeedbackType) {
            events += hapticFeedbackType
        }
    }

    private data class ScannerLocaleExpectation(
        val languageTag: String,
        val title: String,
        val detail: String,
        val permissionTitle: String,
        val permissionDetail: String,
        val permissionAction: String,
        val blockedPermissionTitle: String,
        val blockedPermissionDetail: String,
        val settingsAction: String,
        val flashlightOn: String,
        val flashlightOff: String,
        val flashlightStateOn: String,
        val flashlightStateOff: String,
        val cancel: String,
    )

    private companion object {
        const val CAMERA_PREVIEW_TAG = "pairing_qr_camera_preview"
    }
}
