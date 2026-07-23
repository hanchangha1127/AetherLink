package com.localagentbridge.android.runtime

import com.localagentbridge.android.core.pairing.PairingStore
import com.localagentbridge.android.core.pairing.ProductionC1AuthorityBoundSecureSessionCapability
import com.localagentbridge.android.core.pairing.ProductionC1AuthorityBoundSecureSessionStartCapability
import com.localagentbridge.android.core.pairing.ProductionC1EndpointGrantCompoundCommitToken
import com.localagentbridge.android.core.protocol.p2pnat.ProductionSecureSessionEphemeralKey
import com.localagentbridge.android.core.protocol.p2pnat.VerifiedProductionC1CandidateP2PTranscriptBinding
import com.localagentbridge.android.core.protocol.p2pnat.VerifiedProductionC1CandidateP2PTransportDescriptor
import com.localagentbridge.android.core.transport.RuntimeProductionChannelComposer
import com.localagentbridge.android.core.transport.RuntimeProductionChannelComposition
import com.localagentbridge.android.core.transport.RuntimeProductionConnectionRequest
import com.localagentbridge.android.core.transport.RuntimeProductionRawRouteLease
import com.localagentbridge.android.core.transport.RuntimeRouteCandidate
import com.localagentbridge.android.core.transport.PairedRuntimeIdentity
import com.localagentbridge.android.core.transport.PreparedProductionSecureSession
import com.localagentbridge.android.core.transport.PreparedRemoteRuntimeRoute
import com.localagentbridge.android.core.transport.RuntimeRemoteRoutePreparer
import kotlin.coroutines.CoroutineContext
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext

/**
 * One exact, verifier-derived endpoint commit that may be consumed by the app composition path.
 * It owns the same one-shot opaque key whose public point was committed into the verified
 * transcript; generating a replacement during composition would never match that transcript.
 */
internal class AndroidProductionSecureSessionStartMaterial(
    val token: ProductionC1EndpointGrantCompoundCommitToken,
    val binding: VerifiedProductionC1CandidateP2PTranscriptBinding,
    localEphemeralKey: ProductionSecureSessionEphemeralKey,
) {
    private val localEphemeralKeyLease = AndroidProductionEphemeralKeyLease(localEphemeralKey)

    fun beginEphemeralKeyTransfer(
        expectedPublicKeyX963: ByteArray,
    ): AndroidProductionEphemeralKeyTransfer =
        localEphemeralKeyLease.beginTransfer(expectedPublicKeyX963)

    fun discard() = localEphemeralKeyLease.discard()
}

/** The only post-slot owner of a key while PairingStore is accepting it. */
internal class AndroidProductionEphemeralKeyTransfer(
    private val lease: AndroidProductionEphemeralKeyLease,
    private val key: ProductionSecureSessionEphemeralKey,
) {
    suspend fun <Value> complete(
        transfer: suspend (ProductionSecureSessionEphemeralKey) -> Value,
    ): Value = lease.completeTransfer(key, transfer)
}

