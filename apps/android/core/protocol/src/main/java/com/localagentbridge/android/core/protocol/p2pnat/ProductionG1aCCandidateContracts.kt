package com.localagentbridge.android.core.protocol.p2pnat

import java.security.PrivateKey
import java.security.PublicKey

object ProductionC1CandidateCapabilityContract {
    const val PUBLISH_OBJECT_TYPE: Int = 23
    const val FETCH_OBJECT_TYPE: Int = 24
    const val GRANT_EVIDENCE_OBJECT_TYPE: Int = 25
    const val GRANT_AUTHORIZATION_OBJECT_TYPE: Int = 26
    const val ENDPOINT_OPERATION_PROOF_OBJECT_TYPE: Int = 27
    const val REVISION: ULong = 1uL
    const val MAXIMUM_CAPABILITY_BYTES: Int = 4_096
    const val MAXIMUM_GRANT_EVIDENCE_BYTES: Int = 8_192
    const val MAXIMUM_GRANT_AUTHORIZATION_BYTES: Int = 2_048
    const val MAXIMUM_ENDPOINT_OPERATION_PROOF_BYTES: Int = 2_048
    const val MAXIMUM_LIFETIME_MS: ULong = ProductionC1Contract.MAXIMUM_ROUTE_LIFETIME_MS
}

enum class ProductionC1CandidateCapabilityError {
    MALFORMED_CANONICAL,
    INVALID_VALUE,
    ROLE_MISMATCH,
    AUTHORITY_MISMATCH,
    BATCH_MISMATCH,
    ROUTE_MISMATCH,
    REQUEST_CONFLICT,
    REPLAY,
    QUOTA_EXCEEDED,
    REVISION_MISMATCH,
    RETENTION_EXHAUSTED,
    PERSISTENCE_UNAVAILABLE,
}

class ProductionC1CandidateCapabilityException(
    val reason: ProductionC1CandidateCapabilityError,
) : IllegalArgumentException(reason.name.lowercase())

enum class ProductionC1CandidateOperation(
    val wireValue: String,
    internal val objectType: Int,
    internal val keyPurpose: ProductionC1DelegatedKeyPurpose,
    internal val signingDomain: String,
) {
    PUBLISH(
        "candidate_publish",
        ProductionC1CandidateCapabilityContract.PUBLISH_OBJECT_TYPE,
        ProductionC1DelegatedKeyPurpose.CANDIDATE_PUBLISH,
        "AetherLink G1a-C candidate-publish capability service signature v1",
    ),
    FETCH(
        "candidate_fetch",
        ProductionC1CandidateCapabilityContract.FETCH_OBJECT_TYPE,
        ProductionC1DelegatedKeyPurpose.CANDIDATE_FETCH,
        "AetherLink G1a-C candidate-fetch capability service signature v1",
    );

    companion object {
        internal fun decode(value: String): ProductionC1CandidateOperation =
            entries.singleOrNull { it.wireValue == value }
                ?: candidateFail(ProductionC1CandidateCapabilityError.INVALID_VALUE)

        internal fun decodeObjectType(value: Int): ProductionC1CandidateOperation =
            entries.singleOrNull { it.objectType == value }
                ?: candidateFail(ProductionC1CandidateCapabilityError.MALFORMED_CANONICAL)
    }
}

