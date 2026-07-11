package com.localagentbridge.android.core.protocol

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.KSerializer
import kotlinx.serialization.descriptors.PrimitiveKind
import kotlinx.serialization.descriptors.PrimitiveSerialDescriptor
import kotlinx.serialization.descriptors.SerialDescriptor
import kotlinx.serialization.encoding.Decoder
import kotlinx.serialization.encoding.Encoder
import kotlinx.serialization.json.JsonDecoder
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.decodeFromJsonElement
import java.time.Instant
import java.util.UUID

const val PROTOCOL_VERSION = 1
const val PAIRING_PROOF_SCHEME_P256_SHA256_DER_V1 = "p256-sha256-der-v1"
const val RELAY_ALLOCATION_PROOF_SCHEME = "runtime-client-p256-v2"
const val RELAY_ALLOCATION_PROTOCOL_VERSION = 2

private val SOURCE_ANCHOR_ID_PATTERN = Regex("^source_anchor_[0-9a-f]{16}$")
private val DOCUMENT_CONTENT_FINGERPRINT_PATTERN = Regex("^[0-9a-f]{16}$")
private val LOWERCASE_HEX_64_PATTERN = Regex("^[0-9a-f]{64}$")
private val RUNTIME_KEY_BOUND_RELAY_ID_PATTERN = Regex("^rt2-[0-9a-f]{64}$")
private val CANONICAL_BASE64_PATTERN = Regex("^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$")
private val DOCUMENT_MIME_TYPE_PATTERN = Regex("^[a-z0-9!#\$%&'*+.^_`|~-]+/[a-z0-9!#\$%&'*+.^_`|~-]+$")
private const val MAX_CHAT_SESSION_LIST_LIMIT = 200
private const val MAX_CHAT_MESSAGES_LIST_LIMIT = 500
private const val MAX_MEMORY_SUMMARY_DRAFTS_LIST_LIMIT = 50
private const val MAX_DOCUMENT_REQUEST_LIMIT = 100
private const val MAX_DOCUMENT_ID_LENGTH = 128
private const val MAX_DOCUMENT_DISPLAY_NAME_LENGTH = 256
private const val MAX_DOCUMENT_MIME_TYPE_LENGTH = 128
private const val MAX_RETRIEVAL_QUERY_LENGTH = 1024
private const val MAX_RETRIEVAL_MATCHED_TERMS = 16
private const val MAX_RETRIEVAL_MATCHED_TERM_LENGTH = 64
private const val MAX_RETRIEVAL_SNIPPET_LENGTH = 500
private const val MAX_RELAY_ALLOCATION_OPAQUE_LENGTH = 512
private val DOCUMENT_QUALITIES = setOf("no_usable_text", "single_chunk", "chunked")
private val CHAT_MESSAGE_ROLES = setOf("system", "user", "assistant")
private val CHAT_ATTACHMENT_TYPES = setOf("image", "document", "file")
private val CHAT_DONE_FINISH_REASONS = setOf("stop", "cancelled", "error")
private val RUNTIME_HEALTH_STATUSES = setOf("ok", "degraded", "unavailable")
private val MODEL_INFO_PROVIDERS = setOf("ollama", "lm_studio")
private val MODEL_INFO_KINDS = setOf("chat", "embedding")
private val MODEL_INFO_SOURCES = setOf("local", "cloud")
private val ROUTE_REFRESH_RELAY_SCOPES = setOf("remote", "private_overlay", "usb_reverse")
private val RELAY_ALLOCATION_OPERATIONS = setOf("claim", "renew")
private val CHAT_SESSION_STATUSES = setOf("active", "archived")
private val CHAT_SESSION_LAST_EVENTS = setOf(
    "request",
    "assistant_delta",
    "reasoning_delta",
    "done",
    "cancelled",
    "error",
)
private val ERROR_CODES = setOf(
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
    "document_index_unavailable",
    "source_anchor_not_found",
    "memory_store_unavailable",
    "memory_summary_draft_unavailable",
    "memory_summary_draft_stale",
    "transport_error",
    "internal_error",
)
private const val MEMORY_ENTRY_SOURCE_KIND = "long_inactivity_summary_draft"
private const val MEMORY_ENTRY_SOURCE_SUMMARY_METHOD = "deterministic_preview"
private val MEMORY_SUMMARY_SOURCE_POINTER_ROLES = setOf("user", "assistant")

private fun requireProtocolDateTime(value: String?, fieldName: String) {
    if (value == null) return
    try {
        Instant.parse(value)
    } catch (error: Exception) {
        throw IllegalArgumentException("$fieldName must be date-time", error)
    }
}

private object SourceAnchorIdSerializer : KSerializer<String> {
    override val descriptor: SerialDescriptor =
        PrimitiveSerialDescriptor("SourceAnchorId", PrimitiveKind.STRING)

    override fun deserialize(decoder: Decoder): String {
        val value = decoder.decodeString()
        require(SOURCE_ANCHOR_ID_PATTERN.matches(value)) {
            "source_anchor_id must match source_anchor_[16 lowercase hex]"
        }
        return value
    }

    override fun serialize(encoder: Encoder, value: String) {
        encoder.encodeString(value)
    }
}

private object DocumentContentFingerprintSerializer : KSerializer<String> {
    override val descriptor: SerialDescriptor =
        PrimitiveSerialDescriptor("DocumentContentFingerprint", PrimitiveKind.STRING)

    override fun deserialize(decoder: Decoder): String {
        val value = decoder.decodeString()
        require(DOCUMENT_CONTENT_FINGERPRINT_PATTERN.matches(value)) {
            "content_fingerprint must match 16 lowercase hex characters"
        }
        return value
    }

    override fun serialize(encoder: Encoder, value: String) {
        encoder.encodeString(value)
    }
}

private object RouteRefreshOpaqueValueSerializer : KSerializer<String> {
    override val descriptor: SerialDescriptor =
        PrimitiveSerialDescriptor("RouteRefreshOpaqueValue", PrimitiveKind.STRING)

    override fun deserialize(decoder: Decoder): String {
        val value = decoder.decodeString()
        require(value.isNotEmpty() && value.length <= 512 && value.none { it.isWhitespace() }) {
            "route.refresh opaque route value must be nonempty, at most 512 characters, and whitespace-free"
        }
        return value
    }

    override fun serialize(encoder: Encoder, value: String) {
        encoder.encodeString(value)
    }
}

private object RouteRefreshOpaqueBodySerializer : KSerializer<String> {
    override val descriptor: SerialDescriptor =
        PrimitiveSerialDescriptor("RouteRefreshOpaqueBody", PrimitiveKind.STRING)

    override fun deserialize(decoder: Decoder): String {
        val value = decoder.decodeString()
        require(value.isNotEmpty() && value.length <= 2048 && value.none { it.isWhitespace() }) {
            "route.refresh opaque route body must be nonempty, at most 2048 characters, and whitespace-free"
        }
        return value
    }

    override fun serialize(encoder: Encoder, value: String) {
        encoder.encodeString(value)
    }
}

private object RouteRefreshRelayPortSerializer : KSerializer<Int> {
    override val descriptor: SerialDescriptor =
        PrimitiveSerialDescriptor("RouteRefreshRelayPort", PrimitiveKind.INT)

    override fun deserialize(decoder: Decoder): Int {
        val value = decoder.decodeInt()
        require(value in 1..65_535) {
            "route.refresh relay_port must be between 1 and 65535"
        }
        return value
    }

    override fun serialize(encoder: Encoder, value: Int) {
        encoder.encodeInt(value)
    }
}

private object RouteRefreshExpirySerializer : KSerializer<Long> {
    override val descriptor: SerialDescriptor =
        PrimitiveSerialDescriptor("RouteRefreshExpiry", PrimitiveKind.LONG)

    override fun deserialize(decoder: Decoder): Long {
        val value = decoder.decodeLong()
        require(value >= 1L) {
            "route.refresh route expiry must be positive"
        }
        return value
    }

    override fun serialize(encoder: Encoder, value: Long) {
        encoder.encodeLong(value)
    }
}

private object PositiveTicketGenerationSerializer : KSerializer<Long> {
    override val descriptor: SerialDescriptor =
        PrimitiveSerialDescriptor("PositiveTicketGeneration", PrimitiveKind.LONG)

    override fun deserialize(decoder: Decoder): Long {
        val value = decoder.decodeLong()
        require(value > 0) {
            "ticket_generation must be positive"
        }
        return value
    }

    override fun serialize(encoder: Encoder, value: Long) {
        require(value > 0) {
            "ticket_generation must be positive"
        }
        encoder.encodeLong(value)
    }
}

