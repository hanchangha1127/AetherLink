package com.localagentbridge.android.core.protocol.p2pnat

import java.math.BigInteger
import java.nio.ByteBuffer
import java.security.AlgorithmParameters
import java.security.KeyFactory
import java.security.MessageDigest
import java.security.PrivateKey
import java.security.PublicKey
import java.security.interfaces.ECPublicKey
import java.security.spec.ECFieldFp
import java.security.spec.ECGenParameterSpec
import java.security.spec.ECParameterSpec
import java.security.spec.ECPoint
import java.security.spec.ECPrivateKeySpec
import java.security.spec.ECPublicKeySpec
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

class ProductionG1aCCandidateOperationReceiptsTest {
    private val now = 1_000_000uL
    private val serviceId = "a".repeat(64)

    @Test
    fun object28PublishAndFetchRoundTripWithExactFieldsAndDomains() {
        val publish = fixture(ProductionC1CandidateOperation.PUBLISH)
        val fetch = fixture(ProductionC1CandidateOperation.FETCH)
        listOf(publish, fetch).forEach { value ->
            val bytes = value.receipt.canonicalBytes()
            assertEquals(28, bytes[4].toInt() and 0xff)
            assertTrue(bytes.size <= ProductionC1CandidateOperationReceiptContract.MAXIMUM_BYTES)
            assertEquals((1..48).toList(), tags(bytes))
            val decoded = ProductionC1CandidateOperationReceipt.decode(bytes)
            assertEquals(value.receipt, decoded)
            assertEquals(value.receipt.hashCode(), decoded.hashCode())
            assertEquals(ProductionC1CandidateOperationReceiptStatus.COMMITTED, decoded.status)
            assertEquals(1u, decoded.consumedOperations)
            assertEquals(
                value.receipt,
                ProductionC1CandidateOperationReceiptVerifier.verify(
                    decoded,
                    value.verifiedCapability,
                    value.authorization,
                    value.authority,
                    value.verifiedKeyset,
                    now,
                ).receipt,
            )
        }
        assertReceiptTranscript(
            publish.receipt,
            "AetherLink G1a-C candidate-publish operation receipt service signature v1",
        )
        assertReceiptTranscript(
            fetch.receipt,
            "AetherLink G1a-C candidate-fetch operation receipt service signature v1",
        )
        assertNotEquals(publish.receipt.serviceSignature.toList(), fetch.receipt.serviceSignature.toList())
        assertNotEquals(publish.receipt.digestHex(), fetch.receipt.digestHex())

        val signature = publish.receipt.serviceSignature
        signature.fill(0)
        assertTrue(publish.receipt.serviceSignature.any { it != 0.toByte() })
        assertEquals(
            publish.receipt,
            ProductionC1CandidateOperationReceipt.decode(publish.receipt.canonicalBytes()),
        )
    }

    @Test
    fun usageLedgerEnforcesExactAuthorizationCasRetentionReplayQuotaAndRetry() {
        val publish = fixture(ProductionC1CandidateOperation.PUBLISH)
        assertEquals(ProductionC1CandidateCASDisposition.APPLIED, publish.preparation.disposition)
        assertEquals(publish.previousState.revision + 1uL, publish.committedState.revision)
        assertEquals(0uL, publish.committedState.remainingOperations)
        assertEquals(0uL, publish.committedState.remainingBytes)
        assertEquals(1, publish.committedState.entries.size)
        assertEquals(
            expectedRequestDigest(
                publish.receipt.proofId,
                publish.verifiedCapability.capabilityDigest,
                publish.authorizationDigest,
            ),
            publish.requestDigest,
        )
        assertEquals(
            expectedSnapshotDigest(publish.previousState),
            publish.previousState.snapshotDigestHex(),
        )
        assertEquals(
            expectedSnapshotDigest(publish.committedState),
            publish.committedState.snapshotDigestHex(),
        )
        val committedEntry = publish.committedState.entries.single()
        assertEquals(
            expectedUsageResultDigest(
                committedEntry.requestId,
                committedEntry.requestDigest,
                committedEntry.capabilityDigest,
                committedEntry.authorizationDigest,
                committedEntry.singleUseNonce,
                committedEntry.consumedBytes,
                publish.previousState.revision,
                publish.committedState.revision,
            ),
            committedEntry.receiptDigest,
        )

        val retry = prepareConsume(
            publish,
            state = publish.committedState,
            expectedRevision = ULong.MAX_VALUE,
            expectedSnapshotDigest = "f".repeat(64),
            nowMs = publish.verifiedCapability.capability.expiresAtMs,
        )
        assertEquals(ProductionC1CandidateCASDisposition.IDEMPOTENT, retry.disposition)
        assertEquals(publish.committedState, retry.nextState)
        val reloadRetry = ProductionC1CandidateUsageLedger.prepareCommittedRetry(
            publish.committedState,
            publish.receipt.proofId,
            publish.requestDigest,
            publish.verifiedCapability.capability.canonicalBytes(),
            publish.authorization,
        )
        assertEquals(ProductionC1CandidateCASDisposition.IDEMPOTENT, reloadRetry.disposition)
        assertEquals(publish.committedState, reloadRetry.nextState)

        assertCandidateError(ProductionC1CandidateCapabilityError.REQUEST_CONFLICT) {
            ProductionC1CandidateUsageLedger.prepareCommittedRetry(
                publish.committedState,
                publish.receipt.proofId,
                "f".repeat(64),
                publish.verifiedCapability.capability.canonicalBytes(),
                publish.authorization,
            )
        }
        assertCandidateError(ProductionC1CandidateCapabilityError.ROUTE_MISMATCH) {
            ProductionC1CandidateUsageLedger.prepareCommittedRetry(
                publish.committedState,
                publish.receipt.proofId,
                publish.requestDigest,
                publish.verifiedCapability.capability.canonicalBytes(),
                P2pFetchRouteAuthorization(
                    publish.authority.pairBindingDigest,
                    publish.authority.pairEpoch,
                    publish.authority.generation,
                    publish.verifiedCapability.capability.candidateBatchDigest,
                    publish.verifiedCapability.capabilityDigest,
                ),
            )
        }

        assertCandidateError(ProductionC1CandidateCapabilityError.REVISION_MISMATCH) {
            prepareConsume(
                publish,
                state = publish.previousState,
                expectedRevision = 99uL,
            )
        }
        val quotaState = ProductionC1CandidateUsageLedgerState(
            remainingOperations = 0uL,
            remainingBytes = publish.verifiedCapability.capability.candidateBatchByteCount.toULong(),
            retentionLimit = 4u,
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.QUOTA_EXCEEDED) {
            prepareConsume(publish, quotaState)
        }

        val fetch = fixture(ProductionC1CandidateOperation.FETCH)
        val retainedState = ProductionC1CandidateUsageLedgerState(
            revision = publish.committedState.revision,
            remainingOperations = 1uL,
            remainingBytes = fetch.verifiedCapability.capability.candidateBatchByteCount.toULong(),
            retentionLimit = 1u,
            entries = publish.committedState.entries,
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.RETENTION_EXHAUSTED) {
            prepareConsume(fetch, retainedState)
        }

        val sameNonce = fixture(
            ProductionC1CandidateOperation.PUBLISH,
            proofCharacter = "9",
            capabilityCharacter = "6",
            nonceCharacter = "7",
        )
        val replayState = ProductionC1CandidateUsageLedgerState(
            revision = publish.committedState.revision,
            remainingOperations = 1uL,
            remainingBytes = sameNonce.verifiedCapability.capability.candidateBatchByteCount.toULong(),
            retentionLimit = 4u,
            entries = publish.committedState.entries,
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.REPLAY) {
            prepareConsume(sameNonce, replayState)
        }
    }

