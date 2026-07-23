package com.localagentbridge.android.core.protocol.p2pnat

import java.nio.file.Files
import java.nio.file.Path
import java.security.KeyFactory
import java.security.MessageDigest
import java.security.PublicKey
import java.security.spec.X509EncodedKeySpec
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

class ProductionG1aCCandidateEndpointAdmissionTest {
    @Test
    fun object4Object26BindingMatchesSwiftCrossPlatformParityVector() {
        assertEquals(
            "6e405627c9f8c876db1755f1fae47185bcb4b00384e5850665bff4aa78f0b784",
            ProductionC1EndpointGrantAdmission.bindingDigest(
                "00".repeat(32),
                "11".repeat(32),
                "22".repeat(32),
                "33".repeat(32),
                "44".repeat(32),
                "55".repeat(32),
            ),
        )
    }

    @Test
    fun keyScheduleBindingAcceptsBothRolesAndRejectsStaleAuthorization() {
        val fixture = loadFixture()
        val chain = verifiedChain(fixture)
        val now = fixture.root.obj("constants").ulong("nowMs")

        val client = ProductionC1CandidateVerifier.verifyP2PKeyScheduleBinding(
            chain.transcript,
            chain.grant,
            P2pNatRole.CLIENT,
            chain.authority,
            now,
        )
        val runtime = ProductionC1CandidateVerifier.verifyP2PKeyScheduleBinding(
            chain.transcript,
            chain.grant,
            P2pNatRole.RUNTIME,
            chain.authority,
            now,
        )
        assertEquals(chain.transcript, client.transcript)
        assertEquals(chain.grant.grantAuthorization, client.grantAuthorization)
        assertEquals(chain.context, client.securityContext)
        assertEquals(P2pNatRole.CLIENT, client.localRole)
        assertEquals(P2pNatRole.RUNTIME, runtime.localRole)

        val object4BoundTranscript = ProductionSecureSessionTranscript(
            sessionId = chain.transcript.sessionId,
            pairBindingDigest = chain.transcript.pairBindingDigest,
            pairEpoch = chain.transcript.pairEpoch,
            clientIdentityFingerprint = chain.transcript.clientIdentityFingerprint,
            runtimeIdentityFingerprint = chain.transcript.runtimeIdentityFingerprint,
            clientEphemeralPublicKey = chain.transcript.clientEphemeralPublicKey,
            runtimeEphemeralPublicKey = chain.transcript.runtimeEphemeralPublicKey,
            clientNonce = chain.transcript.clientNonce,
            runtimeNonce = chain.transcript.runtimeNonce,
            generation = chain.transcript.generation,
            serviceConfigVersion = chain.transcript.serviceConfigVersion,
            keysetVersion = chain.transcript.keysetVersion,
            revocationCounter = chain.transcript.revocationCounter,
            protocolVersion = chain.transcript.protocolVersion,
            minimumProtocolVersion = chain.transcript.minimumProtocolVersion,
            profile = chain.transcript.profile,
            routeAuthorizationKind = chain.transcript.routeAuthorizationKind,
            routeAuthorizationDigest = sha256Hex(
                ProductionSecureSessionCodec.encode(chain.authorizations.finalP2PDirect),
            ),
            suite = chain.transcript.suite,
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.ROUTE_MISMATCH) {
            ProductionC1CandidateVerifier.verifyP2PKeyScheduleBinding(
                object4BoundTranscript,
                chain.grant,
                P2pNatRole.CLIENT,
                chain.authority,
                now,
            )
        }
        assertCandidateError(ProductionC1CandidateCapabilityError.ROUTE_MISMATCH) {
            ProductionC1CandidateVerifier.verifyP2PKeyScheduleBinding(
                chain.transcript,
                chain.grant,
                P2pNatRole.CLIENT,
                chain.authority,
                chain.grant.evidence.expiresAtMs,
            )
        }

        val driftedAuthority = chain.authority.copy(
            revocationCounter = chain.authority.revocationCounter + 1uL,
            authorityRevision = chain.authority.authorityRevision + 1uL,
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.AUTHORITY_MISMATCH) {
            ProductionC1CandidateVerifier.verifyP2PKeyScheduleBinding(
                chain.transcript,
                chain.grant,
                P2pNatRole.RUNTIME,
                driftedAuthority,
                now,
            )
        }
    }

    @Test
    fun deterministicBootstrapSnapshotAndCompoundMatchSwiftParityVectors() {
        val authority = ProductionPairAuthorityState(
            pairBindingDigest = "1".repeat(64),
            pairEpoch = 2uL,
            clientIdentityFingerprint = "2".repeat(64),
            runtimeIdentityFingerprint = "3".repeat(64),
            generation = 30uL,
            serviceConfigVersion = 4uL,
            keysetVersion = 5uL,
            revocationCounter = 0uL,
            protocolFloor = 1u,
            status = ProductionPairAuthorityStatus.ACTIVE,
            transitionId = "4".repeat(64),
            transitionRequestDigest = "5".repeat(64),
            acceptedReceiptDigest = "6".repeat(64),
            authorityRevision = 1uL,
        )
        val currentPair = ProductionPairStateSnapshot(authority, 1uL)
        val currentLedger = ProductionC1EndpointGrantLedgerState(
            pairAuthorityDigest = authority.digestHex(),
            pairLocalRevision = 1uL,
            remainingGrants = 64uL,
            retentionLimit = 64u,
        )
        val nextPair = ProductionPairStateSnapshot(
            authority,
            2uL,
            listOf(ProductionPairConsumedSession("7".repeat(32), "7".repeat(64))),
        )
        val entry = ProductionC1EndpointGrantEntry(
            "7".repeat(64),
            "7".repeat(64),
            "7".repeat(64),
            "7".repeat(32),
            "7".repeat(64),
            "7".repeat(64),
            "a".repeat(64),
            "7".repeat(64),
            nextPair.digestHex(),
            2uL,
        )
        val nextLedger = ProductionC1EndpointGrantLedgerState(
            revision = 2uL,
            pairAuthorityDigest = currentLedger.pairAuthorityDigest,
            pairLocalRevision = 2uL,
            remainingGrants = 63uL,
            retentionLimit = 64u,
            entries = listOf(entry),
        )

        assertEquals(
            "2f285232932e32da2ca1aea633f37df6bbfbf7b5ceb4978878b9278b94d224f7",
            nextLedger.snapshotDigestHex(),
        )
        assertEquals(
            "22a1b5f70632c2024fd565708d6227f2ad21037f450b5e1094892d9dd3c36a71",
            ProductionC1EndpointCompoundRecord(nextLedger, nextPair).digestHex(),
        )
    }