private object RouteRefreshRelayScopeSerializer : KSerializer<String> {
    override val descriptor: SerialDescriptor =
        PrimitiveSerialDescriptor("RouteRefreshRelayScope", PrimitiveKind.STRING)

    override fun deserialize(decoder: Decoder): String {
        val value = decoder.decodeString()
        require(value in ROUTE_REFRESH_RELAY_SCOPES) {
            "route.refresh relay_scope must be remote, private_overlay, or usb_reverse"
        }
        return value
    }

    override fun serialize(encoder: Encoder, value: String) {
        encoder.encodeString(value)
    }
}

private object RouteRefreshP2pClassSerializer : KSerializer<String> {
    override val descriptor: SerialDescriptor =
        PrimitiveSerialDescriptor("RouteRefreshP2pClass", PrimitiveKind.STRING)

    override fun deserialize(decoder: Decoder): String {
        val value = decoder.decodeString()
        require(value == "p2p_rendezvous") {
            "route.refresh p2p_class must be p2p_rendezvous"
        }
        return value
    }

    override fun serialize(encoder: Encoder, value: String) {
        encoder.encodeString(value)
    }
}

private object RouteRefreshP2pProtocolVersionSerializer : KSerializer<Int> {
    override val descriptor: SerialDescriptor =
        PrimitiveSerialDescriptor("RouteRefreshP2pProtocolVersion", PrimitiveKind.INT)

    override fun deserialize(decoder: Decoder): Int {
        val value = decoder.decodeInt()
        require(value == 1) {
            "route.refresh p2p_protocol_version must be 1"
        }
        return value
    }

    override fun serialize(encoder: Encoder, value: Int) {
        encoder.encodeInt(value)
    }
}

@Serializable
private data class RouteRefreshPayloadSurrogate(
    @Serializable(with = RouteRefreshOpaqueValueSerializer::class)
    @SerialName("runtime_device_id") val runtimeDeviceId: String? = null,
    @Serializable(with = RouteRefreshOpaqueValueSerializer::class)
    @SerialName("runtime_key_fingerprint") val runtimeKeyFingerprint: String? = null,
    @SerialName("relay_host") val relayHost: String? = null,
    @Serializable(with = RouteRefreshRelayPortSerializer::class)
    @SerialName("relay_port") val relayPort: Int? = null,
    @Serializable(with = RouteRefreshOpaqueValueSerializer::class)
    @SerialName("relay_id") val relayId: String? = null,
    @Serializable(with = RouteRefreshOpaqueValueSerializer::class)
    @SerialName("relay_secret") val relaySecret: String? = null,
    @Serializable(with = RouteRefreshExpirySerializer::class)
    @SerialName("relay_expires_at") val relayExpiresAtEpochMillis: Long? = null,
    @Serializable(with = RouteRefreshOpaqueValueSerializer::class)
    @SerialName("relay_nonce") val relayNonce: String? = null,
    @Serializable(with = RouteRefreshRelayScopeSerializer::class)
    @SerialName("relay_scope") val relayScope: String? = null,
    @Serializable(with = PositiveTicketGenerationSerializer::class)
    @SerialName("ticket_generation") val ticketGeneration: Long? = null,
    @Serializable(with = RouteRefreshP2pClassSerializer::class)
    @SerialName("p2p_class") val p2pRouteClass: String? = null,
    @Serializable(with = RouteRefreshOpaqueValueSerializer::class)
    @SerialName("p2p_record_id") val p2pRecordId: String? = null,
    @Serializable(with = RouteRefreshOpaqueBodySerializer::class)
    @SerialName("p2p_encrypted_body") val p2pEncryptedBody: String? = null,
    @Serializable(with = RouteRefreshExpirySerializer::class)
    @SerialName("p2p_expires_at") val p2pExpiresAtEpochMillis: Long? = null,
    @Serializable(with = RouteRefreshOpaqueValueSerializer::class)
    @SerialName("p2p_anti_replay_nonce") val p2pAntiReplayNonce: String? = null,
    @Serializable(with = RouteRefreshP2pProtocolVersionSerializer::class)
    @SerialName("p2p_protocol_version") val p2pProtocolVersion: Int? = null,
)

object RouteRefreshPayloadSerializer : KSerializer<RouteRefreshPayload> {
    override val descriptor: SerialDescriptor = RouteRefreshPayloadSurrogate.serializer().descriptor

    override fun deserialize(decoder: Decoder): RouteRefreshPayload {
        val surrogate = decoder.decodeSerializableValue(RouteRefreshPayloadSurrogate.serializer())
        validateRouteRefreshPayloadSurrogate(surrogate)
        return surrogate.toRouteRefreshPayload()
    }

    override fun serialize(encoder: Encoder, value: RouteRefreshPayload) {
        encoder.encodeSerializableValue(RouteRefreshPayloadSurrogate.serializer(), value.toRouteRefreshPayloadSurrogate())
    }
}

private fun validateRouteRefreshPayloadSurrogate(payload: RouteRefreshPayloadSurrogate) {
    val hasRuntimeIdentity = payload.runtimeDeviceId != null && payload.runtimeKeyFingerprint != null
    val relayValues = listOf(
        payload.relayHost,
        payload.relayPort,
        payload.relayId,
        payload.relaySecret,
        payload.relayExpiresAtEpochMillis,
        payload.relayNonce,
    )
    val p2pValues = listOf(
        payload.p2pRouteClass,
        payload.p2pRecordId,
        payload.p2pEncryptedBody,
        payload.p2pExpiresAtEpochMillis,
        payload.p2pAntiReplayNonce,
        payload.p2pProtocolVersion,
    )
    val hasRelayField = relayValues.any { it != null } || payload.relayScope != null || payload.ticketGeneration != null
    val hasP2pField = p2pValues.any { it != null }
    val hasAnyField = hasRelayField || hasP2pField || payload.runtimeDeviceId != null || payload.runtimeKeyFingerprint != null
    if (!hasAnyField) return

    require(hasRuntimeIdentity) {
        "route.refresh payload must include runtime_device_id and runtime_key_fingerprint when route material is present"
    }

    val hasCompleteRelay = relayValues.all { it != null }
    val hasCompleteP2p = p2pValues.all { it != null }
    require(!hasRelayField || hasCompleteRelay) {
        "route.refresh relay route material must include relay_host, relay_port, relay_id, relay_secret, relay_expires_at, and relay_nonce together"
    }
    require(!hasP2pField || hasCompleteP2p) {
        "route.refresh P2P route material must include p2p_class, p2p_record_id, p2p_encrypted_body, p2p_expires_at, p2p_anti_replay_nonce, and p2p_protocol_version together"
    }
    require(hasCompleteRelay || hasCompleteP2p) {
        "route.refresh payload must be empty or include complete relay or P2P route material"
    }
}

private fun RouteRefreshPayloadSurrogate.toRouteRefreshPayload(): RouteRefreshPayload =
    RouteRefreshPayload(
        runtimeDeviceId = runtimeDeviceId,
        runtimeKeyFingerprint = runtimeKeyFingerprint,
        relayHost = relayHost,
        relayPort = relayPort,
        relayId = relayId,
        relaySecret = relaySecret,
        relayExpiresAtEpochMillis = relayExpiresAtEpochMillis,
        relayNonce = relayNonce,
        relayScope = relayScope,
        ticketGeneration = ticketGeneration,
        p2pRouteClass = p2pRouteClass,
        p2pRecordId = p2pRecordId,
        p2pEncryptedBody = p2pEncryptedBody,
        p2pExpiresAtEpochMillis = p2pExpiresAtEpochMillis,
        p2pAntiReplayNonce = p2pAntiReplayNonce,
        p2pProtocolVersion = p2pProtocolVersion,
    )

private fun RouteRefreshPayload.toRouteRefreshPayloadSurrogate(): RouteRefreshPayloadSurrogate =
    RouteRefreshPayloadSurrogate(
        runtimeDeviceId = runtimeDeviceId,
        runtimeKeyFingerprint = runtimeKeyFingerprint,
        relayHost = relayHost,
        relayPort = relayPort,
        relayId = relayId,
        relaySecret = relaySecret,
        relayExpiresAtEpochMillis = relayExpiresAtEpochMillis,
        relayNonce = relayNonce,
        relayScope = relayScope,
        ticketGeneration = ticketGeneration,
        p2pRouteClass = p2pRouteClass,
        p2pRecordId = p2pRecordId,
        p2pEncryptedBody = p2pEncryptedBody,
        p2pExpiresAtEpochMillis = p2pExpiresAtEpochMillis,
        p2pAntiReplayNonce = p2pAntiReplayNonce,
        p2pProtocolVersion = p2pProtocolVersion,
    )

