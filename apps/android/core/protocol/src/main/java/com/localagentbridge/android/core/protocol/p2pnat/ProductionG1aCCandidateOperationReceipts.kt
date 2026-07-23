package com.localagentbridge.android.core.protocol.p2pnat

import java.security.PrivateKey
import java.security.PublicKey

enum class ProductionC1CandidateCASDisposition(val wireValue: String) {
    APPLIED("applied"),
    IDEMPOTENT("idempotent"),
}

class ProductionC1CandidateUsageEntry internal constructor(
    val requestId: String,
    val requestDigest: String,
    val capabilityDigest: String,
    val authorizationDigest: String,
    val singleUseNonce: String,
    val consumedBytes: ULong,
    val receiptDigest: String,
    val committedRevision: ULong,
) {
    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is ProductionC1CandidateUsageEntry &&
                requestId == other.requestId &&
                requestDigest == other.requestDigest &&
                capabilityDigest == other.capabilityDigest &&
                authorizationDigest == other.authorizationDigest &&
                singleUseNonce == other.singleUseNonce &&
                consumedBytes == other.consumedBytes &&
                receiptDigest == other.receiptDigest &&
                committedRevision == other.committedRevision)

    override fun hashCode(): Int {
        var result = requestId.hashCode()
        result = 31 * result + requestDigest.hashCode()
        result = 31 * result + capabilityDigest.hashCode()
        result = 31 * result + authorizationDigest.hashCode()
        result = 31 * result + singleUseNonce.hashCode()
        result = 31 * result + consumedBytes.hashCode()
        result = 31 * result + receiptDigest.hashCode()
        return 31 * result + committedRevision.hashCode()
    }
}

class ProductionC1CandidateUsageLedgerState(
    val revision: ULong = 1uL,
    val remainingOperations: ULong,
    val remainingBytes: ULong,
    val retentionLimit: UInt,
    entries: List<ProductionC1CandidateUsageEntry> = emptyList(),
) {
    private val entryValues = entries.toList()
    val entries: List<ProductionC1CandidateUsageEntry> get() = entryValues.toList()

    init {
        usageRequire(
            revision > 0uL &&
                retentionLimit > 0u &&
                entryValues.size.toULong() <= retentionLimit.toULong() &&
                entryValues.map { it.requestId }.toSet().size == entryValues.size &&
                entryValues.map { it.singleUseNonce }.toSet().size == entryValues.size &&
                entryValues.map { it.capabilityDigest }.toSet().size == entryValues.size &&
                entryValues.map { it.receiptDigest }.toSet().size == entryValues.size,
            ProductionC1CandidateCapabilityError.INVALID_VALUE,
        )
        var previousCommittedRevision = 0uL
        entryValues.forEach { entry ->
            listOf(
                entry.requestId,
                entry.requestDigest,
                entry.capabilityDigest,
                entry.authorizationDigest,
                entry.singleUseNonce,
                entry.receiptDigest,
            ).forEach(ProductionC1InternalBridge::validateDigest)
            usageRequire(
                entry.consumedBytes > 0uL &&
                    entry.committedRevision > previousCommittedRevision &&
                    entry.committedRevision <= revision,
                ProductionC1CandidateCapabilityError.INVALID_VALUE,
            )
            previousCommittedRevision = entry.committedRevision
        }
    }

    fun snapshotDigestHex(): String {
        var claims = ProductionC1InternalBridge.be(revision)
        claims += ProductionC1InternalBridge.be(remainingOperations)
        claims += ProductionC1InternalBridge.be(remainingBytes)
        claims += ProductionC1InternalBridge.be(retentionLimit)
        claims += ProductionC1InternalBridge.be(entryValues.size.toUInt())
        entryValues.forEach { entry ->
            listOf(
                entry.requestId,
                entry.requestDigest,
                entry.capabilityDigest,
                entry.authorizationDigest,
                entry.singleUseNonce,
                entry.receiptDigest,
            ).forEach { claims += ProductionC1InternalBridge.rawDigest(it) }
            claims += ProductionC1InternalBridge.be(entry.consumedBytes)
            claims += ProductionC1InternalBridge.be(entry.committedRevision)
        }
        return usageDomainDigest(
            "AetherLink G1a-C candidate usage ledger snapshot v1",
            claims,
        )
    }

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is ProductionC1CandidateUsageLedgerState &&
                revision == other.revision &&
                remainingOperations == other.remainingOperations &&
                remainingBytes == other.remainingBytes &&
                retentionLimit == other.retentionLimit &&
                entryValues == other.entryValues)

    override fun hashCode(): Int {
        var result = revision.hashCode()
        result = 31 * result + remainingOperations.hashCode()
        result = 31 * result + remainingBytes.hashCode()
        result = 31 * result + retentionLimit.hashCode()
        return 31 * result + entryValues.hashCode()
    }
}

class ProductionC1CandidateUsageReceipt internal constructor(
    val entry: ProductionC1CandidateUsageEntry,
    val previousRevision: ULong,
    val committedRevision: ULong,
) {
    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is ProductionC1CandidateUsageReceipt &&
                entry == other.entry &&
                previousRevision == other.previousRevision &&
                committedRevision == other.committedRevision)

    override fun hashCode(): Int {
        var result = entry.hashCode()
        result = 31 * result + previousRevision.hashCode()
        return 31 * result + committedRevision.hashCode()
    }
}