    @Test
    fun connectorConfirmationAndBindingMatchExactSwiftReferenceDigests() {
        val fixture = loadFixture()
        val chain = verifiedChain(fixture)
        val synthetic = fixture.root.obj("syntheticMaterials")
        val now = fixture.root.obj("constants").ulong("nowMs")
        val secret = synthetic.hex("connectorSecretHex")
        val connectorInput = ProductionC1CandidateVerifier.verifyP2PConnectorInput(
            chain.grant,
            P2pNatRole.CLIENT,
            synthetic.string("routeHandle"),
            synthetic.string("connectorNonce"),
            secret,
            chain.authority,
            now,
        )
        assertEquals(SWIFT_CONNECTOR_INPUT_COMMITMENT, connectorInput.commitmentDigest)

        val key = synthetic.hex("keyConfirmationKeyHex")
        val confirmation = ProductionC1CandidateVerifier.makeP2PKeyConfirmation(
            chain.transcript,
            chain.grant.grantAuthorization,
            P2pNatRole.RUNTIME,
            key,
        )
        assertEquals(SWIFT_RUNTIME_KEY_CONFIRMATION, confirmation.lowerHex())
        val binding = ProductionC1CandidateVerifier.verifyP2PTranscriptBinding(
            chain.transcript,
            chain.grant,
            connectorInput,
            P2pNatRole.CLIENT,
            key,
            confirmation,
            chain.authority,
            now,
        )
        assertEquals(chain.context, binding.securityContext)
        val descriptor =
            VerifiedProductionC1CandidateP2PTransportDescriptor.fromVerifiedBinding(binding)
        assertEquals(
            descriptor,
            VerifiedProductionC1CandidateP2PTransportDescriptor.fromVerifiedBinding(binding),
        )
        assertTrue(
            VerifiedProductionC1CandidateP2PTransportDescriptor::class.java.declaredMethods.none {
                it.name == "copy" || it.name.startsWith("component")
            },
        )
        assertEquals(chain.transcript.sessionId, descriptor.sessionId)
        assertEquals(chain.transcript.generation, descriptor.generation)
        assertEquals(connectorInput.commitmentDigest, descriptor.connectorInputCommitmentDigest)
        assertEquals(chain.context.digestHex(), descriptor.securityContextDigest)
        assertEquals(chain.grant.evidence.c1RoutePlanClaimsDigest, descriptor.routePlanDigest)
        assertEquals(chain.grant.evidence.digestHex(), descriptor.routeGrantDigest)
        assertEquals(chain.grant.evidence.effectiveNotBeforeMs, descriptor.effectiveNotBeforeMs)
        assertEquals(chain.grant.evidence.expiresAtMs, descriptor.expiresAtMs)
        assertFalse(descriptor.toString().contains(synthetic.string("routeHandle")))
        assertFalse(descriptor.toString().contains(synthetic.string("connectorNonce")))
        assertFalse(descriptor.toString().contains(synthetic.string("connectorSecretHex")))

        val admissionBinding = admissionBinding(chain, connectorInput, ADMISSION_ID)
        assertEquals(SWIFT_ADMISSION_BINDING, admissionBinding)

        secret.fill(0)
        key.fill(0)
        confirmation.fill(0)
        assertTrue(connectorInput.secret.all { it == 0x5a.toByte() })
        assertEquals(
            SWIFT_RUNTIME_KEY_CONFIRMATION,
            binding.presentedPeerKeyConfirmation.lowerHex(),
        )

        assertCandidateError(ProductionC1CandidateCapabilityError.INVALID_VALUE) {
            ProductionC1CandidateVerifier.makeP2PKeyConfirmation(
                chain.transcript,
                chain.grant.grantAuthorization,
                P2pNatRole.RUNTIME,
                ByteArray(31),
            )
        }
        assertCandidateError(ProductionC1CandidateCapabilityError.ROUTE_MISMATCH) {
            ProductionC1CandidateVerifier.verifyP2PTranscriptBinding(
                chain.transcript,
                chain.grant,
                connectorInput,
                P2pNatRole.CLIENT,
                synthetic.hex("keyConfirmationKeyHex"),
                ByteArray(32),
                chain.authority,
                now,
            )
        }
    }