@Serializable
private data class RelayAllocationChallengePayloadSurrogate(
    @SerialName("proof_scheme") val proofScheme: String,
    @SerialName("protocol_version") val protocolVersion: Int,
    val operation: String,
    @SerialName("authorization_id") val authorizationId: String,
    @SerialName("current_relay_id") val currentRelayId: String,
    @SerialName("next_relay_id") val nextRelayId: String,
    @SerialName("route_token_hash") val routeTokenHash: String,
    @SerialName("runtime_key_fingerprint") val runtimeKeyFingerprint: String,
    @SerialName("client_key_fingerprint") val clientKeyFingerprint: String,
    @SerialName("current_ticket_generation") val currentTicketGeneration: Long,
    @SerialName("next_ticket_generation") val nextTicketGeneration: Long,
    @SerialName("current_relay_expires_at") val currentRelayExpiresAtEpochMillis: Long,
    @SerialName("current_relay_nonce") val currentRelayNonce: String,
    @SerialName("next_relay_expires_at") val nextRelayExpiresAtEpochMillis: Long,
    @SerialName("next_relay_nonce") val nextRelayNonce: String,
    val challenge: String,
    @SerialName("challenge_expires_at") val challengeExpiresAtEpochMillis: Long,
    @SerialName("transport_binding") val transportBinding: String,
)

object RelayAllocationChallengePayloadSerializer : KSerializer<RelayAllocationChallengePayload> {
    override val descriptor: SerialDescriptor = RelayAllocationChallengePayloadSurrogate.serializer().descriptor

    override fun deserialize(decoder: Decoder): RelayAllocationChallengePayload {
        val (jsonDecoder, payload) = decoder.decodeExactJsonObject(RELAY_ALLOCATION_CHALLENGE_FIELDS)
        return jsonDecoder.json
            .decodeFromJsonElement(RelayAllocationChallengePayloadSurrogate.serializer(), payload)
            .toRelayAllocationChallengePayload()
    }

    override fun serialize(encoder: Encoder, value: RelayAllocationChallengePayload) {
        encoder.encodeSerializableValue(
            RelayAllocationChallengePayloadSurrogate.serializer(),
            value.toRelayAllocationChallengePayloadSurrogate(),
        )
    }
}

@Serializable(with = RelayAllocationChallengePayloadSerializer::class)
data class RelayAllocationChallengePayload(
    @SerialName("proof_scheme") val proofScheme: String,
    @SerialName("protocol_version") val protocolVersion: Int,
    val operation: String,
    @SerialName("authorization_id") val authorizationId: String,
    @SerialName("current_relay_id") val currentRelayId: String,
    @SerialName("next_relay_id") val nextRelayId: String,
    @SerialName("route_token_hash") val routeTokenHash: String,
    @SerialName("runtime_key_fingerprint") val runtimeKeyFingerprint: String,
    @SerialName("client_key_fingerprint") val clientKeyFingerprint: String,
    @SerialName("current_ticket_generation") val currentTicketGeneration: Long,
    @SerialName("next_ticket_generation") val nextTicketGeneration: Long,
    @SerialName("current_relay_expires_at") val currentRelayExpiresAtEpochMillis: Long,
    @SerialName("current_relay_nonce") val currentRelayNonce: String,
    @SerialName("next_relay_expires_at") val nextRelayExpiresAtEpochMillis: Long,
    @SerialName("next_relay_nonce") val nextRelayNonce: String,
    val challenge: String,
    @SerialName("challenge_expires_at") val challengeExpiresAtEpochMillis: Long,
    @SerialName("transport_binding") val transportBinding: String,
) {
    init {
        require(proofScheme == RELAY_ALLOCATION_PROOF_SCHEME) {
            "relay allocation proof_scheme must be $RELAY_ALLOCATION_PROOF_SCHEME"
        }
        require(protocolVersion == RELAY_ALLOCATION_PROTOCOL_VERSION) {
            "relay allocation protocol_version must be $RELAY_ALLOCATION_PROTOCOL_VERSION"
        }
        require(operation in RELAY_ALLOCATION_OPERATIONS) {
            "relay allocation operation must be claim or renew"
        }
        require(authorizationId.isBoundedNonBlankRelayAllocationValue()) {
            "relay allocation authorization_id must be nonblank and at most $MAX_RELAY_ALLOCATION_OPAQUE_LENGTH characters"
        }
        require(RUNTIME_KEY_BOUND_RELAY_ID_PATTERN.matches(currentRelayId)) {
            "relay allocation current_relay_id must match rt2-[64 lowercase hex]"
        }
        require(RUNTIME_KEY_BOUND_RELAY_ID_PATTERN.matches(nextRelayId)) {
            "relay allocation next_relay_id must match rt2-[64 lowercase hex]"
        }
        require(operation != "claim" || currentRelayId != nextRelayId) {
            "relay allocation claim next_relay_id must differ from current_relay_id"
        }
        require(LOWERCASE_HEX_64_PATTERN.matches(routeTokenHash)) {
            "relay allocation route_token_hash must be 64 lowercase hex characters"
        }
        require(LOWERCASE_HEX_64_PATTERN.matches(runtimeKeyFingerprint)) {
            "relay allocation runtime_key_fingerprint must be 64 lowercase hex characters"
        }
        require(LOWERCASE_HEX_64_PATTERN.matches(clientKeyFingerprint)) {
            "relay allocation client_key_fingerprint must be 64 lowercase hex characters"
        }
        require(currentTicketGeneration > 0) {
            "relay allocation current_ticket_generation must be positive"
        }
        require(nextTicketGeneration > 0) {
            "relay allocation next_ticket_generation must be positive"
        }
        require(currentRelayExpiresAtEpochMillis > 0) {
            "relay allocation current_relay_expires_at must be positive"
        }
        require(currentRelayNonce.isBoundedWhitespaceFreeRelayAllocationValue()) {
            "relay allocation current_relay_nonce must be nonempty, whitespace-free, and at most $MAX_RELAY_ALLOCATION_OPAQUE_LENGTH characters"
        }
        require(nextRelayExpiresAtEpochMillis > 0) {
            "relay allocation next_relay_expires_at must be positive"
        }
        require(nextRelayNonce.isBoundedWhitespaceFreeRelayAllocationValue()) {
            "relay allocation next_relay_nonce must be nonempty, whitespace-free, and at most $MAX_RELAY_ALLOCATION_OPAQUE_LENGTH characters"
        }
        require(LOWERCASE_HEX_64_PATTERN.matches(challenge)) {
            "relay allocation challenge must be 64 lowercase hex characters"
        }
        require(challengeExpiresAtEpochMillis > 0) {
            "relay allocation challenge_expires_at must be positive"
        }
        require(LOWERCASE_HEX_64_PATTERN.matches(transportBinding)) {
            "relay allocation transport_binding must be 64 lowercase hex characters"
        }
    }
}

@Serializable
private data class RelayAllocationAuthorizationPayloadSurrogate(
    @SerialName("proof_scheme") val proofScheme: String,
    @SerialName("authorization_id") val authorizationId: String,
    val challenge: String,
    @SerialName("client_key_fingerprint") val clientKeyFingerprint: String,
    @SerialName("transport_binding") val transportBinding: String,
    @SerialName("client_signature") val clientSignature: String,
)

object RelayAllocationAuthorizationPayloadSerializer : KSerializer<RelayAllocationAuthorizationPayload> {
    override val descriptor: SerialDescriptor = RelayAllocationAuthorizationPayloadSurrogate.serializer().descriptor

    override fun deserialize(decoder: Decoder): RelayAllocationAuthorizationPayload {
        val (jsonDecoder, payload) = decoder.decodeExactJsonObject(RELAY_ALLOCATION_AUTHORIZATION_FIELDS)
        return jsonDecoder.json
            .decodeFromJsonElement(RelayAllocationAuthorizationPayloadSurrogate.serializer(), payload)
            .toRelayAllocationAuthorizationPayload()
    }

    override fun serialize(encoder: Encoder, value: RelayAllocationAuthorizationPayload) {
        encoder.encodeSerializableValue(
            RelayAllocationAuthorizationPayloadSurrogate.serializer(),
            value.toRelayAllocationAuthorizationPayloadSurrogate(),
        )
    }
}

