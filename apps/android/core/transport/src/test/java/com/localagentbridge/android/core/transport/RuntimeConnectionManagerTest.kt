package com.localagentbridge.android.core.transport

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class RuntimeConnectionManagerTest {
    @Test
    fun pairedRuntimeIdentityRejectsMissingIdentityFields() {
        assertThrows(IllegalArgumentException::class.java) {
            PairedRuntimeIdentity(
                deviceId = "",
                name = "AetherLink",
                fingerprint = "fingerprint",
            )
        }
        assertThrows(IllegalArgumentException::class.java) {
            PairedRuntimeIdentity(
                deviceId = "runtime-1",
                name = "",
                fingerprint = "fingerprint",
            )
        }
        assertThrows(IllegalArgumentException::class.java) {
            PairedRuntimeIdentity(
                deviceId = "runtime-1",
                name = "AetherLink",
                fingerprint = "",
            )
        }
        assertThrows(IllegalArgumentException::class.java) {
            PairedRuntimeIdentity(
                deviceId = "runtime-1",
                name = "AetherLink",
                routeToken = "",
            )
        }
    }

    @Test
    fun pairedRuntimeIdentityCanCarryOptionalRouteToken() {
        val identity = PairedRuntimeIdentity(
            deviceId = "runtime-1",
            name = "AetherLink",
            fingerprint = "fingerprint",
            routeToken = "pairing-route-token",
        )

        assertEquals("runtime-1", identity.deviceId)
        assertEquals("pairing-route-token", identity.routeToken)
    }

    @Test
    fun endpointHintRejectsInvalidEndpoint() {
        assertThrows(IllegalArgumentException::class.java) {
            RuntimeEndpointHint(
                host = "",
                port = 43170,
                source = RuntimeEndpointSource.Manual,
            )
        }
        assertThrows(IllegalArgumentException::class.java) {
            RuntimeEndpointHint(
                host = "127.0.0.1",
                port = 0,
                source = RuntimeEndpointSource.Manual,
            )
        }
        assertThrows(IllegalArgumentException::class.java) {
            RuntimeEndpointHint(
                host = "127.0.0.1",
                port = 65_536,
                source = RuntimeEndpointSource.Manual,
            )
        }
    }

    @Test
    fun connectionTargetCanModelIdentityWithoutEndpointHint() {
        val target = RuntimeConnectionTarget(
            identity = PairedRuntimeIdentity(
                deviceId = "runtime-1",
                name = "AetherLink",
                fingerprint = "fingerprint",
            ),
        )

        assertEquals("runtime-1", target.identity?.deviceId)
        assertNull(target.endpointHint)
        assertThrows(IllegalArgumentException::class.java) {
            target.lastKnownEndpoint
        }
    }

    @Test
    fun connectRejectsTargetWithoutEndpointHint() {
        val calls = mutableListOf<ConnectCall>()
        val manager = RuntimeConnectionManager(
            RuntimeTransportConnector { host, port, timeoutMillis ->
                calls += ConnectCall(host, port, timeoutMillis)
            }
        )

        assertThrows(IllegalArgumentException::class.java) {
            runBlocking {
                manager.connect(
                    RuntimeConnectionTarget(
                        identity = pairedIdentity(),
                    ),
                )
            }
        }

        assertEquals(emptyList<ConnectCall>(), calls)
    }

    @Test
    fun connectDelegatesEndpointHintToTransportConnector() = runBlocking {
        val calls = mutableListOf<ConnectCall>()
        val manager = RuntimeConnectionManager(
            RuntimeTransportConnector { host, port, timeoutMillis ->
                calls += ConnectCall(host, port, timeoutMillis)
            }
        )

        manager.connect(
            RuntimeConnectionTarget(
                identity = pairedIdentity(),
                endpointHint = RuntimeEndpointHint(
                    host = "192.168.1.10",
                    port = 43170,
                    source = RuntimeEndpointSource.TrustedLastKnown,
                ),
            ),
            timeoutMillis = 1_250,
        )

        assertEquals(listOf(ConnectCall("192.168.1.10", 43170, 1_250)), calls)
    }

    @Test
    fun identityOnlyTargetResolvesRoutesButNoConnectableRoute() {
        val calls = mutableListOf<ConnectCall>()
        val manager = RuntimeConnectionManager(
            RuntimeTransportConnector { host, port, timeoutMillis ->
                calls += ConnectCall(host, port, timeoutMillis)
            }
        )

        val failure = assertThrows(RuntimeConnectionFailure::class.java) {
            runBlocking {
                manager.connect(RuntimeConnectionTarget(identity = pairedIdentity()))
            }
        }

        assertEquals(RuntimeConnectionFailureReason.NoConnectableRoute, failure.reason)
        assertTrue(failure.routes.any { it is RuntimeRouteCandidate.LocalDirect })
        assertTrue(failure.routes.any { it is RuntimeRouteCandidate.PeerToPeer })
        assertTrue(failure.routes.any { it is RuntimeRouteCandidate.Relay })
        assertTrue(
            failure.routeRejections.any {
                it.capability == RuntimeRouteCapability.DirectTcp &&
                    it.reason == RuntimeRouteRejectionReason.DirectTcpEndpointNotPrepared
            }
        )
        assertTrue(
            failure.routeRejections.any {
                it.capability == RuntimeRouteCapability.PeerToPeer &&
                    it.reason == RuntimeRouteRejectionReason.PeerToPeerConnectorNotAvailable
            }
        )
        assertTrue(
            failure.routeRejections.any {
                it.capability == RuntimeRouteCapability.Relay &&
                    it.reason == RuntimeRouteRejectionReason.RelayConnectorNotAvailable
            }
        )
        assertEquals(emptyList<ConnectCall>(), calls)
    }

    @Test
    fun endpointHintRouteConnects() = runBlocking {
        val calls = mutableListOf<ConnectCall>()
        val manager = RuntimeConnectionManager(
            connector = RuntimeTransportConnector { host, port, timeoutMillis ->
                calls += ConnectCall(host, port, timeoutMillis)
            },
            routeResolver = RuntimeRouteResolver {
                listOf(
                    RuntimeRouteCandidate.DirectTcp(
                        hint = RuntimeEndpointHint(
                            host = "10.0.2.2",
                            port = 43170,
                            source = RuntimeEndpointSource.Emulator,
                        ),
                    )
                )
            },
        )

        manager.connect(RuntimeConnectionTarget(identity = pairedIdentity()), timeoutMillis = 750)

        assertEquals(listOf(ConnectCall("10.0.2.2", 43170, 750)), calls)
    }

    @Test
    fun resolverCanPreferFreshRouteOverStaleTrustedEndpoint() = runBlocking {
        val calls = mutableListOf<ConnectCall>()
        val staleTrustedEndpoint = RuntimeEndpointHint(
            host = "192.168.1.10",
            port = 43170,
            source = RuntimeEndpointSource.TrustedLastKnown,
        )
        val freshManualEndpoint = RuntimeEndpointHint(
            host = "192.168.1.25",
            port = 43170,
            source = RuntimeEndpointSource.Manual,
        )
        val manager = RuntimeConnectionManager(
            connector = RuntimeTransportConnector { host, port, timeoutMillis ->
                calls += ConnectCall(host, port, timeoutMillis)
            },
            routeResolver = RuntimeRouteResolver {
                listOf(
                    RuntimeRouteCandidate.DirectTcp(
                        hint = freshManualEndpoint,
                        source = RuntimeRouteSource.Manual,
                    ),
                    RuntimeRouteCandidate.DirectTcp(
                        hint = staleTrustedEndpoint,
                        source = RuntimeRouteSource.TrustedLastKnownEndpoint,
                    ),
                )
            },
        )

        manager.connect(
            RuntimeConnectionTarget(
                identity = pairedIdentity(),
                endpointHint = staleTrustedEndpoint,
            ),
        )

        assertEquals(listOf(ConnectCall("192.168.1.25", 43170, 5_000)), calls)
    }

    @Test
    fun remoteRoutePreparerCanUsePairingRouteTokenWithoutDirectTcpEndpoint() {
        val identity = pairedIdentity(routeToken = "pairing-route-token")
        val preparer = RuntimeRemoteRoutePreparer { pairedRuntime ->
            listOf(
                PreparedRemoteRuntimeRoute.PeerToPeer(
                    identity = pairedRuntime,
                    sessionId = requireNotNull(pairedRuntime.routeToken),
                ),
                PreparedRemoteRuntimeRoute.Relay(
                    identity = pairedRuntime,
                    relayId = "relay-${pairedRuntime.routeToken}",
                ),
            )
        }

        val preparedRoutes = preparer.prepareRemoteRoutes(identity)

        assertEquals(
            listOf(RuntimeRouteCapability.PeerToPeer, RuntimeRouteCapability.Relay),
            preparedRoutes.map { it.capability },
        )
        assertTrue(preparedRoutes.all { it.identity == identity })
    }

    @Test
    fun futurePeerToPeerAndRelayRoutesAreNotAttemptedByDirectTcp() {
        val calls = mutableListOf<ConnectCall>()
        val identity = pairedIdentity()
        val peerToPeerRoute = PreparedRemoteRuntimeRoute.PeerToPeer(
            identity = identity,
            sessionId = "p2p-session-1",
        )
        val relayRoute = PreparedRemoteRuntimeRoute.Relay(
            identity = identity,
            relayId = "relay-route-1",
        )
        val manager = RuntimeConnectionManager(
            connector = RuntimeTransportConnector { host, port, timeoutMillis ->
                calls += ConnectCall(host, port, timeoutMillis)
            },
            routeResolver = RuntimeRouteResolver {
                listOf(
                    RuntimeRouteCandidate.PeerToPeer(
                        identity = identity,
                        preparedRoute = peerToPeerRoute,
                    ),
                    RuntimeRouteCandidate.Relay(
                        identity = identity,
                        preparedRoute = relayRoute,
                    ),
                )
            },
        )

        val failure = assertThrows(RuntimeConnectionFailure::class.java) {
            runBlocking {
                manager.connect(RuntimeConnectionTarget(identity = identity))
            }
        }

        assertEquals(RuntimeConnectionFailureReason.NoConnectableRoute, failure.reason)
        assertTrue(failure.routes.any { route ->
            route is RuntimeRouteCandidate.PeerToPeer && route.preparedRoute == peerToPeerRoute
        })
        assertTrue(failure.routes.any { route ->
            route is RuntimeRouteCandidate.Relay && route.preparedRoute == relayRoute
        })
        assertEquals(
            listOf(
                RuntimeRouteRejectionReason.PeerToPeerConnectorNotAvailable,
                RuntimeRouteRejectionReason.RelayConnectorNotAvailable,
            ),
            failure.routeRejections.map { it.reason },
        )
        assertEquals(emptyList<ConnectCall>(), calls)
    }

    private fun pairedIdentity(routeToken: String? = null): PairedRuntimeIdentity {
        return PairedRuntimeIdentity(
            deviceId = "runtime-1",
            name = "AetherLink",
            fingerprint = "fingerprint",
            routeToken = routeToken,
        )
    }

    private data class ConnectCall(
        val host: String,
        val port: Int,
        val timeoutMillis: Int,
    )
}
