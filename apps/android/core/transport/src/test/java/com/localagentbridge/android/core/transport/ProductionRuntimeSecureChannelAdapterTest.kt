package com.localagentbridge.android.core.transport

import com.localagentbridge.android.core.pairing.ProductionC1AuthorityBoundRecordPublication
import com.localagentbridge.android.core.pairing.ProductionC1AuthorityBoundSecureSessionDescriptor
import com.localagentbridge.android.core.protocol.MessageType
import com.localagentbridge.android.core.protocol.ProtocolCodec
import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import com.localagentbridge.android.core.protocol.p2pnat.ProductionSecureSessionCryptoContract
import com.localagentbridge.android.core.protocol.p2pnat.ProductionSecureSessionRecordContentType
import java.io.IOException
import java.util.Collections
import java.util.concurrent.CancellationException
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withTimeout
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

@OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
class ProductionRuntimeSecureChannelAdapterTest {
    @Test
    fun ownedExecutionScopeIsCancelledWhenAdapterConstructionFails() {
        val raw = FakeRawFrameBodyChannel()
        val operations = FakeSecureSessionOperations().apply {
            failTerminalObserverInstall = true
        }
        lateinit var ownedJob: Job

        assertThrows(IllegalStateException::class.java) {
            ProductionRuntimeSecureChannelAdapter.createOwnedForTesting(
                rawChannel = raw,
                operations = operations,
                generation = 3L,
                onOwnedScopeCreated = { ownedJob = it },
            )
        }

        assertFalse(ownedJob.isActive)
        assertTrue(ownedJob.isCancelled)
    }

    @Test
    fun handshakeIsClientFirstObject29SendMarkReceiveAcceptActivate() = runTest {
        val raw = FakeRawFrameBodyChannel()
        val operations = FakeSecureSessionOperations()
        raw.enqueue(als1(ProductionSecureSessionCryptoContract.KEY_CONFIRMATION_OBJECT_TYPE))
        val adapter = adapter(raw, operations)
        assertEquals(null, adapter.transportSecurityContext)
        assertEquals("a".repeat(64), adapter.productionBindingId)
        assertEquals("1".repeat(32), adapter.productionSessionId)
        assertEquals(3L, adapter.productionConnectionGeneration)

        adapter.start()

        assertEquals(
            listOf("confirmation.send", "confirmation.mark", "confirmation.accept", "activate"),
            operations.events,
        )
        assertEquals(
            ProductionSecureSessionCryptoContract.KEY_CONFIRMATION_OBJECT_TYPE,
            objectType(raw.sentBodies.single()),
        )
        assertTrue(adapter.isActive)
        assertEquals("a".repeat(64), adapter.transportSecurityContext?.bindingId)
        adapter.closeAndJoin()
        assertEquals(null, adapter.transportSecurityContext)
        assertEquals(1, raw.closeCount.get())
        assertEquals(1, operations.closeCount.get())
    }

    @Test
    fun canceledExecutionScopeCannotCommitAnActiveProductionChannel() = runTest {
        val raw = FakeRawFrameBodyChannel()
        val operations = FakeSecureSessionOperations()
        raw.enqueue(als1(ProductionSecureSessionCryptoContract.KEY_CONFIRMATION_OBJECT_TYPE))
        val cancelledJob = Job().apply { cancel() }
        val adapter = ProductionRuntimeSecureChannelAdapter(
            rawChannel = raw,
            operations = operations,
            generation = 9L,
            scope = CoroutineScope(cancelledJob),
        )

        val failure = runCatching { adapter.start() }.exceptionOrNull()

        assertNotNull(failure)
        assertFalse(adapter.isConnected)
        assertEquals(1, raw.closeCount.get())
        assertEquals(1, operations.closeCount.get())
    }

    @Test
    fun explicitHandshakeCancellationIsPreservedExactly() = runTest {
        val cancellation = CancellationException("caller cancelled handshake")
        val raw = FakeRawFrameBodyChannel()
        val operations = FakeSecureSessionOperations().apply {
            confirmationCancellation = cancellation
        }
        val adapter = adapter(raw, operations)

        val failure = runCatching { adapter.start() }.exceptionOrNull()

        assertSame(cancellation, failure)
        assertEquals(1, raw.closeCount.get())
        assertEquals(1, operations.closeCount.get())
    }

    @Test
    fun timeoutWinningAfterHandshakeOutcomeCannotReturnClosedChannelAsSuccess() = runTest {
        val raw = FakeRawFrameBodyChannel()
        val operations = FakeSecureSessionOperations()
        val outcomeReady = CompletableDeferred<Unit>()
        val releaseCompletionClaim = CompletableDeferred<Unit>()
        raw.enqueue(als1(ProductionSecureSessionCryptoContract.KEY_CONFIRMATION_OBJECT_TYPE))
        val adapter = adapter(
            raw = raw,
            operations = operations,
            handshakeTimeoutMillis = 100L,
            afterDeadlineOutcomeBeforeClaim = { operation ->
                if (operation == "handshake") {
                    outcomeReady.complete(Unit)
                    releaseCompletionClaim.await()
                }
            },
        )
        val starting = async {
            runCatching { adapter.start() }.exceptionOrNull()
        }

        outcomeReady.await()
        advanceTimeBy(100L)
        runCurrent()
        assertFalse(adapter.isConnected)
        releaseCompletionClaim.complete(Unit)
        val failure = starting.await()

        assertTrue(failure is IOException)
        assertFalse(failure is CancellationException)
        assertTrue(failure?.message?.contains("handshake timed out") == true)
        assertEquals(1, raw.closeCount.get())
        assertEquals(1, operations.closeCount.get())
    }

