package com.localagentbridge.android.core.protocol.p2pnat

import java.math.BigInteger
import java.lang.reflect.Modifier
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
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

class ProductionG1aCContractsTest {
    private val now = 1_000_000uL
    private val serviceId = "a".repeat(64)

    @Test
    fun serviceKeysetVerifiesCanonicalRoundTripAndNMinusOneRotation() {
        val root = privateKey(1)
        val statusKey = privateKey(2)
        val routeKey = privateKey(3)
        val first = keyset(
            root,
            1uL,
            null,
            listOf(delegated(statusKey, 1uL, ProductionC1DelegatedKeyPurpose.ALLOWED)),
        )
        val verifiedFirst = ProductionC1Verifier.verifyServiceKeyset(
            first, serviceId, publicKey(root), 1uL, nowMs = now,
        )
        assertC1Error(ProductionC1Error.STATE_MISMATCH) {
            VerifiedProductionC1ServiceKeyset(first, Any())
        }
        assertEquals(first, ProductionC1ServiceKeyset.decode(first.canonicalBytes()))

        val second = keyset(
            root,
            2uL,
            first.digestHex(),
            listOf(
                delegated(statusKey, 1uL, ProductionC1DelegatedKeyPurpose.PAIR_STATUS),
                delegated(routeKey, 2uL, ProductionC1DelegatedKeyPurpose.ROUTE_CAPABILITY),
            ).sortedBy { it.keyId },
        )
        val verifiedSecond = ProductionC1Verifier.verifyServiceKeyset(
            second, serviceId, publicKey(root), 1uL, verifiedFirst, now,
        )
        assertEquals(2uL, verifiedSecond.keyset.keysetVersion)

        val attacker = privateKey(75)
        val exposedCopy = verifiedSecond.keyset.delegatedKeys as MutableList<ProductionC1DelegatedKey>
        exposedCopy.clear()
        exposedCopy += delegated(attacker, 2uL, ProductionC1DelegatedKeyPurpose.PAIR_STATUS)
        assertEquals(second.delegatedKeys, verifiedSecond.keyset.delegatedKeys)
        assertC1Error(ProductionC1Error.KEY_UNAVAILABLE) {
            ProductionC1InternalBridge.delegatedSigningKey(
                keyId(publicKey(attacker)),
                ProductionC1DelegatedKeyPurpose.PAIR_STATUS,
                verifiedSecond,
                now,
            )
        }

        val gap = keyset(
            root,
            3uL,
            first.digestHex(),
            listOf(delegated(routeKey, 3uL, ProductionC1DelegatedKeyPurpose.ROUTE_CAPABILITY)),
        )
        assertC1Error(ProductionC1Error.KEYSET_GAP) {
            ProductionC1Verifier.verifyServiceKeyset(
                gap, serviceId, publicKey(root), 1uL, verifiedFirst, now,
            )
        }
    }

    @Test
    fun verifiedMintTokensRemainPrivateAtJvmBoundary() {
        listOf(
            ProductionC1Verifier::class.java to "verifiedMint",
        ).forEach { (owner, fieldName) ->
            val field = owner.getDeclaredField(fieldName)
            assertTrue(Modifier.isPrivate(field.modifiers))
            assertTrue(Modifier.isStatic(field.modifiers))
            assertTrue(
                owner.methods.none {
                    it.name.contains("Mint", ignoreCase = true) && it.returnType == Any::class.java
                }
            )
        }
        val fileClass = Class.forName(
            "com.localagentbridge.android.core.protocol.p2pnat.ProductionG1aCContractsKt"
        )
        assertTrue(fileClass.declaredFields.none { it.name.contains("Mint", ignoreCase = true) })
        assertTrue(
            fileClass.declaredMethods.none {
                it.name.contains("Mint", ignoreCase = true) && it.returnType == Any::class.java
            }
        )
        assertTrue(
            ProductionC1PairStateAdmission::class.java.declaredFields.none {
                it.name.contains("Mint", ignoreCase = true)
            }
        )
    }

    @Test
    fun pairSnapshotCollectionsAreDefensiveCopies() {
        val authority = authority("e".repeat(64), "b".repeat(64), "c".repeat(64))
        val consumed = listOf(
            ProductionPairConsumedSession("a".repeat(32), "1".repeat(64)),
            ProductionPairConsumedSession("b".repeat(32), "2".repeat(64)),
        )
        val history = listOf(
            ProductionPairTransitionHistoryEntry("3".repeat(64), "4".repeat(64)),
            ProductionPairTransitionHistoryEntry("5".repeat(64), "6".repeat(64)),
        )
        val snapshot = ProductionPairStateSnapshot(authority, 3uL, consumed, history)
        val canonical = snapshot.canonicalBytes()

        (snapshot.consumedEntries as MutableList).clear()
        (snapshot.transitionHistory as MutableList).clear()

        assertEquals(consumed, snapshot.consumedEntries)
        assertEquals(history, snapshot.transitionHistory)
        assertArrayEquals(canonical, snapshot.canonicalBytes())
    }

    @Test
    fun strictCanonicalDerRejectsHighSAndTrailingMutation() {
        val root = privateKey(4)
        val statusKey = privateKey(5)
        val keyset = keyset(
            root,
            1uL,
            null,
            listOf(delegated(statusKey, 1uL, ProductionC1DelegatedKeyPurpose.PAIR_STATUS)),
        )
        val highS = makeHighS(keyset.rootSignature)
        assertC1Error(ProductionC1Error.HIGH_S) {
            ProductionC1ServiceKeyset.decode(replacingLastTLVField(keyset.canonicalBytes(), highS))
        }
        assertC1Error(ProductionC1Error.MALFORMED_CANONICAL) {
            ProductionC1ServiceKeyset.decode(keyset.canonicalBytes() + 0)
        }
    }

    @Test
    fun pairStatusBindsNonceEvidenceHistoryPurposeAndExplicitExpiry() {
        val fixture = fixture()
        val evidence = "e".repeat(64)
        val authority = authority(evidence, fixture.clientFingerprint, fixture.runtimeFingerprint)
        val status = ProductionC1PairStatus.signed(
            serviceId, 1uL, now - 100uL, now + 10_000uL, ProductionC1RequesterRole.CLIENT,
            "9".repeat(64), ProductionC1TransitionKind.GENESIS, null,
            ProductionC1AuthorizationEvidenceKind.INITIAL_PAIRING, evidence, authority, emptyList(),
            publicKey(fixture.statusKey), fixture.statusKey,
        )
        val verified = ProductionC1Verifier.verifyPairStatus(
            status, serviceId, ProductionC1RequesterRole.CLIENT, "9".repeat(64), null,
            fixture.verifiedKeyset, now,
        )
        assertC1Error(ProductionC1Error.STATE_MISMATCH) {
            VerifiedProductionC1PairStatus(status, fixture.verifiedKeyset, Any())
        }
        assertEquals(authority, verified.status.authority)
        val currentGenesis = ProductionPairStateSnapshot(authority, 1uL)
        assertEquals(
            authority,
            ProductionC1Verifier.verifyPairStatus(
                status,
                serviceId,
                ProductionC1RequesterRole.CLIENT,
                "9".repeat(64),
                currentGenesis,
                fixture.verifiedKeyset,
                now,
            ).status.authority,
        )
        assertEquals(status, ProductionC1PairStatus.decode(status.canonicalBytes()))

        assertC1Error(ProductionC1Error.STATE_MISMATCH) {
            ProductionC1Verifier.verifyPairStatus(
                status, serviceId, ProductionC1RequesterRole.RUNTIME, "9".repeat(64), null,
                fixture.verifiedKeyset, now,
            )
        }
        val expired = ProductionC1PairStatus.signed(
            serviceId, 1uL, now - 1_000uL, now, ProductionC1RequesterRole.CLIENT,
            "9".repeat(64), ProductionC1TransitionKind.GENESIS, null,
            ProductionC1AuthorizationEvidenceKind.INITIAL_PAIRING, evidence, authority, emptyList(),
            publicKey(fixture.statusKey), fixture.statusKey,
        )
        assertC1Error(ProductionC1Error.EXPIRED) {
            ProductionC1Verifier.verifyPairStatus(
                expired, serviceId, ProductionC1RequesterRole.CLIENT, "9".repeat(64), null,
                fixture.verifiedKeyset, now,
            )
        }
    }

