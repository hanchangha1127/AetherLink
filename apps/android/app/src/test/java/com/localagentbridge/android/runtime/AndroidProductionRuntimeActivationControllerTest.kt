package com.localagentbridge.android.runtime

import android.app.Application
import androidx.lifecycle.viewModelScope
import androidx.test.core.app.ApplicationProvider
import com.localagentbridge.android.core.pairing.DeviceIdentityFactory
import com.localagentbridge.android.core.pairing.PairingStore
import com.localagentbridge.android.core.pairing.ProductionC1EndpointGrantCompoundCommitToken
import com.localagentbridge.android.core.pairing.TrustedRuntime
import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import com.localagentbridge.android.core.protocol.p2pnat.*
import com.localagentbridge.android.core.transport.*
import java.io.IOException
import java.lang.reflect.InvocationTargetException
import java.lang.reflect.Proxy
import java.nio.file.Files
import java.nio.file.Path
import java.security.KeyFactory
import java.security.PublicKey
import java.security.spec.X509EncodedKeySpec
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference
import kotlin.coroutines.intrinsics.COROUTINE_SUSPENDED
import kotlin.coroutines.intrinsics.suspendCoroutineUninterceptedOrReturn
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.json.Json
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.shadows.ShadowLog

@RunWith(RobolectricTestRunner::class)
@OptIn(ExperimentalCoroutinesApi::class)
class AndroidProductionRuntimeActivationControllerTest {
    @Test
    fun closedControllerRejectsBeforeDurableEndpointAdmission() = runTest {
        val fixture = createFixture()
        val raw = TrackingRawChannel()
        val endpoint = AndroidProductionPreconnectedRawEndpointClaim.own(raw)
        val clientKey = fixture.ephemeralKey("clientEphemeral")
        val controller = fixture.controller()
        try {
            controller.close()

            val failure = runCatching {
                controller.publishVerifiedAttempt(
                    fixture.identity,
                    ENDPOINT_ADMISSION_ID,
                    fixture.binding,
                    clientKey,
                    endpoint,
                )
            }.exceptionOrNull()

            assertTrue(failure is IllegalStateException)
            assertTrue(clientKey.isConsumedOrClosed)
            assertTrue(endpoint.isDiscardedForTesting)
            assertEquals(1, raw.closeCalls.get())
            // The same admission must still be fresh. A replay here would prove that the closed
            // controller wrote a durable marker before rejecting publication.
            fixture.store.admitVerifiedProductionC1EndpointGrant(
                expectedRuntimeDeviceId = fixture.identity.deviceId,
                expectedRuntimeFingerprint = requireNotNull(fixture.identity.fingerprint),
                expectedRuntimePublicKey = requireNotNull(fixture.identity.publicKeyBase64),
                admissionId = ENDPOINT_ADMISSION_ID,
                binding = fixture.binding,
            )
        } finally {
            runCatching { controller.close() }
            fixture.store.forgetRuntime()
        }
    }

    @Test
    fun closeRevokesOwnedResourcesWhileDurableAdmissionIsSuspended() = runTest {
        val fixture = createFixture()
        val raw = TrackingRawChannel()
        val endpoint = AndroidProductionPreconnectedRawEndpointClaim.own(raw)
        val clientKey = fixture.ephemeralKey("clientEphemeral")
        val admissionReady = CountDownLatch(1)
        val releaseAdmission = CountDownLatch(1)
        val controller = AndroidProductionRuntimeActivationController(
            pairingStore = fixture.store,
            currentTimeMillis = fixture.clock,
            endpointGrantAdmitter = { deviceId, fingerprint, publicKey, admissionId, binding ->
                fixture.store.admitVerifiedProductionC1EndpointGrant(
                    expectedRuntimeDeviceId = deviceId,
                    expectedRuntimeFingerprint = fingerprint,
                    expectedRuntimePublicKey = publicKey,
                    admissionId = admissionId,
                    binding = binding,
                ).also {
                    admissionReady.countDown()
                    check(releaseAdmission.await(5, TimeUnit.SECONDS)) {
                        "Timed out waiting to resume durable admission"
                    }
                }
            },
        )
        var publication: kotlinx.coroutines.Deferred<Result<Unit>>? = null
        try {
            publication = async(Dispatchers.Default) {
                runCatching {
                    controller.publishVerifiedAttempt(
                        fixture.identity,
                        ENDPOINT_ADMISSION_ID,
                        fixture.binding,
                        clientKey,
                        endpoint,
                    )
                }
            }
            assertTrue(withContext(Dispatchers.IO) { admissionReady.await(5, TimeUnit.SECONDS) })

            val closeResult = withContext(Dispatchers.Default) {
                withTimeout(2_000L) { runCatching { controller.close() } }
            }
            assertNull(closeResult.exceptionOrNull()?.stackTraceToString(), closeResult.exceptionOrNull())
            assertTrue(controller.isClosedForTesting)
            assertTrue(clientKey.isConsumedOrClosed)
            assertTrue(endpoint.isDiscardedForTesting)
            assertEquals(1, raw.closeCalls.get())

            releaseAdmission.countDown()
            val publicationFailure = withContext(Dispatchers.Default) {
                withTimeout(5_000L) { publication.await().exceptionOrNull() }
            }
            assertTrue(publicationFailure is IllegalStateException)
            assertEquals(1, raw.closeCalls.get())
            assertTrue(controller.prepareRemoteRoutes(fixture.identity).isEmpty())
        } finally {
            releaseAdmission.countDown()
            publication?.let { pending ->
                withContext(Dispatchers.Default) {
                    withTimeout(5_000L) { pending.await() }
                }
            }
            runCatching { controller.close() }
            fixture.store.forgetRuntime()
        }
    }

