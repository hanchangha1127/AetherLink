package com.localagentbridge.android.core.protocol.p2pnat

import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest

object ProductionPairStateContract {
    const val AUTHORITY_OBJECT_TYPE: Int = 8
    const val SNAPSHOT_OBJECT_TYPE: Int = 9
    const val MAX_AUTHORITY_BYTES: Int = 1_024
    const val MAX_SNAPSHOT_BYTES: Int = 8_192
    const val MAX_CONSUMED_ENTRIES: Int = 64
    const val MAX_TRANSITION_HISTORY_ENTRIES: Int = 20
    const val PROFILE: String = ProductionSecureSessionContract.PROFILE

    const val MAX_REPLAY_TOMBSTONES: Int = MAX_CONSUMED_ENTRIES
}

enum class ProductionPairAuthorityStatus(val wireValue: String) {
    ACTIVE("active"),
    REVOKED("revoked");

    companion object {
        internal fun decode(value: String): ProductionPairAuthorityStatus =
            entries.singleOrNull { it.wireValue == value }
                ?: throw ProductionPairStateException(ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE)
    }
}

data class ProductionPairAuthorityState(
    val pairBindingDigest: String,
    val pairEpoch: ULong,
    val clientIdentityFingerprint: String,
    val runtimeIdentityFingerprint: String,
    val generation: ULong,
    val serviceConfigVersion: ULong,
    val keysetVersion: ULong,
    val revocationCounter: ULong,
    val protocolFloor: UInt,
    val status: ProductionPairAuthorityStatus,
    val transitionId: String,
    val transitionRequestDigest: String,
    val acceptedReceiptDigest: String,
    val authorityRevision: ULong,
) {
    init {
        ProductionPairStateCodec.validate(this)
    }

    fun canonicalBytes(): ByteArray = ProductionPairStateCodec.encode(this)

    fun digest(): ByteArray = ProductionPairStateCodec.sha256(canonicalBytes())

    fun digestHex(): String = digest().lowerHex()

    val profile: String get() = ProductionPairStateContract.PROFILE
    val secureSessionProfile: String get() = profile

    companion object {
        const val PROFILE: String = ProductionPairStateContract.PROFILE

        fun decode(canonicalBytes: ByteArray): ProductionPairAuthorityState =
            ProductionPairStateCodec.decodeAuthorityState(canonicalBytes)
    }
}

class ProductionPairStateSnapshot(
    val authority: ProductionPairAuthorityState,
    val localRevision: ULong,
    consumedEntries: List<ProductionPairConsumedSession> = emptyList(),
    transitionHistory: List<ProductionPairTransitionHistoryEntry> = emptyList(),
) {
    private val consumedEntryValues = consumedEntries.toList()
    private val transitionHistoryValues = transitionHistory.toList()
    val consumedEntries: List<ProductionPairConsumedSession> get() = consumedEntryValues.toList()
    val transitionHistory: List<ProductionPairTransitionHistoryEntry> get() = transitionHistoryValues.toList()

    init {
        ProductionPairStateCodec.validate(this)
    }

    val state: ProductionPairAuthorityState get() = authority
    val authorityState: ProductionPairAuthorityState get() = authority
    val snapshotRevision: ULong get() = localRevision
    val replayTombstones: Map<String, String> get() = consumedEntries.associate { it.sessionId to it.transcriptDigest }

    fun canonicalBytes(): ByteArray = ProductionPairStateCodec.encode(this)

    fun digest(): ByteArray = ProductionPairStateCodec.sha256(canonicalBytes())

    fun digestHex(): String = digest().lowerHex()

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is ProductionPairStateSnapshot &&
                authority == other.authority &&
                localRevision == other.localRevision &&
                consumedEntries == other.consumedEntries &&
                transitionHistory == other.transitionHistory)

    override fun hashCode(): Int {
        var result = authority.hashCode()
        result = 31 * result + localRevision.hashCode()
        result = 31 * result + consumedEntries.hashCode()
        result = 31 * result + transitionHistory.hashCode()
        return result
    }

    companion object {
        fun decode(canonicalBytes: ByteArray): ProductionPairStateSnapshot =
            ProductionPairStateCodec.decodeSnapshot(canonicalBytes)
    }
}

data class ProductionPairConsumedSession(
    val sessionId: String,
    val transcriptDigest: String,
) {
    init {
        ProductionPairStateCodec.validate(this)
    }
}

