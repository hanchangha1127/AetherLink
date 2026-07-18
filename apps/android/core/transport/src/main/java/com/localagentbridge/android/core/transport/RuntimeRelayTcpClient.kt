package com.localagentbridge.android.core.transport

import com.localagentbridge.android.core.protocol.ProtocolCodec
import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import com.localagentbridge.android.core.protocol.PAIRED_CLIENT_RELAY_REGISTRATION_CHALLENGE_PREFIX
import com.localagentbridge.android.core.protocol.PairedClientRelayRegistrationAuthorization
import com.localagentbridge.android.core.protocol.PairedClientRelayRegistrationChallenge
import com.localagentbridge.android.core.protocol.PairedClientRelayRegistrationProof
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.io.OutputStream
import java.net.InetSocketAddress
import java.net.Socket
import java.security.MessageDigest
import java.security.SecureRandom

class RuntimeRelayTcpClient(
    private val codec: ProtocolCodec = ProtocolCodec(),
    private val socketFactory: RuntimeRelaySocketFactory = RuntimeRelaySocketFactory.default,
    private val clientRegistrationAuthorizer: RelayClientRegistrationAuthorizer? = null,
) : RuntimeRelayConnector {
    override suspend fun connect(
        route: PreparedRemoteRuntimeRoute.Relay,
        timeoutMillis: Int,
    ): RuntimeProtocolChannel = withContext(Dispatchers.IO) {
        val relayFrameSecret = route.relayFrameSecret?.takeIf { it.isNotBlank() }
        val clientSessionNonce = relayFrameSecret?.let { generateSessionNonce() }
        val clientEphemeralKeyPair = relayFrameSecret?.let { RelayEphemeralKeyPair.generate() }
        val socket = socketFactory.connect(route, timeoutMillis)
        runCatching {
            val channel = RelayProtocolChannel(
                socket = socket,
                codec = codec,
                relayFrameSecret = relayFrameSecret,
                routeNonce = route.security.antiReplayNonce,
                clientSessionNonce = clientSessionNonce,
                clientEphemeralKeyPair = clientEphemeralKeyPair,
                clientRegistrationAuthorizer = clientRegistrationAuthorizer,
            )
            channel.sendHandshake(route.relayId)
            channel.awaitReady(route)
            socket.soTimeout = 0
            channel
        }.onFailure {
            socket.close()
        }.getOrThrow()
    }

    private class RelayProtocolChannel(
        private val socket: Socket,
        private val codec: ProtocolCodec,
        private val relayFrameSecret: String?,
        private val routeNonce: String?,
        private val clientSessionNonce: String?,
        private val clientEphemeralKeyPair: RelayEphemeralKeyPair?,
        private val clientRegistrationAuthorizer: RelayClientRegistrationAuthorizer?,
    ) : RuntimeProtocolChannel {
        private val sendMutex = Mutex()
        private val receiveMutex = Mutex()
        private var frameCryptor: RelayFrameBodyCryptor? = null
        private var confirmedTransportSecurityContext: TransportSecurityContext? = null

        override val isConnected: Boolean
            get() = socket.isConnected && !socket.isClosed

        override val transportSecurityContext: TransportSecurityContext?
            get() = confirmedTransportSecurityContext

        suspend fun sendHandshake(relayId: String) = withContext(Dispatchers.IO) {
            val handshake = buildString {
                append("AETHERLINK_RELAY client ${relayId.requireRelayToken()}")
                if (relayFrameSecret != null) {
                    append(" crypto=2")
                    append(" session_nonce=${requireNotNull(clientSessionNonce).requireSessionNonce()}")
                    append(" ephemeral_key=${requireNotNull(clientEphemeralKeyPair).publicKeyHex}")
                }
                append('\n')
            }
            socket.outputStream.write(handshake.toByteArray(Charsets.UTF_8))
            socket.outputStream.flush()
        }

        suspend fun awaitReady(route: PreparedRemoteRuntimeRoute.Relay) = withContext(Dispatchers.IO) {
            var line = if (relayFrameSecret == null) {
                socket.inputStream.readAsciiLine(maxBytes = 256)
            } else {
                socket.inputStream.readExactAsciiLine(maxBytes = 4_096)
            }
            if (line.startsWith(PAIRED_CLIENT_RELAY_REGISTRATION_CHALLENGE_PREFIX)) {
                require(relayFrameSecret != null) {
                    "Paired relay client registration requires strict relay crypto"
                }
                val challenge = PairedClientRelayRegistrationAuthorization
                    .parseChallengeControlLine(line)
                val expectedRuntimeFingerprint = requireNotNull(route.identity.fingerprint) {
                    "Paired relay client registration requires a pinned runtime fingerprint"
                }
                val expectedGeneration = requireNotNull(route.ticketGeneration) {
                    "Paired relay client registration was not expected for this route"
                }
                require(
                    challenge.relayId == route.relayId &&
                        challenge.relayExpiresAtEpochMillis == route.security.expiresAtEpochMillis &&
                        challenge.relayNonce == route.security.antiReplayNonce &&
                        challenge.runtimeKeyFingerprint == expectedRuntimeFingerprint &&
                        challenge.ticketGeneration == expectedGeneration &&
                        challenge.sessionNonce == clientSessionNonce &&
                        challenge.ephemeralKey == clientEphemeralKeyPair?.publicKeyHex &&
                        challenge.isFresh(System.currentTimeMillis()),
                ) { "Relay client registration challenge did not match the prepared route" }
                val proof = requireNotNull(clientRegistrationAuthorizer) {
                    "Paired relay client registration authorizer is unavailable"
                }.authorize(challenge)
                socket.outputStream.write(
                    PairedClientRelayRegistrationAuthorization
                        .proofControlLine(challenge, proof)
                        .toByteArray(Charsets.UTF_8),
                )
                socket.outputStream.flush()
                line = socket.inputStream.readExactAsciiLine(maxBytes = 256)
            } else {
                require(route.ticketGeneration == null) {
                    "Paired relay client registration challenge was missing"
                }
            }
            val runtimeSession = parseRuntimeSession(
                line = line,
                requiresStrictCrypto = relayFrameSecret != null,
            )
            relayFrameSecret?.let { secret ->
                val sessionCrypto = RelaySessionCrypto.establish(
                        relaySecret = secret,
                        relayId = route.relayId,
                    routeNonce = routeNonce,
                    clientSessionNonce = requireNotNull(clientSessionNonce),
                    runtimeSessionNonce = requireNotNull(runtimeSession).sessionNonce,
                    clientEphemeralKey = requireNotNull(clientEphemeralKeyPair).publicKeyHex,
                    runtimeEphemeralKey = runtimeSession.ephemeralKey,
                    localEphemeralKeyPair = clientEphemeralKeyPair,
                )
                val clientConfirmation = sessionCrypto.controlLine(role = RelaySessionCrypto.CLIENT_ROLE) + '\n'
                socket.outputStream.write(clientConfirmation.toByteArray(Charsets.UTF_8))
                socket.outputStream.flush()

                val runtimeConfirmation = socket.inputStream.readExactAsciiLine(maxBytes = 256)
                val expectedRuntimeConfirmation = sessionCrypto.controlLine(role = RelaySessionCrypto.RUNTIME_ROLE)
                require(
                    MessageDigest.isEqual(
                        expectedRuntimeConfirmation.toByteArray(Charsets.UTF_8),
                        runtimeConfirmation.toByteArray(Charsets.UTF_8),
                    ),
                ) { "Relay key confirmation failed" }

                frameCryptor = sessionCrypto.frameCryptor()
                confirmedTransportSecurityContext = TransportSecurityContext(sessionCrypto.bindingId)
            }
        }

        override suspend fun send(envelope: ProtocolEnvelope) = withContext(Dispatchers.IO) {
            val body = codec.encodeBody(envelope)
            sendMutex.withLock {
                try {
                    val framedBody = frameCryptor?.encryptClientFrameBody(body) ?: body
                    socket.outputStream.writeProtocolFrameBody(framedBody)
                    socket.outputStream.flush()
                } catch (failure: Throwable) {
                    close()
                    throw failure
                }
            }
        }

        override suspend fun receive(): ProtocolEnvelope = withContext(Dispatchers.IO) {
            receiveMutex.withLock {
                val body = try {
                    val framedBody = codec.readFrameBody(socket.inputStream)
                    frameCryptor?.decryptRuntimeFrameBody(framedBody) ?: framedBody
                } catch (failure: Throwable) {
                    close()
                    throw failure
                }
                codec.decode(body)
            }
        }

        override fun close() {
            socket.close()
        }
    }

    private companion object {
        const val RELAY_READY_LINE = "AETHERLINK_RELAY ready"
        val SECURE_RANDOM = SecureRandom()
        val STRICT_READY_PATTERN = Regex(
            "AETHERLINK_RELAY ready crypto=2 " +
                "peer_session_nonce=([0-9a-f]{32}) " +
                "peer_ephemeral_key=([0-9a-f]{130})",
        )
        val LOWERCASE_HEX = "0123456789abcdef".toCharArray()

        fun generateSessionNonce(): String {
            val bytes = ByteArray(16)
            SECURE_RANDOM.nextBytes(bytes)
            val hex = CharArray(bytes.size * 2)
            bytes.forEachIndexed { index, byte ->
                val value = byte.toInt() and 0xff
                hex[index * 2] = LOWERCASE_HEX[value ushr 4]
                hex[index * 2 + 1] = LOWERCASE_HEX[value and 0x0f]
            }
            return String(hex)
        }

        fun parseRuntimeSession(
            line: String,
            requiresStrictCrypto: Boolean,
        ): StrictRuntimeSession? {
            val strictReady = STRICT_READY_PATTERN.matchEntire(line)
            if (requiresStrictCrypto) {
                require(strictReady != null) { "Relay did not accept route" }
                val ephemeralKey = strictReady.groupValues[2].requireEphemeralKey()
                return StrictRuntimeSession(
                    sessionNonce = strictReady.groupValues[1],
                    ephemeralKey = ephemeralKey,
                )
            }
            require(line == RELAY_READY_LINE) {
                "Relay did not accept route"
            }
            return null
        }

        data class StrictRuntimeSession(
            val sessionNonce: String,
            val ephemeralKey: String,
        )
    }
}

