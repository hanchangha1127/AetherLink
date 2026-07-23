package com.localagentbridge.android.core.protocol.p2pnat

import java.math.BigInteger
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.nio.file.Path
import java.security.AlgorithmParameters
import java.security.KeyFactory
import java.security.MessageDigest
import java.security.PrivateKey
import java.security.PublicKey
import java.security.spec.ECGenParameterSpec
import java.security.spec.ECParameterSpec
import java.security.spec.ECPrivateKeySpec
import java.security.spec.X509EncodedKeySpec
import java.util.Collections
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
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

class ProductionG1aCCandidateSharedVectorTest {
    @Test
    fun namespaceCanonicalObjectsAndFixtureHashesMatch() {
        val fixture = loadFixture()
        val root = fixture.root

        assertEquals(CANDIDATE_FIXTURE_SHA256, sha256Hex(fixture.rawBytes))
        assertEquals("aetherlink-production-g1a-c-candidate-v1-vectors", root.string("schema"))
        assertEquals(1uL, root.ulong("version"))
        assertEquals("ALS1", root.string("magic"))
        assertEquals("ALP1", root.string("artifactMagic"))
        assertEquals(ProductionC1Contract.SUITE, root.string("suite"))
        assertEquals(ProductionC1Contract.SIGNATURE_ALGORITHM, root.string("signatureAlgorithm"))
        assertEquals(
            OPERATION_ORDER,
            root.obj("expectedOutcomes").string("operationOrder"),
        )
        assertEquals(
            OPERATION_ORDER,
            root.array("operations").joinToString(",") { it.jsonObject.string("wireName") },
        )
        assertFalse(root.obj("expectedOutcomes").boolean("productionDurabilityClaim"))
        assertEquals(
            "synthetic_contract_readiness_only",
            root.obj("expectedOutcomes").string("durabilityScope"),
        )
        assertTrue(root.obj("syntheticMaterials").boolean("testOnly"))

        val legacy = root.obj("legacyFixture")
        assertEquals(LEGACY_FIXTURE_SHA256, legacy.string("expectedSha256Hex"))
        assertTrue(legacy.boolean("mustRemainUnchanged"))
        assertEquals(
            LEGACY_FIXTURE_SHA256,
            sha256Hex(Files.readAllBytes(fixture.repositoryRoot.resolve(legacy.string("path")))),
        )

        val expectedTypes = linkedMapOf(
            "authority" to 8,
            "authorizationClientFetchRuntime" to 3,
            "authorizationClientPublish" to 2,
            "authorizationRuntimeFetchClient" to 3,
            "authorizationRuntimePublish" to 2,
            "candidateSecureSessionTranscript" to 7,
            "capabilityClientFetchRuntime" to 24,
            "capabilityClientPublish" to 23,
            "capabilityRuntimeFetchClient" to 24,
            "capabilityRuntimePublish" to 23,
            "endpointProofClientFetchRuntime" to 27,
            "endpointProofClientPublish" to 27,
            "endpointProofRuntimeFetchClient" to 27,
            "endpointProofRuntimePublish" to 27,
            "finalP2PDirectAuthorization" to 4,
            "p2pConnector" to 15,
            "p2pGrantAuthorization" to 26,
            "p2pGrantEvidence" to 25,
            "p2pRouteCapability" to 13,
            "p2pRoutePlan" to 14,
            "preauthorizationSessionContext" to 18,
            "receiptClientFetchRuntime" to 28,
            "receiptClientPublish" to 28,
            "receiptRuntimeFetchClient" to 28,
            "receiptRuntimePublish" to 28,
            "serviceKeyset" to 10,
        )
        val objects = root.obj("objects")
        assertEquals(expectedTypes.keys, objects.keys)
        expectedTypes.forEach { (name, objectType) ->
            val vector = objects.obj(name)
            val expected = vector.hex("expectedCanonicalHex")
            assertEquals(name, objectType, expected[4].toInt() and 0xff)
            assertEquals(name, vector.int("expectedCanonicalByteCount"), expected.size)
            assertArrayEquals(name, expected, decodeAndReencode(name, objectType, expected))
            assertEquals(name, vector.string("expectedSha256Hex"), sha256Hex(expected))
        }

        val artifacts = root.obj("artifacts")
        listOf("clientCandidateBatch", "runtimeCandidateBatch").forEach { name ->
            val vector = artifacts.obj(name)
            val expected = vector.hex("expectedCanonicalHex")
            val decoded = P2pNatCanonicalCodec.decodeCandidateBatch(expected)
            assertArrayEquals(name, expected, P2pNatCanonicalCodec.encode(decoded))
            assertEquals(name, vector.int("expectedCanonicalByteCount"), expected.size)
            assertEquals(name, vector.string("expectedSha256Hex"), sha256Hex(expected))
        }
        val pathVector = artifacts.obj("pathValidationReceipt")
        val pathBytes = pathVector.hex("expectedCanonicalHex")
        val pathReceipt = P2pNatCanonicalCodec.decodeFreshPathValidationReceipt(
            pathBytes,
            root.obj("constants").ulong("nowMs"),
        )
        assertArrayEquals(pathBytes, P2pNatCanonicalCodec.encode(pathReceipt))
        assertEquals(pathVector.string("expectedSha256Hex"), sha256Hex(pathBytes))

        val mutationIds = root.array("mutations").map { it.jsonObject.string("id") }.toSet()
        assertTrue(
            mutationIds.containsAll(
                setOf(
                    "grant_receipt_reorder",
                    "grant_duplicate_receipt",
                    "grant_other_ledger_chain",
                    "transcript_legacy_final_auth",
                ),
            ),
        )
    }

    @Test
    fun signedPlanReceiptsGrantProjectionAndObject26TranscriptAuthorityMatch() {
        val fixture = loadFixture()
        val chain = verifiedChain(fixture)
        val derived = fixture.root.obj("derived")

        assertEquals(derived.string("grantEvidenceDigest"), chain.grant.evidence.digestHex())
        assertEquals(derived.string("grantAuthorizationDigest"), chain.grant.grantAuthorization.digestHex)
        assertEquals(
            derived.string("secureSessionTranscriptDigest"),
            sha256Hex(ProductionSecureSessionCodec.encode(chain.transcript)),
        )
        val object26Bytes = fixture.root.obj("objects")
            .obj("p2pGrantAuthorization")
            .hex("expectedCanonicalHex")
        val object4Bytes = fixture.root.obj("objects")
            .obj("finalP2PDirectAuthorization")
            .hex("expectedCanonicalHex")
        assertEquals(sha256Hex(object26Bytes), chain.transcript.routeAuthorizationDigest)
        assertEquals(derived.string("grantAuthorizationDigest"), chain.transcript.routeAuthorizationDigest)
        assertNotEquals(sha256Hex(object4Bytes), chain.transcript.routeAuthorizationDigest)

        verifyCandidateTranscriptAuthority(chain.transcript, chain)
    }

