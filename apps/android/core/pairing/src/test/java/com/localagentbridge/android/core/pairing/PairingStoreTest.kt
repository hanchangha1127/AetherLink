package com.localagentbridge.android.core.pairing

import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.core.stringSetPreferencesKey
import androidx.test.core.app.ApplicationProvider
import com.localagentbridge.android.core.protocol.p2pnat.LocalDirectRouteAuthorization
import com.localagentbridge.android.core.protocol.p2pnat.ProductionPairAuthorityState
import com.localagentbridge.android.core.protocol.p2pnat.ProductionPairAuthorityStatus
import com.localagentbridge.android.core.protocol.p2pnat.ProductionPairStateException
import com.localagentbridge.android.core.protocol.p2pnat.ProductionPairStateRejectionReason
import com.localagentbridge.android.core.protocol.p2pnat.ProductionPairStateSnapshot
import com.localagentbridge.android.core.protocol.p2pnat.ProductionPairStateTransition
import com.localagentbridge.android.core.protocol.p2pnat.ProductionRouteAuthorizationKind
import com.localagentbridge.android.core.protocol.p2pnat.ProductionSecureSessionCodec
import com.localagentbridge.android.core.protocol.p2pnat.ProductionSecureSessionTranscript
import com.localagentbridge.android.core.protocol.p2pnat.*
import java.nio.file.Files
import java.nio.file.Path
import java.io.IOException
import java.security.KeyFactory
import java.security.MessageDigest
import java.security.PublicKey
import java.security.spec.X509EncodedKeySpec
import java.util.Base64
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.yield
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class PairingStoreTest {
    @Test
    fun publicationGateAdmitsWritersInStrictFifoOrder() = runTest {
        val gate = ProductionC1AuthorityPublicationGate(maximumWaiters = 8)
        val heldRead = gate.acquireRead()
        val admissionOrder = mutableListOf<Int>()

        val first = async {
            val permit = gate.acquireWrite()
            admissionOrder += 1
            permit.release()
        }
        while (gate.waitingWriterCountForTesting() != 1) yield()
        val second = async {
            val permit = gate.acquireWrite()
            admissionOrder += 2
            permit.release()
        }
        while (gate.waitingWriterCountForTesting() != 2) yield()
        val third = async {
            val permit = gate.acquireWrite()
            admissionOrder += 3
            permit.release()
        }
        while (gate.waitingWriterCountForTesting() != 3) yield()

        heldRead.release()
        awaitAll(first, second, third)
        assertEquals(listOf(1, 2, 3), admissionOrder)
    }

    @Test
    fun publicationGateReaderCannotOvertakeEarlierWriter() = runTest {
        val gate = ProductionC1AuthorityPublicationGate(maximumWaiters = 4)
        val heldRead = gate.acquireRead()
        val allowWriterRelease = CompletableDeferred<Unit>()
        val writerEntered = AtomicBoolean(false)
        val readerEntered = AtomicBoolean(false)

        val writer = async {
            val permit = gate.acquireWrite()
            writerEntered.set(true)
            allowWriterRelease.await()
            permit.release()
        }
        while (gate.waitingWriterCountForTesting() != 1) yield()
        val reader = async {
            val permit = gate.acquireRead()
            readerEntered.set(true)
            permit.release()
        }
        while (gate.waitingCountForTesting() != 2) yield()

        heldRead.release()
        while (!writerEntered.get()) yield()
        assertTrue(!readerEntered.get())
        allowWriterRelease.complete(Unit)
        awaitAll(writer, reader)
        assertTrue(readerEntered.get())
    }

    @Test
    fun publicationGateCancellationAndOverflowLeaveNoWaiters() = runTest {
        val gate = ProductionC1AuthorityPublicationGate(maximumWaiters = 2)
        val heldWriter = gate.acquireWrite()
        val first = async { gate.acquireRead() }
        val second = async { gate.acquireRead() }
        while (gate.waitingCountForTesting() != 2) yield()

        try {
            gate.acquireRead()
            throw AssertionError("expected bounded waiter overflow")
        } catch (error: ProductionC1AuthorityPublicationGateCapacityException) {
            assertEquals(2, error.maximumWaiters)
        }

        first.cancelAndJoin()
        second.cancelAndJoin()
        assertEquals(0, gate.waitingCountForTesting())

        repeat(64) {
            val waiter = async { gate.acquireRead() }
            while (gate.waitingCountForTesting() != 1) yield()
            waiter.cancelAndJoin()
            assertEquals(0, gate.waitingCountForTesting())
        }

        heldWriter.release()
        gate.acquireRead().release()
    }

    @Test
    fun publicationGatePromotesLeadingReaderBatchBeforeLaterWriter() = runTest {
        val gate = ProductionC1AuthorityPublicationGate(maximumWaiters = 8)
        val heldWriter = gate.acquireWrite()
        val releaseReaders = CompletableDeferred<Unit>()
        val activeReaders = AtomicInteger(0)
        val laterWriterEntered = AtomicBoolean(false)

        val readers = (0..<3).map {
            async {
                val permit = gate.acquireRead()
                activeReaders.incrementAndGet()
                releaseReaders.await()
                permit.release()
            }
        }
        while (gate.waitingCountForTesting() != 3) yield()
        val laterWriter = async {
            val permit = gate.acquireWrite()
            laterWriterEntered.set(true)
            permit.release()
        }
        while (gate.waitingCountForTesting() != 4) yield()

        heldWriter.release()
        while (activeReaders.get() != 3) yield()
        assertTrue(!laterWriterEntered.get())
        releaseReaders.complete(Unit)
        readers.awaitAll()
        laterWriter.await()
        assertTrue(laterWriterEntered.get())
    }

    @Test
    fun deterministicEndpointEntryMarkerMatchesSwiftParityVector() {
        val authority = ProductionPairAuthorityState(
            pairBindingDigest = "1".repeat(64),
            pairEpoch = 2uL,
            clientIdentityFingerprint = "2".repeat(64),
            runtimeIdentityFingerprint = "3".repeat(64),
            generation = 30uL,
            serviceConfigVersion = 4uL,
            keysetVersion = 5uL,
            revocationCounter = 0uL,
            protocolFloor = 1u,
            status = ProductionPairAuthorityStatus.ACTIVE,
            transitionId = "4".repeat(64),
            transitionRequestDigest = "5".repeat(64),
            acceptedReceiptDigest = "6".repeat(64),
            authorityRevision = 1uL,
        )
        val nextPair = ProductionPairStateSnapshot(
            authority,
            2uL,
            listOf(ProductionPairConsumedSession("7".repeat(32), "7".repeat(64))),
        )
        val constructor = ProductionC1EndpointGrantEntry::class.java.declaredConstructors
            .single { it.parameterCount == 10 }
            .also { it.isAccessible = true }
        val entry = constructor.newInstance(
            "7".repeat(64),
            "7".repeat(64),
            "7".repeat(64),
            "7".repeat(32),
            "7".repeat(64),
            "7".repeat(64),
            "a".repeat(64),
            "7".repeat(64),
            nextPair.digestHex(),
            2L,
        ) as ProductionC1EndpointGrantEntry

        assertEquals(
            "127958514e2894e27cc3ae3a362a7691ce2a4161c6e2024f70cff01d2cfd6a37",
            endpointGrantEntryDigest(entry),
        )
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
    fun trustedRuntimeCanCarryP2pRendezvousRoute() {
        val runtime = completeP2pRuntime()

        assertEquals("p2p_rendezvous", runtime.p2pRouteClass)
        assertEquals("p2p-record-1", runtime.p2pRecordId)
        assertEquals("opaque-candidate-1", runtime.p2pEncryptedBody)
        assertEquals(4102444800000L, runtime.p2pExpiresAtEpochMillis)
        assertEquals("nonce-p2p-1", runtime.p2pAntiReplayNonce)
        assertEquals(1, runtime.p2pProtocolVersion)
        assertEquals(true, runtime.hasValidP2pRoute(nowEpochMillis = 1_000L))
    }

    @Test
    fun trustedRuntimeRejectsNonCanonicalP2pRendezvousRoute() {
        val routes = listOf(
            completeP2pRuntime().copy(p2pRouteClass = " p2p_rendezvous"),
            completeP2pRuntime().copy(p2pRecordId = "p2p record 1"),
            completeP2pRuntime().copy(p2pEncryptedBody = " opaque-candidate-1"),
            completeP2pRuntime().copy(p2pAntiReplayNonce = "nonce p2p 1"),
        )

        routes.forEach { runtime ->
            assertEquals(false, runtime.hasValidP2pRoute(nowEpochMillis = 1_000L))
        }
    }

    @Test
    fun trustedRuntimeRejectsOversizedP2pRendezvousRoute() {
        val oversizedValue = "r".repeat(OPAQUE_ROUTE_VALUE_MAX_CHARS + 1)
        val oversizedBody = "b".repeat(OPAQUE_ROUTE_BODY_MAX_CHARS + 1)
        val routes = listOf(
            completeP2pRuntime().copy(p2pRecordId = oversizedValue),
            completeP2pRuntime().copy(p2pEncryptedBody = oversizedBody),
            completeP2pRuntime().copy(p2pAntiReplayNonce = oversizedValue),
        )

        routes.forEach { runtime ->
            assertEquals(false, runtime.hasValidP2pRoute(nowEpochMillis = 1_000L))
        }
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
    fun trustedRuntimeRejectsNonpositiveRelayTicketGeneration() {
        assertEquals(false, completeRelayRuntime().copy(relayTicketGeneration = 0L).hasValidRelayRoute())
        assertEquals(false, completeRelayRuntime().copy(relayTicketGeneration = -1L).hasValidRelayRoute())
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
    fun trustedRuntimeRejectsNonCanonicalRelayRoute() {
        val routes = listOf(
            completeRelayRuntime().copy(relayHost = " relay.example.test"),
            completeRelayRuntime().copy(relayHost = "relay.example.test "),
            completeRelayRuntime().copy(relayHost = "relay example.test"),
            completeRelayRuntime().copy(relayHost = "https://relay.example.test"),
            completeRelayRuntime().copy(relayHost = "relay.example.test/path"),
            completeRelayRuntime().copy(relayHost = "relay.example.test?route=1"),
            completeRelayRuntime().copy(relayHost = "relay.example.test#fragment"),
            completeRelayRuntime().copy(relayHost = "user@relay.example.test"),
            completeRelayRuntime().copy(relayId = "relay 1"),
            completeRelayRuntime().copy(relaySecret = " secret-1"),
            completeRelayRuntime().copy(relayNonce = "nonce route 1"),
        )

        routes.forEach { runtime ->
            assertEquals(false, runtime.hasValidRelayRoute())
        }
    }

    @Test
    fun trustedRuntimeRejectsInvalidRelayScopeValues() {
        val routes = nonCanonicalRelayScopeValues().map { invalidScope ->
            completeRelayRuntime().copy(relayScope = invalidScope)
        }

        routes.forEach { runtime ->
            assertEquals(false, runtime.hasValidRelayRoute())
        }
    }

    @Test
    fun trustedRuntimeRejectsOversizedRelayRoute() {
        val oversizedValue = "r".repeat(OPAQUE_ROUTE_VALUE_MAX_CHARS + 1)
        val routes = listOf(
            completeRelayRuntime().copy(relayId = oversizedValue),
            completeRelayRuntime().copy(relaySecret = oversizedValue),
            completeRelayRuntime().copy(relayNonce = oversizedValue),
        )

        routes.forEach { runtime ->
            assertEquals(false, runtime.hasValidRelayRoute())
        }
    }

    @Test
    fun trustedRuntimeRejectsExpiredP2pRendezvousRoute() {
        val runtime = completeP2pRuntime().copy(
            p2pExpiresAtEpochMillis = 2_000L,
        )

        assertEquals(false, runtime.hasValidP2pRoute())
        assertEquals(true, runtime.hasExpiredP2pRoute(nowEpochMillis = 2_001L))
        assertEquals(false, runtime.hasExpiredP2pRoute(nowEpochMillis = 1_999L))
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

        assertEquals(true, runtime.hasValidRelayRoute())
    }

    @Test
    fun pairingStoreDropsDirectEndpointForTrustedRuntimeRestore() = runTest {
        val store = pairingStore()
        store.forgetRuntime()

        store.trustRuntime(trustedRuntime(host = "127.0.0.1", port = 43170))

        val trusted = store.trustedRuntime.first()
        assertEquals("runtime-1", trusted?.deviceId)
        assertNull(trusted?.host)
        assertNull(trusted?.port)

        val prefs = ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .data
            .first()
        assertNoStoredDirectEndpoint(prefs)

        store.forgetRuntime()
    }

    @Test
    fun pairingStoreDropsStoredAndLegacyDirectEndpointOnRead() = runTest {
        val store = pairingStore()
        store.forgetRuntime()

        ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .edit { prefs ->
                prefs[stringPreferencesKey("runtime_device_id")] = "runtime-1"
                prefs[stringPreferencesKey("runtime_name")] = "AetherLink Runtime"
                prefs[stringPreferencesKey("runtime_fingerprint")] = "runtime-fingerprint"
                prefs[stringPreferencesKey("runtime_public_key")] = "runtime-public-key"
                prefs[stringPreferencesKey("runtime_route_token")] = "route-token"
                prefs[stringPreferencesKey("runtime_host")] = "192.168.1.10"
                prefs[intPreferencesKey("runtime_port")] = 43170
                prefs[stringPreferencesKey("mac_host")] = "192.168.1.11"
                prefs[intPreferencesKey("mac_port")] = 43171
            }

        val trusted = store.trustedRuntime.first()
        assertEquals("runtime-1", trusted?.deviceId)
        assertEquals("runtime-fingerprint", trusted?.fingerprint)
        assertNull(trusted?.host)
        assertNull(trusted?.port)

        val prefs = ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .data
            .first()
        assertNoStoredDirectEndpoint(prefs)

        store.forgetRuntime()
    }

    @Test
    fun pairingStorePersistsCompleteRelayRoute() = runTest {
        val secretStore = FakeRelaySecretStore()
        val store = pairingStore(secretStore)
        store.forgetRuntime()

        store.trustRuntime(completeRelayRuntime())

        val trusted = store.trustedRuntime.first()
        assertEquals("runtime-1", trusted?.deviceId)
        assertEquals("AetherLink Runtime", trusted?.name)
        assertEquals("runtime-fingerprint", trusted?.fingerprint)
        assertEquals("runtime-public-key", trusted?.publicKeyBase64)
        assertEquals("route-token", trusted?.routeToken)
        assertNull(trusted?.host)
        assertNull(trusted?.port)
        assertEquals("relay.example.test", trusted?.relayHost)
        assertEquals(443, trusted?.relayPort)
        assertEquals("relay-1", trusted?.relayId)
        assertEquals("secret-1", trusted?.relaySecret)
        assertEquals(4102444800000L, trusted?.relayExpiresAtEpochMillis)
        assertEquals("nonce-route-1", trusted?.relayNonce)
        assertEquals("remote", trusted?.relayScope)

        val prefs = ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .data
            .first()
        assertNull(prefs[stringPreferencesKey("runtime_relay_secret")])
        val relaySecretRef = prefs[stringPreferencesKey("runtime_relay_secret_ref")]
        assertNotNull(relaySecretRef)
        assertEquals("secret-1", secretStore.secrets[relaySecretRef])

        store.forgetRuntime()
    }

    @Test
    fun pairingStoreDurablyRotatesRelaySecretBeforeRemovingPreviousHandle() = runTest {
        val secretStore = FakeRelaySecretStore()
        val store = pairingStore(secretStore)
        store.forgetRuntime()

        store.trustRuntime(completeRelayRuntime())
        val firstPrefs = ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .data
            .first()
        val firstReference = requireNotNull(
            firstPrefs[stringPreferencesKey("runtime_relay_secret_ref")],
        )
        store.trustRuntime(completeRelayRuntime())
        assertEquals(listOf(firstReference), secretStore.durablySavedHandles)

        store.trustRuntime(
            completeRelayRuntime().copy(
                relaySecret = "secret-2",
                relayNonce = "nonce-route-2",
                relayTicketGeneration = 2L,
            )
        )

        val secondPrefs = ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .data
            .first()
        val secondReference = requireNotNull(
            secondPrefs[stringPreferencesKey("runtime_relay_secret_ref")],
        )
        assertTrue(firstReference != secondReference)
        assertTrue(secretStore.asynchronouslySavedHandles.isEmpty())
        assertEquals(listOf(firstReference, secondReference), secretStore.durablySavedHandles)
        assertEquals(listOf(firstReference), secretStore.durablyRemovedHandles)
        assertNull(secretStore.secrets[firstReference])
        assertEquals("secret-2", secretStore.secrets[secondReference])
        assertEquals("secret-2", store.trustedRuntime.first()?.relaySecret)

        store.forgetRuntime()
    }

    @Test
    fun pairingStoreFailedDurableSecretRotationPreservesPreviousRoute() = runTest {
        val secretStore = FakeRelaySecretStore()
        val store = pairingStore(secretStore)
        store.forgetRuntime()
        store.trustRuntime(completeRelayRuntime())
        val before = ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .data
            .first()
        val previousReference = requireNotNull(
            before[stringPreferencesKey("runtime_relay_secret_ref")],
        )
        secretStore.failNextDurableSave = true

        val failure = runCatching {
            store.trustRuntime(
                completeRelayRuntime().copy(
                    relaySecret = "secret-rejected",
                    relayNonce = "nonce-route-rejected",
                )
            )
        }.exceptionOrNull()

        assertNotNull(failure)
        assertTrue(failure?.message.orEmpty().contains("persistence failed"))
        val after = ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .data
            .first()
        assertEquals(previousReference, after[stringPreferencesKey("runtime_relay_secret_ref")])
        assertEquals("secret-1", secretStore.secrets[previousReference])
        assertEquals("secret-1", store.trustedRuntime.first()?.relaySecret)
        assertTrue(secretStore.asynchronouslySavedHandles.isEmpty())
        val rejectedReference = secretStore.durablySavedHandles.last()
        assertTrue(rejectedReference != previousReference)
        assertTrue(rejectedReference in secretStore.durablyRemovedHandles)
        assertNull(secretStore.secrets[rejectedReference])

        store.forgetRuntime()
    }

    @Test
    fun pairingStoreCleanupFailureKeepsJournalAndRetriesOnRead() = runTest {
        val secretStore = FakeRelaySecretStore()
        val store = pairingStore(secretStore)
        store.forgetRuntime()
        store.trustRuntime(completeRelayRuntime())
        val firstPrefs = ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .data
            .first()
        val firstReference = requireNotNull(
            firstPrefs[stringPreferencesKey("runtime_relay_secret_ref")],
        )
        secretStore.failNextDurableRemoval = true

        val failure = runCatching {
            store.trustRuntime(
                completeRelayRuntime().copy(
                    relaySecret = "secret-journal",
                    relayNonce = "nonce-route-journal",
                )
            )
        }.exceptionOrNull()

        assertNotNull(failure)
        assertTrue(failure?.message.orEmpty().contains("cleanup failed"))
        val pendingCleanup = ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .data
            .first()
        val replacementReference = requireNotNull(
            pendingCleanup[stringPreferencesKey("runtime_relay_secret_ref")],
        )
        assertTrue(firstReference != replacementReference)
        assertEquals(
            setOf(firstReference),
            pendingCleanup[stringSetPreferencesKey("runtime_relay_secret_cleanup_refs")],
        )
        assertEquals("secret-1", secretStore.secrets[firstReference])

        assertEquals("secret-journal", store.trustedRuntime.first()?.relaySecret)

        val cleaned = ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .data
            .first()
        assertNull(cleaned[stringSetPreferencesKey("runtime_relay_secret_cleanup_refs")])
        assertNull(secretStore.secrets[firstReference])
        assertEquals("secret-journal", secretStore.secrets[replacementReference])

        store.forgetRuntime()
    }

    @Test
    fun pairingStoreRePairDoesNotDrainJournaledCurrentSecret() = runTest {
        val secretStore = FakeRelaySecretStore()
        val store = pairingStore(secretStore)
        store.forgetRuntime()
        store.trustRuntime(completeRelayRuntime())
        val before = ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .data
            .first()
        val currentReference = requireNotNull(
            before[stringPreferencesKey("runtime_relay_secret_ref")],
        )
        secretStore.failNextDurableRemoval = true

        val forgetFailure = runCatching { store.forgetRuntime() }.exceptionOrNull()

        assertNotNull(forgetFailure)
        val forgotten = ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .data
            .first()
        assertNull(forgotten[stringPreferencesKey("runtime_relay_secret_ref")])
        assertEquals(
            setOf(currentReference),
            forgotten[stringSetPreferencesKey("runtime_relay_secret_cleanup_refs")],
        )
        assertEquals("secret-1", secretStore.secrets[currentReference])

        store.trustRuntime(completeRelayRuntime())

        val repaired = ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .data
            .first()
        assertEquals(currentReference, repaired[stringPreferencesKey("runtime_relay_secret_ref")])
        assertNull(repaired[stringSetPreferencesKey("runtime_relay_secret_cleanup_refs")])
        assertEquals("secret-1", secretStore.secrets[currentReference])
        assertEquals("secret-1", store.trustedRuntime.first()?.relaySecret)

        store.forgetRuntime()
    }

    @Test
    fun pairingStorePersistsRelayTicketGenerationAcrossRestart() = runTest {
        val secretStore = FakeRelaySecretStore()
        val store = pairingStore(secretStore)
        store.forgetRuntime()

        store.trustRuntime(completeRelayRuntime().copy(relayTicketGeneration = 7L))

        val restartedStore = pairingStore(secretStore)
        val trusted = restartedStore.trustedRuntime.first()
        assertEquals(7L, trusted?.relayTicketGeneration)
        assertEquals("relay-1", trusted?.relayId)
        assertEquals("secret-1", trusted?.relaySecret)
        val prefs = ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .data
            .first()
        assertEquals(7L, prefs[longPreferencesKey("runtime_relay_ticket_generation")])

        restartedStore.forgetRuntime()
    }

    @Test
    fun pairingStoreClearsRelayTicketGenerationWithRelayRoute() = runTest {
        val secretStore = FakeRelaySecretStore()
        val store = pairingStore(secretStore)
        store.forgetRuntime()
        val trusted = completeRelayRuntime().copy(relayTicketGeneration = 7L)
        store.trustRuntime(trusted)

        store.trustRuntime(
            trusted.copy(
                relayHost = null,
                relayPort = null,
                relayId = null,
                relaySecret = null,
                relayExpiresAtEpochMillis = null,
                relayNonce = null,
                relayScope = null,
                relayTicketGeneration = null,
            )
        )

        val cleared = store.trustedRuntime.first()
        assertEquals("runtime-1", cleared?.deviceId)
        assertNull(cleared?.relayTicketGeneration)
        val prefs = ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .data
            .first()
        assertNoStoredRelayRoute(prefs)
        assertTrue(secretStore.secrets.isEmpty())

        store.forgetRuntime()
    }

    @Test
    fun pairingStorePersistsCompleteP2pRendezvousRoute() = runTest {
        val store = pairingStore()
        store.forgetRuntime()

        store.trustRuntime(completeP2pRuntime())

        val trusted = store.trustedRuntime.first()
        assertEquals("runtime-1", trusted?.deviceId)
        assertEquals("AetherLink Runtime", trusted?.name)
        assertEquals("runtime-fingerprint", trusted?.fingerprint)
        assertEquals("runtime-public-key", trusted?.publicKeyBase64)
        assertEquals("route-token", trusted?.routeToken)
        assertNull(trusted?.host)
        assertNull(trusted?.port)
        assertEquals("p2p_rendezvous", trusted?.p2pRouteClass)
        assertEquals("p2p-record-1", trusted?.p2pRecordId)
        assertEquals("opaque-candidate-1", trusted?.p2pEncryptedBody)
        assertEquals(4102444800000L, trusted?.p2pExpiresAtEpochMillis)
        assertEquals("nonce-p2p-1", trusted?.p2pAntiReplayNonce)
        assertEquals(1, trusted?.p2pProtocolVersion)

        val prefs = ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .data
            .first()
        assertEquals("p2p_rendezvous", prefs[stringPreferencesKey("runtime_p2p_route_class")])
        assertEquals("p2p-record-1", prefs[stringPreferencesKey("runtime_p2p_record_id")])
        assertEquals("opaque-candidate-1", prefs[stringPreferencesKey("runtime_p2p_encrypted_body")])
        assertEquals(4102444800000L, prefs[longPreferencesKey("runtime_p2p_expires_at_epoch_millis")])
        assertEquals("nonce-p2p-1", prefs[stringPreferencesKey("runtime_p2p_anti_replay_nonce")])
        assertEquals(1, prefs[intPreferencesKey("runtime_p2p_protocol_version")])

        store.forgetRuntime()
    }

    @Test
    fun pairingStoreDropsNonCanonicalRouteTokenOnWrite() = runTest {
        val store = pairingStore()
        store.forgetRuntime()

        store.trustRuntime(
            trustedRuntime(host = null, port = null).copy(
                routeToken = "route token",
            )
        )

        val trusted = store.trustedRuntime.first()
        assertEquals("runtime-1", trusted?.deviceId)
        assertNull(trusted?.routeToken)

        val prefs = ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .data
            .first()
        assertNoStoredRouteToken(prefs)

        store.forgetRuntime()
    }

    @Test
    fun pairingStoreDropsNonCanonicalStoredRouteTokenOnRead() = runTest {
        val store = pairingStore()
        val invalidStoredValues = listOf(
            "route token",
            " route-token",
            "r".repeat(OPAQUE_ROUTE_VALUE_MAX_CHARS + 1),
        )

        invalidStoredValues.forEach { invalidValue ->
            store.forgetRuntime()

            ApplicationProvider.getApplicationContext<android.content.Context>()
                .localAgentBridgeDataStore
                .edit { prefs ->
                    prefs[stringPreferencesKey("runtime_device_id")] = "runtime-1"
                    prefs[stringPreferencesKey("runtime_name")] = "AetherLink Runtime"
                    prefs[stringPreferencesKey("runtime_fingerprint")] = "runtime-fingerprint"
                    prefs[stringPreferencesKey("runtime_public_key")] = "runtime-public-key"
                    prefs[stringPreferencesKey("runtime_route_token")] = invalidValue
                    prefs[stringPreferencesKey("mac_route_token")] = invalidValue
                }

            val trusted = store.trustedRuntime.first()
            assertEquals("runtime-1", trusted?.deviceId)
            assertEquals("runtime-fingerprint", trusted?.fingerprint)
            assertNull(trusted?.routeToken)

            val prefs = ApplicationProvider.getApplicationContext<android.content.Context>()
                .localAgentBridgeDataStore
                .data
                .first()
            assertNoStoredRouteToken(prefs)
        }

        store.forgetRuntime()
    }

    @Test
    fun pairingStoreDropsNonCanonicalStoredTrustedIdentityOnRead() = runTest {
        val store = pairingStore()
        val invalidStoredIdentities = listOf(
            Pair(stringPreferencesKey("runtime_device_id"), " runtime-1"),
            Pair(stringPreferencesKey("runtime_device_id"), "r".repeat(OPAQUE_ROUTE_VALUE_MAX_CHARS + 1)),
            Pair(stringPreferencesKey("runtime_fingerprint"), "runtime fingerprint"),
            Pair(stringPreferencesKey("runtime_fingerprint"), " runtime-fingerprint"),
        )

        invalidStoredIdentities.forEach { (key, invalidValue) ->
            store.forgetRuntime()

            ApplicationProvider.getApplicationContext<android.content.Context>()
                .localAgentBridgeDataStore
                .edit { prefs ->
                    prefs[stringPreferencesKey("runtime_device_id")] = "runtime-1"
                    prefs[stringPreferencesKey("runtime_name")] = "AetherLink Runtime"
                    prefs[stringPreferencesKey("runtime_fingerprint")] = "runtime-fingerprint"
                    prefs[stringPreferencesKey("runtime_public_key")] = "runtime-public-key"
                    prefs[stringPreferencesKey("runtime_route_token")] = "route-token"
                    prefs[key] = invalidValue
                }

            assertNull(store.trustedRuntime.first())

            val prefs = ApplicationProvider.getApplicationContext<android.content.Context>()
                .localAgentBridgeDataStore
                .data
                .first()
            assertNoStoredTrustedRuntime(prefs)
        }

        store.forgetRuntime()
    }

    @Test
    fun pairingStoreDropsNonCanonicalStoredRuntimePublicKeyOnRead() = runTest {
        val store = pairingStore()
        val invalidStoredValues = listOf(
            "runtime public key",
            " runtime-public-key",
            "p".repeat(OPAQUE_ROUTE_VALUE_MAX_CHARS + 1),
        )

        invalidStoredValues.forEach { invalidValue ->
            store.forgetRuntime()

            ApplicationProvider.getApplicationContext<android.content.Context>()
                .localAgentBridgeDataStore
                .edit { prefs ->
                    prefs[stringPreferencesKey("runtime_device_id")] = "runtime-1"
                    prefs[stringPreferencesKey("runtime_name")] = "AetherLink Runtime"
                    prefs[stringPreferencesKey("runtime_fingerprint")] = "runtime-fingerprint"
                    prefs[stringPreferencesKey("runtime_public_key")] = invalidValue
                    prefs[stringPreferencesKey("runtime_route_token")] = "route-token"
                }

            assertNull(store.trustedRuntime.first())

            val prefs = ApplicationProvider.getApplicationContext<android.content.Context>()
                .localAgentBridgeDataStore
                .data
                .first()
            assertNoStoredTrustedRuntime(prefs)
        }

        store.forgetRuntime()
    }

    @Test
    fun pairingStoreDropsNonCanonicalTrustedIdentityOnWrite() = runTest {
        val store = pairingStore()
        val invalidRuntimes = listOf(
            trustedRuntime(host = null, port = null).copy(deviceId = " runtime-1"),
            trustedRuntime(host = null, port = null).copy(fingerprint = "runtime fingerprint"),
            trustedRuntime(host = null, port = null).copy(publicKeyBase64 = " runtime-public-key"),
        )

        invalidRuntimes.forEach { runtime ->
            store.forgetRuntime()

            store.trustRuntime(runtime)

            assertNull(store.trustedRuntime.first())

            val prefs = ApplicationProvider.getApplicationContext<android.content.Context>()
                .localAgentBridgeDataStore
                .data
                .first()
            assertNoStoredTrustedRuntime(prefs)
        }

        store.forgetRuntime()
    }

    @Test
    fun pairingStoreDropsNonCanonicalRelayHostOnWrite() = runTest {
        val secretStore = FakeRelaySecretStore()
        val store = pairingStore(secretStore)

        nonCanonicalRelayHostValues().forEach { invalidHost ->
            store.forgetRuntime()

            store.trustRuntime(
                completeRelayRuntime().copy(
                    relayHost = invalidHost,
                )
            )

            val trusted = store.trustedRuntime.first()
            assertEquals("runtime-1", trusted?.deviceId)
            assertNull(trusted?.relayHost)
            assertNull(trusted?.relayPort)
            assertNull(trusted?.relayId)
            assertNull(trusted?.relaySecret)
            assertNull(trusted?.relayExpiresAtEpochMillis)
            assertNull(trusted?.relayNonce)
            assertNull(trusted?.relayScope)

            val prefs = ApplicationProvider.getApplicationContext<android.content.Context>()
                .localAgentBridgeDataStore
                .data
                .first()
            assertNoStoredRelayRoute(prefs)
            assertTrue(secretStore.secrets.isEmpty())
        }

        store.forgetRuntime()
    }

    @Test
    fun pairingStoreDropsInvalidRelayScopeOnWrite() = runTest {
        val secretStore = FakeRelaySecretStore()
        val store = pairingStore(secretStore)

        nonCanonicalRelayScopeValues().forEach { invalidScope ->
            store.forgetRuntime()

            store.trustRuntime(
                completeRelayRuntime().copy(
                    relayScope = invalidScope,
                )
            )

            val trusted = store.trustedRuntime.first()
            assertEquals("runtime-1", trusted?.deviceId)
            assertEquals("runtime-fingerprint", trusted?.fingerprint)
            assertNull(trusted?.relayHost)
            assertNull(trusted?.relayPort)
            assertNull(trusted?.relayId)
            assertNull(trusted?.relaySecret)
            assertNull(trusted?.relayExpiresAtEpochMillis)
            assertNull(trusted?.relayNonce)
            assertNull(trusted?.relayScope)

            val prefs = ApplicationProvider.getApplicationContext<android.content.Context>()
                .localAgentBridgeDataStore
                .data
                .first()
            assertNoStoredRelayRoute(prefs)
            assertTrue(secretStore.secrets.isEmpty())
        }

        store.forgetRuntime()
    }

    @Test
    fun pairingStoreDropsExpiredCompleteRelayRouteOnWrite() = runTest {
        val secretStore = FakeRelaySecretStore()
        val store = pairingStore(secretStore)
        store.forgetRuntime()

        store.trustRuntime(
            completeRelayRuntime().copy(
                relayExpiresAtEpochMillis = 2_000L,
                relayNonce = "expired-nonce-1",
            )
        )

        val trusted = store.trustedRuntime.first()
        assertEquals("runtime-1", trusted?.deviceId)
        assertNull(trusted?.relayHost)
        assertNull(trusted?.relayPort)
        assertNull(trusted?.relayId)
        assertNull(trusted?.relaySecret)
        assertNull(trusted?.relayExpiresAtEpochMillis)
        assertNull(trusted?.relayNonce)
        assertNull(trusted?.relayScope)
        assertEquals(false, trusted?.hasValidRelayRoute())
        assertEquals(false, trusted?.hasExpiredRelayRoute(nowEpochMillis = 2_001L))

        val prefs = ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .data
            .first()
        assertNoStoredRelayRoute(prefs)
        assertTrue(secretStore.secrets.isEmpty())

        store.forgetRuntime()
    }

    @Test
    fun pairingStoreDropsExpiredCompleteP2pRendezvousRouteOnWrite() = runTest {
        val store = pairingStore()
        store.forgetRuntime()

        store.trustRuntime(
            completeP2pRuntime().copy(
                p2pExpiresAtEpochMillis = 2_000L,
                p2pAntiReplayNonce = "expired-p2p-nonce-1",
            )
        )

        val trusted = store.trustedRuntime.first()
        assertEquals("runtime-1", trusted?.deviceId)
        assertNull(trusted?.p2pRouteClass)
        assertNull(trusted?.p2pRecordId)
        assertNull(trusted?.p2pEncryptedBody)
        assertNull(trusted?.p2pExpiresAtEpochMillis)
        assertNull(trusted?.p2pAntiReplayNonce)
        assertNull(trusted?.p2pProtocolVersion)
        assertEquals(false, trusted?.hasValidP2pRoute())
        assertEquals(false, trusted?.hasExpiredP2pRoute(nowEpochMillis = 2_001L))

        val prefs = ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .data
            .first()
        assertNoStoredP2pRoute(prefs)

        store.forgetRuntime()
    }

    @Test
    fun pairingStoreDropsExpiredStoredRelayRouteOnRead() = runTest {
        val secretStore = FakeRelaySecretStore()
        val store = pairingStore(secretStore)
        store.forgetRuntime()

        ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .edit { prefs ->
                prefs[stringPreferencesKey("runtime_device_id")] = "runtime-1"
                prefs[stringPreferencesKey("runtime_name")] = "AetherLink Runtime"
                prefs[stringPreferencesKey("runtime_fingerprint")] = "runtime-fingerprint"
                prefs[stringPreferencesKey("runtime_public_key")] = "runtime-public-key"
                prefs[stringPreferencesKey("runtime_route_token")] = "route-token"
                prefs[stringPreferencesKey("runtime_relay_host")] = "relay.example.test"
                prefs[intPreferencesKey("runtime_relay_port")] = 443
                prefs[stringPreferencesKey("runtime_relay_id")] = "relay-1"
                prefs[stringPreferencesKey("runtime_relay_secret")] = "secret-1"
                prefs[longPreferencesKey("runtime_relay_expires_at_epoch_millis")] = 2_000L
                prefs[stringPreferencesKey("runtime_relay_nonce")] = "expired-nonce-1"
                prefs[stringPreferencesKey("runtime_relay_scope")] = "remote"
            }

        val trusted = store.trustedRuntime.first()
        assertEquals("runtime-1", trusted?.deviceId)
        assertNull(trusted?.relayHost)
        assertNull(trusted?.relayPort)
        assertNull(trusted?.relayId)
        assertNull(trusted?.relaySecret)
        assertNull(trusted?.relayExpiresAtEpochMillis)
        assertNull(trusted?.relayNonce)
        assertNull(trusted?.relayScope)

        val prefs = ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .data
            .first()
        assertNoStoredRelayRoute(prefs)
        assertTrue(secretStore.secrets.isEmpty())

        store.forgetRuntime()
    }

    @Test
    fun pairingStoreDropsExpiredStoredP2pRendezvousRouteOnRead() = runTest {
        val store = pairingStore()
        store.forgetRuntime()

        ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .edit { prefs ->
                prefs[stringPreferencesKey("runtime_device_id")] = "runtime-1"
                prefs[stringPreferencesKey("runtime_name")] = "AetherLink Runtime"
                prefs[stringPreferencesKey("runtime_fingerprint")] = "runtime-fingerprint"
                prefs[stringPreferencesKey("runtime_public_key")] = "runtime-public-key"
                prefs[stringPreferencesKey("runtime_route_token")] = "route-token"
                prefs[stringPreferencesKey("runtime_p2p_route_class")] = "p2p_rendezvous"
                prefs[stringPreferencesKey("runtime_p2p_record_id")] = "p2p-record-1"
                prefs[stringPreferencesKey("runtime_p2p_encrypted_body")] = "opaque-candidate-1"
                prefs[longPreferencesKey("runtime_p2p_expires_at_epoch_millis")] = 2_000L
                prefs[stringPreferencesKey("runtime_p2p_anti_replay_nonce")] = "expired-p2p-nonce-1"
                prefs[intPreferencesKey("runtime_p2p_protocol_version")] = 1
            }

        val trusted = store.trustedRuntime.first()
        assertEquals("runtime-1", trusted?.deviceId)
        assertNull(trusted?.p2pRouteClass)
        assertNull(trusted?.p2pRecordId)
        assertNull(trusted?.p2pEncryptedBody)
        assertNull(trusted?.p2pExpiresAtEpochMillis)
        assertNull(trusted?.p2pAntiReplayNonce)
        assertNull(trusted?.p2pProtocolVersion)

        val prefs = ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .data
            .first()
        assertNoStoredP2pRoute(prefs)

        store.forgetRuntime()
    }

    @Test
    fun pairingStoreDropsNonCanonicalStoredP2pRendezvousRouteOnRead() = runTest {
        val store = pairingStore()
        store.forgetRuntime()

        ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .edit { prefs ->
                prefs[stringPreferencesKey("runtime_device_id")] = "runtime-1"
                prefs[stringPreferencesKey("runtime_name")] = "AetherLink Runtime"
                prefs[stringPreferencesKey("runtime_fingerprint")] = "runtime-fingerprint"
                prefs[stringPreferencesKey("runtime_public_key")] = "runtime-public-key"
                prefs[stringPreferencesKey("runtime_route_token")] = "route-token"
                prefs[stringPreferencesKey("runtime_p2p_route_class")] = "p2p_rendezvous"
                prefs[stringPreferencesKey("runtime_p2p_record_id")] = "p2p record 1"
                prefs[stringPreferencesKey("runtime_p2p_encrypted_body")] = "opaque-candidate-1"
                prefs[longPreferencesKey("runtime_p2p_expires_at_epoch_millis")] = 4102444800000L
                prefs[stringPreferencesKey("runtime_p2p_anti_replay_nonce")] = "nonce-p2p-1"
                prefs[intPreferencesKey("runtime_p2p_protocol_version")] = 1
            }

        val trusted = store.trustedRuntime.first()
        assertEquals("runtime-1", trusted?.deviceId)
        assertEquals("runtime-fingerprint", trusted?.fingerprint)
        assertNull(trusted?.p2pRouteClass)
        assertNull(trusted?.p2pRecordId)
        assertNull(trusted?.p2pEncryptedBody)
        assertNull(trusted?.p2pExpiresAtEpochMillis)
        assertNull(trusted?.p2pAntiReplayNonce)
        assertNull(trusted?.p2pProtocolVersion)

        val prefs = ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .data
            .first()
        assertNoStoredP2pRoute(prefs)

        store.forgetRuntime()
    }

    @Test
    fun pairingStoreDropsOversizedStoredP2pRendezvousRouteOnRead() = runTest {
        val store = pairingStore()
        store.forgetRuntime()

        ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .edit { prefs ->
                prefs[stringPreferencesKey("runtime_device_id")] = "runtime-1"
                prefs[stringPreferencesKey("runtime_name")] = "AetherLink Runtime"
                prefs[stringPreferencesKey("runtime_fingerprint")] = "runtime-fingerprint"
                prefs[stringPreferencesKey("runtime_public_key")] = "runtime-public-key"
                prefs[stringPreferencesKey("runtime_route_token")] = "route-token"
                prefs[stringPreferencesKey("runtime_p2p_route_class")] = "p2p_rendezvous"
                prefs[stringPreferencesKey("runtime_p2p_record_id")] = "p2p-record-1"
                prefs[stringPreferencesKey("runtime_p2p_encrypted_body")] =
                    "b".repeat(OPAQUE_ROUTE_BODY_MAX_CHARS + 1)
                prefs[longPreferencesKey("runtime_p2p_expires_at_epoch_millis")] = 4102444800000L
                prefs[stringPreferencesKey("runtime_p2p_anti_replay_nonce")] = "nonce-p2p-1"
                prefs[intPreferencesKey("runtime_p2p_protocol_version")] = 1
            }

        val trusted = store.trustedRuntime.first()
        assertEquals("runtime-1", trusted?.deviceId)
        assertEquals("runtime-fingerprint", trusted?.fingerprint)
        assertNull(trusted?.p2pRouteClass)
        assertNull(trusted?.p2pRecordId)
        assertNull(trusted?.p2pEncryptedBody)
        assertNull(trusted?.p2pExpiresAtEpochMillis)
        assertNull(trusted?.p2pAntiReplayNonce)
        assertNull(trusted?.p2pProtocolVersion)

        val prefs = ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .data
            .first()
        assertNoStoredP2pRoute(prefs)

        store.forgetRuntime()
    }

    @Test
    fun pairingStoreMigratesLegacyRawRelaySecretToSecretStoreOnRead() = runTest {
        val secretStore = FakeRelaySecretStore()
        val store = pairingStore(secretStore)
        store.forgetRuntime()

        ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .edit { prefs ->
                prefs[stringPreferencesKey("runtime_device_id")] = "runtime-1"
                prefs[stringPreferencesKey("runtime_name")] = "AetherLink Runtime"
                prefs[stringPreferencesKey("runtime_fingerprint")] = "runtime-fingerprint"
                prefs[stringPreferencesKey("runtime_public_key")] = "runtime-public-key"
                prefs[stringPreferencesKey("runtime_route_token")] = "route-token"
                prefs[stringPreferencesKey("runtime_relay_host")] = "relay.example.test"
                prefs[intPreferencesKey("runtime_relay_port")] = 443
                prefs[stringPreferencesKey("runtime_relay_id")] = "relay-1"
                prefs[stringPreferencesKey("runtime_relay_secret")] = "secret-1"
                prefs[longPreferencesKey("runtime_relay_expires_at_epoch_millis")] = 4102444800000L
                prefs[stringPreferencesKey("runtime_relay_nonce")] = "nonce-route-1"
                prefs[stringPreferencesKey("runtime_relay_scope")] = "remote"
            }

        val trusted = store.trustedRuntime.first()
        assertEquals("secret-1", trusted?.relaySecret)

        val prefs = ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .data
            .first()
        assertNull(prefs[stringPreferencesKey("runtime_relay_secret")])
        val relaySecretRef = prefs[stringPreferencesKey("runtime_relay_secret_ref")]
        assertNotNull(relaySecretRef)
        assertEquals("secret-1", secretStore.secrets[relaySecretRef])

        store.forgetRuntime()
    }

    @Test
    fun pairingStoreDropsRelayRouteWhenStoredSecretRefCannotBeResolved() = runTest {
        val store = pairingStore(FakeRelaySecretStore())
        store.forgetRuntime()

        ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .edit { prefs ->
                prefs[stringPreferencesKey("runtime_device_id")] = "runtime-1"
                prefs[stringPreferencesKey("runtime_name")] = "AetherLink Runtime"
                prefs[stringPreferencesKey("runtime_fingerprint")] = "runtime-fingerprint"
                prefs[stringPreferencesKey("runtime_public_key")] = "runtime-public-key"
                prefs[stringPreferencesKey("runtime_route_token")] = "route-token"
                prefs[stringPreferencesKey("runtime_relay_host")] = "relay.example.test"
                prefs[intPreferencesKey("runtime_relay_port")] = 443
                prefs[stringPreferencesKey("runtime_relay_id")] = "relay-1"
                prefs[stringPreferencesKey("runtime_relay_secret_ref")] = "missing-secret-ref"
                prefs[longPreferencesKey("runtime_relay_expires_at_epoch_millis")] = 4102444800000L
                prefs[stringPreferencesKey("runtime_relay_nonce")] = "nonce-route-1"
                prefs[stringPreferencesKey("runtime_relay_scope")] = "remote"
            }

        val trusted = store.trustedRuntime.first()
        assertEquals("runtime-1", trusted?.deviceId)
        assertNull(trusted?.relaySecret)
        assertNull(trusted?.relayHost)

        val prefs = ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .data
            .first()
        assertNoStoredRelayRoute(prefs)

        store.forgetRuntime()
    }

    @Test
    fun pairingStoreDropsIncompleteRelayRouteOnRead() = runTest {
        val store = pairingStore()
        store.forgetRuntime()

        ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .edit { prefs ->
                prefs[stringPreferencesKey("runtime_device_id")] = "runtime-1"
                prefs[stringPreferencesKey("runtime_name")] = "AetherLink Runtime"
                prefs[stringPreferencesKey("runtime_fingerprint")] = "runtime-fingerprint"
                prefs[stringPreferencesKey("runtime_public_key")] = "runtime-public-key"
                prefs[stringPreferencesKey("runtime_route_token")] = "route-token"
                prefs[stringPreferencesKey("runtime_relay_host")] = "relay.example.test"
                prefs[intPreferencesKey("runtime_relay_port")] = 443
                prefs[stringPreferencesKey("runtime_relay_id")] = "relay-1"
                prefs[longPreferencesKey("runtime_relay_expires_at_epoch_millis")] = 4102444800000L
                prefs[stringPreferencesKey("runtime_relay_nonce")] = "nonce-route-1"
                prefs[stringPreferencesKey("runtime_relay_scope")] = "remote"
            }

        val trusted = store.trustedRuntime.first()
        assertEquals("runtime-1", trusted?.deviceId)
        assertEquals("runtime-fingerprint", trusted?.fingerprint)
        assertNull(trusted?.relayHost)
        assertNull(trusted?.relayPort)
        assertNull(trusted?.relayId)
        assertNull(trusted?.relaySecret)
        assertNull(trusted?.relayExpiresAtEpochMillis)
        assertNull(trusted?.relayNonce)
        assertNull(trusted?.relayScope)

        val prefs = ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .data
            .first()
        assertNoStoredRelayRoute(prefs)

        store.forgetRuntime()
    }

    @Test
    fun pairingStoreDropsNonCanonicalStoredRelayRouteOnRead() = runTest {
        val store = pairingStore()
        val invalidStoredValues: List<Pair<Preferences.Key<String>, String>> =
            nonCanonicalRelayHostValues().map { invalidHost ->
                Pair(stringPreferencesKey("runtime_relay_host"), invalidHost)
            } + listOf(
                Pair(stringPreferencesKey("runtime_relay_id"), "relay 1"),
                Pair(stringPreferencesKey("runtime_relay_secret"), " secret-1"),
                Pair(stringPreferencesKey("runtime_relay_nonce"), "nonce route 1"),
                Pair(stringPreferencesKey("runtime_relay_id"), "r".repeat(OPAQUE_ROUTE_VALUE_MAX_CHARS + 1)),
                Pair(stringPreferencesKey("runtime_relay_secret"), "s".repeat(OPAQUE_ROUTE_VALUE_MAX_CHARS + 1)),
                Pair(stringPreferencesKey("runtime_relay_nonce"), "n".repeat(OPAQUE_ROUTE_VALUE_MAX_CHARS + 1)),
            )

        invalidStoredValues.forEach { (key, invalidValue) ->
            store.forgetRuntime()

            ApplicationProvider.getApplicationContext<android.content.Context>()
                .localAgentBridgeDataStore
                .edit { prefs ->
                    prefs[stringPreferencesKey("runtime_device_id")] = "runtime-1"
                    prefs[stringPreferencesKey("runtime_name")] = "AetherLink Runtime"
                    prefs[stringPreferencesKey("runtime_fingerprint")] = "runtime-fingerprint"
                    prefs[stringPreferencesKey("runtime_public_key")] = "runtime-public-key"
                    prefs[stringPreferencesKey("runtime_route_token")] = "route-token"
                    prefs[stringPreferencesKey("runtime_relay_host")] = "relay.example.test"
                    prefs[intPreferencesKey("runtime_relay_port")] = 443
                    prefs[stringPreferencesKey("runtime_relay_id")] = "relay-1"
                    prefs[stringPreferencesKey("runtime_relay_secret")] = "secret-1"
                    prefs[longPreferencesKey("runtime_relay_expires_at_epoch_millis")] = 4102444800000L
                    prefs[stringPreferencesKey("runtime_relay_nonce")] = "nonce-route-1"
                    prefs[stringPreferencesKey("runtime_relay_scope")] = "remote"
                    prefs[key] = invalidValue
                }

            val trusted = store.trustedRuntime.first()
            assertEquals("runtime-1", trusted?.deviceId)
            assertEquals("runtime-fingerprint", trusted?.fingerprint)
            assertNull(trusted?.relayHost)
            assertNull(trusted?.relayPort)
            assertNull(trusted?.relayId)
            assertNull(trusted?.relaySecret)
            assertNull(trusted?.relayExpiresAtEpochMillis)
            assertNull(trusted?.relayNonce)
            assertNull(trusted?.relayScope)

            val prefs = ApplicationProvider.getApplicationContext<android.content.Context>()
                .localAgentBridgeDataStore
                .data
                .first()
            assertNoStoredRelayRoute(prefs)
        }

        store.forgetRuntime()
    }

    @Test
    fun pairingStoreDropsInvalidStoredRelayScopeOnRead() = runTest {
        val secretStore = FakeRelaySecretStore()
        val store = pairingStore(secretStore)

        nonCanonicalRelayScopeValues().forEach { invalidScope ->
            store.forgetRuntime()

            ApplicationProvider.getApplicationContext<android.content.Context>()
                .localAgentBridgeDataStore
                .edit { prefs ->
                    prefs[stringPreferencesKey("runtime_device_id")] = "runtime-1"
                    prefs[stringPreferencesKey("runtime_name")] = "AetherLink Runtime"
                    prefs[stringPreferencesKey("runtime_fingerprint")] = "runtime-fingerprint"
                    prefs[stringPreferencesKey("runtime_public_key")] = "runtime-public-key"
                    prefs[stringPreferencesKey("runtime_route_token")] = "route-token"
                    prefs[stringPreferencesKey("runtime_relay_host")] = "relay.example.test"
                    prefs[intPreferencesKey("runtime_relay_port")] = 443
                    prefs[stringPreferencesKey("runtime_relay_id")] = "relay-1"
                    prefs[stringPreferencesKey("runtime_relay_secret")] = "secret-1"
                    prefs[longPreferencesKey("runtime_relay_expires_at_epoch_millis")] = 4102444800000L
                    prefs[stringPreferencesKey("runtime_relay_nonce")] = "nonce-route-1"
                    prefs[stringPreferencesKey("runtime_relay_scope")] = invalidScope
                }

            val trusted = store.trustedRuntime.first()
            assertEquals("runtime-1", trusted?.deviceId)
            assertEquals("runtime-fingerprint", trusted?.fingerprint)
            assertNull(trusted?.relayHost)
            assertNull(trusted?.relayPort)
            assertNull(trusted?.relayId)
            assertNull(trusted?.relaySecret)
            assertNull(trusted?.relayExpiresAtEpochMillis)
            assertNull(trusted?.relayNonce)
            assertNull(trusted?.relayScope)

            val prefs = ApplicationProvider.getApplicationContext<android.content.Context>()
                .localAgentBridgeDataStore
                .data
                .first()
            assertNoStoredRelayRoute(prefs)
            assertTrue(secretStore.secrets.isEmpty())
        }

        store.forgetRuntime()
    }

    @Test
    fun pairingStoreDropsIncompleteP2pRendezvousRouteOnRead() = runTest {
        val store = pairingStore()
        store.forgetRuntime()

        ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .edit { prefs ->
                prefs[stringPreferencesKey("runtime_device_id")] = "runtime-1"
                prefs[stringPreferencesKey("runtime_name")] = "AetherLink Runtime"
                prefs[stringPreferencesKey("runtime_fingerprint")] = "runtime-fingerprint"
                prefs[stringPreferencesKey("runtime_public_key")] = "runtime-public-key"
                prefs[stringPreferencesKey("runtime_route_token")] = "route-token"
                prefs[stringPreferencesKey("runtime_p2p_route_class")] = "p2p_rendezvous"
                prefs[stringPreferencesKey("runtime_p2p_record_id")] = "p2p-record-1"
                prefs[longPreferencesKey("runtime_p2p_expires_at_epoch_millis")] = 4102444800000L
                prefs[stringPreferencesKey("runtime_p2p_anti_replay_nonce")] = "nonce-p2p-1"
                prefs[intPreferencesKey("runtime_p2p_protocol_version")] = 1
            }

        val trusted = store.trustedRuntime.first()
        assertEquals("runtime-1", trusted?.deviceId)
        assertEquals("runtime-fingerprint", trusted?.fingerprint)
        assertNull(trusted?.p2pRouteClass)
        assertNull(trusted?.p2pRecordId)
        assertNull(trusted?.p2pEncryptedBody)
        assertNull(trusted?.p2pExpiresAtEpochMillis)
        assertNull(trusted?.p2pAntiReplayNonce)
        assertNull(trusted?.p2pProtocolVersion)

        val prefs = ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore
            .data
            .first()
        assertNoStoredP2pRoute(prefs)

        store.forgetRuntime()
    }

    @Test
    fun pairingStoreForgetRuntimeClearsRelayRoute() = runTest {
        val secretStore = FakeRelaySecretStore()
        val store = pairingStore(secretStore)
        store.forgetRuntime()
        store.trustRuntime(completeRelayRuntime())

        assertTrue(secretStore.secrets.isNotEmpty())

        store.forgetRuntime()

        assertNull(store.trustedRuntime.first())
        assertTrue(secretStore.secrets.isEmpty())
    }

    @Test
    fun productionPairStatePersistsCanonicalSnapshotAcrossRestartAndNilTrustRefresh() = runTest {
        val store = pairingStore()
        store.forgetRuntime()
        val runtime = productionTrustedRuntime()
        store.trustRuntime(runtime)

        val committed = store.applyVerifiedProductionPairTransition(
            expectedRuntimeDeviceId = runtime.deviceId,
            expectedRuntimeFingerprint = runtime.fingerprint,
            transition = initialProductionTransition(),
        )
        store.trustRuntime(runtime.copy(name = "Renamed Runtime"))

        val restarted = pairingStore().trustedRuntime.first()
        assertEquals("Renamed Runtime", restarted?.name)
        assertEquals(
            ProductionPairStateLoadState.Valid(committed),
            restarted?.productionPairStateLoadState,
        )
        assertEquals(committed, restarted?.productionPairState)
        val encoded = ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore.data.first()[stringPreferencesKey(PRODUCTION_PAIR_STATE_KEY)]
        assertEquals(
            Base64.getEncoder().encodeToString(committed.canonicalBytes()),
            encoded,
        )

        store.forgetRuntime()
    }

    @Test
    fun mismatchedProductionPairStateFingerprintRemainsStoredAndProjectsInvalidPresent() = runTest {
        val store = pairingStore()
        store.forgetRuntime()
        val runtime = productionTrustedRuntime()
        store.trustRuntime(runtime)
        val mismatched = ProductionPairStateSnapshot(
            authority = initialProductionTransition().nextAuthority.copy(
                runtimeIdentityFingerprint = "f".repeat(64),
            ),
            localRevision = 1uL,
        )
        val encodedMismatch = Base64.getEncoder().encodeToString(mismatched.canonicalBytes())
        ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore.edit { prefs ->
                prefs[stringPreferencesKey(PRODUCTION_PAIR_STATE_KEY)] = encodedMismatch
            }

        val projected = store.trustedRuntime.first()

        assertEquals(
            ProductionPairStateLoadState.InvalidPresent,
            projected?.productionPairStateLoadState,
        )
        assertNull(projected?.productionPairState)
        assertEquals(encodedMismatch, storedProductionPairStateBase64())

        store.forgetRuntime()
    }

    @Test
    fun corruptProductionPairStateRemainsStoredAndFailsTransitionClosed() = runTest {
        val store = pairingStore()
        store.forgetRuntime()
        val runtime = productionTrustedRuntime()
        store.trustRuntime(runtime)
        ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore.edit { prefs ->
                prefs[stringPreferencesKey(PRODUCTION_PAIR_STATE_KEY)] = "not-canonical-base64!"
            }

        val projected = store.trustedRuntime.first()
        assertEquals(
            ProductionPairStateLoadState.InvalidPresent,
            projected?.productionPairStateLoadState,
        )
        assertNull(projected?.productionPairState)
        val failure = runCatching {
            store.applyVerifiedProductionPairTransition(
                expectedRuntimeDeviceId = runtime.deviceId,
                expectedRuntimeFingerprint = runtime.fingerprint,
                transition = initialProductionTransition(),
            )
        }.exceptionOrNull()

        assertEquals(
            ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE,
            (failure as? ProductionPairStateException)?.reason,
        )
        val encoded = ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore.data.first()[stringPreferencesKey(PRODUCTION_PAIR_STATE_KEY)]
        assertEquals("not-canonical-base64!", encoded)

        store.forgetRuntime()
    }

    @Test
    fun productionAdmissionWithoutStateFailsClosedWithoutCreatingState() = runTest {
        val store = pairingStore()
        store.forgetRuntime()
        val runtime = productionTrustedRuntime()
        store.trustRuntime(runtime)
        val route = productionRoute()

        val failure = runCatching {
            store.admitProductionSecureSession(
                expectedRuntimeDeviceId = runtime.deviceId,
                expectedRuntimeFingerprint = runtime.fingerprint,
                transcript = productionTranscript(route),
                routeAuthorization = route,
            )
        }.exceptionOrNull()

        assertEquals(
            ProductionPairStateRejectionReason.MISSING_CURRENT_STATE,
            (failure as? ProductionPairStateException)?.reason,
        )
        val prefs = ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore.data.first()
        assertNull(prefs[stringPreferencesKey(PRODUCTION_PAIR_STATE_KEY)])

        store.forgetRuntime()
    }

    @Test
    fun verifiedProductionTransitionIsIdempotentAndAdvancesMonotonically() = runTest {
        val store = pairingStore()
        store.forgetRuntime()
        val runtime = productionTrustedRuntime()
        store.trustRuntime(runtime)
        val initialTransition = initialProductionTransition()
        val initial = store.applyVerifiedProductionPairTransition(
            runtime.deviceId,
            runtime.fingerprint,
            initialTransition,
        )

        val idempotent = store.applyVerifiedProductionPairTransition(
            runtime.deviceId,
            runtime.fingerprint,
            initialTransition,
        )
        assertEquals(initial, idempotent)

        val nextAuthority = initial.authority.copy(
            generation = initial.authority.generation + 1uL,
            transitionId = "f".repeat(64),
            transitionRequestDigest = "1".repeat(64),
            acceptedReceiptDigest = "2".repeat(64),
            authorityRevision = initial.authority.authorityRevision + 1uL,
        )
        val advanced = store.applyVerifiedProductionPairTransition(
            runtime.deviceId,
            runtime.fingerprint,
            ProductionPairStateTransition(
                expectedPreviousAuthorityDigest = initial.authority.digestHex(),
                nextAuthority = nextAuthority,
            ),
        )

        assertEquals(2uL, advanced.localRevision)
        assertEquals(8uL, advanced.authority.generation)

        store.forgetRuntime()
    }

    @Test
    fun productionPairStateRollbackIsRejectedWithoutChangingPersistedBytes() = runTest {
        val store = pairingStore()
        store.forgetRuntime()
        val runtime = productionTrustedRuntime()
        store.trustRuntime(runtime)
        val initial = store.applyVerifiedProductionPairTransition(
            runtime.deviceId,
            runtime.fingerprint,
            initialProductionTransition(),
        )
        val before = storedProductionPairStateBase64()
        val rollback = initial.authority.copy(
            generation = initial.authority.generation - 1uL,
            transitionId = "f".repeat(64),
            transitionRequestDigest = "1".repeat(64),
            acceptedReceiptDigest = "2".repeat(64),
            authorityRevision = initial.authority.authorityRevision + 1uL,
        )

        val failure = runCatching {
            store.applyVerifiedProductionPairTransition(
                runtime.deviceId,
                runtime.fingerprint,
                ProductionPairStateTransition(initial.authority.digestHex(), rollback),
            )
        }.exceptionOrNull()

        assertEquals(
            ProductionPairStateRejectionReason.NON_MONOTONIC_GENERATION,
            (failure as? ProductionPairStateException)?.reason,
        )
        assertEquals(before, storedProductionPairStateBase64())

        store.forgetRuntime()
    }

    @Test
    fun productionAdmissionPersistsReplayBeforeReturningPermitAndRejectsRetry() = runTest {
        val store = pairingStore()
        store.forgetRuntime()
        val runtime = productionTrustedRuntime()
        store.trustRuntime(runtime)
        store.applyVerifiedProductionPairTransition(
            runtime.deviceId,
            runtime.fingerprint,
            initialProductionTransition(),
        )
        val route = productionRoute()
        val transcript = productionTranscript(route)

        val permit: ProductionPairAdmissionPermit = store.admitProductionSecureSession(
            runtime.deviceId,
            runtime.fingerprint,
            transcript,
            route,
        )
        val prepared = ProductionPairStateAdmission.admit(transcript, route, current =
            ProductionPairStateSnapshot(initialProductionTransition().nextAuthority, 1uL))
        assertEquals(prepared.bindingDigest, permit.bindingDigest)
        assertEquals(transcript.sessionId, permit.sessionId)
        assertEquals(prepared.transcriptDigest, permit.transcriptDigest)
        assertEquals(prepared.routeAuthorizationDigest, permit.routeAuthorizationDigest)
        assertEquals(prepared.pairAuthorityDigest, permit.pairAuthorityDigest)
        assertEquals(prepared.pairSnapshotDigest, permit.pairSnapshotDigest)
        assertTrue(
            runCatching {
                ProductionPairAdmissionPermit(
                    permit.bindingDigest,
                    permit.sessionId,
                    permit.transcriptDigest,
                    permit.routeAuthorizationDigest,
                    permit.pairAuthorityDigest,
                    permit.previousPairSnapshotDigest,
                    permit.pairSnapshotDigest,
                    Any(),
                )
            }.isFailure,
        )
        val restarted = pairingStore().trustedRuntime.first()?.productionPairState
        assertEquals(2uL, restarted?.localRevision)
        assertEquals(transcript.sessionId, restarted?.consumedEntries?.single()?.sessionId)

        val replayFailure = runCatching {
            store.admitProductionSecureSession(
                runtime.deviceId,
                runtime.fingerprint,
                transcript,
                route,
            )
        }.exceptionOrNull()
        assertEquals(
            ProductionPairStateRejectionReason.SESSION_REPLAY,
            (replayFailure as? ProductionPairStateException)?.reason,
        )
        assertEquals(2uL, pairingStore().trustedRuntime.first()?.productionPairState?.localRevision)

        store.forgetRuntime()
    }

    @Test
    fun trustRuntimeCannotOverwriteProductionStateAndForgetExplicitlyRemovesIt() = runTest {
        val store = pairingStore()
        store.forgetRuntime()
        val runtime = productionTrustedRuntime()
        store.trustRuntime(runtime)
        val current = store.applyVerifiedProductionPairTransition(
            runtime.deviceId,
            runtime.fingerprint,
            initialProductionTransition(),
        )
        val differentState = ProductionPairStateSnapshot(
            authority = current.authority.copy(
                generation = current.authority.generation + 1uL,
                transitionId = "f".repeat(64),
                authorityRevision = current.authority.authorityRevision + 1uL,
            ),
            localRevision = current.localRevision + 1uL,
        )

        assertTrue(
            runCatching {
                store.trustRuntime(
                    runtime.copy(
                        productionPairStateLoadState = ProductionPairStateLoadState.Valid(differentState),
                    )
                )
            }.isFailure
        )
        assertTrue(
            runCatching {
                store.forgetRuntime()
                store.trustRuntime(
                    runtime.copy(
                        productionPairStateLoadState = ProductionPairStateLoadState.InvalidPresent,
                    )
                )
            }.isFailure
        )
        store.trustRuntime(runtime)
        store.applyVerifiedProductionPairTransition(
            runtime.deviceId,
            runtime.fingerprint,
            initialProductionTransition(),
        )
        assertTrue(
            runCatching {
                store.trustRuntime(runtime.copy(deviceId = "runtime-2"))
            }.isFailure
        )
        assertEquals(current, store.trustedRuntime.first()?.productionPairState)

        store.forgetRuntime()
        assertNull(store.trustedRuntime.first())
        assertNull(storedProductionPairStateBase64())
    }

    @Test
    fun rawProductionMutationApisAreJvmSyntheticAndVerifiedApisRemainPublic() {
        val methods = PairingStore::class.java.declaredMethods.toList()

        listOf(
            "applyVerifiedProductionPairTransition",
            "admitProductionSecureSession",
        ).forEach { rawName ->
            val rawMethods = methods.filter { it.name.startsWith(rawName) }
            assertTrue("Missing raw compatibility method $rawName", rawMethods.isNotEmpty())
            assertTrue("Raw compatibility method $rawName must be JVM synthetic", rawMethods.all { it.isSynthetic })
        }
        listOf(
            "applyVerifiedProductionC1FreshPairTransition",
            "admitVerifiedProductionC1SecureSession",
        ).forEach { verifiedName ->
            assertTrue(
                "Missing public verifier-minted method $verifiedName",
                methods.any { it.name == verifiedName && !it.isSynthetic },
            )
        }
    }

    @Test
    fun verifierMintedProductionApisUseTrustedClockPersistAndRemainIdempotent() = runTest {
        val fixture = verifiedStoreFixture()
        val store = pairingStore(productionNowMs = fixture.now)
        store.forgetRuntime()
        store.trustRuntime(fixture.runtime)
        ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore.edit { prefs ->
                prefs[stringPreferencesKey(PRODUCTION_PAIR_STATE_KEY)] =
                    Base64.getEncoder().encodeToString(fixture.previousSnapshot.canonicalBytes())
            }

        val applied = store.applyVerifiedProductionC1FreshPairTransition(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            fixture.freshTransition,
        )
        assertEquals(fixture.nextSnapshot, applied)
        val exactAppliedBytes = storedProductionPairStateBase64()

        val idempotent = store.applyVerifiedProductionC1FreshPairTransition(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            fixture.freshTransition,
        )
        assertEquals(applied, idempotent)
        assertEquals(exactAppliedBytes, storedProductionPairStateBase64())

        val permit: VerifiedProductionC1AdmissionPermit =
            store.admitVerifiedProductionC1SecureSession(
                fixture.runtime.deviceId,
                fixture.runtime.fingerprint,
                fixture.transcriptBinding,
            )
        val expectedPreparation = ProductionC1PairStateAdmission.admit(
            fixture.transcriptBinding,
            fixture.nextSnapshot,
        )
        assertEquals(expectedPreparation.bindingDigest, permit.bindingDigest)
        assertEquals(expectedPreparation.sessionId, permit.sessionId)
        assertEquals(expectedPreparation.transcriptDigest, permit.transcriptDigest)
        assertEquals(expectedPreparation.routeAuthorizationDigest, permit.routeAuthorizationDigest)
        assertEquals(expectedPreparation.routePlanDigest, permit.routePlanDigest)
        assertEquals(expectedPreparation.previousPairSnapshotDigest, permit.previousPairSnapshotDigest)
        assertEquals(expectedPreparation.pairSnapshotDigest, permit.pairSnapshotDigest)
        assertEquals(expectedPreparation.effectiveNotBeforeMs, permit.effectiveNotBeforeMs)
        assertEquals(expectedPreparation.expiresAtMs, permit.expiresAtMs)
        assertTrue(
            runCatching {
                VerifiedProductionC1AdmissionPermit(
                    permit.bindingDigest,
                    permit.sessionId,
                    permit.transcriptDigest,
                    permit.routeAuthorizationDigest,
                    permit.routePlanDigest,
                    permit.previousPairSnapshotDigest,
                    permit.pairSnapshotDigest,
                    permit.effectiveNotBeforeMs,
                    permit.expiresAtMs,
                    Any(),
                )
            }.isFailure,
        )
        val admitted = store.trustedRuntime.first()?.productionPairState
        assertEquals(fixture.nextSnapshot.localRevision + 1uL, admitted?.localRevision)
        assertEquals(fixture.transcriptBinding.transcript.sessionId, admitted?.consumedEntries?.last()?.sessionId)

        store.forgetRuntime()
    }

    @Test
    fun verifiedSecureSessionExpiryBeforePersistenceLeavesExactBytesUnchanged() = runTest {
        val fixture = verifiedStoreFixture()
        val preparation = ProductionC1PairStateAdmission.admit(
            fixture.transcriptBinding,
            fixture.nextSnapshot,
        )
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        var trustedClockReads = 0
        val store = PairingStore(
            context,
            FakeRelaySecretStore(),
            ProductionC1EndpointPersistenceHooks(),
            ProductionC1TrustedClock {
                trustedClockReads += 1
                preparation.expiresAtMs
            },
        )
        store.forgetRuntime()
        store.trustRuntime(fixture.runtime)
        context.localAgentBridgeDataStore.edit { prefs ->
            prefs[stringPreferencesKey(PRODUCTION_PAIR_STATE_KEY)] =
                Base64.getEncoder().encodeToString(fixture.nextSnapshot.canonicalBytes())
        }
        val before = storedProductionPairStateBase64()

        val failure = runCatching {
            store.admitVerifiedProductionC1SecureSession(
                fixture.runtime.deviceId,
                fixture.runtime.fingerprint,
                fixture.transcriptBinding,
            )
        }.exceptionOrNull()

        assertEquals(ProductionC1Error.EXPIRED, (failure as? ProductionC1Exception)?.reason)
        assertEquals(1, trustedClockReads)
        assertEquals(before, storedProductionPairStateBase64())
        assertEquals(fixture.nextSnapshot, store.trustedRuntime.first()?.productionPairState)
        store.forgetRuntime()
    }

    @Test
    fun verifiedSecureSessionExpiryAfterReadbackPersistsTombstoneAndRetryCannotAuthorize() = runTest {
        val fixture = verifiedStoreFixture()
        val preparation = ProductionC1PairStateAdmission.admit(
            fixture.transcriptBinding,
            fixture.nextSnapshot,
        )
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        var trustedClockReads = 0
        val store = PairingStore(
            context,
            FakeRelaySecretStore(),
            ProductionC1EndpointPersistenceHooks(),
            ProductionC1TrustedClock {
                trustedClockReads += 1
                if (trustedClockReads == 1) fixture.now else preparation.expiresAtMs
            },
        )
        store.forgetRuntime()
        store.trustRuntime(fixture.runtime)
        context.localAgentBridgeDataStore.edit { prefs ->
            prefs[stringPreferencesKey(PRODUCTION_PAIR_STATE_KEY)] =
                Base64.getEncoder().encodeToString(fixture.nextSnapshot.canonicalBytes())
        }

        val failure = runCatching {
            store.admitVerifiedProductionC1SecureSession(
                fixture.runtime.deviceId,
                fixture.runtime.fingerprint,
                fixture.transcriptBinding,
            )
        }.exceptionOrNull()

        assertEquals(ProductionC1Error.EXPIRED, (failure as? ProductionC1Exception)?.reason)
        assertEquals(2, trustedClockReads)
        val persisted = store.trustedRuntime.first()?.productionPairState
        assertEquals(preparation.nextSnapshot, persisted)
        assertEquals(preparation.sessionId, persisted?.consumedEntries?.last()?.sessionId)
        val exactPersistedBytes = storedProductionPairStateBase64()

        val retryFailure = runCatching {
            store.admitVerifiedProductionC1SecureSession(
                fixture.runtime.deviceId,
                fixture.runtime.fingerprint,
                fixture.transcriptBinding,
            )
        }.exceptionOrNull()
        assertEquals(
            ProductionPairStateRejectionReason.SESSION_REPLAY,
            (retryFailure as? ProductionPairStateException)?.reason,
        )
        assertEquals(2, trustedClockReads)
        assertEquals(exactPersistedBytes, storedProductionPairStateBase64())
        store.forgetRuntime()
    }

    @Test
    fun verifiedSecureSessionTrustedClockRegressionAfterReadbackWithholdsPermit() = runTest {
        val fixture = verifiedStoreFixture()
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        var trustedClockReads = 0
        val store = PairingStore(
            context,
            FakeRelaySecretStore(),
            ProductionC1EndpointPersistenceHooks(),
            ProductionC1TrustedClock {
                trustedClockReads += 1
                if (trustedClockReads == 1) fixture.now else fixture.now - 1uL
            },
        )
        store.forgetRuntime()
        store.trustRuntime(fixture.runtime)
        context.localAgentBridgeDataStore.edit { prefs ->
            prefs[stringPreferencesKey(PRODUCTION_PAIR_STATE_KEY)] =
                Base64.getEncoder().encodeToString(fixture.nextSnapshot.canonicalBytes())
        }

        val failure = runCatching {
            store.admitVerifiedProductionC1SecureSession(
                fixture.runtime.deviceId,
                fixture.runtime.fingerprint,
                fixture.transcriptBinding,
            )
        }.exceptionOrNull()

        assertEquals(ProductionC1Error.STATE_MISMATCH, (failure as? ProductionC1Exception)?.reason)
        assertEquals(2, trustedClockReads)
        assertEquals(
            fixture.transcriptBinding.transcript.sessionId,
            store.trustedRuntime.first()?.productionPairState?.consumedEntries?.last()?.sessionId,
        )
        store.forgetRuntime()
    }

    @Test
    fun endpointCompoundCommitReturnsTokenOnlyAfterExactReadbackAndRestartIsNonAuthorizing() = runTest {
        val fixture = endpointPersistenceFixture()
        val store = pairingStore(productionNowMs = fixture.now)
        store.forgetRuntime()
        store.trustRuntime(fixture.runtime)
        store.applyVerifiedProductionPairTransition(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            ProductionPairStateTransition(null, fixture.chain.authority),
        )
        val preparation = fixture.appliedPreparation()

        val outcome = store.commitPreparedProductionC1EndpointGrant(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            requireNotNull(fixture.runtime.publicKeyBase64),
            preparation,
        )
        val committed = outcome as ProductionC1EndpointGrantCommitOutcome.Committed
        assertEquals(preparation.entry.admissionId, committed.token.admissionId)
        assertEquals(preparation.entry.sessionId, committed.token.sessionId)
        assertEquals(preparation.entry.routeAuthorizationDigest, committed.token.routeAuthorizationDigest)
        assertEquals(
            sha256Hex(ProductionSecureSessionCodec.encode(fixture.chain.authorizations.finalP2PDirect)),
            committed.token.routeAuthorizationDigest,
        )
        assertEquals(preparation.entry.grantAuthorizationDigest, committed.token.grantAuthorizationDigest)
        assertEquals(
            fixture.chain.grant.grantAuthorization.digestHex,
            committed.token.grantAuthorizationDigest,
        )
        assertEquals(fixture.chain.transcript.routeAuthorizationDigest, committed.token.grantAuthorizationDigest)
        assertTrue(committed.token.routeAuthorizationDigest != committed.token.grantAuthorizationDigest)
        assertEquals(fixture.chain.authority.digestHex(), committed.token.pairAuthorityDigest)
        assertEquals(preparation.nextPairSnapshot.digestHex(), committed.token.pairSnapshotDigest)
        assertEquals(preparation.effectiveNotBeforeMs, committed.token.effectiveNotBeforeMs)
        assertEquals(preparation.expiresAtMs, committed.token.expiresAtMs)
        val committedEncoding = storedEndpointCompoundBase64()
        val committedState = StoredProductionC1EndpointCompoundState.decode(
            Base64.getDecoder().decode(requireNotNull(committedEncoding)),
        )
        val committedMarker = committedState.markers.single()
        assertEquals(preparation.entry.sessionId, committedMarker.sessionId)
        assertEquals(preparation.entry.routeAuthorizationDigest, committedMarker.routeAuthorizationDigest)
        assertEquals(preparation.entry.grantAuthorizationDigest, committedMarker.grantAuthorizationDigest)
        assertEquals(fixture.chain.authority.digestHex(), committedMarker.pairAuthorityDigest)
        val invalidWindowMarker = committedMarker.canonicalBytes()
        System.arraycopy(
            invalidWindowMarker,
            ENDPOINT_MARKER_EFFECTIVE_NOT_BEFORE_OFFSET + ULong.SIZE_BYTES,
            invalidWindowMarker,
            ENDPOINT_MARKER_EFFECTIVE_NOT_BEFORE_OFFSET,
            ULong.SIZE_BYTES,
        )
        val invalidWindowFailure = runCatching {
            StoredProductionC1EndpointCommitMarker.decode(invalidWindowMarker)
        }.exceptionOrNull()
        assertEquals(
            ProductionC1EndpointPersistenceFailure.MALFORMED_CANONICAL,
            (invalidWindowFailure as? ProductionC1EndpointPersistenceException)?.failure,
        )
        fun corruptedCompoundFailure(relativeMarkerOffset: Int): ProductionC1EndpointPersistenceFailure? {
            val compoundBytes = Base64.getDecoder().decode(requireNotNull(committedEncoding))
            val markerBytes = committedMarker.canonicalBytes()
            val markerOffset = compoundBytes.indexOfSubsequence(markerBytes)
            check(markerOffset >= 0)
            compoundBytes[markerOffset + relativeMarkerOffset] =
                (compoundBytes[markerOffset + relativeMarkerOffset].toInt() xor 1).toByte()
            return (runCatching {
                StoredProductionC1EndpointCompoundState.decode(compoundBytes)
            }.exceptionOrNull() as? ProductionC1EndpointPersistenceException)?.failure
        }
        assertEquals(
            ProductionC1EndpointPersistenceFailure.COMMIT_CHAIN_MISMATCH,
            corruptedCompoundFailure(ENDPOINT_MARKER_SESSION_ID_OFFSET),
        )
        assertEquals(
            ProductionC1EndpointPersistenceFailure.COMMIT_CHAIN_MISMATCH,
            corruptedCompoundFailure(ENDPOINT_MARKER_ROUTE_AUTHORIZATION_DIGEST_OFFSET),
        )
        assertEquals(
            ProductionC1EndpointPersistenceFailure.COMMIT_CHAIN_MISMATCH,
            corruptedCompoundFailure(ENDPOINT_MARKER_GRANT_AUTHORIZATION_DIGEST_OFFSET),
        )
        assertEquals(
            ProductionC1EndpointPersistenceFailure.COMMIT_CHAIN_MISMATCH,
            corruptedCompoundFailure(ENDPOINT_MARKER_PAIR_AUTHORITY_DIGEST_OFFSET),
        )
        val idempotentPairState = store.applyVerifiedProductionPairTransition(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            ProductionPairStateTransition(null, fixture.chain.authority),
        )
        assertEquals(preparation.nextPairSnapshot, idempotentPairState)
        assertEquals(committedEncoding, storedEndpointCompoundBase64())
        assertTrue(
            runCatching {
                store.trustRuntime(
                    fixture.runtime.copy(publicKeyBase64 = "rotated-unverified-public-key"),
                )
            }.isFailure,
        )
        assertEquals(committedEncoding, storedEndpointCompoundBase64())

        val restarted = pairingStore(productionNowMs = fixture.now)
        assertEquals(
            preparation.nextPairSnapshot,
            restarted.trustedRuntime.first()?.productionPairState,
        )
        val readback = restarted.readProductionC1EndpointGrantCommit(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            requireNotNull(fixture.runtime.publicKeyBase64),
            preparation.entry.admissionId,
            preparation.entry.bindingDigest,
        )
        assertEquals(committed.token.markerDigest, readback?.markerDigest)
        assertEquals(committed.token.sessionId, readback?.sessionId)
        assertEquals(committed.token.routeAuthorizationDigest, readback?.routeAuthorizationDigest)
        assertEquals(committed.token.grantAuthorizationDigest, readback?.grantAuthorizationDigest)
        assertEquals(committed.token.pairAuthorityDigest, readback?.pairAuthorityDigest)
        assertEquals(committed.token.effectiveNotBeforeMs, readback?.effectiveNotBeforeMs)
        assertEquals(committed.token.expiresAtMs, readback?.expiresAtMs)

        val retry = fixture.committedRetry(preparation)
        val retryOutcome = restarted.commitPreparedProductionC1EndpointGrant(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            requireNotNull(fixture.runtime.publicKeyBase64),
            retry,
        )
        assertTrue(retryOutcome is ProductionC1EndpointGrantCommitOutcome.AlreadyCommitted)
        val storedBytes = storedEndpointCompoundBase64()!!.let(Base64.getDecoder()::decode)
        assertTrue(!storedBytes.contentContains(fixture.connectorSecret))
        store.forgetRuntime()
    }

    @Test
    fun endpointCompoundWithholdsTokenOnReadbackMismatchAndPrecommitFailureIsAtomic() = runTest {
        val fixture = endpointPersistenceFixture()
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val baseline = pairingStore(productionNowMs = fixture.now)
        baseline.forgetRuntime()
        baseline.trustRuntime(fixture.runtime)
        baseline.applyVerifiedProductionPairTransition(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            ProductionPairStateTransition(null, fixture.chain.authority),
        )
        val preparation = fixture.appliedPreparation()
        val before = storedProductionPairStateBase64()
        val rejected = PairingStore(
            context,
            FakeRelaySecretStore(),
            ProductionC1EndpointPersistenceHooks(beforeCommit = { error("injected") }),
            ProductionC1TrustedClock { fixture.now },
        )
        assertTrue(
            runCatching {
                rejected.commitPreparedProductionC1EndpointGrant(
                    fixture.runtime.deviceId,
                    fixture.runtime.fingerprint,
                    requireNotNull(fixture.runtime.publicKeyBase64),
                    preparation,
                )
            }.isFailure,
        )
        assertEquals(before, storedProductionPairStateBase64())
        assertNull(storedEndpointCompoundBase64())

        val mismatching = PairingStore(
            context,
            FakeRelaySecretStore(),
            ProductionC1EndpointPersistenceHooks(
                afterCommitBeforeReadback = {
                    context.localAgentBridgeDataStore.edit { prefs ->
                        val encoded = requireNotNull(
                            prefs[stringPreferencesKey(PRODUCTION_ENDPOINT_COMPOUND_KEY)]
                        )
                        prefs[stringPreferencesKey(PRODUCTION_ENDPOINT_COMPOUND_KEY)] =
                            encoded.dropLast(1) + if (encoded.last() == 'A') "B" else "A"
                    }
                },
            ),
            ProductionC1TrustedClock { fixture.now },
        )
        val failure = runCatching {
            mismatching.commitPreparedProductionC1EndpointGrant(
                fixture.runtime.deviceId,
                fixture.runtime.fingerprint,
                requireNotNull(fixture.runtime.publicKeyBase64),
                preparation,
            )
        }.exceptionOrNull()
        assertEquals(
            ProductionC1EndpointPersistenceFailure.READBACK_MISMATCH,
            (failure as? ProductionC1EndpointPersistenceException)?.failure,
        )
        baseline.forgetRuntime()
    }

    @Test
    fun expiredEndpointPreparationIsRejectedBeforeEditWithoutChangingStoredBytes() = runTest {
        val fixture = endpointPersistenceFixture()
        val preparation = fixture.appliedPreparation()
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val store = PairingStore(
            context,
            FakeRelaySecretStore(),
            ProductionC1EndpointPersistenceHooks(),
            ProductionC1TrustedClock { preparation.expiresAtMs },
        )
        store.forgetRuntime()
        store.trustRuntime(fixture.runtime)
        store.applyVerifiedProductionPairTransition(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            ProductionPairStateTransition(null, fixture.chain.authority),
        )
        val beforePair = storedProductionPairStateBase64()
        val beforeCompound = storedEndpointCompoundBase64()

        val failure = runCatching {
            store.commitPreparedProductionC1EndpointGrant(
                fixture.runtime.deviceId,
                fixture.runtime.fingerprint,
                requireNotNull(fixture.runtime.publicKeyBase64),
                preparation,
            )
        }.exceptionOrNull()

        assertEquals(
            ProductionC1CandidateCapabilityError.ROUTE_MISMATCH,
            (failure as? ProductionC1CandidateCapabilityException)?.reason,
        )
        assertEquals(beforePair, storedProductionPairStateBase64())
        assertEquals(beforeCompound, storedEndpointCompoundBase64())
        store.forgetRuntime()
    }

    @Test
    fun endpointExpiryAfterReadbackPersistsExactStateButWithholdsToken() = runTest {
        val fixture = endpointPersistenceFixture()
        val preparation = fixture.appliedPreparation()
        var trustedClockReads = 0
        val store = PairingStore(
            ApplicationProvider.getApplicationContext(),
            FakeRelaySecretStore(),
            ProductionC1EndpointPersistenceHooks(),
            ProductionC1TrustedClock {
                trustedClockReads += 1
                if (trustedClockReads == 1) fixture.now else preparation.expiresAtMs
            },
        )
        store.forgetRuntime()
        store.trustRuntime(fixture.runtime)
        store.applyVerifiedProductionPairTransition(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            ProductionPairStateTransition(null, fixture.chain.authority),
        )

        val failure = runCatching {
            store.commitPreparedProductionC1EndpointGrant(
                fixture.runtime.deviceId,
                fixture.runtime.fingerprint,
                requireNotNull(fixture.runtime.publicKeyBase64),
                preparation,
            )
        }.exceptionOrNull()

        assertEquals(2, trustedClockReads)
        assertEquals(
            ProductionC1CandidateCapabilityError.ROUTE_MISMATCH,
            (failure as? ProductionC1CandidateCapabilityException)?.reason,
        )
        assertNull(storedProductionPairStateBase64())
        assertNotNull(storedEndpointCompoundBase64())
        val readback = store.readProductionC1EndpointGrantCommit(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            requireNotNull(fixture.runtime.publicKeyBase64),
            preparation.entry.admissionId,
            preparation.entry.bindingDigest,
        )
        assertNotNull(readback)
        val retry = store.commitPreparedProductionC1EndpointGrant(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            requireNotNull(fixture.runtime.publicKeyBase64),
            fixture.committedRetry(preparation),
        )
        assertTrue(retry is ProductionC1EndpointGrantCommitOutcome.AlreadyCommitted)
        assertEquals(2, trustedClockReads)
        store.forgetRuntime()
    }

    @Test
    fun endpointCompoundSerializesCompetitionRejectsTamperAndClearsOnAppliedTransition() = runTest {
        val fixture = endpointPersistenceFixture()
        val first = pairingStore(productionNowMs = fixture.now)
        first.forgetRuntime()
        first.trustRuntime(fixture.runtime)
        first.applyVerifiedProductionPairTransition(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            ProductionPairStateTransition(null, fixture.chain.authority),
        )
        val preparation = fixture.appliedPreparation()
        val results = listOf(first, pairingStore(productionNowMs = fixture.now)).map { store ->
            async {
                runCatching {
                    store.commitPreparedProductionC1EndpointGrant(
                        fixture.runtime.deviceId,
                        fixture.runtime.fingerprint,
                        requireNotNull(fixture.runtime.publicKeyBase64),
                        preparation,
                    )
                }
            }
        }.awaitAll()
        assertEquals(1, results.count { it.getOrNull() is ProductionC1EndpointGrantCommitOutcome.Committed })
        assertEquals(1, results.count { it.exceptionOrNull() is ProductionC1CandidateCapabilityException })

        first.trustRuntime(fixture.runtime.copy(name = "Renamed Runtime"))
        assertNotNull(storedEndpointCompoundBase64())
        val nextAuthority = preparation.nextPairSnapshot.authority.copy(
            generation = preparation.nextPairSnapshot.authority.generation + 1uL,
            transitionId = "f".repeat(64),
            transitionRequestDigest = "1".repeat(64),
            acceptedReceiptDigest = "2".repeat(64),
            authorityRevision = preparation.nextPairSnapshot.authority.authorityRevision + 1uL,
        )
        first.applyVerifiedProductionPairTransition(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            ProductionPairStateTransition(
                preparation.nextPairSnapshot.authority.digestHex(),
                nextAuthority,
            ),
        )
        assertNull(storedEndpointCompoundBase64())
        assertNotNull(storedProductionPairStateBase64())

        first.forgetRuntime()
        first.trustRuntime(fixture.runtime)
        first.applyVerifiedProductionPairTransition(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            ProductionPairStateTransition(null, fixture.chain.authority),
        )
        first.commitPreparedProductionC1EndpointGrant(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            requireNotNull(fixture.runtime.publicKeyBase64),
            fixture.appliedPreparation(),
        )
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        context.localAgentBridgeDataStore.edit { prefs ->
            val encoded = requireNotNull(prefs[stringPreferencesKey(PRODUCTION_ENDPOINT_COMPOUND_KEY)])
            val bytes = Base64.getDecoder().decode(encoded)
            bytes[bytes.lastIndex] = (bytes.last().toInt() xor 1).toByte()
            prefs[stringPreferencesKey(PRODUCTION_ENDPOINT_COMPOUND_KEY)] =
                Base64.getEncoder().encodeToString(bytes)
        }
        assertEquals(
            ProductionPairStateLoadState.InvalidPresent,
            first.trustedRuntime.first()?.productionPairStateLoadState,
        )
        first.forgetRuntime()
    }

    @Test
    fun invalidTrustedRuntimeCleanupRemovesOrphanPairAndEndpointCompoundState() = runTest {
        val fixture = endpointPersistenceFixture()
        val store = pairingStore(productionNowMs = fixture.now)
        store.forgetRuntime()
        store.trustRuntime(fixture.runtime)
        store.applyVerifiedProductionPairTransition(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            ProductionPairStateTransition(null, fixture.chain.authority),
        )
        store.commitPreparedProductionC1EndpointGrant(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            requireNotNull(fixture.runtime.publicKeyBase64),
            fixture.appliedPreparation(),
        )
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        context.localAgentBridgeDataStore.edit { prefs ->
            prefs[stringPreferencesKey("runtime_device_id")] = " invalid-runtime-id"
        }

        assertNull(store.trustedRuntime.first())
        val prefs = context.localAgentBridgeDataStore.data.first()
        assertNull(prefs[stringPreferencesKey(PRODUCTION_PAIR_STATE_KEY)])
        assertNull(prefs[stringPreferencesKey(PRODUCTION_ENDPOINT_COMPOUND_KEY)])
    }

    @Test
    fun legacySecureSessionAdmissionClearsEndpointCompoundAtomically() = runTest {
        val fixture = endpointPersistenceFixture()
        val store = pairingStore(productionNowMs = fixture.now)
        store.forgetRuntime()
        store.trustRuntime(fixture.runtime)
        store.applyVerifiedProductionPairTransition(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            ProductionPairStateTransition(null, fixture.chain.authority),
        )
        val applied = fixture.appliedPreparation()
        store.commitPreparedProductionC1EndpointGrant(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            requireNotNull(fixture.runtime.publicKeyBase64),
            applied,
        )
        val route = LocalDirectRouteAuthorization(
            pairBindingDigest = fixture.chain.authority.pairBindingDigest,
            pairEpoch = fixture.chain.authority.pairEpoch,
            nominatedPathReceiptDigest = "7".repeat(64),
        )
        val authority = fixture.chain.authority
        val transcript = ProductionSecureSessionTranscript(
            sessionId = "11223344556677889900aabbccddeeff",
            pairBindingDigest = authority.pairBindingDigest,
            pairEpoch = authority.pairEpoch,
            clientIdentityFingerprint = authority.clientIdentityFingerprint,
            runtimeIdentityFingerprint = authority.runtimeIdentityFingerprint,
            clientEphemeralPublicKey = PRODUCTION_CLIENT_EPHEMERAL_KEY_HEX.hexBytes(),
            runtimeEphemeralPublicKey = PRODUCTION_RUNTIME_EPHEMERAL_KEY_HEX.hexBytes(),
            clientNonce = "1123456789abcdeffedcba9876543210",
            runtimeNonce = "efeeddccbbaa99887766554433221100",
            generation = authority.generation,
            serviceConfigVersion = authority.serviceConfigVersion,
            keysetVersion = authority.keysetVersion,
            revocationCounter = authority.revocationCounter,
            routeAuthorizationKind = ProductionRouteAuthorizationKind.LOCAL_DIRECT,
            routeAuthorizationDigest = ProductionSecureSessionCodec.digest(route).lowerHex(),
        )

        store.admitProductionSecureSession(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            transcript,
            route,
        )

        assertNull(storedEndpointCompoundBase64())
        assertEquals(3uL, store.trustedRuntime.first()?.productionPairState?.localRevision)
        store.forgetRuntime()
    }

    @Test
    fun exactBoundStartValidatorAcceptsOnlyCurrentLiveCommitAndTrustedWindow() = runTest {
        val fixture = endpointPersistenceFixture()
        var trustedNow = fixture.now
        val store = PairingStore(
            ApplicationProvider.getApplicationContext(),
            FakeRelaySecretStore(),
            ProductionC1EndpointPersistenceHooks(),
            ProductionC1TrustedClock { trustedNow },
        )
        store.forgetRuntime()
        store.trustRuntime(fixture.runtime)
        store.applyVerifiedProductionPairTransition(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            ProductionPairStateTransition(null, fixture.chain.authority),
        )
        val preparation = fixture.appliedPreparation()
        val token = (store.commitPreparedProductionC1EndpointGrant(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            requireNotNull(fixture.runtime.publicKeyBase64),
            preparation,
        ) as ProductionC1EndpointGrantCommitOutcome.Committed).token
        val request = ProductionC1ExactBoundStartRequest(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            requireNotNull(fixture.runtime.publicKeyBase64),
            token,
            fixture.verifiedBinding,
        )

        val live = store.validateProductionC1ExactBoundStart(request)
        assertEquals(token.markerDigest, live.markerDigest)
        assertEquals(token.pairAuthorityDigest, live.pairAuthorityDigest)

        trustedNow = token.expiresAtMs
        val expiry = runCatching {
            store.validateProductionC1ExactBoundStart(request)
        }.exceptionOrNull() as? ProductionC1ExactBoundStartValidationException
        assertEquals(ProductionC1ExactBoundStartValidationFailure.EXPIRED, expiry?.failure)

        trustedNow = fixture.now
        val advancedAuthority = preparation.nextPairSnapshot.authority.copy(
            generation = preparation.nextPairSnapshot.authority.generation + 1uL,
            transitionId = "8".repeat(64),
            transitionRequestDigest = "9".repeat(64),
            acceptedReceiptDigest = "a".repeat(64),
            authorityRevision = preparation.nextPairSnapshot.authority.authorityRevision + 1uL,
        )
        store.applyVerifiedProductionPairTransition(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            ProductionPairStateTransition(
                preparation.nextPairSnapshot.authority.digestHex(),
                advancedAuthority,
            ),
        )
        val stale = runCatching {
            store.validateProductionC1ExactBoundStart(request)
        }.exceptionOrNull() as? ProductionC1ExactBoundStartValidationException
        assertEquals(ProductionC1ExactBoundStartValidationFailure.STALE_COMMIT, stale?.failure)
        store.forgetRuntime()
    }

    @Test
    fun publicBeginDiscardsClaimedEphemeralKeyWhenEngineDerivationFails() = runTest {
        val authorityFixture = authoritySecureSessionFixture { it.now }
        val request = authorityFixture.request
        val localEphemeralKey = ProductionSecureSessionEphemeralKey.generate()
        val startCapability = authorityFixture.store
            .prepareAuthorityBoundProductionSecureSessionStart(
                expectedRuntimeDeviceId = request.expectedRuntimeDeviceId,
                expectedRuntimeFingerprint = request.expectedRuntimeFingerprint,
                expectedRuntimePublicKey = request.expectedRuntimePublicKey,
                token = request.token,
                binding = request.binding,
                localEphemeralKey = localEphemeralKey,
            )

        val failure = runCatching {
            authorityFixture.store.beginAuthorityBoundProductionSecureSession(startCapability)
        }.exceptionOrNull()

        assertTrue(failure is ProductionSecureSessionCryptoException)
        assertEquals(
            ProductionSecureSessionCryptoError.KEY_MISMATCH,
            (failure as ProductionSecureSessionCryptoException).reason,
        )
        assertTrue(localEphemeralKey.isConsumedOrClosed)
        authorityFixture.store.forgetRuntime()
    }

    @Test
    fun publicEndpointAdmissionMintsOnlyFreshExactStartToken() = runTest {
        val fixture = endpointPersistenceFixture()
        val store = PairingStore(
            ApplicationProvider.getApplicationContext(),
            FakeRelaySecretStore(),
            ProductionC1EndpointPersistenceHooks(),
            ProductionC1TrustedClock { fixture.now },
        )
        store.forgetRuntime()
        store.trustRuntime(fixture.runtime)
        store.applyVerifiedProductionPairTransition(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            ProductionPairStateTransition(null, fixture.chain.authority),
        )

        val token = store.admitVerifiedProductionC1EndpointGrant(
            expectedRuntimeDeviceId = fixture.runtime.deviceId,
            expectedRuntimeFingerprint = fixture.runtime.fingerprint,
            expectedRuntimePublicKey = requireNotNull(fixture.runtime.publicKeyBase64),
            admissionId = ENDPOINT_ADMISSION_ID,
            binding = fixture.verifiedBinding,
        )

        assertEquals(fixture.chain.transcript.sessionId, token.sessionId)
        val replay = runCatching {
            store.admitVerifiedProductionC1EndpointGrant(
                fixture.runtime.deviceId,
                fixture.runtime.fingerprint,
                requireNotNull(fixture.runtime.publicKeyBase64),
                ENDPOINT_ADMISSION_ID,
                fixture.verifiedBinding,
            )
        }.exceptionOrNull()
        assertTrue(replay is ProductionC1CandidateCapabilityException)
        assertEquals(
            ProductionC1CandidateCapabilityError.REPLAY,
            (replay as ProductionC1CandidateCapabilityException).reason,
        )
        store.forgetRuntime()
    }

    @Test
    fun exactBoundStoreAuthorityAdvanceAndForgetAbortActiveResource() = runTest {
        val fixture = endpointPersistenceFixture()
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val store = PairingStore(
            context,
            FakeRelaySecretStore(),
            ProductionC1EndpointPersistenceHooks(),
            ProductionC1TrustedClock { fixture.now },
        )
        store.forgetRuntime()
        store.trustRuntime(fixture.runtime)
        store.applyVerifiedProductionPairTransition(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            ProductionPairStateTransition(null, fixture.chain.authority),
        )
        val preparation = fixture.appliedPreparation()
        val token = (store.commitPreparedProductionC1EndpointGrant(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            requireNotNull(fixture.runtime.publicKeyBase64),
            preparation,
        ) as ProductionC1EndpointGrantCommitOutcome.Committed).token
        val request = ProductionC1ExactBoundStartRequest(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            requireNotNull(fixture.runtime.publicKeyBase64),
            token,
            fixture.verifiedBinding,
        )
        val coordinator = store.exactBoundStartCoordinator()
        var authorityAdvanceAborts = 0
        val handle = coordinator.admit(request)
        coordinator.begin(
            handle,
            request,
            ProductionC1ExactBoundStartOperation(
                start = {},
                abort = { authorityAdvanceAborts += 1 },
            ),
        )
        val advancedAuthority = preparation.nextPairSnapshot.authority.copy(
            generation = preparation.nextPairSnapshot.authority.generation + 1uL,
            transitionId = "b".repeat(64),
            transitionRequestDigest = "c".repeat(64),
            acceptedReceiptDigest = "d".repeat(64),
            authorityRevision = preparation.nextPairSnapshot.authority.authorityRevision + 1uL,
        )
        store.applyVerifiedProductionPairTransition(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            ProductionPairStateTransition(
                preparation.nextPairSnapshot.authority.digestHex(),
                advancedAuthority,
            ),
        )
        assertEquals(1, authorityAdvanceAborts)
        assertEquals(
            ProductionC1ExactBoundStartTerminalReason.AUTHORITY_ADVANCED,
            coordinator.tombstonesForTesting().single().reason,
        )
        store.forgetRuntime()

        val forgetStore = PairingStore(
            context,
            FakeRelaySecretStore(),
            ProductionC1EndpointPersistenceHooks(),
            ProductionC1TrustedClock { fixture.now },
        )
        forgetStore.trustRuntime(fixture.runtime)
        forgetStore.applyVerifiedProductionPairTransition(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            ProductionPairStateTransition(null, fixture.chain.authority),
        )
        val forgetPreparation = fixture.appliedPreparation()
        val forgetToken = (forgetStore.commitPreparedProductionC1EndpointGrant(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            requireNotNull(fixture.runtime.publicKeyBase64),
            forgetPreparation,
        ) as ProductionC1EndpointGrantCommitOutcome.Committed).token
        val forgetRequest = ProductionC1ExactBoundStartRequest(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            requireNotNull(fixture.runtime.publicKeyBase64),
            forgetToken,
            fixture.verifiedBinding,
        )
        val forgetCoordinator = forgetStore.exactBoundStartCoordinator()
        var forgetAborts = 0
        val forgetHandle = forgetCoordinator.admit(forgetRequest)
        forgetCoordinator.begin(
            forgetHandle,
            forgetRequest,
            ProductionC1ExactBoundStartOperation(
                start = {},
                abort = {
                    forgetAborts += 1
                    if (forgetAborts == 1) error("forget abort failed")
                },
            ),
        )
        val firstForgetFailure = runCatching { forgetStore.forgetRuntime() }.exceptionOrNull()
        assertEquals("forget abort failed", firstForgetFailure?.message)
        assertNull(forgetStore.trustedRuntime.first())
        assertEquals(1, forgetCoordinator.pendingAbortCountForTesting())
        forgetStore.forgetRuntime()
        assertEquals(2, forgetAborts)
        assertEquals(0, forgetCoordinator.pendingAbortCountForTesting())
        assertEquals(
            ProductionC1ExactBoundStartTerminalReason.REVOKED,
            forgetCoordinator.tombstonesForTesting().single().reason,
        )
    }

    @Test
    fun exactBoundStoreIdempotentAuthorityMutationRetriesOldAuthorityCleanup() = runTest {
        val fixture = endpointPersistenceFixture()
        val store = PairingStore(
            ApplicationProvider.getApplicationContext(),
            FakeRelaySecretStore(),
            ProductionC1EndpointPersistenceHooks(),
            ProductionC1TrustedClock { fixture.now },
        )
        store.forgetRuntime()
        store.trustRuntime(fixture.runtime)
        store.applyVerifiedProductionPairTransition(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            ProductionPairStateTransition(null, fixture.chain.authority),
        )
        val preparation = fixture.appliedPreparation()
        val token = (store.commitPreparedProductionC1EndpointGrant(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            requireNotNull(fixture.runtime.publicKeyBase64),
            preparation,
        ) as ProductionC1EndpointGrantCommitOutcome.Committed).token
        val request = ProductionC1ExactBoundStartRequest(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            requireNotNull(fixture.runtime.publicKeyBase64),
            token,
            fixture.verifiedBinding,
        )
        val coordinator = store.exactBoundStartCoordinator()
        val handle = coordinator.admit(request)
        var abortAttempts = 0
        coordinator.begin(
            handle,
            request,
            ProductionC1ExactBoundStartOperation(
                start = {},
                abort = {
                    abortAttempts += 1
                    if (abortAttempts == 1) error("authority abort failed")
                },
            ),
        )
        val advancedAuthority = preparation.nextPairSnapshot.authority.copy(
            generation = preparation.nextPairSnapshot.authority.generation + 1uL,
            transitionId = "e".repeat(64),
            transitionRequestDigest = "f".repeat(64),
            acceptedReceiptDigest = "0".repeat(64),
            authorityRevision = preparation.nextPairSnapshot.authority.authorityRevision + 1uL,
        )
        val transition = ProductionPairStateTransition(
            preparation.nextPairSnapshot.authority.digestHex(),
            advancedAuthority,
        )

        val firstFailure = runCatching {
            store.applyVerifiedProductionPairTransition(
                fixture.runtime.deviceId,
                fixture.runtime.fingerprint,
                transition,
            )
        }.exceptionOrNull()
        assertEquals("authority abort failed", firstFailure?.message)
        assertEquals(advancedAuthority.digestHex(),
            store.trustedRuntime.first()?.productionPairState?.authority?.digestHex())
        assertEquals(1, coordinator.pendingAbortCountForTesting())

        val blocked = runCatching {
            coordinator.admitForTesting(
                exactBoundValidation(
                    marker = "a".repeat(64),
                    pair = advancedAuthority.digestHex(),
                    expiresAtMs = fixture.now + 1_000uL,
                    runtimeDeviceId = fixture.runtime.deviceId,
                ),
            ) { it }
        }.exceptionOrNull() as? ProductionC1ExactBoundStartCoordinatorException
        assertEquals(
            ProductionC1ExactBoundStartCoordinatorFailure.PAIR_CLEANUP_PENDING,
            blocked?.failure,
        )

        store.applyVerifiedProductionPairTransition(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            transition,
        )
        assertEquals(2, abortAttempts)
        assertEquals(0, coordinator.pendingAbortCountForTesting())
        val replacement = coordinator.admitForTesting(
            exactBoundValidation(
                marker = "b".repeat(64),
                pair = advancedAuthority.digestHex(),
                expiresAtMs = fixture.now + 1_000uL,
                runtimeDeviceId = fixture.runtime.deviceId,
            ),
        ) { it }
        coordinator.cancel(replacement)
        store.forgetRuntime()
    }

    @Test
    fun exactBoundStoreConcurrentIdempotentMutationWaitsForInFlightCleanupResult() = runTest {
        val fixture = endpointPersistenceFixture()
        val store = PairingStore(
            ApplicationProvider.getApplicationContext(),
            FakeRelaySecretStore(),
            ProductionC1EndpointPersistenceHooks(),
            ProductionC1TrustedClock { fixture.now },
        )
        store.forgetRuntime()
        store.trustRuntime(fixture.runtime)
        store.applyVerifiedProductionPairTransition(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            ProductionPairStateTransition(null, fixture.chain.authority),
        )
        val preparation = fixture.appliedPreparation()
        val token = (store.commitPreparedProductionC1EndpointGrant(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            requireNotNull(fixture.runtime.publicKeyBase64),
            preparation,
        ) as ProductionC1EndpointGrantCommitOutcome.Committed).token
        val request = ProductionC1ExactBoundStartRequest(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            requireNotNull(fixture.runtime.publicKeyBase64),
            token,
            fixture.verifiedBinding,
        )
        val coordinator = store.exactBoundStartCoordinator()
        val handle = coordinator.admit(request)
        val abortEntered = CompletableDeferred<Unit>()
        val abortRelease = CompletableDeferred<Unit>()
        var abortAttempts = 0
        coordinator.begin(
            handle,
            request,
            ProductionC1ExactBoundStartOperation(
                start = {},
                abort = {
                    abortAttempts += 1
                    if (abortAttempts == 1) {
                        abortEntered.complete(Unit)
                        abortRelease.await()
                        error("concurrent authority abort failed")
                    }
                },
            ),
        )
        val advancedAuthority = preparation.nextPairSnapshot.authority.copy(
            generation = preparation.nextPairSnapshot.authority.generation + 1uL,
            transitionId = "1".repeat(64),
            transitionRequestDigest = "2".repeat(64),
            acceptedReceiptDigest = "3".repeat(64),
            authorityRevision = preparation.nextPairSnapshot.authority.authorityRevision + 1uL,
        )
        val transition = ProductionPairStateTransition(
            preparation.nextPairSnapshot.authority.digestHex(),
            advancedAuthority,
        )

        val firstMutation = async {
            runCatching {
                store.applyVerifiedProductionPairTransition(
                    fixture.runtime.deviceId,
                    fixture.runtime.fingerprint,
                    transition,
                )
            }
        }
        abortEntered.await()
        val concurrentRetry = async {
            runCatching { coordinator.retryPendingAborts() }
        }
        yield()
        assertEquals(false, concurrentRetry.isCompleted)

        abortRelease.complete(Unit)
        assertEquals(
            "concurrent authority abort failed",
            firstMutation.await().exceptionOrNull()?.message,
        )
        assertEquals(
            "concurrent authority abort failed",
            concurrentRetry.await().exceptionOrNull()?.message,
        )
        assertEquals(1, abortAttempts)
        assertEquals(1, coordinator.pendingAbortCountForTesting())

        store.applyVerifiedProductionPairTransition(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            transition,
        )
        assertEquals(2, abortAttempts)
        assertEquals(0, coordinator.pendingAbortCountForTesting())
        store.forgetRuntime()
    }

    @Test
    fun authorityBoundSecureSessionIsInvalidatedByAdvanceAndRevocation() = runTest {
        val advanced = authoritySecureSessionFixture { it.now }
        val advancedEngine = RecordingAuthoritySecureSessionEngine()
        val advancedSession = advanced.begin(advancedEngine)
        assertEquals(
            advanced.request.binding.keyScheduleBinding,
            advancedEngine.derivedBinding,
        )
        assertEquals(32, advancedSession.localConfirmation().size)

        advanced.store.applyVerifiedProductionPairTransition(
            advanced.fixture.runtime.deviceId,
            advanced.fixture.runtime.fingerprint,
            advanced.authorityAdvance("1", "2", "3"),
        )
        assertEquals(true, advancedEngine.invalidated)
        assertNotNull(runCatching { advancedSession.activate() }.exceptionOrNull())
        advanced.store.forgetRuntime()

        val revoked = authoritySecureSessionFixture { it.now }
        val revokedEngine = RecordingAuthoritySecureSessionEngine()
        val revokedSession = revoked.begin(revokedEngine)
        revoked.store.forgetRuntime()
        assertEquals(true, revokedEngine.invalidated)
        assertNotNull(runCatching { revokedSession.sealApplication(byteArrayOf(1)) }.exceptionOrNull())
    }

    @Test
    fun authorityBoundSecureSessionExpiresOnTrustedClockFence() = runTest {
        var trustedNow: ULong? = null
        val setup = authoritySecureSessionFixture { trustedNow ?: it.now }
        val engine = RecordingAuthoritySecureSessionEngine()
        val session = setup.begin(engine)
        trustedNow = setup.request.token.expiresAtMs

        setup.coordinator.fenceExpired()

        assertEquals(true, engine.invalidated)
        assertNotNull(runCatching { session.localConfirmation() }.exceptionOrNull())
        setup.store.forgetRuntime()
    }

    @Test
    fun authorityWriterWaitsForDerivationThenFencesPublishedEngine() = runTest {
        val setup = authoritySecureSessionFixture { it.now }
        val deriveEntered = CompletableDeferred<Unit>()
        val deriveRelease = CompletableDeferred<Unit>()
        val engine = RecordingAuthoritySecureSessionEngine()
        val starting = async {
            runCatching {
                ProductionC1AuthorityBoundSecureSession.beginWithFactoryForTesting(
                    setup.coordinator,
                    setup.request,
                    setup.publicationGate,
                    { setup.fixture.now },
                    ProductionC1AuthoritySecureSessionEngineFactory { binding ->
                        engine.derivedBinding = binding
                        deriveEntered.complete(Unit)
                        deriveRelease.await()
                        engine
                    },
                )
            }
        }
        deriveEntered.await()
        val mutation = async {
            runCatching {
                setup.store.applyVerifiedProductionPairTransition(
                    setup.fixture.runtime.deviceId,
                    setup.fixture.runtime.fingerprint,
                    setup.authorityAdvance("4", "5", "6"),
                )
            }
        }
        withTimeout(5_000) {
            while (setup.publicationGate.waitingWriterCountForTesting() == 0) yield()
        }
        assertEquals(false, mutation.isCompleted)
        deriveRelease.complete(Unit)

        val published = starting.await().getOrThrow()
        assertNull(mutation.await().exceptionOrNull())
        assertEquals(true, engine.invalidated)
        assertNotNull(runCatching { published.localConfirmation() }.exceptionOrNull())
        assertEquals(0, setup.coordinator.liveCountForTesting())
        setup.store.forgetRuntime()
    }

    @Test
    fun authorityBoundSecureSessionCloseDrainsInFlightRecordThenRejectsLaterRecords() = runTest {
        val setup = authoritySecureSessionFixture { it.now }
        val sealEntered = CountDownLatch(1)
        val sealRelease = CountDownLatch(1)
        val engine = RecordingAuthoritySecureSessionEngine(sealEntered, sealRelease)
        val session = setup.begin(engine)

        val sealing = async(Dispatchers.Default) {
            runCatching { session.sealApplication("payload".toByteArray()) }
        }
        assertEquals(
            true,
            withContext(Dispatchers.IO) { sealEntered.await(5, TimeUnit.SECONDS) },
        )
        val closing = async(Dispatchers.Default) { runCatching { session.close() } }
        withTimeout(5_000) {
            while (setup.publicationGate.waitingWriterCountForTesting() == 0) yield()
        }
        assertEquals(false, closing.isCompleted)
        sealRelease.countDown()

        val sealed = sealing.await().getOrThrow()
        assertEquals("sealed", String(sealed.record))
        sealed.wipe()
        assertNull(closing.await().exceptionOrNull())
        assertEquals(true, engine.closed)
        assertEquals(0, setup.coordinator.liveCountForTesting())
        assertNotNull(runCatching { session.sealApplication(byteArrayOf(1)) }.exceptionOrNull())
        setup.store.forgetRuntime()
    }

    @Test
    fun atomicConfirmationSendAndMarkHoldsAuthorityPermitAndWipesCallbackBytes() = runTest {
        val setup = authoritySecureSessionFixture { it.now }
        val engine = RecordingAuthoritySecureSessionEngine()
        val session = setup.begin(engine)
        val sendEntered = CompletableDeferred<Unit>()
        val sendRelease = CompletableDeferred<Unit>()
        var callbackBytes: ByteArray? = null
        val sending = async(Dispatchers.Default) {
            runCatching {
                session.sendLocalConfirmationAndMark { confirmation ->
                    callbackBytes = confirmation
                    sendEntered.complete(Unit)
                    sendRelease.await()
                }
            }
        }
        sendEntered.await()
        assertEquals(false, engine.localConfirmationMarked)

        val mutation = async(Dispatchers.Default) {
            runCatching {
                setup.store.applyVerifiedProductionPairTransition(
                    setup.fixture.runtime.deviceId,
                    setup.fixture.runtime.fingerprint,
                    setup.authorityAdvance("6", "7", "8"),
                )
            }
        }
        withTimeout(5_000) {
            while (setup.publicationGate.waitingWriterCountForTesting() == 0) yield()
        }
        assertEquals(false, mutation.isCompleted)

        sendRelease.complete(Unit)
        assertNull(sending.await().exceptionOrNull())
        assertEquals(true, engine.localConfirmationMarked)
        assertTrue(requireNotNull(callbackBytes).all { it == 0.toByte() })
        assertNull(mutation.await().exceptionOrNull())
        setup.store.forgetRuntime()
    }

    @Test
    fun atomicSealSendFailureTerminalizesLeaseAndWipesCallbackBytes() = runTest {
        val setup = authoritySecureSessionFixture { it.now }
        val engine = RecordingAuthoritySecureSessionEngine()
        val session = setup.begin(engine)
        var callbackBytes: ByteArray? = null

        val failure = runCatching {
            session.sealApplicationAndSend("payload".toByteArray()) { record ->
                callbackBytes = record
                throw IOException("record send failed")
            }
        }.exceptionOrNull()

        assertEquals("record send failed", failure?.message)
        assertTrue(requireNotNull(callbackBytes).all { it == 0.toByte() })
        assertEquals(true, engine.invalidated)
        assertEquals(0, setup.coordinator.liveCountForTesting())
        assertNotNull(
            runCatching { session.sealApplicationAndSend(byteArrayOf(1)) {} }.exceptionOrNull(),
        )
        setup.store.forgetRuntime()
    }

    @Test
    fun cancelledAtomicSealSendTerminalizesLeaseAndWipesCallbackBytes() = runTest {
        val setup = authoritySecureSessionFixture { it.now }
        val engine = RecordingAuthoritySecureSessionEngine()
        val session = setup.begin(engine)
        val sendEntered = CompletableDeferred<Unit>()
        val neverRelease = CompletableDeferred<Unit>()
        var callbackBytes: ByteArray? = null
        val sending = async(Dispatchers.Default) {
            session.sealApplicationAndSend("payload".toByteArray()) { record ->
                callbackBytes = record
                sendEntered.complete(Unit)
                neverRelease.await()
            }
        }
        sendEntered.await()
        sending.cancel()

        assertNotNull(runCatching { sending.await() }.exceptionOrNull())
        withTimeout(5_000) {
            while (setup.coordinator.liveCountForTesting() != 0) yield()
        }
        assertTrue(requireNotNull(callbackBytes).all { it == 0.toByte() })
        assertEquals(true, engine.invalidated)
        setup.store.forgetRuntime()
    }

    @Test
    fun atomicOpenPublishHoldsAuthorityPermitAndWipesCallbackPlaintext() = runTest {
        val setup = authoritySecureSessionFixture { it.now }
        val engine = RecordingAuthoritySecureSessionEngine()
        val session = setup.begin(engine)
        val publishEntered = CompletableDeferred<Unit>()
        val publishRelease = CompletableDeferred<Unit>()
        var callbackPlaintext: ByteArray? = null
        var callbackContentType: ProductionSecureSessionRecordContentType? = null
        val publishing = async(Dispatchers.Default) {
            session.openAndPublish("record".toByteArray()) {
                    plaintext,
                    contentType,
                    keyUpdateRequired,
                    terminalAfterRecord,
                ->
                callbackPlaintext = plaintext
                callbackContentType = contentType
                assertEquals(false, keyUpdateRequired)
                assertEquals(false, terminalAfterRecord)
                publishEntered.complete(Unit)
                publishRelease.await()
                "published"
            }
        }
        publishEntered.await()

        val mutation = async(Dispatchers.Default) {
            runCatching {
                setup.store.applyVerifiedProductionPairTransition(
                    setup.fixture.runtime.deviceId,
                    setup.fixture.runtime.fingerprint,
                    setup.authorityAdvance("9", "a", "b"),
                )
            }
        }
        withTimeout(5_000) {
            while (setup.publicationGate.waitingWriterCountForTesting() == 0) yield()
        }
        assertEquals(false, mutation.isCompleted)

        publishRelease.complete(Unit)
        assertEquals("published", publishing.await())
        assertEquals(ProductionSecureSessionRecordContentType.APPLICATION, callbackContentType)
        assertTrue(requireNotNull(callbackPlaintext).all { it == 0.toByte() })
        assertNull(mutation.await().exceptionOrNull())
        setup.store.forgetRuntime()
    }

    @Test
    fun terminalObserverFiresOnceOnAuthorityFenceAndLateInstallIsImmediate() = runTest {
        val fenced = authoritySecureSessionFixture { it.now }
        val fencedEngine = RecordingAuthoritySecureSessionEngine()
        val fencedSession = fenced.begin(fencedEngine)
        val fencedNotifications = AtomicInteger()
        fencedSession.installTerminalObserver { fencedNotifications.incrementAndGet() }

        fenced.store.applyVerifiedProductionPairTransition(
            fenced.fixture.runtime.deviceId,
            fenced.fixture.runtime.fingerprint,
            fenced.authorityAdvance("c", "d", "e"),
        )
        assertEquals(1, fencedNotifications.get())
        fenced.store.forgetRuntime()
        assertEquals(1, fencedNotifications.get())

        val late = authoritySecureSessionFixture { it.now }
        val lateEngine = RecordingAuthoritySecureSessionEngine()
        val lateSession = late.begin(lateEngine)
        late.store.forgetRuntime()
        val lateNotifications = AtomicInteger()
        lateSession.installTerminalObserver { lateNotifications.incrementAndGet() }
        assertEquals(1, lateNotifications.get())
        assertNotNull(
            runCatching {
                lateSession.installTerminalObserver { lateNotifications.incrementAndGet() }
            }.exceptionOrNull(),
        )
        assertEquals(1, lateNotifications.get())
    }

    @Test
    fun terminalObserverFiresOnceWhenAtomicPublicationFails() = runTest {
        val setup = authoritySecureSessionFixture { it.now }
        val engine = RecordingAuthoritySecureSessionEngine()
        val session = setup.begin(engine)
        val notifications = AtomicInteger()
        session.installTerminalObserver { notifications.incrementAndGet() }

        assertNotNull(
            runCatching {
                session.sealApplicationAndSend("payload".toByteArray()) {
                    throw IOException("socket closed")
                }
            }.exceptionOrNull(),
        )
        assertEquals(1, notifications.get())
        session.close()
        assertEquals(1, notifications.get())
        setup.store.forgetRuntime()
    }

    @Test
    fun authorityWriterWaitsForInFlightSealAndFencesEveryLaterPublication() = runTest {
        val setup = authoritySecureSessionFixture { it.now }
        val sealEntered = CountDownLatch(1)
        val sealRelease = CountDownLatch(1)
        val engine = RecordingAuthoritySecureSessionEngine(sealEntered, sealRelease)
        val session = setup.begin(engine)
        val sealing = async(Dispatchers.Default) {
            runCatching { session.sealApplication("before-commit".toByteArray()) }
        }
        assertEquals(
            true,
            withContext(Dispatchers.IO) { sealEntered.await(5, TimeUnit.SECONDS) },
        )
        val mutation = async(Dispatchers.Default) {
            runCatching {
                setup.store.applyVerifiedProductionPairTransition(
                    setup.fixture.runtime.deviceId,
                    setup.fixture.runtime.fingerprint,
                    setup.authorityAdvance("7", "8", "9"),
                )
            }
        }
        withTimeout(5_000) {
            while (setup.publicationGate.waitingWriterCountForTesting() == 0) yield()
        }
        assertEquals(false, mutation.isCompleted)
        val latePublication = async(Dispatchers.Default) {
            runCatching { session.localConfirmation() }
        }
        yield()
        assertEquals(false, latePublication.isCompleted)

        sealRelease.countDown()
        assertNull(sealing.await().exceptionOrNull())
        assertNull(mutation.await().exceptionOrNull())
        assertNotNull(latePublication.await().exceptionOrNull())
        assertEquals(true, engine.invalidated)
        assertNotNull(
            runCatching { session.sealApplication("after-commit".toByteArray()) }.exceptionOrNull(),
        )
        setup.store.forgetRuntime()
    }

    @Test
    fun failedAuthorityCommitReopensOldSessionPublication() = runTest {
        val setup = authoritySecureSessionFixture { it.now }
        val engine = RecordingAuthoritySecureSessionEngine()
        val session = setup.begin(engine)
        val invalid = setup.authorityAdvance("a", "b", "c").copy(
            expectedPreviousAuthorityDigest = "0".repeat(64),
        )

        assertNotNull(
            runCatching {
                setup.store.applyVerifiedProductionPairTransition(
                    setup.fixture.runtime.deviceId,
                    setup.fixture.runtime.fingerprint,
                    invalid,
                )
            }.exceptionOrNull(),
        )
        assertEquals(false, engine.invalidated)
        assertEquals("sealed", String(session.sealApplication(byteArrayOf(1)).record))
        session.close()
        setup.store.forgetRuntime()
    }

    @Test
    fun terminalEngineFailureCancelsLeaseButRetryableFailureKeepsItActive() = runTest {
        val terminalSetup = authoritySecureSessionFixture { it.now }
        val terminalEngine = RecordingAuthoritySecureSessionEngine(
            failureOnSeal = IllegalStateException("terminal crypto failure"),
            terminalOnSealFailure = true,
        )
        val terminalSession = terminalSetup.begin(terminalEngine)
        assertNotNull(
            runCatching { terminalSession.sealApplication(byteArrayOf(1)) }.exceptionOrNull(),
        )
        assertEquals(0, terminalSetup.coordinator.liveCountForTesting())
        assertEquals(true, terminalEngine.invalidated)
        terminalSetup.store.forgetRuntime()

        val retryableSetup = authoritySecureSessionFixture { it.now }
        val retryableEngine = RecordingAuthoritySecureSessionEngine(
            failureOnSeal = IllegalArgumentException("retryable record rejection"),
            terminalOnSealFailure = false,
        )
        val retryableSession = retryableSetup.begin(retryableEngine)
        assertNotNull(
            runCatching { retryableSession.sealApplication(byteArrayOf(1)) }.exceptionOrNull(),
        )
        assertEquals(1, retryableSetup.coordinator.liveCountForTesting())
        assertEquals(false, retryableEngine.invalidated)
        retryableEngine.failureOnSeal = null
        assertEquals("sealed", String(retryableSession.sealApplication(byteArrayOf(1)).record))
        retryableSession.close()
        retryableSetup.store.forgetRuntime()
    }

    @Test
    fun cancelledInFlightSealInvalidatesEngineAndCancelsLease() = runTest {
        val setup = authoritySecureSessionFixture { it.now }
        val sealEntered = CountDownLatch(1)
        val sealRelease = CountDownLatch(1)
        val engine = RecordingAuthoritySecureSessionEngine(sealEntered, sealRelease)
        val session = setup.begin(engine)
        val sealing = async(Dispatchers.Default) {
            session.sealApplication("cancelled".toByteArray())
        }
        assertEquals(
            true,
            withContext(Dispatchers.IO) { sealEntered.await(5, TimeUnit.SECONDS) },
        )
        sealing.cancel()
        sealRelease.countDown()
        assertNotNull(runCatching { sealing.await() }.exceptionOrNull())
        withTimeout(5_000) {
            while (setup.coordinator.liveCountForTesting() != 0) yield()
        }
        assertEquals(true, engine.invalidated)
        setup.store.forgetRuntime()
    }

    @Test
    fun cancelledAuthorityMutationAfterEnqueueStillCommitsAndFencesBeforeGateRelease() = runTest {
        val armed = AtomicBoolean(false)
        val editEnqueued = CountDownLatch(1)
        val editRelease = CountDownLatch(1)
        val setup = authoritySecureSessionFixture(
            trustedNow = { it.now },
            authorityPersistenceHooks = ProductionC1AuthorityPersistenceHooks(
                afterEditEnqueued = {
                    if (armed.get()) {
                        editEnqueued.countDown()
                        check(editRelease.await(5, TimeUnit.SECONDS)) {
                            "authority edit release timed out"
                        }
                    }
                },
            ),
        )
        val engine = RecordingAuthoritySecureSessionEngine()
        val session = setup.begin(engine)
        armed.set(true)
        val mutation = async(Dispatchers.Default) {
            setup.store.applyVerifiedProductionPairTransition(
                setup.fixture.runtime.deviceId,
                setup.fixture.runtime.fingerprint,
                setup.authorityAdvance("d", "e", "f"),
            )
        }
        assertEquals(
            true,
            withContext(Dispatchers.IO) { editEnqueued.await(5, TimeUnit.SECONDS) },
        )
        val latePublication = async(Dispatchers.Default) {
            runCatching { session.localConfirmation() }
        }
        mutation.cancel()
        yield()
        assertEquals(false, latePublication.isCompleted)
        editRelease.countDown()
        mutation.join()

        assertEquals(true, mutation.isCancelled)
        assertEquals(true, engine.invalidated)
        assertEquals(0, setup.coordinator.liveCountForTesting())
        assertNotNull(latePublication.await().exceptionOrNull())
        setup.store.forgetRuntime()
    }

    @Test
    fun ambiguousAuthorityPersistenceIOExceptionFencesOldSessionFailClosed() = runTest {
        val armed = AtomicBoolean(false)
        val setup = authoritySecureSessionFixture(
            trustedNow = { it.now },
            authorityPersistenceHooks = ProductionC1AuthorityPersistenceHooks(
                afterEditEnqueued = {
                    if (armed.get()) throw IOException("ambiguous authority persistence")
                },
            ),
        )
        val engine = RecordingAuthoritySecureSessionEngine()
        val session = setup.begin(engine)
        armed.set(true)

        val failure = runCatching {
            setup.store.applyVerifiedProductionPairTransition(
                setup.fixture.runtime.deviceId,
                setup.fixture.runtime.fingerprint,
                setup.authorityAdvance("1", "3", "5"),
            )
        }.exceptionOrNull()

        assertEquals("ambiguous authority persistence", failure?.message)
        assertEquals(true, engine.invalidated)
        assertEquals(0, setup.coordinator.liveCountForTesting())
        assertNotNull(runCatching { session.localConfirmation() }.exceptionOrNull())
        armed.set(false)
        setup.store.forgetRuntime()
    }

    @Test
    fun postCommitPersistenceFailureKeepsNewBytesAndFencesOldSession() = runTest {
        val armed = AtomicBoolean(false)
        val setup = authoritySecureSessionFixture(
            trustedNow = { it.now },
            authorityPersistenceHooks = ProductionC1AuthorityPersistenceHooks(
                afterCommitBeforeFence = {
                    if (armed.get()) throw IOException("post-commit cache update failed")
                },
            ),
        )
        val engine = RecordingAuthoritySecureSessionEngine()
        val session = setup.begin(engine)
        val transition = setup.authorityAdvance("2", "4", "6")
        armed.set(true)

        val failure = runCatching {
            setup.store.applyVerifiedProductionPairTransition(
                setup.fixture.runtime.deviceId,
                setup.fixture.runtime.fingerprint,
                transition,
            )
        }.exceptionOrNull()

        assertEquals("post-commit cache update failed", failure?.message)
        assertEquals(
            transition.nextAuthority.digestHex(),
            setup.store.trustedRuntime.first()?.productionPairState?.authority?.digestHex(),
        )
        assertEquals(true, engine.invalidated)
        assertEquals(0, setup.coordinator.liveCountForTesting())
        assertNotNull(runCatching { session.localConfirmation() }.exceptionOrNull())
        armed.set(false)
        setup.store.forgetRuntime()
    }

    @Test
    fun cancelledForgetAfterEnqueueStillWipesSessionBeforeReturning() = runTest {
        val armed = AtomicBoolean(false)
        val editEnqueued = CountDownLatch(1)
        val editRelease = CountDownLatch(1)
        val setup = authoritySecureSessionFixture(
            trustedNow = { it.now },
            authorityPersistenceHooks = ProductionC1AuthorityPersistenceHooks(
                afterEditEnqueued = {
                    if (armed.get()) {
                        editEnqueued.countDown()
                        check(editRelease.await(5, TimeUnit.SECONDS)) {
                            "forget edit release timed out"
                        }
                    }
                },
            ),
        )
        val engine = RecordingAuthoritySecureSessionEngine()
        setup.begin(engine)
        armed.set(true)
        val forgetting = async(Dispatchers.Default) { setup.store.forgetRuntime() }
        assertEquals(
            true,
            withContext(Dispatchers.IO) { editEnqueued.await(5, TimeUnit.SECONDS) },
        )
        forgetting.cancel()
        editRelease.countDown()
        forgetting.join()

        assertEquals(true, forgetting.isCancelled)
        assertEquals(true, engine.invalidated)
        assertEquals(0, setup.coordinator.liveCountForTesting())
        assertNull(setup.store.trustedRuntime.first())
    }

    @Test
    fun invalidStoredIdentityCleanupUsesAuthorityWriterAndWipesLiveSession() = runTest {
        val setup = authoritySecureSessionFixture { it.now }
        val engine = RecordingAuthoritySecureSessionEngine()
        val session = setup.begin(engine)
        ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore.edit { prefs ->
                prefs[stringPreferencesKey("runtime_device_id")] = " invalid-runtime-id"
            }

        assertNull(setup.store.trustedRuntime.first())
        assertEquals(true, engine.invalidated)
        assertEquals(0, setup.coordinator.liveCountForTesting())
        assertNotNull(runCatching { session.localConfirmation() }.exceptionOrNull())
    }

    @Test
    fun exactBoundCoordinatorRevalidatesThreeTimesAndFencesReplayAndFailure() = runTest {
        var trustedNow = 10uL
        val coordinator = ProductionC1ExactBoundStartCoordinator.forTesting(nowMs = { trustedNow })
        val claimed = exactBoundValidation(marker = "1".repeat(64), pair = "a".repeat(64))
        var validations = 0
        var completionAborts = 0
        val handle = coordinator.admitForTesting(claimed) {
            validations += 1
            it
        }
        val lease = coordinator.beginForTesting(
            handle,
            claimed,
            testingValidator = {
                validations += 1
                it
            },
            start = {},
            abort = { completionAborts += 1 },
        )
        assertEquals(3, validations)
        coordinator.assertActive(lease)
        coordinator.complete(handle)
        assertEquals(0, completionAborts)
        assertEquals(0, coordinator.liveCountForTesting())
        assertEquals(ProductionC1ExactBoundStartTerminalReason.COMPLETED,
            coordinator.tombstonesForTesting().single().reason)
        val replay = runCatching {
            coordinator.admitForTesting(claimed) { it }
        }.exceptionOrNull() as? ProductionC1ExactBoundStartCoordinatorException
        assertEquals(ProductionC1ExactBoundStartCoordinatorFailure.MARKER_REPLAY, replay?.failure)

        val failing = exactBoundValidation(marker = "2".repeat(64), pair = "b".repeat(64))
        val failingHandle = coordinator.admitForTesting(failing) { it }
        var failingValidations = 0
        var postStartAborts = 0
        val expired = runCatching {
            coordinator.beginForTesting(failingHandle, failing, testingValidator = {
                failingValidations += 1
                if (failingValidations == 2) {
                    throw ProductionC1ExactBoundStartValidationException(
                        ProductionC1ExactBoundStartValidationFailure.EXPIRED,
                    )
                }
                it
            }, start = {}, abort = { postStartAborts += 1 })
        }.exceptionOrNull() as? ProductionC1ExactBoundStartValidationException
        assertEquals(ProductionC1ExactBoundStartValidationFailure.EXPIRED, expired?.failure)
        assertEquals(1, postStartAborts)
        assertEquals(0, coordinator.liveCountForTesting())
        assertEquals(
            ProductionC1ExactBoundStartTerminalReason.EXPIRED,
            coordinator.tombstonesForTesting().last().reason,
        )

        val partial = exactBoundValidation(marker = "6".repeat(64), pair = "7".repeat(64))
        val partialHandle = coordinator.admitForTesting(partial) { it }
        var partialStartAborts = 0
        val partialFailure = IllegalStateException("partial start")
        val thrown = runCatching {
            coordinator.beginForTesting(
                partialHandle,
                partial,
                testingValidator = { it },
                start = { throw partialFailure },
                abort = { partialStartAborts += 1 },
            )
        }.exceptionOrNull()
        assertTrue(thrown === partialFailure)
        assertEquals(1, partialStartAborts)
        assertEquals(
            ProductionC1ExactBoundStartTerminalReason.START_FAILED,
            coordinator.tombstonesForTesting().last().reason,
        )
    }

    @Test
    fun exactBoundCoordinatorCancellationAndConcurrentBeginCannotReviveLateStart() = runTest {
        val coordinator = ProductionC1ExactBoundStartCoordinator.forTesting(nowMs = { 10uL })
        val claimed = exactBoundValidation(marker = "3".repeat(64), pair = "c".repeat(64))
        val handle = coordinator.admitForTesting(claimed) { it }
        val started = CompletableDeferred<Unit>()
        val release = CompletableDeferred<Unit>()
        val abortEntered = CompletableDeferred<Unit>()
        var lateAborts = 0
        var lateResourceRemainedOpen = false
        val late = async {
            runCatching {
                coordinator.beginForTesting(
                    handle,
                    claimed,
                    testingValidator = { it },
                    start = {
                        started.complete(Unit)
                        release.await()
                        lateResourceRemainedOpen = true
                    },
                    abort = {
                        lateAborts += 1
                        lateResourceRemainedOpen = false
                        abortEntered.complete(Unit)
                    },
                )
            }
        }
        started.await()
        val cancellation = async { coordinator.cancel(handle) }
        abortEntered.await()
        release.complete(Unit)
        cancellation.await()
        val failure = late.await().exceptionOrNull() as?
            ProductionC1ExactBoundStartCoordinatorException
        assertEquals(ProductionC1ExactBoundStartCoordinatorFailure.FENCED, failure?.failure)
        assertEquals(2, lateAborts)
        assertEquals(false, lateResourceRemainedOpen)
        assertEquals(0, coordinator.liveCountForTesting())
        assertEquals(
            ProductionC1ExactBoundStartTerminalReason.CANCELLED,
            coordinator.tombstonesForTesting().single().reason,
        )

        val suspended = ProductionC1ExactBoundStartCoordinator.forTesting(nowMs = { 10uL })
        val suspendedClaim = exactBoundValidation(
            marker = "5".repeat(64),
            pair = "6".repeat(64),
        )
        val suspendedHandle = suspended.admitForTesting(suspendedClaim) { it }
        val validatorEntered = CompletableDeferred<Unit>()
        val validatorRelease = CompletableDeferred<Unit>()
        val fenced = async {
            runCatching {
                suspended.beginForTesting(suspendedHandle, suspendedClaim, {
                    validatorEntered.complete(Unit)
                    validatorRelease.await()
                    it
                })
            }
        }
        validatorEntered.await()
        suspended.fenceRevoked(suspendedClaim.pairAuthorityDigest)
        validatorRelease.complete(Unit)
        val fencedFailure = fenced.await().exceptionOrNull() as?
            ProductionC1ExactBoundStartCoordinatorException
        assertEquals(ProductionC1ExactBoundStartCoordinatorFailure.FENCED, fencedFailure?.failure)
        assertEquals(0, suspended.liveCountForTesting())
        assertEquals(
            ProductionC1ExactBoundStartTerminalReason.REVOKED,
            suspended.tombstonesForTesting().single().reason,
        )

        val concurrent = ProductionC1ExactBoundStartCoordinator.forTesting(nowMs = { 10uL })
        val next = exactBoundValidation(marker = "4".repeat(64), pair = "d".repeat(64))
        val nextHandle = concurrent.admitForTesting(next) { it }
        var starts = 0
        val results = List(2) {
            async {
                runCatching {
                    concurrent.beginForTesting(
                        nextHandle,
                        next,
                        testingValidator = { it },
                        start = { starts += 1 },
                        abort = {},
                    )
                }
            }
        }.awaitAll()
        assertEquals(1, results.count { it.isSuccess })
        assertEquals(1, starts)
    }

    @Test
    fun exactBoundStartOperationSkipsStartAfterAbortWinsPreStartRace() = runTest {
        var starts = 0
        var aborts = 0
        val operation = ProductionC1ExactBoundStartOperation(
            start = { starts += 1 },
            abort = { aborts += 1 },
        )
        val context = ProductionC1ExactBoundStartOperationContext(
            ProductionC1ExactBoundStartCoordinator.forTesting(nowMs = { 10uL }),
            operation.operationId,
        )
        operation.abort(context, originOperationId = null)
        operation.start(context)
        assertEquals(0, starts)
        assertEquals(1, aborts)
    }

    @Test
    fun exactBoundCoordinatorRejectsDifferentAuthorityWhileValidationIsLive() = runTest {
        val coordinator = ProductionC1ExactBoundStartCoordinator.forTesting(nowMs = { 10uL })
        val first = exactBoundValidation(marker = "a".repeat(64), pair = "b".repeat(64))
        val second = exactBoundValidation(marker = "c".repeat(64), pair = "d".repeat(64))
        val validationEntered = CompletableDeferred<Unit>()
        val validationRelease = CompletableDeferred<Unit>()
        val firstAdmission = async {
            coordinator.admitForTesting(first) {
                validationEntered.complete(Unit)
                validationRelease.await()
                it
            }
        }
        validationEntered.await()

        val overlapping = runCatching {
            coordinator.admitForTesting(second) { it }
        }.exceptionOrNull() as? ProductionC1ExactBoundStartCoordinatorException

        assertEquals(
            ProductionC1ExactBoundStartCoordinatorFailure.PAIR_ALREADY_LIVE,
            overlapping?.failure,
        )
        assertEquals(1, coordinator.liveCountForTesting())
        validationRelease.complete(Unit)
        coordinator.cancel(firstAdmission.await())
    }

    @Test
    fun exactBoundCoordinatorAbortCallbackCanReenterItsOwnFenceWithoutDeadlock() = runTest {
        val pair = "0".repeat(64)
        val coordinator = ProductionC1ExactBoundStartCoordinator.forTesting(nowMs = { 10uL })
        val claim = exactBoundValidation(marker = "1".repeat(64), pair = pair)
        val handle = coordinator.admitForTesting(claim) { it }
        var aborts = 0
        coordinator.beginForTesting(
            handle,
            claim,
            testingValidator = { it },
            abort = { operationContext ->
                aborts += 1
                CoroutineScope(SupervisorJob() + StandardTestDispatcher(testScheduler)).async {
                    operationContext.fenceRevoked(pair)
                }.await()
            },
        )

        withTimeout(1_000L) { coordinator.fenceRevoked(pair) }

        assertEquals(1, aborts)
        assertEquals(0, coordinator.liveCountForTesting())
        assertEquals(0, coordinator.pendingAbortCountForTesting())
    }

    @Test
    fun exactBoundCoordinatorAbortCallbackCanRetryOwnPendingAbortWithoutDeadlock() = runTest {
        val pair = "2".repeat(64)
        val coordinator = ProductionC1ExactBoundStartCoordinator.forTesting(nowMs = { 10uL })
        val claim = exactBoundValidation(marker = "3".repeat(64), pair = pair)
        val handle = coordinator.admitForTesting(claim) { it }
        lateinit var lease: ProductionC1ExactBoundStartLease
        var aborts = 0
        lease = coordinator.beginForTesting(
            handle,
            claim,
            testingValidator = { it },
            abort = { operationContext ->
                aborts += 1
                CoroutineScope(SupervisorJob() + StandardTestDispatcher(testScheduler)).async {
                    operationContext.cancel(handle)
                    operationContext.cancel(lease)
                    operationContext.retryPendingAborts()
                }.await()
            },
        )

        withTimeout(1_000L) { coordinator.fenceRevoked(pair) }

        assertEquals(1, aborts)
        assertEquals(0, coordinator.liveCountForTesting())
        assertEquals(0, coordinator.pendingAbortCountForTesting())
    }

    @Test
    fun exactBoundCoordinatorStartCanReenterFenceAndClosesLatePublication() = runTest {
        val pair = "4".repeat(64)
        val coordinator = ProductionC1ExactBoundStartCoordinator.forTesting(nowMs = { 10uL })
        val claim = exactBoundValidation(marker = "5".repeat(64), pair = pair)
        val handle = coordinator.admitForTesting(claim) { it }
        var resourceOpen = false
        var aborts = 0

        val failure = withTimeout(1_000L) {
            runCatching {
                coordinator.beginForTesting(
                    handle,
                    claim,
                    testingValidator = { it },
                    start = { operationContext ->
                        resourceOpen = true
                        CoroutineScope(
                            SupervisorJob() + StandardTestDispatcher(testScheduler),
                        ).async {
                            operationContext.fenceRevoked(pair)
                        }.await()
                        resourceOpen = true
                    },
                    abort = { operationContext ->
                        aborts += 1
                        resourceOpen = false
                        CoroutineScope(
                            SupervisorJob() + StandardTestDispatcher(testScheduler),
                        ).async {
                            operationContext.fenceRevoked(pair)
                        }.await()
                    },
                )
            }.exceptionOrNull()
        } as? ProductionC1ExactBoundStartCoordinatorException
        coordinator.retryPendingAborts()

        assertEquals(ProductionC1ExactBoundStartCoordinatorFailure.FENCED, failure?.failure)
        assertEquals(2, aborts)
        assertEquals(false, resourceOpen)
        assertEquals(0, coordinator.liveCountForTesting())
        assertEquals(0, coordinator.pendingAbortCountForTesting())
        assertEquals(
            ProductionC1ExactBoundStartTerminalReason.REVOKED,
            coordinator.tombstonesForTesting().single().reason,
        )
    }

    @Test
    fun exactBoundCoordinatorStartCanRetryItsDeferredAbortWithoutDeadlock() = runTest {
        val pair = "a".repeat(64)
        val coordinator = ProductionC1ExactBoundStartCoordinator.forTesting(nowMs = { 10uL })
        val claim = exactBoundValidation(marker = "b".repeat(64), pair = pair)
        val handle = coordinator.admitForTesting(claim) { it }
        var resourceOpen = false
        var aborts = 0

        val failure = withTimeout(1_000L) {
            runCatching {
                coordinator.beginForTesting(
                    handle,
                    claim,
                    testingValidator = { it },
                    start = { operationContext ->
                        resourceOpen = true
                        CoroutineScope(
                            SupervisorJob() + StandardTestDispatcher(testScheduler),
                        ).async {
                            operationContext.fenceRevoked(pair)
                            operationContext.cancel(handle)
                            operationContext.retryPendingAborts()
                        }.await()
                        resourceOpen = true
                    },
                    abort = {
                        aborts += 1
                        resourceOpen = false
                    },
                )
            }.exceptionOrNull()
        } as? ProductionC1ExactBoundStartCoordinatorException

        assertEquals(ProductionC1ExactBoundStartCoordinatorFailure.FENCED, failure?.failure)
        assertEquals(2, aborts)
        assertEquals(false, resourceOpen)
        assertEquals(0, coordinator.liveCountForTesting())
        assertEquals(0, coordinator.pendingAbortCountForTesting())
    }

    @Test
    fun exactBoundCoordinatorCancellationCannotLosePreinstalledDeferredAbortLatch() = runTest {
        val pair = "c".repeat(64)
        val coordinator = ProductionC1ExactBoundStartCoordinator.forTesting(nowMs = { 10uL })
        val claim = exactBoundValidation(marker = "d".repeat(64), pair = pair)
        val handle = coordinator.admitForTesting(claim) { it }
        val firstAbortEntered = CompletableDeferred<Unit>()
        val releaseFirstAbort = CompletableDeferred<Unit>()
        var resourceOpen = false
        var aborts = 0
        val beginning = async {
            coordinator.beginForTesting(
                handle,
                claim,
                testingValidator = { it },
                start = { operationContext ->
                    resourceOpen = true
                    val detachedFence = CoroutineScope(
                        SupervisorJob() + StandardTestDispatcher(testScheduler),
                    ).async {
                        operationContext.fenceRevoked(pair)
                    }
                    try {
                        detachedFence.await()
                    } finally {
                        // Simulate a resource published while the cancelled producer unwinds.
                        resourceOpen = true
                    }
                },
                abort = {
                    aborts += 1
                    resourceOpen = false
                    if (aborts == 1) {
                        firstAbortEntered.complete(Unit)
                        releaseFirstAbort.await()
                    }
                },
            )
        }
        firstAbortEntered.await()

        beginning.cancel()
        withTimeout(1_000L) {
            while (!resourceOpen) yield()
        }
        releaseFirstAbort.complete(Unit)
        withTimeout(1_000L) { runCatching { beginning.await() } }
        withTimeout(1_000L) {
            while (coordinator.pendingAbortCountForTesting() != 0) yield()
        }

        assertEquals(2, aborts)
        assertEquals(false, resourceOpen)
        assertEquals(0, coordinator.liveCountForTesting())
        assertEquals(0, coordinator.pendingAbortCountForTesting())
    }

    @Test
    fun exactBoundCoordinatorStartReentryDoesNotWaitOnExternalInFlightFence() = runTest {
        val pair = "6".repeat(64)
        val coordinator = ProductionC1ExactBoundStartCoordinator.forTesting(nowMs = { 10uL })
        val claim = exactBoundValidation(marker = "7".repeat(64), pair = pair)
        val handle = coordinator.admitForTesting(claim) { it }
        val startEntered = CompletableDeferred<Unit>()
        val allowStartReentry = CompletableDeferred<Unit>()
        val firstAbortEntered = CompletableDeferred<Unit>()
        var resourceOpen = false
        var aborts = 0
        val beginning = async {
            runCatching {
                coordinator.beginForTesting(
                    handle,
                    claim,
                    testingValidator = { it },
                    start = { operationContext ->
                        startEntered.complete(Unit)
                        allowStartReentry.await()
                        CoroutineScope(
                            SupervisorJob() + StandardTestDispatcher(testScheduler),
                        ).async {
                            operationContext.fenceRevoked(pair)
                        }.await()
                        resourceOpen = true
                    },
                    abort = {
                        aborts += 1
                        resourceOpen = false
                        if (aborts == 1) firstAbortEntered.complete(Unit)
                    },
                )
            }
        }
        startEntered.await()
        val externalFence = async { coordinator.fenceRevoked(pair) }
        firstAbortEntered.await()

        allowStartReentry.complete(Unit)
        withTimeout(1_000L) {
            externalFence.await()
            val failure = beginning.await().exceptionOrNull() as?
                ProductionC1ExactBoundStartCoordinatorException
            assertEquals(ProductionC1ExactBoundStartCoordinatorFailure.FENCED, failure?.failure)
        }

        assertEquals(2, aborts)
        assertEquals(false, resourceOpen)
        assertEquals(0, coordinator.liveCountForTesting())
        assertEquals(0, coordinator.pendingAbortCountForTesting())
    }

    @Test
    fun exactBoundCoordinatorRetainsFailedDeferredLateCleanupUntilRetry() = runTest {
        val pair = "8".repeat(64)
        val coordinator = ProductionC1ExactBoundStartCoordinator.forTesting(nowMs = { 10uL })
        val claim = exactBoundValidation(marker = "9".repeat(64), pair = pair)
        val handle = coordinator.admitForTesting(claim) { it }
        val finalAbortEntered = CompletableDeferred<Unit>()
        val finalAbortRelease = CompletableDeferred<Unit>()
        var resourceOpen = false
        var aborts = 0
        val beginning = async {
            runCatching {
                coordinator.beginForTesting(
                    handle,
                    claim,
                    testingValidator = { it },
                    start = {
                        resourceOpen = true
                        coordinator.fenceRevoked(pair)
                        resourceOpen = true
                    },
                    abort = {
                        aborts += 1
                        resourceOpen = false
                        if (aborts == 2) {
                            finalAbortEntered.complete(Unit)
                            finalAbortRelease.await()
                            error("deferred late abort failed")
                        }
                    },
                )
            }
        }
        finalAbortEntered.await()
        val waitingRetry = async { runCatching { coordinator.retryPendingAborts() } }
        yield()
        assertEquals(false, waitingRetry.isCompleted)
        val blocked = runCatching {
            coordinator.admitForTesting(
                exactBoundValidation(marker = "e".repeat(64), pair = "f".repeat(64)),
            ) { it }
        }.exceptionOrNull() as? ProductionC1ExactBoundStartCoordinatorException
        assertEquals(
            ProductionC1ExactBoundStartCoordinatorFailure.PAIR_CLEANUP_PENDING,
            blocked?.failure,
        )

        finalAbortRelease.complete(Unit)
        assertEquals(
            ProductionC1ExactBoundStartCoordinatorFailure.FENCED,
            (beginning.await().exceptionOrNull() as?
                ProductionC1ExactBoundStartCoordinatorException)?.failure,
        )
        assertEquals(
            "deferred late abort failed",
            waitingRetry.await().exceptionOrNull()?.message,
        )
        assertEquals(2, aborts)
        assertEquals(1, coordinator.pendingAbortCountForTesting())

        coordinator.retryPendingAborts()
        assertEquals(3, aborts)
        assertEquals(false, resourceOpen)
        assertEquals(0, coordinator.pendingAbortCountForTesting())
    }

    @Test
    fun exactBoundCoordinatorDeliveredLeaseOutlivesProducerJob() = runTest {
        lateinit var producerJob: Job
        var cancelDuringAcknowledgement = false
        val coordinator = ProductionC1ExactBoundStartCoordinator.forTesting(
            nowMs = { 10uL },
            ownershipTransitionForTesting = {
                if (cancelDuringAcknowledgement) producerJob.cancel()
            },
        )
        val claim = exactBoundValidation(marker = "2".repeat(64), pair = "3".repeat(64))
        val delivered = CompletableDeferred<ProductionC1ExactBoundStartLease>()
        val keepOwnerAlive = CompletableDeferred<Unit>()
        var aborts = 0
        val owner = async {
            producerJob = requireNotNull(currentCoroutineContext()[Job])
            val handle = coordinator.admitForTesting(claim) { it }
            val lease = coordinator.beginForTesting(
                handle,
                claim,
                testingValidator = { it },
                abort = { aborts += 1 },
            )
            delivered.complete(lease)
            keepOwnerAlive.await()
        }
        val lease = delivered.await()
        cancelDuringAcknowledgement = true
        coordinator.assertActive(lease)

        owner.join()

        assertTrue(owner.isCancelled)
        assertEquals(0, aborts)
        assertEquals(1, coordinator.liveCountForTesting())
        assertEquals(0, coordinator.pendingAbortCountForTesting())

        coordinator.cancel(lease)
        assertEquals(1, aborts)
        assertEquals(0, coordinator.liveCountForTesting())
        assertEquals(0, coordinator.pendingAbortCountForTesting())
        assertEquals(
            ProductionC1ExactBoundStartTerminalReason.CANCELLED,
            coordinator.tombstonesForTesting().single().reason,
        )
    }

    @Test
    fun exactBoundCoordinatorHandleTransferRejectsStaleOwnerCancellation() = runTest {
        lateinit var producerJob: Job
        var cancelDuringTransfer = false
        val coordinator = ProductionC1ExactBoundStartCoordinator.forTesting(
            nowMs = { 10uL },
            ownershipTransitionForTesting = {
                if (cancelDuringTransfer) producerJob.cancel()
            },
        )
        val claim = exactBoundValidation(marker = "a".repeat(64), pair = "b".repeat(64))
        val delivered = CompletableDeferred<ProductionC1ExactBoundStartHandle>()
        val keepProducerAlive = CompletableDeferred<Unit>()
        val producer = async {
            producerJob = requireNotNull(currentCoroutineContext()[Job])
            val handle = coordinator.admitForTesting(claim) { it }
            delivered.complete(handle)
            keepProducerAlive.await()
        }
        val handle = delivered.await()
        cancelDuringTransfer = true
        var aborts = 0

        val lease = coordinator.beginForTesting(
            handle,
            claim,
            testingValidator = { it },
            abort = { aborts += 1 },
        )
        producer.join()
        coordinator.assertActive(lease)

        assertTrue(producer.isCancelled)
        assertEquals(0, aborts)
        assertEquals(1, coordinator.liveCountForTesting())
        coordinator.cancel(lease)
        assertEquals(1, aborts)
        assertEquals(0, coordinator.liveCountForTesting())
    }

    @Test
    fun exactBoundCoordinatorActiveRevokeAndExpiryAbortExactlyOnce() = runTest {
        var trustedNow = 10uL
        val revokedCoordinator = ProductionC1ExactBoundStartCoordinator.forTesting(
            nowMs = { trustedNow },
        )
        val revokedClaim = exactBoundValidation(
            marker = "7".repeat(64),
            pair = "8".repeat(64),
        )
        val revokedHandle = revokedCoordinator.admitForTesting(revokedClaim) { it }
        var revokeAborts = 0
        revokedCoordinator.beginForTesting(
            revokedHandle,
            revokedClaim,
            testingValidator = { it },
            start = {},
            abort = { revokeAborts += 1 },
        )
        revokedCoordinator.fenceRevoked(revokedClaim.pairAuthorityDigest)
        revokedCoordinator.fenceRevoked(revokedClaim.pairAuthorityDigest)
        assertEquals(1, revokeAborts)
        assertEquals(
            ProductionC1ExactBoundStartTerminalReason.REVOKED,
            revokedCoordinator.tombstonesForTesting().single().reason,
        )

        val expiryCoordinator = ProductionC1ExactBoundStartCoordinator.forTesting(
            nowMs = { trustedNow },
        )
        val expiryClaim = exactBoundValidation(
            marker = "9".repeat(64),
            pair = "a".repeat(64),
            expiresAtMs = 20uL,
        )
        val expiryHandle = expiryCoordinator.admitForTesting(expiryClaim) { it }
        var expiryAborts = 0
        expiryCoordinator.beginForTesting(
            expiryHandle,
            expiryClaim,
            testingValidator = { it },
            start = {},
            abort = { expiryAborts += 1 },
        )
        trustedNow = 20uL
        expiryCoordinator.fenceExpired()
        expiryCoordinator.fenceExpired()
        assertEquals(1, expiryAborts)
        assertEquals(
            ProductionC1ExactBoundStartTerminalReason.EXPIRED,
            expiryCoordinator.tombstonesForTesting().single().reason,
        )
    }

    @Test
    fun exactBoundCoordinatorQuarantinesPairUntilSlowOrFailedAbortFinishes() = runTest {
        val pair = "1".repeat(64)
        val slowCoordinator = ProductionC1ExactBoundStartCoordinator.forTesting(nowMs = { 10uL })
        val slowClaim = exactBoundValidation(marker = "2".repeat(64), pair = pair)
        val slowHandle = slowCoordinator.admitForTesting(slowClaim) { it }
        val abortEntered = CompletableDeferred<Unit>()
        val abortRelease = CompletableDeferred<Unit>()
        slowCoordinator.beginForTesting(
            slowHandle,
            slowClaim,
            testingValidator = { it },
            abort = {
                abortEntered.complete(Unit)
                abortRelease.await()
            },
        )
        val slowFence = async { slowCoordinator.fenceRevoked(pair) }
        abortEntered.await()
        assertEquals(1, slowCoordinator.pendingAbortCountForTesting())
        val whileSlow = runCatching {
            slowCoordinator.admitForTesting(
                exactBoundValidation(marker = "3".repeat(64), pair = pair),
            ) { it }
        }.exceptionOrNull() as? ProductionC1ExactBoundStartCoordinatorException
        assertEquals(
            ProductionC1ExactBoundStartCoordinatorFailure.PAIR_CLEANUP_PENDING,
            whileSlow?.failure,
        )
        abortRelease.complete(Unit)
        slowFence.await()
        assertEquals(0, slowCoordinator.pendingAbortCountForTesting())
        val afterSlow = slowCoordinator.admitForTesting(
            exactBoundValidation(marker = "4".repeat(64), pair = pair),
        ) { it }
        slowCoordinator.cancel(afterSlow)

        val retryCoordinator = ProductionC1ExactBoundStartCoordinator.forTesting(nowMs = { 10uL })
        val retryClaim = exactBoundValidation(marker = "5".repeat(64), pair = pair)
        val retryHandle = retryCoordinator.admitForTesting(retryClaim) { it }
        var abortAttempts = 0
        retryCoordinator.beginForTesting(
            retryHandle,
            retryClaim,
            testingValidator = { it },
            abort = {
                abortAttempts += 1
                if (abortAttempts == 1) error("abort failed")
            },
        )
        val firstFailure = runCatching { retryCoordinator.fenceRevoked(pair) }.exceptionOrNull()
        assertEquals("abort failed", firstFailure?.message)
        assertEquals(1, retryCoordinator.pendingAbortCountForTesting())
        val whileFailed = runCatching {
            retryCoordinator.admitForTesting(
                exactBoundValidation(marker = "6".repeat(64), pair = pair),
            ) { it }
        }.exceptionOrNull() as? ProductionC1ExactBoundStartCoordinatorException
        assertEquals(
            ProductionC1ExactBoundStartCoordinatorFailure.PAIR_CLEANUP_PENDING,
            whileFailed?.failure,
        )
        retryCoordinator.fenceRevoked(pair)
        assertEquals(2, abortAttempts)
        assertEquals(0, retryCoordinator.pendingAbortCountForTesting())
        assertEquals(1, retryCoordinator.tombstonesForTesting().size)
        val afterRetry = retryCoordinator.admitForTesting(
            exactBoundValidation(marker = "7".repeat(64), pair = pair),
        ) { it }
        retryCoordinator.cancel(afterRetry)
        assertEquals(2, retryCoordinator.tombstonesForTesting().size)
    }

    @Test
    fun exactBoundCoordinatorRealCoroutineCancellationCannotLeaveStartedResourceLive() = runTest {
        val coordinator = ProductionC1ExactBoundStartCoordinator.forTesting(nowMs = { 10uL })
        val claim = exactBoundValidation(marker = "8".repeat(64), pair = "9".repeat(64))
        val handle = coordinator.admitForTesting(claim) { it }
        val postStartValidationEntered = CompletableDeferred<Unit>()
        val postStartValidationRelease = CompletableDeferred<Unit>()
        var validations = 0
        var aborts = 0
        val beginning = async {
            coordinator.beginForTesting(
                handle,
                claim,
                testingValidator = {
                    validations += 1
                    if (validations == 2) {
                        postStartValidationEntered.complete(Unit)
                        postStartValidationRelease.await()
                    }
                    it
                },
                abort = { aborts += 1 },
            )
        }
        postStartValidationEntered.await()
        beginning.cancel()
        postStartValidationRelease.complete(Unit)
        runCatching { beginning.await() }
        assertEquals(1, aborts)
        assertEquals(0, coordinator.liveCountForTesting())
        assertEquals(0, coordinator.pendingAbortCountForTesting())
        assertEquals(
            ProductionC1ExactBoundStartTerminalReason.CANCELLED,
            coordinator.tombstonesForTesting().single().reason,
        )
    }

    @Test
    fun exactBoundCoordinatorCancellationSafeHandoffClosesAdmittedAndActiveWindows() = runTest {
        lateinit var admitJob: Job
        val admitCoordinator = ProductionC1ExactBoundStartCoordinator.forTesting(
            nowMs = {
                admitJob.cancel()
                10uL
            },
        )
        val admitClaim = exactBoundValidation(marker = "c".repeat(64), pair = "d".repeat(64))
        val admitting = async {
            admitJob = requireNotNull(currentCoroutineContext()[Job])
            admitCoordinator.admitForTesting(admitClaim) { it }
        }
        admitting.join()
        assertTrue(admitting.isCancelled)
        assertEquals(0, admitCoordinator.liveCountForTesting())
        assertEquals(
            ProductionC1ExactBoundStartTerminalReason.CANCELLED,
            admitCoordinator.tombstonesForTesting().single().reason,
        )

        lateinit var beginJob: Job
        var cancelDuringBegin = false
        var beginClockReads = 0
        val beginCoordinator = ProductionC1ExactBoundStartCoordinator.forTesting(
            nowMs = {
                if (cancelDuringBegin) {
                    beginClockReads += 1
                    if (beginClockReads == 3) beginJob.cancel()
                }
                10uL
            },
        )
        val beginClaim = exactBoundValidation(marker = "e".repeat(64), pair = "f".repeat(64))
        val beginHandle = beginCoordinator.admitForTesting(beginClaim) { it }
        var beginAborts = 0
        val beginning = async {
            beginJob = requireNotNull(currentCoroutineContext()[Job])
            cancelDuringBegin = true
            beginCoordinator.beginForTesting(
                beginHandle,
                beginClaim,
                testingValidator = { it },
                abort = { beginAborts += 1 },
            )
        }
        beginning.join()
        assertTrue(beginning.isCancelled)
        assertEquals(3, beginClockReads)
        assertEquals(1, beginAborts)
        assertEquals(0, beginCoordinator.liveCountForTesting())
        assertEquals(0, beginCoordinator.pendingAbortCountForTesting())
        assertEquals(
            ProductionC1ExactBoundStartTerminalReason.CANCELLED,
            beginCoordinator.tombstonesForTesting().single().reason,
        )
    }

    @Test
    fun exactBoundCoordinatorCancellationAfterInnerHandoffCannotLoseHandleOrLease() = runTest {
        lateinit var admitJob: Job
        var admitHandoffs = 0
        val admitCoordinator = ProductionC1ExactBoundStartCoordinator.forTesting(
            nowMs = { 10uL },
            handoffReturnedForTesting = {
                admitHandoffs += 1
                admitJob.cancel()
            },
        )
        val admitClaim = exactBoundValidation(marker = "4".repeat(64), pair = "5".repeat(64))
        val admitting = async {
            admitJob = requireNotNull(currentCoroutineContext()[Job])
            admitCoordinator.admitForTesting(admitClaim) { it }
        }
        admitting.join()

        assertTrue(admitting.isCancelled)
        assertEquals(1, admitHandoffs)
        assertEquals(0, admitCoordinator.liveCountForTesting())
        assertEquals(
            ProductionC1ExactBoundStartTerminalReason.CANCELLED,
            admitCoordinator.tombstonesForTesting().single().reason,
        )

        lateinit var beginJob: Job
        var beginHandoffs = 0
        val beginCoordinator = ProductionC1ExactBoundStartCoordinator.forTesting(
            nowMs = { 10uL },
            handoffReturnedForTesting = {
                beginHandoffs += 1
                if (beginHandoffs == 2) beginJob.cancel()
            },
        )
        val beginClaim = exactBoundValidation(marker = "6".repeat(64), pair = "7".repeat(64))
        val handle = beginCoordinator.admitForTesting(beginClaim) { it }
        var aborts = 0
        val beginning = async {
            beginJob = requireNotNull(currentCoroutineContext()[Job])
            beginCoordinator.beginForTesting(
                handle,
                beginClaim,
                testingValidator = { it },
                abort = { aborts += 1 },
            )
        }
        beginning.join()

        assertTrue(beginning.isCancelled)
        assertEquals(2, beginHandoffs)
        assertEquals(1, aborts)
        assertEquals(0, beginCoordinator.liveCountForTesting())
        assertEquals(0, beginCoordinator.pendingAbortCountForTesting())
        assertEquals(
            ProductionC1ExactBoundStartTerminalReason.CANCELLED,
            beginCoordinator.tombstonesForTesting().single().reason,
        )
    }

    @Test
    fun exactBoundCoordinatorCancelledExpiryFenceStillRunsClaimedAbort() = runTest {
        lateinit var fenceJob: Job
        var trustedNow = 10uL
        var cancelDuringFence = false
        val coordinator = ProductionC1ExactBoundStartCoordinator.forTesting(
            nowMs = {
                if (cancelDuringFence) fenceJob.cancel()
                trustedNow
            },
        )
        val claim = exactBoundValidation(
            marker = "1".repeat(64),
            pair = "2".repeat(64),
            expiresAtMs = 20uL,
        )
        val handle = coordinator.admitForTesting(claim) { it }
        var aborts = 0
        coordinator.beginForTesting(
            handle,
            claim,
            testingValidator = { it },
            abort = { aborts += 1 },
        )
        trustedNow = 20uL
        val fencing = async {
            fenceJob = requireNotNull(currentCoroutineContext()[Job])
            cancelDuringFence = true
            coordinator.fenceExpired()
        }
        fencing.join()
        assertEquals(1, aborts)
        assertEquals(0, coordinator.liveCountForTesting())
        assertEquals(0, coordinator.pendingAbortCountForTesting())
        assertEquals(
            ProductionC1ExactBoundStartTerminalReason.EXPIRED,
            coordinator.tombstonesForTesting().single().reason,
        )
    }

    @Test
    fun exactBoundCoordinatorRetains64TerminalMarkersPerPairAndRejectsOverflow() = runTest {
        val coordinator = ProductionC1ExactBoundStartCoordinator.forTesting(nowMs = { 10uL })
        val quietPair = "e".repeat(64)
        val noisyPair = "f".repeat(64)
        val quiet = exactBoundValidation(marker = "b".repeat(64), pair = quietPair)
        coordinator.cancel(coordinator.admitForTesting(quiet) { it })
        repeat(65) { index ->
            val marker = index.toString(16).padStart(64, '0')
            val claimed = exactBoundValidation(marker = marker, pair = noisyPair)
            coordinator.cancel(coordinator.admitForTesting(claimed) { it })
        }
        val tombstones = coordinator.tombstonesForTesting()
        assertEquals(65, tombstones.size)
        assertTrue(tombstones.any { it.pairAuthorityDigest == quietPair && it.markerDigest == quiet.markerDigest })
        assertEquals(64, tombstones.count { it.pairAuthorityDigest == noisyPair })

        val exhausted = ProductionC1ExactBoundStartCoordinator.forTesting(
            nowMs = { 10uL },
            initialGeneration = ULong.MAX_VALUE,
        )
        val overflow = runCatching {
            exhausted.admitForTesting(
                exactBoundValidation(marker = "9".repeat(64), pair = "8".repeat(64)),
            ) { it }
        }.exceptionOrNull() as? ProductionC1ExactBoundStartCoordinatorException
        assertEquals(
            ProductionC1ExactBoundStartCoordinatorFailure.GENERATION_OVERFLOW,
            overflow?.failure,
        )
    }

    private fun verifiedStoreFixture(): VerifiedStoreFixture {
        val root = loadProductionFixture()
        val objects = root.getJSONObject("objects")
        val constants = root.getJSONObject("constants")
        val now = constants.stringULong("nowMs")
        val keyset = ProductionC1ServiceKeyset.decode(
            objects.getJSONObject("serviceKeyset").hex("expectedCanonicalHex"),
        )
        val verifiedKeyset = ProductionC1Verifier.verifyServiceKeyset(
            keyset,
            keyset.serviceIdDigest,
            fixturePublicKey(root, "root"),
            constants.stringULong("minimumAcceptedKeysetVersion"),
            nowMs = now,
        )
        val previousSnapshot = ProductionPairStateSnapshot.decode(
            objects.getJSONObject("previousSnapshot").hex("expectedCanonicalHex"),
        )
        val status = ProductionC1PairStatus.decode(
            objects.getJSONObject("pairStatus").hex("expectedCanonicalHex"),
        )
        val verifiedStatus = ProductionC1Verifier.verifyPairStatus(
            status,
            keyset.serviceIdDigest,
            ProductionC1RequesterRole.RUNTIME,
            status.requestNonce,
            previousSnapshot,
            verifiedKeyset,
            now,
        )
        val synthetic = root.getJSONObject("syntheticMaterials")
        val commitments = ProductionC1RecoveryCommitments.currentToken(
            previousSnapshot.authority.pairBindingDigest,
            synthetic.hex("previousEndpointTrafficSecretHex"),
            synthetic.hex("previousRouteTokenSeedHex"),
        )
        val freshTransition = ProductionC1Verifier.verifyFreshPairProof(
            ProductionC1FreshPairProof.decode(
                objects.getJSONObject("freshPairProof").hex("expectedCanonicalHex"),
            ),
            verifiedStatus,
            previousSnapshot,
            commitments,
            fixturePublicKey(root, "survivorRuntimeIdentity"),
            fixturePublicKey(root, "replacementClientIdentity"),
            now,
        )
        val nextSnapshot = ProductionPairStateSnapshot.decode(
            objects.getJSONObject("nextSnapshot").hex("expectedCanonicalHex"),
        )
        val authority = ProductionPairAuthorityState.decode(
            objects.getJSONObject("nextAuthority").hex("expectedCanonicalHex"),
        )
        val securityContext = ProductionC1PreauthorizationSessionContext.decode(
            objects.getJSONObject("preauthorizationSessionContext").hex("expectedCanonicalHex"),
        )
        val plan = ProductionC1Verifier.verifyRoutePlan(
            ProductionC1RoutePlanClaims.decode(
                objects.getJSONObject("routePlan").hex("expectedCanonicalHex"),
            ),
            ProductionC1RouteCapability.decode(
                objects.getJSONObject("routeCapability").hex("expectedCanonicalHex"),
            ),
            securityContext,
            authority,
            verifiedKeyset,
            now,
        )
        val authorization = ProductionC1Verifier.makeRouteAuthorization(plan, now)
        val connectorInput = ProductionC1Verifier.verifyConnectorInput(
            plan,
            synthetic.getString("routeHandle"),
            synthetic.getString("connectorNonce"),
            synthetic.hex("connectorSecretHex"),
            now,
        )
        val transcriptBinding = ProductionC1Verifier.verifyTranscriptBinding(
            ProductionSecureSessionCodec.decodeTranscript(
                objects.getJSONObject("secureSessionTranscript").hex("expectedCanonicalHex"),
            ),
            authorization,
            plan,
            connectorInput,
            authority,
            now,
        )
        return VerifiedStoreFixture(
            runtime = productionTrustedRuntime().copy(
                fingerprint = authority.runtimeIdentityFingerprint,
                publicKeyBase64 = "runtime-production-public-key",
            ),
            previousSnapshot = previousSnapshot,
            nextSnapshot = nextSnapshot,
            freshTransition = freshTransition,
            transcriptBinding = transcriptBinding,
            now = now,
        )
    }

    private fun endpointPersistenceFixture(): EndpointPersistenceFixture {
        val root = loadCandidateFixture()
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
        val receipts = ENDPOINT_OPERATIONS.mapIndexed { index, operation ->
            val operationAuthorizations = listOf(
                authorizations.clientPublish,
                authorizations.runtimeFetchClient,
                authorizations.runtimePublish,
                authorizations.clientFetchRuntime,
            )
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
        val chain = EndpointChain(authority, grant, authorizations, transcript)
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
        val key = synthetic.hex("keyConfirmationKeyHex")
        val confirmation = ProductionC1CandidateVerifier.makeP2PKeyConfirmation(
            transcript,
            grant.grantAuthorization,
            P2pNatRole.RUNTIME,
            key,
        )
        val verifiedBinding = ProductionC1CandidateVerifier.verifyP2PTranscriptBinding(
            transcript,
            grant,
            connectorInput,
            P2pNatRole.CLIENT,
            key,
            confirmation,
            authority,
            now,
        )
        key.fill(0)
        confirmation.fill(0)
        val runtime = productionTrustedRuntime().copy(
            fingerprint = authority.runtimeIdentityFingerprint,
            publicKeyBase64 = "runtime-production-public-key",
        )
        return EndpointPersistenceFixture(
            root = root,
            runtime = runtime,
            chain = chain,
            connectorInput = connectorInput,
            verifiedBinding = verifiedBinding,
            connectorSecret = connectorSecret.copyOf(),
            now = now,
        )
    }

    private fun EndpointPersistenceFixture.appliedPreparation():
        ProductionC1EndpointGrantAdmissionPreparation {
        val pair = ProductionPairStateSnapshot(chain.authority, 1uL)
        val ledger = ProductionC1EndpointGrantLedgerState(
            pairAuthorityDigest = chain.authority.digestHex(),
            pairLocalRevision = pair.localRevision,
            remainingGrants = ProductionPairStateContract.MAX_CONSUMED_ENTRIES.toULong(),
            retentionLimit = ProductionPairStateContract.MAX_CONSUMED_ENTRIES.toUInt(),
        )
        val bindingDigest = ProductionC1EndpointGrantAdmission.bindingDigest(
            ENDPOINT_ADMISSION_ID,
            chain.grant.evidence.digestHex(),
            sha256Hex(ProductionSecureSessionCodec.encode(chain.transcript)),
            sha256Hex(ProductionSecureSessionCodec.encode(chain.authorizations.finalP2PDirect)),
            chain.grant.grantAuthorization.digestHex,
            connectorInput.commitmentDigest,
        )
        return ProductionC1EndpointGrantAdmission.prepareForTrustedPersistence(
            ledger,
            ledger.revision,
            ledger.snapshotDigestHex(),
            ENDPOINT_ADMISSION_ID,
            bindingDigest,
            verifiedBinding,
            pair,
            now,
        )
    }

    private fun EndpointPersistenceFixture.committedRetry(
        applied: ProductionC1EndpointGrantAdmissionPreparation,
    ): ProductionC1EndpointGrantAdmissionPreparation =
        ProductionC1EndpointGrantAdmission.prepareCommittedRetry(
            applied.nextState,
            applied.entry.admissionId,
            applied.entry.bindingDigest,
            chain.grant.evidence.canonicalBytes(),
            chain.authorizations.finalP2PDirect,
            ProductionSecureSessionCodec.encode(chain.transcript),
            connectorInput.commitmentDigest,
            applied.nextPairSnapshot,
        )

    private fun loadCandidateFixture(): JSONObject {
        return loadProductionFixture("production-g1a-c-candidate-v1-vectors.json")
    }

    private fun loadProductionFixture(): JSONObject {
        return loadProductionFixture("production-g1a-c-v1-vectors.json")
    }

    private fun loadProductionFixture(fileName: String): JSONObject {
        val relative = Path.of(
            "shared",
            "protocol",
            "fixtures",
            fileName,
        )
        val starts = listOfNotNull(
            Path.of(System.getProperty("user.dir")).toAbsolutePath(),
            javaClass.protectionDomain?.codeSource?.location?.toURI()?.let(Path::of)?.toAbsolutePath(),
        )
        val path = starts.asSequence().flatMap { start ->
            generateSequence(if (Files.isDirectory(start)) start else start.parent) { it.parent }
        }.map { it.resolve(relative) }.firstOrNull(Files::isRegularFile)
            ?: error("shared production G1a-C candidate fixture not found")
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

    private fun sha256Hex(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(bytes).lowerHex()

    private fun exactBoundValidation(
        marker: String,
        pair: String,
        expiresAtMs: ULong = 100uL,
        runtimeDeviceId: String = "runtime-1",
    ): ProductionC1ExactBoundStartValidation = ProductionC1ExactBoundStartValidation(
        runtimeDeviceId = runtimeDeviceId,
        pairAuthorityDigest = pair,
        markerDigest = marker,
        admissionId = marker,
        bindingDigest = "1".repeat(64),
        sessionId = "2".repeat(32),
        effectiveNotBeforeMs = 1uL,
        expiresAtMs = expiresAtMs,
        pairLocalRevision = 2uL,
        ledgerRevision = 2uL,
    )

    private suspend fun authoritySecureSessionFixture(
        authorityPersistenceHooks: ProductionC1AuthorityPersistenceHooks =
            ProductionC1AuthorityPersistenceHooks(),
        trustedNow: (EndpointPersistenceFixture) -> ULong,
    ): AuthoritySecureSessionFixture {
        val fixture = endpointPersistenceFixture()
        val store = PairingStore(
            ApplicationProvider.getApplicationContext(),
            FakeRelaySecretStore(),
            ProductionC1EndpointPersistenceHooks(),
            ProductionC1TrustedClock { trustedNow(fixture) },
            authorityPersistenceHooks,
        )
        store.forgetRuntime()
        store.trustRuntime(fixture.runtime)
        store.applyVerifiedProductionPairTransition(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            ProductionPairStateTransition(null, fixture.chain.authority),
        )
        val preparation = fixture.appliedPreparation()
        val token = (store.commitPreparedProductionC1EndpointGrant(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            requireNotNull(fixture.runtime.publicKeyBase64),
            preparation,
        ) as ProductionC1EndpointGrantCommitOutcome.Committed).token
        val request = ProductionC1ExactBoundStartRequest(
            fixture.runtime.deviceId,
            fixture.runtime.fingerprint,
            requireNotNull(fixture.runtime.publicKeyBase64),
            token,
            fixture.verifiedBinding,
        )
        return AuthoritySecureSessionFixture(
            fixture,
            store,
            preparation,
            request,
            store.exactBoundStartCoordinator(),
            store.authorityPublicationGateForTesting(),
            { trustedNow(fixture) },
        )
    }

    private fun ByteArray.contentContains(needle: ByteArray): Boolean {
        if (needle.isEmpty()) return true
        return indices.any { offset ->
            offset + needle.size <= size &&
                needle.indices.all { index -> this[offset + index] == needle[index] }
        }
    }

    private data class EndpointOperation(
        val proof: String,
        val capability: String,
        val batch: String,
        val receipt: String,
    )

    private data class EndpointChain(
        val authority: ProductionPairAuthorityState,
        val grant: VerifiedProductionC1P2PGrantEvidence,
        val authorizations: ProductionC1BilateralRouteAuthorizations,
        val transcript: ProductionSecureSessionTranscript,
    )

    private data class EndpointPersistenceFixture(
        val root: JSONObject,
        val runtime: TrustedRuntime,
        val chain: EndpointChain,
        val connectorInput: VerifiedProductionC1CandidateP2PConnectorInput,
        val verifiedBinding: VerifiedProductionC1CandidateP2PTranscriptBinding,
        val connectorSecret: ByteArray,
        val now: ULong,
    )

    private data class AuthoritySecureSessionFixture(
        val fixture: EndpointPersistenceFixture,
        val store: PairingStore,
        val preparation: ProductionC1EndpointGrantAdmissionPreparation,
        val request: ProductionC1ExactBoundStartRequest,
        val coordinator: ProductionC1ExactBoundStartCoordinator,
        val publicationGate: ProductionC1AuthorityPublicationGate,
        val nowMs: () -> ULong,
    ) {
        suspend fun begin(
            engine: RecordingAuthoritySecureSessionEngine,
        ): ProductionC1AuthorityBoundSecureSession {
            return ProductionC1AuthorityBoundSecureSession.beginWithFactoryForTesting(
                coordinator,
                request,
                publicationGate,
                nowMs,
                ProductionC1AuthoritySecureSessionEngineFactory { binding ->
                    engine.derivedBinding = binding
                    engine
                },
            )
        }

        fun authorityAdvance(
            transitionIdCharacter: String,
            requestDigestCharacter: String,
            receiptDigestCharacter: String,
        ): ProductionPairStateTransition {
            val previous = preparation.nextPairSnapshot.authority
            return ProductionPairStateTransition(
                previous.digestHex(),
                previous.copy(
                    generation = previous.generation + 1uL,
                    transitionId = transitionIdCharacter.repeat(64),
                    transitionRequestDigest = requestDigestCharacter.repeat(64),
                    acceptedReceiptDigest = receiptDigestCharacter.repeat(64),
                    authorityRevision = previous.authorityRevision + 1uL,
                ),
            )
        }
    }

    private class RecordingAuthoritySecureSessionEngine(
        private val sealEntered: CountDownLatch? = null,
        private val sealRelease: CountDownLatch? = null,
        var failureOnSeal: Throwable? = null,
        private val terminalOnSealFailure: Boolean = false,
    ) : ProductionC1AuthoritySecureSessionEngine {
        lateinit var derivedBinding: VerifiedProductionC1CandidateP2PKeyScheduleBinding
        @Volatile var invalidated = false
        @Volatile var closed = false
        @Volatile var localConfirmationMarked = false
        @Volatile private var reportedTerminal = false
        override val isTerminal: Boolean get() = invalidated || closed || reportedTerminal

        override fun localConfirmation(nowMs: ULong): ByteArray {
            requireLive()
            return ByteArray(32) { 7 }
        }

        override fun markLocalConfirmationSent(encodedConfirmation: ByteArray, nowMs: ULong) {
            requireLive()
            localConfirmationMarked = true
        }

        override fun acceptPeerConfirmation(encodedConfirmation: ByteArray, nowMs: ULong) {
            requireLive()
        }

        override fun activate(nowMs: ULong) {
            requireLive()
        }

        override fun sealApplication(
            plaintext: ByteArray,
            nowMs: ULong,
        ): ProductionC1AuthorityBoundSealResult {
            requireLive()
            sealEntered?.countDown()
            if (sealRelease != null) {
                check(sealRelease.await(5, TimeUnit.SECONDS)) { "seal release timed out" }
            }
            requireLive()
            failureOnSeal?.let { error ->
                reportedTerminal = terminalOnSealFailure
                throw error
            }
            return ProductionC1AuthorityBoundSealResult(
                "sealed".toByteArray(),
                keyUpdateRequired = false,
                terminalAfterRecord = false,
            )
        }

        override fun sealKeyUpdate(nowMs: ULong): ProductionC1AuthorityBoundSealResult {
            requireLive()
            return ProductionC1AuthorityBoundSealResult(
                "update".toByteArray(),
                keyUpdateRequired = false,
                terminalAfterRecord = false,
            )
        }

        override fun open(
            encodedRecord: ByteArray,
            nowMs: ULong,
        ): ProductionC1AuthorityBoundOpenResult {
            requireLive()
            return ProductionC1AuthorityBoundOpenResult(
                "opened".toByteArray(),
                ProductionSecureSessionRecordContentType.APPLICATION,
                keyUpdateRequired = false,
                terminalAfterRecord = false,
            )
        }

        override fun invalidate() {
            invalidated = true
        }

        override fun close() {
            closed = true
            invalidated = true
        }

        private fun requireLive() {
            check(!invalidated && !closed) { "recording engine is terminal" }
        }
    }

    private data class VerifiedStoreFixture(
        val runtime: TrustedRuntime,
        val previousSnapshot: ProductionPairStateSnapshot,
        val nextSnapshot: ProductionPairStateSnapshot,
        val freshTransition: VerifiedProductionC1FreshPairTransition,
        val transcriptBinding: VerifiedProductionC1TranscriptBinding,
        val now: ULong,
    )

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

    private fun productionTrustedRuntime(): TrustedRuntime =
        trustedRuntime(host = null, port = null).copy(
            fingerprint = PRODUCTION_RUNTIME_FINGERPRINT,
        )

    private fun initialProductionTransition(): ProductionPairStateTransition =
        ProductionPairStateTransition(
            expectedPreviousAuthorityDigest = null,
            nextAuthority = ProductionPairAuthorityState(
                pairBindingDigest = PRODUCTION_PAIR_BINDING_DIGEST,
                pairEpoch = 9uL,
                clientIdentityFingerprint = PRODUCTION_CLIENT_FINGERPRINT,
                runtimeIdentityFingerprint = PRODUCTION_RUNTIME_FINGERPRINT,
                generation = 7uL,
                serviceConfigVersion = 3uL,
                keysetVersion = 4uL,
                revocationCounter = 2uL,
                protocolFloor = 1u,
                status = ProductionPairAuthorityStatus.ACTIVE,
                transitionId = "c".repeat(64),
                transitionRequestDigest = "d".repeat(64),
                acceptedReceiptDigest = "e".repeat(64),
                authorityRevision = 1uL,
            ),
        )

    private fun productionRoute(): LocalDirectRouteAuthorization =
        LocalDirectRouteAuthorization(
            pairBindingDigest = PRODUCTION_PAIR_BINDING_DIGEST,
            pairEpoch = 9uL,
            nominatedPathReceiptDigest = "1".repeat(64),
        )

    private fun productionTranscript(
        route: LocalDirectRouteAuthorization,
    ): ProductionSecureSessionTranscript = ProductionSecureSessionTranscript(
        sessionId = "00112233445566778899aabbccddeeff",
        pairBindingDigest = PRODUCTION_PAIR_BINDING_DIGEST,
        pairEpoch = 9uL,
        clientIdentityFingerprint = PRODUCTION_CLIENT_FINGERPRINT,
        runtimeIdentityFingerprint = PRODUCTION_RUNTIME_FINGERPRINT,
        clientEphemeralPublicKey = PRODUCTION_CLIENT_EPHEMERAL_KEY_HEX.hexBytes(),
        runtimeEphemeralPublicKey = PRODUCTION_RUNTIME_EPHEMERAL_KEY_HEX.hexBytes(),
        clientNonce = "0123456789abcdeffedcba9876543210",
        runtimeNonce = "ffeeddccbbaa99887766554433221100",
        generation = 7uL,
        serviceConfigVersion = 3uL,
        keysetVersion = 4uL,
        revocationCounter = 2uL,
        routeAuthorizationKind = ProductionRouteAuthorizationKind.LOCAL_DIRECT,
        routeAuthorizationDigest = ProductionSecureSessionCodec.digest(route).lowerHex(),
    )

    private suspend fun storedProductionPairStateBase64(): String? =
        ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore.data.first()[stringPreferencesKey(PRODUCTION_PAIR_STATE_KEY)]

    private suspend fun storedEndpointCompoundBase64(): String? =
        ApplicationProvider.getApplicationContext<android.content.Context>()
            .localAgentBridgeDataStore.data.first()[stringPreferencesKey(PRODUCTION_ENDPOINT_COMPOUND_KEY)]

    private fun String.hexBytes(): ByteArray {
        require(length % 2 == 0)
        return chunked(2).map { it.toInt(16).toByte() }.toByteArray()
    }

    private fun ByteArray.lowerHex(): String =
        joinToString("") { "%02x".format(it.toInt() and 0xff) }

    private fun completeRelayRuntime(): TrustedRuntime {
        return trustedRuntime(host = "192.168.1.10", port = 43170).copy(
            relayHost = "relay.example.test",
            relayPort = 443,
            relayId = "relay-1",
            relaySecret = "secret-1",
            relayExpiresAtEpochMillis = 4102444800000L,
            relayNonce = "nonce-route-1",
            relayScope = "remote",
        )
    }

    private fun completeP2pRuntime(): TrustedRuntime {
        return trustedRuntime(host = "192.168.1.10", port = 43170).copy(
            p2pRouteClass = "p2p_rendezvous",
            p2pRecordId = "p2p-record-1",
            p2pEncryptedBody = "opaque-candidate-1",
            p2pExpiresAtEpochMillis = 4102444800000L,
            p2pAntiReplayNonce = "nonce-p2p-1",
            p2pProtocolVersion = 1,
        )
    }

    private fun nonCanonicalRelayHostValues(): List<String> = listOf(
        " relay.example.test",
        "relay.example.test ",
        "relay example.test",
        "https://relay.example.test",
        "relay.example.test/path",
        "relay.example.test?route=1",
        "relay.example.test#fragment",
        "user@relay.example.test",
    )

    private fun nonCanonicalRelayScopeValues(): List<String> = listOf(
        "",
        "public",
        "REMOTE",
        " remote ",
        "privateOverlay",
        "USB_REVERSE",
    )

    private fun pairingStore(
        relaySecretStore: DurableRelaySecretStore = FakeRelaySecretStore(),
        productionNowMs: ULong? = null,
    ): PairingStore {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        return if (productionNowMs == null) {
            PairingStore(context, relaySecretStore)
        } else {
            PairingStore(
                context,
                relaySecretStore,
                ProductionC1EndpointPersistenceHooks(),
                ProductionC1TrustedClock { productionNowMs },
            )
        }
    }

    private fun assertNoStoredRelayRoute(prefs: androidx.datastore.preferences.core.Preferences) {
        assertNull(prefs[stringPreferencesKey("runtime_relay_host")])
        assertNull(prefs[intPreferencesKey("runtime_relay_port")])
        assertNull(prefs[stringPreferencesKey("runtime_relay_id")])
        assertNull(prefs[stringPreferencesKey("runtime_relay_secret")])
        assertNull(prefs[stringPreferencesKey("runtime_relay_secret_ref")])
        assertNull(prefs[longPreferencesKey("runtime_relay_expires_at_epoch_millis")])
        assertNull(prefs[stringPreferencesKey("runtime_relay_nonce")])
        assertNull(prefs[stringPreferencesKey("runtime_relay_scope")])
        assertNull(prefs[longPreferencesKey("runtime_relay_ticket_generation")])
        assertNull(prefs[stringSetPreferencesKey("runtime_relay_secret_cleanup_refs")])
    }

    private fun assertNoStoredP2pRoute(prefs: androidx.datastore.preferences.core.Preferences) {
        assertNull(prefs[stringPreferencesKey("runtime_p2p_route_class")])
        assertNull(prefs[stringPreferencesKey("runtime_p2p_record_id")])
        assertNull(prefs[stringPreferencesKey("runtime_p2p_encrypted_body")])
        assertNull(prefs[longPreferencesKey("runtime_p2p_expires_at_epoch_millis")])
        assertNull(prefs[stringPreferencesKey("runtime_p2p_anti_replay_nonce")])
        assertNull(prefs[intPreferencesKey("runtime_p2p_protocol_version")])
    }

    private fun assertNoStoredDirectEndpoint(prefs: androidx.datastore.preferences.core.Preferences) {
        assertNull(prefs[stringPreferencesKey("runtime_host")])
        assertNull(prefs[intPreferencesKey("runtime_port")])
        assertNull(prefs[stringPreferencesKey("mac_host")])
        assertNull(prefs[intPreferencesKey("mac_port")])
    }

    private fun assertNoStoredRouteToken(prefs: androidx.datastore.preferences.core.Preferences) {
        assertNull(prefs[stringPreferencesKey("runtime_route_token")])
        assertNull(prefs[stringPreferencesKey("mac_route_token")])
    }

    private fun assertNoStoredTrustedRuntime(prefs: Preferences) {
        assertNull(prefs[stringPreferencesKey("runtime_device_id")])
        assertNull(prefs[stringPreferencesKey("runtime_name")])
        assertNull(prefs[stringPreferencesKey("runtime_fingerprint")])
        assertNull(prefs[stringPreferencesKey("runtime_public_key")])
        assertNull(prefs[stringPreferencesKey("runtime_route_token")])
        assertNull(prefs[stringPreferencesKey("mac_device_id")])
        assertNull(prefs[stringPreferencesKey("mac_name")])
        assertNull(prefs[stringPreferencesKey("mac_fingerprint")])
        assertNull(prefs[stringPreferencesKey("mac_public_key")])
        assertNull(prefs[stringPreferencesKey("mac_route_token")])
        assertNoStoredDirectEndpoint(prefs)
        assertNoStoredRelayRoute(prefs)
        assertNoStoredP2pRoute(prefs)
    }

    private fun ByteArray.indexOfSubsequence(needle: ByteArray): Int {
        if (needle.isEmpty() || needle.size > size) return -1
        return (0..size - needle.size).firstOrNull { start ->
            needle.indices.all { offset -> this[start + offset] == needle[offset] }
        } ?: -1
    }

    private companion object {
        const val PRODUCTION_PAIR_STATE_KEY = "runtime_production_pair_state"
        const val PRODUCTION_ENDPOINT_COMPOUND_KEY = "runtime_production_endpoint_compound_state"
        const val ENDPOINT_MARKER_SESSION_ID_OFFSET = 8 + 4 + 4 + (5 * 32)
        const val ENDPOINT_MARKER_ROUTE_AUTHORIZATION_DIGEST_OFFSET =
            ENDPOINT_MARKER_SESSION_ID_OFFSET + 32
        const val ENDPOINT_MARKER_GRANT_AUTHORIZATION_DIGEST_OFFSET =
            ENDPOINT_MARKER_ROUTE_AUTHORIZATION_DIGEST_OFFSET + 32
        const val ENDPOINT_MARKER_PAIR_AUTHORITY_DIGEST_OFFSET =
            ENDPOINT_MARKER_GRANT_AUTHORIZATION_DIGEST_OFFSET + 32
        const val ENDPOINT_MARKER_EFFECTIVE_NOT_BEFORE_OFFSET = 8 + 4 + 4 + (9 * 32)
        const val ENDPOINT_ADMISSION_ID =
            "9999999999999999999999999999999999999999999999999999999999999999"
        const val PRODUCTION_PAIR_BINDING_DIGEST =
            "102132435465768798a9bacbdcedfe0f102132435465768798a9bacbdcedfe0f"
        const val PRODUCTION_CLIENT_FINGERPRINT =
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        const val PRODUCTION_RUNTIME_FINGERPRINT =
            "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        const val PRODUCTION_CLIENT_EPHEMERAL_KEY_HEX =
            "046b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296" +
                "4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5"
        const val PRODUCTION_RUNTIME_EPHEMERAL_KEY_HEX =
            "047cf27b188d034f7e8a52380304b51ac3c08969e277f21b35a60b48fc476699780" +
                "7775510db8ed040293d9ac69f7430dbba7dade63ce982299e04b79d227873d1"
        val ENDPOINT_OPERATIONS = listOf(
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
    }

    private class FakeRelaySecretStore : DurableRelaySecretStore {
        val secrets = linkedMapOf<String, String>()
        val asynchronouslySavedHandles = mutableListOf<String>()
        val durablySavedHandles = mutableListOf<String>()
        val durablyRemovedHandles = mutableListOf<String>()
        var failNextDurableSave = false
        var retainFailedDurableSave = true
        var failNextDurableRemoval = false

        override fun saveSecret(handle: String, secret: String) {
            asynchronouslySavedHandles += handle
            secrets[handle] = secret
        }

        override fun saveSecretDurably(handle: String, secret: String): Boolean {
            durablySavedHandles += handle
            if (failNextDurableSave) {
                failNextDurableSave = false
                if (retainFailedDurableSave) {
                    secrets[handle] = secret
                }
                return false
            }
            secrets[handle] = secret
            return true
        }

        override fun readSecret(handle: String): String? {
            return secrets[handle]
        }

        override fun removeSecret(handle: String) {
            secrets.remove(handle)
        }

        override fun removeSecretDurably(handle: String): Boolean {
            durablyRemovedHandles += handle
            if (failNextDurableRemoval) {
                failNextDurableRemoval = false
                return false
            }
            secrets.remove(handle)
            return true
        }
    }
}
