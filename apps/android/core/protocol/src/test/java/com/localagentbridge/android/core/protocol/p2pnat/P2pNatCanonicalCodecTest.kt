package com.localagentbridge.android.core.protocol.p2pnat

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class P2pNatCanonicalCodecTest {
    @Test
    fun candidateBatchRoundTripsCanonicalCandidates() {
        val batch = candidateBatch()
        val encoded = P2pNatCanonicalCodec.encode(batch)
        val decoded = P2pNatCanonicalCodec.decodeCandidateBatch(encoded)

        assertArrayEquals(byteArrayOf(0x41, 0x4c, 0x50, 0x31, 1, 1), encoded.copyOfRange(0, 6))
        assertEquals(batch, decoded)
        assertArrayEquals(encoded, P2pNatCanonicalCodec.encode(decoded))
    }

    @Test
    fun candidateBatchRejectsNoncanonicalListsAndBoundaries() {
        val high = candidate(priority = UInt.MAX_VALUE, foundationByte = 1)
        val low = candidate(priority = 0u, foundationByte = 2)

        assertThrows(IllegalArgumentException::class.java) {
            P2pNatCanonicalCodec.encode(candidateBatch().copy(candidates = listOf(low, high)))
        }
        assertThrows(IllegalArgumentException::class.java) {
            P2pNatCanonicalCodec.encode(candidateBatch().copy(candidates = listOf(high, high)))
        }
        assertThrows(IllegalArgumentException::class.java) {
            P2pNatCanonicalCodec.encode(candidateBatch().copy(candidates = emptyList()))
        }
        assertThrows(IllegalArgumentException::class.java) {
            P2pNatCanonicalCodec.encode(candidateBatch().copy(candidates = List(33) { index ->
                candidate(priority = (100 - index).toUInt(), foundationByte = index)
            }))
        }
        assertThrows(IllegalArgumentException::class.java) {
            P2pCandidate(CandidateKind.HOST, AddressFamily.IPV4, 1023, 1u, ByteArray(8), byteArrayOf(1, 1, 1, 1))
        }
        assertThrows(IllegalArgumentException::class.java) {
            P2pCandidate(CandidateKind.HOST, AddressFamily.IPV6, 65_536, 1u, ByteArray(8), ByteArray(4))
        }
    }

    @Test
    fun everyObjectRoundTripsWithExactFieldOrder() {
        val sealed = sealedRecord()
        val capability = relayCapability()
        val transcript = transcript()
        val receipt = receipt()

        val sealedDecoded = P2pNatCanonicalCodec.decodeSealedRouteRecord(P2pNatCanonicalCodec.encode(sealed))
        assertEquals(sealed.sessionId, sealedDecoded.sessionId)
        assertArrayEquals(sealed.ciphertext, sealedDecoded.ciphertext)
        assertEquals(capability, P2pNatCanonicalCodec.decodeRelayCapability(P2pNatCanonicalCodec.encode(capability)))
        val transcriptDecoded = P2pNatCanonicalCodec.decodeIdentitySessionTranscript(P2pNatCanonicalCodec.encode(transcript))
        assertEquals(transcript.pathReceiptDigest, transcriptDecoded.pathReceiptDigest)
        assertArrayEquals(transcript.clientEphemeralKey, transcriptDecoded.clientEphemeralKey)
        assertEquals(receipt, P2pNatCanonicalCodec.decodePathValidationReceipt(P2pNatCanonicalCodec.encode(receipt)))

        assertEquals(2, P2pNatCanonicalCodec.encode(sealed)[4].toInt())
        assertEquals(3, P2pNatCanonicalCodec.encode(capability)[4].toInt())
        assertEquals(4, P2pNatCanonicalCodec.encode(transcript)[4].toInt())
        assertEquals(5, P2pNatCanonicalCodec.encode(receipt)[4].toInt())
    }

    @Test
    fun decoderRejectsHeaderTagLengthAndTrailingMutations() {
        val encoded = P2pNatCanonicalCodec.encode(candidateBatch())
        val badMagic = encoded.copyOf().also { it[0] = 0 }
        val badType = encoded.copyOf().also { it[4] = 2 }
        val badVersion = encoded.copyOf().also { it[5] = 2 }
        val reordered = encoded.copyOf().also { it[6] = 2 }
        val excessiveLength = encoded.copyOf().also { it[7] = 0x7f }
        val trailing = encoded + 0

        listOf(badMagic, badType, badVersion, reordered, excessiveLength, trailing).forEach { malformed ->
            assertThrows(IllegalArgumentException::class.java) {
                P2pNatCanonicalCodec.decodeCandidateBatch(malformed)
            }
        }
    }

    @Test
    fun decoderRejectsNoncanonicalAsciiAndInvalidIntegers() {
        val encoded = P2pNatCanonicalCodec.encode(candidateBatch())
        val uppercaseSession = encoded.copyOf().also { it[11] = 'A'.code.toByte() }
        val nonAsciiSession = encoded.copyOf().also { it[11] = 0x80.toByte() }
        val zeroGeneration = encoded.copyOf().also { bytes ->
            for (index in 48..55) bytes[index] = 0
        }

        listOf(uppercaseSession, nonAsciiSession, zeroGeneration).forEach { malformed ->
            assertThrows(IllegalArgumentException::class.java) {
                P2pNatCanonicalCodec.decodeCandidateBatch(malformed)
            }
        }
        assertThrows(IllegalArgumentException::class.java) {
            P2pNatCanonicalCodec.encode(candidateBatch().copy(generation = 0uL))
        }
        assertThrows(IllegalArgumentException::class.java) {
            P2pNatCanonicalCodec.encode(relayCapability().copy(quotaBytes = 0uL))
        }
        assertThrows(IllegalArgumentException::class.java) {
            P2pNatCanonicalCodec.encode(transcript(protocolFloor = 0u))
        }
    }

    @Test
    fun sealedRecordEnforcesCryptoLengthsAndTotalLimit() {
        assertThrows(IllegalArgumentException::class.java) {
            P2pNatCanonicalCodec.encode(sealedRecord(ephemeralPublicKey = ByteArray(65)))
        }
        assertThrows(IllegalArgumentException::class.java) {
            P2pNatCanonicalCodec.encode(sealedRecord(ephemeralPublicKey = ByteArray(65).also { it[0] = 4 }))
        }
        assertThrows(IllegalArgumentException::class.java) {
            P2pNatCanonicalCodec.encode(sealedRecord(sealNonce = ByteArray(11)))
        }
        assertThrows(IllegalArgumentException::class.java) {
            P2pNatCanonicalCodec.encode(sealedRecord(ciphertext = ByteArray(0)))
        }
        val oneByteFrame = P2pNatCanonicalCodec.encode(sealedRecord(ciphertext = ByteArray(1)))
        val maximumCiphertext = P2pNatContract.MAX_SEALED_RECORD_BYTES - (oneByteFrame.size - 1)
        val exactLimit = P2pNatCanonicalCodec.encode(sealedRecord(ciphertext = ByteArray(maximumCiphertext)))
        assertEquals(P2pNatContract.MAX_SEALED_RECORD_BYTES, exactLimit.size)
        assertThrows(IllegalArgumentException::class.java) {
            P2pNatCanonicalCodec.encode(sealedRecord(ciphertext = ByteArray(maximumCiphertext + 1)))
        }
    }

    @Test
    fun transcriptDigestAndRoleConfirmationsAreStableAndSeparated() {
        val transcript = transcript()
        val digest = transcript.digest()
        val key = ByteArray(32) { it.toByte() }
        val client = transcript.keyConfirmation(key, P2pNatRole.CLIENT)
        val runtime = transcript.keyConfirmation(key, P2pNatRole.RUNTIME)

        assertEquals(32, digest.size)
        assertEquals(32, client.size)
        assertFalse(client.contentEquals(runtime))
        assertArrayEquals(digest, transcript.digest())
        assertArrayEquals(client, transcript.keyConfirmation(key, P2pNatRole.CLIENT))
        assertThrows(IllegalArgumentException::class.java) {
            transcript.keyConfirmation(ByteArray(31), P2pNatRole.CLIENT)
        }
    }

    @Test
    fun expiryFreshnessUsesTtlAndClockSkewBoundaries() {
        val now = 1_000_000uL
        assertTrue(P2pNatCanonicalCodec.isFresh(now - 29_999uL, now))
        assertFalse(P2pNatCanonicalCodec.isFresh(now - 30_000uL, now))
        assertTrue(P2pNatCanonicalCodec.isFresh(now + 630_000uL, now))
        assertFalse(P2pNatCanonicalCodec.isFresh(now + 630_001uL, now))
        assertFalse(P2pNatCanonicalCodec.isFresh(0uL, now))
    }

    @Test
    fun freshDecodersRejectExpiredAndExcessiveTtlRecords() {
        val now = 1_000_000uL
        val expiredBatch = P2pNatCanonicalCodec.encode(candidateBatch().copy(expiresAtMillis = now - 30_000uL))
        val futureSealed = P2pNatCanonicalCodec.encode(sealedRecord().let {
            SealedRouteRecord(
                sessionId = it.sessionId,
                pairBindingDigest = it.pairBindingDigest,
                senderRole = it.senderRole,
                generation = it.generation,
                sequence = it.sequence,
                expiresAtMillis = now + 630_001uL,
                antiReplayNonce = it.antiReplayNonce,
                ephemeralPublicKey = it.ephemeralPublicKey,
                sealNonce = it.sealNonce,
                ciphertext = it.ciphertext,
            )
        })

        assertThrows(IllegalArgumentException::class.java) {
            P2pNatCanonicalCodec.decodeFreshCandidateBatch(expiredBatch, now)
        }
        assertThrows(IllegalArgumentException::class.java) {
            P2pNatCanonicalCodec.decodeFreshSealedRouteRecord(futureSealed, now)
        }
        assertEquals(candidateBatch(), P2pNatCanonicalCodec.decodeFreshCandidateBatch(P2pNatCanonicalCodec.encode(candidateBatch()), now))
    }

    @Test
    fun allDecodersRejectFramesAboveTheirPreParseCeilings() {
        assertThrows(IllegalArgumentException::class.java) {
            P2pNatCanonicalCodec.decodeCandidateBatch(ByteArray(P2pNatContract.MAX_CANDIDATE_BATCH_BYTES + 1))
        }
        assertThrows(IllegalArgumentException::class.java) {
            P2pNatCanonicalCodec.decodeRelayCapability(ByteArray(P2pNatContract.MAX_RELAY_CAPABILITY_BYTES + 1))
        }
        assertThrows(IllegalArgumentException::class.java) {
            P2pNatCanonicalCodec.decodeIdentitySessionTranscript(ByteArray(P2pNatContract.MAX_IDENTITY_TRANSCRIPT_BYTES + 1))
        }
        assertThrows(IllegalArgumentException::class.java) {
            P2pNatCanonicalCodec.decodePathValidationReceipt(ByteArray(P2pNatContract.MAX_PATH_RECEIPT_BYTES + 1))
        }
    }

    @Test
    fun receiptRequiresStrictlyIncreasingTimestamps() {
        assertThrows(IllegalArgumentException::class.java) {
            P2pNatCanonicalCodec.encode(receipt().copy(expiresAtMillis = receipt().validatedAtMillis))
        }
        assertThrows(IllegalArgumentException::class.java) {
            P2pNatCanonicalCodec.encode(receipt().copy(validatedAtMillis = 0uL))
        }
        assertThrows(IllegalArgumentException::class.java) {
            P2pNatCanonicalCodec.encode(receipt().copy(expiresAtMillis = receipt().validatedAtMillis + 600_001uL))
        }
        val now = 1_000_000uL
        val future = receipt().copy(validatedAtMillis = now + 30_001uL, expiresAtMillis = now + 30_002uL)
        assertThrows(IllegalArgumentException::class.java) {
            P2pNatCanonicalCodec.decodeFreshPathValidationReceipt(P2pNatCanonicalCodec.encode(future), now)
        }
        assertTrue(P2pNatContract.isPathValidationFresh(now, now + 600_000uL, now))
    }

    private fun candidateBatch() = CandidateBatch(
        sessionId = HEX32,
        generation = 1uL,
        sequence = 0uL,
        expiresAtMillis = 1_600_000uL,
        senderRole = P2pNatRole.CLIENT,
        candidates = listOf(
            candidate(priority = UInt.MAX_VALUE, foundationByte = 1),
            candidate(priority = 1u, foundationByte = 2),
        ),
    )

    private fun candidate(priority: UInt, foundationByte: Int) = P2pCandidate(
        kind = CandidateKind.HOST,
        family = AddressFamily.IPV4,
        port = 1024 + foundationByte,
        priority = priority,
        foundation = ByteArray(8) { foundationByte.toByte() },
        address = byteArrayOf(8, 8, 8, foundationByte.toByte()),
    )

    private fun sealedRecord(
        ephemeralPublicKey: ByteArray = p256Key(3),
        sealNonce: ByteArray = ByteArray(12) { 4 },
        ciphertext: ByteArray = byteArrayOf(5, 6, 7),
    ) = SealedRouteRecord(
        sessionId = HEX32,
        pairBindingDigest = HEX64_A,
        senderRole = P2pNatRole.RUNTIME,
        generation = 2uL,
        sequence = ULong.MAX_VALUE,
        expiresAtMillis = 1_600_000uL,
        antiReplayNonce = HEX32_B,
        ephemeralPublicKey = ephemeralPublicKey,
        sealNonce = sealNonce,
        ciphertext = ciphertext,
    )

    private fun relayCapability() = RelayCapability(
        sessionId = HEX32,
        pairBindingDigest = HEX64_A,
        clientFingerprint = HEX64_B,
        runtimeFingerprint = HEX64_C,
        relayServiceDigest = HEX64_D,
        expiresAtMillis = 1_600_000uL,
        quotaBytes = ULong.MAX_VALUE,
        capabilityNonce = HEX32_B,
    )

    private fun transcript(protocolFloor: UInt = 1u) = IdentitySessionTranscript(
        sessionId = HEX32,
        pairBindingDigest = HEX64_A,
        clientFingerprint = HEX64_B,
        runtimeFingerprint = HEX64_C,
        clientEphemeralKey = p256Key(1),
        runtimeEphemeralKey = p256Key(2),
        generation = 9uL,
        pathReceiptDigest = HEX64_D,
        transportContext = TransportContext.DIRECT,
        fallbackReason = FallbackReason.NONE,
        protocolFloor = protocolFloor,
    )

    private fun receipt() = PathValidationReceipt(
        sessionId = HEX32,
        generation = 9uL,
        candidatePairDigest = HEX64_A,
        transportContext = TransportContext.RELAY,
        clientObservedPathDigest = HEX64_B,
        runtimeObservedPathDigest = HEX64_C,
        validatedAtMillis = 1_000_000uL,
        expiresAtMillis = 1_000_001uL,
    )

    private fun p256Key(fill: Int): ByteArray = (if (fill == 1) P256_G else P256_2G)
        .chunked(2)
        .map { it.toInt(16).toByte() }
        .toByteArray()

    private companion object {
        const val HEX32 = "00112233445566778899aabbccddeeff"
        const val HEX32_B = "ffeeddccbbaa99887766554433221100"
        val HEX64_A = "a".repeat(64)
        val HEX64_B = "b".repeat(64)
        val HEX64_C = "c".repeat(64)
        val HEX64_D = "d".repeat(64)
        const val P256_G = "046b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296" +
            "4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5"
        const val P256_2G = "047cf27b188d034f7e8a52380304b51ac3c08969e277f21b35a60b48fc47669978" +
            "07775510db8ed040293d9ac69f7430dbba7dade63ce982299e04b79d227873d1"
    }
}
