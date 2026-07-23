package com.localagentbridge.android.core.protocol.p2pnat

import java.io.ByteArrayOutputStream
import java.security.MessageDigest
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/**
 * Verified client-side connector material for the candidate P2P route.
 *
 * Construction is module-only and additionally requires the private verifier mint so an
 * internal caller cannot convert unverified route material into a verified wrapper.
 */
class VerifiedProductionC1CandidateP2PConnectorInput internal constructor(
    val connector: ProductionC1RouteConnectorMaterial,
    val commitmentDigest: String,
    internal val routeHandle: String,
    internal val nonce: String,
    secret: ByteArray,
    provenance: Any,
) {
    private val secretBytes = secret.copyOf()
    internal val secret: ByteArray get() = secretBytes.copyOf()

    init {
        endpointRequire(
            CandidateEndpointAdmissionProvenance.ownsVerifiedMint(provenance),
            ProductionC1CandidateCapabilityError.ROUTE_MISMATCH,
        )
        endpointValidateDigest(commitmentDigest)
    }

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is VerifiedProductionC1CandidateP2PConnectorInput &&
                connector == other.connector &&
                commitmentDigest == other.commitmentDigest &&
                routeHandle == other.routeHandle &&
                nonce == other.nonce &&
                secretBytes.contentEquals(other.secretBytes))

    override fun hashCode(): Int {
        var result = connector.hashCode()
        result = 31 * result + commitmentDigest.hashCode()
        result = 31 * result + routeHandle.hashCode()
        result = 31 * result + nonce.hashCode()
        return 31 * result + secretBytes.contentHashCode()
    }
}

/** Verifier-minted, secret-free input to the production P2P key schedule. */
class VerifiedProductionC1CandidateP2PKeyScheduleBinding internal constructor(
    val transcript: ProductionSecureSessionTranscript,
    val grantAuthorization: VerifiedProductionC1P2PGrantAuthorization,
    val securityContext: ProductionC1PreauthorizationSessionContext,
    val localRole: P2pNatRole,
    provenance: Any,
) {
    /**
     * Secret-free digest of the exact object-7 + object-26 claims fed to the production
     * secure-session KDF. This is deliberately not an endpoint admission token binding digest.
     */
    val object7Object26KdfBindingDigestHex: String
        get() = ProductionSecureSessionCrypto.object7Object26KdfBindingDigestHex(this)

    init {
        endpointRequire(
            CandidateEndpointAdmissionProvenance.ownsVerifiedMint(provenance),
            ProductionC1CandidateCapabilityError.ROUTE_MISMATCH,
        )
    }

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is VerifiedProductionC1CandidateP2PKeyScheduleBinding &&
                transcript == other.transcript &&
                grantAuthorization == other.grantAuthorization &&
                securityContext == other.securityContext &&
                localRole == other.localRole)

    override fun hashCode(): Int {
        var result = transcript.hashCode()
        result = 31 * result + grantAuthorization.hashCode()
        result = 31 * result + securityContext.hashCode()
        return 31 * result + localRole.hashCode()
    }
}

/** Exact object-26-authorized secure-session transcript binding. */
class VerifiedProductionC1CandidateP2PTranscriptBinding internal constructor(
    val transcript: ProductionSecureSessionTranscript,
    val grant: VerifiedProductionC1P2PGrantEvidence,
    val connectorInput: VerifiedProductionC1CandidateP2PConnectorInput,
    val securityContext: ProductionC1PreauthorizationSessionContext,
    val keyScheduleBinding: VerifiedProductionC1CandidateP2PKeyScheduleBinding,
    keyConfirmationKey: ByteArray,
    presentedPeerKeyConfirmation: ByteArray,
    provenance: Any,
) {
    private val keyConfirmationKeyBytes = keyConfirmationKey.copyOf()
    private val presentedPeerKeyConfirmationBytes = presentedPeerKeyConfirmation.copyOf()
    internal val keyConfirmationKey: ByteArray get() = keyConfirmationKeyBytes.copyOf()
    internal val presentedPeerKeyConfirmation: ByteArray
        get() = presentedPeerKeyConfirmationBytes.copyOf()

    init {
        endpointRequire(
            CandidateEndpointAdmissionProvenance.ownsVerifiedMint(provenance),
            ProductionC1CandidateCapabilityError.ROUTE_MISMATCH,
        )
    }

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is VerifiedProductionC1CandidateP2PTranscriptBinding &&
                transcript == other.transcript &&
                grant == other.grant &&
                connectorInput == other.connectorInput &&
                securityContext == other.securityContext &&
                keyScheduleBinding == other.keyScheduleBinding &&
                keyConfirmationKeyBytes.contentEquals(other.keyConfirmationKeyBytes) &&
                presentedPeerKeyConfirmationBytes.contentEquals(other.presentedPeerKeyConfirmationBytes))

    override fun hashCode(): Int {
        var result = transcript.hashCode()
        result = 31 * result + grant.hashCode()
        result = 31 * result + connectorInput.hashCode()
        result = 31 * result + securityContext.hashCode()
        result = 31 * result + keyScheduleBinding.hashCode()
        result = 31 * result + keyConfirmationKeyBytes.contentHashCode()
        return 31 * result + presentedPeerKeyConfirmationBytes.contentHashCode()
    }
}

/**
 * Secret-free transport descriptor derived only from one verifier-minted transcript binding.
 * It commits to the hidden connector input without exposing its route handle, nonce, or secret.
 */
