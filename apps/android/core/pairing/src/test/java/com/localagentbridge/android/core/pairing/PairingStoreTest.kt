package com.localagentbridge.android.core.pairing

import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class PairingStoreTest {
    @Test
    fun trustedRuntimeDirectEndpointPreservesValidQrHostAndPort() {
        val runtime = trustedRuntime(host = "192.168.1.10", port = 43170)

        val endpoint = runtime.validDirectEndpointOrNull()

        assertEquals("192.168.1.10", endpoint?.host)
        assertEquals(43170, endpoint?.port)
    }

    @Test
    fun trustedRuntimeDirectEndpointRejectsBlankOrInvalidValues() {
        assertNull(trustedRuntime(host = "", port = 43170).validDirectEndpointOrNull())
        assertNull(trustedRuntime(host = "192.168.1.10", port = null).validDirectEndpointOrNull())
        assertNull(trustedRuntime(host = "192.168.1.10", port = 0).validDirectEndpointOrNull())
        assertNull(trustedRuntime(host = "192.168.1.10", port = 70000).validDirectEndpointOrNull())
    }

    @Test
    fun trustedRuntimeCanCarryRelaySecret() {
        val runtime = trustedRuntime(host = "192.168.1.10", port = 43170).copy(
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-1",
        )

        assertEquals("secret-1", runtime.relaySecret)
        assertEquals(4102444800000L, runtime.relayExpiresAtEpochMillis)
        assertEquals("nonce-route-1", runtime.relayNonce)
    }

    @Test
    fun trustedRuntimeRejectsIncompleteRelayLease() {
        val runtime = trustedRuntime(host = null, port = null).copy(
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
        )

        assertEquals(false, runtime.hasValidRelayRoute())
    }

    @Test
    fun trustedRuntimeRejectsExpiredRelayLease() {
        val runtime = trustedRuntime(host = null, port = null).copy(
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 1L,
            relayNonce = "nonce-route-1",
        )

        assertEquals(false, runtime.hasValidRelayRoute())
    }

    @Test
    fun trustedRuntimeReportsExpiredCompleteRelayLease() {
        val runtime = trustedRuntime(host = null, port = null).copy(
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 2_000L,
            relayNonce = "nonce-route-1",
        )

        assertEquals(false, runtime.hasValidRelayRoute())
        assertEquals(true, runtime.hasExpiredRelayRoute(nowEpochMillis = 2_001L))
        assertEquals(false, runtime.hasExpiredRelayRoute(nowEpochMillis = 1_999L))
    }

    @Test
    fun trustedRuntimeRejectsLoopbackRelayRoute() {
        val runtime = trustedRuntime(host = null, port = null).copy(
            relayHost = "127.0.0.1",
            relayPort = 63664,
            relayId = "relay-1",
            relaySecret = "secret-1",
        )

        assertNull(runtime.validDirectEndpointOrNull())
        assertEquals(false, runtime.hasValidRelayRoute())
    }

    @Test
    fun trustedRuntimeAllowsDebugUsbReverseLoopbackRelayRoute() {
        val runtime = trustedRuntime(host = null, port = null).copy(
            relayHost = "127.0.0.1",
            relayPort = 43171,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-1",
            relayScope = "usb_reverse",
        )

        assertNull(runtime.validDirectEndpointOrNull())
        assertEquals(true, runtime.hasValidRelayRoute())
    }

    @Test
    fun trustedRuntimeAllowsPrivateOverlayRelayRoute() {
        val runtime = trustedRuntime(host = null, port = null).copy(
            relayHost = "100.64.1.10",
            relayPort = 43171,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-1",
            relayScope = "private_overlay",
        )

        assertNull(runtime.validDirectEndpointOrNull())
        assertEquals(true, runtime.hasValidRelayRoute())
    }

    @Test
    fun trustedRuntimeDirectEndpointIsSuppressedWhenRelayRouteExists() {
        val runtime = trustedRuntime(host = "192.168.1.10", port = 43170).copy(
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-1",
        )

        val endpoint = runtime.validDirectEndpointOrNull()

        assertNull(endpoint)
    }

    @Test
    fun trustedRuntimeDirectEndpointIsKeptWhenRelayRouteHasNoSecret() {
        val runtime = trustedRuntime(host = "192.168.1.10", port = 43170).copy(
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = null,
        )

        val endpoint = runtime.validDirectEndpointOrNull()

        assertEquals("192.168.1.10", endpoint?.host)
        assertEquals(43170, endpoint?.port)
    }

    @Test
    fun pairingStorePersistsCompleteRelayRoute() = runTest {
        val store = pairingStore()
        store.forgetRuntime()

        store.trustRuntime(completeRelayRuntime())

        val trusted = store.trustedRuntime.first()
        assertEquals("runtime-1", trusted?.deviceId)
        assertEquals("AetherLink Runtime", trusted?.name)
        assertEquals("runtime-fingerprint", trusted?.fingerprint)
        assertEquals("runtime-public-key", trusted?.publicKeyBase64)
        assertEquals("route-token", trusted?.routeToken)
        assertNull(trusted?.host)
        assertNull(trusted?.port)
        assertEquals("relay.example.test", trusted?.relayHost)
        assertEquals(443, trusted?.relayPort)
        assertEquals("relay-1", trusted?.relayId)
        assertEquals("secret-1", trusted?.relaySecret)
        assertEquals(4102444800000L, trusted?.relayExpiresAtEpochMillis)
        assertEquals("nonce-route-1", trusted?.relayNonce)
        assertEquals("remote", trusted?.relayScope)

        store.forgetRuntime()
    }

    @Test
    fun pairingStorePreservesExpiredCompleteRelayRouteForReconnectDiagnostics() = runTest {
        val store = pairingStore()
        store.forgetRuntime()

        store.trustRuntime(
            completeRelayRuntime().copy(
                relayExpiresAtEpochMillis = 2_000L,
                relayNonce = "expired-nonce-1",
            )
        )

        val trusted = store.trustedRuntime.first()
        assertEquals("runtime-1", trusted?.deviceId)
        assertEquals("relay.example.test", trusted?.relayHost)
        assertEquals(443, trusted?.relayPort)
        assertEquals("relay-1", trusted?.relayId)
        assertEquals("secret-1", trusted?.relaySecret)
        assertEquals(2_000L, trusted?.relayExpiresAtEpochMillis)
        assertEquals("expired-nonce-1", trusted?.relayNonce)
        assertEquals("remote", trusted?.relayScope)
        assertEquals(false, trusted?.hasValidRelayRoute())
        assertEquals(true, trusted?.hasExpiredRelayRoute(nowEpochMillis = 2_001L))
        assertNull(trusted?.validDirectEndpointOrNull())

        store.forgetRuntime()
    }

    @Test
    fun pairingStoreDropsIncompleteRelayRouteOnRead() = runTest {
        val store = pairingStore()
        store.forgetRuntime()

        ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .edit { prefs ->
                prefs[stringPreferencesKey("runtime_device_id")] = "runtime-1"
                prefs[stringPreferencesKey("runtime_name")] = "AetherLink Runtime"
                prefs[stringPreferencesKey("runtime_fingerprint")] = "runtime-fingerprint"
                prefs[stringPreferencesKey("runtime_public_key")] = "runtime-public-key"
                prefs[stringPreferencesKey("runtime_route_token")] = "route-token"
                prefs[stringPreferencesKey("runtime_relay_host")] = "relay.example.test"
                prefs[intPreferencesKey("runtime_relay_port")] = 443
                prefs[stringPreferencesKey("runtime_relay_id")] = "relay-1"
                prefs[longPreferencesKey("runtime_relay_expires_at_epoch_millis")] = 4102444800000L
                prefs[stringPreferencesKey("runtime_relay_nonce")] = "nonce-route-1"
                prefs[stringPreferencesKey("runtime_relay_scope")] = "remote"
            }

        val trusted = store.trustedRuntime.first()
        assertEquals("runtime-1", trusted?.deviceId)
        assertEquals("runtime-fingerprint", trusted?.fingerprint)
        assertNull(trusted?.relayHost)
        assertNull(trusted?.relayPort)
        assertNull(trusted?.relayId)
        assertNull(trusted?.relaySecret)
        assertNull(trusted?.relayExpiresAtEpochMillis)
        assertNull(trusted?.relayNonce)
        assertNull(trusted?.relayScope)

        store.forgetRuntime()
    }

    @Test
    fun pairingStoreForgetRuntimeClearsRelayRoute() = runTest {
        val store = pairingStore()
        store.forgetRuntime()
        store.trustRuntime(completeRelayRuntime())

        store.forgetRuntime()

        assertNull(store.trustedRuntime.first())
    }

    private fun trustedRuntime(
        host: String?,
        port: Int?,
    ): TrustedRuntime {
        return TrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            host = host,
            port = port,
        )
    }

    private fun completeRelayRuntime(): TrustedRuntime {
        return trustedRuntime(host = "192.168.1.10", port = 43170).copy(
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-1",
            relayScope = "remote",
        )
    }

    private fun pairingStore(): PairingStore {
        return PairingStore(ApplicationProvider.getApplicationContext())
    }
}
