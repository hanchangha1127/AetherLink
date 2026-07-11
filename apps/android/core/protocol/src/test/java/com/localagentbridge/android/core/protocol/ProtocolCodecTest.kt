package com.localagentbridge.android.core.protocol

import kotlinx.serialization.encodeToString
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.ByteArrayInputStream

class ProtocolCodecTest {
    @Test
    fun pairingProofPayloadsUseStableWireFieldNamesAndDecodeRejectedResults() {
        val transportBinding = "0123456789abcdef".repeat(4)
        val requestDigest = "fedcba9876543210".repeat(4)
        val request = PairingRequestPayload(
            pairingNonce = "nonce-1",
            pairingCode = "123456",
            deviceId = "client-1",
            deviceName = "AetherLink Client",
            publicKey = "public-key-1",
            pairingProofScheme = PAIRING_PROOF_SCHEME_P256_SHA256_DER_V1,
            pairingSignature = "client-signature-1",
            transportBinding = transportBinding,
        )
        val requestJson = Json.parseToJsonElement(Json.encodeToString(request)).jsonObject

        assertEquals(PAIRING_PROOF_SCHEME_P256_SHA256_DER_V1, requestJson["pairing_proof_scheme"]?.jsonPrimitive?.content)
        assertEquals("client-signature-1", requestJson["pairing_signature"]?.jsonPrimitive?.content)
        assertEquals(transportBinding, requestJson["transport_binding"]?.jsonPrimitive?.content)

        val accepted = PairingResultPayload(
            accepted = true,
            runtimeDeviceIdV2 = "runtime-1",
            runtimePublicKey = "runtime-public-key-1",
            runtimeKeyFingerprint = "runtime-fingerprint-1",
            trustedDeviceId = "client-1",
            message = "paired",
            pairingProofScheme = PAIRING_PROOF_SCHEME_P256_SHA256_DER_V1,
            pairingRequestDigest = requestDigest,
            runtimePairingSignature = "runtime-signature-1",
            transportBinding = transportBinding,
        )
        val acceptedJson = Json.parseToJsonElement(Json.encodeToString(accepted)).jsonObject
        assertEquals(PAIRING_PROOF_SCHEME_P256_SHA256_DER_V1, acceptedJson["pairing_proof_scheme"]?.jsonPrimitive?.content)
        assertEquals(requestDigest, acceptedJson["pairing_request_digest"]?.jsonPrimitive?.content)
        assertEquals("runtime-signature-1", acceptedJson["runtime_pairing_signature"]?.jsonPrimitive?.content)
        assertEquals(transportBinding, acceptedJson["transport_binding"]?.jsonPrimitive?.content)

        val rejected = Json.decodeFromString<PairingResultPayload>(
            """{"accepted":false,"message":"invalid pairing proof"}"""
        )
        assertEquals(false, rejected.accepted)
        assertEquals(null, rejected.pairingProofScheme)
        assertEquals(null, rejected.pairingRequestDigest)
        assertEquals(null, rejected.runtimePairingSignature)
        assertEquals(null, rejected.transportBinding)
    }

    @Test
    fun relayAllocationChallengePayloadRoundTripsExactWireShape() {
        val payload = relayAllocationChallengePayload()
        val encoded = Json.encodeToString(payload)
        val objectValue = Json.parseToJsonElement(encoded).jsonObject
        val decoded = Json.decodeFromString<RelayAllocationChallengePayload>(encoded)

        assertEquals(payload, decoded)
        assertEquals(
            setOf(
                "proof_scheme",
                "protocol_version",
                "operation",
                "authorization_id",
                "current_relay_id",
                "next_relay_id",
                "route_token_hash",
                "runtime_key_fingerprint",
                "client_key_fingerprint",
                "current_ticket_generation",
                "next_ticket_generation",
                "current_relay_expires_at",
                "current_relay_nonce",
                "next_relay_expires_at",
                "next_relay_nonce",
                "challenge",
                "challenge_expires_at",
                "transport_binding",
            ),
            objectValue.keys,
        )
        assertFalse("request_id" in objectValue)
        assertEquals("relay.allocation.challenge", MessageType.RelayAllocationChallenge)
        assertEquals("relay.allocation.authorization", MessageType.RelayAllocationAuthorization)
    }

    @Test
    fun relayAllocationChallengePayloadRejectsMalformedAndSecretBearingSamples() {
        val permissiveJson = Json { ignoreUnknownKeys = true }
        val base = Json.parseToJsonElement(Json.encodeToString(relayAllocationChallengePayload())).jsonObject
        val invalidSamples = mutableListOf(
            "missing field" to base.removing("authorization_id"),
            "unknown field" to base.replacing("unknown", JsonPrimitive("metadata")),
            "route token secret" to base.replacing("route_token", JsonPrimitive("secret")),
            "relay secret" to base.replacing("relay_secret", JsonPrimitive("secret")),
            "wrong scheme" to base.replacing("proof_scheme", JsonPrimitive("runtime-p256-v1")),
            "wrong version" to base.replacing("protocol_version", JsonPrimitive(1)),
            "wrong operation" to base.replacing("operation", JsonPrimitive("create")),
            "blank authorization id" to base.replacing("authorization_id", JsonPrimitive("   ")),
            "oversized authorization id" to base.replacing("authorization_id", JsonPrimitive("a".repeat(513))),
            "legacy relay id" to base.replacing("relay_id", JsonPrimitive("rt2-$allocationHexA")),
            "malformed current relay id" to base.replacing("current_relay_id", JsonPrimitive(allocationHexA)),
            "malformed next relay id" to base.replacing("next_relay_id", JsonPrimitive(allocationHexB)),
            "equal claim relay ids" to base.replacing("next_relay_id", JsonPrimitive("rt2-$allocationHexA")),
            "malformed route token hash" to base.replacing("route_token_hash", JsonPrimitive(allocationHexA.uppercase())),
            "malformed runtime fingerprint" to base.replacing("runtime_key_fingerprint", JsonPrimitive(allocationHexA.dropLast(1))),
            "malformed client fingerprint" to base.replacing("client_key_fingerprint", JsonPrimitive(allocationHexB.uppercase())),
            "malformed challenge" to base.replacing("challenge", JsonPrimitive(allocationHexA.dropLast(1))),
            "malformed binding" to base.replacing("transport_binding", JsonPrimitive(allocationHexB.uppercase())),
            "whitespace current nonce" to base.replacing("current_relay_nonce", JsonPrimitive("current nonce")),
            "oversized next nonce" to base.replacing("next_relay_nonce", JsonPrimitive("n".repeat(513))),
            "noninteger generation" to base.replacing("current_ticket_generation", JsonPrimitive(1.5)),
        )
        listOf(
            "current_ticket_generation",
            "next_ticket_generation",
            "current_relay_expires_at",
            "next_relay_expires_at",
            "challenge_expires_at",
        ).forEach { field ->
            invalidSamples += "nonpositive $field" to base.replacing(field, JsonPrimitive(0))
        }

        invalidSamples.forEach { (label, sample) ->
            val error = assertThrows(label, Exception::class.java) {
                permissiveJson.decodeFromString<RelayAllocationChallengePayload>(sample.toString())
            }
            assertTrue(label, error.message.orEmpty().isNotEmpty())
        }
    }

    @Test
    fun relayAllocationChallengePayloadRenewAllowsEqualOrDifferentRelayIds() {
        val permissiveJson = Json { ignoreUnknownKeys = true }
        val base = Json.parseToJsonElement(Json.encodeToString(relayAllocationChallengePayload())).jsonObject
        val renew = base.replacing("operation", JsonPrimitive("renew"))

        permissiveJson.decodeFromString<RelayAllocationChallengePayload>(renew.toString())
        permissiveJson.decodeFromString<RelayAllocationChallengePayload>(
            renew.replacing("next_relay_id", JsonPrimitive("rt2-$allocationHexA")).toString(),
        )
    }

    @Test
    fun relayAllocationAuthorizationPayloadRoundTripsExactWireShape() {
        val payload = RelayAllocationAuthorizationPayload(
            proofScheme = RELAY_ALLOCATION_PROOF_SCHEME,
            authorizationId = "authorization-1",
            challenge = allocationHexA,
            clientKeyFingerprint = allocationHexB,
            transportBinding = allocationHexA,
            clientSignature = "MEUCIQ==",
        )
        val encoded = Json.encodeToString(payload)
        val objectValue = Json.parseToJsonElement(encoded).jsonObject

        assertEquals(payload, Json.decodeFromString<RelayAllocationAuthorizationPayload>(encoded))
        assertEquals(
            setOf(
                "proof_scheme",
                "authorization_id",
                "challenge",
                "client_key_fingerprint",
                "transport_binding",
                "client_signature",
            ),
            objectValue.keys,
        )
        assertFalse("request_id" in objectValue)
    }

    @Test
    fun relayAllocationAuthorizationPayloadRejectsMalformedAndSecretBearingSamples() {
        val permissiveJson = Json { ignoreUnknownKeys = true }
        val valid = RelayAllocationAuthorizationPayload(
            proofScheme = RELAY_ALLOCATION_PROOF_SCHEME,
            authorizationId = "authorization-1",
            challenge = allocationHexA,
            clientKeyFingerprint = allocationHexB,
            transportBinding = allocationHexA,
            clientSignature = "MEUCIQ==",
        )
        val base = Json.parseToJsonElement(Json.encodeToString(valid)).jsonObject
        val invalidSamples = listOf(
            "missing field" to base.removing("client_signature"),
            "unknown field" to base.replacing("unknown", JsonPrimitive("metadata")),
            "route token secret" to base.replacing("route_token", JsonPrimitive("secret")),
            "relay secret" to base.replacing("relay_secret", JsonPrimitive("secret")),
            "wrong scheme" to base.replacing("proof_scheme", JsonPrimitive("runtime-p256-v1")),
            "blank authorization id" to base.replacing("authorization_id", JsonPrimitive("\t")),
            "oversized authorization id" to base.replacing("authorization_id", JsonPrimitive("a".repeat(513))),
            "malformed challenge" to base.replacing("challenge", JsonPrimitive(allocationHexA.dropLast(1))),
            "malformed client fingerprint" to base.replacing("client_key_fingerprint", JsonPrimitive(allocationHexB.uppercase())),
            "malformed binding" to base.replacing("transport_binding", JsonPrimitive(allocationHexA.uppercase())),
            "blank signature" to base.replacing("client_signature", JsonPrimitive("")),
            "noncanonical signature" to base.replacing("client_signature", JsonPrimitive("TQ=")),
            "oversized signature" to base.replacing("client_signature", JsonPrimitive("A".repeat(516))),
        )

        invalidSamples.forEach { (label, sample) ->
            val error = assertThrows(label, Exception::class.java) {
                permissiveJson.decodeFromString<RelayAllocationAuthorizationPayload>(sample.toString())
            }
            assertTrue(label, error.message.orEmpty().isNotEmpty())
        }
    }

    @Test
    fun routeRefreshRelayResultSupportsOptionalPositiveTicketGeneration() {
        val relayJson = """
            {
              "runtime_device_id": "runtime-1",
              "runtime_key_fingerprint": "runtime-fingerprint",
              "relay_host": "relay.example.test",
              "relay_port": 443,
              "relay_id": "relay-1",
              "relay_secret": "secret-1",
              "relay_expires_at": 4102444800000,
              "relay_nonce": "nonce-1",
              "relay_scope": "remote"
            }
        """.trimIndent()
        val withoutGeneration = Json.decodeFromString<RouteRefreshPayload>(relayJson)
        val withGeneration = Json.decodeFromString<RouteRefreshPayload>(
            relayJson.dropLast(1) + ",\"ticket_generation\":1}",
        )

        assertNull(withoutGeneration.ticketGeneration)
        assertEquals(1L, withGeneration.ticketGeneration)
        assertThrows(Exception::class.java) {
            Json.decodeFromString<RouteRefreshPayload>(relayJson.dropLast(1) + ",\"ticket_generation\":0}")
        }
        assertThrows(Exception::class.java) {
            Json.decodeFromString<RouteRefreshPayload>(
                """
                {
                  "runtime_device_id": "runtime-1",
                  "runtime_key_fingerprint": "runtime-fingerprint",
                  "ticket_generation": 1,
                  "p2p_class": "p2p_rendezvous",
                  "p2p_record_id": "p2p-record-1",
                  "p2p_encrypted_body": "opaque-candidate-1",
                  "p2p_expires_at": 4102444800000,
                  "p2p_anti_replay_nonce": "p2p-nonce-1",
                  "p2p_protocol_version": 1
                }
                """.trimIndent(),
            )
        }
    }

    private val allocationHexA = "0123456789abcdef".repeat(4)
    private val allocationHexB = "fedcba9876543210".repeat(4)

    private fun relayAllocationChallengePayload() = RelayAllocationChallengePayload(
        proofScheme = RELAY_ALLOCATION_PROOF_SCHEME,
        protocolVersion = RELAY_ALLOCATION_PROTOCOL_VERSION,
        operation = "claim",
        authorizationId = "authorization-1",
        currentRelayId = "rt2-$allocationHexA",
        nextRelayId = "rt2-$allocationHexB",
        routeTokenHash = allocationHexB,
        runtimeKeyFingerprint = allocationHexA,
        clientKeyFingerprint = allocationHexB,
        currentTicketGeneration = 1,
        nextTicketGeneration = 2,
        currentRelayExpiresAtEpochMillis = 1,
        currentRelayNonce = "current-nonce",
        nextRelayExpiresAtEpochMillis = Long.MAX_VALUE,
        nextRelayNonce = "next-nonce",
        challenge = allocationHexA,
        challengeExpiresAtEpochMillis = 1,
        transportBinding = allocationHexB,
    )

    private fun JsonObject.replacing(field: String, value: JsonPrimitive): JsonObject =
        JsonObject(toMutableMap().apply { put(field, value) })

    private fun JsonObject.removing(field: String): JsonObject =
        JsonObject(toMutableMap().apply { remove(field) })

    private val nonCanonicalSourceAnchorIds = listOf(
        " source_anchor_0123456789abcdef",
        "source_anchor_0123456789ABCDEF",
        "source_anchor_not_a_handle",
        "source_anchor_0123456789abcde",
        "source_anchor_0123456789abcdef0",
        "",
    )
    private val nonCanonicalContentFingerprints = listOf(
        " 0011223344556677",
        "0011223344556677 ",
        "001122334455667G",
        "AABBCCDDEEFF0011",
        "001122334455667",
        "00112233445566770",
        "",
    )

    @Test
    fun encodesAndDecodesLengthPrefixedFrame() {
        val codec = ProtocolCodec()
        val envelope = ProtocolEnvelope(type = MessageType.ModelsList, payload = JsonObject(emptyMap()))

        val decoded = codec.readFrame(ByteArrayInputStream(codec.encode(envelope)))

        assertEquals(MessageType.ModelsList, decoded.type)
        assertEquals(envelope.requestId, decoded.requestId)
    }

    @Test
    fun encodesAndReadsFrameBodySeparatelyFromLengthPrefix() {
        val codec = ProtocolCodec()
        val envelope = ProtocolEnvelope(type = MessageType.RuntimeHealth, payload = JsonObject(emptyMap()))
        val body = codec.encodeBody(envelope)

        val framedBody = codec.readFrameBody(ByteArrayInputStream(codec.encodeFrameBody(body)))

        assertEquals(envelope, codec.decode(framedBody))
    }

    @Test
    fun decodeRejectsUnknownTopLevelEnvelopeFields() {
        val codec = ProtocolCodec()
        val json = """
            {
              "version": 1,
              "type": "runtime.health",
              "request_id": "android-unknown-top-level-envelope-field",
              "timestamp": "2026-07-07T00:00:00Z",
              "payload": {},
              "backend_url": "http://127.0.0.1:11434",
              "route_token": "client-supplied-route-token"
            }
        """.trimIndent()

        val error = assertThrows(IllegalArgumentException::class.java) {
            codec.decode(json.encodeToByteArray())
        }

        assertEquals("Unknown protocol envelope field: backend_url", error.message)
    }

    @Test
    fun errorPayloadAcceptsKnownProtocolCodes() {
        val knownCodes = listOf(
            "unknown_message_type",
            "unexpected_message_direction",
            "invalid_payload",
            "not_connected",
            "pairing_required",
            "authentication_required",
            "authentication_failed",
            "backend_unavailable",
            "bad_backend_response",
            "no_models",
            "model_not_found",
            "model_not_installed",
            "generation_not_found",
            "generation_cancelled",
            "route_refresh_unavailable",
            "unsupported_operation",
            "unsupported_attachment",
            "unreadable_attachment",
            "chat_session_not_found",
            "chat_session_must_be_archived_before_delete",
            "chat_session_must_be_restored_before_send",
            "chat_store_unavailable",
            "chat_context_window_exceeded",
            "document_index_unavailable",
            "source_anchor_not_found",
            "citation_not_found",
            "trusted_source_review_not_found",
            "trusted_source_review_expired",
            "trusted_source_review_stale",
            "trusted_source_not_found",
            "memory_store_unavailable",
            "memory_summary_draft_unavailable",
            "memory_summary_draft_stale",
            "memory_summary_draft_generation_failed",
            "transport_error",
            "internal_error",
        )

        knownCodes.forEach { code ->
            val decoded = Json.decodeFromString<ErrorPayload>(
                """{"code":"$code","message":"Runtime error","retryable":false}""",
            )

            assertEquals(code, decoded.code)
        }
    }

    @Test
    fun errorPayloadDecodesNonRetryableChatContextWindowExceeded() {
        val decoded = Json.decodeFromString<ErrorPayload>(
            """{"code":"chat_context_window_exceeded","message":"Chat context window exceeded","retryable":false}""",
        )

        assertEquals("chat_context_window_exceeded", decoded.code)
        assertFalse(decoded.retryable)
    }

