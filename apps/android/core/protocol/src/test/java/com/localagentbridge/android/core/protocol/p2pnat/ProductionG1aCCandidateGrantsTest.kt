package com.localagentbridge.android.core.protocol.p2pnat

import java.nio.ByteBuffer
import java.security.KeyPair
import java.security.KeyPairGenerator
import java.security.MessageDigest
import java.security.PublicKey
import java.security.interfaces.ECPublicKey
import java.security.spec.ECGenParameterSpec
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

class ProductionG1aCCandidateGrantsTest {
    private val now = 1_000_000uL
    private val serviceId = "a".repeat(64)

    @Test
    fun object25And26RoundTripOnlyAfterExactFourOperationChain() {
        val fixture = fixture()
        val committed = commitAll(fixture)
        val grant = ProductionC1CandidateVerifier.deriveGrantEvidence(
            fixture.plan,
            fixture.authorizations,
            committed,
            P2pNatRole.CLIENT,
            fixture.authority,
            now,
        )

        val evidenceBytes = grant.evidence.canonicalBytes()
        assertEquals(25, evidenceBytes[4].toInt() and 0xff)
        assertEquals((1..34).toList(), tags(evidenceBytes))
        assertTrue(evidenceBytes.size <= ProductionC1CandidateCapabilityContract.MAXIMUM_GRANT_EVIDENCE_BYTES)
        assertEquals(grant.evidence, ProductionC1P2PGrantEvidence.decode(evidenceBytes))
        assertEquals(ProductionC1P2PGrantEvidence.OPERATION_ORDER, textField(evidenceBytes, 17))
        assertEquals(4, grant.evidence.operationCapabilityDigests.size)
        assertEquals(4, grant.evidence.operationAuthorizationDigests.size)
        assertEquals(4, grant.evidence.operationReceiptDigests.size)
        assertEquals(4, grant.evidence.operationCapabilityDigests.toSet().size)
        assertEquals(4, grant.evidence.operationAuthorizationDigests.toSet().size)
        assertEquals(4, grant.evidence.operationReceiptDigests.toSet().size)
        assertEquals(
            digest(ProductionSecureSessionCodec.encode(fixture.authorizations.finalP2PDirect)),
            grant.evidence.finalRouteAuthorizationDigest,
        )

        val authorization = grant.grantAuthorization.authorization
        val authorizationBytes = authorization.canonicalBytes()
        assertEquals(26, authorizationBytes[4].toInt() and 0xff)
        assertEquals((1..18).toList(), tags(authorizationBytes))
        assertTrue(
            authorizationBytes.size <=
                ProductionC1CandidateCapabilityContract.MAXIMUM_GRANT_AUTHORIZATION_BYTES,
        )
        val decodedAuthorization = ProductionC1P2PGrantAuthorization.decode(authorizationBytes)
        assertEquals(authorization, decodedAuthorization)
        assertEquals(grant.evidence.digestHex(), decodedAuthorization.grantEvidenceDigest)
        assertEquals(authorization.digestHex(), grant.grantAuthorization.digestHex)
        assertEquals(
            authorization,
            ProductionC1CandidateVerifier.makeGrantAuthorization(grant.evidence),
        )
        assertEquals(
            grant.grantAuthorization,
            ProductionC1CandidateVerifier.verifyGrantAuthorization(
                decodedAuthorization,
                grant.evidence,
                fixture.plan,
                P2pNatRole.RUNTIME,
            ),
        )
        assertEquals(
            grant,
            ProductionC1CandidateVerifier.verifyGrantEvidence(
                ProductionC1P2PGrantEvidence.decode(evidenceBytes),
                fixture.plan,
                fixture.authorizations,
                committed,
                P2pNatRole.RUNTIME,
                fixture.authority,
                now,
            ),
        )

        val reorderedPackedCapabilities = field(evidenceBytes, 18)
            .asList()
            .chunked(32)
            .reversed()
            .flatten()
            .toByteArray()
        val reordered = ProductionC1P2PGrantEvidence.decode(
            replaceTLVField(evidenceBytes, 18, reorderedPackedCapabilities),
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.ROUTE_MISMATCH) {
            ProductionC1CandidateVerifier.verifyGrantEvidence(
                reordered,
                fixture.plan,
                fixture.authorizations,
                committed,
                P2pNatRole.CLIENT,
                fixture.authority,
                now,
            )
        }
    }