/** One-use ownership fence around the transcript's opaque client ephemeral key. */
internal class AndroidProductionEphemeralKeyLease(
    private val key: ProductionSecureSessionEphemeralKey,
) {
    private enum class State { AVAILABLE, TRANSFERRING, COMPLETING, TRANSFERRED, DISCARDED }

    private var state = State.AVAILABLE

    suspend fun <Value> transfer(
        expectedPublicKeyX963: ByteArray,
        transfer: suspend (ProductionSecureSessionEphemeralKey) -> Value,
    ): Value = beginTransfer(expectedPublicKeyX963).complete(transfer)

    internal fun beginTransfer(
        expectedPublicKeyX963: ByteArray,
    ): AndroidProductionEphemeralKeyTransfer {
        synchronized(this) {
            check(state == State.AVAILABLE) { "Production ephemeral key was already consumed" }
            state = State.TRANSFERRING
        }
        try {
            check(key.publicKeyX963.contentEquals(expectedPublicKeyX963)) {
                "Production start ephemeral key does not match the verified client transcript"
            }
            return AndroidProductionEphemeralKeyTransfer(this, key)
        } catch (error: Throwable) {
            synchronized(this) {
                if (state == State.TRANSFERRING) state = State.DISCARDED
            }
            key.close()
            throw error
        }
    }

    internal suspend fun <Value> completeTransfer(
        expectedKey: ProductionSecureSessionEphemeralKey,
        transfer: suspend (ProductionSecureSessionEphemeralKey) -> Value,
    ): Value {
        synchronized(this) {
            check(expectedKey === key) { "Production ephemeral key transfer owner mismatch" }
            check(state == State.TRANSFERRING) {
                "Production ephemeral key transfer was already completed or claimed"
            }
            state = State.COMPLETING
        }
        try {
            val value = transfer(key)
            synchronized(this) {
                check(state == State.COMPLETING)
                state = State.TRANSFERRED
            }
            return value
        } catch (error: Throwable) {
            synchronized(this) {
                if (state == State.COMPLETING) state = State.DISCARDED
            }
            key.close()
            throw error
        }
    }

    @Synchronized
    fun discard() {
        if (state != State.AVAILABLE) return
        state = State.DISCARDED
        key.close()
    }

    @get:Synchronized
    internal val isDiscardedForTesting: Boolean get() = state == State.DISCARDED
}

/**
 * Supplies a generation-bound claim for the exact manager-owned connection request. The claim
 * exposes only one narrow PairingStore handoff; raw start material never leaves the slot boundary.
 */
internal interface AndroidProductionRuntimeActivationClaimSource {
    fun claim(
        request: RuntimeProductionConnectionRequest,
    ): AndroidProductionRuntimeActivationClaim

    /** Releases attempt material that was claimed but never transferred to the manager raw lease. */
    fun abandonClaim(request: RuntimeProductionConnectionRequest) = Unit
}

private val androidProductionRuntimeActivationClaimMint = Any()
private val androidProductionRuntimeActivationTestClaimMint = Any()

/** One-use generation capability; its only production operation transfers directly to PairingStore. */
internal class AndroidProductionRuntimeActivationClaim internal constructor(
    private val owner: AndroidProductionRuntimeActivationSlot,
    internal val generation: Long,
    provenance: Any,
) {
    init {
        check(provenance === androidProductionRuntimeActivationClaimMint) {
            "Production activation claim provenance mismatch"
        }
    }

    suspend fun prepareAuthorityBoundStart(
        pairingStore: PairingStore,
    ): ProductionC1AuthorityBoundSecureSessionStartCapability =
        owner.beginPairingStoreTransfer(
            claim = this,
            context = currentCoroutineContext(),
        ).complete(pairingStore)

    internal fun belongsTo(expectedOwner: AndroidProductionRuntimeActivationSlot): Boolean =
        owner === expectedOwner
}

/** State-only generation capability used to prove the same slot race without minting material. */
internal class AndroidProductionRuntimeActivationSlotTestClaim internal constructor(
    private val owner: AndroidProductionRuntimeActivationSlot,
    internal val generation: Long,
    internal val probe: AndroidProductionRuntimeActivationSlotTestProbe,
    provenance: Any,
) {
    init {
        check(provenance === androidProductionRuntimeActivationTestClaimMint) {
            "Production activation test claim provenance mismatch"
        }
    }

    internal fun beginTransfer(context: CoroutineContext): Boolean =
        owner.beginTestingTransfer(this, context)

    internal fun belongsTo(expectedOwner: AndroidProductionRuntimeActivationSlot): Boolean =
        owner === expectedOwner
}

/**
 * Slot ownership has ended, but PairingStore has not necessarily accepted the opaque key yet.
 * This object owns that single transition and closes the key on every failed acceptance path.
 */
