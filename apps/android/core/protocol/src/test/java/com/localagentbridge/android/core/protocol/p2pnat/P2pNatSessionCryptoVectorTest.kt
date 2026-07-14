package com.localagentbridge.android.core.protocol.p2pnat

import java.nio.file.Files
import java.nio.file.Path
import java.security.NoSuchAlgorithmException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference
import kotlin.concurrent.thread
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Test

class P2pNatSessionCryptoVectorTest {
    @Test
    fun sharedSessionCryptoVectorsMatchOnDirectAndRelayTranscripts() {
        val fixture = loadFixture()
        val agreement = fixture.obj("keyAgreement")
        val clientKey = P2pNatSessionEphemeralKey.fromPrivateScalarForTest(
            agreement.hex("clientPrivateScalarHex"),
        )
        val runtimeKey = P2pNatSessionEphemeralKey.fromPrivateScalarForTest(
            agreement.hex("runtimePrivateScalarHex"),
        )
        assertArrayEquals(agreement.hex("clientPublicKeyX963Hex"), clientKey.publicKeyX963)
        assertArrayEquals(agreement.hex("runtimePublicKeyX963Hex"), runtimeKey.publicKeyX963)

        fixture.array("cases").forEach { raw ->
            val vector = raw.jsonObject
            val transcript = transcript(vector.obj("transcriptInput"))
            val caseClientKey = P2pNatSessionEphemeralKey.fromPrivateScalarForTest(
                agreement.hex("clientPrivateScalarHex"),
            )
            val caseRuntimeKey = P2pNatSessionEphemeralKey.fromPrivateScalarForTest(
                agreement.hex("runtimePrivateScalarHex"),
            )
            val materialClientKey = P2pNatSessionEphemeralKey.fromPrivateScalarForTest(
                agreement.hex("clientPrivateScalarHex"),
            )
            assertArrayEquals(vector.hex("expectedCanonicalHex"), P2pNatCanonicalCodec.encode(transcript))
            val clientKeys = P2pNatSessionCrypto.deriveKeys(P2pNatRole.CLIENT, caseClientKey, transcript)
            val runtimeKeys = P2pNatSessionCrypto.deriveKeys(P2pNatRole.RUNTIME, caseRuntimeKey, transcript)
            val material = P2pNatSessionCrypto.vectorMaterial(P2pNatRole.CLIENT, materialClientKey, transcript)
            val expectedKeys = vector.obj("expectedKeys")
            val expectedConfirmations = vector.obj("expectedConfirmations")

            assertArrayEquals(agreement.hex("expectedSharedSecretHex"), material.sharedSecret)
            assertArrayEquals(vector.hex("expectedHkdfSaltHex"), material.salt)
            assertArrayEquals(vector.hex("expectedHkdfInfoHex"), material.info)
            assertArrayEquals(vector.hex("expectedHkdfPrkHex"), material.prk)
            assertArrayEquals(vector.hex("expectedHkdfOkmHex"), material.okm)
            assertArrayEquals(vector.hex("expectedTranscriptSha256Hex"), clientKeys.transcriptDigest)
            assertArrayEquals(expectedKeys.hex("clientTrafficKeyHex"), clientKeys.clientTrafficKey)
            assertArrayEquals(expectedKeys.hex("runtimeTrafficKeyHex"), clientKeys.runtimeTrafficKey)
            assertArrayEquals(expectedKeys.hex("confirmationKeyHex"), clientKeys.confirmationKey)
            assertArrayEquals(clientKeys.clientTrafficKey, runtimeKeys.clientTrafficKey)
            assertArrayEquals(clientKeys.runtimeTrafficKey, runtimeKeys.runtimeTrafficKey)
            assertArrayEquals(clientKeys.confirmationKey, runtimeKeys.confirmationKey)
            assertArrayEquals(expectedConfirmations.hex("client"), clientKeys.confirmation(P2pNatRole.CLIENT))
            assertArrayEquals(expectedConfirmations.hex("runtime"), clientKeys.confirmation(P2pNatRole.RUNTIME))

            val clientHandshake = P2pNatSessionHandshake(P2pNatRole.CLIENT, clientKeys)
            val runtimeHandshake = P2pNatSessionHandshake(P2pNatRole.RUNTIME, runtimeKeys)
            assertThrows(IllegalStateException::class.java) { clientHandshake.makeCipher() }
            val clientProof = clientHandshake.localConfirmation()
            val runtimeProof = runtimeHandshake.localConfirmation()
            clientHandshake.acceptPeerConfirmation(runtimeProof)
            runtimeHandshake.acceptPeerConfirmation(clientProof)
            val clientCipher = clientHandshake.makeCipher()
            val runtimeCipher = runtimeHandshake.makeCipher()
            assertThrows(IllegalStateException::class.java) { clientHandshake.makeCipher() }

            val expectedClient = vector.obj("traffic").obj("client")
            val clientPlaintext = expectedClient.hex("plaintextHex")
            val clientPayload = clientCipher.seal(clientPlaintext)
            assertArrayEquals(expectedClient.hex("nonceHex"), P2pNatSessionCipher.nonce(P2pNatRole.CLIENT, 0uL))
            assertArrayEquals(expectedClient.hex("aadHex"), P2pNatSessionCipher.aad(transcript, P2pNatRole.CLIENT, 0uL))
            assertArrayEquals(expectedClient.hex("ciphertextHex"), clientPayload.ciphertext)
            assertArrayEquals(expectedClient.hex("tagHex"), clientPayload.tag)
            assertArrayEquals(clientPlaintext, runtimeCipher.open(clientPayload))

            val expectedRuntime = vector.obj("traffic").obj("runtime")
            val runtimePlaintext = expectedRuntime.hex("plaintextHex")
            val runtimePayload = runtimeCipher.seal(runtimePlaintext)
            assertArrayEquals(expectedRuntime.hex("nonceHex"), P2pNatSessionCipher.nonce(P2pNatRole.RUNTIME, 0uL))
            assertArrayEquals(expectedRuntime.hex("aadHex"), P2pNatSessionCipher.aad(transcript, P2pNatRole.RUNTIME, 0uL))
            assertArrayEquals(expectedRuntime.hex("ciphertextHex"), runtimePayload.ciphertext)
            assertArrayEquals(expectedRuntime.hex("tagHex"), runtimePayload.tag)
            assertArrayEquals(runtimePlaintext, clientCipher.open(runtimePayload))
        }
    }

