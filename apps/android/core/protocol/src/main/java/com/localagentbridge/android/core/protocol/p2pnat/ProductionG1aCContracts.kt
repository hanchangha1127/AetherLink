package com.localagentbridge.android.core.protocol.p2pnat

import java.io.ByteArrayOutputStream
import java.math.BigInteger
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.AlgorithmParameters
import java.security.KeyFactory
import java.security.MessageDigest
import java.security.PrivateKey
import java.security.PublicKey
import java.security.Signature
import java.security.interfaces.ECPublicKey
import java.security.spec.ECFieldFp
import java.security.spec.ECGenParameterSpec
import java.security.spec.ECParameterSpec
import java.security.spec.ECPoint
import java.security.spec.ECPublicKeySpec
import java.security.spec.X509EncodedKeySpec

object ProductionC1Contract {
    const val SERVICE_KEYSET_OBJECT_TYPE = 10
    const val PAIR_STATUS_OBJECT_TYPE = 11
    const val FRESH_PAIR_PROOF_OBJECT_TYPE = 12
    const val ROUTE_CAPABILITY_OBJECT_TYPE = 13
    const val ROUTE_PLAN_OBJECT_TYPE = 14
    const val P2P_CONNECTOR_OBJECT_TYPE = 15
    const val TURN_CONNECTOR_OBJECT_TYPE = 16
    const val SEALED_RELAY_CONNECTOR_OBJECT_TYPE = 17
    const val PREAUTHORIZATION_SESSION_CONTEXT_OBJECT_TYPE = 18
    const val P2P_ROUTE_AUTHORIZATION_OBJECT_TYPE = 20
    const val TURN_ROUTE_AUTHORIZATION_OBJECT_TYPE = 21
    const val SEALED_RELAY_ROUTE_AUTHORIZATION_OBJECT_TYPE = 22

    const val SUITE = "aetherlink-production-authority-route-v1"
    const val SIGNATURE_ALGORITHM = "p256_ecdsa_sha256_der_low_s_v1"
    const val MAXIMUM_KEYSET_BYTES = 4_096
    const val MAXIMUM_PAIR_STATUS_BYTES = 4_096
    const val MAXIMUM_FRESH_PAIR_PROOF_BYTES = 4_096
    const val MAXIMUM_ROUTE_CAPABILITY_BYTES = 2_048
    const val MAXIMUM_ROUTE_PLAN_BYTES = 2_048
    const val MAXIMUM_CONNECTOR_BYTES = 1_024
    const val MAXIMUM_ROUTE_AUTHORIZATION_BYTES = 1_024
    const val MAXIMUM_PREAUTHORIZATION_SESSION_CONTEXT_BYTES = 2_048
    const val MAXIMUM_DELEGATED_KEYS = 8
    const val MAXIMUM_TRANSITION_HISTORY_ENTRIES = 20
    const val MAXIMUM_CLOCK_SKEW_MS: ULong = 30_000uL
    const val MAXIMUM_KEYSET_LIFETIME_MS: ULong = 2_678_400_000uL
    const val MAXIMUM_STATUS_LIFETIME_MS: ULong = 300_000uL
    const val MAXIMUM_FRESH_PAIR_LIFETIME_MS: ULong = 300_000uL
    const val MAXIMUM_ROUTE_LIFETIME_MS: ULong = 600_000uL
}

enum class ProductionC1Error {
    MALFORMED_CANONICAL,
    INVALID_VALUE,
    LIMIT_EXCEEDED,
    INVALID_PUBLIC_KEY,
    INVALID_SIGNATURE,
    NON_CANONICAL_SIGNATURE,
    HIGH_S,
    UNTRUSTED_ROOT,
    SERVICE_MISMATCH,
    KEYSET_ROLLBACK,
    KEYSET_GAP,
    PREVIOUS_KEYSET_MISMATCH,
    KEY_UNAVAILABLE,
    KEY_PURPOSE_MISMATCH,
    KEY_REVOKED,
    ISSUED_IN_FUTURE,
    NOT_YET_VALID,
    EXPIRED,
    STATE_MISMATCH,
    HISTORY_MISMATCH,
    EVIDENCE_MISMATCH,
    INVALID_FRESH_PAIR,
    ROUTE_MISMATCH,
}

class ProductionC1Exception(
    val reason: ProductionC1Error,
) : IllegalArgumentException(reason.name.lowercase())

private fun c1RequireVerifiedMint(provenance: Any) {
    c1Require(ProductionC1Verifier.ownsVerifiedMint(provenance), ProductionC1Error.STATE_MISMATCH)
}

@JvmInline
value class ProductionC1DelegatedKeyPurpose(val rawValue: UInt) {
    fun contains(other: ProductionC1DelegatedKeyPurpose): Boolean = rawValue and other.rawValue == other.rawValue
    fun isEmpty(): Boolean = rawValue == 0u
    infix fun or(other: ProductionC1DelegatedKeyPurpose) = ProductionC1DelegatedKeyPurpose(rawValue or other.rawValue)

    companion object {
        val PAIR_STATUS = ProductionC1DelegatedKeyPurpose(1u shl 0)
        val ROUTE_CAPABILITY = ProductionC1DelegatedKeyPurpose(1u shl 1)
        val CANDIDATE_PUBLISH = ProductionC1DelegatedKeyPurpose(1u shl 2)
        val CANDIDATE_FETCH = ProductionC1DelegatedKeyPurpose(1u shl 3)
        val CANDIDATE_PUBLISH_RECEIPT = ProductionC1DelegatedKeyPurpose(1u shl 4)
        val CANDIDATE_FETCH_RECEIPT = ProductionC1DelegatedKeyPurpose(1u shl 5)
        val ALLOWED = PAIR_STATUS or ROUTE_CAPABILITY or CANDIDATE_PUBLISH or CANDIDATE_FETCH or
            CANDIDATE_PUBLISH_RECEIPT or CANDIDATE_FETCH_RECEIPT
    }
}

class ProductionC1DelegatedKey(
    val keysetVersion: ULong,
    val keyId: String,
    val purposes: ProductionC1DelegatedKeyPurpose,
    val notBeforeMs: ULong,
    val expiresAtMs: ULong,
    val revokedAtMs: ULong? = null,
    publicKeyX963: ByteArray,
) {
    private val publicKeyBytes = publicKeyX963.copyOf()
    val publicKeyX963: ByteArray get() = publicKeyBytes.copyOf()

    init {
        c1ValidateDigest(keyId)
        c1Require(
            keysetVersion > 0uL &&
                !purposes.isEmpty() &&
                purposes.rawValue and ProductionC1DelegatedKeyPurpose.ALLOWED.rawValue.inv() == 0u &&
                notBeforeMs < expiresAtMs &&
                (revokedAtMs == null || revokedAtMs in notBeforeMs..expiresAtMs),
            ProductionC1Error.INVALID_VALUE,
        )
        val publicKey = c1PublicKey(publicKeyBytes)
        c1Require(keyId == c1KeyId(publicKey), ProductionC1Error.INVALID_VALUE)
    }

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is ProductionC1DelegatedKey &&
                keysetVersion == other.keysetVersion &&
                keyId == other.keyId &&
                purposes == other.purposes &&
                notBeforeMs == other.notBeforeMs &&
                expiresAtMs == other.expiresAtMs &&
                revokedAtMs == other.revokedAtMs &&
                publicKeyBytes.contentEquals(other.publicKeyBytes))

    override fun hashCode(): Int {
        var result = keysetVersion.hashCode()
        result = 31 * result + keyId.hashCode()
        result = 31 * result + purposes.hashCode()
        result = 31 * result + notBeforeMs.hashCode()
        result = 31 * result + expiresAtMs.hashCode()
        result = 31 * result + (revokedAtMs?.hashCode() ?: 0)
        return 31 * result + publicKeyBytes.contentHashCode()
    }
}

class ProductionC1ServiceKeyset private constructor(
    val serviceIdDigest: String,
    val keysetVersion: ULong,
    val previousKeysetDigest: String?,
    val issuedAtMs: ULong,
    val expiresAtMs: ULong,
    val rootKeyId: String,
    delegatedKeys: List<ProductionC1DelegatedKey>,
    rootSignature: ByteArray,
    validateSignatureEncoding: Boolean,
) {
    private val delegatedKeyValues = delegatedKeys.toList()
    val delegatedKeys: List<ProductionC1DelegatedKey> get() = delegatedKeyValues.toList()
    private val rootSignatureBytes = rootSignature.copyOf()
    val rootSignature: ByteArray get() = rootSignatureBytes.copyOf()

    init {
        c1ValidateDigest(serviceIdDigest)
        previousKeysetDigest?.let(::c1ValidateDigest)
        c1ValidateDigest(rootKeyId)
        c1Require(
            keysetVersion > 0uL &&
                issuedAtMs < expiresAtMs &&
                delegatedKeyValues.isNotEmpty() &&
                delegatedKeyValues.size <= ProductionC1Contract.MAXIMUM_DELEGATED_KEYS &&
                delegatedKeyValues.map { it.keyId }.toSet().size == delegatedKeyValues.size &&
                delegatedKeyValues.any { it.keysetVersion == keysetVersion } &&
                delegatedKeyValues.all {
                    it.keysetVersion == keysetVersion ||
                        (keysetVersion > 1uL && it.keysetVersion == keysetVersion - 1uL)
                } &&
                delegatedKeyValues.all {
                    it.notBeforeMs >= issuedAtMs && it.expiresAtMs <= expiresAtMs
                } &&
                delegatedKeyValues.map { it.keyId } == delegatedKeyValues.map { it.keyId }.sorted(),
            ProductionC1Error.INVALID_VALUE,
        )
        if (validateSignatureEncoding) c1ValidateCanonicalLowS(rootSignatureBytes)
        c1Require(canonicalBytes().size <= ProductionC1Contract.MAXIMUM_KEYSET_BYTES, ProductionC1Error.LIMIT_EXCEEDED)
    }

    fun canonicalBytes(): ByteArray = C1TLV.encode(
        ProductionC1Contract.SERVICE_KEYSET_OBJECT_TYPE,
        claimsFields() + rootSignatureBytes,
    )

    fun digestHex(): String = c1DigestHex(canonicalBytes())

    internal fun signingTranscript(): ByteArray = c1SignatureTranscript(
        "AetherLink G1a-C service-keyset root signature v1",
        C1TLV.encode(ProductionC1Contract.SERVICE_KEYSET_OBJECT_TYPE, claimsFields()),
    )

    private fun claimsFields(): List<ByteArray> = listOf(
        c1ASCII(ProductionC1Contract.SUITE),
        c1ASCII(serviceIdDigest),
        c1BE(keysetVersion),
        c1OptionalDigestBytes(previousKeysetDigest),
        c1BE(issuedAtMs),
        c1BE(expiresAtMs),
        c1ASCII(rootKeyId),
        c1BE(delegatedKeyValues.size.toUInt()),
        encodeEntries(delegatedKeyValues),
        c1ASCII(ProductionC1Contract.SIGNATURE_ALGORITHM),
    )

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is ProductionC1ServiceKeyset && canonicalBytes().contentEquals(other.canonicalBytes()))

    override fun hashCode(): Int = canonicalBytes().contentHashCode()

    companion object {
        fun signed(
            serviceIdDigest: String,
            keysetVersion: ULong,
            previousKeysetDigest: String?,
            issuedAtMs: ULong,
            expiresAtMs: ULong,
            delegatedKeys: List<ProductionC1DelegatedKey>,
            rootPublicKey: PublicKey,
            rootPrivateKey: PrivateKey,
        ): ProductionC1ServiceKeyset {
            val rootKeyId = c1KeyId(rootPublicKey)
            val unsigned = ProductionC1ServiceKeyset(
                serviceIdDigest, keysetVersion, previousKeysetDigest, issuedAtMs, expiresAtMs,
                rootKeyId, delegatedKeys, byteArrayOf(), false,
            )
            return ProductionC1ServiceKeyset(
                serviceIdDigest, keysetVersion, previousKeysetDigest, issuedAtMs, expiresAtMs,
                rootKeyId, delegatedKeys, c1Sign(unsigned.signingTranscript(), rootPrivateKey), true,
            ).also { c1Verify(it.rootSignature, it.signingTranscript(), rootPublicKey) }
        }

        fun decode(data: ByteArray): ProductionC1ServiceKeyset {
            val fields = C1TLV.decode(
                data,
                ProductionC1Contract.SERVICE_KEYSET_OBJECT_TYPE,
                11,
                ProductionC1Contract.MAXIMUM_KEYSET_BYTES,
            )
            c1Require(
                c1Text(fields[0]) == ProductionC1Contract.SUITE &&
                    c1Text(fields[9]) == ProductionC1Contract.SIGNATURE_ALGORITHM,
                ProductionC1Error.INVALID_VALUE,
            )
            val version = c1UInt64(fields[2])
            val count = c1UInt32(fields[7])
            c1Require(
                count > 0u && count <= ProductionC1Contract.MAXIMUM_DELEGATED_KEYS.toUInt(),
                ProductionC1Error.LIMIT_EXCEEDED,
            )
            val result = ProductionC1ServiceKeyset(
                c1Text(fields[1]), version, c1OptionalDigest(fields[3]), c1UInt64(fields[4]),
                c1UInt64(fields[5]), c1Text(fields[6]), decodeEntries(fields[8], count.toInt()), fields[10], true,
            )
            c1Require(result.canonicalBytes().contentEquals(data), ProductionC1Error.MALFORMED_CANONICAL)
            return result
        }

        private fun encodeEntries(values: List<ProductionC1DelegatedKey>): ByteArray =
            ByteArrayOutputStream().apply {
                values.forEach { value ->
                    write(c1BE(value.keysetVersion))
                    write(c1ForceDecodeDigest(value.keyId))
                    write(c1BE(value.purposes.rawValue))
                    write(c1BE(value.notBeforeMs))
                    write(c1BE(value.expiresAtMs))
                    write(c1BE(value.revokedAtMs ?: 0uL))
                    write(value.publicKeyX963)
                }
            }.toByteArray()

        private fun decodeEntries(data: ByteArray, count: Int): List<ProductionC1DelegatedKey> {
            val size = 8 + 32 + 4 + 8 + 8 + 8 + 65
            c1Require(data.size == count * size, ProductionC1Error.MALFORMED_CANONICAL)
            return List(count) { index ->
                val base = index * size
                ProductionC1DelegatedKey(
                    c1UInt64(data.copyOfRange(base, base + 8)),
                    c1LowerHex(data.copyOfRange(base + 8, base + 40)),
                    ProductionC1DelegatedKeyPurpose(c1UInt32(data.copyOfRange(base + 40, base + 44))),
                    c1UInt64(data.copyOfRange(base + 44, base + 52)),
                    c1UInt64(data.copyOfRange(base + 52, base + 60)),
                    c1UInt64(data.copyOfRange(base + 60, base + 68)).takeUnless { it == 0uL },
                    data.copyOfRange(base + 68, base + size),
                )
            }
        }
    }
}

class VerifiedProductionC1ServiceKeyset internal constructor(
    val keyset: ProductionC1ServiceKeyset,
    provenance: Any,
) {
    init {
        c1RequireVerifiedMint(provenance)
    }
}

enum class ProductionC1RequesterRole(val wireValue: String) {
    CLIENT("client"),
    RUNTIME("runtime");

    companion object {
        fun decode(value: String) = entries.singleOrNull { it.wireValue == value }
            ?: c1Fail(ProductionC1Error.INVALID_VALUE)
    }
}

enum class ProductionC1TransitionKind(val wireValue: String) {
    GENESIS("genesis"),
    SAME_EPOCH("same_epoch"),
    REVOKE("revoke"),
    FRESH_PAIR("fresh_pair");

    companion object {
        fun decode(value: String) = entries.singleOrNull { it.wireValue == value }
            ?: c1Fail(ProductionC1Error.INVALID_VALUE)
    }
}

enum class ProductionC1AuthorizationEvidenceKind(val wireValue: String) {
    INITIAL_PAIRING("initial_pairing"),
    SAME_EPOCH_TRANSITION("same_epoch_transition"),
    DENY_ONLY_REVOCATION("deny_only_revocation"),
    DUAL_SIGNED_FRESH_PAIR("dual_signed_fresh_pair");

    companion object {
        fun decode(value: String) = entries.singleOrNull { it.wireValue == value }
            ?: c1Fail(ProductionC1Error.INVALID_VALUE)
    }
}

