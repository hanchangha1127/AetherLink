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
    fun emptyAndCorruptStoresLoadAsDefaultsAndRemainWritable() {
        val emptySecrets = RecordingRelaySecretStore()
        val emptyStore = RuntimeLocalStore(context, json, emptySecrets)

        assertEquals(PersistedRuntimeData(), emptyStore.load())

        emptyStore.save(PersistedRuntimeData(composerDraft = "after-empty"))
        assertEquals("after-empty", emptyStore.load().composerDraft)

        preferences().edit().putString(STORE_KEY_FOR_TEST, "{not-json").commit()
        val corruptSecrets = RecordingRelaySecretStore()
        val corruptStore = RuntimeLocalStore(context, json, corruptSecrets)

        assertEquals(PersistedRuntimeData(), corruptStore.load())

        corruptStore.save(PersistedRuntimeData(composerDraft = "after-corrupt"))
        assertEquals("after-corrupt", corruptStore.load().composerDraft)
        assertTrue(corruptSecrets.removedHandles.isEmpty())
    }

    @Test
    fun wrongTypedPreferenceRecoversToDefaultsAndRemainsWritable() {
        preferences().edit().putInt(STORE_KEY_FOR_TEST, 7).commit()
        val store = RuntimeLocalStore(context, json, RecordingRelaySecretStore())

        assertEquals(PersistedRuntimeData(), store.load())
        assertFalse(preferences().contains(STORE_KEY_FOR_TEST))

        store.save(PersistedRuntimeData(composerDraft = "after-type-recovery"))
        assertEquals("after-type-recovery", store.load().composerDraft)
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