    @Test
    fun runtimeInboundBindingRequiresClientRoleConfirmationAndExactObservedPeer() {
        val fixture = loadFixture()
        val chain = verifiedChain(fixture)
        val now = fixture.root.obj("constants").ulong("nowMs")
        val key = fixture.root.obj("syntheticMaterials").hex("keyConfirmationKeyHex")
        val clientConfirmation = ProductionC1CandidateVerifier.makeP2PKeyConfirmation(
            chain.transcript,
            chain.grant.grantAuthorization,
            P2pNatRole.CLIENT,
            key,
        )
        assertEquals(SWIFT_CLIENT_KEY_CONFIRMATION, clientConfirmation.lowerHex())
        val inbound = ProductionC1CandidateVerifier.verifyP2PInboundMaterial(
            chain.transcript,
            chain.grant,
            P2pNatRole.RUNTIME,
            chain.plan.selectedClientCandidate,
            key,
            clientConfirmation,
            chain.authority,
            now,
        )
        assertEquals(SWIFT_CLIENT_CONFIRMATION_DIGEST, inbound.peerKeyConfirmationDigest)
        assertEquals(
            sha256Hex(ProductionSecureSessionCodec.encode(chain.transcript)),
            inbound.transcriptDigest,
        )
        assertEquals(chain.grant.evidence.digestHex(), inbound.routeGrantDigest)
        assertEquals(chain.grant.grantAuthorization.digestHex, inbound.grantAuthorizationDigest)
        assertEquals(chain.transcript.sessionId, inbound.sessionId)
        val exact = ProductionC1CandidateVerifier.verifyP2PInboundTranscriptBinding(
            chain.transcript,
            chain.grant,
            inbound,
            P2pNatRole.RUNTIME,
            chain.authority,
            now,
        )
        assertEquals(chain.context, exact.securityContext)
        val anotherSession = ProductionSecureSessionTranscript(
            sessionId = "d".repeat(32),
            pairBindingDigest = chain.transcript.pairBindingDigest,
            pairEpoch = chain.transcript.pairEpoch,
            clientIdentityFingerprint = chain.transcript.clientIdentityFingerprint,
            runtimeIdentityFingerprint = chain.transcript.runtimeIdentityFingerprint,
            clientEphemeralPublicKey = chain.transcript.clientEphemeralPublicKey,
            runtimeEphemeralPublicKey = chain.transcript.runtimeEphemeralPublicKey,
            clientNonce = chain.transcript.clientNonce,
            runtimeNonce = chain.transcript.runtimeNonce,
            generation = chain.transcript.generation,
            serviceConfigVersion = chain.transcript.serviceConfigVersion,
            keysetVersion = chain.transcript.keysetVersion,
            revocationCounter = chain.transcript.revocationCounter,
            protocolVersion = chain.transcript.protocolVersion,
            minimumProtocolVersion = chain.transcript.minimumProtocolVersion,
            profile = chain.transcript.profile,
            routeAuthorizationKind = chain.transcript.routeAuthorizationKind,
            routeAuthorizationDigest = chain.transcript.routeAuthorizationDigest,
            suite = chain.transcript.suite,
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.ROUTE_MISMATCH) {
            ProductionC1CandidateVerifier.verifyP2PInboundTranscriptBinding(
                anotherSession,
                chain.grant,
                inbound,
                P2pNatRole.RUNTIME,
                chain.authority,
                now,
            )
        }

        clientConfirmation.fill(0)
        key.fill(0)
        assertEquals(SWIFT_CLIENT_CONFIRMATION_DIGEST, inbound.peerKeyConfirmationDigest)

        val freshKey = fixture.root.obj("syntheticMaterials").hex("keyConfirmationKeyHex")
        val freshConfirmation = ProductionC1CandidateVerifier.makeP2PKeyConfirmation(
            chain.transcript,
            chain.grant.grantAuthorization,
            P2pNatRole.CLIENT,
            freshKey,
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.ROUTE_MISMATCH) {
            ProductionC1CandidateVerifier.verifyP2PInboundMaterial(
                chain.transcript,
                chain.grant,
                P2pNatRole.CLIENT,
                chain.plan.selectedClientCandidate,
                freshKey,
                freshConfirmation,
                chain.authority,
                now,
            )
        }
        assertCandidateError(ProductionC1CandidateCapabilityError.ROUTE_MISMATCH) {
            ProductionC1CandidateVerifier.verifyP2PInboundMaterial(
                chain.transcript,
                chain.grant,
                P2pNatRole.RUNTIME,
                chain.plan.selectedRuntimeCandidate,
                freshKey,
                freshConfirmation,
                chain.authority,
                now,
            )
        }
        assertCandidateError(ProductionC1CandidateCapabilityError.ROUTE_MISMATCH) {
            ProductionC1CandidateVerifier.verifyP2PInboundMaterial(
                chain.transcript,
                chain.grant,
                P2pNatRole.RUNTIME,
                chain.plan.selectedClientCandidate,
                freshKey,
                ByteArray(32),
                chain.authority,
                now,
            )
        }
    }

