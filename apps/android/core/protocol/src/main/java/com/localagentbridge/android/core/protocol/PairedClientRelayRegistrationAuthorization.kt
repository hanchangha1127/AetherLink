package com.localagentbridge.android.core.protocol

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.io.ByteArrayInputStream
import java.math.BigInteger
import java.security.KeyFactory
import java.security.MessageDigest
import java.security.interfaces.ECPublicKey
import java.security.spec.ECFieldFp
import java.security.spec.X509EncodedKeySpec
import java.util.Base64

const val PAIRED_CLIENT_RELAY_REGISTRATION_SCHEME = "paired-client-p256-v1"
const val PAIRED_CLIENT_RELAY_REGISTRATION_PROTOCOL_VERSION = 1
const val PAIRED_CLIENT_RELAY_REGISTRATION_ROLE = "client"
const val PAIRED_CLIENT_RELAY_REGISTRATION_CONTEXT =
    "AetherLink relay client registration authorization v1"
const val PAIRED_CLIENT_RELAY_REGISTRATION_CHALLENGE_PREFIX =
    "AETHERLINK_RELAY client_registration_challenge "
const val PAIRED_CLIENT_RELAY_REGISTRATION_PROOF_PREFIX =
    "AETHERLINK_RELAY client_registration_proof"

@Serializable
data class PairedClientRelayRegistrationChallenge(
    val scheme: String = PAIRED_CLIENT_RELAY_REGISTRATION_SCHEME,
    @SerialName("protocol_version")
    val protocolVersion: Int = PAIRED_CLIENT_RELAY_REGISTRATION_PROTOCOL_VERSION,
    val role: String = PAIRED_CLIENT_RELAY_REGISTRATION_ROLE,
    @SerialName("relay_id")
    val relayId: String,
    @SerialName("relay_expires_at")
    val relayExpiresAtEpochMillis: Long,
    @SerialName("relay_nonce")
    val relayNonce: String,
    @SerialName("runtime_key_fingerprint")
    val runtimeKeyFingerprint: String,
    @SerialName("client_key_fingerprint")
    val clientKeyFingerprint: String,
    @SerialName("ticket_generation")
    val ticketGeneration: Long,
    @SerialName("session_nonce")
    val sessionNonce: String,
    @SerialName("ephemeral_key")
    val ephemeralKey: String,
    val challenge: String,
    @SerialName("challenge_expires_at")
    val challengeExpiresAtEpochMillis: Long,
) {
    fun validate() = PairedClientRelayRegistrationAuthorization.validate(this)

    fun transcript(): ByteArray = PairedClientRelayRegistrationAuthorization.transcript(this)

    fun digest(): String = PairedClientRelayRegistrationAuthorization.digest(this)

    fun isRelayFresh(atEpochMillis: Long): Boolean =
        atEpochMillis >= 0 && relayExpiresAtEpochMillis > atEpochMillis

    fun isChallengeFresh(atEpochMillis: Long): Boolean =
        atEpochMillis >= 0 && challengeExpiresAtEpochMillis > atEpochMillis

    fun isFresh(atEpochMillis: Long): Boolean =
        isRelayFresh(atEpochMillis) && isChallengeFresh(atEpochMillis)
}

@Serializable
data class PairedClientRelayRegistrationProof(
    @SerialName("client_public_key")
    val clientPublicKeyBase64: String,
    @SerialName("client_signature")
    val clientSignatureBase64: String,
)

object PairedClientRelayRegistrationAuthorization {
    const val MAX_RELAY_NONCE_UTF8_BYTES = 512

    fun validate(challenge: PairedClientRelayRegistrationChallenge) {
        require(challenge.scheme == PAIRED_CLIENT_RELAY_REGISTRATION_SCHEME) {
            "unsupported paired client registration scheme"
        }
        require(challenge.protocolVersion == PAIRED_CLIENT_RELAY_REGISTRATION_PROTOCOL_VERSION) {
            "unsupported paired client registration protocol version"
        }
        require(challenge.role == PAIRED_CLIENT_RELAY_REGISTRATION_ROLE) {
            "paired client registration role must be client"
        }
        require(RT2_RELAY_ID.matches(challenge.relayId)) {
            "relay_id must be rt2- followed by 64 lowercase hex characters"
        }
        require(challenge.relayExpiresAtEpochMillis > 0) {
            "relay_expires_at must be positive"
        }
        requireCanonicalOpaqueRelayNonce(challenge.relayNonce)
        requireCanonicalDigest(challenge.runtimeKeyFingerprint, "runtime_key_fingerprint")
        requireCanonicalDigest(challenge.clientKeyFingerprint, "client_key_fingerprint")
        require(challenge.runtimeKeyFingerprint != challenge.clientKeyFingerprint) {
            "runtime and client key fingerprints must be distinct"
        }
        require(challenge.ticketGeneration > 0) { "ticket_generation must be positive" }
        require(SESSION_NONCE.matches(challenge.sessionNonce)) {
            "session_nonce must be 32 lowercase hex characters"
        }
        requireCanonicalEphemeralKey(challenge.ephemeralKey)
        requireCanonicalDigest(challenge.challenge, "challenge")
        require(challenge.challengeExpiresAtEpochMillis > 0) {
            "challenge_expires_at must be positive"
        }
    }