internal class AndroidProductionPairingStoreStartTransfer internal constructor(
    private val request: RuntimeProductionConnectionRequest,
    private val material: AndroidProductionSecureSessionStartMaterial,
    private val ephemeralKeyTransfer: AndroidProductionEphemeralKeyTransfer,
) {
    suspend fun complete(
        pairingStore: PairingStore,
    ): ProductionC1AuthorityBoundSecureSessionStartCapability {
        val identity = request.identity
        return ephemeralKeyTransfer.complete { localEphemeralKey ->
            pairingStore.prepareAuthorityBoundProductionSecureSessionStart(
                expectedRuntimeDeviceId = identity.deviceId,
                expectedRuntimeFingerprint = requireNotNull(identity.fingerprint) {
                    "Production runtime fingerprint is required"
                },
                expectedRuntimePublicKey = requireNotNull(identity.publicKeyBase64) {
                    "Production runtime public key is required"
                },
                token = material.token,
                binding = material.binding,
                localEphemeralKey = localEphemeralKey,
            )
        }
    }
}

private interface AndroidProductionRuntimeActivationSlotEntry {
    val effectiveNotBeforeMs: ULong
    val expiresAtMs: ULong

    fun installInto(owner: AndroidProductionRuntimeActivationSlot)

    fun preparedRouteFor(
        owner: AndroidProductionRuntimeActivationSlot,
        identity: PairedRuntimeIdentity,
    ): PreparedRemoteRuntimeRoute?

    fun matches(
        owner: AndroidProductionRuntimeActivationSlot,
        request: RuntimeProductionConnectionRequest,
    ): Boolean

    fun markClaimed(owner: AndroidProductionRuntimeActivationSlot)

    fun beginPairingStoreTransfer(
        owner: AndroidProductionRuntimeActivationSlot,
        request: RuntimeProductionConnectionRequest,
    ): AndroidProductionPairingStoreStartTransfer {
        error("A slot test probe cannot return production start material")
    }

    fun beginTestingTransfer(owner: AndroidProductionRuntimeActivationSlot) {
        error("Verified production activation entries have no testing transfer surface")
    }

    fun discard(owner: AndroidProductionRuntimeActivationSlot?)

    fun isTestingProbe(probe: AndroidProductionRuntimeActivationSlotTestProbe): Boolean = false
}

private class AndroidProductionRuntimeVerifiedSlotEntry(
    private val plan: AndroidProductionRuntimeActivationPlan,
) : AndroidProductionRuntimeActivationSlotEntry {
    override val effectiveNotBeforeMs: ULong get() = plan.effectiveNotBeforeMs
    override val expiresAtMs: ULong get() = plan.expiresAtMs

    override fun installInto(owner: AndroidProductionRuntimeActivationSlot) =
        plan.installInto(owner)

    override fun preparedRouteFor(
        owner: AndroidProductionRuntimeActivationSlot,
        identity: PairedRuntimeIdentity,
    ): PreparedRemoteRuntimeRoute? = plan.preparedRouteFor(owner, identity)

    override fun matches(
        owner: AndroidProductionRuntimeActivationSlot,
        request: RuntimeProductionConnectionRequest,
    ): Boolean = plan.matches(owner, request)

    override fun markClaimed(owner: AndroidProductionRuntimeActivationSlot) =
        plan.markClaimed(owner)

    override fun beginPairingStoreTransfer(
        owner: AndroidProductionRuntimeActivationSlot,
        request: RuntimeProductionConnectionRequest,
    ): AndroidProductionPairingStoreStartTransfer =
        plan.beginPairingStoreTransfer(owner, request)

    override fun discard(owner: AndroidProductionRuntimeActivationSlot?) = plan.discard(owner)
}

/**
 * Narrow state-only test probe. It owns a disposable key but has no API that returns production
 * start material, tokens, bindings, or a verified route descriptor.
 */