    @Test
    fun wrongRawRouteDoesNotConsumeExactPreconnectedEndpoint() = runTest {
        val fixture = createFixture()
        val raw = TrackingRawChannel()
        val endpoint = AndroidProductionPreconnectedRawEndpointClaim.own(raw)
        val clientKey = fixture.ephemeralKey("clientEphemeral")
        val controller = fixture.controller()
        try {
            controller.publishVerifiedAttempt(
                fixture.identity,
                ENDPOINT_ADMISSION_ID,
                fixture.binding,
                clientKey,
                endpoint,
            )
            val route = controller.prepareRemoteRoutes(fixture.identity).single()
                as PreparedRemoteRuntimeRoute.PeerToPeer
            val exactCandidate = RuntimeRouteCandidate.PeerToPeer(
                identity = fixture.identity,
                preparedRoute = route,
            )
            val request = RuntimeProductionConnectionRequest(
                identity = fixture.identity,
                route = exactCandidate,
                session = requireNotNull(route.productionSession),
                connectionGeneration = 1L,
                timeoutMillis = 5_000,
            )
            controller.claim(request)
            val copiedRoute = route.copy()
            val wrongCandidate = RuntimeRouteCandidate.PeerToPeer(
                identity = fixture.identity,
                preparedRoute = copiedRoute,
            )

            val wrong = runCatching { controller.connect(wrongCandidate, 5_000) }.exceptionOrNull()

            assertTrue(wrong is IllegalStateException)
            assertFalse(endpoint.isTransferredForTesting)
            assertFalse(endpoint.isDiscardedForTesting)
            assertEquals(1, controller.claimedEndpointCountForTesting)
            assertSame(raw, controller.connect(exactCandidate, 5_000))
            assertTrue(endpoint.isTransferredForTesting)
            assertEquals(0, controller.claimedEndpointCountForTesting)
        } finally {
            controller.close()
            raw.close()
            fixture.store.forgetRuntime()
        }
        assertTrue(clientKey.isConsumedOrClosed)
    }

    @Test
    fun closeDiscardsUntransferredPlanKeyAndEndpoint() = runTest {
        val fixture = createFixture()
        val raw = TrackingRawChannel()
        val endpoint = AndroidProductionPreconnectedRawEndpointClaim.own(raw)
        val clientKey = fixture.ephemeralKey("clientEphemeral")
        val controller = fixture.controller()
        try {
            controller.publishVerifiedAttempt(
                fixture.identity,
                ENDPOINT_ADMISSION_ID,
                fixture.binding,
                clientKey,
                endpoint,
            )

            controller.close()

            assertTrue(controller.isClosedForTesting)
            assertTrue(clientKey.isConsumedOrClosed)
            assertTrue(endpoint.isDiscardedForTesting)
            assertEquals(1, raw.closeCalls.get())
            assertTrue(controller.prepareRemoteRoutes(fixture.identity).isEmpty())
        } finally {
            runCatching { controller.close() }
            fixture.store.forgetRuntime()
        }
    }

    @Test
    fun olderAdmissionCannotReplaceNewerPublishedGeneration() = runTest {
        val fixture = createFixture()
        val olderRaw = TrackingRawChannel()
        val olderEndpoint = AndroidProductionPreconnectedRawEndpointClaim.own(olderRaw)
        val olderKey = fixture.ephemeralKey("clientEphemeral")
        val newerRaw = TrackingRawChannel()
        val newerEndpoint = AndroidProductionPreconnectedRawEndpointClaim.own(newerRaw)
        val newerKey = fixture.ephemeralKey("clientEphemeral")
        val admittedToken = AtomicReference<ProductionC1EndpointGrantCompoundCommitToken>()
        val olderAdmissionReady = CountDownLatch(1)
        val releaseOlderAdmission = CountDownLatch(1)
        val controller = AndroidProductionRuntimeActivationController(
            pairingStore = fixture.store,
            currentTimeMillis = fixture.clock,
            endpointGrantAdmitter = { deviceId, fingerprint, publicKey, admissionId, binding ->
                if (admissionId == ENDPOINT_ADMISSION_ID) {
                    fixture.store.admitVerifiedProductionC1EndpointGrant(
                        expectedRuntimeDeviceId = deviceId,
                        expectedRuntimeFingerprint = fingerprint,
                        expectedRuntimePublicKey = publicKey,
                        admissionId = admissionId,
                        binding = binding,
                    ).also { token ->
                        admittedToken.set(token)
                        olderAdmissionReady.countDown()
                        check(releaseOlderAdmission.await(5, TimeUnit.SECONDS)) {
                            "Timed out waiting to resume the older admission"
                        }
                    }
                } else {
                    check(olderAdmissionReady.await(5, TimeUnit.SECONDS)) {
                        "Older admission did not produce its durable token"
                    }
                    checkNotNull(admittedToken.get())
                }
            },
        )
        var olderPublication: kotlinx.coroutines.Deferred<Result<Unit>>? = null
        try {
            olderPublication = async(Dispatchers.Default) {
                runCatching {
                    controller.publishVerifiedAttempt(
                        fixture.identity,
                        ENDPOINT_ADMISSION_ID,
                        fixture.binding,
                        olderKey,
                        olderEndpoint,
                    )
                }
            }
            assertTrue(withContext(Dispatchers.IO) { olderAdmissionReady.await(5, TimeUnit.SECONDS) })

            val newerResult = withContext(Dispatchers.Default) {
                withTimeout(5_000L) {
                    runCatching {
                        controller.publishVerifiedAttempt(
                            fixture.identity,
                            REPLACEMENT_ENDPOINT_ADMISSION_ID,
                            fixture.binding,
                            newerKey,
                            newerEndpoint,
                        )
                    }
                }
            }
            assertNull(newerResult.exceptionOrNull()?.stackTraceToString(), newerResult.exceptionOrNull())
            assertEquals(1, controller.prepareRemoteRoutes(fixture.identity).size)
            assertFalse(newerEndpoint.isDiscardedForTesting)
            assertEquals(0, newerRaw.closeCalls.get())

            releaseOlderAdmission.countDown()
            val olderFailure = withContext(Dispatchers.Default) {
                withTimeout(5_000L) { olderPublication.await().exceptionOrNull() }
            }
            assertTrue(olderFailure is IllegalStateException)
            assertTrue(olderKey.isConsumedOrClosed)
            assertTrue(olderEndpoint.isDiscardedForTesting)
            assertEquals(1, olderRaw.closeCalls.get())
            assertEquals(1, controller.prepareRemoteRoutes(fixture.identity).size)
            assertFalse(newerEndpoint.isDiscardedForTesting)
            assertEquals(1, controller.pendingEndpointCountForTesting)
        } finally {
            releaseOlderAdmission.countDown()
            olderPublication?.let { publication ->
                withContext(Dispatchers.Default) {
                    withTimeout(5_000L) { publication.await() }
                }
            }
            runCatching { controller.close() }
            fixture.store.forgetRuntime()
        }
        assertTrue(newerKey.isConsumedOrClosed)
        assertTrue(newerEndpoint.isDiscardedForTesting)
        assertEquals(1, newerRaw.closeCalls.get())
    }

