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
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

class ProductionG1aCCandidateContractsTest {
    private val now = 1_000_000uL
    private val serviceId = "a".repeat(64)

    @Test
    fun object27AndObject23And24RoundTripVerifyExactFieldsAndDomains() {
        val fixture = fixture()
        val publish = signedAndVerified(
            fixture,
            ProductionC1CandidateOperation.PUBLISH,
            P2pNatRole.CLIENT,
            P2pNatRole.CLIENT,
            fixture.publishKey,
            "4".repeat(64),
            "5".repeat(64),
            "6".repeat(64),
        )
        val fetch = signedAndVerified(
            fixture,
            ProductionC1CandidateOperation.FETCH,
            P2pNatRole.RUNTIME,
            P2pNatRole.CLIENT,
            fixture.fetchKey,
            "8".repeat(64),
            "9".repeat(64),
            "b".repeat(64),
        )

        val publishProofBytes = publish.endpointOperationProof.canonicalBytes()
        val publishBytes = publish.capability.canonicalBytes()
        val fetchBytes = fetch.capability.canonicalBytes()
        assertEquals(27, publishProofBytes[4].toInt() and 0xff)
        assertEquals(23, publishBytes[4].toInt() and 0xff)
        assertEquals(24, fetchBytes[4].toInt() and 0xff)
        assertEquals((1..24).toList(), tags(publishProofBytes))
        assertEquals((1..34).toList(), tags(publishBytes))
        assertEquals((1..34).toList(), tags(fetchBytes))
        assertEquals(
            publish.endpointOperationProof,
            ProductionC1EndpointOperationProof.decode(publishProofBytes),
        )
        assertEquals(publish.capability, ProductionC1CandidateCapability.decode(publishBytes))
        assertEquals(fetch.capability, ProductionC1CandidateCapability.decode(fetchBytes))
        assertEquals(publish.endpointOperationProof.hashCode(), ProductionC1EndpointOperationProof.decode(publishProofBytes).hashCode())
        assertEquals(publish.capability.hashCode(), ProductionC1CandidateCapability.decode(publishBytes).hashCode())

        assertTranscriptDomain(
            publish.endpointOperationProof.signingTranscript(),
            "AetherLink G1a-C endpoint-authenticated candidate operation v1",
        )
        assertTranscriptDomain(
            publish.capability.signingTranscript(),
            "AetherLink G1a-C candidate-publish capability service signature v1",
        )
        assertTranscriptDomain(
            fetch.capability.signingTranscript(),
            "AetherLink G1a-C candidate-fetch capability service signature v1",
        )
        assertNotEquals(
            publish.capability.signingTranscript().toList(),
            fetch.capability.signingTranscript().toList(),
        )
        assertEquals("5".repeat(64), publish.endpointOperationProof.proofId)
        assertEquals(fixture.clientBatch, publish.candidateBatch)
        assertEquals(fixture.clientBatch, fetch.candidateBatch)
    }