    @Test
    fun timeoutWinnerDominatesLateHookCancellationAndError() = runTest {
        listOf<Throwable>(
            CancellationException("late hook cancellation"),
            IllegalStateException("late hook error"),
        ).forEach { loser ->
            val raw = FakeRawFrameBodyChannel()
            val operations = FakeSecureSessionOperations()
            val outcomeReady = CompletableDeferred<Unit>()
            val releaseCompletionClaim = CompletableDeferred<Unit>()
            raw.enqueue(als1(ProductionSecureSessionCryptoContract.KEY_CONFIRMATION_OBJECT_TYPE))
            val adapter = adapter(
                raw = raw,
                operations = operations,
                handshakeTimeoutMillis = 100L,
                afterDeadlineOutcomeBeforeClaim = { operation ->
                    if (operation == "handshake") {
                        outcomeReady.complete(Unit)
                        releaseCompletionClaim.await()
                        throw loser
                    }
                },
            )
            val starting = async {
                runCatching { adapter.start() }.exceptionOrNull()
            }

            outcomeReady.await()
            advanceTimeBy(100L)
            runCurrent()
            releaseCompletionClaim.complete(Unit)
            val failure = starting.await()

            assertTrue(failure is IOException)
            failure as IOException
            assertTrue(failure.message?.contains("handshake timed out") == true)
            assertSame(loser, failure.suppressed.single())
            assertEquals(1, raw.closeCount.get())
            assertEquals(1, operations.closeCount.get())
        }
    }

    @Test
    fun timeoutWinnerDominatesExternalCancellationEscapingTimeoutScope() = runTest {
        val externalCancellation = CancellationException("external timeout-race cancellation")
        lateinit var startingJob: Job
        val raw = CancellationOnCloseRawFrameBodyChannel {
            startingJob.cancel(externalCancellation)
        }
        val operations = FakeSecureSessionOperations()
        val adapter = adapter(
            raw = raw,
            operations = operations,
            handshakeTimeoutMillis = 100L,
        )
        val observed = CompletableDeferred<Throwable>()
        startingJob = launch {
            observed.complete(
                runCatching { adapter.start() }.exceptionOrNull()
                    ?: AssertionError("Timed-out handshake unexpectedly succeeded"),
            )
        }

        raw.receiveEntered.await()
        advanceTimeBy(100L)
        runCurrent()
        val failure = withTimeout(5_000) { observed.await() }

        assertTrue(failure is IOException)
        failure as IOException
        assertTrue(failure.message?.contains("handshake timed out") == true)
        assertTrue(
            failure.suppressed.singleOrNull() is CancellationException &&
                failure.suppressed.single().message == externalCancellation.message,
        )
        assertEquals(1, raw.closeCount.get())
        assertEquals(1, operations.closeCount.get())
        startingJob.join()
    }

    @Test
    fun outboundMutexPreservesFifoAndSendsRequiredKeyUpdateBeforeNextApplication() = runTest {
        val raw = FakeRawFrameBodyChannel()
        val operations = FakeSecureSessionOperations().apply {
            applicationPublications.addLast(publication(keyUpdateRequired = true))
            applicationPublications.addLast(publication())
            blockNextApplication = true
        }
        raw.enqueue(als1(ProductionSecureSessionCryptoContract.KEY_CONFIRMATION_OBJECT_TYPE))
        val adapter = adapter(raw, operations)
        adapter.start()

        val first = async { adapter.send(envelope(MessageType.RuntimeHealth, "first")) }
        operations.applicationSealEntered.await()
        val second = async { adapter.send(envelope(MessageType.Hello, "second")) }
        runCurrent()
        assertEquals(listOf("application"), operations.sealOrder)
        assertFalse(second.isCompleted)

        operations.applicationSealRelease.complete(Unit)
        first.await()
        second.await()

        assertEquals(listOf("application", "key-update", "application"), operations.sealOrder)
        assertEquals(
            listOf(29, 30, 30, 30),
            raw.sentBodies.map(::objectType),
        )
        assertEquals(listOf(1, 1, 2, 1), raw.sentBodies.map { it.last().toInt() })
        adapter.closeAndJoin()
    }

    @Test
    fun inboundKeyUpdateIsConsumedButOnlyApplicationReachesGenerationMailbox() = runTest {
        val raw = FakeRawFrameBodyChannel()
        val operations = FakeSecureSessionOperations()
        raw.enqueue(als1(29))
        val adapter = adapter(raw, operations, generation = 7L)
        adapter.start()

        operations.openPlans.addLast(
            OpenPlan(ByteArray(4), ProductionSecureSessionRecordContentType.KEY_UPDATE),
        )
        operations.openPlans.addLast(
            OpenPlan(
                ProtocolCodec().encodeBody(envelope(MessageType.RuntimeHealth, "inbound")),
                ProductionSecureSessionRecordContentType.APPLICATION,
            ),
        )
        raw.enqueue(als1(30, marker = 2))
        raw.enqueue(als1(30, marker = 1))

        val received = adapter.receive()
        assertEquals(MessageType.RuntimeHealth, received.type)
        assertEquals(listOf("KEY_UPDATE", "APPLICATION"), operations.openedContentTypes)
        assertTrue(adapter.isActive)
        adapter.closeAndJoin()
    }