@Serializable(with = RelayAllocationAuthorizationPayloadSerializer::class)
data class RelayAllocationAuthorizationPayload(
    @SerialName("proof_scheme") val proofScheme: String,
    @SerialName("authorization_id") val authorizationId: String,
    val challenge: String,
    @SerialName("client_key_fingerprint") val clientKeyFingerprint: String,
    @SerialName("transport_binding") val transportBinding: String,
    @SerialName("client_signature") val clientSignature: String,
) {
    init {
        require(proofScheme == RELAY_ALLOCATION_PROOF_SCHEME) {
            "relay allocation proof_scheme must be $RELAY_ALLOCATION_PROOF_SCHEME"
        }
        require(authorizationId.isBoundedNonBlankRelayAllocationValue()) {
            "relay allocation authorization_id must be nonblank and at most $MAX_RELAY_ALLOCATION_OPAQUE_LENGTH characters"
        }
        require(LOWERCASE_HEX_64_PATTERN.matches(challenge)) {
            "relay allocation challenge must be 64 lowercase hex characters"
        }
        require(LOWERCASE_HEX_64_PATTERN.matches(clientKeyFingerprint)) {
            "relay allocation client_key_fingerprint must be 64 lowercase hex characters"
        }
        require(LOWERCASE_HEX_64_PATTERN.matches(transportBinding)) {
            "relay allocation transport_binding must be 64 lowercase hex characters"
        }
        require(
            clientSignature.isNotEmpty() &&
                clientSignature.length <= MAX_RELAY_ALLOCATION_OPAQUE_LENGTH &&
                CANONICAL_BASE64_PATTERN.matches(clientSignature)
        ) {
            "relay allocation client_signature must be canonical Base64 and at most $MAX_RELAY_ALLOCATION_OPAQUE_LENGTH characters"
        }
    }
}

private val RELAY_ALLOCATION_CHALLENGE_FIELDS = setOf(
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
)

private val RELAY_ALLOCATION_AUTHORIZATION_FIELDS = setOf(
    "proof_scheme",
    "authorization_id",
    "challenge",
    "client_key_fingerprint",
    "transport_binding",
    "client_signature",
)

private fun Decoder.decodeExactJsonObject(expectedFields: Set<String>): Pair<JsonDecoder, JsonObject> {
    val jsonDecoder = this as? JsonDecoder
        ?: throw IllegalArgumentException("relay allocation payloads require JSON decoding")
    val payload = jsonDecoder.decodeJsonElement() as? JsonObject
        ?: throw IllegalArgumentException("relay allocation payload must be a JSON object")
    val unknownFields = payload.keys.filterNot { it in expectedFields }.sorted()
    require(unknownFields.isEmpty()) {
        "relay allocation payload contains unknown field: ${unknownFields.first()}"
    }
    return jsonDecoder to payload
}

private fun String.isBoundedNonBlankRelayAllocationValue(): Boolean =
    length <= MAX_RELAY_ALLOCATION_OPAQUE_LENGTH && any { !it.isWhitespace() }

private fun String.isBoundedWhitespaceFreeRelayAllocationValue(): Boolean =
    isNotEmpty() && length <= MAX_RELAY_ALLOCATION_OPAQUE_LENGTH && none { it.isWhitespace() }

private fun RelayAllocationChallengePayloadSurrogate.toRelayAllocationChallengePayload() =
    RelayAllocationChallengePayload(
        proofScheme = proofScheme,
        protocolVersion = protocolVersion,
        operation = operation,
        authorizationId = authorizationId,
        currentRelayId = currentRelayId,
        nextRelayId = nextRelayId,
        routeTokenHash = routeTokenHash,
        runtimeKeyFingerprint = runtimeKeyFingerprint,
        clientKeyFingerprint = clientKeyFingerprint,
        currentTicketGeneration = currentTicketGeneration,
        nextTicketGeneration = nextTicketGeneration,
        currentRelayExpiresAtEpochMillis = currentRelayExpiresAtEpochMillis,
        currentRelayNonce = currentRelayNonce,
        nextRelayExpiresAtEpochMillis = nextRelayExpiresAtEpochMillis,
        nextRelayNonce = nextRelayNonce,
        challenge = challenge,
        challengeExpiresAtEpochMillis = challengeExpiresAtEpochMillis,
        transportBinding = transportBinding,
    )

private fun RelayAllocationChallengePayload.toRelayAllocationChallengePayloadSurrogate() =
    RelayAllocationChallengePayloadSurrogate(
        proofScheme = proofScheme,
        protocolVersion = protocolVersion,
        operation = operation,
        authorizationId = authorizationId,
        currentRelayId = currentRelayId,
        nextRelayId = nextRelayId,
        routeTokenHash = routeTokenHash,
        runtimeKeyFingerprint = runtimeKeyFingerprint,
        clientKeyFingerprint = clientKeyFingerprint,
        currentTicketGeneration = currentTicketGeneration,
        nextTicketGeneration = nextTicketGeneration,
        currentRelayExpiresAtEpochMillis = currentRelayExpiresAtEpochMillis,
        currentRelayNonce = currentRelayNonce,
        nextRelayExpiresAtEpochMillis = nextRelayExpiresAtEpochMillis,
        nextRelayNonce = nextRelayNonce,
        challenge = challenge,
        challengeExpiresAtEpochMillis = challengeExpiresAtEpochMillis,
        transportBinding = transportBinding,
    )

private fun RelayAllocationAuthorizationPayloadSurrogate.toRelayAllocationAuthorizationPayload() =
    RelayAllocationAuthorizationPayload(
        proofScheme = proofScheme,
        authorizationId = authorizationId,
        challenge = challenge,
        clientKeyFingerprint = clientKeyFingerprint,
        transportBinding = transportBinding,
        clientSignature = clientSignature,
    )

private fun RelayAllocationAuthorizationPayload.toRelayAllocationAuthorizationPayloadSurrogate() =
    RelayAllocationAuthorizationPayloadSurrogate(
        proofScheme = proofScheme,
        authorizationId = authorizationId,
        challenge = challenge,
        clientKeyFingerprint = clientKeyFingerprint,
        transportBinding = transportBinding,
        clientSignature = clientSignature,
    )

@Serializable
data class ProtocolEnvelope(
    val version: Int = PROTOCOL_VERSION,
    val type: String,
    @SerialName("request_id") val requestId: String = UUID.randomUUID().toString(),
    val timestamp: String = Instant.now().toString(),
    val payload: JsonObject = JsonObject(emptyMap()),
)

object MessageType {
    const val RuntimeHealth = "runtime.health"
    const val Hello = "hello"
    const val AuthChallenge = "auth.challenge"
    const val AuthResponse = "auth.response"
    const val PairingRequest = "pairing.request"
    const val PairingResult = "pairing.result"
    const val ModelsList = "models.list"
    const val ModelsResult = "models.result"
    const val ModelsPull = "models.pull"
    const val RouteRefresh = "route.refresh"
    const val RelayAllocationChallenge = "relay.allocation.challenge"
    const val RelayAllocationAuthorization = "relay.allocation.authorization"
    const val ChatSend = "chat.send"
    const val ChatDelta = "chat.delta"
    const val ChatDone = "chat.done"
    const val ChatCancel = "chat.cancel"
    const val ChatSessionsList = "chat.sessions.list"
    const val ChatMessagesList = "chat.messages.list"
    const val ChatTitleRequest = "chat.title.request"
    const val ChatTitleResult = "chat.title.result"
    const val ChatSessionRename = "chat.session.rename"
    const val ChatSessionArchive = "chat.session.archive"
    const val ChatSessionRestore = "chat.session.restore"
    const val ChatSessionDelete = "chat.session.delete"
    const val IndexDocumentsList = "index.documents.list"
    const val RetrievalQuery = "retrieval.query"
    const val SourceAnchorResolve = "source_anchor.resolve"
    const val MemoryList = "memory.list"
    const val MemoryUpsert = "memory.upsert"
    const val MemoryDelete = "memory.delete"
    const val MemorySummaryDraftsList = "memory.summary.drafts.list"
    const val MemorySummaryDraftApprove = "memory.summary.draft.approve"
    const val MemorySummaryDraftDismiss = "memory.summary.draft.dismiss"
    const val Error = "error"
}

@Serializable
data class HelloPayload(
    @SerialName("device_id") val deviceId: String,
    @SerialName("device_name") val deviceName: String,
    @SerialName("client_capabilities")
    val capabilities: List<String>,
    @SerialName("transport_binding") val transportBinding: String? = null,
)

@Serializable
data class AuthChallengePayload(
    @SerialName("device_id") val deviceId: String? = null,
    val nonce: String,
    @SerialName("runtime_key_fingerprint") val runtimeKeyFingerprint: String? = null,
    @SerialName("runtime_signature") val runtimeSignature: String? = null,
    @SerialName("transport_binding") val transportBinding: String? = null,
)

@Serializable
data class AuthResponsePayload(
    @SerialName("device_id") val deviceId: String? = null,
    val nonce: String? = null,
    val signature: String? = null,
    val accepted: Boolean? = null,
    val message: String? = null,
    @SerialName("transport_binding") val transportBinding: String? = null,
)

