package com.localagentbridge.android.core.transport

import java.math.BigInteger
import java.nio.ByteBuffer
import java.security.AlgorithmParameters
import java.security.KeyFactory
import java.security.KeyPairGenerator
import java.security.MessageDigest
import java.security.PrivateKey
import java.security.interfaces.ECPublicKey
import java.security.spec.ECGenParameterSpec
import java.security.spec.ECParameterSpec
import java.security.spec.ECPoint
import java.security.spec.ECPrivateKeySpec
import java.security.spec.ECPublicKeySpec
import javax.crypto.Cipher
import javax.crypto.KeyAgreement
import javax.crypto.Mac
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

internal class RelayEphemeralKeyPair private constructor(
    val publicKeyHex: String,
    private val privateKey: PrivateKey,
) {
    fun sharedSecret(peerPublicKeyHex: String): ByteArray {
        val agreement = KeyAgreement.getInstance("ECDH")
        agreement.init(privateKey)
        agreement.doPhase(decodeP256PublicKey(peerPublicKeyHex), true)
        val sharedSecret = agreement.generateSecret()
        require(sharedSecret.size <= P256_FIELD_BYTES) { "Relay ECDH shared secret is invalid" }
        return ByteArray(P256_FIELD_BYTES).also { fixedSecret ->
            sharedSecret.copyInto(fixedSecret, destinationOffset = fixedSecret.size - sharedSecret.size)
        }
    }

    companion object {
        fun generate(): RelayEphemeralKeyPair {
            val generator = KeyPairGenerator.getInstance("EC")
            generator.initialize(ECGenParameterSpec(P256_CURVE_NAME))
            val keyPair = generator.generateKeyPair()
            return RelayEphemeralKeyPair(
                publicKeyHex = encodeP256PublicKey(keyPair.public as ECPublicKey),
                privateKey = keyPair.private,
            )
        }

        internal fun fromPrivateScalarForTest(
            privateScalar: BigInteger,
            publicKeyHex: String,
        ): RelayEphemeralKeyPair {
            require(privateScalar.signum() > 0 && privateScalar < P256_PARAMETERS.order) {
                "Relay P-256 private scalar is invalid"
            }
            decodeP256PublicKey(publicKeyHex)
            val privateKey = KeyFactory.getInstance("EC").generatePrivate(
                ECPrivateKeySpec(privateScalar, P256_PARAMETERS),
            )
            return RelayEphemeralKeyPair(publicKeyHex, privateKey)
        }
    }
}

