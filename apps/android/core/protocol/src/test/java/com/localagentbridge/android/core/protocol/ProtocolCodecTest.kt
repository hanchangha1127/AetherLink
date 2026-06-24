package com.localagentbridge.android.core.protocol

import kotlinx.serialization.encodeToString
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.ByteArrayInputStream

class ProtocolCodecTest {
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
    }

    @Test
    fun chatHistorySessionPayloadsUseProtocolFieldNames() {
        val request = ChatSessionsListRequestPayload(limit = 50)
        val result = ChatSessionsListResultPayload(
            sessions = listOf(
                ChatSessionSummaryPayload(
                    sessionId = "session-1",
                    title = "Runtime history",
                    model = "ollama:llama3.1:8b",
                    lastActivityAt = "2026-06-23T09:02:05Z",
                    messageCount = 2,
                ),
            ),
        )

        val requestJson = Json.parseToJsonElement(Json.encodeToString(request)).jsonObject
        val resultJson = Json.parseToJsonElement(Json.encodeToString(result)).jsonObject
        val decoded = Json.decodeFromString<ChatSessionsListResultPayload>(Json.encodeToString(result))

        assertEquals("50", requestJson["limit"]?.jsonPrimitive?.content)
        val session = resultJson["sessions"]?.jsonArray?.first()?.jsonObject
        assertEquals("session-1", session?.get("session_id")?.jsonPrimitive?.content)
        assertEquals("Runtime history", session?.get("title")?.jsonPrimitive?.content)
        assertEquals("ollama:llama3.1:8b", session?.get("model")?.jsonPrimitive?.content)
        assertEquals("2026-06-23T09:02:05Z", session?.get("last_activity_at")?.jsonPrimitive?.content)
        assertEquals("2", session?.get("message_count")?.jsonPrimitive?.content)
        assertEquals("session-1", decoded.sessions.first().sessionId)
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
        assertEquals("2026-06-23T09:02:06Z", message?.get("created_at")?.jsonPrimitive?.content)
        assertEquals("Short thought", decoded.messages.first().reasoning)
    }
}
