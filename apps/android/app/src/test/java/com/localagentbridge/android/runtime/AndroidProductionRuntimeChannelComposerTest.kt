package com.localagentbridge.android.runtime

import com.localagentbridge.android.core.protocol.p2pnat.ProductionSecureSessionEphemeralKey
import com.localagentbridge.android.core.transport.PairedRuntimeIdentity
import com.localagentbridge.android.core.transport.PreparedRemoteRuntimeRoute
import com.localagentbridge.android.core.transport.RemoteRouteSecurityContext
import java.io.IOException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference
import kotlin.concurrent.thread
import kotlin.coroutines.EmptyCoroutineContext
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test

class AndroidProductionRuntimeChannelComposerTest {
    @Test
    fun activationPlanCannotAcceptCallerSelectedPreparedRoute() {
        val constructorParameterTypes = AndroidProductionRuntimeActivationPlan::class.java
            .declaredConstructors
            .flatMap { it.parameterTypes.asList() }

        assertTrue(
            constructorParameterTypes.none {
                PreparedRemoteRuntimeRoute::class.java.isAssignableFrom(it)
            },
        )
    }

    @Test
    fun ephemeralLeaseDiscardsKeyWhenPairingPrepareFails() = runTest {
        val key = ProductionSecureSessionEphemeralKey.generate()
        val lease = AndroidProductionEphemeralKeyLease(key)
        val expectedFailure = IOException("synthetic PairingStore prepare failure")

        val thrown = runCatching {
            lease.transfer(key.publicKeyX963) { transferred ->
                assertSame(key, transferred)
                throw expectedFailure
            }
        }.exceptionOrNull()

        assertSame(expectedFailure, thrown)
        assertTrue(lease.isDiscardedForTesting)
        val replay = runCatching { lease.transfer(key.publicKeyX963) { Unit } }.exceptionOrNull()
        assertTrue(replay is IllegalStateException)
    }

    @Test
    fun ephemeralLeaseRejectsMismatchedTranscriptKeyAndDiscards() = runTest {
        val key = ProductionSecureSessionEphemeralKey.generate()
        val lease = AndroidProductionEphemeralKeyLease(key)
        val wrongPublicKey = key.publicKeyX963.also { it[it.lastIndex] = (it.last() + 1).toByte() }

        val mismatch = runCatching { lease.transfer(wrongPublicKey) { Unit } }.exceptionOrNull()

        assertTrue(mismatch is IllegalStateException)
        assertTrue(lease.isDiscardedForTesting)
    }

    @Test
    fun ephemeralTransferRejectsSequentialDuplicateBeforeCallback() = runTest {
        val key = ProductionSecureSessionEphemeralKey.generate()
        val lease = AndroidProductionEphemeralKeyLease(key)
        val transfer = lease.beginTransfer(key.publicKeyX963)
        val callbackCalls = AtomicInteger(0)

        transfer.complete { callbackCalls.incrementAndGet() }
        val duplicate = runCatching {
            transfer.complete { callbackCalls.incrementAndGet() }
        }.exceptionOrNull()

        assertTrue(duplicate is IllegalStateException)
        assertEquals(1, callbackCalls.get())
        key.close()
    }

    @Test
    fun ephemeralTransferConcurrentCompleteInvokesCallbackExactlyOnce() = runTest {
        val key = ProductionSecureSessionEphemeralKey.generate()
        val lease = AndroidProductionEphemeralKeyLease(key)
        val transfer = lease.beginTransfer(key.publicKeyX963)
        val firstCallbackEntered = CompletableDeferred<Unit>()
        val releaseFirstCallback = CompletableDeferred<Unit>()
        val callbackCalls = AtomicInteger(0)
        val first = async(Dispatchers.Default) {
            transfer.complete {
                callbackCalls.incrementAndGet()
                firstCallbackEntered.complete(Unit)
                releaseFirstCallback.await()
            }
        }
        firstCallbackEntered.await()

        val duplicate = async(Dispatchers.Default) {
            runCatching {
                transfer.complete { callbackCalls.incrementAndGet() }
            }.exceptionOrNull()
        }.await()

        assertTrue(duplicate is IllegalStateException)
        assertEquals(1, callbackCalls.get())
        releaseFirstCallback.complete(Unit)
        first.await()
        assertEquals(1, callbackCalls.get())
        key.close()
    }