internal class RelaySessionCrypto private constructor(
    val bindingId: String,
    private val bindingDigest: ByteArray,
    private val confirmationKey: ByteArray,
    private val clientTrafficSecret: ByteArray,
    private val runtimeTrafficSecret: ByteArray,
) {
    fun proof(role: String): String {
        require(role == CLIENT_ROLE || role == RUNTIME_ROLE) { "Relay confirmation role is invalid" }
        val message = (
            "AetherLink relay key confirmation v2\nrole\n" +
                role +
                "\ntransport_binding\n" +
                bindingId
            ).toByteArray(Charsets.UTF_8)
        return hmacSha256(confirmationKey, message).toLowercaseHex()
    }

    fun controlLine(role: String): String =
        "AETHERLINK_RELAY confirm $role binding=$bindingId proof=${proof(role)}"

    fun frameCryptor(
        clientFrameIndex: Long = 0L,
        runtimeFrameIndex: Long = 0L,
    ): RelayFrameBodyCryptor = RelayFrameBodyCryptor(
        clientTrafficSecret = clientTrafficSecret,
        runtimeTrafficSecret = runtimeTrafficSecret,
        bindingDigest = bindingDigest,
        clientFrameIndex = clientFrameIndex,
        runtimeFrameIndex = runtimeFrameIndex,
    )

    companion object {
        const val CLIENT_ROLE = "client"
        const val RUNTIME_ROLE = "runtime"

        fun establish(
            relaySecret: String,
            relayId: String,
            routeNonce: String?,
            clientSessionNonce: String,
            runtimeSessionNonce: String,
            clientEphemeralKey: String,
            runtimeEphemeralKey: String,
            localEphemeralKeyPair: RelayEphemeralKeyPair,
        ): RelaySessionCrypto {
            require(relaySecret.isNotBlank()) { "Relay secret must not be blank" }
            relayId.requireRelayToken()
            clientSessionNonce.requireSessionNonce()
            runtimeSessionNonce.requireSessionNonce()
            require(
                localEphemeralKeyPair.publicKeyHex == clientEphemeralKey ||
                    localEphemeralKeyPair.publicKeyHex == runtimeEphemeralKey,
            ) { "Local relay ephemeral key is not in the transcript" }

            val clientPublicKey = decodeP256PublicKeyHex(clientEphemeralKey)
            val runtimePublicKey = decodeP256PublicKeyHex(runtimeEphemeralKey)
            val transcript = buildString {
                append("AetherLink relay session binding v2\ncrypto_version\n2\nrelay_id\n")
                append(relayId)
                append("\nroute_nonce\n")
                append(routeNonce.orEmpty())
                append("\nclient_session_nonce\n")
                append(clientSessionNonce)
                append("\nruntime_session_nonce\n")
                append(runtimeSessionNonce)
                append("\nclient_ephemeral_key\n")
                append(clientPublicKey)
                append("\nruntime_ephemeral_key\n")
                append(runtimePublicKey)
            }
            val bindingDigest = MessageDigest.getInstance("SHA-256")
                .digest(transcript.toByteArray(Charsets.UTF_8))
            val peerPublicKey = if (localEphemeralKeyPair.publicKeyHex == clientPublicKey) {
                runtimePublicKey
            } else {
                clientPublicKey
            }
            val inputKeyMaterial = localEphemeralKeyPair.sharedSecret(peerPublicKey) +
                relaySecret.toByteArray(Charsets.UTF_8)
            val pseudoRandomKey = hmacSha256(bindingDigest, inputKeyMaterial)

            return RelaySessionCrypto(
                bindingId = bindingDigest.toLowercaseHex(),
                bindingDigest = bindingDigest,
                confirmationKey = hkdfExpand(pseudoRandomKey, CONFIRMATION_LABEL),
                clientTrafficSecret = hkdfExpand(pseudoRandomKey, CLIENT_TRAFFIC_LABEL),
                runtimeTrafficSecret = hkdfExpand(pseudoRandomKey, RUNTIME_TRAFFIC_LABEL),
            )
        }

        private val CONFIRMATION_LABEL =
            "AetherLink relay confirmation v2".toByteArray(Charsets.UTF_8)
        private val CLIENT_TRAFFIC_LABEL =
            "AetherLink relay client traffic v2".toByteArray(Charsets.UTF_8)
        private val RUNTIME_TRAFFIC_LABEL =
            "AetherLink relay runtime traffic v2".toByteArray(Charsets.UTF_8)

        private fun hkdfExpand(pseudoRandomKey: ByteArray, info: ByteArray): ByteArray {
            return hmacSha256(pseudoRandomKey, info + byteArrayOf(1))
        }
    }
}