class ProductionC1PairStatus private constructor(
    val serviceIdDigest: String,
    val keysetVersion: ULong,
    val signingKeyId: String,
    val issuedAtMs: ULong,
    val expiresAtMs: ULong,
    val requesterRole: ProductionC1RequesterRole,
    val requestNonce: String,
    val transitionKind: ProductionC1TransitionKind,
    val previousAuthorityDigest: String?,
    val evidenceKind: ProductionC1AuthorizationEvidenceKind,
    val authorizationEvidenceDigest: String,
    val authority: ProductionPairAuthorityState,
    transitionHistory: List<ProductionPairTransitionHistoryEntry>,
    serviceSignature: ByteArray,
    validateSignatureEncoding: Boolean,
) {
    private val transitionHistoryValues = transitionHistory.toList()
    val transitionHistory: List<ProductionPairTransitionHistoryEntry> get() = transitionHistoryValues.toList()
    private val serviceSignatureBytes = serviceSignature.copyOf()
    val serviceSignature: ByteArray get() = serviceSignatureBytes.copyOf()

    init {
        listOf(serviceIdDigest, signingKeyId, requestNonce, authorizationEvidenceDigest).forEach(::c1ValidateDigest)
        previousAuthorityDigest?.let(::c1ValidateDigest)
        c1Require(
            keysetVersion > 0uL && issuedAtMs < expiresAtMs &&
                transitionHistoryValues.size <= ProductionC1Contract.MAXIMUM_TRANSITION_HISTORY_ENTRIES &&
                transitionHistoryValues.map { it.transitionId }.toSet().size == transitionHistoryValues.size &&
                transitionHistoryValues.none { it.transitionId == authority.transitionId },
            ProductionC1Error.INVALID_VALUE,
        )
        if (validateSignatureEncoding) c1ValidateCanonicalLowS(serviceSignatureBytes)
        c1Require(canonicalBytes().size <= ProductionC1Contract.MAXIMUM_PAIR_STATUS_BYTES, ProductionC1Error.LIMIT_EXCEEDED)
    }

    fun canonicalBytes(): ByteArray = C1TLV.encode(
        ProductionC1Contract.PAIR_STATUS_OBJECT_TYPE,
        claimsFields() + serviceSignatureBytes,
    )

    fun digestHex(): String = c1DigestHex(canonicalBytes())

    internal fun signingTranscript(): ByteArray = c1SignatureTranscript(
        "AetherLink G1a-C pair-status service signature v1",
        C1TLV.encode(ProductionC1Contract.PAIR_STATUS_OBJECT_TYPE, claimsFields()),
    )

    private fun claimsFields(): List<ByteArray> {
        val history = ByteArrayOutputStream().apply {
            transitionHistoryValues.forEach {
                write(c1ForceDecodeDigest(it.transitionId))
                write(c1ForceDecodeDigest(it.transitionRequestDigest))
            }
        }.toByteArray()
        return listOf(
            c1ASCII(ProductionC1Contract.SUITE), c1ASCII(serviceIdDigest), c1BE(keysetVersion),
            c1ASCII(signingKeyId), c1BE(issuedAtMs), c1BE(expiresAtMs), c1ASCII(requesterRole.wireValue),
            c1ASCII(requestNonce), c1ASCII(transitionKind.wireValue), c1OptionalDigestBytes(previousAuthorityDigest),
            c1ASCII(evidenceKind.wireValue), c1ASCII(authorizationEvidenceDigest), authority.canonicalBytes(),
            c1BE(transitionHistoryValues.size.toUInt()), history, c1ASCII(ProductionC1Contract.SIGNATURE_ALGORITHM),
        )
    }

    override fun equals(other: Any?): Boolean =
        this === other || (other is ProductionC1PairStatus && canonicalBytes().contentEquals(other.canonicalBytes()))

    override fun hashCode(): Int = canonicalBytes().contentHashCode()

    companion object {
        fun signed(
            serviceIdDigest: String,
            keysetVersion: ULong,
            issuedAtMs: ULong,
            expiresAtMs: ULong,
            requesterRole: ProductionC1RequesterRole,
            requestNonce: String,
            transitionKind: ProductionC1TransitionKind,
            previousAuthorityDigest: String?,
            evidenceKind: ProductionC1AuthorizationEvidenceKind,
            authorizationEvidenceDigest: String,
            authority: ProductionPairAuthorityState,
            transitionHistory: List<ProductionPairTransitionHistoryEntry>,
            signingPublicKey: PublicKey,
            signingPrivateKey: PrivateKey,
        ): ProductionC1PairStatus {
            val signingKeyId = c1KeyId(signingPublicKey)
            val unsigned = ProductionC1PairStatus(
                serviceIdDigest, keysetVersion, signingKeyId, issuedAtMs, expiresAtMs, requesterRole,
                requestNonce, transitionKind, previousAuthorityDigest, evidenceKind, authorizationEvidenceDigest,
                authority, transitionHistory, byteArrayOf(), false,
            )
            return ProductionC1PairStatus(
                serviceIdDigest, keysetVersion, signingKeyId, issuedAtMs, expiresAtMs, requesterRole,
                requestNonce, transitionKind, previousAuthorityDigest, evidenceKind, authorizationEvidenceDigest,
                authority, transitionHistory, c1Sign(unsigned.signingTranscript(), signingPrivateKey), true,
            ).also { c1Verify(it.serviceSignature, it.signingTranscript(), signingPublicKey) }
        }

        fun decode(data: ByteArray): ProductionC1PairStatus {
            val fields = C1TLV.decode(
                data, ProductionC1Contract.PAIR_STATUS_OBJECT_TYPE, 17,
                ProductionC1Contract.MAXIMUM_PAIR_STATUS_BYTES,
            )
            c1Require(
                c1Text(fields[0]) == ProductionC1Contract.SUITE &&
                    c1Text(fields[15]) == ProductionC1Contract.SIGNATURE_ALGORITHM,
                ProductionC1Error.INVALID_VALUE,
            )
            val count = c1UInt32(fields[13])
            c1Require(
                count <= ProductionC1Contract.MAXIMUM_TRANSITION_HISTORY_ENTRIES.toUInt() &&
                    fields[14].size == count.toInt() * 64,
                ProductionC1Error.MALFORMED_CANONICAL,
            )
            val history = List(count.toInt()) { index ->
                val base = index * 64
                ProductionPairTransitionHistoryEntry(
                    c1LowerHex(fields[14].copyOfRange(base, base + 32)),
                    c1LowerHex(fields[14].copyOfRange(base + 32, base + 64)),
                )
            }
            val result = ProductionC1PairStatus(
                c1Text(fields[1]), c1UInt64(fields[2]), c1Text(fields[3]), c1UInt64(fields[4]),
                c1UInt64(fields[5]), ProductionC1RequesterRole.decode(c1Text(fields[6])), c1Text(fields[7]),
                ProductionC1TransitionKind.decode(c1Text(fields[8])), c1OptionalDigest(fields[9]),
                ProductionC1AuthorizationEvidenceKind.decode(c1Text(fields[10])), c1Text(fields[11]),
                ProductionPairAuthorityState.decode(fields[12]), history, fields[16], true,
            )
            c1Require(result.canonicalBytes().contentEquals(data), ProductionC1Error.MALFORMED_CANONICAL)
            return result
        }
    }
}

class VerifiedProductionC1PairStatus internal constructor(
    val status: ProductionC1PairStatus,
    internal val verifiedKeyset: VerifiedProductionC1ServiceKeyset,
    provenance: Any,
) {
    init {
        c1RequireVerifiedMint(provenance)
    }
}

enum class ProductionC1ReplacementRole(
    val wireValue: String,
    internal val survivorRole: ProductionC1RequesterRole,
    internal val signerRole: ProductionC1RequesterRole,
) {
    CLIENT("client", ProductionC1RequesterRole.RUNTIME, ProductionC1RequesterRole.CLIENT),
    RUNTIME("runtime", ProductionC1RequesterRole.CLIENT, ProductionC1RequesterRole.RUNTIME);

    companion object {
        fun decode(value: String) = entries.singleOrNull { it.wireValue == value }
            ?: c1Fail(ProductionC1Error.INVALID_FRESH_PAIR)
    }
}

class ProductionC1CurrentRecoveryCommitments private constructor(
    val pairBindingDigest: String,
    val endpointTrafficSecretCommitment: String,
    val routeTokenSeedCommitment: String,
    val endpointTrafficSecretReuseDigest: String,
    val routeTokenSeedReuseDigest: String,
) {
    init {
        listOf(
            pairBindingDigest,
            endpointTrafficSecretCommitment,
            routeTokenSeedCommitment,
            endpointTrafficSecretReuseDigest,
            routeTokenSeedReuseDigest,
        ).forEach(::c1ValidateDigest)
        c1Require(
            endpointTrafficSecretCommitment != routeTokenSeedCommitment &&
                endpointTrafficSecretReuseDigest != routeTokenSeedReuseDigest,
            ProductionC1Error.INVALID_FRESH_PAIR,
        )
    }

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is ProductionC1CurrentRecoveryCommitments &&
                pairBindingDigest == other.pairBindingDigest &&
                endpointTrafficSecretCommitment == other.endpointTrafficSecretCommitment &&
                routeTokenSeedCommitment == other.routeTokenSeedCommitment &&
                endpointTrafficSecretReuseDigest == other.endpointTrafficSecretReuseDigest &&
                routeTokenSeedReuseDigest == other.routeTokenSeedReuseDigest)

    override fun hashCode(): Int {
        var result = pairBindingDigest.hashCode()
        result = 31 * result + endpointTrafficSecretCommitment.hashCode()
        result = 31 * result + routeTokenSeedCommitment.hashCode()
        result = 31 * result + endpointTrafficSecretReuseDigest.hashCode()
        return 31 * result + routeTokenSeedReuseDigest.hashCode()
    }

    companion object {
        internal fun fromSecrets(
            pairBindingDigest: String,
            endpointTrafficSecret: ByteArray,
            routeTokenSeed: ByteArray,
        ): ProductionC1CurrentRecoveryCommitments {
            val endpoint = ProductionC1RecoveryCommitments.endpointTrafficSecret(
                pairBindingDigest,
                endpointTrafficSecret,
            )
            val route = ProductionC1RecoveryCommitments.routeTokenSeed(pairBindingDigest, routeTokenSeed)
            val endpointReuse = ProductionC1RecoveryCommitments.materialReuseDigest(
                pairBindingDigest,
                endpointTrafficSecret,
            )
            val routeReuse = ProductionC1RecoveryCommitments.materialReuseDigest(
                pairBindingDigest,
                routeTokenSeed,
            )
            c1Require(
                endpoint != route && endpointReuse != routeReuse,
                ProductionC1Error.INVALID_FRESH_PAIR,
            )
            return ProductionC1CurrentRecoveryCommitments(
                pairBindingDigest,
                endpoint,
                route,
                endpointReuse,
                routeReuse,
            )
        }
    }
}

object ProductionC1RecoveryCommitments {
    const val MINIMUM_SECRET_BYTES = 32
    const val MAXIMUM_SECRET_BYTES = 512

    fun endpointTrafficSecret(pairBindingDigest: String, rawSecret: ByteArray): String {
        val reuseDigest = materialReuseDigest(pairBindingDigest, rawSecret)
        return endpointTrafficSecret(pairBindingDigest, reuseDigest)
    }

    fun routeTokenSeed(pairBindingDigest: String, rawSecret: ByteArray): String {
        val reuseDigest = materialReuseDigest(pairBindingDigest, rawSecret)
        return routeTokenSeed(pairBindingDigest, reuseDigest)
    }

    fun currentToken(
        pairBindingDigest: String,
        endpointTrafficSecret: ByteArray,
        routeTokenSeed: ByteArray,
    ): ProductionC1CurrentRecoveryCommitments =
        ProductionC1CurrentRecoveryCommitments.fromSecrets(
            pairBindingDigest,
            endpointTrafficSecret,
            routeTokenSeed,
        )

    fun materialReuseDigest(pairBindingDigest: String, rawSecret: ByteArray): String =
        rawSecretCommitment(
            "AetherLink G1a-C secret-material reuse commitment v1",
            pairBindingDigest,
            rawSecret,
        )

    internal fun endpointTrafficSecret(
        pairBindingDigest: String,
        materialReuseDigest: String,
    ): String = purposeCommitment(
        "AetherLink G1a-C endpoint-traffic-secret commitment v1",
        pairBindingDigest,
        materialReuseDigest,
    )

    internal fun routeTokenSeed(
        pairBindingDigest: String,
        materialReuseDigest: String,
    ): String = purposeCommitment(
        "AetherLink G1a-C route-" + "token-seed commitment v1",
        pairBindingDigest,
        materialReuseDigest,
    )

    private fun rawSecretCommitment(
        domain: String,
        pairBindingDigest: String,
        rawSecret: ByteArray,
    ): String {
        c1ValidateDigest(pairBindingDigest)
        c1Require(
            rawSecret.size in MINIMUM_SECRET_BYTES..MAXIMUM_SECRET_BYTES,
            ProductionC1Error.LIMIT_EXCEEDED,
        )
        val claims = ByteArrayOutputStream().apply {
            write(c1ForceDecodeDigest(pairBindingDigest))
            write(c1BE(rawSecret.size.toUInt()))
            write(rawSecret)
        }.toByteArray()
        return c1DigestHex(c1SignatureTranscript(domain, claims))
    }

    private fun purposeCommitment(
        domain: String,
        pairBindingDigest: String,
        materialReuseDigest: String,
    ): String {
        c1ValidateDigest(pairBindingDigest)
        c1ValidateDigest(materialReuseDigest)
        val claims = c1ForceDecodeDigest(pairBindingDigest) +
            c1ForceDecodeDigest(materialReuseDigest)
        return c1DigestHex(c1SignatureTranscript(domain, claims))
    }
}

