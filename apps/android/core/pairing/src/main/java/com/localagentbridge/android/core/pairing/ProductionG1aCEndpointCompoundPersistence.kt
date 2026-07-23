package com.localagentbridge.android.core.pairing

import com.localagentbridge.android.core.protocol.p2pnat.ProductionC1EndpointCompoundRecord
import com.localagentbridge.android.core.protocol.p2pnat.ProductionC1EndpointGrantEntry
import com.localagentbridge.android.core.protocol.p2pnat.ProductionC1EndpointGrantLedgerState
import com.localagentbridge.android.core.protocol.p2pnat.ProductionPairConsumedSession
import com.localagentbridge.android.core.protocol.p2pnat.ProductionPairStateContract
import com.localagentbridge.android.core.protocol.p2pnat.ProductionPairStateSnapshot
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest

internal fun interface ProductionC1TrustedClock {
    fun nowMs(): ULong
}

internal object ProductionC1SystemTrustedClock : ProductionC1TrustedClock {
    override fun nowMs(): ULong {
        val now = System.currentTimeMillis()
        check(now >= 0L) { "Trusted production clock returned a negative epoch" }
        return now.toULong()
    }
}

internal object ProductionC1EndpointCompoundPersistenceContract {
    const val VERSION: UInt = 3u
    const val MAX_MARKERS: Int = ProductionPairStateContract.MAX_CONSUMED_ENTRIES
    const val MAX_MARKER_BYTES: Int = 1_024
    const val MAX_ENVELOPE_BYTES: Int = 128 * 1_024
}

internal enum class ProductionC1EndpointPersistenceFailure {
    MALFORMED_CANONICAL,
    IDENTITY_MISMATCH,
    COMMIT_CHAIN_MISMATCH,
    READBACK_MISMATCH,
    STATE_INJECTION_REJECTED,
}

internal class ProductionC1EndpointPersistenceException(
    val failure: ProductionC1EndpointPersistenceFailure,
) : IllegalStateException(failure.name)

internal data class ProductionC1EndpointPersistenceHooks(
    val beforeCommit: (() -> Unit)? = null,
    val afterCommitBeforeReadback: (suspend () -> Unit)? = null,
)