class ProductionC1EndpointOperationProof private constructor(
    val requesterRole: P2pNatRole,
    val requesterIdentityFingerprint: String,
    requesterPublicKeyX963: ByteArray,
    val operation: ProductionC1CandidateOperation,
    val candidateOwnerRole: P2pNatRole,
    val candidateOwnerIdentityFingerprint: String,
    val sessionId: String,
    val attemptId: String,
    val capabilityId: String,
    val candidateBatchDigest: String,
    val candidateBatchSequence: ULong,
    val singleUseNonce: String,
    val securityContextDigest: String,
    val issuedAtMs: ULong,
    val notBeforeMs: ULong,
    val expiresAtMs: ULong,
    // Downstream usage CAS uses this exact value as requestId; no second ID is serialized.
    val proofId: String,
    val pairAuthorityDigest: String,
    val serviceAudienceId: String,
    val initiatorRole: P2pNatRole,
    endpointSignature: ByteArray,
    validateSignature: Boolean,
) {
    private val requesterPublicKeyBytes = requesterPublicKeyX963.copyOf()
    private val endpointSignatureBytes = endpointSignature.copyOf()

    val requesterPublicKeyX963: ByteArray get() = requesterPublicKeyBytes.copyOf()
    val endpointSignature: ByteArray get() = endpointSignatureBytes.copyOf()

    init {
        listOf(
            requesterIdentityFingerprint,
            candidateOwnerIdentityFingerprint,
            capabilityId,
            candidateBatchDigest,
            singleUseNonce,
            securityContextDigest,
            proofId,
            pairAuthorityDigest,
            serviceAudienceId,
        ).forEach(ProductionC1InternalBridge::validateDigest)
        val requesterPublicKey = try {
            ProductionC1InternalBridge.publicKey(requesterPublicKeyBytes)
        } catch (_: ProductionC1Exception) {
            candidateFail(ProductionC1CandidateCapabilityError.ROLE_MISMATCH)
        }
        candidateRequire(
            ProductionC1InternalBridge.keyId(requesterPublicKey) == requesterIdentityFingerprint,
            ProductionC1CandidateCapabilityError.ROLE_MISMATCH,
        )
        candidateRequire(
            candidateIsLowerHex(sessionId, 32) &&
                candidateIsLowerHex(attemptId, 64) &&
                candidateBatchSequence > 0uL &&
                initiatorRole == P2pNatRole.CLIENT &&
                issuedAtMs <= notBeforeMs &&
                notBeforeMs < expiresAtMs,
            ProductionC1CandidateCapabilityError.INVALID_VALUE,
        )
        when (operation) {
            ProductionC1CandidateOperation.PUBLISH -> candidateRequire(
                requesterRole == candidateOwnerRole,
                ProductionC1CandidateCapabilityError.ROLE_MISMATCH,
            )
            ProductionC1CandidateOperation.FETCH -> candidateRequire(
                requesterRole != candidateOwnerRole,
                ProductionC1CandidateCapabilityError.ROLE_MISMATCH,
            )
        }
        if (validateSignature) {
            ProductionC1InternalBridge.validateSignature(endpointSignatureBytes)
        }
        candidateRequire(
            canonicalBytes().size <=
                ProductionC1CandidateCapabilityContract.MAXIMUM_ENDPOINT_OPERATION_PROOF_BYTES,
            ProductionC1CandidateCapabilityError.INVALID_VALUE,
        )
    }

    fun canonicalBytes(): ByteArray = ProductionC1InternalBridge.encode(
        ProductionC1CandidateCapabilityContract.ENDPOINT_OPERATION_PROOF_OBJECT_TYPE,
        claimsFields() + endpointSignatureBytes,
    )

    fun digestHex(): String = ProductionC1InternalBridge.digestHex(canonicalBytes())

    internal fun signingTranscript(): ByteArray = ProductionC1InternalBridge.transcript(
        ENDPOINT_SIGNING_DOMAIN,
        ProductionC1InternalBridge.encode(
            ProductionC1CandidateCapabilityContract.ENDPOINT_OPERATION_PROOF_OBJECT_TYPE,
            claimsFields(),
        ),
    )

    private fun claimsFields(): List<ByteArray> = listOf(
        ProductionC1InternalBridge.ascii(ProductionC1Contract.SUITE),
        ProductionC1InternalBridge.be(ProductionC1CandidateCapabilityContract.REVISION),
        ProductionC1InternalBridge.ascii(requesterRole.wireValue),
        ProductionC1InternalBridge.ascii(requesterIdentityFingerprint),
        requesterPublicKeyBytes,
        ProductionC1InternalBridge.ascii(operation.wireValue),
        ProductionC1InternalBridge.ascii(candidateOwnerRole.wireValue),
        ProductionC1InternalBridge.ascii(candidateOwnerIdentityFingerprint),
        ProductionC1InternalBridge.ascii(sessionId),
        ProductionC1InternalBridge.ascii(attemptId),
        ProductionC1InternalBridge.ascii(capabilityId),
        ProductionC1InternalBridge.ascii(candidateBatchDigest),
        ProductionC1InternalBridge.be(candidateBatchSequence),
        ProductionC1InternalBridge.ascii(singleUseNonce),
        ProductionC1InternalBridge.ascii(securityContextDigest),
        ProductionC1InternalBridge.be(issuedAtMs),
        ProductionC1InternalBridge.be(notBeforeMs),
        ProductionC1InternalBridge.be(expiresAtMs),
        ProductionC1InternalBridge.ascii(proofId),
        ProductionC1InternalBridge.ascii(pairAuthorityDigest),
        ProductionC1InternalBridge.ascii(serviceAudienceId),
        ProductionC1InternalBridge.ascii(initiatorRole.wireValue),
        ProductionC1InternalBridge.ascii(ProductionC1Contract.SIGNATURE_ALGORITHM),
    )

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is ProductionC1EndpointOperationProof &&
                canonicalBytes().contentEquals(other.canonicalBytes()))

    override fun hashCode(): Int = canonicalBytes().contentHashCode()

    companion object {
        private const val ENDPOINT_SIGNING_DOMAIN =
            "AetherLink G1a-C endpoint-authenticated candidate operation v1"

        fun signed(
            requesterRole: P2pNatRole,
            operation: ProductionC1CandidateOperation,
            candidateOwnerRole: P2pNatRole,
            proofId: String,
            attemptId: String,
            capabilityId: String,
            candidateBatch: CandidateBatch,
            singleUseNonce: String,
            securityContext: ProductionC1PreauthorizationSessionContext,
            serviceAudienceId: String,
            initiatorRole: P2pNatRole = P2pNatRole.CLIENT,
            authority: ProductionPairAuthorityState,
            issuedAtMs: ULong,
            notBeforeMs: ULong,
            expiresAtMs: ULong,
            requesterIdentityPublicKeyX963: ByteArray,
            requesterIdentityPrivateKey: PrivateKey,
        ): ProductionC1EndpointOperationProof {
            candidateRequire(
                securityContext.sessionId == candidateBatch.sessionId &&
                    securityContext.generation == candidateBatch.generation &&
                    securityContext.pairBindingDigest == authority.pairBindingDigest,
                ProductionC1CandidateCapabilityError.ROLE_MISMATCH,
            )
            val requesterIdentity = authority.identityFingerprint(requesterRole)
            val ownerIdentity = authority.identityFingerprint(candidateOwnerRole)
            val batchBytes = P2pNatCanonicalCodec.encode(candidateBatch)
            val unsigned = ProductionC1EndpointOperationProof(
                requesterRole,
                requesterIdentity,
                requesterIdentityPublicKeyX963,
                operation,
                candidateOwnerRole,
                ownerIdentity,
                candidateBatch.sessionId,
                attemptId,
                capabilityId,
                ProductionC1InternalBridge.digestHex(batchBytes),
                candidateBatch.sequence,
                singleUseNonce,
                securityContext.digestHex(),
                issuedAtMs,
                notBeforeMs,
                expiresAtMs,
                proofId,
                authority.digestHex(),
                serviceAudienceId,
                initiatorRole,
                byteArrayOf(),
                false,
            )
            return ProductionC1EndpointOperationProof(
                unsigned.requesterRole,
                unsigned.requesterIdentityFingerprint,
                unsigned.requesterPublicKeyBytes,
                unsigned.operation,
                unsigned.candidateOwnerRole,
                unsigned.candidateOwnerIdentityFingerprint,
                unsigned.sessionId,
                unsigned.attemptId,
                unsigned.capabilityId,
                unsigned.candidateBatchDigest,
                unsigned.candidateBatchSequence,
                unsigned.singleUseNonce,
                unsigned.securityContextDigest,
                unsigned.issuedAtMs,
                unsigned.notBeforeMs,
                unsigned.expiresAtMs,
                unsigned.proofId,
                unsigned.pairAuthorityDigest,
                unsigned.serviceAudienceId,
                unsigned.initiatorRole,
                ProductionC1InternalBridge.sign(unsigned.signingTranscript(), requesterIdentityPrivateKey),
                true,
            ).also { proof ->
                // CryptoKit derives the public key from one private-key value. The JVM API
                // receives separate handles, so reject a mismatched pair here. Valid wire bytes
                // remain identical; only invalid input fails earlier with INVALID_SIGNATURE.
                ProductionC1InternalBridge.verify(
                    proof.endpointSignatureBytes,
                    proof.signingTranscript(),
                    ProductionC1InternalBridge.publicKey(proof.requesterPublicKeyBytes),
                )
            }
        }

        fun decode(data: ByteArray): ProductionC1EndpointOperationProof {
            val fields = ProductionC1InternalBridge.decode(
                data,
                ProductionC1CandidateCapabilityContract.ENDPOINT_OPERATION_PROOF_OBJECT_TYPE,
                24,
                ProductionC1CandidateCapabilityContract.MAXIMUM_ENDPOINT_OPERATION_PROOF_BYTES,
            )
            candidateRequire(
                ProductionC1InternalBridge.text(fields[0]) == ProductionC1Contract.SUITE &&
                    ProductionC1InternalBridge.uint64(fields[1]) ==
                    ProductionC1CandidateCapabilityContract.REVISION &&
                    ProductionC1InternalBridge.text(fields[22]) ==
                    ProductionC1Contract.SIGNATURE_ALGORITHM,
                ProductionC1CandidateCapabilityError.INVALID_VALUE,
            )
            val proof = ProductionC1EndpointOperationProof(
                candidateRole(ProductionC1InternalBridge.text(fields[2])),
                ProductionC1InternalBridge.text(fields[3]),
                fields[4],
                ProductionC1CandidateOperation.decode(ProductionC1InternalBridge.text(fields[5])),
                candidateRole(ProductionC1InternalBridge.text(fields[6])),
                ProductionC1InternalBridge.text(fields[7]),
                ProductionC1InternalBridge.text(fields[8]),
                ProductionC1InternalBridge.text(fields[9]),
                ProductionC1InternalBridge.text(fields[10]),
                ProductionC1InternalBridge.text(fields[11]),
                ProductionC1InternalBridge.uint64(fields[12]),
                ProductionC1InternalBridge.text(fields[13]),
                ProductionC1InternalBridge.text(fields[14]),
                ProductionC1InternalBridge.uint64(fields[15]),
                ProductionC1InternalBridge.uint64(fields[16]),
                ProductionC1InternalBridge.uint64(fields[17]),
                ProductionC1InternalBridge.text(fields[18]),
                ProductionC1InternalBridge.text(fields[19]),
                ProductionC1InternalBridge.text(fields[20]),
                candidateRole(ProductionC1InternalBridge.text(fields[21])),
                fields[23],
                true,
            )
            candidateRequire(
                proof.canonicalBytes().contentEquals(data),
                ProductionC1CandidateCapabilityError.MALFORMED_CANONICAL,
            )
            return proof
        }
    }
}

