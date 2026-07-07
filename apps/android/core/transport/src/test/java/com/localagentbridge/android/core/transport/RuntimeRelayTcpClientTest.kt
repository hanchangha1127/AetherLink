package com.localagentbridge.android.core.transport

import com.localagentbridge.android.core.protocol.ProtocolCodec
import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import com.localagentbridge.android.core.protocol.MessageType
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.ByteArrayInputStream
import java.net.ServerSocket
import java.util.concurrent.CompletableFuture
import java.util.concurrent.TimeUnit
import kotlin.concurrent.thread
import kotlin.system.measureTimeMillis

class RuntimeRelayTcpClientTest {
    @Test
    fun relayFrameCryptorRoundTripsProtocolFrameBodies() {
        val codec = ProtocolCodec()
        val clientCryptor = RelayFrameBodyCryptor("relay-secret-1")
        val runtimeCryptor = RelayFrameBodyCryptor("relay-secret-1")
        val clientBody = envelopeBody(type = "models.list", requestId = "request-1")
        val encryptedClientBody = clientCryptor.encryptClientFrameBody(clientBody)
        val decryptedClientBody = runtimeCryptor.decryptClientFrameBodyForTest(encryptedClientBody)
        val runtimeBody = envelopeBody(type = "runtime.health", requestId = "request-2")
        val encryptedRuntimeBody = runtimeCryptor.encryptRuntimeFrameBodyForTest(runtimeBody)
        val framedRuntimeBody = codec.readFrameBody(ByteArrayInputStream(codec.encodeFrameBody(encryptedRuntimeBody)))
        val decryptedRuntimeBody = clientCryptor.decryptRuntimeFrameBody(framedRuntimeBody)

        assertFalse(clientBody.contentEquals(encryptedClientBody))
        assertEquals("request-1", codec.decode(decryptedClientBody).requestId)
        assertFalse(runtimeBody.contentEquals(encryptedRuntimeBody))
        assertEquals("request-2", codec.decode(decryptedRuntimeBody).requestId)
    }

    @Test
    fun relayFrameCryptorMatchesSharedCiphertextVectors() {
        val clientCryptor = RelayFrameBodyCryptor("relay-secret-vector")
        val runtimeCryptor = RelayFrameBodyCryptor("relay-secret-vector")
        val clientBody = envelopeBody(type = "models.list", requestId = "vector-1")
        val runtimeBody = envelopeBody(type = "runtime.health", requestId = "vector-2")

        assertEquals(
            "4457302b6e0e70e258f180ee79190c41c14adf2d39607afcbc1f5f8ad354dddada75b39f5ef97814d51175e757669a651fda7fa386b53e9a1957608bec1ee575f365fee212e8ccde9e5a23e7cf47de8158f69db5fb2abe3cd20cfed775ef7f1464a2657fdc0a920e2fe563addbd472c93730fb106d9d48b51b4e",
            clientCryptor.encryptClientFrameBody(clientBody).toHex(),
        )
        assertEquals(
            "ec6f7a31b099afb0f0da44a2c4c25d1943b7abb5e8bb00729b0001f9903b5f60925dee392ac4fd6ebeb307d719073662d89e8d1c198f754d732bb2afa58dc0278b69ce81c6d3e87f48caf26707488d0f3b980bd0a8ab21809e13dec4ab8867a0eeee4166d732d39bb932b3ed437e8908e61fbb33d83a59089f217505da",
            runtimeCryptor.encryptRuntimeFrameBodyForTest(runtimeBody).toHex(),
        )
    }

    @Test
    fun relayFrameCryptorBindsRouteNonceIntoKey() {
        val clientCryptor = RelayFrameBodyCryptor("relay-secret-1", "relay-nonce-1")
        val runtimeCryptor = RelayFrameBodyCryptor("relay-secret-1", "relay-nonce-1")
        val wrongNonceRuntimeCryptor = RelayFrameBodyCryptor("relay-secret-1", "relay-nonce-2")
        val clientBody = envelopeBody(type = "models.list", requestId = "request-1")
        val encryptedClientBody = clientCryptor.encryptClientFrameBody(clientBody)

        assertEquals(
            "request-1",
            ProtocolCodec().decode(runtimeCryptor.decryptClientFrameBodyForTest(encryptedClientBody)).requestId,
        )
        assertThrows(Exception::class.java) {
            wrongNonceRuntimeCryptor.decryptClientFrameBodyForTest(encryptedClientBody)
        }
    }