    @Test
    fun coreReceiptAndLegacyTranscriptMutationsFailClosed() {
        val fixture = loadFixture()
        val chain = verifiedChain(fixture)
        val now = fixture.root.obj("constants").ulong("nowMs")

        val reordered = chain.receipts.toMutableList().also {
            val first = it[0]
            it[0] = it[1]
            it[1] = first
        }
        assertCandidateError(ProductionC1CandidateCapabilityError.AUTHORITY_MISMATCH) {
            ProductionC1CandidateVerifier.deriveGrantEvidence(
                chain.plan,
                chain.authorizations,
                reordered,
                P2pNatRole.CLIENT,
                chain.authority,
                now,
            )
        }

        val duplicate = chain.receipts.toMutableList().also { it[3] = it[0] }
        assertCandidateError(ProductionC1CandidateCapabilityError.REQUEST_CONFLICT) {
            ProductionC1CandidateVerifier.deriveGrantEvidence(
                chain.plan,
                chain.authorizations,
                duplicate,
                P2pNatRole.CLIENT,
                chain.authority,
                now,
            )
        }

        val otherChain = commitAll(fixture, chain, initialRevision = 10uL)
        val wrongChain = chain.receipts.toMutableList().also { it[0] = otherChain[0] }
        assertCandidateError(ProductionC1CandidateCapabilityError.REVISION_MISMATCH) {
            ProductionC1CandidateVerifier.deriveGrantEvidence(
                chain.plan,
                chain.authorizations,
                wrongChain,
                P2pNatRole.CLIENT,
                chain.authority,
                now,
            )
        }

        val objects = fixture.root.obj("objects")
        val legacyObject4Digest = sha256Hex(
            objects.obj("finalP2PDirectAuthorization").hex("expectedCanonicalHex"),
        )
        val legacyTranscript = ProductionSecureSessionCodec.decodeTranscript(
            replaceTLVField(
                objects.obj("candidateSecureSessionTranscript").hex("expectedCanonicalHex"),
                21,
                legacyObject4Digest.toByteArray(Charsets.US_ASCII),
            ),
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.ROUTE_MISMATCH) {
            verifyCandidateTranscriptAuthority(legacyTranscript, chain)
        }
    }

    @Test
    fun productionSecureSessionMatchesSharedRootConfirmationAndRecordVectors() {
        val fixture = loadFixture()
        val crypto = loadCryptoFixture(fixture.repositoryRoot)
        val chain = verifiedChain(fixture)
        val now = fixture.root.obj("constants").ulong("nowMs")
        val expected = crypto.obj("expected")
        val expectedKeys = expected.obj("keys")
        assertEquals("aetherlink-production-secure-session-crypto-v1-vectors", crypto.string("schema"))
        assertEquals(1uL, crypto.ulong("version"))
        assertEquals(CANDIDATE_FIXTURE_SHA256, crypto.obj("sourceFixture").string("sha256"))
        assertEquals(
            "000000000000000000000000000000000000000000000000000000000000006b",
            fixture.root.obj("keys").obj("clientEphemeral").string("privateScalarHex"),
        )
        assertEquals(
            "000000000000000000000000000000000000000000000000000000000000006c",
            fixture.root.obj("keys").obj("runtimeEphemeral").string("privateScalarHex"),
        )
        val contract = crypto.obj("contract")
        val objectTypes = contract.obj("objectTypes")
        val limits = contract.obj("limits")
        assertEquals(ProductionSecureSessionContract.SUITE, contract.string("suite"))
        assertEquals(ProductionSecureSessionContract.PROFILE, contract.string("profile"))
        assertEquals(
            ProductionSecureSessionCryptoContract.KEY_CONFIRMATION_OBJECT_TYPE,
            objectTypes.int("confirmation"),
        )
        assertEquals(
            ProductionSecureSessionCryptoContract.ENCRYPTED_RECORD_OBJECT_TYPE,
            objectTypes.int("encryptedRecord"),
        )
        assertEquals(
            ProductionSecureSessionCryptoContract.MAXIMUM_KEY_CONFIRMATION_BYTES,
            limits.int("maximumConfirmationBytes"),
        )
        assertEquals(
            ProductionSecureSessionCryptoContract.MAXIMUM_ENCRYPTED_RECORD_BYTES,
            limits.int("maximumEncryptedRecordBytes"),
        )
        assertEquals(
            ProductionSecureSessionCryptoContract.MAXIMUM_PLAINTEXT_BYTES,
            limits.int("maximumPlaintextBytes"),
        )
        assertEquals(
            ProductionSecureSessionCryptoContract.MAXIMUM_EPOCH.toULong(),
            limits.ulong("maximumEpoch"),
        )
        assertEquals(
            ProductionSecureSessionCryptoContract.MAXIMUM_EPOCH_RECORDS,
            limits.ulong("maximumRecordsPerEpoch"),
        )
        assertEquals(
            ProductionSecureSessionCryptoContract.MAXIMUM_EPOCH_PLAINTEXT_BYTES,
            limits.ulong("maximumPlaintextBytesPerEpoch"),
        )
        assertEquals(
            ProductionSecureSessionCryptoContract.MAXIMUM_SESSION_RECORDS,
            limits.ulong("maximumRecordsPerSession"),
        )
        assertEquals(
            ProductionSecureSessionCryptoContract.MAXIMUM_SESSION_PLAINTEXT_BYTES,
            limits.ulong("maximumPlaintextBytesPerSession"),
        )
        assertEquals(
            expected.string("transcriptSha256Hex"),
            sha256Hex(ProductionSecureSessionCodec.encode(chain.transcript)),
        )
        assertEquals(
            expected.string("grantAuthorizationSha256Hex"),
            sha256Hex(chain.grant.grantAuthorization.authorization.canonicalBytes()),
        )
        val clientBinding = keyScheduleBinding(chain, P2pNatRole.CLIENT, now)
        val material = ProductionSecureSessionCrypto.vectorMaterialForTest(
            clientBinding,
            ephemeralKey(fixture, "clientEphemeral"),
            now,
        )

        assertArrayEquals(expected.hex("bindingHashHex"), material.bindingDigest)
        assertArrayEquals(expected.hex("sharedSecretHex"), material.sharedSecret)
        assertArrayEquals(expected.hex("hkdfSaltHex"), material.salt)
        assertArrayEquals(expected.hex("hkdfPrkHex"), material.prk)
        assertArrayEquals(expected.hex("hkdfRootInfoHex"), material.rootInfo)
        assertArrayEquals(expected.hex("hkdfOkmHex"), material.rootOutput)
        assertArrayEquals(
            expectedKeys.hex("clientConfirmationKeyHex"),
            material.rootOutput.copyOfRange(0, 32),
        )
        assertArrayEquals(
            expectedKeys.hex("runtimeConfirmationKeyHex"),
            material.rootOutput.copyOfRange(32, 64),
        )
        assertArrayEquals(
            expectedKeys.hex("clientEpoch0SecretHex"),
            material.rootOutput.copyOfRange(64, 96),
        )
        assertArrayEquals(
            expectedKeys.hex("runtimeEpoch0SecretHex"),
            material.rootOutput.copyOfRange(96, 128),
        )

        val pair = activeSessionPair(fixture, chain, now)
        val confirmations = expected.obj("confirmations")
        assertArrayEquals(confirmations.obj("client").hex("canonicalHex"), pair.clientConfirmation)
        assertArrayEquals(confirmations.obj("runtime").hex("canonicalHex"), pair.runtimeConfirmation)

        val records = expected.obj("records")
        val clientApplication = pair.client.sealApplication(
            records.obj("clientApplication0").hex("plaintextHex"),
            now,
        )
        assertArrayEquals(records.obj("clientApplication0").hex("canonicalHex"), clientApplication.record)
        assertArrayEquals(
            records.obj("clientApplication0").hex("plaintextHex"),
            pair.runtime.open(clientApplication.record, now).plaintext,
        )

        val runtimeApplication = pair.runtime.sealApplication(
            records.obj("runtimeApplication0").hex("plaintextHex"),
            now,
        )
        assertArrayEquals(records.obj("runtimeApplication0").hex("canonicalHex"), runtimeApplication.record)
        assertArrayEquals(
            records.obj("runtimeApplication0").hex("plaintextHex"),
            pair.client.open(runtimeApplication.record, now).plaintext,
        )

        val keyUpdate = pair.client.sealKeyUpdate(now)
        assertArrayEquals(records.obj("clientKeyUpdate1").hex("canonicalHex"), keyUpdate.record)
        assertEquals(
            ProductionSecureSessionRecordContentType.KEY_UPDATE,
            pair.runtime.open(keyUpdate.record, now).contentType,
        )
        val epochOne = pair.client.sealApplication(
            records.obj("clientEpoch1Application0").hex("plaintextHex"),
            now,
        )
        assertArrayEquals(records.obj("clientEpoch1Application0").hex("canonicalHex"), epochOne.record)
        assertArrayEquals(
            records.obj("clientEpoch1Application0").hex("plaintextHex"),
            pair.runtime.open(epochOne.record, now).plaintext,
        )
        pair.close()
    }