internal fun OutputStream.writeProtocolFrameBody(body: ByteArray) {
    require(body.size in 1..ProtocolCodec.MAX_FRAME_BYTES) { "Invalid frame body length: ${body.size}" }
    val size = body.size
    write(
        byteArrayOf(
            (size ushr 24).toByte(),
            (size ushr 16).toByte(),
            (size ushr 8).toByte(),
            size.toByte(),
        ),
    )
    write(body)
}

fun interface RelayClientRegistrationAuthorizer {
    suspend fun authorize(
        challenge: PairedClientRelayRegistrationChallenge,
    ): PairedClientRelayRegistrationProof
}

fun interface RuntimeRelaySocketFactory {
    fun connect(route: PreparedRemoteRuntimeRoute.Relay, timeoutMillis: Int): Socket

    companion object {
        val default = RuntimeRelaySocketFactory { route, timeoutMillis ->
            Socket().apply {
                tcpNoDelay = true
                soTimeout = timeoutMillis
                connect(InetSocketAddress(route.host, route.port), timeoutMillis)
            }
        }
    }
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

private fun java.io.InputStream.readExactAsciiLine(maxBytes: Int): String {
    val buffer = StringBuilder()
    while (buffer.length < maxBytes) {
        val next = read()
        if (next == -1) break
        if (next == '\n'.code) return buffer.toString()
        buffer.append(next.toChar())
    }
    error("Relay strict response was not a complete line")
}