internal class AndroidProductionRuntimeActivationSlotTestProbe(
    internal val identity: PairedRuntimeIdentity,
    internal val route: PreparedRemoteRuntimeRoute,
    internal val key: ProductionSecureSessionEphemeralKey,
    internal val effectiveNotBeforeMs: ULong,
    internal val expiresAtMs: ULong,
) {
    private enum class State { FRESH, INSTALLED, CLAIMED, TRANSFERRED, DISCARDED }

    private var state = State.FRESH
    private var owner: AndroidProductionRuntimeActivationSlot? = null

    @Synchronized
    internal fun installInto(owner: AndroidProductionRuntimeActivationSlot) {
        check(state == State.FRESH)
        state = State.INSTALLED
        this.owner = owner
    }

    @Synchronized
    internal fun preparedRouteFor(
        owner: AndroidProductionRuntimeActivationSlot,
        identity: PairedRuntimeIdentity,
    ): PreparedRemoteRuntimeRoute? {
        checkInstalled(owner)
        return route.takeIf { identity == this.identity }
    }

    @Synchronized
    internal fun discard(owner: AndroidProductionRuntimeActivationSlot?) {
        when (state) {
            State.FRESH -> check(owner == null)
            State.INSTALLED, State.CLAIMED -> check(this.owner === owner)
            State.TRANSFERRED, State.DISCARDED -> return
        }
        state = State.DISCARDED
        this.owner = null
        key.close()
    }

    @Synchronized
    internal fun markClaimed(owner: AndroidProductionRuntimeActivationSlot) {
        checkInstalled(owner)
        state = State.CLAIMED
    }

    @Synchronized
    internal fun beginTransfer(owner: AndroidProductionRuntimeActivationSlot) {
        check(state == State.CLAIMED && this.owner === owner)
        state = State.TRANSFERRED
        this.owner = null
    }

    private fun checkInstalled(owner: AndroidProductionRuntimeActivationSlot) {
        check(state == State.INSTALLED && this.owner === owner)
    }
}

private class AndroidProductionRuntimeTestingSlotEntry(
    private val probe: AndroidProductionRuntimeActivationSlotTestProbe,
) : AndroidProductionRuntimeActivationSlotEntry {
    override val effectiveNotBeforeMs: ULong get() = probe.effectiveNotBeforeMs
    override val expiresAtMs: ULong get() = probe.expiresAtMs

    override fun installInto(owner: AndroidProductionRuntimeActivationSlot) =
        probe.installInto(owner)

    override fun preparedRouteFor(
        owner: AndroidProductionRuntimeActivationSlot,
        identity: PairedRuntimeIdentity,
    ): PreparedRemoteRuntimeRoute? = probe.preparedRouteFor(owner, identity)

    override fun matches(
        owner: AndroidProductionRuntimeActivationSlot,
        request: RuntimeProductionConnectionRequest,
    ): Boolean = false

    override fun markClaimed(owner: AndroidProductionRuntimeActivationSlot) =
        probe.markClaimed(owner)

    override fun beginTestingTransfer(owner: AndroidProductionRuntimeActivationSlot) =
        probe.beginTransfer(owner)

    override fun discard(owner: AndroidProductionRuntimeActivationSlot?) = probe.discard(owner)

    override fun isTestingProbe(probe: AndroidProductionRuntimeActivationSlotTestProbe): Boolean =
        this.probe === probe

}

/**
 * Renewable owner of at most one verifier-derived activation plan.
 *
 * Route preparation, claim, and PairingStore handoff share this exact object. A claimed entry
 * remains slot-owned until its generation wins the atomic transfer-start transition. Replacement
 * or close destroys both pending and claimed-before-transfer keys; once transfer starts, the
 * transfer object alone owns failure cleanup and the slot can no longer close that key.
 */
