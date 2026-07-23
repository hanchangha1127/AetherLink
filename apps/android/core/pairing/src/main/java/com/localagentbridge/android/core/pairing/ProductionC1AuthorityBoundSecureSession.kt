package com.localagentbridge.android.core.pairing

import com.localagentbridge.android.core.protocol.p2pnat.ProductionAuthorityBoundSecureSessionEngine
import com.localagentbridge.android.core.protocol.p2pnat.ProductionSecureSessionEphemeralKey
import com.localagentbridge.android.core.protocol.p2pnat.ProductionSecureSessionOpenResult
import com.localagentbridge.android.core.protocol.p2pnat.ProductionSecureSessionRecordContentType
import com.localagentbridge.android.core.protocol.p2pnat.ProductionSecureSessionSealResult
import com.localagentbridge.android.core.protocol.p2pnat.VerifiedProductionC1CandidateP2PKeyScheduleBinding
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.util.concurrent.atomic.AtomicBoolean

/** Secret-free identity of the exact authority-bound secure session. */
data class ProductionC1AuthorityBoundSecureSessionDescriptor(
    val sessionId: String,
    val expiresAtMs: ULong,
    /** Domain-separated KDF binding over canonical object 7 + object 26. */
    val object7Object26KdfBindingDigestHex: String,
) {
    init {
        check(sessionId.length == 32 && sessionId.all { it in '0'..'9' || it in 'a'..'f' })
        check(expiresAtMs > 0uL)
        check(
            object7Object26KdfBindingDigestHex.length == 64 &&
                object7Object26KdfBindingDigestHex.all { it in '0'..'9' || it in 'a'..'f' },
        )
    }
}

/** Non-secret outcome after one sealed record has been durably handed to its publisher. */
data class ProductionC1AuthorityBoundRecordPublication(
    val keyUpdateRequired: Boolean,
    val terminalAfterRecord: Boolean,
)

private val productionC1AuthorityBoundStartCapabilityMint = Any()
private val productionC1AuthorityBoundSessionCapabilityMint = Any()

internal data class ProductionC1AuthorityBoundStartMaterial(
    val request: ProductionC1ExactBoundStartRequest,
    val localEphemeralKey: ProductionSecureSessionEphemeralKey,
)

/**
 * Opaque, one-shot input issued only after PairingStore has revalidated the current durable
 * authority. It deliberately exposes neither the request nor the ephemeral private key.
 */
class ProductionC1AuthorityBoundSecureSessionStartCapability internal constructor(
    private val owner: PairingStore,
    private val request: ProductionC1ExactBoundStartRequest,
    private val localEphemeralKey: ProductionSecureSessionEphemeralKey,
    provenance: Any,
) {
    private val claimed = AtomicBoolean(false)

    init {
        check(provenance === productionC1AuthorityBoundStartCapabilityMint) {
            "Production authority-bound start capability provenance mismatch"
        }
    }

    internal fun claim(claimingStore: PairingStore): ProductionC1AuthorityBoundStartMaterial {
        check(owner === claimingStore) {
            "Production authority-bound start capability belongs to another PairingStore"
        }
        check(claimed.compareAndSet(false, true)) {
            "Production authority-bound start capability was already claimed"
        }
        return ProductionC1AuthorityBoundStartMaterial(request, localEphemeralKey)
    }
}

internal fun mintProductionC1AuthorityBoundSecureSessionStartCapability(
    owner: PairingStore,
    request: ProductionC1ExactBoundStartRequest,
    localEphemeralKey: ProductionSecureSessionEphemeralKey,
): ProductionC1AuthorityBoundSecureSessionStartCapability =
    ProductionC1AuthorityBoundSecureSessionStartCapability(
        owner,
        request,
        localEphemeralKey,
        productionC1AuthorityBoundStartCapabilityMint,
    )

/**
 * Narrow transport-facing facade. Raw crypto engines, authority permits, and plaintext/record
 * ownership never escape this capability: callback buffers are zeroed before each call returns.
 */
