package com.localagentbridge.android.core.pairing

import java.io.ByteArrayInputStream
import java.math.BigInteger
import java.security.Signature
import java.security.interfaces.ECPublicKey
import java.util.Base64

const val PAIRED_RELAY_ALLOCATION_AUTHORIZATION_SCHEME = "runtime-client-p256-v2"
const val PAIRED_RELAY_ALLOCATION_AUTHORIZATION_PROTOCOL_VERSION = 2

data class PairedRelayAllocationAuthorization(
    val scheme: String = PAIRED_RELAY_ALLOCATION_AUTHORIZATION_SCHEME,
    val protocolVersion: Int = PAIRED_RELAY_ALLOCATION_AUTHORIZATION_PROTOCOL_VERSION,
    val operation: String,
    val requestId: String,
    val authorizationId: String,
    val currentRelayId: String,
    val nextRelayId: String,
    val routeTokenHash: String,
    val runtimeKeyFingerprint: String,
    val clientKeyFingerprint: String,
    val currentTicketGeneration: Long,
    val nextTicketGeneration: Long,
    val currentRelayExpiresAtEpochMillis: Long,
    val currentRelayNonce: String,
    val nextRelayExpiresAtEpochMillis: Long,
    val nextRelayNonce: String,
    val challenge: String,
    val challengeExpiresAtEpochMillis: Long,
    val transportBinding: String,
) {
    fun runtimeTranscript(): ByteArray = PairedRelayAllocationAuthorizationProof.runtimeTranscript(this)

    fun clientTranscript(): ByteArray = PairedRelayAllocationAuthorizationProof.clientTranscript(this)

    fun runtimeDigest(): String = InitialPairingProof.sha256Hex(runtimeTranscript())

    fun clientDigest(): String = InitialPairingProof.sha256Hex(clientTranscript())
}

object PairedRelayAllocationAuthorizationProof {
    fun pairedRelayId(
        routeToken: String,
        runtimeKeyFingerprint: String,
        clientKeyFingerprint: String,
    ): String {
        requireCanonicalOpaqueValue(routeToken, "route_token", MAX_ID_UTF8_BYTES)
        requireCanonicalHex(runtimeKeyFingerprint, "runtime_key_fingerprint")
        requireCanonicalHex(clientKeyFingerprint, "client_key_fingerprint")
        require(runtimeKeyFingerprint != clientKeyFingerprint) {
            "runtime and client key fingerprints must be distinct"
        }
        val material = listOf(
            "AetherLink paired relay id v1",
            runtimeKeyFingerprint,
            clientKeyFingerprint,
            routeToken,
        ).joinToString("\n")
        return "rt2-${InitialPairingProof.sha256Hex(material.toByteArray(Charsets.UTF_8))}"
    }

    fun runtimeTranscript(authorization: PairedRelayAllocationAuthorization): ByteArray =
        transcript(RUNTIME_CONTEXT, authorization)

    fun clientTranscript(authorization: PairedRelayAllocationAuthorization): ByteArray =
        transcript(CLIENT_CONTEXT, authorization)

    fun verifyRuntime(
        authorization: PairedRelayAllocationAuthorization,
        runtimePublicKeyBase64: String,
        signatureBase64: String,
    ): Boolean = verify(
        authorization = authorization,
        publicKeyBase64 = runtimePublicKeyBase64,
        expectedFingerprint = authorization.runtimeKeyFingerprint,
        signatureBase64 = signatureBase64,
        transcript = authorization::runtimeTranscript,
    )

    fun verifyClient(
        authorization: PairedRelayAllocationAuthorization,
        clientPublicKeyBase64: String,
        signatureBase64: String,
    ): Boolean = verify(
        authorization = authorization,
        publicKeyBase64 = clientPublicKeyBase64,
        expectedFingerprint = authorization.clientKeyFingerprint,
        signatureBase64 = signatureBase64,
        transcript = authorization::clientTranscript,
    )

    internal fun requireCanonicalPublicKey(
        publicKeyBase64: String,
        fingerprint: String,
    ): ECPublicKey = InitialPairingProof.requireCanonicalPublicKey(publicKeyBase64, fingerprint)