    @Test
    fun bilateralVerifierRequiresFourExactRoleShapesUniqueIdsAndTwoBatchPairs() {
        val fixture = fixture()
        val tuple = bilateralTuple(fixture)
        val bilateral = verifyBilateral(tuple, fixture)
        assertEquals(
            tuple.all,
            bilateral.all,
        )
        assertEquals(4, tuple.all.map { it.capability.capabilityId }.toSet().size)
        assertEquals(4, tuple.all.map { it.endpointOperationProof.proofId }.toSet().size)
        assertEquals(4, tuple.all.map { it.capability.singleUseNonce }.toSet().size)
        assertEquals(1, tuple.all.map { it.securityContext }.toSet().size)
        assertEquals(1, tuple.all.map { it.endpointOperationProof.serviceAudienceId }.toSet().size)
        assertEquals(setOf(P2pNatRole.CLIENT), tuple.all.map { it.endpointOperationProof.initiatorRole }.toSet())
        assertArrayEquals(
            tuple.clientPublish.canonicalCandidateBatch,
            tuple.runtimeFetchClient.canonicalCandidateBatch,
        )
        assertArrayEquals(
            tuple.runtimePublish.canonicalCandidateBatch,
            tuple.clientFetchRuntime.canonicalCandidateBatch,
        )
        assertNotEquals(
            tuple.clientPublish.capability.candidateBatchDigest,
            tuple.runtimePublish.capability.candidateBatchDigest,
        )
        assertEquals(
            expectedBilateralDigest(
                "AetherLink G1a-C bilateral candidate-publish set v1",
                tuple.clientPublish.capabilityDigest,
                tuple.runtimePublish.capabilityDigest,
            ),
            bilateral.bilateralPublishDigest,
        )
        assertEquals(
            expectedBilateralDigest(
                "AetherLink G1a-C bilateral candidate-fetch set v1",
                tuple.clientFetchRuntime.capabilityDigest,
                tuple.runtimeFetchClient.capabilityDigest,
            ),
            bilateral.bilateralFetchDigest,
        )
        assertNotEquals(bilateral.bilateralPublishDigest, bilateral.bilateralFetchDigest)
        assertEquals(bilateral, verifyBilateral(tuple, fixture))

        assertCandidateError(ProductionC1CandidateCapabilityError.ROLE_MISMATCH) {
            ProductionC1CandidateVerifier.verifyBilateral(
                tuple.clientPublish,
                tuple.runtimeFetchClient,
                tuple.clientPublish,
                tuple.clientFetchRuntime,
                fixture.authority,
                now,
            )
        }

        val duplicateCapabilityId = bilateralTuple(
            fixture,
            capabilityIds = repeatedHex("4", "8", "4", "f"),
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.AUTHORITY_MISMATCH) {
            verifyBilateral(duplicateCapabilityId, fixture)
        }

        val duplicateProofId = bilateralTuple(
            fixture,
            proofIds = repeatedHex("5", "9", "5", "0"),
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.AUTHORITY_MISMATCH) {
            verifyBilateral(duplicateProofId, fixture)
        }

        val duplicateNonce = bilateralTuple(
            fixture,
            nonces = repeatedHex("6", "b", "6", "1"),
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.AUTHORITY_MISMATCH) {
            verifyBilateral(duplicateNonce, fixture)
        }

        val alternateClientBatch = fixture.clientBatch.copy(
            sequence = 3uL,
            candidates = listOf(candidate(addressLastByte = 10)),
        )
        val mismatchedClientBatchPair = bilateralTuple(
            fixture,
            runtimeFetchClientBatch = alternateClientBatch,
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.BATCH_MISMATCH) {
            verifyBilateral(mismatchedClientBatchPair, fixture)
        }

        val alternateRuntimeBatch = fixture.runtimeBatch.copy(
            sequence = 4uL,
            candidates = listOf(candidate(addressLastByte = 11)),
        )
        val mismatchedRuntimeBatchPair = bilateralTuple(
            fixture,
            clientFetchRuntimeBatch = alternateRuntimeBatch,
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.BATCH_MISMATCH) {
            verifyBilateral(mismatchedRuntimeBatchPair, fixture)
        }

        val mismatchedContext = bilateralTuple(
            fixture,
            runtimePublishContext = context(
                fixture.authority,
                runtimeNonce = "e".repeat(32),
            ),
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.AUTHORITY_MISMATCH) {
            verifyBilateral(mismatchedContext, fixture)
        }

        assertC1Error(ProductionC1Error.EXPIRED) {
            verifyBilateral(tuple, fixture, tuple.clientPublish.capability.expiresAtMs)
        }
    }

    @Test
    fun bilateralVerifierRejectsSameVersionRootSignedKeysetForkMixing() {
        val fixture = fixture()
        val tuple = bilateralTuple(fixture)
        val exact = verifyBilateral(tuple, fixture)
        assertEquals(tuple.all, exact.all)
        val canonicalKeyset = fixture.verifiedKeyset.keyset.canonicalBytes()
        assertTrue(
            tuple.all.all {
                it.verifiedKeyset.keyset.canonicalBytes().contentEquals(canonicalKeyset)
            },
        )

        val forkOnlyKey = privateKey(108)
        val forkDelegated = ProductionC1DelegatedKey(
            1uL,
            keyId(publicKey(forkOnlyKey)),
            ProductionC1DelegatedKeyPurpose.CANDIDATE_PUBLISH,
            now - 1_000uL,
            now + 400_000uL,
            revokedAtMs = now + 300_000uL,
            publicKeyX963 = x963(publicKey(forkOnlyKey)),
        )
        val forkKeyset = verifiedKeyset(
            fixture.rootKey,
            listOf(
                delegated(fixture.publishKey, ProductionC1DelegatedKeyPurpose.CANDIDATE_PUBLISH),
                delegated(fixture.fetchKey, ProductionC1DelegatedKeyPurpose.CANDIDATE_FETCH),
                forkDelegated,
            ),
        )
        assertEquals(
            fixture.verifiedKeyset.keyset.serviceIdDigest,
            forkKeyset.keyset.serviceIdDigest,
        )
        assertEquals(
            fixture.verifiedKeyset.keyset.keysetVersion,
            forkKeyset.keyset.keysetVersion,
        )
        assertFalse(
            forkKeyset.keyset.canonicalBytes().contentEquals(canonicalKeyset),
        )
        val forkRuntimePublish = ProductionC1CandidateVerifier.verifyCapability(
            tuple.runtimePublish.capability,
            tuple.runtimePublish.canonicalCandidateBatch,
            tuple.runtimePublish.endpointOperationProof,
            tuple.runtimePublish.securityContext,
            fixture.authority,
            forkKeyset,
            now,
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.AUTHORITY_MISMATCH) {
            ProductionC1CandidateVerifier.verifyBilateral(
                tuple.clientPublish,
                tuple.runtimeFetchClient,
                forkRuntimePublish,
                tuple.clientFetchRuntime,
                fixture.authority,
                now,
            )
        }
    }