class ProductionC1CandidateCapability private constructor(
    val operation: ProductionC1CandidateOperation,
    val serviceIdDigest: String,
    val keysetVersion: ULong,
    val signingKeyId: String,
    val capabilityId: String,
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
    val requesterRole: P2pNatRole,
    val requesterIdentityFingerprint: String,
    val candidateOwnerRole: P2pNatRole,
    val candidateOwnerIdentityFingerprint: String,
    val candidateBatchDigest: String,
    val candidateBatchByteCount: UInt,
    val candidateBatchSequence: ULong,
    val candidateBatchExpiresAtMs: ULong,
    val maximumCandidateBytes: ULong,
    val maxOperations: UInt,
    val singleUseNonce: String,
    val issuedAtMs: ULong,
    val notBeforeMs: ULong,
    val expiresAtMs: ULong,
    val endpointOperationProofDigest: String,
    serviceSignature: ByteArray,
    validateSignature: Boolean,
) {
    private val serviceSignatureBytes = serviceSignature.copyOf()
    val serviceSignature: ByteArray get() = serviceSignatureBytes.copyOf()

    init {
        listOf(
            serviceIdDigest,
            signingKeyId,
            capabilityId,
            pairAuthorityDigest,
            pairBindingDigest,
            clientIdentityFingerprint,
            runtimeIdentityFingerprint,
            requesterIdentityFingerprint,
            candidateOwnerIdentityFingerprint,
            candidateBatchDigest,
            singleUseNonce,
            endpointOperationProofDigest,
        ).forEach(ProductionC1InternalBridge::validateDigest)
        candidateRequire(
            candidateIsLowerHex(sessionId, 32) &&
                candidateIsLowerHex(attemptId, 64) &&
                keysetVersion > 0uL &&
                pairEpoch > 0uL &&
                generation > 0uL &&
                serviceConfigVersion > 0uL &&
                protocolFloor > 0u &&
                clientIdentityFingerprint != runtimeIdentityFingerprint &&
                candidateBatchByteCount > 0u &&
                candidateBatchByteCount.toULong() <= maximumCandidateBytes &&
                maximumCandidateBytes <= P2pNatContract.MAX_CANDIDATE_BATCH_BYTES.toULong() &&
                maxOperations == 1u &&
                issuedAtMs <= notBeforeMs &&
                notBeforeMs < expiresAtMs &&
                expiresAtMs <= candidateBatchExpiresAtMs,
            ProductionC1CandidateCapabilityError.INVALID_VALUE,
        )
        candidateRequire(
            requesterIdentityFingerprint == authorityIdentityFingerprint(requesterRole) &&
                candidateOwnerIdentityFingerprint == authorityIdentityFingerprint(candidateOwnerRole),
            ProductionC1CandidateCapabilityError.ROLE_MISMATCH,
        )
        when (operation) {
            ProductionC1CandidateOperation.PUBLISH -> candidateRequire(
                requesterRole == candidateOwnerRole,
                ProductionC1CandidateCapabilityError.ROLE_MISMATCH,
            )
            ProductionC1CandidateOperation.FETCH -> candidateRequire(
                requesterRole != candidateOwnerRole,
                ProductionC1CandidateCapabilityError.ROLE_MISMATCH,
            )
        }
        if (validateSignature) {
            ProductionC1InternalBridge.validateSignature(serviceSignatureBytes)
        }
        candidateRequire(
            canonicalBytes().size <= ProductionC1CandidateCapabilityContract.MAXIMUM_CAPABILITY_BYTES,
            ProductionC1CandidateCapabilityError.INVALID_VALUE,
        )
    }

    private fun authorityIdentityFingerprint(role: P2pNatRole): String =
        if (role == P2pNatRole.CLIENT) clientIdentityFingerprint else runtimeIdentityFingerprint

    fun canonicalBytes(): ByteArray = ProductionC1InternalBridge.encode(
        operation.objectType,
        claimsFields() + serviceSignatureBytes,
    )

    fun digestHex(): String = ProductionC1InternalBridge.digestHex(canonicalBytes())

    internal fun signingTranscript(): ByteArray = ProductionC1InternalBridge.transcript(
        operation.signingDomain,
        ProductionC1InternalBridge.encode(operation.objectType, claimsFields()),
    )

    private fun claimsFields(): List<ByteArray> = listOf(
        ProductionC1InternalBridge.ascii(ProductionC1Contract.SUITE),
        ProductionC1InternalBridge.ascii(operation.wireValue),
        ProductionC1InternalBridge.ascii(serviceIdDigest),
        ProductionC1InternalBridge.be(keysetVersion),
        ProductionC1InternalBridge.ascii(signingKeyId),
        ProductionC1InternalBridge.ascii(capabilityId),
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
        ProductionC1InternalBridge.ascii(requesterRole.wireValue),
        ProductionC1InternalBridge.ascii(requesterIdentityFingerprint),
        ProductionC1InternalBridge.ascii(candidateOwnerRole.wireValue),
        ProductionC1InternalBridge.ascii(candidateOwnerIdentityFingerprint),
        ProductionC1InternalBridge.ascii(candidateBatchDigest),
        ProductionC1InternalBridge.be(candidateBatchByteCount),
        ProductionC1InternalBridge.be(candidateBatchSequence),
        ProductionC1InternalBridge.be(candidateBatchExpiresAtMs),
        ProductionC1InternalBridge.be(maximumCandidateBytes),
        ProductionC1InternalBridge.be(maxOperations),
        ProductionC1InternalBridge.ascii(singleUseNonce),
        ProductionC1InternalBridge.be(issuedAtMs),
        ProductionC1InternalBridge.be(notBeforeMs),
        ProductionC1InternalBridge.be(expiresAtMs),
        ProductionC1InternalBridge.ascii(endpointOperationProofDigest),
        ProductionC1InternalBridge.ascii(ProductionC1Contract.SIGNATURE_ALGORITHM),
    )

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is ProductionC1CandidateCapability &&
                canonicalBytes().contentEquals(other.canonicalBytes()))

    override fun hashCode(): Int = canonicalBytes().contentHashCode()

    companion object {
        fun signed(
            operation: ProductionC1CandidateOperation,
            serviceIdDigest: String,
            keysetVersion: ULong,
            capabilityId: String,
            attemptId: String,
            requesterRole: P2pNatRole,
            candidateOwnerRole: P2pNatRole,
            maximumCandidateBytes: ULong,
            singleUseNonce: String,
            issuedAtMs: ULong,
            notBeforeMs: ULong,
            expiresAtMs: ULong,
            authority: ProductionPairAuthorityState,
            candidateBatch: CandidateBatch,
            endpointOperationProof: ProductionC1EndpointOperationProof,
            signingPublicKey: PublicKey,
            signingPrivateKey: PrivateKey,
        ): ProductionC1CandidateCapability {
            val batchBytes = P2pNatCanonicalCodec.encode(candidateBatch)
            candidateRequire(
                batchBytes.size.toULong() <= UInt.MAX_VALUE.toULong(),
                ProductionC1CandidateCapabilityError.INVALID_VALUE,
            )
            val requesterIdentity = authority.identityFingerprint(requesterRole)
            val ownerIdentity = authority.identityFingerprint(candidateOwnerRole)
            candidateRequire(
                endpointOperationProof.operation == operation &&
                    endpointOperationProof.requesterRole == requesterRole &&
                    endpointOperationProof.requesterIdentityFingerprint == requesterIdentity &&
                    endpointOperationProof.candidateOwnerRole == candidateOwnerRole &&
                    endpointOperationProof.candidateOwnerIdentityFingerprint == ownerIdentity &&
                    endpointOperationProof.capabilityId == capabilityId &&
                    endpointOperationProof.attemptId == attemptId &&
                    endpointOperationProof.singleUseNonce == singleUseNonce &&
                    endpointOperationProof.sessionId == candidateBatch.sessionId &&
                    endpointOperationProof.candidateBatchDigest ==
                    ProductionC1InternalBridge.digestHex(batchBytes) &&
                    endpointOperationProof.candidateBatchSequence == candidateBatch.sequence &&
                    endpointOperationProof.notBeforeMs <= notBeforeMs &&
                    endpointOperationProof.expiresAtMs >= expiresAtMs,
                ProductionC1CandidateCapabilityError.ROLE_MISMATCH,
            )
            val unsigned = ProductionC1CandidateCapability(
                operation,
                serviceIdDigest,
                keysetVersion,
                ProductionC1InternalBridge.keyId(signingPublicKey),
                capabilityId,
                authority.digestHex(),
                authority.pairBindingDigest,
                authority.pairEpoch,
                authority.generation,
                authority.serviceConfigVersion,
                authority.revocationCounter,
                authority.protocolFloor,
                authority.clientIdentityFingerprint,
                authority.runtimeIdentityFingerprint,
                candidateBatch.sessionId,
                attemptId,
                requesterRole,
                requesterIdentity,
                candidateOwnerRole,
                ownerIdentity,
                ProductionC1InternalBridge.digestHex(batchBytes),
                batchBytes.size.toUInt(),
                candidateBatch.sequence,
                candidateBatch.expiresAtMillis,
                maximumCandidateBytes,
                1u,
                singleUseNonce,
                issuedAtMs,
                notBeforeMs,
                expiresAtMs,
                endpointOperationProof.digestHex(),
                byteArrayOf(),
                false,
            )
            return ProductionC1CandidateCapability(
                unsigned.operation,
                unsigned.serviceIdDigest,
                unsigned.keysetVersion,
                unsigned.signingKeyId,
                unsigned.capabilityId,
                unsigned.pairAuthorityDigest,
                unsigned.pairBindingDigest,
                unsigned.pairEpoch,
                unsigned.generation,
                unsigned.serviceConfigVersion,
                unsigned.revocationCounter,
                unsigned.protocolFloor,
                unsigned.clientIdentityFingerprint,
                unsigned.runtimeIdentityFingerprint,
                unsigned.sessionId,
                unsigned.attemptId,
                unsigned.requesterRole,
                unsigned.requesterIdentityFingerprint,
                unsigned.candidateOwnerRole,
                unsigned.candidateOwnerIdentityFingerprint,
                unsigned.candidateBatchDigest,
                unsigned.candidateBatchByteCount,
                unsigned.candidateBatchSequence,
                unsigned.candidateBatchExpiresAtMs,
                unsigned.maximumCandidateBytes,
                unsigned.maxOperations,
                unsigned.singleUseNonce,
                unsigned.issuedAtMs,
                unsigned.notBeforeMs,
                unsigned.expiresAtMs,
                unsigned.endpointOperationProofDigest,
                ProductionC1InternalBridge.sign(unsigned.signingTranscript(), signingPrivateKey),
                true,
            ).also { capability ->
                // Keep the JVM's separately supplied public/private handles from producing a
                // capability that cannot be verified. This is stricter only for invalid pairs.
                ProductionC1InternalBridge.verify(
                    capability.serviceSignatureBytes,
                    capability.signingTranscript(),
                    signingPublicKey,
                )
            }
        }

        fun decode(data: ByteArray): ProductionC1CandidateCapability {
            candidateRequire(
                data.size >= 6,
                ProductionC1CandidateCapabilityError.MALFORMED_CANONICAL,
            )
            val operation = ProductionC1CandidateOperation.decodeObjectType(data[4].toInt() and 0xff)
            val fields = ProductionC1InternalBridge.decode(
                data,
                operation.objectType,
                34,
                ProductionC1CandidateCapabilityContract.MAXIMUM_CAPABILITY_BYTES,
            )
            candidateRequire(
                ProductionC1InternalBridge.text(fields[0]) == ProductionC1Contract.SUITE &&
                    ProductionC1InternalBridge.text(fields[1]) == operation.wireValue &&
                    ProductionC1InternalBridge.text(fields[32]) ==
                    ProductionC1Contract.SIGNATURE_ALGORITHM,
                ProductionC1CandidateCapabilityError.INVALID_VALUE,
            )
            val capability = ProductionC1CandidateCapability(
                operation,
                ProductionC1InternalBridge.text(fields[2]),
                ProductionC1InternalBridge.uint64(fields[3]),
                ProductionC1InternalBridge.text(fields[4]),
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
                candidateRole(ProductionC1InternalBridge.text(fields[17])),
                ProductionC1InternalBridge.text(fields[18]),
                candidateRole(ProductionC1InternalBridge.text(fields[19])),
                ProductionC1InternalBridge.text(fields[20]),
                ProductionC1InternalBridge.text(fields[21]),
                ProductionC1InternalBridge.uint32(fields[22]),
                ProductionC1InternalBridge.uint64(fields[23]),
                ProductionC1InternalBridge.uint64(fields[24]),
                ProductionC1InternalBridge.uint64(fields[25]),
                ProductionC1InternalBridge.uint32(fields[26]),
                ProductionC1InternalBridge.text(fields[27]),
                ProductionC1InternalBridge.uint64(fields[28]),
                ProductionC1InternalBridge.uint64(fields[29]),
                ProductionC1InternalBridge.uint64(fields[30]),
                ProductionC1InternalBridge.text(fields[31]),
                fields[33],
                true,
            )
            candidateRequire(
                capability.canonicalBytes().contentEquals(data),
                ProductionC1CandidateCapabilityError.MALFORMED_CANONICAL,
            )
            return capability
        }
    }
}