internal class StoredProductionC1EndpointCommitMarker(
    val sequence: UInt,
    val runtimeDeviceIdDigest: String,
    val trustedPublicKeyDigest: String,
    val admissionId: String,
    val bindingDigest: String,
    val endpointEntryDigest: String,
    val sessionId: String,
    /** Compatibility field: generic final P2P_DIRECT authorization digest (object 4). */
    val routeAuthorizationDigest: String,
    /** Transcript-bound grant authorization digest (object 26). */
    val grantAuthorizationDigest: String,
    val pairAuthorityDigest: String,
    val effectiveNotBeforeMs: ULong,
    val expiresAtMs: ULong,
    val previousMarkerDigest: String?,
    val expectedCompoundDigest: String,
    val committedCompoundDigest: String,
    val committedPairSnapshotDigest: String,
    val committedLedgerSnapshotDigest: String,
    val pairLocalRevision: ULong,
    val ledgerRevision: ULong,
) {
    init {
        endpointPersistenceRequire(
            sequence > 0u &&
                effectiveNotBeforeMs < expiresAtMs &&
                pairLocalRevision > 0uL &&
                ledgerRevision > 0uL,
            ProductionC1EndpointPersistenceFailure.MALFORMED_CANONICAL,
        )
        listOf(
            runtimeDeviceIdDigest,
            trustedPublicKeyDigest,
            admissionId,
            bindingDigest,
            endpointEntryDigest,
            routeAuthorizationDigest,
            grantAuthorizationDigest,
            pairAuthorityDigest,
            expectedCompoundDigest,
            committedCompoundDigest,
            committedPairSnapshotDigest,
            committedLedgerSnapshotDigest,
        ).forEach(::endpointPersistenceDigestBytes)
        endpointPersistenceRequire(
            sessionId.length == 32 && sessionId.all { it in '0'..'9' || it in 'a'..'f' },
            ProductionC1EndpointPersistenceFailure.MALFORMED_CANONICAL,
        )
        previousMarkerDigest?.let(::endpointPersistenceDigestBytes)
    }

    fun canonicalBytes(): ByteArray {
        val encoded = ByteArrayOutputStream().apply {
            write(MARKER_MAGIC)
            write(endpointPersistenceBE(ProductionC1EndpointCompoundPersistenceContract.VERSION))
            write(endpointPersistenceBE(sequence))
            write(endpointPersistenceDigestBytes(runtimeDeviceIdDigest))
            write(endpointPersistenceDigestBytes(trustedPublicKeyDigest))
            write(endpointPersistenceDigestBytes(admissionId))
            write(endpointPersistenceDigestBytes(bindingDigest))
            write(endpointPersistenceDigestBytes(endpointEntryDigest))
            write(sessionId.toByteArray(Charsets.US_ASCII))
            write(endpointPersistenceDigestBytes(routeAuthorizationDigest))
            write(endpointPersistenceDigestBytes(grantAuthorizationDigest))
            write(endpointPersistenceDigestBytes(pairAuthorityDigest))
            write(endpointPersistenceBE(effectiveNotBeforeMs))
            write(endpointPersistenceBE(expiresAtMs))
            if (previousMarkerDigest == null) {
                write(0)
            } else {
                write(1)
                write(endpointPersistenceDigestBytes(previousMarkerDigest))
            }
            write(endpointPersistenceDigestBytes(expectedCompoundDigest))
            write(endpointPersistenceDigestBytes(committedCompoundDigest))
            write(endpointPersistenceDigestBytes(committedPairSnapshotDigest))
            write(endpointPersistenceDigestBytes(committedLedgerSnapshotDigest))
            write(endpointPersistenceBE(pairLocalRevision))
            write(endpointPersistenceBE(ledgerRevision))
        }.toByteArray()
        endpointPersistenceRequire(
            encoded.size <= ProductionC1EndpointCompoundPersistenceContract.MAX_MARKER_BYTES,
            ProductionC1EndpointPersistenceFailure.MALFORMED_CANONICAL,
        )
        return encoded
    }

    fun digestHex(): String = endpointPersistenceDigestHex(canonicalBytes())

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is StoredProductionC1EndpointCommitMarker &&
                canonicalBytes().contentEquals(other.canonicalBytes()))

    override fun hashCode(): Int = canonicalBytes().contentHashCode()

    companion object {
        private val MARKER_MAGIC = "ALC1ECM1".toByteArray(Charsets.US_ASCII)

        fun decode(canonicalBytes: ByteArray): StoredProductionC1EndpointCommitMarker {
            endpointPersistenceRequire(
                canonicalBytes.size <= ProductionC1EndpointCompoundPersistenceContract.MAX_MARKER_BYTES,
                ProductionC1EndpointPersistenceFailure.MALFORMED_CANONICAL,
            )
            val reader = EndpointPersistenceReader(canonicalBytes)
            endpointPersistenceRequire(
                reader.read(MARKER_MAGIC.size).contentEquals(MARKER_MAGIC) &&
                    reader.uint32() == ProductionC1EndpointCompoundPersistenceContract.VERSION,
                ProductionC1EndpointPersistenceFailure.MALFORMED_CANONICAL,
            )
            val marker = StoredProductionC1EndpointCommitMarker(
                sequence = reader.uint32(),
                runtimeDeviceIdDigest = reader.digestHex(),
                trustedPublicKeyDigest = reader.digestHex(),
                admissionId = reader.digestHex(),
                bindingDigest = reader.digestHex(),
                endpointEntryDigest = reader.digestHex(),
                sessionId = reader.read(32).toString(Charsets.US_ASCII),
                routeAuthorizationDigest = reader.digestHex(),
                grantAuthorizationDigest = reader.digestHex(),
                pairAuthorityDigest = reader.digestHex(),
                effectiveNotBeforeMs = reader.uint64(),
                expiresAtMs = reader.uint64(),
                previousMarkerDigest = when (reader.byte().toInt() and 0xff) {
                    0 -> null
                    1 -> reader.digestHex()
                    else -> endpointPersistenceFail(
                        ProductionC1EndpointPersistenceFailure.MALFORMED_CANONICAL,
                    )
                },
                expectedCompoundDigest = reader.digestHex(),
                committedCompoundDigest = reader.digestHex(),
                committedPairSnapshotDigest = reader.digestHex(),
                committedLedgerSnapshotDigest = reader.digestHex(),
                pairLocalRevision = reader.uint64(),
                ledgerRevision = reader.uint64(),
            )
            endpointPersistenceRequire(
                reader.isAtEnd && marker.canonicalBytes().contentEquals(canonicalBytes),
                ProductionC1EndpointPersistenceFailure.MALFORMED_CANONICAL,
            )
            return marker
        }
    }
}