class VerifiedProductionC1CandidateP2PTransportDescriptor private constructor(
    val sessionId: String,
    val generation: ULong,
    val connectorInputCommitmentDigest: String,
    val connectorMaterialDigest: String,
    val securityContextDigest: String,
    val routePlanDigest: String,
    val routeGrantDigest: String,
    val effectiveNotBeforeMs: ULong,
    val expiresAtMs: ULong,
    val descriptorDigest: String,
) {
    override fun equals(other: Any?): Boolean =
        this === other ||
            other is VerifiedProductionC1CandidateP2PTransportDescriptor &&
            sessionId == other.sessionId &&
            generation == other.generation &&
            connectorInputCommitmentDigest == other.connectorInputCommitmentDigest &&
            connectorMaterialDigest == other.connectorMaterialDigest &&
            securityContextDigest == other.securityContextDigest &&
            routePlanDigest == other.routePlanDigest &&
            routeGrantDigest == other.routeGrantDigest &&
            effectiveNotBeforeMs == other.effectiveNotBeforeMs &&
            expiresAtMs == other.expiresAtMs &&
            descriptorDigest == other.descriptorDigest

    override fun hashCode(): Int {
        var result = sessionId.hashCode()
        result = 31 * result + generation.hashCode()
        result = 31 * result + connectorInputCommitmentDigest.hashCode()
        result = 31 * result + connectorMaterialDigest.hashCode()
        result = 31 * result + securityContextDigest.hashCode()
        result = 31 * result + routePlanDigest.hashCode()
        result = 31 * result + routeGrantDigest.hashCode()
        result = 31 * result + effectiveNotBeforeMs.hashCode()
        result = 31 * result + expiresAtMs.hashCode()
        return 31 * result + descriptorDigest.hashCode()
    }

    companion object {
        fun fromVerifiedBinding(
            binding: VerifiedProductionC1CandidateP2PTranscriptBinding,
        ): VerifiedProductionC1CandidateP2PTransportDescriptor {
            val transcript = binding.transcript
            val evidence = binding.grant.evidence
            val authorization = binding.grant.grantAuthorization.authorization
            val securityContextDigest = binding.securityContext.digestHex()
            val connectorMaterialDigest = ProductionC1InternalBridge.digestHex(
                binding.connectorInput.connector.canonicalBytes(),
            )
            endpointRequire(
                transcript.routeAuthorizationKind == ProductionRouteAuthorizationKind.P2P_DIRECT &&
                    binding.securityContext == ProductionC1PreauthorizationSessionContext(transcript) &&
                    evidence.sessionId == transcript.sessionId &&
                    evidence.generation == transcript.generation &&
                    evidence.securityContextDigest == securityContextDigest &&
                    authorization.securityContextDigest == securityContextDigest &&
                    authorization.effectiveNotBeforeMs == evidence.effectiveNotBeforeMs &&
                    authorization.expiresAtMs == evidence.expiresAtMs &&
                    binding.connectorInput.connector.kind == ProductionC1RouteKind.P2P_DIRECT &&
                    binding.keyScheduleBinding.transcript == transcript,
                ProductionC1CandidateCapabilityError.ROUTE_MISMATCH,
            )
            val connectorCommitment = binding.connectorInput.commitmentDigest
            val routeGrantDigest = evidence.digestHex()
            val claims = ByteArrayOutputStream().apply {
                write(ProductionC1InternalBridge.rawDigest(connectorCommitment))
                write(ProductionC1InternalBridge.rawDigest(connectorMaterialDigest))
                write(ProductionC1InternalBridge.rawDigest(securityContextDigest))
                write(ProductionC1InternalBridge.rawDigest(evidence.c1RoutePlanClaimsDigest))
                write(ProductionC1InternalBridge.rawDigest(routeGrantDigest))
                write(ProductionC1InternalBridge.ascii(transcript.sessionId))
                write(ProductionC1InternalBridge.be(transcript.generation))
                write(ProductionC1InternalBridge.be(evidence.effectiveNotBeforeMs))
                write(ProductionC1InternalBridge.be(evidence.expiresAtMs))
            }.toByteArray()
            val descriptorDigest = ProductionC1InternalBridge.digestHex(
                ProductionC1InternalBridge.transcript(
                    "AetherLink G1a-D verified P2P transport descriptor v1",
                    claims,
                ),
            )
            claims.fill(0)
            return VerifiedProductionC1CandidateP2PTransportDescriptor(
                sessionId = transcript.sessionId,
                generation = transcript.generation,
                connectorInputCommitmentDigest = connectorCommitment,
                connectorMaterialDigest = connectorMaterialDigest,
                securityContextDigest = securityContextDigest,
                routePlanDigest = evidence.c1RoutePlanClaimsDigest,
                routeGrantDigest = routeGrantDigest,
                effectiveNotBeforeMs = evidence.effectiveNotBeforeMs,
                expiresAtMs = evidence.expiresAtMs,
                descriptorDigest = descriptorDigest,
            )
        }
    }
}

class VerifiedProductionC1CandidateP2PInboundMaterial internal constructor(
    val observedPeerCandidate: P2pCandidate,
    val peerKeyConfirmationDigest: String,
    val transcriptDigest: String,
    val routeGrantDigest: String,
    val grantAuthorizationDigest: String,
    val sessionId: String,
    provenance: Any,
) {
    init {
        endpointRequire(
            CandidateEndpointAdmissionProvenance.ownsVerifiedMint(provenance),
            ProductionC1CandidateCapabilityError.ROUTE_MISMATCH,
        )
        listOf(
            peerKeyConfirmationDigest,
            transcriptDigest,
            routeGrantDigest,
            grantAuthorizationDigest,
        ).forEach(::endpointValidateDigest)
        endpointRequire(
            endpointIsLowerHex(sessionId, 32),
            ProductionC1CandidateCapabilityError.INVALID_VALUE,
        )
    }

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is VerifiedProductionC1CandidateP2PInboundMaterial &&
                observedPeerCandidate == other.observedPeerCandidate &&
                peerKeyConfirmationDigest == other.peerKeyConfirmationDigest &&
                transcriptDigest == other.transcriptDigest &&
                routeGrantDigest == other.routeGrantDigest &&
                grantAuthorizationDigest == other.grantAuthorizationDigest &&
                sessionId == other.sessionId)

    override fun hashCode(): Int {
        var result = observedPeerCandidate.hashCode()
        result = 31 * result + peerKeyConfirmationDigest.hashCode()
        result = 31 * result + transcriptDigest.hashCode()
        result = 31 * result + routeGrantDigest.hashCode()
        result = 31 * result + grantAuthorizationDigest.hashCode()
        return 31 * result + sessionId.hashCode()
    }
}

class VerifiedProductionC1CandidateP2PInboundTranscriptBinding internal constructor(
    val transcript: ProductionSecureSessionTranscript,
    val grant: VerifiedProductionC1P2PGrantEvidence,
    val inboundMaterial: VerifiedProductionC1CandidateP2PInboundMaterial,
    val securityContext: ProductionC1PreauthorizationSessionContext,
    provenance: Any,
) {
    init {
        endpointRequire(
            CandidateEndpointAdmissionProvenance.ownsVerifiedMint(provenance),
            ProductionC1CandidateCapabilityError.ROUTE_MISMATCH,
        )
    }

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is VerifiedProductionC1CandidateP2PInboundTranscriptBinding &&
                transcript == other.transcript &&
                grant == other.grant &&
                inboundMaterial == other.inboundMaterial &&
                securityContext == other.securityContext)

    override fun hashCode(): Int {
        var result = transcript.hashCode()
        result = 31 * result + grant.hashCode()
        result = 31 * result + inboundMaterial.hashCode()
        return 31 * result + securityContext.hashCode()
    }
}

fun ProductionC1CandidateVerifier.verifyP2PConnectorInput(
    verifiedGrant: VerifiedProductionC1P2PGrantEvidence,
    localRole: P2pNatRole,
    routeHandle: String,
    nonce: String,
    secret: ByteArray,
    authority: ProductionPairAuthorityState,
    nowMs: ULong,
): VerifiedProductionC1CandidateP2PConnectorInput {
    val refreshed = verifyGrantEvidence(
        verifiedGrant.evidence,
        verifiedGrant.plan,
        verifiedGrant.routeAuthorizations,
        verifiedGrant.operationReceipts,
        localRole,
        authority,
        nowMs,
    )
    val connector = verifiedGrant.plan.claims.connector
    endpointRequire(
        refreshed == verifiedGrant &&
            localRole == verifiedGrant.evidence.initiatorRole &&
            verifiedGrant.evidence.connectorTargetRole == P2pNatRole.RUNTIME &&
            verifiedGrant.plan.selectedRuntimeCandidate.address.contentEquals(connector.addressBytes) &&
            verifiedGrant.plan.selectedRuntimeCandidate.port == connector.port.toInt(),
        ProductionC1CandidateCapabilityError.ROUTE_MISMATCH,
    )
    val expectedHandle = try {
        ProductionC1RouteCommitments.routeHandleDigest(ProductionC1RouteKind.P2P_DIRECT, routeHandle)
    } catch (_: ProductionC1Exception) {
        endpointFail(ProductionC1CandidateCapabilityError.INVALID_VALUE)
    }
    val secretSnapshot = secret.copyOf()
    val expectedCredential = try {
        ProductionC1RouteCommitments.credentialCommitmentDigest(
            ProductionC1RouteKind.P2P_DIRECT,
            routeHandle,
            nonce,
            secretSnapshot,
        )
    } catch (_: ProductionC1Exception) {
        endpointFail(ProductionC1CandidateCapabilityError.INVALID_VALUE)
    }
    endpointRequire(
        expectedHandle == connector.routeHandleDigest &&
            expectedCredential == connector.credentialCommitmentDigest,
        ProductionC1CandidateCapabilityError.ROUTE_MISMATCH,
    )
    val handleBytes = endpointASCII(routeHandle)
    val nonceBytes = endpointASCII(nonce)
    endpointRequire(
        handleBytes.size <= ProductionC1RouteCommitments.MAXIMUM_ROUTE_HANDLE_BYTES &&
            nonceBytes.size <= ProductionC1RouteCommitments.MAXIMUM_NONCE_BYTES,
        ProductionC1CandidateCapabilityError.INVALID_VALUE,
    )
    val claims = ByteArrayOutputStream().apply {
        write(connector.canonicalBytes())
        write(ProductionC1InternalBridge.be(handleBytes.size.toUInt()))
        write(handleBytes)
        write(ProductionC1InternalBridge.be(nonceBytes.size.toUInt()))
        write(nonceBytes)
        write(endpointRawDigest(expectedCredential))
    }.toByteArray()
    return VerifiedProductionC1CandidateP2PConnectorInput(
        connector,
        endpointDomainDigest(
            "AetherLink G1a-C verified P2P connector-input commitment v1",
            claims,
        ),
        routeHandle,
        nonce,
        secretSnapshot,
        CandidateEndpointAdmissionProvenance.verifiedMint(),
    )
}