    @Test
    fun authorityBoundOpaqueEngineInvalidatesHandshakeAndActivatedCipher() {
        val fixture = loadFixture()
        val chain = verifiedChain(fixture)
        val now = fixture.root.obj("constants").ulong("nowMs")
        val client = ProductionAuthorityBoundSecureSessionEngine.derive(
            keyScheduleBinding(chain, P2pNatRole.CLIENT, now),
            ProductionSecureSessionEphemeralKey.fromRawForTest(
                ephemeralKey(fixture, "clientEphemeral"),
            ),
            now,
        )
        val runtime = ProductionAuthorityBoundSecureSessionEngine.derive(
            keyScheduleBinding(chain, P2pNatRole.RUNTIME, now),
            ProductionSecureSessionEphemeralKey.fromRawForTest(
                ephemeralKey(fixture, "runtimeEphemeral"),
            ),
            now,
        )
        val clientConfirmation = client.localConfirmation(now)
        val runtimeConfirmation = runtime.localConfirmation(now)
        client.markLocalConfirmationSent(clientConfirmation, now)
        runtime.markLocalConfirmationSent(runtimeConfirmation, now)
        client.acceptPeerConfirmation(runtimeConfirmation, now)
        runtime.acceptPeerConfirmation(clientConfirmation, now)
        client.activate(now)
        runtime.activate(now)
        val sealed = client.sealApplication("lease-bound".toByteArray(), now)
        assertArrayEquals("lease-bound".toByteArray(), runtime.open(sealed.record, now).plaintext)
        val retryable = client.sealApplication("retryable-auth".toByteArray(), now)
        val corrupted = retryable.record.also { it[it.lastIndex] = (it.last().toInt() xor 1).toByte() }
        assertCryptoError(ProductionSecureSessionCryptoError.AUTHENTICATION_FAILED) {
            runtime.open(corrupted, now)
        }
        assertEquals(false, runtime.isTerminal)
        assertArrayEquals("retryable-auth".toByteArray(), runtime.open(retryable.record, now).plaintext)

        client.invalidate()
        assertEquals(true, client.isTerminal)
        assertCryptoError(ProductionSecureSessionCryptoError.TERMINAL) {
            client.sealApplication(byteArrayOf(1), now)
        }
        runtime.close()
        assertCryptoError(ProductionSecureSessionCryptoError.TERMINAL) {
            runtime.open(sealed.record, now)
        }
        clientConfirmation.fill(0)
        runtimeConfirmation.fill(0)
    }

    @Test
    fun productionSecureSessionDerivationAndConfirmationMutationsFailClosed() {
        val fixture = loadFixture()
        val chain = verifiedChain(fixture)
        val now = fixture.root.obj("constants").ulong("nowMs")
        val clientBinding = keyScheduleBinding(chain, P2pNatRole.CLIENT, now)

        val substitutedTranscript = copyTranscript(
            chain.transcript,
            routeAuthorizationDigest = "0".repeat(64),
        )
        assertCandidateError(ProductionC1CandidateCapabilityError.ROUTE_MISMATCH) {
            ProductionC1CandidateVerifier.verifyP2PKeyScheduleBinding(
                substitutedTranscript,
                chain.grant,
                P2pNatRole.CLIENT,
                chain.authority,
                now,
            )
        }
        assertCryptoError(ProductionSecureSessionCryptoError.KEY_MISMATCH) {
            ProductionSecureSessionCrypto.derive(
                clientBinding,
                ephemeralKey(fixture, "runtimeEphemeral"),
                now,
            )
        }

        val consumed = ephemeralKey(fixture, "clientEphemeral")
        ProductionSecureSessionCrypto.derive(clientBinding, consumed, now).close()
        assertCryptoError(ProductionSecureSessionCryptoError.KEY_ALREADY_USED) {
            ProductionSecureSessionCrypto.derive(clientBinding, consumed, now)
        }

        val reflectionPair = handshakePair(fixture, chain, now)
        val reflected = reflectionPair.client.localConfirmation(now)
        assertCryptoError(ProductionSecureSessionCryptoError.AUTHENTICATION_FAILED) {
            reflectionPair.client.acceptPeerConfirmation(reflected, now)
        }
        assertCryptoError(ProductionSecureSessionCryptoError.TERMINAL) {
            reflectionPair.client.localConfirmation(now)
        }
        reflectionPair.close()

        val flippedPair = handshakePair(fixture, chain, now)
        val flippedProof = flippedPair.runtime.localConfirmation(now).also {
            it[it.lastIndex] = (it.last().toInt() xor 1).toByte()
        }
        assertCryptoError(ProductionSecureSessionCryptoError.AUTHENTICATION_FAILED) {
            flippedPair.client.acceptPeerConfirmation(flippedProof, now)
        }
        assertCryptoError(ProductionSecureSessionCryptoError.TERMINAL) {
            flippedPair.client.activate(now)
        }
        flippedPair.close()

        val invalidInitialLocalPair = handshakePair(fixture, chain, now)
        val invalidInitialLocal = invalidInitialLocalPair.client.localConfirmation(now).also {
            it[it.lastIndex] = (it.last().toInt() xor 1).toByte()
        }
        assertCryptoError(ProductionSecureSessionCryptoError.AUTHENTICATION_FAILED) {
            invalidInitialLocalPair.client.markLocalConfirmationSent(invalidInitialLocal, now)
        }
        assertCryptoError(ProductionSecureSessionCryptoError.TERMINAL) {
            invalidInitialLocalPair.client.localConfirmation(now)
        }
        invalidInitialLocalPair.close()

        val confirmationProviderFailure = ProductionSecureSessionCrypto.derive(
            clientBinding,
            ephemeralKey(fixture, "clientEphemeral"),
            now,
            ProductionSecureSessionJcaAlgorithms(
                confirmationMac = "AetherLinkMissingConfirmationMac",
            ),
        )
        assertCryptoError(ProductionSecureSessionCryptoError.CRYPTO_FAILURE) {
            confirmationProviderFailure.localConfirmation(now)
        }
        assertCryptoError(ProductionSecureSessionCryptoError.TERMINAL) {
            confirmationProviderFailure.localConfirmation(now)
        }
        confirmationProviderFailure.close()

        assertCryptoError(ProductionSecureSessionCryptoError.CRYPTO_FAILURE) {
            ProductionSecureSessionCrypto.derive(
                clientBinding,
                ephemeralKey(fixture, "clientEphemeral"),
                now,
                ProductionSecureSessionJcaAlgorithms(mac = "AetherLinkMissingRootMac"),
            )
        }

        val idempotentPair = handshakePair(fixture, chain, now)
        val clientConfirmation = idempotentPair.client.localConfirmation(now)
        val runtimeConfirmation = idempotentPair.runtime.localConfirmation(now)
        idempotentPair.client.markLocalConfirmationSent(clientConfirmation, now)
        idempotentPair.client.markLocalConfirmationSent(clientConfirmation, now)
        idempotentPair.client.acceptPeerConfirmation(runtimeConfirmation, now)
        idempotentPair.client.acceptPeerConfirmation(runtimeConfirmation, now)
        idempotentPair.client.activate(now).close()
        idempotentPair.runtime.close()

        val conflictingLocalPair = handshakePair(fixture, chain, now)
        val firstLocal = conflictingLocalPair.client.localConfirmation(now)
        conflictingLocalPair.client.markLocalConfirmationSent(firstLocal, now)
        val conflictingLocal = firstLocal.copyOf().also {
            it[it.lastIndex] = (it.last().toInt() xor 1).toByte()
        }
        assertCryptoError(ProductionSecureSessionCryptoError.CONFIRMATION_CONFLICT) {
            conflictingLocalPair.client.markLocalConfirmationSent(conflictingLocal, now)
        }
        assertCryptoError(ProductionSecureSessionCryptoError.TERMINAL) {
            conflictingLocalPair.client.localConfirmation(now)
        }
        conflictingLocalPair.close()

        val conflictingPeerPair = handshakePair(fixture, chain, now)
        val firstPeer = conflictingPeerPair.runtime.localConfirmation(now)
        conflictingPeerPair.client.acceptPeerConfirmation(firstPeer, now)
        val conflictingPeer = firstPeer.copyOf().also {
            it[it.lastIndex] = (it.last().toInt() xor 1).toByte()
        }
        assertCryptoError(ProductionSecureSessionCryptoError.CONFIRMATION_CONFLICT) {
            conflictingPeerPair.client.acceptPeerConfirmation(conflictingPeer, now)
        }
        assertCryptoError(ProductionSecureSessionCryptoError.TERMINAL) {
            conflictingPeerPair.client.localConfirmation(now)
        }
        conflictingPeerPair.close()
    }