data class ProductionPairTransitionHistoryEntry(
    val transitionId: String,
    val transitionRequestDigest: String,
) {
    init {
        ProductionPairStateCodec.validate(this)
    }
}

data class ProductionPairStateTransition(
    val expectedPreviousAuthorityDigest: String?,
    val nextAuthority: ProductionPairAuthorityState,
) {
    init {
        expectedPreviousAuthorityDigest?.let(ProductionPairStateCodec::requireCanonicalDigest)
    }
}

enum class ProductionPairStateRejectionReason {
    INVALID_CANONICAL_STATE,
    MISSING_CURRENT_STATE,
    UNEXPECTED_CURRENT_STATE,
    PREVIOUS_STATE_MISMATCH,
    TRANSITION_ID_CONFLICT,
    TRANSITION_HISTORY_CAPACITY_EXHAUSTED,
    NON_MONOTONIC_PAIR_EPOCH,
    NON_MONOTONIC_GENERATION,
    NON_MONOTONIC_SERVICE_CONFIG,
    NON_MONOTONIC_KEYSET,
    NON_MONOTONIC_REVOCATION,
    NON_MONOTONIC_PROTOCOL_FLOOR,
    INVALID_EPOCH_TRANSITION,
    INVALID_TRANSITION,
    REVOKED_PAIR,
    ROUTE_AUTHORIZATION_MISMATCH,
    PAIR_BINDING_MISMATCH,
    PAIR_EPOCH_MISMATCH,
    CLIENT_IDENTITY_MISMATCH,
    RUNTIME_IDENTITY_MISMATCH,
    GENERATION_MISMATCH,
    SERVICE_CONFIG_MISMATCH,
    KEYSET_MISMATCH,
    REVOCATION_MISMATCH,
    PROTOCOL_DOWNGRADE,
    PROFILE_DOWNGRADE,
    SESSION_REPLAY,
    TRANSCRIPT_REPLAY,
    REPLAY_CAPACITY_EXHAUSTED,
    SNAPSHOT_REVISION_EXHAUSTED,
}

class ProductionPairStateException(
    val reason: ProductionPairStateRejectionReason,
) : IllegalArgumentException(reason.name.lowercase())

enum class ProductionPairStateTransitionDisposition {
    APPLIED,
    IDEMPOTENT,
}

data class ProductionPairStateTransitionResult(
    val disposition: ProductionPairStateTransitionDisposition,
    val snapshot: ProductionPairStateSnapshot,
)

class ProductionPairAdmissionPreparation internal constructor(
    val snapshot: ProductionPairStateSnapshot,
    val bindingDigest: String,
    val sessionId: String,
    val transcriptDigest: String,
    val routeAuthorizationDigest: String,
    val pairAuthorityDigest: String,
    val previousPairSnapshotDigest: String,
    val pairSnapshotDigest: String,
) {
    init {
        listOf(
            bindingDigest,
            transcriptDigest,
            routeAuthorizationDigest,
            pairAuthorityDigest,
            previousPairSnapshotDigest,
            pairSnapshotDigest,
        ).forEach(ProductionPairStateCodec::requireCanonicalDigest)
        rejectUnless(
            sessionId.isNotBlank() &&
                pairAuthorityDigest == snapshot.authority.digestHex() &&
                pairSnapshotDigest == snapshot.digestHex(),
            ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE,
        )
    }

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is ProductionPairAdmissionPreparation &&
                snapshot == other.snapshot &&
                bindingDigest == other.bindingDigest &&
                sessionId == other.sessionId &&
                transcriptDigest == other.transcriptDigest &&
                routeAuthorizationDigest == other.routeAuthorizationDigest &&
                pairAuthorityDigest == other.pairAuthorityDigest &&
                previousPairSnapshotDigest == other.previousPairSnapshotDigest &&
                pairSnapshotDigest == other.pairSnapshotDigest)

    override fun hashCode(): Int = bindingDigest.hashCode()
}

typealias ProductionPairAdmissionResult = ProductionPairAdmissionPreparation
typealias ProductionPairStateAdmissionResult = ProductionPairAdmissionPreparation