fun ProductionC1CandidateVerifier.makeP2PKeyConfirmation(
    transcript: ProductionSecureSessionTranscript,
    grantAuthorization: VerifiedProductionC1P2PGrantAuthorization,
    confirmingRole: P2pNatRole,
    key: ByteArray,
): ByteArray = endpointP2PKeyConfirmation(
    transcript,
    grantAuthorization,
    confirmingRole,
    key,
)

fun ProductionC1CandidateVerifier.verifyP2PTranscriptBinding(
    transcript: ProductionSecureSessionTranscript,
    verifiedGrant: VerifiedProductionC1P2PGrantEvidence,
    connectorInput: VerifiedProductionC1CandidateP2PConnectorInput,
    localRole: P2pNatRole,
    keyConfirmationKey: ByteArray,
    presentedPeerKeyConfirmation: ByteArray,
    authority: ProductionPairAuthorityState,
    nowMs: ULong,
): VerifiedProductionC1CandidateP2PTranscriptBinding {
    val keyScheduleBinding = verifyP2PKeyScheduleBinding(
        transcript,
        verifiedGrant,
        localRole,
        authority,
        nowMs,
    )
    val expectedInput = verifyP2PConnectorInput(
        verifiedGrant,
        localRole,
        connectorInput.routeHandle,
        connectorInput.nonce,
        connectorInput.secret,
        authority,
        nowMs,
    )
    val keySnapshot = keyConfirmationKey.copyOf()
    val presentedSnapshot = presentedPeerKeyConfirmation.copyOf()
    val expectedPeerConfirmation = endpointP2PKeyConfirmation(
        transcript,
        keyScheduleBinding.grantAuthorization,
        verifiedGrant.evidence.connectorTargetRole,
        keySnapshot,
    )
    endpointRequire(
        expectedInput == connectorInput &&
            localRole == P2pNatRole.CLIENT &&
            MessageDigest.isEqual(presentedSnapshot, expectedPeerConfirmation),
        ProductionC1CandidateCapabilityError.ROUTE_MISMATCH,
    )
    return VerifiedProductionC1CandidateP2PTranscriptBinding(
        transcript,
        verifiedGrant,
        connectorInput,
        keyScheduleBinding.securityContext,
        keyScheduleBinding,
        keySnapshot,
        presentedSnapshot,
        CandidateEndpointAdmissionProvenance.verifiedMint(),
    )
}

fun ProductionC1CandidateVerifier.verifyP2PKeyScheduleBinding(
    transcript: ProductionSecureSessionTranscript,
    verifiedGrant: VerifiedProductionC1P2PGrantEvidence,
    localRole: P2pNatRole,
    authority: ProductionPairAuthorityState,
    nowMs: ULong,
): VerifiedProductionC1CandidateP2PKeyScheduleBinding {
    val refreshed = verifyGrantEvidence(
        verifiedGrant.evidence,
        verifiedGrant.plan,
        verifiedGrant.routeAuthorizations,
        verifiedGrant.operationReceipts,
        localRole,
        authority,
        nowMs,
    )
    val expectedContext = try {
        ProductionC1PreauthorizationSessionContext(transcript)
    } catch (_: ProductionC1Exception) {
        endpointFail(ProductionC1CandidateCapabilityError.ROUTE_MISMATCH)
    }
    val evidence = verifiedGrant.evidence
    val grantAuthorization = verifyGrantAuthorization(
        verifiedGrant.grantAuthorization.authorization,
        evidence,
        verifiedGrant.plan,
        localRole,
    )
    endpointRequire(
        refreshed == verifiedGrant &&
            grantAuthorization == verifiedGrant.grantAuthorization &&
            expectedContext == verifiedGrant.plan.securityContext &&
            expectedContext.digestHex() == verifiedGrant.plan.claims.securityContextDigest &&
            authority.status == ProductionPairAuthorityStatus.ACTIVE &&
            authority.digestHex() == evidence.pairAuthorityDigest &&
            nowMs >= evidence.effectiveNotBeforeMs &&
            nowMs < evidence.expiresAtMs &&
            transcript.routeAuthorizationKind == ProductionRouteAuthorizationKind.P2P_DIRECT &&
            transcript.routeAuthorizationDigest == grantAuthorization.digestHex &&
            transcript.sessionId == evidence.sessionId &&
            transcript.pairBindingDigest == evidence.pairBindingDigest &&
            transcript.pairEpoch == evidence.pairEpoch &&
            transcript.generation == evidence.generation &&
            transcript.clientIdentityFingerprint == evidence.clientIdentityFingerprint &&
            transcript.runtimeIdentityFingerprint == evidence.runtimeIdentityFingerprint &&
            transcript.serviceConfigVersion == authority.serviceConfigVersion &&
            transcript.keysetVersion == authority.keysetVersion &&
            transcript.revocationCounter == authority.revocationCounter &&
            transcript.protocolVersion >= authority.protocolFloor &&
            transcript.minimumProtocolVersion >= authority.protocolFloor &&
            transcript.profile == ProductionSecureSessionContract.PROFILE,
        ProductionC1CandidateCapabilityError.ROUTE_MISMATCH,
    )
    return VerifiedProductionC1CandidateP2PKeyScheduleBinding(
        transcript,
        grantAuthorization,
        expectedContext,
        localRole,
        CandidateEndpointAdmissionProvenance.verifiedMint(),
    )
}