class ProductionC1AuthorityBoundSecureSessionCapability internal constructor(
    private val session: ProductionC1AuthorityBoundSecureSession,
    val descriptor: ProductionC1AuthorityBoundSecureSessionDescriptor,
    provenance: Any,
) {
    init {
        check(provenance === productionC1AuthorityBoundSessionCapabilityMint) {
            "Production authority-bound secure-session capability provenance mismatch"
        }
    }

    suspend fun sendLocalConfirmationAndMark(send: suspend (ByteArray) -> Unit) =
        session.sendLocalConfirmationAndMark(send)

    suspend fun acceptPeerConfirmation(encodedConfirmation: ByteArray) =
        session.acceptPeerConfirmation(encodedConfirmation)

    suspend fun activate() = session.activate()

    /**
     * Installs the sole terminal notification. The callback is invoked synchronously at most once,
     * contains no secrets, and must only perform a non-blocking transport close/wakeup.
     */
    fun installTerminalObserver(observer: () -> Unit) = session.installTerminalObserver(observer)

    suspend fun sealApplicationAndSend(
        plaintext: ByteArray,
        send: suspend (ByteArray) -> Unit,
    ): ProductionC1AuthorityBoundRecordPublication =
        session.sealApplicationAndSend(plaintext, send)

    suspend fun sealKeyUpdateAndSend(
        send: suspend (ByteArray) -> Unit,
    ): ProductionC1AuthorityBoundRecordPublication = session.sealKeyUpdateAndSend(send)

    suspend fun <Value> openAndPublish(
        encodedRecord: ByteArray,
        publish: suspend (
            plaintext: ByteArray,
            contentType: ProductionSecureSessionRecordContentType,
            keyUpdateRequired: Boolean,
            terminalAfterRecord: Boolean,
        ) -> Value,
    ): Value = session.openAndPublish(encodedRecord, publish)

    suspend fun close() = session.close()
}

internal fun ProductionC1AuthorityBoundSecureSession.asCapability(
    descriptor: ProductionC1AuthorityBoundSecureSessionDescriptor,
): ProductionC1AuthorityBoundSecureSessionCapability =
    ProductionC1AuthorityBoundSecureSessionCapability(
        this,
        descriptor,
        productionC1AuthorityBoundSessionCapabilityMint,
    )

internal class ProductionC1AuthorityBoundSealResult(
    record: ByteArray,
    val keyUpdateRequired: Boolean,
    val terminalAfterRecord: Boolean,
) {
    private val recordBytes = record.copyOf()
    val record: ByteArray get() = recordBytes.copyOf()

    internal fun wipe() = recordBytes.fill(0)
}

internal class ProductionC1AuthorityBoundOpenResult(
    plaintext: ByteArray,
    val contentType: ProductionSecureSessionRecordContentType,
    val keyUpdateRequired: Boolean,
    val terminalAfterRecord: Boolean,
) {
    private val plaintextBytes = plaintext.copyOf()
    val plaintext: ByteArray get() = plaintextBytes.copyOf()

    internal fun wipe() = plaintextBytes.fill(0)
}

internal interface ProductionC1AuthoritySecureSessionEngine : AutoCloseable {
    val isTerminal: Boolean
    fun localConfirmation(nowMs: ULong): ByteArray
    fun markLocalConfirmationSent(encodedConfirmation: ByteArray, nowMs: ULong)
    fun acceptPeerConfirmation(encodedConfirmation: ByteArray, nowMs: ULong)
    fun activate(nowMs: ULong)
    fun sealApplication(plaintext: ByteArray, nowMs: ULong): ProductionC1AuthorityBoundSealResult
    fun sealKeyUpdate(nowMs: ULong): ProductionC1AuthorityBoundSealResult
    fun open(encodedRecord: ByteArray, nowMs: ULong): ProductionC1AuthorityBoundOpenResult
    fun invalidate()
}

private class ProtocolAuthoritySecureSessionEngine(
    private val engine: ProductionAuthorityBoundSecureSessionEngine,
) : ProductionC1AuthoritySecureSessionEngine {
    override val isTerminal: Boolean get() = engine.isTerminal

    override fun localConfirmation(nowMs: ULong): ByteArray = engine.localConfirmation(nowMs)

    override fun markLocalConfirmationSent(encodedConfirmation: ByteArray, nowMs: ULong) =
        engine.markLocalConfirmationSent(encodedConfirmation, nowMs)

    override fun acceptPeerConfirmation(encodedConfirmation: ByteArray, nowMs: ULong) =
        engine.acceptPeerConfirmation(encodedConfirmation, nowMs)

    override fun activate(nowMs: ULong) = engine.activate(nowMs)

    override fun sealApplication(
        plaintext: ByteArray,
        nowMs: ULong,
    ): ProductionC1AuthorityBoundSealResult = engine.sealApplication(plaintext, nowMs).authorityResult()

    override fun sealKeyUpdate(nowMs: ULong): ProductionC1AuthorityBoundSealResult =
        engine.sealKeyUpdate(nowMs).authorityResult()

    override fun open(
        encodedRecord: ByteArray,
        nowMs: ULong,
    ): ProductionC1AuthorityBoundOpenResult = engine.open(encodedRecord, nowMs).authorityResult()

    override fun invalidate() = engine.invalidate()
    override fun close() = engine.close()

    private fun ProductionSecureSessionSealResult.authorityResult():
        ProductionC1AuthorityBoundSealResult {
        val transferred = takeRecordAndWipe()
        return try {
            ProductionC1AuthorityBoundSealResult(
                transferred,
                keyUpdateRequired,
                terminalAfterRecord,
            )
        } finally {
            transferred.fill(0)
        }
    }

    private fun ProductionSecureSessionOpenResult.authorityResult():
        ProductionC1AuthorityBoundOpenResult {
        val transferred = takePlaintextAndWipe()
        return try {
            ProductionC1AuthorityBoundOpenResult(
                transferred,
                contentType,
                keyUpdateRequired,
                terminalAfterRecord,
            )
        } finally {
            transferred.fill(0)
        }
    }
}

