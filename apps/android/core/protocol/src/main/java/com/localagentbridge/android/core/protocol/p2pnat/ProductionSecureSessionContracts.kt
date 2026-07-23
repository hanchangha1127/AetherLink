package com.localagentbridge.android.core.protocol.p2pnat

import java.io.ByteArrayOutputStream
import java.math.BigInteger
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest

object ProductionSecureSessionContract {
    private val magicBytes = byteArrayOf(
        'A'.code.toByte(),
        'L'.code.toByte(),
        'S'.code.toByte(),
        '1'.code.toByte(),
    )

    val MAGIC: ByteArray get() = magicBytes.copyOf()
    const val VERSION: Int = 1
    const val MAX_ROUTE_BYTES: Int = 512
    const val MAX_TRANSCRIPT_BYTES: Int = 1_024
    const val SUITE: String = "aetherlink-secure-session-v1"
    const val PROFILE: String = "p256_hkdf_sha256_aes256gcm_v1"
}

enum class ProductionRouteAuthorizationKind(
    val wireValue: String,
    internal val objectType: Int,
) {
    LOCAL_DIRECT("local_direct", 1),
    P2P_PUBLISH("p2p_publish", 2),
    P2P_FETCH("p2p_fetch", 3),
    P2P_DIRECT("p2p_direct", 4),
    TURN_RELAY("turn_relay", 5),
    SEALED_RELAY("sealed_relay", 6);

    companion object {
        fun decode(value: String): ProductionRouteAuthorizationKind =
            entries.singleOrNull { it.wireValue == value }
                ?: throw IllegalArgumentException("invalid production route authorization kind")

        internal fun decodeObjectType(value: Int): ProductionRouteAuthorizationKind =
            entries.singleOrNull { it.objectType == value }
                ?: throw IllegalArgumentException("invalid production route authorization object type")
    }
}

sealed interface ProductionRouteAuthorization {
    val kind: ProductionRouteAuthorizationKind
    val pairBindingDigest: String
    val pairEpoch: ULong
    val generation: ULong?
}

data class LocalDirectRouteAuthorization(
    override val pairBindingDigest: String,
    override val pairEpoch: ULong,
    val nominatedPathReceiptDigest: String,
) : ProductionRouteAuthorization {
    override val kind: ProductionRouteAuthorizationKind = ProductionRouteAuthorizationKind.LOCAL_DIRECT
    override val generation: ULong? = null
}

data class P2pPublishRouteAuthorization(
    override val pairBindingDigest: String,
    override val pairEpoch: ULong,
    override val generation: ULong,
    val candidateBatchDigest: String,
    val publishCapabilityDigest: String,
) : ProductionRouteAuthorization {
    override val kind: ProductionRouteAuthorizationKind = ProductionRouteAuthorizationKind.P2P_PUBLISH
}

data class P2pFetchRouteAuthorization(
    override val pairBindingDigest: String,
    override val pairEpoch: ULong,
    override val generation: ULong,
    val candidateBatchDigest: String,
    val fetchCapabilityDigest: String,
) : ProductionRouteAuthorization {
    override val kind: ProductionRouteAuthorizationKind = ProductionRouteAuthorizationKind.P2P_FETCH
}

data class P2pDirectRouteAuthorization(
    override val pairBindingDigest: String,
    override val pairEpoch: ULong,
    override val generation: ULong,
    val candidatePairDigest: String,
    val pathValidationReceiptDigest: String,
    val publishCapabilityDigest: String,
    val fetchCapabilityDigest: String,
) : ProductionRouteAuthorization {
    override val kind: ProductionRouteAuthorizationKind = ProductionRouteAuthorizationKind.P2P_DIRECT
}

data class TurnRelayRouteAuthorization(
    override val pairBindingDigest: String,
    override val pairEpoch: ULong,
    override val generation: ULong,
    val leaseDigest: String,
    val allocationDigest: String,
    val pathValidationReceiptDigest: String,
) : ProductionRouteAuthorization {
    override val kind: ProductionRouteAuthorizationKind = ProductionRouteAuthorizationKind.TURN_RELAY
}