    @Test
    fun relayFrameCryptorMatchesNonceBoundSharedCiphertextVectors() {
        val clientCryptor = RelayFrameBodyCryptor("relay-secret-vector", "relay-nonce-vector")
        val runtimeCryptor = RelayFrameBodyCryptor("relay-secret-vector", "relay-nonce-vector")
        val clientBody = envelopeBody(type = "models.list", requestId = "vector-1")
        val runtimeBody = envelopeBody(type = "runtime.health", requestId = "vector-2")

        assertEquals(
            "74f168f9702f3ad65c2315b5dfdcc27e5b570d3fa6e71e471766b7cf8990f55750b50b36a967f9797d4b0074adc986356f329444776df3365208f9de7d25aa1387c574d3c7beb9e4e339ef3f974686d67dfc2c19d3abf398af4c4867b2ccfe44b54f80647e18a4e64f9b15c76989a56f23d99d30b227fc9ea2a2",
            clientCryptor.encryptClientFrameBody(clientBody).toHex(),
        )
        assertEquals(
            "aae3d6418242e599b7b0e00107da8af0461fee8c8ccb32d80efbf7e592fef9832005892f4ea46f0d2e6615adfa278c68dc8df3a7236817784d9dfbe22ab6da43ae564e34c2d41df80a866ebbc7f60e3258f50af91235842f92a56137c6e48d83be96821c54f8c37e9c801c29419047e1296e5b48ea12b32e56426f4abf",
            runtimeCryptor.encryptRuntimeFrameBodyForTest(runtimeBody).toHex(),
        )
    }

    @Test
    fun relayConnectTimesOutWhenReadyLineNeverArrives() {
        val server = ServerSocket(0)
        val serverThread = thread(start = true, isDaemon = true) {
            runCatching {
                server.accept().use { socket ->
                    socket.getInputStream().read()
                    Thread.sleep(1_000)
                }
            }
        }
        val client = RuntimeRelayTcpClient()
        val identity = PairedRuntimeIdentity(
            deviceId = "runtime-1",
            name = "AetherLink",
            fingerprint = "fingerprint",
        )
        val route = PreparedRemoteRuntimeRoute.Relay(
            identity = identity,
            relayId = "relay-timeout",
            host = "127.0.0.1",
            port = server.localPort,
            security = RemoteRouteSecurityContext(
                rendezvousToken = "relay-timeout",
                expiresAtEpochMillis = Long.MAX_VALUE,
                antiReplayNonce = "relay-timeout",
            ),
        )

        val elapsedMillis = measureTimeMillis {
            assertThrows(Exception::class.java) {
                runBlocking {
                    client.connect(route, timeoutMillis = 150)
                }
            }
        }

        server.close()
        serverThread.join(1_500)
        assertTrue("Relay connect should not wait forever", elapsedMillis < 1_500)
    }

    @Test
    fun relayConnectFailsWhenReadyLineRejectsRoute() {
        val server = ServerSocket(0)
        val receivedHandshake = CompletableFuture<String>()
        val serverThread = thread(start = true, isDaemon = true) {
            runCatching {
                server.accept().use { socket ->
                    receivedHandshake.complete(socket.getInputStream().readAsciiLine())
                    socket.getOutputStream().write("AETHERLINK_RELAY rejected\n".toByteArray(Charsets.UTF_8))
                    socket.getOutputStream().flush()
                }
            }.onFailure(receivedHandshake::completeExceptionally)
        }
        val client = RuntimeRelayTcpClient()
        val identity = PairedRuntimeIdentity(
            deviceId = "runtime-1",
            name = "AetherLink",
            fingerprint = "fingerprint",
        )
        val route = PreparedRemoteRuntimeRoute.Relay(
            identity = identity,
            relayId = "relay-rejected",
            host = "127.0.0.1",
            port = server.localPort,
            security = RemoteRouteSecurityContext(
                rendezvousToken = "relay-rejected",
                expiresAtEpochMillis = Long.MAX_VALUE,
                antiReplayNonce = "relay-rejected",
            ),
        )

        val error = assertThrows(IllegalArgumentException::class.java) {
            runBlocking {
                client.connect(route, timeoutMillis = 1_000)
            }
        }

        assertEquals("AETHERLINK_RELAY client relay-rejected", receivedHandshake.get(2, TimeUnit.SECONDS))
        assertEquals("Relay did not accept route", error.message)
        server.close()
        serverThread.join(1_500)
    }