    @Test
    fun endpointAdmissionAppliesIdempotentlyRetriesAndRejectsReplayCasExpiryAndMutation() {
        val fixture = loadFixture()
        val chain = verifiedChain(fixture)
        val synthetic = fixture.root.obj("syntheticMaterials")
        val now = fixture.root.obj("constants").ulong("nowMs")
        val connectorInput = ProductionC1CandidateVerifier.verifyP2PConnectorInput(
            chain.grant,
            P2pNatRole.CLIENT,
            synthetic.string("routeHandle"),
            synthetic.string("connectorNonce"),
            synthetic.hex("connectorSecretHex"),
            chain.authority,
            now,
        )
        val key = synthetic.hex("keyConfirmationKeyHex")
        val confirmation = ProductionC1CandidateVerifier.makeP2PKeyConfirmation(
            chain.transcript,
            chain.grant.grantAuthorization,
            P2pNatRole.RUNTIME,
            key,
        )
        val verifiedBinding = ProductionC1CandidateVerifier.verifyP2PTranscriptBinding(
            chain.transcript,
            chain.grant,
            connectorInput,
            P2pNatRole.CLIENT,
            key,
            confirmation,
            chain.authority,
            now,
        )
        key.fill(0)
        confirmation.fill(0)

        val pair = ProductionPairStateSnapshot(chain.authority, 1uL)
        val ledger = ProductionC1EndpointGrantLedgerState(
            pairAuthorityDigest = chain.authority.digestHex(),
            pairLocalRevision = pair.localRevision,
            remainingGrants = 1uL,
            retentionLimit = 8u,
        )
        val bindingDigest = admissionBinding(chain, connectorInput, ADMISSION_ID)
        val grantDigest = chain.grant.evidence.digestHex()
        val transcriptDigest = sha256Hex(ProductionSecureSessionCodec.encode(chain.transcript))
        val object4Digest = sha256Hex(
            ProductionSecureSessionCodec.encode(chain.authorizations.finalP2PDirect),
        )
        val object26Digest = chain.grant.grantAuthorization.digestHex
        assertEquals(object26Digest, chain.transcript.routeAuthorizationDigest)
        assertTrue(object4Digest != object26Digest)
        val object4OnlyMutationBinding = ProductionC1EndpointGrantAdmission.bindingDigest(
            ADMISSION_ID,
            grantDigest,
            transcriptDigest,
            "0".repeat(64),
            object26Digest,
            connectorInput.commitmentDigest,
        )
        val object26OnlyMutationBinding = ProductionC1EndpointGrantAdmission.bindingDigest(
            ADMISSION_ID,
            grantDigest,
            transcriptDigest,
            object4Digest,
            "0".repeat(64),
            connectorInput.commitmentDigest,
        )
        assertTrue(bindingDigest != object4OnlyMutationBinding)
        assertTrue(bindingDigest != object26OnlyMutationBinding)
        assertCandidateError(ProductionC1CandidateCapabilityError.ROUTE_MISMATCH) {
            ProductionC1EndpointGrantAdmission.prepareForTrustedPersistence(
                ledger,
                ledger.revision,
                ledger.snapshotDigestHex(),
                ADMISSION_ID,
                object4OnlyMutationBinding,
                verifiedBinding,
                pair,
                now,
            )
        }
        assertCandidateError(ProductionC1CandidateCapabilityError.ROUTE_MISMATCH) {
            ProductionC1EndpointGrantAdmission.prepareForTrustedPersistence(
                ledger,
                ledger.revision,
                ledger.snapshotDigestHex(),
                ADMISSION_ID,
                object26OnlyMutationBinding,
                verifiedBinding,
                pair,
                now,
            )
        }
        val preparation = ProductionC1EndpointGrantAdmission.prepareForTrustedPersistence(
            ledger,
            ledger.revision,
            ledger.snapshotDigestHex(),
            ADMISSION_ID,
            bindingDigest,
            verifiedBinding,
            pair,
            now,
        )
        assertEquals(ProductionC1CandidateCASDisposition.APPLIED, preparation.disposition)
        assertEquals(chain.grant.evidence.effectiveNotBeforeMs, preparation.effectiveNotBeforeMs)
        assertEquals(chain.grant.evidence.expiresAtMs, preparation.expiresAtMs)
        assertTrue(preparation.effectiveNotBeforeMs < preparation.expiresAtMs)
        assertEquals(2uL, preparation.nextState.revision)
        assertEquals(0uL, preparation.nextState.remainingGrants)
        assertEquals(2uL, preparation.nextPairSnapshot.localRevision)
        assertEquals(1, preparation.nextPairSnapshot.consumedEntries.size)
        assertEquals(preparation.nextPairSnapshot.digestHex(), preparation.entry.pairSnapshotDigest)
        assertEquals(object4Digest, preparation.entry.routeAuthorizationDigest)
        assertEquals(object26Digest, preparation.entry.grantAuthorizationDigest)
        assertEquals(
            preparation.entry,
            ReadbackConfirmedProductionC1EndpointGrantAdmission.confirm(
                preparation,
                preparation.nextCompoundRecord,
            ).entry,
        )

        val returnedEntries = preparation.nextState.entries.toMutableList()
        returnedEntries.clear()
        val returnedConsumed = preparation.nextPairSnapshot.consumedEntries.toMutableList()
        returnedConsumed.clear()
        assertEquals(1, preparation.nextState.entries.size)
        assertEquals(1, preparation.nextPairSnapshot.consumedEntries.size)

        val idempotent = ProductionC1EndpointGrantAdmission.prepare(
            preparation.nextState,
            999uL,
            "f".repeat(64),
            ADMISSION_ID,
            bindingDigest,
            verifiedBinding,
            preparation.nextPairSnapshot,
            chain.grant.evidence.expiresAtMs,
        )
        assertEquals(ProductionC1CandidateCASDisposition.IDEMPOTENT, idempotent.disposition)
        assertEquals(preparation.effectiveNotBeforeMs, idempotent.effectiveNotBeforeMs)
        assertEquals(preparation.expiresAtMs, idempotent.expiresAtMs)
        ReadbackConfirmedProductionC1EndpointGrantAdmission.confirm(
            idempotent,
            idempotent.nextCompoundRecord,
        )

        val retryGrantBytes = chain.grant.evidence.canonicalBytes()
        val retryTranscriptBytes = ProductionSecureSessionCodec.encode(chain.transcript)
        val committedRetry = ProductionC1EndpointGrantAdmission.prepareCommittedRetry(
            preparation.nextState,
            ADMISSION_ID,
            bindingDigest,
            retryGrantBytes,
            chain.authorizations.finalP2PDirect,
            retryTranscriptBytes,
            connectorInput.commitmentDigest,
            preparation.nextPairSnapshot,
        )
        retryGrantBytes.fill(0)
        retryTranscriptBytes.fill(0)
        assertEquals(ProductionC1CandidateCASDisposition.IDEMPOTENT, committedRetry.disposition)
        assertEquals(preparation.entry, committedRetry.entry)
        assertEquals(preparation.effectiveNotBeforeMs, committedRetry.effectiveNotBeforeMs)
        assertEquals(preparation.expiresAtMs, committedRetry.expiresAtMs)

        fun retryStateWith(entry: ProductionC1EndpointGrantEntry) =
            ProductionC1EndpointGrantLedgerState(
                revision = preparation.nextState.revision,
                pairAuthorityDigest = preparation.nextState.pairAuthorityDigest,
                pairLocalRevision = preparation.nextState.pairLocalRevision,
                remainingGrants = preparation.nextState.remainingGrants,
                retentionLimit = preparation.nextState.retentionLimit,
                entries = listOf(entry),
            )
        val object4OnlyEntryMutation = ProductionC1EndpointGrantEntry(
            preparation.entry.admissionId,
            preparation.entry.bindingDigest,
            preparation.entry.routeGrantDigest,
            preparation.entry.sessionId,
            preparation.entry.transcriptDigest,
            "0".repeat(64),
            preparation.entry.grantAuthorizationDigest,
            preparation.entry.connectorInputCommitmentDigest,
            preparation.entry.pairSnapshotDigest,
            preparation.entry.committedRevision,
        )
        val object26OnlyEntryMutation = ProductionC1EndpointGrantEntry(
            preparation.entry.admissionId,
            preparation.entry.bindingDigest,
            preparation.entry.routeGrantDigest,
            preparation.entry.sessionId,
            preparation.entry.transcriptDigest,
            preparation.entry.routeAuthorizationDigest,
            "0".repeat(64),
            preparation.entry.connectorInputCommitmentDigest,
            preparation.entry.pairSnapshotDigest,
            preparation.entry.committedRevision,
        )
        listOf(object4OnlyEntryMutation, object26OnlyEntryMutation).forEach { mutatedEntry ->
            assertCandidateError(ProductionC1CandidateCapabilityError.REQUEST_CONFLICT) {
                ProductionC1EndpointGrantAdmission.prepareCommittedRetry(
                    retryStateWith(mutatedEntry),
                    ADMISSION_ID,
                    bindingDigest,
                    chain.grant.evidence.canonicalBytes(),
                    chain.authorizations.finalP2PDirect,
                    ProductionSecureSessionCodec.encode(chain.transcript),
                    connectorInput.commitmentDigest,
                    preparation.nextPairSnapshot,
                )
            }
        }

        assertCandidateError(ProductionC1CandidateCapabilityError.REVISION_MISMATCH) {
            ProductionC1EndpointGrantAdmission.prepare(
                ledger,
                99uL,
                ledger.snapshotDigestHex(),
                ADMISSION_ID,
                bindingDigest,
                verifiedBinding,
                pair,
                now,
            )
        }
        assertCandidateError(ProductionC1CandidateCapabilityError.ROUTE_MISMATCH) {
            ProductionC1EndpointGrantAdmission.prepare(
                ledger,
                ledger.revision,
                ledger.snapshotDigestHex(),
                ADMISSION_ID,
                bindingDigest,
                verifiedBinding,
                pair,
                chain.grant.evidence.expiresAtMs,
            )
        }

        val replayId = "8".repeat(64)
        val replayBinding = admissionBinding(chain, connectorInput, replayId)
        assertCandidateError(ProductionC1CandidateCapabilityError.REPLAY) {
            ProductionC1EndpointGrantAdmission.prepare(
                preparation.nextState,
                preparation.nextState.revision,
                preparation.nextState.snapshotDigestHex(),
                replayId,
                replayBinding,
                verifiedBinding,
                preparation.nextPairSnapshot,
                now,
            )
        }
        assertCandidateError(ProductionC1CandidateCapabilityError.REVISION_MISMATCH) {
            ReadbackConfirmedProductionC1EndpointGrantAdmission.confirm(
                preparation,
                ProductionC1EndpointCompoundRecord(ledger, pair),
            )
        }
        assertCandidateError(ProductionC1CandidateCapabilityError.REQUEST_CONFLICT) {
            ProductionC1EndpointGrantAdmission.prepareCommittedRetry(
                preparation.nextState,
                ADMISSION_ID,
                "e".repeat(64),
                chain.grant.evidence.canonicalBytes(),
                chain.authorizations.finalP2PDirect,
                ProductionSecureSessionCodec.encode(chain.transcript),
                connectorInput.commitmentDigest,
                preparation.nextPairSnapshot,
            )
        }
    }