object ProductionPairStateMachine {
    fun apply(
        transition: ProductionPairStateTransition,
        current: ProductionPairStateSnapshot?,
    ): ProductionPairStateTransitionResult {
        val proposed = transition.nextAuthority
        if (current == null) {
            rejectUnless(
                transition.expectedPreviousAuthorityDigest == null,
                ProductionPairStateRejectionReason.PREVIOUS_STATE_MISMATCH,
            )
            rejectUnless(
                proposed.authorityRevision == 1uL && proposed.status == ProductionPairAuthorityStatus.ACTIVE,
                ProductionPairStateRejectionReason.INVALID_TRANSITION,
            )
            return ProductionPairStateTransitionResult(
                disposition = ProductionPairStateTransitionDisposition.APPLIED,
                snapshot = ProductionPairStateSnapshot(
                    authority = proposed,
                    localRevision = 1uL,
                )
            )
        }

        val existing = current.authority
        if (proposed.transitionId == existing.transitionId) {
            rejectUnless(
                proposed.transitionRequestDigest == existing.transitionRequestDigest &&
                    proposed.digestHex() == existing.digestHex(),
                ProductionPairStateRejectionReason.TRANSITION_ID_CONFLICT,
            )
            return ProductionPairStateTransitionResult(
                disposition = ProductionPairStateTransitionDisposition.IDEMPOTENT,
                snapshot = current,
            )
        }
        rejectUnless(proposed != existing, ProductionPairStateRejectionReason.INVALID_TRANSITION)
        rejectUnless(
            current.transitionHistory.none { it.transitionId == proposed.transitionId },
            ProductionPairStateRejectionReason.TRANSITION_ID_CONFLICT,
        )
        rejectUnless(
            transition.expectedPreviousAuthorityDigest == existing.digestHex(),
            ProductionPairStateRejectionReason.PREVIOUS_STATE_MISMATCH,
        )
        requireMonotonic(proposed, existing)
        rejectUnless(
            proposed.authorityRevision == existing.authorityRevision.incrementOrReject(),
            ProductionPairStateRejectionReason.INVALID_TRANSITION,
        )
        rejectUnless(
            proposed.pairEpoch == existing.pairEpoch,
            ProductionPairStateRejectionReason.INVALID_EPOCH_TRANSITION,
        )
        requireSamePair(proposed, existing)
        rejectUnless(
            !(existing.status == ProductionPairAuthorityStatus.REVOKED &&
                proposed.status == ProductionPairAuthorityStatus.ACTIVE),
            ProductionPairStateRejectionReason.INVALID_TRANSITION,
        )
        if (proposed.status == ProductionPairAuthorityStatus.REVOKED &&
            existing.status == ProductionPairAuthorityStatus.ACTIVE
        ) {
            rejectUnless(
                proposed.revocationCounter == existing.revocationCounter.incrementOrReject(),
                ProductionPairStateRejectionReason.INVALID_TRANSITION,
            )
        }
        rejectUnless(hasAuthoritativeAdvance(existing, proposed), ProductionPairStateRejectionReason.INVALID_TRANSITION)

        val nextRevision = current.snapshotRevision.incrementOrRejectRevision()
        rejectUnless(
            current.transitionHistory.size < ProductionPairStateContract.MAX_TRANSITION_HISTORY_ENTRIES,
            ProductionPairStateRejectionReason.TRANSITION_HISTORY_CAPACITY_EXHAUSTED,
        )
        val retainsReplayWindow = proposed.pairBindingDigest == existing.pairBindingDigest &&
            proposed.pairEpoch == existing.pairEpoch &&
            proposed.generation == existing.generation
        return ProductionPairStateTransitionResult(
            disposition = ProductionPairStateTransitionDisposition.APPLIED,
            snapshot = ProductionPairStateSnapshot(
                authority = proposed,
                localRevision = nextRevision,
                consumedEntries = if (retainsReplayWindow) current.consumedEntries else emptyList(),
                transitionHistory = current.transitionHistory + ProductionPairTransitionHistoryEntry(
                    transitionId = existing.transitionId,
                    transitionRequestDigest = existing.transitionRequestDigest,
                ),
            )
        )
    }

