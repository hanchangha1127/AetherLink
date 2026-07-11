package com.localagentbridge.android.core.transport

import com.localagentbridge.android.core.protocol.ProtocolCodec
import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.io.Closeable
import java.net.InetSocketAddress
import java.net.Socket

class RuntimeTransportClient(
    private val codec: ProtocolCodec = ProtocolCodec(),
    private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO,
) : RuntimeProtocolChannel {
    private val sendMutex = Mutex()
    private var socket: Socket? = null

    override val isConnected: Boolean
        get() = socket?.isConnected == true && socket?.isClosed == false

    suspend fun connect(host: String, port: Int, timeoutMillis: Int = 5_000): RuntimeProtocolChannel = withContext(ioDispatcher) {
        close()
        val connected = Socket()
        connected.tcpNoDelay = true
        connected.connect(InetSocketAddress(host, port), timeoutMillis)
        socket = connected
        this@RuntimeTransportClient
    }

    override suspend fun send(envelope: ProtocolEnvelope) {
        val active = requireNotNull(socket) { "Runtime transport is not connected" }
        val frame = codec.encode(envelope)
        withContext(ioDispatcher) {
            sendMutex.withLock {
                active.outputStream.write(frame)
                active.outputStream.flush()
            }
        }
    }

    override suspend fun receive(): ProtocolEnvelope {
        val active = requireNotNull(socket) { "Runtime transport is not connected" }
        return withContext(ioDispatcher) {
            codec.readFrame(active.inputStream)
        }
    }

    override fun close() {
        socket?.close()
        socket = null
    }
}
