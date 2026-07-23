package com.localagentbridge.android.core.protocol.p2pnat

import java.io.ByteArrayOutputStream
import java.math.BigInteger
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

enum class P2pNatRejectionClass(val wireValue: String) {
    INVALID_VALUE("invalidValue"),
    DUPLICATE_FIELD("duplicateField"),
    INVALID_FIELD_ORDER("invalidFieldOrder"),
    TRAILING_BYTES("trailingBytes"),
    LIMIT_EXCEEDED("limitExceeded"),
}

class P2pNatContractException(
    val rejectionClass: P2pNatRejectionClass,
    message: String,
) : IllegalArgumentException(message)

object P2pNatCanonicalCodec {
    private const val CANDIDATE_BATCH_TYPE = 1
    private const val SEALED_RECORD_TYPE = 2
    private const val RELAY_CAPABILITY_TYPE = 3
    private const val IDENTITY_TRANSCRIPT_TYPE = 4
    private const val PATH_RECEIPT_TYPE = 5
    private val lowerHex32 = Regex("[0-9a-f]{32}")
    private val lowerHex64 = Regex("[0-9a-f]{64}")
    private val keyConfirmationContext = ascii("aetherlink-p2p-v1:key-confirmation:")

    fun encode(value: CandidateBatch): ByteArray {
        requireSessionId(value.sessionId)
        require(value.generation > 0uL) { "generation must be positive" }
        require(value.expiresAtMillis > 0uL) { "expiry must be positive" }
        val blob = encodeCandidates(value.candidates)
        return frame(
            CANDIDATE_BATCH_TYPE,
            ascii(value.sessionId),
            uint64(value.generation),
            uint64(value.sequence),
            uint64(value.expiresAtMillis),
            ascii(value.senderRole.wireValue),
            blob,
        )
    }

    fun decodeCandidateBatch(encoded: ByteArray): CandidateBatch {
        val fields = parse(encoded, CANDIDATE_BATCH_TYPE, 6, P2pNatContract.MAX_CANDIDATE_BATCH_BYTES)
        return CandidateBatch(
            sessionId = decodeSessionId(fields[0]),
            generation = decodePositiveUInt64(fields[1], "generation"),
            sequence = decodeUInt64(fields[2]),
            expiresAtMillis = decodePositiveUInt64(fields[3], "expiry"),
            senderRole = P2pNatRole.decode(decodeAscii(fields[4])),
            candidates = decodeCandidates(fields[5]),
        )
    }

    fun decodeFreshCandidateBatch(encoded: ByteArray, nowMillis: ULong): CandidateBatch =
        decodeCandidateBatch(encoded).also {
            require(P2pNatContract.isFresh(it.expiresAtMillis, nowMillis)) { "candidate batch is expired or exceeds TTL" }
        }

    fun encode(value: SealedRouteRecord): ByteArray {
        requireSuite(value.suite)
        requireSessionId(value.sessionId)
        requireLowerHex64(value.pairBindingDigest, "pair binding digest")
        require(value.generation > 0uL) { "generation must be positive" }
        require(value.expiresAtMillis > 0uL) { "expiry must be positive" }
        requireLowerHex32(value.antiReplayNonce, "anti-replay nonce")
        requireP256Key(value.ephemeralPublicKey)
        require(value.sealNonce.size == 12) { "seal nonce must be 12 bytes" }
        require(value.ciphertext.size in 1..P2pNatContract.MAX_SEALED_RECORD_BYTES) { "invalid ciphertext length" }
        return frame(
            SEALED_RECORD_TYPE,
            ascii(value.suite),
            ascii(value.sessionId),
            ascii(value.pairBindingDigest),
            ascii(value.senderRole.wireValue),
            uint64(value.generation),
            uint64(value.sequence),
            uint64(value.expiresAtMillis),
            ascii(value.antiReplayNonce),
            value.ephemeralPublicKey,
            value.sealNonce,
            value.ciphertext,
        ).also { require(it.size <= P2pNatContract.MAX_SEALED_RECORD_BYTES) { "sealed record exceeds limit" } }
    }

