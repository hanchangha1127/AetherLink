package com.localagentbridge.android.core.protocol.p2pnat

object P2pNatContract {
    private val magicBytes = byteArrayOf('A'.code.toByte(), 'L'.code.toByte(), 'P'.code.toByte(), '1'.code.toByte())
    val MAGIC: ByteArray get() = magicBytes.copyOf()
    const val VERSION: Int = 1
    const val MAX_SEALED_RECORD_BYTES: Int = 16_384
    const val MAX_CANDIDATE_BLOB_BYTES: Int = 8_192
    const val MAX_CANDIDATE_BATCH_BYTES: Int = 8_291
    const val MAX_RELAY_CAPABILITY_BYTES: Int = 404
    const val MAX_IDENTITY_TRANSCRIPT_BYTES: Int = 532
    const val MAX_PATH_RECEIPT_BYTES: Int = 300
    const val MAX_CANDIDATES: Int = 32
    const val RECORD_TTL_MILLIS: Long = 600_000L
    const val CLOCK_SKEW_MILLIS: Long = 30_000L
    const val MAX_REPLAY_ENTRIES: Int = 128
    const val MAX_ATTEMPTS_PER_PAIR: Int = 2
    const val MAX_GLOBAL_ATTEMPTS: Int = 32
    const val MAX_RETRIES: Int = 4
    const val SUITE: String = "aetherlink-p2p-v1"

    fun isFresh(expiresAtMillis: ULong, nowMillis: ULong): Boolean {
        if (expiresAtMillis == 0uL) return false
        val lowerBound = if (nowMillis > CLOCK_SKEW_MILLIS.toULong()) {
            nowMillis - CLOCK_SKEW_MILLIS.toULong()
        } else {
            0uL
        }
        val futureAllowance = RECORD_TTL_MILLIS.toULong() + CLOCK_SKEW_MILLIS.toULong()
        val upperBound = if (nowMillis > ULong.MAX_VALUE - futureAllowance) {
            ULong.MAX_VALUE
        } else {
            nowMillis + futureAllowance
        }
        return expiresAtMillis > lowerBound && expiresAtMillis <= upperBound
    }

    fun isPathValidationFresh(validatedAtMillis: ULong, expiresAtMillis: ULong, nowMillis: ULong): Boolean {
        if (validatedAtMillis == 0uL || expiresAtMillis <= validatedAtMillis) return false
        if (expiresAtMillis - validatedAtMillis > RECORD_TTL_MILLIS.toULong()) return false
        val validationUpperBound = if (nowMillis > ULong.MAX_VALUE - CLOCK_SKEW_MILLIS.toULong()) {
            ULong.MAX_VALUE
        } else {
            nowMillis + CLOCK_SKEW_MILLIS.toULong()
        }
        return validatedAtMillis <= validationUpperBound && isFresh(expiresAtMillis, nowMillis)
    }
}

enum class P2pNatRole(val wireValue: String) {
    CLIENT("client"),
    RUNTIME("runtime");

    companion object {
        fun decode(value: String): P2pNatRole = entries.singleOrNull { it.wireValue == value }
            ?: throw IllegalArgumentException("invalid role")
    }
}

enum class TransportContext(val wireValue: String) {
    DIRECT("direct"),
    RELAY("relay");

    companion object {
        fun decode(value: String): TransportContext = entries.singleOrNull { it.wireValue == value }
            ?: throw IllegalArgumentException("invalid transport context")
    }
}

enum class FallbackReason(val wireValue: String) {
    NONE("none"),
    DIRECT_FAILED("direct_failed"),
    CONSENT_LOST("consent_lost");

    companion object {
        fun decode(value: String): FallbackReason = entries.singleOrNull { it.wireValue == value }
            ?: throw IllegalArgumentException("invalid fallback reason")
    }
}

enum class CandidateKind(val wireValue: Int) {
    HOST(1),
    SERVER_REFLEXIVE(2),
    PEER_REFLEXIVE(3),
    RELAY(4);

    companion object {
        fun decode(value: Int): CandidateKind = entries.singleOrNull { it.wireValue == value }
            ?: throw IllegalArgumentException("invalid candidate kind")
    }
}

enum class AddressFamily(val wireValue: Int, val byteLength: Int) {
    IPV4(4, 4),
    IPV6(6, 16);

    companion object {
        fun decode(value: Int): AddressFamily = entries.singleOrNull { it.wireValue == value }
            ?: throw IllegalArgumentException("invalid address family")
    }
}

