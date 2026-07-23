package com.localagentbridge.android.core.pairing

import com.localagentbridge.android.core.protocol.p2pnat.VerifiedProductionC1CandidateP2PTranscriptBinding
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.DisposableHandle
import kotlinx.coroutines.InternalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.supervisorScope
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.NonCancellable
import java.util.UUID
import kotlin.coroutines.AbstractCoroutineContextElement
import kotlin.coroutines.CoroutineContext

internal data class ProductionC1ExactBoundStartRequest(
    val expectedRuntimeDeviceId: String,
    val expectedRuntimeFingerprint: String,
    val expectedRuntimePublicKey: String,
    val token: ProductionC1EndpointGrantCompoundCommitToken,
    val binding: VerifiedProductionC1CandidateP2PTranscriptBinding,
)

internal data class ProductionC1ExactBoundStartValidation(
    val runtimeDeviceId: String,
    val pairAuthorityDigest: String,
    val markerDigest: String,
    val admissionId: String,
    val bindingDigest: String,
    val sessionId: String,
    val effectiveNotBeforeMs: ULong,
    val expiresAtMs: ULong,
    val pairLocalRevision: ULong,
    val ledgerRevision: ULong,
)

internal enum class ProductionC1ExactBoundStartValidationFailure {
    NO_CURRENT_COMMIT,
    STALE_COMMIT,
    EXACT_BINDING_MISMATCH,
    IDENTITY_MISMATCH,
    INACTIVE_PAIR_AUTHORITY,
    NOT_YET_VALID,
    EXPIRED,
}

internal class ProductionC1ExactBoundStartValidationException(
    val failure: ProductionC1ExactBoundStartValidationFailure,
    cause: Throwable? = null,
) : IllegalStateException("Production C1 exact-bound start validation failed: $failure", cause)

internal fun exactBoundStartRequire(
    condition: Boolean,
    failure: ProductionC1ExactBoundStartValidationFailure,
) {
    if (!condition) throw ProductionC1ExactBoundStartValidationException(failure)
}

internal class ProductionC1ExactBoundStartHandle internal constructor(
    val generation: ULong,
    val markerDigest: String,
    private val nonce: UUID,
) {
    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is ProductionC1ExactBoundStartHandle &&
                generation == other.generation &&
                markerDigest == other.markerDigest &&
                nonce == other.nonce)

    override fun hashCode(): Int = 31 * (31 * generation.hashCode() + markerDigest.hashCode()) +
        nonce.hashCode()
}

internal class ProductionC1ExactBoundStartLease internal constructor(
    val generation: ULong,
    val markerDigest: String,
    private val nonce: UUID,
) {
    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is ProductionC1ExactBoundStartLease &&
                generation == other.generation &&
                markerDigest == other.markerDigest &&
                nonce == other.nonce)

    override fun hashCode(): Int = 31 * (31 * generation.hashCode() + markerDigest.hashCode()) +
        nonce.hashCode()
}

internal enum class ProductionC1ExactBoundStartTerminalReason {
    COMPLETED,
    CANCELLED,
    REVOKED,
    AUTHORITY_ADVANCED,
    EXPIRED,
    VALIDATION_FAILED,
    START_FAILED,
}

internal data class ProductionC1ExactBoundStartTombstone(
    val pairAuthorityDigest: String,
    val markerDigest: String,
    val generation: ULong,
    val reason: ProductionC1ExactBoundStartTerminalReason,
)

internal enum class ProductionC1ExactBoundStartCoordinatorFailure {
    PAIR_ALREADY_LIVE,
    PAIR_CLEANUP_PENDING,
    MARKER_REPLAY,
    INVALID_HANDLE,
    INVALID_LEASE,
    FENCED,
    EXPIRED,
    GENERATION_OVERFLOW,
}

internal class ProductionC1ExactBoundStartCoordinatorException(
    val failure: ProductionC1ExactBoundStartCoordinatorFailure,
) : IllegalStateException("Production C1 exact-bound start coordinator failed: $failure")

internal fun interface ProductionC1ExactBoundStartValidator {
    suspend fun validate(request: ProductionC1ExactBoundStartRequest):
        ProductionC1ExactBoundStartValidation
}

private class ProductionC1StartInvocationContext(
    val operationId: UUID,
) : AbstractCoroutineContextElement(Key) {
    companion object Key : CoroutineContext.Key<ProductionC1StartInvocationContext>
}

/** Explicit reentry capability that remains valid when a callback changes CoroutineContext. */
internal class ProductionC1ExactBoundStartOperationContext internal constructor(
    private val coordinator: ProductionC1ExactBoundStartCoordinator,
    internal val operationId: UUID,
) {
    internal suspend fun cancel(handle: ProductionC1ExactBoundStartHandle) =
        coordinator.cancelFromOperation(handle, operationId)

    internal suspend fun cancel(lease: ProductionC1ExactBoundStartLease) =
        coordinator.cancelFromOperation(lease, operationId)

    internal suspend fun fenceRevoked(pairAuthorityDigest: String) =
        coordinator.fenceRevokedFromOperation(pairAuthorityDigest, operationId)

    internal suspend fun fenceAuthorityAdvance(previousPairAuthorityDigest: String) =
        coordinator.fenceAuthorityAdvanceFromOperation(previousPairAuthorityDigest, operationId)

    internal suspend fun fenceExpired() = coordinator.fenceExpiredFromOperation(operationId)

    internal suspend fun retryPendingAborts() =
        coordinator.retryPendingAbortsFromOperation(operationId)
}

/**
 * One generation-scoped start operation. The coordinator-owned latch prevents start after an
 * early abort and, when abort races an in-flight start, waits for start to return and invokes the
 * idempotent cleanup again before releasing the pair quarantine. Callers do not implement the
 * late-publication latch themselves.
 */