class ProductionC1FreshPairProof private constructor(
    val transitionId: String,
    val replacementRole: ProductionC1ReplacementRole,
    val previousAuthorityDigest: String,
    val previousPairBindingDigest: String,
    val nextPairBindingDigest: String,
    val previousPairEpoch: ULong,
    val nextPairEpoch: ULong,
    val previousClientIdentityFingerprint: String,
    val nextClientIdentityFingerprint: String,
    val previousRuntimeIdentityFingerprint: String,
    val nextRuntimeIdentityFingerprint: String,
    val nextGeneration: ULong,
    val nextServiceConfigVersion: ULong,
    val nextKeysetVersion: ULong,
    val nextRevocationCounter: ULong,
    val nextProtocolFloor: UInt,
    val nextAuthorityRevision: ULong,
    val issuedAtMs: ULong,
    val expiresAtMs: ULong,
    val freshPairingRequestDigest: String,
    val freshPairingResultDigest: String,
    val freshTransportBindingDigest: String,
    val previousEndpointTrafficSecretCommitment: String,
    val nextEndpointTrafficSecretCommitment: String,
    val previousRouteTokenSeedCommitment: String,
    val nextRouteTokenSeedCommitment: String,
    val previousEndpointTrafficSecretReuseDigest: String,
    val nextEndpointTrafficSecretReuseDigest: String,
    val previousRouteTokenSeedReuseDigest: String,
    val nextRouteTokenSeedReuseDigest: String,
    survivorSignature: ByteArray,
    replacementSignature: ByteArray,
    validateSignatureEncoding: Boolean,
) {
    private val survivorSignatureBytes = survivorSignature.copyOf()
    private val replacementSignatureBytes = replacementSignature.copyOf()
    val survivorSignature: ByteArray get() = survivorSignatureBytes.copyOf()
    val replacementSignature: ByteArray get() = replacementSignatureBytes.copyOf()

    init {
        listOf(
            transitionId,
            previousAuthorityDigest,
            previousPairBindingDigest,
            nextPairBindingDigest,
            previousClientIdentityFingerprint,
            nextClientIdentityFingerprint,
            previousRuntimeIdentityFingerprint,
            nextRuntimeIdentityFingerprint,
            freshPairingRequestDigest,
            freshPairingResultDigest,
            freshTransportBindingDigest,
            previousEndpointTrafficSecretCommitment,
            nextEndpointTrafficSecretCommitment,
            previousRouteTokenSeedCommitment,
            nextRouteTokenSeedCommitment,
            previousEndpointTrafficSecretReuseDigest,
            nextEndpointTrafficSecretReuseDigest,
            previousRouteTokenSeedReuseDigest,
            nextRouteTokenSeedReuseDigest,
        ).forEach(::c1ValidateDigest)
        val expectedPreviousEndpoint = ProductionC1RecoveryCommitments.endpointTrafficSecret(
            previousPairBindingDigest,
            previousEndpointTrafficSecretReuseDigest,
        )
        val expectedNextEndpoint = ProductionC1RecoveryCommitments.endpointTrafficSecret(
            nextPairBindingDigest,
            nextEndpointTrafficSecretReuseDigest,
        )
        val expectedPreviousRoute = ProductionC1RecoveryCommitments.routeTokenSeed(
            previousPairBindingDigest,
            previousRouteTokenSeedReuseDigest,
        )
        val expectedNextRoute = ProductionC1RecoveryCommitments.routeTokenSeed(
            nextPairBindingDigest,
            nextRouteTokenSeedReuseDigest,
        )
        c1Require(
            previousPairEpoch > 0uL &&
                previousPairEpoch < ULong.MAX_VALUE &&
                nextPairEpoch == previousPairEpoch + 1uL &&
                previousPairBindingDigest == nextPairBindingDigest &&
                nextGeneration > 0uL &&
                nextServiceConfigVersion > 0uL &&
                nextKeysetVersion > 0uL &&
                nextProtocolFloor > 0u &&
                nextAuthorityRevision > 1uL &&
                issuedAtMs < expiresAtMs &&
                freshPairingRequestDigest != freshPairingResultDigest &&
                previousEndpointTrafficSecretCommitment == expectedPreviousEndpoint &&
                nextEndpointTrafficSecretCommitment == expectedNextEndpoint &&
                previousRouteTokenSeedCommitment == expectedPreviousRoute &&
                nextRouteTokenSeedCommitment == expectedNextRoute &&
                previousEndpointTrafficSecretCommitment != nextEndpointTrafficSecretCommitment &&
                previousRouteTokenSeedCommitment != nextRouteTokenSeedCommitment &&
                previousEndpointTrafficSecretCommitment != previousRouteTokenSeedCommitment &&
                nextEndpointTrafficSecretCommitment != nextRouteTokenSeedCommitment &&
                setOf(
                    previousEndpointTrafficSecretReuseDigest,
                    nextEndpointTrafficSecretReuseDigest,
                    previousRouteTokenSeedReuseDigest,
                    nextRouteTokenSeedReuseDigest,
                ).size == 4,
            ProductionC1Error.INVALID_FRESH_PAIR,
        )
        val clientChanged = previousClientIdentityFingerprint != nextClientIdentityFingerprint
        val runtimeChanged = previousRuntimeIdentityFingerprint != nextRuntimeIdentityFingerprint
        c1Require(
            clientChanged != runtimeChanged &&
                (replacementRole == ProductionC1ReplacementRole.CLIENT) == clientChanged &&
                previousClientIdentityFingerprint != previousRuntimeIdentityFingerprint &&
                nextClientIdentityFingerprint != nextRuntimeIdentityFingerprint,
            ProductionC1Error.INVALID_FRESH_PAIR,
        )
        if (validateSignatureEncoding) {
            c1ValidateCanonicalLowS(survivorSignatureBytes)
            c1ValidateCanonicalLowS(replacementSignatureBytes)
        }
        c1Require(
            canonicalBytes().size <= ProductionC1Contract.MAXIMUM_FRESH_PAIR_PROOF_BYTES,
            ProductionC1Error.LIMIT_EXCEEDED,
        )
    }

    val transitionRequestDigest: String
        get() = c1DigestHex(
            C1TLV.encode(
                ProductionC1Contract.FRESH_PAIR_PROOF_OBJECT_TYPE,
                claimsFields(),
            )
        )

    fun canonicalBytes(): ByteArray = C1TLV.encode(
        ProductionC1Contract.FRESH_PAIR_PROOF_OBJECT_TYPE,
        claimsFields() + listOf(survivorSignatureBytes, replacementSignatureBytes),
    )

    fun digestHex(): String = c1DigestHex(canonicalBytes())

    internal fun survivorSigningTranscript(): ByteArray = c1SignatureTranscript(
        "AetherLink G1a-C fresh-pair survivor ${replacementRole.survivorRole.wireValue} signature v1",
        C1TLV.encode(ProductionC1Contract.FRESH_PAIR_PROOF_OBJECT_TYPE, claimsFields()),
    )

    internal fun replacementSigningTranscript(): ByteArray = c1SignatureTranscript(
        "AetherLink G1a-C fresh-pair replacement ${replacementRole.signerRole.wireValue} signature v1",
        C1TLV.encode(ProductionC1Contract.FRESH_PAIR_PROOF_OBJECT_TYPE, claimsFields()),
    )

    private fun claimsFields(): List<ByteArray> = listOf(
        c1ASCII(ProductionC1Contract.SUITE),
        c1ASCII(transitionId),
        c1ASCII(replacementRole.wireValue),
        c1ASCII(previousAuthorityDigest),
        c1ASCII(previousPairBindingDigest),
        c1ASCII(nextPairBindingDigest),
        c1BE(previousPairEpoch),
        c1BE(nextPairEpoch),
        c1ASCII(previousClientIdentityFingerprint),
        c1ASCII(nextClientIdentityFingerprint),
        c1ASCII(previousRuntimeIdentityFingerprint),
        c1ASCII(nextRuntimeIdentityFingerprint),
        c1BE(nextGeneration),
        c1BE(nextServiceConfigVersion),
        c1BE(nextKeysetVersion),
        c1BE(nextRevocationCounter),
        c1BE(nextProtocolFloor),
        c1BE(nextAuthorityRevision),
        c1BE(issuedAtMs),
        c1BE(expiresAtMs),
        c1ASCII(freshPairingRequestDigest),
        c1ASCII(freshPairingResultDigest),
        c1ASCII(freshTransportBindingDigest),
        c1ASCII(previousEndpointTrafficSecretCommitment),
        c1ASCII(nextEndpointTrafficSecretCommitment),
        c1ASCII(previousRouteTokenSeedCommitment),
        c1ASCII(nextRouteTokenSeedCommitment),
        c1ASCII(previousEndpointTrafficSecretReuseDigest),
        c1ASCII(nextEndpointTrafficSecretReuseDigest),
        c1ASCII(previousRouteTokenSeedReuseDigest),
        c1ASCII(nextRouteTokenSeedReuseDigest),
        c1ASCII(ProductionC1Contract.SIGNATURE_ALGORITHM),
        c1ASCII(replacementRole.survivorRole.wireValue),
        c1ASCII(replacementRole.signerRole.wireValue),
    )

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is ProductionC1FreshPairProof && canonicalBytes().contentEquals(other.canonicalBytes()))

    override fun hashCode(): Int = canonicalBytes().contentHashCode()

    companion object {
        fun signed(
            transitionId: String,
            replacementRole: ProductionC1ReplacementRole,
            previousAuthority: ProductionPairAuthorityState,
            nextClientIdentityFingerprint: String,
            nextRuntimeIdentityFingerprint: String,
            nextGeneration: ULong,
            nextServiceConfigVersion: ULong,
            nextKeysetVersion: ULong,
            nextRevocationCounter: ULong,
            nextProtocolFloor: UInt,
            issuedAtMs: ULong,
            expiresAtMs: ULong,
            freshPairingRequestDigest: String,
            freshPairingResultDigest: String,
            freshTransportBindingDigest: String,
            currentCommitments: ProductionC1CurrentRecoveryCommitments,
            nextEndpointTrafficSecret: ByteArray,
            nextRouteTokenSeed: ByteArray,
            survivorPublicKey: PublicKey,
            survivorPrivateKey: PrivateKey,
            replacementPublicKey: PublicKey,
            replacementPrivateKey: PrivateKey,
        ): ProductionC1FreshPairProof {
            c1Require(
                previousAuthority.pairEpoch < ULong.MAX_VALUE &&
                    previousAuthority.authorityRevision < ULong.MAX_VALUE,
                ProductionC1Error.INVALID_FRESH_PAIR,
            )
            c1Require(
                currentCommitments.pairBindingDigest == previousAuthority.pairBindingDigest,
                ProductionC1Error.INVALID_FRESH_PAIR,
            )
            val nextEndpointCommitment = ProductionC1RecoveryCommitments.endpointTrafficSecret(
                previousAuthority.pairBindingDigest,
                nextEndpointTrafficSecret,
            )
            val nextRouteCommitment = ProductionC1RecoveryCommitments.routeTokenSeed(
                previousAuthority.pairBindingDigest,
                nextRouteTokenSeed,
            )
            val nextEndpointReuse = ProductionC1RecoveryCommitments.materialReuseDigest(
                previousAuthority.pairBindingDigest,
                nextEndpointTrafficSecret,
            )
            val nextRouteReuse = ProductionC1RecoveryCommitments.materialReuseDigest(
                previousAuthority.pairBindingDigest,
                nextRouteTokenSeed,
            )
            val unsigned = ProductionC1FreshPairProof(
                transitionId,
                replacementRole,
                previousAuthority.digestHex(),
                previousAuthority.pairBindingDigest,
                previousAuthority.pairBindingDigest,
                previousAuthority.pairEpoch,
                previousAuthority.pairEpoch + 1uL,
                previousAuthority.clientIdentityFingerprint,
                nextClientIdentityFingerprint,
                previousAuthority.runtimeIdentityFingerprint,
                nextRuntimeIdentityFingerprint,
                nextGeneration,
                nextServiceConfigVersion,
                nextKeysetVersion,
                nextRevocationCounter,
                nextProtocolFloor,
                previousAuthority.authorityRevision + 1uL,
                issuedAtMs,
                expiresAtMs,
                freshPairingRequestDigest,
                freshPairingResultDigest,
                freshTransportBindingDigest,
                currentCommitments.endpointTrafficSecretCommitment,
                nextEndpointCommitment,
                currentCommitments.routeTokenSeedCommitment,
                nextRouteCommitment,
                currentCommitments.endpointTrafficSecretReuseDigest,
                nextEndpointReuse,
                currentCommitments.routeTokenSeedReuseDigest,
                nextRouteReuse,
                byteArrayOf(),
                byteArrayOf(),
                false,
            )
            return ProductionC1FreshPairProof(
                unsigned.transitionId,
                unsigned.replacementRole,
                unsigned.previousAuthorityDigest,
                unsigned.previousPairBindingDigest,
                unsigned.nextPairBindingDigest,
                unsigned.previousPairEpoch,
                unsigned.nextPairEpoch,
                unsigned.previousClientIdentityFingerprint,
                unsigned.nextClientIdentityFingerprint,
                unsigned.previousRuntimeIdentityFingerprint,
                unsigned.nextRuntimeIdentityFingerprint,
                unsigned.nextGeneration,
                unsigned.nextServiceConfigVersion,
                unsigned.nextKeysetVersion,
                unsigned.nextRevocationCounter,
                unsigned.nextProtocolFloor,
                unsigned.nextAuthorityRevision,
                unsigned.issuedAtMs,
                unsigned.expiresAtMs,
                unsigned.freshPairingRequestDigest,
                unsigned.freshPairingResultDigest,
                unsigned.freshTransportBindingDigest,
                unsigned.previousEndpointTrafficSecretCommitment,
                unsigned.nextEndpointTrafficSecretCommitment,
                unsigned.previousRouteTokenSeedCommitment,
                unsigned.nextRouteTokenSeedCommitment,
                unsigned.previousEndpointTrafficSecretReuseDigest,
                unsigned.nextEndpointTrafficSecretReuseDigest,
                unsigned.previousRouteTokenSeedReuseDigest,
                unsigned.nextRouteTokenSeedReuseDigest,
                c1Sign(unsigned.survivorSigningTranscript(), survivorPrivateKey),
                c1Sign(unsigned.replacementSigningTranscript(), replacementPrivateKey),
                true,
            ).also {
                c1Verify(it.survivorSignature, it.survivorSigningTranscript(), survivorPublicKey)
                c1Verify(it.replacementSignature, it.replacementSigningTranscript(), replacementPublicKey)
            }
        }

        fun decode(data: ByteArray): ProductionC1FreshPairProof {
            val fields = C1TLV.decode(
                data,
                ProductionC1Contract.FRESH_PAIR_PROOF_OBJECT_TYPE,
                36,
                ProductionC1Contract.MAXIMUM_FRESH_PAIR_PROOF_BYTES,
            )
            val replacement = ProductionC1ReplacementRole.decode(c1Text(fields[2]))
            c1Require(
                c1Text(fields[0]) == ProductionC1Contract.SUITE &&
                    c1Text(fields[31]) == ProductionC1Contract.SIGNATURE_ALGORITHM &&
                    c1Text(fields[32]) == replacement.survivorRole.wireValue &&
                    c1Text(fields[33]) == replacement.signerRole.wireValue,
                ProductionC1Error.INVALID_FRESH_PAIR,
            )
            return ProductionC1FreshPairProof(
                c1Text(fields[1]),
                replacement,
                c1Text(fields[3]),
                c1Text(fields[4]),
                c1Text(fields[5]),
                c1UInt64(fields[6]),
                c1UInt64(fields[7]),
                c1Text(fields[8]),
                c1Text(fields[9]),
                c1Text(fields[10]),
                c1Text(fields[11]),
                c1UInt64(fields[12]),
                c1UInt64(fields[13]),
                c1UInt64(fields[14]),
                c1UInt64(fields[15]),
                c1UInt32(fields[16]),
                c1UInt64(fields[17]),
                c1UInt64(fields[18]),
                c1UInt64(fields[19]),
                c1Text(fields[20]),
                c1Text(fields[21]),
                c1Text(fields[22]),
                c1Text(fields[23]),
                c1Text(fields[24]),
                c1Text(fields[25]),
                c1Text(fields[26]),
                c1Text(fields[27]),
                c1Text(fields[28]),
                c1Text(fields[29]),
                c1Text(fields[30]),
                fields[34],
                fields[35],
                true,
            ).also {
                c1Require(it.canonicalBytes().contentEquals(data), ProductionC1Error.MALFORMED_CANONICAL)
            }
        }
    }
}

class ProductionC1FreshPairApplyPreparation internal constructor(
    val expectedPreviousAuthorityDigest: String,
    val expectedPreviousSnapshotDigest: String,
    val nextAuthority: ProductionPairAuthorityState,
    nextTransitionHistory: List<ProductionPairTransitionHistoryEntry>,
    nextSnapshot: ProductionPairStateSnapshot,
) {
    private val nextTransitionHistoryValues = nextTransitionHistory.toList()
    private val nextSnapshotBytes = nextSnapshot.canonicalBytes().copyOf()
    val nextTransitionHistory: List<ProductionPairTransitionHistoryEntry>
        get() = nextTransitionHistoryValues.toList()
    val nextSnapshot: ProductionPairStateSnapshot
        get() = ProductionPairStateSnapshot.decode(nextSnapshotBytes.copyOf())

    init {
        c1ValidateDigest(expectedPreviousAuthorityDigest)
        c1ValidateDigest(expectedPreviousSnapshotDigest)
        c1Require(
            nextSnapshot.authority == nextAuthority &&
                nextSnapshot.transitionHistory == nextTransitionHistoryValues,
            ProductionC1Error.STATE_MISMATCH,
        )
    }
}

class VerifiedProductionC1FreshPairTransition internal constructor(
    val proof: ProductionC1FreshPairProof,
    internal val verifiedStatus: VerifiedProductionC1PairStatus,
    val applyPreparation: ProductionC1FreshPairApplyPreparation,
    provenance: Any,
) {
    init {
        c1RequireVerifiedMint(provenance)
    }

    val status: ProductionC1PairStatus get() = verifiedStatus.status
}

object ProductionC1FreshPairStateMachine {
    fun apply(
        verified: VerifiedProductionC1FreshPairTransition,
        current: ProductionPairStateSnapshot,
        nowMs: ULong,
    ): ProductionPairStateTransitionResult {
        c1ValidateFreshPairTransitionUse(verified, nowMs)
        val preparation = verified.applyPreparation
        if (current.digestHex() == preparation.nextSnapshot.digestHex()) {
            return ProductionPairStateTransitionResult(
                ProductionPairStateTransitionDisposition.IDEMPOTENT,
                current,
            )
        }
        c1Require(
            current.authority.digestHex() == preparation.expectedPreviousAuthorityDigest &&
                current.digestHex() == preparation.expectedPreviousSnapshotDigest,
            ProductionC1Error.STATE_MISMATCH,
        )
        return ProductionPairStateTransitionResult(
            ProductionPairStateTransitionDisposition.APPLIED,
            preparation.nextSnapshot,
        )
    }
}

enum class ProductionC1RouteKind(
    val wireValue: String,
    internal val connectorObjectType: Int,
    internal val authorizationObjectType: Int,
    internal val transcriptKind: ProductionRouteAuthorizationKind,
) {
    P2P_DIRECT(
        "verified_p2p_direct_v1",
        ProductionC1Contract.P2P_CONNECTOR_OBJECT_TYPE,
        ProductionC1Contract.P2P_ROUTE_AUTHORIZATION_OBJECT_TYPE,
        ProductionRouteAuthorizationKind.P2P_DIRECT,
    ),
    TURN_RELAY(
        "verified_turn_relay_v1",
        ProductionC1Contract.TURN_CONNECTOR_OBJECT_TYPE,
        ProductionC1Contract.TURN_ROUTE_AUTHORIZATION_OBJECT_TYPE,
        ProductionRouteAuthorizationKind.TURN_RELAY,
    ),
    SEALED_RELAY(
        "verified_sealed_relay_v1",
        ProductionC1Contract.SEALED_RELAY_CONNECTOR_OBJECT_TYPE,
        ProductionC1Contract.SEALED_RELAY_ROUTE_AUTHORIZATION_OBJECT_TYPE,
        ProductionRouteAuthorizationKind.SEALED_RELAY,
    );

    companion object {
        fun decode(value: String) = entries.singleOrNull { it.wireValue == value }
            ?: c1Fail(ProductionC1Error.INVALID_VALUE)
        internal fun decodeConnectorObjectType(value: Int) = entries.singleOrNull { it.connectorObjectType == value }
            ?: c1Fail(ProductionC1Error.MALFORMED_CANONICAL)
        internal fun decodeAuthorizationObjectType(value: Int) = entries.singleOrNull { it.authorizationObjectType == value }
            ?: c1Fail(ProductionC1Error.MALFORMED_CANONICAL)
        internal fun fromTranscriptKind(value: ProductionRouteAuthorizationKind): ProductionC1RouteKind? =
            entries.singleOrNull { it.transcriptKind == value }
    }
}