data class SealedRelayRouteAuthorization(
    override val pairBindingDigest: String,
    override val pairEpoch: ULong,
    override val generation: ULong,
    val leaseDigest: String,
    val allocationDigest: String,
    val pathValidationReceiptDigest: String,
) : ProductionRouteAuthorization {
    override val kind: ProductionRouteAuthorizationKind = ProductionRouteAuthorizationKind.SEALED_RELAY
}

class ProductionSecureSessionTranscript(
    val sessionId: String,
    val pairBindingDigest: String,
    val pairEpoch: ULong,
    val clientIdentityFingerprint: String,
    val runtimeIdentityFingerprint: String,
    clientEphemeralPublicKey: ByteArray,
    runtimeEphemeralPublicKey: ByteArray,
    val clientNonce: String,
    val runtimeNonce: String,
    val generation: ULong,
    val serviceConfigVersion: ULong,
    val keysetVersion: ULong,
    val revocationCounter: ULong,
    val protocolVersion: UInt = 1u,
    val minimumProtocolVersion: UInt = 1u,
    val profile: String = ProductionSecureSessionContract.PROFILE,
    val routeAuthorizationKind: ProductionRouteAuthorizationKind,
    val routeAuthorizationDigest: String,
    val suite: String = ProductionSecureSessionContract.SUITE,
) {
    private val clientEphemeralPublicKeyBytes = clientEphemeralPublicKey.copyOf()
    private val runtimeEphemeralPublicKeyBytes = runtimeEphemeralPublicKey.copyOf()

    val clientEphemeralPublicKey: ByteArray get() = clientEphemeralPublicKeyBytes.copyOf()
    val runtimeEphemeralPublicKey: ByteArray get() = runtimeEphemeralPublicKeyBytes.copyOf()

    init {
        ProductionSecureSessionCodec.validateTranscript(this)
    }

    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (other !is ProductionSecureSessionTranscript) return false
        return sessionId == other.sessionId &&
            pairBindingDigest == other.pairBindingDigest &&
            pairEpoch == other.pairEpoch &&
            clientIdentityFingerprint == other.clientIdentityFingerprint &&
            runtimeIdentityFingerprint == other.runtimeIdentityFingerprint &&
            clientEphemeralPublicKeyBytes.contentEquals(other.clientEphemeralPublicKeyBytes) &&
            runtimeEphemeralPublicKeyBytes.contentEquals(other.runtimeEphemeralPublicKeyBytes) &&
            clientNonce == other.clientNonce &&
            runtimeNonce == other.runtimeNonce &&
            generation == other.generation &&
            serviceConfigVersion == other.serviceConfigVersion &&
            keysetVersion == other.keysetVersion &&
            revocationCounter == other.revocationCounter &&
            protocolVersion == other.protocolVersion &&
            minimumProtocolVersion == other.minimumProtocolVersion &&
            profile == other.profile &&
            routeAuthorizationKind == other.routeAuthorizationKind &&
            routeAuthorizationDigest == other.routeAuthorizationDigest &&
            suite == other.suite
    }

    override fun hashCode(): Int {
        var result = sessionId.hashCode()
        result = 31 * result + pairBindingDigest.hashCode()
        result = 31 * result + pairEpoch.hashCode()
        result = 31 * result + clientIdentityFingerprint.hashCode()
        result = 31 * result + runtimeIdentityFingerprint.hashCode()
        result = 31 * result + clientEphemeralPublicKeyBytes.contentHashCode()
        result = 31 * result + runtimeEphemeralPublicKeyBytes.contentHashCode()
        result = 31 * result + clientNonce.hashCode()
        result = 31 * result + runtimeNonce.hashCode()
        result = 31 * result + generation.hashCode()
        result = 31 * result + serviceConfigVersion.hashCode()
        result = 31 * result + keysetVersion.hashCode()
        result = 31 * result + revocationCounter.hashCode()
        result = 31 * result + protocolVersion.hashCode()
        result = 31 * result + minimumProtocolVersion.hashCode()
        result = 31 * result + profile.hashCode()
        result = 31 * result + routeAuthorizationKind.hashCode()
        result = 31 * result + routeAuthorizationDigest.hashCode()
        result = 31 * result + suite.hashCode()
        return result
    }
}

