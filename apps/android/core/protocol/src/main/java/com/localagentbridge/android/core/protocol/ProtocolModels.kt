package com.localagentbridge.android.core.protocol

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject
import java.time.Instant
import java.util.UUID

const val PROTOCOL_VERSION = 1

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
    const val ChatSend = "chat.send"
    const val ChatDelta = "chat.delta"
    const val ChatDone = "chat.done"
    const val ChatCancel = "chat.cancel"
    const val Error = "error"
}

@Serializable
data class HelloPayload(
    @SerialName("device_id") val deviceId: String,
    @SerialName("device_name") val deviceName: String,
    val capabilities: List<String>,
)

@Serializable
data class AuthChallengePayload(
    val nonce: String,
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
    @SerialName("mac_device_id") val macDeviceId: String? = null,
    @SerialName("trusted_device_id") val trustedDeviceId: String? = null,
    val message: String,
)

@Serializable
data class ModelInfoPayload(
    val id: String,
    val name: String? = null,
    val backend: String? = null,
    val provider: String? = null,
    @SerialName("provider_model_id") val providerModelId: String? = null,
    @SerialName("qualified_id") val qualifiedId: String? = null,
    val installed: Boolean? = null,
    val running: Boolean? = null,
    val source: String? = null,
    val description: String? = null,
    @SerialName("size_bytes") val sizeBytes: Long? = null,
    @SerialName("modified_at") val modifiedAt: String? = null,
    @SerialName("remote_model") val remoteModel: String? = null,
    @SerialName("remote_host") val remoteHost: String? = null,
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
data class ChatMessagePayload(
    val role: String,
    val content: String,
)

@Serializable
data class ChatSendPayload(
    @SerialName("session_id") val sessionId: String,
    val model: String,
    val messages: List<ChatMessagePayload>,
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
)

@Serializable
data class RuntimeBackendStatusPayload(
    val available: Boolean,
    val message: String,
    val code: String? = null,
    val retryable: Boolean? = null,
)