internal class ReadbackConfirmedProductionC1CandidateUsageReceipt private constructor(
    val receipt: ProductionC1CandidateUsageReceipt,
    val disposition: ProductionC1CandidateCASDisposition,
    val previousStateCoreDigest: String,
    val committedStateCoreDigest: String,
    val ledgerId: String,
    val commitRecordDigest: String,
) {
    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is ReadbackConfirmedProductionC1CandidateUsageReceipt &&
                receipt == other.receipt &&
                disposition == other.disposition &&
                previousStateCoreDigest == other.previousStateCoreDigest &&
                committedStateCoreDigest == other.committedStateCoreDigest &&
                ledgerId == other.ledgerId &&
                commitRecordDigest == other.commitRecordDigest)

    override fun hashCode(): Int {
        var result = receipt.hashCode()
        result = 31 * result + disposition.hashCode()
        result = 31 * result + previousStateCoreDigest.hashCode()
        result = 31 * result + committedStateCoreDigest.hashCode()
        result = 31 * result + ledgerId.hashCode()
        return 31 * result + commitRecordDigest.hashCode()
    }

    companion object {
        internal fun confirm(
            preparation: ProductionC1CandidateUsagePreparation,
            committedReadback: ProductionC1CandidateUsageLedgerState,
            ledgerId: String,
            commitRecordDigest: String,
        ): ReadbackConfirmedProductionC1CandidateUsageReceipt {
            ProductionC1InternalBridge.validateDigest(ledgerId)
            ProductionC1InternalBridge.validateDigest(commitRecordDigest)
            usageRequire(
                committedReadback == preparation.nextState &&
                    committedReadback.entries.contains(preparation.receipt.entry),
                ProductionC1CandidateCapabilityError.REVISION_MISMATCH,
            )
            if (preparation.disposition == ProductionC1CandidateCASDisposition.APPLIED) {
                usageRequire(
                    committedReadback.revision == preparation.receipt.committedRevision,
                    ProductionC1CandidateCapabilityError.REVISION_MISMATCH,
                )
            }
            return ReadbackConfirmedProductionC1CandidateUsageReceipt(
                preparation.receipt,
                preparation.disposition,
                preparation.expectedSnapshotDigest,
                committedReadback.snapshotDigestHex(),
                ledgerId,
                commitRecordDigest,
            )
        }
    }
}

class ProductionC1CandidateUsagePreparation internal constructor(
    val disposition: ProductionC1CandidateCASDisposition,
    val expectedRevision: ULong,
    val expectedSnapshotDigest: String,
    val nextState: ProductionC1CandidateUsageLedgerState,
    val receipt: ProductionC1CandidateUsageReceipt,
) {
    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is ProductionC1CandidateUsagePreparation &&
                disposition == other.disposition &&
                expectedRevision == other.expectedRevision &&
                expectedSnapshotDigest == other.expectedSnapshotDigest &&
                nextState == other.nextState &&
                receipt == other.receipt)

    override fun hashCode(): Int {
        var result = disposition.hashCode()
        result = 31 * result + expectedRevision.hashCode()
        result = 31 * result + expectedSnapshotDigest.hashCode()
        result = 31 * result + nextState.hashCode()
        return 31 * result + receipt.hashCode()
    }
}

object ProductionC1CandidateUsageLedger {
    fun requestDigest(
        requestId: String,
        capabilityDigest: String,
        authorizationDigest: String,
    ): String {
        var claims = ProductionC1InternalBridge.rawDigest(requestId)
        claims += ProductionC1InternalBridge.rawDigest(capabilityDigest)
        claims += ProductionC1InternalBridge.rawDigest(authorizationDigest)
        return usageDomainDigest(
            "AetherLink G1a-C candidate usage request v1",
            claims,
        )
    }

    /** Restores only an existing committed result; it cannot create a new effect. */
    fun prepareCommittedRetry(
        state: ProductionC1CandidateUsageLedgerState,
        requestId: String,
        requestDigest: String,
        capabilityCanonicalBytes: ByteArray,
        authorization: ProductionRouteAuthorization,
    ): ProductionC1CandidateUsagePreparation {
        val capabilityBytes = capabilityCanonicalBytes.copyOf()
        val capability = ProductionC1CandidateCapability.decode(capabilityBytes)
        usageRequire(
            capability.canonicalBytes().contentEquals(capabilityBytes),
            ProductionC1CandidateCapabilityError.MALFORMED_CANONICAL,
        )
        val capabilityDigest = ProductionC1InternalBridge.digestHex(capabilityBytes)
        val authorizationDigest = authorizationDigest(authorization)
        requireExactAuthorization(authorization, capability, capabilityDigest)
        val exactRequestDigest = requestDigest(requestId, capabilityDigest, authorizationDigest)
        val existing = state.entries.firstOrNull { it.requestId == requestId }
        usageRequire(
            requestDigest == exactRequestDigest &&
                existing != null &&
                existing.requestDigest == requestDigest &&
                existing.capabilityDigest == capabilityDigest &&
                existing.authorizationDigest == authorizationDigest,
            ProductionC1CandidateCapabilityError.REQUEST_CONFLICT,
        )
        val committedEntry = requireNotNull(existing)
        val receipt = ProductionC1CandidateUsageReceipt(
            committedEntry,
            committedEntry.committedRevision - 1uL,
            committedEntry.committedRevision,
        )
        return ProductionC1CandidateUsagePreparation(
            ProductionC1CandidateCASDisposition.IDEMPOTENT,
            state.revision,
            state.snapshotDigestHex(),
            state,
            receipt,
        )
    }

