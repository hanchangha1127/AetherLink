package com.localagentbridge.android.core.transport

import com.localagentbridge.android.core.protocol.ProtocolCodec
import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.net.InetSocketAddress
import java.net.Socket
import java.nio.ByteBuffer
import java.security.MessageDigest
import javax.crypto.Cipher
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

class RuntimeRelayTcpClient(
    private val codec: ProtocolCodec = ProtocolCodec(),
) : RuntimeRelayConnector {
    override suspend fun connect(
        route: PreparedRemoteRuntimeRoute.Relay,
        timeoutMillis: Int,
    ): RuntimeProtocolChannel = withContext(Dispatchers.IO) {
        val socket = Socket()
        socket.tcpNoDelay = true
        socket.soTimeout = timeoutMillis
        socket.connect(InetSocketAddress(route.host, route.port), timeoutMillis)
        val channel = RelayProtocolChannel(
            socket = socket,
            codec = codec,
            frameCryptor = route.relayFrameSecret
                ?.takeIf { it.isNotBlank() }
                ?.let { RelayFrameBodyCryptor(it, route.security.antiReplayNonce) },
        )
        runCatching {
            channel.sendHandshake(route.relayId)
            channel.awaitReady()
            socket.soTimeout = 0
        }.onFailure {
            channel.close()
        }.getOrThrow()
        channel
    }

    private class RelayProtocolChannel(
        private val socket: Socket,
        private val codec: ProtocolCodec,
        private val frameCryptor: RelayFrameBodyCryptor?,
    ) : RuntimeProtocolChannel {
        private val sendMutex = Mutex()

        override val isConnected: Boolean
            get() = socket.isConnected && !socket.isClosed

        suspend fun sendHandshake(relayId: String) = withContext(Dispatchers.IO) {
            val handshake = "AETHERLINK_RELAY client ${relayId.sanitizeRelayToken()}\n"
            socket.outputStream.write(handshake.toByteArray(Charsets.UTF_8))
            socket.outputStream.flush()
        }

        suspend fun awaitReady() = withContext(Dispatchers.IO) {
            val line = socket.inputStream.readAsciiLine(maxBytes = 256)
            require(line == RELAY_READY_LINE) { "Relay did not accept route" }
        }

        override suspend fun send(envelope: ProtocolEnvelope) = withContext(Dispatchers.IO) {
            val body = codec.encodeBody(envelope)
            sendMutex.withLock {
                val framedBody = frameCryptor?.encryptClientFrameBody(body) ?: body
                val frame = codec.encodeFrameBody(framedBody)
                socket.outputStream.write(frame)
                socket.outputStream.flush()
            }
        }

        override suspend fun receive(): ProtocolEnvelope = withContext(Dispatchers.IO) {
            val framedBody = codec.readFrameBody(socket.inputStream)
            val body = frameCryptor?.decryptRuntimeFrameBody(framedBody) ?: framedBody
            codec.decode(body)
        }

        override fun close() {
            socket.close()
        }
    }

    private companion object {
        const val RELAY_READY_LINE = "AETHERLINK_RELAY ready"
    }
}

internal class RelayFrameBodyCryptor(secret: String, routeNonce: String? = null) {
    private val key = SecretKeySpec(deriveKey(secret, routeNonce), "AES")
    private var clientCounter = 0L
    private var runtimeCounter = 0L

    init {
        require(secret.isNotBlank()) { "Relay frame secret must not be blank" }
        require(routeNonce?.isNotBlank() != false) { "Relay frame route nonce must not be blank" }
    }

    fun encryptClientFrameBody(plaintext: ByteArray): ByteArray {
        val ciphertext = crypt(
            mode = Cipher.ENCRYPT_MODE,
            direction = CLIENT_DIRECTION,
            counter = clientCounter,
            input = plaintext,
        )
        clientCounter += 1
        return ciphertext
    }

    fun decryptRuntimeFrameBody(ciphertext: ByteArray): ByteArray {
        val plaintext = crypt(
            mode = Cipher.DECRYPT_MODE,
            direction = RUNTIME_DIRECTION,
            counter = runtimeCounter,
            input = ciphertext,
        )
        runtimeCounter += 1
        return plaintext
    }

    internal fun encryptRuntimeFrameBodyForTest(plaintext: ByteArray): ByteArray {
        val ciphertext = crypt(
            mode = Cipher.ENCRYPT_MODE,
            direction = RUNTIME_DIRECTION,
            counter = runtimeCounter,
            input = plaintext,
        )
        runtimeCounter += 1
        return ciphertext
    }

    internal fun decryptClientFrameBodyForTest(ciphertext: ByteArray): ByteArray {
        val plaintext = crypt(
            mode = Cipher.DECRYPT_MODE,
            direction = CLIENT_DIRECTION,
            counter = clientCounter,
            input = ciphertext,
        )
        clientCounter += 1
        return plaintext
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

        private fun deriveKey(secret: String, routeNonce: String?): ByteArray {
            val digest = MessageDigest.getInstance("SHA-256")
            digest.update(KEY_PREFIX)
            digest.update(secret.toByteArray(Charsets.UTF_8))
            if (routeNonce != null) {
                digest.update(ROUTE_NONCE_CONTEXT)
                digest.update(routeNonce.toByteArray(Charsets.UTF_8))
            }
            return digest.digest()
        }

        private fun nonce(direction: ByteArray, counter: Long): ByteArray {
            require(direction.size == 4) { "Relay frame direction must be 4 bytes" }
            require(counter >= 0L) { "Relay frame counter must not be negative" }
            val counterBytes = ByteBuffer.allocate(Long.SIZE_BYTES).putLong(counter).array()
            return direction + counterBytes
        }
    }
}

private fun String.sanitizeRelayToken(): String {
    require(isNotBlank()) { "Relay token must not be blank" }
    require(none { it <= ' ' }) { "Relay token must not contain whitespace" }
    return this
}

private fun java.io.InputStream.readAsciiLine(maxBytes: Int): String {
    val buffer = StringBuilder()
    while (buffer.length < maxBytes) {
        val next = read()
        if (next == -1) break
        if (next == '\n'.code) return buffer.toString().trimEnd('\r')
        buffer.append(next.toChar())
    }
    error("Relay handshake response was not a complete line")
}
