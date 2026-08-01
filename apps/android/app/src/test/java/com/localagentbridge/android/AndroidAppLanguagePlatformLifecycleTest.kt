package com.localagentbridge.android

import android.app.Application
import android.app.LocaleManager
import android.os.Build
import android.os.LocaleList
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.test.core.app.ActivityScenario
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.localagentbridge.android.runtime.ANDROID_APP_LANGUAGE_PLATFORM_MIGRATION_VERSION
import com.localagentbridge.android.runtime.APP_LANGUAGE_SOURCE_IN_APP
import com.localagentbridge.android.runtime.APP_LANGUAGE_SOURCE_SYSTEM
import com.localagentbridge.android.runtime.PersistedRuntimeData
import com.localagentbridge.android.runtime.RuntimeAppLanguage
import com.localagentbridge.android.runtime.RuntimeLocalStore
import com.localagentbridge.android.runtime.withAppLanguageTag
import kotlinx.serialization.json.Json
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotSame
import org.junit.Assert.assertNull
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config

@RunWith(AndroidJUnit4::class)
class AndroidAppLanguagePlatformLifecycleTest {
    private val application =
        ApplicationProvider.getApplicationContext<Application>()
    private val json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
        encodeDefaults = true
    }

    @get:Rule
    val compose = createAndroidComposeRule<MainActivity>()

    @After
    fun clearPlatformLocaleAndRuntimeStore() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            localeManager().applicationLocales = LocaleList.getEmptyLocaleList()
        }
        application.deleteSharedPreferences(RUNTIME_STORE_NAME)
    }

    @Test
    @Config(sdk = [32], qualifiers = "en")
    fun api32ColdLaunchAndRecreationPreserveStoredExplicitLanguage() {
        closeInitialActivityAndResetState()
        runtimeStore().save(
            PersistedRuntimeData().withAppLanguageTag("fr-FR"),
            commitToDisk = true,
        )

        val scenario = ActivityScenario.launch(MainActivity::class.java)
        try {
            awaitStoredLanguage("fr", APP_LANGUAGE_SOURCE_IN_APP)
            assertNull(androidAppLocaleOverrideLanguageTag(application))
            assertPlatformMigrationNotStarted()

            lateinit var firstActivity: MainActivity
            scenario.onActivity { activity ->
                firstActivity = activity
            }
            scenario.recreate()
            compose.waitForIdle()

            lateinit var recreatedActivity: MainActivity
            scenario.onActivity { activity ->
                recreatedActivity = activity
            }
            assertNotSame(firstActivity, recreatedActivity)
            assertStoredLanguage("fr", APP_LANGUAGE_SOURCE_IN_APP)
            assertNull(androidAppLocaleOverrideLanguageTag(application))
            assertPlatformMigrationNotStarted()
        } finally {
            scenario.close()
        }
    }

    @Test
    @Config(sdk = [33], qualifiers = "en")
    fun api33ExternalApplicationLocaleWinsAcrossColdLaunchAndRecreation() {
        closeInitialActivityAndResetState()
        runtimeStore().save(
            PersistedRuntimeData().withAppLanguageTag("fr-FR"),
            commitToDisk = true,
        )

        val migrationScenario = ActivityScenario.launch(MainActivity::class.java)
        try {
            awaitStoredLanguage("fr", APP_LANGUAGE_SOURCE_IN_APP)
            assertPlatformLanguage("fr")
            assertPlatformMigrationCompleted()

            lateinit var firstActivity: MainActivity
            migrationScenario.onActivity { activity ->
                firstActivity = activity
            }
            migrationScenario.recreate()
            compose.waitForIdle()

            lateinit var recreatedActivity: MainActivity
            migrationScenario.onActivity { activity ->
                recreatedActivity = activity
            }
            assertNotSame(firstActivity, recreatedActivity)
            assertStoredLanguage("fr", APP_LANGUAGE_SOURCE_IN_APP)
            assertPlatformLanguage("fr")
            assertPlatformMigrationCompleted()
        } finally {
            migrationScenario.close()
        }

        val migratedColdScenario = ActivityScenario.launch(MainActivity::class.java)
        try {
            awaitStoredLanguage("fr", APP_LANGUAGE_SOURCE_IN_APP)
            assertPlatformLanguage("fr")
            assertPlatformMigrationCompleted()

            localeManager().applicationLocales = LocaleList.getEmptyLocaleList()
            assertEquals(0, localeManager().applicationLocales.size())

            migratedColdScenario.recreate()
            awaitStoredLanguage("en", APP_LANGUAGE_SOURCE_SYSTEM)
            assertEquals(0, localeManager().applicationLocales.size())
            assertPlatformMigrationCompleted()
        } finally {
            migratedColdScenario.close()
        }

        val clearedColdScenario = ActivityScenario.launch(MainActivity::class.java)
        try {
            awaitStoredLanguage("en", APP_LANGUAGE_SOURCE_SYSTEM)
            assertEquals(0, localeManager().applicationLocales.size())
            assertPlatformMigrationCompleted()
        } finally {
            clearedColdScenario.close()
        }

        localeManager().applicationLocales = LocaleList.forLanguageTags("ko-KR")
        val externalOverrideScenario = ActivityScenario.launch(MainActivity::class.java)
        try {
            awaitStoredLanguage("ko", APP_LANGUAGE_SOURCE_IN_APP)
            assertPlatformLanguage("ko")
            assertPlatformMigrationCompleted()

            externalOverrideScenario.recreate()
            compose.waitForIdle()
            assertStoredLanguage("ko", APP_LANGUAGE_SOURCE_IN_APP)
            assertPlatformLanguage("ko")
            assertPlatformMigrationCompleted()
        } finally {
            externalOverrideScenario.close()
        }
    }

    @Test
    @Config(sdk = [36], qualifiers = "en")
    fun api36ExplicitEnglishAndFollowSystemConvergeAcrossRecreation() {
        closeInitialActivityAndResetState()
        runtimeStore().save(
            PersistedRuntimeData().withAppLanguageTag("fr-FR"),
            commitToDisk = true,
        )

        synchronizeAndroidAppLocaleOverride(
            context = application,
            selectedLanguageTag = "en-US",
        )
        assertPlatformLanguage("en")

        val scenario = ActivityScenario.launch(MainActivity::class.java)
        try {
            awaitStoredLanguage("en", APP_LANGUAGE_SOURCE_IN_APP)
            assertPlatformLanguage("en")
            assertPlatformMigrationCompleted()

            scenario.recreate()
            compose.waitForIdle()
            assertStoredLanguage("en", APP_LANGUAGE_SOURCE_IN_APP)
            assertPlatformLanguage("en")
            assertPlatformMigrationCompleted()

            synchronizeAndroidAppLocaleOverride(
                context = application,
                selectedLanguageTag = null,
            )
            assertEquals(0, localeManager().applicationLocales.size())

            scenario.recreate()
            awaitStoredLanguage("en", APP_LANGUAGE_SOURCE_SYSTEM)
            assertEquals(0, localeManager().applicationLocales.size())
            assertPlatformMigrationCompleted()
        } finally {
            scenario.close()
        }

        val coldScenario = ActivityScenario.launch(MainActivity::class.java)
        try {
            awaitStoredLanguage("en", APP_LANGUAGE_SOURCE_SYSTEM)
            assertEquals(0, localeManager().applicationLocales.size())
            assertPlatformMigrationCompleted()
        } finally {
            coldScenario.close()
        }
    }

    private fun closeInitialActivityAndResetState() {
        compose.waitForIdle()
        compose.activityRule.scenario.close()
        application.deleteSharedPreferences(RUNTIME_STORE_NAME)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            localeManager().applicationLocales = LocaleList.getEmptyLocaleList()
        }
    }

    private fun runtimeStore(): RuntimeLocalStore {
        return RuntimeLocalStore(application, json)
    }

    private fun awaitStoredLanguage(
        expectedLanguageTag: String,
        expectedLanguageSource: String,
    ) {
        compose.waitUntil(timeoutMillis = 5_000) {
            val data = runtimeStore().load()
            data.appLanguageTag == expectedLanguageTag &&
                data.appLanguageSource == expectedLanguageSource
        }
        assertStoredLanguage(expectedLanguageTag, expectedLanguageSource)
    }

    private fun assertStoredLanguage(
        expectedLanguageTag: String,
        expectedLanguageSource: String,
    ) {
        val data = runtimeStore().load()
        assertEquals(expectedLanguageTag, data.appLanguageTag)
        assertEquals(expectedLanguageSource, data.appLanguageSource)
    }

    private fun assertPlatformMigrationCompleted() {
        val data = runtimeStore().load()
        assertEquals(
            ANDROID_APP_LANGUAGE_PLATFORM_MIGRATION_VERSION,
            data.androidAppLanguagePlatformMigrationVersion,
        )
        assertNull(data.pendingAndroidAppLanguagePlatformMigrationTag)
    }

    private fun assertPlatformMigrationNotStarted() {
        val data = runtimeStore().load()
        assertEquals(0, data.androidAppLanguagePlatformMigrationVersion)
        assertNull(data.pendingAndroidAppLanguagePlatformMigrationTag)
    }

    private fun localeManager(): LocaleManager {
        check(Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU)
        return requireNotNull(application.getSystemService(LocaleManager::class.java))
    }

    private fun assertPlatformLanguage(expectedLanguageTag: String) {
        assertEquals(
            expectedLanguageTag,
            RuntimeAppLanguage.supportedLanguageTagOrNull(
                androidAppLocaleOverrideLanguageTag(application),
            ),
        )
        assertEquals(1, localeManager().applicationLocales.size())
    }

    private companion object {
        const val RUNTIME_STORE_NAME = "runtime_local_store"
    }
}
