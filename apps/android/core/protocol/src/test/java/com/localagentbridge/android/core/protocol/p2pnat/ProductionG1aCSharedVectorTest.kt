package com.localagentbridge.android.core.protocol.p2pnat

import java.math.BigInteger
import java.nio.ByteBuffer
import java.nio.ByteOrder
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
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class ProductionG1aCSharedVectorTest {
    @Test
    fun schemaConstantsNamespaceAndEveryCanonicalObjectMatch() {
        val fixture = loadFixture()
        assertEquals("aetherlink-production-g1a-c-v1-vectors", fixture.string("schema"))
        assertEquals(1, fixture.int("version"))
        assertEquals("ALS1", fixture.string("magic"))
        assertEquals(ProductionC1Contract.SUITE, fixture.string("suite"))
        assertEquals(ProductionSecureSessionContract.SUITE, fixture.string("secureSessionSuite"))
        assertEquals(ProductionC1Contract.SIGNATURE_ALGORITHM, fixture.string("signatureAlgorithm"))
        assertEquals("python-stdlib-rfc6979-sha256-test-only-v1", fixture.string("generationProfile"))

        val constants = fixture.obj("constants")
        assertEquals(1_000_000uL, constants.ulong("nowMs"))
        assertEquals(1uL, constants.ulong("minimumAcceptedKeysetVersion"))
        assertEquals(ProductionC1Contract.MAXIMUM_CLOCK_SKEW_MS, constants.ulong("maximumClockSkewMs"))
        assertEquals(ProductionC1Contract.MAXIMUM_KEYSET_LIFETIME_MS, constants.ulong("maximumKeysetLifetimeMs"))
        assertEquals(ProductionC1Contract.MAXIMUM_STATUS_LIFETIME_MS, constants.ulong("maximumStatusLifetimeMs"))
        assertEquals(
            ProductionC1Contract.MAXIMUM_FRESH_PAIR_LIFETIME_MS,
            constants.ulong("maximumFreshPairLifetimeMs"),
        )
        assertEquals(ProductionC1Contract.MAXIMUM_ROUTE_LIFETIME_MS, constants.ulong("maximumRouteLifetimeMs"))
        assertEquals(1u, constants.uint("protocolVersion"))
        assertEquals(1u, constants.uint("minimumProtocolVersion"))
        assertEquals(ProductionSecureSessionContract.PROFILE, constants.string("profile"))

        assertEquals(listOf(19), fixture.array("reservedObjectTypes").map { it.jsonPrimitive.content.toInt() })
        val objects = fixture.obj("objects")
        val objectTypes = objects.values.map { it.jsonObject.int("objectType") }.toSet()
        assertEquals(
            setOf(7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 20, 21, 22),
            objectTypes,
        )
        assertTrue(19 !in objectTypes)
        assertEquals(ProductionC1Contract.SERVICE_KEYSET_OBJECT_TYPE, 10)
        assertEquals(ProductionC1Contract.PAIR_STATUS_OBJECT_TYPE, 11)
        assertEquals(ProductionC1Contract.FRESH_PAIR_PROOF_OBJECT_TYPE, 12)
        assertEquals(ProductionC1Contract.ROUTE_CAPABILITY_OBJECT_TYPE, 13)
        assertEquals(ProductionC1Contract.ROUTE_PLAN_OBJECT_TYPE, 14)
        assertEquals(ProductionC1Contract.P2P_CONNECTOR_OBJECT_TYPE, 15)
        assertEquals(ProductionC1Contract.TURN_CONNECTOR_OBJECT_TYPE, 16)
        assertEquals(ProductionC1Contract.SEALED_RELAY_CONNECTOR_OBJECT_TYPE, 17)
        assertEquals(ProductionC1Contract.PREAUTHORIZATION_SESSION_CONTEXT_OBJECT_TYPE, 18)
        assertEquals(ProductionC1Contract.P2P_ROUTE_AUTHORIZATION_OBJECT_TYPE, 20)
        assertEquals(ProductionC1Contract.TURN_ROUTE_AUTHORIZATION_OBJECT_TYPE, 21)
        assertEquals(ProductionC1Contract.SEALED_RELAY_ROUTE_AUTHORIZATION_OBJECT_TYPE, 22)

        objects.forEach { (name, raw) ->
            val vector = raw.jsonObject
            val expected = vector.hex("expectedCanonicalHex")
            val objectType = vector.int("objectType")
            val reencoded = decodeAndReencode(objectType, expected)
            assertEquals(name, objectType, expected[4].toInt() and 0xff)
            assertEquals(name, vector.int("expectedCanonicalByteCount"), expected.size)
            assertArrayEquals(name, expected, reencoded)
            assertEquals(name, vector.string("expectedSha256Hex"), sha256Hex(reencoded))
        }
    }

    @Test
    fun fixedSignaturesRecoveryCommitmentsAndFreshApplyMatch() {
        val fixture = loadFixture()
        val objects = fixture.obj("objects")
        val constants = fixture.obj("constants")
        val keyset = ProductionC1ServiceKeyset.decode(objects.obj("serviceKeyset").hex("expectedCanonicalHex"))
        assertArrayEquals(
            objects.obj("serviceKeyset").array("signatures")[0].jsonObject.hex("fixedLowSDERSignatureHex"),
            keyset.rootSignature,
        )
        val verifiedKeyset = ProductionC1Verifier.verifyServiceKeyset(
            keyset,
            keyset.serviceIdDigest,
            publicKey(fixture, "root"),
            constants.ulong("minimumAcceptedKeysetVersion"),
            nowMs = constants.ulong("nowMs"),
        )

        val previousSnapshot = ProductionPairStateSnapshot.decode(
            objects.obj("previousSnapshot").hex("expectedCanonicalHex")
        )
        val status = ProductionC1PairStatus.decode(objects.obj("pairStatus").hex("expectedCanonicalHex"))
        assertArrayEquals(
            objects.obj("pairStatus").array("signatures")[0].jsonObject.hex("fixedLowSDERSignatureHex"),
            status.serviceSignature,
        )
        val verifiedStatus = ProductionC1Verifier.verifyPairStatus(
            status,
            keyset.serviceIdDigest,
            ProductionC1RequesterRole.RUNTIME,
            status.requestNonce,
            previousSnapshot,
            verifiedKeyset,
            constants.ulong("nowMs"),
        )

        val synthetic = fixture.obj("syntheticMaterials")
        assertTrue(synthetic.boolean("testOnly"))
        val previousCommitments = ProductionC1RecoveryCommitments.currentToken(
            previousSnapshot.authority.pairBindingDigest,
            synthetic.hex("previousEndpointTrafficSecretHex"),
            synthetic.hex("previousRouteTokenSeedHex"),
        )
        val expectedPrevious = fixture.obj("derived").obj("previousRecoveryCommitments")
        assertEquals(
            expectedPrevious.string("endpointTrafficSecretCommitment"),
            previousCommitments.endpointTrafficSecretCommitment,
        )
        assertEquals(
            expectedPrevious.string("routeTokenSeedCommitment"),
            previousCommitments.routeTokenSeedCommitment,
        )
        assertEquals(
            expectedPrevious.string("endpointTrafficSecretReuseDigest"),
            previousCommitments.endpointTrafficSecretReuseDigest,
        )
        assertEquals(
            expectedPrevious.string("routeTokenSeedReuseDigest"),
            previousCommitments.routeTokenSeedReuseDigest,
        )
        val expectedNext = fixture.obj("derived").obj("nextRecoveryCommitments")
        assertEquals(
            expectedNext.string("endpointTrafficSecretCommitment"),
            ProductionC1RecoveryCommitments.endpointTrafficSecret(
                previousSnapshot.authority.pairBindingDigest,
                synthetic.hex("nextEndpointTrafficSecretHex"),
            ),
        )
        assertEquals(
            expectedNext.string("routeTokenSeedCommitment"),
            ProductionC1RecoveryCommitments.routeTokenSeed(
                previousSnapshot.authority.pairBindingDigest,
                synthetic.hex("nextRouteTokenSeedHex"),
            ),
        )
        assertEquals(
            expectedNext.string("endpointTrafficSecretReuseDigest"),
            ProductionC1RecoveryCommitments.materialReuseDigest(
                previousSnapshot.authority.pairBindingDigest,
                synthetic.hex("nextEndpointTrafficSecretHex"),
            ),
        )
        assertEquals(
            expectedNext.string("routeTokenSeedReuseDigest"),
            ProductionC1RecoveryCommitments.materialReuseDigest(
                previousSnapshot.authority.pairBindingDigest,
                synthetic.hex("nextRouteTokenSeedHex"),
            ),
        )

        val proof = ProductionC1FreshPairProof.decode(objects.obj("freshPairProof").hex("expectedCanonicalHex"))
        val proofSignatures = objects.obj("freshPairProof").array("signatures")
        assertArrayEquals(proofSignatures[0].jsonObject.hex("fixedLowSDERSignatureHex"), proof.survivorSignature)
        assertArrayEquals(proofSignatures[1].jsonObject.hex("fixedLowSDERSignatureHex"), proof.replacementSignature)
        val verified = ProductionC1Verifier.verifyFreshPairProof(
            proof,
            verifiedStatus,
            previousSnapshot,
            previousCommitments,
            publicKey(fixture, "survivorRuntimeIdentity"),
            publicKey(fixture, "replacementClientIdentity"),
            constants.ulong("nowMs"),
        )
        val derived = fixture.obj("derived")
        assertEquals(derived.string("freshPairTransitionRequestDigest"), proof.transitionRequestDigest)
        assertEquals(derived.string("freshPairProofDigest"), proof.digestHex())

        val applied = ProductionC1FreshPairStateMachine.apply(
            verified,
            previousSnapshot,
            constants.ulong("nowMs"),
        )
        val expectedSnapshot = ProductionPairStateSnapshot.decode(
            objects.obj("nextSnapshot").hex("expectedCanonicalHex")
        )
        assertEquals(ProductionPairStateTransitionDisposition.APPLIED, applied.disposition)
        assertEquals(expectedSnapshot, applied.snapshot)
        assertArrayEquals(objects.obj("nextSnapshot").hex("expectedCanonicalHex"), applied.snapshot.canonicalBytes())
        assertEquals(derived.string("nextSnapshotDigest"), applied.snapshot.digestHex())
        val idempotent = ProductionC1FreshPairStateMachine.apply(
            verified,
            applied.snapshot,
            constants.ulong("nowMs"),
        )
        assertEquals(ProductionPairStateTransitionDisposition.IDEMPOTENT, idempotent.disposition)
        assertEquals(expectedSnapshot, idempotent.snapshot)
    }

    @Test
    fun fixedRouteChainAndDurableAdmissionMatch() {
        val fixture = loadFixture()
        val route = verifiedRoute(fixture)
        val objects = fixture.obj("objects")
        val derived = fixture.obj("derived")

        assertEquals(
            route.context,
            ProductionC1PreauthorizationSessionContext(route.transcript),
        )
        assertEquals(derived.string("preauthorizationSessionContextDigest"), route.context.digestHex())
        assertArrayEquals(
            objects.obj("routeCapability").array("signatures")[0].jsonObject.hex("fixedLowSDERSignatureHex"),
            route.capability.serviceSignature,
        )
        assertArrayEquals(
            objects.obj("turnRouteAuthorization").hex("expectedCanonicalHex"),
            route.authorization.canonicalBytes,
        )
        assertEquals(derived.string("turnRouteAuthorizationDigest"), route.authorization.digestHex)
        assertEquals(derived.string("connectorInputCommitmentDigest"), route.connectorInput.commitmentDigest)

        val admitted = ProductionC1PairStateAdmission.admit(
            route.binding,
            route.initialSnapshot,
        )
        val expectedSnapshot = ProductionPairStateSnapshot.decode(
            objects.obj("admittedSnapshot").hex("expectedCanonicalHex")
        )
        assertEquals(expectedSnapshot, admitted.nextSnapshot)
        assertArrayEquals(objects.obj("admittedSnapshot").hex("expectedCanonicalHex"), admitted.nextSnapshot.canonicalBytes())
        assertEquals(derived.string("admittedSnapshotDigest"), admitted.nextSnapshot.digestHex())
        assertEquals(derived.string("durableAdmissionPermitDigest"), admitted.bindingDigest)
        assertPairStateError(ProductionPairStateRejectionReason.SESSION_REPLAY) {
            ProductionC1PairStateAdmission.admit(
                route.binding,
                admitted.nextSnapshot,
            )
        }
    }

    @Test
    fun platformMutationsFailClosed() {
        val fixture = loadFixture()
        val objects = fixture.obj("objects")
        val keysetBytes = objects.obj("serviceKeyset").hex("expectedCanonicalHex")
        val reordered = keysetBytes.copyOf().also {
            it[tagOffset(it, 1)] = 2
            it[tagOffset(it, 2)] = 1
        }
        assertC1Error(ProductionC1Error.MALFORMED_CANONICAL) {
            ProductionC1ServiceKeyset.decode(reordered)
        }
        assertC1Error(ProductionC1Error.HIGH_S) {
            ProductionC1ServiceKeyset.decode(
                replacingFields(keysetBytes, mapOf(11 to makeHighS(fieldValue(keysetBytes, 11))))
            )
        }
        assertC1Error(ProductionC1Error.MALFORMED_CANONICAL) {
            ProductionC1RouteConnectorMaterial.decode(
                objects.obj("turnConnector").hex("expectedCanonicalHex") + byteArrayOf(0)
            )
        }

        val fresh = verifiedFresh(fixture)
        val proofBytes = fresh.proof.canonicalBytes()
        val mutatedQrProof = ProductionC1FreshPairProof.decode(
            replacingFields(
                proofBytes,
                mapOf(21 to "abababababababababababababababababababababababababababababababab".toByteArray()),
            )
        )
        assertC1Error(ProductionC1Error.INVALID_SIGNATURE) {
            ProductionC1Verifier.verifyFreshPairProof(
                mutatedQrProof,
                fresh.status,
                fresh.previousSnapshot,
                fresh.currentCommitments,
                fresh.survivorPublicKey,
                fresh.replacementPublicKey,
                fixture.obj("constants").ulong("nowMs"),
            )
        }

        val route = verifiedRoute(fixture)
        assertC1Error(ProductionC1Error.ROUTE_MISMATCH) {
            ProductionC1Verifier.verifyRoutePlan(
                route.claims.copy(securityContextDigest = "0".repeat(64)),
                route.capability,
                route.context,
                route.authority,
                route.verifiedKeyset,
                fixture.obj("constants").ulong("nowMs"),
            )
        }
        val wrongSecret = fixture.obj("syntheticMaterials").hex("connectorSecretHex").also { it[0] = 0 }
        assertC1Error(ProductionC1Error.ROUTE_MISMATCH) {
            ProductionC1Verifier.verifyConnectorInput(
                route.plan,
                fixture.obj("syntheticMaterials").string("routeHandle"),
                fixture.obj("syntheticMaterials").string("connectorNonce"),
                wrongSecret,
                fixture.obj("constants").ulong("nowMs"),
            )
        }
        assertC1Error(ProductionC1Error.EXPIRED) {
            ProductionC1Verifier.makeRouteAuthorization(route.plan, route.claims.expiresAtMs)
        }
        val admitted = ProductionC1PairStateAdmission.admit(
            route.binding,
            route.initialSnapshot,
        )
        assertPairStateError(ProductionPairStateRejectionReason.SESSION_REPLAY) {
            ProductionC1PairStateAdmission.admit(
                route.binding,
                admitted.nextSnapshot,
            )
        }
    }

    private data class FreshVerification(
        val proof: ProductionC1FreshPairProof,
        val status: VerifiedProductionC1PairStatus,
        val previousSnapshot: ProductionPairStateSnapshot,
        val currentCommitments: ProductionC1CurrentRecoveryCommitments,
        val survivorPublicKey: PublicKey,
        val replacementPublicKey: PublicKey,
    )

    private data class RouteVerification(
        val verifiedKeyset: VerifiedProductionC1ServiceKeyset,
        val authority: ProductionPairAuthorityState,
        val context: ProductionC1PreauthorizationSessionContext,
        val claims: ProductionC1RoutePlanClaims,
        val capability: ProductionC1RouteCapability,
        val plan: VerifiedProductionC1RoutePlan,
        val authorization: VerifiedProductionC1RouteAuthorization,
        val connectorInput: VerifiedProductionC1ConnectorInput,
        val transcript: ProductionSecureSessionTranscript,
        val binding: VerifiedProductionC1TranscriptBinding,
        val initialSnapshot: ProductionPairStateSnapshot,
    )

    private fun verifiedFresh(fixture: JsonObject): FreshVerification {
        val objects = fixture.obj("objects")
        val constants = fixture.obj("constants")
        val keyset = ProductionC1ServiceKeyset.decode(objects.obj("serviceKeyset").hex("expectedCanonicalHex"))
        val verifiedKeyset = ProductionC1Verifier.verifyServiceKeyset(
            keyset,
            keyset.serviceIdDigest,
            publicKey(fixture, "root"),
            constants.ulong("minimumAcceptedKeysetVersion"),
            nowMs = constants.ulong("nowMs"),
        )
        val previousSnapshot = ProductionPairStateSnapshot.decode(
            objects.obj("previousSnapshot").hex("expectedCanonicalHex")
        )
        val status = ProductionC1PairStatus.decode(objects.obj("pairStatus").hex("expectedCanonicalHex"))
        val verifiedStatus = ProductionC1Verifier.verifyPairStatus(
            status,
            keyset.serviceIdDigest,
            ProductionC1RequesterRole.RUNTIME,
            status.requestNonce,
            previousSnapshot,
            verifiedKeyset,
            constants.ulong("nowMs"),
        )
        val synthetic = fixture.obj("syntheticMaterials")
        val commitments = ProductionC1RecoveryCommitments.currentToken(
            previousSnapshot.authority.pairBindingDigest,
            synthetic.hex("previousEndpointTrafficSecretHex"),
            synthetic.hex("previousRouteTokenSeedHex"),
        )
        return FreshVerification(
            ProductionC1FreshPairProof.decode(objects.obj("freshPairProof").hex("expectedCanonicalHex")),
            verifiedStatus,
            previousSnapshot,
            commitments,
            publicKey(fixture, "survivorRuntimeIdentity"),
            publicKey(fixture, "replacementClientIdentity"),
        )
    }

    private fun verifiedRoute(fixture: JsonObject): RouteVerification {
        val objects = fixture.obj("objects")
        val constants = fixture.obj("constants")
        val keyset = ProductionC1ServiceKeyset.decode(objects.obj("serviceKeyset").hex("expectedCanonicalHex"))
        val verifiedKeyset = ProductionC1Verifier.verifyServiceKeyset(
            keyset,
            keyset.serviceIdDigest,
            publicKey(fixture, "root"),
            constants.ulong("minimumAcceptedKeysetVersion"),
            nowMs = constants.ulong("nowMs"),
        )
        val authority = ProductionPairAuthorityState.decode(objects.obj("nextAuthority").hex("expectedCanonicalHex"))
        val context = ProductionC1PreauthorizationSessionContext.decode(
            objects.obj("preauthorizationSessionContext").hex("expectedCanonicalHex")
        )
        val claims = ProductionC1RoutePlanClaims.decode(objects.obj("routePlan").hex("expectedCanonicalHex"))
        val capability = ProductionC1RouteCapability.decode(
            objects.obj("routeCapability").hex("expectedCanonicalHex")
        )
        val plan = ProductionC1Verifier.verifyRoutePlan(
            claims,
            capability,
            context,
            authority,
            verifiedKeyset,
            constants.ulong("nowMs"),
        )
        val authorization = ProductionC1Verifier.makeRouteAuthorization(plan, constants.ulong("nowMs"))
        val synthetic = fixture.obj("syntheticMaterials")
        val connectorInput = ProductionC1Verifier.verifyConnectorInput(
            plan,
            synthetic.string("routeHandle"),
            synthetic.string("connectorNonce"),
            synthetic.hex("connectorSecretHex"),
            constants.ulong("nowMs"),
        )
        val transcript = ProductionSecureSessionCodec.decodeTranscript(
            objects.obj("secureSessionTranscript").hex("expectedCanonicalHex")
        )
        val binding = ProductionC1Verifier.verifyTranscriptBinding(
            transcript,
            authorization,
            plan,
            connectorInput,
            authority,
            constants.ulong("nowMs"),
        )
        return RouteVerification(
            verifiedKeyset,
            authority,
            context,
            claims,
            capability,
            plan,
            authorization,
            connectorInput,
            transcript,
            binding,
            ProductionPairStateSnapshot.decode(objects.obj("nextSnapshot").hex("expectedCanonicalHex")),
        )
    }

    private fun decodeAndReencode(objectType: Int, bytes: ByteArray): ByteArray = when (objectType) {
        7 -> ProductionSecureSessionCodec.encode(ProductionSecureSessionCodec.decodeTranscript(bytes))
        8 -> ProductionPairAuthorityState.decode(bytes).canonicalBytes()
        9 -> ProductionPairStateSnapshot.decode(bytes).canonicalBytes()
        10 -> ProductionC1ServiceKeyset.decode(bytes).canonicalBytes()
        11 -> ProductionC1PairStatus.decode(bytes).canonicalBytes()
        12 -> ProductionC1FreshPairProof.decode(bytes).canonicalBytes()
        13 -> ProductionC1RouteCapability.decode(bytes).canonicalBytes()
        14 -> ProductionC1RoutePlanClaims.decode(bytes).canonicalBytes()
        15, 16, 17 -> ProductionC1RouteConnectorMaterial.decode(bytes).canonicalBytes()
        18 -> ProductionC1PreauthorizationSessionContext.decode(bytes).canonicalBytes()
        20, 21, 22 -> ProductionC1RouteAuthorization.decode(bytes).canonicalBytes()
        else -> error("unsupported shared object type $objectType")
    }

    private fun publicKey(fixture: JsonObject, name: String): PublicKey =
        KeyFactory.getInstance("EC").generatePublic(
            X509EncodedKeySpec(fixture.obj("keys").obj(name).hex("publicKeySPKIDERHex"))
        )

    private fun assertC1Error(expected: ProductionC1Error, body: () -> Unit) {
        val error = assertThrows(ProductionC1Exception::class.java, body)
        assertEquals(expected, error.reason)
    }

    private fun assertPairStateError(expected: ProductionPairStateRejectionReason, body: () -> Unit) {
        val error = assertThrows(ProductionPairStateException::class.java, body)
        assertEquals(expected, error.reason)
    }

    private fun makeHighS(der: ByteArray): ByteArray {
        val (r, s) = parseDer(der)
        return encodeDer(r, P256_ORDER - s)
    }

    private fun parseDer(der: ByteArray): Pair<BigInteger, BigInteger> {
        var offset = 2
        fun integer(): BigInteger {
            require(der[offset++] == 0x02.toByte())
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

    private fun tagOffset(encoded: ByteArray, fieldNumber: Int): Int {
        var offset = 6
        repeat(fieldNumber - 1) {
            val length = ByteBuffer.wrap(encoded, offset + 1, 4).order(ByteOrder.BIG_ENDIAN).int
            offset += 5 + length
        }
        return offset
    }

    private fun fieldValue(encoded: ByteArray, fieldNumber: Int): ByteArray {
        val tag = tagOffset(encoded, fieldNumber)
        val length = ByteBuffer.wrap(encoded, tag + 1, 4).order(ByteOrder.BIG_ENDIAN).int
        return encoded.copyOfRange(tag + 5, tag + 5 + length)
    }

    private fun replacingFields(encoded: ByteArray, replacements: Map<Int, ByteArray>): ByteArray {
        var offset = 6
        var output = encoded.copyOfRange(0, offset)
        while (offset < encoded.size) {
            val tag = encoded[offset].toInt() and 0xff
            val length = ByteBuffer.wrap(encoded, offset + 1, 4).order(ByteOrder.BIG_ENDIAN).int
            val original = encoded.copyOfRange(offset + 5, offset + 5 + length)
            val value = replacements[tag] ?: original
            output += byteArrayOf(tag.toByte())
            output += ByteBuffer.allocate(4).order(ByteOrder.BIG_ENDIAN).putInt(value.size).array()
            output += value
            offset += 5 + length
        }
        return output
    }

    private fun loadFixture(): JsonObject {
        val relative = Path.of(
            "shared", "protocol", "fixtures", "production-g1a-c-v1-vectors.json",
        )
        val starts = listOfNotNull(
            Path.of(System.getProperty("user.dir")).toAbsolutePath(),
            javaClass.protectionDomain?.codeSource?.location?.toURI()?.let(Path::of)?.toAbsolutePath(),
        )
        val fixture = starts.asSequence().flatMap { start ->
            generateSequence(if (Files.isDirectory(start)) start else start.parent) { it.parent }
        }.map { it.resolve(relative) }.firstOrNull(Files::isRegularFile)
            ?: error("shared production G1a-C fixture not found from repository ancestors")
        return Json.parseToJsonElement(String(Files.readAllBytes(fixture), Charsets.UTF_8)).jsonObject
    }

    private fun JsonObject.obj(name: String): JsonObject = getValue(name).jsonObject
    private fun JsonObject.array(name: String): JsonArray = getValue(name).jsonArray
    private fun JsonObject.string(name: String): String = getValue(name).jsonPrimitive.content
    private fun JsonObject.boolean(name: String): Boolean = string(name).toBooleanStrict()
    private fun JsonObject.ulong(name: String): ULong = string(name).toULong()
    private fun JsonObject.uint(name: String): UInt = string(name).toUInt()
    private fun JsonObject.int(name: String): Int = string(name).toInt()
    private fun JsonObject.hex(name: String): ByteArray = string(name).hex()

    private fun String.hex(): ByteArray {
        require(isNotEmpty() && length % 2 == 0 && all { it in '0'..'9' || it in 'a'..'f' })
        return chunked(2).map { it.toInt(16).toByte() }.toByteArray()
    }

    private fun sha256Hex(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    private companion object {
        val P256_ORDER = BigInteger(
            "ffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551",
            16,
        )
    }
}