internal class ProductionC1ExactBoundStartOperation(
    start: suspend (ProductionC1ExactBoundStartOperationContext) -> Unit,
    abort: suspend (ProductionC1ExactBoundStartOperationContext) -> Unit,
) {
    private enum class Phase { NOT_STARTED, STARTING, FINISHED }

    private val lifecycleMutex = Mutex()
    private val startFinished = CompletableDeferred<Unit>()
    private val startAction = start
    private val abortAction = abort
    internal val operationId: UUID = UUID.randomUUID()
    private var phase = Phase.NOT_STARTED
    private var abortRequested = false
    private var reentrantAbortCompletion: CompletableDeferred<Throwable?>? = null
    private var reentrantFirstAttempt: CompletableDeferred<Throwable?>? = null

    internal suspend fun start(context: ProductionC1ExactBoundStartOperationContext) {
        val shouldStart = lifecycleMutex.withLock {
            check(phase == Phase.NOT_STARTED) { "Production C1 start operation was reused" }
            if (abortRequested) {
                phase = Phase.FINISHED
                startFinished.complete(Unit)
                false
            } else {
                phase = Phase.STARTING
                true
            }
        }
        if (!shouldStart) return
        try {
            var startFailure: Throwable? = null
            withContext(ProductionC1StartInvocationContext(operationId)) {
                try {
                    startAction(context)
                } catch (error: Throwable) {
                    startFailure = error
                }
            }
            startFailure?.let { throw it }
        } finally {
            val deferredCleanup = withContext(NonCancellable) {
                lifecycleMutex.withLock {
                    phase = Phase.FINISHED
                    startFinished.complete(Unit)
                    val completion = reentrantAbortCompletion
                    val firstAttempt = reentrantFirstAttempt
                    if (completion != null && firstAttempt != null) {
                        completion to firstAttempt
                    } else {
                        null
                    }
                }
            }
            if (deferredCleanup != null) {
                val (completion, firstAttempt) = deferredCleanup
                val firstFailure = withContext(NonCancellable) { firstAttempt.await() }
                val finalFailure = withContext(
                    NonCancellable + ProductionC1StartInvocationContext(operationId),
                ) {
                    runCatching { abortAction(context) }.exceptionOrNull()
                }
                if (finalFailure != null && firstFailure != null &&
                    finalFailure !== firstFailure
                ) {
                    finalFailure.addSuppressed(firstFailure)
                }
                completion.complete(finalFailure)
            }
        }
    }

    /**
     * Returns a completion only when start itself requested its fence. The coordinator keeps the
     * pair quarantined while start unwinds and this operation performs the late-publication abort.
     */
    internal suspend fun abort(
        context: ProductionC1ExactBoundStartOperationContext,
        originOperationId: UUID?,
    ): CompletableDeferred<Throwable?>? {
        val invokedByOwnStart = originOperationId == operationId ||
            currentCoroutineContext()[ProductionC1StartInvocationContext]?.operationId ==
                operationId
        var ownStartingAttempt: Pair<
            CompletableDeferred<Throwable?>,
            CompletableDeferred<Throwable?>
        >? = null
        val phaseAtAbort = lifecycleMutex.withLock {
            abortRequested = true
            if (phase == Phase.STARTING && invokedByOwnStart) {
                val completion = reentrantAbortCompletion
                    ?: CompletableDeferred<Throwable?>().also {
                        reentrantAbortCompletion = it
                    }
                val firstAttempt = reentrantFirstAttempt
                    ?: CompletableDeferred<Throwable?>().also {
                        reentrantFirstAttempt = it
                    }
                ownStartingAttempt = completion to firstAttempt
            }
            phase
        }
        val firstFailure = runCatching { abortAction(context) }.exceptionOrNull()
        ownStartingAttempt?.let { (completion, firstAttempt) ->
            firstAttempt.complete(firstFailure)
            return completion
        }
        if (phaseAtAbort == Phase.STARTING) {
            startFinished.await()
            val delegated = lifecycleMutex.withLock { reentrantAbortCompletion }
            if (delegated != null) {
                delegated.await()?.let { throw it }
                return null
            }
            val finalFailure = runCatching { abortAction(context) }.exceptionOrNull()
            if (finalFailure != null) {
                if (firstFailure != null && firstFailure !== finalFailure) {
                    finalFailure.addSuppressed(firstFailure)
                }
                throw finalFailure
            }
            return null
        }
        firstFailure?.let { throw it }
        return null
    }
}

/**
 * Process-local admission gate for the exact current durable compound commit.
 *
 * The production instance is cached by PairingStore. No historical readback can enter this API,
 * and no token, binding, connector secret, or key-confirmation material is retained in terminal
 * tombstones.
 */