internal class AndroidProductionRuntimeActivationSlot(
    private val currentTimeMillis: () -> Long,
) : RuntimeRemoteRoutePreparer, AndroidProductionRuntimeActivationClaimSource, AutoCloseable {
    private enum class Validity { NOT_YET_VALID, CURRENT, EXPIRED }

    private data class ClaimedEntry(
        val generation: Long,
        val entry: AndroidProductionRuntimeActivationSlotEntry,
        val request: RuntimeProductionConnectionRequest?,
    )

    private var pending: AndroidProductionRuntimeActivationSlotEntry? = null
    private var claimed: ClaimedEntry? = null
    private var nextClaimGeneration = 0L
    private var closed = false

    fun install(plan: AndroidProductionRuntimeActivationPlan) =
        installEntry(AndroidProductionRuntimeVerifiedSlotEntry(plan))

    internal fun installForTesting(probe: AndroidProductionRuntimeActivationSlotTestProbe) =
        installEntry(AndroidProductionRuntimeTestingSlotEntry(probe))

    @Synchronized
    private fun installEntry(entry: AndroidProductionRuntimeActivationSlotEntry) {
        if (closed) {
            entry.discard(owner = null)
            error("Production activation slot is closed")
        }
        entry.installInto(this)
        pending?.discard(this)
        claimed?.entry?.discard(this)
        claimed = null
        pending = entry
    }

    @Synchronized
    override fun prepareRemoteRoutes(identity: PairedRuntimeIdentity): List<PreparedRemoteRuntimeRoute> {
        val entry = pending ?: return emptyList()
        return when (validity(entry)) {
            Validity.NOT_YET_VALID -> emptyList()
            Validity.EXPIRED -> {
                pending = null
                entry.discard(this)
                emptyList()
            }
            Validity.CURRENT -> listOfNotNull(entry.preparedRouteFor(this, identity))
        }
    }

    override fun claim(
        request: RuntimeProductionConnectionRequest,
    ): AndroidProductionRuntimeActivationClaim = synchronized(this) {
        check(!closed) { "Production activation slot is closed" }
        check(claimed == null) { "A production activation claim is already pending transfer" }
        val entry = checkNotNull(pending) { "No production activation plan is pending" }
        when (validity(entry)) {
            Validity.NOT_YET_VALID -> error("Production activation plan is not yet valid")
            Validity.EXPIRED -> {
                pending = null
                entry.discard(this)
                error("Production activation plan expired")
            }
            Validity.CURRENT -> Unit
        }
        check(entry.matches(this, request)) {
            "Production activation request does not match the pending verified plan"
        }
        val generation = nextGeneration()
        pending = null
        entry.markClaimed(this)
        claimed = ClaimedEntry(generation, entry, request)
        AndroidProductionRuntimeActivationClaim(
            owner = this,
            generation = generation,
            provenance = androidProductionRuntimeActivationClaimMint,
        )
    }

    /** Deterministic state-only seam; no production material can be minted from a test probe. */
    @Synchronized
    internal fun claimExpectedEntryForTesting(
        expected: AndroidProductionRuntimeActivationSlotTestProbe,
    ): AndroidProductionRuntimeActivationSlotTestClaim? {
        val entry = pending ?: return null
        if (closed || claimed != null || !entry.isTestingProbe(expected)) return null
        when (validity(entry)) {
            Validity.NOT_YET_VALID -> return null
            Validity.EXPIRED -> {
                pending = null
                entry.discard(this)
                return null
            }
            Validity.CURRENT -> Unit
        }
        val generation = nextGeneration()
        pending = null
        entry.markClaimed(this)
        claimed = ClaimedEntry(generation, entry, request = null)
        return AndroidProductionRuntimeActivationSlotTestClaim(
            owner = this,
            generation = generation,
            probe = expected,
            provenance = androidProductionRuntimeActivationTestClaimMint,
        )
    }

    @Synchronized
    internal fun beginPairingStoreTransfer(
        claim: AndroidProductionRuntimeActivationClaim,
        context: CoroutineContext,
    ): AndroidProductionPairingStoreStartTransfer {
        check(claim.belongsTo(this)) { "Production activation claim belongs to another slot" }
        val active = claimed
        check(
            !closed &&
                active != null &&
                active.generation == claim.generation &&
                active.request != null,
        ) { "Production activation claim is no longer transferable" }
        context.ensureActiveOrDiscard(active)
        return handoffOrDiscard(active) {
            active.entry.beginPairingStoreTransfer(this, active.request)
        }
    }

    @Synchronized
    internal fun beginTestingTransfer(
        claim: AndroidProductionRuntimeActivationSlotTestClaim,
        context: CoroutineContext,
    ): Boolean {
        if (!claim.belongsTo(this)) return false
        val active = claimed ?: return false
        if (
            closed ||
            active.generation != claim.generation ||
            active.request != null ||
            !active.entry.isTestingProbe(claim.probe)
        ) {
            return false
        }
        context.ensureActiveOrDiscard(active)
        handoffOrDiscard(active) {
            active.entry.beginTestingTransfer(this)
            Unit
        }
        return true
    }

    @Synchronized
    override fun close() {
        if (closed) return
        closed = true
        val pendingEntry = pending
        val claimedEntry = claimed?.entry
        pending = null
        claimed = null
        pendingEntry?.discard(this)
        claimedEntry?.discard(this)
    }

    @get:Synchronized
    internal val isClosedForTesting: Boolean get() = closed

    @get:Synchronized
    internal val hasPendingEntryForController: Boolean get() = pending != null

    @Synchronized
    internal fun discardPendingForController() {
        val entry = pending ?: return
        pending = null
        entry.discard(this)
    }

    internal fun usesClock(clock: () -> Long): Boolean = currentTimeMillis === clock

    private fun nextGeneration(): Long {
        check(nextClaimGeneration < Long.MAX_VALUE) {
            "Production activation claim generation exhausted"
        }
        nextClaimGeneration += 1L
        return nextClaimGeneration
    }

    private fun CoroutineContext.ensureActiveOrDiscard(active: ClaimedEntry) {
        try {
            ensureActive()
        } catch (error: Throwable) {
            claimed = null
            active.entry.discard(this@AndroidProductionRuntimeActivationSlot)
            throw error
        }
    }

    private inline fun <Value> handoffOrDiscard(
        active: ClaimedEntry,
        handoff: () -> Value,
    ): Value {
        return try {
            val value = handoff()
            check(claimed === active) { "Production activation claim ownership changed" }
            claimed = null
            value
        } catch (error: Throwable) {
            if (claimed === active) claimed = null
            runCatching { active.entry.discard(this) }
                .exceptionOrNull()
                ?.let(error::addSuppressed)
            throw error
        }
    }

    private fun validity(entry: AndroidProductionRuntimeActivationSlotEntry): Validity {
        val now = currentTimeMillis()
        if (now < 0L) return Validity.NOT_YET_VALID
        val nowMs = now.toULong()
        return when {
            nowMs >= entry.expiresAtMs -> Validity.EXPIRED
            nowMs < entry.effectiveNotBeforeMs -> Validity.NOT_YET_VALID
            else -> Validity.CURRENT
        }
    }
}