    fun decodeSealedRouteRecord(encoded: ByteArray): SealedRouteRecord {
        require(encoded.size <= P2pNatContract.MAX_SEALED_RECORD_BYTES) { "sealed record exceeds limit" }
        val fields = parse(encoded, SEALED_RECORD_TYPE, 11, P2pNatContract.MAX_SEALED_RECORD_BYTES)
        val key = fields[8].also(::requireP256Key)
        val nonce = fields[9].also { require(it.size == 12) { "seal nonce must be 12 bytes" } }
        val ciphertext = fields[10].also {
            require(it.size in 1..P2pNatContract.MAX_SEALED_RECORD_BYTES) { "invalid ciphertext length" }
        }
        return SealedRouteRecord(
            suite = decodeSuite(fields[0]),
            sessionId = decodeSessionId(fields[1]),
            pairBindingDigest = decodeLowerHex64(fields[2], "pair binding digest"),
            senderRole = P2pNatRole.decode(decodeAscii(fields[3])),
            generation = decodePositiveUInt64(fields[4], "generation"),
            sequence = decodeUInt64(fields[5]),
            expiresAtMillis = decodePositiveUInt64(fields[6], "expiry"),
            antiReplayNonce = decodeLowerHex32(fields[7], "anti-replay nonce"),
            ephemeralPublicKey = key,
            sealNonce = nonce,
            ciphertext = ciphertext,
        )
    }

    fun decodeFreshSealedRouteRecord(encoded: ByteArray, nowMillis: ULong): SealedRouteRecord =
        decodeSealedRouteRecord(encoded).also {
            require(P2pNatContract.isFresh(it.expiresAtMillis, nowMillis)) { "sealed record is expired or exceeds TTL" }
        }

    fun encode(value: RelayCapability): ByteArray {
        requireSuite(value.suite)
        requireSessionId(value.sessionId)
        requireLowerHex64(value.pairBindingDigest, "pair binding digest")
        requireLowerHex64(value.clientFingerprint, "client fingerprint")
        requireLowerHex64(value.runtimeFingerprint, "runtime fingerprint")
        requireLowerHex64(value.relayServiceDigest, "relay service digest")
        require(value.expiresAtMillis > 0uL) { "expiry must be positive" }
        require(value.quotaBytes > 0uL) { "quota must be positive" }
        requireLowerHex32(value.capabilityNonce, "capability nonce")
        return frame(
            RELAY_CAPABILITY_TYPE,
            ascii(value.suite), ascii(value.sessionId), ascii(value.pairBindingDigest),
            ascii(value.clientFingerprint), ascii(value.runtimeFingerprint), ascii(value.relayServiceDigest),
            uint64(value.expiresAtMillis), uint64(value.quotaBytes), ascii(value.capabilityNonce),
        )
    }

    fun decodeRelayCapability(encoded: ByteArray): RelayCapability {
        val fields = parse(encoded, RELAY_CAPABILITY_TYPE, 9, P2pNatContract.MAX_RELAY_CAPABILITY_BYTES)
        return RelayCapability(
            suite = decodeSuite(fields[0]),
            sessionId = decodeSessionId(fields[1]),
            pairBindingDigest = decodeLowerHex64(fields[2], "pair binding digest"),
            clientFingerprint = decodeLowerHex64(fields[3], "client fingerprint"),
            runtimeFingerprint = decodeLowerHex64(fields[4], "runtime fingerprint"),
            relayServiceDigest = decodeLowerHex64(fields[5], "relay service digest"),
            expiresAtMillis = decodePositiveUInt64(fields[6], "expiry"),
            quotaBytes = decodePositiveUInt64(fields[7], "quota"),
            capabilityNonce = decodeLowerHex32(fields[8], "capability nonce"),
        )
    }

