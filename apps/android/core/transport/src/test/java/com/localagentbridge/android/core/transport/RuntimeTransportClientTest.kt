package com.localagentbridge.android.core.transport

import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import java.io.ByteArrayOutputStream
import java.io.OutputStream
import java.net.Socket
import java.net.SocketException
import java.util.ArrayDeque
import kotlin.coroutines.CoroutineContext
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test

class RuntimeTransportClientTest {
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
        private var closed = false

        override fun isConnected(): Boolean = true

        override fun isClosed(): Boolean = closed

        override fun getOutputStream(): OutputStream = object : OutputStream() {
            override fun write(value: Int) {
                if (closed) throw SocketException("Socket is closed")
                bytes.write(value)
            }

            override fun write(buffer: ByteArray, offset: Int, length: Int) {
                if (closed) throw SocketException("Socket is closed")
                bytes.write(buffer, offset, length)
            }
        }

        override fun close() {
            closed = true
        }
    }
}