internal class StoredProductionC1EndpointCompoundState(
    val pairSnapshot: ProductionPairStateSnapshot,
    val ledger: ProductionC1EndpointGrantLedgerState,
    markers: List<StoredProductionC1EndpointCommitMarker>,
) {
    private val markerValues = markers.toList()
    val markers: List<StoredProductionC1EndpointCommitMarker> get() = markerValues.toList()

    init {
        endpointPersistenceRequire(
            markerValues.isNotEmpty() &&
                markerValues.size <= ProductionC1EndpointCompoundPersistenceContract.MAX_MARKERS,
            ProductionC1EndpointPersistenceFailure.COMMIT_CHAIN_MISMATCH,
        )
        validateChain()
    }

    fun canonicalBytes(): ByteArray {
        val pairBytes = pairSnapshot.canonicalBytes()
        val ledgerBytes = ledger.persistenceCanonicalBytes()
        val markerBytes = markerValues.map(StoredProductionC1EndpointCommitMarker::canonicalBytes)
        val encoded = ByteArrayOutputStream().apply {
            write(ENVELOPE_MAGIC)
            write(endpointPersistenceBE(ProductionC1EndpointCompoundPersistenceContract.VERSION))
            write(endpointPersistenceLengthPrefixed(pairBytes))
            write(endpointPersistenceLengthPrefixed(ledgerBytes))
            write(endpointPersistenceBE(markerBytes.size.toUInt()))
            markerBytes.forEach { write(endpointPersistenceLengthPrefixed(it)) }
        }.toByteArray()
        endpointPersistenceRequire(
            encoded.size <= ProductionC1EndpointCompoundPersistenceContract.MAX_ENVELOPE_BYTES,
            ProductionC1EndpointPersistenceFailure.MALFORMED_CANONICAL,
        )
        return encoded
    }

    fun requireRuntimeIdentity(deviceId: String, trustedPublicKey: String) {
        val deviceDigest = endpointRuntimeIdentityDigest(
            "AetherLink trusted-runtime identifier v1",
            deviceId,
        )
        val keyDigest = endpointRuntimeIdentityDigest(
            "AetherLink trusted-runtime public key v1",
            trustedPublicKey,
        )
        endpointPersistenceRequire(
            markerValues.all {
                it.runtimeDeviceIdDigest == deviceDigest &&
                    it.trustedPublicKeyDigest == keyDigest
            },
            ProductionC1EndpointPersistenceFailure.IDENTITY_MISMATCH,
        )
    }

    private fun validateChain() {
        endpointPersistenceRequire(
            markerValues.size == ledger.entries.size,
            ProductionC1EndpointPersistenceFailure.COMMIT_CHAIN_MISMATCH,
        )
        val chainLength = markerValues.size.toULong()
        endpointPersistenceRequire(
            pairSnapshot.localRevision > chainLength &&
                pairSnapshot.consumedEntries.size >= markerValues.size &&
                ledger.remainingGrants <= ULong.MAX_VALUE - chainLength,
            ProductionC1EndpointPersistenceFailure.COMMIT_CHAIN_MISMATCH,
        )
        val initialPairRevision = pairSnapshot.localRevision - chainLength
        val initialConsumedCount = pairSnapshot.consumedEntries.size - markerValues.size
        var reconstructedPair = ProductionPairStateSnapshot(
            authority = pairSnapshot.authority,
            localRevision = initialPairRevision,
            consumedEntries = pairSnapshot.consumedEntries.take(initialConsumedCount),
            transitionHistory = pairSnapshot.transitionHistory,
        )
        var reconstructedLedger = ProductionC1EndpointGrantLedgerState(
            revision = 1uL,
            pairAuthorityDigest = ledger.pairAuthorityDigest,
            pairLocalRevision = initialPairRevision,
            remainingGrants = ledger.remainingGrants + chainLength,
            retentionLimit = ledger.retentionLimit,
        )
        var previousMarkerDigest: String? = null
        var previousCompoundDigest = ProductionC1EndpointCompoundRecord(
            grantLedger = reconstructedLedger,
            pairSnapshot = reconstructedPair,
        ).digestHex()
        markerValues.zip(ledger.entries).forEachIndexed { index, (marker, entry) ->
            endpointPersistenceRequire(
                reconstructedLedger.remainingGrants > 0uL &&
                    reconstructedPair.localRevision < ULong.MAX_VALUE,
                ProductionC1EndpointPersistenceFailure.COMMIT_CHAIN_MISMATCH,
            )
            val nextPair = ProductionPairStateSnapshot(
                authority = reconstructedPair.authority,
                localRevision = reconstructedPair.localRevision + 1uL,
                consumedEntries = reconstructedPair.consumedEntries + ProductionPairConsumedSession(
                    sessionId = entry.sessionId,
                    transcriptDigest = entry.transcriptDigest,
                ),
                transitionHistory = reconstructedPair.transitionHistory,
            )
            val nextLedger = ProductionC1EndpointGrantLedgerState(
                revision = reconstructedLedger.revision + 1uL,
                pairAuthorityDigest = reconstructedLedger.pairAuthorityDigest,
                pairLocalRevision = nextPair.localRevision,
                remainingGrants = reconstructedLedger.remainingGrants - 1uL,
                retentionLimit = reconstructedLedger.retentionLimit,
                entries = reconstructedLedger.entries + entry,
            )
            val nextCompoundDigest = ProductionC1EndpointCompoundRecord(
                grantLedger = nextLedger,
                pairSnapshot = nextPair,
            ).digestHex()
            endpointPersistenceRequire(
                marker.sequence == (index + 1).toUInt() &&
                    marker.admissionId == entry.admissionId &&
                    marker.bindingDigest == entry.bindingDigest &&
                    marker.endpointEntryDigest == endpointGrantEntryDigest(entry) &&
                    marker.sessionId == entry.sessionId &&
                    marker.routeAuthorizationDigest == entry.routeAuthorizationDigest &&
                    marker.grantAuthorizationDigest == entry.grantAuthorizationDigest &&
                    marker.pairAuthorityDigest == reconstructedLedger.pairAuthorityDigest &&
                    marker.pairAuthorityDigest == reconstructedPair.authority.digestHex() &&
                    marker.effectiveNotBeforeMs < marker.expiresAtMs &&
                    marker.previousMarkerDigest == previousMarkerDigest &&
                    marker.expectedCompoundDigest == previousCompoundDigest &&
                    marker.ledgerRevision == entry.committedRevision &&
                    marker.ledgerRevision == nextLedger.revision &&
                    marker.pairLocalRevision == nextPair.localRevision &&
                    marker.committedPairSnapshotDigest == entry.pairSnapshotDigest &&
                    marker.committedPairSnapshotDigest == nextPair.digestHex() &&
                    marker.committedLedgerSnapshotDigest == nextLedger.snapshotDigestHex() &&
                    marker.committedCompoundDigest == nextCompoundDigest,
                ProductionC1EndpointPersistenceFailure.COMMIT_CHAIN_MISMATCH,
            )
            previousMarkerDigest = marker.digestHex()
            previousCompoundDigest = nextCompoundDigest
            reconstructedPair = nextPair
            reconstructedLedger = nextLedger
        }
        endpointPersistenceRequire(
            reconstructedPair == pairSnapshot && reconstructedLedger == ledger,
            ProductionC1EndpointPersistenceFailure.COMMIT_CHAIN_MISMATCH,
        )
    }

    companion object {
        private val ENVELOPE_MAGIC = "ALC1ECS1".toByteArray(Charsets.US_ASCII)

        fun decode(canonicalBytes: ByteArray): StoredProductionC1EndpointCompoundState {
            endpointPersistenceRequire(
                canonicalBytes.size <= ProductionC1EndpointCompoundPersistenceContract.MAX_ENVELOPE_BYTES,
                ProductionC1EndpointPersistenceFailure.MALFORMED_CANONICAL,
            )
            val reader = EndpointPersistenceReader(canonicalBytes)
            endpointPersistenceRequire(
                reader.read(ENVELOPE_MAGIC.size).contentEquals(ENVELOPE_MAGIC) &&
                    reader.uint32() == ProductionC1EndpointCompoundPersistenceContract.VERSION,
                ProductionC1EndpointPersistenceFailure.MALFORMED_CANONICAL,
            )
            val pair = ProductionPairStateSnapshot.decode(
                reader.lengthPrefixed(ProductionPairStateContract.MAX_SNAPSHOT_BYTES),
            )
            val ledger = ProductionC1EndpointGrantLedgerState.decodePersistenceCanonicalBytes(
                reader.lengthPrefixed(ProductionC1EndpointCompoundPersistenceContract.MAX_ENVELOPE_BYTES),
            )
            val markerCount = reader.uint32().toLong()
            endpointPersistenceRequire(
                markerCount in 1..ProductionC1EndpointCompoundPersistenceContract.MAX_MARKERS.toLong(),
                ProductionC1EndpointPersistenceFailure.MALFORMED_CANONICAL,
            )
            val markers = List(markerCount.toInt()) {
                StoredProductionC1EndpointCommitMarker.decode(
                    reader.lengthPrefixed(ProductionC1EndpointCompoundPersistenceContract.MAX_MARKER_BYTES),
                )
            }
            val state = StoredProductionC1EndpointCompoundState(pair, ledger, markers)
            endpointPersistenceRequire(
                reader.isAtEnd && state.canonicalBytes().contentEquals(canonicalBytes),
                ProductionC1EndpointPersistenceFailure.MALFORMED_CANONICAL,
            )
            return state
        }
    }
}

