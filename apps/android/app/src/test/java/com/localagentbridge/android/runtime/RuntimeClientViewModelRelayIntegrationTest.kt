package com.localagentbridge.android.runtime

import android.app.Application
import androidx.lifecycle.viewModelScope
import com.localagentbridge.android.core.pairing.DeviceIdentity
import com.localagentbridge.android.core.pairing.RuntimeIdentityProofVerifier
import com.localagentbridge.android.core.pairing.TrustedRuntime
import com.localagentbridge.android.core.protocol.AuthChallengePayload
import com.localagentbridge.android.core.protocol.AuthResponsePayload
import com.localagentbridge.android.core.protocol.HelloPayload
import com.localagentbridge.android.core.protocol.MessageType
import com.localagentbridge.android.core.protocol.PairingRequestPayload
import com.localagentbridge.android.core.protocol.PairingResultPayload
import com.localagentbridge.android.core.protocol.ProtocolCodec
import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import com.localagentbridge.android.core.protocol.RouteRefreshPayload
import com.localagentbridge.android.core.protocol.RuntimeHealthPayload
import com.localagentbridge.android.core.transport.DiscoveredRuntime
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
import java.nio.ByteBuffer
import java.security.KeyPairGenerator
import java.security.MessageDigest
import java.security.Signature
import java.security.spec.ECGenParameterSpec
import java.util.Base64
import java.util.concurrent.CompletableFuture
import java.util.concurrent.TimeUnit
import javax.crypto.Cipher
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec
import kotlin.concurrent.thread

