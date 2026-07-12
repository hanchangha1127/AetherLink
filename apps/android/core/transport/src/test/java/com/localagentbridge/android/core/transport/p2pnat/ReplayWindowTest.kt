package com.localagentbridge.android.core.transport.p2pnat

import com.localagentbridge.android.core.protocol.p2pnat.P2pNatContract
import com.localagentbridge.android.core.protocol.p2pnat.P2pNatRole
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ReplayWindowTest {
    @Test
    fun acceptsOnlyAdvancingScopedPositionWithGloballyFreshNonce() {
        val window = ReplayWindow()

        assertTrue(accept(window, PAIR_A, P2pNatRole.CLIENT, 1uL, 0uL, nonce(1)))
        assertFalse(accept(window, PAIR_A, P2pNatRole.CLIENT, 1uL, 0uL, nonce(2)))
        assertFalse(accept(window, PAIR_A, P2pNatRole.CLIENT, 1uL, 1uL, nonce(1)))
        assertTrue(accept(window, PAIR_A, P2pNatRole.CLIENT, 1uL, 1uL, nonce(2)))
        assertTrue(accept(window, PAIR_B, P2pNatRole.CLIENT, 1uL, 0uL, nonce(3)))
        assertTrue(accept(window, PAIR_A, P2pNatRole.RUNTIME, 1uL, 0uL, nonce(4)))
        assertFalse(accept(window, PAIR_B, P2pNatRole.RUNTIME, 1uL, 0uL, nonce(1)))
        assertFalse(accept(window, PAIR_A, P2pNatRole.CLIENT, 0uL, 100uL, nonce(5)))
        assertTrue(accept(window, PAIR_A, P2pNatRole.CLIENT, 2uL, 0uL, nonce(5)))
        assertFalse(accept(window, PAIR_A, P2pNatRole.CLIENT, 1uL, ULong.MAX_VALUE, nonce(6)))
    }

    @Test
    fun rejectsExpiredExcessiveTtlAndNoncanonicalScopeOrNonce() {
        val window = ReplayWindow()

        assertFalse(accept(window, PAIR_A, P2pNatRole.CLIENT, 1uL, 0uL, nonce(1), expires = 1_000uL))
        assertFalse(accept(window, PAIR_A, P2pNatRole.CLIENT, 1uL, 0uL, nonce(1), expires = 700_001uL))
        assertFalse(accept(window, PAIR_A.uppercase(), P2pNatRole.CLIENT, 1uL, 0uL, nonce(1)))
        assertFalse(accept(window, PAIR_A, P2pNatRole.CLIENT, 1uL, 0uL, "A".repeat(32)))
        assertTrue(accept(window, PAIR_A, P2pNatRole.CLIENT, 1uL, 0uL, nonce(1), expires = 1_001uL))
        assertEquals(1, window.size(1_000uL))
        assertEquals(0, window.size(1_001uL))
    }

    @Test
    fun liveEntryCollectionFailsClosedAtCapWithoutEviction() {
        val window = ReplayWindow()
        repeat(P2pNatContract.MAX_REPLAY_ENTRIES) { index ->
            assertTrue(
                accept(
                    window,
                    pair(index),
                    P2pNatRole.CLIENT,
                    1uL,
                    0uL,
                    nonce(index),
                    expires = 10_000uL,
                ),
            )
        }
        assertFalse(accept(window, pair(999), P2pNatRole.CLIENT, 1uL, 0uL, nonce(999), expires = 10_000uL))
        assertEquals(P2pNatContract.MAX_REPLAY_ENTRIES, window.size(1_000uL))
        assertFalse(accept(window, pair(998), P2pNatRole.CLIENT, 1uL, 0uL, nonce(0), expires = 10_000uL))
    }

    private fun accept(
        window: ReplayWindow,
        pair: String,
        role: P2pNatRole,
        generation: ULong,
        sequence: ULong,
        nonce: String,
        expires: ULong = 2_000uL,
    ): Boolean = window.accept(pair, role, generation, sequence, nonce, expires, 1_000uL)

    private fun nonce(value: Int): String = value.toUInt().toString(16).padStart(32, '0')
    private fun pair(value: Int): String = value.toUInt().toString(16).padStart(64, '0')

    private companion object {
        val PAIR_A = "a".repeat(64)
        val PAIR_B = "b".repeat(64)
    }
}