class ProductionC1PreauthorizationSessionContext(
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
    val routeKind: ProductionC1RouteKind,
) {
    private val clientEphemeralPublicKeyBytes = clientEphemeralPublicKey.copyOf()
    private val runtimeEphemeralPublicKeyBytes = runtimeEphemeralPublicKey.copyOf()
    val clientEphemeralPublicKey: ByteArray get() = clientEphemeralPublicKeyBytes.copyOf()
    val runtimeEphemeralPublicKey: ByteArray get() = runtimeEphemeralPublicKeyBytes.copyOf()

    init {
        c1Require(c1DecodeLowerHex(sessionId)?.size == 16, ProductionC1Error.INVALID_VALUE)
        c1Require(c1DecodeLowerHex(clientNonce)?.size == 16, ProductionC1Error.INVALID_VALUE)
        c1Require(c1DecodeLowerHex(runtimeNonce)?.size == 16, ProductionC1Error.INVALID_VALUE)
        listOf(
            pairBindingDigest,
            clientIdentityFingerprint,
            runtimeIdentityFingerprint,
        ).forEach(::c1ValidateDigest)
        c1PublicKey(clientEphemeralPublicKeyBytes)
        c1PublicKey(runtimeEphemeralPublicKeyBytes)
        c1Require(
            pairEpoch > 0uL &&
                generation > 0uL &&
                serviceConfigVersion > 0uL &&
                keysetVersion > 0uL &&
                clientIdentityFingerprint != runtimeIdentityFingerprint &&
                !clientEphemeralPublicKeyBytes.contentEquals(runtimeEphemeralPublicKeyBytes) &&
                clientNonce != runtimeNonce,
            ProductionC1Error.INVALID_VALUE,
        )
        c1Require(
            canonicalBytes().size <= ProductionC1Contract.MAXIMUM_PREAUTHORIZATION_SESSION_CONTEXT_BYTES,
            ProductionC1Error.LIMIT_EXCEEDED,
        )
    }

    constructor(transcript: ProductionSecureSessionTranscript) : this(
        sessionId = transcript.sessionId,
        pairBindingDigest = transcript.pairBindingDigest,
        pairEpoch = transcript.pairEpoch,
        clientIdentityFingerprint = transcript.clientIdentityFingerprint,
        runtimeIdentityFingerprint = transcript.runtimeIdentityFingerprint,
        clientEphemeralPublicKey = transcript.clientEphemeralPublicKey,
        runtimeEphemeralPublicKey = transcript.runtimeEphemeralPublicKey,
        clientNonce = transcript.clientNonce,
        runtimeNonce = transcript.runtimeNonce,
        generation = transcript.generation,
        serviceConfigVersion = transcript.serviceConfigVersion,
        keysetVersion = transcript.keysetVersion,
        revocationCounter = transcript.revocationCounter,
        routeKind = ProductionC1RouteKind.fromTranscriptKind(transcript.routeAuthorizationKind)
            ?: c1Fail(ProductionC1Error.ROUTE_MISMATCH),
    )

    fun canonicalBytes(): ByteArray = C1TLV.encode(
        ProductionC1Contract.PREAUTHORIZATION_SESSION_CONTEXT_OBJECT_TYPE,
        listOf(
            c1ASCII(ProductionC1Contract.SUITE),
            c1BE(REVISION),
            c1ASCII(sessionId),
            c1ASCII(pairBindingDigest),
            c1BE(pairEpoch),
            c1ASCII(clientIdentityFingerprint),
            c1ASCII(runtimeIdentityFingerprint),
            c1ASCII("client"),
            c1ASCII("runtime"),
            clientEphemeralPublicKeyBytes,
            runtimeEphemeralPublicKeyBytes,
            c1ASCII(clientNonce),
            c1ASCII(runtimeNonce),
            c1BE(generation),
            c1BE(serviceConfigVersion),
            c1BE(keysetVersion),
            c1BE(revocationCounter),
            c1BE(PROTOCOL_VERSION),
            c1BE(MINIMUM_PROTOCOL_VERSION),
            c1ASCII(ProductionSecureSessionContract.PROFILE),
            c1ASCII(routeKind.wireValue),
        ),
    )

    fun digestHex(): String = c1DigestHex(canonicalBytes())

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is ProductionC1PreauthorizationSessionContext &&
                canonicalBytes().contentEquals(other.canonicalBytes()))

    override fun hashCode(): Int = canonicalBytes().contentHashCode()

    companion object {
        const val REVISION: ULong = 1uL
        internal const val PROTOCOL_VERSION: UInt = 1u
        internal const val MINIMUM_PROTOCOL_VERSION: UInt = 1u

        fun decode(data: ByteArray): ProductionC1PreauthorizationSessionContext {
            val fields = C1TLV.decode(
                data,
                ProductionC1Contract.PREAUTHORIZATION_SESSION_CONTEXT_OBJECT_TYPE,
                21,
                ProductionC1Contract.MAXIMUM_PREAUTHORIZATION_SESSION_CONTEXT_BYTES,
            )
            c1Require(
                c1Text(fields[0]) == ProductionC1Contract.SUITE &&
                    c1UInt64(fields[1]) == REVISION &&
                    c1Text(fields[7]) == "client" &&
                    c1Text(fields[8]) == "runtime" &&
                    c1UInt32(fields[17]) == PROTOCOL_VERSION &&
                    c1UInt32(fields[18]) == MINIMUM_PROTOCOL_VERSION &&
                    c1Text(fields[19]) == ProductionSecureSessionContract.PROFILE,
                ProductionC1Error.INVALID_VALUE,
            )
            return ProductionC1PreauthorizationSessionContext(
                c1Text(fields[2]),
                c1Text(fields[3]),
                c1UInt64(fields[4]),
                c1Text(fields[5]),
                c1Text(fields[6]),
                fields[9],
                fields[10],
                c1Text(fields[11]),
                c1Text(fields[12]),
                c1UInt64(fields[13]),
                c1UInt64(fields[14]),
                c1UInt64(fields[15]),
                c1UInt64(fields[16]),
                ProductionC1RouteKind.decode(c1Text(fields[20])),
            ).also {
                c1Require(it.canonicalBytes().contentEquals(data), ProductionC1Error.MALFORMED_CANONICAL)
            }
        }
    }
}

enum class ProductionC1RouteTransport(val wireValue: String) {
    UDP("udp"),
    TLS_TCP("tls_tcp");

    companion object {
        fun decode(value: String) = entries.singleOrNull { it.wireValue == value }
            ?: c1Fail(ProductionC1Error.INVALID_VALUE)
    }
}

class ProductionC1RouteConnectorMaterial(
    val kind: ProductionC1RouteKind,
    addressBytes: ByteArray,
    val port: UShort,
    val serverName: String?,
    val transport: ProductionC1RouteTransport,
    val routeHandleDigest: String,
    val credentialCommitmentDigest: String,
    val pathReceiptDigest: String,
    val leaseDigest: String? = null,
    val allocationDigest: String? = null,
) {
    private val address = addressBytes.copyOf()
    val addressBytes: ByteArray get() = address.copyOf()

    init {
        listOf(routeHandleDigest, credentialCommitmentDigest, pathReceiptDigest).forEach(::c1ValidateDigest)
        leaseDigest?.let(::c1ValidateDigest)
        allocationDigest?.let(::c1ValidateDigest)
        c1Require(
            (address.size == 4 || address.size == 16) && port > 0u &&
                (serverName == null || c1IsCanonicalServerName(serverName)),
            ProductionC1Error.INVALID_VALUE,
        )
        when (kind) {
            ProductionC1RouteKind.P2P_DIRECT -> c1Require(
                serverName == null && transport == ProductionC1RouteTransport.UDP &&
                    leaseDigest == null && allocationDigest == null,
                ProductionC1Error.INVALID_VALUE,
            )
            ProductionC1RouteKind.TURN_RELAY,
            ProductionC1RouteKind.SEALED_RELAY,
            -> c1Require(
                serverName != null && transport == ProductionC1RouteTransport.TLS_TCP &&
                    leaseDigest != null && allocationDigest != null,
                ProductionC1Error.INVALID_VALUE,
            )
        }
        c1Require(canonicalBytes().size <= ProductionC1Contract.MAXIMUM_CONNECTOR_BYTES, ProductionC1Error.LIMIT_EXCEEDED)
    }

    fun canonicalBytes(): ByteArray = C1TLV.encode(
        kind.connectorObjectType,
        listOf(
            c1ASCII(ProductionC1Contract.SUITE), c1ASCII(kind.wireValue), address, c1BE(port),
            c1ASCII(serverName ?: "none"), c1ASCII(transport.wireValue), c1ASCII(routeHandleDigest),
            c1ASCII(credentialCommitmentDigest), c1ASCII(pathReceiptDigest), c1OptionalDigestBytes(leaseDigest),
            c1OptionalDigestBytes(allocationDigest),
        ),
    )

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is ProductionC1RouteConnectorMaterial && canonicalBytes().contentEquals(other.canonicalBytes()))

    override fun hashCode(): Int = canonicalBytes().contentHashCode()

    companion object {
        fun decode(data: ByteArray): ProductionC1RouteConnectorMaterial {
            val kind = ProductionC1RouteKind.decodeConnectorObjectType(C1TLV.peekObjectType(data))
            val fields = C1TLV.decode(
                data, kind.connectorObjectType, 11, ProductionC1Contract.MAXIMUM_CONNECTOR_BYTES,
            )
            c1Require(
                c1Text(fields[0]) == ProductionC1Contract.SUITE && c1Text(fields[1]) == kind.wireValue,
                ProductionC1Error.INVALID_VALUE,
            )
            val server = c1Text(fields[4])
            val result = ProductionC1RouteConnectorMaterial(
                kind, fields[2], c1UInt16(fields[3]), server.takeUnless { it == "none" },
                ProductionC1RouteTransport.decode(c1Text(fields[5])), c1Text(fields[6]), c1Text(fields[7]),
                c1Text(fields[8]), c1OptionalDigest(fields[9]), c1OptionalDigest(fields[10]),
            )
            c1Require(result.canonicalBytes().contentEquals(data), ProductionC1Error.MALFORMED_CANONICAL)
            return result
        }
    }
}

data class ProductionC1RoutePlanClaims(
    val planId: String,
    val kind: ProductionC1RouteKind,
    val pairAuthorityDigest: String,
    val pairBindingDigest: String,
    val pairEpoch: ULong,
    val generation: ULong,
    val clientIdentityFingerprint: String,
    val runtimeIdentityFingerprint: String,
    val connector: ProductionC1RouteConnectorMaterial,
    val securityContextDigest: String,
    val selectedPathReceiptDigest: String,
    val notBeforeMs: ULong,
    val expiresAtMs: ULong,
) {
    init {
        listOf(
            planId, pairAuthorityDigest, pairBindingDigest, clientIdentityFingerprint,
            runtimeIdentityFingerprint, securityContextDigest, selectedPathReceiptDigest,
        ).forEach(::c1ValidateDigest)
        c1Require(
            pairEpoch > 0uL && generation > 0uL &&
                clientIdentityFingerprint != runtimeIdentityFingerprint && connector.kind == kind &&
                connector.pathReceiptDigest == selectedPathReceiptDigest && notBeforeMs < expiresAtMs,
            ProductionC1Error.INVALID_VALUE,
        )
        c1Require(canonicalBytes().size <= ProductionC1Contract.MAXIMUM_ROUTE_PLAN_BYTES, ProductionC1Error.LIMIT_EXCEEDED)
    }

    fun canonicalBytes(): ByteArray = C1TLV.encode(
        ProductionC1Contract.ROUTE_PLAN_OBJECT_TYPE,
        listOf(
            c1ASCII(ProductionC1Contract.SUITE), c1ASCII(planId), c1BE(REVISION), c1ASCII(kind.wireValue),
            c1ASCII(pairAuthorityDigest), c1ASCII(pairBindingDigest), c1BE(pairEpoch), c1BE(generation),
            c1ASCII(clientIdentityFingerprint), c1ASCII(runtimeIdentityFingerprint), connector.canonicalBytes(),
            c1ASCII(securityContextDigest), c1ASCII(selectedPathReceiptDigest), c1BE(notBeforeMs), c1BE(expiresAtMs),
        ),
    )

    fun digestHex(): String = c1DigestHex(canonicalBytes())

    companion object {
        const val REVISION: ULong = 1uL

        fun decode(data: ByteArray): ProductionC1RoutePlanClaims {
            val fields = C1TLV.decode(
                data, ProductionC1Contract.ROUTE_PLAN_OBJECT_TYPE, 15,
                ProductionC1Contract.MAXIMUM_ROUTE_PLAN_BYTES,
            )
            c1Require(
                c1Text(fields[0]) == ProductionC1Contract.SUITE && c1UInt64(fields[2]) == REVISION,
                ProductionC1Error.INVALID_VALUE,
            )
            return ProductionC1RoutePlanClaims(
                c1Text(fields[1]), ProductionC1RouteKind.decode(c1Text(fields[3])), c1Text(fields[4]),
                c1Text(fields[5]), c1UInt64(fields[6]), c1UInt64(fields[7]), c1Text(fields[8]),
                c1Text(fields[9]), ProductionC1RouteConnectorMaterial.decode(fields[10]), c1Text(fields[11]),
                c1Text(fields[12]), c1UInt64(fields[13]), c1UInt64(fields[14]),
            ).also {
                c1Require(it.canonicalBytes().contentEquals(data), ProductionC1Error.MALFORMED_CANONICAL)
            }
        }
    }
}

class ProductionC1RouteCapability private constructor(
    val serviceIdDigest: String,
    val keysetVersion: ULong,
    val signingKeyId: String,
    val capabilityId: String,
    val issuedAtMs: ULong,
    val notBeforeMs: ULong,
    val expiresAtMs: ULong,
    val pairAuthorityDigest: String,
    val pairBindingDigest: String,
    val pairEpoch: ULong,
    val clientIdentityFingerprint: String,
    val runtimeIdentityFingerprint: String,
    val generation: ULong,
    val serviceConfigVersion: ULong,
    val revocationCounter: ULong,
    val protocolFloor: UInt,
    val kind: ProductionC1RouteKind,
    val routePlanClaimsDigest: String,
    val maxUses: UInt,
    serviceSignature: ByteArray,
    validateSignatureEncoding: Boolean,
) {
    private val serviceSignatureBytes = serviceSignature.copyOf()
    val serviceSignature: ByteArray get() = serviceSignatureBytes.copyOf()

    init {
        listOf(
            serviceIdDigest, signingKeyId, capabilityId, pairAuthorityDigest, pairBindingDigest,
            clientIdentityFingerprint, runtimeIdentityFingerprint, routePlanClaimsDigest,
        ).forEach(::c1ValidateDigest)
        c1Require(
            keysetVersion > 0uL && issuedAtMs <= notBeforeMs && notBeforeMs < expiresAtMs &&
                pairEpoch > 0uL && generation > 0uL && serviceConfigVersion > 0uL && protocolFloor > 0u &&
                maxUses == 1u && clientIdentityFingerprint != runtimeIdentityFingerprint,
            ProductionC1Error.INVALID_VALUE,
        )
        if (validateSignatureEncoding) c1ValidateCanonicalLowS(serviceSignatureBytes)
        c1Require(
            canonicalBytes().size <= ProductionC1Contract.MAXIMUM_ROUTE_CAPABILITY_BYTES,
            ProductionC1Error.LIMIT_EXCEEDED,
        )
    }

    fun canonicalBytes(): ByteArray = C1TLV.encode(
        ProductionC1Contract.ROUTE_CAPABILITY_OBJECT_TYPE,
        claimsFields() + serviceSignatureBytes,
    )

    fun digestHex(): String = c1DigestHex(canonicalBytes())

    internal fun signingTranscript(): ByteArray = c1SignatureTranscript(
        "AetherLink G1a-C route-capability service signature v1",
        C1TLV.encode(ProductionC1Contract.ROUTE_CAPABILITY_OBJECT_TYPE, claimsFields()),
    )

    private fun claimsFields() = listOf(
        c1ASCII(ProductionC1Contract.SUITE), c1ASCII(serviceIdDigest), c1BE(keysetVersion), c1ASCII(signingKeyId),
        c1ASCII(capabilityId), c1BE(issuedAtMs), c1BE(notBeforeMs), c1BE(expiresAtMs),
        c1ASCII(pairAuthorityDigest), c1ASCII(pairBindingDigest), c1BE(pairEpoch),
        c1ASCII(clientIdentityFingerprint), c1ASCII(runtimeIdentityFingerprint), c1BE(generation),
        c1BE(serviceConfigVersion), c1BE(revocationCounter), c1BE(protocolFloor), c1ASCII(kind.wireValue),
        c1ASCII(routePlanClaimsDigest), c1BE(maxUses), c1ASCII(ProductionC1Contract.SIGNATURE_ALGORITHM),
    )

    override fun equals(other: Any?): Boolean =
        this === other || (other is ProductionC1RouteCapability && canonicalBytes().contentEquals(other.canonicalBytes()))

    override fun hashCode(): Int = canonicalBytes().contentHashCode()

    companion object {
        fun signed(
            serviceIdDigest: String,
            keysetVersion: ULong,
            capabilityId: String,
            issuedAtMs: ULong,
            notBeforeMs: ULong,
            expiresAtMs: ULong,
            authority: ProductionPairAuthorityState,
            kind: ProductionC1RouteKind,
            routePlanClaimsDigest: String,
            signingPublicKey: PublicKey,
            signingPrivateKey: PrivateKey,
        ): ProductionC1RouteCapability {
            val signingKeyId = c1KeyId(signingPublicKey)
            val authorityDigest = authority.digestHex()
            val unsigned = ProductionC1RouteCapability(
                serviceIdDigest, keysetVersion, signingKeyId, capabilityId, issuedAtMs, notBeforeMs,
                expiresAtMs, authorityDigest, authority.pairBindingDigest, authority.pairEpoch,
                authority.clientIdentityFingerprint, authority.runtimeIdentityFingerprint, authority.generation,
                authority.serviceConfigVersion, authority.revocationCounter, authority.protocolFloor, kind,
                routePlanClaimsDigest, 1u, byteArrayOf(), false,
            )
            return ProductionC1RouteCapability(
                serviceIdDigest, keysetVersion, signingKeyId, capabilityId, issuedAtMs, notBeforeMs,
                expiresAtMs, authorityDigest, authority.pairBindingDigest, authority.pairEpoch,
                authority.clientIdentityFingerprint, authority.runtimeIdentityFingerprint, authority.generation,
                authority.serviceConfigVersion, authority.revocationCounter, authority.protocolFloor, kind,
                routePlanClaimsDigest, 1u, c1Sign(unsigned.signingTranscript(), signingPrivateKey), true,
            ).also { c1Verify(it.serviceSignature, it.signingTranscript(), signingPublicKey) }
        }

        fun decode(data: ByteArray): ProductionC1RouteCapability {
            val fields = C1TLV.decode(
                data, ProductionC1Contract.ROUTE_CAPABILITY_OBJECT_TYPE, 22,
                ProductionC1Contract.MAXIMUM_ROUTE_CAPABILITY_BYTES,
            )
            c1Require(
                c1Text(fields[0]) == ProductionC1Contract.SUITE &&
                    c1Text(fields[20]) == ProductionC1Contract.SIGNATURE_ALGORITHM,
                ProductionC1Error.INVALID_VALUE,
            )
            return ProductionC1RouteCapability(
                c1Text(fields[1]), c1UInt64(fields[2]), c1Text(fields[3]), c1Text(fields[4]),
                c1UInt64(fields[5]), c1UInt64(fields[6]), c1UInt64(fields[7]), c1Text(fields[8]),
                c1Text(fields[9]), c1UInt64(fields[10]), c1Text(fields[11]), c1Text(fields[12]),
                c1UInt64(fields[13]), c1UInt64(fields[14]), c1UInt64(fields[15]), c1UInt32(fields[16]),
                ProductionC1RouteKind.decode(c1Text(fields[17])), c1Text(fields[18]), c1UInt32(fields[19]),
                fields[21], true,
            ).also {
                c1Require(it.canonicalBytes().contentEquals(data), ProductionC1Error.MALFORMED_CANONICAL)
            }
        }
    }
}