    @Test
    fun grantDerivationRejectsMissingDuplicateOutOfOrderBrokenChainAndFinalRoute() {
        val fixture = fixture()
        val committed = commitAll(fixture)
        assertCandidateError(ProductionC1CandidateCapabilityError.QUOTA_EXCEEDED) {
            ProductionC1CandidateVerifier.deriveGrantEvidence(
                fixture.plan,
                fixture.authorizations,
                committed.take(3),
                P2pNatRole.CLIENT,
                fixture.authority,
                now,
            )
        }
        val duplicate = committed.toMutableList().also { it[3] = it[0] }
        assertCandidateError(ProductionC1CandidateCapabilityError.REQUEST_CONFLICT) {
            ProductionC1CandidateVerifier.deriveGrantEvidence(
                fixture.plan,
                fixture.authorizations,
                duplicate,
                P2pNatRole.CLIENT,
                fixture.authority,
                now,
            )
        }
        val outOfOrder = committed.toMutableList().also { it[0] = committed[1]; it[1] = committed[0] }
        assertCandidateError(ProductionC1CandidateCapabilityError.AUTHORITY_MISMATCH) {
            ProductionC1CandidateVerifier.deriveGrantEvidence(
                fixture.plan,
                fixture.authorizations,
                outOfOrder,
                P2pNatRole.CLIENT,
                fixture.authority,
                now,
            )
        }
        val otherChain = commitAll(fixture, 10uL)
        val brokenChain = committed.toMutableList().also { it[0] = otherChain[0] }
        assertCandidateError(ProductionC1CandidateCapabilityError.REVISION_MISMATCH) {
            ProductionC1CandidateVerifier.deriveGrantEvidence(
                fixture.plan,
                fixture.authorizations,
                brokenChain,
                P2pNatRole.CLIENT,
                fixture.authority,
                now,
            )
        }
        val wrongFinal = ProductionC1BilateralRouteAuthorizations(
            fixture.authorizations.clientPublish,
            fixture.authorizations.runtimeFetchClient,
            fixture.authorizations.runtimePublish,
            fixture.authorizations.clientFetchRuntime,
            P2pDirectRouteAuthorization(
                fixture.authority.pairBindingDigest,
                fixture.authority.pairEpoch,
                fixture.authority.generation,
                "0".repeat(64),
                fixture.plan.pathValidationReceiptDigest,
                fixture.bilateral.bilateralPublishDigest,
                fixture.bilateral.bilateralFetchDigest,
            ),
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.ROUTE_MISMATCH) {
            ProductionC1CandidateVerifier.deriveGrantEvidence(
                fixture.plan,
                wrongFinal,
                committed,
                P2pNatRole.CLIENT,
                fixture.authority,
                now,
            )
        }
    }