    @Test
    fun nonterminalApplicationRemainsStagedUntilFacadePostPublicationFenceReturns() = runTest {
        val raw = FakeRawFrameBodyChannel()
        val operations = FakeSecureSessionOperations().apply { blockOpenAfterPublish = true }
        raw.enqueue(als1(29))
        val adapter = adapter(raw, operations)
        adapter.start()
        operations.openPlans.addLast(
            OpenPlan(
                ProtocolCodec().encodeBody(envelope(MessageType.RuntimeHealth, "post-fence-wait")),
                ProductionSecureSessionRecordContentType.APPLICATION,
            ),
        )
        val pendingReceive = async { adapter.receive() }
        raw.enqueue(als1(30))
        withTimeout(5_000) { operations.openAfterPublishEntered.await() }
        runCurrent()

        assertTrue(operations.callbackCompletedBeforeOpenReturn.get())
        assertFalse(pendingReceive.isCompleted)

        operations.openAfterPublishRelease.complete(Unit)
        assertEquals(
            "post-fence-wait",
            withTimeout(5_000) { pendingReceive.await() }.requestId,
        )
        adapter.closeAndJoin()
    }

    @Test
    fun nonterminalPostPublicationFenceFailureSuppressesPendingDeliveryWithoutHanging() = runTest {
        val raw = FakeRawFrameBodyChannel()
        val operations = FakeSecureSessionOperations().apply { failOpenAfterPublish = true }
        raw.enqueue(als1(29))
        val adapter = adapter(raw, operations)
        adapter.start()
        operations.openPlans.addLast(
            OpenPlan(
                ProtocolCodec().encodeBody(envelope(MessageType.RuntimeHealth, "post-fence-fail")),
                ProductionSecureSessionRecordContentType.APPLICATION,
            ),
        )
        val pendingReceive = async { runCatching { adapter.receive() } }
        raw.enqueue(als1(30))
        withTimeout(5_000) { operations.openAfterPublishEntered.await() }

        assertNotNull(withTimeout(5_000) { pendingReceive.await() }.exceptionOrNull())
        assertNotNull(
            withTimeout(5_000) {
                runCatching { adapter.receive() }.exceptionOrNull()
            },
        )
        assertEquals(1, operations.closeCount.get())
    }

    @Test
    fun committedNonterminalApplicationsDeliverExactlyOnceInFifoOrder() = runTest {
        val raw = FakeRawFrameBodyChannel()
        val operations = FakeSecureSessionOperations()
        raw.enqueue(als1(29))
        val adapter = adapter(raw, operations)
        adapter.start()
        operations.openPlans.addLast(
            OpenPlan(
                ProtocolCodec().encodeBody(envelope(MessageType.RuntimeHealth, "fifo-1")),
                ProductionSecureSessionRecordContentType.APPLICATION,
            ),
        )
        operations.openPlans.addLast(
            OpenPlan(
                ProtocolCodec().encodeBody(envelope(MessageType.RuntimeHealth, "fifo-2")),
                ProductionSecureSessionRecordContentType.APPLICATION,
            ),
        )
        raw.enqueue(als1(30, marker = 1))
        raw.enqueue(als1(30, marker = 2))

        val first = withTimeout(5_000) { adapter.receive() }
        val second = withTimeout(5_000) { adapter.receive() }
        assertEquals(listOf("fifo-1", "fifo-2"), listOf(first.requestId, second.requestId))

        adapter.closeAndJoin()
        assertNotNull(
            withTimeout(5_000) {
                runCatching { adapter.receive() }.exceptionOrNull()
            },
        )
    }

    @Test
    fun terminalApplicationUsesTheSamePostPublicationFenceBeforeFinalDelivery() = runTest {
        val raw = FakeRawFrameBodyChannel()
        val operations = FakeSecureSessionOperations().apply { blockOpenAfterPublish = true }
        raw.enqueue(als1(29))
        val adapter = adapter(raw, operations)
        adapter.start()
        operations.openPlans.addLast(
            OpenPlan(
                ProtocolCodec().encodeBody(envelope(MessageType.RuntimeHealth, "terminal-parity")),
                ProductionSecureSessionRecordContentType.APPLICATION,
                terminalAfterRecord = true,
            ),
        )
        val pendingReceive = async { adapter.receive() }
        raw.enqueue(als1(30))
        withTimeout(5_000) { operations.openAfterPublishEntered.await() }
        runCurrent()
        assertFalse(pendingReceive.isCompleted)

        operations.openAfterPublishRelease.complete(Unit)
        assertEquals(
            "terminal-parity",
            withTimeout(5_000) { pendingReceive.await() }.requestId,
        )
        assertNotNull(
            withTimeout(5_000) {
                runCatching { adapter.receive() }.exceptionOrNull()
            },
        )
        assertEquals(1, operations.closeCount.get())
    }

    @Test
    fun handshakeRejectsObject30AndClosesRawAndAuthorityWithoutFallback() = runTest {
        val raw = FakeRawFrameBodyChannel()
        val operations = FakeSecureSessionOperations()
        raw.enqueue(als1(ProductionSecureSessionCryptoContract.ENCRYPTED_RECORD_OBJECT_TYPE))
        val adapter = adapter(raw, operations)

        val failure = runCatching { adapter.start() }.exceptionOrNull()

        assertEquals(
            ProductionRuntimeSecureChannelFailure.INVALID_FRAME,
            (failure as? ProductionRuntimeSecureChannelException)?.failure,
        )
        assertEquals(1, raw.closeCount.get())
        assertEquals(1, operations.closeCount.get())
        assertFalse(adapter.isActive)
    }