internal fun interface ProductionC1AuthoritySecureSessionEngineFactory {
    suspend fun derive(
        binding: VerifiedProductionC1CandidateP2PKeyScheduleBinding,
    ): ProductionC1AuthoritySecureSessionEngine
}

private class ProductionC1AuthoritySecureSessionLockBox {
    private var engine: ProductionC1AuthoritySecureSessionEngine? = null
    private var terminal = false
    private var terminalObserverInstalled = false
    private var terminalObserverDelivered = false
    private var terminalObserver: (() -> Unit)? = null

    @Synchronized
    fun install(value: ProductionC1AuthoritySecureSessionEngine) {
        if (terminal || engine != null) {
            try {
                value.invalidate()
            } finally {
                value.close()
            }
            check(false) { "Production authority secure-session engine publication was fenced" }
        }
        engine = value
    }

    @Synchronized
    fun <Value> use(block: (ProductionC1AuthoritySecureSessionEngine) -> Value): Value {
        check(!terminal) { "Production authority secure-session engine is terminal" }
        return block(requireNotNull(engine) { "Production authority secure-session engine is absent" })
    }

    @Synchronized
    fun assertLive() {
        check(!terminal && engine != null) {
            "Production authority secure-session engine publication was fenced"
        }
    }

    @Synchronized
    fun isEngineTerminal(): Boolean = terminal || engine?.isTerminal != false

    fun installTerminalObserver(observer: () -> Unit) {
        val immediate = synchronized(this) {
            check(!terminalObserverInstalled) {
                "Production authority secure-session terminal observer was already installed"
            }
            terminalObserverInstalled = true
            if (terminal) {
                terminalObserverDelivered = true
                observer
            } else {
                terminalObserver = observer
                null
            }
        }
        notifyTerminal(immediate)
    }

    fun invalidate() {
        var callback: (() -> Unit)? = null
        var failure: Throwable? = null
        synchronized(this) {
            if (terminal) return
            terminal = true
            try {
                engine?.invalidate()
            } catch (error: Throwable) {
                failure = error
            } finally {
                callback = takeTerminalObserverLocked()
            }
        }
        notifyTerminal(callback)
        failure?.let { throw it }
    }

    fun close() {
        var callback: (() -> Unit)? = null
        var failure: Throwable? = null
        synchronized(this) {
            terminal = true
            val closingEngine = engine
            engine = null
            if (closingEngine != null) {
                try {
                    closingEngine.invalidate()
                } catch (error: Throwable) {
                    failure = error
                }
                try {
                    closingEngine.close()
                } catch (error: Throwable) {
                    failure?.addSuppressed(error) ?: run { failure = error }
                }
            }
            callback = takeTerminalObserverLocked()
        }
        notifyTerminal(callback)
        failure?.let { throw it }
    }

    private fun takeTerminalObserverLocked(): (() -> Unit)? {
        if (terminalObserverDelivered) return null
        val observer = terminalObserver ?: return null
        terminalObserver = null
        terminalObserverDelivered = true
        return observer
    }

    private fun notifyTerminal(observer: (() -> Unit)?) {
        try {
            observer?.invoke()
        } catch (_: Throwable) {
            // Transport wakeup failures must not reopen crypto authority or poison abort cleanup.
        }
    }
}

/**
 * The only pairing production path from an exact durable authority commit to record crypto.
 * Every externally observable operation is fenced before and after by the coordinator lease.
 */
