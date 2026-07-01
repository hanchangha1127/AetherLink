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
        val clientBody = """{"type":"models.list","request_id":"request-1","payload":{}}""".encodeToByteArray()
        val encryptedClientBody = clientCryptor.encryptClientFrameBody(clientBody)
        val decryptedClientBody = runtimeCryptor.decryptClientFrameBodyForTest(encryptedClientBody)
        val runtimeBody = """{"type":"runtime.health","request_id":"request-2","payload":{}}""".encodeToByteArray()
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
        val clientBody = """{"type":"models.list","request_id":"vector-1","payload":{}}""".encodeToByteArray()
        val runtimeBody = """{"type":"runtime.health","request_id":"vector-2","payload":{}}""".encodeToByteArray()

        assertEquals(
            "445732376c183bb714bed5bb30570b16dd468e63392137eabc0259c1cc49f1c79c7babcf4ded6e05c91707bf1168823708c670b888a3319140063f1900d799afa5ad81bfa7df52c96f88c1",
            clientCryptor.encryptClientFrameBody(clientBody).toHex(),
        )
        assertEquals(
            "ec6f782db28fe4e5bc8a0bfd9c8944051dbaeceea6bd1d3ec34b1ef9cf265f728a76ef7f24dcad7daaa516cb1f756d24d686df0b05806e436524baf6f4d27f6fb86e25b5eae90f83ccf30718cf68",
            runtimeCryptor.encryptRuntimeFrameBodyForTest(runtimeBody).toHex(),
        )
    }

    @Test
    fun relayFrameCryptorBindsRouteNonceIntoKey() {
        val clientCryptor = RelayFrameBodyCryptor("relay-secret-1", "relay-nonce-1")
        val runtimeCryptor = RelayFrameBodyCryptor("relay-secret-1", "relay-nonce-1")
        val wrongNonceRuntimeCryptor = RelayFrameBodyCryptor("relay-secret-1", "relay-nonce-2")
        val clientBody = """{"type":"models.list","request_id":"request-1","payload":{}}""".encodeToByteArray()
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
        val clientBody = """{"type":"models.list","request_id":"vector-1","payload":{}}""".encodeToByteArray()
        val runtimeBody = """{"type":"runtime.health","request_id":"vector-2","payload":{}}""".encodeToByteArray()

        assertEquals(
            "74f16ae572397183106c40e09692c529475b5c71a6a65351177bb184968dd94a16bb1366ba73ef68614d722cebc79e67782e9b5f797bfc3d0b59a6ba9a5d48873303037e1866b51a32fb9d",
            clientCryptor.encryptClientFrameBody(clientBody).toHex(),
        )
        assertEquals(
            "aae3d45d8054aeccfbe0af5e5f9193ec1812a9d7c2cd2f9456b0e8e5cde3f991382e886940bc3f1e3a7004b1fc55d72ed295a1b03f670c765b92f3bb7be947f27f3f4572eff0aeb6a541e1c263c5",
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