    @Test
    fun objectDomainPurposeAndLongTermEndpointIdentityStaySeparated() {
        val fixture = fixture()
        val publish = signedAndVerified(
            fixture,
            ProductionC1CandidateOperation.PUBLISH,
            P2pNatRole.CLIENT,
            P2pNatRole.CLIENT,
            fixture.publishKey,
            "4".repeat(64),
            "5".repeat(64),
            "6".repeat(64),
        )
        val fetch = signedAndVerified(
            fixture,
            ProductionC1CandidateOperation.FETCH,
            P2pNatRole.RUNTIME,
            P2pNatRole.CLIENT,
            fixture.fetchKey,
            "8".repeat(64),
            "9".repeat(64),
            "b".repeat(64),
        )

        assertCandidateError(ProductionC1CandidateCapabilityError.ROLE_MISMATCH) {
            proof(
                fixture,
                ProductionC1CandidateOperation.PUBLISH,
                P2pNatRole.CLIENT,
                P2pNatRole.CLIENT,
                "c".repeat(64),
                "d".repeat(64),
                "e".repeat(64),
                fixture.runtimeIdentityKey,
            )
        }
        // CryptoKit derives the public key from its private key. The JVM API accepts two
        // handles, so it deliberately rejects an invalid pair before returning wire bytes.
        assertC1Error(ProductionC1Error.INVALID_SIGNATURE) {
            ProductionC1EndpointOperationProof.signed(
                requesterRole = P2pNatRole.CLIENT,
                operation = ProductionC1CandidateOperation.PUBLISH,
                candidateOwnerRole = P2pNatRole.CLIENT,
                proofId = "c".repeat(64),
                attemptId = ATTEMPT_ID,
                capabilityId = "d".repeat(64),
                candidateBatch = fixture.clientBatch,
                singleUseNonce = "e".repeat(64),
                securityContext = fixture.context,
                serviceAudienceId = serviceId,
                authority = fixture.authority,
                issuedAtMs = now - 100uL,
                notBeforeMs = now - 50uL,
                expiresAtMs = now + 200_000uL,
                requesterIdentityPublicKeyX963 = x963(publicKey(fixture.clientIdentityKey)),
                requesterIdentityPrivateKey = fixture.runtimeIdentityKey,
            )
        }
        assertCandidateError(ProductionC1CandidateCapabilityError.ROLE_MISMATCH) {
            proof(
                fixture,
                ProductionC1CandidateOperation.FETCH,
                P2pNatRole.CLIENT,
                P2pNatRole.CLIENT,
                "c".repeat(64),
                "d".repeat(64),
                "e".repeat(64),
                fixture.clientIdentityKey,
            )
        }

        val crossObject = publish.capability.canonicalBytes().also {
            it[4] = ProductionC1CandidateCapabilityContract.FETCH_OBJECT_TYPE.toByte()
        }
        assertCandidateError(ProductionC1CandidateCapabilityError.INVALID_VALUE) {
            ProductionC1CandidateCapability.decode(crossObject)
        }
        val swappedSignature = replaceTLVField(
            fetch.capability.canonicalBytes(),
            34,
            publish.capability.serviceSignature,
        )
        val decodedSwapped = ProductionC1CandidateCapability.decode(swappedSignature)
        assertC1Error(ProductionC1Error.INVALID_SIGNATURE) {
            ProductionC1CandidateVerifier.verifyCapability(
                decodedSwapped,
                P2pNatCanonicalCodec.encode(fixture.clientBatch),
                fetch.endpointOperationProof,
                fixture.context,
                fixture.authority,
                fixture.verifiedKeyset,
                now,
            )
        }

        val wrongPurposeKeyset = verifiedKeyset(
            fixture.rootKey,
            listOf(
                delegated(
                    fixture.publishKey,
                    ProductionC1DelegatedKeyPurpose.CANDIDATE_FETCH,
                ),
            ),
        )
        assertC1Error(ProductionC1Error.KEY_PURPOSE_MISMATCH) {
            ProductionC1CandidateVerifier.verifyCapability(
                publish.capability,
                P2pNatCanonicalCodec.encode(fixture.clientBatch),
                publish.endpointOperationProof,
                fixture.context,
                fixture.authority,
                wrongPurposeKeyset,
                now,
            )
        }
    }

