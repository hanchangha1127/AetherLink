package com.localagentbridge.android.core.protocol

import kotlinx.serialization.encodeToString
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.boolean
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
        )

        val json = Json.parseToJsonElement(Json.encodeToString(payload)).jsonObject
        val decoded = Json.decodeFromString<ChatSendPayload>(Json.encodeToString(payload))

        assertEquals("session-1", json["session_id"]?.jsonPrimitive?.content)
        assertEquals("ollama:llama3.1:8b", json["model"]?.jsonPrimitive?.content)
        assertEquals("fr", json["locale"]?.jsonPrimitive?.content)
        assertEquals("fr", decoded.locale)
    }

    @Test
    fun chatHistorySessionPayloadsUseProtocolFieldNames() {
        val request = ChatSessionsListRequestPayload(limit = 50, includeArchived = true)
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
                ),
            ),
        )

        val requestJson = Json.parseToJsonElement(Json.encodeToString(request)).jsonObject
        val resultJson = Json.parseToJsonElement(Json.encodeToString(result)).jsonObject
        val decoded = Json.decodeFromString<ChatSessionsListResultPayload>(Json.encodeToString(result))

        assertEquals("50", requestJson["limit"]?.jsonPrimitive?.content)
        assertEquals("true", requestJson["include_archived"]?.jsonPrimitive?.content)
        val session = resultJson["sessions"]?.jsonArray?.first()?.jsonObject
        assertEquals("session-1", session?.get("session_id")?.jsonPrimitive?.content)
        assertEquals("Runtime history", session?.get("title")?.jsonPrimitive?.content)
        assertEquals("ollama:llama3.1:8b", session?.get("model")?.jsonPrimitive?.content)
        assertEquals("2026-06-23T09:02:05Z", session?.get("last_activity_at")?.jsonPrimitive?.content)
        assertEquals("2", session?.get("message_count")?.jsonPrimitive?.content)
        assertEquals("archived", session?.get("status")?.jsonPrimitive?.content)
        assertEquals("2026-06-23T09:05:05Z", session?.get("archived_at")?.jsonPrimitive?.content)
        assertEquals("session-1", decoded.sessions.first().sessionId)
        assertEquals("archived", decoded.sessions.first().status)
        assertEquals("2026-06-23T09:05:05Z", decoded.sessions.first().archivedAt)
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
                        ChatAttachmentPayload(
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
        assertEquals("2026-06-23T09:02:06Z", message?.get("created_at")?.jsonPrimitive?.content)
        assertEquals("Short thought", decoded.messages.first().reasoning)
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
    fun chatDeltaPayloadAcceptsCompatibilityAliases() {
        val textAlias = Json.decodeFromString<ChatDeltaPayload>("""{"text":"hello"}""")
        val thinkingAlias = Json.decodeFromString<ChatDeltaPayload>("""{"thinking_delta":"plan"}""")

        assertEquals("hello", textAlias.content)
        assertEquals("plan", thinkingAlias.reasoning)
    }

    @Test
    fun memoryPayloadsUseProtocolFieldNames() {
        val protocolJson = Json { encodeDefaults = true }
        val entry = MemoryEntryPayload(
            id = "memory-1",
            content = "Prefers concise answers.",
            enabled = true,
            createdAt = "2026-06-25T05:25:00Z",
            updatedAt = "2026-06-25T05:26:00Z",
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

        val listJson = Json.parseToJsonElement(protocolJson.encodeToString(listResult)).jsonObject
        val upsertJson = Json.parseToJsonElement(Json.encodeToString(upsert)).jsonObject
        val deleteJson = Json.parseToJsonElement(Json.encodeToString(deleteResult)).jsonObject
        val listedEntry = listJson["entries"]?.jsonArray?.first()?.jsonObject

        assertEquals(MessageType.MemoryList, "memory.list")
        assertEquals(MessageType.MemoryUpsert, "memory.upsert")
        assertEquals(MessageType.MemoryDelete, "memory.delete")
        assertEquals("memory-1", listedEntry?.get("id")?.jsonPrimitive?.content)
        assertEquals("Prefers concise answers.", listedEntry?.get("content")?.jsonPrimitive?.content)
        assertEquals(true, listedEntry?.get("enabled")?.jsonPrimitive?.boolean)
        assertEquals("2026-06-25T05:25:00Z", listedEntry?.get("created_at")?.jsonPrimitive?.content)
        assertEquals("2026-06-25T05:26:00Z", listedEntry?.get("updated_at")?.jsonPrimitive?.content)
        assertEquals("memory-1", upsertJson["id"]?.jsonPrimitive?.content)
        assertEquals("Prefers concise Korean answers.", upsertJson["content"]?.jsonPrimitive?.content)
        assertEquals(false, upsertJson["enabled"]?.jsonPrimitive?.boolean)
        assertEquals("memory-1", deleteJson["id"]?.jsonPrimitive?.content)
        assertEquals("2026-06-25T05:27:00Z", deleteJson["deleted_at"]?.jsonPrimitive?.content)
    }
}