    @Test
    fun usageLedgerStateValidatesUniqueMonotonicEntriesAndCopiesInputList() {
        val fixture = fixture(ProductionC1CandidateOperation.PUBLISH)
        val first = fixture.committedState.entries.single()
        val duplicateRequest = usageEntry(
            requestId = first.requestId,
            committedRevision = 3uL,
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.INVALID_VALUE) {
            ProductionC1CandidateUsageLedgerState(
                revision = 3uL,
                remainingOperations = 1uL,
                remainingBytes = 1uL,
                retentionLimit = 4u,
                entries = listOf(first, duplicateRequest),
            )
        }
        val nonMonotonic = usageEntry(committedRevision = first.committedRevision)
        assertCandidateError(ProductionC1CandidateCapabilityError.INVALID_VALUE) {
            ProductionC1CandidateUsageLedgerState(
                revision = first.committedRevision,
                remainingOperations = 1uL,
                remainingBytes = 1uL,
                retentionLimit = 4u,
                entries = listOf(first, nonMonotonic),
            )
        }
        val zeroBytes = usageEntry(consumedBytes = 0uL, committedRevision = 3uL)
        assertCandidateError(ProductionC1CandidateCapabilityError.INVALID_VALUE) {
            ProductionC1CandidateUsageLedgerState(
                revision = 3uL,
                remainingOperations = 1uL,
                remainingBytes = 1uL,
                retentionLimit = 4u,
                entries = listOf(first, zeroBytes),
            )
        }

        val mutableEntries = mutableListOf(first)
        val copied = ProductionC1CandidateUsageLedgerState(
            revision = fixture.committedState.revision,
            remainingOperations = 0uL,
            remainingBytes = 0uL,
            retentionLimit = 4u,
            entries = mutableEntries,
        )
        mutableEntries.clear()
        assertEquals(listOf(first), copied.entries)
        assertEquals(fixture.committedState.snapshotDigestHex(), copied.snapshotDigestHex())

        val second = ProductionC1CandidateUsageEntry(
            requestId = "6".repeat(64),
            requestDigest = "7".repeat(64),
            capabilityDigest = "8".repeat(64),
            authorizationDigest = "9".repeat(64),
            singleUseNonce = "a".repeat(64),
            consumedBytes = 1uL,
            receiptDigest = "b".repeat(64),
            committedRevision = first.committedRevision + 1uL,
        )
        val expectedEntries = listOf(first, second)
        val sealed = ProductionC1CandidateUsageLedgerState(
            revision = second.committedRevision,
            remainingOperations = 0uL,
            remainingBytes = 0uL,
            retentionLimit = 4u,
            entries = expectedEntries,
        )
        val sealedDigest = sealed.snapshotDigestHex()
        (sealed.entries as MutableList).clear()
        assertEquals(expectedEntries, sealed.entries)
        assertEquals(sealedDigest, sealed.snapshotDigestHex())
    }

