package com.localagentbridge.android.core.protocol.p2pnat

import java.math.BigInteger
import java.nio.ByteBuffer
import java.security.AlgorithmParameters
import java.security.KeyFactory
import java.security.KeyPairGenerator
import java.security.MessageDigest
import java.security.PrivateKey
import java.security.interfaces.ECPublicKey
import java.security.spec.ECFieldFp
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

internal data class P2pNatJcaAlgorithms(
    val keyAgreement: String = "ECDH",
    val mac: String = "HmacSHA256",
    val cipher: String = "AES/GCM/NoPadding",
)

internal class P2pNatSessionEphemeralKey private constructor(
    publicKeyX963: ByteArray,
    privateKey: PrivateKey,
) : AutoCloseable {
    private val publicKeyX963Bytes = publicKeyX963.copyOf()
    private var privateKey: PrivateKey? = privateKey
    private var sharedSecretConsumed = false
    val publicKeyX963: ByteArray get() = publicKeyX963Bytes.copyOf()

    @get:Synchronized
    val isConsumedOrClosed: Boolean get() = sharedSecretConsumed

    @Synchronized
    fun sharedSecret(peerPublicKeyX963: ByteArray, algorithms: P2pNatJcaAlgorithms): ByteArray {
        check(!sharedSecretConsumed) { "P2P/NAT ephemeral key was already used" }
        sharedSecretConsumed = true
        val claimedPrivateKey = checkNotNull(privateKey) {
            "P2P/NAT ephemeral key was already closed"
        }
        privateKey = null
        val agreement = KeyAgreement.getInstance(algorithms.keyAgreement)
        return try {
            agreement.init(claimedPrivateKey)
            agreement.doPhase(decodePublicKey(peerPublicKeyX963), true)
            val generated = agreement.generateSecret()
            try {
                require(generated.size <= P256_FIELD_BYTES) { "P2P/NAT ECDH secret is invalid" }
                ByteArray(P256_FIELD_BYTES).also {
                    generated.copyInto(it, destinationOffset = it.size - generated.size)
                }
            } finally {
                generated.fill(0)
            }
        } finally {
            runCatching { claimedPrivateKey.destroy() }
        }
    }

    @Synchronized
    override fun close() {
        sharedSecretConsumed = true
        privateKey?.let { claimedPrivateKey ->
            privateKey = null
            runCatching { claimedPrivateKey.destroy() }
        }
    }

    companion object {
        fun generate(): P2pNatSessionEphemeralKey {
            val generator = KeyPairGenerator.getInstance("EC")
            generator.initialize(ECGenParameterSpec(P256_CURVE_NAME))
            val pair = generator.generateKeyPair()
            return P2pNatSessionEphemeralKey(
                publicKeyX963 = encodePublicKey(pair.public as ECPublicKey),
                privateKey = pair.private,
            )
        }

        internal fun fromPrivateScalarForTest(privateScalar: ByteArray): P2pNatSessionEphemeralKey {
            require(privateScalar.size == P256_FIELD_BYTES) { "P2P/NAT private scalar must be 32 bytes" }
            val scalar = BigInteger(1, privateScalar)
            require(scalar.signum() > 0 && scalar < P256_PARAMETERS.order) {
                "P2P/NAT private scalar is invalid"
            }
            val privateKey = KeyFactory.getInstance("EC").generatePrivate(
                ECPrivateKeySpec(scalar, P256_PARAMETERS),
            )
            val publicPoint = scalarMultiply(P256_PARAMETERS.generator, scalar)
            return P2pNatSessionEphemeralKey(
                publicKeyX963 = encodePoint(publicPoint),
                privateKey = privateKey,
            )
        }
    }
}

internal class P2pNatSealedPayload(ciphertext: ByteArray, tag: ByteArray) {
    private val ciphertextBytes = ciphertext.copyOf()
    private val tagBytes = tag.copyOf()
    val ciphertext: ByteArray get() = ciphertextBytes.copyOf()
    val tag: ByteArray get() = tagBytes.copyOf()

    fun copy(
        ciphertext: ByteArray = ciphertextBytes,
        tag: ByteArray = tagBytes,
    ): P2pNatSealedPayload = P2pNatSealedPayload(ciphertext, tag)
}

