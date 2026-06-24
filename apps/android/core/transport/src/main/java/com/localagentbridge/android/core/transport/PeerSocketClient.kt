package com.localagentbridge.android.core.transport

import com.localagentbridge.android.core.protocol.ProtocolCodec
import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.Closeable
import javax.net.ssl.SSLSocket
import javax.net.ssl.SSLSocketFactory

class PeerSocketClient(
    private val codec: ProtocolCodec = ProtocolCodec(),
    private val socketFactory: SSLSocketFactory = SSLSocketFactory.getDefault() as SSLSocketFactory,
) : Closeable {
    private var socket: SSLSocket? = null

    suspend fun connect(peer: DiscoveredRuntime) = withContext(Dispatchers.IO) {
        val connected = socketFactory.createSocket(peer.host, peer.port) as SSLSocket
        connected.startHandshake()
        socket = connected
    }

    suspend fun send(envelope: ProtocolEnvelope) = withContext(Dispatchers.IO) {
        val active = requireNotNull(socket) { "Socket is not connected" }
        active.outputStream.write(codec.encode(envelope))
        active.outputStream.flush()
    }

    suspend fun receive(): ProtocolEnvelope = withContext(Dispatchers.IO) {
        val active = requireNotNull(socket) { "Socket is not connected" }
        codec.readFrame(active.inputStream)
    }

    override fun close() {
        socket?.close()
        socket = null
    }
}