class VerifiedProductionC1CandidateCapability private constructor(
    val capability: ProductionC1CandidateCapability,
    canonicalCandidateBatch: ByteArray,
    val capabilityDigest: String,
    val endpointOperationProof: ProductionC1EndpointOperationProof,
    val securityContext: ProductionC1PreauthorizationSessionContext,
    internal val verifiedKeyset: VerifiedProductionC1ServiceKeyset,
) {
    private val canonicalCandidateBatchBytes = canonicalCandidateBatch.copyOf()

    val canonicalCandidateBatch: ByteArray get() = canonicalCandidateBatchBytes.copyOf()

    val candidateBatch: CandidateBatch
        get() = P2pNatCanonicalCodec.decodeCandidateBatch(canonicalCandidateBatchBytes.copyOf())

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is VerifiedProductionC1CandidateCapability &&
                capability == other.capability &&
                canonicalCandidateBatchBytes.contentEquals(other.canonicalCandidateBatchBytes) &&
                capabilityDigest == other.capabilityDigest &&
                endpointOperationProof == other.endpointOperationProof &&
                securityContext == other.securityContext &&
                verifiedKeyset.keyset == other.verifiedKeyset.keyset)

    override fun hashCode(): Int {
        var result = capability.hashCode()
        result = 31 * result + canonicalCandidateBatchBytes.contentHashCode()
        result = 31 * result + capabilityDigest.hashCode()
        result = 31 * result + endpointOperationProof.hashCode()
        result = 31 * result + securityContext.hashCode()
        return 31 * result + verifiedKeyset.keyset.hashCode()
    }

    companion object {
        internal fun verify(
            capability: ProductionC1CandidateCapability,
            candidateBatchCanonicalBytes: ByteArray,
            endpointOperationProof: ProductionC1EndpointOperationProof,
            securityContext: ProductionC1PreauthorizationSessionContext,
            authority: ProductionPairAuthorityState,
            verifiedKeyset: VerifiedProductionC1ServiceKeyset,
            nowMs: ULong,
        ): VerifiedProductionC1CandidateCapability {
            val batchBytes = candidateBatchCanonicalBytes.copyOf()
            val batch = P2pNatCanonicalCodec.decodeCandidateBatch(batchBytes)
            candidateRequire(
                P2pNatCanonicalCodec.encode(batch).contentEquals(batchBytes),
                ProductionC1CandidateCapabilityError.MALFORMED_CANONICAL,
            )
            val verified = VerifiedProductionC1CandidateCapability(
                capability,
                batchBytes,
                capability.digestHex(),
                endpointOperationProof,
                securityContext,
                verifiedKeyset,
            )
            ProductionC1CandidateVerifier.validateUse(verified, authority, nowMs)
            return verified
        }
    }
}

