package com.localagentbridge.android.core.transport

import com.localagentbridge.android.core.protocol.ProtocolCodec
import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.Semaphore
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
    maximumOutstandingSends: Int = 64,
) : RuntimeProtocolChannel {
    private val sendAdmission = Semaphore(maximumOutstandingSends.also { require(it > 0) })
    private val sendMutex = Mutex()
    private val receiveMutex = Mutex()
    private val stateLock = Any()
    private var socketFactory: () -> Socket = { Socket() }
    private var generation = 0L
    private var socket: Socket? = null
    private var connectingSocket: Socket? = null
    private var socketMode = RuntimeFrameBodyMode.ProtocolEnvelope

    override val isConnected: Boolean
        get() = synchronized(stateLock) {
            socket?.let { active -> active.isConnected && !active.isClosed } == true
        }

    override val transportSecurityContext: TransportSecurityContext?
        get() = null

    suspend fun connect(
        host: String,
        port: Int,
        timeoutMillis: Int = 5_000,
    ): RuntimeProtocolChannel {
        connectWithMode(host, port, timeoutMillis, RuntimeFrameBodyMode.ProtocolEnvelope)
        return this
    }

    suspend fun connectRaw(
        host: String,
        port: Int,
        timeoutMillis: Int = 5_000,
    ): RuntimeRawFrameBodyChannel = GenerationBoundRawFrameBodyChannel(
        this,
        connectWithMode(host, port, timeoutMillis, RuntimeFrameBodyMode.Raw),
    )

    private suspend fun connectWithMode(
        host: String,
        port: Int,
        timeoutMillis: Int,
        mode: RuntimeFrameBodyMode,
    ): ConnectedSocketState = withContext(ioDispatcher) {
        val attempt = beginConnect(mode)
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

            if (!publishConnectedSocket(attempt, candidate)) {
                discardSocket(candidate)
                if (continuation.isActive) {
                    continuation.resumeWithException(
                        CancellationException("Runtime transport connect was superseded"),
                    )
                }
                return@suspendCancellableCoroutine
            }

            val connected = ConnectedSocketState(attempt.generation, candidate, mode)
            continuation.resume(connected) { _, _, _ ->
                discardSocket(candidate)
            }
        }
    }

    override suspend fun send(envelope: ProtocolEnvelope) {
        val active = requireConnectedSocket(RuntimeFrameBodyMode.ProtocolEnvelope)
        val frame = codec.encode(envelope)
        writeFrame(active, frame)
    }

    private suspend fun writeFrame(active: Socket, frame: ByteArray) {
        if (!sendAdmission.tryAcquire()) {
            discardSocket(active)
            error("Runtime transport send backlog exceeded")
        }
        try {
            sendMutex.withLock {
                withContext(ioDispatcher) {
                    suspendCancellableCoroutine { continuation ->
                        // Java socket writes are blocking and do not observe coroutine
                        // cancellation. Register the close first so a secure-session
                        // deadline or authority fence can break a blocked write while
                        // its publication permit is still held.
                        continuation.invokeOnCancellation {
                            discardSocket(active)
                        }
                        if (!continuation.isActive) return@suspendCancellableCoroutine
                        try {
                            active.outputStream.write(frame)
                            active.outputStream.flush()
                            continuation.resume(Unit) { _, _, _ ->
                                discardSocket(active)
                            }
                        } catch (failure: Throwable) {
                            discardSocket(active)
                            if (continuation.isActive) {
                                continuation.resumeWithException(failure)
                            }
                        }
                    }
                }
            }
        } finally {
            sendAdmission.release()
        }
    }

    override suspend fun receive(): ProtocolEnvelope {
        return codec.decode(readFrameBody(RuntimeFrameBodyMode.ProtocolEnvelope))
    }

    private suspend fun sendFrameBody(
        state: ConnectedSocketState,
        body: ByteArray,
    ) {
        val active = requireConnectedSocket(state)
        val frame = try {
            codec.encodeFrameBody(body)
        } catch (failure: Throwable) {
            discardSocket(active)
            throw failure
        }
        writeFrame(active, frame)
    }

    private suspend fun receiveFrameBody(state: ConnectedSocketState): ByteArray {
        val active = requireConnectedSocket(state)
        return readFrameBody(active)
    }

    private suspend fun readFrameBody(mode: RuntimeFrameBodyMode): ByteArray {
        val active = requireConnectedSocket(mode)
        return readFrameBody(active)
    }

    private suspend fun readFrameBody(active: Socket): ByteArray {
        return withContext(ioDispatcher) {
            receiveMutex.withLock {
                suspendCancellableCoroutine { continuation ->
                    continuation.invokeOnCancellation {
                        discardSocket(active)
                    }

                    val body = try {
                        codec.readFrameBody(active.inputStream)
                    } catch (failure: Throwable) {
                        discardSocket(active)
                        if (continuation.isActive) continuation.resumeWithException(failure)
                        return@suspendCancellableCoroutine
                    }

                    continuation.resume(body) { _, _, _ ->
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

    private fun beginConnect(mode: RuntimeFrameBodyMode): ConnectAttempt {
        return synchronized(stateLock) {
            val candidate = socketFactory()
            generation += 1
            val displacedSockets = buildList {
                socket?.let(::add)
                connectingSocket?.takeIf { it !== socket }?.let(::add)
            }
            socket = null
            connectingSocket = candidate
            ConnectAttempt(generation, candidate, displacedSockets, mode)
        }
    }

    private fun publishConnectedSocket(attempt: ConnectAttempt, candidate: Socket): Boolean {
        return synchronized(stateLock) {
            if (generation != attempt.generation || connectingSocket !== candidate) {
                false
            } else {
                connectingSocket = null
                socket = candidate
                socketMode = attempt.mode
                true
            }
        }
    }

    private fun requireConnectedSocket(expectedMode: RuntimeFrameBodyMode): Socket {
        val state = synchronized(stateLock) {
            socket to socketMode
        }
        val active = requireNotNull(state.first) { "Runtime transport is not connected" }
        if (state.second != expectedMode) {
            discardSocket(active)
            error("Runtime transport frame-body mode mismatch")
        }
        return active
    }

    private fun requireConnectedSocket(state: ConnectedSocketState): Socket {
        val current = synchronized(stateLock) {
            generation == state.generation && socket === state.socket && socketMode == state.mode
        }
        check(current) { "Runtime raw frame-body handle is stale" }
        check(state.mode == RuntimeFrameBodyMode.Raw) { "Runtime raw frame-body handle mode mismatch" }
        return state.socket
    }

    private fun isConnected(state: ConnectedSocketState): Boolean = synchronized(stateLock) {
        generation == state.generation && socket === state.socket && socketMode == state.mode &&
            state.socket.isConnected && !state.socket.isClosed
    }

    private fun close(state: ConnectedSocketState) {
        val shouldClose = synchronized(stateLock) {
            if (generation == state.generation && socket === state.socket) {
                generation += 1
                socket = null
                true
            } else {
                false
            }
        }
        if (shouldClose) runCatching { state.socket.close() }
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
        val mode: RuntimeFrameBodyMode,
    )

    private data class ConnectedSocketState(
        val generation: Long,
        val socket: Socket,
        val mode: RuntimeFrameBodyMode,
    )

    private class GenerationBoundRawFrameBodyChannel(
        private val owner: RuntimeTransportClient,
        private val state: ConnectedSocketState,
    ) : RuntimeRawFrameBodyChannel {
        override val isConnected: Boolean
            get() = owner.isConnected(state)

        override val transportSecurityContext: TransportSecurityContext?
            get() = null

        override suspend fun sendFrameBody(body: ByteArray) = owner.sendFrameBody(state, body)

        override suspend fun receiveFrameBody(): ByteArray = owner.receiveFrameBody(state)

        override fun close() = owner.close(state)
    }
}
