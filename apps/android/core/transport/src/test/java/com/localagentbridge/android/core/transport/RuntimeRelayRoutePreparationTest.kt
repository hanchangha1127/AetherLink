package com.localagentbridge.android.core.transport

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class RuntimeRelayRoutePreparationTest {
    @Test
    fun validRelayRoutePreparationMapsToPreparedRelayRoute() {
        val route = RuntimeRelayRoutePreparation(
            host = "relay.example.test",
            port = 443,
            relayId = "relay-1",
            relayFrameSecret = "secret-1",
            expiresAtEpochMillis = 4102444800000L,
            antiReplayNonce = "nonce-1",
        ).toPreparedRelayRouteOrNull(identity)

        assertNotNull(route)
        requireNotNull(route)
        assertEquals(identity, route.identity)
        assertEquals("relay-1", route.relayId)
        assertEquals("relay.example.test", route.host)
        assertEquals(443, route.port)
        assertEquals("secret-1", route.relayFrameSecret)
        assertEquals("relay-1", route.security.rendezvousToken)
        assertEquals(4102444800000L, route.security.expiresAtEpochMillis)
        assertEquals("nonce-1", route.security.antiReplayNonce)
    }

    @Test
    fun invalidRelayRoutePreparationReturnsNull() {
        val valid = RuntimeRelayRoutePreparation(
            host = "relay.example.test",
            port = 443,
            relayId = "relay-1",
            relayFrameSecret = "secret-1",
            expiresAtEpochMillis = 4102444800000L,
            antiReplayNonce = "nonce-1",
        )

        assertNull(valid.copy(host = null).toPreparedRelayRouteOrNull(identity))
        assertNull(valid.copy(host = "").toPreparedRelayRouteOrNull(identity))
        assertNull(valid.copy(port = null).toPreparedRelayRouteOrNull(identity))
        assertNull(valid.copy(port = 0).toPreparedRelayRouteOrNull(identity))
        assertNull(valid.copy(port = 70000).toPreparedRelayRouteOrNull(identity))
        assertNull(valid.copy(relayId = null).toPreparedRelayRouteOrNull(identity))
        assertNull(valid.copy(relayId = "").toPreparedRelayRouteOrNull(identity))
        assertNull(valid.copy(relayFrameSecret = null).toPreparedRelayRouteOrNull(identity))
        assertNull(valid.copy(relayFrameSecret = "").toPreparedRelayRouteOrNull(identity))
        assertNull(valid.copy(expiresAtEpochMillis = null).toPreparedRelayRouteOrNull(identity))
        assertNull(valid.copy(expiresAtEpochMillis = 1L).toPreparedRelayRouteOrNull(identity))
        assertNull(valid.copy(antiReplayNonce = null).toPreparedRelayRouteOrNull(identity))
        assertNull(valid.copy(antiReplayNonce = "").toPreparedRelayRouteOrNull(identity))
    }

    @Test
    fun relayRoutePreparationRejectsLocalOnlyRelayHosts() {
        val valid = RuntimeRelayRoutePreparation(
            host = "relay.example.test",
            port = 443,
            relayId = "relay-1",
            relayFrameSecret = "secret-1",
            expiresAtEpochMillis = 4102444800000L,
            antiReplayNonce = "nonce-1",
        )

        listOf(
            "127.0.0.1",
            "localhost",
            "0.0.0.0",
            "10.0.0.5",
            "100.64.1.5",
            "169.254.10.20",
            "172.20.1.5",
            "192.168.50.10",
            "[::1]",
            "[fe80::1]",
            "[fd00::1]",
            "aetherlink.local",
        ).forEach { host ->
            assertNull("Expected $host to be rejected", valid.copy(host = host).toPreparedRelayRouteOrNull(identity))
        }
    }

    @Test
    fun relayRoutePreparationRejectsNonCanonicalRelayHostMaterial() {
        val valid = RuntimeRelayRoutePreparation(
            host = "relay.example.test",
            port = 443,
            relayId = "relay-1",
            relayFrameSecret = "secret-1",
            expiresAtEpochMillis = 4102444800000L,
            antiReplayNonce = "nonce-1",
        )

        listOf(
            " relay.example.test",
            "relay.example.test ",
            "relay example.test",
            "2130706433",
            "167772161",
            "${"r".repeat(254)}.test",
            "https://relay.example.test",
            "relay.example.test/path",
            "relay.example.test?route=1",
            "relay.example.test#fragment",
            "user@relay.example.test",
        ).forEach { host ->
            assertNull(
                "Expected non-canonical relay host $host to be rejected",
                valid.copy(host = host).toPreparedRelayRouteOrNull(identity),
            )
        }
    }

    @Test
    fun relayRoutePreparationRejectsWhitespaceMutatedRelaySecrets() {
        val valid = RuntimeRelayRoutePreparation(
            host = "relay.example.test",
            port = 443,
            relayId = "relay-1",
            relayFrameSecret = "secret-1",
            expiresAtEpochMillis = 4102444800000L,
            antiReplayNonce = "nonce-1",
        )

        assertNull(valid.copy(relayId = " relay-1").toPreparedRelayRouteOrNull(identity))
        assertNull(valid.copy(relayId = "relay 1").toPreparedRelayRouteOrNull(identity))
        assertNull(valid.copy(relayFrameSecret = " secret-1").toPreparedRelayRouteOrNull(identity))
        assertNull(valid.copy(relayFrameSecret = "secret 1").toPreparedRelayRouteOrNull(identity))
        assertNull(valid.copy(antiReplayNonce = " nonce-1").toPreparedRelayRouteOrNull(identity))
        assertNull(valid.copy(antiReplayNonce = "nonce 1").toPreparedRelayRouteOrNull(identity))
    }

    @Test
    fun relayRoutePreparationRejectsOversizedOpaqueRouteMaterial() {
        val valid = RuntimeRelayRoutePreparation(
            host = "relay.example.test",
            port = 443,
            relayId = "relay-1",
            relayFrameSecret = "secret-1",
            expiresAtEpochMillis = 4102444800000L,
            antiReplayNonce = "nonce-1",
        )
        val oversizedOpaqueValue = "r".repeat(TEST_OPAQUE_RELAY_ROUTE_VALUE_MAX_CHARS + 1)

        assertNull(valid.copy(relayId = oversizedOpaqueValue).toPreparedRelayRouteOrNull(identity))
        assertNull(valid.copy(relayFrameSecret = oversizedOpaqueValue).toPreparedRelayRouteOrNull(identity))
        assertNull(valid.copy(antiReplayNonce = oversizedOpaqueValue).toPreparedRelayRouteOrNull(identity))
    }

    @Test
    fun relayRoutePreparationAllowsPrivateOverlayScopeForOverlayPrivateHosts() {
        val valid = RuntimeRelayRoutePreparation(
            host = "100.64.1.5",
            port = 443,
            relayId = "relay-1",
            relayFrameSecret = "secret-1",
            expiresAtEpochMillis = 4102444800000L,
            antiReplayNonce = "nonce-1",
            relayScope = "private_overlay",
        )

        assertEquals("100.64.1.5", valid.toPreparedRelayRouteOrNull(identity)?.host)
        assertEquals("private_overlay", valid.toPreparedRelayRouteOrNull(identity)?.relayScope)
        assertEquals("10.0.0.5", valid.copy(host = "10.0.0.5").toPreparedRelayRouteOrNull(identity)?.host)
        assertEquals("[fd00::1]", valid.copy(host = "[fd00::1]").toPreparedRelayRouteOrNull(identity)?.host)
        assertNull(valid.copy(host = "169.254.10.20").toPreparedRelayRouteOrNull(identity))
        assertNull(valid.copy(host = "[fe80::1]").toPreparedRelayRouteOrNull(identity))
    }

    @Test
    fun relayRoutePreparationRejectsUnknownOrMutatedRelayScope() {
        val valid = RuntimeRelayRoutePreparation(
            host = "relay.example.test",
            port = 443,
            relayId = "relay-1",
            relayFrameSecret = "secret-1",
            expiresAtEpochMillis = 4102444800000L,
            antiReplayNonce = "nonce-1",
        )

        listOf("public", "REMOTE", " remote ", " private_overlay ", "USB_REVERSE").forEach { scope ->
            assertNull(
                "Expected relay scope $scope to be rejected",
                valid.copy(relayScope = scope).toPreparedRelayRouteOrNull(identity),
            )
        }
    }

    @Test
    fun relayRoutePreparationAllowsUsbReverseScopeForLoopbackDiagnostics() {
        val route = RuntimeRelayRoutePreparation(
            host = "127.0.0.1",
            port = 443,
            relayId = "relay-1",
            relayFrameSecret = "secret-1",
            expiresAtEpochMillis = 4102444800000L,
            antiReplayNonce = "nonce-1",
            relayScope = "usb_reverse",
        ).toPreparedRelayRouteOrNull(identity)

        assertEquals("127.0.0.1", route?.host)
    }

    @Test
    fun relayRoutePreparationRequiresExplicitRelayId() {
        val route = RuntimeRelayRoutePreparation(
            host = "relay.example.test",
            port = 443,
            relayId = null,
            relayFrameSecret = "secret-1",
            expiresAtEpochMillis = 4102444800000L,
            antiReplayNonce = "nonce-1",
        ).toPreparedRelayRouteOrNull(identity)

        assertNull(route)
    }

    @Test
    fun relayRoutePreparationRejectsPairedRouteTokenAsRelayId() {
        val route = RuntimeRelayRoutePreparation(
            host = "relay.example.test",
            port = 443,
            relayId = identity.routeToken,
            relayFrameSecret = "secret-1",
            expiresAtEpochMillis = 4102444800000L,
            antiReplayNonce = "nonce-1",
        ).toPreparedRelayRouteOrNull(identity)

        assertNull(route)
    }

    @Test
    fun relayRoutePreparerUsesInjectedClockForLeaseExpiration() {
        val preparation = RuntimeRelayRoutePreparation(
            host = "relay.example.test",
            port = 443,
            relayId = "relay-1",
            relayFrameSecret = "secret-1",
            expiresAtEpochMillis = 2_000L,
            antiReplayNonce = "nonce-1",
        )

        val freshRoutes = RuntimeRelayRoutePreparer(nowEpochMillis = { 1_000L }) {
            listOf(preparation)
        }.prepareRemoteRoutes(identity)
        val expiredRoutes = RuntimeRelayRoutePreparer(nowEpochMillis = { 3_000L }) {
            listOf(preparation)
        }.prepareRemoteRoutes(identity)

        assertEquals("relay-1", (freshRoutes.single() as PreparedRemoteRuntimeRoute.Relay).relayId)
        assertEquals(emptyList<PreparedRemoteRuntimeRoute>(), expiredRoutes)
    }

    @Test
    fun missingExpirationAndNonceRejectRelayRoutePreparation() {
        val route = RuntimeRelayRoutePreparation(
            host = "relay.example.test",
            port = 443,
            relayId = "relay-1",
            relayFrameSecret = "secret-1",
            expiresAtEpochMillis = null,
            antiReplayNonce = null,
        ).toPreparedRelayRouteOrNull(identity)

        assertNull(route)
    }

    @Test
    fun relayRoutePreparerDropsInvalidRoutePreparations() {
        val preparer = RuntimeRelayRoutePreparer {
            listOf(
                RuntimeRelayRoutePreparation(
                    host = "",
                    port = 443,
                    relayId = "relay-invalid",
                    relayFrameSecret = "secret-1",
                    expiresAtEpochMillis = 4102444800000L,
                    antiReplayNonce = "nonce-invalid",
                ),
                RuntimeRelayRoutePreparation(
                    host = "relay.example.test",
                    port = 443,
                    relayId = "relay-valid",
                    relayFrameSecret = "secret-2",
                    expiresAtEpochMillis = 4102444800000L,
                    antiReplayNonce = "nonce-valid",
                ),
            )
        }

        val routes = preparer.prepareRemoteRoutes(identity)

        assertEquals(1, routes.size)
        assertEquals("relay-valid", (routes.single() as PreparedRemoteRuntimeRoute.Relay).relayId)
    }

    private val identity = PairedRuntimeIdentity(
        deviceId = "runtime-1",
        name = "AetherLink Runtime",
        fingerprint = "runtime-fingerprint",
        publicKeyBase64 = "runtime-public-key",
        routeToken = "route-token",
    )
}

private const val TEST_OPAQUE_RELAY_ROUTE_VALUE_MAX_CHARS = 512
