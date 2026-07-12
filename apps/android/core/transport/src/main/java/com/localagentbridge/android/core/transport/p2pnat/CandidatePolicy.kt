package com.localagentbridge.android.core.transport.p2pnat

import com.localagentbridge.android.core.protocol.p2pnat.AddressFamily
import com.localagentbridge.android.core.protocol.p2pnat.P2pCandidate
import com.localagentbridge.android.core.protocol.p2pnat.P2pNatContract

class CandidatePolicy(private val allowPrivateSameLink: Boolean = false) {
    fun accepts(candidates: List<P2pCandidate>): Boolean {
        if (candidates.size !in 1..P2pNatContract.MAX_CANDIDATES) return false
        if (candidates.distinct().size != candidates.size) return false
        return candidates.all(::accepts)
    }

    fun accepts(candidate: P2pCandidate): Boolean {
        val address = candidate.address
        return when (candidate.family) {
            AddressFamily.IPV4 -> acceptsIpv4(address)
            AddressFamily.IPV6 -> acceptsIpv6(address)
        }
    }

    private fun acceptsIpv4(address: ByteArray): Boolean {
        if (address.size != 4) return false
        val first = address[0].unsigned()
        val second = address[1].unsigned()
        if (address.all { it == 0.toByte() }) return false
        if (first == 127) return false
        if (first in 224..239) return false
        if (first == 169 && second == 254) return false
        if (address.all { it == 0xff.toByte() }) return false
        val privateAddress = first == 10 ||
            (first == 172 && second in 16..31) ||
            (first == 192 && second == 168)
        return !privateAddress || allowPrivateSameLink
    }

    private fun acceptsIpv6(address: ByteArray): Boolean {
        if (address.size != 16) return false
        if (address.all { it == 0.toByte() }) return false
        if (address.dropLast(1).all { it == 0.toByte() } && address.last() == 1.toByte()) return false
        val first = address[0].unsigned()
        val second = address[1].unsigned()
        if (first == 0xff) return false
        if (first == 0xfe && (second and 0xc0) == 0x80) return false
        if (address.copyOfRange(0, 10).all { it == 0.toByte() } &&
            address[10] == 0xff.toByte() && address[11] == 0xff.toByte()) return false
        val privateAddress = (first and 0xfe) == 0xfc
        return !privateAddress || allowPrivateSameLink
    }

    private fun Byte.unsigned(): Int = toInt() and 0xff
}