fun ProductionC1CandidateVerifier.verifyP2PInboundMaterial(
    transcript: ProductionSecureSessionTranscript,
    verifiedGrant: VerifiedProductionC1P2PGrantEvidence,
    localRole: P2pNatRole,
    observedPeerCandidate: P2pCandidate,
    keyConfirmationKey: ByteArray,
    presentedPeerKeyConfirmation: ByteArray,
    authority: ProductionPairAuthorityState,
    nowMs: ULong,
): VerifiedProductionC1CandidateP2PInboundMaterial {
    val refreshed = verifyGrantEvidence(
        verifiedGrant.evidence,
        verifiedGrant.plan,
        verifiedGrant.routeAuthorizations,
        verifiedGrant.operationReceipts,
        localRole,
        authority,
        nowMs,
    )
    val grantAuthorization = verifyGrantAuthorization(
        verifiedGrant.grantAuthorization.authorization,
        verifiedGrant.evidence,
        verifiedGrant.plan,
        localRole,
    )
    val presentedSnapshot = presentedPeerKeyConfirmation.copyOf()
    val expectedPeerConfirmation = endpointP2PKeyConfirmation(
        transcript,
        grantAuthorization,
        verifiedGrant.evidence.initiatorRole,
        keyConfirmationKey,
    )
    endpointRequire(
        refreshed == verifiedGrant &&
            localRole == verifiedGrant.evidence.connectorTargetRole &&
            observedPeerCandidate == verifiedGrant.plan.selectedClientCandidate &&
            MessageDigest.isEqual(presentedSnapshot, expectedPeerConfirmation),
        ProductionC1CandidateCapabilityError.ROUTE_MISMATCH,
    )
    return VerifiedProductionC1CandidateP2PInboundMaterial(
        observedPeerCandidate,
        ProductionC1InternalBridge.digestHex(presentedSnapshot),
        ProductionC1InternalBridge.digestHex(ProductionSecureSessionCodec.encode(transcript)),
        verifiedGrant.evidence.digestHex(),
        grantAuthorization.digestHex,
        verifiedGrant.evidence.sessionId,
        CandidateEndpointAdmissionProvenance.verifiedMint(),
    )
}

fun ProductionC1CandidateVerifier.verifyP2PInboundTranscriptBinding(
    transcript: ProductionSecureSessionTranscript,
    verifiedGrant: VerifiedProductionC1P2PGrantEvidence,
    inboundMaterial: VerifiedProductionC1CandidateP2PInboundMaterial,
    localRole: P2pNatRole,
    authority: ProductionPairAuthorityState,
    nowMs: ULong,
): VerifiedProductionC1CandidateP2PInboundTranscriptBinding {
    val expectedContext = try {
        ProductionC1PreauthorizationSessionContext(transcript)
    } catch (_: ProductionC1Exception) {
        endpointFail(ProductionC1CandidateCapabilityError.ROUTE_MISMATCH)
    }
    val grantAuthorization = verifyGrantAuthorization(
        verifiedGrant.grantAuthorization.authorization,
        verifiedGrant.evidence,
        verifiedGrant.plan,
        localRole,
    )
    val evidence = verifiedGrant.evidence
    val transcriptDigest =
        ProductionC1InternalBridge.digestHex(ProductionSecureSessionCodec.encode(transcript))
    endpointRequire(
        localRole == evidence.connectorTargetRole &&
            inboundMaterial.observedPeerCandidate == verifiedGrant.plan.selectedClientCandidate &&
            inboundMaterial.transcriptDigest == transcriptDigest &&
            inboundMaterial.routeGrantDigest == evidence.digestHex() &&
            inboundMaterial.grantAuthorizationDigest == grantAuthorization.digestHex &&
            inboundMaterial.sessionId == evidence.sessionId &&
            expectedContext == verifiedGrant.plan.securityContext &&
            transcript.routeAuthorizationKind == ProductionRouteAuthorizationKind.P2P_DIRECT &&
            transcript.routeAuthorizationDigest == grantAuthorization.digestHex &&
            transcript.sessionId == evidence.sessionId &&
            transcript.pairBindingDigest == evidence.pairBindingDigest &&
            transcript.pairEpoch == evidence.pairEpoch &&
            transcript.generation == evidence.generation &&
            authority.digestHex() == evidence.pairAuthorityDigest &&
            nowMs >= evidence.effectiveNotBeforeMs && nowMs < evidence.expiresAtMs,
        ProductionC1CandidateCapabilityError.ROUTE_MISMATCH,
    )
    return VerifiedProductionC1CandidateP2PInboundTranscriptBinding(
        transcript,
        verifiedGrant,
        inboundMaterial,
        expectedContext,
        CandidateEndpointAdmissionProvenance.verifiedMint(),
    )
}

private fun endpointP2PKeyConfirmation(
    transcript: ProductionSecureSessionTranscript,
    grantAuthorization: VerifiedProductionC1P2PGrantAuthorization,
    confirmingRole: P2pNatRole,
    key: ByteArray,
): ByteArray {
    val keySnapshot = key.copyOf()
    endpointRequire(keySnapshot.size == 32, ProductionC1CandidateCapabilityError.INVALID_VALUE)
    val claims = ByteArrayOutputStream().apply {
        write(ProductionSecureSessionCodec.encode(transcript))
        write(grantAuthorization.authorization.canonicalBytes())
        write(endpointASCII(confirmingRole.wireValue))
    }.toByteArray()
    val message = ProductionC1InternalBridge.transcript(
        "AetherLink G1a-C role-labeled P2P key confirmation v1",
        claims,
    )
    return Mac.getInstance("HmacSHA256").run {
        init(SecretKeySpec(keySnapshot, "HmacSHA256"))
        doFinal(message)
    }
}

class ProductionC1EndpointGrantEntry internal constructor(
    val admissionId: String,
    val bindingDigest: String,
    val routeGrantDigest: String,
    val sessionId: String,
    val transcriptDigest: String,
    /** Digest of the generic final P2P_DIRECT route authorization (object 4). */
    val routeAuthorizationDigest: String,
    /** Digest of the verified grant authorization (object 26) bound by the transcript. */
    val grantAuthorizationDigest: String,
    val connectorInputCommitmentDigest: String,
    val pairSnapshotDigest: String,
    val committedRevision: ULong,
) {
    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is ProductionC1EndpointGrantEntry &&
                admissionId == other.admissionId &&
                bindingDigest == other.bindingDigest &&
                routeGrantDigest == other.routeGrantDigest &&
                sessionId == other.sessionId &&
                transcriptDigest == other.transcriptDigest &&
                routeAuthorizationDigest == other.routeAuthorizationDigest &&
                grantAuthorizationDigest == other.grantAuthorizationDigest &&
                connectorInputCommitmentDigest == other.connectorInputCommitmentDigest &&
                pairSnapshotDigest == other.pairSnapshotDigest &&
                committedRevision == other.committedRevision)

    override fun hashCode(): Int {
        var result = admissionId.hashCode()
        result = 31 * result + bindingDigest.hashCode()
        result = 31 * result + routeGrantDigest.hashCode()
        result = 31 * result + sessionId.hashCode()
        result = 31 * result + transcriptDigest.hashCode()
        result = 31 * result + routeAuthorizationDigest.hashCode()
        result = 31 * result + grantAuthorizationDigest.hashCode()
        result = 31 * result + connectorInputCommitmentDigest.hashCode()
        result = 31 * result + pairSnapshotDigest.hashCode()
        return 31 * result + committedRevision.hashCode()
    }
}