    @Test
    fun boundedMailboxOverflowIsTerminalAndNeverPublishesPlaintextFallback() = runTest {
        val raw = FakeRawFrameBodyChannel()
        val operations = FakeSecureSessionOperations()
        raw.enqueue(als1(29))
        val adapter = adapter(raw, operations, mailboxCapacity = 1)
        adapter.start()
        repeat(2) { index ->
            operations.openPlans.addLast(
                OpenPlan(
                    ProtocolCodec().encodeBody(envelope(MessageType.RuntimeHealth, "$index")),
                    ProductionSecureSessionRecordContentType.APPLICATION,
                    terminalAfterRecord = index == 1,
                ),
            )
            raw.enqueue(als1(30, marker = index + 1))
        }

        withTimeout(5_000) { operations.closed.await() }

        assertEquals(1, raw.closeCount.get())
        assertEquals(1, operations.closeCount.get())
        assertFalse(adapter.isActive)
    }

    @Test
    fun terminalObserverClosesBlockedRawReceiveAndPumpClosesAuthority() = runTest {
        val raw = FakeRawFrameBodyChannel()
        val operations = FakeSecureSessionOperations()
        raw.enqueue(als1(29))
        val adapter = adapter(raw, operations)
        adapter.start()
        runCurrent()
        assertTrue(raw.receiveCalls.get() >= 2)
        val waitingMailbox = async { runCatching { adapter.receive() } }
        runCurrent()
        assertFalse(waitingMailbox.isCompleted)

        operations.terminalize()
        assertNotNull(waitingMailbox.await().exceptionOrNull())
        withTimeout(5_000) { operations.closed.await() }

        assertEquals(1, raw.closeCount.get())
        assertEquals(1, operations.closeCount.get())
        assertFalse(adapter.isActive)
    }

    @Test
    fun handshakeTimeoutAndCancelledOutboundBothCloseRawAndAuthority() = runTest {
        val timeoutRaw = FakeRawFrameBodyChannel()
        val timeoutOperations = FakeSecureSessionOperations()
        val timeoutAdapter = adapter(
            timeoutRaw,
            timeoutOperations,
            handshakeTimeoutMillis = 1L,
        )
        val timeoutFailure = runCatching { timeoutAdapter.start() }.exceptionOrNull()
        assertTrue(timeoutFailure is IOException)
        assertFalse(timeoutFailure is CancellationException)
        assertTrue(timeoutFailure?.message?.contains("handshake timed out") == true)
        assertEquals(1, timeoutRaw.closeCount.get())
        assertEquals(1, timeoutOperations.closeCount.get())

        val cancelRaw = FakeRawFrameBodyChannel()
        val cancelOperations = FakeSecureSessionOperations().apply {
            blockNextApplication = true
        }
        cancelRaw.enqueue(als1(29))
        val cancelAdapter = adapter(cancelRaw, cancelOperations)
        cancelAdapter.start()
        val sending = async {
            cancelAdapter.send(envelope(MessageType.RuntimeHealth, "cancel"))
        }
        cancelOperations.applicationSealEntered.await()
        sending.cancel()
        assertNotNull(runCatching { sending.await() }.exceptionOrNull())
        assertEquals(1, cancelRaw.closeCount.get())
        assertEquals(1, cancelOperations.closeCount.get())
        assertFalse(cancelAdapter.isActive)
    }

    @Test
    fun terminalAfterApplicationRecordCompletesSendThenClosesWithoutDuplicate() = runTest {
        val raw = FakeRawFrameBodyChannel()
        val operations = FakeSecureSessionOperations().apply {
            applicationPublications.addLast(publication(terminalAfterRecord = true))
        }
        raw.enqueue(als1(29))
        val adapter = adapter(raw, operations)
        adapter.start()

        adapter.send(envelope(MessageType.RuntimeHealth, "terminal"))
        withTimeout(5_000) { operations.closed.await() }

        assertEquals(listOf(29, 30), raw.sentBodies.map(::objectType))
        assertEquals(1, raw.closeCount.get())
        assertEquals(1, operations.closeCount.get())
        assertNotNull(
            runCatching {
                adapter.send(envelope(MessageType.RuntimeHealth, "must-not-retry"))
            }.exceptionOrNull(),
        )
        assertEquals(1, operations.applicationSealCount.get())
    }

    @Test
    fun inboundTerminalApplicationIsDeliveredExactlyOnceThenChannelIsClosed() = runTest {
        val raw = FakeRawFrameBodyChannel()
        val operations = FakeSecureSessionOperations()
        raw.enqueue(als1(29))
        val adapter = adapter(raw, operations, generation = 21L)
        adapter.start()
        operations.openPlans.addLast(
            OpenPlan(
                ProtocolCodec().encodeBody(envelope(MessageType.RuntimeHealth, "terminal-inbound")),
                ProductionSecureSessionRecordContentType.APPLICATION,
                terminalAfterRecord = true,
            ),
        )
        raw.enqueue(als1(30))
        withTimeout(5_000) { operations.closed.await() }
        // Explicit close/revocation after facade commit must not erase the committed final item.
        adapter.close()

        val delivered = adapter.receive()

        assertEquals("terminal-inbound", delivered.requestId)
        assertNotNull(runCatching { adapter.receive() }.exceptionOrNull())
        assertNotNull(
            runCatching { adapter.send(envelope(MessageType.Hello, "after-terminal")) }
                .exceptionOrNull(),
        )
        assertEquals(1, operations.closeCount.get())
    }

