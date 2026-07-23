package com.localagentbridge.android.core.transport

import com.localagentbridge.android.core.pairing.ProductionC1AuthorityBoundRecordPublication
import com.localagentbridge.android.core.pairing.ProductionC1AuthorityBoundSecureSessionDescriptor
import com.localagentbridge.android.core.pairing.ProductionC1AuthorityBoundSecureSessionCapability
import com.localagentbridge.android.core.protocol.ProtocolCodec
import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import com.localagentbridge.android.core.protocol.p2pnat.ProductionSecureSessionCryptoContract
import com.localagentbridge.android.core.protocol.p2pnat.ProductionSecureSessionRecordContentType
import java.io.IOException
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull

internal enum class ProductionRuntimeSecureChannelFailure {
    INVALID_PHASE,
    INVALID_FRAME,
    STALE_GENERATION,
    MAILBOX_FULL,
    OUTBOUND_QUEUE_FULL,
    TERMINAL_RECORD,
}

internal class ProductionRuntimeSecureChannelException(
    val failure: ProductionRuntimeSecureChannelFailure,
) : IOException("Production runtime secure channel failed: $failure")

/** Testable authority facade; production construction wraps the public pairing capability. */
internal interface ProductionRuntimeSecureSessionOperations {
    val descriptor: ProductionC1AuthorityBoundSecureSessionDescriptor

    fun installTerminalObserver(observer: () -> Unit)

    suspend fun sendLocalConfirmationAndMark(send: suspend (ByteArray) -> Unit)

    suspend fun acceptPeerConfirmation(encodedConfirmation: ByteArray)

    suspend fun activate()

    suspend fun sealApplicationAndSend(
        plaintext: ByteArray,
        send: suspend (ByteArray) -> Unit,
    ): ProductionC1AuthorityBoundRecordPublication

    suspend fun sealKeyUpdateAndSend(
        send: suspend (ByteArray) -> Unit,
    ): ProductionC1AuthorityBoundRecordPublication

    suspend fun <Value> openAndPublish(
        encodedRecord: ByteArray,
        publish: suspend (
            plaintext: ByteArray,
            contentType: ProductionSecureSessionRecordContentType,
            keyUpdateRequired: Boolean,
            terminalAfterRecord: Boolean,
        ) -> Value,
    ): Value

    suspend fun close()
}

private class PairingProductionRuntimeSecureSessionOperations(
    private val capability: ProductionC1AuthorityBoundSecureSessionCapability,
) : ProductionRuntimeSecureSessionOperations {
    override val descriptor: ProductionC1AuthorityBoundSecureSessionDescriptor
        get() = capability.descriptor

    override fun installTerminalObserver(observer: () -> Unit) =
        capability.installTerminalObserver(observer)

    override suspend fun sendLocalConfirmationAndMark(send: suspend (ByteArray) -> Unit) =
        capability.sendLocalConfirmationAndMark(send)

    override suspend fun acceptPeerConfirmation(encodedConfirmation: ByteArray) =
        capability.acceptPeerConfirmation(encodedConfirmation)

    override suspend fun activate() = capability.activate()

    override suspend fun sealApplicationAndSend(
        plaintext: ByteArray,
        send: suspend (ByteArray) -> Unit,
    ): ProductionC1AuthorityBoundRecordPublication =
        capability.sealApplicationAndSend(plaintext, send)

    override suspend fun sealKeyUpdateAndSend(
        send: suspend (ByteArray) -> Unit,
    ): ProductionC1AuthorityBoundRecordPublication = capability.sealKeyUpdateAndSend(send)

    override suspend fun <Value> openAndPublish(
        encodedRecord: ByteArray,
        publish: suspend (
            plaintext: ByteArray,
            contentType: ProductionSecureSessionRecordContentType,
            keyUpdateRequired: Boolean,
            terminalAfterRecord: Boolean,
        ) -> Value,
    ): Value = capability.openAndPublish(encodedRecord, publish)

    override suspend fun close() {
        capability.close()
    }
}

/**
 * Production object-29/object-30 adapter over an already connected raw frame-body channel.
 * RuntimeClientViewModel can wire this only through its optional production graph: one verified
 * renewable activation slot, the exact PairingStore owned by the trusted store, and one raw
 * connector must all be installed together. The default app graph remains fail-closed and leaves
 * it unwired.
 *
 * RuntimeRawFrameBodyChannel is required to make close() synchronously wake an in-flight
 * sendFrameBody/receiveFrameBody. The terminal observer closes it synchronously; production
 * activation therefore also depends on the direct/relay socket implementations honoring that
 * cancellation boundary for blocking write/flush calls.
 */