class ProductionC1EndpointGrantLedgerState(
    val revision: ULong = 1uL,
    val pairAuthorityDigest: String,
    val pairLocalRevision: ULong,
    val remainingGrants: ULong,
    val retentionLimit: UInt,
    entries: List<ProductionC1EndpointGrantEntry> = emptyList(),
) {
    private val entryValues = entries.toList()
    val entries: List<ProductionC1EndpointGrantEntry> get() = entryValues.toList()

    init {
        endpointValidateDigest(pairAuthorityDigest)
        endpointRequire(
            revision > 0uL && pairLocalRevision > 0uL && retentionLimit > 0u &&
                entryValues.size <= retentionLimit.toInt() &&
                revision == entryValues.size.toULong() + 1uL &&
                entryValues.map { it.admissionId }.toSet().size == entryValues.size &&
                entryValues.map { it.sessionId }.toSet().size == entryValues.size &&
                entryValues.map { it.routeGrantDigest }.toSet().size == entryValues.size &&
                entryValues.map { it.transcriptDigest }.toSet().size == entryValues.size,
            ProductionC1CandidateCapabilityError.INVALID_VALUE,
        )
        entryValues.forEachIndexed { index, entry ->
            listOf(
                entry.admissionId,
                entry.bindingDigest,
                entry.routeGrantDigest,
                entry.transcriptDigest,
                entry.routeAuthorizationDigest,
                entry.grantAuthorizationDigest,
                entry.connectorInputCommitmentDigest,
                entry.pairSnapshotDigest,
            ).forEach(::endpointValidateDigest)
            endpointRequire(
                endpointIsLowerHex(entry.sessionId, 32) &&
                    entry.committedRevision == index.toULong() + 2uL,
                ProductionC1CandidateCapabilityError.INVALID_VALUE,
            )
        }
    }

    fun snapshotDigestHex(): String {
        val claims = ByteArrayOutputStream().apply {
            write(ProductionC1InternalBridge.be(revision))
            write(endpointRawDigest(pairAuthorityDigest))
            write(ProductionC1InternalBridge.be(pairLocalRevision))
            write(ProductionC1InternalBridge.be(remainingGrants))
            write(ProductionC1InternalBridge.be(retentionLimit))
            entryValues.forEach { entry ->
                listOf(
                    entry.admissionId,
                    entry.bindingDigest,
                    entry.routeGrantDigest,
                    entry.transcriptDigest,
                    entry.routeAuthorizationDigest,
                    entry.grantAuthorizationDigest,
                    entry.connectorInputCommitmentDigest,
                    entry.pairSnapshotDigest,
                ).forEach { write(endpointRawDigest(it)) }
                write(endpointASCII(entry.sessionId))
                write(ProductionC1InternalBridge.be(entry.committedRevision))
            }
        }.toByteArray()
        return endpointDomainDigest(
            "AetherLink G1a-C endpoint grant ledger snapshot v2 object4+object26",
            claims,
        )
    }

    fun persistenceCanonicalBytes(): ByteArray = ProductionC1EndpointLedgerPersistenceCodec.encode(this)

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is ProductionC1EndpointGrantLedgerState &&
                revision == other.revision &&
                pairAuthorityDigest == other.pairAuthorityDigest &&
                pairLocalRevision == other.pairLocalRevision &&
                remainingGrants == other.remainingGrants &&
                retentionLimit == other.retentionLimit &&
                entryValues == other.entryValues)

    override fun hashCode(): Int {
        var result = revision.hashCode()
        result = 31 * result + pairAuthorityDigest.hashCode()
        result = 31 * result + pairLocalRevision.hashCode()
        result = 31 * result + remainingGrants.hashCode()
        result = 31 * result + retentionLimit.hashCode()
        return 31 * result + entryValues.hashCode()
    }

    companion object {
        fun decodePersistenceCanonicalBytes(data: ByteArray): ProductionC1EndpointGrantLedgerState =
            ProductionC1EndpointLedgerPersistenceCodec.decode(data)
    }
}

class ProductionC1EndpointCompoundRecord(
    val grantLedger: ProductionC1EndpointGrantLedgerState,
    val pairSnapshot: ProductionPairStateSnapshot,
) {
    init {
        endpointRequire(
            pairSnapshot.authority.digestHex() == grantLedger.pairAuthorityDigest &&
                pairSnapshot.localRevision == grantLedger.pairLocalRevision,
            ProductionC1CandidateCapabilityError.AUTHORITY_MISMATCH,
        )
    }

    fun digestHex(): String {
        val claims = endpointRawDigest(grantLedger.snapshotDigestHex()) +
            endpointRawDigest(pairSnapshot.digestHex())
        return endpointDomainDigest(
            "AetherLink G1a-C endpoint pair-and-grant compound record v1",
            claims,
        )
    }

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is ProductionC1EndpointCompoundRecord &&
                grantLedger == other.grantLedger && pairSnapshot == other.pairSnapshot)

    override fun hashCode(): Int = 31 * grantLedger.hashCode() + pairSnapshot.hashCode()
}

class ProductionC1EndpointGrantAdmissionPreparation internal constructor(
    val disposition: ProductionC1CandidateCASDisposition,
    val expectedRevision: ULong,
    val expectedSnapshotDigest: String,
    val expectedPairSnapshotDigest: String,
    val effectiveNotBeforeMs: ULong,
    val expiresAtMs: ULong,
    val nextState: ProductionC1EndpointGrantLedgerState,
    val nextPairSnapshot: ProductionPairStateSnapshot,
    val expectedCompoundDigest: String,
    val nextCompoundRecord: ProductionC1EndpointCompoundRecord,
    val entry: ProductionC1EndpointGrantEntry,
    provenance: Any,
) {
    init {
        endpointRequire(
            CandidateEndpointAdmissionProvenance.ownsPreparationMint(provenance),
            ProductionC1CandidateCapabilityError.PERSISTENCE_UNAVAILABLE,
        )
        listOf(
            expectedSnapshotDigest,
            expectedPairSnapshotDigest,
            expectedCompoundDigest,
        ).forEach(::endpointValidateDigest)
        endpointRequire(
            effectiveNotBeforeMs < expiresAtMs,
            ProductionC1CandidateCapabilityError.INVALID_VALUE,
        )
    }

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is ProductionC1EndpointGrantAdmissionPreparation &&
                disposition == other.disposition &&
                expectedRevision == other.expectedRevision &&
                expectedSnapshotDigest == other.expectedSnapshotDigest &&
                expectedPairSnapshotDigest == other.expectedPairSnapshotDigest &&
                effectiveNotBeforeMs == other.effectiveNotBeforeMs &&
                expiresAtMs == other.expiresAtMs &&
                nextState == other.nextState &&
                nextPairSnapshot == other.nextPairSnapshot &&
                expectedCompoundDigest == other.expectedCompoundDigest &&
                nextCompoundRecord == other.nextCompoundRecord &&
                entry == other.entry)

    override fun hashCode(): Int {
        var result = disposition.hashCode()
        result = 31 * result + expectedRevision.hashCode()
        result = 31 * result + expectedSnapshotDigest.hashCode()
        result = 31 * result + expectedPairSnapshotDigest.hashCode()
        result = 31 * result + effectiveNotBeforeMs.hashCode()
        result = 31 * result + expiresAtMs.hashCode()
        result = 31 * result + nextState.hashCode()
        result = 31 * result + nextPairSnapshot.hashCode()
        result = 31 * result + expectedCompoundDigest.hashCode()
        result = 31 * result + nextCompoundRecord.hashCode()
        return 31 * result + entry.hashCode()
    }
}

class ReadbackConfirmedProductionC1EndpointGrantAdmission private constructor(
    val entry: ProductionC1EndpointGrantEntry,
) {
    companion object {
        fun confirm(
            preparation: ProductionC1EndpointGrantAdmissionPreparation,
            committedCompoundReadback: ProductionC1EndpointCompoundRecord,
        ): ReadbackConfirmedProductionC1EndpointGrantAdmission {
            val committedLedger = committedCompoundReadback.grantLedger
            val committedPair = committedCompoundReadback.pairSnapshot
            endpointRequire(
                committedLedger == preparation.nextState &&
                    committedPair == preparation.nextPairSnapshot &&
                    committedCompoundReadback == preparation.nextCompoundRecord &&
                    committedLedger.entries.contains(preparation.entry) &&
                    committedPair.digestHex() == preparation.entry.pairSnapshotDigest,
                ProductionC1CandidateCapabilityError.REVISION_MISMATCH,
            )
            if (preparation.disposition == ProductionC1CandidateCASDisposition.APPLIED) {
                endpointRequire(
                    committedLedger.revision == preparation.entry.committedRevision &&
                        committedPair.localRevision == committedLedger.pairLocalRevision,
                    ProductionC1CandidateCapabilityError.REVISION_MISMATCH,
                )
            }
            return ReadbackConfirmedProductionC1EndpointGrantAdmission(preparation.entry)
        }
    }
}