@Serializable
data class PairingRequestPayload(
    @SerialName("pairing_nonce") val pairingNonce: String,
    @SerialName("pairing_code") val pairingCode: String,
    @SerialName("device_id") val deviceId: String,
    @SerialName("device_name") val deviceName: String,
    @SerialName("public_key") val publicKey: String,
    @SerialName("pairing_proof_scheme") val pairingProofScheme: String,
    @SerialName("pairing_signature") val pairingSignature: String,
    @SerialName("transport_binding") val transportBinding: String? = null,
)

@Serializable
data class PairingResultPayload(
    val accepted: Boolean,
    @SerialName("mac_device_id") val runtimeDeviceId: String? = null,
    @SerialName("runtime_device_id") val runtimeDeviceIdV2: String? = null,
    @SerialName("runtime_public_key") val runtimePublicKey: String? = null,
    @SerialName("runtime_key_fingerprint") val runtimeKeyFingerprint: String? = null,
    @SerialName("trusted_device_id") val trustedDeviceId: String? = null,
    val message: String,
    @SerialName("pairing_proof_scheme") val pairingProofScheme: String? = null,
    @SerialName("pairing_request_digest") val pairingRequestDigest: String? = null,
    @SerialName("runtime_pairing_signature") val runtimePairingSignature: String? = null,
    @SerialName("transport_binding") val transportBinding: String? = null,
)

@Serializable
data class ModelInfoPayload(
    val id: String,
    val name: String? = null,
    val backend: String? = null,
    val provider: String? = null,
    @SerialName("model_kind") val modelKind: String? = null,
    val kind: String? = null,
    val capabilities: List<String> = emptyList(),
    @SerialName("provider_model_id") val providerModelId: String? = null,
    @SerialName("qualified_id") val qualifiedId: String? = null,
    val installed: Boolean? = null,
    val running: Boolean? = null,
    val source: String? = null,
    val description: String? = null,
    @SerialName("size_bytes") val sizeBytes: Long? = null,
    @SerialName("context_window_tokens") val contextWindowTokens: Int? = null,
    @SerialName("modified_at") val modifiedAt: String? = null,
    @SerialName("remote_model") val remoteModel: String? = null,
) {
    init {
        require(id.isNotEmpty()) {
            "model info id must be nonempty"
        }
        require(!name.isNullOrEmpty()) {
            "model info name must be nonempty"
        }
        require(backend == null || backend in MODEL_INFO_PROVIDERS) {
            "model info backend must be ollama or lm_studio"
        }
        require(provider == null || provider in MODEL_INFO_PROVIDERS) {
            "model info provider must be ollama or lm_studio"
        }
        require(modelKind == null || modelKind in MODEL_INFO_KINDS) {
            "model info model_kind must be chat or embedding"
        }
        require(capabilities.distinct() == capabilities) {
            "model info capabilities must be unique"
        }
        require(source == null || source in MODEL_INFO_SOURCES) {
            "model info source must be local or cloud"
        }
        require(sizeBytes == null || sizeBytes >= 0) {
            "model info size_bytes must be nonnegative"
        }
        require(contextWindowTokens == null || contextWindowTokens > 0) {
            "model info context_window_tokens must be positive"
        }
        requireProtocolDateTime(modifiedAt, "model info modified_at")
    }
}

@Serializable
data class ModelsResultPayload(
    val models: List<ModelInfoPayload>,
)

@Serializable
data class ModelPullPayload(
    val model: String,
) {
    init {
        require(model.isNotBlank()) {
            "models.pull request model must be nonblank"
        }
    }
}

@Serializable
data class ModelPullResultPayload(
    val model: String? = null,
    val id: String? = null,
    val backend: String? = null,
    val provider: String? = null,
    val accepted: Boolean? = null,
    val success: Boolean? = null,
    val status: String? = null,
    val installed: Boolean? = null,
    val message: String? = null,
)

@Serializable(with = RouteRefreshPayloadSerializer::class)
data class RouteRefreshPayload(
    @Serializable(with = RouteRefreshOpaqueValueSerializer::class)
    @SerialName("runtime_device_id") val runtimeDeviceId: String? = null,
    @Serializable(with = RouteRefreshOpaqueValueSerializer::class)
    @SerialName("runtime_key_fingerprint") val runtimeKeyFingerprint: String? = null,
    @SerialName("relay_host") val relayHost: String? = null,
    @Serializable(with = RouteRefreshRelayPortSerializer::class)
    @SerialName("relay_port") val relayPort: Int? = null,
    @Serializable(with = RouteRefreshOpaqueValueSerializer::class)
    @SerialName("relay_id") val relayId: String? = null,
    @Serializable(with = RouteRefreshOpaqueValueSerializer::class)
    @SerialName("relay_secret") val relaySecret: String? = null,
    @Serializable(with = RouteRefreshExpirySerializer::class)
    @SerialName("relay_expires_at") val relayExpiresAtEpochMillis: Long? = null,
    @Serializable(with = RouteRefreshOpaqueValueSerializer::class)
    @SerialName("relay_nonce") val relayNonce: String? = null,
    @Serializable(with = RouteRefreshRelayScopeSerializer::class)
    @SerialName("relay_scope") val relayScope: String? = null,
    @Serializable(with = PositiveTicketGenerationSerializer::class)
    @SerialName("ticket_generation") val ticketGeneration: Long? = null,
    @Serializable(with = RouteRefreshP2pClassSerializer::class)
    @SerialName("p2p_class") val p2pRouteClass: String? = null,
    @Serializable(with = RouteRefreshOpaqueValueSerializer::class)
    @SerialName("p2p_record_id") val p2pRecordId: String? = null,
    @Serializable(with = RouteRefreshOpaqueBodySerializer::class)
    @SerialName("p2p_encrypted_body") val p2pEncryptedBody: String? = null,
    @Serializable(with = RouteRefreshExpirySerializer::class)
    @SerialName("p2p_expires_at") val p2pExpiresAtEpochMillis: Long? = null,
    @Serializable(with = RouteRefreshOpaqueValueSerializer::class)
    @SerialName("p2p_anti_replay_nonce") val p2pAntiReplayNonce: String? = null,
    @Serializable(with = RouteRefreshP2pProtocolVersionSerializer::class)
    @SerialName("p2p_protocol_version") val p2pProtocolVersion: Int? = null,
) {
    init {
        require(ticketGeneration == null || ticketGeneration > 0) {
            "route.refresh ticket_generation must be positive"
        }
    }
}

@Serializable
data class ChatMessagePayload(
    val role: String,
    val content: String,
    val attachments: List<ChatAttachmentPayload> = emptyList(),
) {
    init {
        require(role in CHAT_MESSAGE_ROLES) {
            "chat.send message role must be system, user, or assistant"
        }
    }
}

@Serializable
data class ChatAttachmentPayload(
    val type: String,
    @SerialName("mime_type") val mimeType: String,
    val name: String? = null,
    @SerialName("data_base64") val dataBase64: String? = null,
    val text: String? = null,
) {
    init {
        require(type in CHAT_ATTACHMENT_TYPES) {
            "chat.send attachment type must be image, document, or file"
        }
        require(mimeType.isNotEmpty()) {
            "chat.send attachment mime_type must be nonempty"
        }
    }
}

@Serializable
data class ChatStoredAttachmentPayload(
    val type: String,
    @SerialName("mime_type") val mimeType: String,
    val name: String? = null,
    val text: String? = null,
) {
    init {
        require(type in CHAT_ATTACHMENT_TYPES) {
            "chat.messages.list attachment type must be image, document, or file"
        }
        require(mimeType.isNotEmpty()) {
            "chat.messages.list attachment mime_type must be nonempty"
        }
    }
}

@Serializable
data class ChatSendPayload(
    @SerialName("session_id") val sessionId: String,
    val model: String,
    val messages: List<ChatMessagePayload>,
    val locale: String? = null,
) {
    init {
        require(sessionId.isNotBlank()) {
            "chat.send request session_id must be nonblank"
        }
        require(model.isNotBlank()) {
            "chat.send request model must be nonblank"
        }
        require(messages.isNotEmpty()) {
            "chat.send request messages must be nonempty"
        }
    }
}

@Serializable
data class ChatDeltaPayload(
    val delta: String? = null,
    val text: String? = null,
    @SerialName("reasoning_delta") val reasoningDelta: String? = null,
    @SerialName("thinking_delta") val thinkingDelta: String? = null,
) {
    init {
        require(delta != null || text != null || reasoningDelta != null || thinkingDelta != null) {
            "chat.delta payload must include delta, text, reasoning_delta, or thinking_delta"
        }
    }

    val content: String
        get() = delta ?: text.orEmpty()

    val reasoning: String
        get() = reasoningDelta ?: thinkingDelta.orEmpty()
}