object ProductionSecureSessionCodec {
    private const val TRANSCRIPT_OBJECT_TYPE = 7
    private const val TRANSCRIPT_FIELD_COUNT = 21
    private const val CLIENT_ROLE = "client"
    private const val RUNTIME_ROLE = "runtime"
    private val lowerHex32 = Regex("[0-9a-f]{32}")
    private val lowerHex64 = Regex("[0-9a-f]{64}")
    private val p256Prime = BigInteger(
        "ffffffff00000001000000000000000000000000ffffffffffffffffffffffff",
        16,
    )
    private val p256A = p256Prime.subtract(BigInteger.valueOf(3L))
    private val p256B = BigInteger(
        "5ac635d8aa3a93e7b3ebbd55769886bc651d06b0cc53b0f63bce3c3e27d2604b",
        16,
    )

    fun encode(value: ProductionRouteAuthorization): ByteArray {
        requireRouteCommon(value)
        val fields = when (value) {
            is LocalDirectRouteAuthorization -> listOf(
                suite(),
                lowerHex64(value.pairBindingDigest, "pair binding digest"),
                positiveUInt64(value.pairEpoch, "pair epoch"),
                lowerHex64(value.nominatedPathReceiptDigest, "nominated path receipt digest"),
            )

            is P2pPublishRouteAuthorization -> listOf(
                suite(),
                lowerHex64(value.pairBindingDigest, "pair binding digest"),
                positiveUInt64(value.pairEpoch, "pair epoch"),
                positiveUInt64(value.generation, "generation"),
                lowerHex64(value.candidateBatchDigest, "candidate batch digest"),
                lowerHex64(value.publishCapabilityDigest, "publish capability digest"),
            )

            is P2pFetchRouteAuthorization -> listOf(
                suite(),
                lowerHex64(value.pairBindingDigest, "pair binding digest"),
                positiveUInt64(value.pairEpoch, "pair epoch"),
                positiveUInt64(value.generation, "generation"),
                lowerHex64(value.candidateBatchDigest, "candidate batch digest"),
                lowerHex64(value.fetchCapabilityDigest, "fetch capability digest"),
            )

            is P2pDirectRouteAuthorization -> listOf(
                suite(),
                lowerHex64(value.pairBindingDigest, "pair binding digest"),
                positiveUInt64(value.pairEpoch, "pair epoch"),
                positiveUInt64(value.generation, "generation"),
                lowerHex64(value.candidatePairDigest, "candidate pair digest"),
                lowerHex64(value.pathValidationReceiptDigest, "path validation receipt digest"),
                lowerHex64(value.publishCapabilityDigest, "publish capability digest"),
                lowerHex64(value.fetchCapabilityDigest, "fetch capability digest"),
            )

            is TurnRelayRouteAuthorization -> listOf(
                suite(),
                lowerHex64(value.pairBindingDigest, "pair binding digest"),
                positiveUInt64(value.pairEpoch, "pair epoch"),
                positiveUInt64(value.generation, "generation"),
                lowerHex64(value.leaseDigest, "relay lease digest"),
                lowerHex64(value.allocationDigest, "relay allocation digest"),
                lowerHex64(value.pathValidationReceiptDigest, "path validation receipt digest"),
            )

            is SealedRelayRouteAuthorization -> listOf(
                suite(),
                lowerHex64(value.pairBindingDigest, "pair binding digest"),
                positiveUInt64(value.pairEpoch, "pair epoch"),
                positiveUInt64(value.generation, "generation"),
                lowerHex64(value.leaseDigest, "sealed-relay lease digest"),
                lowerHex64(value.allocationDigest, "sealed-relay allocation digest"),
                lowerHex64(value.pathValidationReceiptDigest, "path validation receipt digest"),
            )
        }
        return frame(value.kind.objectType, fields, ProductionSecureSessionContract.MAX_ROUTE_BYTES)
    }