    @Test
    fun productionSecureSessionRecordMutationsAreOrderedAndAuthenticationIsTransactional() {
        val fixture = loadFixture()
        val crypto = loadCryptoFixture(fixture.repositoryRoot)
        val chain = verifiedChain(fixture)
        val now = fixture.root.obj("constants").ulong("nowMs")
        val records = crypto.obj("expected").obj("records")
        val clientApplication = records.obj("clientApplication0").hex("canonicalHex")
        val decodedApplication = ProductionSecureSessionCryptoCodec.decodeRecord(clientApplication)

        fun assertFreshReceiverRejects(
            expected: ProductionSecureSessionCryptoError,
            record: ByteArray,
        ) {
            val pair = activeSessionPair(fixture, chain, now)
            try {
                assertCryptoError(expected) { pair.runtime.open(record, now) }
            } finally {
                pair.close()
            }
        }

        assertFreshReceiverRejects(
            ProductionSecureSessionCryptoError.BINDING_MISMATCH,
            encodeRecord(decodedApplication, sessionId = "0".repeat(32)),
        )
        assertFreshReceiverRejects(
            ProductionSecureSessionCryptoError.BINDING_MISMATCH,
            encodeRecord(decodedApplication, senderRole = P2pNatRole.RUNTIME),
        )
        assertFreshReceiverRejects(
            ProductionSecureSessionCryptoError.OUT_OF_ORDER,
            encodeRecord(decodedApplication, sequence = 1uL),
        )
        assertFreshReceiverRejects(
            ProductionSecureSessionCryptoError.OUT_OF_ORDER,
            encodeRecord(decodedApplication, epoch = 1u),
        )
        assertFreshReceiverRejects(
            ProductionSecureSessionCryptoError.AUTHENTICATION_FAILED,
            encodeRecord(
                decodedApplication,
                tag = decodedApplication.tag.also {
                    it[it.lastIndex] = (it.last().toInt() xor 1).toByte()
                },
            ),
        )
        assertFreshReceiverRejects(
            ProductionSecureSessionCryptoError.AUTHENTICATION_FAILED,
            encodeRecord(
                decodedApplication,
                ciphertext = decodedApplication.ciphertext.also {
                    it[0] = (it[0].toInt() xor 1).toByte()
                },
            ),
        )

        val transactionalPair = activeSessionPair(fixture, chain, now)
        val badTag = encodeRecord(
            decodedApplication,
            tag = decodedApplication.tag.also {
                it[0] = (it[0].toInt() xor 1).toByte()
            },
        )
        assertCryptoError(ProductionSecureSessionCryptoError.AUTHENTICATION_FAILED) {
            transactionalPair.runtime.open(badTag, now)
        }
        assertArrayEquals(
            records.obj("clientApplication0").hex("plaintextHex"),
            transactionalPair.runtime.open(clientApplication, now).plaintext,
        )
        assertCryptoError(ProductionSecureSessionCryptoError.OUT_OF_ORDER) {
            transactionalPair.runtime.open(clientApplication, now)
        }

        val decryptProviderFailure = activeSessionPair(
            fixture,
            chain,
            now,
            runtimeAlgorithms = ProductionSecureSessionJcaAlgorithms(
                cipher = "AetherLinkMissingAeadCipher",
            ),
        )
        assertCryptoError(ProductionSecureSessionCryptoError.CRYPTO_FAILURE) {
            decryptProviderFailure.runtime.open(clientApplication, now)
        }
        assertCryptoError(ProductionSecureSessionCryptoError.TERMINAL) {
            decryptProviderFailure.runtime.open(clientApplication, now)
        }
        decryptProviderFailure.close()

        val keyUpdate = records.obj("clientKeyUpdate1").hex("canonicalHex")
        val skippedPair = activeSessionPair(fixture, chain, now)
        assertCryptoError(ProductionSecureSessionCryptoError.OUT_OF_ORDER) {
            skippedPair.runtime.open(keyUpdate, now)
        }
        skippedPair.close()

        transactionalPair.runtime.open(keyUpdate, now)
        assertCryptoError(ProductionSecureSessionCryptoError.OUT_OF_ORDER) {
            transactionalPair.runtime.open(keyUpdate, now)
        }
        transactionalPair.close()
    }