    private fun verify(
        authorization: PairedRelayAllocationAuthorization,
        publicKeyBase64: String,
        expectedFingerprint: String,
        signatureBase64: String,
        transcript: () -> ByteArray,
    ): Boolean = runCatching {
        validate(authorization)
        val publicKey = requireCanonicalPublicKey(publicKeyBase64, expectedFingerprint)
        val signatureBytes = decodeCanonicalBase64(signatureBase64)
        requireCanonicalEcdsaDer(signatureBytes)
        Signature.getInstance("SHA256withECDSA").run {
            initVerify(publicKey)
            update(transcript())
            verify(signatureBytes)
        }
    }.getOrDefault(false)

    private fun transcript(
        context: String,
        authorization: PairedRelayAllocationAuthorization,
    ): ByteArray {
        validate(authorization)
        return lengthFramedTranscript(
            context,
            "scheme" to authorization.scheme,
            "protocol_version" to authorization.protocolVersion.toString(),
            "operation" to authorization.operation,
            "request_id" to authorization.requestId,
            "authorization_id" to authorization.authorizationId,
            "current_relay_id" to authorization.currentRelayId,
            "next_relay_id" to authorization.nextRelayId,
            "route_token_hash" to authorization.routeTokenHash,
            "runtime_key_fingerprint" to authorization.runtimeKeyFingerprint,
            "client_key_fingerprint" to authorization.clientKeyFingerprint,
            "current_ticket_generation" to authorization.currentTicketGeneration.toString(),
            "next_ticket_generation" to authorization.nextTicketGeneration.toString(),
            "current_relay_expires_at" to authorization.currentRelayExpiresAtEpochMillis.toString(),
            "current_relay_nonce" to authorization.currentRelayNonce,
            "next_relay_expires_at" to authorization.nextRelayExpiresAtEpochMillis.toString(),
            "next_relay_nonce" to authorization.nextRelayNonce,
            "challenge" to authorization.challenge,
            "challenge_expires_at" to authorization.challengeExpiresAtEpochMillis.toString(),
            "transport_binding" to authorization.transportBinding,
        )
    }

    private fun validate(authorization: PairedRelayAllocationAuthorization) {
        require(authorization.scheme == PAIRED_RELAY_ALLOCATION_AUTHORIZATION_SCHEME) {
            "unsupported authorization scheme"
        }
        require(authorization.protocolVersion == PAIRED_RELAY_ALLOCATION_AUTHORIZATION_PROTOCOL_VERSION) {
            "unsupported protocol version"
        }
        require(authorization.operation == "claim" || authorization.operation == "renew") {
            "operation must be claim or renew"
        }
        requireBoundedId(authorization.requestId, "request_id")
        requireBoundedId(authorization.authorizationId, "authorization_id")
        require(RT2_ID.matches(authorization.currentRelayId)) {
            "current_relay_id must be rt2- followed by 64 lowercase hex characters"
        }
        require(RT2_ID.matches(authorization.nextRelayId)) {
            "next_relay_id must be rt2- followed by 64 lowercase hex characters"
        }
        require(authorization.operation != "claim" || authorization.currentRelayId != authorization.nextRelayId) {
            "claim next_relay_id must differ from current_relay_id"
        }
        requireCanonicalHex(authorization.routeTokenHash, "route_token_hash")
        requireCanonicalHex(authorization.runtimeKeyFingerprint, "runtime_key_fingerprint")
        requireCanonicalHex(authorization.clientKeyFingerprint, "client_key_fingerprint")
        require(authorization.currentTicketGeneration > 0) {
            "current_ticket_generation must be positive"
        }
        require(
            authorization.currentTicketGeneration < Long.MAX_VALUE &&
                authorization.nextTicketGeneration == authorization.currentTicketGeneration + 1,
        ) {
            "next_ticket_generation must be the generation after current_ticket_generation"
        }
        require(authorization.currentRelayExpiresAtEpochMillis > 0) {
            "current_relay_expires_at must be positive"
        }
        require(authorization.nextRelayExpiresAtEpochMillis > authorization.currentRelayExpiresAtEpochMillis) {
            "next_relay_expires_at must advance"
        }
        requireCanonicalOpaqueValue(authorization.currentRelayNonce, "current_relay_nonce", MAX_NONCE_UTF8_BYTES)
        requireCanonicalOpaqueValue(authorization.nextRelayNonce, "next_relay_nonce", MAX_NONCE_UTF8_BYTES)
        require(authorization.currentRelayNonce != authorization.nextRelayNonce) {
            "current_relay_nonce and next_relay_nonce must be distinct"
        }
        requireCanonicalHex(authorization.challenge, "challenge")
        require(authorization.challengeExpiresAtEpochMillis > 0) {
            "challenge_expires_at must be positive"
        }
        requireCanonicalHex(authorization.transportBinding, "transport_binding")
    }

