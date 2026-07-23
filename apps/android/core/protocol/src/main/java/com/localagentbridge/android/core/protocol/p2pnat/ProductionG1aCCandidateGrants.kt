package com.localagentbridge.android.core.protocol.p2pnat

import java.io.ByteArrayOutputStream

enum class ProductionC1P2PDestinationPolicy {
    PUBLIC_ONLY;

    companion object {
        const val POLICY_ID: String = "public_only_special_use_deny_iana_2025_10_09_v1"
        const val POLICY_VERSION: ULong = 1uL
        val INITIATOR_ROLE: P2pNatRole = P2pNatRole.CLIENT
        val CONNECTOR_TARGET_ROLE: P2pNatRole = P2pNatRole.RUNTIME
    }
}

object ProductionC1PublicOnlyV1Policy {
    const val ID: String = ProductionC1P2PDestinationPolicy.POLICY_ID
    const val VERSION: ULong = ProductionC1P2PDestinationPolicy.POLICY_VERSION

    private val ipv4SpecialUse = listOf(
        byteArrayOf(0, 0, 0, 0) to 8,
        byteArrayOf(10, 0, 0, 0) to 8,
        byteArrayOf(100, 64, 0, 0) to 10,
        byteArrayOf(127, 0, 0, 0) to 8,
        byteArrayOf(169.toByte(), 254.toByte(), 0, 0) to 16,
        byteArrayOf(172.toByte(), 16, 0, 0) to 12,
        byteArrayOf(192.toByte(), 0, 0, 0) to 24,
        byteArrayOf(192.toByte(), 0, 2, 0) to 24,
        byteArrayOf(192.toByte(), 31, 196.toByte(), 0) to 24,
        byteArrayOf(192.toByte(), 52, 193.toByte(), 0) to 24,
        byteArrayOf(192.toByte(), 88, 99, 0) to 24,
        byteArrayOf(192.toByte(), 168.toByte(), 0, 0) to 16,
        byteArrayOf(192.toByte(), 175.toByte(), 48, 0) to 24,
        byteArrayOf(198.toByte(), 18, 0, 0) to 15,
        byteArrayOf(198.toByte(), 51, 100, 0) to 24,
        byteArrayOf(203.toByte(), 0, 113, 0) to 24,
        byteArrayOf(224.toByte(), 0, 0, 0) to 4,
        byteArrayOf(240.toByte(), 0, 0, 0) to 4,
    )

    private val ipv6SpecialUse = listOf(
        ByteArray(16) to 128,
        (ByteArray(15) + byteArrayOf(1)) to 128,
        (ByteArray(10) + byteArrayOf(0xff.toByte(), 0xff.toByte()) + ByteArray(4)) to 96,
        (byteArrayOf(0, 0x64, 0xff.toByte(), 0x9b.toByte()) + ByteArray(12)) to 96,
        (byteArrayOf(0, 0x64, 0xff.toByte(), 0x9b.toByte(), 0, 1) + ByteArray(10)) to 48,
        (byteArrayOf(1, 0) + ByteArray(14)) to 64,
        (byteArrayOf(0x20, 1) + ByteArray(14)) to 23,
        (byteArrayOf(0x20, 1, 0, 0) + ByteArray(12)) to 32,
        (byteArrayOf(0x20, 1, 0, 1) + ByteArray(10) + byteArrayOf(0, 1)) to 128,
        (byteArrayOf(0x20, 1, 0, 1) + ByteArray(10) + byteArrayOf(0, 2)) to 128,
        (byteArrayOf(0x20, 1, 0, 2) + ByteArray(12)) to 48,
        (byteArrayOf(0x20, 1, 0, 3) + ByteArray(12)) to 32,
        (byteArrayOf(0x20, 1, 0, 4, 1, 0x12) + ByteArray(10)) to 48,
        (byteArrayOf(0x20, 1, 0, 0x10) + ByteArray(12)) to 28,
        (byteArrayOf(0x20, 1, 0, 0x20) + ByteArray(12)) to 28,
        (byteArrayOf(0x20, 1, 0, 0x30) + ByteArray(12)) to 28,
        (byteArrayOf(0x20, 1, 0x0d, 0xb8.toByte()) + ByteArray(12)) to 32,
        (byteArrayOf(0x20, 2) + ByteArray(14)) to 16,
        (byteArrayOf(0x26, 0x20, 0, 0x4f, 0x80.toByte(), 0) + ByteArray(10)) to 48,
        (byteArrayOf(0x3f, 0xff.toByte()) + ByteArray(14)) to 20,
        (byteArrayOf(0x5f, 0) + ByteArray(14)) to 16,
        (byteArrayOf(0xfc.toByte(), 0) + ByteArray(14)) to 7,
        (byteArrayOf(0xfe.toByte(), 0x80.toByte()) + ByteArray(14)) to 10,
        (byteArrayOf(0xff.toByte(), 0) + ByteArray(14)) to 8,
    )

    fun allows(address: ByteArray, port: Int): Boolean {
        if (port !in 1_024..65_535) return false
        if (address.size == 4) {
            return ipv4SpecialUse.none { (prefix, bits) -> prefixMatches(address, prefix, bits) }
        }
        if (address.size != 16 || (address[0].toInt() and 0xe0) != 0x20) return false
        return ipv6SpecialUse.none { (prefix, bits) -> prefixMatches(address, prefix, bits) }
    }

    private fun prefixMatches(address: ByteArray, prefix: ByteArray, bitCount: Int): Boolean {
        if (address.size != prefix.size) return false
        val wholeBytes = bitCount / 8
        val remainingBits = bitCount % 8
        for (index in 0 until wholeBytes) {
            if (address[index] != prefix[index]) return false
        }
        if (remainingBits == 0) return true
        val mask = 0xff shl (8 - remainingBits)
        return (address[wholeBytes].toInt() and mask) == (prefix[wholeBytes].toInt() and mask)
    }
}

class ProductionC1BilateralRouteAuthorizations internal constructor(
    val clientPublish: ProductionRouteAuthorization,
    val runtimeFetchClient: ProductionRouteAuthorization,
    val runtimePublish: ProductionRouteAuthorization,
    val clientFetchRuntime: ProductionRouteAuthorization,
    val finalP2PDirect: ProductionRouteAuthorization,
) {
    internal val operationOrder: List<ProductionRouteAuthorization>
        get() = listOf(clientPublish, runtimeFetchClient, runtimePublish, clientFetchRuntime)

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is ProductionC1BilateralRouteAuthorizations &&
                clientPublish == other.clientPublish &&
                runtimeFetchClient == other.runtimeFetchClient &&
                runtimePublish == other.runtimePublish &&
                clientFetchRuntime == other.clientFetchRuntime &&
                finalP2PDirect == other.finalP2PDirect)

    override fun hashCode(): Int {
        var result = clientPublish.hashCode()
        result = 31 * result + runtimeFetchClient.hashCode()
        result = 31 * result + runtimePublish.hashCode()
        result = 31 * result + clientFetchRuntime.hashCode()
        return 31 * result + finalP2PDirect.hashCode()
    }
}

