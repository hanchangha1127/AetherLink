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
import org.junit.Test

class P2pNatSharedVectorTest {
    @Test
    fun allSevenObjectsMatchSharedCanonicalVectors() {
        val root = loadFixture()
        val objects = root.obj("objects")

        val candidateVector = objects.obj("candidateBatch")
        val candidateInput = candidateVector.obj("input")
        val candidateBatch = CandidateBatch(
            sessionId = candidateInput.string("sessionId"),
            generation = candidateInput.ulong("generation"),
            sequence = candidateInput.ulong("sequence"),
            expiresAtMillis = candidateInput.ulong("expiresAtMillis"),
            senderRole = role(candidateInput.string("senderRole")),
            candidates = candidateInput.array("candidates").map { raw ->
                val item = raw.jsonObject
                P2pCandidate(
                    kind = when (item.string("kind")) {
                        "host" -> CandidateKind.HOST
                        "server_reflexive" -> CandidateKind.SERVER_REFLEXIVE
                        "peer_reflexive" -> CandidateKind.PEER_REFLEXIVE
                        "relay" -> CandidateKind.RELAY
                        else -> error("unknown candidate kind")
                    },
                    family = when (item.string("family")) {
                        "ipv4" -> AddressFamily.IPV4
                        "ipv6" -> AddressFamily.IPV6
                        else -> error("unknown address family")
                    },
                    port = item.int("port"),
                    priority = item.uint("priority"),
                    foundation = item.hex("foundationHex"),
                    address = item.hex("addressHex"),
                )
            },
        )
        assertVector(candidateVector, P2pNatCanonicalCodec.encode(candidateBatch), P2pNatCanonicalCodec::decodeCandidateBatch) { P2pNatCanonicalCodec.encode(it) }

        val sealedVector = objects.obj("sealedRouteRecord")
        val sealed = sealedVector.obj("input")
        val sealedRecord = SealedRouteRecord(
            sessionId = sealed.string("sessionId"),
            pairBindingDigest = sealed.string("pairBindingDigest"),
            senderRole = role(sealed.string("senderRole")),
            generation = sealed.ulong("generation"),
            sequence = sealed.ulong("sequence"),
            expiresAtMillis = sealed.ulong("expiresAtMillis"),
            antiReplayNonce = sealed.string("antiReplayNonce"),
            ephemeralPublicKey = sealed.hex("ephemeralPublicKeyHex"),
            sealNonce = sealed.hex("sealNonceHex"),
            ciphertext = sealed.hex("ciphertextHex"),
        )
        assertVector(sealedVector, P2pNatCanonicalCodec.encode(sealedRecord), P2pNatCanonicalCodec::decodeSealedRouteRecord) { P2pNatCanonicalCodec.encode(it) }

        val relayVector = objects.obj("relayCapability")
        val relay = relayVector.obj("input")
        val relayCapability = RelayCapability(
            sessionId = relay.string("sessionId"),
            pairBindingDigest = relay.string("pairBindingDigest"),
            clientFingerprint = relay.string("clientFingerprint"),
            runtimeFingerprint = relay.string("runtimeFingerprint"),
            relayServiceDigest = relay.string("relayServiceDigest"),
            expiresAtMillis = relay.ulong("expiresAtMillis"),
            quotaBytes = relay.ulong("quotaBytes"),
            capabilityNonce = relay.string("capabilityNonce"),
        )
        assertVector(relayVector, P2pNatCanonicalCodec.encode(relayCapability), P2pNatCanonicalCodec::decodeRelayCapability) { P2pNatCanonicalCodec.encode(it) }

        val transcriptVector = objects.obj("identitySessionTranscript")
        val transcriptInput = transcriptVector.obj("input")
        val transcript = IdentitySessionTranscript(
            sessionId = transcriptInput.string("sessionId"),
            pairBindingDigest = transcriptInput.string("pairBindingDigest"),
            clientFingerprint = transcriptInput.string("clientFingerprint"),
            runtimeFingerprint = transcriptInput.string("runtimeFingerprint"),
            clientEphemeralKey = transcriptInput.hex("clientEphemeralKeyHex"),
            runtimeEphemeralKey = transcriptInput.hex("runtimeEphemeralKeyHex"),
            generation = transcriptInput.ulong("generation"),
            pathReceiptDigest = transcriptInput.string("pathReceiptDigest"),
            transportContext = transport(transcriptInput.string("transportContext")),
            fallbackReason = fallback(transcriptInput.string("fallbackReason")),
            protocolFloor = transcriptInput.uint("protocolFloor"),
        )
        assertVector(transcriptVector, P2pNatCanonicalCodec.encode(transcript), P2pNatCanonicalCodec::decodeIdentitySessionTranscript) { P2pNatCanonicalCodec.encode(it) }

        val relayTranscriptVector = objects.obj("relayIdentitySessionTranscript")
        val relayTranscriptInput = relayTranscriptVector.obj("input")
        val relayTranscript = transcript(relayTranscriptInput)
        val relayTranscriptBytes = P2pNatCanonicalCodec.encode(relayTranscript)
        assertEquals(relayTranscriptVector.int("expectedCanonicalByteCount"), relayTranscriptBytes.size)
        assertVector(relayTranscriptVector, relayTranscriptBytes, P2pNatCanonicalCodec::decodeIdentitySessionTranscript) { P2pNatCanonicalCodec.encode(it) }

        val maximumTranscriptVector = objects.obj("maximumIdentitySessionTranscript")
        val maximumTranscript = transcript(maximumTranscriptVector.obj("input"))
        val maximumTranscriptBytes = P2pNatCanonicalCodec.encode(maximumTranscript)
        assertEquals(maximumTranscriptVector.int("expectedCanonicalByteCount"), maximumTranscriptBytes.size)
        assertVector(maximumTranscriptVector, maximumTranscriptBytes, P2pNatCanonicalCodec::decodeIdentitySessionTranscript) { P2pNatCanonicalCodec.encode(it) }

        val receiptVector = objects.obj("pathValidationReceipt")
        val receipt = receiptVector.obj("input")
        val pathValidationReceipt = PathValidationReceipt(
            sessionId = receipt.string("sessionId"),
            generation = receipt.ulong("generation"),
            candidatePairDigest = receipt.string("candidatePairDigest"),
            transportContext = transport(receipt.string("transportContext")),
            clientObservedPathDigest = receipt.string("clientObservedPathDigest"),
            runtimeObservedPathDigest = receipt.string("runtimeObservedPathDigest"),
            validatedAtMillis = receipt.ulong("validatedAtMillis"),
            expiresAtMillis = receipt.ulong("expiresAtMillis"),
        )
        assertVector(receiptVector, P2pNatCanonicalCodec.encode(pathValidationReceipt), P2pNatCanonicalCodec::decodePathValidationReceipt) { P2pNatCanonicalCodec.encode(it) }

        val checks = root.obj("transcriptChecks")
        assertTranscriptChecks(transcript, checks.obj("identitySessionTranscript"))
        assertTranscriptChecks(relayTranscript, checks.obj("relayIdentitySessionTranscript"))
        assertTranscriptChecks(maximumTranscript, checks.obj("maximumIdentitySessionTranscript"))
    }

