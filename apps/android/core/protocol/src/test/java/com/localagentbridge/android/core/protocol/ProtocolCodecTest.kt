package com.localagentbridge.android.core.protocol

import kotlinx.serialization.encodeToString
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
}