class VerifiedProductionC1CandidateP2PPlan private constructor(
    val bilateral: VerifiedProductionC1BilateralCandidateCapabilities,
    val pathValidationReceipt: PathValidationReceipt,
    val pathValidationReceiptDigest: String,
    val selectedClientCandidate: P2pCandidate,
    val selectedRuntimeCandidate: P2pCandidate,
    val effectiveNotBeforeMs: ULong,
    val expiresAtMs: ULong,
    private val basePlan: VerifiedProductionC1RoutePlan,
) {
    val claims: ProductionC1RoutePlanClaims get() = basePlan.claims
    val capability: ProductionC1RouteCapability get() = basePlan.capability
    val securityContext: ProductionC1PreauthorizationSessionContext get() = basePlan.securityContext

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is VerifiedProductionC1CandidateP2PPlan &&
                bilateral == other.bilateral &&
                pathValidationReceipt == other.pathValidationReceipt &&
                pathValidationReceiptDigest == other.pathValidationReceiptDigest &&
                selectedClientCandidate == other.selectedClientCandidate &&
                selectedRuntimeCandidate == other.selectedRuntimeCandidate &&
                effectiveNotBeforeMs == other.effectiveNotBeforeMs &&
                expiresAtMs == other.expiresAtMs &&
                basePlan.claims == other.basePlan.claims &&
                basePlan.capability == other.basePlan.capability &&
                basePlan.securityContext == other.basePlan.securityContext)

    override fun hashCode(): Int {
        var result = bilateral.hashCode()
        result = 31 * result + pathValidationReceipt.hashCode()
        result = 31 * result + pathValidationReceiptDigest.hashCode()
        result = 31 * result + selectedClientCandidate.hashCode()
        result = 31 * result + selectedRuntimeCandidate.hashCode()
        result = 31 * result + effectiveNotBeforeMs.hashCode()
        result = 31 * result + expiresAtMs.hashCode()
        return 31 * result + basePlan.claims.hashCode()
    }

    companion object {
        internal fun verify(
            claims: ProductionC1RoutePlanClaims,
            capability: ProductionC1RouteCapability,
            securityContext: ProductionC1PreauthorizationSessionContext,
            bilateral: VerifiedProductionC1BilateralCandidateCapabilities,
            selectedClientCandidate: P2pCandidate,
            selectedRuntimeCandidate: P2pCandidate,
            pathValidationReceiptCanonicalBytes: ByteArray,
            authority: ProductionPairAuthorityState,
            verifiedKeyset: VerifiedProductionC1ServiceKeyset,
            destinationPolicy: ProductionC1P2PDestinationPolicy,
            nowMs: ULong,
        ): VerifiedProductionC1CandidateP2PPlan {
            validateBilateralUse(bilateral, authority, nowMs)
            grantRequire(
                verifiedKeyset.keyset.canonicalBytes().contentEquals(
                    bilateral.clientPublish.verifiedKeyset.keyset.canonicalBytes(),
                ),
                ProductionC1CandidateCapabilityError.AUTHORITY_MISMATCH,
            )
            grantRequire(
                claims.kind == ProductionC1RouteKind.P2P_DIRECT &&
                    securityContext.routeKind == ProductionC1RouteKind.P2P_DIRECT &&
                    securityContext.sessionId == bilateral.clientPublish.capability.sessionId &&
                    bilateral.all.all { it.securityContext == securityContext },
                ProductionC1CandidateCapabilityError.ROUTE_MISMATCH,
            )
            validateDestination(claims.connector.addressBytes, claims.connector.port.toInt(), destinationPolicy)
            val selectedPairDigest = validateSelectedCandidates(
                bilateral,
                selectedClientCandidate,
                selectedRuntimeCandidate,
                claims.connector,
            )
            val receiptBytes = pathValidationReceiptCanonicalBytes.copyOf()
            val receipt = try {
                P2pNatCanonicalCodec.decodeFreshPathValidationReceipt(receiptBytes, nowMs)
            } catch (_: IllegalArgumentException) {
                grantFail(ProductionC1CandidateCapabilityError.ROUTE_MISMATCH)
            }
            grantRequire(
                P2pNatCanonicalCodec.encode(receipt).contentEquals(receiptBytes) &&
                    receipt.transportContext == TransportContext.DIRECT &&
                    receipt.sessionId == securityContext.sessionId &&
                    receipt.generation == authority.generation &&
                    receipt.candidatePairDigest == selectedPairDigest &&
                    nowMs < receipt.expiresAtMillis,
                ProductionC1CandidateCapabilityError.ROUTE_MISMATCH,
            )
            val receiptDigest = ProductionC1InternalBridge.digestHex(receiptBytes)
            val base = ProductionC1Verifier.verifyCandidateP2PRoutePlanBase(
                claims,
                capability,
                securityContext,
                authority,
                verifiedKeyset,
                nowMs,
            )
            val keyset = bilateral.clientPublish.verifiedKeyset.keyset
            val delegatedExpiries = bilateral.all.map { value ->
                keyset.delegatedKeys.firstOrNull {
                    it.keyId == value.capability.signingKeyId &&
                        it.purposes.contains(value.capability.operation.keyPurpose)
                }?.expiresAtMs ?: grantFail(ProductionC1CandidateCapabilityError.AUTHORITY_MISMATCH)
            }
            val routeDelegated = keyset.delegatedKeys.firstOrNull {
                it.keyId == capability.signingKeyId &&
                    it.purposes.contains(ProductionC1DelegatedKeyPurpose.ROUTE_CAPABILITY)
            } ?: grantFail(ProductionC1CandidateCapabilityError.AUTHORITY_MISMATCH)
            val notBefore = buildList {
                add(claims.notBeforeMs)
                add(capability.notBeforeMs)
                add(receipt.validatedAtMillis)
                bilateral.all.forEach {
                    add(it.capability.notBeforeMs)
                    add(it.endpointOperationProof.notBeforeMs)
                }
            }.maxOrNull() ?: 0uL
            val expires = buildList {
                add(receipt.expiresAtMillis)
                add(claims.expiresAtMs)
                add(capability.expiresAtMs)
                add(keyset.expiresAtMs)
                add(routeDelegated.expiresAtMs)
                addAll(delegatedExpiries)
                bilateral.all.forEach {
                    add(it.capability.expiresAtMs)
                    add(it.endpointOperationProof.expiresAtMs)
                    add(it.candidateBatch.expiresAtMillis)
                }
            }.minOrNull() ?: 0uL
            grantRequire(
                claims.selectedPathReceiptDigest == receiptDigest &&
                    nowMs >= notBefore && nowMs < expires,
                ProductionC1CandidateCapabilityError.ROUTE_MISMATCH,
            )
            return VerifiedProductionC1CandidateP2PPlan(
                bilateral,
                receipt,
                receiptDigest,
                selectedClientCandidate,
                selectedRuntimeCandidate,
                notBefore,
                expires,
                base,
            )
        }

        internal fun refresh(
            plan: VerifiedProductionC1CandidateP2PPlan,
            authority: ProductionPairAuthorityState,
            nowMs: ULong,
        ) {
            validatePlanUse(plan, authority, nowMs)
        }

        internal fun refreshBaseAuthorization(
            plan: VerifiedProductionC1CandidateP2PPlan,
            nowMs: ULong,
        ) {
            ProductionC1Verifier.makeCandidateP2PRouteAuthorizationBase(plan.basePlan, nowMs)
        }
    }
}