    fun decodeFreshRelayCapability(encoded: ByteArray, nowMillis: ULong): RelayCapability =
        decodeRelayCapability(encoded).also {
            require(P2pNatContract.isFresh(it.expiresAtMillis, nowMillis)) { "relay capability is expired or exceeds TTL" }
        }

    fun encode(value: IdentitySessionTranscript): ByteArray {
        requireSuite(value.suite)
        requireSessionId(value.sessionId)
        requireLowerHex64(value.pairBindingDigest, "pair binding digest")
        requireLowerHex64(value.clientFingerprint, "client fingerprint")
        requireLowerHex64(value.runtimeFingerprint, "runtime fingerprint")
        requireP256Key(value.clientEphemeralKey)
        requireP256Key(value.runtimeEphemeralKey)
        require(value.generation > 0uL) { "generation must be positive" }
        requireLowerHex64(value.pathReceiptDigest, "path receipt digest")
        require(value.protocolFloor == 1u) { "invalid protocol floor" }
        return frame(
            IDENTITY_TRANSCRIPT_TYPE,
            ascii(value.suite), ascii(value.sessionId), ascii(value.pairBindingDigest),
            ascii(value.clientFingerprint), ascii(value.runtimeFingerprint), value.clientEphemeralKey,
            value.runtimeEphemeralKey, uint64(value.generation), ascii(value.pathReceiptDigest),
            ascii(value.transportContext.wireValue), ascii(value.fallbackReason.wireValue), uint32(value.protocolFloor),
        )
    }

    fun decodeIdentitySessionTranscript(encoded: ByteArray): IdentitySessionTranscript {
        val fields = parse(encoded, IDENTITY_TRANSCRIPT_TYPE, 12, P2pNatContract.MAX_IDENTITY_TRANSCRIPT_BYTES)
        return IdentitySessionTranscript(
            suite = decodeSuite(fields[0]),
            sessionId = decodeSessionId(fields[1]),
            pairBindingDigest = decodeLowerHex64(fields[2], "pair binding digest"),
            clientFingerprint = decodeLowerHex64(fields[3], "client fingerprint"),
            runtimeFingerprint = decodeLowerHex64(fields[4], "runtime fingerprint"),
            clientEphemeralKey = fields[5].also(::requireP256Key),
            runtimeEphemeralKey = fields[6].also(::requireP256Key),
            generation = decodePositiveUInt64(fields[7], "generation"),
            pathReceiptDigest = decodeLowerHex64(fields[8], "path receipt digest"),
            transportContext = TransportContext.decode(decodeAscii(fields[9])),
            fallbackReason = FallbackReason.decode(decodeAscii(fields[10])),
            protocolFloor = decodeUInt32(fields[11]).also { require(it == 1u) { "invalid protocol floor" } },
        )
    }

    fun encode(value: PathValidationReceipt): ByteArray {
        requireSessionId(value.sessionId)
        require(value.generation > 0uL) { "generation must be positive" }
        requireLowerHex64(value.candidatePairDigest, "candidate pair digest")
        requireLowerHex64(value.clientObservedPathDigest, "client observed path digest")
        requireLowerHex64(value.runtimeObservedPathDigest, "runtime observed path digest")
        require(value.validatedAtMillis > 0uL) { "validation time must be positive" }
        require(value.expiresAtMillis > value.validatedAtMillis) { "expiry must follow validation" }
        require(value.expiresAtMillis - value.validatedAtMillis <= P2pNatContract.RECORD_TTL_MILLIS.toULong()) {
            "path receipt lifetime exceeds TTL"
        }
        return frame(
            PATH_RECEIPT_TYPE,
            ascii(value.sessionId), uint64(value.generation), ascii(value.candidatePairDigest),
            ascii(value.transportContext.wireValue), ascii(value.clientObservedPathDigest),
            ascii(value.runtimeObservedPathDigest), uint64(value.validatedAtMillis), uint64(value.expiresAtMillis),
        )
    }

