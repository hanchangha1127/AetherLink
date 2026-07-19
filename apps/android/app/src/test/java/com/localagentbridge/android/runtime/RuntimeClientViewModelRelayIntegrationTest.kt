package com.localagentbridge.android.runtime

import android.app.Application
import androidx.lifecycle.viewModelScope
import com.localagentbridge.android.core.pairing.DeviceIdentity
import com.localagentbridge.android.core.pairing.INITIAL_PAIRING_PROOF_SCHEME
import com.localagentbridge.android.core.pairing.InitialPairingAcceptedResult
import com.localagentbridge.android.core.pairing.InitialPairingClientRequest
import com.localagentbridge.android.core.pairing.PairedRelayAllocationAuthorization
import com.localagentbridge.android.core.pairing.PairedRelayAllocationAuthorizationProof
import com.localagentbridge.android.core.pairing.RuntimeIdentityProofVerifier
import com.localagentbridge.android.core.pairing.TrustedRuntime
import com.localagentbridge.android.core.protocol.AuthChallengePayload
import com.localagentbridge.android.core.protocol.AuthResponsePayload
import com.localagentbridge.android.core.protocol.ChatSendPayload
import com.localagentbridge.android.core.protocol.HelloPayload
import com.localagentbridge.android.core.protocol.IndexDocumentsListRequestPayload
import com.localagentbridge.android.core.protocol.IndexDocumentsListResultPayload
import com.localagentbridge.android.core.protocol.IndexDocumentsQualityCountsPayload
import com.localagentbridge.android.core.protocol.IndexDocumentsSummaryPayload
import com.localagentbridge.android.core.protocol.MessageType
import com.localagentbridge.android.core.protocol.ModelInfoPayload
import com.localagentbridge.android.core.protocol.ModelsResultPayload
import com.localagentbridge.android.core.protocol.PairingRequestPayload
import com.localagentbridge.android.core.protocol.PairingResultPayload
import com.localagentbridge.android.core.protocol.PAIRED_CLIENT_RELAY_REGISTRATION_CHALLENGE_PREFIX
import com.localagentbridge.android.core.protocol.PairedClientRelayRegistrationChallenge
import com.localagentbridge.android.core.protocol.PairedClientRelayRegistrationProof
import com.localagentbridge.android.core.protocol.ProtocolCodec
import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import com.localagentbridge.android.core.protocol.RetrievalQueryRequestPayload
import com.localagentbridge.android.core.protocol.RetrievalQueryResultItemPayload
import com.localagentbridge.android.core.protocol.RetrievalQueryResultPayload
import com.localagentbridge.android.core.protocol.RelayAllocationAuthorizationPayload
import com.localagentbridge.android.core.protocol.RelayAllocationChallengePayload
import com.localagentbridge.android.core.protocol.RouteRefreshPayload
import com.localagentbridge.android.core.protocol.RuntimeDocumentIndexDocumentPayload
import com.localagentbridge.android.core.protocol.RuntimeHealthPayload
import com.localagentbridge.android.core.transport.DiscoveredRuntime
import com.localagentbridge.android.core.transport.RelayClientRegistrationAuthorizer
import com.localagentbridge.android.core.transport.RuntimeRelaySocketFactory
import com.localagentbridge.android.core.transport.RuntimeRelayTcpClient
import com.localagentbridge.android.core.transport.RuntimeTransportClient
import com.localagentbridge.android.core.transport.RuntimeTransportConnector
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.encodeToJsonElement
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.Closeable
import java.io.InputStream
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketTimeoutException
import java.nio.ByteBuffer
import java.math.BigInteger
import java.security.AlgorithmParameters
import java.security.KeyFactory
import java.security.KeyPair
import java.security.KeyPairGenerator
import java.security.MessageDigest
import java.security.Signature
import java.security.spec.ECGenParameterSpec
import java.security.spec.ECParameterSpec
import java.security.spec.ECPoint
import java.security.spec.ECPublicKeySpec
import java.security.spec.X509EncodedKeySpec
import java.util.Base64
import java.util.concurrent.CompletableFuture
import java.util.concurrent.TimeUnit
import javax.crypto.Cipher
import javax.crypto.KeyAgreement
import javax.crypto.Mac
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec
import java.security.interfaces.ECPublicKey
import kotlin.concurrent.thread

private const val TEST_RUNTIME_RELAY_SESSION_NONCE = "ffeeddccbbaa99887766554433221100"
private val TEST_RELAY_SESSION_NONCE_PATTERN = Regex("^[0-9a-f]{32}$")
private val TEST_RELAY_EPHEMERAL_KEY_PATTERN = Regex("^04[0-9a-f]{128}$")

private data class TestRelayClientHandshake(
    val sessionNonce: String,
    val ephemeralKey: String,
)

private fun clientRelayHandshake(handshake: String, relayId: String): TestRelayClientHandshake {
    val pattern = Regex(
        "AETHERLINK_RELAY client ${Regex.escape(relayId)} crypto=2 " +
            "session_nonce=([0-9a-f]{32}) ephemeral_key=(04[0-9a-f]{128})",
    )
    val match = requireNotNull(pattern.matchEntire(handshake)) { "Unexpected relay handshake" }
    return TestRelayClientHandshake(
        sessionNonce = match.groupValues[1],
        ephemeralKey = match.groupValues[2],
    ).also {
        require(TEST_RELAY_SESSION_NONCE_PATTERN.matches(it.sessionNonce))
        require(TEST_RELAY_EPHEMERAL_KEY_PATTERN.matches(it.ephemeralKey))
    }
}

private data class TestRelaySession(
    val bindingId: String,
    val clientTrafficSecret: ByteArray,
    val runtimeTrafficSecret: ByteArray,
)

private class TestRelaySessionKeyConfirmationV2(
    secret: String,
    relayId: String,
    routeNonce: String,
    clientSessionNonce: String,
    runtimeSessionNonce: String,
    clientEphemeralKey: String,
    runtimeKeyPair: KeyPair,
) {
    val runtimeEphemeralKey = runtimeKeyPair.public.toX963Hex()
    private val bindingDigest = MessageDigest.getInstance("SHA-256").digest(
        (
            "AetherLink relay session binding v2\ncrypto_version\n2\nrelay_id\n" +
                relayId +
                "\nroute_nonce\n" +
                routeNonce +
                "\nclient_session_nonce\n" +
                clientSessionNonce +
                "\nruntime_session_nonce\n" +
                runtimeSessionNonce +
                "\nclient_ephemeral_key\n" +
                clientEphemeralKey +
                "\nruntime_ephemeral_key\n" +
                runtimeEphemeralKey
            ).toByteArray(Charsets.UTF_8),
    )
    val bindingId = bindingDigest.toLowercaseHex()
    private val sharedSecret = KeyAgreement.getInstance("ECDH").run {
        init(runtimeKeyPair.private)
        doPhase(clientEphemeralKey.toP256PublicKey(), true)
        generateSecret()
    }
    private val ikm = sharedSecret + secret.toByteArray(Charsets.UTF_8)
    private val confirmationKey = hkdfSha256(
        ikm = ikm,
        salt = bindingDigest,
        info = "AetherLink relay confirmation v2".toByteArray(Charsets.UTF_8),
    )
    val clientTrafficSecret = hkdfSha256(
        ikm = ikm,
        salt = bindingDigest,
        info = "AetherLink relay client traffic v2".toByteArray(Charsets.UTF_8),
    )
    val runtimeTrafficSecret = hkdfSha256(
        ikm = ikm,
        salt = bindingDigest,
        info = "AetherLink relay runtime traffic v2".toByteArray(Charsets.UTF_8),
    )

    fun controlLine(role: String): String {
        val message = (
            "AetherLink relay key confirmation v2\nrole\n" +
                role +
                "\ntransport_binding\n" +
                bindingId
            ).toByteArray(Charsets.UTF_8)
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(confirmationKey, "HmacSHA256"))
        return "AETHERLINK_RELAY confirm $role binding=$bindingId proof=${mac.doFinal(message).toLowercaseHex()}"
    }
}

private fun completeRelayKeyConfirmation(
    input: InputStream,
    output: java.io.OutputStream,
    relayId: String,
    relaySecret: String,
    routeNonce: String,
    clientHandshake: TestRelayClientHandshake,
): TestRelaySession {
    val runtimeKeyPair = KeyPairGenerator.getInstance("EC").run {
        initialize(ECGenParameterSpec("secp256r1"))
        generateKeyPair()
    }
    val confirmation = TestRelaySessionKeyConfirmationV2(
        secret = relaySecret,
        relayId = relayId,
        routeNonce = routeNonce,
        clientSessionNonce = clientHandshake.sessionNonce,
        runtimeSessionNonce = TEST_RUNTIME_RELAY_SESSION_NONCE,
        clientEphemeralKey = clientHandshake.ephemeralKey,
        runtimeKeyPair = runtimeKeyPair,
    )
    output.write(
        (
            "AETHERLINK_RELAY ready crypto=2 " +
                "peer_session_nonce=$TEST_RUNTIME_RELAY_SESSION_NONCE " +
                "peer_ephemeral_key=${confirmation.runtimeEphemeralKey}\n"
            )
            .toByteArray(Charsets.UTF_8),
    )
    output.flush()
    require(input.readAsciiLine() == confirmation.controlLine("client")) {
        "Relay client key confirmation failed"
    }
    output.write("${confirmation.controlLine("runtime")}\n".toByteArray(Charsets.UTF_8))
    output.flush()
    return TestRelaySession(
        bindingId = confirmation.bindingId,
        clientTrafficSecret = confirmation.clientTrafficSecret,
        runtimeTrafficSecret = confirmation.runtimeTrafficSecret,
    )
}

private fun ByteArray.toLowercaseHex(): String {
    val digits = "0123456789abcdef"
    val result = CharArray(size * 2)
    forEachIndexed { index, byte ->
        val value = byte.toInt() and 0xff
        result[index * 2] = digits[value ushr 4]
        result[index * 2 + 1] = digits[value and 0x0f]
    }
    return String(result)
}