    @Test
    fun relayChannelEncryptsSentFramesAndDecryptsRuntimeResponses() {
        runBlocking {
            val codec = ProtocolCodec()
            val relaySecret = "relay-channel-secret"
            val relayNonce = "relay-channel-nonce"
            val server = ServerSocket(0)
            val encryptedClientBody = CompletableFuture<ByteArray>()
            val encryptedRuntimeBody = CompletableFuture<ByteArray>()
            val serverThread = thread(start = true, isDaemon = true) {
                runCatching {
                    server.accept().use { socket ->
                        val handshake = socket.getInputStream().readAsciiLine()
                        assertEquals("AETHERLINK_RELAY client relay-channel", handshake)
                        socket.getOutputStream().write("AETHERLINK_RELAY ready\n".toByteArray(Charsets.UTF_8))
                        socket.getOutputStream().flush()

                        val runtimeCryptor = RelayFrameBodyCryptor(relaySecret, relayNonce)
                        val encryptedRequestBody = codec.readFrameBody(socket.getInputStream())
                        assertFalse(encryptedRequestBody.containsBytes(MessageType.ModelsList.encodeToByteArray()))
                        assertFalse(encryptedRequestBody.containsBytes("client-request-1".encodeToByteArray()))
                        val request = codec.decode(runtimeCryptor.decryptClientFrameBodyForTest(encryptedRequestBody))
                        assertEquals(MessageType.ModelsList, request.type)
                        assertEquals("client-request-1", request.requestId)
                        encryptedClientBody.complete(encryptedRequestBody)

                        val response = ProtocolEnvelope(
                            type = MessageType.RuntimeHealth,
                            requestId = "runtime-response-1",
                        )
                        val plaintextBody = codec.encodeBody(response)
                        val ciphertextBody = runtimeCryptor.encryptRuntimeFrameBodyForTest(plaintextBody)

                        assertFalse(plaintextBody.contentEquals(ciphertextBody))
                        assertFalse(ciphertextBody.containsBytes(MessageType.RuntimeHealth.encodeToByteArray()))
                        assertFalse(ciphertextBody.containsBytes("runtime-response-1".encodeToByteArray()))
                        encryptedRuntimeBody.complete(ciphertextBody)

                        socket.getOutputStream().write(codec.encodeFrameBody(ciphertextBody))
                        socket.getOutputStream().flush()
                    }
                }.onFailure { failure ->
                    encryptedClientBody.completeExceptionally(failure)
                    encryptedRuntimeBody.completeExceptionally(failure)
                }
            }
            val client = RuntimeRelayTcpClient()
            val route = PreparedRemoteRuntimeRoute.Relay(
                identity = PairedRuntimeIdentity(
                    deviceId = "runtime-1",
                    name = "AetherLink",
                    fingerprint = "fingerprint",
                ),
                relayId = "relay-channel",
                host = "127.0.0.1",
                port = server.localPort,
                relayFrameSecret = relaySecret,
                security = RemoteRouteSecurityContext(
                    rendezvousToken = "relay-channel",
                    expiresAtEpochMillis = Long.MAX_VALUE,
                    antiReplayNonce = relayNonce,
                ),
            )

            val channel = client.connect(route, timeoutMillis = 1_000)
            try {
                channel.send(
                    ProtocolEnvelope(
                        type = MessageType.ModelsList,
                        requestId = "client-request-1",
                    ),
                )
                val received = channel.receive()
                val capturedClientCiphertextBody = encryptedClientBody.get(2, TimeUnit.SECONDS)
                val capturedCiphertextBody = encryptedRuntimeBody.get(2, TimeUnit.SECONDS)

                assertEquals(MessageType.RuntimeHealth, received.type)
                assertEquals("runtime-response-1", received.requestId)
                assertThrows(Exception::class.java) {
                    RelayFrameBodyCryptor(relaySecret, "wrong-route-nonce")
                        .decryptClientFrameBodyForTest(capturedClientCiphertextBody)
                }
                assertThrows(Exception::class.java) {
                    RelayFrameBodyCryptor(relaySecret, "wrong-route-nonce")
                        .decryptRuntimeFrameBody(capturedCiphertextBody)
                }
            } finally {
                channel.close()
                server.close()
                serverThread.join(1_500)
            }
        }
    }