    @Test
    fun cancelledReceiveAfterTerminalCommitRestoresExactlyOneDeliveryForNextReceive() = runTest {
        val raw = FakeRawFrameBodyChannel()
        val operations = FakeSecureSessionOperations()
        val afterCommitEntered = CompletableDeferred<Unit>()
        val holdBeforeClaim = CompletableDeferred<Unit>()
        val afterCommitCalls = AtomicInteger()
        raw.enqueue(als1(29))
        val adapter = adapter(
            raw,
            operations,
            generation = 22L,
            afterTerminalCommitBeforeClaim = {
                if (afterCommitCalls.incrementAndGet() == 1) {
                    afterCommitEntered.complete(Unit)
                    holdBeforeClaim.await()
                }
            },
        )
        adapter.start()
        operations.openPlans.addLast(
            OpenPlan(
                ProtocolCodec().encodeBody(envelope(MessageType.RuntimeHealth, "terminal-race")),
                ProductionSecureSessionRecordContentType.APPLICATION,
                terminalAfterRecord = true,
            ),
        )
        val cancelledReceive = async { adapter.receive() }
        raw.enqueue(als1(30))
        withTimeout(5_000) { afterCommitEntered.await() }

        cancelledReceive.cancel()
        cancelledReceive.join()
        assertTrue(cancelledReceive.isCancelled)

        val delivered = withTimeout(5_000) { adapter.receive() }
        assertEquals("terminal-race", delivered.requestId)
        assertEquals(2, afterCommitCalls.get())
        assertNotNull(
            withTimeout(5_000) {
                runCatching { adapter.receive() }.exceptionOrNull()
            },
        )
        assertEquals(1, operations.closeCount.get())
    }

    @Test
    fun cancelledReceiveWhileTerminalIsStagedSuppressesDeliveryWithoutHanging() = runTest {
        val raw = FakeRawFrameBodyChannel()
        val operations = FakeSecureSessionOperations().apply { blockOpenAfterPublish = true }
        val afterDequeueEntered = CompletableDeferred<Unit>()
        val holdBeforeCommit = CompletableDeferred<Unit>()
        raw.enqueue(als1(29))
        val adapter = adapter(
            raw,
            operations,
            afterTerminalDequeuedBeforeCommit = {
                afterDequeueEntered.complete(Unit)
                holdBeforeCommit.await()
            },
        )
        adapter.start()
        operations.openPlans.addLast(
            OpenPlan(
                ProtocolCodec().encodeBody(envelope(MessageType.RuntimeHealth, "staged-race")),
                ProductionSecureSessionRecordContentType.APPLICATION,
                terminalAfterRecord = true,
            ),
        )
        val cancelledReceive = async { adapter.receive() }
        raw.enqueue(als1(30))
        withTimeout(5_000) { operations.openAfterPublishEntered.await() }
        withTimeout(5_000) { afterDequeueEntered.await() }

        cancelledReceive.cancel()
        cancelledReceive.join()
        assertTrue(cancelledReceive.isCancelled)

        assertNotNull(
            withTimeout(5_000) {
                runCatching { adapter.receive() }.exceptionOrNull()
            },
        )
        assertEquals(1, operations.closeCount.get())
    }

    @Test
    fun inboundTerminalKeyUpdateClosesImmediatelyAndDeliversNothing() = runTest {
        val raw = FakeRawFrameBodyChannel()
        val operations = FakeSecureSessionOperations()
        raw.enqueue(als1(29))
        val adapter = adapter(raw, operations)
        adapter.start()
        operations.openPlans.addLast(
            OpenPlan(
                ByteArray(4),
                ProductionSecureSessionRecordContentType.KEY_UPDATE,
                terminalAfterRecord = true,
            ),
        )
        raw.enqueue(als1(30, marker = 2))
        withTimeout(5_000) { operations.closed.await() }

        assertNotNull(runCatching { adapter.receive() }.exceptionOrNull())
        assertEquals(1, operations.closeCount.get())
    }

    @Test
    fun observerDuringUncommittedTerminalOpenSuppressesStagedMailboxItem() = runTest {
        val raw = FakeRawFrameBodyChannel()
        val operations = FakeSecureSessionOperations().apply {
            terminalizeAfterPublishBeforeOpenReturns = true
        }
        raw.enqueue(als1(29))
        val adapter = adapter(raw, operations)
        adapter.start()
        operations.openPlans.addLast(
            OpenPlan(
                ProtocolCodec().encodeBody(envelope(MessageType.RuntimeHealth, "uncommitted")),
                ProductionSecureSessionRecordContentType.APPLICATION,
                terminalAfterRecord = true,
            ),
        )
        raw.enqueue(als1(30))
        withTimeout(5_000) { operations.closed.await() }

        assertTrue(operations.callbackCompletedBeforeOpenReturn.get())
        assertNotNull(runCatching { adapter.receive() }.exceptionOrNull())
        assertEquals(1, operations.closeCount.get())
    }

    @Test
    fun boundedOutboundAdmissionOverflowIsTerminalWhileFifoWorkerIsBusy() = runTest {
        val raw = FakeRawFrameBodyChannel()
        val operations = FakeSecureSessionOperations().apply { blockNextApplication = true }
        raw.enqueue(als1(29))
        val adapter = adapter(raw, operations, outboundQueueCapacity = 1)
        adapter.start()
        val first = async {
            runCatching { adapter.send(envelope(MessageType.RuntimeHealth, "first")) }
        }
        operations.applicationSealEntered.await()
        val second = async { runCatching { adapter.send(envelope(MessageType.Hello, "second")) } }
        runCurrent()

        val overflow = runCatching {
            adapter.send(envelope(MessageType.ModelsList, "overflow"))
        }.exceptionOrNull()

        assertEquals(
            ProductionRuntimeSecureChannelFailure.OUTBOUND_QUEUE_FULL,
            (overflow as? ProductionRuntimeSecureChannelException)?.failure,
        )
        assertNotNull(first.await().exceptionOrNull())
        assertNotNull(second.await().exceptionOrNull())
        assertEquals(1, raw.closeCount.get())
        assertEquals(1, operations.closeCount.get())
    }