/** Unsigned derived artifact; decoding it does not establish authority or activation. */
class ProductionC1P2PGrantEvidence private constructor(
    val serviceIdDigest: String,
    val keysetVersion: ULong,
    val pairAuthorityDigest: String,
    val pairBindingDigest: String,
    val pairEpoch: ULong,
    val generation: ULong,
    val sessionId: String,
    val attemptId: String,
    val clientIdentityFingerprint: String,
    val runtimeIdentityFingerprint: String,
    val clientCandidateBatchDigest: String,
    val clientCandidateBatchByteCount: UInt,
    val runtimeCandidateBatchDigest: String,
    val runtimeCandidateBatchByteCount: UInt,
    operationCapabilityDigests: List<String>,
    operationAuthorizationDigests: List<String>,
    val bilateralPublishDigest: String,
    val bilateralFetchDigest: String,
    val candidatePairDigest: String,
    val pathValidationReceiptDigest: String,
    val finalRouteAuthorizationDigest: String,
    val c1RoutePlanClaimsDigest: String,
    val c1RouteCapabilityDigest: String,
    operationReceiptDigests: List<String>,
    val initiatorRole: P2pNatRole,
    val connectorTargetRole: P2pNatRole,
    val destinationPolicyId: String,
    val destinationPolicyVersion: ULong,
    val securityContextDigest: String,
    val effectiveNotBeforeMs: ULong,
    val expiresAtMs: ULong,
) {
    private val capabilityDigests = operationCapabilityDigests.toList()
    private val authorizationDigests = operationAuthorizationDigests.toList()
    private val receiptDigests = operationReceiptDigests.toList()

    val operationCapabilityDigests: List<String> get() = capabilityDigests.toList()
    val operationAuthorizationDigests: List<String> get() = authorizationDigests.toList()
    val operationReceiptDigests: List<String> get() = receiptDigests.toList()

    init {
        val scalarDigests = listOf(
            serviceIdDigest,
            pairAuthorityDigest,
            pairBindingDigest,
            clientIdentityFingerprint,
            runtimeIdentityFingerprint,
            clientCandidateBatchDigest,
            runtimeCandidateBatchDigest,
            bilateralPublishDigest,
            bilateralFetchDigest,
            candidatePairDigest,
            pathValidationReceiptDigest,
            finalRouteAuthorizationDigest,
            c1RoutePlanClaimsDigest,
            c1RouteCapabilityDigest,
            securityContextDigest,
        )
        (scalarDigests + capabilityDigests + authorizationDigests + receiptDigests)
            .forEach(ProductionC1InternalBridge::validateDigest)
        grantRequire(
            keysetVersion > 0uL && pairEpoch > 0uL && generation > 0uL &&
                grantIsLowerHex(sessionId, 32) && grantIsLowerHex(attemptId, 64) &&
                clientIdentityFingerprint != runtimeIdentityFingerprint &&
                clientCandidateBatchByteCount > 0u && runtimeCandidateBatchByteCount > 0u &&
                capabilityDigests.size == 4 && authorizationDigests.size == 4 && receiptDigests.size == 4 &&
                capabilityDigests.toSet().size == 4 &&
                authorizationDigests.toSet().size == 4 && receiptDigests.toSet().size == 4 &&
                initiatorRole == ProductionC1P2PDestinationPolicy.INITIATOR_ROLE &&
                connectorTargetRole == ProductionC1P2PDestinationPolicy.CONNECTOR_TARGET_ROLE &&
                destinationPolicyId == ProductionC1P2PDestinationPolicy.POLICY_ID &&
                destinationPolicyVersion == ProductionC1P2PDestinationPolicy.POLICY_VERSION &&
                effectiveNotBeforeMs < expiresAtMs,
            ProductionC1CandidateCapabilityError.INVALID_VALUE,
        )
        grantRequire(
            canonicalBytes().size <= ProductionC1CandidateCapabilityContract.MAXIMUM_GRANT_EVIDENCE_BYTES,
            ProductionC1CandidateCapabilityError.INVALID_VALUE,
        )
    }

    fun canonicalBytes(): ByteArray = ProductionC1InternalBridge.encode(
        ProductionC1CandidateCapabilityContract.GRANT_EVIDENCE_OBJECT_TYPE,
        listOf(
            ProductionC1InternalBridge.ascii(ProductionC1Contract.SUITE),
            ProductionC1InternalBridge.be(ProductionC1CandidateCapabilityContract.REVISION),
            ProductionC1InternalBridge.ascii(serviceIdDigest),
            ProductionC1InternalBridge.be(keysetVersion),
            ProductionC1InternalBridge.ascii(pairAuthorityDigest),
            ProductionC1InternalBridge.ascii(pairBindingDigest),
            ProductionC1InternalBridge.be(pairEpoch),
            ProductionC1InternalBridge.be(generation),
            ProductionC1InternalBridge.ascii(sessionId),
            ProductionC1InternalBridge.ascii(attemptId),
            ProductionC1InternalBridge.ascii(clientIdentityFingerprint),
            ProductionC1InternalBridge.ascii(runtimeIdentityFingerprint),
            ProductionC1InternalBridge.ascii(clientCandidateBatchDigest),
            ProductionC1InternalBridge.be(clientCandidateBatchByteCount),
            ProductionC1InternalBridge.ascii(runtimeCandidateBatchDigest),
            ProductionC1InternalBridge.be(runtimeCandidateBatchByteCount),
            ProductionC1InternalBridge.ascii(OPERATION_ORDER),
            packDigests(capabilityDigests),
            packDigests(authorizationDigests),
            ProductionC1InternalBridge.ascii(bilateralPublishDigest),
            ProductionC1InternalBridge.ascii(bilateralFetchDigest),
            ProductionC1InternalBridge.ascii(candidatePairDigest),
            ProductionC1InternalBridge.ascii(pathValidationReceiptDigest),
            ProductionC1InternalBridge.ascii(finalRouteAuthorizationDigest),
            ProductionC1InternalBridge.ascii(c1RoutePlanClaimsDigest),
            ProductionC1InternalBridge.ascii(c1RouteCapabilityDigest),
            packDigests(receiptDigests),
            ProductionC1InternalBridge.ascii(initiatorRole.wireValue),
            ProductionC1InternalBridge.ascii(connectorTargetRole.wireValue),
            ProductionC1InternalBridge.ascii(destinationPolicyId),
            ProductionC1InternalBridge.be(destinationPolicyVersion),
            ProductionC1InternalBridge.ascii(securityContextDigest),
            ProductionC1InternalBridge.be(effectiveNotBeforeMs),
            ProductionC1InternalBridge.be(expiresAtMs),
        ),
    )

    fun digestHex(): String = ProductionC1InternalBridge.digestHex(canonicalBytes())

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is ProductionC1P2PGrantEvidence && canonicalBytes().contentEquals(other.canonicalBytes()))

    override fun hashCode(): Int = canonicalBytes().contentHashCode()

    companion object {
        const val OPERATION_ORDER: String =
            "client_publish,runtime_fetch_client,runtime_publish,client_fetch_runtime"

        fun decode(data: ByteArray): ProductionC1P2PGrantEvidence {
            val fields = ProductionC1InternalBridge.decode(
                data,
                ProductionC1CandidateCapabilityContract.GRANT_EVIDENCE_OBJECT_TYPE,
                34,
                ProductionC1CandidateCapabilityContract.MAXIMUM_GRANT_EVIDENCE_BYTES,
            )
            grantRequire(
                ProductionC1InternalBridge.text(fields[0]) == ProductionC1Contract.SUITE &&
                    ProductionC1InternalBridge.uint64(fields[1]) ==
                    ProductionC1CandidateCapabilityContract.REVISION &&
                    ProductionC1InternalBridge.text(fields[16]) == OPERATION_ORDER,
                ProductionC1CandidateCapabilityError.INVALID_VALUE,
            )
            val result = ProductionC1P2PGrantEvidence(
                ProductionC1InternalBridge.text(fields[2]),
                ProductionC1InternalBridge.uint64(fields[3]),
                ProductionC1InternalBridge.text(fields[4]),
                ProductionC1InternalBridge.text(fields[5]),
                ProductionC1InternalBridge.uint64(fields[6]),
                ProductionC1InternalBridge.uint64(fields[7]),
                ProductionC1InternalBridge.text(fields[8]),
                ProductionC1InternalBridge.text(fields[9]),
                ProductionC1InternalBridge.text(fields[10]),
                ProductionC1InternalBridge.text(fields[11]),
                ProductionC1InternalBridge.text(fields[12]),
                ProductionC1InternalBridge.uint32(fields[13]),
                ProductionC1InternalBridge.text(fields[14]),
                ProductionC1InternalBridge.uint32(fields[15]),
                unpackDigests(fields[17]),
                unpackDigests(fields[18]),
                ProductionC1InternalBridge.text(fields[19]),
                ProductionC1InternalBridge.text(fields[20]),
                ProductionC1InternalBridge.text(fields[21]),
                ProductionC1InternalBridge.text(fields[22]),
                ProductionC1InternalBridge.text(fields[23]),
                ProductionC1InternalBridge.text(fields[24]),
                ProductionC1InternalBridge.text(fields[25]),
                unpackDigests(fields[26]),
                grantRole(fields[27]),
                grantRole(fields[28]),
                ProductionC1InternalBridge.text(fields[29]),
                ProductionC1InternalBridge.uint64(fields[30]),
                ProductionC1InternalBridge.text(fields[31]),
                ProductionC1InternalBridge.uint64(fields[32]),
                ProductionC1InternalBridge.uint64(fields[33]),
            )
            grantRequire(
                result.canonicalBytes().contentEquals(data),
                ProductionC1CandidateCapabilityError.MALFORMED_CANONICAL,
            )
            return result
        }

        internal fun derived(
            serviceIdDigest: String,
            keysetVersion: ULong,
            pairAuthorityDigest: String,
            pairBindingDigest: String,
            pairEpoch: ULong,
            generation: ULong,
            sessionId: String,
            attemptId: String,
            clientIdentityFingerprint: String,
            runtimeIdentityFingerprint: String,
            clientCandidateBatchDigest: String,
            clientCandidateBatchByteCount: UInt,
            runtimeCandidateBatchDigest: String,
            runtimeCandidateBatchByteCount: UInt,
            operationCapabilityDigests: List<String>,
            operationAuthorizationDigests: List<String>,
            bilateralPublishDigest: String,
            bilateralFetchDigest: String,
            candidatePairDigest: String,
            pathValidationReceiptDigest: String,
            finalRouteAuthorizationDigest: String,
            c1RoutePlanClaimsDigest: String,
            c1RouteCapabilityDigest: String,
            operationReceiptDigests: List<String>,
            initiatorRole: P2pNatRole,
            connectorTargetRole: P2pNatRole,
            destinationPolicyId: String,
            destinationPolicyVersion: ULong,
            securityContextDigest: String,
            effectiveNotBeforeMs: ULong,
            expiresAtMs: ULong,
        ): ProductionC1P2PGrantEvidence = ProductionC1P2PGrantEvidence(
            serviceIdDigest,
            keysetVersion,
            pairAuthorityDigest,
            pairBindingDigest,
            pairEpoch,
            generation,
            sessionId,
            attemptId,
            clientIdentityFingerprint,
            runtimeIdentityFingerprint,
            clientCandidateBatchDigest,
            clientCandidateBatchByteCount,
            runtimeCandidateBatchDigest,
            runtimeCandidateBatchByteCount,
            operationCapabilityDigests,
            operationAuthorizationDigests,
            bilateralPublishDigest,
            bilateralFetchDigest,
            candidatePairDigest,
            pathValidationReceiptDigest,
            finalRouteAuthorizationDigest,
            c1RoutePlanClaimsDigest,
            c1RouteCapabilityDigest,
            operationReceiptDigests,
            initiatorRole,
            connectorTargetRole,
            destinationPolicyId,
            destinationPolicyVersion,
            securityContextDigest,
            effectiveNotBeforeMs,
            expiresAtMs,
        )

        private fun packDigests(values: List<String>): ByteArray {
            grantRequire(values.size == 4, ProductionC1CandidateCapabilityError.INVALID_VALUE)
            return ByteArrayOutputStream().apply {
                values.forEach { write(ProductionC1InternalBridge.rawDigest(it)) }
            }.toByteArray()
        }

        private fun unpackDigests(data: ByteArray): List<String> {
            grantRequire(data.size == 128, ProductionC1CandidateCapabilityError.MALFORMED_CANONICAL)
            return (0 until 4).map { index ->
                data.copyOfRange(index * 32, (index + 1) * 32).toLowerHex()
            }
        }
    }
}

