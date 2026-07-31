package com.localagentbridge.android

import android.Manifest
import android.content.Context
import androidx.activity.ComponentActivity
import androidx.activity.compose.LocalActivityResultRegistryOwner
import androidx.activity.result.ActivityResultRegistry
import androidx.activity.result.ActivityResultRegistryOwner
import androidx.activity.result.contract.ActivityResultContract
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.core.app.ActivityOptionsCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.LifecycleRegistry
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config

@RunWith(AndroidJUnit4::class)
@Config(sdk = [26, 30, 33, 36])
class PairingQrCameraPermissionControllerHostApiMatrixTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun controllerHostRunsDenialRegrantRevocationAndResumeLifecycle() {
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
                checkNotNull(latestController).requestPermission()
            }
            compose.waitForIdle()
            assertEquals(2, resultRegistry.launchCount)
            assertEquals(
                PairingQrCameraPermissionStage.RequestInFlight,
                checkNotNull(latestController).stage,
            )

            compose.runOnIdle {
                platform.cameraPermissionGranted = true
                platform.cameraPermissionRationale = false
                resultRegistry.dispatchPermissionResult(granted = true)
            }
            compose.waitForIdle()
            assertEquals(
                PairingQrCameraPermissionStage.Granted,
                checkNotNull(latestController).stage,
            )

            compose.runOnIdle {
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
            assertEquals(2, resultRegistry.launchCount)
        } finally {
            context.deleteSharedPreferences(preferencesName)
        }
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
            check(contract is ActivityResultContracts.RequestPermission)
            check(input == Manifest.permission.CAMERA)
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
}
