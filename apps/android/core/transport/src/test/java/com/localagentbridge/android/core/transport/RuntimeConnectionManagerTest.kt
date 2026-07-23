package com.localagentbridge.android.core.transport

import com.localagentbridge.android.core.pairing.ProductionC1AuthorityBoundRecordPublication
import com.localagentbridge.android.core.pairing.ProductionC1AuthorityBoundSecureSessionDescriptor
import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import com.localagentbridge.android.core.protocol.p2pnat.P2pDirectRouteAuthorization
import com.localagentbridge.android.core.protocol.p2pnat.ProductionRouteAuthorization
import com.localagentbridge.android.core.protocol.p2pnat.ProductionSecureSessionCodec
import com.localagentbridge.android.core.protocol.p2pnat.ProductionSecureSessionTranscript
import com.localagentbridge.android.core.protocol.p2pnat.ProductionSecureSessionRecordContentType
import com.localagentbridge.android.core.protocol.p2pnat.TurnRelayRouteAuthorization
import java.io.IOException
import java.util.concurrent.CancellationException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.async
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class RuntimeConnectionManagerTest {
    private val productionTestScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    @Test
    fun productionCompositionTimeoutUsesSaturatingAddition() {
        assertEquals(30L, productionCompositionTimeoutMillis(10L, 20L))
        assertEquals(Long.MAX_VALUE, productionCompositionTimeoutMillis(Long.MAX_VALUE, 1L))
        assertEquals(
            Long.MAX_VALUE,
            productionCompositionTimeoutMillis(Long.MAX_VALUE - 5L, 6L),
        )
    }

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
                    source = RuntimeEndpointSource.PairingQr,
                ),
            ),
            timeoutMillis = 1_250,
        )

        assertEquals(listOf(ConnectCall("192.168.1.10", 43170, 1_250)), calls)
    }

    @Test
    fun defaultResolverIgnoresTrustedLastKnownEndpointHintForPairedTarget() {
        val calls = mutableListOf<ConnectCall>()
        val manager = RuntimeConnectionManager(
            RuntimeTransportConnector { host, port, timeoutMillis ->
                calls += ConnectCall(host, port, timeoutMillis)
                TestRuntimeProtocolChannel
            }
        )

        val failure = assertThrows(RuntimeConnectionFailure::class.java) {
            runBlocking {
                manager.connect(
                    RuntimeConnectionTarget(
                        identity = pairedIdentity(),
                        endpointHint = RuntimeEndpointHint(
                            host = "192.168.1.10",
                            port = 43170,
                            source = RuntimeEndpointSource.TrustedLastKnown,
                        ),
                    ),
                )
            }
        }

        assertEquals(RuntimeConnectionFailureReason.NoConnectableRoute, failure.reason)
        assertTrue(failure.routes.none { it is RuntimeRouteCandidate.DirectTcp })
        assertTrue(failure.routes.any { it is RuntimeRouteCandidate.LocalDirect })
        assertTrue(failure.routes.any { it is RuntimeRouteCandidate.PeerToPeer })
        assertTrue(failure.routes.any { it is RuntimeRouteCandidate.Relay })
        assertEquals(emptyList<ConnectCall>(), calls)
    }

    @Test
    fun preparedRelayRouteStillConnectsWhenTargetHasTrustedLastKnownEndpointHint() = runBlocking {
        val directCalls = mutableListOf<ConnectCall>()
        val relayCalls = mutableListOf<String>()
        val identity = pairedIdentity(routeToken = "route-token")
        val relayRoute = PreparedRemoteRuntimeRoute.Relay(
            identity = identity,
            relayId = "relay-session",
            host = "relay.example.test",
            port = 443,
            security = securityContext("relay-session"),
        )
        val manager = RuntimeConnectionManager(
            connector = RuntimeTransportConnector { host, port, timeoutMillis ->
                directCalls += ConnectCall(host, port, timeoutMillis)
                throw IllegalStateException("trusted last-known direct endpoint must not be attempted")
            },
            remoteRoutePreparer = RuntimeRemoteRoutePreparer { listOf(relayRoute) },
            relayConnector = RuntimeRelayConnector { route, timeoutMillis ->
                relayCalls += "${route.relayId}:$timeoutMillis"
                TestRuntimeProtocolChannel
            },
        )

        manager.connect(
            RuntimeConnectionTarget(
                identity = identity,
                endpointHint = RuntimeEndpointHint(
                    host = "192.168.1.10",
                    port = 43170,
                    source = RuntimeEndpointSource.TrustedLastKnown,
                ),
            ),
            timeoutMillis = 1_250,
        )

        assertEquals(listOf("relay-session:1250"), relayCalls)
        assertEquals(emptyList<ConnectCall>(), directCalls)
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
    fun remoteRoutePreparerRejectsRoutesThatReusePairingRouteTokenMaterial() {
        val identity = pairedIdentity(routeToken = "pairing-route-token")
        val preparer = RuntimeRemoteRoutePreparer { pairedRuntime ->
            listOf(
                PreparedRemoteRuntimeRoute.PeerToPeer(
                    identity = pairedRuntime,
                    sessionId = requireNotNull(pairedRuntime.routeToken),
                    security = securityContext(pairedRuntime.routeToken),
                ),
                PreparedRemoteRuntimeRoute.PeerToPeer(
                    identity = pairedRuntime,
                    sessionId = "p2p-record-1",
                    security = securityContext(pairedRuntime.routeToken),
                ),
                PreparedRemoteRuntimeRoute.Relay(
                    identity = pairedRuntime,
                    relayId = requireNotNull(pairedRuntime.routeToken),
                    host = "relay.example.test",
                    port = 443,
                    security = securityContext(pairedRuntime.routeToken),
                ),
                PreparedRemoteRuntimeRoute.Relay(
                    identity = pairedRuntime,
                    relayId = "relay-record-1",
                    host = "relay.example.test",
                    port = 443,
                    security = securityContext(pairedRuntime.routeToken),
                ),
            )
        }
        val peerCalls = mutableListOf<PreparedRemoteRuntimeRoute.PeerToPeer>()
        val relayCalls = mutableListOf<PreparedRemoteRuntimeRoute.Relay>()
        val manager = RuntimeConnectionManager(
            connector = RuntimeTransportConnector { _, _, _ ->
                error("Direct TCP should not be used for route-token material rejection")
            },
            routeResolver = RuntimeRouteResolver { emptyList() },
            remoteRoutePreparer = preparer,
            peerToPeerConnector = RuntimePeerToPeerConnector { route, _ ->
                peerCalls += route
                TestRuntimeProtocolChannel
            },
            relayConnector = RuntimeRelayConnector { route, _ ->
                relayCalls += route
                TestRuntimeProtocolChannel
            },
        )

        val failure = assertThrows(RuntimeConnectionFailure::class.java) {
            runBlocking {
                manager.connect(RuntimeConnectionTarget(identity = identity))
            }
        }

        assertEquals(RuntimeConnectionFailureReason.NoConnectableRoute, failure.reason)
        assertEquals(
            listOf(
                RuntimeRouteRejectionReason.RemoteRouteUsesPairingRouteToken,
                RuntimeRouteRejectionReason.RemoteRouteUsesPairingRouteToken,
                RuntimeRouteRejectionReason.RemoteRouteUsesPairingRouteToken,
                RuntimeRouteRejectionReason.RemoteRouteUsesPairingRouteToken,
            ),
            failure.routeRejections.map { it.reason },
        )
        assertEquals(emptyList<PreparedRemoteRuntimeRoute.PeerToPeer>(), peerCalls)
        assertEquals(emptyList<PreparedRemoteRuntimeRoute.Relay>(), relayCalls)
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
                        sessionId = "p2p-record-1",
                        security = securityContext("p2p-record-1"),
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
        assertEquals("p2p-record-1", peerCalls.single().sessionId)
        assertTrue(peerCalls.single().sessionId != identity.routeToken)
        assertTrue(peerCalls.single().security.rendezvousToken != identity.routeToken)
        assertEquals(identity, peerCalls.single().identity)
    }

    @Test
    fun preparedRelayRouteIsAttemptedBeforeStaleEndpointHint() = runBlocking {
        val directCalls = mutableListOf<ConnectCall>()
        val relayCalls = mutableListOf<String>()
        val identity = pairedIdentity(routeToken = "route-token")
        val relayRoute = PreparedRemoteRuntimeRoute.Relay(
            identity = identity,
            relayId = "relay-session",
            host = "relay.example.test",
            port = 443,
            security = securityContext("relay-session"),
        )
        val manager = RuntimeConnectionManager(
            connector = RuntimeTransportConnector { host, port, timeoutMillis ->
                directCalls += ConnectCall(host, port, timeoutMillis)
                throw IllegalStateException("stale direct route should not be attempted first")
            },
            routeResolver = RuntimeRouteResolver {
                listOf(
                    RuntimeRouteCandidate.DirectTcp(
                        hint = RuntimeEndpointHint(
                            host = "192.168.1.10",
                            port = 43170,
                            source = RuntimeEndpointSource.TrustedLastKnown,
                        ),
                        source = RuntimeRouteSource.TrustedLastKnownEndpoint,
                    ),
                    RuntimeRouteCandidate.Relay(identity),
                )
            },
            remoteRoutePreparer = RuntimeRemoteRoutePreparer { listOf(relayRoute) },
            relayConnector = RuntimeRelayConnector { route, timeoutMillis ->
                relayCalls += "${route.relayId}:$timeoutMillis"
                TestRuntimeProtocolChannel
            },
        )

        manager.connect(RuntimeConnectionTarget(identity = identity))

        assertEquals(listOf("relay-session:5000"), relayCalls)
        assertEquals(emptyList<ConnectCall>(), directCalls)
    }

    @Test
    fun preparedRelayRoutePrecedesFreshDiscoveryRoute() = runBlocking {
        val directCalls = mutableListOf<ConnectCall>()
        val relayCalls = mutableListOf<String>()
        val identity = pairedIdentity(routeToken = "route-token")
        val manager = RuntimeConnectionManager(
            connector = RuntimeTransportConnector { host, port, timeoutMillis ->
                directCalls += ConnectCall(host, port, timeoutMillis)
                TestRuntimeProtocolChannel
            },
            routeResolver = RuntimeRouteResolver {
                listOf(
                    RuntimeRouteCandidate.DirectTcp(
                        hint = RuntimeEndpointHint(
                            host = "192.168.1.20",
                            port = 43170,
                            source = RuntimeEndpointSource.BonjourDiscovery,
                        ),
                        source = RuntimeRouteSource.FreshDiscovery,
                    ),
                    RuntimeRouteCandidate.Relay(identity),
                )
            },
            remoteRoutePreparer = RuntimeRemoteRoutePreparer {
                listOf(
                    PreparedRemoteRuntimeRoute.Relay(
                        identity = identity,
                        relayId = "relay-session",
                        host = "relay.example.test",
                        port = 443,
                        security = securityContext("relay-session"),
                    )
                )
            },
            relayConnector = RuntimeRelayConnector { route, _ ->
                relayCalls += route.relayId
                TestRuntimeProtocolChannel
            },
        )

        manager.connect(RuntimeConnectionTarget(identity = identity))

        assertEquals(emptyList<ConnectCall>(), directCalls)
        assertEquals(listOf("relay-session"), relayCalls)
    }

    @Test
    fun freshDiscoveryRouteFallbacksWhenPreparedRelayRouteFails() = runBlocking {
        val directCalls = mutableListOf<ConnectCall>()
        val relayCalls = mutableListOf<String>()
        val identity = pairedIdentity(routeToken = "route-token")
        val manager = RuntimeConnectionManager(
            connector = RuntimeTransportConnector { host, port, timeoutMillis ->
                directCalls += ConnectCall(host, port, timeoutMillis)
                TestRuntimeProtocolChannel
            },
            routeResolver = RuntimeRouteResolver {
                listOf(
                    RuntimeRouteCandidate.DirectTcp(
                        hint = RuntimeEndpointHint(
                            host = "192.168.1.20",
                            port = 43170,
                            source = RuntimeEndpointSource.BonjourDiscovery,
                        ),
                        source = RuntimeRouteSource.FreshDiscovery,
                    ),
                    RuntimeRouteCandidate.Relay(identity),
                )
            },
            remoteRoutePreparer = RuntimeRemoteRoutePreparer {
                listOf(
                    PreparedRemoteRuntimeRoute.Relay(
                        identity = identity,
                        relayId = "relay-session",
                        host = "relay.example.test",
                        port = 443,
                        security = securityContext("relay-session"),
                    )
                )
            },
            relayConnector = RuntimeRelayConnector { route, _ ->
                relayCalls += route.relayId
                throw IllegalStateException("relay offline")
            },
        )

        manager.connect(RuntimeConnectionTarget(identity = identity))

        assertEquals(listOf("relay-session"), relayCalls)
        assertEquals(listOf(ConnectCall("192.168.1.20", 43170, 5000)), directCalls)
    }

    @Test
    fun routeCancellationIsRethrownWithoutTryingTheNextConnector() {
        val cancellation = CancellationException("connection cancelled")
        var firstConnectorCalls = 0
        var secondConnectorCalls = 0
        val routes = listOf(
            RuntimeRouteCandidate.DirectTcp(
                RuntimeEndpointHint("192.168.1.20", 43170, RuntimeEndpointSource.BonjourDiscovery),
            ),
            RuntimeRouteCandidate.DirectTcp(
                RuntimeEndpointHint("192.168.1.21", 43170, RuntimeEndpointSource.BonjourDiscovery),
            ),
        )
        val manager = RuntimeConnectionManager(
            connector = RuntimeTransportConnector { host, _, _ ->
                when (host) {
                    "192.168.1.20" -> {
                        firstConnectorCalls += 1
                        throw cancellation
                    }
                    "192.168.1.21" -> {
                        secondConnectorCalls += 1
                        TestRuntimeProtocolChannel
                    }
                    else -> error("Unexpected route host: $host")
                }
            },
            routeResolver = RuntimeRouteResolver { routes },
        )

        val actual = assertThrows(CancellationException::class.java) {
            runBlocking {
                manager.connect(RuntimeConnectionTarget(identity = pairedIdentity()))
            }
        }

        assertSame(cancellation, actual)
        assertEquals(1, firstConnectorCalls)
        assertEquals(0, secondConnectorCalls)
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

    @Test
    fun productionComposerUsesOneRawRouteWithoutCallingLegacyConnectors() = runBlocking {
        val session = productionPeerSession()
        val identity = pairedIdentity(fingerprint = session.transcript.runtimeIdentityFingerprint)
        val events = mutableListOf<String>()
        var directCalls = 0
        var peerCalls = 0
        var rawCalls = 0
        var composerCalls = 0
        var capturedRequest: RuntimeProductionConnectionRequest? = null
        val manager = RuntimeConnectionManager(
            connector = RuntimeTransportConnector { _, _, _ ->
                directCalls += 1
                TestRuntimeProtocolChannel
            },
            routeResolver = RuntimeRouteResolver { emptyList() },
            remoteRoutePreparer = RuntimeRemoteRoutePreparer { pairedRuntime ->
                listOf(
                    PreparedRemoteRuntimeRoute.PeerToPeer(
                        identity = pairedRuntime,
                        sessionId = session.expectedSessionId,
                        security = securityContext("production-p2p-session"),
                        productionSession = session,
                    )
                )
            },
            peerToPeerConnector = RuntimePeerToPeerConnector { _, _ ->
                peerCalls += 1
                TestRuntimeProtocolChannel
            },
            productionRawRouteConnector = RuntimeRawRouteConnector { route, timeoutMillis ->
                rawCalls += 1
                events += "raw"
                assertTrue(route is RuntimeRouteCandidate.PeerToPeer)
                assertEquals(1_250, timeoutMillis)
                TrackingRawFrameBodyChannel()
            },
            productionChannelComposer = RuntimeProductionChannelComposer { request, rawLease ->
                composerCalls += 1
                events += "composer"
                capturedRequest = request
                rawLease.composeForTest()
            },
        )

        val result = manager.connectWithRoute(
            target = RuntimeConnectionTarget(identity = identity),
            timeoutMillis = 1_250,
        )

        assertEquals(listOf("composer", "raw"), events)
        assertEquals(1, composerCalls)
        assertEquals(1, rawCalls)
        assertEquals(0, directCalls)
        assertEquals(0, peerCalls)
        assertEquals(identity, capturedRequest?.identity)
        assertSame(session, capturedRequest?.session)
        assertEquals(1L, capturedRequest?.connectionGeneration)
        assertEquals(1_250, capturedRequest?.timeoutMillis)
        assertSame(result.route, capturedRequest?.route)
        assertTrue(result.channel is ProductionRuntimeSecureChannelAdapter)
        result.channel.close()
    }

    @Test
    fun productionPeerRouteRejectsAConnectorSessionDifferentFromExactTranscriptSession() {
        val session = productionPeerSession()
        val identity = pairedIdentity(fingerprint = session.transcript.runtimeIdentityFingerprint)

        val failure = assertThrows(IllegalArgumentException::class.java) {
            PreparedRemoteRuntimeRoute.PeerToPeer(
                identity = identity,
                sessionId = "different-production-route-session",
                security = securityContext("different-production-route-session"),
                productionSession = session,
            )
        }

        assertTrue(failure.message?.contains("session ID must match") == true)
    }

    @Test
    fun productionRelayWithoutVerifierDerivedExactRouteBindingIsRejectedBeforeComposition() {
        val session = productionRelaySession()
        val identity = pairedIdentity(fingerprint = session.transcript.runtimeIdentityFingerprint)
        var rawCalls = 0
        var composerCalls = 0
        var legacyRelayCalls = 0
        val manager = RuntimeConnectionManager(
            connector = RuntimeTransportConnector { _, _, _ ->
                error("Production relay must not use direct TCP")
            },
            routeResolver = RuntimeRouteResolver { emptyList() },
            remoteRoutePreparer = RuntimeRemoteRoutePreparer { pairedRuntime ->
                listOf(
                    PreparedRemoteRuntimeRoute.Relay(
                        identity = pairedRuntime,
                        relayId = "opaque-relay-id",
                        host = "relay.example.test",
                        port = 443,
                        security = securityContext("production-relay"),
                        productionSession = session,
                    ),
                )
            },
            relayConnector = RuntimeRelayConnector { _, _ ->
                legacyRelayCalls += 1
                TestRuntimeProtocolChannel
            },
            productionRawRouteConnector = RuntimeRawRouteConnector { _, _ ->
                rawCalls += 1
                TrackingRawFrameBodyChannel()
            },
            productionChannelComposer = RuntimeProductionChannelComposer { _, _ ->
                composerCalls += 1
                error("Production relay composer must not be invoked")
            },
        )

        val failure = assertThrows(RuntimeConnectionFailure::class.java) {
            runBlocking { manager.connect(RuntimeConnectionTarget(identity = identity)) }
        }

        assertEquals(RuntimeConnectionFailureReason.NoConnectableRoute, failure.reason)
        assertEquals(
            listOf(RuntimeRouteRejectionReason.ProductionRelayExactBindingUnavailable),
            failure.routeRejections.map { it.reason },
        )
        assertEquals(0, rawCalls)
        assertEquals(0, composerCalls)
        assertEquals(0, legacyRelayCalls)
    }

    @Test
    fun productionRouteExpiryAfterCompositionFailsClosedAndCleansTransferredRaw() {
        val session = productionPeerSession()
        val identity = pairedIdentity(fingerprint = session.transcript.runtimeIdentityFingerprint)
        val expiresAt = 2_000L
        var now = 1_000L
        var legacyPeerCalls = 0
        val raw = TrackingRawFrameBodyChannel()
        val manager = productionManager(
            session = session,
            rawConnector = RuntimeRawRouteConnector { _, _ -> raw },
            composer = RuntimeProductionChannelComposer { _, rawLease ->
                rawLease.composeForTest().also {
                    now = expiresAt
                }
            },
            onLegacyPeerConnect = { legacyPeerCalls += 1 },
            routeExpiresAtEpochMillis = expiresAt,
            currentTimeMillis = { now },
        )

        val failure = assertThrows(RuntimeConnectionFailure::class.java) {
            runBlocking { manager.connect(RuntimeConnectionTarget(identity = identity)) }
        }

        assertEquals(RuntimeConnectionFailureReason.ProductionSessionSecurityRejected, failure.reason)
        assertTrue(
            failure.attemptFailures.single().cause.message
                ?.contains("expired during secure-channel composition") == true,
        )
        assertEquals(1, raw.closeCount)
        assertEquals(0, legacyPeerCalls)
    }

    @Test
    fun productionRouteClockRollbackAfterCompositionFailsClosed() {
        val session = productionPeerSession()
        val identity = pairedIdentity(fingerprint = session.transcript.runtimeIdentityFingerprint)
        var now = 1_000L
        var legacyPeerCalls = 0
        val raw = TrackingRawFrameBodyChannel()
        val manager = productionManager(
            session = session,
            rawConnector = RuntimeRawRouteConnector { _, _ -> raw },
            composer = RuntimeProductionChannelComposer { _, rawLease ->
                rawLease.composeForTest().also {
                    now = 999L
                }
            },
            onLegacyPeerConnect = { legacyPeerCalls += 1 },
            routeExpiresAtEpochMillis = 2_000L,
            currentTimeMillis = { now },
        )

        val failure = assertThrows(RuntimeConnectionFailure::class.java) {
            runBlocking { manager.connect(RuntimeConnectionTarget(identity = identity)) }
        }

        assertEquals(RuntimeConnectionFailureReason.ProductionSessionSecurityRejected, failure.reason)
        assertTrue(
            failure.attemptFailures.single().cause.message
                ?.contains("clock moved backwards during secure-channel composition") == true,
        )
        assertEquals(1, raw.closeCount)
        assertEquals(0, legacyPeerCalls)
    }

    @Test
    fun publicProductionConnectionsUseStrictlyIncreasingManagerOwnedGenerations() = runBlocking {
        val session = productionPeerSession()
        val identity = pairedIdentity(fingerprint = session.transcript.runtimeIdentityFingerprint)
        val generations = mutableListOf<Long>()
        val raws = mutableListOf<TrackingRawFrameBodyChannel>()
        val manager = productionManager(
            session = session,
            rawConnector = RuntimeRawRouteConnector { _, _ ->
                TrackingRawFrameBodyChannel().also(raws::add)
            },
            composer = RuntimeProductionChannelComposer { request, rawLease ->
                generations += request.connectionGeneration
                rawLease.composeForTest()
            },
        )

        val first = manager.connectWithRoute(RuntimeConnectionTarget(identity = identity))
        val second = manager.connectWithRoute(RuntimeConnectionTarget(identity = identity))

        assertEquals(listOf(1L, 2L), generations)
        first.channel.close()
        second.channel.close()
        raws.forEach { it.close() }
    }

    @Test
    fun productionComposerCannotReturnACompositionWhileIgnoringTheLease() {
        val session = productionPeerSession()
        val identity = pairedIdentity(fingerprint = session.transcript.runtimeIdentityFingerprint)
        var rawCalls = 0
        val manager = productionManager(
            session = session,
            rawConnector = RuntimeRawRouteConnector { _, _ ->
                rawCalls += 1
                TrackingRawFrameBodyChannel()
            },
            composer = RuntimeProductionChannelComposer { _, _ ->
                error("Composer ignored its manager-owned lease")
            },
        )

        val failure = assertThrows(RuntimeConnectionFailure::class.java) {
            runBlocking {
                manager.connectWithRoute(
                    RuntimeConnectionTarget(identity = identity),
                    timeoutMillis = 1_250,
                )
            }
        }

        assertEquals(0, rawCalls)
        assertTrue(
            failure.attemptFailures.single().cause.message
                ?.contains("ignored its manager-owned lease") == true,
        )
    }

    @Test
    fun productionComposerThrowAfterRawAcquisitionCleansRetainedRawExactlyOnce() {
        val session = productionPeerSession()
        val identity = pairedIdentity(fingerprint = session.transcript.runtimeIdentityFingerprint)
        val raw = TrackingRawFrameBodyChannel()
        val manager = productionManager(
            session = session,
            rawConnector = RuntimeRawRouteConnector { _, _ -> raw },
            composer = RuntimeProductionChannelComposer { _, rawLease ->
                rawLease.composeForTest()
                throw IllegalStateException("composition failed after raw acquisition")
            },
        )

        val failure = assertThrows(RuntimeConnectionFailure::class.java) {
            runBlocking {
                manager.connectWithRoute(
                    RuntimeConnectionTarget(identity = identity),
                    timeoutMillis = 1_250,
                )
            }
        }

        assertEquals(1, raw.closeCount)
        assertTrue(
            failure.attemptFailures.single().cause.message
                ?.contains("composition failed after raw acquisition") == true,
        )
    }

    @Test
    fun productionLeaseRejectsWrongAuthorityBindingAndSessionBeforeRawOpen() {
        val session = productionPeerSession()
        val identity = pairedIdentity(fingerprint = session.transcript.runtimeIdentityFingerprint)
        val cases = listOf(
            ManagerTestSecureSessionOperations(bindingId = "d".repeat(64)) to
                "capability binding mismatch",
            ManagerTestSecureSessionOperations(sessionId = "2".repeat(32)) to
                "capability session ID mismatch",
        )

        cases.forEach { (operations, expectedMessage) ->
            var rawCalls = 0
            val manager = productionManager(
                session = session,
                rawConnector = RuntimeRawRouteConnector { _, _ ->
                    rawCalls += 1
                    TrackingRawFrameBodyChannel()
                },
                composer = RuntimeProductionChannelComposer { _, rawLease ->
                    (rawLease as ManagedRuntimeProductionRawRouteLease).composeForTesting(
                        operations = operations,
                        scope = productionTestScope,
                    )
                },
            )

            val failure = assertThrows(RuntimeConnectionFailure::class.java) {
                runBlocking {
                    manager.connectWithRoute(
                        RuntimeConnectionTarget(identity = identity),
                        timeoutMillis = 1_250,
                    )
                }
            }

            assertTrue(
                failure.attemptFailures.single().cause.message
                    ?.contains(expectedMessage) == true,
            )
            assertEquals(0, rawCalls)
        }
    }

    @Test
    fun arbitrarySelfReportedProductionChannelCannotReplaceTheRawBoundAdapter() = runBlocking {
        val session = productionPeerSession()
        val identity = pairedIdentity(fingerprint = session.transcript.runtimeIdentityFingerprint)
        val raw = TrackingRawFrameBodyChannel()
        val manager = productionManager(
            session = session,
            rawConnector = RuntimeRawRouteConnector { _, _ -> raw },
            composer = RuntimeProductionChannelComposer { _, rawLease ->
                rawLease.composeForTest()
            },
        )

        val result = manager.connectWithRoute(
            RuntimeConnectionTarget(identity = identity),
            timeoutMillis = 1_250,
        )

        assertTrue(result.channel is ProductionRuntimeSecureChannelAdapter)
        result.channel.close()
        assertEquals(1, raw.closeCount)
    }

    @Test
    fun productionFinalCommitRejectsForeignAndDuplicateReceipts() = runBlocking {
        val session = productionPeerSession()
        val request = productionRequest(session, connectionGeneration = 71L)
        val foreignRaw = TrackingRawFrameBodyChannel()
        val foreignLease = ManagedRuntimeProductionRawRouteLease(
            request,
            RuntimeRawRouteConnector { _, _ -> foreignRaw },
        )
        val foreignComposition = foreignLease.composeForTest()

        val currentRaw = TrackingRawFrameBodyChannel()
        val currentLease = ManagedRuntimeProductionRawRouteLease(
            request,
            RuntimeRawRouteConnector { _, _ -> currentRaw },
        )
        currentLease.composeForTest()

        val foreignFailure = assertThrows(IllegalStateException::class.java) {
            currentLease.commit(foreignComposition)
        }
        assertTrue(foreignFailure.message?.contains("another lease") == true)
        currentLease.cleanup(foreignComposition.channel)
        assertEquals(1, currentRaw.closeCount)
        foreignLease.cleanup(null)
        assertEquals(1, foreignRaw.closeCount)

        val duplicateRequest = productionRequest(session, connectionGeneration = 72L)
        val duplicateRaw = TrackingRawFrameBodyChannel()
        val duplicateLease = ManagedRuntimeProductionRawRouteLease(
            duplicateRequest,
            RuntimeRawRouteConnector { _, _ -> duplicateRaw },
        )
        val duplicateComposition = duplicateLease.composeForTest()
        val duplicateAcquiredRaw = duplicateComposition.receipt.rawChannel
        val committed = duplicateLease.commit(duplicateComposition)
        assertTrue(committed is ProductionRuntimeSecureChannelAdapter)
        val duplicateFailure = assertThrows(IllegalStateException::class.java) {
            duplicateLease.commit(duplicateComposition)
        }
        assertTrue(duplicateFailure.message?.contains("already committed") == true)

        committed.close()
        duplicateAcquiredRaw.close()
        assertEquals(1, duplicateRaw.closeCount)
    }

    @Test
    fun cleanupBeforeAcquisitionTransitionPreventsRawConnectorInvocation() = runBlocking {
        val session = productionPeerSession()
        val request = productionRequest(session, connectionGeneration = 73L)
        val transitionEntered = CountDownLatch(1)
        val releaseTransition = CountDownLatch(1)
        var rawCalls = 0
        val lease = ManagedRuntimeProductionRawRouteLease(
            request = request,
            delegate = RuntimeRawRouteConnector { _, _ ->
                rawCalls += 1
                TrackingRawFrameBodyChannel()
            },
            beforeAcquisitionTransitionForTesting = {
                transitionEntered.countDown()
                releaseTransition.await()
            },
        )
        val pending = async(Dispatchers.Default) {
            runCatching { lease.composeForTest() }.exceptionOrNull()
        }

        try {
            assertTrue(transitionEntered.await(5, TimeUnit.SECONDS))
            assertTrue(lease.cleanup(null).isEmpty())
        } finally {
            releaseTransition.countDown()
        }
        val failure = withTimeout(5_000) { pending.await() }

        assertTrue(failure is IllegalStateException)
        assertTrue(failure?.message?.contains("lease is closed") == true)
        assertEquals(0, rawCalls)
    }

    @Test
    fun cleanupAfterTransitionCannotReturnBeforePhysicalConnectorEntry() = runBlocking {
        val session = productionPeerSession()
        val request = productionRequest(session, connectionGeneration = 74L)
        val beforeConnectorEntry = CountDownLatch(1)
        val releaseConnectorEntry = CountDownLatch(1)
        val cleanupReturned = CountDownLatch(1)
        var rawCalls = 0
        val raw = TrackingRawFrameBodyChannel()
        val lease = ManagedRuntimeProductionRawRouteLease(
            request = request,
            delegate = RuntimeRawRouteConnector { _, _ ->
                rawCalls += 1
                raw
            },
            beforePhysicalConnectorEntryForTesting = {
                beforeConnectorEntry.countDown()
                releaseConnectorEntry.await()
            },
        )
        val pendingComposition = async(Dispatchers.Default) {
            runCatching { lease.composeForTest() }.exceptionOrNull()
        }

        assertTrue(beforeConnectorEntry.await(5, TimeUnit.SECONDS))
        val cleanupThread = Thread {
            lease.cleanup(null)
            cleanupReturned.countDown()
        }.apply { start() }
        try {
            val blockedDeadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5)
            while (cleanupThread.state != Thread.State.BLOCKED &&
                System.nanoTime() < blockedDeadline
            ) {
                Thread.onSpinWait()
            }
            assertEquals(Thread.State.BLOCKED, cleanupThread.state)
            assertEquals(1L, cleanupReturned.count)
            assertEquals(0, rawCalls)
        } finally {
            releaseConnectorEntry.countDown()
        }
        cleanupThread.join(TimeUnit.SECONDS.toMillis(5))
        assertEquals(0L, cleanupReturned.count)
        val failure = withTimeout(5_000) { pendingComposition.await() }

        assertTrue(failure is IllegalStateException)
        assertEquals(1, rawCalls)
        assertEquals(1, raw.closeCount)
    }

    @Test
    fun productionComposerFailureIsTerminalAndDoesNotTryAnotherProductionOrDirectRoute() {
        val session = productionPeerSession()
        val identity = pairedIdentity(fingerprint = session.transcript.runtimeIdentityFingerprint)
        var directCalls = 0
        var peerCalls = 0
        var rawCalls = 0
        var composerCalls = 0
        val manager = RuntimeConnectionManager(
            connector = RuntimeTransportConnector { _, _, _ ->
                directCalls += 1
                TestRuntimeProtocolChannel
            },
            routeResolver = RuntimeRouteResolver {
                listOf(
                    RuntimeRouteCandidate.DirectTcp(
                        hint = RuntimeEndpointHint(
                            host = "192.168.1.40",
                            port = 43170,
                            source = RuntimeEndpointSource.BonjourDiscovery,
                        ),
                        source = RuntimeRouteSource.FreshDiscovery,
                    )
                )
            },
            remoteRoutePreparer = RuntimeRemoteRoutePreparer { pairedRuntime ->
                listOf(
                    PreparedRemoteRuntimeRoute.PeerToPeer(
                        identity = pairedRuntime,
                        sessionId = session.expectedSessionId,
                        security = securityContext("production-p2p-session-1"),
                        productionSession = session,
                    ),
                    PreparedRemoteRuntimeRoute.PeerToPeer(
                        identity = pairedRuntime,
                        sessionId = session.expectedSessionId,
                        security = securityContext("production-p2p-session-2"),
                        productionSession = session,
                    ),
                )
            },
            peerToPeerConnector = RuntimePeerToPeerConnector { _, _ ->
                peerCalls += 1
                TestRuntimeProtocolChannel
            },
            productionRawRouteConnector = RuntimeRawRouteConnector { _, _ ->
                rawCalls += 1
                TrackingRawFrameBodyChannel()
            },
            productionChannelComposer = RuntimeProductionChannelComposer { _, _ ->
                composerCalls += 1
                throw IllegalStateException("fresh start capability is unavailable")
            },
        )

        val failure = assertThrows(RuntimeConnectionFailure::class.java) {
            runBlocking {
                manager.connect(RuntimeConnectionTarget(identity = identity))
            }
        }

        assertEquals(RuntimeConnectionFailureReason.ProductionSessionSecurityRejected, failure.reason)
        assertEquals(1, failure.attemptFailures.size)
        assertEquals(2, failure.routes.size)
        assertEquals(1, composerCalls)
        assertEquals(0, rawCalls)
        assertEquals(0, peerCalls)
        assertEquals(0, directCalls)
        assertTrue(failure.routes.all { it is RuntimeRouteCandidate.PeerToPeer })
    }

    @Test
    fun productionRawFailureIsTerminalAndDoesNotTryTheNextProductionRoute() {
        val session = productionPeerSession()
        val identity = pairedIdentity(fingerprint = session.transcript.runtimeIdentityFingerprint)
        var peerCalls = 0
        var rawCalls = 0
        var composerCalls = 0
        val manager = RuntimeConnectionManager(
            connector = RuntimeTransportConnector { _, _, _ ->
                error("Production peer route must not use direct TCP")
            },
            routeResolver = RuntimeRouteResolver { emptyList() },
            remoteRoutePreparer = RuntimeRemoteRoutePreparer { pairedRuntime ->
                listOf(
                    PreparedRemoteRuntimeRoute.PeerToPeer(
                        identity = pairedRuntime,
                        sessionId = session.expectedSessionId,
                        security = securityContext("production-p2p-session"),
                        productionSession = session,
                    ),
                    PreparedRemoteRuntimeRoute.PeerToPeer(
                        identity = pairedRuntime,
                        sessionId = session.expectedSessionId,
                        security = securityContext("production-p2p-session-2"),
                        productionSession = session,
                    ),
                )
            },
            peerToPeerConnector = RuntimePeerToPeerConnector { _, _ ->
                peerCalls += 1
                TestRuntimeProtocolChannel
            },
            productionRawRouteConnector = RuntimeRawRouteConnector { _, _ ->
                rawCalls += 1
                throw IllegalStateException("raw route failed")
            },
            productionChannelComposer = RuntimeProductionChannelComposer { _, rawLease ->
                composerCalls += 1
                rawLease.composeForTest()
            },
        )

        val failure = assertThrows(RuntimeConnectionFailure::class.java) {
            runBlocking {
                manager.connect(RuntimeConnectionTarget(identity = identity))
            }
        }

        assertEquals(RuntimeConnectionFailureReason.ProductionSessionSecurityRejected, failure.reason)
        assertEquals(1, composerCalls)
        assertEquals(1, rawCalls)
        assertEquals(0, peerCalls)
    }

    @Test
    fun productionRouteWithoutCompositionIsRejectedBeforeLegacyConnectorInvocation() {
        val session = productionPeerSession()
        val identity = pairedIdentity(fingerprint = session.transcript.runtimeIdentityFingerprint)
        var peerCalls = 0
        val manager = RuntimeConnectionManager(
            connector = RuntimeTransportConnector { _, _, _ ->
                error("Production peer route must not use direct TCP")
            },
            routeResolver = RuntimeRouteResolver { emptyList() },
            remoteRoutePreparer = RuntimeRemoteRoutePreparer { pairedRuntime ->
                listOf(
                    PreparedRemoteRuntimeRoute.PeerToPeer(
                        identity = pairedRuntime,
                        sessionId = session.expectedSessionId,
                        security = securityContext("production-p2p-session"),
                        productionSession = session,
                    )
                )
            },
            peerToPeerConnector = RuntimePeerToPeerConnector { _, _ ->
                peerCalls += 1
                TestRuntimeProtocolChannel
            },
        )

        val failure = assertThrows(RuntimeConnectionFailure::class.java) {
            runBlocking {
                manager.connect(RuntimeConnectionTarget(identity = identity))
            }
        }

        assertEquals(RuntimeConnectionFailureReason.NoConnectableRoute, failure.reason)
        assertEquals(
            listOf(RuntimeRouteRejectionReason.ProductionChannelCompositionNotAvailable),
            failure.routeRejections.map { it.reason },
        )
        assertEquals(0, peerCalls)
    }

    @Test
    fun productionComposerCancellationIsSecurityTerminalAndDoesNotRetry() {
        val session = productionPeerSession()
        val identity = pairedIdentity(fingerprint = session.transcript.runtimeIdentityFingerprint)
        var peerCalls = 0
        var rawCalls = 0
        var composerCalls = 0
        val raw = TrackingRawFrameBodyChannel()
        val cancellation = CancellationException("cancelled after raw acquisition")
        val manager = RuntimeConnectionManager(
            connector = RuntimeTransportConnector { _, _, _ ->
                error("Production peer route must not use direct TCP")
            },
            routeResolver = RuntimeRouteResolver { emptyList() },
            remoteRoutePreparer = RuntimeRemoteRoutePreparer { pairedRuntime ->
                listOf(
                    PreparedRemoteRuntimeRoute.PeerToPeer(
                        identity = pairedRuntime,
                        sessionId = session.expectedSessionId,
                        security = securityContext("production-p2p-session"),
                        productionSession = session,
                    ),
                    PreparedRemoteRuntimeRoute.PeerToPeer(
                        identity = pairedRuntime,
                        sessionId = session.expectedSessionId,
                        security = securityContext("production-p2p-session-2"),
                        productionSession = session,
                    ),
                )
            },
            peerToPeerConnector = RuntimePeerToPeerConnector { _, _ ->
                peerCalls += 1
                TestRuntimeProtocolChannel
            },
            productionRawRouteConnector = RuntimeRawRouteConnector { _, _ ->
                rawCalls += 1
                raw
            },
            productionChannelComposer = RuntimeProductionChannelComposer { _, rawLease ->
                composerCalls += 1
                rawLease.composeForTest()
                throw cancellation
            },
        )

        val failure = assertThrows(CancellationException::class.java) {
            runBlocking {
                manager.connect(RuntimeConnectionTarget(identity = identity))
            }
        }

        assertSame(cancellation, failure)
        assertEquals(1, composerCalls)
        assertEquals(1, rawCalls)
        assertEquals(1, raw.closeCount)
        assertEquals(0, peerCalls)
    }

    @Test
    fun callerCancellationClosesLeaseWhileComposerBlocksNonCooperativelyAfterCompose() = runBlocking {
        val session = productionPeerSession()
        val identity = pairedIdentity(fingerprint = session.transcript.runtimeIdentityFingerprint)
        val raw = TrackingRawFrameBodyChannel()
        val composed = CountDownLatch(1)
        val releaseComposer = CountDownLatch(1)
        val composerReturned = CountDownLatch(1)
        val manager = productionManager(
            session = session,
            rawConnector = RuntimeRawRouteConnector { _, _ -> raw },
            composer = RuntimeProductionChannelComposer { _, rawLease ->
                val composition = rawLease.composeForTest()
                composed.countDown()
                while (true) {
                    try {
                        releaseComposer.await()
                        break
                    } catch (_: InterruptedException) {
                        // Deliberately non-cooperative: cancellation must not gate lease cleanup.
                    }
                }
                composerReturned.countDown()
                composition
            },
        )
        val pending = async(Dispatchers.Default) {
            manager.connect(RuntimeConnectionTarget(identity = identity))
        }

        assertTrue(composed.await(5, TimeUnit.SECONDS))
        pending.cancel(CancellationException("caller cancelled stalled composer"))
        withTimeout(5_000) { pending.join() }

        assertEquals(1, raw.closeCount)
        assertTrue(pending.isCancelled)
        releaseComposer.countDown()
        assertTrue(composerReturned.await(5, TimeUnit.SECONDS))
    }

    @Test
    fun cancellationAfterCommitBeforePublicDeliveryClosesCommittedChannelForBothApis() {
        listOf(false, true).forEach { returnRoute ->
            val session = productionPeerSession()
            val identity = pairedIdentity(fingerprint = session.transcript.runtimeIdentityFingerprint)
            val cancellation = CancellationException(
                if (returnRoute) "cancel connectWithRoute delivery" else "cancel connect delivery",
            )
            val raw = TrackingRawFrameBodyChannel()
            val authorityClosed = CountDownLatch(1)
            val operations = ManagerTestSecureSessionOperations(
                onClose = authorityClosed::countDown,
            )
            var legacyPeerCalls = 0
            var composedChannel: RuntimeProtocolChannel? = null
            val manager = productionManager(
                session = session,
                rawConnector = RuntimeRawRouteConnector { _, _ -> raw },
                composer = RuntimeProductionChannelComposer { _, rawLease ->
                    rawLease.composeForTest(operations).also {
                        composedChannel = it.channel
                    }
                },
                onLegacyPeerConnect = { legacyPeerCalls += 1 },
                afterProductionCommitBeforeReturnForTesting = {
                    currentCoroutineContext()[Job]?.cancel(cancellation)
                },
            )

            val failure = assertThrows(CancellationException::class.java) {
                runBlocking {
                    if (returnRoute) {
                        manager.connectWithRoute(RuntimeConnectionTarget(identity = identity))
                    } else {
                        manager.connect(RuntimeConnectionTarget(identity = identity))
                    }
                }
            }

            assertSame(cancellation, failure)
            assertEquals(1, raw.closeCount)
            assertTrue(authorityClosed.await(5, TimeUnit.SECONDS))
            assertTrue(composedChannel?.isConnected == false)
            assertEquals(0, legacyPeerCalls)
        }
    }

    @Test
    fun successfulPublicDeliverySurvivesLaterAcquisitionJobCancellationForBothApis() =
        runBlocking {
            listOf(false, true).forEach { returnRoute ->
                val session = productionPeerSession()
                val identity = pairedIdentity(
                    fingerprint = session.transcript.runtimeIdentityFingerprint,
                )
                val raw = TrackingRawFrameBodyChannel()
                val authorityClosed = CountDownLatch(1)
                val operations = ManagerTestSecureSessionOperations(
                    onClose = authorityClosed::countDown,
                )
                var legacyPeerCalls = 0
                val manager = productionManager(
                    session = session,
                    rawConnector = RuntimeRawRouteConnector { _, _ -> raw },
                    composer = RuntimeProductionChannelComposer { _, rawLease ->
                        rawLease.composeForTest(operations)
                    },
                    onLegacyPeerConnect = { legacyPeerCalls += 1 },
                )
                val delivered = CompletableDeferred<RuntimeProtocolChannel>()
                val retainAcquisitionJob = CompletableDeferred<Unit>()
                val acquisition = async(Dispatchers.Default) {
                    val channel = if (returnRoute) {
                        manager.connectWithRoute(
                            RuntimeConnectionTarget(identity = identity),
                        ).channel
                    } else {
                        manager.connect(RuntimeConnectionTarget(identity = identity))
                    }
                    delivered.complete(channel)
                    retainAcquisitionJob.await()
                }
                var channel: RuntimeProtocolChannel? = null

                try {
                    channel = withTimeout(5_000) { delivered.await() }
                    assertTrue(channel.isConnected)
                    assertEquals(0, raw.closeCount)

                    acquisition.cancel(
                        CancellationException("cancel acquisition after successful transfer"),
                    )
                    withTimeout(5_000) { acquisition.join() }

                    assertTrue(acquisition.isCancelled)
                    assertTrue(channel.isConnected)
                    assertEquals(0, raw.closeCount)
                    assertEquals(1L, authorityClosed.count)
                    assertEquals(0, legacyPeerCalls)

                    channel.close()
                    assertEquals(1, raw.closeCount)
                    assertTrue(authorityClosed.await(5, TimeUnit.SECONDS))
                } finally {
                    acquisition.cancel()
                    channel?.close()
                }
            }
        }

    @Test
    fun productionCompositionDeadlineClosesLeaseWhileComposerBlocksAfterCompose() = runBlocking {
        val session = productionPeerSession()
        val identity = pairedIdentity(fingerprint = session.transcript.runtimeIdentityFingerprint)
        val raw = TrackingRawFrameBodyChannel()
        val composed = CountDownLatch(1)
        val releaseComposer = CountDownLatch(1)
        val composerReturned = CountDownLatch(1)
        val manager = productionManager(
            session = session,
            rawConnector = RuntimeRawRouteConnector { _, _ -> raw },
            composer = RuntimeProductionChannelComposer { _, rawLease ->
                val composition = rawLease.composeForTest()
                composed.countDown()
                try {
                    while (true) {
                        try {
                            releaseComposer.await()
                            break
                        } catch (_: InterruptedException) {
                            // Deliberately non-cooperative with task cancellation.
                        }
                    }
                    composition
                } finally {
                    composerReturned.countDown()
                }
            },
            compositionHandshakeBudgetMillis = 250L,
        )
        try {
            val failure = runCatching {
                withTimeout(5_000) {
                    manager.connect(
                        target = RuntimeConnectionTarget(identity = identity),
                        timeoutMillis = 250,
                    )
                }
            }.exceptionOrNull()
            assertTrue(composed.await(0, TimeUnit.MILLISECONDS))
            assertTrue(failure is RuntimeConnectionFailure)
            failure as RuntimeConnectionFailure
            assertEquals(
                RuntimeConnectionFailureReason.ProductionSessionSecurityRejected,
                failure.reason,
            )
            assertTrue(failure.cause is IOException)
            assertTrue(failure.cause?.message?.contains("500 ms") == true)
            assertEquals(1, raw.closeCount)
        } finally {
            releaseComposer.countDown()
        }
        assertTrue(composerReturned.await(5, TimeUnit.SECONDS))
    }

    @Test
    fun deadlineRetainsAndClosesAdapterDuringNonCooperativeHandshake() = runBlocking {
        val session = productionPeerSession()
        val identity = pairedIdentity(fingerprint = session.transcript.runtimeIdentityFingerprint)
        val raw = NonCooperativeHandshakeRawFrameBodyChannel()
        val authorityClosed = CountDownLatch(1)
        val composerExited = CountDownLatch(1)
        val operations = ManagerTestSecureSessionOperations(
            onClose = authorityClosed::countDown,
        )
        val manager = productionManager(
            session = session,
            rawConnector = RuntimeRawRouteConnector { _, _ -> raw },
            composer = RuntimeProductionChannelComposer { _, rawLease ->
                try {
                    rawLease.composeForTest(operations)
                } finally {
                    composerExited.countDown()
                }
            },
            compositionHandshakeBudgetMillis = 250L,
        )
        try {
            val failure = runCatching {
                withTimeout(5_000) {
                    manager.connect(
                        target = RuntimeConnectionTarget(identity = identity),
                        timeoutMillis = 250,
                    )
                }
            }.exceptionOrNull()
            assertTrue(raw.receiveStarted.await(0, TimeUnit.MILLISECONDS))
            assertTrue(failure is RuntimeConnectionFailure)
            failure as RuntimeConnectionFailure
            assertEquals(
                RuntimeConnectionFailureReason.ProductionSessionSecurityRejected,
                failure.reason,
            )
            assertTrue(failure.cause is IOException)
            assertTrue(failure.cause?.message?.contains("500 ms") == true)
            assertEquals(1, raw.closeCount)
            assertTrue(authorityClosed.await(5, TimeUnit.SECONDS))
        } finally {
            raw.releaseReceive.countDown()
        }
        assertTrue(composerExited.await(5, TimeUnit.SECONDS))
        assertEquals(1, raw.closeCount)
        assertTrue(raw.lateBody.all { it == 0.toByte() })
    }

    @Test
    fun productionComposerCannotInvokeBoundRawConnectorTwice() {
        val session = productionPeerSession()
        val identity = pairedIdentity(fingerprint = session.transcript.runtimeIdentityFingerprint)
        var delegateCalls = 0
        val manager = RuntimeConnectionManager(
            connector = RuntimeTransportConnector { _, _, _ ->
                error("Production peer route must not use direct TCP")
            },
            routeResolver = RuntimeRouteResolver { emptyList() },
            remoteRoutePreparer = RuntimeRemoteRoutePreparer { pairedRuntime ->
                listOf(
                    PreparedRemoteRuntimeRoute.PeerToPeer(
                        identity = pairedRuntime,
                        sessionId = session.expectedSessionId,
                        security = securityContext("production-p2p-session"),
                        productionSession = session,
                    )
                )
            },
            productionRawRouteConnector = RuntimeRawRouteConnector { _, _ ->
                delegateCalls += 1
                TrackingRawFrameBodyChannel()
            },
            productionChannelComposer = RuntimeProductionChannelComposer { _, rawLease ->
                rawLease.composeForTest()
                rawLease.composeForTest()
            },
        )

        val failure = assertThrows(RuntimeConnectionFailure::class.java) {
            runBlocking {
                manager.connect(RuntimeConnectionTarget(identity = identity))
            }
        }

        assertEquals(RuntimeConnectionFailureReason.ProductionSessionSecurityRejected, failure.reason)
        assertEquals(1, delegateCalls)
        assertTrue(failure.attemptFailures.single().cause.message?.contains("already composed") == true)
    }

    @Test
    fun productionComposerCannotSubstituteAPlaintextChannelForTheCoreAdapter() = runBlocking {
        val session = productionPeerSession()
        val identity = pairedIdentity(fingerprint = session.transcript.runtimeIdentityFingerprint)
        var peerCalls = 0
        val manager = RuntimeConnectionManager(
            connector = RuntimeTransportConnector { _, _, _ ->
                error("Production peer route must not use direct TCP")
            },
            routeResolver = RuntimeRouteResolver { emptyList() },
            remoteRoutePreparer = RuntimeRemoteRoutePreparer { pairedRuntime ->
                listOf(
                    PreparedRemoteRuntimeRoute.PeerToPeer(
                        identity = pairedRuntime,
                        sessionId = session.expectedSessionId,
                        security = securityContext("production-p2p-session"),
                        productionSession = session,
                    )
                )
            },
            peerToPeerConnector = RuntimePeerToPeerConnector { _, _ ->
                peerCalls += 1
                TestRuntimeProtocolChannel
            },
            productionRawRouteConnector = RuntimeRawRouteConnector { _, _ ->
                TrackingRawFrameBodyChannel()
            },
            productionChannelComposer = RuntimeProductionChannelComposer { _, rawLease ->
                rawLease.composeForTest()
            },
        )

        val result = manager.connectWithRoute(RuntimeConnectionTarget(identity = identity))

        assertEquals(0, peerCalls)
        assertTrue(result.channel is ProductionRuntimeSecureChannelAdapter)
        assertTrue(result.channel !== TestRuntimeProtocolChannel)
        result.channel.close()
    }

    @Test
    fun requiredProductionSessionRejectsEveryLegacyRouteBeforeConnectorInvocation() {
        val identity = pairedIdentity()
        var directCalls = 0
        var peerCalls = 0
        val manager = RuntimeConnectionManager(
            connector = RuntimeTransportConnector { _, _, _ ->
                directCalls += 1
                TestRuntimeProtocolChannel
            },
            routeResolver = RuntimeRouteResolver {
                listOf(
                    RuntimeRouteCandidate.DirectTcp(
                        hint = RuntimeEndpointHint(
                            host = "192.168.1.40",
                            port = 43170,
                            source = RuntimeEndpointSource.BonjourDiscovery,
                        ),
                        source = RuntimeRouteSource.FreshDiscovery,
                    )
                )
            },
            remoteRoutePreparer = RuntimeRemoteRoutePreparer { pairedRuntime ->
                listOf(
                    PreparedRemoteRuntimeRoute.PeerToPeer(
                        identity = pairedRuntime,
                        sessionId = "legacy-p2p-session",
                        security = securityContext("legacy-p2p-session"),
                    )
                )
            },
            peerToPeerConnector = RuntimePeerToPeerConnector { _, _ ->
                peerCalls += 1
                TestRuntimeProtocolChannel
            },
        )

        val failure = assertThrows(RuntimeConnectionFailure::class.java) {
            runBlocking {
                manager.connect(
                    RuntimeConnectionTarget(
                        identity = identity,
                        requiresProductionSession = true,
                    )
                )
            }
        }

        assertEquals(RuntimeConnectionFailureReason.NoConnectableRoute, failure.reason)
        assertTrue(failure.routeRejections.isNotEmpty())
        assertTrue(
            failure.routeRejections.all {
                it.reason == RuntimeRouteRejectionReason.ProductionSessionRequired
            }
        )
        assertEquals(0, directCalls)
        assertEquals(0, peerCalls)
    }

    /** Core-internal test seam: production still builds the same concrete raw-bound adapter. */
    private suspend fun RuntimeProductionRawRouteLease.composeForTest(
        operations: ProductionRuntimeSecureSessionOperations = ManagerTestSecureSessionOperations(),
    ): RuntimeProductionChannelComposition =
        (this as ManagedRuntimeProductionRawRouteLease).composeForTesting(
            operations = operations,
            scope = productionTestScope,
        )

    private fun pairedIdentity(
        routeToken: String? = null,
        fingerprint: String = "fingerprint",
    ): PairedRuntimeIdentity {
        return PairedRuntimeIdentity(
            deviceId = "runtime-1",
            name = "AetherLink",
            fingerprint = fingerprint,
            routeToken = routeToken,
        )
    }

    private fun productionManager(
        session: PreparedProductionSecureSession,
        rawConnector: RuntimeRawRouteConnector,
        composer: RuntimeProductionChannelComposer,
        onLegacyPeerConnect: () -> Unit = {},
        routeExpiresAtEpochMillis: Long = 1_893_456_000_000,
        currentTimeMillis: () -> Long = { System.currentTimeMillis() },
        compositionHandshakeBudgetMillis: Long =
            RuntimeConnectionManager.DEFAULT_PRODUCTION_COMPOSITION_HANDSHAKE_BUDGET_MILLIS,
        afterProductionCommitBeforeReturnForTesting:
            (suspend (RuntimeProtocolChannel) -> Unit)? = null,
    ): RuntimeConnectionManager = RuntimeConnectionManager(
        connector = RuntimeTransportConnector { _, _, _ ->
            error("Production peer route must not use direct TCP")
        },
        routeResolver = RuntimeRouteResolver { emptyList() },
        remoteRoutePreparer = RuntimeRemoteRoutePreparer { pairedRuntime ->
            listOf(
                PreparedRemoteRuntimeRoute.PeerToPeer(
                    identity = pairedRuntime,
                    sessionId = session.expectedSessionId,
                    security = securityContext(
                        "production-p2p-session",
                        routeExpiresAtEpochMillis,
                    ),
                    productionSession = session,
                ),
            )
        },
        peerToPeerConnector = RuntimePeerToPeerConnector { _, _ ->
            onLegacyPeerConnect()
            TestRuntimeProtocolChannel
        },
        relayConnector = null,
        productionRawRouteConnector = rawConnector,
        productionChannelComposer = composer,
        currentTimeMillis = currentTimeMillis,
        productionCompositionHandshakeBudgetMillis = compositionHandshakeBudgetMillis,
        afterProductionCommitBeforeReturnForTesting =
            afterProductionCommitBeforeReturnForTesting,
        _productionBridgeMarker = Unit,
    )

    private fun productionRequest(
        session: PreparedProductionSecureSession,
        connectionGeneration: Long,
    ): RuntimeProductionConnectionRequest {
        val identity = pairedIdentity(fingerprint = session.transcript.runtimeIdentityFingerprint)
        val prepared = PreparedRemoteRuntimeRoute.PeerToPeer(
            identity = identity,
            sessionId = session.expectedSessionId,
            security = securityContext("production-p2p-session"),
            productionSession = session,
        )
        return RuntimeProductionConnectionRequest(
            identity = identity,
            route = RuntimeRouteCandidate.PeerToPeer(
                identity = identity,
                preparedRoute = prepared,
            ),
            session = session,
            connectionGeneration = connectionGeneration,
            timeoutMillis = 1_250,
        )
    }

    private fun productionPeerSession(): PreparedProductionSecureSession {
        val pairBindingDigest = "102132435465768798a9bacbdcedfe0f102132435465768798a9bacbdcedfe0f"
        val route = P2pDirectRouteAuthorization(
            pairBindingDigest = pairBindingDigest,
            pairEpoch = 9uL,
            generation = 7uL,
            candidatePairDigest = "5".repeat(64),
            pathValidationReceiptDigest = "6".repeat(64),
            publishCapabilityDigest = "3".repeat(64),
            fetchCapabilityDigest = "4".repeat(64),
        )
        return productionSession(route)
    }

    private fun productionRelaySession(): PreparedProductionSecureSession {
        val route = TurnRelayRouteAuthorization(
            pairBindingDigest =
                "102132435465768798a9bacbdcedfe0f102132435465768798a9bacbdcedfe0f",
            pairEpoch = 9uL,
            generation = 7uL,
            leaseDigest = "7".repeat(64),
            allocationDigest = "8".repeat(64),
            pathValidationReceiptDigest = "9".repeat(64),
        )
        return productionSession(route)
    }

    private fun productionSession(
        route: ProductionRouteAuthorization,
    ): PreparedProductionSecureSession {
        val transcript = ProductionSecureSessionTranscript(
            sessionId = "00112233445566778899aabbccddeeff",
            pairBindingDigest = route.pairBindingDigest,
            pairEpoch = route.pairEpoch,
            clientIdentityFingerprint = "a".repeat(64),
            runtimeIdentityFingerprint = "b".repeat(64),
            clientEphemeralPublicKey = (
                "046b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296" +
                    "4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5"
                ).lowerHexBytes(),
            runtimeEphemeralPublicKey = (
                "047cf27b188d034f7e8a52380304b51ac3c08969e277f21b35a60b48fc476699780" +
                    "7775510db8ed040293d9ac69f7430dbba7dade63ce982299e04b79d227873d1"
                ).lowerHexBytes(),
            clientNonce = "0123456789abcdeffedcba9876543210",
            runtimeNonce = "ffeeddccbbaa99887766554433221100",
            generation = requireNotNull(route.generation),
            serviceConfigVersion = 3uL,
            keysetVersion = 4uL,
            revocationCounter = 2uL,
            routeAuthorizationKind = route.kind,
            routeAuthorizationDigest = ProductionSecureSessionCodec.digest(route).lowerHex(),
        )
        return PreparedProductionSecureSession(
            transcript,
            route,
            expectedObject7Object26BindingId = "c".repeat(64),
        )
    }

    private fun String.lowerHexBytes(): ByteArray {
        require(length % 2 == 0)
        return ByteArray(length / 2) { index ->
            substring(index * 2, index * 2 + 2).toInt(16).toByte()
        }
    }

    private fun ByteArray.lowerHex(): String =
        joinToString("") { byte -> "%02x".format(byte.toInt() and 0xff) }

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

    private class ManagerTestSecureSessionOperations(
        bindingId: String = "c".repeat(64),
        sessionId: String = "00112233445566778899aabbccddeeff",
        private val onClose: () -> Unit = {},
    ) : ProductionRuntimeSecureSessionOperations {
        override val descriptor = ProductionC1AuthorityBoundSecureSessionDescriptor(
            sessionId = sessionId,
            expiresAtMs = ULong.MAX_VALUE,
            object7Object26KdfBindingDigestHex = bindingId,
        )

        override fun installTerminalObserver(observer: () -> Unit) = Unit

        override suspend fun sendLocalConfirmationAndMark(send: suspend (ByteArray) -> Unit) {
            send(als1(29))
        }

        override suspend fun acceptPeerConfirmation(encodedConfirmation: ByteArray) = Unit

        override suspend fun activate() = Unit

        override suspend fun sealApplicationAndSend(
            plaintext: ByteArray,
            send: suspend (ByteArray) -> Unit,
        ): ProductionC1AuthorityBoundRecordPublication =
            error("Manager test secure session does not seal application records")

        override suspend fun sealKeyUpdateAndSend(
            send: suspend (ByteArray) -> Unit,
        ): ProductionC1AuthorityBoundRecordPublication =
            error("Manager test secure session does not seal key updates")

        override suspend fun <Value> openAndPublish(
            encodedRecord: ByteArray,
            publish: suspend (
                plaintext: ByteArray,
                contentType: ProductionSecureSessionRecordContentType,
                keyUpdateRequired: Boolean,
                terminalAfterRecord: Boolean,
            ) -> Value,
        ): Value = error("Manager test secure session does not open records")

        override suspend fun close() = onClose()
    }

    private class NonCooperativeHandshakeRawFrameBodyChannel : RuntimeRawFrameBodyChannel {
        val receiveStarted = CountDownLatch(1)
        val releaseReceive = CountDownLatch(1)
        private val closes = AtomicInteger(0)
        val lateBody = als1(29)

        val closeCount: Int
            get() = closes.get()

        override val isConnected: Boolean
            get() = closeCount == 0

        override suspend fun sendFrameBody(body: ByteArray) {
            check(isConnected) { "Non-cooperative raw channel is closed" }
        }

        override suspend fun receiveFrameBody(): ByteArray {
            receiveStarted.countDown()
            while (true) {
                try {
                    releaseReceive.await()
                    break
                } catch (_: InterruptedException) {
                    // Deliberately ignores interruption and close until the test releases it.
                }
            }
            return lateBody
        }

        override fun close() {
            closes.compareAndSet(0, 1)
        }
    }

    private class TrackingRawFrameBodyChannel : RuntimeRawFrameBodyChannel {
        private val incoming = Channel<ByteArray>(Channel.UNLIMITED).apply {
            trySend(als1(29)).getOrThrow()
        }
        var closeCount: Int = 0
            private set

        override val isConnected: Boolean
            get() = closeCount == 0

        override suspend fun sendFrameBody(body: ByteArray) {
            check(isConnected) { "Tracking raw channel is closed" }
        }

        override suspend fun receiveFrameBody(): ByteArray = incoming.receive()

        override fun close() {
            if (closeCount != 0) return
            closeCount = 1
            incoming.close()
        }
    }

    private companion object {
        fun als1(objectType: Int, marker: Int = 1): ByteArray = byteArrayOf(
            'A'.code.toByte(),
            'L'.code.toByte(),
            'S'.code.toByte(),
            '1'.code.toByte(),
            objectType.toByte(),
            1,
            marker.toByte(),
        )
    }
}