internal class ProductionC1ExactBoundStartCoordinator private constructor(
    private val validator: ProductionC1ExactBoundStartValidator?,
    private val nowMs: () -> ULong,
    initialGeneration: ULong,
    private val handoffReturnedForTesting: (() -> Unit)?,
    private val ownershipTransitionForTesting: (() -> Unit)?,
) {
    private enum class Phase { VALIDATING, ADMITTED, STARTING, ACTIVE }

    private data class LiveRecord(
        val handle: ProductionC1ExactBoundStartHandle,
        val runtimeDeviceId: String,
        val pairAuthorityDigest: String,
        val expiresAtMs: ULong,
        var validation: ProductionC1ExactBoundStartValidation?,
        var lease: ProductionC1ExactBoundStartLease?,
        var abortOperationId: UUID?,
        var abort: (suspend (UUID?) -> CompletableDeferred<Throwable?>?)?,
        var handleCancellationCleanup: DisposableHandle?,
        var handleCancellationToken: UUID?,
        var leaseCancellationCleanup: DisposableHandle?,
        var leaseCancellationToken: UUID?,
        var phase: Phase,
    )

    private sealed interface Finalization {
        data class Active(val lease: ProductionC1ExactBoundStartLease) : Finalization
        data class Failed(
            val error: Throwable,
            val abort: PendingAbortTicket?,
        ) : Finalization
    }

    private data class PendingAbort(
        val id: UUID,
        val handle: ProductionC1ExactBoundStartHandle,
        val lease: ProductionC1ExactBoundStartLease?,
        val runtimeDeviceId: String,
        val pairAuthorityDigest: String,
        val markerDigest: String,
        val generation: ULong,
        val abortOperationId: UUID,
        val abort: suspend (UUID?) -> CompletableDeferred<Throwable?>?,
        var inFlight: Boolean,
        var inFlightCompletion: CompletableDeferred<Throwable?>?,
    )

    private data class PendingAbortTicket(
        val id: UUID,
        val runtimeDeviceId: String,
        val pairAuthorityDigest: String,
        val markerDigest: String,
        val generation: ULong,
        val abortOperationId: UUID,
        val abort: suspend (UUID?) -> CompletableDeferred<Throwable?>?,
    )

    private sealed interface AbortClaim {
        data object Missing : AbortClaim

        data class Invoke(
            val abort: suspend (UUID?) -> CompletableDeferred<Throwable?>?,
            val completion: CompletableDeferred<Throwable?>,
        ) : AbortClaim

        data class Wait(
            val completion: CompletableDeferred<Throwable?>,
        ) : AbortClaim
    }

    private class AbortInvocationContext(
        val abortId: UUID,
    ) : AbstractCoroutineContextElement(Key) {
        companion object Key : CoroutineContext.Key<AbortInvocationContext>
    }

    private val mutex = Mutex()
    private val cancellationCleanupScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private var generation = initialGeneration
    private val recordsByMarker = mutableMapOf<String, LiveRecord>()
    private val liveMarkerByPairAuthority = mutableMapOf<String, String>()
    private val tombstonesByPairAuthority =
        mutableMapOf<String, ArrayDeque<ProductionC1ExactBoundStartTombstone>>()
    private val tombstonedMarkers = mutableSetOf<String>()
    // A pair remains quarantined until its generation-scoped abort succeeds. A failed abort keeps
    // the idempotent callback here so an explicit fence can retry without reopening the pair.
    private val pendingAbortsByPairAuthority = mutableMapOf<String, PendingAbort>()

    @JvmSynthetic
    internal suspend fun admit(
        request: ProductionC1ExactBoundStartRequest,
    ): ProductionC1ExactBoundStartHandle {
        val exactValidator = validator ?: throw ProductionC1ExactBoundStartCoordinatorException(
            ProductionC1ExactBoundStartCoordinatorFailure.FENCED,
        )
        return admit(validationClaim(request)) { exactValidator.validate(request) }
    }

    @JvmSynthetic
    internal suspend fun begin(
        handle: ProductionC1ExactBoundStartHandle,
        request: ProductionC1ExactBoundStartRequest,
        operation: ProductionC1ExactBoundStartOperation,
    ): ProductionC1ExactBoundStartLease {
        val exactValidator = validator ?: throw ProductionC1ExactBoundStartCoordinatorException(
            ProductionC1ExactBoundStartCoordinatorFailure.FENCED,
        )
        return begin(handle, { exactValidator.validate(request) }, operation)
    }

    @JvmSynthetic
    internal suspend fun cancel(handle: ProductionC1ExactBoundStartHandle) =
        cancelWithOrigin(handle, originOperationId = null)

    internal suspend fun cancelFromOperation(
        handle: ProductionC1ExactBoundStartHandle,
        operationId: UUID,
    ) = cancelWithOrigin(handle, operationId)

    private suspend fun cancelWithOrigin(
        handle: ProductionC1ExactBoundStartHandle,
        originOperationId: UUID?,
    ) =
        withContext(NonCancellable) {
            val abort = mutex.withLock {
                val record = exactRecord(handle)
                when {
                    record != null ->
                        terminalize(record, ProductionC1ExactBoundStartTerminalReason.CANCELLED)
                    originOperationId != null ->
                        pendingAbortTicket(handle, originOperationId)
                            ?: throw ProductionC1ExactBoundStartCoordinatorException(
                                ProductionC1ExactBoundStartCoordinatorFailure.INVALID_HANDLE,
                            )
                    else -> throw ProductionC1ExactBoundStartCoordinatorException(
                        ProductionC1ExactBoundStartCoordinatorFailure.INVALID_HANDLE,
                    )
                }
            }
            runAbort(abort, originOperationId)
        }

    @JvmSynthetic
    internal suspend fun cancel(lease: ProductionC1ExactBoundStartLease) =
        cancelWithOrigin(lease, originOperationId = null)

    internal suspend fun cancelFromOperation(
        lease: ProductionC1ExactBoundStartLease,
        operationId: UUID,
    ) = cancelWithOrigin(lease, operationId)

    private suspend fun cancelWithOrigin(
        lease: ProductionC1ExactBoundStartLease,
        originOperationId: UUID?,
    ) =
        withContext(NonCancellable) {
            val abort = mutex.withLock {
                val record = exactRecord(lease)
                when {
                    record != null ->
                        terminalize(record, ProductionC1ExactBoundStartTerminalReason.CANCELLED)
                    originOperationId != null ->
                        pendingAbortTicket(lease, originOperationId)
                            ?: throw ProductionC1ExactBoundStartCoordinatorException(
                                ProductionC1ExactBoundStartCoordinatorFailure.INVALID_LEASE,
                            )
                    else -> throw ProductionC1ExactBoundStartCoordinatorException(
                        ProductionC1ExactBoundStartCoordinatorFailure.INVALID_LEASE,
                    )
                }
            }
            runAbort(abort, originOperationId)
        }

    @JvmSynthetic
    internal suspend fun complete(lease: ProductionC1ExactBoundStartLease) {
        mutex.withLock {
            val record = exactRecord(lease)
            if (record == null || record.phase != Phase.ACTIVE) {
                throw ProductionC1ExactBoundStartCoordinatorException(
                    ProductionC1ExactBoundStartCoordinatorFailure.INVALID_LEASE,
                )
            }
            terminalize(
                record,
                ProductionC1ExactBoundStartTerminalReason.COMPLETED,
                shouldAbort = false,
            )
        }
    }

    @JvmSynthetic
    internal suspend fun complete(handle: ProductionC1ExactBoundStartHandle) {
        mutex.withLock {
            val record = exactRecord(handle)
            if (record == null || record.phase != Phase.ACTIVE) {
                throw ProductionC1ExactBoundStartCoordinatorException(
                    ProductionC1ExactBoundStartCoordinatorFailure.INVALID_HANDLE,
                )
            }
            terminalize(
                record,
                ProductionC1ExactBoundStartTerminalReason.COMPLETED,
                shouldAbort = false,
            )
        }
    }

    @JvmSynthetic
    internal suspend fun assertActive(
        lease: ProductionC1ExactBoundStartLease,
    ) = withContext(NonCancellable) {
        val abort = mutex.withLock {
            val record = exactRecord(lease)
            if (record == null || record.phase != Phase.ACTIVE) {
                throw ProductionC1ExactBoundStartCoordinatorException(
                    ProductionC1ExactBoundStartCoordinatorFailure.INVALID_LEASE,
                )
            }
            if (nowMs() >= record.expiresAtMs) {
                return@withLock terminalize(
                    record,
                    ProductionC1ExactBoundStartTerminalReason.EXPIRED,
                )
            }
            // A successful active assertion is the explicit lease-ownership acknowledgement.
            ownershipTransitionForTesting?.invoke()
            record.leaseCancellationToken = null
            record.leaseCancellationCleanup?.dispose()
            record.leaseCancellationCleanup = null
            null
        }
        if (abort != null) {
            val failure = ProductionC1ExactBoundStartCoordinatorException(
                ProductionC1ExactBoundStartCoordinatorFailure.EXPIRED,
            )
            runAbortPreserving(abort, failure)
            throw failure
        }
    }

    @JvmSynthetic
    internal suspend fun fenceRevoked(pairAuthorityDigest: String) =
        fenceRevokedWithOrigin(pairAuthorityDigest, originOperationId = null)

    internal suspend fun fenceRevokedFromOperation(
        pairAuthorityDigest: String,
        operationId: UUID,
    ) = fenceRevokedWithOrigin(pairAuthorityDigest, operationId)

    private suspend fun fenceRevokedWithOrigin(
        pairAuthorityDigest: String,
        originOperationId: UUID?,
    ) =
        withContext(NonCancellable) {
            val abort = mutex.withLock {
                terminalize(pairAuthorityDigest, ProductionC1ExactBoundStartTerminalReason.REVOKED)
                    ?: pendingAbortTicket(pairAuthorityDigest)
            }
            runAbort(abort, originOperationId)
        }

    @JvmSynthetic
    internal suspend fun fenceAuthorityAdvance(previousPairAuthorityDigest: String) =
        fenceAuthorityAdvanceWithOrigin(
            previousPairAuthorityDigest,
            originOperationId = null,
        )

    internal suspend fun fenceAuthorityAdvanceFromOperation(
        previousPairAuthorityDigest: String,
        operationId: UUID,
    ) = fenceAuthorityAdvanceWithOrigin(previousPairAuthorityDigest, operationId)

    private suspend fun fenceAuthorityAdvanceWithOrigin(
        previousPairAuthorityDigest: String,
        originOperationId: UUID?,
    ) =
        withContext(NonCancellable) {
            val abort = mutex.withLock {
                terminalize(
                    previousPairAuthorityDigest,
                    ProductionC1ExactBoundStartTerminalReason.AUTHORITY_ADVANCED,
                ) ?: pendingAbortTicket(previousPairAuthorityDigest)
            }
            runAbort(abort, originOperationId)
        }

    @JvmSynthetic
    internal suspend fun fenceExpired() = fenceExpiredWithOrigin(originOperationId = null)

    internal suspend fun fenceExpiredFromOperation(operationId: UUID) =
        fenceExpiredWithOrigin(operationId)

    private suspend fun fenceExpiredWithOrigin(originOperationId: UUID?) =
        withContext(NonCancellable) {
            val aborts = mutex.withLock {
                val instant = nowMs()
                val newlyExpired = recordsByMarker.values
                    .filter { instant >= it.expiresAtMs }
                    .mapNotNull {
                        terminalize(it, ProductionC1ExactBoundStartTerminalReason.EXPIRED)
                    }
                val retryable = pendingAbortsByPairAuthority.keys
                    .toList()
                    .mapNotNull(::pendingAbortTicket)
                (newlyExpired + retryable).distinctBy { it.id }
            }
            runAborts(aborts, originOperationId)
        }

    /** Fail-closed fallback when persistence cannot identify which authority bytes committed. */
    internal suspend fun fenceAllUncertainAuthority() = withContext(NonCancellable) {
        val aborts = mutex.withLock {
            val live = recordsByMarker.values.toList().mapNotNull {
                terminalize(it, ProductionC1ExactBoundStartTerminalReason.REVOKED)
            }
            val retryable = pendingAbortsByPairAuthority.keys
                .toList()
                .mapNotNull(::pendingAbortTicket)
            (live + retryable).distinctBy { it.id }
        }
        runAborts(aborts)
    }

    /** Retries every failed cleanup retained by this store-cached coordinator. */
    @JvmSynthetic
    internal suspend fun retryPendingAborts() =
        retryPendingAbortsWithOrigin(originOperationId = null)

    internal suspend fun retryPendingAbortsFromOperation(operationId: UUID) =
        retryPendingAbortsWithOrigin(operationId)

    private suspend fun retryPendingAbortsWithOrigin(originOperationId: UUID?) =
        withContext(NonCancellable) {
            val aborts = mutex.withLock {
                pendingAbortsByPairAuthority.keys
                    .toList()
                    .mapNotNull(::pendingAbortTicket)
            }
            runAborts(aborts, originOperationId)
        }

    private suspend fun admit(
        claimed: ProductionC1ExactBoundStartValidation,
        validate: suspend () -> ProductionC1ExactBoundStartValidation,
    ): ProductionC1ExactBoundStartHandle {
        var reservedHandle: ProductionC1ExactBoundStartHandle? = null
        try {
            val handle = mutex.withLock {
                if (claimed.markerDigest in tombstonedMarkers ||
                    claimed.markerDigest in recordsByMarker
                ) {
                    throw ProductionC1ExactBoundStartCoordinatorException(
                        ProductionC1ExactBoundStartCoordinatorFailure.MARKER_REPLAY,
                    )
                }
                if (recordsByMarker.isNotEmpty()) {
                    throw ProductionC1ExactBoundStartCoordinatorException(
                        ProductionC1ExactBoundStartCoordinatorFailure.PAIR_ALREADY_LIVE,
                    )
                }
                // PairingStore owns one trusted-runtime slot. Cleanup from the displaced authority
                // or device must finish before any replacement authority can start in that store.
                if (pendingAbortsByPairAuthority.isNotEmpty()) {
                    throw ProductionC1ExactBoundStartCoordinatorException(
                        ProductionC1ExactBoundStartCoordinatorFailure.PAIR_CLEANUP_PENDING,
                    )
                }
                val next = (if (generation == ULong.MAX_VALUE) null else generation + 1uL)
                    ?: throw ProductionC1ExactBoundStartCoordinatorException(
                        ProductionC1ExactBoundStartCoordinatorFailure.GENERATION_OVERFLOW,
                    )
                generation = next
                val reserved = ProductionC1ExactBoundStartHandle(
                    generation,
                    claimed.markerDigest,
                    UUID.randomUUID(),
                )
                recordsByMarker[claimed.markerDigest] = LiveRecord(
                    reserved,
                    claimed.runtimeDeviceId,
                    claimed.pairAuthorityDigest,
                    claimed.expiresAtMs,
                    validation = null,
                    lease = null,
                    abortOperationId = null,
                    abort = null,
                    handleCancellationCleanup = null,
                    handleCancellationToken = null,
                    leaseCancellationCleanup = null,
                    leaseCancellationToken = null,
                    phase = Phase.VALIDATING,
                )
                liveMarkerByPairAuthority[claimed.pairAuthorityDigest] = claimed.markerDigest
                reservedHandle = reserved
                reserved
            }
            registerCancellationCleanup(handle)
            val validated = validate()
            currentCoroutineContext().ensureActive()
            val admittedHandle = mutex.withLock {
                val current = exactRecord(handle)
                if (validated != claimed || current == null || current.phase != Phase.VALIDATING) {
                    throw ProductionC1ExactBoundStartCoordinatorException(
                        ProductionC1ExactBoundStartCoordinatorFailure.FENCED,
                    )
                }
                if (nowMs() >= validated.expiresAtMs) {
                    terminalize(current, ProductionC1ExactBoundStartTerminalReason.EXPIRED)
                    throw ProductionC1ExactBoundStartCoordinatorException(
                        ProductionC1ExactBoundStartCoordinatorFailure.EXPIRED,
                    )
                }
                current.validation = validated
                current.phase = Phase.ADMITTED
                handle
            }
            return cancellationSafeHandoff(admittedHandle) { cancelIfPresent(it) }
        } catch (error: Throwable) {
            withContext(NonCancellable) {
                mutex.withLock {
                    val current = reservedHandle?.let { exactRecord(it) }
                    when {
                        error is CancellationException &&
                            (current?.phase == Phase.VALIDATING || current?.phase == Phase.ADMITTED) ->
                            terminalize(current, ProductionC1ExactBoundStartTerminalReason.CANCELLED)
                        current?.phase == Phase.VALIDATING -> releaseWithoutTombstone(current)
                    }
                }
            }
            throw error
        }
    }

    private suspend fun begin(
        handle: ProductionC1ExactBoundStartHandle,
        validate: suspend () -> ProductionC1ExactBoundStartValidation,
        operation: ProductionC1ExactBoundStartOperation,
    ): ProductionC1ExactBoundStartLease {
        val admittedValidation = mutex.withLock {
            val admitted = exactRecord(handle)
            if (admitted == null || admitted.phase != Phase.ADMITTED || admitted.validation == null) {
                throw ProductionC1ExactBoundStartCoordinatorException(
                    ProductionC1ExactBoundStartCoordinatorFailure.INVALID_HANDLE,
                )
            }
            if (nowMs() >= admitted.expiresAtMs) {
                terminalize(admitted, ProductionC1ExactBoundStartTerminalReason.EXPIRED)
                throw ProductionC1ExactBoundStartCoordinatorException(
                    ProductionC1ExactBoundStartCoordinatorFailure.EXPIRED,
                )
            }
            requireNotNull(admitted.validation)
        }

        val validated = try {
            validate().also { currentCoroutineContext().ensureActive() }
        } catch (error: Throwable) {
            withContext(NonCancellable) {
                mutex.withLock {
                    val current = exactRecord(handle)
                    if (current?.phase == Phase.ADMITTED) {
                        terminalize(
                            current,
                            when {
                                error is CancellationException ->
                                    ProductionC1ExactBoundStartTerminalReason.CANCELLED
                                (error as? ProductionC1ExactBoundStartValidationException)?.failure ==
                                    ProductionC1ExactBoundStartValidationFailure.EXPIRED ->
                                    ProductionC1ExactBoundStartTerminalReason.EXPIRED
                                else -> ProductionC1ExactBoundStartTerminalReason.VALIDATION_FAILED
                            },
                        )
                    }
                }
            }
            throw error
        }
        val operationContext = ProductionC1ExactBoundStartOperationContext(
            this,
            operation.operationId,
        )
        val lease = try {
            mutex.withLock {
                val starting = exactRecord(handle)
                if (validated != admittedValidation ||
                    starting == null ||
                    starting.phase != Phase.ADMITTED
                ) {
                    if (starting?.phase == Phase.ADMITTED) {
                        terminalize(
                            starting,
                            ProductionC1ExactBoundStartTerminalReason.VALIDATION_FAILED,
                        )
                    }
                    throw ProductionC1ExactBoundStartCoordinatorException(
                        ProductionC1ExactBoundStartCoordinatorFailure.FENCED,
                    )
                }
                if (nowMs() >= starting.expiresAtMs) {
                    terminalize(starting, ProductionC1ExactBoundStartTerminalReason.EXPIRED)
                    throw ProductionC1ExactBoundStartCoordinatorException(
                        ProductionC1ExactBoundStartCoordinatorFailure.EXPIRED,
                    )
                }
                val reserved = ProductionC1ExactBoundStartLease(
                    handle.generation,
                    handle.markerDigest,
                    UUID.randomUUID(),
                )
                starting.lease = reserved
                starting.abortOperationId = operation.operationId
                starting.abort = { originOperationId ->
                    operation.abort(operationContext, originOperationId)
                }
                starting.phase = Phase.STARTING
                reserved
            }
        } catch (error: Throwable) {
            withContext(NonCancellable) {
                val detached = mutex.withLock {
                    exactRecord(handle)
                        ?.takeIf { it.phase == Phase.ADMITTED || it.phase == Phase.STARTING }
                        ?.let {
                            terminalize(
                                it,
                                if (error is CancellationException) {
                                    ProductionC1ExactBoundStartTerminalReason.CANCELLED
                                } else {
                                    ProductionC1ExactBoundStartTerminalReason.VALIDATION_FAILED
                                },
                            )
                        }
                }
            runAbortPreserving(detached, error)
            }
            throw error
        }

        registerCancellationCleanup(lease)
        try {
            operation.start(operationContext)
        } catch (error: Throwable) {
            withContext(NonCancellable) {
                val detached = mutex.withLock {
                    exactRecord(handle)
                        ?.takeIf { it.phase == Phase.STARTING && it.lease == lease }
                        ?.let {
                            terminalize(
                                it,
                                if (error is CancellationException) {
                                    ProductionC1ExactBoundStartTerminalReason.CANCELLED
                                } else {
                                    ProductionC1ExactBoundStartTerminalReason.START_FAILED
                                },
                            )
                        }
                }
                runAbortPreserving(detached, error)
            }
            throw error
        }

        try {
            val transferred = withContext(NonCancellable) {
                mutex.withLock {
                    val current = exactRecord(handle)
                    current != null && current.phase == Phase.STARTING && current.lease == lease
                }
            }
            if (!transferred) {
                throw ProductionC1ExactBoundStartCoordinatorException(
                    ProductionC1ExactBoundStartCoordinatorFailure.FENCED,
                )
            }
            currentCoroutineContext().ensureActive()
            val postStartValidation = validate()
            currentCoroutineContext().ensureActive()
            val finalLease = withContext(NonCancellable) {
                val final = mutex.withLock {
                    val current = exactRecord(handle)
                    if (current == null || current.phase != Phase.STARTING || current.lease != lease) {
                        return@withLock Finalization.Failed(
                            ProductionC1ExactBoundStartCoordinatorException(
                                ProductionC1ExactBoundStartCoordinatorFailure.FENCED,
                            ),
                            abort = null,
                        )
                    }
                    if (postStartValidation != admittedValidation) {
                        return@withLock Finalization.Failed(
                            ProductionC1ExactBoundStartCoordinatorException(
                                ProductionC1ExactBoundStartCoordinatorFailure.FENCED,
                            ),
                            terminalize(
                                current,
                                ProductionC1ExactBoundStartTerminalReason.VALIDATION_FAILED,
                            ),
                        )
                    }
                    if (nowMs() >= current.expiresAtMs) {
                        return@withLock Finalization.Failed(
                            ProductionC1ExactBoundStartCoordinatorException(
                                ProductionC1ExactBoundStartCoordinatorFailure.EXPIRED,
                            ),
                            terminalize(current, ProductionC1ExactBoundStartTerminalReason.EXPIRED),
                        )
                    }
                    current.phase = Phase.ACTIVE
                    Finalization.Active(lease)
                }
                when (final) {
                    is Finalization.Active -> final.lease
                    is Finalization.Failed -> {
                        runAbortPreserving(final.abort, final.error)
                        throw final.error
                    }
                }
            }
            return cancellationSafeHandoff(finalLease) { cancelIfPresent(it) }
        } catch (error: Throwable) {
            withContext(NonCancellable) {
                val detached = mutex.withLock {
                    val current = exactRecord(handle)
                    if (current?.lease == lease &&
                        (current.phase == Phase.STARTING || current.phase == Phase.ACTIVE)
                    ) {
                        terminalize(
                            current,
                            when {
                                error is CancellationException ->
                                    ProductionC1ExactBoundStartTerminalReason.CANCELLED
                                (error as? ProductionC1ExactBoundStartValidationException)?.failure ==
                                    ProductionC1ExactBoundStartValidationFailure.EXPIRED ->
                                    ProductionC1ExactBoundStartTerminalReason.EXPIRED
                                else -> ProductionC1ExactBoundStartTerminalReason.VALIDATION_FAILED
                            },
                        )
                    } else {
                        null
                    }
                }
                runAbortPreserving(detached, error)
            }
            throw error
        }
    }

    /**
     * Adds the prompt-cancellation handoff used for resource-like coroutine results. If
     * cancellation wins after state publication but before delivery, the continuation callback
     * owns terminalization instead of retaining ownership for the caller Job's later lifetime.
     */
    private suspend inline fun <Value> cancellationSafeHandoff(
        value: Value,
        crossinline cancelIfUndelivered: suspend (Value) -> Unit,
    ): Value {
        val handedOff = suspendCancellableCoroutine { continuation ->
            continuation.resume(value) { _, undelivered, _ ->
                cancellationCleanupScope.launch(start = CoroutineStart.UNDISPATCHED) {
                    runCatching { cancelIfUndelivered(undelivered) }
                }
            }
        }
        handoffReturnedForTesting?.invoke()
        return handedOff
    }

    /**
     * Covers the outer coroutine completion-CAS window that remains after continuation handoff.
     * The registration fires at cancellation start (rather than final Job completion), and is
     * released as soon as begin accepts a handle, assertActive accepts a lease, or the record ends.
     */
    @OptIn(InternalCoroutinesApi::class)
    private suspend fun registerCancellationCleanup(
        handle: ProductionC1ExactBoundStartHandle,
    ) {
        val owner = currentCoroutineContext()[Job] ?: return
        val token = UUID.randomUUID()
        val prepared = withContext(NonCancellable) {
            mutex.withLock {
                exactRecord(handle)?.let { record ->
                    record.handleCancellationCleanup?.dispose()
                    record.handleCancellationCleanup = null
                    record.handleCancellationToken = token
                    true
                } ?: false
            }
        }
        if (!prepared) return
        val registration = owner.invokeOnCompletion(
            onCancelling = true,
            invokeImmediately = true,
        ) { cause ->
            if (cause != null) {
                cancellationCleanupScope.launch(start = CoroutineStart.UNDISPATCHED) {
                    runCatching { cancelIfPresent(handle, token) }
                }
            }
        }
        val retained = withContext(NonCancellable) {
            mutex.withLock {
                exactRecord(handle)?.takeIf {
                    it.handleCancellationToken == token
                }?.let { record ->
                    record.handleCancellationCleanup = registration
                    true
                } ?: false
            }
        }
        if (!retained) registration.dispose()
    }

    @OptIn(InternalCoroutinesApi::class)
    private suspend fun registerCancellationCleanup(
        lease: ProductionC1ExactBoundStartLease,
    ) {
        val owner = currentCoroutineContext()[Job] ?: return
        val token = UUID.randomUUID()
        val prepared = withContext(NonCancellable) {
            mutex.withLock {
                exactRecord(lease)?.let { record ->
                    ownershipTransitionForTesting?.invoke()
                    record.leaseCancellationCleanup?.dispose()
                    record.leaseCancellationCleanup = null
                    record.leaseCancellationToken = token
                    record.handleCancellationToken = null
                    record.handleCancellationCleanup?.dispose()
                    record.handleCancellationCleanup = null
                    true
                } ?: false
            }
        }
        if (!prepared) return
        val registration = owner.invokeOnCompletion(
            onCancelling = true,
            invokeImmediately = true,
        ) { cause ->
            if (cause != null) {
                cancellationCleanupScope.launch(start = CoroutineStart.UNDISPATCHED) {
                    runCatching { cancelIfPresent(lease, token) }
                }
            }
        }
        val retained = withContext(NonCancellable) {
            mutex.withLock {
                exactRecord(lease)?.takeIf {
                    it.leaseCancellationToken == token
                }?.let { record ->
                    record.leaseCancellationCleanup = registration
                    true
                } ?: false
            }
        }
        if (!retained) registration.dispose()
    }

    private suspend fun cancelIfPresent(handle: ProductionC1ExactBoundStartHandle) =
        withContext(NonCancellable) {
            val abort = mutex.withLock {
                exactRecord(handle)?.let {
                    terminalize(it, ProductionC1ExactBoundStartTerminalReason.CANCELLED)
                }
            }
            runAbort(abort)
        }

    private suspend fun cancelIfPresent(
        handle: ProductionC1ExactBoundStartHandle,
        token: UUID,
    ) = withContext(NonCancellable) {
        val abort = mutex.withLock {
            exactRecord(handle)
                ?.takeIf { it.handleCancellationToken == token }
                ?.let { terminalize(it, ProductionC1ExactBoundStartTerminalReason.CANCELLED) }
        }
        runAbort(abort)
    }

    private suspend fun cancelIfPresent(lease: ProductionC1ExactBoundStartLease) =
        withContext(NonCancellable) {
            val abort = mutex.withLock {
                exactRecord(lease)?.let {
                    terminalize(it, ProductionC1ExactBoundStartTerminalReason.CANCELLED)
                }
            }
            runAbort(abort)
        }

    private suspend fun cancelIfPresent(
        lease: ProductionC1ExactBoundStartLease,
        token: UUID,
    ) = withContext(NonCancellable) {
        val abort = mutex.withLock {
            exactRecord(lease)
                ?.takeIf { it.leaseCancellationToken == token }
                ?.let { terminalize(it, ProductionC1ExactBoundStartTerminalReason.CANCELLED) }
        }
        runAbort(abort)
    }

    private fun validationClaim(
        request: ProductionC1ExactBoundStartRequest,
    ): ProductionC1ExactBoundStartValidation = request.token.let { token ->
        ProductionC1ExactBoundStartValidation(
            runtimeDeviceId = request.expectedRuntimeDeviceId,
            pairAuthorityDigest = token.pairAuthorityDigest,
            markerDigest = token.markerDigest,
            admissionId = token.admissionId,
            bindingDigest = token.bindingDigest,
            sessionId = token.sessionId,
            effectiveNotBeforeMs = token.effectiveNotBeforeMs,
            expiresAtMs = token.expiresAtMs,
            pairLocalRevision = token.pairLocalRevision,
            ledgerRevision = token.ledgerRevision,
        )
    }

    private fun exactRecord(handle: ProductionC1ExactBoundStartHandle): LiveRecord? =
        recordsByMarker[handle.markerDigest]?.takeIf { it.handle == handle }

    private fun exactRecord(lease: ProductionC1ExactBoundStartLease): LiveRecord? =
        recordsByMarker[lease.markerDigest]?.takeIf {
            it.handle.generation == lease.generation && it.lease == lease
        }

    private fun terminalize(
        pairAuthorityDigest: String,
        reason: ProductionC1ExactBoundStartTerminalReason,
    ): PendingAbortTicket? {
        val marker = liveMarkerByPairAuthority[pairAuthorityDigest] ?: return null
        return recordsByMarker[marker]?.let { terminalize(it, reason) }
    }

    private fun releaseWithoutTombstone(record: LiveRecord) {
        record.handleCancellationToken = null
        record.handleCancellationCleanup?.dispose()
        record.handleCancellationCleanup = null
        record.leaseCancellationToken = null
        record.leaseCancellationCleanup?.dispose()
        record.leaseCancellationCleanup = null
        recordsByMarker.remove(record.handle.markerDigest)
        if (liveMarkerByPairAuthority[record.pairAuthorityDigest] == record.handle.markerDigest) {
            liveMarkerByPairAuthority.remove(record.pairAuthorityDigest)
        }
    }

    private fun terminalize(
        record: LiveRecord,
        reason: ProductionC1ExactBoundStartTerminalReason,
        shouldAbort: Boolean = true,
    ): PendingAbortTicket? {
        val abort = record.abort.takeIf { shouldAbort }
        val abortOperationId = record.abortOperationId.takeIf { abort != null }
        if (abort != null) {
            check(record.pairAuthorityDigest !in pendingAbortsByPairAuthority) {
                "Production C1 exact-bound pair already has pending cleanup"
            }
        }
        record.abortOperationId = null
        record.abort = null
        releaseWithoutTombstone(record)
        val tombstone = ProductionC1ExactBoundStartTombstone(
            record.pairAuthorityDigest,
            record.handle.markerDigest,
            record.handle.generation,
            reason,
        )
        val pairTombstones = tombstonesByPairAuthority.getOrPut(record.pairAuthorityDigest) {
            ArrayDeque()
        }
        pairTombstones.addLast(tombstone)
        tombstonedMarkers += tombstone.markerDigest
        if (pairTombstones.size > MAXIMUM_TERMINAL_TOMBSTONES_PER_PAIR_SCOPE) {
            val removed = pairTombstones.removeFirst()
            if (tombstonesByPairAuthority.values.none { tombstones ->
                    tombstones.any { it.markerDigest == removed.markerDigest }
                }
            ) {
                tombstonedMarkers -= removed.markerDigest
            }
        }
        if (abort == null) return null
        pendingAbortsByPairAuthority[record.pairAuthorityDigest] = PendingAbort(
            id = UUID.randomUUID(),
            handle = record.handle,
            lease = record.lease,
            runtimeDeviceId = record.runtimeDeviceId,
            pairAuthorityDigest = record.pairAuthorityDigest,
            markerDigest = record.handle.markerDigest,
            generation = record.handle.generation,
            abortOperationId = requireNotNull(abortOperationId),
            abort = abort,
            inFlight = false,
            inFlightCompletion = null,
        )
        return pendingAbortTicket(record.pairAuthorityDigest)
    }

    private fun pendingAbortTicket(pairAuthorityDigest: String): PendingAbortTicket? {
        val pending = pendingAbortsByPairAuthority[pairAuthorityDigest] ?: return null
        return PendingAbortTicket(
            id = pending.id,
            runtimeDeviceId = pending.runtimeDeviceId,
            pairAuthorityDigest = pending.pairAuthorityDigest,
            markerDigest = pending.markerDigest,
            generation = pending.generation,
            abortOperationId = pending.abortOperationId,
            abort = pending.abort,
        )
    }

    private fun pendingAbortTicket(
        handle: ProductionC1ExactBoundStartHandle,
        operationId: UUID,
    ): PendingAbortTicket? = pendingAbortsByPairAuthority.values
        .singleOrNull { it.handle == handle && it.abortOperationId == operationId }
        ?.let { pendingAbortTicket(it.pairAuthorityDigest) }

    private fun pendingAbortTicket(
        lease: ProductionC1ExactBoundStartLease,
        operationId: UUID,
    ): PendingAbortTicket? = pendingAbortsByPairAuthority.values
        .singleOrNull { it.lease == lease && it.abortOperationId == operationId }
        ?.let { pendingAbortTicket(it.pairAuthorityDigest) }

    private suspend fun runAbort(
        abort: PendingAbortTicket?,
        originOperationId: UUID? = null,
    ) {
        if (abort == null) return
        withContext(NonCancellable) {
            val invokingAbortId = currentCoroutineContext()[AbortInvocationContext]?.abortId
            val invokingStartOperationId =
                currentCoroutineContext()[ProductionC1StartInvocationContext]?.operationId
            val claim = mutex.withLock {
                val pending = pendingAbortsByPairAuthority[abort.pairAuthorityDigest]
                if (pending?.id == abort.id &&
                    pending.runtimeDeviceId == abort.runtimeDeviceId &&
                    pending.markerDigest == abort.markerDigest &&
                    pending.generation == abort.generation &&
                    pending.abortOperationId == abort.abortOperationId
                ) {
                    when {
                        !pending.inFlight -> {
                            val completion = CompletableDeferred<Throwable?>()
                            pending.inFlight = true
                            pending.inFlightCompletion = completion
                            AbortClaim.Invoke(pending.abort, completion)
                        }
                        originOperationId == pending.abortOperationId -> AbortClaim.Missing
                        invokingAbortId == pending.id -> AbortClaim.Missing
                        invokingStartOperationId == pending.abortOperationId -> AbortClaim.Missing
                        else -> AbortClaim.Wait(requireNotNull(pending.inFlightCompletion))
                    }
                } else {
                    AbortClaim.Missing
                }
            }
            when (claim) {
                AbortClaim.Missing -> return@withContext
                is AbortClaim.Wait -> claim.completion.await()?.let { throw it }
                is AbortClaim.Invoke -> {
                    val invocation = runCatching {
                        withContext(AbortInvocationContext(abort.id)) {
                            claim.abort(originOperationId)
                        }
                    }
                    val deferredCleanup = invocation.getOrNull()
                    val immediateFailure = invocation.exceptionOrNull()
                    if (immediateFailure == null && deferredCleanup != null) {
                        cancellationCleanupScope.launch(start = CoroutineStart.UNDISPATCHED) {
                            val deferredFailure = try {
                                deferredCleanup.await()
                            } catch (error: Throwable) {
                                error
                            }
                            settleAbort(abort, claim.completion, deferredFailure)
                        }
                        return@withContext
                    }
                    settleAbort(abort, claim.completion, immediateFailure)
                    immediateFailure?.let { throw it }
                }
            }
        }
    }

    private suspend fun settleAbort(
        abort: PendingAbortTicket,
        completion: CompletableDeferred<Throwable?>,
        failure: Throwable?,
    ) = withContext(NonCancellable) {
        mutex.withLock {
            val pending = pendingAbortsByPairAuthority[abort.pairAuthorityDigest]
            if (pending?.id == abort.id &&
                pending.runtimeDeviceId == abort.runtimeDeviceId &&
                pending.markerDigest == abort.markerDigest &&
                pending.generation == abort.generation &&
                pending.abortOperationId == abort.abortOperationId
            ) {
                if (failure == null) {
                    pendingAbortsByPairAuthority.remove(abort.pairAuthorityDigest)
                } else {
                    pending.inFlight = false
                    pending.inFlightCompletion = null
                }
            }
        }
        completion.complete(failure)
    }

    private suspend fun runAbortPreserving(
        abort: PendingAbortTicket?,
        primary: Throwable,
    ) {
        if (abort == null) return
        try {
            runAbort(abort)
        } catch (abortFailure: Throwable) {
            if (abortFailure !== primary) primary.addSuppressed(abortFailure)
        }
    }

    private suspend fun runAborts(
        aborts: List<PendingAbortTicket>,
        originOperationId: UUID? = null,
    ) {
        val failures = withContext(NonCancellable) {
            supervisorScope {
                aborts.map { abort ->
                    async {
                        runCatching { runAbort(abort, originOperationId) }.exceptionOrNull()
                    }
                }.awaitAll().filterNotNull()
            }
        }
        val firstFailure = failures.firstOrNull()
        failures.drop(1).forEach { error ->
            if (error !== firstFailure) requireNotNull(firstFailure).addSuppressed(error)
        }
        firstFailure?.let { throw it }
    }

    internal suspend fun tombstonesForTesting(): List<ProductionC1ExactBoundStartTombstone> =
        mutex.withLock { tombstonesByPairAuthority.values.flatMap { it.toList() } }

    internal suspend fun liveCountForTesting(): Int = mutex.withLock { recordsByMarker.size }

    internal suspend fun pendingAbortCountForTesting(): Int =
        mutex.withLock { pendingAbortsByPairAuthority.size }

    internal suspend fun admitForTesting(
        claimed: ProductionC1ExactBoundStartValidation,
        testingValidator: suspend (ProductionC1ExactBoundStartValidation) ->
            ProductionC1ExactBoundStartValidation,
    ): ProductionC1ExactBoundStartHandle = admit(claimed) { testingValidator(claimed) }

    internal suspend fun beginForTesting(
        handle: ProductionC1ExactBoundStartHandle,
        claimed: ProductionC1ExactBoundStartValidation,
        testingValidator: suspend (ProductionC1ExactBoundStartValidation) ->
            ProductionC1ExactBoundStartValidation,
        start: suspend (ProductionC1ExactBoundStartOperationContext) -> Unit = {},
        abort: suspend (ProductionC1ExactBoundStartOperationContext) -> Unit = {},
    ): ProductionC1ExactBoundStartLease = begin(
        handle,
        { testingValidator(claimed) },
        ProductionC1ExactBoundStartOperation(start, abort),
    )

    companion object {
        internal const val MAXIMUM_TERMINAL_TOMBSTONES_PER_PAIR_SCOPE = 64

        internal fun storeCached(
            store: PairingStore,
            nowMs: () -> ULong,
        ): ProductionC1ExactBoundStartCoordinator = ProductionC1ExactBoundStartCoordinator(
            ProductionC1ExactBoundStartValidator(store::validateProductionC1ExactBoundStart),
            nowMs,
            0uL,
            handoffReturnedForTesting = null,
            ownershipTransitionForTesting = null,
        )

        internal fun forTesting(
            nowMs: () -> ULong,
            initialGeneration: ULong = 0uL,
            handoffReturnedForTesting: (() -> Unit)? = null,
            ownershipTransitionForTesting: (() -> Unit)? = null,
        ): ProductionC1ExactBoundStartCoordinator = ProductionC1ExactBoundStartCoordinator(
            validator = null,
            nowMs = nowMs,
            initialGeneration = initialGeneration,
            handoffReturnedForTesting = handoffReturnedForTesting,
            ownershipTransitionForTesting = ownershipTransitionForTesting,
        )
    }
}