class ProductionC1EndpointGrantCompoundCommitToken internal constructor(
    val admissionId: String,
    val bindingDigest: String,
    val routeGrantDigest: String,
    val sessionId: String,
    val transcriptDigest: String,
    /** Compatibility field: generic final P2P_DIRECT authorization digest (object 4). */
    val routeAuthorizationDigest: String,
    /** Transcript-bound grant authorization digest (object 26). */
    val grantAuthorizationDigest: String,
    val pairAuthorityDigest: String,
    val connectorInputCommitmentDigest: String,
    val pairSnapshotDigest: String,
    val ledgerSnapshotDigest: String,
    val compoundCommitDigest: String,
    val effectiveNotBeforeMs: ULong,
    val expiresAtMs: ULong,
    val pairLocalRevision: ULong,
    val ledgerRevision: ULong,
    val markerDigest: String,
) {
    init {
        endpointPersistenceRequire(
            effectiveNotBeforeMs < expiresAtMs &&
                sessionId.length == 32 && sessionId.all { it in '0'..'9' || it in 'a'..'f' },
            ProductionC1EndpointPersistenceFailure.COMMIT_CHAIN_MISMATCH,
        )
        listOf(
            admissionId,
            bindingDigest,
            routeGrantDigest,
            transcriptDigest,
            routeAuthorizationDigest,
            grantAuthorizationDigest,
            pairAuthorityDigest,
            connectorInputCommitmentDigest,
            pairSnapshotDigest,
            ledgerSnapshotDigest,
            compoundCommitDigest,
            markerDigest,
        ).forEach(::endpointPersistenceDigestBytes)
    }
}

