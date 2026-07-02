package com.localagentbridge.android.core.transport

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class RuntimePeerToPeerRoutePreparationTest {
    @Test
    fun validPeerToPeerRoutePreparationMapsToPreparedPeerToPeerRoute() {
        val route = RuntimePeerToPeerRoutePreparation(
            recordId = "p2p-record-1",
            encryptedCandidateMaterial = "opaque-candidate-material-1",
            expiresAtEpochMillis = 4102444800000L,
            antiReplayNonce = "nonce-1",
            protocolVersion = CURRENT_P2P_RENDEZVOUS_PROTOCOL_VERSION,
        ).toPreparedPeerToPeerRouteOrNull(identity)

        assertNotNull(route)
        requireNotNull(route)
        assertEquals(identity, route.identity)
        assertEquals("p2p-record-1", route.sessionId)
        assertEquals("opaque-candidate-material-1", route.encryptedCandidateMaterial)
        assertEquals("p2p-record-1", route.security.rendezvousToken)
        assertEquals(4102444800000L, route.security.expiresAtEpochMillis)
        assertEquals("nonce-1", route.security.antiReplayNonce)
    }

    @Test
    fun invalidPeerToPeerRoutePreparationReturnsNull() {
        val valid = RuntimePeerToPeerRoutePreparation(
            recordId = "p2p-record-1",
            encryptedCandidateMaterial = "opaque-candidate-material-1",
            expiresAtEpochMillis = 4102444800000L,
            antiReplayNonce = "nonce-1",
            protocolVersion = CURRENT_P2P_RENDEZVOUS_PROTOCOL_VERSION,
        )

        assertNull(valid.copy(recordId = null).toPreparedPeerToPeerRouteOrNull(identity))
        assertNull(valid.copy(recordId = "").toPreparedPeerToPeerRouteOrNull(identity))
        assertNull(valid.copy(recordId = " p2p-record-1").toPreparedPeerToPeerRouteOrNull(identity))
        assertNull(valid.copy(recordId = "p2p record 1").toPreparedPeerToPeerRouteOrNull(identity))
        assertNull(valid.copy(encryptedCandidateMaterial = null).toPreparedPeerToPeerRouteOrNull(identity))
        assertNull(valid.copy(encryptedCandidateMaterial = "").toPreparedPeerToPeerRouteOrNull(identity))
        assertNull(valid.copy(encryptedCandidateMaterial = "opaque material").toPreparedPeerToPeerRouteOrNull(identity))
        assertNull(valid.copy(expiresAtEpochMillis = null).toPreparedPeerToPeerRouteOrNull(identity))
        assertNull(valid.copy(expiresAtEpochMillis = 1L).toPreparedPeerToPeerRouteOrNull(identity))
        assertNull(valid.copy(antiReplayNonce = null).toPreparedPeerToPeerRouteOrNull(identity))
        assertNull(valid.copy(antiReplayNonce = "").toPreparedPeerToPeerRouteOrNull(identity))
        assertNull(valid.copy(antiReplayNonce = "nonce 1").toPreparedPeerToPeerRouteOrNull(identity))
        assertNull(valid.copy(protocolVersion = null).toPreparedPeerToPeerRouteOrNull(identity))
        assertNull(valid.copy(protocolVersion = 2).toPreparedPeerToPeerRouteOrNull(identity))
    }

    @Test
    fun oversizedPeerToPeerRoutePreparationReturnsNull() {
        val valid = RuntimePeerToPeerRoutePreparation(
            recordId = "p2p-record-1",
            encryptedCandidateMaterial = "opaque-candidate-material-1",
            expiresAtEpochMillis = 4102444800000L,
            antiReplayNonce = "nonce-1",
            protocolVersion = CURRENT_P2P_RENDEZVOUS_PROTOCOL_VERSION,
        )
        val oversizedValue = "r".repeat(TEST_OPAQUE_ROUTE_VALUE_MAX_CHARS + 1)
        val oversizedBody = "b".repeat(TEST_OPAQUE_ROUTE_BODY_MAX_CHARS + 1)

        assertNull(valid.copy(recordId = oversizedValue).toPreparedPeerToPeerRouteOrNull(identity))
        assertNull(valid.copy(encryptedCandidateMaterial = oversizedBody).toPreparedPeerToPeerRouteOrNull(identity))
        assertNull(valid.copy(antiReplayNonce = oversizedValue).toPreparedPeerToPeerRouteOrNull(identity))
    }

    @Test
    fun peerToPeerRoutePreparationDoesNotCarryHostOrPortMaterial() {
        val preparationFields = RuntimePeerToPeerRoutePreparation::class.java.declaredFields
            .map { it.name.lowercase() }
        val preparedFields = PreparedRemoteRuntimeRoute.PeerToPeer::class.java.declaredFields
            .map { it.name.lowercase() }

        assertTrue(preparationFields.none { it.contains("host") || it.contains("port") })
        assertTrue(preparedFields.none { it.contains("host") || it.contains("port") })
    }

    @Test
    fun peerToPeerRoutePreparerUsesInjectedClockForRecordExpiration() {
        val preparation = RuntimePeerToPeerRoutePreparation(
            recordId = "p2p-record-1",
            encryptedCandidateMaterial = "opaque-candidate-material-1",
            expiresAtEpochMillis = 2_000L,
            antiReplayNonce = "nonce-1",
            protocolVersion = CURRENT_P2P_RENDEZVOUS_PROTOCOL_VERSION,
        )

        val freshRoutes = RuntimePeerToPeerRoutePreparer(nowEpochMillis = { 1_000L }) {
            listOf(preparation)
        }.prepareRemoteRoutes(identity)
        val expiredRoutes = RuntimePeerToPeerRoutePreparer(nowEpochMillis = { 3_000L }) {
            listOf(preparation)
        }.prepareRemoteRoutes(identity)

        assertEquals("p2p-record-1", (freshRoutes.single() as PreparedRemoteRuntimeRoute.PeerToPeer).sessionId)
        assertEquals(emptyList<PreparedRemoteRuntimeRoute>(), expiredRoutes)
    }

    @Test
    fun peerToPeerRoutePreparerDropsInvalidRoutePreparations() {
        val preparer = RuntimePeerToPeerRoutePreparer {
            listOf(
                RuntimePeerToPeerRoutePreparation(
                    recordId = "",
                    encryptedCandidateMaterial = "opaque-candidate-material-1",
                    expiresAtEpochMillis = 4102444800000L,
                    antiReplayNonce = "nonce-invalid",
                    protocolVersion = CURRENT_P2P_RENDEZVOUS_PROTOCOL_VERSION,
                ),
                RuntimePeerToPeerRoutePreparation(
                    recordId = "p2p-record-valid",
                    encryptedCandidateMaterial = "opaque-candidate-material-2",
                    expiresAtEpochMillis = 4102444800000L,
                    antiReplayNonce = "nonce-valid",
                    protocolVersion = CURRENT_P2P_RENDEZVOUS_PROTOCOL_VERSION,
                ),
            )
        }

        val routes = preparer.prepareRemoteRoutes(identity)

        assertEquals(1, routes.size)
        assertEquals("p2p-record-valid", (routes.single() as PreparedRemoteRuntimeRoute.PeerToPeer).sessionId)
    }

    private val identity = PairedRuntimeIdentity(
        deviceId = "runtime-1",
        name = "AetherLink Runtime",
        fingerprint = "runtime-fingerprint",
        publicKeyBase64 = "runtime-public-key",
        routeToken = "route-token",
    )
}

private const val TEST_OPAQUE_ROUTE_VALUE_MAX_CHARS = 512
private const val TEST_OPAQUE_ROUTE_BODY_MAX_CHARS = 2048