    @Test
    fun verifierRejectsAuthorityContextBatchWindowAndRevocationSubstitution() {
        val fixture = fixture()
        val publish = signedAndVerified(
            fixture,
            ProductionC1CandidateOperation.PUBLISH,
            P2pNatRole.CLIENT,
            P2pNatRole.CLIENT,
            fixture.publishKey,
            "4".repeat(64),
            "5".repeat(64),
            "6".repeat(64),
        )

        val staleAuthority = authority(
            fixture.clientIdentityKey,
            fixture.runtimeIdentityKey,
            serviceConfigVersion = 2uL,
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.AUTHORITY_MISMATCH) {
            ProductionC1CandidateVerifier.verifyCapability(
                publish.capability,
                P2pNatCanonicalCodec.encode(fixture.clientBatch),
                publish.endpointOperationProof,
                fixture.context,
                staleAuthority,
                fixture.verifiedKeyset,
                now,
            )
        }

        val substitutedContext = context(
            fixture.authority,
            runtimeNonce = "e".repeat(32),
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.ROLE_MISMATCH) {
            ProductionC1CandidateVerifier.verifyCapability(
                publish.capability,
                P2pNatCanonicalCodec.encode(fixture.clientBatch),
                publish.endpointOperationProof,
                substitutedContext,
                fixture.authority,
                fixture.verifiedKeyset,
                now,
            )
        }

        val substitutedBatch = fixture.clientBatch.copy(
            candidates = listOf(candidate(addressLastByte = 9)),
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.BATCH_MISMATCH) {
            ProductionC1CandidateVerifier.verifyCapability(
                publish.capability,
                P2pNatCanonicalCodec.encode(substitutedBatch),
                publish.endpointOperationProof,
                fixture.context,
                fixture.authority,
                fixture.verifiedKeyset,
                now,
            )
        }

        val expiringProof = proof(
            fixture,
            ProductionC1CandidateOperation.PUBLISH,
            P2pNatRole.CLIENT,
            P2pNatRole.CLIENT,
            "7".repeat(64),
            "8".repeat(64),
            "9".repeat(64),
            fixture.clientIdentityKey,
        )
        val expiredCapability = ProductionC1CandidateCapability.signed(
            operation = ProductionC1CandidateOperation.PUBLISH,
            serviceIdDigest = serviceId,
            keysetVersion = 1uL,
            capabilityId = "7".repeat(64),
            attemptId = ATTEMPT_ID,
            requesterRole = P2pNatRole.CLIENT,
            candidateOwnerRole = P2pNatRole.CLIENT,
            maximumCandidateBytes = P2pNatContract.MAX_CANDIDATE_BATCH_BYTES.toULong(),
            singleUseNonce = "9".repeat(64),
            issuedAtMs = now - 50uL,
            notBeforeMs = now - 10uL,
            expiresAtMs = now,
            authority = fixture.authority,
            candidateBatch = fixture.clientBatch,
            endpointOperationProof = expiringProof,
            signingPublicKey = publicKey(fixture.publishKey),
            signingPrivateKey = fixture.publishKey,
        )
        assertC1Error(ProductionC1Error.EXPIRED) {
            ProductionC1CandidateVerifier.verifyCapability(
                expiredCapability,
                P2pNatCanonicalCodec.encode(fixture.clientBatch),
                expiringProof,
                fixture.context,
                fixture.authority,
                fixture.verifiedKeyset,
                now,
            )
        }

        val revoked = ProductionC1DelegatedKey(
            1uL,
            keyId(publicKey(fixture.publishKey)),
            ProductionC1DelegatedKeyPurpose.CANDIDATE_PUBLISH,
            now - 1_000uL,
            now + 400_000uL,
            revokedAtMs = now,
            publicKeyX963 = x963(publicKey(fixture.publishKey)),
        )
        val revokedKeyset = verifiedKeyset(fixture.rootKey, listOf(revoked))
        assertC1Error(ProductionC1Error.KEY_REVOKED) {
            ProductionC1CandidateVerifier.verifyCapability(
                publish.capability,
                P2pNatCanonicalCodec.encode(fixture.clientBatch),
                publish.endpointOperationProof,
                fixture.context,
                fixture.authority,
                revokedKeyset,
                now,
            )
        }
    }

