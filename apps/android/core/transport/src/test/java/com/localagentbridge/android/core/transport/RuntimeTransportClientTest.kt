package com.localagentbridge.android.core.transport

import com.localagentbridge.android.core.protocol.ProtocolCodec
import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.io.OutputStream
import java.net.Socket
import java.net.SocketException
import java.util.ArrayDeque
import kotlin.coroutines.CoroutineContext
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
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
    fun frameWriteFailurePropagatesWithoutClosingDirectSocketOrWritingAPrefix() = runBlocking {
        val client = RuntimeTransportClient()
        val socket = FrameWriteFailingSocket()
        client.replaceSocketForTest(socket)

        val failure = runCatching {
            client.send(ProtocolEnvelope(type = "runtime.health", requestId = "write-failure"))
        }.exceptionOrNull()

        assertTrue(failure is IOException)
        assertFalse(socket.isClosed)
        assertEquals(1, socket.attemptedWriteLengths.size)
        assertTrue(socket.attemptedWriteLengths.single() > 4)
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
    }

    private fun RuntimeTransportClient.replaceSocketForTest(socket: Socket) {
        val field = RuntimeTransportClient::class.java.getDeclaredField("socket")
        field.isAccessible = true
        field.set(this, socket)
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

    private class FrameWriteFailingSocket : Socket() {
        val attemptedWriteLengths = mutableListOf<Int>()
        private var closed = false

        override fun isConnected(): Boolean = true

        override fun isClosed(): Boolean = closed

        override fun getOutputStream(): OutputStream = object : OutputStream() {
            override fun write(value: Int) {
                throw IOException("Unexpected single-byte write")
            }

            override fun write(buffer: ByteArray, offset: Int, length: Int) {
                attemptedWriteLengths += length
                throw IOException("Frame write failed")
            }
        }

        override fun close() {
            closed = true
        }
    }
}