    fun decodeRouteAuthorization(encoded: ByteArray): ProductionRouteAuthorization {
        require(encoded.size <= ProductionSecureSessionContract.MAX_ROUTE_BYTES) {
            "production route authorization exceeds limit"
        }
        val kind = ProductionRouteAuthorizationKind.decodeObjectType(peekObjectType(encoded))
        val fieldCount = when (kind) {
            ProductionRouteAuthorizationKind.LOCAL_DIRECT -> 4
            ProductionRouteAuthorizationKind.P2P_PUBLISH,
            ProductionRouteAuthorizationKind.P2P_FETCH,
            -> 6
            ProductionRouteAuthorizationKind.P2P_DIRECT -> 8
            ProductionRouteAuthorizationKind.TURN_RELAY,
            ProductionRouteAuthorizationKind.SEALED_RELAY,
            -> 7
        }
        val fields = parse(
            encoded,
            kind.objectType,
            fieldCount,
            ProductionSecureSessionContract.MAX_ROUTE_BYTES,
        )
        requireSuite(fields[0])
        val pairBindingDigest = decodeLowerHex64(fields[1], "pair binding digest")
        val pairEpoch = decodePositiveUInt64(fields[2], "pair epoch")
        return when (kind) {
            ProductionRouteAuthorizationKind.LOCAL_DIRECT -> LocalDirectRouteAuthorization(
                pairBindingDigest,
                pairEpoch,
                decodeLowerHex64(fields[3], "nominated path receipt digest"),
            )

            ProductionRouteAuthorizationKind.P2P_PUBLISH -> P2pPublishRouteAuthorization(
                pairBindingDigest,
                pairEpoch,
                decodePositiveUInt64(fields[3], "generation"),
                decodeLowerHex64(fields[4], "candidate batch digest"),
                decodeLowerHex64(fields[5], "publish capability digest"),
            )

            ProductionRouteAuthorizationKind.P2P_FETCH -> P2pFetchRouteAuthorization(
                pairBindingDigest,
                pairEpoch,
                decodePositiveUInt64(fields[3], "generation"),
                decodeLowerHex64(fields[4], "candidate batch digest"),
                decodeLowerHex64(fields[5], "fetch capability digest"),
            )

            ProductionRouteAuthorizationKind.P2P_DIRECT -> P2pDirectRouteAuthorization(
                pairBindingDigest,
                pairEpoch,
                decodePositiveUInt64(fields[3], "generation"),
                decodeLowerHex64(fields[4], "candidate pair digest"),
                decodeLowerHex64(fields[5], "path validation receipt digest"),
                decodeLowerHex64(fields[6], "publish capability digest"),
                decodeLowerHex64(fields[7], "fetch capability digest"),
            )

            ProductionRouteAuthorizationKind.TURN_RELAY -> TurnRelayRouteAuthorization(
                pairBindingDigest,
                pairEpoch,
                decodePositiveUInt64(fields[3], "generation"),
                decodeLowerHex64(fields[4], "relay lease digest"),
                decodeLowerHex64(fields[5], "relay allocation digest"),
                decodeLowerHex64(fields[6], "path validation receipt digest"),
            )

            ProductionRouteAuthorizationKind.SEALED_RELAY -> SealedRelayRouteAuthorization(
                pairBindingDigest,
                pairEpoch,
                decodePositiveUInt64(fields[3], "generation"),
                decodeLowerHex64(fields[4], "sealed-relay lease digest"),
                decodeLowerHex64(fields[5], "sealed-relay allocation digest"),
                decodeLowerHex64(fields[6], "path validation receipt digest"),
            )
        }
    }

    fun encode(value: ProductionSecureSessionTranscript): ByteArray {
        validateTranscript(value)
        return frame(
            TRANSCRIPT_OBJECT_TYPE,
            listOf(
                ascii(value.suite),
                lowerHex32(value.sessionId, "session id"),
                lowerHex64(value.pairBindingDigest, "pair binding digest"),
                positiveUInt64(value.pairEpoch, "pair epoch"),
                lowerHex64(value.clientIdentityFingerprint, "client identity fingerprint"),
                lowerHex64(value.runtimeIdentityFingerprint, "runtime identity fingerprint"),
                ascii(CLIENT_ROLE),
                ascii(RUNTIME_ROLE),
                value.clientEphemeralPublicKey,
                value.runtimeEphemeralPublicKey,
                lowerHex32(value.clientNonce, "client nonce"),
                lowerHex32(value.runtimeNonce, "runtime nonce"),
                positiveUInt64(value.generation, "generation"),
                positiveUInt64(value.serviceConfigVersion, "service config version"),
                positiveUInt64(value.keysetVersion, "keyset version"),
                uint64(value.revocationCounter),
                uint32(value.protocolVersion),
                uint32(value.minimumProtocolVersion),
                ascii(value.profile),
                ascii(value.routeAuthorizationKind.wireValue),
                lowerHex64(value.routeAuthorizationDigest, "route authorization digest"),
            ),
            ProductionSecureSessionContract.MAX_TRANSCRIPT_BYTES,
        )
    }

