package com.localagentbridge.android

import android.Manifest
import android.app.Application
import android.content.Context
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.core.app.ActivityScenario
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.localagentbridge.android.ui.SETTINGS_QR_PAIRING_SCAN_BUTTON_TEST_TAG
import org.junit.After
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotSame
import org.junit.Assert.assertNull
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config

@RunWith(AndroidJUnit4::class)
@Config(sdk = [26, 30, 33, 36])
class PairingQrCameraPermissionActivityRecreationTest {
    private val application =
        ApplicationProvider.getApplicationContext<Application>()
    private val permissionPreferences =
        application.getSharedPreferences(
            PAIRING_QR_CAMERA_PERMISSION_PREFERENCES,
            Context.MODE_PRIVATE,
        ).also { preferences ->
            check(preferences.edit().clear().commit())
        }
    init {
        shadowOf(application).denyPermissions(Manifest.permission.CAMERA)
    }

    @get:Rule
    val compose = createAndroidComposeRule<MainActivity>()

    @After
    fun deleteTestPreferences() {
        application.deleteSharedPreferences(
            PAIRING_QR_CAMERA_PERMISSION_PREFERENCES,
        )
    }

    @Test
    fun activityScenarioRecreateRestoresRecordedRequestWithoutRelaunch() {
        compose.waitForIdle()
        compose.onNodeWithTag(SETTINGS_QR_PAIRING_SCAN_BUTTON_TEST_TAG)
            .assertIsDisplayed()
            .performClick()
        compose.waitForIdle()

        val firstActivity = compose.activity
        compose.onNodeWithTag(PAIRING_QR_SCANNER_CHROME_TEST_TAG)
            .assertIsDisplayed()
        compose.onNodeWithTag(
            PAIRING_QR_SCANNER_PERMISSION_ACTION_TEST_TAG,
        ).assertIsNotEnabled()
        val firstPermissionRequest =
            shadowOf(firstActivity).lastRequestedPermission
        assertArrayEquals(
            arrayOf(Manifest.permission.CAMERA),
            firstPermissionRequest.requestedPermissions,
        )
        assertEquals(
            PairingQrCameraPermissionRequestRecord.Recorded,
            readPairingQrCameraPermissionRequestRecord(
                permissionPreferences,
            ),
        )

        compose.activityRule.scenario.recreate()
        compose.waitForIdle()

        val recreatedActivity = compose.activity
        assertNotSame(firstActivity, recreatedActivity)
        compose.onNodeWithTag(PAIRING_QR_SCANNER_CHROME_TEST_TAG)
            .assertIsDisplayed()
        compose.onNodeWithTag(
            PAIRING_QR_SCANNER_PERMISSION_ACTION_TEST_TAG,
        ).assertIsEnabled()
        compose.onNodeWithText(
            application.getString(
                R.string.qr_scanner_permission_blocked_title,
            ),
        ).assertIsDisplayed()
        compose.onNodeWithText(
            application.getString(
                R.string.qr_scanner_permission_settings_action,
            ),
        ).assertIsDisplayed()
        assertNull(shadowOf(recreatedActivity).lastRequestedPermission)
        assertEquals(
            PairingQrCameraPermissionRequestRecord.Recorded,
            readPairingQrCameraPermissionRequestRecord(
                permissionPreferences,
            ),
        )
    }

    @Test
    fun coldActivityLaunchRestoresRecordedRequestWithoutRelaunch() {
        compose.waitForIdle()
        compose.onNodeWithTag(SETTINGS_QR_PAIRING_SCAN_BUTTON_TEST_TAG)
            .assertIsDisplayed()
            .performClick()
        compose.waitForIdle()

        val firstActivity = compose.activity
        assertArrayEquals(
            arrayOf(Manifest.permission.CAMERA),
            shadowOf(firstActivity)
                .lastRequestedPermission
                .requestedPermissions,
        )
        assertEquals(
            PairingQrCameraPermissionRequestRecord.Recorded,
            readPairingQrCameraPermissionRequestRecord(
                permissionPreferences,
            ),
        )

        compose.activityRule.scenario.close()
        val coldScenario = ActivityScenario.launch(MainActivity::class.java)
        try {
            compose.waitForIdle()
            compose.onNodeWithTag(
                SETTINGS_QR_PAIRING_SCAN_BUTTON_TEST_TAG,
            )
                .assertIsDisplayed()
                .performClick()
            compose.waitForIdle()

            lateinit var coldActivity: MainActivity
            coldScenario.onActivity { activity ->
                coldActivity = activity
            }
            assertNotSame(firstActivity, coldActivity)
            compose.onNodeWithTag(PAIRING_QR_SCANNER_CHROME_TEST_TAG)
                .assertIsDisplayed()
            compose.onNodeWithTag(
                PAIRING_QR_SCANNER_PERMISSION_ACTION_TEST_TAG,
            ).assertIsEnabled()
            compose.onNodeWithText(
                application.getString(
                    R.string.qr_scanner_permission_blocked_title,
                ),
            ).assertIsDisplayed()
            compose.onNodeWithText(
                application.getString(
                    R.string.qr_scanner_permission_settings_action,
                ),
            ).assertIsDisplayed()
            assertNull(shadowOf(coldActivity).lastRequestedPermission)
            assertEquals(
                PairingQrCameraPermissionRequestRecord.Recorded,
                readPairingQrCameraPermissionRequestRecord(
                    permissionPreferences,
                ),
            )
        } finally {
            coldScenario.close()
        }
    }

    @Test
    fun coldActivityLaunchRecoversLaunchPendingWithoutAutomaticRelaunch() {
        val initialActivity = compose.activity
        compose.activityRule.scenario.close()
        check(
            persistPairingQrCameraPermissionRequestRecord(
                preferences = permissionPreferences,
                requestRecord =
                    PairingQrCameraPermissionRequestRecord.LaunchPending,
            ),
        )

        val coldScenario = ActivityScenario.launch(MainActivity::class.java)
        try {
            compose.waitForIdle()
            compose.onNodeWithTag(
                SETTINGS_QR_PAIRING_SCAN_BUTTON_TEST_TAG,
            )
                .assertIsDisplayed()
                .performClick()
            compose.waitForIdle()

            lateinit var coldActivity: MainActivity
            coldScenario.onActivity { activity ->
                coldActivity = activity
            }
            assertNotSame(initialActivity, coldActivity)
            compose.onNodeWithTag(PAIRING_QR_SCANNER_CHROME_TEST_TAG)
                .assertIsDisplayed()
            compose.onNodeWithTag(
                PAIRING_QR_SCANNER_PERMISSION_ACTION_TEST_TAG,
            ).assertIsEnabled()
            compose.onNodeWithText(
                application.getString(
                    R.string.qr_scanner_permission_title,
                ),
            ).assertIsDisplayed()
            compose.onNodeWithText(
                application.getString(
                    R.string.qr_scanner_permission_action,
                ),
            ).assertIsDisplayed()
            assertNull(shadowOf(coldActivity).lastRequestedPermission)
            assertEquals(
                PairingQrCameraPermissionRequestRecord.RetryRequired,
                readPairingQrCameraPermissionRequestRecord(
                    permissionPreferences,
                ),
            )
        } finally {
            coldScenario.close()
        }
    }
}