/**
 * One verifier-derived app activation plan installed into the renewable slot above. Its prepared
 * route and opaque material remain inseparable, while the slot supplies fresh plans across later
 * reconnect attempts without retaining an expired or replaced private key.
 */
internal class AndroidProductionRuntimeActivationPlan(
    private val identity: PairedRuntimeIdentity,
    token: ProductionC1EndpointGrantCompoundCommitToken,
    binding: VerifiedProductionC1CandidateP2PTranscriptBinding,
    localEphemeralKey: ProductionSecureSessionEphemeralKey,
) {
    private enum class State { FRESH, INSTALLED, CLAIMED, TRANSFERRED, DISCARDED }

    private val material = AndroidProductionSecureSessionStartMaterial(
        token,
        binding,
        localEphemeralKey,
    )
    private val route = try {
        PreparedRemoteRuntimeRoute.PeerToPeer.fromVerifiedCandidate(
            identity = identity,
            binding = binding,
        )
    } catch (error: Throwable) {
        material.discard()
        throw error
    }
    private val expectedSession = requireNotNull(route.productionSession)
    private var state = State.FRESH
    private var owner: AndroidProductionRuntimeActivationSlot? = null

    internal val effectiveNotBeforeMs: ULong = token.effectiveNotBeforeMs
    internal val expiresAtMs: ULong = token.expiresAtMs

    init {
        try {
            val expectedSession = PreparedProductionSecureSession.fromVerifiedCandidate(binding)
            val expectedDescriptor =
                VerifiedProductionC1CandidateP2PTransportDescriptor.fromVerifiedBinding(binding)
            val descriptor = requireNotNull(route.verifiedCandidateDescriptor)
            check(descriptor == expectedDescriptor) {
                "Production activation route descriptor does not match its verified binding"
            }
            check(route.identity == identity)
            check(route.productionSession?.transcript == expectedSession.transcript)
            check(route.productionSession?.routeAuthorization == expectedSession.routeAuthorization)
            check(
                route.productionSession?.expectedObject7Object26BindingId ==
                    expectedSession.expectedObject7Object26BindingId,
            )
            check(route.sessionId == expectedSession.expectedSessionId)
            check(token.sessionId == expectedSession.expectedSessionId)
            check(
                token.connectorInputCommitmentDigest == descriptor.connectorInputCommitmentDigest &&
                    token.effectiveNotBeforeMs == descriptor.effectiveNotBeforeMs &&
                    token.expiresAtMs == descriptor.expiresAtMs &&
                    descriptor.sessionId == expectedSession.expectedSessionId &&
                    descriptor.generation == expectedSession.transcript.generation
            ) { "Production activation token does not match its verified transport descriptor" }
            check(
                token.expiresAtMs ==
                    binding.keyScheduleBinding.grantAuthorization.authorization.expiresAtMs,
            )
            check(
                localEphemeralKey.publicKeyX963.contentEquals(
                    binding.transcript.clientEphemeralPublicKey,
                ),
            )
        } catch (error: Throwable) {
            material.discard()
            throw error
        }
    }

    @Synchronized
    internal fun rawEndpointBinding(): AndroidProductionRuntimeRawEndpointBinding {
        check(state == State.FRESH) {
            "Production activation endpoint can only be bound before installation"
        }
        return AndroidProductionRuntimeRawEndpointBinding(
            identity = identity,
            route = route,
            descriptor = requireNotNull(route.verifiedCandidateDescriptor) {
                "Production activation route requires a verified transport descriptor"
            },
            effectiveNotBeforeMs = effectiveNotBeforeMs,
            expiresAtMs = expiresAtMs,
        )
    }

    @Synchronized
    internal fun installInto(owner: AndroidProductionRuntimeActivationSlot) {
        check(state == State.FRESH) { "Production activation plan is not fresh" }
        state = State.INSTALLED
        this.owner = owner
    }

    @Synchronized
    internal fun preparedRouteFor(
        owner: AndroidProductionRuntimeActivationSlot,
        identity: PairedRuntimeIdentity,
    ): PreparedRemoteRuntimeRoute? {
        checkInstalled(owner)
        return route.takeIf { identity == this.identity }
    }

    @Synchronized
    internal fun matches(
        owner: AndroidProductionRuntimeActivationSlot,
        request: RuntimeProductionConnectionRequest,
    ): Boolean {
        checkInstalled(owner)
        return requestMatches(request)
    }

    @Synchronized
    internal fun markClaimed(owner: AndroidProductionRuntimeActivationSlot) {
        checkInstalled(owner)
        state = State.CLAIMED
    }

    @Synchronized
    internal fun beginPairingStoreTransfer(
        owner: AndroidProductionRuntimeActivationSlot,
        request: RuntimeProductionConnectionRequest,
    ): AndroidProductionPairingStoreStartTransfer {
        checkClaimed(owner)
        check(requestMatches(request)) {
            "Production activation request does not match its verified plan"
        }
        requireExactStartMaterial(request, material)
        val ephemeralTransfer = material.beginEphemeralKeyTransfer(
            material.binding.transcript.clientEphemeralPublicKey,
        )
        state = State.TRANSFERRED
        this.owner = null
        return AndroidProductionPairingStoreStartTransfer(
            request = request,
            material = material,
            ephemeralKeyTransfer = ephemeralTransfer,
        )
    }

    private fun requestMatches(request: RuntimeProductionConnectionRequest): Boolean {
        val candidate = request.route as? RuntimeRouteCandidate.PeerToPeer ?: return false
        return request.identity == identity &&
            candidate.identity == identity &&
            candidate.preparedRoute === route &&
            request.session === expectedSession
    }

    @Synchronized
    internal fun discard(owner: AndroidProductionRuntimeActivationSlot?) {
        when (state) {
            State.FRESH -> check(owner == null) {
                "Fresh production activation plan has no slot owner"
            }
            State.INSTALLED, State.CLAIMED -> check(this.owner === owner) {
                "Production activation plan belongs to another slot"
            }
            State.TRANSFERRED, State.DISCARDED -> return
        }
        state = State.DISCARDED
        this.owner = null
        material.discard()
    }

    private fun checkInstalled(owner: AndroidProductionRuntimeActivationSlot) {
        check(state == State.INSTALLED && this.owner === owner) {
            "Production activation plan is not installed in this slot"
        }
    }

    private fun checkClaimed(owner: AndroidProductionRuntimeActivationSlot) {
        check(state == State.CLAIMED && this.owner === owner) {
            "Production activation plan is not claimed by this slot"
        }
    }
}