@Serializable
data class ChatDonePayload(
    @SerialName("finish_reason") val finishReason: String? = null,
    val usage: UsagePayload? = null,
) {
    init {
        require(finishReason == null || finishReason in CHAT_DONE_FINISH_REASONS) {
            "chat.done finish_reason must be stop, cancelled, or error"
        }
    }
}

@Serializable
data class UsagePayload(
    @SerialName("input_tokens") val inputTokens: Int = 0,
    @SerialName("output_tokens") val outputTokens: Int = 0,
) {
    init {
        require(inputTokens >= 0) {
            "chat.done usage input_tokens must be nonnegative"
        }
        require(outputTokens >= 0) {
            "chat.done usage output_tokens must be nonnegative"
        }
    }
}

@Serializable
data class ChatCancelPayload(
    @SerialName("target_request_id") val targetRequestId: String,
) {
    init {
        require(targetRequestId.isNotBlank()) {
            "chat.cancel request target_request_id must be nonblank"
        }
    }
}

@Serializable
data class ChatSessionsListRequestPayload(
    val limit: Int? = null,
    @SerialName("include_archived") val includeArchived: Boolean = false,
    val query: String? = null,
    @SerialName("embedding_model_id") val embeddingModelId: String? = null,
) {
    init {
        require(limit == null || limit >= 0) {
            "chat.sessions.list request limit must be nonnegative"
        }
        require(limit == null || limit <= MAX_CHAT_SESSION_LIST_LIMIT) {
            "chat.sessions.list request limit must be at most 200"
        }
        require(query == null || query.isNotEmpty()) {
            "chat.sessions.list request query must be nonempty"
        }
        require(embeddingModelId == null || embeddingModelId.isNotEmpty()) {
            "chat.sessions.list request embedding_model_id must be nonempty"
        }
    }
}

@Serializable
data class ChatSessionsListResultPayload(
    val sessions: List<ChatSessionSummaryPayload>,
)

@Serializable
data class ChatSessionSummaryPayload(
    @SerialName("session_id") val sessionId: String,
    val title: String,
    val model: String,
    @SerialName("last_activity_at") val lastActivityAt: String,
    @SerialName("message_count") val messageCount: Int,
    val status: String? = null,
    @SerialName("archived_at") val archivedAt: String? = null,
    @SerialName("last_event") val lastEvent: String? = null,
    @SerialName("last_finish_reason") val lastFinishReason: String? = null,
    @SerialName("last_error_code") val lastErrorCode: String? = null,
    val search: ChatSessionSearchPayload? = null,
) {
    init {
        require(sessionId.isNotEmpty()) {
            "chat.sessions.list response session_id must be nonempty"
        }
        require(messageCount >= 0) {
            "chat.sessions.list response message_count must be nonnegative"
        }
        require(status == null || status in CHAT_SESSION_STATUSES) {
            "chat.sessions.list response status must be active or archived"
        }
        require(lastEvent == null || lastEvent in CHAT_SESSION_LAST_EVENTS) {
            "chat.sessions.list response last_event must be a known chat event"
        }
        requireProtocolDateTime(lastActivityAt, "chat.sessions.list response last_activity_at")
        requireProtocolDateTime(archivedAt, "chat.sessions.list response archived_at")
    }
}

@Serializable
data class ChatSessionSearchPayload(
    val rank: Int,
    val snippet: String,
    @SerialName("matched_fields") val matchedFields: List<String> = emptyList(),
) {
    init {
        require(rank >= 1) {
            "chat session search rank must be positive"
        }
        require(matchedFields.isNotEmpty()) {
            "chat session search matched_fields must be nonempty"
        }
        require(matchedFields.all { it.isNotEmpty() }) {
            "chat session search matched_fields entries must be nonempty"
        }
        require(matchedFields.toSet().size == matchedFields.size) {
            "chat session search matched_fields entries must be unique"
        }
    }
}

@Serializable
data class IndexDocumentsListRequestPayload(
    val limit: Int? = null,
) {
    init {
        require(limit == null || limit >= 0) {
            "index.documents.list request limit must be nonnegative"
        }
        require(limit == null || limit <= MAX_DOCUMENT_REQUEST_LIMIT) {
            "index.documents.list request limit must be at most 100"
        }
    }
}

@Serializable
data class IndexDocumentsListResultPayload(
    val documents: List<RuntimeDocumentIndexDocumentPayload>,
    val summary: IndexDocumentsSummaryPayload,
) {
    init {
        require(documents.size <= MAX_DOCUMENT_REQUEST_LIMIT) {
            "index.documents.list response documents must contain at most 100 items"
        }
    }
}

@Serializable
data class IndexDocumentsSummaryPayload(
    @SerialName("document_count") val documentCount: Int,
    @SerialName("chunk_count") val chunkCount: Int,
    @SerialName("extracted_character_count") val extractedCharacterCount: Int,
    @SerialName("quality_counts") val qualityCounts: IndexDocumentsQualityCountsPayload,
) {
    init {
        require(documentCount >= 0) {
            "index.documents.list summary document_count must be nonnegative"
        }
        require(chunkCount >= 0) {
            "index.documents.list summary chunk_count must be nonnegative"
        }
        require(extractedCharacterCount >= 0) {
            "index.documents.list summary extracted_character_count must be nonnegative"
        }
    }
}

@Serializable
data class IndexDocumentsQualityCountsPayload(
    @SerialName("no_usable_text") val noUsableText: Int,
    @SerialName("single_chunk") val singleChunk: Int,
    val chunked: Int,
) {
    init {
        require(noUsableText >= 0) {
            "index.documents.list summary quality_counts.no_usable_text must be nonnegative"
        }
        require(singleChunk >= 0) {
            "index.documents.list summary quality_counts.single_chunk must be nonnegative"
        }
        require(chunked >= 0) {
            "index.documents.list summary quality_counts.chunked must be nonnegative"
        }
    }
}

@Serializable
data class RetrievalQueryRequestPayload(
    val query: String,
    val limit: Int? = null,
    @SerialName("max_snippet_characters") val maxSnippetCharacters: Int? = null,
) {
    init {
        require(query.isNotBlank()) {
            "retrieval.query request query must be nonblank"
        }
        require(query.length <= MAX_RETRIEVAL_QUERY_LENGTH) {
            "retrieval.query request query must be at most 1024 characters"
        }
        require(limit == null || limit >= 0) {
            "retrieval.query request limit must be nonnegative"
        }
        require(limit == null || limit <= MAX_DOCUMENT_REQUEST_LIMIT) {
            "retrieval.query request limit must be at most 100"
        }
        require(maxSnippetCharacters == null || maxSnippetCharacters >= 0) {
            "retrieval.query request max_snippet_characters must be nonnegative"
        }
        require(maxSnippetCharacters == null || maxSnippetCharacters <= MAX_RETRIEVAL_SNIPPET_LENGTH) {
            "retrieval.query request max_snippet_characters must be at most 500"
        }
    }
}

@Serializable
data class RetrievalQueryResultPayload(
    val results: List<RetrievalQueryResultItemPayload>,
) {
    init {
        require(results.size <= MAX_DOCUMENT_REQUEST_LIMIT) {
            "retrieval.query response results must contain at most 100 items"
        }
    }
}

@Serializable
data class RetrievalQueryResultItemPayload(
    val document: RuntimeDocumentIndexDocumentPayload,
    @SerialName("chunk_index") val chunkIndex: Int,
    @SerialName("start_character_offset") val startCharacterOffset: Int,
    @SerialName("end_character_offset") val endCharacterOffset: Int,
    val rank: Int,
    @SerialName("matched_terms") val matchedTerms: List<String>,
    val snippet: String,
    @Serializable(with = SourceAnchorIdSerializer::class)
    @SerialName("source_anchor_id") val sourceAnchorId: String,
) {
    init {
        require(chunkIndex >= 0) {
            "retrieval.query result chunk_index must be nonnegative"
        }
        require(startCharacterOffset >= 0) {
            "retrieval.query result start_character_offset must be nonnegative"
        }
        require(endCharacterOffset >= 0) {
            "retrieval.query result end_character_offset must be nonnegative"
        }
        require(endCharacterOffset >= startCharacterOffset) {
            "retrieval.query result end_character_offset must be greater than or equal to start_character_offset"
        }
        require(rank >= 1) {
            "retrieval.query result rank must be positive"
        }
        require(matchedTerms.isNotEmpty()) {
            "retrieval.query result matched_terms must be nonempty"
        }
        require(matchedTerms.size <= MAX_RETRIEVAL_MATCHED_TERMS) {
            "retrieval.query result matched_terms must contain at most 16 terms"
        }
        require(matchedTerms.all { it.isNotEmpty() }) {
            "retrieval.query result matched_terms entries must be nonempty"
        }
        require(matchedTerms.all { it.length <= MAX_RETRIEVAL_MATCHED_TERM_LENGTH }) {
            "retrieval.query result matched_terms entries must be at most 64 characters"
        }
        require(snippet.isNotEmpty()) {
            "retrieval.query result snippet must be nonempty"
        }
        require(snippet.length <= MAX_RETRIEVAL_SNIPPET_LENGTH) {
            "retrieval.query result snippet must be at most 500 characters"
        }
    }
}