    @Test
    fun candidatePlanUsesPublicOnlyPolicyAndClosesEveryGenericP2PAuthorityPath() {
        assertTrue(ProductionC1PublicOnlyV1Policy.allows(byteArrayOf(8, 8, 4, 4), 50_000))
        assertFalse(ProductionC1PublicOnlyV1Policy.allows(byteArrayOf(127, 0, 0, 1), 50_000))
        assertFalse(ProductionC1PublicOnlyV1Policy.allows(byteArrayOf(100, 64, 0, 1), 50_000))
        assertFalse(ProductionC1PublicOnlyV1Policy.allows(byteArrayOf(8, 8, 4, 4), 443))
        assertFalse(ProductionC1PublicOnlyV1Policy.allows(byteArrayOf(8, 8, 4, 4), 65_536))
        assertFalse(ProductionC1PublicOnlyV1Policy.allows(byteArrayOf(8, 8, 4, 4), Int.MAX_VALUE))
        assertFalse(ProductionC1PublicOnlyV1Policy.allows(ByteArray(16), 50_000))

        val fixture = fixture()
        assertEquals(
            ProductionC1CandidateVerifier.selectedCandidatePairDigest(
                fixture.plan.selectedClientCandidate,
                fixture.plan.selectedRuntimeCandidate,
            ),
            fixture.plan.pathValidationReceipt.candidatePairDigest,
        )
        assertC1Error(ProductionC1Error.ROUTE_MISMATCH) {
            ProductionC1Verifier.verifyRoutePlan(
                fixture.claims,
                fixture.routeCapability,
                fixture.context,
                fixture.authority,
                fixture.verifiedKeyset,
                now,
            )
        }
        val basePlan = ProductionC1Verifier.verifyCandidateP2PRoutePlanBase(
            fixture.claims,
            fixture.routeCapability,
            fixture.context,
            fixture.authority,
            fixture.verifiedKeyset,
            now,
        )
        val baseAuthorization = ProductionC1Verifier.makeCandidateP2PRouteAuthorizationBase(basePlan, now)
        assertEquals(ProductionC1RouteKind.P2P_DIRECT, baseAuthorization.kind)
        assertC1Error(ProductionC1Error.ROUTE_MISMATCH) {
            ProductionC1Verifier.makeRouteAuthorization(basePlan, now)
        }
        assertC1Error(ProductionC1Error.ROUTE_MISMATCH) {
            ProductionC1Verifier.verifyConnectorInput(basePlan, "direct-01", "nonce-01", ByteArray(32), now)
        }
        assertC1Error(ProductionC1Error.STATE_MISMATCH) {
            VerifiedProductionC1ConnectorInput(
                "direct-01",
                "nonce-01",
                ByteArray(32),
                fixture.claims.connector,
                "0".repeat(64),
                Any(),
            )
        }
    }

    @Test
    fun candidatePlanRejectsSameVersionRouteKeysetFork() {
        val fixture = fixture()
        val exact = ProductionC1CandidateVerifier.verifyP2PDirectPlan(
            fixture.claims,
            fixture.routeCapability,
            fixture.context,
            fixture.bilateral,
            fixture.plan.selectedClientCandidate,
            fixture.plan.selectedRuntimeCandidate,
            P2pNatCanonicalCodec.encode(fixture.plan.pathValidationReceipt),
            fixture.authority,
            fixture.verifiedKeyset,
            nowMs = now,
        )
        assertEquals(fixture.claims, exact.claims)
        assertTrue(
            fixture.verifiedKeyset.keyset.canonicalBytes().contentEquals(
                fixture.bilateral.clientPublish.verifiedKeyset.keyset.canonicalBytes(),
            ),
        )

        val verifiedFork = sameVersionRouteFork(fixture)
        assertEquals(
            fixture.verifiedKeyset.keyset.serviceIdDigest,
            verifiedFork.keyset.serviceIdDigest,
        )
        assertEquals(
            fixture.verifiedKeyset.keyset.keysetVersion,
            verifiedFork.keyset.keysetVersion,
        )
        assertFalse(
            verifiedFork.keyset.canonicalBytes().contentEquals(
                fixture.verifiedKeyset.keyset.canonicalBytes(),
            ),
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.AUTHORITY_MISMATCH) {
            ProductionC1CandidateVerifier.verifyP2PDirectPlan(
                fixture.claims,
                fixture.routeCapability,
                fixture.context,
                fixture.bilateral,
                fixture.plan.selectedClientCandidate,
                fixture.plan.selectedRuntimeCandidate,
                P2pNatCanonicalCodec.encode(fixture.plan.pathValidationReceipt),
                fixture.authority,
                verifiedFork,
                nowMs = now,
            )
        }
    }