    @Test
    fun leadingZeroScalarAndProviderFailuresFailClosed() {
        val fixture = loadFixture()
        val vector = fixture.obj("keyAgreement").obj("leadingZeroNormalizationCase")
        val client = P2pNatSessionEphemeralKey.fromPrivateScalarForTest(vector.hex("clientPrivateScalarHex"))
        val runtime = P2pNatSessionEphemeralKey.fromPrivateScalarForTest(vector.hex("runtimePrivateScalarHex"))
        val base = fixture.array("cases").first().jsonObject.obj("transcriptInput")
        val transcript = transcript(
            base,
            clientKey = client.publicKeyX963,
            runtimeKey = runtime.publicKeyX963,
        )
        val material = P2pNatSessionCrypto.vectorMaterial(P2pNatRole.CLIENT, client, transcript)

        assertArrayEquals(vector.hex("clientPublicKeyX963Hex"), client.publicKeyX963)
        assertArrayEquals(vector.hex("runtimePublicKeyX963Hex"), runtime.publicKeyX963)
        assertArrayEquals(vector.hex("expectedSharedSecretHex"), material.sharedSecret)
        assertEquals(0, material.sharedSecret.first().toInt())
        assertThrows(IllegalArgumentException::class.java) {
            P2pNatSessionEphemeralKey.fromPrivateScalarForTest(ByteArray(32))
        }
        assertThrows(IllegalArgumentException::class.java) {
            P2pNatSessionEphemeralKey.fromPrivateScalarForTest(
                "ffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551".hex(),
            )
        }
        val negatives = fixture.array("negativeVectors").associate { it.jsonObject.string("id") to it.jsonObject }
        val providerFailure = negatives.getValue("provider_failure")
        assertEquals("derive_keys", providerFailure.string("operation"))
        assertEquals("unavailable_hmac_algorithm", providerFailure.string("mutation"))
        assertEquals("reject_without_provider_fallback", providerFailure.string("expectedResult"))
        assertEquals(listOf("android"), providerFailure.strings("platforms"))
        val providerClient = P2pNatSessionEphemeralKey.fromPrivateScalarForTest(
            fixture.obj("keyAgreement").hex("clientPrivateScalarHex"),
        )
        assertThrows(NoSuchAlgorithmException::class.java) {
            P2pNatSessionCrypto.deriveKeys(
                P2pNatRole.CLIENT,
                providerClient,
                transcript,
                P2pNatJcaAlgorithms(mac = "UnavailableHmac"),
            )
        }

        for ((id, invalidRuntimeKey) in listOf(
            "off_curve_public_key" to (byteArrayOf(0x04) + ByteArray(64)),
            "truncated_public_key" to base.hex("runtimeEphemeralKeyHex").copyOf(64),
        )) {
            val negative = negatives.getValue(id)
            assertEquals("derive_keys", negative.string("operation"))
            assertEquals("reject_before_key_agreement", negative.string("expectedResult"))
            assertEquals(listOf("swift", "android"), negative.strings("platforms"))
            val invalidTranscript = transcript(base, runtimeKey = invalidRuntimeKey)
            val baseClient = P2pNatSessionEphemeralKey.fromPrivateScalarForTest(
                fixture.obj("keyAgreement").hex("clientPrivateScalarHex"),
            )
            assertThrows(IllegalArgumentException::class.java) {
                P2pNatSessionCrypto.deriveKeys(P2pNatRole.CLIENT, baseClient, invalidTranscript)
            }
        }
    }