    @Test
    fun outboundDeadlineIncludesBoundedQueueWaitAndTimeoutIsTerminal() = runTest {
        val raw = FakeRawFrameBodyChannel()
        val operations = FakeSecureSessionOperations().apply { blockNextApplication = true }
        raw.enqueue(als1(29))
        val adapter = adapter(
            raw,
            operations,
            outboundQueueCapacity = 1,
            outboundTimeoutMillis = 50L,
        )
        adapter.start()
        val first = async {
            runCatching { adapter.send(envelope(MessageType.RuntimeHealth, "first")) }
        }
        operations.applicationSealEntered.await()
        val queued = async { runCatching { adapter.send(envelope(MessageType.Hello, "queued")) } }
        runCurrent()
        assertFalse(queued.isCompleted)

        advanceTimeBy(51L)
        runCurrent()

        assertNotNull(first.await().exceptionOrNull())
        assertNotNull(queued.await().exceptionOrNull())
        assertEquals(1, raw.closeCount.get())
        assertEquals(1, operations.closeCount.get())
    }

    @Test
    fun activePhaseRejectsObject29WrongMagicVersionEmptyAndOversizeObject30() = runTest {
        val malformedBodies = listOf(
            als1(29),
            als1(30).also { it[0] = 'X'.code.toByte() },
            als1(30).also { it[5] = 2 },
            ByteArray(0),
            ByteArray(ProductionSecureSessionCryptoContract.MAXIMUM_ENCRYPTED_RECORD_BYTES + 1)
                .also {
                    "ALS1".encodeToByteArray().copyInto(it)
                    it[4] = 30
                    it[5] = 1
                },
        )
        malformedBodies.forEachIndexed { index, malformed ->
            val raw = FakeRawFrameBodyChannel()
            val operations = FakeSecureSessionOperations()
            raw.enqueue(als1(29))
            val adapter = adapter(raw, operations, generation = index + 1L)
            adapter.start()

            raw.enqueue(malformed)
            withTimeout(5_000) { operations.closed.await() }

            assertEquals(1, raw.closeCount.get())
            assertEquals(1, operations.closeCount.get())
            assertFalse(adapter.isConnected)
        }
    }

    @Test
    fun encryptedWireFailureAfterCopyIsTerminalAndNeverReusesSealedSequence() = runTest {
        val raw = FakeRawFrameBodyChannel().apply { failNextEncryptedSendAfterCopy = true }
        val operations = FakeSecureSessionOperations()
        raw.enqueue(als1(29))
        val adapter = adapter(raw, operations)
        adapter.start()

        assertNotNull(
            runCatching { adapter.send(envelope(MessageType.RuntimeHealth, "first")) }
                .exceptionOrNull(),
        )
        assertEquals(1, operations.applicationSealCount.get())
        assertEquals(1, raw.copiedEncryptedBodies.get())
        assertNotNull(
            runCatching { adapter.send(envelope(MessageType.RuntimeHealth, "retry")) }
                .exceptionOrNull(),
        )
        assertEquals(1, operations.applicationSealCount.get())
        assertEquals(1, operations.closeCount.get())
    }

    @Test
    fun closeDuringOpenPublicationAndObserverDuringSealedSendDoNotDeadlock() = runTest {
        val openRaw = FakeRawFrameBodyChannel()
        val openOperations = FakeSecureSessionOperations().apply { blockOpenAfterPublish = true }
        openRaw.enqueue(als1(29))
        val openAdapter = adapter(openRaw, openOperations)
        openAdapter.start()
        openOperations.openPlans.addLast(
            OpenPlan(
                ProtocolCodec().encodeBody(envelope(MessageType.RuntimeHealth, "open")),
                ProductionSecureSessionRecordContentType.APPLICATION,
            ),
        )
        openRaw.enqueue(als1(30))
        openOperations.openAfterPublishEntered.await()
        assertTrue(openOperations.callbackCompletedBeforeOpenReturn.get())

        openAdapter.close()
        withTimeout(5_000) { openOperations.closed.await() }
        assertEquals(1, openOperations.closeCount.get())

        val sealRaw = FakeRawFrameBodyChannel().apply { blockNextEncryptedSendAfterCopy = true }
        val sealOperations = FakeSecureSessionOperations()
        sealRaw.enqueue(als1(29))
        val sealAdapter = adapter(sealRaw, sealOperations)
        sealAdapter.start()
        val sending = async {
            runCatching { sealAdapter.send(envelope(MessageType.RuntimeHealth, "seal")) }
        }
        sealRaw.encryptedSendEntered.await()

        sealOperations.terminalize()
        withTimeout(5_000) { sealOperations.closed.await() }
        assertNotNull(sending.await().exceptionOrNull())
        assertEquals(1, sealOperations.closeCount.get())
        assertEquals(1, sealRaw.closeCount.get())
    }

    @Test
    fun lateTerminalObserverAndOldGenerationCannotAffectReplacementChannel() = runTest {
        val lateRaw = FakeRawFrameBodyChannel()
        val lateOperations = FakeSecureSessionOperations().apply { terminalize() }
        val lateAdapter = adapter(lateRaw, lateOperations, generation = 11L)
        runCurrent()
        assertFalse(lateAdapter.isConnected)
        assertEquals(1, lateRaw.closeCount.get())
        assertEquals(1, lateOperations.closeCount.get())

        val replacementRaw = FakeRawFrameBodyChannel()
        val replacementOperations = FakeSecureSessionOperations()
        replacementRaw.enqueue(als1(29))
        val replacement = adapter(replacementRaw, replacementOperations, generation = 12L)
        replacement.start()
        replacementOperations.openPlans.addLast(
            OpenPlan(
                ProtocolCodec().encodeBody(envelope(MessageType.RuntimeHealth, "replacement")),
                ProductionSecureSessionRecordContentType.APPLICATION,
            ),
        )
        replacementRaw.enqueue(als1(30))

        assertEquals("replacement", replacement.receive().requestId)
        assertTrue(replacement.isConnected)
        lateOperations.terminalize()
        assertTrue(replacement.isConnected)
        replacement.closeAndJoin()
    }

