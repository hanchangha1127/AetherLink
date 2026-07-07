package com.localagentbridge.android.core.pairing

import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
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

    private fun pairingStore(relaySecretStore: RelaySecretStore = FakeRelaySecretStore()): PairingStore {
        return PairingStore(ApplicationProvider.getApplicationContext(), relaySecretStore)
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

    private class FakeRelaySecretStore : RelaySecretStore {
        val secrets = linkedMapOf<String, String>()

        override fun saveSecret(handle: String, secret: String) {
            secrets[handle] = secret
        }

        override fun readSecret(handle: String): String? {
            return secrets[handle]
        }

        override fun removeSecret(handle: String) {
            secrets.remove(handle)
        }
    }
}