/** Unsigned derived artifact; decoding it does not establish authority or activation. */
class ProductionC1P2PGrantAuthorization private constructor(
    val grantEvidenceDigest: String,
    val pairAuthorityDigest: String,
    val pairBindingDigest: String,
    val pairEpoch: ULong,
    val generation: ULong,
    val clientIdentityFingerprint: String,
    val runtimeIdentityFingerprint: String,
    val sessionId: String,
    val attemptId: String,
    val initiatorRole: P2pNatRole,
    val connectorTargetRole: P2pNatRole,
    val destinationPolicyId: String,
    val destinationPolicyVersion: ULong,
    val securityContextDigest: String,
    val effectiveNotBeforeMs: ULong,
    val expiresAtMs: ULong,
) {
    init {
        listOf(
            grantEvidenceDigest,
            pairAuthorityDigest,
            pairBindingDigest,
            clientIdentityFingerprint,
            runtimeIdentityFingerprint,
            securityContextDigest,
        ).forEach(ProductionC1InternalBridge::validateDigest)
        grantRequire(
            pairEpoch > 0uL && generation > 0uL &&
                clientIdentityFingerprint != runtimeIdentityFingerprint &&
                grantIsLowerHex(sessionId, 32) && grantIsLowerHex(attemptId, 64) &&
                initiatorRole != connectorTargetRole && destinationPolicyId.isNotEmpty() &&
                destinationPolicyVersion > 0uL && effectiveNotBeforeMs < expiresAtMs,
            ProductionC1CandidateCapabilityError.INVALID_VALUE,
        )
        grantRequire(
            canonicalBytes().size <=
                ProductionC1CandidateCapabilityContract.MAXIMUM_GRANT_AUTHORIZATION_BYTES,
            ProductionC1CandidateCapabilityError.INVALID_VALUE,
        )
    }

    fun canonicalBytes(): ByteArray = ProductionC1InternalBridge.encode(
        ProductionC1CandidateCapabilityContract.GRANT_AUTHORIZATION_OBJECT_TYPE,
        listOf(
            ProductionC1InternalBridge.ascii(ProductionC1Contract.SUITE),
            ProductionC1InternalBridge.be(ProductionC1CandidateCapabilityContract.REVISION),
            ProductionC1InternalBridge.ascii(grantEvidenceDigest),
            ProductionC1InternalBridge.ascii(pairAuthorityDigest),
            ProductionC1InternalBridge.ascii(pairBindingDigest),
            ProductionC1InternalBridge.be(pairEpoch),
            ProductionC1InternalBridge.be(generation),
            ProductionC1InternalBridge.ascii(clientIdentityFingerprint),
            ProductionC1InternalBridge.ascii(runtimeIdentityFingerprint),
            ProductionC1InternalBridge.ascii(sessionId),
            ProductionC1InternalBridge.ascii(attemptId),
            ProductionC1InternalBridge.ascii(initiatorRole.wireValue),
            ProductionC1InternalBridge.ascii(connectorTargetRole.wireValue),
            ProductionC1InternalBridge.ascii(destinationPolicyId),
            ProductionC1InternalBridge.be(destinationPolicyVersion),
            ProductionC1InternalBridge.ascii(securityContextDigest),
            ProductionC1InternalBridge.be(effectiveNotBeforeMs),
            ProductionC1InternalBridge.be(expiresAtMs),
        ),
    )

    fun digestHex(): String = ProductionC1InternalBridge.digestHex(canonicalBytes())

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is ProductionC1P2PGrantAuthorization && canonicalBytes().contentEquals(other.canonicalBytes()))

    override fun hashCode(): Int = canonicalBytes().contentHashCode()

    companion object {
        fun decode(data: ByteArray): ProductionC1P2PGrantAuthorization {
            val fields = ProductionC1InternalBridge.decode(
                data,
                ProductionC1CandidateCapabilityContract.GRANT_AUTHORIZATION_OBJECT_TYPE,
                18,
                ProductionC1CandidateCapabilityContract.MAXIMUM_GRANT_AUTHORIZATION_BYTES,
            )
            grantRequire(
                ProductionC1InternalBridge.text(fields[0]) == ProductionC1Contract.SUITE &&
                    ProductionC1InternalBridge.uint64(fields[1]) ==
                    ProductionC1CandidateCapabilityContract.REVISION,
                ProductionC1CandidateCapabilityError.INVALID_VALUE,
            )
            val result = ProductionC1P2PGrantAuthorization(
                ProductionC1InternalBridge.text(fields[2]),
                ProductionC1InternalBridge.text(fields[3]),
                ProductionC1InternalBridge.text(fields[4]),
                ProductionC1InternalBridge.uint64(fields[5]),
                ProductionC1InternalBridge.uint64(fields[6]),
                ProductionC1InternalBridge.text(fields[7]),
                ProductionC1InternalBridge.text(fields[8]),
                ProductionC1InternalBridge.text(fields[9]),
                ProductionC1InternalBridge.text(fields[10]),
                grantRole(fields[11]),
                grantRole(fields[12]),
                ProductionC1InternalBridge.text(fields[13]),
                ProductionC1InternalBridge.uint64(fields[14]),
                ProductionC1InternalBridge.text(fields[15]),
                ProductionC1InternalBridge.uint64(fields[16]),
                ProductionC1InternalBridge.uint64(fields[17]),
            )
            grantRequire(
                result.canonicalBytes().contentEquals(data),
                ProductionC1CandidateCapabilityError.MALFORMED_CANONICAL,
            )
            return result
        }

        internal fun fromEvidence(evidence: ProductionC1P2PGrantEvidence): ProductionC1P2PGrantAuthorization =
            ProductionC1P2PGrantAuthorization(
                evidence.digestHex(),
                evidence.pairAuthorityDigest,
                evidence.pairBindingDigest,
                evidence.pairEpoch,
                evidence.generation,
                evidence.clientIdentityFingerprint,
                evidence.runtimeIdentityFingerprint,
                evidence.sessionId,
                evidence.attemptId,
                evidence.initiatorRole,
                evidence.connectorTargetRole,
                evidence.destinationPolicyId,
                evidence.destinationPolicyVersion,
                evidence.securityContextDigest,
                evidence.effectiveNotBeforeMs,
                evidence.expiresAtMs,
            )
    }
}