internal class ProductionRuntimeSecureChannelAdapter private constructor(
    private val rawChannel: RuntimeRawFrameBodyChannel,
    private val operations: ProductionRuntimeSecureSessionOperations,
    val generation: Long,
    private val scope: CoroutineScope,
    private val ownedScopeJob: Job?,
    private val codec: ProtocolCodec,
    mailboxCapacity: Int,
    outboundQueueCapacity: Int,
    private val handshakeTimeoutMillis: Long,
    private val outboundTimeoutMillis: Long,
    private val trustedNowMs: () -> ULong,
    private val afterDeadlineOutcomeBeforeClaim: suspend (String) -> Unit,
    private val afterTerminalDequeuedBeforeCommit: suspend () -> Unit,
    private val afterTerminalCommitBeforeClaim: suspend () -> Unit,
) : RuntimeProductionProtocolChannel {
    private enum class Phase {
        NEW,
        CONFIRMATION_SENT,
        ACTIVE,
        TERMINAL_DRAIN,
        CLOSED,
    }

    private enum class InboundApplicationPublicationState {
        STAGED,
        COMMITTED,
        CLAIMED,
        SUPPRESSED,
    }

    private enum class TerminalDeadlineState {
        PENDING,
        COMPLETED,
        TIMED_OUT,
    }

    private class InboundApplicationPublication(
        val terminalAfterDelivery: Boolean,
    ) {
        val commit = CompletableDeferred<Boolean>()
        var state = InboundApplicationPublicationState.STAGED
        var dequeueOwner: Any? = null
    }

    private data class GenerationBoundEnvelope(
        val generation: Long,
        val envelope: ProtocolEnvelope,
        val publication: InboundApplicationPublication,
    )

    private data class InboundPublication(
        val terminalAfterRecord: Boolean,
        val applicationItem: GenerationBoundEnvelope? = null,
    )

    private data class OutboundPublication(
        val terminalAfterSuccessfulApplication: Boolean,
    )

    private data class OutboundRequest(
        val envelope: ProtocolEnvelope,
        val completion: CompletableDeferred<Result<Unit>> = CompletableDeferred(),
    )

    private val startMutex = Mutex()
    private val terminalStateLock = Any()
    private val terminated = AtomicBoolean(false)
    private val authorityCloseStarted = AtomicBoolean(false)
    private val authorityCloseCompletion = CompletableDeferred<Result<Unit>>()
    private val mailbox = Channel<GenerationBoundEnvelope>(mailboxCapacity)
    private val outboundRequests = Channel<OutboundRequest>(outboundQueueCapacity)
    @Volatile private var phase = Phase.NEW
    @Volatile private var keyUpdateRequiredBeforeApplication = false
    @Volatile private var inboundJob: Job? = null
    @Volatile private var outboundJob: Job? = null
    @Volatile private var expiryJob: Job? = null
    private var stagedApplicationItem: GenerationBoundEnvelope? = null
    private var terminalApplicationItem: GenerationBoundEnvelope? = null

    init {
        require(generation > 0) { "Production secure-channel generation must be positive" }
        require(mailboxCapacity > 0) { "Production secure-channel mailbox must be bounded" }
        require(outboundQueueCapacity > 0) { "Production outbound queue must be bounded" }
        require(handshakeTimeoutMillis > 0)
        require(outboundTimeoutMillis > 0)
        operations.installTerminalObserver {
            // Pairing invokes this synchronously. First wake every waiter without suspension, then
            // finish the authority close exactly once on the supplied dispatcher without reentry.
            if (signalTerminal(IOException("Production authority terminated"))) {
                scheduleAuthorityClose()
            }
        }
    }

    internal constructor(
        rawChannel: RuntimeRawFrameBodyChannel,
        operations: ProductionRuntimeSecureSessionOperations,
        generation: Long,
        scope: CoroutineScope,
        codec: ProtocolCodec = ProtocolCodec(),
        mailboxCapacity: Int = DEFAULT_MAILBOX_CAPACITY,
        outboundQueueCapacity: Int = DEFAULT_OUTBOUND_QUEUE_CAPACITY,
        handshakeTimeoutMillis: Long = DEFAULT_HANDSHAKE_TIMEOUT_MILLIS,
        outboundTimeoutMillis: Long = DEFAULT_OUTBOUND_TIMEOUT_MILLIS,
        trustedNowMs: () -> ULong = SYSTEM_TRUSTED_NOW_MS,
        afterDeadlineOutcomeBeforeClaim: suspend (String) -> Unit = {},
        afterTerminalDequeuedBeforeCommit: suspend () -> Unit = {},
        afterTerminalCommitBeforeClaim: suspend () -> Unit = {},
        @Suppress("UNUSED_PARAMETER") testing: Unit = Unit,
    ) : this(
        rawChannel,
        operations,
        generation,
        scope,
        null,
        codec,
        mailboxCapacity,
        outboundQueueCapacity,
        handshakeTimeoutMillis,
        outboundTimeoutMillis,
        trustedNowMs,
        afterDeadlineOutcomeBeforeClaim,
        afterTerminalDequeuedBeforeCommit,
        afterTerminalCommitBeforeClaim,
    )

    val isActive: Boolean
        get() = phase == Phase.ACTIVE && !terminated.get() && rawChannel.isConnected

    override val isConnected: Boolean
        get() = isActive

    override val productionBindingId: String
        get() = operations.descriptor.object7Object26KdfBindingDigestHex

    override val productionSessionId: String
        get() = operations.descriptor.sessionId

    override val productionConnectionGeneration: Long
        get() = generation

    override val transportSecurityContext: TransportSecurityContext?
        get() = if (isActive) {
            TransportSecurityContext(
                bindingId = productionBindingId,
            )
        } else {
            null
        }

    suspend fun start() = startMutex.withLock {
        failClosed {
            requirePhase(Phase.NEW)
            withTerminalDeadline(handshakeTimeoutMillis, "handshake") {
                operations.sendLocalConfirmationAndMark { encodedConfirmation ->
                    requireAls1Object(
                        encodedConfirmation,
                        ProductionSecureSessionCryptoContract.KEY_CONFIRMATION_OBJECT_TYPE,
                        ProductionSecureSessionCryptoContract.MAXIMUM_KEY_CONFIRMATION_BYTES,
                    )
                    rawChannel.sendFrameBody(encodedConfirmation)
                }
                phase = Phase.CONFIRMATION_SENT

                // Raw receive intentionally happens outside any pairing publication permit.
                val peerConfirmation = rawChannel.receiveFrameBody()
                try {
                    requireAls1Object(
                        peerConfirmation,
                        ProductionSecureSessionCryptoContract.KEY_CONFIRMATION_OBJECT_TYPE,
                        ProductionSecureSessionCryptoContract.MAXIMUM_KEY_CONFIRMATION_BYTES,
                    )
                    operations.acceptPeerConfirmation(peerConfirmation)
                } finally {
                    peerConfirmation.fill(0)
                }
                operations.activate()
                currentCoroutineContext().ensureActive()
                check(scope.coroutineContext[Job]?.isActive != false) {
                    "Production channel execution scope is not active"
                }
                phase = Phase.ACTIVE
                outboundJob = scope.launch { runOutboundPump() }
                inboundJob = scope.launch { runInboundPump() }
                expiryJob = scope.launch { runExpiryTimer() }
                check(
                    listOfNotNull(outboundJob, inboundJob, expiryJob).all(Job::isActive),
                ) { "Production channel execution jobs did not start" }
            }
        }
    }

    override suspend fun send(envelope: ProtocolEnvelope) = failClosed {
        withTerminalDeadline(outboundTimeoutMillis, "outbound publication") {
            requirePhase(Phase.ACTIVE)
            val request = OutboundRequest(envelope)
            if (outboundRequests.trySend(request).isFailure) {
                secureChannelFail(ProductionRuntimeSecureChannelFailure.OUTBOUND_QUEUE_FULL)
            }
            request.completion.await().getOrThrow()
        }
    }

    override suspend fun receive(): ProtocolEnvelope = failClosed {
        val dequeueOwner = Any()
        var applicationItem: GenerationBoundEnvelope? = null
        try {
            if (phase != Phase.ACTIVE && phase != Phase.TERMINAL_DRAIN) {
                secureChannelFail(ProductionRuntimeSecureChannelFailure.INVALID_PHASE)
            }
            val item = mailbox.receive()
            if (!registerApplicationDequeue(item, dequeueOwner)) {
                secureChannelFail(ProductionRuntimeSecureChannelFailure.STALE_GENERATION)
            }
            applicationItem = item
            if (item.publication.terminalAfterDelivery) {
                afterTerminalDequeuedBeforeCommit()
            }
            if (item.generation != generation) {
                secureChannelFail(ProductionRuntimeSecureChannelFailure.STALE_GENERATION)
            }
            val committed = item.publication.commit.await()
            if (!committed) {
                secureChannelFail(ProductionRuntimeSecureChannelFailure.STALE_GENERATION)
            }
            if (item.publication.terminalAfterDelivery) {
                afterTerminalCommitBeforeClaim()
            }
            if (!claimApplication(item, dequeueOwner)) {
                secureChannelFail(ProductionRuntimeSecureChannelFailure.STALE_GENERATION)
            }
            applicationItem = null
            if (item.publication.terminalAfterDelivery) completeTerminalApplicationDelivery(item)
            item.envelope
        } catch (error: Throwable) {
            applicationItem?.let { item ->
                try {
                    releaseApplicationDequeueAfterFailure(item, dequeueOwner)
                } catch (recoveryError: Throwable) {
                    error.addSuppressed(recoveryError)
                }
            }
            throw error
        }
    }

    override fun close() {
        if (signalTerminal(IOException("Production runtime secure channel closed"))) {
            scheduleAuthorityClose()
        }
    }

    internal suspend fun closeAndJoin() {
        signalTerminal(IOException("Production runtime secure channel closed"))
        closeAuthorityOnce()
    }

    private suspend fun runOutboundPump() {
        try {
            for (request in outboundRequests) {
                val result = runCatching { performOutboundSend(request.envelope) }
                request.completion.complete(result.map { Unit })
                result.exceptionOrNull()?.let { throw it }
                if (result.getOrThrow().terminalAfterSuccessfulApplication) {
                    val terminal = IOException(
                        "Production secure-session sent its final application record",
                    )
                    if (signalTerminal(terminal)) scheduleAuthorityClose()
                    return
                }
            }
        } catch (error: Throwable) {
            terminate(error)
        }
    }

    private suspend fun performOutboundSend(envelope: ProtocolEnvelope): OutboundPublication {
        requirePhase(Phase.ACTIVE)
        if (keyUpdateRequiredBeforeApplication) {
            val update = operations.sealKeyUpdateAndSend(::sendEncryptedRecord)
            check(!update.keyUpdateRequired) {
                "Production key-update record requested another key update"
            }
            keyUpdateRequiredBeforeApplication = false
            // A terminal key-update has no following application delivery to complete.
            requireNonTerminal(update)
        }

        val plaintext = codec.encodeBody(envelope)
        try {
            if (plaintext.size !in
                1..ProductionSecureSessionCryptoContract.MAXIMUM_PLAINTEXT_BYTES
            ) {
                secureChannelFail(ProductionRuntimeSecureChannelFailure.INVALID_FRAME)
            }
            val publication = operations.sealApplicationAndSend(
                plaintext,
                ::sendEncryptedRecord,
            )
            keyUpdateRequiredBeforeApplication = publication.keyUpdateRequired
            return OutboundPublication(
                terminalAfterSuccessfulApplication = publication.terminalAfterRecord,
            )
        } finally {
            plaintext.fill(0)
        }
    }

    private suspend fun runInboundPump() {
        try {
            while (phase == Phase.ACTIVE && !terminated.get()) {
                // The potentially blocking socket read owns no pairing authority permit.
                val encodedRecord = rawChannel.receiveFrameBody()
                var stagedItem: GenerationBoundEnvelope? = null
                val publication = try {
                    requireAls1Object(
                        encodedRecord,
                        ProductionSecureSessionCryptoContract.ENCRYPTED_RECORD_OBJECT_TYPE,
                        ProductionSecureSessionCryptoContract.MAXIMUM_ENCRYPTED_RECORD_BYTES,
                    )
                    try {
                        operations.openAndPublish(encodedRecord) {
                                plaintext,
                                contentType,
                                _,
                                terminal,
                            ->
                            when (contentType) {
                                ProductionSecureSessionRecordContentType.APPLICATION -> {
                                    if (phase != Phase.ACTIVE || terminated.get()) {
                                        secureChannelFail(
                                            ProductionRuntimeSecureChannelFailure.STALE_GENERATION,
                                        )
                                    }
                                    val envelope = codec.decode(plaintext)
                                    val item = stageApplication(envelope, terminal)
                                    stagedItem = item
                                    InboundPublication(
                                        terminalAfterRecord = terminal,
                                        applicationItem = item,
                                    )
                                }
                                ProductionSecureSessionRecordContentType.KEY_UPDATE ->
                                    InboundPublication(terminalAfterRecord = terminal)
                            }
                        }
                    } catch (error: Throwable) {
                        stagedItem?.let(::suppressStagedApplication)
                        throw error
                    }
                } finally {
                    encodedRecord.fill(0)
                }
                val applicationItem = publication.applicationItem
                if (applicationItem != null) {
                    if (!commitApplication(applicationItem)) {
                        secureChannelFail(ProductionRuntimeSecureChannelFailure.STALE_GENERATION)
                    }
                    if (applicationItem.publication.terminalAfterDelivery) {
                        val terminal = IOException(
                            "Production secure-session received its final application record",
                        )
                        if (signalTerminal(terminal)) scheduleAuthorityClose()
                        return
                    }
                }
                if (publication.terminalAfterRecord) {
                    val terminal = IOException(
                        "Production secure-session received a terminal key-update record",
                    )
                    if (signalTerminal(terminal)) scheduleAuthorityClose()
                    return
                }
            }
        } catch (error: Throwable) {
            terminate(error)
        }
    }

    private suspend fun runExpiryTimer() {
        try {
            while (phase == Phase.ACTIVE && !terminated.get()) {
                val nowMs = trustedNowMs()
                val expiresAtMs = operations.descriptor.expiresAtMs
                if (nowMs >= expiresAtMs) {
                    val failure = IOException("Production secure-session descriptor expired")
                    if (signalTerminal(failure)) {
                        scheduleAuthorityClose()
                    }
                    return
                }
                val remaining = expiresAtMs - nowMs
                delay(remaining.coerceAtMost(Long.MAX_VALUE.toULong()).toLong())
            }
        } catch (_: CancellationException) {
            // Normal terminal shutdown cancels the idle expiry timer.
        } catch (error: Throwable) {
            terminate(error)
        }
    }

    private suspend fun sendEncryptedRecord(encodedRecord: ByteArray) {
        requireAls1Object(
            encodedRecord,
            ProductionSecureSessionCryptoContract.ENCRYPTED_RECORD_OBJECT_TYPE,
            ProductionSecureSessionCryptoContract.MAXIMUM_ENCRYPTED_RECORD_BYTES,
        )
        rawChannel.sendFrameBody(encodedRecord)
    }

    private fun stageApplication(
        envelope: ProtocolEnvelope,
        terminalAfterDelivery: Boolean,
    ): GenerationBoundEnvelope = synchronized(terminalStateLock) {
        if (phase != Phase.ACTIVE || terminated.get() ||
            stagedApplicationItem != null ||
            (terminalAfterDelivery && terminalApplicationItem != null)
        ) {
            secureChannelFail(ProductionRuntimeSecureChannelFailure.STALE_GENERATION)
        }
        val item = GenerationBoundEnvelope(
            generation = generation,
            envelope = envelope,
            publication = InboundApplicationPublication(terminalAfterDelivery),
        )
        if (mailbox.trySend(item).isFailure) {
            secureChannelFail(ProductionRuntimeSecureChannelFailure.MAILBOX_FULL)
        }
        stagedApplicationItem = item
        if (terminalAfterDelivery) terminalApplicationItem = item
        item
    }

    private fun commitApplication(item: GenerationBoundEnvelope): Boolean {
        val committed = synchronized(terminalStateLock) {
            if (stagedApplicationItem === item &&
                item.publication.state == InboundApplicationPublicationState.STAGED &&
                phase == Phase.ACTIVE &&
                !terminated.get()
            ) {
                stagedApplicationItem = null
                item.publication.state = InboundApplicationPublicationState.COMMITTED
                if (item.publication.terminalAfterDelivery) phase = Phase.TERMINAL_DRAIN
                true
            } else {
                false
            }
        }
        item.publication.commit.complete(committed)
        return committed
    }

    private fun suppressStagedApplication(item: GenerationBoundEnvelope): Boolean {
        val suppressed = synchronized(terminalStateLock) {
            if (stagedApplicationItem !== item ||
                item.publication.state != InboundApplicationPublicationState.STAGED
            ) {
                false
            } else {
                stagedApplicationItem = null
                item.publication.state = InboundApplicationPublicationState.SUPPRESSED
                if (terminalApplicationItem === item) terminalApplicationItem = null
                true
            }
        }
        if (suppressed) item.publication.commit.complete(false)
        return suppressed
    }

    private fun registerApplicationDequeue(
        item: GenerationBoundEnvelope,
        owner: Any,
    ): Boolean = synchronized(terminalStateLock) {
        if (item.publication.dequeueOwner != null ||
            item.publication.state !in setOf(
                InboundApplicationPublicationState.STAGED,
                InboundApplicationPublicationState.COMMITTED,
            )
        ) {
            false
        } else {
            item.publication.dequeueOwner = owner
            true
        }
    }

    private fun claimApplication(
        item: GenerationBoundEnvelope,
        owner: Any,
    ): Boolean =
        synchronized(terminalStateLock) {
            val phaseAllowsClaim = if (item.publication.terminalAfterDelivery) {
                terminalApplicationItem === item && phase == Phase.TERMINAL_DRAIN
            } else {
                phase == Phase.ACTIVE && !terminated.get()
            }
            if (item.publication.dequeueOwner !== owner ||
                item.publication.state != InboundApplicationPublicationState.COMMITTED ||
                !phaseAllowsClaim
            ) {
                false
            } else {
                item.publication.dequeueOwner = null
                item.publication.state = InboundApplicationPublicationState.CLAIMED
                true
            }
        }

    private fun releaseApplicationDequeueAfterFailure(
        item: GenerationBoundEnvelope,
        owner: Any,
    ) {
        var suppressCommit: CompletableDeferred<Boolean>? = null
        synchronized(terminalStateLock) {
            if (item.publication.dequeueOwner !== owner) {
                return
            }
            item.publication.dequeueOwner = null
            when (item.publication.state) {
                InboundApplicationPublicationState.STAGED -> {
                    item.publication.state = InboundApplicationPublicationState.SUPPRESSED
                    if (stagedApplicationItem === item) stagedApplicationItem = null
                    if (terminalApplicationItem === item) terminalApplicationItem = null
                    suppressCommit = item.publication.commit
                }
                InboundApplicationPublicationState.COMMITTED -> {
                    if (item.publication.terminalAfterDelivery) {
                        check(mailbox.trySend(item).isSuccess) {
                            "Committed production terminal application could not be restored"
                        }
                    } else {
                        item.publication.state = InboundApplicationPublicationState.SUPPRESSED
                    }
                }
                InboundApplicationPublicationState.CLAIMED,
                InboundApplicationPublicationState.SUPPRESSED,
                -> Unit
            }
        }
        suppressCommit?.complete(false)
    }

    private fun completeTerminalApplicationDelivery(item: GenerationBoundEnvelope) {
        val terminal = IOException("Production terminal application was delivered")
        if (signalTerminal(terminal)) scheduleAuthorityClose()
        synchronized(terminalStateLock) {
            check(terminalApplicationItem === item)
            check(item.publication.state == InboundApplicationPublicationState.CLAIMED)
            check(item.publication.dequeueOwner == null)
            phase = Phase.CLOSED
            mailbox.close(terminal)
            terminalApplicationItem = null
        }
    }

    private fun requireNonTerminal(publication: ProductionC1AuthorityBoundRecordPublication) {
        if (publication.terminalAfterRecord) {
            secureChannelFail(ProductionRuntimeSecureChannelFailure.TERMINAL_RECORD)
        }
    }

    private fun requirePhase(expected: Phase) {
        if (phase != expected || terminated.get()) {
            secureChannelFail(ProductionRuntimeSecureChannelFailure.INVALID_PHASE)
        }
    }

    private suspend fun <Value> failClosed(block: suspend () -> Value): Value = try {
        block()
    } catch (error: Throwable) {
        terminate(error)
        throw error
    }

    private suspend fun <Value> withTerminalDeadline(
        timeoutMillis: Long,
        operation: String,
        block: suspend () -> Value,
    ): Value {
        // This watchdog is deliberately launched beside the possibly blocked caller. If coroutine
        // cancellation alone cannot interrupt Socket.write/flush, synchronous raw close still can.
        val deadlineState = AtomicReference(TerminalDeadlineState.PENDING)
        val timeoutFailure = IOException("Production secure-channel $operation timed out")
        fun throwTimeoutWith(loser: Throwable? = null): Nothing {
            loser?.takeIf { it !== timeoutFailure }?.let(timeoutFailure::addSuppressed)
            throw timeoutFailure
        }
        fun claimCompletionOrThrowTimeout(loser: Throwable? = null) {
            if (deadlineState.compareAndSet(
                    TerminalDeadlineState.PENDING,
                    TerminalDeadlineState.COMPLETED,
                )
            ) {
                return
            }
            when (deadlineState.get()) {
                TerminalDeadlineState.TIMED_OUT -> throwTimeoutWith(loser)
                TerminalDeadlineState.COMPLETED ->
                    error("Production terminal deadline completion was claimed twice")
                TerminalDeadlineState.PENDING ->
                    error("Production terminal deadline CAS failed while still pending")
            }
        }
        fun claimTimeoutAndTerminalize() {
            if (deadlineState.compareAndSet(
                    TerminalDeadlineState.PENDING,
                    TerminalDeadlineState.TIMED_OUT,
                ) && signalTerminal(timeoutFailure)
            ) {
                scheduleAuthorityClose()
            }
        }
        val watchdog = scope.launch(start = CoroutineStart.UNDISPATCHED) {
            delay(timeoutMillis)
            claimTimeoutAndTerminalize()
        }
        return try {
            val outcome = try {
                withTimeoutOrNull(timeoutMillis) {
                    try {
                        Result.success(block())
                    } catch (error: CancellationException) {
                        // A CancellationException explicitly thrown while the caller Job remains
                        // active is data from the caller/composer. Carry it outside the timeout
                        // coroutine so stack-trace recovery cannot replace its object identity.
                        currentCoroutineContext().ensureActive()
                        Result.failure(error)
                    } catch (error: Throwable) {
                        Result.failure(error)
                    }
                }
            } catch (error: Throwable) {
                claimCompletionOrThrowTimeout(error)
                throw error
            }
            if (outcome == null) {
                claimTimeoutAndTerminalize()
                throw timeoutFailure
            }
            try {
                afterDeadlineOutcomeBeforeClaim(operation)
            } catch (error: Throwable) {
                claimCompletionOrThrowTimeout(error)
                throw error
            }
            claimCompletionOrThrowTimeout(outcome.exceptionOrNull())
            outcome.getOrThrow()
        } finally {
            watchdog.cancel()
        }
    }

    private suspend fun terminate(original: Throwable) = withContext(NonCancellable) {
        signalTerminal(original)
        try {
            closeAuthorityOnce()
        } catch (closeError: Throwable) {
            original.addSuppressed(closeError)
        }
    }

    /** Synchronous, idempotent, and bounded so it is safe inside the pairing terminal observer. */
    private fun signalTerminal(cause: Throwable): Boolean {
        var suppressedCommit: CompletableDeferred<Boolean>? = null
        val preserveCommittedApplication = synchronized(terminalStateLock) {
            if (!terminated.compareAndSet(false, true)) return false
            stagedApplicationItem?.let { item ->
                if (item.publication.state == InboundApplicationPublicationState.STAGED) {
                    item.publication.state = InboundApplicationPublicationState.SUPPRESSED
                    stagedApplicationItem = null
                    if (terminalApplicationItem === item) terminalApplicationItem = null
                    suppressedCommit = item.publication.commit
                }
            }
            when (terminalApplicationItem?.publication?.state) {
                InboundApplicationPublicationState.COMMITTED -> {
                    phase = Phase.TERMINAL_DRAIN
                    true
                }
                InboundApplicationPublicationState.STAGED,
                InboundApplicationPublicationState.CLAIMED,
                InboundApplicationPublicationState.SUPPRESSED,
                null,
                -> {
                    phase = Phase.CLOSED
                    false
                }
            }
        }
        suppressedCommit?.complete(false)
        keyUpdateRequiredBeforeApplication = false
        if (!preserveCommittedApplication) mailbox.close(cause)
        outboundRequests.close(cause)
        while (true) {
            val queued = outboundRequests.tryReceive().getOrNull() ?: break
            queued.completion.complete(Result.failure(cause))
        }
        inboundJob?.cancel()
        outboundJob?.cancel()
        expiryJob?.cancel()
        ownedScopeJob?.cancel()
        try {
            rawChannel.close()
        } catch (closeError: Throwable) {
            cause.addSuppressed(closeError)
        }
        return true
    }

    private suspend fun closeAuthorityOnce() {
        if (authorityCloseStarted.compareAndSet(false, true)) {
            authorityCloseCompletion.complete(runCatching { operations.close() })
        }
        authorityCloseCompletion.await().getOrThrow()
    }

    private fun scheduleAuthorityClose() {
        scope.launch(NonCancellable) {
            // The synchronous RuntimeProtocolChannel/observer surfaces cannot report a suspend
            // close failure; the channel is already terminal, so retain fail-closed state.
            runCatching { closeAuthorityOnce() }
        }
    }

    private fun requireAls1Object(body: ByteArray, objectType: Int, maximumBytes: Int) {
        if (body.size !in ALS1_HEADER_BYTES..maximumBytes ||
            body[0] != 'A'.code.toByte() ||
            body[1] != 'L'.code.toByte() ||
            body[2] != 'S'.code.toByte() ||
            body[3] != '1'.code.toByte() ||
            (body[4].toInt() and 0xff) != objectType ||
            (body[5].toInt() and 0xff) != ALS1_VERSION
        ) {
            secureChannelFail(ProductionRuntimeSecureChannelFailure.INVALID_FRAME)
        }
    }

    private fun secureChannelFail(failure: ProductionRuntimeSecureChannelFailure): Nothing =
        throw ProductionRuntimeSecureChannelException(failure)

    internal companion object {
        const val ALS1_HEADER_BYTES = 6
        const val ALS1_VERSION = 1
        const val DEFAULT_MAILBOX_CAPACITY = 64
        const val DEFAULT_OUTBOUND_QUEUE_CAPACITY = 64
        const val DEFAULT_HANDSHAKE_TIMEOUT_MILLIS = 15_000L
        const val DEFAULT_OUTBOUND_TIMEOUT_MILLIS = 30_000L
        val SYSTEM_TRUSTED_NOW_MS: () -> ULong = {
            System.currentTimeMillis().coerceAtLeast(0L).toULong()
        }

        fun createOwned(
            rawChannel: RuntimeRawFrameBodyChannel,
            capability: ProductionC1AuthorityBoundSecureSessionCapability,
            generation: Long,
            currentTimeMillis: () -> Long = { System.currentTimeMillis() },
        ): ProductionRuntimeSecureChannelAdapter = createOwnedWithOperations(
            rawChannel = rawChannel,
            operations = PairingProductionRuntimeSecureSessionOperations(capability),
            generation = generation,
            trustedNowMs = {
                val now = currentTimeMillis()
                check(now >= 0L) { "Production secure-channel clock must not be negative" }
                now.toULong()
            },
        )

        internal fun createOwnedForTesting(
            rawChannel: RuntimeRawFrameBodyChannel,
            operations: ProductionRuntimeSecureSessionOperations,
            generation: Long,
            onOwnedScopeCreated: (Job) -> Unit,
        ): ProductionRuntimeSecureChannelAdapter = createOwnedWithOperations(
            rawChannel = rawChannel,
            operations = operations,
            generation = generation,
            onOwnedScopeCreated = onOwnedScopeCreated,
        )

        private fun createOwnedWithOperations(
            rawChannel: RuntimeRawFrameBodyChannel,
            operations: ProductionRuntimeSecureSessionOperations,
            generation: Long,
            onOwnedScopeCreated: (Job) -> Unit = {},
            trustedNowMs: () -> ULong = SYSTEM_TRUSTED_NOW_MS,
        ): ProductionRuntimeSecureChannelAdapter {
            val scopeJob = SupervisorJob()
            return try {
                onOwnedScopeCreated(scopeJob)
                ProductionRuntimeSecureChannelAdapter(
                    rawChannel = rawChannel,
                    operations = operations,
                    generation = generation,
                    scope = CoroutineScope(scopeJob + Dispatchers.IO),
                    ownedScopeJob = scopeJob,
                    codec = ProtocolCodec(),
                    mailboxCapacity = DEFAULT_MAILBOX_CAPACITY,
                    outboundQueueCapacity = DEFAULT_OUTBOUND_QUEUE_CAPACITY,
                    handshakeTimeoutMillis = DEFAULT_HANDSHAKE_TIMEOUT_MILLIS,
                    outboundTimeoutMillis = DEFAULT_OUTBOUND_TIMEOUT_MILLIS,
                    trustedNowMs = trustedNowMs,
                    afterDeadlineOutcomeBeforeClaim = {},
                    afterTerminalDequeuedBeforeCommit = {},
                    afterTerminalCommitBeforeClaim = {},
                )
            } catch (error: Throwable) {
                scopeJob.cancel()
                throw error
            }
        }
    }
}