    private fun requireMonotonic(
        proposed: ProductionPairAuthorityState,
        existing: ProductionPairAuthorityState,
    ) {
        rejectUnless(proposed.pairEpoch >= existing.pairEpoch, ProductionPairStateRejectionReason.NON_MONOTONIC_PAIR_EPOCH)
        rejectUnless(proposed.generation >= existing.generation, ProductionPairStateRejectionReason.NON_MONOTONIC_GENERATION)
        rejectUnless(
            proposed.serviceConfigVersion >= existing.serviceConfigVersion,
            ProductionPairStateRejectionReason.NON_MONOTONIC_SERVICE_CONFIG,
        )
        rejectUnless(proposed.keysetVersion >= existing.keysetVersion, ProductionPairStateRejectionReason.NON_MONOTONIC_KEYSET)
        rejectUnless(
            proposed.revocationCounter >= existing.revocationCounter,
            ProductionPairStateRejectionReason.NON_MONOTONIC_REVOCATION,
        )
        rejectUnless(
            proposed.protocolFloor >= existing.protocolFloor,
            ProductionPairStateRejectionReason.NON_MONOTONIC_PROTOCOL_FLOOR,
        )
    }

    private fun requireSamePair(
        proposed: ProductionPairAuthorityState,
        existing: ProductionPairAuthorityState,
    ) {
        rejectUnless(
            proposed.pairBindingDigest == existing.pairBindingDigest &&
                proposed.pairEpoch == existing.pairEpoch &&
                proposed.clientIdentityFingerprint == existing.clientIdentityFingerprint &&
                proposed.runtimeIdentityFingerprint == existing.runtimeIdentityFingerprint &&
                proposed.profile == existing.profile,
            ProductionPairStateRejectionReason.INVALID_TRANSITION,
        )
    }

    private fun hasAuthoritativeAdvance(
        previous: ProductionPairAuthorityState,
        next: ProductionPairAuthorityState,
    ): Boolean = previous.pairBindingDigest != next.pairBindingDigest ||
        previous.pairEpoch != next.pairEpoch ||
        previous.clientIdentityFingerprint != next.clientIdentityFingerprint ||
        previous.runtimeIdentityFingerprint != next.runtimeIdentityFingerprint ||
        previous.generation != next.generation ||
        previous.serviceConfigVersion != next.serviceConfigVersion ||
        previous.keysetVersion != next.keysetVersion ||
        previous.revocationCounter != next.revocationCounter ||
        previous.protocolFloor != next.protocolFloor ||
        previous.status != next.status
}