    @Test
    fun publicKeysSessionKeysAndSealedPayloadsUseDefensiveCopies() {
        val fixture = loadFixture()
        val input = fixture.array("cases").first().jsonObject.obj("transcriptInput")
        val client = P2pNatSessionEphemeralKey.fromPrivateScalarForTest(
            fixture.obj("keyAgreement").hex("clientPrivateScalarHex"),
        )
        val originalPublic = client.publicKeyX963
        client.publicKeyX963.fill(0)
        assertArrayEquals(originalPublic, client.publicKeyX963)

        val transcript = transcript(input)
        val digest = ByteArray(32) { 1 }
        val clientTraffic = ByteArray(32) { 2 }
        val runtimeTraffic = ByteArray(32) { 3 }
        val confirmation = ByteArray(32) { 4 }
        val keys = P2pNatSessionKeys(transcript, digest, clientTraffic, runtimeTraffic, confirmation)
        digest.fill(0)
        clientTraffic.fill(0)
        runtimeTraffic.fill(0)
        confirmation.fill(0)
        assertArrayEquals(ByteArray(32) { 1 }, keys.transcriptDigest)
        assertArrayEquals(ByteArray(32) { 2 }, keys.clientTrafficKey)
        assertArrayEquals(ByteArray(32) { 3 }, keys.runtimeTrafficKey)
        assertArrayEquals(ByteArray(32) { 4 }, keys.confirmationKey)
        keys.clientTrafficKey.fill(9)
        keys.runtimeTrafficKey.fill(9)
        keys.confirmationKey.fill(9)
        assertArrayEquals(ByteArray(32) { 2 }, keys.clientTrafficKey)
        assertArrayEquals(ByteArray(32) { 3 }, keys.runtimeTrafficKey)
        assertArrayEquals(ByteArray(32) { 4 }, keys.confirmationKey)

        val ciphertext = byteArrayOf(1, 2, 3)
        val tag = ByteArray(16) { 4 }
        val payload = P2pNatSealedPayload(ciphertext, tag)
        ciphertext.fill(0)
        tag.fill(0)
        payload.ciphertext.fill(9)
        payload.tag.fill(9)
        assertArrayEquals(byteArrayOf(1, 2, 3), payload.ciphertext)
        assertArrayEquals(ByteArray(16) { 4 }, payload.tag)

        val invalidKeys = P2pNatSessionKeys(
            transcript,
            ByteArray(32),
            ByteArray(32),
            ByteArray(32),
            ByteArray(0),
        )
        val handshake = P2pNatSessionHandshake(P2pNatRole.CLIENT, invalidKeys)
        assertThrows(IllegalArgumentException::class.java) { handshake.localConfirmation() }
        assertThrows(IllegalStateException::class.java) { handshake.makeCipher() }
    }