    fun decodeTranscript(encoded: ByteArray): ProductionSecureSessionTranscript {
        val fields = parse(
            encoded,
            TRANSCRIPT_OBJECT_TYPE,
            TRANSCRIPT_FIELD_COUNT,
            ProductionSecureSessionContract.MAX_TRANSCRIPT_BYTES,
        )
        requireSuite(fields[0])
        require(decodeAscii(fields[6]) == CLIENT_ROLE) { "invalid client role" }
        require(decodeAscii(fields[7]) == RUNTIME_ROLE) { "invalid runtime role" }
        val transcript = ProductionSecureSessionTranscript(
            suite = ProductionSecureSessionContract.SUITE,
            sessionId = decodeLowerHex32(fields[1], "session id"),
            pairBindingDigest = decodeLowerHex64(fields[2], "pair binding digest"),
            pairEpoch = decodePositiveUInt64(fields[3], "pair epoch"),
            clientIdentityFingerprint = decodeLowerHex64(fields[4], "client identity fingerprint"),
            runtimeIdentityFingerprint = decodeLowerHex64(fields[5], "runtime identity fingerprint"),
            clientEphemeralPublicKey = fields[8].also { requireP256PublicKey(it, "client ephemeral public key") },
            runtimeEphemeralPublicKey = fields[9].also { requireP256PublicKey(it, "runtime ephemeral public key") },
            clientNonce = decodeLowerHex32(fields[10], "client nonce"),
            runtimeNonce = decodeLowerHex32(fields[11], "runtime nonce"),
            generation = decodePositiveUInt64(fields[12], "generation"),
            serviceConfigVersion = decodePositiveUInt64(fields[13], "service config version"),
            keysetVersion = decodePositiveUInt64(fields[14], "keyset version"),
            revocationCounter = decodeUInt64(fields[15]),
            protocolVersion = decodeUInt32(fields[16]).also { require(it == 1u) { "invalid protocol version" } },
            minimumProtocolVersion = decodeUInt32(fields[17]).also {
                require(it == 1u) { "invalid minimum protocol version" }
            },
            profile = decodeAscii(fields[18]).also {
                require(it == ProductionSecureSessionContract.PROFILE) { "invalid secure-session profile" }
            },
            routeAuthorizationKind = ProductionRouteAuthorizationKind.decode(decodeAscii(fields[19])),
            routeAuthorizationDigest = decodeLowerHex64(fields[20], "route authorization digest"),
        )
        return transcript
    }

    fun digest(value: ProductionRouteAuthorization): ByteArray = sha256(encode(value))

    fun digest(value: ProductionSecureSessionTranscript): ByteArray = sha256(encode(value))

    fun matches(
        transcript: ProductionSecureSessionTranscript,
        routeAuthorization: ProductionRouteAuthorization,
    ): Boolean = runCatching {
        validateTranscript(transcript)
        requireRouteCommon(routeAuthorization)
        if (transcript.routeAuthorizationKind != routeAuthorization.kind ||
            transcript.pairBindingDigest != routeAuthorization.pairBindingDigest ||
            transcript.pairEpoch != routeAuthorization.pairEpoch
        ) {
            return@runCatching false
        }
        val routeGeneration = routeAuthorization.generation
        if (routeGeneration != null && transcript.generation != routeGeneration) {
            return@runCatching false
        }
        val suppliedDigest = decodeHex64OrNull(transcript.routeAuthorizationDigest)
            ?: return@runCatching false
        MessageDigest.isEqual(digest(routeAuthorization), suppliedDigest)
    }.getOrDefault(false)