private fun String.toHexBytes(): ByteArray {
    require(length % 2 == 0 && all { it in '0'..'9' || it in 'a'..'f' })
    return ByteArray(length / 2) { index ->
        substring(index * 2, index * 2 + 2).toInt(16).toByte()
    }
}

private fun java.security.PublicKey.toX963Hex(): String {
    val publicKey = this as ECPublicKey
    return (
        byteArrayOf(0x04) +
            publicKey.w.affineX.toUnsignedFixedBytes(32) +
            publicKey.w.affineY.toUnsignedFixedBytes(32)
        ).toLowercaseHex()
}

private fun BigInteger.toUnsignedFixedBytes(size: Int): ByteArray {
    val encoded = toByteArray()
    val unsigned = if (encoded.size == size + 1 && encoded.first() == 0.toByte()) {
        encoded.copyOfRange(1, encoded.size)
    } else {
        encoded
    }
    require(unsigned.size <= size)
    return ByteArray(size - unsigned.size) + unsigned
}

private fun String.toP256PublicKey(): java.security.PublicKey {
    require(TEST_RELAY_EPHEMERAL_KEY_PATTERN.matches(this))
    val bytes = toHexBytes()
    val parameters = AlgorithmParameters.getInstance("EC").apply {
        init(ECGenParameterSpec("secp256r1"))
    }.getParameterSpec(ECParameterSpec::class.java)
    val point = ECPoint(
        BigInteger(1, bytes.copyOfRange(1, 33)),
        BigInteger(1, bytes.copyOfRange(33, 65)),
    )
    return KeyFactory.getInstance("EC").generatePublic(ECPublicKeySpec(point, parameters))
}

private fun hkdfSha256(ikm: ByteArray, salt: ByteArray, info: ByteArray): ByteArray {
    val extract = Mac.getInstance("HmacSHA256").run {
        init(SecretKeySpec(salt, "HmacSHA256"))
        doFinal(ikm)
    }
    return Mac.getInstance("HmacSHA256").run {
        init(SecretKeySpec(extract, "HmacSHA256"))
        doFinal(info + byteArrayOf(1))
    }
}

