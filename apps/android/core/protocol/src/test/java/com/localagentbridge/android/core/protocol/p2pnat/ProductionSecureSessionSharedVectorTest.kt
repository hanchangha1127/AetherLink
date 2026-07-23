package com.localagentbridge.android.core.protocol.p2pnat

import java.nio.ByteBuffer
import java.nio.ByteOrder
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
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class ProductionSecureSessionSharedVectorTest {
    @Test
    fun allSixRoutesMatchSharedCanonicalVectorsAndRoundTrip() {
        val fixture = loadFixture()
        assertEquals(
            "aetherlink-production-secure-session-route-binding-v1-vectors",
            fixture.string("schema"),
        )
        assertEquals(1, fixture.int("version"))
        assertEquals("ALS1", fixture.string("magic"))
        assertEquals(ProductionSecureSessionContract.SUITE, fixture.string("suite"))
        val routes = fixture.array("routes")
        assertEquals(6, routes.size)

        routes.forEach { raw ->
            val vector = raw.jsonObject
            val route = route(vector)
            val encoded = ProductionSecureSessionCodec.encode(route)
            val expected = vector.hex("expectedCanonicalHex")

            assertEquals(vector.string("id"), vector.int("expectedCanonicalByteCount"), encoded.size)
            assertArrayEquals(vector.string("id"), expected, encoded)
            assertArrayEquals(
                vector.string("id"),
                vector.hex("expectedSha256Hex"),
                ProductionSecureSessionCodec.digest(route),
            )
            assertArrayEquals(
                vector.string("id"),
                expected,
                ProductionSecureSessionCodec.encode(
                    ProductionSecureSessionCodec.decodeRouteAuthorization(expected),
                ),
            )
        }
    }

    @Test
    fun allSixTranscriptsMatchSharedCanonicalVectorsRoundTripAndMatchRoutes() {
        val fixture = loadFixture()
        val routesByKind = fixture.array("routes")
            .associate { raw -> raw.jsonObject.string("kind") to route(raw.jsonObject) }
        val transcripts = fixture.array("transcripts")
        assertEquals(6, transcripts.size)

        transcripts.forEach { raw ->
            val vector = raw.jsonObject
            val transcript = transcript(vector.obj("input"))
            val route = requireNotNull(routesByKind[transcript.routeAuthorizationKind.wireValue])
            val encoded = ProductionSecureSessionCodec.encode(transcript)
            val expected = vector.hex("expectedCanonicalHex")

            assertEquals(vector.string("id"), vector.int("expectedCanonicalByteCount"), encoded.size)
            assertArrayEquals(vector.string("id"), expected, encoded)
            assertArrayEquals(
                vector.string("id"),
                vector.hex("expectedSha256Hex"),
                ProductionSecureSessionCodec.digest(transcript),
            )
            val decoded = ProductionSecureSessionCodec.decodeTranscript(expected)
            assertEquals(vector.string("id"), transcript, decoded)
            assertEquals(vector.string("id"), transcript.hashCode(), decoded.hashCode())
            assertArrayEquals(
                vector.string("id"),
                expected,
                ProductionSecureSessionCodec.encode(decoded),
            )
            assertTrue(vector.string("id"), ProductionSecureSessionCodec.matches(transcript, route))
        }
    }

    @Test
    fun routeMatchingRejectsWrongKindDigestPairEpochAndGenerationButLocalIgnoresGeneration() {
        val fixture = loadFixture()
        val routesByKind = fixture.array("routes")
            .associate { raw -> raw.jsonObject.string("kind") to route(raw.jsonObject) }
        val transcriptsByKind = fixture.array("transcripts")
            .associate { raw ->
                val parsed = transcript(raw.jsonObject.obj("input"))
                parsed.routeAuthorizationKind.wireValue to parsed
            }

        val publishRoute = requireNotNull(routesByKind["p2p_publish"])
        val publish = requireNotNull(transcriptsByKind["p2p_publish"])
        assertTrue(ProductionSecureSessionCodec.matches(publish, publishRoute))
        assertFalse(
            ProductionSecureSessionCodec.matches(
                copyTranscript(publish, routeAuthorizationKind = ProductionRouteAuthorizationKind.P2P_FETCH),
                publishRoute,
            ),
        )
        assertFalse(
            ProductionSecureSessionCodec.matches(
                copyTranscript(publish, routeAuthorizationDigest = "0".repeat(64)),
                publishRoute,
            ),
        )
        assertFalse(
            ProductionSecureSessionCodec.matches(
                copyTranscript(publish, pairBindingDigest = "f".repeat(64)),
                publishRoute,
            ),
        )
        assertFalse(
            ProductionSecureSessionCodec.matches(
                copyTranscript(publish, pairEpoch = publish.pairEpoch + 1uL),
                publishRoute,
            ),
        )
        assertFalse(
            ProductionSecureSessionCodec.matches(
                copyTranscript(publish, generation = publish.generation + 1uL),
                publishRoute,
            ),
        )

        val localRoute = requireNotNull(routesByKind["local_direct"])
        val local = requireNotNull(transcriptsByKind["local_direct"])
        assertTrue(
            "local-direct route matching deliberately has no route generation",
            ProductionSecureSessionCodec.matches(
                copyTranscript(local, generation = local.generation + 99uL),
                localRoute,
            ),
        )
    }

    @Test
    fun malformedTagsTrailingAndOversizeFramesFailClosed() {
        val fixture = loadFixture()
        val routeBytes = fixture.array("routes").first().jsonObject.hex("expectedCanonicalHex")
        val transcriptBytes = fixture.array("transcripts").first().jsonObject.hex("expectedCanonicalHex")

        val duplicate = routeBytes.copyOf().also { it[tagOffset(it, 2)] = 1 }
        assertThrows(IllegalArgumentException::class.java) {
            ProductionSecureSessionCodec.decodeRouteAuthorization(duplicate)
        }

        val reordered = routeBytes.copyOf().also {
            val first = tagOffset(it, 1)
            val second = tagOffset(it, 2)
            it[first] = 2
            it[second] = 1
        }
        assertThrows(IllegalArgumentException::class.java) {
            ProductionSecureSessionCodec.decodeRouteAuthorization(reordered)
        }

        val unknown = routeBytes.copyOf().also { it[tagOffset(it, 1)] = 99 }
        assertThrows(IllegalArgumentException::class.java) {
            ProductionSecureSessionCodec.decodeRouteAuthorization(unknown)
        }

        assertThrows(IllegalArgumentException::class.java) {
            ProductionSecureSessionCodec.decodeRouteAuthorization(routeBytes + byteArrayOf(0))
        }
        assertThrows(IllegalArgumentException::class.java) {
            ProductionSecureSessionCodec.decodeTranscript(transcriptBytes + byteArrayOf(0))
        }
        assertThrows(IllegalArgumentException::class.java) {
            ProductionSecureSessionCodec.decodeRouteAuthorization(
                ByteArray(ProductionSecureSessionContract.MAX_ROUTE_BYTES + 1),
            )
        }
        assertThrows(IllegalArgumentException::class.java) {
            ProductionSecureSessionCodec.decodeTranscript(
                ByteArray(ProductionSecureSessionContract.MAX_TRANSCRIPT_BYTES + 1),
            )
        }

        val wrongMagic = transcriptBytes.copyOf().also { it[0] = 'X'.code.toByte() }
        assertThrows(IllegalArgumentException::class.java) {
            ProductionSecureSessionCodec.decodeTranscript(wrongMagic)
        }
        val wrongType = transcriptBytes.copyOf().also { it[4] = 1 }
        assertThrows(IllegalArgumentException::class.java) {
            ProductionSecureSessionCodec.decodeTranscript(wrongType)
        }
        val wrongVersion = transcriptBytes.copyOf().also { it[5] = 2 }
        assertThrows(IllegalArgumentException::class.java) {
            ProductionSecureSessionCodec.decodeTranscript(wrongVersion)
        }
        val transcriptDuplicate = transcriptBytes.copyOf().also { it[tagOffset(it, 2)] = 1 }
        assertThrows(IllegalArgumentException::class.java) {
            ProductionSecureSessionCodec.decodeTranscript(transcriptDuplicate)
        }
        val transcriptReordered = transcriptBytes.copyOf().also {
            it[tagOffset(it, 1)] = 2
            it[tagOffset(it, 2)] = 1
        }
        assertThrows(IllegalArgumentException::class.java) {
            ProductionSecureSessionCodec.decodeTranscript(transcriptReordered)
        }
        val transcriptUnknown = transcriptBytes.copyOf().also { it[tagOffset(it, 1)] = 99 }
        assertThrows(IllegalArgumentException::class.java) {
            ProductionSecureSessionCodec.decodeTranscript(transcriptUnknown)
        }
        val malformedLength = transcriptBytes.copyOf().also {
            val firstTag = tagOffset(it, 1)
            for (index in firstTag + 1..firstTag + 4) it[index] = 0x7f
        }
        assertThrows(IllegalArgumentException::class.java) {
            ProductionSecureSessionCodec.decodeTranscript(malformedLength)
        }
    }

    @Test
    fun invalidIdentityKeyAndNonceFailClosed() {
        val fixture = loadFixture()
        val base = transcript(fixture.array("transcripts").first().jsonObject.obj("input"))
        val canonical = ProductionSecureSessionCodec.encode(base)

        assertThrows(IllegalArgumentException::class.java) {
            ProductionSecureSessionCodec.encode(
                copyTranscript(base, runtimeIdentityFingerprint = base.clientIdentityFingerprint),
            )
        }
        assertThrows(IllegalArgumentException::class.java) {
            ProductionSecureSessionCodec.encode(
                copyTranscript(base, runtimeEphemeralPublicKey = ByteArray(65)),
            )
        }
        assertThrows(IllegalArgumentException::class.java) {
            ProductionSecureSessionCodec.encode(
                copyTranscript(base, runtimeNonce = base.clientNonce),
            )
        }
        assertThrows(IllegalArgumentException::class.java) {
            ProductionSecureSessionCodec.encode(
                copyTranscript(base, clientNonce = base.clientNonce.uppercase()),
            )
        }

        assertThrows(IllegalArgumentException::class.java) {
            ProductionSecureSessionCodec.decodeTranscript(
                replacingField(canonical, 6, fieldValue(canonical, 5)),
            )
        }
        assertThrows(IllegalArgumentException::class.java) {
            ProductionSecureSessionCodec.decodeTranscript(
                replacingField(canonical, 10, fieldValue(canonical, 9)),
            )
        }
        val offCurveKey = ByteArray(65).also { it[0] = 0x04 }
        assertThrows(IllegalArgumentException::class.java) {
            ProductionSecureSessionCodec.decodeTranscript(
                replacingField(canonical, 10, offCurveKey),
            )
        }
        assertThrows(IllegalArgumentException::class.java) {
            ProductionSecureSessionCodec.decodeTranscript(
                replacingField(canonical, 12, fieldValue(canonical, 11)),
            )
        }
        val uppercaseNonce = fieldValue(canonical, 11).also { nonce ->
            val index = nonce.indexOf('a'.code.toByte())
            require(index >= 0)
            nonce[index] = 'A'.code.toByte()
        }
        assertThrows(IllegalArgumentException::class.java) {
            ProductionSecureSessionCodec.decodeTranscript(
                replacingField(canonical, 11, uppercaseNonce),
            )
        }
    }

    private fun route(vector: JsonObject): ProductionRouteAuthorization {
        val input = vector.obj("input")
        assertEquals(ProductionSecureSessionContract.SUITE, input.string("suite"))
        val pair = input.string("pairBindingDigest")
        val epoch = input.ulong("pairEpoch")
        return when (vector.string("kind")) {
            "local_direct" -> LocalDirectRouteAuthorization(
                pair,
                epoch,
                input.string("nominatedPathReceiptDigest"),
            )

            "p2p_publish" -> P2pPublishRouteAuthorization(
                pair,
                epoch,
                input.ulong("generation"),
                input.string("candidateBatchDigest"),
                input.string("publishCapabilityDigest"),
            )

            "p2p_fetch" -> P2pFetchRouteAuthorization(
                pair,
                epoch,
                input.ulong("generation"),
                input.string("candidateBatchDigest"),
                input.string("fetchCapabilityDigest"),
            )

            "p2p_direct" -> P2pDirectRouteAuthorization(
                pair,
                epoch,
                input.ulong("generation"),
                input.string("candidatePairDigest"),
                input.string("pathValidationReceiptDigest"),
                input.string("publishCapabilityDigest"),
                input.string("fetchCapabilityDigest"),
            )

            "turn_relay" -> TurnRelayRouteAuthorization(
                pair,
                epoch,
                input.ulong("generation"),
                input.string("turnLeaseDigest"),
                input.string("allocationDigest"),
                input.string("pathValidationReceiptDigest"),
            )

            "sealed_relay" -> SealedRelayRouteAuthorization(
                pair,
                epoch,
                input.ulong("generation"),
                input.string("sealedRelayLeaseDigest"),
                input.string("allocationDigest"),
                input.string("pathValidationReceiptDigest"),
            )

            else -> error("unsupported production route kind ${vector.string("kind")}")
        }
    }

    private fun transcript(input: JsonObject): ProductionSecureSessionTranscript {
        assertEquals("client", input.string("clientRole"))
        assertEquals("runtime", input.string("runtimeRole"))
        return ProductionSecureSessionTranscript(
            suite = input.string("suite"),
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

    private fun copyTranscript(
        value: ProductionSecureSessionTranscript,
        sessionId: String = value.sessionId,
        pairBindingDigest: String = value.pairBindingDigest,
        pairEpoch: ULong = value.pairEpoch,
        clientIdentityFingerprint: String = value.clientIdentityFingerprint,
        runtimeIdentityFingerprint: String = value.runtimeIdentityFingerprint,
        clientEphemeralPublicKey: ByteArray = value.clientEphemeralPublicKey,
        runtimeEphemeralPublicKey: ByteArray = value.runtimeEphemeralPublicKey,
        clientNonce: String = value.clientNonce,
        runtimeNonce: String = value.runtimeNonce,
        generation: ULong = value.generation,
        serviceConfigVersion: ULong = value.serviceConfigVersion,
        keysetVersion: ULong = value.keysetVersion,
        revocationCounter: ULong = value.revocationCounter,
        protocolVersion: UInt = value.protocolVersion,
        minimumProtocolVersion: UInt = value.minimumProtocolVersion,
        profile: String = value.profile,
        routeAuthorizationKind: ProductionRouteAuthorizationKind = value.routeAuthorizationKind,
        routeAuthorizationDigest: String = value.routeAuthorizationDigest,
        suite: String = value.suite,
    ): ProductionSecureSessionTranscript = ProductionSecureSessionTranscript(
        sessionId = sessionId,
        pairBindingDigest = pairBindingDigest,
        pairEpoch = pairEpoch,
        clientIdentityFingerprint = clientIdentityFingerprint,
        runtimeIdentityFingerprint = runtimeIdentityFingerprint,
        clientEphemeralPublicKey = clientEphemeralPublicKey,
        runtimeEphemeralPublicKey = runtimeEphemeralPublicKey,
        clientNonce = clientNonce,
        runtimeNonce = runtimeNonce,
        generation = generation,
        serviceConfigVersion = serviceConfigVersion,
        keysetVersion = keysetVersion,
        revocationCounter = revocationCounter,
        protocolVersion = protocolVersion,
        minimumProtocolVersion = minimumProtocolVersion,
        profile = profile,
        routeAuthorizationKind = routeAuthorizationKind,
        routeAuthorizationDigest = routeAuthorizationDigest,
        suite = suite,
    )

    private fun tagOffset(encoded: ByteArray, fieldNumber: Int): Int {
        require(fieldNumber > 0)
        var offset = 6
        repeat(fieldNumber - 1) {
            require(offset + 5 <= encoded.size)
            val length = ByteBuffer.wrap(encoded, offset + 1, 4)
                .order(ByteOrder.BIG_ENDIAN)
                .int
            require(length >= 0 && offset + 5 + length <= encoded.size)
            offset += 5 + length
        }
        require(offset < encoded.size)
        return offset
    }

    private fun fieldValue(encoded: ByteArray, fieldNumber: Int): ByteArray {
        val tag = tagOffset(encoded, fieldNumber)
        val length = ByteBuffer.wrap(encoded, tag + 1, 4)
            .order(ByteOrder.BIG_ENDIAN)
            .int
        require(length >= 0 && tag + 5 + length <= encoded.size)
        return encoded.copyOfRange(tag + 5, tag + 5 + length)
    }

    private fun replacingField(
        encoded: ByteArray,
        fieldNumber: Int,
        replacement: ByteArray,
    ): ByteArray {
        val tag = tagOffset(encoded, fieldNumber)
        val original = fieldValue(encoded, fieldNumber)
        require(original.size == replacement.size)
        return encoded.copyOf().also {
            replacement.copyInto(it, destinationOffset = tag + 5)
        }
    }

    private fun loadFixture(): JsonObject {
        val relative = Path.of(
            "shared",
            "protocol",
            "fixtures",
            "production-secure-session-route-binding-v1-vectors.json",
        )
        val starts = listOfNotNull(
            Path.of(System.getProperty("user.dir")).toAbsolutePath(),
            javaClass.protectionDomain?.codeSource?.location?.toURI()?.let(Path::of)?.toAbsolutePath(),
        )
        val fixture = starts.asSequence().flatMap { start ->
            generateSequence(if (Files.isDirectory(start)) start else start.parent) { it.parent }
        }.map { it.resolve(relative) }.firstOrNull(Files::isRegularFile)
            ?: error("shared production secure-session fixture not found from repository ancestors")
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
