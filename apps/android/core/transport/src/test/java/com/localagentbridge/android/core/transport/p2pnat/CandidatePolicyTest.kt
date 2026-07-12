package com.localagentbridge.android.core.transport.p2pnat

import com.localagentbridge.android.core.protocol.p2pnat.AddressFamily
import com.localagentbridge.android.core.protocol.p2pnat.CandidateKind
import com.localagentbridge.android.core.protocol.p2pnat.P2pCandidate
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CandidatePolicyTest {
    @Test
    fun rejectsProhibitedIpv4ClassesUsingRawBytes() {
        val policy = CandidatePolicy()
        listOf(
            v4(0, 0, 0, 0),
            v4(127, 0, 0, 1),
            v4(224, 0, 0, 1),
            v4(239, 255, 255, 255),
            v4(169, 254, 1, 2),
            v4(255, 255, 255, 255),
            v4(10, 0, 0, 1),
            v4(172, 16, 0, 1),
            v4(172, 31, 255, 255),
            v4(192, 168, 1, 1),
        ).forEach { assertFalse(policy.accepts(it)) }

        assertTrue(policy.accepts(v4(8, 8, 8, 8)))
        assertTrue(policy.accepts(v4(172, 32, 0, 1)))
        assertTrue(CandidatePolicy(allowPrivateSameLink = true).accepts(v4(192, 168, 1, 1)))
    }

    @Test
    fun rejectsProhibitedIpv6ClassesUsingRawBytes() {
        val policy = CandidatePolicy()
        val loopback = ByteArray(16).also { it[15] = 1 }
        val multicast = ByteArray(16).also { it[0] = 0xff.toByte() }
        val linkLocal = ByteArray(16).also { it[0] = 0xfe.toByte(); it[1] = 0x80.toByte() }
        val mapped = ByteArray(16).also { it[10] = 0xff.toByte(); it[11] = 0xff.toByte(); it[12] = 8 }
        val privateAddress = ByteArray(16).also { it[0] = 0xfd.toByte(); it[15] = 1 }
        val publicAddress = ByteArray(16).also { it[0] = 0x20; it[1] = 0x01; it[15] = 1 }

        listOf(ByteArray(16), loopback, multicast, linkLocal, mapped, privateAddress).forEach {
            assertFalse(policy.accepts(v6(it)))
        }
        assertTrue(policy.accepts(v6(publicAddress)))
        assertTrue(CandidatePolicy(allowPrivateSameLink = true).accepts(v6(privateAddress)))
    }

    @Test
    fun rejectsDuplicateEmptyAndExcessCandidateSets() {
        val policy = CandidatePolicy()
        val candidate = v4(8, 8, 8, 8)

        assertFalse(policy.accepts(emptyList()))
        assertFalse(policy.accepts(listOf(candidate, candidate)))
        assertFalse(policy.accepts(List(33) { index -> v4(8, 8, index / 256, index % 256) }))
        assertTrue(policy.accepts(listOf(candidate)))
    }

    private fun v4(a: Int, b: Int, c: Int, d: Int) = candidate(
        AddressFamily.IPV4,
        byteArrayOf(a.toByte(), b.toByte(), c.toByte(), d.toByte()),
    )

    private fun v6(address: ByteArray) = candidate(AddressFamily.IPV6, address)

    private fun candidate(family: AddressFamily, address: ByteArray) = P2pCandidate(
        kind = CandidateKind.HOST,
        family = family,
        port = 10_000,
        priority = 1u,
        foundation = ByteArray(8) { 1 },
        address = address,
    )
}