    @Test
    fun candidatePlanRederivesAndRejectsForgedBilateralWrappers() {
        val fixture = fixture()
        fun assertRejected(bilateral: VerifiedProductionC1BilateralCandidateCapabilities) {
            assertCandidateError(ProductionC1CandidateCapabilityError.AUTHORITY_MISMATCH) {
                ProductionC1CandidateVerifier.verifyP2PDirectPlan(
                    fixture.claims,
                    fixture.routeCapability,
                    fixture.context,
                    bilateral,
                    fixture.plan.selectedClientCandidate,
                    fixture.plan.selectedRuntimeCandidate,
                    P2pNatCanonicalCodec.encode(fixture.plan.pathValidationReceipt),
                    fixture.authority,
                    fixture.verifiedKeyset,
                    nowMs = now,
                )
            }
        }

        assertRejected(
            VerifiedProductionC1BilateralCandidateCapabilities(
                fixture.bilateral.clientPublish,
                fixture.bilateral.runtimeFetchClient,
                fixture.bilateral.runtimePublish,
                fixture.bilateral.clientFetchRuntime,
                "0".repeat(64),
                fixture.bilateral.bilateralFetchDigest,
            ),
        )
        assertRejected(
            VerifiedProductionC1BilateralCandidateCapabilities(
                fixture.bilateral.runtimePublish,
                fixture.bilateral.runtimeFetchClient,
                fixture.bilateral.clientPublish,
                fixture.bilateral.clientFetchRuntime,
                fixture.bilateral.bilateralPublishDigest,
                fixture.bilateral.bilateralFetchDigest,
            ),
        )

        val fork = sameVersionRouteFork(fixture)
        val originalClientPublish = fixture.bilateral.clientPublish
        val forkClientPublish = ProductionC1CandidateVerifier.verifyCapability(
            originalClientPublish.capability,
            originalClientPublish.canonicalCandidateBatch,
            originalClientPublish.endpointOperationProof,
            originalClientPublish.securityContext,
            fixture.authority,
            fork,
            now,
        )
        assertRejected(
            VerifiedProductionC1BilateralCandidateCapabilities(
                forkClientPublish,
                fixture.bilateral.runtimeFetchClient,
                fixture.bilateral.runtimePublish,
                fixture.bilateral.clientFetchRuntime,
                fixture.bilateral.bilateralPublishDigest,
                fixture.bilateral.bilateralFetchDigest,
            ),
        )
    }

    private data class Fixture(
        val rootKey: KeyPair,
        val signingKey: KeyPair,
        val authority: ProductionPairAuthorityState,
        val verifiedKeyset: VerifiedProductionC1ServiceKeyset,
        val context: ProductionC1PreauthorizationSessionContext,
        val bilateral: VerifiedProductionC1BilateralCandidateCapabilities,
        val claims: ProductionC1RoutePlanClaims,
        val routeCapability: ProductionC1RouteCapability,
        val plan: VerifiedProductionC1CandidateP2PPlan,
        val authorizations: ProductionC1BilateralRouteAuthorizations,
    ) {
        val capabilities: List<VerifiedProductionC1CandidateCapability>
            get() = bilateral.all
    }

