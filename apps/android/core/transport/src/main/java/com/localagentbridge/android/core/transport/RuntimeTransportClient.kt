package com.localagentbridge.android.core.transport

import com.localagentbridge.android.core.protocol.ProtocolCodec
import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.io.Closeable
import java.net.InetSocketAddress
import java.net.Socket

class RuntimeTransportClient(
    private val codec: ProtocolCodec = ProtocolCodec(),
) : Closeable {
    private val sendMutex = Mutex()
    private var socket: Socket? = null

    val isConnected: Boolean
        get() = socket?.isConnected == true && socket?.isClosed == false

    suspend fun connect(host: String, port: Int, timeoutMillis: Int = 5_000) = withContext(Dispatchers.IO) {
        close()
        val connected = Socket()
        connected.tcpNoDelay = true
        connected.connect(InetSocketAddress(host, port), timeoutMillis)
        socket = connected
    }

    suspend fun send(envelope: ProtocolEnvelope) = withContext(Dispatchers.IO) {
        val active = requireNotNull(socket) { "Runtime transport is not connected" }
        val frame = codec.encode(envelope)
        sendMutex.withLock {
            active.outputStream.write(frame)
            active.outputStream.flush()
        }
    }

    suspend fun receive(): ProtocolEnvelope = withContext(Dispatchers.IO) {
        val active = requireNotNull(socket) { "Runtime transport is not connected" }
        codec.readFrame(active.inputStream)
    }

    override fun close() {
        socket?.close()
        socket = null
    }
}