class VerifiedProductionC1BilateralCandidateCapabilities internal constructor(
    val clientPublish: VerifiedProductionC1CandidateCapability,
    val runtimeFetchClient: VerifiedProductionC1CandidateCapability,
    val runtimePublish: VerifiedProductionC1CandidateCapability,
    val clientFetchRuntime: VerifiedProductionC1CandidateCapability,
    val bilateralPublishDigest: String,
    val bilateralFetchDigest: String,
) {
    internal val all: List<VerifiedProductionC1CandidateCapability>
        get() = listOf(clientPublish, runtimeFetchClient, runtimePublish, clientFetchRuntime)

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is VerifiedProductionC1BilateralCandidateCapabilities &&
                clientPublish == other.clientPublish &&
                runtimeFetchClient == other.runtimeFetchClient &&
                runtimePublish == other.runtimePublish &&
                clientFetchRuntime == other.clientFetchRuntime &&
                bilateralPublishDigest == other.bilateralPublishDigest &&
                bilateralFetchDigest == other.bilateralFetchDigest)

    override fun hashCode(): Int {
        var result = clientPublish.hashCode()
        result = 31 * result + runtimeFetchClient.hashCode()
        result = 31 * result + runtimePublish.hashCode()
        result = 31 * result + clientFetchRuntime.hashCode()
        result = 31 * result + bilateralPublishDigest.hashCode()
        return 31 * result + bilateralFetchDigest.hashCode()
    }
}

