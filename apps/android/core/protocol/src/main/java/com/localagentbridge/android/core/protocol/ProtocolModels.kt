package com.localagentbridge.android.core.protocol

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.KSerializer
import kotlinx.serialization.descriptors.PrimitiveKind
import kotlinx.serialization.descriptors.PrimitiveSerialDescriptor
import kotlinx.serialization.descriptors.SerialDescriptor
import kotlinx.serialization.encoding.Decoder
import kotlinx.serialization.encoding.Encoder
import kotlinx.serialization.json.JsonObject
import java.time.Instant
import java.util.UUID

const val PROTOCOL_VERSION = 1

private val SOURCE_ANCHOR_ID_PATTERN = Regex("^source_anchor_[0-9a-f]{16}$")

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
)

@Serializable
data class AuthChallengePayload(
    @SerialName("device_id") val deviceId: String? = null,
    val nonce: String,
    @SerialName("runtime_key_fingerprint") val runtimeKeyFingerprint: String? = null,
    @SerialName("runtime_signature") val runtimeSignature: String? = null,
)

@Serializable
data class AuthResponsePayload(
    @SerialName("device_id") val deviceId: String? = null,
    val nonce: String? = null,
    val signature: String? = null,
    val accepted: Boolean? = null,
    val message: String? = null,
)

@Serializable
data class PairingRequestPayload(
    @SerialName("pairing_nonce") val pairingNonce: String,
    @SerialName("pairing_code") val pairingCode: String,
    @SerialName("device_id") val deviceId: String,
    @SerialName("device_name") val deviceName: String,
    @SerialName("public_key") val publicKey: String,
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
)

@Serializable
data class ModelsResultPayload(
    val models: List<ModelInfoPayload>,
)

@Serializable
data class ModelPullPayload(
    val model: String,
)

@Serializable
data class ModelPullResultPayload(
    val model: String? = null,
    val id: String? = null,
    val accepted: Boolean? = null,
    val success: Boolean? = null,
    val status: String? = null,
    val message: String? = null,
)

@Serializable
data class RouteRefreshPayload(
    @SerialName("runtime_device_id") val runtimeDeviceId: String? = null,
    @SerialName("runtime_key_fingerprint") val runtimeKeyFingerprint: String? = null,
    @SerialName("relay_host") val relayHost: String? = null,
    @SerialName("relay_port") val relayPort: Int? = null,
    @SerialName("relay_id") val relayId: String? = null,
    @SerialName("relay_secret") val relaySecret: String? = null,
    @SerialName("relay_expires_at") val relayExpiresAtEpochMillis: Long? = null,
    @SerialName("relay_nonce") val relayNonce: String? = null,
    @SerialName("relay_scope") val relayScope: String? = null,
    @SerialName("p2p_class") val p2pRouteClass: String? = null,
    @SerialName("p2p_record_id") val p2pRecordId: String? = null,
    @SerialName("p2p_encrypted_body") val p2pEncryptedBody: String? = null,
    @SerialName("p2p_expires_at") val p2pExpiresAtEpochMillis: Long? = null,
    @SerialName("p2p_anti_replay_nonce") val p2pAntiReplayNonce: String? = null,
    @SerialName("p2p_protocol_version") val p2pProtocolVersion: Int? = null,
)

@Serializable
data class ChatMessagePayload(
    val role: String,
    val content: String,
    val attachments: List<ChatAttachmentPayload> = emptyList(),
)

@Serializable
data class ChatAttachmentPayload(
    val type: String,
    @SerialName("mime_type") val mimeType: String,
    val name: String? = null,
    @SerialName("data_base64") val dataBase64: String? = null,
    val text: String? = null,
)

@Serializable
data class ChatSendPayload(
    @SerialName("session_id") val sessionId: String,
    val model: String,
    val messages: List<ChatMessagePayload>,
    val locale: String? = null,
)

@Serializable
data class ChatDeltaPayload(
    val delta: String? = null,
    val text: String? = null,
    @SerialName("reasoning_delta") val reasoningDelta: String? = null,
    @SerialName("thinking_delta") val thinkingDelta: String? = null,
) {
    val content: String
        get() = delta ?: text.orEmpty()

    val reasoning: String
        get() = reasoningDelta ?: thinkingDelta.orEmpty()
}

@Serializable
data class ChatDonePayload(
    @SerialName("finish_reason") val finishReason: String? = null,
    val usage: UsagePayload? = null,
)

@Serializable
data class UsagePayload(
    @SerialName("input_tokens") val inputTokens: Int = 0,
    @SerialName("output_tokens") val outputTokens: Int = 0,
)

@Serializable
data class ChatCancelPayload(
    @SerialName("target_request_id") val targetRequestId: String,
)

@Serializable
data class ChatSessionsListRequestPayload(
    val limit: Int? = null,
    @SerialName("include_archived") val includeArchived: Boolean = false,
    val query: String? = null,
    @SerialName("embedding_model_id") val embeddingModelId: String? = null,
)

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
)

@Serializable
data class ChatSessionSearchPayload(
    val rank: Int,
    val snippet: String,
    @SerialName("matched_fields") val matchedFields: List<String> = emptyList(),
)

@Serializable
data class IndexDocumentsListRequestPayload(
    val limit: Int? = null,
)

@Serializable
data class IndexDocumentsListResultPayload(
    val documents: List<RuntimeDocumentIndexDocumentPayload>,
    val summary: IndexDocumentsSummaryPayload,
)