    @Test
    fun displacedEndpointCloseCanWaitForControllerCloseWithoutDeadlock() = runTest {
        val fixture = createFixture()
        val displacedRaw = ControllerCloseAwaitingRawChannel()
        val displacedEndpoint = AndroidProductionPreconnectedRawEndpointClaim.own(displacedRaw)
        val displacedKey = fixture.ephemeralKey("clientEphemeral")
        val replacementRaw = TrackingRawChannel()
        val replacementEndpoint = AndroidProductionPreconnectedRawEndpointClaim.own(replacementRaw)
        val replacementKey = fixture.ephemeralKey("clientEphemeral")
        var admittedToken: ProductionC1EndpointGrantCompoundCommitToken? = null
        val controller = AndroidProductionRuntimeActivationController(
            pairingStore = fixture.store,
            currentTimeMillis = fixture.clock,
            endpointGrantAdmitter = { deviceId, fingerprint, publicKey, admissionId, binding ->
                admittedToken ?: fixture.store.admitVerifiedProductionC1EndpointGrant(
                    expectedRuntimeDeviceId = deviceId,
                    expectedRuntimeFingerprint = fingerprint,
                    expectedRuntimePublicKey = publicKey,
                    admissionId = admissionId,
                    binding = binding,
                ).also { admittedToken = it }
            },
        )
        try {
            controller.publishVerifiedAttempt(
                fixture.identity,
                ENDPOINT_ADMISSION_ID,
                fixture.binding,
                displacedKey,
                displacedEndpoint,
            )
            val replacement = async(Dispatchers.Default) {
                runCatching {
                    controller.publishVerifiedAttempt(
                        fixture.identity,
                        REPLACEMENT_ENDPOINT_ADMISSION_ID,
                        fixture.binding,
                        replacementKey,
                        replacementEndpoint,
                    )
                }
            }
            assertTrue(withContext(Dispatchers.IO) { displacedRaw.awaitCloseEntered() })

            val closeResult = withContext(Dispatchers.Default) {
                withTimeout(2_000L) {
                    runCatching { controller.close() }.also {
                        displacedRaw.signalControllerCloseReturned()
                    }
                }
            }
            assertNull(closeResult.exceptionOrNull()?.stackTraceToString(), closeResult.exceptionOrNull())
            val replacementFailure = withContext(Dispatchers.Default) {
                withTimeout(5_000L) { replacement.await().exceptionOrNull() }
            }

            assertTrue(replacementFailure is IllegalStateException)
            assertTrue(controller.isClosedForTesting)
            assertTrue(displacedKey.isConsumedOrClosed)
            assertTrue(displacedEndpoint.isDiscardedForTesting)
            assertTrue(replacementKey.isConsumedOrClosed)
            assertTrue(replacementEndpoint.isDiscardedForTesting)
            assertEquals(1, displacedRaw.closeCalls.get())
            assertEquals(1, replacementRaw.closeCalls.get())
            assertTrue(controller.prepareRemoteRoutes(fixture.identity).isEmpty())
        } finally {
            displacedRaw.signalControllerCloseReturned()
            runCatching { controller.close() }
            fixture.store.forgetRuntime()
        }
    }

    @Test
    fun failingDisplacedCloseKeepsReplacementPrivateAndLeavesNoRoute() = runTest {
        val fixture = createFixture()
        val displacedRaw = DelayedFailingCloseRawChannel()
        val displacedEndpoint = AndroidProductionPreconnectedRawEndpointClaim.own(displacedRaw)
        val displacedKey = fixture.ephemeralKey("clientEphemeral")
        val replacementRaw = TrackingRawChannel()
        val replacementEndpoint = AndroidProductionPreconnectedRawEndpointClaim.own(replacementRaw)
        val replacementKey = fixture.ephemeralKey("clientEphemeral")
        var admittedToken: ProductionC1EndpointGrantCompoundCommitToken? = null
        val controller = AndroidProductionRuntimeActivationController(
            pairingStore = fixture.store,
            currentTimeMillis = fixture.clock,
            endpointGrantAdmitter = { deviceId, fingerprint, publicKey, admissionId, binding ->
                admittedToken ?: fixture.store.admitVerifiedProductionC1EndpointGrant(
                    expectedRuntimeDeviceId = deviceId,
                    expectedRuntimeFingerprint = fingerprint,
                    expectedRuntimePublicKey = publicKey,
                    admissionId = admissionId,
                    binding = binding,
                ).also { admittedToken = it }
            },
        )
        try {
            controller.publishVerifiedAttempt(
                fixture.identity,
                ENDPOINT_ADMISSION_ID,
                fixture.binding,
                displacedKey,
                displacedEndpoint,
            )
            val replacement = async(Dispatchers.Default) {
                runCatching {
                    controller.publishVerifiedAttempt(
                        fixture.identity,
                        REPLACEMENT_ENDPOINT_ADMISSION_ID,
                        fixture.binding,
                        replacementKey,
                        replacementEndpoint,
                    )
                }
            }
            if (!withContext(Dispatchers.IO) { displacedRaw.awaitCloseEntered() }) {
                throw AssertionError(
                    "Replacement did not reach displaced endpoint cleanup",
                    replacement.await().exceptionOrNull(),
                )
            }

            val racedTransfer = withContext(Dispatchers.Default) {
                val route = controller.prepareRemoteRoutes(fixture.identity).singleOrNull()
                    as? PreparedRemoteRuntimeRoute.PeerToPeer
                    ?: return@withContext false
                val candidate = RuntimeRouteCandidate.PeerToPeer(
                    identity = fixture.identity,
                    preparedRoute = route,
                )
                val request = RuntimeProductionConnectionRequest(
                    identity = fixture.identity,
                    route = candidate,
                    session = requireNotNull(route.productionSession),
                    connectionGeneration = 1L,
                    timeoutMillis = 5_000,
                )
                controller.claim(request)
                controller.connect(candidate, 5_000)
                true
            }

            assertFalse(racedTransfer)
            assertFalse(replacementEndpoint.isTransferredForTesting)
            assertEquals(0, controller.pendingEndpointCountForTesting)
            assertEquals(0, controller.claimedEndpointCountForTesting)
            displacedRaw.releaseClose()

            val failure = replacement.await().exceptionOrNull()
            assertTrue(failure is IOException)
            assertTrue(controller.isClosedForTesting)
            assertTrue(displacedKey.isConsumedOrClosed)
            assertTrue(displacedEndpoint.isDiscardedForTesting)
            assertTrue(replacementKey.isConsumedOrClosed)
            assertTrue(replacementEndpoint.isDiscardedForTesting)
            assertEquals(1, displacedRaw.closeCalls.get())
            assertEquals(1, replacementRaw.closeCalls.get())
            assertTrue(controller.prepareRemoteRoutes(fixture.identity).isEmpty())
            assertEquals(0, controller.pendingEndpointCountForTesting)
            assertEquals(0, controller.claimedEndpointCountForTesting)
        } finally {
            displacedRaw.releaseClose()
            runCatching { controller.close() }
            replacementRaw.close()
            fixture.store.forgetRuntime()
        }
    }

