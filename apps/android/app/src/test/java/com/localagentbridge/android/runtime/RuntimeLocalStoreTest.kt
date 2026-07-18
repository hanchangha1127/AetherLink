package com.localagentbridge.android.runtime

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import com.localagentbridge.android.core.pairing.RelaySecretStore
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.json.Json
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
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
    fun decodedButInvalidPendingRouteStillRemovesItsPreviousSecretOnNextSave() {
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

        assertEquals(listOf(invalidRef), secrets.removedHandles)
        assertNull(secrets.readSecret(invalidRef))
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

    private class RecordingRelaySecretStore : RelaySecretStore {
        private val secrets = mutableMapOf<String, String>()
        val removedHandles = mutableListOf<String>()

        override fun saveSecret(handle: String, secret: String) {
            secrets[handle] = secret
        }

        override fun readSecret(handle: String): String? = secrets[handle]

        override fun removeSecret(handle: String) {
            removedHandles += handle
            secrets.remove(handle)
        }
    }

    private companion object {
        const val STORE_NAME_FOR_TEST = "runtime_local_store"
        const val STORE_KEY_FOR_TEST = "runtime_data"
    }
}
