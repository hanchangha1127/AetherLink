package com.localagentbridge.android.core.transport

import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import java.io.Closeable

interface RuntimeProtocolChannel : Closeable {
    val isConnected: Boolean

    suspend fun send(envelope: ProtocolEnvelope)

    suspend fun receive(): ProtocolEnvelope
}
