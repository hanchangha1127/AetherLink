package com.localagentbridge.android.core.protocol

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.KSerializer
import kotlinx.serialization.EncodeDefault
import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.descriptors.PrimitiveKind
import kotlinx.serialization.descriptors.PrimitiveSerialDescriptor
import kotlinx.serialization.descriptors.SerialDescriptor
import kotlinx.serialization.encoding.Decoder
import kotlinx.serialization.encoding.Encoder
import kotlinx.serialization.json.JsonDecoder
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonEncoder
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.encodeToJsonElement
import kotlinx.serialization.json.jsonObject
import java.time.Instant
import java.util.UUID

const val PROTOCOL_VERSION = 1
const val PAIRING_PROOF_SCHEME_P256_SHA256_DER_V1 = "p256-sha256-der-v1"
const val RELAY_ALLOCATION_PROOF_SCHEME = "runtime-client-p256-v2"
const val RELAY_ALLOCATION_PROTOCOL_VERSION = 2
const val CHAT_SOURCE_ATTRIBUTIONS_CAPABILITY = "chat.source_attributions.v1"
const val CHAT_SOURCE_ATTRIBUTION_RESOLVE_CAPABILITY = "chat.source_attribution.resolve.v1"
const val CHAT_SESSIONS_SYNC_CAPABILITY = "chat.sessions.authoritative_sync.v1"
const val RESEARCH_NOTEBOOKS_CAPABILITY = "research.notebooks.v1"
const val RESEARCH_NOTEBOOKS_AUTHORITATIVE_SYNC_CAPABILITY =
    "research.notebooks.authoritative_sync.v1"
const val MEMORY_DUPLICATE_SUGGESTIONS_CAPABILITY = "memory.duplicate_suggestions.v1"
const val MEMORY_SEMANTIC_DUPLICATE_SUGGESTIONS_CAPABILITY = "memory.semantic_duplicate_suggestions.v1"
const val MEMORY_SEMANTIC_DUPLICATE_CLUSTERS_CAPABILITY = "memory.semantic_duplicate_clusters.v1"

private val SOURCE_ANCHOR_ID_PATTERN = Regex("^source_anchor_[0-9a-f]{16}$")
private val CITATION_ID_PATTERN = Regex("^citation_[0-9a-f]{32}$")
private val ASSISTANT_MESSAGE_ID_PATTERN = Regex("^assistant_message_[0-9a-f]{32}$")
private val SOURCE_REVIEW_ID_PATTERN = Regex("^source_review_[0-9a-f]{32}$")
private val SOURCE_CONFIRMATION_TOKEN_PATTERN = Regex("^source_confirmation_[0-9a-f]{64}$")
private val TRUSTED_SOURCE_GRANT_ID_PATTERN = Regex("^trusted_source_[0-9a-f]{32}$")
private val RESEARCH_NOTEBOOK_ID_PATTERN = Regex("^research_notebook_[0-9a-f]{32}$")
private val RESEARCH_NOTEBOOK_CURSOR_PATTERN = Regex("^[A-Za-z0-9._-]+$")
private val DOCUMENT_CONTENT_FINGERPRINT_PATTERN = Regex("^[0-9a-f]{16}$")
private val LOWERCASE_HEX_64_PATTERN = Regex("^[0-9a-f]{64}$")
private val RUNTIME_KEY_BOUND_RELAY_ID_PATTERN = Regex("^rt2-[0-9a-f]{64}$")
private val CANONICAL_BASE64_PATTERN = Regex("^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$")
private val DOCUMENT_MIME_TYPE_PATTERN = Regex("^[a-z0-9!#\$%&'*+.^_`|~-]+/[a-z0-9!#\$%&'*+.^_`|~-]+$")
private val JSON_INTEGER_PATTERN = Regex("^-?(?:0|[1-9][0-9]*)$")
private val RFC3339_DATE_TIME_PATTERN = Regex(
    "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,9})?(?:Z|[+-]\\d{2}:\\d{2})$",
)
private const val MAX_CHAT_SESSION_LIST_LIMIT = 200
private const val MAX_CHAT_SESSION_CURSOR_BYTES = 512
private const val MAX_CHAT_SESSION_SNAPSHOT_COUNT = 10_000
private const val MAX_CHAT_MESSAGES_LIST_LIMIT = 500
private const val MAX_MEMORY_SUMMARY_DRAFTS_LIST_LIMIT = 50
private const val MAX_MEMORY_DUPLICATE_SUGGESTION_ID_AGGREGATE_UTF8_BYTES = 128 * 1024
private const val MAX_MEMORY_DUPLICATE_SUGGESTION_GROUPS = 100
private const val MAX_MEMORY_DUPLICATE_SUGGESTION_GROUP_SIZE = 200
private const val MAX_MEMORY_DUPLICATE_SUGGESTION_SCANNED_COUNT = 200
private const val MAX_MEMORY_SEMANTIC_DUPLICATE_SUGGESTION_EMBEDDING_MODEL_ID_LENGTH = 256
private const val MAX_MEMORY_SEMANTIC_DUPLICATE_SUGGESTION_PAIRS = 100
private const val MAX_MEMORY_SEMANTIC_DUPLICATE_SUGGESTION_SCANNED_COUNT = 200
private const val MAX_MEMORY_SEMANTIC_DUPLICATE_SUGGESTION_ID_AGGREGATE_UTF8_BYTES = 128 * 1024
private const val MAX_MEMORY_SEMANTIC_DUPLICATE_CLUSTERS = 100
private const val MAX_MEMORY_SEMANTIC_DUPLICATE_CLUSTER_SIZE = 200
private const val MAX_MEMORY_SEMANTIC_DUPLICATE_CLUSTER_SCANNED_COUNT = 200
private const val MAX_MEMORY_SEMANTIC_DUPLICATE_CLUSTER_ID_AGGREGATE_UTF8_BYTES = 128 * 1024
private const val MAX_DOCUMENT_REQUEST_LIMIT = 100
private const val MAX_TRUSTED_SOURCE_GRANT_IDS = 8
private const val MAX_CHAT_SOURCE_ATTRIBUTIONS = 8
private const val MAX_CLIENT_CAPABILITIES = 64
private const val DEFAULT_RESEARCH_NOTEBOOK_LIST_LIMIT = 100
private const val MAX_RESEARCH_NOTEBOOK_LIST_LIMIT = 200
private const val MAX_RESEARCH_NOTEBOOK_CURSOR_BYTES = 512
private const val MAX_RESEARCH_NOTEBOOK_SNAPSHOT_COUNT = 10_000
private const val MAX_RESEARCH_SESSION_ID_BYTES = 256
private const val MAX_RESEARCH_MODEL_BYTES = 256
private const val MAX_RESEARCH_LOCALE_BYTES = 64
private const val MAX_RESEARCH_TOPIC_CHARACTERS = 2048
private const val MAX_RESEARCH_TOPIC_BYTES = 8192
private const val MAX_RESEARCH_NOTEBOOK_TITLE_CHARACTERS = 256
private const val MAX_RESEARCH_NOTEBOOK_TITLE_BYTES = 1024
private const val TRUSTED_SOURCE_DISCLOSURE_VERSION = "runtime-trusted-source-v1"
private const val TRUSTED_SOURCE_USAGE_SCOPE = "chat_context"
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
private val CHAT_SESSIONS_BULK_LIFECYCLE_STATUS_BY_SCOPE = mapOf(
    "all_active" to "archived",
    "all_archived" to "deleted",
)
private val CHAT_SESSION_LAST_EVENTS = setOf(
    "request",
    "assistant_delta",
    "reasoning_delta",
    "done",
    "cancelled",
    "error",
)

fun isCanonicalProviderQualifiedModelId(modelId: String): Boolean {
    val separatorIndex = modelId.indexOf(':')
    if (separatorIndex <= 0 || separatorIndex == modelId.lastIndex) return false
    val provider = modelId.substring(0, separatorIndex)
    val providerModelId = modelId.substring(separatorIndex + 1)
    return provider in MODEL_INFO_PROVIDERS && providerModelId.isNotBlank()
}

private val CANONICAL_UNSIGNED_UTF8_STRING_COMPARATOR = Comparator<String> { left, right ->
    val leftBytes = left.toByteArray(Charsets.UTF_8)
    val rightBytes = right.toByteArray(Charsets.UTF_8)
    val sharedLength = minOf(leftBytes.size, rightBytes.size)
    for (index in 0 until sharedLength) {
        val comparison = (leftBytes[index].toInt() and 0xff) - (rightBytes[index].toInt() and 0xff)
        if (comparison != 0) return@Comparator comparison
    }
    leftBytes.size - rightBytes.size
}

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
    "chat_context_window_exceeded",
    "document_index_unavailable",
    "source_anchor_not_found",
    "citation_not_found",
    "chat_source_attribution_not_found",
    "trusted_source_review_not_found",
    "trusted_source_review_expired",
    "trusted_source_review_stale",
    "trusted_source_not_found",
    "research_notebook_store_unavailable",
    "memory_store_unavailable",
    "memory_summary_draft_unavailable",
    "memory_summary_draft_stale",
    "memory_summary_draft_generation_failed",
    "transport_error",
    "internal_error",
)
private const val MEMORY_ENTRY_SOURCE_KIND = "long_inactivity_summary_draft"
private const val MEMORY_ENTRY_SOURCE_SUMMARY_METHOD = "deterministic_preview"
private val MEMORY_SUMMARY_DRAFT_METHODS = setOf("deterministic_preview", "llm_summary_v1")
private val MEMORY_SUMMARY_SOURCE_POINTER_ROLES = setOf("user", "assistant")

private fun requireProtocolDateTime(value: String?, fieldName: String) {
    if (value == null) return
    try {
        Instant.parse(value)
    } catch (error: Exception) {
        throw IllegalArgumentException("$fieldName must be date-time", error)
    }
}

private fun requireExactRfc3339DateTime(value: String, fieldName: String) {
    require(RFC3339_DATE_TIME_PATTERN.matches(value)) {
        "$fieldName must be RFC3339 date-time"
    }
    try {
        Instant.parse(value)
    } catch (error: Exception) {
        throw IllegalArgumentException("$fieldName must be RFC3339 date-time", error)
    }
}

private fun requireValidUtf8(value: String, fieldName: String) {
    require(Charsets.UTF_8.newEncoder().canEncode(value)) {
        "$fieldName must be valid UTF-8 encodable Unicode"
    }
}