    @Test
    fun relayClientSerializesEncryptionWithConcurrentSends() = runBlocking {
        val codec = ProtocolCodec()
        val relaySecret = "relay-concurrent-secret"
        val frameCount = 48
        val server = ServerSocket(0)
        val receivedRequestIds = CompletableFuture<List<String>>()
        val serverThread = thread(start = true, isDaemon = true) {
            runCatching {
                server.accept().use { socket ->
                    val handshake = socket.getInputStream().readAsciiLine()
                    assertEquals("AETHERLINK_RELAY client relay-concurrent", handshake)
                    socket.getOutputStream().write("AETHERLINK_RELAY ready\n".toByteArray(Charsets.UTF_8))
                    socket.getOutputStream().flush()

                    val runtimeCryptor = RelayFrameBodyCryptor(relaySecret, "relay-concurrent")
                    val requestIds = mutableListOf<String>()
                    repeat(frameCount) {
                        val encryptedBody = codec.readFrameBody(socket.getInputStream())
                        val body = runtimeCryptor.decryptClientFrameBodyForTest(encryptedBody)
                        requestIds += codec.decode(body).requestId
                    }
                    receivedRequestIds.complete(requestIds)
                }
            }.onFailure(receivedRequestIds::completeExceptionally)
        }
        val client = RuntimeRelayTcpClient()
        val route = PreparedRemoteRuntimeRoute.Relay(
            identity = PairedRuntimeIdentity(
                deviceId = "runtime-1",
                name = "AetherLink",
                fingerprint = "fingerprint",
            ),
            relayId = "relay-concurrent",
            host = "127.0.0.1",
            port = server.localPort,
            relayFrameSecret = relaySecret,
            security = RemoteRouteSecurityContext(
                rendezvousToken = "relay-concurrent",
                expiresAtEpochMillis = Long.MAX_VALUE,
                antiReplayNonce = "relay-concurrent",
            ),
        )

        val channel = client.connect(route, timeoutMillis = 1_000)
        coroutineScope {
            (0 until frameCount)
                .map { index ->
                    async {
                        channel.send(
                            ProtocolEnvelope(
                                type = MessageType.ModelsList,
                                requestId = "request-$index",
                            ),
                        )
                    }
                }
                .awaitAll()
        }
        channel.close()

        val requestIds = receivedRequestIds.get(2, TimeUnit.SECONDS)
        server.close()
        serverThread.join(1_500)
        assertEquals(frameCount, requestIds.size)
        assertEquals((0 until frameCount).map { "request-$it" }.toSet(), requestIds.toSet())
    }

    private fun envelopeBody(type: String, requestId: String): ByteArray {
        return """{"version":1,"type":"$type","request_id":"$requestId","timestamp":"2026-07-07T00:00:00Z","payload":{}}"""
            .encodeToByteArray()
    }
}

private fun ByteArray.toHex(): String = joinToString(separator = "") { "%02x".format(it) }

private fun ByteArray.containsBytes(needle: ByteArray): Boolean {
    if (needle.isEmpty()) return true
    return indices.any { start ->
        start + needle.size <= size && needle.indices.all { offset -> this[start + offset] == needle[offset] }
    }
}

private fun java.io.InputStream.readAsciiLine(maxBytes: Int = 256): String {
    val buffer = StringBuilder()
    while (buffer.length < maxBytes) {
        val next = read()
        if (next == -1) break
        if (next == '\n'.code) return buffer.toString().trimEnd('\r')
        buffer.append(next.toChar())
    }
    error("ASCII line was not complete")
}
