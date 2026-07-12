package com.localagentbridge.android.core.transport.p2pnat

import com.localagentbridge.android.core.protocol.p2pnat.P2pNatContract
import com.localagentbridge.android.core.protocol.p2pnat.P2pNatRole

class ReplayWindow {
    private data class Scope(val pairBindingDigest: String, val senderRole: P2pNatRole)
    private data class Position(val generation: ULong, val sequence: ULong)
    private data class Entry(
        val scope: Scope,
        val generation: ULong,
        val sequence: ULong,
        val nonce: String,
        val expiresAtMillis: ULong,
    )

    private val entries = ArrayDeque<Entry>()
    private val nonces = HashSet<String>()
    private val positions = HashMap<Scope, Position>()

    @Synchronized
    fun accept(
        pairBindingDigest: String,
        senderRole: P2pNatRole,
        candidateGeneration: ULong,
        candidateSequence: ULong,
        nonce: String,
        expiresAtMillis: ULong,
        nowMillis: ULong,
    ): Boolean {
        purgeExpired(nowMillis)
        if (!PAIR_DIGEST.matches(pairBindingDigest) || candidateGeneration == 0uL || !NONCE.matches(nonce)) return false
        if (expiresAtMillis <= nowMillis || !P2pNatContract.isFresh(expiresAtMillis, nowMillis)) return false
        if (nonces.contains(nonce)) return false
        if (entries.size >= P2pNatContract.MAX_REPLAY_ENTRIES) return false

        val scope = Scope(pairBindingDigest, senderRole)
        val current = positions[scope]
        if (current != null) {
            if (candidateGeneration < current.generation) return false
            if (candidateGeneration == current.generation && candidateSequence <= current.sequence) return false
        }

        positions[scope] = Position(candidateGeneration, candidateSequence)
        entries.addLast(Entry(scope, candidateGeneration, candidateSequence, nonce, expiresAtMillis))
        nonces += nonce
        return true
    }

    @Synchronized
    fun size(nowMillis: ULong): Int {
        purgeExpired(nowMillis)
        return entries.size
    }

    private fun purgeExpired(nowMillis: ULong) {
        if (entries.isEmpty()) return
        val retained = entries.filter { it.expiresAtMillis > nowMillis }
        entries.clear()
        nonces.clear()
        positions.clear()
        retained.forEach {
            entries.addLast(it)
            nonces += it.nonce
            val current = positions[it.scope]
            if (current == null || it.generation > current.generation ||
                (it.generation == current.generation && it.sequence > current.sequence)
            ) {
                positions[it.scope] = Position(it.generation, it.sequence)
            }
        }
    }

    private companion object {
        val PAIR_DIGEST = Regex("[0-9a-f]{64}")
        val NONCE = Regex("[0-9a-f]{32}")
    }
}
