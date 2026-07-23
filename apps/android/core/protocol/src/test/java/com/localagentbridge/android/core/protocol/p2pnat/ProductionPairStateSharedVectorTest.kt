package com.localagentbridge.android.core.protocol.p2pnat

import java.nio.file.Files
import java.nio.file.Path
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class ProductionPairStateSharedVectorTest {
    @Test
    fun authorityAndEmptySnapshotMatchSharedCanonicalVectors() {
        val fixture = loadFixture()
        assertEquals("aetherlink-production-pair-state-admission-v1-vectors", fixture.string("schema"))
        assertEquals(1, fixture.int("version"))
        assertEquals("ALS1", fixture.string("magic"))
        assertEquals(ProductionSecureSessionContract.SUITE, fixture.string("suite"))
        assertEquals(ProductionPairStateContract.PROFILE, fixture.string("profile"))

        val authorityVector = fixture.obj("authority")
        val authority = authority(authorityVector.obj("input"))
        val authorityBytes = authority.canonicalBytes()
        assertEquals(authorityVector.int("expectedCanonicalByteCount"), authorityBytes.size)
        assertArrayEquals(authorityVector.hex("expectedCanonicalHex"), authorityBytes)
        assertEquals(authorityVector.string("expectedSha256Hex"), authority.digestHex())
        assertEquals(authority, ProductionPairAuthorityState.decode(authorityBytes))

        val snapshotVector = fixture.obj("emptySnapshot")
        val snapshot = ProductionPairStateSnapshot(
            authority = authority,
            localRevision = snapshotVector.ulong("localRevision"),
        )
        val snapshotBytes = snapshot.canonicalBytes()
        assertEquals(snapshotVector.int("expectedCanonicalByteCount"), snapshotBytes.size)
        assertArrayEquals(snapshotVector.hex("expectedCanonicalHex"), snapshotBytes)
        assertEquals(snapshotVector.string("expectedSha256Hex"), snapshot.digestHex())
        assertEquals(snapshot, ProductionPairStateSnapshot.decode(snapshotBytes))
    }

    @Test
    fun localDirectAdmissionMatchesSharedSnapshotAndNonAuthorizingCommitment() {
        val fixture = loadFixture()
        val authority = authority(fixture.obj("authority").obj("input"))
        val empty = ProductionPairStateSnapshot(
            authority = authority,
            localRevision = fixture.obj("emptySnapshot").ulong("localRevision"),
        )
        val vector = fixture.obj("localDirectAdmission")
        val result = ProductionPairStateAdmission.admit(
            transcript = transcript(vector.obj("transcriptInput")),
            routeAuthorization = route(vector.obj("routeInput")),
            current = empty,
        )

        assertEquals(vector.int("expectedSnapshotByteCount"), result.snapshot.canonicalBytes().size)
        assertArrayEquals(vector.hex("expectedSnapshotCanonicalHex"), result.snapshot.canonicalBytes())
        assertEquals(vector.string("expectedSnapshotSha256Hex"), result.snapshot.digestHex())
        assertEquals(vector.string("expectedPermitBindingDigest"), result.bindingDigest)
        assertEquals(result.snapshot.authority.digestHex(), result.pairAuthorityDigest)
        assertEquals(result.snapshot.digestHex(), result.pairSnapshotDigest)
        assertEquals(
            ProductionSecureSessionCodec.digest(transcript(vector.obj("transcriptInput")))
                .joinToString("") { "%02x".format(it.toInt() and 0xff) },
            result.transcriptDigest,
        )
        assertTrue(
            ProductionPairStateAdmission::class.java.methods.none {
                it.returnType.simpleName.contains("Permit")
            },
        )
        assertEquals(2uL, result.snapshot.localRevision)
        assertEquals(1, result.snapshot.consumedEntries.size)
        assertEquals(result.snapshot, ProductionPairStateSnapshot.decode(vector.hex("expectedSnapshotCanonicalHex")))
    }

    @Test
    fun genericAdmissionRejectsAllP2pAuthorizationKindsUntilObject28() {
        val fixture = loadFixture()
        val authority = authority(fixture.obj("authority").obj("input"))
        val snapshot = ProductionPairStateSnapshot(
            authority = authority,
            localRevision = fixture.obj("emptySnapshot").ulong("localRevision"),
        )
        val baseTranscript = transcript(fixture.obj("localDirectAdmission").obj("transcriptInput"))
        val routes = listOf<ProductionRouteAuthorization>(
            P2pPublishRouteAuthorization(
                pairBindingDigest = authority.pairBindingDigest,
                pairEpoch = authority.pairEpoch,
                generation = authority.generation,
                candidateBatchDigest = "1".repeat(64),
                publishCapabilityDigest = "2".repeat(64),
            ),
            P2pFetchRouteAuthorization(
                pairBindingDigest = authority.pairBindingDigest,
                pairEpoch = authority.pairEpoch,
                generation = authority.generation,
                candidateBatchDigest = "3".repeat(64),
                fetchCapabilityDigest = "4".repeat(64),
            ),
            P2pDirectRouteAuthorization(
                pairBindingDigest = authority.pairBindingDigest,
                pairEpoch = authority.pairEpoch,
                generation = authority.generation,
                candidatePairDigest = "5".repeat(64),
                pathValidationReceiptDigest = "6".repeat(64),
                publishCapabilityDigest = "7".repeat(64),
                fetchCapabilityDigest = "8".repeat(64),
            ),
        )
        routes.forEach { route ->
            val transcript = ProductionSecureSessionTranscript(
                sessionId = baseTranscript.sessionId,
                pairBindingDigest = baseTranscript.pairBindingDigest,
                pairEpoch = baseTranscript.pairEpoch,
                clientIdentityFingerprint = baseTranscript.clientIdentityFingerprint,
                runtimeIdentityFingerprint = baseTranscript.runtimeIdentityFingerprint,
                clientEphemeralPublicKey = baseTranscript.clientEphemeralPublicKey,
                runtimeEphemeralPublicKey = baseTranscript.runtimeEphemeralPublicKey,
                clientNonce = baseTranscript.clientNonce,
                runtimeNonce = baseTranscript.runtimeNonce,
                generation = baseTranscript.generation,
                serviceConfigVersion = baseTranscript.serviceConfigVersion,
                keysetVersion = baseTranscript.keysetVersion,
                revocationCounter = baseTranscript.revocationCounter,
                protocolVersion = baseTranscript.protocolVersion,
                minimumProtocolVersion = baseTranscript.minimumProtocolVersion,
                profile = baseTranscript.profile,
                routeAuthorizationKind = route.kind,
                routeAuthorizationDigest = ProductionSecureSessionCodec.digest(route)
                    .joinToString("") { "%02x".format(it.toInt() and 0xff) },
            )
            assertReason(
                route.kind.wireValue,
                ProductionPairStateRejectionReason.ROUTE_AUTHORIZATION_MISMATCH,
            ) {
                ProductionPairStateAdmission.admit(transcript, route, snapshot)
            }
        }
    }

    @Test
    fun sharedTransitionCaseExpectations() {
        val fixture = loadFixture()
        val baseline = authority(fixture.obj("authority").obj("input"))
        val snapshot = ProductionPairStateSnapshot(
            authority = baseline,
            localRevision = fixture.obj("emptySnapshot").ulong("localRevision"),
        )

        fixture.array("transitionCases").forEach { raw ->
            val vector = raw.jsonObject
            when (vector.string("mutation")) {
                "genesis" -> {
                    val result = ProductionPairStateMachine.apply(
                        ProductionPairStateTransition(null, baseline),
                        null,
                    )
                    assertEquals(vector.string("id"), "applied", vector.string("expected"))
                    assertEquals(vector.string("id"), ProductionPairStateTransitionDisposition.APPLIED, result.disposition)
                    assertEquals(vector.string("id"), snapshot, result.snapshot)
                }
                "idempotent" -> {
                    val result = ProductionPairStateMachine.apply(
                        ProductionPairStateTransition(baseline.digestHex(), baseline),
                        snapshot,
                    )
                    assertEquals(vector.string("id"), "idempotent", vector.string("expected"))
                    assertEquals(vector.string("id"), ProductionPairStateTransitionDisposition.IDEMPOTENT, result.disposition)
                    assertEquals(vector.string("id"), snapshot, result.snapshot)
                }
                "generation_advance" -> {
                    val next = nextAuthority(baseline, generation = 8uL)
                    val result = ProductionPairStateMachine.apply(
                        ProductionPairStateTransition(baseline.digestHex(), next),
                        snapshot,
                    )
                    assertEquals(vector.string("id"), "applied", vector.string("expected"))
                    assertEquals(vector.string("id"), 8uL, result.snapshot.authority.generation)
                    assertEquals(vector.string("id"), 2uL, result.snapshot.localRevision)
                }
                "generation_rollback" -> {
                    assertEquals(vector.string("id"), "rejected", vector.string("expected"))
                    assertReason(vector.string("id"), ProductionPairStateRejectionReason.NON_MONOTONIC_GENERATION) {
                        ProductionPairStateMachine.apply(
                            ProductionPairStateTransition(
                                baseline.digestHex(),
                                nextAuthority(baseline, generation = 6uL),
                            ),
                            snapshot,
                        )
                    }
                }
                "revoke" -> {
                    val next = nextAuthority(
                        baseline,
                        revocationCounter = 3uL,
                        status = ProductionPairAuthorityStatus.REVOKED,
                    )
                    val result = ProductionPairStateMachine.apply(
                        ProductionPairStateTransition(baseline.digestHex(), next),
                        snapshot,
                    )
                    assertEquals(vector.string("id"), "applied", vector.string("expected"))
                    assertEquals(vector.string("id"), ProductionPairAuthorityStatus.REVOKED, result.snapshot.authority.status)
                }
                else -> error("unknown transition mutation ${vector.string("mutation")}")
            }
        }
    }

    @Test
    fun transitionHistoryRejectsPairLifetimeIdReuseAndRoundTripsCanonically() {
        val fixture = loadFixture()
        val baseline = authority(fixture.obj("authority").obj("input"))
        val initial = ProductionPairStateSnapshot(
            authority = baseline,
            localRevision = fixture.obj("emptySnapshot").ulong("localRevision"),
        )
        val second = nextAuthority(baseline, generation = baseline.generation + 1uL)
        val advanced = ProductionPairStateMachine.apply(
            ProductionPairStateTransition(baseline.digestHex(), second),
            initial,
        ).snapshot

        assertEquals(
            listOf(
                ProductionPairTransitionHistoryEntry(
                    transitionId = baseline.transitionId,
                    transitionRequestDigest = baseline.transitionRequestDigest,
                )
            ),
            advanced.transitionHistory,
        )
        assertEquals(734, advanced.canonicalBytes().size)
        assertEquals(
            "bf32cef0254efcc882a4fc370192bd339ea7076833c1514a0e6958ebfa5d6b96",
            advanced.digestHex(),
        )
        assertEquals(advanced, ProductionPairStateSnapshot.decode(advanced.canonicalBytes()))

        val reused = second.copy(
            generation = second.generation + 1uL,
            transitionId = baseline.transitionId,
            transitionRequestDigest = "9".repeat(64),
            acceptedReceiptDigest = "8".repeat(64),
            authorityRevision = second.authorityRevision + 1uL,
        )
        assertReason("pair-lifetime-transition-id-reuse", ProductionPairStateRejectionReason.TRANSITION_ID_CONFLICT) {
            ProductionPairStateMachine.apply(
                ProductionPairStateTransition(second.digestHex(), reused),
                advanced,
            )
        }
    }

    @Test
    fun epochAdvanceFailsClosedUntilSignedFreshPairProofExists() {
        val fixture = loadFixture()
        val baseline = authority(fixture.obj("authority").obj("input"))
        val snapshot = ProductionPairStateSnapshot(
            authority = baseline,
            localRevision = fixture.obj("emptySnapshot").ulong("localRevision"),
        )
        val proposed = nextAuthority(baseline, generation = baseline.generation + 1uL).copy(
            pairBindingDigest = "7".repeat(64),
            pairEpoch = baseline.pairEpoch + 1uL,
            clientIdentityFingerprint = "8".repeat(64),
            runtimeIdentityFingerprint = "9".repeat(64),
        )

        assertReason("epoch-advance-without-fresh-pair-proof", ProductionPairStateRejectionReason.INVALID_EPOCH_TRANSITION) {
            ProductionPairStateMachine.apply(
                ProductionPairStateTransition(baseline.digestHex(), proposed),
                snapshot,
            )
        }
    }

    @Test
    fun transitionHistoryCapacityCoexistsWithReplayCapacityAndFailsClosed() {
        val fixture = loadFixture()
        val baseline = authority(fixture.obj("authority").obj("input"))
        val sessions = (1..ProductionPairStateContract.MAX_CONSUMED_ENTRIES).map { index ->
            ProductionPairConsumedSession(
                sessionId = index.toString(16).padStart(32, '0'),
                transcriptDigest = (index + 1_000).toString(16).padStart(64, '0'),
            )
        }
        val history = (1..ProductionPairStateContract.MAX_TRANSITION_HISTORY_ENTRIES).map { index ->
            ProductionPairTransitionHistoryEntry(
                transitionId = index.toString(16).padStart(64, '0'),
                transitionRequestDigest = (index + 10_000).toString(16).padStart(64, '0'),
            )
        }
        val full = ProductionPairStateSnapshot(
            authority = baseline,
            localRevision = 1uL,
            consumedEntries = sessions,
            transitionHistory = history,
        )

        assertTrue(full.canonicalBytes().size <= ProductionPairStateContract.MAX_SNAPSHOT_BYTES)
        assertEquals(full, ProductionPairStateSnapshot.decode(full.canonicalBytes()))

        val next = nextAuthority(baseline, generation = baseline.generation + 1uL)
        assertReason(
            "transition-history-capacity",
            ProductionPairStateRejectionReason.TRANSITION_HISTORY_CAPACITY_EXHAUSTED,
        ) {
            ProductionPairStateMachine.apply(
                ProductionPairStateTransition(baseline.digestHex(), next),
                full,
            )
        }
    }

    @Test
    fun admissionPreservesTransitionHistory() {
        val fixture = loadFixture()
        val baseline = authority(fixture.obj("authority").obj("input"))
        val history = listOf(
            ProductionPairTransitionHistoryEntry(
                transitionId = "f".repeat(64),
                transitionRequestDigest = "1".repeat(64),
            )
        )
        val snapshot = ProductionPairStateSnapshot(
            authority = baseline,
            localRevision = 1uL,
            transitionHistory = history,
        )
        val admission = fixture.obj("localDirectAdmission")
        val admitted = ProductionPairStateAdmission.admit(
            transcript = transcript(admission.obj("transcriptInput")),
            routeAuthorization = route(admission.obj("routeInput")),
            current = snapshot,
        ).snapshot

        assertEquals(history, admitted.transitionHistory)
        assertEquals(admitted, ProductionPairStateSnapshot.decode(admitted.canonicalBytes()))
    }

    @Test
    fun sharedAdmissionAndMalformedCaseExpectations() {
        val fixture = loadFixture()
        val baseline = authority(fixture.obj("authority").obj("input"))
        val empty = ProductionPairStateSnapshot(
            authority = baseline,
            localRevision = fixture.obj("emptySnapshot").ulong("localRevision"),
        )
        val admission = fixture.obj("localDirectAdmission")
        val route = route(admission.obj("routeInput"))
        val transcript = transcript(admission.obj("transcriptInput"))
        val admitted = ProductionPairStateAdmission.admit(transcript, route, empty).snapshot

        fixture.array("admissionCases").forEach { raw ->
            val vector = raw.jsonObject
            when (vector.string("mutation")) {
                "none" -> {
                    assertEquals(vector.string("id"), "accepted", vector.string("expected"))
                    ProductionPairStateAdmission.admit(transcript, route, empty)
                }
                "replay" -> {
                    assertEquals(vector.string("id"), "rejected", vector.string("expected"))
                    assertReason(vector.string("id"), ProductionPairStateRejectionReason.SESSION_REPLAY) {
                        ProductionPairStateAdmission.admit(transcript, route, admitted)
                    }
                }
                "revoked" -> {
                    val revoked = ProductionPairStateSnapshot(
                        authority = baseline.copy(status = ProductionPairAuthorityStatus.REVOKED),
                        localRevision = 1uL,
                    )
                    assertEquals(vector.string("id"), "rejected", vector.string("expected"))
                    assertReason(vector.string("id"), ProductionPairStateRejectionReason.REVOKED_PAIR) {
                        ProductionPairStateAdmission.admit(transcript, route, revoked)
                    }
                }
                "persisted_epoch_mismatch" -> {
                    val future = ProductionPairStateSnapshot(
                        authority = baseline.copy(pairEpoch = 10uL),
                        localRevision = 1uL,
                    )
                    assertEquals(vector.string("id"), "rejected", vector.string("expected"))
                    assertReason(vector.string("id"), ProductionPairStateRejectionReason.PAIR_EPOCH_MISMATCH) {
                        ProductionPairStateAdmission.admit(transcript, route, future)
                    }
                }
                "route_digest_mismatch" -> {
                    val wrongRoute = LocalDirectRouteAuthorization(
                        pairBindingDigest = route.pairBindingDigest,
                        pairEpoch = route.pairEpoch,
                        nominatedPathReceiptDigest = "2".repeat(64),
                    )
                    assertEquals(vector.string("id"), "rejected", vector.string("expected"))
                    assertReason(vector.string("id"), ProductionPairStateRejectionReason.ROUTE_AUTHORIZATION_MISMATCH) {
                        ProductionPairStateAdmission.admit(transcript, wrongRoute, empty)
                    }
                }
                "capacity" -> {
                    val entries = (1..ProductionPairStateContract.MAX_CONSUMED_ENTRIES).map { index ->
                        ProductionPairConsumedSession(
                            sessionId = index.toString(16).padStart(32, '0'),
                            transcriptDigest = (index + 1_000).toString(16).padStart(64, '0'),
                        )
                    }
                    val full = ProductionPairStateSnapshot(baseline, 1uL, entries)
                    assertEquals(vector.string("id"), "rejected", vector.string("expected"))
                    assertReason(vector.string("id"), ProductionPairStateRejectionReason.REPLAY_CAPACITY_EXHAUSTED) {
                        ProductionPairStateAdmission.admit(transcript, route, full)
                    }
                }
                "malformed_authority" -> {
                    assertEquals(vector.string("id"), "rejected", vector.string("expected"))
                    assertReason(vector.string("id"), ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE) {
                        ProductionPairAuthorityState.decode(baseline.canonicalBytes() + byteArrayOf(0))
                    }
                }
                else -> error("unknown admission mutation ${vector.string("mutation")}")
            }
        }
    }

    private fun authority(input: JsonObject): ProductionPairAuthorityState = ProductionPairAuthorityState(
        pairBindingDigest = input.string("pairBindingDigest"),
        pairEpoch = input.ulong("pairEpoch"),
        clientIdentityFingerprint = input.string("clientIdentityFingerprint"),
        runtimeIdentityFingerprint = input.string("runtimeIdentityFingerprint"),
        generation = input.ulong("generation"),
        serviceConfigVersion = input.ulong("serviceConfigVersion"),
        keysetVersion = input.ulong("keysetVersion"),
        revocationCounter = input.ulong("revocationCounter"),
        protocolFloor = input.uint("protocolFloor"),
        status = ProductionPairAuthorityStatus.entries.single { it.wireValue == input.string("status") },
        transitionId = input.string("transitionId"),
        transitionRequestDigest = input.string("transitionRequestDigest"),
        acceptedReceiptDigest = input.string("acceptedReceiptDigest"),
        authorityRevision = input.ulong("authorityRevision"),
    )

    private fun route(input: JsonObject): LocalDirectRouteAuthorization {
        require(input.string("suite") == ProductionSecureSessionContract.SUITE)
        return LocalDirectRouteAuthorization(
            pairBindingDigest = input.string("pairBindingDigest"),
            pairEpoch = input.ulong("pairEpoch"),
            nominatedPathReceiptDigest = input.string("nominatedPathReceiptDigest"),
        )
    }

    private fun transcript(input: JsonObject): ProductionSecureSessionTranscript {
        require(input.string("suite") == ProductionSecureSessionContract.SUITE)
        require(input.string("clientRole") == "client" && input.string("runtimeRole") == "runtime")
        require(input.uint("protocolVersion") == 1u && input.uint("minimumProtocolVersion") == 1u)
        require(input.string("cryptographicProfile") == ProductionSecureSessionContract.PROFILE)
        return ProductionSecureSessionTranscript(
            sessionId = input.string("sessionId"),
            pairBindingDigest = input.string("pairBindingDigest"),
            pairEpoch = input.ulong("pairEpoch"),
            clientIdentityFingerprint = input.string("clientIdentityFingerprint"),
            runtimeIdentityFingerprint = input.string("runtimeIdentityFingerprint"),
            clientEphemeralPublicKey = input.hex("clientEphemeralPublicKeyHex"),
            runtimeEphemeralPublicKey = input.hex("runtimeEphemeralPublicKeyHex"),
            clientNonce = input.string("clientNonce"),
            runtimeNonce = input.string("runtimeNonce"),
            generation = input.ulong("generation"),
            serviceConfigVersion = input.ulong("serviceConfigVersion"),
            keysetVersion = input.ulong("keysetVersion"),
            revocationCounter = input.ulong("revocationCounter"),
            protocolVersion = input.uint("protocolVersion"),
            minimumProtocolVersion = input.uint("minimumProtocolVersion"),
            profile = input.string("cryptographicProfile"),
            routeAuthorizationKind = ProductionRouteAuthorizationKind.decode(input.string("routeKind")),
            routeAuthorizationDigest = input.string("routeAuthorizationDigest"),
        )
    }

    private fun nextAuthority(
        baseline: ProductionPairAuthorityState,
        generation: ULong = baseline.generation,
        revocationCounter: ULong = baseline.revocationCounter,
        status: ProductionPairAuthorityStatus = baseline.status,
    ): ProductionPairAuthorityState = baseline.copy(
        generation = generation,
        revocationCounter = revocationCounter,
        status = status,
        transitionId = "f".repeat(64),
        transitionRequestDigest = "1".repeat(64),
        acceptedReceiptDigest = "2".repeat(64),
        authorityRevision = 2uL,
    )

    private fun assertReason(
        id: String,
        expected: ProductionPairStateRejectionReason,
        block: () -> Unit,
    ) {
        val error = assertThrows(id, ProductionPairStateException::class.java, block)
        assertEquals(id, expected, error.reason)
    }

    private fun loadFixture(): JsonObject {
        val relative = Path.of(
            "shared", "protocol", "fixtures", "production-pair-state-admission-v1-vectors.json",
        )
        val starts = listOfNotNull(
            Path.of(System.getProperty("user.dir")).toAbsolutePath(),
            javaClass.protectionDomain?.codeSource?.location?.toURI()?.let(Path::of)?.toAbsolutePath(),
        )
        val fixture = starts.asSequence().flatMap { start ->
            generateSequence(if (Files.isDirectory(start)) start else start.parent) { it.parent }
        }.map { it.resolve(relative) }.firstOrNull(Files::isRegularFile)
            ?: error("shared production pair-state fixture not found from repository ancestors")
        return Json.parseToJsonElement(String(Files.readAllBytes(fixture), Charsets.UTF_8)).jsonObject
    }

    private fun JsonObject.obj(name: String): JsonObject = getValue(name).jsonObject
    private fun JsonObject.array(name: String): JsonArray = getValue(name).jsonArray
    private fun JsonObject.string(name: String): String = getValue(name).jsonPrimitive.content
    private fun JsonObject.ulong(name: String): ULong = string(name).toULong()
    private fun JsonObject.uint(name: String): UInt = string(name).toUInt()
    private fun JsonObject.int(name: String): Int = string(name).toInt()
    private fun JsonObject.hex(name: String): ByteArray = string(name).hex()

    private fun String.hex(): ByteArray {
        require(isNotEmpty() && length % 2 == 0 && all { it in '0'..'9' || it in 'a'..'f' })
        return chunked(2).map { it.toInt(16).toByte() }.toByteArray()
    }
}
