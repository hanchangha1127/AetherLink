package com.localagentbridge.android.core.transport

import com.localagentbridge.android.core.protocol.ProtocolCodec
import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.net.Socket
import java.net.SocketAddress
import java.net.SocketException
import java.util.ArrayDeque
import java.util.concurrent.CancellationException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import kotlin.coroutines.CoroutineContext
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class RuntimeTransportClientTest {
    @Test
    fun sendWritesOneCompleteProtocolFrame() = runBlocking {
        val codec = ProtocolCodec()
        val envelope = ProtocolEnvelope(type = "runtime.health", requestId = "single-frame")
        val expected = codec.encode(envelope)
        val client = RuntimeTransportClient(codec = codec)
        val socket = RecordingSocket()
        client.replaceSocketForTest(socket)

        client.send(envelope)

        assertEquals(listOf(expected.size), socket.writeLengths)
        assertArrayEquals(expected, socket.bytes.toByteArray())
    }

    @Test
    fun concurrentSendsRemainSerializedAsCompleteProtocolFrames() = runBlocking {
        val codec = ProtocolCodec()
        val client = RuntimeTransportClient(codec = codec)
        val socket = RecordingSocket()
        client.replaceSocketForTest(socket)
        val expectedRequestIds = (0 until 64).map { "request-$it" }

        coroutineScope {
            expectedRequestIds.map { requestId ->
                async {
                    client.send(ProtocolEnvelope(type = "runtime.health", requestId = requestId))
                }
            }.awaitAll()
        }

        val input = ByteArrayInputStream(socket.bytes.toByteArray())
        val actualRequestIds = expectedRequestIds.indices.map {
            codec.readFrame(input).requestId
        }
        assertEquals(-1, input.read())
        assertEquals(expectedRequestIds.toSet(), actualRequestIds.toSet())
    }

    @Test
    fun partialFrameWriteFailureClosesCurrentSocketAndLeavesClientDisconnected() = runBlocking {
        val codec = ProtocolCodec()
        val client = RuntimeTransportClient()
        val socket = PartialFrameWriteFailingSocket()
        client.replaceSocketForTest(socket)
        val envelope = ProtocolEnvelope(type = "runtime.health", requestId = "partial-write-failure")
        val expectedFrameSize = codec.encode(envelope).size

        val failure = runCatching {
            client.send(envelope)
        }.exceptionOrNull()

        assertTrue(failure is IOException)
        assertTrue(socket.isClosed)
        assertTrue(socket.bytes.size() in 1 until expectedFrameSize)
        assertFalse(client.isConnected)
        client.assertNextSendFailsDisconnected()
    }

    @Test
    fun flushFailureClosesCurrentSocketAndLeavesClientDisconnected() = runBlocking {
        val codec = ProtocolCodec()
        val client = RuntimeTransportClient(codec = codec)
        val socket = FlushFailingSocket()
        client.replaceSocketForTest(socket)
        val envelope = ProtocolEnvelope(type = "runtime.health", requestId = "flush-failure")
        val expected = codec.encode(envelope)

        val failure = runCatching {
            client.send(envelope)
        }.exceptionOrNull()

        assertTrue(failure is IOException)
        assertArrayEquals(expected, socket.bytes.toByteArray())
        assertEquals(1, socket.flushCalls)
        assertTrue(socket.isClosed)
        assertFalse(client.isConnected)
        client.assertNextSendFailsDisconnected()
    }

    @Test
    fun queuedSendDoesNotCrossReconnectOnSameClientObject() = runBlocking {
        val dispatcher = QueuedDispatcher()
        val client = RuntimeTransportClient(ioDispatcher = dispatcher)
        val firstSocket = RecordingSocket()
        val replacementSocket = RecordingSocket()
        client.replaceSocketForTest(firstSocket)
        var failure: Throwable? = null

        val sendJob = launch(start = CoroutineStart.UNDISPATCHED) {
            runCatching {
                client.send(ProtocolEnvelope(type = "runtime.health"))
            }.onFailure { failure = it }
        }
        firstSocket.close()
        client.replaceSocketForTest(replacementSocket)
        dispatcher.runAll()
        sendJob.join()

        assertNotNull(failure)
        assertEquals(0, firstSocket.bytes.size())
        assertEquals(0, replacementSocket.bytes.size())
        assertTrue(client.isConnected)
        assertFalse(replacementSocket.isClosed)
    }

    @Test
    fun closeOwnsInFlightSocketAndStaleCompletionCannotPublish() = runBlocking {
        val socket = BarrierConnectSocket()
        val client = RuntimeTransportClient(ioDispatcher = Dispatchers.IO)
        client.replaceSocketFactoryForTest { socket }
        val attempt = async(start = CoroutineStart.UNDISPATCHED) {
            runCatching {
                client.connect("127.0.0.1", 43170)
            }.exceptionOrNull()
        }
        assertTrue(socket.connectStarted.await(TEST_TIMEOUT_SECONDS, TimeUnit.SECONDS))

        client.close()

        val failure = withTimeout(TEST_TIMEOUT_MILLIS) { attempt.await() }
        assertTrue(failure is CancellationException)
        assertTrue(socket.isClosed)
        assertTrue(socket.closeCalls.get() >= 1)
        assertFalse(client.isConnected)
    }

    @Test
    fun cancellationOwnsAndClosesInFlightSocketBoundedly() = runBlocking {
        val socket = BarrierConnectSocket()
        val client = RuntimeTransportClient(ioDispatcher = Dispatchers.IO)
        client.replaceSocketFactoryForTest { socket }
        val attempt = async(start = CoroutineStart.UNDISPATCHED) {
            client.connect("127.0.0.1", 43170)
        }
        assertTrue(socket.connectStarted.await(TEST_TIMEOUT_SECONDS, TimeUnit.SECONDS))

        attempt.cancel(CancellationException("connect cancelled"))

        val failure = runCatching {
            withTimeout(TEST_TIMEOUT_MILLIS) { attempt.await() }
        }.exceptionOrNull()
        assertTrue(failure is CancellationException)
        assertTrue(socket.isClosed)
        assertTrue(socket.closeCalls.get() >= 1)
        assertFalse(client.isConnected)
    }

    @Test
    fun laterConnectWinsWhenEarlierBarrierSocketCompletesStale() = runBlocking {
        val firstSocket = BarrierConnectSocket()
        val replacementSocket = ImmediateConnectSocket()
        val sockets = ArrayDeque<Socket>().apply {
            addLast(firstSocket)
            addLast(replacementSocket)
        }
        val client = RuntimeTransportClient(ioDispatcher = Dispatchers.IO)
        client.replaceSocketFactoryForTest {
            synchronized(sockets) { sockets.removeFirst() }
        }
        val firstAttempt = async(start = CoroutineStart.UNDISPATCHED) {
            runCatching {
                client.connect("127.0.0.1", 43170)
            }.exceptionOrNull()
        }
        assertTrue(firstSocket.connectStarted.await(TEST_TIMEOUT_SECONDS, TimeUnit.SECONDS))

        client.connect("127.0.0.1", 43171)

        val firstFailure = withTimeout(TEST_TIMEOUT_MILLIS) { firstAttempt.await() }
        assertTrue(firstFailure is CancellationException)
        assertTrue(firstSocket.isClosed)
        assertFalse(replacementSocket.isClosed)
        assertTrue(client.isConnected)
    }

    @Test
    fun cancellingBlockingReceiveClosesOnlyCapturedSocketAndCompletesBoundedly() = runBlocking {
        val client = RuntimeTransportClient()
        val capturedSocket = BlockingReadSocket()
        val replacementSocket = RecordingSocket()
        client.replaceSocketForTest(capturedSocket)
        val receive = async(start = CoroutineStart.UNDISPATCHED) {
            client.receive()
        }
        assertTrue(capturedSocket.readStarted.await(TEST_TIMEOUT_SECONDS, TimeUnit.SECONDS))
        client.replaceSocketForTest(replacementSocket)

        receive.cancel(CancellationException("receive cancelled"))

        val failure = runCatching {
            withTimeout(TEST_TIMEOUT_MILLIS) { receive.await() }
        }.exceptionOrNull()
        assertTrue(failure is CancellationException)
        assertTrue(capturedSocket.isClosed)
        assertFalse(replacementSocket.isClosed)
        assertTrue(client.isConnected)
    }

    private fun RuntimeTransportClient.replaceSocketForTest(socket: Socket) {
        val lockField = RuntimeTransportClient::class.java.getDeclaredField("stateLock")
        lockField.isAccessible = true
        val lock = requireNotNull(lockField.get(this))
        val socketField = RuntimeTransportClient::class.java.getDeclaredField("socket")
        socketField.isAccessible = true
        synchronized(lock) {
            socketField.set(this, socket)
        }
    }

    private fun RuntimeTransportClient.replaceSocketFactoryForTest(factory: () -> Socket) {
        val lockField = RuntimeTransportClient::class.java.getDeclaredField("stateLock")
        lockField.isAccessible = true
        val lock = requireNotNull(lockField.get(this))
        val factoryField = RuntimeTransportClient::class.java.getDeclaredField("socketFactory")
        factoryField.isAccessible = true
        synchronized(lock) {
            factoryField.set(this, factory)
        }
    }

    private suspend fun RuntimeTransportClient.assertNextSendFailsDisconnected() {
        val failure = runCatching {
            send(ProtocolEnvelope(type = "runtime.health", requestId = "after-failure"))
        }.exceptionOrNull()
        assertTrue(failure is IllegalArgumentException)
        assertEquals("Runtime transport is not connected", failure?.message)
    }

    private class QueuedDispatcher : CoroutineDispatcher() {
        private val tasks = ArrayDeque<Runnable>()

        override fun dispatch(context: CoroutineContext, block: Runnable) {
            tasks.addLast(block)
        }

        fun runAll() {
            while (tasks.isNotEmpty()) tasks.removeFirst().run()
        }
    }

    private class RecordingSocket : Socket() {
        val bytes = ByteArrayOutputStream()
        val writeLengths = mutableListOf<Int>()
        private var closed = false

        override fun isConnected(): Boolean = true

        override fun isClosed(): Boolean = closed

        override fun getOutputStream(): OutputStream = object : OutputStream() {
            override fun write(value: Int) {
                if (closed) throw SocketException("Socket is closed")
                writeLengths += 1
                bytes.write(value)
            }

            override fun write(buffer: ByteArray, offset: Int, length: Int) {
                if (closed) throw SocketException("Socket is closed")
                writeLengths += length
                bytes.write(buffer, offset, length)
            }
        }

        override fun close() {
            closed = true
        }
    }

    private class PartialFrameWriteFailingSocket : Socket() {
        val bytes = ByteArrayOutputStream()
        @Volatile
        private var closed = false

        override fun isConnected(): Boolean = true

        override fun isClosed(): Boolean = closed

        override fun getOutputStream(): OutputStream = object : OutputStream() {
            override fun write(value: Int) {
                bytes.write(value)
                throw IOException("Frame write failed after a partial write")
            }

            override fun write(buffer: ByteArray, offset: Int, length: Int) {
                val partialLength = minOf(8, length)
                bytes.write(buffer, offset, partialLength)
                throw IOException("Frame write failed after a partial write")
            }
        }

        override fun close() {
            closed = true
        }
    }

    private class FlushFailingSocket : Socket() {
        val bytes = ByteArrayOutputStream()
        var flushCalls = 0
            private set
        @Volatile
        private var closed = false

        override fun isConnected(): Boolean = true

        override fun isClosed(): Boolean = closed

        override fun getOutputStream(): OutputStream = object : OutputStream() {
            override fun write(value: Int) {
                bytes.write(value)
            }

            override fun write(buffer: ByteArray, offset: Int, length: Int) {
                bytes.write(buffer, offset, length)
            }

            override fun flush() {
                flushCalls += 1
                throw IOException("Frame flush failed")
            }
        }

        override fun close() {
            closed = true
        }
    }

    private class BarrierConnectSocket : Socket() {
        val connectStarted = CountDownLatch(1)
        val closeCalls = AtomicInteger()
        private val releaseConnect = CountDownLatch(1)
        @Volatile
        private var connected = false
        @Volatile
        private var closed = false

        override fun setTcpNoDelay(on: Boolean) = Unit

        override fun connect(endpoint: SocketAddress, timeout: Int) {
            connectStarted.countDown()
            if (!releaseConnect.await(TEST_TIMEOUT_SECONDS, TimeUnit.SECONDS)) {
                throw IOException("Timed out waiting to release fake connect")
            }
            connected = true
        }

        override fun isConnected(): Boolean = connected

        override fun isClosed(): Boolean = closed

        override fun close() {
            closeCalls.incrementAndGet()
            closed = true
            releaseConnect.countDown()
        }
    }

    private class ImmediateConnectSocket : Socket() {
        @Volatile
        private var connected = false
        @Volatile
        private var closed = false

        override fun setTcpNoDelay(on: Boolean) = Unit

        override fun connect(endpoint: SocketAddress, timeout: Int) {
            connected = true
        }

        override fun isConnected(): Boolean = connected

        override fun isClosed(): Boolean = closed

        override fun close() {
            closed = true
        }
    }

    private class BlockingReadSocket : Socket() {
        val readStarted = CountDownLatch(1)
        private val closedLatch = CountDownLatch(1)
        @Volatile
        private var closed = false

        override fun isConnected(): Boolean = true

        override fun isClosed(): Boolean = closed

        override fun getInputStream(): InputStream = object : InputStream() {
            override fun read(): Int = awaitClose()

            override fun read(buffer: ByteArray, offset: Int, length: Int): Int = awaitClose()

            private fun awaitClose(): Nothing {
                readStarted.countDown()
                if (!closedLatch.await(TEST_TIMEOUT_SECONDS, TimeUnit.SECONDS)) {
                    throw IOException("Timed out waiting for the fake socket to close")
                }
                throw SocketException("Socket is closed")
            }
        }

        override fun close() {
            closed = true
            closedLatch.countDown()
        }
    }

    private companion object {
        const val TEST_TIMEOUT_SECONDS = 2L
        const val TEST_TIMEOUT_MILLIS = 2_000L
    }
}