    private fun fixture(): Fixture {
        val root = keyPair()
        val signing = keyPair()
        val allPurposes = candidateAndRoutePurposes()
        val delegated = ProductionC1DelegatedKey(
            1uL,
            ProductionC1InternalBridge.keyId(signing.public),
            allPurposes,
            now - 1_000uL,
            now + 100_000uL,
            publicKeyX963 = x963(signing.public),
        )
        val keyset = ProductionC1ServiceKeyset.signed(
            serviceId,
            1uL,
            null,
            now - 1_000uL,
            now + 100_000uL,
            listOf(delegated),
            root.public,
            root.private,
        )
        val verifiedKeyset = ProductionC1Verifier.verifyServiceKeyset(
            keyset,
            serviceId,
            root.public,
            1uL,
            nowMs = now,
        )
        val clientIdentity = keyPair()
        val runtimeIdentity = keyPair()
        val authority = ProductionPairAuthorityState(
            "d".repeat(64),
            1uL,
            ProductionC1InternalBridge.keyId(clientIdentity.public),
            ProductionC1InternalBridge.keyId(runtimeIdentity.public),
            1uL,
            1uL,
            1uL,
            0uL,
            1u,
            ProductionPairAuthorityStatus.ACTIVE,
            "1".repeat(64),
            "2".repeat(64),
            "e".repeat(64),
            1uL,
        )
        val context = ProductionC1PreauthorizationSessionContext(
            SESSION_ID,
            authority.pairBindingDigest,
            authority.pairEpoch,
            authority.clientIdentityFingerprint,
            authority.runtimeIdentityFingerprint,
            x963(keyPair().public),
            x963(keyPair().public),
            "c".repeat(32),
            "d".repeat(32),
            authority.generation,
            authority.serviceConfigVersion,
            authority.keysetVersion,
            authority.revocationCounter,
            ProductionC1RouteKind.P2P_DIRECT,
        )
        val clientBatch = batch(P2pNatRole.CLIENT, 1uL, byteArrayOf(1, 1, 1, 1))
        val runtimeBatch = batch(P2pNatRole.RUNTIME, 2uL, byteArrayOf(8, 8, 4, 4))

        fun capability(
            operation: ProductionC1CandidateOperation,
            requester: P2pNatRole,
            owner: P2pNatRole,
            proofCharacter: String,
            capabilityCharacter: String,
            nonceCharacter: String,
            candidateBatch: CandidateBatch,
        ): VerifiedProductionC1CandidateCapability {
            val identity = if (requester == P2pNatRole.CLIENT) clientIdentity else runtimeIdentity
            val proof = ProductionC1EndpointOperationProof.signed(
                requesterRole = requester,
                operation = operation,
                candidateOwnerRole = owner,
                proofId = proofCharacter.repeat(64),
                attemptId = ATTEMPT_ID,
                capabilityId = capabilityCharacter.repeat(64),
                candidateBatch = candidateBatch,
                singleUseNonce = nonceCharacter.repeat(64),
                securityContext = context,
                serviceAudienceId = serviceId,
                authority = authority,
                issuedAtMs = now - 200uL,
                notBeforeMs = now - 10uL,
                expiresAtMs = now + 20_000uL,
                requesterIdentityPublicKeyX963 = x963(identity.public),
                requesterIdentityPrivateKey = identity.private,
            )
            val value = ProductionC1CandidateCapability.signed(
                operation = operation,
                serviceIdDigest = serviceId,
                keysetVersion = 1uL,
                capabilityId = capabilityCharacter.repeat(64),
                attemptId = ATTEMPT_ID,
                requesterRole = requester,
                candidateOwnerRole = owner,
                maximumCandidateBytes = P2pNatContract.MAX_CANDIDATE_BATCH_BYTES.toULong(),
                singleUseNonce = nonceCharacter.repeat(64),
                issuedAtMs = now - 100uL,
                notBeforeMs = now - 10uL,
                expiresAtMs = now + 20_000uL,
                authority = authority,
                candidateBatch = candidateBatch,
                endpointOperationProof = proof,
                signingPublicKey = signing.public,
                signingPrivateKey = signing.private,
            )
            return ProductionC1CandidateVerifier.verifyCapability(
                value,
                P2pNatCanonicalCodec.encode(candidateBatch),
                proof,
                context,
                authority,
                verifiedKeyset,
                now,
            )
        }

        val clientPublish = capability(
            ProductionC1CandidateOperation.PUBLISH,
            P2pNatRole.CLIENT,
            P2pNatRole.CLIENT,
            "1",
            "3",
            "7",
            clientBatch,
        )
        val runtimeFetchClient = capability(
            ProductionC1CandidateOperation.FETCH,
            P2pNatRole.RUNTIME,
            P2pNatRole.CLIENT,
            "2",
            "4",
            "8",
            clientBatch,
        )
        val runtimePublish = capability(
            ProductionC1CandidateOperation.PUBLISH,
            P2pNatRole.RUNTIME,
            P2pNatRole.RUNTIME,
            "3",
            "5",
            "9",
            runtimeBatch,
        )
        val clientFetchRuntime = capability(
            ProductionC1CandidateOperation.FETCH,
            P2pNatRole.CLIENT,
            P2pNatRole.RUNTIME,
            "4",
            "6",
            "c",
            runtimeBatch,
        )
        val bilateral = ProductionC1CandidateVerifier.verifyBilateral(
            clientPublish,
            runtimeFetchClient,
            runtimePublish,
            clientFetchRuntime,
            authority,
            now,
        )
        val selectedPairDigest = ProductionC1CandidateVerifier.selectedCandidatePairDigest(
            clientBatch.candidates.single(),
            runtimeBatch.candidates.single(),
        )
        val pathReceipt = PathValidationReceipt(
            SESSION_ID,
            authority.generation,
            selectedPairDigest,
            TransportContext.DIRECT,
            "3".repeat(64),
            "4".repeat(64),
            now - 100uL,
            now + 15_000uL,
        )
        val pathBytes = P2pNatCanonicalCodec.encode(pathReceipt)
        val pathDigest = digest(pathBytes)
        val connector = ProductionC1RouteConnectorMaterial(
            ProductionC1RouteKind.P2P_DIRECT,
            byteArrayOf(8, 8, 4, 4),
            50_000u,
            null,
            ProductionC1RouteTransport.UDP,
            ProductionC1RouteCommitments.routeHandleDigest(
                ProductionC1RouteKind.P2P_DIRECT,
                "direct-01",
            ),
            ProductionC1RouteCommitments.credentialCommitmentDigest(
                ProductionC1RouteKind.P2P_DIRECT,
                "direct-01",
                "nonce-01",
                ByteArray(32) { 0x5a },
            ),
            pathDigest,
        )
        val claims = ProductionC1RoutePlanClaims(
            "f".repeat(64),
            ProductionC1RouteKind.P2P_DIRECT,
            authority.digestHex(),
            authority.pairBindingDigest,
            authority.pairEpoch,
            authority.generation,
            authority.clientIdentityFingerprint,
            authority.runtimeIdentityFingerprint,
            connector,
            context.digestHex(),
            pathDigest,
            now - 10uL,
            now + 10_000uL,
        )
        val routeCapability = ProductionC1RouteCapability.signed(
            serviceId,
            1uL,
            "e".repeat(64),
            now - 100uL,
            now - 10uL,
            now + 12_000uL,
            authority,
            ProductionC1RouteKind.P2P_DIRECT,
            claims.digestHex(),
            signing.public,
            signing.private,
        )
        val plan = ProductionC1CandidateVerifier.verifyP2PDirectPlan(
            claims,
            routeCapability,
            context,
            bilateral,
            clientBatch.candidates.single(),
            runtimeBatch.candidates.single(),
            pathBytes,
            authority,
            verifiedKeyset,
            nowMs = now,
        )
        val authorizations = ProductionC1CandidateVerifier.makeBilateralRouteAuthorizations(
            plan,
            authority,
            now,
        )
        return Fixture(
            root,
            signing,
            authority,
            verifiedKeyset,
            context,
            bilateral,
            claims,
            routeCapability,
            plan,
            authorizations,
        )
    }

