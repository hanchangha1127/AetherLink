package com.localagentbridge.android.core.transport

import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import java.util.concurrent.CancellationException
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
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
