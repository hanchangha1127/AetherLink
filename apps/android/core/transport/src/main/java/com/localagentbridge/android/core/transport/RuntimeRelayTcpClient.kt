package com.localagentbridge.android.core.transport

import com.localagentbridge.android.core.protocol.ProtocolCodec
import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import com.localagentbridge.android.core.protocol.PAIRED_CLIENT_RELAY_REGISTRATION_CHALLENGE_PREFIX
import com.localagentbridge.android.core.protocol.PairedClientRelayRegistrationAuthorization
import com.localagentbridge.android.core.protocol.PairedClientRelayRegistrationChallenge
import com.localagentbridge.android.core.protocol.PairedClientRelayRegistrationProof
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.io.OutputStream
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.Socket
import java.security.MessageDigest
import java.security.SecureRandom
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

class RuntimeRelayTcpClient(
    private val codec: ProtocolCodec = ProtocolCodec(),
    private val socketFactory: RuntimeRelaySocketFactory = RuntimeRelaySocketFactory.default,
    private val clientRegistrationAuthorizer: RelayClientRegistrationAuthorizer? = null,
) : RuntimeRelayConnector {
    override suspend fun connect(
        route: PreparedRemoteRuntimeRoute.Relay,
        timeoutMillis: Int,
    ): RuntimeProtocolChannel = connectWithMode(route, timeoutMillis, RuntimeFrameBodyMode.ProtocolEnvelope)

    suspend fun connectRaw(
        route: PreparedRemoteRuntimeRoute.Relay,
        timeoutMillis: Int,
    ): RuntimeRawFrameBodyChannel = connectWithMode(route, timeoutMillis, RuntimeFrameBodyMode.Raw)

    private suspend fun connectWithMode(
        route: PreparedRemoteRuntimeRoute.Relay,
        timeoutMillis: Int,
        mode: RuntimeFrameBodyMode,
    ): RelayProtocolChannel = withContext(Dispatchers.IO) {
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
                mode = mode,
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
        private val mode: RuntimeFrameBodyMode,
    ) : RuntimeProtocolChannel, RuntimeRawFrameBodyChannel {
        private val sendMutex = Mutex()
        private val sendAdmission = Semaphore(64)
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
            requireMode(RuntimeFrameBodyMode.ProtocolEnvelope)
            val body = codec.encodeBody(envelope)
            sendBody(body)
        }

        override suspend fun sendFrameBody(body: ByteArray) = withContext(Dispatchers.IO) {
            requireMode(RuntimeFrameBodyMode.Raw)
            try {
                requireRelayRawFrameBodyLength(body.size, frameCryptor != null)
            } catch (failure: Throwable) {
                close()
                throw failure
            }
            sendBody(body)
        }

        private suspend fun sendBody(body: ByteArray) {
            if (!sendAdmission.tryAcquire()) {
                close()
                error("Relay transport send backlog exceeded")
            }
            try {
                sendMutex.withLock {
                    suspendCancellableCoroutine { continuation ->
                        // Closing the socket is the only bounded way to interrupt a
                        // blocking Java write/flush when the enclosing authority-bound
                        // secure-session publication is cancelled or times out.
                        continuation.invokeOnCancellation {
                            runCatching { close() }
                        }
                        if (!continuation.isActive) return@suspendCancellableCoroutine
                        try {
                            val framedBody = frameCryptor?.encryptClientFrameBody(body) ?: body
                            socket.outputStream.writeProtocolFrameBody(framedBody)
                            socket.outputStream.flush()
                            continuation.resume(Unit) { _, _, _ ->
                                runCatching { close() }
                            }
                        } catch (failure: Throwable) {
                            runCatching { close() }
                            if (continuation.isActive) {
                                continuation.resumeWithException(failure)
                            }
                        }
                    }
                }
            } finally {
                sendAdmission.release()
            }
        }

        override suspend fun receive(): ProtocolEnvelope = withContext(Dispatchers.IO) {
            requireMode(RuntimeFrameBodyMode.ProtocolEnvelope)
            codec.decode(receiveBody())
        }

        override suspend fun receiveFrameBody(): ByteArray = withContext(Dispatchers.IO) {
            requireMode(RuntimeFrameBodyMode.Raw)
            receiveBody()
        }

        private suspend fun receiveBody(): ByteArray {
            return receiveMutex.withLock {
                suspendCancellableCoroutine { continuation ->
                    // Relay reads use the same blocking Java socket surface as
                    // writes. Cancellation must close it so a stopped adapter
                    // cannot leave an IO worker or handshake suspended forever.
                    continuation.invokeOnCancellation {
                        runCatching { close() }
                    }
                    if (!continuation.isActive) return@suspendCancellableCoroutine
                    try {
                        val framedBody = codec.readFrameBody(socket.inputStream)
                        val body = frameCryptor?.decryptRuntimeFrameBody(framedBody) ?: framedBody
                        require(body.size in 1..ProtocolCodec.MAX_FRAME_BYTES) {
                            "Invalid raw frame body length: ${body.size}"
                        }
                        continuation.resume(body) { _, _, _ ->
                            runCatching { close() }
                        }
                    } catch (failure: Throwable) {
                        runCatching { close() }
                        if (continuation.isActive) {
                            continuation.resumeWithException(failure)
                        }
                    }
                }
            }
        }

        private fun requireMode(expected: RuntimeFrameBodyMode) {
            if (mode != expected) {
                close()
                error("Relay transport frame-body mode mismatch")
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

internal const val RELAY_FRAME_AUTHENTICATION_TAG_BYTES = 16

internal fun maximumRelayRawFrameBodyBytes(usesFrameCryptor: Boolean): Int =
    ProtocolCodec.MAX_FRAME_BYTES - if (usesFrameCryptor) RELAY_FRAME_AUTHENTICATION_TAG_BYTES else 0

internal fun requireRelayRawFrameBodyLength(byteCount: Int, usesFrameCryptor: Boolean) {
    val maximum = maximumRelayRawFrameBodyBytes(usesFrameCryptor)
    require(byteCount in 1..maximum) {
        "Invalid raw relay frame body length: $byteCount (maximum $maximum)"
    }
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
                connect(resolveValidatedRelaySocketAddress(route), timeoutMillis)
            }
        }
    }
}