    fun decodePathValidationReceipt(encoded: ByteArray): PathValidationReceipt {
        val fields = parse(encoded, PATH_RECEIPT_TYPE, 8, P2pNatContract.MAX_PATH_RECEIPT_BYTES)
        val validated = decodePositiveUInt64(fields[6], "validation time")
        val expires = decodePositiveUInt64(fields[7], "expiry")
        require(expires > validated) { "expiry must follow validation" }
        requireContract(
            expires - validated <= P2pNatContract.RECORD_TTL_MILLIS.toULong(),
            P2pNatRejectionClass.INVALID_VALUE,
            "path receipt lifetime exceeds TTL",
        )
        return PathValidationReceipt(
            sessionId = decodeSessionId(fields[0]),
            generation = decodePositiveUInt64(fields[1], "generation"),
            candidatePairDigest = decodeLowerHex64(fields[2], "candidate pair digest"),
            transportContext = TransportContext.decode(decodeAscii(fields[3])),
            clientObservedPathDigest = decodeLowerHex64(fields[4], "client observed path digest"),
            runtimeObservedPathDigest = decodeLowerHex64(fields[5], "runtime observed path digest"),
            validatedAtMillis = validated,
            expiresAtMillis = expires,
        )
    }

    fun decodeFreshPathValidationReceipt(encoded: ByteArray, nowMillis: ULong): PathValidationReceipt =
        decodePathValidationReceipt(encoded).also {
            requireContract(
                P2pNatContract.isPathValidationFresh(it.validatedAtMillis, it.expiresAtMillis, nowMillis),
                P2pNatRejectionClass.INVALID_VALUE,
                "path receipt validation time or expiry is not fresh",
            )
        }

    fun sha256(value: IdentitySessionTranscript): ByteArray = MessageDigest.getInstance("SHA-256").digest(encode(value))