object ProductionC1CandidateVerifier {
    fun verifyCapability(
        capability: ProductionC1CandidateCapability,
        candidateBatchCanonicalBytes: ByteArray,
        endpointOperationProof: ProductionC1EndpointOperationProof,
        securityContext: ProductionC1PreauthorizationSessionContext,
        authority: ProductionPairAuthorityState,
        verifiedKeyset: VerifiedProductionC1ServiceKeyset,
        nowMs: ULong,
    ): VerifiedProductionC1CandidateCapability =
        VerifiedProductionC1CandidateCapability.verify(
            capability,
            candidateBatchCanonicalBytes,
            endpointOperationProof,
            securityContext,
            authority,
            verifiedKeyset,
            nowMs,
        )

    fun verifyBilateral(
        clientPublish: VerifiedProductionC1CandidateCapability,
        runtimeFetchClient: VerifiedProductionC1CandidateCapability,
        runtimePublish: VerifiedProductionC1CandidateCapability,
        clientFetchRuntime: VerifiedProductionC1CandidateCapability,
        authority: ProductionPairAuthorityState,
        nowMs: ULong,
    ): VerifiedProductionC1BilateralCandidateCapabilities {
        val values = listOf(clientPublish, runtimeFetchClient, runtimePublish, clientFetchRuntime)
        values.forEach { validateUse(it, authority, nowMs) }
        val canonicalKeyset = clientPublish.verifiedKeyset.keyset.canonicalBytes()
        candidateRequire(
            values.all {
                it.verifiedKeyset.keyset.canonicalBytes().contentEquals(canonicalKeyset)
            },
            ProductionC1CandidateCapabilityError.AUTHORITY_MISMATCH,
        )
        requireShape(
            clientPublish,
            ProductionC1CandidateOperation.PUBLISH,
            P2pNatRole.CLIENT,
            P2pNatRole.CLIENT,
        )
        requireShape(
            runtimeFetchClient,
            ProductionC1CandidateOperation.FETCH,
            P2pNatRole.RUNTIME,
            P2pNatRole.CLIENT,
        )
        requireShape(
            runtimePublish,
            ProductionC1CandidateOperation.PUBLISH,
            P2pNatRole.RUNTIME,
            P2pNatRole.RUNTIME,
        )
        requireShape(
            clientFetchRuntime,
            ProductionC1CandidateOperation.FETCH,
            P2pNatRole.CLIENT,
            P2pNatRole.RUNTIME,
        )
        val first = clientPublish.capability
        candidateRequire(
            values.all { value ->
                val candidate = value.capability
                candidate.serviceIdDigest == first.serviceIdDigest &&
                    candidate.keysetVersion == first.keysetVersion &&
                    candidate.pairAuthorityDigest == first.pairAuthorityDigest &&
                    candidate.pairBindingDigest == first.pairBindingDigest &&
                    candidate.pairEpoch == first.pairEpoch &&
                    candidate.generation == first.generation &&
                    candidate.serviceConfigVersion == first.serviceConfigVersion &&
                    candidate.revocationCounter == first.revocationCounter &&
                    candidate.protocolFloor == first.protocolFloor &&
                    candidate.clientIdentityFingerprint == first.clientIdentityFingerprint &&
                    candidate.runtimeIdentityFingerprint == first.runtimeIdentityFingerprint &&
                    candidate.sessionId == first.sessionId &&
                    candidate.attemptId == first.attemptId &&
                    value.endpointOperationProof.securityContextDigest ==
                    clientPublish.endpointOperationProof.securityContextDigest &&
                    value.securityContext == clientPublish.securityContext &&
                    value.endpointOperationProof.serviceAudienceId ==
                    clientPublish.endpointOperationProof.serviceAudienceId &&
                    value.endpointOperationProof.initiatorRole ==
                    clientPublish.endpointOperationProof.initiatorRole
            } &&
                values.map { it.capability.capabilityId }.toSet().size == 4 &&
                values.map { it.endpointOperationProof.proofId }.toSet().size == 4 &&
                values.map { it.capability.singleUseNonce }.toSet().size == 4,
            ProductionC1CandidateCapabilityError.AUTHORITY_MISMATCH,
        )
        candidateRequire(
            clientPublish.canonicalCandidateBatch.contentEquals(
                runtimeFetchClient.canonicalCandidateBatch,
            ) &&
                runtimePublish.canonicalCandidateBatch.contentEquals(
                    clientFetchRuntime.canonicalCandidateBatch,
                ) &&
                clientPublish.capability.candidateBatchDigest ==
                runtimeFetchClient.capability.candidateBatchDigest &&
                runtimePublish.capability.candidateBatchDigest ==
                clientFetchRuntime.capability.candidateBatchDigest &&
                clientPublish.capability.candidateBatchDigest !=
                runtimePublish.capability.candidateBatchDigest,
            ProductionC1CandidateCapabilityError.BATCH_MISMATCH,
        )
        return VerifiedProductionC1BilateralCandidateCapabilities(
            clientPublish,
            runtimeFetchClient,
            runtimePublish,
            clientFetchRuntime,
            aggregateDigest(
                "AetherLink G1a-C bilateral candidate-publish set v1",
                clientPublish.capabilityDigest,
                runtimePublish.capabilityDigest,
            ),
            aggregateDigest(
                "AetherLink G1a-C bilateral candidate-fetch set v1",
                clientFetchRuntime.capabilityDigest,
                runtimeFetchClient.capabilityDigest,
            ),
        )
    }

