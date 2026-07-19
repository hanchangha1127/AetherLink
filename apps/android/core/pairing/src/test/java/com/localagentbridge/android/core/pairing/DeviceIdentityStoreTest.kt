package com.localagentbridge.android.core.pairing

import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.security.KeyFactory
import java.security.KeyPair
import java.security.KeyPairGenerator
import java.security.Signature
import java.security.spec.ECGenParameterSpec
import java.security.spec.X509EncodedKeySpec
import java.util.Base64
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger

@RunWith(RobolectricTestRunner::class)
class DeviceIdentityStoreTest {
    private val context: android.content.Context = ApplicationProvider.getApplicationContext()

    @Before
    fun resetStore() = runTest {
        context.localAgentBridgeDataStore.edit { it.clear() }
    }

    @Test
    fun loadOrCreateReusesDeviceIdNameAndPublicKeyAcrossStoreInstances() = runTest {
        val keyPairStore = FakeDeviceIdentityKeyPairStore()
        val first = DeviceIdentityStore(context, keyPairStore).loadOrCreate()
        val second = DeviceIdentityStore(context, keyPairStore).loadOrCreate()

        assertEquals(first.deviceId, second.deviceId)
        assertEquals(first.deviceName, second.deviceName)
        assertEquals(first.publicKeyBase64, second.publicKeyBase64)
        assertEquals(2, keyPairStore.loadCalls)
        assertTrue(first.deviceId.isNotBlank())
        assertTrue(first.deviceName.isNotBlank())
        assertTrue(
            verifyClientAuthSignature(
                publicKeyBase64 = second.publicKeyBase64,
                deviceId = first.deviceId,
                nonce = "auth-nonce-1",
                signatureBase64 = first.signAuthenticationResponse("auth-nonce-1"),
            )
        )
    }

    @Test
    fun concurrentFirstRunReturnsOnePersistedIdentityAcrossStoreInstances() = runTest {
        val keyPairStore = RacingDeviceIdentityKeyPairStore()
        val identities = awaitAll(
            async(Dispatchers.IO) {
                DeviceIdentityStore(context, keyPairStore).loadOrCreate()
            },
            async(Dispatchers.IO) {
                DeviceIdentityStore(context, keyPairStore).loadOrCreate()
            },
        )

        val persisted = context.localAgentBridgeDataStore.data.first()
        assertEquals(identities[0].deviceId, identities[1].deviceId)
        assertEquals(identities[0].deviceName, identities[1].deviceName)
        assertEquals(identities[0].publicKeyBase64, identities[1].publicKeyBase64)
        assertEquals(identities[0].deviceId, persisted[stringPreferencesKey("android_device_id")])
        assertEquals(identities[0].deviceName, persisted[stringPreferencesKey("android_device_name")])
        assertEquals(2, keyPairStore.loadCalls.get())
    }

    @Test
    fun loadOrCreateDoesNotPersistPrivateKeyMaterialInDataStore() = runTest {
        val keyPairStore = FakeDeviceIdentityKeyPairStore()

        DeviceIdentityStore(context, keyPairStore).loadOrCreate()

        val prefs = context.localAgentBridgeDataStore.data.first()
        assertEquals(
            setOf("android_device_id", "android_device_name"),
            prefs.asMap().keys.map { it.name }.toSet(),
        )
        val storedValues = prefs.asMap().values.map { it.toString() }
        assertFalse(storedValues.contains(keyPairStore.keyPair.private.encoded?.let(Base64.getEncoder()::encodeToString)))
        assertFalse(storedValues.contains(Base64.getEncoder().encodeToString(keyPairStore.keyPair.public.encoded)))
    }

    @Test
    fun keyPairFailureSurfacesWithoutRotatingStoredDeviceIdentity() = runTest {
        context.localAgentBridgeDataStore.edit { prefs ->
            prefs[stringPreferencesKey("android_device_id")] = "android-client-1"
            prefs[stringPreferencesKey("android_device_name")] = "AetherLink Test Client"
        }
        val failure = IllegalStateException("keystore unavailable")
        val store = DeviceIdentityStore(context, FailingDeviceIdentityKeyPairStore(failure))

        try {
            store.loadOrCreate()
            fail("Expected keypair failure")
        } catch (error: IllegalStateException) {
            assertEquals(failure.message, error.message)
        }

        val prefs = context.localAgentBridgeDataStore.data.first()
        assertEquals("android-client-1", prefs[stringPreferencesKey("android_device_id")])
        assertEquals("AetherLink Test Client", prefs[stringPreferencesKey("android_device_name")])
    }

    @Test
    fun firstRunKeyPairFailureDoesNotPersistOrphanDeviceIdentity() = runTest {
        val failure = IllegalStateException("keystore unavailable")
        val store = DeviceIdentityStore(context, FailingDeviceIdentityKeyPairStore(failure))

        try {
            store.loadOrCreate()
            fail("Expected keypair failure")
        } catch (error: IllegalStateException) {
            assertEquals(failure.message, error.message)
        }

        val prefs = context.localAgentBridgeDataStore.data.first()
        assertTrue(prefs.asMap().isEmpty())
    }

    private fun verifyClientAuthSignature(
        publicKeyBase64: String,
        deviceId: String,
        nonce: String,
        signatureBase64: String,
    ): Boolean {
        val publicKey = KeyFactory.getInstance("EC")
            .generatePublic(X509EncodedKeySpec(Base64.getDecoder().decode(publicKeyBase64)))
        return Signature.getInstance("SHA256withECDSA").run {
            initVerify(publicKey)
            update(DeviceIdentity.authenticationResponseMessage(deviceId, nonce))
            verify(Base64.getDecoder().decode(signatureBase64))
        }
    }

    private class FakeDeviceIdentityKeyPairStore(
        val keyPair: KeyPair = generateKeyPair(),
    ) : DeviceIdentityKeyPairStore {
        var loadCalls = 0
            private set

        override fun loadOrCreate(): KeyPair {
            loadCalls += 1
            return keyPair
        }
    }

    private class RacingDeviceIdentityKeyPairStore(
        private val keyPair: KeyPair = generateKeyPair(),
    ) : DeviceIdentityKeyPairStore {
        val loadCalls = AtomicInteger()
        private val simultaneousArrivals = CountDownLatch(2)

        override fun loadOrCreate(): KeyPair {
            loadCalls.incrementAndGet()
            simultaneousArrivals.countDown()
            simultaneousArrivals.await(250, TimeUnit.MILLISECONDS)
            return keyPair
        }
    }

    private class FailingDeviceIdentityKeyPairStore(
        private val failure: RuntimeException,
    ) : DeviceIdentityKeyPairStore {
        override fun loadOrCreate(): KeyPair {
            throw failure
        }
    }

    private companion object {
        fun generateKeyPair(): KeyPair {
            return KeyPairGenerator.getInstance("EC").apply {
                initialize(ECGenParameterSpec("secp256r1"))
            }.generateKeyPair()
        }
    }
}