    @Test
    fun productionSecureSessionLifecycleSizeConcurrencyAndCapacityBoundariesHold() {
        val fixture = loadFixture()
        val chain = verifiedChain(fixture)
        val now = fixture.root.obj("constants").ulong("nowMs")
        val expiresAt = chain.grant.grantAuthorization.authorization.expiresAtMs
        val clientBinding = keyScheduleBinding(chain, P2pNatRole.CLIENT, now)

        assertCryptoError(ProductionSecureSessionCryptoError.EXPIRED) {
            ProductionSecureSessionCrypto.derive(
                clientBinding,
                ephemeralKey(fixture, "clientEphemeral"),
                expiresAt,
            )
        }
        val rollback = ProductionSecureSessionCrypto.derive(
            clientBinding,
            ephemeralKey(fixture, "clientEphemeral"),
            now,
        )
        rollback.localConfirmation(now + 1uL)
        assertCryptoError(ProductionSecureSessionCryptoError.CLOCK_REGRESSION) {
            rollback.localConfirmation(now)
        }
        assertCryptoError(ProductionSecureSessionCryptoError.TERMINAL) {
            rollback.localConfirmation(now + 1uL)
        }
        rollback.close()

        val closed = ProductionSecureSessionCrypto.derive(
            clientBinding,
            ephemeralKey(fixture, "clientEphemeral"),
            now,
        )
        closed.close()
        assertCryptoError(ProductionSecureSessionCryptoError.CLOSED) {
            closed.localConfirmation(now)
        }

        val invalidated = activeSessionPair(fixture, chain, now)
        invalidated.client.invalidate()
        assertCryptoError(ProductionSecureSessionCryptoError.TERMINAL) {
            invalidated.client.sealApplication(byteArrayOf(1), now)
        }
        invalidated.runtime.close()
        assertCryptoError(ProductionSecureSessionCryptoError.CLOSED) {
            invalidated.runtime.open(ByteArray(0), now)
        }

        val maximum = activeSessionPair(fixture, chain, now)
        val maximumRecord = maximum.client.sealApplication(
            ByteArray(ProductionSecureSessionCryptoContract.MAXIMUM_PLAINTEXT_BYTES),
            now,
        ).record
        assertEquals(1_048_551, maximumRecord.size)
        assertTrue(maximumRecord.size <= ProductionSecureSessionCryptoContract.MAXIMUM_ENCRYPTED_RECORD_BYTES)
        maximum.close()
        val tooLarge = activeSessionPair(fixture, chain, now)
        assertCryptoError(ProductionSecureSessionCryptoError.LIMIT_EXCEEDED) {
            tooLarge.client.sealApplication(
                ByteArray(ProductionSecureSessionCryptoContract.MAXIMUM_PLAINTEXT_BYTES + 1),
                now,
            )
        }
        tooLarge.close()

        val concurrent = activeSessionPair(fixture, chain, now)
        val threadCount = 32
        val start = CountDownLatch(1)
        val records = Collections.synchronizedList(mutableListOf<ByteArray>())
        val executor = Executors.newFixedThreadPool(8)
        try {
            val futures = (0 until threadCount).map { value ->
                executor.submit {
                    start.await()
                    records += concurrent.client.sealApplication(byteArrayOf(value.toByte()), now).record
                }
            }
            start.countDown()
            futures.forEach { it.get(10, TimeUnit.SECONDS) }
        } finally {
            executor.shutdownNow()
            concurrent.close()
        }
        assertEquals(threadCount, records.size)
        assertEquals(
            (0 until threadCount).map(Int::toULong),
            records.map { ProductionSecureSessionCryptoCodec.decodeRecord(it).sequence }.sorted(),
        )

        assertCapacityBoundaries()
        val expectedNegativeIds = listOf(
            "object7_object26_substitution",
            "local_private_public_mismatch",
            "ephemeral_handle_reuse",
            "role_reflection_confirmation",
            "confirmation_proof_bit_flip",
            "confirmation_before_activation",
            "record_wrong_session",
            "record_wrong_role",
            "record_replay",
            "record_gap",
            "record_future_epoch",
            "record_tag_bit_flip",
            "record_ciphertext_bit_flip",
            "authentication_failure_no_receive_advance",
            "key_update_skip",
            "key_update_duplicate",
            "key_update_epoch_15",
            "record_max_plus_one",
            "epoch_record_limit",
            "epoch_plaintext_limit",
            "session_record_limit",
            "session_plaintext_limit",
            "expiry_boundary",
            "clock_regression",
            "authority_invalidation",
            "concurrent_seal_unique_sequence",
        )
        assertEquals(
            expectedNegativeIds,
            loadCryptoFixture(fixture.repositoryRoot).array("negativeVectors")
                .map { it.jsonObject.string("id") },
        )
    }

    private fun keyScheduleBinding(
        chain: CandidateVectorChain,
        role: P2pNatRole,
        nowMs: ULong,
    ): VerifiedProductionC1CandidateP2PKeyScheduleBinding =
        ProductionC1CandidateVerifier.verifyP2PKeyScheduleBinding(
            chain.transcript,
            chain.grant,
            role,
            chain.authority,
            nowMs,
        )

    private fun ephemeralKey(
        fixture: CandidateFixtureDocument,
        keyName: String,
    ): P2pNatSessionEphemeralKey = P2pNatSessionEphemeralKey.fromPrivateScalarForTest(
        fixture.root.obj("keys").obj(keyName).hex("privateScalarHex"),
    )

    private fun handshakePair(
        fixture: CandidateFixtureDocument,
        chain: CandidateVectorChain,
        nowMs: ULong,
        clientAlgorithms: ProductionSecureSessionJcaAlgorithms = ProductionSecureSessionJcaAlgorithms(),
        runtimeAlgorithms: ProductionSecureSessionJcaAlgorithms = ProductionSecureSessionJcaAlgorithms(),
    ): HandshakePair = HandshakePair(
        ProductionSecureSessionCrypto.derive(
            keyScheduleBinding(chain, P2pNatRole.CLIENT, nowMs),
            ephemeralKey(fixture, "clientEphemeral"),
            nowMs,
            clientAlgorithms,
        ),
        ProductionSecureSessionCrypto.derive(
            keyScheduleBinding(chain, P2pNatRole.RUNTIME, nowMs),
            ephemeralKey(fixture, "runtimeEphemeral"),
            nowMs,
            runtimeAlgorithms,
        ),
    )

    private fun activeSessionPair(
        fixture: CandidateFixtureDocument,
        chain: CandidateVectorChain,
        nowMs: ULong,
        clientAlgorithms: ProductionSecureSessionJcaAlgorithms = ProductionSecureSessionJcaAlgorithms(),
        runtimeAlgorithms: ProductionSecureSessionJcaAlgorithms = ProductionSecureSessionJcaAlgorithms(),
    ): ActiveSessionPair {
        val handshakes = handshakePair(
            fixture,
            chain,
            nowMs,
            clientAlgorithms,
            runtimeAlgorithms,
        )
        val clientConfirmation = handshakes.client.localConfirmation(nowMs)
        val runtimeConfirmation = handshakes.runtime.localConfirmation(nowMs)
        handshakes.client.markLocalConfirmationSent(clientConfirmation, nowMs)
        handshakes.runtime.markLocalConfirmationSent(runtimeConfirmation, nowMs)
        handshakes.client.acceptPeerConfirmation(runtimeConfirmation, nowMs)
        handshakes.runtime.acceptPeerConfirmation(clientConfirmation, nowMs)
        return ActiveSessionPair(
            handshakes.client.activate(nowMs),
            handshakes.runtime.activate(nowMs),
            clientConfirmation,
            runtimeConfirmation,
        )
    }

    private fun copyTranscript(
        value: ProductionSecureSessionTranscript,
        routeAuthorizationDigest: String = value.routeAuthorizationDigest,
    ): ProductionSecureSessionTranscript = ProductionSecureSessionTranscript(
        sessionId = value.sessionId,
        pairBindingDigest = value.pairBindingDigest,
        pairEpoch = value.pairEpoch,
        clientIdentityFingerprint = value.clientIdentityFingerprint,
        runtimeIdentityFingerprint = value.runtimeIdentityFingerprint,
        clientEphemeralPublicKey = value.clientEphemeralPublicKey,
        runtimeEphemeralPublicKey = value.runtimeEphemeralPublicKey,
        clientNonce = value.clientNonce,
        runtimeNonce = value.runtimeNonce,
        generation = value.generation,
        serviceConfigVersion = value.serviceConfigVersion,
        keysetVersion = value.keysetVersion,
        revocationCounter = value.revocationCounter,
        protocolVersion = value.protocolVersion,
        minimumProtocolVersion = value.minimumProtocolVersion,
        profile = value.profile,
        routeAuthorizationKind = value.routeAuthorizationKind,
        routeAuthorizationDigest = routeAuthorizationDigest,
        suite = value.suite,
    )

    private fun encodeRecord(
        value: ProductionSecureSessionEncryptedRecord,
        sessionId: String = value.sessionId,
        senderRole: P2pNatRole = value.senderRole,
        epoch: UInt = value.epoch,
        sequence: ULong = value.sequence,
        contentType: ProductionSecureSessionRecordContentType = value.contentType,
        ciphertext: ByteArray = value.ciphertext,
        tag: ByteArray = value.tag,
    ): ByteArray = ProductionSecureSessionCryptoCodec.encode(
        ProductionSecureSessionEncryptedRecord(
            sessionId,
            senderRole,
            epoch,
            sequence,
            contentType,
            ciphertext,
            tag,
        ),
    )