    @Test
    fun injectedRawTransferDoesNotHoldControllerStateLock() = runTest {
        val fixture = createFixture()
        val raw = BlockingTransferRawChannel()
        val endpoint = AndroidProductionPreconnectedRawEndpointClaim.own(raw)
        val clientKey = fixture.ephemeralKey("clientEphemeral")
        val controller = fixture.controller()
        try {
            controller.publishVerifiedAttempt(
                fixture.identity,
                ENDPOINT_ADMISSION_ID,
                fixture.binding,
                clientKey,
                endpoint,
            )
            val route = controller.prepareRemoteRoutes(fixture.identity).single()
                as PreparedRemoteRuntimeRoute.PeerToPeer
            val candidate = RuntimeRouteCandidate.PeerToPeer(
                identity = fixture.identity,
                preparedRoute = route,
            )
            val request = RuntimeProductionConnectionRequest(
                identity = fixture.identity,
                route = candidate,
                session = requireNotNull(route.productionSession),
                connectionGeneration = 1L,
                timeoutMillis = 5_000,
            )
            controller.claim(request)
            val connection = async(Dispatchers.Default) {
                controller.connect(candidate, 5_000)
            }
            try {
                assertTrue(withContext(Dispatchers.IO) { raw.awaitTransferCheck() })
                val abandonment = async(Dispatchers.Default) {
                    controller.abandonClaim(request)
                }
                withContext(Dispatchers.Default) {
                    withTimeout(2_000L) { abandonment.await() }
                }
            } finally {
                raw.releaseTransferCheck()
            }

            assertSame(
                raw,
                withContext(Dispatchers.Default) {
                    withTimeout(2_000L) { connection.await() }
                },
            )
            assertTrue(endpoint.isTransferredForTesting)
        } finally {
            raw.releaseTransferCheck()
            runCatching { controller.close() }
            raw.close()
            fixture.store.forgetRuntime()
        }
        assertTrue(clientKey.isConsumedOrClosed)
    }

    @Test
    fun composerFailureBeforeRawComposeAbandonsEndpointWithoutLegacyFallback() = runTest {
        val fixture = createFixture()
        val raw = TrackingRawChannel()
        val endpoint = AndroidProductionPreconnectedRawEndpointClaim.own(raw)
        val controller = fixture.controller()
        val legacyCalls = AtomicInteger(0)
        try {
            controller.publishVerifiedAttempt(
                fixture.identity,
                ENDPOINT_ADMISSION_ID,
                fixture.binding,
                fixture.ephemeralKey("clientEphemeral"),
                endpoint,
            )
            fixture.store.forgetRuntime()
            val manager = RuntimeConnectionManager(
                connector = RuntimeTransportConnector { _, _, _ ->
                    legacyCalls.incrementAndGet()
                    error("legacy direct must not run")
                },
                routeResolver = RuntimeRouteResolver { emptyList() },
                remoteRoutePreparer = controller,
                peerToPeerConnector = RuntimePeerToPeerConnector { _, _ ->
                    legacyCalls.incrementAndGet()
                    error("legacy P2P must not run")
                },
                relayConnector = RuntimeRelayConnector { _, _ ->
                    legacyCalls.incrementAndGet()
                    error("legacy relay must not run")
                },
                productionRawRouteConnector = controller,
                productionChannelComposer = AndroidProductionRuntimeChannelComposer(
                    pairingStore = fixture.store,
                    claimSource = controller,
                ),
                currentTimeMillis = fixture.clock,
            )

            val failure = runCatching {
                manager.connectWithRoute(
                    RuntimeConnectionTarget(
                        identity = fixture.identity,
                        requiresProductionSession = true,
                    ),
                )
            }.exceptionOrNull()

            assertTrue(failure is RuntimeConnectionFailure)
            assertEquals(0, legacyCalls.get())
            assertTrue(endpoint.isDiscardedForTesting)
            assertEquals(1, raw.closeCalls.get())
            assertEquals(0, controller.claimedEndpointCountForTesting)
        } finally {
            controller.close()
            fixture.store.forgetRuntime()
        }
    }

    @Test
    fun managerComposesRealProductionActivationWithoutLegacyFallback() = runTest {
        val fixture = createFixture()
        val runtimeEngine = fixture.runtimeEngine()
        val raw = LoopbackProductionRawChannel(runtimeEngine, fixture.now)
        val endpoint = AndroidProductionPreconnectedRawEndpointClaim.own(raw)
        val controller = fixture.controller()
        val legacyCalls = AtomicInteger(0)
        var connectedChannel: RuntimeProtocolChannel? = null
        try {
            controller.publishVerifiedAttempt(
                fixture.identity,
                ENDPOINT_ADMISSION_ID,
                fixture.binding,
                fixture.ephemeralKey("clientEphemeral"),
                endpoint,
            )
            val manager = RuntimeConnectionManager(
                connector = RuntimeTransportConnector { _, _, _ ->
                    legacyCalls.incrementAndGet()
                    error("legacy direct must not run")
                },
                routeResolver = RuntimeRouteResolver { emptyList() },
                remoteRoutePreparer = controller,
                peerToPeerConnector = RuntimePeerToPeerConnector { _, _ ->
                    legacyCalls.incrementAndGet()
                    error("legacy P2P must not run")
                },
                relayConnector = RuntimeRelayConnector { _, _ ->
                    legacyCalls.incrementAndGet()
                    error("legacy relay must not run")
                },
                productionRawRouteConnector = controller,
                productionChannelComposer = AndroidProductionRuntimeChannelComposer(
                    pairingStore = fixture.store,
                    claimSource = controller,
                ),
                currentTimeMillis = fixture.clock,
            )

            val outcome = withContext(Dispatchers.Default) {
                runCatching {
                    manager.connectWithRoute(
                        RuntimeConnectionTarget(
                            identity = fixture.identity,
                            requiresProductionSession = true,
                        ),
                    )
                }
            }
            assertNull(outcome.exceptionOrNull()?.stackTraceToString(), outcome.exceptionOrNull())
            val connection = outcome.getOrThrow()
            connectedChannel = connection.channel
            assertEquals(RuntimeActiveRouteKind.PeerToPeer, connection.route.activeRouteKind())
            assertEquals(0, legacyCalls.get())
            assertTrue(endpoint.isTransferredForTesting)
            assertTrue(raw.handshakeCompleted.get())
        } finally {
            connectedChannel?.close()
            raw.close()
            runCatching { controller.close() }
            fixture.store.forgetRuntime()
        }
    }

