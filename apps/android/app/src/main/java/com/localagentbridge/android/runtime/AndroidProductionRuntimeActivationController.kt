package com.localagentbridge.android.runtime

import com.localagentbridge.android.core.pairing.PairingStore
import com.localagentbridge.android.core.pairing.ProductionC1EndpointGrantCompoundCommitToken
import com.localagentbridge.android.core.protocol.p2pnat.ProductionSecureSessionEphemeralKey
import com.localagentbridge.android.core.protocol.p2pnat.VerifiedProductionC1CandidateP2PTranscriptBinding
import com.localagentbridge.android.core.protocol.p2pnat.VerifiedProductionC1CandidateP2PTransportDescriptor
import com.localagentbridge.android.core.transport.PairedRuntimeIdentity
import com.localagentbridge.android.core.transport.PreparedRemoteRuntimeRoute
import com.localagentbridge.android.core.transport.RuntimeRawFrameBodyChannel
import com.localagentbridge.android.core.transport.RuntimeRawRouteConnector
import com.localagentbridge.android.core.transport.RuntimeRemoteRoutePreparer
import com.localagentbridge.android.core.transport.RuntimeProductionConnectionRequest
import com.localagentbridge.android.core.transport.RuntimeRouteCandidate
import kotlin.coroutines.CoroutineContext
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive

/** Exact route identity derived by [AndroidProductionRuntimeActivationPlan]. */
internal class AndroidProductionRuntimeRawEndpointBinding(
    val identity: PairedRuntimeIdentity,
    val route: PreparedRemoteRuntimeRoute.PeerToPeer,
    val descriptor: VerifiedProductionC1CandidateP2PTransportDescriptor,
    val effectiveNotBeforeMs: ULong,
    val expiresAtMs: ULong,
) {
    init {
        check(route.identity == identity)
        check(route.verifiedCandidateDescriptor === descriptor)
        check(descriptor.effectiveNotBeforeMs == effectiveNotBeforeMs)
        check(descriptor.expiresAtMs == expiresAtMs)
    }

    fun matches(request: RuntimeProductionConnectionRequest): Boolean {
        val candidate = request.route as? RuntimeRouteCandidate.PeerToPeer ?: return false
        return request.identity == identity &&
            candidate.identity == identity &&
            candidate.preparedRoute === route &&
            route.verifiedCandidateDescriptor === descriptor &&
            request.session === route.productionSession
    }

    fun matches(routeCandidate: RuntimeRouteCandidate): Boolean {
        val candidate = routeCandidate as? RuntimeRouteCandidate.PeerToPeer ?: return false
        val prepared = candidate.preparedRoute ?: return false
        return candidate.identity == identity &&
            prepared === route &&
            prepared.identity == identity &&
            prepared.verifiedCandidateDescriptor === descriptor
    }
}

/**
 * One-use ownership fence around an already-connected raw endpoint supplied by the future P2P
 * stack. This class never opens a socket; it only transfers or closes the injected endpoint.
 */
internal class AndroidProductionPreconnectedRawEndpointClaim private constructor(
    rawChannel: RuntimeRawFrameBodyChannel,
) : AutoCloseable {
    private enum class State { AVAILABLE, TRANSFERRING, TRANSFERRED, DISCARDED }

    private var state = State.AVAILABLE
    private var channel: RuntimeRawFrameBodyChannel? = rawChannel

    fun transfer(): RuntimeRawFrameBodyChannel {
        val connected = synchronized(this) {
            check(state == State.AVAILABLE) { "Production raw endpoint was already consumed" }
            state = State.TRANSFERRING
            checkNotNull(channel).also { channel = null }
        }
        try {
            check(connected.isConnected) { "Production raw endpoint is not connected" }
            synchronized(this) {
                check(state == State.TRANSFERRING)
                state = State.TRANSFERRED
            }
            return connected
        } catch (error: Throwable) {
            synchronized(this) {
                if (state == State.TRANSFERRING) state = State.DISCARDED
            }
            runCatching { connected.close() }
                .exceptionOrNull()
                ?.let(error::addSuppressed)
            throw error
        }
    }

    override fun close() {
        val discarded = synchronized(this) {
            if (state != State.AVAILABLE) return
            state = State.DISCARDED
            channel.also { channel = null }
        }
        discarded?.close()
    }

    @get:Synchronized
    internal val isTransferredForTesting: Boolean get() = state == State.TRANSFERRED

    @get:Synchronized
    internal val isDiscardedForTesting: Boolean get() = state == State.DISCARDED

    companion object {
        fun own(rawChannel: RuntimeRawFrameBodyChannel): AndroidProductionPreconnectedRawEndpointClaim {
            try {
                check(rawChannel.isConnected) {
                    "A preconnected production raw endpoint must already be connected"
                }
            } catch (error: Throwable) {
                runCatching { rawChannel.close() }
                    .exceptionOrNull()
                    ?.let(error::addSuppressed)
                throw error
            }
            return AndroidProductionPreconnectedRawEndpointClaim(rawChannel)
        }
    }
}