    @Test
    fun confirmationTamperingReplayAndTranscriptSubstitutionFailClosed() {
        val fixture = loadFixture()
        val expectedNegativeIds = setOf(
            "off_curve_public_key", "truncated_public_key", "zero_private_scalar",
            "out_of_range_private_scalar", "transcript_substitution", "role_reflection",
            "generation_replay", "nonce_reuse", "modified_gcm_tag", "provider_failure",
        )
        assertEquals(
            expectedNegativeIds,
            fixture.array("negativeVectors").map { it.jsonObject.string("id") }.toSet(),
        )
        val vector = fixture.array("cases").first().jsonObject
        val input = vector.obj("transcriptInput")
        val transcript = transcript(input)
        val agreement = fixture.obj("keyAgreement")
        val client = P2pNatSessionEphemeralKey.fromPrivateScalarForTest(agreement.hex("clientPrivateScalarHex"))
        val runtime = P2pNatSessionEphemeralKey.fromPrivateScalarForTest(agreement.hex("runtimePrivateScalarHex"))
        val clientKeys = P2pNatSessionCrypto.deriveKeys(P2pNatRole.CLIENT, client, transcript)
        val runtimeKeys = P2pNatSessionCrypto.deriveKeys(P2pNatRole.RUNTIME, runtime, transcript)

        val firstHandshake = P2pNatSessionHandshake(P2pNatRole.CLIENT, clientKeys)
        val duplicateHandshake = P2pNatSessionHandshake(P2pNatRole.CLIENT, clientKeys)
        firstHandshake.localConfirmation()
        duplicateHandshake.localConfirmation()
        val runtimeProof = runtimeKeys.confirmation(P2pNatRole.RUNTIME)
        firstHandshake.acceptPeerConfirmation(runtimeProof)
        duplicateHandshake.acceptPeerConfirmation(runtimeProof)
        val start = CountDownLatch(1)
        val issuanceSuccesses = AtomicInteger()
        val issuanceFailures = AtomicInteger()
        val unexpectedFailure = AtomicReference<Throwable?>()
        val issuanceThreads = listOf(firstHandshake, duplicateHandshake).map { handshake ->
            thread {
                start.await()
                try {
                    handshake.makeCipher()
                    issuanceSuccesses.incrementAndGet()
                } catch (_: IllegalStateException) {
                    issuanceFailures.incrementAndGet()
                } catch (error: Throwable) {
                    unexpectedFailure.compareAndSet(null, error)
                }
            }
        }
        start.countDown()
        issuanceThreads.forEach { it.join() }
        assertEquals(null, unexpectedFailure.get())
        assertEquals(1, issuanceSuccesses.get())
        assertEquals(1, issuanceFailures.get())

        val consumedEphemeral = P2pNatSessionEphemeralKey.fromPrivateScalarForTest(
            agreement.hex("clientPrivateScalarHex"),
        )
        P2pNatSessionCrypto.deriveKeys(P2pNatRole.CLIENT, consumedEphemeral, transcript)
        assertThrows(IllegalStateException::class.java) {
            P2pNatSessionCrypto.deriveKeys(P2pNatRole.CLIENT, consumedEphemeral, transcript)
        }

        val reflected = P2pNatSessionHandshake(P2pNatRole.CLIENT, clientKeys)
        assertThrows(IllegalArgumentException::class.java) {
            reflected.acceptPeerConfirmation(clientKeys.confirmation(P2pNatRole.CLIENT))
        }

        val sender = P2pNatSessionCipher(P2pNatRole.CLIENT, clientKeys)
        val receiver = P2pNatSessionCipher(P2pNatRole.RUNTIME, runtimeKeys)
        val payload = sender.seal("authenticated".encodeToByteArray())
        val tampered = payload.copy(tag = payload.tag.copyOf().also { it[0] = (it[0].toInt() xor 1).toByte() })
        assertThrows(Exception::class.java) { receiver.open(tampered) }
        assertEquals("authenticated", receiver.open(payload).decodeToString())
        assertThrows(Exception::class.java) { receiver.open(payload) }

        val substituted = transcript(input, pairDigest = "1".repeat(64))
        val substitutedRuntime = P2pNatSessionEphemeralKey.fromPrivateScalarForTest(
            agreement.hex("runtimePrivateScalarHex"),
        )
        val substitutedKeys = P2pNatSessionCrypto.deriveKeys(P2pNatRole.RUNTIME, substitutedRuntime, substituted)
        val wrongTranscriptReceiver = P2pNatSessionCipher(P2pNatRole.RUNTIME, substitutedKeys)
        val freshSender = P2pNatSessionCipher(P2pNatRole.CLIENT, clientKeys)
        assertThrows(Exception::class.java) {
            wrongTranscriptReceiver.open(freshSender.seal("bound".encodeToByteArray()))
        }

        val replayedGeneration = transcript(input, generation = input.ulong("generation") + 1uL)
        val replayRuntime = P2pNatSessionEphemeralKey.fromPrivateScalarForTest(
            agreement.hex("runtimePrivateScalarHex"),
        )
        val replayKeys = P2pNatSessionCrypto.deriveKeys(P2pNatRole.RUNTIME, replayRuntime, replayedGeneration)
        assertThrows(Exception::class.java) {
            P2pNatSessionCipher(P2pNatRole.RUNTIME, replayKeys).open(
                P2pNatSessionCipher(P2pNatRole.CLIENT, clientKeys).seal("generation-bound".encodeToByteArray()),
            )
        }
        assertFalse(clientKeys.confirmation(P2pNatRole.CLIENT).contentEquals(clientKeys.confirmation(P2pNatRole.RUNTIME)))
    }