    @Test
    fun viewModelClearCompletesAfterThrowingControllerCloseWithoutLoggingThrowable() = runTest {
        Dispatchers.setMain(Dispatchers.Default)
        val fixture = createFixture()
        val sensitiveFailure = "injected-sensitive-route-token-must-not-be-logged"
        val raw = DelayedFailingCloseRawChannel(sensitiveFailure)
        val endpoint = AndroidProductionPreconnectedRawEndpointClaim.own(raw)
        val controller = fixture.controller()
        val lifecycle = TrackingLifecycleCallbacksRegistrar()
        val discoveredPeers = MutableStateFlow<List<DiscoveredRuntime>>(emptyList())
        var viewModel: RuntimeClientViewModel? = null
        try {
            controller.publishVerifiedAttempt(
                fixture.identity,
                ENDPOINT_ADMISSION_ID,
                fixture.binding,
                fixture.ephemeralKey("clientEphemeral"),
                endpoint,
            )
            val application = ApplicationProvider.getApplicationContext<Application>()
            val activeViewModel = RuntimeClientViewModel(
                application = application,
                dependencies = RuntimeClientViewModelDependencies(
                    json = Json {
                        ignoreUnknownKeys = true
                        explicitNulls = false
                        encodeDefaults = true
                    },
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ -> error("unused") },
                    relayConnector = RuntimeRelayConnector { _, _ -> error("unused") },
                    discovery = object : RuntimeDiscoverySource {
                        override fun discover() = discoveredPeers
                    },
                    trustedRuntimeStore = AndroidTrustedRuntimeStore(fixture.store),
                    deviceIdentityProvider = object : RuntimeDeviceIdentityProvider {
                        override suspend fun loadOrCreate() =
                            DeviceIdentityFactory.create("Controller teardown test client")
                    },
                    localDataStore = InMemoryRuntimeLocalDataStore(
                        PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = false),
                    ),
                    lifecycleCallbacksRegistrar = lifecycle,
                    currentTimeMillis = fixture.clock,
                    productionActivationController = controller,
                ),
            )
            viewModel = activeViewModel
            activeViewModel.startDiscovery()
            withContext(Dispatchers.Default) {
                withTimeout(5_000L) {
                    activeViewModel.state.firstMatching { it.isDiscovering }
                }
            }
            val scopeStarted = CompletableDeferred<Unit>()
            val scopeCancelled = CompletableDeferred<Unit>()
            activeViewModel.viewModelScope.launch {
                scopeStarted.complete(Unit)
                try {
                    awaitCancellation()
                } finally {
                    scopeCancelled.complete(Unit)
                }
            }
            withTimeout(5_000L) { scopeStarted.await() }
            raw.releaseClose()
            ShadowLog.clear()

            activeViewModel.clearWithReflection()

            withTimeout(5_000L) { scopeCancelled.await() }
            assertFalse(activeViewModel.state.value.isDiscovering)
            assertEquals(1, lifecycle.unregisterCalls.get())
            assertTrue(controller.isClosedForTesting)
            assertTrue(endpoint.isDiscardedForTesting)
            assertEquals(1, raw.closeCalls.get())
            val teardownLogs = ShadowLog.getLogsForTag("RuntimeClientVM").filter {
                it.msg.startsWith("Runtime client teardown completed")
            }
            assertEquals(1, teardownLogs.size)
            assertEquals(
                "Runtime client teardown completed with cleanup failure count=1",
                teardownLogs.single().msg,
            )
            assertNull(teardownLogs.single().throwable)
            assertFalse(teardownLogs.single().msg.contains(sensitiveFailure))
            viewModel = null
        } finally {
            raw.releaseClose()
            viewModel?.clearWithReflection()
            runCatching { controller.close() }
            fixture.store.forgetRuntime()
            Dispatchers.resetMain()
        }
    }

    @Test
    fun viewModelUsesRealProductionActivationWithoutCallingLegacyConnectors() = runTest {
        Dispatchers.setMain(Dispatchers.Default)
        val fixture = createFixture()
        val runtimeEngine = fixture.runtimeEngine()
        val raw = LoopbackProductionRawChannel(runtimeEngine, fixture.now)
        val endpoint = AndroidProductionPreconnectedRawEndpointClaim.own(raw)
        val controller = fixture.controller()
        val legacyCalls = AtomicInteger(0)
        var viewModel: RuntimeClientViewModel? = null
        try {
            controller.publishVerifiedAttempt(
                fixture.identity,
                ENDPOINT_ADMISSION_ID,
                fixture.binding,
                fixture.ephemeralKey("clientEphemeral"),
                endpoint,
            )
            val application = ApplicationProvider.getApplicationContext<Application>()
            viewModel = RuntimeClientViewModel(
                application = application,
                dependencies = RuntimeClientViewModelDependencies(
                    json = Json {
                        ignoreUnknownKeys = true
                        explicitNulls = false
                        encodeDefaults = true
                    },
                    transportClient = RuntimeTransportClient(),
                    transportConnector = RuntimeTransportConnector { _, _, _ ->
                        legacyCalls.incrementAndGet()
                        error("legacy direct must not run")
                    },
                    relayConnector = RuntimeRelayConnector { _, _ ->
                        legacyCalls.incrementAndGet()
                        error("legacy relay must not run")
                    },
                    peerToPeerConnector = RuntimePeerToPeerConnector { _, _ ->
                        legacyCalls.incrementAndGet()
                        error("legacy P2P must not run")
                    },
                    discovery = object : RuntimeDiscoverySource {
                        override fun discover() = flowOf(emptyList<DiscoveredRuntime>())
                    },
                    trustedRuntimeStore = AndroidTrustedRuntimeStore(fixture.store),
                    deviceIdentityProvider = object : RuntimeDeviceIdentityProvider {
                        override suspend fun loadOrCreate() =
                            DeviceIdentityFactory.create("Controller test client")
                    },
                    localDataStore = InMemoryRuntimeLocalDataStore(
                        PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = false),
                    ),
                    lifecycleCallbacksRegistrar = NoopLifecycleCallbacksRegistrar,
                    currentTimeMillis = fixture.clock,
                    productionActivationController = controller,
                ),
            )
            withContext(Dispatchers.Default) {
                withTimeout(5_000L) {
                    viewModel.state.firstMatching { it.trustedRuntime != null }
                }
            }

            viewModel.connectToTrustedRuntime()
            val connectedState = withContext(Dispatchers.Default) {
                withTimeout(10_000L) {
                    viewModel.state.firstMatching {
                        it.isConnected || (!it.isConnecting && it.error != null)
                    }
                }
            }

            assertTrue(
                "$connectedState endpointTransferred=${endpoint.isTransferredForTesting} " +
                    "handshakeCompleted=${raw.handshakeCompleted.get()} rawConnected=${raw.isConnected}",
                connectedState.isConnected,
            )
            assertEquals(RuntimeActiveRouteKind.PeerToPeer, connectedState.activeRouteKind)
            assertEquals(0, legacyCalls.get())
            assertTrue(endpoint.isTransferredForTesting)
            assertTrue(raw.handshakeCompleted.get())
            withContext(Dispatchers.Default) {
                withTimeout(5_000L) {
                    while (raw.applicationRecords.get() == 0) {
                        kotlinx.coroutines.yield()
                    }
                }
            }
            assertTrue(raw.applicationRecords.get() > 0)
        } finally {
            viewModel?.clearWithReflection()
            raw.close()
            runCatching { controller.close() }
            fixture.store.forgetRuntime()
            Dispatchers.resetMain()
        }
    }
}