    @Test
    fun revocationStatusAllowsExactAlreadyCurrentReconciliation() {
        val fixture = fixture()
        val previous = authority("e".repeat(64), fixture.clientFingerprint, fixture.runtimeFingerprint)
        val evidence = "f".repeat(64)
        val revoked = ProductionPairAuthorityState(
            previous.pairBindingDigest,
            previous.pairEpoch,
            previous.clientIdentityFingerprint,
            previous.runtimeIdentityFingerprint,
            previous.generation,
            previous.serviceConfigVersion,
            previous.keysetVersion,
            previous.revocationCounter + 1uL,
            previous.protocolFloor,
            ProductionPairAuthorityStatus.REVOKED,
            "3".repeat(64),
            "4".repeat(64),
            evidence,
            previous.authorityRevision + 1uL,
        )
        val history = listOf(
            ProductionPairTransitionHistoryEntry(
                previous.transitionId,
                previous.transitionRequestDigest,
            )
        )
        val status = ProductionC1PairStatus.signed(
            serviceId,
            1uL,
            now - 100uL,
            now + 10_000uL,
            ProductionC1RequesterRole.CLIENT,
            "9".repeat(64),
            ProductionC1TransitionKind.REVOKE,
            previous.digestHex(),
            ProductionC1AuthorizationEvidenceKind.DENY_ONLY_REVOCATION,
            evidence,
            revoked,
            history,
            publicKey(fixture.statusKey),
            fixture.statusKey,
        )
        ProductionC1Verifier.verifyPairStatus(
            status,
            serviceId,
            ProductionC1RequesterRole.CLIENT,
            "9".repeat(64),
            ProductionPairStateSnapshot(previous, 1uL),
            fixture.verifiedKeyset,
            now,
        )
        val currentRevoked = ProductionPairStateSnapshot(
            revoked,
            2uL,
            transitionHistory = history,
        )
        assertEquals(
            revoked,
            ProductionC1Verifier.verifyPairStatus(
                status,
                serviceId,
                ProductionC1RequesterRole.CLIENT,
                "9".repeat(64),
                currentRevoked,
                fixture.verifiedKeyset,
                now,
            ).status.authority,
        )
    }

