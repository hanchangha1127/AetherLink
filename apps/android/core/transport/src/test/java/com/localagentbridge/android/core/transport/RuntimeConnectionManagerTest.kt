package com.localagentbridge.android.core.transport

import com.localagentbridge.android.core.protocol.ProtocolEnvelope
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
                publicKeyBase64 = "",
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
    fun remoteRouteSecurityContextRejectsMissingOrExpiredRouteMetadata() {
        assertThrows(IllegalArgumentException::class.java) {
            RemoteRouteSecurityContext(
                rendezvousToken = "",
                expiresAtEpochMillis = 1_000,
                antiReplayNonce = "nonce-1",
            )
        }
        assertThrows(IllegalArgumentException::class.java) {
            RemoteRouteSecurityContext(
                rendezvousToken = "token-1",
                expiresAtEpochMillis = 0,
                antiReplayNonce = "nonce-1",
            )
        }
        assertThrows(IllegalArgumentException::class.java) {
            RemoteRouteSecurityContext(
                rendezvousToken = "token-1",
                expiresAtEpochMillis = 1_000,
                antiReplayNonce = "",
            )
        }
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
                TestRuntimeProtocolChannel
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
                TestRuntimeProtocolChannel
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
                TestRuntimeProtocolChannel
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
        val endpoint = RuntimeEndpointHint(
            host = "10.0.2.2",
            port = 43170,
            source = RuntimeEndpointSource.Emulator,
        )
        val manager = RuntimeConnectionManager(
            connector = RuntimeTransportConnector { host, port, timeoutMillis ->
                calls += ConnectCall(host, port, timeoutMillis)
                TestRuntimeProtocolChannel
            },
            routeResolver = RuntimeRouteResolver {
                listOf(
                    RuntimeRouteCandidate.DirectTcp(
                        hint = endpoint,
                    )
                )
            },
        )

        val result = manager.connectWithRoute(RuntimeConnectionTarget(identity = pairedIdentity()), timeoutMillis = 750)

        assertEquals(listOf(ConnectCall("10.0.2.2", 43170, 750)), calls)
        assertEquals(RuntimeRouteCandidate.DirectTcp(endpoint), result.route)
        assertEquals(TestRuntimeProtocolChannel, result.channel)
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
                TestRuntimeProtocolChannel
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
                    security = securityContext(pairedRuntime.routeToken),
                ),
                PreparedRemoteRuntimeRoute.Relay(
                    identity = pairedRuntime,
                    relayId = "relay-${pairedRuntime.routeToken}",
                    host = "relay.example.test",
                    port = 443,
                    security = securityContext("relay-${pairedRuntime.routeToken}"),
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
            security = securityContext("p2p-session-1"),
        )
        val relayRoute = PreparedRemoteRuntimeRoute.Relay(
            identity = identity,
            relayId = "relay-route-1",
            host = "relay.example.test",
            port = 443,
            security = securityContext("relay-route-1"),
        )
        val manager = RuntimeConnectionManager(
            connector = RuntimeTransportConnector { host, port, timeoutMillis ->
                calls += ConnectCall(host, port, timeoutMillis)
                TestRuntimeProtocolChannel
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

    @Test
    fun remoteRoutePreparerCanConnectIdentityOnlyTargetThroughPeerToPeerConnector() = runBlocking {
        val directCalls = mutableListOf<ConnectCall>()
        val peerCalls = mutableListOf<PreparedRemoteRuntimeRoute.PeerToPeer>()
        val identity = pairedIdentity(routeToken = "route-token")
        val manager = RuntimeConnectionManager(
            connector = RuntimeTransportConnector { host, port, timeoutMillis ->
                directCalls += ConnectCall(host, port, timeoutMillis)
                TestRuntimeProtocolChannel
            },
            routeResolver = RuntimeRouteResolver { emptyList() },
            remoteRoutePreparer = RuntimeRemoteRoutePreparer { pairedRuntime ->
                listOf(
                    PreparedRemoteRuntimeRoute.PeerToPeer(
                        identity = pairedRuntime,
                        sessionId = "p2p-${pairedRuntime.routeToken}",
                        security = securityContext("p2p-${pairedRuntime.routeToken}"),
                    )
                )
            },
            peerToPeerConnector = RuntimePeerToPeerConnector { route, timeoutMillis ->
                peerCalls += route
                assertEquals(900, timeoutMillis)
                TestRuntimeProtocolChannel
            },
        )

        manager.connect(RuntimeConnectionTarget(identity = identity), timeoutMillis = 900)

        assertEquals(emptyList<ConnectCall>(), directCalls)
        assertEquals("p2p-route-token", peerCalls.single().sessionId)
        assertEquals(identity, peerCalls.single().identity)
    }

    @Test
    fun expiredRemoteRoutesAreRejectedBeforeConnectorAttempt() {
        val identity = pairedIdentity(routeToken = "route-token")
        val peerCalls = mutableListOf<PreparedRemoteRuntimeRoute.PeerToPeer>()
        val manager = RuntimeConnectionManager(
            connector = RuntimeTransportConnector { _, _, _ ->
                error("Direct TCP should not be used for this identity-only target")
            },
            routeResolver = RuntimeRouteResolver { emptyList() },
            remoteRoutePreparer = RuntimeRemoteRoutePreparer { pairedRuntime ->
                listOf(
                    PreparedRemoteRuntimeRoute.PeerToPeer(
                        identity = pairedRuntime,
                        sessionId = "p2p-expired",
                        security = securityContext("p2p-expired", expiresAtEpochMillis = 1_000),
                    )
                )
            },
            peerToPeerConnector = RuntimePeerToPeerConnector { route, _ ->
                peerCalls += route
                TestRuntimeProtocolChannel
            },
            currentTimeMillis = { 2_000 },
        )

        val failure = assertThrows(RuntimeConnectionFailure::class.java) {
            runBlocking {
                manager.connect(RuntimeConnectionTarget(identity = identity))
            }
        }

        assertEquals(RuntimeConnectionFailureReason.NoConnectableRoute, failure.reason)
        assertEquals(
            listOf(RuntimeRouteRejectionReason.RemoteRouteExpired),
            failure.routeRejections.map { it.reason },
        )
        assertEquals(emptyList<PreparedRemoteRuntimeRoute.PeerToPeer>(), peerCalls)
    }

    @Test
    fun mismatchedRemoteRouteIdentityIsRejectedBeforeConnectorAttempt() {
        val trustedIdentity = pairedIdentity(routeToken = "route-token")
        val mismatchedIdentity = PairedRuntimeIdentity(
            deviceId = "runtime-2",
            name = "AetherLink",
            fingerprint = "other-fingerprint",
            routeToken = "other-route-token",
        )
        val peerCalls = mutableListOf<PreparedRemoteRuntimeRoute.PeerToPeer>()
        val manager = RuntimeConnectionManager(
            connector = RuntimeTransportConnector { _, _, _ ->
                error("Direct TCP should not be used for this identity-only target")
            },
            routeResolver = RuntimeRouteResolver { emptyList() },
            remoteRoutePreparer = RuntimeRemoteRoutePreparer {
                listOf(
                    PreparedRemoteRuntimeRoute.PeerToPeer(
                        identity = mismatchedIdentity,
                        sessionId = "p2p-wrong-runtime",
                        security = securityContext("p2p-wrong-runtime"),
                    )
                )
            },
            peerToPeerConnector = RuntimePeerToPeerConnector { route, _ ->
                peerCalls += route
                TestRuntimeProtocolChannel
            },
        )

        val failure = assertThrows(RuntimeConnectionFailure::class.java) {
            runBlocking {
                manager.connect(RuntimeConnectionTarget(identity = trustedIdentity))
            }
        }

        assertEquals(RuntimeConnectionFailureReason.NoConnectableRoute, failure.reason)
        assertEquals(
            listOf(RuntimeRouteRejectionReason.RemoteRouteIdentityMismatch),
            failure.routeRejections.map { it.reason },
        )
        assertEquals(emptyList<PreparedRemoteRuntimeRoute.PeerToPeer>(), peerCalls)
    }

    @Test
    fun remoteRouteMissingPinnedMetadataIsRejectedBeforeConnectorAttempt() {
        val trustedIdentity = pairedIdentity(routeToken = "route-token")
        val incompleteIdentity = PairedRuntimeIdentity(
            deviceId = trustedIdentity.deviceId,
            name = trustedIdentity.name,
        )
        val peerCalls = mutableListOf<PreparedRemoteRuntimeRoute.PeerToPeer>()
        val manager = RuntimeConnectionManager(
            connector = RuntimeTransportConnector { _, _, _ ->
                error("Direct TCP should not be used for this identity-only target")
            },
            routeResolver = RuntimeRouteResolver { emptyList() },
            remoteRoutePreparer = RuntimeRemoteRoutePreparer {
                listOf(
                    PreparedRemoteRuntimeRoute.PeerToPeer(
                        identity = incompleteIdentity,
                        sessionId = "p2p-incomplete-runtime",
                        security = securityContext("p2p-incomplete-runtime"),
                    )
                )
            },
            peerToPeerConnector = RuntimePeerToPeerConnector { route, _ ->
                peerCalls += route
                TestRuntimeProtocolChannel
            },
        )

        val failure = assertThrows(RuntimeConnectionFailure::class.java) {
            runBlocking {
                manager.connect(RuntimeConnectionTarget(identity = trustedIdentity))
            }
        }

        assertEquals(RuntimeConnectionFailureReason.NoConnectableRoute, failure.reason)
        assertEquals(
            listOf(RuntimeRouteRejectionReason.RemoteRouteIdentityMismatch),
            failure.routeRejections.map { it.reason },
        )
        assertEquals(emptyList<PreparedRemoteRuntimeRoute.PeerToPeer>(), peerCalls)
    }

    @Test
    fun relayConnectorCanFallbackAfterPreparedPeerToPeerRouteFails() = runBlocking {
        val identity = pairedIdentity(routeToken = "route-token")
        val peerCalls = mutableListOf<String>()
        val relayCalls = mutableListOf<String>()
        val manager = RuntimeConnectionManager(
            connector = RuntimeTransportConnector { _, _, _ ->
                error("Direct TCP should not be used for this identity-only target")
            },
            routeResolver = RuntimeRouteResolver { emptyList() },
            remoteRoutePreparer = RuntimeRemoteRoutePreparer { pairedRuntime ->
                listOf(
                    PreparedRemoteRuntimeRoute.PeerToPeer(
                        identity = pairedRuntime,
                        sessionId = "p2p-session",
                        security = securityContext("p2p-session"),
                    ),
                    PreparedRemoteRuntimeRoute.Relay(
                        identity = pairedRuntime,
                        relayId = "relay-session",
                        host = "relay.example.test",
                        port = 443,
                        security = securityContext("relay-session"),
                    ),
                )
            },
            peerToPeerConnector = RuntimePeerToPeerConnector { route, _ ->
                peerCalls += route.sessionId
                throw IllegalStateException("hole punching failed")
            },
            relayConnector = RuntimeRelayConnector { route, timeoutMillis ->
                relayCalls += "${route.relayId}:$timeoutMillis"
                TestRuntimeProtocolChannel
            },
        )

        manager.connect(RuntimeConnectionTarget(identity = identity), timeoutMillis = 1_500)

        assertEquals(listOf("p2p-session"), peerCalls)
        assertEquals(listOf("relay-session:1500"), relayCalls)
    }

    private fun pairedIdentity(routeToken: String? = null): PairedRuntimeIdentity {
        return PairedRuntimeIdentity(
            deviceId = "runtime-1",
            name = "AetherLink",
            fingerprint = "fingerprint",
            routeToken = routeToken,
        )
    }

    private fun securityContext(
        token: String,
        expiresAtEpochMillis: Long = 1_893_456_000_000,
    ): RemoteRouteSecurityContext {
        return RemoteRouteSecurityContext(
            rendezvousToken = token,
            expiresAtEpochMillis = expiresAtEpochMillis,
            antiReplayNonce = "nonce-$token",
        )
    }

    private data class ConnectCall(
        val host: String,
        val port: Int,
        val timeoutMillis: Int,
    )

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
}