    internal fun prepareConsume(
        state: ProductionC1CandidateUsageLedgerState,
        expectedRevision: ULong,
        expectedSnapshotDigest: String,
        requestId: String,
        requestDigest: String,
        verifiedCapability: VerifiedProductionC1CandidateCapability,
        authorization: ProductionRouteAuthorization,
        authenticatedLocalRole: P2pNatRole,
        authenticatedLocalIdentityFingerprint: String,
        authority: ProductionPairAuthorityState,
        nowMs: ULong,
    ): ProductionC1CandidateUsagePreparation {
        val capability = verifiedCapability.capability
        val proof = verifiedCapability.endpointOperationProof
        usageRequire(
            requestId == proof.proofId &&
                authenticatedLocalRole == proof.requesterRole &&
                authenticatedLocalIdentityFingerprint == proof.requesterIdentityFingerprint,
            ProductionC1CandidateCapabilityError.ROLE_MISMATCH,
        )
        val authorizationDigest = authorizationDigest(authorization)
        requireExactAuthorization(authorization, verifiedCapability)
        val exactRequestDigest = requestDigest(
            requestId,
            verifiedCapability.capabilityDigest,
            authorizationDigest,
        )
        usageRequire(
            requestDigest == exactRequestDigest,
            ProductionC1CandidateCapabilityError.REQUEST_CONFLICT,
        )
        state.entries.firstOrNull { it.requestId == requestId }?.let { existing ->
            usageRequire(
                existing.requestDigest == requestDigest &&
                    existing.capabilityDigest == verifiedCapability.capabilityDigest &&
                    existing.authorizationDigest == authorizationDigest,
                ProductionC1CandidateCapabilityError.REQUEST_CONFLICT,
            )
            return ProductionC1CandidateUsagePreparation(
                ProductionC1CandidateCASDisposition.IDEMPOTENT,
                state.revision,
                state.snapshotDigestHex(),
                state,
                ProductionC1CandidateUsageReceipt(
                    existing,
                    existing.committedRevision - 1uL,
                    existing.committedRevision,
                ),
            )
        }
        ProductionC1CandidateVerifier.validateUse(verifiedCapability, authority, nowMs)
        usageRequire(
            state.revision == expectedRevision &&
                state.snapshotDigestHex() == expectedSnapshotDigest,
            ProductionC1CandidateCapabilityError.REVISION_MISMATCH,
        )
        usageRequire(
            state.entries.size.toULong() < state.retentionLimit.toULong(),
            ProductionC1CandidateCapabilityError.RETENTION_EXHAUSTED,
        )
        usageRequire(
            state.entries.none {
                it.singleUseNonce == capability.singleUseNonce ||
                    it.capabilityDigest == verifiedCapability.capabilityDigest
            },
            ProductionC1CandidateCapabilityError.REPLAY,
        )
        val bytes = capability.candidateBatchByteCount.toULong()
        usageRequire(
            state.remainingOperations >= capability.maxOperations.toULong() &&
                state.remainingBytes >= bytes &&
                state.revision < ULong.MAX_VALUE,
            ProductionC1CandidateCapabilityError.QUOTA_EXCEEDED,
        )
        val committedRevision = state.revision + 1uL
        val receiptDigest = usageCommitResultDigest(
            requestId,
            requestDigest,
            verifiedCapability.capabilityDigest,
            authorizationDigest,
            capability.singleUseNonce,
            bytes,
            state.revision,
            committedRevision,
        )
        val entry = ProductionC1CandidateUsageEntry(
            requestId,
            requestDigest,
            verifiedCapability.capabilityDigest,
            authorizationDigest,
            capability.singleUseNonce,
            bytes,
            receiptDigest,
            committedRevision,
        )
        val next = ProductionC1CandidateUsageLedgerState(
            committedRevision,
            state.remainingOperations - capability.maxOperations.toULong(),
            state.remainingBytes - bytes,
            state.retentionLimit,
            state.entries + entry,
        )
        return ProductionC1CandidateUsagePreparation(
            ProductionC1CandidateCASDisposition.APPLIED,
            state.revision,
            expectedSnapshotDigest,
            next,
            ProductionC1CandidateUsageReceipt(entry, state.revision, committedRevision),
        )
    }

    internal fun requireExactAuthorization(
        authorization: ProductionRouteAuthorization,
        verifiedCapability: VerifiedProductionC1CandidateCapability,
    ) = requireExactAuthorization(
        authorization,
        verifiedCapability.capability,
        verifiedCapability.capabilityDigest,
    )

    internal fun requireExactAuthorization(
        authorization: ProductionRouteAuthorization,
        capability: ProductionC1CandidateCapability,
        capabilityDigest: String,
    ) {
        val matches = when {
            capability.operation == ProductionC1CandidateOperation.PUBLISH &&
                authorization is P2pPublishRouteAuthorization ->
                authorization.pairBindingDigest == capability.pairBindingDigest &&
                    authorization.pairEpoch == capability.pairEpoch &&
                    authorization.generation == capability.generation &&
                    authorization.candidateBatchDigest == capability.candidateBatchDigest &&
                    authorization.publishCapabilityDigest == capabilityDigest

            capability.operation == ProductionC1CandidateOperation.FETCH &&
                authorization is P2pFetchRouteAuthorization ->
                authorization.pairBindingDigest == capability.pairBindingDigest &&
                    authorization.pairEpoch == capability.pairEpoch &&
                    authorization.generation == capability.generation &&
                    authorization.candidateBatchDigest == capability.candidateBatchDigest &&
                    authorization.fetchCapabilityDigest == capabilityDigest

            else -> false
        }
        usageRequire(matches, ProductionC1CandidateCapabilityError.ROUTE_MISMATCH)
    }
}

object ProductionC1CandidateOperationReceiptContract {
    const val OBJECT_TYPE: Int = 28
    const val REVISION: ULong = 1uL
    const val MAXIMUM_BYTES: Int = 4_096
    const val MAXIMUM_LIFETIME_MS: ULong = ProductionC1Contract.MAXIMUM_ROUTE_LIFETIME_MS
}

enum class ProductionC1CandidateOperationReceiptStatus(val wireValue: String) {
    COMMITTED("committed");

    companion object {
        internal fun decode(value: String): ProductionC1CandidateOperationReceiptStatus =
            entries.singleOrNull { it.wireValue == value }
                ?: usageFail(ProductionC1CandidateCapabilityError.INVALID_VALUE)
    }
}

/**
 * Authenticates already-committed core claims. It does not itself prove store I/O or fsync;
 * commitRecordDigest identifies a pre-existing record that excludes object-28 bytes/signature.
 */