@Serializable
data class SourceAnchorResolveRequestPayload(
    @Serializable(with = SourceAnchorIdSerializer::class)
    @SerialName("source_anchor_id") val sourceAnchorId: String,
)

@Serializable
data class SourceAnchorResolveResultPayload(
    @Serializable(with = SourceAnchorIdSerializer::class)
    @SerialName("source_anchor_id") val sourceAnchorId: String,
    val document: RuntimeDocumentIndexDocumentPayload,
    @SerialName("chunk_summary") val chunkSummary: SourceAnchorChunkSummaryPayload,
)

@Serializable
data class SourceAnchorChunkSummaryPayload(
    @SerialName("chunk_index") val chunkIndex: Int,
    @SerialName("start_character_offset") val startCharacterOffset: Int,
    @SerialName("end_character_offset") val endCharacterOffset: Int,
    @SerialName("character_count") val characterCount: Int,
) {
    init {
        require(chunkIndex >= 0) {
            "chunk_summary.chunk_index must be nonnegative"
        }
        require(startCharacterOffset >= 0) {
            "chunk_summary.start_character_offset must be nonnegative"
        }
        require(endCharacterOffset >= 0) {
            "chunk_summary.end_character_offset must be nonnegative"
        }
        require(characterCount >= 0) {
            "chunk_summary.character_count must be nonnegative"
        }
        require(endCharacterOffset >= startCharacterOffset) {
            "chunk_summary.end_character_offset must be greater than or equal to start_character_offset"
        }
    }
}

@Serializable
data class RuntimeDocumentIndexDocumentPayload(
    val id: String,
    @SerialName("display_name") val displayName: String,
    @SerialName("mime_type") val mimeType: String,
    @Serializable(with = DocumentContentFingerprintSerializer::class)
    @SerialName("content_fingerprint") val contentFingerprint: String,
    @SerialName("extracted_character_count") val extractedCharacterCount: Int,
    @SerialName("chunk_count") val chunkCount: Int,
    val quality: String,
) {
    init {
        require(id.isNotEmpty()) {
            "index document id must be nonempty"
        }
        require(id.length <= MAX_DOCUMENT_ID_LENGTH) {
            "index document id must be at most 128 characters"
        }
        require(displayName.isNotEmpty()) {
            "index document display_name must be nonempty"
        }
        require(displayName.length <= MAX_DOCUMENT_DISPLAY_NAME_LENGTH) {
            "index document display_name must be at most 256 characters"
        }
        require(mimeType.isNotEmpty()) {
            "index document mime_type must be nonempty"
        }
        require(mimeType.length <= MAX_DOCUMENT_MIME_TYPE_LENGTH) {
            "index document mime_type must be at most 128 characters"
        }
        require(DOCUMENT_MIME_TYPE_PATTERN.matches(mimeType)) {
            "index document mime_type must match lowercase type/subtype"
        }
        require(extractedCharacterCount >= 0) {
            "index document extracted_character_count must be nonnegative"
        }
        require(chunkCount >= 0) {
            "index document chunk_count must be nonnegative"
        }
        require(quality in DOCUMENT_QUALITIES) {
            "index document quality must be no_usable_text, single_chunk, or chunked"
        }
        val expectedQuality = when {
            chunkCount == 0 -> "no_usable_text"
            chunkCount == 1 -> "single_chunk"
            else -> "chunked"
        }
        require(quality == expectedQuality) {
            "index document quality must match chunk_count"
        }
    }
}

@Serializable
data class ChatMessagesListRequestPayload(
    @SerialName("session_id") val sessionId: String,
    val limit: Int? = null,
) {
    init {
        require(sessionId.isNotBlank()) {
            "chat.messages.list request session_id must be nonblank"
        }
        require(limit == null || limit >= 0) {
            "chat.messages.list request limit must be nonnegative"
        }
        require(limit == null || limit <= MAX_CHAT_MESSAGES_LIST_LIMIT) {
            "chat.messages.list request limit must be at most 500"
        }
    }
}

@Serializable
data class ChatMessagesListResultPayload(
    @SerialName("session_id") val sessionId: String,
    val messages: List<ChatStoredMessagePayload>,
)

@Serializable
data class ChatStoredMessagePayload(
    val role: String,
    val content: String,
    val reasoning: String? = null,
    val attachments: List<ChatStoredAttachmentPayload> = emptyList(),
    @SerialName("created_at") val createdAt: String? = null,
) {
    init {
        requireProtocolDateTime(createdAt, "chat.messages.list response created_at")
    }
}

@Serializable
data class ChatTitleRequestPayload(
    @SerialName("session_id") val sessionId: String,
    val model: String,
    val messages: List<ChatMessagePayload>,
    val locale: String? = null,
) {
    init {
        require(sessionId.isNotBlank()) {
            "chat.title.request session_id must be nonblank"
        }
        require(model.isNotBlank()) {
            "chat.title.request model must be nonblank"
        }
        require(messages.isNotEmpty()) {
            "chat.title.request messages must be nonempty"
        }
    }
}

@Serializable
data class ChatTitleResultPayload(
    val title: String,
)

@Serializable
data class ChatSessionRenamePayload(
    @SerialName("session_id") val sessionId: String,
    val title: String,
    @SerialName("renamed_at") val renamedAt: String? = null,
) {
    init {
        require(sessionId.isNotBlank()) {
            "chat.session.rename session_id must be nonblank"
        }
        require(title.isNotBlank()) {
            "chat.session.rename title must be nonblank"
        }
        requireProtocolDateTime(renamedAt, "chat.session.rename renamed_at")
    }
}

@Serializable
data class ChatSessionLifecyclePayload(
    @SerialName("session_id") val sessionId: String,
    val status: String? = null,
    @SerialName("archived_at") val archivedAt: String? = null,
    @SerialName("restored_at") val restoredAt: String? = null,
    @SerialName("deleted_at") val deletedAt: String? = null,
) {
    init {
        require(sessionId.isNotBlank()) {
            "chat.session lifecycle session_id must be nonblank"
        }
        requireProtocolDateTime(archivedAt, "chat.session lifecycle archived_at")
        requireProtocolDateTime(restoredAt, "chat.session lifecycle restored_at")
        requireProtocolDateTime(deletedAt, "chat.session lifecycle deleted_at")
    }
}

@Serializable
data class MemoryListRequestPayload(
    val query: String? = null,
) {
    init {
        require(query == null || query.isNotEmpty()) {
            "memory.list request query must be nonempty"
        }
    }
}

@Serializable
data class MemoryListResultPayload(
    val entries: List<MemoryEntryPayload>,
)

@Serializable
data class MemoryEntryPayload(
    val id: String,
    val content: String,
    val enabled: Boolean = true,
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("updated_at") val updatedAt: String? = null,
    val source: MemoryEntrySourcePayload? = null,
    val search: ChatSessionSearchPayload? = null,
) {
    init {
        require(id.isNotEmpty()) {
            "memory entry id must be nonempty"
        }
        require(content.isNotEmpty()) {
            "memory entry content must be nonempty"
        }
        requireProtocolDateTime(createdAt, "memory entry created_at")
        requireProtocolDateTime(updatedAt, "memory entry updated_at")
    }
}

@Serializable
data class MemoryEntrySourcePayload(
    val kind: String,
    @SerialName("draft_id") val draftId: String,
    @SerialName("summary_method") val summaryMethod: String,
    val session: MemorySummaryDraftSessionPayload,
    @SerialName("source_message_count") val sourceMessageCount: Int,
    @SerialName("source_range") val sourceRange: String,
    @SerialName("source_pointers") val sourcePointers: List<MemorySummaryDraftSourcePointerPayload>,
) {
    init {
        require(kind == MEMORY_ENTRY_SOURCE_KIND) {
            "memory entry source kind must be long_inactivity_summary_draft"
        }
        require(draftId.isNotEmpty()) {
            "memory entry source draft_id must be nonempty"
        }
        require(summaryMethod == MEMORY_ENTRY_SOURCE_SUMMARY_METHOD) {
            "memory entry source summary_method must be deterministic_preview"
        }
        require(sourceMessageCount > 0) {
            "memory entry source source_message_count must be positive"
        }
        require(sourceRange.isNotEmpty()) {
            "memory entry source source_range must be nonempty"
        }
        require(sourcePointers.isNotEmpty()) {
            "memory entry source source_pointers must be nonempty"
        }
    }
}