    @Test
    fun counterExhaustionFailsBeforeCryptography() {
        val fixture = loadFixture()
        val input = fixture.array("cases").first().jsonObject.obj("transcriptInput")
        val transcript = transcript(input)
        val agreement = fixture.obj("keyAgreement")
        val client = P2pNatSessionEphemeralKey.fromPrivateScalarForTest(agreement.hex("clientPrivateScalarHex"))
        val runtime = P2pNatSessionEphemeralKey.fromPrivateScalarForTest(agreement.hex("runtimePrivateScalarHex"))
        val keys = P2pNatSessionCrypto.deriveKeys(P2pNatRole.CLIENT, client, transcript)
        val runtimeKeys = P2pNatSessionCrypto.deriveKeys(P2pNatRole.RUNTIME, runtime, transcript)
        assertArrayEquals(
            "434c4e54fffffffffffffffe".hex(),
            P2pNatSessionCipher.nonce(P2pNatRole.CLIENT, ULong.MAX_VALUE - 1uL),
        )
        assertThrows(IllegalArgumentException::class.java) {
            P2pNatSessionCipher.nonce(P2pNatRole.CLIENT, ULong.MAX_VALUE)
        }

        val nearLimitClient = P2pNatSessionCipher(
            P2pNatRole.CLIENT,
            keys,
            sendSequence = ULong.MAX_VALUE - 2uL,
            receiveSequence = ULong.MAX_VALUE - 2uL,
        )
        val nearLimitRuntime = P2pNatSessionCipher(
            P2pNatRole.RUNTIME,
            runtimeKeys,
            sendSequence = ULong.MAX_VALUE - 2uL,
            receiveSequence = ULong.MAX_VALUE - 2uL,
        )
        assertEquals("client", nearLimitRuntime.open(nearLimitClient.seal("client".encodeToByteArray())).decodeToString())
        assertEquals("runtime", nearLimitClient.open(nearLimitRuntime.seal("runtime".encodeToByteArray())).decodeToString())
        assertThrows(IllegalArgumentException::class.java) { nearLimitClient.seal(byteArrayOf(1)) }
        assertThrows(IllegalArgumentException::class.java) {
            nearLimitClient.open(P2pNatSealedPayload(ByteArray(0), ByteArray(16)))
        }

        val exhausted = P2pNatSessionCipher(
            P2pNatRole.CLIENT,
            keys,
            sendSequence = ULong.MAX_VALUE - 1uL,
            receiveSequence = ULong.MAX_VALUE - 1uL,
        )

        assertThrows(IllegalArgumentException::class.java) { exhausted.seal(byteArrayOf(1)) }
        assertThrows(IllegalArgumentException::class.java) {
            exhausted.open(P2pNatSealedPayload(ByteArray(0), ByteArray(16)))
        }
    }