class ProductionC1CandidateOperationReceipt private constructor(
    val status: ProductionC1CandidateOperationReceiptStatus,
    val serviceIdDigest: String,
    val keysetVersion: ULong,
    val signingKeyId: String,
    val pairAuthorityDigest: String,
    val pairBindingDigest: String,
    val pairEpoch: ULong,
    val generation: ULong,
    val serviceConfigVersion: ULong,
    val revocationCounter: ULong,
    val protocolFloor: UInt,
    val clientIdentityFingerprint: String,
    val runtimeIdentityFingerprint: String,
    val sessionId: String,
    val attemptId: String,
    val ledgerId: String,
    val initiatorRole: P2pNatRole,
    val operation: ProductionC1CandidateOperation,
    val requesterRole: P2pNatRole,
    val candidateOwnerRole: P2pNatRole,
    val capabilityId: String,
    val capabilityDigest: String,
    val endpointOperationProofDigest: String,
    val proofId: String,
    val operationAuthorizationKind: ProductionRouteAuthorizationKind,
    val operationAuthorizationDigest: String,
    val requestDigest: String,
    val singleUseNonce: String,
    val candidateBatchDigest: String,
    val candidateBatchByteCount: UInt,
    val candidateBatchSequence: ULong,
    val candidateBatchExpiresAtMs: ULong,
    val consumedOperations: UInt,
    val consumedBytes: ULong,
    val resultDigest: String,
    val previousLedgerRevision: ULong,
    val committedLedgerRevision: ULong,
    val previousLedgerStateCoreDigest: String,
    val committedLedgerStateCoreDigest: String,
    val commitRecordDigest: String,
    val committedAtMs: ULong,
    val issuedAtMs: ULong,
    val notBeforeMs: ULong,
    val expiresAtMs: ULong,
    serviceSignature: ByteArray,
    validateSignature: Boolean,
) {
    private val serviceSignatureBytes = serviceSignature.copyOf()
    val serviceSignature: ByteArray get() = serviceSignatureBytes.copyOf()

    init {
        listOf(
            serviceIdDigest,
            signingKeyId,
            pairAuthorityDigest,
            pairBindingDigest,
            clientIdentityFingerprint,
            runtimeIdentityFingerprint,
            ledgerId,
            capabilityId,
            capabilityDigest,
            endpointOperationProofDigest,
            proofId,
            operationAuthorizationDigest,
            requestDigest,
            singleUseNonce,
            candidateBatchDigest,
            resultDigest,
            previousLedgerStateCoreDigest,
            committedLedgerStateCoreDigest,
            commitRecordDigest,
        ).forEach(ProductionC1InternalBridge::validateDigest)
        usageRequire(
            keysetVersion > 0uL &&
                pairEpoch > 0uL &&
                generation > 0uL &&
                serviceConfigVersion > 0uL &&
                protocolFloor > 0u &&
                clientIdentityFingerprint != runtimeIdentityFingerprint &&
                receiptIsLowerHex(sessionId, 32) &&
                receiptIsLowerHex(attemptId, 64) &&
                initiatorRole == P2pNatRole.CLIENT &&
                candidateBatchByteCount > 0u &&
                candidateBatchSequence > 0uL &&
                consumedOperations == 1u &&
                consumedBytes == candidateBatchByteCount.toULong() &&
                previousLedgerRevision > 0uL &&
                previousLedgerRevision < ULong.MAX_VALUE &&
                committedLedgerRevision == previousLedgerRevision + 1uL &&
                committedAtMs <= issuedAtMs &&
                issuedAtMs <= notBeforeMs &&
                notBeforeMs < expiresAtMs &&
                expiresAtMs - issuedAtMs <=
                ProductionC1CandidateOperationReceiptContract.MAXIMUM_LIFETIME_MS,
            ProductionC1CandidateCapabilityError.INVALID_VALUE,
        )
        when (operation) {
            ProductionC1CandidateOperation.PUBLISH -> usageRequire(
                requesterRole == candidateOwnerRole &&
                    operationAuthorizationKind == ProductionRouteAuthorizationKind.P2P_PUBLISH,
                ProductionC1CandidateCapabilityError.ROLE_MISMATCH,
            )
            ProductionC1CandidateOperation.FETCH -> usageRequire(
                requesterRole != candidateOwnerRole &&
                    operationAuthorizationKind == ProductionRouteAuthorizationKind.P2P_FETCH,
                ProductionC1CandidateCapabilityError.ROLE_MISMATCH,
            )
        }
        val expectedRequest = ProductionC1CandidateUsageLedger.requestDigest(
            proofId,
            capabilityDigest,
            operationAuthorizationDigest,
        )
        val expectedResult = usageCommitResultDigest(
            proofId,
            requestDigest,
            capabilityDigest,
            operationAuthorizationDigest,
            singleUseNonce,
            consumedBytes,
            previousLedgerRevision,
            committedLedgerRevision,
        )
        usageRequire(
            requestDigest == expectedRequest && resultDigest == expectedResult,
            ProductionC1CandidateCapabilityError.REQUEST_CONFLICT,
        )
        if (validateSignature) ProductionC1InternalBridge.validateSignature(serviceSignatureBytes)
        usageRequire(
            canonicalBytes().size <= ProductionC1CandidateOperationReceiptContract.MAXIMUM_BYTES,
            ProductionC1CandidateCapabilityError.INVALID_VALUE,
        )
    }

    fun canonicalBytes(): ByteArray = ProductionC1InternalBridge.encode(
        ProductionC1CandidateOperationReceiptContract.OBJECT_TYPE,
        claimsFields() + serviceSignatureBytes,
    )

    fun digestHex(): String = ProductionC1InternalBridge.digestHex(canonicalBytes())

    internal fun signingTranscript(): ByteArray = ProductionC1InternalBridge.transcript(
        if (operation == ProductionC1CandidateOperation.PUBLISH) {
            "AetherLink G1a-C candidate-publish operation receipt service signature v1"
        } else {
            "AetherLink G1a-C candidate-fetch operation receipt service signature v1"
        },
        ProductionC1InternalBridge.encode(
            ProductionC1CandidateOperationReceiptContract.OBJECT_TYPE,
            claimsFields(),
        ),
    )

    internal val requiredPurpose: ProductionC1DelegatedKeyPurpose
        get() = receiptPurpose(operation)

    private fun claimsFields(): List<ByteArray> = listOf(
        ProductionC1InternalBridge.ascii(ProductionC1Contract.SUITE),
        ProductionC1InternalBridge.be(ProductionC1CandidateOperationReceiptContract.REVISION),
        ProductionC1InternalBridge.ascii(status.wireValue),
        ProductionC1InternalBridge.ascii(serviceIdDigest),
        ProductionC1InternalBridge.be(keysetVersion),
        ProductionC1InternalBridge.ascii(signingKeyId),
        ProductionC1InternalBridge.ascii(pairAuthorityDigest),
        ProductionC1InternalBridge.ascii(pairBindingDigest),
        ProductionC1InternalBridge.be(pairEpoch),
        ProductionC1InternalBridge.be(generation),
        ProductionC1InternalBridge.be(serviceConfigVersion),
        ProductionC1InternalBridge.be(revocationCounter),
        ProductionC1InternalBridge.be(protocolFloor),
        ProductionC1InternalBridge.ascii(clientIdentityFingerprint),
        ProductionC1InternalBridge.ascii(runtimeIdentityFingerprint),
        ProductionC1InternalBridge.ascii(sessionId),
        ProductionC1InternalBridge.ascii(attemptId),
        ProductionC1InternalBridge.ascii(ledgerId),
        ProductionC1InternalBridge.ascii(initiatorRole.wireValue),
        ProductionC1InternalBridge.ascii(operation.wireValue),
        ProductionC1InternalBridge.ascii(requesterRole.wireValue),
        ProductionC1InternalBridge.ascii(candidateOwnerRole.wireValue),
        ProductionC1InternalBridge.ascii(capabilityId),
        ProductionC1InternalBridge.ascii(capabilityDigest),
        ProductionC1InternalBridge.ascii(endpointOperationProofDigest),
        ProductionC1InternalBridge.ascii(proofId),
        ProductionC1InternalBridge.ascii(operationAuthorizationKind.wireValue),
        ProductionC1InternalBridge.ascii(operationAuthorizationDigest),
        ProductionC1InternalBridge.ascii(requestDigest),
        ProductionC1InternalBridge.ascii(singleUseNonce),
        ProductionC1InternalBridge.ascii(candidateBatchDigest),
        ProductionC1InternalBridge.be(candidateBatchByteCount),
        ProductionC1InternalBridge.be(candidateBatchSequence),
        ProductionC1InternalBridge.be(candidateBatchExpiresAtMs),
        ProductionC1InternalBridge.be(consumedOperations),
        ProductionC1InternalBridge.be(consumedBytes),
        ProductionC1InternalBridge.ascii(resultDigest),
        ProductionC1InternalBridge.be(previousLedgerRevision),
        ProductionC1InternalBridge.be(committedLedgerRevision),
        ProductionC1InternalBridge.ascii(previousLedgerStateCoreDigest),
        ProductionC1InternalBridge.ascii(committedLedgerStateCoreDigest),
        ProductionC1InternalBridge.ascii(commitRecordDigest),
        ProductionC1InternalBridge.be(committedAtMs),
        ProductionC1InternalBridge.be(issuedAtMs),
        ProductionC1InternalBridge.be(notBeforeMs),
        ProductionC1InternalBridge.be(expiresAtMs),
        ProductionC1InternalBridge.ascii(ProductionC1Contract.SIGNATURE_ALGORITHM),
    )

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is ProductionC1CandidateOperationReceipt &&
                canonicalBytes().contentEquals(other.canonicalBytes()))

    override fun hashCode(): Int = canonicalBytes().contentHashCode()

    companion object {
        /** Readiness-only signer; a stateful coordinator must persist and replay the one receipt. */
        internal fun signedAfterAppliedCommit(
            verifiedCapability: VerifiedProductionC1CandidateCapability,
            authorization: ProductionRouteAuthorization,
            confirmedUsageReceipt: ReadbackConfirmedProductionC1CandidateUsageReceipt,
            previousLedgerState: ProductionC1CandidateUsageLedgerState,
            committedLedgerState: ProductionC1CandidateUsageLedgerState,
            committedAtMs: ULong,
            issuedAtMs: ULong,
            notBeforeMs: ULong,
            expiresAtMs: ULong,
            authority: ProductionPairAuthorityState,
            verifiedKeyset: VerifiedProductionC1ServiceKeyset,
            signingPublicKey: PublicKey,
            signingPrivateKey: PrivateKey,
        ): ProductionC1CandidateOperationReceipt {
            usageRequire(
                confirmedUsageReceipt.disposition == ProductionC1CandidateCASDisposition.APPLIED,
                ProductionC1CandidateCapabilityError.REPLAY,
            )
            ProductionC1CandidateVerifier.validateUse(verifiedCapability, authority, committedAtMs)
            ProductionC1CandidateUsageLedger.requireExactAuthorization(
                authorization,
                verifiedCapability,
            )
            val capability = verifiedCapability.capability
            val proof = verifiedCapability.endpointOperationProof
            val usage = confirmedUsageReceipt.receipt
            val entry = usage.entry
            val authorizationDigest = authorizationDigest(authorization)
            val expectedRequestDigest = ProductionC1CandidateUsageLedger.requestDigest(
                proof.proofId,
                verifiedCapability.capabilityDigest,
                authorizationDigest,
            )
            usageRequire(
                entry.requestId == proof.proofId &&
                    entry.requestDigest == expectedRequestDigest &&
                    entry.capabilityDigest == verifiedCapability.capabilityDigest &&
                    entry.authorizationDigest == authorizationDigest &&
                    entry.singleUseNonce == capability.singleUseNonce &&
                    entry.consumedBytes == capability.candidateBatchByteCount.toULong() &&
                    usage.previousRevision == previousLedgerState.revision &&
                    usage.committedRevision == committedLedgerState.revision &&
                    entry.committedRevision == committedLedgerState.revision &&
                    previousLedgerState.revision < ULong.MAX_VALUE &&
                    committedLedgerState.revision == previousLedgerState.revision + 1uL &&
                    previousLedgerState.remainingOperations >= 1uL &&
                    previousLedgerState.remainingOperations - 1uL ==
                    committedLedgerState.remainingOperations &&
                    previousLedgerState.remainingBytes >= entry.consumedBytes &&
                    previousLedgerState.remainingBytes - entry.consumedBytes ==
                    committedLedgerState.remainingBytes &&
                    previousLedgerState.retentionLimit == committedLedgerState.retentionLimit &&
                    committedLedgerState.entries == previousLedgerState.entries + entry &&
                    previousLedgerState.snapshotDigestHex() ==
                    confirmedUsageReceipt.previousStateCoreDigest &&
                    committedLedgerState.snapshotDigestHex() ==
                    confirmedUsageReceipt.committedStateCoreDigest &&
                    committedAtMs >= capability.notBeforeMs &&
                    committedAtMs >= proof.notBeforeMs &&
                    issuedAtMs >= capability.issuedAtMs &&
                    notBeforeMs >= capability.notBeforeMs &&
                    notBeforeMs >= proof.notBeforeMs &&
                    expiresAtMs <= capability.expiresAtMs &&
                    expiresAtMs <= proof.expiresAtMs &&
                    authority.status == ProductionPairAuthorityStatus.ACTIVE &&
                    capability.pairAuthorityDigest == authority.digestHex() &&
                    capability.serviceIdDigest == verifiedKeyset.keyset.serviceIdDigest &&
                    capability.keysetVersion == verifiedKeyset.keyset.keysetVersion &&
                    capability.keysetVersion == authority.keysetVersion,
                ProductionC1CandidateCapabilityError.REVISION_MISMATCH,
            )
            val purpose = receiptPurpose(capability.operation)
            val signingKeyId = ProductionC1InternalBridge.keyId(signingPublicKey)
            val delegatedAtIssue = ProductionC1InternalBridge.delegatedSigningKey(
                signingKeyId,
                purpose,
                verifiedKeyset,
                issuedAtMs,
            )
            usageRequire(
                expiresAtMs > 0uL,
                ProductionC1CandidateCapabilityError.INVALID_VALUE,
            )
            val delegatedAtExpiry = ProductionC1InternalBridge.delegatedSigningKey(
                signingKeyId,
                purpose,
                verifiedKeyset,
                expiresAtMs - 1uL,
            )
            usageRequire(
                delegatedAtIssue.encoded.contentEquals(signingPublicKey.encoded) &&
                    delegatedAtExpiry.encoded.contentEquals(signingPublicKey.encoded),
                ProductionC1CandidateCapabilityError.AUTHORITY_MISMATCH,
            )
            val resultDigest = usageCommitResultDigest(
                proof.proofId,
                entry.requestDigest,
                verifiedCapability.capabilityDigest,
                authorizationDigest,
                capability.singleUseNonce,
                entry.consumedBytes,
                usage.previousRevision,
                usage.committedRevision,
            )
            usageRequire(
                resultDigest == entry.receiptDigest,
                ProductionC1CandidateCapabilityError.REQUEST_CONFLICT,
            )
            val unsigned = ProductionC1CandidateOperationReceipt(
                ProductionC1CandidateOperationReceiptStatus.COMMITTED,
                capability.serviceIdDigest,
                capability.keysetVersion,
                signingKeyId,
                capability.pairAuthorityDigest,
                capability.pairBindingDigest,
                capability.pairEpoch,
                capability.generation,
                capability.serviceConfigVersion,
                capability.revocationCounter,
                capability.protocolFloor,
                capability.clientIdentityFingerprint,
                capability.runtimeIdentityFingerprint,
                capability.sessionId,
                capability.attemptId,
                confirmedUsageReceipt.ledgerId,
                proof.initiatorRole,
                capability.operation,
                capability.requesterRole,
                capability.candidateOwnerRole,
                capability.capabilityId,
                verifiedCapability.capabilityDigest,
                capability.endpointOperationProofDigest,
                proof.proofId,
                authorization.kind,
                authorizationDigest,
                entry.requestDigest,
                capability.singleUseNonce,
                capability.candidateBatchDigest,
                capability.candidateBatchByteCount,
                capability.candidateBatchSequence,
                capability.candidateBatchExpiresAtMs,
                capability.maxOperations,
                entry.consumedBytes,
                resultDigest,
                usage.previousRevision,
                usage.committedRevision,
                previousLedgerState.snapshotDigestHex(),
                committedLedgerState.snapshotDigestHex(),
                confirmedUsageReceipt.commitRecordDigest,
                committedAtMs,
                issuedAtMs,
                notBeforeMs,
                expiresAtMs,
                byteArrayOf(),
                false,
            )
            val receipt = unsigned.replacingSignature(
                ProductionC1InternalBridge.sign(unsigned.signingTranscript(), signingPrivateKey),
            )
            // JVM callers supply separate key handles; reject an invalid pair before returning bytes.
            ProductionC1InternalBridge.verify(
                receipt.serviceSignatureBytes,
                receipt.signingTranscript(),
                signingPublicKey,
            )
            return receipt
        }

        fun decode(data: ByteArray): ProductionC1CandidateOperationReceipt {
            val fields = ProductionC1InternalBridge.decode(
                data,
                ProductionC1CandidateOperationReceiptContract.OBJECT_TYPE,
                48,
                ProductionC1CandidateOperationReceiptContract.MAXIMUM_BYTES,
            )
            usageRequire(
                ProductionC1InternalBridge.text(fields[0]) == ProductionC1Contract.SUITE &&
                    ProductionC1InternalBridge.uint64(fields[1]) ==
                    ProductionC1CandidateOperationReceiptContract.REVISION,
                ProductionC1CandidateCapabilityError.INVALID_VALUE,
            )
            val status = ProductionC1CandidateOperationReceiptStatus.decode(
                ProductionC1InternalBridge.text(fields[2]),
            )
            val initiatorRole = receiptRole(ProductionC1InternalBridge.text(fields[18]))
            val operation = ProductionC1CandidateOperation.decode(
                ProductionC1InternalBridge.text(fields[19]),
            )
            val requesterRole = receiptRole(ProductionC1InternalBridge.text(fields[20]))
            val candidateOwnerRole = receiptRole(ProductionC1InternalBridge.text(fields[21]))
            val authorizationKind = receiptAuthorizationKind(
                ProductionC1InternalBridge.text(fields[26]),
            )
            usageRequire(
                ProductionC1InternalBridge.text(fields[46]) ==
                    ProductionC1Contract.SIGNATURE_ALGORITHM,
                ProductionC1CandidateCapabilityError.INVALID_VALUE,
            )
            val receipt = ProductionC1CandidateOperationReceipt(
                status,
                ProductionC1InternalBridge.text(fields[3]),
                ProductionC1InternalBridge.uint64(fields[4]),
                ProductionC1InternalBridge.text(fields[5]),
                ProductionC1InternalBridge.text(fields[6]),
                ProductionC1InternalBridge.text(fields[7]),
                ProductionC1InternalBridge.uint64(fields[8]),
                ProductionC1InternalBridge.uint64(fields[9]),
                ProductionC1InternalBridge.uint64(fields[10]),
                ProductionC1InternalBridge.uint64(fields[11]),
                ProductionC1InternalBridge.uint32(fields[12]),
                ProductionC1InternalBridge.text(fields[13]),
                ProductionC1InternalBridge.text(fields[14]),
                ProductionC1InternalBridge.text(fields[15]),
                ProductionC1InternalBridge.text(fields[16]),
                ProductionC1InternalBridge.text(fields[17]),
                initiatorRole,
                operation,
                requesterRole,
                candidateOwnerRole,
                ProductionC1InternalBridge.text(fields[22]),
                ProductionC1InternalBridge.text(fields[23]),
                ProductionC1InternalBridge.text(fields[24]),
                ProductionC1InternalBridge.text(fields[25]),
                authorizationKind,
                ProductionC1InternalBridge.text(fields[27]),
                ProductionC1InternalBridge.text(fields[28]),
                ProductionC1InternalBridge.text(fields[29]),
                ProductionC1InternalBridge.text(fields[30]),
                ProductionC1InternalBridge.uint32(fields[31]),
                ProductionC1InternalBridge.uint64(fields[32]),
                ProductionC1InternalBridge.uint64(fields[33]),
                ProductionC1InternalBridge.uint32(fields[34]),
                ProductionC1InternalBridge.uint64(fields[35]),
                ProductionC1InternalBridge.text(fields[36]),
                ProductionC1InternalBridge.uint64(fields[37]),
                ProductionC1InternalBridge.uint64(fields[38]),
                ProductionC1InternalBridge.text(fields[39]),
                ProductionC1InternalBridge.text(fields[40]),
                ProductionC1InternalBridge.text(fields[41]),
                ProductionC1InternalBridge.uint64(fields[42]),
                ProductionC1InternalBridge.uint64(fields[43]),
                ProductionC1InternalBridge.uint64(fields[44]),
                ProductionC1InternalBridge.uint64(fields[45]),
                fields[47],
                true,
            )
            usageRequire(
                receipt.canonicalBytes().contentEquals(data),
                ProductionC1CandidateCapabilityError.MALFORMED_CANONICAL,
            )
            return receipt
        }

        private fun receiptPurpose(
            operation: ProductionC1CandidateOperation,
        ): ProductionC1DelegatedKeyPurpose =
            if (operation == ProductionC1CandidateOperation.PUBLISH) {
                ProductionC1DelegatedKeyPurpose.CANDIDATE_PUBLISH_RECEIPT
            } else {
                ProductionC1DelegatedKeyPurpose.CANDIDATE_FETCH_RECEIPT
            }
    }

    private fun replacingSignature(signature: ByteArray): ProductionC1CandidateOperationReceipt =
        ProductionC1CandidateOperationReceipt(
            status,
            serviceIdDigest,
            keysetVersion,
            signingKeyId,
            pairAuthorityDigest,
            pairBindingDigest,
            pairEpoch,
            generation,
            serviceConfigVersion,
            revocationCounter,
            protocolFloor,
            clientIdentityFingerprint,
            runtimeIdentityFingerprint,
            sessionId,
            attemptId,
            ledgerId,
            initiatorRole,
            operation,
            requesterRole,
            candidateOwnerRole,
            capabilityId,
            capabilityDigest,
            endpointOperationProofDigest,
            proofId,
            operationAuthorizationKind,
            operationAuthorizationDigest,
            requestDigest,
            singleUseNonce,
            candidateBatchDigest,
            candidateBatchByteCount,
            candidateBatchSequence,
            candidateBatchExpiresAtMs,
            consumedOperations,
            consumedBytes,
            resultDigest,
            previousLedgerRevision,
            committedLedgerRevision,
            previousLedgerStateCoreDigest,
            committedLedgerStateCoreDigest,
            commitRecordDigest,
            committedAtMs,
            issuedAtMs,
            notBeforeMs,
            expiresAtMs,
            signature,
            true,
        )
}