class VerifiedProductionC1P2PGrantAuthorization private constructor(
    val authorization: ProductionC1P2PGrantAuthorization,
) {
    val digestHex: String = authorization.digestHex()

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is VerifiedProductionC1P2PGrantAuthorization && authorization == other.authorization)

    override fun hashCode(): Int = authorization.hashCode()

    companion object {
        internal fun verify(
            authorization: ProductionC1P2PGrantAuthorization,
            evidence: ProductionC1P2PGrantEvidence,
            plan: VerifiedProductionC1CandidateP2PPlan,
            localRole: P2pNatRole,
        ): VerifiedProductionC1P2PGrantAuthorization {
            val expected = ProductionC1P2PGrantAuthorization.fromEvidence(evidence)
            grantRequire(
                authorization == expected &&
                    (localRole == authorization.initiatorRole ||
                        localRole == authorization.connectorTargetRole) &&
                    authorization.connectorTargetRole == P2pNatRole.RUNTIME &&
                    authorization.destinationPolicyId == ProductionC1P2PDestinationPolicy.POLICY_ID &&
                    authorization.destinationPolicyVersion ==
                    ProductionC1P2PDestinationPolicy.POLICY_VERSION &&
                    authorization.securityContextDigest == plan.securityContext.digestHex() &&
                    authorization.effectiveNotBeforeMs == evidence.effectiveNotBeforeMs &&
                    authorization.expiresAtMs == evidence.expiresAtMs &&
                    authorization.effectiveNotBeforeMs >= plan.effectiveNotBeforeMs &&
                    authorization.expiresAtMs <= plan.expiresAtMs,
                ProductionC1CandidateCapabilityError.ROUTE_MISMATCH,
            )
            return VerifiedProductionC1P2PGrantAuthorization(authorization)
        }
    }
}