    @Test
    fun verifiedRoutePlanUsesSwiftByteExactConnectorOneWayDagAndExactSecrets() {
        val fixture = fixture()
        val authority = authority("e".repeat(64), fixture.clientFingerprint, fixture.runtimeFingerprint)
        val pathDigest = "7".repeat(64)
        val routeHandle = "relay-01"
        val nonce = "nonce-01"
        val secret = ByteArray(32) { 0x5a }
        val sessionId = "a".repeat(32)
        val clientEphemeral = x963(publicKey(privateKey(30)))
        val runtimeEphemeral = x963(publicKey(privateKey(31)))
        val clientNonce = "b".repeat(32)
        val runtimeNonce = "c".repeat(32)
        val securityContext = ProductionC1PreauthorizationSessionContext(
            sessionId,
            authority.pairBindingDigest,
            authority.pairEpoch,
            authority.clientIdentityFingerprint,
            authority.runtimeIdentityFingerprint,
            clientEphemeral,
            runtimeEphemeral,
            clientNonce,
            runtimeNonce,
            authority.generation,
            authority.serviceConfigVersion,
            authority.keysetVersion,
            authority.revocationCounter,
            ProductionC1RouteKind.TURN_RELAY,
        )
        assertEquals(
            securityContext,
            ProductionC1PreauthorizationSessionContext.decode(securityContext.canonicalBytes()),
        )
        val handleDigest = ProductionC1RouteCommitments.routeHandleDigest(
            ProductionC1RouteKind.TURN_RELAY,
            routeHandle,
        )
        val credentialDigest = ProductionC1RouteCommitments.credentialCommitmentDigest(
            ProductionC1RouteKind.TURN_RELAY,
            routeHandle,
            nonce,
            secret,
        )
        assertEquals(SWIFT_ROUTE_HANDLE_DIGEST, handleDigest)
        assertEquals(SWIFT_CREDENTIAL_DIGEST, credentialDigest)

        val connector = ProductionC1RouteConnectorMaterial(
            ProductionC1RouteKind.TURN_RELAY, byteArrayOf(127, 0, 0, 1), 443u,
            "relay.example", ProductionC1RouteTransport.TLS_TCP, handleDigest, credentialDigest,
            pathDigest, "6".repeat(64), "8".repeat(64),
        )
        assertArrayEquals(SWIFT_CONNECTOR_HEX.hexBytes(), connector.canonicalBytes())
        assertEquals(connector, ProductionC1RouteConnectorMaterial.decode(connector.canonicalBytes()))
        val p2pConnector = ProductionC1RouteConnectorMaterial(
            ProductionC1RouteKind.P2P_DIRECT, byteArrayOf(127, 0, 0, 1), 43170u,
            null, ProductionC1RouteTransport.UDP,
            ProductionC1RouteCommitments.routeHandleDigest(ProductionC1RouteKind.P2P_DIRECT, routeHandle),
            ProductionC1RouteCommitments.credentialCommitmentDigest(
                ProductionC1RouteKind.P2P_DIRECT, routeHandle, nonce, secret,
            ),
            pathDigest,
        )
        val sealedConnector = ProductionC1RouteConnectorMaterial(
            ProductionC1RouteKind.SEALED_RELAY, ByteArray(16).also { it[15] = 1 }, 443u,
            "relay.example", ProductionC1RouteTransport.TLS_TCP,
            ProductionC1RouteCommitments.routeHandleDigest(ProductionC1RouteKind.SEALED_RELAY, routeHandle),
            ProductionC1RouteCommitments.credentialCommitmentDigest(
                ProductionC1RouteKind.SEALED_RELAY, routeHandle, nonce, secret,
            ),
            pathDigest, "6".repeat(64), "8".repeat(64),
        )
        listOf(p2pConnector, connector, sealedConnector).forEach { material ->
            assertEquals(material, ProductionC1RouteConnectorMaterial.decode(material.canonicalBytes()))
            assertEquals(material.kind.connectorObjectType, material.canonicalBytes()[4].toInt() and 0xff)
        }
        val claims = ProductionC1RoutePlanClaims(
            "1".repeat(64), ProductionC1RouteKind.TURN_RELAY, authority.digestHex(),
            authority.pairBindingDigest, authority.pairEpoch, authority.generation,
            authority.clientIdentityFingerprint, authority.runtimeIdentityFingerprint, connector,
            securityContext.digestHex(), pathDigest, now - 10uL, now + 20_000uL,
        )
        assertEquals(claims, ProductionC1RoutePlanClaims.decode(claims.canonicalBytes()))
        val capability = ProductionC1RouteCapability.signed(
            serviceId, 1uL, "3".repeat(64), now - 100uL, now - 10uL, now + 30_000uL,
            authority, ProductionC1RouteKind.TURN_RELAY, claims.digestHex(),
            publicKey(fixture.routeKey), fixture.routeKey,
        )
        val plan = ProductionC1Verifier.verifyRoutePlan(
            claims, capability, securityContext, authority, fixture.verifiedKeyset, now,
        )
        assertC1Error(ProductionC1Error.STATE_MISMATCH) {
            VerifiedProductionC1RouteCapability(capability, Any())
        }
        assertC1Error(ProductionC1Error.STATE_MISMATCH) {
            VerifiedProductionC1RoutePlan(
                plan.claims,
                plan.capability,
                plan.securityContext,
                plan.authorityDigest,
                plan.capabilityDigest,
                plan.claimsDigest,
                plan.verifiedKeyset,
                Any(),
            )
        }
        assertEquals(connector, plan.connectorMaterial)
        assertEquals(claims.digestHex(), plan.claimsDigest)
        assertEquals(capability.digestHex(), plan.capabilityDigest)
        val alteredEphemeralContext = ProductionC1PreauthorizationSessionContext(
            sessionId,
            authority.pairBindingDigest,
            authority.pairEpoch,
            authority.clientIdentityFingerprint,
            authority.runtimeIdentityFingerprint,
            x963(publicKey(privateKey(32))),
            runtimeEphemeral,
            clientNonce,
            runtimeNonce,
            authority.generation,
            authority.serviceConfigVersion,
            authority.keysetVersion,
            authority.revocationCounter,
            ProductionC1RouteKind.TURN_RELAY,
        )
        assertC1Error(ProductionC1Error.ROUTE_MISMATCH) {
            ProductionC1Verifier.verifyRoutePlan(
                claims,
                capability,
                alteredEphemeralContext,
                authority,
                fixture.verifiedKeyset,
                now,
            )
        }

        val connectorInput = ProductionC1Verifier.verifyConnectorInput(
            plan, routeHandle, nonce, secret, now,
        )
        assertC1Error(ProductionC1Error.STATE_MISMATCH) {
            VerifiedProductionC1ConnectorInput(
                routeHandle,
                nonce,
                secret,
                connector,
                connectorInput.commitmentDigest,
                Any(),
            )
        }
        assertEquals(routeHandle, connectorInput.routeHandle)
        assertArrayEquals(secret, connectorInput.secret)
        assertC1Error(ProductionC1Error.ROUTE_MISMATCH) {
            ProductionC1Verifier.verifyConnectorInput(
                plan,
                routeHandle,
                nonce,
                ByteArray(32) { 0x5b },
                now,
            )
        }

        val routeAuthorization = ProductionC1Verifier.makeRouteAuthorization(plan, now)
        assertC1Error(ProductionC1Error.STATE_MISMATCH) {
            VerifiedProductionC1RouteAuthorization(routeAuthorization.authorization, Any())
        }
        assertEquals(ProductionC1RouteKind.TURN_RELAY, routeAuthorization.kind)
        assertEquals(claims.digestHex(), routeAuthorization.authorization.routePlanClaimsDigest)
        assertEquals(capability.digestHex(), routeAuthorization.authorization.routeCapabilityDigest)
        assertEquals(
            routeAuthorization.authorization,
            ProductionC1RouteAuthorization.decode(routeAuthorization.canonicalBytes),
        )
        listOf(
            ProductionC1RouteKind.P2P_DIRECT,
            ProductionC1RouteKind.TURN_RELAY,
            ProductionC1RouteKind.SEALED_RELAY,
        ).forEach { kind ->
            val bytes = routeAuthorization.canonicalBytes.also {
                it[4] = kind.authorizationObjectType.toByte()
            }
            val decoded = ProductionC1RouteAuthorization.decode(bytes)
            assertEquals(kind, decoded.kind)
            assertArrayEquals(bytes, decoded.canonicalBytes())
        }

        val transcript = ProductionSecureSessionTranscript(
            sessionId, authority.pairBindingDigest, authority.pairEpoch,
            authority.clientIdentityFingerprint, authority.runtimeIdentityFingerprint,
            clientEphemeral, runtimeEphemeral,
            clientNonce, runtimeNonce, authority.generation, authority.serviceConfigVersion,
            authority.keysetVersion, authority.revocationCounter,
            routeAuthorizationKind = ProductionRouteAuthorizationKind.TURN_RELAY,
            routeAuthorizationDigest = routeAuthorization.digestHex,
        )
        val binding = ProductionC1Verifier.verifyTranscriptBinding(
            transcript, routeAuthorization, plan, connectorInput, authority, now,
        )
        assertC1Error(ProductionC1Error.STATE_MISMATCH) {
            VerifiedProductionC1TranscriptBinding(
                transcript,
                routeAuthorization,
                plan,
                connectorInput,
                securityContext,
                Any(),
            )
        }
        assertEquals(routeAuthorization, binding.authorization)
        assertEquals(plan, binding.plan)
        assertEquals(connectorInput.commitmentDigest, binding.connectorInput.commitmentDigest)
        val reusedForAnotherSession = ProductionSecureSessionTranscript(
            "d".repeat(32),
            authority.pairBindingDigest,
            authority.pairEpoch,
            authority.clientIdentityFingerprint,
            authority.runtimeIdentityFingerprint,
            clientEphemeral,
            runtimeEphemeral,
            clientNonce,
            runtimeNonce,
            authority.generation,
            authority.serviceConfigVersion,
            authority.keysetVersion,
            authority.revocationCounter,
            routeAuthorizationKind = ProductionRouteAuthorizationKind.TURN_RELAY,
            routeAuthorizationDigest = routeAuthorization.digestHex,
        )
        assertC1Error(ProductionC1Error.ROUTE_MISMATCH) {
            ProductionC1Verifier.verifyTranscriptBinding(
                reusedForAnotherSession,
                routeAuthorization,
                plan,
                connectorInput,
                authority,
                now,
            )
        }

        val admitted = ProductionC1PairStateAdmission.admit(
            binding,
            ProductionPairStateSnapshot(authority, 1uL),
        )
        assertEquals(2uL, admitted.nextSnapshot.localRevision)
        assertEquals(1, admitted.nextSnapshot.consumedEntries.size)
        assertEquals(64, admitted.bindingDigest.length)
        assertEquals(transcript.sessionId, admitted.sessionId)
        assertEquals(claims.notBeforeMs, admitted.effectiveNotBeforeMs)
        assertEquals(claims.expiresAtMs, admitted.expiresAtMs)
        assertTrue(
            ProductionC1PairStateAdmission::class.java.methods.none {
                it.returnType.simpleName.contains("Permit")
            }
        )
        assertPairStateError(ProductionPairStateRejectionReason.SESSION_REPLAY) {
            ProductionC1PairStateAdmission.admit(binding, admitted.nextSnapshot)
        }
        assertC1Error(ProductionC1Error.EXPIRED) {
            ProductionC1Verifier.makeRouteAuthorization(plan, claims.expiresAtMs)
        }
        assertC1Error(ProductionC1Error.EXPIRED) {
            ProductionC1Verifier.verifyConnectorInput(
                plan,
                routeHandle,
                nonce,
                secret,
                claims.expiresAtMs,
            )
        }
        assertC1Error(ProductionC1Error.EXPIRED) {
            ProductionC1Verifier.verifyTranscriptBinding(
                transcript,
                routeAuthorization,
                plan,
                connectorInput,
                authority,
                claims.expiresAtMs,
            )
        }
        val expiredNonAuthorizingPreparation = ProductionC1PairStateAdmission.admit(
            binding,
            ProductionPairStateSnapshot(authority, 1uL),
        )
        assertEquals(claims.expiresAtMs, expiredNonAuthorizingPreparation.expiresAtMs)

        val substituted = claims.copy(
            connector = ProductionC1RouteConnectorMaterial(
                ProductionC1RouteKind.TURN_RELAY, byteArrayOf(127, 0, 0, 2), 443u,
                "relay.example", ProductionC1RouteTransport.TLS_TCP, handleDigest, credentialDigest,
                pathDigest, "6".repeat(64), "8".repeat(64),
            ),
        )
        assertC1Error(ProductionC1Error.ROUTE_MISMATCH) {
            ProductionC1Verifier.verifyRoutePlan(
                substituted, capability, securityContext, authority, fixture.verifiedKeyset, now,
            )
        }
    }