    private fun assertCapacityBoundaries() {
        val maxEpochRecords = ProductionSecureSessionCryptoContract.MAXIMUM_EPOCH_RECORDS
        val maxEpochBytes = ProductionSecureSessionCryptoContract.MAXIMUM_EPOCH_PLAINTEXT_BYTES
        val maxSessionRecords = ProductionSecureSessionCryptoContract.MAXIMUM_SESSION_RECORDS
        val maxSessionBytes = ProductionSecureSessionCryptoContract.MAXIMUM_SESSION_PLAINTEXT_BYTES

        fun snapshot(
            epoch: UInt = 0u,
            epochRecords: ULong = 0uL,
            epochBytes: ULong = 0uL,
            sessionRecords: ULong = 0uL,
            sessionBytes: ULong = 0uL,
        ) = ProductionSecureSessionCounterSnapshot(
            epoch,
            epochRecords,
            epochBytes,
            sessionRecords,
            sessionBytes,
        )

        assertEquals(
            ProductionSecureSessionCapacityDecision(true, false),
            ProductionSecureSessionCapacityPolicy.application(
                snapshot(epochRecords = maxEpochRecords - 2uL),
                0uL,
            ),
        )
        assertCryptoError(ProductionSecureSessionCryptoError.KEY_UPDATE_REQUIRED) {
            ProductionSecureSessionCapacityPolicy.application(
                snapshot(epochRecords = maxEpochRecords - 1uL),
                0uL,
            )
        }
        assertEquals(
            ProductionSecureSessionCapacityDecision(true, false),
            ProductionSecureSessionCapacityPolicy.application(
                snapshot(epochBytes = maxEpochBytes - 5uL),
                1uL,
            ),
        )
        assertCryptoError(ProductionSecureSessionCryptoError.KEY_UPDATE_REQUIRED) {
            ProductionSecureSessionCapacityPolicy.application(
                snapshot(epochBytes = maxEpochBytes - 4uL),
                1uL,
            )
        }
        assertEquals(
            1u,
            ProductionSecureSessionCapacityPolicy.keyUpdate(
                snapshot(
                    epochRecords = maxEpochRecords - 1uL,
                    epochBytes = maxEpochBytes - 4uL,
                ),
            ),
        )
        assertEquals(
            ProductionSecureSessionKeyUpdateCapacityDecision(1u, false),
            ProductionSecureSessionCapacityPolicy.keyUpdateDecision(snapshot()),
        )
        assertEquals(
            ProductionSecureSessionKeyUpdateCapacityDecision(1u, true),
            ProductionSecureSessionCapacityPolicy.keyUpdateDecision(
                snapshot(sessionRecords = maxSessionRecords - 1uL),
            ),
        )
        assertEquals(
            ProductionSecureSessionKeyUpdateCapacityDecision(1u, true),
            ProductionSecureSessionCapacityPolicy.keyUpdateDecision(
                snapshot(sessionBytes = maxSessionBytes - UInt.SIZE_BYTES.toULong()),
            ),
        )
        assertCryptoError(ProductionSecureSessionCryptoError.LIMIT_EXCEEDED) {
            ProductionSecureSessionCapacityPolicy.keyUpdateDecision(
                snapshot(sessionRecords = maxSessionRecords),
            )
        }
        assertCryptoError(ProductionSecureSessionCryptoError.LIMIT_EXCEEDED) {
            ProductionSecureSessionCapacityPolicy.keyUpdateDecision(
                snapshot(sessionBytes = maxSessionBytes - UInt.SIZE_BYTES.toULong() + 1uL),
            )
        }
        assertCryptoError(ProductionSecureSessionCryptoError.LIMIT_EXCEEDED) {
            ProductionSecureSessionCapacityPolicy.keyUpdate(snapshot(epochRecords = maxEpochRecords))
        }

        assertEquals(
            ProductionSecureSessionCapacityDecision(false, true),
            ProductionSecureSessionCapacityPolicy.application(
                snapshot(epoch = 15u, epochRecords = maxEpochRecords - 1uL),
                0uL,
            ),
        )
        assertCryptoError(ProductionSecureSessionCryptoError.LIMIT_EXCEEDED) {
            ProductionSecureSessionCapacityPolicy.application(
                snapshot(epoch = 15u, epochRecords = maxEpochRecords),
                0uL,
            )
        }
        assertEquals(
            ProductionSecureSessionCapacityDecision(false, true),
            ProductionSecureSessionCapacityPolicy.application(
                snapshot(epoch = 15u, epochBytes = maxEpochBytes - 1uL),
                1uL,
            ),
        )
        assertCryptoError(ProductionSecureSessionCryptoError.LIMIT_EXCEEDED) {
            ProductionSecureSessionCapacityPolicy.application(
                snapshot(epoch = 15u, epochBytes = maxEpochBytes),
                1uL,
            )
        }
        assertCryptoError(ProductionSecureSessionCryptoError.LIMIT_EXCEEDED) {
            ProductionSecureSessionCapacityPolicy.keyUpdate(snapshot(epoch = 15u))
        }

        assertEquals(
            ProductionSecureSessionCapacityDecision(false, true),
            ProductionSecureSessionCapacityPolicy.application(
                snapshot(epoch = 15u, sessionRecords = maxSessionRecords - 1uL),
                0uL,
            ),
        )
        assertCryptoError(ProductionSecureSessionCryptoError.LIMIT_EXCEEDED) {
            ProductionSecureSessionCapacityPolicy.application(
                snapshot(epoch = 15u, sessionRecords = maxSessionRecords),
                0uL,
            )
        }
        assertEquals(
            ProductionSecureSessionCapacityDecision(false, true),
            ProductionSecureSessionCapacityPolicy.application(
                snapshot(epoch = 15u, sessionBytes = maxSessionBytes - 1uL),
                1uL,
            ),
        )
        assertCryptoError(ProductionSecureSessionCryptoError.LIMIT_EXCEEDED) {
            ProductionSecureSessionCapacityPolicy.application(
                snapshot(epoch = 15u, sessionBytes = maxSessionBytes),
                1uL,
            )
        }
    }

    private fun assertCryptoError(
        expected: ProductionSecureSessionCryptoError,
        body: () -> Unit,
    ) {
        try {
            body()
            fail("Expected $expected")
        } catch (error: ProductionSecureSessionCryptoException) {
            assertEquals(expected, error.reason)
        }
    }

    private fun loadCryptoFixture(repositoryRoot: Path): JsonObject {
        val path = repositoryRoot.resolve(
            "shared/protocol/fixtures/production-secure-session-crypto-v1-vectors.json",
        )
        return Json.parseToJsonElement(String(Files.readAllBytes(path), Charsets.UTF_8)).jsonObject
    }