class VerifiedProductionC1P2PGrantEvidence private constructor(
    val evidence: ProductionC1P2PGrantEvidence,
    val routeAuthorizations: ProductionC1BilateralRouteAuthorizations,
    operationReceipts: List<VerifiedProductionC1CandidateOperationReceipt>,
    val grantAuthorization: VerifiedProductionC1P2PGrantAuthorization,
    internal val plan: VerifiedProductionC1CandidateP2PPlan,
) {
    private val receipts = operationReceipts.toList()
    val operationReceipts: List<VerifiedProductionC1CandidateOperationReceipt>
        get() = receipts.toList()

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is VerifiedProductionC1P2PGrantEvidence &&
                evidence == other.evidence &&
                routeAuthorizations == other.routeAuthorizations &&
                receipts == other.receipts &&
                grantAuthorization == other.grantAuthorization &&
                plan == other.plan)

    override fun hashCode(): Int {
        var result = evidence.hashCode()
        result = 31 * result + routeAuthorizations.hashCode()
        result = 31 * result + receipts.hashCode()
        result = 31 * result + grantAuthorization.hashCode()
        return 31 * result + plan.hashCode()
    }

    companion object {
        internal fun derive(
            plan: VerifiedProductionC1CandidateP2PPlan,
            routeAuthorizations: ProductionC1BilateralRouteAuthorizations,
            operationReceipts: List<VerifiedProductionC1CandidateOperationReceipt>,
            initiatorRole: P2pNatRole,
            authority: ProductionPairAuthorityState,
            nowMs: ULong,
        ): VerifiedProductionC1P2PGrantEvidence {
            VerifiedProductionC1CandidateP2PPlan.refresh(plan, authority, nowMs)
            grantRequire(
                operationReceipts.size == 4 &&
                    initiatorRole == ProductionC1P2PDestinationPolicy.INITIATOR_ROLE,
                ProductionC1CandidateCapabilityError.QUOTA_EXCEEDED,
            )
            val bilateral = plan.bilateral
            val capabilities = bilateral.all
            val authorizations = routeAuthorizations.operationOrder
            val capabilityDigests = capabilities.map { it.capabilityDigest }
            val authorizationDigests = authorizations.map(::routeAuthorizationDigest)
            val rawReceipts = operationReceipts.map { it.receipt }
            val receiptDigests = rawReceipts.map { it.digestHex() }
            val firstReceipt = rawReceipts.first()
            grantRequire(
                receiptDigests.toSet().size == 4 &&
                    rawReceipts.map { it.proofId }.toSet().size == 4 &&
                    rawReceipts.map { it.capabilityDigest }.toSet().size == 4 &&
                    rawReceipts.map { it.operationAuthorizationDigest }.toSet().size == 4 &&
                    rawReceipts.map { it.singleUseNonce }.toSet().size == 4 &&
                    rawReceipts.all { it.ledgerId == firstReceipt.ledgerId },
                ProductionC1CandidateCapabilityError.REQUEST_CONFLICT,
            )
            rawReceipts.indices.forEach { index ->
                val receipt = rawReceipts[index]
                val refreshed = ProductionC1CandidateOperationReceiptVerifier.verify(
                    receipt,
                    capabilities[index],
                    authorizations[index],
                    authority,
                    capabilities[index].verifiedKeyset,
                    nowMs,
                )
                grantRequire(
                    refreshed == operationReceipts[index] &&
                        receipt.capabilityDigest == capabilityDigests[index] &&
                        receipt.operationAuthorizationDigest == authorizationDigests[index],
                    ProductionC1CandidateCapabilityError.REQUEST_CONFLICT,
                )
                if (index > 0) {
                    val previous = rawReceipts[index - 1]
                    grantRequire(
                        receipt.previousLedgerRevision == previous.committedLedgerRevision &&
                            receipt.previousLedgerStateCoreDigest ==
                            previous.committedLedgerStateCoreDigest &&
                            receipt.committedAtMs >= previous.committedAtMs,
                        ProductionC1CandidateCapabilityError.REVISION_MISMATCH,
                    )
                }
            }
            val effectiveNotBefore = maxOf(
                plan.effectiveNotBeforeMs,
                rawReceipts.maxOf { it.notBeforeMs },
            )
            val expiresAt = minOf(plan.expiresAtMs, rawReceipts.minOf { it.expiresAtMs })
            grantRequire(
                nowMs >= effectiveNotBefore && nowMs < expiresAt,
                ProductionC1CandidateCapabilityError.ROUTE_MISMATCH,
            )
            requireFinalRoute(routeAuthorizations.finalP2PDirect, plan, authority)
            val finalDigest = routeAuthorizationDigest(routeAuthorizations.finalP2PDirect)
            val first = bilateral.clientPublish.capability
            val evidence = ProductionC1P2PGrantEvidence.derived(
                first.serviceIdDigest,
                first.keysetVersion,
                first.pairAuthorityDigest,
                first.pairBindingDigest,
                first.pairEpoch,
                first.generation,
                first.sessionId,
                first.attemptId,
                first.clientIdentityFingerprint,
                first.runtimeIdentityFingerprint,
                bilateral.clientPublish.capability.candidateBatchDigest,
                bilateral.clientPublish.capability.candidateBatchByteCount,
                bilateral.runtimePublish.capability.candidateBatchDigest,
                bilateral.runtimePublish.capability.candidateBatchByteCount,
                capabilityDigests,
                authorizationDigests,
                bilateral.bilateralPublishDigest,
                bilateral.bilateralFetchDigest,
                plan.pathValidationReceipt.candidatePairDigest,
                plan.pathValidationReceiptDigest,
                finalDigest,
                plan.claims.digestHex(),
                plan.capability.digestHex(),
                receiptDigests,
                initiatorRole,
                ProductionC1P2PDestinationPolicy.CONNECTOR_TARGET_ROLE,
                ProductionC1P2PDestinationPolicy.POLICY_ID,
                ProductionC1P2PDestinationPolicy.POLICY_VERSION,
                plan.securityContext.digestHex(),
                effectiveNotBefore,
                expiresAt,
            )
            val grantAuthorization = VerifiedProductionC1P2PGrantAuthorization.verify(
                ProductionC1P2PGrantAuthorization.fromEvidence(evidence),
                evidence,
                plan,
                initiatorRole,
            )
            return VerifiedProductionC1P2PGrantEvidence(
                evidence,
                routeAuthorizations,
                operationReceipts,
                grantAuthorization,
                plan,
            )
        }

        internal fun verify(
            evidence: ProductionC1P2PGrantEvidence,
            plan: VerifiedProductionC1CandidateP2PPlan,
            routeAuthorizations: ProductionC1BilateralRouteAuthorizations,
            operationReceipts: List<VerifiedProductionC1CandidateOperationReceipt>,
            localRole: P2pNatRole,
            authority: ProductionPairAuthorityState,
            nowMs: ULong,
        ): VerifiedProductionC1P2PGrantEvidence {
            val derived = derive(
                plan,
                routeAuthorizations,
                operationReceipts,
                evidence.initiatorRole,
                authority,
                nowMs,
            )
            grantRequire(
                derived.evidence == evidence &&
                    (localRole == evidence.initiatorRole ||
                        localRole == evidence.connectorTargetRole),
                ProductionC1CandidateCapabilityError.ROUTE_MISMATCH,
            )
            return derived
        }
    }
}

