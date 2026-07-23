package com.localagentbridge.android.core.transport

import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import java.io.Closeable

data class TransportSecurityContext(
    val bindingId: String,
) {
    init {
        require(bindingId.length == 64 && bindingId.all { it in '0'..'9' || it in 'a'..'f' }) {
            "Transport binding ID must be 64 lowercase hexadecimal characters"
        }
    }
}

interface RuntimeProtocolChannel : Closeable {
    val isConnected: Boolean

    val transportSecurityContext: TransportSecurityContext?
        get() = null

    suspend fun send(envelope: ProtocolEnvelope)

    suspend fun receive(): ProtocolEnvelope
}

/**
 * Exact identity surface required from a fully composed production secure channel.
 * A generic transport-security context is deliberately insufficient: the connection manager
 * validates these values against the verifier-prepared session and its own connection generation.
 */
internal interface RuntimeProductionProtocolChannel : RuntimeProtocolChannel {
    val productionBindingId: String

    val productionSessionId: String

    val productionConnectionGeneration: Long
}

/**
 * Opt-in transport surface for protocols that own the bytes inside the existing four-byte
 * big-endian length frame. A concrete connection is opened in either protocol-envelope mode or
 * raw-frame-body mode. Calling the other mode's API is a terminal misuse and closes the channel.
 * `close()` must synchronously initiate interruption of blocked send/receive operations; those
 * suspend calls must then complete with cancellation or failure rather than retain a caller's
 * authority/publication permit indefinitely.
 */
interface RuntimeRawFrameBodyChannel : Closeable {
    val isConnected: Boolean

    val transportSecurityContext: TransportSecurityContext?
        get() = null

    suspend fun sendFrameBody(body: ByteArray)

    suspend fun receiveFrameBody(): ByteArray
}

internal enum class RuntimeFrameBodyMode {
    ProtocolEnvelope,
    Raw,
}
