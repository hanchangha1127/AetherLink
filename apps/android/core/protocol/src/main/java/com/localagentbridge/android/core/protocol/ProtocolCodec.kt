package com.localagentbridge.android.core.protocol

import kotlinx.serialization.KSerializer
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.encodeToJsonElement
import java.io.ByteArrayOutputStream
import java.io.EOFException
import java.io.InputStream
import java.nio.ByteBuffer
import java.time.Instant
import java.time.format.DateTimeParseException

class ProtocolCodec(
    private val json: Json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
        encodeDefaults = true
    },
) {
    fun encode(envelope: ProtocolEnvelope): ByteArray {
        return encodeFrameBody(encodeBody(envelope))
    }

    fun encodeBody(envelope: ProtocolEnvelope): ByteArray {
        return json.encodeToString(envelope).encodeToByteArray()
    }

    fun encodeFrameBody(body: ByteArray): ByteArray {
        require(body.size in 1..MAX_FRAME_BYTES) { "Invalid frame body length: ${body.size}" }
        val prefix = ByteBuffer.allocate(4).putInt(body.size).array()
        return prefix + body
    }

    fun decode(bytes: ByteArray): ProtocolEnvelope {
        val element = json.parseToJsonElement(bytes.decodeToString())
        val envelopeObject = element as? JsonObject
            ?: throw IllegalArgumentException("Protocol envelope must be a JSON object")
        validateEnvelopeFields(envelopeObject)
        return json.decodeFromJsonElement(ProtocolEnvelope.serializer(), envelopeObject)
    }

    private fun validateEnvelopeFields(envelope: JsonObject) {
        val missingFields = REQUIRED_ENVELOPE_FIELDS
            .filterNot { it in envelope }
        require(missingFields.isEmpty()) {
            "Missing protocol envelope field: ${missingFields.first()}"
        }

        val unknownFields = envelope.keys
            .filterNot { it in ALLOWED_ENVELOPE_FIELDS }
            .sorted()
        require(unknownFields.isEmpty()) {
            "Unknown protocol envelope field: ${unknownFields.first()}"
        }

        val version = validateVersion(envelope["version"] as? JsonPrimitive)
        STRING_ENVELOPE_FIELDS.forEach { field ->
            require((envelope[field] as? JsonPrimitive)?.isString == true) {
                "Invalid protocol envelope field: $field"
            }
        }
        require(version == PROTOCOL_VERSION) {
            "Unsupported protocol envelope version: $version"
        }
        validateRequestId(envelope["request_id"] as JsonPrimitive)
        validateTimestamp(envelope["timestamp"] as JsonPrimitive)
        require(envelope["payload"] is JsonObject) {
            "Invalid protocol envelope field: payload"
        }
    }

    private fun validateVersion(version: JsonPrimitive?): Int {
        require(version != null && !version.isString) {
            "Invalid protocol envelope field: version"
        }
        return version.content.toIntOrNull()
            ?: throw IllegalArgumentException("Invalid protocol envelope field: version")
    }

    private fun validateRequestId(requestId: JsonPrimitive) {
        require(requestId.content.isNotBlank()) {
            "Invalid protocol envelope field: request_id"
        }
    }

    private fun validateTimestamp(timestamp: JsonPrimitive) {
        try {
            Instant.parse(timestamp.content)
        } catch (error: DateTimeParseException) {
            throw IllegalArgumentException("Invalid protocol envelope field: timestamp", error)
        }
    }

    fun readFrameBody(input: InputStream): ByteArray {
        val lengthBytes = input.readExactly(4)
        val length = ByteBuffer.wrap(lengthBytes).int
        require(length in 1..MAX_FRAME_BYTES) { "Invalid frame length: $length" }
        return input.readExactly(length)
    }

    fun readFrame(input: InputStream): ProtocolEnvelope {
        return decode(readFrameBody(input))
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
        private val REQUIRED_ENVELOPE_FIELDS = listOf(
            "version",
            "type",
            "request_id",
            "timestamp",
            "payload",
        )
        private val STRING_ENVELOPE_FIELDS = listOf(
            "type",
            "request_id",
            "timestamp",
        )
        private val ALLOWED_ENVELOPE_FIELDS = setOf(
            "version",
            "type",
            "request_id",
            "timestamp",
            "payload",
        )
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