private fun requireResearchNotebookCursor(value: String, fieldName: String) {
    requireValidUtf8(value, fieldName)
    require(value.toByteArray(Charsets.UTF_8).size in 1..MAX_RESEARCH_NOTEBOOK_CURSOR_BYTES) {
        "$fieldName must contain 1 to 512 UTF-8 bytes"
    }
    require(RESEARCH_NOTEBOOK_CURSOR_PATTERN.matches(value)) {
        "$fieldName must match ^[A-Za-z0-9._-]+$"
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

private fun Decoder.decodeExactJsonObject(
    expectedFields: Set<String>,
    payloadName: String = "relay allocation payload",
): Pair<JsonDecoder, JsonObject> {
    val jsonDecoder = this as? JsonDecoder
        ?: throw IllegalArgumentException("$payloadName requires JSON decoding")
    val payload = jsonDecoder.decodeJsonElement() as? JsonObject
        ?: throw IllegalArgumentException("$payloadName must be a JSON object")
    val unknownFields = payload.keys.filterNot { it in expectedFields }.sorted()
    require(unknownFields.isEmpty()) {
        "$payloadName contains unknown field: ${unknownFields.first()}"
    }
    return jsonDecoder to payload
}

private abstract class ExactJsonObjectTransformingSerializer<T, S>(
    private val surrogateSerializer: KSerializer<S>,
    private val expectedFields: Set<String>,
    private val payloadName: String,
    private val validatePayload: (JsonObject) -> Unit = {},
) : KSerializer<T> {
    override val descriptor: SerialDescriptor = surrogateSerializer.descriptor

    final override fun deserialize(decoder: Decoder): T {
        val (jsonDecoder, payload) = decoder.decodeExactJsonObject(expectedFields, payloadName)
        validatePayload(payload)
        return fromSurrogate(jsonDecoder.json.decodeFromJsonElement(surrogateSerializer, payload))
    }

    final override fun serialize(encoder: Encoder, value: T) {
        encoder.encodeSerializableValue(surrogateSerializer, toSurrogate(value))
    }

    protected abstract fun fromSurrogate(value: S): T

    protected abstract fun toSurrogate(value: T): S
}

private fun JsonObject.requireExactNestedJsonObject(
    fieldName: String,
    expectedFields: Set<String>,
    objectName: String,
) {
    val nested = this[fieldName] as? JsonObject
        ?: throw IllegalArgumentException("$objectName must be a JSON object")
    val unknownFields = nested.keys.filterNot { it in expectedFields }.sorted()
    require(unknownFields.isEmpty()) {
        "$objectName contains unknown field: ${unknownFields.first()}"
    }
}

private fun JsonObject.requireJsonInteger(fieldName: String, payloadName: String) {
    val value = this[fieldName] as? JsonPrimitive
    require(value != null && !value.isString && JSON_INTEGER_PATTERN.matches(value.content)) {
        "$payloadName $fieldName must be an integer"
    }
}

private fun JsonObject.requireJsonBoolean(fieldName: String, payloadName: String) {
    val value = this[fieldName] as? JsonPrimitive
    require(value != null && !value.isString && value.content in setOf("true", "false")) {
        "$payloadName $fieldName must be a boolean"
    }
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
    const val ChatSourceAttributionResolve = "chat.source_attribution.resolve"
    const val ResearchBriefCreate = "research.brief.create"
    const val ResearchNotebooksList = "research.notebooks.list"
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
    const val CitationResolve = "citation.resolve"
    const val TrustedSourceApprove = "trusted_source.approve"
    const val TrustedSourceDismiss = "trusted_source.dismiss"
    const val TrustedSourceList = "trusted_source.list"
    const val TrustedSourceRevoke = "trusted_source.revoke"
    const val MemoryList = "memory.list"
    const val MemoryDuplicateSuggestionsList = "memory.duplicate_suggestions.list"
    const val MemorySemanticDuplicateSuggestionsList = "memory.semantic_duplicate_suggestions.list"
    const val MemorySemanticDuplicateClustersList = "memory.semantic_duplicate_clusters.list"
    const val MemoryUpsert = "memory.upsert"
    const val MemoryDelete = "memory.delete"
    const val MemorySummaryDraftsList = "memory.summary.drafts.list"
    const val MemorySummaryDraftGenerate = "memory.summary.draft.generate"
    const val MemorySummaryDraftApprove = "memory.summary.draft.approve"
    const val MemorySummaryDraftDismiss = "memory.summary.draft.dismiss"
    const val Error = "error"
}

@Serializable
data class HelloPayload(
    @SerialName("device_id") val deviceId: String,
    @SerialName("device_name") val deviceName: String,
    @SerialName("client_capabilities")
    val capabilities: List<String> = emptyList(),
    @SerialName("transport_binding") val transportBinding: String? = null,
) {
    init {
        require(capabilities.size <= MAX_CLIENT_CAPABILITIES) {
            "hello request client_capabilities must contain at most 64 entries"
        }
        capabilities.forEach { capability ->
            requireValidUtf8(capability, "hello request client_capabilities entry")
            require(capability.isNotBlank()) {
                "hello request client_capabilities entries must be nonblank"
            }
        }
        require(capabilities.distinct().size == capabilities.size) {
            "hello request client_capabilities entries must be unique"
        }
    }
}

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
private data class ChatSendPayloadSurrogate(
    @SerialName("session_id") val sessionId: String,
    val model: String,
    val messages: List<ChatMessagePayload>,
    val locale: String? = null,
    @SerialName("trusted_source_grant_ids") val trustedSourceGrantIds: List<String> = emptyList(),
)

object ChatSendPayloadSerializer : KSerializer<ChatSendPayload> {
    private val surrogateSerializer = ChatSendPayloadSurrogate.serializer()
    override val descriptor: SerialDescriptor = surrogateSerializer.descriptor

    override fun deserialize(decoder: Decoder): ChatSendPayload {
        val (jsonDecoder, payload) = decoder.decodeExactJsonObject(
            setOf("session_id", "model", "messages", "locale", "trusted_source_grant_ids"),
            "chat.send request",
        )
        payload["trusted_source_grant_ids"]?.let { grants ->
            require(grants is JsonArray && grants.isNotEmpty()) {
                "chat.send request trusted_source_grant_ids must be a nonempty array when present"
            }
        }
        val value = jsonDecoder.json.decodeFromJsonElement(surrogateSerializer, payload)
        return ChatSendPayload(
            sessionId = value.sessionId,
            model = value.model,
            messages = value.messages,
            locale = value.locale,
            trustedSourceGrantIds = value.trustedSourceGrantIds,
        )
    }

    override fun serialize(encoder: Encoder, value: ChatSendPayload) {
        val jsonEncoder = encoder as? JsonEncoder
            ?: throw IllegalArgumentException("chat.send request requires JSON encoding")
        val surrogate = ChatSendPayloadSurrogate(
            sessionId = value.sessionId,
            model = value.model,
            messages = value.messages,
            locale = value.locale,
            trustedSourceGrantIds = value.trustedSourceGrantIds,
        )
        val payload = jsonEncoder.json.encodeToJsonElement(surrogateSerializer, surrogate).jsonObject
        jsonEncoder.encodeJsonElement(
            if (value.trustedSourceGrantIds.isEmpty()) {
                JsonObject(payload - "trusted_source_grant_ids")
            } else {
                payload
            }
        )
    }
}

@Serializable(with = ChatSendPayloadSerializer::class)
data class ChatSendPayload(
    @SerialName("session_id") val sessionId: String,
    val model: String,
    val messages: List<ChatMessagePayload>,
    val locale: String? = null,
    @SerialName("trusted_source_grant_ids") val trustedSourceGrantIds: List<String> = emptyList(),
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
        require(trustedSourceGrantIds.size <= MAX_TRUSTED_SOURCE_GRANT_IDS) {
            "chat.send request trusted_source_grant_ids must contain at most 8 entries"
        }
        require(trustedSourceGrantIds.distinct().size == trustedSourceGrantIds.size) {
            "chat.send request trusted_source_grant_ids must contain unique entries"
        }
        require(trustedSourceGrantIds.all(TRUSTED_SOURCE_GRANT_ID_PATTERN::matches)) {
            "chat.send request trusted_source_grant_ids entries must match trusted_source_[32 lowercase hex]"
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
    @OptIn(ExperimentalSerializationApi::class)
    @EncodeDefault(EncodeDefault.Mode.NEVER)
    @Serializable(with = NonEmptyChatSourceAttributionsSerializer::class)
    @SerialName("source_attributions")
    val sourceAttributions: List<ChatSourceAttributionPayload> = emptyList(),
    @OptIn(ExperimentalSerializationApi::class)
    @EncodeDefault(EncodeDefault.Mode.NEVER)
    @SerialName("assistant_message_id")
    val assistantMessageId: String? = null,
) {
    init {
        require(finishReason == null || finishReason in CHAT_DONE_FINISH_REASONS) {
            "chat.done finish_reason must be stop, cancelled, or error"
        }
        require(sourceAttributions.isEmpty() || finishReason == "stop") {
            "chat.done source_attributions require finish_reason stop"
        }
        require(assistantMessageId == null || sourceAttributions.isNotEmpty()) {
            "chat.done assistant_message_id requires source_attributions"
        }
        requireAssistantMessageId(assistantMessageId, "chat.done assistant_message_id")
        requireCanonicalChatSourceAttributions(sourceAttributions, "chat.done source_attributions")
    }
}

@Serializable
private data class ChatSourceAttributionPayloadSurrogate(
    @SerialName("source_index") val sourceIndex: Int,
    @SerialName("document_name") val documentName: String,
    @SerialName("mime_type") val mimeType: String,
    @SerialName("chunk_index") val chunkIndex: Int,
)

object ChatSourceAttributionPayloadSerializer : KSerializer<ChatSourceAttributionPayload> by object :
    ExactJsonObjectTransformingSerializer<ChatSourceAttributionPayload, ChatSourceAttributionPayloadSurrogate>(
        ChatSourceAttributionPayloadSurrogate.serializer(),
        setOf("source_index", "document_name", "mime_type", "chunk_index"),
        "source attribution",
    ) {
    override fun fromSurrogate(value: ChatSourceAttributionPayloadSurrogate) = ChatSourceAttributionPayload(
        value.sourceIndex,
        value.documentName,
        value.mimeType,
        value.chunkIndex,
    )

    override fun toSurrogate(value: ChatSourceAttributionPayload) = ChatSourceAttributionPayloadSurrogate(
        value.sourceIndex,
        value.documentName,
        value.mimeType,
        value.chunkIndex,
    )
}

@Serializable(with = ChatSourceAttributionPayloadSerializer::class)
data class ChatSourceAttributionPayload(
    @SerialName("source_index") val sourceIndex: Int,
    @SerialName("document_name") val documentName: String,
    @SerialName("mime_type") val mimeType: String,
    @SerialName("chunk_index") val chunkIndex: Int,
) {
    init {
        require(sourceIndex in 1..MAX_CHAT_SOURCE_ATTRIBUTIONS) {
            "source attribution source_index must be between 1 and 8"
        }
        require(documentName.isNotBlank()) {
            "source attribution document_name must be nonblank"
        }
        require(documentName.codePointCount(0, documentName.length) <= MAX_DOCUMENT_DISPLAY_NAME_LENGTH) {
            "source attribution document_name must be at most 256 Unicode code points"
        }
        require(documentName.none { character ->
            character.code in 0x00..0x1F ||
                character.code in 0x7F..0x9F ||
                character == '/' ||
                character == '\\'
        }) {
            "source attribution document_name must not contain controls or path separators"
        }
        require(mimeType.length <= MAX_DOCUMENT_MIME_TYPE_LENGTH && DOCUMENT_MIME_TYPE_PATTERN.matches(mimeType)) {
            "source attribution mime_type must be canonical lowercase type/subtype and at most 128 characters"
        }
        require(chunkIndex >= 0) {
            "source attribution chunk_index must be nonnegative"
        }
    }
}

object NonEmptyChatSourceAttributionsSerializer : KSerializer<List<ChatSourceAttributionPayload>> {
    private val delegate = ListSerializer(ChatSourceAttributionPayload.serializer())

    override val descriptor: SerialDescriptor = delegate.descriptor

    override fun deserialize(decoder: Decoder): List<ChatSourceAttributionPayload> =
        decoder.decodeSerializableValue(delegate).also { value ->
            require(value.isNotEmpty()) {
                "source_attributions must contain between 1 and 8 entries when present"
            }
        }

    override fun serialize(encoder: Encoder, value: List<ChatSourceAttributionPayload>) {
        require(value.isNotEmpty()) {
            "source_attributions must contain between 1 and 8 entries when present"
        }
        encoder.encodeSerializableValue(delegate, value)
    }
}

private fun requireAssistantMessageId(value: String?, fieldName: String) {
    require(value == null || ASSISTANT_MESSAGE_ID_PATTERN.matches(value)) {
        "$fieldName must match assistant_message_[32 lowercase hex]"
    }
}

private fun requireCanonicalChatSourceAttributions(
    sourceAttributions: List<ChatSourceAttributionPayload>,
    fieldName: String,
) {
    require(sourceAttributions.size <= MAX_CHAT_SOURCE_ATTRIBUTIONS) {
        "$fieldName must contain at most 8 entries"
    }
    require(sourceAttributions.map(ChatSourceAttributionPayload::sourceIndex) == (1..sourceAttributions.size).toList()) {
        "$fieldName source_index must be contiguous and match array order"
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
private data class ChatSessionsListRequestPayloadSurrogate(
    val limit: Int? = null,
    @SerialName("include_archived") val includeArchived: Boolean = false,
    val query: String? = null,
    @SerialName("embedding_model_id") val embeddingModelId: String? = null,
    val cursor: String? = null,
)

object ChatSessionsListRequestPayloadSerializer : KSerializer<ChatSessionsListRequestPayload> {
    private val surrogateSerializer = ChatSessionsListRequestPayloadSurrogate.serializer()
    override val descriptor: SerialDescriptor = surrogateSerializer.descriptor

    override fun deserialize(decoder: Decoder): ChatSessionsListRequestPayload {
        val (jsonDecoder, payload) = decoder.decodeExactJsonObject(
            setOf("limit", "include_archived", "query", "embedding_model_id", "cursor"),
            "chat.sessions.list request",
        )
        val hasCursor = "cursor" in payload
        require(!hasCursor || payload.keys == setOf("cursor")) {
            "chat.sessions.list request cursor must not be combined with other fields"
        }
        val value = jsonDecoder.json.decodeFromJsonElement(surrogateSerializer, payload)
        require(!hasCursor || value.cursor != null) {
            "chat.sessions.list request cursor must be nonblank"
        }
        return ChatSessionsListRequestPayload(
            limit = value.limit,
            includeArchived = value.includeArchived,
            query = value.query,
            embeddingModelId = value.embeddingModelId,
            cursor = value.cursor,
        )
    }

    override fun serialize(encoder: Encoder, value: ChatSessionsListRequestPayload) {
        val surrogate = ChatSessionsListRequestPayloadSurrogate(
            limit = value.limit,
            includeArchived = value.includeArchived,
            query = value.query,
            embeddingModelId = value.embeddingModelId,
            cursor = value.cursor,
        )
        if (value.cursor == null) {
            encoder.encodeSerializableValue(surrogateSerializer, surrogate)
            return
        }
        val jsonEncoder = encoder as? JsonEncoder
            ?: throw IllegalArgumentException("chat.sessions.list request cursor requires JSON encoding")
        val payload = jsonEncoder.json.encodeToJsonElement(surrogateSerializer, surrogate).jsonObject
        jsonEncoder.encodeJsonElement(JsonObject(mapOf("cursor" to payload.getValue("cursor"))))
    }
}

@Serializable(with = ChatSessionsListRequestPayloadSerializer::class)
data class ChatSessionsListRequestPayload(
    val limit: Int? = null,
    @SerialName("include_archived") val includeArchived: Boolean = false,
    val query: String? = null,
    @SerialName("embedding_model_id") val embeddingModelId: String? = null,
    val cursor: String? = null,
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
        require(cursor == null || cursor.isNotBlank()) {
            "chat.sessions.list request cursor must be nonblank"
        }
        require(cursor == null || cursor.toByteArray(Charsets.UTF_8).size <= MAX_CHAT_SESSION_CURSOR_BYTES) {
            "chat.sessions.list request cursor must be at most 512 UTF-8 bytes"
        }
        require(
            cursor == null || (
                limit == null &&
                    !includeArchived &&
                    query == null &&
                    embeddingModelId == null
                )
        ) {
            "chat.sessions.list request cursor must not be combined with other fields"
        }
    }
}

@Serializable
private data class ChatSessionsListResultPayloadSurrogate(
    val sessions: List<ChatSessionSummaryPayload>,
    @SerialName("snapshot_count") val snapshotCount: Int? = null,
    @SerialName("next_cursor") val nextCursor: String? = null,
)

object ChatSessionsListResultPayloadSerializer : KSerializer<ChatSessionsListResultPayload> by object :
    ExactJsonObjectTransformingSerializer<
        ChatSessionsListResultPayload,
        ChatSessionsListResultPayloadSurrogate
    >(
        ChatSessionsListResultPayloadSurrogate.serializer(),
        setOf("sessions", "snapshot_count", "next_cursor"),
        "chat.sessions.list response",
    ) {
    override fun fromSurrogate(value: ChatSessionsListResultPayloadSurrogate) =
        ChatSessionsListResultPayload(
            sessions = value.sessions,
            snapshotCount = value.snapshotCount,
            nextCursor = value.nextCursor,
        )

    override fun toSurrogate(value: ChatSessionsListResultPayload) =
        ChatSessionsListResultPayloadSurrogate(
            sessions = value.sessions,
            snapshotCount = value.snapshotCount,
            nextCursor = value.nextCursor,
        )
}

@Serializable(with = ChatSessionsListResultPayloadSerializer::class)
data class ChatSessionsListResultPayload(
    val sessions: List<ChatSessionSummaryPayload>,
    @SerialName("snapshot_count") val snapshotCount: Int? = null,
    @SerialName("next_cursor") val nextCursor: String? = null,
) {
    init {
        require(sessions.size <= MAX_CHAT_SESSION_LIST_LIMIT) {
            "chat.sessions.list response sessions must contain at most 200 entries"
        }
        require(sessions.map(ChatSessionSummaryPayload::sessionId).toSet().size == sessions.size) {
            "chat.sessions.list response session_id values must be unique"
        }
        require(snapshotCount == null || snapshotCount in 0..MAX_CHAT_SESSION_SNAPSHOT_COUNT) {
            "chat.sessions.list response snapshot_count must be between 0 and 10000"
        }
        require(nextCursor == null || nextCursor.isNotBlank()) {
            "chat.sessions.list response next_cursor must be nonblank"
        }
        require(nextCursor == null || nextCursor.toByteArray(Charsets.UTF_8).size <= MAX_CHAT_SESSION_CURSOR_BYTES) {
            "chat.sessions.list response next_cursor must be at most 512 UTF-8 bytes"
        }
        require(nextCursor == null || snapshotCount != null) {
            "chat.sessions.list response next_cursor requires snapshot_count"
        }
        require(snapshotCount == null || sessions.size <= snapshotCount) {
            "chat.sessions.list response sessions size must not exceed snapshot_count"
        }
    }
}

@Serializable
private data class ChatSessionsBulkLifecyclePayloadSurrogate(
    val scope: String,
    val limit: Int = MAX_CHAT_SESSION_LIST_LIMIT,
)

object ChatSessionsBulkLifecyclePayloadSerializer : KSerializer<ChatSessionsBulkLifecyclePayload> by object :
    ExactJsonObjectTransformingSerializer<
        ChatSessionsBulkLifecyclePayload,
        ChatSessionsBulkLifecyclePayloadSurrogate
    >(
        ChatSessionsBulkLifecyclePayloadSurrogate.serializer(),
        setOf("scope", "limit"),
        "chat.sessions bulk lifecycle request",
    ) {
    override fun fromSurrogate(value: ChatSessionsBulkLifecyclePayloadSurrogate) =
        ChatSessionsBulkLifecyclePayload(
            scope = value.scope,
            limit = value.limit,
        )

    override fun toSurrogate(value: ChatSessionsBulkLifecyclePayload) =
        ChatSessionsBulkLifecyclePayloadSurrogate(
            scope = value.scope,
            limit = value.limit,
        )
}

@Serializable(with = ChatSessionsBulkLifecyclePayloadSerializer::class)
data class ChatSessionsBulkLifecyclePayload(
    val scope: String,
    val limit: Int = MAX_CHAT_SESSION_LIST_LIMIT,
) {
    init {
        require(scope in CHAT_SESSIONS_BULK_LIFECYCLE_STATUS_BY_SCOPE) {
            "chat.sessions bulk lifecycle scope must be all_active or all_archived"
        }
        require(limit in 1..MAX_CHAT_SESSION_LIST_LIMIT) {
            "chat.sessions bulk lifecycle limit must be between 1 and 200"
        }
    }
}

@Serializable
private data class ChatSessionsBulkLifecycleResultPayloadSurrogate(
    val scope: String,
    val status: String,
    @SerialName("affected_count") val affectedCount: Int,
    @SerialName("remaining_count") val remainingCount: Int,
    @SerialName("completed_at") val completedAt: String,
)

object ChatSessionsBulkLifecycleResultPayloadSerializer :
    KSerializer<ChatSessionsBulkLifecycleResultPayload> by object :
    ExactJsonObjectTransformingSerializer<
        ChatSessionsBulkLifecycleResultPayload,
        ChatSessionsBulkLifecycleResultPayloadSurrogate
    >(
        ChatSessionsBulkLifecycleResultPayloadSurrogate.serializer(),
        setOf("scope", "status", "affected_count", "remaining_count", "completed_at"),
        "chat.sessions bulk lifecycle result",
    ) {
    override fun fromSurrogate(value: ChatSessionsBulkLifecycleResultPayloadSurrogate) =
        ChatSessionsBulkLifecycleResultPayload(
            scope = value.scope,
            status = value.status,
            affectedCount = value.affectedCount,
            remainingCount = value.remainingCount,
            completedAt = value.completedAt,
        )

    override fun toSurrogate(value: ChatSessionsBulkLifecycleResultPayload) =
        ChatSessionsBulkLifecycleResultPayloadSurrogate(
            scope = value.scope,
            status = value.status,
            affectedCount = value.affectedCount,
            remainingCount = value.remainingCount,
            completedAt = value.completedAt,
        )
}

@Serializable(with = ChatSessionsBulkLifecycleResultPayloadSerializer::class)
data class ChatSessionsBulkLifecycleResultPayload(
    val scope: String,
    val status: String,
    @SerialName("affected_count") val affectedCount: Int,
    @SerialName("remaining_count") val remainingCount: Int,
    @SerialName("completed_at") val completedAt: String,
) {
    init {
        require(scope in CHAT_SESSIONS_BULK_LIFECYCLE_STATUS_BY_SCOPE) {
            "chat.sessions bulk lifecycle result scope must be all_active or all_archived"
        }
        require(status in CHAT_SESSIONS_BULK_LIFECYCLE_STATUS_BY_SCOPE.values) {
            "chat.sessions bulk lifecycle result status must be archived or deleted"
        }
        require(CHAT_SESSIONS_BULK_LIFECYCLE_STATUS_BY_SCOPE[scope] == status) {
            "chat.sessions bulk lifecycle result scope and status must match"
        }
        require(affectedCount in 0..MAX_CHAT_SESSION_LIST_LIMIT) {
            "chat.sessions bulk lifecycle result affected_count must be between 0 and 200"
        }
        require(remainingCount >= 0) {
            "chat.sessions bulk lifecycle result remaining_count must be nonnegative"
        }
        requireExactRfc3339DateTime(completedAt, "chat.sessions bulk lifecycle result completed_at")
    }
}

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
    @SerialName("embedding_model_id") val embeddingModelId: String? = null,
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
        require(embeddingModelId == null || embeddingModelId.isNotBlank()) {
            "retrieval.query request embedding_model_id must be nonblank"
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
enum class RetrievalMatchKind {
    @SerialName("lexical")
    Lexical,

    @SerialName("semantic")
    Semantic,
}

@Serializable
data class RetrievalQueryResultItemPayload(
    val document: RuntimeDocumentIndexDocumentPayload,
    @SerialName("chunk_index") val chunkIndex: Int,
    @SerialName("start_character_offset") val startCharacterOffset: Int,
    @SerialName("end_character_offset") val endCharacterOffset: Int,
    val rank: Int,
    @SerialName("match_kind") val matchKind: RetrievalMatchKind = RetrievalMatchKind.Lexical,
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
        require(matchKind == RetrievalMatchKind.Semantic || matchedTerms.isNotEmpty()) {
            "retrieval.query result matched_terms must be nonempty"
        }
        require(matchedTerms.size <= MAX_RETRIEVAL_MATCHED_TERMS) {
            "retrieval.query result matched_terms must contain at most 16 terms"
        }
        require(matchedTerms.all { it.isNotBlank() }) {
            "retrieval.query result matched_terms entries must be nonblank"
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
private data class CitationResolveRequestPayloadSurrogate(
    @Serializable(with = SourceAnchorIdSerializer::class)
    @SerialName("source_anchor_id") val sourceAnchorId: String,
)

object CitationResolveRequestPayloadSerializer : KSerializer<CitationResolveRequestPayload> by object :
    ExactJsonObjectTransformingSerializer<CitationResolveRequestPayload, CitationResolveRequestPayloadSurrogate>(
        CitationResolveRequestPayloadSurrogate.serializer(),
        setOf("source_anchor_id"),
        "citation.resolve request",
    ) {
    override fun fromSurrogate(value: CitationResolveRequestPayloadSurrogate) =
        CitationResolveRequestPayload(value.sourceAnchorId)

    override fun toSurrogate(value: CitationResolveRequestPayload) =
        CitationResolveRequestPayloadSurrogate(value.sourceAnchorId)
}

@Serializable(with = CitationResolveRequestPayloadSerializer::class)
data class CitationResolveRequestPayload(
    @SerialName("source_anchor_id") val sourceAnchorId: String,
) {
    init {
        require(SOURCE_ANCHOR_ID_PATTERN.matches(sourceAnchorId)) {
            "citation.resolve request source_anchor_id must match source_anchor_[16 lowercase hex]"
        }
    }
}

@Serializable
private data class CitationPayloadSurrogate(
    @SerialName("schema_version") val schemaVersion: Int,
    @SerialName("citation_id") val citationId: String,
    @Serializable(with = SourceAnchorIdSerializer::class)
    @SerialName("source_anchor_id") val sourceAnchorId: String,
    val document: RuntimeDocumentIndexDocumentPayload,
    @SerialName("chunk_summary") val chunkSummary: SourceAnchorChunkSummaryPayload,
)

object CitationPayloadSerializer : KSerializer<CitationPayload> by object :
    ExactJsonObjectTransformingSerializer<CitationPayload, CitationPayloadSurrogate>(
        CitationPayloadSurrogate.serializer(),
        setOf("schema_version", "citation_id", "source_anchor_id", "document", "chunk_summary"),
        "citation",
        { payload ->
            payload.requireExactNestedJsonObject(
                "document",
                setOf(
                    "id",
                    "display_name",
                    "mime_type",
                    "content_fingerprint",
                    "extracted_character_count",
                    "chunk_count",
                    "quality",
                ),
                "citation document",
            )
            payload.requireExactNestedJsonObject(
                "chunk_summary",
                setOf("chunk_index", "start_character_offset", "end_character_offset", "character_count"),
                "citation chunk_summary",
            )
        },
    ) {
    override fun fromSurrogate(value: CitationPayloadSurrogate) = CitationPayload(
        schemaVersion = value.schemaVersion,
        citationId = value.citationId,
        sourceAnchorId = value.sourceAnchorId,
        document = value.document,
        chunkSummary = value.chunkSummary,
    )

    override fun toSurrogate(value: CitationPayload) = CitationPayloadSurrogate(
        schemaVersion = value.schemaVersion,
        citationId = value.citationId,
        sourceAnchorId = value.sourceAnchorId,
        document = value.document,
        chunkSummary = value.chunkSummary,
    )
}

@Serializable(with = CitationPayloadSerializer::class)
data class CitationPayload(
    @SerialName("schema_version") val schemaVersion: Int,
    @SerialName("citation_id") val citationId: String,
    @SerialName("source_anchor_id") val sourceAnchorId: String,
    val document: RuntimeDocumentIndexDocumentPayload,
    @SerialName("chunk_summary") val chunkSummary: SourceAnchorChunkSummaryPayload,
) {
    init {
        require(schemaVersion == 1) { "citation schema_version must be 1" }
        require(CITATION_ID_PATTERN.matches(citationId)) {
            "citation_id must match citation_[32 lowercase hex]"
        }
        require(SOURCE_ANCHOR_ID_PATTERN.matches(sourceAnchorId)) {
            "citation source_anchor_id must match source_anchor_[16 lowercase hex]"
        }
    }
}

@Serializable
private data class SourceReviewPayloadSurrogate(
    @SerialName("review_id") val reviewId: String,
    @SerialName("confirmation_token") val confirmationToken: String,
    @SerialName("disclosure_version") val disclosureVersion: String,
    @SerialName("usage_scope") val usageScope: String,
    @SerialName("expires_at") val expiresAt: String,
)

object SourceReviewPayloadSerializer : KSerializer<SourceReviewPayload> by object :
    ExactJsonObjectTransformingSerializer<SourceReviewPayload, SourceReviewPayloadSurrogate>(
        SourceReviewPayloadSurrogate.serializer(),
        setOf("review_id", "confirmation_token", "disclosure_version", "usage_scope", "expires_at"),
        "citation review",
    ) {
    override fun fromSurrogate(value: SourceReviewPayloadSurrogate) = SourceReviewPayload(
        reviewId = value.reviewId,
        confirmationToken = value.confirmationToken,
        disclosureVersion = value.disclosureVersion,
        usageScope = value.usageScope,
        expiresAt = value.expiresAt,
    )

    override fun toSurrogate(value: SourceReviewPayload) = SourceReviewPayloadSurrogate(
        reviewId = value.reviewId,
        confirmationToken = value.confirmationToken,
        disclosureVersion = value.disclosureVersion,
        usageScope = value.usageScope,
        expiresAt = value.expiresAt,
    )
}

@Serializable(with = SourceReviewPayloadSerializer::class)
data class SourceReviewPayload(
    @SerialName("review_id") val reviewId: String,
    @SerialName("confirmation_token") val confirmationToken: String,
    @SerialName("disclosure_version") val disclosureVersion: String,
    @SerialName("usage_scope") val usageScope: String,
    @SerialName("expires_at") val expiresAt: String,
) {
    init {
        require(SOURCE_REVIEW_ID_PATTERN.matches(reviewId)) {
            "review_id must match source_review_[32 lowercase hex]"
        }
        require(SOURCE_CONFIRMATION_TOKEN_PATTERN.matches(confirmationToken)) {
            "confirmation_token must match source_confirmation_[64 lowercase hex]"
        }
        require(disclosureVersion == TRUSTED_SOURCE_DISCLOSURE_VERSION) {
            "disclosure_version must be runtime-trusted-source-v1"
        }
        require(usageScope == TRUSTED_SOURCE_USAGE_SCOPE) { "usage_scope must be chat_context" }
        requireProtocolDateTime(expiresAt, "expires_at")
    }
}

@Serializable
private data class TrustedSourcePayloadSurrogate(
    @SerialName("grant_id") val grantId: String,
    @SerialName("citation_id") val citationId: String,
    @Serializable(with = SourceAnchorIdSerializer::class)
    @SerialName("source_anchor_id") val sourceAnchorId: String,
    val document: RuntimeDocumentIndexDocumentPayload,
    @SerialName("usage_scope") val usageScope: String,
    @SerialName("approved_at") val approvedAt: String,
)

object TrustedSourcePayloadSerializer : KSerializer<TrustedSourcePayload> by object :
    ExactJsonObjectTransformingSerializer<TrustedSourcePayload, TrustedSourcePayloadSurrogate>(
        TrustedSourcePayloadSurrogate.serializer(),
        setOf("grant_id", "citation_id", "source_anchor_id", "document", "usage_scope", "approved_at"),
        "trusted_source",
        { payload ->
            payload.requireExactNestedJsonObject(
                "document",
                setOf(
                    "id",
                    "display_name",
                    "mime_type",
                    "content_fingerprint",
                    "extracted_character_count",
                    "chunk_count",
                    "quality",
                ),
                "trusted_source document",
            )
        },
    ) {
    override fun fromSurrogate(value: TrustedSourcePayloadSurrogate) = TrustedSourcePayload(
        grantId = value.grantId,
        citationId = value.citationId,
        sourceAnchorId = value.sourceAnchorId,
        document = value.document,
        usageScope = value.usageScope,
        approvedAt = value.approvedAt,
    )

    override fun toSurrogate(value: TrustedSourcePayload) = TrustedSourcePayloadSurrogate(
        grantId = value.grantId,
        citationId = value.citationId,
        sourceAnchorId = value.sourceAnchorId,
        document = value.document,
        usageScope = value.usageScope,
        approvedAt = value.approvedAt,
    )
}

@Serializable(with = TrustedSourcePayloadSerializer::class)
data class TrustedSourcePayload(
    @SerialName("grant_id") val grantId: String,
    @SerialName("citation_id") val citationId: String,
    @SerialName("source_anchor_id") val sourceAnchorId: String,
    val document: RuntimeDocumentIndexDocumentPayload,
    @SerialName("usage_scope") val usageScope: String,
    @SerialName("approved_at") val approvedAt: String,
) {
    init {
        require(TRUSTED_SOURCE_GRANT_ID_PATTERN.matches(grantId)) {
            "grant_id must match trusted_source_[32 lowercase hex]"
        }
        require(CITATION_ID_PATTERN.matches(citationId)) {
            "citation_id must match citation_[32 lowercase hex]"
        }
        require(SOURCE_ANCHOR_ID_PATTERN.matches(sourceAnchorId)) {
            "trusted_source source_anchor_id must match source_anchor_[16 lowercase hex]"
        }
        require(usageScope == TRUSTED_SOURCE_USAGE_SCOPE) { "usage_scope must be chat_context" }
        requireProtocolDateTime(approvedAt, "approved_at")
    }
}

@Serializable
private data class CitationResolveResultPayloadSurrogate(
    val citation: CitationPayload,
    val review: SourceReviewPayload,
    @SerialName("trusted_source") val trustedSource: TrustedSourcePayload? = null,
)

object CitationResolveResultPayloadSerializer : KSerializer<CitationResolveResultPayload> by object :
    ExactJsonObjectTransformingSerializer<CitationResolveResultPayload, CitationResolveResultPayloadSurrogate>(
        CitationResolveResultPayloadSurrogate.serializer(),
        setOf("citation", "review", "trusted_source"),
        "citation.resolve response",
    ) {
    override fun fromSurrogate(value: CitationResolveResultPayloadSurrogate) = CitationResolveResultPayload(
        citation = value.citation,
        review = value.review,
        trustedSource = value.trustedSource,
    )

    override fun toSurrogate(value: CitationResolveResultPayload) = CitationResolveResultPayloadSurrogate(
        citation = value.citation,
        review = value.review,
        trustedSource = value.trustedSource,
    )
}

@Serializable(with = CitationResolveResultPayloadSerializer::class)
data class CitationResolveResultPayload(
    val citation: CitationPayload,
    val review: SourceReviewPayload,
    @SerialName("trusted_source") val trustedSource: TrustedSourcePayload? = null,
) {
    init {
        require(
            trustedSource == null || (
                trustedSource.citationId == citation.citationId &&
                    trustedSource.sourceAnchorId == citation.sourceAnchorId &&
                    trustedSource.document == citation.document
                )
        ) {
            "citation.resolve trusted_source must match the citation identity and document"
        }
    }
}

@Serializable
private data class ChatSourceAttributionResolveRequestPayloadSurrogate(
    @SerialName("session_id") val sessionId: String,
    @SerialName("assistant_message_id") val assistantMessageId: String,
    @SerialName("source_index") val sourceIndex: Int,
)

object ChatSourceAttributionResolveRequestPayloadSerializer :
    KSerializer<ChatSourceAttributionResolveRequestPayload> by object :
    ExactJsonObjectTransformingSerializer<
        ChatSourceAttributionResolveRequestPayload,
        ChatSourceAttributionResolveRequestPayloadSurrogate
    >(
        ChatSourceAttributionResolveRequestPayloadSurrogate.serializer(),
        setOf("session_id", "assistant_message_id", "source_index"),
        "chat.source_attribution.resolve request",
    ) {
    override fun fromSurrogate(value: ChatSourceAttributionResolveRequestPayloadSurrogate) =
        ChatSourceAttributionResolveRequestPayload(
            value.sessionId,
            value.assistantMessageId,
            value.sourceIndex,
        )

    override fun toSurrogate(value: ChatSourceAttributionResolveRequestPayload) =
        ChatSourceAttributionResolveRequestPayloadSurrogate(
            value.sessionId,
            value.assistantMessageId,
            value.sourceIndex,
        )
}

@Serializable(with = ChatSourceAttributionResolveRequestPayloadSerializer::class)
data class ChatSourceAttributionResolveRequestPayload(
    @SerialName("session_id") val sessionId: String,
    @SerialName("assistant_message_id") val assistantMessageId: String,
    @SerialName("source_index") val sourceIndex: Int,
) {
    init {
        require(sessionId.isNotBlank()) {
            "chat.source_attribution.resolve request session_id must be nonblank"
        }
        requireAssistantMessageId(
            assistantMessageId,
            "chat.source_attribution.resolve request assistant_message_id",
        )
        require(sourceIndex in 1..MAX_CHAT_SOURCE_ATTRIBUTIONS) {
            "chat.source_attribution.resolve request source_index must be between 1 and 8"
        }
    }
}

@Serializable
private data class ChatSourceAttributionResolveResultPayloadSurrogate(
    val citation: CitationPayload,
    val review: SourceReviewPayload,
    @SerialName("trusted_source") val trustedSource: TrustedSourcePayload? = null,
)

object ChatSourceAttributionResolveResultPayloadSerializer :
    KSerializer<ChatSourceAttributionResolveResultPayload> by object :
    ExactJsonObjectTransformingSerializer<
        ChatSourceAttributionResolveResultPayload,
        ChatSourceAttributionResolveResultPayloadSurrogate
    >(
        ChatSourceAttributionResolveResultPayloadSurrogate.serializer(),
        setOf("citation", "review", "trusted_source"),
        "chat.source_attribution.resolve response",
    ) {
    override fun fromSurrogate(value: ChatSourceAttributionResolveResultPayloadSurrogate) =
        ChatSourceAttributionResolveResultPayload(
            value.citation,
            value.review,
            value.trustedSource,
        )

    override fun toSurrogate(value: ChatSourceAttributionResolveResultPayload) =
        ChatSourceAttributionResolveResultPayloadSurrogate(
            value.citation,
            value.review,
            value.trustedSource,
        )
}

@Serializable(with = ChatSourceAttributionResolveResultPayloadSerializer::class)
data class ChatSourceAttributionResolveResultPayload(
    val citation: CitationPayload,
    val review: SourceReviewPayload,
    @SerialName("trusted_source") val trustedSource: TrustedSourcePayload? = null,
) {
    init {
        require(
            trustedSource == null || (
                trustedSource.citationId == citation.citationId &&
                    trustedSource.sourceAnchorId == citation.sourceAnchorId &&
                    trustedSource.document == citation.document
                )
        ) {
            "chat.source_attribution.resolve trusted_source must match the citation identity and document"
        }
    }
}

@Serializable
private data class ResearchBriefCreateRequestPayloadSurrogate(
    @SerialName("notebook_id") val notebookId: String,
    @SerialName("session_id") val sessionId: String,
    val topic: String,
    val model: String,
    val locale: String? = null,
    @SerialName("trusted_source_grant_ids") val trustedSourceGrantIds: List<String>,
)

object ResearchBriefCreateRequestPayloadSerializer :
    KSerializer<ResearchBriefCreateRequestPayload> by object :
    ExactJsonObjectTransformingSerializer<
        ResearchBriefCreateRequestPayload,
        ResearchBriefCreateRequestPayloadSurrogate
    >(
        ResearchBriefCreateRequestPayloadSurrogate.serializer(),
        setOf("notebook_id", "session_id", "topic", "model", "locale", "trusted_source_grant_ids"),
        "research.brief.create request",
        validatePayload = { payload ->
            payload["locale"]?.let { locale ->
                require(locale is JsonPrimitive && locale.isString) {
                    "research.brief.create request locale must be a string"
                }
            }
        },
    ) {
    override fun fromSurrogate(value: ResearchBriefCreateRequestPayloadSurrogate) =
        ResearchBriefCreateRequestPayload(
            notebookId = value.notebookId,
            sessionId = value.sessionId,
            topic = value.topic,
            model = value.model,
            locale = value.locale,
            trustedSourceGrantIds = value.trustedSourceGrantIds,
        )

    override fun toSurrogate(value: ResearchBriefCreateRequestPayload) =
        ResearchBriefCreateRequestPayloadSurrogate(
            notebookId = value.notebookId,
            sessionId = value.sessionId,
            topic = value.topic,
            model = value.model,
            locale = value.locale,
            trustedSourceGrantIds = value.trustedSourceGrantIds,
        )
}

@Serializable(with = ResearchBriefCreateRequestPayloadSerializer::class)
data class ResearchBriefCreateRequestPayload(
    @SerialName("notebook_id") val notebookId: String,
    @SerialName("session_id") val sessionId: String,
    val topic: String,
    val model: String,
    val locale: String? = null,
    @SerialName("trusted_source_grant_ids") val trustedSourceGrantIds: List<String>,
) {
    init {
        require(RESEARCH_NOTEBOOK_ID_PATTERN.matches(notebookId)) {
            "research.brief.create request notebook_id must match research_notebook_[32 lowercase hex]"
        }
        requireValidUtf8(sessionId, "research.brief.create request session_id")
        require(sessionId.isNotBlank()) {
            "research.brief.create request session_id must be nonblank"
        }
        require(sessionId.codePointCount(0, sessionId.length) <= MAX_RESEARCH_SESSION_ID_BYTES) {
            "research.brief.create request session_id must be at most 256 Unicode characters"
        }
        requireValidUtf8(topic, "research.brief.create request topic")
        require(topic.trim().isNotEmpty()) {
            "research.brief.create request topic must be nonblank after trimming"
        }
        require(topic.codePointCount(0, topic.length) <= MAX_RESEARCH_TOPIC_CHARACTERS) {
            "research.brief.create request topic must be at most 2048 Unicode characters"
        }
        require(topic.toByteArray(Charsets.UTF_8).size <= MAX_RESEARCH_TOPIC_BYTES) {
            "research.brief.create request topic must be at most 8192 UTF-8 bytes"
        }
        requireValidUtf8(model, "research.brief.create request model")
        require(model.isNotBlank()) {
            "research.brief.create request model must be nonblank"
        }
        require(model.codePointCount(0, model.length) <= MAX_RESEARCH_MODEL_BYTES) {
            "research.brief.create request model must be at most 256 Unicode characters"
        }
        locale?.let {
            requireValidUtf8(it, "research.brief.create request locale")
            require(it.isNotBlank()) {
                "research.brief.create request locale must be nonblank"
            }
            require(it.codePointCount(0, it.length) <= MAX_RESEARCH_LOCALE_BYTES) {
                "research.brief.create request locale must be at most 64 Unicode characters"
            }
        }
        require(trustedSourceGrantIds.size in 1..MAX_TRUSTED_SOURCE_GRANT_IDS) {
            "research.brief.create request trusted_source_grant_ids must contain 1 to 8 entries"
        }
        require(trustedSourceGrantIds.distinct().size == trustedSourceGrantIds.size) {
            "research.brief.create request trusted_source_grant_ids must contain unique entries"
        }
        require(trustedSourceGrantIds.all(TRUSTED_SOURCE_GRANT_ID_PATTERN::matches)) {
            "research.brief.create request trusted_source_grant_ids entries must match trusted_source_[32 lowercase hex]"
        }
    }
}

@Serializable
private data class ResearchNotebooksListInitialRequestPayloadSurrogate(
    @SerialName("include_archived") val includeArchived: Boolean,
    val limit: Int,
)

@Serializable
private data class ResearchNotebooksListContinuationRequestPayloadSurrogate(
    val cursor: String,
)

object ResearchNotebooksListRequestPayloadSerializer : KSerializer<ResearchNotebooksListRequestPayload> {
    private val initialSerializer = ResearchNotebooksListInitialRequestPayloadSurrogate.serializer()
    private val continuationSerializer = ResearchNotebooksListContinuationRequestPayloadSurrogate.serializer()
    override val descriptor: SerialDescriptor = initialSerializer.descriptor

    override fun deserialize(decoder: Decoder): ResearchNotebooksListRequestPayload {
        val (jsonDecoder, payload) = decoder.decodeExactJsonObject(
            setOf("include_archived", "limit", "cursor"),
            "research.notebooks.list request",
        )
        if ("cursor" in payload) {
            require(payload.keys == setOf("cursor")) {
                "research.notebooks.list continuation request must contain only cursor"
            }
            val continuation = jsonDecoder.json.decodeFromJsonElement(continuationSerializer, payload)
            return ResearchNotebooksListRequestPayload(cursor = continuation.cursor)
        }
        require(payload.keys == setOf("include_archived", "limit")) {
            "research.notebooks.list initial request must contain exactly include_archived and limit"
        }
        payload.requireJsonBoolean("include_archived", "research.notebooks.list initial request")
        payload.requireJsonInteger("limit", "research.notebooks.list initial request")
        val initial = jsonDecoder.json.decodeFromJsonElement(initialSerializer, payload)
        return ResearchNotebooksListRequestPayload(
            includeArchived = initial.includeArchived,
            limit = initial.limit,
        )
    }

    override fun serialize(encoder: Encoder, value: ResearchNotebooksListRequestPayload) {
        if (value.cursor == null) {
            encoder.encodeSerializableValue(
                initialSerializer,
                ResearchNotebooksListInitialRequestPayloadSurrogate(
                    includeArchived = value.includeArchived,
                    limit = value.limit,
                ),
            )
            return
        }
        encoder.encodeSerializableValue(
            continuationSerializer,
            ResearchNotebooksListContinuationRequestPayloadSurrogate(value.cursor),
        )
    }
}

@Serializable(with = ResearchNotebooksListRequestPayloadSerializer::class)
data class ResearchNotebooksListRequestPayload(
    @SerialName("include_archived") val includeArchived: Boolean = false,
    val limit: Int = DEFAULT_RESEARCH_NOTEBOOK_LIST_LIMIT,
    val cursor: String? = null,
) {
    init {
        require(limit in 1..MAX_RESEARCH_NOTEBOOK_LIST_LIMIT) {
            "research.notebooks.list initial request limit must be between 1 and 200"
        }
        cursor?.let {
            requireResearchNotebookCursor(it, "research.notebooks.list continuation request cursor")
        }
        require(
            cursor == null || (
                !includeArchived && limit == DEFAULT_RESEARCH_NOTEBOOK_LIST_LIMIT
                )
        ) {
            "research.notebooks.list continuation request cursor must not be combined with initial request values"
        }
    }
}

@Serializable
private data class ResearchNotebookPayloadSurrogate(
    @SerialName("notebook_id") val notebookId: String,
    @SerialName("session_id") val sessionId: String,
    val title: String,
    val model: String,
    @SerialName("source_count") val sourceCount: Int,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
    @SerialName("archived_at") val archivedAt: String? = null,
)

object ResearchNotebookPayloadSerializer : KSerializer<ResearchNotebookPayload> by object :
    ExactJsonObjectTransformingSerializer<ResearchNotebookPayload, ResearchNotebookPayloadSurrogate>(
        ResearchNotebookPayloadSurrogate.serializer(),
        setOf(
            "notebook_id",
            "session_id",
            "title",
            "model",
            "source_count",
            "created_at",
            "updated_at",
            "archived_at",
        ),
        "research.notebooks.list response notebook",
        validatePayload = { payload ->
            payload.requireJsonInteger("source_count", "research.notebooks.list response notebook")
            payload["archived_at"]?.let { archivedAt ->
                require(archivedAt is JsonPrimitive && archivedAt.isString) {
                    "research.notebooks.list response notebook archived_at must be a string"
                }
            }
        },
    ) {
    override fun fromSurrogate(value: ResearchNotebookPayloadSurrogate) = ResearchNotebookPayload(
        notebookId = value.notebookId,
        sessionId = value.sessionId,
        title = value.title,
        model = value.model,
        sourceCount = value.sourceCount,
        createdAt = value.createdAt,
        updatedAt = value.updatedAt,
        archivedAt = value.archivedAt,
    )

    override fun toSurrogate(value: ResearchNotebookPayload) = ResearchNotebookPayloadSurrogate(
        notebookId = value.notebookId,
        sessionId = value.sessionId,
        title = value.title,
        model = value.model,
        sourceCount = value.sourceCount,
        createdAt = value.createdAt,
        updatedAt = value.updatedAt,
        archivedAt = value.archivedAt,
    )
}

@Serializable(with = ResearchNotebookPayloadSerializer::class)
data class ResearchNotebookPayload(
    @SerialName("notebook_id") val notebookId: String,
    @SerialName("session_id") val sessionId: String,
    val title: String,
    val model: String,
    @SerialName("source_count") val sourceCount: Int,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
    @SerialName("archived_at") val archivedAt: String? = null,
) {
    init {
        require(RESEARCH_NOTEBOOK_ID_PATTERN.matches(notebookId)) {
            "research.notebooks.list response notebook_id must match research_notebook_[32 lowercase hex]"
        }
        requireValidUtf8(sessionId, "research.notebooks.list response session_id")
        require(sessionId.isNotBlank()) {
            "research.notebooks.list response session_id must be nonblank"
        }
        require(sessionId.codePointCount(0, sessionId.length) <= MAX_RESEARCH_SESSION_ID_BYTES) {
            "research.notebooks.list response session_id must be at most 256 Unicode characters"
        }
        requireValidUtf8(title, "research.notebooks.list response title")
        require(title.isNotBlank()) {
            "research.notebooks.list response title must be nonblank"
        }
        require(title.codePointCount(0, title.length) <= MAX_RESEARCH_NOTEBOOK_TITLE_CHARACTERS) {
            "research.notebooks.list response title must be at most 256 Unicode characters"
        }
        require(title.toByteArray(Charsets.UTF_8).size <= MAX_RESEARCH_NOTEBOOK_TITLE_BYTES) {
            "research.notebooks.list response title must be at most 1024 UTF-8 bytes"
        }
        requireValidUtf8(model, "research.notebooks.list response model")
        require(model.isNotBlank()) {
            "research.notebooks.list response model must be nonblank"
        }
        require(model.codePointCount(0, model.length) <= MAX_RESEARCH_MODEL_BYTES) {
            "research.notebooks.list response model must be at most 256 Unicode characters"
        }
        require(sourceCount in 1..MAX_TRUSTED_SOURCE_GRANT_IDS) {
            "research.notebooks.list response source_count must be between 1 and 8"
        }
        requireExactRfc3339DateTime(createdAt, "research.notebooks.list response created_at")
        requireExactRfc3339DateTime(updatedAt, "research.notebooks.list response updated_at")
        val createdInstant = Instant.parse(createdAt)
        val updatedInstant = Instant.parse(updatedAt)
        require(updatedInstant >= createdInstant) {
            "research.notebooks.list response updated_at must be at or after created_at"
        }
        archivedAt?.let {
            requireExactRfc3339DateTime(it, "research.notebooks.list response archived_at")
            val archivedInstant = Instant.parse(it)
            require(archivedInstant >= createdInstant) {
                "research.notebooks.list response archived_at must be at or after created_at"
            }
        }
    }
}

private val RESEARCH_NOTEBOOK_COMPARATOR = Comparator<ResearchNotebookPayload> { left, right ->
    val updatedAtComparison = Instant.parse(right.updatedAt).compareTo(Instant.parse(left.updatedAt))
    if (updatedAtComparison != 0) return@Comparator updatedAtComparison
    CANONICAL_UNSIGNED_UTF8_STRING_COMPARATOR.compare(left.notebookId, right.notebookId)
}

@Serializable
private data class ResearchNotebooksListResultPayloadSurrogate(
    val notebooks: List<ResearchNotebookPayload>,
    @SerialName("snapshot_count") val snapshotCount: Int? = null,
    @SerialName("next_cursor") val nextCursor: String? = null,
)

object ResearchNotebooksListResultPayloadSerializer : KSerializer<ResearchNotebooksListResultPayload> {
    private val surrogateSerializer = ResearchNotebooksListResultPayloadSurrogate.serializer()
    private val notebookListSerializer = ListSerializer(ResearchNotebookPayload.serializer())
    override val descriptor: SerialDescriptor = surrogateSerializer.descriptor

    override fun deserialize(decoder: Decoder): ResearchNotebooksListResultPayload {
        val (jsonDecoder, payload) = decoder.decodeExactJsonObject(
            setOf("notebooks", "snapshot_count", "next_cursor"),
            "research.notebooks.list response",
        )
        require("notebooks" in payload) {
            "research.notebooks.list response must contain notebooks"
        }
        val hasSnapshotCount = "snapshot_count" in payload
        val hasNextCursor = "next_cursor" in payload
        if (!hasSnapshotCount) {
            require(!hasNextCursor && payload.keys == setOf("notebooks")) {
                "research.notebooks.list legacy response must contain only notebooks"
            }
        } else {
            require(
                payload.keys == setOf("notebooks", "snapshot_count") ||
                    payload.keys == setOf("notebooks", "snapshot_count", "next_cursor")
            ) {
                "research.notebooks.list capable response must contain notebooks, snapshot_count, and optional next_cursor"
            }
            payload.requireJsonInteger("snapshot_count", "research.notebooks.list capable response")
            payload["next_cursor"]?.let { nextCursor ->
                require(nextCursor is JsonPrimitive && nextCursor.isString) {
                    "research.notebooks.list capable response next_cursor must be a string"
                }
            }
        }
        val value = jsonDecoder.json.decodeFromJsonElement(surrogateSerializer, payload)
        return ResearchNotebooksListResultPayload(
            notebooks = value.notebooks,
            snapshotCount = value.snapshotCount,
            nextCursor = value.nextCursor,
        )
    }

    override fun serialize(encoder: Encoder, value: ResearchNotebooksListResultPayload) {
        val jsonEncoder = encoder as? JsonEncoder
            ?: throw IllegalArgumentException("research.notebooks.list response requires JSON encoding")
        val payload = buildMap<String, kotlinx.serialization.json.JsonElement> {
            put(
                "notebooks",
                jsonEncoder.json.encodeToJsonElement(notebookListSerializer, value.notebooks),
            )
            value.snapshotCount?.let { put("snapshot_count", JsonPrimitive(it)) }
            value.nextCursor?.let { put("next_cursor", JsonPrimitive(it)) }
        }
        jsonEncoder.encodeJsonElement(JsonObject(payload))
    }
}

@Serializable(with = ResearchNotebooksListResultPayloadSerializer::class)
data class ResearchNotebooksListResultPayload(
    val notebooks: List<ResearchNotebookPayload>,
    @SerialName("snapshot_count") val snapshotCount: Int? = null,
    @SerialName("next_cursor") val nextCursor: String? = null,
) {
    init {
        val pageLimit = if (snapshotCount == null) {
            DEFAULT_RESEARCH_NOTEBOOK_LIST_LIMIT
        } else {
            MAX_RESEARCH_NOTEBOOK_LIST_LIMIT
        }
        require(notebooks.size <= pageLimit) {
            "research.notebooks.list response notebooks must contain at most $pageLimit entries"
        }
        require(notebooks.distinctBy(ResearchNotebookPayload::notebookId).size == notebooks.size) {
            "research.notebooks.list response notebook_id values must be unique"
        }
        require(notebooks.distinctBy(ResearchNotebookPayload::sessionId).size == notebooks.size) {
            "research.notebooks.list response session_id values must be unique"
        }
        require(notebooks.sortedWith(RESEARCH_NOTEBOOK_COMPARATOR) == notebooks) {
            "research.notebooks.list response notebooks must be sorted by updated_at descending then notebook_id using canonical unsigned UTF-8 byte order"
        }
        require(snapshotCount == null || snapshotCount in 0..MAX_RESEARCH_NOTEBOOK_SNAPSHOT_COUNT) {
            "research.notebooks.list capable response snapshot_count must be between 0 and 10000"
        }
        require(nextCursor == null || snapshotCount != null) {
            "research.notebooks.list response next_cursor requires snapshot_count"
        }
        nextCursor?.let {
            requireResearchNotebookCursor(it, "research.notebooks.list capable response next_cursor")
        }
        require(snapshotCount == null || notebooks.size <= snapshotCount) {
            "research.notebooks.list capable response notebooks size must not exceed snapshot_count"
        }
    }
}

@Serializable
private data class TrustedSourceApproveRequestPayloadSurrogate(
    @SerialName("review_id") val reviewId: String,
    @SerialName("confirmation_token") val confirmationToken: String,
    @SerialName("disclosure_version") val disclosureVersion: String,
    @SerialName("usage_scope") val usageScope: String,
)

object TrustedSourceApproveRequestPayloadSerializer : KSerializer<TrustedSourceApproveRequestPayload> by object :
    ExactJsonObjectTransformingSerializer<TrustedSourceApproveRequestPayload, TrustedSourceApproveRequestPayloadSurrogate>(
        TrustedSourceApproveRequestPayloadSurrogate.serializer(),
        setOf("review_id", "confirmation_token", "disclosure_version", "usage_scope"),
        "trusted_source.approve request",
    ) {
    override fun fromSurrogate(value: TrustedSourceApproveRequestPayloadSurrogate) = TrustedSourceApproveRequestPayload(
        value.reviewId,
        value.confirmationToken,
        value.disclosureVersion,
        value.usageScope,
    )

    override fun toSurrogate(value: TrustedSourceApproveRequestPayload) = TrustedSourceApproveRequestPayloadSurrogate(
        value.reviewId,
        value.confirmationToken,
        value.disclosureVersion,
        value.usageScope,
    )
}

@Serializable(with = TrustedSourceApproveRequestPayloadSerializer::class)
data class TrustedSourceApproveRequestPayload(
    @SerialName("review_id") val reviewId: String,
    @SerialName("confirmation_token") val confirmationToken: String,
    @SerialName("disclosure_version") val disclosureVersion: String,
    @SerialName("usage_scope") val usageScope: String,
) {
    init {
        require(SOURCE_REVIEW_ID_PATTERN.matches(reviewId)) {
            "review_id must match source_review_[32 lowercase hex]"
        }
        require(SOURCE_CONFIRMATION_TOKEN_PATTERN.matches(confirmationToken)) {
            "confirmation_token must match source_confirmation_[64 lowercase hex]"
        }
        require(disclosureVersion == TRUSTED_SOURCE_DISCLOSURE_VERSION) {
            "disclosure_version must be runtime-trusted-source-v1"
        }
        require(usageScope == TRUSTED_SOURCE_USAGE_SCOPE) { "usage_scope must be chat_context" }
    }
}

@Serializable
private data class TrustedSourceApproveResultPayloadSurrogate(
    @SerialName("trusted_source") val trustedSource: TrustedSourcePayload,
)

object TrustedSourceApproveResultPayloadSerializer : KSerializer<TrustedSourceApproveResultPayload> by object :
    ExactJsonObjectTransformingSerializer<TrustedSourceApproveResultPayload, TrustedSourceApproveResultPayloadSurrogate>(
        TrustedSourceApproveResultPayloadSurrogate.serializer(),
        setOf("trusted_source"),
        "trusted_source.approve response",
    ) {
    override fun fromSurrogate(value: TrustedSourceApproveResultPayloadSurrogate) =
        TrustedSourceApproveResultPayload(value.trustedSource)

    override fun toSurrogate(value: TrustedSourceApproveResultPayload) =
        TrustedSourceApproveResultPayloadSurrogate(value.trustedSource)
}

@Serializable(with = TrustedSourceApproveResultPayloadSerializer::class)
data class TrustedSourceApproveResultPayload(
    @SerialName("trusted_source") val trustedSource: TrustedSourcePayload,
)

@Serializable
private data class TrustedSourceDismissRequestPayloadSurrogate(
    @SerialName("review_id") val reviewId: String,
)

object TrustedSourceDismissRequestPayloadSerializer : KSerializer<TrustedSourceDismissRequestPayload> by object :
    ExactJsonObjectTransformingSerializer<TrustedSourceDismissRequestPayload, TrustedSourceDismissRequestPayloadSurrogate>(
        TrustedSourceDismissRequestPayloadSurrogate.serializer(),
        setOf("review_id"),
        "trusted_source.dismiss request",
    ) {
    override fun fromSurrogate(value: TrustedSourceDismissRequestPayloadSurrogate) =
        TrustedSourceDismissRequestPayload(value.reviewId)

    override fun toSurrogate(value: TrustedSourceDismissRequestPayload) =
        TrustedSourceDismissRequestPayloadSurrogate(value.reviewId)
}

@Serializable(with = TrustedSourceDismissRequestPayloadSerializer::class)
data class TrustedSourceDismissRequestPayload(
    @SerialName("review_id") val reviewId: String,
) {
    init {
        require(SOURCE_REVIEW_ID_PATTERN.matches(reviewId)) {
            "review_id must match source_review_[32 lowercase hex]"
        }
    }
}

@Serializable
private data class TrustedSourceDismissResultPayloadSurrogate(
    @SerialName("review_id") val reviewId: String,
    val dismissed: Boolean,
)

object TrustedSourceDismissResultPayloadSerializer : KSerializer<TrustedSourceDismissResultPayload> by object :
    ExactJsonObjectTransformingSerializer<TrustedSourceDismissResultPayload, TrustedSourceDismissResultPayloadSurrogate>(
        TrustedSourceDismissResultPayloadSurrogate.serializer(),
        setOf("review_id", "dismissed"),
        "trusted_source.dismiss response",
    ) {
    override fun fromSurrogate(value: TrustedSourceDismissResultPayloadSurrogate) =
        TrustedSourceDismissResultPayload(value.reviewId, value.dismissed)

    override fun toSurrogate(value: TrustedSourceDismissResultPayload) =
        TrustedSourceDismissResultPayloadSurrogate(value.reviewId, value.dismissed)
}

@Serializable(with = TrustedSourceDismissResultPayloadSerializer::class)
data class TrustedSourceDismissResultPayload(
    @SerialName("review_id") val reviewId: String,
    val dismissed: Boolean,
) {
    init {
        require(SOURCE_REVIEW_ID_PATTERN.matches(reviewId)) {
            "review_id must match source_review_[32 lowercase hex]"
        }
        require(dismissed) { "trusted_source.dismiss response dismissed must be true" }
    }
}

@Serializable
private data class TrustedSourceListRequestPayloadSurrogate(val limit: Int? = null)

object TrustedSourceListRequestPayloadSerializer : KSerializer<TrustedSourceListRequestPayload> by object :
    ExactJsonObjectTransformingSerializer<TrustedSourceListRequestPayload, TrustedSourceListRequestPayloadSurrogate>(
        TrustedSourceListRequestPayloadSurrogate.serializer(),
        setOf("limit"),
        "trusted_source.list request",
    ) {
    override fun fromSurrogate(value: TrustedSourceListRequestPayloadSurrogate) =
        TrustedSourceListRequestPayload(value.limit)

    override fun toSurrogate(value: TrustedSourceListRequestPayload) =
        TrustedSourceListRequestPayloadSurrogate(value.limit)
}

@Serializable(with = TrustedSourceListRequestPayloadSerializer::class)
data class TrustedSourceListRequestPayload(val limit: Int? = null) {
    init {
        require(limit == null || limit in 0..MAX_DOCUMENT_REQUEST_LIMIT) {
            "trusted_source.list request limit must be between 0 and 100"
        }
    }
}

@Serializable
private data class TrustedSourceListResultPayloadSurrogate(
    @SerialName("trusted_sources") val trustedSources: List<TrustedSourcePayload>,
)

object TrustedSourceListResultPayloadSerializer : KSerializer<TrustedSourceListResultPayload> by object :
    ExactJsonObjectTransformingSerializer<TrustedSourceListResultPayload, TrustedSourceListResultPayloadSurrogate>(
        TrustedSourceListResultPayloadSurrogate.serializer(),
        setOf("trusted_sources"),
        "trusted_source.list response",
    ) {
    override fun fromSurrogate(value: TrustedSourceListResultPayloadSurrogate) =
        TrustedSourceListResultPayload(value.trustedSources)

    override fun toSurrogate(value: TrustedSourceListResultPayload) =
        TrustedSourceListResultPayloadSurrogate(value.trustedSources)
}

@Serializable(with = TrustedSourceListResultPayloadSerializer::class)
data class TrustedSourceListResultPayload(
    @SerialName("trusted_sources") val trustedSources: List<TrustedSourcePayload>,
) {
    init {
        require(trustedSources.size <= MAX_DOCUMENT_REQUEST_LIMIT) {
            "trusted_source.list response trusted_sources must contain at most 100 items"
        }
        require(trustedSources.map { it.grantId }.distinct().size == trustedSources.size) {
            "trusted_source.list response grant_id values must be unique"
        }
        require(trustedSources.map { it.sourceAnchorId }.distinct().size == trustedSources.size) {
            "trusted_source.list response source_anchor_id values must be unique"
        }
    }
}

@Serializable
private data class TrustedSourceRevokeRequestPayloadSurrogate(
    @SerialName("grant_id") val grantId: String,
)

object TrustedSourceRevokeRequestPayloadSerializer : KSerializer<TrustedSourceRevokeRequestPayload> by object :
    ExactJsonObjectTransformingSerializer<TrustedSourceRevokeRequestPayload, TrustedSourceRevokeRequestPayloadSurrogate>(
        TrustedSourceRevokeRequestPayloadSurrogate.serializer(),
        setOf("grant_id"),
        "trusted_source.revoke request",
    ) {
    override fun fromSurrogate(value: TrustedSourceRevokeRequestPayloadSurrogate) =
        TrustedSourceRevokeRequestPayload(value.grantId)

    override fun toSurrogate(value: TrustedSourceRevokeRequestPayload) =
        TrustedSourceRevokeRequestPayloadSurrogate(value.grantId)
}

@Serializable(with = TrustedSourceRevokeRequestPayloadSerializer::class)
data class TrustedSourceRevokeRequestPayload(
    @SerialName("grant_id") val grantId: String,
) {
    init {
        require(TRUSTED_SOURCE_GRANT_ID_PATTERN.matches(grantId)) {
            "grant_id must match trusted_source_[32 lowercase hex]"
        }
    }
}

@Serializable
private data class TrustedSourceRevokeResultPayloadSurrogate(
    @SerialName("grant_id") val grantId: String,
    val revoked: Boolean,
)

object TrustedSourceRevokeResultPayloadSerializer : KSerializer<TrustedSourceRevokeResultPayload> by object :
    ExactJsonObjectTransformingSerializer<TrustedSourceRevokeResultPayload, TrustedSourceRevokeResultPayloadSurrogate>(
        TrustedSourceRevokeResultPayloadSurrogate.serializer(),
        setOf("grant_id", "revoked"),
        "trusted_source.revoke response",
    ) {
    override fun fromSurrogate(value: TrustedSourceRevokeResultPayloadSurrogate) =
        TrustedSourceRevokeResultPayload(value.grantId, value.revoked)

    override fun toSurrogate(value: TrustedSourceRevokeResultPayload) =
        TrustedSourceRevokeResultPayloadSurrogate(value.grantId, value.revoked)
}

@Serializable(with = TrustedSourceRevokeResultPayloadSerializer::class)
data class TrustedSourceRevokeResultPayload(
    @SerialName("grant_id") val grantId: String,
    val revoked: Boolean,
) {
    init {
        require(TRUSTED_SOURCE_GRANT_ID_PATTERN.matches(grantId)) {
            "grant_id must match trusted_source_[32 lowercase hex]"
        }
        require(revoked) { "trusted_source.revoke response revoked must be true" }
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
    @OptIn(ExperimentalSerializationApi::class)
    @EncodeDefault(EncodeDefault.Mode.NEVER)
    @Serializable(with = NonEmptyChatSourceAttributionsSerializer::class)
    @SerialName("source_attributions")
    val sourceAttributions: List<ChatSourceAttributionPayload> = emptyList(),
    @SerialName("created_at") val createdAt: String? = null,
    @OptIn(ExperimentalSerializationApi::class)
    @EncodeDefault(EncodeDefault.Mode.NEVER)
    @SerialName("assistant_message_id")
    val assistantMessageId: String? = null,
) {
    init {
        require(sourceAttributions.isEmpty() || role == "assistant") {
            "chat.messages.list response source_attributions require assistant role"
        }
        requireCanonicalChatSourceAttributions(
            sourceAttributions,
            "chat.messages.list response source_attributions",
        )
        require(assistantMessageId == null || (role == "assistant" && sourceAttributions.isNotEmpty())) {
            "chat.messages.list response assistant_message_id requires assistant source_attributions"
        }
        requireAssistantMessageId(
            assistantMessageId,
            "chat.messages.list response assistant_message_id",
        )
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
    @SerialName("embedding_model_id") val embeddingModelId: String? = null,
) {
    init {
        require(query == null || query.isNotEmpty()) {
            "memory.list request query must be nonempty"
        }
        require(embeddingModelId == null || embeddingModelId.isNotBlank()) {
            "memory.list request embedding_model_id must be nonblank"
        }
    }
}

@Serializable
data class MemoryListResultPayload(
    val entries: List<MemoryEntryPayload>,
)

@Serializable
data object MemoryDuplicateSuggestionsListRequestPayload

@Serializable
data class MemoryDuplicateSuggestionGroupPayload(
    @SerialName("entry_ids") val entryIds: List<String>,
) {
    init {
        require(entryIds.size in 2..MAX_MEMORY_DUPLICATE_SUGGESTION_GROUP_SIZE) {
            "memory.duplicate_suggestions.list response group entry_ids must contain 2 to 200 IDs"
        }
        require(entryIds.all { it.isNotBlank() }) {
            "memory.duplicate_suggestions.list response entry_ids must be nonblank"
        }
        require(entryIds.all { Charsets.UTF_8.newEncoder().canEncode(it) }) {
            "memory.duplicate_suggestions.list response entry_ids must be valid UTF-8 encodable Unicode"
        }
        require(entryIds.distinct() == entryIds) {
            "memory.duplicate_suggestions.list response group entry_ids must be unique"
        }
        require(entryIds.sortedWith(CANONICAL_UNSIGNED_UTF8_STRING_COMPARATOR) == entryIds) {
            "memory.duplicate_suggestions.list response group entry_ids must use canonical unsigned UTF-8 byte order"
        }
    }
}

@Serializable
data class MemoryDuplicateSuggestionsListResultPayload(
    val groups: List<MemoryDuplicateSuggestionGroupPayload>,
    @SerialName("scanned_count") val scannedCount: Int,
    val truncated: Boolean,
) {
    init {
        require(groups.size <= MAX_MEMORY_DUPLICATE_SUGGESTION_GROUPS) {
            "memory.duplicate_suggestions.list response groups must contain at most 100 groups"
        }
        require(scannedCount in 0..MAX_MEMORY_DUPLICATE_SUGGESTION_SCANNED_COUNT) {
            "memory.duplicate_suggestions.list response scanned_count must be between 0 and 200"
        }
        val entryIds = groups.flatMap(MemoryDuplicateSuggestionGroupPayload::entryIds)
        val aggregateEntryIdUtf8Bytes = entryIds.sumOf { entryId ->
            entryId.toByteArray(Charsets.UTF_8).size.toLong()
        }
        require(aggregateEntryIdUtf8Bytes <= MAX_MEMORY_DUPLICATE_SUGGESTION_ID_AGGREGATE_UTF8_BYTES) {
            "memory.duplicate_suggestions.list response entry_ids must not exceed 128 KiB of aggregate UTF-8 bytes"
        }
        require(entryIds.distinct().size == entryIds.size) {
            "memory.duplicate_suggestions.list response entry_ids must not repeat across groups"
        }
        require(entryIds.size <= scannedCount) {
            "memory.duplicate_suggestions.list response grouped distinct ID count must not exceed scanned_count"
        }
        require(
            groups.map { it.entryIds.first() }.sortedWith(CANONICAL_UNSIGNED_UTF8_STRING_COMPARATOR) ==
                groups.map { it.entryIds.first() },
        ) {
            "memory.duplicate_suggestions.list response groups must be sorted by first entry ID using canonical unsigned UTF-8 byte order"
        }
    }
}

@Serializable
private data class MemorySemanticDuplicateSuggestionsListRequestPayloadSurrogate(
    @SerialName("embedding_model_id") val embeddingModelId: String,
    @SerialName("minimum_similarity_basis_points") val minimumSimilarityBasisPoints: Int,
)

object MemorySemanticDuplicateSuggestionsListRequestPayloadSerializer :
    KSerializer<MemorySemanticDuplicateSuggestionsListRequestPayload> by object :
    ExactJsonObjectTransformingSerializer<
        MemorySemanticDuplicateSuggestionsListRequestPayload,
        MemorySemanticDuplicateSuggestionsListRequestPayloadSurrogate
    >(
        MemorySemanticDuplicateSuggestionsListRequestPayloadSurrogate.serializer(),
        setOf("embedding_model_id", "minimum_similarity_basis_points"),
        "memory.semantic_duplicate_suggestions.list request",
        validatePayload = { payload ->
            payload.requireJsonInteger(
                "minimum_similarity_basis_points",
                "memory.semantic_duplicate_suggestions.list request",
            )
        },
    ) {
    override fun fromSurrogate(value: MemorySemanticDuplicateSuggestionsListRequestPayloadSurrogate) =
        MemorySemanticDuplicateSuggestionsListRequestPayload(
            embeddingModelId = value.embeddingModelId,
            minimumSimilarityBasisPoints = value.minimumSimilarityBasisPoints,
        )

    override fun toSurrogate(value: MemorySemanticDuplicateSuggestionsListRequestPayload) =
        MemorySemanticDuplicateSuggestionsListRequestPayloadSurrogate(
            embeddingModelId = value.embeddingModelId,
            minimumSimilarityBasisPoints = value.minimumSimilarityBasisPoints,
        )
}

@Serializable(with = MemorySemanticDuplicateSuggestionsListRequestPayloadSerializer::class)
data class MemorySemanticDuplicateSuggestionsListRequestPayload(
    @SerialName("embedding_model_id") val embeddingModelId: String,
    @SerialName("minimum_similarity_basis_points") val minimumSimilarityBasisPoints: Int,
) {
    init {
        require(embeddingModelId.isNotBlank()) {
            "memory.semantic_duplicate_suggestions.list request embedding_model_id must be nonblank"
        }
        require(isCanonicalProviderQualifiedModelId(embeddingModelId)) {
            "memory.semantic_duplicate_suggestions.list request embedding_model_id must be provider-qualified"
        }
        require(Charsets.UTF_8.newEncoder().canEncode(embeddingModelId)) {
            "memory.semantic_duplicate_suggestions.list request embedding_model_id must be valid UTF-8 encodable Unicode"
        }
        require(
            embeddingModelId.codePointCount(0, embeddingModelId.length) <=
                MAX_MEMORY_SEMANTIC_DUPLICATE_SUGGESTION_EMBEDDING_MODEL_ID_LENGTH
        ) {
            "memory.semantic_duplicate_suggestions.list request embedding_model_id must be at most 256 Unicode code points"
        }
        require(minimumSimilarityBasisPoints in 8_000..10_000) {
            "memory.semantic_duplicate_suggestions.list request minimum_similarity_basis_points must be between 8000 and 10000"
        }
    }
}

@Serializable
private data class MemorySemanticDuplicateSuggestionPairPayloadSurrogate(
    @SerialName("entry_ids") val entryIds: List<String>,
    @SerialName("similarity_basis_points") val similarityBasisPoints: Int,
)

object MemorySemanticDuplicateSuggestionPairPayloadSerializer :
    KSerializer<MemorySemanticDuplicateSuggestionPairPayload> by object :
    ExactJsonObjectTransformingSerializer<
        MemorySemanticDuplicateSuggestionPairPayload,
        MemorySemanticDuplicateSuggestionPairPayloadSurrogate
    >(
        MemorySemanticDuplicateSuggestionPairPayloadSurrogate.serializer(),
        setOf("entry_ids", "similarity_basis_points"),
        "memory.semantic_duplicate_suggestions.list response pair",
        validatePayload = { payload ->
            payload.requireJsonInteger(
                "similarity_basis_points",
                "memory.semantic_duplicate_suggestions.list response pair",
            )
        },
    ) {
    override fun fromSurrogate(value: MemorySemanticDuplicateSuggestionPairPayloadSurrogate) =
        MemorySemanticDuplicateSuggestionPairPayload(
            entryIds = value.entryIds,
            similarityBasisPoints = value.similarityBasisPoints,
        )

    override fun toSurrogate(value: MemorySemanticDuplicateSuggestionPairPayload) =
        MemorySemanticDuplicateSuggestionPairPayloadSurrogate(
            entryIds = value.entryIds,
            similarityBasisPoints = value.similarityBasisPoints,
        )
}

@Serializable(with = MemorySemanticDuplicateSuggestionPairPayloadSerializer::class)
data class MemorySemanticDuplicateSuggestionPairPayload(
    @SerialName("entry_ids") val entryIds: List<String>,
    @SerialName("similarity_basis_points") val similarityBasisPoints: Int,
) {
    init {
        require(entryIds.size == 2) {
            "memory.semantic_duplicate_suggestions.list response pair entry_ids must contain exactly two IDs"
        }
        require(entryIds.all { it.isNotBlank() }) {
            "memory.semantic_duplicate_suggestions.list response pair entry_ids must be nonblank"
        }
        require(entryIds.all { Charsets.UTF_8.newEncoder().canEncode(it) }) {
            "memory.semantic_duplicate_suggestions.list response pair entry_ids must be valid UTF-8 encodable Unicode"
        }
        require(entryIds[0] != entryIds[1]) {
            "memory.semantic_duplicate_suggestions.list response pair entry_ids must be distinct"
        }
        require(CANONICAL_UNSIGNED_UTF8_STRING_COMPARATOR.compare(entryIds[0], entryIds[1]) < 0) {
            "memory.semantic_duplicate_suggestions.list response pair entry_ids must use canonical unsigned UTF-8 byte order"
        }
        require(similarityBasisPoints in 0..10_000) {
            "memory.semantic_duplicate_suggestions.list response pair similarity_basis_points must be between 0 and 10000"
        }
    }
}

private val MEMORY_SEMANTIC_DUPLICATE_SUGGESTION_PAIR_COMPARATOR =
    Comparator<MemorySemanticDuplicateSuggestionPairPayload> { left, right ->
        val scoreComparison = right.similarityBasisPoints.compareTo(left.similarityBasisPoints)
        if (scoreComparison != 0) return@Comparator scoreComparison
        val firstIdComparison = CANONICAL_UNSIGNED_UTF8_STRING_COMPARATOR.compare(
            left.entryIds[0],
            right.entryIds[0],
        )
        if (firstIdComparison != 0) return@Comparator firstIdComparison
        CANONICAL_UNSIGNED_UTF8_STRING_COMPARATOR.compare(left.entryIds[1], right.entryIds[1])
    }

@Serializable
private data class MemorySemanticDuplicateSuggestionsListResultPayloadSurrogate(
    val pairs: List<MemorySemanticDuplicateSuggestionPairPayload>,
    @SerialName("scanned_count") val scannedCount: Int,
    @SerialName("omitted_count") val omittedCount: Int,
    val truncated: Boolean,
)

object MemorySemanticDuplicateSuggestionsListResultPayloadSerializer :
    KSerializer<MemorySemanticDuplicateSuggestionsListResultPayload> by object :
    ExactJsonObjectTransformingSerializer<
        MemorySemanticDuplicateSuggestionsListResultPayload,
        MemorySemanticDuplicateSuggestionsListResultPayloadSurrogate
    >(
        MemorySemanticDuplicateSuggestionsListResultPayloadSurrogate.serializer(),
        setOf("pairs", "scanned_count", "omitted_count", "truncated"),
        "memory.semantic_duplicate_suggestions.list response",
        validatePayload = { payload ->
            payload.requireJsonInteger(
                "scanned_count",
                "memory.semantic_duplicate_suggestions.list response",
            )
            payload.requireJsonInteger(
                "omitted_count",
                "memory.semantic_duplicate_suggestions.list response",
            )
            payload.requireJsonBoolean(
                "truncated",
                "memory.semantic_duplicate_suggestions.list response",
            )
        },
    ) {
    override fun fromSurrogate(value: MemorySemanticDuplicateSuggestionsListResultPayloadSurrogate) =
        MemorySemanticDuplicateSuggestionsListResultPayload(
            pairs = value.pairs,
            scannedCount = value.scannedCount,
            omittedCount = value.omittedCount,
            truncated = value.truncated,
        )

    override fun toSurrogate(value: MemorySemanticDuplicateSuggestionsListResultPayload) =
        MemorySemanticDuplicateSuggestionsListResultPayloadSurrogate(
            pairs = value.pairs,
            scannedCount = value.scannedCount,
            omittedCount = value.omittedCount,
            truncated = value.truncated,
        )
}

@Serializable(with = MemorySemanticDuplicateSuggestionsListResultPayloadSerializer::class)
data class MemorySemanticDuplicateSuggestionsListResultPayload(
    val pairs: List<MemorySemanticDuplicateSuggestionPairPayload>,
    @SerialName("scanned_count") val scannedCount: Int,
    @SerialName("omitted_count") val omittedCount: Int,
    val truncated: Boolean,
) {
    init {
        require(pairs.size <= MAX_MEMORY_SEMANTIC_DUPLICATE_SUGGESTION_PAIRS) {
            "memory.semantic_duplicate_suggestions.list response pairs must contain at most 100 pairs"
        }
        require(scannedCount in 0..MAX_MEMORY_SEMANTIC_DUPLICATE_SUGGESTION_SCANNED_COUNT) {
            "memory.semantic_duplicate_suggestions.list response scanned_count must be between 0 and 200"
        }
        require(omittedCount in 0..MAX_MEMORY_SEMANTIC_DUPLICATE_SUGGESTION_SCANNED_COUNT) {
            "memory.semantic_duplicate_suggestions.list response omitted_count must be between 0 and 200"
        }
        require(pairs.distinctBy(MemorySemanticDuplicateSuggestionPairPayload::entryIds).size == pairs.size) {
            "memory.semantic_duplicate_suggestions.list response pairs must be unique"
        }
        require(pairs.flatMap { it.entryIds }.distinct().size <= scannedCount) {
            "memory.semantic_duplicate_suggestions.list response distinct pair IDs must not exceed scanned_count"
        }
        require(pairs.sortedWith(MEMORY_SEMANTIC_DUPLICATE_SUGGESTION_PAIR_COMPARATOR) == pairs) {
            "memory.semantic_duplicate_suggestions.list response pairs must be sorted by score descending then canonical entry ID order"
        }
        val aggregateEntryIdUtf8Bytes = pairs.sumOf { pair ->
            pair.entryIds.sumOf { entryId -> entryId.toByteArray(Charsets.UTF_8).size.toLong() }
        }
        require(
            aggregateEntryIdUtf8Bytes <=
                MAX_MEMORY_SEMANTIC_DUPLICATE_SUGGESTION_ID_AGGREGATE_UTF8_BYTES
        ) {
            "memory.semantic_duplicate_suggestions.list response entry_ids must not exceed 128 KiB of aggregate UTF-8 bytes"
        }
    }
}

@Serializable
private data class MemorySemanticDuplicateClustersListRequestPayloadSurrogate(
    @SerialName("embedding_model_id") val embeddingModelId: String,
    @SerialName("minimum_similarity_basis_points") val minimumSimilarityBasisPoints: Int,
)

object MemorySemanticDuplicateClustersListRequestPayloadSerializer :
    KSerializer<MemorySemanticDuplicateClustersListRequestPayload> by object :
    ExactJsonObjectTransformingSerializer<
        MemorySemanticDuplicateClustersListRequestPayload,
        MemorySemanticDuplicateClustersListRequestPayloadSurrogate
    >(
        MemorySemanticDuplicateClustersListRequestPayloadSurrogate.serializer(),
        setOf("embedding_model_id", "minimum_similarity_basis_points"),
        "memory.semantic_duplicate_clusters.list request",
        validatePayload = { payload ->
            payload.requireJsonInteger(
                "minimum_similarity_basis_points",
                "memory.semantic_duplicate_clusters.list request",
            )
        },
    ) {
    override fun fromSurrogate(value: MemorySemanticDuplicateClustersListRequestPayloadSurrogate) =
        MemorySemanticDuplicateClustersListRequestPayload(
            embeddingModelId = value.embeddingModelId,
            minimumSimilarityBasisPoints = value.minimumSimilarityBasisPoints,
        )

    override fun toSurrogate(value: MemorySemanticDuplicateClustersListRequestPayload) =
        MemorySemanticDuplicateClustersListRequestPayloadSurrogate(
            embeddingModelId = value.embeddingModelId,
            minimumSimilarityBasisPoints = value.minimumSimilarityBasisPoints,
        )
}

@Serializable(with = MemorySemanticDuplicateClustersListRequestPayloadSerializer::class)
data class MemorySemanticDuplicateClustersListRequestPayload(
    @SerialName("embedding_model_id") val embeddingModelId: String,
    @SerialName("minimum_similarity_basis_points") val minimumSimilarityBasisPoints: Int,
) {
    init {
        require(embeddingModelId.isNotBlank()) {
            "memory.semantic_duplicate_clusters.list request embedding_model_id must be nonblank"
        }
        require(isCanonicalProviderQualifiedModelId(embeddingModelId)) {
            "memory.semantic_duplicate_clusters.list request embedding_model_id must be provider-qualified"
        }
        require(Charsets.UTF_8.newEncoder().canEncode(embeddingModelId)) {
            "memory.semantic_duplicate_clusters.list request embedding_model_id must be valid UTF-8 encodable Unicode"
        }
        require(
            embeddingModelId.codePointCount(0, embeddingModelId.length) <=
                MAX_MEMORY_SEMANTIC_DUPLICATE_SUGGESTION_EMBEDDING_MODEL_ID_LENGTH
        ) {
            "memory.semantic_duplicate_clusters.list request embedding_model_id must be at most 256 Unicode code points"
        }
        require(minimumSimilarityBasisPoints in 8_000..10_000) {
            "memory.semantic_duplicate_clusters.list request minimum_similarity_basis_points must be between 8000 and 10000"
        }
    }
}

@Serializable
private data class MemorySemanticDuplicateClusterPayloadSurrogate(
    @SerialName("entry_ids") val entryIds: List<String>,
    @SerialName("minimum_similarity_basis_points") val minimumSimilarityBasisPoints: Int,
)

object MemorySemanticDuplicateClusterPayloadSerializer :
    KSerializer<MemorySemanticDuplicateClusterPayload> by object :
    ExactJsonObjectTransformingSerializer<
        MemorySemanticDuplicateClusterPayload,
        MemorySemanticDuplicateClusterPayloadSurrogate
    >(
        MemorySemanticDuplicateClusterPayloadSurrogate.serializer(),
        setOf("entry_ids", "minimum_similarity_basis_points"),
        "memory.semantic_duplicate_clusters.list response cluster",
        validatePayload = { payload ->
            payload.requireJsonInteger(
                "minimum_similarity_basis_points",
                "memory.semantic_duplicate_clusters.list response cluster",
            )
        },
    ) {
    override fun fromSurrogate(value: MemorySemanticDuplicateClusterPayloadSurrogate) =
        MemorySemanticDuplicateClusterPayload(
            entryIds = value.entryIds,
            minimumSimilarityBasisPoints = value.minimumSimilarityBasisPoints,
        )

    override fun toSurrogate(value: MemorySemanticDuplicateClusterPayload) =
        MemorySemanticDuplicateClusterPayloadSurrogate(
            entryIds = value.entryIds,
            minimumSimilarityBasisPoints = value.minimumSimilarityBasisPoints,
        )
}

@Serializable(with = MemorySemanticDuplicateClusterPayloadSerializer::class)
data class MemorySemanticDuplicateClusterPayload(
    @SerialName("entry_ids") val entryIds: List<String>,
    @SerialName("minimum_similarity_basis_points") val minimumSimilarityBasisPoints: Int,
) {
    init {
        require(entryIds.size in 2..MAX_MEMORY_SEMANTIC_DUPLICATE_CLUSTER_SIZE) {
            "memory.semantic_duplicate_clusters.list response cluster entry_ids must contain 2 to 200 IDs"
        }
        require(entryIds.all { it.isNotBlank() }) {
            "memory.semantic_duplicate_clusters.list response entry_ids must be nonblank"
        }
        require(entryIds.all { Charsets.UTF_8.newEncoder().canEncode(it) }) {
            "memory.semantic_duplicate_clusters.list response entry_ids must be valid UTF-8 encodable Unicode"
        }
        require(entryIds.distinct().size == entryIds.size) {
            "memory.semantic_duplicate_clusters.list response cluster entry_ids must be unique"
        }
        require(entryIds.sortedWith(CANONICAL_UNSIGNED_UTF8_STRING_COMPARATOR) == entryIds) {
            "memory.semantic_duplicate_clusters.list response cluster entry_ids must use canonical unsigned UTF-8 byte order"
        }
        require(minimumSimilarityBasisPoints in 0..10_000) {
            "memory.semantic_duplicate_clusters.list response cluster minimum_similarity_basis_points must be between 0 and 10000"
        }
    }
}

private fun compareCanonicalIdArrays(left: List<String>, right: List<String>): Int {
    val sharedSize = minOf(left.size, right.size)
    for (index in 0 until sharedSize) {
        val comparison = CANONICAL_UNSIGNED_UTF8_STRING_COMPARATOR.compare(left[index], right[index])
        if (comparison != 0) return comparison
    }
    return left.size.compareTo(right.size)
}

private val MEMORY_SEMANTIC_DUPLICATE_CLUSTER_COMPARATOR =
    Comparator<MemorySemanticDuplicateClusterPayload> { left, right ->
        val scoreComparison = right.minimumSimilarityBasisPoints.compareTo(
            left.minimumSimilarityBasisPoints,
        )
        if (scoreComparison != 0) return@Comparator scoreComparison
        compareCanonicalIdArrays(left.entryIds, right.entryIds)
    }

@Serializable
private data class MemorySemanticDuplicateClustersListResultPayloadSurrogate(
    val clusters: List<MemorySemanticDuplicateClusterPayload>,
    @SerialName("scanned_count") val scannedCount: Int,
    @SerialName("omitted_count") val omittedCount: Int,
    val truncated: Boolean,
)

object MemorySemanticDuplicateClustersListResultPayloadSerializer :
    KSerializer<MemorySemanticDuplicateClustersListResultPayload> by object :
    ExactJsonObjectTransformingSerializer<
        MemorySemanticDuplicateClustersListResultPayload,
        MemorySemanticDuplicateClustersListResultPayloadSurrogate
    >(
        MemorySemanticDuplicateClustersListResultPayloadSurrogate.serializer(),
        setOf("clusters", "scanned_count", "omitted_count", "truncated"),
        "memory.semantic_duplicate_clusters.list response",
        validatePayload = { payload ->
            payload.requireJsonInteger(
                "scanned_count",
                "memory.semantic_duplicate_clusters.list response",
            )
            payload.requireJsonInteger(
                "omitted_count",
                "memory.semantic_duplicate_clusters.list response",
            )
            payload.requireJsonBoolean(
                "truncated",
                "memory.semantic_duplicate_clusters.list response",
            )
        },
    ) {
    override fun fromSurrogate(value: MemorySemanticDuplicateClustersListResultPayloadSurrogate) =
        MemorySemanticDuplicateClustersListResultPayload(
            clusters = value.clusters,
            scannedCount = value.scannedCount,
            omittedCount = value.omittedCount,
            truncated = value.truncated,
        )

    override fun toSurrogate(value: MemorySemanticDuplicateClustersListResultPayload) =
        MemorySemanticDuplicateClustersListResultPayloadSurrogate(
            clusters = value.clusters,
            scannedCount = value.scannedCount,
            omittedCount = value.omittedCount,
            truncated = value.truncated,
        )
}

@Serializable(with = MemorySemanticDuplicateClustersListResultPayloadSerializer::class)
data class MemorySemanticDuplicateClustersListResultPayload(
    val clusters: List<MemorySemanticDuplicateClusterPayload>,
    @SerialName("scanned_count") val scannedCount: Int,
    @SerialName("omitted_count") val omittedCount: Int,
    val truncated: Boolean,
) {
    init {
        require(clusters.size <= MAX_MEMORY_SEMANTIC_DUPLICATE_CLUSTERS) {
            "memory.semantic_duplicate_clusters.list response clusters must contain at most 100 clusters"
        }
        require(scannedCount in 0..MAX_MEMORY_SEMANTIC_DUPLICATE_CLUSTER_SCANNED_COUNT) {
            "memory.semantic_duplicate_clusters.list response scanned_count must be between 0 and 200"
        }
        require(omittedCount in 0..MAX_MEMORY_SEMANTIC_DUPLICATE_CLUSTER_SCANNED_COUNT) {
            "memory.semantic_duplicate_clusters.list response omitted_count must be between 0 and 200"
        }
        require(clusters.sortedWith(MEMORY_SEMANTIC_DUPLICATE_CLUSTER_COMPARATOR) == clusters) {
            "memory.semantic_duplicate_clusters.list response clusters must be sorted by minimum score descending then canonical entry ID-array order"
        }
        val entryIds = clusters.flatMap(MemorySemanticDuplicateClusterPayload::entryIds)
        require(entryIds.distinct().size == entryIds.size) {
            "memory.semantic_duplicate_clusters.list response entry_ids must not repeat across clusters"
        }
        require(entryIds.size <= scannedCount) {
            "memory.semantic_duplicate_clusters.list response distinct cluster IDs must not exceed scanned_count"
        }
        val aggregateEntryIdUtf8Bytes = entryIds.sumOf { entryId ->
            entryId.toByteArray(Charsets.UTF_8).size.toLong()
        }
        require(
            aggregateEntryIdUtf8Bytes <=
                MAX_MEMORY_SEMANTIC_DUPLICATE_CLUSTER_ID_AGGREGATE_UTF8_BYTES
        ) {
            "memory.semantic_duplicate_clusters.list response entry_ids must not exceed 128 KiB of aggregate UTF-8 bytes"
        }
    }
}

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
private data class MemorySummaryDraftGenerateRequestPayloadSurrogate(
    @SerialName("draft_id") val draftId: String,
    val model: String,
    @SerialName("expected_session_id") val expectedSessionId: String,
    @SerialName("expected_source_message_count") val expectedSourceMessageCount: Int,
)

object MemorySummaryDraftGenerateRequestPayloadSerializer : KSerializer<MemorySummaryDraftGenerateRequestPayload> {
    override val descriptor: SerialDescriptor = MemorySummaryDraftGenerateRequestPayloadSurrogate.serializer().descriptor

    override fun deserialize(decoder: Decoder): MemorySummaryDraftGenerateRequestPayload {
        val (jsonDecoder, payload) = decoder.decodeExactJsonObject(
            MEMORY_SUMMARY_DRAFT_GENERATE_REQUEST_FIELDS,
            "memory.summary.draft.generate request payload",
        )
        val surrogate = jsonDecoder.json.decodeFromJsonElement(
            MemorySummaryDraftGenerateRequestPayloadSurrogate.serializer(),
            payload,
        )
        return MemorySummaryDraftGenerateRequestPayload(
            draftId = surrogate.draftId,
            model = surrogate.model,
            expectedSessionId = surrogate.expectedSessionId,
            expectedSourceMessageCount = surrogate.expectedSourceMessageCount,
        )
    }

    override fun serialize(encoder: Encoder, value: MemorySummaryDraftGenerateRequestPayload) {
        encoder.encodeSerializableValue(
            MemorySummaryDraftGenerateRequestPayloadSurrogate.serializer(),
            MemorySummaryDraftGenerateRequestPayloadSurrogate(
                draftId = value.draftId,
                model = value.model,
                expectedSessionId = value.expectedSessionId,
                expectedSourceMessageCount = value.expectedSourceMessageCount,
            ),
        )
    }
}

@Serializable(with = MemorySummaryDraftGenerateRequestPayloadSerializer::class)
data class MemorySummaryDraftGenerateRequestPayload(
    @SerialName("draft_id") val draftId: String,
    val model: String,
    @SerialName("expected_session_id") val expectedSessionId: String,
    @SerialName("expected_source_message_count") val expectedSourceMessageCount: Int,
) {
    init {
        require(draftId.isNotBlank()) {
            "memory.summary.draft.generate request draft_id must be nonblank"
        }
        require(model.isNotBlank()) {
            "memory.summary.draft.generate request model must be nonblank"
        }
        require(expectedSessionId.isNotBlank()) {
            "memory.summary.draft.generate request expected_session_id must be nonblank"
        }
        require(expectedSourceMessageCount > 0) {
            "memory.summary.draft.generate request expected_source_message_count must be positive"
        }
    }
}

@Serializable
private data class MemorySummaryDraftGenerateResultPayloadSurrogate(
    val draft: MemorySummaryDraftPayload,
)

object MemorySummaryDraftGenerateResultPayloadSerializer : KSerializer<MemorySummaryDraftGenerateResultPayload> {
    override val descriptor: SerialDescriptor = MemorySummaryDraftGenerateResultPayloadSurrogate.serializer().descriptor

    override fun deserialize(decoder: Decoder): MemorySummaryDraftGenerateResultPayload {
        val (jsonDecoder, payload) = decoder.decodeExactJsonObject(
            MEMORY_SUMMARY_DRAFT_GENERATE_RESULT_FIELDS,
            "memory.summary.draft.generate response payload",
        )
        val surrogate = jsonDecoder.json.decodeFromJsonElement(
            MemorySummaryDraftGenerateResultPayloadSurrogate.serializer(),
            payload,
        )
        return MemorySummaryDraftGenerateResultPayload(draft = surrogate.draft)
    }

    override fun serialize(encoder: Encoder, value: MemorySummaryDraftGenerateResultPayload) {
        encoder.encodeSerializableValue(
            MemorySummaryDraftGenerateResultPayloadSurrogate.serializer(),
            MemorySummaryDraftGenerateResultPayloadSurrogate(draft = value.draft),
        )
    }
}

@Serializable(with = MemorySummaryDraftGenerateResultPayloadSerializer::class)
data class MemorySummaryDraftGenerateResultPayload(
    val draft: MemorySummaryDraftPayload,
)

private val MEMORY_SUMMARY_DRAFT_GENERATE_REQUEST_FIELDS = setOf(
    "draft_id",
    "model",
    "expected_session_id",
    "expected_source_message_count",
)
private val MEMORY_SUMMARY_DRAFT_GENERATE_RESULT_FIELDS = setOf("draft")

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
private data class MemorySummaryDraftPayloadSurrogate(
    val id: String,
    val session: MemorySummaryDraftSessionPayload,
    @SerialName("source_message_count") val sourceMessageCount: Int,
    @SerialName("source_range") val sourceRange: String,
    @SerialName("source_pointers") val sourcePointers: List<MemorySummaryDraftSourcePointerPayload>,
    @SerialName("summary_preview") val summaryPreview: String,
    @SerialName("summary_method") val summaryMethod: String? = null,
    @SerialName("generated_at") val generatedAt: String? = null,
    @SerialName("generated_model_id") val generatedModelId: String? = null,
)

object MemorySummaryDraftPayloadSerializer : KSerializer<MemorySummaryDraftPayload> {
    override val descriptor: SerialDescriptor = MemorySummaryDraftPayloadSurrogate.serializer().descriptor

    override fun deserialize(decoder: Decoder): MemorySummaryDraftPayload {
        val (jsonDecoder, payload) = decoder.decodeExactJsonObject(
            MEMORY_SUMMARY_DRAFT_FIELDS,
            "memory summary draft payload",
        )
        val surrogate = jsonDecoder.json.decodeFromJsonElement(MemorySummaryDraftPayloadSurrogate.serializer(), payload)
        return MemorySummaryDraftPayload(
            id = surrogate.id,
            session = surrogate.session,
            sourceMessageCount = surrogate.sourceMessageCount,
            sourceRange = surrogate.sourceRange,
            sourcePointers = surrogate.sourcePointers,
            summaryPreview = surrogate.summaryPreview,
            summaryMethod = surrogate.summaryMethod ?: "deterministic_preview",
            generatedAt = surrogate.generatedAt,
            generatedModelId = surrogate.generatedModelId,
        )
    }

    override fun serialize(encoder: Encoder, value: MemorySummaryDraftPayload) {
        encoder.encodeSerializableValue(
            MemorySummaryDraftPayloadSurrogate.serializer(),
            MemorySummaryDraftPayloadSurrogate(
                id = value.id,
                session = value.session,
                sourceMessageCount = value.sourceMessageCount,
                sourceRange = value.sourceRange,
                sourcePointers = value.sourcePointers,
                summaryPreview = value.summaryPreview,
                summaryMethod = value.summaryMethod,
                generatedAt = value.generatedAt,
                generatedModelId = value.generatedModelId,
            ),
        )
    }
}

@Serializable(with = MemorySummaryDraftPayloadSerializer::class)
data class MemorySummaryDraftPayload(
    val id: String,
    val session: MemorySummaryDraftSessionPayload,
    @SerialName("source_message_count") val sourceMessageCount: Int,
    @SerialName("source_range") val sourceRange: String,
    @SerialName("source_pointers") val sourcePointers: List<MemorySummaryDraftSourcePointerPayload>,
    @SerialName("summary_preview") val summaryPreview: String,
    @SerialName("summary_method") val summaryMethod: String = "deterministic_preview",
    @SerialName("generated_at") val generatedAt: String? = null,
    @SerialName("generated_model_id") val generatedModelId: String? = null,
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
        require(summaryMethod in MEMORY_SUMMARY_DRAFT_METHODS) {
            "memory summary draft summary_method must be deterministic_preview or llm_summary_v1"
        }
        requireProtocolDateTime(generatedAt, "memory summary draft generated_at")
        require(generatedModelId == null || generatedModelId.isNotBlank()) {
            "memory summary draft generated_model_id must be nonblank"
        }
    }
}

private val MEMORY_SUMMARY_DRAFT_FIELDS = setOf(
    "id",
    "session",
    "source_message_count",
    "source_range",
    "source_pointers",
    "summary_preview",
    "summary_method",
    "generated_at",
    "generated_model_id",
)

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