internal class RelayFrameBodyCryptor(
    clientTrafficSecret: ByteArray,
    runtimeTrafficSecret: ByteArray,
    bindingDigest: ByteArray,
    clientFrameIndex: Long = 0L,
    runtimeFrameIndex: Long = 0L,
) {
    private val clientTrafficSecret = clientTrafficSecret.requireTrafficSecret().copyOf()
    private val runtimeTrafficSecret = runtimeTrafficSecret.requireTrafficSecret().copyOf()
    private val bindingDigest = bindingDigest.requireBindingDigest().copyOf()
    private var clientFrameIndex = clientFrameIndex.requireFrameIndex()
    private var runtimeFrameIndex = runtimeFrameIndex.requireFrameIndex()

    fun encryptClientFrameBody(plaintext: ByteArray): ByteArray {
        val ciphertext = crypt(
            mode = Cipher.ENCRYPT_MODE,
            trafficSecret = clientTrafficSecret,
            direction = CLIENT_DIRECTION,
            frameIndex = clientFrameIndex,
            input = plaintext,
        )
        clientFrameIndex = clientFrameIndex.nextFrameIndex()
        return ciphertext
    }

    fun decryptRuntimeFrameBody(ciphertext: ByteArray): ByteArray {
        val plaintext = crypt(
            mode = Cipher.DECRYPT_MODE,
            trafficSecret = runtimeTrafficSecret,
            direction = RUNTIME_DIRECTION,
            frameIndex = runtimeFrameIndex,
            input = ciphertext,
        )
        runtimeFrameIndex = runtimeFrameIndex.nextFrameIndex()
        return plaintext
    }

    internal fun encryptRuntimeFrameBodyForTest(plaintext: ByteArray): ByteArray {
        val ciphertext = crypt(
            mode = Cipher.ENCRYPT_MODE,
            trafficSecret = runtimeTrafficSecret,
            direction = RUNTIME_DIRECTION,
            frameIndex = runtimeFrameIndex,
            input = plaintext,
        )
        runtimeFrameIndex = runtimeFrameIndex.nextFrameIndex()
        return ciphertext
    }

    internal fun decryptClientFrameBodyForTest(ciphertext: ByteArray): ByteArray {
        val plaintext = crypt(
            mode = Cipher.DECRYPT_MODE,
            trafficSecret = clientTrafficSecret,
            direction = CLIENT_DIRECTION,
            frameIndex = clientFrameIndex,
            input = ciphertext,
        )
        clientFrameIndex = clientFrameIndex.nextFrameIndex()
        return plaintext
    }

    private fun crypt(
        mode: Int,
        trafficSecret: ByteArray,
        direction: ByteArray,
        frameIndex: Long,
        input: ByteArray,
    ): ByteArray {
        frameIndex.requireFrameIndex()
        val epoch = frameIndex ushr EPOCH_SHIFT
        val sequence = frameIndex and SEQUENCE_MASK
        val epochKey = hmacSha256(
            trafficSecret,
            FRAME_EPOCH_LABEL + direction + epoch.toUInt64BigEndian(),
        )
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(
            mode,
            SecretKeySpec(epochKey, "AES"),
            GCMParameterSpec(GCM_TAG_BITS, direction + sequence.toUInt64BigEndian()),
        )
        cipher.updateAAD(
            FRAME_AAD_LABEL +
                bindingDigest +
                direction +
                epoch.toUInt64BigEndian() +
                sequence.toUInt64BigEndian(),
        )
        return cipher.doFinal(input)
    }

    private companion object {
        private val FRAME_EPOCH_LABEL =
            "AetherLink relay frame epoch v2\n".toByteArray(Charsets.UTF_8)
        private val FRAME_AAD_LABEL =
            "AETHERLINK_RELAY_FRAME_V2".toByteArray(Charsets.UTF_8)
        private val CLIENT_DIRECTION = "CLNT".toByteArray(Charsets.US_ASCII)
        private val RUNTIME_DIRECTION = "RUNT".toByteArray(Charsets.US_ASCII)
        private const val EPOCH_SHIFT = 16
        private const val SEQUENCE_MASK = 0xffffL
        private const val GCM_TAG_BITS = 128
    }
}

internal fun String.requireRelayToken(): String {
    require(isNotBlank()) { "Relay token must not be blank" }
    require(none { it <= ' ' }) { "Relay token must not contain whitespace" }
    return this
}

internal fun String.requireSessionNonce(): String {
    require(length == 32 && isLowercaseHex()) {
        "Relay session nonce must be 32 lowercase hexadecimal characters"
    }
    return this
}

internal fun String.requireEphemeralKey(): String {
    decodeP256PublicKeyHex(this)
    return this
}

internal fun ByteArray.toLowercaseHex(): String {
    val digits = "0123456789abcdef"
    val result = CharArray(size * 2)
    forEachIndexed { index, byte ->
        val value = byte.toInt() and 0xff
        result[index * 2] = digits[value ushr 4]
        result[index * 2 + 1] = digits[value and 0x0f]
    }
    return String(result)
}

private const val P256_CURVE_NAME = "secp256r1"
private const val P256_FIELD_BYTES = 32
private const val P256_PUBLIC_KEY_BYTES = 65
private val P256_PARAMETERS: ECParameterSpec = AlgorithmParameters.getInstance("EC").run {
    init(ECGenParameterSpec(P256_CURVE_NAME))
    getParameterSpec(ECParameterSpec::class.java)
}