private class TrackingRawChannel : RuntimeRawFrameBodyChannel {
    private val connected = AtomicBoolean(true)
    val closeCalls = AtomicInteger(0)

    override val isConnected: Boolean get() = connected.get()

    override suspend fun sendFrameBody(body: ByteArray) {
        check(isConnected)
    }

    override suspend fun receiveFrameBody(): ByteArray {
        check(isConnected)
        error("unused")
    }

    override fun close() {
        if (connected.compareAndSet(true, false)) closeCalls.incrementAndGet()
    }
}

private class DelayedFailingCloseRawChannel(
    private val failureMessage: String = "Injected displaced endpoint close failure",
) : RuntimeRawFrameBodyChannel {
    private val connected = AtomicBoolean(true)
    private val closeEntered = CountDownLatch(1)
    private val closeRelease = CountDownLatch(1)
    val closeCalls = AtomicInteger(0)

    override val isConnected: Boolean get() = connected.get()

    override suspend fun sendFrameBody(body: ByteArray) {
        check(isConnected)
    }

    override suspend fun receiveFrameBody(): ByteArray = error("unused")

    override fun close() {
        if (!connected.compareAndSet(true, false)) return
        closeCalls.incrementAndGet()
        closeEntered.countDown()
        check(closeRelease.await(5, TimeUnit.SECONDS)) {
            "Timed out waiting to release the displaced endpoint close"
        }
        throw IOException(failureMessage)
    }

    fun awaitCloseEntered(): Boolean = closeEntered.await(5, TimeUnit.SECONDS)

    fun releaseClose() = closeRelease.countDown()
}

private class ControllerCloseAwaitingRawChannel : RuntimeRawFrameBodyChannel {
    private val connected = AtomicBoolean(true)
    private val closeEntered = CountDownLatch(1)
    private val controllerCloseReturned = CountDownLatch(1)
    val closeCalls = AtomicInteger(0)

    override val isConnected: Boolean get() = connected.get()

    override suspend fun sendFrameBody(body: ByteArray) {
        check(isConnected)
    }

    override suspend fun receiveFrameBody(): ByteArray = error("unused")

    override fun close() {
        if (!connected.compareAndSet(true, false)) return
        closeCalls.incrementAndGet()
        closeEntered.countDown()
        check(controllerCloseReturned.await(5, TimeUnit.SECONDS)) {
            "Timed out waiting for controller.close() to return"
        }
    }

    fun awaitCloseEntered(): Boolean = closeEntered.await(5, TimeUnit.SECONDS)

    fun signalControllerCloseReturned() = controllerCloseReturned.countDown()
}

private class BlockingTransferRawChannel : RuntimeRawFrameBodyChannel {
    private val connected = AtomicBoolean(true)
    private val connectionChecks = AtomicInteger(0)
    private val transferCheckEntered = CountDownLatch(1)
    private val transferCheckRelease = CountDownLatch(1)

    override val isConnected: Boolean
        get() {
            if (connectionChecks.incrementAndGet() == 2) {
                transferCheckEntered.countDown()
                check(transferCheckRelease.await(5, TimeUnit.SECONDS)) {
                    "Timed out waiting to release the injected raw endpoint check"
                }
            }
            return connected.get()
        }

    fun awaitTransferCheck(): Boolean = transferCheckEntered.await(5, TimeUnit.SECONDS)

    fun releaseTransferCheck() = transferCheckRelease.countDown()

    override suspend fun sendFrameBody(body: ByteArray) = Unit

    override suspend fun receiveFrameBody(): ByteArray = error("unused")

    override fun close() {
        connected.set(false)
        transferCheckRelease.countDown()
    }
}

private class LoopbackProductionRawChannel(
    private val runtimeEngine: ProductionAuthorityBoundSecureSessionEngine,
    private val nowMs: ULong,
) : RuntimeRawFrameBodyChannel {
    private val connected = AtomicBoolean(true)
    private val sendCount = AtomicInteger(0)
    private val receiveCount = AtomicInteger(0)
    private val runtimeConfirmation = CompletableDeferred<ByteArray>()
    private val blockedInbound = CompletableDeferred<ByteArray>()
    val handshakeCompleted = AtomicBoolean(false)
    val applicationRecords = AtomicInteger(0)

    override val isConnected: Boolean get() = connected.get()

    override suspend fun sendFrameBody(body: ByteArray) {
        check(isConnected)
        if (sendCount.getAndIncrement() == 0) {
            runtimeEngine.acceptPeerConfirmation(body, nowMs)
            val confirmation = runtimeEngine.localConfirmation(nowMs)
            runtimeEngine.markLocalConfirmationSent(confirmation, nowMs)
            runtimeEngine.activate(nowMs)
            handshakeCompleted.set(true)
            runtimeConfirmation.complete(confirmation)
            return
        }
        val opened = runtimeEngine.open(body, nowMs)
        val plaintext = opened.takePlaintextAndWipe()
        plaintext.fill(0)
        applicationRecords.incrementAndGet()
    }

    override suspend fun receiveFrameBody(): ByteArray {
        check(isConnected)
        return if (receiveCount.getAndIncrement() == 0) {
            runtimeConfirmation.await()
        } else {
            blockedInbound.await()
        }
    }

    override fun close() {
        if (!connected.compareAndSet(true, false)) return
        val failure = IOException("loopback production raw endpoint closed")
        runtimeConfirmation.completeExceptionally(failure)
        blockedInbound.completeExceptionally(failure)
        runtimeEngine.close()
    }
}

private class InMemoryRuntimeLocalDataStore(
    private var data: PersistedRuntimeData,
) : RuntimeLocalDataStore {
    override fun load(): PersistedRuntimeData = data

    override fun save(data: PersistedRuntimeData, durability: RuntimeLocalDataWriteDurability) {
        this.data = data
    }
}

private object NoopLifecycleCallbacksRegistrar : RuntimeLifecycleCallbacksRegistrar {
    override fun register(application: Application, callbacks: Application.ActivityLifecycleCallbacks) = Unit