    @Test
    fun canonicalDecodersRejectOrderTrailingHighSAndBoundFieldMutations() {
        val fixture = fixture()
        val publish = signedAndVerified(
            fixture,
            ProductionC1CandidateOperation.PUBLISH,
            P2pNatRole.CLIENT,
            P2pNatRole.CLIENT,
            fixture.publishKey,
            "4".repeat(64),
            "5".repeat(64),
            "6".repeat(64),
        )
        val proofBytes = publish.endpointOperationProof.canonicalBytes()
        val capabilityBytes = publish.capability.canonicalBytes()

        assertC1Error(ProductionC1Error.MALFORMED_CANONICAL) {
            ProductionC1EndpointOperationProof.decode(proofBytes.copyOf().also { it[6] = 2 })
        }
        assertC1Error(ProductionC1Error.MALFORMED_CANONICAL) {
            ProductionC1CandidateCapability.decode(capabilityBytes + byteArrayOf(0))
        }
        assertC1Error(ProductionC1Error.LIMIT_EXCEEDED) {
            ProductionC1CandidateCapability.decode(
                capabilityBytes + ByteArray(
                    ProductionC1CandidateCapabilityContract.MAXIMUM_CAPABILITY_BYTES,
                ),
            )
        }
        assertC1Error(ProductionC1Error.HIGH_S) {
            ProductionC1EndpointOperationProof.decode(
                replaceTLVField(proofBytes, 24, makeHighS(publish.endpointOperationProof.endpointSignature)),
            )
        }
        assertC1Error(ProductionC1Error.HIGH_S) {
            ProductionC1CandidateCapability.decode(
                replaceTLVField(capabilityBytes, 34, makeHighS(publish.capability.serviceSignature)),
            )
        }

        val reboundProof = ProductionC1EndpointOperationProof.decode(
            replaceTLVField(
                proofBytes,
                15,
                ProductionC1InternalBridge.ascii("f".repeat(64)),
            ),
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.ROLE_MISMATCH) {
            ProductionC1CandidateVerifier.verifyCapability(
                publish.capability,
                P2pNatCanonicalCodec.encode(fixture.clientBatch),
                reboundProof,
                fixture.context,
                fixture.authority,
                fixture.verifiedKeyset,
                now,
            )
        }

        val reboundCapability = ProductionC1CandidateCapability.decode(
            replaceTLVField(
                capabilityBytes,
                23,
                ProductionC1InternalBridge.be(publish.capability.candidateBatchByteCount + 1u),
            ),
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.BATCH_MISMATCH) {
            ProductionC1CandidateVerifier.verifyCapability(
                reboundCapability,
                P2pNatCanonicalCodec.encode(fixture.clientBatch),
                publish.endpointOperationProof,
                fixture.context,
                fixture.authority,
                fixture.verifiedKeyset,
                now,
            )
        }
    }

    @Test
    fun byteArraysAndCanonicalBatchAreDefensivelyCopiedWithContentEquality() {
        val fixture = fixture()
        val batchInput = P2pNatCanonicalCodec.encode(fixture.clientBatch)
        val proof = proof(
            fixture,
            ProductionC1CandidateOperation.PUBLISH,
            P2pNatRole.CLIENT,
            P2pNatRole.CLIENT,
            "4".repeat(64),
            "5".repeat(64),
            "6".repeat(64),
            fixture.clientIdentityKey,
        )
        val capability = capability(
            fixture,
            proof,
            ProductionC1CandidateOperation.PUBLISH,
            P2pNatRole.CLIENT,
            P2pNatRole.CLIENT,
            fixture.publishKey,
            "4".repeat(64),
            "6".repeat(64),
        )
        val verified = ProductionC1CandidateVerifier.verifyCapability(
            capability,
            batchInput,
            proof,
            fixture.context,
            fixture.authority,
            fixture.verifiedKeyset,
            now,
        )
        val verifiedAgain = ProductionC1CandidateVerifier.verifyCapability(
            ProductionC1CandidateCapability.decode(capability.canonicalBytes()),
            batchInput.copyOf(),
            ProductionC1EndpointOperationProof.decode(proof.canonicalBytes()),
            fixture.context,
            fixture.authority,
            fixture.verifiedKeyset,
            now,
        )
        assertEquals(verified, verifiedAgain)
        assertEquals(verified.hashCode(), verifiedAgain.hashCode())

        batchInput.fill(0)
        assertArrayEquals(
            P2pNatCanonicalCodec.encode(fixture.clientBatch),
            verified.canonicalCandidateBatch,
        )
        verified.canonicalCandidateBatch.fill(0)
        assertArrayEquals(
            P2pNatCanonicalCodec.encode(fixture.clientBatch),
            verified.canonicalCandidateBatch,
        )
        @Suppress("UNCHECKED_CAST")
        (verified.candidateBatch.candidates as MutableList<P2pCandidate>).clear()
        assertEquals(1, verified.candidateBatch.candidates.size)

        val proofPublicKey = proof.requesterPublicKeyX963
        val proofSignature = proof.endpointSignature
        val capabilitySignature = capability.serviceSignature
        proofPublicKey.fill(0)
        proofSignature.fill(0)
        capabilitySignature.fill(0)
        assertTrue(proof.requesterPublicKeyX963.any { it != 0.toByte() })
        assertTrue(proof.endpointSignature.any { it != 0.toByte() })
        assertTrue(capability.serviceSignature.any { it != 0.toByte() })
        assertEquals(proof, ProductionC1EndpointOperationProof.decode(proof.canonicalBytes()))
        assertEquals(capability, ProductionC1CandidateCapability.decode(capability.canonicalBytes()))
    }

    private data class Fixture(
        val rootKey: PrivateKey,
        val clientIdentityKey: PrivateKey,
        val runtimeIdentityKey: PrivateKey,
        val publishKey: PrivateKey,
        val fetchKey: PrivateKey,
        val authority: ProductionPairAuthorityState,
        val context: ProductionC1PreauthorizationSessionContext,
        val clientBatch: CandidateBatch,
        val runtimeBatch: CandidateBatch,
        val verifiedKeyset: VerifiedProductionC1ServiceKeyset,
    )