    @Test
    fun claimedBeforeTransferCancellationDiscardsSlotOwnedKey() {
        val slot = AndroidProductionRuntimeActivationSlot { 150L }
        val entry = slotTestActivationEntry("cancelled", expiresAtMs = 200uL)
        slot.installForTesting(entry)
        val claim = requireNotNull(slot.claimExpectedEntryForTesting(entry))
        val cancellation = CancellationException("cancelled after slot claim")
        val cancelledOwner = Job().also { it.cancel(cancellation) }

        val thrown = runCatching {
            claim.beginTransfer(cancelledOwner)
        }.exceptionOrNull()

        assertTrue(thrown is CancellationException)
        assertTrue(entry.key.isConsumedOrClosed)

        val fresh = slotTestActivationEntry("after-cancel", expiresAtMs = 300uL)
        slot.installForTesting(fresh)
        assertSame(fresh.route, slot.prepareRemoteRoutes(fresh.identity).single())
        slot.close()
    }

    @Test
    fun activationSlotReplacementSynchronouslyDiscardsOldPendingMaterial() {
        val clock = { 150L }
        val slot = AndroidProductionRuntimeActivationSlot(clock)
        val first = slotTestActivationEntry("first", expiresAtMs = 200uL)
        val second = slotTestActivationEntry("second", expiresAtMs = 300uL)

        slot.installForTesting(first)
        assertSame(first.route, slot.prepareRemoteRoutes(first.identity).single())

        slot.installForTesting(second)

        assertTrue(first.key.isConsumedOrClosed)
        assertFalse(second.key.isConsumedOrClosed)
        assertSame(second.route, slot.prepareRemoteRoutes(second.identity).single())
    }

    @Test
    fun activationSlotSuppressesNotYetValidAndDiscardsAtExpiry() {
        var now = 99L
        val clock = { now }
        val slot = AndroidProductionRuntimeActivationSlot(clock)
        val entry = slotTestActivationEntry(
            label = "windowed",
            effectiveNotBeforeMs = 100uL,
            expiresAtMs = 200uL,
        )
        slot.installForTesting(entry)

        assertTrue(slot.prepareRemoteRoutes(entry.identity).isEmpty())
        assertFalse(entry.key.isConsumedOrClosed)

        now = 100L
        assertSame(entry.route, slot.prepareRemoteRoutes(entry.identity).single())
        assertFalse(entry.key.isConsumedOrClosed)

        now = 200L
        assertTrue(slot.prepareRemoteRoutes(entry.identity).isEmpty())
        assertTrue(entry.key.isConsumedOrClosed)
        assertTrue(slot.prepareRemoteRoutes(entry.identity).isEmpty())
    }

    @Test
    fun activationSlotCloseDiscardsPendingAndRejectsAndDiscardsLaterInstall() {
        val clock = { 150L }
        val slot = AndroidProductionRuntimeActivationSlot(clock)
        val pending = slotTestActivationEntry("pending", expiresAtMs = 200uL)
        slot.installForTesting(pending)

        slot.close()
        slot.close()

        assertTrue(slot.isClosedForTesting)
        assertTrue(pending.key.isConsumedOrClosed)
        val later = slotTestActivationEntry("later", expiresAtMs = 300uL)
        val rejected = runCatching { slot.installForTesting(later) }.exceptionOrNull()
        assertTrue(rejected is IllegalStateException)
        assertTrue(later.key.isConsumedOrClosed)
    }

