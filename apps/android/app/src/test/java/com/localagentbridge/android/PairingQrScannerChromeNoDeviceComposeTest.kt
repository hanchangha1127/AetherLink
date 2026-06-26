package com.localagentbridge.android

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.hapticfeedback.HapticFeedback
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
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
import androidx.test.ext.junit.runners.AndroidJUnit4
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
        var requestPermissionClicks = 0
        var cancelClicks = 0

        compose.setContent {
            CompositionLocalProvider(LocalHapticFeedback provides hapticFeedback) {
                MaterialTheme {
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

        compose.onNodeWithText("Scan AetherLink QR").assertIsDisplayed()
        compose.onNodeWithText("Camera access is needed").assertIsDisplayed()
        compose.onNodeWithText("AetherLink uses the camera only to scan pairing QR codes.").assertIsDisplayed()
        compose.onAllNodesWithTag(CAMERA_PREVIEW_TAG).assertCountEquals(0)
        compose.onAllNodesWithContentDescription("Turn flashlight on").assertCountEquals(0)

        compose.onNodeWithText("Allow camera").performClick()

        assertEquals(1, requestPermissionClicks)
        assertEquals(0, cancelClicks)
        assertEquals(listOf(HapticFeedbackType.TextHandleMove), hapticFeedback.events)
    }

    @Test
    fun scannerChromeShowsCameraStateWithTorchAndCancelActions() {
        val hapticFeedback = RecordingHapticFeedback()
        val torchEnabled = mutableStateOf(false)
        var torchToggleClicks = 0
        var cancelClicks = 0
        var requestPermissionClicks = 0

        compose.setContent {
            CompositionLocalProvider(LocalHapticFeedback provides hapticFeedback) {
                MaterialTheme {
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

        compose.onNodeWithText("Scan AetherLink QR").assertIsDisplayed()
        compose.onNodeWithText(
            "Point the camera at the latest AetherLink Runtime QR. " +
                "The QR must verify AetherLink Runtime and include a connection both devices can reach."
        ).assertIsDisplayed()
        compose.onNodeWithTag(CAMERA_PREVIEW_TAG).assertIsDisplayed()
        compose.onNodeWithTag(PAIRING_QR_FLASHLIGHT_BUTTON_TEST_TAG, useUnmergedTree = true)
            .assert(hasStateDescription("Flashlight off"))

        compose.onNodeWithContentDescription("Turn flashlight on").performClick()
        compose.onNodeWithTag(PAIRING_QR_FLASHLIGHT_BUTTON_TEST_TAG, useUnmergedTree = true)
            .assert(hasStateDescription("Flashlight on"))
        compose.onNodeWithContentDescription("Turn flashlight off").assertIsDisplayed()
        compose.onNodeWithText("Cancel").performClick()

        assertEquals(1, torchToggleClicks)
        assertEquals(1, cancelClicks)
        assertEquals(0, requestPermissionClicks)
        assertEquals(
            listOf(HapticFeedbackType.TextHandleMove, HapticFeedbackType.TextHandleMove),
            hapticFeedback.events,
        )
    }

    private class RecordingHapticFeedback : HapticFeedback {
        val events = mutableListOf<HapticFeedbackType>()

        override fun performHapticFeedback(hapticFeedbackType: HapticFeedbackType) {
            events += hapticFeedbackType
        }
    }

    private companion object {
        const val CAMERA_PREVIEW_TAG = "pairing_qr_camera_preview"
    }
}
