package com.localagentbridge.android.core.transport

import com.localagentbridge.android.core.protocol.ProtocolCodec
import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import javax.net.ssl.SSLSocket
import javax.net.ssl.SSLSocketFactory

class PeerSocketClient(
    private val codec: ProtocolCodec = ProtocolCodec(),
    private val socketFactory: SSLSocketFactory = SSLSocketFactory.getDefault() as SSLSocketFactory,
) : RuntimeProtocolChannel {
    private var socket: SSLSocket? = null

    override val isConnected: Boolean
        get() = socket?.isConnected == true && socket?.isClosed == false

    suspend fun connect(peer: DiscoveredRuntime): RuntimeProtocolChannel = withContext(Dispatchers.IO) {
        val connected = socketFactory.createSocket(peer.host, peer.port) as SSLSocket
        connected.startHandshake()
        socket = connected
        this@PeerSocketClient
    }

    override suspend fun send(envelope: ProtocolEnvelope) = withContext(Dispatchers.IO) {
        val active = requireNotNull(socket) { "Socket is not connected" }
        active.outputStream.write(codec.encode(envelope))
        active.outputStream.flush()
    }

    override suspend fun receive(): ProtocolEnvelope = withContext(Dispatchers.IO) {
        val active = requireNotNull(socket) { "Socket is not connected" }
        codec.readFrame(active.inputStream)
    }

    override fun close() {
        socket?.close()
        socket = null
    }
}