object ProductionPairStateAdmission {
    /** Returns a non-authorizing replay-state preparation; durable permit minting belongs to a store. */
    fun admit(
        transcript: ProductionSecureSessionTranscript,
        routeAuthorization: ProductionRouteAuthorization,
        current: ProductionPairStateSnapshot,
    ): ProductionPairAdmissionPreparation {
        when (routeAuthorization.kind) {
            ProductionRouteAuthorizationKind.P2P_PUBLISH,
            ProductionRouteAuthorizationKind.P2P_FETCH,
            ProductionRouteAuthorizationKind.P2P_DIRECT,
            -> throw ProductionPairStateException(
                ProductionPairStateRejectionReason.ROUTE_AUTHORIZATION_MISMATCH,
            )
            ProductionRouteAuthorizationKind.LOCAL_DIRECT,
            ProductionRouteAuthorizationKind.TURN_RELAY,
            ProductionRouteAuthorizationKind.SEALED_RELAY,
            -> Unit
        }
        val state = current.authorityState
        rejectUnless(state.status == ProductionPairAuthorityStatus.ACTIVE, ProductionPairStateRejectionReason.REVOKED_PAIR)
        rejectUnless(
            ProductionSecureSessionCodec.matches(transcript, routeAuthorization),
            ProductionPairStateRejectionReason.ROUTE_AUTHORIZATION_MISMATCH,
        )
        rejectUnless(transcript.pairBindingDigest == state.pairBindingDigest, ProductionPairStateRejectionReason.PAIR_BINDING_MISMATCH)
        rejectUnless(transcript.pairEpoch == state.pairEpoch, ProductionPairStateRejectionReason.PAIR_EPOCH_MISMATCH)
        rejectUnless(
            transcript.clientIdentityFingerprint == state.clientIdentityFingerprint,
            ProductionPairStateRejectionReason.CLIENT_IDENTITY_MISMATCH,
        )
        rejectUnless(
            transcript.runtimeIdentityFingerprint == state.runtimeIdentityFingerprint,
            ProductionPairStateRejectionReason.RUNTIME_IDENTITY_MISMATCH,
        )
        rejectUnless(transcript.generation == state.generation, ProductionPairStateRejectionReason.GENERATION_MISMATCH)
        rejectUnless(
            transcript.serviceConfigVersion == state.serviceConfigVersion,
            ProductionPairStateRejectionReason.SERVICE_CONFIG_MISMATCH,
        )
        rejectUnless(transcript.keysetVersion == state.keysetVersion, ProductionPairStateRejectionReason.KEYSET_MISMATCH)
        rejectUnless(
            transcript.revocationCounter == state.revocationCounter,
            ProductionPairStateRejectionReason.REVOCATION_MISMATCH,
        )
        rejectUnless(
            transcript.protocolVersion >= state.protocolFloor &&
                transcript.minimumProtocolVersion >= state.protocolFloor,
            ProductionPairStateRejectionReason.PROTOCOL_DOWNGRADE,
        )
        rejectUnless(transcript.profile == state.profile, ProductionPairStateRejectionReason.PROFILE_DOWNGRADE)

        val transcriptDigest = ProductionSecureSessionCodec.digest(transcript).lowerHex()
        rejectUnless(
            transcript.sessionId !in current.replayTombstones,
            ProductionPairStateRejectionReason.SESSION_REPLAY,
        )
        rejectUnless(
            transcriptDigest !in current.replayTombstones.values,
            ProductionPairStateRejectionReason.TRANSCRIPT_REPLAY,
        )
        rejectUnless(
            current.replayTombstones.size < ProductionPairStateContract.MAX_REPLAY_TOMBSTONES,
            ProductionPairStateRejectionReason.REPLAY_CAPACITY_EXHAUSTED,
        )
        val nextRevision = current.snapshotRevision.incrementOrRejectRevision()
        val next = ProductionPairStateSnapshot(
            authority = state,
            localRevision = nextRevision,
            consumedEntries = current.consumedEntries + ProductionPairConsumedSession(
                sessionId = transcript.sessionId,
                transcriptDigest = transcriptDigest,
            ),
            transitionHistory = current.transitionHistory,
        )
        val permitBytes = ProductionSecureSessionCodec.digest(transcript) +
            ProductionSecureSessionCodec.digest(routeAuthorization) +
            next.digest()
        return ProductionPairAdmissionPreparation(
            snapshot = next,
            bindingDigest = ProductionPairStateCodec.sha256(permitBytes).lowerHex(),
            sessionId = transcript.sessionId,
            transcriptDigest = transcriptDigest,
            routeAuthorizationDigest = ProductionSecureSessionCodec.digest(routeAuthorization).lowerHex(),
            pairAuthorityDigest = current.authority.digestHex(),
            previousPairSnapshotDigest = current.digestHex(),
            pairSnapshotDigest = next.digestHex(),
        )
    }
}

private object ProductionPairStateCodec {
    private const val STATE_FIELD_COUNT = 16
    private const val LEGACY_SNAPSHOT_FIELD_COUNT = 5
    private const val SNAPSHOT_FIELD_COUNT_WITH_TRANSITION_HISTORY = 7
    private val lowerHex32 = Regex("[0-9a-f]{32}")
    private val lowerHex64 = Regex("[0-9a-f]{64}")

    fun validate(value: ProductionPairAuthorityState) {
        requireHex64(value.pairBindingDigest)
        rejectUnless(value.pairEpoch > 0uL, ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE)
        requireHex64(value.clientIdentityFingerprint)
        requireHex64(value.runtimeIdentityFingerprint)
        rejectUnless(
            value.clientIdentityFingerprint != value.runtimeIdentityFingerprint,
            ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE,
        )
        rejectUnless(value.generation > 0uL, ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE)
        rejectUnless(value.serviceConfigVersion > 0uL, ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE)
        rejectUnless(value.keysetVersion > 0uL, ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE)
        rejectUnless(value.protocolFloor > 0u, ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE)
        rejectUnless(
            value.profile == ProductionPairStateContract.PROFILE,
            ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE,
        )
        requireHex64(value.transitionId)
        requireHex64(value.transitionRequestDigest)
        requireHex64(value.acceptedReceiptDigest)
        rejectUnless(value.authorityRevision > 0uL, ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE)
    }