    @Test
    fun claimedThenCloseDiscardsKeyAndMakesTransferFailClosed() {
        val slot = AndroidProductionRuntimeActivationSlot { 150L }
        val entry = slotTestActivationEntry("claim-close", expiresAtMs = 200uL)
        slot.installForTesting(entry)
        val claim = requireNotNull(slot.claimExpectedEntryForTesting(entry))

        assertFalse(entry.key.isConsumedOrClosed)
        slot.close()

        assertTrue(entry.key.isConsumedOrClosed)
        assertFalse(claim.beginTransfer(EmptyCoroutineContext))
    }

    @Test
    fun claimedThenReplacementDiscardsOldKeyAndKeepsFreshPlan() {
        val slot = AndroidProductionRuntimeActivationSlot { 150L }
        val old = slotTestActivationEntry("claim-replace-old", expiresAtMs = 200uL)
        val fresh = slotTestActivationEntry("claim-replace-fresh", expiresAtMs = 300uL)
        slot.installForTesting(old)
        val oldClaim = requireNotNull(slot.claimExpectedEntryForTesting(old))

        slot.installForTesting(fresh)

        assertTrue(old.key.isConsumedOrClosed)
        assertFalse(oldClaim.beginTransfer(EmptyCoroutineContext))
        assertFalse(fresh.key.isConsumedOrClosed)
        assertSame(fresh.route, slot.prepareRemoteRoutes(fresh.identity).single())
        slot.close()
    }

    @Test
    fun transferFirstMakesCloseLeaveHandedOffKeyAlone() {
        val slot = AndroidProductionRuntimeActivationSlot { 150L }
        val entry = slotTestActivationEntry("transfer-close", expiresAtMs = 200uL)
        slot.installForTesting(entry)
        val claim = requireNotNull(slot.claimExpectedEntryForTesting(entry))

        assertTrue(claim.beginTransfer(EmptyCoroutineContext))
        slot.close()

        assertFalse(entry.key.isConsumedOrClosed)
        entry.key.close()
    }

    @Test
    fun activationSlotClaimsOnlyExpectedEntryAndAcceptsFreshPlanAfterTransfer() {
        val clock = { 150L }
        val slot = AndroidProductionRuntimeActivationSlot(clock)
        val first = slotTestActivationEntry("first", expiresAtMs = 200uL)
        val wrong = slotTestActivationEntry("wrong", expiresAtMs = 200uL)
        slot.installForTesting(first)

        assertNull(slot.claimExpectedEntryForTesting(wrong))
        assertSame(first.route, slot.prepareRemoteRoutes(first.identity).single())
        val firstClaim = requireNotNull(slot.claimExpectedEntryForTesting(first))
        assertTrue(slot.prepareRemoteRoutes(first.identity).isEmpty())
        assertTrue(firstClaim.beginTransfer(EmptyCoroutineContext))
        assertFalse(first.key.isConsumedOrClosed)

        slot.installForTesting(wrong)
        assertSame(wrong.route, slot.prepareRemoteRoutes(wrong.identity).single())
        first.key.close()
        slot.close()
    }

    @Test
    fun closeAndTransferRaceHasExactlyOneLinearizedKeyOwner() {
        repeat(32) { index ->
            val slot = AndroidProductionRuntimeActivationSlot { 150L }
            val entry = slotTestActivationEntry("close-race-$index", expiresAtMs = 200uL)
            slot.installForTesting(entry)
            val claim = requireNotNull(slot.claimExpectedEntryForTesting(entry))
            val transferred = AtomicReference<Boolean?>(null)

            runConcurrentRace(
                first = { transferred.set(claim.beginTransfer(EmptyCoroutineContext)) },
                second = slot::close,
            )

            if (requireNotNull(transferred.get())) {
                assertFalse(entry.key.isConsumedOrClosed)
                entry.key.close()
            } else {
                assertTrue(entry.key.isConsumedOrClosed)
            }
            assertTrue(slot.isClosedForTesting)
        }
    }