object ProductionC1EndpointGrantAdmission {
    fun bindingDigest(
        admissionId: String,
        routeGrantDigest: String,
        transcriptDigest: String,
        /** Generic final P2P_DIRECT authorization digest (object 4). */
        routeAuthorizationDigest: String,
        /** Grant authorization digest (object 26). */
        grantAuthorizationDigest: String,
        connectorInputCommitmentDigest: String,
    ): String {
        val claims = ByteArrayOutputStream().apply {
            listOf(
                admissionId,
                routeGrantDigest,
                transcriptDigest,
                routeAuthorizationDigest,
                grantAuthorizationDigest,
                connectorInputCommitmentDigest,
            ).forEach { write(endpointRawDigest(it)) }
        }.toByteArray()
        return endpointDomainDigest(
            "AetherLink G1a-C endpoint grant admission binding v2 object4+object26",
            claims,
        )
    }

    fun prepareCommittedRetry(
        state: ProductionC1EndpointGrantLedgerState,
        admissionId: String,
        bindingDigest: String,
        grantEvidenceCanonicalBytes: ByteArray,
        routeAuthorization: ProductionRouteAuthorization,
        transcriptCanonicalBytes: ByteArray,
        connectorInputCommitmentDigest: String,
        currentPairSnapshot: ProductionPairStateSnapshot,
    ): ProductionC1EndpointGrantAdmissionPreparation {
        val grantBytesSnapshot = grantEvidenceCanonicalBytes.copyOf()
        val transcriptBytesSnapshot = transcriptCanonicalBytes.copyOf()
        val evidence = ProductionC1P2PGrantEvidence.decode(grantBytesSnapshot)
        val transcript = ProductionSecureSessionCodec.decodeTranscript(transcriptBytesSnapshot)
        val grantDigest = ProductionC1InternalBridge.digestHex(grantBytesSnapshot)
        val grantAuthorization = ProductionC1CandidateVerifier.makeGrantAuthorization(evidence)
        val grantAuthorizationDigest = grantAuthorization.digestHex()
        val routeDigest = endpointRouteAuthorizationDigest(routeAuthorization)
        val transcriptDigest = ProductionC1InternalBridge.digestHex(transcriptBytesSnapshot)
        val exactBinding = bindingDigest(
            admissionId,
            grantDigest,
            transcriptDigest,
            routeDigest,
            grantAuthorizationDigest,
            connectorInputCommitmentDigest,
        )
        val pairSnapshotDigest = currentPairSnapshot.digestHex()
        val existing = state.entries.firstOrNull { it.admissionId == admissionId }
        endpointRequire(
            bindingDigest == exactBinding &&
                evidence.canonicalBytes().contentEquals(grantBytesSnapshot) &&
                ProductionSecureSessionCodec.encode(transcript).contentEquals(transcriptBytesSnapshot) &&
                routeDigest == evidence.finalRouteAuthorizationDigest &&
                transcript.routeAuthorizationDigest == grantAuthorizationDigest &&
                transcript.sessionId == evidence.sessionId &&
                existing != null &&
                existing.bindingDigest == bindingDigest &&
                existing.routeGrantDigest == grantDigest &&
                existing.sessionId == transcript.sessionId &&
                existing.transcriptDigest == transcriptDigest &&
                existing.routeAuthorizationDigest == routeDigest &&
                existing.grantAuthorizationDigest == grantAuthorizationDigest &&
                existing.connectorInputCommitmentDigest == connectorInputCommitmentDigest &&
                existing.pairSnapshotDigest == pairSnapshotDigest &&
                currentPairSnapshot.localRevision == state.pairLocalRevision &&
                currentPairSnapshot.authority.digestHex() == state.pairAuthorityDigest,
            ProductionC1CandidateCapabilityError.REQUEST_CONFLICT,
        )
        val compound = ProductionC1EndpointCompoundRecord(state, currentPairSnapshot)
        return preparation(
            ProductionC1CandidateCASDisposition.IDEMPOTENT,
            state.revision,
            state.snapshotDigestHex(),
            pairSnapshotDigest,
            evidence.effectiveNotBeforeMs,
            evidence.expiresAtMs,
            state,
            currentPairSnapshot,
            compound.digestHex(),
            compound,
            existing!!,
        )
    }

    fun prepareForTrustedPersistence(
        state: ProductionC1EndpointGrantLedgerState,
        expectedRevision: ULong,
        expectedSnapshotDigest: String,
        admissionId: String,
        bindingDigest: String,
        verifiedBinding: VerifiedProductionC1CandidateP2PTranscriptBinding,
        currentPairSnapshot: ProductionPairStateSnapshot,
        nowMs: ULong,
    ): ProductionC1EndpointGrantAdmissionPreparation = prepare(
        state,
        expectedRevision,
        expectedSnapshotDigest,
        admissionId,
        bindingDigest,
        verifiedBinding,
        currentPairSnapshot,
        nowMs,
    )