@Serializable
data class MemoryUpsertPayload(
    val id: String? = null,
    val content: String,
    val enabled: Boolean? = null,
) {
    init {
        require(id == null || id.isNotBlank()) {
            "memory.upsert request id must be nonblank"
        }
        require(content.isNotBlank()) {
            "memory.upsert request content must be nonblank"
        }
    }
}

@Serializable
data class MemoryUpsertResultPayload(
    val entry: MemoryEntryPayload,
)

@Serializable
data class MemoryDeletePayload(
    val id: String,
) {
    init {
        require(id.isNotBlank()) {
            "memory.delete request id must be nonblank"
        }
    }
}

@Serializable
data class MemoryDeleteResultPayload(
    val id: String,
    @SerialName("deleted_at") val deletedAt: String? = null,
) {
    init {
        requireProtocolDateTime(deletedAt, "memory.delete result deleted_at")
    }
}

@Serializable
data class MemorySummaryDraftsListRequestPayload(
    val limit: Int? = null,
) {
    init {
        require(limit == null || limit >= 0) {
            "memory.summary.drafts.list request limit must be nonnegative"
        }
        require(limit == null || limit <= MAX_MEMORY_SUMMARY_DRAFTS_LIST_LIMIT) {
            "memory.summary.drafts.list request limit must be at most 50"
        }
    }
}

@Serializable
data class MemorySummaryDraftsListResultPayload(
    val drafts: List<MemorySummaryDraftPayload>,
)

@Serializable
data class MemorySummaryDraftApprovePayload(
    @SerialName("draft_id") val draftId: String,
    val content: String? = null,
    val enabled: Boolean? = null,
    @SerialName("expected_session_id") val expectedSessionId: String? = null,
    @SerialName("expected_source_message_count") val expectedSourceMessageCount: Int? = null,
) {
    init {
        require(draftId.isNotBlank()) {
            "memory.summary.draft.approve request draft_id must be nonblank"
        }
        require(content == null || content.isNotBlank()) {
            "memory.summary.draft.approve request content must be nonblank"
        }
        require(expectedSessionId == null || expectedSessionId.isNotBlank()) {
            "memory.summary.draft.approve request expected_session_id must be nonblank"
        }
        require(expectedSourceMessageCount == null || expectedSourceMessageCount > 0) {
            "memory.summary.draft.approve request expected_source_message_count must be positive"
        }
    }
}

@Serializable
data class MemorySummaryDraftApproveResultPayload(
    @SerialName("draft_id") val draftId: String,
    val status: String,
    val entry: MemoryEntryPayload,
)

@Serializable
data class MemorySummaryDraftDismissPayload(
    @SerialName("draft_id") val draftId: String,
    @SerialName("expected_session_id") val expectedSessionId: String? = null,
    @SerialName("expected_source_message_count") val expectedSourceMessageCount: Int? = null,
) {
    init {
        require(draftId.isNotBlank()) {
            "memory.summary.draft.dismiss request draft_id must be nonblank"
        }
        require(expectedSessionId == null || expectedSessionId.isNotBlank()) {
            "memory.summary.draft.dismiss request expected_session_id must be nonblank"
        }
        require(expectedSourceMessageCount == null || expectedSourceMessageCount > 0) {
            "memory.summary.draft.dismiss request expected_source_message_count must be positive"
        }
    }
}

@Serializable
data class MemorySummaryDraftDismissResultPayload(
    @SerialName("draft_id") val draftId: String,
    val status: String,
    @SerialName("dismissed_at") val dismissedAt: String? = null,
) {
    init {
        requireProtocolDateTime(dismissedAt, "memory.summary.draft.dismiss result dismissed_at")
    }
}

@Serializable
data class MemorySummaryDraftPayload(
    val id: String,
    val session: MemorySummaryDraftSessionPayload,
    @SerialName("source_message_count") val sourceMessageCount: Int,
    @SerialName("source_range") val sourceRange: String,
    @SerialName("source_pointers") val sourcePointers: List<MemorySummaryDraftSourcePointerPayload>,
    @SerialName("summary_preview") val summaryPreview: String,
) {
    init {
        require(id.isNotEmpty()) {
            "memory summary draft id must be nonempty"
        }
        require(sourceMessageCount > 0) {
            "memory summary draft source_message_count must be positive"
        }
        require(sourceRange.isNotEmpty()) {
            "memory summary draft source_range must be nonempty"
        }
        require(sourcePointers.isNotEmpty()) {
            "memory summary draft source_pointers must be nonempty"
        }
        require(summaryPreview.isNotEmpty()) {
            "memory summary draft summary_preview must be nonempty"
        }
    }
}

@Serializable
data class MemorySummaryDraftSessionPayload(
    @SerialName("session_id") val sessionId: String,
    val title: String,
    val model: String,
    @SerialName("last_activity_at") val lastActivityAt: String,
    @SerialName("message_count") val messageCount: Int,
    @SerialName("inactive_seconds") val inactiveSeconds: Long,
) {
    init {
        require(sessionId.isNotEmpty()) {
            "memory summary draft session_id must be nonempty"
        }
        require(messageCount >= 0) {
            "memory summary draft message_count must be nonnegative"
        }
        require(inactiveSeconds >= 0) {
            "memory summary draft inactive_seconds must be nonnegative"
        }
        requireProtocolDateTime(lastActivityAt, "memory summary draft session last_activity_at")
    }
}

@Serializable
data class MemorySummaryDraftSourcePointerPayload(
    @SerialName("session_id") val sessionId: String,
    @SerialName("message_index") val messageIndex: Int,
    val role: String,
    @SerialName("created_at") val createdAt: String? = null,
    val excerpt: String,
) {
    init {
        require(sessionId.isNotEmpty()) {
            "memory summary draft source pointer session_id must be nonempty"
        }
        require(messageIndex > 0) {
            "memory summary draft source pointer message_index must be positive"
        }
        require(role in MEMORY_SUMMARY_SOURCE_POINTER_ROLES) {
            "memory summary draft source pointer role must be user or assistant"
        }
        require(excerpt.isNotEmpty()) {
            "memory summary draft source pointer excerpt must be nonempty"
        }
        requireProtocolDateTime(createdAt, "memory summary draft source pointer created_at")
    }
}

@Serializable
data class ErrorPayload(
    val code: String,
    val message: String,
    val retryable: Boolean,
) {
    init {
        require(code in ERROR_CODES) {
            "error payload code must be a known protocol error code"
        }
    }
}

@Serializable
data class RuntimeHealthPayload(
    val status: String,
    val ollama: RuntimeBackendStatusPayload? = null,
    @SerialName("lm_studio") val lmStudio: RuntimeBackendStatusPayload? = null,
    @SerialName("model_residency") val modelResidency: RuntimeModelResidencyPayload? = null,
) {
    init {
        require(status in RUNTIME_HEALTH_STATUSES) {
            "runtime.health status must be ok, degraded, or unavailable"
        }
    }
}

@Serializable
data class RuntimeBackendStatusPayload(
    val available: Boolean,
    val message: String? = null,
    val code: String? = null,
    val retryable: Boolean? = null,
)

@Serializable
data class RuntimeModelResidencyPayload(
    val supported: Boolean,
    @SerialName("active_provider") val activeProvider: String? = null,
    @SerialName("active_model_id") val activeModelId: String? = null,
    @SerialName("in_flight_generations") val inFlightGenerations: Int = 0,
    @SerialName("idle_unload_delay_seconds") val idleUnloadDelaySeconds: Int? = null,
    @SerialName("last_unload_failure") val lastUnloadFailure: RuntimeModelResidencyUnloadFailurePayload? = null,
) {
    init {
        require(inFlightGenerations >= 0) {
            "runtime.health model_residency in_flight_generations must be nonnegative"
        }
        require(idleUnloadDelaySeconds == null || idleUnloadDelaySeconds >= 0) {
            "runtime.health model_residency idle_unload_delay_seconds must be nonnegative"
        }
    }
}

@Serializable
data class RuntimeModelResidencyUnloadFailurePayload(
    val provider: String,
    @SerialName("model_id") val modelId: String,
    val reason: String,
)