fun ProductionC1CandidateVerifier.selectedCandidatePairDigest(
    clientCandidate: P2pCandidate,
    runtimeCandidate: P2pCandidate,
): String {
    val claims = ByteArrayOutputStream().apply {
        listOf(
            "client" to clientCandidate,
            "runtime" to runtimeCandidate,
        ).forEach { (role, candidate) ->
            val roleBytes = ProductionC1InternalBridge.ascii(role)
            val candidateBytes = P2pNatCanonicalCodec.encodeCandidate(candidate)
            write(ProductionC1InternalBridge.be(roleBytes.size.toUInt()))
            write(roleBytes)
            write(ProductionC1InternalBridge.be(candidateBytes.size.toUInt()))
            write(candidateBytes)
        }
    }.toByteArray()
    return ProductionC1InternalBridge.digestHex(
        ProductionC1InternalBridge.transcript(
            "AetherLink G1a-C selected direct candidate-pair v1",
            claims,
        ),
    )
}

fun ProductionC1CandidateVerifier.verifyP2PDirectPlan(
    claims: ProductionC1RoutePlanClaims,
    capability: ProductionC1RouteCapability,
    securityContext: ProductionC1PreauthorizationSessionContext,
    bilateral: VerifiedProductionC1BilateralCandidateCapabilities,
    selectedClientCandidate: P2pCandidate,
    selectedRuntimeCandidate: P2pCandidate,
    pathValidationReceiptCanonicalBytes: ByteArray,
    authority: ProductionPairAuthorityState,
    verifiedKeyset: VerifiedProductionC1ServiceKeyset,
    destinationPolicy: ProductionC1P2PDestinationPolicy = ProductionC1P2PDestinationPolicy.PUBLIC_ONLY,
    nowMs: ULong,
): VerifiedProductionC1CandidateP2PPlan = VerifiedProductionC1CandidateP2PPlan.verify(
    claims,
    capability,
    securityContext,
    bilateral,
    selectedClientCandidate,
    selectedRuntimeCandidate,
    pathValidationReceiptCanonicalBytes,
    authority,
    verifiedKeyset,
    destinationPolicy,
    nowMs,
)

fun ProductionC1CandidateVerifier.makeBilateralRouteAuthorizations(
    plan: VerifiedProductionC1CandidateP2PPlan,
    authority: ProductionPairAuthorityState,
    nowMs: ULong,
): ProductionC1BilateralRouteAuthorizations {
    VerifiedProductionC1CandidateP2PPlan.refresh(plan, authority, nowMs)
    val bilateral = plan.bilateral
    val clientPublish = publishAuthorization(bilateral.clientPublish)
    val runtimeFetchClient = fetchAuthorization(bilateral.runtimeFetchClient)
    val runtimePublish = publishAuthorization(bilateral.runtimePublish)
    val clientFetchRuntime = fetchAuthorization(bilateral.clientFetchRuntime)
    val final = P2pDirectRouteAuthorization(
        authority.pairBindingDigest,
        authority.pairEpoch,
        authority.generation,
        plan.pathValidationReceipt.candidatePairDigest,
        plan.pathValidationReceiptDigest,
        bilateral.bilateralPublishDigest,
        bilateral.bilateralFetchDigest,
    )
    ProductionSecureSessionCodec.encode(final)
    return ProductionC1BilateralRouteAuthorizations(
        clientPublish,
        runtimeFetchClient,
        runtimePublish,
        clientFetchRuntime,
        final,
    )
}

internal fun ProductionC1CandidateVerifier.deriveGrantEvidence(
    plan: VerifiedProductionC1CandidateP2PPlan,
    routeAuthorizations: ProductionC1BilateralRouteAuthorizations,
    operationReceipts: List<VerifiedProductionC1CandidateOperationReceipt>,
    initiatorRole: P2pNatRole,
    authority: ProductionPairAuthorityState,
    nowMs: ULong,
): VerifiedProductionC1P2PGrantEvidence = VerifiedProductionC1P2PGrantEvidence.derive(
    plan,
    routeAuthorizations,
    operationReceipts,
    initiatorRole,
    authority,
    nowMs,
)

fun ProductionC1CandidateVerifier.verifyGrantEvidence(
    evidence: ProductionC1P2PGrantEvidence,
    plan: VerifiedProductionC1CandidateP2PPlan,
    routeAuthorizations: ProductionC1BilateralRouteAuthorizations,
    operationReceipts: List<VerifiedProductionC1CandidateOperationReceipt>,
    localRole: P2pNatRole,
    authority: ProductionPairAuthorityState,
    nowMs: ULong,
): VerifiedProductionC1P2PGrantEvidence = VerifiedProductionC1P2PGrantEvidence.verify(
    evidence,
    plan,
    routeAuthorizations,
    operationReceipts,
    localRole,
    authority,
    nowMs,
)

internal fun ProductionC1CandidateVerifier.makeGrantAuthorization(
    evidence: ProductionC1P2PGrantEvidence,
): ProductionC1P2PGrantAuthorization = ProductionC1P2PGrantAuthorization.fromEvidence(evidence)

internal fun ProductionC1CandidateVerifier.verifyGrantAuthorization(
    authorization: ProductionC1P2PGrantAuthorization,
    evidence: ProductionC1P2PGrantEvidence,
    plan: VerifiedProductionC1CandidateP2PPlan,
    localRole: P2pNatRole,
): VerifiedProductionC1P2PGrantAuthorization = VerifiedProductionC1P2PGrantAuthorization.verify(
    authorization,
    evidence,
    plan,
    localRole,
)