    @Test
    fun descriptorExpiryTimerClosesIdleChannel() = runTest {
        var trustedNow = 0uL
        val raw = FakeRawFrameBodyChannel()
        val operations = FakeSecureSessionOperations()
        raw.enqueue(als1(29))
        val adapter = adapter(raw, operations, trustedNowMs = { trustedNow })
        adapter.start()
        trustedNow = operations.descriptor.expiresAtMs

        advanceTimeBy(operations.descriptor.expiresAtMs.toLong())
        runCurrent()
        withTimeout(5_000) { operations.closed.await() }

        assertFalse(adapter.isConnected)
        assertEquals(1, raw.closeCount.get())
        assertEquals(1, operations.closeCount.get())
    }

    private fun kotlinx.coroutines.test.TestScope.adapter(
        raw: RuntimeRawFrameBodyChannel,
        operations: FakeSecureSessionOperations,
        generation: Long = 3L,
        mailboxCapacity: Int = 4,
        outboundQueueCapacity: Int = 4,
        handshakeTimeoutMillis: Long = 5_000L,
        outboundTimeoutMillis: Long = 5_000L,
        trustedNowMs: () -> ULong = { 0uL },
        afterDeadlineOutcomeBeforeClaim: suspend (String) -> Unit = {},
        afterTerminalDequeuedBeforeCommit: suspend () -> Unit = {},
        afterTerminalCommitBeforeClaim: suspend () -> Unit = {},
    ): ProductionRuntimeSecureChannelAdapter = ProductionRuntimeSecureChannelAdapter(
        rawChannel = raw,
        operations = operations,
        generation = generation,
        scope = backgroundScope,
        mailboxCapacity = mailboxCapacity,
        outboundQueueCapacity = outboundQueueCapacity,
        handshakeTimeoutMillis = handshakeTimeoutMillis,
        outboundTimeoutMillis = outboundTimeoutMillis,
        trustedNowMs = trustedNowMs,
        afterDeadlineOutcomeBeforeClaim = afterDeadlineOutcomeBeforeClaim,
        afterTerminalDequeuedBeforeCommit = afterTerminalDequeuedBeforeCommit,
        afterTerminalCommitBeforeClaim = afterTerminalCommitBeforeClaim,
    )

    private class CancellationOnCloseRawFrameBodyChannel(
        private val onClose: () -> Unit,
    ) : RuntimeRawFrameBodyChannel {
        private val closed = AtomicBoolean(false)
        private val neverReturns = CompletableDeferred<ByteArray>()
        val receiveEntered = CompletableDeferred<Unit>()
        val closeCount = AtomicInteger()

        override val isConnected: Boolean
            get() = !closed.get()

        override suspend fun sendFrameBody(body: ByteArray) {
            check(!closed.get()) { "raw channel closed" }
        }

        override suspend fun receiveFrameBody(): ByteArray {
            receiveEntered.complete(Unit)
            return neverReturns.await()
        }

        override fun close() {
            if (!closed.compareAndSet(false, true)) return
            closeCount.incrementAndGet()
            onClose()
        }
    }

    private class FakeRawFrameBodyChannel : RuntimeRawFrameBodyChannel {
        // Models the raw seam contract required by the adapter: coroutine cancellation or close()
        // wakes a suspended send/receive immediately. Real blocking Socket.write/flush must make
        // the same guarantee by closing the underlying socket from the terminal/timeout path.
        private val incoming = Channel<ByteArray>(Channel.UNLIMITED)
        private val closed = AtomicBoolean(false)
        val sentBodies = Collections.synchronizedList(mutableListOf<ByteArray>())
        val closeCount = AtomicInteger()
        val receiveCalls = AtomicInteger()
        val copiedEncryptedBodies = AtomicInteger()
        val encryptedSendEntered = CompletableDeferred<Unit>()
        var failNextEncryptedSendAfterCopy = false
        var blockNextEncryptedSendAfterCopy = false

        override val isConnected: Boolean get() = !closed.get()

        override suspend fun sendFrameBody(body: ByteArray) {
            check(!closed.get()) { "raw channel closed" }
            sentBodies += body.copyOf()
            if (objectType(body) == 30) {
                copiedEncryptedBodies.incrementAndGet()
                if (failNextEncryptedSendAfterCopy) {
                    failNextEncryptedSendAfterCopy = false
                    throw IOException("encrypted wire send failed after copy")
                }
                if (blockNextEncryptedSendAfterCopy) {
                    blockNextEncryptedSendAfterCopy = false
                    encryptedSendEntered.complete(Unit)
                    CompletableDeferred<Unit>().await()
                }
            }
        }

        override suspend fun receiveFrameBody(): ByteArray {
            receiveCalls.incrementAndGet()
            return incoming.receive()
        }

        fun enqueue(body: ByteArray) {
            check(incoming.trySend(body.copyOf()).isSuccess)
        }

        override fun close() {
            if (!closed.compareAndSet(false, true)) return
            closeCount.incrementAndGet()
            incoming.close(IOException("raw channel closed"))
        }
    }