    private data class BilateralTuple(
        val clientPublish: VerifiedProductionC1CandidateCapability,
        val runtimeFetchClient: VerifiedProductionC1CandidateCapability,
        val runtimePublish: VerifiedProductionC1CandidateCapability,
        val clientFetchRuntime: VerifiedProductionC1CandidateCapability,
    ) {
        val all: List<VerifiedProductionC1CandidateCapability>
            get() = listOf(clientPublish, runtimeFetchClient, runtimePublish, clientFetchRuntime)
    }

    private fun fixture(): Fixture {
        val root = privateKey(101)
        val clientIdentity = privateKey(102)
        val runtimeIdentity = privateKey(103)
        val publish = privateKey(104)
        val fetch = privateKey(105)
        val authority = authority(clientIdentity, runtimeIdentity)
        return Fixture(
            root,
            clientIdentity,
            runtimeIdentity,
            publish,
            fetch,
            authority,
            context(authority),
            CandidateBatch(
                sessionId = SESSION_ID,
                generation = authority.generation,
                sequence = 1uL,
                expiresAtMillis = now + 300_000uL,
                senderRole = P2pNatRole.CLIENT,
                candidates = listOf(candidate()),
            ),
            CandidateBatch(
                sessionId = SESSION_ID,
                generation = authority.generation,
                sequence = 2uL,
                expiresAtMillis = now + 300_000uL,
                senderRole = P2pNatRole.RUNTIME,
                candidates = listOf(candidate(addressLastByte = 9)),
            ),
            verifiedKeyset(
                root,
                listOf(
                    delegated(publish, ProductionC1DelegatedKeyPurpose.CANDIDATE_PUBLISH),
                    delegated(fetch, ProductionC1DelegatedKeyPurpose.CANDIDATE_FETCH),
                ).sortedBy { it.keyId },
            ),
        )
    }

    private fun signedAndVerified(
        fixture: Fixture,
        operation: ProductionC1CandidateOperation,
        requester: P2pNatRole,
        owner: P2pNatRole,
        serviceKey: PrivateKey,
        capabilityId: String,
        proofId: String,
        nonce: String,
        batch: CandidateBatch = fixture.clientBatch,
        securityContext: ProductionC1PreauthorizationSessionContext = fixture.context,
    ): VerifiedProductionC1CandidateCapability {
        val identityKey = if (requester == P2pNatRole.CLIENT) {
            fixture.clientIdentityKey
        } else {
            fixture.runtimeIdentityKey
        }
        val proof = proof(
            fixture,
            operation,
            requester,
            owner,
            capabilityId,
            proofId,
            nonce,
            identityKey,
            batch,
            securityContext,
        )
        val capability = capability(
            fixture,
            proof,
            operation,
            requester,
            owner,
            serviceKey,
            capabilityId,
            nonce,
            batch,
        )
        return ProductionC1CandidateVerifier.verifyCapability(
            capability,
            P2pNatCanonicalCodec.encode(batch),
            proof,
            securityContext,
            fixture.authority,
            fixture.verifiedKeyset,
            now,
        )
    }

    private fun bilateralTuple(
        fixture: Fixture,
        capabilityIds: List<String> = listOf("4", "8", "c", "f").map { it.repeat(64) },
        proofIds: List<String> = listOf("5", "9", "d", "0").map { it.repeat(64) },
        nonces: List<String> = listOf("6", "b", "e", "1").map { it.repeat(64) },
        clientPublishBatch: CandidateBatch = fixture.clientBatch,
        runtimeFetchClientBatch: CandidateBatch = fixture.clientBatch,
        runtimePublishBatch: CandidateBatch = fixture.runtimeBatch,
        clientFetchRuntimeBatch: CandidateBatch = fixture.runtimeBatch,
        runtimePublishContext: ProductionC1PreauthorizationSessionContext = fixture.context,
    ): BilateralTuple {
        require(capabilityIds.size == 4 && proofIds.size == 4 && nonces.size == 4)
        return BilateralTuple(
            clientPublish = signedAndVerified(
                fixture = fixture,
                operation = ProductionC1CandidateOperation.PUBLISH,
                requester = P2pNatRole.CLIENT,
                owner = P2pNatRole.CLIENT,
                serviceKey = fixture.publishKey,
                capabilityId = capabilityIds[0],
                proofId = proofIds[0],
                nonce = nonces[0],
                batch = clientPublishBatch,
            ),
            runtimeFetchClient = signedAndVerified(
                fixture = fixture,
                operation = ProductionC1CandidateOperation.FETCH,
                requester = P2pNatRole.RUNTIME,
                owner = P2pNatRole.CLIENT,
                serviceKey = fixture.fetchKey,
                capabilityId = capabilityIds[1],
                proofId = proofIds[1],
                nonce = nonces[1],
                batch = runtimeFetchClientBatch,
            ),
            runtimePublish = signedAndVerified(
                fixture = fixture,
                operation = ProductionC1CandidateOperation.PUBLISH,
                requester = P2pNatRole.RUNTIME,
                owner = P2pNatRole.RUNTIME,
                serviceKey = fixture.publishKey,
                capabilityId = capabilityIds[2],
                proofId = proofIds[2],
                nonce = nonces[2],
                batch = runtimePublishBatch,
                securityContext = runtimePublishContext,
            ),
            clientFetchRuntime = signedAndVerified(
                fixture = fixture,
                operation = ProductionC1CandidateOperation.FETCH,
                requester = P2pNatRole.CLIENT,
                owner = P2pNatRole.RUNTIME,
                serviceKey = fixture.fetchKey,
                capabilityId = capabilityIds[3],
                proofId = proofIds[3],
                nonce = nonces[3],
                batch = clientFetchRuntimeBatch,
            ),
        )
    }