    @Test
    fun sharedNegativeCanonicalVectorsAreRejectedByProductionDecoders() {
        loadFixture().array("negativeCanonicalVectors").forEach { raw ->
            val vector = raw.jsonObject
            val encoded = vector.hex("canonicalHex")
            val error = assertThrows("vector ${vector.string("id")} must be rejected", P2pNatContractException::class.java) {
                when (vector.string("operation")) {
                    "decodeCandidateBatch" -> P2pNatCanonicalCodec.decodeCandidateBatch(encoded)
                    "decodeSealedRouteRecord" -> P2pNatCanonicalCodec.decodeSealedRouteRecord(encoded)
                    "decodeIdentitySessionTranscript" -> P2pNatCanonicalCodec.decodeIdentitySessionTranscript(encoded)
                    "decodePathValidationReceipt" -> P2pNatCanonicalCodec.decodePathValidationReceipt(encoded)
                    "decodeFreshPathValidationReceipt" -> P2pNatCanonicalCodec.decodeFreshPathValidationReceipt(encoded, vector.ulong("nowMillis"))
                    else -> error("unsupported shared operation ${vector.string("operation")}")
                }
            }
            assertEquals(
                "vector ${vector.string("id")}",
                rejectionClass(vector.string("expectedRejectionClass")),
                error.rejectionClass,
            )
        }
    }