class ProductionC1EndpointGrantCommitReadback internal constructor(
    val admissionId: String,
    val bindingDigest: String,
    val sessionId: String,
    /** Compatibility field: generic final P2P_DIRECT authorization digest (object 4). */
    val routeAuthorizationDigest: String,
    /** Transcript-bound grant authorization digest (object 26). */
    val grantAuthorizationDigest: String,
    val pairAuthorityDigest: String,
    val compoundCommitDigest: String,
    val effectiveNotBeforeMs: ULong,
    val expiresAtMs: ULong,
    val pairLocalRevision: ULong,
    val ledgerRevision: ULong,
    val markerDigest: String,
) {
    init {
        endpointPersistenceRequire(
            effectiveNotBeforeMs < expiresAtMs &&
                sessionId.length == 32 && sessionId.all { it in '0'..'9' || it in 'a'..'f' },
            ProductionC1EndpointPersistenceFailure.COMMIT_CHAIN_MISMATCH,
        )
        listOf(
            admissionId,
            bindingDigest,
            routeAuthorizationDigest,
            grantAuthorizationDigest,
            pairAuthorityDigest,
            compoundCommitDigest,
            markerDigest,
        ).forEach(::endpointPersistenceDigestBytes)
    }

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is ProductionC1EndpointGrantCommitReadback &&
                admissionId == other.admissionId &&
                bindingDigest == other.bindingDigest &&
                sessionId == other.sessionId &&
                routeAuthorizationDigest == other.routeAuthorizationDigest &&
                grantAuthorizationDigest == other.grantAuthorizationDigest &&
                pairAuthorityDigest == other.pairAuthorityDigest &&
                compoundCommitDigest == other.compoundCommitDigest &&
                effectiveNotBeforeMs == other.effectiveNotBeforeMs &&
                expiresAtMs == other.expiresAtMs &&
                pairLocalRevision == other.pairLocalRevision &&
                ledgerRevision == other.ledgerRevision &&
                markerDigest == other.markerDigest)

    override fun hashCode(): Int {
        var result = admissionId.hashCode()
        result = 31 * result + bindingDigest.hashCode()
        result = 31 * result + sessionId.hashCode()
        result = 31 * result + routeAuthorizationDigest.hashCode()
        result = 31 * result + grantAuthorizationDigest.hashCode()
        result = 31 * result + pairAuthorityDigest.hashCode()
        result = 31 * result + compoundCommitDigest.hashCode()
        result = 31 * result + effectiveNotBeforeMs.hashCode()
        result = 31 * result + expiresAtMs.hashCode()
        result = 31 * result + pairLocalRevision.hashCode()
        result = 31 * result + ledgerRevision.hashCode()
        return 31 * result + markerDigest.hashCode()
    }
}

