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