    @Test
    fun persistenceCodecMatchesSwiftBytesAndRejectsMalformedCapacityAndMutableCopies() {
        val entry = ProductionC1EndpointGrantEntry(
            "1".repeat(64),
            "2".repeat(64),
            "3".repeat(64),
            "4".repeat(32),
            "5".repeat(64),
            "6".repeat(64),
            "9".repeat(64),
            "7".repeat(64),
            "8".repeat(64),
            2uL,
        )
        val state = ProductionC1EndpointGrantLedgerState(
            revision = 2uL,
            pairAuthorityDigest = "a".repeat(64),
            pairLocalRevision = 2uL,
            remainingGrants = 1uL,
            retentionLimit = 8u,
            entries = listOf(entry),
        )
        assertEquals(SWIFT_LEDGER_SNAPSHOT_DIGEST, state.snapshotDigestHex())
        val encoded = state.persistenceCanonicalBytes()
        assertArrayEquals(SWIFT_ALC1EGL1_BYTES.hex(), encoded)
        assertEquals(state, ProductionC1EndpointGrantLedgerState.decodePersistenceCanonicalBytes(encoded))

        val source = encoded.copyOf()
        val decoded = ProductionC1EndpointLedgerPersistenceCodec.decode(source)
        source.fill(0)
        assertArrayEquals(encoded, decoded.persistenceCanonicalBytes())
        val returned = decoded.entries.toMutableList()
        returned.clear()
        assertEquals(entry, decoded.entries.single())

        assertCandidateError(ProductionC1CandidateCapabilityError.MALFORMED_CANONICAL) {
            ProductionC1EndpointLedgerPersistenceCodec.decode(encoded.copyOf(encoded.size - 1))
        }
        assertCandidateError(ProductionC1CandidateCapabilityError.MALFORMED_CANONICAL) {
            ProductionC1EndpointLedgerPersistenceCodec.decode(encoded + byteArrayOf(0))
        }
        val wrongMagic = encoded.copyOf().also { bytes ->
            bytes[0] = (bytes[0].toInt() xor 0x01).toByte()
        }
        assertCandidateError(ProductionC1CandidateCapabilityError.MALFORMED_CANONICAL) {
            ProductionC1EndpointLedgerPersistenceCodec.decode(wrongMagic)
        }
        val obsoleteObject4OnlySchema = encoded.copyOf().also { it[11] = 1 }
        assertCandidateError(ProductionC1CandidateCapabilityError.MALFORMED_CANONICAL) {
            ProductionC1EndpointLedgerPersistenceCodec.decode(obsoleteObject4OnlySchema)
        }
        val overCommitted = ProductionC1EndpointGrantLedgerState(
            revision = 2uL,
            pairAuthorityDigest = "a".repeat(64),
            pairLocalRevision = 2uL,
            remainingGrants = 8uL,
            retentionLimit = 8u,
            entries = listOf(entry),
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.RETENTION_EXHAUSTED) {
            ProductionC1EndpointLedgerPersistenceCodec.encode(overCommitted)
        }
    }