    fun prepare(
        state: ProductionC1EndpointGrantLedgerState,
        expectedRevision: ULong,
        expectedSnapshotDigest: String,
        admissionId: String,
        bindingDigest: String,
        verifiedBinding: VerifiedProductionC1CandidateP2PTranscriptBinding,
        currentPairSnapshot: ProductionPairStateSnapshot,
        nowMs: ULong,
    ): ProductionC1EndpointGrantAdmissionPreparation {
        val verifiedGrant = verifiedBinding.grant
        val transcript = verifiedBinding.transcript
        val evidence = verifiedGrant.evidence
        val routeAuthorization = verifiedGrant.routeAuthorizations.finalP2PDirect
        val routeDigest = endpointRouteAuthorizationDigest(routeAuthorization)
        val grantAuthorizationDigest = verifiedGrant.grantAuthorization.digestHex
        val transcriptBytes = ProductionSecureSessionCodec.encode(transcript)
        val transcriptDigest = ProductionC1InternalBridge.digestHex(transcriptBytes)
        val grantDigest = evidence.digestHex()
        val expectedBinding = bindingDigest(
            admissionId,
            grantDigest,
            transcriptDigest,
            routeDigest,
            grantAuthorizationDigest,
            verifiedBinding.connectorInput.commitmentDigest,
        )
        endpointRequire(
            bindingDigest == expectedBinding &&
                routeAuthorization == verifiedGrant.routeAuthorizations.finalP2PDirect &&
                routeDigest == evidence.finalRouteAuthorizationDigest &&
                transcript.routeAuthorizationKind == ProductionRouteAuthorizationKind.P2P_DIRECT &&
                transcript.routeAuthorizationDigest == verifiedGrant.grantAuthorization.digestHex &&
                transcript.sessionId == evidence.sessionId &&
                transcript.pairBindingDigest == evidence.pairBindingDigest &&
                transcript.pairEpoch == evidence.pairEpoch &&
                transcript.generation == evidence.generation &&
                transcript.clientIdentityFingerprint == evidence.clientIdentityFingerprint &&
                transcript.runtimeIdentityFingerprint == evidence.runtimeIdentityFingerprint &&
                ProductionC1PreauthorizationSessionContext(transcript) == verifiedGrant.plan.securityContext,
            ProductionC1CandidateCapabilityError.ROUTE_MISMATCH,
        )
        val currentPairDigest = currentPairSnapshot.digestHex()
        state.entries.firstOrNull { it.admissionId == admissionId }?.let { existing ->
            endpointRequire(
                existing.bindingDigest == bindingDigest &&
                    existing.routeGrantDigest == grantDigest &&
                    existing.sessionId == transcript.sessionId &&
                    existing.transcriptDigest == transcriptDigest &&
                    existing.routeAuthorizationDigest == routeDigest &&
                    existing.grantAuthorizationDigest == grantAuthorizationDigest &&
                    existing.connectorInputCommitmentDigest ==
                    verifiedBinding.connectorInput.commitmentDigest &&
                    existing.pairSnapshotDigest == currentPairDigest &&
                    currentPairSnapshot.localRevision == state.pairLocalRevision &&
                    currentPairSnapshot.authority.digestHex() == state.pairAuthorityDigest,
                ProductionC1CandidateCapabilityError.REQUEST_CONFLICT,
            )
            val compound = ProductionC1EndpointCompoundRecord(state, currentPairSnapshot)
            return preparation(
                ProductionC1CandidateCASDisposition.IDEMPOTENT,
                state.revision,
                state.snapshotDigestHex(),
                currentPairDigest,
                evidence.effectiveNotBeforeMs,
                evidence.expiresAtMs,
                state,
                currentPairSnapshot,
                compound.digestHex(),
                compound,
                existing,
            )
        }
        val refreshed = ProductionC1CandidateVerifier.verifyP2PTranscriptBinding(
            transcript,
            verifiedGrant,
            verifiedBinding.connectorInput,
            P2pNatRole.CLIENT,
            verifiedBinding.keyConfirmationKey,
            verifiedBinding.presentedPeerKeyConfirmation,
            currentPairSnapshot.authority,
            nowMs,
        )
        endpointRequire(refreshed == verifiedBinding, ProductionC1CandidateCapabilityError.ROUTE_MISMATCH)
        endpointRequire(
            nowMs >= evidence.effectiveNotBeforeMs && nowMs < evidence.expiresAtMs &&
                currentPairSnapshot.authority.digestHex() == state.pairAuthorityDigest &&
                currentPairSnapshot.localRevision == state.pairLocalRevision &&
                currentPairSnapshot.authority.digestHex() == evidence.pairAuthorityDigest,
            ProductionC1CandidateCapabilityError.AUTHORITY_MISMATCH,
        )
        endpointRequire(
            state.revision == expectedRevision && state.snapshotDigestHex() == expectedSnapshotDigest,
            ProductionC1CandidateCapabilityError.REVISION_MISMATCH,
        )
        endpointRequire(
            state.entries.size < state.retentionLimit.toInt(),
            ProductionC1CandidateCapabilityError.RETENTION_EXHAUSTED,
        )
        endpointRequire(
            state.entries.none {
                it.routeGrantDigest == grantDigest || it.sessionId == transcript.sessionId ||
                    it.transcriptDigest == transcriptDigest
            } &&
                currentPairSnapshot.consumedEntries.none {
                    it.sessionId == transcript.sessionId || it.transcriptDigest == transcriptDigest
                },
            ProductionC1CandidateCapabilityError.REPLAY,
        )
        endpointRequire(
            state.remainingGrants > 0uL && state.revision < ULong.MAX_VALUE &&
                currentPairSnapshot.localRevision < ULong.MAX_VALUE,
            ProductionC1CandidateCapabilityError.QUOTA_EXCEEDED,
        )
        val nextPairSnapshot = ProductionPairStateSnapshot(
            currentPairSnapshot.authority,
            currentPairSnapshot.localRevision + 1uL,
            currentPairSnapshot.consumedEntries + ProductionPairConsumedSession(
                transcript.sessionId,
                transcriptDigest,
            ),
            currentPairSnapshot.transitionHistory,
        )
        val nextPairDigest = nextPairSnapshot.digestHex()
        val entry = ProductionC1EndpointGrantEntry(
            admissionId,
            bindingDigest,
            grantDigest,
            transcript.sessionId,
            transcriptDigest,
            routeDigest,
            grantAuthorizationDigest,
            verifiedBinding.connectorInput.commitmentDigest,
            nextPairDigest,
            state.revision + 1uL,
        )
        val next = ProductionC1EndpointGrantLedgerState(
            state.revision + 1uL,
            state.pairAuthorityDigest,
            nextPairSnapshot.localRevision,
            state.remainingGrants - 1uL,
            state.retentionLimit,
            state.entries + entry,
        )
        val currentCompound = ProductionC1EndpointCompoundRecord(state, currentPairSnapshot)
        val nextCompound = ProductionC1EndpointCompoundRecord(next, nextPairSnapshot)
        return preparation(
            ProductionC1CandidateCASDisposition.APPLIED,
            state.revision,
            expectedSnapshotDigest,
            currentPairDigest,
            evidence.effectiveNotBeforeMs,
            evidence.expiresAtMs,
            next,
            nextPairSnapshot,
            currentCompound.digestHex(),
            nextCompound,
            entry,
        )
    }

    private fun preparation(
        disposition: ProductionC1CandidateCASDisposition,
        expectedRevision: ULong,
        expectedSnapshotDigest: String,
        expectedPairSnapshotDigest: String,
        effectiveNotBeforeMs: ULong,
        expiresAtMs: ULong,
        nextState: ProductionC1EndpointGrantLedgerState,
        nextPairSnapshot: ProductionPairStateSnapshot,
        expectedCompoundDigest: String,
        nextCompoundRecord: ProductionC1EndpointCompoundRecord,
        entry: ProductionC1EndpointGrantEntry,
    ): ProductionC1EndpointGrantAdmissionPreparation =
        ProductionC1EndpointGrantAdmissionPreparation(
            disposition,
            expectedRevision,
            expectedSnapshotDigest,
            expectedPairSnapshotDigest,
            effectiveNotBeforeMs,
            expiresAtMs,
            nextState,
            nextPairSnapshot,
            expectedCompoundDigest,
            nextCompoundRecord,
            entry,
            CandidateEndpointAdmissionProvenance.preparationMint(),
        )
}

object ProductionC1EndpointLedgerPersistenceContract {
    const val VERSION: UInt = 2u
    const val MAXIMUM_ENTRIES: Int = ProductionPairStateContract.MAX_CONSUMED_ENTRIES
    const val MAXIMUM_BYTES: Int = 32 * 1024
}

object ProductionC1EndpointLedgerPersistenceCodec {
    private val magic = "ALC1EGL1".toByteArray(Charsets.US_ASCII)