    fun validate(value: ProductionPairStateSnapshot) {
        rejectUnless(value.localRevision > 0uL, ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE)
        rejectUnless(
            value.consumedEntries.size <= ProductionPairStateContract.MAX_REPLAY_TOMBSTONES,
            ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE,
        )
        val sessionIds = linkedSetOf<String>()
        val transcriptDigests = linkedSetOf<String>()
        value.consumedEntries.forEach { entry ->
            requireHex32(entry.sessionId)
            requireHex64(entry.transcriptDigest)
            rejectUnless(sessionIds.add(entry.sessionId), ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE)
            rejectUnless(transcriptDigests.add(entry.transcriptDigest), ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE)
        }
        rejectUnless(
            value.transitionHistory.size <= ProductionPairStateContract.MAX_TRANSITION_HISTORY_ENTRIES,
            ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE,
        )
        val transitionIds = linkedSetOf<String>()
        value.transitionHistory.forEach { entry ->
            requireHex64(entry.transitionId)
            requireHex64(entry.transitionRequestDigest)
            rejectUnless(
                transitionIds.add(entry.transitionId),
                ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE,
            )
        }
        rejectUnless(
            value.authority.transitionId !in transitionIds,
            ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE,
        )
    }

    fun validate(value: ProductionPairConsumedSession) {
        requireHex32(value.sessionId)
        requireHex64(value.transcriptDigest)
    }

    fun validate(value: ProductionPairTransitionHistoryEntry) {
        requireHex64(value.transitionId)
        requireHex64(value.transitionRequestDigest)
    }

    fun encode(value: ProductionPairAuthorityState): ByteArray {
        validate(value)
        return frame(
            ProductionPairStateContract.AUTHORITY_OBJECT_TYPE,
            listOf(
                ascii(ProductionSecureSessionContract.SUITE),
                ascii(value.pairBindingDigest),
                uint64(value.pairEpoch),
                ascii(value.clientIdentityFingerprint),
                ascii(value.runtimeIdentityFingerprint),
                uint64(value.generation),
                uint64(value.serviceConfigVersion),
                uint64(value.keysetVersion),
                uint64(value.revocationCounter),
                uint32(value.protocolFloor),
                ascii(ProductionPairStateContract.PROFILE),
                ascii(value.status.wireValue),
                ascii(value.transitionId),
                ascii(value.transitionRequestDigest),
                ascii(value.acceptedReceiptDigest),
                uint64(value.authorityRevision),
            ),
            ProductionPairStateContract.MAX_AUTHORITY_BYTES,
        )
    }

    fun decodeAuthorityState(encoded: ByteArray): ProductionPairAuthorityState {
        val fields = parse(
            encoded,
            ProductionPairStateContract.AUTHORITY_OBJECT_TYPE,
            STATE_FIELD_COUNT,
            ProductionPairStateContract.MAX_AUTHORITY_BYTES,
        )
        requireSuite(fields[0])
        return ProductionPairAuthorityState(
            pairBindingDigest = decodeHex64(fields[1]),
            pairEpoch = decodePositiveUInt64(fields[2]),
            clientIdentityFingerprint = decodeHex64(fields[3]),
            runtimeIdentityFingerprint = decodeHex64(fields[4]),
            generation = decodePositiveUInt64(fields[5]),
            serviceConfigVersion = decodePositiveUInt64(fields[6]),
            keysetVersion = decodePositiveUInt64(fields[7]),
            revocationCounter = decodeUInt64(fields[8]),
            protocolFloor = decodePositiveUInt32(fields[9]),
            status = ProductionPairAuthorityStatus.decode(decodeAscii(fields[11])),
            transitionId = decodeHex64(fields[12]),
            transitionRequestDigest = decodeHex64(fields[13]),
            acceptedReceiptDigest = decodeHex64(fields[14]),
            authorityRevision = decodePositiveUInt64(fields[15]),
        ).also {
            rejectUnless(
                decodeAscii(fields[10]) == ProductionPairStateContract.PROFILE &&
                    it.canonicalBytes().contentEquals(encoded),
                ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE,
            )
        }
    }

    fun encode(value: ProductionPairStateSnapshot): ByteArray {
        validate(value)
        val replayBytes = ByteArrayOutputStream().apply {
            value.consumedEntries.forEach { entry ->
                write(ascii(entry.sessionId))
                write(ascii(entry.transcriptDigest))
            }
        }.toByteArray()
        val legacyFields = listOf(
            ascii(ProductionSecureSessionContract.SUITE),
            value.authority.canonicalBytes(),
            uint64(value.localRevision),
            uint32(value.consumedEntries.size.toUInt()),
            replayBytes,
        )
        val fields = if (value.transitionHistory.isEmpty()) {
            legacyFields
        } else {
            legacyFields + listOf(
                uint32(value.transitionHistory.size.toUInt()),
                ByteArrayOutputStream().apply {
                    value.transitionHistory.forEach { entry ->
                        write(hexBytes(entry.transitionId))
                        write(hexBytes(entry.transitionRequestDigest))
                    }
                }.toByteArray(),
            )
        }
        return frame(
            ProductionPairStateContract.SNAPSHOT_OBJECT_TYPE,
            fields,
            ProductionPairStateContract.MAX_SNAPSHOT_BYTES,
        )
    }