private fun encodeP256PublicKey(publicKey: ECPublicKey): String {
    val point = publicKey.w
    val encoded = byteArrayOf(0x04) +
        point.affineX.toFixedUnsigned(P256_FIELD_BYTES) +
        point.affineY.toFixedUnsigned(P256_FIELD_BYTES)
    return encoded.toLowercaseHex()
}

private fun decodeP256PublicKeyHex(encoded: String): String {
    require(encoded.length == P256_PUBLIC_KEY_BYTES * 2 && encoded.isLowercaseHex()) {
        "Relay ephemeral key must be 130 lowercase hexadecimal characters"
    }
    val bytes = encoded.hexToByteArray()
    require(bytes.first() == 0x04.toByte()) { "Relay ephemeral key must be X9.63 uncompressed" }
    val x = BigInteger(1, bytes.copyOfRange(1, 33))
    val y = BigInteger(1, bytes.copyOfRange(33, 65))
    require(isOnP256Curve(x, y)) { "Relay ephemeral key is not on P-256" }
    return encoded
}

private fun decodeP256PublicKey(encoded: String): java.security.PublicKey {
    decodeP256PublicKeyHex(encoded)
    val bytes = encoded.hexToByteArray()
    return KeyFactory.getInstance("EC").generatePublic(
        ECPublicKeySpec(
            ECPoint(
                BigInteger(1, bytes.copyOfRange(1, 33)),
                BigInteger(1, bytes.copyOfRange(33, 65)),
            ),
            P256_PARAMETERS,
        ),
    )
}

private fun isOnP256Curve(x: BigInteger, y: BigInteger): Boolean {
    val field = P256_PARAMETERS.curve.field
    val prime = (field as? java.security.spec.ECFieldFp)?.p ?: return false
    if (x.signum() < 0 || y.signum() < 0 || x >= prime || y >= prime) return false
    val left = y.modPow(BigInteger.valueOf(2L), prime)
    val right = x.modPow(BigInteger.valueOf(3L), prime)
        .add(P256_PARAMETERS.curve.a.multiply(x))
        .add(P256_PARAMETERS.curve.b)
        .mod(prime)
    return left == right
}

private fun BigInteger.toFixedUnsigned(size: Int): ByteArray {
    val encoded = toByteArray()
    val unsigned = if (encoded.size > size && encoded.first() == 0.toByte()) {
        encoded.copyOfRange(1, encoded.size)
    } else {
        encoded
    }
    require(unsigned.size <= size) { "Relay P-256 coordinate is invalid" }
    return ByteArray(size).also { unsigned.copyInto(it, destinationOffset = size - unsigned.size) }
}

private fun String.isLowercaseHex(): Boolean = all { it in '0'..'9' || it in 'a'..'f' }

private fun String.hexToByteArray(): ByteArray {
    require(length % 2 == 0 && isLowercaseHex()) { "Hex value must be canonical lowercase" }
    return ByteArray(length / 2) { index ->
        substring(index * 2, index * 2 + 2).toInt(16).toByte()
    }
}

private fun hmacSha256(key: ByteArray, message: ByteArray): ByteArray {
    val mac = Mac.getInstance("HmacSHA256")
    mac.init(SecretKeySpec(key, "HmacSHA256"))
    return mac.doFinal(message)
}

private fun ByteArray.requireTrafficSecret(): ByteArray {
    require(size == 32) { "Relay traffic secret must be 32 bytes" }
    return this
}

private fun ByteArray.requireBindingDigest(): ByteArray {
    require(size == 32) { "Relay binding digest must be 32 bytes" }
    return this
}

private fun Long.requireFrameIndex(): Long {
    require(this >= 0L && this < Long.MAX_VALUE) { "Relay frame index is exhausted" }
    return this
}

private fun Long.nextFrameIndex(): Long = if (this == Long.MAX_VALUE - 1L) {
    Long.MAX_VALUE
} else {
    this + 1L
}

private fun Long.toUInt64BigEndian(): ByteArray = ByteBuffer.allocate(Long.SIZE_BYTES).putLong(this).array()