    @Test
    fun object28RejectsBoundFieldsTagsTrailingHighSAndSizeMutations() {
        val fixture = fixture(ProductionC1CandidateOperation.PUBLISH)
        val canonical = fixture.receipt.canonicalBytes()
        val mutations = listOf(
            3 to "pending".toByteArray(),
            18 to "0".repeat(64).toByteArray(),
            24 to "0".repeat(64).toByteArray(),
            25 to "0".repeat(64).toByteArray(),
            26 to "0".repeat(64).toByteArray(),
            27 to "0".repeat(64).toByteArray(),
            28 to "0".repeat(64).toByteArray(),
            29 to "0".repeat(64).toByteArray(),
            30 to "0".repeat(64).toByteArray(),
            33 to be(fixture.receipt.candidateBatchSequence + 1uL),
            37 to "0".repeat(64).toByteArray(),
            38 to be(fixture.receipt.previousLedgerRevision + 1uL),
            40 to "0".repeat(64).toByteArray(),
            41 to "0".repeat(64).toByteArray(),
            42 to "0".repeat(64).toByteArray(),
            46 to be(fixture.receipt.notBeforeMs),
        )
        mutations.forEach { (tag, value) ->
            assertReceiptRejected(replaceTLVField(canonical, tag, value), fixture)
        }
        assertReceiptRejected(canonical.copyOf().also { it[4] = 27 }, fixture)
        assertReceiptRejected(
            replaceTLVField(canonical, 2, be(2uL)),
            fixture,
        )
        assertReceiptRejected(swapTLVFields(canonical, 23, 24), fixture)
        assertReceiptRejected(canonical + byteArrayOf(0), fixture)
        assertC1Error(ProductionC1Error.LIMIT_EXCEEDED) {
            ProductionC1CandidateOperationReceipt.decode(
                canonical + ByteArray(ProductionC1CandidateOperationReceiptContract.MAXIMUM_BYTES),
            )
        }
        assertC1Error(ProductionC1Error.HIGH_S) {
            ProductionC1CandidateOperationReceipt.decode(
                replaceTLVField(canonical, 48, makeHighS(fixture.receipt.serviceSignature)),
            )
        }
        val changedSignature = fixture.receipt.serviceSignature.also {
            it[it.lastIndex] = (it.last().toInt() xor 1).toByte()
        }
        assertReceiptRejected(replaceTLVField(canonical, 48, changedSignature), fixture)
    }

    @Test
    fun receiptVerifierChecksPurposeRotationRevocationAndExpiryAtUse() {
        assertC1Error(ProductionC1Error.KEY_PURPOSE_MISMATCH) {
            fixture(
                ProductionC1CandidateOperation.PUBLISH,
                receiptPurpose = ProductionC1DelegatedKeyPurpose.CANDIDATE_FETCH_RECEIPT,
            )
        }
        val fixture = fixture(ProductionC1CandidateOperation.PUBLISH)
        val rotated = alternateKeyset(
            fixture,
            version = 2uL,
            delegatedVersion = 1uL,
            purpose = ProductionC1DelegatedKeyPurpose.CANDIDATE_PUBLISH_RECEIPT,
            notBeforeMs = now - 1_000uL,
            expiresAtMs = now + 100_000uL,
        )
        verifyReceipt(fixture, rotated)

        val wrongPurpose = alternateKeyset(
            fixture,
            purpose = ProductionC1DelegatedKeyPurpose.CANDIDATE_FETCH_RECEIPT,
            notBeforeMs = now - 1_000uL,
            expiresAtMs = now + 100_000uL,
        )
        assertC1Error(ProductionC1Error.KEY_PURPOSE_MISMATCH) {
            verifyReceipt(fixture, wrongPurpose)
        }
        val revoked = alternateKeyset(
            fixture,
            purpose = ProductionC1DelegatedKeyPurpose.CANDIDATE_PUBLISH_RECEIPT,
            notBeforeMs = now - 1_000uL,
            expiresAtMs = now + 100_000uL,
            revokedAtMs = now,
        )
        assertC1Error(ProductionC1Error.KEY_REVOKED) {
            verifyReceipt(fixture, revoked)
        }
        val expired = alternateKeyset(
            fixture,
            purpose = ProductionC1DelegatedKeyPurpose.CANDIDATE_PUBLISH_RECEIPT,
            notBeforeMs = now - 1_000uL,
            expiresAtMs = now,
        )
        assertC1Error(ProductionC1Error.EXPIRED) {
            verifyReceipt(fixture, expired)
        }
        assertC1Error(ProductionC1Error.EXPIRED) {
            verifyReceipt(fixture, fixture.verifiedKeyset, fixture.receipt.expiresAtMs)
        }
    }

    @Test
    fun verifierRejectsCapabilityProofAndAuthorizationSubstitution() {
        val publish = fixture(ProductionC1CandidateOperation.PUBLISH)
        val fetch = fixture(ProductionC1CandidateOperation.FETCH)
        assertCandidateError(ProductionC1CandidateCapabilityError.AUTHORITY_MISMATCH) {
            ProductionC1CandidateOperationReceiptVerifier.verify(
                publish.receipt,
                fetch.verifiedCapability,
                fetch.authorization,
                fetch.authority,
                fetch.verifiedKeyset,
                now,
            )
        }
        assertCandidateError(ProductionC1CandidateCapabilityError.ROUTE_MISMATCH) {
            ProductionC1CandidateOperationReceiptVerifier.verify(
                publish.receipt,
                publish.verifiedCapability,
                fetch.authorization,
                publish.authority,
                publish.verifiedKeyset,
                now,
            )
        }
        val alternateProofAndCapability = fixture(
            ProductionC1CandidateOperation.PUBLISH,
            proofCharacter = "9",
            capabilityCharacter = "6",
            nonceCharacter = "0",
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.AUTHORITY_MISMATCH) {
            ProductionC1CandidateOperationReceiptVerifier.verify(
                publish.receipt,
                alternateProofAndCapability.verifiedCapability,
                alternateProofAndCapability.authorization,
                alternateProofAndCapability.authority,
                alternateProofAndCapability.verifiedKeyset,
                now,
            )
        }
    }