internal class P2pNatSessionKeys(
    val transcript: IdentitySessionTranscript,
    transcriptDigest: ByteArray,
    clientTrafficKey: ByteArray,
    runtimeTrafficKey: ByteArray,
    confirmationKey: ByteArray,
) {
    private val transcriptDigestBytes = transcriptDigest.copyOf()
    private val clientTrafficKeyBytes = clientTrafficKey.copyOf()
    private val runtimeTrafficKeyBytes = runtimeTrafficKey.copyOf()
    private val confirmationKeyBytes = confirmationKey.copyOf()
    private var cipherIssued = false
    val transcriptDigest: ByteArray get() = transcriptDigestBytes.copyOf()
    val clientTrafficKey: ByteArray get() = clientTrafficKeyBytes.copyOf()
    val runtimeTrafficKey: ByteArray get() = runtimeTrafficKeyBytes.copyOf()
    val confirmationKey: ByteArray get() = confirmationKeyBytes.copyOf()

    fun confirmation(role: P2pNatRole): ByteArray =
        transcript.keyConfirmation(confirmationKeyBytes, role)

    fun verifiesConfirmation(proof: ByteArray, role: P2pNatRole): Boolean =
        MessageDigest.isEqual(confirmation(role), proof)

    fun trafficKey(role: P2pNatRole): ByteArray =
        (if (role == P2pNatRole.CLIENT) clientTrafficKeyBytes else runtimeTrafficKeyBytes).copyOf()

    @Synchronized
    fun claimCipher() {
        check(!cipherIssued) { "P2P/NAT session cipher was already created" }
        cipherIssued = true
    }
}

internal data class P2pNatSessionVectorMaterial(
    val sharedSecret: ByteArray,
    val salt: ByteArray,
    val info: ByteArray,
    val prk: ByteArray,
    val okm: ByteArray,
)

internal object P2pNatSessionCrypto {
    private val KEY_INFO_PREFIX =
        "aetherlink-p2p-v1/session-keys/v1".toByteArray(Charsets.UTF_8) + byteArrayOf(0)

    fun deriveKeys(
        localRole: P2pNatRole,
        localEphemeralKey: P2pNatSessionEphemeralKey,
        transcript: IdentitySessionTranscript,
        algorithms: P2pNatJcaAlgorithms = P2pNatJcaAlgorithms(),
    ): P2pNatSessionKeys {
        val expectedLocal = if (localRole == P2pNatRole.CLIENT) {
            transcript.clientEphemeralKey
        } else {
            transcript.runtimeEphemeralKey
        }
        require(localEphemeralKey.publicKeyX963.contentEquals(expectedLocal)) {
            "P2P/NAT local key does not match transcript role"
        }
        val peer = if (localRole == P2pNatRole.CLIENT) {
            transcript.runtimeEphemeralKey
        } else {
            transcript.clientEphemeralKey
        }
        val sharedSecret = localEphemeralKey.sharedSecret(peer, algorithms)
        val transcriptDigest = transcript.digest()
        val info = KEY_INFO_PREFIX + transcriptDigest
        val prk = hmac(algorithms.mac, transcriptDigest, sharedSecret)
        val okm = hkdfExpand(algorithms.mac, prk, info, 96)
        return P2pNatSessionKeys(
            transcript = transcript,
            transcriptDigest = transcriptDigest,
            clientTrafficKey = okm.copyOfRange(0, 32),
            runtimeTrafficKey = okm.copyOfRange(32, 64),
            confirmationKey = okm.copyOfRange(64, 96),
        )
    }

    fun vectorMaterial(
        localRole: P2pNatRole,
        localEphemeralKey: P2pNatSessionEphemeralKey,
        transcript: IdentitySessionTranscript,
        algorithms: P2pNatJcaAlgorithms = P2pNatJcaAlgorithms(),
    ): P2pNatSessionVectorMaterial {
        val expectedLocal = if (localRole == P2pNatRole.CLIENT) {
            transcript.clientEphemeralKey
        } else {
            transcript.runtimeEphemeralKey
        }
        require(localEphemeralKey.publicKeyX963.contentEquals(expectedLocal)) {
            "P2P/NAT local key does not match transcript role"
        }
        val peer = if (localRole == P2pNatRole.CLIENT) {
            transcript.runtimeEphemeralKey
        } else {
            transcript.clientEphemeralKey
        }
        val sharedSecret = localEphemeralKey.sharedSecret(peer, algorithms)
        val transcriptDigest = transcript.digest()
        val info = KEY_INFO_PREFIX + transcriptDigest
        val prk = hmac(algorithms.mac, transcriptDigest, sharedSecret)
        return P2pNatSessionVectorMaterial(
            sharedSecret = sharedSecret,
            salt = transcriptDigest,
            info = info,
            prk = prk,
            okm = hkdfExpand(algorithms.mac, prk, info, 96),
        )
    }