    fun transcript(challenge: PairedClientRelayRegistrationChallenge): ByteArray {
        validate(challenge)
        return lengthFramedTranscript(
            "scheme" to challenge.scheme,
            "protocol_version" to challenge.protocolVersion.toString(),
            "role" to challenge.role,
            "relay_id" to challenge.relayId,
            "relay_expires_at" to challenge.relayExpiresAtEpochMillis.toString(),
            "relay_nonce" to challenge.relayNonce,
            "runtime_key_fingerprint" to challenge.runtimeKeyFingerprint,
            "client_key_fingerprint" to challenge.clientKeyFingerprint,
            "ticket_generation" to challenge.ticketGeneration.toString(),
            "session_nonce" to challenge.sessionNonce,
            "ephemeral_key" to challenge.ephemeralKey,
            "challenge" to challenge.challenge,
            "challenge_expires_at" to challenge.challengeExpiresAtEpochMillis.toString(),
        )
    }

    fun digest(challenge: PairedClientRelayRegistrationChallenge): String =
        MessageDigest.getInstance("SHA-256").digest(transcript(challenge)).toLowercaseHex()

    fun clientKeyFingerprint(publicKeyBase64: String): String {
        val encoded = decodeCanonicalBase64(publicKeyBase64)
        val publicKey = try {
            KeyFactory.getInstance("EC").generatePublic(X509EncodedKeySpec(encoded)) as? ECPublicKey
        } catch (error: Exception) {
            throw IllegalArgumentException("client public key must be canonical P-256", error)
        } ?: throw IllegalArgumentException("client public key must be P-256")
        require(publicKey.encoded.contentEquals(encoded)) { "client public key DER must be canonical" }
        val field = publicKey.params.curve.field as? ECFieldFp
        require(
            field?.p == P256_PRIME &&
                publicKey.params.order == P256_ORDER &&
                isOnP256Curve(publicKey.w.affineX, publicKey.w.affineY),
        ) { "client public key must be canonical P-256" }
        return MessageDigest.getInstance("SHA-256").digest(encoded).toLowercaseHex()
    }

    fun parseChallengeControlLine(line: String): PairedClientRelayRegistrationChallenge {
        require(line.startsWith(PAIRED_CLIENT_RELAY_REGISTRATION_CHALLENGE_PREFIX)) {
            "relay client registration challenge prefix is invalid"
        }
        val jsonBody = line.removePrefix(PAIRED_CLIENT_RELAY_REGISTRATION_CHALLENGE_PREFIX)
        require(jsonBody.isNotEmpty() && jsonBody == jsonBody.trim()) {
            "relay client registration challenge body is invalid"
        }
        return STRICT_JSON.decodeFromString<PairedClientRelayRegistrationChallenge>(jsonBody).also {
            it.validate()
        }
    }

    fun proofControlLine(
        challenge: PairedClientRelayRegistrationChallenge,
        proof: PairedClientRelayRegistrationProof,
    ): String {
        challenge.validate()
        require(clientKeyFingerprint(proof.clientPublicKeyBase64) == challenge.clientKeyFingerprint) {
            "relay client registration proof key does not match challenge"
        }
        requireCanonicalSignature(proof.clientSignatureBase64)
        return "$PAIRED_CLIENT_RELAY_REGISTRATION_PROOF_PREFIX crypto=2 " +
            "challenge=${challenge.challenge} " +
            "client_public_key=${proof.clientPublicKeyBase64} " +
            "client_signature=${proof.clientSignatureBase64}\n"
    }

    private fun lengthFramedTranscript(vararg fields: Pair<String, String>): ByteArray {
        val lines = ArrayList<String>(1 + fields.size * 3)
        lines += PAIRED_CLIENT_RELAY_REGISTRATION_CONTEXT
        fields.forEach { (name, value) ->
            lines += name
            lines += value.toByteArray(Charsets.UTF_8).size.toString()
            lines += value
        }
        return lines.joinToString("\n").toByteArray(Charsets.UTF_8)
    }