class RuntimeClientViewModelRelayIntegrationTest {
    private val json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
        encodeDefaults = true
    }
    private val testClientKeyPair = KeyPairGenerator.getInstance("EC")
        .apply { initialize(ECGenParameterSpec("secp256r1")) }
        .generateKeyPair()

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun compactRelayQrPairingUsesRealRelayTcpClientAndPersistsTrustedRelay() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        val relaySecret = "real-relay-secret"
        val relayNonce = "real-relay-nonce"
        val relayId = "real-relay-id"
        FakeRelayRuntimeServer(
            json = json,
            relayId = relayId,
            relaySecret = relaySecret,
            relayNonce = relayNonce,
            runtimeDeviceId = "runtime-real",
        ).use { relay ->
            var viewModel: RuntimeClientViewModel? = null
            try {
                val trustedRuntimeStore = FakeTrustedRuntimeStore()
                val localStore = FakeRuntimeLocalDataStore(
                    initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = false),
                )
                var directConnectionAttempts = 0
                viewModel = RuntimeClientViewModel(
                    application = Application(),
                    dependencies = RuntimeClientViewModelDependencies(
                        json = json,
                        transportClient = RuntimeTransportClient(),
                        transportConnector = RuntimeTransportConnector { _, _, _ ->
                            directConnectionAttempts += 1
                            error("Direct TCP must not be used for relay QR pairing")
                        },
                        relayConnector = RuntimeRelayTcpClient(),
                        discovery = EmptyRuntimeDiscoverySource,
                        trustedRuntimeStore = trustedRuntimeStore,
                        deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                        localDataStore = localStore,
                        lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                        allowDebugUsbReverseRoutes = true,
                        currentTimeMillis = { 1_000L },
                    ),
                )
                val rawUri = "aetherlink://pair?v=1&n=nonce-real&c=246810" +
                    "&rid=runtime-real&rn=AetherLink%20Runtime&rf=${relay.runtimeFingerprint}" +
                    "&rk=${relay.runtimePublicKey}&rt=route-real" +
                    "&rh=127.0.0.1&rp=${relay.port}&ri=$relayId&rs=$relaySecret" +
                    "&rx=4102444800000&rrn=$relayNonce&rsc=usb_reverse"

                viewModel.trustRuntimeFromPairingQr(rawUri)

                val pairingEnvelope = awaitFuture(relay.pairingRequest)
                val pairingPayload = json.decodeFromJsonElement(
                    PairingRequestPayload.serializer(),
                    pairingEnvelope.payload,
                )
                val trusted = awaitFuture(trustedRuntimeStore.trustedRuntimeWritten)

                assertEquals(0, directConnectionAttempts)
                assertEquals(MessageType.PairingRequest, pairingEnvelope.type)
                assertEquals("nonce-real", pairingPayload.pairingNonce)
                assertEquals("246810", pairingPayload.pairingCode)
                assertEquals("client-real", pairingPayload.deviceId)
                assertEquals("AetherLink Test Client", pairingPayload.deviceName)
                assertEquals(Base64.getEncoder().encodeToString(testClientKeyPair.public.encoded), pairingPayload.publicKey)
                assertEquals(32, clientRelayHandshake(relay.handshakeLine.get(1, TimeUnit.SECONDS), relayId).sessionNonce.length)
                assertEquals("runtime-real", trusted.deviceId)
                assertEquals("route-real", trusted.routeToken)
                assertNull(trusted.host)
                assertNull(trusted.port)
                assertEquals("127.0.0.1", trusted.relayHost)
                assertEquals(relay.port, trusted.relayPort)
                assertEquals(relayId, trusted.relayId)
                assertEquals(relaySecret, trusted.relaySecret)
                assertEquals(4102444800000L, trusted.relayExpiresAtEpochMillis)
                assertEquals(relayNonce, trusted.relayNonce)
                assertEquals("usb_reverse", trusted.relayScope)
                assertNull(localStore.data.pendingPairingRoute)
                assertTrue(localStore.data.trustedRuntimeAutoReconnectEnabled)
                assertTrue(localStore.data.pairingOnboardingCompleted)
                val connectedState = awaitActiveRouteKind(viewModel, RuntimeActiveRouteKind.Relay)
                assertEquals("127.0.0.1", connectedState.trustedRuntime?.relayHost)
                assertEquals(RuntimeActiveRouteKind.Relay, connectedState.activeRouteKind)
                assertNull(relay.closedWithoutServerError())
            } finally {
                viewModel?.stopForTest()
                Thread.sleep(100)
                advanceUntilIdle()
                Dispatchers.resetMain()
            }
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun privateOverlayRelayQrPairingUsesRealRelayTcpClientAndPersistsOverlayRoute() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        val relaySecret = "overlay-relay-secret"
        val relayNonce = "overlay-relay-nonce"
        val relayId = "overlay-relay-id"
        FakeRelayRuntimeServer(
            json = json,
            relayId = relayId,
            relaySecret = relaySecret,
            relayNonce = relayNonce,
            runtimeDeviceId = "runtime-overlay",
        ).use { relay ->
            var viewModel: RuntimeClientViewModel? = null
            try {
                val trustedRuntimeStore = FakeTrustedRuntimeStore()
                val localStore = FakeRuntimeLocalDataStore(
                    initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = false),
                )
                var directConnectionAttempts = 0
                val socketFactory = RuntimeRelaySocketFactory { route, timeoutMillis ->
                    assertEquals("100.64.1.10", route.host)
                    assertEquals(443, route.port)
                    assertEquals(relayId, route.relayId)
                    assertEquals(relaySecret, route.relayFrameSecret)
                    assertEquals(relayNonce, route.security.antiReplayNonce)
                    Socket().apply {
                        tcpNoDelay = true
                        soTimeout = timeoutMillis
                        connect(InetSocketAddress("127.0.0.1", relay.port), timeoutMillis)
                    }
                }
                viewModel = RuntimeClientViewModel(
                    application = Application(),
                    dependencies = RuntimeClientViewModelDependencies(
                        json = json,
                        transportClient = RuntimeTransportClient(),
                        transportConnector = RuntimeTransportConnector { _, _, _ ->
                            directConnectionAttempts += 1
                            error("Direct TCP must not be used for private-overlay relay QR pairing")
                        },
                        relayConnector = RuntimeRelayTcpClient(socketFactory = socketFactory),
                        discovery = EmptyRuntimeDiscoverySource,
                        trustedRuntimeStore = trustedRuntimeStore,
                        deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                        localDataStore = localStore,
                        lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                        currentTimeMillis = { 1_000L },
                    ),
                )
                val rawUri = "aetherlink://pair?v=1&n=nonce-overlay&c=135790" +
                    "&rid=runtime-overlay&rn=AetherLink%20Runtime&rf=${relay.runtimeFingerprint}" +
                    "&rk=${relay.runtimePublicKey}&rt=route-overlay" +
                    "&rh=100.64.1.10&rp=443&ri=$relayId&rs=$relaySecret" +
                    "&rx=4102444800000&rrn=$relayNonce&rsc=private_overlay"

                viewModel.trustRuntimeFromPairingQr(rawUri)

                val pairingEnvelope = awaitFuture(relay.pairingRequest)
                val pairingPayload = json.decodeFromJsonElement(
                    PairingRequestPayload.serializer(),
                    pairingEnvelope.payload,
                )
                val trusted = awaitFuture(trustedRuntimeStore.trustedRuntimeWritten)

                assertEquals(0, directConnectionAttempts)
                assertEquals(MessageType.PairingRequest, pairingEnvelope.type)
                assertEquals("nonce-overlay", pairingPayload.pairingNonce)
                assertEquals("135790", pairingPayload.pairingCode)
                assertEquals("client-real", pairingPayload.deviceId)
                assertEquals(32, clientRelayHandshake(relay.handshakeLine.get(1, TimeUnit.SECONDS), relayId).sessionNonce.length)
                assertEquals("runtime-overlay", trusted.deviceId)
                assertEquals("route-overlay", trusted.routeToken)
                assertNull(trusted.host)
                assertNull(trusted.port)
                assertEquals("100.64.1.10", trusted.relayHost)
                assertEquals(443, trusted.relayPort)
                assertEquals(relayId, trusted.relayId)
                assertEquals(relaySecret, trusted.relaySecret)
                assertEquals(4102444800000L, trusted.relayExpiresAtEpochMillis)
                assertEquals(relayNonce, trusted.relayNonce)
                assertEquals("private_overlay", trusted.relayScope)
                assertNull(localStore.data.pendingPairingRoute)
                assertTrue(localStore.data.trustedRuntimeAutoReconnectEnabled)
                assertTrue(localStore.data.pairingOnboardingCompleted)
                val connectedState = awaitActiveRouteKind(viewModel, RuntimeActiveRouteKind.Relay)
                assertEquals("100.64.1.10", connectedState.trustedRuntime?.relayHost)
                assertEquals("private_overlay", connectedState.trustedRuntime?.relayScope)
                assertEquals(RuntimeActiveRouteKind.Relay, connectedState.activeRouteKind)
                assertNull(relay.closedWithoutServerError())
            } finally {
                viewModel?.stopForTest()
                Thread.sleep(100)
                advanceUntilIdle()
                Dispatchers.resetMain()
            }
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun trustedPrivateOverlayRelayReconnectUsesRealRelayTcpClientAndAuthenticatedSession() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        val relaySecret = "trusted-overlay-relay-secret"
        val relayNonce = "trusted-overlay-relay-nonce"
        val refreshedRelayNonce = "trusted-overlay-relay-nonce-refreshed"
        val currentRelayExpiresAt = 4_102_444_800_000L
        val refreshedRelayExpiresAt = 4102448400000L
        val routeToken = "route-trusted-overlay"
        val currentTicketGeneration = 7L
        val runtimeIdentity = testRuntimeIdentityMaterial()
        val clientPublicKeyBase64 = Base64.getEncoder().encodeToString(testClientKeyPair.public.encoded)
        val clientFingerprint = MessageDigest.getInstance("SHA-256")
            .digest(Base64.getDecoder().decode(clientPublicKeyBase64))
            .joinToString("") { "%02x".format(it) }
        val relayId = PairedRelayAllocationAuthorizationProof.pairedRelayId(
            routeToken = routeToken,
            runtimeKeyFingerprint = runtimeIdentity.fingerprint,
            clientKeyFingerprint = clientFingerprint,
        )
        FakeAuthenticatedRelayRuntimeServer(
            json = json,
            relayId = relayId,
            relaySecret = relaySecret,
            relayNonce = relayNonce,
            refreshedRelayNonce = refreshedRelayNonce,
            refreshedRelayExpiresAtEpochMillis = refreshedRelayExpiresAt,
            runtimeIdentity = runtimeIdentity,
            routeToken = routeToken,
            currentRelayExpiresAtEpochMillis = currentRelayExpiresAt,
            currentTicketGeneration = currentTicketGeneration,
            clientPublicKeyBase64 = clientPublicKeyBase64,
        ).use { relay ->
            var viewModel: RuntimeClientViewModel? = null
            try {
                val trustedRuntimeStore = FakeTrustedRuntimeStore(
                    initialRuntime = TrustedRuntime(
                        deviceId = "runtime-trusted-overlay",
                        name = "AetherLink Runtime",
                        fingerprint = runtimeIdentity.fingerprint,
                        publicKeyBase64 = runtimeIdentity.publicKeyBase64,
                        routeToken = routeToken,
                        host = null,
                        port = null,
                        relayHost = "100.64.2.20",
                        relayPort = 443,
                        relayId = relayId,
                        relaySecret = relaySecret,
                        relayExpiresAtEpochMillis = currentRelayExpiresAt,
                        relayNonce = relayNonce,
                        relayScope = "private_overlay",
                        relayTicketGeneration = currentTicketGeneration,
                    ),
                )
                val localStore = FakeRuntimeLocalDataStore(
                    initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = true),
                )
                var directConnectionAttempts = 0
                val socketFactory = RuntimeRelaySocketFactory { route, timeoutMillis ->
                    assertEquals("100.64.2.20", route.host)
                    assertEquals(443, route.port)
                    assertEquals(relayId, route.relayId)
                    assertEquals(relaySecret, route.relayFrameSecret)
                    assertEquals(relayNonce, route.security.antiReplayNonce)
                    Socket().apply {
                        tcpNoDelay = true
                        soTimeout = timeoutMillis
                        connect(InetSocketAddress("127.0.0.1", relay.port), timeoutMillis)
                    }
                }
                viewModel = RuntimeClientViewModel(
                    application = Application(),
                    dependencies = RuntimeClientViewModelDependencies(
                        json = json,
                        transportClient = RuntimeTransportClient(),
                        transportConnector = RuntimeTransportConnector { _, _, _ ->
                            directConnectionAttempts += 1
                            error("Direct TCP must not be used for private-overlay trusted relay reconnect")
                        },
                        relayConnector = RuntimeRelayTcpClient(
                            socketFactory = socketFactory,
                            clientRegistrationAuthorizer = RelayClientRegistrationAuthorizer { challenge ->
                                val identity = testDeviceIdentity()
                                PairedClientRelayRegistrationProof(
                                    clientPublicKeyBase64 = identity.publicKeyBase64,
                                    clientSignatureBase64 = identity
                                        .signPairedClientRelayRegistrationAuthorization(challenge),
                                )
                            },
                        ),
                        discovery = EmptyRuntimeDiscoverySource,
                        trustedRuntimeStore = trustedRuntimeStore,
                        deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                        localDataStore = localStore,
                        lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                        authenticatedRouteRefreshEnabled = false,
                        currentTimeMillis = { currentRelayExpiresAt - 500L },
                    ),
                )
                viewModel.connectToTrustedRuntime()
                runCurrent()

                val helloEnvelope = awaitFuture(relay.helloRequest)
                val helloPayload = json.decodeFromJsonElement(
                    HelloPayload.serializer(),
                    helloEnvelope.payload,
                )
                val authResponseEnvelope = awaitFuture(relay.authResponseRequest)
                val authResponsePayload = json.decodeFromJsonElement(
                    AuthResponsePayload.serializer(),
                    authResponseEnvelope.payload,
                )
                val routeRefreshEnvelope = awaitFuture(relay.routeRefreshRequest)
                val allocationAuthorizationEnvelope = awaitFuture(relay.allocationAuthorizationRequest)
                val healthEnvelope = awaitFuture(relay.healthRequest)
                val refreshedTrusted = awaitFuture(trustedRuntimeStore.trustedRuntimeWritten)
                val connectedState = awaitActiveRouteKind(viewModel, RuntimeActiveRouteKind.Relay)
                val healthyState = awaitRuntimeStatus(viewModel, "ok")

                viewModel.refreshRuntimeDocumentCatalog()
                val indexDocumentsEnvelope = awaitFuture(relay.indexDocumentsListRequest)
                val indexDocumentsRequest = json.decodeFromJsonElement(
                    IndexDocumentsListRequestPayload.serializer(),
                    indexDocumentsEnvelope.payload,
                )
                val catalogState = awaitDocumentCatalog(viewModel)

                viewModel.searchRuntimeDocuments("  relay document  ")
                val retrievalQueryEnvelope = awaitFuture(relay.retrievalQueryRequest)
                val retrievalQueryRequest = json.decodeFromJsonElement(
                    RetrievalQueryRequestPayload.serializer(),
                    retrievalQueryEnvelope.payload,
                )
                val retrievalState = awaitDocumentSearchResult(viewModel)

                viewModel.requestModels()
                val modelsListEnvelope = awaitFuture(relay.modelsListRequest)
                val modelState = awaitSelectedModel(viewModel, "ollama:relay-chat")

                viewModel.updateChatInput("Use the relay document result")
                viewModel.sendChatMessage()
                val chatSendEnvelope = awaitFuture(relay.chatSendRequest)
                val chatSendPayload = json.decodeFromJsonElement(
                    ChatSendPayload.serializer(),
                    chatSendEnvelope.payload,
                )
                val chatSendPayloadText = chatSendEnvelope.payload.toString()

                assertEquals(0, directConnectionAttempts)
                assertEquals(32, clientRelayHandshake(relay.handshakeLine.get(1, TimeUnit.SECONDS), relayId).sessionNonce.length)
                assertEquals(MessageType.Hello, helloEnvelope.type)
                assertEquals("client-real", helloPayload.deviceId)
                assertEquals("AetherLink Test Client", helloPayload.deviceName)
                assertEquals(MessageType.AuthResponse, authResponseEnvelope.type)
                assertEquals("client-real", authResponsePayload.deviceId)
                assertEquals("trusted-auth-nonce", authResponsePayload.nonce)
                assertTrue(!authResponsePayload.signature.isNullOrBlank())
                assertEquals(MessageType.RouteRefresh, routeRefreshEnvelope.type)
                assertEquals(
                    MessageType.RelayAllocationAuthorization,
                    allocationAuthorizationEnvelope.type,
                )
                assertEquals(routeRefreshEnvelope.requestId, allocationAuthorizationEnvelope.requestId)
                assertEquals(MessageType.RuntimeHealth, healthEnvelope.type)
                assertEquals(MessageType.IndexDocumentsList, indexDocumentsEnvelope.type)
                assertEquals(100, indexDocumentsRequest.limit)
                assertEquals(MessageType.RetrievalQuery, retrievalQueryEnvelope.type)
                assertEquals("relay document", retrievalQueryRequest.query)
                assertEquals(10, retrievalQueryRequest.limit)
                assertEquals(480, retrievalQueryRequest.maxSnippetCharacters)
                assertEquals(MessageType.ModelsList, modelsListEnvelope.type)
                assertEquals("ollama:relay-chat", modelState.selectedModelId)
                assertEquals(MessageType.ChatSend, chatSendEnvelope.type)
                assertEquals("ollama:relay-chat", chatSendPayload.model)
                assertEquals("Use the relay document result", chatSendPayload.messages.last().content)
                listOf(
                    "retrieval_context",
                    "source_path",
                    "workspace_id",
                    "project_id",
                    "citation",
                    "trusted_source",
                    "source_anchor_id",
                    "source_anchor_0011223344556677",
                    "relay-runtime-guide.md",
                    "Relay document search stays inside the authenticated runtime channel.",
                ).forEach { forbidden ->
                    assertTrue(
                        "Document search state must stay out of chat.send payload: $forbidden",
                        !chatSendPayloadText.contains(forbidden),
                    )
                }
                assertEquals("ok", healthyState.runtimeStatus)
                assertEquals("100.64.2.20", connectedState.trustedRuntime?.relayHost)
                assertEquals("private_overlay", connectedState.trustedRuntime?.relayScope)
                assertEquals(RuntimeActiveRouteKind.Relay, connectedState.activeRouteKind)
                assertEquals(1, catalogState.documentCatalog.documents.size)
                assertEquals("relay-doc", catalogState.documentCatalog.documents.single().id)
                assertEquals("relay-runtime-guide.md", catalogState.documentCatalog.documents.single().displayName)
                assertEquals(2, catalogState.documentCatalog.summary.documentCount)
                assertEquals(3, catalogState.documentCatalog.summary.chunkCount)
                assertEquals(1, catalogState.documentCatalog.summary.qualityCounts.chunked)
                assertEquals(1, retrievalState.documentSearchResults.size)
                val searchResult = retrievalState.documentSearchResults.single()
                assertEquals("relay-doc", searchResult.document.id)
                assertEquals("relay-runtime-guide.md", searchResult.document.displayName)
                assertEquals(listOf("relay", "document"), searchResult.matchedTerms)
                assertEquals("Relay document search stays inside the authenticated runtime channel.", searchResult.snippet)
                assertEquals("source_anchor_0011223344556677", searchResult.sourceAnchorId)
                assertEquals("100.64.2.20", refreshedTrusted.relayHost)
                assertEquals(443, refreshedTrusted.relayPort)
                assertEquals(relayId, refreshedTrusted.relayId)
                assertEquals(relaySecret, refreshedTrusted.relaySecret)
                assertEquals(refreshedRelayExpiresAt, refreshedTrusted.relayExpiresAtEpochMillis)
                assertEquals(refreshedRelayNonce, refreshedTrusted.relayNonce)
                assertEquals("private_overlay", refreshedTrusted.relayScope)
                assertEquals(currentTicketGeneration + 1L, refreshedTrusted.relayTicketGeneration)
                assertEquals("100.64.2.20", trustedRuntimeStore.trusted?.relayHost)
                assertEquals(refreshedRelayExpiresAt, trustedRuntimeStore.trusted?.relayExpiresAtEpochMillis)
                assertEquals(refreshedRelayNonce, trustedRuntimeStore.trusted?.relayNonce)
                assertEquals("private_overlay", trustedRuntimeStore.trusted?.relayScope)
                assertEquals(currentTicketGeneration + 1L, trustedRuntimeStore.trusted?.relayTicketGeneration)
                assertEquals(refreshedRelayExpiresAt, viewModel.state.value.trustedRuntime?.relayExpiresAtEpochMillis)
                assertEquals(refreshedRelayNonce, viewModel.state.value.trustedRuntime?.relayNonce)
                assertEquals(
                    currentTicketGeneration + 1L,
                    viewModel.state.value.trustedRuntime?.relayTicketGeneration,
                )
                assertNull(relay.closedWithoutServerError())
            } finally {
                viewModel?.stopForTest()
                Thread.sleep(100)
                advanceUntilIdle()
                Dispatchers.resetMain()
            }
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun trustedRelayReconnectRejectsInvalidRuntimeProofBeforeAuthResponse() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        val relaySecret = "trusted-invalid-proof-relay-secret"
        val relayNonce = "trusted-invalid-proof-relay-nonce"
        val relayId = "trusted-invalid-proof-relay-id"
        val runtimeIdentity = testRuntimeIdentityMaterial()
        FakeInvalidRuntimeProofRelayServer(
            json = json,
            relayId = relayId,
            relaySecret = relaySecret,
            relayNonce = relayNonce,
            runtimeIdentity = runtimeIdentity,
        ).use { relay ->
            var viewModel: RuntimeClientViewModel? = null
            try {
                val trustedRuntimeStore = FakeTrustedRuntimeStore(
                    initialRuntime = TrustedRuntime(
                        deviceId = "runtime-invalid-proof",
                        name = "AetherLink Runtime",
                        fingerprint = runtimeIdentity.fingerprint,
                        publicKeyBase64 = runtimeIdentity.publicKeyBase64,
                        routeToken = "route-invalid-proof",
                        host = null,
                        port = null,
                        relayHost = "100.64.2.21",
                        relayPort = 443,
                        relayId = relayId,
                        relaySecret = relaySecret,
                        relayExpiresAtEpochMillis = 4102444800000L,
                        relayNonce = relayNonce,
                        relayScope = "private_overlay",
                    ),
                )
                val localStore = FakeRuntimeLocalDataStore(
                    initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = true),
                )
                var directConnectionAttempts = 0
                val socketFactory = RuntimeRelaySocketFactory { route, timeoutMillis ->
                    assertEquals("100.64.2.21", route.host)
                    assertEquals(443, route.port)
                    assertEquals(relayId, route.relayId)
                    assertEquals(relaySecret, route.relayFrameSecret)
                    assertEquals(relayNonce, route.security.antiReplayNonce)
                    Socket().apply {
                        tcpNoDelay = true
                        soTimeout = timeoutMillis
                        connect(InetSocketAddress("127.0.0.1", relay.port), timeoutMillis)
                    }
                }
                viewModel = RuntimeClientViewModel(
                    application = Application(),
                    dependencies = RuntimeClientViewModelDependencies(
                        json = json,
                        transportClient = RuntimeTransportClient(),
                        transportConnector = RuntimeTransportConnector { _, _, _ ->
                            directConnectionAttempts += 1
                            error("Direct TCP must not be used for invalid runtime proof relay reconnect")
                        },
                        relayConnector = RuntimeRelayTcpClient(socketFactory = socketFactory),
                        discovery = EmptyRuntimeDiscoverySource,
                        trustedRuntimeStore = trustedRuntimeStore,
                        deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                        localDataStore = localStore,
                        lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                        authenticatedRouteRefreshEnabled = true,
                        currentTimeMillis = { 1_000L },
                    ),
                )

                val helloEnvelope = awaitFuture(relay.helloRequest)
                val postChallengeEnvelope = awaitFuture(relay.postChallengeRequest)
                val errorState = awaitRuntimeError(viewModel, "runtime_authentication_failed")

                assertEquals(0, directConnectionAttempts)
                assertEquals(32, clientRelayHandshake(relay.handshakeLine.get(1, TimeUnit.SECONDS), relayId).sessionNonce.length)
                assertEquals(MessageType.Hello, helloEnvelope.type)
                assertNull(
                    "Android must not send auth.response or runtime.health after invalid runtime proof",
                    postChallengeEnvelope,
                )
                assertEquals("runtime_authentication_failed", errorState.error?.code)
                assertNull(relay.closedWithoutServerError())
            } finally {
                viewModel?.stopForTest()
                Thread.sleep(100)
                advanceUntilIdle()
                Dispatchers.resetMain()
            }
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun trustedRelayReconnectRejectsRuntimeFingerprintMismatchBeforeAuthResponse() = runTest {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        val relaySecret = "trusted-fingerprint-mismatch-relay-secret"
        val relayNonce = "trusted-fingerprint-mismatch-relay-nonce"
        val relayId = "trusted-fingerprint-mismatch-relay-id"
        val runtimeIdentity = testRuntimeIdentityMaterial()
        FakeInvalidRuntimeProofRelayServer(
            json = json,
            relayId = relayId,
            relaySecret = relaySecret,
            relayNonce = relayNonce,
            runtimeIdentity = runtimeIdentity,
            challengeFingerprint = "wrong-runtime-fingerprint",
            signatureNonce = "trusted-auth-nonce",
        ).use { relay ->
            var viewModel: RuntimeClientViewModel? = null
            try {
                val trustedRuntimeStore = FakeTrustedRuntimeStore(
                    initialRuntime = TrustedRuntime(
                        deviceId = "runtime-fingerprint-mismatch",
                        name = "AetherLink Runtime",
                        fingerprint = runtimeIdentity.fingerprint,
                        publicKeyBase64 = runtimeIdentity.publicKeyBase64,
                        routeToken = "route-fingerprint-mismatch",
                        host = null,
                        port = null,
                        relayHost = "100.64.2.22",
                        relayPort = 443,
                        relayId = relayId,
                        relaySecret = relaySecret,
                        relayExpiresAtEpochMillis = 4102444800000L,
                        relayNonce = relayNonce,
                        relayScope = "private_overlay",
                    ),
                )
                val localStore = FakeRuntimeLocalDataStore(
                    initialData = PersistedRuntimeData(trustedRuntimeAutoReconnectEnabled = true),
                )
                var directConnectionAttempts = 0
                val socketFactory = RuntimeRelaySocketFactory { route, timeoutMillis ->
                    assertEquals("100.64.2.22", route.host)
                    assertEquals(443, route.port)
                    assertEquals(relayId, route.relayId)
                    assertEquals(relaySecret, route.relayFrameSecret)
                    assertEquals(relayNonce, route.security.antiReplayNonce)
                    Socket().apply {
                        tcpNoDelay = true
                        soTimeout = timeoutMillis
                        connect(InetSocketAddress("127.0.0.1", relay.port), timeoutMillis)
                    }
                }
                viewModel = RuntimeClientViewModel(
                    application = Application(),
                    dependencies = RuntimeClientViewModelDependencies(
                        json = json,
                        transportClient = RuntimeTransportClient(),
                        transportConnector = RuntimeTransportConnector { _, _, _ ->
                            directConnectionAttempts += 1
                            error("Direct TCP must not be used for runtime fingerprint mismatch relay reconnect")
                        },
                        relayConnector = RuntimeRelayTcpClient(socketFactory = socketFactory),
                        discovery = EmptyRuntimeDiscoverySource,
                        trustedRuntimeStore = trustedRuntimeStore,
                        deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                        localDataStore = localStore,
                        lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                        authenticatedRouteRefreshEnabled = true,
                        currentTimeMillis = { 1_000L },
                    ),
                )

                val helloEnvelope = awaitFuture(relay.helloRequest)
                val postChallengeEnvelope = awaitFuture(relay.postChallengeRequest)
                val errorState = awaitRuntimeError(viewModel, "runtime_authentication_failed")

                assertEquals(0, directConnectionAttempts)
                assertEquals(32, clientRelayHandshake(relay.handshakeLine.get(1, TimeUnit.SECONDS), relayId).sessionNonce.length)
                assertEquals(MessageType.Hello, helloEnvelope.type)
                assertNull(
                    "Android must not send auth.response or runtime.health after runtime fingerprint mismatch",
                    postChallengeEnvelope,
                )
                assertEquals("runtime_authentication_failed", errorState.error?.code)
                assertNull(relay.closedWithoutServerError())
            } finally {
                viewModel?.stopForTest()
                Thread.sleep(100)
                advanceUntilIdle()
                Dispatchers.resetMain()
            }
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    private fun <T> TestScope.awaitFuture(future: CompletableFuture<T>): T {
        val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(4)
        while (!future.isDone && System.nanoTime() < deadline) {
            runCurrent()
            Thread.sleep(10)
        }
        runCurrent()
        return future.get(1, TimeUnit.SECONDS)
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    private fun TestScope.awaitActiveRouteKind(
        viewModel: RuntimeClientViewModel,
        expected: RuntimeActiveRouteKind,
    ): RuntimeUiState {
        val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(4)
        while (System.nanoTime() < deadline) {
            runCurrent()
            val state = viewModel.state.value
            if (state.activeRouteKind == expected) return state
            Thread.sleep(10)
        }
        runCurrent()
        return viewModel.state.value
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    private fun TestScope.awaitRuntimeStatus(
        viewModel: RuntimeClientViewModel,
        expected: String,
    ): RuntimeUiState {
        val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(4)
        while (System.nanoTime() < deadline) {
            runCurrent()
            val state = viewModel.state.value
            if (state.runtimeStatus == expected) return state
            Thread.sleep(10)
        }
        runCurrent()
        return viewModel.state.value
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    private fun TestScope.awaitDocumentCatalog(viewModel: RuntimeClientViewModel): RuntimeUiState {
        val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(4)
        while (System.nanoTime() < deadline) {
            runCurrent()
            val state = viewModel.state.value
            if (!state.isLoadingDocumentCatalog && state.documentCatalog.documents.isNotEmpty()) return state
            Thread.sleep(10)
        }
        runCurrent()
        return viewModel.state.value
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    private fun TestScope.awaitDocumentSearchResult(viewModel: RuntimeClientViewModel): RuntimeUiState {
        val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(4)
        while (System.nanoTime() < deadline) {
            runCurrent()
            val state = viewModel.state.value
            if (!state.isSearchingDocuments && state.documentSearchResults.isNotEmpty()) return state
            Thread.sleep(10)
        }
        runCurrent()
        return viewModel.state.value
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    private fun TestScope.awaitSelectedModel(
        viewModel: RuntimeClientViewModel,
        expectedModelId: String,
    ): RuntimeUiState {
        val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(4)
        while (System.nanoTime() < deadline) {
            runCurrent()
            val state = viewModel.state.value
            if (!state.isLoadingModels && state.selectedModelId == expectedModelId) return state
            Thread.sleep(10)
        }
        runCurrent()
        return viewModel.state.value
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    private fun TestScope.awaitRuntimeError(
        viewModel: RuntimeClientViewModel,
        expected: String,
    ): RuntimeUiState {
        val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(4)
        while (System.nanoTime() < deadline) {
            runCurrent()
            val state = viewModel.state.value
            if (state.error?.code == expected) return state
            Thread.sleep(10)
        }
        runCurrent()
        return viewModel.state.value
    }

    private class FakeRelayRuntimeServer(
        private val json: Json,
        private val relayId: String,
        private val relaySecret: String,
        private val relayNonce: String,
        private val runtimeDeviceId: String,
    ) : Closeable {
        private val codec = ProtocolCodec(json)
        private val runtimeSigningKeyPair = KeyPairGenerator.getInstance("EC")
            .apply { initialize(ECGenParameterSpec("secp256r1")) }
            .generateKeyPair()
        val runtimePublicKey: String = Base64.getEncoder()
            .encodeToString(runtimeSigningKeyPair.public.encoded)
        val runtimeFingerprint: String = MessageDigest.getInstance("SHA-256")
            .digest(runtimeSigningKeyPair.public.encoded)
            .joinToString("") { "%02x".format(it) }
        private val server = ServerSocket(0)
        private val serverError = CompletableFuture<Throwable?>()
        val port: Int = server.localPort
        val handshakeLine: CompletableFuture<String> = CompletableFuture()
        val pairingRequest: CompletableFuture<ProtocolEnvelope> = CompletableFuture()
        private val releaseConnection: CompletableFuture<Unit> = CompletableFuture()
        private val worker = thread(start = true, isDaemon = true) {
            runCatching {
                server.accept().use { socket ->
                    val input = socket.getInputStream()
                    val output = socket.getOutputStream()
                    val handshake = input.readAsciiLine(maxBytes = 512)
                    handshakeLine.complete(handshake)
                    val clientHandshake = clientRelayHandshake(handshake, relayId)
                    val relaySession = completeRelayKeyConfirmation(
                        input = input,
                        output = output,
                        relayId = relayId,
                        relaySecret = relaySecret,
                        routeNonce = relayNonce,
                        clientHandshake = clientHandshake,
                    )

                    val cryptor = TestRelayFrameBodyCryptor(
                        bindingId = relaySession.bindingId,
                        clientTrafficSecret = relaySession.clientTrafficSecret,
                        runtimeTrafficSecret = relaySession.runtimeTrafficSecret,
                    )
                    val encryptedBody = codec.readFrameBody(input)
                    val envelope = codec.decode(cryptor.decryptClientFrameBody(encryptedBody))
                    pairingRequest.complete(envelope)

                    val requestPayload = json.decodeFromJsonElement(
                        PairingRequestPayload.serializer(),
                        envelope.payload,
                    )
                    require(requestPayload.transportBinding == relaySession.bindingId)
                    require(requestPayload.pairingProofScheme == INITIAL_PAIRING_PROOF_SCHEME)
                    val clientPublicKeyBytes = Base64.getDecoder().decode(requestPayload.publicKey)
                    val clientFingerprint = MessageDigest.getInstance("SHA-256")
                        .digest(clientPublicKeyBytes)
                        .joinToString("") { "%02x".format(it) }
                    val clientRequest = InitialPairingClientRequest(
                        scheme = requestPayload.pairingProofScheme,
                        protocolVersion = 1,
                        requestId = envelope.requestId,
                        pairingNonce = requestPayload.pairingNonce,
                        pairingCode = requestPayload.pairingCode,
                        runtimeDeviceId = runtimeDeviceId,
                        runtimePublicKey = runtimePublicKey,
                        runtimeKeyFingerprint = runtimeFingerprint,
                        clientDeviceId = requestPayload.deviceId,
                        clientDeviceName = requestPayload.deviceName,
                        clientPublicKey = requestPayload.publicKey,
                        clientKeyFingerprint = clientFingerprint,
                        transportBinding = requestPayload.transportBinding,
                    )
                    val clientPublicKey = KeyFactory.getInstance("EC")
                        .generatePublic(java.security.spec.X509EncodedKeySpec(clientPublicKeyBytes))
                    require(Signature.getInstance("SHA256withECDSA").run {
                        initVerify(clientPublicKey)
                        update(clientRequest.transcript())
                        verify(Base64.getDecoder().decode(requestPayload.pairingSignature))
                    })
                    val message = "trusted"
                    val pairingResult = InitialPairingAcceptedResult(
                        scheme = INITIAL_PAIRING_PROOF_SCHEME,
                        protocolVersion = 1,
                        requestId = envelope.requestId,
                        pairingRequestDigest = clientRequest.digest(),
                        accepted = true,
                        runtimeDeviceId = runtimeDeviceId,
                        runtimePublicKey = runtimePublicKey,
                        runtimeKeyFingerprint = runtimeFingerprint,
                        trustedDeviceId = requestPayload.deviceId,
                        message = message,
                        transportBinding = relaySession.bindingId,
                    )
                    val resultSignature = Signature.getInstance("SHA256withECDSA").run {
                        initSign(runtimeSigningKeyPair.private)
                        update(pairingResult.transcript())
                        Base64.getEncoder().encodeToString(sign())
                    }

                    val response = ProtocolEnvelope(
                        type = MessageType.PairingResult,
                        requestId = envelope.requestId,
                        payload = json.encodeToJsonElement(
                            PairingResultPayload.serializer(),
                            PairingResultPayload(
                                accepted = true,
                                runtimeDeviceIdV2 = runtimeDeviceId,
                                runtimePublicKey = runtimePublicKey,
                                runtimeKeyFingerprint = runtimeFingerprint,
                                trustedDeviceId = requestPayload.deviceId,
                                message = message,
                                pairingProofScheme = INITIAL_PAIRING_PROOF_SCHEME,
                                pairingRequestDigest = clientRequest.digest(),
                                runtimePairingSignature = resultSignature,
                                transportBinding = relaySession.bindingId,
                            ),
                        ).jsonObject,
                    )
                    output.write(codec.encodeFrameBody(cryptor.encryptRuntimeFrameBody(codec.encodeBody(response))))
                    output.flush()
                    releaseConnection.get(4, TimeUnit.SECONDS)
                }
                serverError.complete(null)
            }.onFailure { error ->
                handshakeLine.completeExceptionally(error)
                pairingRequest.completeExceptionally(error)
                serverError.complete(error)
            }
        }

        fun closedWithoutServerError(): Throwable? {
            releaseConnection.complete(Unit)
            val error = serverError.get(2, TimeUnit.SECONDS)
            worker.join(1_000)
            return error
        }

        override fun close() {
            releaseConnection.complete(Unit)
            runCatching { server.close() }
            worker.join(1_000)
        }
    }

    private class FakeInvalidRuntimeProofRelayServer(
        private val json: Json,
        private val relayId: String,
        private val relaySecret: String,
        private val relayNonce: String,
        private val runtimeIdentity: RuntimeIdentityMaterial,
        private val challengeFingerprint: String = runtimeIdentity.fingerprint,
        private val signatureNonce: String = "replayed-auth-nonce",
    ) : Closeable {
        private val codec = ProtocolCodec(json)
        private val server = ServerSocket(0)
        private val serverError = CompletableFuture<Throwable?>()
        val port: Int = server.localPort
        val handshakeLine: CompletableFuture<String> = CompletableFuture()
        val helloRequest: CompletableFuture<ProtocolEnvelope> = CompletableFuture()
        val postChallengeRequest: CompletableFuture<ProtocolEnvelope?> = CompletableFuture()
        private val releaseConnection: CompletableFuture<Unit> = CompletableFuture()
        private val worker = thread(start = true, isDaemon = true) {
            runCatching {
                server.soTimeout = 4_000
                var acceptedSocket: Socket? = null
                var acceptedHandshake: String? = null
                repeat(2) {
                    if (acceptedSocket != null) return@repeat
                    val candidate = server.accept()
                    candidate.soTimeout = 4_000
                    val candidateHandshake = candidate.getInputStream().readAsciiLineOrNull()
                    if (candidateHandshake == null) {
                        candidate.close()
                    } else {
                        acceptedSocket = candidate
                        acceptedHandshake = candidateHandshake
                    }
                }
                requireNotNull(acceptedSocket).use { socket ->
                    socket.soTimeout = 4_000
                    val input = socket.getInputStream()
                    val output = socket.getOutputStream()
                    val handshake = requireNotNull(acceptedHandshake)
                    handshakeLine.complete(handshake)
                    val clientHandshake = clientRelayHandshake(handshake, relayId)
                    val relaySession = completeRelayKeyConfirmation(
                        input = input,
                        output = output,
                        relayId = relayId,
                        relaySecret = relaySecret,
                        routeNonce = relayNonce,
                        clientHandshake = clientHandshake,
                    )
                    val transportBinding = relaySession.bindingId
                    val cryptor = TestRelayFrameBodyCryptor(
                        bindingId = relaySession.bindingId,
                        clientTrafficSecret = relaySession.clientTrafficSecret,
                        runtimeTrafficSecret = relaySession.runtimeTrafficSecret,
                    )
                    val hello = readEncryptedEnvelope(input, cryptor)
                    helloRequest.complete(hello)
                    val helloPayload = json.decodeFromJsonElement(
                        HelloPayload.serializer(),
                        hello.payload,
                    )
                    require(helloPayload.transportBinding == transportBinding) {
                        "Relay hello transport binding did not match"
                    }
                    val challengeNonce = "trusted-auth-nonce"
                    writeEncryptedEnvelope(
                        output = output,
                        cryptor = cryptor,
                        envelope = ProtocolEnvelope(
                            type = MessageType.AuthChallenge,
                            requestId = hello.requestId,
                            payload = json.encodeToJsonElement(
                                AuthChallengePayload.serializer(),
                                AuthChallengePayload(
                                    deviceId = helloPayload.deviceId,
                                    nonce = challengeNonce,
                                    runtimeKeyFingerprint = challengeFingerprint,
                                    runtimeSignature = runtimeIdentity.signChallenge(
                                        deviceId = helloPayload.deviceId,
                                        nonce = signatureNonce,
                                        transportBinding = transportBinding,
                                    ),
                                    transportBinding = transportBinding,
                                ),
                            ).jsonObject,
                        ),
                    )

                    socket.soTimeout = 750
                    val nextRequest = try {
                        readEncryptedEnvelope(input, cryptor)
                    } catch (_: SocketTimeoutException) {
                        null
                    }
                    postChallengeRequest.complete(nextRequest)
                    releaseConnection.get(4, TimeUnit.SECONDS)
                }
                serverError.complete(null)
            }.onFailure { error ->
                handshakeLine.completeExceptionally(error)
                helloRequest.completeExceptionally(error)
                postChallengeRequest.completeExceptionally(error)
                serverError.complete(error)
            }
        }

        private fun readEncryptedEnvelope(
            input: InputStream,
            cryptor: TestRelayFrameBodyCryptor,
        ): ProtocolEnvelope {
            val encryptedBody = codec.readFrameBody(input)
            return codec.decode(cryptor.decryptClientFrameBody(encryptedBody))
        }

        private fun writeEncryptedEnvelope(
            output: java.io.OutputStream,
            cryptor: TestRelayFrameBodyCryptor,
            envelope: ProtocolEnvelope,
        ) {
            output.write(codec.encodeFrameBody(cryptor.encryptRuntimeFrameBody(codec.encodeBody(envelope))))
            output.flush()
        }

        fun closedWithoutServerError(): Throwable? {
            releaseConnection.complete(Unit)
            val error = serverError.get(2, TimeUnit.SECONDS)
            worker.join(1_000)
            return error
        }

        override fun close() {
            releaseConnection.complete(Unit)
            runCatching { server.close() }
            worker.join(1_000)
        }
    }

    private class FakeAuthenticatedRelayRuntimeServer(
        private val json: Json,
        private val relayId: String,
        private val relaySecret: String,
        private val relayNonce: String,
        private val refreshedRelayNonce: String,
        private val refreshedRelayExpiresAtEpochMillis: Long,
        private val runtimeIdentity: RuntimeIdentityMaterial,
        private val routeToken: String,
        private val currentRelayExpiresAtEpochMillis: Long,
        private val currentTicketGeneration: Long,
        private val clientPublicKeyBase64: String,
    ) : Closeable {
        private val codec = ProtocolCodec(json)
        private val server = ServerSocket(0)
        private val serverError = CompletableFuture<Throwable?>()
        val port: Int = server.localPort
        val handshakeLine: CompletableFuture<String> = CompletableFuture()
        val helloRequest: CompletableFuture<ProtocolEnvelope> = CompletableFuture()
        val authResponseRequest: CompletableFuture<ProtocolEnvelope> = CompletableFuture()
        val routeRefreshRequest: CompletableFuture<ProtocolEnvelope> = CompletableFuture()
        val allocationAuthorizationRequest: CompletableFuture<ProtocolEnvelope> = CompletableFuture()
        val healthRequest: CompletableFuture<ProtocolEnvelope> = CompletableFuture()
        val modelsListRequest: CompletableFuture<ProtocolEnvelope> = CompletableFuture()
        val indexDocumentsListRequest: CompletableFuture<ProtocolEnvelope> = CompletableFuture()
        val retrievalQueryRequest: CompletableFuture<ProtocolEnvelope> = CompletableFuture()
        val chatSendRequest: CompletableFuture<ProtocolEnvelope> = CompletableFuture()
        private val releaseConnection: CompletableFuture<Unit> = CompletableFuture()
        private val worker = thread(start = true, isDaemon = true) {
            runCatching {
                server.accept().use { socket ->
                    val input = socket.getInputStream()
                    val output = socket.getOutputStream()
                    val handshake = input.readAsciiLine(maxBytes = 512)
                    handshakeLine.complete(handshake)
                    val clientHandshake = clientRelayHandshake(handshake, relayId)
                    val clientFingerprint = MessageDigest.getInstance("SHA-256")
                        .digest(Base64.getDecoder().decode(clientPublicKeyBase64))
                        .joinToString("") { "%02x".format(it) }
                    val registrationChallenge = PairedClientRelayRegistrationChallenge(
                        relayId = relayId,
                        relayExpiresAtEpochMillis = currentRelayExpiresAtEpochMillis,
                        relayNonce = relayNonce,
                        runtimeKeyFingerprint = runtimeIdentity.fingerprint,
                        clientKeyFingerprint = clientFingerprint,
                        ticketGeneration = currentTicketGeneration,
                        sessionNonce = clientHandshake.sessionNonce,
                        ephemeralKey = clientHandshake.ephemeralKey,
                        challenge = "d".repeat(64),
                        challengeExpiresAtEpochMillis = 4_102_444_800_000L,
                    )
                    output.write(
                        (
                            PAIRED_CLIENT_RELAY_REGISTRATION_CHALLENGE_PREFIX +
                                json.encodeToString(
                                    PairedClientRelayRegistrationChallenge.serializer(),
                                    registrationChallenge,
                                ) +
                                "\n"
                            ).toByteArray(Charsets.UTF_8),
                    )
                    output.flush()
                    val registrationProof = input.readAsciiLine(maxBytes = 4_096)
                    val proofParts = registrationProof.split(' ')
                    require(proofParts.size == 6)
                    require(proofParts[0] == "AETHERLINK_RELAY")
                    require(proofParts[1] == "client_registration_proof")
                    require(proofParts[2] == "crypto=2")
                    require(proofParts[3] == "challenge=${registrationChallenge.challenge}")
                    val proofPublicKey = proofParts[4].removePrefix("client_public_key=")
                    val proofSignature = proofParts[5].removePrefix("client_signature=")
                    require(proofPublicKey == clientPublicKeyBase64)
                    val signingKey = KeyFactory.getInstance("EC").generatePublic(
                        X509EncodedKeySpec(Base64.getDecoder().decode(proofPublicKey))
                    )
                    require(Signature.getInstance("SHA256withECDSA").run {
                        initVerify(signingKey)
                        update(registrationChallenge.transcript())
                        verify(Base64.getDecoder().decode(proofSignature))
                    })
                    val relaySession = completeRelayKeyConfirmation(
                        input = input,
                        output = output,
                        relayId = relayId,
                        relaySecret = relaySecret,
                        routeNonce = relayNonce,
                        clientHandshake = clientHandshake,
                    )
                    val transportBinding = relaySession.bindingId
                    val cryptor = TestRelayFrameBodyCryptor(
                        bindingId = relaySession.bindingId,
                        clientTrafficSecret = relaySession.clientTrafficSecret,
                        runtimeTrafficSecret = relaySession.runtimeTrafficSecret,
                    )
                    val hello = readEncryptedEnvelope(input, cryptor)
                    helloRequest.complete(hello)
                    val helloPayload = json.decodeFromJsonElement(
                        HelloPayload.serializer(),
                        hello.payload,
                    )
                    require(helloPayload.transportBinding == transportBinding) {
                        "Relay hello transport binding did not match"
                    }
                    val challengeNonce = "trusted-auth-nonce"
                    writeEncryptedEnvelope(
                        output = output,
                        cryptor = cryptor,
                        envelope = ProtocolEnvelope(
                            type = MessageType.AuthChallenge,
                            requestId = hello.requestId,
                            payload = json.encodeToJsonElement(
                                AuthChallengePayload.serializer(),
                                AuthChallengePayload(
                                    deviceId = helloPayload.deviceId,
                                    nonce = challengeNonce,
                                    runtimeKeyFingerprint = runtimeIdentity.fingerprint,
                                    runtimeSignature = runtimeIdentity.signChallenge(
                                        deviceId = helloPayload.deviceId,
                                        nonce = challengeNonce,
                                        transportBinding = transportBinding,
                                    ),
                                    transportBinding = transportBinding,
                                ),
                            ).jsonObject,
                        ),
                    )

                    val authResponse = readEncryptedEnvelope(input, cryptor)
                    authResponseRequest.complete(authResponse)
                    val authResponsePayload = json.decodeFromJsonElement(
                        AuthResponsePayload.serializer(),
                        authResponse.payload,
                    )
                    require(authResponsePayload.transportBinding == transportBinding) {
                        "Relay auth response transport binding did not match"
                    }
                    writeEncryptedEnvelope(
                        output = output,
                        cryptor = cryptor,
                        envelope = ProtocolEnvelope(
                            type = MessageType.AuthResponse,
                            requestId = authResponse.requestId,
                            payload = json.encodeToJsonElement(
                                AuthResponsePayload.serializer(),
                                AuthResponsePayload(
                                    accepted = true,
                                    transportBinding = transportBinding,
                                ),
                            ).jsonObject,
                        ),
                    )

                    var pendingAllocationChallenge: RelayAllocationChallengePayload? = null
                    while (
                        !healthRequest.isDone ||
                        !routeRefreshRequest.isDone ||
                        !allocationAuthorizationRequest.isDone ||
                        !modelsListRequest.isDone ||
                        !indexDocumentsListRequest.isDone ||
                        !retrievalQueryRequest.isDone ||
                        !chatSendRequest.isDone
                    ) {
                        val request = readEncryptedEnvelope(input, cryptor)
                        when (request.type) {
                            MessageType.RouteRefresh -> {
                                routeRefreshRequest.complete(request)
                                val clientFingerprint = MessageDigest.getInstance("SHA-256")
                                    .digest(Base64.getDecoder().decode(clientPublicKeyBase64))
                                    .joinToString("") { "%02x".format(it) }
                                val challenge = RelayAllocationChallengePayload(
                                    proofScheme = "runtime-client-p256-v2",
                                    protocolVersion = 2,
                                    operation = "renew",
                                    authorizationId = "encrypted-allocation-authorization",
                                    currentRelayId = relayId,
                                    nextRelayId = relayId,
                                    routeTokenHash = MessageDigest.getInstance("SHA-256")
                                        .digest(routeToken.toByteArray(Charsets.UTF_8))
                                        .joinToString("") { "%02x".format(it) },
                                    runtimeKeyFingerprint = runtimeIdentity.fingerprint,
                                    clientKeyFingerprint = clientFingerprint,
                                    currentTicketGeneration = currentTicketGeneration,
                                    nextTicketGeneration = currentTicketGeneration + 1L,
                                    currentRelayExpiresAtEpochMillis = currentRelayExpiresAtEpochMillis,
                                    currentRelayNonce = relayNonce,
                                    nextRelayExpiresAtEpochMillis = refreshedRelayExpiresAtEpochMillis,
                                    nextRelayNonce = refreshedRelayNonce,
                                    challenge = "c".repeat(64),
                                    challengeExpiresAtEpochMillis = currentRelayExpiresAtEpochMillis,
                                    transportBinding = transportBinding,
                                )
                                pendingAllocationChallenge = challenge
                                writeEncryptedEnvelope(
                                    output = output,
                                    cryptor = cryptor,
                                    envelope = ProtocolEnvelope(
                                        type = MessageType.RelayAllocationChallenge,
                                        requestId = request.requestId,
                                        payload = json.encodeToJsonElement(
                                            RelayAllocationChallengePayload.serializer(),
                                            challenge,
                                        ).jsonObject,
                                    ),
                                )
                            }
                            MessageType.RelayAllocationAuthorization -> {
                                val challenge = requireNotNull(pendingAllocationChallenge)
                                val payload = json.decodeFromJsonElement(
                                    RelayAllocationAuthorizationPayload.serializer(),
                                    request.payload,
                                )
                                val authorization = PairedRelayAllocationAuthorization(
                                    operation = challenge.operation,
                                    requestId = request.requestId,
                                    authorizationId = challenge.authorizationId,
                                    currentRelayId = challenge.currentRelayId,
                                    nextRelayId = challenge.nextRelayId,
                                    routeTokenHash = challenge.routeTokenHash,
                                    runtimeKeyFingerprint = challenge.runtimeKeyFingerprint,
                                    clientKeyFingerprint = challenge.clientKeyFingerprint,
                                    currentTicketGeneration = challenge.currentTicketGeneration,
                                    nextTicketGeneration = challenge.nextTicketGeneration,
                                    currentRelayExpiresAtEpochMillis = challenge.currentRelayExpiresAtEpochMillis,
                                    currentRelayNonce = challenge.currentRelayNonce,
                                    nextRelayExpiresAtEpochMillis = challenge.nextRelayExpiresAtEpochMillis,
                                    nextRelayNonce = challenge.nextRelayNonce,
                                    challenge = challenge.challenge,
                                    challengeExpiresAtEpochMillis = challenge.challengeExpiresAtEpochMillis,
                                    transportBinding = challenge.transportBinding,
                                )
                                require(request.requestId == routeRefreshRequest.get().requestId)
                                require(payload.authorizationId == challenge.authorizationId)
                                require(payload.challenge == challenge.challenge)
                                require(payload.clientKeyFingerprint == challenge.clientKeyFingerprint)
                                require(payload.transportBinding == transportBinding)
                                require(
                                    PairedRelayAllocationAuthorizationProof.verifyClient(
                                        authorization = authorization,
                                        clientPublicKeyBase64 = clientPublicKeyBase64,
                                        signatureBase64 = payload.clientSignature,
                                    )
                                )
                                allocationAuthorizationRequest.complete(request)
                                pendingAllocationChallenge = null
                                writeEncryptedEnvelope(
                                    output = output,
                                    cryptor = cryptor,
                                    envelope = ProtocolEnvelope(
                                        type = MessageType.RouteRefresh,
                                        requestId = request.requestId,
                                        payload = json.encodeToJsonElement(
                                            RouteRefreshPayload.serializer(),
                                            RouteRefreshPayload(
                                                runtimeDeviceId = "runtime-trusted-overlay",
                                                runtimeKeyFingerprint = runtimeIdentity.fingerprint,
                                                relayHost = "100.64.2.20",
                                                relayPort = 443,
                                                relayId = relayId,
                                                relaySecret = relaySecret,
                                                relayExpiresAtEpochMillis = refreshedRelayExpiresAtEpochMillis,
                                                relayNonce = refreshedRelayNonce,
                                                relayScope = "private_overlay",
                                                ticketGeneration = currentTicketGeneration + 1L,
                                            ),
                                        ).jsonObject,
                                    ),
                                )
                            }
                            MessageType.RuntimeHealth -> {
                                healthRequest.complete(request)
                                writeEncryptedEnvelope(
                                    output = output,
                                    cryptor = cryptor,
                                    envelope = ProtocolEnvelope(
                                        type = MessageType.RuntimeHealth,
                                        requestId = request.requestId,
                                        payload = json.encodeToJsonElement(
                                            RuntimeHealthPayload.serializer(),
                                            RuntimeHealthPayload(status = "ok"),
                                        ).jsonObject,
                                    ),
                                )
                            }
                            MessageType.ModelsList -> {
                                modelsListRequest.complete(request)
                                writeEncryptedEnvelope(
                                    output = output,
                                    cryptor = cryptor,
                                    envelope = ProtocolEnvelope(
                                        type = MessageType.ModelsResult,
                                        requestId = request.requestId,
                                        payload = json.encodeToJsonElement(
                                            ModelsResultPayload.serializer(),
                                            ModelsResultPayload(
                                                models = listOf(
                                                    ModelInfoPayload(
                                                        id = "relay-chat",
                                                        name = "Relay Chat",
                                                        provider = "ollama",
                                                        providerModelId = "relay-chat",
                                                        qualifiedId = "ollama:relay-chat",
                                                        modelKind = "chat",
                                                        capabilities = listOf("chat"),
                                                        installed = true,
                                                        running = true,
                                                        source = "local",
                                                    ),
                                                ),
                                            ),
                                        ).jsonObject,
                                    ),
                                )
                            }
                            MessageType.IndexDocumentsList -> {
                                indexDocumentsListRequest.complete(request)
                                writeEncryptedEnvelope(
                                    output = output,
                                    cryptor = cryptor,
                                    envelope = ProtocolEnvelope(
                                        type = MessageType.IndexDocumentsList,
                                        requestId = request.requestId,
                                        payload = json.encodeToJsonElement(
                                            IndexDocumentsListResultPayload.serializer(),
                                            IndexDocumentsListResultPayload(
                                                documents = listOf(relayDocumentPayload()),
                                                summary = IndexDocumentsSummaryPayload(
                                                    documentCount = 2,
                                                    chunkCount = 3,
                                                    extractedCharacterCount = 256,
                                                    qualityCounts = IndexDocumentsQualityCountsPayload(
                                                        noUsableText = 0,
                                                        singleChunk = 1,
                                                        chunked = 1,
                                                    ),
                                                ),
                                            ),
                                        ).jsonObject,
                                    ),
                                )
                            }
                            MessageType.RetrievalQuery -> {
                                retrievalQueryRequest.complete(request)
                                writeEncryptedEnvelope(
                                    output = output,
                                    cryptor = cryptor,
                                    envelope = ProtocolEnvelope(
                                        type = MessageType.RetrievalQuery,
                                        requestId = request.requestId,
                                        payload = json.encodeToJsonElement(
                                            RetrievalQueryResultPayload.serializer(),
                                            RetrievalQueryResultPayload(
                                                results = listOf(
                                                    RetrievalQueryResultItemPayload(
                                                        document = relayDocumentPayload(),
                                                        chunkIndex = 0,
                                                        startCharacterOffset = 0,
                                                        endCharacterOffset = 72,
                                                        rank = 3,
                                                        matchedTerms = listOf("relay", "document"),
                                                        snippet = "Relay document search stays inside the authenticated runtime channel.",
                                                        sourceAnchorId = "source_anchor_0011223344556677",
                                                    ),
                                                ),
                                            ),
                                        ).jsonObject,
                                    ),
                                )
                            }
                            MessageType.ChatSend -> {
                                chatSendRequest.complete(request)
                            }
                        }
                    }
                    releaseConnection.get(4, TimeUnit.SECONDS)
                }
                serverError.complete(null)
            }.onFailure { error ->
                handshakeLine.completeExceptionally(error)
                helloRequest.completeExceptionally(error)
                authResponseRequest.completeExceptionally(error)
                routeRefreshRequest.completeExceptionally(error)
                allocationAuthorizationRequest.completeExceptionally(error)
                healthRequest.completeExceptionally(error)
                modelsListRequest.completeExceptionally(error)
                indexDocumentsListRequest.completeExceptionally(error)
                retrievalQueryRequest.completeExceptionally(error)
                chatSendRequest.completeExceptionally(error)
                serverError.complete(error)
            }
        }

        private fun relayDocumentPayload(): RuntimeDocumentIndexDocumentPayload =
            RuntimeDocumentIndexDocumentPayload(
                id = "relay-doc",
                displayName = "relay-runtime-guide.md",
                mimeType = "text/markdown",
                contentFingerprint = "0123456789abcdef",
                extractedCharacterCount = 128,
                chunkCount = 2,
                quality = "chunked",
            )

        private fun readEncryptedEnvelope(
            input: InputStream,
            cryptor: TestRelayFrameBodyCryptor,
        ): ProtocolEnvelope {
            val encryptedBody = codec.readFrameBody(input)
            return codec.decode(cryptor.decryptClientFrameBody(encryptedBody))
        }

        private fun writeEncryptedEnvelope(
            output: java.io.OutputStream,
            cryptor: TestRelayFrameBodyCryptor,
            envelope: ProtocolEnvelope,
        ) {
            output.write(codec.encodeFrameBody(cryptor.encryptRuntimeFrameBody(codec.encodeBody(envelope))))
            output.flush()
        }

        fun closedWithoutServerError(): Throwable? {
            releaseConnection.complete(Unit)
            val error = serverError.get(2, TimeUnit.SECONDS)
            worker.join(1_000)
            return error
        }

        override fun close() {
            releaseConnection.complete(Unit)
            runCatching { server.close() }
            worker.join(1_000)
        }
    }

    private class TestRelayFrameBodyCryptor(
        bindingId: String,
        private val clientTrafficSecret: ByteArray,
        private val runtimeTrafficSecret: ByteArray,
    ) {
        private val bindingDigest = bindingId.toHexBytes()
        private var clientCounter = 0L
        private var runtimeCounter = 0L

        fun decryptClientFrameBody(ciphertext: ByteArray): ByteArray {
            val plaintext = crypt(
                mode = Cipher.DECRYPT_MODE,
                direction = CLIENT_DIRECTION,
                frameIndex = clientCounter,
                trafficSecret = clientTrafficSecret,
                input = ciphertext,
            )
            clientCounter += 1
            return plaintext
        }

        fun encryptRuntimeFrameBody(plaintext: ByteArray): ByteArray {
            val ciphertext = crypt(
                mode = Cipher.ENCRYPT_MODE,
                direction = RUNTIME_DIRECTION,
                frameIndex = runtimeCounter,
                trafficSecret = runtimeTrafficSecret,
                input = plaintext,
            )
            runtimeCounter += 1
            return ciphertext
        }

        private fun crypt(
            mode: Int,
            direction: ByteArray,
            frameIndex: Long,
            trafficSecret: ByteArray,
            input: ByteArray,
        ): ByteArray {
            require(frameIndex in 0 until Long.MAX_VALUE)
            val epoch = frameIndex ushr 16
            val sequence = frameIndex and 0xffffL
            val epochBytes = ByteBuffer.allocate(Long.SIZE_BYTES).putLong(epoch).array()
            val sequenceBytes = ByteBuffer.allocate(Long.SIZE_BYTES).putLong(sequence).array()
            val epochKey = Mac.getInstance("HmacSHA256").run {
                init(SecretKeySpec(trafficSecret, "HmacSHA256"))
                doFinal(FRAME_EPOCH_PREFIX + direction + epochBytes)
            }
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(
                mode,
                SecretKeySpec(epochKey, "AES"),
                GCMParameterSpec(GCM_TAG_BITS, direction + sequenceBytes),
            )
            cipher.updateAAD(AAD_PREFIX + bindingDigest + direction + epochBytes + sequenceBytes)
            return cipher.doFinal(input)
        }

        private companion object {
            private val FRAME_EPOCH_PREFIX =
                "AetherLink relay frame epoch v2\n".toByteArray(Charsets.UTF_8)
            private val AAD_PREFIX = "AETHERLINK_RELAY_FRAME_V2".toByteArray(Charsets.UTF_8)
            private val CLIENT_DIRECTION = "CLNT".toByteArray(Charsets.US_ASCII)
            private val RUNTIME_DIRECTION = "RUNT".toByteArray(Charsets.US_ASCII)
            private const val GCM_TAG_BITS = 128
        }
    }

    private class FakeTrustedRuntimeStore(
        initialRuntime: TrustedRuntime? = null,
    ) : RuntimeTrustedRuntimeStore {
        private val trustedRuntimeFlow = MutableStateFlow(initialRuntime)
        override val trustedRuntime: Flow<TrustedRuntime?> = trustedRuntimeFlow
        val trustedRuntimeWritten: CompletableFuture<TrustedRuntime> = CompletableFuture()
        val trusted: TrustedRuntime?
            get() = trustedRuntimeFlow.value

        override suspend fun trustRuntime(runtime: TrustedRuntime) {
            trustedRuntimeFlow.value = runtime
            trustedRuntimeWritten.complete(runtime)
        }

        override suspend fun forgetRuntime() {
            trustedRuntimeFlow.value = null
        }
    }

    private class FakeDeviceIdentityProvider(
        private val identity: DeviceIdentity,
    ) : RuntimeDeviceIdentityProvider {
        override suspend fun loadOrCreate(): DeviceIdentity = identity
    }

    private class FakeRuntimeLocalDataStore(
        initialData: PersistedRuntimeData = PersistedRuntimeData(),
    ) : RuntimeLocalDataStore {
        var data: PersistedRuntimeData = initialData
            private set

        override fun load(): PersistedRuntimeData = data

        override fun save(data: PersistedRuntimeData) {
            this.data = data
        }
    }

    private object EmptyRuntimeDiscoverySource : RuntimeDiscoverySource {
        override fun discover(): Flow<List<DiscoveredRuntime>> = emptyFlow()
    }

    private object NoopRuntimeLifecycleCallbacksRegistrar : RuntimeLifecycleCallbacksRegistrar {
        override fun register(application: Application, callbacks: Application.ActivityLifecycleCallbacks) = Unit
        override fun unregister(application: Application, callbacks: Application.ActivityLifecycleCallbacks) = Unit
    }

    private fun testDeviceIdentity(): DeviceIdentity {
        return DeviceIdentity(
            deviceId = "client-real",
            deviceName = "AetherLink Test Client",
            publicKeyBase64 = Base64.getEncoder().encodeToString(testClientKeyPair.public.encoded),
            keyPair = testClientKeyPair,
        )
    }

    private data class RuntimeIdentityMaterial(
        val publicKeyBase64: String,
        val fingerprint: String,
        private val privateKey: java.security.PrivateKey,
    ) {
        fun signChallenge(
            deviceId: String,
            nonce: String,
            transportBinding: String? = null,
        ): String {
            val message = RuntimeIdentityProofVerifier.authenticationChallengeMessage(
                deviceId = deviceId,
                nonce = nonce,
                transportBinding = transportBinding,
            )
            return Signature.getInstance("SHA256withECDSA").run {
                initSign(privateKey)
                update(message)
                Base64.getEncoder().encodeToString(sign())
            }
        }
    }

    private fun testRuntimeIdentityMaterial(): RuntimeIdentityMaterial {
        val keyPair = KeyPairGenerator.getInstance("EC")
            .apply { initialize(ECGenParameterSpec("secp256r1")) }
            .generateKeyPair()
        val publicKeyBytes = keyPair.public.encoded
        return RuntimeIdentityMaterial(
            publicKeyBase64 = Base64.getEncoder().encodeToString(publicKeyBytes),
            fingerprint = MessageDigest.getInstance("SHA-256")
                .digest(publicKeyBytes)
                .joinToString("") { "%02x".format(it) },
            privateKey = keyPair.private,
        )
    }

    private fun RuntimeClientViewModel.stopForTest() {
        runCatching {
            val field = RuntimeClientViewModel::class.java.getDeclaredField("activeChannel")
            field.isAccessible = true
            (field.get(this) as? Closeable)?.close()
        }
        viewModelScope.cancel()
    }
}

private fun InputStream.readAsciiLine(maxBytes: Int = 256): String {
    val buffer = StringBuilder()
    while (buffer.length < maxBytes) {
        val next = read()
        if (next == -1) break
        if (next == '\n'.code) return buffer.toString().trimEnd('\r')
        buffer.append(next.toChar())
    }
    error("ASCII line was not complete")
}

private fun InputStream.readAsciiLineOrNull(maxBytes: Int = 512): String? {
    val buffer = StringBuilder()
    while (buffer.length < maxBytes) {
        val next = read()
        if (next == -1) return null
        if (next == '\n'.code) return buffer.toString().trimEnd('\r')
        buffer.append(next.toChar())
    }
    error("ASCII line exceeded $maxBytes bytes")
}