@Serializable
data class IndexDocumentsSummaryPayload(
    @SerialName("document_count") val documentCount: Int,
    @SerialName("chunk_count") val chunkCount: Int,
    @SerialName("extracted_character_count") val extractedCharacterCount: Int,
    @SerialName("quality_counts") val qualityCounts: IndexDocumentsQualityCountsPayload,
)

@Serializable
data class IndexDocumentsQualityCountsPayload(
    @SerialName("no_usable_text") val noUsableText: Int,
    @SerialName("single_chunk") val singleChunk: Int,
    val chunked: Int,
)

@Serializable
data class RetrievalQueryRequestPayload(
    val query: String,
    val limit: Int? = null,
    @SerialName("max_snippet_characters") val maxSnippetCharacters: Int? = null,
)

@Serializable
data class RetrievalQueryResultPayload(
    val results: List<RetrievalQueryResultItemPayload>,
)

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
)

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
)

@Serializable
data class RuntimeDocumentIndexDocumentPayload(
    val id: String,
    @SerialName("display_name") val displayName: String,
    @SerialName("mime_type") val mimeType: String,
    @SerialName("content_fingerprint") val contentFingerprint: String,
    @SerialName("extracted_character_count") val extractedCharacterCount: Int,
    @SerialName("chunk_count") val chunkCount: Int,
    val quality: String,
)

@Serializable
data class ChatMessagesListRequestPayload(
    @SerialName("session_id") val sessionId: String,
    val limit: Int? = null,
)

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
    val attachments: List<ChatAttachmentPayload> = emptyList(),
    @SerialName("created_at") val createdAt: String? = null,
)

@Serializable
data class ChatTitleRequestPayload(
    @SerialName("session_id") val sessionId: String,
    val model: String,
    val messages: List<ChatMessagePayload>,
    val locale: String? = null,
)

@Serializable
data class ChatTitleResultPayload(
    val title: String,
)

@Serializable
data class ChatSessionRenamePayload(
    @SerialName("session_id") val sessionId: String,
    val title: String,
    @SerialName("renamed_at") val renamedAt: String? = null,
)

@Serializable
data class ChatSessionLifecyclePayload(
    @SerialName("session_id") val sessionId: String,
    val status: String? = null,
    @SerialName("archived_at") val archivedAt: String? = null,
    @SerialName("restored_at") val restoredAt: String? = null,
    @SerialName("deleted_at") val deletedAt: String? = null,
)

@Serializable
data class MemoryListRequestPayload(
    val query: String? = null,
)

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
)

@Serializable
data class MemoryEntrySourcePayload(
    val kind: String,
    @SerialName("draft_id") val draftId: String,
    @SerialName("summary_method") val summaryMethod: String,
    val session: MemorySummaryDraftSessionPayload,
    @SerialName("source_message_count") val sourceMessageCount: Int,
    @SerialName("source_range") val sourceRange: String,
    @SerialName("source_pointers") val sourcePointers: List<MemorySummaryDraftSourcePointerPayload>,
)

@Serializable
data class MemoryUpsertPayload(
    val id: String? = null,
    val content: String,
    val enabled: Boolean? = null,
)

@Serializable
data class MemoryUpsertResultPayload(
    val entry: MemoryEntryPayload,
)

@Serializable
data class MemoryDeletePayload(
    val id: String,
)

@Serializable
data class MemoryDeleteResultPayload(
    val id: String,
    @SerialName("deleted_at") val deletedAt: String? = null,
)

@Serializable
data class MemorySummaryDraftsListRequestPayload(
    val limit: Int? = null,
)

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
)

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
)

@Serializable
data class MemorySummaryDraftDismissResultPayload(
    @SerialName("draft_id") val draftId: String,
    val status: String,
    @SerialName("dismissed_at") val dismissedAt: String? = null,
)

@Serializable
data class MemorySummaryDraftPayload(
    val id: String,
    val session: MemorySummaryDraftSessionPayload,
    @SerialName("source_message_count") val sourceMessageCount: Int,
    @SerialName("source_range") val sourceRange: String,
    @SerialName("source_pointers") val sourcePointers: List<MemorySummaryDraftSourcePointerPayload>,
    @SerialName("summary_preview") val summaryPreview: String,
)

@Serializable
data class MemorySummaryDraftSessionPayload(
    @SerialName("session_id") val sessionId: String,
    val title: String,
    val model: String,
    @SerialName("last_activity_at") val lastActivityAt: String,
    @SerialName("message_count") val messageCount: Int,
    @SerialName("inactive_seconds") val inactiveSeconds: Long,
)

@Serializable
data class MemorySummaryDraftSourcePointerPayload(
    @SerialName("session_id") val sessionId: String,
    @SerialName("message_index") val messageIndex: Int,
    val role: String,
    @SerialName("created_at") val createdAt: String? = null,
    val excerpt: String,
)

@Serializable
data class ErrorPayload(
    val code: String,
    val message: String,
    val retryable: Boolean,
)

@Serializable
data class RuntimeHealthPayload(
    val status: String,
    val ollama: RuntimeBackendStatusPayload? = null,
    @SerialName("lm_studio") val lmStudio: RuntimeBackendStatusPayload? = null,
    @SerialName("model_residency") val modelResidency: RuntimeModelResidencyPayload? = null,
)

@Serializable
data class RuntimeBackendStatusPayload(
    val available: Boolean,
    val message: String,
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
)

@Serializable
data class RuntimeModelResidencyUnloadFailurePayload(
    val provider: String,
    @SerialName("model_id") val modelId: String,
    val reason: String,
)