    fun decodeSnapshot(encoded: ByteArray): ProductionPairStateSnapshot {
        val fields = try {
            parse(
                encoded,
                ProductionPairStateContract.SNAPSHOT_OBJECT_TYPE,
                SNAPSHOT_FIELD_COUNT_WITH_TRANSITION_HISTORY,
                ProductionPairStateContract.MAX_SNAPSHOT_BYTES,
            )
        } catch (_: ProductionPairStateException) {
            parse(
                encoded,
                ProductionPairStateContract.SNAPSHOT_OBJECT_TYPE,
                LEGACY_SNAPSHOT_FIELD_COUNT,
                ProductionPairStateContract.MAX_SNAPSHOT_BYTES,
            )
        }
        requireSuite(fields[0])
        val replayCount = decodeUInt32(fields[3])
        val replay = decodeReplay(fields[4], replayCount)
        val transitionHistory = if (fields.size == SNAPSHOT_FIELD_COUNT_WITH_TRANSITION_HISTORY) {
            decodeTransitionHistory(fields[6], decodeUInt32(fields[5]))
        } else {
            emptyList()
        }
        return ProductionPairStateSnapshot(
            authority = decodeAuthorityState(fields[1]),
            localRevision = decodePositiveUInt64(fields[2]),
            consumedEntries = replay,
            transitionHistory = transitionHistory,
        ).also {
            rejectUnless(
                it.canonicalBytes().contentEquals(encoded),
                ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE,
            )
        }
    }

    fun sha256(value: ByteArray): ByteArray = MessageDigest.getInstance("SHA-256").digest(value)

    private fun decodeReplay(encoded: ByteArray, countValue: UInt): List<ProductionPairConsumedSession> {
        val reader = ByteBuffer.wrap(encoded).order(ByteOrder.BIG_ENDIAN)
        val count = countValue.toLong()
        rejectUnless(
            count <= ProductionPairStateContract.MAX_REPLAY_TOMBSTONES.toLong() &&
                encoded.size.toLong() == count * 96L,
            ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE,
        )
        val replay = mutableListOf<ProductionPairConsumedSession>()
        val sessionIds = linkedSetOf<String>()
        val transcriptDigests = linkedSetOf<String>()
        repeat(count.toInt()) {
            val sessionBytes = ByteArray(32).also(reader::get)
            val digestBytes = ByteArray(64).also(reader::get)
            val sessionId = decodeHex32(sessionBytes)
            val transcriptDigest = decodeHex64(digestBytes)
            rejectUnless(sessionIds.add(sessionId), ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE)
            rejectUnless(transcriptDigests.add(transcriptDigest), ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE)
            replay += ProductionPairConsumedSession(sessionId, transcriptDigest)
        }
        return replay
    }