class VerifiedProductionC1CandidateOperationReceipt private constructor(
    val receipt: ProductionC1CandidateOperationReceipt,
) {
    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is VerifiedProductionC1CandidateOperationReceipt && receipt == other.receipt)

    override fun hashCode(): Int = receipt.hashCode()

    companion object {
        internal fun verify(
            receipt: ProductionC1CandidateOperationReceipt,
            verifiedCapability: VerifiedProductionC1CandidateCapability,
            authorization: ProductionRouteAuthorization,
            authority: ProductionPairAuthorityState,
            verifiedKeyset: VerifiedProductionC1ServiceKeyset,
            nowMs: ULong,
        ): VerifiedProductionC1CandidateOperationReceipt {
            ProductionC1CandidateVerifier.validateUse(verifiedCapability, authority, nowMs)
            ProductionC1CandidateUsageLedger.requireExactAuthorization(
                authorization,
                verifiedCapability,
            )
            val capability = verifiedCapability.capability
            val proof = verifiedCapability.endpointOperationProof
            val authorizationDigest = authorizationDigest(authorization)
            usageRequire(
                receipt.status == ProductionC1CandidateOperationReceiptStatus.COMMITTED &&
                    receipt.serviceIdDigest == capability.serviceIdDigest &&
                    receipt.keysetVersion == capability.keysetVersion &&
                    receipt.serviceIdDigest == verifiedKeyset.keyset.serviceIdDigest &&
                    (verifiedKeyset.keyset.keysetVersion == receipt.keysetVersion ||
                        (receipt.keysetVersion < ULong.MAX_VALUE &&
                            verifiedKeyset.keyset.keysetVersion == receipt.keysetVersion + 1uL)) &&
                    receipt.pairAuthorityDigest == authority.digestHex() &&
                    receipt.pairBindingDigest == authority.pairBindingDigest &&
                    receipt.pairEpoch == authority.pairEpoch &&
                    receipt.generation == authority.generation &&
                    receipt.serviceConfigVersion == authority.serviceConfigVersion &&
                    receipt.revocationCounter == authority.revocationCounter &&
                    receipt.protocolFloor == authority.protocolFloor &&
                    receipt.clientIdentityFingerprint == authority.clientIdentityFingerprint &&
                    receipt.runtimeIdentityFingerprint == authority.runtimeIdentityFingerprint &&
                    receipt.sessionId == capability.sessionId &&
                    receipt.attemptId == capability.attemptId &&
                    receipt.initiatorRole == proof.initiatorRole &&
                    receipt.operation == capability.operation &&
                    receipt.requesterRole == capability.requesterRole &&
                    receipt.candidateOwnerRole == capability.candidateOwnerRole &&
                    receipt.capabilityId == capability.capabilityId &&
                    receipt.capabilityDigest == verifiedCapability.capabilityDigest &&
                    receipt.endpointOperationProofDigest == capability.endpointOperationProofDigest &&
                    receipt.endpointOperationProofDigest == proof.digestHex() &&
                    receipt.proofId == proof.proofId &&
                    receipt.operationAuthorizationKind == authorization.kind &&
                    receipt.operationAuthorizationDigest == authorizationDigest &&
                    receipt.singleUseNonce == capability.singleUseNonce &&
                    receipt.candidateBatchDigest == capability.candidateBatchDigest &&
                    receipt.candidateBatchByteCount == capability.candidateBatchByteCount &&
                    receipt.candidateBatchSequence == capability.candidateBatchSequence &&
                    receipt.candidateBatchExpiresAtMs == capability.candidateBatchExpiresAtMs &&
                    receipt.consumedOperations == capability.maxOperations &&
                    receipt.consumedBytes == capability.candidateBatchByteCount.toULong() &&
                    receipt.committedAtMs >= capability.notBeforeMs &&
                    receipt.committedAtMs >= proof.notBeforeMs &&
                    receipt.issuedAtMs >= capability.issuedAtMs &&
                    receipt.notBeforeMs >= capability.notBeforeMs &&
                    receipt.notBeforeMs >= proof.notBeforeMs &&
                    receipt.expiresAtMs <= capability.expiresAtMs &&
                    receipt.expiresAtMs <= proof.expiresAtMs,
                ProductionC1CandidateCapabilityError.AUTHORITY_MISMATCH,
            )
            ProductionC1InternalBridge.validateWindow(
                receipt.issuedAtMs,
                receipt.notBeforeMs,
                receipt.expiresAtMs,
                ProductionC1CandidateOperationReceiptContract.MAXIMUM_LIFETIME_MS,
                nowMs,
            )
            val delegated = verifiedKeyset.keyset.delegatedKeys.firstOrNull {
                it.keyId == receipt.signingKeyId
            }
            if (delegated == null || delegated.keysetVersion != receipt.keysetVersion) {
                throw ProductionC1Exception(ProductionC1Error.KEY_UNAVAILABLE)
            }
            if (!delegated.purposes.contains(receipt.requiredPurpose)) {
                throw ProductionC1Exception(ProductionC1Error.KEY_PURPOSE_MISMATCH)
            }
            if (delegated.notBeforeMs > receipt.issuedAtMs ||
                delegated.notBeforeMs > receipt.notBeforeMs
            ) {
                throw ProductionC1Exception(ProductionC1Error.NOT_YET_VALID)
            }
            if (receipt.expiresAtMs > delegated.expiresAtMs) {
                throw ProductionC1Exception(ProductionC1Error.EXPIRED)
            }
            if (delegated.revokedAtMs?.let { receipt.expiresAtMs > it } == true) {
                throw ProductionC1Exception(ProductionC1Error.KEY_REVOKED)
            }
            val publicKey = ProductionC1InternalBridge.delegatedSigningKey(
                receipt.signingKeyId,
                receipt.requiredPurpose,
                verifiedKeyset,
                nowMs,
            )
            ProductionC1InternalBridge.verify(
                receipt.serviceSignature,
                receipt.signingTranscript(),
                publicKey,
            )
            return VerifiedProductionC1CandidateOperationReceipt(receipt)
        }
    }
}