    internal fun validateTranscript(value: ProductionSecureSessionTranscript) {
        require(value.suite == ProductionSecureSessionContract.SUITE) { "invalid secure-session suite" }
        requireLowerHex32(value.sessionId, "session id")
        requireLowerHex64(value.pairBindingDigest, "pair binding digest")
        require(value.pairEpoch > 0uL) { "pair epoch must be positive" }
        requireLowerHex64(value.clientIdentityFingerprint, "client identity fingerprint")
        requireLowerHex64(value.runtimeIdentityFingerprint, "runtime identity fingerprint")
        require(value.clientIdentityFingerprint != value.runtimeIdentityFingerprint) {
            "client and runtime identities must be distinct"
        }
        val clientKey = value.clientEphemeralPublicKey
        val runtimeKey = value.runtimeEphemeralPublicKey
        requireP256PublicKey(clientKey, "client ephemeral public key")
        requireP256PublicKey(runtimeKey, "runtime ephemeral public key")
        require(!clientKey.contentEquals(runtimeKey)) { "client and runtime ephemeral keys must be distinct" }
        requireLowerHex32(value.clientNonce, "client nonce")
        requireLowerHex32(value.runtimeNonce, "runtime nonce")
        require(value.clientNonce != value.runtimeNonce) { "client and runtime nonces must be distinct" }
        require(value.generation > 0uL) { "generation must be positive" }
        require(value.serviceConfigVersion > 0uL) { "service config version must be positive" }
        require(value.keysetVersion > 0uL) { "keyset version must be positive" }
        require(value.protocolVersion == 1u) { "invalid protocol version" }
        require(value.minimumProtocolVersion == 1u) { "invalid minimum protocol version" }
        require(value.profile == ProductionSecureSessionContract.PROFILE) { "invalid secure-session profile" }
        requireLowerHex64(value.routeAuthorizationDigest, "route authorization digest")
    }

    private fun requireRouteCommon(value: ProductionRouteAuthorization) {
        requireLowerHex64(value.pairBindingDigest, "pair binding digest")
        require(value.pairEpoch > 0uL) { "pair epoch must be positive" }
        value.generation?.let { require(it > 0uL) { "generation must be positive" } }
    }

    private fun frame(objectType: Int, fields: List<ByteArray>, maximumBytes: Int): ByteArray {
        val output = ByteArrayOutputStream()
        output.write(ProductionSecureSessionContract.MAGIC)
        output.write(objectType)
        output.write(ProductionSecureSessionContract.VERSION)
        fields.forEachIndexed { index, field ->
            output.write(index + 1)
            output.write(uint32(field.size.toUInt()))
            output.write(field)
        }
        return output.toByteArray().also {
            require(it.size <= maximumBytes) { "canonical production secure-session frame exceeds limit" }
        }
    }

    private fun parse(
        encoded: ByteArray,
        expectedObjectType: Int,
        fieldCount: Int,
        maximumBytes: Int,
    ): List<ByteArray> {
        require(encoded.size <= maximumBytes) { "canonical production secure-session frame exceeds limit" }
        val reader = Reader(encoded)
        require(reader.bytes(4).contentEquals(ProductionSecureSessionContract.MAGIC)) { "invalid magic" }
        require(reader.uint8() == expectedObjectType) { "invalid object type" }
        require(reader.uint8() == ProductionSecureSessionContract.VERSION) { "invalid version" }
        val fields = ArrayList<ByteArray>(fieldCount)
        for (expectedTag in 1..fieldCount) {
            val actualTag = reader.uint8()
            require(actualTag == expectedTag) { "omitted, duplicate, reordered, or unknown tag" }
            val fieldLength = reader.uint32().toULong()
            require(fieldLength <= reader.remaining.toULong()) { "invalid field length" }
            fields += reader.bytes(fieldLength.toInt())
        }
        reader.requireEnd()
        return fields
    }

    private fun peekObjectType(encoded: ByteArray): Int {
        require(encoded.size >= 6) { "truncated production secure-session frame" }
        require(encoded.copyOfRange(0, 4).contentEquals(ProductionSecureSessionContract.MAGIC)) {
            "invalid magic"
        }
        require((encoded[5].toInt() and 0xff) == ProductionSecureSessionContract.VERSION) {
            "invalid version"
        }
        return encoded[4].toInt() and 0xff
    }

    private fun suite(): ByteArray = ascii(ProductionSecureSessionContract.SUITE)

    private fun requireSuite(value: ByteArray) {
        require(decodeAscii(value) == ProductionSecureSessionContract.SUITE) {
            "invalid production secure-session suite"
        }
    }