class VerifiedProductionC1RouteCapability internal constructor(
    val capability: ProductionC1RouteCapability,
    provenance: Any,
) {
    init {
        c1RequireVerifiedMint(provenance)
    }
}

class VerifiedProductionC1RoutePlan internal constructor(
    val claims: ProductionC1RoutePlanClaims,
    val capability: ProductionC1RouteCapability,
    val securityContext: ProductionC1PreauthorizationSessionContext,
    val authorityDigest: String,
    val capabilityDigest: String,
    val claimsDigest: String,
    internal val verifiedKeyset: VerifiedProductionC1ServiceKeyset,
    provenance: Any,
) {
    init {
        c1RequireVerifiedMint(provenance)
    }

    val kind: ProductionC1RouteKind get() = claims.kind
    val pairBindingDigest: String get() = claims.pairBindingDigest
    val pairEpoch: ULong get() = claims.pairEpoch
    val clientIdentityFingerprint: String get() = claims.clientIdentityFingerprint
    val runtimeIdentityFingerprint: String get() = claims.runtimeIdentityFingerprint
    val generation: ULong get() = claims.generation
    val connectorMaterial: ProductionC1RouteConnectorMaterial get() = claims.connector
}

class ProductionC1RouteAuthorization private constructor(
    val kind: ProductionC1RouteKind,
    val pairBindingDigest: String,
    val pairEpoch: ULong,
    val generation: ULong,
    val pairAuthorityDigest: String,
    val routeCapabilityDigest: String,
    val routePlanClaimsDigest: String,
    val selectedPathReceiptDigest: String,
    val serviceIdDigest: String,
    val keysetVersion: ULong,
) {
    init {
        listOf(
            pairBindingDigest, pairAuthorityDigest, routeCapabilityDigest, routePlanClaimsDigest,
            selectedPathReceiptDigest, serviceIdDigest,
        ).forEach(::c1ValidateDigest)
        c1Require(
            pairEpoch > 0uL && generation > 0uL && keysetVersion > 0uL,
            ProductionC1Error.MALFORMED_CANONICAL,
        )
    }

    fun canonicalBytes(): ByteArray = C1TLV.encode(
        kind.authorizationObjectType,
        listOf(
            c1ASCII(ProductionC1Contract.SUITE), c1ASCII(pairBindingDigest), c1BE(pairEpoch),
            c1BE(generation), c1ASCII(pairAuthorityDigest), c1ASCII(routeCapabilityDigest),
            c1ASCII(routePlanClaimsDigest), c1ASCII(selectedPathReceiptDigest), c1ASCII(serviceIdDigest),
            c1BE(keysetVersion),
        ),
    )

    fun digestHex(): String = c1DigestHex(canonicalBytes())

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is ProductionC1RouteAuthorization && canonicalBytes().contentEquals(other.canonicalBytes()))

    override fun hashCode(): Int = canonicalBytes().contentHashCode()

    companion object {
        internal fun fromVerifiedPlan(plan: VerifiedProductionC1RoutePlan) = ProductionC1RouteAuthorization(
            plan.kind, plan.pairBindingDigest, plan.pairEpoch, plan.generation, plan.authorityDigest,
            plan.capabilityDigest, plan.claimsDigest, plan.claims.selectedPathReceiptDigest,
            plan.capability.serviceIdDigest, plan.capability.keysetVersion,
        )

        fun decode(data: ByteArray): ProductionC1RouteAuthorization {
            val kind = ProductionC1RouteKind.decodeAuthorizationObjectType(C1TLV.peekObjectType(data))
            val fields = C1TLV.decode(
                data, kind.authorizationObjectType, 10,
                ProductionC1Contract.MAXIMUM_ROUTE_AUTHORIZATION_BYTES,
            )
            c1Require(c1Text(fields[0]) == ProductionC1Contract.SUITE, ProductionC1Error.INVALID_VALUE)
            return ProductionC1RouteAuthorization(
                kind, c1Text(fields[1]), c1UInt64(fields[2]), c1UInt64(fields[3]), c1Text(fields[4]),
                c1Text(fields[5]), c1Text(fields[6]), c1Text(fields[7]), c1Text(fields[8]), c1UInt64(fields[9]),
            ).also {
                c1Require(it.canonicalBytes().contentEquals(data), ProductionC1Error.MALFORMED_CANONICAL)
            }
        }
    }
}

class VerifiedProductionC1RouteAuthorization internal constructor(
    val authorization: ProductionC1RouteAuthorization,
    provenance: Any,
) {
    private val bytes = authorization.canonicalBytes()
    val canonicalBytes: ByteArray get() = bytes.copyOf()
    val digestHex: String = authorization.digestHex()
    val kind: ProductionC1RouteKind get() = authorization.kind
    val pairBindingDigest: String get() = authorization.pairBindingDigest
    val pairEpoch: ULong get() = authorization.pairEpoch
    val generation: ULong get() = authorization.generation

    init {
        c1RequireVerifiedMint(provenance)
    }

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is VerifiedProductionC1RouteAuthorization && bytes.contentEquals(other.bytes))

    override fun hashCode(): Int = bytes.contentHashCode()
}

object ProductionC1RouteCommitments {
    const val MAXIMUM_ROUTE_HANDLE_BYTES = 512
    const val MAXIMUM_NONCE_BYTES = 512
    const val MINIMUM_SECRET_BYTES = 32
    const val MAXIMUM_SECRET_BYTES = 512

    fun routeHandleDigest(kind: ProductionC1RouteKind, routeHandle: String): String {
        val bytes = c1BoundedUTF8(routeHandle, MAXIMUM_ROUTE_HANDLE_BYTES)
        val claims = c1BE(bytes.size.toUInt()) + bytes
        return c1DigestHex(
            c1SignatureTranscript(
                "AetherLink G1a-C route-handle commitment ${kind.wireValue} v1",
                claims,
            )
        )
    }

    fun credentialCommitmentDigest(
        kind: ProductionC1RouteKind,
        routeHandle: String,
        nonce: String,
        secret: ByteArray,
    ): String {
        val handleBytes = c1BoundedUTF8(routeHandle, MAXIMUM_ROUTE_HANDLE_BYTES)
        val nonceBytes = c1BoundedUTF8(nonce, MAXIMUM_NONCE_BYTES)
        c1Require(secret.size in MINIMUM_SECRET_BYTES..MAXIMUM_SECRET_BYTES, ProductionC1Error.LIMIT_EXCEEDED)
        val claims = ByteArrayOutputStream().apply {
            write(c1BE(handleBytes.size.toUInt()))
            write(handleBytes)
            write(c1BE(nonceBytes.size.toUInt()))
            write(nonceBytes)
            write(c1BE(secret.size.toUInt()))
            write(secret)
        }.toByteArray()
        return c1DigestHex(
            c1SignatureTranscript(
                "AetherLink G1a-C credential commitment ${kind.wireValue} v1",
                claims,
            )
        )
    }
}

class VerifiedProductionC1ConnectorInput internal constructor(
    val routeHandle: String,
    val nonce: String,
    secret: ByteArray,
    val connector: ProductionC1RouteConnectorMaterial,
    val commitmentDigest: String,
    provenance: Any,
) {
    private val secretBytes = secret.copyOf()
    val secret: ByteArray get() = secretBytes.copyOf()

    init {
        c1RequireVerifiedMint(provenance)
        c1ValidateDigest(commitmentDigest)
    }

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is VerifiedProductionC1ConnectorInput &&
                routeHandle == other.routeHandle &&
                nonce == other.nonce &&
                secretBytes.contentEquals(other.secretBytes) &&
                connector == other.connector &&
                commitmentDigest == other.commitmentDigest)

    override fun hashCode(): Int {
        var result = routeHandle.hashCode()
        result = 31 * result + nonce.hashCode()
        result = 31 * result + secretBytes.contentHashCode()
        result = 31 * result + connector.hashCode()
        return 31 * result + commitmentDigest.hashCode()
    }
}

class VerifiedProductionC1TranscriptBinding internal constructor(
    val transcript: ProductionSecureSessionTranscript,
    val authorization: VerifiedProductionC1RouteAuthorization,
    val plan: VerifiedProductionC1RoutePlan,
    val connectorInput: VerifiedProductionC1ConnectorInput,
    val securityContext: ProductionC1PreauthorizationSessionContext,
    provenance: Any,
) {
    init {
        c1RequireVerifiedMint(provenance)
    }
}

class ProductionC1AdmissionPreparation internal constructor(
    val nextSnapshot: ProductionPairStateSnapshot,
    val bindingDigest: String,
    val sessionId: String,
    val transcriptDigest: String,
    val routeAuthorizationDigest: String,
    val routePlanDigest: String,
    val previousPairSnapshotDigest: String,
    val pairSnapshotDigest: String,
    val effectiveNotBeforeMs: ULong,
    val expiresAtMs: ULong,
) {
    init {
        listOf(
            bindingDigest,
            transcriptDigest,
            routeAuthorizationDigest,
            routePlanDigest,
            previousPairSnapshotDigest,
            pairSnapshotDigest,
        ).forEach(::c1ValidateDigest)
        c1Require(
            sessionId.isNotBlank() &&
                pairSnapshotDigest == nextSnapshot.digestHex() &&
                effectiveNotBeforeMs < expiresAtMs,
            ProductionC1Error.STATE_MISMATCH,
        )
    }

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is ProductionC1AdmissionPreparation &&
                bindingDigest == other.bindingDigest &&
                sessionId == other.sessionId &&
                transcriptDigest == other.transcriptDigest &&
                routeAuthorizationDigest == other.routeAuthorizationDigest &&
                routePlanDigest == other.routePlanDigest &&
                previousPairSnapshotDigest == other.previousPairSnapshotDigest &&
                pairSnapshotDigest == other.pairSnapshotDigest &&
                effectiveNotBeforeMs == other.effectiveNotBeforeMs &&
                expiresAtMs == other.expiresAtMs &&
                nextSnapshot == other.nextSnapshot)

    override fun hashCode(): Int = bindingDigest.hashCode()
}

object ProductionC1PairStateAdmission {
    /**
     * Produces a non-authorizing state-transition preparation only.  In particular, this public
     * protocol API never mints a durable-session permit and does not accept a caller-supplied
     * clock.  A durable owner must check [effectiveNotBeforeMs, expiresAtMs), persist
     * [ProductionC1AdmissionPreparation.nextSnapshot], perform exact readback, check trusted time
     * again, and only then mint its own non-forgeable permit.
     */
    fun admit(
        binding: VerifiedProductionC1TranscriptBinding,
        snapshot: ProductionPairStateSnapshot,
    ): ProductionC1AdmissionPreparation {
        c1Require(binding.plan.kind != ProductionC1RouteKind.P2P_DIRECT, ProductionC1Error.ROUTE_MISMATCH)
        val transcript = binding.transcript
        val authorization = binding.authorization.authorization
        val authority = snapshot.authority
        c1Require(
            authority.status == ProductionPairAuthorityStatus.ACTIVE &&
                authorization.pairAuthorityDigest == authority.digestHex() &&
                transcript.pairBindingDigest == authority.pairBindingDigest &&
                transcript.pairEpoch == authority.pairEpoch &&
                transcript.clientIdentityFingerprint == authority.clientIdentityFingerprint &&
                transcript.runtimeIdentityFingerprint == authority.runtimeIdentityFingerprint &&
                transcript.generation == authority.generation &&
                transcript.serviceConfigVersion == authority.serviceConfigVersion &&
                transcript.keysetVersion == authority.keysetVersion &&
                transcript.revocationCounter == authority.revocationCounter,
            ProductionC1Error.STATE_MISMATCH,
        )
        val transcriptDigestBytes = ProductionSecureSessionCodec.digest(transcript)
        val transcriptDigest = c1LowerHex(transcriptDigestBytes)
        if (snapshot.consumedEntries.any { it.sessionId == transcript.sessionId }) {
            throw ProductionPairStateException(ProductionPairStateRejectionReason.SESSION_REPLAY)
        }
        if (snapshot.consumedEntries.any { it.transcriptDigest == transcriptDigest }) {
            throw ProductionPairStateException(ProductionPairStateRejectionReason.TRANSCRIPT_REPLAY)
        }
        if (snapshot.consumedEntries.size >= ProductionPairStateContract.MAX_CONSUMED_ENTRIES) {
            throw ProductionPairStateException(ProductionPairStateRejectionReason.REPLAY_CAPACITY_EXHAUSTED)
        }
        if (snapshot.localRevision == ULong.MAX_VALUE) {
            throw ProductionPairStateException(ProductionPairStateRejectionReason.SNAPSHOT_REVISION_EXHAUSTED)
        }
        val updated = ProductionPairStateSnapshot(
            authority = authority,
            localRevision = snapshot.localRevision + 1uL,
            consumedEntries = snapshot.consumedEntries + ProductionPairConsumedSession(
                sessionId = transcript.sessionId,
                transcriptDigest = transcriptDigest,
            ),
            transitionHistory = snapshot.transitionHistory,
        )
        val permitClaims = ByteArrayOutputStream().apply {
            write(transcriptDigestBytes)
            write(binding.authorization.canonicalBytes)
            write(binding.plan.claims.canonicalBytes())
            write(binding.plan.connectorMaterial.canonicalBytes())
            write(binding.plan.capability.canonicalBytes())
            write(binding.securityContext.canonicalBytes())
            write(c1ForceDecodeDigest(binding.connectorInput.commitmentDigest))
            write(updated.digest())
        }.toByteArray()
        val signingKey = binding.plan.verifiedKeyset.keyset.delegatedKeys.firstOrNull {
            it.keyId == binding.plan.capability.signingKeyId
        } ?: c1Fail(ProductionC1Error.KEY_UNAVAILABLE)
        val effectiveNotBeforeMs = listOf(
            binding.plan.verifiedKeyset.keyset.issuedAtMs,
            signingKey.notBeforeMs,
            binding.plan.capability.notBeforeMs,
            binding.plan.claims.notBeforeMs,
        ).maxOrNull() ?: c1Fail(ProductionC1Error.INVALID_VALUE)
        val expiresAtMs = listOf(
            binding.plan.verifiedKeyset.keyset.expiresAtMs,
            signingKey.expiresAtMs,
            signingKey.revokedAtMs ?: ULong.MAX_VALUE,
            binding.plan.capability.expiresAtMs,
            binding.plan.claims.expiresAtMs,
        ).minOrNull() ?: c1Fail(ProductionC1Error.INVALID_VALUE)
        c1Require(effectiveNotBeforeMs < expiresAtMs, ProductionC1Error.INVALID_VALUE)
        return ProductionC1AdmissionPreparation(
            nextSnapshot = updated,
            bindingDigest = c1DigestHex(
                c1SignatureTranscript(
                    "AetherLink G1a-C durable admission permit v1",
                    permitClaims,
                )
            ),
            sessionId = transcript.sessionId,
            transcriptDigest = transcriptDigest,
            routeAuthorizationDigest = binding.authorization.digestHex,
            routePlanDigest = binding.plan.claimsDigest,
            previousPairSnapshotDigest = snapshot.digestHex(),
            pairSnapshotDigest = updated.digestHex(),
            effectiveNotBeforeMs = effectiveNotBeforeMs,
            expiresAtMs = expiresAtMs,
        )
    }
}

object ProductionC1Verifier {
    private val verifiedMint = Any()

    @JvmSynthetic
    internal fun ownsVerifiedMint(provenance: Any): Boolean = provenance === verifiedMint