    @Test
    fun verifiedWrappersAndPreparationsRejectForgedProvenance() {
        val fixture = loadFixture()
        val chain = verifiedChain(fixture)
        val synthetic = fixture.root.obj("syntheticMaterials")
        val now = fixture.root.obj("constants").ulong("nowMs")
        assertCandidateError(ProductionC1CandidateCapabilityError.ROUTE_MISMATCH) {
            VerifiedProductionC1CandidateP2PConnectorInput(
                chain.plan.claims.connector,
                "a".repeat(64),
                synthetic.string("routeHandle"),
                synthetic.string("connectorNonce"),
                synthetic.hex("connectorSecretHex"),
                Any(),
            )
        }

        val connectorInput = ProductionC1CandidateVerifier.verifyP2PConnectorInput(
            chain.grant,
            P2pNatRole.CLIENT,
            synthetic.string("routeHandle"),
            synthetic.string("connectorNonce"),
            synthetic.hex("connectorSecretHex"),
            chain.authority,
            now,
        )
        val key = synthetic.hex("keyConfirmationKeyHex")
        val confirmation = ProductionC1CandidateVerifier.makeP2PKeyConfirmation(
            chain.transcript,
            chain.grant.grantAuthorization,
            P2pNatRole.RUNTIME,
            key,
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.ROUTE_MISMATCH) {
            VerifiedProductionC1CandidateP2PTranscriptBinding(
                chain.transcript,
                chain.grant,
                connectorInput,
                chain.context,
                ProductionC1CandidateVerifier.verifyP2PKeyScheduleBinding(
                    chain.transcript,
                    chain.grant,
                    P2pNatRole.CLIENT,
                    chain.authority,
                    now,
                ),
                key,
                confirmation,
                Any(),
            )
        }
        assertCandidateError(ProductionC1CandidateCapabilityError.ROUTE_MISMATCH) {
            VerifiedProductionC1CandidateP2PInboundMaterial(
                chain.plan.selectedClientCandidate,
                "a".repeat(64),
                "b".repeat(64),
                "c".repeat(64),
                "d".repeat(64),
                chain.transcript.sessionId,
                Any(),
            )
        }

        val pair = ProductionPairStateSnapshot(chain.authority, 1uL)
        val ledger = ProductionC1EndpointGrantLedgerState(
            pairAuthorityDigest = chain.authority.digestHex(),
            pairLocalRevision = 1uL,
            remainingGrants = 1uL,
            retentionLimit = 8u,
        )
        val placeholder = ProductionC1EndpointGrantEntry(
            "1".repeat(64),
            "2".repeat(64),
            "3".repeat(64),
            "4".repeat(32),
            "5".repeat(64),
            "6".repeat(64),
            "8".repeat(64),
            "7".repeat(64),
            pair.digestHex(),
            2uL,
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.PERSISTENCE_UNAVAILABLE) {
            ProductionC1EndpointGrantAdmissionPreparation(
                ProductionC1CandidateCASDisposition.APPLIED,
                1uL,
                ledger.snapshotDigestHex(),
                pair.digestHex(),
                chain.grant.evidence.effectiveNotBeforeMs,
                chain.grant.evidence.expiresAtMs,
                ledger,
                pair,
                ProductionC1EndpointCompoundRecord(ledger, pair).digestHex(),
                ProductionC1EndpointCompoundRecord(ledger, pair),
                placeholder,
                Any(),
            )
        }
    }