private fun validateBilateralUse(
    bilateral: VerifiedProductionC1BilateralCandidateCapabilities,
    authority: ProductionPairAuthorityState,
    nowMs: ULong,
) {
    val refreshed = try {
        ProductionC1CandidateVerifier.verifyBilateral(
            bilateral.clientPublish,
            bilateral.runtimeFetchClient,
            bilateral.runtimePublish,
            bilateral.clientFetchRuntime,
            authority,
            nowMs,
        )
    } catch (_: ProductionC1CandidateCapabilityException) {
        grantFail(ProductionC1CandidateCapabilityError.AUTHORITY_MISMATCH)
    }
    grantRequire(
        refreshed == bilateral,
        ProductionC1CandidateCapabilityError.AUTHORITY_MISMATCH,
    )
}

private fun validatePlanUse(
    plan: VerifiedProductionC1CandidateP2PPlan,
    authority: ProductionPairAuthorityState,
    nowMs: ULong,
) {
    validateBilateralUse(plan.bilateral, authority, nowMs)
    validateDestination(
        plan.claims.connector.addressBytes,
        plan.claims.connector.port.toInt(),
        ProductionC1P2PDestinationPolicy.PUBLIC_ONLY,
    )
    val selectedPairDigest = validateSelectedCandidates(
        plan.bilateral,
        plan.selectedClientCandidate,
        plan.selectedRuntimeCandidate,
        plan.claims.connector,
    )
    grantRequire(
        nowMs >= plan.effectiveNotBeforeMs && nowMs < plan.expiresAtMs &&
            plan.pathValidationReceipt.transportContext == TransportContext.DIRECT &&
            plan.pathValidationReceipt.sessionId == plan.securityContext.sessionId &&
            plan.pathValidationReceipt.generation == authority.generation &&
            plan.pathValidationReceipt.candidatePairDigest == selectedPairDigest &&
            plan.pathValidationReceiptDigest == plan.claims.selectedPathReceiptDigest &&
            P2pNatContract.isPathValidationFresh(
                plan.pathValidationReceipt.validatedAtMillis,
                plan.pathValidationReceipt.expiresAtMillis,
                nowMs,
            ),
        ProductionC1CandidateCapabilityError.ROUTE_MISMATCH,
    )
    VerifiedProductionC1CandidateP2PPlan.refreshBaseAuthorization(plan, nowMs)
}

private fun validateSelectedCandidates(
    bilateral: VerifiedProductionC1BilateralCandidateCapabilities,
    client: P2pCandidate,
    runtime: P2pCandidate,
    connector: ProductionC1RouteConnectorMaterial,
): String {
    val directKinds = setOf(
        CandidateKind.HOST,
        CandidateKind.SERVER_REFLEXIVE,
        CandidateKind.PEER_REFLEXIVE,
    )
    grantRequire(
        client.kind in directKinds && runtime.kind in directKinds &&
            client.family == runtime.family && client.address.size == runtime.address.size &&
            bilateral.clientPublish.candidateBatch.candidates.contains(client) &&
            bilateral.runtimePublish.candidateBatch.candidates.contains(runtime) &&
            connector.addressBytes.contentEquals(runtime.address) &&
            connector.port.toInt() == runtime.port,
        ProductionC1CandidateCapabilityError.ROUTE_MISMATCH,
    )
    validateDestination(client.address, client.port, ProductionC1P2PDestinationPolicy.PUBLIC_ONLY)
    validateDestination(runtime.address, runtime.port, ProductionC1P2PDestinationPolicy.PUBLIC_ONLY)
    return ProductionC1CandidateVerifier.selectedCandidatePairDigest(client, runtime)
}

private fun validateDestination(
    address: ByteArray,
    port: Int,
    policy: ProductionC1P2PDestinationPolicy,
) {
    grantRequire(
        policy == ProductionC1P2PDestinationPolicy.PUBLIC_ONLY &&
            ProductionC1PublicOnlyV1Policy.allows(address, port),
        ProductionC1CandidateCapabilityError.ROUTE_MISMATCH,
    )
}

private fun publishAuthorization(
    verified: VerifiedProductionC1CandidateCapability,
): ProductionRouteAuthorization {
    val value = verified.capability
    return P2pPublishRouteAuthorization(
        value.pairBindingDigest,
        value.pairEpoch,
        value.generation,
        value.candidateBatchDigest,
        verified.capabilityDigest,
    )
}

private fun fetchAuthorization(
    verified: VerifiedProductionC1CandidateCapability,
): ProductionRouteAuthorization {
    val value = verified.capability
    return P2pFetchRouteAuthorization(
        value.pairBindingDigest,
        value.pairEpoch,
        value.generation,
        value.candidateBatchDigest,
        verified.capabilityDigest,
    )
}

private fun requireFinalRoute(
    route: ProductionRouteAuthorization,
    plan: VerifiedProductionC1CandidateP2PPlan,
    authority: ProductionPairAuthorityState,
) {
    grantRequire(
        route is P2pDirectRouteAuthorization &&
            route.pairBindingDigest == authority.pairBindingDigest &&
            route.pairEpoch == authority.pairEpoch &&
            route.generation == authority.generation &&
            route.candidatePairDigest == plan.pathValidationReceipt.candidatePairDigest &&
            route.pathValidationReceiptDigest == plan.pathValidationReceiptDigest &&
            route.publishCapabilityDigest == plan.bilateral.bilateralPublishDigest &&
            route.fetchCapabilityDigest == plan.bilateral.bilateralFetchDigest,
        ProductionC1CandidateCapabilityError.ROUTE_MISMATCH,
    )
}

private fun routeAuthorizationDigest(value: ProductionRouteAuthorization): String =
    ProductionC1InternalBridge.digestHex(ProductionSecureSessionCodec.encode(value))

private fun grantRole(data: ByteArray): P2pNatRole =
    P2pNatRole.entries.singleOrNull { it.wireValue == ProductionC1InternalBridge.text(data) }
        ?: grantFail(ProductionC1CandidateCapabilityError.INVALID_VALUE)

private fun grantIsLowerHex(value: String, count: Int): Boolean =
    value.length == count && value.all { it in '0'..'9' || it in 'a'..'f' }

private fun ByteArray.toLowerHex(): String = joinToString("") { byte ->
    (byte.toInt() and 0xff).toString(16).padStart(2, '0')
}

private fun grantRequire(
    condition: Boolean,
    error: ProductionC1CandidateCapabilityError,
) {
    if (!condition) throw ProductionC1CandidateCapabilityException(error)
}

private fun grantFail(error: ProductionC1CandidateCapabilityError): Nothing =
    throw ProductionC1CandidateCapabilityException(error)