    fun verifyServiceKeyset(
        keyset: ProductionC1ServiceKeyset,
        expectedServiceIdDigest: String,
        pinnedRootPublicKey: PublicKey,
        minimumAcceptedKeysetVersion: ULong,
        previous: VerifiedProductionC1ServiceKeyset? = null,
        nowMs: ULong,
    ): VerifiedProductionC1ServiceKeyset {
        c1ValidateDigest(expectedServiceIdDigest)
        c1Require(
            minimumAcceptedKeysetVersion > 0uL &&
                keyset.keysetVersion >= minimumAcceptedKeysetVersion,
            ProductionC1Error.KEYSET_ROLLBACK,
        )
        c1Require(keyset.serviceIdDigest == expectedServiceIdDigest, ProductionC1Error.SERVICE_MISMATCH)
        c1Require(keyset.rootKeyId == c1KeyId(pinnedRootPublicKey), ProductionC1Error.UNTRUSTED_ROOT)
        c1ValidateWindow(
            keyset.issuedAtMs, keyset.issuedAtMs, keyset.expiresAtMs,
            ProductionC1Contract.MAXIMUM_KEYSET_LIFETIME_MS, nowMs,
        )
        if (previous != null) {
            c1Require(
                previous.keyset.serviceIdDigest == keyset.serviceIdDigest &&
                    previous.keyset.rootKeyId == keyset.rootKeyId,
                ProductionC1Error.SERVICE_MISMATCH,
            )
            if (previous.keyset.keysetVersion == ULong.MAX_VALUE ||
                keyset.keysetVersion != previous.keyset.keysetVersion + 1uL
            ) {
                c1Fail(
                    if (keyset.keysetVersion <= previous.keyset.keysetVersion) {
                        ProductionC1Error.KEYSET_ROLLBACK
                    } else {
                        ProductionC1Error.KEYSET_GAP
                    }
                )
            }
            c1Require(
                keyset.previousKeysetDigest == previous.keyset.digestHex(),
                ProductionC1Error.PREVIOUS_KEYSET_MISMATCH,
            )
        } else {
            c1Require(
                (keyset.keysetVersion == 1uL && keyset.previousKeysetDigest == null) ||
                    (keyset.keysetVersion > 1uL && keyset.previousKeysetDigest != null),
                ProductionC1Error.PREVIOUS_KEYSET_MISMATCH,
            )
        }
        c1Verify(keyset.rootSignature, keyset.signingTranscript(), pinnedRootPublicKey)
        return VerifiedProductionC1ServiceKeyset(keyset, verifiedMint)
    }

    fun verifyPairStatus(
        status: ProductionC1PairStatus,
        expectedServiceIdDigest: String,
        expectedRequesterRole: ProductionC1RequesterRole,
        expectedRequestNonce: String,
        current: ProductionPairStateSnapshot?,
        verifiedKeyset: VerifiedProductionC1ServiceKeyset,
        nowMs: ULong,
    ): VerifiedProductionC1PairStatus {
        c1ValidateDigest(expectedRequestNonce)
        c1Require(
            status.serviceIdDigest == expectedServiceIdDigest &&
                status.serviceIdDigest == verifiedKeyset.keyset.serviceIdDigest,
            ProductionC1Error.SERVICE_MISMATCH,
        )
        c1Require(
            status.keysetVersion == verifiedKeyset.keyset.keysetVersion &&
                status.authority.keysetVersion == status.keysetVersion,
            ProductionC1Error.KEYSET_ROLLBACK,
        )
        c1Require(
            status.requesterRole == expectedRequesterRole && status.requestNonce == expectedRequestNonce,
            ProductionC1Error.STATE_MISMATCH,
        )
        c1ValidateVerifiedKeysetUse(verifiedKeyset, nowMs)
        c1ValidateWindow(
            status.issuedAtMs, status.issuedAtMs, status.expiresAtMs,
            ProductionC1Contract.MAXIMUM_STATUS_LIFETIME_MS, nowMs,
        )
        val signingKey = c1DelegatedKey(
            status.signingKeyId, ProductionC1DelegatedKeyPurpose.PAIR_STATUS, verifiedKeyset, nowMs,
        )
        c1Verify(status.serviceSignature, status.signingTranscript(), c1PublicKey(signingKey.publicKeyX963))
        c1Require(
            status.authority.acceptedReceiptDigest == status.authorizationEvidenceDigest,
            ProductionC1Error.EVIDENCE_MISMATCH,
        )
        val remoteSequence = c1TransitionSequence(status.transitionHistory, status.authority)
        c1Require(
            remoteSequence.size.toULong() == status.authority.authorityRevision,
            ProductionC1Error.HISTORY_MISMATCH,
        )
        c1Require(c1TransitionKindMatchesState(status), ProductionC1Error.STATE_MISMATCH)
        if (current != null) {
            val localSequence = c1TransitionSequence(current.transitionHistory, current.authority)
            c1Require(
                localSequence.size <= remoteSequence.size &&
                    remoteSequence.take(localSequence.size) == localSequence,
                ProductionC1Error.HISTORY_MISMATCH,
            )
            if (status.authority.authorityRevision == current.authority.authorityRevision) {
                c1Require(
                    status.authority == current.authority &&
                        status.transitionHistory == current.transitionHistory,
                    ProductionC1Error.STATE_MISMATCH,
                )
            } else {
                c1ValidateAuthorityAdvance(current.authority, status.authority, status.transitionKind)
                if (current.authority.authorityRevision < ULong.MAX_VALUE &&
                    status.authority.authorityRevision == current.authority.authorityRevision + 1uL
                ) {
                    c1Require(
                        status.previousAuthorityDigest == current.authority.digestHex(),
                        ProductionC1Error.PREVIOUS_KEYSET_MISMATCH,
                    )
                } else {
                    c1Require(status.previousAuthorityDigest != null, ProductionC1Error.STATE_MISMATCH)
                }
            }
        } else {
            c1Require(
                status.transitionKind == ProductionC1TransitionKind.GENESIS &&
                    status.previousAuthorityDigest == null && status.authority.authorityRevision == 1uL &&
                    status.authority.status == ProductionPairAuthorityStatus.ACTIVE &&
                    status.transitionHistory.isEmpty(),
                ProductionC1Error.STATE_MISMATCH,
            )
        }
        return VerifiedProductionC1PairStatus(status, verifiedKeyset, verifiedMint)
    }

    fun verifyFreshPairProof(
        proof: ProductionC1FreshPairProof,
        verifiedStatus: VerifiedProductionC1PairStatus,
        current: ProductionPairStateSnapshot,
        currentCommitments: ProductionC1CurrentRecoveryCommitments,
        survivorPublicKey: PublicKey,
        replacementPublicKey: PublicKey,
        nowMs: ULong,
    ): VerifiedProductionC1FreshPairTransition {
        val previous = current.authority
        val status = verifiedStatus.status
        c1ValidateVerifiedPairStatusUse(verifiedStatus, nowMs)
        c1Require(
            previous.pairEpoch < ULong.MAX_VALUE && previous.authorityRevision < ULong.MAX_VALUE,
            ProductionC1Error.INVALID_FRESH_PAIR,
        )
        c1ValidateWindow(
            proof.issuedAtMs,
            proof.issuedAtMs,
            proof.expiresAtMs,
            ProductionC1Contract.MAXIMUM_FRESH_PAIR_LIFETIME_MS,
            nowMs,
        )
        val previousAuthorityDigest = previous.digestHex()
        c1Require(
            status.transitionKind == ProductionC1TransitionKind.FRESH_PAIR &&
                status.evidenceKind == ProductionC1AuthorizationEvidenceKind.DUAL_SIGNED_FRESH_PAIR &&
                status.previousAuthorityDigest == previousAuthorityDigest &&
                proof.previousAuthorityDigest == previousAuthorityDigest &&
                proof.previousPairBindingDigest == previous.pairBindingDigest &&
                proof.nextPairBindingDigest == previous.pairBindingDigest &&
                currentCommitments.pairBindingDigest == previous.pairBindingDigest &&
                proof.previousEndpointTrafficSecretCommitment ==
                currentCommitments.endpointTrafficSecretCommitment &&
                proof.previousRouteTokenSeedCommitment == currentCommitments.routeTokenSeedCommitment &&
                proof.previousEndpointTrafficSecretReuseDigest ==
                currentCommitments.endpointTrafficSecretReuseDigest &&
                proof.previousRouteTokenSeedReuseDigest == currentCommitments.routeTokenSeedReuseDigest &&
                proof.nextEndpointTrafficSecretCommitment !=
                currentCommitments.endpointTrafficSecretCommitment &&
                proof.nextRouteTokenSeedCommitment != currentCommitments.routeTokenSeedCommitment &&
                proof.nextEndpointTrafficSecretReuseDigest !=
                currentCommitments.endpointTrafficSecretReuseDigest &&
                proof.nextRouteTokenSeedReuseDigest != currentCommitments.routeTokenSeedReuseDigest &&
                proof.nextEndpointTrafficSecretReuseDigest != proof.nextRouteTokenSeedReuseDigest &&
                proof.previousPairEpoch == previous.pairEpoch &&
                proof.previousClientIdentityFingerprint == previous.clientIdentityFingerprint &&
                proof.previousRuntimeIdentityFingerprint == previous.runtimeIdentityFingerprint &&
                proof.nextPairEpoch == previous.pairEpoch + 1uL &&
                proof.nextGeneration > previous.generation &&
                proof.nextServiceConfigVersion >= previous.serviceConfigVersion &&
                proof.nextKeysetVersion >= previous.keysetVersion &&
                proof.nextRevocationCounter >= previous.revocationCounter &&
                proof.nextProtocolFloor >= previous.protocolFloor &&
                proof.nextAuthorityRevision == previous.authorityRevision + 1uL &&
                current.transitionHistory.none { it.transitionId == proof.transitionId } &&
                proof.transitionId != previous.transitionId,
            ProductionC1Error.INVALID_FRESH_PAIR,
        )
        val survivorFingerprint = c1KeyId(survivorPublicKey)
        val replacementFingerprint = c1KeyId(replacementPublicKey)
        when (proof.replacementRole) {
            ProductionC1ReplacementRole.CLIENT -> c1Require(
                proof.nextClientIdentityFingerprint == replacementFingerprint &&
                    proof.previousClientIdentityFingerprint != replacementFingerprint &&
                    proof.previousRuntimeIdentityFingerprint == survivorFingerprint &&
                    proof.nextRuntimeIdentityFingerprint == survivorFingerprint,
                ProductionC1Error.INVALID_FRESH_PAIR,
            )
            ProductionC1ReplacementRole.RUNTIME -> c1Require(
                proof.nextRuntimeIdentityFingerprint == replacementFingerprint &&
                    proof.previousRuntimeIdentityFingerprint != replacementFingerprint &&
                    proof.previousClientIdentityFingerprint == survivorFingerprint &&
                    proof.nextClientIdentityFingerprint == survivorFingerprint,
                ProductionC1Error.INVALID_FRESH_PAIR,
            )
        }
        c1Verify(proof.survivorSignature, proof.survivorSigningTranscript(), survivorPublicKey)
        c1Verify(proof.replacementSignature, proof.replacementSigningTranscript(), replacementPublicKey)
        val proofDigest = proof.digestHex()
        c1Require(
            status.authorizationEvidenceDigest == proofDigest &&
                status.authority.acceptedReceiptDigest == proofDigest,
            ProductionC1Error.EVIDENCE_MISMATCH,
        )
        val expectedNext = ProductionPairAuthorityState(
            pairBindingDigest = proof.nextPairBindingDigest,
            pairEpoch = proof.nextPairEpoch,
            clientIdentityFingerprint = proof.nextClientIdentityFingerprint,
            runtimeIdentityFingerprint = proof.nextRuntimeIdentityFingerprint,
            generation = proof.nextGeneration,
            serviceConfigVersion = proof.nextServiceConfigVersion,
            keysetVersion = proof.nextKeysetVersion,
            revocationCounter = proof.nextRevocationCounter,
            protocolFloor = proof.nextProtocolFloor,
            status = ProductionPairAuthorityStatus.ACTIVE,
            transitionId = proof.transitionId,
            transitionRequestDigest = proof.transitionRequestDigest,
            acceptedReceiptDigest = proofDigest,
            authorityRevision = proof.nextAuthorityRevision,
        )
        c1Require(status.authority == expectedNext, ProductionC1Error.STATE_MISMATCH)
        if (current.transitionHistory.size >= ProductionPairStateContract.MAX_TRANSITION_HISTORY_ENTRIES) {
            throw ProductionPairStateException(
                ProductionPairStateRejectionReason.TRANSITION_HISTORY_CAPACITY_EXHAUSTED
            )
        }
        val expectedHistory = current.transitionHistory + ProductionPairTransitionHistoryEntry(
            transitionId = previous.transitionId,
            transitionRequestDigest = previous.transitionRequestDigest,
        )
        c1Require(status.transitionHistory == expectedHistory, ProductionC1Error.HISTORY_MISMATCH)
        if (current.localRevision == ULong.MAX_VALUE) {
            throw ProductionPairStateException(ProductionPairStateRejectionReason.SNAPSHOT_REVISION_EXHAUSTED)
        }
        val nextSnapshot = ProductionPairStateSnapshot(
            authority = expectedNext,
            localRevision = current.localRevision + 1uL,
            consumedEntries = emptyList(),
            transitionHistory = expectedHistory,
        )
        return VerifiedProductionC1FreshPairTransition(
            proof = proof,
            verifiedStatus = verifiedStatus,
            applyPreparation = ProductionC1FreshPairApplyPreparation(
                expectedPreviousAuthorityDigest = proof.previousAuthorityDigest,
                expectedPreviousSnapshotDigest = current.digestHex(),
                nextAuthority = expectedNext,
                nextTransitionHistory = expectedHistory,
                nextSnapshot = nextSnapshot,
            ),
            provenance = verifiedMint,
        )
    }

    fun verifyRouteCapability(
        capability: ProductionC1RouteCapability,
        authority: ProductionPairAuthorityState,
        verifiedKeyset: VerifiedProductionC1ServiceKeyset,
        nowMs: ULong,
    ): VerifiedProductionC1RouteCapability {
        c1Require(authority.status == ProductionPairAuthorityStatus.ACTIVE, ProductionC1Error.STATE_MISMATCH)
        c1ValidateVerifiedKeysetUse(verifiedKeyset, nowMs)
        c1Require(
            capability.serviceIdDigest == verifiedKeyset.keyset.serviceIdDigest,
            ProductionC1Error.SERVICE_MISMATCH,
        )
        c1Require(
            capability.keysetVersion == verifiedKeyset.keyset.keysetVersion &&
                capability.keysetVersion == authority.keysetVersion,
            ProductionC1Error.KEYSET_ROLLBACK,
        )
        c1ValidateWindow(
            capability.issuedAtMs, capability.notBeforeMs, capability.expiresAtMs,
            ProductionC1Contract.MAXIMUM_ROUTE_LIFETIME_MS, nowMs,
        )
        c1Require(
            capability.pairAuthorityDigest == authority.digestHex() &&
                capability.pairBindingDigest == authority.pairBindingDigest &&
                capability.pairEpoch == authority.pairEpoch &&
                capability.clientIdentityFingerprint == authority.clientIdentityFingerprint &&
                capability.runtimeIdentityFingerprint == authority.runtimeIdentityFingerprint &&
                capability.generation == authority.generation &&
                capability.serviceConfigVersion == authority.serviceConfigVersion &&
                capability.revocationCounter == authority.revocationCounter &&
                capability.protocolFloor == authority.protocolFloor && capability.maxUses == 1u,
            ProductionC1Error.STATE_MISMATCH,
        )
        val signingKey = c1DelegatedKey(
            capability.signingKeyId, ProductionC1DelegatedKeyPurpose.ROUTE_CAPABILITY,
            verifiedKeyset, nowMs,
        )
        c1Verify(capability.serviceSignature, capability.signingTranscript(), c1PublicKey(signingKey.publicKeyX963))
        return VerifiedProductionC1RouteCapability(capability, verifiedMint)
    }

    fun verifyRoutePlan(
        claims: ProductionC1RoutePlanClaims,
        capability: ProductionC1RouteCapability,
        securityContext: ProductionC1PreauthorizationSessionContext,
        authority: ProductionPairAuthorityState,
        verifiedKeyset: VerifiedProductionC1ServiceKeyset,
        nowMs: ULong,
    ): VerifiedProductionC1RoutePlan {
        c1Require(claims.kind != ProductionC1RouteKind.P2P_DIRECT, ProductionC1Error.ROUTE_MISMATCH)
        return verifyRoutePlanCore(
            claims,
            capability,
            securityContext,
            authority,
            verifiedKeyset,
            nowMs,
        )
    }

    internal fun verifyCandidateP2PRoutePlanBase(
        claims: ProductionC1RoutePlanClaims,
        capability: ProductionC1RouteCapability,
        securityContext: ProductionC1PreauthorizationSessionContext,
        authority: ProductionPairAuthorityState,
        verifiedKeyset: VerifiedProductionC1ServiceKeyset,
        nowMs: ULong,
    ): VerifiedProductionC1RoutePlan {
        c1Require(claims.kind == ProductionC1RouteKind.P2P_DIRECT, ProductionC1Error.ROUTE_MISMATCH)
        return verifyRoutePlanCore(
            claims,
            capability,
            securityContext,
            authority,
            verifiedKeyset,
            nowMs,
        )
    }