    @Test
    fun readbackConfirmationAndSignerRejectStateCoreSubstitution() {
        val fixture = fixture(ProductionC1CandidateOperation.PUBLISH)
        val alternateCommitted = ProductionC1CandidateUsageLedgerState(
            revision = fixture.committedState.revision,
            remainingOperations = fixture.committedState.remainingOperations,
            remainingBytes = fixture.committedState.remainingBytes,
            retentionLimit = fixture.committedState.retentionLimit + 1u,
            entries = fixture.committedState.entries,
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.REVISION_MISMATCH) {
            ReadbackConfirmedProductionC1CandidateUsageReceipt.confirm(
                fixture.preparation,
                alternateCommitted,
                fixture.receipt.ledgerId,
                fixture.receipt.commitRecordDigest,
            )
        }
        val alternatePrevious = ProductionC1CandidateUsageLedgerState(
            revision = fixture.previousState.revision,
            remainingOperations = fixture.previousState.remainingOperations,
            remainingBytes = fixture.previousState.remainingBytes,
            retentionLimit = fixture.previousState.retentionLimit + 1u,
            entries = fixture.previousState.entries,
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.REVISION_MISMATCH) {
            signReceipt(
                fixture,
                fixture.confirmedUsageReceipt,
                alternatePrevious,
                alternateCommitted,
            )
        }
    }

    @Test
    fun idempotentRetryCannotCreateAnotherObject28Signature() {
        val fixture = fixture(ProductionC1CandidateOperation.PUBLISH)
        val retry = prepareConsume(
            fixture,
            state = fixture.committedState,
            expectedRevision = ULong.MAX_VALUE,
            expectedSnapshotDigest = "f".repeat(64),
            nowMs = fixture.verifiedCapability.capability.expiresAtMs,
        )
        assertEquals(ProductionC1CandidateCASDisposition.IDEMPOTENT, retry.disposition)
        val confirmedRetry = ReadbackConfirmedProductionC1CandidateUsageReceipt.confirm(
            retry,
            fixture.committedState,
            fixture.receipt.ledgerId,
            fixture.receipt.commitRecordDigest,
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.REPLAY) {
            signReceipt(
                fixture,
                confirmedRetry,
                fixture.previousState,
                fixture.committedState,
            )
        }
    }

    private class Fixture(
        val rootKey: PrivateKey,
        val receiptKey: PrivateKey,
        val authority: ProductionPairAuthorityState,
        val verifiedKeyset: VerifiedProductionC1ServiceKeyset,
        val verifiedCapability: VerifiedProductionC1CandidateCapability,
        val authorization: ProductionRouteAuthorization,
        val authorizationDigest: String,
        val requestDigest: String,
        val previousState: ProductionC1CandidateUsageLedgerState,
        val preparation: ProductionC1CandidateUsagePreparation,
        val committedState: ProductionC1CandidateUsageLedgerState,
        val confirmedUsageReceipt: ReadbackConfirmedProductionC1CandidateUsageReceipt,
        val receipt: ProductionC1CandidateOperationReceipt,
    )

