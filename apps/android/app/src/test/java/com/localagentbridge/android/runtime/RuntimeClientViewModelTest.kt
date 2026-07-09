package com.localagentbridge.android.runtime

import android.app.Application
import com.localagentbridge.android.core.protocol.AuthResponsePayload
import com.localagentbridge.android.core.protocol.ChatCancelPayload
import com.localagentbridge.android.core.protocol.ChatAttachmentPayload
import com.localagentbridge.android.core.protocol.ChatDeltaPayload
import com.localagentbridge.android.core.protocol.ChatDonePayload
import com.localagentbridge.android.core.protocol.ChatSendPayload
import com.localagentbridge.android.core.protocol.ChatMessagesListResultPayload
import com.localagentbridge.android.core.protocol.ChatSessionsListRequestPayload
import com.localagentbridge.android.core.protocol.ChatSessionsListResultPayload
import com.localagentbridge.android.core.protocol.ChatSessionLifecyclePayload
import com.localagentbridge.android.core.protocol.ChatSessionSearchPayload
import com.localagentbridge.android.core.protocol.ChatSessionSummaryPayload
import com.localagentbridge.android.core.protocol.ChatStoredAttachmentPayload
import com.localagentbridge.android.core.protocol.ChatStoredMessagePayload
import com.localagentbridge.android.core.protocol.ChatTitleResultPayload
import com.localagentbridge.android.core.protocol.ErrorPayload
import com.localagentbridge.android.core.protocol.IndexDocumentsListRequestPayload
import com.localagentbridge.android.core.protocol.IndexDocumentsListResultPayload
import com.localagentbridge.android.core.protocol.IndexDocumentsQualityCountsPayload
import com.localagentbridge.android.core.protocol.IndexDocumentsSummaryPayload
import com.localagentbridge.android.core.protocol.MemoryEntryPayload
import com.localagentbridge.android.core.protocol.MemoryEntrySourcePayload
import com.localagentbridge.android.core.protocol.MemoryDeleteResultPayload
import com.localagentbridge.android.core.protocol.MemoryListRequestPayload
import com.localagentbridge.android.core.protocol.MemoryListResultPayload
import com.localagentbridge.android.core.protocol.MemorySummaryDraftApprovePayload
import com.localagentbridge.android.core.protocol.MemorySummaryDraftApproveResultPayload
import com.localagentbridge.android.core.protocol.MemorySummaryDraftDismissPayload
import com.localagentbridge.android.core.protocol.MemorySummaryDraftDismissResultPayload
import com.localagentbridge.android.core.protocol.MemorySummaryDraftPayload
import com.localagentbridge.android.core.protocol.MemorySummaryDraftSessionPayload
import com.localagentbridge.android.core.protocol.MemorySummaryDraftSourcePointerPayload
import com.localagentbridge.android.core.protocol.MemorySummaryDraftsListResultPayload
import com.localagentbridge.android.core.protocol.MemoryUpsertResultPayload
import com.localagentbridge.android.core.protocol.MessageType
import com.localagentbridge.android.core.protocol.ModelInfoPayload
import com.localagentbridge.android.core.protocol.ModelPullPayload
import com.localagentbridge.android.core.protocol.ModelPullResultPayload
import com.localagentbridge.android.core.protocol.ModelsResultPayload
import com.localagentbridge.android.core.protocol.PairingRequestPayload
import com.localagentbridge.android.core.protocol.PairingResultPayload
import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import com.localagentbridge.android.core.protocol.RetrievalQueryRequestPayload
import com.localagentbridge.android.core.protocol.RetrievalQueryResultItemPayload
import com.localagentbridge.android.core.protocol.RetrievalQueryResultPayload
import com.localagentbridge.android.core.protocol.RouteRefreshPayload
import com.localagentbridge.android.core.protocol.RuntimeDocumentIndexDocumentPayload
import com.localagentbridge.android.core.protocol.RuntimeBackendStatusPayload
import com.localagentbridge.android.core.protocol.RuntimeHealthPayload
import com.localagentbridge.android.core.protocol.RuntimeModelResidencyPayload
import com.localagentbridge.android.core.protocol.RuntimeModelResidencyUnloadFailurePayload
import com.localagentbridge.android.core.pairing.DeviceIdentity
import com.localagentbridge.android.core.pairing.OPAQUE_ROUTE_BODY_MAX_CHARS
import com.localagentbridge.android.core.pairing.RelaySecretStore
import com.localagentbridge.android.core.pairing.RuntimePairingPayload
import com.localagentbridge.android.core.pairing.RuntimePairingPayloadParser
import com.localagentbridge.android.core.pairing.TrustedRuntime
import com.localagentbridge.android.core.transport.DiscoveredRuntime
import com.localagentbridge.android.core.transport.PairedRuntimeIdentity
import com.localagentbridge.android.core.transport.PreparedRemoteRuntimeRoute
import com.localagentbridge.android.core.transport.RemoteRouteSecurityContext
import com.localagentbridge.android.core.transport.RuntimeConnectionFailure
import com.localagentbridge.android.core.transport.RuntimeConnectionFailureReason
import com.localagentbridge.android.core.transport.RuntimeConnectionManager
import com.localagentbridge.android.core.transport.RuntimeConnectionTarget
import com.localagentbridge.android.core.transport.RuntimeEndpointHint
import com.localagentbridge.android.core.transport.RuntimeEndpointSource
import com.localagentbridge.android.core.transport.RuntimePeerToPeerConnector
import com.localagentbridge.android.core.transport.RuntimeProtocolChannel
import com.localagentbridge.android.core.transport.RuntimeRelayConnector
import com.localagentbridge.android.core.transport.RuntimeRouteCapability
import com.localagentbridge.android.core.transport.RuntimeRouteCandidate
import com.localagentbridge.android.core.transport.RuntimeRouteAttemptFailure
import com.localagentbridge.android.core.transport.RuntimeRouteRejection
import com.localagentbridge.android.core.transport.RuntimeRouteRejectionReason
import com.localagentbridge.android.core.transport.RuntimeRouteResolver
import com.localagentbridge.android.core.transport.RuntimeRouteSource
import com.localagentbridge.android.core.transport.RuntimeTransportConnector
import com.localagentbridge.android.core.transport.RuntimeTransportClient
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import kotlinx.coroutines.test.TestScope
import kotlinx.serialization.encodeToString
import kotlinx.serialization.KSerializer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.encodeToJsonElement
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.security.KeyPairGenerator
import java.security.spec.ECGenParameterSpec

class RuntimeClientViewModelTest {
    @Test
    fun trustedRuntimeConnectionTargetDropsTrustedLastKnownEndpoint() {
        val state = RuntimeUiState(
            runtimeHost = "127.0.0.1",
            runtimePort = "43169",
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "mac-1",
                name = "AetherLink Runtime",
                endpointHint = RuntimeEndpointHint(
                    host = "192.168.1.20",
                    port = 43170,
                    source = RuntimeEndpointSource.TrustedLastKnown,
                ),
            ),
        )

        val target = trustedRuntimeConnectionTarget(state)

        assertEquals("mac-1", target?.identity?.deviceId)
        assertEquals("AetherLink Runtime", target?.identity?.name)
        assertNull(target?.endpointHint)
    }

    @Test
    fun trustedRuntimeConnectionTargetAllowsTrustedIdentityWithoutEndpointHint() {
        val state = RuntimeUiState(
            runtimeHost = "127.0.0.1",
            runtimePort = "43170",
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "mac-identity-only",
                name = "AetherLink Runtime",
                fingerprint = "fingerprint",
                endpointHint = null,
            ),
        )

        val target = trustedRuntimeConnectionTarget(state)

        assertEquals("mac-identity-only", target?.identity?.deviceId)
        assertEquals("AetherLink Runtime", target?.identity?.name)
        assertEquals("fingerprint", target?.identity?.fingerprint)
        assertNull(target?.endpointHint)
    }

    @Test
    fun discoveredRuntimeSelectionRequiresTrustedIdentityMetadata() {
        val trustedState = RuntimeUiState(
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "runtime-1",
                name = "AetherLink Runtime",
                fingerprint = "fingerprint",
                routeToken = "route-token",
            ),
        )

        assertTrue(
            discoveredRuntimeSelectableForTrustState(
                state = trustedState,
                pendingPairingPayload = null,
                peer = RuntimeDiscoveredRuntime(
                    serviceName = "AetherLink Runtime",
                    host = "192.168.1.20",
                    port = 43170,
                    routeToken = "route-token",
                ),
            ),
        )
        assertFalse(
            discoveredRuntimeSelectableForTrustState(
                state = trustedState,
                pendingPairingPayload = null,
                peer = RuntimeDiscoveredRuntime(
                    serviceName = "AetherLink Runtime",
                    host = "192.168.1.20",
                    port = 43170,
                ),
            ),
        )
        assertFalse(
            discoveredRuntimeSelectableForTrustState(
                state = trustedState,
                pendingPairingPayload = null,
                peer = RuntimeDiscoveredRuntime(
                    serviceName = "AetherLink Runtime",
                    host = "192.168.1.20",
                    port = 43170,
                    routeToken = "other-route",
                ),
            ),
        )
    }

    @Test
    fun discoveredRuntimeSelectionCanUsePendingPairingIdentityBeforeTrustIsSaved() {
        val payload = RuntimePairingPayload(
            pairingNonce = "nonce-1",
            pairingCode = "123456",
            runtimeDeviceId = "runtime-1",
            runtimeName = "AetherLink Runtime",
            fingerprint = "fingerprint",
            runtimePublicKeyBase64 = null,
            routeToken = "route-token",
            host = null,
            port = null,
            serviceType = null,
        )

        assertTrue(
            discoveredRuntimeSelectableForTrustState(
                state = RuntimeUiState(),
                pendingPairingPayload = payload,
                peer = RuntimeDiscoveredRuntime(
                    serviceName = "AetherLink Runtime",
                    host = "192.168.1.20",
                    port = 43170,
                    routeToken = "route-token",
                ),
            ),
        )
        assertFalse(
            discoveredRuntimeSelectableForTrustState(
                state = RuntimeUiState(),
                pendingPairingPayload = payload,
                peer = RuntimeDiscoveredRuntime(
                    serviceName = "AetherLink Runtime",
                    host = "192.168.1.20",
                    port = 43170,
                ),
            ),
        )
    }

    @Test
    fun trustedRuntimeConnectionTargetOmitsDirectEndpointWhenRelayRouteIsSaved() {
        val state = RuntimeUiState(
            runtimeHost = "192.168.1.20",
            runtimePort = "43170",
            runtimeEndpointSource = RuntimeEndpointSource.PairingQr,
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "runtime-relay",
                name = "AetherLink Runtime",
                fingerprint = "fingerprint",
                endpointHint = RuntimeEndpointHint(
                    host = "192.168.1.20",
                    port = 43170,
                    source = RuntimeEndpointSource.TrustedLastKnown,
                ),
                relayHost = "relay.example.test",
                relayPort = 443,
                relayId = "relay-1",
                relaySecret = "secret-1",
                relayExpiresAtEpochMillis = 4102444800000L,
                relayNonce = "nonce-route-1",
            ),
        )

        val target = trustedRuntimeConnectionTarget(state)

        assertEquals("runtime-relay", target?.identity?.deviceId)
        assertNull(target?.endpointHint)
    }

    @Test
    fun trustedRuntimeConnectionTargetOmitsDirectEndpointWhenP2pRouteIsSaved() {
        val state = RuntimeUiState(
            runtimeHost = "192.168.1.20",
            runtimePort = "43170",
            runtimeEndpointSource = RuntimeEndpointSource.PairingQr,
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "runtime-p2p",
                name = "AetherLink Runtime",
                fingerprint = "fingerprint",
                endpointHint = RuntimeEndpointHint(
                    host = "192.168.1.20",
                    port = 43170,
                    source = RuntimeEndpointSource.TrustedLastKnown,
                ),
                p2pRouteClass = "p2p_rendezvous",
                p2pRecordId = "p2p-record-1",
                p2pEncryptedBody = "opaque-candidate-1",
                p2pExpiresAtEpochMillis = 4102444800000L,
                p2pAntiReplayNonce = "nonce-p2p-1",
                p2pProtocolVersion = 1,
            ),
        )

        val target = trustedRuntimeConnectionTarget(state)

        assertEquals("runtime-p2p", target?.identity?.deviceId)
        assertNull(target?.endpointHint)
    }

    @Test
    fun trustedRuntimeRelayReconnectUsesStoredQrLeaseMetadata() {
        val trusted = RuntimeTrustedRuntime(
            deviceId = "runtime-relay",
            name = "AetherLink Runtime",
            fingerprint = "fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            endpointHint = null,
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-1",
        )
        val planner = RuntimeRemoteRoutePlanner(
            pendingPairingPayload = { null },
            trustedRuntime = { trusted },
        )

        val route = planner.prepareRemoteRoutes(
            PairedRuntimeIdentity(
                deviceId = "runtime-relay",
                name = "AetherLink Runtime",
                fingerprint = "fingerprint",
                publicKeyBase64 = "runtime-public-key",
                routeToken = "route-token",
            )
        ).single() as PreparedRemoteRuntimeRoute.Relay

        assertEquals(4102444800000L, route.security.expiresAtEpochMillis)
        assertEquals("nonce-route-1", route.security.antiReplayNonce)
    }

    @Test
    fun trustedRuntimeP2pReconnectUsesStoredQrRendezvousMetadata() {
        val trusted = RuntimeTrustedRuntime(
            deviceId = "runtime-p2p",
            name = "AetherLink Runtime",
            fingerprint = "fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            endpointHint = null,
            p2pRouteClass = "p2p_rendezvous",
            p2pRecordId = "p2p-record-1",
            p2pEncryptedBody = "opaque-candidate-1",
            p2pExpiresAtEpochMillis = 4102444800000L,
            p2pAntiReplayNonce = "nonce-p2p-1",
            p2pProtocolVersion = 1,
        )
        val planner = RuntimeRemoteRoutePlanner(
            pendingPairingPayload = { null },
            trustedRuntime = { trusted },
        )

        val route = planner.prepareRemoteRoutes(
            PairedRuntimeIdentity(
                deviceId = "runtime-p2p",
                name = "AetherLink Runtime",
                fingerprint = "fingerprint",
                publicKeyBase64 = "runtime-public-key",
                routeToken = "route-token",
            )
        ).single() as PreparedRemoteRuntimeRoute.PeerToPeer

        assertEquals("p2p-record-1", route.sessionId)
        assertEquals("opaque-candidate-1", route.encryptedCandidateMaterial)
        assertEquals(4102444800000L, route.security.expiresAtEpochMillis)
        assertEquals("nonce-p2p-1", route.security.antiReplayNonce)
    }

    @Test
    fun runtimeRemoteRoutePlannerUsesInjectedClockForSavedRelayLease() {
        val trusted = RuntimeTrustedRuntime(
            deviceId = "runtime-relay",
            name = "AetherLink Runtime",
            fingerprint = "fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            endpointHint = null,
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 2_000L,
            relayNonce = "nonce-route-1",
        )
        val identity = PairedRuntimeIdentity(
            deviceId = "runtime-relay",
            name = "AetherLink Runtime",
            fingerprint = "fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
        )

        val freshRoutes = RuntimeRemoteRoutePlanner(
            pendingPairingPayload = { null },
            trustedRuntime = { trusted },
            nowEpochMillis = { 1_000L },
        ).prepareRemoteRoutes(identity)
        val expiredRoutes = RuntimeRemoteRoutePlanner(
            pendingPairingPayload = { null },
            trustedRuntime = { trusted },
            nowEpochMillis = { 3_000L },
        ).prepareRemoteRoutes(identity)

        val freshRoute = freshRoutes.single() as PreparedRemoteRuntimeRoute.Relay
        assertEquals("relay-1", freshRoute.relayId)
        assertEquals(2_000L, freshRoute.security.expiresAtEpochMillis)
        assertTrue(expiredRoutes.isEmpty())
    }

    @Test
    fun runtimeRemoteRoutePlannerRejectsNonCanonicalSavedRelayMaterial() {
        val baseTrusted = RuntimeTrustedRuntime(
            deviceId = "runtime-relay",
            name = "AetherLink Runtime",
            fingerprint = "fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            endpointHint = null,
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-1",
        )
        val identity = PairedRuntimeIdentity(
            deviceId = "runtime-relay",
            name = "AetherLink Runtime",
            fingerprint = "fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
        )
        val invalidRuntimes = listOf(
            baseTrusted.copy(relayId = "relay 1"),
            baseTrusted.copy(relaySecret = " secret-1"),
            baseTrusted.copy(relayNonce = "n".repeat(513)),
        )

        invalidRuntimes.forEach { trusted ->
            val routes = RuntimeRemoteRoutePlanner(
                pendingPairingPayload = { null },
                trustedRuntime = { trusted },
                nowEpochMillis = { 1_000L },
            ).prepareRemoteRoutes(identity)

            assertFalse(trusted.hasRelayRoute(nowEpochMillis = 1_000L))
            assertFalse(trusted.hasCompleteRemoteRouteMaterial())
            assertTrue(routes.isEmpty())
        }
    }

    @Test
    fun runtimeRemoteRoutePlannerRejectsNonCanonicalPendingRelayMaterial() {
        val basePayload = runtimePairingPayload(
            host = null,
            port = null,
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-1",
        )
        val identity = identityFor(basePayload)
        val invalidPayloads = listOf(
            basePayload.copy(relayId = "relay 1"),
            basePayload.copy(relaySecret = " secret-1"),
            basePayload.copy(relayNonce = "n".repeat(513)),
        )

        invalidPayloads.forEach { payload ->
            val routes = RuntimeRemoteRoutePlanner(
                pendingPairingPayload = { payload },
                trustedRuntime = { null },
                nowEpochMillis = { 1_000L },
            ).prepareRemoteRoutes(identity)

            assertFalse(payload.hasRelayRoute(nowEpochMillis = 1_000L))
            assertFalse(payload.hasRemoteRoute(nowEpochMillis = 1_000L))
            assertTrue(routes.isEmpty())
        }
    }

    @Test
    fun runtimeRemoteRoutePlannerUsesInjectedClockForSavedP2pRendezvousRecord() {
        val trusted = RuntimeTrustedRuntime(
            deviceId = "runtime-p2p",
            name = "AetherLink Runtime",
            fingerprint = "fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            endpointHint = null,
            p2pRouteClass = "p2p_rendezvous",
            p2pRecordId = "p2p-record-1",
            p2pEncryptedBody = "opaque-candidate-1",
            p2pExpiresAtEpochMillis = 2_000L,
            p2pAntiReplayNonce = "nonce-p2p-1",
            p2pProtocolVersion = 1,
        )
        val identity = PairedRuntimeIdentity(
            deviceId = "runtime-p2p",
            name = "AetherLink Runtime",
            fingerprint = "fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
        )

        val freshRoutes = RuntimeRemoteRoutePlanner(
            pendingPairingPayload = { null },
            trustedRuntime = { trusted },
            nowEpochMillis = { 1_000L },
        ).prepareRemoteRoutes(identity)
        val expiredRoutes = RuntimeRemoteRoutePlanner(
            pendingPairingPayload = { null },
            trustedRuntime = { trusted },
            nowEpochMillis = { 3_000L },
        ).prepareRemoteRoutes(identity)

        val freshRoute = freshRoutes.single() as PreparedRemoteRuntimeRoute.PeerToPeer
        assertEquals("p2p-record-1", freshRoute.sessionId)
        assertEquals(2_000L, freshRoute.security.expiresAtEpochMillis)
        assertTrue(expiredRoutes.isEmpty())
    }

    @Test
    fun trustedRuntimeRelayReconnectRejectsMismatchedPinnedIdentity() {
        val trusted = RuntimeTrustedRuntime(
            deviceId = "runtime-relay",
            name = "AetherLink Runtime",
            fingerprint = "pinned-fingerprint",
            publicKeyBase64 = "pinned-runtime-public-key",
            routeToken = "route-token",
            endpointHint = null,
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-1",
        )
        val planner = RuntimeRemoteRoutePlanner(
            pendingPairingPayload = { null },
            trustedRuntime = { trusted },
            nowEpochMillis = { 1_000L },
        )

        val fingerprintMismatch = planner.prepareRemoteRoutes(
            PairedRuntimeIdentity(
                deviceId = "runtime-relay",
                name = "AetherLink Runtime",
                fingerprint = "other-fingerprint",
                publicKeyBase64 = "pinned-runtime-public-key",
                routeToken = "route-token",
            )
        )
        val publicKeyMismatch = planner.prepareRemoteRoutes(
            PairedRuntimeIdentity(
                deviceId = "runtime-relay",
                name = "AetherLink Runtime",
                fingerprint = "pinned-fingerprint",
                publicKeyBase64 = "other-runtime-public-key",
                routeToken = "route-token",
            )
        )

        assertTrue(fingerprintMismatch.isEmpty())
        assertTrue(publicKeyMismatch.isEmpty())
    }

    @Test
    fun runtimeRemoteRoutePlannerUsesInjectedClockForPendingPairingRelayLease() {
        val payload = RuntimePairingPayload(
            pairingNonce = "nonce-1",
            pairingCode = "123456",
            runtimeDeviceId = "runtime-relay",
            runtimeName = "AetherLink Runtime",
            fingerprint = "fingerprint",
            runtimePublicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            host = null,
            port = null,
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 2_000L,
            relayNonce = "nonce-route-1",
            serviceType = "_aetherlink._tcp.local.",
        )
        val identity = identityFor(payload)

        val freshRoutes = RuntimeRemoteRoutePlanner(
            pendingPairingPayload = { payload },
            trustedRuntime = { null },
            nowEpochMillis = { 1_000L },
        ).prepareRemoteRoutes(identity)
        val expiredRoutes = RuntimeRemoteRoutePlanner(
            pendingPairingPayload = { payload },
            trustedRuntime = { null },
            nowEpochMillis = { 3_000L },
        ).prepareRemoteRoutes(identity)

        assertEquals("relay-1", (freshRoutes.single() as PreparedRemoteRuntimeRoute.Relay).relayId)
        assertTrue(expiredRoutes.isEmpty())
    }

    @Test
    fun runtimeRemoteRoutePlannerPlansPendingP2pRendezvousBeforeRelayRoute() {
        val payload = RuntimePairingPayload(
            pairingNonce = "nonce-1",
            pairingCode = "123456",
            runtimeDeviceId = "runtime-relay",
            runtimeName = "AetherLink Runtime",
            fingerprint = "fingerprint",
            runtimePublicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            host = null,
            port = null,
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-1",
            p2pRouteClass = "p2p_rendezvous",
            p2pRecordId = "p2p-record-1",
            p2pEncryptedBody = "opaque-candidate-1",
            p2pExpiresAtEpochMillis = 4102444800000L,
            p2pAntiReplayNonce = "nonce-p2p-1",
            p2pProtocolVersion = 1,
            serviceType = "_aetherlink._tcp.local.",
        )
        val identity = identityFor(payload)

        val routes = RuntimeRemoteRoutePlanner(
            pendingPairingPayload = { payload },
            trustedRuntime = { null },
            nowEpochMillis = { 1_000L },
        ).prepareRemoteRoutes(identity)

        assertEquals(
            listOf(RuntimeRouteCapability.PeerToPeer, RuntimeRouteCapability.Relay),
            routes.map { it.capability },
        )
        val p2pRoute = routes.first() as PreparedRemoteRuntimeRoute.PeerToPeer
        assertEquals("p2p-record-1", p2pRoute.sessionId)
        assertEquals("opaque-candidate-1", p2pRoute.encryptedCandidateMaterial)
        assertEquals("nonce-p2p-1", p2pRoute.security.antiReplayNonce)
        assertEquals("relay-1", (routes[1] as PreparedRemoteRuntimeRoute.Relay).relayId)
    }

    @Test
    fun runtimeRemoteRoutePlannerUsesInjectedClockForPendingP2pRendezvousRecord() {
        val payload = RuntimePairingPayload(
            pairingNonce = "nonce-1",
            pairingCode = "123456",
            runtimeDeviceId = "runtime-relay",
            runtimeName = "AetherLink Runtime",
            fingerprint = "fingerprint",
            runtimePublicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            host = null,
            port = null,
            p2pRouteClass = "p2p_rendezvous",
            p2pRecordId = "p2p-record-1",
            p2pEncryptedBody = "opaque-candidate-1",
            p2pExpiresAtEpochMillis = 2_000L,
            p2pAntiReplayNonce = "nonce-p2p-1",
            p2pProtocolVersion = 1,
            serviceType = "_aetherlink._tcp.local.",
        )
        val identity = identityFor(payload)

        val freshRoutes = RuntimeRemoteRoutePlanner(
            pendingPairingPayload = { payload },
            trustedRuntime = { null },
            nowEpochMillis = { 1_000L },
        ).prepareRemoteRoutes(identity)
        val expiredRoutes = RuntimeRemoteRoutePlanner(
            pendingPairingPayload = { payload },
            trustedRuntime = { null },
            nowEpochMillis = { 3_000L },
        ).prepareRemoteRoutes(identity)

        assertEquals("p2p-record-1", (freshRoutes.single() as PreparedRemoteRuntimeRoute.PeerToPeer).sessionId)
        assertTrue(expiredRoutes.isEmpty())
    }

    @Test
    fun trustedRuntimeRelayReconnectRejectsExpiredSavedRelayLease() {
        val trusted = RuntimeTrustedRuntime(
            deviceId = "runtime-relay",
            name = "AetherLink Runtime",
            fingerprint = "fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            endpointHint = null,
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 1L,
            relayNonce = "stale-qr-nonce",
        )
        val planner = RuntimeRemoteRoutePlanner(
            pendingPairingPayload = { null },
            trustedRuntime = { trusted },
        )

        val target = autoReconnectTrustedRuntimeConnectionTarget(
            RuntimeUiState(trustedRuntime = trusted)
        )
        val routes = planner.prepareRemoteRoutes(
            PairedRuntimeIdentity(
                deviceId = "runtime-relay",
                name = "AetherLink Runtime",
                fingerprint = "fingerprint",
                publicKeyBase64 = "runtime-public-key",
                routeToken = "route-token",
            )
        )

        assertNull(target)
        assertTrue(routes.isEmpty())
    }

    @Test
    fun trustedRuntimeRelayReconnectRejectsIncompleteSavedRelayLease() {
        val trusted = RuntimeTrustedRuntime(
            deviceId = "runtime-relay",
            name = "AetherLink Runtime",
            fingerprint = "fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            endpointHint = null,
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = null,
            relayNonce = null,
        )
        val planner = RuntimeRemoteRoutePlanner(
            pendingPairingPayload = { null },
            trustedRuntime = { trusted },
        )

        val target = autoReconnectTrustedRuntimeConnectionTarget(
            RuntimeUiState(trustedRuntime = trusted)
        )
        val routes = planner.prepareRemoteRoutes(
            PairedRuntimeIdentity(
                deviceId = "runtime-relay",
                name = "AetherLink Runtime",
                fingerprint = "fingerprint",
                publicKeyBase64 = "runtime-public-key",
                routeToken = "route-token",
            )
        )

        assertNull(target)
        assertTrue(routes.isEmpty())
    }

    @Test
    fun trustedRuntimeRelayReconnectIgnoresLoopbackRelayRoute() {
        val trusted = RuntimeTrustedRuntime(
            deviceId = "runtime-relay",
            name = "AetherLink Runtime",
            fingerprint = "fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            endpointHint = null,
            relayHost = "127.0.0.1",
            relayPort = 63664,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-1",
        )
        val planner = RuntimeRemoteRoutePlanner(
            pendingPairingPayload = { null },
            trustedRuntime = { trusted },
        )

        val routes = planner.prepareRemoteRoutes(
            PairedRuntimeIdentity(
                deviceId = "runtime-relay",
                name = "AetherLink Runtime",
                fingerprint = "fingerprint",
                publicKeyBase64 = "runtime-public-key",
                routeToken = "route-token",
            )
        )

        assertTrue(routes.isEmpty())
    }

    @Test
    fun trustedRuntimeRelayReconnectAllowsDebugUsbReverseRelayRoute() {
        val trusted = RuntimeTrustedRuntime(
            deviceId = "runtime-relay",
            name = "AetherLink Runtime",
            fingerprint = "fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            endpointHint = null,
            relayHost = "127.0.0.1",
            relayPort = 43171,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-1",
            relayScope = "usb_reverse",
        )
        val planner = RuntimeRemoteRoutePlanner(
            pendingPairingPayload = { null },
            trustedRuntime = { trusted },
        )

        val route = planner.prepareRemoteRoutes(
            PairedRuntimeIdentity(
                deviceId = "runtime-relay",
                name = "AetherLink Runtime",
                fingerprint = "fingerprint",
                publicKeyBase64 = "runtime-public-key",
                routeToken = "route-token",
            )
        ).single() as PreparedRemoteRuntimeRoute.Relay

        assertEquals("127.0.0.1", route.host)
        assertEquals(43171, route.port)
        assertEquals("relay-1", route.relayId)
        assertEquals(4102444800000L, route.security.expiresAtEpochMillis)
        assertEquals("nonce-route-1", route.security.antiReplayNonce)
    }

    @Test
    fun trustedRuntimeRelayReconnectAllowsPrivateOverlayRelayRoute() {
        val trusted = RuntimeTrustedRuntime(
            deviceId = "runtime-relay",
            name = "AetherLink Runtime",
            fingerprint = "fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            endpointHint = null,
            relayHost = "100.64.1.10",
            relayPort = 43171,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-1",
            relayScope = "private_overlay",
        )
        val planner = RuntimeRemoteRoutePlanner(
            pendingPairingPayload = { null },
            trustedRuntime = { trusted },
        )

        val route = planner.prepareRemoteRoutes(
            PairedRuntimeIdentity(
                deviceId = "runtime-relay",
                name = "AetherLink Runtime",
                fingerprint = "fingerprint",
                publicKeyBase64 = "runtime-public-key",
                routeToken = "route-token",
            )
        ).single() as PreparedRemoteRuntimeRoute.Relay

        assertEquals("100.64.1.10", route.host)
        assertEquals(43171, route.port)
        assertEquals("relay-1", route.relayId)
    }

    @Test
    fun trustedRuntimeRelayReconnectRejectsScopeLessPrivateRelayRoute() {
        val trusted = RuntimeTrustedRuntime(
            deviceId = "runtime-relay",
            name = "AetherLink Runtime",
            fingerprint = "fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            endpointHint = null,
            relayHost = "100.64.1.10",
            relayPort = 43171,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-1",
        )
        val planner = RuntimeRemoteRoutePlanner(
            pendingPairingPayload = { null },
            trustedRuntime = { trusted },
        )

        val routes = planner.prepareRemoteRoutes(
            PairedRuntimeIdentity(
                deviceId = "runtime-relay",
                name = "AetherLink Runtime",
                fingerprint = "fingerprint",
                publicKeyBase64 = "runtime-public-key",
                routeToken = "route-token",
            )
        )

        assertTrue(routes.isEmpty())
    }

    @Test
    fun autoReconnectTrustedRuntimeTargetUsesSavedRelayRouteWithoutManualEndpoint() {
        val trusted = RuntimeTrustedRuntime(
            deviceId = "runtime-relay",
            name = "AetherLink Runtime",
            fingerprint = "fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            endpointHint = null,
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-1",
        )

        val target = requireNotNull(
            autoReconnectTrustedRuntimeConnectionTarget(RuntimeUiState(trustedRuntime = trusted))
        )
        val plannedRoute = RuntimeRemoteRoutePlanner(
            pendingPairingPayload = { null },
            trustedRuntime = { trusted },
        ).prepareRemoteRoutes(requireNotNull(target.identity)).single() as PreparedRemoteRuntimeRoute.Relay

        assertNull(target.endpointHint)
        assertEquals("runtime-relay", target.identity?.deviceId)
        assertEquals("relay.example.test", plannedRoute.host)
        assertEquals(443, plannedRoute.port)
        assertEquals("relay-1", plannedRoute.relayId)
        assertEquals("secret-1", plannedRoute.relayFrameSecret)
        assertEquals(4102444800000L, plannedRoute.security.expiresAtEpochMillis)
        assertEquals("nonce-route-1", plannedRoute.security.antiReplayNonce)
    }

    @Test
    fun autoReconnectTrustedRuntimeTargetUsesSavedP2pRouteWithoutManualEndpoint() {
        val trusted = RuntimeTrustedRuntime(
            deviceId = "runtime-p2p",
            name = "AetherLink Runtime",
            fingerprint = "fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            endpointHint = null,
            p2pRouteClass = "p2p_rendezvous",
            p2pRecordId = "p2p-record-1",
            p2pEncryptedBody = "opaque-candidate-1",
            p2pExpiresAtEpochMillis = 4102444800000L,
            p2pAntiReplayNonce = "nonce-p2p-1",
            p2pProtocolVersion = 1,
        )

        val target = requireNotNull(
            autoReconnectTrustedRuntimeConnectionTarget(RuntimeUiState(trustedRuntime = trusted))
        )
        val plannedRoute = RuntimeRemoteRoutePlanner(
            pendingPairingPayload = { null },
            trustedRuntime = { trusted },
        ).prepareRemoteRoutes(requireNotNull(target.identity)).single() as PreparedRemoteRuntimeRoute.PeerToPeer

        assertNull(target.endpointHint)
        assertEquals("runtime-p2p", target.identity?.deviceId)
        assertEquals("p2p-record-1", plannedRoute.sessionId)
        assertEquals("opaque-candidate-1", plannedRoute.encryptedCandidateMaterial)
        assertEquals(4102444800000L, plannedRoute.security.expiresAtEpochMillis)
        assertEquals("nonce-p2p-1", plannedRoute.security.antiReplayNonce)
    }

    @Test
    fun trustedRuntimeRestoreShouldStartDiscoveryEvenWithoutEndpointHint() {
        val state = RuntimeUiState(
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "runtime-identity-only",
                name = "AetherLink Runtime",
                fingerprint = "fingerprint",
                endpointHint = null,
            ),
        )

        assertTrue(state.shouldDiscoverTrustedRuntimeRoute())
    }

    @Test
    fun trustedRuntimeRestoreDoesNotStartDiscoveryWhenRelayRouteIsAvailable() {
        val state = RuntimeUiState(
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "runtime-relay",
                name = "AetherLink Runtime",
                fingerprint = "fingerprint",
                endpointHint = null,
                relayHost = "relay.example.test",
                relayPort = 443,
                relayId = "relay-1",
                relaySecret = "secret-1",
                relayExpiresAtEpochMillis = 4102444800000L,
                relayNonce = "nonce-route-1",
            ),
        )

        assertFalse(state.shouldDiscoverTrustedRuntimeRoute())
        val target = requireNotNull(autoReconnectTrustedRuntimeConnectionTarget(state))
        assertEquals("runtime-relay", target.identity?.deviceId)
        assertNull(target.endpointHint)
    }

    @Test
    fun trustedRuntimeRestoreDoesNotStartDiscoveryWhenP2pRouteIsAvailable() {
        val state = RuntimeUiState(
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "runtime-p2p",
                name = "AetherLink Runtime",
                fingerprint = "fingerprint",
                endpointHint = null,
                p2pRouteClass = "p2p_rendezvous",
                p2pRecordId = "p2p-record-1",
                p2pEncryptedBody = "opaque-candidate-1",
                p2pExpiresAtEpochMillis = 4102444800000L,
                p2pAntiReplayNonce = "nonce-p2p-1",
                p2pProtocolVersion = 1,
            ),
        )

        assertFalse(state.shouldDiscoverTrustedRuntimeRoute())
        val target = requireNotNull(autoReconnectTrustedRuntimeConnectionTarget(state))
        assertEquals("runtime-p2p", target.identity?.deviceId)
        assertNull(target.endpointHint)
    }

    @Test
    fun trustedRuntimeRestoreDoesNotStartDiscoveryWhenAlreadyBusyOrUnpaired() {
        val trusted = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "fingerprint",
            endpointHint = null,
        )

        assertFalse(RuntimeUiState(trustedRuntime = null).shouldDiscoverTrustedRuntimeRoute())
        assertFalse(RuntimeUiState(trustedRuntime = trusted, isConnected = true).shouldDiscoverTrustedRuntimeRoute())
        assertFalse(RuntimeUiState(trustedRuntime = trusted, isConnecting = true).shouldDiscoverTrustedRuntimeRoute())
    }

    @Test
    fun pendingPairingStateShowsIdentityOnlyQrWaitingForRoute() {
        val state = RuntimeUiState(
            runtimeStatus = "disconnected",
            routeRefreshNoticeRuntimeName = "Previous Runtime",
        )
        val payload = RuntimePairingPayload(
            pairingNonce = "nonce-1",
            pairingCode = "123456",
            runtimeDeviceId = "runtime-identity-only",
            runtimeName = "AetherLink Runtime",
            fingerprint = "fingerprint",
            runtimePublicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            host = null,
            port = null,
            serviceType = "_aetherlink._tcp.local.",
        )

        val pending = state.withPendingPairing(payload)

        assertEquals("123456", pending.pairingCode)
        assertEquals("AetherLink Runtime", pending.pendingPairingRuntimeName)
        assertTrue(pending.isPairingAwaitingRoute)
        assertEquals("pairing", pending.runtimeStatus)
        assertEquals("", pending.runtimeHost)
        assertEquals("", pending.runtimePort)
        assertNull(pending.routeRefreshNoticeRuntimeName)

        val cleared = pending.withClearedPendingPairing()

        assertNull(cleared.pendingPairingRuntimeName)
        assertFalse(cleared.isPairingAwaitingRoute)
        assertEquals("", cleared.pairingCode)
        assertEquals("disconnected", cleared.runtimeStatus)
    }

    @Test
    fun pendingPairingStateUsesEndpointHintWhenQrHasDevelopmentRoute() {
        val state = RuntimeUiState(
            runtimeHost = "127.0.0.1",
            runtimePort = "43170",
            runtimeStatus = "disconnected",
        )
        val payload = RuntimePairingPayload(
            pairingNonce = "nonce-1",
            pairingCode = "123456",
            runtimeDeviceId = "runtime-1",
            runtimeName = "AetherLink Runtime",
            fingerprint = "fingerprint",
            runtimePublicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            host = "192.168.1.44",
            port = 43170,
            serviceType = "_aetherlink._tcp.local.",
        )

        val pending = state.withPendingPairing(payload)

        assertEquals("123456", pending.pairingCode)
        assertEquals("AetherLink Runtime", pending.pendingPairingRuntimeName)
        assertFalse(pending.isPairingAwaitingRoute)
        assertEquals("disconnected", pending.runtimeStatus)
        assertEquals("192.168.1.44", pending.runtimeHost)
        assertEquals("43170", pending.runtimePort)
        assertEquals(RuntimeEndpointSource.PairingQr, pending.runtimeEndpointSource)
    }

    @Test
    fun pendingPairingStateIgnoresEndpointHintWhenRelayQrHasDevelopmentRoute() {
        val state = RuntimeUiState(
            runtimeHost = "127.0.0.1",
            runtimePort = "43170",
            runtimeEndpointSource = RuntimeEndpointSource.UsbReverse,
            runtimeStatus = "disconnected",
        )
        val payload = RuntimePairingPayload(
            pairingNonce = "nonce-1",
            pairingCode = "123456",
            runtimeDeviceId = "runtime-relay",
            runtimeName = "AetherLink Runtime",
            fingerprint = "fingerprint",
            runtimePublicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            host = "192.168.1.44",
            port = 43170,
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-1",
            serviceType = "_aetherlink._tcp.local.",
        )

        val pending = state.withPendingPairing(payload)

        assertFalse(pending.isPairingAwaitingRoute)
        assertEquals("127.0.0.1", pending.runtimeHost)
        assertEquals("43170", pending.runtimePort)
        assertEquals(RuntimeEndpointSource.UsbReverse, pending.runtimeEndpointSource)
    }

    @Test
    fun identityOnlyPairingPayloadBuildsIdentityOnlyTarget() {
        val payload = RuntimePairingPayload(
            pairingNonce = "nonce-1",
            pairingCode = "123456",
            runtimeDeviceId = "runtime-identity-only",
            runtimeName = "AetherLink Runtime",
            fingerprint = "fingerprint",
            runtimePublicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            host = null,
            port = null,
            serviceType = "_aetherlink._tcp.local.",
        )

        val target = payload.toConnectionTarget()

        assertEquals("runtime-identity-only", target.identity?.deviceId)
        assertEquals("AetherLink Runtime", target.identity?.name)
        assertEquals("fingerprint", target.identity?.fingerprint)
        assertEquals("runtime-public-key", target.identity?.publicKeyBase64)
        assertEquals("route-token", target.identity?.routeToken)
        assertNull(target.endpointHint)
        assertTrue(payload.shouldWaitForDiscoveryRoute())
    }

    @Test
    fun pairingRuntimeTargetWaitsForDiscoveryWhenQrHasNoEndpoint() {
        val payload = RuntimePairingPayload(
            pairingNonce = "nonce-1",
            pairingCode = "123456",
            runtimeDeviceId = "runtime-identity-only",
            runtimeName = "AetherLink Runtime",
            fingerprint = "fingerprint",
            runtimePublicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            host = null,
            port = null,
            serviceType = "_aetherlink._tcp.local.",
        )

        assertNull(pairingRuntimeConnectionTarget(RuntimeUiState(), payload))
    }

    @Test
    fun pairingRuntimeTargetCanUseUsbReverseFallbackWhenQrHasNoEndpoint() {
        val payload = RuntimePairingPayload(
            pairingNonce = "nonce-1",
            pairingCode = "123456",
            runtimeDeviceId = "runtime-identity-only",
            runtimeName = "AetherLink Runtime",
            fingerprint = "fingerprint",
            runtimePublicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            host = null,
            port = null,
            serviceType = "_aetherlink._tcp.local.",
        )

        val target = pairingRuntimeConnectionTarget(
            state = RuntimeUiState(),
            payload = payload,
            allowUsbReverseFallback = true,
        )

        assertEquals("runtime-identity-only", target?.identity?.deviceId)
        assertEquals("127.0.0.1", target?.endpointHint?.host)
        assertEquals(43170, target?.endpointHint?.port)
        assertEquals(RuntimeEndpointSource.UsbReverse, target?.endpointHint?.source)
    }

    @Test
    fun newPairingQrPreemptsActiveUntrustedConnection() {
        val payload = RuntimePairingPayload(
            pairingNonce = "nonce-1",
            pairingCode = "123456",
            runtimeDeviceId = "runtime-new",
            runtimeName = "AetherLink Runtime",
            fingerprint = "fingerprint-new",
            runtimePublicKeyBase64 = "runtime-public-key-new",
            routeToken = "route-token-new",
            host = null,
            port = null,
            serviceType = "_aetherlink._tcp.local.",
        )

        assertTrue(
            shouldPreemptActiveConnectionForPairingQr(
                RuntimeUiState(isConnected = true),
                payload,
            )
        )
    }

    @Test
    fun newPairingQrPreemptsActiveDifferentTrustedRuntimeConnection() {
        val payload = RuntimePairingPayload(
            pairingNonce = "nonce-1",
            pairingCode = "123456",
            runtimeDeviceId = "runtime-new",
            runtimeName = "AetherLink Runtime",
            fingerprint = "fingerprint-new",
            runtimePublicKeyBase64 = "runtime-public-key-new",
            routeToken = "route-token-new",
            host = null,
            port = null,
            serviceType = "_aetherlink._tcp.local.",
        )
        val state = RuntimeUiState(
            isConnecting = true,
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "runtime-old",
                name = "Old Runtime",
                fingerprint = "fingerprint-old",
                publicKeyBase64 = "runtime-public-key-old",
            ),
        )

        assertTrue(shouldPreemptActiveConnectionForPairingQr(state, payload))
    }

    @Test
    fun sameRuntimePairingQrDoesNotPreemptActiveTrustedConnection() {
        val payload = RuntimePairingPayload(
            pairingNonce = "nonce-1",
            pairingCode = "123456",
            runtimeDeviceId = "runtime-1",
            runtimeName = "AetherLink Runtime",
            fingerprint = "fingerprint-1",
            runtimePublicKeyBase64 = "runtime-public-key-1",
            routeToken = "route-token-1",
            host = null,
            port = null,
            serviceType = "_aetherlink._tcp.local.",
        )
        val state = RuntimeUiState(
            isConnected = true,
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "runtime-1",
                name = "AetherLink Runtime",
                fingerprint = "fingerprint-1",
                publicKeyBase64 = "runtime-public-key-1",
                routeToken = "route-token-1",
            ),
        )

        assertFalse(shouldPreemptActiveConnectionForPairingQr(state, payload))
    }

    @Test
    fun pairingRuntimeTargetUsesRelayQrWithoutLocalEndpoint() {
        val payload = RuntimePairingPayload(
            pairingNonce = "nonce-1",
            pairingCode = "123456",
            runtimeDeviceId = "runtime-identity-only",
            runtimeName = "AetherLink Runtime",
            fingerprint = "fingerprint",
            runtimePublicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            host = null,
            port = null,
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-1",
            serviceType = "_aetherlink._tcp.local.",
        )

        val target = pairingRuntimeConnectionTarget(RuntimeUiState(), payload)

        assertEquals("runtime-identity-only", target?.identity?.deviceId)
        assertEquals("fingerprint", target?.identity?.fingerprint)
        assertEquals("route-token", target?.identity?.routeToken)
        assertNull(target?.endpointHint)
    }

    @Test
    fun pendingPairingRelayQrOverridesSavedRelayRoute() {
        val payload = RuntimePairingPayload(
            pairingNonce = "nonce-1",
            pairingCode = "123456",
            runtimeDeviceId = "runtime-relay",
            runtimeName = "AetherLink Runtime",
            fingerprint = "fingerprint",
            runtimePublicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            host = null,
            port = null,
            relayHost = "relay-from-qr.example.test",
            relayPort = 443,
            relayId = "relay-from-qr",
            relaySecret = "qr-secret",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "qr-nonce",
            serviceType = "_aetherlink._tcp.local.",
        )
        val trusted = RuntimeTrustedRuntime(
            deviceId = "runtime-relay",
            name = "AetherLink Runtime",
            fingerprint = "fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            endpointHint = RuntimeEndpointHint(
                host = "192.168.1.44",
                port = 43170,
                source = RuntimeEndpointSource.TrustedLastKnown,
            ),
            relayHost = "saved-relay.example.test",
            relayPort = 444,
            relayId = "saved-relay",
            relaySecret = "saved-secret",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "saved-nonce",
        )

        val route = RuntimeRemoteRoutePlanner(
            pendingPairingPayload = { payload },
            trustedRuntime = { trusted },
        ).prepareRemoteRoutes(identityFor(payload)).single() as PreparedRemoteRuntimeRoute.Relay

        assertEquals("relay-from-qr.example.test", route.host)
        assertEquals(443, route.port)
        assertEquals("relay-from-qr", route.relayId)
        assertEquals("qr-secret", route.relayFrameSecret)
        assertEquals("qr-nonce", route.security.antiReplayNonce)
    }

    @Test
    fun pendingPairingQrWithoutRemoteRouteDoesNotFallbackToSavedRelayRoute() {
        val payload = RuntimePairingPayload(
            pairingNonce = "nonce-1",
            pairingCode = "123456",
            runtimeDeviceId = "runtime-relay",
            runtimeName = "AetherLink Runtime",
            fingerprint = "fingerprint",
            runtimePublicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            host = null,
            port = null,
            serviceType = "_aetherlink._tcp.local.",
        )
        val trusted = RuntimeTrustedRuntime(
            deviceId = "runtime-relay",
            name = "AetherLink Runtime",
            fingerprint = "fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            endpointHint = RuntimeEndpointHint(
                host = "192.168.1.44",
                port = 43170,
                source = RuntimeEndpointSource.TrustedLastKnown,
            ),
            relayHost = "saved-relay.example.test",
            relayPort = 443,
            relayId = "saved-relay",
            relaySecret = "saved-secret",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "saved-nonce",
        )

        val routes = RuntimeRemoteRoutePlanner(
            pendingPairingPayload = { payload },
            trustedRuntime = { trusted },
        ).prepareRemoteRoutes(identityFor(payload))

        assertTrue(routes.isEmpty())
    }

    @Test
    fun pairingRuntimeTargetUsesDebugUsbReverseRelayQr() {
        val payload = RuntimePairingPayload(
            pairingNonce = "nonce-1",
            pairingCode = "123456",
            runtimeDeviceId = "runtime-usb",
            runtimeName = "AetherLink Dev Runtime",
            fingerprint = "fingerprint",
            runtimePublicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            host = null,
            port = null,
            relayHost = "127.0.0.1",
            relayPort = 43171,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-1",
            relayScope = "usb_reverse",
            serviceType = "_aetherlink._tcp.local.",
        )

        val target = pairingRuntimeConnectionTarget(RuntimeUiState(), payload)
        val plannedRoute = RuntimeRemoteRoutePlanner(
            pendingPairingPayload = { payload },
            trustedRuntime = { null },
        ).prepareRemoteRoutes(requireNotNull(target?.identity)).single() as PreparedRemoteRuntimeRoute.Relay

        assertNull(target.endpointHint)
        assertEquals("127.0.0.1", plannedRoute.host)
        assertEquals(43171, plannedRoute.port)
        assertEquals("relay-1", plannedRoute.relayId)
    }

    @Test
    fun pairingRuntimeTargetIgnoresDirectEndpointWhenRelayQrAlsoHasIt() {
        val payload = RuntimePairingPayload(
            pairingNonce = "nonce-1",
            pairingCode = "123456",
            runtimeDeviceId = "runtime-relay",
            runtimeName = "AetherLink Runtime",
            fingerprint = "fingerprint",
            runtimePublicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            host = "192.168.1.44",
            port = 43170,
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-1",
            serviceType = "_aetherlink._tcp.local.",
        )

        val target = pairingRuntimeConnectionTarget(RuntimeUiState(), payload)

        assertEquals("runtime-relay", target?.identity?.deviceId)
        assertNull(target?.endpointHint)
    }

    @Test
    fun pairingRuntimeTargetIgnoresDirectEndpointWhenP2pQrAlsoHasIt() {
        val payload = RuntimePairingPayload(
            pairingNonce = "nonce-1",
            pairingCode = "123456",
            runtimeDeviceId = "runtime-p2p",
            runtimeName = "AetherLink Runtime",
            fingerprint = "fingerprint",
            runtimePublicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            host = "192.168.1.44",
            port = 43170,
            p2pRouteClass = "p2p_rendezvous",
            p2pRecordId = "p2p-record-1",
            p2pEncryptedBody = "opaque-candidate-1",
            p2pExpiresAtEpochMillis = 4102444800000L,
            p2pAntiReplayNonce = "nonce-p2p-1",
            p2pProtocolVersion = 1,
            serviceType = "_aetherlink._tcp.local.",
        )

        val target = pairingRuntimeConnectionTarget(RuntimeUiState(), payload)

        assertEquals("runtime-p2p", target?.identity?.deviceId)
        assertNull(target?.endpointHint)
    }

    @Test
    fun pairingRuntimeTargetResolvesIdentityOnlyQrFromMatchingDiscovery() {
        val payload = RuntimePairingPayload(
            pairingNonce = "nonce-1",
            pairingCode = "123456",
            runtimeDeviceId = "runtime-identity-only",
            runtimeName = "AetherLink Runtime",
            fingerprint = "fingerprint",
            runtimePublicKeyBase64 = "runtime-public-key",
            routeToken = "route-token",
            host = null,
            port = null,
            serviceType = "_aetherlink._tcp.local.",
        )
        val state = RuntimeUiState(
            discoveredRuntimes = listOf(
                RuntimeDiscoveredRuntime(
                    serviceName = "AetherLink",
                    host = "192.168.1.44",
                    port = 43170,
                    routeToken = "route-token",
                    deviceId = "runtime-identity-only",
                    fingerprint = "fingerprint",
                )
            )
        )

        val target = pairingRuntimeConnectionTarget(state, payload)
        assertNotNull(target)

        assertEquals("runtime-identity-only", target?.identity?.deviceId)
        assertEquals("192.168.1.44", target?.endpointHint?.host)
        assertEquals(43170, target?.endpointHint?.port)
        assertEquals(RuntimeEndpointSource.BonjourDiscovery, target?.endpointHint?.source)
    }

    @Test
    fun trustedRuntimeRestoreHonorsManualDisconnectFlag() {
        val trusted = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "fingerprint",
            endpointHint = RuntimeEndpointHint(
                host = "192.168.1.20",
                port = 43170,
                source = RuntimeEndpointSource.TrustedLastKnown,
            ),
        )

        assertTrue(
            shouldAttemptTrustedRuntimeRestore(
                restoreEnabled = true,
                state = RuntimeUiState(trustedRuntime = trusted),
            )
        )
        assertFalse(
            shouldAttemptTrustedRuntimeRestore(
                restoreEnabled = false,
                state = RuntimeUiState(trustedRuntime = trusted),
            )
        )
        assertFalse(
            shouldAttemptTrustedRuntimeRestore(
                restoreEnabled = true,
                state = RuntimeUiState(trustedRuntime = null),
            )
        )
        assertFalse(
            shouldAttemptTrustedRuntimeRestore(
                restoreEnabled = true,
                state = RuntimeUiState(trustedRuntime = trusted, isConnected = true),
            )
        )
        assertFalse(
            shouldAttemptTrustedRuntimeRestore(
                restoreEnabled = true,
                state = RuntimeUiState(trustedRuntime = trusted, isConnecting = true),
            )
        )
    }

    @Test
    fun trustedRelayRouteFailureIsEligibleForReconnectRetry() {
        val trusted = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "fingerprint",
            routeToken = "route-1",
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-1",
        )
        val target = trustedRuntimeConnectionTarget(RuntimeUiState(trustedRuntime = trusted))
            ?: error("Expected trusted target")

        assertTrue(
            shouldRetryTrustedRuntimeConnectFailure(
                state = RuntimeUiState(trustedRuntime = trusted),
                target = target,
                restoreEnabled = true,
            )
        )
        assertFalse(
            shouldRetryTrustedRuntimeConnectFailure(
                state = RuntimeUiState(trustedRuntime = trusted),
                target = target,
                restoreEnabled = false,
            )
        )
        assertFalse(
            shouldRetryTrustedRuntimeConnectFailure(
                state = RuntimeUiState(trustedRuntime = trusted, isConnected = true),
                target = target,
                restoreEnabled = true,
            )
        )
        assertFalse(
            shouldRetryTrustedRuntimeConnectFailure(
                state = RuntimeUiState(
                    trustedRuntime = trusted,
                    error = RuntimeUiError(
                        code = "remote_route_auth_failed",
                        diagnosticCode = "route_diagnostic_relay_auth_failed",
                    ),
                ),
                target = target,
                restoreEnabled = true,
            )
        )
    }

    @Test
    fun trustedDirectRouteFailureIsEligibleForReconnectRetry() {
        val trusted = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "fingerprint",
            endpointHint = RuntimeEndpointHint(
                host = "192.168.1.20",
                port = 43170,
                source = RuntimeEndpointSource.TrustedLastKnown,
            ),
        )
        val target = trustedRuntimeConnectionTarget(RuntimeUiState(trustedRuntime = trusted))
            ?: error("Expected trusted target")

        assertTrue(
            shouldRetryTrustedRuntimeConnectFailure(
                state = RuntimeUiState(trustedRuntime = trusted),
                target = target,
                restoreEnabled = true,
            )
        )
        assertFalse(
            shouldRetryTrustedRuntimeConnectFailure(
                state = RuntimeUiState(trustedRuntime = trusted),
                target = target,
                restoreEnabled = false,
            )
        )
    }

    @Test
    fun acceptedPairingResultCreatesIdentityOnlyTrustedRuntimeFromMatchingRuntimeIdentity() {
        val pending = runtimePairingPayload(host = null, port = null)
        val trusted = trustedRuntimeFromAcceptedPairing(
            pending = pending,
            payload = PairingResultPayload(
                accepted = true,
                runtimeDeviceIdV2 = "runtime-1",
                runtimePublicKey = "runtime-public-key",
                runtimeKeyFingerprint = "runtime-fingerprint",
                trustedDeviceId = "client-1",
                message = "trusted",
            ),
        )

        assertEquals("runtime-1", trusted?.deviceId)
        assertEquals("AetherLink Runtime", trusted?.name)
        assertEquals("runtime-fingerprint", trusted?.fingerprint)
        assertEquals("runtime-public-key", trusted?.publicKeyBase64)
        assertEquals("route-1", trusted?.routeToken)
        assertNull(trusted?.host)
        assertNull(trusted?.port)
    }

    @Test
    fun acceptedPairingResultDropsQrDirectEndpointFromTrustedRuntimeStorage() {
        val pending = runtimePairingPayload(host = "192.168.1.10", port = 43170)
        val trusted = trustedRuntimeFromAcceptedPairing(
            pending = pending,
            payload = PairingResultPayload(
                accepted = true,
                runtimeDeviceIdV2 = "runtime-1",
                runtimePublicKey = "runtime-public-key",
                runtimeKeyFingerprint = "runtime-fingerprint",
                trustedDeviceId = "client-1",
                message = "trusted",
            ),
        ) ?: error("Expected trusted runtime")

        assertNull(trusted.host)
        assertNull(trusted.port)

        val sessionEndpoint = acceptedPairingCurrentEndpointHint(pending)

        assertEquals("192.168.1.10", sessionEndpoint?.host)
        assertEquals(43170, sessionEndpoint?.port)
        assertEquals(RuntimeEndpointSource.PairingQr, sessionEndpoint?.source)

        val restored = RuntimeUiState(
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = trusted.deviceId,
                name = trusted.name,
                fingerprint = trusted.fingerprint,
                publicKeyBase64 = trusted.publicKeyBase64,
                routeToken = trusted.routeToken,
                endpointHint = null,
            ),
        )
        val target = trustedRuntimeConnectionTarget(restored)

        assertEquals("runtime-1", target?.identity?.deviceId)
        assertNull(target?.endpointHint)
    }

    @Test
    fun acceptedPairingResultDropsDirectHintWhenRelayRouteIsPresent() {
        val pending = runtimePairingPayload(
            host = "192.168.1.10",
            port = 43170,
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-1",
        )
        val trusted = trustedRuntimeFromAcceptedPairing(
            pending = pending,
            payload = PairingResultPayload(
                accepted = true,
                runtimeDeviceIdV2 = "runtime-1",
                runtimePublicKey = "runtime-public-key",
                runtimeKeyFingerprint = "runtime-fingerprint",
                trustedDeviceId = "client-1",
                message = "trusted",
            ),
        ) ?: error("Expected trusted runtime")

        assertNull(trusted.host)
        assertNull(trusted.port)
        assertEquals("relay.example.test", trusted.relayHost)
        assertEquals("relay-1", trusted.relayId)
        assertEquals(4102444800000L, trusted.relayExpiresAtEpochMillis)
        assertEquals("nonce-route-1", trusted.relayNonce)
        val restoredTarget = trustedRuntimeConnectionTarget(
            RuntimeUiState(
                trustedRuntime = RuntimeTrustedRuntime(
                    deviceId = trusted.deviceId,
                    name = trusted.name,
                    fingerprint = trusted.fingerprint,
                    publicKeyBase64 = trusted.publicKeyBase64,
                    routeToken = trusted.routeToken,
                    endpointHint = null,
                    relayHost = trusted.relayHost,
                    relayPort = trusted.relayPort,
                    relayId = trusted.relayId,
                    relaySecret = trusted.relaySecret,
                ),
            )
        )
        assertNull(restoredTarget?.endpointHint)
    }

    @Test
    fun acceptedPairingResultPreservesRelaySecretForTrustedRuntimeRestore() {
        val pending = runtimePairingPayload(
            host = null,
            port = null,
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-1",
        )
        val trusted = trustedRuntimeFromAcceptedPairing(
            pending = pending,
            payload = PairingResultPayload(
                accepted = true,
                runtimeDeviceIdV2 = "runtime-1",
                runtimePublicKey = "runtime-public-key",
                runtimeKeyFingerprint = "runtime-fingerprint",
                trustedDeviceId = "client-1",
                message = "trusted",
            ),
        ) ?: error("Expected trusted runtime")

        assertEquals("relay.example.test", trusted.relayHost)
        assertEquals(443, trusted.relayPort)
        assertEquals("relay-1", trusted.relayId)
        assertEquals("secret-1", trusted.relaySecret)
        assertEquals(4102444800000L, trusted.relayExpiresAtEpochMillis)
        assertEquals("nonce-route-1", trusted.relayNonce)
    }

    @Test
    fun acceptedPairingResultPreservesP2pRendezvousForTrustedRuntimeRestore() {
        val pending = runtimePairingPayload(
            host = null,
            port = null,
            p2pRouteClass = "p2p_rendezvous",
            p2pRecordId = "p2p-record-1",
            p2pEncryptedBody = "opaque-candidate-1",
            p2pExpiresAtEpochMillis = 4102444800000L,
            p2pAntiReplayNonce = "nonce-p2p-1",
            p2pProtocolVersion = 1,
        )
        val trusted = trustedRuntimeFromAcceptedPairing(
            pending = pending,
            payload = PairingResultPayload(
                accepted = true,
                runtimeDeviceIdV2 = "runtime-1",
                runtimePublicKey = "runtime-public-key",
                runtimeKeyFingerprint = "runtime-fingerprint",
                trustedDeviceId = "client-1",
                message = "trusted",
            ),
        ) ?: error("Expected trusted runtime")

        assertNull(trusted.host)
        assertNull(trusted.port)
        assertEquals("p2p_rendezvous", trusted.p2pRouteClass)
        assertEquals("p2p-record-1", trusted.p2pRecordId)
        assertEquals("opaque-candidate-1", trusted.p2pEncryptedBody)
        assertEquals(4102444800000L, trusted.p2pExpiresAtEpochMillis)
        assertEquals("nonce-p2p-1", trusted.p2pAntiReplayNonce)
        assertEquals(1, trusted.p2pProtocolVersion)
    }

    @Test
    fun compactRelayQrScanPlansPendingRelayPairingWithoutManualEndpoint() {
        val rawUri = "aetherlink://pair?v=1&n=nonce-1&c=123456" +
            "&rid=runtime-1&rn=AetherLink%20Runtime&rf=runtime-fingerprint" +
            "&rk=runtime-public-key&rt=route-1" +
            "&h=192.168.1.10&p=43170" +
            "&rh=relay.example.test&rp=443&ri=relay-1&rs=secret-1" +
            "&rx=4102444800000&rrn=nonce-route-1&rsc=remote"
        val parsed = parseRuntimePairingQrPayload(
            rawValue = rawUri,
            allowDebugLoopbackRelay = false,
            allowDiagnosticLocalDirectEndpoint = false,
        ) as RuntimePairingQrParseResult.Accepted
        val plan = pendingPairingConnectionPlan(
            state = RuntimeUiState(
                runtimeHost = "10.0.0.99",
                runtimePort = "59999",
                runtimeEndpointSource = RuntimeEndpointSource.Manual,
            ),
            payload = parsed.payload,
        )
        val target = requireNotNull(plan.target)
        val plannedRoute = RuntimeRemoteRoutePlanner(
            pendingPairingPayload = { parsed.payload },
            trustedRuntime = { null },
            nowEpochMillis = { 1_000L },
        ).prepareRemoteRoutes(requireNotNull(target.identity)).single() as PreparedRemoteRuntimeRoute.Relay

        assertNull(parsed.payload.host)
        assertNull(parsed.payload.port)
        assertEquals("123456", plan.pendingState.pairingCode)
        assertEquals("AetherLink Runtime", plan.pendingState.pendingPairingRuntimeName)
        assertFalse(plan.pendingState.isPairingAwaitingRoute)
        assertEquals("10.0.0.99", plan.pendingState.runtimeHost)
        assertEquals("59999", plan.pendingState.runtimePort)
        assertNull(target.endpointHint)
        assertEquals("runtime-1", target.identity?.deviceId)
        assertEquals(false, plan.shouldStartDiscovery)
        assertEquals(false, plan.shouldWaitForDiscoveryRoute)
        assertEquals("relay.example.test", plannedRoute.host)
        assertEquals(443, plannedRoute.port)
        assertEquals("relay-1", plannedRoute.relayId)
        assertEquals("secret-1", plannedRoute.relayFrameSecret)
        assertEquals("nonce-route-1", plannedRoute.security.antiReplayNonce)
    }

    @Test
    fun macosCompactRelayQrFixtureParsesAndPreparesRelayRoute() {
        val payload = RuntimePairingPayloadParser.parse(
            sharedProtocolFixture("macos-compact-relay-pairing-uri.txt"),
        )
        val route = RuntimeRemoteRoutePlanner(
            pendingPairingPayload = { payload },
            trustedRuntime = { null },
            nowEpochMillis = { 1_000L },
        ).prepareRemoteRoutes(identityFor(payload)).single() as PreparedRemoteRuntimeRoute.Relay
        val expiredRoutes = RuntimeRemoteRoutePlanner(
            pendingPairingPayload = { payload },
            trustedRuntime = { null },
            nowEpochMillis = { 4_102_444_800_001L },
        ).prepareRemoteRoutes(identityFor(payload))

        assertEquals("nonce-1", payload.pairingNonce)
        assertEquals("123456", payload.pairingCode)
        assertEquals("runtime-1", payload.runtimeDeviceId)
        assertEquals("AetherLink Runtime", payload.runtimeName)
        assertEquals("runtime-fingerprint", payload.fingerprint)
        assertEquals("runtime+public/key=", payload.runtimePublicKeyBase64)
        assertEquals("route-token-1", payload.routeToken)
        assertNull(payload.host)
        assertNull(payload.port)
        assertEquals("relay.example.test", payload.relayHost)
        assertEquals(43171, payload.relayPort)
        assertEquals("relay-bootstrap-1", payload.relayId)
        assertEquals("secret-bootstrap-1", payload.relaySecret)
        assertEquals(4102444800000L, payload.relayExpiresAtEpochMillis)
        assertEquals("allocated-nonce-1", payload.relayNonce)
        assertEquals("remote", payload.relayScope)
        assertTrue(payload.hasRelayRoute(nowEpochMillis = 1_000L))
        assertFalse(payload.hasRelayRoute(nowEpochMillis = 4_102_444_800_001L))
        assertEquals("relay.example.test", route.host)
        assertEquals(43171, route.port)
        assertEquals("relay-bootstrap-1", route.relayId)
        assertEquals("secret-bootstrap-1", route.relayFrameSecret)
        assertEquals("relay-bootstrap-1", route.security.rendezvousToken)
        assertEquals(4102444800000L, route.security.expiresAtEpochMillis)
        assertEquals("allocated-nonce-1", route.security.antiReplayNonce)
        assertTrue(expiredRoutes.isEmpty())
    }

    @Test
    fun diagnosticIdentityOnlyQrPlanStartsDiscoveryAndWaitsForRouteWhenRemoteRouteIsNotRequired() {
        val parsed = parseRuntimePairingQrPayload(
            rawValue = "aetherlink://pair?v=1&n=nonce-1&c=123456" +
                "&rid=runtime-1&rn=AetherLink%20Runtime&rf=runtime-fingerprint" +
                "&rk=runtime-public-key&rt=route-1",
            allowDebugLoopbackRelay = false,
            allowDiagnosticLocalDirectEndpoint = false,
        ) as RuntimePairingQrParseResult.Accepted

        val plan = pendingPairingConnectionPlan(RuntimeUiState(), parsed.payload)

        assertNull(plan.target)
        assertEquals("123456", plan.pendingState.pairingCode)
        assertTrue(plan.pendingState.isPairingAwaitingRoute)
        assertEquals(true, plan.shouldStartDiscovery)
        assertEquals(true, plan.shouldWaitForDiscoveryRoute)
    }

    @Test
    fun productPairingQrParserRejectsIdentityOnlyQrWhenRemoteRouteIsRequired() {
        val parsed = parseRuntimePairingQrPayload(
            rawValue = "aetherlink://pair?v=1&n=nonce-1&c=123456" +
                "&rid=runtime-1&rn=AetherLink%20Runtime&rf=runtime-fingerprint" +
                "&rk=runtime-public-key&rt=route-1",
            allowDebugLoopbackRelay = false,
            allowDiagnosticLocalDirectEndpoint = false,
            requireRemoteRoute = true,
        )

        val rejected = parsed as RuntimePairingQrParseResult.Rejected
        assertEquals("pairing_endpoint_unavailable", rejected.error.code)
        assertEquals("route_diagnostic_remote_pending", rejected.error.diagnosticCode)
        assertEquals(false, rejected.clearPendingPairing)
    }

    @Test
    fun productPairingQrParserRequiresRuntimePublicKeyAndRouteTokenWhenRemoteRouteIsRequired() {
        val baseUri = "aetherlink://pair?v=1&n=nonce-1&c=123456" +
            "&rid=runtime-1&rn=AetherLink%20Runtime&rf=runtime-fingerprint"
        val relayRoute = "&rh=relay.example.test&rp=443&ri=relay-1&rs=secret-1" +
            "&rx=4102444800000&rrn=nonce-route-1&rsc=remote"

        val missingRuntimePublicKey = parseRuntimePairingQrPayload(
            rawValue = baseUri + "&rt=route-1" + relayRoute,
            allowDebugLoopbackRelay = false,
            allowDiagnosticLocalDirectEndpoint = false,
            requireRemoteRoute = true,
        ) as RuntimePairingQrParseResult.Rejected
        val missingRouteToken = parseRuntimePairingQrPayload(
            rawValue = baseUri + "&rk=runtime-public-key" + relayRoute,
            allowDebugLoopbackRelay = false,
            allowDiagnosticLocalDirectEndpoint = false,
            requireRemoteRoute = true,
        ) as RuntimePairingQrParseResult.Rejected

        assertEquals("pairing_endpoint_unavailable", missingRuntimePublicKey.error.code)
        assertEquals("route_diagnostic_remote_pending", missingRuntimePublicKey.error.diagnosticCode)
        assertEquals("pairing_endpoint_unavailable", missingRouteToken.error.code)
        assertEquals("route_diagnostic_remote_pending", missingRouteToken.error.diagnosticCode)
    }

    @Test
    fun productPairingQrParserAcceptsP2pRendezvousQrWhenRemoteRouteIsRequired() {
        val parsed = parseRuntimePairingQrPayload(
            rawValue = "aetherlink://pair?v=1&n=nonce-1&c=123456" +
                "&rid=runtime-1&rn=AetherLink%20Runtime&rf=runtime-fingerprint" +
                "&rk=runtime-public-key&rt=route-1" +
                "&pc=p2p_rendezvous&prid=p2p-record-1&peb=opaque-candidate-1" +
                "&px=4102444800000&pn=nonce-p2p-1&pv=1",
            allowDebugLoopbackRelay = false,
            allowDiagnosticLocalDirectEndpoint = false,
            requireRemoteRoute = true,
        )

        val accepted = parsed as RuntimePairingQrParseResult.Accepted
        val plan = pendingPairingConnectionPlan(RuntimeUiState(), accepted.payload)
        val target = requireNotNull(plan.target)
        val route = RuntimeRemoteRoutePlanner(
            pendingPairingPayload = { accepted.payload },
            trustedRuntime = { null },
            nowEpochMillis = { 1_000L },
        ).prepareRemoteRoutes(requireNotNull(target.identity)).single() as PreparedRemoteRuntimeRoute.PeerToPeer

        assertNull(target.endpointHint)
        assertEquals(false, plan.shouldStartDiscovery)
        assertEquals(false, plan.shouldWaitForDiscoveryRoute)
        assertEquals("p2p-record-1", route.sessionId)
        assertEquals("opaque-candidate-1", route.encryptedCandidateMaterial)
        assertEquals("nonce-p2p-1", route.security.antiReplayNonce)
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun trustRuntimeFromPairingQrRejectsIdentityOnlyQrInNormalScanPath() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        var viewModel: RuntimeClientViewModel? = null
        try {
            val rawUri = "aetherlink://pair?v=1&n=nonce-timeout&c=123456" +
                "&rid=runtime-timeout&rn=AetherLink%20Runtime&rf=runtime-fingerprint" +
                "&rk=runtime-public-key&rt=route-timeout"
            val localStore = FakeRuntimeLocalDataStore()
            var directConnectionAttempts = 0
            var relayConnectionAttempts = 0
            viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        directConnectionAttempts += 1
                        error("Identity-only product QR must not use direct transport")
                    },
                    relayConnector = RuntimeRelayConnector { _, _ ->
                        relayConnectionAttempts += 1
                        error("Identity-only product QR must not use relay transport")
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = FakeTrustedRuntimeStore(),
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = localStore,
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    currentTimeMillis = { 1_000L },
                ),
            )

            viewModel.trustRuntimeFromPairingQr(rawUri)
            runCurrent()

            assertEquals(0, directConnectionAttempts)
            assertEquals(0, relayConnectionAttempts)
            assertFalse(viewModel.state.value.isPairingAwaitingRoute)
            assertEquals("", viewModel.state.value.pairingCode)
            assertNull(viewModel.state.value.pendingPairingRuntimeName)
            assertNull(localStore.data.pendingPairingRoute)
            assertEquals("pairing_endpoint_unavailable", viewModel.state.value.error?.code)
            assertEquals("route_diagnostic_remote_pending", viewModel.state.value.error?.diagnosticCode)
            viewModel.clearForTest()
            viewModel = null
            advanceUntilIdle()
        } finally {
            viewModel?.clearForTest()
            advanceUntilIdle()
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun diagnosticIdentityOnlyPairingQrCanUseUsbReverseFallbackWhenRemoteRouteIsNotRequired() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        var viewModel: RuntimeClientViewModel? = null
        try {
            val rawUri = "aetherlink://pair?v=1&n=nonce-timeout&c=123456" +
                "&rid=runtime-timeout&rn=AetherLink%20Runtime&rf=runtime-fingerprint" +
                "&rk=runtime-public-key&rt=route-timeout"
            val localStore = FakeRuntimeLocalDataStore()
            val channel = ScriptedRuntimeProtocolChannel()
            var directHost: String? = null
            var directPort: Int? = null
            viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { host, port, _ ->
                        directHost = host
                        directPort = port
                        channel
                    },
                    relayConnector = RuntimeRelayConnector { _, _ ->
                        error("Identity-only QR without relay metadata must not use relay")
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = FakeTrustedRuntimeStore(),
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = localStore,
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    currentTimeMillis = { 1_000L },
                ),
            )

            viewModel.trustRuntimeFromPairingQr(
                rawValue = rawUri,
                requireRemoteRoute = false,
            )
            runCurrent()

            assertEquals("127.0.0.1", directHost)
            assertEquals(43170, directPort)
            assertFalse(viewModel.state.value.isPairingAwaitingRoute)
            assertEquals("123456", viewModel.state.value.pairingCode)
            assertEquals("AetherLink Runtime", viewModel.state.value.pendingPairingRuntimeName)
            assertNotNull(localStore.data.pendingPairingRoute)
            val pairingEnvelope = channel.sentEnvelopes.single { it.type == MessageType.PairingRequest }
            val payload = json.decodeFromJsonElement(
                PairingRequestPayload.serializer(),
                pairingEnvelope.payload,
            )
            assertEquals("123456", payload.pairingCode)
            assertEquals("client-1", payload.deviceId)
            viewModel.clearForTest()
            viewModel = null
            advanceUntilIdle()
        } finally {
            viewModel?.clearForTest()
            advanceUntilIdle()
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun trustRuntimeFromPairingQrWithCompactRelayUriConnectsRelayAndSendsPairingRequest() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val rawUri = "aetherlink://pair?v=1&n=nonce-1&c=123456" +
                "&rid=runtime-1&rn=AetherLink%20Runtime&rf=runtime-fingerprint" +
                "&rk=runtime-public-key&rt=route-1" +
                "&h=192.168.1.10&p=43170" +
                "&rh=relay.example.test&rp=443&ri=relay-1&rs=secret-1" +
                "&rx=4102444800000&rrn=nonce-route-1&rsc=remote"
            val channel = CapturingRuntimeProtocolChannel()
            var directConnectionAttempts = 0
            var capturedRelayRoute: PreparedRemoteRuntimeRoute.Relay? = null
            var preflightRelayRoute: PreparedRemoteRuntimeRoute.Relay? = null
            val localStore = FakeRuntimeLocalDataStore(
                initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = false),
            )
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        directConnectionAttempts += 1
                        error("Direct TCP should not be used for compact relay QR pairing")
                    },
                    relayConnector = RuntimeRelayConnector { route, _ ->
                        capturedRelayRoute = route
                        channel
                    },
                    relayReachabilityChecker = RuntimeRelayReachabilityChecker { route, _ ->
                        preflightRelayRoute = route
                        true
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = FakeTrustedRuntimeStore(),
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = localStore,
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    currentTimeMillis = { 1_000L },
                ),
            )

            viewModel.trustRuntimeFromPairingQr(rawUri)
            advanceUntilIdle()

            val relayRoute = requireNotNull(capturedRelayRoute)
            val checkedRelayRoute = requireNotNull(preflightRelayRoute)
            val pairingEnvelope = channel.sentEnvelopes.single { it.type == MessageType.PairingRequest }
            val pairingPayload = json.decodeFromJsonElement(
                PairingRequestPayload.serializer(),
                pairingEnvelope.payload,
            )
            assertEquals(0, directConnectionAttempts)
            assertEquals("relay.example.test", relayRoute.host)
            assertEquals(443, relayRoute.port)
            assertEquals("relay-1", relayRoute.relayId)
            assertEquals("secret-1", relayRoute.relayFrameSecret)
            assertEquals("nonce-route-1", relayRoute.security.antiReplayNonce)
            assertEquals(relayRoute.host, checkedRelayRoute.host)
            assertEquals(relayRoute.port, checkedRelayRoute.port)
            assertEquals(relayRoute.relayId, checkedRelayRoute.relayId)
            assertEquals(relayRoute.relayFrameSecret, checkedRelayRoute.relayFrameSecret)
            assertEquals(relayRoute.security.antiReplayNonce, checkedRelayRoute.security.antiReplayNonce)
            assertEquals("nonce-1", pairingPayload.pairingNonce)
            assertEquals("123456", pairingPayload.pairingCode)
            assertEquals("client-1", pairingPayload.deviceId)
            assertEquals("AetherLink Test Client", pairingPayload.deviceName)
            assertEquals("client-public-key", pairingPayload.publicKey)
            assertTrue(localStore.data.trustedRuntimeAutoReconnectEnabled)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun duplicateCompactRelayQrScanSendsSinglePairingRequestOnActiveRelayConnection() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        var viewModel: RuntimeClientViewModel? = null
        try {
            val rawUri = "aetherlink://pair?v=1&n=nonce-duplicate&c=123456" +
                "&rid=runtime-duplicate&rn=AetherLink%20Runtime&rf=runtime-fingerprint" +
                "&rk=runtime-public-key&rt=route-duplicate" +
                "&rh=relay-duplicate.example.test&rp=443&ri=relay-duplicate&rs=secret-duplicate" +
                "&rx=4102444800000&rrn=nonce-route-duplicate&rsc=remote"
            val channel = ScriptedRuntimeProtocolChannel()
            var directConnectionAttempts = 0
            var relayConnectionAttempts = 0
            viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        directConnectionAttempts += 1
                        error("Direct TCP should not be used for compact relay QR pairing")
                    },
                    relayConnector = RuntimeRelayConnector { _, _ ->
                        relayConnectionAttempts += 1
                        channel
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = FakeTrustedRuntimeStore(),
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = FakeRuntimeLocalDataStore(),
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    currentTimeMillis = { 1_000L },
                ),
            )

            viewModel.trustRuntimeFromPairingQr(rawUri)
            advanceUntilIdle()
            viewModel.trustRuntimeFromPairingQr(rawUri)
            advanceUntilIdle()

            assertEquals(0, directConnectionAttempts)
            assertEquals(1, relayConnectionAttempts)
            assertTrue(channel.isConnected)
            assertEquals(1, channel.sentEnvelopes.count { it.type == MessageType.PairingRequest })
        } finally {
            viewModel?.clearForTest()
            advanceUntilIdle()
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun relayQrPairingFailsBeforeConnectWhenDeviceCannotReachRelayRoute() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val rawUri = "aetherlink://pair?v=1&n=nonce-1&c=123456" +
                "&rid=runtime-1&rn=AetherLink%20Runtime&rf=runtime-fingerprint" +
                "&rk=runtime-public-key&rt=route-1" +
                "&h=192.168.1.10&p=43170" +
                "&rh=relay.example.test&rp=443&ri=relay-1&rs=secret-1" +
                "&rx=4102444800000&rrn=nonce-route-1&rsc=remote"
            val localStore = FakeRuntimeLocalDataStore(
                initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = false),
            )
            var directConnectionAttempts = 0
            var relayConnectionAttempts = 0
            var checkedRoute: PreparedRemoteRuntimeRoute.Relay? = null
            var checkedTimeoutMillis: Int? = null
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        directConnectionAttempts += 1
                        error("Direct TCP should not be used for compact relay QR pairing")
                    },
                    relayConnector = RuntimeRelayConnector { _, _ ->
                        relayConnectionAttempts += 1
                        error("Relay connection must not start when preflight fails")
                    },
                    relayReachabilityChecker = RuntimeRelayReachabilityChecker { route, timeoutMillis ->
                        checkedRoute = route
                        checkedTimeoutMillis = timeoutMillis
                        false
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = FakeTrustedRuntimeStore(),
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = localStore,
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    currentTimeMillis = { 1_000L },
                ),
            )

            viewModel.trustRuntimeFromPairingQr(rawUri)
            advanceUntilIdle()

            assertEquals(0, directConnectionAttempts)
            assertEquals(0, relayConnectionAttempts)
            val checkedRelayRoute = requireNotNull(checkedRoute)
            assertEquals("relay.example.test", checkedRelayRoute.host)
            assertEquals(443, checkedRelayRoute.port)
            assertEquals("relay-1", checkedRelayRoute.relayId)
            assertEquals("secret-1", checkedRelayRoute.relayFrameSecret)
            assertEquals("nonce-route-1", checkedRelayRoute.security.antiReplayNonce)
            assertEquals(RELAY_REACHABILITY_PREFLIGHT_TIMEOUT_MS, checkedTimeoutMillis)
            assertFalse(viewModel.state.value.isPairingAwaitingRoute)
            assertNull(viewModel.state.value.pendingPairingRuntimeName)
            assertNull(localStore.data.pendingPairingRoute)
            assertEquals("remote_route_unreachable_from_device", viewModel.state.value.error?.code)
            assertEquals(
                "route_diagnostic_relay_unreachable_from_device",
                viewModel.state.value.error?.diagnosticCode,
            )
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun compactRelayQrPairingResultPersistsTrustedRelayAndClearsPendingRoute() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val rawUri = "aetherlink://pair?v=1&n=nonce-accepted&c=135790" +
                "&rid=runtime-accepted&rn=AetherLink%20Runtime&rf=runtime-fingerprint" +
                "&rk=runtime-public-key&rt=route-accepted" +
                "&rh=relay-accepted.example.test&rp=443&ri=relay-accepted&rs=secret-accepted" +
                "&rx=4102444800000&rrn=nonce-route-accepted&rsc=remote"
            val channel = ScriptedRuntimeProtocolChannel()
            val trustedRuntimeStore = FakeTrustedRuntimeStore()
            val localStore = FakeRuntimeLocalDataStore(
                initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = true),
            )
            var directConnectionAttempts = 0
            var relayConnectionAttempts = 0
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        directConnectionAttempts += 1
                        error("Direct TCP should not be used for compact relay QR pairing")
                    },
                    relayConnector = RuntimeRelayConnector { route, _ ->
                        relayConnectionAttempts += 1
                        assertEquals("relay-accepted.example.test", route.host)
                        assertEquals("relay-accepted", route.relayId)
                        assertEquals("secret-accepted", route.relayFrameSecret)
                        assertEquals("nonce-route-accepted", route.security.antiReplayNonce)
                        channel
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedRuntimeStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = localStore,
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    currentTimeMillis = { 1_000L },
                ),
            )

            viewModel.trustRuntimeFromPairingQr(rawUri)
            advanceUntilIdle()

            assertNotNull(localStore.data.pendingPairingRoute)
            val pairingRequest = channel.sentEnvelopes.single { it.type == MessageType.PairingRequest }
            channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.PairingResult,
                    requestId = pairingRequest.requestId,
                    payload = json.encodeToJsonElement(
                        PairingResultPayload.serializer(),
                        PairingResultPayload(
                            accepted = true,
                            runtimeDeviceIdV2 = "runtime-accepted",
                            runtimePublicKey = "runtime-public-key",
                            runtimeKeyFingerprint = "runtime-fingerprint",
                            trustedDeviceId = "client-1",
                            message = "trusted",
                        ),
                    ).jsonObject,
                )
            )
            advanceUntilIdle()

            val trusted = requireNotNull(trustedRuntimeStore.trusted)
            assertEquals(0, directConnectionAttempts)
            assertEquals(1, relayConnectionAttempts)
            assertEquals("runtime-accepted", trusted.deviceId)
            assertEquals("route-accepted", trusted.routeToken)
            assertNull(trusted.host)
            assertNull(trusted.port)
            assertEquals("relay-accepted.example.test", trusted.relayHost)
            assertEquals(443, trusted.relayPort)
            assertEquals("relay-accepted", trusted.relayId)
            assertEquals("secret-accepted", trusted.relaySecret)
            assertEquals(4102444800000L, trusted.relayExpiresAtEpochMillis)
            assertEquals("nonce-route-accepted", trusted.relayNonce)
            assertEquals("remote", trusted.relayScope)
            assertNull(localStore.data.pendingPairingRoute)
            assertTrue(localStore.data.trustedRuntimeAutoReconnectEnabled)
            assertTrue(localStore.data.pairingOnboardingCompleted)
            assertEquals("relay-accepted.example.test", viewModel.state.value.trustedRuntime?.relayHost)
            assertEquals(RuntimeActiveRouteKind.Relay, viewModel.state.value.activeRouteKind)
            assertNull(viewModel.state.value.error)
            assertFalse(channel.sentEnvelopes.any { it.type == MessageType.RouteRefresh })
            assertTrue(channel.sentEnvelopes.any { it.type == MessageType.RuntimeHealth })
            assertTrue(channel.sentEnvelopes.any { it.type == MessageType.ChatSessionsList })
            assertTrue(channel.sentEnvelopes.any { it.type == MessageType.MemoryList })
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun pairingResultRejectsUnknownMetadataBeforeTrustMutation() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val rawUri = "aetherlink://pair?v=1&n=nonce-unknown-metadata&c=135791" +
                "&rid=runtime-unknown-metadata&rn=AetherLink%20Runtime&rf=runtime-fingerprint" +
                "&rk=runtime-public-key&rt=route-unknown-metadata" +
                "&rh=relay-unknown.example.test&rp=443&ri=relay-unknown&rs=secret-unknown" +
                "&rx=4102444800000&rrn=nonce-route-unknown&rsc=remote"
            val channel = ScriptedRuntimeProtocolChannel()
            val trustedRuntimeStore = FakeTrustedRuntimeStore()
            val localStore = FakeRuntimeLocalDataStore(
                initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = true),
            )
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Direct TCP should not be used for pairing result metadata rejection")
                    },
                    relayConnector = RuntimeRelayConnector { route, _ ->
                        assertEquals("relay-unknown.example.test", route.host)
                        assertEquals("relay-unknown", route.relayId)
                        assertEquals("secret-unknown", route.relayFrameSecret)
                        assertEquals("nonce-route-unknown", route.security.antiReplayNonce)
                        channel
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedRuntimeStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = localStore,
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    currentTimeMillis = { 1_000L },
                ),
            )

            viewModel.trustRuntimeFromPairingQr(rawUri)
            advanceUntilIdle()

            val pendingSecretRef = requireNotNull(localStore.data.pendingPairingRoute?.relaySecretRef)
            assertEquals("secret-unknown", localStore.relaySecret(pendingSecretRef))
            val pairingRequest = channel.sentEnvelopes.single { it.type == MessageType.PairingRequest }
            val sentCountBeforeRejectedResult = channel.sentEnvelopes.size
            channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.PairingResult,
                    requestId = pairingRequest.requestId,
                    payload = buildJsonObject {
                        put("accepted", true)
                        put("runtime_device_id", "runtime-unknown-metadata")
                        put("runtime_public_key", "runtime-public-key")
                        put("runtime_key_fingerprint", "runtime-fingerprint")
                        put("trusted_device_id", "client-1")
                        put("message", "trusted")
                        put("backend_url", "http://127.0.0.1:11434")
                    },
                ),
            )
            advanceUntilIdle()

            val rejectedState = viewModel.state.value
            assertEquals("invalid_payload", rejectedState.error?.code)
            assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("pairing.result response"))
            assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("backend_url"))
            assertNull(trustedRuntimeStore.trusted)
            assertNotNull(localStore.data.pendingPairingRoute)
            assertEquals("secret-unknown", localStore.relaySecret(pendingSecretRef))
            assertEquals("135791", rejectedState.pairingCode)
            assertEquals("AetherLink Runtime", rejectedState.pendingPairingRuntimeName)
            assertEquals(sentCountBeforeRejectedResult, channel.sentEnvelopes.size)
            assertEquals(0, channel.sentEnvelopes.count { it.type == MessageType.RuntimeHealth })
            assertEquals(0, channel.sentEnvelopes.count { it.type == MessageType.ChatSessionsList })
            assertEquals(0, channel.sentEnvelopes.count { it.type == MessageType.MemoryList })
            assertFalse(json.encodeToString(localStore.data).contains("127.0.0.1:11434"))

            channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.PairingResult,
                    requestId = pairingRequest.requestId,
                    payload = json.encodeToJsonElement(
                        PairingResultPayload.serializer(),
                        PairingResultPayload(
                            accepted = true,
                            runtimeDeviceIdV2 = "runtime-unknown-metadata",
                            runtimePublicKey = "runtime-public-key",
                            runtimeKeyFingerprint = "runtime-fingerprint",
                            trustedDeviceId = "client-1",
                            message = "trusted",
                        ),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val trusted = requireNotNull(trustedRuntimeStore.trusted)
            val acceptedState = viewModel.state.value
            assertEquals("runtime-unknown-metadata", trusted.deviceId)
            assertEquals("relay-unknown.example.test", trusted.relayHost)
            assertNull(localStore.data.pendingPairingRoute)
            assertNull(localStore.relaySecret(pendingSecretRef))
            assertNull(acceptedState.error)
            assertNull(acceptedState.pendingPairingRuntimeName)
            assertFalse(acceptedState.isPairingAwaitingRoute)
            assertEquals("", acceptedState.pairingCode)
            assertTrue(channel.sentEnvelopes.any { it.type == MessageType.RuntimeHealth })
            assertTrue(channel.sentEnvelopes.any { it.type == MessageType.ChatSessionsList })
            assertTrue(channel.sentEnvelopes.any { it.type == MessageType.MemoryList })
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun rejectedCompactRelayQrPairingResultClearsPendingRouteAndSecret() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val rawUri = "aetherlink://pair?v=1&n=nonce-rejected&c=246810" +
                "&rid=runtime-rejected&rn=AetherLink%20Runtime&rf=runtime-fingerprint" +
                "&rk=runtime-public-key&rt=route-rejected" +
                "&rh=relay-rejected.example.test&rp=443&ri=relay-rejected&rs=secret-rejected" +
                "&rx=4102444800000&rrn=nonce-route-rejected&rsc=remote"
            val channel = ScriptedRuntimeProtocolChannel()
            val trustedRuntimeStore = FakeTrustedRuntimeStore()
            val localStore = FakeRuntimeLocalDataStore()
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Direct TCP should not be used for compact relay QR pairing")
                    },
                    relayConnector = RuntimeRelayConnector { route, _ ->
                        assertEquals("relay-rejected.example.test", route.host)
                        assertEquals("relay-rejected", route.relayId)
                        assertEquals("secret-rejected", route.relayFrameSecret)
                        assertEquals("nonce-route-rejected", route.security.antiReplayNonce)
                        channel
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedRuntimeStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = localStore,
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    currentTimeMillis = { 1_000L },
                ),
            )

            viewModel.trustRuntimeFromPairingQr(rawUri)
            advanceUntilIdle()

            val pendingSecretRef = requireNotNull(localStore.data.pendingPairingRoute?.relaySecretRef)
            assertEquals("secret-rejected", localStore.relaySecret(pendingSecretRef))
            assertEquals("246810", viewModel.state.value.pairingCode)
            assertEquals("AetherLink Runtime", viewModel.state.value.pendingPairingRuntimeName)
            val pairingRequest = channel.sentEnvelopes.single { it.type == MessageType.PairingRequest }
            channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.PairingResult,
                    requestId = pairingRequest.requestId,
                    payload = json.encodeToJsonElement(
                        PairingResultPayload.serializer(),
                        PairingResultPayload(
                            accepted = false,
                            message = "Pairing code expired; scan the latest QR.",
                        ),
                    ).jsonObject,
                )
            )
            advanceUntilIdle()

            assertNull(trustedRuntimeStore.trusted)
            assertNull(localStore.data.pendingPairingRoute)
            assertNull(localStore.relaySecret(pendingSecretRef))
            assertNull(viewModel.state.value.pendingPairingRuntimeName)
            assertFalse(viewModel.state.value.isPairingAwaitingRoute)
            assertEquals("", viewModel.state.value.pairingCode)
            assertEquals("pairing_rejected", viewModel.state.value.error?.code)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun routeRefreshQrAfterAcceptedRelayPairingDoesNotOpenDuplicateRelayConnection() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        var viewModel: RuntimeClientViewModel? = null
        try {
            val pairingUri = "aetherlink://pair?v=1&n=nonce-accepted&c=135790" +
                "&rid=runtime-accepted&rn=AetherLink%20Runtime&rf=runtime-fingerprint" +
                "&rk=runtime-public-key&rt=route-accepted" +
                "&rh=relay-accepted.example.test&rp=443&ri=relay-accepted&rs=secret-accepted" +
                "&rx=4102444800000&rrn=nonce-route-accepted&rsc=remote"
            val routeRefreshUri = "aetherlink://pair?v=1&n=nonce-refresh&c=246810" +
                "&rid=runtime-accepted&rn=AetherLink%20Runtime&rf=runtime-fingerprint" +
                "&rk=runtime-public-key&rt=route-refreshed" +
                "&rh=relay-refreshed.example.test&rp=443&ri=relay-refreshed&rs=secret-refreshed" +
                "&rx=4102444900000&rrn=nonce-route-refreshed&rsc=remote"
            val channel = ScriptedRuntimeProtocolChannel()
            val trustedRuntimeStore = FakeEmittingTrustedRuntimeStore(null)
            val localStore = FakeRuntimeLocalDataStore(
                initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = true),
            )
            var directConnectionAttempts = 0
            var relayConnectionAttempts = 0
            viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        directConnectionAttempts += 1
                        error("Direct TCP should not be used for relay QR pairing or refresh")
                    },
                    relayConnector = RuntimeRelayConnector { _, _ ->
                        relayConnectionAttempts += 1
                        channel
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedRuntimeStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = localStore,
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    currentTimeMillis = { 1_000L },
                ),
            )

            viewModel.trustRuntimeFromPairingQr(pairingUri)
            advanceUntilIdle()

            val pairingRequest = channel.sentEnvelopes.single { it.type == MessageType.PairingRequest }
            channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.PairingResult,
                    requestId = pairingRequest.requestId,
                    payload = json.encodeToJsonElement(
                        PairingResultPayload.serializer(),
                        PairingResultPayload(
                            accepted = true,
                            runtimeDeviceIdV2 = "runtime-accepted",
                            runtimePublicKey = "runtime-public-key",
                            runtimeKeyFingerprint = "runtime-fingerprint",
                            trustedDeviceId = "client-1",
                            message = "trusted",
                        ),
                    ).jsonObject,
                )
            )
            advanceUntilIdle()

            viewModel.trustRuntimeFromPairingQr(routeRefreshUri)
            advanceUntilIdle()

            val trusted = requireNotNull(trustedRuntimeStore.trusted)
            assertEquals(0, directConnectionAttempts)
            assertEquals(1, relayConnectionAttempts)
            assertTrue(channel.isConnected)
            assertEquals("route-refreshed", trusted.routeToken)
            assertEquals("relay-refreshed.example.test", trusted.relayHost)
            assertEquals("relay-refreshed", trusted.relayId)
            assertEquals("secret-refreshed", trusted.relaySecret)
            val state = viewModel.state.value
            assertEquals("relay-refreshed.example.test", state.trustedRuntime?.relayHost)
            assertEquals(RuntimeActiveRouteKind.Relay, state.activeRouteKind)
            assertTrue(state.isConnected)
            assertNull(state.error)
        } finally {
            viewModel?.clearForTest()
            advanceUntilIdle()
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun routeRefreshQrAfterAcceptedP2pPairingDoesNotOpenDuplicatePeerConnection() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        var viewModel: RuntimeClientViewModel? = null
        try {
            val pairingUri = "aetherlink://pair?v=1&n=nonce-p2p-accepted&c=135790" +
                "&rid=runtime-p2p-accepted&rn=AetherLink%20Runtime&rf=runtime-fingerprint" +
                "&rk=runtime-public-key&rt=route-p2p-accepted" +
                "&pc=p2p_rendezvous&prid=p2p-accepted&peb=opaque-accepted" +
                "&px=4102444800000&pn=nonce-p2p-accepted&pv=1"
            val routeRefreshUri = "aetherlink://pair?v=1&n=nonce-p2p-refresh&c=246810" +
                "&rid=runtime-p2p-accepted&rn=AetherLink%20Runtime&rf=runtime-fingerprint" +
                "&rk=runtime-public-key&rt=route-p2p-refreshed" +
                "&pc=p2p_rendezvous&prid=p2p-refreshed&peb=opaque-refreshed" +
                "&px=4102444900000&pn=nonce-p2p-refreshed&pv=1"
            val channel = ScriptedRuntimeProtocolChannel()
            val trustedRuntimeStore = FakeEmittingTrustedRuntimeStore(null)
            val localStore = FakeRuntimeLocalDataStore(
                initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = true),
            )
            var directConnectionAttempts = 0
            var relayConnectionAttempts = 0
            var peerToPeerConnectionAttempts = 0
            viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        directConnectionAttempts += 1
                        error("Direct TCP should not be used for P2P QR pairing or refresh")
                    },
                    peerToPeerConnector = RuntimePeerToPeerConnector { route, _ ->
                        peerToPeerConnectionAttempts += 1
                        assertEquals("p2p-accepted", route.sessionId)
                        assertEquals("opaque-accepted", route.encryptedCandidateMaterial)
                        assertEquals("nonce-p2p-accepted", route.security.antiReplayNonce)
                        channel
                    },
                    relayConnector = RuntimeRelayConnector { _, _ ->
                        relayConnectionAttempts += 1
                        error("Relay should not be used for P2P QR pairing or refresh")
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedRuntimeStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = localStore,
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    currentTimeMillis = { 1_000L },
                ),
            )

            viewModel.trustRuntimeFromPairingQr(pairingUri)
            advanceUntilIdle()

            val pairingRequest = channel.sentEnvelopes.single { it.type == MessageType.PairingRequest }
            channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.PairingResult,
                    requestId = pairingRequest.requestId,
                    payload = json.encodeToJsonElement(
                        PairingResultPayload.serializer(),
                        PairingResultPayload(
                            accepted = true,
                            runtimeDeviceIdV2 = "runtime-p2p-accepted",
                            runtimePublicKey = "runtime-public-key",
                            runtimeKeyFingerprint = "runtime-fingerprint",
                            trustedDeviceId = "client-1",
                            message = "trusted",
                        ),
                    ).jsonObject,
                )
            )
            advanceUntilIdle()

            viewModel.trustRuntimeFromPairingQr(routeRefreshUri)
            advanceUntilIdle()

            val trusted = requireNotNull(trustedRuntimeStore.trusted)
            assertEquals(0, directConnectionAttempts)
            assertEquals(0, relayConnectionAttempts)
            assertEquals(1, peerToPeerConnectionAttempts)
            assertTrue(channel.isConnected)
            assertEquals("route-p2p-refreshed", trusted.routeToken)
            assertNull(trusted.relayHost)
            assertNull(trusted.relaySecret)
            assertEquals("p2p_rendezvous", trusted.p2pRouteClass)
            assertEquals("p2p-refreshed", trusted.p2pRecordId)
            assertEquals("opaque-refreshed", trusted.p2pEncryptedBody)
            assertEquals(4102444900000L, trusted.p2pExpiresAtEpochMillis)
            assertEquals("nonce-p2p-refreshed", trusted.p2pAntiReplayNonce)
            assertEquals(1, trusted.p2pProtocolVersion)
            val state = viewModel.state.value
            assertEquals("p2p-refreshed", state.trustedRuntime?.p2pRecordId)
            assertEquals(RuntimeActiveRouteKind.PeerToPeer, state.activeRouteKind)
            assertTrue(state.isConnected)
            assertNull(state.error)
        } finally {
            viewModel?.clearForTest()
            advanceUntilIdle()
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun invalidPairingQrDoesNotEnableTrustedRuntimeAutoReconnect() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val localStore = FakeRuntimeLocalDataStore(
                initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = false),
            )
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Invalid QR must not start a runtime connection")
                    },
                    relayConnector = RuntimeRelayConnector { _, _ ->
                        error("Invalid QR must not start a relay connection")
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = FakeTrustedRuntimeStore(),
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = localStore,
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    currentTimeMillis = { 1_000L },
                ),
            )

            viewModel.trustRuntimeFromPairingQr("aetherlink://pair?pairing_code=123456")
            advanceUntilIdle()

            assertFalse(localStore.data.trustedRuntimeAutoReconnectEnabled)
            assertFalse(viewModel.state.value.trustedRuntimeAutoReconnectEnabled)
            assertEquals("invalid_pairing_qr", viewModel.state.value.error?.code)
            assertNull(localStore.data.pendingPairingRoute)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun trustRuntimeFromMacosPrivateOverlayQrConnectsRelayAndSendsPairingRequest() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val rawUri = sharedProtocolFixture("macos-compact-private-overlay-pairing-uri.txt")
            val channel = CapturingRuntimeProtocolChannel()
            var directConnectionAttempts = 0
            var capturedRelayRoute: PreparedRemoteRuntimeRoute.Relay? = null
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        directConnectionAttempts += 1
                        error("Direct TCP should not be used for private-overlay relay QR pairing")
                    },
                    relayConnector = RuntimeRelayConnector { route, _ ->
                        capturedRelayRoute = route
                        channel
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = FakeTrustedRuntimeStore(),
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = FakeRuntimeLocalDataStore(),
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    currentTimeMillis = { 1_000L },
                ),
            )

            viewModel.trustRuntimeFromPairingQr(rawUri)
            advanceUntilIdle()

            val relayRoute = requireNotNull(capturedRelayRoute)
            val pairingEnvelope = channel.sentEnvelopes.single { it.type == MessageType.PairingRequest }
            val pairingPayload = json.decodeFromJsonElement(
                PairingRequestPayload.serializer(),
                pairingEnvelope.payload,
            )
            assertEquals(0, directConnectionAttempts)
            assertEquals("100.64.1.10", relayRoute.host)
            assertEquals(43171, relayRoute.port)
            assertEquals("relay-private-overlay-1", relayRoute.relayId)
            assertEquals("secret-private-overlay-1", relayRoute.relayFrameSecret)
            assertEquals("private-overlay-nonce-1", relayRoute.security.antiReplayNonce)
            assertEquals("nonce-private-1", pairingPayload.pairingNonce)
            assertEquals("654321", pairingPayload.pairingCode)
            assertEquals("client-1", pairingPayload.deviceId)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun relayPairingQrPersistsPendingRouteAfterInitialConnectionFailure() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val rawUri = "aetherlink://pair?v=1&n=nonce-1&c=123456" +
                "&rid=runtime-1&rn=AetherLink%20Runtime&rf=runtime-fingerprint" +
                "&rk=runtime-public-key&rt=route-1" +
                "&rh=relay.example.test&rp=443&ri=relay-1&rs=secret-1" +
                "&rx=4102444800000&rrn=nonce-route-1&rsc=remote"
            val localStore = FakeRuntimeLocalDataStore()
            var directConnectionAttempts = 0
            var relayConnectionAttempts = 0
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        directConnectionAttempts += 1
                        error("Direct TCP should not be used for relay QR pairing")
                    },
                    relayConnector = RuntimeRelayConnector { route, _ ->
                        relayConnectionAttempts += 1
                        assertEquals("relay.example.test", route.host)
                        assertEquals("relay-1", route.relayId)
                        assertEquals("secret-1", route.relayFrameSecret)
                        assertEquals("nonce-route-1", route.security.antiReplayNonce)
                        error("Relay route is still warming up")
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = FakeTrustedRuntimeStore(),
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = localStore,
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    currentTimeMillis = { 1_000L },
                ),
            )

            viewModel.trustRuntimeFromPairingQr(rawUri)
            runCurrent()

            val pending = requireNotNull(localStore.data.pendingPairingRoute)
            assertEquals(0, directConnectionAttempts)
            assertEquals(1, relayConnectionAttempts)
            assertEquals("nonce-1", pending.pairingNonce)
            assertEquals("123456", pending.pairingCode)
            assertEquals("runtime-1", pending.runtimeDeviceId)
            assertEquals("relay.example.test", pending.relayHost)
            assertEquals(443, pending.relayPort)
            assertEquals("relay-1", pending.relayId)
            assertNull(pending.relaySecret)
            assertNotNull(pending.relaySecretRef)
            assertEquals(4102444800000L, pending.relayExpiresAtEpochMillis)
            assertEquals("nonce-route-1", pending.relayNonce)
            assertEquals("remote", pending.relayScope)
            assertEquals("pairing_route_retrying", viewModel.state.value.error?.code)
            viewModel.disconnect()
            runCurrent()
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun relayPairingQrRetriesAndSendsPairingRequestAfterRelayBecomesReady() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val rawUri = "aetherlink://pair?v=1&n=nonce-retry&c=246810" +
                "&rid=runtime-retry&rn=AetherLink%20Runtime&rf=runtime-fingerprint" +
                "&rk=runtime-public-key&rt=route-retry" +
                "&rh=relay-retry.example.test&rp=443&ri=relay-retry&rs=secret-retry" +
                "&rx=4102444800000&rrn=nonce-route-retry&rsc=remote"
            val localStore = FakeRuntimeLocalDataStore()
            val channel = ScriptedRuntimeProtocolChannel()
            var directConnectionAttempts = 0
            var relayConnectionAttempts = 0
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        directConnectionAttempts += 1
                        error("Direct TCP should not be used for relay QR pairing retry")
                    },
                    relayConnector = RuntimeRelayConnector { route, _ ->
                        relayConnectionAttempts += 1
                        assertEquals("relay-retry.example.test", route.host)
                        assertEquals("relay-retry", route.relayId)
                        assertEquals("secret-retry", route.relayFrameSecret)
                        assertEquals("nonce-route-retry", route.security.antiReplayNonce)
                        if (relayConnectionAttempts == 1) {
                            error("Relay route is still warming up")
                        }
                        channel
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = FakeTrustedRuntimeStore(),
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = localStore,
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    currentTimeMillis = { 1_000L },
                ),
            )

            viewModel.trustRuntimeFromPairingQr(rawUri)
            runCurrent()

            assertEquals(0, directConnectionAttempts)
            assertEquals(1, relayConnectionAttempts)
            assertEquals("pairing_route_retrying", viewModel.state.value.error?.code)
            assertNotNull(localStore.data.pendingPairingRoute)

            advanceTimeBy(750L)
            runCurrent()

            val pairingEnvelope = channel.sentEnvelopes.single { it.type == MessageType.PairingRequest }
            val pairingPayload = json.decodeFromJsonElement(
                PairingRequestPayload.serializer(),
                pairingEnvelope.payload,
            )
            assertEquals(0, directConnectionAttempts)
            assertEquals(2, relayConnectionAttempts)
            assertEquals("nonce-retry", pairingPayload.pairingNonce)
            assertEquals("246810", pairingPayload.pairingCode)
            assertEquals("client-1", pairingPayload.deviceId)
            assertEquals("AetherLink Test Client", pairingPayload.deviceName)
            assertEquals("client-public-key", pairingPayload.publicKey)
            assertNull(viewModel.state.value.error)
            assertNotNull(localStore.data.pendingPairingRoute)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun recreatedViewModelRestoresPendingRelayPairingAndSendsPairingRequest() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val payload = runtimePairingPayload(
                pairingNonce = "nonce-restored",
                pairingCode = "654321",
                runtimeDeviceId = "runtime-restored",
                runtimeName = "AetherLink Runtime",
                fingerprint = "runtime-fingerprint",
                runtimePublicKeyBase64 = "runtime-public-key",
                routeToken = "route-restored",
                host = null,
                port = null,
                relayHost = "relay-restored.example.test",
                relayPort = 443,
                relayId = "relay-restored",
                relaySecret = "secret-restored",
                relayExpiresAtEpochMillis = 4102444800000L,
                relayNonce = "nonce-route-restored",
                relayScope = "remote",
            )
            val localStore = FakeRuntimeLocalDataStore(
                initialData = PersistedRuntimeData().withPendingPairingRoute(payload, nowMillis = 1_000L),
            )
            val channel = CapturingRuntimeProtocolChannel()
            var directConnectionAttempts = 0
            var capturedRelayRoute: PreparedRemoteRuntimeRoute.Relay? = null

            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        directConnectionAttempts += 1
                        error("Direct TCP should not be used when restoring pending relay QR pairing")
                    },
                    relayConnector = RuntimeRelayConnector { route, _ ->
                        capturedRelayRoute = route
                        channel
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = FakeTrustedRuntimeStore(),
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = localStore,
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    currentTimeMillis = { 2_000L },
                ),
            )
            advanceUntilIdle()

            val relayRoute = requireNotNull(capturedRelayRoute)
            val pairingEnvelope = channel.sentEnvelopes.single { it.type == MessageType.PairingRequest }
            val pairingPayload = json.decodeFromJsonElement(
                PairingRequestPayload.serializer(),
                pairingEnvelope.payload,
            )
            assertEquals(0, directConnectionAttempts)
            assertEquals("relay-restored.example.test", relayRoute.host)
            assertEquals(443, relayRoute.port)
            assertEquals("relay-restored", relayRoute.relayId)
            assertEquals("secret-restored", relayRoute.relayFrameSecret)
            assertEquals("nonce-route-restored", relayRoute.security.antiReplayNonce)
            assertEquals("nonce-restored", pairingPayload.pairingNonce)
            assertEquals("654321", pairingPayload.pairingCode)
            assertEquals("client-1", pairingPayload.deviceId)
            assertEquals("AetherLink Test Client", pairingPayload.deviceName)
            assertEquals("client-public-key", pairingPayload.publicKey)
            assertNotNull(localStore.data.pendingPairingRoute)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun routeRefreshQrKeepsUnreachableRelayRouteForRetryOrFreshQrRecovery() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val rawUri = "aetherlink://pair?v=1&n=nonce-refresh&c=654321" +
                "&rid=runtime-1&rn=AetherLink%20Runtime&rf=runtime-fingerprint" +
                "&rk=runtime-public-key&rt=route-1" +
                "&rh=relay-refresh.example.test&rp=443&ri=relay-refresh&rs=secret-refresh" +
                "&rx=4102444800000&rrn=nonce-refresh-route&rsc=remote"
            val initialTrustedRuntime = TrustedRuntime(
                deviceId = "runtime-1",
                name = "AetherLink Runtime",
                fingerprint = "runtime-fingerprint",
                publicKeyBase64 = "runtime-public-key",
                routeToken = "route-1",
                host = null,
                port = null,
            )
            val channel = ScriptedRuntimeProtocolChannel()
            val trustedRuntimeStore = FakeEmittingTrustedRuntimeStore(initialTrustedRuntime)
            val localStore = FakeRuntimeLocalDataStore()
            var directConnectionAttempts = 0
            var relayConnectionAttempts = 0
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        directConnectionAttempts += 1
                        error("Direct TCP should not be used for relay route refresh")
                    },
                    relayConnector = RuntimeRelayConnector { route, _ ->
                        relayConnectionAttempts += 1
                        assertEquals("relay-refresh.example.test", route.host)
                        assertEquals("relay-refresh", route.relayId)
                        assertEquals("secret-refresh", route.relayFrameSecret)
                        assertEquals("nonce-refresh-route", route.security.antiReplayNonce)
                        if (relayConnectionAttempts == 1) {
                            error("Relay route is still warming up")
                        }
                        channel
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedRuntimeStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = localStore,
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    currentTimeMillis = { 1_000L },
                ),
            )
            advanceUntilIdle()

            viewModel.trustRuntimeFromPairingQr(rawUri)
            advanceUntilIdle()

            assertEquals(0, directConnectionAttempts)
            assertEquals(1, relayConnectionAttempts)
            val trusted = trustedRuntimeStore.trusted ?: error("Expected trusted runtime to remain pinned")
            assertEquals("runtime-1", trusted.deviceId)
            assertEquals("runtime-fingerprint", trusted.fingerprint)
            assertEquals("runtime-public-key", trusted.publicKeyBase64)
            assertEquals("route-1", trusted.routeToken)
            assertEquals("relay-refresh.example.test", trusted.relayHost)
            assertEquals(443, trusted.relayPort)
            assertEquals("relay-refresh", trusted.relayId)
            assertEquals("secret-refresh", trusted.relaySecret)
            assertEquals(4102444800000L, trusted.relayExpiresAtEpochMillis)
            assertEquals("nonce-refresh-route", trusted.relayNonce)
            assertEquals("remote", trusted.relayScope)
            assertNull(localStore.data.pendingPairingRoute)
            assertEquals("relay-refresh.example.test", viewModel.state.value.trustedRuntime?.relayHost)
            assertEquals("secret-refresh", viewModel.state.value.trustedRuntime?.relaySecret)
            assertEquals("runtime-1", viewModel.state.value.trustedRuntime?.deviceId)
            assertEquals("remote_route_unreachable", viewModel.state.value.error?.code)
            assertEquals("route_diagnostic_relay_failed", viewModel.state.value.error?.diagnosticCode)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun trustedRelayReconnectAttemptsRelayBeforeMatchingBonjourFallback() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val trustedStore = FakeEmittingTrustedRuntimeStore(
                TrustedRuntime(
                    deviceId = "runtime-1",
                    name = "AetherLink Runtime",
                    fingerprint = "runtime-fingerprint",
                    publicKeyBase64 = "runtime-public-key",
                    routeToken = "route-token-1",
                    relayHost = "relay-fallback.example.test",
                    relayPort = 443,
                    relayId = "relay-fallback",
                    relaySecret = "secret-fallback",
                    relayExpiresAtEpochMillis = 4102444800000L,
                    relayNonce = "nonce-fallback",
                    relayScope = "remote",
                ),
            )
            val discoveredPeers = MutableStateFlow(
                listOf(
                    DiscoveredRuntime(
                        serviceName = "AetherLink Runtime",
                        host = "192.168.1.44",
                        port = 43170,
                        routeToken = "route-token-1",
                        deviceId = "runtime-1",
                        fingerprint = "runtime-fingerprint",
                    )
                )
            )
            val channel = ScriptedRuntimeProtocolChannel()
            var relayConnectionAttempts = 0
            var directConnectionAttempts = 0
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { host, port, _ ->
                        directConnectionAttempts += 1
                        assertEquals("192.168.1.44", host)
                        assertEquals(43170, port)
                        channel
                    },
                    relayConnector = RuntimeRelayConnector { route, _ ->
                        relayConnectionAttempts += 1
                        assertEquals("relay-fallback.example.test", route.host)
                        assertEquals("relay-fallback", route.relayId)
                        assertEquals("secret-fallback", route.relayFrameSecret)
                        assertEquals("nonce-fallback", route.security.antiReplayNonce)
                        error("Relay route unavailable")
                    },
                    relayReachabilityChecker = RuntimeRelayReachabilityChecker { _, _ ->
                        error("Fresh discovery routes should not be blocked by relay preflight")
                    },
                    discovery = object : RuntimeDiscoverySource {
                        override fun discover(): Flow<List<DiscoveredRuntime>> = discoveredPeers
                    },
                    trustedRuntimeStore = trustedStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = FakeRuntimeLocalDataStore(
                        initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = false),
                    ),
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    currentTimeMillis = { 1_000L },
                ),
            )
            advanceUntilIdle()

            viewModel.startDiscovery()
            runCurrent()
            viewModel.connectToTrustedRuntime()
            advanceUntilIdle()

            val helloEnvelope = channel.sentEnvelopes.single { it.type == MessageType.Hello }
            assertEquals(1, relayConnectionAttempts)
            assertEquals(1, directConnectionAttempts)
            assertEquals("192.168.1.44", viewModel.state.value.runtimeHost)
            assertEquals("43170", viewModel.state.value.runtimePort)
            assertEquals(RuntimeEndpointSource.BonjourDiscovery, viewModel.state.value.runtimeEndpointSource)
            assertEquals(RuntimeActiveRouteKind.DirectTcp, viewModel.state.value.activeRouteKind)
            assertEquals(MessageType.Hello, helloEnvelope.type)
            assertNull(viewModel.state.value.error)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun authenticatedTrustedRuntimeRefreshesRelayRouteMaterial() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val channel = ScriptedRuntimeProtocolChannel()
            val trustedStore = FakeEmittingTrustedRuntimeStore(
                TrustedRuntime(
                    deviceId = "runtime-1",
                    name = "AetherLink Runtime",
                    fingerprint = "runtime-fingerprint",
                    publicKeyBase64 = "runtime-public-key",
                    routeToken = "route-token-1",
                    relayHost = "old-relay.example.test",
                    relayPort = 443,
                    relayId = "old-relay",
                    relaySecret = "old-secret",
                    relayExpiresAtEpochMillis = 4_102_444_800_000L,
                    relayNonce = "old-nonce",
                    relayScope = "remote",
                ),
            )
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Direct TCP should not be used for route-refresh relay reconnect")
                    },
                    relayConnector = RuntimeRelayConnector { _, _ -> channel },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = FakeRuntimeLocalDataStore(
                        initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = false),
                    ),
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    authenticatedRouteRefreshEnabled = true,
                    currentTimeMillis = { 1_000L },
                ),
            )
            advanceUntilIdle()

            viewModel.connectToTrustedRuntime()
            advanceUntilIdle()
            channel.enqueue(
                envelope(
                    type = MessageType.AuthResponse,
                    serializer = AuthResponsePayload.serializer(),
                    payload = AuthResponsePayload(accepted = true),
                    requestId = "auth-accepted",
                ),
            )
            advanceUntilIdle()

            val routeRefreshRequest = channel.sentEnvelopes.single { it.type == MessageType.RouteRefresh }
            channel.enqueue(
                envelope(
                    type = MessageType.RouteRefresh,
                    serializer = RouteRefreshPayload.serializer(),
                    payload = RouteRefreshPayload(
                        runtimeDeviceId = "runtime-1",
                        runtimeKeyFingerprint = "runtime-fingerprint",
                        relayHost = "fresh-relay.example.test",
                        relayPort = 43171,
                        relayId = "fresh-relay",
                        relaySecret = "fresh-secret",
                        relayExpiresAtEpochMillis = 4_102_444_900_000L,
                        relayNonce = "fresh-nonce",
                        relayScope = "remote",
                    ),
                    requestId = routeRefreshRequest.requestId,
                ),
            )
            advanceUntilIdle()

            val trusted = trustedStore.trusted ?: error("Expected route refresh to persist trusted runtime")
            assertEquals("fresh-relay.example.test", trusted.relayHost)
            assertEquals(43171, trusted.relayPort)
            assertEquals("fresh-relay", trusted.relayId)
            assertEquals("fresh-secret", trusted.relaySecret)
            assertEquals(4_102_444_900_000L, trusted.relayExpiresAtEpochMillis)
            assertEquals("fresh-nonce", trusted.relayNonce)
            assertEquals("remote", trusted.relayScope)
            assertEquals("fresh-relay.example.test", viewModel.state.value.trustedRuntime?.relayHost)
            viewModel.clearForTest()
            runCurrent()
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun authenticatedTrustedRuntimeRejectsRouteRefreshPayloadWithUnknownMetadataBeforeStorage() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        var runtimeViewModel: RuntimeClientViewModel? = null
        try {
            var currentTimeMillis = 1_000L
            val currentRelayExpiry = currentTimeMillis + 180_000L
            val channel = ScriptedRuntimeProtocolChannel()
            val trustedStore = FakeEmittingTrustedRuntimeStore(
                TrustedRuntime(
                    deviceId = "runtime-1",
                    name = "AetherLink Runtime",
                    fingerprint = "runtime-fingerprint",
                    publicKeyBase64 = "runtime-public-key",
                    routeToken = "route-token-1",
                    relayHost = "relay.example.test",
                    relayPort = 443,
                    relayId = "stable-relay",
                    relaySecret = "stable-secret",
                    relayExpiresAtEpochMillis = currentRelayExpiry,
                    relayNonce = "nonce-route-1",
                    relayScope = "remote",
                ),
            )
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Direct TCP should not be used for route-refresh metadata rejection")
                    },
                    relayConnector = RuntimeRelayConnector { _, _ -> channel },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = FakeRuntimeLocalDataStore(
                        initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = false),
                    ),
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    authenticatedRouteRefreshEnabled = true,
                    currentTimeMillis = { currentTimeMillis },
                ),
            )
            runtimeViewModel = viewModel
            advanceUntilIdle()

            viewModel.connectToTrustedRuntime()
            advanceUntilIdle()
            channel.enqueue(
                envelope(
                    type = MessageType.AuthResponse,
                    serializer = AuthResponsePayload.serializer(),
                    payload = AuthResponsePayload(accepted = true),
                    requestId = "auth-accepted",
                ),
            )
            runCurrent()

            val firstRouteRefreshDelay = runtimeRouteRefreshLeaseDelayMillis(
                nowEpochMillis = currentTimeMillis,
                remoteRouteExpiresAtEpochMillis = trustedStore.trusted?.relayExpiresAtEpochMillis,
            ) ?: error("Expected trusted relay lease to schedule route refresh")
            advanceTimeBy(firstRouteRefreshDelay)
            currentTimeMillis += firstRouteRefreshDelay
            runCurrent()

            val routeRefreshRequest = channel.sentEnvelopes.single { it.type == MessageType.RouteRefresh }
            val routeRefreshPayload = RouteRefreshPayload(
                runtimeDeviceId = "runtime-1",
                runtimeKeyFingerprint = "runtime-fingerprint",
                relayHost = "fresh-relay.example.test",
                relayPort = 43171,
                relayId = "stable-relay",
                relaySecret = "stable-secret",
                relayExpiresAtEpochMillis = currentTimeMillis + 240_000L,
                relayNonce = "nonce-route-2",
                relayScope = "remote",
            )
            channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.RouteRefresh,
                    requestId = routeRefreshRequest.requestId,
                    payload = JsonObject(
                        json.encodeToJsonElement(RouteRefreshPayload.serializer(), routeRefreshPayload)
                            .jsonObject + ("backend_url" to JsonPrimitive("http://127.0.0.1:11434")),
                    ),
                ),
            )
            runCurrent()

            assertEquals("relay.example.test", trustedStore.trusted?.relayHost)
            assertEquals(443, trustedStore.trusted?.relayPort)
            assertEquals("stable-relay", trustedStore.trusted?.relayId)
            assertEquals("stable-secret", trustedStore.trusted?.relaySecret)
            assertEquals(currentRelayExpiry, trustedStore.trusted?.relayExpiresAtEpochMillis)
            assertEquals("nonce-route-1", trustedStore.trusted?.relayNonce)
            assertEquals("relay.example.test", viewModel.state.value.trustedRuntime?.relayHost)
            assertNull(viewModel.state.value.error)
            assertNull(viewModel.privateField<String>("pendingRouteRefreshRequestId"))
            assertNotNull(viewModel.privateField<Any>("routeRefreshLeaseJob"))
            assertEquals(1, channel.sentEnvelopes.count { it.type == MessageType.RouteRefresh })
        } finally {
            runtimeViewModel?.clearForTest()
            runCurrent()
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun authenticatedTrustedRuntimeRetriesMalformedRouteRefreshAllowedFieldPayloadBeforeLeaseExpiry() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        var runtimeViewModel: RuntimeClientViewModel? = null
        try {
            var currentTimeMillis = 1_000L
            val currentRelayExpiry = currentTimeMillis + 180_000L
            val channel = ScriptedRuntimeProtocolChannel()
            val trustedStore = FakeEmittingTrustedRuntimeStore(
                TrustedRuntime(
                    deviceId = "runtime-1",
                    name = "AetherLink Runtime",
                    fingerprint = "runtime-fingerprint",
                    publicKeyBase64 = "runtime-public-key",
                    routeToken = "route-token-1",
                    relayHost = "relay.example.test",
                    relayPort = 443,
                    relayId = "stable-relay",
                    relaySecret = "stable-secret",
                    relayExpiresAtEpochMillis = currentRelayExpiry,
                    relayNonce = "nonce-route-1",
                    relayScope = "remote",
                ),
            )
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Direct TCP should not be used for malformed route-refresh retry")
                    },
                    relayConnector = RuntimeRelayConnector { _, _ -> channel },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = FakeRuntimeLocalDataStore(
                        initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = false),
                    ),
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    authenticatedRouteRefreshEnabled = true,
                    currentTimeMillis = { currentTimeMillis },
                ),
            )
            runtimeViewModel = viewModel
            advanceUntilIdle()

            viewModel.connectToTrustedRuntime()
            advanceUntilIdle()
            channel.enqueue(
                envelope(
                    type = MessageType.AuthResponse,
                    serializer = AuthResponsePayload.serializer(),
                    payload = AuthResponsePayload(accepted = true),
                    requestId = "auth-accepted",
                ),
            )
            runCurrent()

            val firstRouteRefreshDelay = runtimeRouteRefreshLeaseDelayMillis(
                nowEpochMillis = currentTimeMillis,
                remoteRouteExpiresAtEpochMillis = trustedStore.trusted?.relayExpiresAtEpochMillis,
            ) ?: error("Expected trusted relay lease to schedule route refresh")
            advanceTimeBy(firstRouteRefreshDelay)
            currentTimeMillis += firstRouteRefreshDelay
            runCurrent()

            val routeRefreshRequest = channel.sentEnvelopes.single { it.type == MessageType.RouteRefresh }
            channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.RouteRefresh,
                    requestId = routeRefreshRequest.requestId,
                    payload = JsonObject(
                        mapOf(
                            "runtime_device_id" to JsonPrimitive(7),
                            "runtime_key_fingerprint" to JsonPrimitive("runtime-fingerprint"),
                            "relay_host" to JsonPrimitive("fresh-relay.example.test"),
                            "relay_port" to JsonPrimitive("43171"),
                            "relay_id" to JsonPrimitive("stable-relay"),
                            "relay_secret" to JsonPrimitive("stable-secret"),
                            "relay_expires_at" to JsonPrimitive("not-an-integer"),
                            "relay_nonce" to JsonPrimitive("nonce-route-2"),
                            "relay_scope" to JsonPrimitive("remote"),
                            "p2p_protocol_version" to JsonPrimitive("1"),
                        ),
                    ),
                ),
            )
            runCurrent()

            assertEquals("relay.example.test", trustedStore.trusted?.relayHost)
            assertEquals(443, trustedStore.trusted?.relayPort)
            assertEquals("stable-relay", trustedStore.trusted?.relayId)
            assertEquals("stable-secret", trustedStore.trusted?.relaySecret)
            assertEquals(currentRelayExpiry, trustedStore.trusted?.relayExpiresAtEpochMillis)
            assertEquals("nonce-route-1", trustedStore.trusted?.relayNonce)
            assertEquals("relay.example.test", viewModel.state.value.trustedRuntime?.relayHost)
            assertNull(viewModel.state.value.error)
            assertTrue(viewModel.state.value.isConnected)
            assertNull(viewModel.privateField<String>("pendingRouteRefreshRequestId"))
            assertNotNull(viewModel.privateField<Any>("routeRefreshLeaseJob"))
            assertEquals(1, channel.sentEnvelopes.count { it.type == MessageType.RouteRefresh })

            advanceTimeBy(ROUTE_REFRESH_RETRY_DELAY_MS)
            currentTimeMillis += ROUTE_REFRESH_RETRY_DELAY_MS
            runCurrent()

            val routeRefreshRequests = channel.sentEnvelopes.filter { it.type == MessageType.RouteRefresh }
            assertEquals(2, routeRefreshRequests.size)
            assertTrue(routeRefreshRequests[1].requestId != routeRefreshRequests[0].requestId)
        } finally {
            runtimeViewModel?.clearForTest()
            runCurrent()
            Dispatchers.resetMain()
        }
    }

    @Test
    fun runtimeRouteRefreshLeaseDelayUsesRenewalWindow() {
        assertEquals(
            120_000L,
            runtimeRouteRefreshLeaseDelayMillis(
                nowEpochMillis = 1_000L,
                remoteRouteExpiresAtEpochMillis = 181_000L,
            ),
        )
        assertEquals(
            ROUTE_REFRESH_LEASE_MIN_DELAY_MS,
            runtimeRouteRefreshLeaseDelayMillis(
                nowEpochMillis = 1_000L,
                remoteRouteExpiresAtEpochMillis = 61_500L,
            ),
        )
        assertNull(
            runtimeRouteRefreshLeaseDelayMillis(
                nowEpochMillis = 1_000L,
                remoteRouteExpiresAtEpochMillis = null,
            ),
        )
        assertNull(
            runtimeRouteRefreshLeaseDelayMillis(
                nowEpochMillis = 1_000L,
                remoteRouteExpiresAtEpochMillis = 1_000L,
            ),
        )
    }

    @Test
    fun runtimeRouteRefreshRetryDelayStaysInsideActiveLease() {
        assertEquals(
            ROUTE_REFRESH_RETRY_DELAY_MS,
            runtimeRouteRefreshRetryDelayMillis(
                nowEpochMillis = 1_000L,
                remoteRouteExpiresAtEpochMillis = 30_000L,
            ),
        )
        assertEquals(
            3_000L,
            runtimeRouteRefreshRetryDelayMillis(
                nowEpochMillis = 1_000L,
                remoteRouteExpiresAtEpochMillis = 5_000L,
            ),
        )
        assertNull(
            runtimeRouteRefreshRetryDelayMillis(
                nowEpochMillis = 1_000L,
                remoteRouteExpiresAtEpochMillis = 2_000L,
            ),
        )
        assertNull(
            runtimeRouteRefreshRetryDelayMillis(
                nowEpochMillis = 1_000L,
                remoteRouteExpiresAtEpochMillis = null,
            ),
        )
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun authenticatedTrustedRuntimeSchedulesRouteRefreshBeforeLeaseExpiry() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            var currentTimeMillis = 1_000L
            val channel = ScriptedRuntimeProtocolChannel()
            val trustedStore = FakeEmittingTrustedRuntimeStore(
                TrustedRuntime(
                    deviceId = "runtime-1",
                    name = "AetherLink Runtime",
                    fingerprint = "runtime-fingerprint",
                    publicKeyBase64 = "runtime-public-key",
                    routeToken = "route-token-1",
                    relayHost = "old-relay.example.test",
                    relayPort = 443,
                    relayId = "old-relay",
                    relaySecret = "old-secret",
                    relayExpiresAtEpochMillis = currentTimeMillis + 600_000L,
                    relayNonce = "old-nonce",
                    relayScope = "remote",
                ),
            )
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Direct TCP should not be used for scheduled route-refresh relay reconnect")
                    },
                    relayConnector = RuntimeRelayConnector { _, _ -> channel },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = FakeRuntimeLocalDataStore(
                        initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = false),
                    ),
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    authenticatedRouteRefreshEnabled = true,
                    currentTimeMillis = { currentTimeMillis },
                ),
            )
            advanceUntilIdle()

            viewModel.connectToTrustedRuntime()
            advanceUntilIdle()
            channel.enqueue(
                envelope(
                    type = MessageType.AuthResponse,
                    serializer = AuthResponsePayload.serializer(),
                    payload = AuthResponsePayload(accepted = true),
                    requestId = "auth-accepted",
                ),
            )
            runCurrent()

            assertEquals(0, channel.sentEnvelopes.count { it.type == MessageType.RouteRefresh })

            advanceTimeBy(539_999L)
            currentTimeMillis += 539_999L
            runCurrent()
            assertEquals(0, channel.sentEnvelopes.count { it.type == MessageType.RouteRefresh })

            advanceTimeBy(1L)
            currentTimeMillis += 1L
            runCurrent()

            val routeRefreshRequest = channel.sentEnvelopes.single { it.type == MessageType.RouteRefresh }
            channel.enqueue(
                envelope(
                    type = MessageType.RouteRefresh,
                    serializer = RouteRefreshPayload.serializer(),
                    payload = RouteRefreshPayload(
                        runtimeDeviceId = "runtime-1",
                        runtimeKeyFingerprint = "runtime-fingerprint",
                        relayHost = "fresh-relay.example.test",
                        relayPort = 43171,
                        relayId = "fresh-relay",
                        relaySecret = "fresh-secret",
                        relayExpiresAtEpochMillis = currentTimeMillis + 180_000L,
                        relayNonce = "fresh-nonce",
                        relayScope = "remote",
                    ),
                    requestId = routeRefreshRequest.requestId,
                ),
            )
            runCurrent()

            advanceTimeBy(119_999L)
            currentTimeMillis += 119_999L
            runCurrent()
            assertEquals(1, channel.sentEnvelopes.count { it.type == MessageType.RouteRefresh })

            advanceTimeBy(1L)
            currentTimeMillis += 1L
            runCurrent()

            val routeRefreshRequests = channel.sentEnvelopes.filter { it.type == MessageType.RouteRefresh }
            assertEquals(2, routeRefreshRequests.size)
            assertTrue(routeRefreshRequests[1].requestId != routeRefreshRequests[0].requestId)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun authChallengeRejectsUnknownMetadataBeforeAuthResponseSigning() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val channel = ScriptedRuntimeProtocolChannel()
            val trustedStore = FakeEmittingTrustedRuntimeStore(
                TrustedRuntime(
                    deviceId = "runtime-auth-challenge",
                    name = "AetherLink Runtime",
                    fingerprint = "runtime-fingerprint",
                    publicKeyBase64 = null,
                    routeToken = "route-token-1",
                    relayHost = "relay-auth-challenge.example.test",
                    relayPort = 443,
                    relayId = "relay-auth-challenge",
                    relaySecret = "secret-auth-challenge",
                    relayExpiresAtEpochMillis = 4102444800000L,
                    relayNonce = "nonce-route-auth-challenge",
                    relayScope = "remote",
                ),
            )
            val localStore = FakeRuntimeLocalDataStore(
                initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = false),
            )
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Direct TCP should not be used for auth challenge metadata rejection")
                    },
                    relayConnector = RuntimeRelayConnector { route, _ ->
                        assertEquals("relay-auth-challenge.example.test", route.host)
                        assertEquals(443, route.port)
                        assertEquals("relay-auth-challenge", route.relayId)
                        assertEquals("secret-auth-challenge", route.relayFrameSecret)
                        assertEquals("nonce-route-auth-challenge", route.security.antiReplayNonce)
                        channel
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = localStore,
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    authenticatedRouteRefreshEnabled = true,
                    currentTimeMillis = { 1_000L },
                ),
            )
            advanceUntilIdle()

            viewModel.connectToTrustedRuntime()
            advanceUntilIdle()

            assertEquals(1, channel.sentEnvelopes.count { it.type == MessageType.Hello })
            val sentCountBeforeRejectedChallenge = channel.sentEnvelopes.size
            channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.AuthChallenge,
                    requestId = "auth-challenge",
                    payload = buildJsonObject {
                        put("device_id", "client-1")
                        put("nonce", "nonce-for-signing")
                        put("backend_url", "http://127.0.0.1:11434")
                    },
                ),
            )
            advanceUntilIdle()

            val rejectedState = viewModel.state.value
            assertEquals("invalid_payload", rejectedState.error?.code)
            assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("auth.challenge response"))
            assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("backend_url"))
            assertFalse(viewModel.privateField<Boolean>("isSessionAuthenticated") == true)
            assertEquals(sentCountBeforeRejectedChallenge, channel.sentEnvelopes.size)
            assertEquals(0, channel.sentEnvelopes.count { it.type == MessageType.AuthResponse })
            assertEquals(0, channel.sentEnvelopes.count { it.type == MessageType.RuntimeHealth })
            assertFalse(json.encodeToString(localStore.data).contains("127.0.0.1:11434"))

            channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.AuthChallenge,
                    requestId = "auth-challenge",
                    payload = buildJsonObject {
                        put("device_id", "client-1")
                        put("nonce", "nonce-for-signing")
                    },
                ),
            )
            advanceUntilIdle()

            val authResponse = channel.sentEnvelopes.single { it.type == MessageType.AuthResponse }
            val payload = json.decodeFromJsonElement(AuthResponsePayload.serializer(), authResponse.payload)
            assertEquals("auth-challenge", authResponse.requestId)
            assertEquals("client-1", payload.deviceId)
            assertEquals("nonce-for-signing", payload.nonce)
            assertNotNull(payload.signature)
            assertFalse(viewModel.privateField<Boolean>("isSessionAuthenticated") == true)
            assertEquals(0, channel.sentEnvelopes.count { it.type == MessageType.RuntimeHealth })
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun authResponseResultRejectsUnknownMetadataBeforeAuthenticationStateMutation() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val channel = ScriptedRuntimeProtocolChannel()
            val trustedStore = FakeEmittingTrustedRuntimeStore(trustedRuntimeForViewModelTests())
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Direct TCP should not be used for auth response metadata rejection")
                    },
                    relayConnector = RuntimeRelayConnector { _, _ -> channel },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = FakeRuntimeLocalDataStore(
                        initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = false),
                    ),
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    authenticatedRouteRefreshEnabled = true,
                    currentTimeMillis = { 1_000L },
                ),
            )
            advanceUntilIdle()

            viewModel.connectToTrustedRuntime()
            advanceUntilIdle()
            val sentCountBeforeRejectedAuth = channel.sentEnvelopes.size
            channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.AuthResponse,
                    requestId = "auth-accepted",
                    payload = buildJsonObject {
                        put("accepted", true)
                        put("device_id", "client-1")
                        put("backend_url", "http://127.0.0.1:11434")
                    },
                ),
            )
            advanceUntilIdle()

            val rejectedState = viewModel.state.value
            assertEquals("invalid_payload", rejectedState.error?.code)
            assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("auth.response response"))
            assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("backend_url"))
            assertFalse(rejectedState.runtimeStatus == "authenticated")
            assertFalse(viewModel.privateField<Boolean>("isSessionAuthenticated") == true)
            assertNull(viewModel.privateField<Any>("routeRefreshLeaseJob"))
            assertEquals(sentCountBeforeRejectedAuth, channel.sentEnvelopes.size)
            assertEquals(0, channel.sentEnvelopes.count { it.type == MessageType.RuntimeHealth })
            assertEquals(0, channel.sentEnvelopes.count { it.type == MessageType.ChatSessionsList })
            assertEquals(0, channel.sentEnvelopes.count { it.type == MessageType.MemoryList })
            assertEquals(0, channel.sentEnvelopes.count { it.type == MessageType.MemorySummaryDraftsList })

            channel.enqueue(
                envelope(
                    type = MessageType.AuthResponse,
                    serializer = AuthResponsePayload.serializer(),
                    payload = AuthResponsePayload(
                        deviceId = "client-1",
                        accepted = true,
                    ),
                    requestId = "auth-accepted",
                ),
            )
            advanceUntilIdle()

            val acceptedState = viewModel.state.value
            assertNull(acceptedState.error)
            assertEquals("authenticated", acceptedState.runtimeStatus)
            assertTrue(viewModel.privateField<Boolean>("isSessionAuthenticated") == true)
            assertEquals(1, channel.sentEnvelopes.count { it.type == MessageType.RuntimeHealth })
            assertEquals(1, channel.sentEnvelopes.count { it.type == MessageType.ChatSessionsList })
            assertEquals(1, channel.sentEnvelopes.count { it.type == MessageType.MemoryList })
            assertEquals(1, channel.sentEnvelopes.count { it.type == MessageType.MemorySummaryDraftsList })
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun authenticatedTrustedP2pRuntimeSchedulesRouteRefreshBeforeRecordExpiry() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            var currentTimeMillis = 1_000L
            val channel = ScriptedRuntimeProtocolChannel()
            val trustedStore = FakeEmittingTrustedRuntimeStore(
                TrustedRuntime(
                    deviceId = "runtime-1",
                    name = "AetherLink Runtime",
                    fingerprint = "runtime-fingerprint",
                    publicKeyBase64 = "runtime-public-key",
                    routeToken = "route-token-1",
                    p2pRouteClass = "p2p_rendezvous",
                    p2pRecordId = "old-p2p-record",
                    p2pEncryptedBody = "old-p2p-body",
                    p2pExpiresAtEpochMillis = currentTimeMillis + 600_000L,
                    p2pAntiReplayNonce = "old-p2p-nonce",
                    p2pProtocolVersion = 1,
                ),
            )
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Direct TCP should not be used for scheduled P2P route-refresh")
                    },
                    peerToPeerConnector = RuntimePeerToPeerConnector { route, timeoutMillis ->
                        assertEquals("old-p2p-record", route.sessionId)
                        assertEquals(5_000, timeoutMillis)
                        channel
                    },
                    relayConnector = RuntimeRelayConnector { _, _ ->
                        error("Relay should not be used for scheduled P2P route-refresh")
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = FakeRuntimeLocalDataStore(
                        initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = false),
                    ),
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    authenticatedRouteRefreshEnabled = true,
                    currentTimeMillis = { currentTimeMillis },
                ),
            )
            advanceUntilIdle()

            viewModel.connectToTrustedRuntime()
            advanceUntilIdle()
            channel.enqueue(
                envelope(
                    type = MessageType.AuthResponse,
                    serializer = AuthResponsePayload.serializer(),
                    payload = AuthResponsePayload(accepted = true),
                    requestId = "auth-accepted",
                ),
            )
            runCurrent()

            assertEquals(RuntimeActiveRouteKind.PeerToPeer, viewModel.state.value.activeRouteKind)
            assertEquals(0, channel.sentEnvelopes.count { it.type == MessageType.RouteRefresh })

            advanceTimeBy(539_999L)
            currentTimeMillis += 539_999L
            runCurrent()
            assertEquals(0, channel.sentEnvelopes.count { it.type == MessageType.RouteRefresh })

            advanceTimeBy(1L)
            currentTimeMillis += 1L
            runCurrent()

            val routeRefreshRequest = channel.sentEnvelopes.single { it.type == MessageType.RouteRefresh }
            channel.enqueue(
                envelope(
                    type = MessageType.RouteRefresh,
                    serializer = RouteRefreshPayload.serializer(),
                    payload = RouteRefreshPayload(
                        runtimeDeviceId = "runtime-1",
                        runtimeKeyFingerprint = "runtime-fingerprint",
                        p2pRouteClass = "p2p_rendezvous",
                        p2pRecordId = "fresh-p2p-record",
                        p2pEncryptedBody = "fresh-p2p-body",
                        p2pExpiresAtEpochMillis = currentTimeMillis + 180_000L,
                        p2pAntiReplayNonce = "fresh-p2p-nonce",
                        p2pProtocolVersion = 1,
                    ),
                    requestId = routeRefreshRequest.requestId,
                ),
            )
            runCurrent()

            assertEquals("fresh-p2p-record", trustedStore.trusted?.p2pRecordId)
            assertEquals("fresh-p2p-body", viewModel.state.value.trustedRuntime?.p2pEncryptedBody)

            advanceTimeBy(119_999L)
            currentTimeMillis += 119_999L
            runCurrent()
            assertEquals(1, channel.sentEnvelopes.count { it.type == MessageType.RouteRefresh })

            advanceTimeBy(1L)
            currentTimeMillis += 1L
            runCurrent()

            val routeRefreshRequests = channel.sentEnvelopes.filter { it.type == MessageType.RouteRefresh }
            assertEquals(2, routeRefreshRequests.size)
            assertTrue(routeRefreshRequests[1].requestId != routeRefreshRequests[0].requestId)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun authenticatedTrustedRuntimeRetriesRouteRefreshErrorBeforeLeaseExpiry() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            var currentTimeMillis = 1_000L
            val channel = ScriptedRuntimeProtocolChannel()
            val trustedStore = FakeEmittingTrustedRuntimeStore(
                TrustedRuntime(
                    deviceId = "runtime-1",
                    name = "AetherLink Runtime",
                    fingerprint = "runtime-fingerprint",
                    publicKeyBase64 = "runtime-public-key",
                    routeToken = "route-token-1",
                    relayHost = "relay.example.test",
                    relayPort = 443,
                    relayId = "relay-1",
                    relaySecret = "secret-1",
                    relayExpiresAtEpochMillis = currentTimeMillis + 180_000L,
                    relayNonce = "nonce-route-1",
                    relayScope = "remote",
                ),
            )
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Direct TCP should not be used for route-refresh retry")
                    },
                    relayConnector = RuntimeRelayConnector { _, _ -> channel },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = FakeRuntimeLocalDataStore(
                        initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = false),
                    ),
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    authenticatedRouteRefreshEnabled = true,
                    currentTimeMillis = { currentTimeMillis },
                ),
            )
            advanceUntilIdle()

            viewModel.connectToTrustedRuntime()
            advanceUntilIdle()
            channel.enqueue(
                envelope(
                    type = MessageType.AuthResponse,
                    serializer = AuthResponsePayload.serializer(),
                    payload = AuthResponsePayload(accepted = true),
                    requestId = "auth-accepted",
                ),
            )
            advanceUntilIdle()

            val firstRouteRefresh = channel.sentEnvelopes.single { it.type == MessageType.RouteRefresh }
            channel.enqueue(
                envelope(
                    type = MessageType.Error,
                    serializer = ErrorPayload.serializer(),
                    payload = ErrorPayload(
                        code = "route_refresh_unavailable",
                        message = "Route refresh is temporarily unavailable.",
                        retryable = true,
                    ),
                    requestId = firstRouteRefresh.requestId,
                ),
            )
            runCurrent()

            advanceTimeBy(ROUTE_REFRESH_RETRY_DELAY_MS - 1)
            currentTimeMillis += ROUTE_REFRESH_RETRY_DELAY_MS - 1
            runCurrent()
            assertEquals(1, channel.sentEnvelopes.count { it.type == MessageType.RouteRefresh })

            advanceTimeBy(1)
            currentTimeMillis += 1
            runCurrent()

            val routeRefreshRequests = channel.sentEnvelopes.filter { it.type == MessageType.RouteRefresh }
            assertEquals(2, routeRefreshRequests.size)
            assertTrue(routeRefreshRequests[1].requestId != routeRefreshRequests[0].requestId)
            assertNull(viewModel.state.value.error)
            assertEquals("relay.example.test", trustedStore.trusted?.relayHost)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun authenticatedTrustedP2pRuntimeRetriesRouteRefreshErrorBeforeRecordExpiry() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            var currentTimeMillis = 1_000L
            val channel = ScriptedRuntimeProtocolChannel()
            val trustedStore = FakeEmittingTrustedRuntimeStore(
                TrustedRuntime(
                    deviceId = "runtime-1",
                    name = "AetherLink Runtime",
                    fingerprint = "runtime-fingerprint",
                    publicKeyBase64 = "runtime-public-key",
                    routeToken = "route-token-1",
                    p2pRouteClass = "p2p_rendezvous",
                    p2pRecordId = "p2p-record-1",
                    p2pEncryptedBody = "p2p-body-1",
                    p2pExpiresAtEpochMillis = currentTimeMillis + 180_000L,
                    p2pAntiReplayNonce = "p2p-nonce-1",
                    p2pProtocolVersion = 1,
                ),
            )
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Direct TCP should not be used for P2P route-refresh retry")
                    },
                    peerToPeerConnector = RuntimePeerToPeerConnector { _, _ -> channel },
                    relayConnector = RuntimeRelayConnector { _, _ ->
                        error("Relay should not be used for P2P route-refresh retry")
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = FakeRuntimeLocalDataStore(
                        initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = false),
                    ),
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    authenticatedRouteRefreshEnabled = true,
                    currentTimeMillis = { currentTimeMillis },
                ),
            )
            advanceUntilIdle()

            viewModel.connectToTrustedRuntime()
            advanceUntilIdle()
            channel.enqueue(
                envelope(
                    type = MessageType.AuthResponse,
                    serializer = AuthResponsePayload.serializer(),
                    payload = AuthResponsePayload(accepted = true),
                    requestId = "auth-accepted",
                ),
            )
            advanceUntilIdle()

            val firstRouteRefresh = channel.sentEnvelopes.single { it.type == MessageType.RouteRefresh }
            channel.enqueue(
                envelope(
                    type = MessageType.Error,
                    serializer = ErrorPayload.serializer(),
                    payload = ErrorPayload(
                        code = "route_refresh_unavailable",
                        message = "Route refresh is temporarily unavailable.",
                        retryable = true,
                    ),
                    requestId = firstRouteRefresh.requestId,
                ),
            )
            runCurrent()

            advanceTimeBy(ROUTE_REFRESH_RETRY_DELAY_MS - 1)
            currentTimeMillis += ROUTE_REFRESH_RETRY_DELAY_MS - 1
            runCurrent()
            assertEquals(1, channel.sentEnvelopes.count { it.type == MessageType.RouteRefresh })

            advanceTimeBy(1)
            currentTimeMillis += 1
            runCurrent()

            val routeRefreshRequests = channel.sentEnvelopes.filter { it.type == MessageType.RouteRefresh }
            assertEquals(2, routeRefreshRequests.size)
            assertTrue(routeRefreshRequests[1].requestId != routeRefreshRequests[0].requestId)
            assertNull(viewModel.state.value.error)
            assertEquals("p2p-record-1", trustedStore.trusted?.p2pRecordId)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun authenticatedTrustedP2pRuntimeRetriesRouteRefreshWhenRuntimeReturnsReusedP2pRecord() = runTest {
        verifyAuthenticatedTrustedP2pRuntimeRetriesStaleRouteRefreshBeforeRecordExpiry(
            stalePayload = { currentRecordExpiry ->
                RouteRefreshPayload(
                    runtimeDeviceId = "runtime-1",
                    runtimeKeyFingerprint = "runtime-fingerprint",
                    p2pRouteClass = "p2p_rendezvous",
                    p2pRecordId = "p2p-record-1",
                    p2pEncryptedBody = "stale-p2p-body",
                    p2pExpiresAtEpochMillis = currentRecordExpiry + 60_000L,
                    p2pAntiReplayNonce = "p2p-nonce-2",
                    p2pProtocolVersion = 1,
                )
            },
        )
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun authenticatedTrustedP2pRuntimeRetriesRouteRefreshWhenRuntimeReturnsNonAdvancingP2pExpiry() = runTest {
        verifyAuthenticatedTrustedP2pRuntimeRetriesStaleRouteRefreshBeforeRecordExpiry(
            stalePayload = { currentRecordExpiry ->
                RouteRefreshPayload(
                    runtimeDeviceId = "runtime-1",
                    runtimeKeyFingerprint = "runtime-fingerprint",
                    p2pRouteClass = "p2p_rendezvous",
                    p2pRecordId = "p2p-record-2",
                    p2pEncryptedBody = "stale-p2p-body",
                    p2pExpiresAtEpochMillis = currentRecordExpiry,
                    p2pAntiReplayNonce = "p2p-nonce-2",
                    p2pProtocolVersion = 1,
                )
            },
        )
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    private suspend fun TestScope.verifyAuthenticatedTrustedP2pRuntimeRetriesStaleRouteRefreshBeforeRecordExpiry(
        stalePayload: (currentRecordExpiry: Long) -> RouteRefreshPayload,
    ) {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        var runtimeViewModel: RuntimeClientViewModel? = null
        try {
            var currentTimeMillis = 1_000L
            val currentRecordExpiry = currentTimeMillis + 180_000L
            val channel = ScriptedRuntimeProtocolChannel()
            val trustedStore = FakeEmittingTrustedRuntimeStore(
                TrustedRuntime(
                    deviceId = "runtime-1",
                    name = "AetherLink Runtime",
                    fingerprint = "runtime-fingerprint",
                    publicKeyBase64 = "runtime-public-key",
                    routeToken = "route-token-1",
                    p2pRouteClass = "p2p_rendezvous",
                    p2pRecordId = "p2p-record-1",
                    p2pEncryptedBody = "p2p-body-1",
                    p2pExpiresAtEpochMillis = currentRecordExpiry,
                    p2pAntiReplayNonce = "p2p-nonce-1",
                    p2pProtocolVersion = 1,
                ),
            )
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Direct TCP should not be used for stale P2P route-refresh retry")
                    },
                    peerToPeerConnector = RuntimePeerToPeerConnector { _, _ -> channel },
                    relayConnector = RuntimeRelayConnector { _, _ ->
                        error("Relay should not be used for stale P2P route-refresh retry")
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = FakeRuntimeLocalDataStore(
                        initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = false),
                    ),
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    authenticatedRouteRefreshEnabled = true,
                    currentTimeMillis = { currentTimeMillis },
                ),
            )
            runtimeViewModel = viewModel
            advanceUntilIdle()

            viewModel.connectToTrustedRuntime()
            advanceUntilIdle()
            channel.enqueue(
                envelope(
                    type = MessageType.AuthResponse,
                    serializer = AuthResponsePayload.serializer(),
                    payload = AuthResponsePayload(accepted = true),
                    requestId = "auth-accepted",
                ),
            )
            advanceUntilIdle()

            val firstRouteRefresh = channel.sentEnvelopes.single { it.type == MessageType.RouteRefresh }
            channel.enqueue(
                envelope(
                    type = MessageType.RouteRefresh,
                    serializer = RouteRefreshPayload.serializer(),
                    payload = stalePayload(currentRecordExpiry),
                    requestId = firstRouteRefresh.requestId,
                ),
            )
            runCurrent()

            assertEquals("p2p-record-1", trustedStore.trusted?.p2pRecordId)
            assertEquals("p2p-body-1", trustedStore.trusted?.p2pEncryptedBody)
            assertEquals(currentRecordExpiry, trustedStore.trusted?.p2pExpiresAtEpochMillis)
            assertEquals("p2p-nonce-1", trustedStore.trusted?.p2pAntiReplayNonce)
            assertNull(viewModel.state.value.error)
            assertTrue(viewModel.state.value.isConnected)
            assertEquals(RuntimeActiveRouteKind.PeerToPeer, viewModel.state.value.activeRouteKind)
            assertNotNull(viewModel.privateField<Any>("routeRefreshLeaseJob"))
            assertEquals(1, channel.sentEnvelopes.count { it.type == MessageType.RouteRefresh })

            advanceTimeBy(ROUTE_REFRESH_RETRY_DELAY_MS)
            currentTimeMillis += ROUTE_REFRESH_RETRY_DELAY_MS
            runCurrent()

            val routeRefreshRequests = channel.sentEnvelopes.filter { it.type == MessageType.RouteRefresh }
            assertEquals(2, routeRefreshRequests.size)
            assertTrue(routeRefreshRequests[1].requestId != routeRefreshRequests[0].requestId)

            val freshRecordExpiry = currentTimeMillis + 240_000L
            channel.enqueue(
                envelope(
                    type = MessageType.RouteRefresh,
                    serializer = RouteRefreshPayload.serializer(),
                    payload = RouteRefreshPayload(
                        runtimeDeviceId = "runtime-1",
                        runtimeKeyFingerprint = "runtime-fingerprint",
                        p2pRouteClass = "p2p_rendezvous",
                        p2pRecordId = "fresh-p2p-record",
                        p2pEncryptedBody = "fresh-p2p-body",
                        p2pExpiresAtEpochMillis = freshRecordExpiry,
                        p2pAntiReplayNonce = "fresh-p2p-nonce",
                        p2pProtocolVersion = 1,
                    ),
                    requestId = routeRefreshRequests[1].requestId,
                ),
            )
            runCurrent()

            assertEquals("fresh-p2p-record", trustedStore.trusted?.p2pRecordId)
            assertEquals("fresh-p2p-body", trustedStore.trusted?.p2pEncryptedBody)
            assertEquals(freshRecordExpiry, trustedStore.trusted?.p2pExpiresAtEpochMillis)
            assertEquals("fresh-p2p-nonce", trustedStore.trusted?.p2pAntiReplayNonce)
            assertNull(viewModel.state.value.error)
            assertTrue(viewModel.state.value.isConnected)
        } finally {
            runtimeViewModel?.clearForTest()
            runCurrent()
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun routeRefreshAuthenticationRequiredDoesNotRetainRouteMaterialTechnicalDetail() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        var runtimeViewModel: RuntimeClientViewModel? = null
        try {
            var currentTimeMillis = 1_000L
            val channel = ScriptedRuntimeProtocolChannel()
            val trustedStore = FakeEmittingTrustedRuntimeStore(
                TrustedRuntime(
                    deviceId = "runtime-1",
                    name = "AetherLink Runtime",
                    fingerprint = "runtime-fingerprint",
                    publicKeyBase64 = "runtime-public-key",
                    routeToken = "route-token-1",
                    relayHost = "relay.example.test",
                    relayPort = 443,
                    relayId = "relay-1",
                    relaySecret = "secret-1",
                    relayExpiresAtEpochMillis = currentTimeMillis + 180_000L,
                    relayNonce = "nonce-route-1",
                    relayScope = "remote",
                ),
            )
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Direct TCP should not be used for route-refresh auth failure")
                    },
                    relayConnector = RuntimeRelayConnector { _, _ -> channel },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = FakeRuntimeLocalDataStore(
                        initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = false),
                    ),
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    authenticatedRouteRefreshEnabled = true,
                    currentTimeMillis = { currentTimeMillis },
                ),
            )
            runtimeViewModel = viewModel
            advanceUntilIdle()

            viewModel.connectToTrustedRuntime()
            advanceUntilIdle()
            channel.enqueue(
                envelope(
                    type = MessageType.AuthResponse,
                    serializer = AuthResponsePayload.serializer(),
                    payload = AuthResponsePayload(accepted = true),
                    requestId = "auth-accepted",
                ),
            )
            advanceUntilIdle()

            val firstRouteRefresh = channel.sentEnvelopes.single { it.type == MessageType.RouteRefresh }
            channel.enqueue(
                envelope(
                    type = MessageType.Error,
                    serializer = ErrorPayload.serializer(),
                    payload = ErrorPayload(
                        code = "authentication_required",
                        message = "Pair again relaySecret=secret-1 routeToken=route-token-1 relayId=relay-1 nonce=nonce-route-1",
                        retryable = false,
                    ),
                    requestId = firstRouteRefresh.requestId,
                ),
            )
            runCurrent()

            val error = viewModel.state.value.error ?: error("Expected route-refresh auth error")
            assertEquals("pairing_required", viewModel.state.value.runtimeStatus)
            assertEquals("pairing_required", error.code)
            assertNull(error.detail)
            assertEquals("Route refresh requires pairing again.", error.technicalDetail)
            assertFalse(error.technicalDetail.orEmpty().contains("secret-1"))
            assertFalse(error.technicalDetail.orEmpty().contains("route-token-1"))
            assertFalse(error.technicalDetail.orEmpty().contains("relay-1"))
            assertFalse(viewModel.state.value.isConnected)
            assertFalse(viewModel.state.value.isConnecting)
            assertNull(viewModel.privateField<Any>("routeRefreshLeaseJob"))
            assertNull(viewModel.privateField<String>("pendingRouteRefreshRequestId"))

            advanceTimeBy(ROUTE_REFRESH_RETRY_DELAY_MS + 1)
            currentTimeMillis += ROUTE_REFRESH_RETRY_DELAY_MS + 1
            runCurrent()

            assertEquals(1, channel.sentEnvelopes.count { it.type == MessageType.RouteRefresh })
        } finally {
            runtimeViewModel?.clearForTest()
            runCurrent()
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun authenticatedTrustedRuntimeMarksRouteExpiredWhenRefreshErrorCannotRetryBeforeLeaseExpiry() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        var runtimeViewModel: RuntimeClientViewModel? = null
        try {
            var currentTimeMillis = 1_000L
            val channel = ScriptedRuntimeProtocolChannel()
            val trustedStore = FakeEmittingTrustedRuntimeStore(
                TrustedRuntime(
                    deviceId = "runtime-1",
                    name = "AetherLink Runtime",
                    fingerprint = "runtime-fingerprint",
                    publicKeyBase64 = "runtime-public-key",
                    routeToken = "route-token-1",
                    relayHost = "relay.example.test",
                    relayPort = 443,
                    relayId = "relay-1",
                    relaySecret = "secret-1",
                    relayExpiresAtEpochMillis = currentTimeMillis + ROUTE_REFRESH_LEASE_MIN_DELAY_MS,
                    relayNonce = "nonce-route-1",
                    relayScope = "remote",
                ),
            )
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Direct TCP should not be used for terminal route-refresh failure")
                    },
                    relayConnector = RuntimeRelayConnector { _, _ -> channel },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = FakeRuntimeLocalDataStore(
                        initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = false),
                    ),
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    authenticatedRouteRefreshEnabled = true,
                    currentTimeMillis = { currentTimeMillis },
                ),
            )
            runtimeViewModel = viewModel
            advanceUntilIdle()

            viewModel.connectToTrustedRuntime()
            advanceUntilIdle()
            channel.enqueue(
                envelope(
                    type = MessageType.AuthResponse,
                    serializer = AuthResponsePayload.serializer(),
                    payload = AuthResponsePayload(accepted = true),
                    requestId = "auth-accepted",
                ),
            )
            advanceUntilIdle()

            val firstRouteRefresh = channel.sentEnvelopes.single { it.type == MessageType.RouteRefresh }
            channel.enqueue(
                envelope(
                    type = MessageType.Error,
                    serializer = ErrorPayload.serializer(),
                    payload = ErrorPayload(
                        code = "route_refresh_unavailable",
                        message = "Route refresh is temporarily unavailable.",
                        retryable = true,
                    ),
                    requestId = firstRouteRefresh.requestId,
                ),
            )
            runCurrent()

            assertEquals("remote_route_expired", viewModel.state.value.error?.code)
            assertEquals(
                "route_diagnostic_remote_route_expired",
                viewModel.state.value.error?.diagnosticCode,
            )
            assertFalse(viewModel.state.value.isConnected)
            assertFalse(viewModel.state.value.isConnecting)
            assertEquals("failed", viewModel.state.value.runtimeStatus)
            assertNull(viewModel.state.value.activeRouteKind)
            assertNull(viewModel.privateField<Any>("routeRefreshLeaseJob"))

            advanceTimeBy(ROUTE_REFRESH_RETRY_DELAY_MS + 1)
            currentTimeMillis += ROUTE_REFRESH_RETRY_DELAY_MS + 1
            runCurrent()

            assertEquals(1, channel.sentEnvelopes.count { it.type == MessageType.RouteRefresh })
            assertEquals("relay.example.test", trustedStore.trusted?.relayHost)
        } finally {
            runtimeViewModel?.clearForTest()
            runCurrent()
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun authenticatedTrustedP2pRuntimeMarksRouteExpiredWhenRefreshCannotRetryBeforeRecordExpiry() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        var runtimeViewModel: RuntimeClientViewModel? = null
        try {
            var currentTimeMillis = 1_000L
            val channel = ScriptedRuntimeProtocolChannel()
            val trustedStore = FakeEmittingTrustedRuntimeStore(
                TrustedRuntime(
                    deviceId = "runtime-1",
                    name = "AetherLink Runtime",
                    fingerprint = "runtime-fingerprint",
                    publicKeyBase64 = "runtime-public-key",
                    routeToken = "route-token-1",
                    p2pRouteClass = "p2p_rendezvous",
                    p2pRecordId = "p2p-record-1",
                    p2pEncryptedBody = "p2p-body-1",
                    p2pExpiresAtEpochMillis = currentTimeMillis + ROUTE_REFRESH_LEASE_MIN_DELAY_MS,
                    p2pAntiReplayNonce = "p2p-nonce-1",
                    p2pProtocolVersion = 1,
                ),
            )
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Direct TCP should not be used for terminal P2P route-refresh failure")
                    },
                    peerToPeerConnector = RuntimePeerToPeerConnector { _, _ -> channel },
                    relayConnector = RuntimeRelayConnector { _, _ ->
                        error("Relay should not be used for terminal P2P route-refresh failure")
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = FakeRuntimeLocalDataStore(
                        initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = false),
                    ),
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    authenticatedRouteRefreshEnabled = true,
                    currentTimeMillis = { currentTimeMillis },
                ),
            )
            runtimeViewModel = viewModel
            advanceUntilIdle()

            viewModel.connectToTrustedRuntime()
            advanceUntilIdle()
            channel.enqueue(
                envelope(
                    type = MessageType.AuthResponse,
                    serializer = AuthResponsePayload.serializer(),
                    payload = AuthResponsePayload(accepted = true),
                    requestId = "auth-accepted",
                ),
            )
            advanceUntilIdle()

            val firstRouteRefresh = channel.sentEnvelopes.single { it.type == MessageType.RouteRefresh }
            channel.enqueue(
                envelope(
                    type = MessageType.Error,
                    serializer = ErrorPayload.serializer(),
                    payload = ErrorPayload(
                        code = "route_refresh_unavailable",
                        message = "Route refresh is temporarily unavailable.",
                        retryable = true,
                    ),
                    requestId = firstRouteRefresh.requestId,
                ),
            )
            runCurrent()

            assertEquals("remote_route_expired", viewModel.state.value.error?.code)
            assertEquals(
                "route_diagnostic_remote_route_expired",
                viewModel.state.value.error?.diagnosticCode,
            )
            assertFalse(viewModel.state.value.isConnected)
            assertFalse(viewModel.state.value.isConnecting)
            assertEquals("failed", viewModel.state.value.runtimeStatus)
            assertNull(viewModel.state.value.activeRouteKind)
            assertNull(viewModel.privateField<Any>("routeRefreshLeaseJob"))

            advanceTimeBy(ROUTE_REFRESH_RETRY_DELAY_MS + 1)
            currentTimeMillis += ROUTE_REFRESH_RETRY_DELAY_MS + 1
            runCurrent()

            assertEquals(1, channel.sentEnvelopes.count { it.type == MessageType.RouteRefresh })
            assertEquals("p2p-record-1", trustedStore.trusted?.p2pRecordId)
        } finally {
            runtimeViewModel?.clearForTest()
            runCurrent()
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun authenticatedTrustedRuntimeRetriesRejectedRouteRefreshPayloadBeforeLeaseExpiry() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        var runtimeViewModel: RuntimeClientViewModel? = null
        try {
            var currentTimeMillis = 1_000L
            val channel = ScriptedRuntimeProtocolChannel()
            val trustedStore = FakeEmittingTrustedRuntimeStore(
                TrustedRuntime(
                    deviceId = "runtime-1",
                    name = "AetherLink Runtime",
                    fingerprint = "runtime-fingerprint",
                    publicKeyBase64 = "runtime-public-key",
                    routeToken = "route-token-1",
                    relayHost = "relay.example.test",
                    relayPort = 443,
                    relayId = "relay-1",
                    relaySecret = "secret-1",
                    relayExpiresAtEpochMillis = currentTimeMillis + 180_000L,
                    relayNonce = "nonce-route-1",
                    relayScope = "remote",
                ),
            )
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Direct TCP should not be used for route-refresh retry")
                    },
                    relayConnector = RuntimeRelayConnector { _, _ -> channel },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = FakeRuntimeLocalDataStore(
                        initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = false),
                    ),
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    authenticatedRouteRefreshEnabled = true,
                    currentTimeMillis = { currentTimeMillis },
                ),
            )
            runtimeViewModel = viewModel
            advanceUntilIdle()

            viewModel.connectToTrustedRuntime()
            advanceUntilIdle()
            channel.enqueue(
                envelope(
                    type = MessageType.AuthResponse,
                    serializer = AuthResponsePayload.serializer(),
                    payload = AuthResponsePayload(accepted = true),
                    requestId = "auth-accepted",
                ),
            )
            advanceUntilIdle()

            val firstRouteRefresh = channel.sentEnvelopes.single { it.type == MessageType.RouteRefresh }
            channel.enqueue(
                envelope(
                    type = MessageType.RouteRefresh,
                    serializer = RouteRefreshPayload.serializer(),
                    payload = RouteRefreshPayload(
                        runtimeDeviceId = "other-runtime",
                        runtimeKeyFingerprint = "runtime-fingerprint",
                        relayHost = "fresh-relay.example.test",
                        relayPort = 43171,
                        relayId = "fresh-relay",
                        relaySecret = "fresh-secret",
                        relayExpiresAtEpochMillis = currentTimeMillis + 180_000L,
                        relayNonce = "fresh-nonce",
                        relayScope = "remote",
                    ),
                    requestId = firstRouteRefresh.requestId,
                ),
            )
            runCurrent()

            assertEquals("relay.example.test", trustedStore.trusted?.relayHost)
            assertNull(viewModel.state.value.error)
            assertEquals(1, channel.sentEnvelopes.count { it.type == MessageType.RouteRefresh })

            advanceTimeBy(ROUTE_REFRESH_RETRY_DELAY_MS)
            currentTimeMillis += ROUTE_REFRESH_RETRY_DELAY_MS
            runCurrent()

            val routeRefreshRequests = channel.sentEnvelopes.filter { it.type == MessageType.RouteRefresh }
            assertEquals(2, routeRefreshRequests.size)
            assertTrue(routeRefreshRequests[1].requestId != routeRefreshRequests[0].requestId)
        } finally {
            runtimeViewModel?.clearForTest()
            runCurrent()
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun authenticatedTrustedRelayRuntimeRetriesRouteRefreshWhenRuntimeReturnsReusedRelayNonce() = runTest {
        verifyAuthenticatedTrustedRelayRuntimeRetriesStaleRouteRefreshBeforeLeaseExpiry(
            stalePayload = { currentRelayExpiry ->
                RouteRefreshPayload(
                    runtimeDeviceId = "runtime-1",
                    runtimeKeyFingerprint = "runtime-fingerprint",
                    relayHost = "stale-relay.example.test",
                    relayPort = 43171,
                    relayId = "stable-relay",
                    relaySecret = "stable-secret",
                    relayExpiresAtEpochMillis = currentRelayExpiry + 60_000L,
                    relayNonce = "nonce-route-1",
                    relayScope = "remote",
                )
            },
        )
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun authenticatedTrustedRelayRuntimeRetriesRouteRefreshWhenRuntimeReturnsNonAdvancingRelayExpiry() = runTest {
        verifyAuthenticatedTrustedRelayRuntimeRetriesStaleRouteRefreshBeforeLeaseExpiry(
            stalePayload = { currentRelayExpiry ->
                RouteRefreshPayload(
                    runtimeDeviceId = "runtime-1",
                    runtimeKeyFingerprint = "runtime-fingerprint",
                    relayHost = "stale-relay.example.test",
                    relayPort = 43171,
                    relayId = "stable-relay",
                    relaySecret = "stable-secret",
                    relayExpiresAtEpochMillis = currentRelayExpiry,
                    relayNonce = "nonce-route-2",
                    relayScope = "remote",
                )
            },
        )
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    private suspend fun TestScope.verifyAuthenticatedTrustedRelayRuntimeRetriesStaleRouteRefreshBeforeLeaseExpiry(
        stalePayload: (currentRelayExpiry: Long) -> RouteRefreshPayload,
    ) {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        var runtimeViewModel: RuntimeClientViewModel? = null
        try {
            var currentTimeMillis = 1_000L
            val currentRelayExpiry = currentTimeMillis + 180_000L
            val channel = ScriptedRuntimeProtocolChannel()
            val trustedStore = FakeEmittingTrustedRuntimeStore(
                TrustedRuntime(
                    deviceId = "runtime-1",
                    name = "AetherLink Runtime",
                    fingerprint = "runtime-fingerprint",
                    publicKeyBase64 = "runtime-public-key",
                    routeToken = "route-token-1",
                    relayHost = "relay.example.test",
                    relayPort = 443,
                    relayId = "stable-relay",
                    relaySecret = "stable-secret",
                    relayExpiresAtEpochMillis = currentRelayExpiry,
                    relayNonce = "nonce-route-1",
                    relayScope = "remote",
                ),
            )
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Direct TCP should not be used for stale route-refresh retry")
                    },
                    relayConnector = RuntimeRelayConnector { _, _ -> channel },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = FakeRuntimeLocalDataStore(
                        initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = false),
                    ),
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    authenticatedRouteRefreshEnabled = true,
                    currentTimeMillis = { currentTimeMillis },
                ),
            )
            runtimeViewModel = viewModel
            advanceUntilIdle()

            viewModel.connectToTrustedRuntime()
            advanceUntilIdle()
            channel.enqueue(
                envelope(
                    type = MessageType.AuthResponse,
                    serializer = AuthResponsePayload.serializer(),
                    payload = AuthResponsePayload(accepted = true),
                    requestId = "auth-accepted",
                ),
            )
            advanceUntilIdle()

            val firstRouteRefresh = channel.sentEnvelopes.single { it.type == MessageType.RouteRefresh }
            channel.enqueue(
                envelope(
                    type = MessageType.RouteRefresh,
                    serializer = RouteRefreshPayload.serializer(),
                    payload = stalePayload(currentRelayExpiry),
                    requestId = firstRouteRefresh.requestId,
                ),
            )
            runCurrent()

            assertEquals("relay.example.test", trustedStore.trusted?.relayHost)
            assertEquals(443, trustedStore.trusted?.relayPort)
            assertEquals("stable-relay", trustedStore.trusted?.relayId)
            assertEquals("stable-secret", trustedStore.trusted?.relaySecret)
            assertEquals(currentRelayExpiry, trustedStore.trusted?.relayExpiresAtEpochMillis)
            assertEquals("nonce-route-1", trustedStore.trusted?.relayNonce)
            assertNull(viewModel.state.value.error)
            assertTrue(viewModel.state.value.isConnected)
            assertNotNull(viewModel.privateField<Any>("routeRefreshLeaseJob"))
            assertEquals(1, channel.sentEnvelopes.count { it.type == MessageType.RouteRefresh })

            advanceTimeBy(ROUTE_REFRESH_RETRY_DELAY_MS)
            currentTimeMillis += ROUTE_REFRESH_RETRY_DELAY_MS
            runCurrent()

            val routeRefreshRequests = channel.sentEnvelopes.filter { it.type == MessageType.RouteRefresh }
            assertEquals(2, routeRefreshRequests.size)
            assertTrue(routeRefreshRequests[1].requestId != routeRefreshRequests[0].requestId)

            val freshRelayExpiry = currentTimeMillis + 240_000L
            channel.enqueue(
                envelope(
                    type = MessageType.RouteRefresh,
                    serializer = RouteRefreshPayload.serializer(),
                    payload = RouteRefreshPayload(
                        runtimeDeviceId = "runtime-1",
                        runtimeKeyFingerprint = "runtime-fingerprint",
                        relayHost = "fresh-relay.example.test",
                        relayPort = 43172,
                        relayId = "stable-relay",
                        relaySecret = "stable-secret",
                        relayExpiresAtEpochMillis = freshRelayExpiry,
                        relayNonce = "nonce-route-3",
                        relayScope = "remote",
                    ),
                    requestId = routeRefreshRequests[1].requestId,
                ),
            )
            runCurrent()

            assertEquals("fresh-relay.example.test", trustedStore.trusted?.relayHost)
            assertEquals(43172, trustedStore.trusted?.relayPort)
            assertEquals("stable-relay", trustedStore.trusted?.relayId)
            assertEquals("stable-secret", trustedStore.trusted?.relaySecret)
            assertEquals(freshRelayExpiry, trustedStore.trusted?.relayExpiresAtEpochMillis)
            assertEquals("nonce-route-3", trustedStore.trusted?.relayNonce)
            assertNull(viewModel.state.value.error)
            assertTrue(viewModel.state.value.isConnected)
        } finally {
            runtimeViewModel?.clearForTest()
            runCurrent()
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun disconnectCancelsScheduledRouteRefreshRetry() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        var runtimeViewModel: RuntimeClientViewModel? = null
        try {
            var currentTimeMillis = 1_000L
            val channel = ScriptedRuntimeProtocolChannel()
            val trustedStore = FakeEmittingTrustedRuntimeStore(
                TrustedRuntime(
                    deviceId = "runtime-1",
                    name = "AetherLink Runtime",
                    fingerprint = "runtime-fingerprint",
                    publicKeyBase64 = "runtime-public-key",
                    routeToken = "route-token-1",
                    relayHost = "relay.example.test",
                    relayPort = 443,
                    relayId = "relay-1",
                    relaySecret = "secret-1",
                    relayExpiresAtEpochMillis = currentTimeMillis + 180_000L,
                    relayNonce = "nonce-route-1",
                    relayScope = "remote",
                ),
            )
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Direct TCP should not be used for route-refresh retry cleanup")
                    },
                    relayConnector = RuntimeRelayConnector { _, _ -> channel },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = FakeRuntimeLocalDataStore(
                        initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = false),
                    ),
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    authenticatedRouteRefreshEnabled = true,
                    currentTimeMillis = { currentTimeMillis },
                ),
            )
            runtimeViewModel = viewModel
            advanceUntilIdle()

            viewModel.connectToTrustedRuntime()
            advanceUntilIdle()
            channel.enqueue(
                envelope(
                    type = MessageType.AuthResponse,
                    serializer = AuthResponsePayload.serializer(),
                    payload = AuthResponsePayload(accepted = true),
                    requestId = "auth-accepted",
                ),
            )
            runCurrent()

            val firstRouteRefreshDelay = runtimeRouteRefreshLeaseDelayMillis(
                nowEpochMillis = currentTimeMillis,
                remoteRouteExpiresAtEpochMillis = trustedStore.trusted?.relayExpiresAtEpochMillis,
            ) ?: error("Expected trusted relay lease to schedule route refresh")
            advanceTimeBy(firstRouteRefreshDelay)
            currentTimeMillis += firstRouteRefreshDelay
            runCurrent()

            val firstRouteRefresh = channel.sentEnvelopes.single { it.type == MessageType.RouteRefresh }
            channel.enqueue(
                envelope(
                    type = MessageType.Error,
                    serializer = ErrorPayload.serializer(),
                    payload = ErrorPayload(
                        code = "route_refresh_unavailable",
                        message = "Route refresh is temporarily unavailable.",
                        retryable = true,
                    ),
                    requestId = firstRouteRefresh.requestId,
                ),
            )
            runCurrent()
            assertNotNull(viewModel.privateField<Any>("routeRefreshLeaseJob"))

            viewModel.disconnect()
            runCurrent()
            assertNull(viewModel.privateField<Any>("routeRefreshLeaseJob"))
            assertNull(viewModel.privateField<String>("pendingRouteRefreshRequestId"))

            advanceTimeBy(ROUTE_REFRESH_RETRY_DELAY_MS + 1)
            currentTimeMillis += ROUTE_REFRESH_RETRY_DELAY_MS + 1
            runCurrent()

            assertEquals(1, channel.sentEnvelopes.count { it.type == MessageType.RouteRefresh })
            assertFalse(viewModel.state.value.isConnected)
        } finally {
            runtimeViewModel?.clearForTest()
            runCurrent()
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun forgetTrustedRuntimeClosesConnectionAndClearsPendingRouteRefresh() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        var runtimeViewModel: RuntimeClientViewModel? = null
        try {
            var currentTimeMillis = 1_000L
            val channel = ScriptedRuntimeProtocolChannel()
            val trustedStore = FakeEmittingTrustedRuntimeStore(
                TrustedRuntime(
                    deviceId = "runtime-1",
                    name = "AetherLink Runtime",
                    fingerprint = "runtime-fingerprint",
                    publicKeyBase64 = "runtime-public-key",
                    routeToken = "route-token-1",
                    relayHost = "relay.example.test",
                    relayPort = 443,
                    relayId = "relay-1",
                    relaySecret = "secret-1",
                    relayExpiresAtEpochMillis = currentTimeMillis + 180_000L,
                    relayNonce = "nonce-route-1",
                    relayScope = "remote",
                ),
            )
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Direct TCP should not be used for route-refresh forget cleanup")
                    },
                    relayConnector = RuntimeRelayConnector { _, _ -> channel },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = FakeRuntimeLocalDataStore(
                        initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = false),
                    ),
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    authenticatedRouteRefreshEnabled = true,
                    currentTimeMillis = { currentTimeMillis },
                ),
            )
            runtimeViewModel = viewModel
            advanceUntilIdle()

            viewModel.connectToTrustedRuntime()
            advanceUntilIdle()
            channel.enqueue(
                envelope(
                    type = MessageType.AuthResponse,
                    serializer = AuthResponsePayload.serializer(),
                    payload = AuthResponsePayload(accepted = true),
                    requestId = "auth-accepted",
                ),
            )
            runCurrent()

            assertNotNull(viewModel.privateField<Any>("routeRefreshLeaseJob"))
            val firstRouteRefreshDelay = runtimeRouteRefreshLeaseDelayMillis(
                nowEpochMillis = currentTimeMillis,
                remoteRouteExpiresAtEpochMillis = trustedStore.trusted?.relayExpiresAtEpochMillis,
            ) ?: error("Expected trusted relay lease to schedule route refresh")
            advanceTimeBy(firstRouteRefreshDelay)
            currentTimeMillis += firstRouteRefreshDelay
            runCurrent()

            assertEquals(1, channel.sentEnvelopes.count { it.type == MessageType.RouteRefresh })
            assertNotNull(viewModel.privateField<String>("pendingRouteRefreshRequestId"))
            assertNull(viewModel.privateField<Any>("routeRefreshLeaseJob"))

            viewModel.forgetTrustedRuntime()
            advanceUntilIdle()

            assertNull(trustedStore.trusted)
            assertNull(viewModel.privateField<String>("pendingRouteRefreshRequestId"))
            assertNull(viewModel.privateField<Any>("routeRefreshLeaseJob"))
            assertFalse(viewModel.state.value.isConnected)
            assertFalse(channel.isConnected)

            advanceTimeBy(120_000L)
            currentTimeMillis += 120_000L
            runCurrent()

            assertEquals(1, channel.sentEnvelopes.count { it.type == MessageType.RouteRefresh })
        } finally {
            runtimeViewModel?.clearForTest()
            runCurrent()
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun disconnectClearsPendingChatSessionRenameRequests() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val channel = ScriptedRuntimeProtocolChannel()
            val trustedStore = FakeEmittingTrustedRuntimeStore(trustedRuntimeForViewModelTests())
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Direct TCP should not be used for rename cleanup")
                    },
                    relayConnector = RuntimeRelayConnector { _, _ -> channel },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = FakeRuntimeLocalDataStore(
                        initialData = PersistedRuntimeData(
                            trustedRuntimeAutoReconnectEnabled = false,
                            sessions = listOf(
                                PersistedChatSession(
                                    id = "runtime-session",
                                    title = "Original title",
                                    modelId = "ollama:llama3.1:8b",
                                    createdAtMillis = 100L,
                                    updatedAtMillis = 200L,
                                    runtimeOwned = true,
                                    runtimeMessageCount = 1,
                                    messages = emptyList(),
                                ),
                            ),
                        ),
                    ),
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    currentTimeMillis = { 1_000L },
                ),
            )
            advanceUntilIdle()

            viewModel.connectToTrustedRuntime()
            advanceUntilIdle()
            channel.enqueue(
                envelope(
                    type = MessageType.AuthResponse,
                    serializer = AuthResponsePayload.serializer(),
                    payload = AuthResponsePayload(accepted = true),
                    requestId = "auth-accepted",
                ),
            )
            runCurrent()

            viewModel.renameChatSession("runtime-session", "Renamed title")
            runCurrent()

            val renameRequest = channel.sentEnvelopes.single { it.type == MessageType.ChatSessionRename }
            val pendingBeforeDisconnect =
                viewModel.privateField<MutableSet<String>>("pendingChatSessionRenameRequestIds")
            assertTrue(pendingBeforeDisconnect?.contains(renameRequest.requestId) == true)

            viewModel.disconnect()
            runCurrent()

            val pendingAfterDisconnect =
                viewModel.privateField<MutableSet<String>>("pendingChatSessionRenameRequestIds")
            assertTrue(pendingAfterDisconnect?.isEmpty() == true)
            assertFalse(viewModel.state.value.isConnected)
            assertFalse(channel.isConnected)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @Test
    fun compactRelayQrAcceptedPairingRestoresRelayReconnectWithoutManualEndpoint() {
        val pending = RuntimePairingPayloadParser.parse(
            sharedProtocolFixture("macos-compact-relay-pairing-uri.txt")
        )
        assertEquals("runtime-1", pending.runtimeDeviceId)
        assertEquals("runtime-fingerprint", pending.fingerprint)
        assertEquals("runtime+public/key=", pending.runtimePublicKeyBase64)
        assertEquals("route-token-1", pending.routeToken)
        assertFalse(pending.hasExpiredRemoteRoute())
        assertTrue(runtimePublicKeyMatches(pending.runtimePublicKeyBase64, "runtime+public/key="))
        val trusted = trustedRuntimeFromAcceptedPairing(
            pending = pending,
            payload = PairingResultPayload(
                accepted = true,
                runtimeDeviceIdV2 = "runtime-1",
                runtimePublicKey = "runtime+public/key=",
                runtimeKeyFingerprint = "runtime-fingerprint",
                trustedDeviceId = "client-1",
                message = "trusted",
            ),
        ) ?: error("Expected trusted runtime")
        val restored = RuntimeTrustedRuntime(
            deviceId = trusted.deviceId,
            name = trusted.name,
            fingerprint = trusted.fingerprint,
            publicKeyBase64 = trusted.publicKeyBase64,
            routeToken = trusted.routeToken,
            endpointHint = null,
            relayHost = trusted.relayHost,
            relayPort = trusted.relayPort,
            relayId = trusted.relayId,
            relaySecret = trusted.relaySecret,
            relayExpiresAtEpochMillis = trusted.relayExpiresAtEpochMillis,
            relayNonce = trusted.relayNonce,
            relayScope = trusted.relayScope,
        )
        val reconnectTarget = autoReconnectTrustedRuntimeConnectionTarget(
            RuntimeUiState(trustedRuntime = restored),
        )
        val plannedRoute = RuntimeRemoteRoutePlanner(
            pendingPairingPayload = { null },
            trustedRuntime = { restored },
            nowEpochMillis = { 1_000L },
        ).prepareRemoteRoutes(requireNotNull(reconnectTarget?.identity)).single() as PreparedRemoteRuntimeRoute.Relay

        assertNull(pending.host)
        assertNull(pending.port)
        assertNull(trusted.host)
        assertNull(trusted.port)
        assertEquals("runtime+public/key=", trusted.publicKeyBase64)
        assertEquals("route-token-1", trusted.routeToken)
        assertEquals("relay.example.test", trusted.relayHost)
        assertEquals(43171, trusted.relayPort)
        assertEquals("relay-bootstrap-1", trusted.relayId)
        assertEquals("secret-bootstrap-1", trusted.relaySecret)
        assertEquals(4102444800000L, trusted.relayExpiresAtEpochMillis)
        assertEquals("allocated-nonce-1", trusted.relayNonce)
        assertEquals("remote", trusted.relayScope)
        assertNull(reconnectTarget.endpointHint)
        assertEquals("relay.example.test", plannedRoute.host)
        assertEquals(43171, plannedRoute.port)
        assertEquals("relay-bootstrap-1", plannedRoute.relayId)
        assertEquals("secret-bootstrap-1", plannedRoute.relayFrameSecret)
        assertEquals(4102444800000L, plannedRoute.security.expiresAtEpochMillis)
        assertEquals("allocated-nonce-1", plannedRoute.security.antiReplayNonce)
    }

    @Test
    fun exhaustedPendingRelayPairingReportsRemoteRouteUnreachable() {
        val pending = runtimePairingPayload(
            host = null,
            port = null,
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
        )

        val error = pendingPairingExhaustedRouteError(pending)

        assertEquals("remote_route_unreachable", error.code)
        assertEquals("route_diagnostic_relay_failed", error.diagnosticCode)
    }

    @Test
    fun exhaustedPendingIdentityOnlyPairingStillRequestsReachableQrRoute() {
        val pending = runtimePairingPayload(host = null, port = null)

        val error = pendingPairingExhaustedRouteError(pending)

        assertEquals("pairing_endpoint_unavailable", error.code)
        assertNull(error.diagnosticCode)
    }

    @Test
    fun relayProbeResponseParserRequiresKnownRouteAndWaitingRuntime() {
        assertTrue("AETHERLINK_RELAY probe known=1 runtime_waiting=1\n".isRelayProbeReady())
        assertTrue("AETHERLINK_RELAY probe allocated=true runtime_waiting=true\n".isRelayProbeReady())
        assertFalse("AETHERLINK_RELAY probe known=1 runtime_waiting=0\n".isRelayProbeReady())
        assertFalse("AETHERLINK_RELAY probe known=0 runtime_waiting=1\n".isRelayProbeReady())
        assertFalse("AETHERLINK_RELAY ready\n".isRelayProbeReady())
        assertFalse("AETHERLINK_RELAY probe ready\n".isRelayProbeReady())
        assertFalse("AETHERLINK_RELAY probe unknown\n".isRelayProbeReady())
    }

    @Test
    fun relayProbeKnownParserAllowsRuntimeReconnectRace() {
        assertTrue("AETHERLINK_RELAY probe known=1 runtime_waiting=1\n".isRelayProbeKnown())
        assertTrue("AETHERLINK_RELAY probe known=1 runtime_waiting=0\n".isRelayProbeKnown())
        assertTrue("AETHERLINK_RELAY probe allocated=true runtime_waiting=false\n".isRelayProbeKnown())
        assertFalse("AETHERLINK_RELAY probe known=0 runtime_waiting=1\n".isRelayProbeKnown())
        assertFalse("AETHERLINK_RELAY ready\n".isRelayProbeKnown())
        assertFalse("AETHERLINK_RELAY probe ready\n".isRelayProbeKnown())
        assertFalse("AETHERLINK_RELAY probe unknown\n".isRelayProbeKnown())
    }

    @Test
    fun releasePairingParserRejectsMacosLocalDiagnosticQrRoute() {
        val result = parseRuntimePairingQrPayload(
            rawValue = "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                "&runtime_device_id=runtime-1&runtime_name=AetherLink%20Runtime" +
                "&runtime_key_fingerprint=runtime-fingerprint&route_token=route-1" +
                "&host=192.168.1.44&port=43170&route_scope=local_diagnostic",
            allowDebugLoopbackRelay = false,
            allowDiagnosticLocalDirectEndpoint = false,
        )

        val rejected = result as RuntimePairingQrParseResult.Rejected
        assertEquals("pairing_direct_route_rejected", rejected.error.code)
        assertEquals("route_diagnostic_direct_qr_rejected", rejected.error.diagnosticCode)
        assertEquals(false, rejected.clearPendingPairing)
    }

    @Test
    fun localDirectQrParseFailureReportsRouteQrRequired() {
        val error = pairingQrParseUiError(
            IllegalArgumentException("Local direct endpoint QR routes are diagnostic-only"),
        )

        assertEquals("pairing_direct_route_rejected", error.code)
        assertNull(error.detail)
        assertEquals("Local direct endpoint QR routes are diagnostic-only", error.technicalDetail)
        assertEquals("route_diagnostic_direct_qr_rejected", error.diagnosticCode)
    }

    @Test
    fun unreachableRelayQrParseFailureReportsReachableRouteRequired() {
        val error = pairingQrParseUiError(
            IllegalArgumentException("Relay host is not reachable for remote pairing"),
        )

        assertEquals("pairing_relay_route_rejected", error.code)
        assertNull(error.detail)
        assertEquals("Relay host is not reachable for remote pairing", error.technicalDetail)
        assertEquals("route_diagnostic_relay_qr_unreachable", error.diagnosticCode)
    }

    @Test
    fun privateOverlayRelayQrParseFailureReportsScopeRequired() {
        val error = pairingQrParseUiError(
            IllegalArgumentException("Private relay hosts require relay_scope=private_overlay"),
        )

        assertEquals("pairing_relay_route_rejected", error.code)
        assertNull(error.detail)
        assertEquals("Private relay hosts require relay_scope=private_overlay", error.technicalDetail)
        assertEquals("route_diagnostic_private_overlay_scope_required", error.diagnosticCode)
    }

    @Test
    fun genericQrParseFailureStillReportsInvalidPairingQr() {
        val error = pairingQrParseUiError(
            IllegalArgumentException("Missing pairing nonce"),
        )

        assertEquals("invalid_pairing_qr", error.code)
        assertNull(error.detail)
        assertEquals("Missing pairing nonce", error.technicalDetail)
        assertNull(error.diagnosticCode)
    }

    @Test
    fun acceptedPairingResultRejectsIncompleteRelayRouteInsteadOfDirectFallback() {
        val acceptedPayload = PairingResultPayload(
            accepted = true,
            runtimeDeviceIdV2 = "runtime-1",
            runtimePublicKey = "runtime-public-key",
            runtimeKeyFingerprint = "runtime-fingerprint",
            trustedDeviceId = "client-1",
            message = "trusted",
        )
        val incompleteRelayRoutes = listOf(
            runtimePairingPayload(
                host = "192.168.1.10",
                port = 43170,
                relayHost = "relay.example.test",
                relayPort = 443,
                relayId = "relay-1",
                relaySecret = null,
                relayExpiresAtEpochMillis = 4102444800000L,
                relayNonce = "nonce-route-1",
            ),
            runtimePairingPayload(
                host = "192.168.1.10",
                port = 43170,
                relayHost = "relay.example.test",
                relayPort = null,
                relayId = "relay-1",
                relaySecret = "secret-1",
                relayExpiresAtEpochMillis = 4102444800000L,
                relayNonce = "nonce-route-1",
            ),
            runtimePairingPayload(
                host = "192.168.1.10",
                port = 43170,
                relayHost = "relay.example.test",
                relayPort = 443,
                relayId = "relay-1",
                relaySecret = "secret-1",
                relayExpiresAtEpochMillis = 4102444800000L,
                relayNonce = "",
            ),
            runtimePairingPayload(
                host = "192.168.1.10",
                port = 43170,
                relayHost = "relay.example.test",
            ),
        )

        incompleteRelayRoutes.forEach { pending ->
            val trusted = trustedRuntimeFromAcceptedPairing(
                pending = pending,
                payload = acceptedPayload,
            )

            assertNull(trusted)
        }

        val directOnlyPending = runtimePairingPayload(
            host = "192.168.1.10",
            port = 43170,
        )
        val directOnlyTrusted = trustedRuntimeFromAcceptedPairing(
            pending = directOnlyPending,
            payload = acceptedPayload,
        ) ?: error("Expected trusted runtime")
        val directOnlyEndpoint = acceptedPairingCurrentEndpointHint(directOnlyPending)

        assertNull(directOnlyTrusted.host)
        assertNull(directOnlyTrusted.port)
        assertEquals("192.168.1.10", directOnlyEndpoint?.host)
        assertEquals(43170, directOnlyEndpoint?.port)
        assertEquals(RuntimeEndpointSource.PairingQr, directOnlyEndpoint?.source)
        assertNull(directOnlyTrusted.relayHost)
        assertNull(directOnlyTrusted.relayPort)
        assertNull(directOnlyTrusted.relayId)
        assertNull(directOnlyTrusted.relaySecret)
    }

    @Test
    fun acceptedPairingResultRejectsIncompleteP2pRouteInsteadOfDirectFallback() {
        val acceptedPayload = PairingResultPayload(
            accepted = true,
            runtimeDeviceIdV2 = "runtime-1",
            runtimePublicKey = "runtime-public-key",
            runtimeKeyFingerprint = "runtime-fingerprint",
            trustedDeviceId = "client-1",
            message = "trusted",
        )
        val incompleteP2pRoutes = listOf(
            runtimePairingPayload(
                host = "192.168.1.10",
                port = 43170,
                p2pRouteClass = "p2p_rendezvous",
                p2pRecordId = "p2p-record-1",
                p2pEncryptedBody = null,
                p2pExpiresAtEpochMillis = 4102444800000L,
                p2pAntiReplayNonce = "nonce-p2p-1",
                p2pProtocolVersion = 1,
            ),
            runtimePairingPayload(
                host = "192.168.1.10",
                port = 43170,
                p2pRouteClass = "p2p_rendezvous",
                p2pRecordId = "p2p-record-1",
                p2pEncryptedBody = "opaque-candidate-1",
                p2pExpiresAtEpochMillis = null,
                p2pAntiReplayNonce = "nonce-p2p-1",
                p2pProtocolVersion = 1,
            ),
            runtimePairingPayload(
                host = "192.168.1.10",
                port = 43170,
                p2pRouteClass = "p2p_rendezvous",
                p2pRecordId = "p2p-record-1",
                p2pEncryptedBody = "opaque-candidate-1",
                p2pExpiresAtEpochMillis = 4102444800000L,
                p2pAntiReplayNonce = "nonce-p2p-1",
                p2pProtocolVersion = 2,
            ),
        )

        incompleteP2pRoutes.forEach { pending ->
            val trusted = trustedRuntimeFromAcceptedPairing(
                pending = pending,
                payload = acceptedPayload,
            )

            assertNull(trusted)
        }
    }

    @Test
    fun expiredRelayQrIsNotSavedAsTrustedRuntime() {
        val pending = runtimePairingPayload(
            host = null,
            port = null,
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 1L,
            relayNonce = "nonce-route-1",
        )

        val trusted = trustedRuntimeFromAcceptedPairing(
            pending = pending,
            payload = PairingResultPayload(
                accepted = true,
                runtimeDeviceIdV2 = "runtime-1",
                runtimePublicKey = "runtime-public-key",
                runtimeKeyFingerprint = "runtime-fingerprint",
                trustedDeviceId = "client-1",
                message = "trusted",
            ),
        )

        assertNull(trusted)
    }

    @Test
    fun expiredP2pQrIsNotSavedAsTrustedRuntime() {
        val pending = runtimePairingPayload(
            host = null,
            port = null,
            p2pRouteClass = "p2p_rendezvous",
            p2pRecordId = "p2p-record-1",
            p2pEncryptedBody = "opaque-candidate-1",
            p2pExpiresAtEpochMillis = 1L,
            p2pAntiReplayNonce = "nonce-p2p-1",
            p2pProtocolVersion = 1,
        )

        val trusted = trustedRuntimeFromAcceptedPairing(
            pending = pending,
            payload = PairingResultPayload(
                accepted = true,
                runtimeDeviceIdV2 = "runtime-1",
                runtimePublicKey = "runtime-public-key",
                runtimeKeyFingerprint = "runtime-fingerprint",
                trustedDeviceId = "client-1",
                message = "trusted",
            ),
        )

        assertNull(trusted)
    }

    @Test
    fun routeRefreshQrAddsRelayRouteToExistingTrustedRuntime() {
        val current = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-1",
            endpointHint = RuntimeEndpointHint(
                host = "192.168.219.104",
                port = 43170,
                source = RuntimeEndpointSource.TrustedLastKnown,
            ),
        )
        val payload = runtimePairingPayload(
            host = null,
            port = null,
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-1",
        )

        val refreshed = trustedRuntimeFromRouteRefreshQr(current, payload)

        assertEquals("runtime-1", refreshed?.deviceId)
        assertEquals("runtime-fingerprint", refreshed?.fingerprint)
        assertEquals("runtime-public-key", refreshed?.publicKeyBase64)
        assertEquals("route-1", refreshed?.routeToken)
        assertNull(refreshed?.host)
        assertNull(refreshed?.port)
        assertEquals("relay.example.test", refreshed?.relayHost)
        assertEquals(443, refreshed?.relayPort)
        assertEquals("relay-1", refreshed?.relayId)
        assertEquals("secret-1", refreshed?.relaySecret)
        assertEquals(4102444800000L, refreshed?.relayExpiresAtEpochMillis)
        assertEquals("nonce-route-1", refreshed?.relayNonce)
    }

    @Test
    fun routeRefreshQrAddsP2pRendezvousRouteToExistingTrustedRuntime() {
        val current = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-1",
            endpointHint = RuntimeEndpointHint(
                host = "192.168.219.104",
                port = 43170,
                source = RuntimeEndpointSource.TrustedLastKnown,
            ),
        )
        val payload = runtimePairingPayload(
            host = null,
            port = null,
            p2pRouteClass = "p2p_rendezvous",
            p2pRecordId = "p2p-record-1",
            p2pEncryptedBody = "opaque-candidate-1",
            p2pExpiresAtEpochMillis = 4102444800000L,
            p2pAntiReplayNonce = "nonce-p2p-1",
            p2pProtocolVersion = 1,
        )

        val refreshed = trustedRuntimeFromRouteRefreshQr(current, payload)

        assertEquals("runtime-1", refreshed?.deviceId)
        assertEquals("runtime-fingerprint", refreshed?.fingerprint)
        assertEquals("runtime-public-key", refreshed?.publicKeyBase64)
        assertEquals("route-1", refreshed?.routeToken)
        assertNull(refreshed?.host)
        assertNull(refreshed?.port)
        assertEquals("p2p_rendezvous", refreshed?.p2pRouteClass)
        assertEquals("p2p-record-1", refreshed?.p2pRecordId)
        assertEquals("opaque-candidate-1", refreshed?.p2pEncryptedBody)
        assertEquals(4102444800000L, refreshed?.p2pExpiresAtEpochMillis)
        assertEquals("nonce-p2p-1", refreshed?.p2pAntiReplayNonce)
        assertEquals(1, refreshed?.p2pProtocolVersion)
    }

    @Test
    fun routeRefreshQrRejectsReusedOrNonAdvancingRemoteRouteMaterial() {
        val currentRelay = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-1",
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "current-relay",
            relaySecret = "current-secret",
            relayExpiresAtEpochMillis = 300_000L,
            relayNonce = "current-relay-nonce",
            relayScope = "remote",
        )
        listOf(
            runtimePairingPayload(
                host = null,
                port = null,
                relayHost = "relay.example.test",
                relayPort = 443,
                relayId = "fresh-relay",
                relaySecret = "fresh-secret",
                relayExpiresAtEpochMillis = 600_000L,
                relayNonce = "current-relay-nonce",
                relayScope = "remote",
            ),
            runtimePairingPayload(
                host = null,
                port = null,
                relayHost = "relay.example.test",
                relayPort = 443,
                relayId = "fresh-relay-same-expiry",
                relaySecret = "fresh-secret-same-expiry",
                relayExpiresAtEpochMillis = 300_000L,
                relayNonce = "fresh-relay-nonce-same-expiry",
                relayScope = "remote",
            ),
            runtimePairingPayload(
                host = null,
                port = null,
                relayHost = "relay.example.test",
                relayPort = 443,
                relayId = "fresh-relay-older-expiry",
                relaySecret = "fresh-secret-older-expiry",
                relayExpiresAtEpochMillis = 299_999L,
                relayNonce = "fresh-relay-nonce-older-expiry",
                relayScope = "remote",
            ),
        ).forEach { payload ->
            assertNull(
                trustedRuntimeFromRouteRefreshQr(
                    current = currentRelay,
                    payload = payload,
                    nowEpochMillis = 1_000L,
                ),
            )
        }

        val currentP2p = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-1",
            p2pRouteClass = "p2p_rendezvous",
            p2pRecordId = "current-p2p-record",
            p2pEncryptedBody = "current-p2p-body",
            p2pExpiresAtEpochMillis = 300_000L,
            p2pAntiReplayNonce = "current-p2p-nonce",
            p2pProtocolVersion = 1,
        )
        listOf(
            runtimePairingPayload(
                host = null,
                port = null,
                p2pRouteClass = "p2p_rendezvous",
                p2pRecordId = "current-p2p-record",
                p2pEncryptedBody = "fresh-p2p-body",
                p2pExpiresAtEpochMillis = 600_000L,
                p2pAntiReplayNonce = "fresh-p2p-nonce",
                p2pProtocolVersion = 1,
            ),
            runtimePairingPayload(
                host = null,
                port = null,
                p2pRouteClass = "p2p_rendezvous",
                p2pRecordId = "fresh-p2p-record",
                p2pEncryptedBody = "fresh-p2p-body",
                p2pExpiresAtEpochMillis = 600_000L,
                p2pAntiReplayNonce = "current-p2p-nonce",
                p2pProtocolVersion = 1,
            ),
            runtimePairingPayload(
                host = null,
                port = null,
                p2pRouteClass = "p2p_rendezvous",
                p2pRecordId = "fresh-p2p-record-same-expiry",
                p2pEncryptedBody = "fresh-p2p-body-same-expiry",
                p2pExpiresAtEpochMillis = 300_000L,
                p2pAntiReplayNonce = "fresh-p2p-nonce-same-expiry",
                p2pProtocolVersion = 1,
            ),
            runtimePairingPayload(
                host = null,
                port = null,
                p2pRouteClass = "p2p_rendezvous",
                p2pRecordId = "fresh-p2p-record-older-expiry",
                p2pEncryptedBody = "fresh-p2p-body-older-expiry",
                p2pExpiresAtEpochMillis = 299_999L,
                p2pAntiReplayNonce = "fresh-p2p-nonce-older-expiry",
                p2pProtocolVersion = 1,
            ),
        ).forEach { payload ->
            assertNull(
                trustedRuntimeFromRouteRefreshQr(
                    current = currentP2p,
                    payload = payload,
                    nowEpochMillis = 1_000L,
                ),
            )
        }
    }

    @Test
    fun routeRefreshQrWithoutPublicKeyCanRefreshPinnedRuntimeRelayRoute() {
        val current = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-old",
            endpointHint = null,
        )
        val payload = runtimePairingPayload(
            runtimePublicKeyBase64 = null,
            routeToken = "route-new",
            host = null,
            port = null,
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-new",
            relaySecret = "secret-new",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-new",
        )

        val refreshed = trustedRuntimeFromRouteRefreshQr(current, payload)

        assertEquals("runtime-1", refreshed?.deviceId)
        assertEquals("runtime-fingerprint", refreshed?.fingerprint)
        assertEquals("runtime-public-key", refreshed?.publicKeyBase64)
        assertEquals("route-new", refreshed?.routeToken)
        assertNull(refreshed?.host)
        assertNull(refreshed?.port)
        assertEquals("relay.example.test", refreshed?.relayHost)
        assertEquals(443, refreshed?.relayPort)
        assertEquals("relay-new", refreshed?.relayId)
        assertEquals("secret-new", refreshed?.relaySecret)
        assertEquals(4102444800000L, refreshed?.relayExpiresAtEpochMillis)
        assertEquals("nonce-route-new", refreshed?.relayNonce)
    }

    @Test
    fun routeRefreshQrWithoutPublicKeyCanRefreshPinnedRuntimeP2pRendezvousRoute() {
        val current = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-old",
            endpointHint = null,
        )
        val payload = runtimePairingPayload(
            runtimePublicKeyBase64 = null,
            routeToken = "route-new",
            host = null,
            port = null,
            p2pRouteClass = "p2p_rendezvous",
            p2pRecordId = "p2p-record-new",
            p2pEncryptedBody = "opaque-candidate-new",
            p2pExpiresAtEpochMillis = 4102444800000L,
            p2pAntiReplayNonce = "nonce-p2p-new",
            p2pProtocolVersion = 1,
        )

        val refreshed = trustedRuntimeFromRouteRefreshQr(current, payload)

        assertEquals("runtime-1", refreshed?.deviceId)
        assertEquals("runtime-fingerprint", refreshed?.fingerprint)
        assertEquals("runtime-public-key", refreshed?.publicKeyBase64)
        assertEquals("route-new", refreshed?.routeToken)
        assertNull(refreshed?.host)
        assertNull(refreshed?.port)
        assertNull(refreshed?.relayHost)
        assertNull(refreshed?.relayPort)
        assertNull(refreshed?.relaySecret)
        assertEquals("p2p_rendezvous", refreshed?.p2pRouteClass)
        assertEquals("p2p-record-new", refreshed?.p2pRecordId)
        assertEquals("opaque-candidate-new", refreshed?.p2pEncryptedBody)
        assertEquals(4102444800000L, refreshed?.p2pExpiresAtEpochMillis)
        assertEquals("nonce-p2p-new", refreshed?.p2pAntiReplayNonce)
        assertEquals(1, refreshed?.p2pProtocolVersion)
    }

    @Test
    fun routeRefreshPayloadAddsFreshRelayRouteToCurrentTrustedRuntime() {
        val current = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token-1",
            relayHost = "old-relay.example.test",
            relayPort = 443,
            relayId = "old-relay",
            relaySecret = "old-secret",
            relayExpiresAtEpochMillis = 2_000L,
            relayNonce = "old-nonce",
            relayScope = "remote",
        )

        val refreshed = trustedRuntimeFromRouteRefreshPayload(
            current = current,
            payload = RouteRefreshPayload(
                runtimeDeviceId = "runtime-1",
                runtimeKeyFingerprint = "runtime-fingerprint",
                relayHost = "fresh-relay.example.test",
                relayPort = 43171,
                relayId = "fresh-relay",
                relaySecret = "fresh-secret",
                relayExpiresAtEpochMillis = 4_102_444_800_000L,
                relayNonce = "fresh-nonce",
                relayScope = "remote",
            ),
            nowEpochMillis = 1_000L,
        ) ?: error("Expected refreshed trusted runtime")

        assertEquals("runtime-1", refreshed.deviceId)
        assertEquals("runtime-fingerprint", refreshed.fingerprint)
        assertEquals("runtime-public-key", refreshed.publicKeyBase64)
        assertEquals("route-token-1", refreshed.routeToken)
        assertNull(refreshed.host)
        assertNull(refreshed.port)
        assertEquals("fresh-relay.example.test", refreshed.relayHost)
        assertEquals(43171, refreshed.relayPort)
        assertEquals("fresh-relay", refreshed.relayId)
        assertEquals("fresh-secret", refreshed.relaySecret)
        assertEquals(4_102_444_800_000L, refreshed.relayExpiresAtEpochMillis)
        assertEquals("fresh-nonce", refreshed.relayNonce)
        assertEquals("remote", refreshed.relayScope)
    }

    @Test
    fun routeRefreshPayloadAllowsStableRelayIdAndSecretWithFreshNonceAndExpiry() {
        val current = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token-1",
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "stable-relay-id",
            relaySecret = "stable-relay-secret",
            relayExpiresAtEpochMillis = 300_000L,
            relayNonce = "current-relay-nonce",
            relayScope = "remote",
        )

        val refreshed = trustedRuntimeFromRouteRefreshPayload(
            current = current,
            payload = RouteRefreshPayload(
                runtimeDeviceId = "runtime-1",
                runtimeKeyFingerprint = "runtime-fingerprint",
                relayHost = "relay.example.test",
                relayPort = 443,
                relayId = "stable-relay-id",
                relaySecret = "stable-relay-secret",
                relayExpiresAtEpochMillis = 600_000L,
                relayNonce = "fresh-relay-nonce",
                relayScope = "remote",
            ),
            nowEpochMillis = 1_000L,
        ) ?: error("Expected refreshed trusted runtime")

        assertEquals("stable-relay-id", refreshed.relayId)
        assertEquals("stable-relay-secret", refreshed.relaySecret)
        assertEquals(600_000L, refreshed.relayExpiresAtEpochMillis)
        assertEquals("fresh-relay-nonce", refreshed.relayNonce)
    }

    @Test
    fun routeRefreshPayloadRejectsReusedRelayNonce() {
        val current = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token-1",
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "current-relay",
            relaySecret = "current-secret",
            relayExpiresAtEpochMillis = 300_000L,
            relayNonce = "current-relay-nonce",
            relayScope = "remote",
        )

        assertNull(
            trustedRuntimeFromRouteRefreshPayload(
                current = current,
                payload = RouteRefreshPayload(
                    runtimeDeviceId = "runtime-1",
                    runtimeKeyFingerprint = "runtime-fingerprint",
                    relayHost = "fresh-relay.example.test",
                    relayPort = 43171,
                    relayId = "fresh-relay",
                    relaySecret = "fresh-secret",
                    relayExpiresAtEpochMillis = 600_000L,
                    relayNonce = "current-relay-nonce",
                    relayScope = "remote",
                ),
                nowEpochMillis = 1_000L,
            ),
        )
    }

    @Test
    fun routeRefreshPayloadRejectsNonAdvancingRelayExpiry() {
        val current = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token-1",
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "current-relay",
            relaySecret = "current-secret",
            relayExpiresAtEpochMillis = 300_000L,
            relayNonce = "current-relay-nonce",
            relayScope = "remote",
        )

        listOf(299_999L, 300_000L).forEach { refreshedExpiry ->
            assertNull(
                trustedRuntimeFromRouteRefreshPayload(
                    current = current,
                    payload = RouteRefreshPayload(
                        runtimeDeviceId = "runtime-1",
                        runtimeKeyFingerprint = "runtime-fingerprint",
                        relayHost = "fresh-relay.example.test",
                        relayPort = 43171,
                        relayId = "fresh-relay-$refreshedExpiry",
                        relaySecret = "fresh-secret-$refreshedExpiry",
                        relayExpiresAtEpochMillis = refreshedExpiry,
                        relayNonce = "fresh-relay-nonce-$refreshedExpiry",
                        relayScope = "remote",
                    ),
                    nowEpochMillis = 1_000L,
                ),
            )
        }
    }

    @Test
    fun routeRefreshPayloadAddsFreshP2pRendezvousRouteToCurrentTrustedRuntime() {
        val maxSizedP2pEncryptedBody = maxSizedOpaqueP2pEncryptedBody()
        val current = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token-1",
            p2pRouteClass = "p2p_rendezvous",
            p2pRecordId = "old-p2p-record",
            p2pEncryptedBody = "old-p2p-body",
            p2pExpiresAtEpochMillis = 2_000L,
            p2pAntiReplayNonce = "old-p2p-nonce",
            p2pProtocolVersion = 1,
        )

        val refreshed = trustedRuntimeFromRouteRefreshPayload(
            current = current,
            payload = RouteRefreshPayload(
                runtimeDeviceId = "runtime-1",
                runtimeKeyFingerprint = "runtime-fingerprint",
                p2pRouteClass = "p2p_rendezvous",
                p2pRecordId = "fresh-p2p-record",
                p2pEncryptedBody = maxSizedP2pEncryptedBody,
                p2pExpiresAtEpochMillis = 4_102_444_800_000L,
                p2pAntiReplayNonce = "fresh-p2p-nonce",
                p2pProtocolVersion = 1,
            ),
            nowEpochMillis = 1_000L,
        ) ?: error("Expected refreshed trusted runtime")

        assertEquals("runtime-1", refreshed.deviceId)
        assertEquals("runtime-fingerprint", refreshed.fingerprint)
        assertEquals("runtime-public-key", refreshed.publicKeyBase64)
        assertEquals("route-token-1", refreshed.routeToken)
        assertNull(refreshed.host)
        assertNull(refreshed.port)
        assertNull(refreshed.relayHost)
        assertNull(refreshed.relayPort)
        assertEquals("p2p_rendezvous", refreshed.p2pRouteClass)
        assertEquals("fresh-p2p-record", refreshed.p2pRecordId)
        assertEquals(OPAQUE_ROUTE_BODY_MAX_CHARS, maxSizedP2pEncryptedBody.length)
        assertEquals(maxSizedP2pEncryptedBody, refreshed.p2pEncryptedBody)
        assertEquals(4_102_444_800_000L, refreshed.p2pExpiresAtEpochMillis)
        assertEquals("fresh-p2p-nonce", refreshed.p2pAntiReplayNonce)
        assertEquals(1, refreshed.p2pProtocolVersion)
    }

    @Test
    fun routeRefreshPayloadRejectsReusedP2pRendezvousRecordOrNonce() {
        val current = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token-1",
            p2pRouteClass = "p2p_rendezvous",
            p2pRecordId = "current-p2p-record",
            p2pEncryptedBody = "current-p2p-body",
            p2pExpiresAtEpochMillis = 300_000L,
            p2pAntiReplayNonce = "current-p2p-nonce",
            p2pProtocolVersion = 1,
        )

        assertNull(
            trustedRuntimeFromRouteRefreshPayload(
                current = current,
                payload = RouteRefreshPayload(
                    runtimeDeviceId = "runtime-1",
                    runtimeKeyFingerprint = "runtime-fingerprint",
                    p2pRouteClass = "p2p_rendezvous",
                    p2pRecordId = "current-p2p-record",
                    p2pEncryptedBody = "fresh-p2p-body",
                    p2pExpiresAtEpochMillis = 600_000L,
                    p2pAntiReplayNonce = "fresh-p2p-nonce",
                    p2pProtocolVersion = 1,
                ),
                nowEpochMillis = 1_000L,
            ),
        )
        assertNull(
            trustedRuntimeFromRouteRefreshPayload(
                current = current,
                payload = RouteRefreshPayload(
                    runtimeDeviceId = "runtime-1",
                    runtimeKeyFingerprint = "runtime-fingerprint",
                    p2pRouteClass = "p2p_rendezvous",
                    p2pRecordId = "fresh-p2p-record",
                    p2pEncryptedBody = "fresh-p2p-body",
                    p2pExpiresAtEpochMillis = 600_000L,
                    p2pAntiReplayNonce = "current-p2p-nonce",
                    p2pProtocolVersion = 1,
                ),
                nowEpochMillis = 1_000L,
            ),
        )
    }

    @Test
    fun routeRefreshPayloadRejectsNonAdvancingP2pExpiry() {
        val current = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token-1",
            p2pRouteClass = "p2p_rendezvous",
            p2pRecordId = "current-p2p-record",
            p2pEncryptedBody = "current-p2p-body",
            p2pExpiresAtEpochMillis = 300_000L,
            p2pAntiReplayNonce = "current-p2p-nonce",
            p2pProtocolVersion = 1,
        )

        listOf(299_999L, 300_000L).forEach { refreshedExpiry ->
            assertNull(
                trustedRuntimeFromRouteRefreshPayload(
                    current = current,
                    payload = RouteRefreshPayload(
                        runtimeDeviceId = "runtime-1",
                        runtimeKeyFingerprint = "runtime-fingerprint",
                        p2pRouteClass = "p2p_rendezvous",
                        p2pRecordId = "fresh-p2p-record-$refreshedExpiry",
                        p2pEncryptedBody = "fresh-p2p-body-$refreshedExpiry",
                        p2pExpiresAtEpochMillis = refreshedExpiry,
                        p2pAntiReplayNonce = "fresh-p2p-nonce-$refreshedExpiry",
                        p2pProtocolVersion = 1,
                    ),
                    nowEpochMillis = 1_000L,
                ),
            )
        }
    }

    @Test
    fun routeRefreshPayloadRejectsUnknownRelayScope() {
        val current = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token-1",
        )

        assertNull(
            trustedRuntimeFromRouteRefreshPayload(
                current = current,
                payload = RouteRefreshPayload(
                    runtimeDeviceId = "runtime-1",
                    runtimeKeyFingerprint = "runtime-fingerprint",
                    relayHost = "fresh-relay.example.test",
                    relayPort = 43171,
                    relayId = "fresh-relay",
                    relaySecret = "fresh-secret",
                    relayExpiresAtEpochMillis = 4_102_444_800_000L,
                    relayNonce = "fresh-nonce",
                    relayScope = "public",
                ),
                nowEpochMillis = 1_000L,
            ),
        )
        assertNull(
            trustedRuntimeFromRouteRefreshPayload(
                current = current,
                payload = RouteRefreshPayload(
                    runtimeDeviceId = "runtime-1",
                    runtimeKeyFingerprint = "runtime-fingerprint",
                    relayHost = "fresh-relay.example.test",
                    relayPort = 43171,
                    relayId = "fresh-relay",
                    relaySecret = "fresh-secret",
                    relayExpiresAtEpochMillis = 4_102_444_800_000L,
                    relayNonce = "fresh-nonce",
                    relayScope = " remote ",
                ),
                nowEpochMillis = 1_000L,
            ),
        )
    }

    @Test
    fun routeRefreshPayloadRejectsScopedRelayHostScopeMismatch() {
        val current = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token-1",
        )

        fun payload(relayHost: String, relayScope: String?) = RouteRefreshPayload(
            runtimeDeviceId = "runtime-1",
            runtimeKeyFingerprint = "runtime-fingerprint",
            relayHost = relayHost,
            relayPort = 43171,
            relayId = "fresh-relay",
            relaySecret = "fresh-secret",
            relayExpiresAtEpochMillis = 4_102_444_800_000L,
            relayNonce = "fresh-nonce",
            relayScope = relayScope,
        )

        listOf(
            payload(relayHost = "100.64.1.10", relayScope = null),
            payload(relayHost = "100.64.1.10", relayScope = "remote"),
            payload(relayHost = "127.0.0.1", relayScope = null),
            payload(relayHost = "127.0.0.1", relayScope = "remote"),
        ).forEach { payload ->
            assertNull(
                trustedRuntimeFromRouteRefreshPayload(
                    current = current,
                    payload = payload,
                    nowEpochMillis = 1_000L,
                ),
            )
        }
    }

    @Test
    fun routeRefreshPayloadRejectsNonCanonicalRelayMaterial() {
        val current = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token-1",
        )

        listOf(
            RouteRefreshPayload(
                runtimeDeviceId = "runtime-1",
                runtimeKeyFingerprint = "runtime-fingerprint",
                relayHost = " fresh-relay.example.test",
                relayPort = 43171,
                relayId = "fresh-relay",
                relaySecret = "fresh-secret",
                relayExpiresAtEpochMillis = 4_102_444_800_000L,
                relayNonce = "fresh-nonce",
                relayScope = "remote",
            ),
            RouteRefreshPayload(
                runtimeDeviceId = "runtime-1",
                runtimeKeyFingerprint = "runtime-fingerprint",
                relayHost = "https://fresh-relay.example.test",
                relayPort = 43171,
                relayId = "fresh-relay",
                relaySecret = "fresh-secret",
                relayExpiresAtEpochMillis = 4_102_444_800_000L,
                relayNonce = "fresh-nonce",
                relayScope = "remote",
            ),
            RouteRefreshPayload(
                runtimeDeviceId = "runtime-1",
                runtimeKeyFingerprint = "runtime-fingerprint",
                relayHost = "fresh-relay.example.test",
                relayPort = 43171,
                relayId = "fresh relay",
                relaySecret = "fresh-secret",
                relayExpiresAtEpochMillis = 4_102_444_800_000L,
                relayNonce = "fresh-nonce",
                relayScope = "remote",
            ),
            RouteRefreshPayload(
                runtimeDeviceId = "runtime-1",
                runtimeKeyFingerprint = "runtime-fingerprint",
                relayHost = "fresh-relay.example.test",
                relayPort = 43171,
                relayId = "fresh-relay",
                relaySecret = " fresh-secret",
                relayExpiresAtEpochMillis = 4_102_444_800_000L,
                relayNonce = "fresh-nonce",
                relayScope = "remote",
            ),
            RouteRefreshPayload(
                runtimeDeviceId = "runtime-1",
                runtimeKeyFingerprint = "runtime-fingerprint",
                relayHost = "fresh-relay.example.test",
                relayPort = 43171,
                relayId = "fresh-relay",
                relaySecret = "fresh-secret",
                relayExpiresAtEpochMillis = 4_102_444_800_000L,
                relayNonce = "n".repeat(513),
                relayScope = "remote",
            ),
        ).forEach { payload ->
            assertNull(
                trustedRuntimeFromRouteRefreshPayload(
                    current = current,
                    payload = payload,
                    nowEpochMillis = 1_000L,
                ),
            )
        }
    }

    @Test
    fun routeRefreshPayloadRejectsExpiredOrIncompleteRelayMaterial() {
        val current = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token-1",
        )

        assertNull(
            trustedRuntimeFromRouteRefreshPayload(
                current = current,
                payload = RouteRefreshPayload(
                    runtimeDeviceId = "runtime-1",
                    runtimeKeyFingerprint = "runtime-fingerprint",
                    relayHost = "fresh-relay.example.test",
                    relayPort = 43171,
                    relayId = "fresh-relay",
                    relaySecret = "fresh-secret",
                    relayExpiresAtEpochMillis = 999L,
                    relayNonce = "fresh-nonce",
                    relayScope = "remote",
                ),
                nowEpochMillis = 1_000L,
            ),
        )
        assertNull(
            trustedRuntimeFromRouteRefreshPayload(
                current = current,
                payload = RouteRefreshPayload(
                    runtimeDeviceId = "runtime-1",
                    runtimeKeyFingerprint = "runtime-fingerprint",
                    relayHost = "fresh-relay.example.test",
                    relayPort = 43171,
                    relayId = "fresh-relay",
                    relaySecret = null,
                    relayExpiresAtEpochMillis = 4_102_444_800_000L,
                    relayNonce = "fresh-nonce",
                    relayScope = "remote",
                ),
                nowEpochMillis = 1_000L,
            ),
        )
    }

    @Test
    fun routeRefreshPayloadRejectsExpiredOrIncompleteP2pMaterial() {
        val current = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token-1",
        )

        assertNull(
            trustedRuntimeFromRouteRefreshPayload(
                current = current,
                payload = RouteRefreshPayload(
                    runtimeDeviceId = "runtime-1",
                    runtimeKeyFingerprint = "runtime-fingerprint",
                    p2pRouteClass = "p2p_rendezvous",
                    p2pRecordId = "fresh-p2p-record",
                    p2pEncryptedBody = "fresh-p2p-body",
                    p2pExpiresAtEpochMillis = 999L,
                    p2pAntiReplayNonce = "fresh-p2p-nonce",
                    p2pProtocolVersion = 1,
                ),
                nowEpochMillis = 1_000L,
            ),
        )
        assertNull(
            trustedRuntimeFromRouteRefreshPayload(
                current = current,
                payload = RouteRefreshPayload(
                    runtimeDeviceId = "runtime-1",
                    runtimeKeyFingerprint = "runtime-fingerprint",
                    p2pRouteClass = "p2p_rendezvous",
                    p2pRecordId = "fresh-p2p-record",
                    p2pEncryptedBody = null,
                    p2pExpiresAtEpochMillis = 4_102_444_800_000L,
                    p2pAntiReplayNonce = "fresh-p2p-nonce",
                    p2pProtocolVersion = 1,
                ),
                nowEpochMillis = 1_000L,
            ),
        )
        assertNull(
            trustedRuntimeFromRouteRefreshPayload(
                current = current,
                payload = RouteRefreshPayload(
                    runtimeDeviceId = "runtime-1",
                    runtimeKeyFingerprint = "runtime-fingerprint",
                    relayHost = "fresh-relay.example.test",
                    relayPort = 43171,
                    relayId = "fresh-relay",
                    relaySecret = "fresh-secret",
                    relayExpiresAtEpochMillis = 4_102_444_800_000L,
                    relayNonce = "fresh-nonce",
                    relayScope = "remote",
                    p2pRouteClass = "p2p_rendezvous",
                    p2pRecordId = "fresh-p2p-record",
                ),
                nowEpochMillis = 1_000L,
            ),
        )
    }

    @Test
    fun routeRefreshPayloadRejectsNonCanonicalP2pMaterial() {
        val current = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token-1",
        )

        listOf(
            RouteRefreshPayload(
                runtimeDeviceId = "runtime-1",
                runtimeKeyFingerprint = "runtime-fingerprint",
                p2pRouteClass = " p2p_rendezvous",
                p2pRecordId = "fresh-p2p-record",
                p2pEncryptedBody = "fresh-p2p-body",
                p2pExpiresAtEpochMillis = 4_102_444_800_000L,
                p2pAntiReplayNonce = "fresh-p2p-nonce",
                p2pProtocolVersion = 1,
            ),
            RouteRefreshPayload(
                runtimeDeviceId = "runtime-1",
                runtimeKeyFingerprint = "runtime-fingerprint",
                p2pRouteClass = "p2p_rendezvous",
                p2pRecordId = "fresh p2p record",
                p2pEncryptedBody = "fresh-p2p-body",
                p2pExpiresAtEpochMillis = 4_102_444_800_000L,
                p2pAntiReplayNonce = "fresh-p2p-nonce",
                p2pProtocolVersion = 1,
            ),
            RouteRefreshPayload(
                runtimeDeviceId = "runtime-1",
                runtimeKeyFingerprint = "runtime-fingerprint",
                p2pRouteClass = "p2p_rendezvous",
                p2pRecordId = "fresh-p2p-record",
                p2pEncryptedBody = " fresh-p2p-body",
                p2pExpiresAtEpochMillis = 4_102_444_800_000L,
                p2pAntiReplayNonce = "fresh-p2p-nonce",
                p2pProtocolVersion = 1,
            ),
            RouteRefreshPayload(
                runtimeDeviceId = "runtime-1",
                runtimeKeyFingerprint = "runtime-fingerprint",
                relayHost = "fresh-relay.example.test",
                relayPort = 43171,
                relayId = "fresh-relay",
                relaySecret = "fresh-secret",
                relayExpiresAtEpochMillis = 4_102_444_800_000L,
                relayNonce = "fresh-nonce",
                relayScope = "remote",
                p2pRouteClass = "p2p_rendezvous",
                p2pRecordId = "fresh-p2p-record",
                p2pEncryptedBody = "fresh-p2p-body",
                p2pExpiresAtEpochMillis = 4_102_444_800_000L,
                p2pAntiReplayNonce = "fresh p2p nonce",
                p2pProtocolVersion = 1,
            ),
        ).forEach { payload ->
            assertNull(
                trustedRuntimeFromRouteRefreshPayload(
                    current = current,
                    payload = payload,
                    nowEpochMillis = 1_000L,
                ),
            )
        }
    }

    @Test
    fun routeRefreshPayloadRejectsMismatchedRuntimeIdentity() {
        val current = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token-1",
        )

        assertNull(
            trustedRuntimeFromRouteRefreshPayload(
                current = current,
                payload = RouteRefreshPayload(
                    runtimeDeviceId = "other-runtime",
                    runtimeKeyFingerprint = "runtime-fingerprint",
                    relayHost = "fresh-relay.example.test",
                    relayPort = 43171,
                    relayId = "fresh-relay",
                    relaySecret = "fresh-secret",
                    relayExpiresAtEpochMillis = 4_102_444_800_000L,
                    relayNonce = "fresh-nonce",
                    relayScope = "remote",
                ),
                nowEpochMillis = 1_000L,
            ),
        )
        assertNull(
            trustedRuntimeFromRouteRefreshPayload(
                current = current,
                payload = RouteRefreshPayload(
                    runtimeDeviceId = "runtime-1",
                    runtimeKeyFingerprint = "other-fingerprint",
                    relayHost = "fresh-relay.example.test",
                    relayPort = 43171,
                    relayId = "fresh-relay",
                    relaySecret = "fresh-secret",
                    relayExpiresAtEpochMillis = 4_102_444_800_000L,
                    relayNonce = "fresh-nonce",
                    relayScope = "remote",
                ),
                nowEpochMillis = 1_000L,
            ),
        )
        assertNull(
            trustedRuntimeFromRouteRefreshPayload(
                current = current,
                payload = RouteRefreshPayload(
                    relayHost = "fresh-relay.example.test",
                    relayPort = 43171,
                    relayId = "fresh-relay",
                    relaySecret = "fresh-secret",
                    relayExpiresAtEpochMillis = 4_102_444_800_000L,
                    relayNonce = "fresh-nonce",
                    relayScope = "remote",
                ),
                nowEpochMillis = 1_000L,
            ),
        )
    }

    @Test
    fun routeRefreshPayloadRejectsNonCanonicalRuntimeIdentity() {
        val current = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token-1",
        )

        listOf(
            RouteRefreshPayload(
                runtimeDeviceId = "runtime-1 ",
                runtimeKeyFingerprint = "runtime-fingerprint",
                relayHost = "fresh-relay.example.test",
                relayPort = 43171,
                relayId = "fresh-relay",
                relaySecret = "fresh-secret",
                relayExpiresAtEpochMillis = 4_102_444_800_000L,
                relayNonce = "fresh-nonce",
                relayScope = "remote",
            ),
            RouteRefreshPayload(
                runtimeDeviceId = "runtime-1",
                runtimeKeyFingerprint = " runtime-fingerprint",
                relayHost = "fresh-relay.example.test",
                relayPort = 43171,
                relayId = "fresh-relay",
                relaySecret = "fresh-secret",
                relayExpiresAtEpochMillis = 4_102_444_800_000L,
                relayNonce = "fresh-nonce",
                relayScope = "remote",
            ),
            RouteRefreshPayload(
                runtimeDeviceId = "r".repeat(513),
                runtimeKeyFingerprint = "runtime-fingerprint",
                relayHost = "fresh-relay.example.test",
                relayPort = 43171,
                relayId = "fresh-relay",
                relaySecret = "fresh-secret",
                relayExpiresAtEpochMillis = 4_102_444_800_000L,
                relayNonce = "fresh-nonce",
                relayScope = "remote",
            ),
            RouteRefreshPayload(
                runtimeDeviceId = "runtime-1",
                runtimeKeyFingerprint = "f".repeat(513),
                relayHost = "fresh-relay.example.test",
                relayPort = 43171,
                relayId = "fresh-relay",
                relaySecret = "fresh-secret",
                relayExpiresAtEpochMillis = 4_102_444_800_000L,
                relayNonce = "fresh-nonce",
                relayScope = "remote",
            ),
        ).forEach { payload ->
            assertNull(
                trustedRuntimeFromRouteRefreshPayload(
                    current = current,
                    payload = payload,
                    nowEpochMillis = 1_000L,
                ),
            )
        }
    }

    @Test
    fun expiredRouteRefreshQrIsNotSavedAsTrustedRuntimeRoute() {
        val current = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-1",
            endpointHint = null,
        )
        val payload = runtimePairingPayload(
            host = null,
            port = null,
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 1L,
            relayNonce = "nonce-route-1",
        )

        assertNull(trustedRuntimeFromRouteRefreshQr(current, payload))
    }

    @Test
    fun routeRefreshQrRejectsRelayRouteWithoutSecret() {
        val current = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-1",
            endpointHint = null,
        )
        val payload = runtimePairingPayload(
            host = null,
            port = null,
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = null,
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-1",
        )

        assertNull(trustedRuntimeFromRouteRefreshQr(current, payload))
    }

    @Test
    fun routeRefreshQrRejectsExpiredOrIncompleteP2pRoute() {
        val current = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-1",
            endpointHint = null,
        )
        val expiredOrIncompleteP2pRoutes = listOf(
            runtimePairingPayload(
                host = null,
                port = null,
                p2pRouteClass = "p2p_rendezvous",
                p2pRecordId = "p2p-record-1",
                p2pEncryptedBody = "opaque-candidate-1",
                p2pExpiresAtEpochMillis = 1L,
                p2pAntiReplayNonce = "nonce-p2p-1",
                p2pProtocolVersion = 1,
            ),
            runtimePairingPayload(
                host = null,
                port = null,
                p2pRouteClass = "p2p_rendezvous",
                p2pRecordId = "p2p-record-1",
                p2pEncryptedBody = null,
                p2pExpiresAtEpochMillis = 4102444800000L,
                p2pAntiReplayNonce = "nonce-p2p-1",
                p2pProtocolVersion = 1,
            ),
            runtimePairingPayload(
                host = null,
                port = null,
                p2pRouteClass = "p2p_rendezvous",
                p2pRecordId = "p2p-record-1",
                p2pEncryptedBody = "opaque-candidate-1",
                p2pExpiresAtEpochMillis = 4102444800000L,
                p2pAntiReplayNonce = null,
                p2pProtocolVersion = 1,
            ),
        )

        expiredOrIncompleteP2pRoutes.forEach { payload ->
            assertNull(trustedRuntimeFromRouteRefreshQr(current, payload))
        }
    }

    @Test
    fun routeRefreshQrRejectsP2pRouteWithRelayScopeOnly() {
        val current = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-1",
            endpointHint = null,
        )
        val payload = runtimePairingPayload(
            host = null,
            port = null,
            relayScope = "remote",
            p2pRouteClass = "p2p_rendezvous",
            p2pRecordId = "p2p-record-1",
            p2pEncryptedBody = "opaque-candidate-1",
            p2pExpiresAtEpochMillis = 4102444800000L,
            p2pAntiReplayNonce = "nonce-p2p-1",
            p2pProtocolVersion = 1,
        )

        assertNull(trustedRuntimeFromRouteRefreshQr(current, payload))
    }

    @Test
    fun routeRefreshQrRejectsDirectRouteForExistingTrustedRuntime() {
        val current = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-old",
            endpointHint = null,
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-old",
            relaySecret = "secret-old",
        )
        val payload = runtimePairingPayload(
            routeToken = "route-new",
            host = "192.168.219.104",
            port = 43170,
            relayHost = null,
            relayPort = null,
            relayId = null,
            relaySecret = null,
        )

        assertNull(trustedRuntimeFromRouteRefreshQr(current, payload))
    }

    @Test
    fun routeRefreshQrCanRotateRouteTokenForPinnedRuntimeIdentity() {
        val current = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-old",
            endpointHint = null,
        )
        val payload = runtimePairingPayload(
            routeToken = "route-new",
            host = null,
            port = null,
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-new",
            relaySecret = "secret-new",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-new",
        )

        val refreshed = trustedRuntimeFromRouteRefreshQr(current, payload)

        assertEquals("runtime-1", refreshed?.deviceId)
        assertEquals("route-new", refreshed?.routeToken)
        assertEquals("relay-new", refreshed?.relayId)
        assertEquals("secret-new", refreshed?.relaySecret)
        assertEquals(4102444800000L, refreshed?.relayExpiresAtEpochMillis)
        assertEquals("nonce-route-new", refreshed?.relayNonce)
    }

    @Test
    fun routeRefreshQrRejectsUntrustedOrMismatchedRuntimeIdentity() {
        val current = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-1",
            endpointHint = null,
        )

        assertNull(
            trustedRuntimeFromRouteRefreshQr(
                current = null,
                payload = runtimePairingPayload(
                    relayHost = "relay.example.test",
                    relayPort = 443,
                    relayId = "relay-1",
                    relaySecret = "secret-1",
                    relayExpiresAtEpochMillis = 4102444800000L,
                    relayNonce = "nonce-route-1",
                ),
            )
        )
        assertNull(
            trustedRuntimeFromRouteRefreshQr(
                current = current,
                payload = runtimePairingPayload(
                    runtimeDeviceId = "other-runtime",
                    relayHost = "relay.example.test",
                    relayPort = 443,
                    relayId = "relay-1",
                    relaySecret = "secret-1",
                    relayExpiresAtEpochMillis = 4102444800000L,
                    relayNonce = "nonce-route-1",
                ),
            )
        )
        assertNull(
            trustedRuntimeFromRouteRefreshQr(
                current = current,
                payload = runtimePairingPayload(
                    runtimePublicKeyBase64 = "other-public-key",
                    relayHost = "relay.example.test",
                    relayPort = 443,
                    relayId = "relay-1",
                    relaySecret = "secret-1",
                    relayExpiresAtEpochMillis = 4102444800000L,
                    relayNonce = "nonce-route-1",
                ),
            )
        )
        assertNull(
            trustedRuntimeFromRouteRefreshQr(
                current = current,
                payload = runtimePairingPayload(
                    host = null,
                    port = null,
                    relayHost = null,
                    relayPort = null,
                    relayId = null,
                    relaySecret = null,
                ),
            )
        )
    }

    @Test
    fun routeRefreshQrDropsTrustedEndpointFallbackWhenRelayRouteIsSaved() {
        val current = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-1",
            endpointHint = RuntimeEndpointHint(
                host = "192.168.219.104",
                port = 43170,
                source = RuntimeEndpointSource.TrustedLastKnown,
            ),
        )

        val refreshed = trustedRuntimeFromRouteRefreshQr(
            current = current,
            payload = runtimePairingPayload(
                host = null,
                port = null,
                relayHost = "relay.example.test",
                relayPort = 443,
                relayId = "relay-1",
                relaySecret = "secret-1",
                relayExpiresAtEpochMillis = 4102444800000L,
                relayNonce = "nonce-route-1",
            ),
        )

        assertNull(refreshed?.host)
        assertNull(refreshed?.port)
        assertEquals("relay.example.test", refreshed?.relayHost)
    }

    @Test
    fun acceptedPairingResultRejectsMismatchedRuntimeIdentity() {
        val pending = runtimePairingPayload()

        assertNull(
            trustedRuntimeFromAcceptedPairing(
                pending = pending,
                payload = PairingResultPayload(
                    accepted = true,
                    runtimeDeviceIdV2 = "other-runtime",
                    runtimePublicKey = "runtime-public-key",
                    runtimeKeyFingerprint = "runtime-fingerprint",
                    message = "trusted",
                ),
            )
        )
        assertNull(
            trustedRuntimeFromAcceptedPairing(
                pending = pending,
                payload = PairingResultPayload(
                    accepted = true,
                    runtimeDeviceIdV2 = "runtime-1",
                    runtimePublicKey = "runtime-public-key",
                    runtimeKeyFingerprint = "other-fingerprint",
                    message = "trusted",
                ),
            )
        )
        assertNull(
            trustedRuntimeFromAcceptedPairing(
                pending = pending,
                payload = PairingResultPayload(
                    accepted = true,
                    runtimeDeviceIdV2 = "runtime-1",
                    runtimePublicKey = "other-public-key",
                    runtimeKeyFingerprint = "runtime-fingerprint",
                    message = "trusted",
                ),
            )
        )
    }

    @Test
    fun acceptedPairingResultKeepsLegacyPairingWithoutRuntimePublicKey() {
        val pending = runtimePairingPayload(runtimePublicKeyBase64 = null)
        val trusted = trustedRuntimeFromAcceptedPairing(
            pending = pending,
            payload = PairingResultPayload(
                accepted = true,
                runtimeDeviceId = "runtime-1",
                message = "trusted",
            ),
        )

        assertEquals("runtime-1", trusted?.deviceId)
        assertEquals("runtime-fingerprint", trusted?.fingerprint)
        assertNull(trusted?.publicKeyBase64)
    }

    @Test
    fun runtimeRouteCandidatesUseDiscoveredEndpointInsteadOfTrustedLastKnownFallback() {
        val staleTrustedEndpoint = RuntimeEndpointHint(
            host = "192.168.1.20",
            port = 43170,
            source = RuntimeEndpointSource.TrustedLastKnown,
        )
        val state = RuntimeUiState(
            runtimeHost = "127.0.0.1",
            runtimePort = "43170",
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "mac-1",
                name = "AetherLink Runtime",
                endpointHint = staleTrustedEndpoint,
            ),
            discoveredRuntimes = listOf(
                RuntimeDiscoveredRuntime(
                    serviceName = "AetherLink._localagentbridge._tcp.local.",
                    host = "192.168.1.44",
                    port = 43170,
                    deviceId = "mac-1",
                ),
            ),
        )
        val target = trustedRuntimeConnectionTarget(state) ?: error("Expected trusted target")

        val endpointRoutes = runtimeRouteCandidates(state, target)
            .filterIsInstance<RuntimeRouteCandidate.DirectTcp>()

        assertEquals(1, endpointRoutes.size)
        assertEquals("192.168.1.44", endpointRoutes.single().hint.host)
        assertEquals(RuntimeEndpointSource.BonjourDiscovery, endpointRoutes.single().hint.source)
        assertEquals(RuntimeRouteSource.FreshDiscovery, endpointRoutes.single().source)
    }

    @Test
    fun runtimeRouteCandidatesDoNotAutoUseMetadataLessDiscoveryForTrustedIdentity() {
        val staleTrustedEndpoint = RuntimeEndpointHint(
            host = "192.168.1.20",
            port = 43170,
            source = RuntimeEndpointSource.TrustedLastKnown,
        )
        val state = RuntimeUiState(
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "mac-1",
                name = "AetherLink Runtime",
                fingerprint = "trusted-fingerprint",
                endpointHint = staleTrustedEndpoint,
            ),
            discoveredRuntimes = listOf(
                RuntimeDiscoveredRuntime(
                    serviceName = "Metadata-less AetherLink",
                    host = "192.168.1.44",
                    port = 43170,
                ),
            ),
        )
        val target = trustedRuntimeConnectionTarget(state) ?: error("Expected trusted target")

        val endpointRoutes = runtimeRouteCandidates(state, target)
            .filterIsInstance<RuntimeRouteCandidate.DirectTcp>()

        assertTrue(endpointRoutes.isEmpty())
    }

    @Test
    fun runtimeRouteCandidatesUseDiscoveredEndpointWithMatchingIdentityMetadata() {
        val staleTrustedEndpoint = RuntimeEndpointHint(
            host = "192.168.1.20",
            port = 43170,
            source = RuntimeEndpointSource.TrustedLastKnown,
        )
        val state = RuntimeUiState(
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "mac-1",
                name = "AetherLink Runtime",
                fingerprint = "trusted-fingerprint",
                endpointHint = staleTrustedEndpoint,
            ),
            discoveredRuntimes = listOf(
                RuntimeDiscoveredRuntime(
                    serviceName = "AetherLink",
                    host = "192.168.1.44",
                    port = 43170,
                    deviceId = "mac-1",
                    fingerprint = "other-fingerprint",
                    app = "AetherLink",
                    version = "0.1.0",
                ),
                RuntimeDiscoveredRuntime(
                    serviceName = "AetherLink Fingerprint",
                    host = "192.168.1.45",
                    port = 43170,
                    deviceId = "other-mac",
                    fingerprint = "trusted-fingerprint",
                ),
            ),
        )
        val target = trustedRuntimeConnectionTarget(state) ?: error("Expected trusted target")

        val endpointRoutes = runtimeRouteCandidates(state, target)
            .filterIsInstance<RuntimeRouteCandidate.DirectTcp>()

        assertEquals(2, endpointRoutes.size)
        assertEquals("192.168.1.44", endpointRoutes[0].hint.host)
        assertEquals("192.168.1.45", endpointRoutes[1].hint.host)
    }

    @Test
    fun runtimeRouteCandidatesUseRouteTokenBeforeLegacyIdentityMetadata() {
        val state = RuntimeUiState(
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "mac-1",
                name = "AetherLink Runtime",
                fingerprint = "trusted-fingerprint",
                routeToken = "paired-route-token",
                endpointHint = null,
            ),
            discoveredRuntimes = listOf(
                RuntimeDiscoveredRuntime(
                    serviceName = "AetherLink Route Token",
                    host = "192.168.1.88",
                    port = 43170,
                    routeToken = "paired-route-token",
                    deviceId = "legacy-device-id-that-should-not-be-used",
                    fingerprint = "legacy-fingerprint-that-should-not-be-used",
                ),
            ),
        )
        val target = trustedRuntimeConnectionTarget(state) ?: error("Expected trusted target")

        val endpointRoutes = runtimeRouteCandidates(state, target)
            .filterIsInstance<RuntimeRouteCandidate.DirectTcp>()

        assertEquals(1, endpointRoutes.size)
        assertEquals("192.168.1.88", endpointRoutes.single().hint.host)
        assertEquals(RuntimeEndpointSource.BonjourDiscovery, endpointRoutes.single().hint.source)
    }

    @Test
    fun runtimeRouteCandidatesIgnoreRouteTokenMismatchEvenWhenLegacyIdentityMatches() {
        val staleTrustedEndpoint = RuntimeEndpointHint(
            host = "192.168.1.20",
            port = 43170,
            source = RuntimeEndpointSource.TrustedLastKnown,
        )
        val state = RuntimeUiState(
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "mac-1",
                name = "AetherLink Runtime",
                fingerprint = "trusted-fingerprint",
                routeToken = "trusted-route-token",
                endpointHint = staleTrustedEndpoint,
            ),
            discoveredRuntimes = listOf(
                RuntimeDiscoveredRuntime(
                    serviceName = "AetherLink Wrong Route Token",
                    host = "192.168.1.89",
                    port = 43170,
                    routeToken = "other-route-token",
                    deviceId = "mac-1",
                    fingerprint = "trusted-fingerprint",
                ),
            ),
        )
        val target = trustedRuntimeConnectionTarget(state) ?: error("Expected trusted target")

        val endpointRoutes = runtimeRouteCandidates(state, target)
            .filterIsInstance<RuntimeRouteCandidate.DirectTcp>()

        assertTrue(endpointRoutes.isEmpty())
    }

    @Test
    fun runtimeRouteCandidatesRejectUnpinnedDiscoveryRouteTokenEvenWhenLegacyIdentityMatches() {
        val state = RuntimeUiState(
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "mac-legacy",
                name = "AetherLink Runtime",
                fingerprint = "trusted-fingerprint",
                routeToken = null,
                endpointHint = null,
            ),
            discoveredRuntimes = listOf(
                RuntimeDiscoveredRuntime(
                    serviceName = "AetherLink Unpinned Route Token",
                    host = "192.168.1.90",
                    port = 43170,
                    routeToken = "advertised-route-token",
                    deviceId = "mac-legacy",
                    fingerprint = "trusted-fingerprint",
                ),
            ),
        )
        val target = trustedRuntimeConnectionTarget(state) ?: error("Expected trusted target")

        val endpointRoutes = runtimeRouteCandidates(state, target)
            .filterIsInstance<RuntimeRouteCandidate.DirectTcp>()

        assertTrue(endpointRoutes.isEmpty())
    }

    @Test
    fun trustedDiscoveredRuntimeConnectionTargetRequiresMatchingDiscoveryIdentity() {
        val state = RuntimeUiState(
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "runtime-1",
                name = "AetherLink Runtime",
                routeToken = "trusted-route-token",
                endpointHint = null,
            ),
            discoveredRuntimes = listOf(
                RuntimeDiscoveredRuntime(
                    serviceName = "AetherLink Runtime",
                    host = "192.168.1.88",
                    port = 43170,
                    routeToken = "trusted-route-token",
                ),
            ),
        )

        val target = trustedDiscoveredRuntimeConnectionTarget(state)

        assertEquals("runtime-1", target?.identity?.deviceId)
        assertEquals("trusted-route-token", target?.identity?.routeToken)
        assertEquals("192.168.1.88", target?.endpointHint?.host)
        assertEquals(43170, target?.endpointHint?.port)
        assertEquals(RuntimeEndpointSource.BonjourDiscovery, target?.endpointHint?.source)
    }

    @Test
    fun trustedDiscoveredRuntimeConnectionTargetRejectsMetadataLessDiscovery() {
        val state = RuntimeUiState(
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "runtime-1",
                name = "AetherLink Runtime",
                routeToken = "trusted-route-token",
                endpointHint = null,
            ),
            discoveredRuntimes = listOf(
                RuntimeDiscoveredRuntime(
                    serviceName = "Metadata-less Runtime",
                    host = "192.168.1.88",
                    port = 43170,
                ),
            ),
        )

        assertNull(trustedDiscoveredRuntimeConnectionTarget(state))
    }

    @Test
    fun autoReconnectTrustedRuntimeTargetPrefersMatchingDiscoveredEndpoint() {
        val state = RuntimeUiState(
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "runtime-1",
                name = "AetherLink Runtime",
                routeToken = "trusted-route-token",
                endpointHint = RuntimeEndpointHint(
                    host = "192.168.1.20",
                    port = 43170,
                    source = RuntimeEndpointSource.TrustedLastKnown,
                ),
            ),
            discoveredRuntimes = listOf(
                RuntimeDiscoveredRuntime(
                    serviceName = "AetherLink Runtime",
                    host = "192.168.1.88",
                    port = 43170,
                    routeToken = "trusted-route-token",
                ),
            ),
        )

        val target = autoReconnectTrustedRuntimeConnectionTarget(state)

        assertEquals("runtime-1", target?.identity?.deviceId)
        assertEquals("192.168.1.88", target?.endpointHint?.host)
        assertEquals(RuntimeEndpointSource.BonjourDiscovery, target?.endpointHint?.source)
    }

    @Test
    fun autoReconnectTrustedRuntimeTargetWaitsForFreshRouteWhenOnlyTrustedLastKnownEndpointExists() {
        val state = RuntimeUiState(
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "runtime-1",
                name = "AetherLink Runtime",
                routeToken = "trusted-route-token",
                endpointHint = RuntimeEndpointHint(
                    host = "192.168.1.20",
                    port = 43170,
                    source = RuntimeEndpointSource.TrustedLastKnown,
                ),
            ),
        )

        val target = autoReconnectTrustedRuntimeConnectionTarget(state)

        assertNull(target)
    }

    @Test
    fun autoReconnectRouteCandidatesDoNotUseTrustedLastKnownEndpointAsFallback() {
        val state = RuntimeUiState(
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "runtime-1",
                name = "AetherLink Runtime",
                routeToken = "trusted-route-token",
                endpointHint = RuntimeEndpointHint(
                    host = "192.168.1.20",
                    port = 43170,
                    source = RuntimeEndpointSource.TrustedLastKnown,
                ),
            ),
        )

        val target = trustedRuntimeConnectionTarget(state)
            ?: error("Expected trusted runtime identity target")
        val endpointRoutes = runtimeRouteCandidates(
            state = state,
            target = target,
            includeUsbReverseFallback = false,
        ).filterIsInstance<RuntimeRouteCandidate.DirectTcp>()

        assertTrue(endpointRoutes.isEmpty())
    }

    @Test
    fun autoReconnectTrustedRuntimeTargetWaitsForRouteWhenIdentityOnly() {
        val state = RuntimeUiState(
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "runtime-1",
                name = "AetherLink Runtime",
                routeToken = "trusted-route-token",
                endpointHint = null,
            ),
        )

        assertNull(autoReconnectTrustedRuntimeConnectionTarget(state))
    }

    @Test
    fun runtimeRouteCandidatesIgnoreDiscoveredEndpointWithMismatchedIdentityMetadata() {
        val staleTrustedEndpoint = RuntimeEndpointHint(
            host = "192.168.1.20",
            port = 43170,
            source = RuntimeEndpointSource.TrustedLastKnown,
        )
        val state = RuntimeUiState(
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "mac-1",
                name = "AetherLink Runtime",
                fingerprint = "trusted-fingerprint",
                endpointHint = staleTrustedEndpoint,
            ),
            discoveredRuntimes = listOf(
                RuntimeDiscoveredRuntime(
                    serviceName = "Other AetherLink",
                    host = "192.168.1.44",
                    port = 43170,
                    deviceId = "other-mac",
                    fingerprint = "other-fingerprint",
                ),
            ),
        )
        val target = trustedRuntimeConnectionTarget(state) ?: error("Expected trusted target")

        val endpointRoutes = runtimeRouteCandidates(state, target)
            .filterIsInstance<RuntimeRouteCandidate.DirectTcp>()

        assertTrue(endpointRoutes.isEmpty())
    }

    @Test
    fun runtimeRouteCandidatesIgnoreSelectedBonjourEndpointWithMismatchedIdentityMetadata() {
        val staleTrustedEndpoint = RuntimeEndpointHint(
            host = "192.168.1.20",
            port = 43170,
            source = RuntimeEndpointSource.TrustedLastKnown,
        )
        val state = RuntimeUiState(
            runtimeHost = "192.168.1.44",
            runtimePort = "43170",
            runtimeEndpointSource = RuntimeEndpointSource.BonjourDiscovery,
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "mac-1",
                name = "AetherLink Runtime",
                fingerprint = "trusted-fingerprint",
                endpointHint = staleTrustedEndpoint,
            ),
            discoveredRuntimes = listOf(
                RuntimeDiscoveredRuntime(
                    serviceName = "Other AetherLink",
                    host = "192.168.1.44",
                    port = 43170,
                    deviceId = "other-mac",
                    fingerprint = "other-fingerprint",
                ),
            ),
        )
        val target = trustedRuntimeConnectionTarget(state) ?: error("Expected trusted target")

        val endpointRoutes = runtimeRouteCandidates(state, target)
            .filterIsInstance<RuntimeRouteCandidate.DirectTcp>()

        assertTrue(endpointRoutes.isEmpty())
    }

    @Test
    fun runtimeRouteCandidatesRejectMetadataLessSelectedBonjourEndpoint() {
        val state = RuntimeUiState(
            runtimeHost = "192.168.1.99",
            runtimePort = "43170",
            runtimeEndpointSource = RuntimeEndpointSource.BonjourDiscovery,
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "mac-1",
                name = "AetherLink Runtime",
                fingerprint = "trusted-fingerprint",
                endpointHint = null,
            ),
            discoveredRuntimes = listOf(
                RuntimeDiscoveredRuntime(
                    serviceName = "Dev AetherLink",
                    host = "192.168.1.99",
                    port = 43170,
                ),
            ),
        )
        val target = trustedRuntimeConnectionTarget(state) ?: error("Expected trusted target")

        val endpointRoutes = runtimeRouteCandidates(state, target)
            .filterIsInstance<RuntimeRouteCandidate.DirectTcp>()

        assertTrue(endpointRoutes.isEmpty())
    }

    @Test
    fun runtimeRouteCandidatesRejectDirectModelProviderPortsFromSelectedAndDiscoveredRoutes() {
        val trusted = RuntimeTrustedRuntime(
            deviceId = "mac-1",
            name = "AetherLink Runtime",
            fingerprint = "trusted-fingerprint",
            routeToken = "route-token",
            endpointHint = null,
        )
        val selectedOllamaPortState = RuntimeUiState(
            runtimeHost = "192.168.1.44",
            runtimePort = "11434",
            runtimeEndpointSource = RuntimeEndpointSource.BonjourDiscovery,
            trustedRuntime = trusted,
            discoveredRuntimes = listOf(
                RuntimeDiscoveredRuntime(
                    serviceName = "AetherLink Runtime",
                    host = "192.168.1.44",
                    port = 11434,
                    deviceId = "mac-1",
                    fingerprint = "trusted-fingerprint",
                    routeToken = "route-token",
                ),
            ),
        )
        val discoveredLmStudioPortState = RuntimeUiState(
            trustedRuntime = trusted,
            discoveredRuntimes = listOf(
                RuntimeDiscoveredRuntime(
                    serviceName = "AetherLink Runtime",
                    host = "192.168.1.45",
                    port = 1234,
                    deviceId = "mac-1",
                    fingerprint = "trusted-fingerprint",
                    routeToken = "route-token",
                ),
            ),
        )

        val selectedRoutes = runtimeRouteCandidates(
            selectedOllamaPortState,
            trustedRuntimeConnectionTarget(selectedOllamaPortState) ?: error("Expected trusted target"),
        ).filterIsInstance<RuntimeRouteCandidate.DirectTcp>()
        val discoveredRoutes = runtimeRouteCandidates(
            discoveredLmStudioPortState,
            trustedRuntimeConnectionTarget(discoveredLmStudioPortState) ?: error("Expected trusted target"),
        ).filterIsInstance<RuntimeRouteCandidate.DirectTcp>()
        val usbReverseRoutes = runtimeRouteCandidates(
            RuntimeUiState(
                runtimeHost = "127.0.0.1",
                runtimePort = "11434",
                runtimeEndpointSource = RuntimeEndpointSource.UsbReverse,
                trustedRuntime = trusted,
            ),
            RuntimeConnectionTarget(
                identity = PairedRuntimeIdentity(
                    deviceId = "mac-1",
                    name = "AetherLink Runtime",
                    fingerprint = "trusted-fingerprint",
                    routeToken = "route-token",
                ),
                endpointHint = RuntimeEndpointHint(
                    host = "127.0.0.1",
                    port = 11434,
                    source = RuntimeEndpointSource.UsbReverse,
                ),
            ),
        ).filterIsInstance<RuntimeRouteCandidate.DirectTcp>()
        val emulatorRoutes = runtimeRouteCandidates(
            RuntimeUiState(
                runtimeHost = "10.0.2.2",
                runtimePort = "1234",
                runtimeEndpointSource = RuntimeEndpointSource.Emulator,
                trustedRuntime = trusted,
            ),
            RuntimeConnectionTarget(
                identity = PairedRuntimeIdentity(
                    deviceId = "mac-1",
                    name = "AetherLink Runtime",
                    fingerprint = "trusted-fingerprint",
                    routeToken = "route-token",
                ),
                endpointHint = RuntimeEndpointHint(
                    host = "10.0.2.2",
                    port = 1234,
                    source = RuntimeEndpointSource.Emulator,
                ),
            ),
        ).filterIsInstance<RuntimeRouteCandidate.DirectTcp>()

        assertTrue(selectedRoutes.isEmpty())
        assertTrue(discoveredRoutes.isEmpty())
        assertTrue(usbReverseRoutes.isEmpty())
        assertTrue(emulatorRoutes.isEmpty())
    }

    @Test
    fun runtimeRouteCandidatesRejectSelectedBonjourEndpointMissingCurrentDiscoveryMetadata() {
        val state = RuntimeUiState(
            runtimeHost = "192.168.1.99",
            runtimePort = "43170",
            runtimeEndpointSource = RuntimeEndpointSource.BonjourDiscovery,
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "mac-1",
                name = "AetherLink Runtime",
                fingerprint = "trusted-fingerprint",
                endpointHint = null,
            ),
            discoveredRuntimes = emptyList(),
        )
        val target = trustedRuntimeConnectionTarget(state) ?: error("Expected trusted target")

        val endpointRoutes = runtimeRouteCandidates(state, target)
            .filterIsInstance<RuntimeRouteCandidate.DirectTcp>()

        assertTrue(endpointRoutes.isEmpty())
    }

    @Test
    fun runtimeRouteCandidatesPreferSelectedBonjourEndpointBeforeOtherDiscovery() {
        val staleTrustedEndpoint = RuntimeEndpointHint(
            host = "192.168.1.20",
            port = 43170,
            source = RuntimeEndpointSource.TrustedLastKnown,
        )
        val state = RuntimeUiState(
            runtimeHost = "192.168.1.99",
            runtimePort = "43170",
            runtimeEndpointSource = RuntimeEndpointSource.BonjourDiscovery,
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "mac-1",
                name = "AetherLink Runtime",
                endpointHint = staleTrustedEndpoint,
            ),
            discoveredRuntimes = listOf(
                RuntimeDiscoveredRuntime(
                    serviceName = "Other AetherLink",
                    host = "192.168.1.44",
                    port = 43170,
                    deviceId = "mac-1",
                ),
                RuntimeDiscoveredRuntime(
                    serviceName = "Selected AetherLink",
                    host = "192.168.1.99",
                    port = 43170,
                    deviceId = "mac-1",
                ),
            ),
        )
        val target = trustedRuntimeConnectionTarget(state) ?: error("Expected trusted target")

        val endpointRoutes = runtimeRouteCandidates(state, target)
            .filterIsInstance<RuntimeRouteCandidate.DirectTcp>()

        assertEquals("192.168.1.99", endpointRoutes[0].hint.host)
        assertEquals(RuntimeEndpointSource.BonjourDiscovery, endpointRoutes[0].hint.source)
        assertEquals(RuntimeRouteSource.FreshDiscovery, endpointRoutes[0].source)
        assertEquals("192.168.1.44", endpointRoutes[1].hint.host)
    }

    @Test
    fun runtimeRouteCandidatesUseExplicitUsbReverseEndpointForTrustedIdentity() {
        val state = RuntimeUiState(
            runtimeHost = "127.0.0.1",
            runtimePort = "43170",
            runtimeEndpointSource = RuntimeEndpointSource.UsbReverse,
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "mac-identity-only",
                name = "AetherLink Runtime",
                endpointHint = null,
            ),
        )
        val target = trustedRuntimeConnectionTarget(state) ?: error("Expected trusted target")

        val endpointRoutes = runtimeRouteCandidates(state, target)
            .filterIsInstance<RuntimeRouteCandidate.DirectTcp>()

        assertEquals(1, endpointRoutes.size)
        assertEquals("127.0.0.1", endpointRoutes.first().hint.host)
        assertEquals(43170, endpointRoutes.first().hint.port)
        assertEquals(RuntimeEndpointSource.UsbReverse, endpointRoutes.first().hint.source)
        assertEquals(RuntimeRouteSource.FreshDiscovery, endpointRoutes.first().source)
    }

    @Test
    fun runtimeRouteCandidatesRejectLocalModelBackendPortsFromDirectRoutes() {
        val blockedPorts = listOf(11434, 1234)
        val sources = listOf(
            RuntimeEndpointSource.Manual,
            RuntimeEndpointSource.PairingQr,
            RuntimeEndpointSource.TrustedLastKnown,
            RuntimeEndpointSource.BonjourDiscovery,
        )

        blockedPorts.forEach { blockedPort ->
            sources.forEach { source ->
                val target = RuntimeConnectionTarget(
                    identity = null,
                    endpointHint = RuntimeEndpointHint(
                        host = "127.0.0.1",
                        port = blockedPort,
                        source = source,
                    ),
                )

                val routes = runtimeRouteCandidates(RuntimeUiState(), target)

                assertTrue(routes.filterIsInstance<RuntimeRouteCandidate.DirectTcp>().isEmpty())
            }
        }
    }

    @Test
    fun runtimeRouteCandidatesAllowManualAetherLinkRuntimePort() {
        val target = RuntimeConnectionTarget(
            identity = null,
            endpointHint = RuntimeEndpointHint(
                host = "127.0.0.1",
                port = 43170,
                source = RuntimeEndpointSource.Manual,
            ),
        )

        val routes = runtimeRouteCandidates(RuntimeUiState(), target)
            .filterIsInstance<RuntimeRouteCandidate.DirectTcp>()

        assertEquals(1, routes.size)
        assertEquals(43170, routes.single().hint.port)
        assertEquals(RuntimeRouteSource.Manual, routes.single().source)
    }

    @Test
    fun runtimeRouteCandidatesAddDebugUsbReverseFallbackForTrustedIdentity() {
        val staleTrustedEndpoint = RuntimeEndpointHint(
            host = "192.168.219.104",
            port = 43170,
            source = RuntimeEndpointSource.TrustedLastKnown,
        )
        val state = RuntimeUiState(
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "mac-identity",
                name = "AetherLink Runtime",
                endpointHint = staleTrustedEndpoint,
            ),
        )
        val target = trustedRuntimeConnectionTarget(state) ?: error("Expected trusted target")

        val endpointRoutes = runtimeRouteCandidates(
            state = state,
            target = target,
            includeUsbReverseFallback = true,
        ).filterIsInstance<RuntimeRouteCandidate.DirectTcp>()

        assertEquals("127.0.0.1", endpointRoutes[0].hint.host)
        assertEquals(RuntimeEndpointSource.UsbReverse, endpointRoutes[0].hint.source)
    }

    @Test
    fun runtimeRouteCandidatesDoNotAddUsbReverseFallbackUnlessExplicitlyRequested() {
        val state = RuntimeUiState(
            runtimeEndpointSource = RuntimeEndpointSource.Manual,
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "mac-identity",
                name = "AetherLink Runtime",
                endpointHint = null,
            ),
        )
        val target = trustedRuntimeConnectionTarget(state) ?: error("Expected trusted target")

        val endpointRoutes = runtimeRouteCandidates(
            state = state,
            target = target,
            includeUsbReverseFallback = false,
        ).filterIsInstance<RuntimeRouteCandidate.DirectTcp>()

        assertEquals(emptyList<RuntimeRouteCandidate.DirectTcp>(), endpointRoutes)
    }

    @Test
    fun runtimeRouteCandidatesOmitDirectEndpointsWhenRelayRouteIsSaved() {
        val state = RuntimeUiState(
            runtimeHost = "192.168.1.20",
            runtimePort = "43170",
            runtimeEndpointSource = RuntimeEndpointSource.PairingQr,
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "runtime-relay",
                name = "AetherLink Runtime",
                fingerprint = "fingerprint",
                endpointHint = RuntimeEndpointHint(
                    host = "192.168.1.20",
                    port = 43170,
                    source = RuntimeEndpointSource.TrustedLastKnown,
                ),
                relayHost = "relay.example.test",
                relayPort = 443,
                relayId = "relay-1",
                relaySecret = "secret-1",
                relayExpiresAtEpochMillis = 4102444800000L,
                relayNonce = "nonce-route-1",
            ),
        )
        val target = trustedRuntimeConnectionTarget(state) ?: error("Expected trusted target")

        val endpointRoutes = runtimeRouteCandidates(
            state = state,
            target = target,
            includeUsbReverseFallback = true,
        ).filterIsInstance<RuntimeRouteCandidate.DirectTcp>()

        assertTrue(endpointRoutes.isEmpty())
    }

    @Test
    fun runtimeRouteCandidatesSuppressDirectRoutesDuringRelayQrPairing() {
        val identity = PairedRuntimeIdentity(
            deviceId = "runtime-relay",
            name = "AetherLink Runtime",
            fingerprint = "fingerprint",
            routeToken = "route-token",
        )
        val state = RuntimeUiState(
            runtimeHost = "192.168.1.20",
            runtimePort = "43170",
            runtimeEndpointSource = RuntimeEndpointSource.PairingQr,
            discoveredRuntimes = listOf(
                RuntimeDiscoveredRuntime(
                    serviceName = "AetherLink Runtime",
                    host = "192.168.1.44",
                    port = 43170,
                    routeToken = "route-token",
                ),
            ),
        )
        val target = RuntimeConnectionTarget(
            identity = identity,
            endpointHint = RuntimeEndpointHint(
                host = "192.168.1.55",
                port = 43170,
                source = RuntimeEndpointSource.PairingQr,
            ),
        )

        val routes = runtimeRouteCandidates(
            state = state,
            target = target,
            includeUsbReverseFallback = true,
            suppressDirectRoutes = true,
        )

        assertTrue(routes.filterIsInstance<RuntimeRouteCandidate.DirectTcp>().isEmpty())
        assertTrue(routes.any { it is RuntimeRouteCandidate.Relay })
    }

    @Test
    fun activeRouteKindTracksConnectedRouteType() {
        val identity = PairedRuntimeIdentity(
            deviceId = "mac-identity",
            name = "AetherLink Runtime",
        )

        assertEquals(
            RuntimeActiveRouteKind.DirectTcp,
            RuntimeRouteCandidate.DirectTcp(
                hint = RuntimeEndpointHint(
                    host = "192.168.1.20",
                    port = 43170,
                    source = RuntimeEndpointSource.BonjourDiscovery,
                )
            ).activeRouteKind(),
        )
        assertEquals(
            RuntimeActiveRouteKind.PeerToPeer,
            RuntimeRouteCandidate.PeerToPeer(identity).activeRouteKind(),
        )
        assertEquals(
            RuntimeActiveRouteKind.Relay,
            RuntimeRouteCandidate.Relay(identity).activeRouteKind(),
        )
    }

    @Test
    fun identityOnlyTrustedRuntimeWithoutDiscoveredEndpointReturnsNoConnectableRoute() {
        val state = RuntimeUiState(
            runtimeHost = "127.0.0.1",
            runtimePort = "43170",
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = "mac-identity-only",
                name = "AetherLink Runtime",
                endpointHint = null,
            ),
            discoveredRuntimes = emptyList(),
        )
        val target = trustedRuntimeConnectionTarget(state) ?: error("Expected trusted target")
        val calls = mutableListOf<Pair<String, Int>>()
        val manager = RuntimeConnectionManager(
            connector = RuntimeTransportConnector { host, port, _ ->
                calls += host to port
                TestRuntimeProtocolChannel
            },
            routeResolver = RuntimeRouteResolver { runtimeRouteCandidates(state, it) },
        )

        val failure = assertThrows(RuntimeConnectionFailure::class.java) {
            runBlocking { manager.connect(target) }
        }

        assertEquals(RuntimeConnectionFailureReason.NoConnectableRoute, failure.reason)
        assertTrue(failure.routes.any { it is RuntimeRouteCandidate.LocalDirect })
        assertTrue(failure.routes.any { it is RuntimeRouteCandidate.PeerToPeer })
        assertTrue(failure.routes.any { it is RuntimeRouteCandidate.Relay })
        assertEquals(emptyList<Pair<String, Int>>(), calls)
    }

    @Test
    fun runtimeConnectionFailureMapsRouteMissingReasonsToFocusedUiErrors() {
        val identityOnlyTarget = RuntimeConnectionTarget(
            identity = PairedRuntimeIdentity(
                deviceId = "mac-identity-only",
                name = "AetherLink Runtime",
            ),
            endpointHint = null,
        )
        val identity = identityOnlyTarget.identity ?: error("Expected identity")
        val mismatchedIdentity = PairedRuntimeIdentity(
            deviceId = "different-runtime",
            name = "Different Runtime",
        )
        val preparedPeerToPeerRoute = RuntimeRouteCandidate.PeerToPeer(
            identity = identity,
            preparedRoute = PreparedRemoteRuntimeRoute.PeerToPeer(
                identity = identity,
                sessionId = "p2p-record-1",
                encryptedCandidateMaterial = "opaque-candidate-material-1",
                security = RemoteRouteSecurityContext(
                    rendezvousToken = "p2p-token-1",
                    expiresAtEpochMillis = 4_102_444_800_000L,
                    antiReplayNonce = "p2p-nonce-1",
                ),
            ),
        )

        val noRoute = RuntimeConnectionFailure(
            reason = RuntimeConnectionFailureReason.NoRoutesResolved,
            target = identityOnlyTarget,
            routes = emptyList(),
        ).toRuntimeUiError()
        val noConnectableRoute = RuntimeConnectionFailure(
            reason = RuntimeConnectionFailureReason.NoConnectableRoute,
            target = identityOnlyTarget,
            routes = emptyList(),
        ).toRuntimeUiError()
        val remoteRoutesUnavailable = RuntimeConnectionFailure(
            reason = RuntimeConnectionFailureReason.NoConnectableRoute,
            target = identityOnlyTarget,
            routes = listOf(
                RuntimeRouteCandidate.LocalDirect(identity),
                RuntimeRouteCandidate.PeerToPeer(identity),
                RuntimeRouteCandidate.Relay(identity),
            ),
            routeRejections = listOf(
                RuntimeRouteRejection(
                    route = RuntimeRouteCandidate.LocalDirect(identity),
                    capability = RuntimeRouteCapability.DirectTcp,
                    reason = RuntimeRouteRejectionReason.DirectTcpEndpointNotPrepared,
                ),
                RuntimeRouteRejection(
                    route = RuntimeRouteCandidate.PeerToPeer(identity),
                    capability = RuntimeRouteCapability.PeerToPeer,
                    reason = RuntimeRouteRejectionReason.PeerToPeerConnectorNotAvailable,
                ),
                RuntimeRouteRejection(
                    route = RuntimeRouteCandidate.Relay(identity),
                    capability = RuntimeRouteCapability.Relay,
                    reason = RuntimeRouteRejectionReason.RelayConnectorNotAvailable,
                ),
            ),
        ).toRuntimeUiError()
        val relayRouteFailed = RuntimeConnectionFailure(
            reason = RuntimeConnectionFailureReason.RouteAttemptsFailed,
            target = identityOnlyTarget,
            routes = listOf(RuntimeRouteCandidate.Relay(identity)),
            attemptFailures = listOf(
                RuntimeRouteAttemptFailure(
                    route = RuntimeRouteCandidate.Relay(identity),
                    cause = IllegalStateException("Relay did not accept route"),
                )
            ),
        ).toRuntimeUiError()
        val peerToPeerFailedWithoutRelay = RuntimeConnectionFailure(
            reason = RuntimeConnectionFailureReason.RouteAttemptsFailed,
            target = identityOnlyTarget,
            routes = listOf(
                preparedPeerToPeerRoute,
                RuntimeRouteCandidate.Relay(identity),
            ),
            routeRejections = listOf(
                RuntimeRouteRejection(
                    route = RuntimeRouteCandidate.Relay(identity),
                    capability = RuntimeRouteCapability.Relay,
                    reason = RuntimeRouteRejectionReason.RelayConnectorNotAvailable,
                ),
            ),
            attemptFailures = listOf(
                RuntimeRouteAttemptFailure(
                    route = preparedPeerToPeerRoute,
                    cause = IllegalStateException("P2P rendezvous route did not establish a session"),
                )
            ),
        ).toRuntimeUiError()
        val expiredRemoteRoute = RuntimeConnectionFailure(
            reason = RuntimeConnectionFailureReason.NoConnectableRoute,
            target = identityOnlyTarget,
            routes = listOf(RuntimeRouteCandidate.Relay(identity)),
            routeRejections = listOf(
                RuntimeRouteRejection(
                    route = RuntimeRouteCandidate.Relay(identity),
                    capability = RuntimeRouteCapability.Relay,
                    reason = RuntimeRouteRejectionReason.RemoteRouteExpired,
                ),
            ),
        ).toRuntimeUiError()
        val mismatchedRemoteRoute = RuntimeConnectionFailure(
            reason = RuntimeConnectionFailureReason.NoConnectableRoute,
            target = identityOnlyTarget,
            routes = listOf(
                RuntimeRouteCandidate.Relay(
                    identity = identity,
                    preparedRoute = PreparedRemoteRuntimeRoute.Relay(
                        identity = mismatchedIdentity,
                        relayId = "mismatched-relay",
                        host = "relay.example.test",
                        port = 443,
                        relayFrameSecret = "mismatched-secret",
                        security = RemoteRouteSecurityContext(
                            rendezvousToken = "mismatched-token",
                            expiresAtEpochMillis = 4_102_444_800_000L,
                            antiReplayNonce = "mismatched-nonce",
                        ),
                    ),
                ),
            ),
            routeRejections = listOf(
                RuntimeRouteRejection(
                    route = RuntimeRouteCandidate.Relay(identity),
                    capability = RuntimeRouteCapability.Relay,
                    reason = RuntimeRouteRejectionReason.RemoteRouteIdentityMismatch,
                ),
            ),
        ).toRuntimeUiError()
        val remoteOnlyUnavailable = RuntimeConnectionFailure(
            reason = RuntimeConnectionFailureReason.NoConnectableRoute,
            target = identityOnlyTarget,
            routes = listOf(
                RuntimeRouteCandidate.PeerToPeer(identity),
                RuntimeRouteCandidate.Relay(identity),
            ),
            routeRejections = listOf(
                RuntimeRouteRejection(
                    route = RuntimeRouteCandidate.PeerToPeer(identity),
                    capability = RuntimeRouteCapability.PeerToPeer,
                    reason = RuntimeRouteRejectionReason.PeerToPeerConnectorNotAvailable,
                ),
                RuntimeRouteRejection(
                    route = RuntimeRouteCandidate.Relay(identity),
                    capability = RuntimeRouteCapability.Relay,
                    reason = RuntimeRouteRejectionReason.RelayConnectorNotAvailable,
                ),
            ),
        ).toRuntimeUiError()

        assertEquals("no_route", noRoute.code)
        assertEquals("no_connectable_route", noConnectableRoute.code)
        assertNull(noConnectableRoute.diagnosticCode)
        assertNull(remoteRoutesUnavailable.detail)
        assertEquals("No connectable runtime route resolved for target", remoteRoutesUnavailable.technicalDetail)
        assertEquals("remote_routes_unavailable", remoteRoutesUnavailable.code)
        assertEquals(
            "route_diagnostic_local_missing_remote_pending",
            remoteRoutesUnavailable.diagnosticCode,
        )
        assertNull(relayRouteFailed.detail)
        assertEquals("All connectable runtime routes failed", relayRouteFailed.technicalDetail)
        assertEquals("remote_route_unreachable", relayRouteFailed.code)
        assertEquals("route_diagnostic_relay_failed", relayRouteFailed.diagnosticCode)
        assertNull(peerToPeerFailedWithoutRelay.detail)
        assertEquals("All connectable runtime routes failed", peerToPeerFailedWithoutRelay.technicalDetail)
        assertEquals("remote_route_unreachable", peerToPeerFailedWithoutRelay.code)
        assertEquals(
            "route_diagnostic_p2p_failed_relay_pending",
            peerToPeerFailedWithoutRelay.diagnosticCode,
        )
        assertNull(expiredRemoteRoute.detail)
        assertEquals("No connectable runtime route resolved for target", expiredRemoteRoute.technicalDetail)
        assertEquals("remote_route_expired", expiredRemoteRoute.code)
        assertEquals(
            "route_diagnostic_remote_route_expired",
            expiredRemoteRoute.diagnosticCode,
        )
        assertNull(mismatchedRemoteRoute.detail)
        assertEquals("No connectable runtime route resolved for target", mismatchedRemoteRoute.technicalDetail)
        assertEquals("remote_routes_unavailable", mismatchedRemoteRoute.code)
        assertEquals(
            "route_diagnostic_remote_identity_mismatch",
            mismatchedRemoteRoute.diagnosticCode,
        )
        assertNull(remoteOnlyUnavailable.detail)
        assertEquals("No connectable runtime route resolved for target", remoteOnlyUnavailable.technicalDetail)
        assertEquals("remote_routes_unavailable", remoteOnlyUnavailable.code)
        assertEquals("route_diagnostic_remote_pending", remoteOnlyUnavailable.diagnosticCode)
    }

    @Test
    fun runtimeProviderStatusesPreserveSafeBackendDetails() {
        val payload = RuntimeHealthPayload(
            status = "ok",
            ollama = RuntimeBackendStatusPayload(
                available = true,
                message = "Ollama is reachable through AetherLink Runtime",
            ),
            lmStudio = RuntimeBackendStatusPayload(
                available = false,
                message = "LM Studio is not reachable through AetherLink Runtime",
                code = "backend_unavailable",
                retryable = true,
            ),
        )

        val statuses = runtimeProviderStatuses(payload)

        assertEquals(2, statuses.size)
        assertEquals(RuntimeProviderStatus("ollama", "Ollama", true, "Ollama is reachable through AetherLink Runtime"), statuses[0])
        assertEquals(
            RuntimeProviderStatus(
                id = "lm_studio",
                name = "LM Studio",
                available = false,
                message = "LM Studio is not reachable through AetherLink Runtime",
                code = "backend_unavailable",
                retryable = true,
            ),
            statuses[1],
        )
    }

    @Test
    fun runtimeProviderStatusesRedactBackendEndpointDetails() {
        val payload = RuntimeHealthPayload(
            status = "degraded",
            ollama = RuntimeBackendStatusPayload(
                available = false,
                message = "Ollama returned http://127.0.0.1:11434/api/tags",
                code = "backend_unavailable",
                retryable = true,
            ),
            lmStudio = RuntimeBackendStatusPayload(
                available = false,
                message = "LM Studio failed at localhost:1234/v1/models",
                code = "backend_unavailable",
                retryable = true,
            ),
        )

        val statuses = runtimeProviderStatuses(payload)

        assertEquals(2, statuses.size)
        assertEquals("", statuses[0].message)
        assertEquals("", statuses[1].message)
        assertEquals("backend_unavailable", statuses[0].code)
        assertEquals("backend_unavailable", statuses[1].code)
    }

    @Test
    fun runtimeProviderStatusesRedactRouteSecretDetails() {
        val payload = RuntimeHealthPayload(
            status = "degraded",
            ollama = RuntimeBackendStatusPayload(
                available = false,
                message = "Route refresh failed route_token=route-secret-token",
                code = "relay_secret=relay-secret-value",
                retryable = true,
            ),
            lmStudio = RuntimeBackendStatusPayload(
                available = false,
                message = "{\"routeToken\":\"camel-route-token\",\"relaySecret\":\"camel-relay-secret\"}",
                code = "backend unavailable",
                retryable = true,
            ),
        )

        val statuses = runtimeProviderStatuses(payload)

        assertEquals(2, statuses.size)
        assertEquals("", statuses[0].message)
        assertEquals("", statuses[1].message)
        assertNull(statuses[0].code)
        assertNull(statuses[1].code)
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun runtimeHealthRejectsUnknownMetadataBeforeRuntimeStatePublication() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val selectedModel = textChatModel()
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(selectedModel),
                selectedModelId = selectedModel.id,
            )

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.ChatSessionsList,
                    serializer = ChatSessionsListResultPayload.serializer(),
                    payload = ChatSessionsListResultPayload(sessions = emptyList()),
                    requestId = fixture.channel.sentEnvelopes.last { it.type == MessageType.ChatSessionsList }.requestId,
                ),
            )
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.MemoryList,
                    serializer = MemoryListResultPayload.serializer(),
                    payload = MemoryListResultPayload(entries = emptyList()),
                    requestId = fixture.channel.sentEnvelopes.last { it.type == MessageType.MemoryList }.requestId,
                ),
            )
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.MemorySummaryDraftsList,
                    serializer = MemorySummaryDraftsListResultPayload.serializer(),
                    payload = MemorySummaryDraftsListResultPayload(drafts = emptyList()),
                    requestId = fixture.channel.sentEnvelopes.last { it.type == MessageType.MemorySummaryDraftsList }.requestId,
                ),
            )
            advanceUntilIdle()

            val initialState = fixture.viewModel.state.value
            val initialRuntimeStatus = initialState.runtimeStatus
            val initialBackendAvailable = initialState.backendAvailable
            val initialBackendCode = initialState.backendCode
            val initialProviderStatuses = initialState.providerStatuses
            val initialModelResidency = initialState.modelResidency
            val initialModelsListRequests = fixture.channel.sentEnvelopes.count { it.type == MessageType.ModelsList }
            val initialChatSessionsListRequests = fixture.channel.sentEnvelopes.count { it.type == MessageType.ChatSessionsList }
            val initialMemoryListRequests = fixture.channel.sentEnvelopes.count { it.type == MessageType.MemoryList }
            val initialMemorySummaryDraftsListRequests = fixture.channel.sentEnvelopes.count {
                it.type == MessageType.MemorySummaryDraftsList
            }

            fun assertRuntimeHealthStateUnchanged() {
                val state = fixture.viewModel.state.value
                assertEquals(initialRuntimeStatus, state.runtimeStatus)
                assertEquals(initialBackendAvailable, state.backendAvailable)
                assertEquals(initialBackendCode, state.backendCode)
                assertEquals(initialProviderStatuses, state.providerStatuses)
                assertEquals(initialModelResidency, state.modelResidency)
                assertEquals(initialModelsListRequests, fixture.channel.sentEnvelopes.count { it.type == MessageType.ModelsList })
                assertEquals(
                    initialChatSessionsListRequests,
                    fixture.channel.sentEnvelopes.count { it.type == MessageType.ChatSessionsList },
                )
                assertEquals(initialMemoryListRequests, fixture.channel.sentEnvelopes.count { it.type == MessageType.MemoryList })
                assertEquals(
                    initialMemorySummaryDraftsListRequests,
                    fixture.channel.sentEnvelopes.count { it.type == MessageType.MemorySummaryDraftsList },
                )
            }

            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.RuntimeHealth,
                    requestId = "runtime-health-unknown-top-level",
                    payload = json.parseToJsonElement(
                        """
                            {
                              "status": "ok",
                              "backend_url": "http://127.0.0.1:11434"
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val rejectedTopLevelState = fixture.viewModel.state.value
            assertEquals("invalid_payload", rejectedTopLevelState.error?.code)
            assertTrue(rejectedTopLevelState.error?.technicalDetail.orEmpty().contains("runtime.health"))
            assertTrue(rejectedTopLevelState.error?.technicalDetail.orEmpty().contains("backend_url"))
            assertRuntimeHealthStateUnchanged()

            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.RuntimeHealth,
                    requestId = "runtime-health-unknown-provider",
                    payload = json.parseToJsonElement(
                        """
                            {
                              "status": "ok",
                              "ollama": {
                                "available": true,
                                "provider_url": "http://127.0.0.1:11434"
                              }
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val rejectedProviderState = fixture.viewModel.state.value
            assertEquals("invalid_payload", rejectedProviderState.error?.code)
            assertTrue(rejectedProviderState.error?.technicalDetail.orEmpty().contains("runtime.health"))
            assertTrue(rejectedProviderState.error?.technicalDetail.orEmpty().contains("ollama.provider_url"))
            assertRuntimeHealthStateUnchanged()

            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.RuntimeHealth,
                    requestId = "runtime-health-unknown-residency",
                    payload = json.parseToJsonElement(
                        """
                            {
                              "status": "ok",
                              "model_residency": {
                                "supported": true,
                                "in_flight_generations": 0,
                                "workspace_id": "local-workspace"
                              }
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val rejectedResidencyState = fixture.viewModel.state.value
            assertEquals("invalid_payload", rejectedResidencyState.error?.code)
            assertTrue(rejectedResidencyState.error?.technicalDetail.orEmpty().contains("runtime.health"))
            assertTrue(rejectedResidencyState.error?.technicalDetail.orEmpty().contains("model_residency.workspace_id"))
            assertRuntimeHealthStateUnchanged()

            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.RuntimeHealth,
                    requestId = "runtime-health-unknown-residency-failure",
                    payload = json.parseToJsonElement(
                        """
                            {
                              "status": "ok",
                              "model_residency": {
                                "supported": true,
                                "in_flight_generations": 0,
                                "last_unload_failure": {
                                  "provider": "ollama",
                                  "model_id": "llama3.1:8b",
                                  "reason": "manual",
                                  "backend_url": "http://127.0.0.1:11434"
                                }
                              }
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val rejectedNestedState = fixture.viewModel.state.value
            assertEquals("invalid_payload", rejectedNestedState.error?.code)
            assertTrue(rejectedNestedState.error?.technicalDetail.orEmpty().contains("runtime.health"))
            assertTrue(
                rejectedNestedState.error?.technicalDetail.orEmpty()
                    .contains("model_residency.last_unload_failure.backend_url"),
            )
            assertRuntimeHealthStateUnchanged()

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.RuntimeHealth,
                    serializer = RuntimeHealthPayload.serializer(),
                    payload = RuntimeHealthPayload(
                        status = "degraded",
                        ollama = RuntimeBackendStatusPayload(
                            available = false,
                            message = "Provider unavailable",
                            code = "backend_unavailable",
                            retryable = true,
                        ),
                        modelResidency = RuntimeModelResidencyPayload(
                            supported = true,
                            activeProvider = "ollama",
                            activeModelId = "llama3.1:8b",
                            inFlightGenerations = 1,
                            idleUnloadDelaySeconds = 60,
                        ),
                    ),
                    requestId = "runtime-health-canonical-retry",
                ),
            )
            advanceUntilIdle()

            val retryState = fixture.viewModel.state.value
            assertEquals("degraded", retryState.runtimeStatus)
            assertEquals(false, retryState.backendAvailable)
            assertEquals("backend_unavailable", retryState.backendCode)
            assertEquals(1, retryState.providerStatuses.size)
            assertEquals("ollama", retryState.providerStatuses.single().id)
            assertEquals(false, retryState.providerStatuses.single().available)
            assertEquals("Provider unavailable", retryState.providerStatuses.single().message)
            assertEquals("backend_unavailable", retryState.providerStatuses.single().code)
            assertEquals(true, retryState.providerStatuses.single().retryable)
            val residency = requireNotNull(retryState.modelResidency)
            assertTrue(residency.supported)
            assertEquals("ollama", residency.activeProvider)
            assertEquals("llama3.1:8b", residency.activeModelId)
            assertEquals(1, residency.inFlightGenerations)
            assertEquals(60, residency.idleUnloadDelaySeconds)
            assertNull(retryState.error)
            assertEquals(initialModelsListRequests + 1, fixture.channel.sentEnvelopes.count { it.type == MessageType.ModelsList })
            assertEquals(
                initialChatSessionsListRequests + 1,
                fixture.channel.sentEnvelopes.count { it.type == MessageType.ChatSessionsList },
            )
            assertEquals(initialMemoryListRequests + 1, fixture.channel.sentEnvelopes.count { it.type == MessageType.MemoryList })
            assertEquals(
                initialMemorySummaryDraftsListRequests + 1,
                fixture.channel.sentEnvelopes.count { it.type == MessageType.MemorySummaryDraftsList },
            )
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun runtimeHealthStoresModelResidencySnapshotFromAggregateRuntime() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val selectedModel = textChatModel()
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(selectedModel),
                selectedModelId = selectedModel.id,
            )

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.RuntimeHealth,
                    serializer = RuntimeHealthPayload.serializer(),
                    payload = RuntimeHealthPayload(
                        status = "ok",
                        modelResidency = RuntimeModelResidencyPayload(
                            supported = true,
                            activeProvider = "ollama",
                            activeModelId = "llama3.1:8b",
                            inFlightGenerations = 2,
                            idleUnloadDelaySeconds = 600,
                            lastUnloadFailure = RuntimeModelResidencyUnloadFailurePayload(
                                provider = "ollama",
                                modelId = "llama3.1:8b",
                                reason = "manual",
                            ),
                        ),
                    ),
                    requestId = "runtime-health-residency",
                ),
            )
            advanceUntilIdle()

            val residency = requireNotNull(fixture.viewModel.state.value.modelResidency)
            assertTrue(residency.supported)
            assertEquals("ollama", residency.activeProvider)
            assertEquals("llama3.1:8b", residency.activeModelId)
            assertEquals(2, residency.inFlightGenerations)
            assertEquals(600, residency.idleUnloadDelaySeconds)
            assertEquals("ollama", residency.lastUnloadFailure?.provider)
            assertEquals("llama3.1:8b", residency.lastUnloadFailure?.modelId)
            assertEquals("manual", residency.lastUnloadFailure?.reason)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @Test
    fun runtimeModelResidencyStatusRedactsUnsafeSnapshotDetails() {
        val payload = RuntimeHealthPayload(
            status = "ok",
            modelResidency = RuntimeModelResidencyPayload(
                supported = true,
                activeProvider = "http://127.0.0.1:11434",
                activeModelId = "llama3.1:8b route_token=secret",
                inFlightGenerations = 2,
                idleUnloadDelaySeconds = 600,
                lastUnloadFailure = RuntimeModelResidencyUnloadFailurePayload(
                    provider = "http://127.0.0.1:11434",
                    modelId = "qwen-local relay_secret=secret",
                    reason = "idle_timeout route_token=secret",
                ),
            ),
        )

        val residency = requireNotNull(runtimeModelResidencyStatus(payload))

        assertTrue(residency.supported)
        assertNull(residency.activeProvider)
        assertNull(residency.activeModelId)
        assertEquals(2, residency.inFlightGenerations)
        assertEquals(600, residency.idleUnloadDelaySeconds)
        assertNull(residency.lastUnloadFailure)
    }

    @Test
    fun runtimeProviderSafeMessageTreatsMissingAndUnsafeMessagesAsEmpty() {
        assertEquals("", runtimeProviderSafeMessage(null))
        assertEquals("", runtimeProviderSafeMessage("   "))
        assertEquals("Provider is reachable", runtimeProviderSafeMessage(" Provider is reachable "))
        assertEquals("", runtimeProviderSafeMessage("http://127.0.0.1:11434/api/tags"))
        assertEquals("", runtimeProviderSafeMessage("route_token=route-secret-token"))
        assertEquals("", runtimeProviderSafeMessage("relay_secret=relay-secret-value"))
    }

    @Test
    fun runtimeProviderSafeCodePreservesStructuredCodesOnly() {
        assertEquals("backend_unavailable", runtimeProviderSafeCode(" backend_unavailable "))
        assertEquals("provider.auth-required", runtimeProviderSafeCode("provider.auth-required"))
        assertNull(runtimeProviderSafeCode(null))
        assertNull(runtimeProviderSafeCode("   "))
        assertNull(runtimeProviderSafeCode("backend unavailable"))
        assertNull(runtimeProviderSafeCode("http://127.0.0.1:11434/api/tags"))
        assertNull(runtimeProviderSafeCode("route_token=route-secret-token"))
        assertNull(runtimeProviderSafeCode("relay_secret=relay-secret-value"))
        assertNull(runtimeProviderSafeCode("rt=compact-route-token"))
    }

    @Test
    fun selectedModelSendStateRequiresInstalledModelInCurrentList() {
        val ready = RuntimeUiState(
            selectedModelId = "ollama:llama3",
            models = listOf(
                RuntimeModel(
                    id = "ollama:llama3",
                    name = "Llama 3",
                    installed = true,
                ),
            ),
        )
        val notInstalled = RuntimeUiState(
            selectedModelId = "lm_studio:cloud/model",
            models = listOf(
                RuntimeModel(
                    id = "lm_studio:cloud/model",
                    name = "Cloud model",
                    installed = false,
                ),
            ),
        )
        val stale = RuntimeUiState(
            selectedModelId = "ollama:missing",
            models = listOf(
                RuntimeModel(
                    id = "ollama:llama3",
                    name = "Llama 3",
                    installed = true,
                ),
            ),
        )
        val providerManaged = RuntimeUiState(
            selectedModelId = "ollama:remote-chat",
            models = listOf(
                RuntimeModel(
                    id = "ollama:remote-chat",
                    name = "Provider managed chat",
                    installed = true,
                    source = "cloud",
                ),
            ),
        )
        val missing = RuntimeUiState()

        assertEquals(SelectedModelSendState.Ready, ready.selectedModelSendState())
        assertEquals(SelectedModelSendState.NotInstalled, notInstalled.selectedModelSendState())
        assertEquals(SelectedModelSendState.Missing, stale.selectedModelSendState())
        assertEquals(SelectedModelSendState.Missing, providerManaged.selectedModelSendState())
        assertEquals(SelectedModelSendState.Missing, missing.selectedModelSendState())
    }

    @Test
    fun selectedModelSendStateRejectsEmbeddingModelAsChatModel() {
        val state = RuntimeUiState(
            selectedModelId = "ollama:nomic-embed-text",
            models = listOf(
                RuntimeModel(
                    id = "ollama:nomic-embed-text",
                    name = "nomic-embed-text",
                    modelKind = MODEL_KIND_EMBEDDING,
                    capabilities = listOf("embedding"),
                    installed = true,
                ),
            ),
        )

        assertEquals(SelectedModelSendState.Missing, state.selectedModelSendState())
        assertTrue(state.models.single().isEmbeddingModel())
        assertFalse(state.models.single().isChatModel())
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun selectUninstalledChatModelPersistsInstallTargetAndRequestsRuntimePull() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val installedModel = textChatModel()
            val uninstalledModel = installedModel.copy(
                id = "ollama:gemma3:12b",
                name = "Gemma 3 12B",
                installed = false,
            )
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(installedModel, uninstalledModel),
                selectedModelId = installedModel.id,
            )

            fixture.viewModel.selectModel(uninstalledModel.id)
            advanceUntilIdle()

            val state = fixture.viewModel.state.value
            val pullEnvelope = fixture.channel.sentEnvelopes.last { it.type == MessageType.ModelsPull }
            val pullPayload = json.decodeFromJsonElement(ModelPullPayload.serializer(), pullEnvelope.payload)
            assertEquals(uninstalledModel.id, state.selectedModelId)
            assertEquals(uninstalledModel.id, state.installingModelId)
            assertEquals(uninstalledModel.id, fixture.localStore.data.selectedModelId)
            assertEquals(uninstalledModel.id, pullPayload.model)
            assertEquals(SelectedModelSendState.NotInstalled, state.selectedModelSendState())
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun modelPullResultRejectsUnknownMetadataBeforeInstallStateMutation() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val installedModel = textChatModel()
            val uninstalledModel = installedModel.copy(
                id = "ollama:gemma3:12b",
                name = "Gemma 3 12B",
                installed = false,
            )
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(installedModel, uninstalledModel),
                selectedModelId = installedModel.id,
            )

            fixture.viewModel.selectModel(uninstalledModel.id)
            advanceUntilIdle()

            val pullEnvelope = fixture.channel.sentEnvelopes.last { it.type == MessageType.ModelsPull }
            val modelListRequestsBeforeResult = fixture.channel.sentEnvelopes.count {
                it.type == MessageType.ModelsList
            }
            assertEquals(pullEnvelope.requestId, fixture.viewModel.privateField<String>("pendingModelPullRequestId"))
            assertEquals(uninstalledModel.id, fixture.viewModel.state.value.installingModelId)
            assertEquals(uninstalledModel.id, fixture.viewModel.privateField<String>("modelIdToSelectAfterRefresh"))

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.ModelsPull,
                    serializer = ModelPullResultPayload.serializer(),
                    payload = ModelPullResultPayload(
                        model = uninstalledModel.id,
                        backend = "ollama",
                        provider = "ollama",
                        status = "success",
                        installed = true,
                    ),
                    requestId = "stale-model-pull-result",
                ),
            )
            advanceUntilIdle()

            val afterStaleResult = fixture.viewModel.state.value
            assertNull(afterStaleResult.error)
            assertEquals(uninstalledModel.id, afterStaleResult.installingModelId)
            assertEquals(pullEnvelope.requestId, fixture.viewModel.privateField<String>("pendingModelPullRequestId"))
            assertEquals(
                modelListRequestsBeforeResult,
                fixture.channel.sentEnvelopes.count { it.type == MessageType.ModelsList },
            )

            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.ModelsPull,
                    requestId = pullEnvelope.requestId,
                    payload = buildJsonObject {
                        put("model", uninstalledModel.id)
                        put("backend", "ollama")
                        put("provider", "ollama")
                        put("status", "success")
                        put("installed", true)
                        put("provider_url", "http://127.0.0.1:11434")
                    },
                ),
            )
            advanceUntilIdle()

            val rejectedState = fixture.viewModel.state.value
            assertEquals("invalid_payload", rejectedState.error?.code)
            assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("models.pull"))
            assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("provider_url"))
            assertEquals(uninstalledModel.id, rejectedState.installingModelId)
            assertEquals(pullEnvelope.requestId, fixture.viewModel.privateField<String>("pendingModelPullRequestId"))
            assertEquals(uninstalledModel.id, fixture.viewModel.privateField<String>("modelIdToSelectAfterRefresh"))
            assertEquals(
                modelListRequestsBeforeResult,
                fixture.channel.sentEnvelopes.count { it.type == MessageType.ModelsList },
            )
            assertFalse(json.encodeToString(fixture.localStore.data).contains("127.0.0.1:11434"))

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.ModelsPull,
                    serializer = ModelPullResultPayload.serializer(),
                    payload = ModelPullResultPayload(
                        model = uninstalledModel.id,
                        backend = "ollama",
                        provider = "ollama",
                        status = "success",
                        installed = true,
                    ),
                    requestId = pullEnvelope.requestId,
                ),
            )
            advanceUntilIdle()

            val acceptedState = fixture.viewModel.state.value
            assertNull(acceptedState.error)
            assertNull(acceptedState.installingModelId)
            assertNull(fixture.viewModel.privateField<String>("pendingModelPullRequestId"))
            assertEquals(
                modelListRequestsBeforeResult + 1,
                fixture.channel.sentEnvelopes.count { it.type == MessageType.ModelsList },
            )
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun requestModelInstallRejectsUnknownModelWithoutPersistingOrPulling() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val installedModel = textChatModel()
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(installedModel),
                selectedModelId = installedModel.id,
            )

            fixture.viewModel.requestModelInstall("ollama:missing")
            advanceUntilIdle()

            assertEquals(installedModel.id, fixture.viewModel.state.value.selectedModelId)
            assertEquals(installedModel.id, fixture.localStore.data.selectedModelId)
            assertNull(fixture.viewModel.state.value.installingModelId)
            assertEquals("select_chat_model", fixture.viewModel.state.value.error?.code)
            assertFalse(fixture.channel.sentEnvelopes.any { it.type == MessageType.ModelsPull })
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun selectModelRejectsUnknownModelWithoutPersistingOrPulling() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val installedModel = textChatModel()
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(installedModel),
                selectedModelId = installedModel.id,
            )

            fixture.viewModel.selectModel("ollama:missing")
            advanceUntilIdle()

            assertEquals(installedModel.id, fixture.viewModel.state.value.selectedModelId)
            assertEquals(installedModel.id, fixture.localStore.data.selectedModelId)
            assertNull(fixture.viewModel.state.value.installingModelId)
            assertEquals("select_chat_model", fixture.viewModel.state.value.error?.code)
            assertFalse(fixture.channel.sentEnvelopes.any { it.type == MessageType.ModelsPull })
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun streamingBlocksModelSelectionAndInstallRequests() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val selectedModel = textChatModel()
            val selectedEmbeddingModel = embeddingModel()
            val alternateEmbeddingModel = selectedEmbeddingModel.copy(
                id = "ollama:mxbai-embed-large",
                name = "mxbai-embed-large",
            )
            val alternateModel = selectedModel.copy(
                id = "ollama:qwen3:8b",
                name = "Qwen3 8B",
            )
            val uninstalledModel = selectedModel.copy(
                id = "ollama:gemma3:12b",
                name = "Gemma 3 12B",
                installed = false,
            )
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(
                    selectedModel,
                    alternateModel,
                    uninstalledModel,
                    selectedEmbeddingModel,
                    alternateEmbeddingModel,
                ),
                selectedModelId = selectedModel.id,
                selectedEmbeddingModelId = selectedEmbeddingModel.id,
            )

            fixture.viewModel.replaceStateForTest {
                it.copy(isStreaming = true, error = null)
            }

            fixture.viewModel.selectModel(alternateModel.id)
            advanceUntilIdle()

            assertEquals(selectedModel.id, fixture.viewModel.state.value.selectedModelId)
            assertEquals(selectedModel.id, fixture.localStore.data.selectedModelId)
            assertEquals("generation_in_progress", fixture.viewModel.state.value.error?.code)

            fixture.viewModel.replaceStateForTest {
                it.copy(error = null)
            }
            fixture.viewModel.requestModelInstall(uninstalledModel.id)
            advanceUntilIdle()

            assertEquals(selectedModel.id, fixture.viewModel.state.value.selectedModelId)
            assertEquals(selectedModel.id, fixture.localStore.data.selectedModelId)
            assertNull(fixture.viewModel.state.value.installingModelId)
            assertEquals("generation_in_progress", fixture.viewModel.state.value.error?.code)
            assertFalse(fixture.channel.sentEnvelopes.any { it.type == MessageType.ModelsPull })

            fixture.viewModel.replaceStateForTest {
                it.copy(error = null)
            }
            fixture.viewModel.selectEmbeddingModel(alternateEmbeddingModel.id)
            advanceUntilIdle()

            assertEquals(selectedEmbeddingModel.id, fixture.viewModel.state.value.selectedEmbeddingModelId)
            assertEquals(selectedEmbeddingModel.id, fixture.localStore.data.selectedEmbeddingModelId)
            assertEquals("generation_in_progress", fixture.viewModel.state.value.error?.code)

            fixture.viewModel.replaceStateForTest {
                it.copy(error = null)
            }
            fixture.viewModel.selectEmbeddingModel(null)
            advanceUntilIdle()

            assertEquals(selectedEmbeddingModel.id, fixture.viewModel.state.value.selectedEmbeddingModelId)
            assertEquals(selectedEmbeddingModel.id, fixture.localStore.data.selectedEmbeddingModelId)
            assertEquals("generation_in_progress", fixture.viewModel.state.value.error?.code)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun streamingBlocksReentrantChatSendRequests() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val selectedModel = textChatModel()
            val existingMessages = listOf(
                RuntimeChatMessage(
                    id = "user-active",
                    role = "user",
                    content = "First prompt",
                ),
                RuntimeChatMessage(
                    id = "assistant-active",
                    role = "assistant",
                    content = "Partial answer",
                ),
            )
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(selectedModel),
                selectedModelId = selectedModel.id,
            )
            fixture.viewModel.replaceStateForTest {
                it.copy(
                    isStreaming = true,
                    activeRequestId = "active-request",
                    activeChatSessionId = "session-active",
                    chatInput = "Second prompt",
                    messages = existingMessages,
                    error = null,
                )
            }

            fixture.viewModel.sendChatMessage()
            advanceUntilIdle()

            val state = fixture.viewModel.state.value
            assertEquals("generation_in_progress", state.error?.code)
            assertEquals("active-request", state.activeRequestId)
            assertTrue(state.isStreaming)
            assertEquals("Second prompt", state.chatInput)
            assertEquals(existingMessages, state.messages)
            assertFalse(fixture.channel.sentEnvelopes.any { it.type == MessageType.ChatSend })
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun regenerateLatestResponseExcludesOldAssistantFromPayloadAndHistory() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
            )
            fixture.viewModel.replaceStateForTest {
                it.copy(
                    activeChatSessionId = "session-regenerate",
                    messages = listOf(
                        RuntimeChatMessage(id = "u1", role = "user", content = "First prompt"),
                        RuntimeChatMessage(
                            id = "a1",
                            role = "assistant",
                            content = "First answer",
                        ),
                        RuntimeChatMessage(id = "u2", role = "user", content = "Try again"),
                        RuntimeChatMessage(
                            id = "a2",
                            role = "assistant",
                            content = "Old latest answer",
                        ),
                    ),
                )
            }

            fixture.viewModel.regenerateLatestResponse()
            advanceUntilIdle()

            val payload = fixture.channel.lastChatSendPayload()
            assertEquals(listOf("user", "assistant", "user"), payload.messages.map { it.role })
            assertEquals(listOf("First prompt", "First answer", "Try again"), payload.messages.map { it.content })
            assertFalse(payload.messages.any { it.content == "Old latest answer" })

            val state = fixture.viewModel.state.value
            assertTrue(state.isStreaming)
            assertNotNull(state.activeRequestId)
            assertEquals(listOf("First prompt", "First answer", "Try again", ""), state.messages.map { it.content })
            assertFalse(state.messages.any { it.id == "a2" })

            val savedSession = fixture.localStore.data.sessions.single { it.id == "session-regenerate" }
            assertTrue(savedSession.runtimeOwned)
            assertEquals(listOf("First prompt", "First answer", "Try again", ""), savedSession.messages.map { it.content })
            assertFalse(savedSession.messages.any { it.id == "a2" })
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun regenerateLatestResponsePreservesComposerDraftAndPendingAttachments() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
            )
            val pendingAttachment = textAttachment()
            fixture.viewModel.replaceStateForTest {
                it.copy(
                    activeChatSessionId = "session-draft",
                    chatInput = "Do not clear this draft",
                    pendingAttachments = listOf(pendingAttachment),
                    messages = listOf(
                        RuntimeChatMessage(id = "u1", role = "user", content = "Original prompt"),
                        RuntimeChatMessage(id = "a1", role = "assistant", content = "Original answer"),
                    ),
                )
            }

            fixture.viewModel.retryLatestAssistantResponse()
            advanceUntilIdle()

            val state = fixture.viewModel.state.value
            assertEquals("Do not clear this draft", state.chatInput)
            assertEquals(listOf(pendingAttachment), state.pendingAttachments)
            val payload = fixture.channel.lastChatSendPayload()
            assertEquals(listOf("user"), payload.messages.map { it.role })
            assertTrue(payload.messages.all { it.attachments.isEmpty() })
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun regenerateLatestResponseBlocksAttachmentBackedPriorPrompt() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
            )
            val messages = listOf(
                RuntimeChatMessage(
                    id = "u1",
                    role = "user",
                    content = "Summarize this file",
                    attachments = listOf(
                        RuntimeMessageAttachment(
                            id = "m-attachment",
                            type = "document",
                            name = "pairing-notes.txt",
                            mimeType = "text/plain",
                        ),
                    ),
                ),
                RuntimeChatMessage(id = "a1", role = "assistant", content = "File summary"),
            )
            fixture.viewModel.replaceStateForTest {
                it.copy(
                    activeChatSessionId = "session-attachment",
                    messages = messages,
                    chatInput = "Draft survives",
                    pendingAttachments = listOf(textAttachment()),
                    error = null,
                )
            }
            val envelopeCountBeforeRetry = fixture.channel.sentEnvelopes.size

            fixture.viewModel.regenerateLatestResponse()
            advanceUntilIdle()

            val state = fixture.viewModel.state.value
            assertEquals("regenerate_attachment_context_unavailable", state.error?.code)
            assertFalse(state.isStreaming)
            assertEquals(messages, state.messages)
            assertEquals("Draft survives", state.chatInput)
            assertEquals(1, state.pendingAttachments.size)
            assertEquals(envelopeCountBeforeRetry, fixture.channel.sentEnvelopes.size)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun reuseLatestUserMessageAsDraftCopiesLatestTextWithoutSendingOrMutatingHistory() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
            )
            val pendingAttachment = textAttachment()
            val messages = listOf(
                RuntimeChatMessage(id = "u1", role = "user", content = "Older prompt"),
                RuntimeChatMessage(id = "a1", role = "assistant", content = "Older answer"),
                RuntimeChatMessage(id = "u2", role = "user", content = "Revise this prompt"),
                RuntimeChatMessage(id = "a2", role = "assistant", content = "Latest answer"),
            )
            fixture.viewModel.replaceStateForTest {
                it.copy(
                    activeChatSessionId = "session-reuse",
                    chatInput = "Existing draft",
                    pendingAttachments = listOf(pendingAttachment),
                    messages = messages,
                    error = RuntimeUiError("send_failed"),
                )
            }
            val chatSendCountBefore = fixture.channel.sentEnvelopes.count { it.type == MessageType.ChatSend }

            fixture.viewModel.reuseLatestUserMessageAsDraft()
            advanceUntilIdle()

            val state = fixture.viewModel.state.value
            assertEquals("Revise this prompt", state.chatInput)
            assertTrue(state.pendingAttachments.isEmpty())
            assertNull(state.error)
            assertEquals(messages, state.messages)
            assertEquals("Revise this prompt", fixture.localStore.data.composerDraft)
            assertEquals(chatSendCountBefore, fixture.channel.sentEnvelopes.count { it.type == MessageType.ChatSend })
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun reuseLatestUserMessageAsDraftRejectsAttachmentBackedPromptAndPreservesDraft() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
            )
            val pendingAttachment = textAttachment()
            val messages = listOf(
                RuntimeChatMessage(
                    id = "u1",
                    role = "user",
                    content = "Summarize the attachment",
                    attachments = listOf(
                        RuntimeMessageAttachment(
                            id = "attachment-1",
                            type = "document",
                            name = "report.pdf",
                            mimeType = "application/pdf",
                        ),
                    ),
                ),
                RuntimeChatMessage(id = "a1", role = "assistant", content = "Summary"),
            )
            fixture.viewModel.replaceStateForTest {
                it.copy(
                    activeChatSessionId = "session-reuse-attachment",
                    chatInput = "Keep this draft",
                    pendingAttachments = listOf(pendingAttachment),
                    messages = messages,
                    error = null,
                )
            }
            val envelopeCountBefore = fixture.channel.sentEnvelopes.size

            fixture.viewModel.reuseLatestUserMessageAsDraft()
            advanceUntilIdle()

            val state = fixture.viewModel.state.value
            assertEquals("reuse_message_unavailable", state.error?.code)
            assertEquals("Keep this draft", state.chatInput)
            assertEquals(listOf(pendingAttachment), state.pendingAttachments)
            assertEquals(messages, state.messages)
            assertEquals(envelopeCountBefore, fixture.channel.sentEnvelopes.size)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun reuseLatestUserMessageAsDraftRejectsWhileStreamingAndPreservesDraft() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
            )
            val messages = listOf(
                RuntimeChatMessage(id = "u1", role = "user", content = "Original prompt"),
                RuntimeChatMessage(id = "a1", role = "assistant", content = ""),
            )
            fixture.viewModel.replaceStateForTest {
                it.copy(
                    activeChatSessionId = "session-reuse-streaming",
                    chatInput = "Do not replace while streaming",
                    messages = messages,
                    activeRequestId = "request-streaming",
                    isStreaming = true,
                    error = null,
                )
            }
            val envelopeCountBefore = fixture.channel.sentEnvelopes.size

            fixture.viewModel.reuseLatestUserMessageAsDraft()
            advanceUntilIdle()

            val state = fixture.viewModel.state.value
            assertEquals("generation_in_progress", state.error?.code)
            assertEquals("Do not replace while streaming", state.chatInput)
            assertEquals(messages, state.messages)
            assertTrue(state.isStreaming)
            assertEquals(envelopeCountBefore, fixture.channel.sentEnvelopes.size)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun streamingBlocksMemoryMutations() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
            )
            val memoryEntry = RuntimeMemoryEntry(
                id = "memory-active",
                content = "Keep answers concise",
                enabled = true,
                createdAtMillis = 1_000L,
                updatedAtMillis = 1_000L,
            )
            val summaryDraft = RuntimeMemorySummaryDraft(
                id = "draft-streaming",
                session = RuntimeMemorySummaryDraftSession(
                    sessionId = "runtime-session",
                    title = "Planning chat",
                    modelId = "ollama:qwen3:8b",
                    lastActivityAtMillis = 1_000L,
                    messageCount = 6,
                    inactiveSeconds = 1_209_600L,
                ),
                sourceMessageCount = 6,
                sourceRange = "visible messages 1-6 of 6",
                sourcePointers = listOf(
                    RuntimeMemorySummaryDraftSourcePointer(
                        sessionId = "runtime-session",
                        messageIndex = 1,
                        role = "user",
                        createdAtMillis = 1_000L,
                        excerpt = "Use concise summaries.",
                    ),
                ),
                summaryPreview = "Prefer concise summaries.",
            )
            fixture.viewModel.replaceStateForTest {
                it.copy(
                    isStreaming = true,
                    memoryEntries = listOf(memoryEntry),
                    memorySummaryDrafts = listOf(summaryDraft),
                    error = null,
                )
            }

            fixture.viewModel.addMemoryEntry("New memory")
            advanceUntilIdle()

            assertEquals(listOf(memoryEntry), fixture.viewModel.state.value.memoryEntries)
            assertEquals("generation_in_progress", fixture.viewModel.state.value.error?.code)

            fixture.viewModel.replaceStateForTest { it.copy(error = null) }
            fixture.viewModel.setMemoryEntryEnabled(memoryEntry.id, enabled = false)
            advanceUntilIdle()

            assertEquals(listOf(memoryEntry), fixture.viewModel.state.value.memoryEntries)
            assertEquals("generation_in_progress", fixture.viewModel.state.value.error?.code)

            fixture.viewModel.replaceStateForTest { it.copy(error = null) }
            fixture.viewModel.removeMemoryEntry(memoryEntry.id)
            advanceUntilIdle()

            assertEquals(listOf(memoryEntry), fixture.viewModel.state.value.memoryEntries)
            assertEquals("generation_in_progress", fixture.viewModel.state.value.error?.code)
            fixture.viewModel.replaceStateForTest { it.copy(error = null) }
            fixture.viewModel.approveMemorySummaryDraft(summaryDraft.id)
            advanceUntilIdle()

            assertEquals(listOf(summaryDraft), fixture.viewModel.state.value.memorySummaryDrafts)
            assertEquals("generation_in_progress", fixture.viewModel.state.value.error?.code)

            fixture.viewModel.replaceStateForTest { it.copy(error = null) }
            fixture.viewModel.dismissMemorySummaryDraft(summaryDraft.id)
            advanceUntilIdle()

            assertEquals(listOf(summaryDraft), fixture.viewModel.state.value.memorySummaryDrafts)
            assertEquals("generation_in_progress", fixture.viewModel.state.value.error?.code)
            assertFalse(fixture.channel.sentEnvelopes.any { it.type == MessageType.MemoryUpsert })
            assertFalse(fixture.channel.sentEnvelopes.any { it.type == MessageType.MemoryDelete })
            assertFalse(fixture.channel.sentEnvelopes.any { it.type == MessageType.MemorySummaryDraftApprove })
            assertFalse(fixture.channel.sentEnvelopes.any { it.type == MessageType.MemorySummaryDraftDismiss })
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun runtimeMemoryListRendersInMemoryButRedactsDeviceStorage() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.MemoryList,
                    serializer = MemoryListResultPayload.serializer(),
                    payload = MemoryListResultPayload(
                        entries = listOf(
                            MemoryEntryPayload(
                                id = "memory-runtime",
                                content = "Runtime-owned memory body",
                                enabled = true,
                                createdAt = "2026-06-25T00:00:00Z",
                                updatedAt = "2026-06-25T00:01:00Z",
                            ),
                        ),
                    ),
                    requestId = "memory-list",
                ),
            )
            advanceUntilIdle()

            assertEquals(
                listOf("Runtime-owned memory body"),
                fixture.viewModel.state.value.memoryEntries.map { it.content },
            )
            assertTrue(fixture.localStore.data.memoryEntries.isEmpty())
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun refreshRuntimeMemoryRequestsFreshListAfterPendingListCompletes() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )
            val initialMemoryListRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.MemoryList }
            val initialMemoryListCount = fixture.channel.sentEnvelopes.count { it.type == MessageType.MemoryList }

            fixture.viewModel.refreshRuntimeMemory()
            advanceUntilIdle()
            assertEquals(initialMemoryListCount, fixture.channel.sentEnvelopes.count { it.type == MessageType.MemoryList })

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.MemoryList,
                    serializer = MemoryListResultPayload.serializer(),
                    payload = MemoryListResultPayload(
                        entries = listOf(
                            MemoryEntryPayload(
                                id = "memory-before-refresh",
                                content = "Initial runtime memory",
                                enabled = true,
                                createdAt = "2026-06-25T00:00:00Z",
                                updatedAt = "2026-06-25T00:01:00Z",
                            ),
                        ),
                    ),
                    requestId = initialMemoryListRequest.requestId,
                ),
            )
            advanceUntilIdle()

            fixture.viewModel.refreshRuntimeMemory()
            advanceUntilIdle()
            val refreshMemoryListRequests = fixture.channel.sentEnvelopes.filter { it.type == MessageType.MemoryList }
            assertEquals(initialMemoryListCount + 1, refreshMemoryListRequests.size)

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.MemoryList,
                    serializer = MemoryListResultPayload.serializer(),
                    payload = MemoryListResultPayload(
                        entries = listOf(
                            MemoryEntryPayload(
                                id = "memory-after-refresh",
                                content = "Updated runtime memory",
                                enabled = false,
                                createdAt = "2026-06-25T00:02:00Z",
                                updatedAt = "2026-06-25T00:03:00Z",
                            ),
                        ),
                    ),
                    requestId = refreshMemoryListRequests.last().requestId,
                ),
            )
            advanceUntilIdle()

            assertEquals(
                listOf("Updated runtime memory"),
                fixture.viewModel.state.value.memoryEntries.map { it.content },
            )
            assertTrue(fixture.localStore.data.memoryEntries.isEmpty())
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun refreshRuntimeMemorySendsTrimmedQueryAndRedactsSearchMetadataFromDeviceStorage() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )
            val initialMemoryListRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.MemoryList }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.MemoryList,
                    serializer = MemoryListResultPayload.serializer(),
                    payload = MemoryListResultPayload(entries = emptyList()),
                    requestId = initialMemoryListRequest.requestId,
                ),
            )
            advanceUntilIdle()

            val summaryDraftRequestCountBeforeQuery = fixture.channel.sentEnvelopes.count {
                it.type == MessageType.MemorySummaryDraftsList
            }
            fixture.viewModel.refreshRuntimeMemory(query = "  relay recovery  ")
            advanceUntilIdle()

            val queryRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.MemoryList }
            val queryPayload = json.decodeFromJsonElement(
                MemoryListRequestPayload.serializer(),
                queryRequest.payload,
            )
            assertEquals("relay recovery", queryPayload.query)
            assertEquals(
                summaryDraftRequestCountBeforeQuery,
                fixture.channel.sentEnvelopes.count { it.type == MessageType.MemorySummaryDraftsList },
            )

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.MemoryList,
                    serializer = MemoryListResultPayload.serializer(),
                    payload = MemoryListResultPayload(
                        entries = listOf(
                            MemoryEntryPayload(
                                id = "memory-runtime-search",
                                content = "Use the latest QR route recovery steps.",
                                enabled = true,
                                createdAt = "2026-06-25T00:00:00Z",
                                updatedAt = "2026-06-25T00:01:00Z",
                                search = ChatSessionSearchPayload(
                                    rank = 1,
                                    snippet = "Relay recovery source matched the memory entry.",
                                    matchedFields = listOf("content", "source_excerpt"),
                                ),
                            ),
                        ),
                    ),
                    requestId = queryRequest.requestId,
                ),
            )
            advanceUntilIdle()

            val runtimeEntry = fixture.viewModel.state.value.memoryEntries.single()
            assertEquals("Use the latest QR route recovery steps.", runtimeEntry.content)
            assertEquals(1, runtimeEntry.searchRank)
            assertEquals("Relay recovery source matched the memory entry.", runtimeEntry.searchSnippet)
            assertEquals(listOf("content", "source_excerpt"), runtimeEntry.searchMatchedFields)
            assertTrue(fixture.localStore.data.memoryEntries.isEmpty())
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun runtimeDocumentCatalogRequestStoresTransientCatalogWithoutDeviceStorage() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )

            fixture.viewModel.refreshRuntimeDocumentCatalog()
            advanceUntilIdle()

            val catalogRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.IndexDocumentsList }
            val requestPayload = json.decodeFromJsonElement(
                IndexDocumentsListRequestPayload.serializer(),
                catalogRequest.payload,
            )
            assertEquals(100, requestPayload.limit)
            assertTrue(fixture.viewModel.state.value.isLoadingDocumentCatalog)

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.IndexDocumentsList,
                    serializer = IndexDocumentsListResultPayload.serializer(),
                    payload = IndexDocumentsListResultPayload(
                        documents = listOf(
                            RuntimeDocumentIndexDocumentPayload(
                                id = "doc-1",
                                displayName = "Runtime Notes.md",
                                mimeType = "text/markdown",
                                contentFingerprint = "0123456789abcdef",
                                extractedCharacterCount = 1200,
                                chunkCount = 3,
                                quality = "chunked",
                            ),
                        ),
                        summary = IndexDocumentsSummaryPayload(
                            documentCount = 1,
                            chunkCount = 3,
                            extractedCharacterCount = 1200,
                            qualityCounts = IndexDocumentsQualityCountsPayload(
                                noUsableText = 0,
                                singleChunk = 0,
                                chunked = 1,
                            ),
                        ),
                    ),
                    requestId = catalogRequest.requestId,
                ),
            )
            advanceUntilIdle()

            val catalog = fixture.viewModel.state.value.documentCatalog
            assertFalse(fixture.viewModel.state.value.isLoadingDocumentCatalog)
            assertEquals(1, catalog.summary.documentCount)
            assertEquals(3, catalog.summary.chunkCount)
            assertEquals(1, catalog.summary.qualityCounts.chunked)
            assertEquals("Runtime Notes.md", catalog.documents.single().displayName)
            assertEquals("text/markdown", catalog.documents.single().mimeType)
            assertEquals("0123456789abcdef", catalog.documents.single().contentFingerprint)
            assertTrue(fixture.localStore.data.memoryEntries.isEmpty())
            assertTrue(fixture.localStore.data.sessions.none { it.title.contains("Runtime Notes") })
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun runtimeDocumentCatalogClearsTransientRowsOnDisconnect() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )

            fixture.viewModel.refreshRuntimeDocumentCatalog()
            advanceUntilIdle()

            val catalogRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.IndexDocumentsList }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.IndexDocumentsList,
                    serializer = IndexDocumentsListResultPayload.serializer(),
                    payload = IndexDocumentsListResultPayload(
                        documents = listOf(
                            RuntimeDocumentIndexDocumentPayload(
                                id = "doc-disconnect-catalog",
                                displayName = "Disconnect Catalog.md",
                                mimeType = "text/markdown",
                                contentFingerprint = "1122334455667788",
                                extractedCharacterCount = 2048,
                                chunkCount = 2,
                                quality = "chunked",
                            ),
                        ),
                        summary = IndexDocumentsSummaryPayload(
                            documentCount = 1,
                            chunkCount = 2,
                            extractedCharacterCount = 2048,
                            qualityCounts = IndexDocumentsQualityCountsPayload(
                                noUsableText = 0,
                                singleChunk = 0,
                                chunked = 1,
                            ),
                        ),
                    ),
                    requestId = catalogRequest.requestId,
                ),
            )
            advanceUntilIdle()

            val connectedCatalog = fixture.viewModel.state.value.documentCatalog
            assertEquals("Disconnect Catalog.md", connectedCatalog.documents.single().displayName)
            assertEquals(1, connectedCatalog.summary.documentCount)

            fixture.viewModel.disconnect()
            advanceUntilIdle()

            val disconnectedState = fixture.viewModel.state.value
            assertFalse(disconnectedState.isConnected)
            assertEquals("disconnected", disconnectedState.runtimeStatus)
            assertTrue(disconnectedState.documentCatalog.documents.isEmpty())
            assertEquals(RuntimeDocumentIndexSummary(), disconnectedState.documentCatalog.summary)
            assertFalse(disconnectedState.isLoadingDocumentCatalog)
            assertTrue(fixture.localStore.data.memoryEntries.isEmpty())
            assertTrue(fixture.localStore.data.sessions.isEmpty())
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun runtimeDocumentCatalogSummaryBoundsTransientCountsFromRuntimeResponses() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )

            fixture.viewModel.refreshRuntimeDocumentCatalog()
            advanceUntilIdle()

            val catalogRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.IndexDocumentsList }
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.IndexDocumentsList,
                    requestId = catalogRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "documents": [
                                {
                                  "id": "doc-summary-bounds",
                                  "display_name": "Summary Bounds.md",
                                  "mime_type": "text/markdown",
                                  "content_fingerprint": "bbbbaaaa99998888",
                                  "extracted_character_count": 128,
                                  "chunk_count": 1,
                                  "quality": "single_chunk"
                                }
                              ],
                              "summary": {
                                "document_count": -7,
                                "chunk_count": -3,
                                "extracted_character_count": -1200,
                                "quality_counts": {
                                  "no_usable_text": -1,
                                  "single_chunk": -2,
                                  "chunked": -3
                                }
                              }
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val catalog = fixture.viewModel.state.value.documentCatalog
            assertFalse(fixture.viewModel.state.value.isLoadingDocumentCatalog)
            assertTrue(catalog.documents.isEmpty())
            assertEquals(RuntimeDocumentIndexSummary(), catalog.summary)
            assertEquals("invalid_payload", fixture.viewModel.state.value.error?.code)
            assertTrue(fixture.localStore.data.memoryEntries.isEmpty())
            assertTrue(fixture.localStore.data.sessions.isEmpty())
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun runtimeDocumentResponsesCapTransientRowsToRequestLimits() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )

            fun fingerprint(index: Int): String = index.toString(16).padStart(16, '0')

            fun document(index: Int): RuntimeDocumentIndexDocumentPayload {
                return RuntimeDocumentIndexDocumentPayload(
                    id = "doc-$index",
                    displayName = "Document $index.md",
                    mimeType = "text/markdown",
                    contentFingerprint = fingerprint(index),
                    extractedCharacterCount = 100 + index,
                    chunkCount = 2,
                    quality = "chunked",
                )
            }

            fixture.viewModel.refreshRuntimeDocumentCatalog()
            advanceUntilIdle()

            val catalogRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.IndexDocumentsList }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.IndexDocumentsList,
                    serializer = IndexDocumentsListResultPayload.serializer(),
                    payload = IndexDocumentsListResultPayload(
                        documents = (0 until 100).map(::document),
                        summary = IndexDocumentsSummaryPayload(
                            documentCount = 105,
                            chunkCount = 210,
                            extractedCharacterCount = 15000,
                            qualityCounts = IndexDocumentsQualityCountsPayload(
                                noUsableText = 0,
                                singleChunk = 0,
                                chunked = 100,
                            ),
                        ),
                    ),
                    requestId = catalogRequest.requestId,
                ),
            )
            advanceUntilIdle()

            val catalog = fixture.viewModel.state.value.documentCatalog
            assertEquals(100, catalog.documents.size)
            assertEquals("doc-0", catalog.documents.first().id)
            assertEquals("doc-99", catalog.documents.last().id)
            assertEquals(105, catalog.summary.documentCount)
            assertFalse(fixture.viewModel.state.value.isLoadingDocumentCatalog)

            fixture.viewModel.searchRuntimeDocuments("bounded rows")
            advanceUntilIdle()

            val searchRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.RetrievalQuery }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.RetrievalQuery,
                    serializer = RetrievalQueryResultPayload.serializer(),
                    payload = RetrievalQueryResultPayload(
                        results = (0 until 12).map { index ->
                            RetrievalQueryResultItemPayload(
                                document = document(index),
                                chunkIndex = index,
                                startCharacterOffset = index * 10,
                                endCharacterOffset = index * 10 + 5,
                                rank = index + 1,
                                matchedTerms = listOf("bounded", "rows"),
                                snippet = "Bounded document row $index.",
                                sourceAnchorId = "source_anchor_${fingerprint(index)}",
                            )
                        },
                    ),
                    requestId = searchRequest.requestId,
                ),
            )
            advanceUntilIdle()

            val searchResults = fixture.viewModel.state.value.documentSearchResults
            assertEquals(10, searchResults.size)
            assertEquals("doc-0", searchResults.first().document.id)
            assertEquals("doc-9", searchResults.last().document.id)
            assertFalse(fixture.viewModel.state.value.isSearchingDocuments)
            assertTrue(fixture.localStore.data.memoryEntries.isEmpty())
            assertTrue(fixture.localStore.data.sessions.none { it.title.contains("Document") })
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun runtimeDocumentMetadataRejectsNonCanonicalContentFingerprintsBeforeTransientState() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )
            val canonicalDocument = RuntimeDocumentIndexDocumentPayload(
                id = "doc-canonical",
                displayName = "Canonical Fingerprint.md",
                mimeType = "text/markdown",
                contentFingerprint = "0123456789abcdef",
                extractedCharacterCount = 128,
                chunkCount = 1,
                quality = "single_chunk",
            )

            fixture.viewModel.refreshRuntimeDocumentCatalog()
            advanceUntilIdle()

            val catalogRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.IndexDocumentsList }
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.IndexDocumentsList,
                    requestId = catalogRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "documents": [
                                {
                                  "id": "doc-whitespace-fingerprint",
                                  "display_name": "Whitespace Fingerprint.md",
                                  "mime_type": "text/markdown",
                                  "content_fingerprint": " 0123456789abcdef",
                                  "extracted_character_count": 128,
                                  "chunk_count": 1,
                                  "quality": "single_chunk"
                                }
                              ],
                              "summary": {
                                "document_count": 1,
                                "chunk_count": 1,
                                "extracted_character_count": 128,
                                "quality_counts": {
                                  "no_usable_text": 0,
                                  "single_chunk": 1,
                                  "chunked": 0
                                }
                              }
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val rejectedCatalogState = fixture.viewModel.state.value
            assertFalse(rejectedCatalogState.isLoadingDocumentCatalog)
            assertTrue(rejectedCatalogState.documentCatalog.documents.isEmpty())
            assertEquals("invalid_payload", rejectedCatalogState.error?.code)
            assertTrue(rejectedCatalogState.error?.technicalDetail.orEmpty().contains("content_fingerprint"))
            assertTrue(rejectedCatalogState.error?.technicalDetail.orEmpty().contains("16 lowercase hex"))

            fixture.viewModel.refreshRuntimeDocumentCatalog()
            advanceUntilIdle()

            val retryCatalogRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.IndexDocumentsList }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.IndexDocumentsList,
                    serializer = IndexDocumentsListResultPayload.serializer(),
                    payload = IndexDocumentsListResultPayload(
                        documents = listOf(canonicalDocument),
                        summary = IndexDocumentsSummaryPayload(
                            documentCount = 1,
                            chunkCount = 1,
                            extractedCharacterCount = 128,
                            qualityCounts = IndexDocumentsQualityCountsPayload(
                                noUsableText = 0,
                                singleChunk = 1,
                                chunked = 0,
                            ),
                        ),
                    ),
                    requestId = retryCatalogRequest.requestId,
                ),
            )
            advanceUntilIdle()

            assertEquals(
                listOf("0123456789abcdef"),
                fixture.viewModel.state.value.documentCatalog.documents.map { it.contentFingerprint },
            )
            assertNull(fixture.viewModel.state.value.error)

            fixture.viewModel.searchRuntimeDocuments("fingerprint")
            advanceUntilIdle()

            val searchRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.RetrievalQuery }
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.RetrievalQuery,
                    requestId = searchRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "results": [
                                {
                                  "document": {
                                    "id": "doc-uppercase-fingerprint",
                                    "display_name": "Uppercase Fingerprint.md",
                                    "mime_type": "text/markdown",
                                    "content_fingerprint": "0123456789ABCDEF",
                                    "extracted_character_count": 128,
                                    "chunk_count": 1,
                                    "quality": "single_chunk"
                                  },
                                  "chunk_index": 0,
                                  "start_character_offset": 0,
                                  "end_character_offset": 64,
                                  "rank": 1,
                                  "matched_terms": ["fingerprint"],
                                  "snippet": "Noncanonical content fingerprint must fail decode.",
                                  "source_anchor_id": "source_anchor_0123456789abcdef"
                                }
                              ]
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val rejectedSearchState = fixture.viewModel.state.value
            assertFalse(rejectedSearchState.isSearchingDocuments)
            assertTrue(rejectedSearchState.documentSearchResults.isEmpty())
            assertEquals("invalid_payload", rejectedSearchState.error?.code)
            assertTrue(rejectedSearchState.error?.technicalDetail.orEmpty().contains("content_fingerprint"))
            assertTrue(rejectedSearchState.error?.technicalDetail.orEmpty().contains("16 lowercase hex"))

            fixture.viewModel.searchRuntimeDocuments("fingerprint retry")
            advanceUntilIdle()

            val retrySearchRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.RetrievalQuery }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.RetrievalQuery,
                    serializer = RetrievalQueryResultPayload.serializer(),
                    payload = RetrievalQueryResultPayload(
                        results = listOf(
                            RetrievalQueryResultItemPayload(
                                document = canonicalDocument,
                                chunkIndex = 0,
                                startCharacterOffset = 0,
                                endCharacterOffset = 64,
                                rank = 1,
                                matchedTerms = listOf("fingerprint"),
                                snippet = "Canonical fingerprint metadata stays runtime-owned.",
                                sourceAnchorId = "source_anchor_0123456789abcdef",
                            ),
                        ),
                    ),
                    requestId = retrySearchRequest.requestId,
                ),
            )
            advanceUntilIdle()

            assertEquals(
                listOf("0123456789abcdef"),
                fixture.viewModel.state.value.documentSearchResults.map { it.document.contentFingerprint },
            )
            assertNull(fixture.viewModel.state.value.error)
            assertTrue(fixture.localStore.data.memoryEntries.isEmpty())
            assertTrue(fixture.localStore.data.sessions.isEmpty())
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun runtimeDocumentResponsesRejectUnknownFutureMetadataBeforeTransientState() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )
            val canonicalDocument = RuntimeDocumentIndexDocumentPayload(
                id = "doc-future-metadata",
                displayName = "Future Metadata.md",
                mimeType = "text/markdown",
                contentFingerprint = "0123456789abcdef",
                extractedCharacterCount = 512,
                chunkCount = 2,
                quality = "chunked",
            )

            fixture.viewModel.refreshRuntimeDocumentCatalog()
            advanceUntilIdle()

            val catalogRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.IndexDocumentsList }
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.IndexDocumentsList,
                    requestId = catalogRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "documents": [
                                {
                                  "id": "doc-catalog-future",
                                  "display_name": "Catalog Future.md",
                                  "mime_type": "text/markdown",
                                  "content_fingerprint": "0123456789abcdef",
                                  "extracted_character_count": 512,
                                  "chunk_count": 2,
                                  "quality": "chunked",
                                  "source_path": "/private/catalog.md"
                                }
                              ],
                              "summary": {
                                "document_count": 1,
                                "chunk_count": 2,
                                "extracted_character_count": 512,
                                "quality_counts": {
                                  "no_usable_text": 0,
                                  "single_chunk": 0,
                                  "chunked": 1
                                }
                              }
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val rejectedCatalogState = fixture.viewModel.state.value
            assertFalse(rejectedCatalogState.isLoadingDocumentCatalog)
            assertTrue(rejectedCatalogState.documentCatalog.documents.isEmpty())
            assertEquals("invalid_payload", rejectedCatalogState.error?.code)
            assertTrue(rejectedCatalogState.error?.technicalDetail.orEmpty().contains("index.documents.list"))
            assertTrue(rejectedCatalogState.error?.technicalDetail.orEmpty().contains("documents[0].source_path"))

            fixture.viewModel.refreshRuntimeDocumentCatalog()
            advanceUntilIdle()

            val retryCatalogRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.IndexDocumentsList }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.IndexDocumentsList,
                    serializer = IndexDocumentsListResultPayload.serializer(),
                    payload = IndexDocumentsListResultPayload(
                        documents = listOf(canonicalDocument),
                        summary = IndexDocumentsSummaryPayload(
                            documentCount = 1,
                            chunkCount = 2,
                            extractedCharacterCount = 512,
                            qualityCounts = IndexDocumentsQualityCountsPayload(
                                noUsableText = 0,
                                singleChunk = 0,
                                chunked = 1,
                            ),
                        ),
                    ),
                    requestId = retryCatalogRequest.requestId,
                ),
            )
            advanceUntilIdle()

            assertEquals(
                listOf("Future Metadata.md"),
                fixture.viewModel.state.value.documentCatalog.documents.map { it.displayName },
            )
            assertNull(fixture.viewModel.state.value.error)

            fixture.viewModel.searchRuntimeDocuments("future metadata")
            advanceUntilIdle()

            val searchRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.RetrievalQuery }
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.RetrievalQuery,
                    requestId = searchRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "results": [
                                {
                                  "document": {
                                    "id": "doc-search-future",
                                    "display_name": "Search Future.md",
                                    "mime_type": "text/markdown",
                                    "content_fingerprint": "abcdef0123456789",
                                    "extracted_character_count": 512,
                                    "chunk_count": 2,
                                    "quality": "chunked"
                                  },
                                  "chunk_index": 0,
                                  "start_character_offset": 0,
                                  "end_character_offset": 80,
                                  "rank": 1,
                                  "matched_terms": ["future"],
                                  "snippet": "Future metadata must fail before transient state.",
                                  "source_anchor_id": "source_anchor_abcdef0123456789",
                                  "retrieval_context": "private retrieval context"
                                }
                              ]
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val rejectedSearchState = fixture.viewModel.state.value
            assertFalse(rejectedSearchState.isSearchingDocuments)
            assertTrue(rejectedSearchState.documentSearchResults.isEmpty())
            assertEquals("invalid_payload", rejectedSearchState.error?.code)
            assertTrue(rejectedSearchState.error?.technicalDetail.orEmpty().contains("retrieval.query"))
            assertTrue(rejectedSearchState.error?.technicalDetail.orEmpty().contains("results[0].retrieval_context"))

            fixture.viewModel.searchRuntimeDocuments("future metadata retry")
            advanceUntilIdle()

            val documentMetadataSearchRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.RetrievalQuery }
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.RetrievalQuery,
                    requestId = documentMetadataSearchRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "results": [
                                {
                                  "document": {
                                    "id": "doc-search-document-future",
                                    "display_name": "Search Document Future.md",
                                    "mime_type": "text/markdown",
                                    "content_fingerprint": "abcdef0123456789",
                                    "extracted_character_count": 512,
                                    "chunk_count": 2,
                                    "quality": "chunked",
                                    "source_path": "/private/search.md"
                                  },
                                  "chunk_index": 0,
                                  "start_character_offset": 0,
                                  "end_character_offset": 80,
                                  "rank": 1,
                                  "matched_terms": ["future"],
                                  "snippet": "Nested document metadata must also fail.",
                                  "source_anchor_id": "source_anchor_abcdef0123456789"
                                }
                              ]
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val rejectedDocumentMetadataSearchState = fixture.viewModel.state.value
            assertFalse(rejectedDocumentMetadataSearchState.isSearchingDocuments)
            assertTrue(rejectedDocumentMetadataSearchState.documentSearchResults.isEmpty())
            assertEquals("invalid_payload", rejectedDocumentMetadataSearchState.error?.code)
            assertTrue(
                rejectedDocumentMetadataSearchState.error?.technicalDetail.orEmpty()
                    .contains("results[0].document.source_path"),
            )

            fixture.viewModel.searchRuntimeDocuments("canonical future metadata")
            advanceUntilIdle()

            val canonicalSearchRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.RetrievalQuery }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.RetrievalQuery,
                    serializer = RetrievalQueryResultPayload.serializer(),
                    payload = RetrievalQueryResultPayload(
                        results = listOf(
                            RetrievalQueryResultItemPayload(
                                document = canonicalDocument,
                                chunkIndex = 0,
                                startCharacterOffset = 0,
                                endCharacterOffset = 80,
                                rank = 1,
                                matchedTerms = listOf("future"),
                                snippet = "Canonical document metadata can recover after rejection.",
                                sourceAnchorId = "source_anchor_abcdef0123456789",
                            ),
                        ),
                    ),
                    requestId = canonicalSearchRequest.requestId,
                ),
            )
            advanceUntilIdle()

            assertEquals(
                listOf("Future Metadata.md"),
                fixture.viewModel.state.value.documentSearchResults.map { it.document.displayName },
            )
            assertNull(fixture.viewModel.state.value.error)
            assertTrue(fixture.localStore.data.memoryEntries.isEmpty())
            assertTrue(fixture.localStore.data.sessions.isEmpty())
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun runtimeDocumentMetadataReplacesNonCanonicalMimeTypesInTransientState() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )
            val canonicalDocument = RuntimeDocumentIndexDocumentPayload(
                id = "doc-canonical-mime",
                displayName = "Canonical MIME.md",
                mimeType = "text/markdown",
                contentFingerprint = "1234567890abcdef",
                extractedCharacterCount = 128,
                chunkCount = 1,
                quality = "single_chunk",
            )

            fixture.viewModel.refreshRuntimeDocumentCatalog()
            advanceUntilIdle()

            val catalogRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.IndexDocumentsList }
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.IndexDocumentsList,
                    requestId = catalogRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "documents": [
                                {
                                  "id": "doc-uppercase-mime",
                                  "display_name": "Uppercase MIME.md",
                                  "mime_type": "Text/Markdown",
                                  "content_fingerprint": "1234567890abcdef",
                                  "extracted_character_count": 128,
                                  "chunk_count": 1,
                                  "quality": "single_chunk"
                                }
                              ],
                              "summary": {
                                "document_count": 1,
                                "chunk_count": 1,
                                "extracted_character_count": 128,
                                "quality_counts": {
                                  "no_usable_text": 0,
                                  "single_chunk": 1,
                                  "chunked": 0
                                }
                              }
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            assertFalse(fixture.viewModel.state.value.isLoadingDocumentCatalog)
            assertTrue(fixture.viewModel.state.value.documentCatalog.documents.isEmpty())
            assertEquals("invalid_payload", fixture.viewModel.state.value.error?.code)
            assertTrue(fixture.viewModel.state.value.error?.technicalDetail.orEmpty().contains("mime_type"))

            fixture.viewModel.refreshRuntimeDocumentCatalog()
            advanceUntilIdle()

            val retryCatalogRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.IndexDocumentsList }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.IndexDocumentsList,
                    serializer = IndexDocumentsListResultPayload.serializer(),
                    payload = IndexDocumentsListResultPayload(
                        documents = listOf(canonicalDocument),
                        summary = IndexDocumentsSummaryPayload(
                            documentCount = 1,
                            chunkCount = 1,
                            extractedCharacterCount = 128,
                            qualityCounts = IndexDocumentsQualityCountsPayload(
                                noUsableText = 0,
                                singleChunk = 1,
                                chunked = 0,
                            ),
                        ),
                    ),
                    requestId = retryCatalogRequest.requestId,
                ),
            )
            advanceUntilIdle()

            assertEquals(
                listOf("text/markdown"),
                fixture.viewModel.state.value.documentCatalog.documents.map { it.mimeType },
            )
            assertNull(fixture.viewModel.state.value.error)

            fixture.viewModel.searchRuntimeDocuments("mime")
            advanceUntilIdle()

            val searchRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.RetrievalQuery }
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.RetrievalQuery,
                    requestId = searchRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "results": [
                                {
                                  "document": {
                                    "id": "doc-parameterized-mime",
                                    "display_name": "Parameterized MIME.md",
                                    "mime_type": "text/plain; charset=utf-8",
                                    "content_fingerprint": "1234567890abcdef",
                                    "extracted_character_count": 128,
                                    "chunk_count": 1,
                                    "quality": "single_chunk"
                                  },
                                  "chunk_index": 0,
                                  "start_character_offset": 0,
                                  "end_character_offset": 64,
                                  "rank": 1,
                                  "matched_terms": ["mime"],
                                  "snippet": "Parameterized MIME must fail before transient state.",
                                  "source_anchor_id": "source_anchor_0123456789abcdef"
                                }
                              ]
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            assertFalse(fixture.viewModel.state.value.isSearchingDocuments)
            assertTrue(fixture.viewModel.state.value.documentSearchResults.isEmpty())
            assertEquals("invalid_payload", fixture.viewModel.state.value.error?.code)
            assertTrue(fixture.viewModel.state.value.error?.technicalDetail.orEmpty().contains("mime_type"))

            fixture.viewModel.searchRuntimeDocuments("canonical mime")
            advanceUntilIdle()

            val retrySearchRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.RetrievalQuery }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.RetrievalQuery,
                    serializer = RetrievalQueryResultPayload.serializer(),
                    payload = RetrievalQueryResultPayload(
                        results = listOf(
                            RetrievalQueryResultItemPayload(
	                                document = canonicalDocument,
	                                chunkIndex = 0,
	                                startCharacterOffset = 0,
	                                endCharacterOffset = 64,
	                                rank = 1,
	                                matchedTerms = listOf("mime"),
                                snippet = "Canonical MIME metadata stays runtime-owned.",
                                sourceAnchorId = "source_anchor_0123456789abcdef",
                            ),
                        ),
                    ),
                    requestId = retrySearchRequest.requestId,
                ),
            )
            advanceUntilIdle()

            assertEquals(
                listOf("text/markdown"),
                fixture.viewModel.state.value.documentSearchResults.map { it.document.mimeType },
            )
            assertNull(fixture.viewModel.state.value.error)
            assertTrue(fixture.localStore.data.memoryEntries.isEmpty())
            assertTrue(fixture.localStore.data.sessions.isEmpty())
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun runtimeDocumentMetadataDerivesQualityFromChunkCountInTransientState() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )
            val zeroChunkDocument = RuntimeDocumentIndexDocumentPayload(
                id = "doc-zero-chunk-quality",
                displayName = "Zero Chunk Quality.md",
                mimeType = "text/markdown",
                contentFingerprint = "2222333344445555",
                extractedCharacterCount = 0,
                chunkCount = 0,
                quality = "no_usable_text",
            )
            val singleChunkDocument = RuntimeDocumentIndexDocumentPayload(
                id = "doc-single-chunk-quality",
                displayName = "Single Chunk Quality.md",
                mimeType = "text/markdown",
                contentFingerprint = "3333444455556666",
                extractedCharacterCount = 128,
                chunkCount = 1,
                quality = "single_chunk",
            )
            val chunkedDocument = RuntimeDocumentIndexDocumentPayload(
                id = "doc-multi-chunk-quality",
                displayName = "Multi Chunk Quality.md",
                mimeType = "text/markdown",
                contentFingerprint = "4444555566667777",
                extractedCharacterCount = 256,
                chunkCount = 2,
                quality = "chunked",
            )
            val documents = listOf(
                zeroChunkDocument,
                singleChunkDocument,
                chunkedDocument,
            )

            fixture.viewModel.refreshRuntimeDocumentCatalog()
            advanceUntilIdle()

            val catalogRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.IndexDocumentsList }
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.IndexDocumentsList,
                    requestId = catalogRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "documents": [
                                {
                                  "id": "doc-quality-mismatch",
                                  "display_name": "Quality Mismatch.md",
                                  "mime_type": "text/markdown",
                                  "content_fingerprint": "1111222233334444",
                                  "extracted_character_count": 128,
                                  "chunk_count": 0,
                                  "quality": "chunked"
                                }
                              ],
                              "summary": {
                                "document_count": 1,
                                "chunk_count": 0,
                                "extracted_character_count": 128,
                                "quality_counts": {
                                  "no_usable_text": 1,
                                  "single_chunk": 0,
                                  "chunked": 0
                                }
                              }
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            assertFalse(fixture.viewModel.state.value.isLoadingDocumentCatalog)
            assertTrue(fixture.viewModel.state.value.documentCatalog.documents.isEmpty())
            assertEquals("invalid_payload", fixture.viewModel.state.value.error?.code)
            assertTrue(fixture.viewModel.state.value.error?.technicalDetail.orEmpty().contains("quality"))

            fixture.viewModel.refreshRuntimeDocumentCatalog()
            advanceUntilIdle()

            val retryCatalogRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.IndexDocumentsList }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.IndexDocumentsList,
                    serializer = IndexDocumentsListResultPayload.serializer(),
                    payload = IndexDocumentsListResultPayload(
                        documents = documents,
                        summary = IndexDocumentsSummaryPayload(
                            documentCount = documents.size,
                            chunkCount = 3,
                            extractedCharacterCount = documents.sumOf { it.extractedCharacterCount },
                            qualityCounts = IndexDocumentsQualityCountsPayload(
                                noUsableText = 1,
                                singleChunk = 1,
                                chunked = 1,
                            ),
                        ),
                    ),
                    requestId = retryCatalogRequest.requestId,
                ),
            )
            advanceUntilIdle()

            assertEquals(
                listOf(0, 1, 2),
                fixture.viewModel.state.value.documentCatalog.documents.map { it.chunkCount },
            )
            assertEquals(
                listOf("no_usable_text", "single_chunk", "chunked"),
                fixture.viewModel.state.value.documentCatalog.documents.map { it.quality },
            )
            assertNull(fixture.viewModel.state.value.error)

            fixture.viewModel.searchRuntimeDocuments("quality")
            advanceUntilIdle()

            val searchRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.RetrievalQuery }
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.RetrievalQuery,
                    requestId = searchRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "results": [
                                {
                                  "document": {
                                    "id": "doc-search-quality-mismatch",
                                    "display_name": "Search Quality Mismatch.md",
                                    "mime_type": "text/markdown",
                                    "content_fingerprint": "5555666677778888",
                                    "extracted_character_count": 128,
                                    "chunk_count": 1,
                                    "quality": "chunked"
                                  },
                                  "chunk_index": 0,
                                  "start_character_offset": 0,
                                  "end_character_offset": 64,
                                  "rank": 1,
                                  "matched_terms": ["quality"],
                                  "snippet": "Mismatched quality must fail before transient state.",
                                  "source_anchor_id": "source_anchor_0123456789abcdef"
                                }
                              ]
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            assertFalse(fixture.viewModel.state.value.isSearchingDocuments)
            assertTrue(fixture.viewModel.state.value.documentSearchResults.isEmpty())
            assertEquals("invalid_payload", fixture.viewModel.state.value.error?.code)
            assertTrue(fixture.viewModel.state.value.error?.technicalDetail.orEmpty().contains("quality"))

            fixture.viewModel.searchRuntimeDocuments("canonical quality")
            advanceUntilIdle()

            val retrySearchRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.RetrievalQuery }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.RetrievalQuery,
                    serializer = RetrievalQueryResultPayload.serializer(),
                    payload = RetrievalQueryResultPayload(
                        results = documents.mapIndexed { index, document ->
                            RetrievalQueryResultItemPayload(
                                document = document,
                                chunkIndex = index,
                                startCharacterOffset = index * 10,
                                endCharacterOffset = index * 10 + 8,
                                rank = index + 1,
                                matchedTerms = listOf("quality"),
                                snippet = "Quality metadata matches chunk count.",
                                sourceAnchorId = "source_anchor_0123456789abcd${index}f",
                            )
                        },
                    ),
                    requestId = retrySearchRequest.requestId,
                ),
            )
            advanceUntilIdle()

            assertEquals(
                listOf(0, 1, 2),
                fixture.viewModel.state.value.documentSearchResults.map { it.document.chunkCount },
            )
            assertEquals(
                listOf("no_usable_text", "single_chunk", "chunked"),
                fixture.viewModel.state.value.documentSearchResults.map { it.document.quality },
            )
            assertNull(fixture.viewModel.state.value.error)
            assertTrue(fixture.localStore.data.memoryEntries.isEmpty())
            assertTrue(fixture.localStore.data.sessions.isEmpty())
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun runtimeDocumentMetadataBoundsIdsAndDisplayNamesInTransientState() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )
            val canonicalDocument = RuntimeDocumentIndexDocumentPayload(
                id = "doc-canonical-label",
                displayName = "Canonical Label.md",
                mimeType = "text/markdown",
                contentFingerprint = "5555666677778888",
                extractedCharacterCount = 128,
                chunkCount = 1,
                quality = "single_chunk",
            )
            val pathDisplayDocument = canonicalDocument.copy(
                id = " doc-trimmed ",
                displayName = " /safe/path/Runtime Notes.md ",
                contentFingerprint = "6666777788889999",
            )
            val blankDocument = canonicalDocument.copy(
                id = "   ",
                displayName = "   ",
                contentFingerprint = "777788889999aaaa",
            )
            val controlIdDocument = canonicalDocument.copy(
                id = "doc\u0000control",
                displayName = "folder\\Nested.pdf",
                contentFingerprint = "88889999aaaabbbb",
            )
            val documents = listOf(
                canonicalDocument,
                pathDisplayDocument,
                blankDocument,
                controlIdDocument,
            )
            val expectedIds = listOf(
                "doc-canonical-label",
                "doc-trimmed",
                "document_3",
                "document_4",
            )
            val expectedDisplayNames = listOf(
                "Canonical Label.md",
                "Runtime Notes.md",
                "untitled-document",
                "Nested.pdf",
            )

            fixture.viewModel.refreshRuntimeDocumentCatalog()
            advanceUntilIdle()

            val catalogRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.IndexDocumentsList }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.IndexDocumentsList,
                    serializer = IndexDocumentsListResultPayload.serializer(),
                    payload = IndexDocumentsListResultPayload(
                        documents = documents,
                        summary = IndexDocumentsSummaryPayload(
                            documentCount = documents.size,
                            chunkCount = documents.size,
                            extractedCharacterCount = documents.sumOf { it.extractedCharacterCount },
                            qualityCounts = IndexDocumentsQualityCountsPayload(
                                noUsableText = 0,
                                singleChunk = documents.size,
                                chunked = 0,
                            ),
                        ),
                    ),
                    requestId = catalogRequest.requestId,
                ),
            )
            advanceUntilIdle()

            assertEquals(
                expectedIds,
                fixture.viewModel.state.value.documentCatalog.documents.map { it.id },
            )
            assertEquals(
                expectedDisplayNames,
                fixture.viewModel.state.value.documentCatalog.documents.map { it.displayName },
            )

            fixture.viewModel.searchRuntimeDocuments("labels")
            advanceUntilIdle()

            val searchRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.RetrievalQuery }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.RetrievalQuery,
                    serializer = RetrievalQueryResultPayload.serializer(),
                    payload = RetrievalQueryResultPayload(
                        results = documents.mapIndexed { index, document ->
                            RetrievalQueryResultItemPayload(
                                document = document,
                                chunkIndex = index,
                                startCharacterOffset = index * 10,
                                endCharacterOffset = index * 10 + 8,
                                rank = index + 1,
                                matchedTerms = listOf("labels"),
                                snippet = "Document labels stay bounded.",
                                sourceAnchorId = "source_anchor_0123456789abcd${index}f",
                            )
                        },
                    ),
                    requestId = searchRequest.requestId,
                ),
            )
            advanceUntilIdle()

            assertEquals(
                expectedIds,
                fixture.viewModel.state.value.documentSearchResults.map { it.document.id },
            )
            assertEquals(
                expectedDisplayNames,
                fixture.viewModel.state.value.documentSearchResults.map { it.document.displayName },
            )
            assertTrue(fixture.localStore.data.memoryEntries.isEmpty())
            assertTrue(fixture.localStore.data.sessions.isEmpty())
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun runtimeDocumentSearchSendsBoundedQueryAndStaysOutOfChatContext() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val selectedModel = textChatModel()
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(selectedModel),
                selectedModelId = selectedModel.id,
                redactRuntimeOwnedLocalDataOnSave = true,
            )

            fixture.viewModel.searchRuntimeDocuments("  relay recovery  ")
            advanceUntilIdle()

            val searchRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.RetrievalQuery }
            val searchPayload = json.decodeFromJsonElement(
                RetrievalQueryRequestPayload.serializer(),
                searchRequest.payload,
            )
            assertEquals("relay recovery", searchPayload.query)
            assertEquals(10, searchPayload.limit)
            assertEquals(480, searchPayload.maxSnippetCharacters)
            assertEquals("relay recovery", fixture.viewModel.state.value.documentSearchQuery)
            assertTrue(fixture.viewModel.state.value.isSearchingDocuments)

            val document = RuntimeDocumentIndexDocumentPayload(
                id = "doc-relay",
                displayName = "Relay Recovery.md",
                mimeType = "text/markdown",
                contentFingerprint = "abcdef0123456789",
                extractedCharacterCount = 2048,
                chunkCount = 4,
                quality = "chunked",
            )
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.RetrievalQuery,
                    serializer = RetrievalQueryResultPayload.serializer(),
                    payload = RetrievalQueryResultPayload(
                        results = listOf(
                            RetrievalQueryResultItemPayload(
                                document = document,
                                chunkIndex = 2,
                                startCharacterOffset = 120,
                                endCharacterOffset = 360,
                                rank = 1,
                                matchedTerms = listOf("relay", "recovery", "relay", " "),
                                snippet = "Use the latest QR route before retrying relay recovery.",
                                sourceAnchorId = "source_anchor_8899aabbccddeeff",
                            ),
                        ),
                    ),
                    requestId = searchRequest.requestId,
                ),
            )
            advanceUntilIdle()

            val result = fixture.viewModel.state.value.documentSearchResults.single()
            assertFalse(fixture.viewModel.state.value.isSearchingDocuments)
            assertEquals("Relay Recovery.md", result.document.displayName)
            assertEquals("abcdef0123456789", result.document.contentFingerprint)
            assertEquals(2, result.chunkIndex)
            assertEquals(listOf("relay", "recovery"), result.matchedTerms)
            assertEquals("Use the latest QR route before retrying relay recovery.", result.snippet)
            assertEquals("source_anchor_8899aabbccddeeff", result.sourceAnchorId)
            assertTrue(fixture.localStore.data.memoryEntries.isEmpty())

            fixture.viewModel.updateChatInput("Summarize current runtime state")
            fixture.viewModel.sendChatMessage()
            advanceUntilIdle()

            val chatSendEnvelope = fixture.channel.sentEnvelopes.last { it.type == MessageType.ChatSend }
            val chatSendPayload = chatSendEnvelope.payload.toString()
            assertFalse(chatSendPayload.contains("retrieval_context"))
            assertFalse(chatSendPayload.contains("source_path"))
            assertFalse(chatSendPayload.contains("workspace_id"))
            assertFalse(chatSendPayload.contains("project_id"))
            assertFalse(chatSendPayload.contains("citation"))
            assertFalse(chatSendPayload.contains("trusted_source"))
            assertFalse(chatSendPayload.contains("source_anchor_id"))
            assertFalse(chatSendPayload.contains("source_anchor_8899aabbccddeeff"))
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun runtimeDocumentSearchDoesNotSendSelectedEmbeddingModelHint() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val selectedEmbeddingModel = embeddingModel()
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel(), selectedEmbeddingModel),
                selectedEmbeddingModelId = selectedEmbeddingModel.id,
                redactRuntimeOwnedLocalDataOnSave = true,
            )

            fixture.viewModel.searchRuntimeDocuments("  source approval notes  ")
            advanceUntilIdle()

            val searchRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.RetrievalQuery }
            val searchPayload = json.decodeFromJsonElement(
                RetrievalQueryRequestPayload.serializer(),
                searchRequest.payload,
            )
            assertEquals("source approval notes", searchPayload.query)
            assertEquals(10, searchPayload.limit)
            assertEquals(480, searchPayload.maxSnippetCharacters)
            assertNull(searchRequest.payload["embedding_model_id"])
            assertNull(searchRequest.payload["source_anchor_id"])
            assertFalse(json.encodeToString(searchRequest.payload).contains(selectedEmbeddingModel.id))
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun runtimeDocumentSearchRejectsOverlongQueryBeforeSendingRetrievalRequest() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )
            val retrievalRequestsBefore = fixture.channel.sentEnvelopes.count {
                it.type == MessageType.RetrievalQuery
            }

            fixture.viewModel.searchRuntimeDocuments("q".repeat(1025))
            advanceUntilIdle()

            assertEquals(
                retrievalRequestsBefore,
                fixture.channel.sentEnvelopes.count { it.type == MessageType.RetrievalQuery },
            )
            assertFalse(fixture.viewModel.state.value.isSearchingDocuments)
            assertEquals("", fixture.viewModel.state.value.documentSearchQuery)
            assertEquals("document_search_failed", fixture.viewModel.state.value.error?.code)
            assertEquals("query_too_long", fixture.viewModel.state.value.error?.technicalDetail)
            assertTrue(fixture.localStore.data.memoryEntries.isEmpty())
            assertTrue(fixture.localStore.data.sessions.isEmpty())
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun runtimeDocumentSearchInvalidQueryCancelsPendingRequestAndIgnoresStaleResponses() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )

            fixture.viewModel.searchRuntimeDocuments("route")
            advanceUntilIdle()
            val firstRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.RetrievalQuery }

            fixture.viewModel.searchRuntimeDocuments("   ")
            advanceUntilIdle()

            assertEquals("", fixture.viewModel.state.value.documentSearchQuery)
            assertTrue(fixture.viewModel.state.value.documentSearchResults.isEmpty())
            assertFalse(fixture.viewModel.state.value.isSearchingDocuments)

            val document = RuntimeDocumentIndexDocumentPayload(
                id = "doc-stale-search",
                displayName = "Stale Search.md",
                mimeType = "text/markdown",
                contentFingerprint = "0011223344556677",
                extractedCharacterCount = 120,
                chunkCount = 1,
                quality = "single_chunk",
            )
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.RetrievalQuery,
                    serializer = RetrievalQueryResultPayload.serializer(),
                    payload = RetrievalQueryResultPayload(
                        results = listOf(
                            RetrievalQueryResultItemPayload(
                                document = document,
                                chunkIndex = 0,
                                startCharacterOffset = 0,
                                endCharacterOffset = 32,
                                rank = 1,
                                matchedTerms = listOf("route"),
                                snippet = "This stale route result must not reappear.",
                                sourceAnchorId = "source_anchor_0011223344556677",
                            ),
                        ),
                    ),
                    requestId = firstRequest.requestId,
                ),
            )
            advanceUntilIdle()

            assertEquals("", fixture.viewModel.state.value.documentSearchQuery)
            assertTrue(fixture.viewModel.state.value.documentSearchResults.isEmpty())
            assertFalse(fixture.viewModel.state.value.isSearchingDocuments)

            fixture.viewModel.searchRuntimeDocuments("fresh qr")
            advanceUntilIdle()
            val secondRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.RetrievalQuery }
            val secondPayload = json.decodeFromJsonElement(
                RetrievalQueryRequestPayload.serializer(),
                secondRequest.payload,
            )
            assertEquals("fresh qr", secondPayload.query)

            fixture.viewModel.searchRuntimeDocuments("q".repeat(1025))
            advanceUntilIdle()

            assertEquals(
                2,
                fixture.channel.sentEnvelopes.count { it.type == MessageType.RetrievalQuery },
            )
            assertEquals("", fixture.viewModel.state.value.documentSearchQuery)
            assertTrue(fixture.viewModel.state.value.documentSearchResults.isEmpty())
            assertFalse(fixture.viewModel.state.value.isSearchingDocuments)
            assertEquals("document_search_failed", fixture.viewModel.state.value.error?.code)
            assertEquals("query_too_long", fixture.viewModel.state.value.error?.technicalDetail)

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.RetrievalQuery,
                    serializer = RetrievalQueryResultPayload.serializer(),
                    payload = RetrievalQueryResultPayload(
                        results = listOf(
                            RetrievalQueryResultItemPayload(
                                document = document.copy(id = "doc-overlong-stale"),
                                chunkIndex = 0,
                                startCharacterOffset = 0,
                                endCharacterOffset = 24,
                                rank = 1,
                                matchedTerms = listOf("fresh"),
                                snippet = "Overlong rejection should also ignore stale responses.",
                                sourceAnchorId = "source_anchor_8899aabbccddeeff",
                            ),
                        ),
                    ),
                    requestId = secondRequest.requestId,
                ),
            )
            advanceUntilIdle()

            assertTrue(fixture.viewModel.state.value.documentSearchResults.isEmpty())
            assertEquals("document_search_failed", fixture.viewModel.state.value.error?.code)

            fixture.viewModel.searchRuntimeDocuments("after invalid")
            advanceUntilIdle()
            val thirdRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.RetrievalQuery }
            val thirdPayload = json.decodeFromJsonElement(
                RetrievalQueryRequestPayload.serializer(),
                thirdRequest.payload,
            )
            assertEquals("after invalid", thirdPayload.query)
            assertEquals(
                3,
                fixture.channel.sentEnvelopes.count { it.type == MessageType.RetrievalQuery },
            )
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun runtimeDocumentSearchBoundsTransientLexicalMetadataFromRuntimeResponses() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )
            val document = RuntimeDocumentIndexDocumentPayload(
                id = "doc-lexical-bounds",
                displayName = "Lexical Bounds.md",
                mimeType = "text/markdown",
                contentFingerprint = "fedcba9876543210",
                extractedCharacterCount = 1000,
                chunkCount = 2,
                quality = "chunked",
            )
            val maxWireSnippet = "s".repeat(500)
            val maxWireTerm = "t".repeat(64)
            val matchedTerms = listOf(" route ", " ", "route", maxWireTerm) +
                (1..12).map { index -> "term$index" }

            fixture.viewModel.searchRuntimeDocuments("route")
            advanceUntilIdle()

            val searchRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.RetrievalQuery }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.RetrievalQuery,
                    serializer = RetrievalQueryResultPayload.serializer(),
                    payload = RetrievalQueryResultPayload(
                        results = listOf(
                            RetrievalQueryResultItemPayload(
                                document = document,
                                chunkIndex = 3,
                                startCharacterOffset = 10,
                                endCharacterOffset = 42,
                                rank = 2,
                                matchedTerms = matchedTerms,
                                snippet = maxWireSnippet,
                                sourceAnchorId = "source_anchor_fedcba9876543210",
                            ),
                        ),
                    ),
                    requestId = searchRequest.requestId,
                ),
            )
            advanceUntilIdle()

            val result = fixture.viewModel.state.value.documentSearchResults.single()
            assertEquals(3, result.chunkIndex)
            assertEquals(10, result.startCharacterOffset)
            assertEquals(42, result.endCharacterOffset)
            assertEquals(2, result.rank)
            assertEquals(
                listOf("route", maxWireTerm) + (1..12).map { index -> "term$index" },
                result.matchedTerms,
            )
            assertEquals("s".repeat(480), result.snippet)
            assertEquals("source_anchor_fedcba9876543210", result.sourceAnchorId)
            assertTrue(fixture.localStore.data.memoryEntries.isEmpty())
            assertTrue(fixture.localStore.data.sessions.isEmpty())
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun runtimeDocumentSearchRejectsInvalidLexicalMetadataBeforeTransientState() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )

            fixture.viewModel.searchRuntimeDocuments("source anchor lexical terms")
            advanceUntilIdle()

            val invalidTermsRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.RetrievalQuery }
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.RetrievalQuery,
                    requestId = invalidTermsRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "results": [
                                {
                                  "document": {
                                    "id": "doc-invalid-terms",
                                    "display_name": "Invalid Terms.md",
                                    "mime_type": "text/markdown",
                                    "content_fingerprint": "fedcba9876543210",
                                    "extracted_character_count": 1000,
                                    "chunk_count": 2,
                                    "quality": "chunked"
                                  },
                                  "chunk_index": 1,
                                  "start_character_offset": 40,
                                  "end_character_offset": 80,
                                  "rank": 1,
                                  "matched_terms": [],
                                  "snippet": "Invalid matched terms must fail before transient source anchors.",
                                  "source_anchor_id": "source_anchor_fedcba9876543210"
                                }
                              ]
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val rejectedTermsState = fixture.viewModel.state.value
            assertFalse(rejectedTermsState.isSearchingDocuments)
            assertTrue(rejectedTermsState.documentSearchResults.isEmpty())
            assertEquals("invalid_payload", rejectedTermsState.error?.code)
            assertTrue(rejectedTermsState.error?.technicalDetail.orEmpty().contains("matched_terms"))

            fixture.viewModel.searchRuntimeDocuments("source anchor lexical snippet")
            advanceUntilIdle()

            val invalidSnippetRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.RetrievalQuery }
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.RetrievalQuery,
                    requestId = invalidSnippetRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "results": [
                                {
                                  "document": {
                                    "id": "doc-invalid-snippet",
                                    "display_name": "Invalid Snippet.md",
                                    "mime_type": "text/markdown",
                                    "content_fingerprint": "fedcba9876543210",
                                    "extracted_character_count": 1000,
                                    "chunk_count": 2,
                                    "quality": "chunked"
                                  },
                                  "chunk_index": 1,
                                  "start_character_offset": 40,
                                  "end_character_offset": 80,
                                  "rank": 1,
                                  "matched_terms": ["source", "anchor"],
                                  "snippet": "${"s".repeat(501)}",
                                  "source_anchor_id": "source_anchor_fedcba9876543210"
                                }
                              ]
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val rejectedSnippetState = fixture.viewModel.state.value
            assertFalse(rejectedSnippetState.isSearchingDocuments)
            assertTrue(rejectedSnippetState.documentSearchResults.isEmpty())
            assertEquals("invalid_payload", rejectedSnippetState.error?.code)
            assertTrue(rejectedSnippetState.error?.technicalDetail.orEmpty().contains("snippet"))

            fixture.viewModel.searchRuntimeDocuments("source anchor lexical retry")
            advanceUntilIdle()

            val retryRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.RetrievalQuery }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.RetrievalQuery,
                    serializer = RetrievalQueryResultPayload.serializer(),
                    payload = RetrievalQueryResultPayload(
                        results = listOf(
                            RetrievalQueryResultItemPayload(
                                document = RuntimeDocumentIndexDocumentPayload(
                                    id = "doc-valid-lexical",
                                    displayName = "Valid Lexical.md",
                                    mimeType = "text/markdown",
                                    contentFingerprint = "fedcba9876543210",
                                    extractedCharacterCount = 1000,
                                    chunkCount = 2,
                                    quality = "chunked",
                                ),
                                chunkIndex = 1,
                                startCharacterOffset = 40,
                                endCharacterOffset = 80,
                                rank = 1,
                                matchedTerms = listOf("source", "anchor"),
                                snippet = "Valid lexical metadata can publish transient search rows.",
                                sourceAnchorId = "source_anchor_fedcba9876543210",
                            ),
                        ),
                    ),
                    requestId = retryRequest.requestId,
                ),
            )
            advanceUntilIdle()

            val result = fixture.viewModel.state.value.documentSearchResults.single()
            assertEquals("Valid Lexical.md", result.document.displayName)
            assertEquals(listOf("source", "anchor"), result.matchedTerms)
            assertEquals("Valid lexical metadata can publish transient search rows.", result.snippet)
            assertEquals("source_anchor_fedcba9876543210", result.sourceAnchorId)
            assertTrue(fixture.localStore.data.memoryEntries.isEmpty())
            assertTrue(fixture.localStore.data.sessions.isEmpty())
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun runtimeDocumentSearchRejectsInvalidCoordinatesAndRankBeforeTransientState() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )

            fixture.viewModel.searchRuntimeDocuments("source anchor coordinates")
            advanceUntilIdle()

            val invalidRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.RetrievalQuery }
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.RetrievalQuery,
                    requestId = invalidRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "results": [
                                {
                                  "document": {
                                    "id": "doc-invalid-coordinate",
                                    "display_name": "Invalid Coordinate.md",
                                    "mime_type": "text/markdown",
                                    "content_fingerprint": "fedcba9876543210",
                                    "extracted_character_count": 1000,
                                    "chunk_count": 2,
                                    "quality": "chunked"
                                  },
                                  "chunk_index": 1,
                                  "start_character_offset": 80,
                                  "end_character_offset": 40,
                                  "rank": 1,
                                  "matched_terms": ["source", "anchor"],
                                  "snippet": "Invalid coordinates must fail before transient source anchors.",
                                  "source_anchor_id": "source_anchor_fedcba9876543210"
                                }
                              ]
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val rejectedState = fixture.viewModel.state.value
            assertFalse(rejectedState.isSearchingDocuments)
            assertTrue(rejectedState.documentSearchResults.isEmpty())
            assertEquals("invalid_payload", rejectedState.error?.code)
            assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("end_character_offset"))
            assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("start_character_offset"))

            fixture.viewModel.searchRuntimeDocuments("source anchor coordinates retry")
            advanceUntilIdle()

            val retryRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.RetrievalQuery }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.RetrievalQuery,
                    serializer = RetrievalQueryResultPayload.serializer(),
                    payload = RetrievalQueryResultPayload(
                        results = listOf(
                            RetrievalQueryResultItemPayload(
                                document = RuntimeDocumentIndexDocumentPayload(
                                    id = "doc-valid-coordinate",
                                    displayName = "Valid Coordinate.md",
                                    mimeType = "text/markdown",
                                    contentFingerprint = "fedcba9876543210",
                                    extractedCharacterCount = 1000,
                                    chunkCount = 2,
                                    quality = "chunked",
                                ),
                                chunkIndex = 1,
                                startCharacterOffset = 40,
                                endCharacterOffset = 80,
                                rank = 1,
                                matchedTerms = listOf("source", "anchor"),
                                snippet = "Valid coordinates can still publish transient search rows.",
                                sourceAnchorId = "source_anchor_fedcba9876543210",
                            ),
                        ),
                    ),
                    requestId = retryRequest.requestId,
                ),
            )
            advanceUntilIdle()

            val retryState = fixture.viewModel.state.value
            assertFalse(retryState.isSearchingDocuments)
            assertNull(retryState.error)
            assertEquals("Valid Coordinate.md", retryState.documentSearchResults.single().document.displayName)
            assertEquals("source_anchor_fedcba9876543210", retryState.documentSearchResults.single().sourceAnchorId)
            assertTrue(fixture.localStore.data.memoryEntries.isEmpty())
            assertTrue(fixture.localStore.data.sessions.isEmpty())
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun runtimeDocumentSearchDropsNonCanonicalSourceAnchorIdsFromTransientState() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
            )

            fixture.viewModel.searchRuntimeDocuments("source anchor")
            advanceUntilIdle()

            val searchRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.RetrievalQuery }
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.RetrievalQuery,
                    requestId = searchRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "results": [
                                {
                                  "document": {
                                    "id": "doc-source-anchor-uppercase",
                                    "display_name": "Source Anchor Notes.md",
                                    "mime_type": "text/markdown",
                                    "content_fingerprint": "abcdef0123456789",
                                    "extracted_character_count": 4096,
                                    "chunk_count": 6,
                                    "quality": "chunked"
                                  },
                                  "chunk_index": 0,
                                  "start_character_offset": 0,
                                  "end_character_offset": 120,
                                  "rank": 1,
                                  "matched_terms": ["source", "anchor"],
                                  "snippet": "Noncanonical source anchor must fail decode.",
                                  "source_anchor_id": "source_anchor_0123456789ABCDEF"
                                }
                              ]
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val rejectedState = fixture.viewModel.state.value
            assertFalse(rejectedState.isSearchingDocuments)
            assertTrue(rejectedState.documentSearchResults.isEmpty())
            assertEquals("invalid_payload", rejectedState.error?.code)
            assertTrue(
                rejectedState.error?.technicalDetail.orEmpty().contains("source_anchor_id"),
            )
            assertTrue(
                rejectedState.error?.technicalDetail.orEmpty().contains("source_anchor_[16 lowercase hex]"),
            )

            fixture.viewModel.searchRuntimeDocuments("source anchor retry")
            advanceUntilIdle()

            val retryRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.RetrievalQuery }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.RetrievalQuery,
                    serializer = RetrievalQueryResultPayload.serializer(),
                    payload = RetrievalQueryResultPayload(
                        results = listOf(
                            RetrievalQueryResultItemPayload(
                                document = RuntimeDocumentIndexDocumentPayload(
                                    id = "doc-source-anchor-retry",
                                    displayName = "Source Anchor Retry.md",
                                    mimeType = "text/markdown",
                                    contentFingerprint = "abcdef0123456789",
                                    extractedCharacterCount = 4096,
                                    chunkCount = 6,
                                    quality = "chunked",
                                ),
                                chunkIndex = 0,
                                startCharacterOffset = 0,
                                endCharacterOffset = 120,
                                rank = 1,
                                matchedTerms = listOf("source", "anchor"),
                                snippet = "Canonical source anchor remains available for future review.",
                                sourceAnchorId = "source_anchor_0123456789abcdef",
                            ),
                        ),
                    ),
                    requestId = retryRequest.requestId,
                ),
            )
            advanceUntilIdle()

            val results = fixture.viewModel.state.value.documentSearchResults
            assertFalse(fixture.viewModel.state.value.isSearchingDocuments)
            assertEquals(1, results.size)
            assertEquals("Canonical source anchor remains available for future review.", results.single().snippet)
            assertEquals("source_anchor_0123456789abcdef", results.single().sourceAnchorId)
            assertEquals("abcdef0123456789", results.single().document.contentFingerprint)
            assertNull(fixture.viewModel.state.value.error)
            assertTrue(fixture.localStore.data.memoryEntries.isEmpty())
            assertTrue(fixture.localStore.data.sessions.isEmpty())
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun runtimeIgnoresUnsolicitedSourceAnchorResolveResultWithoutAdvertisingOrPersisting() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            assertFalse(runtimeClientCapabilities(authenticatedRouteRefreshEnabled = false).contains(MessageType.SourceAnchorResolve))
            assertFalse(runtimeClientCapabilities(authenticatedRouteRefreshEnabled = true).contains(MessageType.SourceAnchorResolve))

            val selectedModel = textChatModel()
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(selectedModel),
                selectedModelId = selectedModel.id,
                redactRuntimeOwnedLocalDataOnSave = true,
            )

            fixture.viewModel.searchRuntimeDocuments("source anchor")
            advanceUntilIdle()

            val searchRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.RetrievalQuery }
            val searchDocument = RuntimeDocumentIndexDocumentPayload(
                id = "doc-source-anchor-boundary",
                displayName = "Source Anchor Boundary.md",
                mimeType = "text/markdown",
                contentFingerprint = "1234567890abcdef",
                extractedCharacterCount = 2048,
                chunkCount = 3,
                quality = "chunked",
            )
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.RetrievalQuery,
                    serializer = RetrievalQueryResultPayload.serializer(),
                    payload = RetrievalQueryResultPayload(
                        results = listOf(
                            RetrievalQueryResultItemPayload(
                                document = searchDocument,
                                chunkIndex = 0,
                                startCharacterOffset = 0,
                                endCharacterOffset = 128,
                                rank = 1,
                                matchedTerms = listOf("source", "anchor"),
                                snippet = "Search can keep an opaque source anchor without resolving it on Android.",
                                sourceAnchorId = "source_anchor_1234567890abcdef",
                            ),
                        ),
                    ),
                    requestId = searchRequest.requestId,
                ),
            )
            advanceUntilIdle()

            val beforeResolverState = fixture.viewModel.state.value
            val beforeResolverStore = fixture.localStore.data
            assertEquals("source_anchor_1234567890abcdef", beforeResolverState.documentSearchResults.single().sourceAnchorId)
            assertTrue(fixture.channel.sentEnvelopes.none { it.type == MessageType.SourceAnchorResolve })

            val resolvedDocumentNameCanary = "Resolved Private Source.md"
            val resolvedFingerprintCanary = "fedcba9876543210"
            val resolvedAnchorCanary = "source_anchor_fedcba9876543210"
            val resolvedChunkTextCanary = "private chunk text must stay unavailable"
            val resolvedSnippetCanary = "private resolver snippet must stay unavailable"
            val resolvedSourcePathCanary = "/Users/runtime/private/source.md"
            val resolvedRetrievalContextCanary = "private retrieval context must stay unavailable"
            val resolvedCitationCanary = "citation-source-canary"
            val resolvedTrustedSourceCanary = "trusted-source-canary"
            val resolvedApprovalStateCanary = "approval-state-canary"
            val resolvedBackendUrlCanary = "http://127.0.0.1:11434/private"
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.SourceAnchorResolve,
                    requestId = "unsolicited-source-anchor-resolve",
                    payload = json.parseToJsonElement(
                        """
                            {
                              "source_anchor_id": "$resolvedAnchorCanary",
                              "document": {
                                "id": "doc-resolved-private",
                                "display_name": "$resolvedDocumentNameCanary",
                                "mime_type": "text/markdown",
                                "content_fingerprint": "$resolvedFingerprintCanary",
                                "extracted_character_count": 8192,
                                "chunk_count": 8,
                                "quality": "chunked",
                                "source_path": "$resolvedSourcePathCanary",
                                "backend_url": "$resolvedBackendUrlCanary"
                              },
                              "chunk_summary": {
                                "chunk_index": 7,
                                "start_character_offset": 700,
                                "end_character_offset": 900,
                                "character_count": 200,
                                "snippet": "$resolvedSnippetCanary"
                              },
                              "chunk_text": "$resolvedChunkTextCanary",
                              "snippet": "$resolvedSnippetCanary",
                              "source_path": "$resolvedSourcePathCanary",
                              "retrieval_context": "$resolvedRetrievalContextCanary",
                              "citations": [{"source": "$resolvedCitationCanary"}],
                              "trusted_source": {"id": "$resolvedTrustedSourceCanary"},
                              "approval_state": "$resolvedApprovalStateCanary",
                              "backend_url": "$resolvedBackendUrlCanary"
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val afterResolverState = fixture.viewModel.state.value
            assertEquals(beforeResolverState.documentCatalog, afterResolverState.documentCatalog)
            assertEquals(beforeResolverState.documentSearchQuery, afterResolverState.documentSearchQuery)
            assertEquals(beforeResolverState.documentSearchResults, afterResolverState.documentSearchResults)
            assertEquals(beforeResolverState.isSearchingDocuments, afterResolverState.isSearchingDocuments)
            assertEquals(beforeResolverState.error, afterResolverState.error)
            assertEquals(beforeResolverStore, fixture.localStore.data)
            assertTrue(fixture.channel.sentEnvelopes.none { it.type == MessageType.SourceAnchorResolve })

            fixture.viewModel.updateChatInput("Summarize visible document search state")
            fixture.viewModel.sendChatMessage()
            advanceUntilIdle()

            val chatSendPayload = fixture.channel.sentEnvelopes.last { it.type == MessageType.ChatSend }.payload.toString()
            assertFalse(chatSendPayload.contains("source_anchor_id"))
            assertFalse(chatSendPayload.contains("source_anchor_1234567890abcdef"))
            assertFalse(chatSendPayload.contains(resolvedAnchorCanary))
            assertFalse(chatSendPayload.contains(resolvedDocumentNameCanary))
            assertFalse(chatSendPayload.contains(resolvedFingerprintCanary))
            assertFalse(chatSendPayload.contains("chunk_summary"))
            assertFalse(chatSendPayload.contains(resolvedChunkTextCanary))
            assertFalse(chatSendPayload.contains(resolvedSnippetCanary))
            assertFalse(chatSendPayload.contains(resolvedSourcePathCanary))
            assertFalse(chatSendPayload.contains(resolvedRetrievalContextCanary))
            assertFalse(chatSendPayload.contains(resolvedCitationCanary))
            assertFalse(chatSendPayload.contains(resolvedTrustedSourceCanary))
            assertFalse(chatSendPayload.contains(resolvedApprovalStateCanary))
            assertFalse(chatSendPayload.contains(resolvedBackendUrlCanary))
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun runtimeDocumentSearchClearsTransientResultsAndSourceAnchorsOnDisconnect() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )

            fixture.viewModel.searchRuntimeDocuments("source anchor")
            advanceUntilIdle()

            val searchRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.RetrievalQuery }
            val document = RuntimeDocumentIndexDocumentPayload(
                id = "doc-disconnect-source-anchor",
                displayName = "Disconnect Source Anchor.md",
                mimeType = "text/markdown",
                contentFingerprint = "aabbccddeeff0011",
                extractedCharacterCount = 4096,
                chunkCount = 6,
                quality = "chunked",
            )
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.RetrievalQuery,
                    serializer = RetrievalQueryResultPayload.serializer(),
                    payload = RetrievalQueryResultPayload(
                        results = listOf(
                            RetrievalQueryResultItemPayload(
                                document = document,
                                chunkIndex = 1,
                                startCharacterOffset = 80,
                                endCharacterOffset = 180,
                                rank = 1,
                                matchedTerms = listOf("source", "anchor"),
                                snippet = "Disconnect must clear transient source anchors.",
                                sourceAnchorId = "source_anchor_aabbccddeeff0011",
                            ),
                        ),
                    ),
                    requestId = searchRequest.requestId,
                ),
            )
            advanceUntilIdle()

            val connectedState = fixture.viewModel.state.value
            assertEquals("source anchor", connectedState.documentSearchQuery)
            assertEquals("source_anchor_aabbccddeeff0011", connectedState.documentSearchResults.single().sourceAnchorId)
            assertFalse(connectedState.isSearchingDocuments)

            fixture.viewModel.disconnect()
            advanceUntilIdle()

            val disconnectedState = fixture.viewModel.state.value
            assertFalse(disconnectedState.isConnected)
            assertEquals("disconnected", disconnectedState.runtimeStatus)
            assertEquals("", disconnectedState.documentSearchQuery)
            assertTrue(disconnectedState.documentSearchResults.isEmpty())
            assertFalse(disconnectedState.isSearchingDocuments)
            assertTrue(fixture.localStore.data.memoryEntries.isEmpty())
            assertTrue(fixture.localStore.data.sessions.isEmpty())
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun runtimeDocumentSearchErrorClearsPendingAndAllowsRetry() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
            )

            fixture.viewModel.searchRuntimeDocuments("route")
            advanceUntilIdle()
            val firstRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.RetrievalQuery }

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.Error,
                    serializer = ErrorPayload.serializer(),
                    payload = ErrorPayload(
                        code = "document_index_unavailable",
                        message = "Document index unavailable",
                        retryable = false,
                    ),
                    requestId = firstRequest.requestId,
                ),
            )
            advanceUntilIdle()

            assertFalse(fixture.viewModel.state.value.isSearchingDocuments)
            assertEquals("document_search_failed", fixture.viewModel.state.value.error?.code)

            fixture.viewModel.searchRuntimeDocuments("fresh qr")
            advanceUntilIdle()

            val searchRequests = fixture.channel.sentEnvelopes.filter { it.type == MessageType.RetrievalQuery }
            val retryPayload = json.decodeFromJsonElement(
                RetrievalQueryRequestPayload.serializer(),
                searchRequests.last().payload,
            )
            assertEquals(2, searchRequests.size)
            assertEquals("fresh qr", retryPayload.query)
            assertTrue(fixture.viewModel.state.value.isSearchingDocuments)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun runtimeMemorySummaryDraftsListRendersReviewStateWithoutDeviceStorage() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )
            val initialDraftRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.MemorySummaryDraftsList
            }
            val initialDraftRequestCount = fixture.channel.sentEnvelopes.count {
                it.type == MessageType.MemorySummaryDraftsList
            }

            fixture.viewModel.refreshRuntimeMemorySummaryDrafts()
            advanceUntilIdle()
            assertEquals(
                initialDraftRequestCount,
                fixture.channel.sentEnvelopes.count { it.type == MessageType.MemorySummaryDraftsList },
            )

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.MemorySummaryDraftsList,
                    serializer = MemorySummaryDraftsListResultPayload.serializer(),
                    payload = MemorySummaryDraftsListResultPayload(
                        drafts = listOf(
                            MemorySummaryDraftPayload(
                                id = "draft-runtime-memory",
                                session = MemorySummaryDraftSessionPayload(
                                    sessionId = "runtime-session",
                                    title = "Long idle planning chat",
                                    model = "ollama:qwen3:8b",
                                    lastActivityAt = "2026-06-01T00:00:00Z",
                                    messageCount = 6,
                                    inactiveSeconds = 1_209_600L,
                                ),
                                sourceMessageCount = 6,
                                sourceRange = "visible messages 1-6 of 6",
                                sourcePointers = listOf(
                                    MemorySummaryDraftSourcePointerPayload(
                                        sessionId = "runtime-session",
                                        messageIndex = 1,
                                        role = "user",
                                        createdAt = "2026-06-01T00:00:00Z",
                                        excerpt = "Use concise Korean summaries for release notes.",
                                    ),
                                    MemorySummaryDraftSourcePointerPayload(
                                        sessionId = "runtime-session",
                                        messageIndex = 2,
                                        role = "assistant",
                                        createdAt = "2026-06-01T00:01:00Z",
                                        excerpt = "I will keep release notes concise.",
                                    ),
                                ),
                                summaryPreview = "Prefer concise Korean release-note summaries.",
                            ),
                        ),
                    ),
                    requestId = initialDraftRequest.requestId,
                ),
            )
            advanceUntilIdle()

            val draft = fixture.viewModel.state.value.memorySummaryDrafts.single()
            assertEquals("draft-runtime-memory", draft.id)
            assertEquals("Long idle planning chat", draft.session.title)
            assertEquals("runtime-session", draft.session.sessionId)
            assertEquals(6, draft.sourceMessageCount)
            assertEquals("visible messages 1-6 of 6", draft.sourceRange)
            assertEquals(
                listOf(
                    "Use concise Korean summaries for release notes.",
                    "I will keep release notes concise.",
                ),
                draft.sourcePointers.map { it.excerpt },
            )
            assertEquals("Prefer concise Korean release-note summaries.", draft.summaryPreview)
            assertTrue(fixture.localStore.data.memoryEntries.isEmpty())

            fixture.viewModel.refreshRuntimeMemorySummaryDrafts()
            advanceUntilIdle()
            assertEquals(
                initialDraftRequestCount + 1,
                fixture.channel.sentEnvelopes.count { it.type == MessageType.MemorySummaryDraftsList },
            )
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun memorySummaryDraftsListRejectsUnknownMetadataBeforeReviewStatePublication() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )
            val initialDraftRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.MemorySummaryDraftsList
            }

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.MemorySummaryDraftsList,
                    serializer = MemorySummaryDraftsListResultPayload.serializer(),
                    payload = MemorySummaryDraftsListResultPayload(
                        drafts = listOf(
                            MemorySummaryDraftPayload(
                                id = "existing-draft",
                                session = MemorySummaryDraftSessionPayload(
                                    sessionId = "runtime-session",
                                    title = "Existing planning chat",
                                    model = "ollama:qwen3:8b",
                                    lastActivityAt = "2026-06-01T00:00:00Z",
                                    messageCount = 6,
                                    inactiveSeconds = 1_209_600L,
                                ),
                                sourceMessageCount = 6,
                                sourceRange = "visible messages 1-6 of 6",
                                sourcePointers = listOf(
                                    MemorySummaryDraftSourcePointerPayload(
                                        sessionId = "runtime-session",
                                        messageIndex = 1,
                                        role = "user",
                                        createdAt = "2026-06-01T00:00:00Z",
                                        excerpt = "Keep review state stable.",
                                    ),
                                ),
                                summaryPreview = "Existing summary preview",
                            ),
                        ),
                    ),
                    requestId = initialDraftRequest.requestId,
                ),
            )
            advanceUntilIdle()

            fun assertExistingDraftPreserved() {
                assertEquals(
                    listOf("Existing summary preview"),
                    fixture.viewModel.state.value.memorySummaryDrafts.map { it.summaryPreview },
                )
                assertTrue(fixture.localStore.data.memoryEntries.isEmpty())
                val persistedSnapshot = json.encodeToString(fixture.localStore.data)
                assertFalse(persistedSnapshot.contains("Leaky summary preview"))
                assertFalse(persistedSnapshot.contains("workspace-canary"))
            }

            assertExistingDraftPreserved()

            fixture.viewModel.refreshRuntimeMemorySummaryDrafts()
            advanceUntilIdle()
            val topLevelMetadataRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.MemorySummaryDraftsList
            }
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.MemorySummaryDraftsList,
                    requestId = topLevelMetadataRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "drafts": [
                                {
                                  "id": "leaky-top-level-draft",
                                  "session": {
                                    "session_id": "runtime-session",
                                    "title": "Leaky planning chat",
                                    "model": "ollama:qwen3:8b",
                                    "last_activity_at": "2026-06-01T00:00:00Z",
                                    "message_count": 6,
                                    "inactive_seconds": 1209600
                                  },
                                  "source_message_count": 6,
                                  "source_range": "visible messages 1-6 of 6",
                                  "source_pointers": [
                                    {
                                      "session_id": "runtime-session",
                                      "message_index": 1,
                                      "role": "user",
                                      "created_at": "2026-06-01T00:00:00Z",
                                      "excerpt": "Leaky source excerpt"
                                    }
                                  ],
                                  "summary_preview": "Leaky summary preview"
                                }
                              ],
                              "backend_url": "http://127.0.0.1:11434"
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val topLevelRejectedState = fixture.viewModel.state.value
            assertEquals("invalid_payload", topLevelRejectedState.error?.code)
            assertTrue(topLevelRejectedState.error?.technicalDetail.orEmpty().contains("memory.summary.drafts.list"))
            assertTrue(topLevelRejectedState.error?.technicalDetail.orEmpty().contains("backend_url"))
            assertExistingDraftPreserved()

            fixture.viewModel.refreshRuntimeMemorySummaryDrafts()
            advanceUntilIdle()
            val draftMetadataRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.MemorySummaryDraftsList
            }
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.MemorySummaryDraftsList,
                    requestId = draftMetadataRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "drafts": [
                                {
                                  "id": "leaky-draft-metadata",
                                  "session": {
                                    "session_id": "runtime-session",
                                    "title": "Leaky planning chat",
                                    "model": "ollama:qwen3:8b",
                                    "last_activity_at": "2026-06-01T00:00:00Z",
                                    "message_count": 6,
                                    "inactive_seconds": 1209600
                                  },
                                  "source_message_count": 6,
                                  "source_range": "visible messages 1-6 of 6",
                                  "source_pointers": [
                                    {
                                      "session_id": "runtime-session",
                                      "message_index": 1,
                                      "role": "user",
                                      "created_at": "2026-06-01T00:00:00Z",
                                      "excerpt": "Leaky source excerpt"
                                    }
                                  ],
                                  "summary_preview": "Leaky summary preview",
                                  "workspace_id": "workspace-canary"
                                }
                              ]
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val draftRejectedState = fixture.viewModel.state.value
            assertEquals("invalid_payload", draftRejectedState.error?.code)
            assertTrue(draftRejectedState.error?.technicalDetail.orEmpty().contains("memory.summary.drafts.list"))
            assertTrue(draftRejectedState.error?.technicalDetail.orEmpty().contains("drafts[0].workspace_id"))
            assertExistingDraftPreserved()

            fixture.viewModel.refreshRuntimeMemorySummaryDrafts()
            advanceUntilIdle()
            val sessionMetadataRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.MemorySummaryDraftsList
            }
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.MemorySummaryDraftsList,
                    requestId = sessionMetadataRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "drafts": [
                                {
                                  "id": "leaky-session-metadata",
                                  "session": {
                                    "session_id": "runtime-session",
                                    "title": "Leaky planning chat",
                                    "model": "ollama:qwen3:8b",
                                    "last_activity_at": "2026-06-01T00:00:00Z",
                                    "message_count": 6,
                                    "inactive_seconds": 1209600,
                                    "backend_url": "http://127.0.0.1:11434"
                                  },
                                  "source_message_count": 6,
                                  "source_range": "visible messages 1-6 of 6",
                                  "source_pointers": [
                                    {
                                      "session_id": "runtime-session",
                                      "message_index": 1,
                                      "role": "user",
                                      "created_at": "2026-06-01T00:00:00Z",
                                      "excerpt": "Leaky source excerpt"
                                    }
                                  ],
                                  "summary_preview": "Leaky summary preview"
                                }
                              ]
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val sessionRejectedState = fixture.viewModel.state.value
            assertEquals("invalid_payload", sessionRejectedState.error?.code)
            assertTrue(sessionRejectedState.error?.technicalDetail.orEmpty().contains("memory.summary.drafts.list"))
            assertTrue(sessionRejectedState.error?.technicalDetail.orEmpty().contains("drafts[0].session.backend_url"))
            assertExistingDraftPreserved()

            fixture.viewModel.refreshRuntimeMemorySummaryDrafts()
            advanceUntilIdle()
            val pointerMetadataRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.MemorySummaryDraftsList
            }
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.MemorySummaryDraftsList,
                    requestId = pointerMetadataRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "drafts": [
                                {
                                  "id": "leaky-pointer-metadata",
                                  "session": {
                                    "session_id": "runtime-session",
                                    "title": "Leaky planning chat",
                                    "model": "ollama:qwen3:8b",
                                    "last_activity_at": "2026-06-01T00:00:00Z",
                                    "message_count": 6,
                                    "inactive_seconds": 1209600
                                  },
                                  "source_message_count": 6,
                                  "source_range": "visible messages 1-6 of 6",
                                  "source_pointers": [
                                    {
                                      "session_id": "runtime-session",
                                      "message_index": 1,
                                      "role": "user",
                                      "created_at": "2026-06-01T00:00:00Z",
                                      "excerpt": "Leaky source excerpt",
                                      "source_path": "/Users/hanchangha/private-chat.jsonl"
                                    }
                                  ],
                                  "summary_preview": "Leaky summary preview"
                                }
                              ]
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val pointerRejectedState = fixture.viewModel.state.value
            assertEquals("invalid_payload", pointerRejectedState.error?.code)
            assertTrue(pointerRejectedState.error?.technicalDetail.orEmpty().contains("memory.summary.drafts.list"))
            assertTrue(
                pointerRejectedState.error?.technicalDetail.orEmpty()
                    .contains("drafts[0].source_pointers[0].source_path"),
            )
            assertExistingDraftPreserved()

            fixture.viewModel.refreshRuntimeMemorySummaryDrafts()
            advanceUntilIdle()
            val canonicalRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.MemorySummaryDraftsList
            }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.MemorySummaryDraftsList,
                    serializer = MemorySummaryDraftsListResultPayload.serializer(),
                    payload = MemorySummaryDraftsListResultPayload(
                        drafts = listOf(
                            MemorySummaryDraftPayload(
                                id = "canonical-draft",
                                session = MemorySummaryDraftSessionPayload(
                                    sessionId = "runtime-session",
                                    title = "Canonical planning chat",
                                    model = "ollama:qwen3:8b",
                                    lastActivityAt = "2026-06-02T00:00:00Z",
                                    messageCount = 7,
                                    inactiveSeconds = 1_296_000L,
                                ),
                                sourceMessageCount = 7,
                                sourceRange = "visible messages 1-7 of 7",
                                sourcePointers = listOf(
                                    MemorySummaryDraftSourcePointerPayload(
                                        sessionId = "runtime-session",
                                        messageIndex = 1,
                                        role = "assistant",
                                        createdAt = "2026-06-02T00:00:00Z",
                                        excerpt = "Canonical source excerpt.",
                                    ),
                                ),
                                summaryPreview = "Canonical summary preview",
                            ),
                        ),
                    ),
                    requestId = canonicalRequest.requestId,
                ),
            )
            advanceUntilIdle()

            val acceptedState = fixture.viewModel.state.value
            assertNull(acceptedState.error)
            assertEquals(
                listOf("Canonical summary preview"),
                acceptedState.memorySummaryDrafts.map { it.summaryPreview },
            )
            assertEquals("canonical-draft", acceptedState.memorySummaryDrafts.single().id)
            assertTrue(fixture.localStore.data.memoryEntries.isEmpty())
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun approveMemorySummaryDraftSendsExpectedApprovalAndRendersRuntimeMemoryOnly() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )
            val initialDraftRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.MemorySummaryDraftsList
            }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.MemorySummaryDraftsList,
                    serializer = MemorySummaryDraftsListResultPayload.serializer(),
                    payload = MemorySummaryDraftsListResultPayload(
                        drafts = listOf(
                            MemorySummaryDraftPayload(
                                id = "draft-runtime-memory",
                                session = MemorySummaryDraftSessionPayload(
                                    sessionId = "runtime-session",
                                    title = "Long idle planning chat",
                                    model = "ollama:qwen3:8b",
                                    lastActivityAt = "2026-06-01T00:00:00Z",
                                    messageCount = 6,
                                    inactiveSeconds = 1_209_600L,
                                ),
                                sourceMessageCount = 6,
                                sourceRange = "visible messages 1-6 of 6",
                                sourcePointers = listOf(
                                    MemorySummaryDraftSourcePointerPayload(
                                        sessionId = "runtime-session",
                                        messageIndex = 1,
                                        role = "user",
                                        createdAt = "2026-06-01T00:00:00Z",
                                        excerpt = "Use concise Korean summaries for release notes.",
                                    ),
                                ),
                                summaryPreview = "Prefer concise Korean release-note summaries.",
                            ),
                        ),
                    ),
                    requestId = initialDraftRequest.requestId,
                ),
            )
            advanceUntilIdle()

            fixture.viewModel.approveMemorySummaryDraft("draft-runtime-memory")
            advanceUntilIdle()

            val approvalRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.MemorySummaryDraftApprove
            }
            val approvalPayload = json.decodeFromJsonElement(
                MemorySummaryDraftApprovePayload.serializer(),
                approvalRequest.payload,
            )
            assertEquals("draft-runtime-memory", approvalPayload.draftId)
            assertTrue(approvalPayload.enabled == true)
            assertEquals("runtime-session", approvalPayload.expectedSessionId)
            assertEquals(6, approvalPayload.expectedSourceMessageCount)
            assertEquals(setOf("draft-runtime-memory"), fixture.viewModel.state.value.approvingMemorySummaryDraftIds)

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.MemorySummaryDraftApprove,
                    serializer = MemorySummaryDraftApproveResultPayload.serializer(),
                    payload = MemorySummaryDraftApproveResultPayload(
                        draftId = "draft-runtime-memory",
                        status = "approved",
                        entry = MemoryEntryPayload(
                            id = "memory-summary:draft-runtime-memory",
                            content = "Prefer concise Korean release-note summaries.",
                            enabled = true,
                            createdAt = "2026-06-25T00:00:00Z",
                            updatedAt = "2026-06-25T00:01:00Z",
                            source = MemoryEntrySourcePayload(
                                kind = "long_inactivity_summary_draft",
                                draftId = "draft-runtime-memory",
                                summaryMethod = "deterministic_preview",
                                session = MemorySummaryDraftSessionPayload(
                                    sessionId = "runtime-session",
                                    title = "Long idle planning chat",
                                    model = "ollama:qwen3:8b",
                                    lastActivityAt = "2026-06-01T00:00:00Z",
                                    messageCount = 6,
                                    inactiveSeconds = 1_209_600L,
                                ),
                                sourceMessageCount = 6,
                                sourceRange = "visible messages 1-6 of 6",
                                sourcePointers = listOf(
                                    MemorySummaryDraftSourcePointerPayload(
                                        sessionId = "runtime-session",
                                        messageIndex = 1,
                                        role = "user",
                                        createdAt = "2026-06-01T00:00:00Z",
                                        excerpt = "Use concise Korean summaries for release notes.",
                                    ),
                                ),
                            ),
                        ),
                    ),
                    requestId = approvalRequest.requestId,
                ),
            )
            advanceUntilIdle()

            val approvedMemory = fixture.viewModel.state.value.memoryEntries.single()
            assertEquals(
                listOf("Prefer concise Korean release-note summaries."),
                fixture.viewModel.state.value.memoryEntries.map { it.content },
            )
            assertEquals("draft-runtime-memory", approvedMemory.source?.draftId)
            assertEquals("deterministic_preview", approvedMemory.source?.summaryMethod)
            assertEquals("runtime-session", approvedMemory.source?.session?.sessionId)
            assertEquals("visible messages 1-6 of 6", approvedMemory.source?.sourceRange)
            assertEquals(
                listOf("Use concise Korean summaries for release notes."),
                approvedMemory.source?.sourcePointers?.map { it.excerpt },
            )
            assertTrue(fixture.viewModel.state.value.memorySummaryDrafts.isEmpty())
            assertTrue(fixture.viewModel.state.value.approvingMemorySummaryDraftIds.isEmpty())
            assertTrue(fixture.localStore.data.memoryEntries.isEmpty())
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun memorySummaryDraftApproveResultRejectsUnknownMetadataBeforeMemoryMutation() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )
            val initialDraftRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.MemorySummaryDraftsList
            }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.MemorySummaryDraftsList,
                    serializer = MemorySummaryDraftsListResultPayload.serializer(),
                    payload = MemorySummaryDraftsListResultPayload(
                        drafts = listOf(memorySummaryDraftPayload(id = "draft-approve-guard")),
                    ),
                    requestId = initialDraftRequest.requestId,
                ),
            )
            advanceUntilIdle()

            fixture.viewModel.approveMemorySummaryDraft("draft-approve-guard")
            advanceUntilIdle()
            val approvalRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.MemorySummaryDraftApprove
            }
            assertEquals(setOf("draft-approve-guard"), fixture.viewModel.state.value.approvingMemorySummaryDraftIds)

            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.MemorySummaryDraftApprove,
                    requestId = approvalRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "draft_id": "draft-approve-guard",
                              "status": "approved",
                              "entry": {
                                "id": "memory-summary:draft-approve-guard",
                                "content": "Leaky approved memory",
                                "enabled": true,
                                "created_at": "2026-06-25T00:00:00Z",
                                "updated_at": "2026-06-25T00:01:00Z",
                                "source": {
                                  "kind": "long_inactivity_summary_draft",
                                  "draft_id": "draft-approve-guard",
                                  "summary_method": "deterministic_preview",
                                  "session": {
                                    "session_id": "runtime-session",
                                    "title": "Long idle planning chat",
                                    "model": "ollama:qwen3:8b",
                                    "last_activity_at": "2026-06-01T00:00:00Z",
                                    "message_count": 6,
                                    "inactive_seconds": 1209600
                                  },
                                  "source_message_count": 6,
                                  "source_range": "visible messages 1-6 of 6",
                                  "source_pointers": [
                                    {
                                      "session_id": "runtime-session",
                                      "message_index": 1,
                                      "role": "user",
                                      "created_at": "2026-06-01T00:00:00Z",
                                      "excerpt": "Use concise Korean summaries for release notes.",
                                      "backend_url": "http://127.0.0.1:11434"
                                    }
                                  ]
                                }
                              }
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val rejectedState = fixture.viewModel.state.value
            assertEquals("invalid_payload", rejectedState.error?.code)
            assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("memory.summary.draft.approve"))
            assertTrue(
                rejectedState.error?.technicalDetail.orEmpty()
                    .contains("entry.source.source_pointers[0].backend_url"),
            )
            assertEquals(listOf("draft-approve-guard"), rejectedState.memorySummaryDrafts.map { it.id })
            assertEquals(setOf("draft-approve-guard"), rejectedState.approvingMemorySummaryDraftIds)
            assertTrue(rejectedState.memoryEntries.isEmpty())
            assertTrue(fixture.localStore.data.memoryEntries.isEmpty())
            val rejectedPersistedSnapshot = json.encodeToString(fixture.localStore.data)
            assertFalse(rejectedPersistedSnapshot.contains("Leaky approved memory"))
            assertFalse(rejectedPersistedSnapshot.contains("127.0.0.1"))

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.MemorySummaryDraftApprove,
                    serializer = MemorySummaryDraftApproveResultPayload.serializer(),
                    payload = MemorySummaryDraftApproveResultPayload(
                        draftId = "draft-approve-guard",
                        status = "approved",
                        entry = memorySummaryDraftApprovedEntryPayload(
                            draftId = "draft-approve-guard",
                            memoryId = "memory-summary:draft-approve-guard",
                            content = "Canonical approved memory",
                        ),
                    ),
                    requestId = approvalRequest.requestId,
                ),
            )
            advanceUntilIdle()

            val acceptedState = fixture.viewModel.state.value
            assertNull(acceptedState.error)
            assertTrue(acceptedState.memorySummaryDrafts.isEmpty())
            assertTrue(acceptedState.approvingMemorySummaryDraftIds.isEmpty())
            assertEquals(listOf("Canonical approved memory"), acceptedState.memoryEntries.map { it.content })
            assertTrue(fixture.localStore.data.memoryEntries.isEmpty())
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun approveMemorySummaryDraftErrorClearsPendingAndAllowsRetry() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )
            val initialDraftRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.MemorySummaryDraftsList
            }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.MemorySummaryDraftsList,
                    serializer = MemorySummaryDraftsListResultPayload.serializer(),
                    payload = MemorySummaryDraftsListResultPayload(
                        drafts = listOf(
                            MemorySummaryDraftPayload(
                                id = "draft-stale",
                                session = MemorySummaryDraftSessionPayload(
                                    sessionId = "runtime-session",
                                    title = "Long idle planning chat",
                                    model = "ollama:qwen3:8b",
                                    lastActivityAt = "2026-06-01T00:00:00Z",
                                    messageCount = 6,
                                    inactiveSeconds = 1_209_600L,
                                ),
                                sourceMessageCount = 6,
                                sourceRange = "visible messages 1-6 of 6",
                                sourcePointers = listOf(
                                    MemorySummaryDraftSourcePointerPayload(
                                        sessionId = "runtime-session",
                                        messageIndex = 1,
                                        role = "user",
                                        createdAt = "2026-06-01T00:00:00Z",
                                        excerpt = "Use concise Korean summaries for release notes.",
                                    ),
                                ),
                                summaryPreview = "Prefer concise Korean release-note summaries.",
                            ),
                        ),
                    ),
                    requestId = initialDraftRequest.requestId,
                ),
            )
            advanceUntilIdle()

            fixture.viewModel.approveMemorySummaryDraft("draft-stale")
            advanceUntilIdle()
            val firstApprovalRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.MemorySummaryDraftApprove
            }
            assertEquals(setOf("draft-stale"), fixture.viewModel.state.value.approvingMemorySummaryDraftIds)

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.Error,
                    serializer = ErrorPayload.serializer(),
                    payload = ErrorPayload(
                        code = "memory_summary_draft_stale",
                        message = "Memory summary draft changed before approval.",
                        retryable = false,
                    ),
                    requestId = firstApprovalRequest.requestId,
                ),
            )
            advanceUntilIdle()

            assertTrue(fixture.viewModel.state.value.approvingMemorySummaryDraftIds.isEmpty())
            assertEquals("memory_summary_draft_approval_failed", fixture.viewModel.state.value.error?.code)
            assertEquals(
                "Memory summary draft changed before approval.",
                fixture.viewModel.state.value.error?.technicalDetail,
            )
            assertEquals(listOf("draft-stale"), fixture.viewModel.state.value.memorySummaryDrafts.map { it.id })
            assertTrue(fixture.viewModel.state.value.memoryEntries.isEmpty())
            assertTrue(fixture.localStore.data.memoryEntries.isEmpty())

            fixture.viewModel.approveMemorySummaryDraft("draft-stale")
            advanceUntilIdle()
            assertEquals(
                2,
                fixture.channel.sentEnvelopes.count { it.type == MessageType.MemorySummaryDraftApprove },
            )
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun dismissMemorySummaryDraftSendsExpectedDecisionAndRemovesDraft() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )
            val initialDraftRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.MemorySummaryDraftsList
            }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.MemorySummaryDraftsList,
                    serializer = MemorySummaryDraftsListResultPayload.serializer(),
                    payload = MemorySummaryDraftsListResultPayload(
                        drafts = listOf(
                            MemorySummaryDraftPayload(
                                id = "draft-dismiss-runtime-memory",
                                session = MemorySummaryDraftSessionPayload(
                                    sessionId = "runtime-session",
                                    title = "Long idle planning chat",
                                    model = "ollama:qwen3:8b",
                                    lastActivityAt = "2026-06-01T00:00:00Z",
                                    messageCount = 6,
                                    inactiveSeconds = 1_209_600L,
                                ),
                                sourceMessageCount = 6,
                                sourceRange = "visible messages 1-6 of 6",
                                sourcePointers = listOf(
                                    MemorySummaryDraftSourcePointerPayload(
                                        sessionId = "runtime-session",
                                        messageIndex = 1,
                                        role = "user",
                                        createdAt = "2026-06-01T00:00:00Z",
                                        excerpt = "Use concise Korean summaries for release notes.",
                                    ),
                                ),
                                summaryPreview = "Prefer concise Korean release-note summaries.",
                            ),
                        ),
                    ),
                    requestId = initialDraftRequest.requestId,
                ),
            )
            advanceUntilIdle()

            fixture.viewModel.dismissMemorySummaryDraft("draft-dismiss-runtime-memory")
            advanceUntilIdle()

            val dismissRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.MemorySummaryDraftDismiss
            }
            val dismissPayload = json.decodeFromJsonElement(
                MemorySummaryDraftDismissPayload.serializer(),
                dismissRequest.payload,
            )
            assertEquals("draft-dismiss-runtime-memory", dismissPayload.draftId)
            assertEquals("runtime-session", dismissPayload.expectedSessionId)
            assertEquals(6, dismissPayload.expectedSourceMessageCount)
            assertEquals(setOf("draft-dismiss-runtime-memory"), fixture.viewModel.state.value.dismissingMemorySummaryDraftIds)

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.MemorySummaryDraftDismiss,
                    serializer = MemorySummaryDraftDismissResultPayload.serializer(),
                    payload = MemorySummaryDraftDismissResultPayload(
                        draftId = "draft-dismiss-runtime-memory",
                        status = "dismissed",
                        dismissedAt = "2026-06-25T00:01:00Z",
                    ),
                    requestId = dismissRequest.requestId,
                ),
            )
            advanceUntilIdle()

            assertTrue(fixture.viewModel.state.value.memorySummaryDrafts.isEmpty())
            assertTrue(fixture.viewModel.state.value.dismissingMemorySummaryDraftIds.isEmpty())
            assertTrue(fixture.viewModel.state.value.memoryEntries.isEmpty())
            assertTrue(fixture.localStore.data.memoryEntries.isEmpty())
            assertNull(fixture.viewModel.state.value.error)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun memorySummaryDraftDismissResultRejectsUnknownMetadataBeforeReviewStateMutation() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )
            val initialDraftRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.MemorySummaryDraftsList
            }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.MemorySummaryDraftsList,
                    serializer = MemorySummaryDraftsListResultPayload.serializer(),
                    payload = MemorySummaryDraftsListResultPayload(
                        drafts = listOf(memorySummaryDraftPayload(id = "draft-dismiss-guard")),
                    ),
                    requestId = initialDraftRequest.requestId,
                ),
            )
            advanceUntilIdle()

            fixture.viewModel.dismissMemorySummaryDraft("draft-dismiss-guard")
            advanceUntilIdle()
            val dismissRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.MemorySummaryDraftDismiss
            }
            assertEquals(setOf("draft-dismiss-guard"), fixture.viewModel.state.value.dismissingMemorySummaryDraftIds)

            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.MemorySummaryDraftDismiss,
                    requestId = dismissRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "draft_id": "draft-dismiss-guard",
                              "status": "dismissed",
                              "dismissed_at": "2026-06-25T00:01:00Z",
                              "workspace_id": "workspace-canary"
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val rejectedState = fixture.viewModel.state.value
            assertEquals("invalid_payload", rejectedState.error?.code)
            assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("memory.summary.draft.dismiss"))
            assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("workspace_id"))
            assertEquals(listOf("draft-dismiss-guard"), rejectedState.memorySummaryDrafts.map { it.id })
            assertEquals(setOf("draft-dismiss-guard"), rejectedState.dismissingMemorySummaryDraftIds)
            assertTrue(rejectedState.memoryEntries.isEmpty())
            assertTrue(fixture.localStore.data.memoryEntries.isEmpty())
            val rejectedPersistedSnapshot = json.encodeToString(fixture.localStore.data)
            assertFalse(rejectedPersistedSnapshot.contains("workspace-canary"))

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.MemorySummaryDraftDismiss,
                    serializer = MemorySummaryDraftDismissResultPayload.serializer(),
                    payload = MemorySummaryDraftDismissResultPayload(
                        draftId = "draft-dismiss-guard",
                        status = "dismissed",
                        dismissedAt = "2026-06-25T00:01:00Z",
                    ),
                    requestId = dismissRequest.requestId,
                ),
            )
            advanceUntilIdle()

            val acceptedState = fixture.viewModel.state.value
            assertNull(acceptedState.error)
            assertTrue(acceptedState.memorySummaryDrafts.isEmpty())
            assertTrue(acceptedState.dismissingMemorySummaryDraftIds.isEmpty())
            assertTrue(acceptedState.memoryEntries.isEmpty())
            assertTrue(fixture.localStore.data.memoryEntries.isEmpty())
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun dismissMemorySummaryDraftErrorClearsPendingAndAllowsRetry() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )
            val initialDraftRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.MemorySummaryDraftsList
            }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.MemorySummaryDraftsList,
                    serializer = MemorySummaryDraftsListResultPayload.serializer(),
                    payload = MemorySummaryDraftsListResultPayload(
                        drafts = listOf(
                            MemorySummaryDraftPayload(
                                id = "draft-dismiss-stale",
                                session = MemorySummaryDraftSessionPayload(
                                    sessionId = "runtime-session",
                                    title = "Long idle planning chat",
                                    model = "ollama:qwen3:8b",
                                    lastActivityAt = "2026-06-01T00:00:00Z",
                                    messageCount = 6,
                                    inactiveSeconds = 1_209_600L,
                                ),
                                sourceMessageCount = 6,
                                sourceRange = "visible messages 1-6 of 6",
                                sourcePointers = listOf(
                                    MemorySummaryDraftSourcePointerPayload(
                                        sessionId = "runtime-session",
                                        messageIndex = 1,
                                        role = "user",
                                        createdAt = "2026-06-01T00:00:00Z",
                                        excerpt = "Use concise Korean summaries for release notes.",
                                    ),
                                ),
                                summaryPreview = "Prefer concise Korean release-note summaries.",
                            ),
                        ),
                    ),
                    requestId = initialDraftRequest.requestId,
                ),
            )
            advanceUntilIdle()

            fixture.viewModel.dismissMemorySummaryDraft("draft-dismiss-stale")
            advanceUntilIdle()
            val firstDismissRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.MemorySummaryDraftDismiss
            }
            assertEquals(setOf("draft-dismiss-stale"), fixture.viewModel.state.value.dismissingMemorySummaryDraftIds)

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.Error,
                    serializer = ErrorPayload.serializer(),
                    payload = ErrorPayload(
                        code = "memory_summary_draft_stale",
                        message = "Memory summary draft changed before dismissal.",
                        retryable = false,
                    ),
                    requestId = firstDismissRequest.requestId,
                ),
            )
            advanceUntilIdle()

            assertTrue(fixture.viewModel.state.value.dismissingMemorySummaryDraftIds.isEmpty())
            assertEquals("memory_summary_draft_dismiss_failed", fixture.viewModel.state.value.error?.code)
            assertEquals(
                "Memory summary draft changed before dismissal.",
                fixture.viewModel.state.value.error?.technicalDetail,
            )
            assertEquals(
                listOf("draft-dismiss-stale"),
                fixture.viewModel.state.value.memorySummaryDrafts.map { it.id },
            )
            assertTrue(fixture.viewModel.state.value.memoryEntries.isEmpty())
            assertTrue(fixture.localStore.data.memoryEntries.isEmpty())

            fixture.viewModel.dismissMemorySummaryDraft("draft-dismiss-stale")
            advanceUntilIdle()
            assertEquals(
                2,
                fixture.channel.sentEnvelopes.count { it.type == MessageType.MemorySummaryDraftDismiss },
            )
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun refreshRuntimeMemorySearchDoesNotSendSelectedEmbeddingModelHint() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val selectedEmbeddingModel = embeddingModel()
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel(), selectedEmbeddingModel),
                selectedEmbeddingModelId = selectedEmbeddingModel.id,
                redactRuntimeOwnedLocalDataOnSave = true,
            )
            val initialMemoryListRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.MemoryList }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.MemoryList,
                    serializer = MemoryListResultPayload.serializer(),
                    payload = MemoryListResultPayload(entries = emptyList()),
                    requestId = initialMemoryListRequest.requestId,
                ),
            )
            advanceUntilIdle()

            fixture.viewModel.refreshRuntimeMemory(query = "  durable route notes  ")
            advanceUntilIdle()

            val queryRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.MemoryList }
            val queryPayload = json.decodeFromJsonElement(
                MemoryListRequestPayload.serializer(),
                queryRequest.payload,
            )
            assertEquals("durable route notes", queryPayload.query)
            assertNull(queryRequest.payload["embedding_model_id"])
            assertFalse(json.encodeToString(queryRequest.payload).contains(selectedEmbeddingModel.id))
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun memoryListRejectsUnknownMetadataBeforeMemoryStatePublication() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val initialData = PersistedRuntimeData(
                memoryEntries = listOf(
                    PersistedMemoryEntry(
                        id = "existing-memory",
                        content = "Existing memory",
                        enabled = true,
                        createdAtMillis = 100L,
                        updatedAtMillis = 200L,
                    ),
                ),
            )
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                initialData = initialData,
            )
            val initialMemoryRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.MemoryList
            }

            fun assertExistingMemoryPreserved() {
                assertEquals(
                    listOf("Existing memory"),
                    fixture.viewModel.state.value.memoryEntries.map { it.content },
                )
                assertEquals(
                    listOf("Existing memory"),
                    fixture.localStore.data.memoryEntries.map { it.content },
                )
            }

            assertExistingMemoryPreserved()

            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.MemoryList,
                    requestId = initialMemoryRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "entries": [
                                {
                                  "id": "leaky-memory-top-level",
                                  "content": "Leaky top-level memory",
                                  "enabled": true
                                }
                              ],
                              "backend_url": "http://127.0.0.1:11434"
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val rejectedTopLevelState = fixture.viewModel.state.value
            assertEquals("invalid_payload", rejectedTopLevelState.error?.code)
            assertTrue(rejectedTopLevelState.error?.technicalDetail.orEmpty().contains("memory.list"))
            assertTrue(rejectedTopLevelState.error?.technicalDetail.orEmpty().contains("backend_url"))
            assertExistingMemoryPreserved()

            fixture.viewModel.refreshRuntimeMemory()
            advanceUntilIdle()
            val entryMetadataRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.MemoryList
            }
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.MemoryList,
                    requestId = entryMetadataRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "entries": [
                                {
                                  "id": "leaky-memory-entry",
                                  "content": "Leaky entry memory",
                                  "enabled": true,
                                  "workspace_id": "workspace-canary"
                                }
                              ]
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val rejectedEntryState = fixture.viewModel.state.value
            assertEquals("invalid_payload", rejectedEntryState.error?.code)
            assertTrue(rejectedEntryState.error?.technicalDetail.orEmpty().contains("memory.list"))
            assertTrue(rejectedEntryState.error?.technicalDetail.orEmpty().contains("entries[0].workspace_id"))
            assertExistingMemoryPreserved()

            fixture.viewModel.refreshRuntimeMemory()
            advanceUntilIdle()
            val sourceMetadataRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.MemoryList
            }
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.MemoryList,
                    requestId = sourceMetadataRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "entries": [
                                {
                                  "id": "leaky-memory-source",
                                  "content": "Leaky source memory",
                                  "enabled": true,
                                  "source": {
                                    "kind": "long_inactivity_summary_draft",
                                    "draft_id": "long-inactivity:session-1:1000:6",
                                    "summary_method": "deterministic_preview",
                                    "session": {
                                      "session_id": "session-1",
                                      "title": "Runtime notes",
                                      "model": "ollama:llama3.1:8b",
                                      "last_activity_at": "2026-06-25T00:00:00Z",
                                      "message_count": 6,
                                      "inactive_seconds": 1209600
                                    },
                                    "source_message_count": 6,
                                    "source_range": "visible messages 1-6 of 6",
                                    "source_pointers": [
                                      {
                                        "session_id": "session-1",
                                        "message_index": 1,
                                        "role": "user",
                                        "created_at": "2026-06-25T00:00:00Z",
                                        "excerpt": "Remember route recovery steps."
                                      }
                                    ],
                                    "source_path": "/Users/hanchangha/private-memory.jsonl"
                                  }
                                }
                              ]
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val rejectedSourceState = fixture.viewModel.state.value
            assertEquals("invalid_payload", rejectedSourceState.error?.code)
            assertTrue(rejectedSourceState.error?.technicalDetail.orEmpty().contains("memory.list"))
            assertTrue(
                rejectedSourceState.error?.technicalDetail.orEmpty()
                    .contains("entries[0].source.source_path"),
            )
            assertExistingMemoryPreserved()

            fixture.viewModel.refreshRuntimeMemory()
            advanceUntilIdle()
            val pointerMetadataRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.MemoryList
            }
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.MemoryList,
                    requestId = pointerMetadataRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "entries": [
                                {
                                  "id": "leaky-memory-pointer",
                                  "content": "Leaky pointer memory",
                                  "enabled": true,
                                  "source": {
                                    "kind": "long_inactivity_summary_draft",
                                    "draft_id": "long-inactivity:session-1:1000:6",
                                    "summary_method": "deterministic_preview",
                                    "session": {
                                      "session_id": "session-1",
                                      "title": "Runtime notes",
                                      "model": "ollama:llama3.1:8b",
                                      "last_activity_at": "2026-06-25T00:00:00Z",
                                      "message_count": 6,
                                      "inactive_seconds": 1209600
                                    },
                                    "source_message_count": 6,
                                    "source_range": "visible messages 1-6 of 6",
                                    "source_pointers": [
                                      {
                                        "session_id": "session-1",
                                        "message_index": 1,
                                        "role": "user",
                                        "created_at": "2026-06-25T00:00:00Z",
                                        "excerpt": "Remember route recovery steps.",
                                        "backend_url": "http://127.0.0.1:1234"
                                      }
                                    ]
                                  }
                                }
                              ]
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val rejectedPointerState = fixture.viewModel.state.value
            assertEquals("invalid_payload", rejectedPointerState.error?.code)
            assertTrue(rejectedPointerState.error?.technicalDetail.orEmpty().contains("memory.list"))
            assertTrue(
                rejectedPointerState.error?.technicalDetail.orEmpty()
                    .contains("entries[0].source.source_pointers[0].backend_url"),
            )
            assertExistingMemoryPreserved()
            val storedJson = json.encodeToString(fixture.localStore.data)
            assertFalse(storedJson.contains("workspace-canary"))
            assertFalse(storedJson.contains("private-memory.jsonl"))
            assertFalse(storedJson.contains("127.0.0.1:1234"))

            fixture.viewModel.refreshRuntimeMemory()
            advanceUntilIdle()
            val canonicalRetryRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.MemoryList
            }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.MemoryList,
                    serializer = MemoryListResultPayload.serializer(),
                    payload = MemoryListResultPayload(
                        entries = listOf(
                            MemoryEntryPayload(
                                id = "canonical-memory",
                                content = "Canonical runtime memory",
                                enabled = true,
                                createdAt = "2026-06-25T00:00:00Z",
                                updatedAt = "2026-06-25T00:01:00Z",
                            ),
                        ),
                    ),
                    requestId = canonicalRetryRequest.requestId,
                ),
            )
            advanceUntilIdle()

            val retryState = fixture.viewModel.state.value
            assertNull(retryState.error)
            assertEquals(listOf("Canonical runtime memory"), retryState.memoryEntries.map { it.content })
            assertEquals(listOf("Canonical runtime memory"), fixture.localStore.data.memoryEntries.map { it.content })
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun memoryUpsertResultRejectsUnknownMetadataBeforeMemoryMutation() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val initialData = PersistedRuntimeData(
                memoryEntries = listOf(
                    PersistedMemoryEntry(
                        id = "existing-memory",
                        content = "Existing memory",
                        enabled = true,
                        createdAtMillis = 100L,
                        updatedAtMillis = 200L,
                    ),
                ),
            )
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                initialData = initialData,
            )

            fun assertExistingMemoryPreserved() {
                assertEquals(
                    listOf("Existing memory"),
                    fixture.viewModel.state.value.memoryEntries.map { it.content },
                )
                assertEquals(
                    listOf("Existing memory"),
                    fixture.localStore.data.memoryEntries.map { it.content },
                )
            }

            assertExistingMemoryPreserved()

            fixture.viewModel.addMemoryEntry("New runtime memory")
            advanceUntilIdle()
            val upsertRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.MemoryUpsert
            }

            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.MemoryUpsert,
                    requestId = upsertRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "entry": {
                                "id": "leaky-upsert-memory",
                                "content": "Leaky upsert memory",
                                "enabled": true,
                                "created_at": "2026-06-25T00:00:00Z",
                                "updated_at": "2026-06-25T00:01:00Z",
                                "source": {
                                  "kind": "long_inactivity_summary_draft",
                                  "draft_id": "long-inactivity:session-1:1000:6",
                                  "summary_method": "deterministic_preview",
                                  "session": {
                                    "session_id": "session-1",
                                    "title": "Runtime notes",
                                    "model": "ollama:llama3.1:8b",
                                    "last_activity_at": "2026-06-25T00:00:00Z",
                                    "message_count": 6,
                                    "inactive_seconds": 1209600
                                  },
                                  "source_message_count": 6,
                                  "source_range": "visible messages 1-6 of 6",
                                  "source_pointers": [
                                    {
                                      "session_id": "session-1",
                                      "message_index": 1,
                                      "role": "user",
                                      "created_at": "2026-06-25T00:00:00Z",
                                      "excerpt": "Remember route recovery steps.",
                                      "backend_url": "http://127.0.0.1:11434"
                                    }
                                  ]
                                }
                              }
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val rejectedState = fixture.viewModel.state.value
            assertEquals("invalid_payload", rejectedState.error?.code)
            assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("memory.upsert"))
            assertTrue(
                rejectedState.error?.technicalDetail.orEmpty()
                    .contains("entry.source.source_pointers[0].backend_url"),
            )
            assertExistingMemoryPreserved()
            val rejectedStoredJson = json.encodeToString(fixture.localStore.data)
            assertFalse(rejectedStoredJson.contains("Leaky upsert memory"))
            assertFalse(rejectedStoredJson.contains("127.0.0.1:11434"))

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.MemoryUpsert,
                    serializer = MemoryUpsertResultPayload.serializer(),
                    payload = MemoryUpsertResultPayload(
                        entry = MemoryEntryPayload(
                            id = "canonical-upsert-memory",
                            content = "Canonical upsert memory",
                            enabled = true,
                            createdAt = "2026-06-25T00:00:00Z",
                            updatedAt = "2026-06-25T00:01:00Z",
                        ),
                    ),
                    requestId = upsertRequest.requestId,
                ),
            )
            advanceUntilIdle()

            val acceptedState = fixture.viewModel.state.value
            assertNull(acceptedState.error)
            assertEquals(
                listOf("Canonical upsert memory", "Existing memory"),
                acceptedState.memoryEntries.map { it.content },
            )
            assertEquals(
                listOf("Canonical upsert memory", "Existing memory"),
                fixture.localStore.data.memoryEntries.map { it.content },
            )
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun memoryDeleteResultRejectsUnknownMetadataBeforeMemoryMutation() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val initialData = PersistedRuntimeData(
                memoryEntries = listOf(
                    PersistedMemoryEntry(
                        id = "delete-target",
                        content = "Delete target memory",
                        enabled = true,
                        createdAtMillis = 100L,
                        updatedAtMillis = 200L,
                    ),
                    PersistedMemoryEntry(
                        id = "keep-memory",
                        content = "Keep memory",
                        enabled = true,
                        createdAtMillis = 300L,
                        updatedAtMillis = 400L,
                    ),
                ),
            )
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                initialData = initialData,
            )

            fun assertDeleteTargetPreserved() {
                assertEquals(
                    setOf("Delete target memory", "Keep memory"),
                    fixture.viewModel.state.value.memoryEntries.map { it.content }.toSet(),
                )
                assertEquals(
                    setOf("Delete target memory", "Keep memory"),
                    fixture.localStore.data.memoryEntries.map { it.content }.toSet(),
                )
            }

            assertDeleteTargetPreserved()

            fixture.viewModel.removeMemoryEntry("delete-target")
            advanceUntilIdle()
            val deleteRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.MemoryDelete
            }

            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.MemoryDelete,
                    requestId = deleteRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "id": "delete-target",
                              "deleted_at": "2026-06-25T00:01:00Z",
                              "workspace_id": "workspace-canary"
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val rejectedState = fixture.viewModel.state.value
            assertEquals("invalid_payload", rejectedState.error?.code)
            assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("memory.delete"))
            assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("workspace_id"))
            assertDeleteTargetPreserved()
            val rejectedStoredJson = json.encodeToString(fixture.localStore.data)
            assertFalse(rejectedStoredJson.contains("workspace-canary"))

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.MemoryDelete,
                    serializer = MemoryDeleteResultPayload.serializer(),
                    payload = MemoryDeleteResultPayload(
                        id = "delete-target",
                        deletedAt = "2026-06-25T00:01:00Z",
                    ),
                    requestId = deleteRequest.requestId,
                ),
            )
            advanceUntilIdle()

            val acceptedState = fixture.viewModel.state.value
            assertNull(acceptedState.error)
            assertEquals(listOf("Keep memory"), acceptedState.memoryEntries.map { it.content })
            assertEquals(listOf("Keep memory"), fixture.localStore.data.memoryEntries.map { it.content })
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun errorPayloadRejectsUnknownMetadataBeforePendingStateMutation() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
            )
            val initialMemoryRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.MemoryList
            }
            val memoryRequestCountBeforeRejectedError = fixture.channel.sentEnvelopes.count {
                it.type == MessageType.MemoryList
            }

            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.Error,
                    requestId = initialMemoryRequest.requestId,
                    payload = buildJsonObject {
                        put("code", "memory_store_unavailable")
                        put("message", "Memory store unavailable.")
                        put("retryable", true)
                        put("backend_url", "http://127.0.0.1:11434")
                    },
                ),
            )
            advanceUntilIdle()

            val rejectedState = fixture.viewModel.state.value
            assertEquals("invalid_payload", rejectedState.error?.code)
            assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("error response"))
            assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("backend_url"))
            fixture.viewModel.refreshRuntimeMemory()
            advanceUntilIdle()
            assertEquals(
                memoryRequestCountBeforeRejectedError,
                fixture.channel.sentEnvelopes.count { it.type == MessageType.MemoryList },
            )

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.Error,
                    serializer = ErrorPayload.serializer(),
                    payload = ErrorPayload(
                        code = "memory_store_unavailable",
                        message = "Memory store unavailable.",
                        retryable = true,
                    ),
                    requestId = initialMemoryRequest.requestId,
                ),
            )
            advanceUntilIdle()

            assertEquals("memory_load_failed", fixture.viewModel.state.value.error?.code)
            assertEquals(
                "Memory store unavailable.",
                fixture.viewModel.state.value.error?.technicalDetail,
            )
            fixture.viewModel.refreshRuntimeMemory()
            advanceUntilIdle()
            assertEquals(
                memoryRequestCountBeforeRejectedError + 1,
                fixture.channel.sentEnvelopes.count { it.type == MessageType.MemoryList },
            )
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun errorPayloadRejectsUnknownMetadataBeforeActiveStreamTermination() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
            )
            fixture.viewModel.replaceStateForTest {
                it.copy(chatInput = "Explain runtime error metadata boundaries")
            }

            fixture.viewModel.sendChatMessage()
            advanceUntilIdle()

            val sendEnvelope = fixture.channel.sentEnvelopes.last { it.type == MessageType.ChatSend }
            val sessionId = requireNotNull(fixture.viewModel.state.value.activeChatSessionId)
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.Error,
                    requestId = sendEnvelope.requestId,
                    payload = buildJsonObject {
                        put("code", "backend_unavailable")
                        put("message", "Backend unavailable.")
                        put("retryable", true)
                        put("workspace_id", "workspace-canary")
                    },
                ),
            )
            advanceUntilIdle()

            val rejectedState = fixture.viewModel.state.value
            assertEquals("invalid_payload", rejectedState.error?.code)
            assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("error response"))
            assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("workspace_id"))
            assertTrue(rejectedState.isStreaming)
            assertEquals(sendEnvelope.requestId, rejectedState.activeRequestId)
            assertEquals(
                listOf("Explain runtime error metadata boundaries", ""),
                rejectedState.messages.map { it.content },
            )
            val rejectedStoredJson = json.encodeToString(fixture.localStore.data)
            assertFalse(rejectedStoredJson.contains("workspace-canary"))

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.Error,
                    serializer = ErrorPayload.serializer(),
                    payload = ErrorPayload(
                        code = "backend_unavailable",
                        message = "Backend unavailable.",
                        retryable = true,
                    ),
                    requestId = sendEnvelope.requestId,
                ),
            )
            advanceUntilIdle()

            val acceptedState = fixture.viewModel.state.value
            assertEquals("backend_unavailable", acceptedState.error?.code)
            assertFalse(acceptedState.isStreaming)
            assertNull(acceptedState.activeRequestId)
            assertEquals(
                listOf("Explain runtime error metadata boundaries"),
                acceptedState.messages.map { it.content },
            )
            val savedSession = fixture.localStore.data.sessions.single { it.id == sessionId }
            assertEquals(
                listOf("Explain runtime error metadata boundaries"),
                savedSession.messages.map { it.content },
            )
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun chatSessionsListRejectsUnknownMetadataBeforeHistoryStatePublication() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )
            val initialChatSessionsRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.ChatSessionsList
            }

            fun assertNoRuntimeHistoryPublished() {
                assertTrue(fixture.viewModel.state.value.chatSessions.isEmpty())
                assertTrue(fixture.viewModel.state.value.archivedChatSessions.isEmpty())
                assertTrue(fixture.localStore.data.sessions.isEmpty())
            }

            assertNoRuntimeHistoryPublished()

            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.ChatSessionsList,
                    requestId = initialChatSessionsRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "sessions": [
                                {
                                  "session_id": "leaky-chat-history",
                                  "title": "Leaky chat history",
                                  "model": "ollama:llama3.1:8b",
                                  "last_activity_at": "2026-06-25T00:00:00Z",
                                  "message_count": 2,
                                  "status": "active",
                                  "last_event": "done"
                                }
                              ],
                              "backend_url": "http://127.0.0.1:11434"
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val rejectedTopLevelState = fixture.viewModel.state.value
            assertEquals("invalid_payload", rejectedTopLevelState.error?.code)
            assertTrue(rejectedTopLevelState.error?.technicalDetail.orEmpty().contains("chat.sessions.list"))
            assertTrue(rejectedTopLevelState.error?.technicalDetail.orEmpty().contains("backend_url"))
            assertNoRuntimeHistoryPublished()

            fixture.viewModel.refreshRuntimeChatHistory()
            advanceUntilIdle()
            val sessionMetadataRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.ChatSessionsList
            }
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.ChatSessionsList,
                    requestId = sessionMetadataRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "sessions": [
                                {
                                  "session_id": "leaky-session-metadata",
                                  "title": "Leaky session metadata",
                                  "model": "ollama:llama3.1:8b",
                                  "last_activity_at": "2026-06-25T00:01:00Z",
                                  "message_count": 3,
                                  "status": "active",
                                  "last_event": "done",
                                  "workspace_id": "workspace-canary"
                                }
                              ]
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val rejectedSessionMetadataState = fixture.viewModel.state.value
            assertEquals("invalid_payload", rejectedSessionMetadataState.error?.code)
            assertTrue(rejectedSessionMetadataState.error?.technicalDetail.orEmpty().contains("chat.sessions.list"))
            assertTrue(rejectedSessionMetadataState.error?.technicalDetail.orEmpty().contains("sessions[0].workspace_id"))
            assertNoRuntimeHistoryPublished()

            fixture.viewModel.refreshRuntimeChatHistory()
            advanceUntilIdle()
            val searchMetadataRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.ChatSessionsList
            }
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.ChatSessionsList,
                    requestId = searchMetadataRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "sessions": [
                                {
                                  "session_id": "leaky-search-metadata",
                                  "title": "Leaky search metadata",
                                  "model": "ollama:llama3.1:8b",
                                  "last_activity_at": "2026-06-25T00:02:00Z",
                                  "message_count": 4,
                                  "status": "active",
                                  "last_event": "done",
                                  "search": {
                                    "rank": 1,
                                    "snippet": "Relay route matched the session title.",
                                    "matched_fields": ["title"],
                                    "source_path": "/Users/hanchangha/private-chat-history.jsonl"
                                  }
                                }
                              ]
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val rejectedSearchMetadataState = fixture.viewModel.state.value
            assertEquals("invalid_payload", rejectedSearchMetadataState.error?.code)
            assertTrue(rejectedSearchMetadataState.error?.technicalDetail.orEmpty().contains("chat.sessions.list"))
            assertTrue(
                rejectedSearchMetadataState.error?.technicalDetail.orEmpty()
                    .contains("sessions[0].search.source_path"),
            )
            assertNoRuntimeHistoryPublished()

            fixture.viewModel.refreshRuntimeChatHistory()
            advanceUntilIdle()
            val canonicalRetryRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.ChatSessionsList
            }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.ChatSessionsList,
                    serializer = ChatSessionsListResultPayload.serializer(),
                    payload = ChatSessionsListResultPayload(
                        sessions = listOf(
                            ChatSessionSummaryPayload(
                                sessionId = "runtime-history-canonical-retry",
                                title = "Canonical runtime history",
                                model = "ollama:llama3.1:8b",
                                lastActivityAt = "2026-06-25T00:03:00Z",
                                messageCount = 5,
                                status = "active",
                                lastEvent = "done",
                                search = ChatSessionSearchPayload(
                                    rank = 1,
                                    snippet = "Canonical runtime history matched the query.",
                                    matchedFields = listOf("title"),
                                ),
                            ),
                        ),
                    ),
                    requestId = canonicalRetryRequest.requestId,
                ),
            )
            advanceUntilIdle()

            val retryState = fixture.viewModel.state.value
            assertEquals(listOf("Canonical runtime history"), retryState.chatSessions.map { it.title })
            val retrySession = retryState.chatSessions.single()
            assertEquals(1, retrySession.searchRank)
            assertEquals("Canonical runtime history matched the query.", retrySession.searchSnippet)
            assertEquals(listOf("title"), retrySession.searchMatchedFields)
            val savedRuntimeSession = fixture.localStore.data.sessions.single {
                it.id == "runtime-history-canonical-retry"
            }
            assertTrue(savedRuntimeSession.runtimeOwned)
            assertEquals(5, savedRuntimeSession.runtimeMessageCount)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun refreshRuntimeChatHistoryRequestsFreshListAfterPendingListCompletes() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )
            val initialChatSessionsRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.ChatSessionsList
            }
            val initialChatSessionsRequestCount = fixture.channel.sentEnvelopes.count {
                it.type == MessageType.ChatSessionsList
            }

            fixture.viewModel.refreshRuntimeChatHistory()
            advanceUntilIdle()
            assertEquals(
                initialChatSessionsRequestCount,
                fixture.channel.sentEnvelopes.count { it.type == MessageType.ChatSessionsList },
            )

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.ChatSessionsList,
                    serializer = ChatSessionsListResultPayload.serializer(),
                    payload = ChatSessionsListResultPayload(
                        sessions = listOf(
                            ChatSessionSummaryPayload(
                                sessionId = "runtime-chat-before-refresh",
                                title = "Initial runtime chat",
                                model = "ollama:llama3.1:8b",
                                lastActivityAt = "2026-06-25T00:00:00Z",
                                messageCount = 2,
                                status = "active",
                                lastEvent = "done",
                                lastFinishReason = "stop",
                            ),
                        ),
                    ),
                    requestId = initialChatSessionsRequest.requestId,
                ),
            )
            advanceUntilIdle()

            fixture.viewModel.refreshRuntimeChatHistory()
            advanceUntilIdle()
            val chatSessionsRequests = fixture.channel.sentEnvelopes.filter {
                it.type == MessageType.ChatSessionsList
            }
            assertEquals(initialChatSessionsRequestCount + 1, chatSessionsRequests.size)
            val refreshPayload = json.decodeFromJsonElement(
                ChatSessionsListRequestPayload.serializer(),
                chatSessionsRequests.last().payload,
            )
            assertTrue(refreshPayload.includeArchived)
            assertNull(refreshPayload.query)

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.ChatSessionsList,
                    serializer = ChatSessionsListResultPayload.serializer(),
                    payload = ChatSessionsListResultPayload(
                        sessions = listOf(
                            ChatSessionSummaryPayload(
                                sessionId = "runtime-chat-after-refresh",
                                title = "Updated runtime chat",
                                model = "ollama:llama3.1:8b",
                                lastActivityAt = "2026-06-25T00:05:00Z",
                                messageCount = 4,
                                status = "active",
                                lastEvent = "done",
                                lastFinishReason = "stop",
                            ),
                        ),
                    ),
                    requestId = chatSessionsRequests.last().requestId,
                ),
            )
            advanceUntilIdle()

            assertEquals(
                listOf("Updated runtime chat"),
                fixture.viewModel.state.value.chatSessions.map { it.title },
            )
            val savedRuntimeSession = fixture.localStore.data.sessions.single { it.id == "runtime-chat-after-refresh" }
            assertTrue(savedRuntimeSession.runtimeOwned)
            assertTrue(savedRuntimeSession.messages.isEmpty())
            assertEquals(4, savedRuntimeSession.runtimeMessageCount)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun refreshRuntimeChatHistoryCanSendTrimmedQuery() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )
            val initialChatSessionsRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.ChatSessionsList
            }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.ChatSessionsList,
                    serializer = ChatSessionsListResultPayload.serializer(),
                    payload = ChatSessionsListResultPayload(sessions = emptyList()),
                    requestId = initialChatSessionsRequest.requestId,
                ),
            )
            advanceUntilIdle()

            fixture.viewModel.refreshRuntimeChatHistory(query = "  relay route  ")
            advanceUntilIdle()

            val queryRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.ChatSessionsList
            }
            val queryPayload = json.decodeFromJsonElement(
                ChatSessionsListRequestPayload.serializer(),
                queryRequest.payload,
            )
            assertEquals(100, queryPayload.limit)
            assertTrue(queryPayload.includeArchived)
            assertEquals("relay route", queryPayload.query)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun refreshRuntimeChatHistorySendsSelectedEmbeddingModelOnlyForSearchQuery() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val selectedEmbeddingModel = embeddingModel()
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel(), selectedEmbeddingModel),
                selectedEmbeddingModelId = selectedEmbeddingModel.id,
                redactRuntimeOwnedLocalDataOnSave = true,
            )
            val initialChatSessionsRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.ChatSessionsList
            }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.ChatSessionsList,
                    serializer = ChatSessionsListResultPayload.serializer(),
                    payload = ChatSessionsListResultPayload(sessions = emptyList()),
                    requestId = initialChatSessionsRequest.requestId,
                ),
            )
            advanceUntilIdle()

            fixture.viewModel.refreshRuntimeChatHistory()
            advanceUntilIdle()

            val refreshRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.ChatSessionsList
            }
            val refreshPayload = json.decodeFromJsonElement(
                ChatSessionsListRequestPayload.serializer(),
                refreshRequest.payload,
            )
            assertNull(refreshPayload.query)
            assertNull(refreshPayload.embeddingModelId)

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.ChatSessionsList,
                    serializer = ChatSessionsListResultPayload.serializer(),
                    payload = ChatSessionsListResultPayload(sessions = emptyList()),
                    requestId = refreshRequest.requestId,
                ),
            )
            advanceUntilIdle()

            fixture.viewModel.refreshRuntimeChatHistory(query = "  relay route  ")
            advanceUntilIdle()

            val queryRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.ChatSessionsList
            }
            val queryPayload = json.decodeFromJsonElement(
                ChatSessionsListRequestPayload.serializer(),
                queryRequest.payload,
            )
            assertEquals("relay route", queryPayload.query)
            assertEquals(selectedEmbeddingModel.id, queryPayload.embeddingModelId)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun runtimeChatMessagesListErrorClearsLoadingAndShowsChatHistoryLoadFailed() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val initialData = PersistedRuntimeData(
                selectedModelId = "ollama:llama3.1:8b",
                trustedRuntimeAutoReconnectEnabled = false,
                sessions = listOf(
                    PersistedChatSession(
                        id = "runtime-session",
                        title = "Runtime session",
                        modelId = "ollama:llama3.1:8b",
                        createdAtMillis = 100L,
                        updatedAtMillis = 200L,
                        runtimeOwned = true,
                        runtimeMessageCount = 2,
                    ),
                ),
            )
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                initialData = initialData,
            )

            fixture.viewModel.openPreviousChat("runtime-session")
            advanceUntilIdle()

            val messagesRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.ChatMessagesList }
            assertEquals("runtime-session", fixture.viewModel.state.value.loadingChatSessionId)

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.Error,
                    serializer = ErrorPayload.serializer(),
                    payload = ErrorPayload(
                        code = "chat_store_unavailable",
                        message = "Runtime history unavailable",
                        retryable = true,
                    ),
                    requestId = messagesRequest.requestId,
                ),
            )
            advanceUntilIdle()

            assertNull(fixture.viewModel.state.value.loadingChatSessionId)
            assertFalse(fixture.viewModel.state.value.isLoadingActiveChatMessages)
            assertEquals("chat_history_load_failed", fixture.viewModel.state.value.error?.code)
            assertNull(fixture.viewModel.state.value.error?.detail)
            assertEquals("Runtime history unavailable", fixture.viewModel.state.value.error?.technicalDetail)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun refreshRuntimeChatHistoryErrorShowsLoadFailureAndAllowsRetry() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )
            val initialChatSessionsRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.ChatSessionsList
            }
            val initialChatSessionsRequestCount = fixture.channel.sentEnvelopes.count {
                it.type == MessageType.ChatSessionsList
            }

            fixture.viewModel.refreshRuntimeChatHistory()
            advanceUntilIdle()
            assertEquals(
                initialChatSessionsRequestCount,
                fixture.channel.sentEnvelopes.count { it.type == MessageType.ChatSessionsList },
            )

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.Error,
                    serializer = ErrorPayload.serializer(),
                    payload = ErrorPayload(
                        code = "chat_store_unavailable",
                        message = "Runtime history unavailable",
                        retryable = true,
                    ),
                    requestId = initialChatSessionsRequest.requestId,
                ),
            )
            advanceUntilIdle()

            assertEquals("chat_history_load_failed", fixture.viewModel.state.value.error?.code)
            assertNull(fixture.viewModel.state.value.error?.detail)
            assertEquals("Runtime history unavailable", fixture.viewModel.state.value.error?.technicalDetail)

            fixture.viewModel.refreshRuntimeChatHistory()
            advanceUntilIdle()
            assertEquals(
                initialChatSessionsRequestCount + 1,
                fixture.channel.sentEnvelopes.count { it.type == MessageType.ChatSessionsList },
            )
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun refreshRuntimeMemoryErrorShowsFailureAndAllowsRetry() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )
            val initialMemoryListRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.MemoryList }
            val initialMemoryListCount = fixture.channel.sentEnvelopes.count { it.type == MessageType.MemoryList }

            fixture.viewModel.refreshRuntimeMemory()
            advanceUntilIdle()
            assertEquals(initialMemoryListCount, fixture.channel.sentEnvelopes.count { it.type == MessageType.MemoryList })

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.Error,
                    serializer = ErrorPayload.serializer(),
                    payload = ErrorPayload(
                        code = "memory_store_unavailable",
                        message = "Runtime memory unavailable",
                        retryable = true,
                    ),
                    requestId = initialMemoryListRequest.requestId,
                ),
            )
            advanceUntilIdle()

            assertEquals("memory_load_failed", fixture.viewModel.state.value.error?.code)
            assertNull(fixture.viewModel.state.value.error?.detail)
            assertEquals("Runtime memory unavailable", fixture.viewModel.state.value.error?.technicalDetail)

            fixture.viewModel.refreshRuntimeMemory()
            advanceUntilIdle()
            assertEquals(
                initialMemoryListCount + 1,
                fixture.channel.sentEnvelopes.count { it.type == MessageType.MemoryList },
            )
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun refreshRuntimeMemorySummaryDraftsErrorShowsFailureAndAllowsRetry() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )
            val initialDraftRequest = fixture.channel.sentEnvelopes.last {
                it.type == MessageType.MemorySummaryDraftsList
            }
            val initialDraftRequestCount = fixture.channel.sentEnvelopes.count {
                it.type == MessageType.MemorySummaryDraftsList
            }

            fixture.viewModel.refreshRuntimeMemorySummaryDrafts()
            advanceUntilIdle()
            assertEquals(
                initialDraftRequestCount,
                fixture.channel.sentEnvelopes.count { it.type == MessageType.MemorySummaryDraftsList },
            )

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.Error,
                    serializer = ErrorPayload.serializer(),
                    payload = ErrorPayload(
                        code = "memory_summary_draft_unavailable",
                        message = "Runtime memory summary drafts unavailable",
                        retryable = true,
                    ),
                    requestId = initialDraftRequest.requestId,
                ),
            )
            advanceUntilIdle()

            assertEquals("memory_summary_drafts_load_failed", fixture.viewModel.state.value.error?.code)
            assertNull(fixture.viewModel.state.value.error?.detail)
            assertEquals(
                "Runtime memory summary drafts unavailable",
                fixture.viewModel.state.value.error?.technicalDetail,
            )

            fixture.viewModel.refreshRuntimeMemorySummaryDrafts()
            advanceUntilIdle()
            assertEquals(
                initialDraftRequestCount + 1,
                fixture.channel.sentEnvelopes.count { it.type == MessageType.MemorySummaryDraftsList },
            )
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun streamingBlocksRuntimeRouteTrustAndConnectionMutations() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
            )
            fixture.viewModel.replaceStateForTest {
                it.copy(
                    runtimeHost = "192.168.1.20",
                    runtimePort = "43170",
                    runtimeEndpointSource = RuntimeEndpointSource.Manual,
                    pairingCode = "000000",
                    isDiscovering = true,
                    isStreaming = true,
                    activeRequestId = "active-request",
                    error = null,
                )
            }
            val sentEnvelopeCount = fixture.channel.sentEnvelopes.size

            fixture.viewModel.updateHost("10.0.0.2")
            fixture.viewModel.updatePort("54321")
            fixture.viewModel.useUsbReverseEndpoint()
            fixture.viewModel.useEmulatorEndpoint()
            fixture.viewModel.updatePairingCode("123456")
            fixture.viewModel.useDiscoveredRuntime(
                RuntimeDiscoveredRuntime(
                    serviceName = "AetherLink Runtime",
                    host = "192.168.1.44",
                    port = 43170,
                    routeToken = "route-token-1",
                    deviceId = "runtime-1",
                    fingerprint = "runtime-fingerprint",
                )
            )
            fixture.viewModel.setTrustedRuntimeAutoReconnectEnabled(false)
            fixture.viewModel.connectToTrustedRuntime()
            fixture.viewModel.startDiscovery()
            fixture.viewModel.stopDiscovery()
            fixture.viewModel.trustRuntimeFromPairingQr(
                "aetherlink://pair?v=1&n=nonce-streaming&c=123456" +
                    "&rid=runtime-2&rn=AetherLink%20Runtime&rf=runtime-fingerprint-2" +
                    "&rk=runtime-public-key-2&rt=route-token-2",
            )
            fixture.viewModel.requestRuntimeHealth()
            fixture.viewModel.requestModels()
            fixture.viewModel.forgetTrustedRuntime()
            fixture.viewModel.disconnect()
            advanceUntilIdle()

            val state = fixture.viewModel.state.value
            assertEquals("192.168.1.20", state.runtimeHost)
            assertEquals("43170", state.runtimePort)
            assertEquals(RuntimeEndpointSource.Manual, state.runtimeEndpointSource)
            assertEquals("000000", state.pairingCode)
            assertTrue(state.isDiscovering)
            assertTrue(state.isStreaming)
            assertEquals("active-request", state.activeRequestId)
            assertTrue(state.isConnected)
            assertTrue(fixture.channel.isConnected)
            assertEquals("runtime-1", state.trustedRuntime?.deviceId)
            assertTrue(fixture.localStore.data.trustedRuntimeAutoReconnectEnabled)
            assertNull(fixture.localStore.data.pendingPairingRoute)
            assertEquals(sentEnvelopeCount, fixture.channel.sentEnvelopes.size)
            assertEquals("generation_in_progress", state.error?.code)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun modelsResultRejectsUnknownMetadataBeforeModelStatePublication() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
            )
            val initialModelIds = fixture.viewModel.state.value.models.map { it.id }

            fixture.viewModel.requestModels()
            advanceUntilIdle()

            val topLevelRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.ModelsList }
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.ModelsResult,
                    requestId = topLevelRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "models": [
                                {
                                  "id": "leaky-top-level",
                                  "name": "Leaky Top Level",
                                  "provider": "ollama",
                                  "model_kind": "chat",
                                  "capabilities": ["chat"],
                                  "qualified_id": "ollama:leaky-top-level",
                                  "installed": true,
                                  "source": "local"
                                }
                              ],
                              "route_token": "route-token-canary"
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val rejectedTopLevelState = fixture.viewModel.state.value
            assertFalse(rejectedTopLevelState.isLoadingModels)
            assertEquals(initialModelIds, rejectedTopLevelState.models.map { it.id })
            assertEquals("invalid_payload", rejectedTopLevelState.error?.code)
            assertTrue(rejectedTopLevelState.error?.technicalDetail.orEmpty().contains("models.result"))
            assertTrue(rejectedTopLevelState.error?.technicalDetail.orEmpty().contains("route_token"))

            fixture.viewModel.requestModels()
            advanceUntilIdle()

            val modelMetadataRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.ModelsList }
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.ModelsResult,
                    requestId = modelMetadataRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "models": [
                                {
                                  "id": "leaky-provider",
                                  "name": "Leaky Provider",
                                  "provider": "ollama",
                                  "model_kind": "chat",
                                  "capabilities": ["chat"],
                                  "qualified_id": "ollama:leaky-provider",
                                  "installed": true,
                                  "source": "local",
                                  "provider_url": "http://127.0.0.1:11434",
                                  "backend_url": "http://127.0.0.1:1234"
                                }
                              ]
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val rejectedModelMetadataState = fixture.viewModel.state.value
            assertFalse(rejectedModelMetadataState.isLoadingModels)
            assertEquals(initialModelIds, rejectedModelMetadataState.models.map { it.id })
            assertEquals("invalid_payload", rejectedModelMetadataState.error?.code)
            assertTrue(rejectedModelMetadataState.error?.technicalDetail.orEmpty().contains("models.result"))
            assertTrue(rejectedModelMetadataState.error?.technicalDetail.orEmpty().contains("models[0].provider_url"))

            fixture.viewModel.requestModels()
            advanceUntilIdle()

            val canonicalRetryRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.ModelsList }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.ModelsResult,
                    serializer = ModelsResultPayload.serializer(),
                    payload = ModelsResultPayload(
                        models = listOf(
                            ModelInfoPayload(
                                id = "canonical-retry",
                                name = "Canonical Retry",
                                provider = "ollama",
                                modelKind = MODEL_KIND_CHAT,
                                capabilities = listOf("chat"),
                                qualifiedId = "ollama:canonical-retry",
                                installed = true,
                                source = "local",
                            ),
                        ),
                    ),
                    requestId = canonicalRetryRequest.requestId,
                ),
            )
            advanceUntilIdle()

            val retryState = fixture.viewModel.state.value
            assertEquals(listOf("ollama:canonical-retry"), retryState.models.map { it.id })
            assertNull(retryState.error)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun modelsResultMissingInstalledOrSourceDoesNotBecomeSelectableChatModel() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val modelId = "ollama:metadata-missing"
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = emptyList(),
                modelPayloads = listOf(
                    ModelInfoPayload(
                        id = "metadata-missing",
                        name = "Metadata Missing",
                        provider = "ollama",
                        modelKind = MODEL_KIND_CHAT,
                        capabilities = listOf("chat"),
                        qualifiedId = modelId,
                    ),
                ),
                selectedModelId = modelId,
            )

            val parsedModel = fixture.viewModel.state.value.models.single()
            assertEquals(modelId, parsedModel.id)
            assertEquals(false, parsedModel.installed)
            assertNull(parsedModel.source)
            assertNull(fixture.viewModel.state.value.selectedModelId)
            assertEquals(
                SelectedModelSendState.Missing,
                fixture.viewModel.state.value.copy(selectedModelId = modelId).selectedModelSendState(),
            )

            fixture.viewModel.selectModel(modelId)

            assertNull(fixture.viewModel.state.value.selectedModelId)
            assertEquals("select_chat_model", fixture.viewModel.state.value.error?.code)
            assertFalse(fixture.channel.sentEnvelopes.any { it.type == MessageType.ModelsPull })
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun selectModelRejectsProviderManagedOrUnknownSourceChatModelWithoutPersisting() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val localModel = textChatModel()
            val providerManagedModel = localModel.copy(
                id = "ollama:provider-managed",
                name = "Provider Managed",
                source = "cloud",
            )
            val unknownSourceModel = localModel.copy(
                id = "ollama:unknown-source",
                name = "Unknown Source",
                source = null,
            )
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(localModel, providerManagedModel, unknownSourceModel),
                selectedModelId = localModel.id,
            )

            fixture.viewModel.selectModel(providerManagedModel.id)

            assertEquals(localModel.id, fixture.viewModel.state.value.selectedModelId)
            assertEquals(localModel.id, fixture.localStore.data.selectedModelId)
            assertEquals("select_chat_model", fixture.viewModel.state.value.error?.code)

            fixture.viewModel.selectModel(unknownSourceModel.id)

            assertEquals(localModel.id, fixture.viewModel.state.value.selectedModelId)
            assertEquals(localModel.id, fixture.localStore.data.selectedModelId)
            assertEquals("select_chat_model", fixture.viewModel.state.value.error?.code)
            assertFalse(fixture.channel.sentEnvelopes.any { it.type == MessageType.ModelsPull })
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun selectEmbeddingModelRejectsUninstalledRuntimeModelWithoutChangingSelection() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val existingEmbeddingModelId = "ollama:nomic-embed-text"
            val uninstalledEmbeddingModelId = "ollama:mxbai-embed-large"
            val channel = ScriptedRuntimeProtocolChannel()
            val localStore = FakeRuntimeLocalDataStore(
                initialData = PersistedRuntimeData(
                    selectedEmbeddingModelId = existingEmbeddingModelId,
                    trustedRuntimeAutoReconnectEnabled = false,
                ),
            )
            val trustedStore = FakeEmittingTrustedRuntimeStore(
                TrustedRuntime(
                    deviceId = "runtime-1",
                    name = "AetherLink Runtime",
                    fingerprint = "runtime-fingerprint",
                    publicKeyBase64 = "runtime-public-key",
                    routeToken = "route-token-1",
                    relayHost = "relay.example.test",
                    relayPort = 443,
                    relayId = "relay-1",
                    relaySecret = "secret-1",
                    relayExpiresAtEpochMillis = 4_102_444_800_000L,
                    relayNonce = "relay-nonce-1",
                    relayScope = "remote",
                ),
            )
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Direct TCP should not be used for relay-backed model selection test")
                    },
                    relayConnector = RuntimeRelayConnector { _, _ -> channel },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = localStore,
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    currentTimeMillis = { 1_000L },
                ),
            )
            advanceUntilIdle()

            viewModel.connectToTrustedRuntime()
            advanceUntilIdle()
            channel.enqueue(
                envelope(
                    type = MessageType.AuthResponse,
                    serializer = AuthResponsePayload.serializer(),
                    payload = AuthResponsePayload(accepted = true),
                    requestId = "auth-accepted",
                ),
            )
            advanceUntilIdle()
            channel.enqueue(
                envelope(
                    type = MessageType.RuntimeHealth,
                    serializer = RuntimeHealthPayload.serializer(),
                    payload = RuntimeHealthPayload(status = "ok"),
                    requestId = "runtime-health",
                ),
            )
            advanceUntilIdle()
            val modelsRequest = channel.sentEnvelopes.last { it.type == MessageType.ModelsList }
            channel.enqueue(
                envelope(
                    type = MessageType.ModelsResult,
                    serializer = ModelsResultPayload.serializer(),
                    payload = ModelsResultPayload(
                        models = listOf(
                            ModelInfoPayload(
                                id = "llama3.1:8b",
                                name = "Llama 3.1 8B",
                                provider = "ollama",
                                modelKind = MODEL_KIND_CHAT,
                                capabilities = listOf("chat"),
                                qualifiedId = "ollama:llama3.1:8b",
                                installed = true,
                                source = "local",
                                contextWindowTokens = 32768,
                            ),
                            ModelInfoPayload(
                                id = "nomic-embed-text",
                                name = "nomic-embed-text",
                                provider = "ollama",
                                modelKind = MODEL_KIND_EMBEDDING,
                                capabilities = listOf("embedding"),
                                qualifiedId = existingEmbeddingModelId,
                                installed = true,
                                source = "local",
                            ),
                            ModelInfoPayload(
                                id = "mxbai-embed-large",
                                name = "mxbai-embed-large",
                                provider = "ollama",
                                modelKind = MODEL_KIND_EMBEDDING,
                                capabilities = listOf("embedding"),
                                qualifiedId = uninstalledEmbeddingModelId,
                                installed = false,
                                source = "local",
                            ),
                        ),
                    ),
                    requestId = modelsRequest.requestId,
                ),
            )
            advanceUntilIdle()

            val chatModel = viewModel.state.value.models.first { it.id == "ollama:llama3.1:8b" }
            assertEquals(32768, chatModel.contextWindowTokens)
            viewModel.selectEmbeddingModel(uninstalledEmbeddingModelId)

            assertEquals(existingEmbeddingModelId, viewModel.state.value.selectedEmbeddingModelId)
            assertEquals(existingEmbeddingModelId, localStore.data.selectedEmbeddingModelId)
            assertEquals("select_embedding_model", viewModel.state.value.error?.code)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun viewModelRestoresPersistedLanguageThemeAndModelSelectionsOnInit() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val localStore = FakeRuntimeLocalDataStore(
                initialData = PersistedRuntimeData(
                    selectedModelId = "ollama:qwen3:8b",
                    selectedEmbeddingModelId = "ollama:nomic-embed-text",
                    appLanguageTag = RuntimeAppLanguage.Korean.languageTag,
                    appTheme = RuntimeAppTheme.Dark.storageValue,
                    trustedRuntimeAutoReconnectEnabled = false,
                ),
            )
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Direct TCP should not be used for persisted settings restore")
                    },
                    relayConnector = RuntimeRelayConnector { _, _ ->
                        error("Relay should not be used for persisted settings restore")
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = FakeTrustedRuntimeStore(),
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = localStore,
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    currentTimeMillis = { 1_000L },
                ),
            )
            advanceUntilIdle()

            val state = viewModel.state.value
            assertEquals("ollama:qwen3:8b", state.selectedModelId)
            assertEquals("ollama:nomic-embed-text", state.selectedEmbeddingModelId)
            assertEquals(RuntimeAppLanguage.Korean.languageTag, state.selectedLanguageTag)
            assertEquals(RuntimeAppTheme.Dark, state.selectedTheme)
            assertEquals(false, state.trustedRuntimeAutoReconnectEnabled)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun viewModelPersistsLanguageThemeAndRestoresThemAfterRecreation() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val localStore = FakeRuntimeLocalDataStore(
                initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = false),
            )
            fun createViewModel(): RuntimeClientViewModel {
                return RuntimeClientViewModel(
                    application = Application(),
                    dependencies = RuntimeClientViewModelDependencies(
                        json = json,
                        transportClient = RuntimeTransportClient(),
                        transportConnector = RuntimeTransportConnector { _, _, _ ->
                            error("Direct TCP should not be used for persisted settings recreation")
                        },
                        relayConnector = RuntimeRelayConnector { _, _ ->
                            error("Relay should not be used for persisted settings recreation")
                        },
                        discovery = EmptyRuntimeDiscoverySource,
                        trustedRuntimeStore = FakeTrustedRuntimeStore(),
                        deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                        localDataStore = localStore,
                        lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                        currentTimeMillis = { 1_000L },
                    ),
                )
            }

            val first = createViewModel()
            advanceUntilIdle()
            first.setAppLanguageTag("zh-Hans")
            first.setAppTheme(RuntimeAppTheme.Light)
            advanceUntilIdle()

            assertEquals(RuntimeAppLanguage.SimplifiedChinese.languageTag, localStore.data.appLanguageTag)
            assertEquals(RuntimeAppTheme.Light.storageValue, localStore.data.appTheme)
            assertEquals(RuntimeAppLanguage.SimplifiedChinese.languageTag, first.state.value.selectedLanguageTag)
            assertEquals(RuntimeAppTheme.Light, first.state.value.selectedTheme)

            val recreated = createViewModel()
            advanceUntilIdle()

            assertEquals(RuntimeAppLanguage.SimplifiedChinese.languageTag, recreated.state.value.selectedLanguageTag)
            assertEquals(RuntimeAppTheme.Light, recreated.state.value.selectedTheme)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun viewModelReconcilesSystemAppLanguageUntilInAppLanguageIsSelected() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val localStore = FakeRuntimeLocalDataStore()
            fun createViewModel(): RuntimeClientViewModel {
                return RuntimeClientViewModel(
                    application = Application(),
                    dependencies = RuntimeClientViewModelDependencies(
                        json = json,
                        transportClient = RuntimeTransportClient(),
                        transportConnector = RuntimeTransportConnector { _, _, _ ->
                            error("Direct TCP should not be used for app language handoff")
                        },
                        relayConnector = RuntimeRelayConnector { _, _ ->
                            error("Relay should not be used for app language handoff")
                        },
                        discovery = EmptyRuntimeDiscoverySource,
                        trustedRuntimeStore = FakeTrustedRuntimeStore(),
                        deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                        localDataStore = localStore,
                        lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                        currentTimeMillis = { 1_000L },
                    ),
                )
            }

            val first = createViewModel()
            advanceUntilIdle()
            first.reconcileSystemAppLanguageTag("ko-KR")
            advanceUntilIdle()

            assertEquals(RuntimeAppLanguage.Korean.languageTag, first.state.value.selectedLanguageTag)
            assertEquals(RuntimeAppLanguage.Korean.languageTag, localStore.data.appLanguageTag)
            assertEquals(APP_LANGUAGE_SOURCE_SYSTEM, localStore.data.appLanguageSource)

            first.setAppLanguageTag("fr-FR")
            advanceUntilIdle()
            assertEquals(RuntimeAppLanguage.French.languageTag, first.state.value.selectedLanguageTag)
            assertEquals(APP_LANGUAGE_SOURCE_IN_APP, localStore.data.appLanguageSource)

            val recreated = createViewModel()
            advanceUntilIdle()
            recreated.reconcileSystemAppLanguageTag("ja-JP")
            advanceUntilIdle()

            assertEquals(RuntimeAppLanguage.French.languageTag, recreated.state.value.selectedLanguageTag)
            assertEquals(RuntimeAppLanguage.French.languageTag, localStore.data.appLanguageTag)
            assertEquals(APP_LANGUAGE_SOURCE_IN_APP, localStore.data.appLanguageSource)

            recreated.followSystemAppLanguageTag("ja-JP")
            advanceUntilIdle()

            assertEquals(RuntimeAppLanguage.Japanese.languageTag, recreated.state.value.selectedLanguageTag)
            assertEquals(RuntimeAppLanguage.Japanese.languageTag, localStore.data.appLanguageTag)
            assertEquals(APP_LANGUAGE_SOURCE_SYSTEM, localStore.data.appLanguageSource)

            recreated.reconcileSystemAppLanguageTag("ko-KR")
            advanceUntilIdle()

            assertEquals(RuntimeAppLanguage.Korean.languageTag, recreated.state.value.selectedLanguageTag)
            assertEquals(RuntimeAppLanguage.Korean.languageTag, localStore.data.appLanguageTag)
            assertEquals(APP_LANGUAGE_SOURCE_SYSTEM, localStore.data.appLanguageSource)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun viewModelPublicSettingsSettersPersistAcrossRecreation() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val localStore = FakeRuntimeLocalDataStore()
            fun createViewModel(): RuntimeClientViewModel {
                return RuntimeClientViewModel(
                    application = Application(),
                    dependencies = RuntimeClientViewModelDependencies(
                        json = json,
                        transportClient = RuntimeTransportClient(),
                        transportConnector = RuntimeTransportConnector { _, _, _ ->
                            error("Direct TCP should not be used for settings setter persistence")
                        },
                        relayConnector = RuntimeRelayConnector { _, _ ->
                            error("Relay should not be used for settings setter persistence")
                        },
                        discovery = EmptyRuntimeDiscoverySource,
                        trustedRuntimeStore = FakeTrustedRuntimeStore(),
                        deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                        localDataStore = localStore,
                        lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                        currentTimeMillis = { 1_000L },
                    ),
                )
            }

            val first = createViewModel()
            advanceUntilIdle()
            first.replaceStateForTest {
                it.copy(
                    models = listOf(textChatModel(), embeddingModel()),
                )
            }

            first.setAppLanguageTag(RuntimeAppLanguage.French.languageTag)
            first.setAppTheme(RuntimeAppTheme.Dark)
            first.setTrustedRuntimeAutoReconnectEnabled(false)
            first.selectModel("ollama:llama3.1:8b")
            first.selectEmbeddingModel("ollama:nomic-embed-text")
            advanceUntilIdle()

            assertEquals(RuntimeAppLanguage.French.languageTag, localStore.data.appLanguageTag)
            assertEquals(RuntimeAppTheme.Dark.storageValue, localStore.data.appTheme)
            assertEquals(false, localStore.data.trustedRuntimeAutoReconnectEnabled)
            assertEquals("ollama:llama3.1:8b", localStore.data.selectedModelId)
            assertEquals("ollama:nomic-embed-text", localStore.data.selectedEmbeddingModelId)

            val recreated = createViewModel()
            advanceUntilIdle()

            val state = recreated.state.value
            assertEquals(RuntimeAppLanguage.French.languageTag, state.selectedLanguageTag)
            assertEquals(RuntimeAppTheme.Dark, state.selectedTheme)
            assertEquals(false, state.trustedRuntimeAutoReconnectEnabled)
            assertEquals("ollama:llama3.1:8b", state.selectedModelId)
            assertEquals("ollama:nomic-embed-text", state.selectedEmbeddingModelId)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @Test
    fun chatTitleRequestCandidateBuildsAfterFirstCompletedExchange() {
        val state = RuntimeUiState(
            isConnected = true,
            activeChatSessionId = "session-1",
            selectedModelId = "ollama:llama3.1:8b",
            selectedLanguageTag = "ko",
            models = listOf(
                RuntimeModel(
                    id = "ollama:llama3.1:8b",
                    name = "Llama 3.1 8B",
                    installed = true,
                ),
            ),
            messages = listOf(
                RuntimeChatMessage(role = "system", content = "Ignored system message"),
                RuntimeChatMessage(role = "user", content = "Explain runtime-mediated model access."),
                RuntimeChatMessage(role = "assistant", content = "AetherLink Runtime mediates all backend access."),
            ),
        )
        val persisted = PersistedRuntimeData(
            sessions = listOf(
                PersistedChatSession(
                    id = "session-1",
                    title = "",
                    createdAtMillis = 10L,
                    updatedAtMillis = 20L,
                ),
            ),
        )

        val candidate = requireNotNull(
            chatTitleRequestCandidate(
                sourceState = state,
                persistedRuntimeData = persisted,
                isSessionAuthenticated = true,
            )
        )

        assertEquals("session-1", candidate.sessionId)
        assertEquals("ollama:llama3.1:8b", candidate.model)
        assertEquals("ko", candidate.locale)
        assertEquals(listOf("user", "assistant"), candidate.messages.map { it.role })
        assertEquals("Explain runtime-mediated model access.", candidate.messages.first().content)
    }

    @Test
    fun chatTitleRequestCandidateUsesEnglishWhenLanguagePreferenceIsLegacyBlank() {
        val state = RuntimeUiState(
            isConnected = true,
            activeChatSessionId = "session-1",
            selectedModelId = "ollama:llama3.1:8b",
            selectedLanguageTag = "",
            models = listOf(
                RuntimeModel(
                    id = "ollama:llama3.1:8b",
                    name = "Llama 3.1 8B",
                    installed = true,
                ),
            ),
            messages = listOf(
                RuntimeChatMessage(role = "user", content = "Summarize this topic."),
                RuntimeChatMessage(role = "assistant", content = "A short answer."),
            ),
        )
        val persisted = PersistedRuntimeData(
            sessions = listOf(
                PersistedChatSession(
                    id = "session-1",
                    title = "",
                    createdAtMillis = 10L,
                    updatedAtMillis = 20L,
                ),
            ),
        )

        val legacyBlankCandidate = requireNotNull(
            chatTitleRequestCandidate(
                sourceState = state,
                persistedRuntimeData = persisted,
                isSessionAuthenticated = true,
            )
        )
        val unsupportedCandidate = requireNotNull(
            chatTitleRequestCandidate(
                sourceState = state,
                persistedRuntimeData = persisted,
                isSessionAuthenticated = true,
            )
        )

        assertEquals("en", legacyBlankCandidate.locale)
        assertEquals("en", unsupportedCandidate.locale)
    }

    @Test
    fun chatTitleRequestCandidateRejectsUnsafeOrAlreadyTitledSessions() {
        val baseState = RuntimeUiState(
            isConnected = true,
            activeChatSessionId = "session-1",
            selectedModelId = "ollama:llama3.1:8b",
            models = listOf(
                RuntimeModel(
                    id = "ollama:llama3.1:8b",
                    name = "Llama 3.1 8B",
                    installed = true,
                ),
            ),
            messages = listOf(
                RuntimeChatMessage(role = "user", content = "First prompt"),
                RuntimeChatMessage(role = "assistant", content = "First answer"),
            ),
        )
        val untitledSession = PersistedChatSession(
            id = "session-1",
            title = "",
            createdAtMillis = 10L,
            updatedAtMillis = 20L,
        )
        val untitledData = PersistedRuntimeData(sessions = listOf(untitledSession))

        assertNull(chatTitleRequestCandidate(baseState, untitledData, isSessionAuthenticated = false))
        assertNull(chatTitleRequestCandidate(baseState.copy(isStreaming = true), untitledData, isSessionAuthenticated = true))
        assertNull(
            chatTitleRequestCandidate(
                baseState.copy(messages = listOf(RuntimeChatMessage(role = "user", content = "Only prompt"))),
                untitledData,
                isSessionAuthenticated = true,
            )
        )
        assertNull(
            chatTitleRequestCandidate(
                baseState.copy(
                    messages = listOf(
                        RuntimeChatMessage(role = "user", content = "First prompt"),
                        RuntimeChatMessage(role = "assistant", content = "First answer"),
                        RuntimeChatMessage(role = "user", content = "Follow-up prompt"),
                    )
                ),
                untitledData,
                isSessionAuthenticated = true,
            )
        )
        assertNull(
            chatTitleRequestCandidate(
                baseState,
                PersistedRuntimeData(sessions = listOf(untitledSession.copy(titleManuallyEdited = true))),
                isSessionAuthenticated = true,
            )
        )
        assertNull(
            chatTitleRequestCandidate(
                baseState,
                PersistedRuntimeData(sessions = listOf(untitledSession.copy(titleGenerated = true))),
                isSessionAuthenticated = true,
            )
        )
        assertNull(
            chatTitleRequestCandidate(
                baseState,
                PersistedRuntimeData(sessions = listOf(untitledSession.copy(archivedAtMillis = 30L))),
                isSessionAuthenticated = true,
            )
        )
    }

    @Test
    fun modelSelectionReconciliationKeepsMissingPersistedSelectionsTypedAcrossRefresh() {
        val selections = reconcileModelSelections(
            currentSelectedModelId = "ollama:qwen3:8b",
            currentSelectedEmbeddingModelId = "ollama:nomic-embed-text",
            models = listOf(
                RuntimeModel(
                    id = "ollama:llama3",
                    name = "Llama 3",
                    modelKind = MODEL_KIND_CHAT,
                    capabilities = listOf("chat"),
                    installed = true,
                ),
                RuntimeModel(
                    id = "ollama:mxbai-embed-large",
                    name = "mxbai-embed-large",
                    modelKind = MODEL_KIND_EMBEDDING,
                    capabilities = listOf("embedding"),
                    installed = true,
                ),
            ),
        )

        assertEquals("ollama:qwen3:8b", selections.selectedModelId)
        assertEquals("ollama:nomic-embed-text", selections.selectedEmbeddingModelId)
    }

    @Test
    fun modelSelectionReconciliationKeepsPersistedSelectionsWhileModelListIsRestoring() {
        val selections = reconcileModelSelections(
            currentSelectedModelId = "ollama:qwen3:8b",
            currentSelectedEmbeddingModelId = "ollama:nomic-embed-text",
            models = emptyList(),
        )

        assertEquals("ollama:qwen3:8b", selections.selectedModelId)
        assertEquals("ollama:nomic-embed-text", selections.selectedEmbeddingModelId)
    }

    @Test
    fun modelSelectionReconciliationClearsSelectionsWhenRefreshedModelHasWrongKind() {
        val selections = reconcileModelSelections(
            currentSelectedModelId = "ollama:nomic-embed-text",
            currentSelectedEmbeddingModelId = "ollama:qwen3:8b",
            models = listOf(
                RuntimeModel(
                    id = "ollama:nomic-embed-text",
                    name = "nomic-embed-text",
                    modelKind = MODEL_KIND_EMBEDDING,
                    capabilities = listOf("embedding"),
                    installed = true,
                ),
                RuntimeModel(
                    id = "ollama:qwen3:8b",
                    name = "Qwen3 8B",
                    modelKind = MODEL_KIND_CHAT,
                    capabilities = listOf("chat"),
                    installed = true,
                ),
            ),
        )

        assertNull(selections.selectedModelId)
        assertNull(selections.selectedEmbeddingModelId)
    }

    @Test
    fun modelSelectionReconciliationClearsEmbeddingSelectionWhenModelIsNotInstalled() {
        val selections = reconcileModelSelections(
            currentSelectedModelId = "ollama:qwen3:8b",
            currentSelectedEmbeddingModelId = "ollama:nomic-embed-text",
            models = listOf(
                RuntimeModel(
                    id = "ollama:qwen3:8b",
                    name = "Qwen3 8B",
                    modelKind = MODEL_KIND_CHAT,
                    capabilities = listOf("chat"),
                    installed = true,
                ),
                RuntimeModel(
                    id = "ollama:nomic-embed-text",
                    name = "nomic-embed-text",
                    modelKind = MODEL_KIND_EMBEDDING,
                    capabilities = listOf("embedding"),
                    installed = false,
                ),
            ),
        )

        assertEquals("ollama:qwen3:8b", selections.selectedModelId)
        assertNull(selections.selectedEmbeddingModelId)
    }

    @Test
    fun modelSelectionReconciliationOnlyAutoSelectsChatWhenSelectionIsEmpty() {
        val models = listOf(
            RuntimeModel(
                id = "ollama:remote-chat",
                name = "Provider Managed Chat",
                modelKind = MODEL_KIND_CHAT,
                capabilities = listOf("chat"),
                installed = true,
                source = "cloud",
            ),
            RuntimeModel(
                id = "ollama:qwen3:8b",
                name = "Qwen3 8B",
                modelKind = MODEL_KIND_CHAT,
                capabilities = listOf("chat"),
                installed = true,
            ),
            RuntimeModel(
                id = "ollama:nomic-embed-text",
                name = "nomic-embed-text",
                modelKind = MODEL_KIND_EMBEDDING,
                capabilities = listOf("embedding"),
                installed = true,
            ),
        )

        val selections = reconcileModelSelections(
            currentSelectedModelId = null,
            currentSelectedEmbeddingModelId = null,
            models = models,
        )

        assertEquals("ollama:qwen3:8b", selections.selectedModelId)
        assertNull(selections.selectedEmbeddingModelId)
    }

    @Test
    fun modelSelectionReconciliationKeepsExplicitEmbeddingSelection() {
        val selections = reconcileModelSelections(
            currentSelectedModelId = null,
            currentSelectedEmbeddingModelId = "ollama:nomic-embed-text",
            models = listOf(
                RuntimeModel(
                    id = "ollama:qwen3:8b",
                    name = "Qwen3 8B",
                    modelKind = MODEL_KIND_CHAT,
                    capabilities = listOf("chat"),
                    installed = true,
                ),
                RuntimeModel(
                    id = "ollama:nomic-embed-text",
                    name = "nomic-embed-text",
                    modelKind = MODEL_KIND_EMBEDDING,
                    capabilities = listOf("embedding"),
                    installed = true,
                ),
            ),
        )

        assertEquals("ollama:qwen3:8b", selections.selectedModelId)
        assertEquals("ollama:nomic-embed-text", selections.selectedEmbeddingModelId)
    }

    @Test
    fun modelSelectionReconciliationSelectsInstalledChatTargetAfterRefresh() {
        val selections = reconcileModelSelections(
            currentSelectedModelId = "ollama:llama3",
            currentSelectedEmbeddingModelId = null,
            installTargetModelId = "ollama:qwen3:8b",
            models = listOf(
                RuntimeModel(
                    id = "ollama:qwen3:8b",
                    name = "Qwen3 8B",
                    modelKind = MODEL_KIND_CHAT,
                    capabilities = listOf("chat"),
                    installed = true,
                ),
            ),
        )

        assertEquals("ollama:qwen3:8b", selections.selectedModelId)
        assertEquals("ollama:qwen3:8b", selections.installedTargetModelId)
    }

    @Test
    fun modelKindNormalizationSeparatesChatAndEmbeddingModels() {
        assertEquals(
            MODEL_KIND_EMBEDDING,
            normalizeModelKind(
                kind = "embedding",
                capabilities = emptyList(),
                id = "lm_studio:text-embedding-nomic",
                name = "Nomic Embed",
            ),
        )
        assertEquals(
            MODEL_KIND_EMBEDDING,
            normalizeModelKind(
                kind = null,
                capabilities = listOf("embedding"),
                id = "ollama:mxbai-embed-large",
                name = "mxbai-embed-large",
            ),
        )
        assertEquals(
            MODEL_KIND_CHAT,
            normalizeModelKind(
                kind = "llm",
                capabilities = emptyList(),
                id = "lm_studio:qwen-local",
                name = "Qwen Local",
            ),
        )
    }

    @Test
    fun embeddingCapabilityPreventsModelFromBeingTreatedAsChat() {
        val mixedModel = RuntimeModel(
            id = "lm_studio:mixed-embedding",
            name = "Mixed embedding",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat", "embedding"),
            installed = true,
        )

        assertTrue(mixedModel.isEmbeddingModel())
        assertFalse(mixedModel.isChatModel())
    }

    @Test
    fun staleChatDeltaAndDoneForDifferentRequestIdAreIgnored() {
        val state = RuntimeUiState(
            messages = listOf(
                RuntimeChatMessage(role = "user", content = "Hello"),
                RuntimeChatMessage(role = "assistant", content = "Partial"),
            ),
            isStreaming = true,
            activeRequestId = "active-request",
        )

        val afterDelta = state.withChatDelta(
            envelope(
                type = MessageType.ChatDelta,
                requestId = "stale-request",
                serializer = ChatDeltaPayload.serializer(),
                payload = ChatDeltaPayload(delta = " stale"),
            ),
            ChatDeltaPayload(delta = " stale"),
        )
        val afterDone = afterDelta.withChatDone(
            envelope(
                type = MessageType.ChatDone,
                requestId = "stale-request",
                serializer = ChatDonePayload.serializer(),
                payload = ChatDonePayload(),
            ),
            ChatDonePayload(),
        )

        assertSame(state, afterDelta)
        assertSame(afterDelta, afterDone)
        assertTrue(afterDone.isStreaming)
        assertEquals("active-request", afterDone.activeRequestId)
        assertEquals("Partial", afterDone.messages.last().content)
    }

    @Test
    fun chatDeltaAppendsReasoningWithoutMixingIntoAnswerContent() {
        val state = RuntimeUiState(
            messages = listOf(
                RuntimeChatMessage(role = "user", content = "Hello"),
                RuntimeChatMessage(role = "assistant", content = "Final", reasoning = "Plan"),
            ),
            isStreaming = true,
            activeRequestId = "active-request",
        )

        val afterReasoning = state.withChatDelta(
            envelope(
                type = MessageType.ChatDelta,
                requestId = "active-request",
                serializer = ChatDeltaPayload.serializer(),
                payload = ChatDeltaPayload(reasoningDelta = " step"),
            ),
            ChatDeltaPayload(reasoningDelta = " step"),
        )
        val afterAnswer = afterReasoning.withChatDelta(
            envelope(
                type = MessageType.ChatDelta,
                requestId = "active-request",
                serializer = ChatDeltaPayload.serializer(),
                payload = ChatDeltaPayload(delta = " answer"),
            ),
            ChatDeltaPayload(delta = " answer"),
        )

        val message = afterAnswer.messages.last()
        assertEquals("Final answer", message.content)
        assertEquals("Plan step", message.reasoning)
    }

    @Test
    fun thinkingDeltaAliasAppendsReasoning() {
        val state = RuntimeUiState(
            messages = listOf(RuntimeChatMessage(role = "assistant", content = "")),
            isStreaming = true,
            activeRequestId = "active-request",
        )

        val afterDelta = state.withChatDelta(
            envelope(
                type = MessageType.ChatDelta,
                requestId = "active-request",
                serializer = ChatDeltaPayload.serializer(),
                payload = ChatDeltaPayload(thinkingDelta = "Considering context"),
            ),
            ChatDeltaPayload(thinkingDelta = "Considering context"),
        )

        assertEquals("", afterDelta.messages.last().content)
        assertEquals("Considering context", afterDelta.messages.last().reasoning)
    }

    @Test
    fun inlineThinkTagsAreSeparatedFromAnswerContent() {
        val state = RuntimeUiState(
            messages = listOf(RuntimeChatMessage(role = "assistant", content = "")),
            isStreaming = true,
            activeRequestId = "active-request",
        )

        val afterDelta = state.withChatDelta(
            envelope(
                type = MessageType.ChatDelta,
                requestId = "active-request",
                serializer = ChatDeltaPayload.serializer(),
                payload = ChatDeltaPayload(delta = "<think>Check context</think>\nFinal answer"),
            ),
            ChatDeltaPayload(delta = "<think>Check context</think>\nFinal answer"),
        )

        assertEquals("Final answer", afterDelta.messages.last().content)
        assertEquals("Check context", afterDelta.messages.last().reasoning)
        assertFalse(afterDelta.messages.last().isReasoningOpen)
    }

    @Test
    fun splitInlineThinkTagsKeepReasoningCollapsedOutOfAnswerContent() {
        val state = RuntimeUiState(
            messages = listOf(RuntimeChatMessage(role = "assistant", content = "")),
            isStreaming = true,
            activeRequestId = "active-request",
        )

        val afterOpen = state.withChatDelta(
            envelope(
                type = MessageType.ChatDelta,
                requestId = "active-request",
                serializer = ChatDeltaPayload.serializer(),
                payload = ChatDeltaPayload(delta = "<think>Check"),
            ),
            ChatDeltaPayload(delta = "<think>Check"),
        )
        val afterClose = afterOpen.withChatDelta(
            envelope(
                type = MessageType.ChatDelta,
                requestId = "active-request",
                serializer = ChatDeltaPayload.serializer(),
                payload = ChatDeltaPayload(delta = " route</think> Answer"),
            ),
            ChatDeltaPayload(delta = " route</think> Answer"),
        )

        assertEquals("Answer", afterClose.messages.last().content)
        assertEquals("Check route", afterClose.messages.last().reasoning)
        assertFalse(afterClose.messages.last().isReasoningOpen)
    }

    @Test
    fun splitInlineThinkOpeningTagAcrossDeltasDoesNotLeakTagToAnswer() {
        val state = RuntimeUiState(
            messages = listOf(RuntimeChatMessage(role = "assistant", content = "")),
            isStreaming = true,
            activeRequestId = "active-request",
        )

        val afterPartialTag = state.withChatDelta(
            envelope(
                type = MessageType.ChatDelta,
                requestId = "active-request",
                serializer = ChatDeltaPayload.serializer(),
                payload = ChatDeltaPayload(delta = "<thi"),
            ),
            ChatDeltaPayload(delta = "<thi"),
        )
        val afterCompleteTag = afterPartialTag.withChatDelta(
            envelope(
                type = MessageType.ChatDelta,
                requestId = "active-request",
                serializer = ChatDeltaPayload.serializer(),
                payload = ChatDeltaPayload(delta = "nk>Plan</think> Answer"),
            ),
            ChatDeltaPayload(delta = "nk>Plan</think> Answer"),
        )

        assertEquals("", afterPartialTag.messages.last().content)
        assertEquals("", afterPartialTag.messages.last().reasoning)
        assertEquals("<thi", afterPartialTag.messages.last().inlineReasoningPendingTag)
        assertEquals("Answer", afterCompleteTag.messages.last().content)
        assertEquals("Plan", afterCompleteTag.messages.last().reasoning)
        assertEquals("", afterCompleteTag.messages.last().inlineReasoningPendingTag)
        assertFalse(afterCompleteTag.messages.last().isReasoningOpen)
    }

    @Test
    fun splitInlineThinkClosingTagAcrossDeltasDoesNotLeakTagToReasoning() {
        val state = RuntimeUiState(
            messages = listOf(RuntimeChatMessage(role = "assistant", content = "")),
            isStreaming = true,
            activeRequestId = "active-request",
        )

        val afterPartialClose = state.withChatDelta(
            envelope(
                type = MessageType.ChatDelta,
                requestId = "active-request",
                serializer = ChatDeltaPayload.serializer(),
                payload = ChatDeltaPayload(delta = "<think>Plan</thi"),
            ),
            ChatDeltaPayload(delta = "<think>Plan</thi"),
        )
        val afterCompleteClose = afterPartialClose.withChatDelta(
            envelope(
                type = MessageType.ChatDelta,
                requestId = "active-request",
                serializer = ChatDeltaPayload.serializer(),
                payload = ChatDeltaPayload(delta = "nk> Answer"),
            ),
            ChatDeltaPayload(delta = "nk> Answer"),
        )

        assertEquals("", afterPartialClose.messages.last().content)
        assertEquals("Plan", afterPartialClose.messages.last().reasoning)
        assertEquals("</thi", afterPartialClose.messages.last().inlineReasoningPendingTag)
        assertTrue(afterPartialClose.messages.last().isReasoningOpen)
        assertEquals("Answer", afterCompleteClose.messages.last().content)
        assertEquals("Plan", afterCompleteClose.messages.last().reasoning)
        assertEquals("", afterCompleteClose.messages.last().inlineReasoningPendingTag)
        assertFalse(afterCompleteClose.messages.last().isReasoningOpen)
    }

    @Test
    fun incompleteInlineThinkTagPlaceholderIsClearedOnDone() {
        val state = RuntimeUiState(
            messages = listOf(RuntimeChatMessage(role = "assistant", content = "")),
            isStreaming = true,
            activeRequestId = "active-request",
        )

        val afterPartialTag = state.withChatDelta(
            envelope(
                type = MessageType.ChatDelta,
                requestId = "active-request",
                serializer = ChatDeltaPayload.serializer(),
                payload = ChatDeltaPayload(delta = "<thi"),
            ),
            ChatDeltaPayload(delta = "<thi"),
        )
        val afterDone = afterPartialTag.withChatDone(
            envelope(
                type = MessageType.ChatDone,
                requestId = "active-request",
                serializer = ChatDonePayload.serializer(),
                payload = ChatDonePayload(),
            ),
            ChatDonePayload(),
        )

        assertEquals("<thi", afterPartialTag.messages.last().inlineReasoningPendingTag)
        assertTrue(afterDone.messages.isEmpty())
        assertFalse(afterDone.isStreaming)
        assertNull(afterDone.activeRequestId)
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun persistedComposerDraftRestoresOnViewModelCreationAndUpdatesWithTyping() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val channel = ScriptedRuntimeProtocolChannel()
            val localStore = FakeRuntimeLocalDataStore(
                initialData = PersistedRuntimeData(
                    composerDraft = "Restore this draft",
                    trustedRuntimeAutoReconnectEnabled = false,
                ),
            )
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Composer draft restore should not open direct transport")
                    },
                    relayConnector = RuntimeRelayConnector { _, _ -> channel },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = FakeTrustedRuntimeStore(),
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = localStore,
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                ),
            )
            advanceUntilIdle()

            assertEquals("Restore this draft", viewModel.state.value.chatInput)

            viewModel.updateChatInput("Edited persisted draft")
            advanceUntilIdle()

            assertEquals("Edited persisted draft", viewModel.state.value.chatInput)
            assertEquals("Edited persisted draft", localStore.data.composerDraft)
            assertTrue(channel.sentEnvelopes.isEmpty())
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun openPreviousChatRestoresSessionScopedComposerDrafts() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val initialData = PersistedRuntimeData(
                selectedModelId = "ollama:llama3.1:8b",
                trustedRuntimeAutoReconnectEnabled = false,
            )
                .withPersistedMessages(
                    sessionId = "session-a",
                    messages = listOf(RuntimeChatMessage(role = "user", content = "Question A")),
                    nowMillis = 100L,
                )
                .withPersistedMessages(
                    sessionId = "session-b",
                    messages = listOf(RuntimeChatMessage(role = "user", content = "Question B")),
                    nowMillis = 200L,
                )
                .withComposerDraft("Draft A", sessionId = "session-a")
                .withComposerDraft("Draft B", sessionId = "session-b")
                .withActiveSession("session-a")
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                initialData = initialData,
            )

            assertEquals("Draft A", fixture.viewModel.state.value.chatInput)

            val sessionAAttachment = textAttachment().copy(name = "session-a-note.txt")
            fixture.viewModel.replaceStateForTest {
                it.copy(pendingAttachments = listOf(sessionAAttachment))
            }

            fixture.viewModel.openPreviousChat("session-b")
            advanceUntilIdle()

            assertEquals("Draft B", fixture.viewModel.state.value.chatInput)
            assertTrue(fixture.viewModel.state.value.pendingAttachments.isEmpty())

            fixture.viewModel.updateChatInput("Edited B")
            advanceUntilIdle()

            assertEquals(
                "Edited B",
                fixture.localStore.data.sessions.single { it.id == "session-b" }.composerDraft,
            )
            assertEquals(
                "Draft A",
                fixture.localStore.data.sessions.single { it.id == "session-a" }.composerDraft,
            )

            fixture.viewModel.openPreviousChat("session-a")
            advanceUntilIdle()

            assertEquals("Draft A", fixture.viewModel.state.value.chatInput)
            assertEquals(listOf(sessionAAttachment), fixture.viewModel.state.value.pendingAttachments)

            fixture.viewModel.openPreviousChat("session-b")
            advanceUntilIdle()

            assertEquals("Edited B", fixture.viewModel.state.value.chatInput)
            assertTrue(fixture.viewModel.state.value.pendingAttachments.isEmpty())
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun clearChatDraftClearsActiveSessionTextAndPendingAttachments() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val initialData = PersistedRuntimeData(
                selectedModelId = "ollama:llama3.1:8b",
                trustedRuntimeAutoReconnectEnabled = false,
            )
                .withPersistedMessages(
                    sessionId = "session-a",
                    messages = listOf(RuntimeChatMessage(role = "user", content = "Question A")),
                    nowMillis = 100L,
                )
                .withComposerDraft("Draft A", sessionId = "session-a")
                .withActiveSession("session-a")
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                initialData = initialData,
            )
            val pendingAttachment = textAttachment().copy(name = "draft-note.txt")
            val pendingAttachmentsBySession =
                fixture.viewModel.privateField<MutableMap<String?, List<RuntimePendingAttachment>>>(
                    "pendingAttachmentsBySession",
                )
            pendingAttachmentsBySession?.put("session-a", listOf(pendingAttachment))
            fixture.viewModel.replaceStateForTest {
                it.copy(
                    activeChatSessionId = "session-a",
                    chatInput = "Draft A",
                    pendingAttachments = listOf(pendingAttachment),
                )
            }

            fixture.viewModel.clearChatDraft()
            advanceUntilIdle()

            assertEquals("", fixture.viewModel.state.value.chatInput)
            assertTrue(fixture.viewModel.state.value.pendingAttachments.isEmpty())
            assertEquals(
                "",
                fixture.localStore.data.sessions.single { it.id == "session-a" }.composerDraft,
            )
            assertFalse(pendingAttachmentsBySession?.containsKey("session-a") == true)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun startNewChatClearsNoActiveDraftButKeepsSessionDrafts() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val initialData = PersistedRuntimeData(
                selectedModelId = "ollama:llama3.1:8b",
                composerDraft = "No-active stale draft",
                trustedRuntimeAutoReconnectEnabled = false,
            )
                .withPersistedMessages(
                    sessionId = "session-a",
                    messages = listOf(RuntimeChatMessage(role = "user", content = "Question A")),
                    nowMillis = 100L,
                )
                .withComposerDraft("Draft A", sessionId = "session-a")
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                initialData = initialData,
            )
            assertEquals("Draft A", fixture.viewModel.state.value.chatInput)

            fixture.viewModel.replaceStateForTest {
                it.copy(pendingAttachments = listOf(textAttachment()))
            }

            fixture.viewModel.startNewChat()
            advanceUntilIdle()

            assertNull(fixture.viewModel.state.value.activeChatSessionId)
            assertEquals("", fixture.viewModel.state.value.chatInput)
            assertTrue(fixture.viewModel.state.value.pendingAttachments.isEmpty())
            assertEquals("", fixture.localStore.data.composerDraft)
            assertEquals(
                "Draft A",
                fixture.localStore.data.sessions.single { it.id == "session-a" }.composerDraft,
            )
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun archiveActiveChatClearsNoActiveDraftAndPendingAttachments() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val initialData = PersistedRuntimeData(
                selectedModelId = "ollama:llama3.1:8b",
                composerDraft = "No-active stale draft",
                trustedRuntimeAutoReconnectEnabled = false,
            )
                .withPersistedMessages(
                    sessionId = "session-a",
                    messages = listOf(RuntimeChatMessage(role = "user", content = "Question A")),
                    nowMillis = 100L,
                )
                .withComposerDraft("Draft A", sessionId = "session-a")
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                initialData = initialData,
            )

            fixture.viewModel.replaceStateForTest {
                it.copy(pendingAttachments = listOf(textAttachment()))
            }

            fixture.viewModel.archiveChatSession("session-a")
            advanceUntilIdle()

            assertNull(fixture.viewModel.state.value.activeChatSessionId)
            assertEquals("", fixture.viewModel.state.value.chatInput)
            assertTrue(fixture.viewModel.state.value.pendingAttachments.isEmpty())
            assertEquals("", fixture.localStore.data.composerDraft)
            assertEquals(
                "",
                fixture.localStore.data.sessions.single { it.id == "session-a" }.composerDraft,
            )
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun archiveAllChatsClearsNoActiveDraftAndPendingAttachments() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val initialData = PersistedRuntimeData(
                selectedModelId = "ollama:llama3.1:8b",
                composerDraft = "No-active stale draft",
                trustedRuntimeAutoReconnectEnabled = false,
            )
                .withPersistedMessages(
                    sessionId = "session-a",
                    messages = listOf(RuntimeChatMessage(role = "user", content = "Question A")),
                    nowMillis = 100L,
                )
                .withPersistedMessages(
                    sessionId = "session-b",
                    messages = listOf(RuntimeChatMessage(role = "user", content = "Question B")),
                    nowMillis = 200L,
                )
                .withComposerDraft("Draft A", sessionId = "session-a")
                .withComposerDraft("Draft B", sessionId = "session-b")
                .withActiveSession("session-a")
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                initialData = initialData,
            )

            fixture.viewModel.replaceStateForTest {
                it.copy(pendingAttachments = listOf(textAttachment()))
            }

            fixture.viewModel.archiveChatSessions()
            advanceUntilIdle()

            assertNull(fixture.viewModel.state.value.activeChatSessionId)
            assertEquals("", fixture.viewModel.state.value.chatInput)
            assertTrue(fixture.viewModel.state.value.pendingAttachments.isEmpty())
            assertEquals("", fixture.localStore.data.composerDraft)
            assertTrue(fixture.localStore.data.sessions.all { it.archivedAtMillis != null })
            assertEquals(
                "",
                fixture.localStore.data.sessions.single { it.id == "session-a" }.composerDraft,
            )
            assertEquals(
                "",
                fixture.localStore.data.sessions.single { it.id == "session-b" }.composerDraft,
            )
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun openingRuntimeOwnedChatShowsLoadingAndBlocksComposerUntilMessagesArrive() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val initialData = PersistedRuntimeData(
                selectedModelId = "ollama:llama3.1:8b",
                trustedRuntimeAutoReconnectEnabled = false,
                sessions = listOf(
                    PersistedChatSession(
                        id = "runtime-session",
                        title = "Runtime session",
                        modelId = "ollama:llama3.1:8b",
                        createdAtMillis = 100L,
                        updatedAtMillis = 200L,
                        runtimeOwned = true,
                        runtimeMessageCount = 2,
                    )
                ),
            )
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                initialData = initialData,
            )

            fixture.viewModel.openPreviousChat("runtime-session")
            advanceUntilIdle()

            assertEquals("runtime-session", fixture.viewModel.state.value.activeChatSessionId)
            assertEquals("runtime-session", fixture.viewModel.state.value.loadingChatSessionId)
            assertTrue(fixture.viewModel.state.value.isLoadingActiveChatMessages)

            fixture.viewModel.updateChatInput("Do not send yet")
            fixture.viewModel.sendChatMessage()
            advanceUntilIdle()

            assertEquals("", fixture.viewModel.state.value.chatInput)
            assertEquals("chat_history_loading", fixture.viewModel.state.value.error?.code)
            assertTrue(fixture.channel.sentEnvelopes.none { it.type == MessageType.ChatSend })

            fixture.viewModel.renameChatSession("runtime-session", "Should not rename while loading")
            fixture.viewModel.archiveChatSession("runtime-session")
            fixture.viewModel.archiveChatSessions()
            advanceUntilIdle()

            assertEquals("chat_history_loading", fixture.viewModel.state.value.error?.code)
            assertTrue(
                fixture.channel.sentEnvelopes.none {
                    it.type == MessageType.ChatSessionRename || it.type == MessageType.ChatSessionArchive
                }
            )
            val blockedMutationSession = fixture.localStore.data.sessions.single { it.id == "runtime-session" }
            assertEquals("Runtime session", blockedMutationSession.title)
            assertNull(blockedMutationSession.archivedAtMillis)

            val messagesRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.ChatMessagesList }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.ChatMessagesList,
                    serializer = ChatMessagesListResultPayload.serializer(),
                    payload = ChatMessagesListResultPayload(
                        sessionId = "runtime-session",
                        messages = listOf(
                            ChatStoredMessagePayload(role = "user", content = "Runtime prompt"),
                            ChatStoredMessagePayload(role = "assistant", content = "Runtime answer"),
                        ),
                    ),
                    requestId = messagesRequest.requestId,
                )
            )
            advanceUntilIdle()

            assertNull(fixture.viewModel.state.value.loadingChatSessionId)
            assertFalse(fixture.viewModel.state.value.isLoadingActiveChatMessages)
            assertEquals(
                listOf("Runtime prompt", "Runtime answer"),
                fixture.viewModel.state.value.messages.map { it.content },
            )
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun chatMessagesListRejectsInlineStoredAttachmentBytesBeforeTranscriptPublication() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val initialData = PersistedRuntimeData(
                selectedModelId = "ollama:llama3.1:8b",
                trustedRuntimeAutoReconnectEnabled = false,
                sessions = listOf(
                    PersistedChatSession(
                        id = "runtime-session",
                        title = "Runtime session",
                        modelId = "ollama:llama3.1:8b",
                        createdAtMillis = 100L,
                        updatedAtMillis = 200L,
                        runtimeOwned = true,
                        runtimeMessageCount = 1,
                        messages = listOf(
                            PersistedChatMessage(
                                id = "existing-message",
                                role = "user",
                                content = "Existing prompt",
                                createdAtMillis = 100L,
                            ),
                        ),
                    )
                ),
            )
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                initialData = initialData,
            )

            fixture.viewModel.openPreviousChat("runtime-session")
            advanceUntilIdle()

            val messagesRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.ChatMessagesList }
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.ChatMessagesList,
                    requestId = messagesRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "session_id": "runtime-session",
                              "messages": [
                                {
                                  "role": "user",
                                  "content": "Malformed attachment bytes",
                                  "attachments": [
                                    {
                                      "type": "document",
                                      "mime_type": "text/plain",
                                      "name": "context.txt",
                                      "text": "Saved context",
                                      "data_base64": "U2F2ZWQgY29udGV4dA=="
                                    }
                                  ],
                                  "created_at": "2026-06-23T09:02:06Z"
                                }
                              ]
                            }
                        """.trimIndent(),
                    ).jsonObject,
                )
            )
            advanceUntilIdle()

            val state = fixture.viewModel.state.value
            assertNull(state.loadingChatSessionId)
            assertFalse(state.isLoadingActiveChatMessages)
            assertEquals("invalid_payload", state.error?.code)
            assertTrue(state.error?.technicalDetail.orEmpty().contains("chat.messages.list"))
            assertTrue(state.error?.technicalDetail.orEmpty().contains("messages[0].attachments[0].data_base64"))
            assertEquals(listOf("Existing prompt"), state.messages.map { it.content })
            val persistedSession = fixture.localStore.data.sessions.single { it.id == "runtime-session" }
            assertEquals(listOf("Existing prompt"), persistedSession.messages.map { it.content })
            assertFalse(json.encodeToString(fixture.localStore.data).contains("U2F2ZWQgY29udGV4dA=="))
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun chatMessagesListRejectsUnknownMetadataBeforeTranscriptPublication() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val initialData = PersistedRuntimeData(
                selectedModelId = "ollama:llama3.1:8b",
                trustedRuntimeAutoReconnectEnabled = false,
                sessions = listOf(
                    PersistedChatSession(
                        id = "runtime-session",
                        title = "Runtime session",
                        modelId = "ollama:llama3.1:8b",
                        createdAtMillis = 100L,
                        updatedAtMillis = 200L,
                        runtimeOwned = true,
                        runtimeMessageCount = 1,
                        messages = listOf(
                            PersistedChatMessage(
                                id = "existing-message",
                                role = "user",
                                content = "Existing prompt",
                                createdAtMillis = 100L,
                            ),
                        ),
                    )
                ),
            )
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                initialData = initialData,
            )

            fixture.viewModel.openPreviousChat("runtime-session")
            advanceUntilIdle()

            val topLevelMetadataRequest =
                fixture.channel.sentEnvelopes.last { it.type == MessageType.ChatMessagesList }
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.ChatMessagesList,
                    requestId = topLevelMetadataRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "session_id": "runtime-session",
                              "messages": [
                                {
                                  "role": "user",
                                  "content": "Leaky top-level transcript",
                                  "created_at": "2026-06-23T09:02:00Z"
                                }
                              ],
                              "backend_url": "http://127.0.0.1:11434"
                            }
                        """.trimIndent(),
                    ).jsonObject,
                )
            )
            advanceUntilIdle()

            val topLevelRejectedState = fixture.viewModel.state.value
            assertNull(topLevelRejectedState.loadingChatSessionId)
            assertFalse(topLevelRejectedState.isLoadingActiveChatMessages)
            assertEquals("invalid_payload", topLevelRejectedState.error?.code)
            assertTrue(topLevelRejectedState.error?.technicalDetail.orEmpty().contains("chat.messages.list"))
            assertTrue(topLevelRejectedState.error?.technicalDetail.orEmpty().contains("backend_url"))
            assertEquals(listOf("Existing prompt"), topLevelRejectedState.messages.map { it.content })
            assertEquals(
                listOf("Existing prompt"),
                fixture.localStore.data.sessions.single { it.id == "runtime-session" }.messages.map { it.content },
            )
            assertFalse(json.encodeToString(fixture.localStore.data).contains("Leaky top-level transcript"))

            fixture.viewModel.openPreviousChat("runtime-session")
            advanceUntilIdle()

            val messageMetadataRequest =
                fixture.channel.sentEnvelopes.last { it.type == MessageType.ChatMessagesList }
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.ChatMessagesList,
                    requestId = messageMetadataRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "session_id": "runtime-session",
                              "messages": [
                                {
                                  "role": "assistant",
                                  "content": "Leaky message transcript",
                                  "created_at": "2026-06-23T09:02:05Z",
                                  "workspace_id": "workspace-canary"
                                }
                              ]
                            }
                        """.trimIndent(),
                    ).jsonObject,
                )
            )
            advanceUntilIdle()

            val messageRejectedState = fixture.viewModel.state.value
            assertNull(messageRejectedState.loadingChatSessionId)
            assertFalse(messageRejectedState.isLoadingActiveChatMessages)
            assertEquals("invalid_payload", messageRejectedState.error?.code)
            assertTrue(messageRejectedState.error?.technicalDetail.orEmpty().contains("chat.messages.list"))
            assertTrue(messageRejectedState.error?.technicalDetail.orEmpty().contains("messages[0].workspace_id"))
            assertEquals(listOf("Existing prompt"), messageRejectedState.messages.map { it.content })
            assertEquals(
                listOf("Existing prompt"),
                fixture.localStore.data.sessions.single { it.id == "runtime-session" }.messages.map { it.content },
            )
            assertFalse(json.encodeToString(fixture.localStore.data).contains("Leaky message transcript"))

            fixture.viewModel.openPreviousChat("runtime-session")
            advanceUntilIdle()

            val canonicalRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.ChatMessagesList }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.ChatMessagesList,
                    serializer = ChatMessagesListResultPayload.serializer(),
                    payload = ChatMessagesListResultPayload(
                        sessionId = "runtime-session",
                        messages = listOf(
                            ChatStoredMessagePayload(
                                role = "user",
                                content = "Canonical runtime prompt",
                                createdAt = "2026-06-23T09:02:00Z",
                            ),
                            ChatStoredMessagePayload(
                                role = "assistant",
                                content = "Canonical runtime answer",
                                reasoning = "Canonical runtime reasoning",
                                createdAt = "2026-06-23T09:02:05Z",
                            ),
                        ),
                    ),
                    requestId = canonicalRequest.requestId,
                )
            )
            advanceUntilIdle()

            val acceptedState = fixture.viewModel.state.value
            assertNull(acceptedState.loadingChatSessionId)
            assertFalse(acceptedState.isLoadingActiveChatMessages)
            assertNull(acceptedState.error)
            assertEquals(
                listOf("Canonical runtime prompt", "Canonical runtime answer"),
                acceptedState.messages.map { it.content },
            )
            assertEquals("Canonical runtime reasoning", acceptedState.messages.last().reasoning)
            assertEquals(
                listOf("Canonical runtime prompt", "Canonical runtime answer"),
                fixture.localStore.data.sessions.single { it.id == "runtime-session" }.messages.map { it.content },
            )
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun chatMessagesListIgnoresRuntimeOnlyCompactionMetadataInRawPayload() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val sentinel = "runtime_compaction_backend_summary_SENTINEL"
            val initialData = PersistedRuntimeData(
                selectedModelId = "ollama:llama3.1:8b",
                trustedRuntimeAutoReconnectEnabled = false,
                sessions = listOf(
                    PersistedChatSession(
                        id = "runtime-session",
                        title = "Runtime session",
                        modelId = "ollama:llama3.1:8b",
                        createdAtMillis = 100L,
                        updatedAtMillis = 200L,
                        runtimeOwned = true,
                        runtimeMessageCount = 2,
                    )
                ),
            )
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                initialData = initialData,
            )

            fixture.viewModel.openPreviousChat("runtime-session")
            advanceUntilIdle()

            val messagesRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.ChatMessagesList }
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.ChatMessagesList,
                    requestId = messagesRequest.requestId,
                    payload = JsonObject(
                        mapOf(
                            "session_id" to JsonPrimitive("runtime-session"),
                            "messages" to JsonArray(
                                listOf(
                                    JsonObject(
                                        mapOf(
                                            "role" to JsonPrimitive("user"),
                                            "content" to JsonPrimitive("Visible prompt"),
                                            "created_at" to JsonPrimitive("2026-06-23T09:02:00Z"),
                                            "compaction_metadata" to compactionMetadataJson(sentinel),
                                        ),
                                    ),
                                    JsonObject(
                                        mapOf(
                                            "role" to JsonPrimitive("assistant"),
                                            "content" to JsonPrimitive("Visible answer"),
                                            "reasoning" to JsonPrimitive("Visible reasoning"),
                                            "source_pointers" to sourcePointersJson(sentinel),
                                            "created_at" to JsonPrimitive("2026-06-23T09:02:05Z"),
                                        ),
                                    ),
                                ),
                            ),
                            "compaction_metadata" to compactionMetadataJson(sentinel),
                            "source_pointers" to sourcePointersJson(sentinel),
                        ),
                    ),
                )
            )
            advanceUntilIdle()

            val stateMessages = fixture.viewModel.state.value.messages
            assertEquals(listOf("Visible prompt", "Visible answer"), stateMessages.map { it.content })
            assertEquals("Visible reasoning", stateMessages.last().reasoning)
            assertTrue(stateMessages.none { it.content.contains(sentinel) || it.reasoning.contains(sentinel) })
            assertNull(fixture.viewModel.state.value.error)

            val persistedMessages = fixture.localStore.data.sessions
                .single { it.id == "runtime-session" }
                .messages
            assertEquals(listOf("Visible prompt", "Visible answer"), persistedMessages.map { it.content })
            assertEquals("Visible reasoning", persistedMessages.last().reasoning)
            val persistedSnapshot = json.encodeToString(fixture.localStore.data)
            assertFalse(persistedSnapshot.contains(sentinel))
            assertFalse(persistedSnapshot.contains("compaction_metadata"))
            assertFalse(persistedSnapshot.contains("source_pointers"))
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun sendChatMessageClearsOnlyActiveSessionComposerDraft() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val initialData = PersistedRuntimeData(
                selectedModelId = "ollama:llama3.1:8b",
                composerDraft = "No-active draft",
                trustedRuntimeAutoReconnectEnabled = false,
            )
                .withPersistedMessages(
                    sessionId = "session-a",
                    messages = listOf(RuntimeChatMessage(role = "user", content = "Question A")),
                    nowMillis = 100L,
                )
                .withPersistedMessages(
                    sessionId = "session-b",
                    messages = listOf(RuntimeChatMessage(role = "user", content = "Question B")),
                    nowMillis = 200L,
                )
                .withComposerDraft("Draft A", sessionId = "session-a")
                .withComposerDraft("Draft B", sessionId = "session-b")
                .withActiveSession("session-a")
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                initialData = initialData,
            )

            fixture.viewModel.sendChatMessage()
            advanceUntilIdle()

            assertEquals("", fixture.viewModel.state.value.chatInput)
            assertEquals(
                "",
                fixture.localStore.data.sessions.single { it.id == "session-a" }.composerDraft,
            )
            assertEquals(
                "Draft B",
                fixture.localStore.data.sessions.single { it.id == "session-b" }.composerDraft,
            )
            assertEquals("No-active draft", fixture.localStore.data.composerDraft)
            assertEquals(1, fixture.channel.sentEnvelopes.count { it.type == MessageType.ChatSend })
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun updateChatInputRejectsWhileStreamingAndPreservesDraft() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val localStore = FakeRuntimeLocalDataStore(
                initialData = PersistedRuntimeData(composerDraft = "stored draft"),
            )
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Chat input changes should not open direct transport")
                    },
                    relayConnector = RuntimeRelayConnector { _, _ ->
                        error("Chat input changes should not open relay transport")
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = FakeTrustedRuntimeStore(),
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = localStore,
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                ),
            )
            advanceUntilIdle()
            viewModel.replaceStateForTest {
                it.copy(
                    chatInput = "keep this draft",
                    isStreaming = true,
                    error = null,
                )
            }

            viewModel.updateChatInput("stale IME value")

            assertEquals("keep this draft", viewModel.state.value.chatInput)
            assertEquals("generation_in_progress", viewModel.state.value.error?.code)
            assertEquals("stored draft", localStore.data.composerDraft)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @Test
    fun staleReasoningDeltaForDifferentRequestIdIsIgnored() {
        val state = RuntimeUiState(
            messages = listOf(
                RuntimeChatMessage(role = "assistant", content = "Partial", reasoning = "Plan"),
            ),
            isStreaming = true,
            activeRequestId = "active-request",
        )

        val afterDelta = state.withChatDelta(
            envelope(
                type = MessageType.ChatDelta,
                requestId = "stale-request",
                serializer = ChatDeltaPayload.serializer(),
                payload = ChatDeltaPayload(reasoningDelta = " stale"),
            ),
            ChatDeltaPayload(reasoningDelta = " stale"),
        )

        assertSame(state, afterDelta)
        assertEquals("Partial", afterDelta.messages.last().content)
        assertEquals("Plan", afterDelta.messages.last().reasoning)
    }

    @Test
    fun cancelAckAndErrorForUnrelatedRequestsDoNotClearActiveStreaming() {
        val state = RuntimeUiState(
            messages = listOf(RuntimeChatMessage(role = "assistant", content = "Partial")),
            isStreaming = true,
            activeRequestId = "active-request",
            isLoadingModels = true,
            installingModelId = "lm_studio:model",
        )

        val afterCancel = state.withChatCancelAck(
            envelope(
                type = MessageType.ChatCancel,
                requestId = "cancel-request",
                serializer = ChatCancelPayload.serializer(),
                payload = ChatCancelPayload(targetRequestId = "other-request"),
            ),
            ChatCancelPayload(targetRequestId = "other-request"),
        )
        val afterError = afterCancel.withRuntimeError(
            envelope(
                type = MessageType.Error,
                requestId = "other-request",
                serializer = ErrorPayload.serializer(),
                payload = ErrorPayload(
                    code = "backend_unavailable",
                    message = "Different request failed",
                    retryable = false,
                ),
            ),
            ErrorPayload(
                code = "backend_unavailable",
                message = "Different request failed",
                retryable = false,
            ),
            pendingModelPullRequestId = "model-pull-request",
        )

        assertSame(state, afterCancel)
        assertTrue(afterError.isStreaming)
        assertEquals("active-request", afterError.activeRequestId)
        assertEquals("lm_studio:model", afterError.installingModelId)
        assertFalse(afterError.isLoadingModels)
        assertEquals("backend_unavailable", afterError.error?.code)
        assertNull(afterError.error?.detail)
        assertEquals("Different request failed", afterError.error?.technicalDetail)
    }

    @Test
    fun activeChatDoneAndCancelClearStreamingOnlyForActiveRequest() {
        val state = RuntimeUiState(
            isStreaming = true,
            activeRequestId = "active-request",
            error = RuntimeUiError("previous_error"),
        )

        val afterDone = state.withChatDone(
            envelope(
                type = MessageType.ChatDone,
                requestId = "active-request",
                serializer = ChatDonePayload.serializer(),
                payload = ChatDonePayload(finishReason = "cancelled"),
            ),
            ChatDonePayload(finishReason = "cancelled"),
        )
        val afterCancel = state.withChatCancelAck(
            envelope(
                type = MessageType.ChatCancel,
                requestId = "cancel-request",
                serializer = ChatCancelPayload.serializer(),
                payload = ChatCancelPayload(targetRequestId = "active-request"),
            ),
            ChatCancelPayload(targetRequestId = "active-request"),
        )

        assertFalse(afterDone.isStreaming)
        assertNull(afterDone.activeRequestId)
        assertEquals("generation_cancelled", afterDone.error?.code)
        assertFalse(afterCancel.isStreaming)
        assertNull(afterCancel.activeRequestId)
        assertNull(afterCancel.error)
    }

    @Test
    fun activeCompletionCancellationAndErrorRemoveOnlyBlankAssistantPlaceholder() {
        val userMessage = RuntimeChatMessage(id = "user", role = "user", content = "Question")
        val blankAssistant = RuntimeChatMessage(id = "assistant", role = "assistant", content = "")
        val blankState = RuntimeUiState(
            messages = listOf(userMessage, blankAssistant),
            isStreaming = true,
            activeRequestId = "active-request",
        )

        val afterDone = blankState.withChatDone(
            envelope(
                type = MessageType.ChatDone,
                requestId = "active-request",
                serializer = ChatDonePayload.serializer(),
                payload = ChatDonePayload(),
            ),
            ChatDonePayload(),
        )
        val afterCancel = blankState.withChatCancelAck(
            envelope(
                type = MessageType.ChatCancel,
                requestId = "cancel-request",
                serializer = ChatCancelPayload.serializer(),
                payload = ChatCancelPayload(targetRequestId = "active-request"),
            ),
            ChatCancelPayload(targetRequestId = "active-request"),
        )
        val afterError = blankState.withRuntimeError(
            envelope(
                type = MessageType.Error,
                requestId = "active-request",
                serializer = ErrorPayload.serializer(),
                payload = ErrorPayload(
                    code = "backend_unavailable",
                    message = "Backend failed",
                    retryable = false,
                ),
            ),
            ErrorPayload(
                code = "backend_unavailable",
                message = "Backend failed",
                retryable = false,
            ),
            pendingModelPullRequestId = null,
        )

        assertEquals(listOf(userMessage), afterDone.messages)
        assertEquals(listOf(userMessage), afterCancel.messages)
        assertEquals(listOf(userMessage), afterError.messages)
        assertFalse(afterDone.isStreaming)
        assertFalse(afterCancel.isStreaming)
        assertFalse(afterError.isStreaming)
        assertEquals("backend_unavailable", afterError.error?.code)
        assertNull(afterError.error?.detail)
        assertEquals("Backend failed", afterError.error?.technicalDetail)

        val partialAssistant = blankAssistant.copy(content = "Partial")
        val reasoningAssistant = blankAssistant.copy(reasoning = "Thinking")
        val afterPartialError = blankState.copy(messages = listOf(userMessage, partialAssistant))
            .withRuntimeError(
                envelope(
                    type = MessageType.Error,
                    requestId = "active-request",
                    serializer = ErrorPayload.serializer(),
                    payload = ErrorPayload(
                        code = "backend_unavailable",
                        message = "Backend failed",
                        retryable = false,
                    ),
                ),
                ErrorPayload(
                    code = "backend_unavailable",
                    message = "Backend failed",
                    retryable = false,
                ),
                pendingModelPullRequestId = null,
            )
        val afterReasoningDone = blankState.copy(messages = listOf(userMessage, reasoningAssistant))
            .withChatDone(
                envelope(
                    type = MessageType.ChatDone,
                    requestId = "active-request",
                    serializer = ChatDonePayload.serializer(),
                    payload = ChatDonePayload(),
                ),
                ChatDonePayload(),
            )

        assertEquals(partialAssistant, afterPartialError.messages.last())
        assertEquals(reasoningAssistant, afterReasoningDone.messages.last())
    }

    @Test
    fun activeStreamTerminationClosesTrailingAssistantReasoningState() {
        val userMessage = RuntimeChatMessage(id = "user", role = "user", content = "Question")
        val priorAssistant = RuntimeChatMessage(
            id = "assistant-prior",
            role = "assistant",
            content = "Earlier answer",
            reasoning = "Older reasoning",
            isReasoningOpen = true,
            inlineReasoningPendingTag = "<thi",
        )
        val activeAssistant = RuntimeChatMessage(
            id = "assistant-active",
            role = "assistant",
            content = "Partial answer",
            reasoning = "Active reasoning",
            isReasoningOpen = true,
            inlineReasoningPendingTag = "</thi",
        )
        val state = RuntimeUiState(
            messages = listOf(priorAssistant, userMessage, activeAssistant),
            isConnected = true,
            isStreaming = true,
            activeRequestId = "active-request",
            runtimeStatus = "connected",
        )

        val afterDone = state.withChatDone(
            envelope(
                type = MessageType.ChatDone,
                requestId = "active-request",
                serializer = ChatDonePayload.serializer(),
                payload = ChatDonePayload(),
            ),
            ChatDonePayload(),
        )
        val afterCancel = state.withChatCancelAck(
            envelope(
                type = MessageType.ChatCancel,
                requestId = "cancel-request",
                serializer = ChatCancelPayload.serializer(),
                payload = ChatCancelPayload(targetRequestId = "active-request"),
            ),
            ChatCancelPayload(targetRequestId = "active-request"),
        )
        val afterError = state.withRuntimeError(
            envelope(
                type = MessageType.Error,
                requestId = "active-request",
                serializer = ErrorPayload.serializer(),
                payload = ErrorPayload(
                    code = "backend_unavailable",
                    message = "Backend failed",
                    retryable = false,
                ),
            ),
            ErrorPayload(
                code = "backend_unavailable",
                message = "Backend failed",
                retryable = false,
            ),
            pendingModelPullRequestId = null,
        )
        val afterReceiveFailure = state.withRuntimeReceiveFailure("socket closed")

        listOf(afterDone, afterCancel, afterError, afterReceiveFailure).forEach { updated ->
            assertEquals(priorAssistant, updated.messages.first())
            val trailingAssistant = updated.messages.last()
            assertEquals("assistant-active", trailingAssistant.id)
            assertEquals("Partial answer", trailingAssistant.content)
            assertEquals("Active reasoning", trailingAssistant.reasoning)
            assertFalse(trailingAssistant.isReasoningOpen)
            assertEquals("", trailingAssistant.inlineReasoningPendingTag)
            assertFalse(updated.isStreaming)
            assertNull(updated.activeRequestId)
        }
    }

    @Test
    fun runtimeReceiveFailureClearsStreamingAndRemovesOnlyBlankAssistantPlaceholder() {
        val userMessage = RuntimeChatMessage(id = "user", role = "user", content = "Question")
        val blankAssistant = RuntimeChatMessage(id = "assistant", role = "assistant", content = "")
        val blankState = RuntimeUiState(
            isConnected = true,
            isStreaming = true,
            installingModelId = "ollama:pulling",
            activeRequestId = "active-request",
            activeRouteKind = RuntimeActiveRouteKind.Relay,
            runtimeStatus = "connected",
            messages = listOf(userMessage, blankAssistant),
            documentCatalog = RuntimeDocumentCatalog(
                documents = listOf(
                    RuntimeDocumentIndexDocument(
                        id = "doc-receive-failure-catalog",
                        displayName = "Receive Failure Catalog.md",
                        mimeType = "text/markdown",
                        contentFingerprint = "bbccddeeff001122",
                        extractedCharacterCount = 240,
                        chunkCount = 2,
                        quality = "chunked",
                    ),
                ),
                summary = RuntimeDocumentIndexSummary(
                    documentCount = 1,
                    chunkCount = 2,
                    extractedCharacterCount = 240,
                    qualityCounts = RuntimeDocumentQualityCounts(chunked = 1),
                ),
            ),
            documentSearchQuery = "source anchor",
            documentSearchResults = listOf(
                RuntimeDocumentSearchResult(
                    document = RuntimeDocumentIndexDocument(
                        id = "doc-receive-failure",
                        displayName = "Receive Failure.md",
                        mimeType = "text/markdown",
                        contentFingerprint = "aabbccddeeff0011",
                        extractedCharacterCount = 120,
                        chunkCount = 1,
                        quality = "single_chunk",
                    ),
                    chunkIndex = 0,
                    startCharacterOffset = 0,
                    endCharacterOffset = 40,
                    rank = 1,
                    matchedTerms = listOf("source", "anchor"),
                    snippet = "Receive failure must clear stale source anchors.",
                    sourceAnchorId = "source_anchor_aabbccddeeff0011",
                ),
            ),
            isLoadingDocumentCatalog = true,
            isSearchingDocuments = true,
        )

        val afterBlankFailure = blankState.withRuntimeReceiveFailure("socket closed")

        assertFalse(afterBlankFailure.isConnected)
        assertFalse(afterBlankFailure.isStreaming)
        assertNull(afterBlankFailure.installingModelId)
        assertNull(afterBlankFailure.activeRequestId)
        assertTrue(afterBlankFailure.documentCatalog.documents.isEmpty())
        assertEquals(RuntimeDocumentIndexSummary(), afterBlankFailure.documentCatalog.summary)
        assertFalse(afterBlankFailure.isLoadingDocumentCatalog)
        assertEquals("", afterBlankFailure.documentSearchQuery)
        assertTrue(afterBlankFailure.documentSearchResults.isEmpty())
        assertFalse(afterBlankFailure.isSearchingDocuments)
        assertNull(afterBlankFailure.activeRouteKind)
        assertEquals("disconnected", afterBlankFailure.runtimeStatus)
        assertEquals(listOf(userMessage), afterBlankFailure.messages)
        assertEquals("receive_failed", afterBlankFailure.error?.code)
        assertNull(afterBlankFailure.error?.detail)
        assertEquals("socket closed", afterBlankFailure.error?.technicalDetail)

        val partialAssistant = blankAssistant.copy(content = "Partial")
        val reasoningAssistant = blankAssistant.copy(reasoning = "Thinking")
        val afterPartialFailure = blankState.copy(messages = listOf(userMessage, partialAssistant))
            .withRuntimeReceiveFailure("socket closed")
        val afterReasoningFailure = blankState.copy(messages = listOf(userMessage, reasoningAssistant))
            .withRuntimeReceiveFailure("socket closed")

        assertEquals(partialAssistant, afterPartialFailure.messages.last())
        assertEquals(reasoningAssistant, afterReasoningFailure.messages.last())
    }

    @Test
    fun relayReceiveAuthenticationFailureUsesRouteAuthError() {
        val state = RuntimeUiState(activeRouteKind = RuntimeActiveRouteKind.Relay)
        val error = javax.crypto.AEADBadTagException("Tag mismatch")

        val uiError = state.runtimeReceiveFailureUiError(error)
        val failedState = state.withRuntimeReceiveFailure(uiError)

        assertEquals("remote_route_auth_failed", uiError.code)
        assertEquals("route_diagnostic_relay_auth_failed", uiError.diagnosticCode)
        assertEquals("remote_route_auth_failed", failedState.error?.code)
        assertNull(failedState.activeRouteKind)
    }

    @Test
    fun nonRelayReceiveFailureKeepsGenericReceiveError() {
        val state = RuntimeUiState(activeRouteKind = RuntimeActiveRouteKind.DirectTcp)

        val uiError = state.runtimeReceiveFailureUiError(javax.crypto.AEADBadTagException("Tag mismatch"))

        assertEquals("receive_failed", uiError.code)
    }

    @Test
    fun runtimeAuthenticationErrorTransitionsToPairingRequiredState() {
        val state = RuntimeUiState(
            isConnected = true,
            isConnecting = true,
            isStreaming = true,
            isLoadingModels = true,
            installingModelId = "ollama:llama3",
            activeRequestId = "hello-request",
            runtimeStatus = "connected",
            backendAvailable = true,
            backendCode = "ok",
            providerStatuses = listOf(
                RuntimeProviderStatus(
                    id = "ollama",
                    name = "Ollama",
                    available = true,
                )
            ),
        )

        val afterError = state.withRuntimeError(
            envelope(
                type = MessageType.Error,
                requestId = "hello-request",
                serializer = ErrorPayload.serializer(),
                payload = ErrorPayload(
                    code = "authentication_required",
                    message = "Pair this device first",
                    retryable = false,
                ),
            ),
            ErrorPayload(
                code = "authentication_required",
                message = "Pair this device first",
                retryable = false,
            ),
            pendingModelPullRequestId = null,
        )

        assertFalse(afterError.isConnected)
        assertFalse(afterError.isConnecting)
        assertFalse(afterError.isStreaming)
        assertFalse(afterError.isLoadingModels)
        assertNull(afterError.installingModelId)
        assertNull(afterError.activeRequestId)
        assertEquals("pairing_required", afterError.runtimeStatus)
        assertNull(afterError.backendAvailable)
        assertNull(afterError.backendCode)
        assertTrue(afterError.providerStatuses.isEmpty())
        assertEquals("pairing_required", afterError.error?.code)
        assertNull(afterError.error?.detail)
        assertEquals("Pair this device first", afterError.error?.technicalDetail)
    }

    @Test
    fun runtimePairingRequiredCodeMatchingIsCaseInsensitive() {
        assertTrue("pairing_required".isPairingRequiredRuntimeCode())
        assertTrue("AUTHENTICATION_REQUIRED".isPairingRequiredRuntimeCode())
        assertFalse("connection_failed".isPairingRequiredRuntimeCode())
        assertFalse(null.isPairingRequiredRuntimeCode())
    }

    @Test
    fun persistedMessagesCreateSortedSessionSummaryAndReloadActiveMessages() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "older",
                messages = listOf(RuntimeChatMessage(id = "m1", role = "user", content = "Older question")),
                nowMillis = 100L,
            )
            .withPersistedMessages(
                sessionId = "newer",
                messages = listOf(
                    RuntimeChatMessage(id = "m2", role = "user", content = "Newer question"),
                    RuntimeChatMessage(id = "m3", role = "assistant", content = "Newer answer"),
                ),
                nowMillis = 200L,
            )

        val sessions = runtimeChatSessions(data)

        assertEquals(listOf("newer", "older"), sessions.map { it.id })
        assertEquals("", sessions.first().title)
        assertEquals(2, sessions.first().messageCount)
        assertEquals("newer", data.activeSessionId)
        assertEquals("Newer answer", activeSessionMessages(data).last().content)
    }

    @Test
    fun newPersistedMessagesDoNotUseFirstUserPromptAsTitle() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "session",
                messages = listOf(RuntimeChatMessage(id = "m1", role = "user", content = "Original prompt")),
                nowMillis = 100L,
            )

        val session = data.sessions.single()

        assertEquals("", session.title)
        assertFalse(session.titleManuallyEdited)
        assertFalse(session.titleGenerated)
    }

    @Test
    fun sanitizedMigratesLegacyPromptTitleToDefaultTitle() {
        val data = PersistedRuntimeData(
            activeSessionId = "legacy",
            sessions = listOf(
                PersistedChatSession(
                    id = "legacy",
                    title = "Original prompt",
                    createdAtMillis = 10L,
                    updatedAtMillis = 20L,
                    messages = listOf(
                        PersistedChatMessage(
                            id = "m1",
                            role = "user",
                            content = "Original prompt",
                            createdAtMillis = 10L,
                        ),
                    ),
                ),
            ),
        ).sanitized()

        val session = data.sessions.single()

        assertEquals("", session.title)
        assertFalse(session.titleManuallyEdited)
        assertFalse(session.titleGenerated)
        assertEquals("legacy", data.activeSessionId)
    }

    @Test
    fun sanitizedPreservesExplicitAndRuntimeGeneratedPromptTitles() {
        val data = PersistedRuntimeData(
            sessions = listOf(
                PersistedChatSession(
                    id = "manual",
                    title = "Original prompt",
                    createdAtMillis = 10L,
                    updatedAtMillis = 30L,
                    titleManuallyEdited = true,
                    messages = listOf(
                        PersistedChatMessage(
                            id = "manual-message",
                            role = "user",
                            content = "Original prompt",
                            createdAtMillis = 10L,
                        ),
                    ),
                ),
                PersistedChatSession(
                    id = "generated",
                    title = "Original prompt",
                    createdAtMillis = 10L,
                    updatedAtMillis = 20L,
                    titleGenerated = true,
                    messages = listOf(
                        PersistedChatMessage(
                            id = "generated-message",
                            role = "user",
                            content = "Original prompt",
                            createdAtMillis = 10L,
                        ),
                    ),
                ),
                PersistedChatSession(
                    id = "manual-default",
                    title = "New chat",
                    createdAtMillis = 10L,
                    updatedAtMillis = 40L,
                    titleManuallyEdited = true,
                ),
                PersistedChatSession(
                    id = "generated-default",
                    title = "New chat",
                    createdAtMillis = 10L,
                    updatedAtMillis = 50L,
                    titleGenerated = true,
                ),
            ),
        ).sanitized()

        assertEquals("Original prompt", data.sessions.first { it.id == "manual" }.title)
        assertTrue(data.sessions.first { it.id == "manual" }.titleManuallyEdited)
        assertEquals("Original prompt", data.sessions.first { it.id == "generated" }.title)
        assertTrue(data.sessions.first { it.id == "generated" }.titleGenerated)
        assertEquals("New chat", data.sessions.first { it.id == "manual-default" }.title)
        assertTrue(data.sessions.first { it.id == "manual-default" }.titleManuallyEdited)
        assertEquals("New chat", data.sessions.first { it.id == "generated-default" }.title)
        assertTrue(data.sessions.first { it.id == "generated-default" }.titleGenerated)
        assertTrue(runtimeChatSessions(data).first { it.id == "manual-default" }.titleManuallyEdited)
        assertTrue(runtimeChatSessions(data).first { it.id == "generated-default" }.titleGenerated)
    }

    @Test
    fun sanitizedCapsSessionScopedComposerDrafts() {
        val oversizedDraft = "x".repeat(25_000)
        val data = PersistedRuntimeData(
            activeSessionId = "draft-session",
            sessions = listOf(
                PersistedChatSession(
                    id = "draft-session",
                    title = "Draft session",
                    composerDraft = oversizedDraft,
                    createdAtMillis = 10L,
                    updatedAtMillis = 20L,
                ),
            ),
        ).sanitized()

        assertEquals(20_000, data.sessions.single().composerDraft.length)
        assertEquals("x".repeat(20_000), data.composerDraftForSession("draft-session"))
    }

    @Test
    fun sanitizedDropsArchivedSessionComposerDrafts() {
        val data = PersistedRuntimeData(
            activeSessionId = "archived-draft",
            sessions = listOf(
                PersistedChatSession(
                    id = "archived-draft",
                    title = "Archived draft",
                    composerDraft = "Do not keep archived draft",
                    createdAtMillis = 10L,
                    updatedAtMillis = 20L,
                    archivedAtMillis = 30L,
                ),
            ),
        ).sanitized()

        assertNull(data.activeSessionId)
        assertEquals("", data.sessions.single().composerDraft)
        assertEquals("", data.composerDraftForSession("archived-draft"))
    }

    @Test
    fun noActiveSessionKeepsPreviousChatsButClearsCurrentMessages() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "previous",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Saved chat")),
                nowMillis = 100L,
            )
            .withNoActiveSession()

        assertNull(data.activeSessionId)
        assertEquals(listOf("previous"), runtimeChatSessions(data).map { it.id })
        assertTrue(activeSessionMessages(data).isEmpty())
    }

    @Test
    fun renamedChatSessionUsesTrimmedTitleAndMovesSessionToTop() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "older",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Older question")),
                nowMillis = 100L,
            )
            .withPersistedMessages(
                sessionId = "newer",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Newer question")),
                nowMillis = 200L,
            )
            .withRenamedChatSession(
                sessionId = "older",
                title = "  Renamed chat  ",
                nowMillis = 300L,
            )

        val sessions = runtimeChatSessions(data)

        assertEquals(listOf("older", "newer"), sessions.map { it.id })
        assertEquals("Renamed chat", sessions.first().title)
        assertEquals(300L, sessions.first().updatedAtMillis)
        assertEquals("newer", data.activeSessionId)
    }

    @Test
    fun renamedArchivedChatSessionKeepsArchiveState() {
        val data = PersistedRuntimeData(
            sessions = listOf(
                PersistedChatSession(
                    id = "archived-session",
                    title = "Original archived title",
                    createdAtMillis = 100L,
                    updatedAtMillis = 200L,
                    archivedAtMillis = 250L,
                    messages = listOf(
                        PersistedChatMessage(
                            id = "archived-message",
                            role = "user",
                            content = "Archived prompt",
                            createdAtMillis = 100L,
                        ),
                    ),
                ),
            ),
        )
            .withRenamedChatSession(
                sessionId = "archived-session",
                title = " Renamed archived title ",
                nowMillis = 300L,
            )

        assertTrue(runtimeChatSessions(data).isEmpty())
        val archived = archivedRuntimeChatSessions(data).single()
        assertEquals("Renamed archived title", archived.title)
        assertEquals(250L, archived.archivedAtMillis)
        assertEquals(300L, archived.updatedAtMillis)
    }

    @Test
    fun persistedMessagesPreserveRenamedChatSessionTitle() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "session",
                messages = listOf(RuntimeChatMessage(id = "m1", role = "user", content = "Original prompt")),
                nowMillis = 100L,
            )
            .withRenamedChatSession(
                sessionId = "session",
                title = "Project notes",
                nowMillis = 200L,
            )
            .withPersistedMessages(
                sessionId = "session",
                messages = listOf(
                    RuntimeChatMessage(id = "m1", role = "user", content = "Original prompt"),
                    RuntimeChatMessage(id = "m2", role = "assistant", content = "Answer"),
                    RuntimeChatMessage(id = "m3", role = "user", content = "Follow up"),
                ),
                nowMillis = 300L,
            )

        val session = runtimeChatSessions(data).single()

        assertEquals("Project notes", session.title)
        assertEquals(3, session.messageCount)
    }

    @Test
    fun runtimeBackedPersistedMessagesMarkNewSessionRuntimeOwnedForDeletionSuppression() {
        val data = PersistedRuntimeData()
            .withNewChatSession(nowMillis = 100L, sessionId = "local-before-sync")
            .withPersistedMessages(
                sessionId = "local-before-sync",
                messages = listOf(
                    RuntimeChatMessage(id = "m1", role = "user", content = "Prompt sent to runtime"),
                    RuntimeChatMessage(id = "m2", role = "assistant", content = ""),
                ),
                nowMillis = 200L,
                runtimeBacked = true,
            )

        assertTrue(data.sessions.single { it.id == "local-before-sync" }.runtimeOwned)

        val deletedBeforeSync = data.withoutChatSession(
            sessionId = "local-before-sync",
            nowMillis = 300L,
        )
        val afterSummarySync = deletedBeforeSync.withRuntimeChatSessionSummaries(
            sessions = listOf(
                ChatSessionSummaryPayload(
                    sessionId = "local-before-sync",
                    title = "Runtime title",
                    model = "ollama:qwen3:8b",
                    lastActivityAt = "2026-06-23T09:03:05Z",
                    messageCount = 2,
                ),
            ),
            nowMillis = 400L,
        )
        val afterMessageSync = afterSummarySync.withRuntimeChatMessages(
            sessionId = "local-before-sync",
            messages = listOf(ChatStoredMessagePayload(role = "user", content = "Do not restore")),
            nowMillis = 500L,
        )

        assertTrue(afterMessageSync.sessions.none { it.id == "local-before-sync" })
        assertEquals(listOf("local-before-sync"), afterMessageSync.suppressedRuntimeSessions.map { it.sessionId })
        assertEquals("deleted", afterMessageSync.suppressedRuntimeSessions.single().reason)
    }

    @Test
    fun deviceStorageSnapshotDropsRuntimeOwnedDataButKeepsLocalDrafts() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "runtime-session",
                messages = listOf(
                    RuntimeChatMessage(id = "r1", role = "user", content = "Runtime prompt"),
                    RuntimeChatMessage(id = "r2", role = "assistant", content = "Runtime answer"),
                ),
                nowMillis = 100L,
                runtimeBacked = true,
            )
            .withPersistedMessages(
                sessionId = "local-session",
                messages = listOf(RuntimeChatMessage(id = "l1", role = "user", content = "Local note")),
                nowMillis = 200L,
                runtimeBacked = false,
            )
            .withRuntimeMemoryEntry(
                entry = MemoryEntryPayload(
                    id = "memory-1",
                    content = "Runtime-owned memory body",
                    enabled = true,
                    createdAt = "2026-06-25T00:00:00Z",
                    updatedAt = "2026-06-25T00:01:00Z",
                ),
                nowMillis = 300L,
            )

        val storageSnapshot = data.withoutRuntimeOwnedLocalData()

        assertEquals(listOf("Runtime-owned memory body"), data.memoryEntries.map { it.content })
        assertTrue(storageSnapshot.memoryEntries.isEmpty())
        assertTrue(storageSnapshot.sessions.first { it.id == "runtime-session" }.runtimeOwned)
        assertTrue(storageSnapshot.sessions.first { it.id == "runtime-session" }.messages.isEmpty())
        assertEquals(2, runtimeChatSessions(storageSnapshot).first { it.id == "runtime-session" }.messageCount)
        assertEquals(
            listOf("Local note"),
            storageSnapshot.sessions.first { it.id == "local-session" }.messages.map { it.content },
        )
    }

    @Test
    fun deviceStorageSnapshotRedactsArchivedRuntimeOwnedBodiesButKeepsLocalArchivedBodies() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "runtime-archived",
                messages = listOf(
                    RuntimeChatMessage(id = "r1", role = "user", content = "Runtime archived prompt"),
                    RuntimeChatMessage(id = "r2", role = "assistant", content = "Runtime archived answer"),
                ),
                nowMillis = 100L,
                runtimeBacked = true,
            )
            .withPersistedMessages(
                sessionId = "local-archived",
                messages = listOf(RuntimeChatMessage(id = "l1", role = "user", content = "Local archived note")),
                nowMillis = 200L,
                runtimeBacked = false,
            )
            .withArchivedChatSession(
                sessionId = "runtime-archived",
                nowMillis = 300L,
            )
            .withArchivedChatSession(
                sessionId = "local-archived",
                nowMillis = 400L,
            )

        val storageSnapshot = data.withoutRuntimeOwnedLocalData()
        val runtimeArchived = storageSnapshot.sessions.first { it.id == "runtime-archived" }
        val localArchived = storageSnapshot.sessions.first { it.id == "local-archived" }

        assertTrue(runtimeArchived.runtimeOwned)
        assertTrue(runtimeArchived.messages.isEmpty())
        assertEquals(2, archivedRuntimeChatSessions(storageSnapshot).first { it.id == "runtime-archived" }.messageCount)
        assertFalse(localArchived.runtimeOwned)
        assertEquals(listOf("Local archived note"), localArchived.messages.map { it.content })
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun activeRedactedRuntimeSessionRehydratesAfterReconnectSessionSync() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val channel = ScriptedRuntimeProtocolChannel()
            val localStore = FakeRuntimeLocalDataStore(
                initialData = PersistedRuntimeData(
                    activeSessionId = "runtime-session",
                    trustedRuntimeAutoReconnectEnabled = false,
                    sessions = listOf(
                        PersistedChatSession(
                            id = "runtime-session",
                            title = "Runtime session",
                            modelId = "ollama:llama3.1:8b",
                            createdAtMillis = 100L,
                            updatedAtMillis = 200L,
                            runtimeOwned = true,
                            runtimeMessageCount = 2,
                            messages = emptyList(),
                        ),
                    ),
                ),
                redactRuntimeOwnedLocalDataOnSave = true,
            )
            val trustedStore = FakeEmittingTrustedRuntimeStore(
                TrustedRuntime(
                    deviceId = "runtime-1",
                    name = "AetherLink Runtime",
                    fingerprint = "runtime-fingerprint",
                    publicKeyBase64 = "runtime-public-key",
                    routeToken = "route-token-1",
                    relayHost = "relay.example.test",
                    relayPort = 443,
                    relayId = "relay-1",
                    relaySecret = "secret-1",
                    relayExpiresAtEpochMillis = 4_102_444_800_000L,
                    relayNonce = "relay-nonce-1",
                    relayScope = "remote",
                ),
            )
            var capturedRelayRoute: PreparedRemoteRuntimeRoute.Relay? = null
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Direct TCP should not be used for relay-backed reconnect")
                    },
                    relayConnector = RuntimeRelayConnector { route, _ ->
                        capturedRelayRoute = route
                        channel
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = localStore,
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    currentTimeMillis = { 1_000L },
                ),
            )
            advanceUntilIdle()

            assertTrue(viewModel.state.value.messages.isEmpty())
            assertEquals(2, viewModel.state.value.chatSessions.single().messageCount)

            channel.enqueue(
                envelope(
                    type = MessageType.AuthResponse,
                    serializer = com.localagentbridge.android.core.protocol.AuthResponsePayload.serializer(),
                    payload = com.localagentbridge.android.core.protocol.AuthResponsePayload(accepted = true),
                    requestId = "auth-accepted",
                ),
            )
            viewModel.connectToTrustedRuntime()
            advanceUntilIdle()

            assertEquals("relay.example.test", requireNotNull(capturedRelayRoute).host)
            val sessionsRequest = channel.sentEnvelopes.last { it.type == MessageType.ChatSessionsList }
            channel.enqueue(
                envelope(
                    type = MessageType.ChatSessionsList,
                    serializer = ChatSessionsListResultPayload.serializer(),
                    payload = ChatSessionsListResultPayload(
                        sessions = listOf(
                            ChatSessionSummaryPayload(
                                sessionId = "runtime-session",
                                title = "Runtime title",
                                model = "ollama:llama3.1:8b",
                                lastActivityAt = "2026-06-23T09:02:05Z",
                                messageCount = 2,
                                status = "active",
                                lastEvent = "done",
                                lastFinishReason = "stop",
                            ),
                        ),
                    ),
                    requestId = sessionsRequest.requestId,
                ),
            )
            advanceUntilIdle()

            val messagesRequest = channel.sentEnvelopes.last { it.type == MessageType.ChatMessagesList }
            assertEquals(
                "runtime-session",
                json.decodeFromJsonElement(
                    com.localagentbridge.android.core.protocol.ChatMessagesListRequestPayload.serializer(),
                    messagesRequest.payload,
                ).sessionId,
            )

            channel.enqueue(
                envelope(
                    type = MessageType.ChatMessagesList,
                    serializer = ChatMessagesListResultPayload.serializer(),
                    payload = ChatMessagesListResultPayload(
                        sessionId = "runtime-session",
                        messages = listOf(
                            ChatStoredMessagePayload(role = "user", content = "Runtime prompt"),
                            ChatStoredMessagePayload(role = "assistant", content = "Runtime answer"),
                        ),
                    ),
                    requestId = messagesRequest.requestId,
                ),
            )
            advanceUntilIdle()

            assertEquals(
                listOf("Runtime prompt", "Runtime answer"),
                viewModel.state.value.messages.map { it.content },
            )
            assertTrue(localStore.data.sessions.single { it.id == "runtime-session" }.messages.isEmpty())
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun trustedRelayRestoreMarksConnectingBeforeRelayDialCompletes() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val localStore = FakeRuntimeLocalDataStore(
                initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = false),
            )
            val trustedStore = FakeEmittingTrustedRuntimeStore(trustedRuntimeForViewModelTests())
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Direct TCP should not be used for relay-backed trusted restore")
                    },
                    relayConnector = RuntimeRelayConnector { _, _ ->
                        awaitCancellation()
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = localStore,
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    currentTimeMillis = { 1_000L },
                ),
            )
            advanceUntilIdle()

            assertEquals("disconnected", viewModel.state.value.runtimeStatus)

            viewModel.setTrustedRuntimeAutoReconnectEnabled(true)

            assertTrue(viewModel.state.value.isConnecting)
            assertEquals("connecting", viewModel.state.value.runtimeStatus)
            assertEquals("runtime-1", viewModel.state.value.trustedRuntime?.deviceId)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun viewModelAutoReconnectsTrustedRelayOnInitAndRefreshesRuntimeState() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val channel = ScriptedRuntimeProtocolChannel()
            val localStore = FakeRuntimeLocalDataStore(
                initialData = PersistedRuntimeData(
                    selectedModelId = "ollama:llama3.1:8b",
                    selectedEmbeddingModelId = "ollama:nomic-embed-text",
                    trustedRuntimeAutoReconnectEnabled = true,
                ),
            )
            val trustedStore = FakeEmittingTrustedRuntimeStore(trustedRuntimeForViewModelTests())
            var capturedRelayRoute: PreparedRemoteRuntimeRoute.Relay? = null
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Direct TCP should not be used for trusted relay auto-reconnect")
                    },
                    relayConnector = RuntimeRelayConnector { route, _ ->
                        capturedRelayRoute = route
                        channel
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = localStore,
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    currentTimeMillis = { 1_000L },
                ),
            )
            advanceUntilIdle()

            assertEquals("relay.example.test", requireNotNull(capturedRelayRoute).host)
            assertTrue(viewModel.state.value.isConnected)
            assertEquals("connected", viewModel.state.value.runtimeStatus)
            assertEquals("ollama:llama3.1:8b", viewModel.state.value.selectedModelId)
            assertEquals("ollama:nomic-embed-text", viewModel.state.value.selectedEmbeddingModelId)
            assertTrue(channel.sentEnvelopes.any { it.type == MessageType.Hello })

            channel.enqueue(
                envelope(
                    type = MessageType.AuthResponse,
                    serializer = AuthResponsePayload.serializer(),
                    payload = AuthResponsePayload(accepted = true),
                    requestId = "auth-accepted",
                ),
            )
            advanceUntilIdle()

            assertEquals("authenticated", viewModel.state.value.runtimeStatus)
            assertFalse(channel.sentEnvelopes.any { it.type == MessageType.RouteRefresh })
            assertTrue(channel.sentEnvelopes.any { it.type == MessageType.RuntimeHealth })
            assertTrue(channel.sentEnvelopes.any { it.type == MessageType.ChatSessionsList })
            assertTrue(channel.sentEnvelopes.any { it.type == MessageType.MemoryList })

            channel.enqueue(
                envelope(
                    type = MessageType.RuntimeHealth,
                    serializer = RuntimeHealthPayload.serializer(),
                    payload = RuntimeHealthPayload(status = "ok"),
                    requestId = "runtime-health",
                ),
            )
            advanceUntilIdle()

            assertTrue(channel.sentEnvelopes.any { it.type == MessageType.ModelsList })
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun relayReceiveAuthenticationFailureClearsStoredRelayAndStopsAutoReconnect() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val channel = FailingReceiveRuntimeProtocolChannel(
                javax.crypto.AEADBadTagException("Tag mismatch")
            )
            val trustedStore = FakeEmittingTrustedRuntimeStore(trustedRuntimeForViewModelTests())
            var relayConnectionAttempts = 0
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Direct TCP should not be used for trusted relay auto-reconnect")
                    },
                    relayConnector = RuntimeRelayConnector { _, _ ->
                        relayConnectionAttempts += 1
                        channel
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = FakeRuntimeLocalDataStore(
                        initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = true),
                    ),
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    currentTimeMillis = { 1_000L },
                ),
            )
            advanceUntilIdle()

            assertEquals("remote_route_auth_failed", viewModel.state.value.error?.code)
            assertEquals(
                "route_diagnostic_relay_auth_failed",
                viewModel.state.value.error?.diagnosticCode,
            )
            assertNull(viewModel.state.value.trustedRuntime?.relayHost)
            assertNull(viewModel.state.value.trustedRuntime?.relaySecret)
            assertNull(trustedStore.trusted?.relayHost)
            assertNull(trustedStore.trusted?.relaySecret)
            assertEquals(1, relayConnectionAttempts)

            advanceTimeBy(2_000L)
            advanceUntilIdle()

            assertEquals(1, relayConnectionAttempts)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun trustedRelayConnectionFailureKeepsStoredRelayAndStopsAutoReconnectUntilUserRetries() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val trustedStore = FakeEmittingTrustedRuntimeStore(trustedRuntimeForViewModelTests())
            var relayConnectionAttempts = 0
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Direct TCP should not be used for trusted relay auto-reconnect")
                    },
                    relayConnector = RuntimeRelayConnector { _, _ ->
                        relayConnectionAttempts += 1
                        error("Relay route is unreachable from this network")
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = FakeRuntimeLocalDataStore(
                        initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = false),
                    ),
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    currentTimeMillis = { 1_000L },
                ),
            )
            advanceUntilIdle()
            assertEquals("runtime-1", viewModel.state.value.trustedRuntime?.deviceId)
            assertEquals("relay.example.test", viewModel.state.value.trustedRuntime?.relayHost)
            assertEquals("secret-1", viewModel.state.value.trustedRuntime?.relaySecret)

            viewModel.connectToTrustedRuntime()
            runCurrent()
            advanceUntilIdle()

            assertEquals(1, relayConnectionAttempts)
            assertEquals("remote_route_unreachable", viewModel.state.value.error?.code)
            assertEquals(
                "route_diagnostic_relay_failed",
                viewModel.state.value.error?.diagnosticCode,
            )
            assertEquals("relay.example.test", viewModel.state.value.trustedRuntime?.relayHost)
            assertEquals("secret-1", viewModel.state.value.trustedRuntime?.relaySecret)
            assertEquals("relay.example.test", trustedStore.trusted?.relayHost)
            assertEquals("secret-1", trustedStore.trusted?.relaySecret)
            advanceTimeBy(2_000L)
            advanceUntilIdle()

            assertEquals(1, relayConnectionAttempts)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun trustedPeerToPeerRouteFallsBackToRelayAtViewModelConnectionLayer() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val channel = ScriptedRuntimeProtocolChannel()
            val maxSizedP2pEncryptedBody = maxSizedOpaqueP2pEncryptedBody()
            val trustedStore = FakeEmittingTrustedRuntimeStore(
                trustedRuntimeForViewModelTests().copy(
                    p2pRouteClass = "p2p_rendezvous",
                    p2pRecordId = "p2p-record-1",
                    p2pEncryptedBody = maxSizedP2pEncryptedBody,
                    p2pExpiresAtEpochMillis = 4_102_444_800_000L,
                    p2pAntiReplayNonce = "p2p-nonce-1",
                    p2pProtocolVersion = 1,
                ),
            )
            val routeAttempts = mutableListOf<String>()
            var capturedPeerToPeerRoute: PreparedRemoteRuntimeRoute.PeerToPeer? = null
            var capturedRelayRoute: PreparedRemoteRuntimeRoute.Relay? = null
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Direct TCP should not be used when saved remote routes are available")
                    },
                    peerToPeerConnector = RuntimePeerToPeerConnector { route, _ ->
                        routeAttempts += "p2p"
                        capturedPeerToPeerRoute = route
                        error("P2P rendezvous route did not establish a session")
                    },
                    relayConnector = RuntimeRelayConnector { route, _ ->
                        routeAttempts += "relay"
                        capturedRelayRoute = route
                        channel
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = FakeRuntimeLocalDataStore(
                        initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = false),
                    ),
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    currentTimeMillis = { 1_000L },
                ),
            )
            advanceUntilIdle()

            viewModel.connectToTrustedRuntime()
            runCurrent()
            advanceUntilIdle()

            val peerToPeerRoute = requireNotNull(capturedPeerToPeerRoute)
            val relayRoute = requireNotNull(capturedRelayRoute)
            assertEquals(listOf("p2p", "relay"), routeAttempts)
            assertEquals("p2p-record-1", peerToPeerRoute.sessionId)
            assertEquals(OPAQUE_ROUTE_BODY_MAX_CHARS, maxSizedP2pEncryptedBody.length)
            assertEquals(maxSizedP2pEncryptedBody, peerToPeerRoute.encryptedCandidateMaterial)
            assertEquals("p2p-nonce-1", peerToPeerRoute.security.antiReplayNonce)
            assertEquals("relay-1", relayRoute.relayId)
            assertEquals("secret-1", relayRoute.relayFrameSecret)
            assertEquals(RuntimeActiveRouteKind.Relay, viewModel.state.value.activeRouteKind)
            assertEquals("connected", viewModel.state.value.runtimeStatus)
            assertNull(viewModel.state.value.error)
            assertTrue(channel.sentEnvelopes.any { it.type == MessageType.Hello })
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun trustedRelayHandshakeRejectionKeepsStoredRelayAndStopsAutoReconnectUntilUserRetries() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val trustedStore = FakeEmittingTrustedRuntimeStore(trustedRuntimeForViewModelTests())
            var relayConnectionAttempts = 0
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        error("Direct TCP should not be used for trusted relay handshake rejection")
                    },
                    relayConnector = RuntimeRelayConnector { _, _ ->
                        relayConnectionAttempts += 1
                        throw IllegalArgumentException("Relay did not accept route")
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = FakeRuntimeLocalDataStore(
                        initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = false),
                    ),
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    currentTimeMillis = { 1_000L },
                ),
            )
            advanceUntilIdle()

            viewModel.connectToTrustedRuntime()
            runCurrent()
            advanceUntilIdle()

            assertEquals(1, relayConnectionAttempts)
            assertEquals("remote_route_unreachable", viewModel.state.value.error?.code)
            assertEquals(
                "route_diagnostic_relay_failed",
                viewModel.state.value.error?.diagnosticCode,
            )
            assertEquals("relay.example.test", viewModel.state.value.trustedRuntime?.relayHost)
            assertEquals("secret-1", viewModel.state.value.trustedRuntime?.relaySecret)
            assertEquals("relay.example.test", trustedStore.trusted?.relayHost)
            assertEquals("secret-1", trustedStore.trusted?.relaySecret)

            advanceTimeBy(2_000L)
            advanceUntilIdle()

            assertEquals(1, relayConnectionAttempts)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun viewModelShowsExpiredRemoteRouteWhenTrustedRelayLeaseExpiredOnInit() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val localStore = FakeRuntimeLocalDataStore(
                initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = true),
            )
            val trustedStore = FakeEmittingTrustedRuntimeStore(
                trustedRuntimeForViewModelTests().copy(
                    relayExpiresAtEpochMillis = 2_000L,
                ),
            )
            var directConnectionAttempts = 0
            var relayConnectionAttempts = 0
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        directConnectionAttempts += 1
                        error("Direct TCP should not be used when the saved relay lease is expired")
                    },
                    relayConnector = RuntimeRelayConnector { _, _ ->
                        relayConnectionAttempts += 1
                        error("Relay should not be dialed with an expired lease")
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = localStore,
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    currentTimeMillis = { 3_000L },
                ),
            )
            advanceUntilIdle()

            assertEquals(0, directConnectionAttempts)
            assertEquals(0, relayConnectionAttempts)
            assertEquals("failed", viewModel.state.value.runtimeStatus)
            assertEquals("remote_route_expired", viewModel.state.value.error?.code)
            assertEquals(
                "route_diagnostic_remote_route_expired",
                viewModel.state.value.error?.diagnosticCode,
            )
            assertNull(viewModel.state.value.trustedRuntime?.relayHost)
            assertNull(viewModel.state.value.trustedRuntime?.relaySecret)
            assertNull(trustedStore.trusted?.relayHost)
            assertNull(trustedStore.trusted?.relaySecret)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun freshCompactRelayQrRefreshesExpiredTrustedRelayRouteAndReconnectsViaRelay() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val rawUri = "aetherlink://pair?v=1&n=nonce-refresh&c=654321" +
                "&rid=runtime-1&rn=AetherLink%20Runtime&rf=runtime-fingerprint" +
                "&rk=runtime-public-key&rt=route-token-1" +
                "&rh=fresh-relay.example.test&rp=43171&ri=fresh-relay&rs=fresh-secret" +
                "&rx=4102444800000&rrn=fresh-nonce&rsc=remote"
            val channel = ScriptedRuntimeProtocolChannel()
            val localStore = FakeRuntimeLocalDataStore(
                initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = true),
            )
            val trustedStore = FakeEmittingTrustedRuntimeStore(
                trustedRuntimeForViewModelTests().copy(
                    relayHost = "expired-relay.example.test",
                    relayPort = 443,
                    relayId = "expired-relay",
                    relaySecret = "expired-secret",
                    relayExpiresAtEpochMillis = 2_000L,
                    relayNonce = "expired-nonce",
                    relayScope = "remote",
                ),
            )
            var directConnectionAttempts = 0
            var relayConnectionAttempts = 0
            var capturedRelayRoute: PreparedRemoteRuntimeRoute.Relay? = null
            val viewModel = RuntimeClientViewModel(
                application = Application(),
                dependencies = RuntimeClientViewModelDependencies(
                    json = json,
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        directConnectionAttempts += 1
                        error("Direct TCP should not be used when refreshing an expired relay route")
                    },
                    relayConnector = RuntimeRelayConnector { route, _ ->
                        relayConnectionAttempts += 1
                        capturedRelayRoute = route
                        channel
                    },
                    discovery = EmptyRuntimeDiscoverySource,
                    trustedRuntimeStore = trustedStore,
                    deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                    localDataStore = localStore,
                    lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                    currentTimeMillis = { 3_000L },
                ),
            )
            advanceUntilIdle()

            assertEquals("remote_route_expired", viewModel.state.value.error?.code)
            assertNull(viewModel.state.value.trustedRuntime?.relayHost)
            assertNull(viewModel.state.value.trustedRuntime?.relaySecret)
            assertNull(trustedStore.trusted?.relayHost)
            assertNull(trustedStore.trusted?.relaySecret)
            assertEquals(0, directConnectionAttempts)
            assertEquals(0, relayConnectionAttempts)

            viewModel.trustRuntimeFromPairingQr(rawUri)
            advanceUntilIdle()

            val trusted = trustedStore.trusted ?: error("Expected trusted route refresh to persist")
            val relayRoute = requireNotNull(capturedRelayRoute)
            assertEquals(0, directConnectionAttempts)
            assertEquals(1, relayConnectionAttempts)
            assertEquals("fresh-relay.example.test", relayRoute.host)
            assertEquals(43171, relayRoute.port)
            assertEquals("fresh-relay", relayRoute.relayId)
            assertEquals("fresh-secret", relayRoute.relayFrameSecret)
            assertEquals("fresh-nonce", relayRoute.security.antiReplayNonce)
            assertEquals("fresh-relay.example.test", trusted.relayHost)
            assertEquals(43171, trusted.relayPort)
            assertEquals("fresh-relay", trusted.relayId)
            assertEquals("fresh-secret", trusted.relaySecret)
            assertEquals(4102444800000L, trusted.relayExpiresAtEpochMillis)
            assertEquals("fresh-nonce", trusted.relayNonce)
            assertEquals("remote", trusted.relayScope)
            assertNull(trusted.host)
            assertNull(trusted.port)
            assertNull(viewModel.state.value.error)
            assertEquals("fresh-relay.example.test", viewModel.state.value.trustedRuntime?.relayHost)
            assertEquals(4102444800000L, viewModel.state.value.trustedRuntime?.relayExpiresAtEpochMillis)
            assertEquals(RuntimeActiveRouteKind.Relay, viewModel.state.value.activeRouteKind)
            assertEquals("AetherLink Runtime", viewModel.state.value.routeRefreshNoticeRuntimeName)
            assertTrue(channel.sentEnvelopes.any { it.type == MessageType.Hello })
        } finally {
            Dispatchers.resetMain()
        }
    }

    @Test
    fun generatedChatTitleAppliesOnlyUntilUserRenamesSession() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "session",
                messages = listOf(
                    RuntimeChatMessage(id = "m1", role = "user", content = "Please explain this architecture"),
                    RuntimeChatMessage(id = "m2", role = "assistant", content = "It uses a client app and AetherLink Runtime."),
                ),
                nowMillis = 100L,
            )
            .withGeneratedChatSessionTitle(
                sessionId = "session",
                title = " Runtime architecture plan ",
                nowMillis = 200L,
            )

        assertEquals("Runtime architecture plan", runtimeChatSessions(data).single().title)

        val renamed = data
            .withRenamedChatSession(
                sessionId = "session",
                title = "Manual title",
                nowMillis = 300L,
            )
            .withGeneratedChatSessionTitle(
                sessionId = "session",
                title = "Generated replacement",
                nowMillis = 400L,
            )

        assertEquals("Manual title", runtimeChatSessions(renamed).single().title)
    }

    @Test
    fun runtimeSessionSummariesReplaceRuntimeOwnedCacheAndPreserveLocalSessions() {
        val data = PersistedRuntimeData(
            activeSessionId = "runtime-kept",
            sessions = listOf(
                PersistedChatSession(
                    id = "runtime-old",
                    title = "Old runtime",
                    createdAtMillis = 10L,
                    updatedAtMillis = 10L,
                    runtimeOwned = true,
                ),
                PersistedChatSession(
                    id = "runtime-kept",
                    title = "Manual kept title",
                    createdAtMillis = 20L,
                    updatedAtMillis = 20L,
                    titleManuallyEdited = true,
                    runtimeOwned = true,
                ),
                PersistedChatSession(
                    id = "local-only",
                    title = "Local only",
                    createdAtMillis = 30L,
                    updatedAtMillis = 30L,
                ),
            ),
        )

        val merged = data.withRuntimeChatSessionSummaries(
            sessions = listOf(
                ChatSessionSummaryPayload(
                    sessionId = "runtime-kept",
                    title = "Server title",
                    model = "ollama:llama3.1:8b",
                    lastActivityAt = "2026-06-23T09:02:05Z",
                    messageCount = 2,
                ),
                ChatSessionSummaryPayload(
                    sessionId = "runtime-new",
                    title = "Server new",
                    model = "ollama:qwen3:8b",
                    lastActivityAt = "2026-06-23T09:02:06Z",
                    messageCount = 1,
                    lastEvent = "error",
                    lastErrorCode = "model_not_installed",
                    search = ChatSessionSearchPayload(
                        rank = 2,
                        snippet = "Fresh QR route matched this runtime transcript.",
                        matchedFields = listOf("transcript", "model"),
                    ),
                ),
            ),
            nowMillis = 100L,
        )

        assertEquals("runtime-kept", merged.activeSessionId)
        assertEquals(
            setOf("runtime-kept", "runtime-new", "local-only"),
            merged.sessions.map { it.id }.toSet(),
        )
        assertFalse(merged.sessions.any { it.id == "runtime-old" })
        assertTrue(merged.sessions.first { it.id == "runtime-kept" }.runtimeOwned)
        assertEquals("Manual kept title", merged.sessions.first { it.id == "runtime-kept" }.title)
        assertFalse(merged.sessions.first { it.id == "local-only" }.runtimeOwned)
        val runtimeNew = merged.sessions.first { it.id == "runtime-new" }
        assertEquals("error", runtimeNew.lastEvent)
        assertEquals("model_not_installed", runtimeNew.lastErrorCode)
        assertNull(runtimeNew.lastFinishReason)
        assertEquals(2, runtimeNew.runtimeSearchRank)
        assertEquals("Fresh QR route matched this runtime transcript.", runtimeNew.runtimeSearchSnippet)
        assertEquals(listOf("transcript", "model"), runtimeNew.runtimeSearchMatchedFields)
        val runtimeNewUi = runtimeChatSessions(merged).first { it.id == "runtime-new" }
        assertEquals(2, runtimeNewUi.searchRank)
        assertEquals("Fresh QR route matched this runtime transcript.", runtimeNewUi.searchSnippet)
        assertEquals(listOf("transcript", "model"), runtimeNewUi.searchMatchedFields)
        val savedRedaction = merged.withoutRuntimeOwnedLocalData().sessions.first { it.id == "runtime-new" }
        assertNull(savedRedaction.runtimeSearchRank)
        assertNull(savedRedaction.runtimeSearchSnippet)
        assertTrue(savedRedaction.runtimeSearchMatchedFields.isEmpty())
    }

    @Test
    fun runtimeSessionSummariesClampNegativeMessageCounts() {
        val data = PersistedRuntimeData(
            sessions = listOf(
                PersistedChatSession(
                    id = "runtime-existing",
                    title = "Existing runtime",
                    createdAtMillis = 10L,
                    updatedAtMillis = 10L,
                    runtimeOwned = true,
                    runtimeMessageCount = -9,
                ),
            ),
        )

        val merged = data.withRuntimeChatSessionSummaries(
            sessions = listOf(
                ChatSessionSummaryPayload(
                    sessionId = "runtime-existing",
                    title = "Existing runtime",
                    model = "ollama:llama3.1:8b",
                    lastActivityAt = "2026-06-23T09:02:05Z",
                    messageCount = 0,
                ),
                ChatSessionSummaryPayload(
                    sessionId = "runtime-new",
                    title = "New runtime",
                    model = "ollama:qwen3:8b",
                    lastActivityAt = "2026-06-23T09:02:06Z",
                    messageCount = 1,
                ),
            ),
            nowMillis = 100L,
        )

        assertEquals(0, merged.sessions.first { it.id == "runtime-existing" }.runtimeMessageCount)
        assertEquals(1, merged.sessions.first { it.id == "runtime-new" }.runtimeMessageCount)
        assertEquals(0, runtimeChatSessions(merged).first { it.id == "runtime-existing" }.messageCount)
        assertEquals(1, runtimeChatSessions(merged).first { it.id == "runtime-new" }.messageCount)

        val stalePersistedData = PersistedRuntimeData(
            sessions = listOf(
                PersistedChatSession(
                    id = "runtime-stale",
                    title = "Stale runtime",
                    createdAtMillis = 10L,
                    updatedAtMillis = 20L,
                    runtimeOwned = true,
                    runtimeMessageCount = -7,
                ),
            ),
        )

        assertEquals(0, runtimeChatSessions(stalePersistedData).single().messageCount)
    }

    @Test
    fun runtimeSessionSummariesRestoreArchivedRuntimeSessions() {
        val data = PersistedRuntimeData(
            activeSessionId = "runtime-archived",
            sessions = listOf(
                PersistedChatSession(
                    id = "runtime-archived",
                    title = "Old runtime title",
                    createdAtMillis = 10L,
                    updatedAtMillis = 10L,
                    runtimeOwned = true,
                ),
            ),
        )

        val merged = data.withRuntimeChatSessionSummaries(
            sessions = listOf(
                ChatSessionSummaryPayload(
                    sessionId = "runtime-archived",
                    title = "Server archived title",
                    model = "ollama:llama3.1:8b",
                    lastActivityAt = "2026-06-23T09:02:05Z",
                    messageCount = 2,
                    status = "archived",
                    archivedAt = "2026-06-23T09:05:05Z",
                ),
            ),
            nowMillis = 100L,
        )

        assertNull(merged.activeSessionId)
        assertTrue(runtimeChatSessions(merged).isEmpty())
        assertEquals(listOf("runtime-archived"), archivedRuntimeChatSessions(merged).map { it.id })
        assertEquals(1_782_205_505_000L, archivedRuntimeChatSessions(merged).single().archivedAtMillis)
    }

    @Test
    fun activeRuntimeSummaryClearsPreviousRuntimeArchiveState() {
        val data = PersistedRuntimeData(
            sessions = listOf(
                PersistedChatSession(
                    id = "runtime-session",
                    title = "Archived runtime",
                    createdAtMillis = 10L,
                    updatedAtMillis = 20L,
                    archivedAtMillis = 30L,
                    runtimeOwned = true,
                ),
            ),
        )

        val merged = data.withRuntimeChatSessionSummaries(
            sessions = listOf(
                ChatSessionSummaryPayload(
                    sessionId = "runtime-session",
                    title = "Active runtime",
                    model = "ollama:llama3.1:8b",
                    lastActivityAt = "2026-06-23T09:02:05Z",
                    messageCount = 2,
                    status = "active",
                ),
            ),
            nowMillis = 100L,
        )

        assertEquals(listOf("runtime-session"), runtimeChatSessions(merged).map { it.id })
        assertTrue(archivedRuntimeChatSessions(merged).isEmpty())
        assertNull(merged.sessions.single().archivedAtMillis)
    }

    @Test
    fun runtimeLifecycleAckUpdatesLocalSessionArchiveState() {
        val data = PersistedRuntimeData(
            activeSessionId = "runtime-session",
            sessions = listOf(
                PersistedChatSession(
                    id = "runtime-session",
                    title = "Runtime session",
                    createdAtMillis = 10L,
                    updatedAtMillis = 20L,
                    runtimeOwned = true,
                ),
            ),
        )

        val archived = data.withRuntimeChatSessionLifecycleResult(
            result = ChatSessionLifecyclePayload(
                sessionId = "runtime-session",
                status = "archived",
                archivedAt = "2026-06-23T09:05:05Z",
            ),
            nowMillis = 100L,
        )
        val restored = archived.withRuntimeChatSessionLifecycleResult(
            result = ChatSessionLifecyclePayload(
                sessionId = "runtime-session",
                status = "restored",
                restoredAt = "2026-06-23T09:06:05Z",
            ),
            nowMillis = 200L,
        )

        assertNull(archived.activeSessionId)
        assertTrue(runtimeChatSessions(archived).isEmpty())
        assertEquals(listOf("runtime-session"), archivedRuntimeChatSessions(archived).map { it.id })
        assertEquals(1_782_205_505_000L, archivedRuntimeChatSessions(archived).single().archivedAtMillis)
        assertEquals(listOf("runtime-session"), runtimeChatSessions(restored).map { it.id })
        assertTrue(archivedRuntimeChatSessions(restored).isEmpty())
        assertEquals(1_782_205_565_000L, runtimeChatSessions(restored).single().updatedAtMillis)
    }

    @Test
    fun runtimeOwnedChatMutationsRequireConnectedRuntime() {
        val localSession = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "local",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Local only")),
                nowMillis = 100L,
                runtimeBacked = false,
            )
            .sessions
            .single()
        val runtimeSession = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "runtime",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Runtime saved")),
                nowMillis = 100L,
                runtimeBacked = true,
            )
            .sessions
            .single()

        assertFalse(
            runtimeOwnedChatMutationRequiresConnectedRuntime(
                sessions = listOf(localSession),
                isSessionAuthenticated = false,
                isTransportConnected = false,
            )
        )
        assertTrue(
            runtimeOwnedChatMutationRequiresConnectedRuntime(
                sessions = listOf(runtimeSession),
                isSessionAuthenticated = false,
                isTransportConnected = false,
            )
        )
        assertTrue(
            runtimeOwnedChatMutationRequiresConnectedRuntime(
                sessions = listOf(runtimeSession),
                isSessionAuthenticated = true,
                isTransportConnected = false,
            )
        )
        assertTrue(
            runtimeOwnedChatMutationRequiresConnectedRuntime(
                sessions = listOf(runtimeSession),
                isSessionAuthenticated = false,
                isTransportConnected = true,
            )
        )
        assertFalse(
            runtimeOwnedChatMutationRequiresConnectedRuntime(
                sessions = listOf(localSession, runtimeSession),
                isSessionAuthenticated = true,
                isTransportConnected = true,
            )
        )
    }

    @Test
    fun runtimeDeleteAckSuppressesSessionEvenWhenLocalCacheIsMissing() {
        val data = PersistedRuntimeData()
        val deleted = data.withRuntimeChatSessionLifecycleResult(
            result = ChatSessionLifecyclePayload(
                sessionId = "runtime-deleted",
                status = "deleted",
                deletedAt = "2026-06-23T09:07:05Z",
            ),
            nowMillis = 100L,
        )
        val afterSummarySync = deleted.withRuntimeChatSessionSummaries(
            sessions = listOf(
                ChatSessionSummaryPayload(
                    sessionId = "runtime-deleted",
                    title = "Should not return",
                    model = "ollama:llama3.1:8b",
                    lastActivityAt = "2026-06-23T09:08:05Z",
                    messageCount = 1,
                ),
            ),
            nowMillis = 200L,
        )

        assertTrue(afterSummarySync.sessions.none { it.id == "runtime-deleted" })
        assertEquals(listOf("runtime-deleted"), afterSummarySync.suppressedRuntimeSessions.map { it.sessionId })
        assertEquals(1_782_205_625_000L, afterSummarySync.suppressedRuntimeSessions.single().updatedAtMillis)
    }

    @Test
    fun runtimeLifecycleAckDoesNotMutateLocalOnlySessionWithSameId() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "local-collision",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Keep this local note")),
                nowMillis = 100L,
                runtimeBacked = false,
            )
        val deleteAck = data.withRuntimeChatSessionLifecycleResult(
            result = ChatSessionLifecyclePayload(
                sessionId = "local-collision",
                status = "deleted",
                deletedAt = "2026-06-23T09:07:05Z",
            ),
            nowMillis = 200L,
        )
        val archiveAck = data.withRuntimeChatSessionLifecycleResult(
            result = ChatSessionLifecyclePayload(
                sessionId = "local-collision",
                status = "archived",
                archivedAt = "2026-06-23T09:08:05Z",
            ),
            nowMillis = 300L,
        )
        val restoreAck = data
            .withArchivedChatSession(sessionId = "local-collision", nowMillis = 400L)
            .withRuntimeChatSessionLifecycleResult(
                result = ChatSessionLifecyclePayload(
                    sessionId = "local-collision",
                    status = "restored",
                    restoredAt = "2026-06-23T09:09:05Z",
                ),
                nowMillis = 500L,
            )

        assertEquals(listOf("local-collision"), runtimeChatSessions(deleteAck).map { it.id })
        assertEquals("Keep this local note", activeSessionMessages(deleteAck).single().content)
        assertTrue(deleteAck.suppressedRuntimeSessions.isEmpty())

        assertEquals(listOf("local-collision"), runtimeChatSessions(archiveAck).map { it.id })
        assertTrue(archivedRuntimeChatSessions(archiveAck).isEmpty())

        assertTrue(runtimeChatSessions(restoreAck).isEmpty())
        assertEquals(listOf("local-collision"), archivedRuntimeChatSessions(restoreAck).map { it.id })
        assertEquals(400L, archivedRuntimeChatSessions(restoreAck).single().archivedAtMillis)
    }

    @Test
    fun runtimeSessionSummariesClearActiveSessionWhenRuntimeOwnedActiveSessionDisappears() {
        val data = PersistedRuntimeData(
            activeSessionId = "runtime-old",
            sessions = listOf(
                PersistedChatSession(
                    id = "runtime-old",
                    title = "Old runtime",
                    createdAtMillis = 10L,
                    updatedAtMillis = 10L,
                    runtimeOwned = true,
                ),
            ),
        )

        val merged = data.withRuntimeChatSessionSummaries(
            sessions = emptyList(),
            nowMillis = 100L,
        )

        assertNull(merged.activeSessionId)
        assertTrue(runtimeChatSessions(merged).isEmpty())
    }

    @Test
    fun runtimeMessagesDoNotResurrectSessionMissingFromLatestRuntimeSummary() {
        val data = PersistedRuntimeData(
            activeSessionId = "runtime-old",
            sessions = listOf(
                PersistedChatSession(
                    id = "runtime-old",
                    title = "Old runtime",
                    createdAtMillis = 10L,
                    updatedAtMillis = 10L,
                    runtimeOwned = true,
                    runtimeMessageCount = 1,
                ),
            ),
        )

        val afterSummarySync = data.withRuntimeChatSessionSummaries(
            sessions = emptyList(),
            nowMillis = 100L,
        )
        val afterLateMessageSync = afterSummarySync.withRuntimeChatMessages(
            sessionId = "runtime-old",
            messages = listOf(ChatStoredMessagePayload(role = "user", content = "Stale runtime prompt")),
            nowMillis = 200L,
        )

        assertNull(afterLateMessageSync.activeSessionId)
        assertTrue(afterLateMessageSync.sessions.none { it.id == "runtime-old" })
        assertTrue(runtimeChatSessions(afterLateMessageSync).isEmpty())
        assertTrue(activeSessionMessages(afterLateMessageSync).isEmpty())
    }

    @Test
    fun runtimeMessagesReplaceSessionTranscriptAndPreserveReasoningWithStableIds() {
        val data = PersistedRuntimeData()
            .withRuntimeChatSessionSummaries(
                sessions = listOf(
                    ChatSessionSummaryPayload(
                        sessionId = "runtime-session",
                        title = "Runtime title",
                        model = "ollama:llama3.1:8b",
                        lastActivityAt = "2026-06-23T09:02:05Z",
                        messageCount = 2,
                    ),
                ),
                nowMillis = 100L,
            )
            .withActiveSession("runtime-session")
        val runtimeMessages = listOf(
            ChatStoredMessagePayload(
                role = "user",
                content = "Explain QR pairing.",
                attachments = listOf(
                    ChatStoredAttachmentPayload(
                        type = "document",
                        mimeType = "text/plain",
                        name = "pairing-notes.txt",
                        text = "QR route notes",
                    ),
                ),
                createdAt = "2026-06-23T09:02:00Z",
            ),
            ChatStoredMessagePayload(
                role = "assistant",
                content = "Scan the runtime QR.",
                reasoning = "Checking route material.",
                createdAt = "2026-06-23T09:02:05Z",
            ),
        )

        val firstMerge = data.withRuntimeChatMessages(
            sessionId = "runtime-session",
            messages = runtimeMessages,
            nowMillis = 200L,
        )
        val secondMerge = firstMerge.withRuntimeChatMessages(
            sessionId = "runtime-session",
            messages = runtimeMessages,
            nowMillis = 300L,
        )

        val messages = activeSessionMessages(firstMerge)
        assertEquals(listOf("user", "assistant"), messages.map { it.role })
        assertEquals("Explain QR pairing.", messages.first().content)
        assertEquals(1, messages.first().attachments.size)
        assertEquals("pairing-notes.txt", messages.first().attachments.single().name)
        assertEquals("text/plain", messages.first().attachments.single().mimeType)
        assertEquals("QR route notes", messages.first().attachments.single().text)
        assertEquals("Scan the runtime QR.", messages.last().content)
        assertEquals("Checking route material.", messages.last().reasoning)
        assertEquals(
            messages.map { it.id },
            activeSessionMessages(secondMerge).map { it.id },
        )
    }

    @Test
    fun runtimeMessagesForOneSessionDoNotChangeActiveLocalSessionMessages() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "local-active",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Local active")),
                nowMillis = 100L,
            )
            .withRuntimeChatSessionSummaries(
                sessions = listOf(
                    ChatSessionSummaryPayload(
                        sessionId = "runtime-other",
                        title = "Runtime other",
                        model = "ollama:llama3.1:8b",
                        lastActivityAt = "2026-06-23T09:02:05Z",
                        messageCount = 1,
                    ),
                ),
                nowMillis = 200L,
            )

        val merged = data.withRuntimeChatMessages(
            sessionId = "runtime-other",
            messages = listOf(ChatStoredMessagePayload(role = "user", content = "Server chat")),
            nowMillis = 300L,
        )

        assertEquals("local-active", merged.activeSessionId)
        assertEquals("Local active", activeSessionMessages(merged).single().content)
        assertEquals("Server chat", merged.sessions.first { it.id == "runtime-other" }.messages.single().content)
    }

    @Test
    fun activeRuntimeSessionIdRequiresActiveRuntimeOwnedUnarchivedSession() {
        val runtimeActive = PersistedRuntimeData()
            .withRuntimeChatSessionSummaries(
                sessions = listOf(
                    ChatSessionSummaryPayload(
                        sessionId = "runtime-active",
                        title = "Runtime active",
                        model = "ollama:llama3.1:8b",
                        lastActivityAt = "2026-06-23T09:02:05Z",
                        messageCount = 2,
                    ),
                ),
                nowMillis = 100L,
            )
            .withActiveSession("runtime-active")

        assertEquals("runtime-active", activeRuntimeSessionId(runtimeActive))

        val localActive = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "local-active",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Local")),
                nowMillis = 200L,
            )

        assertNull(activeRuntimeSessionId(localActive))

        val archivedRuntimeActive = runtimeActive.withRuntimeChatSessionSummaries(
            sessions = listOf(
                ChatSessionSummaryPayload(
                    sessionId = "runtime-active",
                    title = "Runtime active",
                    model = "ollama:llama3.1:8b",
                    lastActivityAt = "2026-06-23T09:02:05Z",
                    messageCount = 2,
                    status = "archived",
                    archivedAt = "2026-06-23T09:05:05Z",
                ),
            ),
            nowMillis = 300L,
        )

        assertNull(activeRuntimeSessionId(archivedRuntimeActive))
        assertNull(activeRuntimeSessionId(PersistedRuntimeData()))
    }

    @Test
    fun permanentlyDeletedRuntimeSessionDoesNotReturnFromRuntimeSync() {
        val data = PersistedRuntimeData()
            .withRuntimeChatSessionSummaries(
                sessions = listOf(
                    ChatSessionSummaryPayload(
                        sessionId = "runtime-deleted",
                        title = "Runtime deleted",
                        model = "ollama:llama3.1:8b",
                        lastActivityAt = "2026-06-23T09:02:05Z",
                        messageCount = 1,
                    ),
                ),
                nowMillis = 100L,
            )
            .withArchivedChatSession(
                sessionId = "runtime-deleted",
                nowMillis = 200L,
            )
            .withoutChatSession(
                sessionId = "runtime-deleted",
                nowMillis = 300L,
            )

        val afterSummarySync = data.withRuntimeChatSessionSummaries(
            sessions = listOf(
                ChatSessionSummaryPayload(
                    sessionId = "runtime-deleted",
                    title = "Runtime deleted again",
                    model = "ollama:llama3.1:8b",
                    lastActivityAt = "2026-06-23T09:03:05Z",
                    messageCount = 2,
                ),
            ),
            nowMillis = 400L,
        )
        val afterMessageSync = afterSummarySync.withRuntimeChatMessages(
            sessionId = "runtime-deleted",
            messages = listOf(ChatStoredMessagePayload(role = "user", content = "Do not restore")),
            nowMillis = 500L,
        )

        assertTrue(afterMessageSync.sessions.none { it.id == "runtime-deleted" })
        assertEquals(listOf("runtime-deleted"), afterMessageSync.suppressedRuntimeSessions.map { it.sessionId })
        assertEquals("deleted", afterMessageSync.suppressedRuntimeSessions.single().reason)
    }

    @Test
    fun permanentlyDeletingArchivedRuntimeSessionsAddsSuppressionsButKeepsActiveLocalChats() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "local-active",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Local active")),
                nowMillis = 100L,
            )
            .withRuntimeChatSessionSummaries(
                sessions = listOf(
                    ChatSessionSummaryPayload(
                        sessionId = "runtime-archived",
                        title = "Runtime archived",
                        model = "ollama:llama3.1:8b",
                        lastActivityAt = "2026-06-23T09:02:05Z",
                        messageCount = 1,
                    ),
                ),
                nowMillis = 150L,
            )
            .withArchivedChatSession(
                sessionId = "runtime-archived",
                nowMillis = 200L,
            )
            .withoutArchivedChatSessions(nowMillis = 300L)
            .withRuntimeChatSessionSummaries(
                sessions = listOf(
                    ChatSessionSummaryPayload(
                        sessionId = "runtime-archived",
                        title = "Runtime archived returns",
                        model = "ollama:llama3.1:8b",
                        lastActivityAt = "2026-06-23T09:03:05Z",
                        messageCount = 1,
                    ),
                ),
                nowMillis = 400L,
            )

        assertEquals(listOf("local-active"), runtimeChatSessions(data).map { it.id })
        assertTrue(data.sessions.none { it.id == "runtime-archived" })
        assertEquals(listOf("runtime-archived"), data.suppressedRuntimeSessions.map { it.sessionId })
    }

    @Test
    fun deleteActiveChatSessionClearsActiveMessagesAndKeepsOtherSessions() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "older",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Older question")),
                nowMillis = 100L,
            )
            .withPersistedMessages(
                sessionId = "active",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Active question")),
                nowMillis = 200L,
            )
            .withoutChatSession("active")

        assertNull(data.activeSessionId)
        assertEquals(listOf("older"), runtimeChatSessions(data).map { it.id })
        assertTrue(activeSessionMessages(data).isEmpty())
    }

    @Test
    fun permanentDeleteRequiresArchivedChatSession() {
        val activeData = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "active",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Active question")),
                nowMillis = 100L,
                runtimeBacked = true,
            )
            .withoutArchivedChatSession("active", nowMillis = 200L)

        assertEquals(listOf("active"), runtimeChatSessions(activeData).map { it.id })
        assertEquals("Active question", activeSessionMessages(activeData).single().content)

        val archivedData = activeData
            .withArchivedChatSession(sessionId = "active", nowMillis = 300L)
            .withoutArchivedChatSession("active", nowMillis = 400L)

        assertTrue(archivedData.sessions.none { it.id == "active" })
        assertEquals(listOf("active"), archivedData.suppressedRuntimeSessions.map { it.sessionId })
    }

    @Test
    fun deleteInactiveChatSessionPreservesActiveSessionAndMessages() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "inactive",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Inactive question")),
                nowMillis = 100L,
            )
            .withPersistedMessages(
                sessionId = "active",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Active question")),
                nowMillis = 200L,
            )
            .withoutChatSession("inactive")

        assertEquals("active", data.activeSessionId)
        assertEquals(listOf("active"), runtimeChatSessions(data).map { it.id })
        assertEquals("Active question", activeSessionMessages(data).single().content)
    }

    @Test
    fun archivedChatSessionIsExcludedFromPreviousChatsAndClearsActiveSession() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "older",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Older question")),
                nowMillis = 100L,
            )
            .withPersistedMessages(
                sessionId = "active",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Active question")),
                nowMillis = 200L,
            )
            .withArchivedChatSession(
                sessionId = "active",
                nowMillis = 300L,
            )

        assertNull(data.activeSessionId)
        assertEquals(listOf("older"), runtimeChatSessions(data).map { it.id })
        assertEquals(listOf("active"), archivedRuntimeChatSessions(data).map { it.id })
        assertEquals(300L, archivedRuntimeChatSessions(data).single().archivedAtMillis)
        assertTrue(activeSessionMessages(data).isEmpty())
    }

    @Test
    fun archiveAllChatSessionsRetainsSessionsAsArchivedAndKeepsMemoryCandidatesEmpty() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "first",
                messages = listOf(RuntimeChatMessage(role = "user", content = "First question")),
                nowMillis = 100L,
            )
            .withPersistedMessages(
                sessionId = "second",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Second question")),
                nowMillis = 200L,
            )
            .withArchivedChatSessions(nowMillis = 300L)

        assertNull(data.activeSessionId)
        assertTrue(runtimeChatSessions(data).isEmpty())
        assertEquals(listOf("first", "second"), archivedRuntimeChatSessions(data).map { it.id }.sorted())
        assertTrue(memoryCandidateChatSessions(data).isEmpty())
        assertTrue(reflectionCandidateChatSessions(data).isEmpty())
        assertTrue(researchCandidateChatSessions(data).isEmpty())
    }

    @Test
    fun permanentDeleteArchivedChatSessionsDoesNotDeleteActivePreviousChats() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "active",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Active question")),
                nowMillis = 100L,
            )
            .withPersistedMessages(
                sessionId = "archived",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Archived question")),
                nowMillis = 200L,
            )
            .withArchivedChatSession(
                sessionId = "archived",
                nowMillis = 300L,
            )
            .withoutArchivedChatSessions()

        assertEquals(listOf("active"), runtimeChatSessions(data).map { it.id })
        assertTrue(archivedRuntimeChatSessions(data).isEmpty())
        assertNull(data.activeSessionId)
    }

    @Test
    fun permanentDeleteArchivedChatSessionsSuppressesOnlyRuntimeOwnedArchivedSessions() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "runtime-active",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Active runtime question")),
                nowMillis = 100L,
                runtimeBacked = true,
            )
            .withPersistedMessages(
                sessionId = "runtime-archived",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Archived runtime question")),
                nowMillis = 200L,
                runtimeBacked = true,
            )
            .withPersistedMessages(
                sessionId = "local-archived",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Archived local note")),
                nowMillis = 300L,
                runtimeBacked = false,
            )
            .withArchivedChatSession(
                sessionId = "runtime-archived",
                nowMillis = 400L,
            )
            .withArchivedChatSession(
                sessionId = "local-archived",
                nowMillis = 450L,
            )
            .withoutArchivedChatSessions(nowMillis = 500L)

        assertEquals(listOf("runtime-active"), runtimeChatSessions(data).map { it.id })
        assertTrue(archivedRuntimeChatSessions(data).isEmpty())
        assertEquals(listOf("runtime-archived"), data.suppressedRuntimeSessions.map { it.sessionId })
        assertEquals(500L, data.suppressedRuntimeSessions.single().updatedAtMillis)
        assertTrue(data.suppressedRuntimeSessions.none { it.sessionId == "local-archived" })
    }

    @Test
    fun unarchivedChatSessionReturnsToPreviousChatsWithoutBecomingActive() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "session",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Saved chat")),
                nowMillis = 100L,
            )
            .withArchivedChatSession(
                sessionId = "session",
                nowMillis = 200L,
            )
            .withUnarchivedChatSession(
                sessionId = "session",
                nowMillis = 300L,
            )

        assertNull(data.activeSessionId)
        assertEquals(listOf("session"), runtimeChatSessions(data).map { it.id })
        assertTrue(archivedRuntimeChatSessions(data).isEmpty())
        assertNull(runtimeChatSessions(data).single().archivedAtMillis)
        assertEquals(300L, runtimeChatSessions(data).single().updatedAtMillis)
    }

    @Test
    fun archivedChatSessionCannotBeSelectedAsActiveSession() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "session",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Saved chat")),
                nowMillis = 100L,
            )
            .withArchivedChatSession(
                sessionId = "session",
                nowMillis = 200L,
            )
            .withActiveSession("session")

        assertNull(data.activeSessionId)
        assertTrue(activeSessionMessages(data).isEmpty())
    }

    @Test
    fun candidateChatSessionHelpersExcludeArchivedSessions() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "active-candidate",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Candidate")),
                nowMillis = 100L,
            )
            .withPersistedMessages(
                sessionId = "archived-candidate",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Archived")),
                nowMillis = 200L,
            )
            .withArchivedChatSession(
                sessionId = "archived-candidate",
                nowMillis = 300L,
            )

        assertEquals(listOf("active-candidate"), memoryCandidateChatSessions(data).map { it.id })
        assertEquals(listOf("active-candidate"), reflectionCandidateChatSessions(data).map { it.id })
        assertEquals(listOf("active-candidate"), researchCandidateChatSessions(data).map { it.id })
    }

    @Test
    fun clearChatSessionsRemovesOnlySessionsAndActiveMessages() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "session",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Saved chat")),
                nowMillis = 100L,
            )
            .withRuntimeMemoryEntry(
                entry = MemoryEntryPayload(
                    id = "memory-1",
                    content = "Keep memory",
                    enabled = true,
                    createdAt = "2026-06-25T00:00:00Z",
                    updatedAt = "2026-06-25T00:00:00Z",
                ),
                nowMillis = 200L,
            )
            .withoutChatSessions()

        assertNull(data.activeSessionId)
        assertTrue(runtimeChatSessions(data).isEmpty())
        assertTrue(activeSessionMessages(data).isEmpty())
        assertEquals("Keep memory", data.memoryEntries.single().content)
    }

    @Test
    fun persistedRuntimeDataDefaultsToEnglishAppLanguage() {
        val data = PersistedRuntimeData()

        assertEquals(RuntimeAppLanguage.English.languageTag, data.appLanguageTag)
        assertEquals(RuntimeAppLanguage.English.languageTag, data.sanitized().appLanguageTag)
        assertEquals(APP_LANGUAGE_SOURCE_DEFAULT, data.sanitized().appLanguageSource)
    }

    @Test
    fun persistedRuntimeDataDefaultsToSystemAppearance() {
        val data = PersistedRuntimeData()

        assertEquals(RuntimeAppTheme.System.storageValue, data.appTheme)
        assertEquals(RuntimeAppTheme.System.storageValue, data.sanitized().appTheme)
    }

    @Test
    fun appLanguageTagHelperNormalizesSupportedAndInvalidTags() {
        val korean = PersistedRuntimeData().withAppLanguageTag(" KO ")
        val simplifiedChinese = korean.withAppLanguageTag("zh-cn")
        val simplifiedChineseHans = simplifiedChinese.withAppLanguageTag("zh-Hans")
        val simplifiedChineseAndroidQualifier = simplifiedChineseHans.withAppLanguageTag("zh-rCN")
        val invalid = simplifiedChineseAndroidQualifier.withAppLanguageTag("unknown")
        val legacyBlankLanguage = invalid.withAppLanguageTag("")

        assertEquals(RuntimeAppLanguage.Korean.languageTag, korean.appLanguageTag)
        assertEquals(RuntimeAppLanguage.SimplifiedChinese.languageTag, simplifiedChinese.appLanguageTag)
        assertEquals(RuntimeAppLanguage.SimplifiedChinese.languageTag, simplifiedChineseHans.appLanguageTag)
        assertEquals(RuntimeAppLanguage.SimplifiedChinese.languageTag, simplifiedChineseAndroidQualifier.appLanguageTag)
        assertEquals(RuntimeAppLanguage.English.languageTag, invalid.appLanguageTag)
        assertEquals(RuntimeAppLanguage.English.languageTag, legacyBlankLanguage.appLanguageTag)
        assertEquals(RuntimeAppLanguage.Korean.languageTag, RuntimeAppLanguage.normalizeLanguageTag("ko-KR"))
        assertEquals(RuntimeAppLanguage.Japanese.languageTag, RuntimeAppLanguage.normalizeLanguageTag("ja-JP"))
        assertEquals(RuntimeAppLanguage.French.languageTag, RuntimeAppLanguage.normalizeLanguageTag("fr-FR"))
        assertEquals(RuntimeAppLanguage.English.languageTag, RuntimeAppLanguage.normalizeLanguageTag("en-US"))
        assertEquals(APP_LANGUAGE_SOURCE_IN_APP, korean.appLanguageSource)
    }

    @Test
    fun systemAppLanguageHelperDoesNotOverrideInAppLanguageSelection() {
        val systemLanguage = PersistedRuntimeData().withSystemAppLanguageTag("ko-KR")
        val inAppLanguage = systemLanguage.withAppLanguageTag("fr-FR")
        val followSystemLanguage = inAppLanguage.withFollowSystemAppLanguageTag("ja-JP")
        val ignoredSystemUpdate = inAppLanguage.withSystemAppLanguageTag("ja-JP")
        val unsupportedSystemUpdate = PersistedRuntimeData().withSystemAppLanguageTag("de-DE")
        val unsupportedFollowSystem = inAppLanguage.withFollowSystemAppLanguageTag("de-DE")

        assertEquals(RuntimeAppLanguage.Korean.languageTag, systemLanguage.appLanguageTag)
        assertEquals(APP_LANGUAGE_SOURCE_SYSTEM, systemLanguage.appLanguageSource)
        assertEquals(RuntimeAppLanguage.French.languageTag, inAppLanguage.appLanguageTag)
        assertEquals(APP_LANGUAGE_SOURCE_IN_APP, inAppLanguage.appLanguageSource)
        assertEquals(RuntimeAppLanguage.Japanese.languageTag, followSystemLanguage.appLanguageTag)
        assertEquals(APP_LANGUAGE_SOURCE_SYSTEM, followSystemLanguage.appLanguageSource)
        assertEquals(RuntimeAppLanguage.French.languageTag, ignoredSystemUpdate.appLanguageTag)
        assertEquals(APP_LANGUAGE_SOURCE_IN_APP, ignoredSystemUpdate.appLanguageSource)
        assertEquals(RuntimeAppLanguage.English.languageTag, unsupportedSystemUpdate.appLanguageTag)
        assertEquals(APP_LANGUAGE_SOURCE_DEFAULT, unsupportedSystemUpdate.appLanguageSource)
        assertEquals(RuntimeAppLanguage.English.languageTag, unsupportedFollowSystem.appLanguageTag)
        assertEquals(APP_LANGUAGE_SOURCE_DEFAULT, unsupportedFollowSystem.appLanguageSource)
    }

    @Test
    fun attachmentOnlyPromptUsesSelectedAppLanguageAndEnglishFallback() {
        val attachments = listOf(
            RuntimePendingAttachment(
                type = "document",
                name = "route-notes.txt",
                mimeType = "text/plain",
                sizeBytes = 12L,
                dataBase64 = "cm91dGUgbm90ZXM=",
            ),
            RuntimePendingAttachment(
                type = "image",
                name = "pairing-qr.png",
                mimeType = "image/png",
                sizeBytes = 24L,
                dataBase64 = "cGFpcmluZy1xcg==",
            ),
        )

        val expectedBullets = "\n- route-notes.txt\n- pairing-qr.png"

        assertEquals(
            "첨부한 입력을 분석하세요:",
            testAttachmentOnlyPromptHeader(RuntimeAppLanguage.Korean.languageTag),
        )
        assertEquals(
            "添付された入力を分析してください:",
            testAttachmentOnlyPromptHeader(RuntimeAppLanguage.Japanese.languageTag),
        )
        assertEquals(
            "请分析附加输入：",
            testAttachmentOnlyPromptHeader(RuntimeAppLanguage.SimplifiedChinese.languageTag),
        )
        assertEquals(
            "Analysez les éléments joints :",
            testAttachmentOnlyPromptHeader(RuntimeAppLanguage.French.languageTag),
        )
        assertEquals(
            "Analyze attached input:",
            testAttachmentOnlyPromptHeader(""),
        )

        assertEquals(
            "Analyze attached input:$expectedBullets",
            attachmentOnlyPrompt(
                attachments = attachments,
                promptHeader = testAttachmentOnlyPromptHeader(RuntimeAppLanguage.English.languageTag),
            ),
        )
        assertEquals(
            "첨부한 입력을 분석하세요:$expectedBullets",
            attachmentOnlyPrompt(
                attachments = attachments,
                promptHeader = testAttachmentOnlyPromptHeader(RuntimeAppLanguage.Korean.languageTag),
            ),
        )
        assertEquals(
            "添付された入力を分析してください:$expectedBullets",
            attachmentOnlyPrompt(
                attachments = attachments,
                promptHeader = testAttachmentOnlyPromptHeader(RuntimeAppLanguage.Japanese.languageTag),
            ),
        )
        assertEquals(
            "请分析附加输入：$expectedBullets",
            attachmentOnlyPrompt(
                attachments = attachments,
                promptHeader = testAttachmentOnlyPromptHeader(RuntimeAppLanguage.SimplifiedChinese.languageTag),
            ),
        )
        assertEquals(
            "Analysez les éléments joints :$expectedBullets",
            attachmentOnlyPrompt(
                attachments = attachments,
                promptHeader = testAttachmentOnlyPromptHeader(RuntimeAppLanguage.French.languageTag),
            ),
        )
        assertEquals(
            "Analyze attached input:$expectedBullets",
            attachmentOnlyPrompt(
                attachments = attachments,
                promptHeader = testAttachmentOnlyPromptHeader(""),
            ),
        )
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun attachmentOnlySendUsesSelectedLanguagePromptInChatSendPayload() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
            )
            val attachment = textAttachment()
            fixture.viewModel.replaceStateForTest {
                it.copy(
                    selectedLanguageTag = RuntimeAppLanguage.Korean.languageTag,
                    chatInput = "   ",
                    pendingAttachments = listOf(attachment),
                )
            }

            fixture.viewModel.sendChatMessage()
            advanceUntilIdle()

            val payload = fixture.channel.lastChatSendPayload()
            assertEquals(RuntimeAppLanguage.Korean.languageTag, payload.locale)
            assertEquals("ollama:llama3.1:8b", payload.model)
            assertEquals(
                "첨부한 입력을 분석하세요:\n- pairing-notes.txt",
                payload.messages.last().content,
            )
            assertEquals("user", payload.messages.last().role)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun sendChatMessageClearsPersistedComposerDraft() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
            )
            fixture.viewModel.updateChatInput("Explain persisted composer draft cleanup")
            advanceUntilIdle()
            assertEquals("Explain persisted composer draft cleanup", fixture.localStore.data.composerDraft)

            fixture.viewModel.sendChatMessage()
            advanceUntilIdle()

            assertEquals("", fixture.viewModel.state.value.chatInput)
            assertEquals("", fixture.localStore.data.composerDraft)
            assertEquals(1, fixture.channel.sentEnvelopes.count { it.type == MessageType.ChatSend })
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun streamingRuntimeOwnedChatRendersInMemoryButRedactsDeviceStorage() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                redactRuntimeOwnedLocalDataOnSave = true,
            )
            fixture.viewModel.replaceStateForTest {
                it.copy(chatInput = "Explain runtime-owned chat storage")
            }

            fixture.viewModel.sendChatMessage()
            advanceUntilIdle()

            val sendEnvelope = fixture.channel.sentEnvelopes.last { it.type == MessageType.ChatSend }
            val sessionId = requireNotNull(fixture.viewModel.state.value.activeChatSessionId)
            val savedAfterSend = fixture.localStore.data.sessions.single { it.id == sessionId }
            assertTrue(savedAfterSend.runtimeOwned)
            assertTrue(savedAfterSend.messages.isEmpty())
            assertEquals(2, savedAfterSend.runtimeMessageCount)
            assertEquals(
                listOf("Explain runtime-owned chat storage", ""),
                fixture.viewModel.state.value.messages.map { it.content },
            )

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.ChatDelta,
                    serializer = ChatDeltaPayload.serializer(),
                    payload = ChatDeltaPayload(
                        delta = "Runtime-owned answer",
                        reasoningDelta = "Server-side reasoning",
                    ),
                    requestId = sendEnvelope.requestId,
                ),
            )
            advanceUntilIdle()

            val streamedAssistant = fixture.viewModel.state.value.messages.last()
            assertEquals("Runtime-owned answer", streamedAssistant.content)
            assertEquals("Server-side reasoning", streamedAssistant.reasoning)
            val savedAfterDelta = fixture.localStore.data.sessions.single { it.id == sessionId }
            assertTrue(savedAfterDelta.runtimeOwned)
            assertTrue(savedAfterDelta.messages.isEmpty())
            assertEquals(2, savedAfterDelta.runtimeMessageCount)

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.ChatDone,
                    serializer = ChatDonePayload.serializer(),
                    payload = ChatDonePayload(),
                    requestId = sendEnvelope.requestId,
                ),
            )
            advanceUntilIdle()

            assertFalse(fixture.viewModel.state.value.isStreaming)
            assertEquals(
                listOf("Explain runtime-owned chat storage", "Runtime-owned answer"),
                fixture.viewModel.state.value.messages.map { it.content },
            )
            val savedAfterDone = fixture.localStore.data.sessions.single { it.id == sessionId }
            assertTrue(savedAfterDone.runtimeOwned)
            assertTrue(savedAfterDone.messages.isEmpty())
            assertEquals(2, savedAfterDone.runtimeMessageCount)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun chatDeltaRejectsUnknownMetadataBeforeMessagePublication() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
            )
            fixture.viewModel.replaceStateForTest {
                it.copy(chatInput = "Explain stream metadata boundaries")
            }

            fixture.viewModel.sendChatMessage()
            advanceUntilIdle()

            val sendEnvelope = fixture.channel.sentEnvelopes.last { it.type == MessageType.ChatSend }
            val sessionId = requireNotNull(fixture.viewModel.state.value.activeChatSessionId)
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.ChatDelta,
                    requestId = sendEnvelope.requestId,
                    payload = buildJsonObject {
                        put("delta", "Leaky stream answer")
                        put("backend_url", "http://127.0.0.1:11434")
                    },
                ),
            )
            advanceUntilIdle()

            val rejectedState = fixture.viewModel.state.value
            assertEquals("invalid_payload", rejectedState.error?.code)
            assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("chat.delta"))
            assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("backend_url"))
            assertTrue(rejectedState.isStreaming)
            assertEquals(sendEnvelope.requestId, rejectedState.activeRequestId)
            assertEquals(
                listOf("Explain stream metadata boundaries", ""),
                rejectedState.messages.map { it.content },
            )
            assertFalse(json.encodeToString(fixture.localStore.data).contains("Leaky stream answer"))
            assertFalse(json.encodeToString(fixture.localStore.data).contains("127.0.0.1:11434"))

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.ChatDelta,
                    serializer = ChatDeltaPayload.serializer(),
                    payload = ChatDeltaPayload(
                        delta = "Canonical stream answer",
                        reasoningDelta = "Canonical runtime reasoning",
                    ),
                    requestId = sendEnvelope.requestId,
                ),
            )
            advanceUntilIdle()

            val acceptedState = fixture.viewModel.state.value
            assertNull(acceptedState.error)
            assertTrue(acceptedState.isStreaming)
            assertEquals(sendEnvelope.requestId, acceptedState.activeRequestId)
            val acceptedAssistant = acceptedState.messages.last()
            assertEquals("Canonical stream answer", acceptedAssistant.content)
            assertEquals("Canonical runtime reasoning", acceptedAssistant.reasoning)
            assertEquals(
                "Canonical stream answer",
                fixture.localStore.data.sessions.single { it.id == sessionId }.messages.last().content,
            )
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun chatDoneRejectsUnknownMetadataBeforeCompletionSideEffects() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
            )
            fixture.viewModel.replaceStateForTest {
                it.copy(chatInput = "Explain done metadata boundaries")
            }

            fixture.viewModel.sendChatMessage()
            advanceUntilIdle()

            val sendEnvelope = fixture.channel.sentEnvelopes.last { it.type == MessageType.ChatSend }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.ChatDelta,
                    serializer = ChatDeltaPayload.serializer(),
                    payload = ChatDeltaPayload(delta = "Canonical answer before done"),
                    requestId = sendEnvelope.requestId,
                ),
            )
            advanceUntilIdle()

            val titleRequestCountBeforeRejectedDone = fixture.channel.sentEnvelopes.count {
                it.type == MessageType.ChatTitleRequest
            }
            val historyRequestCountBeforeRejectedDone = fixture.channel.sentEnvelopes.count {
                it.type == MessageType.ChatSessionsList
            }
            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.ChatDone,
                    requestId = sendEnvelope.requestId,
                    payload = buildJsonObject {
                        put("finish_reason", "stop")
                        put(
                            "usage",
                            buildJsonObject {
                                put("input_tokens", 4)
                                put("output_tokens", 6)
                                put("workspace_id", "workspace-canary")
                            },
                        )
                    },
                ),
            )
            advanceUntilIdle()

            val rejectedState = fixture.viewModel.state.value
            assertEquals("invalid_payload", rejectedState.error?.code)
            assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("chat.done"))
            assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("usage.workspace_id"))
            assertTrue(rejectedState.isStreaming)
            assertEquals(sendEnvelope.requestId, rejectedState.activeRequestId)
            assertEquals("Canonical answer before done", rejectedState.messages.last().content)
            assertEquals(
                titleRequestCountBeforeRejectedDone,
                fixture.channel.sentEnvelopes.count { it.type == MessageType.ChatTitleRequest },
            )
            assertEquals(
                historyRequestCountBeforeRejectedDone,
                fixture.channel.sentEnvelopes.count { it.type == MessageType.ChatSessionsList },
            )
            assertFalse(json.encodeToString(fixture.localStore.data).contains("workspace-canary"))

            fixture.channel.enqueue(
                envelope(
                    type = MessageType.ChatDone,
                    serializer = ChatDonePayload.serializer(),
                    payload = ChatDonePayload(),
                    requestId = sendEnvelope.requestId,
                ),
            )
            advanceUntilIdle()

            val acceptedState = fixture.viewModel.state.value
            assertNull(acceptedState.error)
            assertFalse(acceptedState.isStreaming)
            assertNull(acceptedState.activeRequestId)
            assertEquals("Canonical answer before done", acceptedState.messages.last().content)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun chatCancelAckRejectsUnknownMetadataBeforeStreamingClear() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
            )
            fixture.viewModel.replaceStateForTest {
                it.copy(chatInput = "Explain cancel acknowledgement metadata boundaries")
            }

            fixture.viewModel.sendChatMessage()
            advanceUntilIdle()

            val sendEnvelope = fixture.channel.sentEnvelopes.last { it.type == MessageType.ChatSend }
            val sessionId = requireNotNull(fixture.viewModel.state.value.activeChatSessionId)
            fixture.viewModel.cancelGeneration()
            advanceUntilIdle()
            val cancelEnvelope = fixture.channel.sentEnvelopes.last { it.type == MessageType.ChatCancel }

            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.ChatCancel,
                    requestId = cancelEnvelope.requestId,
                    payload = buildJsonObject {
                        put("target_request_id", sendEnvelope.requestId)
                        put("cancelled", true)
                        put("backend_url", "http://127.0.0.1:11434")
                    },
                ),
            )
            advanceUntilIdle()

            val rejectedState = fixture.viewModel.state.value
            assertEquals("invalid_payload", rejectedState.error?.code)
            assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("chat.cancel"))
            assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("backend_url"))
            assertTrue(rejectedState.isStreaming)
            assertEquals(sendEnvelope.requestId, rejectedState.activeRequestId)
            assertEquals(
                listOf("Explain cancel acknowledgement metadata boundaries", ""),
                rejectedState.messages.map { it.content },
            )
            assertFalse(json.encodeToString(fixture.localStore.data).contains("127.0.0.1:11434"))

            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.ChatCancel,
                    requestId = cancelEnvelope.requestId,
                    payload = buildJsonObject {
                        put("target_request_id", sendEnvelope.requestId)
                        put("cancelled", true)
                    },
                ),
            )
            advanceUntilIdle()

            val acceptedState = fixture.viewModel.state.value
            assertNull(acceptedState.error)
            assertFalse(acceptedState.isStreaming)
            assertNull(acceptedState.activeRequestId)
            assertEquals(
                listOf("Explain cancel acknowledgement metadata boundaries"),
                acceptedState.messages.map { it.content },
            )
            assertEquals(
                listOf("Explain cancel acknowledgement metadata boundaries"),
                fixture.localStore.data.sessions.single { it.id == sessionId }.messages.map { it.content },
            )
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun chatTitleResultRejectsUnknownMetadataBeforeGeneratedTitlePublication() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
            )
            val initialHistoryRequest = fixture.channel.sentEnvelopes.lastOrNull {
                it.type == MessageType.ChatSessionsList
            }
            if (initialHistoryRequest != null) {
                fixture.channel.enqueue(
                    envelope(
                        type = MessageType.ChatSessionsList,
                        serializer = ChatSessionsListResultPayload.serializer(),
                        payload = ChatSessionsListResultPayload(sessions = emptyList()),
                        requestId = initialHistoryRequest.requestId,
                    ),
                )
                advanceUntilIdle()
            }

            fun completeFirstTurn(prompt: String, answer: String): Pair<String, ProtocolEnvelope> {
                val titleRequestCount = fixture.channel.sentEnvelopes.count {
                    it.type == MessageType.ChatTitleRequest
                }
                fixture.viewModel.updateChatInput(prompt)
                fixture.viewModel.sendChatMessage()
                advanceUntilIdle()

                val sendEnvelope = fixture.channel.sentEnvelopes.last { it.type == MessageType.ChatSend }
                val sessionId = requireNotNull(fixture.viewModel.state.value.activeChatSessionId)
                fixture.channel.enqueue(
                    envelope(
                        type = MessageType.ChatDelta,
                        serializer = ChatDeltaPayload.serializer(),
                        payload = ChatDeltaPayload(delta = answer),
                        requestId = sendEnvelope.requestId,
                    ),
                )
                fixture.channel.enqueue(
                    envelope(
                        type = MessageType.ChatDone,
                        serializer = ChatDonePayload.serializer(),
                        payload = ChatDonePayload(),
                        requestId = sendEnvelope.requestId,
                    ),
                )
                advanceUntilIdle()

                val titleRequests = fixture.channel.sentEnvelopes.filter {
                    it.type == MessageType.ChatTitleRequest
                }
                assertEquals(titleRequestCount + 1, titleRequests.size)
                return sessionId to titleRequests.last()
            }

            val (rejectedSessionId, rejectedTitleRequest) = completeFirstTurn(
                prompt = "Explain generated-title metadata boundaries",
                answer = "Title results must stay inside the runtime contract.",
            )

            fixture.channel.enqueue(
                ProtocolEnvelope(
                    type = MessageType.ChatTitleResult,
                    requestId = rejectedTitleRequest.requestId,
                    payload = json.parseToJsonElement(
                        """
                            {
                              "title": "Leaky Generated Title",
                              "backend_url": "http://127.0.0.1:11434"
                            }
                        """.trimIndent(),
                    ).jsonObject,
                ),
            )
            advanceUntilIdle()

            val rejectedState = fixture.viewModel.state.value
            assertEquals("invalid_payload", rejectedState.error?.code)
            assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("chat.title.result"))
            assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("backend_url"))
            val rejectedSession = fixture.localStore.data.sessions.single { it.id == rejectedSessionId }
            assertFalse(rejectedSession.titleGenerated)
            assertFalse(rejectedSession.title == "Leaky Generated Title")
            assertFalse(json.encodeToString(fixture.localStore.data).contains("Leaky Generated Title"))
            assertEquals(
                listOf(
                    "Explain generated-title metadata boundaries",
                    "Title results must stay inside the runtime contract.",
                ),
                rejectedState.messages.map { it.content },
            )
            val historyRequestCountBeforeCanonical = fixture.channel.sentEnvelopes.count { it.type == MessageType.ChatSessionsList }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.ChatTitleResult,
                    serializer = ChatTitleResultPayload.serializer(),
                    payload = ChatTitleResultPayload(title = "Canonical Generated Title"),
                    requestId = rejectedTitleRequest.requestId,
                ),
            )
            advanceUntilIdle()

            val canonicalSession = fixture.localStore.data.sessions.single { it.id == rejectedSessionId }
            assertTrue(canonicalSession.titleGenerated)
            assertEquals("Canonical Generated Title", canonicalSession.title)
            assertNull(fixture.viewModel.state.value.error)
            assertEquals(
                historyRequestCountBeforeCanonical + 1,
                fixture.channel.sentEnvelopes.count {
                    it.type == MessageType.ChatSessionsList
                },
            )
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun attachmentSendAttachesMetadataOnlyToFinalUserPayloadMessage() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(visionChatModel()),
            )
            val document = textAttachment()
            val image = imageAttachment()
            fixture.viewModel.replaceStateForTest {
                it.copy(
                    selectedLanguageTag = RuntimeAppLanguage.English.languageTag,
                    chatInput = "Use these inputs",
                    pendingAttachments = listOf(document, image),
                    messages = listOf(
                        RuntimeChatMessage(
                            role = "system",
                            content = "UI-only context",
                            attachments = listOf(
                                RuntimeMessageAttachment(
                                    type = "document",
                                    name = "prior-ui-chip.txt",
                                    mimeType = "text/plain",
                                ),
                            ),
                        ),
                        RuntimeChatMessage(
                            role = "user",
                            content = "Prior question",
                            attachments = listOf(
                                RuntimeMessageAttachment(
                                    type = "document",
                                    name = "prior-user-chip.txt",
                                    mimeType = "text/plain",
                                ),
                            ),
                        ),
                        RuntimeChatMessage(role = "assistant", content = "Prior answer"),
                    ),
                )
            }

            fixture.viewModel.sendChatMessage()
            advanceUntilIdle()

            val payload = fixture.channel.lastChatSendPayload()
            assertEquals(listOf("user", "assistant", "user"), payload.messages.map { it.role })
            assertTrue(payload.messages.dropLast(1).all { it.attachments.isEmpty() })
            val sentAttachments = payload.messages.last().attachments
            assertEquals(2, sentAttachments.size)
            assertEquals("document", sentAttachments[0].type)
            assertEquals("pairing-notes.txt", sentAttachments[0].name)
            assertEquals("text/plain", sentAttachments[0].mimeType)
            assertEquals("cGFpcmluZyBub3Rlcw==", sentAttachments[0].dataBase64)
            assertEquals("image", sentAttachments[1].type)
            assertEquals("pairing-qr.png", sentAttachments[1].name)
            assertEquals("image/png", sentAttachments[1].mimeType)
            assertEquals("cGFpcmluZyBxcg==", sentAttachments[1].dataBase64)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun imageAttachmentSendRequiresVisionModelAndKeepsPendingAttachmentsWhenBlocked() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
            )
            val image = imageAttachment()
            fixture.viewModel.replaceStateForTest {
                it.copy(
                    chatInput = "Describe this image",
                    pendingAttachments = listOf(image),
                )
            }

            fixture.viewModel.sendChatMessage()
            advanceUntilIdle()

            assertTrue(fixture.channel.sentEnvelopes.none { it.type == MessageType.ChatSend })
            assertEquals("select_vision_model", fixture.viewModel.state.value.error?.code)
            assertEquals(listOf(image), fixture.viewModel.state.value.pendingAttachments)
            assertEquals("Describe this image", fixture.viewModel.state.value.chatInput)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun validAttachmentSendClearsPendingAttachmentsAndRetainsReadonlyMessageChips() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
            )
            val attachment = textAttachment()
            fixture.viewModel.replaceStateForTest {
                it.copy(
                    chatInput = "Summarize this note",
                    pendingAttachments = listOf(attachment),
                )
            }

            fixture.viewModel.sendChatMessage()
            advanceUntilIdle()

            val state = fixture.viewModel.state.value
            assertTrue(state.pendingAttachments.isEmpty())
            assertEquals("", state.chatInput)
            val userMessage = state.messages.first { it.role == "user" }
            assertEquals("Summarize this note", userMessage.content)
            assertEquals(1, userMessage.attachments.size)
            assertEquals("document", userMessage.attachments.single().type)
            assertEquals("pairing-notes.txt", userMessage.attachments.single().name)
            assertEquals("text/plain", userMessage.attachments.single().mimeType)
            assertNull(userMessage.attachments.single().text)
            assertTrue(fixture.channel.sentEnvelopes.any { it.type == MessageType.ChatSend })
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun removePendingAttachmentDropsOnlySelectedAttachmentAndClearsError() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(visionChatModel()),
            )
            val document = textAttachment()
            val image = imageAttachment()
            fixture.viewModel.replaceStateForTest {
                it.copy(
                    pendingAttachments = listOf(document, image),
                    error = RuntimeUiError(code = "select_vision_model"),
                )
            }

            fixture.viewModel.removePendingAttachment(document.id)
            advanceUntilIdle()

            val state = fixture.viewModel.state.value
            assertEquals(listOf(image), state.pendingAttachments)
            assertNull(state.error)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun streamingBlocksPendingAttachmentMutation() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val documentReference = "content://attachments/notes"
            val attachmentReader = FakeRuntimeAttachmentReader(
                mapOf(
                    documentReference to RuntimeAttachmentFile(
                        name = "notes.txt",
                        mimeType = "text/plain",
                        reportedSizeBytes = 5L,
                        bytes = "notes".encodeToByteArray(),
                    ),
                )
            )
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                attachmentReader = attachmentReader,
            )
            val existingAttachment = textAttachment()
            fixture.viewModel.replaceStateForTest {
                it.copy(
                    isStreaming = true,
                    pendingAttachments = listOf(existingAttachment),
                    error = null,
                )
            }

            fixture.viewModel.addAttachmentReferences(listOf(documentReference))
            advanceUntilIdle()

            assertTrue(attachmentReader.metadataRequests.isEmpty())
            assertTrue(attachmentReader.readRequests.isEmpty())
            assertEquals(listOf(existingAttachment), fixture.viewModel.state.value.pendingAttachments)
            assertEquals("generation_in_progress", fixture.viewModel.state.value.error?.code)

            fixture.viewModel.replaceStateForTest { it.copy(error = null) }
            fixture.viewModel.removePendingAttachment(existingAttachment.id)
            advanceUntilIdle()

            assertEquals(listOf(existingAttachment), fixture.viewModel.state.value.pendingAttachments)
            assertEquals("generation_in_progress", fixture.viewModel.state.value.error?.code)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun blankMessageWithoutAttachmentsDoesNotSend() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
            )
            fixture.viewModel.replaceStateForTest {
                it.copy(
                    chatInput = "   ",
                    pendingAttachments = emptyList(),
                )
            }

            fixture.viewModel.sendChatMessage()
            advanceUntilIdle()

            assertTrue(fixture.channel.sentEnvelopes.none { it.type == MessageType.ChatSend })
            assertTrue(fixture.viewModel.state.value.messages.isEmpty())
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun addAttachmentsLoadsDocumentAndImageUrisIntoPendingAttachments() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val documentReference = "content://attachments/notes"
            val imageReference = "content://attachments/diagram"
            val attachmentReader = FakeRuntimeAttachmentReader(
                mapOf(
                    documentReference to RuntimeAttachmentFile(
                        name = "notes.txt",
                        mimeType = "text/plain",
                        reportedSizeBytes = 5L,
                        bytes = "notes".encodeToByteArray(),
                    ),
                    imageReference to RuntimeAttachmentFile(
                        name = "diagram.png",
                        mimeType = "application/octet-stream",
                        reportedSizeBytes = 7L,
                        bytes = "diagram".encodeToByteArray(),
                    ),
                )
            )
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(visionChatModel()),
                attachmentReader = attachmentReader,
            )

            fixture.viewModel.addAttachmentReferences(listOf(documentReference, imageReference))
            advanceUntilIdle()

            val attachments = fixture.viewModel.state.value.pendingAttachments
            assertEquals(listOf(documentReference, imageReference), attachmentReader.metadataRequests)
            assertEquals(listOf(documentReference, imageReference), attachmentReader.readRequests)
            assertEquals(2, attachments.size)
            assertEquals("document", attachments[0].type)
            assertEquals("notes.txt", attachments[0].name)
            assertEquals("text/plain", attachments[0].mimeType)
            assertEquals("bm90ZXM=", attachments[0].dataBase64)
            assertEquals("image", attachments[1].type)
            assertEquals("diagram.png", attachments[1].name)
            assertEquals("application/octet-stream", attachments[1].mimeType)
            assertEquals("ZGlhZ3JhbQ==", attachments[1].dataBase64)
            assertNull(fixture.viewModel.state.value.error)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun addAttachmentsStopsBeforeReadingReportedOversizeFile() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val largeReference = "content://attachments/large"
            val attachmentReader = FakeRuntimeAttachmentReader(
                mapOf(
                    largeReference to RuntimeAttachmentFile(
                        name = "large.pdf",
                        mimeType = "application/pdf",
                        reportedSizeBytes = 16L * 1024L * 1024L,
                        bytes = "should-not-read".encodeToByteArray(),
                    ),
                )
            )
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                attachmentReader = attachmentReader,
            )

            fixture.viewModel.addAttachmentReferences(listOf(largeReference))
            advanceUntilIdle()

            assertEquals(listOf(largeReference), attachmentReader.metadataRequests)
            assertTrue(attachmentReader.readRequests.isEmpty())
            assertTrue(fixture.viewModel.state.value.pendingAttachments.isEmpty())
            assertEquals("attachment_too_large", fixture.viewModel.state.value.error?.code)
            assertEquals("large.pdf", fixture.viewModel.state.value.error?.detail)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun addAttachmentsBoundsReadWhenReportedSizeIsUnknown() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val largeReference = "content://attachments/unknown-large"
            val attachmentLimitBytes = 15 * 1024 * 1024
            val attachmentReader = FakeRuntimeAttachmentReader(
                mapOf(
                    largeReference to RuntimeAttachmentFile(
                        name = "unknown-large.txt",
                        mimeType = "text/plain",
                        reportedSizeBytes = -1L,
                        bytes = ByteArray(attachmentLimitBytes + 2) { 1 },
                    ),
                )
            )
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                attachmentReader = attachmentReader,
            )

            fixture.viewModel.addAttachmentReferences(listOf(largeReference))
            advanceUntilIdle()

            assertEquals(listOf(largeReference), attachmentReader.metadataRequests)
            assertEquals(listOf(largeReference), attachmentReader.readRequests)
            assertEquals(listOf(attachmentLimitBytes), attachmentReader.readLimits)
            assertTrue(fixture.viewModel.state.value.pendingAttachments.isEmpty())
            assertEquals("attachment_too_large", fixture.viewModel.state.value.error?.code)
            assertEquals("unknown-large.txt", fixture.viewModel.state.value.error?.detail)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun addAttachmentsKeepsAtMostFourPendingAttachments() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val references = (1..6).map { index -> "content://attachments/file-$index" }
            val files = references.associate { reference ->
                val name = reference.substringAfterLast('/')
                reference to RuntimeAttachmentFile(
                    name = "$name.txt",
                    mimeType = "text/plain",
                    reportedSizeBytes = 8L,
                    bytes = name.encodeToByteArray(),
                )
            }
            val attachmentReader = FakeRuntimeAttachmentReader(files)
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                attachmentReader = attachmentReader,
            )

            fixture.viewModel.addAttachmentReferences(references)
            advanceUntilIdle()

            val expectedLoadedReferences = references.take(4)
            assertEquals(expectedLoadedReferences, attachmentReader.metadataRequests)
            assertEquals(expectedLoadedReferences, attachmentReader.readRequests)
            assertEquals(
                listOf("file-1.txt", "file-2.txt", "file-3.txt", "file-4.txt"),
                fixture.viewModel.state.value.pendingAttachments.map { it.name },
            )
            assertEquals("attachment_limit_reached", fixture.viewModel.state.value.error?.code)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun addAttachmentsWithExistingPendingAttachmentsReadsOnlyRemainingSlotsAndShowsLimit() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        try {
            val references = (1..3).map { index -> "content://attachments/new-$index" }
            val files = references.associate { reference ->
                val name = reference.substringAfterLast('/')
                reference to RuntimeAttachmentFile(
                    name = "$name.txt",
                    mimeType = "text/plain",
                    reportedSizeBytes = 8L,
                    bytes = name.encodeToByteArray(),
                )
            }
            val attachmentReader = FakeRuntimeAttachmentReader(files)
            val fixture = createAuthenticatedRuntimeClientFixture(
                models = listOf(textChatModel()),
                attachmentReader = attachmentReader,
            )
            fixture.viewModel.replaceStateForTest {
                it.copy(
                    pendingAttachments = listOf(
                        textAttachment().copy(id = "existing-1", name = "existing-1.txt"),
                        textAttachment().copy(id = "existing-2", name = "existing-2.txt"),
                        textAttachment().copy(id = "existing-3", name = "existing-3.txt"),
                    ),
                )
            }

            fixture.viewModel.addAttachmentReferences(references)
            advanceUntilIdle()

            assertEquals(listOf(references.first()), attachmentReader.metadataRequests)
            assertEquals(listOf(references.first()), attachmentReader.readRequests)
            assertEquals(
                listOf("existing-1.txt", "existing-2.txt", "existing-3.txt", "new-1.txt"),
                fixture.viewModel.state.value.pendingAttachments.map { it.name },
            )
            assertEquals("attachment_limit_reached", fixture.viewModel.state.value.error?.code)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @Test
    fun appThemeHelperNormalizesSupportedAndInvalidValues() {
        val light = PersistedRuntimeData().withAppTheme(RuntimeAppTheme.Light)
        val dark = light.withAppTheme(RuntimeAppTheme.Dark)
        val invalid = dark.copy(appTheme = "unknown").sanitized()

        assertEquals(RuntimeAppTheme.Light.storageValue, light.appTheme)
        assertEquals(RuntimeAppTheme.Dark.storageValue, dark.appTheme)
        assertEquals(RuntimeAppTheme.System.storageValue, invalid.appTheme)
    }

    @Test
    fun persistedRuntimeDataStoresSelectedChatAndEmbeddingModelsSeparately() {
        val data = PersistedRuntimeData()
            .withSelectedModelId("  ollama:qwen3:8b  ")
            .withSelectedEmbeddingModelId("  ollama:nomic-embed-text  ")

        assertEquals("ollama:qwen3:8b", data.selectedModelId)
        assertEquals("ollama:nomic-embed-text", data.selectedEmbeddingModelId)
    }

    @Test
    fun persistedRuntimeDataCanClearSelectedEmbeddingModel() {
        val data = PersistedRuntimeData()
            .withSelectedEmbeddingModelId("ollama:nomic-embed-text")
            .withSelectedEmbeddingModelId(null)

        assertNull(data.selectedEmbeddingModelId)
        assertNull(data.sanitized().selectedEmbeddingModelId)
    }

    @Test
    fun persistedRuntimeDataDefaultsAutoReconnectOnAndCanDisableIt() {
        val disabled = PersistedRuntimeData()
            .withTrustedRuntimeAutoReconnectEnabled(false)
        val reEnabled = disabled.withTrustedRuntimeAutoReconnectEnabled(true)

        assertTrue(PersistedRuntimeData().trustedRuntimeAutoReconnectEnabled)
        assertFalse(disabled.trustedRuntimeAutoReconnectEnabled)
        assertTrue(reEnabled.trustedRuntimeAutoReconnectEnabled)
        assertFalse(disabled.sanitized().trustedRuntimeAutoReconnectEnabled)
    }

    @Test
    fun persistedRuntimeDataTracksPairingOnboardingCompletion() {
        val completed = PersistedRuntimeData().withPairingOnboardingCompleted()

        assertFalse(PersistedRuntimeData().pairingOnboardingCompleted)
        assertTrue(completed.pairingOnboardingCompleted)
        assertTrue(completed.sanitized().pairingOnboardingCompleted)
    }

    @Test
    fun persistedRuntimeDataStoresPendingPairingRouteUntilShorterRelayExpiry() {
        val now = 1_000L
        val relayExpiresAt = now + 120_000L
        val secretStore = FakeRelaySecretStore()
        val payload = runtimePairingPayload(
            host = "192.168.1.10",
            port = 43170,
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = relayExpiresAt,
            relayNonce = "nonce-route-1",
        )

        val data = PersistedRuntimeData()
            .withPendingPairingRoute(payload, now)
            .withStoredPendingPairingRelaySecret(secretStore)
        val pending = data.pendingPairingRoute
        val restoredWithoutSecretStore = pending?.toRuntimePairingPayloadOrNull()
        val restored = data.withLoadedPendingPairingRelaySecret(secretStore)
            .pendingPairingRoute
            ?.toRuntimePairingPayloadOrNull()

        assertNotNull(pending)
        assertEquals(now, pending?.capturedAtEpochMillis)
        assertEquals(relayExpiresAt, pending?.expiresAtEpochMillis)
        assertFalse(pending?.isExpired(relayExpiresAt - 1L) ?: true)
        assertTrue(pending?.isExpired(relayExpiresAt) ?: false)
        assertNull(pending?.host)
        assertNull(pending?.port)
        assertNull(pending?.relaySecret)
        assertNotNull(pending?.relaySecretRef)
        assertNull(restoredWithoutSecretStore)
        assertEquals("relay.example.test", restored?.relayHost)
        assertEquals(443, restored?.relayPort)
        assertEquals("relay-1", restored?.relayId)
        assertEquals("secret-1", restored?.relaySecret)
        assertEquals("nonce-route-1", restored?.relayNonce)
    }

    @Test
    fun persistedRuntimeDataStoresPendingP2pRendezvousRouteUntilShorterRecordExpiry() {
        val now = 1_000L
        val p2pExpiresAt = now + 90_000L
        val maxSizedP2pEncryptedBody = maxSizedOpaqueP2pEncryptedBody()
        val payload = runtimePairingPayload(
            host = "192.168.1.10",
            port = 43170,
            p2pRouteClass = "p2p_rendezvous",
            p2pRecordId = "p2p-record-1",
            p2pEncryptedBody = maxSizedP2pEncryptedBody,
            p2pExpiresAtEpochMillis = p2pExpiresAt,
            p2pAntiReplayNonce = "nonce-p2p-1",
            p2pProtocolVersion = 1,
        )

        val pending = PersistedRuntimeData()
            .withPendingPairingRoute(payload, now)
            .pendingPairingRoute
        val restored = pending?.toRuntimePairingPayloadOrNull()

        assertNotNull(pending)
        assertEquals(now, pending?.capturedAtEpochMillis)
        assertEquals(p2pExpiresAt, pending?.expiresAtEpochMillis)
        assertFalse(pending?.isExpired(p2pExpiresAt - 1L) ?: true)
        assertTrue(pending?.isExpired(p2pExpiresAt) ?: false)
        assertNull(pending?.host)
        assertNull(pending?.port)
        assertEquals("p2p_rendezvous", restored?.p2pRouteClass)
        assertEquals("p2p-record-1", restored?.p2pRecordId)
        assertEquals(OPAQUE_ROUTE_BODY_MAX_CHARS, maxSizedP2pEncryptedBody.length)
        assertEquals(maxSizedP2pEncryptedBody, restored?.p2pEncryptedBody)
        assertEquals(p2pExpiresAt, restored?.p2pExpiresAtEpochMillis)
        assertEquals("nonce-p2p-1", restored?.p2pAntiReplayNonce)
        assertEquals(1, restored?.p2pProtocolVersion)
    }

    @Test
    fun persistedRuntimeDataDropsDirectEndpointFromPendingPairingRouteStorage() {
        val now = 1_000L
        val payload = runtimePairingPayload(
            host = "192.168.1.10",
            port = 43170,
            relayHost = null,
            relayPort = null,
            relayId = null,
            relaySecret = null,
            relayExpiresAtEpochMillis = null,
            relayNonce = null,
        )
        val legacyDirectPendingRoute = validPersistedPendingPairingRoute().copy(
            host = "192.168.1.44",
            port = 43170,
        )

        val pending = PersistedRuntimeData()
            .withPendingPairingRoute(payload, now)
            .pendingPairingRoute
        val restored = pending?.toRuntimePairingPayloadOrNull()
        val restoredLegacy = PersistedRuntimeData(pendingPairingRoute = legacyDirectPendingRoute)
            .sanitized()
            .pendingPairingRoute
            ?.toRuntimePairingPayloadOrNull()

        assertNotNull(pending)
        assertEquals(now, pending?.capturedAtEpochMillis)
        assertEquals(now + 300_000L, pending?.expiresAtEpochMillis)
        assertNull(pending?.host)
        assertNull(pending?.port)
        assertEquals("runtime-1", restored?.runtimeDeviceId)
        assertNull(restored?.host)
        assertNull(restored?.port)
        assertEquals("runtime-1", restoredLegacy?.runtimeDeviceId)
        assertNull(restoredLegacy?.host)
        assertNull(restoredLegacy?.port)
    }

    @Test
    fun persistedRuntimeDataCapsPendingPairingRouteAtFiveMinutes() {
        val now = 1_000L
        val payload = runtimePairingPayload(
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = now + 900_000L,
            relayNonce = "nonce-route-1",
        )

        val pending = PersistedRuntimeData()
            .withPendingPairingRoute(payload, now)
            .pendingPairingRoute

        assertNotNull(pending)
        assertEquals(now + 300_000L, pending?.expiresAtEpochMillis)
        assertFalse(pending?.isExpired(now + 299_999L) ?: true)
        assertTrue(pending?.isExpired(now + 300_000L) ?: false)
    }

    @Test
    fun persistedRuntimeDataRejectsIncompletePendingPairingRoute() {
        val incompleteDirect = validPersistedPendingPairingRoute().copy(
            host = "192.168.1.10",
            port = null,
        )
        val incompleteRelay = validPersistedPendingPairingRoute().copy(
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = null,
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-1",
        )

        assertNull(PersistedRuntimeData(pendingPairingRoute = incompleteDirect).sanitized().pendingPairingRoute)
        assertNull(PersistedRuntimeData(pendingPairingRoute = incompleteRelay).sanitized().pendingPairingRoute)
        assertNull(incompleteRelay.toRuntimePairingPayloadOrNull())

        val incompleteP2p = validPersistedPendingPairingRoute().copy(
            p2pRouteClass = "p2p_rendezvous",
            p2pRecordId = "p2p-record-1",
            p2pEncryptedBody = null,
            p2pExpiresAtEpochMillis = 4102444800000L,
            p2pAntiReplayNonce = "nonce-p2p-1",
            p2pProtocolVersion = 1,
        )

        assertNull(PersistedRuntimeData(pendingPairingRoute = incompleteP2p).sanitized().pendingPairingRoute)
        assertNull(incompleteP2p.toRuntimePairingPayloadOrNull())

        val nonCanonicalP2p = validPersistedPendingPairingRoute().copy(
            p2pRouteClass = "p2p_rendezvous",
            p2pRecordId = "p2p record 1",
            p2pEncryptedBody = "opaque-candidate-1",
            p2pExpiresAtEpochMillis = 4102444800000L,
            p2pAntiReplayNonce = "nonce-p2p-1",
            p2pProtocolVersion = 1,
        )

        assertNull(PersistedRuntimeData(pendingPairingRoute = nonCanonicalP2p).sanitized().pendingPairingRoute)
        assertNull(nonCanonicalP2p.toRuntimePairingPayloadOrNull())
    }

    @Test
    fun persistedRuntimeDataRejectsNonCanonicalPendingPairingIdentityValues() {
        val invalidStoredRoutes = listOf(
            validPersistedPendingPairingRoute().copy(pairingNonce = " nonce-1"),
            validPersistedPendingPairingRoute().copy(pairingNonce = "n".repeat(513)),
            validPersistedPendingPairingRoute().copy(pairingCode = " 123456"),
            validPersistedPendingPairingRoute().copy(pairingCode = "123456 "),
            validPersistedPendingPairingRoute().copy(runtimeDeviceId = "runtime-1 "),
            validPersistedPendingPairingRoute().copy(runtimeDeviceId = "r".repeat(513)),
            validPersistedPendingPairingRoute().copy(fingerprint = " runtime-fingerprint"),
            validPersistedPendingPairingRoute().copy(fingerprint = "f".repeat(513)),
        )

        invalidStoredRoutes.forEach { route ->
            assertNull(PersistedRuntimeData(pendingPairingRoute = route).sanitized().pendingPairingRoute)
            assertNull(route.toRuntimePairingPayloadOrNull())
        }

        val fromPayload = PersistedRuntimeData()
            .withPendingPairingRoute(
                runtimePairingPayload(runtimeDeviceId = "runtime-1 "),
                nowMillis = 1_000L,
            )

        assertNull(fromPayload.pendingPairingRoute)
    }

    @Test
    fun persistedRuntimeDataRejectsNonCanonicalPendingPairingRouteToken() {
        val whitespaceMutated = validPersistedPendingPairingRoute().copy(
            routeToken = " route-1",
        )
        val oversized = validPersistedPendingPairingRoute().copy(
            routeToken = "r".repeat(513),
        )
        val fromPayload = PersistedRuntimeData()
            .withPendingPairingRoute(
                runtimePairingPayload(routeToken = "route-1 "),
                nowMillis = 1_000L,
            )

        assertNull(PersistedRuntimeData(pendingPairingRoute = whitespaceMutated).sanitized().pendingPairingRoute)
        assertNull(whitespaceMutated.toRuntimePairingPayloadOrNull())
        assertNull(PersistedRuntimeData(pendingPairingRoute = oversized).sanitized().pendingPairingRoute)
        assertNull(oversized.toRuntimePairingPayloadOrNull())
        assertNull(fromPayload.pendingPairingRoute)
    }

    @Test
    fun persistedRuntimeDataRejectsNonCanonicalPendingRuntimePublicKey() {
        val whitespaceMutated = validPersistedPendingPairingRoute().copy(
            runtimePublicKeyBase64 = " runtime-public-key",
        )
        val oversized = validPersistedPendingPairingRoute().copy(
            runtimePublicKeyBase64 = "k".repeat(513),
        )
        val fromPayload = PersistedRuntimeData()
            .withPendingPairingRoute(
                runtimePairingPayload(runtimePublicKeyBase64 = "runtime-public-key "),
                nowMillis = 1_000L,
            )

        assertNull(PersistedRuntimeData(pendingPairingRoute = whitespaceMutated).sanitized().pendingPairingRoute)
        assertNull(whitespaceMutated.toRuntimePairingPayloadOrNull())
        assertNull(PersistedRuntimeData(pendingPairingRoute = oversized).sanitized().pendingPairingRoute)
        assertNull(oversized.toRuntimePairingPayloadOrNull())
        assertNull(fromPayload.pendingPairingRoute)
    }

    @Test
    fun persistedRuntimeDataRejectsNonCanonicalPendingRelayRouteMaterial() {
        val completeRelay = validPersistedPendingRelayPairingRoute()
        val invalidStoredRoutes = listOf(
            completeRelay.copy(relayHost = " relay.example.test"),
            completeRelay.copy(relayId = "relay 1"),
            completeRelay.copy(relaySecret = " secret-1"),
            completeRelay.copy(relayNonce = "n".repeat(513)),
            completeRelay.copy(relayScope = " remote "),
        )

        invalidStoredRoutes.forEach { route ->
            assertNull(PersistedRuntimeData(pendingPairingRoute = route).sanitized().pendingPairingRoute)
            assertNull(route.toRuntimePairingPayloadOrNull())
        }

        val fromPayload = PersistedRuntimeData()
            .withPendingPairingRoute(
                runtimePairingPayload(
                    host = null,
                    port = null,
                    relayHost = "relay.example.test",
                    relayPort = 443,
                    relayId = "relay 1",
                    relaySecret = "secret-1",
                    relayExpiresAtEpochMillis = 4102444800000L,
                    relayNonce = "nonce-route-1",
                    relayScope = "remote",
                ),
                nowMillis = 1_000L,
            )

        assertNull(fromPayload.pendingPairingRoute)
    }

    @Test
    fun persistedRuntimeDataClearsPendingPairingRouteWithoutTouchingTrustedReconnect() {
        val data = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = true)
            .withPendingPairingRoute(runtimePairingPayload(), nowMillis = 1_000L)
            .withoutPendingPairingRoute()

        assertNull(data.pendingPairingRoute)
        assertTrue(data.trustedRuntimeAutoReconnectEnabled)
    }

    @Test
    fun persistedRuntimeDataRemovesPendingPairingRelaySecretWhenRouteClearsOrReplaces() {
        val firstPayload = runtimePairingPayload(
            pairingNonce = "nonce-first",
            runtimeDeviceId = "runtime-first",
            relayHost = "relay-first.example.test",
            relayPort = 443,
            relayId = "relay-first",
            relaySecret = "secret-first",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-first",
        )
        val secondPayload = runtimePairingPayload(
            pairingNonce = "nonce-second",
            runtimeDeviceId = "runtime-second",
            relayHost = "relay-second.example.test",
            relayPort = 443,
            relayId = "relay-second",
            relaySecret = "secret-second",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-second",
        )

        val clearedStore = FakeRuntimeLocalDataStore()
        clearedStore.save(PersistedRuntimeData().withPendingPairingRoute(firstPayload, nowMillis = 1_000L))
        val clearedRef = requireNotNull(clearedStore.data.pendingPairingRoute?.relaySecretRef)

        assertEquals("secret-first", clearedStore.relaySecret(clearedRef))

        clearedStore.save(clearedStore.load().withoutPendingPairingRoute())

        assertNull(clearedStore.data.pendingPairingRoute)
        assertNull(clearedStore.relaySecret(clearedRef))

        val replacedStore = FakeRuntimeLocalDataStore()
        replacedStore.save(PersistedRuntimeData().withPendingPairingRoute(firstPayload, nowMillis = 1_000L))
        val firstRef = requireNotNull(replacedStore.data.pendingPairingRoute?.relaySecretRef)

        replacedStore.save(PersistedRuntimeData().withPendingPairingRoute(secondPayload, nowMillis = 2_000L))
        val secondRef = requireNotNull(replacedStore.data.pendingPairingRoute?.relaySecretRef)

        assertFalse(firstRef == secondRef)
        assertNull(replacedStore.relaySecret(firstRef))
        assertEquals("secret-second", replacedStore.relaySecret(secondRef))
    }

    @Test
    fun chatSendMessagesSerializesOnlyClientVisibleConversationAndFinalAttachments() {
        val messages = listOf(
            RuntimeChatMessage(role = "system", content = "UI-only system"),
            RuntimeChatMessage(role = "user", content = "Hello"),
            RuntimeChatMessage(
                role = "system",
                content = "Runtime user memory:\n- stale client memory",
            ),
            RuntimeChatMessage(role = "assistant", content = "Runtime answered"),
            RuntimeChatMessage(role = "user", content = "Review this file"),
        )
        val attachments = listOf(
            RuntimePendingAttachment(
                id = "attachment-1",
                type = "document",
                name = "brief.pdf",
                mimeType = "application/pdf",
                sizeBytes = 12L,
                dataBase64 = "ZmFrZQ==",
            ),
        )

        val payloadMessages = chatSendMessages(messages, attachments)

        assertEquals(listOf("user", "assistant", "user"), payloadMessages.map { it.role })
        assertEquals(listOf("Hello", "Runtime answered", "Review this file"), payloadMessages.map { it.content })
        assertTrue(payloadMessages.none { it.content.contains("Runtime user memory:") })
        assertTrue(payloadMessages.none { it.content.contains("AetherLink currently provides") })
        assertTrue(payloadMessages.dropLast(1).all { it.attachments.isEmpty() })
        assertEquals("brief.pdf", payloadMessages.last().attachments.single().name)
    }

    @Test
    fun runtimeMemoryEntriesReplaceAndMutateCachedMemory() {
        val synced = PersistedRuntimeData(
            memoryEntries = listOf(
                PersistedMemoryEntry(
                    id = "local-stale",
                    content = "Stale local note",
                    enabled = true,
                    createdAtMillis = 1L,
                    updatedAtMillis = 1L,
                )
            )
        )
            .withRuntimeMemoryEntries(
                entries = listOf(
                    MemoryEntryPayload(
                        id = "runtime-1",
                        content = "  Runtime note  ",
                        enabled = true,
                        createdAt = "2026-06-25T00:00:00Z",
                        updatedAt = "2026-06-25T00:01:00Z",
                        source = MemoryEntrySourcePayload(
                            kind = "long_inactivity_summary_draft",
                            draftId = "draft-runtime-memory",
                            summaryMethod = "deterministic_preview",
                            session = MemorySummaryDraftSessionPayload(
                                sessionId = "runtime-session",
                                title = "Long idle planning chat",
                                model = "ollama:qwen3:8b",
                                lastActivityAt = "2026-06-01T00:00:00Z",
                                messageCount = 6,
                                inactiveSeconds = 1_209_600L,
                            ),
                            sourceMessageCount = 6,
                            sourceRange = "visible messages 1-6 of 6",
                            sourcePointers = listOf(
                                MemorySummaryDraftSourcePointerPayload(
                                    sessionId = "runtime-session",
                                    messageIndex = 1,
                                    role = "user",
                                    createdAt = "2026-06-01T00:00:00Z",
                                    excerpt = "Use concise Korean summaries for release notes.",
                                ),
                            ),
                        ),
                    ),
                ),
                nowMillis = 30L,
            )
        val updated = synced.withRuntimeMemoryEntry(
            entry = MemoryEntryPayload(
                id = "runtime-1",
                content = "Runtime note updated",
                enabled = false,
                updatedAt = "2026-06-25T00:02:00Z",
            ),
            nowMillis = 40L,
        )
        val removed = updated.withoutRuntimeMemoryEntry("runtime-1")

        assertEquals(listOf("runtime-1"), synced.memoryEntries.map { it.id })
        assertEquals("Runtime note", synced.memoryEntries.single().content)
        assertEquals(1_782_345_660_000L, synced.memoryEntries.single().updatedAtMillis)
        assertEquals("draft-runtime-memory", synced.memoryEntries.single().source?.draftId)
        assertEquals(
            listOf("Use concise Korean summaries for release notes."),
            runtimeMemoryEntries(synced).single().source?.sourcePointers?.map { it.excerpt },
        )
        assertFalse(updated.memoryEntries.single().enabled)
        assertEquals("Runtime note updated", updated.memoryEntries.single().content)
        assertEquals("draft-runtime-memory", updated.memoryEntries.single().source?.draftId)
        assertTrue(removed.memoryEntries.isEmpty())
    }

    @Test
    fun clientCapabilitiesAdvertiseRuntimeOwnedHistoryMemoryAndAttachments() {
        assertFalse(RUNTIME_CLIENT_CAPABILITIES.contains(MessageType.RouteRefresh))
        assertFalse(runtimeClientCapabilities(authenticatedRouteRefreshEnabled = false).contains(MessageType.RouteRefresh))
        assertTrue(runtimeClientCapabilities(authenticatedRouteRefreshEnabled = true).contains(MessageType.RouteRefresh))
        assertTrue(RUNTIME_CLIENT_CAPABILITIES.contains(MessageType.ChatSessionsList))
        assertTrue(RUNTIME_CLIENT_CAPABILITIES.contains(MessageType.ChatMessagesList))
        assertTrue(RUNTIME_CLIENT_CAPABILITIES.contains(MessageType.ChatSessionArchive))
        assertTrue(RUNTIME_CLIENT_CAPABILITIES.contains(MessageType.ChatSessionRestore))
        assertTrue(RUNTIME_CLIENT_CAPABILITIES.contains(MessageType.ChatSessionDelete))
        assertTrue(RUNTIME_CLIENT_CAPABILITIES.contains(MessageType.IndexDocumentsList))
        assertTrue(RUNTIME_CLIENT_CAPABILITIES.contains(MessageType.RetrievalQuery))
        assertTrue(RUNTIME_CLIENT_CAPABILITIES.contains(MessageType.MemoryList))
        assertTrue(RUNTIME_CLIENT_CAPABILITIES.contains(MessageType.MemoryUpsert))
        assertTrue(RUNTIME_CLIENT_CAPABILITIES.contains(MessageType.MemoryDelete))
        assertTrue(RUNTIME_CLIENT_CAPABILITIES.contains(MessageType.MemorySummaryDraftsList))
        assertTrue(RUNTIME_CLIENT_CAPABILITIES.contains(MessageType.MemorySummaryDraftApprove))
        assertTrue(RUNTIME_CLIENT_CAPABILITIES.contains(MessageType.MemorySummaryDraftDismiss))
        assertTrue(RUNTIME_CLIENT_CAPABILITIES.contains("chat.attachments"))
    }

    @Test
    fun clientCapabilitiesDoNotAdvertiseFutureWorkspaceRagSourceProtocols() {
        val reservedFutureCapabilities = listOf(
            "embeddings.create",
            "index.build",
            "research.brief.create",
            "citation.sources.list",
            "source_anchor.resolve",
            "trusted_source.approve",
            "source_control.status",
            "projects.sessions.list",
            "automation.runs.create",
            "tool.call",
            "tool.result",
            "tool.run",
            "skills.run",
            "mcp.tool.call",
            "web_search.query",
            "python.run",
            "python.exec",
            "permission.request",
            "approval.prompt",
            "audit.events.list",
            "file.read",
            "file.write",
            "file.index",
            "terminal.exec",
            "terminal.kill",
            "network.request",
            "network.open",
            "backend.call",
            "backend.configure",
            "memory.search",
            "route.candidates.exchange",
            "route.diagnostics.report",
            "route.allocation.status",
            "route.failure.report",
        )

        val defaultCapabilities = runtimeClientCapabilities(authenticatedRouteRefreshEnabled = false)
        val diagnosticCapabilities = runtimeClientCapabilities(authenticatedRouteRefreshEnabled = true)

        reservedFutureCapabilities.forEach { capability ->
            assertFalse("Default hello must not advertise $capability", defaultCapabilities.contains(capability))
            assertFalse("Diagnostic hello must not advertise $capability", diagnosticCapabilities.contains(capability))
        }
        assertTrue(defaultCapabilities.contains(MessageType.IndexDocumentsList))
        assertTrue(defaultCapabilities.contains(MessageType.RetrievalQuery))
        assertTrue(diagnosticCapabilities.contains(MessageType.RouteRefresh))
    }

    private fun <T> envelope(
        type: String,
        requestId: String,
        serializer: KSerializer<T>,
        payload: T,
    ): ProtocolEnvelope {
        return ProtocolEnvelope(
            type = type,
            requestId = requestId,
            payload = json.encodeToJsonElement(serializer, payload).jsonObject,
        )
    }

    private fun compactionMetadataJson(sentinel: String): JsonObject {
        return JsonObject(
            mapOf(
                "summary" to JsonPrimitive(sentinel),
                "source_pointers" to sourcePointersJson(sentinel),
            ),
        )
    }

    private fun sourcePointersJson(sentinel: String): JsonArray {
        return JsonArray(
            listOf(
                JsonObject(
                    mapOf(
                        "session_id" to JsonPrimitive("runtime-session"),
                        "message_index" to JsonPrimitive(1),
                        "role" to JsonPrimitive("user"),
                        "excerpt" to JsonPrimitive(sentinel),
                    ),
                ),
            ),
        )
    }

    private fun runtimePairingPayload(
        pairingNonce: String = "nonce-1",
        pairingCode: String = "123456",
        runtimeDeviceId: String = "runtime-1",
        runtimeName: String = "AetherLink Runtime",
        fingerprint: String = "runtime-fingerprint",
        runtimePublicKeyBase64: String? = "runtime-public-key",
        routeToken: String? = "route-1",
        host: String? = "192.168.1.10",
        port: Int? = 43170,
        relayHost: String? = null,
        relayPort: Int? = null,
        relayId: String? = null,
        relaySecret: String? = null,
        relayExpiresAtEpochMillis: Long? = null,
        relayNonce: String? = null,
        relayScope: String? = null,
        p2pRouteClass: String? = null,
        p2pRecordId: String? = null,
        p2pEncryptedBody: String? = null,
        p2pExpiresAtEpochMillis: Long? = null,
        p2pAntiReplayNonce: String? = null,
        p2pProtocolVersion: Int? = null,
    ): RuntimePairingPayload {
        val hasCompleteRelayAddress = !relayHost.isNullOrBlank() &&
            relayPort != null &&
            relayId != null &&
            relaySecret != null
        return RuntimePairingPayload(
            pairingNonce = pairingNonce,
            pairingCode = pairingCode,
            runtimeDeviceId = runtimeDeviceId,
            runtimeName = runtimeName,
            fingerprint = fingerprint,
            runtimePublicKeyBase64 = runtimePublicKeyBase64,
            routeToken = routeToken,
            host = host,
            port = port,
            relayHost = relayHost,
            relayPort = relayPort,
            relayId = relayId,
            relaySecret = relaySecret,
            relayExpiresAtEpochMillis = relayExpiresAtEpochMillis
                ?: if (hasCompleteRelayAddress) 4102444800000L else null,
            relayNonce = relayNonce ?: if (hasCompleteRelayAddress) "nonce-route-1" else null,
            relayScope = relayScope,
            p2pRouteClass = p2pRouteClass,
            p2pRecordId = p2pRecordId,
            p2pEncryptedBody = p2pEncryptedBody,
            p2pExpiresAtEpochMillis = p2pExpiresAtEpochMillis,
            p2pAntiReplayNonce = p2pAntiReplayNonce,
            p2pProtocolVersion = p2pProtocolVersion,
            serviceType = "_aetherlink._tcp.local.",
        )
    }

    private fun validPersistedPendingPairingRoute(): PersistedPendingPairingRoute {
        return PersistedPendingPairingRoute(
            pairingNonce = "nonce-1",
            pairingCode = "123456",
            runtimeDeviceId = "runtime-1",
            runtimeName = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            runtimePublicKeyBase64 = "runtime-public-key",
            routeToken = "route-1",
            host = null,
            port = null,
            relayHost = null,
            relayPort = null,
            relayId = null,
            relaySecret = null,
            relayExpiresAtEpochMillis = null,
            relayNonce = null,
            relayScope = null,
            p2pRouteClass = null,
            p2pRecordId = null,
            p2pEncryptedBody = null,
            p2pExpiresAtEpochMillis = null,
            p2pAntiReplayNonce = null,
            p2pProtocolVersion = null,
            serviceType = "_aetherlink._tcp.local.",
            capturedAtEpochMillis = 1_000L,
            expiresAtEpochMillis = 301_000L,
        )
    }

    private fun validPersistedPendingRelayPairingRoute(): PersistedPendingPairingRoute {
        return validPersistedPendingPairingRoute().copy(
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-1",
            relayScope = "remote",
            expiresAtEpochMillis = 301_000L,
        )
    }

    private fun identityFor(payload: RuntimePairingPayload): PairedRuntimeIdentity {
        return PairedRuntimeIdentity(
            deviceId = payload.runtimeDeviceId,
            name = payload.runtimeName,
            fingerprint = payload.fingerprint,
            publicKeyBase64 = payload.runtimePublicKeyBase64,
            routeToken = payload.routeToken,
        )
    }

    private fun sharedProtocolFixture(name: String): String {
        val fixture = generateSequence(File(System.getProperty("user.dir") ?: ".")) { it.parentFile }
            .map { File(it, "shared/protocol/fixtures/$name") }
            .firstOrNull { it.isFile }
            ?: error("Missing shared protocol fixture: $name")
        return fixture.readText().trim()
    }

    private fun RuntimeClientViewModel.clearForTest() {
        val method = RuntimeClientViewModel::class.java.getDeclaredMethod("onCleared")
        method.isAccessible = true
        method.invoke(this)
    }

    private object TestRuntimeProtocolChannel : RuntimeProtocolChannel {
        override val isConnected: Boolean = true

        override suspend fun send(envelope: ProtocolEnvelope) {
            error("Test channel does not send frames")
        }

        override suspend fun receive(): ProtocolEnvelope {
            error("Test channel does not receive frames")
        }

        override fun close() = Unit
    }

    private class CapturingRuntimeProtocolChannel : RuntimeProtocolChannel {
        val sentEnvelopes = mutableListOf<ProtocolEnvelope>()
        private var closed = false

        override val isConnected: Boolean
            get() = !closed

        override suspend fun send(envelope: ProtocolEnvelope) {
            sentEnvelopes += envelope
        }

        override suspend fun receive(): ProtocolEnvelope {
            error("Test channel does not receive frames")
        }

        override fun close() {
            closed = true
        }
    }

    private class FailingReceiveRuntimeProtocolChannel(
        private val receiveFailure: Throwable,
    ) : RuntimeProtocolChannel {
        val sentEnvelopes = mutableListOf<ProtocolEnvelope>()
        private var closed = false

        override val isConnected: Boolean
            get() = !closed

        override suspend fun send(envelope: ProtocolEnvelope) {
            sentEnvelopes += envelope
        }

        override suspend fun receive(): ProtocolEnvelope {
            throw receiveFailure
        }

        override fun close() {
            closed = true
        }
    }

    private class ScriptedRuntimeProtocolChannel : RuntimeProtocolChannel {
        val sentEnvelopes = mutableListOf<ProtocolEnvelope>()
        private val incoming = Channel<ProtocolEnvelope>(Channel.UNLIMITED)
        private var closed = false

        override val isConnected: Boolean
            get() = !closed

        override suspend fun send(envelope: ProtocolEnvelope) {
            sentEnvelopes += envelope
        }

        override suspend fun receive(): ProtocolEnvelope = incoming.receive()

        fun enqueue(envelope: ProtocolEnvelope) {
            incoming.trySend(envelope).getOrThrow()
        }

        override fun close() {
            closed = true
            incoming.close()
        }
    }

    private class FakeRuntimeLocalDataStore(
        initialData: PersistedRuntimeData = PersistedRuntimeData(),
        private val redactRuntimeOwnedLocalDataOnSave: Boolean = false,
    ) : RuntimeLocalDataStore {
        private val relaySecretStore = FakeRelaySecretStore()
        var data: PersistedRuntimeData = initialData.withStoredPendingPairingRelaySecret(relaySecretStore)
            private set

        override fun load(): PersistedRuntimeData = data.withLoadedPendingPairingRelaySecret(relaySecretStore)

        override fun save(data: PersistedRuntimeData) {
            val previousPendingSecretRef = this.data.pendingPairingRoute?.relaySecretRef
            val cleanData = if (redactRuntimeOwnedLocalDataOnSave) {
                data.withoutRuntimeOwnedLocalData()
            } else {
                data
            }
            val dataForDisk = cleanData.withStoredPendingPairingRelaySecret(relaySecretStore)
            val currentPendingSecretRef = dataForDisk.pendingPairingRoute?.relaySecretRef
            if (previousPendingSecretRef != null && previousPendingSecretRef != currentPendingSecretRef) {
                relaySecretStore.removeSecret(previousPendingSecretRef)
            }
            this.data = dataForDisk
        }

        fun relaySecret(handle: String): String? {
            return relaySecretStore.readSecret(handle)
        }
    }

    private class FakeRelaySecretStore : RelaySecretStore {
        val secrets = mutableMapOf<String, String>()

        override fun saveSecret(handle: String, secret: String) {
            secrets[handle] = secret
        }

        override fun readSecret(handle: String): String? = secrets[handle]

        override fun removeSecret(handle: String) {
            secrets.remove(handle)
        }
    }

    private class FakeTrustedRuntimeStore : RuntimeTrustedRuntimeStore {
        override val trustedRuntime: Flow<TrustedRuntime?> = emptyFlow()
        var trusted: TrustedRuntime? = null
            private set

        override suspend fun trustRuntime(runtime: TrustedRuntime) {
            trusted = runtime
        }

        override suspend fun forgetRuntime() {
            trusted = null
        }
    }

    private class FakeEmittingTrustedRuntimeStore(
        initialTrustedRuntime: TrustedRuntime?,
    ) : RuntimeTrustedRuntimeStore {
        private val trustedRuntimeFlow = MutableStateFlow(initialTrustedRuntime)
        override val trustedRuntime: Flow<TrustedRuntime?> = trustedRuntimeFlow
        var trusted: TrustedRuntime? = initialTrustedRuntime
            private set

        override suspend fun trustRuntime(runtime: TrustedRuntime) {
            trusted = runtime
            trustedRuntimeFlow.value = runtime
        }

        override suspend fun forgetRuntime() {
            trusted = null
            trustedRuntimeFlow.value = null
        }
    }

    private class FakeDeviceIdentityProvider(
        private val identity: DeviceIdentity,
    ) : RuntimeDeviceIdentityProvider {
        override suspend fun loadOrCreate(): DeviceIdentity = identity
    }

    private class FakeRuntimeAttachmentReader(
        private val files: Map<String, RuntimeAttachmentFile>,
    ) : RuntimeAttachmentReader {
        val metadataRequests = mutableListOf<String>()
        val readRequests = mutableListOf<String>()
        val readLimits = mutableListOf<Int>()

        override fun metadata(reference: String): RuntimeAttachmentMetadata {
            metadataRequests += reference
            val file = files[reference] ?: error("No fake attachment metadata for $reference")
            return RuntimeAttachmentMetadata(
                name = file.name,
                mimeType = file.mimeType,
                sizeBytes = file.reportedSizeBytes,
            )
        }

        override fun readBytes(reference: String, maxBytes: Int): ByteArray? {
            readRequests += reference
            readLimits += maxBytes
            val bytes = files[reference]?.bytes ?: return null
            val boundedSize = maxBytes + 1
            return if (bytes.size > boundedSize) bytes.copyOf(boundedSize) else bytes
        }
    }

    private data class RuntimeAttachmentFile(
        val name: String,
        val mimeType: String,
        val reportedSizeBytes: Long,
        val bytes: ByteArray?,
    )

    private object EmptyRuntimeDiscoverySource : RuntimeDiscoverySource {
        override fun discover(): Flow<List<DiscoveredRuntime>> = emptyFlow()
    }

    private object NoopRuntimeLifecycleCallbacksRegistrar : RuntimeLifecycleCallbacksRegistrar {
        override fun register(application: Application, callbacks: Application.ActivityLifecycleCallbacks) = Unit

        override fun unregister(application: Application, callbacks: Application.ActivityLifecycleCallbacks) = Unit
    }

    private data class RuntimeClientFixture(
        val viewModel: RuntimeClientViewModel,
        val channel: ScriptedRuntimeProtocolChannel,
        val localStore: FakeRuntimeLocalDataStore,
    )

    @OptIn(ExperimentalCoroutinesApi::class)
    private suspend fun TestScope.createAuthenticatedRuntimeClientFixture(
        models: List<RuntimeModel>,
        modelPayloads: List<ModelInfoPayload> = models.map { it.toModelInfoPayload() },
        selectedModelId: String = models.first().id,
        selectedEmbeddingModelId: String? = null,
        attachmentReader: RuntimeAttachmentReader? = null,
        redactRuntimeOwnedLocalDataOnSave: Boolean = false,
        initialData: PersistedRuntimeData? = null,
    ): RuntimeClientFixture {
        val channel = ScriptedRuntimeProtocolChannel()
        val localStore = FakeRuntimeLocalDataStore(
            initialData = initialData ?: PersistedRuntimeData(
                selectedModelId = selectedModelId,
                selectedEmbeddingModelId = selectedEmbeddingModelId,
                trustedRuntimeAutoReconnectEnabled = false,
            ),
            redactRuntimeOwnedLocalDataOnSave = redactRuntimeOwnedLocalDataOnSave,
        )
        val trustedStore = FakeEmittingTrustedRuntimeStore(trustedRuntimeForViewModelTests())
        val viewModel = RuntimeClientViewModel(
            application = Application(),
            dependencies = RuntimeClientViewModelDependencies(
                json = json,
                transportClient = RuntimeTransportClient(),
                transportConnector = RuntimeTransportConnector { _, _, _ ->
                    error("Direct TCP should not be used by attachment send-path tests")
                },
                relayConnector = RuntimeRelayConnector { _, _ -> channel },
                discovery = EmptyRuntimeDiscoverySource,
                trustedRuntimeStore = trustedStore,
                deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                localDataStore = localStore,
                lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                attachmentReader = attachmentReader,
                attachmentPromptHeaderProvider = ::testAttachmentOnlyPromptHeader,
                currentTimeMillis = { 1_000L },
            ),
        )
        advanceUntilIdle()

        viewModel.connectToTrustedRuntime()
        advanceUntilIdle()
        channel.enqueue(
            envelope(
                type = MessageType.AuthResponse,
                serializer = AuthResponsePayload.serializer(),
                payload = AuthResponsePayload(accepted = true),
                requestId = "auth-accepted",
            ),
        )
        advanceUntilIdle()
        channel.enqueue(
            envelope(
                type = MessageType.RuntimeHealth,
                serializer = RuntimeHealthPayload.serializer(),
                payload = RuntimeHealthPayload(status = "ok"),
                requestId = "runtime-health",
            ),
        )
        advanceUntilIdle()
        val modelsRequest = channel.sentEnvelopes.last { it.type == MessageType.ModelsList }
        channel.enqueue(
            envelope(
                type = MessageType.ModelsResult,
                serializer = ModelsResultPayload.serializer(),
                payload = ModelsResultPayload(
                    models = modelPayloads,
                ),
                requestId = modelsRequest.requestId,
            ),
        )
        advanceUntilIdle()

        return RuntimeClientFixture(
            viewModel = viewModel,
            channel = channel,
            localStore = localStore,
        )
    }

    private fun RuntimeModel.toModelInfoPayload(): ModelInfoPayload {
        return ModelInfoPayload(
            id = id.removePrefix("$provider:"),
            name = name,
            provider = provider,
            modelKind = modelKind,
            capabilities = capabilities,
            qualifiedId = id,
            installed = installed,
            source = source,
            contextWindowTokens = contextWindowTokens,
        )
    }

    private fun ScriptedRuntimeProtocolChannel.lastChatSendPayload(): ChatSendPayload {
        val envelope = sentEnvelopes.last { it.type == MessageType.ChatSend }
        return json.decodeFromJsonElement(ChatSendPayload.serializer(), envelope.payload)
    }

    @Suppress("UNCHECKED_CAST")
    private fun RuntimeClientViewModel.replaceStateForTest(
        transform: (RuntimeUiState) -> RuntimeUiState,
    ) {
        val field = RuntimeClientViewModel::class.java.getDeclaredField("mutableState")
        field.isAccessible = true
        val mutableState = field.get(this) as MutableStateFlow<RuntimeUiState>
        mutableState.value = transform(mutableState.value)
    }

    @Suppress("UNCHECKED_CAST")
    private fun <T> RuntimeClientViewModel.privateField(name: String): T? {
        val field = RuntimeClientViewModel::class.java.getDeclaredField(name)
        field.isAccessible = true
        return field.get(this) as T?
    }

    private fun memorySummaryDraftPayload(id: String): MemorySummaryDraftPayload {
        return MemorySummaryDraftPayload(
            id = id,
            session = MemorySummaryDraftSessionPayload(
                sessionId = "runtime-session",
                title = "Long idle planning chat",
                model = "ollama:qwen3:8b",
                lastActivityAt = "2026-06-01T00:00:00Z",
                messageCount = 6,
                inactiveSeconds = 1_209_600L,
            ),
            sourceMessageCount = 6,
            sourceRange = "visible messages 1-6 of 6",
            sourcePointers = listOf(
                MemorySummaryDraftSourcePointerPayload(
                    sessionId = "runtime-session",
                    messageIndex = 1,
                    role = "user",
                    createdAt = "2026-06-01T00:00:00Z",
                    excerpt = "Use concise Korean summaries for release notes.",
                ),
            ),
            summaryPreview = "Prefer concise Korean release-note summaries.",
        )
    }

    private fun memorySummaryDraftApprovedEntryPayload(
        draftId: String,
        memoryId: String,
        content: String,
    ): MemoryEntryPayload {
        return MemoryEntryPayload(
            id = memoryId,
            content = content,
            enabled = true,
            createdAt = "2026-06-25T00:00:00Z",
            updatedAt = "2026-06-25T00:01:00Z",
            source = MemoryEntrySourcePayload(
                kind = "long_inactivity_summary_draft",
                draftId = draftId,
                summaryMethod = "deterministic_preview",
                session = MemorySummaryDraftSessionPayload(
                    sessionId = "runtime-session",
                    title = "Long idle planning chat",
                    model = "ollama:qwen3:8b",
                    lastActivityAt = "2026-06-01T00:00:00Z",
                    messageCount = 6,
                    inactiveSeconds = 1_209_600L,
                ),
                sourceMessageCount = 6,
                sourceRange = "visible messages 1-6 of 6",
                sourcePointers = listOf(
                    MemorySummaryDraftSourcePointerPayload(
                        sessionId = "runtime-session",
                        messageIndex = 1,
                        role = "user",
                        createdAt = "2026-06-01T00:00:00Z",
                        excerpt = "Use concise Korean summaries for release notes.",
                    ),
                ),
            ),
        )
    }

    private fun textChatModel(): RuntimeModel {
        return RuntimeModel(
            id = "ollama:llama3.1:8b",
            name = "Llama 3.1 8B",
            provider = "ollama",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat"),
            installed = true,
        )
    }

    private fun visionChatModel(): RuntimeModel {
        return RuntimeModel(
            id = "ollama:llava:latest",
            name = "LLaVA",
            provider = "ollama",
            modelKind = MODEL_KIND_CHAT,
            capabilities = listOf("chat", "vision"),
            installed = true,
        )
    }

    private fun embeddingModel(): RuntimeModel {
        return RuntimeModel(
            id = "ollama:nomic-embed-text",
            name = "nomic-embed-text",
            provider = "ollama",
            modelKind = MODEL_KIND_EMBEDDING,
            capabilities = listOf("embedding"),
            installed = true,
        )
    }

    private fun textAttachment(): RuntimePendingAttachment {
        return RuntimePendingAttachment(
            id = "attachment-document",
            type = "document",
            name = "pairing-notes.txt",
            mimeType = "text/plain",
            sizeBytes = 13L,
            dataBase64 = "cGFpcmluZyBub3Rlcw==",
        )
    }

    private fun imageAttachment(): RuntimePendingAttachment {
        return RuntimePendingAttachment(
            id = "attachment-image",
            type = "image",
            name = "pairing-qr.png",
            mimeType = "image/png",
            sizeBytes = 10L,
            dataBase64 = "cGFpcmluZyBxcg==",
        )
    }

    private fun testAttachmentOnlyPromptHeader(languageTag: String): String {
        return when (RuntimeAppLanguage.normalizeLanguageTag(languageTag)) {
            RuntimeAppLanguage.Korean.languageTag -> "첨부한 입력을 분석하세요:"
            RuntimeAppLanguage.Japanese.languageTag -> "添付された入力を分析してください:"
            RuntimeAppLanguage.SimplifiedChinese.languageTag -> "请分析附加输入："
            RuntimeAppLanguage.French.languageTag -> "Analysez les éléments joints :"
            else -> "Analyze attached input:"
        }
    }

    private fun trustedRuntimeForViewModelTests(): TrustedRuntime {
        return TrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-token-1",
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 4_102_444_800_000L,
            relayNonce = "relay-nonce-1",
            relayScope = "remote",
        )
    }

    private fun maxSizedOpaqueP2pEncryptedBody(): String =
        "p".repeat(OPAQUE_ROUTE_BODY_MAX_CHARS)

    private fun testDeviceIdentity(): DeviceIdentity {
        val keyPair = KeyPairGenerator.getInstance("EC")
            .apply { initialize(ECGenParameterSpec("secp256r1")) }
            .generateKeyPair()
        return DeviceIdentity(
            deviceId = "client-1",
            deviceName = "AetherLink Test Client",
            publicKeyBase64 = "client-public-key",
            keyPair = keyPair,
        )
    }

    private companion object {
        val json = Json {
            ignoreUnknownKeys = true
            explicitNulls = false
            encodeDefaults = true
        }
    }
}
