package com.localagentbridge.android.core.pairing

import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

internal class ProductionC1AuthorityPublicationGateCapacityException(
    val maximumWaiters: Int,
) : IllegalStateException("Production C1 authority publication waiter capacity exceeded")

/**
 * Process-local, bounded FIFO publication gate. A durable authority writer blocks new secure
 * session publications, drains existing readers, commits, synchronously fences/wipes old engines,
 * and only then reopens publication.
 */
internal class ProductionC1AuthorityPublicationGate(
    private val maximumWaiters: Int = DEFAULT_MAXIMUM_WAITERS,
) {
    init {
        require(maximumWaiters > 0)
    }

    private enum class WaiterState {
        WAITING,
        GRANTED,
        CANCELLED,
    }

    private sealed class Waiter {
        val ready = CompletableDeferred<Unit>()
        var state = WaiterState.WAITING

        class Read : Waiter()
        class Write : Waiter()
    }

    private val mutex = Mutex()
    private val waiters = ArrayDeque<Waiter>()
    private val queuedWriterCount = AtomicInteger(0)
    private var activeReaders = 0
    private var writerActive = false

    internal class ReadPermit(
        private val owner: ProductionC1AuthorityPublicationGate,
    ) {
        private val released = AtomicBoolean(false)

        suspend fun release() {
            if (!released.compareAndSet(false, true)) return
            withContext(NonCancellable) { owner.releaseRead() }
        }
    }

    internal class WritePermit(
        private val owner: ProductionC1AuthorityPublicationGate,
    ) {
        private val released = AtomicBoolean(false)

        suspend fun release() {
            if (!released.compareAndSet(false, true)) return
            withContext(NonCancellable) { owner.releaseWrite() }
        }
    }

    suspend fun acquireRead(): ReadPermit {
        currentCoroutineContext().ensureActive()
        val waiter = mutex.withLock {
            if (!writerActive && waiters.isEmpty()) {
                activeReaders += 1
                null
            } else {
                enqueue(Waiter.Read())
            }
        } ?: return ReadPermit(this)

        try {
            waiter.ready.await()
            currentCoroutineContext().ensureActive()
        } catch (error: CancellationException) {
            cancelOrRollback(waiter)
            throw error
        }
        return ReadPermit(this)
    }

    suspend fun acquireWrite(): WritePermit {
        currentCoroutineContext().ensureActive()
        val waiter = mutex.withLock {
            if (!writerActive && activeReaders == 0 && waiters.isEmpty()) {
                writerActive = true
                null
            } else {
                enqueue(Waiter.Write())
            }
        } ?: return WritePermit(this)

        try {
            waiter.ready.await()
            currentCoroutineContext().ensureActive()
        } catch (error: CancellationException) {
            cancelOrRollback(waiter)
            throw error
        }
        return WritePermit(this)
    }

    suspend fun <Value> withRead(block: suspend () -> Value): Value {
        val permit = acquireRead()
        return try {
            block()
        } finally {
            permit.release()
        }
    }

    suspend fun <Value> withWrite(block: suspend () -> Value): Value {
        val permit = acquireWrite()
        return try {
            // Once a writer owns the gate, caller cancellation cannot acknowledge/reopen the
            // publication boundary before persistence classification and fail-closed fencing.
            withContext(NonCancellable) { block() }
        } finally {
            permit.release()
        }
    }

    internal fun waitingWriterCountForTesting(): Int = queuedWriterCount.get()

    internal suspend fun waitingCountForTesting(): Int = mutex.withLock { waiters.size }

    private fun <T : Waiter> enqueue(waiter: T): T {
        if (waiters.size >= maximumWaiters) {
            throw ProductionC1AuthorityPublicationGateCapacityException(maximumWaiters)
        }
        waiters.addLast(waiter)
        if (waiter is Waiter.Write) queuedWriterCount.incrementAndGet()
        return waiter
    }

    private suspend fun cancelOrRollback(waiter: Waiter) {
        withContext(NonCancellable) {
            mutex.withLock {
                when (waiter.state) {
                    WaiterState.WAITING -> {
                        check(waiters.remove(waiter))
                        if (waiter is Waiter.Write) decrementQueuedWriterCount()
                        waiter.state = WaiterState.CANCELLED
                    }
                    WaiterState.GRANTED -> {
                        when (waiter) {
                            is Waiter.Read -> {
                                check(activeReaders > 0)
                                activeReaders -= 1
                            }
                            is Waiter.Write -> {
                                check(writerActive)
                                writerActive = false
                            }
                        }
                        waiter.state = WaiterState.CANCELLED
                    }
                    WaiterState.CANCELLED -> Unit
                }
                promoteWaiters()
            }
        }
    }

    private suspend fun releaseRead() {
        mutex.withLock {
            check(activeReaders > 0)
            activeReaders -= 1
            promoteWaiters()
        }
    }

    private suspend fun releaseWrite() {
        mutex.withLock {
            check(writerActive)
            writerActive = false
            promoteWaiters()
        }
    }

    private fun promoteWaiters() {
        if (writerActive || activeReaders != 0 || waiters.isEmpty()) return

        when (val first = waiters.removeFirst()) {
            is Waiter.Write -> {
                decrementQueuedWriterCount()
                first.state = WaiterState.GRANTED
                writerActive = true
                first.ready.complete(Unit)
            }
            is Waiter.Read -> {
                grantRead(first)
                while (waiters.firstOrNull() is Waiter.Read) {
                    grantRead(waiters.removeFirst() as Waiter.Read)
                }
            }
        }
    }

    private fun grantRead(waiter: Waiter.Read) {
        waiter.state = WaiterState.GRANTED
        activeReaders += 1
        waiter.ready.complete(Unit)
    }

    private fun decrementQueuedWriterCount() {
        check(queuedWriterCount.decrementAndGet() >= 0)
    }

    private companion object {
        const val DEFAULT_MAXIMUM_WAITERS = 1_024
    }
}