    private fun fixture(
        operation: ProductionC1CandidateOperation,
        receiptPurpose: ProductionC1DelegatedKeyPurpose? = null,
        proofCharacter: String = if (operation == ProductionC1CandidateOperation.PUBLISH) "3" else "4",
        capabilityCharacter: String = if (operation == ProductionC1CandidateOperation.PUBLISH) "5" else "6",
        nonceCharacter: String = if (operation == ProductionC1CandidateOperation.PUBLISH) "7" else "8",
    ): Fixture {
        val root = privateKey(101)
        val capabilityKey = privateKey(
            if (operation == ProductionC1CandidateOperation.PUBLISH) 104 else 105,
        )
        val receiptKey = privateKey(106)
        val expectedReceiptPurpose = if (operation == ProductionC1CandidateOperation.PUBLISH) {
            ProductionC1DelegatedKeyPurpose.CANDIDATE_PUBLISH_RECEIPT
        } else {
            ProductionC1DelegatedKeyPurpose.CANDIDATE_FETCH_RECEIPT
        }
        val capabilityPurpose = if (operation == ProductionC1CandidateOperation.PUBLISH) {
            ProductionC1DelegatedKeyPurpose.CANDIDATE_PUBLISH
        } else {
            ProductionC1DelegatedKeyPurpose.CANDIDATE_FETCH
        }
        val delegated = listOf(
            delegated(capabilityKey, capabilityPurpose),
            delegated(receiptKey, receiptPurpose ?: expectedReceiptPurpose),
        ).sortedBy { it.keyId }
        val keyset = ProductionC1ServiceKeyset.signed(
            serviceId,
            1uL,
            null,
            now - 1_000uL,
            now + 100_000uL,
            delegated,
            publicKey(root),
            root,
        )
        val verifiedKeyset = ProductionC1Verifier.verifyServiceKeyset(
            keyset,
            serviceId,
            publicKey(root),
            1uL,
            nowMs = now,
        )
        val clientIdentity = privateKey(102)
        val runtimeIdentity = privateKey(103)
        val authority = authority(clientIdentity, runtimeIdentity)
        val context = context(authority)
        val requester = P2pNatRole.CLIENT
        val owner = if (operation == ProductionC1CandidateOperation.PUBLISH) {
            P2pNatRole.CLIENT
        } else {
            P2pNatRole.RUNTIME
        }
        val batch = CandidateBatch(
            SESSION_ID,
            authority.generation,
            if (operation == ProductionC1CandidateOperation.PUBLISH) 1uL else 2uL,
            now + 30_000uL,
            owner,
            listOf(candidate(operation)),
        )
        val proofId = proofCharacter.repeat(64)
        val capabilityId = capabilityCharacter.repeat(64)
        val nonce = nonceCharacter.repeat(64)
        val proof = ProductionC1EndpointOperationProof.signed(
            requesterRole = requester,
            operation = operation,
            candidateOwnerRole = owner,
            proofId = proofId,
            attemptId = ATTEMPT_ID,
            capabilityId = capabilityId,
            candidateBatch = batch,
            singleUseNonce = nonce,
            securityContext = context,
            serviceAudienceId = serviceId,
            authority = authority,
            issuedAtMs = now - 200uL,
            notBeforeMs = now - 10uL,
            expiresAtMs = now + 20_000uL,
            requesterIdentityPublicKeyX963 = x963(publicKey(clientIdentity)),
            requesterIdentityPrivateKey = clientIdentity,
        )
        val capability = ProductionC1CandidateCapability.signed(
            operation = operation,
            serviceIdDigest = serviceId,
            keysetVersion = 1uL,
            capabilityId = capabilityId,
            attemptId = ATTEMPT_ID,
            requesterRole = requester,
            candidateOwnerRole = owner,
            maximumCandidateBytes = P2pNatContract.MAX_CANDIDATE_BATCH_BYTES.toULong(),
            singleUseNonce = nonce,
            issuedAtMs = now - 100uL,
            notBeforeMs = now - 10uL,
            expiresAtMs = now + 20_000uL,
            authority = authority,
            candidateBatch = batch,
            endpointOperationProof = proof,
            signingPublicKey = publicKey(capabilityKey),
            signingPrivateKey = capabilityKey,
        )
        val verifiedCapability = ProductionC1CandidateVerifier.verifyCapability(
            capability,
            P2pNatCanonicalCodec.encode(batch),
            proof,
            context,
            authority,
            verifiedKeyset,
            now,
        )
        val authorization: ProductionRouteAuthorization =
            if (operation == ProductionC1CandidateOperation.PUBLISH) {
                P2pPublishRouteAuthorization(
                    authority.pairBindingDigest,
                    authority.pairEpoch,
                    authority.generation,
                    capability.candidateBatchDigest,
                    verifiedCapability.capabilityDigest,
                )
            } else {
                P2pFetchRouteAuthorization(
                    authority.pairBindingDigest,
                    authority.pairEpoch,
                    authority.generation,
                    capability.candidateBatchDigest,
                    verifiedCapability.capabilityDigest,
                )
            }
        val authorizationDigest = digest(ProductionSecureSessionCodec.encode(authorization))
        val requestDigest = ProductionC1CandidateUsageLedger.requestDigest(
            proofId,
            verifiedCapability.capabilityDigest,
            authorizationDigest,
        )
        val previous = ProductionC1CandidateUsageLedgerState(
            remainingOperations = 1uL,
            remainingBytes = capability.candidateBatchByteCount.toULong(),
            retentionLimit = 4u,
        )
        val preparation = ProductionC1CandidateUsageLedger.prepareConsume(
            previous,
            previous.revision,
            previous.snapshotDigestHex(),
            proofId,
            requestDigest,
            verifiedCapability,
            authorization,
            requester,
            authority.clientIdentityFingerprint,
            authority,
            now,
        )
        val committed = preparation.nextState
        val ledgerId = digest("object28-ledger".toByteArray())
        val commitRecordDigest = digest("object28-commit-${operation.wireValue}".toByteArray())
        val confirmed = ReadbackConfirmedProductionC1CandidateUsageReceipt.confirm(
            preparation,
            committed,
            ledgerId,
            commitRecordDigest,
        )
        val receipt = ProductionC1CandidateOperationReceipt.signedAfterAppliedCommit(
            verifiedCapability,
            authorization,
            confirmed,
            previous,
            committed,
            now,
            now,
            now,
            now + 10_000uL,
            authority,
            verifiedKeyset,
            publicKey(receiptKey),
            receiptKey,
        )
        return Fixture(
            root,
            receiptKey,
            authority,
            verifiedKeyset,
            verifiedCapability,
            authorization,
            authorizationDigest,
            requestDigest,
            previous,
            preparation,
            committed,
            confirmed,
            receipt,
        )
    }