private class AndroidProductionRuntimeEndpointRegistration(
    val binding: AndroidProductionRuntimeRawEndpointBinding,
    val claim: AndroidProductionPreconnectedRawEndpointClaim,
) {
    var request: RuntimeProductionConnectionRequest? = null

    fun matches(request: RuntimeProductionConnectionRequest): Boolean = binding.matches(request)

    fun matches(route: RuntimeRouteCandidate): Boolean = binding.matches(route)
}

internal typealias AndroidProductionEndpointGrantAdmitter = suspend (
    expectedRuntimeDeviceId: String,
    expectedRuntimeFingerprint: String,
    expectedRuntimePublicKey: String,
    admissionId: String,
    binding: VerifiedProductionC1CandidateP2PTranscriptBinding,
) -> ProductionC1EndpointGrantCompoundCommitToken

/**
 * App-scoped owner of one verifier-derived activation attempt and its preconnected raw endpoint.
 *
 * The controller deliberately has no networking implementation. A future selected P2P stack must
 * hand in an already-connected, one-use endpoint claim. Until then the normal app graph owns an
 * empty controller and publishes no production route.
 */
internal class AndroidProductionRuntimeActivationController(
    private val pairingStore: PairingStore,
    private val currentTimeMillis: () -> Long,
    private val endpointGrantAdmitter: AndroidProductionEndpointGrantAdmitter =
        { deviceId, fingerprint, publicKey, admissionId, binding ->
            pairingStore.admitVerifiedProductionC1EndpointGrant(
                expectedRuntimeDeviceId = deviceId,
                expectedRuntimeFingerprint = fingerprint,
                expectedRuntimePublicKey = publicKey,
                admissionId = admissionId,
                binding = binding,
            )
        },
) : RuntimeRemoteRoutePreparer,
    AndroidProductionRuntimeActivationClaimSource,
    RuntimeRawRouteConnector,
    AutoCloseable {
    private val stateLock = Any()
    private var activationSlot: AndroidProductionRuntimeActivationSlot? =
        AndroidProductionRuntimeActivationSlot(currentTimeMillis)
    private var pendingEndpoint: AndroidProductionRuntimeEndpointRegistration? = null
    private val claimedEndpoints = mutableListOf<AndroidProductionRuntimeEndpointRegistration>()
    private val startedPublicationAttempts =
        mutableMapOf<Long, StartedPublicationAttempt>()
    private val waitingPublications =
        mutableMapOf<Long, ControllerPublication>()
    private var inFlightPublication: InFlightPublication? = null
    private var latestStartedPublicationGeneration = 0L
    private var closed = false

    /**
     * Durably admits one freshly verified endpoint grant, then atomically publishes its plan and
     * preconnected endpoint. This method assumes ownership of both supplied one-use resources.
     */
    suspend fun publishVerifiedAttempt(
        identity: PairedRuntimeIdentity,
        admissionId: String,
        binding: VerifiedProductionC1CandidateP2PTranscriptBinding,
        localEphemeralKey: ProductionSecureSessionEphemeralKey,
        endpointClaim: AndroidProductionPreconnectedRawEndpointClaim,
    ) {
        val attempt = StartedPublicationAttempt(localEphemeralKey, endpointClaim)
        var publicationGeneration: Long? = null
        try {
            val publicationContext = currentCoroutineContext()
            publicationContext.ensureActive()
            // Generation is assigned before durable admission. An older admission that resumes
            // late can therefore never displace a newer publication attempt.
            val generation = beginPublicationAttempt(attempt)
            publicationGeneration = generation
            val fingerprint = requireNotNull(identity.fingerprint) {
                "Production runtime fingerprint is required"
            }
            val publicKey = requireNotNull(identity.publicKeyBase64) {
                "Production runtime public key is required"
            }
            check(binding.transcript.runtimeIdentityFingerprint == fingerprint) {
                "Production activation identity does not match the verified transcript"
            }
            val token = endpointGrantAdmitter(
                identity.deviceId,
                fingerprint,
                publicKey,
                admissionId,
                binding,
            )
            publicationContext.ensureActive()
            val publication = attempt.buildCandidate { ownedKey, ownedEndpoint ->
                createCandidatePublication(
                    identity = identity,
                    token = token,
                    binding = binding,
                    localEphemeralKey = ownedKey,
                    endpointClaim = ownedEndpoint,
                )
            }
            registerWaitingPublication(generation, attempt, publication)
            replacePublication(
                generation = generation,
                candidate = publication,
                publicationContext = publicationContext,
            )
        } catch (error: Throwable) {
            publicationGeneration?.let { generation ->
                synchronized(stateLock) {
                    if (startedPublicationAttempts[generation] === attempt) {
                        startedPublicationAttempts.remove(generation)
                    }
                }
            }
            closeStartedPublicationAttempt(attempt)?.let(error::addSuppressed)
            throw error
        }
    }

    override fun prepareRemoteRoutes(
        identity: PairedRuntimeIdentity,
    ): List<PreparedRemoteRuntimeRoute> {
        var orphaned: AndroidProductionRuntimeEndpointRegistration? = null
        val routes = synchronized(stateLock) {
            val slot = activationSlot
            if (closed || slot == null) {
                emptyList()
            } else {
                orphaned = discardExpiredPendingLocked(slot)
                val prepared = slot.prepareRemoteRoutes(identity)
                if (pendingEndpoint != null && !slot.hasPendingEntryForController) {
                    orphaned = pendingEndpoint
                    pendingEndpoint = null
                }
                prepared
            }
        }
        orphaned?.claim?.close()
        return routes
    }

    override fun claim(
        request: RuntimeProductionConnectionRequest,
    ): AndroidProductionRuntimeActivationClaim {
        var orphaned: AndroidProductionRuntimeEndpointRegistration? = null
        try {
            return synchronized(stateLock) {
                check(!closed) { "Production activation controller is closed" }
                val slot = checkNotNull(activationSlot) {
                    "Production activation publication is not ready"
                }
                orphaned = discardExpiredPendingLocked(slot)
                orphaned?.let {
                    error("Production activation plan expired")
                }
                val registration = checkNotNull(pendingEndpoint) {
                    "No production raw endpoint is pending"
                }
                check(registration.matches(request)) {
                    "Production raw endpoint does not match the manager-selected route"
                }
                val activationClaim = try {
                    slot.claim(request)
                } catch (error: Throwable) {
                    if (!slot.hasPendingEntryForController) {
                        pendingEndpoint = null
                        orphaned = registration
                    }
                    throw error
                }
                pendingEndpoint = null
                registration.request = request
                claimedEndpoints += registration
                activationClaim
            }
        } catch (error: Throwable) {
            orphaned?.let { registration ->
                runCatching { registration.claim.close() }
                    .exceptionOrNull()
                    ?.let(error::addSuppressed)
            }
            throw error
        }
    }

    override fun abandonClaim(request: RuntimeProductionConnectionRequest) {
        val abandoned = synchronized(stateLock) {
            val index = claimedEndpoints.indexOfFirst { it.request === request }
            if (index < 0) null else claimedEndpoints.removeAt(index)
        }
        abandoned?.claim?.close()
    }

    override suspend fun connect(
        route: RuntimeRouteCandidate,
        timeoutMillis: Int,
    ): RuntimeRawFrameBodyChannel {
        require(timeoutMillis > 0) { "Production raw-route timeout must be positive" }
        currentCoroutineContext().ensureActive()
        // Removing the exact registration is the linearized destructive claim. From this point
        // this coroutine alone owns the endpoint, so no injected channel code runs under stateLock.
        val registration = synchronized(stateLock) {
            check(!closed) { "Production activation controller is closed" }
            val index = claimedEndpoints.indexOfFirst { it.matches(route) }
            check(index >= 0) {
                "No exact production raw endpoint claim matches the selected route"
            }
            claimedEndpoints.removeAt(index)
        }
        return try {
            currentCoroutineContext().ensureActive()
            val now = currentTimeMillis()
            if (
                now < 0L ||
                now.toULong() < registration.binding.effectiveNotBeforeMs ||
                now.toULong() >= registration.binding.expiresAtMs
            ) {
                error("Production raw endpoint is outside its verified validity window")
            }
            registration.claim.transfer()
        } catch (error: Throwable) {
            runCatching { registration.claim.close() }
                .exceptionOrNull()
                ?.let(error::addSuppressed)
            throw error
        }
    }

    override fun close() {
        val snapshot = synchronized(stateLock) {
            if (closed) return
            closed = true
            val current = detachCurrentPublicationLocked()
            val active = inFlightPublication
            inFlightPublication = null
            val started = startedPublicationAttempts.values.toList()
            startedPublicationAttempts.clear()
            val waiting = waitingPublications.values.toList()
            waitingPublications.clear()
            ControllerCloseSnapshot(
                completion = active?.completion,
                startedAttempts = started,
                publications = buildList {
                    add(current)
                    // The active publisher exclusively owns cleanup of its displaced publication.
                    // Taking only its still-private candidate lets close return even when displaced
                    // endpoint cleanup is waiting for this close call to finish.
                    active?.candidate?.let(::add)
                    addAll(waiting)
                },
            )
        }
        snapshot.completion?.complete(Unit)
        val publicationFailure = closePublications(snapshot.publications)
        val startedFailure = closeStartedPublicationAttempts(snapshot.startedAttempts)
        if (publicationFailure != null && startedFailure != null) {
            publicationFailure.addSuppressed(startedFailure)
        }
        (publicationFailure ?: startedFailure)?.let { throw it }
    }

    internal fun usesPairingStore(store: PairingStore): Boolean = pairingStore === store

    internal fun usesClock(clock: () -> Long): Boolean =
        currentTimeMillis === clock

    internal val isClosedForTesting: Boolean
        get() = synchronized(stateLock) { closed }

    internal val pendingEndpointCountForTesting: Int
        get() = synchronized(stateLock) { if (pendingEndpoint == null) 0 else 1 }

    internal val claimedEndpointCountForTesting: Int
        get() = synchronized(stateLock) { claimedEndpoints.size }

    private fun discardExpiredPendingLocked(
        slot: AndroidProductionRuntimeActivationSlot,
    ): AndroidProductionRuntimeEndpointRegistration? {
        val registration = pendingEndpoint ?: return null
        val now = currentTimeMillis()
        if (now < 0L || now.toULong() < registration.binding.expiresAtMs) return null
        pendingEndpoint = null
        slot.discardPendingForController()
        return registration
    }

    private fun beginPublicationAttempt(attempt: StartedPublicationAttempt): Long = synchronized(stateLock) {
        check(!closed) { "Production activation controller is closed" }
        check(latestStartedPublicationGeneration < Long.MAX_VALUE) {
            "Production activation publication generation exhausted"
        }
        latestStartedPublicationGeneration += 1L
        latestStartedPublicationGeneration.also { generation ->
            check(startedPublicationAttempts.put(generation, attempt) == null) {
                "Production activation publication generation was already started"
            }
        }
    }

    private fun registerWaitingPublication(
        generation: Long,
        attempt: StartedPublicationAttempt,
        publication: ControllerPublication,
    ) = synchronized(stateLock) {
        check(!closed) { "Production activation controller is closed" }
        check(generation == latestStartedPublicationGeneration) {
            "Production activation publication was superseded"
        }
        check(startedPublicationAttempts[generation] === attempt) {
            "Production activation publication attempt ownership changed"
        }
        check(!waitingPublications.containsKey(generation)) {
            "Production activation publication generation was already registered"
        }
        val transferred = attempt.transferCandidate(publication)
        startedPublicationAttempts.remove(generation)
        waitingPublications[generation] = transferred
    }

    private fun createCandidatePublication(
        identity: PairedRuntimeIdentity,
        token: ProductionC1EndpointGrantCompoundCommitToken,
        binding: VerifiedProductionC1CandidateP2PTranscriptBinding,
        localEphemeralKey: ProductionSecureSessionEphemeralKey,
        endpointClaim: AndroidProductionPreconnectedRawEndpointClaim,
    ): ControllerPublication {
        var plan: AndroidProductionRuntimeActivationPlan? = null
        var slot: AndroidProductionRuntimeActivationSlot? = null
        try {
            val candidatePlan = AndroidProductionRuntimeActivationPlan(
                identity = identity,
                token = token,
                binding = binding,
                localEphemeralKey = localEphemeralKey,
            )
            plan = candidatePlan
            val registration = AndroidProductionRuntimeEndpointRegistration(
                binding = candidatePlan.rawEndpointBinding(),
                claim = endpointClaim,
            )
            val candidateSlot = AndroidProductionRuntimeActivationSlot(currentTimeMillis)
            slot = candidateSlot
            candidateSlot.install(candidatePlan)
            return ControllerPublication(
                slot = candidateSlot,
                registrations = listOf(registration),
            )
        } catch (error: Throwable) {
            val slotFailure = runCatching { slot?.close() }.exceptionOrNull()
            val planFailure = runCatching { plan?.discard(owner = null) }.exceptionOrNull()
            slotFailure?.let(error::addSuppressed)
            if (planFailure != null && planFailure !== slotFailure) {
                error.addSuppressed(planFailure)
            }
            throw error
        }
    }

    private suspend fun replacePublication(
        generation: Long,
        candidate: ControllerPublication,
        publicationContext: CoroutineContext,
    ) {
        var candidateMovedToFlight = false
        try {
            while (true) {
                publicationContext.ensureActive()
                when (val action = nextPublicationAction(generation, candidate)) {
                    is PublicationAction.Await -> action.completion.await()
                    is PublicationAction.Reject -> throw IllegalStateException(action.reason)
                    is PublicationAction.Start -> {
                        candidateMovedToFlight = true
                        completeInFlightPublication(action.publication, publicationContext)
                        return
                    }
                }
            }
        } catch (error: Throwable) {
            if (!candidateMovedToFlight) {
                val detached = synchronized(stateLock) {
                    if (waitingPublications[generation] === candidate) {
                        waitingPublications.remove(generation)
                    } else {
                        null
                    }
                }
                detached?.let(::closePublication)?.let(error::addSuppressed)
            }
            throw error
        }
    }

    private fun nextPublicationAction(
        generation: Long,
        candidate: ControllerPublication,
    ): PublicationAction = synchronized(stateLock) {
        when {
            closed -> PublicationAction.Reject("Production activation controller is closed")
            generation != latestStartedPublicationGeneration ->
                PublicationAction.Reject("Production activation publication was superseded")
            waitingPublications[generation] !== candidate ->
                PublicationAction.Reject("Production activation publication ownership changed")
            inFlightPublication != null ->
                PublicationAction.Await(checkNotNull(inFlightPublication).completion)
            else -> {
                waitingPublications.remove(generation)
                val publication = InFlightPublication(
                    generation = generation,
                    candidate = candidate,
                    displaced = detachCurrentPublicationLocked(),
                    completion = CompletableDeferred(),
                )
                inFlightPublication = publication
                PublicationAction.Start(publication)
            }
        }
    }

    private fun completeInFlightPublication(
        publication: InFlightPublication,
        publicationContext: CoroutineContext,
    ) {
        // Slot/key/endpoint cleanup is intentionally outside every controller lock. In particular,
        // an injected endpoint close may synchronously call or wait for controller.close().
        val displacedFailure = closePublication(publication.displaced)
        val contextFailure = if (displacedFailure == null) {
            runCatching { publicationContext.ensureActive() }.exceptionOrNull()
        } else {
            null
        }
        val finish = synchronized(stateLock) {
            when {
                inFlightPublication !== publication -> PublicationFinish(
                    failure = displacedFailure ?: contextFailure
                        ?: IllegalStateException("Production activation controller is closed"),
                    publicationsToClose = listOf(publication.candidate),
                )
                displacedFailure != null -> {
                    inFlightPublication = null
                    closed = true
                    val current = detachCurrentPublicationLocked()
                    val waiting = waitingPublications.values.toList()
                    waitingPublications.clear()
                    PublicationFinish(
                        failure = displacedFailure,
                        publicationsToClose = buildList {
                            add(current)
                            add(publication.candidate)
                            addAll(waiting)
                        },
                    )
                }
                contextFailure != null -> {
                    inFlightPublication = null
                    PublicationFinish(
                        failure = contextFailure,
                        publicationsToClose = listOf(publication.candidate),
                    )
                }
                closed -> {
                    inFlightPublication = null
                    PublicationFinish(
                        failure = IllegalStateException("Production activation controller is closed"),
                        publicationsToClose = listOf(publication.candidate),
                    )
                }
                publication.generation != latestStartedPublicationGeneration -> {
                    inFlightPublication = null
                    PublicationFinish(
                        failure = IllegalStateException(
                            "Production activation publication was superseded",
                        ),
                        publicationsToClose = listOf(publication.candidate),
                    )
                }
                activationSlot != null || pendingEndpoint != null || claimedEndpoints.isNotEmpty() -> {
                    inFlightPublication = null
                    closed = true
                    val current = detachCurrentPublicationLocked()
                    val waiting = waitingPublications.values.toList()
                    waitingPublications.clear()
                    PublicationFinish(
                        failure = IllegalStateException(
                            "Production activation publication ownership changed",
                        ),
                        publicationsToClose = buildList {
                            add(current)
                            add(publication.candidate)
                            addAll(waiting)
                        },
                    )
                }
                else -> {
                    activationSlot = checkNotNull(publication.candidate.slot)
                    pendingEndpoint = publication.candidate.registrations.single()
                    inFlightPublication = null
                    PublicationFinish(failure = null, publicationsToClose = emptyList())
                }
            }
        }
        publication.completion.complete(Unit)
        val finalCleanupFailure = closePublications(finish.publicationsToClose)
        val failure = finish.failure
        if (failure != null) {
            finalCleanupFailure?.let(failure::addSuppressed)
            throw failure
        }
        finalCleanupFailure?.let { throw it }
    }

    private fun detachCurrentPublicationLocked(): ControllerPublication {
        val publication = ControllerPublication(
            slot = activationSlot,
            registrations = buildList {
                pendingEndpoint?.let(::add)
                addAll(claimedEndpoints)
            },
        )
        activationSlot = null
        pendingEndpoint = null
        claimedEndpoints.clear()
        return publication
    }

    private sealed interface PublicationAction {
        data class Await(val completion: CompletableDeferred<Unit>) : PublicationAction
        data class Start(val publication: InFlightPublication) : PublicationAction
        data class Reject(val reason: String) : PublicationAction
    }

    private data class InFlightPublication(
        val generation: Long,
        val candidate: ControllerPublication,
        val displaced: ControllerPublication,
        val completion: CompletableDeferred<Unit>,
    )

    private data class PublicationFinish(
        val failure: Throwable?,
        val publicationsToClose: List<ControllerPublication>,
    )

    private data class ControllerCloseSnapshot(
        val completion: CompletableDeferred<Unit>?,
        val startedAttempts: List<StartedPublicationAttempt>,
        val publications: List<ControllerPublication>,
    )

    private data class ControllerPublication(
        val slot: AndroidProductionRuntimeActivationSlot?,
        val registrations: List<AndroidProductionRuntimeEndpointRegistration>,
    )

    private class StartedPublicationAttempt(
        private val localEphemeralKey: ProductionSecureSessionEphemeralKey,
        private val endpointClaim: AndroidProductionPreconnectedRawEndpointClaim,
    ) {
        private enum class State { RAW, CANDIDATE, TRANSFERRED, REVOKED }

        private var state = State.RAW
        private var candidate: ControllerPublication? = null

        @Synchronized
        fun buildCandidate(
            build: (
                ProductionSecureSessionEphemeralKey,
                AndroidProductionPreconnectedRawEndpointClaim,
            ) -> ControllerPublication,
        ): ControllerPublication {
            check(state == State.RAW) { "Production activation attempt was revoked" }
            val publication = build(localEphemeralKey, endpointClaim)
            check(state == State.RAW)
            state = State.CANDIDATE
            candidate = publication
            return publication
        }

        @Synchronized
        fun transferCandidate(expected: ControllerPublication): ControllerPublication {
            check(state == State.CANDIDATE && candidate === expected) {
                "Production activation candidate ownership changed"
            }
            state = State.TRANSFERRED
            candidate = null
            return expected
        }

        @Synchronized
        fun revoke(): StartedPublicationResources? = when (state) {
            State.RAW -> {
                state = State.REVOKED
                StartedPublicationResources.Raw(localEphemeralKey, endpointClaim)
            }
            State.CANDIDATE -> {
                val publication = checkNotNull(candidate)
                candidate = null
                state = State.REVOKED
                StartedPublicationResources.Candidate(publication)
            }
            State.TRANSFERRED, State.REVOKED -> null
        }
    }

    private sealed interface StartedPublicationResources {
        data class Raw(
            val localEphemeralKey: ProductionSecureSessionEphemeralKey,
            val endpointClaim: AndroidProductionPreconnectedRawEndpointClaim,
        ) : StartedPublicationResources

        data class Candidate(
            val publication: ControllerPublication,
        ) : StartedPublicationResources
    }

    private fun closeStartedPublicationAttempts(
        attempts: List<StartedPublicationAttempt>,
    ): Throwable? {
        var firstFailure: Throwable? = null
        attempts.forEach { attempt ->
            closeStartedPublicationAttempt(attempt)?.let { failure ->
                val existingFailure = firstFailure
                if (existingFailure == null) firstFailure = failure else existingFailure.addSuppressed(failure)
            }
        }
        return firstFailure
    }

    private fun closeStartedPublicationAttempt(attempt: StartedPublicationAttempt): Throwable? =
        when (val resources = attempt.revoke()) {
            null -> null
            is StartedPublicationResources.Candidate -> closePublication(resources.publication)
            is StartedPublicationResources.Raw -> {
                val keyFailure = runCatching { resources.localEphemeralKey.close() }.exceptionOrNull()
                val endpointFailure = runCatching { resources.endpointClaim.close() }.exceptionOrNull()
                if (keyFailure != null && endpointFailure != null) {
                    keyFailure.addSuppressed(endpointFailure)
                }
                keyFailure ?: endpointFailure
            }
        }

    private fun closePublications(publications: List<ControllerPublication>): Throwable? {
        var firstFailure: Throwable? = null
        publications.forEach { publication ->
            closePublication(publication)?.let { failure ->
                val existingFailure = firstFailure
                if (existingFailure == null) firstFailure = failure else existingFailure.addSuppressed(failure)
            }
        }
        return firstFailure
    }

    private fun closePublication(publication: ControllerPublication): Throwable? {
        val slotFailure = runCatching { publication.slot?.close() }.exceptionOrNull()
        val endpointFailure = closeRegistrations(publication.registrations)
        if (slotFailure != null && endpointFailure != null) {
            slotFailure.addSuppressed(endpointFailure)
        }
        return slotFailure ?: endpointFailure
    }

    private fun closeRegistrations(
        registrations: List<AndroidProductionRuntimeEndpointRegistration>,
    ): Throwable? {
        var firstFailure: Throwable? = null
        registrations.forEach { registration ->
            runCatching { registration.claim.close() }.exceptionOrNull()?.let { failure ->
                val existingFailure = firstFailure
                if (existingFailure == null) firstFailure = failure else existingFailure.addSuppressed(failure)
            }
        }
        return firstFailure
    }
}