internal class ProductionC1AuthorityBoundSecureSession private constructor(
    private val coordinator: ProductionC1ExactBoundStartCoordinator,
    private val lease: ProductionC1ExactBoundStartLease,
    private val lockBox: ProductionC1AuthoritySecureSessionLockBox,
    private val publicationGate: ProductionC1AuthorityPublicationGate,
    private val nowMs: () -> ULong,
) {
    private val closeMutex = Mutex()
    private val outboundPublicationMutex = Mutex()
    private val inboundPublicationMutex = Mutex()
    @Volatile private var closing = false
    @Volatile private var closed = false

    suspend fun localConfirmation(): ByteArray = fenced(
        wipeOnFailure = { it.fill(0) },
    ) { it.localConfirmation(nowMs()) }

    suspend fun markLocalConfirmationSent(encodedConfirmation: ByteArray) = fenced {
        it.markLocalConfirmationSent(encodedConfirmation, nowMs())
    }

    suspend fun acceptPeerConfirmation(encodedConfirmation: ByteArray) = fenced {
        it.acceptPeerConfirmation(encodedConfirmation, nowMs())
    }

    suspend fun activate() = fenced { it.activate(nowMs()) }

    suspend fun sealApplication(plaintext: ByteArray): ProductionC1AuthorityBoundSealResult = fenced(
        wipeOnFailure = ProductionC1AuthorityBoundSealResult::wipe,
    ) { it.sealApplication(plaintext, nowMs()) }

    suspend fun sealKeyUpdate(): ProductionC1AuthorityBoundSealResult = fenced(
        wipeOnFailure = ProductionC1AuthorityBoundSealResult::wipe,
    ) { it.sealKeyUpdate(nowMs()) }

    suspend fun open(encodedRecord: ByteArray): ProductionC1AuthorityBoundOpenResult = fenced(
        wipeOnFailure = ProductionC1AuthorityBoundOpenResult::wipe,
    ) { it.open(encodedRecord, nowMs()) }

    suspend fun sendLocalConfirmationAndMark(
        send: suspend (ByteArray) -> Unit,
    ) = outboundPublicationMutex.withLock {
        fencedPublication(
            prepare = { engine -> engine.localConfirmation(nowMs()) },
            wipePrepared = { confirmation -> confirmation.fill(0) },
        ) { engine, confirmation ->
            send(confirmation)
            currentCoroutineContext().ensureActive()
            lockBox.use { liveEngine ->
                check(liveEngine === engine) {
                    "Production authority secure-session engine changed during publication"
                }
                liveEngine.markLocalConfirmationSent(confirmation, nowMs())
            }
        }
    }

    suspend fun sealApplicationAndSend(
        plaintext: ByteArray,
        send: suspend (ByteArray) -> Unit,
    ): ProductionC1AuthorityBoundRecordPublication = outboundPublicationMutex.withLock {
        fencedPublication(
            prepare = { engine -> engine.sealApplication(plaintext, nowMs()) },
            wipePrepared = ProductionC1AuthorityBoundSealResult::wipe,
        ) { _, sealed ->
            val record = sealed.record
            try {
                send(record)
                ProductionC1AuthorityBoundRecordPublication(
                    keyUpdateRequired = sealed.keyUpdateRequired,
                    terminalAfterRecord = sealed.terminalAfterRecord,
                )
            } finally {
                record.fill(0)
            }
        }
    }

    suspend fun sealKeyUpdateAndSend(
        send: suspend (ByteArray) -> Unit,
    ): ProductionC1AuthorityBoundRecordPublication = outboundPublicationMutex.withLock {
        fencedPublication(
            prepare = { engine -> engine.sealKeyUpdate(nowMs()) },
            wipePrepared = ProductionC1AuthorityBoundSealResult::wipe,
        ) { _, sealed ->
            val record = sealed.record
            try {
                send(record)
                ProductionC1AuthorityBoundRecordPublication(
                    keyUpdateRequired = sealed.keyUpdateRequired,
                    terminalAfterRecord = sealed.terminalAfterRecord,
                )
            } finally {
                record.fill(0)
            }
        }
    }

    suspend fun <Value> openAndPublish(
        encodedRecord: ByteArray,
        publish: suspend (
            plaintext: ByteArray,
            contentType: ProductionSecureSessionRecordContentType,
            keyUpdateRequired: Boolean,
            terminalAfterRecord: Boolean,
        ) -> Value,
    ): Value = inboundPublicationMutex.withLock {
        fencedPublication(
            prepare = { engine -> engine.open(encodedRecord, nowMs()) },
            wipePrepared = ProductionC1AuthorityBoundOpenResult::wipe,
        ) { _, opened ->
            val plaintext = opened.plaintext
            try {
                publish(
                    plaintext,
                    opened.contentType,
                    opened.keyUpdateRequired,
                    opened.terminalAfterRecord,
                )
            } finally {
                plaintext.fill(0)
            }
        }
    }

    suspend fun close() = withContext(NonCancellable) {
        publicationGate.withWrite {
            closeMutex.withLock {
                if (closed) return@withLock
                closing = true
                var closeFailure: Throwable? = null
                try {
                    lockBox.close()
                } catch (error: Throwable) {
                    closeFailure = error
                }
                var completionFailure: Throwable? = null
                try {
                    try {
                        coordinator.complete(lease)
                    } catch (error: ProductionC1ExactBoundStartCoordinatorException) {
                        if (error.failure !=
                            ProductionC1ExactBoundStartCoordinatorFailure.INVALID_LEASE
                        ) {
                            completionFailure = error
                        }
                    } catch (error: Throwable) {
                        completionFailure = error
                    }
                } finally {
                    closed = true
                }
                if (closeFailure != null && completionFailure != null) {
                    closeFailure.addSuppressed(completionFailure)
                }
                closeFailure?.let { throw it }
                completionFailure?.let { throw it }
            }
        }
    }

    internal fun isClosingForTesting(): Boolean = closing

    fun installTerminalObserver(observer: () -> Unit) =
        lockBox.installTerminalObserver(observer)

    private data class PreparedPublication<Value : Any>(
        val engine: ProductionC1AuthoritySecureSessionEngine,
        val value: Value,
    )

    private suspend fun <Prepared : Any, Value> fencedPublication(
        prepare: (ProductionC1AuthoritySecureSessionEngine) -> Prepared,
        wipePrepared: (Prepared) -> Unit,
        publish: suspend (ProductionC1AuthoritySecureSessionEngine, Prepared) -> Value,
    ): Value = publicationGate.withRead {
        assertActiveOrInvalidate()
        var prepared: Prepared? = null
        try {
            assertPublicationReady("before preparation")
            val preparedPublication = lockBox.use { engine ->
                PreparedPublication(engine, prepare(engine))
            }
            prepared = preparedPublication.value
            assertPublicationReady("before publication")
            val published = publish(preparedPublication.engine, preparedPublication.value)
            assertPublicationReady("after publication")
            published
        } catch (error: Throwable) {
            val terminalEngineFailure = lockBox.isEngineTerminal()
            val cancellation = error is CancellationException
            val publicationStateConsumed = prepared != null
            if (closing || closed || error is ProductionC1ExactBoundStartCoordinatorException ||
                terminalEngineFailure || cancellation || publicationStateConsumed
            ) {
                try {
                    lockBox.invalidate()
                } catch (invalidationError: Throwable) {
                    error.addSuppressed(invalidationError)
                }
            }
            if ((terminalEngineFailure || cancellation || publicationStateConsumed) &&
                !closing && !closed
            ) {
                terminalizeLeaseAfterEngineFailure(error)
            }
            throw error
        } finally {
            prepared?.let(wipePrepared)
        }
    }

    private suspend fun assertPublicationReady(boundary: String) {
        currentCoroutineContext().ensureActive()
        lockBox.assertLive()
        check(!closing && !closed) {
            "Production authority secure-session closed $boundary"
        }
        coordinator.assertActive(lease)
        currentCoroutineContext().ensureActive()
        lockBox.assertLive()
        check(!closing && !closed) {
            "Production authority secure-session closed $boundary"
        }
    }

    private suspend fun <Value> fenced(
        wipeOnFailure: (Value) -> Unit = {},
        operation: (ProductionC1AuthoritySecureSessionEngine) -> Value,
    ): Value = publicationGate.withRead {
        assertActiveOrInvalidate()
        var value: Value? = null
        try {
            currentCoroutineContext().ensureActive()
            check(!closing && !closed) { "Production authority secure-session is closing" }
            value = lockBox.use(operation)
            currentCoroutineContext().ensureActive()
            lockBox.assertLive()
            check(!closing && !closed) { "Production authority secure-session closed during operation" }
            coordinator.assertActive(lease)
            currentCoroutineContext().ensureActive()
            lockBox.assertLive()
            check(!closing && !closed) { "Production authority secure-session closed before publication" }
            requireNotNull(value)
        } catch (error: Throwable) {
            value?.let(wipeOnFailure)
            val terminalEngineFailure = lockBox.isEngineTerminal()
            val cancellation = error is CancellationException
            if (closing || closed || error is ProductionC1ExactBoundStartCoordinatorException ||
                terminalEngineFailure || cancellation
            ) {
                lockBox.invalidate()
            }
            if ((terminalEngineFailure || cancellation) && !closing && !closed) {
                terminalizeLeaseAfterEngineFailure(error)
            }
            throw error
        }
    }

    private suspend fun assertActiveOrInvalidate() {
        try {
            coordinator.assertActive(lease)
        } catch (error: Throwable) {
            lockBox.invalidate()
            throw error
        }
    }

    private suspend fun terminalizeLeaseAfterEngineFailure(original: Throwable) {
        withContext(NonCancellable) {
            try {
                coordinator.cancel(lease)
            } catch (error: ProductionC1ExactBoundStartCoordinatorException) {
                if (error.failure != ProductionC1ExactBoundStartCoordinatorFailure.INVALID_LEASE) {
                    original.addSuppressed(error)
                }
            } catch (error: Throwable) {
                original.addSuppressed(error)
            }
        }
    }

    companion object {
        internal suspend fun begin(
            coordinator: ProductionC1ExactBoundStartCoordinator,
            request: ProductionC1ExactBoundStartRequest,
            localEphemeralKey: ProductionSecureSessionEphemeralKey,
            publicationGate: ProductionC1AuthorityPublicationGate,
            nowMs: () -> ULong,
        ): ProductionC1AuthorityBoundSecureSession = beginWithFactory(
            coordinator,
            request,
            publicationGate,
            nowMs,
            ProductionC1AuthoritySecureSessionEngineFactory { binding ->
                ProtocolAuthoritySecureSessionEngine(
                    ProductionAuthorityBoundSecureSessionEngine.derive(
                        binding,
                        localEphemeralKey,
                        nowMs(),
                    ),
                )
            },
        )

        internal suspend fun beginWithFactoryForTesting(
            coordinator: ProductionC1ExactBoundStartCoordinator,
            request: ProductionC1ExactBoundStartRequest,
            publicationGate: ProductionC1AuthorityPublicationGate,
            nowMs: () -> ULong,
            engineFactory: ProductionC1AuthoritySecureSessionEngineFactory,
        ): ProductionC1AuthorityBoundSecureSession =
            beginWithFactory(coordinator, request, publicationGate, nowMs, engineFactory)

        private suspend fun beginWithFactory(
            coordinator: ProductionC1ExactBoundStartCoordinator,
            request: ProductionC1ExactBoundStartRequest,
            publicationGate: ProductionC1AuthorityPublicationGate,
            nowMs: () -> ULong,
            engineFactory: ProductionC1AuthoritySecureSessionEngineFactory,
        ): ProductionC1AuthorityBoundSecureSession = publicationGate.withRead {
            val exactBinding = request.binding.keyScheduleBinding
            check(exactBinding.transcript == request.binding.transcript)
            check(exactBinding.securityContext == request.binding.securityContext)
            check(exactBinding.grantAuthorization == request.binding.grant.grantAuthorization)
            val lockBox = ProductionC1AuthoritySecureSessionLockBox()
            val handle = coordinator.admit(request)
            val lease = coordinator.begin(
                handle,
                request,
                ProductionC1ExactBoundStartOperation(
                    start = {
                        val engine = engineFactory.derive(exactBinding)
                        lockBox.install(engine)
                    },
                    abort = { lockBox.invalidate() },
                ),
            )
            ProductionC1AuthorityBoundSecureSession(
                coordinator,
                lease,
                lockBox,
                publicationGate,
                nowMs,
            ).also {
                try {
                    currentCoroutineContext().ensureActive()
                    coordinator.assertActive(lease)
                    currentCoroutineContext().ensureActive()
                } catch (error: Throwable) {
                    withContext(NonCancellable) {
                        lockBox.invalidate()
                        try {
                            coordinator.cancel(lease)
                        } catch (cancelError: ProductionC1ExactBoundStartCoordinatorException) {
                            if (cancelError.failure !=
                                ProductionC1ExactBoundStartCoordinatorFailure.INVALID_LEASE
                            ) {
                                error.addSuppressed(cancelError)
                            }
                        } catch (cancelError: Throwable) {
                            error.addSuppressed(cancelError)
                        }
                    }
                    throw error
                }
            }
        }
    }
}
