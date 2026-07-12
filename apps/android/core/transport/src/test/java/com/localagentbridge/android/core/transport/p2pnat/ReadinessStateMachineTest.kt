package com.localagentbridge.android.core.transport.p2pnat

import com.localagentbridge.android.core.protocol.p2pnat.P2pNatContract
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ReadinessStateMachineTest {
    @Test
    fun reachesApplicationReadyOnlyInExactOrderForOneGeneration() {
        val machine = ReadinessStateMachine()

        assertTrue(machine.beginAttempt(PAIR_A, 1uL))
        assertTrue(machine.pathReachable(1uL))
        assertTrue(machine.identityVerified(1uL))
        assertTrue(machine.keyConfirmed(1uL))
        assertTrue(machine.applicationReady(1uL))
        assertEquals(ReadinessState.APPLICATION_READY, machine.state)
    }

    @Test
    fun outOfOrderAndStaleGenerationFailClosed() {
        val outOfOrder = ReadinessStateMachine()
        assertTrue(outOfOrder.beginAttempt(PAIR_A, 1uL))
        assertFalse(outOfOrder.identityVerified(1uL))
        assertEquals(ReadinessState.FAILED, outOfOrder.state)
        assertFalse(outOfOrder.pathReachable(1uL))

        val stale = ReadinessStateMachine()
        assertTrue(stale.beginAttempt(PAIR_A, 3uL))
        assertFalse(stale.pathReachable(2uL))
        assertEquals(ReadinessState.FAILED, stale.state)
    }

    @Test
    fun fallbackStartsNewGenerationAndResetsProofs() {
        val machine = ReadinessStateMachine()
        assertTrue(machine.beginAttempt(PAIR_A, 1uL))
        assertTrue(machine.pathReachable(1uL))
        assertTrue(machine.identityVerified(1uL))

        assertTrue(machine.fallback(PAIR_A, 2uL))
        assertEquals(ReadinessState.ATTEMPT_STARTED, machine.state)
        assertEquals(2uL, machine.activeGeneration())
        assertFalse(machine.keyConfirmed(2uL))
        assertEquals(ReadinessState.FAILED, machine.state)
    }

    @Test
    fun fallbackCannotSubstitutePairIdentity() {
        val machine = ReadinessStateMachine()
        assertTrue(machine.beginAttempt(PAIR_A, 1uL))
        assertTrue(machine.pathReachable(1uL))
        assertFalse(machine.fallback("b".repeat(64), 2uL))
        assertEquals(ReadinessState.FAILED, machine.state)
        assertEquals(PAIR_A, machine.activePair())
        assertEquals(1uL, machine.activeGeneration())
    }

    @Test
    fun staleFallbackAndAttemptCapsFailClosed() {
        val stale = ReadinessStateMachine()
        assertTrue(stale.beginAttempt(PAIR_A, 2uL))
        assertFalse(stale.fallback(PAIR_A, 2uL))

        val pairCap = ReadinessStateMachine()
        assertTrue(pairCap.beginAttempt(PAIR_A, 1uL))
        assertTrue(pairCap.fallback(PAIR_A, 2uL))
        assertFalse(pairCap.fallback(PAIR_A, 3uL))

        val globalCap = ReadinessStateMachine()
        repeat(P2pNatContract.MAX_GLOBAL_ATTEMPTS) { index ->
            assertTrue(globalCap.beginAttempt(pair(index), (index + 1).toULong()))
        }
        assertFalse(globalCap.beginAttempt(pair(100), 100uL))
    }

    @Test
    fun retryCapResetsProofsAndThenFailsClosed() {
        val machine = ReadinessStateMachine()
        assertTrue(machine.beginAttempt(PAIR_A, 1uL))
        repeat(P2pNatContract.MAX_RETRIES) {
            assertTrue(machine.pathReachable(1uL))
            assertTrue(machine.retry(1uL))
        }
        assertFalse(machine.retry(1uL))
        assertEquals(ReadinessState.FAILED, machine.state)
    }

    private fun pair(index: Int): String = index.toString(16).padStart(64, '0')

    private companion object {
        val PAIR_A = "a".repeat(64)
    }
}