sealed interface ProductionC1EndpointGrantCommitOutcome {
    data class Committed(
        val token: ProductionC1EndpointGrantCompoundCommitToken,
    ) : ProductionC1EndpointGrantCommitOutcome

    data class AlreadyCommitted(
        val readback: ProductionC1EndpointGrantCommitReadback,
    ) : ProductionC1EndpointGrantCommitOutcome
}

internal fun endpointRuntimeIdentityDigest(domain: String, value: String): String {
    val domainBytes = domain.toByteArray(Charsets.UTF_8)
    val valueBytes = value.toByteArray(Charsets.UTF_8)
    return endpointPersistenceDigestHex(
        ByteArrayOutputStream().apply {
            write(domainBytes)
            write(0)
            write(endpointPersistenceBE(valueBytes.size.toUInt()))
            write(valueBytes)
        }.toByteArray(),
    )
}

internal fun endpointGrantEntryDigest(entry: ProductionC1EndpointGrantEntry): String {
    return endpointPersistenceDigestHex(ByteArrayOutputStream().apply {
        write("AetherLink C1 endpoint grant entry marker v2 object4+object26".toByteArray(Charsets.UTF_8))
        write(0)
        listOf(
            entry.admissionId,
            entry.bindingDigest,
            entry.routeGrantDigest,
            entry.sessionId,
            entry.transcriptDigest,
            entry.routeAuthorizationDigest,
            entry.grantAuthorizationDigest,
            entry.connectorInputCommitmentDigest,
            entry.pairSnapshotDigest,
        ).forEach { value ->
            val bytes = value.toByteArray(Charsets.UTF_8)
            write(endpointPersistenceBE(bytes.size.toUInt()))
            write(bytes)
        }
        write(endpointPersistenceBE(entry.committedRevision))
    }.toByteArray())
}