class RuntimeClientViewModelRelayIntegrationTest {
    private val json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
        encodeDefaults = true
    }

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
            runtimePublicKey = "runtime-public-key",
            runtimeFingerprint = "runtime-fingerprint",
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
                        currentTimeMillis = { 1_000L },
                    ),
                )
                val rawUri = "aetherlink://pair?v=1&n=nonce-real&c=246810" +
                    "&rid=runtime-real&rn=AetherLink%20Runtime&rf=runtime-fingerprint" +
                    "&rk=runtime-public-key&rt=route-real" +
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
                assertEquals("client-public-key-real", pairingPayload.publicKey)
                assertTrue(relay.handshakeLine.get(1, TimeUnit.SECONDS).endsWith(" $relayId"))
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
            runtimePublicKey = "runtime-overlay-public-key",
            runtimeFingerprint = "runtime-overlay-fingerprint",
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
                    "&rid=runtime-overlay&rn=AetherLink%20Runtime&rf=runtime-overlay-fingerprint" +
                    "&rk=runtime-overlay-public-key&rt=route-overlay" +
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
                assertTrue(relay.handshakeLine.get(1, TimeUnit.SECONDS).endsWith(" $relayId"))
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
        val relayId = "trusted-overlay-relay-id"
        val runtimeIdentity = testRuntimeIdentityMaterial()
        FakeAuthenticatedRelayRuntimeServer(
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
                        deviceId = "runtime-trusted-overlay",
                        name = "AetherLink Runtime",
                        fingerprint = runtimeIdentity.fingerprint,
                        publicKeyBase64 = runtimeIdentity.publicKeyBase64,
                        routeToken = "route-trusted-overlay",
                        host = null,
                        port = null,
                        relayHost = "100.64.2.20",
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
                        relayConnector = RuntimeRelayTcpClient(socketFactory = socketFactory),
                        discovery = EmptyRuntimeDiscoverySource,
                        trustedRuntimeStore = trustedRuntimeStore,
                        deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                        localDataStore = localStore,
                        lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                        currentTimeMillis = { 1_000L },
                    ),
                )

                val helloEnvelope = awaitFuture(relay.helloRequest)
                val helloPayload = json.decodeFromJsonElement(
                    HelloPayload.serializer(),
                    helloEnvelope.payload,
                )
                println(
                    "DEBUG trusted relay auth state=" +
                        "${viewModel.state.value.runtimeStatus} error=${viewModel.state.value.error}"
                )
                val authResponseEnvelope = awaitFuture(relay.authResponseRequest)
                val authResponsePayload = json.decodeFromJsonElement(
                    AuthResponsePayload.serializer(),
                    authResponseEnvelope.payload,
                )
                val routeRefreshEnvelope = awaitFuture(relay.routeRefreshRequest)
                val healthEnvelope = awaitFuture(relay.healthRequest)
                val connectedState = awaitActiveRouteKind(viewModel, RuntimeActiveRouteKind.Relay)

                assertEquals(0, directConnectionAttempts)
                assertTrue(relay.handshakeLine.get(1, TimeUnit.SECONDS).endsWith(" $relayId"))
                assertEquals(MessageType.Hello, helloEnvelope.type)
                assertEquals("client-real", helloPayload.deviceId)
                assertEquals("AetherLink Test Client", helloPayload.deviceName)
                assertEquals(MessageType.AuthResponse, authResponseEnvelope.type)
                assertEquals("client-real", authResponsePayload.deviceId)
                assertEquals("trusted-auth-nonce", authResponsePayload.nonce)
                assertTrue(!authResponsePayload.signature.isNullOrBlank())
                assertEquals(MessageType.RouteRefresh, routeRefreshEnvelope.type)
                assertEquals(MessageType.RuntimeHealth, healthEnvelope.type)
                assertEquals("ok", viewModel.state.value.runtimeStatus)
                assertEquals("100.64.2.20", connectedState.trustedRuntime?.relayHost)
                assertEquals("private_overlay", connectedState.trustedRuntime?.relayScope)
                assertEquals(RuntimeActiveRouteKind.Relay, connectedState.activeRouteKind)
                assertEquals("100.64.2.20", trustedRuntimeStore.trusted?.relayHost)
                assertEquals("private_overlay", trustedRuntimeStore.trusted?.relayScope)
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
            advanceUntilIdle()
            Thread.sleep(10)
        }
        advanceUntilIdle()
        return future.get(1, TimeUnit.SECONDS)
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    private fun TestScope.awaitActiveRouteKind(
        viewModel: RuntimeClientViewModel,
        expected: RuntimeActiveRouteKind,
    ): RuntimeUiState {
        val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(4)
        while (System.nanoTime() < deadline) {
            advanceUntilIdle()
            val state = viewModel.state.value
            if (state.activeRouteKind == expected) return state
            Thread.sleep(10)
        }
        advanceUntilIdle()
        return viewModel.state.value
    }

    private class FakeRelayRuntimeServer(
        private val json: Json,
        private val relayId: String,
        private val relaySecret: String,
        private val relayNonce: String,
        private val runtimeDeviceId: String,
        private val runtimePublicKey: String,
        private val runtimeFingerprint: String,
    ) : Closeable {
        private val codec = ProtocolCodec(json)
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
                    val handshake = input.readAsciiLine()
                    handshakeLine.complete(handshake)
                    require(handshake == "AETHERLINK_RELAY client $relayId") {
                        "Unexpected relay handshake: $handshake"
                    }
                    output.write("AETHERLINK_RELAY ready\n".toByteArray(Charsets.UTF_8))
                    output.flush()

                    val cryptor = TestRelayFrameBodyCryptor(relaySecret, relayNonce)
                    val encryptedBody = codec.readFrameBody(input)
                    val envelope = codec.decode(cryptor.decryptClientFrameBody(encryptedBody))
                    pairingRequest.complete(envelope)

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
                                trustedDeviceId = "client-real",
                                message = "trusted",
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

    private class FakeAuthenticatedRelayRuntimeServer(
        private val json: Json,
        private val relayId: String,
        private val relaySecret: String,
        private val relayNonce: String,
        private val runtimeIdentity: RuntimeIdentityMaterial,
    ) : Closeable {
        private val codec = ProtocolCodec(json)
        private val server = ServerSocket(0)
        private val serverError = CompletableFuture<Throwable?>()
        val port: Int = server.localPort
        val handshakeLine: CompletableFuture<String> = CompletableFuture()
        val helloRequest: CompletableFuture<ProtocolEnvelope> = CompletableFuture()
        val authResponseRequest: CompletableFuture<ProtocolEnvelope> = CompletableFuture()
        val routeRefreshRequest: CompletableFuture<ProtocolEnvelope> = CompletableFuture()
        val healthRequest: CompletableFuture<ProtocolEnvelope> = CompletableFuture()
        private val releaseConnection: CompletableFuture<Unit> = CompletableFuture()
        private val worker = thread(start = true, isDaemon = true) {
            runCatching {
                server.accept().use { socket ->
                    val input = socket.getInputStream()
                    val output = socket.getOutputStream()
                    val handshake = input.readAsciiLine()
                    handshakeLine.complete(handshake)
                    require(handshake == "AETHERLINK_RELAY client $relayId") {
                        "Unexpected relay handshake: $handshake"
                    }
                    output.write("AETHERLINK_RELAY ready\n".toByteArray(Charsets.UTF_8))
                    output.flush()

                    val cryptor = TestRelayFrameBodyCryptor(relaySecret, relayNonce)
                    val hello = readEncryptedEnvelope(input, cryptor)
                    helloRequest.complete(hello)
                    val helloPayload = json.decodeFromJsonElement(
                        HelloPayload.serializer(),
                        hello.payload,
                    )
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
                                    ),
                                ),
                            ).jsonObject,
                        ),
                    )

                    val authResponse = readEncryptedEnvelope(input, cryptor)
                    authResponseRequest.complete(authResponse)
                    writeEncryptedEnvelope(
                        output = output,
                        cryptor = cryptor,
                        envelope = ProtocolEnvelope(
                            type = MessageType.AuthResponse,
                            requestId = authResponse.requestId,
                            payload = json.encodeToJsonElement(
                                AuthResponsePayload.serializer(),
                                AuthResponsePayload(accepted = true),
                            ).jsonObject,
                        ),
                    )

                    while (!healthRequest.isDone) {
                        val request = readEncryptedEnvelope(input, cryptor)
                        when (request.type) {
                            MessageType.RouteRefresh -> {
                                routeRefreshRequest.complete(request)
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
                                                relayExpiresAtEpochMillis = 4102444800000L,
                                                relayNonce = relayNonce,
                                                relayScope = "private_overlay",
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
                healthRequest.completeExceptionally(error)
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

    private class TestRelayFrameBodyCryptor(secret: String, routeNonce: String) {
        private val key = SecretKeySpec(deriveKey(secret, routeNonce), "AES")
        private var clientCounter = 0L
        private var runtimeCounter = 0L

        fun decryptClientFrameBody(ciphertext: ByteArray): ByteArray {
            val plaintext = crypt(
                mode = Cipher.DECRYPT_MODE,
                direction = CLIENT_DIRECTION,
                counter = clientCounter,
                input = ciphertext,
            )
            clientCounter += 1
            return plaintext
        }

        fun encryptRuntimeFrameBody(plaintext: ByteArray): ByteArray {
            val ciphertext = crypt(
                mode = Cipher.ENCRYPT_MODE,
                direction = RUNTIME_DIRECTION,
                counter = runtimeCounter,
                input = plaintext,
            )
            runtimeCounter += 1
            return ciphertext
        }

        private fun crypt(
            mode: Int,
            direction: ByteArray,
            counter: Long,
            input: ByteArray,
        ): ByteArray {
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(mode, key, GCMParameterSpec(GCM_TAG_BITS, nonce(direction, counter)))
            cipher.updateAAD(AAD)
            return cipher.doFinal(input)
        }

        private companion object {
            private val KEY_PREFIX = "AetherLink relay frame v1\n".toByteArray(Charsets.UTF_8)
            private val ROUTE_NONCE_CONTEXT = "\nroute_nonce\n".toByteArray(Charsets.UTF_8)
            private val AAD = "AETHERLINK_RELAY_FRAME_V1".toByteArray(Charsets.UTF_8)
            private val CLIENT_DIRECTION = "CLNT".toByteArray(Charsets.US_ASCII)
            private val RUNTIME_DIRECTION = "RUNT".toByteArray(Charsets.US_ASCII)
            private const val GCM_TAG_BITS = 128

            private fun deriveKey(secret: String, routeNonce: String): ByteArray {
                val digest = MessageDigest.getInstance("SHA-256")
                digest.update(KEY_PREFIX)
                digest.update(secret.toByteArray(Charsets.UTF_8))
                digest.update(ROUTE_NONCE_CONTEXT)
                digest.update(routeNonce.toByteArray(Charsets.UTF_8))
                return digest.digest()
            }

            private fun nonce(direction: ByteArray, counter: Long): ByteArray {
                val counterBytes = ByteBuffer.allocate(Long.SIZE_BYTES).putLong(counter).array()
                return direction + counterBytes
            }
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
        val keyPair = KeyPairGenerator.getInstance("EC")
            .apply { initialize(ECGenParameterSpec("secp256r1")) }
            .generateKeyPair()
        return DeviceIdentity(
            deviceId = "client-real",
            deviceName = "AetherLink Test Client",
            publicKeyBase64 = "client-public-key-real",
            keyPair = keyPair,
        )
    }

    private data class RuntimeIdentityMaterial(
        val publicKeyBase64: String,
        val fingerprint: String,
        private val privateKey: java.security.PrivateKey,
    ) {
        fun signChallenge(deviceId: String, nonce: String): String {
            val message = RuntimeIdentityProofVerifier.authenticationChallengeMessage(
                deviceId = deviceId,
                nonce = nonce,
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