/**
 * The Android app's concrete PairingStore -> manager-owned raw lease composition bridge.
 *
 * Capability ownership moves directly from PairingStore to the core transport adapter. Neither a
 * raw channel nor an authority capability is returned to, cached by, or otherwise exposed to the
 * ViewModel. If transfer does not complete, the freshly started authority session is closed in a
 * non-cancellable cleanup before the original failure is rethrown.
 */
internal class AndroidProductionRuntimeChannelComposer(
    private val pairingStore: PairingStore,
    private val claimSource: AndroidProductionRuntimeActivationClaimSource,
) : RuntimeProductionChannelComposer {
    override suspend fun connect(
        request: RuntimeProductionConnectionRequest,
        rawLease: RuntimeProductionRawRouteLease,
    ): RuntimeProductionChannelComposition {
        var capability: ProductionC1AuthorityBoundSecureSessionCapability? = null
        var transferred = false
        try {
            val claim = claimSource.claim(request)
            // Slot ownership remains live after claim. This call checks cancellation and moves the
            // exact generation to the PairingStore transfer owner under the slot's single monitor.
            val startCapability = claim.prepareAuthorityBoundStart(pairingStore)
            capability = pairingStore.beginAuthorityBoundProductionSecureSession(startCapability)
            val composition = rawLease.compose(requireNotNull(capability))
            transferred = true
            return composition
        } catch (error: Throwable) {
            withContext(NonCancellable) {
                runCatching { claimSource.abandonClaim(request) }
                    .exceptionOrNull()
                    ?.let(error::addSuppressed)
                if (!transferred) {
                    runCatching { capability?.close() }
                        .exceptionOrNull()
                        ?.let(error::addSuppressed)
                }
            }
            throw error
        }
    }
}