    private fun batch(role: P2pNatRole, sequence: ULong, address: ByteArray): CandidateBatch =
        CandidateBatch(
            SESSION_ID,
            1uL,
            sequence,
            now + 30_000uL,
            role,
            listOf(
                P2pCandidate(
                    CandidateKind.SERVER_REFLEXIVE,
                    AddressFamily.IPV4,
                    50_000,
                    100u,
                    ByteArray(8) { sequence.toByte() },
                    address,
                ),
            ),
        )

    private fun candidateAndRoutePurposes(): ProductionC1DelegatedKeyPurpose =
        ProductionC1DelegatedKeyPurpose.ROUTE_CAPABILITY or
            ProductionC1DelegatedKeyPurpose.CANDIDATE_PUBLISH or
            ProductionC1DelegatedKeyPurpose.CANDIDATE_FETCH or
            ProductionC1DelegatedKeyPurpose.CANDIDATE_PUBLISH_RECEIPT or
            ProductionC1DelegatedKeyPurpose.CANDIDATE_FETCH_RECEIPT

    private fun sameVersionRouteFork(
        fixture: Fixture,
    ): VerifiedProductionC1ServiceKeyset {
        val forkDelegated = ProductionC1DelegatedKey(
            1uL,
            ProductionC1InternalBridge.keyId(fixture.signingKey.public),
            candidateAndRoutePurposes(),
            now - 1_000uL,
            now + 100_000uL,
            revokedAtMs = now + 50_000uL,
            publicKeyX963 = x963(fixture.signingKey.public),
        )
        val fork = ProductionC1ServiceKeyset.signed(
            serviceId,
            1uL,
            null,
            now - 1_000uL,
            now + 100_000uL,
            listOf(forkDelegated),
            fixture.rootKey.public,
            fixture.rootKey.private,
        )
        return ProductionC1Verifier.verifyServiceKeyset(
            fork,
            serviceId,
            fixture.rootKey.public,
            1uL,
            nowMs = now,
        )
    }