    @Test
    fun sealedRelayStillPassesTheFullGenericAdmissionPath() {
        val fixture = fixture()
        val authority = authority(
            "e".repeat(64),
            fixture.clientFingerprint,
            fixture.runtimeFingerprint,
        )
        val clientEphemeral = x963(publicKey(privateKey(80)))
        val runtimeEphemeral = x963(publicKey(privateKey(81)))
        val context = ProductionC1PreauthorizationSessionContext(
            "8".repeat(32),
            authority.pairBindingDigest,
            authority.pairEpoch,
            authority.clientIdentityFingerprint,
            authority.runtimeIdentityFingerprint,
            clientEphemeral,
            runtimeEphemeral,
            "9".repeat(32),
            "a".repeat(32),
            authority.generation,
            authority.serviceConfigVersion,
            authority.keysetVersion,
            authority.revocationCounter,
            ProductionC1RouteKind.SEALED_RELAY,
        )
        val routeHandle = "sealed-route-01"
        val nonce = "sealed-nonce-01"
        val secret = ByteArray(32) { 0x4a }
        val pathDigest = "7".repeat(64)
        val connector = ProductionC1RouteConnectorMaterial(
            ProductionC1RouteKind.SEALED_RELAY,
            byteArrayOf(8, 8, 8, 8),
            443u,
            "relay.example",
            ProductionC1RouteTransport.TLS_TCP,
            ProductionC1RouteCommitments.routeHandleDigest(
                ProductionC1RouteKind.SEALED_RELAY,
                routeHandle,
            ),
            ProductionC1RouteCommitments.credentialCommitmentDigest(
                ProductionC1RouteKind.SEALED_RELAY,
                routeHandle,
                nonce,
                secret,
            ),
            pathDigest,
            "6".repeat(64),
            "8".repeat(64),
        )
        val claims = ProductionC1RoutePlanClaims(
            "5".repeat(64),
            ProductionC1RouteKind.SEALED_RELAY,
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
        val capability = ProductionC1RouteCapability.signed(
            serviceId,
            1uL,
            "4".repeat(64),
            now - 100uL,
            now - 10uL,
            now + 20_000uL,
            authority,
            ProductionC1RouteKind.SEALED_RELAY,
            claims.digestHex(),
            publicKey(fixture.routeKey),
            fixture.routeKey,
        )
        val plan = ProductionC1Verifier.verifyRoutePlan(
            claims,
            capability,
            context,
            authority,
            fixture.verifiedKeyset,
            now,
        )
        val connectorInput = ProductionC1Verifier.verifyConnectorInput(
            plan,
            routeHandle,
            nonce,
            secret,
            now,
        )
        val authorization = ProductionC1Verifier.makeRouteAuthorization(plan, now)
        val transcript = ProductionSecureSessionTranscript(
            context.sessionId,
            context.pairBindingDigest,
            context.pairEpoch,
            context.clientIdentityFingerprint,
            context.runtimeIdentityFingerprint,
            clientEphemeral,
            runtimeEphemeral,
            context.clientNonce,
            context.runtimeNonce,
            context.generation,
            context.serviceConfigVersion,
            context.keysetVersion,
            context.revocationCounter,
            routeAuthorizationKind = ProductionRouteAuthorizationKind.SEALED_RELAY,
            routeAuthorizationDigest = authorization.digestHex,
        )
        val binding = ProductionC1Verifier.verifyTranscriptBinding(
            transcript,
            authorization,
            plan,
            connectorInput,
            authority,
            now,
        )
        val admitted = ProductionC1PairStateAdmission.admit(
            binding,
            ProductionPairStateSnapshot(authority, 1uL),
        )
        assertEquals(ProductionC1RouteKind.SEALED_RELAY, plan.kind)
        assertEquals(ProductionC1RouteKind.SEALED_RELAY, authorization.kind)
        assertEquals(2uL, admitted.nextSnapshot.localRevision)
    }

    @Test
    fun dualSignedFreshPairIsOnlyEpochApplyPreparationPath() {
        val fixture = fixture()
        val oldClient = privateKey(50)
        val survivorRuntime = privateKey(51)
        val replacementClient = privateKey(52)
        val previous = authority(
            "e".repeat(64),
            keyId(publicKey(oldClient)),
            keyId(publicKey(survivorRuntime)),
        ).copy(authorityRevision = 3uL)
        val priorHistory = listOf(
            ProductionPairTransitionHistoryEntry("a".repeat(64), "b".repeat(64)),
            ProductionPairTransitionHistoryEntry("c".repeat(64), "d".repeat(64)),
        )
        val current = ProductionPairStateSnapshot(
            previous,
            1uL,
            transitionHistory = priorHistory,
        )
        val previousEndpointSecret = ByteArray(32) { 0x11 }
        val previousRouteSeed = ByteArray(32) { 0x12 }
        val nextEndpointSecret = ByteArray(32) { 0x13 }
        val nextRouteSeed = ByteArray(32) { 0x14 }
        val currentCommitments = ProductionC1RecoveryCommitments.currentToken(
            previous.pairBindingDigest,
            previousEndpointSecret,
            previousRouteSeed,
        )
        val proof = ProductionC1FreshPairProof.signed(
            transitionId = "f".repeat(64),
            replacementRole = ProductionC1ReplacementRole.CLIENT,
            previousAuthority = previous,
            nextClientIdentityFingerprint = keyId(publicKey(replacementClient)),
            nextRuntimeIdentityFingerprint = keyId(publicKey(survivorRuntime)),
            nextGeneration = previous.generation + 1uL,
            nextServiceConfigVersion = previous.serviceConfigVersion,
            nextKeysetVersion = previous.keysetVersion,
            nextRevocationCounter = previous.revocationCounter,
            nextProtocolFloor = previous.protocolFloor,
            issuedAtMs = now - 100uL,
            expiresAtMs = now + 10_000uL,
            freshPairingRequestDigest = "3".repeat(64),
            freshPairingResultDigest = "4".repeat(64),
            freshTransportBindingDigest = "5".repeat(64),
            currentCommitments = currentCommitments,
            nextEndpointTrafficSecret = nextEndpointSecret,
            nextRouteTokenSeed = nextRouteSeed,
            survivorPublicKey = publicKey(survivorRuntime),
            survivorPrivateKey = survivorRuntime,
            replacementPublicKey = publicKey(replacementClient),
            replacementPrivateKey = replacementClient,
        )
        assertC1Error(ProductionC1Error.INVALID_FRESH_PAIR) {
            ProductionC1FreshPairProof.signed(
                transitionId = "6".repeat(64),
                replacementRole = ProductionC1ReplacementRole.CLIENT,
                previousAuthority = previous,
                nextClientIdentityFingerprint = keyId(publicKey(replacementClient)),
                nextRuntimeIdentityFingerprint = keyId(publicKey(survivorRuntime)),
                nextGeneration = previous.generation + 1uL,
                nextServiceConfigVersion = previous.serviceConfigVersion,
                nextKeysetVersion = previous.keysetVersion,
                nextRevocationCounter = previous.revocationCounter,
                nextProtocolFloor = previous.protocolFloor,
                issuedAtMs = now - 100uL,
                expiresAtMs = now + 10_000uL,
                freshPairingRequestDigest = "3".repeat(64),
                freshPairingResultDigest = "4".repeat(64),
                freshTransportBindingDigest = "5".repeat(64),
                currentCommitments = currentCommitments,
                nextEndpointTrafficSecret = previousEndpointSecret,
                nextRouteTokenSeed = nextRouteSeed,
                survivorPublicKey = publicKey(survivorRuntime),
                survivorPrivateKey = survivorRuntime,
                replacementPublicKey = publicKey(replacementClient),
                replacementPrivateKey = replacementClient,
            )
        }
        assertC1Error(ProductionC1Error.INVALID_FRESH_PAIR) {
            ProductionC1FreshPairProof.signed(
                transitionId = "7".repeat(64),
                replacementRole = ProductionC1ReplacementRole.CLIENT,
                previousAuthority = previous,
                nextClientIdentityFingerprint = keyId(publicKey(replacementClient)),
                nextRuntimeIdentityFingerprint = keyId(publicKey(survivorRuntime)),
                nextGeneration = previous.generation + 1uL,
                nextServiceConfigVersion = previous.serviceConfigVersion,
                nextKeysetVersion = previous.keysetVersion,
                nextRevocationCounter = previous.revocationCounter,
                nextProtocolFloor = previous.protocolFloor,
                issuedAtMs = now - 100uL,
                expiresAtMs = now + 10_000uL,
                freshPairingRequestDigest = "3".repeat(64),
                freshPairingResultDigest = "4".repeat(64),
                freshTransportBindingDigest = "5".repeat(64),
                currentCommitments = currentCommitments,
                nextEndpointTrafficSecret = nextEndpointSecret,
                nextRouteTokenSeed = nextEndpointSecret,
                survivorPublicKey = publicKey(survivorRuntime),
                survivorPrivateKey = survivorRuntime,
                replacementPublicKey = publicKey(replacementClient),
                replacementPrivateKey = replacementClient,
            )
        }
        val next = ProductionPairAuthorityState(
            proof.nextPairBindingDigest,
            proof.nextPairEpoch,
            proof.nextClientIdentityFingerprint,
            proof.nextRuntimeIdentityFingerprint,
            proof.nextGeneration,
            proof.nextServiceConfigVersion,
            proof.nextKeysetVersion,
            proof.nextRevocationCounter,
            proof.nextProtocolFloor,
            ProductionPairAuthorityStatus.ACTIVE,
            proof.transitionId,
            proof.transitionRequestDigest,
            proof.digestHex(),
            proof.nextAuthorityRevision,
        )
        val history = priorHistory + listOf(
            ProductionPairTransitionHistoryEntry(
                previous.transitionId,
                previous.transitionRequestDigest,
            )
        )
        val status = ProductionC1PairStatus.signed(
            serviceId,
            1uL,
            now - 50uL,
            now + 10_000uL,
            ProductionC1RequesterRole.RUNTIME,
            "9".repeat(64),
            ProductionC1TransitionKind.FRESH_PAIR,
            previous.digestHex(),
            ProductionC1AuthorizationEvidenceKind.DUAL_SIGNED_FRESH_PAIR,
            proof.digestHex(),
            next,
            history,
            publicKey(fixture.statusKey),
            fixture.statusKey,
        )
        val verifiedStatus = ProductionC1Verifier.verifyPairStatus(
            status,
            serviceId,
            ProductionC1RequesterRole.RUNTIME,
            "9".repeat(64),
            current,
            fixture.verifiedKeyset,
            now,
        )
        (verifiedStatus.status.transitionHistory as MutableList).clear()
        assertEquals(history, verifiedStatus.status.transitionHistory)
        val wrongCurrentCommitments = ProductionC1RecoveryCommitments.currentToken(
            previous.pairBindingDigest,
            ByteArray(32) { 0x21 },
            ByteArray(32) { 0x22 },
        )
        assertC1Error(ProductionC1Error.INVALID_FRESH_PAIR) {
            ProductionC1Verifier.verifyFreshPairProof(
                proof,
                verifiedStatus,
                current,
                wrongCurrentCommitments,
                publicKey(survivorRuntime),
                publicKey(replacementClient),
                now,
            )
        }
        val verified = ProductionC1Verifier.verifyFreshPairProof(
            proof,
            verifiedStatus,
            current,
            currentCommitments,
            publicKey(survivorRuntime),
            publicKey(replacementClient),
            now,
        )
        assertC1Error(ProductionC1Error.STATE_MISMATCH) {
            VerifiedProductionC1FreshPairTransition(
                proof,
                verifiedStatus,
                verified.applyPreparation,
                Any(),
            )
        }
        (verified.applyPreparation.nextTransitionHistory as MutableList).clear()
        (verified.applyPreparation.nextSnapshot.transitionHistory as MutableList).clear()
        assertEquals(history, verified.applyPreparation.nextTransitionHistory)
        assertEquals(history, verified.applyPreparation.nextSnapshot.transitionHistory)
        assertEquals(next, verified.applyPreparation.nextAuthority)
        assertEquals(proof.previousPairBindingDigest, proof.nextPairBindingDigest)
        assertTrue(
            proof.previousEndpointTrafficSecretReuseDigest !=
                proof.nextEndpointTrafficSecretReuseDigest
        )
        assertEquals(proof, ProductionC1FreshPairProof.decode(proof.canonicalBytes()))

        val qrMutatedProof = ProductionC1FreshPairProof.decode(
            replacingTLVFields(
                proof.canonicalBytes(),
                mapOf(21 to "a".repeat(64).toByteArray(Charsets.US_ASCII)),
            )
        )
        assertC1Error(ProductionC1Error.INVALID_SIGNATURE) {
            ProductionC1Verifier.verifyFreshPairProof(
                qrMutatedProof,
                verifiedStatus,
                current,
                currentCommitments,
                publicKey(survivorRuntime),
                publicKey(replacementClient),
                now,
            )
        }
        assertPairStateError(ProductionPairStateRejectionReason.INVALID_EPOCH_TRANSITION) {
            ProductionPairStateMachine.apply(
                ProductionPairStateTransition(previous.digestHex(), next),
                current,
            )
        }
        val applied = ProductionC1FreshPairStateMachine.apply(verified, current, now)
        assertEquals(next, applied.snapshot.authority)
        assertEquals(history, applied.snapshot.transitionHistory)
        assertTrue(applied.snapshot.consumedEntries.isEmpty())
        assertEquals(
            next,
            ProductionC1Verifier.verifyPairStatus(
                status,
                serviceId,
                ProductionC1RequesterRole.RUNTIME,
                "9".repeat(64),
                applied.snapshot,
                fixture.verifiedKeyset,
                now,
            ).status.authority,
        )
        val idempotent = ProductionC1FreshPairStateMachine.apply(verified, applied.snapshot, now)
        assertEquals(ProductionPairStateTransitionDisposition.IDEMPOTENT, idempotent.disposition)
        assertEquals(applied.snapshot, idempotent.snapshot)
        assertC1Error(ProductionC1Error.EXPIRED) {
            ProductionC1FreshPairStateMachine.apply(verified, current, proof.expiresAtMs)
        }

        val wrongSignerProof = ProductionC1FreshPairProof.signed(
            transitionId = proof.transitionId,
            replacementRole = proof.replacementRole,
            previousAuthority = previous,
            nextClientIdentityFingerprint = proof.nextClientIdentityFingerprint,
            nextRuntimeIdentityFingerprint = proof.nextRuntimeIdentityFingerprint,
            nextGeneration = proof.nextGeneration,
            nextServiceConfigVersion = proof.nextServiceConfigVersion,
            nextKeysetVersion = proof.nextKeysetVersion,
            nextRevocationCounter = proof.nextRevocationCounter,
            nextProtocolFloor = proof.nextProtocolFloor,
            issuedAtMs = proof.issuedAtMs,
            expiresAtMs = proof.expiresAtMs,
            freshPairingRequestDigest = proof.freshPairingRequestDigest,
            freshPairingResultDigest = proof.freshPairingResultDigest,
            freshTransportBindingDigest = proof.freshTransportBindingDigest,
            currentCommitments = currentCommitments,
            nextEndpointTrafficSecret = nextEndpointSecret,
            nextRouteTokenSeed = nextRouteSeed,
            survivorPublicKey = publicKey(oldClient),
            survivorPrivateKey = oldClient,
            replacementPublicKey = publicKey(replacementClient),
            replacementPrivateKey = replacementClient,
        )
        assertC1Error(ProductionC1Error.INVALID_SIGNATURE) {
            ProductionC1Verifier.verifyFreshPairProof(
                wrongSignerProof,
                verifiedStatus,
                current,
                currentCommitments,
                publicKey(survivorRuntime),
                publicKey(replacementClient),
                now,
            )
        }
        assertC1Error(ProductionC1Error.INVALID_FRESH_PAIR) {
            ProductionC1FreshPairProof.decode(
                replacingTLVFields(
                    proof.canonicalBytes(),
                    mapOf(8 to be(proof.previousPairEpoch + 2uL)),
                )
            )
        }
        val swappedProof = ProductionC1FreshPairProof.decode(
            replacingTLVFields(
                proof.canonicalBytes(),
                mapOf(35 to proof.replacementSignature, 36 to proof.survivorSignature),
            )
        )
        assertC1Error(ProductionC1Error.INVALID_SIGNATURE) {
            ProductionC1Verifier.verifyFreshPairProof(
                swappedProof,
                verifiedStatus,
                current,
                currentCommitments,
                publicKey(survivorRuntime),
                publicKey(replacementClient),
                now,
            )
        }
    }

    @Test
    fun routeCapabilityRejectsWrongPurposeAndObjectNamespaceRemainsDisjoint() {
        val root = privateKey(20)
        val statusOnly = privateKey(21)
        val authority = authority("e".repeat(64), "b".repeat(64), "c".repeat(64))
        val verified = ProductionC1Verifier.verifyServiceKeyset(
            keyset(
                root, 1uL, null,
                listOf(delegated(statusOnly, 1uL, ProductionC1DelegatedKeyPurpose.PAIR_STATUS)),
            ),
            serviceId,
            publicKey(root),
            1uL,
            nowMs = now,
        )
        val capability = ProductionC1RouteCapability.signed(
            serviceId, 1uL, "3".repeat(64), now - 100uL, now - 10uL, now + 100uL,
            authority, ProductionC1RouteKind.P2P_DIRECT, "4".repeat(64),
            publicKey(statusOnly), statusOnly,
        )
        assertC1Error(ProductionC1Error.KEY_PURPOSE_MISMATCH) {
            ProductionC1Verifier.verifyRouteCapability(capability, authority, verified, now)
        }
        assertEquals(10, ProductionC1Contract.SERVICE_KEYSET_OBJECT_TYPE)
        assertEquals(14, ProductionC1Contract.ROUTE_PLAN_OBJECT_TYPE)
        assertEquals(12, ProductionC1Contract.FRESH_PAIR_PROOF_OBJECT_TYPE)
        assertEquals(18, ProductionC1Contract.PREAUTHORIZATION_SESSION_CONTEXT_OBJECT_TYPE)
        assertEquals(30_000uL, ProductionC1Contract.MAXIMUM_CLOCK_SKEW_MS)
        assertEquals(600_000uL, ProductionC1Contract.MAXIMUM_ROUTE_LIFETIME_MS)
        assertTrue((1..9).none { it == ProductionC1Contract.SERVICE_KEYSET_OBJECT_TYPE })
    }

    @Test
    fun firstTrustRequiresRollbackFloorAndExpiryBoundaryIsExclusive() {
        val root = privateKey(40)
        val delegatedKey = privateKey(41)
        val versionTwo = keyset(
            root,
            2uL,
            "1".repeat(64),
            listOf(delegated(delegatedKey, 2uL, ProductionC1DelegatedKeyPurpose.PAIR_STATUS)),
        )
        assertEquals(
            2uL,
            ProductionC1Verifier.verifyServiceKeyset(
                versionTwo,
                serviceId,
                publicKey(root),
                2uL,
                nowMs = now,
            ).keyset.keysetVersion,
        )
        assertC1Error(ProductionC1Error.KEYSET_ROLLBACK) {
            ProductionC1Verifier.verifyServiceKeyset(
                versionTwo,
                serviceId,
                publicKey(root),
                3uL,
                nowMs = now,
            )
        }

        val expiringDelegated = ProductionC1DelegatedKey(
            1uL,
            keyId(publicKey(delegatedKey)),
            ProductionC1DelegatedKeyPurpose.PAIR_STATUS,
            now - 1_000uL,
            now,
            publicKeyX963 = x963(publicKey(delegatedKey)),
        )
        val expiring = ProductionC1ServiceKeyset.signed(
            serviceId,
            1uL,
            null,
            now - 1_000uL,
            now,
            listOf(expiringDelegated),
            publicKey(root),
            root,
        )
        assertC1Error(ProductionC1Error.EXPIRED) {
            ProductionC1Verifier.verifyServiceKeyset(
                expiring,
                serviceId,
                publicKey(root),
                1uL,
                nowMs = now,
            )
        }

        val first = keyset(
            root,
            1uL,
            null,
            listOf(delegated(delegatedKey, 1uL, ProductionC1DelegatedKeyPurpose.PAIR_STATUS)),
        )
        val verifiedFirst = ProductionC1Verifier.verifyServiceKeyset(
            first,
            serviceId,
            publicKey(root),
            1uL,
            nowMs = now,
        )
        assertC1Error(ProductionC1Error.KEYSET_ROLLBACK) {
            ProductionC1Verifier.verifyServiceKeyset(
                first,
                serviceId,
                publicKey(root),
                1uL,
                verifiedFirst,
                now,
            )
        }
        val reordered = first.canonicalBytes().also { it[6] = 2 }
        assertC1Error(ProductionC1Error.MALFORMED_CANONICAL) {
            ProductionC1ServiceKeyset.decode(reordered)
        }
    }

    @Test
    fun cachedKeysetAndDelegatedValidityAreRecheckedAtUse() {
        val root = privateKey(60)
        val online = privateKey(61)
        val onlinePublic = publicKey(online)
        val delegatedKey = ProductionC1DelegatedKey(
            1uL,
            keyId(onlinePublic),
            ProductionC1DelegatedKeyPurpose.ALLOWED,
            now - 1_000uL,
            now + 100uL,
            publicKeyX963 = x963(onlinePublic),
        )
        val keyset = ProductionC1ServiceKeyset.signed(
            serviceId,
            1uL,
            null,
            now - 1_000uL,
            now + 200uL,
            listOf(delegatedKey),
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
        val evidence = "e".repeat(64)
        val authority = authority(evidence, "b".repeat(64), "c".repeat(64))
        val status = ProductionC1PairStatus.signed(
            serviceId,
            1uL,
            now,
            now + 1_000uL,
            ProductionC1RequesterRole.CLIENT,
            "9".repeat(64),
            ProductionC1TransitionKind.GENESIS,
            null,
            ProductionC1AuthorizationEvidenceKind.INITIAL_PAIRING,
            evidence,
            authority,
            emptyList(),
            onlinePublic,
            online,
        )
        ProductionC1Verifier.verifyPairStatus(
            status,
            serviceId,
            ProductionC1RequesterRole.CLIENT,
            "9".repeat(64),
            null,
            verifiedKeyset,
            now,
        )
        assertC1Error(ProductionC1Error.EXPIRED) {
            ProductionC1Verifier.verifyPairStatus(
                status,
                serviceId,
                ProductionC1RequesterRole.CLIENT,
                "9".repeat(64),
                null,
                verifiedKeyset,
                delegatedKey.expiresAtMs,
            )
        }
        assertC1Error(ProductionC1Error.EXPIRED) {
            ProductionC1Verifier.verifyPairStatus(
                status,
                serviceId,
                ProductionC1RequesterRole.CLIENT,
                "9".repeat(64),
                null,
                verifiedKeyset,
                keyset.expiresAtMs,
            )
        }
        val capability = ProductionC1RouteCapability.signed(
            serviceId,
            1uL,
            "3".repeat(64),
            now,
            now,
            now + 1_000uL,
            authority,
            ProductionC1RouteKind.P2P_DIRECT,
            "4".repeat(64),
            onlinePublic,
            online,
        )
        ProductionC1Verifier.verifyRouteCapability(capability, authority, verifiedKeyset, now)
        assertC1Error(ProductionC1Error.EXPIRED) {
            ProductionC1Verifier.verifyRouteCapability(
                capability,
                authority,
                verifiedKeyset,
                delegatedKey.expiresAtMs,
            )
        }
        assertC1Error(ProductionC1Error.EXPIRED) {
            ProductionC1Verifier.verifyRouteCapability(
                capability,
                authority,
                verifiedKeyset,
                keyset.expiresAtMs,
            )
        }

        val routeHandle = "direct-01"
        val nonce = "nonce-01"
        val secret = ByteArray(32) { 0x31 }
        val pathDigest = "7".repeat(64)
        val context = ProductionC1PreauthorizationSessionContext(
            "a".repeat(32),
            authority.pairBindingDigest,
            authority.pairEpoch,
            authority.clientIdentityFingerprint,
            authority.runtimeIdentityFingerprint,
            x963(publicKey(privateKey(62))),
            x963(publicKey(privateKey(63))),
            "d".repeat(32),
            "f".repeat(32),
            authority.generation,
            authority.serviceConfigVersion,
            authority.keysetVersion,
            authority.revocationCounter,
            ProductionC1RouteKind.P2P_DIRECT,
        )
        val connector = ProductionC1RouteConnectorMaterial(
            ProductionC1RouteKind.P2P_DIRECT,
            byteArrayOf(127, 0, 0, 1),
            43170u,
            null,
            ProductionC1RouteTransport.UDP,
            ProductionC1RouteCommitments.routeHandleDigest(
                ProductionC1RouteKind.P2P_DIRECT,
                routeHandle,
            ),
            ProductionC1RouteCommitments.credentialCommitmentDigest(
                ProductionC1RouteKind.P2P_DIRECT,
                routeHandle,
                nonce,
                secret,
            ),
            pathDigest,
        )
        val claims = ProductionC1RoutePlanClaims(
            "5".repeat(64),
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
            now,
            now + 1_000uL,
        )
        val planCapability = ProductionC1RouteCapability.signed(
            serviceId,
            1uL,
            "6".repeat(64),
            now,
            now,
            now + 1_000uL,
            authority,
            ProductionC1RouteKind.P2P_DIRECT,
            claims.digestHex(),
            onlinePublic,
            online,
        )
        assertC1Error(ProductionC1Error.ROUTE_MISMATCH) {
            ProductionC1Verifier.verifyRoutePlan(
                claims,
                planCapability,
                context,
                authority,
                verifiedKeyset,
                now,
            )
        }
        val plan = ProductionC1Verifier.verifyCandidateP2PRoutePlanBase(
            claims,
            planCapability,
            context,
            authority,
            verifiedKeyset,
            now,
        )
        ProductionC1Verifier.makeCandidateP2PRouteAuthorizationBase(plan, now)
        assertC1Error(ProductionC1Error.ROUTE_MISMATCH) {
            ProductionC1Verifier.makeRouteAuthorization(plan, now)
        }
        assertC1Error(ProductionC1Error.EXPIRED) {
            ProductionC1Verifier.makeCandidateP2PRouteAuthorizationBase(plan, delegatedKey.expiresAtMs)
        }
        assertC1Error(ProductionC1Error.EXPIRED) {
            ProductionC1Verifier.makeCandidateP2PRouteAuthorizationBase(plan, keyset.expiresAtMs)
        }

        val overlongDelegated = ProductionC1DelegatedKey(
            1uL,
            keyId(onlinePublic),
            ProductionC1DelegatedKeyPurpose.PAIR_STATUS,
            now - 1_000uL,
            now + 201uL,
            publicKeyX963 = x963(onlinePublic),
        )
        assertC1Error(ProductionC1Error.INVALID_VALUE) {
            ProductionC1ServiceKeyset.signed(
                serviceId,
                1uL,
                null,
                now - 1_000uL,
                now + 200uL,
                listOf(overlongDelegated),
                publicKey(root),
                root,
            )
        }
    }

    @Test
    fun candidateDelegatedPurposesExtendAllowedMaskWithoutChangingHistoricalBits() {
        assertEquals(1u, ProductionC1DelegatedKeyPurpose.PAIR_STATUS.rawValue)
        assertEquals(2u, ProductionC1DelegatedKeyPurpose.ROUTE_CAPABILITY.rawValue)
        assertEquals(4u, ProductionC1DelegatedKeyPurpose.CANDIDATE_PUBLISH.rawValue)
        assertEquals(8u, ProductionC1DelegatedKeyPurpose.CANDIDATE_FETCH.rawValue)
        assertEquals(16u, ProductionC1DelegatedKeyPurpose.CANDIDATE_PUBLISH_RECEIPT.rawValue)
        assertEquals(32u, ProductionC1DelegatedKeyPurpose.CANDIDATE_FETCH_RECEIPT.rawValue)
        assertEquals(63u, ProductionC1DelegatedKeyPurpose.ALLOWED.rawValue)
        listOf(
            ProductionC1DelegatedKeyPurpose.PAIR_STATUS,
            ProductionC1DelegatedKeyPurpose.ROUTE_CAPABILITY,
            ProductionC1DelegatedKeyPurpose.CANDIDATE_PUBLISH,
            ProductionC1DelegatedKeyPurpose.CANDIDATE_FETCH,
            ProductionC1DelegatedKeyPurpose.CANDIDATE_PUBLISH_RECEIPT,
            ProductionC1DelegatedKeyPurpose.CANDIDATE_FETCH_RECEIPT,
        ).forEach { purpose ->
            assertTrue(ProductionC1DelegatedKeyPurpose.ALLOWED.contains(purpose))
        }

        val unknownPurpose = ProductionC1DelegatedKeyPurpose(1u shl 6)
        val key = publicKey(privateKey(70))
        assertC1Error(ProductionC1Error.INVALID_VALUE) {
            ProductionC1DelegatedKey(
                1uL,
                keyId(key),
                unknownPurpose,
                now - 1_000uL,
                now + 1_000uL,
                publicKeyX963 = x963(key),
            )
        }
    }

    @Test
    fun internalBridgeCodecDigestAndCryptoStaySingleSourced() {
        val fields = listOf(
            ProductionC1InternalBridge.ascii("bridge"),
            ProductionC1InternalBridge.be(7uL),
            ProductionC1InternalBridge.be(9u),
        )
        val encoded = ProductionC1InternalBridge.encode(23, fields)
        val decoded = ProductionC1InternalBridge.decode(encoded, 23, fields.size, encoded.size)
        assertArrayEquals(fields[0], decoded[0])
        assertArrayEquals(fields[1], decoded[1])
        assertArrayEquals(fields[2], decoded[2])
        assertEquals("bridge", ProductionC1InternalBridge.text(decoded[0]))
        assertEquals(7uL, ProductionC1InternalBridge.uint64(decoded[1]))
        assertEquals(9u, ProductionC1InternalBridge.uint32(decoded[2]))

        val digest = ProductionC1InternalBridge.digestHex(encoded)
        ProductionC1InternalBridge.validateDigest(digest)
        assertArrayEquals(
            MessageDigest.getInstance("SHA-256").digest(encoded),
            ProductionC1InternalBridge.rawDigest(digest),
        )
        assertC1Error(ProductionC1Error.INVALID_VALUE) {
            ProductionC1InternalBridge.rawDigest(digest.uppercase())
        }
        assertC1Error(ProductionC1Error.MALFORMED_CANONICAL) {
            ProductionC1InternalBridge.text(byteArrayOf(0x80.toByte()))
        }
        assertC1Error(ProductionC1Error.MALFORMED_CANONICAL) {
            ProductionC1InternalBridge.decode(encoded + byteArrayOf(0), 23, fields.size, encoded.size + 1)
        }
        assertC1Error(ProductionC1Error.MALFORMED_CANONICAL) {
            ProductionC1InternalBridge.decode(encoded, 24, fields.size, encoded.size)
        }
        assertC1Error(ProductionC1Error.LIMIT_EXCEEDED) {
            ProductionC1InternalBridge.decode(encoded, 23, fields.size, encoded.size - 1)
        }

        val signingKey = privateKey(71)
        val expectedPublicKey = publicKey(signingKey)
        val parsedPublicKey = ProductionC1InternalBridge.publicKey(x963(expectedPublicKey))
        assertEquals(keyId(expectedPublicKey), ProductionC1InternalBridge.keyId(parsedPublicKey))
        val claims = ProductionC1InternalBridge.ascii("claims")
        val transcript = ProductionC1InternalBridge.transcript("bridge-domain-v1", claims)
        assertArrayEquals(
            "bridge-domain-v1".toByteArray(Charsets.UTF_8) + byteArrayOf(0) +
                java.nio.ByteBuffer.allocate(4).putInt(claims.size).array() + claims,
            transcript,
        )
        val signature = ProductionC1InternalBridge.sign(transcript, signingKey)
        ProductionC1InternalBridge.validateSignature(signature)
        ProductionC1InternalBridge.verify(signature, transcript, parsedPublicKey)
        ProductionC1InternalBridge.validateSignature(signature)
        assertC1Error(ProductionC1Error.INVALID_SIGNATURE) {
            ProductionC1InternalBridge.verify(
                signature,
                transcript + byteArrayOf(0),
                parsedPublicKey,
            )
        }
        assertC1Error(ProductionC1Error.INVALID_SIGNATURE) {
            ProductionC1InternalBridge.verify(
                signature,
                transcript,
                publicKey(privateKey(72)),
            )
        }
        assertC1Error(ProductionC1Error.HIGH_S) {
            ProductionC1InternalBridge.validateSignature(makeHighS(signature))
        }
        assertC1Error(ProductionC1Error.NON_CANONICAL_SIGNATURE) {
            ProductionC1InternalBridge.validateSignature(signature + byteArrayOf(0))
        }
        assertC1Error(ProductionC1Error.INVALID_PUBLIC_KEY) {
            ProductionC1InternalBridge.publicKey(x963(expectedPublicKey).also { it[0] = 0x02 })
        }

        ProductionC1InternalBridge.validateWindow(
            now - 100uL,
            now - 10uL,
            now + 100uL,
            1_000uL,
            now,
        )
        assertC1Error(ProductionC1Error.EXPIRED) {
            ProductionC1InternalBridge.validateWindow(
                now - 100uL,
                now - 10uL,
                now,
                1_000uL,
                now,
            )
        }
    }

    @Test
    fun internalBridgeDelegatedSigningKeyRechecksKeysetPurposeAndWindow() {
        val root = privateKey(73)
        val online = privateKey(74)
        val onlinePublic = publicKey(online)
        val delegated = ProductionC1DelegatedKey(
            1uL,
            keyId(onlinePublic),
            ProductionC1DelegatedKeyPurpose.CANDIDATE_PUBLISH,
            now - 1_000uL,
            now + 1_000uL,
            publicKeyX963 = x963(onlinePublic),
        )
        val keyset = ProductionC1ServiceKeyset.signed(
            serviceId,
            1uL,
            null,
            now - 1_000uL,
            now + 2_000uL,
            listOf(delegated),
            publicKey(root),
            root,
        )
        val verified = ProductionC1Verifier.verifyServiceKeyset(
            keyset,
            serviceId,
            publicKey(root),
            1uL,
            nowMs = now,
        )
        val signingPublicKey = ProductionC1InternalBridge.delegatedSigningKey(
            delegated.keyId,
            ProductionC1DelegatedKeyPurpose.CANDIDATE_PUBLISH,
            verified,
            now,
        )
        assertEquals(delegated.keyId, ProductionC1InternalBridge.keyId(signingPublicKey))
        val transcript = ProductionC1InternalBridge.transcript(
            "candidate-publish-bridge-test-v1",
            byteArrayOf(1, 2, 3),
        )
        ProductionC1InternalBridge.verify(
            ProductionC1InternalBridge.sign(transcript, online),
            transcript,
            signingPublicKey,
        )
        assertC1Error(ProductionC1Error.KEY_PURPOSE_MISMATCH) {
            ProductionC1InternalBridge.delegatedSigningKey(
                delegated.keyId,
                ProductionC1DelegatedKeyPurpose.CANDIDATE_FETCH,
                verified,
                now,
            )
        }
        assertC1Error(ProductionC1Error.NOT_YET_VALID) {
            ProductionC1InternalBridge.delegatedSigningKey(
                delegated.keyId,
                ProductionC1DelegatedKeyPurpose.CANDIDATE_PUBLISH,
                verified,
                delegated.notBeforeMs - 1uL,
            )
        }
        assertC1Error(ProductionC1Error.EXPIRED) {
            ProductionC1InternalBridge.delegatedSigningKey(
                delegated.keyId,
                ProductionC1DelegatedKeyPurpose.CANDIDATE_PUBLISH,
                verified,
                delegated.expiresAtMs,
            )
        }
    }

    private data class Fixture(
        val statusKey: PrivateKey,
        val routeKey: PrivateKey,
        val verifiedKeyset: VerifiedProductionC1ServiceKeyset,
        val clientFingerprint: String,
        val runtimeFingerprint: String,
    )

    private fun fixture(): Fixture {
        val root = privateKey(10)
        val status = privateKey(11)
        val route = privateKey(12)
        val keyset = keyset(
            root,
            1uL,
            null,
            listOf(
                delegated(status, 1uL, ProductionC1DelegatedKeyPurpose.PAIR_STATUS),
                delegated(route, 1uL, ProductionC1DelegatedKeyPurpose.ROUTE_CAPABILITY),
            ).sortedBy { it.keyId },
        )
        return Fixture(
            status,
            route,
            ProductionC1Verifier.verifyServiceKeyset(
                keyset,
                serviceId,
                publicKey(root),
                1uL,
                nowMs = now,
            ),
            keyId(publicKey(privateKey(13))),
            keyId(publicKey(privateKey(14))),
        )
    }

    private fun keyset(
        root: PrivateKey,
        version: ULong,
        previousDigest: String?,
        keys: List<ProductionC1DelegatedKey>,
    ) = ProductionC1ServiceKeyset.signed(
        serviceId, version, previousDigest, now - 1_000uL, now + 100_000uL, keys,
        publicKey(root), root,
    )

    private fun delegated(
        key: PrivateKey,
        version: ULong,
        purposes: ProductionC1DelegatedKeyPurpose,
    ) = ProductionC1DelegatedKey(
        version, keyId(publicKey(key)), purposes, now - 1_000uL, now + 100_000uL,
        publicKeyX963 = x963(publicKey(key)),
    )

    private fun authority(
        evidence: String,
        clientFingerprint: String,
        runtimeFingerprint: String,
    ) = ProductionPairAuthorityState(
        "d".repeat(64), 1uL, clientFingerprint, runtimeFingerprint, 1uL, 1uL, 1uL,
        0uL, 1u, ProductionPairAuthorityStatus.ACTIVE, "1".repeat(64), "2".repeat(64),
        evidence, 1uL,
    )

    private fun assertC1Error(expected: ProductionC1Error, body: () -> Unit) {
        try {
            body()
            fail("Expected $expected")
        } catch (error: ProductionC1Exception) {
            assertEquals(expected, error.reason)
        }
    }

    private fun assertPairStateError(
        expected: ProductionPairStateRejectionReason,
        body: () -> Unit,
    ) {
        try {
            body()
            fail("Expected $expected")
        } catch (error: ProductionPairStateException) {
            assertEquals(expected, error.reason)
        }
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
                .multiply(left.affineY.multiply(BigInteger.TWO).mod(prime).modInverse(prime)).mod(prime)
        } else {
            right.affineY.subtract(left.affineY).mod(prime)
                .multiply(right.affineX.subtract(left.affineX).mod(prime).modInverse(prime)).mod(prime)
        }
        val x = slope.modPow(BigInteger.TWO, prime).subtract(left.affineX).subtract(right.affineX).mod(prime)
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

    private fun replacingLastTLVField(data: ByteArray, replacement: ByteArray): ByteArray {
        var cursor = 6
        var last = 0
        while (cursor < data.size) {
            last = cursor
            val size = java.nio.ByteBuffer.wrap(data, cursor + 1, 4).int
            cursor += 5 + size
        }
        val length = java.nio.ByteBuffer.allocate(4).putInt(replacement.size).array()
        return data.copyOfRange(0, last) + byteArrayOf(data[last]) + length + replacement
    }

    private fun replacingTLVFields(
        data: ByteArray,
        replacements: Map<Int, ByteArray>,
    ): ByteArray {
        var cursor = 6
        var result = data.copyOfRange(0, cursor)
        while (cursor < data.size) {
            val tag = data[cursor].toInt() and 0xff
            val length = java.nio.ByteBuffer.wrap(data, cursor + 1, 4).int
            val original = data.copyOfRange(cursor + 5, cursor + 5 + length)
            val value = replacements[tag] ?: original
            result += byteArrayOf(tag.toByte())
            result += java.nio.ByteBuffer.allocate(4).putInt(value.size).array()
            result += value
            cursor += 5 + length
        }
        return result
    }

    private fun be(value: ULong): ByteArray = java.nio.ByteBuffer.allocate(8)
        .putLong(value.toLong())
        .array()

    private fun String.hexBytes(): ByteArray = chunked(2).map { it.toInt(16).toByte() }.toByteArray()
    private fun ByteArray.hex(): String = joinToString("") { "%02x".format(it) }
    private fun BigInteger.fixed(size: Int): ByteArray {
        val raw = toByteArray()
        val unsigned = if (raw.size > 1 && raw[0] == 0.toByte()) raw.copyOfRange(1, raw.size) else raw
        return ByteArray(size - unsigned.size) + unsigned
    }

    private companion object {
        val P256: ECParameterSpec = AlgorithmParameters.getInstance("EC").run {
            init(ECGenParameterSpec("secp256r1"))
            getParameterSpec(ECParameterSpec::class.java)
        }
        val ORDER = BigInteger("ffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551", 16)
        const val SWIFT_ROUTE_HANDLE_DIGEST =
            "28fb49c2e49a3479d68af922ea3ab1ed3f8b09eed2d2d419e00a0b551ccd033b"
        const val SWIFT_CREDENTIAL_DIGEST =
            "648a00a4ab7cccfa07b9a480e76218533c844baaeadb87b1b78dff09dc83ef88"
        const val SWIFT_CONNECTOR_HEX =
            "414c5331100101000000286165746865726c696e6b2d70726f64756374696f6e2d617574686f726974792d726f7574652d7631020000001676657269666965645f7475726e5f72656c61795f763103000000047f000001040000000201bb050000000d72656c61792e6578616d706c650600000007746c735f7463700700000040323866623439633265343961333437396436386166393232656133616231656433663862303965656432643264343139653030613062353531636364303333620800000040363438613030613461623763636366613037623961343830653736323138353333633834346261616561646238376231623738646666303964633833656638380900000040373737373737373737373737373737373737373737373737373737373737373737373737373737373737373737373737373737373737373737373737373737370a00000040363636363636363636363636363636363636363636363636363636363636363636363636363636363636363636363636363636363636363636363636363636360b0000004038383838383838383838383838383838383838383838383838383838383838383838383838383838383838383838383838383838383838383838383838383838"
    }
}
