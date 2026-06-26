package com.localagentbridge.android.runtime

import android.app.Application
import androidx.lifecycle.viewModelScope
import com.localagentbridge.android.core.pairing.DeviceIdentity
import com.localagentbridge.android.core.pairing.TrustedRuntime
import com.localagentbridge.android.core.protocol.MessageType
import com.localagentbridge.android.core.protocol.PairingRequestPayload
import com.localagentbridge.android.core.protocol.PairingResultPayload
import com.localagentbridge.android.core.protocol.ProtocolCodec
import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import com.localagentbridge.android.core.transport.DiscoveredRuntime
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
import java.net.ServerSocket
import java.nio.ByteBuffer
import java.security.KeyPairGenerator
import java.security.MessageDigest
import java.security.spec.ECGenParameterSpec
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
                assertEquals("127.0.0.1", viewModel.state.value.trustedRuntime?.relayHost)
                assertEquals(RuntimeActiveRouteKind.Relay, viewModel.state.value.activeRouteKind)
                assertNull(relay.closedWithoutServerError())
            } finally {
                viewModel?.stopForTest()
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
                }
                serverError.complete(null)
            }.onFailure { error ->
                handshakeLine.completeExceptionally(error)
                pairingRequest.completeExceptionally(error)
                serverError.complete(error)
            }
        }

        fun closedWithoutServerError(): Throwable? {
            val error = serverError.get(2, TimeUnit.SECONDS)
            worker.join(1_000)
            return error
        }

        override fun close() {
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

    private class FakeTrustedRuntimeStore : RuntimeTrustedRuntimeStore {
        private val trustedRuntimeFlow = MutableStateFlow<TrustedRuntime?>(null)
        override val trustedRuntime: Flow<TrustedRuntime?> = trustedRuntimeFlow
        val trustedRuntimeWritten: CompletableFuture<TrustedRuntime> = CompletableFuture()

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