    private fun requireBoundedId(value: String, field: String) {
        requireCanonicalOpaqueValue(value, field, MAX_ID_UTF8_BYTES)
    }

    private fun requireCanonicalOpaqueValue(value: String, field: String, maximumUtf8Bytes: Int) {
        val byteLength = value.toByteArray(Charsets.UTF_8).size
        require(
            byteLength in 1..maximumUtf8Bytes &&
                value.all { !it.isWhitespace() && !it.isISOControl() },
        ) {
            "$field must be nonblank, whitespace-free, control-free, and at most $maximumUtf8Bytes UTF-8 bytes"
        }
    }

    private fun requireCanonicalHex(value: String, field: String) {
        require(value.length == SHA256_HEX_LENGTH && value.all(::isLowercaseHexCharacter)) {
            "$field must be 64 lowercase ASCII hex characters"
        }
    }

    private fun lengthFramedTranscript(context: String, vararg fields: Pair<String, String>): ByteArray {
        val lines = ArrayList<String>(1 + fields.size * 3)
        lines += context
        fields.forEach { (name, value) ->
            lines += name
            lines += value.toByteArray(Charsets.UTF_8).size.toString()
            lines += value
        }
        return lines.joinToString("\n").toByteArray(Charsets.UTF_8)
    }

    private fun decodeCanonicalBase64(value: String): ByteArray {
        val decoded = Base64.getDecoder().decode(value)
        require(Base64.getEncoder().encodeToString(decoded) == value) { "base64 is not canonical" }
        return decoded
    }

    private fun requireCanonicalEcdsaDer(der: ByteArray) {
        val input = ByteArrayInputStream(der)
        require(input.read() == DER_SEQUENCE_TAG) { "signature must be a DER sequence" }
        val sequenceLength = readDerLength(input)
        require(sequenceLength == input.available()) { "invalid DER sequence length" }
        readCanonicalDerInteger(input)
        readCanonicalDerInteger(input)
        require(input.available() == 0) { "trailing DER data" }
    }

    private fun readCanonicalDerInteger(input: ByteArrayInputStream) {
        require(input.read() == DER_INTEGER_TAG) { "signature component must be a DER integer" }
        val length = readDerLength(input)
        require(length in 1..MAX_DER_INTEGER_BYTES && length <= input.available()) {
            "invalid DER integer length"
        }
        val bytes = ByteArray(length)
        require(input.read(bytes) == length)
        require(bytes[0].toInt() and DER_SIGN_BIT == 0) { "DER integer must be positive" }
        require(!(length > 1 && bytes[0] == 0.toByte() && bytes[1].toInt() and DER_SIGN_BIT == 0)) {
            "DER integer is not minimally encoded"
        }
        val value = BigInteger(1, bytes)
        require(value.signum() > 0 && value < P256_ORDER) { "ECDSA component is out of range" }
    }

    private fun readDerLength(input: ByteArrayInputStream): Int {
        val first = input.read()
        require(first >= 0 && first and DER_SIGN_BIT == 0) { "DER length must use canonical short form" }
        return first
    }

    private fun isLowercaseHexCharacter(character: Char): Boolean =
        character in '0'..'9' || character in 'a'..'f'

    private const val RUNTIME_CONTEXT =
        "AetherLink paired relay allocation runtime authorization v2"
    private const val CLIENT_CONTEXT =
        "AetherLink paired relay allocation client authorization v2"
    private const val MAX_ID_UTF8_BYTES = 512
    private const val MAX_NONCE_UTF8_BYTES = 512
    private const val SHA256_HEX_LENGTH = 64
    private const val DER_SEQUENCE_TAG = 0x30
    private const val DER_INTEGER_TAG = 0x02
    private const val DER_SIGN_BIT = 0x80
    private const val MAX_DER_INTEGER_BYTES = 33
    private val RT2_ID = Regex("rt2-[0-9a-f]{64}")
    private val P256_ORDER = BigInteger("ffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551", 16)
}
