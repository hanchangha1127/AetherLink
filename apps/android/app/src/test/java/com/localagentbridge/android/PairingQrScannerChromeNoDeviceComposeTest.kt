package com.localagentbridge.android

import android.content.Context
import android.content.res.Configuration
import android.os.LocaleList
import androidx.activity.ComponentActivity
import androidx.activity.compose.LocalActivityResultRegistryOwner
import androidx.activity.result.ActivityResultRegistry
import androidx.activity.result.ActivityResultRegistryOwner
import androidx.activity.result.contract.ActivityResultContract
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.width
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.hapticfeedback.HapticFeedback
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.assert
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.hasStateDescription
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onAllNodesWithContentDescription
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.unit.DpRect
import androidx.compose.ui.unit.dp
import androidx.core.app.ActivityOptionsCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.LifecycleRegistry
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import java.util.Locale
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
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

            compose.onNodeWithText(expected.title)
                .assertIsDisplayed()
                .assert(hasHeading())
            compose.onNodeWithText(expected.permissionTitle)
                .assertIsDisplayed()
                .assert(hasHeading())
            compose.onNodeWithText(expected.permissionDetail).assertIsDisplayed()
            compose.onAllNodesWithTag(CAMERA_PREVIEW_TAG).assertCountEquals(0)
            compose.onAllNodesWithContentDescription(expected.flashlightOn).assertCountEquals(0)
            compose.onNodeWithContentDescription(expected.closeScanner).assertIsDisplayed()
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

            compose.onNodeWithText(expected.title)
                .assertIsDisplayed()
                .assert(hasHeading())
            compose.onNodeWithText(expected.blockedPermissionTitle)
                .assertIsDisplayed()
                .assert(hasHeading())
            compose.onNodeWithText(expected.blockedPermissionDetail).assertIsDisplayed()
            compose.onAllNodesWithTag(CAMERA_PREVIEW_TAG).assertCountEquals(0)
            compose.onAllNodesWithContentDescription(expected.flashlightOn).assertCountEquals(0)
            compose.onNodeWithContentDescription(expected.closeScanner).assertIsDisplayed()
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
    fun cameraPermissionStateMachineRequestsOnlyOnFirstEntryAndNeverDuringReentry() {
        var automaticRequestCount = 0
        fun observeScannerEntry(stage: PairingQrCameraPermissionStage) {
            if (shouldAutomaticallyRequestPairingQrCameraPermission(stage)) {
                automaticRequestCount += 1
            }
        }

        val firstEntry = pairingQrCameraPermissionStage(
            hasPermission = false,
            requestRecord =
                PairingQrCameraPermissionRequestRecord.NeverStarted,
            requestIsInFlight = false,
            shouldShowRationale = false,
        )
        assertEquals(PairingQrCameraPermissionStage.NeverAsked, firstEntry)
        assertTrue(canRequestPairingQrCameraPermission(firstEntry))
        observeScannerEntry(firstEntry)

        val requestInFlight = pairingQrCameraPermissionStage(
            hasPermission = false,
            requestRecord =
                PairingQrCameraPermissionRequestRecord.LaunchPending,
            requestIsInFlight = true,
            shouldShowRationale = false,
        )
        assertEquals(
            PairingQrCameraPermissionStage.RequestInFlight,
            requestInFlight,
        )
        assertFalse(canRequestPairingQrCameraPermission(requestInFlight))
        observeScannerEntry(requestInFlight)

        val firstDenialAndReentry = pairingQrCameraPermissionStage(
            hasPermission = false,
            requestRecord =
                PairingQrCameraPermissionRequestRecord.Recorded,
            requestIsInFlight = false,
            shouldShowRationale = true,
        )
        assertEquals(
            PairingQrCameraPermissionStage.RationaleRequired,
            firstDenialAndReentry,
        )
        assertTrue(canRequestPairingQrCameraPermission(firstDenialAndReentry))
        observeScannerEntry(firstDenialAndReentry)

        val repeatedDenialAndReentry = pairingQrCameraPermissionStage(
            hasPermission = false,
            requestRecord =
                PairingQrCameraPermissionRequestRecord.Recorded,
            requestIsInFlight = false,
            shouldShowRationale = false,
        )
        assertEquals(
            PairingQrCameraPermissionStage.SettingsRecovery,
            repeatedDenialAndReentry,
        )
        assertFalse(
            canRequestPairingQrCameraPermission(repeatedDenialAndReentry),
        )
        observeScannerEntry(repeatedDenialAndReentry)

        assertEquals(1, automaticRequestCount)
    }

    @Test
    fun cameraPermissionStateMachineReconcilesSettingsReturnWithoutReRequest() {
        val deniedAfterSettings = pairingQrCameraPermissionStage(
            hasPermission = false,
            requestRecord =
                PairingQrCameraPermissionRequestRecord.Recorded,
            requestIsInFlight = false,
            shouldShowRationale = false,
        )
        assertEquals(
            PairingQrCameraPermissionStage.SettingsRecovery,
            deniedAfterSettings,
        )
        assertFalse(
            shouldAutomaticallyRequestPairingQrCameraPermission(
                deniedAfterSettings,
            ),
        )

        val grantedAfterSettings = pairingQrCameraPermissionStage(
            hasPermission = true,
            requestRecord =
                PairingQrCameraPermissionRequestRecord.Recorded,
            requestIsInFlight = false,
            shouldShowRationale = false,
        )
        assertEquals(
            PairingQrCameraPermissionStage.Granted,
            grantedAfterSettings,
        )
        assertFalse(canRequestPairingQrCameraPermission(grantedAfterSettings))

        val revokedAfterGrant = pairingQrCameraPermissionStage(
            hasPermission = false,
            requestRecord =
                PairingQrCameraPermissionRequestRecord.Recorded,
            requestIsInFlight = false,
            shouldShowRationale = false,
        )
        assertEquals(
            PairingQrCameraPermissionStage.SettingsRecovery,
            revokedAfterGrant,
        )
        assertFalse(
            shouldAutomaticallyRequestPairingQrCameraPermission(
                revokedAfterGrant,
            ),
        )
    }

    @Test
    fun cameraPermissionRequestTransactionPersistsBeforeLaunchAndFinalizesAfterAcceptance() {
        var requestRecord =
            PairingQrCameraPermissionRequestRecord.NeverStarted
        var requestIsInFlight = false
        val events = mutableListOf<String>()

        val launched = beginPairingQrCameraPermissionRequest(
            requestRecord = requestRecord,
            persistRequestRecord = { updatedRecord ->
                events += "persist:$updatedRecord"
                true
            },
            updateRequestRecord = { updatedRecord ->
                requestRecord = updatedRecord
                events += "record:$updatedRecord"
            },
            updateRequestInFlight = { inFlight ->
                requestIsInFlight = inFlight
                events += "in-flight:$inFlight"
            },
            launchPermissionRequest = {
                events += "launch"
            },
        )

        assertTrue(launched)
        assertEquals(
            PairingQrCameraPermissionRequestRecord.Recorded,
            requestRecord,
        )
        assertTrue(requestIsInFlight)
        assertEquals(
            listOf(
                "persist:LaunchPending",
                "record:LaunchPending",
                "in-flight:true",
                "launch",
                "persist:Recorded",
                "record:Recorded",
            ),
            events,
        )

        var synchronousRecord =
            PairingQrCameraPermissionRequestRecord.NeverStarted
        var synchronousRequestIsInFlight = false
        val synchronousLaunchAccepted =
            beginPairingQrCameraPermissionRequest(
                requestRecord = synchronousRecord,
                persistRequestRecord = { true },
                updateRequestRecord = { synchronousRecord = it },
                updateRequestInFlight = {
                    synchronousRequestIsInFlight = it
                },
                launchPermissionRequest = {
                    synchronousRecord =
                        completePairingQrCameraPermissionRequest(
                            requestRecord = synchronousRecord,
                            persistRequestRecord = { true },
                        )
                    synchronousRequestIsInFlight = false
                },
            )
        assertTrue(synchronousLaunchAccepted)
        assertEquals(
            PairingQrCameraPermissionRequestRecord.Recorded,
            synchronousRecord,
        )
        assertFalse(synchronousRequestIsInFlight)
    }

    @Test
    fun cameraPermissionRequestTransactionDoesNotLaunchWhenPersistenceFails() {
        var requestRecord =
            PairingQrCameraPermissionRequestRecord.NeverStarted
        var requestIsInFlight = false
        var launchCount = 0

        val launched = beginPairingQrCameraPermissionRequest(
            requestRecord = requestRecord,
            persistRequestRecord = { false },
            updateRequestRecord = { requestRecord = it },
            updateRequestInFlight = { requestIsInFlight = it },
            launchPermissionRequest = { launchCount += 1 },
        )

        assertFalse(launched)
        assertEquals(0, launchCount)
        assertEquals(
            PairingQrCameraPermissionRequestRecord.NeverStarted,
            requestRecord,
        )
        assertFalse(requestIsInFlight)
    }

    @Test
    fun cameraPermissionRequestTransactionPersistsManualRetryAcrossLauncherFailureRecreation() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val preferencesName =
            "camera-permission-launch-failure-${System.nanoTime()}"
        val preferences = context.getSharedPreferences(
            preferencesName,
            Context.MODE_PRIVATE,
        )
        try {
            var requestRecord =
                readPairingQrCameraPermissionRequestRecord(preferences)
            var requestIsInFlight = false

            val launched = beginPairingQrCameraPermissionRequest(
                requestRecord = requestRecord,
                persistRequestRecord = { updatedRecord ->
                    persistPairingQrCameraPermissionRequestRecord(
                        preferences,
                        updatedRecord,
                    )
                },
                updateRequestRecord = { requestRecord = it },
                updateRequestInFlight = { requestIsInFlight = it },
                launchPermissionRequest = {
                    throw IllegalStateException("launcher unavailable")
                },
            )

            assertFalse(launched)
            assertFalse(requestIsInFlight)
            assertEquals(
                PairingQrCameraPermissionRequestRecord.RetryRequired,
                requestRecord,
            )
            val recordAfterRecreation =
                readPairingQrCameraPermissionRequestRecord(preferences)
            assertEquals(
                PairingQrCameraPermissionRequestRecord.RetryRequired,
                recordAfterRecreation,
            )
            val retryStage = pairingQrCameraPermissionStage(
                hasPermission = false,
                requestRecord = recordAfterRecreation,
                requestIsInFlight = false,
                shouldShowRationale = false,
            )
            assertEquals(
                PairingQrCameraPermissionStage.RetryRequired,
                retryStage,
            )
            assertFalse(
                shouldAutomaticallyRequestPairingQrCameraPermission(
                    retryStage,
                ),
            )
            assertTrue(canRequestPairingQrCameraPermission(retryStage))
        } finally {
            context.deleteSharedPreferences(preferencesName)
        }
    }

    @Test
    fun cameraPermissionResumeReconcilesStaleInFlightRequestWithoutAutoRetry() {
        listOf(true, false).forEach { completionPersists ->
            val resumed = reconcilePairingQrCameraPermissionRequestOnResume(
                requestRecord =
                    PairingQrCameraPermissionRequestRecord.LaunchPending,
                requestIsInFlight = true,
                persistRequestRecord = { completionPersists },
            )

            assertEquals(
                if (completionPersists) {
                    PairingQrCameraPermissionRequestRecord.Recorded
                } else {
                    PairingQrCameraPermissionRequestRecord.RetryRequired
                },
                resumed.requestRecord,
            )
            assertFalse(resumed.requestIsInFlight)
            val resumedStage = pairingQrCameraPermissionStage(
                hasPermission = false,
                requestRecord = resumed.requestRecord,
                requestIsInFlight = resumed.requestIsInFlight,
                shouldShowRationale = false,
            )
            assertEquals(
                if (completionPersists) {
                    PairingQrCameraPermissionStage.SettingsRecovery
                } else {
                    PairingQrCameraPermissionStage.RetryRequired
                },
                resumedStage,
            )
            assertFalse(
                shouldAutomaticallyRequestPairingQrCameraPermission(
                    resumedStage,
                ),
            )
        }
    }

    @Test
    fun cameraPermissionControllerHostRunsResultReentryAndResumeLifecycle() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val preferencesName =
            "camera-permission-controller-host-${System.nanoTime()}"
        val preferences = context.getSharedPreferences(
            preferencesName,
            Context.MODE_PRIVATE,
        )
        val platform = RecordingCameraPermissionPlatform()
        val lifecycleOwner = ManualLifecycleOwner().apply {
            handle(Lifecycle.Event.ON_CREATE)
        }
        val resultRegistry = RecordingPermissionActivityResultRegistry()
        val resultRegistryOwner =
            RecordingActivityResultRegistryOwner(resultRegistry)
        val hostGeneration = mutableStateOf(0)
        val scannerVisible = mutableStateOf(true)
        var latestController: PairingQrCameraPermissionController? = null

        try {
            compose.setContent {
                CompositionLocalProvider(
                    LocalActivityResultRegistryOwner provides
                        resultRegistryOwner,
                    LocalLifecycleOwner provides lifecycleOwner,
                ) {
                    key(hostGeneration.value) {
                        val controller =
                            rememberPairingQrCameraPermissionController(
                                platform = platform,
                                preferencesOverride = preferences,
                            )
                        SideEffect {
                            latestController = controller
                        }
                        if (scannerVisible.value) {
                            PairingQrCameraPermissionAutoRequestEffect(
                                controller,
                            )
                        }
                    }
                }
            }
            compose.waitForIdle()

            assertEquals(1, resultRegistry.launchCount)
            assertEquals(
                PairingQrCameraPermissionStage.RequestInFlight,
                checkNotNull(latestController).stage,
            )

            compose.runOnIdle {
                platform.cameraPermissionRationale = true
                resultRegistry.dispatchPermissionResult(granted = false)
            }
            compose.waitForIdle()
            assertEquals(
                PairingQrCameraPermissionStage.RationaleRequired,
                checkNotNull(latestController).stage,
            )

            compose.runOnIdle {
                scannerVisible.value = false
            }
            compose.waitForIdle()
            compose.runOnIdle {
                scannerVisible.value = true
            }
            compose.waitForIdle()
            assertEquals(1, resultRegistry.launchCount)

            compose.runOnIdle {
                hostGeneration.value += 1
            }
            compose.waitForIdle()
            assertEquals(
                PairingQrCameraPermissionStage.RationaleRequired,
                checkNotNull(latestController).stage,
            )
            assertEquals(1, resultRegistry.launchCount)

            compose.runOnIdle {
                platform.cameraPermissionGranted = true
                platform.cameraPermissionRationale = false
                lifecycleOwner.handle(Lifecycle.Event.ON_START)
                lifecycleOwner.handle(Lifecycle.Event.ON_RESUME)
            }
            compose.waitForIdle()
            assertEquals(
                PairingQrCameraPermissionStage.Granted,
                checkNotNull(latestController).stage,
            )

            compose.runOnIdle {
                lifecycleOwner.handle(Lifecycle.Event.ON_PAUSE)
                platform.cameraPermissionGranted = false
                lifecycleOwner.handle(Lifecycle.Event.ON_RESUME)
            }
            compose.waitForIdle()
            assertEquals(
                PairingQrCameraPermissionStage.SettingsRecovery,
                checkNotNull(latestController).stage,
            )
            assertEquals(1, resultRegistry.launchCount)
        } finally {
            context.deleteSharedPreferences(preferencesName)
        }
    }

    @Test
    fun scannerChromeDisablesPermissionActionWhileRequestIsInFlight() {
        val expected = scannerLocaleExpectations().first()
        var requestPermissionClicks = 0

        compose.setContent {
            LocalizedScannerContent(languageTag = expected.languageTag) {
                PairingQrScannerChrome(
                    hasCameraPermission = false,
                    cameraPermissionRequestInFlight = true,
                    torchAvailable = false,
                    torchEnabled = false,
                    onTorchToggle = {},
                    onCancel = {},
                    onRequestCameraPermission = {
                        requestPermissionClicks += 1
                    },
                )
            }
        }

        compose.onNodeWithText(expected.permissionAction)
            .assertIsDisplayed()
            .assertIsNotEnabled()
        compose.onAllNodesWithTag(CAMERA_PREVIEW_TAG).assertCountEquals(0)
        assertEquals(0, requestPermissionClicks)
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

            compose.onNodeWithText(expected.title)
                .assertIsDisplayed()
                .assert(hasHeading())
            compose.onNodeWithText(expected.detail).assertIsDisplayed()
            compose.onNodeWithTag(CAMERA_PREVIEW_TAG).assertIsDisplayed()
            compose.onNodeWithTag(PAIRING_QR_SCANNER_TARGET_TEST_TAG).assertIsDisplayed()
            compose.onNodeWithContentDescription(expected.scanTarget).assertIsDisplayed()
            compose.onNodeWithContentDescription(expected.closeScanner).assertIsDisplayed()
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

    @Test
    fun scannerChromeShowsInvalidQrFeedbackWithoutClosingScanner() {
        val currentExpectation = mutableStateOf(scannerLocaleExpectations().first())
        val feedback = mutableStateOf(PairingQrScannerFeedback.InvalidPairingQr)
        var cancelClicks = 0

        compose.setContent {
            LocalizedScannerContent(languageTag = currentExpectation.value.languageTag) {
                PairingQrScannerChrome(
                    hasCameraPermission = true,
                    torchAvailable = false,
                    torchEnabled = false,
                    scannerFeedback = feedback.value,
                    onTorchToggle = {},
                    onCancel = { cancelClicks += 1 },
                    onRequestCameraPermission = {},
                ) {
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .testTag(CAMERA_PREVIEW_TAG),
                    )
                }
            }
        }

        scannerLocaleExpectations().forEach { expected ->
            currentExpectation.value = expected

            feedback.value = PairingQrScannerFeedback.InvalidPairingQr
            compose.waitForIdle()
            compose.onNodeWithText(expected.invalidQrFeedback).assertIsDisplayed()
            compose.onNodeWithContentDescription(expected.invalidQrFeedback).assertIsDisplayed()
            compose.onNodeWithTag(CAMERA_PREVIEW_TAG).assertIsDisplayed()
            compose.onNodeWithTag(PAIRING_QR_SCANNER_TARGET_TEST_TAG).assertIsDisplayed()
            compose.onNodeWithText(expected.cancel).assertIsDisplayed()
            compose.onNodeWithContentDescription(expected.closeScanner).assertIsDisplayed()

            feedback.value = PairingQrScannerFeedback.UnsupportedQr
            compose.waitForIdle()
            compose.onNodeWithText(expected.unsupportedQrFeedback).assertIsDisplayed()
            compose.onNodeWithContentDescription(expected.unsupportedQrFeedback).assertIsDisplayed()
            compose.onNodeWithTag(CAMERA_PREVIEW_TAG).assertIsDisplayed()
            compose.onNodeWithTag(PAIRING_QR_SCANNER_TARGET_TEST_TAG).assertIsDisplayed()
        }

        compose.onNodeWithText(scannerLocaleExpectations().last().cancel).performClick()
        assertEquals(1, cancelClicks)
    }

    @Test
    fun scannerChromeRendersCompactPairingStatesAcrossSupportedLanguages() {
        val currentExpectation = mutableStateOf(scannerLocaleExpectations().first())
        val scannerState = mutableStateOf(CompactScannerState.ActiveCamera)

        compose.setContent {
            LocalizedScannerContent(languageTag = currentExpectation.value.languageTag) {
                Box(
                    modifier = Modifier
                        .width(320.dp)
                        .height(520.dp),
                ) {
                    when (scannerState.value) {
                        CompactScannerState.ActiveCamera -> PairingQrScannerChrome(
                            hasCameraPermission = true,
                            torchAvailable = true,
                            torchEnabled = false,
                            onTorchToggle = {},
                            onCancel = {},
                            onRequestCameraPermission = {},
                        ) {
                            Box(
                                modifier = Modifier
                                    .fillMaxSize()
                                    .testTag(CAMERA_PREVIEW_TAG),
                            )
                        }

                        CompactScannerState.PermissionPrompt -> PairingQrScannerChrome(
                            hasCameraPermission = false,
                            torchAvailable = false,
                            torchEnabled = false,
                            onTorchToggle = {},
                            onCancel = {},
                            onRequestCameraPermission = {},
                        )

                        CompactScannerState.SettingsRecovery -> PairingQrScannerChrome(
                            hasCameraPermission = false,
                            cameraPermissionPermanentlyDenied = true,
                            torchAvailable = false,
                            torchEnabled = false,
                            onTorchToggle = {},
                            onCancel = {},
                            onRequestCameraPermission = {},
                            onOpenAppSettings = {},
                        )
                    }
                }
            }
        }

        scannerLocaleExpectations().forEach { expected ->
            currentExpectation.value = expected

            scannerState.value = CompactScannerState.ActiveCamera
            compose.waitForIdle()
            compose.onNodeWithText(expected.title)
                .assertIsDisplayed()
                .assert(hasHeading())
            compose.onNodeWithText(expected.detail).assertIsDisplayed()
            compose.onNodeWithTag(CAMERA_PREVIEW_TAG).assertIsDisplayed()
            compose.onNodeWithTag(PAIRING_QR_SCANNER_TARGET_TEST_TAG).assertIsDisplayed()
            compose.onNodeWithContentDescription(expected.scanTarget).assertIsDisplayed()
            compose.onNodeWithContentDescription(expected.flashlightOn).assertIsDisplayed()
            compose.onNodeWithText(expected.cancel).assertIsDisplayed()

            scannerState.value = CompactScannerState.PermissionPrompt
            compose.waitForIdle()
            compose.onNodeWithText(expected.title)
                .assertIsDisplayed()
                .assert(hasHeading())
            compose.onNodeWithText(expected.permissionTitle)
                .assertIsDisplayed()
                .assert(hasHeading())
            compose.onNodeWithText(expected.permissionDetail).assertIsDisplayed()
            compose.onNodeWithText(expected.permissionAction).assertIsDisplayed()
            compose.onNodeWithText(expected.cancel).assertIsDisplayed()

            scannerState.value = CompactScannerState.SettingsRecovery
            compose.waitForIdle()
            compose.onNodeWithText(expected.title)
                .assertIsDisplayed()
                .assert(hasHeading())
            compose.onNodeWithText(expected.blockedPermissionTitle)
                .assertIsDisplayed()
                .assert(hasHeading())
            compose.onNodeWithText(expected.blockedPermissionDetail).assertIsDisplayed()
            compose.onNodeWithText(expected.settingsAction).assertIsDisplayed()
            compose.onNodeWithText(expected.cancel).assertIsDisplayed()
        }
    }

    @Test
    fun scannerChromeCompactLargeFontBoundsAcrossSupportedLanguages() {
        val currentExpectation = mutableStateOf(scannerLocaleExpectations().first())
        val scannerState = mutableStateOf(CompactScannerBoundsState.ActiveCamera)

        compose.setContent {
            LocalizedScannerContent(
                languageTag = currentExpectation.value.languageTag,
                fontScale = 1.45f,
            ) {
                Box(
                    modifier = Modifier
                        .width(320.dp)
                        .height(560.dp)
                        .testTag(scannerCompactBoundsRootTestTag),
                ) {
                    when (scannerState.value) {
                        CompactScannerBoundsState.ActiveCamera -> PairingQrScannerChrome(
                            hasCameraPermission = true,
                            torchAvailable = true,
                            torchEnabled = false,
                            onTorchToggle = {},
                            onCancel = {},
                            onRequestCameraPermission = {},
                        ) {
                            Box(
                                modifier = Modifier
                                    .fillMaxSize()
                                    .testTag(CAMERA_PREVIEW_TAG),
                            )
                        }

                        CompactScannerBoundsState.InvalidFeedback -> PairingQrScannerChrome(
                            hasCameraPermission = true,
                            torchAvailable = false,
                            torchEnabled = false,
                            scannerFeedback = PairingQrScannerFeedback.InvalidPairingQr,
                            onTorchToggle = {},
                            onCancel = {},
                            onRequestCameraPermission = {},
                        ) {
                            Box(
                                modifier = Modifier
                                    .fillMaxSize()
                                    .testTag(CAMERA_PREVIEW_TAG),
                            )
                        }

                        CompactScannerBoundsState.UnsupportedFeedback -> PairingQrScannerChrome(
                            hasCameraPermission = true,
                            torchAvailable = false,
                            torchEnabled = false,
                            scannerFeedback = PairingQrScannerFeedback.UnsupportedQr,
                            onTorchToggle = {},
                            onCancel = {},
                            onRequestCameraPermission = {},
                        ) {
                            Box(
                                modifier = Modifier
                                    .fillMaxSize()
                                    .testTag(CAMERA_PREVIEW_TAG),
                            )
                        }

                        CompactScannerBoundsState.PermissionPrompt -> PairingQrScannerChrome(
                            hasCameraPermission = false,
                            torchAvailable = false,
                            torchEnabled = false,
                            onTorchToggle = {},
                            onCancel = {},
                            onRequestCameraPermission = {},
                        )

                        CompactScannerBoundsState.SettingsRecovery -> PairingQrScannerChrome(
                            hasCameraPermission = false,
                            cameraPermissionPermanentlyDenied = true,
                            torchAvailable = false,
                            torchEnabled = false,
                            onTorchToggle = {},
                            onCancel = {},
                            onRequestCameraPermission = {},
                            onOpenAppSettings = {},
                        )
                    }
                }
            }
        }

        scannerLocaleExpectations().forEach { expected ->
            currentExpectation.value = expected

            scannerState.value = CompactScannerBoundsState.ActiveCamera
            compose.waitForIdle()
            assertActiveScannerCompactBounds(
                stateLabel = "active camera",
                expected = expected,
                hasTorch = true,
            )

            scannerState.value = CompactScannerBoundsState.InvalidFeedback
            compose.waitForIdle()
            assertActiveScannerCompactBounds(
                stateLabel = "invalid QR",
                expected = expected,
                hasTorch = false,
                expectedFeedback = expected.invalidQrFeedback,
            )

            scannerState.value = CompactScannerBoundsState.UnsupportedFeedback
            compose.waitForIdle()
            assertActiveScannerCompactBounds(
                stateLabel = "unsupported QR",
                expected = expected,
                hasTorch = false,
                expectedFeedback = expected.unsupportedQrFeedback,
            )

            scannerState.value = CompactScannerBoundsState.PermissionPrompt
            compose.waitForIdle()
            assertPermissionScannerCompactBounds(
                stateLabel = "permission prompt",
                expected = expected,
                title = expected.permissionTitle,
                detail = expected.permissionDetail,
                action = expected.permissionAction,
            )

            scannerState.value = CompactScannerBoundsState.SettingsRecovery
            compose.waitForIdle()
            assertPermissionScannerCompactBounds(
                stateLabel = "settings recovery",
                expected = expected,
                title = expected.blockedPermissionTitle,
                detail = expected.blockedPermissionDetail,
                action = expected.settingsAction,
            )
        }
    }

    @Composable
    private fun LocalizedScannerContent(
        languageTag: String,
        fontScale: Float = 1f,
        content: @Composable () -> Unit,
    ) {
        val baseContext = LocalContext.current
        val localizedContext = remember(baseContext, languageTag, fontScale) {
            baseContext.localizedContext(languageTag, fontScale)
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
                unsupportedQrFeedback = localizedContext.getString(R.string.qr_scanner_feedback_unsupported),
                invalidQrFeedback = localizedContext.getString(R.string.qr_scanner_feedback_invalid),
                scanTarget = localizedContext.getString(R.string.qr_scanner_scan_target_accessibility),
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
                closeScanner = localizedContext.getString(R.string.qr_scanner_close_action),
                cancel = localizedContext.getString(R.string.cancel),
            )
        }
    }

    private fun Context.localizedContext(languageTag: String, fontScale: Float = 1f): Context {
        val locale = Locale.forLanguageTag(languageTag)
        val configuration = Configuration(resources.configuration)
        configuration.setLocale(locale)
        configuration.setLocales(LocaleList(locale))
        configuration.fontScale = fontScale
        return createConfigurationContext(configuration)
    }

    private fun hasHeading(): SemanticsMatcher {
        return SemanticsMatcher.expectValue(SemanticsProperties.Heading, Unit)
    }

    private fun assertActiveScannerCompactBounds(
        stateLabel: String,
        expected: ScannerLocaleExpectation,
        hasTorch: Boolean,
        expectedFeedback: String? = null,
    ) {
        val rootBounds = compose.onNodeWithTag(scannerCompactBoundsRootTestTag)
            .getUnclippedBoundsInRoot()
        val chromeBounds = compose.onNodeWithTag(PAIRING_QR_SCANNER_CHROME_TEST_TAG)
            .assertIsDisplayed()
            .getUnclippedBoundsInRoot()
        val titleBounds = compose.onNodeWithTag(PAIRING_QR_SCANNER_TITLE_TEST_TAG, useUnmergedTree = true)
            .assertIsDisplayed()
            .assert(hasHeading())
            .getUnclippedBoundsInRoot()
        val closeBounds = compose.onNodeWithTag(PAIRING_QR_SCANNER_CLOSE_BUTTON_TEST_TAG, useUnmergedTree = true)
            .assertIsDisplayed()
            .getUnclippedBoundsInRoot()
        val cameraBounds = compose.onNodeWithTag(PAIRING_QR_SCANNER_CAMERA_SURFACE_TEST_TAG)
            .assertIsDisplayed()
            .getUnclippedBoundsInRoot()
        val targetBounds = compose.onNodeWithTag(PAIRING_QR_SCANNER_TARGET_TEST_TAG, useUnmergedTree = true)
            .assertIsDisplayed()
            .getUnclippedBoundsInRoot()
        val instructionsBounds = compose.onNodeWithTag(
            PAIRING_QR_SCANNER_INSTRUCTIONS_TEST_TAG,
            useUnmergedTree = true,
        )
            .assertIsDisplayed()
            .getUnclippedBoundsInRoot()
        val detailBounds = compose.onNodeWithTag(PAIRING_QR_SCANNER_DETAIL_TEST_TAG, useUnmergedTree = true)
            .assertIsDisplayed()
            .getUnclippedBoundsInRoot()
        val cancelBounds = compose.onNodeWithTag(
            PAIRING_QR_SCANNER_CANCEL_BUTTON_TEST_TAG,
            useUnmergedTree = true,
        )
            .assertIsDisplayed()
            .getUnclippedBoundsInRoot()

        assertBoundsInside("$stateLabel ${expected.languageTag} scanner chrome", chromeBounds, rootBounds)
        assertBoundsInside("$stateLabel ${expected.languageTag} scanner title", titleBounds, rootBounds)
        assertBoundsInside("$stateLabel ${expected.languageTag} close action", closeBounds, rootBounds)
        assertBoundsInside("$stateLabel ${expected.languageTag} camera surface", cameraBounds, rootBounds)
        assertBoundsInside("$stateLabel ${expected.languageTag} scan target", targetBounds, cameraBounds)
        assertBoundsInside("$stateLabel ${expected.languageTag} instruction panel", instructionsBounds, rootBounds)
        assertBoundsInside("$stateLabel ${expected.languageTag} detail", detailBounds, instructionsBounds)
        assertBoundsInside("$stateLabel ${expected.languageTag} cancel action", cancelBounds, instructionsBounds)
        assertFalse(
            "$stateLabel ${expected.languageTag} title should not overlap close action.",
            boundsOverlap(titleBounds, closeBounds),
        )
        assertFalse(
            "$stateLabel ${expected.languageTag} scan target should not overlap instruction panel. " +
                "target=$targetBounds instructions=$instructionsBounds",
            boundsOverlap(targetBounds, instructionsBounds),
        )
        if (hasTorch) {
            val torchBounds = compose.onNodeWithTag(
                PAIRING_QR_FLASHLIGHT_BUTTON_TEST_TAG,
                useUnmergedTree = true,
            )
                .assertIsDisplayed()
                .getUnclippedBoundsInRoot()
            assertBoundsInside("$stateLabel ${expected.languageTag} torch action", torchBounds, rootBounds)
            assertFalse(
                "$stateLabel ${expected.languageTag} title should not overlap torch action.",
                boundsOverlap(titleBounds, torchBounds),
            )
            assertFalse(
                "$stateLabel ${expected.languageTag} close and torch actions should not overlap.",
                boundsOverlap(closeBounds, torchBounds),
            )
        }
        expectedFeedback?.let { feedback ->
            val feedbackBounds = compose.onNodeWithTag(
                PAIRING_QR_SCANNER_FEEDBACK_TEST_TAG,
                useUnmergedTree = true,
            )
                .assertIsDisplayed()
                .assert(SemanticsMatcher.expectValue(SemanticsProperties.ContentDescription, listOf(feedback)))
                .getUnclippedBoundsInRoot()
            assertBoundsInside("$stateLabel ${expected.languageTag} feedback", feedbackBounds, instructionsBounds)
            assertFalse(
                "$stateLabel ${expected.languageTag} detail and feedback should not overlap.",
                boundsOverlap(detailBounds, feedbackBounds),
            )
            assertFalse(
                "$stateLabel ${expected.languageTag} feedback and cancel should not overlap.",
                boundsOverlap(feedbackBounds, cancelBounds),
            )
        }
    }

    private fun assertPermissionScannerCompactBounds(
        stateLabel: String,
        expected: ScannerLocaleExpectation,
        title: String,
        detail: String,
        action: String,
    ) {
        val rootBounds = compose.onNodeWithTag(scannerCompactBoundsRootTestTag)
            .getUnclippedBoundsInRoot()
        val chromeBounds = compose.onNodeWithTag(PAIRING_QR_SCANNER_CHROME_TEST_TAG)
            .assertIsDisplayed()
            .getUnclippedBoundsInRoot()
        val titleBounds = compose.onNodeWithTag(PAIRING_QR_SCANNER_TITLE_TEST_TAG, useUnmergedTree = true)
            .assertIsDisplayed()
            .assert(hasHeading())
            .getUnclippedBoundsInRoot()
        val closeBounds = compose.onNodeWithTag(PAIRING_QR_SCANNER_CLOSE_BUTTON_TEST_TAG, useUnmergedTree = true)
            .assertIsDisplayed()
            .getUnclippedBoundsInRoot()
        val panelBounds = compose.onNodeWithTag(PAIRING_QR_SCANNER_PERMISSION_PANEL_TEST_TAG, useUnmergedTree = true)
            .assertIsDisplayed()
            .getUnclippedBoundsInRoot()
        val permissionTitleBounds = compose.onNodeWithTag(
            PAIRING_QR_SCANNER_PERMISSION_TITLE_TEST_TAG,
            useUnmergedTree = true,
        )
            .assertIsDisplayed()
            .assert(hasHeading())
            .getUnclippedBoundsInRoot()
        val permissionDetailBounds = compose.onNodeWithTag(
            PAIRING_QR_SCANNER_PERMISSION_DETAIL_TEST_TAG,
            useUnmergedTree = true,
        )
            .assertIsDisplayed()
            .getUnclippedBoundsInRoot()
        val actionBounds = compose.onNodeWithTag(
            PAIRING_QR_SCANNER_PERMISSION_ACTION_TEST_TAG,
            useUnmergedTree = true,
        )
            .assertIsDisplayed()
            .getUnclippedBoundsInRoot()
        val cancelBounds = compose.onNodeWithTag(
            PAIRING_QR_SCANNER_PERMISSION_CANCEL_BUTTON_TEST_TAG,
            useUnmergedTree = true,
        )
            .assertIsDisplayed()
            .getUnclippedBoundsInRoot()

        compose.onNodeWithText(title).assertIsDisplayed()
        compose.onNodeWithText(detail).assertIsDisplayed()
        compose.onNodeWithText(action).assertIsDisplayed()
        assertBoundsInside("$stateLabel ${expected.languageTag} scanner chrome", chromeBounds, rootBounds)
        assertBoundsInside("$stateLabel ${expected.languageTag} scanner title", titleBounds, rootBounds)
        assertBoundsInside("$stateLabel ${expected.languageTag} close action", closeBounds, rootBounds)
        assertBoundsInside("$stateLabel ${expected.languageTag} permission panel", panelBounds, rootBounds)
        assertBoundsInside("$stateLabel ${expected.languageTag} permission title", permissionTitleBounds, panelBounds)
        assertBoundsInside("$stateLabel ${expected.languageTag} permission detail", permissionDetailBounds, panelBounds)
        assertBoundsInside("$stateLabel ${expected.languageTag} permission action", actionBounds, panelBounds)
        assertBoundsInside("$stateLabel ${expected.languageTag} permission cancel", cancelBounds, panelBounds)
        assertFalse(
            "$stateLabel ${expected.languageTag} title should not overlap close action.",
            boundsOverlap(titleBounds, closeBounds),
        )
        assertFalse(
            "$stateLabel ${expected.languageTag} permission title and detail should not overlap.",
            boundsOverlap(permissionTitleBounds, permissionDetailBounds),
        )
        assertFalse(
            "$stateLabel ${expected.languageTag} permission detail and action should not overlap.",
            boundsOverlap(permissionDetailBounds, actionBounds),
        )
        assertFalse(
            "$stateLabel ${expected.languageTag} permission action and cancel should not overlap.",
            boundsOverlap(actionBounds, cancelBounds),
        )
    }

    private fun assertBoundsInside(label: String, bounds: DpRect, container: DpRect) {
        assertTrue(
            "$label should stay inside compact scanner root horizontally. bounds=$bounds container=$container",
            bounds.left >= container.left,
        )
        assertTrue(
            "$label should stay inside compact scanner root horizontally. bounds=$bounds container=$container",
            bounds.right <= container.right,
        )
        assertTrue(
            "$label should stay inside compact scanner root vertically. bounds=$bounds container=$container",
            bounds.top >= container.top,
        )
        assertTrue(
            "$label should stay inside compact scanner root vertically. bounds=$bounds container=$container",
            bounds.bottom <= container.bottom,
        )
    }

    private fun boundsOverlap(first: DpRect, second: DpRect): Boolean {
        val overlapsHorizontally = first.left < second.right && second.left < first.right
        val overlapsVertically = first.top < second.bottom && second.top < first.bottom
        return overlapsHorizontally && overlapsVertically
    }

    private class RecordingCameraPermissionPlatform :
        PairingQrCameraPermissionPlatform {
        var cameraPermissionGranted = false
        var cameraPermissionRationale = false

        override fun hasCameraPermission(context: Context): Boolean {
            return cameraPermissionGranted
        }

        override fun shouldShowCameraPermissionRationale(
            activity: ComponentActivity?,
        ): Boolean {
            return cameraPermissionRationale
        }
    }

    private class ManualLifecycleOwner : LifecycleOwner {
        private val registry = LifecycleRegistry(this)

        override val lifecycle: Lifecycle
            get() = registry

        fun handle(event: Lifecycle.Event) {
            registry.handleLifecycleEvent(event)
        }
    }

    private class RecordingPermissionActivityResultRegistry :
        ActivityResultRegistry() {
        var launchCount = 0
            private set
        private var latestRequestCode: Int? = null

        override fun <I, O> onLaunch(
            requestCode: Int,
            contract: ActivityResultContract<I, O>,
            input: I,
            options: ActivityOptionsCompat?,
        ) {
            latestRequestCode = requestCode
            launchCount += 1
        }

        fun dispatchPermissionResult(granted: Boolean) {
            check(
                dispatchResult(
                    checkNotNull(latestRequestCode),
                    granted,
                ),
            )
        }
    }

    private class RecordingActivityResultRegistryOwner(
        registry: ActivityResultRegistry,
    ) : ActivityResultRegistryOwner {
        override val activityResultRegistry: ActivityResultRegistry = registry
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
        val unsupportedQrFeedback: String,
        val invalidQrFeedback: String,
        val scanTarget: String,
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
        val closeScanner: String,
        val cancel: String,
    )

    private enum class CompactScannerState {
        ActiveCamera,
        PermissionPrompt,
        SettingsRecovery,
    }

    private enum class CompactScannerBoundsState {
        ActiveCamera,
        InvalidFeedback,
        UnsupportedFeedback,
        PermissionPrompt,
        SettingsRecovery,
    }

    private companion object {
        const val CAMERA_PREVIEW_TAG = "pairing_qr_camera_preview"
        const val scannerCompactBoundsRootTestTag = "pairing_qr_scanner_compact_bounds_root"
    }
}