    private fun prepareConsume(
        fixture: Fixture,
        state: ProductionC1CandidateUsageLedgerState,
        expectedRevision: ULong = state.revision,
        expectedSnapshotDigest: String = state.snapshotDigestHex(),
        nowMs: ULong = now,
    ): ProductionC1CandidateUsagePreparation =
        ProductionC1CandidateUsageLedger.prepareConsume(
            state,
            expectedRevision,
            expectedSnapshotDigest,
            fixture.receipt.proofId,
            fixture.requestDigest,
            fixture.verifiedCapability,
            fixture.authorization,
            fixture.verifiedCapability.capability.requesterRole,
            fixture.verifiedCapability.capability.requesterIdentityFingerprint,
            fixture.authority,
            nowMs,
        )

    private fun signReceipt(
        fixture: Fixture,
        confirmed: ReadbackConfirmedProductionC1CandidateUsageReceipt,
        previous: ProductionC1CandidateUsageLedgerState,
        committed: ProductionC1CandidateUsageLedgerState,
    ): ProductionC1CandidateOperationReceipt =
        ProductionC1CandidateOperationReceipt.signedAfterAppliedCommit(
            fixture.verifiedCapability,
            fixture.authorization,
            confirmed,
            previous,
            committed,
            now,
            now,
            now,
            now + 10_000uL,
            fixture.authority,
            fixture.verifiedKeyset,
            publicKey(fixture.receiptKey),
            fixture.receiptKey,
        )

    private fun verifyReceipt(
        fixture: Fixture,
        keyset: VerifiedProductionC1ServiceKeyset,
        nowMs: ULong = now,
    ): VerifiedProductionC1CandidateOperationReceipt =
        ProductionC1CandidateOperationReceiptVerifier.verify(
            fixture.receipt,
            fixture.verifiedCapability,
            fixture.authorization,
            fixture.authority,
            keyset,
            nowMs,
        )

    private fun alternateKeyset(
        fixture: Fixture,
        version: ULong = 1uL,
        delegatedVersion: ULong = 1uL,
        purpose: ProductionC1DelegatedKeyPurpose,
        notBeforeMs: ULong,
        expiresAtMs: ULong,
        revokedAtMs: ULong? = null,
    ): VerifiedProductionC1ServiceKeyset {
        val keys = mutableListOf(
            ProductionC1DelegatedKey(
                delegatedVersion,
                ProductionC1InternalBridge.keyId(publicKey(fixture.receiptKey)),
                purpose,
                notBeforeMs,
                expiresAtMs,
                revokedAtMs,
                x963(publicKey(fixture.receiptKey)),
            ),
        )
        if (version != delegatedVersion) {
            val current = privateKey(110)
            keys += ProductionC1DelegatedKey(
                version,
                ProductionC1InternalBridge.keyId(publicKey(current)),
                ProductionC1DelegatedKeyPurpose.ROUTE_CAPABILITY,
                now - 1_000uL,
                now + 100_000uL,
                publicKeyX963 = x963(publicKey(current)),
            )
        }
        val keyset = ProductionC1ServiceKeyset.signed(
            serviceId,
            version,
            if (version == 1uL) null else fixture.verifiedKeyset.keyset.digestHex(),
            now - 1_000uL,
            now + 100_000uL,
            keys.sortedBy { it.keyId },
            publicKey(fixture.rootKey),
            fixture.rootKey,
        )
        return ProductionC1Verifier.verifyServiceKeyset(
            keyset,
            serviceId,
            publicKey(fixture.rootKey),
            version,
            nowMs = now - 1uL,
        )
    }

    private fun authority(
        clientIdentityKey: PrivateKey,
        runtimeIdentityKey: PrivateKey,
    ): ProductionPairAuthorityState = ProductionPairAuthorityState(
        pairBindingDigest = "d".repeat(64),
        pairEpoch = 1uL,
        clientIdentityFingerprint = ProductionC1InternalBridge.keyId(publicKey(clientIdentityKey)),
        runtimeIdentityFingerprint = ProductionC1InternalBridge.keyId(publicKey(runtimeIdentityKey)),
        generation = 1uL,
        serviceConfigVersion = 1uL,
        keysetVersion = 1uL,
        revocationCounter = 0uL,
        protocolFloor = 1u,
        status = ProductionPairAuthorityStatus.ACTIVE,
        transitionId = "1".repeat(64),
        transitionRequestDigest = "2".repeat(64),
        acceptedReceiptDigest = "e".repeat(64),
        authorityRevision = 1uL,
    )

    private fun context(
        authority: ProductionPairAuthorityState,
    ): ProductionC1PreauthorizationSessionContext = ProductionC1PreauthorizationSessionContext(
        sessionId = SESSION_ID,
        pairBindingDigest = authority.pairBindingDigest,
        pairEpoch = authority.pairEpoch,
        clientIdentityFingerprint = authority.clientIdentityFingerprint,
        runtimeIdentityFingerprint = authority.runtimeIdentityFingerprint,
        clientEphemeralPublicKey = x963(publicKey(privateKey(107))),
        runtimeEphemeralPublicKey = x963(publicKey(privateKey(108))),
        clientNonce = "c".repeat(32),
        runtimeNonce = "d".repeat(32),
        generation = authority.generation,
        serviceConfigVersion = authority.serviceConfigVersion,
        keysetVersion = authority.keysetVersion,
        revocationCounter = authority.revocationCounter,
        routeKind = ProductionC1RouteKind.P2P_DIRECT,
    )