    fun encode(state: ProductionC1EndpointGrantLedgerState): ByteArray {
        val entries = state.entries
        endpointRequire(
            entries.size <= ProductionC1EndpointLedgerPersistenceContract.MAXIMUM_ENTRIES &&
                state.retentionLimit <=
                ProductionC1EndpointLedgerPersistenceContract.MAXIMUM_ENTRIES.toUInt() &&
                state.remainingGrants <= state.retentionLimit.toULong() &&
                entries.size.toULong() + state.remainingGrants <= state.retentionLimit.toULong(),
            ProductionC1CandidateCapabilityError.RETENTION_EXHAUSTED,
        )
        val data = ByteArrayOutputStream().apply {
            write(magic)
            write(ProductionC1InternalBridge.be(ProductionC1EndpointLedgerPersistenceContract.VERSION))
            write(ProductionC1InternalBridge.be(state.revision))
            write(endpointRawDigest(state.pairAuthorityDigest))
            write(ProductionC1InternalBridge.be(state.pairLocalRevision))
            write(ProductionC1InternalBridge.be(state.remainingGrants))
            write(ProductionC1InternalBridge.be(state.retentionLimit))
            write(ProductionC1InternalBridge.be(entries.size.toUInt()))
            entries.forEach { entry ->
                listOf(
                    entry.admissionId,
                    entry.bindingDigest,
                    entry.routeGrantDigest,
                    entry.transcriptDigest,
                    entry.routeAuthorizationDigest,
                    entry.grantAuthorizationDigest,
                    entry.connectorInputCommitmentDigest,
                    entry.pairSnapshotDigest,
                ).forEach { write(endpointRawDigest(it)) }
                endpointRequire(
                    endpointIsLowerHex(entry.sessionId, 32),
                    ProductionC1CandidateCapabilityError.INVALID_VALUE,
                )
                write(endpointASCII(entry.sessionId))
                write(ProductionC1InternalBridge.be(entry.committedRevision))
            }
        }.toByteArray()
        endpointRequire(
            data.size <= ProductionC1EndpointLedgerPersistenceContract.MAXIMUM_BYTES,
            ProductionC1CandidateCapabilityError.RETENTION_EXHAUSTED,
        )
        return data
    }

    fun decode(data: ByteArray): ProductionC1EndpointGrantLedgerState {
        val snapshot = data.copyOf()
        endpointRequire(
            snapshot.size <= ProductionC1EndpointLedgerPersistenceContract.MAXIMUM_BYTES,
            ProductionC1CandidateCapabilityError.RETENTION_EXHAUSTED,
        )
        val reader = EndpointLedgerPersistenceReader(snapshot)
        endpointRequire(
            reader.read(8).contentEquals(magic) &&
                reader.uint32() == ProductionC1EndpointLedgerPersistenceContract.VERSION,
            ProductionC1CandidateCapabilityError.MALFORMED_CANONICAL,
        )
        val revision = reader.uint64()
        val pairAuthorityDigest = reader.digestHex()
        val pairLocalRevision = reader.uint64()
        val remainingGrants = reader.uint64()
        val retentionLimit = reader.uint32()
        val entryCount = reader.uint32()
        endpointRequire(
            retentionLimit <= ProductionC1EndpointLedgerPersistenceContract.MAXIMUM_ENTRIES.toUInt() &&
                entryCount <= retentionLimit &&
                entryCount <= ProductionC1EndpointLedgerPersistenceContract.MAXIMUM_ENTRIES.toUInt() &&
                remainingGrants <= retentionLimit.toULong() &&
                entryCount.toULong() + remainingGrants <= retentionLimit.toULong(),
            ProductionC1CandidateCapabilityError.RETENTION_EXHAUSTED,
        )
        val entries = buildList {
            repeat(entryCount.toInt()) {
                val admissionId = reader.digestHex()
                val bindingDigest = reader.digestHex()
                val routeGrantDigest = reader.digestHex()
                val transcriptDigest = reader.digestHex()
                val routeAuthorizationDigest = reader.digestHex()
                val grantAuthorizationDigest = reader.digestHex()
                val connectorInputCommitmentDigest = reader.digestHex()
                val pairSnapshotDigest = reader.digestHex()
                val sessionId = reader.lowerHexText(32)
                add(
                    ProductionC1EndpointGrantEntry(
                        admissionId,
                        bindingDigest,
                        routeGrantDigest,
                        sessionId,
                        transcriptDigest,
                        routeAuthorizationDigest,
                        grantAuthorizationDigest,
                        connectorInputCommitmentDigest,
                        pairSnapshotDigest,
                        reader.uint64(),
                    ),
                )
            }
        }
        endpointRequire(reader.isAtEnd, ProductionC1CandidateCapabilityError.MALFORMED_CANONICAL)
        val result = ProductionC1EndpointGrantLedgerState(
            revision,
            pairAuthorityDigest,
            pairLocalRevision,
            remainingGrants,
            retentionLimit,
            entries,
        )
        endpointRequire(
            encode(result).contentEquals(snapshot),
            ProductionC1CandidateCapabilityError.MALFORMED_CANONICAL,
        )
        return result
    }
}

private class EndpointLedgerPersistenceReader(
    private val data: ByteArray,
) {
    private var offset = 0
    val isAtEnd: Boolean get() = offset == data.size

    fun read(count: Int): ByteArray {
        endpointRequire(
            count >= 0 && offset <= data.size && count <= data.size - offset,
            ProductionC1CandidateCapabilityError.MALFORMED_CANONICAL,
        )
        val end = offset + count
        return data.copyOfRange(offset, end).also { offset = end }
    }

    fun uint32(): UInt = read(4).fold(0u) { result, byte ->
        (result shl 8) or (byte.toUInt() and 0xffu)
    }

    fun uint64(): ULong = read(8).fold(0uL) { result, byte ->
        (result shl 8) or (byte.toULong() and 0xffuL)
    }

    fun digestHex(): String = read(32).toLowerHex()

    fun lowerHexText(byteCount: Int): String {
        val value = read(byteCount).toString(Charsets.US_ASCII)
        endpointRequire(
            endpointIsLowerHex(value, byteCount),
            ProductionC1CandidateCapabilityError.MALFORMED_CANONICAL,
        )
        return value
    }
}

private object CandidateEndpointAdmissionProvenance {
    private val verified = Any()
    private val preparation = Any()

    fun verifiedMint(): Any = verified
    fun preparationMint(): Any = preparation
    fun ownsVerifiedMint(value: Any): Boolean = value === verified
    fun ownsPreparationMint(value: Any): Boolean = value === preparation
}

private fun endpointRouteAuthorizationDigest(value: ProductionRouteAuthorization): String =
    ProductionC1InternalBridge.digestHex(ProductionSecureSessionCodec.encode(value))

private fun endpointDomainDigest(domain: String, claims: ByteArray): String =
    ProductionC1InternalBridge.digestHex(ProductionC1InternalBridge.transcript(domain, claims))

private fun endpointASCII(value: String): ByteArray = try {
    ProductionC1InternalBridge.ascii(value)
} catch (_: ProductionC1Exception) {
    endpointFail(ProductionC1CandidateCapabilityError.INVALID_VALUE)
}

private fun endpointValidateDigest(value: String) {
    try {
        ProductionC1InternalBridge.validateDigest(value)
    } catch (_: ProductionC1Exception) {
        endpointFail(ProductionC1CandidateCapabilityError.INVALID_VALUE)
    }
}

private fun endpointRawDigest(value: String): ByteArray = try {
    ProductionC1InternalBridge.rawDigest(value)
} catch (_: ProductionC1Exception) {
    endpointFail(ProductionC1CandidateCapabilityError.INVALID_VALUE)
}

private fun endpointIsLowerHex(value: String, count: Int): Boolean =
    value.length == count && value.all { it in '0'..'9' || it in 'a'..'f' }

private fun ByteArray.toLowerHex(): String = joinToString("") { byte ->
    (byte.toInt() and 0xff).toString(16).padStart(2, '0')
}

private fun endpointRequire(
    condition: Boolean,
    error: ProductionC1CandidateCapabilityError,
) {
    if (!condition) endpointFail(error)
}

private fun endpointFail(error: ProductionC1CandidateCapabilityError): Nothing =
    throw ProductionC1CandidateCapabilityException(error)