    @Test
    fun replacementAndTransferRacePreservesFreshPlanAndOneOldKeyOwner() {
        repeat(32) { index ->
            val slot = AndroidProductionRuntimeActivationSlot { 150L }
            val old = slotTestActivationEntry("replace-race-old-$index", expiresAtMs = 200uL)
            val fresh = slotTestActivationEntry("replace-race-fresh-$index", expiresAtMs = 300uL)
            slot.installForTesting(old)
            val oldClaim = requireNotNull(slot.claimExpectedEntryForTesting(old))
            val transferred = AtomicReference<Boolean?>(null)

            runConcurrentRace(
                first = { transferred.set(oldClaim.beginTransfer(EmptyCoroutineContext)) },
                second = { slot.installForTesting(fresh) },
            )

            if (requireNotNull(transferred.get())) {
                assertFalse(old.key.isConsumedOrClosed)
                old.key.close()
            } else {
                assertTrue(old.key.isConsumedOrClosed)
            }
            assertFalse(fresh.key.isConsumedOrClosed)
            assertSame(fresh.route, slot.prepareRemoteRoutes(fresh.identity).single())
            slot.close()
            assertTrue(fresh.key.isConsumedOrClosed)
        }
    }

    @Test
    fun activationSlotTestClaimSurfaceCannotReturnProductionMaterial() {
        val forbiddenTypeFragments = listOf(
            "SecureSessionStartMaterial",
            "EndpointGrantCompoundCommitToken",
            "VerifiedProductionC1Candidate",
            "PairingStoreStartTransfer",
        )
        val exposedTypes = AndroidProductionRuntimeActivationSlotTestClaim::class.java
            .declaredMethods
            .flatMap { method -> listOf(method.returnType) + method.parameterTypes } +
            AndroidProductionRuntimeActivationSlotTestClaim::class.java
                .declaredConstructors
                .flatMap { constructor -> constructor.parameterTypes.asList() }

        assertTrue(
            exposedTypes.none { type ->
                forbiddenTypeFragments.any(type.name::contains)
            },
        )
    }
}

private fun runConcurrentRace(
    first: () -> Unit,
    second: () -> Unit,
) {
    val ready = CountDownLatch(2)
    val start = CountDownLatch(1)
    val failure = AtomicReference<Throwable?>(null)
    fun runner(block: () -> Unit): Thread = thread(start = true) {
        ready.countDown()
        start.await()
        runCatching(block).exceptionOrNull()?.let { failure.compareAndSet(null, it) }
    }
    val firstThread = runner(first)
    val secondThread = runner(second)
    assertTrue("Race workers did not become ready", ready.await(5L, TimeUnit.SECONDS))
    start.countDown()
    firstThread.join(5_000L)
    secondThread.join(5_000L)
    assertFalse("First race worker did not finish", firstThread.isAlive)
    assertFalse("Second race worker did not finish", secondThread.isAlive)
    failure.get()?.let { throw AssertionError("Race worker failed", it) }
}

internal fun slotTestActivationEntry(
    label: String,
    effectiveNotBeforeMs: ULong = 1uL,
    expiresAtMs: ULong,
): AndroidProductionRuntimeActivationSlotTestProbe {
    val identity = PairedRuntimeIdentity(
        deviceId = "runtime-$label",
        name = "Runtime $label",
    )
    val route = PreparedRemoteRuntimeRoute.PeerToPeer(
        identity = identity,
        sessionId = "session-$label",
        security = RemoteRouteSecurityContext(
            rendezvousToken = "rendezvous-$label",
            expiresAtEpochMillis = expiresAtMs.toLong(),
            antiReplayNonce = "nonce-$label",
        ),
    )
    return AndroidProductionRuntimeActivationSlotTestProbe(
        identity = identity,
        route = route,
        key = ProductionSecureSessionEphemeralKey.generate(),
        effectiveNotBeforeMs = effectiveNotBeforeMs,
        expiresAtMs = expiresAtMs,
    )
}