    internal fun validateUse(
        verified: VerifiedProductionC1CandidateCapability,
        authority: ProductionPairAuthorityState,
        nowMs: ULong,
    ) {
        val capability = verified.capability
        val batch = verified.candidateBatch
        val proof = verified.endpointOperationProof
        val context = verified.securityContext
        candidateRequire(
            authority.status == ProductionPairAuthorityStatus.ACTIVE &&
                capability.pairAuthorityDigest == authority.digestHex() &&
                capability.pairBindingDigest == authority.pairBindingDigest &&
                capability.pairEpoch == authority.pairEpoch &&
                capability.generation == authority.generation &&
                capability.serviceConfigVersion == authority.serviceConfigVersion &&
                capability.revocationCounter == authority.revocationCounter &&
                capability.protocolFloor == authority.protocolFloor &&
                capability.clientIdentityFingerprint == authority.clientIdentityFingerprint &&
                capability.runtimeIdentityFingerprint == authority.runtimeIdentityFingerprint &&
                capability.serviceIdDigest == verified.verifiedKeyset.keyset.serviceIdDigest &&
                capability.keysetVersion == verified.verifiedKeyset.keyset.keysetVersion &&
                capability.keysetVersion == authority.keysetVersion,
            ProductionC1CandidateCapabilityError.AUTHORITY_MISMATCH,
        )
        val requesterIdentity = authority.identityFingerprint(capability.requesterRole)
        candidateRequire(
            proof.digestHex() == capability.endpointOperationProofDigest &&
                proof.operation == capability.operation &&
                proof.requesterRole == capability.requesterRole &&
                proof.requesterIdentityFingerprint == requesterIdentity &&
                proof.candidateOwnerRole == capability.candidateOwnerRole &&
                proof.candidateOwnerIdentityFingerprint ==
                capability.candidateOwnerIdentityFingerprint &&
                proof.sessionId == capability.sessionId &&
                proof.attemptId == capability.attemptId &&
                proof.capabilityId == capability.capabilityId &&
                proof.candidateBatchDigest == capability.candidateBatchDigest &&
                proof.candidateBatchSequence == capability.candidateBatchSequence &&
                proof.singleUseNonce == capability.singleUseNonce &&
                proof.securityContextDigest == context.digestHex() &&
                proof.pairAuthorityDigest == capability.pairAuthorityDigest &&
                proof.serviceAudienceId == capability.serviceIdDigest &&
                proof.initiatorRole == P2pNatRole.CLIENT &&
                capability.issuedAtMs >= proof.issuedAtMs &&
                proof.notBeforeMs <= capability.notBeforeMs &&
                proof.expiresAtMs >= capability.expiresAtMs &&
                context.sessionId == capability.sessionId &&
                context.pairBindingDigest == capability.pairBindingDigest &&
                context.pairEpoch == capability.pairEpoch &&
                context.generation == capability.generation &&
                context.serviceConfigVersion == capability.serviceConfigVersion &&
                context.keysetVersion == capability.keysetVersion &&
                context.revocationCounter == capability.revocationCounter &&
                context.clientIdentityFingerprint == authority.clientIdentityFingerprint &&
                context.runtimeIdentityFingerprint == authority.runtimeIdentityFingerprint,
            ProductionC1CandidateCapabilityError.ROLE_MISMATCH,
        )
        ProductionC1InternalBridge.validateWindow(
            proof.issuedAtMs,
            proof.notBeforeMs,
            proof.expiresAtMs,
            ProductionC1CandidateCapabilityContract.MAXIMUM_LIFETIME_MS,
            nowMs,
        )
        val endpointPublicKey = ProductionC1InternalBridge.publicKey(proof.requesterPublicKeyX963)
        ProductionC1InternalBridge.verify(
            proof.endpointSignature,
            proof.signingTranscript(),
            endpointPublicKey,
        )
        val batchBytes = verified.canonicalCandidateBatch
        candidateRequire(
            P2pNatCanonicalCodec.encode(batch).contentEquals(batchBytes) &&
                ProductionC1InternalBridge.digestHex(batchBytes) == capability.candidateBatchDigest &&
                batchBytes.size == capability.candidateBatchByteCount.toInt() &&
                batch.sessionId == capability.sessionId &&
                batch.generation == capability.generation &&
                batch.sequence == capability.candidateBatchSequence &&
                batch.expiresAtMillis == capability.candidateBatchExpiresAtMs &&
                batch.senderRole == capability.candidateOwnerRole &&
                nowMs < batch.expiresAtMillis &&
                P2pNatContract.isFresh(batch.expiresAtMillis, nowMs),
            ProductionC1CandidateCapabilityError.BATCH_MISMATCH,
        )
        ProductionC1InternalBridge.validateWindow(
            capability.issuedAtMs,
            capability.notBeforeMs,
            capability.expiresAtMs,
            ProductionC1CandidateCapabilityContract.MAXIMUM_LIFETIME_MS,
            nowMs,
        )
        val signingKey = ProductionC1InternalBridge.delegatedSigningKey(
            capability.signingKeyId,
            capability.operation.keyPurpose,
            verified.verifiedKeyset,
            nowMs,
        )
        ProductionC1InternalBridge.verify(
            capability.serviceSignature,
            capability.signingTranscript(),
            signingKey,
        )
    }