    private fun admissionBinding(
        chain: CandidateEndpointChain,
        connectorInput: VerifiedProductionC1CandidateP2PConnectorInput,
        admissionId: String,
    ): String = ProductionC1EndpointGrantAdmission.bindingDigest(
        admissionId,
        chain.grant.evidence.digestHex(),
        sha256Hex(ProductionSecureSessionCodec.encode(chain.transcript)),
        sha256Hex(ProductionSecureSessionCodec.encode(chain.authorizations.finalP2PDirect)),
        chain.grant.grantAuthorization.digestHex,
        connectorInput.commitmentDigest,
    )

    private fun verifiedChain(fixture: CandidateFixture): CandidateEndpointChain {
        val root = fixture.root
        val objects = root.obj("objects")
        val artifacts = root.obj("artifacts")
        val now = root.obj("constants").ulong("nowMs")
        val keyset = ProductionC1ServiceKeyset.decode(
            objects.obj("serviceKeyset").hex("expectedCanonicalHex"),
        )
        val verifiedKeyset = ProductionC1Verifier.verifyServiceKeyset(
            keyset,
            keyset.serviceIdDigest,
            publicKey(root, "root"),
            keyset.keysetVersion,
            nowMs = now,
        )
        val authority = ProductionPairAuthorityState.decode(
            objects.obj("authority").hex("expectedCanonicalHex"),
        )
        val context = ProductionC1PreauthorizationSessionContext.decode(
            objects.obj("preauthorizationSessionContext").hex("expectedCanonicalHex"),
        )
        val capabilities = OPERATIONS.map { operation ->
            ProductionC1CandidateVerifier.verifyCapability(
                ProductionC1CandidateCapability.decode(
                    objects.obj(operation.capability).hex("expectedCanonicalHex"),
                ),
                artifacts.obj(operation.batch).hex("expectedCanonicalHex"),
                ProductionC1EndpointOperationProof.decode(
                    objects.obj(operation.proof).hex("expectedCanonicalHex"),
                ),
                context,
                authority,
                verifiedKeyset,
                now,
            )
        }
        val bilateral = ProductionC1CandidateVerifier.verifyBilateral(
            capabilities[0],
            capabilities[1],
            capabilities[2],
            capabilities[3],
            authority,
            now,
        )
        val clientBatch = P2pNatCanonicalCodec.decodeCandidateBatch(
            artifacts.obj("clientCandidateBatch").hex("expectedCanonicalHex"),
        )
        val runtimeBatch = P2pNatCanonicalCodec.decodeCandidateBatch(
            artifacts.obj("runtimeCandidateBatch").hex("expectedCanonicalHex"),
        )
        val plan = ProductionC1CandidateVerifier.verifyP2PDirectPlan(
            ProductionC1RoutePlanClaims.decode(
                objects.obj("p2pRoutePlan").hex("expectedCanonicalHex"),
            ),
            ProductionC1RouteCapability.decode(
                objects.obj("p2pRouteCapability").hex("expectedCanonicalHex"),
            ),
            context,
            bilateral,
            clientBatch.candidates.single(),
            runtimeBatch.candidates.single(),
            artifacts.obj("pathValidationReceipt").hex("expectedCanonicalHex"),
            authority,
            verifiedKeyset,
            nowMs = now,
        )
        val authorizations = ProductionC1CandidateVerifier.makeBilateralRouteAuthorizations(
            plan,
            authority,
            now,
        )
        val receipts = OPERATIONS.mapIndexed { index, operation ->
            ProductionC1CandidateOperationReceiptVerifier.verify(
                ProductionC1CandidateOperationReceipt.decode(
                    objects.obj(operation.receipt).hex("expectedCanonicalHex"),
                ),
                capabilities[index],
                authorizations.operationOrder[index],
                authority,
                verifiedKeyset,
                now,
            )
        }
        val evidence = ProductionC1P2PGrantEvidence.decode(
            objects.obj("p2pGrantEvidence").hex("expectedCanonicalHex"),
        )
        val grant = ProductionC1CandidateVerifier.verifyGrantEvidence(
            evidence,
            plan,
            authorizations,
            receipts,
            P2pNatRole.CLIENT,
            authority,
            now,
        )
        assertEquals(
            ProductionC1P2PGrantAuthorization.decode(
                objects.obj("p2pGrantAuthorization").hex("expectedCanonicalHex"),
            ),
            grant.grantAuthorization.authorization,
        )
        val transcript = ProductionSecureSessionCodec.decodeTranscript(
            objects.obj("candidateSecureSessionTranscript").hex("expectedCanonicalHex"),
        )
        return CandidateEndpointChain(
            authority,
            verifiedKeyset,
            context,
            capabilities,
            plan,
            authorizations,
            receipts,
            grant,
            transcript,
        )
    }

