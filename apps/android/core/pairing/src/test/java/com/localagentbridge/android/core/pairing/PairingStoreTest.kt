package com.localagentbridge.android.core.pairing

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

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
}
