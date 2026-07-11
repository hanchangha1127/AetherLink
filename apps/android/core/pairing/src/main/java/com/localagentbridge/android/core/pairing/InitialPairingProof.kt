package com.localagentbridge.android.core.pairing

import java.io.ByteArrayInputStream
import java.math.BigInteger
import java.security.AlgorithmParameters
import java.security.KeyFactory
import java.security.MessageDigest
import java.security.Signature
import java.security.interfaces.ECPublicKey
import java.security.spec.ECGenParameterSpec
import java.security.spec.ECParameterSpec
import java.security.spec.X509EncodedKeySpec
import java.util.Base64

const val INITIAL_PAIRING_PROOF_SCHEME = "p256-sha256-der-v1"

data class InitialPairingClientRequest(
    val scheme: String,
    val protocolVersion: Int,
    val requestId: String,
    val pairingNonce: String,
    val pairingCode: String,
    val runtimeDeviceId: String,
    val runtimePublicKey: String,
    val runtimeKeyFingerprint: String,
    val clientDeviceId: String,
    val clientDeviceName: String,
    val clientPublicKey: String,
    val clientKeyFingerprint: String,
    val transportBinding: String?,
) {
    fun transcript(): ByteArray = InitialPairingProof.clientRequestTranscript(this)

    fun digest(): String = InitialPairingProof.sha256Hex(transcript())
}

data class InitialPairingAcceptedResult(
    val scheme: String,
    val protocolVersion: Int,
    val requestId: String,
    val pairingRequestDigest: String,
    val accepted: Boolean,
    val runtimeDeviceId: String,
    val runtimePublicKey: String,
    val runtimeKeyFingerprint: String,
    val trustedDeviceId: String,
    val message: String,
    val transportBinding: String?,
) {
    fun transcript(): ByteArray = InitialPairingProof.acceptedResultTranscript(this)

    fun digest(): String = InitialPairingProof.sha256Hex(transcript())
}

object InitialPairingProof {
    fun clientRequestTranscript(request: InitialPairingClientRequest): ByteArray {
        require(request.scheme == INITIAL_PAIRING_PROOF_SCHEME) { "unsupported proof scheme" }
        require(request.protocolVersion == 1) { "unsupported protocol version" }
        val binding = canonicalTransportBinding(request.transportBinding)
        requireCanonicalPublicKey(request.runtimePublicKey, request.runtimeKeyFingerprint)
        requireCanonicalPublicKey(request.clientPublicKey, request.clientKeyFingerprint)
        return transcript(
            CLIENT_CONTEXT,
            "scheme" to request.scheme,
            "protocol_version" to request.protocolVersion.toString(),
            "request_id" to request.requestId,
            "pairing_nonce" to request.pairingNonce,
            "pairing_code" to request.pairingCode,
            "runtime_device_id" to request.runtimeDeviceId,
            "runtime_public_key" to request.runtimePublicKey,
            "runtime_key_fingerprint" to request.runtimeKeyFingerprint,
            "client_device_id" to request.clientDeviceId,
            "client_device_name" to request.clientDeviceName,
            "client_public_key" to request.clientPublicKey,
            "client_key_fingerprint" to request.clientKeyFingerprint,
            "transport_binding" to binding,
        )
    }

    fun acceptedResultTranscript(result: InitialPairingAcceptedResult): ByteArray {
        require(result.scheme == INITIAL_PAIRING_PROOF_SCHEME) { "unsupported proof scheme" }
        require(result.protocolVersion == 1) { "unsupported protocol version" }
        require(result.accepted) { "only accepted pairing results are signed" }
        require(isLowercaseHex(result.pairingRequestDigest, 64)) { "invalid pairing request digest" }
        val binding = canonicalTransportBinding(result.transportBinding)
        requireCanonicalPublicKey(result.runtimePublicKey, result.runtimeKeyFingerprint)
        return transcript(
            RESULT_CONTEXT,
            "scheme" to result.scheme,
            "protocol_version" to result.protocolVersion.toString(),
            "request_id" to result.requestId,
            "pairing_request_digest" to result.pairingRequestDigest,
            "accepted" to "true",
            "runtime_device_id" to result.runtimeDeviceId,
            "runtime_public_key" to result.runtimePublicKey,
            "runtime_key_fingerprint" to result.runtimeKeyFingerprint,
            "trusted_device_id" to result.trustedDeviceId,
            "message" to result.message,
            "transport_binding" to binding,
        )
    }