class P2pCandidate(
    val kind: CandidateKind,
    val family: AddressFamily,
    val port: Int,
    val priority: UInt,
    foundation: ByteArray,
    address: ByteArray,
) {
    private val foundationBytes: ByteArray = foundation.copyOf()
    private val addressBytes: ByteArray = address.copyOf()
    val foundation: ByteArray get() = foundationBytes.copyOf()
    val address: ByteArray get() = addressBytes.copyOf()

    init {
        require(port in 1024..65_535) { "invalid candidate port" }
        require(foundationBytes.size == 8) { "foundation must be 8 bytes" }
        require(addressBytes.size == family.byteLength) { "address length does not match family" }
    }

    override fun equals(other: Any?): Boolean = other is P2pCandidate &&
        kind == other.kind && family == other.family && port == other.port && priority == other.priority &&
        foundationBytes.contentEquals(other.foundationBytes) && addressBytes.contentEquals(other.addressBytes)

    override fun hashCode(): Int {
        var result = kind.hashCode()
        result = 31 * result + family.hashCode()
        result = 31 * result + port
        result = 31 * result + priority.hashCode()
        result = 31 * result + foundationBytes.contentHashCode()
        return 31 * result + addressBytes.contentHashCode()
    }
}

data class CandidateBatch(
    val sessionId: String,
    val generation: ULong,
    val sequence: ULong,
    val expiresAtMillis: ULong,
    val senderRole: P2pNatRole,
    val candidates: List<P2pCandidate>,
)

class SealedRouteRecord(
    val suite: String = P2pNatContract.SUITE,
    val sessionId: String,
    val pairBindingDigest: String,
    val senderRole: P2pNatRole,
    val generation: ULong,
    val sequence: ULong,
    val expiresAtMillis: ULong,
    val antiReplayNonce: String,
    ephemeralPublicKey: ByteArray,
    sealNonce: ByteArray,
    ciphertext: ByteArray,
) {
    private val ephemeralPublicKeyBytes: ByteArray = ephemeralPublicKey.copyOf()
    private val sealNonceBytes: ByteArray = sealNonce.copyOf()
    private val ciphertextBytes: ByteArray = ciphertext.copyOf()
    val ephemeralPublicKey: ByteArray get() = ephemeralPublicKeyBytes.copyOf()
    val sealNonce: ByteArray get() = sealNonceBytes.copyOf()
    val ciphertext: ByteArray get() = ciphertextBytes.copyOf()
}

data class RelayCapability(
    val suite: String = P2pNatContract.SUITE,
    val sessionId: String,
    val pairBindingDigest: String,
    val clientFingerprint: String,
    val runtimeFingerprint: String,
    val relayServiceDigest: String,
    val expiresAtMillis: ULong,
    val quotaBytes: ULong,
    val capabilityNonce: String,
)

class IdentitySessionTranscript(
    val suite: String = P2pNatContract.SUITE,
    val sessionId: String,
    val pairBindingDigest: String,
    val clientFingerprint: String,
    val runtimeFingerprint: String,
    clientEphemeralKey: ByteArray,
    runtimeEphemeralKey: ByteArray,
    val generation: ULong,
    val pathReceiptDigest: String,
    val transportContext: TransportContext,
    val fallbackReason: FallbackReason,
    val protocolFloor: UInt = 1u,
) {
    private val clientEphemeralKeyBytes: ByteArray = clientEphemeralKey.copyOf()
    private val runtimeEphemeralKeyBytes: ByteArray = runtimeEphemeralKey.copyOf()
    val clientEphemeralKey: ByteArray get() = clientEphemeralKeyBytes.copyOf()
    val runtimeEphemeralKey: ByteArray get() = runtimeEphemeralKeyBytes.copyOf()

    fun digest(): ByteArray = P2pNatCanonicalCodec.sha256(this)

    fun keyConfirmation(key: ByteArray, role: P2pNatRole): ByteArray =
        P2pNatCanonicalCodec.keyConfirmation(this, key, role)
}

data class PathValidationReceipt(
    val sessionId: String,
    val generation: ULong,
    val candidatePairDigest: String,
    val transportContext: TransportContext,
    val clientObservedPathDigest: String,
    val runtimeObservedPathDigest: String,
    val validatedAtMillis: ULong,
    val expiresAtMillis: ULong,
)