    private class FakeSecureSessionOperations : ProductionRuntimeSecureSessionOperations {
        override val descriptor = ProductionC1AuthorityBoundSecureSessionDescriptor(
            sessionId = "1".repeat(32),
            expiresAtMs = 100uL,
            object7Object26KdfBindingDigestHex = "a".repeat(64),
        )
        val events = Collections.synchronizedList(mutableListOf<String>())
        val sealOrder = Collections.synchronizedList(mutableListOf<String>())
        val openedContentTypes = Collections.synchronizedList(mutableListOf<String>())
        val applicationPublications = ArrayDeque<ProductionC1AuthorityBoundRecordPublication>()
        val openPlans = ArrayDeque<OpenPlan>()
        val closeCount = AtomicInteger()
        val closed = CompletableDeferred<Unit>()
        val applicationSealEntered = CompletableDeferred<Unit>()
        val applicationSealRelease = CompletableDeferred<Unit>()
        val applicationSealCount = AtomicInteger()
        val openAfterPublishEntered = CompletableDeferred<Unit>()
        val openAfterPublishRelease = CompletableDeferred<Unit>()
        val callbackCompletedBeforeOpenReturn = AtomicBoolean(false)
        var blockNextApplication = false
        var blockOpenAfterPublish = false
        var failOpenAfterPublish = false
        var terminalizeAfterPublishBeforeOpenReturns = false
        private var terminalObserver: (() -> Unit)? = null
        private val terminal = AtomicBoolean(false)
        var failTerminalObserverInstall = false
        var confirmationCancellation: CancellationException? = null

        override fun installTerminalObserver(observer: () -> Unit) {
            check(!failTerminalObserverInstall) { "terminal observer install failed" }
            check(terminalObserver == null)
            terminalObserver = observer
            if (terminal.get()) observer()
        }

        fun terminalize() {
            if (terminal.compareAndSet(false, true)) terminalObserver?.invoke()
        }

        override suspend fun sendLocalConfirmationAndMark(send: suspend (ByteArray) -> Unit) {
            confirmationCancellation?.let { throw it }
            events += "confirmation.send"
            send(als1(29))
            events += "confirmation.mark"
        }

        override suspend fun acceptPeerConfirmation(encodedConfirmation: ByteArray) {
            events += "confirmation.accept"
        }

        override suspend fun activate() {
            events += "activate"
        }

        override suspend fun sealApplicationAndSend(
            plaintext: ByteArray,
            send: suspend (ByteArray) -> Unit,
        ): ProductionC1AuthorityBoundRecordPublication {
            sealOrder += "application"
            applicationSealCount.incrementAndGet()
            if (blockNextApplication) {
                blockNextApplication = false
                applicationSealEntered.complete(Unit)
                applicationSealRelease.await()
            }
            send(als1(30, marker = 1))
            return applicationPublications.removeFirstOrNull() ?: publication()
        }

        override suspend fun sealKeyUpdateAndSend(
            send: suspend (ByteArray) -> Unit,
        ): ProductionC1AuthorityBoundRecordPublication {
            sealOrder += "key-update"
            send(als1(30, marker = 2))
            return publication()
        }

        override suspend fun <Value> openAndPublish(
            encodedRecord: ByteArray,
            publish: suspend (
                plaintext: ByteArray,
                contentType: ProductionSecureSessionRecordContentType,
                keyUpdateRequired: Boolean,
                terminalAfterRecord: Boolean,
            ) -> Value,
        ): Value {
            val plan = openPlans.removeFirst()
            openedContentTypes += plan.contentType.name
            val plaintext = plan.plaintext.copyOf()
            return try {
                val result = publish(
                    plaintext,
                    plan.contentType,
                    plan.keyUpdateRequired,
                    plan.terminalAfterRecord,
                )
                callbackCompletedBeforeOpenReturn.set(true)
                if (terminalizeAfterPublishBeforeOpenReturns) {
                    terminalizeAfterPublishBeforeOpenReturns = false
                    terminalize()
                }
                if (blockOpenAfterPublish) {
                    blockOpenAfterPublish = false
                    openAfterPublishEntered.complete(Unit)
                    openAfterPublishRelease.await()
                }
                if (failOpenAfterPublish) {
                    failOpenAfterPublish = false
                    openAfterPublishEntered.complete(Unit)
                    throw IOException("post-publication fence failed")
                }
                result
            } finally {
                plaintext.fill(0)
            }
        }

        override suspend fun close() {
            if (closeCount.incrementAndGet() == 1) closed.complete(Unit)
        }
    }

    private data class OpenPlan(
        val plaintext: ByteArray,
        val contentType: ProductionSecureSessionRecordContentType,
        val keyUpdateRequired: Boolean = false,
        val terminalAfterRecord: Boolean = false,
    )

    private companion object {
        fun publication(
            keyUpdateRequired: Boolean = false,
            terminalAfterRecord: Boolean = false,
        ) = ProductionC1AuthorityBoundRecordPublication(
            keyUpdateRequired = keyUpdateRequired,
            terminalAfterRecord = terminalAfterRecord,
        )

        fun envelope(type: String, requestId: String) = ProtocolEnvelope(
            type = type,
            requestId = requestId,
        )

        fun als1(objectType: Int, marker: Int = 1): ByteArray = byteArrayOf(
            'A'.code.toByte(),
            'L'.code.toByte(),
            'S'.code.toByte(),
            '1'.code.toByte(),
            objectType.toByte(),
            1,
            marker.toByte(),
        )

        fun objectType(body: ByteArray): Int = body[4].toInt() and 0xff
    }
}