    private fun candidate(operation: ProductionC1CandidateOperation): P2pCandidate = P2pCandidate(
        kind = CandidateKind.HOST,
        family = AddressFamily.IPV4,
        port = 50_000,
        priority = 100u,
        foundation = ByteArray(8) {
            if (operation == ProductionC1CandidateOperation.PUBLISH) 1 else 2
        },
        address = if (operation == ProductionC1CandidateOperation.PUBLISH) {
            byteArrayOf(1, 1, 1, 1)
        } else {
            byteArrayOf(8, 8, 4, 4)
        },
    )

    private fun delegated(
        key: PrivateKey,
        purpose: ProductionC1DelegatedKeyPurpose,
    ): ProductionC1DelegatedKey = ProductionC1DelegatedKey(
        1uL,
        ProductionC1InternalBridge.keyId(publicKey(key)),
        purpose,
        now - 1_000uL,
        now + 100_000uL,
        publicKeyX963 = x963(publicKey(key)),
    )

    private fun usageEntry(
        requestId: String = "0".repeat(64),
        consumedBytes: ULong = 1uL,
        committedRevision: ULong,
    ): ProductionC1CandidateUsageEntry = ProductionC1CandidateUsageEntry(
        requestId = requestId,
        requestDigest = "1".repeat(64),
        capabilityDigest = "2".repeat(64),
        authorizationDigest = "3".repeat(64),
        singleUseNonce = "4".repeat(64),
        consumedBytes = consumedBytes,
        receiptDigest = "5".repeat(64),
        committedRevision = committedRevision,
    )

    private fun assertReceiptRejected(data: ByteArray, fixture: Fixture) {
        try {
            val receipt = ProductionC1CandidateOperationReceipt.decode(data)
            ProductionC1CandidateOperationReceiptVerifier.verify(
                receipt,
                fixture.verifiedCapability,
                fixture.authorization,
                fixture.authority,
                fixture.verifiedKeyset,
                now,
            )
            fail("Expected receipt rejection")
        } catch (_: IllegalArgumentException) {
            // Decoder and verifier deliberately use typed IllegalArgumentException subclasses.
        }
    }

    private fun assertCandidateError(
        expected: ProductionC1CandidateCapabilityError,
        body: () -> Unit,
    ) {
        try {
            body()
            fail("Expected $expected")
        } catch (error: ProductionC1CandidateCapabilityException) {
            assertEquals(expected, error.reason)
        }
    }

    private fun assertC1Error(expected: ProductionC1Error, body: () -> Unit) {
        try {
            body()
            fail("Expected $expected")
        } catch (error: ProductionC1Exception) {
            assertEquals(expected, error.reason)
        }
    }

    private fun tags(data: ByteArray): List<Int> = tlvFields(data).map { it.first }

    private fun replaceTLVField(
        data: ByteArray,
        tag: Int,
        replacement: ByteArray,
    ): ByteArray = encodeTLV(
        data,
        tlvFields(data).map { if (it.first == tag) tag to replacement else it },
    )

    private fun swapTLVFields(data: ByteArray, first: Int, second: Int): ByteArray {
        val fields = tlvFields(data).toMutableList()
        val left = fields.indexOfFirst { it.first == first }
        val right = fields.indexOfFirst { it.first == second }
        val temporary = fields[left]
        fields[left] = fields[right]
        fields[right] = temporary
        return encodeTLV(data, fields)
    }

    private fun tlvFields(data: ByteArray): List<Pair<Int, ByteArray>> {
        val result = mutableListOf<Pair<Int, ByteArray>>()
        var cursor = 6
        while (cursor < data.size) {
            val tag = data[cursor].toInt() and 0xff
            val size = ByteBuffer.wrap(data, cursor + 1, 4).int
            result += tag to data.copyOfRange(cursor + 5, cursor + 5 + size)
            cursor += 5 + size
        }
        return result
    }

    private fun encodeTLV(
        original: ByteArray,
        fields: List<Pair<Int, ByteArray>>,
    ): ByteArray {
        var result = original.copyOfRange(0, 6)
        fields.forEach { (tag, value) ->
            result += byteArrayOf(tag.toByte())
            result += ByteBuffer.allocate(4).putInt(value.size).array()
            result += value
        }
        return result
    }

    private fun assertReceiptTranscript(
        receipt: ProductionC1CandidateOperationReceipt,
        domain: String,
    ) {
        val canonical = receipt.canonicalBytes()
        val claims = encodeTLV(canonical, tlvFields(canonical).dropLast(1))
        val expected = domain.toByteArray(Charsets.US_ASCII) +
            byteArrayOf(0) +
            be(claims.size.toUInt()) +
            claims
        assertArrayEquals(expected, receipt.signingTranscript())
    }

    private fun be(value: ULong): ByteArray = ByteBuffer.allocate(8).putLong(value.toLong()).array()

    private fun be(value: UInt): ByteArray = ByteBuffer.allocate(4).putInt(value.toInt()).array()

    private fun expectedRequestDigest(
        requestId: String,
        capabilityDigest: String,
        authorizationDigest: String,
    ): String = domainDigest(
        "AetherLink G1a-C candidate usage request v1",
        rawDigest(requestId) + rawDigest(capabilityDigest) + rawDigest(authorizationDigest),
    )