    private fun verifyRoutePlanCore(
        claims: ProductionC1RoutePlanClaims,
        capability: ProductionC1RouteCapability,
        securityContext: ProductionC1PreauthorizationSessionContext,
        authority: ProductionPairAuthorityState,
        verifiedKeyset: VerifiedProductionC1ServiceKeyset,
        nowMs: ULong,
    ): VerifiedProductionC1RoutePlan {
        verifyRouteCapability(capability, authority, verifiedKeyset, nowMs)
        c1ValidateWindow(
            capability.issuedAtMs, claims.notBeforeMs, claims.expiresAtMs,
            ProductionC1Contract.MAXIMUM_ROUTE_LIFETIME_MS, nowMs,
        )
        val claimsDigest = claims.digestHex()
        val authorityDigest = authority.digestHex()
        c1Require(
            claimsDigest == capability.routePlanClaimsDigest &&
                claims.securityContextDigest == securityContext.digestHex() &&
                claims.kind == capability.kind &&
                securityContext.routeKind == claims.kind &&
                claims.pairAuthorityDigest == authorityDigest && claims.pairBindingDigest == authority.pairBindingDigest &&
                claims.pairEpoch == authority.pairEpoch && claims.generation == authority.generation &&
                claims.clientIdentityFingerprint == authority.clientIdentityFingerprint &&
                claims.runtimeIdentityFingerprint == authority.runtimeIdentityFingerprint &&
                securityContext.pairBindingDigest == authority.pairBindingDigest &&
                securityContext.pairEpoch == authority.pairEpoch &&
                securityContext.clientIdentityFingerprint == authority.clientIdentityFingerprint &&
                securityContext.runtimeIdentityFingerprint == authority.runtimeIdentityFingerprint &&
                securityContext.generation == authority.generation &&
                securityContext.serviceConfigVersion == authority.serviceConfigVersion &&
                securityContext.keysetVersion == authority.keysetVersion &&
                securityContext.revocationCounter == authority.revocationCounter &&
                ProductionC1PreauthorizationSessionContext.PROTOCOL_VERSION >= authority.protocolFloor &&
                ProductionC1PreauthorizationSessionContext.MINIMUM_PROTOCOL_VERSION >= authority.protocolFloor &&
                claims.notBeforeMs >= capability.notBeforeMs && claims.expiresAtMs <= capability.expiresAtMs &&
                claims.connector.pathReceiptDigest == claims.selectedPathReceiptDigest,
            ProductionC1Error.ROUTE_MISMATCH,
        )
        return VerifiedProductionC1RoutePlan(
            claims,
            capability,
            securityContext,
            authorityDigest,
            capability.digestHex(),
            claimsDigest,
            verifiedKeyset,
            verifiedMint,
        )
    }

    fun makeRouteAuthorization(
        plan: VerifiedProductionC1RoutePlan,
        nowMs: ULong,
    ): VerifiedProductionC1RouteAuthorization {
        c1Require(plan.kind != ProductionC1RouteKind.P2P_DIRECT, ProductionC1Error.ROUTE_MISMATCH)
        return makeRouteAuthorizationCore(plan, nowMs)
    }

    internal fun makeCandidateP2PRouteAuthorizationBase(
        plan: VerifiedProductionC1RoutePlan,
        nowMs: ULong,
    ): VerifiedProductionC1RouteAuthorization {
        c1Require(plan.kind == ProductionC1RouteKind.P2P_DIRECT, ProductionC1Error.ROUTE_MISMATCH)
        return makeRouteAuthorizationCore(plan, nowMs)
    }

    private fun makeRouteAuthorizationCore(
        plan: VerifiedProductionC1RoutePlan,
        nowMs: ULong,
    ): VerifiedProductionC1RouteAuthorization {
        c1ValidateVerifiedRoutePlanUse(plan, nowMs)
        return VerifiedProductionC1RouteAuthorization(
            ProductionC1RouteAuthorization.fromVerifiedPlan(plan),
            verifiedMint,
        )
    }

    fun verifyConnectorInput(
        plan: VerifiedProductionC1RoutePlan,
        routeHandle: String,
        nonce: String,
        secret: ByteArray,
        nowMs: ULong,
    ): VerifiedProductionC1ConnectorInput {
        c1Require(plan.kind != ProductionC1RouteKind.P2P_DIRECT, ProductionC1Error.ROUTE_MISMATCH)
        c1ValidateVerifiedRoutePlanUse(plan, nowMs)
        val expectedHandle = ProductionC1RouteCommitments.routeHandleDigest(plan.kind, routeHandle)
        val expectedCredential = ProductionC1RouteCommitments.credentialCommitmentDigest(
            plan.kind, routeHandle, nonce, secret,
        )
        c1Require(
            expectedHandle == plan.connectorMaterial.routeHandleDigest &&
                expectedCredential == plan.connectorMaterial.credentialCommitmentDigest,
            ProductionC1Error.ROUTE_MISMATCH,
        )
        val handleBytes = c1BoundedUTF8(routeHandle, ProductionC1RouteCommitments.MAXIMUM_ROUTE_HANDLE_BYTES)
        val nonceBytes = c1BoundedUTF8(nonce, ProductionC1RouteCommitments.MAXIMUM_NONCE_BYTES)
        val inputClaims = ByteArrayOutputStream().apply {
            write(plan.connectorMaterial.canonicalBytes())
            write(c1BE(handleBytes.size.toUInt()))
            write(handleBytes)
            write(c1BE(nonceBytes.size.toUInt()))
            write(nonceBytes)
            write(c1ForceDecodeDigest(expectedCredential))
        }.toByteArray()
        val inputCommitment = c1DigestHex(
            c1SignatureTranscript(
                "AetherLink G1a-C verified connector-input commitment v1",
                inputClaims,
            )
        )
        return VerifiedProductionC1ConnectorInput(
            routeHandle,
            nonce,
            secret,
            plan.connectorMaterial,
            inputCommitment,
            verifiedMint,
        )
    }

    fun verifyTranscriptBinding(
        transcript: ProductionSecureSessionTranscript,
        authorization: VerifiedProductionC1RouteAuthorization,
        verifiedPlan: VerifiedProductionC1RoutePlan,
        connectorInput: VerifiedProductionC1ConnectorInput,
        authority: ProductionPairAuthorityState,
        nowMs: ULong,
    ): VerifiedProductionC1TranscriptBinding {
        c1Require(verifiedPlan.kind != ProductionC1RouteKind.P2P_DIRECT, ProductionC1Error.ROUTE_MISMATCH)
        c1ValidateVerifiedRoutePlanUse(verifiedPlan, nowMs)
        val expectedContext = ProductionC1PreauthorizationSessionContext(transcript)
        val expectedConnectorInput = verifyConnectorInput(
            verifiedPlan,
            connectorInput.routeHandle,
            connectorInput.nonce,
            connectorInput.secret,
            nowMs,
        )
        c1Require(
            authority.status == ProductionPairAuthorityStatus.ACTIVE &&
                authorization.kind == verifiedPlan.kind &&
                authorization.authorization.pairAuthorityDigest == verifiedPlan.authorityDigest &&
                authorization.authorization.routeCapabilityDigest == verifiedPlan.capabilityDigest &&
                authorization.authorization.routePlanClaimsDigest == verifiedPlan.claimsDigest &&
                authorization.authorization.selectedPathReceiptDigest ==
                verifiedPlan.claims.selectedPathReceiptDigest &&
                connectorInput == expectedConnectorInput &&
                expectedContext == verifiedPlan.securityContext &&
                expectedContext.digestHex() == verifiedPlan.claims.securityContextDigest &&
                transcript.routeAuthorizationKind == authorization.kind.transcriptKind &&
                transcript.routeAuthorizationDigest == authorization.digestHex &&
                transcript.pairBindingDigest == authorization.pairBindingDigest &&
                transcript.pairEpoch == authorization.pairEpoch && transcript.generation == authorization.generation &&
                transcript.pairBindingDigest == authority.pairBindingDigest &&
                transcript.pairEpoch == authority.pairEpoch &&
                transcript.clientIdentityFingerprint == authority.clientIdentityFingerprint &&
                transcript.runtimeIdentityFingerprint == authority.runtimeIdentityFingerprint &&
                transcript.generation == authority.generation &&
                transcript.serviceConfigVersion == authority.serviceConfigVersion &&
                transcript.keysetVersion == authority.keysetVersion &&
                transcript.revocationCounter == authority.revocationCounter &&
                transcript.protocolVersion >= authority.protocolFloor &&
                transcript.minimumProtocolVersion >= authority.protocolFloor &&
                transcript.profile == ProductionSecureSessionContract.PROFILE,
            ProductionC1Error.ROUTE_MISMATCH,
        )
        return VerifiedProductionC1TranscriptBinding(
            transcript,
            authorization,
            verifiedPlan,
            connectorInput,
            expectedContext,
            verifiedMint,
        )
    }
}

// Narrow module-only bridge for extension codecs. It keeps ALS1 framing, DER,
// signing, key-purpose, and use-time rules single-sourced in this file.
internal object ProductionC1InternalBridge {
    fun encode(objectType: Int, fields: List<ByteArray>): ByteArray =
        C1TLV.encode(objectType, fields)

    fun decode(
        data: ByteArray,
        objectType: Int,
        fieldCount: Int,
        maximumBytes: Int,
    ): List<ByteArray> = C1TLV.decode(data, objectType, fieldCount, maximumBytes)

    fun ascii(value: String): ByteArray = c1ASCII(value)

    fun text(data: ByteArray): String = c1Text(data)

    fun be(value: ULong): ByteArray = c1BE(value)

    fun be(value: UInt): ByteArray = c1BE(value)

    fun uint64(data: ByteArray): ULong = c1UInt64(data)

    fun uint32(data: ByteArray): UInt = c1UInt32(data)

    fun validateDigest(value: String) = c1ValidateDigest(value)

    fun rawDigest(value: String): ByteArray {
        c1ValidateDigest(value)
        return c1ForceDecodeDigest(value)
    }

    fun digestHex(data: ByteArray): String = c1DigestHex(data)

    fun publicKey(x963: ByteArray): PublicKey = c1PublicKey(x963)

    fun keyId(publicKey: PublicKey): String = c1KeyId(publicKey)

    fun transcript(domain: String, claims: ByteArray): ByteArray =
        c1SignatureTranscript(domain, claims)

    fun sign(transcript: ByteArray, privateKey: PrivateKey): ByteArray =
        c1Sign(transcript, privateKey)

    fun validateSignature(signature: ByteArray) {
        c1ValidateCanonicalLowS(signature)
    }

    fun verify(signature: ByteArray, transcript: ByteArray, publicKey: PublicKey) =
        c1Verify(signature, transcript, publicKey)

    fun validateWindow(
        issuedAtMs: ULong,
        notBeforeMs: ULong,
        expiresAtMs: ULong,
        maximumLifetimeMs: ULong,
        nowMs: ULong,
    ) = c1ValidateWindow(issuedAtMs, notBeforeMs, expiresAtMs, maximumLifetimeMs, nowMs)

    fun delegatedSigningKey(
        id: String,
        purpose: ProductionC1DelegatedKeyPurpose,
        keyset: VerifiedProductionC1ServiceKeyset,
        nowMs: ULong,
    ): PublicKey {
        c1ValidateVerifiedKeysetUse(keyset, nowMs)
        return c1PublicKey(c1DelegatedKey(id, purpose, keyset, nowMs).publicKeyX963)
    }
}

private object C1TLV {
    private val magic = "ALS1".toByteArray(Charsets.US_ASCII)
    private const val version = 1

    fun encode(objectType: Int, fields: List<ByteArray>): ByteArray =
        ByteArrayOutputStream().apply {
            write(magic)
            write(objectType)
            write(version)
            fields.forEachIndexed { index, field ->
                write(index + 1)
                write(c1BE(field.size.toUInt()))
                write(field)
            }
        }.toByteArray()

    fun decode(
        data: ByteArray,
        objectType: Int,
        fieldCount: Int,
        maximumBytes: Int,
    ): List<ByteArray> {
        c1Require(data.size <= maximumBytes, ProductionC1Error.LIMIT_EXCEEDED)
        c1Require(
            fieldCount in 1..UByte.MAX_VALUE.toInt() && data.size >= 6,
            ProductionC1Error.MALFORMED_CANONICAL,
        )
        val cursor = C1Cursor(data)
        c1Require(
            cursor.read(4).contentEquals(magic) && cursor.byte() == objectType && cursor.byte() == version,
            ProductionC1Error.MALFORMED_CANONICAL,
        )
        val fields = ArrayList<ByteArray>(fieldCount)
        repeat(fieldCount) { index ->
            c1Require(cursor.byte() == index + 1, ProductionC1Error.MALFORMED_CANONICAL)
            val length = cursor.uint32()
            c1Require(length <= maximumBytes.toUInt(), ProductionC1Error.LIMIT_EXCEEDED)
            fields += cursor.read(length.toInt())
        }
        c1Require(cursor.isAtEnd, ProductionC1Error.MALFORMED_CANONICAL)
        return fields
    }

    fun peekObjectType(data: ByteArray): Int {
        c1Require(data.size >= 5, ProductionC1Error.MALFORMED_CANONICAL)
        return data[4].toInt() and 0xff
    }
}

private class C1Cursor(private val data: ByteArray) {
    private var offset = 0
    val isAtEnd: Boolean get() = offset == data.size

    fun read(count: Int): ByteArray {
        c1Require(
            count >= 0 && offset <= data.size && count <= data.size - offset,
            ProductionC1Error.MALFORMED_CANONICAL,
        )
        return data.copyOfRange(offset, offset + count).also { offset += count }
    }

    fun byte(): Int {
        c1Require(offset < data.size, ProductionC1Error.MALFORMED_CANONICAL)
        return data[offset++].toInt() and 0xff
    }

    fun uint32(): UInt = c1UInt32(read(4))
}

private fun c1ASCII(value: String): ByteArray = value.toByteArray(Charsets.UTF_8)

private fun c1Text(data: ByteArray): String {
    c1Require(data.all { it.toInt() and 0xff < 0x80 }, ProductionC1Error.MALFORMED_CANONICAL)
    return data.toString(Charsets.US_ASCII)
}

private fun c1BE(value: ULong): ByteArray = ByteBuffer.allocate(8).order(ByteOrder.BIG_ENDIAN)
    .putLong(value.toLong()).array()

private fun c1BE(value: UInt): ByteArray = ByteBuffer.allocate(4).order(ByteOrder.BIG_ENDIAN)
    .putInt(value.toInt()).array()

private fun c1BE(value: UShort): ByteArray = ByteBuffer.allocate(2).order(ByteOrder.BIG_ENDIAN)
    .putShort(value.toShort()).array()

private fun c1UInt64(data: ByteArray): ULong {
    c1Require(data.size == 8, ProductionC1Error.MALFORMED_CANONICAL)
    return ByteBuffer.wrap(data).order(ByteOrder.BIG_ENDIAN).long.toULong()
}

private fun c1UInt32(data: ByteArray): UInt {
    c1Require(data.size == 4, ProductionC1Error.MALFORMED_CANONICAL)
    return ByteBuffer.wrap(data).order(ByteOrder.BIG_ENDIAN).int.toUInt()
}

private fun c1UInt16(data: ByteArray): UShort {
    c1Require(data.size == 2, ProductionC1Error.MALFORMED_CANONICAL)
    return ByteBuffer.wrap(data).order(ByteOrder.BIG_ENDIAN).short.toUShort()
}

private fun c1LowerHex(data: ByteArray): String = data.joinToString("") { "%02x".format(it) }

private fun c1DecodeLowerHex(value: String): ByteArray? {
    if (value.length % 2 != 0 || value.any { it !in '0'..'9' && it !in 'a'..'f' }) return null
    return runCatching {
        ByteArray(value.length / 2) { index -> value.substring(index * 2, index * 2 + 2).toInt(16).toByte() }
    }.getOrNull()
}

private fun c1ValidateDigest(value: String) {
    c1Require(c1DecodeLowerHex(value)?.size == 32, ProductionC1Error.INVALID_VALUE)
}

private fun c1ForceDecodeDigest(value: String): ByteArray = c1DecodeLowerHex(value) ?: byteArrayOf()

private fun c1OptionalDigestBytes(value: String?): ByteArray = c1ASCII(value ?: "none")

private fun c1OptionalDigest(data: ByteArray): String? {
    val value = c1Text(data)
    if (value == "none") return null
    c1ValidateDigest(value)
    return value
}

private fun c1DigestHex(data: ByteArray): String =
    c1LowerHex(MessageDigest.getInstance("SHA-256").digest(data))

private val C1_P256_PARAMETERS: ECParameterSpec = AlgorithmParameters.getInstance("EC").run {
    init(ECGenParameterSpec("secp256r1"))
    getParameterSpec(ECParameterSpec::class.java)
}
private val C1_P256_ORDER = BigInteger(
    "ffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551",
    16,
)
private val C1_P256_HALF_ORDER = BigInteger(
    "7fffffff800000007fffffffffffffffde737d56d38bcf4279dce5617e3192a8",
    16,
)
private val C1_BIG_INTEGER_TWO = BigInteger.valueOf(2L)