    private fun hkdfExpand(
        macAlgorithm: String,
        prk: ByteArray,
        info: ByteArray,
        outputByteCount: Int,
    ): ByteArray {
        require(outputByteCount in 1..(255 * 32)) { "P2P/NAT HKDF output size is invalid" }
        val result = ByteArray(outputByteCount)
        var previous = ByteArray(0)
        var offset = 0
        var block = 1
        while (offset < outputByteCount) {
            previous = hmac(macAlgorithm, prk, previous + info + byteArrayOf(block.toByte()))
            val count = minOf(previous.size, outputByteCount - offset)
            previous.copyInto(result, destinationOffset = offset, endIndex = count)
            offset += count
            block += 1
        }
        return result
    }
}

internal class P2pNatSessionHandshake(
    private val localRole: P2pNatRole,
    private val keys: P2pNatSessionKeys,
    private val algorithms: P2pNatJcaAlgorithms = P2pNatJcaAlgorithms(),
) {
    private var localConfirmationEmitted = false
    private var peerConfirmationVerified = false
    private var cipherCreated = false

    @Synchronized
    fun localConfirmation(): ByteArray {
        val proof = keys.confirmation(localRole)
        localConfirmationEmitted = true
        return proof
    }

    @Synchronized
    fun acceptPeerConfirmation(proof: ByteArray) {
        val peerRole = if (localRole == P2pNatRole.CLIENT) P2pNatRole.RUNTIME else P2pNatRole.CLIENT
        require(keys.verifiesConfirmation(proof, peerRole)) { "P2P/NAT peer confirmation is invalid" }
        peerConfirmationVerified = true
    }

    @Synchronized
    fun makeCipher(): P2pNatSessionCipher {
        check(localConfirmationEmitted && peerConfirmationVerified) {
            "P2P/NAT bidirectional key confirmation is incomplete"
        }
        check(!cipherCreated) { "P2P/NAT session cipher was already created" }
        keys.claimCipher()
        cipherCreated = true
        return P2pNatSessionCipher(localRole, keys, algorithms)
    }
}

internal class P2pNatSessionCipher(
    private val localRole: P2pNatRole,
    private val keys: P2pNatSessionKeys,
    private val algorithms: P2pNatJcaAlgorithms = P2pNatJcaAlgorithms(),
    private var sendSequence: ULong = 0uL,
    private var receiveSequence: ULong = 0uL,
) {
    @Synchronized
    fun seal(plaintext: ByteArray): P2pNatSealedPayload {
        sendSequence.requireSequence()
        val sealed = crypt(
            mode = Cipher.ENCRYPT_MODE,
            input = plaintext,
            senderRole = localRole,
            sequence = sendSequence,
        )
        sendSequence = sendSequence.nextSequence()
        return P2pNatSealedPayload(
            ciphertext = sealed.copyOfRange(0, sealed.size - GCM_TAG_BYTES),
            tag = sealed.copyOfRange(sealed.size - GCM_TAG_BYTES, sealed.size),
        )
    }

    @Synchronized
    fun open(payload: P2pNatSealedPayload): ByteArray {
        receiveSequence.requireSequence()
        val peerRole = if (localRole == P2pNatRole.CLIENT) P2pNatRole.RUNTIME else P2pNatRole.CLIENT
        val plaintext = crypt(
            mode = Cipher.DECRYPT_MODE,
            input = payload.ciphertext + payload.tag,
            senderRole = peerRole,
            sequence = receiveSequence,
        )
        receiveSequence = receiveSequence.nextSequence()
        return plaintext
    }

    private fun crypt(
        mode: Int,
        input: ByteArray,
        senderRole: P2pNatRole,
        sequence: ULong,
    ): ByteArray {
        val cipher = Cipher.getInstance(algorithms.cipher)
        cipher.init(
            mode,
            SecretKeySpec(keys.trafficKey(senderRole), "AES"),
            GCMParameterSpec(GCM_TAG_BITS, nonce(senderRole, sequence)),
        )
        cipher.updateAAD(aad(keys.transcript, senderRole, sequence))
        return cipher.doFinal(input)
    }

    companion object {
        internal fun nonce(role: P2pNatRole, sequence: ULong): ByteArray {
            require(sequence < ULong.MAX_VALUE) { "P2P/NAT sequence is exhausted" }
            val direction = if (role == P2pNatRole.CLIENT) "CLNT" else "RUNT"
            return direction.toByteArray(Charsets.US_ASCII) + sequence.toBigEndianBytes()
        }

        internal fun aad(
            transcript: IdentitySessionTranscript,
            senderRole: P2pNatRole,
            sequence: ULong,
        ): ByteArray = P2pNatCanonicalCodec.encode(transcript) +
            "aetherlink-p2p-v1:traffic:${senderRole.wireValue}:".toByteArray(Charsets.UTF_8) +
            sequence.toBigEndianBytes()
    }
}

private const val P256_CURVE_NAME = "secp256r1"
private const val P256_FIELD_BYTES = 32
private const val GCM_TAG_BITS = 128
private const val GCM_TAG_BYTES = 16
private val BIG_INTEGER_TWO = BigInteger.valueOf(2L)