private fun requireExactStartMaterial(
    request: RuntimeProductionConnectionRequest,
    material: AndroidProductionSecureSessionStartMaterial,
) {
    val route = request.route as? RuntimeRouteCandidate.PeerToPeer
        ?: error("Authority-bound production start requires a P2P direct route")
    val preparedRoute = requireNotNull(route.preparedRoute) {
        "Authority-bound production start requires a prepared P2P route"
    }
    val session = request.session
    val binding = material.binding
    val keyScheduleBinding = binding.keyScheduleBinding
    val token = material.token
    val descriptor = requireNotNull(preparedRoute.verifiedCandidateDescriptor) {
        "Authority-bound production start requires a verified transport descriptor"
    }

    check(request.identity == preparedRoute.identity) {
        "Production start identity does not match its prepared route"
    }
    check(binding.transcript == session.transcript) {
        "Production start transcript does not match the manager request"
    }
    check(keyScheduleBinding.transcript == session.transcript) {
        "Production start key schedule does not match the manager transcript"
    }
    check(
        binding.grant.routeAuthorizations.finalP2PDirect == session.routeAuthorization &&
            keyScheduleBinding.grantAuthorization == binding.grant.grantAuthorization
    ) { "Production start authorization does not match the prepared route" }
    check(
        keyScheduleBinding.object7Object26KdfBindingDigestHex ==
            session.expectedObject7Object26BindingId
    ) { "Production start object-7/object-26 binding mismatch" }
    check(
        token.sessionId == session.expectedSessionId &&
            preparedRoute.sessionId == session.expectedSessionId
    ) { "Production start session ID mismatch" }
    check(token.expiresAtMs == keyScheduleBinding.grantAuthorization.authorization.expiresAtMs) {
        "Production start expiration does not match the verified authorization"
    }
    check(
        token.connectorInputCommitmentDigest == descriptor.connectorInputCommitmentDigest &&
            token.effectiveNotBeforeMs == descriptor.effectiveNotBeforeMs &&
            token.expiresAtMs == descriptor.expiresAtMs &&
            descriptor.sessionId == session.expectedSessionId &&
            descriptor.generation == session.transcript.generation
    ) { "Production start token does not match the verified transport descriptor" }
}