    fun verifyAcceptedResult(
        result: InitialPairingAcceptedResult,
        signatureBase64: String,
        expectedRequestId: String,
        expectedPairingRequestDigest: String,
        expectedTrustedDeviceId: String,
        expectedTransportBinding: String?,
    ): Boolean = runCatching {
        val actualBinding = canonicalTransportBinding(result.transportBinding)
        val expectedBinding = canonicalTransportBinding(expectedTransportBinding)
        if (result.requestId != expectedRequestId ||
            result.pairingRequestDigest != expectedPairingRequestDigest ||
            result.trustedDeviceId != expectedTrustedDeviceId ||
            actualBinding != expectedBinding
        ) return false

        val publicKey = requireCanonicalPublicKey(result.runtimePublicKey, result.runtimeKeyFingerprint)
        val signatureBytes = decodeCanonicalBase64(signatureBase64)
        requireCanonicalEcdsaDer(signatureBytes)
        Signature.getInstance("SHA256withECDSA").run {
            initVerify(publicKey)
            update(result.transcript())
            verify(signatureBytes)
        }
    }.getOrDefault(false)

    internal fun requireCanonicalPublicKey(publicKeyBase64: String, fingerprint: String): ECPublicKey {
        require(isLowercaseHex(fingerprint, 64)) { "fingerprint must be 64 lowercase hex characters" }
        val encoded = decodeCanonicalBase64(publicKeyBase64)
        val publicKey = KeyFactory.getInstance("EC")
            .generatePublic(X509EncodedKeySpec(encoded)) as? ECPublicKey
            ?: throw IllegalArgumentException("public key must be an EC key")
        require(publicKey.encoded.contentEquals(encoded)) { "public key encoding is not canonical" }
        require(publicKey.params.matchesP256()) { "public key must use P-256" }
        require(sha256Hex(encoded) == fingerprint) { "public key fingerprint mismatch" }
        return publicKey
    }

    internal fun sha256Hex(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256")
        .digest(bytes)
        .joinToString("") { "%02x".format(it) }

    private fun transcript(context: String, vararg fields: Pair<String, String>): ByteArray {
        val lines = ArrayList<String>(1 + fields.size * 3)
        lines += context
        fields.forEach { (name, value) ->
            lines += name
            lines += value.toByteArray(Charsets.UTF_8).size.toString()
            lines += value
        }
        return lines.joinToString("\n").toByteArray(Charsets.UTF_8)
    }

    private fun canonicalTransportBinding(value: String?): String {
        if (value == null || value == "none") return "none"
        require(isLowercaseHex(value, 64)) { "transport binding must be 64 lowercase hex characters or none" }
        return value
    }

    private fun decodeCanonicalBase64(value: String): ByteArray {
        val decoded = Base64.getDecoder().decode(value)
        require(Base64.getEncoder().encodeToString(decoded) == value) { "base64 is not canonical" }
        return decoded
    }

    private fun requireCanonicalEcdsaDer(der: ByteArray) {
        val input = ByteArrayInputStream(der)
        require(input.read() == 0x30) { "signature must be a DER sequence" }
        val sequenceLength = readDerLength(input)
        require(sequenceLength == input.available()) { "invalid DER sequence length" }
        readCanonicalDerInteger(input)
        readCanonicalDerInteger(input)
        require(input.available() == 0) { "trailing DER data" }
    }

    private fun readCanonicalDerInteger(input: ByteArrayInputStream) {
        require(input.read() == 0x02) { "signature component must be a DER integer" }
        val length = readDerLength(input)
        require(length in 1..33 && length <= input.available()) { "invalid DER integer length" }
        val bytes = ByteArray(length)
        require(input.read(bytes) == length)
        require(bytes[0].toInt() and 0x80 == 0) { "DER integer must be positive" }
        require(!(length > 1 && bytes[0] == 0.toByte() && bytes[1].toInt() and 0x80 == 0)) {
            "DER integer is not minimally encoded"
        }
        val value = BigInteger(1, bytes)
        require(value.signum() > 0 && value < P256_ORDER) { "ECDSA component is out of range" }
    }

    private fun readDerLength(input: ByteArrayInputStream): Int {
        val first = input.read()
        require(first >= 0 && first and 0x80 == 0) { "DER length must use canonical short form" }
        return first
    }

    private fun ECParameterSpec.matchesP256(): Boolean {
        val expected = AlgorithmParameters.getInstance("EC").run {
            init(ECGenParameterSpec("secp256r1"))
            getParameterSpec(ECParameterSpec::class.java)
        }
        return order == expected.order && cofactor == expected.cofactor &&
            generator == expected.generator && curve == expected.curve
    }

    private fun isLowercaseHex(value: String, length: Int): Boolean =
        value.length == length && value.all { it in '0'..'9' || it in 'a'..'f' }

    private const val CLIENT_CONTEXT = "AetherLink initial pairing client proof v1"
    private const val RESULT_CONTEXT = "AetherLink initial pairing runtime result proof v1"
    private val P256_ORDER = BigInteger("ffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551", 16)
}