internal fun interface RuntimeRelayAddressResolver {
    fun resolve(host: String): Array<InetAddress>
}

internal fun resolveValidatedRelaySocketAddress(
    route: PreparedRemoteRuntimeRoute.Relay,
    resolver: RuntimeRelayAddressResolver = RuntimeRelayAddressResolver(InetAddress::getAllByName),
): InetSocketAddress {
    val host = route.host.removeSuffix(".").removePrefix("[").removeSuffix("]")
    val addresses = resolver.resolve(host)
    require(addresses.isNotEmpty()) { "Relay host did not resolve to an address" }
    require(addresses.all { it.isAllowedForRelayScope(route.relayScope) }) {
        "Relay host resolved outside its approved address scope"
    }
    return InetSocketAddress(addresses.first(), route.port)
}

private fun InetAddress.isAllowedForRelayScope(relayScope: String?): Boolean {
    return when (relayScope) {
        DEBUG_USB_REVERSE_RELAY_SCOPE -> isLoopbackAddress
        PRIVATE_OVERLAY_RELAY_SCOPE -> isPublicRelayAddress() || isPrivateOverlayRelayAddress()
        else -> isPublicRelayAddress()
    }
}

private fun InetAddress.isPublicRelayAddress(): Boolean {
    if (isAnyLocalAddress || isLoopbackAddress || isLinkLocalAddress || isSiteLocalAddress || isMulticastAddress) {
        return false
    }
    val octets = address.map { it.toInt() and 0xff }
    return when (octets.size) {
        4 -> {
            val first = octets[0]
            val second = octets[1]
            first != 0 && first < 224 && !(first == 100 && second in 64..127)
        }
        16 -> (octets[0] and 0xfe) != 0xfc
        else -> false
    }
}

private fun InetAddress.isPrivateOverlayRelayAddress(): Boolean {
    val octets = address.map { it.toInt() and 0xff }
    return when (octets.size) {
        4 -> {
            val first = octets[0]
            val second = octets[1]
            first == 10 ||
                (first == 100 && second in 64..127) ||
                (first == 172 && second in 16..31) ||
                (first == 192 && second == 168)
        }
        16 -> (octets[0] and 0xfe) == 0xfc
        else -> false
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