private class EndpointPersistenceReader(private val bytes: ByteArray) {
    private var offset = 0
    val isAtEnd: Boolean get() = offset == bytes.size

    fun read(count: Int): ByteArray {
        endpointPersistenceRequire(
            count >= 0 && offset <= bytes.size && count <= bytes.size - offset,
            ProductionC1EndpointPersistenceFailure.MALFORMED_CANONICAL,
        )
        return bytes.copyOfRange(offset, offset + count).also { offset += count }
    }

    fun byte(): Byte = read(1)[0]

    fun uint32(): UInt = ByteBuffer.wrap(read(UInt.SIZE_BYTES))
        .order(ByteOrder.BIG_ENDIAN)
        .int
        .toUInt()

    fun uint64(): ULong = ByteBuffer.wrap(read(ULong.SIZE_BYTES))
        .order(ByteOrder.BIG_ENDIAN)
        .long
        .toULong()

    fun digestHex(): String = read(32).joinToString("") { "%02x".format(it.toInt() and 0xff) }

    fun lengthPrefixed(maximumBytes: Int): ByteArray {
        val length = uint32().toLong()
        endpointPersistenceRequire(
            length in 0..maximumBytes.toLong(),
            ProductionC1EndpointPersistenceFailure.MALFORMED_CANONICAL,
        )
        return read(length.toInt())
    }
}

private fun endpointPersistenceLengthPrefixed(bytes: ByteArray): ByteArray =
    endpointPersistenceBE(bytes.size.toUInt()) + bytes

private fun endpointPersistenceBE(value: UInt): ByteArray =
    ByteBuffer.allocate(UInt.SIZE_BYTES).order(ByteOrder.BIG_ENDIAN).putInt(value.toInt()).array()

private fun endpointPersistenceBE(value: ULong): ByteArray =
    ByteBuffer.allocate(ULong.SIZE_BYTES).order(ByteOrder.BIG_ENDIAN).putLong(value.toLong()).array()

private fun endpointPersistenceDigestBytes(value: String): ByteArray {
    endpointPersistenceRequire(
        value.length == 64 && value.all { it in '0'..'9' || it in 'a'..'f' },
        ProductionC1EndpointPersistenceFailure.MALFORMED_CANONICAL,
    )
    return ByteArray(32) { index -> value.substring(index * 2, index * 2 + 2).toInt(16).toByte() }
}

private fun endpointPersistenceDigestHex(bytes: ByteArray): String =
    MessageDigest.getInstance("SHA-256").digest(bytes)
        .joinToString("") { "%02x".format(it.toInt() and 0xff) }

private fun endpointPersistenceRequire(
    condition: Boolean,
    failure: ProductionC1EndpointPersistenceFailure,
) {
    if (!condition) endpointPersistenceFail(failure)
}

private fun endpointPersistenceFail(failure: ProductionC1EndpointPersistenceFailure): Nothing =
    throw ProductionC1EndpointPersistenceException(failure)