    private fun rejectionClass(value: String): P2pNatRejectionClass =
        P2pNatRejectionClass.entries.singleOrNull { it.wireValue == value }
            ?: error("unknown shared rejection class $value")

    private fun transcript(input: JsonObject) = IdentitySessionTranscript(
        sessionId = input.string("sessionId"),
        pairBindingDigest = input.string("pairBindingDigest"),
        clientFingerprint = input.string("clientFingerprint"),
        runtimeFingerprint = input.string("runtimeFingerprint"),
        clientEphemeralKey = input.hex("clientEphemeralKeyHex"),
        runtimeEphemeralKey = input.hex("runtimeEphemeralKeyHex"),
        generation = input.ulong("generation"),
        pathReceiptDigest = input.string("pathReceiptDigest"),
        transportContext = transport(input.string("transportContext")),
        fallbackReason = fallback(input.string("fallbackReason")),
        protocolFloor = input.uint("protocolFloor"),
    )

    private fun assertTranscriptChecks(transcript: IdentitySessionTranscript, checks: JsonObject) {
        assertArrayEquals(checks.hex("expectedSha256Hex"), transcript.digest())
        val confirmationKey = checks.hex("confirmationKeyHex")
        val expectedMacs = checks.obj("expectedHmacSha256")
        assertArrayEquals(expectedMacs.hex("client"), transcript.keyConfirmation(confirmationKey, P2pNatRole.CLIENT))
        assertArrayEquals(expectedMacs.hex("runtime"), transcript.keyConfirmation(confirmationKey, P2pNatRole.RUNTIME))
    }

    private fun <T> assertVector(
        vector: JsonObject,
        actual: ByteArray,
        decode: (ByteArray) -> T,
        encode: (T) -> ByteArray,
    ) {
        val expected = vector.hex("expectedCanonicalHex")
        assertArrayEquals(expected, actual)
        assertArrayEquals(expected, encode(decode(expected)))
    }

    private fun loadFixture(): JsonObject {
        val relative = Path.of("shared", "protocol", "fixtures", "production-p2p-nat-v1-vectors.json")
        val starts = listOfNotNull(
            Path.of(System.getProperty("user.dir")).toAbsolutePath(),
            javaClass.protectionDomain?.codeSource?.location?.toURI()?.let(Path::of)?.toAbsolutePath(),
        )
        val fixture = starts.asSequence().flatMap { start ->
            generateSequence(if (Files.isDirectory(start)) start else start.parent) { it.parent }
        }.map { it.resolve(relative) }.firstOrNull(Files::isRegularFile)
            ?: error("shared P2P/NAT fixture not found from repository ancestors")
        return Json.parseToJsonElement(String(Files.readAllBytes(fixture), Charsets.UTF_8)).jsonObject
    }

    private fun JsonObject.obj(name: String): JsonObject = getValue(name).jsonObject
    private fun JsonObject.array(name: String): JsonArray = getValue(name).jsonArray
    private fun JsonObject.string(name: String): String = getValue(name).jsonPrimitive.content
    private fun JsonObject.ulong(name: String): ULong = string(name).toULong()
    private fun JsonObject.uint(name: String): UInt = string(name).toUInt()
    private fun JsonObject.int(name: String): Int = string(name).toInt()
    private fun JsonObject.hex(name: String): ByteArray = string(name).chunked(2).map { it.toInt(16).toByte() }.toByteArray()

    private fun role(value: String): P2pNatRole = P2pNatRole.decode(value)
    private fun transport(value: String): TransportContext = TransportContext.decode(value)
    private fun fallback(value: String): FallbackReason = FallbackReason.decode(value)
}
