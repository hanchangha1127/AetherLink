package com.localagentbridge.android.core.protocol

import kotlinx.serialization.KSerializer
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.encodeToJsonElement
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
        val body = bytes.decodeToString()
        val rawInspection = RawJsonObjectInspector(body).inspect()
        val duplicateKeyStrictMessageType = when {
            MessageType.ResearchBriefCreate in rawInspection.topLevelTypeValues ->
                MessageType.ResearchBriefCreate
            MessageType.ResearchNotebooksList in rawInspection.topLevelTypeValues ->
                MessageType.ResearchNotebooksList
            MessageType.MemorySemanticDuplicateSuggestionsList in rawInspection.topLevelTypeValues ->
                MessageType.MemorySemanticDuplicateSuggestionsList
            MessageType.MemorySemanticDuplicateClustersList in rawInspection.topLevelTypeValues ->
                MessageType.MemorySemanticDuplicateClustersList
            else -> null
        }
        if (duplicateKeyStrictMessageType != null && rawInspection.firstDuplicateKeyPath != null) {
            throw IllegalArgumentException(
                "$duplicateKeyStrictMessageType contains duplicate JSON object key: " +
                    rawInspection.firstDuplicateKeyPath,
            )
        }
        val element = json.parseToJsonElement(body)
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

private data class RawJsonObjectInspection(
    val topLevelTypeValues: Set<String>,
    val firstDuplicateKeyPath: String?,
)

private class RawJsonObjectInspector(
    private val source: String,
) {
    private var index = 0
    private val topLevelTypeValues = mutableSetOf<String>()
    private var firstDuplicateKeyPath: String? = null

    fun inspect(): RawJsonObjectInspection {
        parseValue(path = "$", depth = 0)
        skipWhitespace()
        require(index == source.length) { "Unexpected trailing JSON content" }
        return RawJsonObjectInspection(
            topLevelTypeValues = topLevelTypeValues,
            firstDuplicateKeyPath = firstDuplicateKeyPath,
        )
    }

    private fun parseValue(path: String, depth: Int): String? {
        require(depth <= MAX_JSON_NESTING_DEPTH) {
            "JSON nesting exceeds the protocol limit"
        }
        skipWhitespace()
        require(index < source.length) { "Unexpected end of JSON input" }
        return when (source[index]) {
            '"' -> parseString()
            '{' -> {
                parseObject(path, depth)
                null
            }
            '[' -> {
                parseArray(path, depth)
                null
            }
            else -> {
                parsePrimitive()
                null
            }
        }
    }

    private fun parseObject(path: String, depth: Int) {
        expect('{')
        skipWhitespace()
        if (consumeIf('}')) return

        val keys = mutableSetOf<String>()
        while (true) {
            skipWhitespace()
            require(index < source.length && source[index] == '"') {
                "JSON object key must be a string"
            }
            val key = parseString()
            if (!keys.add(key) && firstDuplicateKeyPath == null) {
                firstDuplicateKeyPath = "$path.$key"
            }
            skipWhitespace()
            expect(':')
            val stringValue = parseValue("$path.$key", depth + 1)
            if (path == "$" && key == "type" && stringValue != null) {
                topLevelTypeValues += stringValue
            }
            skipWhitespace()
            when {
                consumeIf('}') -> return
                consumeIf(',') -> Unit
                else -> throw IllegalArgumentException("JSON object entries must be comma-separated")
            }
        }
    }

    private fun parseArray(path: String, depth: Int) {
        expect('[')
        skipWhitespace()
        if (consumeIf(']')) return

        var elementIndex = 0
        while (true) {
            parseValue("$path[$elementIndex]", depth + 1)
            elementIndex += 1
            skipWhitespace()
            when {
                consumeIf(']') -> return
                consumeIf(',') -> Unit
                else -> throw IllegalArgumentException("JSON array elements must be comma-separated")
            }
        }
    }

    private fun parseString(): String {
        expect('"')
        val result = StringBuilder()
        while (index < source.length) {
            val character = source[index++]
            when {
                character == '"' -> return result.toString()
                character == '\\' -> result.append(parseEscape())
                character < ' ' -> throw IllegalArgumentException("JSON strings must not contain control characters")
                else -> result.append(character)
            }
        }
        throw IllegalArgumentException("Unterminated JSON string")
    }

    private fun parseEscape(): Char {
        require(index < source.length) { "Unterminated JSON escape" }
        return when (val escaped = source[index++]) {
            '"', '\\', '/' -> escaped
            'b' -> '\b'
            'f' -> '\u000c'
            'n' -> '\n'
            'r' -> '\r'
            't' -> '\t'
            'u' -> parseUnicodeEscape()
            else -> throw IllegalArgumentException("Invalid JSON escape: \\$escaped")
        }
    }

    private fun parseUnicodeEscape(): Char {
        require(index + 4 <= source.length) { "Incomplete JSON Unicode escape" }
        var value = 0
        repeat(4) {
            val digit = source[index++].digitToIntOrNull(radix = 16)
                ?: throw IllegalArgumentException("Invalid JSON Unicode escape")
            value = (value shl 4) or digit
        }
        return value.toChar()
    }

    private fun parsePrimitive() {
        val start = index
        while (index < source.length && source[index] !in JSON_VALUE_DELIMITERS) {
            index += 1
        }
        require(index > start) { "Expected JSON value" }
    }

    private fun skipWhitespace() {
        while (index < source.length && source[index] in JSON_WHITESPACE) {
            index += 1
        }
    }

    private fun expect(expected: Char) {
        require(index < source.length && source[index] == expected) {
            "Expected '$expected' in JSON input"
        }
        index += 1
    }

    private fun consumeIf(expected: Char): Boolean {
        if (index >= source.length || source[index] != expected) return false
        index += 1
        return true
    }

    private companion object {
        const val MAX_JSON_NESTING_DEPTH = 128
        val JSON_WHITESPACE = setOf(' ', '\t', '\r', '\n')
        val JSON_VALUE_DELIMITERS = JSON_WHITESPACE + setOf(',', ']', '}')
    }
}

private fun InputStream.readExactly(size: Int): ByteArray {
    val buffer = ByteArray(size)
    var offset = 0
    while (offset < size) {
        val read = read(buffer, offset, size - offset)
        if (read == -1) throw EOFException("Stream ended while reading frame")
        if (read == 0) {
            val byte = read()
            if (byte == -1) throw EOFException("Stream ended while reading frame")
            buffer[offset] = byte.toByte()
            offset += 1
        } else {
            offset += read
        }
    }
    return buffer
}

private fun kotlinx.serialization.json.JsonElement.jsonObject(): kotlinx.serialization.json.JsonObject {
    return this as kotlinx.serialization.json.JsonObject
}