    private fun decodeTransitionHistory(
        encoded: ByteArray,
        countValue: UInt,
    ): List<ProductionPairTransitionHistoryEntry> {
        val count = countValue.toLong()
        rejectUnless(
            count in 1..ProductionPairStateContract.MAX_TRANSITION_HISTORY_ENTRIES.toLong() &&
                encoded.size.toLong() == count * 64L,
            ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE,
        )
        val reader = ByteBuffer.wrap(encoded)
        val transitionHistory = mutableListOf<ProductionPairTransitionHistoryEntry>()
        val uniqueIds = linkedSetOf<String>()
        repeat(count.toInt()) {
            val transitionId = ByteArray(32).also(reader::get).lowerHex()
            val transitionRequestDigest = ByteArray(32).also(reader::get).lowerHex()
            rejectUnless(
                uniqueIds.add(transitionId),
                ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE,
            )
            transitionHistory += ProductionPairTransitionHistoryEntry(
                transitionId = transitionId,
                transitionRequestDigest = transitionRequestDigest,
            )
        }
        return transitionHistory
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
            rejectUnless(it.size <= maximumBytes, ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE)
        }
    }

    private fun parse(encoded: ByteArray, objectType: Int, fieldCount: Int, maximumBytes: Int): List<ByteArray> {
        rejectUnless(encoded.size in 6..maximumBytes, ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE)
        val reader = ByteBuffer.wrap(encoded).order(ByteOrder.BIG_ENDIAN)
        val magic = ByteArray(4).also(reader::get)
        rejectUnless(magic.contentEquals(ProductionSecureSessionContract.MAGIC), ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE)
        rejectUnless(reader.get().toInt() and 0xff == objectType, ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE)
        rejectUnless(
            reader.get().toInt() and 0xff == ProductionSecureSessionContract.VERSION,
            ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE,
        )
        val fields = ArrayList<ByteArray>(fieldCount)
        repeat(fieldCount) { index ->
            rejectUnless(reader.remaining() >= 5, ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE)
            rejectUnless(reader.get().toInt() and 0xff == index + 1, ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE)
            val size = reader.int.toUInt().toLong()
            rejectUnless(size <= reader.remaining().toLong(), ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE)
            fields += ByteArray(size.toInt()).also(reader::get)
        }
        rejectUnless(!reader.hasRemaining(), ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE)
        return fields
    }

    private fun requireSuite(value: ByteArray) {
        rejectUnless(
            decodeAscii(value) == ProductionSecureSessionContract.SUITE,
            ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE,
        )
    }

    private fun ascii(value: String): ByteArray {
        rejectUnless(value.isNotEmpty() && value.all { it.code in 0x21..0x7e }, ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE)
        return value.toByteArray(Charsets.US_ASCII)
    }

    private fun decodeAscii(value: ByteArray): String {
        rejectUnless(value.isNotEmpty() && value.all { it.toInt() and 0xff in 0x21..0x7e }, ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE)
        return value.toString(Charsets.US_ASCII)
    }

    private fun decodeHex32(value: ByteArray): String = decodeAscii(value).also(::requireHex32)
    private fun decodeHex64(value: ByteArray): String = decodeAscii(value).also(::requireHex64)

    private fun hexBytes(value: String): ByteArray {
        requireHex64(value)
        return value.chunked(2).map { it.toInt(16).toByte() }.toByteArray()
    }

    private fun requireHex32(value: String) {
        rejectUnless(lowerHex32.matches(value), ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE)
    }

    private fun requireHex64(value: String) {
        rejectUnless(lowerHex64.matches(value), ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE)
    }

    fun requireCanonicalDigest(value: String) = requireHex64(value)

    private fun uint32(value: UInt): ByteArray = ByteBuffer.allocate(4).order(ByteOrder.BIG_ENDIAN).putInt(value.toInt()).array()
    private fun uint64(value: ULong): ByteArray = ByteBuffer.allocate(8).order(ByteOrder.BIG_ENDIAN).putLong(value.toLong()).array()

    private fun decodePositiveUInt32(value: ByteArray): UInt {
        return decodeUInt32(value).also {
            rejectUnless(it > 0u, ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE)
        }
    }

    private fun decodeUInt32(value: ByteArray): UInt {
        rejectUnless(value.size == 4, ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE)
        return ByteBuffer.wrap(value).order(ByteOrder.BIG_ENDIAN).int.toUInt()
    }

    private fun decodeUInt64(value: ByteArray): ULong {
        rejectUnless(value.size == 8, ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE)
        return ByteBuffer.wrap(value).order(ByteOrder.BIG_ENDIAN).long.toULong()
    }

    private fun decodePositiveUInt64(value: ByteArray): ULong = decodeUInt64(value).also {
        rejectUnless(it > 0uL, ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE)
    }
}

private fun rejectUnless(condition: Boolean, reason: ProductionPairStateRejectionReason) {
    if (!condition) throw ProductionPairStateException(reason)
}

private fun ULong.incrementOrReject(): ULong {
    rejectUnless(this != ULong.MAX_VALUE, ProductionPairStateRejectionReason.INVALID_TRANSITION)
    return this + 1uL
}

private fun ULong.incrementOrRejectRevision(): ULong {
    rejectUnless(this != ULong.MAX_VALUE, ProductionPairStateRejectionReason.SNAPSHOT_REVISION_EXHAUSTED)
    return this + 1uL
}

private fun ByteArray.lowerHex(): String = joinToString("") { "%02x".format(it.toInt() and 0xff) }