    private fun verifyBilateral(
        tuple: BilateralTuple,
        fixture: Fixture,
        nowMs: ULong = now,
    ): VerifiedProductionC1BilateralCandidateCapabilities =
        ProductionC1CandidateVerifier.verifyBilateral(
            tuple.clientPublish,
            tuple.runtimeFetchClient,
            tuple.runtimePublish,
            tuple.clientFetchRuntime,
            fixture.authority,
            nowMs,
        )

    private fun repeatedHex(vararg values: String): List<String> =
        values.map { it.repeat(64) }

    private fun expectedBilateralDigest(
        domain: String,
        clientDigest: String,
        runtimeDigest: String,
    ): String {
        var claims = byteArrayOf()
        listOf("client" to clientDigest, "runtime" to runtimeDigest).forEach { (role, digest) ->
            val roleBytes = role.toByteArray(Charsets.US_ASCII)
            val digestBytes = digest.chunked(2).map { it.toInt(16).toByte() }.toByteArray()
            claims += ByteBuffer.allocate(4).putInt(roleBytes.size).array()
            claims += roleBytes
            claims += ByteBuffer.allocate(4).putInt(digestBytes.size).array()
            claims += digestBytes
        }
        val domainBytes = domain.toByteArray(Charsets.US_ASCII)
        val transcript = domainBytes +
            byteArrayOf(0) +
            ByteBuffer.allocate(4).putInt(claims.size).array() +
            claims
        return MessageDigest.getInstance("SHA-256").digest(transcript).hex()
    }

    private fun proof(
        fixture: Fixture,
        operation: ProductionC1CandidateOperation,
        requester: P2pNatRole,
        owner: P2pNatRole,
        capabilityId: String,
        proofId: String,
        nonce: String,
        identityKey: PrivateKey,
        batch: CandidateBatch = fixture.clientBatch,
        securityContext: ProductionC1PreauthorizationSessionContext = fixture.context,
    ): ProductionC1EndpointOperationProof = ProductionC1EndpointOperationProof.signed(
        requesterRole = requester,
        operation = operation,
        candidateOwnerRole = owner,
        proofId = proofId,
        attemptId = ATTEMPT_ID,
        capabilityId = capabilityId,
        candidateBatch = batch,
        singleUseNonce = nonce,
        securityContext = securityContext,
        serviceAudienceId = serviceId,
        authority = fixture.authority,
        issuedAtMs = now - 100uL,
        notBeforeMs = now - 50uL,
        expiresAtMs = now + 200_000uL,
        requesterIdentityPublicKeyX963 = x963(publicKey(identityKey)),
        requesterIdentityPrivateKey = identityKey,
    )

    private fun capability(
        fixture: Fixture,
        proof: ProductionC1EndpointOperationProof,
        operation: ProductionC1CandidateOperation,
        requester: P2pNatRole,
        owner: P2pNatRole,
        serviceKey: PrivateKey,
        capabilityId: String,
        nonce: String,
        batch: CandidateBatch = fixture.clientBatch,
    ): ProductionC1CandidateCapability = ProductionC1CandidateCapability.signed(
        operation = operation,
        serviceIdDigest = serviceId,
        keysetVersion = 1uL,
        capabilityId = capabilityId,
        attemptId = ATTEMPT_ID,
        requesterRole = requester,
        candidateOwnerRole = owner,
        maximumCandidateBytes = P2pNatContract.MAX_CANDIDATE_BATCH_BYTES.toULong(),
        singleUseNonce = nonce,
        issuedAtMs = now - 50uL,
        notBeforeMs = now - 10uL,
        expiresAtMs = now + 100_000uL,
        authority = fixture.authority,
        candidateBatch = batch,
        endpointOperationProof = proof,
        signingPublicKey = publicKey(serviceKey),
        signingPrivateKey = serviceKey,
    )