    private fun verifiedChain(fixture: CandidateFixtureDocument): CandidateVectorChain {
        val root = fixture.root
        val objects = root.obj("objects")
        val artifacts = root.obj("artifacts")
        val now = root.obj("constants").ulong("nowMs")
        val keysetBytes = objects.obj("serviceKeyset").hex("expectedCanonicalHex")
        val keyset = ProductionC1ServiceKeyset.decode(keysetBytes)
        val verifiedKeyset = ProductionC1Verifier.verifyServiceKeyset(
            keyset,
            keyset.serviceIdDigest,
            publicKey(root, "root"),
            keyset.keysetVersion,
            nowMs = now,
        )
        assertArrayEquals(keysetBytes, verifiedKeyset.keyset.canonicalBytes())

        val authority = ProductionPairAuthorityState.decode(
            objects.obj("authority").hex("expectedCanonicalHex"),
        )
        val context = ProductionC1PreauthorizationSessionContext.decode(
            objects.obj("preauthorizationSessionContext").hex("expectedCanonicalHex"),
        )
        val capabilities = OPERATIONS.map { vector ->
            val proof = ProductionC1EndpointOperationProof.decode(
                objects.obj(vector.proof).hex("expectedCanonicalHex"),
            )
            val capability = ProductionC1CandidateCapability.decode(
                objects.obj(vector.capability).hex("expectedCanonicalHex"),
            )
            ProductionC1CandidateVerifier.verifyCapability(
                capability,
                artifacts.obj(vector.batch).hex("expectedCanonicalHex"),
                proof,
                context,
                authority,
                verifiedKeyset,
                now,
            )
        }
        capabilities.forEach {
            assertArrayEquals(keysetBytes, it.verifiedKeyset.keyset.canonicalBytes())
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
        val claims = ProductionC1RoutePlanClaims.decode(
            objects.obj("p2pRoutePlan").hex("expectedCanonicalHex"),
        )
        val routeCapability = ProductionC1RouteCapability.decode(
            objects.obj("p2pRouteCapability").hex("expectedCanonicalHex"),
        )
        val plan = ProductionC1CandidateVerifier.verifyP2PDirectPlan(
            claims,
            routeCapability,
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
        OPERATIONS.forEachIndexed { index, vector ->
            assertArrayEquals(
                vector.authorization,
                objects.obj(vector.authorization).hex("expectedCanonicalHex"),
                ProductionSecureSessionCodec.encode(authorizations.operationOrder[index]),
            )
        }
        assertArrayEquals(
            objects.obj("finalP2PDirectAuthorization").hex("expectedCanonicalHex"),
            ProductionSecureSessionCodec.encode(authorizations.finalP2PDirect),
        )

        val receipts = OPERATIONS.mapIndexed { index, vector ->
            val receipt = ProductionC1CandidateOperationReceipt.decode(
                objects.obj(vector.receipt).hex("expectedCanonicalHex"),
            )
            ProductionC1CandidateOperationReceiptVerifier.verify(
                receipt,
                capabilities[index],
                authorizations.operationOrder[index],
                authority,
                verifiedKeyset,
                now,
            )
        }
        assertEquals(
            root.obj("derived").array("operationReceiptDigests").map { it.jsonPrimitive.content },
            receipts.map { it.receipt.digestHex() },
        )

        val derivedGrant = ProductionC1CandidateVerifier.deriveGrantEvidence(
            plan,
            authorizations,
            receipts,
            P2pNatRole.CLIENT,
            authority,
            now,
        )
        val vectorEvidence = ProductionC1P2PGrantEvidence.decode(
            objects.obj("p2pGrantEvidence").hex("expectedCanonicalHex"),
        )
        assertArrayEquals(
            objects.obj("p2pGrantEvidence").hex("expectedCanonicalHex"),
            derivedGrant.evidence.canonicalBytes(),
        )
        assertEquals(vectorEvidence, derivedGrant.evidence)
        assertEquals(
            root.obj("expectedOutcomes").ulong("effectiveNotBeforeMs"),
            derivedGrant.evidence.effectiveNotBeforeMs,
        )
        assertEquals(
            root.obj("expectedOutcomes").ulong("expiresAtMs"),
            derivedGrant.evidence.expiresAtMs,
        )
        val grant = ProductionC1CandidateVerifier.verifyGrantEvidence(
            vectorEvidence,
            plan,
            authorizations,
            receipts,
            P2pNatRole.CLIENT,
            authority,
            now,
        )

        val vectorAuthorization = ProductionC1P2PGrantAuthorization.decode(
            objects.obj("p2pGrantAuthorization").hex("expectedCanonicalHex"),
        )
        val projected = ProductionC1CandidateVerifier.makeGrantAuthorization(vectorEvidence)
        assertEquals(vectorAuthorization, projected)
        assertArrayEquals(
            objects.obj("p2pGrantAuthorization").hex("expectedCanonicalHex"),
            projected.canonicalBytes(),
        )
        assertEquals(vectorAuthorization, grant.grantAuthorization.authorization)
        assertEquals(
            grant.grantAuthorization,
            ProductionC1CandidateVerifier.verifyGrantAuthorization(
                vectorAuthorization,
                vectorEvidence,
                plan,
                P2pNatRole.CLIENT,
            ),
        )

        val transcript = ProductionSecureSessionCodec.decodeTranscript(
            objects.obj("candidateSecureSessionTranscript").hex("expectedCanonicalHex"),
        )
        val chain = CandidateVectorChain(
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
        verifyCandidateTranscriptAuthority(transcript, chain)
        return chain
    }

    /** Candidate object 7 is authorized by verified object 26, never generic object-4 matches(). */
    private fun verifyCandidateTranscriptAuthority(
        transcript: ProductionSecureSessionTranscript,
        chain: CandidateVectorChain,
    ) {
        val evidence = chain.grant.evidence
        val refreshedAuthorization = ProductionC1CandidateVerifier.verifyGrantAuthorization(
            chain.grant.grantAuthorization.authorization,
            evidence,
            chain.plan,
            P2pNatRole.CLIENT,
        )
        val context = try {
            ProductionC1PreauthorizationSessionContext(transcript)
        } catch (_: ProductionC1Exception) {
            throw ProductionC1CandidateCapabilityException(
                ProductionC1CandidateCapabilityError.ROUTE_MISMATCH,
            )
        }
        val suppliedDigest = runCatching { transcript.routeAuthorizationDigest.hex() }.getOrNull()
        val expectedDigest = refreshedAuthorization.digestHex.hex()
        val valid = suppliedDigest != null &&
            MessageDigest.isEqual(suppliedDigest, expectedDigest) &&
            transcript.routeAuthorizationKind == ProductionRouteAuthorizationKind.P2P_DIRECT &&
            context == chain.context &&
            context == chain.plan.securityContext &&
            transcript.sessionId == evidence.sessionId &&
            transcript.pairBindingDigest == evidence.pairBindingDigest &&
            transcript.pairEpoch == evidence.pairEpoch &&
            transcript.generation == evidence.generation &&
            transcript.clientIdentityFingerprint == evidence.clientIdentityFingerprint &&
            transcript.runtimeIdentityFingerprint == evidence.runtimeIdentityFingerprint &&
            transcript.serviceConfigVersion == chain.authority.serviceConfigVersion &&
            transcript.keysetVersion == chain.authority.keysetVersion &&
            transcript.revocationCounter == chain.authority.revocationCounter
        if (!valid) {
            throw ProductionC1CandidateCapabilityException(
                ProductionC1CandidateCapabilityError.ROUTE_MISMATCH,
            )
        }
    }

    private fun commitAll(
        fixture: CandidateFixtureDocument,
        chain: CandidateVectorChain,
        initialRevision: ULong,
    ): List<VerifiedProductionC1CandidateOperationReceipt> {
        val now = fixture.root.obj("constants").ulong("nowMs")
        var state = ProductionC1CandidateUsageLedgerState(
            revision = initialRevision,
            remainingOperations = 4uL,
            remainingBytes = chain.capabilities.sumOf {
                it.capability.candidateBatchByteCount.toULong()
            },
            retentionLimit = 8u,
        )
        val ledgerId = fixture.root.obj("usageLedger").string("ledgerId")
        val signingPublicKey = publicKey(fixture.root, "candidateReceipt")
        val signingPrivateKey = privateKey(fixture.root, "candidateReceipt")
        val receipts = mutableListOf<VerifiedProductionC1CandidateOperationReceipt>()
        chain.capabilities.indices.forEach { index ->
            val capability = chain.capabilities[index]
            val authorization = chain.authorizations.operationOrder[index]
            val requestId = capability.endpointOperationProof.proofId
            val authorizationDigest = sha256Hex(ProductionSecureSessionCodec.encode(authorization))
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
                chain.authority,
                now,
            )
            val previous = state
            state = preparation.nextState
            val confirmed = ReadbackConfirmedProductionC1CandidateUsageReceipt.confirm(
                preparation,
                state,
                ledgerId,
                sha256Hex("candidate-shared-other-chain-$index".toByteArray()),
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
                chain.authority,
                chain.verifiedKeyset,
                signingPublicKey,
                signingPrivateKey,
            )
            receipts += ProductionC1CandidateOperationReceiptVerifier.verify(
                receipt,
                capability,
                authorization,
                chain.authority,
                chain.verifiedKeyset,
                now,
            )
        }
        return receipts
    }

    private fun decodeAndReencode(name: String, objectType: Int, bytes: ByteArray): ByteArray =
        when (objectType) {
            2, 3, 4 -> ProductionSecureSessionCodec.encode(
                ProductionSecureSessionCodec.decodeRouteAuthorization(bytes),
            )
            7 -> ProductionSecureSessionCodec.encode(
                ProductionSecureSessionCodec.decodeTranscript(bytes),
            )
            8 -> ProductionPairAuthorityState.decode(bytes).canonicalBytes()
            10 -> ProductionC1ServiceKeyset.decode(bytes).canonicalBytes()
            13 -> ProductionC1RouteCapability.decode(bytes).canonicalBytes()
            14 -> ProductionC1RoutePlanClaims.decode(bytes).canonicalBytes()
            15 -> ProductionC1RouteConnectorMaterial.decode(bytes).canonicalBytes()
            18 -> ProductionC1PreauthorizationSessionContext.decode(bytes).canonicalBytes()
            23, 24 -> ProductionC1CandidateCapability.decode(bytes).canonicalBytes()
            25 -> ProductionC1P2PGrantEvidence.decode(bytes).canonicalBytes()
            26 -> ProductionC1P2PGrantAuthorization.decode(bytes).canonicalBytes()
            27 -> ProductionC1EndpointOperationProof.decode(bytes).canonicalBytes()
            28 -> ProductionC1CandidateOperationReceipt.decode(bytes).canonicalBytes()
            else -> error("unsupported shared object $name type $objectType")
        }

    private fun publicKey(fixture: JsonObject, name: String): PublicKey =
        KeyFactory.getInstance("EC").generatePublic(
            X509EncodedKeySpec(fixture.obj("keys").obj(name).hex("publicKeySPKIDERHex")),
        )

    private fun privateKey(fixture: JsonObject, name: String): PrivateKey {
        val parameters = AlgorithmParameters.getInstance("EC").apply {
            init(ECGenParameterSpec("secp256r1"))
        }
        val curve = parameters.getParameterSpec(ECParameterSpec::class.java)
        val scalar = BigInteger(1, fixture.obj("keys").obj(name).hex("privateScalarHex"))
        return KeyFactory.getInstance("EC").generatePrivate(ECPrivateKeySpec(scalar, curve))
    }

    private fun replaceTLVField(data: ByteArray, tag: Int, replacement: ByteArray): ByteArray {
        var result = data.copyOfRange(0, 6)
        tlvFields(data).forEach { (fieldTag, value) ->
            val actual = if (fieldTag == tag) replacement else value
            result += byteArrayOf(fieldTag.toByte())
            result += ByteBuffer.allocate(4).order(ByteOrder.BIG_ENDIAN).putInt(actual.size).array()
            result += actual
        }
        return result
    }

    private fun tlvFields(data: ByteArray): List<Pair<Int, ByteArray>> {
        val fields = mutableListOf<Pair<Int, ByteArray>>()
        var cursor = 6
        while (cursor < data.size) {
            val tag = data[cursor].toInt() and 0xff
            val size = ByteBuffer.wrap(data, cursor + 1, 4).order(ByteOrder.BIG_ENDIAN).int
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

    private fun loadFixture(): CandidateFixtureDocument {
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
        val fixture = starts.asSequence().flatMap { start ->
            generateSequence(if (Files.isDirectory(start)) start else start.parent) { it.parent }
        }.map { it.resolve(relative) }.firstOrNull(Files::isRegularFile)
            ?: error("shared production G1a-C candidate fixture not found from repository ancestors")
        val bytes = Files.readAllBytes(fixture)
        val root = Json.parseToJsonElement(String(bytes, Charsets.UTF_8)).jsonObject
        var repositoryRoot = fixture
        repeat(relative.nameCount) { repositoryRoot = repositoryRoot.parent }
        return CandidateFixtureDocument(root, bytes, repositoryRoot)
    }

    private fun JsonObject.obj(name: String): JsonObject = getValue(name).jsonObject
    private fun JsonObject.array(name: String): JsonArray = getValue(name).jsonArray
    private fun JsonObject.string(name: String): String = getValue(name).jsonPrimitive.content
    private fun JsonObject.boolean(name: String): Boolean = string(name).toBooleanStrict()
    private fun JsonObject.ulong(name: String): ULong = string(name).toULong()
    private fun JsonObject.int(name: String): Int = string(name).toInt()
    private fun JsonObject.hex(name: String): ByteArray = string(name).hex()

    private fun String.hex(): ByteArray {
        require(isNotEmpty() && length % 2 == 0 && all { it in '0'..'9' || it in 'a'..'f' })
        return chunked(2).map { it.toInt(16).toByte() }.toByteArray()
    }

    private fun sha256Hex(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") {
            (it.toInt() and 0xff).toString(16).padStart(2, '0')
        }

    private data class CandidateFixtureDocument(
        val root: JsonObject,
        val rawBytes: ByteArray,
        val repositoryRoot: Path,
    )

    private data class OperationVector(
        val proof: String,
        val capability: String,
        val batch: String,
        val authorization: String,
        val receipt: String,
    )

    private data class CandidateVectorChain(
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

    private data class HandshakePair(
        val client: ProductionSecureSessionHandshake,
        val runtime: ProductionSecureSessionHandshake,
    ) : AutoCloseable {
        override fun close() {
            client.close()
            runtime.close()
        }
    }

    private data class ActiveSessionPair(
        val client: ProductionSecureSessionCipher,
        val runtime: ProductionSecureSessionCipher,
        val clientConfirmation: ByteArray,
        val runtimeConfirmation: ByteArray,
    ) : AutoCloseable {
        override fun close() {
            client.close()
            runtime.close()
        }
    }

    private companion object {
        const val CANDIDATE_FIXTURE_SHA256 =
            "e6bc666dbf9fded82d5681fdcfdc2c4c9cd5fa197135fc0673569d35656236af"
        const val LEGACY_FIXTURE_SHA256 =
            "c25c0f4d74b0029f060bcedf31b19ef95c57a0a0e6708a741175c8cedeb611f3"
        const val OPERATION_ORDER =
            "client_publish,runtime_fetch_client,runtime_publish,client_fetch_runtime"

        val OPERATIONS = listOf(
            OperationVector(
                "endpointProofClientPublish",
                "capabilityClientPublish",
                "clientCandidateBatch",
                "authorizationClientPublish",
                "receiptClientPublish",
            ),
            OperationVector(
                "endpointProofRuntimeFetchClient",
                "capabilityRuntimeFetchClient",
                "clientCandidateBatch",
                "authorizationRuntimeFetchClient",
                "receiptRuntimeFetchClient",
            ),
            OperationVector(
                "endpointProofRuntimePublish",
                "capabilityRuntimePublish",
                "runtimeCandidateBatch",
                "authorizationRuntimePublish",
                "receiptRuntimePublish",
            ),
            OperationVector(
                "endpointProofClientFetchRuntime",
                "capabilityClientFetchRuntime",
                "runtimeCandidateBatch",
                "authorizationClientFetchRuntime",
                "receiptClientFetchRuntime",
            ),
        )
    }
}
