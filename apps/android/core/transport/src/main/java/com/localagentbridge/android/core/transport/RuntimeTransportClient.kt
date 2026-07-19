package com.localagentbridge.android.core.transport

import com.localagentbridge.android.core.protocol.ProtocolCodec
import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.net.InetSocketAddress
import java.net.Socket
import java.util.concurrent.CancellationException
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

class RuntimeTransportClient(
    private val codec: ProtocolCodec = ProtocolCodec(),
    private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO,
) : RuntimeProtocolChannel {
    private val sendMutex = Mutex()
    private val receiveMutex = Mutex()
    private val stateLock = Any()
    private var socketFactory: () -> Socket = { Socket() }
    private var generation = 0L
    private var socket: Socket? = null
    private var connectingSocket: Socket? = null

    override val isConnected: Boolean
        get() = synchronized(stateLock) {
            socket?.let { active -> active.isConnected && !active.isClosed } == true
        }

    suspend fun connect(
        host: String,
        port: Int,
        timeoutMillis: Int = 5_000,
    ): RuntimeProtocolChannel = withContext(ioDispatcher) {
        val attempt = beginConnect()
        val candidate = attempt.socket
        suspendCancellableCoroutine { continuation ->
            continuation.invokeOnCancellation {
                discardSocket(candidate)
            }

            try {
                closeSockets(attempt.displacedSockets)
                candidate.tcpNoDelay = true
                candidate.connect(InetSocketAddress(host, port), timeoutMillis)
            } catch (failure: Throwable) {
                discardSocket(candidate)
                if (continuation.isActive) continuation.resumeWithException(failure)
                return@suspendCancellableCoroutine
            }

            if (!publishConnectedSocket(attempt.generation, candidate)) {
                discardSocket(candidate)
                if (continuation.isActive) {
                    continuation.resumeWithException(
                        CancellationException("Runtime transport connect was superseded"),
                    )
                }
                return@suspendCancellableCoroutine
            }

            continuation.resume(this@RuntimeTransportClient) { _, _, _ ->
                discardSocket(candidate)
            }
        }
    }

    override suspend fun send(envelope: ProtocolEnvelope) {
        val active = requireConnectedSocket()
        val frame = codec.encode(envelope)
        withContext(ioDispatcher) {
            sendMutex.withLock {
                try {
                    active.outputStream.write(frame)
                    active.outputStream.flush()
                } catch (failure: Throwable) {
                    discardSocket(active)
                    throw failure
                }
            }
        }
    }

    override suspend fun receive(): ProtocolEnvelope {
        val active = requireConnectedSocket()
        return withContext(ioDispatcher) {
            receiveMutex.withLock {
                suspendCancellableCoroutine { continuation ->
                    continuation.invokeOnCancellation {
                        discardSocket(active)
                    }

                    val envelope = try {
                        codec.readFrame(active.inputStream)
                    } catch (failure: Throwable) {
                        if (continuation.isActive) continuation.resumeWithException(failure)
                        return@suspendCancellableCoroutine
                    }

                    continuation.resume(envelope) { _, _, _ ->
                        discardSocket(active)
                    }
                }
            }
        }
    }

    override fun close() {
        val socketsToClose = synchronized(stateLock) {
            generation += 1
            buildList {
                socket?.let(::add)
                connectingSocket?.takeIf { it !== socket }?.let(::add)
            }.also {
                socket = null
                connectingSocket = null
            }
        }
        closeSockets(socketsToClose)
    }

    private fun beginConnect(): ConnectAttempt {
        return synchronized(stateLock) {
            val candidate = socketFactory()
            generation += 1
            val displacedSockets = buildList {
                socket?.let(::add)
                connectingSocket?.takeIf { it !== socket }?.let(::add)
            }
            socket = null
            connectingSocket = candidate
            ConnectAttempt(generation, candidate, displacedSockets)
        }
    }

    private fun publishConnectedSocket(attemptGeneration: Long, candidate: Socket): Boolean {
        return synchronized(stateLock) {
            if (generation != attemptGeneration || connectingSocket !== candidate) {
                false
            } else {
                connectingSocket = null
                socket = candidate
                true
            }
        }
    }

    private fun requireConnectedSocket(): Socket {
        return synchronized(stateLock) {
            requireNotNull(socket) { "Runtime transport is not connected" }
        }
    }

    private fun discardSocket(candidate: Socket) {
        synchronized(stateLock) {
            if (socket === candidate) socket = null
            if (connectingSocket === candidate) connectingSocket = null
        }
        runCatching { candidate.close() }
    }

    private fun closeSockets(sockets: List<Socket>) {
        var firstFailure: Throwable? = null
        sockets.forEach { socketToClose ->
            try {
                socketToClose.close()
            } catch (failure: Throwable) {
                val recordedFailure = firstFailure
                if (recordedFailure == null) {
                    firstFailure = failure
                } else {
                    recordedFailure.addSuppressed(failure)
                }
            }
        }
        firstFailure?.let { throw it }
    }

    private data class ConnectAttempt(
        val generation: Long,
        val socket: Socket,
        val displacedSockets: List<Socket>,
    )
}