    override fun unregister(application: Application, callbacks: Application.ActivityLifecycleCallbacks) = Unit
}

private class TrackingLifecycleCallbacksRegistrar : RuntimeLifecycleCallbacksRegistrar {
    val unregisterCalls = AtomicInteger(0)

    override fun register(
        application: Application,
        callbacks: Application.ActivityLifecycleCallbacks,
    ) = Unit

    override fun unregister(
        application: Application,
        callbacks: Application.ActivityLifecycleCallbacks,
    ) {
        unregisterCalls.incrementAndGet()
    }
}

private suspend fun <Value> kotlinx.coroutines.flow.StateFlow<Value>.firstMatching(
    predicate: (Value) -> Boolean,
): Value = first(predicate)

private fun RuntimeClientViewModel.clearWithReflection() {
    val method = RuntimeClientViewModel::class.java.getDeclaredMethod("onCleared")
    method.isAccessible = true
    try {
        method.invoke(this)
    } catch (error: InvocationTargetException) {
        throw error.targetException
    }
}

private data class ActivationFixture(
    val root: JSONObject,
    val store: PairingStore,
    val runtime: TrustedRuntime,
    val identity: PairedRuntimeIdentity,
    val authority: ProductionPairAuthorityState,
    val grant: VerifiedProductionC1P2PGrantEvidence,
    val binding: VerifiedProductionC1CandidateP2PTranscriptBinding,
    val now: ULong,
) {
    val clock: () -> Long = { now.toLong() }

    fun controller() = AndroidProductionRuntimeActivationController(store, clock)

    fun ephemeralKey(name: String): ProductionSecureSessionEphemeralKey =
        productionEphemeralKey(root.getJSONObject("keys").getJSONObject(name).hex("privateScalarHex"))

    fun runtimeEngine(): ProductionAuthorityBoundSecureSessionEngine {
        val runtimeBinding = ProductionC1CandidateVerifier.verifyP2PKeyScheduleBinding(
            binding.transcript,
            grant,
            P2pNatRole.RUNTIME,
            authority,
            now,
        )
        return ProductionAuthorityBoundSecureSessionEngine.derive(
            runtimeBinding,
            ephemeralKey("runtimeEphemeral"),
            now,
        )
    }
}

private suspend fun createFixture(): ActivationFixture {
    val root = loadProductionFixture("production-g1a-c-candidate-v1-vectors.json")
    val objects = root.getJSONObject("objects")
    val artifacts = root.getJSONObject("artifacts")
    val now = root.getJSONObject("constants").stringULong("nowMs")
    val keyset = ProductionC1ServiceKeyset.decode(
        objects.getJSONObject("serviceKeyset").hex("expectedCanonicalHex"),
    )
    val verifiedKeyset = ProductionC1Verifier.verifyServiceKeyset(
        keyset,
        keyset.serviceIdDigest,
        fixturePublicKey(root, "root"),
        keyset.keysetVersion,
        nowMs = now,
    )
    val authority = ProductionPairAuthorityState.decode(
        objects.getJSONObject("authority").hex("expectedCanonicalHex"),
    )
    val sessionContext = ProductionC1PreauthorizationSessionContext.decode(
        objects.getJSONObject("preauthorizationSessionContext").hex("expectedCanonicalHex"),
    )
    val capabilities = ENDPOINT_OPERATIONS.map { operation ->
        ProductionC1CandidateVerifier.verifyCapability(
            ProductionC1CandidateCapability.decode(
                objects.getJSONObject(operation.capability).hex("expectedCanonicalHex"),
            ),
            artifacts.getJSONObject(operation.batch).hex("expectedCanonicalHex"),
            ProductionC1EndpointOperationProof.decode(
                objects.getJSONObject(operation.proof).hex("expectedCanonicalHex"),
            ),
            sessionContext,
            authority,
            verifiedKeyset,
            now,
        )
    }
    val bilateral = ProductionC1CandidateVerifier.verifyBilateral(
        capabilities[0],
        capabilities[1],
        capabilities[2],
        capabilities[3],
        authority,
        now,
    )
    val clientBatch = P2pNatCanonicalCodec.decodeCandidateBatch(
        artifacts.getJSONObject("clientCandidateBatch").hex("expectedCanonicalHex"),
    )
    val runtimeBatch = P2pNatCanonicalCodec.decodeCandidateBatch(
        artifacts.getJSONObject("runtimeCandidateBatch").hex("expectedCanonicalHex"),
    )
    val plan = ProductionC1CandidateVerifier.verifyP2PDirectPlan(
        ProductionC1RoutePlanClaims.decode(
            objects.getJSONObject("p2pRoutePlan").hex("expectedCanonicalHex"),
        ),
        ProductionC1RouteCapability.decode(
            objects.getJSONObject("p2pRouteCapability").hex("expectedCanonicalHex"),
        ),
        sessionContext,
        bilateral,
        clientBatch.candidates.single(),
        runtimeBatch.candidates.single(),
        artifacts.getJSONObject("pathValidationReceipt").hex("expectedCanonicalHex"),
        authority,
        verifiedKeyset,
        nowMs = now,
    )
    val authorizations = ProductionC1CandidateVerifier.makeBilateralRouteAuthorizations(
        plan,
        authority,
        now,
    )
    val operationAuthorizations = listOf(
        authorizations.clientPublish,
        authorizations.runtimeFetchClient,
        authorizations.runtimePublish,
        authorizations.clientFetchRuntime,
    )
    val receipts = ENDPOINT_OPERATIONS.mapIndexed { index, operation ->
        ProductionC1CandidateOperationReceiptVerifier.verify(
            ProductionC1CandidateOperationReceipt.decode(
                objects.getJSONObject(operation.receipt).hex("expectedCanonicalHex"),
            ),
            capabilities[index],
            operationAuthorizations[index],
            authority,
            verifiedKeyset,
            now,
        )
    }
    val grant = ProductionC1CandidateVerifier.verifyGrantEvidence(
        ProductionC1P2PGrantEvidence.decode(
            objects.getJSONObject("p2pGrantEvidence").hex("expectedCanonicalHex"),
        ),
        plan,
        authorizations,
        receipts,
        P2pNatRole.CLIENT,
        authority,
        now,
    )
    val transcript = ProductionSecureSessionCodec.decodeTranscript(
        objects.getJSONObject("candidateSecureSessionTranscript").hex("expectedCanonicalHex"),
    )
    val synthetic = root.getJSONObject("syntheticMaterials")
    val connectorSecret = synthetic.hex("connectorSecretHex")
    val connectorInput = ProductionC1CandidateVerifier.verifyP2PConnectorInput(
        grant,
        P2pNatRole.CLIENT,
        synthetic.getString("routeHandle"),
        synthetic.getString("connectorNonce"),
        connectorSecret,
        authority,
        now,
    )
    connectorSecret.fill(0)
    val confirmationKey = synthetic.hex("keyConfirmationKeyHex")
    val confirmation = ProductionC1CandidateVerifier.makeP2PKeyConfirmation(
        transcript,
        grant.grantAuthorization,
        P2pNatRole.RUNTIME,
        confirmationKey,
    )
    val binding = ProductionC1CandidateVerifier.verifyP2PTranscriptBinding(
        transcript,
        grant,
        connectorInput,
        P2pNatRole.CLIENT,
        confirmationKey,
        confirmation,
        authority,
        now,
    )
    confirmationKey.fill(0)
    confirmation.fill(0)
    val runtime = TrustedRuntime(
        deviceId = "runtime-production-controller-fixture",
        name = "Production controller fixture",
        fingerprint = authority.runtimeIdentityFingerprint,
        publicKeyBase64 = "runtime-production-public-key",
    )
    val store = PairingStore(ApplicationProvider.getApplicationContext())
    store.installTrustedClockForTest(now)
    store.forgetRuntime()
    store.trustRuntime(runtime)
    store.applyVerifiedPairTransitionForTest(
        runtime.deviceId,
        runtime.fingerprint,
        ProductionPairStateTransition(null, authority),
    )
    return ActivationFixture(
        root = root,
        store = store,
        runtime = runtime,
        identity = PairedRuntimeIdentity(
            deviceId = runtime.deviceId,
            name = runtime.name,
            fingerprint = runtime.fingerprint,
            publicKeyBase64 = runtime.publicKeyBase64,
        ),
        authority = authority,
        grant = grant,
        binding = binding,
        now = now,
    )
}