private fun c1PublicKey(x963: ByteArray): PublicKey {
    c1Require(
        x963.size == 65 && x963[0] == 0x04.toByte(),
        ProductionC1Error.INVALID_PUBLIC_KEY,
    )
    val point = ECPoint(
        BigInteger(1, x963.copyOfRange(1, 33)),
        BigInteger(1, x963.copyOfRange(33, 65)),
    )
    c1Require(c1IsOnCurve(point), ProductionC1Error.INVALID_PUBLIC_KEY)
    val publicKey = runCatching {
        KeyFactory.getInstance("EC").generatePublic(ECPublicKeySpec(point, C1_P256_PARAMETERS))
    }.getOrElse { c1Fail(ProductionC1Error.INVALID_PUBLIC_KEY) }
    c1Require(
        publicKey is ECPublicKey && c1EncodePoint(publicKey.w).contentEquals(x963),
        ProductionC1Error.INVALID_PUBLIC_KEY,
    )
    return publicKey
}

private fun c1KeyId(publicKey: PublicKey): String {
    val key = publicKey as? ECPublicKey ?: c1Fail(ProductionC1Error.INVALID_PUBLIC_KEY)
    c1Require(
        key.params.order == C1_P256_PARAMETERS.order && c1IsOnCurve(key.w),
        ProductionC1Error.INVALID_PUBLIC_KEY,
    )
    val canonical = runCatching {
        KeyFactory.getInstance("EC").generatePublic(X509EncodedKeySpec(key.encoded))
    }.getOrElse { c1Fail(ProductionC1Error.INVALID_PUBLIC_KEY) }
    c1Require(canonical.encoded.contentEquals(key.encoded), ProductionC1Error.INVALID_PUBLIC_KEY)
    return c1DigestHex(key.encoded)
}

private fun c1EncodePoint(point: ECPoint): ByteArray =
    byteArrayOf(0x04) + point.affineX.c1FixedUnsigned(32) + point.affineY.c1FixedUnsigned(32)

private fun BigInteger.c1FixedUnsigned(size: Int): ByteArray {
    val raw = toByteArray()
    val unsigned = if (raw.size > 1 && raw[0] == 0.toByte()) raw.copyOfRange(1, raw.size) else raw
    c1Require(unsigned.size <= size, ProductionC1Error.INVALID_PUBLIC_KEY)
    return ByteArray(size - unsigned.size) + unsigned
}

private fun c1IsOnCurve(point: ECPoint): Boolean {
    val prime = (C1_P256_PARAMETERS.curve.field as? ECFieldFp)?.p ?: return false
    val x = point.affineX
    val y = point.affineY
    if (x.signum() < 0 || y.signum() < 0 || x >= prime || y >= prime) return false
    return y.modPow(C1_BIG_INTEGER_TWO, prime) ==
        x.modPow(BigInteger.valueOf(3), prime)
            .add(C1_P256_PARAMETERS.curve.a.multiply(x))
            .add(C1_P256_PARAMETERS.curve.b)
            .mod(prime)
}

private fun c1SignatureTranscript(domain: String, claims: ByteArray): ByteArray =
    c1ASCII(domain) + byteArrayOf(0) + c1BE(claims.size.toUInt()) + claims

private data class C1SignatureComponents(val r: BigInteger, val s: BigInteger)

private fun c1ValidateCanonicalLowS(data: ByteArray): C1SignatureComponents {
    val bytes = data.map { it.toInt() and 0xff }
    c1Require(
        bytes.size in 8..72 && bytes[0] == 0x30 && bytes[1] == bytes.size - 2,
        ProductionC1Error.NON_CANONICAL_SIGNATURE,
    )
    val offset = intArrayOf(2)
    val r = c1DERInteger(bytes, offset)
    val s = c1DERInteger(bytes, offset)
    c1Require(
        offset[0] == bytes.size && r < C1_P256_ORDER && s < C1_P256_ORDER,
        ProductionC1Error.NON_CANONICAL_SIGNATURE,
    )
    c1Require(s <= C1_P256_HALF_ORDER, ProductionC1Error.HIGH_S)
    c1Require(c1EncodeDER(r, s).contentEquals(data), ProductionC1Error.NON_CANONICAL_SIGNATURE)
    return C1SignatureComponents(r, s)
}

private fun c1DERInteger(bytes: List<Int>, offset: IntArray): BigInteger {
    c1Require(
        offset[0] + 2 <= bytes.size && bytes[offset[0]] == 0x02,
        ProductionC1Error.NON_CANONICAL_SIGNATURE,
    )
    val length = bytes[offset[0] + 1]
    offset[0] += 2
    c1Require(
        length in 1..33 && offset[0] + length <= bytes.size,
        ProductionC1Error.NON_CANONICAL_SIGNATURE,
    )
    var value = bytes.subList(offset[0], offset[0] + length)
    offset[0] += length
    if (value[0] == 0) {
        c1Require(value.size > 1 && value[1] and 0x80 != 0, ProductionC1Error.NON_CANONICAL_SIGNATURE)
        value = value.drop(1)
    } else {
        c1Require(value[0] and 0x80 == 0, ProductionC1Error.NON_CANONICAL_SIGNATURE)
    }
    c1Require(value.size <= 32 && value.any { it != 0 }, ProductionC1Error.NON_CANONICAL_SIGNATURE)
    return BigInteger(1, value.map(Int::toByte).toByteArray())
}

private fun c1EncodeDER(r: BigInteger, s: BigInteger): ByteArray {
    fun integer(value: BigInteger): ByteArray {
        val raw = value.toByteArray()
        val canonical = if (raw.size > 1 && raw[0] == 0.toByte() && raw[1].toInt() and 0x80 == 0) {
            raw.copyOfRange(1, raw.size)
        } else {
            raw
        }
        return byteArrayOf(0x02, canonical.size.toByte()) + canonical
    }
    val body = integer(r) + integer(s)
    return byteArrayOf(0x30, body.size.toByte()) + body
}

private fun c1Sign(data: ByteArray, privateKey: PrivateKey): ByteArray {
    val der = runCatching {
        Signature.getInstance("SHA256withECDSA").run {
            initSign(privateKey)
            update(data)
            sign()
        }
    }.getOrElse { c1Fail(ProductionC1Error.INVALID_SIGNATURE) }
    val parsed = try {
        c1ParseCanonicalDERAllowHighS(der)
    } catch (_: ProductionC1Exception) {
        c1Fail(ProductionC1Error.INVALID_SIGNATURE)
    }
    val normalizedS = if (parsed.s > C1_P256_HALF_ORDER) C1_P256_ORDER - parsed.s else parsed.s
    return c1EncodeDER(parsed.r, normalizedS).also(::c1ValidateCanonicalLowS)
}

private fun c1ParseCanonicalDERAllowHighS(data: ByteArray): C1SignatureComponents {
    val bytes = data.map { it.toInt() and 0xff }
    c1Require(
        bytes.size in 8..72 && bytes[0] == 0x30 && bytes[1] == bytes.size - 2,
        ProductionC1Error.NON_CANONICAL_SIGNATURE,
    )
    val offset = intArrayOf(2)
    val result = C1SignatureComponents(c1DERInteger(bytes, offset), c1DERInteger(bytes, offset))
    c1Require(
        offset[0] == bytes.size && result.r < C1_P256_ORDER && result.s < C1_P256_ORDER,
        ProductionC1Error.NON_CANONICAL_SIGNATURE,
    )
    c1Require(c1EncodeDER(result.r, result.s).contentEquals(data), ProductionC1Error.NON_CANONICAL_SIGNATURE)
    return result
}

private fun c1Verify(signature: ByteArray, transcript: ByteArray, publicKey: PublicKey) {
    c1ValidateCanonicalLowS(signature)
    val valid = runCatching {
        Signature.getInstance("SHA256withECDSA").run {
            initVerify(publicKey)
            update(transcript)
            verify(signature)
        }
    }.getOrDefault(false)
    c1Require(valid, ProductionC1Error.INVALID_SIGNATURE)
}

private fun c1ValidateWindow(
    issuedAtMs: ULong,
    notBeforeMs: ULong,
    expiresAtMs: ULong,
    maximumLifetimeMs: ULong,
    nowMs: ULong,
) {
    c1Require(
        issuedAtMs <= notBeforeMs && notBeforeMs < expiresAtMs &&
            expiresAtMs - issuedAtMs <= maximumLifetimeMs,
        ProductionC1Error.INVALID_VALUE,
    )
    val futureLimit = nowMs + ProductionC1Contract.MAXIMUM_CLOCK_SKEW_MS
    c1Require(futureLimit >= nowMs && issuedAtMs <= futureLimit, ProductionC1Error.ISSUED_IN_FUTURE)
    c1Require(notBeforeMs <= futureLimit, ProductionC1Error.NOT_YET_VALID)
    c1Require(nowMs < expiresAtMs, ProductionC1Error.EXPIRED)
}

private fun c1ValidateVerifiedKeysetUse(
    verifiedKeyset: VerifiedProductionC1ServiceKeyset,
    nowMs: ULong,
) {
    val keyset = verifiedKeyset.keyset
    c1ValidateWindow(
        keyset.issuedAtMs,
        keyset.issuedAtMs,
        keyset.expiresAtMs,
        ProductionC1Contract.MAXIMUM_KEYSET_LIFETIME_MS,
        nowMs,
    )
}

private fun c1ValidateVerifiedPairStatusUse(
    verifiedStatus: VerifiedProductionC1PairStatus,
    nowMs: ULong,
) {
    c1ValidateVerifiedKeysetUse(verifiedStatus.verifiedKeyset, nowMs)
    val status = verifiedStatus.status
    c1ValidateWindow(
        status.issuedAtMs,
        status.issuedAtMs,
        status.expiresAtMs,
        ProductionC1Contract.MAXIMUM_STATUS_LIFETIME_MS,
        nowMs,
    )
    c1DelegatedKey(
        status.signingKeyId,
        ProductionC1DelegatedKeyPurpose.PAIR_STATUS,
        verifiedStatus.verifiedKeyset,
        nowMs,
    )
}

private fun c1ValidateFreshPairTransitionUse(
    verified: VerifiedProductionC1FreshPairTransition,
    nowMs: ULong,
) {
    c1ValidateVerifiedPairStatusUse(verified.verifiedStatus, nowMs)
    c1ValidateWindow(
        verified.proof.issuedAtMs,
        verified.proof.issuedAtMs,
        verified.proof.expiresAtMs,
        ProductionC1Contract.MAXIMUM_FRESH_PAIR_LIFETIME_MS,
        nowMs,
    )
}

private fun c1ValidateVerifiedRoutePlanUse(
    verifiedPlan: VerifiedProductionC1RoutePlan,
    nowMs: ULong,
) {
    c1ValidateVerifiedKeysetUse(verifiedPlan.verifiedKeyset, nowMs)
    c1Require(
        verifiedPlan.claims.securityContextDigest == verifiedPlan.securityContext.digestHex() &&
            verifiedPlan.claims.kind == verifiedPlan.securityContext.routeKind,
        ProductionC1Error.ROUTE_MISMATCH,
    )
    val capability = verifiedPlan.capability
    c1ValidateWindow(
        capability.issuedAtMs,
        capability.notBeforeMs,
        capability.expiresAtMs,
        ProductionC1Contract.MAXIMUM_ROUTE_LIFETIME_MS,
        nowMs,
    )
    c1ValidateWindow(
        capability.issuedAtMs,
        verifiedPlan.claims.notBeforeMs,
        verifiedPlan.claims.expiresAtMs,
        ProductionC1Contract.MAXIMUM_ROUTE_LIFETIME_MS,
        nowMs,
    )
    c1DelegatedKey(
        capability.signingKeyId,
        ProductionC1DelegatedKeyPurpose.ROUTE_CAPABILITY,
        verifiedPlan.verifiedKeyset,
        nowMs,
    )
}

private fun c1DelegatedKey(
    id: String,
    purpose: ProductionC1DelegatedKeyPurpose,
    keyset: VerifiedProductionC1ServiceKeyset,
    nowMs: ULong,
): ProductionC1DelegatedKey {
    val key = keyset.keyset.delegatedKeys.firstOrNull { it.keyId == id }
        ?: c1Fail(ProductionC1Error.KEY_UNAVAILABLE)
    c1Require(
        key.keysetVersion == keyset.keyset.keysetVersion ||
            (keyset.keyset.keysetVersion > 1uL && key.keysetVersion == keyset.keyset.keysetVersion - 1uL),
        ProductionC1Error.KEY_UNAVAILABLE,
    )
    c1Require(key.purposes.contains(purpose), ProductionC1Error.KEY_PURPOSE_MISMATCH)
    if (key.revokedAtMs?.let { it <= nowMs } == true) c1Fail(ProductionC1Error.KEY_REVOKED)
    c1Require(key.notBeforeMs <= nowMs, ProductionC1Error.NOT_YET_VALID)
    c1Require(nowMs < key.expiresAtMs, ProductionC1Error.EXPIRED)
    return key
}

private fun c1TransitionSequence(
    history: List<ProductionPairTransitionHistoryEntry>,
    authority: ProductionPairAuthorityState,
): List<ProductionPairTransitionHistoryEntry> = history + ProductionPairTransitionHistoryEntry(
    authority.transitionId,
    authority.transitionRequestDigest,
)

private fun c1TransitionKindMatchesState(status: ProductionC1PairStatus): Boolean =
    when (status.transitionKind) {
        ProductionC1TransitionKind.GENESIS ->
            status.evidenceKind == ProductionC1AuthorizationEvidenceKind.INITIAL_PAIRING &&
                status.authority.status == ProductionPairAuthorityStatus.ACTIVE
        ProductionC1TransitionKind.SAME_EPOCH ->
            status.evidenceKind == ProductionC1AuthorizationEvidenceKind.SAME_EPOCH_TRANSITION &&
                status.authority.status == ProductionPairAuthorityStatus.ACTIVE
        ProductionC1TransitionKind.REVOKE ->
            status.evidenceKind == ProductionC1AuthorizationEvidenceKind.DENY_ONLY_REVOCATION &&
                status.authority.status == ProductionPairAuthorityStatus.REVOKED
        ProductionC1TransitionKind.FRESH_PAIR ->
            status.evidenceKind == ProductionC1AuthorizationEvidenceKind.DUAL_SIGNED_FRESH_PAIR &&
                status.authority.status == ProductionPairAuthorityStatus.ACTIVE
    }

private fun c1ValidateAuthorityAdvance(
    previous: ProductionPairAuthorityState,
    next: ProductionPairAuthorityState,
    transitionKind: ProductionC1TransitionKind,
) {
    c1Require(
        next.authorityRevision >= previous.authorityRevision && next.generation >= previous.generation &&
            next.serviceConfigVersion >= previous.serviceConfigVersion && next.keysetVersion >= previous.keysetVersion &&
            next.revocationCounter >= previous.revocationCounter && next.protocolFloor >= previous.protocolFloor,
        ProductionC1Error.STATE_MISMATCH,
    )
    when (transitionKind) {
        ProductionC1TransitionKind.SAME_EPOCH,
        ProductionC1TransitionKind.REVOKE,
        -> {
            c1Require(
                next.pairEpoch == previous.pairEpoch && next.pairBindingDigest == previous.pairBindingDigest &&
                    next.clientIdentityFingerprint == previous.clientIdentityFingerprint &&
                    next.runtimeIdentityFingerprint == previous.runtimeIdentityFingerprint &&
                    !(previous.status == ProductionPairAuthorityStatus.REVOKED &&
                        next.status == ProductionPairAuthorityStatus.ACTIVE),
                ProductionC1Error.STATE_MISMATCH,
            )
            if (transitionKind == ProductionC1TransitionKind.REVOKE) {
                c1Require(
                    previous.status == ProductionPairAuthorityStatus.ACTIVE &&
                        previous.revocationCounter < ULong.MAX_VALUE &&
                        next.revocationCounter == previous.revocationCounter + 1uL,
                    ProductionC1Error.STATE_MISMATCH,
                )
            }
        }
        ProductionC1TransitionKind.FRESH_PAIR -> c1Require(
            previous.pairEpoch < ULong.MAX_VALUE && next.pairEpoch == previous.pairEpoch + 1uL,
            ProductionC1Error.INVALID_FRESH_PAIR,
        )
        ProductionC1TransitionKind.GENESIS -> c1Fail(ProductionC1Error.STATE_MISMATCH)
    }
}

private fun c1IsCanonicalServerName(value: String): Boolean {
    if (value.isEmpty() || value == "none" || value.toByteArray(Charsets.UTF_8).size > 253 ||
        value != value.lowercase() || value.any { it.code >= 128 }
    ) {
        return false
    }
    val labels = value.split('.', ignoreCase = false, limit = Int.MAX_VALUE)
    return labels.isNotEmpty() && labels.all { label ->
        label.isNotEmpty() && label.toByteArray(Charsets.UTF_8).size <= 63 &&
            label.first() != '-' && label.last() != '-' &&
            label.all { it in '0'..'9' || it in 'a'..'z' || it == '-' }
    }
}

private fun c1BoundedUTF8(value: String, maximum: Int): ByteArray =
    value.toByteArray(Charsets.UTF_8).also {
        c1Require(it.isNotEmpty() && it.size <= maximum, ProductionC1Error.LIMIT_EXCEEDED)
    }

private fun c1Require(condition: Boolean, error: ProductionC1Error) {
    if (!condition) throw ProductionC1Exception(error)
}

private fun c1Fail(error: ProductionC1Error): Nothing = throw ProductionC1Exception(error)