    @Test
    fun errorPayloadRejectsUnknownCodes() {
        val invalidCodes = listOf(
            "backend_failed",
            "runtime_history_unavailable",
            "route_refresh_unavailable ",
            "",
        )

        invalidCodes.forEach { code ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<ErrorPayload>(
                    """{"code":"$code","message":"Runtime error","retryable":false}""",
                )
            }

            assertTrue(
                "expected code in ${error.message}",
                error.message.orEmpty().contains("code"),
            )
        }
    }

    @Test
    fun decodeRejectsMalformedRequiredEnvelopeFields() {
        val codec = ProtocolCodec()
        val validEnvelope = linkedMapOf(
            "version" to "1",
            "type" to "\"runtime.health\"",
            "request_id" to "\"android-required-envelope-field\"",
            "timestamp" to "\"2026-07-07T00:00:00Z\"",
            "payload" to "{}",
        )
        val missingCases = listOf(
            "version",
            "type",
            "request_id",
            "timestamp",
            "payload",
        )

        missingCases.forEach { missingField ->
            val json = validEnvelope
                .filterKeys { it != missingField }
                .entries
                .joinToString(prefix = "{", postfix = "}") { (key, value) -> "\"$key\":$value" }

            val error = assertThrows(IllegalArgumentException::class.java) {
                codec.decode(json.encodeToByteArray())
            }

            assertEquals("Missing protocol envelope field: $missingField", error.message)
        }

        val mistypedCases = listOf(
            """{"version":"1","type":"runtime.health","request_id":"bad-version","timestamp":"2026-07-07T00:00:00Z","payload":{}}""",
            """{"version":1,"type":7,"request_id":"bad-type","timestamp":"2026-07-07T00:00:00Z","payload":{}}""",
            """{"version":1,"type":"runtime.health","request_id":7,"timestamp":"2026-07-07T00:00:00Z","payload":{}}""",
            """{"version":1,"type":"runtime.health","request_id":"bad-timestamp","timestamp":123,"payload":{}}""",
            """{"version":1,"type":"runtime.health","request_id":"malformed-timestamp","timestamp":"not-a-date","payload":{}}""",
            """{"version":1,"type":"runtime.health","request_id":"bad-payload","timestamp":"2026-07-07T00:00:00Z","payload":[]}""",
        )
        mistypedCases.forEach { json ->
            assertThrows(Exception::class.java) {
                codec.decode(json.encodeToByteArray())
            }
        }
    }

    @Test
    fun decodeRejectsUnsupportedVersionAndBlankRequestId() {
        val codec = ProtocolCodec()

        val unsupportedVersion = """
            {
              "version": 2,
              "type": "runtime.health",
              "request_id": "unsupported-version",
              "timestamp": "2026-07-07T00:00:00Z",
              "payload": {}
            }
        """.trimIndent()
        val versionError = assertThrows(IllegalArgumentException::class.java) {
            codec.decode(unsupportedVersion.encodeToByteArray())
        }
        assertEquals("Unsupported protocol envelope version: 2", versionError.message)

        listOf("", "   ").forEach { requestId ->
            val blankRequestId = """
                {
                  "version": 1,
                  "type": "runtime.health",
                  "request_id": "$requestId",
                  "timestamp": "2026-07-07T00:00:00Z",
                  "payload": {}
                }
            """.trimIndent()

            val requestIdError = assertThrows(IllegalArgumentException::class.java) {
                codec.decode(blankRequestId.encodeToByteArray())
            }
            assertEquals("Invalid protocol envelope field: request_id", requestIdError.message)
        }
    }

    @Test
    fun decodeAllowsMessageSpecificMetadataInsidePayloadObject() {
        val codec = ProtocolCodec()
        val json = """
            {
              "version": 1,
              "type": "runtime.health",
              "request_id": "android-payload-object-boundary",
              "timestamp": "2026-07-07T00:00:00Z",
              "payload": {
                "backend_url": "http://127.0.0.1:11434"
              }
            }
        """.trimIndent()

        val decoded = codec.decode(json.encodeToByteArray())

        assertEquals(MessageType.RuntimeHealth, decoded.type)
        assertEquals("http://127.0.0.1:11434", decoded.payload["backend_url"]?.jsonPrimitive?.content)
    }

    @Test
    fun helloPayloadUsesProtocolClientCapabilitiesFieldName() {
        val payload = HelloPayload(
            deviceId = "client-1",
            deviceName = "AetherLink Client",
            capabilities = listOf("chat", "attachments"),
        )

        val encoded = Json.encodeToString(payload)
        val json = Json.parseToJsonElement(encoded).jsonObject

        assertEquals("client-1", json["device_id"]?.jsonPrimitive?.content)
        assertEquals("AetherLink Client", json["device_name"]?.jsonPrimitive?.content)
        assertEquals(
            listOf("chat", "attachments"),
            json["client_capabilities"]?.jsonArray?.map { it.jsonPrimitive.content },
        )
        assertEquals(null, json["capabilities"])
        assertEquals(null, json["transport_binding"])
    }

    @Test
    fun authenticationPayloadsUseOptionalTransportBindingFieldWithoutChangingV1Json() {
        val transportBinding = "0123456789abcdef".repeat(4)
        val v1Hello = Json.parseToJsonElement(
            Json.encodeToString(
                HelloPayload(
                    deviceId = "client-1",
                    deviceName = "AetherLink Client",
                    capabilities = listOf("chat"),
                )
            )
        ).jsonObject
        assertEquals(setOf("device_id", "device_name", "client_capabilities"), v1Hello.keys)

        val challenge = AuthChallengePayload(
            deviceId = "client-1",
            nonce = "nonce-1",
            runtimeKeyFingerprint = "fingerprint-1",
            runtimeSignature = "signature-1",
            transportBinding = transportBinding,
        )
        val response = AuthResponsePayload(
            deviceId = "client-1",
            nonce = "nonce-1",
            signature = "signature-2",
            transportBinding = transportBinding,
        )
        val boundHelloJson = Json.parseToJsonElement(
            Json.encodeToString(
                HelloPayload(
                    deviceId = "client-1",
                    deviceName = "AetherLink Client",
                    capabilities = listOf("chat"),
                    transportBinding = transportBinding,
                )
            )
        ).jsonObject
        val challengeJson = Json.parseToJsonElement(Json.encodeToString(challenge)).jsonObject
        val responseJson = Json.parseToJsonElement(Json.encodeToString(response)).jsonObject

        assertEquals(transportBinding, boundHelloJson["transport_binding"]?.jsonPrimitive?.content)
        assertEquals(transportBinding, challengeJson["transport_binding"]?.jsonPrimitive?.content)
        assertEquals(transportBinding, responseJson["transport_binding"]?.jsonPrimitive?.content)
        assertEquals(challenge, Json.decodeFromString<AuthChallengePayload>(challengeJson.toString()))
        assertEquals(response, Json.decodeFromString<AuthResponsePayload>(responseJson.toString()))
    }

    @Test
    fun chatSendPayloadCanCarryRuntimeLocaleHint() {
        val payload = ChatSendPayload(
            sessionId = "session-1",
            model = "ollama:llama3.1:8b",
            messages = listOf(
                ChatMessagePayload(
                    role = "user",
                    content = "Explain runtime titles.",
                ),
            ),
            locale = "fr",
            trustedSourceGrantIds = emptyList(),
        )

        val json = Json.parseToJsonElement(Json.encodeToString(payload)).jsonObject
        val decoded = Json.decodeFromString<ChatSendPayload>(Json.encodeToString(payload))

        assertEquals("session-1", json["session_id"]?.jsonPrimitive?.content)
        assertEquals("ollama:llama3.1:8b", json["model"]?.jsonPrimitive?.content)
        assertEquals("fr", json["locale"]?.jsonPrimitive?.content)
        assertEquals("fr", decoded.locale)
        assertFalse(json.containsKey("trusted_source_grant_ids"))
    }

    @Test
    fun chatSendPayloadCarriesUniqueCanonicalTrustedSourceGrantIds() {
        val grantIds = listOf(
            "trusted_source_00112233445566778899aabbccddeeff",
            "trusted_source_ffeeddccbbaa99887766554433221100",
        )
        val payload = ChatSendPayload(
            sessionId = "session-1",
            model = "ollama:llama3.1:8b",
            messages = listOf(ChatMessagePayload(role = "user", content = "Compare sources")),
            trustedSourceGrantIds = grantIds,
        )

        val encoded = Json.encodeToString(payload)
        val json = Json.parseToJsonElement(encoded).jsonObject

        assertEquals(grantIds, json["trusted_source_grant_ids"]?.jsonArray?.map { it.jsonPrimitive.content })
        assertEquals(grantIds, Json.decodeFromString<ChatSendPayload>(encoded).trustedSourceGrantIds)
    }

    @Test
    fun chatSendPayloadRejectsMalformedDuplicateEmptyAndExcessTrustedSourceGrantIds() {
        val canonical = "trusted_source_00112233445566778899aabbccddeeff"
        val invalidGrantLists = listOf(
            "null",
            "[]",
            "[\"$canonical\",\"$canonical\"]",
            "[\"trusted_source_00112233445566778899AABBCCDDEEFF\"]",
            "[\"trusted_source_0011\"]",
            (0..8).joinToString(prefix = "[", postfix = "]") { index ->
                "\"trusted_source_${index.toString(16).padStart(32, '0')}\""
            },
        )

        invalidGrantLists.forEach { grants ->
            assertThrows(Exception::class.java) {
                Json.decodeFromString<ChatSendPayload>(
                    """{"session_id":"session-1","model":"ollama:llama3.1:8b","messages":[{"role":"user","content":"Hello"}],"trusted_source_grant_ids":$grants}"""
                )
            }
        }
    }

    @Test
    fun chatSendRequestRejectsInvalidBounds() {
        val invalidRequests = listOf(
            """{"session_id":"","model":"ollama:llama3.1:8b","messages":[{"role":"user","content":"Hello"}]}""" to "session_id",
            """{"session_id":"   ","model":"ollama:llama3.1:8b","messages":[{"role":"user","content":"Hello"}]}""" to "session_id",
            """{"session_id":"session-1","model":"","messages":[{"role":"user","content":"Hello"}]}""" to "model",
            """{"session_id":"session-1","model":"   ","messages":[{"role":"user","content":"Hello"}]}""" to "model",
            """{"session_id":"session-1","model":"ollama:llama3.1:8b","messages":[]}""" to "messages",
            """{"session_id":"session-1","model":"ollama:llama3.1:8b","messages":[{"role":"tool","content":"Hello"}]}""" to "role",
            """{"session_id":"session-1","model":"ollama:llama3.1:8b","messages":[{"role":"user","content":"Hello","attachments":[{"type":"audio","mime_type":"audio/wav"}]}]}""" to "type",
            """{"session_id":"session-1","model":"ollama:llama3.1:8b","messages":[{"role":"user","content":"Hello","attachments":[{"type":"document","mime_type":""}]}]}""" to "mime_type",
        )

        invalidRequests.forEach { (json, expectedField) ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<ChatSendPayload>(json)
            }

            assertTrue(
                "expected $expectedField in ${error.message}",
                error.message.orEmpty().contains(expectedField),
            )
        }
    }

    @Test
    fun modelInfoPayloadCanCarryContextWindowMetadata() {
        val payload = ModelsResultPayload(
            models = listOf(
                ModelInfoPayload(
                    id = "llama3.1:8b",
                    name = "Llama 3.1 8B",
                    provider = "ollama",
                    modelKind = "chat",
                    capabilities = listOf("chat"),
                    qualifiedId = "ollama:llama3.1:8b",
                    installed = true,
                    source = "local",
                    contextWindowTokens = 32768,
                ),
            ),
        )

        val json = Json.parseToJsonElement(Json.encodeToString(payload)).jsonObject
        val decoded = Json.decodeFromString<ModelsResultPayload>(Json.encodeToString(payload))

        val model = json["models"]?.jsonArray?.first()?.jsonObject
        assertEquals("32768", model?.get("context_window_tokens")?.jsonPrimitive?.content)
        assertEquals(32768, decoded.models.first().contextWindowTokens)
    }

    @Test
    fun modelInfoPayloadPreservesProviderAndEmbeddingMetadata() {
        val payload = ModelsResultPayload(
            models = listOf(
                ModelInfoPayload(
                    id = "nomic-embed-text",
                    name = "Nomic Embed Text",
                    backend = "ollama",
                    provider = "ollama",
                    modelKind = "embedding",
                    kind = "embedding",
                    capabilities = listOf("embedding", "retrieval"),
                    providerModelId = "nomic-embed-text",
                    qualifiedId = "ollama:nomic-embed-text",
                    installed = true,
                    running = false,
                    source = "local",
                    sizeBytes = 274_000_000,
                    contextWindowTokens = 8192,
                    modifiedAt = "2026-07-02T12:34:56Z",
                    remoteModel = "nomic-embed-text",
                ),
            ),
        )

        val json = Json.parseToJsonElement(Json.encodeToString(payload)).jsonObject
        val decoded = Json.decodeFromString<ModelsResultPayload>(Json.encodeToString(payload))

        val model = json["models"]?.jsonArray?.first()?.jsonObject
        assertEquals("ollama", model?.get("backend")?.jsonPrimitive?.content)
        assertEquals("ollama", model?.get("provider")?.jsonPrimitive?.content)
        assertEquals("embedding", model?.get("model_kind")?.jsonPrimitive?.content)
        assertEquals("embedding", model?.get("kind")?.jsonPrimitive?.content)
        assertEquals(
            listOf("embedding", "retrieval"),
            model?.get("capabilities")?.jsonArray?.map { it.jsonPrimitive.content },
        )
        assertEquals("nomic-embed-text", model?.get("provider_model_id")?.jsonPrimitive?.content)
        assertEquals("ollama:nomic-embed-text", model?.get("qualified_id")?.jsonPrimitive?.content)
        assertEquals("274000000", model?.get("size_bytes")?.jsonPrimitive?.content)
        assertEquals("8192", model?.get("context_window_tokens")?.jsonPrimitive?.content)
        assertEquals("2026-07-02T12:34:56Z", model?.get("modified_at")?.jsonPrimitive?.content)
        assertEquals("nomic-embed-text", model?.get("remote_model")?.jsonPrimitive?.content)
        assertEquals("ollama", decoded.models.first().backend)
        assertEquals("ollama", decoded.models.first().provider)
        assertEquals("embedding", decoded.models.first().modelKind)
        assertEquals("embedding", decoded.models.first().kind)
        assertEquals(listOf("embedding", "retrieval"), decoded.models.first().capabilities)
        assertEquals("nomic-embed-text", decoded.models.first().providerModelId)
        assertEquals("ollama:nomic-embed-text", decoded.models.first().qualifiedId)
        assertEquals(274_000_000L, decoded.models.first().sizeBytes)
        assertEquals(8192, decoded.models.first().contextWindowTokens)
        assertEquals("2026-07-02T12:34:56Z", decoded.models.first().modifiedAt)
        assertEquals("nomic-embed-text", decoded.models.first().remoteModel)
    }

    @Test
    fun modelInfoPayloadRejectsInvalidScalarMetadata() {
        val invalidPayloads = listOf(
            """{"models":[{"id":"","name":"Empty ID"}]}""" to "id",
            """{"models":[{"id":"missing-name"}]}""" to "name",
            """{"models":[{"id":"empty-name","name":""}]}""" to "name",
            """{"models":[{"id":"bad-backend","name":"Bad Backend","backend":"openai"}]}""" to "backend",
            """{"models":[{"id":"bad-provider","name":"Bad Provider","provider":"openai"}]}""" to "provider",
            """{"models":[{"id":"bad-kind","name":"Bad Kind","model_kind":"vision"}]}""" to "model_kind",
            """{"models":[{"id":"duplicate-capability","name":"Duplicate Capability","capabilities":["chat","chat"]}]}""" to "capabilities",
            """{"models":[{"id":"bad-source","name":"Bad Source","source":"remote"}]}""" to "source",
        )

        invalidPayloads.forEach { (json, expectedField) ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<ModelsResultPayload>(json)
            }

            assertTrue(
                "expected $expectedField in ${error.message}",
                error.message.orEmpty().contains(expectedField),
            )
        }
    }

    @Test
    fun modelInfoPayloadRejectsInvalidModifiedAtMetadata() {
        val invalidPayloads = listOf(
            """{"models":[{"id":"not-a-date","name":"Not A Date","modified_at":"not-a-date"}]}""",
            """{"models":[{"id":"date-only","name":"Date Only","modified_at":"2026-07-09"}]}""",
            """{"models":[{"id":"missing-zone","name":"Missing Zone","modified_at":"2026-07-09T12:34:56"}]}""",
        )

        invalidPayloads.forEach { json ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<ModelsResultPayload>(json)
            }

            assertTrue(
                "expected modified_at in ${error.message}",
                error.message.orEmpty().contains("modified_at"),
            )
        }
    }

    @Test
    fun modelInfoPayloadRejectsInvalidNumericMetadata() {
        val invalidPayloads = listOf(
            """{"models":[{"id":"negative-size","name":"Negative Size","size_bytes":-1}]}""" to "size_bytes",
            """{"models":[{"id":"zero-context","name":"Zero Context","context_window_tokens":0}]}""" to "context_window_tokens",
            """{"models":[{"id":"negative-context","name":"Negative Context","context_window_tokens":-1}]}""" to "context_window_tokens",
        )

        invalidPayloads.forEach { (json, expectedField) ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<ModelsResultPayload>(json)
            }

            assertTrue(
                "expected $expectedField in ${error.message}",
                error.message.orEmpty().contains(expectedField),
            )
        }
    }

    @Test
    fun modelInfoPayloadDefaultsMissingCapabilitiesToEmptyList() {
        val decoded = Json.decodeFromString<ModelsResultPayload>(
            """
            {
              "models": [
                {
                  "id": "legacy-embed",
                  "name": "Legacy Embed",
                  "provider": "ollama",
                  "model_kind": "embedding",
                  "provider_model_id": "legacy-embed",
                  "qualified_id": "ollama:legacy-embed"
                }
              ]
            }
            """.trimIndent(),
        )

        assertEquals(emptyList<String>(), decoded.models.first().capabilities)
        assertEquals("embedding", decoded.models.first().modelKind)
        assertEquals("legacy-embed", decoded.models.first().providerModelId)
        assertEquals("ollama:legacy-embed", decoded.models.first().qualifiedId)
    }

    @Test
    fun routeRefreshPayloadRejectsInvalidScalarRouteMaterial() {
        val oversizedBody = "b".repeat(2049)
        val invalidPayloads = listOf(
            """{"runtime_device_id":" runtime"}""" to "opaque route value",
            """{"runtime_key_fingerprint":"${"f".repeat(513)}"}""" to "opaque route value",
            """{"relay_port":0}""" to "relay_port",
            """{"relay_port":65536}""" to "relay_port",
            """{"relay_id":"relay id"}""" to "opaque route value",
            """{"relay_secret":""}""" to "opaque route value",
            """{"relay_expires_at":0}""" to "expiry",
            """{"relay_nonce":"nonce\nroute"}""" to "opaque route value",
            """{"relay_scope":" remote "}""" to "relay_scope",
            """{"relay_scope":"local_diagnostic"}""" to "relay_scope",
            """{"p2p_class":"relay"}""" to "p2p_class",
            """{"p2p_record_id":"p2p record"}""" to "opaque route value",
            """{"p2p_encrypted_body":"$oversizedBody"}""" to "opaque route body",
            """{"p2p_expires_at":0}""" to "expiry",
            """{"p2p_anti_replay_nonce":"p2p nonce"}""" to "opaque route value",
            """{"p2p_protocol_version":2}""" to "p2p_protocol_version",
        )

        invalidPayloads.forEach { (json, expectedField) ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<RouteRefreshPayload>(json)
            }

            assertTrue(
                "expected $expectedField in ${error.message}",
                error.message.orEmpty().contains(expectedField),
            )
        }
    }

    @Test
    fun routeRefreshPayloadRequiresCompleteRouteMaterialFamilies() {
        val empty = Json.decodeFromString<RouteRefreshPayload>("{}")
        assertNull(empty.runtimeDeviceId)
        assertNull(empty.relayHost)
        assertNull(empty.p2pRouteClass)

        val relay = Json.decodeFromString<RouteRefreshPayload>(
            """
            {
              "runtime_device_id": "runtime-1",
              "runtime_key_fingerprint": "runtime-fingerprint",
              "relay_host": "relay.example.test",
              "relay_port": 443,
              "relay_id": "relay-1",
              "relay_secret": "secret-1",
              "relay_expires_at": 4102444800000,
              "relay_nonce": "nonce-1",
              "relay_scope": "remote"
            }
            """.trimIndent(),
        )
        assertEquals("runtime-1", relay.runtimeDeviceId)
        assertEquals("relay.example.test", relay.relayHost)
        assertEquals("remote", relay.relayScope)

        val p2p = Json.decodeFromString<RouteRefreshPayload>(
            """
            {
              "runtime_device_id": "runtime-1",
              "runtime_key_fingerprint": "runtime-fingerprint",
              "p2p_class": "p2p_rendezvous",
              "p2p_record_id": "p2p-record-1",
              "p2p_encrypted_body": "opaque-candidate-1",
              "p2p_expires_at": 4102444800000,
              "p2p_anti_replay_nonce": "p2p-nonce-1",
              "p2p_protocol_version": 1
            }
            """.trimIndent(),
        )
        assertEquals("runtime-1", p2p.runtimeDeviceId)
        assertEquals("p2p_rendezvous", p2p.p2pRouteClass)
        assertEquals(1, p2p.p2pProtocolVersion)

        val invalidPayloads = listOf(
            """{"runtime_device_id":"runtime-1","runtime_key_fingerprint":"runtime-fingerprint"}""" to "complete relay or P2P route material",
            """{"runtime_device_id":"runtime-1","relay_host":"relay.example.test","relay_port":443,"relay_id":"relay-1","relay_secret":"secret-1","relay_expires_at":4102444800000,"relay_nonce":"nonce-1"}""" to "runtime_key_fingerprint",
            """{"runtime_device_id":"runtime-1","runtime_key_fingerprint":"runtime-fingerprint","relay_host":"relay.example.test"}""" to "relay route material",
            """{"runtime_device_id":"runtime-1","runtime_key_fingerprint":"runtime-fingerprint","relay_scope":"remote"}""" to "relay route material",
            """{"runtime_device_id":"runtime-1","runtime_key_fingerprint":"runtime-fingerprint","p2p_class":"p2p_rendezvous"}""" to "P2P route material",
            """{"runtime_device_id":"runtime-1","runtime_key_fingerprint":"runtime-fingerprint","p2p_record_id":"p2p-record-1","p2p_encrypted_body":"opaque-candidate-1","p2p_expires_at":4102444800000,"p2p_anti_replay_nonce":"p2p-nonce-1","p2p_protocol_version":1}""" to "P2P route material",
        )

        invalidPayloads.forEach { (json, expectedField) ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<RouteRefreshPayload>(json)
            }

            assertTrue(
                "expected $expectedField in ${error.message}",
                error.message.orEmpty().contains(expectedField),
            )
        }
    }

    @Test
    fun runtimeHealthBackendStatusAcceptsSchemaMinimalPayload() {
        val decoded = Json.decodeFromString<RuntimeHealthPayload>(
            """
            {
              "status": "ok",
              "ollama": {
                "available": true
              },
              "lm_studio": {
                "available": false,
                "code": "backend_unavailable",
                "retryable": true
              }
            }
            """.trimIndent(),
        )

        assertEquals("ok", decoded.status)
        assertEquals(true, decoded.ollama?.available)
        assertNull(decoded.ollama?.message)
        assertNull(decoded.ollama?.code)
        assertNull(decoded.ollama?.retryable)
        assertEquals(false, decoded.lmStudio?.available)
        assertNull(decoded.lmStudio?.message)
        assertEquals("backend_unavailable", decoded.lmStudio?.code)
        assertEquals(true, decoded.lmStudio?.retryable)
    }

    @Test
    fun runtimeHealthPayloadRejectsInvalidStatus() {
        val invalidPayloads = listOf(
            """{"status":"connected"}""",
            """{"status":"failed"}""",
            """{"status":""}""",
        )

        invalidPayloads.forEach { json ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<RuntimeHealthPayload>(json)
            }

            assertTrue(
                "expected status in ${error.message}",
                error.message.orEmpty().contains("status"),
            )
        }
    }

    @Test
    fun runtimeHealthPayloadCanCarryModelResidencySnapshot() {
        val payload = RuntimeHealthPayload(
            status = "ok",
            modelResidency = RuntimeModelResidencyPayload(
                supported = true,
                activeProvider = "ollama",
                activeModelId = "llama3.1:8b",
                inFlightGenerations = 1,
                idleUnloadDelaySeconds = 600,
                lastUnloadFailure = RuntimeModelResidencyUnloadFailurePayload(
                    provider = "ollama",
                    modelId = "llama3.1:8b",
                    reason = "manual",
                ),
            ),
        )

        val json = Json.parseToJsonElement(Json.encodeToString(payload)).jsonObject
        val decoded = Json.decodeFromString<RuntimeHealthPayload>(Json.encodeToString(payload))

        val residency = json["model_residency"]?.jsonObject
        assertEquals("true", residency?.get("supported")?.jsonPrimitive?.content)
        assertEquals("ollama", residency?.get("active_provider")?.jsonPrimitive?.content)
        assertEquals("llama3.1:8b", residency?.get("active_model_id")?.jsonPrimitive?.content)
        assertEquals("1", residency?.get("in_flight_generations")?.jsonPrimitive?.content)
        assertEquals("600", residency?.get("idle_unload_delay_seconds")?.jsonPrimitive?.content)
        val failure = residency?.get("last_unload_failure")?.jsonObject
        assertEquals("ollama", failure?.get("provider")?.jsonPrimitive?.content)
        assertEquals("llama3.1:8b", failure?.get("model_id")?.jsonPrimitive?.content)
        assertEquals("manual", failure?.get("reason")?.jsonPrimitive?.content)
        assertEquals("ollama", decoded.modelResidency?.activeProvider)
        assertEquals("llama3.1:8b", decoded.modelResidency?.activeModelId)
        assertEquals(1, decoded.modelResidency?.inFlightGenerations)
        assertEquals(600, decoded.modelResidency?.idleUnloadDelaySeconds)
        assertEquals("ollama", decoded.modelResidency?.lastUnloadFailure?.provider)
        assertEquals("llama3.1:8b", decoded.modelResidency?.lastUnloadFailure?.modelId)
        assertEquals("manual", decoded.modelResidency?.lastUnloadFailure?.reason)
    }

    @Test
    fun runtimeHealthPayloadRejectsInvalidModelResidencyBounds() {
        val invalidPayloads = listOf(
            """
            {
              "status": "ok",
              "model_residency": {
                "supported": true,
                "in_flight_generations": -1
              }
            }
            """.trimIndent() to "in_flight_generations",
            """
            {
              "status": "ok",
              "model_residency": {
                "supported": true,
                "in_flight_generations": 0,
                "idle_unload_delay_seconds": -1
              }
            }
            """.trimIndent() to "idle_unload_delay_seconds",
        )

        invalidPayloads.forEach { (json, expectedField) ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<RuntimeHealthPayload>(json)
            }

            assertTrue(
                "expected $expectedField in ${error.message}",
                error.message.orEmpty().contains(expectedField),
            )
        }
    }

    @Test
    fun chatHistorySessionPayloadsUseProtocolFieldNames() {
        val request = ChatSessionsListRequestPayload(
            limit = 50,
            includeArchived = true,
            query = "relay route",
            embeddingModelId = "ollama:nomic-embed-text",
        )
        val result = ChatSessionsListResultPayload(
            sessions = listOf(
                ChatSessionSummaryPayload(
                    sessionId = "session-1",
                    title = "Runtime history",
                    model = "ollama:llama3.1:8b",
                    lastActivityAt = "2026-06-23T09:02:05Z",
                    messageCount = 2,
                    status = "archived",
                    archivedAt = "2026-06-23T09:05:05Z",
                    search = ChatSessionSearchPayload(
                        rank = 1,
                        snippet = "Runtime history matched relay route.",
                        matchedFields = listOf("title", "transcript"),
                    ),
                ),
            ),
        )

        val requestJson = Json.parseToJsonElement(Json.encodeToString(request)).jsonObject
        val resultJson = Json.parseToJsonElement(Json.encodeToString(result)).jsonObject
        val decoded = Json.decodeFromString<ChatSessionsListResultPayload>(Json.encodeToString(result))

        assertEquals("50", requestJson["limit"]?.jsonPrimitive?.content)
        assertEquals("true", requestJson["include_archived"]?.jsonPrimitive?.content)
        assertEquals("relay route", requestJson["query"]?.jsonPrimitive?.content)
        assertEquals("ollama:nomic-embed-text", requestJson["embedding_model_id"]?.jsonPrimitive?.content)
        val session = resultJson["sessions"]?.jsonArray?.first()?.jsonObject
        assertEquals("session-1", session?.get("session_id")?.jsonPrimitive?.content)
        assertEquals("Runtime history", session?.get("title")?.jsonPrimitive?.content)
        assertEquals("ollama:llama3.1:8b", session?.get("model")?.jsonPrimitive?.content)
        assertEquals("2026-06-23T09:02:05Z", session?.get("last_activity_at")?.jsonPrimitive?.content)
        assertEquals("2", session?.get("message_count")?.jsonPrimitive?.content)
        assertEquals("archived", session?.get("status")?.jsonPrimitive?.content)
        assertEquals("2026-06-23T09:05:05Z", session?.get("archived_at")?.jsonPrimitive?.content)
        val search = session?.get("search")?.jsonObject
        assertEquals("1", search?.get("rank")?.jsonPrimitive?.content)
        assertEquals("Runtime history matched relay route.", search?.get("snippet")?.jsonPrimitive?.content)
        assertEquals(
            listOf("title", "transcript"),
            search?.get("matched_fields")?.jsonArray?.map { it.jsonPrimitive.content },
        )
        assertEquals("session-1", decoded.sessions.first().sessionId)
        assertEquals("archived", decoded.sessions.first().status)
        assertEquals("2026-06-23T09:05:05Z", decoded.sessions.first().archivedAt)
        assertEquals(1, decoded.sessions.first().search?.rank)
        assertEquals("Runtime history matched relay route.", decoded.sessions.first().search?.snippet)
        assertEquals(listOf("title", "transcript"), decoded.sessions.first().search?.matchedFields)
    }

    @Test
    fun chatSessionsListRequestRejectsInvalidBounds() {
        val invalidRequests = listOf(
            """{"limit":-1}""" to "limit",
            """{"limit":201}""" to "limit",
            """{"query":""}""" to "query",
            """{"embedding_model_id":""}""" to "embedding_model_id",
        )

        invalidRequests.forEach { (json, expectedField) ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<ChatSessionsListRequestPayload>(json)
            }

            assertTrue(
                "expected $expectedField in ${error.message}",
                error.message.orEmpty().contains(expectedField),
            )
        }
    }

    @Test
    fun chatSessionsListResponseRejectsInvalidBounds() {
        val invalidResponses = listOf(
            """
            {
              "sessions": [
                {
                  "session_id": "",
                  "title": "Runtime history",
                  "model": "ollama:llama3.1:8b",
                  "last_activity_at": "2026-06-23T09:02:05Z",
                  "message_count": 2
                }
              ]
            }
            """.trimIndent() to "session_id",
            """
            {
              "sessions": [
                {
                  "session_id": "session-1",
                  "title": "Runtime history",
                  "model": "ollama:llama3.1:8b",
                  "last_activity_at": "2026-06-23T09:02:05Z",
                  "message_count": -1
                }
              ]
            }
            """.trimIndent() to "message_count",
            """
            {
              "sessions": [
                {
                  "session_id": "session-1",
                  "title": "Runtime history",
                  "model": "ollama:llama3.1:8b",
                  "last_activity_at": "2026-06-23T09:02:05Z",
                  "message_count": 2,
                  "status": "deleted"
                }
              ]
            }
            """.trimIndent() to "status",
            """
            {
              "sessions": [
                {
                  "session_id": "session-1",
                  "title": "Runtime history",
                  "model": "ollama:llama3.1:8b",
                  "last_activity_at": "2026-06-23T09:02:05Z",
                  "message_count": 2,
                  "last_event": "started"
                }
              ]
            }
            """.trimIndent() to "last_event",
            """
            {
              "sessions": [
                {
                  "session_id": "session-1",
                  "title": "Runtime history",
                  "model": "ollama:llama3.1:8b",
                  "last_activity_at": "2026-06-23T09:02:05Z",
                  "message_count": 2,
                  "search": {
                    "rank": 0,
                    "snippet": "Runtime history matched relay route.",
                    "matched_fields": ["title"]
                  }
                }
              ]
            }
            """.trimIndent() to "rank",
            """
            {
              "sessions": [
                {
                  "session_id": "session-1",
                  "title": "Runtime history",
                  "model": "ollama:llama3.1:8b",
                  "last_activity_at": "2026-06-23T09:02:05Z",
                  "message_count": 2,
                  "search": {
                    "rank": 1,
                    "snippet": "Runtime history matched relay route.",
                    "matched_fields": []
                  }
                }
              ]
            }
            """.trimIndent() to "matched_fields",
            """
            {
              "sessions": [
                {
                  "session_id": "session-1",
                  "title": "Runtime history",
                  "model": "ollama:llama3.1:8b",
                  "last_activity_at": "2026-06-23T09:02:05Z",
                  "message_count": 2,
                  "search": {
                    "rank": 1,
                    "snippet": "Runtime history matched relay route.",
                    "matched_fields": [""]
                  }
                }
              ]
            }
            """.trimIndent() to "matched_fields",
            """
            {
              "sessions": [
                {
                  "session_id": "session-1",
                  "title": "Runtime history",
                  "model": "ollama:llama3.1:8b",
                  "last_activity_at": "2026-06-23T09:02:05Z",
                  "message_count": 2,
                  "search": {
                    "rank": 1,
                    "snippet": "Runtime history matched relay route.",
                    "matched_fields": ["title", "title"]
                  }
                }
              ]
            }
            """.trimIndent() to "matched_fields",
        )

        invalidResponses.forEach { (json, expectedField) ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<ChatSessionsListResultPayload>(json)
            }

            assertTrue(
                "expected $expectedField in ${error.message}",
                error.message.orEmpty().contains(expectedField),
            )
        }
    }

    @Test
    fun indexDocumentsListPayloadUsesProtocolFieldNames() {
        val request = IndexDocumentsListRequestPayload(limit = 25)
        val document = RuntimeDocumentIndexDocumentPayload(
            id = "doc-1",
            displayName = "runtime-notes.md",
            mimeType = "text/markdown",
            contentFingerprint = "0011223344556677",
            extractedCharacterCount = 2048,
            chunkCount = 3,
            quality = "chunked",
        )
        val result = IndexDocumentsListResultPayload(
            documents = listOf(document),
            summary = IndexDocumentsSummaryPayload(
                documentCount = 1,
                chunkCount = 3,
                extractedCharacterCount = 2048,
                qualityCounts = IndexDocumentsQualityCountsPayload(
                    noUsableText = 0,
                    singleChunk = 0,
                    chunked = 1,
                ),
            ),
        )

        val requestJson = Json.parseToJsonElement(Json.encodeToString(request)).jsonObject
        val resultJson = Json.parseToJsonElement(Json.encodeToString(result)).jsonObject
        val decoded = Json.decodeFromString<IndexDocumentsListResultPayload>(Json.encodeToString(result))

        assertEquals(MessageType.IndexDocumentsList, "index.documents.list")
        assertEquals("25", requestJson["limit"]?.jsonPrimitive?.content)
        val listedDocument = resultJson["documents"]?.jsonArray?.first()?.jsonObject
        assertEquals("doc-1", listedDocument?.get("id")?.jsonPrimitive?.content)
        assertEquals("runtime-notes.md", listedDocument?.get("display_name")?.jsonPrimitive?.content)
        assertEquals("text/markdown", listedDocument?.get("mime_type")?.jsonPrimitive?.content)
        assertEquals("0011223344556677", listedDocument?.get("content_fingerprint")?.jsonPrimitive?.content)
        assertEquals("2048", listedDocument?.get("extracted_character_count")?.jsonPrimitive?.content)
        assertEquals("3", listedDocument?.get("chunk_count")?.jsonPrimitive?.content)
        assertEquals("chunked", listedDocument?.get("quality")?.jsonPrimitive?.content)
        val summary = resultJson["summary"]?.jsonObject
        assertEquals("1", summary?.get("document_count")?.jsonPrimitive?.content)
        assertEquals("3", summary?.get("chunk_count")?.jsonPrimitive?.content)
        assertEquals("2048", summary?.get("extracted_character_count")?.jsonPrimitive?.content)
        val qualityCounts = summary?.get("quality_counts")?.jsonObject
        assertEquals("0", qualityCounts?.get("no_usable_text")?.jsonPrimitive?.content)
        assertEquals("0", qualityCounts?.get("single_chunk")?.jsonPrimitive?.content)
        assertEquals("1", qualityCounts?.get("chunked")?.jsonPrimitive?.content)
        assertEquals("runtime-notes.md", decoded.documents.single().displayName)
        assertEquals("text/markdown", decoded.documents.single().mimeType)
        assertEquals("0011223344556677", decoded.documents.single().contentFingerprint)
        assertEquals(2048, decoded.documents.single().extractedCharacterCount)
        assertEquals(3, decoded.documents.single().chunkCount)
        assertEquals("chunked", decoded.documents.single().quality)
        assertEquals(1, decoded.summary.documentCount)
        assertEquals(1, decoded.summary.qualityCounts.chunked)
    }

    @Test
    fun indexDocumentsListRequestRejectsInvalidBounds() {
        val invalidRequestSamples = listOf(
            "limit" to """{"limit": -1}""",
            "limit" to """{"limit": 101}""",
        )

        invalidRequestSamples.forEach { (fieldName, sample) ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<IndexDocumentsListRequestPayload>(sample)
            }

            assertTrue(
                "Expected invalid $fieldName decode error to name the field, got ${error.message}",
                error.message.orEmpty().contains(fieldName),
            )
        }
    }

    @Test
    fun indexDocumentsListResponseRejectsInvalidDocumentMetadataBounds() {
        val overlongMimeType = "text/" + "a".repeat(124)
        val overlongDocuments = (0..100).joinToString(",") { index ->
            indexDocumentJson(
                id = jsonString("doc-$index"),
                contentFingerprint = jsonString(index.toString(16).padStart(16, '0')),
            )
        }
        val invalidResponseSamples = listOf(
            "documents" to indexDocumentsListResultJson(documentsJson = overlongDocuments),
            "id" to indexDocumentsListResultJson(
                documentsJson = indexDocumentJson(id = jsonString("")),
            ),
            "id" to indexDocumentsListResultJson(
                documentsJson = indexDocumentJson(id = jsonString("d".repeat(129))),
            ),
            "display_name" to indexDocumentsListResultJson(
                documentsJson = indexDocumentJson(displayName = jsonString("")),
            ),
            "display_name" to indexDocumentsListResultJson(
                documentsJson = indexDocumentJson(displayName = jsonString("d".repeat(257))),
            ),
            "mime_type" to indexDocumentsListResultJson(
                documentsJson = indexDocumentJson(mimeType = jsonString(overlongMimeType)),
            ),
            "mime_type" to indexDocumentsListResultJson(
                documentsJson = indexDocumentJson(mimeType = jsonString("Text/markdown")),
            ),
            "mime_type" to indexDocumentsListResultJson(
                documentsJson = indexDocumentJson(mimeType = jsonString("textplain")),
            ),
            "mime_type" to indexDocumentsListResultJson(
                documentsJson = indexDocumentJson(mimeType = jsonString("text/plain; charset=utf-8")),
            ),
            "mime_type" to indexDocumentsListResultJson(
                documentsJson = indexDocumentJson(mimeType = jsonString("https://example.invalid/text/plain")),
            ),
            "extracted_character_count" to indexDocumentsListResultJson(
                documentsJson = indexDocumentJson(extractedCharacterCount = "-1"),
            ),
            "chunk_count" to indexDocumentsListResultJson(
                documentsJson = indexDocumentJson(chunkCount = "-1"),
            ),
            "quality" to indexDocumentsListResultJson(
                documentsJson = indexDocumentJson(quality = jsonString("trusted_source")),
            ),
            "quality" to indexDocumentsListResultJson(
                documentsJson = indexDocumentJson(chunkCount = "0", quality = jsonString("chunked")),
            ),
            "quality" to indexDocumentsListResultJson(
                documentsJson = indexDocumentJson(chunkCount = "1", quality = jsonString("no_usable_text")),
            ),
            "quality" to indexDocumentsListResultJson(
                documentsJson = indexDocumentJson(chunkCount = "2", quality = jsonString("single_chunk")),
            ),
        )

        invalidResponseSamples.forEach { (fieldName, sample) ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<IndexDocumentsListResultPayload>(sample)
            }

            assertTrue(
                "Expected invalid $fieldName decode error to name the field, got ${error.message}",
                error.message.orEmpty().contains(fieldName),
            )
        }
    }

    @Test
    fun indexDocumentsListResponseRejectsInvalidSummaryBounds() {
        val invalidResponseSamples = listOf(
            "document_count" to indexDocumentsListResultJson(
                summaryJson = indexDocumentsSummaryJson(documentCount = "-1"),
            ),
            "chunk_count" to indexDocumentsListResultJson(
                summaryJson = indexDocumentsSummaryJson(chunkCount = "-1"),
            ),
            "extracted_character_count" to indexDocumentsListResultJson(
                summaryJson = indexDocumentsSummaryJson(extractedCharacterCount = "-1"),
            ),
            "no_usable_text" to indexDocumentsListResultJson(
                summaryJson = indexDocumentsSummaryJson(
                    qualityCountsJson = """{"single_chunk": 0, "chunked": 1}""",
                ),
            ),
            "single_chunk" to indexDocumentsListResultJson(
                summaryJson = indexDocumentsSummaryJson(
                    qualityCountsJson = """{"no_usable_text": 0, "chunked": 1}""",
                ),
            ),
            "chunked" to indexDocumentsListResultJson(
                summaryJson = indexDocumentsSummaryJson(
                    qualityCountsJson = """{"no_usable_text": 0, "single_chunk": 0}""",
                ),
            ),
            "no_usable_text" to indexDocumentsListResultJson(
                summaryJson = indexDocumentsSummaryJson(
                    qualityCountsJson = """{"no_usable_text": -1, "single_chunk": 0, "chunked": 1}""",
                ),
            ),
            "single_chunk" to indexDocumentsListResultJson(
                summaryJson = indexDocumentsSummaryJson(
                    qualityCountsJson = """{"no_usable_text": 0, "single_chunk": -1, "chunked": 1}""",
                ),
            ),
            "chunked" to indexDocumentsListResultJson(
                summaryJson = indexDocumentsSummaryJson(
                    qualityCountsJson = """{"no_usable_text": 0, "single_chunk": 0, "chunked": -1}""",
                ),
            ),
        )

        invalidResponseSamples.forEach { (fieldName, sample) ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<IndexDocumentsListResultPayload>(sample)
            }

            assertTrue(
                "Expected invalid $fieldName decode error to name the field, got ${error.message}",
                error.message.orEmpty().contains(fieldName),
            )
        }
    }

    @Test
    fun retrievalAndSourceAnchorDocumentMetadataRejectsInvalidBounds() {
        val invalidDocument = indexDocumentJson(
            mimeType = jsonString("Text/markdown"),
        )
        val invalidResponseSamples = listOf(
            "mime_type" to {
                Json.decodeFromString<RetrievalQueryResultPayload>(
                    retrievalQueryResultJsonWithDocument(invalidDocument),
                )
            },
            "mime_type" to {
                Json.decodeFromString<SourceAnchorResolveResultPayload>(
                    sourceAnchorResolveResultJsonWithDocument(invalidDocument),
                )
            },
        )

        invalidResponseSamples.forEach { (fieldName, decode) ->
            val error = assertThrows(Exception::class.java) {
                decode()
            }

            assertTrue(
                "Expected invalid $fieldName decode error to name the field, got ${error.message}",
                error.message.orEmpty().contains(fieldName),
            )
        }
    }

    @Test
    fun retrievalQueryResponseRejectsTooManyResults() {
        val overlongResults = (0..100).joinToString(",") { index ->
            retrievalQueryResultItemJson(index)
        }

        val error = assertThrows(Exception::class.java) {
            Json.decodeFromString<RetrievalQueryResultPayload>(
                retrievalQueryResultJsonWithResults(overlongResults),
            )
        }

        assertTrue(
            "Expected oversized retrieval.query response decode error to name results, got ${error.message}",
            error.message.orEmpty().contains("results"),
        )
    }

    @Test
    fun retrievalQueryPayloadUsesProtocolFieldNames() {
        val request = RetrievalQueryRequestPayload(
            query = "relay route",
            limit = 5,
            maxSnippetCharacters = 120,
        )
        val result = RetrievalQueryResultPayload(
            results = listOf(
                RetrievalQueryResultItemPayload(
                    document = RuntimeDocumentIndexDocumentPayload(
                        id = "doc-1",
                        displayName = "runtime-notes.md",
                        mimeType = "text/markdown",
                        contentFingerprint = "0011223344556677",
                        extractedCharacterCount = 2048,
                        chunkCount = 3,
                        quality = "chunked",
                    ),
                    chunkIndex = 1,
                    startCharacterOffset = 120,
                    endCharacterOffset = 240,
                    rank = 2,
                    matchedTerms = listOf("relay", "route"),
                    snippet = "Runtime document snippet matched relay route.",
                    sourceAnchorId = "source_anchor_0123456789abcdef",
                ),
            ),
        )

        val requestJson = Json.parseToJsonElement(Json.encodeToString(request)).jsonObject
        val resultJson = Json.parseToJsonElement(Json.encodeToString(result)).jsonObject
        val decoded = Json.decodeFromString<RetrievalQueryResultPayload>(Json.encodeToString(result))
        val sourceAnchorWireShape = Regex("^source_anchor_[0-9a-f]{16}$")

        assertEquals(MessageType.RetrievalQuery, "retrieval.query")
        assertEquals("relay route", requestJson["query"]?.jsonPrimitive?.content)
        assertEquals("5", requestJson["limit"]?.jsonPrimitive?.content)
        assertEquals("120", requestJson["max_snippet_characters"]?.jsonPrimitive?.content)
        assertFalse(requestJson.containsKey("embedding_model_id"))
        assertFalse(requestJson.containsKey("source_anchor_id"))
        val item = resultJson["results"]?.jsonArray?.first()?.jsonObject
        val document = item?.get("document")?.jsonObject
        assertEquals("doc-1", document?.get("id")?.jsonPrimitive?.content)
        assertEquals("runtime-notes.md", document?.get("display_name")?.jsonPrimitive?.content)
        assertEquals("text/markdown", document?.get("mime_type")?.jsonPrimitive?.content)
        assertEquals("0011223344556677", document?.get("content_fingerprint")?.jsonPrimitive?.content)
        assertEquals("2048", document?.get("extracted_character_count")?.jsonPrimitive?.content)
        assertEquals("3", document?.get("chunk_count")?.jsonPrimitive?.content)
        assertEquals("chunked", document?.get("quality")?.jsonPrimitive?.content)
        assertEquals("1", item?.get("chunk_index")?.jsonPrimitive?.content)
        assertEquals("120", item?.get("start_character_offset")?.jsonPrimitive?.content)
        assertEquals("240", item?.get("end_character_offset")?.jsonPrimitive?.content)
        assertEquals("2", item?.get("rank")?.jsonPrimitive?.content)
        assertEquals("source_anchor_0123456789abcdef", item?.get("source_anchor_id")?.jsonPrimitive?.content)
        assertEquals(
            listOf("relay", "route"),
            item?.get("matched_terms")?.jsonArray?.map { it.jsonPrimitive.content },
        )
        assertEquals("Runtime document snippet matched relay route.", item?.get("snippet")?.jsonPrimitive?.content)
        val decodedItem = decoded.results.single()
        assertEquals("runtime-notes.md", decodedItem.document.displayName)
        assertEquals(1, decodedItem.chunkIndex)
        assertEquals(120, decodedItem.startCharacterOffset)
        assertEquals(240, decodedItem.endCharacterOffset)
        assertEquals(2, decodedItem.rank)
        assertEquals("source_anchor_0123456789abcdef", decodedItem.sourceAnchorId)
        assertTrue(sourceAnchorWireShape.matches(decodedItem.sourceAnchorId))
        assertEquals(listOf("relay", "route"), decodedItem.matchedTerms)
        assertEquals("Runtime document snippet matched relay route.", decodedItem.snippet)
    }

    @Test
    fun retrievalQueryRequestSerializesEmbeddingModelHintAndRejectsBlankHint() {
        val semanticRequest = RetrievalQueryRequestPayload(
            query = "semantic relay route",
            limit = 7,
            maxSnippetCharacters = 240,
            embeddingModelId = "embedding-model-1",
        )

        val semanticJson = Json.parseToJsonElement(Json.encodeToString(semanticRequest)).jsonObject
        val decoded = Json.decodeFromString<RetrievalQueryRequestPayload>(Json.encodeToString(semanticRequest))

        assertEquals("embedding-model-1", semanticJson["embedding_model_id"]?.jsonPrimitive?.content)
        assertEquals("embedding-model-1", decoded.embeddingModelId)

        listOf("", "   ").forEach { invalidHint ->
            val error = assertThrows(IllegalArgumentException::class.java) {
                RetrievalQueryRequestPayload(
                    query = "relay route",
                    embeddingModelId = invalidHint,
                )
            }
            assertTrue(error.message.orEmpty().contains("embedding_model_id"))
        }
        val decodeError = assertThrows(Exception::class.java) {
            Json.decodeFromString<RetrievalQueryRequestPayload>(
                """{"query":"relay route","embedding_model_id":"   "}""",
            )
        }
        assertTrue(decodeError.message.orEmpty().contains("embedding_model_id"))
    }

    @Test
    fun retrievalQueryMatchKindDefaultsLexicalAndControlsMatchedTermsBounds() {
        val missingKind = Json.decodeFromString<RetrievalQueryResultPayload>(
            retrievalQueryResultJsonWithSourceAnchor(
                sourceAnchorId = "source_anchor_0123456789abcdef",
            ),
        ).results.single()
        val semantic = Json.decodeFromString<RetrievalQueryResultPayload>(
            retrievalQueryResultJsonWithSourceAnchor(
                sourceAnchorId = "source_anchor_0123456789abcdef",
                matchKind = "semantic",
                matchedTermsJson = "",
            ),
        ).results.single()

        assertEquals(RetrievalMatchKind.Lexical, missingKind.matchKind)
        assertEquals(RetrievalMatchKind.Semantic, semantic.matchKind)
        assertTrue(semantic.matchedTerms.isEmpty())
        val semanticJson = Json.parseToJsonElement(Json.encodeToString(semantic)).jsonObject
        assertEquals("semantic", semanticJson["match_kind"]?.jsonPrimitive?.content)

        val invalidSamples = listOf(
            retrievalQueryResultJsonWithSourceAnchor(
                sourceAnchorId = "source_anchor_0123456789abcdef",
                matchKind = "lexical",
                matchedTermsJson = "",
            ),
            retrievalQueryResultJsonWithSourceAnchor(
                sourceAnchorId = "source_anchor_0123456789abcdef",
                matchKind = "semantic",
                matchedTermsJson = (1..17).joinToString(", ") { index -> "\"term$index\"" },
            ),
            retrievalQueryResultJsonWithSourceAnchor(
                sourceAnchorId = "source_anchor_0123456789abcdef",
                matchKind = "semantic",
                matchedTermsJson = "\"\"",
            ),
            retrievalQueryResultJsonWithSourceAnchor(
                sourceAnchorId = "source_anchor_0123456789abcdef",
                matchKind = "lexical",
                matchedTermsJson = "\"   \"",
            ),
            retrievalQueryResultJsonWithSourceAnchor(
                sourceAnchorId = "source_anchor_0123456789abcdef",
                matchKind = "semantic",
                matchedTermsJson = "\"   \"",
            ),
        )
        invalidSamples.forEach { sample ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<RetrievalQueryResultPayload>(sample)
            }
            assertTrue(error.message.orEmpty().contains("matched_terms"))
        }

        val unknownKindError = assertThrows(Exception::class.java) {
            Json.decodeFromString<RetrievalQueryResultPayload>(
                retrievalQueryResultJsonWithSourceAnchor(
                    sourceAnchorId = "source_anchor_0123456789abcdef",
                    matchKind = "hybrid",
                ),
            )
        }
        assertTrue(unknownKindError.message.orEmpty().contains("match_kind"))
    }

    @Test
    fun retrievalQueryRequestRejectsInvalidBounds() {
        val invalidRequestSamples = listOf(
            "query" to """{"query": ""}""",
            "query" to """{"query": "   "}""",
            "query" to """{"query": "${"q".repeat(1025)}"}""",
            "limit" to """{"query": "relay", "limit": -1}""",
            "limit" to """{"query": "relay", "limit": 101}""",
            "max_snippet_characters" to """{"query": "relay", "max_snippet_characters": -1}""",
            "max_snippet_characters" to """{"query": "relay", "max_snippet_characters": 501}""",
        )

        invalidRequestSamples.forEach { (fieldName, sample) ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<RetrievalQueryRequestPayload>(sample)
            }

            assertTrue(
                "Expected invalid $fieldName decode error to name the field, got ${error.message}",
                error.message.orEmpty().contains(fieldName),
            )
        }
    }

    @Test
    fun sourceAnchorResolvePayloadUsesProtocolFieldNames() {
        val request = SourceAnchorResolveRequestPayload(
            sourceAnchorId = "source_anchor_0123456789abcdef",
        )
        val result = SourceAnchorResolveResultPayload(
            sourceAnchorId = "source_anchor_0123456789abcdef",
            document = RuntimeDocumentIndexDocumentPayload(
                id = "doc-1",
                displayName = "runtime-notes.md",
                mimeType = "text/markdown",
                contentFingerprint = "0011223344556677",
                extractedCharacterCount = 2048,
                chunkCount = 3,
                quality = "chunked",
            ),
            chunkSummary = SourceAnchorChunkSummaryPayload(
                chunkIndex = 1,
                startCharacterOffset = 120,
                endCharacterOffset = 240,
                characterCount = 120,
            ),
        )

        val requestJson = Json.parseToJsonElement(Json.encodeToString(request)).jsonObject
        val resultJson = Json.parseToJsonElement(Json.encodeToString(result)).jsonObject
        val decoded = Json.decodeFromString<SourceAnchorResolveResultPayload>(Json.encodeToString(result))
        val sourceAnchorWireShape = Regex("^source_anchor_[0-9a-f]{16}$")

        assertEquals(MessageType.SourceAnchorResolve, "source_anchor.resolve")
        assertEquals("source_anchor_0123456789abcdef", requestJson["source_anchor_id"]?.jsonPrimitive?.content)
        assertFalse(requestJson.containsKey("document"))
        assertFalse(requestJson.containsKey("chunk_summary"))
        assertEquals("source_anchor_0123456789abcdef", resultJson["source_anchor_id"]?.jsonPrimitive?.content)
        val document = resultJson["document"]?.jsonObject
        assertEquals("doc-1", document?.get("id")?.jsonPrimitive?.content)
        assertEquals("runtime-notes.md", document?.get("display_name")?.jsonPrimitive?.content)
        assertEquals("text/markdown", document?.get("mime_type")?.jsonPrimitive?.content)
        assertEquals("0011223344556677", document?.get("content_fingerprint")?.jsonPrimitive?.content)
        assertEquals("2048", document?.get("extracted_character_count")?.jsonPrimitive?.content)
        assertEquals("3", document?.get("chunk_count")?.jsonPrimitive?.content)
        assertEquals("chunked", document?.get("quality")?.jsonPrimitive?.content)
        val chunkSummary = resultJson["chunk_summary"]?.jsonObject
        assertEquals("1", chunkSummary?.get("chunk_index")?.jsonPrimitive?.content)
        assertEquals("120", chunkSummary?.get("start_character_offset")?.jsonPrimitive?.content)
        assertEquals("240", chunkSummary?.get("end_character_offset")?.jsonPrimitive?.content)
        assertEquals("120", chunkSummary?.get("character_count")?.jsonPrimitive?.content)
        assertFalse(resultJson.containsKey("chunk_text"))
        assertFalse(resultJson.containsKey("snippet"))
        assertFalse(resultJson.containsKey("source_path"))
        assertEquals("source_anchor_0123456789abcdef", decoded.sourceAnchorId)
        assertTrue(sourceAnchorWireShape.matches(decoded.sourceAnchorId))
        assertEquals("runtime-notes.md", decoded.document.displayName)
        assertEquals(1, decoded.chunkSummary.chunkIndex)
        assertEquals(120, decoded.chunkSummary.characterCount)
    }

    @Test
    fun indexDocumentsListRejectsNonCanonicalContentFingerprints() {
        nonCanonicalContentFingerprints.forEach { contentFingerprint ->
            assertContentFingerprintDecodeRejected(contentFingerprint) {
                Json.decodeFromString<IndexDocumentsListResultPayload>(
                    indexDocumentsListResultJsonWithContentFingerprint(contentFingerprint),
                )
            }
        }
    }

    @Test
    fun retrievalQueryResultRejectsNonCanonicalDocumentContentFingerprints() {
        nonCanonicalContentFingerprints.forEach { contentFingerprint ->
            assertContentFingerprintDecodeRejected(contentFingerprint) {
                Json.decodeFromString<RetrievalQueryResultPayload>(
                    retrievalQueryResultJsonWithSourceAnchor(
                        sourceAnchorId = "source_anchor_0123456789abcdef",
                        contentFingerprint = contentFingerprint,
                    ),
                )
            }
        }
    }

    @Test
    fun sourceAnchorResolveResultRejectsNonCanonicalDocumentContentFingerprints() {
        nonCanonicalContentFingerprints.forEach { contentFingerprint ->
            assertContentFingerprintDecodeRejected(contentFingerprint) {
                Json.decodeFromString<SourceAnchorResolveResultPayload>(
                    sourceAnchorResolveResultJsonWithSourceAnchor(
                        sourceAnchorId = "source_anchor_0123456789abcdef",
                        contentFingerprint = contentFingerprint,
                    ),
                )
            }
        }
    }

    @Test
    fun sourceAnchorResolveRequestRejectsMissingRequiredField() {
        val error = assertThrows(Exception::class.java) {
            Json.decodeFromString<SourceAnchorResolveRequestPayload>("{}")
        }

        assertTrue(
            "Expected missing source_anchor_id decode error to name the field, got ${error.message}",
            error.message.orEmpty().contains("source_anchor_id"),
        )
    }

    @Test
    fun sourceAnchorResolveRequestRejectsNonCanonicalSourceAnchorIds() {
        nonCanonicalSourceAnchorIds.forEach { sourceAnchorId ->
            assertSourceAnchorDecodeRejected(sourceAnchorId) {
                Json.decodeFromString<SourceAnchorResolveRequestPayload>(
                    """{"source_anchor_id": "$sourceAnchorId"}""",
                )
            }
        }
    }

    @Test
    fun sourceAnchorResolveResultRejectsMissingRequiredFields() {
        val canonicalResult = """
            {
              "source_anchor_id": "source_anchor_0123456789abcdef",
              "document": {
                "id": "doc-1",
                "display_name": "runtime-notes.md",
                "mime_type": "text/markdown",
                "content_fingerprint": "0011223344556677",
                "extracted_character_count": 2048,
                "chunk_count": 3,
                "quality": "chunked"
              },
              "chunk_summary": {
                "chunk_index": 1,
                "start_character_offset": 120,
                "end_character_offset": 240,
                "character_count": 120
              }
            }
        """.trimIndent()
        val missingRequiredFieldSamples = listOf(
            "source_anchor_id" to canonicalResult.replace(
                Regex("""\s+"source_anchor_id": "source_anchor_0123456789abcdef",\n"""),
                "",
            ),
            "document" to canonicalResult.replace(
                Regex(
                    """(?s),\n\s+"document": \{\n.*?\n\s+\}(?=,\n\s+"chunk_summary")""",
                ),
                "",
            ),
            "chunk_summary" to canonicalResult.replace(
                Regex("""(?s),\n\s+"chunk_summary": \{\n.*?\n\s+\}\n\s*(?=\})"""),
                "",
            ),
            "chunk_index" to canonicalResult.replace(
                Regex("""\s+"chunk_index": 1,\n"""),
                "",
            ),
            "start_character_offset" to canonicalResult.replace(
                Regex("""\s+"start_character_offset": 120,\n"""),
                "",
            ),
            "end_character_offset" to canonicalResult.replace(
                Regex("""\s+"end_character_offset": 240,\n"""),
                "",
            ),
            "character_count" to canonicalResult.replace(
                Regex("""\s+"end_character_offset": 240,\n\s+"character_count": 120\n"""),
                "\n                \"end_character_offset\": 240\n",
            ),
        )

        missingRequiredFieldSamples.forEach { (fieldName, sample) ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<SourceAnchorResolveResultPayload>(sample)
            }

            assertTrue(
                "Expected missing $fieldName decode error to name the field, got ${error.message}",
                error.message.orEmpty().contains(fieldName),
            )
        }
    }

    @Test
    fun sourceAnchorResolveResultRejectsInvalidChunkSummaryValues() {
        val invalidChunkSummarySamples = listOf(
            "chunk_summary.chunk_index" to sourceAnchorResolveResultJsonWithSourceAnchor(
                sourceAnchorId = "source_anchor_0123456789abcdef",
                chunkSummaryOverrides = mapOf("chunk_index" to -1),
            ),
            "chunk_summary.start_character_offset" to sourceAnchorResolveResultJsonWithSourceAnchor(
                sourceAnchorId = "source_anchor_0123456789abcdef",
                chunkSummaryOverrides = mapOf("start_character_offset" to -1),
            ),
            "chunk_summary.end_character_offset" to sourceAnchorResolveResultJsonWithSourceAnchor(
                sourceAnchorId = "source_anchor_0123456789abcdef",
                chunkSummaryOverrides = mapOf("end_character_offset" to -1),
            ),
            "chunk_summary.character_count" to sourceAnchorResolveResultJsonWithSourceAnchor(
                sourceAnchorId = "source_anchor_0123456789abcdef",
                chunkSummaryOverrides = mapOf("character_count" to -1),
            ),
            "chunk_summary.end_character_offset" to sourceAnchorResolveResultJsonWithSourceAnchor(
                sourceAnchorId = "source_anchor_0123456789abcdef",
                chunkSummaryOverrides = mapOf(
                    "start_character_offset" to 240,
                    "end_character_offset" to 120,
                    "character_count" to 0,
                ),
            ),
        )

        invalidChunkSummarySamples.forEach { (fieldName, sample) ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<SourceAnchorResolveResultPayload>(sample)
            }

            assertTrue(
                "Expected invalid $fieldName decode error to name the field, got ${error.message}",
                error.message.orEmpty().contains(fieldName),
            )
        }
    }

    @Test
    fun sourceAnchorResolveResultRejectsNonCanonicalSourceAnchorIds() {
        nonCanonicalSourceAnchorIds.forEach { sourceAnchorId ->
            assertSourceAnchorDecodeRejected(sourceAnchorId) {
                Json.decodeFromString<SourceAnchorResolveResultPayload>(
                    sourceAnchorResolveResultJsonWithSourceAnchor(sourceAnchorId),
                )
            }
        }
    }

    @Test
    fun retrievalQueryResultRejectsMissingSourceAnchorId() {
        val missingSourceAnchorResult = """
            {
              "results": [
                {
                  "document": {
                    "id": "doc-1",
                    "display_name": "runtime-notes.md",
                    "mime_type": "text/markdown",
                    "content_fingerprint": "0011223344556677",
                    "extracted_character_count": 2048,
                    "chunk_count": 3,
                    "quality": "chunked"
                  },
                  "chunk_index": 1,
                  "start_character_offset": 120,
                  "end_character_offset": 240,
                  "rank": 2,
                  "matched_terms": ["relay", "route"],
                  "snippet": "Runtime document snippet matched relay route."
                }
              ]
            }
        """.trimIndent()

        val error = assertThrows(Exception::class.java) {
            Json.decodeFromString<RetrievalQueryResultPayload>(missingSourceAnchorResult)
        }

        assertTrue(error.message.orEmpty().contains("source_anchor_id"))
    }

    @Test
    fun retrievalQueryResultRejectsNonCanonicalSourceAnchorIds() {
        nonCanonicalSourceAnchorIds.forEach { sourceAnchorId ->
            assertSourceAnchorDecodeRejected(sourceAnchorId) {
                Json.decodeFromString<RetrievalQueryResultPayload>(
                    retrievalQueryResultJsonWithSourceAnchor(sourceAnchorId),
                )
            }
        }
    }

    @Test
    fun retrievalQueryResultRejectsInvalidCoordinatesAndRank() {
        val invalidResultSamples = listOf(
            "chunk_index" to retrievalQueryResultJsonWithSourceAnchor(
                sourceAnchorId = "source_anchor_0123456789abcdef",
                chunkIndex = -1,
            ),
            "start_character_offset" to retrievalQueryResultJsonWithSourceAnchor(
                sourceAnchorId = "source_anchor_0123456789abcdef",
                startCharacterOffset = -1,
            ),
            "end_character_offset" to retrievalQueryResultJsonWithSourceAnchor(
                sourceAnchorId = "source_anchor_0123456789abcdef",
                endCharacterOffset = -1,
            ),
            "end_character_offset" to retrievalQueryResultJsonWithSourceAnchor(
                sourceAnchorId = "source_anchor_0123456789abcdef",
                startCharacterOffset = 240,
                endCharacterOffset = 120,
            ),
            "rank" to retrievalQueryResultJsonWithSourceAnchor(
                sourceAnchorId = "source_anchor_0123456789abcdef",
                rank = 0,
            ),
        )

        invalidResultSamples.forEach { (fieldName, sample) ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<RetrievalQueryResultPayload>(sample)
            }

            assertTrue(
                "Expected invalid $fieldName decode error to name the field, got ${error.message}",
                error.message.orEmpty().contains(fieldName),
            )
        }
    }

    @Test
    fun retrievalQueryResultRejectsInvalidLexicalMetadata() {
        val invalidResultSamples = listOf(
            "matched_terms" to retrievalQueryResultJsonWithSourceAnchor(
                sourceAnchorId = "source_anchor_0123456789abcdef",
                matchedTermsJson = "",
            ),
            "matched_terms" to retrievalQueryResultJsonWithSourceAnchor(
                sourceAnchorId = "source_anchor_0123456789abcdef",
                matchedTermsJson = (1..17).joinToString(", ") { index -> "\"term$index\"" },
            ),
            "matched_terms" to retrievalQueryResultJsonWithSourceAnchor(
                sourceAnchorId = "source_anchor_0123456789abcdef",
                matchedTermsJson = "\"relay\", \"\"",
            ),
            "matched_terms" to retrievalQueryResultJsonWithSourceAnchor(
                sourceAnchorId = "source_anchor_0123456789abcdef",
                matchedTermsJson = "\"relay\", \"${"t".repeat(65)}\"",
            ),
            "snippet" to retrievalQueryResultJsonWithSourceAnchor(
                sourceAnchorId = "source_anchor_0123456789abcdef",
                snippet = "",
            ),
            "snippet" to retrievalQueryResultJsonWithSourceAnchor(
                sourceAnchorId = "source_anchor_0123456789abcdef",
                snippet = "s".repeat(501),
            ),
        )

        invalidResultSamples.forEach { (fieldName, sample) ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<RetrievalQueryResultPayload>(sample)
            }

            assertTrue(
                "Expected invalid $fieldName decode error to name the field, got ${error.message}",
                error.message.orEmpty().contains(fieldName),
            )
        }
    }

    @Test
    fun retrievalQueryResultRejectsMissingMatchedTerms() {
        val missingMatchedTermsResult = """
            {
              "results": [
                {
                  "document": {
                    "id": "doc-1",
                    "display_name": "runtime-notes.md",
                    "mime_type": "text/markdown",
                    "content_fingerprint": "0011223344556677",
                    "extracted_character_count": 2048,
                    "chunk_count": 3,
                    "quality": "chunked"
                  },
                  "chunk_index": 1,
                  "start_character_offset": 120,
                  "end_character_offset": 240,
                  "rank": 2,
                  "snippet": "Runtime document snippet matched relay route.",
                  "source_anchor_id": "source_anchor_0123456789abcdef"
                }
              ]
            }
        """.trimIndent()

        val error = assertThrows(Exception::class.java) {
            Json.decodeFromString<RetrievalQueryResultPayload>(missingMatchedTermsResult)
        }

        assertTrue(error.message.orEmpty().contains("matched_terms"))
    }

    @Test
    fun citationResolvePayloadsRoundTripCanonicalClosedWireShape() {
        val request = CitationResolveRequestPayload(sourceAnchorId = canonicalSourceAnchorId)
        val result = CitationResolveResultPayload(
            citation = canonicalCitationPayload(),
            review = canonicalSourceReviewPayload(),
            trustedSource = canonicalTrustedSourcePayload(),
        )

        val requestJson = Json.parseToJsonElement(Json.encodeToString(request)).jsonObject
        val resultEncoded = Json.encodeToString(result)
        val resultJson = Json.parseToJsonElement(resultEncoded).jsonObject
        val decoded = Json.decodeFromString<CitationResolveResultPayload>(resultEncoded)

        assertEquals(setOf("source_anchor_id"), requestJson.keys)
        assertEquals(setOf("citation", "review", "trusted_source"), resultJson.keys)
        assertEquals(
            setOf("schema_version", "citation_id", "source_anchor_id", "document", "chunk_summary"),
            resultJson.getValue("citation").jsonObject.keys,
        )
        assertEquals(
            setOf("review_id", "confirmation_token", "disclosure_version", "usage_scope", "expires_at"),
            resultJson.getValue("review").jsonObject.keys,
        )
        assertEquals(result, decoded)
        assertEquals("citation.resolve", MessageType.CitationResolve)
        listOf("body", "snippet", "path", "query", "model", "vector", "revision", "approval_id").forEach {
            forbiddenField -> assertFalse(resultEncoded.contains("\"$forbiddenField\""))
        }
    }

    @Test
    fun trustedSourceOperationPayloadsRoundTripCanonicalWireShapes() {
        val approveRequest = TrustedSourceApproveRequestPayload(
            reviewId = canonicalReviewId,
            confirmationToken = canonicalConfirmationToken,
            disclosureVersion = "runtime-trusted-source-v1",
            usageScope = "chat_context",
        )
        val approveResult = TrustedSourceApproveResultPayload(canonicalTrustedSourcePayload())
        val dismissRequest = TrustedSourceDismissRequestPayload(canonicalReviewId)
        val dismissResult = TrustedSourceDismissResultPayload(canonicalReviewId, dismissed = true)
        val listRequest = TrustedSourceListRequestPayload(limit = 100)
        val listResult = TrustedSourceListResultPayload(listOf(canonicalTrustedSourcePayload()))
        val revokeRequest = TrustedSourceRevokeRequestPayload(canonicalGrantId)
        val revokeResult = TrustedSourceRevokeResultPayload(canonicalGrantId, revoked = true)

        assertEquals(approveRequest, Json.decodeFromString<TrustedSourceApproveRequestPayload>(Json.encodeToString(approveRequest)))
        assertEquals(approveResult, Json.decodeFromString<TrustedSourceApproveResultPayload>(Json.encodeToString(approveResult)))
        assertEquals(dismissRequest, Json.decodeFromString<TrustedSourceDismissRequestPayload>(Json.encodeToString(dismissRequest)))
        assertEquals(dismissResult, Json.decodeFromString<TrustedSourceDismissResultPayload>(Json.encodeToString(dismissResult)))
        assertEquals(listRequest, Json.decodeFromString<TrustedSourceListRequestPayload>(Json.encodeToString(listRequest)))
        assertEquals(listResult, Json.decodeFromString<TrustedSourceListResultPayload>(Json.encodeToString(listResult)))
        assertEquals(revokeRequest, Json.decodeFromString<TrustedSourceRevokeRequestPayload>(Json.encodeToString(revokeRequest)))
        assertEquals(revokeResult, Json.decodeFromString<TrustedSourceRevokeResultPayload>(Json.encodeToString(revokeResult)))
        assertEquals("trusted_source.approve", MessageType.TrustedSourceApprove)
        assertEquals("trusted_source.dismiss", MessageType.TrustedSourceDismiss)
        assertEquals("trusted_source.list", MessageType.TrustedSourceList)
        assertEquals("trusted_source.revoke", MessageType.TrustedSourceRevoke)
    }

    @Test
    fun citationAndTrustedSourcePayloadsRejectUnknownAndForbiddenFieldsEvenPermissively() {
        val permissiveJson = Json { ignoreUnknownKeys = true }
        val decodeSamples = listOf<() -> Unit>(
            {
                permissiveJson.decodeFromString<CitationResolveRequestPayload>(
                    """{"source_anchor_id":"$canonicalSourceAnchorId","query":"secret"}""",
                )
            },
            {
                val sample = Json.parseToJsonElement(Json.encodeToString(
                    CitationResolveResultPayload.serializer(),
                    CitationResolveResultPayload(canonicalCitationPayload(), canonicalSourceReviewPayload()),
                )).jsonObject.replacing("body", JsonPrimitive("secret")).toString()
                permissiveJson.decodeFromString<CitationResolveResultPayload>(sample)
            },
            {
                val sample = Json.parseToJsonElement(Json.encodeToString(canonicalCitationPayload()))
                    .jsonObject.replacing("revision", JsonPrimitive("secret")).toString()
                permissiveJson.decodeFromString<CitationPayload>(sample)
            },
            {
                val sample = Json.encodeToString(canonicalCitationPayload()).replace(
                    "\"quality\":\"chunked\"",
                    "\"quality\":\"chunked\",\"path\":\"secret\"",
                )
                permissiveJson.decodeFromString<CitationPayload>(sample)
            },
            {
                val sample = Json.encodeToString(canonicalCitationPayload()).replace(
                    "\"character_count\":120",
                    "\"character_count\":120,\"revision\":1",
                )
                permissiveJson.decodeFromString<CitationPayload>(sample)
            },
            {
                val sample = Json.parseToJsonElement(Json.encodeToString(canonicalSourceReviewPayload()))
                    .jsonObject.replacing("approval_id", JsonPrimitive("secret")).toString()
                permissiveJson.decodeFromString<SourceReviewPayload>(sample)
            },
            {
                val sample = Json.parseToJsonElement(Json.encodeToString(canonicalTrustedSourcePayload()))
                    .jsonObject.replacing("path", JsonPrimitive("secret")).toString()
                permissiveJson.decodeFromString<TrustedSourcePayload>(sample)
            },
            {
                val sample = Json.parseToJsonElement(Json.encodeToString(
                    TrustedSourceApproveRequestPayload.serializer(),
                    TrustedSourceApproveRequestPayload(
                        canonicalReviewId,
                        canonicalConfirmationToken,
                        "runtime-trusted-source-v1",
                        "chat_context",
                    ),
                )).jsonObject.replacing("model", JsonPrimitive("secret")).toString()
                permissiveJson.decodeFromString<TrustedSourceApproveRequestPayload>(sample)
            },
            {
                permissiveJson.decodeFromString<TrustedSourceDismissRequestPayload>(
                    """{"review_id":"$canonicalReviewId","snippet":"secret"}""",
                )
            },
            { permissiveJson.decodeFromString<TrustedSourceListRequestPayload>("""{"limit":1,"vector":[]}""") },
            {
                permissiveJson.decodeFromString<TrustedSourceRevokeRequestPayload>(
                    """{"grant_id":"$canonicalGrantId","body":"secret"}""",
                )
            },
        )

        decodeSamples.forEach { decode ->
            val error = assertThrows(Exception::class.java) { decode() }
            assertTrue(error.message.orEmpty().contains("unknown field"))
        }
    }

    @Test
    fun citationAndTrustedSourcePayloadsRejectMalformedBlankAndUnknownValues() {
        val citationJson = Json.encodeToString(canonicalCitationPayload())
        val reviewJson = Json.encodeToString(canonicalSourceReviewPayload())
        val trustedSourceJson = Json.encodeToString(canonicalTrustedSourcePayload())
        val decodeSamples = listOf<() -> Unit>(
            { Json.decodeFromString<CitationPayload>(citationJson.replace(canonicalCitationId, "citation_${"A".repeat(32)}")) },
            { Json.decodeFromString<CitationPayload>(citationJson.replace("\"schema_version\":1", "\"schema_version\":2")) },
            { Json.decodeFromString<SourceReviewPayload>(reviewJson.replace(canonicalReviewId, "source_review_${"0".repeat(31)}")) },
            {
                Json.decodeFromString<SourceReviewPayload>(
                    reviewJson.replace(canonicalConfirmationToken, "source_confirmation_${"0".repeat(63)}"),
                )
            },
            { Json.decodeFromString<SourceReviewPayload>(reviewJson.replace("runtime-trusted-source-v1", "runtime-trusted-source-v2")) },
            { Json.decodeFromString<SourceReviewPayload>(reviewJson.replace("chat_context", "retrieval")) },
            { Json.decodeFromString<SourceReviewPayload>(reviewJson.replace("2026-07-12T12:00:00Z", "   ")) },
            { Json.decodeFromString<TrustedSourcePayload>(trustedSourceJson.replace(canonicalGrantId, "trusted_source_${"g".repeat(32)}")) },
            { Json.decodeFromString<TrustedSourcePayload>(trustedSourceJson.replace("chat_context", "global")) },
            { Json.decodeFromString<TrustedSourcePayload>(trustedSourceJson.replace("2026-07-12T11:00:00Z", "not-an-instant")) },
        )

        decodeSamples.forEach { decode ->
            assertThrows(Exception::class.java) { decode() }
        }
        assertThrows(IllegalArgumentException::class.java) {
            CitationResolveResultPayload(
                citation = canonicalCitationPayload(),
                review = canonicalSourceReviewPayload(),
                trustedSource = canonicalTrustedSourcePayload().copy(
                    document = canonicalDocumentPayload().copy(displayName = "different-source.md"),
                ),
            )
        }
    }

    @Test
    fun trustedSourceListAndBooleanResultsRejectOutOfContractValues() {
        listOf(-1, 101).forEach { limit ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<TrustedSourceListRequestPayload>("""{"limit":$limit}""")
            }
            assertTrue(error.message.orEmpty().contains("limit"))
        }
        val sources = (0..100).joinToString(",") { Json.encodeToString(canonicalTrustedSourcePayload()) }
        assertThrows(Exception::class.java) {
            Json.decodeFromString<TrustedSourceListResultPayload>("""{"trusted_sources":[$sources]}""")
        }
        val canonicalSource = canonicalTrustedSourcePayload()
        assertThrows(IllegalArgumentException::class.java) {
            TrustedSourceListResultPayload(
                listOf(
                    canonicalSource,
                    canonicalSource.copy(sourceAnchorId = "source_anchor_${"1".repeat(16)}"),
                ),
            )
        }
        assertThrows(IllegalArgumentException::class.java) {
            TrustedSourceListResultPayload(
                listOf(
                    canonicalSource,
                    canonicalSource.copy(grantId = "trusted_source_${"1".repeat(32)}"),
                ),
            )
        }
        assertThrows(Exception::class.java) {
            Json.decodeFromString<TrustedSourceDismissResultPayload>(
                """{"review_id":"$canonicalReviewId","dismissed":false}""",
            )
        }
        assertThrows(Exception::class.java) {
            Json.decodeFromString<TrustedSourceRevokeResultPayload>(
                """{"grant_id":"$canonicalGrantId","revoked":false}""",
            )
        }
    }

    @Test
    fun chatHistoryMessagePayloadsUseProtocolFieldNames() {
        val request = ChatMessagesListRequestPayload(sessionId = "session-1", limit = 200)
        val result = ChatMessagesListResultPayload(
            sessionId = "session-1",
            messages = listOf(
                ChatStoredMessagePayload(
                    role = "assistant",
                    content = "Hello",
                    reasoning = "Short thought",
                    attachments = listOf(
                        ChatStoredAttachmentPayload(
                            type = "document",
                            mimeType = "text/plain",
                            name = "context.txt",
                            text = "Saved context",
                        ),
                    ),
                    createdAt = "2026-06-23T09:02:06Z",
                ),
            ),
        )

        val requestJson = Json.parseToJsonElement(Json.encodeToString(request)).jsonObject
        val resultJson = Json.parseToJsonElement(Json.encodeToString(result)).jsonObject
        val decoded = Json.decodeFromString<ChatMessagesListResultPayload>(Json.encodeToString(result))

        assertEquals("session-1", requestJson["session_id"]?.jsonPrimitive?.content)
        assertEquals("200", requestJson["limit"]?.jsonPrimitive?.content)
        assertEquals("session-1", resultJson["session_id"]?.jsonPrimitive?.content)
        val message = resultJson["messages"]?.jsonArray?.first()?.jsonObject
        assertEquals("assistant", message?.get("role")?.jsonPrimitive?.content)
        assertEquals("Hello", message?.get("content")?.jsonPrimitive?.content)
        assertEquals("Short thought", message?.get("reasoning")?.jsonPrimitive?.content)
        val attachment = message?.get("attachments")?.jsonArray?.first()?.jsonObject
        assertEquals("document", attachment?.get("type")?.jsonPrimitive?.content)
        assertEquals("text/plain", attachment?.get("mime_type")?.jsonPrimitive?.content)
        assertEquals("context.txt", attachment?.get("name")?.jsonPrimitive?.content)
        assertEquals("Saved context", attachment?.get("text")?.jsonPrimitive?.content)
        assertFalse(attachment?.containsKey("data_base64") ?: true)
        assertEquals("2026-06-23T09:02:06Z", message?.get("created_at")?.jsonPrimitive?.content)
        assertEquals("Short thought", decoded.messages.first().reasoning)
    }

    @Test
    fun chatMessagesListRejectsInlineStoredAttachmentBytes() {
        val response = """
            {
              "session_id": "session-1",
              "messages": [
                {
                  "role": "user",
                  "content": "Summarize this stored attachment.",
                  "attachments": [
                    {
                      "type": "document",
                      "mime_type": "text/plain",
                      "name": "context.txt",
                      "text": "Saved context",
                      "data_base64": "U2F2ZWQgY29udGV4dA=="
                    }
                  ],
                  "created_at": "2026-06-23T09:02:06Z"
                }
              ]
            }
        """.trimIndent()

        val error = assertThrows(Exception::class.java) {
            Json.decodeFromString<ChatMessagesListResultPayload>(response)
        }

        assertTrue(error.message.orEmpty().contains("data_base64"))
    }

    @Test
    fun chatMessagesListRequestRejectsInvalidBounds() {
        val invalidRequests = listOf(
            """{"session_id":"","limit":1}""" to "session_id",
            """{"session_id":"   ","limit":1}""" to "session_id",
            """{"session_id":"session-1","limit":-1}""" to "limit",
            """{"session_id":"session-1","limit":501}""" to "limit",
        )

        invalidRequests.forEach { (json, expectedField) ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<ChatMessagesListRequestPayload>(json)
            }

            assertTrue(
                "expected $expectedField in ${error.message}",
                error.message.orEmpty().contains(expectedField),
            )
        }
    }

    @Test
    fun chatSessionRenamePayloadUsesProtocolFieldNames() {
        val payload = ChatSessionRenamePayload(
            sessionId = "session-1",
            title = "Runtime route notes",
            renamedAt = "2026-06-23T09:02:00Z",
        )

        val json = Json.parseToJsonElement(Json.encodeToString(payload)).jsonObject
        val decoded = Json.decodeFromString<ChatSessionRenamePayload>(Json.encodeToString(payload))

        assertEquals(MessageType.ChatSessionRename, "chat.session.rename")
        assertEquals("session-1", json["session_id"]?.jsonPrimitive?.content)
        assertEquals("Runtime route notes", json["title"]?.jsonPrimitive?.content)
        assertEquals("2026-06-23T09:02:00Z", json["renamed_at"]?.jsonPrimitive?.content)
        assertEquals("session-1", decoded.sessionId)
        assertEquals("Runtime route notes", decoded.title)
    }

    @Test
    fun chatTitleAndSessionMutationRequestsRejectInvalidBounds() {
        val invalidTitleRequests = listOf(
            """{"session_id":"","model":"ollama:llama3.1:8b","messages":[{"role":"user","content":"Title this"}]}""" to "session_id",
            """{"session_id":"   ","model":"ollama:llama3.1:8b","messages":[{"role":"user","content":"Title this"}]}""" to "session_id",
            """{"session_id":"session-1","model":"","messages":[{"role":"user","content":"Title this"}]}""" to "model",
            """{"session_id":"session-1","model":"   ","messages":[{"role":"user","content":"Title this"}]}""" to "model",
            """{"session_id":"session-1","model":"ollama:llama3.1:8b","messages":[]}""" to "messages",
        )
        val invalidRenameRequests = listOf(
            """{"session_id":"","title":"Renamed chat"}""" to "session_id",
            """{"session_id":"   ","title":"Renamed chat"}""" to "session_id",
            """{"session_id":"session-1","title":""}""" to "title",
            """{"session_id":"session-1","title":"   "}""" to "title",
        )
        val invalidLifecycleRequests = listOf(
            """{"session_id":""}""",
            """{"session_id":"   "}""",
        )

        invalidTitleRequests.forEach { (json, expectedField) ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<ChatTitleRequestPayload>(json)
            }

            assertTrue(
                "expected $expectedField in ${error.message}",
                error.message.orEmpty().contains(expectedField),
            )
        }
        invalidRenameRequests.forEach { (json, expectedField) ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<ChatSessionRenamePayload>(json)
            }

            assertTrue(
                "expected $expectedField in ${error.message}",
                error.message.orEmpty().contains(expectedField),
            )
        }
        invalidLifecycleRequests.forEach { json ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<ChatSessionLifecyclePayload>(json)
            }

            assertTrue(
                "expected session_id in ${error.message}",
                error.message.orEmpty().contains("session_id"),
            )
        }
    }

    @Test
    fun chatDeltaPayloadAcceptsCompatibilityAliases() {
        val textAlias = Json.decodeFromString<ChatDeltaPayload>("""{"text":"hello"}""")
        val thinkingAlias = Json.decodeFromString<ChatDeltaPayload>("""{"thinking_delta":"plan"}""")

        assertEquals("hello", textAlias.content)
        assertEquals("plan", thinkingAlias.reasoning)
    }

    @Test
    fun chatStreamResponsePayloadsRejectInvalidBounds() {
        val invalidDeltas = listOf(
            "{}" to "delta",
        )
        val invalidDonePayloads = listOf(
            """{"finish_reason":"timeout"}""" to "finish_reason",
            """{"usage":{"input_tokens":-1,"output_tokens":0}}""" to "input_tokens",
            """{"usage":{"input_tokens":0,"output_tokens":-1}}""" to "output_tokens",
        )

        invalidDeltas.forEach { (json, expectedField) ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<ChatDeltaPayload>(json)
            }

            assertTrue(
                "expected $expectedField in ${error.message}",
                error.message.orEmpty().contains(expectedField),
            )
        }
        invalidDonePayloads.forEach { (json, expectedField) ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<ChatDonePayload>(json)
            }

            assertTrue(
                "expected $expectedField in ${error.message}",
                error.message.orEmpty().contains(expectedField),
            )
        }
    }

    @Test
    fun modelPullAndChatCancelRequestsRejectInvalidBounds() {
        val invalidModelPullRequests = listOf(
            """{"model":""}""" to "model",
            """{"model":"   "}""" to "model",
        )
        val invalidChatCancelRequests = listOf(
            """{"target_request_id":""}""" to "target_request_id",
            """{"target_request_id":"   "}""" to "target_request_id",
        )

        invalidModelPullRequests.forEach { (json, expectedField) ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<ModelPullPayload>(json)
            }

            assertTrue(
                "expected $expectedField in ${error.message}",
                error.message.orEmpty().contains(expectedField),
            )
        }
        invalidChatCancelRequests.forEach { (json, expectedField) ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<ChatCancelPayload>(json)
            }

            assertTrue(
                "expected $expectedField in ${error.message}",
                error.message.orEmpty().contains(expectedField),
            )
        }
    }

    @Test
    fun memoryPayloadsUseProtocolFieldNames() {
        val protocolJson = Json { encodeDefaults = true }
        val source = MemoryEntrySourcePayload(
            kind = "long_inactivity_summary_draft",
            draftId = "long-inactivity:session-1:1000:6",
            summaryMethod = "deterministic_preview",
            session = MemorySummaryDraftSessionPayload(
                sessionId = "session-1",
                title = "Runtime notes",
                model = "ollama:llama3.1:8b",
                lastActivityAt = "2026-06-01T09:02:05Z",
                messageCount = 7,
                inactiveSeconds = 1_209_600,
            ),
            sourceMessageCount = 6,
            sourceRange = "visible messages 1-6 of 6",
            sourcePointers = listOf(
                MemorySummaryDraftSourcePointerPayload(
                    sessionId = "session-1",
                    messageIndex = 1,
                    role = "user",
                    createdAt = "2026-06-01T09:00:00Z",
                    excerpt = "Summarize my preference.",
                ),
            ),
        )
        val entry = MemoryEntryPayload(
            id = "memory-1",
            content = "Prefers concise answers.",
            enabled = true,
            createdAt = "2026-06-25T05:25:00Z",
            updatedAt = "2026-06-25T05:26:00Z",
            source = source,
            search = ChatSessionSearchPayload(
                rank = 1,
                snippet = "Prefers concise answers.",
                matchedFields = listOf("content"),
            ),
        )
        val listRequest = MemoryListRequestPayload(
            query = "concise answers",
            embeddingModelId = "ollama:nomic-embed-text",
        )
        val listResult = MemoryListResultPayload(entries = listOf(entry))
        val upsert = MemoryUpsertPayload(
            id = "memory-1",
            content = "Prefers concise Korean answers.",
            enabled = false,
        )
        val deleteResult = MemoryDeleteResultPayload(
            id = "memory-1",
            deletedAt = "2026-06-25T05:27:00Z",
        )

        val listRequestJson = Json.parseToJsonElement(Json.encodeToString(listRequest)).jsonObject
        val listJson = Json.parseToJsonElement(protocolJson.encodeToString(listResult)).jsonObject
        val upsertJson = Json.parseToJsonElement(Json.encodeToString(upsert)).jsonObject
        val deleteJson = Json.parseToJsonElement(Json.encodeToString(deleteResult)).jsonObject
        val decodedList = Json.decodeFromString<MemoryListResultPayload>(Json.encodeToString(listResult))
        val listedEntry = listJson["entries"]?.jsonArray?.first()?.jsonObject

        assertEquals(MessageType.MemoryList, "memory.list")
        assertEquals(MessageType.MemoryUpsert, "memory.upsert")
        assertEquals(MessageType.MemoryDelete, "memory.delete")
        assertEquals("ollama:nomic-embed-text", listRequestJson["embedding_model_id"]?.jsonPrimitive?.content)
        assertEquals("concise answers", listRequestJson["query"]?.jsonPrimitive?.content)
        assertEquals("memory-1", listedEntry?.get("id")?.jsonPrimitive?.content)
        assertEquals("Prefers concise answers.", listedEntry?.get("content")?.jsonPrimitive?.content)
        assertEquals(true, listedEntry?.get("enabled")?.jsonPrimitive?.boolean)
        assertEquals("2026-06-25T05:25:00Z", listedEntry?.get("created_at")?.jsonPrimitive?.content)
        assertEquals("2026-06-25T05:26:00Z", listedEntry?.get("updated_at")?.jsonPrimitive?.content)
        val listedSource = listedEntry?.get("source")?.jsonObject
        assertEquals("long_inactivity_summary_draft", listedSource?.get("kind")?.jsonPrimitive?.content)
        assertEquals("long-inactivity:session-1:1000:6", listedSource?.get("draft_id")?.jsonPrimitive?.content)
        assertEquals("deterministic_preview", listedSource?.get("summary_method")?.jsonPrimitive?.content)
        assertEquals("session-1", listedSource?.get("session")?.jsonObject?.get("session_id")?.jsonPrimitive?.content)
        assertEquals("visible messages 1-6 of 6", listedSource?.get("source_range")?.jsonPrimitive?.content)
        assertEquals(
            "Summarize my preference.",
            listedSource?.get("source_pointers")?.jsonArray?.first()?.jsonObject?.get("excerpt")?.jsonPrimitive?.content,
        )
        val listedSearch = listedEntry?.get("search")?.jsonObject
        assertEquals("1", listedSearch?.get("rank")?.jsonPrimitive?.content)
        assertEquals("Prefers concise answers.", listedSearch?.get("snippet")?.jsonPrimitive?.content)
        assertEquals(
            listOf("content"),
            listedSearch?.get("matched_fields")?.jsonArray?.map { it.jsonPrimitive.content },
        )
        assertEquals(1, decodedList.entries.first().search?.rank)
        assertEquals("Prefers concise answers.", decodedList.entries.first().search?.snippet)
        assertEquals(listOf("content"), decodedList.entries.first().search?.matchedFields)
        assertEquals("memory-1", upsertJson["id"]?.jsonPrimitive?.content)
        assertEquals("Prefers concise Korean answers.", upsertJson["content"]?.jsonPrimitive?.content)
        assertEquals(false, upsertJson["enabled"]?.jsonPrimitive?.boolean)
        assertEquals("memory-1", deleteJson["id"]?.jsonPrimitive?.content)
        assertEquals("2026-06-25T05:27:00Z", deleteJson["deleted_at"]?.jsonPrimitive?.content)
    }

    @Test
    fun memoryListRequestRejectsInvalidBounds() {
        val error = assertThrows(Exception::class.java) {
            Json.decodeFromString<MemoryListRequestPayload>("""{"query":""}""")
        }

        assertTrue(
            "expected query in ${error.message}",
            error.message.orEmpty().contains("query"),
        )
        val embeddingError = assertThrows(Exception::class.java) {
            Json.decodeFromString<MemoryListRequestPayload>(
                """{"query":"memory","embedding_model_id":"   "}""",
            )
        }
        assertTrue(embeddingError.message.orEmpty().contains("embedding_model_id"))
    }

    @Test
    fun memoryCrudRequestsRejectInvalidBounds() {
        val invalidUpsertRequests = listOf(
            """{"id":"","content":"Prefers concise answers."}""" to "id",
            """{"id":"   ","content":"Prefers concise answers."}""" to "id",
            """{"content":""}""" to "content",
            """{"content":"   "}""" to "content",
        )
        val invalidDeleteRequests = listOf(
            """{"id":""}""" to "id",
            """{"id":"   "}""" to "id",
        )

        invalidUpsertRequests.forEach { (json, expectedField) ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<MemoryUpsertPayload>(json)
            }

            assertTrue(
                "expected $expectedField in ${error.message}",
                error.message.orEmpty().contains(expectedField),
            )
        }
        invalidDeleteRequests.forEach { (json, expectedField) ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<MemoryDeletePayload>(json)
            }

            assertTrue(
                "expected $expectedField in ${error.message}",
                error.message.orEmpty().contains(expectedField),
            )
        }
    }

    @Test
    fun memorySummaryDraftsListPayloadUsesProtocolFieldNames() {
        val protocolJson = Json { encodeDefaults = true }
        val request = MemorySummaryDraftsListRequestPayload(limit = 10)
        val result = MemorySummaryDraftsListResultPayload(
            drafts = listOf(
                MemorySummaryDraftPayload(
                    id = "long-inactivity:session-1:1000:6",
                    session = MemorySummaryDraftSessionPayload(
                        sessionId = "session-1",
                        title = "Runtime notes",
                        model = "ollama:llama3.1:8b",
                        lastActivityAt = "2026-06-01T09:02:05Z",
                        messageCount = 7,
                        inactiveSeconds = 1_209_600,
                    ),
                    sourceMessageCount = 6,
                    sourceRange = "visible messages 1-6 of 6",
                    sourcePointers = listOf(
                        MemorySummaryDraftSourcePointerPayload(
                            sessionId = "session-1",
                            messageIndex = 1,
                            role = "user",
                            createdAt = "2026-06-01T09:00:00Z",
                            excerpt = "Summarize my preference.",
                        ),
                    ),
                    summaryPreview = "User: Summarize my preference.",
                    summaryMethod = "llm_summary_v1",
                    generatedAt = "2026-06-25T05:25:00Z",
                    generatedModelId = "openai:gpt-5.6-sol",
                ),
            ),
        )

        val requestJson = Json.parseToJsonElement(Json.encodeToString(request)).jsonObject
        val resultJson = Json.parseToJsonElement(protocolJson.encodeToString(result)).jsonObject
        val decoded = Json.decodeFromString<MemorySummaryDraftsListResultPayload>(
            protocolJson.encodeToString(result),
        )

        assertEquals(MessageType.MemorySummaryDraftsList, "memory.summary.drafts.list")
        assertEquals("10", requestJson["limit"]?.jsonPrimitive?.content)
        val draft = resultJson["drafts"]?.jsonArray?.first()?.jsonObject
        assertEquals("long-inactivity:session-1:1000:6", draft?.get("id")?.jsonPrimitive?.content)
        val session = draft?.get("session")?.jsonObject
        assertEquals("session-1", session?.get("session_id")?.jsonPrimitive?.content)
        assertEquals("Runtime notes", session?.get("title")?.jsonPrimitive?.content)
        assertEquals("ollama:llama3.1:8b", session?.get("model")?.jsonPrimitive?.content)
        assertEquals("2026-06-01T09:02:05Z", session?.get("last_activity_at")?.jsonPrimitive?.content)
        assertEquals("7", session?.get("message_count")?.jsonPrimitive?.content)
        assertEquals("1209600", session?.get("inactive_seconds")?.jsonPrimitive?.content)
        assertEquals("6", draft?.get("source_message_count")?.jsonPrimitive?.content)
        assertEquals("visible messages 1-6 of 6", draft?.get("source_range")?.jsonPrimitive?.content)
        val sourcePointer = draft?.get("source_pointers")?.jsonArray?.first()?.jsonObject
        assertEquals("session-1", sourcePointer?.get("session_id")?.jsonPrimitive?.content)
        assertEquals("1", sourcePointer?.get("message_index")?.jsonPrimitive?.content)
        assertEquals("user", sourcePointer?.get("role")?.jsonPrimitive?.content)
        assertEquals("2026-06-01T09:00:00Z", sourcePointer?.get("created_at")?.jsonPrimitive?.content)
        assertEquals("Summarize my preference.", sourcePointer?.get("excerpt")?.jsonPrimitive?.content)
        assertEquals("User: Summarize my preference.", draft?.get("summary_preview")?.jsonPrimitive?.content)
        assertEquals("llm_summary_v1", draft?.get("summary_method")?.jsonPrimitive?.content)
        assertEquals("2026-06-25T05:25:00Z", draft?.get("generated_at")?.jsonPrimitive?.content)
        assertEquals("openai:gpt-5.6-sol", draft?.get("generated_model_id")?.jsonPrimitive?.content)
        assertEquals("session-1", decoded.drafts.first().session.sessionId)
        assertEquals(1_209_600L, decoded.drafts.first().session.inactiveSeconds)
        assertEquals(1, decoded.drafts.first().sourcePointers.first().messageIndex)
    }

    @Test
    fun memorySummaryDraftsListRequestRejectsInvalidBounds() {
        val invalidRequests = listOf(
            """{"limit":-1}""",
            """{"limit":51}""",
        )

        invalidRequests.forEach { json ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<MemorySummaryDraftsListRequestPayload>(json)
            }

            assertTrue(
                "expected limit in ${error.message}",
                error.message.orEmpty().contains("limit"),
            )
        }
    }

    @Test
    fun memorySummaryDraftGeneratePayloadRoundTripsExactWireShape() {
        assertEquals(MessageType.MemorySummaryDraftGenerate, "memory.summary.draft.generate")
        val request = MemorySummaryDraftGenerateRequestPayload(
            draftId = "long-inactivity:session-1:1000:6",
            model = "openai:gpt-5.6-sol",
            expectedSessionId = "session-1",
            expectedSourceMessageCount = 6,
        )
        val response = MemorySummaryDraftGenerateResultPayload(
            draft = MemorySummaryDraftPayload(
                id = "long-inactivity:session-1:1000:6",
                session = MemorySummaryDraftSessionPayload(
                    sessionId = "session-1",
                    title = "Runtime notes",
                    model = "ollama:llama3.1:8b",
                    lastActivityAt = "2026-06-01T09:02:05Z",
                    messageCount = 7,
                    inactiveSeconds = 1_209_600,
                ),
                sourceMessageCount = 6,
                sourceRange = "visible messages 1-6 of 6",
                sourcePointers = listOf(
                    MemorySummaryDraftSourcePointerPayload(
                        sessionId = "session-1",
                        messageIndex = 1,
                        role = "user",
                        createdAt = "2026-06-01T09:00:00Z",
                        excerpt = "Summarize my preference.",
                    ),
                ),
                summaryPreview = "Prefers concise Korean release-note summaries.",
                summaryMethod = "llm_summary_v1",
                generatedAt = "2026-06-25T05:25:00Z",
                generatedModelId = "openai:gpt-5.6-sol",
            ),
        )

        val requestJson = Json.parseToJsonElement(Json.encodeToString(request)).jsonObject
        val responseJson = Json.parseToJsonElement(Json.encodeToString(response)).jsonObject
        val decoded = Json.decodeFromString<MemorySummaryDraftGenerateResultPayload>(
            Json.encodeToString(response),
        )

        assertEquals("memory.summary.draft.generate", MessageType.MemorySummaryDraftGenerate)
        assertEquals(
            setOf("draft_id", "model", "expected_session_id", "expected_source_message_count"),
            requestJson.keys,
        )
        assertEquals("openai:gpt-5.6-sol", requestJson["model"]?.jsonPrimitive?.content)
        assertEquals(setOf("draft"), responseJson.keys)
        assertEquals("llm_summary_v1", decoded.draft.summaryMethod)
        assertEquals("2026-06-25T05:25:00Z", decoded.draft.generatedAt)
        assertEquals("openai:gpt-5.6-sol", decoded.draft.generatedModelId)

        val runtimeFailure = Json.decodeFromString<ErrorPayload>(
            """{"code":"memory_summary_draft_generation_failed","message":"Summary generation failed.","retryable":true}""",
        )
        assertEquals("memory_summary_draft_generation_failed", runtimeFailure.code)
    }

    @Test
    fun memorySummaryDraftGeneratePayloadRejectsBoundsMalformedValuesAndUnknownMetadata() {
        val permissiveJson = Json { ignoreUnknownKeys = true }
        val invalidRequests = listOf(
            "blank draft_id" to """{"draft_id":" ","model":"openai:gpt-5.6-sol","expected_session_id":"session-1","expected_source_message_count":6}""",
            "blank model" to """{"draft_id":"draft-1","model":"\t","expected_session_id":"session-1","expected_source_message_count":6}""",
            "blank expected_session_id" to """{"draft_id":"draft-1","model":"openai:gpt-5.6-sol","expected_session_id":"","expected_source_message_count":6}""",
            "zero expected_source_message_count" to """{"draft_id":"draft-1","model":"openai:gpt-5.6-sol","expected_session_id":"session-1","expected_source_message_count":0}""",
            "negative expected_source_message_count" to """{"draft_id":"draft-1","model":"openai:gpt-5.6-sol","expected_session_id":"session-1","expected_source_message_count":-1}""",
            "missing model" to """{"draft_id":"draft-1","expected_session_id":"session-1","expected_source_message_count":6}""",
            "unknown request metadata" to """{"draft_id":"draft-1","model":"openai:gpt-5.6-sol","expected_session_id":"session-1","expected_source_message_count":6,"backend_url":"http://localhost"}""",
        )

        invalidRequests.forEach { (label, json) ->
            assertThrows(label, Exception::class.java) {
                permissiveJson.decodeFromString<MemorySummaryDraftGenerateRequestPayload>(json)
            }
        }

        val validResponse = Json.parseToJsonElement(
            """
            {
              "draft": {
                "id": "draft-1",
                "session": {
                  "session_id": "session-1",
                  "title": "Runtime notes",
                  "model": "ollama:llama3.1:8b",
                  "last_activity_at": "2026-06-01T09:02:05Z",
                  "message_count": 7,
                  "inactive_seconds": 1209600
                },
                "source_message_count": 6,
                "source_range": "visible messages 1-6 of 6",
                "source_pointers": [{
                  "session_id": "session-1",
                  "message_index": 1,
                  "role": "user",
                  "excerpt": "Summarize my preference."
                }],
                "summary_preview": "Prefers concise summaries.",
                "summary_method": "llm_summary_v1",
                "generated_at": "2026-06-25T05:25:00Z",
                "generated_model_id": "openai:gpt-5.6-sol"
              }
            }
            """.trimIndent(),
        ).jsonObject
        val draft = validResponse.getValue("draft").jsonObject
        fun responseWithDraft(value: JsonObject) = JsonObject(validResponse + ("draft" to value))
        val invalidResponses = listOf(
            "unknown response metadata" to validResponse.replacing("route_token", JsonPrimitive("secret")),
            "unknown draft metadata" to responseWithDraft(
                draft.replacing("provider_url", JsonPrimitive("http://localhost")),
            ),
            "invalid summary_method" to responseWithDraft(
                draft.replacing("summary_method", JsonPrimitive("manual")),
            ),
            "invalid generated_at" to responseWithDraft(
                draft.replacing("generated_at", JsonPrimitive("2026-06-25")),
            ),
            "blank generated_model_id" to responseWithDraft(
                draft.replacing("generated_model_id", JsonPrimitive("   ")),
            ),
        )

        invalidResponses.forEach { (label, json) ->
            assertThrows(label, Exception::class.java) {
                permissiveJson.decodeFromString<MemorySummaryDraftGenerateResultPayload>(json.toString())
            }
        }

        val legacyDraft = permissiveJson.decodeFromString<MemorySummaryDraftGenerateResultPayload>(
            responseWithDraft(draft.removing("summary_method")).toString(),
        )
        assertEquals("deterministic_preview", legacyDraft.draft.summaryMethod)
    }

    @Test
    fun memorySummaryDraftResponsePayloadsRejectInvalidBounds() {
        fun sessionJson(
            sessionId: String = """"session-1"""",
            messageCount: String = "7",
            inactiveSeconds: String = "1209600",
        ) = """
            {
              "session_id": $sessionId,
              "title": "Runtime notes",
              "model": "ollama:llama3.1:8b",
              "last_activity_at": "2026-06-01T09:02:05Z",
              "message_count": $messageCount,
              "inactive_seconds": $inactiveSeconds
            }
        """.trimIndent()

        fun sourcePointersJson(
            sessionId: String = """"session-1"""",
            messageIndex: String = "1",
            role: String = """"user"""",
            excerpt: String = """"Summarize my preference."""",
        ) = """
            [
              {
                "session_id": $sessionId,
                "message_index": $messageIndex,
                "role": $role,
                "created_at": "2026-06-01T09:00:00Z",
                "excerpt": $excerpt
              }
            ]
        """.trimIndent()

        fun draftListResultJson(
            id: String = """"long-inactivity:session-1:1000:6"""",
            session: String = sessionJson(),
            sourceMessageCount: String = "6",
            sourceRange: String = """"visible messages 1-6 of 6"""",
            sourcePointers: String = sourcePointersJson(),
            summaryPreview: String = """"User: Summarize my preference."""",
            summaryMethod: String = """"deterministic_preview"""",
        ) = """
            {
              "drafts": [
                {
                  "id": $id,
                  "session": $session,
                  "source_message_count": $sourceMessageCount,
                  "source_range": $sourceRange,
                  "source_pointers": $sourcePointers,
                  "summary_preview": $summaryPreview,
                  "summary_method": $summaryMethod
                }
              ]
            }
        """.trimIndent()

        fun memoryEntrySourceJson(
            kind: String = """"long_inactivity_summary_draft"""",
            draftId: String = """"long-inactivity:session-1:1000:6"""",
            summaryMethod: String = """"deterministic_preview"""",
            sourceMessageCount: String = "6",
            sourceRange: String = """"visible messages 1-6 of 6"""",
            sourcePointers: String = sourcePointersJson(),
        ) = """
            {
              "kind": $kind,
              "draft_id": $draftId,
              "summary_method": $summaryMethod,
              "session": ${sessionJson()},
              "source_message_count": $sourceMessageCount,
              "source_range": $sourceRange,
              "source_pointers": $sourcePointers
            }
        """.trimIndent()

        fun memoryListResultJson(
            id: String = """"memory-1"""",
            content: String = """"Prefers concise answers."""",
            source: String = memoryEntrySourceJson(),
        ) = """
            {
              "entries": [
                {
                  "id": $id,
                  "content": $content,
                  "enabled": true,
                  "created_at": "2026-06-25T05:25:00Z",
                  "updated_at": "2026-06-25T05:26:00Z",
                  "source": $source
                }
              ]
            }
        """.trimIndent()

        val invalidDraftResults = listOf(
            draftListResultJson(id = "\"\"") to "id",
            draftListResultJson(session = sessionJson(sessionId = "\"\"")) to "session_id",
            draftListResultJson(session = sessionJson(messageCount = "-1")) to "message_count",
            draftListResultJson(session = sessionJson(inactiveSeconds = "-1")) to "inactive_seconds",
            draftListResultJson(sourceMessageCount = "0") to "source_message_count",
            draftListResultJson(sourceRange = "\"\"") to "source_range",
            draftListResultJson(sourcePointers = "[]") to "source_pointers",
            draftListResultJson(sourcePointers = sourcePointersJson(sessionId = "\"\"")) to "session_id",
            draftListResultJson(sourcePointers = sourcePointersJson(messageIndex = "0")) to "message_index",
            draftListResultJson(sourcePointers = sourcePointersJson(role = "\"system\"")) to "role",
            draftListResultJson(sourcePointers = sourcePointersJson(excerpt = "\"\"")) to "excerpt",
            draftListResultJson(summaryPreview = "\"\"") to "summary_preview",
            draftListResultJson(summaryMethod = "\"manual\"") to "summary_method",
        )
        val invalidMemoryResults = listOf(
            memoryListResultJson(id = "\"\"") to "id",
            memoryListResultJson(content = "\"\"") to "content",
            memoryListResultJson(source = memoryEntrySourceJson(kind = "\"manual\"")) to "kind",
            memoryListResultJson(source = memoryEntrySourceJson(draftId = "\"\"")) to "draft_id",
            memoryListResultJson(source = memoryEntrySourceJson(summaryMethod = "\"manual\"")) to "summary_method",
            memoryListResultJson(source = memoryEntrySourceJson(sourceMessageCount = "0")) to "source_message_count",
            memoryListResultJson(source = memoryEntrySourceJson(sourceRange = "\"\"")) to "source_range",
            memoryListResultJson(source = memoryEntrySourceJson(sourcePointers = "[]")) to "source_pointers",
        )

        invalidDraftResults.forEach { (json, expectedField) ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<MemorySummaryDraftsListResultPayload>(json)
            }

            assertTrue(
                "expected $expectedField in ${error.message}",
                error.message.orEmpty().contains(expectedField),
            )
        }
        invalidMemoryResults.forEach { (json, expectedField) ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<MemoryListResultPayload>(json)
            }

            assertTrue(
                "expected $expectedField in ${error.message}",
                error.message.orEmpty().contains(expectedField),
            )
        }
    }

    @Test
    fun memorySummaryDraftApprovePayloadUsesProtocolFieldNames() {
        val protocolJson = Json { encodeDefaults = true }
        val request = MemorySummaryDraftApprovePayload(
            draftId = "long-inactivity:session-1:1000:6",
            content = "Prefer concise Korean release-note summaries.",
            enabled = true,
            expectedSessionId = "session-1",
            expectedSourceMessageCount = 6,
        )
        val result = MemorySummaryDraftApproveResultPayload(
            draftId = "long-inactivity:session-1:1000:6",
            status = "approved",
            entry = MemoryEntryPayload(
                id = "memory-summary:long-inactivity:session-1:1000:6",
                content = "Prefer concise Korean release-note summaries.",
                enabled = true,
                createdAt = "2026-06-25T05:25:00Z",
                updatedAt = "2026-06-25T05:26:00Z",
                source = MemoryEntrySourcePayload(
                    kind = "long_inactivity_summary_draft",
                    draftId = "long-inactivity:session-1:1000:6",
                    summaryMethod = "deterministic_preview",
                    session = MemorySummaryDraftSessionPayload(
                        sessionId = "session-1",
                        title = "Runtime notes",
                        model = "ollama:llama3.1:8b",
                        lastActivityAt = "2026-06-01T09:02:05Z",
                        messageCount = 7,
                        inactiveSeconds = 1_209_600,
                    ),
                    sourceMessageCount = 6,
                    sourceRange = "visible messages 1-6 of 6",
                    sourcePointers = listOf(
                        MemorySummaryDraftSourcePointerPayload(
                            sessionId = "session-1",
                            messageIndex = 1,
                            role = "user",
                            createdAt = "2026-06-01T09:00:00Z",
                            excerpt = "Summarize my preference.",
                        ),
                    ),
                ),
            ),
        )

        val requestJson = Json.parseToJsonElement(Json.encodeToString(request)).jsonObject
        val resultJson = Json.parseToJsonElement(protocolJson.encodeToString(result)).jsonObject
        val decoded = Json.decodeFromString<MemorySummaryDraftApproveResultPayload>(
            protocolJson.encodeToString(result),
        )

        assertEquals(MessageType.MemorySummaryDraftApprove, "memory.summary.draft.approve")
        assertEquals("long-inactivity:session-1:1000:6", requestJson["draft_id"]?.jsonPrimitive?.content)
        assertEquals("Prefer concise Korean release-note summaries.", requestJson["content"]?.jsonPrimitive?.content)
        assertEquals(true, requestJson["enabled"]?.jsonPrimitive?.boolean)
        assertEquals("session-1", requestJson["expected_session_id"]?.jsonPrimitive?.content)
        assertEquals("6", requestJson["expected_source_message_count"]?.jsonPrimitive?.content)
        assertEquals("long-inactivity:session-1:1000:6", resultJson["draft_id"]?.jsonPrimitive?.content)
        assertEquals("approved", resultJson["status"]?.jsonPrimitive?.content)
        val entry = resultJson["entry"]?.jsonObject
        assertEquals("memory-summary:long-inactivity:session-1:1000:6", entry?.get("id")?.jsonPrimitive?.content)
        assertEquals("Prefer concise Korean release-note summaries.", entry?.get("content")?.jsonPrimitive?.content)
        assertEquals(
            "long_inactivity_summary_draft",
            entry?.get("source")?.jsonObject?.get("kind")?.jsonPrimitive?.content,
        )
        assertEquals(
            "visible messages 1-6 of 6",
            decoded.entry.source?.sourceRange,
        )
        assertEquals("memory-summary:long-inactivity:session-1:1000:6", decoded.entry.id)
    }

    @Test
    fun memorySummaryDraftDecisionRequestsRejectInvalidBounds() {
        val invalidApproveRequests = listOf(
            """{"draft_id":"","content":"Reviewed memory"}""" to "draft_id",
            """{"draft_id":"   ","content":"Reviewed memory"}""" to "draft_id",
            """{"draft_id":"long-inactivity:session-1:1000:6","content":""}""" to "content",
            """{"draft_id":"long-inactivity:session-1:1000:6","content":"   "}""" to "content",
            """{"draft_id":"long-inactivity:session-1:1000:6","expected_session_id":""}""" to "expected_session_id",
            """{"draft_id":"long-inactivity:session-1:1000:6","expected_session_id":"   "}""" to "expected_session_id",
            """{"draft_id":"long-inactivity:session-1:1000:6","expected_source_message_count":0}""" to "expected_source_message_count",
            """{"draft_id":"long-inactivity:session-1:1000:6","expected_source_message_count":-1}""" to "expected_source_message_count",
        )
        val invalidDismissRequests = listOf(
            """{"draft_id":""}""" to "draft_id",
            """{"draft_id":"   "}""" to "draft_id",
            """{"draft_id":"long-inactivity:session-1:1000:6","expected_session_id":""}""" to "expected_session_id",
            """{"draft_id":"long-inactivity:session-1:1000:6","expected_session_id":"   "}""" to "expected_session_id",
            """{"draft_id":"long-inactivity:session-1:1000:6","expected_source_message_count":0}""" to "expected_source_message_count",
            """{"draft_id":"long-inactivity:session-1:1000:6","expected_source_message_count":-1}""" to "expected_source_message_count",
        )

        invalidApproveRequests.forEach { (json, expectedField) ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<MemorySummaryDraftApprovePayload>(json)
            }

            assertTrue(
                "expected $expectedField in ${error.message}",
                error.message.orEmpty().contains(expectedField),
            )
        }
        invalidDismissRequests.forEach { (json, expectedField) ->
            val error = assertThrows(Exception::class.java) {
                Json.decodeFromString<MemorySummaryDraftDismissPayload>(json)
            }

            assertTrue(
                "expected $expectedField in ${error.message}",
                error.message.orEmpty().contains(expectedField),
            )
        }
    }

    @Test
    fun memorySummaryDraftDismissPayloadUsesProtocolFieldNames() {
        val protocolJson = Json { encodeDefaults = true }
        val request = MemorySummaryDraftDismissPayload(
            draftId = "long-inactivity:session-1:1000:6",
            expectedSessionId = "session-1",
            expectedSourceMessageCount = 6,
        )
        val result = MemorySummaryDraftDismissResultPayload(
            draftId = "long-inactivity:session-1:1000:6",
            status = "dismissed",
            dismissedAt = "2026-06-25T05:26:00Z",
        )

        val requestJson = Json.parseToJsonElement(Json.encodeToString(request)).jsonObject
        val resultJson = Json.parseToJsonElement(protocolJson.encodeToString(result)).jsonObject
        val decoded = Json.decodeFromString<MemorySummaryDraftDismissResultPayload>(
            protocolJson.encodeToString(result),
        )

        assertEquals(MessageType.MemorySummaryDraftDismiss, "memory.summary.draft.dismiss")
        assertEquals("long-inactivity:session-1:1000:6", requestJson["draft_id"]?.jsonPrimitive?.content)
        assertEquals("session-1", requestJson["expected_session_id"]?.jsonPrimitive?.content)
        assertEquals("6", requestJson["expected_source_message_count"]?.jsonPrimitive?.content)
        assertEquals("long-inactivity:session-1:1000:6", resultJson["draft_id"]?.jsonPrimitive?.content)
        assertEquals("dismissed", resultJson["status"]?.jsonPrimitive?.content)
        assertEquals("2026-06-25T05:26:00Z", resultJson["dismissed_at"]?.jsonPrimitive?.content)
        assertEquals("long-inactivity:session-1:1000:6", decoded.draftId)
        assertEquals("dismissed", decoded.status)
        assertEquals("2026-06-25T05:26:00Z", decoded.dismissedAt)
    }

    @Test
    fun chatAndMemoryPayloadsRejectInvalidTimestampMetadata() {
        val invalidDecodes: List<Pair<String, () -> Unit>> = listOf(
            "last_activity_at" to {
                Json.decodeFromString<ChatSessionsListResultPayload>(
                    """
                    {
                      "sessions": [
                        {
                          "session_id": "session-1",
                          "title": "Runtime notes",
                          "model": "ollama:llama3.1:8b",
                          "last_activity_at": "not-a-date",
                          "message_count": 1
                        }
                      ]
                    }
                    """.trimIndent(),
                )
                Unit
            },
            "archived_at" to {
                Json.decodeFromString<ChatSessionsListResultPayload>(
                    """
                    {
                      "sessions": [
                        {
                          "session_id": "session-1",
                          "title": "Runtime notes",
                          "model": "ollama:llama3.1:8b",
                          "last_activity_at": "2026-06-23T09:02:05Z",
                          "message_count": 1,
                          "status": "archived",
                          "archived_at": "2026-07-09"
                        }
                      ]
                    }
                    """.trimIndent(),
                )
                Unit
            },
            "created_at" to {
                Json.decodeFromString<ChatMessagesListResultPayload>(
                    """
                    {
                      "session_id": "session-1",
                      "messages": [
                        {
                          "role": "user",
                          "content": "Hello",
                          "created_at": "2026-07-09"
                        }
                      ]
                    }
                    """.trimIndent(),
                )
                Unit
            },
            "renamed_at" to {
                Json.decodeFromString<ChatSessionRenamePayload>(
                    """{"session_id":"session-1","title":"Runtime notes","renamed_at":"not-a-date"}""",
                )
                Unit
            },
            "archived_at" to {
                Json.decodeFromString<ChatSessionLifecyclePayload>(
                    """{"session_id":"session-1","status":"archived","archived_at":"not-a-date"}""",
                )
                Unit
            },
            "restored_at" to {
                Json.decodeFromString<ChatSessionLifecyclePayload>(
                    """{"session_id":"session-1","status":"active","restored_at":"2026-07-09"}""",
                )
                Unit
            },
            "deleted_at" to {
                Json.decodeFromString<ChatSessionLifecyclePayload>(
                    """{"session_id":"session-1","status":"deleted","deleted_at":"2026-07-09T12:34:56"}""",
                )
                Unit
            },
            "created_at" to {
                Json.decodeFromString<MemoryListResultPayload>(
                    """
                    {
                      "entries": [
                        {
                          "id": "memory-1",
                          "content": "Prefers concise answers.",
                          "enabled": true,
                          "created_at": "not-a-date"
                        }
                      ]
                    }
                    """.trimIndent(),
                )
                Unit
            },
            "updated_at" to {
                Json.decodeFromString<MemoryListResultPayload>(
                    """
                    {
                      "entries": [
                        {
                          "id": "memory-1",
                          "content": "Prefers concise answers.",
                          "enabled": true,
                          "updated_at": "2026-07-09"
                        }
                      ]
                    }
                    """.trimIndent(),
                )
                Unit
            },
            "deleted_at" to {
                Json.decodeFromString<MemoryDeleteResultPayload>(
                    """{"id":"memory-1","deleted_at":"2026-07-09"}""",
                )
                Unit
            },
            "dismissed_at" to {
                Json.decodeFromString<MemorySummaryDraftDismissResultPayload>(
                    """{"draft_id":"long-inactivity:session-1:1000:6","status":"dismissed","dismissed_at":"not-a-date"}""",
                )
                Unit
            },
            "last_activity_at" to {
                Json.decodeFromString<MemorySummaryDraftsListResultPayload>(
                    """
                    {
                      "drafts": [
                        {
                          "id": "long-inactivity:session-1:1000:6",
                          "session": {
                            "session_id": "session-1",
                            "title": "Runtime notes",
                            "model": "ollama:llama3.1:8b",
                            "last_activity_at": "not-a-date",
                            "message_count": 7,
                            "inactive_seconds": 1209600
                          },
                          "source_message_count": 6,
                          "source_range": "visible messages 1-6 of 6",
                          "source_pointers": [
                            {
                              "session_id": "session-1",
                              "message_index": 1,
                              "role": "user",
                              "created_at": "2026-06-01T09:00:00Z",
                              "excerpt": "Summarize my preference."
                            }
                          ],
                          "summary_preview": "User: Summarize my preference.",
                          "summary_method": "deterministic_preview"
                        }
                      ]
                    }
                    """.trimIndent(),
                )
                Unit
            },
            "created_at" to {
                Json.decodeFromString<MemorySummaryDraftsListResultPayload>(
                    """
                    {
                      "drafts": [
                        {
                          "id": "long-inactivity:session-1:1000:6",
                          "session": {
                            "session_id": "session-1",
                            "title": "Runtime notes",
                            "model": "ollama:llama3.1:8b",
                            "last_activity_at": "2026-06-01T09:02:05Z",
                            "message_count": 7,
                            "inactive_seconds": 1209600
                          },
                          "source_message_count": 6,
                          "source_range": "visible messages 1-6 of 6",
                          "source_pointers": [
                            {
                              "session_id": "session-1",
                              "message_index": 1,
                              "role": "user",
                              "created_at": "2026-07-09",
                              "excerpt": "Summarize my preference."
                            }
                          ],
                          "summary_preview": "User: Summarize my preference.",
                          "summary_method": "deterministic_preview"
                        }
                      ]
                    }
                    """.trimIndent(),
                )
                Unit
            },
        )

        invalidDecodes.forEach { (expectedField, decode) ->
            val error = assertThrows(Exception::class.java) {
                decode()
            }

            assertTrue(
                "expected $expectedField in ${error.message}",
                error.message.orEmpty().contains(expectedField),
            )
        }
    }

    private fun assertSourceAnchorDecodeRejected(sourceAnchorId: String, decode: () -> Unit) {
        val error = assertThrows(Exception::class.java) {
            decode()
        }
        val message = error.message.orEmpty()

        assertTrue(
            "Expected noncanonical $sourceAnchorId decode error to name source_anchor_id, got $message",
            message.contains("source_anchor_id"),
        )
        assertTrue(
            "Expected noncanonical $sourceAnchorId decode error to name canonical source-anchor shape, got $message",
            message.contains("source_anchor_[16 lowercase hex]"),
        )
    }

    private fun assertContentFingerprintDecodeRejected(contentFingerprint: String, decode: () -> Unit) {
        val error = assertThrows(Exception::class.java) {
            decode()
        }
        val message = error.message.orEmpty()

        assertTrue(
            "Expected noncanonical $contentFingerprint decode error to name content_fingerprint, got $message",
            message.contains("content_fingerprint"),
        )
        assertTrue(
            "Expected noncanonical $contentFingerprint decode error to name canonical fingerprint shape, got $message",
            message.contains("16 lowercase hex"),
        )
    }

    private val canonicalSourceAnchorId = "source_anchor_0123456789abcdef"
    private val canonicalCitationId = "citation_${"0".repeat(32)}"
    private val canonicalReviewId = "source_review_${"1".repeat(32)}"
    private val canonicalConfirmationToken = "source_confirmation_${"2".repeat(64)}"
    private val canonicalGrantId = "trusted_source_${"3".repeat(32)}"

    private fun canonicalDocumentPayload() = RuntimeDocumentIndexDocumentPayload(
        id = "doc-1",
        displayName = "runtime-notes.md",
        mimeType = "text/markdown",
        contentFingerprint = "0011223344556677",
        extractedCharacterCount = 2048,
        chunkCount = 3,
        quality = "chunked",
    )

    private fun canonicalCitationPayload() = CitationPayload(
        schemaVersion = 1,
        citationId = canonicalCitationId,
        sourceAnchorId = canonicalSourceAnchorId,
        document = canonicalDocumentPayload(),
        chunkSummary = SourceAnchorChunkSummaryPayload(
            chunkIndex = 1,
            startCharacterOffset = 120,
            endCharacterOffset = 240,
            characterCount = 120,
        ),
    )

    private fun canonicalSourceReviewPayload() = SourceReviewPayload(
        reviewId = canonicalReviewId,
        confirmationToken = canonicalConfirmationToken,
        disclosureVersion = "runtime-trusted-source-v1",
        usageScope = "chat_context",
        expiresAt = "2026-07-12T12:00:00Z",
    )

    private fun canonicalTrustedSourcePayload() = TrustedSourcePayload(
        grantId = canonicalGrantId,
        citationId = canonicalCitationId,
        sourceAnchorId = canonicalSourceAnchorId,
        document = canonicalDocumentPayload(),
        usageScope = "chat_context",
        approvedAt = "2026-07-12T11:00:00Z",
    )

    private fun jsonString(value: String): String = "\"$value\""

    private fun indexDocumentJson(
        id: String = """"doc-1"""",
        displayName: String = """"runtime-notes.md"""",
        mimeType: String = """"text/markdown"""",
        contentFingerprint: String = """"0011223344556677"""",
        extractedCharacterCount: String = "2048",
        chunkCount: String = "3",
        quality: String = """"chunked"""",
    ): String {
        return """
            {
              "id": $id,
              "display_name": $displayName,
              "mime_type": $mimeType,
              "content_fingerprint": $contentFingerprint,
              "extracted_character_count": $extractedCharacterCount,
              "chunk_count": $chunkCount,
              "quality": $quality
            }
        """.trimIndent()
    }

    private fun indexDocumentsSummaryJson(
        documentCount: String = "1",
        chunkCount: String = "3",
        extractedCharacterCount: String = "2048",
        qualityCountsJson: String = """
            {
              "no_usable_text": 0,
              "single_chunk": 0,
              "chunked": 1
            }
        """.trimIndent(),
    ): String {
        return """
            {
              "document_count": $documentCount,
              "chunk_count": $chunkCount,
              "extracted_character_count": $extractedCharacterCount,
              "quality_counts": $qualityCountsJson
            }
        """.trimIndent()
    }

    private fun indexDocumentsListResultJson(
        documentsJson: String = indexDocumentJson(),
        summaryJson: String = indexDocumentsSummaryJson(),
    ): String {
        return """
            {
              "documents": [
                $documentsJson
              ],
              "summary": $summaryJson
            }
        """.trimIndent()
    }

    private fun retrievalQueryResultJsonWithDocument(documentJson: String): String {
        return """
            {
              "results": [
                {
                  "document": $documentJson,
                  "chunk_index": 1,
                  "start_character_offset": 120,
                  "end_character_offset": 240,
                  "rank": 2,
                  "matched_terms": ["relay", "route"],
                  "snippet": "Runtime document snippet matched relay route.",
                  "source_anchor_id": "source_anchor_0123456789abcdef"
                }
              ]
            }
        """.trimIndent()
    }

    private fun retrievalQueryResultItemJson(index: Int): String {
        val fingerprint = index.toString(16).padStart(16, '0')
        return """
            {
              "document": ${indexDocumentJson(
                  id = jsonString("doc-$index"),
                  contentFingerprint = jsonString(fingerprint),
              )},
              "chunk_index": 0,
              "start_character_offset": 0,
              "end_character_offset": 64,
              "rank": ${index + 1},
              "matched_terms": ["relay"],
              "snippet": "Runtime document snippet matched relay.",
              "source_anchor_id": "source_anchor_$fingerprint"
            }
        """.trimIndent()
    }

    private fun retrievalQueryResultJsonWithResults(resultsJson: String): String {
        return """
            {
              "results": [
                $resultsJson
              ]
            }
        """.trimIndent()
    }

    private fun sourceAnchorResolveResultJsonWithDocument(documentJson: String): String {
        return """
            {
              "source_anchor_id": "source_anchor_0123456789abcdef",
              "document": $documentJson,
              "chunk_summary": {
                "chunk_index": 1,
                "start_character_offset": 120,
                "end_character_offset": 240,
                "character_count": 120
              }
            }
        """.trimIndent()
    }

    private fun indexDocumentsListResultJsonWithContentFingerprint(contentFingerprint: String): String {
        return """
            {
              "documents": [
                {
                  "id": "doc-1",
                  "display_name": "runtime-notes.md",
                  "mime_type": "text/markdown",
                  "content_fingerprint": "$contentFingerprint",
                  "extracted_character_count": 2048,
                  "chunk_count": 3,
                  "quality": "chunked"
                }
              ],
              "summary": {
                "document_count": 1,
                "chunk_count": 3,
                "extracted_character_count": 2048,
                "quality_counts": {
                  "no_usable_text": 0,
                  "single_chunk": 0,
                  "chunked": 1
                }
              }
            }
        """.trimIndent()
    }

    private fun retrievalQueryResultJsonWithSourceAnchor(
        sourceAnchorId: String,
        contentFingerprint: String = "0011223344556677",
        chunkIndex: Int = 1,
        startCharacterOffset: Int = 120,
        endCharacterOffset: Int = 240,
        rank: Int = 2,
        matchKind: String? = null,
        matchedTermsJson: String = "\"relay\", \"route\"",
        snippet: String = "Runtime document snippet matched relay route.",
    ): String {
        val matchKindJson = matchKind?.let { "\"match_kind\": \"$it\"," }.orEmpty()
        return """
            {
              "results": [
                {
                  "document": {
                    "id": "doc-1",
                    "display_name": "runtime-notes.md",
                    "mime_type": "text/markdown",
                    "content_fingerprint": "$contentFingerprint",
                    "extracted_character_count": 2048,
                    "chunk_count": 3,
                    "quality": "chunked"
                  },
                  "chunk_index": $chunkIndex,
                  "start_character_offset": $startCharacterOffset,
                  "end_character_offset": $endCharacterOffset,
                  "rank": $rank,
                  $matchKindJson
                  "matched_terms": [$matchedTermsJson],
                  "snippet": "$snippet",
                  "source_anchor_id": "$sourceAnchorId"
                }
              ]
            }
        """.trimIndent()
    }

    private fun sourceAnchorResolveResultJsonWithSourceAnchor(
        sourceAnchorId: String,
        contentFingerprint: String = "0011223344556677",
        chunkSummaryOverrides: Map<String, Int> = emptyMap(),
    ): String {
        val chunkIndex = chunkSummaryOverrides["chunk_index"] ?: 1
        val startCharacterOffset = chunkSummaryOverrides["start_character_offset"] ?: 120
        val endCharacterOffset = chunkSummaryOverrides["end_character_offset"] ?: 240
        val characterCount = chunkSummaryOverrides["character_count"] ?: 120
        return """
            {
              "source_anchor_id": "$sourceAnchorId",
              "document": {
                "id": "doc-1",
                "display_name": "runtime-notes.md",
                "mime_type": "text/markdown",
                "content_fingerprint": "$contentFingerprint",
                "extracted_character_count": 2048,
                "chunk_count": 3,
                "quality": "chunked"
              },
              "chunk_summary": {
                "chunk_index": $chunkIndex,
                "start_character_offset": $startCharacterOffset,
                "end_character_offset": $endCharacterOffset,
                "character_count": $characterCount
              }
            }
        """.trimIndent()
    }
}