    private fun requireCanonicalOpaqueRelayNonce(value: String) {
        val utf8Length = value.toByteArray(Charsets.UTF_8).size
        require(
            utf8Length in 1..MAX_RELAY_NONCE_UTF8_BYTES &&
                value.all { !it.isWhitespace() && !it.isISOControl() },
        ) {
            "relay_nonce must be nonblank, whitespace-free, control-free, and at most " +
                "$MAX_RELAY_NONCE_UTF8_BYTES UTF-8 bytes"
        }
    }

    private fun requireCanonicalDigest(value: String, field: String) {
        require(LOWERCASE_HEX_64.matches(value)) {
            "$field must be 64 lowercase ASCII hex characters"
        }
    }

    private fun requireCanonicalEphemeralKey(value: String) {
        require(UNCOMPRESSED_P256_KEY.matches(value)) {
            "ephemeral_key must be 130 lowercase hex characters in X9.63 uncompressed form"
        }
        val bytes = value.hexToByteArray()
        val x = BigInteger(1, bytes.copyOfRange(1, 33))
        val y = BigInteger(1, bytes.copyOfRange(33, 65))
        require(isOnP256Curve(x, y)) { "ephemeral_key must be a P-256 point" }
    }

    private fun isOnP256Curve(x: BigInteger, y: BigInteger): Boolean {
        if (x.signum() < 0 || y.signum() < 0 || x >= P256_PRIME || y >= P256_PRIME) return false
        val left = y.modPow(BigInteger.valueOf(2), P256_PRIME)
        val right = x.modPow(BigInteger.valueOf(3), P256_PRIME)
            .subtract(BigInteger.valueOf(3).multiply(x))
            .add(P256_B)
            .mod(P256_PRIME)
        return left == right
    }

    private fun decodeCanonicalBase64(value: String): ByteArray {
        val decoded = Base64.getDecoder().decode(value)
        require(Base64.getEncoder().encodeToString(decoded) == value) { "base64 must be canonical" }
        return decoded
    }

    private fun requireCanonicalSignature(value: String) {
        val der = decodeCanonicalBase64(value)
        val input = ByteArrayInputStream(der)
        require(input.read() == DER_SEQUENCE_TAG) { "signature must be a DER sequence" }
        val sequenceLength = readDerLength(input)
        require(sequenceLength == input.available()) { "signature DER sequence length is invalid" }
        repeat(2) { readCanonicalDerInteger(input) }
        require(input.available() == 0) { "signature DER has trailing data" }
    }

    private fun readCanonicalDerInteger(input: ByteArrayInputStream) {
        require(input.read() == DER_INTEGER_TAG) { "signature component must be a DER integer" }
        val length = readDerLength(input)
        require(length in 1..MAX_DER_INTEGER_BYTES && length <= input.available()) {
            "signature DER integer length is invalid"
        }
        val bytes = ByteArray(length)
        require(input.read(bytes) == length)
        require(bytes[0].toInt() and 0x80 == 0) { "signature DER integer must be positive" }
        require(length == 1 || bytes[0] != 0.toByte() || bytes[1].toInt() and 0x80 != 0) {
            "signature DER integer is not minimally encoded"
        }
    }

    private fun readDerLength(input: ByteArrayInputStream): Int {
        val first = input.read()
        require(first >= 0) { "signature DER length is missing" }
        require(first and 0x80 == 0) { "signature DER length must use short form" }
        return first
    }

    private fun String.hexToByteArray(): ByteArray = ByteArray(length / 2) { index ->
        substring(index * 2, index * 2 + 2).toInt(16).toByte()
    }

    private fun ByteArray.toLowercaseHex(): String = joinToString("") { "%02x".format(it) }

    private val RT2_RELAY_ID = Regex("^rt2-[0-9a-f]{64}$")
    private val LOWERCASE_HEX_64 = Regex("^[0-9a-f]{64}$")
    private val SESSION_NONCE = Regex("^[0-9a-f]{32}$")
    private val UNCOMPRESSED_P256_KEY = Regex("^04[0-9a-f]{128}$")
    private val P256_PRIME = BigInteger("ffffffff00000001000000000000000000000000ffffffffffffffffffffffff", 16)
    private val P256_B = BigInteger("5ac635d8aa3a93e7b3ebbd55769886bc651d06b0cc53b0f63bce3c3e27d2604b", 16)
    private val P256_ORDER = BigInteger("ffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551", 16)
    private val STRICT_JSON = Json { ignoreUnknownKeys = false }
    private const val DER_SEQUENCE_TAG = 0x30
    private const val DER_INTEGER_TAG = 0x02
    private const val MAX_DER_INTEGER_BYTES = 33
}