    private fun transcript(
        input: JsonObject,
        pairDigest: String = input.string("pairBindingDigest"),
        generation: ULong = input.ulong("generation"),
        clientKey: ByteArray = input.hex("clientEphemeralKeyHex"),
        runtimeKey: ByteArray = input.hex("runtimeEphemeralKeyHex"),
    ) = IdentitySessionTranscript(
        sessionId = input.string("sessionId"),
        pairBindingDigest = pairDigest,
        clientFingerprint = input.string("clientFingerprint"),
        runtimeFingerprint = input.string("runtimeFingerprint"),
        clientEphemeralKey = clientKey,
        runtimeEphemeralKey = runtimeKey,
        generation = generation,
        pathReceiptDigest = input.string("pathReceiptDigest"),
        transportContext = TransportContext.decode(input.string("transportContext")),
        fallbackReason = FallbackReason.decode(input.string("fallbackReason")),
        protocolFloor = input.uint("protocolFloor"),
    )

    private fun loadFixture(): JsonObject {
        val relative = Path.of(
            "shared", "protocol", "fixtures", "production-p2p-nat-v1-session-crypto-vectors.json",
        )
        val starts = listOfNotNull(
            Path.of(System.getProperty("user.dir")).toAbsolutePath(),
            javaClass.protectionDomain?.codeSource?.location?.toURI()?.let(Path::of)?.toAbsolutePath(),
        )
        val path = starts.asSequence().flatMap { start ->
            generateSequence(if (Files.isDirectory(start)) start else start.parent) { it.parent }
        }.map { it.resolve(relative) }.firstOrNull(Files::isRegularFile)
            ?: error("shared P2P/NAT session crypto fixture not found")
        return Json.parseToJsonElement(String(Files.readAllBytes(path), Charsets.UTF_8)).jsonObject
    }

    private fun JsonObject.obj(name: String): JsonObject = getValue(name).jsonObject
    private fun JsonObject.array(name: String): JsonArray = getValue(name).jsonArray
    private fun JsonObject.string(name: String): String = getValue(name).jsonPrimitive.content
    private fun JsonObject.ulong(name: String): ULong = string(name).toULong()
    private fun JsonObject.uint(name: String): UInt = string(name).toUInt()
    private fun JsonObject.hex(name: String): ByteArray = string(name).hex()
    private fun JsonObject.strings(name: String): List<String> =
        array(name).map { it.jsonPrimitive.content }
    private fun String.hex(): ByteArray = chunked(2).map { it.toInt(16).toByte() }.toByteArray()
}