    private fun requireShape(
        value: VerifiedProductionC1CandidateCapability,
        operation: ProductionC1CandidateOperation,
        requester: P2pNatRole,
        owner: P2pNatRole,
    ) {
        candidateRequire(
            value.capability.operation == operation &&
                value.capability.requesterRole == requester &&
                value.capability.candidateOwnerRole == owner,
            ProductionC1CandidateCapabilityError.ROLE_MISMATCH,
        )
    }

    private fun aggregateDigest(
        domain: String,
        clientDigest: String,
        runtimeDigest: String,
    ): String {
        var claims = byteArrayOf()
        listOf("client" to clientDigest, "runtime" to runtimeDigest).forEach { (role, digest) ->
            val roleBytes = ProductionC1InternalBridge.ascii(role)
            val digestBytes = ProductionC1InternalBridge.rawDigest(digest)
            claims += ProductionC1InternalBridge.be(roleBytes.size.toUInt())
            claims += roleBytes
            claims += ProductionC1InternalBridge.be(digestBytes.size.toUInt())
            claims += digestBytes
        }
        return ProductionC1InternalBridge.digestHex(
            ProductionC1InternalBridge.transcript(domain, claims),
        )
    }
}

private fun ProductionPairAuthorityState.identityFingerprint(role: P2pNatRole): String =
    if (role == P2pNatRole.CLIENT) clientIdentityFingerprint else runtimeIdentityFingerprint

private fun candidateRole(value: String): P2pNatRole =
    P2pNatRole.entries.singleOrNull { it.wireValue == value }
        ?: candidateFail(ProductionC1CandidateCapabilityError.INVALID_VALUE)

private fun candidateIsLowerHex(value: String, count: Int): Boolean =
    value.length == count && value.all { it in '0'..'9' || it in 'a'..'f' }

private fun candidateRequire(
    condition: Boolean,
    error: ProductionC1CandidateCapabilityError,
) {
    if (!condition) throw ProductionC1CandidateCapabilityException(error)
}

private fun candidateFail(error: ProductionC1CandidateCapabilityError): Nothing =
    throw ProductionC1CandidateCapabilityException(error)
