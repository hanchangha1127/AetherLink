package com.localagentbridge.android.core.transport.p2pnat

import com.localagentbridge.android.core.protocol.p2pnat.P2pNatContract

enum class ReadinessState {
    IDLE,
    ATTEMPT_STARTED,
    PATH_REACHABLE,
    IDENTITY_VERIFIED,
    KEY_CONFIRMED,
    APPLICATION_READY,
    FAILED,
}

class ReadinessStateMachine {
    private val attemptsByPair = HashMap<String, Int>()
    private var globalAttempts = 0
    private var retries = 0
    private var activePair: String? = null
    private var activeGeneration: ULong? = null

    var state: ReadinessState = ReadinessState.IDLE
        private set

    @Synchronized
    fun beginAttempt(pairBindingDigest: String, generation: ULong): Boolean {
        if (!PAIR_DIGEST.matches(pairBindingDigest) || generation == 0uL) return fail()
        val previousGeneration = activeGeneration
        if (previousGeneration != null && generation <= previousGeneration) return fail()
        val pairAttempts = attemptsByPair[pairBindingDigest] ?: 0
        if (pairAttempts >= P2pNatContract.MAX_ATTEMPTS_PER_PAIR ||
            globalAttempts >= P2pNatContract.MAX_GLOBAL_ATTEMPTS) return fail()

        attemptsByPair[pairBindingDigest] = pairAttempts + 1
        globalAttempts += 1
        activePair = pairBindingDigest
        activeGeneration = generation
        retries = 0
        state = ReadinessState.ATTEMPT_STARTED
        return true
    }

    @Synchronized
    fun pathReachable(generation: ULong): Boolean = transition(
        generation,
        ReadinessState.ATTEMPT_STARTED,
        ReadinessState.PATH_REACHABLE,
    )

    @Synchronized
    fun identityVerified(generation: ULong): Boolean = transition(
        generation,
        ReadinessState.PATH_REACHABLE,
        ReadinessState.IDENTITY_VERIFIED,
    )

    @Synchronized
    fun keyConfirmed(generation: ULong): Boolean = transition(
        generation,
        ReadinessState.IDENTITY_VERIFIED,
        ReadinessState.KEY_CONFIRMED,
    )

    @Synchronized
    fun applicationReady(generation: ULong): Boolean = transition(
        generation,
        ReadinessState.KEY_CONFIRMED,
        ReadinessState.APPLICATION_READY,
    )

    @Synchronized
    fun retry(generation: ULong): Boolean {
        if (generation != activeGeneration || state == ReadinessState.IDLE ||
            state == ReadinessState.APPLICATION_READY || state == ReadinessState.FAILED) return fail()
        if (retries >= P2pNatContract.MAX_RETRIES) return fail()
        retries += 1
        state = ReadinessState.ATTEMPT_STARTED
        return true
    }

    @Synchronized
    fun fallback(pairBindingDigest: String, generation: ULong): Boolean {
        if (pairBindingDigest != activePair || activeGeneration == null || generation <= activeGeneration!!) return fail()
        return beginAttempt(pairBindingDigest, generation)
    }

    @Synchronized
    fun activeGeneration(): ULong? = activeGeneration

    @Synchronized
    fun activePair(): String? = activePair

    private fun transition(generation: ULong, expected: ReadinessState, next: ReadinessState): Boolean {
        if (generation != activeGeneration || state != expected) return fail()
        state = next
        return true
    }

    private fun fail(): Boolean {
        state = ReadinessState.FAILED
        return false
    }

    private companion object {
        val PAIR_DIGEST = Regex("[0-9a-f]{64}")
    }
}
