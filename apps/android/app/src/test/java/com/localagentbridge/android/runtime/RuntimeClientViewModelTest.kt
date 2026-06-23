package com.localagentbridge.android.runtime

import com.localagentbridge.android.core.protocol.ChatCancelPayload
import com.localagentbridge.android.core.protocol.ChatDeltaPayload
import com.localagentbridge.android.core.protocol.ChatDonePayload
import com.localagentbridge.android.core.protocol.ErrorPayload
import com.localagentbridge.android.core.protocol.MessageType
import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import kotlinx.serialization.KSerializer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.encodeToJsonElement
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test

class RuntimeClientViewModelTest {
    @Test
    fun trustedRuntimeConnectionTargetUsesTrustedMacInsteadOfManualHostFields() {
        val state = RuntimeUiState(
            macHost = "127.0.0.1",
            macPort = "11434",
            trustedMac = RuntimeTrustedMac(
                deviceId = "mac-1",
                name = "AetherLink Mac",
                host = "192.168.1.20",
                port = 43170,
            ),
        )

        val target = trustedRuntimeConnectionTarget(state)

        assertEquals("192.168.1.20", target?.host)
        assertEquals(43170, target?.port)
    }

    @Test
    fun staleChatDeltaAndDoneForDifferentRequestIdAreIgnored() {
        val state = RuntimeUiState(
            messages = listOf(
                RuntimeChatMessage(role = "user", content = "Hello"),
                RuntimeChatMessage(role = "assistant", content = "Partial"),
            ),
            isStreaming = true,
            activeRequestId = "active-request",
        )

        val afterDelta = state.withChatDelta(
            envelope(
                type = MessageType.ChatDelta,
                requestId = "stale-request",
                serializer = ChatDeltaPayload.serializer(),
                payload = ChatDeltaPayload(delta = " stale"),
            ),
            ChatDeltaPayload(delta = " stale"),
        )
        val afterDone = afterDelta.withChatDone(
            envelope(
                type = MessageType.ChatDone,
                requestId = "stale-request",
                serializer = ChatDonePayload.serializer(),
                payload = ChatDonePayload(),
            ),
            ChatDonePayload(),
        )

        assertSame(state, afterDelta)
        assertSame(afterDelta, afterDone)
        assertTrue(afterDone.isStreaming)
        assertEquals("active-request", afterDone.activeRequestId)
        assertEquals("Partial", afterDone.messages.last().content)
    }

    @Test
    fun cancelAckAndErrorForUnrelatedRequestsDoNotClearActiveStreaming() {
        val state = RuntimeUiState(
            messages = listOf(RuntimeChatMessage(role = "assistant", content = "Partial")),
            isStreaming = true,
            activeRequestId = "active-request",
            isLoadingModels = true,
            installingModelId = "lm_studio:model",
        )

        val afterCancel = state.withChatCancelAck(
            envelope(
                type = MessageType.ChatCancel,
                requestId = "cancel-request",
                serializer = ChatCancelPayload.serializer(),
                payload = ChatCancelPayload(targetRequestId = "other-request"),
            ),
            ChatCancelPayload(targetRequestId = "other-request"),
        )
        val afterError = afterCancel.withRuntimeError(
            envelope(
                type = MessageType.Error,
                requestId = "other-request",
                serializer = ErrorPayload.serializer(),
                payload = ErrorPayload(
                    code = "backend_failed",
                    message = "Different request failed",
                    retryable = false,
                ),
            ),
            ErrorPayload(
                code = "backend_failed",
                message = "Different request failed",
                retryable = false,
            ),
            pendingModelPullRequestId = "model-pull-request",
        )

        assertSame(state, afterCancel)
        assertTrue(afterError.isStreaming)
        assertEquals("active-request", afterError.activeRequestId)
        assertEquals("lm_studio:model", afterError.installingModelId)
        assertFalse(afterError.isLoadingModels)
        assertEquals("backend_failed", afterError.error?.code)
        assertEquals("Different request failed", afterError.error?.detail)
    }

    @Test
    fun activeChatDoneAndCancelClearStreamingOnlyForActiveRequest() {
        val state = RuntimeUiState(
            isStreaming = true,
            activeRequestId = "active-request",
            error = RuntimeUiError("previous_error"),
        )

        val afterDone = state.withChatDone(
            envelope(
                type = MessageType.ChatDone,
                requestId = "active-request",
                serializer = ChatDonePayload.serializer(),
                payload = ChatDonePayload(finishReason = "cancelled"),
            ),
            ChatDonePayload(finishReason = "cancelled"),
        )
        val afterCancel = state.withChatCancelAck(
            envelope(
                type = MessageType.ChatCancel,
                requestId = "cancel-request",
                serializer = ChatCancelPayload.serializer(),
                payload = ChatCancelPayload(targetRequestId = "active-request"),
            ),
            ChatCancelPayload(targetRequestId = "active-request"),
        )

        assertFalse(afterDone.isStreaming)
        assertNull(afterDone.activeRequestId)
        assertEquals("generation_cancelled", afterDone.error?.code)
        assertFalse(afterCancel.isStreaming)
        assertNull(afterCancel.activeRequestId)
        assertNull(afterCancel.error)
    }

    private fun <T> envelope(
        type: String,
        requestId: String,
        serializer: KSerializer<T>,
        payload: T,
    ): ProtocolEnvelope {
        return ProtocolEnvelope(
            type = type,
            requestId = requestId,
            payload = json.encodeToJsonElement(serializer, payload).jsonObject,
        )
    }

    private companion object {
        val json = Json {
            ignoreUnknownKeys = true
            explicitNulls = false
            encodeDefaults = true
        }
    }
}