    private fun authority(
        clientIdentityKey: PrivateKey,
        runtimeIdentityKey: PrivateKey,
        serviceConfigVersion: ULong = 1uL,
    ): ProductionPairAuthorityState = ProductionPairAuthorityState(
        pairBindingDigest = "d".repeat(64),
        pairEpoch = 1uL,
        clientIdentityFingerprint = keyId(publicKey(clientIdentityKey)),
        runtimeIdentityFingerprint = keyId(publicKey(runtimeIdentityKey)),
        generation = 1uL,
        serviceConfigVersion = serviceConfigVersion,
        keysetVersion = 1uL,
        revocationCounter = 0uL,
        protocolFloor = 1u,
        status = ProductionPairAuthorityStatus.ACTIVE,
        transitionId = "1".repeat(64),
        transitionRequestDigest = "2".repeat(64),
        acceptedReceiptDigest = "3".repeat(64),
        authorityRevision = 1uL,
    )

    private fun context(
        authority: ProductionPairAuthorityState,
        runtimeNonce: String = "c".repeat(32),
    ): ProductionC1PreauthorizationSessionContext = ProductionC1PreauthorizationSessionContext(
        sessionId = SESSION_ID,
        pairBindingDigest = authority.pairBindingDigest,
        pairEpoch = authority.pairEpoch,
        clientIdentityFingerprint = authority.clientIdentityFingerprint,
        runtimeIdentityFingerprint = authority.runtimeIdentityFingerprint,
        clientEphemeralPublicKey = x963(publicKey(privateKey(106))),
        runtimeEphemeralPublicKey = x963(publicKey(privateKey(107))),
        clientNonce = "b".repeat(32),
        runtimeNonce = runtimeNonce,
        generation = authority.generation,
        serviceConfigVersion = authority.serviceConfigVersion,
        keysetVersion = authority.keysetVersion,
        revocationCounter = authority.revocationCounter,
        routeKind = ProductionC1RouteKind.P2P_DIRECT,
    )

    private fun candidate(addressLastByte: Int = 8): P2pCandidate = P2pCandidate(
        kind = CandidateKind.HOST,
        family = AddressFamily.IPV4,
        port = 43_170,
        priority = 100u,
        foundation = ByteArray(8) { 1 },
        address = byteArrayOf(8, 8, 8, addressLastByte.toByte()),
    )

    private fun delegated(
        key: PrivateKey,
        purpose: ProductionC1DelegatedKeyPurpose,
    ): ProductionC1DelegatedKey {
        val publicKey = publicKey(key)
        return ProductionC1DelegatedKey(
            1uL,
            keyId(publicKey),
            purpose,
            now - 1_000uL,
            now + 400_000uL,
            publicKeyX963 = x963(publicKey),
        )
    }

    private fun verifiedKeyset(
        root: PrivateKey,
        keys: List<ProductionC1DelegatedKey>,
    ): VerifiedProductionC1ServiceKeyset {
        val keyset = ProductionC1ServiceKeyset.signed(
            serviceId,
            1uL,
            null,
            now - 1_000uL,
            now + 500_000uL,
            keys.sortedBy { it.keyId },
            publicKey(root),
            root,
        )
        return ProductionC1Verifier.verifyServiceKeyset(
            keyset,
            serviceId,
            publicKey(root),
            1uL,
            nowMs = now,
        )
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

    private fun tags(data: ByteArray): List<Int> {
        val result = mutableListOf<Int>()
        var cursor = 6
        while (cursor < data.size) {
            result += data[cursor].toInt() and 0xff
            val size = ByteBuffer.wrap(data, cursor + 1, 4).int
            cursor += 5 + size
        }
        return result
    }

    private fun assertTranscriptDomain(transcript: ByteArray, domain: String) {
        val expected = domain.toByteArray(Charsets.UTF_8)
        assertArrayEquals(expected, transcript.copyOfRange(0, expected.size))
        assertEquals(0, transcript[expected.size].toInt())
    }

    private fun replaceTLVField(data: ByteArray, tagToReplace: Int, replacement: ByteArray): ByteArray {
        var cursor = 6
        var result = data.copyOfRange(0, cursor)
        while (cursor < data.size) {
            val tag = data[cursor].toInt() and 0xff
            val size = ByteBuffer.wrap(data, cursor + 1, 4).int
            val value = if (tag == tagToReplace) {
                replacement
            } else {
                data.copyOfRange(cursor + 5, cursor + 5 + size)
            }
            result += byteArrayOf(tag.toByte())
            result += ByteBuffer.allocate(4).putInt(value.size).array()
            result += value
            cursor += 5 + size
        }
        return result
    }

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

    private fun keyId(publicKey: PublicKey): String =
        MessageDigest.getInstance("SHA-256").digest(publicKey.encoded).hex()

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
            "7777777777777777777777777777777777777777777777777777777777777777"
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