object ProductionC1CandidateOperationReceiptVerifier {
    fun verify(
        receipt: ProductionC1CandidateOperationReceipt,
        verifiedCapability: VerifiedProductionC1CandidateCapability,
        authorization: ProductionRouteAuthorization,
        authority: ProductionPairAuthorityState,
        verifiedKeyset: VerifiedProductionC1ServiceKeyset,
        nowMs: ULong,
    ): VerifiedProductionC1CandidateOperationReceipt =
        VerifiedProductionC1CandidateOperationReceipt.verify(
            receipt,
            verifiedCapability,
            authorization,
            authority,
            verifiedKeyset,
            nowMs,
        )
}

private fun authorizationDigest(authorization: ProductionRouteAuthorization): String =
    ProductionC1InternalBridge.digestHex(ProductionSecureSessionCodec.encode(authorization))

private fun usageCommitResultDigest(
    proofId: String,
    requestDigest: String,
    capabilityDigest: String,
    operationAuthorizationDigest: String,
    singleUseNonce: String,
    consumedBytes: ULong,
    previousLedgerRevision: ULong,
    committedLedgerRevision: ULong,
): String {
    var claims = ProductionC1InternalBridge.rawDigest(proofId)
    claims += ProductionC1InternalBridge.rawDigest(requestDigest)
    claims += ProductionC1InternalBridge.rawDigest(capabilityDigest)
    claims += ProductionC1InternalBridge.rawDigest(operationAuthorizationDigest)
    claims += ProductionC1InternalBridge.rawDigest(singleUseNonce)
    claims += ProductionC1InternalBridge.be(consumedBytes)
    claims += ProductionC1InternalBridge.be(previousLedgerRevision)
    claims += ProductionC1InternalBridge.be(committedLedgerRevision)
    return usageDomainDigest(
        "AetherLink G1a-C readback-confirmed candidate usage receipt v1",
        claims,
    )
}

private fun usageDomainDigest(domain: String, claims: ByteArray): String =
    ProductionC1InternalBridge.digestHex(ProductionC1InternalBridge.transcript(domain, claims))

private fun receiptRole(value: String): P2pNatRole =
    P2pNatRole.entries.singleOrNull { it.wireValue == value }
        ?: usageFail(ProductionC1CandidateCapabilityError.INVALID_VALUE)

private fun receiptAuthorizationKind(value: String): ProductionRouteAuthorizationKind =
    ProductionRouteAuthorizationKind.entries.singleOrNull { it.wireValue == value }
        ?: usageFail(ProductionC1CandidateCapabilityError.INVALID_VALUE)

private fun receiptIsLowerHex(value: String, count: Int): Boolean =
    value.length == count && value.all { it in '0'..'9' || it in 'a'..'f' }

private fun usageRequire(
    condition: Boolean,
    error: ProductionC1CandidateCapabilityError,
) {
    if (!condition) throw ProductionC1CandidateCapabilityException(error)
}

private fun usageFail(error: ProductionC1CandidateCapabilityError): Nothing =
    throw ProductionC1CandidateCapabilityException(error)