    private fun loadFixture(): CandidateFixture {
        val relative = Path.of(
            "shared",
            "protocol",
            "fixtures",
            "production-g1a-c-candidate-v1-vectors.json",
        )
        val starts = listOfNotNull(
            Path.of(System.getProperty("user.dir")).toAbsolutePath(),
            javaClass.protectionDomain?.codeSource?.location?.toURI()?.let(Path::of)?.toAbsolutePath(),
        )
        val path = starts.asSequence().flatMap { start ->
            generateSequence(if (Files.isDirectory(start)) start else start.parent) { it.parent }
        }.map { it.resolve(relative) }.firstOrNull(Files::isRegularFile)
            ?: error("shared production G1a-C candidate fixture not found")
        return CandidateFixture(
            Json.parseToJsonElement(String(Files.readAllBytes(path), Charsets.UTF_8)).jsonObject,
        )
    }

    private fun publicKey(root: JsonObject, name: String): PublicKey =
        KeyFactory.getInstance("EC").generatePublic(
            X509EncodedKeySpec(root.obj("keys").obj(name).hex("publicKeySPKIDERHex")),
        )

    private fun JsonObject.obj(name: String): JsonObject = getValue(name).jsonObject
    private fun JsonObject.array(name: String): JsonArray = getValue(name).jsonArray
    private fun JsonObject.string(name: String): String = getValue(name).jsonPrimitive.content
    private fun JsonObject.ulong(name: String): ULong = string(name).toULong()
    private fun JsonObject.hex(name: String): ByteArray = string(name).hex()

    private fun String.hex(): ByteArray {
        require(isNotEmpty() && length % 2 == 0 && all { it in '0'..'9' || it in 'a'..'f' })
        return chunked(2).map { it.toInt(16).toByte() }.toByteArray()
    }

    private fun ByteArray.lowerHex(): String = joinToString("") { byte ->
        (byte.toInt() and 0xff).toString(16).padStart(2, '0')
    }

    private fun sha256Hex(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(bytes).lowerHex()

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

    private data class CandidateFixture(val root: JsonObject)

    private data class Operation(
        val proof: String,
        val capability: String,
        val batch: String,
        val receipt: String,
    )

    private data class CandidateEndpointChain(
        val authority: ProductionPairAuthorityState,
        val verifiedKeyset: VerifiedProductionC1ServiceKeyset,
        val context: ProductionC1PreauthorizationSessionContext,
        val capabilities: List<VerifiedProductionC1CandidateCapability>,
        val plan: VerifiedProductionC1CandidateP2PPlan,
        val authorizations: ProductionC1BilateralRouteAuthorizations,
        val receipts: List<VerifiedProductionC1CandidateOperationReceipt>,
        val grant: VerifiedProductionC1P2PGrantEvidence,
        val transcript: ProductionSecureSessionTranscript,
    )

    private companion object {
        const val ADMISSION_ID =
            "9999999999999999999999999999999999999999999999999999999999999999"
        const val SWIFT_CONNECTOR_INPUT_COMMITMENT =
            "efcbf6460a9ba9a1cd0506dc5fa56a91c6d19990cb79422945c5c7c699f79213"
        const val SWIFT_RUNTIME_KEY_CONFIRMATION =
            "3e41f946378cdc361e81b20b883ee08e23eed0e76af40c08d0946d0f7a186172"
        const val SWIFT_CLIENT_KEY_CONFIRMATION =
            "b79f9ef3ec9d4efa966c620ea4a76f9603b3bdf8910f06271bb43c2b1fbca1e7"
        const val SWIFT_CLIENT_CONFIRMATION_DIGEST =
            "36deb548dc2230961271a21150b93397c213256255492ed54472350e44eaffe7"
        const val SWIFT_ADMISSION_BINDING =
            "c38f04eb96b4ec54da404a19703a868d38ce76def9cae33275572fb1b757cc78"
        const val SWIFT_LEDGER_SNAPSHOT_DIGEST =
            "d927e4eac47c1f22c55c84157d68696f16249d5e1e01c5b70cceef58651ebe56"
        const val SWIFT_ALC1EGL1_BYTES =
            "414c433145474c31000000020000000000000002" +
                "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" +
                "000000000000000200000000000000010000000800000001" +
                "1111111111111111111111111111111111111111111111111111111111111111" +
                "2222222222222222222222222222222222222222222222222222222222222222" +
                "3333333333333333333333333333333333333333333333333333333333333333" +
                "5555555555555555555555555555555555555555555555555555555555555555" +
                "6666666666666666666666666666666666666666666666666666666666666666" +
                "9999999999999999999999999999999999999999999999999999999999999999" +
                "7777777777777777777777777777777777777777777777777777777777777777" +
                "8888888888888888888888888888888888888888888888888888888888888888" +
                "3434343434343434343434343434343434343434343434343434343434343434" +
                "0000000000000002"

        val OPERATIONS = listOf(
            Operation("endpointProofClientPublish", "capabilityClientPublish", "clientCandidateBatch", "receiptClientPublish"),
            Operation("endpointProofRuntimeFetchClient", "capabilityRuntimeFetchClient", "clientCandidateBatch", "receiptRuntimeFetchClient"),
            Operation("endpointProofRuntimePublish", "capabilityRuntimePublish", "runtimeCandidateBatch", "receiptRuntimePublish"),
            Operation("endpointProofClientFetchRuntime", "capabilityClientFetchRuntime", "runtimeCandidateBatch", "receiptClientFetchRuntime"),
        )
    }
}
