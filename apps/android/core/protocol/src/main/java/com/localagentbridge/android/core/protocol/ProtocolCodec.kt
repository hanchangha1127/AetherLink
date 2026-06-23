package com.localagentbridge.android.core.protocol

import kotlinx.serialization.KSerializer
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.encodeToJsonElement
import java.io.ByteArrayOutputStream
import java.io.EOFException
import java.io.InputStream
import java.nio.ByteBuffer

class ProtocolCodec(
    private val json: Json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
        encodeDefaults = true
    },
) {
    fun encode(envelope: ProtocolEnvelope): ByteArray {
        val body = json.encodeToString(envelope).encodeToByteArray()
        val prefix = ByteBuffer.allocate(4).putInt(body.size).array()
        return prefix + body
    }

    fun decode(bytes: ByteArray): ProtocolEnvelope {
        return json.decodeFromString(ProtocolEnvelope.serializer(), bytes.decodeToString())
    }

    fun readFrame(input: InputStream): ProtocolEnvelope {
        val lengthBytes = input.readExactly(4)
        val length = ByteBuffer.wrap(lengthBytes).int
        require(length in 1..MAX_FRAME_BYTES) { "Invalid frame length: $length" }
        return decode(input.readExactly(length))
    }

    fun <T> envelope(
        type: String,
        payloadSerializer: KSerializer<T>,
        payload: T,
        requestId: String? = null,
    ): ProtocolEnvelope {
        return ProtocolEnvelope(
            type = type,
            requestId = requestId ?: java.util.UUID.randomUUID().toString(),
            payload = json.encodeToJsonElement(payloadSerializer, payload).jsonObject(),
        )
    }

    companion object {
        const val MAX_FRAME_BYTES = 1024 * 1024
    }
}

private fun InputStream.readExactly(size: Int): ByteArray {
    val buffer = ByteArrayOutputStream(size)
    val chunk = ByteArray(size)
    var remaining = size
    while (remaining > 0) {
        val read = read(chunk, 0, remaining.coerceAtMost(chunk.size))
        if (read == -1) throw EOFException("Stream ended while reading frame")
        buffer.write(chunk, 0, read)
        remaining -= read
    }
    return buffer.toByteArray()
}

private fun kotlinx.serialization.json.JsonElement.jsonObject(): kotlinx.serialization.json.JsonObject {
    return this as kotlinx.serialization.json.JsonObject
}