private fun PairingStore.installTrustedClockForTest(now: ULong) {
    val field = PairingStore::class.java.getDeclaredField("productionTrustedClock")
    field.isAccessible = true
    val clockType = field.type
    val clock = Proxy.newProxyInstance(
        clockType.classLoader,
        arrayOf(clockType),
    ) { proxy, method, arguments ->
        when {
            method.name.startsWith("nowMs") -> now.toLong()
            method.name == "toString" -> "FixtureProductionClock($now)"
            method.name == "hashCode" -> System.identityHashCode(proxy)
            method.name == "equals" -> proxy === arguments?.singleOrNull()
            else -> error("Unexpected trusted-clock method ${method.name}")
        }
    }
    field.set(this, clock)
}

private suspend fun PairingStore.applyVerifiedPairTransitionForTest(
    deviceId: String,
    fingerprint: String,
    transition: ProductionPairStateTransition,
): ProductionPairStateSnapshot = suspendCoroutineUninterceptedOrReturn { continuation ->
    val method = PairingStore::class.java.methods.single {
        it.name.startsWith("applyVerifiedProductionPairTransition")
    }
    try {
        val result = method.invoke(this, deviceId, fingerprint, transition, continuation)
        if (result === COROUTINE_SUSPENDED) COROUTINE_SUSPENDED else result as ProductionPairStateSnapshot
    } catch (error: InvocationTargetException) {
        throw error.targetException
    }
}

private fun productionEphemeralKey(privateScalar: ByteArray): ProductionSecureSessionEphemeralKey {
    val rawClass = Class.forName(
        "com.localagentbridge.android.core.protocol.p2pnat.P2pNatSessionEphemeralKey",
    )
    val rawCompanion = rawClass.getField("Companion").get(null)
    val rawFactory = rawCompanion.javaClass.methods.single {
        it.name.startsWith("fromPrivateScalarForTest")
    }
    val rawKey = rawFactory.invoke(rawCompanion, privateScalar)
    privateScalar.fill(0)
    val productionCompanion = ProductionSecureSessionEphemeralKey::class.java
        .getField("Companion")
        .get(null)
    val productionFactory = productionCompanion.javaClass.methods.single {
        it.name.startsWith("fromRawForTest")
    }
    return productionFactory.invoke(productionCompanion, rawKey)
        as ProductionSecureSessionEphemeralKey
}

private fun loadProductionFixture(fileName: String): JSONObject {
    val relative = Path.of("shared", "protocol", "fixtures", fileName)
    val starts = listOfNotNull(
        Path.of(System.getProperty("user.dir")).toAbsolutePath(),
        AndroidProductionRuntimeActivationControllerTest::class.java.protectionDomain
            ?.codeSource
            ?.location
            ?.toURI()
            ?.let(Path::of)
            ?.toAbsolutePath(),
    )
    val path = starts.asSequence().flatMap { start ->
        generateSequence(if (Files.isDirectory(start)) start else start.parent) { it.parent }
    }.map { it.resolve(relative) }.firstOrNull(Files::isRegularFile)
        ?: error("Shared production candidate fixture not found")
    return JSONObject(String(Files.readAllBytes(path), Charsets.UTF_8))
}

private fun fixturePublicKey(root: JSONObject, name: String): PublicKey =
    KeyFactory.getInstance("EC").generatePublic(
        X509EncodedKeySpec(
            root.getJSONObject("keys").getJSONObject(name).hex("publicKeySPKIDERHex"),
        ),
    )

private fun JSONObject.hex(name: String): ByteArray = getString(name).hexBytes()

private fun JSONObject.stringULong(name: String): ULong = getString(name).toULong()

private fun String.hexBytes(): ByteArray {
    require(length % 2 == 0)
    return chunked(2).map { it.toInt(16).toByte() }.toByteArray()
}

private data class EndpointOperation(
    val proof: String,
    val capability: String,
    val batch: String,
    val receipt: String,
)

private const val ENDPOINT_ADMISSION_ID =
    "9999999999999999999999999999999999999999999999999999999999999999"

private const val REPLACEMENT_ENDPOINT_ADMISSION_ID =
    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

private val ENDPOINT_OPERATIONS = listOf(
    EndpointOperation(
        "endpointProofClientPublish",
        "capabilityClientPublish",
        "clientCandidateBatch",
        "receiptClientPublish",
    ),
    EndpointOperation(
        "endpointProofRuntimeFetchClient",
        "capabilityRuntimeFetchClient",
        "clientCandidateBatch",
        "receiptRuntimeFetchClient",
    ),
    EndpointOperation(
        "endpointProofRuntimePublish",
        "capabilityRuntimePublish",
        "runtimeCandidateBatch",
        "receiptRuntimePublish",
    ),
    EndpointOperation(
        "endpointProofClientFetchRuntime",
        "capabilityClientFetchRuntime",
        "runtimeCandidateBatch",
        "receiptClientFetchRuntime",
    ),
)