    fun keyConfirmation(value: IdentitySessionTranscript, key: ByteArray, role: P2pNatRole): ByteArray {
        require(key.size == 32) { "confirmation key must be 32 bytes" }
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(key.copyOf(), "HmacSHA256"))
        mac.update(encode(value))
        mac.update(keyConfirmationContext)
        mac.update(ascii(role.wireValue))
        return mac.doFinal()
    }

    fun isFresh(expiresAtMillis: ULong, nowMillis: ULong): Boolean =
        P2pNatContract.isFresh(expiresAtMillis, nowMillis)

    internal fun encodeCandidate(candidate: P2pCandidate): ByteArray {
        val out = ByteArrayOutputStream()
        out.write(candidate.kind.wireValue)
        out.write(candidate.family.wireValue)
        out.write(1)
        writeUInt16(out, candidate.port)
        out.write(uint32(candidate.priority))
        out.write(candidate.foundation)
        out.write(candidate.address.size)
        out.write(candidate.address)
        return out.toByteArray()
    }

    private fun encodeCandidates(candidates: List<P2pCandidate>): ByteArray {
        require(candidates.size in 1..P2pNatContract.MAX_CANDIDATES) { "invalid candidate count" }
        val encoded = candidates.map(::encodeCandidate)
        require(encoded.map { it.toList() }.distinct().size == encoded.size) { "duplicate candidate" }
        require(encoded.zipWithNext().all { (left, right) -> candidateCompare(left, right) <= 0 }) {
            "candidates are not canonically ordered"
        }
        val out = ByteArrayOutputStream()
        writeUInt16(out, encoded.size)
        encoded.forEach(out::write)
        return out.toByteArray().also {
            require(it.size <= P2pNatContract.MAX_CANDIDATE_BLOB_BYTES) { "candidate blob exceeds limit" }
        }
    }

    private fun decodeCandidates(blob: ByteArray): List<P2pCandidate> {
        require(blob.size <= P2pNatContract.MAX_CANDIDATE_BLOB_BYTES) { "candidate blob exceeds limit" }
        val reader = Reader(blob)
        val count = reader.uint16()
        require(count in 1..P2pNatContract.MAX_CANDIDATES) { "invalid candidate count" }
        val result = ArrayList<P2pCandidate>(count)
        repeat(count) {
            val kind = CandidateKind.decode(reader.uint8())
            val family = AddressFamily.decode(reader.uint8())
            require(reader.uint8() == 1) { "invalid candidate transport" }
            val port = reader.uint16()
            require(port in 1024..65_535) { "invalid candidate port" }
            val priority = reader.uint32()
            val foundation = reader.bytes(8)
            val addressLength = reader.uint8()
            require(addressLength == family.byteLength) { "address length does not match family" }
            result += P2pCandidate(kind, family, port, priority, foundation, reader.bytes(addressLength))
        }
        reader.requireEnd()
        val canonical = result.map(::encodeCandidate)
        require(canonical.map { it.toList() }.distinct().size == canonical.size) { "duplicate candidate" }
        require(canonical.zipWithNext().all { (left, right) -> candidateCompare(left, right) <= 0 }) {
            "candidates are not canonically ordered"
        }
        return result
    }

    private fun candidateCompare(left: ByteArray, right: ByteArray): Int {
        val leftPriority = ByteBuffer.wrap(left, 5, 4).order(ByteOrder.BIG_ENDIAN).int.toUInt()
        val rightPriority = ByteBuffer.wrap(right, 5, 4).order(ByteOrder.BIG_ENDIAN).int.toUInt()
        if (leftPriority != rightPriority) return if (leftPriority > rightPriority) -1 else 1
        for (index in 0 until minOf(left.size, right.size)) {
            val difference = (left[index].toInt() and 0xff) - (right[index].toInt() and 0xff)
            if (difference != 0) return difference
        }
        return left.size - right.size
    }

    private fun frame(type: Int, vararg values: ByteArray): ByteArray {
        val out = ByteArrayOutputStream()
        out.write(P2pNatContract.MAGIC)
        out.write(type)
        out.write(P2pNatContract.VERSION)
        values.forEachIndexed { index, value ->
            out.write(index + 1)
            out.write(uint32(value.size.toUInt()))
            out.write(value)
        }
        return out.toByteArray()
    }

    private fun parse(
        encoded: ByteArray,
        expectedType: Int,
        fieldCount: Int,
        maximumFrameBytes: Int,
    ): List<ByteArray> {
        requireContract(
            encoded.size <= maximumFrameBytes,
            P2pNatRejectionClass.LIMIT_EXCEEDED,
            "canonical frame exceeds limit",
        )
        val reader = Reader(encoded)
        require(reader.bytes(4).contentEquals(P2pNatContract.MAGIC)) { "invalid magic" }
        require(reader.uint8() == expectedType) { "invalid object type" }
        require(reader.uint8() == P2pNatContract.VERSION) { "invalid version" }
        val fields = ArrayList<ByteArray>(fieldCount)
        for (expectedTag in 1..fieldCount) {
            val actualTag = reader.uint8()
            if (actualTag != expectedTag) {
                val rejectionClass = when {
                    actualTag < expectedTag -> P2pNatRejectionClass.DUPLICATE_FIELD
                    actualTag <= fieldCount -> P2pNatRejectionClass.INVALID_FIELD_ORDER
                    else -> P2pNatRejectionClass.INVALID_VALUE
                }
                throw P2pNatContractException(rejectionClass, "omitted, duplicate, reordered, or unknown tag")
            }
            val length = reader.uint32().toULong()
            require(length <= reader.remaining.toULong()) { "invalid field length" }
            fields += reader.bytes(length.toInt())
        }
        reader.requireEnd()
        return fields
    }

    private fun uint64(value: ULong): ByteArray = ByteBuffer.allocate(8).order(ByteOrder.BIG_ENDIAN)
        .putLong(value.toLong()).array()

    private fun uint32(value: UInt): ByteArray = ByteBuffer.allocate(4).order(ByteOrder.BIG_ENDIAN)
        .putInt(value.toInt()).array()

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

    private fun ascii(value: String): ByteArray {
        require(value.all { it.code in 0x20..0x7e }) { "noncanonical ASCII" }
        return value.toByteArray(Charsets.US_ASCII)
    }

    private fun decodeAscii(value: ByteArray): String {
        require(value.all { (it.toInt() and 0xff) in 0x20..0x7e }) { "noncanonical ASCII" }
        return value.toString(Charsets.US_ASCII)
    }

    private fun requireSessionId(value: String) = require(lowerHex32.matches(value)) { "invalid session id" }
    private fun decodeSessionId(value: ByteArray): String = decodeAscii(value).also(::requireSessionId)
    private fun requireSuite(value: String) = require(value == P2pNatContract.SUITE) { "invalid suite" }
    private fun decodeSuite(value: ByteArray): String = decodeAscii(value).also(::requireSuite)
    private fun requireLowerHex32(value: String, name: String) = require(lowerHex32.matches(value)) { "invalid $name" }
    private fun requireLowerHex64(value: String, name: String) = require(lowerHex64.matches(value)) { "invalid $name" }
    private fun decodeLowerHex32(value: ByteArray, name: String): String = decodeAscii(value).also { requireLowerHex32(it, name) }
    private fun decodeLowerHex64(value: ByteArray, name: String): String = decodeAscii(value).also { requireLowerHex64(it, name) }
    private fun requireP256Key(value: ByteArray) {
        requireContract(
            value.size == 65 && value[0] == 0x04.toByte(),
            P2pNatRejectionClass.INVALID_VALUE,
            "invalid uncompressed P-256 key",
        )
        val x = BigInteger(1, value.copyOfRange(1, 33))
        val y = BigInteger(1, value.copyOfRange(33, 65))
        requireContract(
            x < P256_FIELD && y < P256_FIELD,
            P2pNatRejectionClass.INVALID_VALUE,
            "P-256 coordinate is outside the field",
        )
        val left = y.modPow(BigInteger.valueOf(2L), P256_FIELD)
        val right = x.modPow(BigInteger.valueOf(3), P256_FIELD)
            .subtract(x.multiply(BigInteger.valueOf(3)))
            .add(P256_B)
            .mod(P256_FIELD)
        requireContract(left == right, P2pNatRejectionClass.INVALID_VALUE, "P-256 point is not on the curve")
    }

    private fun requireContract(condition: Boolean, rejectionClass: P2pNatRejectionClass, message: String) {
        if (!condition) throw P2pNatContractException(rejectionClass, message)
    }

    private fun writeUInt16(out: ByteArrayOutputStream, value: Int) {
        out.write((value ushr 8) and 0xff)
        out.write(value and 0xff)
    }

    private class Reader(private val value: ByteArray) {
        private var offset = 0
        val remaining: Int get() = value.size - offset

        fun uint8(): Int = bytes(1)[0].toInt() and 0xff
        fun uint16(): Int {
            val bytes = bytes(2)
            return ((bytes[0].toInt() and 0xff) shl 8) or (bytes[1].toInt() and 0xff)
        }
        fun uint32(): UInt {
            val bytes = bytes(4)
            return ByteBuffer.wrap(bytes).order(ByteOrder.BIG_ENDIAN).int.toUInt()
        }
        fun bytes(count: Int): ByteArray {
            require(count >= 0 && count <= remaining) { "truncated input" }
            return value.copyOfRange(offset, offset + count).also { offset += count }
        }
        fun requireEnd() {
            if (offset != value.size) {
                throw P2pNatContractException(P2pNatRejectionClass.TRAILING_BYTES, "trailing bytes")
            }
        }
    }

    private val P256_FIELD = BigInteger("ffffffff00000001000000000000000000000000ffffffffffffffffffffffff", 16)
    private val P256_B = BigInteger("5ac635d8aa3a93e7b3ebbd55769886bc651d06b0cc53b0f63bce3c3e27d2604b", 16)
}
