package com.localagentbridge.android.runtime

import com.localagentbridge.android.core.protocol.ChatCancelPayload
import com.localagentbridge.android.core.protocol.ChatDeltaPayload
import com.localagentbridge.android.core.protocol.ChatDonePayload
import com.localagentbridge.android.core.protocol.ErrorPayload
import com.localagentbridge.android.core.protocol.MessageType
import com.localagentbridge.android.core.protocol.PairingResultPayload
import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import com.localagentbridge.android.core.protocol.RuntimeBackendStatusPayload
import com.localagentbridge.android.core.protocol.RuntimeHealthPayload
import com.localagentbridge.android.core.pairing.RuntimePairingPayload
import com.localagentbridge.android.core.transport.PairedRuntimeIdentity
import com.localagentbridge.android.core.transport.RuntimeConnectionFailure
import com.localagentbridge.android.core.transport.RuntimeConnectionFailureReason
import com.localagentbridge.android.core.transport.RuntimeConnectionManager
import com.localagentbridge.android.core.transport.RuntimeConnectionTarget
import com.localagentbridge.android.core.transport.RuntimeEndpointHint
import com.localagentbridge.android.core.transport.RuntimeEndpointSource
import com.localagentbridge.android.core.transport.RuntimeProtocolChannel
import com.localagentbridge.android.core.transport.RuntimeRouteCapability
import com.localagentbridge.android.core.transport.RuntimeRouteCandidate
import com.localagentbridge.android.core.transport.RuntimeRouteAttemptFailure
import com.localagentbridge.android.core.transport.RuntimeRouteRejection
import com.localagentbridge.android.core.transport.RuntimeRouteRejectionReason
import com.localagentbridge.android.core.transport.RuntimeRouteResolver
import com.localagentbridge.android.core.transport.RuntimeRouteSource
import com.localagentbridge.android.core.transport.RuntimeTransportConnector
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.KSerializer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.encodeToJsonElement
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class RuntimeClientViewModelTest {
    @Test
    fun trustedRuntimeConnectionTargetUsesTrustedLastKnownEndpointInsteadOfManualHostFields() {
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
        assertEquals("192.168.1.20", target?.endpointHint?.host)
        assertEquals(43170, target?.endpointHint?.port)
        assertEquals(RuntimeEndpointSource.TrustedLastKnown, target?.endpointHint?.source)
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
    fun trustedRuntimeConnectionTargetUsesIdentityOnlyWhenRelayRouteIsSaved() {
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
            ),
        )

        val target = trustedRuntimeConnectionTarget(state)

        assertEquals("runtime-relay", target?.identity?.deviceId)
        assertNull(target?.endpointHint)
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

        val cleared = pending.withClearedPendingPairing()

        assertNull(cleared.pendingPairingRuntimeName)
        assertFalse(cleared.isPairingAwaitingRoute)
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
            serviceType = "_aetherlink._tcp.local.",
        )

        val target = pairingRuntimeConnectionTarget(RuntimeUiState(), payload)

        assertEquals("runtime-identity-only", target?.identity?.deviceId)
        assertEquals("fingerprint", target?.identity?.fingerprint)
        assertEquals("route-token", target?.identity?.routeToken)
        assertNull(target?.endpointHint)
    }

    @Test
    fun pairingRuntimeTargetUsesRelayQrBeforeDirectEndpoint() {
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
            serviceType = "_aetherlink._tcp.local.",
        )

        val target = pairingRuntimeConnectionTarget(RuntimeUiState(), payload)

        assertEquals("runtime-relay", target?.identity?.deviceId)
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
    fun acceptedPairingResultPreservesQrEndpointForTrustedRuntimeRestore() {
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

        assertEquals("192.168.1.10", trusted.host)
        assertEquals(43170, trusted.port)

        val restored = RuntimeUiState(
            trustedRuntime = RuntimeTrustedRuntime(
                deviceId = trusted.deviceId,
                name = trusted.name,
                fingerprint = trusted.fingerprint,
                publicKeyBase64 = trusted.publicKeyBase64,
                routeToken = trusted.routeToken,
                endpointHint = RuntimeEndpointHint(
                    host = trusted.host ?: error("Expected persisted host"),
                    port = trusted.port ?: error("Expected persisted port"),
                    source = RuntimeEndpointSource.TrustedLastKnown,
                ),
            ),
        )
        val target = trustedRuntimeConnectionTarget(restored)

        assertEquals("runtime-1", target?.identity?.deviceId)
        assertEquals("192.168.1.10", target?.endpointHint?.host)
        assertEquals(43170, target?.endpointHint?.port)
        assertEquals(RuntimeEndpointSource.TrustedLastKnown, target?.endpointHint?.source)
    }

    @Test
    fun acceptedPairingResultDropsDirectEndpointWhenRelayRouteIsPresent() {
        val pending = runtimePairingPayload(
            host = "192.168.1.10",
            port = 43170,
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
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
                ),
            )
        )
        assertNull(
            trustedRuntimeFromRouteRefreshQr(
                current = current,
                payload = runtimePairingPayload(
                    relayHost = null,
                    relayPort = null,
                    relayId = null,
                    relaySecret = null,
                ),
            )
        )
    }

    @Test
    fun routeRefreshQrRejectsMismatchedRouteToken() {
        val current = RuntimeTrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            routeToken = "route-1",
            endpointHint = null,
        )

        val refreshed = trustedRuntimeFromRouteRefreshQr(
            current = current,
            payload = runtimePairingPayload(
                routeToken = "other-route",
                relayHost = "relay.example.test",
                relayPort = 443,
                relayId = "relay-1",
                relaySecret = "secret-1",
            ),
        )

        assertNull(refreshed)
    }

    @Test
    fun routeRefreshQrClearsTrustedEndpointWhenRelayRouteIsSaved() {
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
    fun runtimeRouteCandidatesPreferDiscoveredEndpointBeforeStaleTrustedEndpoint() {
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

        assertEquals(2, endpointRoutes.size)
        assertEquals("192.168.1.44", endpointRoutes[0].hint.host)
        assertEquals(RuntimeEndpointSource.BonjourDiscovery, endpointRoutes[0].hint.source)
        assertEquals(RuntimeRouteSource.FreshDiscovery, endpointRoutes[0].source)
        assertEquals("192.168.1.20", endpointRoutes[1].hint.host)
        assertEquals(RuntimeEndpointSource.TrustedLastKnown, endpointRoutes[1].hint.source)
        assertEquals(RuntimeRouteSource.TrustedLastKnownEndpoint, endpointRoutes[1].source)
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

        assertEquals(1, endpointRoutes.size)
        assertEquals("192.168.1.20", endpointRoutes.single().hint.host)
        assertEquals(RuntimeEndpointSource.TrustedLastKnown, endpointRoutes.single().hint.source)
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

        assertEquals("192.168.1.44", endpointRoutes[0].hint.host)
        assertEquals("192.168.1.45", endpointRoutes[1].hint.host)
        assertEquals("192.168.1.20", endpointRoutes[2].hint.host)
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

        assertEquals(1, endpointRoutes.size)
        assertEquals("192.168.1.20", endpointRoutes.single().hint.host)
        assertEquals(RuntimeEndpointSource.TrustedLastKnown, endpointRoutes.single().hint.source)
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
    fun autoReconnectTrustedRuntimeTargetDoesNotPromoteStaleTrustedLastKnownEndpoint() {
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

        assertEquals("runtime-1", target?.identity?.deviceId)
        assertNull(target?.endpointHint)
    }

    @Test
    fun autoReconnectRouteCandidatesDoNotUseStaleTrustedLastKnownEndpoint() {
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
            ?: error("Expected identity-only auto reconnect target")
        val endpointRoutes = runtimeRouteCandidates(
            state = state,
            target = target,
            includeUsbReverseFallback = false,
        ).filterIsInstance<RuntimeRouteCandidate.DirectTcp>()

        assertEquals(emptyList<RuntimeRouteCandidate.DirectTcp>(), endpointRoutes)
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

        assertEquals(1, endpointRoutes.size)
        assertEquals("192.168.1.20", endpointRoutes.single().hint.host)
        assertEquals(RuntimeEndpointSource.TrustedLastKnown, endpointRoutes.single().hint.source)
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

        assertEquals(1, endpointRoutes.size)
        assertEquals("192.168.1.20", endpointRoutes.single().hint.host)
        assertEquals(RuntimeEndpointSource.TrustedLastKnown, endpointRoutes.single().hint.source)
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
        assertEquals("192.168.1.20", endpointRoutes[2].hint.host)
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
    fun runtimeRouteCandidatesRejectManualLocalModelBackendPorts() {
        val blockedPorts = listOf(11434, 1234)

        blockedPorts.forEach { blockedPort ->
            val target = RuntimeConnectionTarget(
                identity = null,
                endpointHint = RuntimeEndpointHint(
                    host = "127.0.0.1",
                    port = blockedPort,
                    source = RuntimeEndpointSource.Manual,
                ),
            )

            val routes = runtimeRouteCandidates(RuntimeUiState(), target)

            assertTrue(routes.filterIsInstance<RuntimeRouteCandidate.DirectTcp>().isEmpty())
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
        assertEquals("192.168.219.104", endpointRoutes[1].hint.host)
        assertEquals(RuntimeEndpointSource.TrustedLastKnown, endpointRoutes[1].hint.source)
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
    fun runtimeRouteCandidatesDoNotUseStaleUiEndpointOrUsbFallbackWhenRelayRouteIsSaved() {
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

        assertEquals("no_route", noRoute.code)
        assertEquals("no_connectable_route", noConnectableRoute.code)
        assertNull(noConnectableRoute.diagnosticCode)
        assertEquals("remote_routes_unavailable", remoteRoutesUnavailable.code)
        assertEquals(
            "route_diagnostic_local_missing_remote_pending",
            remoteRoutesUnavailable.diagnosticCode,
        )
        assertEquals("connection_failed", relayRouteFailed.code)
        assertEquals("route_diagnostic_relay_failed", relayRouteFailed.diagnosticCode)
    }

    @Test
    fun runtimeProviderStatusesPreserveBackendDetails() {
        val payload = RuntimeHealthPayload(
            status = "ok",
            ollama = RuntimeBackendStatusPayload(
                available = true,
                message = "Ollama is reachable from the runtime host",
            ),
            lmStudio = RuntimeBackendStatusPayload(
                available = false,
                message = "LM Studio is not reachable from the runtime host",
                code = "backend_unavailable",
                retryable = true,
            ),
        )

        val statuses = runtimeProviderStatuses(payload)

        assertEquals(2, statuses.size)
        assertEquals(RuntimeProviderStatus("ollama", "Ollama", true, "Ollama is reachable from the runtime host"), statuses[0])
        assertEquals(
            RuntimeProviderStatus(
                id = "lm_studio",
                name = "LM Studio",
                available = false,
                message = "LM Studio is not reachable from the runtime host",
                code = "backend_unavailable",
                retryable = true,
            ),
            statuses[1],
        )
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
        val missing = RuntimeUiState()

        assertEquals(SelectedModelSendState.Ready, ready.selectedModelSendState())
        assertEquals(SelectedModelSendState.NotInstalled, notInstalled.selectedModelSendState())
        assertEquals(SelectedModelSendState.Missing, stale.selectedModelSendState())
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
    fun modelSelectionReconciliationOnlyAutoSelectsChatWhenSelectionIsEmpty() {
        val models = listOf(
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
    fun chatSuggestionsAttachToLatestAssistantMessage() {
        val state = RuntimeUiState(
            messages = listOf(
                RuntimeChatMessage(role = "assistant", content = "Older answer"),
                RuntimeChatMessage(role = "user", content = "Follow up"),
                RuntimeChatMessage(role = "assistant", content = "Latest answer"),
            )
        )

        val updated = state.withChatSuggestions(
            listOf("What should we do next?", "What should we do next?", "Can you compare the options?"),
        )

        assertTrue(updated.messages[0].suggestions.isEmpty())
        assertEquals(
            listOf("What should we do next?", "Can you compare the options?"),
            updated.messages.last().suggestions,
        )
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
                    code = "backend_failed",
                    message = "Different request failed",
                    retryable = false,
                ),
            ),
            ErrorPayload(
                code = "backend_failed",
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
        assertEquals("backend_failed", afterError.error?.code)
        assertEquals("Different request failed", afterError.error?.detail)
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
                    code = "backend_failed",
                    message = "Backend failed",
                    retryable = false,
                ),
            ),
            ErrorPayload(
                code = "backend_failed",
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
        assertEquals("backend_failed", afterError.error?.code)
        assertEquals("Backend failed", afterError.error?.detail)

        val partialAssistant = blankAssistant.copy(content = "Partial")
        val reasoningAssistant = blankAssistant.copy(reasoning = "Thinking")
        val afterPartialError = blankState.copy(messages = listOf(userMessage, partialAssistant))
            .withRuntimeError(
                envelope(
                    type = MessageType.Error,
                    requestId = "active-request",
                    serializer = ErrorPayload.serializer(),
                    payload = ErrorPayload(
                        code = "backend_failed",
                        message = "Backend failed",
                        retryable = false,
                    ),
                ),
                ErrorPayload(
                    code = "backend_failed",
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
    fun runtimeReceiveFailureClearsStreamingAndRemovesOnlyBlankAssistantPlaceholder() {
        val userMessage = RuntimeChatMessage(id = "user", role = "user", content = "Question")
        val blankAssistant = RuntimeChatMessage(id = "assistant", role = "assistant", content = "")
        val blankState = RuntimeUiState(
            isConnected = true,
            isStreaming = true,
            isLoadingSuggestions = true,
            installingModelId = "ollama:pulling",
            activeRequestId = "active-request",
            activeRouteKind = RuntimeActiveRouteKind.Relay,
            runtimeStatus = "connected",
            messages = listOf(userMessage, blankAssistant),
        )

        val afterBlankFailure = blankState.withRuntimeReceiveFailure("socket closed")

        assertFalse(afterBlankFailure.isConnected)
        assertFalse(afterBlankFailure.isStreaming)
        assertFalse(afterBlankFailure.isLoadingSuggestions)
        assertNull(afterBlankFailure.installingModelId)
        assertNull(afterBlankFailure.activeRequestId)
        assertNull(afterBlankFailure.activeRouteKind)
        assertEquals("disconnected", afterBlankFailure.runtimeStatus)
        assertEquals(listOf(userMessage), afterBlankFailure.messages)
        assertEquals("receive_failed", afterBlankFailure.error?.code)
        assertEquals("socket closed", afterBlankFailure.error?.detail)

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
    fun runtimeAuthenticationErrorTransitionsToPairingRequiredState() {
        val state = RuntimeUiState(
            isConnected = true,
            isConnecting = true,
            isStreaming = true,
            isLoadingModels = true,
            isLoadingSuggestions = true,
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
        assertFalse(afterError.isLoadingSuggestions)
        assertNull(afterError.installingModelId)
        assertNull(afterError.activeRequestId)
        assertEquals("pairing_required", afterError.runtimeStatus)
        assertNull(afterError.backendAvailable)
        assertNull(afterError.backendCode)
        assertTrue(afterError.providerStatuses.isEmpty())
        assertEquals("pairing_required", afterError.error?.code)
        assertEquals("Pair this device first", afterError.error?.detail)
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
        assertEquals("New chat", sessions.first().title)
        assertEquals(2, sessions.first().messageCount)
        assertEquals("newer", data.activeSessionId)
        assertEquals("Newer answer", activeSessionMessages(data).last().content)
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
    fun generatedChatTitleAppliesOnlyUntilUserRenamesSession() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "session",
                messages = listOf(
                    RuntimeChatMessage(id = "m1", role = "user", content = "Please explain this architecture"),
                    RuntimeChatMessage(id = "m2", role = "assistant", content = "It uses a client app and runtime host."),
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
            .withMemoryEntry(
                content = "Keep memory",
                nowMillis = 200L,
                entryId = "memory-1",
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
    }

    @Test
    fun appLanguageTagHelperNormalizesSupportedAndInvalidTags() {
        val korean = PersistedRuntimeData().withAppLanguageTag(" KO ")
        val simplifiedChinese = korean.withAppLanguageTag("zh-cn")
        val simplifiedChineseHans = simplifiedChinese.withAppLanguageTag("zh-Hans")
        val simplifiedChineseAndroidQualifier = simplifiedChineseHans.withAppLanguageTag("zh-rCN")
        val invalid = simplifiedChineseAndroidQualifier.withAppLanguageTag("unknown")
        val system = invalid.withAppLanguageTag(RuntimeAppLanguage.System.languageTag)

        assertEquals(RuntimeAppLanguage.Korean.languageTag, korean.appLanguageTag)
        assertEquals(RuntimeAppLanguage.SimplifiedChinese.languageTag, simplifiedChinese.appLanguageTag)
        assertEquals(RuntimeAppLanguage.SimplifiedChinese.languageTag, simplifiedChineseHans.appLanguageTag)
        assertEquals(RuntimeAppLanguage.SimplifiedChinese.languageTag, simplifiedChineseAndroidQualifier.appLanguageTag)
        assertEquals(RuntimeAppLanguage.System.languageTag, invalid.appLanguageTag)
        assertEquals(RuntimeAppLanguage.System.languageTag, system.appLanguageTag)
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
    fun chatSendMessagesPrependsCapabilityGuardAndOnlyEnabledMemoryAsSystemContext() {
        val messages = listOf(
            RuntimeChatMessage(role = "system", content = "UI-only system"),
            RuntimeChatMessage(role = "user", content = "Hello"),
            RuntimeChatMessage(role = "assistant", content = ""),
        )
        val memory = listOf(
            RuntimeMemoryEntry(
                id = "enabled",
                content = "Prefers concise answers",
                enabled = true,
                createdAtMillis = 1L,
                updatedAtMillis = 1L,
            ),
            RuntimeMemoryEntry(
                id = "disabled",
                content = "Disabled memory",
                enabled = false,
                createdAtMillis = 2L,
                updatedAtMillis = 2L,
            ),
        )

        val payloadMessages = chatSendMessages(messages, memory)

        assertEquals("system", payloadMessages[0].role)
        assertEquals(AETHERLINK_RUNTIME_CAPABILITY_GUARD, payloadMessages[0].content)
        assertTrue(payloadMessages[0].content.contains("does not provide live web search"))
        assertTrue(payloadMessages[0].content.contains("Do not claim that you can search the web"))
        assertEquals("system", payloadMessages[1].role)
        assertEquals("Local user memory:\n- Prefers concise answers", payloadMessages[1].content)
        assertEquals("user", payloadMessages[2].role)
        assertEquals("Hello", payloadMessages[2].content)
        assertEquals(3, payloadMessages.size)
    }

    @Test
    fun memoryEntryHelpersStoreRemoveAndDisableEntries() {
        val withEntry = PersistedRuntimeData().withMemoryEntry(
            content = "  Remember this locally  ",
            nowMillis = 10L,
            entryId = "memory-1",
        )
        val disabled = withEntry.withMemoryEntryEnabled(
            entryId = "memory-1",
            enabled = false,
            nowMillis = 20L,
        )
        val removed = disabled.withoutMemoryEntry("memory-1")

        assertEquals("Remember this locally", withEntry.memoryEntries.single().content)
        assertFalse(disabled.memoryEntries.single().enabled)
        assertEquals(20L, disabled.memoryEntries.single().updatedAtMillis)
        assertTrue(removed.memoryEntries.isEmpty())
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

    private fun runtimePairingPayload(
        runtimeDeviceId: String = "runtime-1",
        runtimePublicKeyBase64: String? = "runtime-public-key",
        routeToken: String? = "route-1",
        host: String? = "192.168.1.10",
        port: Int? = 43170,
        relayHost: String? = null,
        relayPort: Int? = null,
        relayId: String? = null,
        relaySecret: String? = null,
    ): RuntimePairingPayload {
        return RuntimePairingPayload(
            pairingNonce = "nonce-1",
            pairingCode = "123456",
            runtimeDeviceId = runtimeDeviceId,
            runtimeName = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            runtimePublicKeyBase64 = runtimePublicKeyBase64,
            routeToken = routeToken,
            host = host,
            port = port,
            relayHost = relayHost,
            relayPort = relayPort,
            relayId = relayId,
            relaySecret = relaySecret,
            serviceType = "_aetherlink._tcp.local.",
        )
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

    private companion object {
        val json = Json {
            ignoreUnknownKeys = true
            explicitNulls = false
            encodeDefaults = true
        }
    }
}