private val P256_PARAMETERS: ECParameterSpec = AlgorithmParameters.getInstance("EC").run {
    init(ECGenParameterSpec(P256_CURVE_NAME))
    getParameterSpec(ECParameterSpec::class.java)
}

private fun encodePublicKey(key: ECPublicKey): ByteArray = encodePoint(key.w)

private fun encodePoint(point: ECPoint): ByteArray = byteArrayOf(0x04) +
    point.affineX.toFixedUnsigned(P256_FIELD_BYTES) +
    point.affineY.toFixedUnsigned(P256_FIELD_BYTES)

private fun decodePublicKey(encoded: ByteArray): java.security.PublicKey {
    require(encoded.size == 65 && encoded.first() == 0x04.toByte()) {
        "P2P/NAT public key must be canonical X9.63 uncompressed P-256"
    }
    val point = ECPoint(
        BigInteger(1, encoded.copyOfRange(1, 33)),
        BigInteger(1, encoded.copyOfRange(33, 65)),
    )
    require(isOnCurve(point)) { "P2P/NAT public key is not on P-256" }
    return KeyFactory.getInstance("EC").generatePublic(ECPublicKeySpec(point, P256_PARAMETERS))
}

private fun isOnCurve(point: ECPoint): Boolean {
    val prime = (P256_PARAMETERS.curve.field as? ECFieldFp)?.p ?: return false
    val x = point.affineX
    val y = point.affineY
    if (x.signum() < 0 || y.signum() < 0 || x >= prime || y >= prime) return false
    val left = y.modPow(BIG_INTEGER_TWO, prime)
    val right = x.modPow(BigInteger.valueOf(3), prime)
        .add(P256_PARAMETERS.curve.a.multiply(x))
        .add(P256_PARAMETERS.curve.b)
        .mod(prime)
    return left == right
}

private fun scalarMultiply(point: ECPoint, scalar: BigInteger): ECPoint {
    val prime = (P256_PARAMETERS.curve.field as ECFieldFp).p
    var result: ECPoint? = null
    var addend: ECPoint? = point
    var value = scalar
    while (value.signum() > 0) {
        if (value.testBit(0)) result = addPoints(result, addend, prime)
        addend = addPoints(addend, addend, prime)
        value = value.shiftRight(1)
    }
    return requireNotNull(result) { "P2P/NAT scalar multiplication failed" }
}

private fun addPoints(left: ECPoint?, right: ECPoint?, prime: BigInteger): ECPoint? {
    if (left == null) return right
    if (right == null) return left
    if (left.affineX == right.affineX && left.affineY.add(right.affineY).mod(prime) == BigInteger.ZERO) {
        return null
    }
    val slope = if (left == right) {
        left.affineX.modPow(BIG_INTEGER_TWO, prime).multiply(BigInteger.valueOf(3))
            .add(P256_PARAMETERS.curve.a)
            .multiply(left.affineY.multiply(BIG_INTEGER_TWO).modInverse(prime))
            .mod(prime)
    } else {
        right.affineY.subtract(left.affineY)
            .multiply(right.affineX.subtract(left.affineX).mod(prime).modInverse(prime))
            .mod(prime)
    }
    val x = slope.modPow(BIG_INTEGER_TWO, prime).subtract(left.affineX).subtract(right.affineX).mod(prime)
    val y = slope.multiply(left.affineX.subtract(x)).subtract(left.affineY).mod(prime)
    return ECPoint(x, y)
}

private fun BigInteger.toFixedUnsigned(size: Int): ByteArray {
    val raw = toByteArray()
    val unsigned = if (raw.size > size && raw.first() == 0.toByte()) raw.copyOfRange(1, raw.size) else raw
    require(unsigned.size <= size) { "P2P/NAT P-256 coordinate is invalid" }
    return ByteArray(size).also { unsigned.copyInto(it, destinationOffset = size - unsigned.size) }
}

private fun hmac(algorithm: String, key: ByteArray, input: ByteArray): ByteArray {
    val mac = Mac.getInstance(algorithm)
    mac.init(SecretKeySpec(key, algorithm))
    return mac.doFinal(input)
}

private fun ULong.requireSequence(): ULong {
    require(this < ULong.MAX_VALUE - 1uL) { "P2P/NAT sequence is exhausted" }
    return this
}

private fun ULong.nextSequence(): ULong {
    require(this < ULong.MAX_VALUE - 1uL) { "P2P/NAT sequence is exhausted" }
    return this + 1uL
}

private fun ULong.toBigEndianBytes(): ByteArray =
    ByteBuffer.allocate(Long.SIZE_BYTES).putLong(toLong()).array()