    private fun positiveUInt64(value: ULong, name: String): ByteArray {
        require(value > 0uL) { "$name must be positive" }
        return uint64(value)
    }

    private fun uint64(value: ULong): ByteArray =
        ByteBuffer.allocate(8).order(ByteOrder.BIG_ENDIAN).putLong(value.toLong()).array()

    private fun uint32(value: UInt): ByteArray =
        ByteBuffer.allocate(4).order(ByteOrder.BIG_ENDIAN).putInt(value.toInt()).array()

    private fun decodeUInt64(value: ByteArray): ULong {
        require(value.size == 8) { "invalid UInt64 length" }
        return ByteBuffer.wrap(value).order(ByteOrder.BIG_ENDIAN).long.toULong()
    }

    private fun decodePositiveUInt64(value: ByteArray, name: String): ULong = decodeUInt64(value).also {
        require(it > 0uL) { "$name must be positive" }
    }

    private fun decodeUInt32(value: ByteArray): UInt {
        require(value.size == 4) { "invalid UInt32 length" }
        return ByteBuffer.wrap(value).order(ByteOrder.BIG_ENDIAN).int.toUInt()
    }

    private fun lowerHex32(value: String, name: String): ByteArray {
        requireLowerHex32(value, name)
        return ascii(value)
    }

    private fun lowerHex64(value: String, name: String): ByteArray {
        requireLowerHex64(value, name)
        return ascii(value)
    }

    private fun requireLowerHex32(value: String, name: String) {
        require(lowerHex32.matches(value)) { "invalid $name" }
    }

    private fun requireLowerHex64(value: String, name: String) {
        require(lowerHex64.matches(value)) { "invalid $name" }
    }

    private fun decodeLowerHex32(value: ByteArray, name: String): String = decodeAscii(value).also {
        requireLowerHex32(it, name)
    }

    private fun decodeLowerHex64(value: ByteArray, name: String): String = decodeAscii(value).also {
        requireLowerHex64(it, name)
    }

    private fun decodeHex64OrNull(value: String): ByteArray? {
        if (!lowerHex64.matches(value)) return null
        return ByteArray(32) { index -> value.substring(index * 2, index * 2 + 2).toInt(16).toByte() }
    }

    private fun ascii(value: String): ByteArray {
        require(value.all { it.code in 0x20..0x7e }) { "noncanonical ASCII" }
        return value.toByteArray(Charsets.US_ASCII)
    }

    private fun decodeAscii(value: ByteArray): String {
        require(value.all { (it.toInt() and 0xff) in 0x20..0x7e }) { "noncanonical ASCII" }
        return value.toString(Charsets.US_ASCII)
    }

    private fun requireP256PublicKey(value: ByteArray, name: String) {
        require(value.size == 65 && value[0] == 0x04.toByte()) {
            "$name must be canonical X9.63 uncompressed P-256"
        }
        val x = BigInteger(1, value.copyOfRange(1, 33))
        val y = BigInteger(1, value.copyOfRange(33, 65))
        require(x < p256Prime && y < p256Prime) { "$name coordinate is outside P-256" }
        val left = y.modPow(BigInteger.valueOf(2L), p256Prime)
        val right = x.modPow(BigInteger.valueOf(3L), p256Prime)
            .add(p256A.multiply(x))
            .add(p256B)
            .mod(p256Prime)
        require(left == right) { "$name is not on P-256" }
    }

    private fun sha256(value: ByteArray): ByteArray = MessageDigest.getInstance("SHA-256").digest(value)

    private class Reader(private val value: ByteArray) {
        private var offset = 0
        val remaining: Int get() = value.size - offset

        fun uint8(): Int {
            require(remaining >= 1) { "truncated UInt8" }
            return value[offset++].toInt() and 0xff
        }

        fun uint32(): UInt {
            require(remaining >= 4) { "truncated UInt32" }
            val result = ByteBuffer.wrap(value, offset, 4).order(ByteOrder.BIG_ENDIAN).int.toUInt()
            offset += 4
            return result
        }

        fun bytes(count: Int): ByteArray {
            require(count >= 0 && count <= remaining) { "truncated bytes" }
            return value.copyOfRange(offset, offset + count).also { offset += count }
        }

        fun requireEnd() {
            require(offset == value.size) { "trailing bytes" }
        }
    }
}