    private fun commitAll(
        fixture: Fixture,
        initialRevision: ULong = 1uL,
    ): List<VerifiedProductionC1CandidateOperationReceipt> {
        var state = ProductionC1CandidateUsageLedgerState(
            revision = initialRevision,
            remainingOperations = 4uL,
            remainingBytes = fixture.capabilities.sumOf {
                it.capability.candidateBatchByteCount.toULong()
            },
            retentionLimit = 8u,
        )
        val receipts = mutableListOf<VerifiedProductionC1CandidateOperationReceipt>()
        val ledgerId = digest("candidate-operation-ledger".toByteArray())
        fixture.capabilities.indices.forEach { index ->
            val capability = fixture.capabilities[index]
            val authorization = fixture.authorizations.operationOrder[index]
            val requestId = capability.endpointOperationProof.proofId
            val authorizationDigest = digest(ProductionSecureSessionCodec.encode(authorization))
            val requestDigest = ProductionC1CandidateUsageLedger.requestDigest(
                requestId,
                capability.capabilityDigest,
                authorizationDigest,
            )
            val preparation = ProductionC1CandidateUsageLedger.prepareConsume(
                state,
                state.revision,
                state.snapshotDigestHex(),
                requestId,
                requestDigest,
                capability,
                authorization,
                capability.capability.requesterRole,
                capability.capability.requesterIdentityFingerprint,
                fixture.authority,
                now,
            )
            val previous = state
            state = preparation.nextState
            val confirmed = ReadbackConfirmedProductionC1CandidateUsageReceipt.confirm(
                preparation,
                state,
                ledgerId,
                digest("candidate-commit-$index".toByteArray()),
            )
            val receipt = ProductionC1CandidateOperationReceipt.signedAfterAppliedCommit(
                capability,
                authorization,
                confirmed,
                previous,
                state,
                now,
                now,
                now,
                now + 10_000uL,
                fixture.authority,
                fixture.verifiedKeyset,
                fixture.signingKey.public,
                fixture.signingKey.private,
            )
            receipts += ProductionC1CandidateOperationReceiptVerifier.verify(
                receipt,
                capability,
                authorization,
                fixture.authority,
                fixture.verifiedKeyset,
                now,
            )
        }
        return receipts
    }

    private fun keyPair(): KeyPair = KeyPairGenerator.getInstance("EC").run {
        initialize(ECGenParameterSpec("secp256r1"))
        generateKeyPair()
    }

    private fun x963(publicKey: PublicKey): ByteArray {
        val point = (publicKey as ECPublicKey).w
        return byteArrayOf(0x04) + point.affineX.toFixed(32) + point.affineY.toFixed(32)
    }

    private fun java.math.BigInteger.toFixed(size: Int): ByteArray {
        val bytes = toByteArray()
        val unsigned = if (bytes.size > 1 && bytes[0] == 0.toByte()) bytes.copyOfRange(1, bytes.size) else bytes
        return ByteArray(size - unsigned.size) + unsigned
    }

    private fun digest(value: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(value).joinToString("") {
            (it.toInt() and 0xff).toString(16).padStart(2, '0')
        }

    private fun tags(data: ByteArray): List<Int> = tlvFields(data).map { it.first }

    private fun textField(data: ByteArray, tag: Int): String = field(data, tag).toString(Charsets.US_ASCII)

    private fun field(data: ByteArray, tag: Int): ByteArray =
        tlvFields(data).single { it.first == tag }.second

    private fun replaceTLVField(data: ByteArray, tag: Int, replacement: ByteArray): ByteArray {
        var result = data.copyOfRange(0, 6)
        tlvFields(data).forEach { (fieldTag, value) ->
            val actual = if (fieldTag == tag) replacement else value
            result += byteArrayOf(fieldTag.toByte())
            result += ByteBuffer.allocate(4).putInt(actual.size).array()
            result += actual
        }
        return result
    }

    private fun tlvFields(data: ByteArray): List<Pair<Int, ByteArray>> {
        val fields = mutableListOf<Pair<Int, ByteArray>>()
        var cursor = 6
        while (cursor < data.size) {
            val tag = data[cursor].toInt() and 0xff
            val size = ByteBuffer.wrap(data, cursor + 1, 4).int
            fields += tag to data.copyOfRange(cursor + 5, cursor + 5 + size)
            cursor += 5 + size
        }
        return fields
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

    companion object {
        private const val SESSION_ID = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        private const val ATTEMPT_ID =
            "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    }
}