    private fun expectedSnapshotDigest(state: ProductionC1CandidateUsageLedgerState): String {
        var claims = be(state.revision)
        claims += be(state.remainingOperations)
        claims += be(state.remainingBytes)
        claims += be(state.retentionLimit)
        claims += be(state.entries.size.toUInt())
        state.entries.forEach { entry ->
            claims += rawDigest(entry.requestId)
            claims += rawDigest(entry.requestDigest)
            claims += rawDigest(entry.capabilityDigest)
            claims += rawDigest(entry.authorizationDigest)
            claims += rawDigest(entry.singleUseNonce)
            claims += rawDigest(entry.receiptDigest)
            claims += be(entry.consumedBytes)
            claims += be(entry.committedRevision)
        }
        return domainDigest("AetherLink G1a-C candidate usage ledger snapshot v1", claims)
    }

    private fun expectedUsageResultDigest(
        proofId: String,
        requestDigest: String,
        capabilityDigest: String,
        authorizationDigest: String,
        nonce: String,
        consumedBytes: ULong,
        previousRevision: ULong,
        committedRevision: ULong,
    ): String = domainDigest(
        "AetherLink G1a-C readback-confirmed candidate usage receipt v1",
        rawDigest(proofId) +
            rawDigest(requestDigest) +
            rawDigest(capabilityDigest) +
            rawDigest(authorizationDigest) +
            rawDigest(nonce) +
            be(consumedBytes) +
            be(previousRevision) +
            be(committedRevision),
    )

    private fun domainDigest(domain: String, claims: ByteArray): String = digest(
        domain.toByteArray(Charsets.US_ASCII) +
            byteArrayOf(0) +
            be(claims.size.toUInt()) +
            claims,
    )

    private fun rawDigest(value: String): ByteArray =
        value.chunked(2).map { it.toInt(16).toByte() }.toByteArray()

    private fun digest(value: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(value).hex()

    private fun privateKey(scalar: Int): PrivateKey = KeyFactory.getInstance("EC").generatePrivate(
        ECPrivateKeySpec(BigInteger.valueOf(scalar.toLong()), P256),
    )

    private fun publicKey(privateKey: PrivateKey): PublicKey {
        val scalar = (privateKey as java.security.interfaces.ECPrivateKey).s
        return KeyFactory.getInstance("EC").generatePublic(
            ECPublicKeySpec(multiply(P256.generator, scalar), P256),
        )
    }

    private fun x963(publicKey: PublicKey): ByteArray {
        val point = (publicKey as ECPublicKey).w
        return byteArrayOf(0x04) + point.affineX.fixed(32) + point.affineY.fixed(32)
    }

    private fun multiply(point: ECPoint, scalar: BigInteger): ECPoint {
        val prime = (P256.curve.field as ECFieldFp).p
        var result: ECPoint? = null
        var addend: ECPoint? = point
        var value = scalar
        while (value.signum() > 0) {
            if (value.testBit(0)) result = add(result, addend, prime)
            addend = add(addend, addend, prime)
            value = value.shiftRight(1)
        }
        return requireNotNull(result)
    }

    private fun add(left: ECPoint?, right: ECPoint?, prime: BigInteger): ECPoint? {
        if (left == null) return right
        if (right == null) return left
        if (left.affineX == right.affineX && left.affineY.add(right.affineY).mod(prime) == BigInteger.ZERO) {
            return null
        }
        val slope = if (left == right) {
            left.affineX.modPow(BigInteger.TWO, prime).multiply(BigInteger.valueOf(3))
                .add(P256.curve.a)
                .multiply(left.affineY.multiply(BigInteger.TWO).mod(prime).modInverse(prime))
                .mod(prime)
        } else {
            right.affineY.subtract(left.affineY).mod(prime)
                .multiply(right.affineX.subtract(left.affineX).mod(prime).modInverse(prime))
                .mod(prime)
        }
        val x = slope.modPow(BigInteger.TWO, prime)
            .subtract(left.affineX)
            .subtract(right.affineX)
            .mod(prime)
        return ECPoint(x, slope.multiply(left.affineX.subtract(x)).subtract(left.affineY).mod(prime))
    }

    private fun makeHighS(der: ByteArray): ByteArray {
        val (r, s) = parseDer(der)
        return encodeDer(r, ORDER - s)
    }

    private fun parseDer(der: ByteArray): Pair<BigInteger, BigInteger> {
        var offset = 2
        fun integer(): BigInteger {
            check(der[offset++] == 0x02.toByte())
            val size = der[offset++].toInt() and 0xff
            return BigInteger(der.copyOfRange(offset, offset + size)).also { offset += size }
        }
        return integer() to integer()
    }

    private fun encodeDer(r: BigInteger, s: BigInteger): ByteArray {
        fun integer(value: BigInteger): ByteArray {
            val bytes = value.toByteArray()
            return byteArrayOf(0x02, bytes.size.toByte()) + bytes
        }
        val body = integer(r) + integer(s)
        return byteArrayOf(0x30, body.size.toByte()) + body
    }

    private fun BigInteger.fixed(size: Int): ByteArray {
        val raw = toByteArray()
        val unsigned = if (raw.size > 1 && raw[0] == 0.toByte()) raw.copyOfRange(1, raw.size) else raw
        return ByteArray(size - unsigned.size) + unsigned
    }

    private fun ByteArray.hex(): String = joinToString("") { "%02x".format(it) }

    companion object {
        private const val SESSION_ID = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        private const val ATTEMPT_ID =
            "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        private val P256: ECParameterSpec = AlgorithmParameters.getInstance("EC").run {
            init(ECGenParameterSpec("secp256r1"))
            getParameterSpec(ECParameterSpec::class.java)
        }
        private val ORDER = BigInteger(
            "ffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551",
            16,
        )
    }
}
