package com.localagentbridge.android.runtime

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import com.localagentbridge.android.core.pairing.DurableRelaySecretStore
import com.localagentbridge.android.core.pairing.RelaySecretStore
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.json.Json
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.assertThrows
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class RuntimeLocalStoreTest {
    private val json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
        encodeDefaults = true
    }
    private lateinit var context: Context

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        preferences().edit().clear().commit()
    }

    @After
    fun tearDown() {
        preferences().edit().clear().commit()
    }

    @Test
    // Retained because the G7 Android testcase manifest pins this historical identity.
    fun emptyAndCorruptStoresLoadAsDefaultsAndRemainWritable() {
        val emptySecrets = RecordingRelaySecretStore()
        val emptyStore = RuntimeLocalStore(context, json, emptySecrets)

        assertEquals(PersistedRuntimeData(), emptyStore.load())

        emptyStore.save(PersistedRuntimeData(composerDraft = "after-empty"))
        assertEquals("after-empty", emptyStore.load().composerDraft)

        assertIncompatibleRawIsPreserved(
            raw = "{not-json",
            expectedIssue = RuntimeLocalDataCompatibilityIssue.InvalidFormat,
        )
        assertIncompatibleRawIsPreserved(
            raw = "[]",
            expectedIssue = RuntimeLocalDataCompatibilityIssue.InvalidFormat,
        )
        assertIncompatibleRawIsPreserved(
            raw = "null",
            expectedIssue = RuntimeLocalDataCompatibilityIssue.InvalidFormat,
        )

        preferences().edit()
            .putString(STORE_KEY_FOR_TEST, """{"composerDraft":"legacy-v0"}""")
            .commit()
        val legacyStore = RuntimeLocalStore(context, json, RecordingRelaySecretStore())
        val legacyResult = legacyStore.loadResult()

        assertNull(legacyResult.compatibilityIssue)
        assertEquals("legacy-v0", legacyResult.data.composerDraft)

        legacyStore.save(legacyResult.data.copy(composerDraft = "legacy-upgraded"))
        val upgradedLegacyRaw = requireNotNull(
            preferences().getString(STORE_KEY_FOR_TEST, null),
        )
        assertTrue(upgradedLegacyRaw.contains("\"version\":1"))
        assertEquals("legacy-upgraded", legacyStore.load().composerDraft)

        listOf(
            """{"version":2,"future_sentinel":"keep-future"}""" to
                RuntimeLocalDataCompatibilityIssue.UnsupportedVersion,
            """{"version":9223372036854775808,"future_sentinel":"keep-huge"}""" to
                RuntimeLocalDataCompatibilityIssue.UnsupportedVersion,
            """{"version":0,"future_sentinel":"keep-zero"}""" to
                RuntimeLocalDataCompatibilityIssue.InvalidVersion,
            """{"version":-1,"future_sentinel":"keep-negative"}""" to
                RuntimeLocalDataCompatibilityIssue.InvalidVersion,
            """{"version":"1","future_sentinel":"keep-string"}""" to
                RuntimeLocalDataCompatibilityIssue.InvalidVersion,
            """{"version":1.0,"future_sentinel":"keep-float"}""" to
                RuntimeLocalDataCompatibilityIssue.InvalidVersion,
            """{"version":true,"future_sentinel":"keep-boolean"}""" to
                RuntimeLocalDataCompatibilityIssue.InvalidVersion,
            """{"version":1,"version":2,"future_sentinel":"keep-duplicate"}""" to
                RuntimeLocalDataCompatibilityIssue.InvalidVersion,
            """{"metadata":{"x":1,"x":2},"version":2,"version":1,"future_sentinel":"keep-all"}""" to
                RuntimeLocalDataCompatibilityIssue.InvalidFormat,
            """{"version":1,"metadata":{"x":1,"x":2},"future_sentinel":"keep-nested"}""" to
                RuntimeLocalDataCompatibilityIssue.InvalidFormat,
        ).forEach { (raw, expectedIssue) ->
            assertIncompatibleRawIsPreserved(raw, expectedIssue)
        }
    }

    @Test
    // Retained because the G7 Android testcase manifest pins this historical identity.
    fun wrongTypedPreferenceRecoversToDefaultsAndRemainsWritable() {
        preferences().edit().putInt(STORE_KEY_FOR_TEST, 7).commit()
        val store = RuntimeLocalStore(context, json, RecordingRelaySecretStore())

        val result = store.loadResult()
        assertEquals(PersistedRuntimeData(), result.data)
        assertEquals(RuntimeLocalDataCompatibilityIssue.InvalidFormat, result.compatibilityIssue)
        assertTrue(preferences().contains(STORE_KEY_FOR_TEST))
        assertEquals(7, preferences().getInt(STORE_KEY_FOR_TEST, -1))

        assertThrows(IllegalStateException::class.java) {
            store.save(PersistedRuntimeData(composerDraft = "must-not-overwrite"))
        }
        assertEquals(7, preferences().getInt(STORE_KEY_FOR_TEST, -1))
    }

    @Test
    fun processRecreationLoadsPendingSecretAndReplacementRemovesPreviousHandle() {
        val secrets = RecordingRelaySecretStore()
        val firstStore = RuntimeLocalStore(context, json, secrets)
        firstStore.save(runtimeDataWithPendingRelay("first", "secret-first"))
        val firstRef = requireNotNull(diskData().pendingPairingRoute?.relaySecretRef)

        val recreatedStore = RuntimeLocalStore(context, json, secrets)
        val restored = recreatedStore.load()

        assertEquals("secret-first", restored.pendingPairingRoute?.relaySecret)
        assertEquals(firstRef, restored.pendingPairingRoute?.relaySecretRef)

        recreatedStore.save(runtimeDataWithPendingRelay("second", "secret-second"))
        val secondRef = requireNotNull(diskData().pendingPairingRoute?.relaySecretRef)

        assertFalse(firstRef == secondRef)
        assertEquals(listOf(firstRef), secrets.removedHandles)
        assertNull(secrets.readSecret(firstRef))
        assertEquals("secret-second", secrets.readSecret(secondRef))
    }

    @Test
    fun durableSaveConfirmsSecretWriteMetadataAndOldSecretCleanup() {
        val secrets = RecordingRelaySecretStore()
        val store = RuntimeLocalStore(context, json, secrets)

        store.save(
            data = runtimeDataWithPendingRelay("durable-first", "secret-durable-first"),
            commitToDisk = true,
        )
        val firstRef = requireNotNull(diskData().pendingPairingRoute?.relaySecretRef)
        store.save(
            data = runtimeDataWithPendingRelay("durable-second", "secret-durable-second"),
            commitToDisk = true,
        )
        val secondRef = requireNotNull(diskData().pendingPairingRoute?.relaySecretRef)

        assertEquals(listOf(firstRef, secondRef), secrets.durablySavedHandles)
        assertEquals(listOf(firstRef), secrets.durablyRemovedHandles)
        assertNull(secrets.readSecret(firstRef))
        assertEquals("secret-durable-second", secrets.readSecret(secondRef))
        assertEquals("secret-durable-second", store.load().pendingPairingRoute?.relaySecret)
    }

    @Test
    fun durableSaveRejectsSecretStoreWithoutConfirmationContract() {
        val store = RuntimeLocalStore(context, json, NonDurableRelaySecretStore())

        val error = assertThrows(IllegalStateException::class.java) {
            store.save(
                data = runtimeDataWithPendingRelay("non-durable", "secret-non-durable"),
                commitToDisk = true,
            )
        }

        assertTrue(error.message.orEmpty().contains("durable relay secret store"))
        assertNull(preferences().getString(STORE_KEY_FOR_TEST, null))
    }

    @Test
    fun durableMetadataFailureCompensatesNewSecretBeforeReturningFailure() {
        val secrets = RecordingRelaySecretStore()
        val store = RuntimeLocalStore(
            context = context,
            json = json,
            relaySecretStore = secrets,
            durableMetadataCommit = { false },
        )

        val error = assertThrows(IllegalStateException::class.java) {
            store.save(
                data = runtimeDataWithPendingRelay("metadata-failure", "secret-metadata-failure"),
                commitToDisk = true,
            )
        }

        assertTrue(error.message.orEmpty().contains("metadata persistence failed"))
        assertEquals(1, secrets.durablySavedHandles.size)
        assertEquals(secrets.durablySavedHandles, secrets.durablyRemovedHandles)
        assertTrue(secrets.storedHandles.isEmpty())
        assertNull(preferences().getString(STORE_KEY_FOR_TEST, null))
    }

    @Test
    fun durableCleanupFailureRetainsJournalAndRetriesOnNextBarrier() {
        val secrets = RecordingRelaySecretStore()
        val store = RuntimeLocalStore(context, json, secrets)
        val firstData = runtimeDataWithPendingRelay("cleanup-first", "secret-cleanup-first")
        val secondData = runtimeDataWithPendingRelay("cleanup-second", "secret-cleanup-second")
        store.save(firstData, commitToDisk = true)
        val firstReference = requireNotNull(diskData().pendingPairingRoute?.relaySecretRef)
        secrets.failNextDurableRemoval = true

        val error = assertThrows(IllegalStateException::class.java) {
            store.save(secondData, commitToDisk = true)
        }

        assertTrue(error.message.orEmpty().contains("secret cleanup failed"))
        val secondReference = requireNotNull(diskData().pendingPairingRoute?.relaySecretRef)
        assertTrue(firstReference != secondReference)
        assertEquals("secret-cleanup-first", secrets.readSecret(firstReference))
        assertEquals(
            setOf(firstReference),
            preferences().getStringSet(PENDING_RELAY_SECRET_CLEANUP_KEY_FOR_TEST, emptySet()),
        )

        store.save(secondData, commitToDisk = true)

        assertNull(secrets.readSecret(firstReference))
        assertEquals("secret-cleanup-second", secrets.readSecret(secondReference))
        assertTrue(
            preferences()
                .getStringSet(PENDING_RELAY_SECRET_CLEANUP_KEY_FOR_TEST, emptySet())
                .orEmpty()
                .isEmpty(),
        )
        assertEquals(listOf(firstReference, firstReference), secrets.durablyRemovedHandles)
    }

    @Test
    fun sameRouteSecretReplacementMetadataFailurePreservesPreviousSecret() {
        val secrets = RecordingRelaySecretStore()
        var failNextMetadataCommit = false
        val store = RuntimeLocalStore(
            context = context,
            json = json,
            relaySecretStore = secrets,
            durableMetadataCommit = { editor ->
                if (failNextMetadataCommit) {
                    failNextMetadataCommit = false
                    false
                } else {
                    editor.commit()
                }
            },
        )
        store.save(
            runtimeDataWithPendingRelay("same-route", "secret-before-failure"),
            commitToDisk = true,
        )
        val previousReference = requireNotNull(diskData().pendingPairingRoute?.relaySecretRef)
        failNextMetadataCommit = true

        val error = assertThrows(IllegalStateException::class.java) {
            store.save(
                runtimeDataWithPendingRelay("same-route", "secret-after-failure"),
                commitToDisk = true,
            )
        }

        assertTrue(error.message.orEmpty().contains("metadata persistence failed"))
        val rejectedReference = secrets.durablySavedHandles.last()
        assertTrue(previousReference != rejectedReference)
        assertEquals(previousReference, diskData().pendingPairingRoute?.relaySecretRef)
        assertEquals("secret-before-failure", store.load().pendingPairingRoute?.relaySecret)
        assertEquals("secret-before-failure", secrets.readSecret(previousReference))
        assertNull(secrets.readSecret(rejectedReference))
        assertTrue(rejectedReference in secrets.durablyRemovedHandles)
    }

    @Test
    fun unchangedPendingSecretIsNotRewrittenAcrossStateBarriers() {
        val secrets = RecordingRelaySecretStore()
        val store = RuntimeLocalStore(context, json, secrets)
        val data = runtimeDataWithPendingRelay("stable-secret", "secret-stable")
        store.save(data, commitToDisk = true)
        val firstReference = requireNotNull(diskData().pendingPairingRoute?.relaySecretRef)
        val loaded = store.load()

        store.save(loaded.copy(composerDraft = "durable barrier"), commitToDisk = true)
        store.save(loaded.copy(composerDraft = "volatile barrier"), commitToDisk = false)

        assertEquals(listOf(firstReference), secrets.durablySavedHandles)
        assertTrue(secrets.removedHandles.isEmpty())
        assertTrue(secrets.durablyRemovedHandles.isEmpty())
        assertEquals("secret-stable", secrets.readSecret(firstReference))
    }

    @Test
    fun invalidPendingRouteCannotDeleteForeignSecretReferenceOnNextSave() {
        val secrets = RecordingRelaySecretStore()
        val invalidRef = "invalid-route-secret-ref"
        secrets.saveSecret(invalidRef, "orphaned-secret")
        val invalidData = runtimeDataWithPendingRelay("invalid", "unused")
            .copy(
                pendingPairingRoute = runtimeDataWithPendingRelay("invalid", "unused")
                    .pendingPairingRoute
                    ?.copy(
                        pairingCode = "not-six-digits",
                        relaySecret = null,
                        relaySecretRef = invalidRef,
                    ),
            )
        preferences().edit()
            .putString(STORE_KEY_FOR_TEST, json.encodeToString(PersistedRuntimeData.serializer(), invalidData))
            .commit()
        val store = RuntimeLocalStore(context, json, secrets)

        assertEquals(PersistedRuntimeData(), store.load())

        store.save(PersistedRuntimeData())

        assertTrue(secrets.removedHandles.isEmpty())
        assertEquals("orphaned-secret", secrets.readSecret(invalidRef))
    }

    @Test
    fun validPendingMetadataCannotReadOrDeleteTrustedSecretNamespace() {
        val secrets = RecordingRelaySecretStore()
        val trustedRef = "relay-v1-${"a".repeat(64)}"
        secrets.saveSecret(trustedRef, "trusted-secret")
        val foreignData = runtimeDataWithPendingRelay("foreign", "unused").copy(
            pendingPairingRoute = runtimeDataWithPendingRelay("foreign", "unused")
                .pendingPairingRoute
                ?.copy(
                    relaySecret = null,
                    relaySecretRef = trustedRef,
                ),
        )
        preferences().edit()
            .putString(STORE_KEY_FOR_TEST, json.encodeToString(PersistedRuntimeData.serializer(), foreignData))
            .commit()
        val store = RuntimeLocalStore(context, json, secrets)

        assertNull(store.load().pendingPairingRoute)
        store.save(PersistedRuntimeData())

        assertTrue(secrets.removedHandles.isEmpty())
        assertEquals("trusted-secret", secrets.readSecret(trustedRef))
    }

    @Test
    fun interleavedStoreInstancesRemoveTheLatestPersistedSecretReference() {
        val secrets = RecordingRelaySecretStore()
        val firstStore = RuntimeLocalStore(context, json, secrets)
        firstStore.save(runtimeDataWithPendingRelay("first", "secret-first"))
        val firstRef = requireNotNull(diskData().pendingPairingRoute?.relaySecretRef)
        assertEquals("secret-first", firstStore.load().pendingPairingRoute?.relaySecret)

        val secondStore = RuntimeLocalStore(context, json, secrets)
        secondStore.save(runtimeDataWithPendingRelay("second", "secret-second"))
        val secondRef = requireNotNull(diskData().pendingPairingRoute?.relaySecretRef)

        assertEquals(listOf(firstRef), secrets.removedHandles)
        firstStore.save(PersistedRuntimeData())

        assertEquals(listOf(firstRef, secondRef), secrets.removedHandles)
        assertNull(secrets.readSecret(secondRef))
        assertNull(diskData().pendingPairingRoute)
    }

    @Test
    fun saveWritesOneSanitizedDiskProjectionWithoutRuntimeMessagesOrPlaintextSecret() {
        val secrets = RecordingRelaySecretStore()
        val store = RuntimeLocalStore(context, json, secrets)
        val runtimeSession = PersistedChatSession(
            id = "runtime-session",
            title = "Runtime session",
            createdAtMillis = 1L,
            updatedAtMillis = 2L,
            runtimeOwned = true,
            messages = listOf(
                PersistedChatMessage(
                    id = "runtime-message",
                    role = "assistant",
                    content = "runtime-only-content",
                    createdAtMillis = 2L,
                ),
            ),
        )

        store.save(
            runtimeDataWithPendingRelay("projection", "projection-secret")
                .copy(sessions = listOf(runtimeSession)),
        )

        val raw = requireNotNull(preferences().getString(STORE_KEY_FOR_TEST, null))
        val persisted = json.decodeFromString<PersistedRuntimeData>(raw)
        val pending = requireNotNull(persisted.pendingPairingRoute)

        assertFalse(raw.contains("projection-secret"))
        assertFalse(raw.contains("runtime-only-content"))
        assertNull(pending.relaySecret)
        assertNotNull(pending.relaySecretRef)
        assertTrue(persisted.sessions.single().messages.isEmpty())
    }

    @Test
    fun unsupportedSystemLanguageFallsBackWithoutOverridingExplicitLanguage() {
        val systemKorean = PersistedRuntimeData().withSystemAppLanguageTag("ko-KR")
        val unsupportedSystem = systemKorean.withSystemAppLanguageTag("de-DE")
        val explicitKorean = PersistedRuntimeData()
            .withAppLanguageTag("ko-KR")
            .withSystemAppLanguageTag("de-DE")

        assertEquals("en", unsupportedSystem.appLanguageTag)
        assertEquals(APP_LANGUAGE_SOURCE_DEFAULT, unsupportedSystem.appLanguageSource)
        assertEquals("ko", explicitKorean.appLanguageTag)
        assertEquals(APP_LANGUAGE_SOURCE_IN_APP, explicitKorean.appLanguageSource)
    }

    @Test
    fun androidPlatformLanguageSnapshotUsesApi33OverrideAndPreservesLegacyExplicitChoice() {
        val explicitFrench = PersistedRuntimeData().withAppLanguageTag("fr-FR")
        val api33PendingFrenchMigration = explicitFrench.reconcileAndroidPlatformAppLanguage(
            applicationLocalesSupported = true,
            applicationLocaleLanguageTag = null,
            systemLanguageTag = "ja-JP",
        )
        val api33RetriedFrenchMigration =
            api33PendingFrenchMigration.data.reconcileAndroidPlatformAppLanguage(
                applicationLocalesSupported = true,
                applicationLocaleLanguageTag = null,
                systemLanguageTag = "ja-JP",
            )
        val api33CompletedFrenchMigration =
            api33RetriedFrenchMigration.data.reconcileAndroidPlatformAppLanguage(
                applicationLocalesSupported = true,
                applicationLocaleLanguageTag = "fr-FR",
                systemLanguageTag = "ja-JP",
            )
        val api33ExternalClearAfterMigration =
            api33CompletedFrenchMigration.data.reconcileAndroidPlatformAppLanguage(
                applicationLocalesSupported = true,
                applicationLocaleLanguageTag = null,
                systemLanguageTag = "ja-JP",
            )
        val api33KoreanOverride = explicitFrench.reconcileAndroidPlatformAppLanguage(
            applicationLocalesSupported = true,
            applicationLocaleLanguageTag = "ko-KR",
            systemLanguageTag = "ja-JP",
        )
        val api33SimplifiedChineseOverride =
            explicitFrench.reconcileAndroidPlatformAppLanguage(
                applicationLocalesSupported = true,
                applicationLocaleLanguageTag = "zh-Hans",
                systemLanguageTag = "ja-JP",
            )
        val api33FollowJapanese = PersistedRuntimeData(
            androidAppLanguagePlatformMigrationVersion =
                ANDROID_APP_LANGUAGE_PLATFORM_MIGRATION_VERSION,
        ).reconcileAndroidPlatformAppLanguage(
            applicationLocalesSupported = true,
            applicationLocaleLanguageTag = null,
            systemLanguageTag = "ja-JP",
        )
        val api33UnsupportedSystem = PersistedRuntimeData(
            androidAppLanguagePlatformMigrationVersion =
                ANDROID_APP_LANGUAGE_PLATFORM_MIGRATION_VERSION,
        ).reconcileAndroidPlatformAppLanguage(
            applicationLocalesSupported = true,
            applicationLocaleLanguageTag = null,
            systemLanguageTag = "de-DE",
        )
        val api33DefaultCompletesWithoutSetter =
            PersistedRuntimeData().reconcileAndroidPlatformAppLanguage(
                applicationLocalesSupported = true,
                applicationLocaleLanguageTag = null,
                systemLanguageTag = "ko-KR",
            )
        val api33ExplicitEnglishMigration =
            PersistedRuntimeData().withAppLanguageTag("en-US")
                .reconcileAndroidPlatformAppLanguage(
                    applicationLocalesSupported = true,
                    applicationLocaleLanguageTag = null,
                    systemLanguageTag = "en-US",
                )
        val api33FutureMigrationVersion = PersistedRuntimeData(
            appLanguageTag = "fr",
            appLanguageSource = APP_LANGUAGE_SOURCE_IN_APP,
            androidAppLanguagePlatformMigrationVersion = 7,
            pendingAndroidAppLanguagePlatformMigrationTag = "fr",
        ).reconcileAndroidPlatformAppLanguage(
            applicationLocalesSupported = true,
            applicationLocaleLanguageTag = null,
            systemLanguageTag = "ko-KR",
        )
        val mismatchedPendingMigration = PersistedRuntimeData(
            appLanguageTag = "fr",
            appLanguageSource = APP_LANGUAGE_SOURCE_IN_APP,
            pendingAndroidAppLanguagePlatformMigrationTag = "ko",
        ).sanitized()
        val systemSourcePendingMigration = PersistedRuntimeData(
            appLanguageTag = "fr",
            appLanguageSource = APP_LANGUAGE_SOURCE_SYSTEM,
            pendingAndroidAppLanguagePlatformMigrationTag = "fr",
        ).sanitized()
        val api32ExplicitFrench = explicitFrench.reconcileAndroidPlatformAppLanguage(
            applicationLocalesSupported = false,
            applicationLocaleLanguageTag = null,
            systemLanguageTag = "ko-KR",
        )
        val api32SystemKorean = PersistedRuntimeData().reconcileAndroidPlatformAppLanguage(
            applicationLocalesSupported = false,
            applicationLocaleLanguageTag = null,
            systemLanguageTag = "ko-KR",
        )

        assertEquals("fr", api33PendingFrenchMigration.data.appLanguageTag)
        assertEquals(APP_LANGUAGE_SOURCE_IN_APP, api33PendingFrenchMigration.data.appLanguageSource)
        assertEquals("fr", api33PendingFrenchMigration.snapshot.languageTag)
        assertEquals("fr", api33PendingFrenchMigration.applicationLocaleLanguageTagToSet)
        assertEquals(0, api33PendingFrenchMigration.data.androidAppLanguagePlatformMigrationVersion)
        assertEquals("fr", api33PendingFrenchMigration.data.pendingAndroidAppLanguagePlatformMigrationTag)
        assertEquals(api33PendingFrenchMigration, api33RetriedFrenchMigration)

        assertNull(api33CompletedFrenchMigration.applicationLocaleLanguageTagToSet)
        assertEquals(
            ANDROID_APP_LANGUAGE_PLATFORM_MIGRATION_VERSION,
            api33CompletedFrenchMigration.data.androidAppLanguagePlatformMigrationVersion,
        )
        assertNull(
            api33CompletedFrenchMigration.data.pendingAndroidAppLanguagePlatformMigrationTag,
        )
        assertEquals("ja", api33ExternalClearAfterMigration.data.appLanguageTag)
        assertEquals(
            APP_LANGUAGE_SOURCE_SYSTEM,
            api33ExternalClearAfterMigration.data.appLanguageSource,
        )
        assertNull(api33ExternalClearAfterMigration.applicationLocaleLanguageTagToSet)

        assertEquals("ko", api33KoreanOverride.data.appLanguageTag)
        assertEquals(APP_LANGUAGE_SOURCE_IN_APP, api33KoreanOverride.data.appLanguageSource)
        assertEquals(
            ANDROID_APP_LANGUAGE_PLATFORM_MIGRATION_VERSION,
            api33KoreanOverride.data.androidAppLanguagePlatformMigrationVersion,
        )
        assertEquals("zh-CN", api33SimplifiedChineseOverride.data.appLanguageTag)
        assertEquals(APP_LANGUAGE_SOURCE_IN_APP, api33SimplifiedChineseOverride.data.appLanguageSource)
        assertEquals("ja", api33FollowJapanese.data.appLanguageTag)
        assertEquals(APP_LANGUAGE_SOURCE_SYSTEM, api33FollowJapanese.data.appLanguageSource)
        assertEquals("en", api33UnsupportedSystem.data.appLanguageTag)
        assertEquals(APP_LANGUAGE_SOURCE_DEFAULT, api33UnsupportedSystem.data.appLanguageSource)

        assertEquals("ko", api33DefaultCompletesWithoutSetter.data.appLanguageTag)
        assertEquals(APP_LANGUAGE_SOURCE_SYSTEM, api33DefaultCompletesWithoutSetter.data.appLanguageSource)
        assertEquals(
            ANDROID_APP_LANGUAGE_PLATFORM_MIGRATION_VERSION,
            api33DefaultCompletesWithoutSetter.data.androidAppLanguagePlatformMigrationVersion,
        )
        assertNull(api33DefaultCompletesWithoutSetter.applicationLocaleLanguageTagToSet)
        assertEquals("en", api33ExplicitEnglishMigration.applicationLocaleLanguageTagToSet)
        assertEquals("en", api33ExplicitEnglishMigration.snapshot.languageTag)

        assertEquals(7, api33FutureMigrationVersion.data.androidAppLanguagePlatformMigrationVersion)
        assertEquals("ko", api33FutureMigrationVersion.data.appLanguageTag)
        assertEquals(APP_LANGUAGE_SOURCE_SYSTEM, api33FutureMigrationVersion.data.appLanguageSource)
        assertNull(api33FutureMigrationVersion.data.pendingAndroidAppLanguagePlatformMigrationTag)
        assertNull(api33FutureMigrationVersion.applicationLocaleLanguageTagToSet)
        assertNull(mismatchedPendingMigration.pendingAndroidAppLanguagePlatformMigrationTag)
        assertNull(systemSourcePendingMigration.pendingAndroidAppLanguagePlatformMigrationTag)

        assertEquals("fr", api32ExplicitFrench.data.appLanguageTag)
        assertEquals(APP_LANGUAGE_SOURCE_IN_APP, api32ExplicitFrench.data.appLanguageSource)
        assertEquals(0, api32ExplicitFrench.data.androidAppLanguagePlatformMigrationVersion)
        assertNull(api32ExplicitFrench.applicationLocaleLanguageTagToSet)
        assertEquals("ko", api32SystemKorean.data.appLanguageTag)
        assertEquals(APP_LANGUAGE_SOURCE_SYSTEM, api32SystemKorean.data.appLanguageSource)
        assertEquals(0, api32SystemKorean.data.androidAppLanguagePlatformMigrationVersion)
    }

    @Test
    fun composerDraftLimitNeverPersistsHalfOfSurrogatePair() {
        val splitBoundary = "a".repeat(19_999) + "😀" + "tail"
        val exactBoundary = "a".repeat(19_998) + "😀"
        val store = RuntimeLocalStore(context, json, RecordingRelaySecretStore())

        store.save(PersistedRuntimeData().withComposerDraft(splitBoundary))
        val truncated = store.load().composerDraft
        assertEquals(19_999, truncated.length)
        assertFalse(truncated.any(Char::isSurrogate))

        store.save(PersistedRuntimeData().withComposerDraft(exactBoundary))
        assertEquals(exactBoundary, store.load().composerDraft)
    }

    private fun runtimeDataWithPendingRelay(suffix: String, secret: String): PersistedRuntimeData {
        return PersistedRuntimeData(
            pendingPairingRoute = PersistedPendingPairingRoute(
                pairingNonce = "pairing-nonce-$suffix",
                pairingCode = "123456",
                runtimeDeviceId = "runtime-$suffix",
                runtimeName = "Runtime $suffix",
                fingerprint = "fingerprint-$suffix",
                runtimePublicKeyBase64 = "public-key-$suffix",
                routeToken = "route-token-$suffix",
                relayHost = "relay.example.test",
                relayPort = 443,
                relayId = "relay-$suffix",
                relaySecret = secret,
                relayExpiresAtEpochMillis = 4_102_444_800_000L,
                relayNonce = "relay-nonce-$suffix",
                relayScope = "remote",
                capturedAtEpochMillis = 1_000L,
                expiresAtEpochMillis = 301_000L,
            ),
        )
    }

    private fun assertIncompatibleRawIsPreserved(
        raw: String,
        expectedIssue: RuntimeLocalDataCompatibilityIssue,
    ) {
        preferences().edit().clear().putString(STORE_KEY_FOR_TEST, raw).commit()
        val secrets = RecordingRelaySecretStore()
        var durableMetadataCommitCount = 0
        var volatileMetadataApplyCount = 0
        val store = RuntimeLocalStore(
            context = context,
            json = json,
            relaySecretStore = secrets,
            durableMetadataCommit = { editor ->
                durableMetadataCommitCount += 1
                editor.commit()
            },
            volatileMetadataApply = { editor ->
                volatileMetadataApplyCount += 1
                editor.apply()
            },
        )

        val result = store.loadResult()
        assertEquals(PersistedRuntimeData(), result.data)
        assertEquals(expectedIssue, result.compatibilityIssue)

        listOf(false, true).forEach { commitToDisk ->
            val error = assertThrows(IllegalStateException::class.java) {
                store.save(
                    data = runtimeDataWithPendingRelay(
                        suffix = "blocked-$commitToDisk",
                        secret = "must-not-write-$commitToDisk",
                    ),
                    commitToDisk = commitToDisk,
                )
            }
            assertTrue(error.message.orEmpty().contains("cannot be rewritten"))
            assertEquals(raw, preferences().getString(STORE_KEY_FOR_TEST, null))
        }

        assertEquals(0, durableMetadataCommitCount)
        assertEquals(0, volatileMetadataApplyCount)
        assertTrue(secrets.storedHandles.isEmpty())
        assertTrue(secrets.removedHandles.isEmpty())
        assertTrue(secrets.durablySavedHandles.isEmpty())
        assertTrue(secrets.durablyRemovedHandles.isEmpty())
    }

    private fun diskData(): PersistedRuntimeData {
        val raw = requireNotNull(preferences().getString(STORE_KEY_FOR_TEST, null))
        return json.decodeFromString(raw)
    }

    private fun preferences() = context.getSharedPreferences(STORE_NAME_FOR_TEST, Context.MODE_PRIVATE)

    private class RecordingRelaySecretStore : DurableRelaySecretStore {
        private val secrets = mutableMapOf<String, String>()
        val removedHandles = mutableListOf<String>()
        val durablySavedHandles = mutableListOf<String>()
        val durablyRemovedHandles = mutableListOf<String>()
        val storedHandles: Set<String>
            get() = secrets.keys.toSet()
        var failNextDurableRemoval = false

        override fun saveSecret(handle: String, secret: String) {
            secrets[handle] = secret
        }

        override fun readSecret(handle: String): String? = secrets[handle]

        override fun saveSecretDurably(handle: String, secret: String): Boolean {
            durablySavedHandles += handle
            secrets[handle] = secret
            return true
        }

        override fun removeSecret(handle: String) {
            removedHandles += handle
            secrets.remove(handle)
        }

        override fun removeSecretDurably(handle: String): Boolean {
            durablyRemovedHandles += handle
            if (failNextDurableRemoval) {
                failNextDurableRemoval = false
                return false
            }
            secrets.remove(handle)
            return true
        }
    }

    private class NonDurableRelaySecretStore : RelaySecretStore {
        private val secrets = mutableMapOf<String, String>()

        override fun saveSecret(handle: String, secret: String) {
            secrets[handle] = secret
        }

        override fun readSecret(handle: String): String? = secrets[handle]

        override fun removeSecret(handle: String) {
            secrets.remove(handle)
        }
    }

    private companion object {
        const val STORE_NAME_FOR_TEST = "runtime_local_store"
        const val STORE_KEY_FOR_TEST = "runtime_data"
        const val PENDING_RELAY_SECRET_CLEANUP_KEY_FOR_TEST = "pending_relay_secret_cleanup_refs"
    }
}
