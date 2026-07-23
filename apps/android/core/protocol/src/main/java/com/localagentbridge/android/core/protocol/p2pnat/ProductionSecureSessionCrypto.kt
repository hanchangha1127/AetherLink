package com.localagentbridge.android.core.protocol.p2pnat

import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import javax.crypto.AEADBadTagException
import javax.crypto.Cipher
import javax.crypto.Mac
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

/** No-network production key schedule and ordered record contract. */
object ProductionSecureSessionCryptoContract {
    const val KEY_CONFIRMATION_OBJECT_TYPE: Int = 29
    const val ENCRYPTED_RECORD_OBJECT_TYPE: Int = 30
    const val MAXIMUM_KEY_CONFIRMATION_BYTES: Int = 384
    const val MAXIMUM_ENCRYPTED_RECORD_BYTES: Int = 1_048_576
    const val MAXIMUM_PLAINTEXT_BYTES: Int = 1_048_448
    const val MAXIMUM_CIPHERTEXT_BYTES: Int = 1_048_448
    const val MAXIMUM_EPOCH: UInt = 15u
    const val MAXIMUM_EPOCH_RECORDS: ULong = 1_048_576uL
    const val MAXIMUM_EPOCH_PLAINTEXT_BYTES: ULong = 1_073_741_824uL
    const val MAXIMUM_SESSION_RECORDS: ULong = 16_777_216uL
    const val MAXIMUM_SESSION_PLAINTEXT_BYTES: ULong = 17_179_869_184uL
}

enum class ProductionSecureSessionCryptoError {
    MALFORMED_CANONICAL,
    INVALID_VALUE,
    BINDING_MISMATCH,
    KEY_MISMATCH,
    KEY_ALREADY_USED,
    NOT_YET_VALID,
    EXPIRED,
    CLOCK_REGRESSION,
    CONFIRMATION_REQUIRED,
    CONFIRMATION_CONFLICT,
    AUTHENTICATION_FAILED,
    OUT_OF_ORDER,
    LIMIT_EXCEEDED,
    KEY_UPDATE_REQUIRED,
    ALREADY_USED,
    CRYPTO_FAILURE,
    TERMINAL,
    CLOSED,
}

class ProductionSecureSessionCryptoException(
    val reason: ProductionSecureSessionCryptoError,
    cause: Throwable? = null,
) : IllegalStateException(reason.name.lowercase(), cause)

enum class ProductionSecureSessionRecordContentType(val wireValue: Int) {
    APPLICATION(1),
    KEY_UPDATE(2);

    companion object {
        internal fun decode(value: Int): ProductionSecureSessionRecordContentType =
            entries.singleOrNull { it.wireValue == value }
                ?: cryptoFail(ProductionSecureSessionCryptoError.INVALID_VALUE)
    }
}

class ProductionSecureSessionKeyConfirmation internal constructor(
    val suite: String,
    val profile: String,
    val sessionId: String,
    val object7DigestHex: String,
    val object26DigestHex: String,
    val confirmingRole: P2pNatRole,
    val epoch: UInt,
    proof: ByteArray,
) {
    private val proofBytes = proof.copyOf()
    val proof: ByteArray get() = proofBytes.copyOf()

    internal fun prefixFields(): List<ByteArray> = listOf(
        ProductionC1InternalBridge.ascii(suite),
        ProductionC1InternalBridge.ascii(profile),
        ProductionC1InternalBridge.ascii(sessionId),
        ProductionC1InternalBridge.ascii(object7DigestHex),
        ProductionC1InternalBridge.ascii(object26DigestHex),
        ProductionC1InternalBridge.ascii(confirmingRole.wireValue),
        ProductionC1InternalBridge.be(epoch),
    )
}

class ProductionSecureSessionEncryptedRecord internal constructor(
    val sessionId: String,
    val senderRole: P2pNatRole,
    val epoch: UInt,
    val sequence: ULong,
    val contentType: ProductionSecureSessionRecordContentType,
    ciphertext: ByteArray,
    tag: ByteArray,
) {
    private val ciphertextBytes = ciphertext.copyOf()
    private val tagBytes = tag.copyOf()
    val ciphertext: ByteArray get() = ciphertextBytes.copyOf()
    val tag: ByteArray get() = tagBytes.copyOf()

    internal fun prefixFields(): List<ByteArray> = listOf(
        ProductionC1InternalBridge.ascii(sessionId),
        byteArrayOf(senderRole.cryptoRoleByte()),
        ProductionC1InternalBridge.be(epoch),
        ProductionC1InternalBridge.be(sequence),
        byteArrayOf(contentType.wireValue.toByte()),
    )
}

internal object ProductionSecureSessionCryptoCodec {
    fun encode(value: ProductionSecureSessionKeyConfirmation): ByteArray {
        validateConfirmation(value)
        return ProductionC1InternalBridge.encode(
            ProductionSecureSessionCryptoContract.KEY_CONFIRMATION_OBJECT_TYPE,
            value.prefixFields() + value.proof,
        ).also {
            cryptoRequire(
                it.size <= ProductionSecureSessionCryptoContract.MAXIMUM_KEY_CONFIRMATION_BYTES,
                ProductionSecureSessionCryptoError.LIMIT_EXCEEDED,
            )
        }
    }

    fun decodeConfirmation(data: ByteArray): ProductionSecureSessionKeyConfirmation = decodeCanonical {
        val fields = ProductionC1InternalBridge.decode(
            data,
            ProductionSecureSessionCryptoContract.KEY_CONFIRMATION_OBJECT_TYPE,
            8,
            ProductionSecureSessionCryptoContract.MAXIMUM_KEY_CONFIRMATION_BYTES,
        )
        val result = ProductionSecureSessionKeyConfirmation(
            suite = ProductionC1InternalBridge.text(fields[0]),
            profile = ProductionC1InternalBridge.text(fields[1]),
            sessionId = ProductionC1InternalBridge.text(fields[2]),
            object7DigestHex = ProductionC1InternalBridge.text(fields[3]),
            object26DigestHex = ProductionC1InternalBridge.text(fields[4]),
            confirmingRole = P2pNatRole.decode(ProductionC1InternalBridge.text(fields[5])),
            epoch = ProductionC1InternalBridge.uint32(fields[6]),
            proof = fields[7],
        )
        validateConfirmation(result)
        cryptoRequire(
            encode(result).contentEquals(data),
            ProductionSecureSessionCryptoError.MALFORMED_CANONICAL,
        )
        result
    }

    fun confirmationPrefix(value: ProductionSecureSessionKeyConfirmation): ByteArray {
        validateConfirmation(value, requireProof = false)
        return ProductionC1InternalBridge.encode(
            ProductionSecureSessionCryptoContract.KEY_CONFIRMATION_OBJECT_TYPE,
            value.prefixFields(),
        )
    }

    fun encode(value: ProductionSecureSessionEncryptedRecord): ByteArray {
        validateRecord(value)
        return ProductionC1InternalBridge.encode(
            ProductionSecureSessionCryptoContract.ENCRYPTED_RECORD_OBJECT_TYPE,
            value.prefixFields() + listOf(value.ciphertext, value.tag),
        ).also {
            cryptoRequire(
                it.size <= ProductionSecureSessionCryptoContract.MAXIMUM_ENCRYPTED_RECORD_BYTES,
                ProductionSecureSessionCryptoError.LIMIT_EXCEEDED,
            )
        }
    }

    fun decodeRecord(data: ByteArray): ProductionSecureSessionEncryptedRecord = decodeCanonical {
        val fields = ProductionC1InternalBridge.decode(
            data,
            ProductionSecureSessionCryptoContract.ENCRYPTED_RECORD_OBJECT_TYPE,
            7,
            ProductionSecureSessionCryptoContract.MAXIMUM_ENCRYPTED_RECORD_BYTES,
        )
        cryptoRequire(fields[1].size == 1, ProductionSecureSessionCryptoError.INVALID_VALUE)
        cryptoRequire(fields[4].size == 1, ProductionSecureSessionCryptoError.INVALID_VALUE)
        val result = ProductionSecureSessionEncryptedRecord(
            sessionId = ProductionC1InternalBridge.text(fields[0]),
            senderRole = cryptoRole(fields[1][0].toInt() and 0xff),
            epoch = ProductionC1InternalBridge.uint32(fields[2]),
            sequence = ProductionC1InternalBridge.uint64(fields[3]),
            contentType = ProductionSecureSessionRecordContentType.decode(fields[4][0].toInt() and 0xff),
            ciphertext = fields[5],
            tag = fields[6],
        )
        validateRecord(result)
        cryptoRequire(
            encode(result).contentEquals(data),
            ProductionSecureSessionCryptoError.MALFORMED_CANONICAL,
        )
        result
    }

    fun recordPrefix(value: ProductionSecureSessionEncryptedRecord): ByteArray {
        validateRecord(value)
        return ProductionC1InternalBridge.encode(
            ProductionSecureSessionCryptoContract.ENCRYPTED_RECORD_OBJECT_TYPE,
            value.prefixFields(),
        )
    }

    private fun validateConfirmation(
        value: ProductionSecureSessionKeyConfirmation,
        requireProof: Boolean = true,
    ) {
        cryptoRequire(
            value.suite == ProductionSecureSessionContract.SUITE &&
                value.profile == ProductionSecureSessionContract.PROFILE &&
                value.sessionId.isLowerHex(32) &&
                value.object7DigestHex.isLowerHex(64) &&
                value.object26DigestHex.isLowerHex(64) &&
                value.epoch == 0u &&
                (!requireProof || value.proof.size == SHA256_BYTES),
            ProductionSecureSessionCryptoError.INVALID_VALUE,
        )
    }

    private fun validateRecord(value: ProductionSecureSessionEncryptedRecord) {
        cryptoRequire(
            value.sessionId.isLowerHex(32) &&
                value.epoch <= ProductionSecureSessionCryptoContract.MAXIMUM_EPOCH &&
                value.sequence < ProductionSecureSessionCryptoContract.MAXIMUM_EPOCH_RECORDS &&
                value.ciphertext.size <= ProductionSecureSessionCryptoContract.MAXIMUM_CIPHERTEXT_BYTES &&
                value.tag.size == GCM_TAG_BYTES,
            ProductionSecureSessionCryptoError.INVALID_VALUE,
        )
    }

    private inline fun <T> decodeCanonical(block: () -> T): T = try {
        block()
    } catch (error: ProductionSecureSessionCryptoException) {
        throw error
    } catch (error: Exception) {
        throw ProductionSecureSessionCryptoException(
            ProductionSecureSessionCryptoError.MALFORMED_CANONICAL,
            error,
        )
    }
}

internal data class ProductionSecureSessionJcaAlgorithms(
    val keyAgreement: String = "ECDH",
    val mac: String = "HmacSHA256",
    val cipher: String = "AES/GCM/NoPadding",
    /** Test seam separating post-derive confirmation failures from root KDF failures. */
    val confirmationMac: String = mac,
)

internal class ProductionSecureSessionVectorMaterial(
    bindingDigest: ByteArray,
    sharedSecret: ByteArray,
    salt: ByteArray,
    prk: ByteArray,
    rootInfo: ByteArray,
    rootOutput: ByteArray,
) {
    private val bindingDigestBytes = bindingDigest.copyOf()
    private val sharedSecretBytes = sharedSecret.copyOf()
    private val saltBytes = salt.copyOf()
    private val prkBytes = prk.copyOf()
    private val rootInfoBytes = rootInfo.copyOf()
    private val rootOutputBytes = rootOutput.copyOf()

    val bindingDigest: ByteArray get() = bindingDigestBytes.copyOf()
    val sharedSecret: ByteArray get() = sharedSecretBytes.copyOf()
    val salt: ByteArray get() = saltBytes.copyOf()
    val prk: ByteArray get() = prkBytes.copyOf()
    val rootInfo: ByteArray get() = rootInfoBytes.copyOf()
    val rootOutput: ByteArray get() = rootOutputBytes.copyOf()
}

internal object ProductionSecureSessionCrypto {
    internal fun object7Object26KdfBindingDigestHex(
        binding: VerifiedProductionC1CandidateP2PKeyScheduleBinding,
    ): String {
        val transcriptBytes = ProductionSecureSessionCodec.encode(binding.transcript)
        val grantBytes = binding.grantAuthorization.authorization.canonicalBytes()
        var bindingClaims = ByteArray(0)
        var digest = ByteArray(0)
        return try {
            bindingClaims = transcriptBytes.size.toUInt32Bytes() + transcriptBytes +
                grantBytes.size.toUInt32Bytes() + grantBytes
            digest = sha256(
                ProductionC1InternalBridge.transcript(BINDING_DOMAIN, bindingClaims),
            )
            digest.joinToString(separator = "") { byte -> "%02x".format(byte.toInt() and 0xff) }
        } finally {
            transcriptBytes.wipe()
            grantBytes.wipe()
            bindingClaims.wipe()
            digest.wipe()
        }
    }

    fun derive(
        binding: VerifiedProductionC1CandidateP2PKeyScheduleBinding,
        localEphemeralKey: P2pNatSessionEphemeralKey,
        nowMs: ULong,
        algorithms: ProductionSecureSessionJcaAlgorithms = ProductionSecureSessionJcaAlgorithms(),
    ): ProductionSecureSessionHandshake {
        val material = deriveMaterial(binding, localEphemeralKey, nowMs, algorithms, captureVector = false)
        return try {
            ProductionSecureSessionHandshake(
                binding = binding,
                bindingDigest = material.bindingDigest,
                clientConfirmationKey = material.rootOutput.copyOfRange(0, 32),
                runtimeConfirmationKey = material.rootOutput.copyOfRange(32, 64),
                clientEpochZeroSecret = material.rootOutput.copyOfRange(64, 96),
                runtimeEpochZeroSecret = material.rootOutput.copyOfRange(96, 128),
                nowMs = nowMs,
                algorithms = algorithms,
            )
        } finally {
            material.wipe()
        }
    }

    fun vectorMaterialForTest(
        binding: VerifiedProductionC1CandidateP2PKeyScheduleBinding,
        localEphemeralKey: P2pNatSessionEphemeralKey,
        nowMs: ULong,
        algorithms: ProductionSecureSessionJcaAlgorithms = ProductionSecureSessionJcaAlgorithms(),
    ): ProductionSecureSessionVectorMaterial {
        val material = deriveMaterial(binding, localEphemeralKey, nowMs, algorithms, captureVector = true)
        return try {
            requireNotNull(material.vectorMaterial)
        } finally {
            material.wipe()
        }
    }

    private fun deriveMaterial(
        binding: VerifiedProductionC1CandidateP2PKeyScheduleBinding,
        localEphemeralKey: P2pNatSessionEphemeralKey,
        nowMs: ULong,
        algorithms: ProductionSecureSessionJcaAlgorithms,
        captureVector: Boolean,
    ): DerivedRootMaterial {
        validateBinding(binding, nowMs)
        val transcriptBytes = ProductionSecureSessionCodec.encode(binding.transcript)
        val grantBytes = binding.grantAuthorization.authorization.canonicalBytes()
        val bindingClaims = transcriptBytes.size.toUInt32Bytes() + transcriptBytes +
            grantBytes.size.toUInt32Bytes() + grantBytes
        val bindingDigest = sha256(
            ProductionC1InternalBridge.transcript(BINDING_DOMAIN, bindingClaims),
        )
        val expectedLocalKey = when (binding.localRole) {
            P2pNatRole.CLIENT -> binding.transcript.clientEphemeralPublicKey
            P2pNatRole.RUNTIME -> binding.transcript.runtimeEphemeralPublicKey
        }
        cryptoRequire(
            localEphemeralKey.publicKeyX963.contentEquals(expectedLocalKey),
            ProductionSecureSessionCryptoError.KEY_MISMATCH,
        )
        val peerKey = when (binding.localRole) {
            P2pNatRole.CLIENT -> binding.transcript.runtimeEphemeralPublicKey
            P2pNatRole.RUNTIME -> binding.transcript.clientEphemeralPublicKey
        }
        val sharedSecret = try {
            localEphemeralKey.sharedSecret(
                peerKey,
                P2pNatJcaAlgorithms(
                    keyAgreement = algorithms.keyAgreement,
                    mac = algorithms.mac,
                    cipher = algorithms.cipher,
                ),
            )
        } catch (error: IllegalStateException) {
            throw ProductionSecureSessionCryptoException(
                ProductionSecureSessionCryptoError.KEY_ALREADY_USED,
                error,
            )
        } catch (error: Exception) {
            throw ProductionSecureSessionCryptoException(
                ProductionSecureSessionCryptoError.CRYPTO_FAILURE,
                error,
            )
        }
        var prk = ByteArray(0)
        var rootInfo = ByteArray(0)
        var rootOutput = ByteArray(0)
        return try {
            cryptoRequire(
                sharedSecret.size == P256_SHARED_SECRET_BYTES && sharedSecret.any { it != 0.toByte() },
                ProductionSecureSessionCryptoError.INVALID_VALUE,
            )
            prk = cryptoHmac(algorithms.mac, bindingDigest, sharedSecret)
            rootInfo = ProductionC1InternalBridge.transcript(ROOT_DOMAIN, bindingDigest)
            rootOutput = hkdfExpand(algorithms.mac, prk, rootInfo, ROOT_OUTPUT_BYTES)
            return DerivedRootMaterial(
                bindingDigest = bindingDigest,
                rootOutput = rootOutput,
                vectorMaterial = if (captureVector) {
                    ProductionSecureSessionVectorMaterial(
                        bindingDigest,
                        sharedSecret,
                        bindingDigest,
                        prk,
                        rootInfo,
                        rootOutput,
                    )
                } else {
                    null
                },
            )
        } finally {
            sharedSecret.wipe()
            prk.wipe()
            rootInfo.wipe()
            rootOutput.wipe()
            bindingClaims.wipe()
        }
    }

    private fun validateBinding(
        binding: VerifiedProductionC1CandidateP2PKeyScheduleBinding,
        nowMs: ULong,
    ) {
        val transcript = binding.transcript
        val authorization = binding.grantAuthorization.authorization
        val expectedContext = ProductionC1PreauthorizationSessionContext(transcript)
        cryptoRequire(
            binding.securityContext == expectedContext &&
                authorization.sessionId == transcript.sessionId &&
                authorization.pairBindingDigest == transcript.pairBindingDigest &&
                authorization.pairEpoch == transcript.pairEpoch &&
                authorization.generation == transcript.generation &&
                authorization.clientIdentityFingerprint == transcript.clientIdentityFingerprint &&
                authorization.runtimeIdentityFingerprint == transcript.runtimeIdentityFingerprint &&
                authorization.securityContextDigest == expectedContext.digestHex() &&
                transcript.routeAuthorizationKind == ProductionRouteAuthorizationKind.P2P_DIRECT &&
                transcript.routeAuthorizationDigest == binding.grantAuthorization.digestHex &&
                (binding.localRole == authorization.initiatorRole ||
                    binding.localRole == authorization.connectorTargetRole),
            ProductionSecureSessionCryptoError.BINDING_MISMATCH,
        )
        cryptoRequire(
            nowMs >= authorization.effectiveNotBeforeMs,
            ProductionSecureSessionCryptoError.NOT_YET_VALID,
        )
        cryptoRequire(nowMs < authorization.expiresAtMs, ProductionSecureSessionCryptoError.EXPIRED)
    }

    private class DerivedRootMaterial(
        bindingDigest: ByteArray,
        rootOutput: ByteArray,
        val vectorMaterial: ProductionSecureSessionVectorMaterial?,
    ) {
        val bindingDigest = bindingDigest.copyOf()
        val rootOutput = rootOutput.copyOf()

        fun wipe() {
            bindingDigest.wipe()
            rootOutput.wipe()
        }
    }
}

/**
 * Opaque production ephemeral key. The private key and raw ECDH operation never cross the
 * protocol boundary; callers can only publish the public point and transfer the one-shot key to
 * the verified authority engine below.
 */
class ProductionSecureSessionEphemeralKey private constructor(
    internal val rawKey: P2pNatSessionEphemeralKey,
) : AutoCloseable {
    val publicKeyX963: ByteArray get() = rawKey.publicKeyX963

    /** True after the private key has either been used for ECDH or explicitly discarded. */
    val isConsumedOrClosed: Boolean get() = rawKey.isConsumedOrClosed

    /** Invalidates an untransferred one-shot key and releases its private-key reference. */
    override fun close() = rawKey.close()

    companion object {
        @JvmStatic
        fun generate(): ProductionSecureSessionEphemeralKey =
            ProductionSecureSessionEphemeralKey(P2pNatSessionEphemeralKey.generate())

        internal fun fromRawForTest(
            rawKey: P2pNatSessionEphemeralKey,
        ): ProductionSecureSessionEphemeralKey = ProductionSecureSessionEphemeralKey(rawKey)
    }
}

/**
 * Minimal opaque bridge used by an authority-lease owner. It deliberately exposes neither the
 * handshake nor traffic keys. Construction consumes only a verifier-minted exact object-7 /
 * object-26 binding and the one-shot opaque local key.
 */
class ProductionAuthorityBoundSecureSessionEngine private constructor(
    private val handshake: ProductionSecureSessionHandshake,
) : AutoCloseable {
    private var cipher: ProductionSecureSessionCipher? = null
    private var invalidated = false
    private var terminal = false

    @get:Synchronized
    val isTerminal: Boolean get() = invalidated || terminal

    @Synchronized
    fun localConfirmation(nowMs: ULong): ByteArray {
        requireLiveHandshake()
        return trackTerminal { handshake.localConfirmation(nowMs) }
    }

    @Synchronized
    fun markLocalConfirmationSent(encodedConfirmation: ByteArray, nowMs: ULong) {
        requireLiveHandshake()
        trackTerminal(ProductionSecureSessionCryptoError.AUTHENTICATION_FAILED) {
            handshake.markLocalConfirmationSent(encodedConfirmation, nowMs)
        }
    }

    @Synchronized
    fun acceptPeerConfirmation(encodedConfirmation: ByteArray, nowMs: ULong) {
        requireLiveHandshake()
        trackTerminal(ProductionSecureSessionCryptoError.AUTHENTICATION_FAILED) {
            handshake.acceptPeerConfirmation(encodedConfirmation, nowMs)
        }
    }

    @Synchronized
    fun activate(nowMs: ULong) {
        requireNotInvalidated()
        if (cipher != null) cryptoFail(ProductionSecureSessionCryptoError.ALREADY_USED)
        cipher = trackTerminal { handshake.activate(nowMs) }
    }

    @Synchronized
    fun sealApplication(
        plaintext: ByteArray,
        nowMs: ULong,
    ): ProductionSecureSessionSealResult =
        trackTerminal { requireCipher().sealApplication(plaintext, nowMs) }

    @Synchronized
    fun sealKeyUpdate(nowMs: ULong): ProductionSecureSessionSealResult =
        trackTerminal { requireCipher().sealKeyUpdate(nowMs) }

    @Synchronized
    fun open(
        encodedRecord: ByteArray,
        nowMs: ULong,
    ): ProductionSecureSessionOpenResult =
        trackTerminal { requireCipher().open(encodedRecord, nowMs) }

    @Synchronized
    fun invalidate() {
        if (invalidated) return
        invalidated = true
        terminal = true
        handshake.invalidate()
        cipher?.invalidate()
    }

    @Synchronized
    override fun close() {
        invalidated = true
        terminal = true
        handshake.close()
        cipher?.close()
        cipher = null
    }

    private fun requireLiveHandshake() {
        requireNotInvalidated()
        if (cipher != null) cryptoFail(ProductionSecureSessionCryptoError.ALREADY_USED)
    }

    private fun requireCipher(): ProductionSecureSessionCipher {
        requireNotInvalidated()
        return cipher ?: cryptoFail(ProductionSecureSessionCryptoError.CONFIRMATION_REQUIRED)
    }

    private fun requireNotInvalidated() {
        if (invalidated) cryptoFail(ProductionSecureSessionCryptoError.TERMINAL)
    }

    private inline fun <Value> trackTerminal(
        additionalTerminalError: ProductionSecureSessionCryptoError? = null,
        block: () -> Value,
    ): Value = try {
        block()
    } catch (error: ProductionSecureSessionCryptoException) {
        if (error.reason in TERMINAL_ENGINE_ERRORS || error.reason == additionalTerminalError) {
            terminal = true
        }
        throw error
    }

    companion object {
        @JvmStatic
        fun derive(
            binding: VerifiedProductionC1CandidateP2PKeyScheduleBinding,
            localEphemeralKey: ProductionSecureSessionEphemeralKey,
            nowMs: ULong,
        ): ProductionAuthorityBoundSecureSessionEngine =
            ProductionAuthorityBoundSecureSessionEngine(
                ProductionSecureSessionCrypto.derive(binding, localEphemeralKey.rawKey, nowMs),
            )
    }
}

class ProductionSecureSessionSealResult internal constructor(
    record: ByteArray,
    val keyUpdateRequired: Boolean,
    val terminalAfterRecord: Boolean,
) {
    private val recordBytes = record.copyOf()
    val record: ByteArray get() = recordBytes.copyOf()

    /** Transfers a copy across the authority facade and destroys this result's retained copy. */
    @Synchronized
    fun takeRecordAndWipe(): ByteArray = recordBytes.copyOf().also { recordBytes.wipe() }
}

class ProductionSecureSessionOpenResult internal constructor(
    plaintext: ByteArray,
    val contentType: ProductionSecureSessionRecordContentType,
    val keyUpdateRequired: Boolean,
    val terminalAfterRecord: Boolean,
) {
    private val plaintextBytes = plaintext.copyOf()
    val plaintext: ByteArray get() = plaintextBytes.copyOf()

    /** Transfers a copy across the authority facade and destroys this result's retained copy. */
    @Synchronized
    fun takePlaintextAndWipe(): ByteArray = plaintextBytes.copyOf().also { plaintextBytes.wipe() }
}

/** Immutable, secret-free boundary input used by parity tests and the live state machine. */
internal data class ProductionSecureSessionCounterSnapshot(
    val epoch: UInt,
    val epochRecords: ULong,
    val epochPlaintextBytes: ULong,
    val sessionRecords: ULong,
    val sessionPlaintextBytes: ULong,
)

internal data class ProductionSecureSessionCapacityDecision(
    val keyUpdateRequired: Boolean,
    val terminalAfterRecord: Boolean,
)

internal data class ProductionSecureSessionKeyUpdateCapacityDecision(
    val nextEpoch: UInt,
    val terminalAfterRecord: Boolean,
)

/** Pure limit policy: it neither owns keys nor mutates a session. */
internal object ProductionSecureSessionCapacityPolicy {
    fun application(
        snapshot: ProductionSecureSessionCounterSnapshot,
        byteCount: ULong,
    ): ProductionSecureSessionCapacityDecision {
        validate(snapshot)
        val nextEpochRecords = checkedAdd(snapshot.epochRecords, 1uL)
        val nextEpochBytes = checkedAdd(snapshot.epochPlaintextBytes, byteCount)
        val nextSessionRecords = checkedAdd(snapshot.sessionRecords, 1uL)
        val nextSessionBytes = checkedAdd(snapshot.sessionPlaintextBytes, byteCount)
        cryptoRequire(
            nextSessionRecords <= ProductionSecureSessionCryptoContract.MAXIMUM_SESSION_RECORDS &&
                nextSessionBytes <= ProductionSecureSessionCryptoContract.MAXIMUM_SESSION_PLAINTEXT_BYTES,
            ProductionSecureSessionCryptoError.LIMIT_EXCEEDED,
        )
        if (snapshot.epoch < ProductionSecureSessionCryptoContract.MAXIMUM_EPOCH) {
            cryptoRequire(
                nextEpochRecords <= ProductionSecureSessionCryptoContract.MAXIMUM_EPOCH_RECORDS - 1uL &&
                    nextEpochBytes <= ProductionSecureSessionCryptoContract.MAXIMUM_EPOCH_PLAINTEXT_BYTES -
                    UInt.SIZE_BYTES.toULong(),
                ProductionSecureSessionCryptoError.KEY_UPDATE_REQUIRED,
            )
            return ProductionSecureSessionCapacityDecision(
                keyUpdateRequired =
                    nextEpochRecords == ProductionSecureSessionCryptoContract.MAXIMUM_EPOCH_RECORDS - 1uL ||
                        nextEpochBytes == ProductionSecureSessionCryptoContract.MAXIMUM_EPOCH_PLAINTEXT_BYTES -
                        UInt.SIZE_BYTES.toULong(),
                terminalAfterRecord =
                    nextSessionRecords == ProductionSecureSessionCryptoContract.MAXIMUM_SESSION_RECORDS ||
                        nextSessionBytes == ProductionSecureSessionCryptoContract.MAXIMUM_SESSION_PLAINTEXT_BYTES,
            )
        }
        cryptoRequire(
            nextEpochRecords <= ProductionSecureSessionCryptoContract.MAXIMUM_EPOCH_RECORDS &&
                nextEpochBytes <= ProductionSecureSessionCryptoContract.MAXIMUM_EPOCH_PLAINTEXT_BYTES,
            ProductionSecureSessionCryptoError.LIMIT_EXCEEDED,
        )
        return ProductionSecureSessionCapacityDecision(
            keyUpdateRequired = false,
            terminalAfterRecord =
                nextEpochRecords == ProductionSecureSessionCryptoContract.MAXIMUM_EPOCH_RECORDS ||
                    nextEpochBytes == ProductionSecureSessionCryptoContract.MAXIMUM_EPOCH_PLAINTEXT_BYTES ||
                    nextSessionRecords == ProductionSecureSessionCryptoContract.MAXIMUM_SESSION_RECORDS ||
                    nextSessionBytes == ProductionSecureSessionCryptoContract.MAXIMUM_SESSION_PLAINTEXT_BYTES,
        )
    }

    fun keyUpdate(snapshot: ProductionSecureSessionCounterSnapshot): UInt {
        return keyUpdateDecision(snapshot).nextEpoch
    }

    fun keyUpdateDecision(
        snapshot: ProductionSecureSessionCounterSnapshot,
    ): ProductionSecureSessionKeyUpdateCapacityDecision {
        validate(snapshot)
        cryptoRequire(
            snapshot.epoch < ProductionSecureSessionCryptoContract.MAXIMUM_EPOCH,
            ProductionSecureSessionCryptoError.LIMIT_EXCEEDED,
        )
        cryptoRequire(
            checkedAdd(snapshot.epochRecords, 1uL) <=
                ProductionSecureSessionCryptoContract.MAXIMUM_EPOCH_RECORDS &&
                checkedAdd(snapshot.epochPlaintextBytes, UInt.SIZE_BYTES.toULong()) <=
                ProductionSecureSessionCryptoContract.MAXIMUM_EPOCH_PLAINTEXT_BYTES &&
                checkedAdd(snapshot.sessionRecords, 1uL) <=
                ProductionSecureSessionCryptoContract.MAXIMUM_SESSION_RECORDS &&
                checkedAdd(snapshot.sessionPlaintextBytes, UInt.SIZE_BYTES.toULong()) <=
                ProductionSecureSessionCryptoContract.MAXIMUM_SESSION_PLAINTEXT_BYTES,
            ProductionSecureSessionCryptoError.LIMIT_EXCEEDED,
        )
        return ProductionSecureSessionKeyUpdateCapacityDecision(
            nextEpoch = snapshot.epoch + 1u,
            terminalAfterRecord =
                checkedAdd(snapshot.sessionRecords, 1uL) ==
                ProductionSecureSessionCryptoContract.MAXIMUM_SESSION_RECORDS ||
                    checkedAdd(snapshot.sessionPlaintextBytes, UInt.SIZE_BYTES.toULong()) ==
                    ProductionSecureSessionCryptoContract.MAXIMUM_SESSION_PLAINTEXT_BYTES,
        )
    }

    private fun validate(snapshot: ProductionSecureSessionCounterSnapshot) {
        cryptoRequire(
            snapshot.epoch <= ProductionSecureSessionCryptoContract.MAXIMUM_EPOCH &&
                snapshot.epochRecords <= ProductionSecureSessionCryptoContract.MAXIMUM_EPOCH_RECORDS &&
                snapshot.epochPlaintextBytes <=
                ProductionSecureSessionCryptoContract.MAXIMUM_EPOCH_PLAINTEXT_BYTES &&
                snapshot.sessionRecords <= ProductionSecureSessionCryptoContract.MAXIMUM_SESSION_RECORDS &&
                snapshot.sessionPlaintextBytes <=
                ProductionSecureSessionCryptoContract.MAXIMUM_SESSION_PLAINTEXT_BYTES,
            ProductionSecureSessionCryptoError.INVALID_VALUE,
        )
    }
}

internal class ProductionSecureSessionHandshake(
    private val binding: VerifiedProductionC1CandidateP2PKeyScheduleBinding,
    bindingDigest: ByteArray,
    clientConfirmationKey: ByteArray,
    runtimeConfirmationKey: ByteArray,
    clientEpochZeroSecret: ByteArray,
    runtimeEpochZeroSecret: ByteArray,
    nowMs: ULong,
    private val algorithms: ProductionSecureSessionJcaAlgorithms,
) : AutoCloseable {
    private val bindingDigestBytes = bindingDigest.copyOf()
    private val clientConfirmationKeyBytes = clientConfirmationKey.copyOf()
    private val runtimeConfirmationKeyBytes = runtimeConfirmationKey.copyOf()
    private val clientEpochZeroSecretBytes = clientEpochZeroSecret.copyOf()
    private val runtimeEpochZeroSecretBytes = runtimeEpochZeroSecret.copyOf()
    private var lastNowMs = nowMs
    private var localConfirmationSent: ByteArray? = null
    private var peerConfirmationAccepted: ByteArray? = null
    private var cipherIssued = false
    private var terminal = false
    private var closed = false

    @Synchronized
    fun localConfirmation(nowMs: ULong): ByteArray {
        requireUsable(nowMs)
        return expectedConfirmation(binding.localRole)
    }

    @Synchronized
    fun markLocalConfirmationSent(encodedConfirmation: ByteArray, nowMs: ULong) {
        requireUsable(nowMs)
        localConfirmationSent?.let {
            if (!MessageDigest.isEqual(it, encodedConfirmation)) {
                failTerminal(ProductionSecureSessionCryptoError.CONFIRMATION_CONFLICT)
            }
            return
        }
        val expected = expectedConfirmation(binding.localRole)
        if (!MessageDigest.isEqual(expected, encodedConfirmation)) {
            failTerminal(ProductionSecureSessionCryptoError.AUTHENTICATION_FAILED)
        }
        localConfirmationSent = encodedConfirmation.copyOf()
    }

    @Synchronized
    fun acceptPeerConfirmation(encodedConfirmation: ByteArray, nowMs: ULong) {
        requireUsable(nowMs)
        peerConfirmationAccepted?.let {
            if (!MessageDigest.isEqual(it, encodedConfirmation)) {
                failTerminal(ProductionSecureSessionCryptoError.CONFIRMATION_CONFLICT)
            }
            return
        }
        val peerRole = binding.localRole.peer()
        val expected = expectedConfirmation(peerRole)
        if (!MessageDigest.isEqual(expected, encodedConfirmation)) {
            failTerminal(ProductionSecureSessionCryptoError.AUTHENTICATION_FAILED)
        }
        peerConfirmationAccepted = encodedConfirmation.copyOf()
    }

    @Synchronized
    fun activate(nowMs: ULong): ProductionSecureSessionCipher {
        requireUsable(nowMs)
        cryptoRequire(
            localConfirmationSent != null && peerConfirmationAccepted != null,
            ProductionSecureSessionCryptoError.CONFIRMATION_REQUIRED,
        )
        cryptoRequire(!cipherIssued, ProductionSecureSessionCryptoError.ALREADY_USED)
        val cipher = try {
            ProductionSecureSessionCipher(
                binding = binding,
                bindingDigest = bindingDigestBytes,
                clientEpochZeroSecret = clientEpochZeroSecretBytes,
                runtimeEpochZeroSecret = runtimeEpochZeroSecretBytes,
                nowMs = lastNowMs,
                algorithms = algorithms,
            )
        } catch (error: Exception) {
            failTerminal(ProductionSecureSessionCryptoError.CRYPTO_FAILURE)
        }
        cipherIssued = true
        return cipher.also {
            wipeSecrets()
            localConfirmationSent?.wipe()
            localConfirmationSent = null
            peerConfirmationAccepted?.wipe()
            peerConfirmationAccepted = null
        }
    }

    @Synchronized
    fun invalidate() {
        terminal = true
        wipeSecrets()
    }

    @Synchronized
    override fun close() {
        closed = true
        wipeSecrets()
        localConfirmationSent?.wipe()
        localConfirmationSent = null
        peerConfirmationAccepted?.wipe()
        peerConfirmationAccepted = null
    }

    private fun expectedConfirmation(role: P2pNatRole): ByteArray {
        var prefix = ByteArray(0)
        var proofInput = ByteArray(0)
        var proof = ByteArray(0)
        return try {
            val transcriptBytes = ProductionSecureSessionCodec.encode(binding.transcript)
            val authorizationBytes = binding.grantAuthorization.authorization.canonicalBytes()
            val unsigned = ProductionSecureSessionKeyConfirmation(
                suite = ProductionSecureSessionContract.SUITE,
                profile = ProductionSecureSessionContract.PROFILE,
                sessionId = binding.transcript.sessionId,
                object7DigestHex = ProductionC1InternalBridge.digestHex(transcriptBytes),
                object26DigestHex = ProductionC1InternalBridge.digestHex(authorizationBytes),
                confirmingRole = role,
                epoch = 0u,
                proof = ByteArray(SHA256_BYTES),
            )
            prefix = ProductionSecureSessionCryptoCodec.confirmationPrefix(unsigned)
            proofInput = ProductionC1InternalBridge.transcript(CONFIRMATION_DOMAIN, prefix)
            val key = if (role == P2pNatRole.CLIENT) {
                clientConfirmationKeyBytes
            } else {
                runtimeConfirmationKeyBytes
            }
            proof = cryptoHmac(algorithms.confirmationMac, key, proofInput)
            ProductionSecureSessionCryptoCodec.encode(
                ProductionSecureSessionKeyConfirmation(
                    suite = unsigned.suite,
                    profile = unsigned.profile,
                    sessionId = unsigned.sessionId,
                    object7DigestHex = unsigned.object7DigestHex,
                    object26DigestHex = unsigned.object26DigestHex,
                    confirmingRole = role,
                    epoch = 0u,
                    proof = proof,
                ),
            )
        } catch (error: Exception) {
            failTerminal(ProductionSecureSessionCryptoError.CRYPTO_FAILURE, error)
        } finally {
            proof.wipe()
            proofInput.wipe()
            prefix.wipe()
        }
    }

    private fun requireUsable(nowMs: ULong) {
        cryptoRequire(!closed, ProductionSecureSessionCryptoError.CLOSED)
        cryptoRequire(!terminal, ProductionSecureSessionCryptoError.TERMINAL)
        cryptoRequire(!cipherIssued, ProductionSecureSessionCryptoError.ALREADY_USED)
        if (nowMs < lastNowMs) failTerminal(ProductionSecureSessionCryptoError.CLOCK_REGRESSION)
        if (nowMs >= binding.grantAuthorization.authorization.expiresAtMs) {
            failTerminal(ProductionSecureSessionCryptoError.EXPIRED)
        }
        lastNowMs = nowMs
    }

    private fun failTerminal(
        reason: ProductionSecureSessionCryptoError,
        cause: Throwable? = null,
    ): Nothing {
        terminal = true
        wipeSecrets()
        cryptoFail(reason, cause)
    }

    private fun wipeSecrets() {
        bindingDigestBytes.wipe()
        clientConfirmationKeyBytes.wipe()
        runtimeConfirmationKeyBytes.wipe()
        clientEpochZeroSecretBytes.wipe()
        runtimeEpochZeroSecretBytes.wipe()
    }
}

internal class ProductionSecureSessionCipher(
    private val binding: VerifiedProductionC1CandidateP2PKeyScheduleBinding,
    bindingDigest: ByteArray,
    clientEpochZeroSecret: ByteArray,
    runtimeEpochZeroSecret: ByteArray,
    nowMs: ULong,
    private val algorithms: ProductionSecureSessionJcaAlgorithms,
) : AutoCloseable {
    private val bindingDigestBytes = bindingDigest.copyOf()
    private val send = DirectionState(
        binding.localRole,
        if (binding.localRole == P2pNatRole.CLIENT) clientEpochZeroSecret else runtimeEpochZeroSecret,
        bindingDigestBytes,
        algorithms,
    )
    private val receive = DirectionState(
        binding.localRole.peer(),
        if (binding.localRole == P2pNatRole.CLIENT) runtimeEpochZeroSecret else clientEpochZeroSecret,
        bindingDigestBytes,
        algorithms,
    )
    private var lastNowMs = nowMs
    private var fatal = false
    private var closed = false

    @Synchronized
    fun sealApplication(plaintext: ByteArray, nowMs: ULong): ProductionSecureSessionSealResult {
        requireUsable(nowMs)
        cryptoRequire(
            plaintext.size <= ProductionSecureSessionCryptoContract.MAXIMUM_PLAINTEXT_BYTES,
            ProductionSecureSessionCryptoError.LIMIT_EXCEEDED,
        )
        val prospective = send.requireApplicationCapacity(plaintext.size.toULong())
        val encoded = sealRecord(plaintext, ProductionSecureSessionRecordContentType.APPLICATION)
        send.commitApplication(plaintext.size.toULong(), prospective)
        return ProductionSecureSessionSealResult(
            encoded,
            prospective.keyUpdateRequired,
            prospective.terminalAfterRecord,
        )
    }

    @Synchronized
    fun sealKeyUpdate(nowMs: ULong): ProductionSecureSessionSealResult {
        requireUsable(nowMs)
        val capacity = send.requireKeyUpdateCapacity()
        val plaintext = capacity.nextEpoch.toUInt32Bytes()
        val nextSecret = try {
            send.nextEpochSecret(capacity.nextEpoch)
        } catch (error: Exception) {
            plaintext.wipe()
            failTerminal(ProductionSecureSessionCryptoError.CRYPTO_FAILURE)
        }
        var adopted = false
        return try {
            val encoded = sealRecord(plaintext, ProductionSecureSessionRecordContentType.KEY_UPDATE)
            try {
                send.commitKeyUpdate(capacity, nextSecret)
            } catch (error: Exception) {
                failTerminal(ProductionSecureSessionCryptoError.CRYPTO_FAILURE)
            }
            adopted = true
            ProductionSecureSessionSealResult(
                encoded,
                keyUpdateRequired = false,
                terminalAfterRecord = capacity.terminalAfterRecord,
            )
        } finally {
            plaintext.wipe()
            if (!adopted) nextSecret.wipe()
        }
    }

    @Synchronized
    fun open(encodedRecord: ByteArray, nowMs: ULong): ProductionSecureSessionOpenResult {
        requireUsable(nowMs)
        cryptoRequire(!receive.terminal, ProductionSecureSessionCryptoError.TERMINAL)
        val record = ProductionSecureSessionCryptoCodec.decodeRecord(encodedRecord)
        cryptoRequire(record.sessionId == binding.transcript.sessionId, ProductionSecureSessionCryptoError.BINDING_MISMATCH)
        cryptoRequire(record.senderRole == receive.role, ProductionSecureSessionCryptoError.BINDING_MISMATCH)
        cryptoRequire(
            record.epoch == receive.epoch && record.sequence == receive.sequence,
            ProductionSecureSessionCryptoError.OUT_OF_ORDER,
        )
        val prospective = when (record.contentType) {
            ProductionSecureSessionRecordContentType.APPLICATION ->
                receive.requireApplicationCapacity(record.ciphertext.size.toULong())
            ProductionSecureSessionRecordContentType.KEY_UPDATE -> null
        }
        val keyUpdateCapacity = when (record.contentType) {
            ProductionSecureSessionRecordContentType.APPLICATION -> null
            ProductionSecureSessionRecordContentType.KEY_UPDATE -> receive.requireKeyUpdateCapacity()
        }
        val plaintext = openRecord(record)
        return try {
            when (record.contentType) {
                ProductionSecureSessionRecordContentType.APPLICATION -> {
                    val applicationProspective = requireNotNull(prospective)
                    receive.commitApplication(plaintext.size.toULong(), applicationProspective)
                    ProductionSecureSessionOpenResult(
                        plaintext,
                        record.contentType,
                        applicationProspective.keyUpdateRequired,
                        applicationProspective.terminalAfterRecord,
                    )
                }
                ProductionSecureSessionRecordContentType.KEY_UPDATE -> {
                    val capacity = requireNotNull(keyUpdateCapacity)
                    cryptoRequire(plaintext.size == UInt.SIZE_BYTES, ProductionSecureSessionCryptoError.INVALID_VALUE)
                    val nextEpoch = ByteBuffer.wrap(plaintext).order(ByteOrder.BIG_ENDIAN).int.toUInt()
                    cryptoRequire(nextEpoch == capacity.nextEpoch, ProductionSecureSessionCryptoError.OUT_OF_ORDER)
                    val nextSecret = try {
                        receive.nextEpochSecret(nextEpoch)
                    } catch (error: Exception) {
                        failTerminal(ProductionSecureSessionCryptoError.CRYPTO_FAILURE)
                    }
                    try {
                        receive.commitKeyUpdate(capacity, nextSecret)
                    } catch (error: Exception) {
                        failTerminal(ProductionSecureSessionCryptoError.CRYPTO_FAILURE)
                    }
                    ProductionSecureSessionOpenResult(
                        plaintext,
                        record.contentType,
                        keyUpdateRequired = false,
                        terminalAfterRecord = capacity.terminalAfterRecord,
                    )
                }
            }
        } catch (error: Exception) {
            plaintext.wipe()
            throw error
        }
    }

    @Synchronized
    fun invalidate() {
        fatal = true
        wipeSecrets()
    }

    @Synchronized
    override fun close() {
        closed = true
        wipeSecrets()
    }

    private fun sealRecord(
        plaintext: ByteArray,
        contentType: ProductionSecureSessionRecordContentType,
    ): ByteArray {
        val skeleton = ProductionSecureSessionEncryptedRecord(
            sessionId = binding.transcript.sessionId,
            senderRole = send.role,
            epoch = send.epoch,
            sequence = send.sequence,
            contentType = contentType,
            ciphertext = ByteArray(0),
            tag = ByteArray(GCM_TAG_BYTES),
        )
        val prefix = ProductionSecureSessionCryptoCodec.recordPrefix(skeleton)
        val aad = recordAad(bindingDigestBytes, prefix, plaintext.size)
        return try {
            val sealed = crypt(Cipher.ENCRYPT_MODE, plaintext, send, aad)
            val record = ProductionSecureSessionEncryptedRecord(
                sessionId = skeleton.sessionId,
                senderRole = skeleton.senderRole,
                epoch = skeleton.epoch,
                sequence = skeleton.sequence,
                contentType = skeleton.contentType,
                ciphertext = sealed.copyOfRange(0, sealed.size - GCM_TAG_BYTES),
                tag = sealed.copyOfRange(sealed.size - GCM_TAG_BYTES, sealed.size),
            )
            sealed.wipe()
            ProductionSecureSessionCryptoCodec.encode(record)
        } catch (error: Exception) {
            fatal = true
            wipeSecrets()
            throw ProductionSecureSessionCryptoException(
                ProductionSecureSessionCryptoError.CRYPTO_FAILURE,
                error,
            )
        } finally {
            prefix.wipe()
            aad.wipe()
        }
    }

    private fun openRecord(record: ProductionSecureSessionEncryptedRecord): ByteArray {
        val prefix = ProductionSecureSessionCryptoCodec.recordPrefix(record)
        val aad = recordAad(bindingDigestBytes, prefix, record.ciphertext.size)
        val sealed = record.ciphertext + record.tag
        return try {
            crypt(Cipher.DECRYPT_MODE, sealed, receive, aad)
        } catch (error: AEADBadTagException) {
            cryptoFail(ProductionSecureSessionCryptoError.AUTHENTICATION_FAILED, error)
        } catch (error: Exception) {
            failTerminal(ProductionSecureSessionCryptoError.CRYPTO_FAILURE, error)
        } finally {
            sealed.wipe()
            prefix.wipe()
            aad.wipe()
        }
    }

    private fun crypt(
        mode: Int,
        input: ByteArray,
        state: DirectionState,
        aad: ByteArray,
    ): ByteArray {
        val trafficKey = state.trafficKey()
        val nonce = state.nonce()
        return try {
            val cipher = Cipher.getInstance(algorithms.cipher)
            cipher.init(
                mode,
                SecretKeySpec(trafficKey, "AES"),
                GCMParameterSpec(GCM_TAG_BITS, nonce),
            )
            cipher.updateAAD(aad)
            cipher.doFinal(input)
        } finally {
            trafficKey.wipe()
            nonce.wipe()
        }
    }

    private fun requireUsable(nowMs: ULong) {
        cryptoRequire(!closed, ProductionSecureSessionCryptoError.CLOSED)
        cryptoRequire(!fatal, ProductionSecureSessionCryptoError.TERMINAL)
        if (nowMs < lastNowMs) failTerminal(ProductionSecureSessionCryptoError.CLOCK_REGRESSION)
        if (nowMs >= binding.grantAuthorization.authorization.expiresAtMs) {
            failTerminal(ProductionSecureSessionCryptoError.EXPIRED)
        }
        lastNowMs = nowMs
    }

    private fun failTerminal(
        reason: ProductionSecureSessionCryptoError,
        cause: Throwable? = null,
    ): Nothing {
        fatal = true
        wipeSecrets()
        cryptoFail(reason, cause)
    }

    private fun wipeSecrets() {
        bindingDigestBytes.wipe()
        send.wipe()
        receive.wipe()
    }
}

private class DirectionState(
    val role: P2pNatRole,
    epochZeroSecret: ByteArray,
    private val bindingDigest: ByteArray,
    private val algorithms: ProductionSecureSessionJcaAlgorithms,
) {
    private var epochSecret = epochZeroSecret.copyOf()
    private var key = deriveTrafficMaterial(TRAFFIC_KEY_DOMAIN, 32)
    private var iv = deriveTrafficMaterial(TRAFFIC_IV_DOMAIN, GCM_IV_BYTES)
    var epoch: UInt = 0u
        private set
    var sequence: ULong = 0uL
        private set
    var epochRecords: ULong = 0uL
        private set
    var epochPlaintextBytes: ULong = 0uL
        private set
    var sessionRecords: ULong = 0uL
        private set
    var sessionPlaintextBytes: ULong = 0uL
        private set
    var terminal: Boolean = false
        private set

    fun trafficKey(): ByteArray = key.copyOf()

    fun nonce(): ByteArray {
        cryptoRequire(sequence < ProductionSecureSessionCryptoContract.MAXIMUM_EPOCH_RECORDS, ProductionSecureSessionCryptoError.LIMIT_EXCEEDED)
        val result = iv.copyOf()
        val sequenceBytes = sequence.toUInt64Bytes()
        for (index in sequenceBytes.indices) {
            result[index + 4] = (result[index + 4].toInt() xor sequenceBytes[index].toInt()).toByte()
        }
        sequenceBytes.wipe()
        return result
    }

    fun requireApplicationCapacity(byteCount: ULong): ProductionSecureSessionCapacityDecision {
        cryptoRequire(!terminal, ProductionSecureSessionCryptoError.TERMINAL)
        return ProductionSecureSessionCapacityPolicy.application(snapshot(), byteCount)
    }

    fun commitApplication(
        byteCount: ULong,
        capacity: ProductionSecureSessionCapacityDecision,
    ) {
        epochRecords += 1uL
        epochPlaintextBytes += byteCount
        sessionRecords += 1uL
        sessionPlaintextBytes += byteCount
        sequence += 1uL
        if (capacity.terminalAfterRecord) {
            terminal = true
            wipeTrafficOnly()
        }
    }

    fun requireKeyUpdateCapacity(): ProductionSecureSessionKeyUpdateCapacityDecision {
        cryptoRequire(!terminal, ProductionSecureSessionCryptoError.TERMINAL)
        return ProductionSecureSessionCapacityPolicy.keyUpdateDecision(snapshot())
    }

    fun nextEpochSecret(nextEpoch: UInt): ByteArray {
        cryptoRequire(nextEpoch == epoch + 1u, ProductionSecureSessionCryptoError.OUT_OF_ORDER)
        return hkdfExpand(
            algorithms.mac,
            epochSecret,
            ProductionC1InternalBridge.transcript(
                TRAFFIC_UPDATE_DOMAIN,
                epochContext(bindingDigest, role, nextEpoch),
            ),
            SHA256_BYTES,
        )
    }

    fun commitKeyUpdate(
        capacity: ProductionSecureSessionKeyUpdateCapacityDecision,
        nextSecret: ByteArray,
    ) {
        cryptoRequire(capacity.nextEpoch == epoch + 1u, ProductionSecureSessionCryptoError.OUT_OF_ORDER)
        cryptoRequire(nextSecret.size == SHA256_BYTES, ProductionSecureSessionCryptoError.INVALID_VALUE)
        sessionRecords += 1uL
        sessionPlaintextBytes += UInt.SIZE_BYTES.toULong()
        wipeTrafficOnly()
        epochSecret = nextSecret.copyOf()
        nextSecret.wipe()
        epoch = capacity.nextEpoch
        sequence = 0uL
        epochRecords = 0uL
        epochPlaintextBytes = 0uL
        key = deriveTrafficMaterial(TRAFFIC_KEY_DOMAIN, 32)
        iv = deriveTrafficMaterial(TRAFFIC_IV_DOMAIN, GCM_IV_BYTES)
        if (capacity.terminalAfterRecord) {
            terminal = true
            wipeTrafficOnly()
        }
    }

    fun wipe() {
        terminal = true
        wipeTrafficOnly()
    }

    private fun wipeTrafficOnly() {
        epochSecret.wipe()
        key.wipe()
        iv.wipe()
    }

    private fun deriveTrafficMaterial(domain: String, byteCount: Int): ByteArray = hkdfExpand(
        algorithms.mac,
        epochSecret,
        ProductionC1InternalBridge.transcript(domain, epochContext(bindingDigest, role, epoch)),
        byteCount,
    )

    private fun snapshot(): ProductionSecureSessionCounterSnapshot =
        ProductionSecureSessionCounterSnapshot(
            epoch,
            epochRecords,
            epochPlaintextBytes,
            sessionRecords,
            sessionPlaintextBytes,
        )
}

private const val BINDING_DOMAIN = "AetherLink production secure-session object7+object26 binding v1"
private const val ROOT_DOMAIN = "AetherLink production secure-session HKDF root v1"
private const val TRAFFIC_KEY_DOMAIN = "AetherLink production secure-session traffic key v1"
private const val TRAFFIC_IV_DOMAIN = "AetherLink production secure-session traffic iv v1"
private const val TRAFFIC_UPDATE_DOMAIN = "AetherLink production secure-session traffic update v1"
private const val CONFIRMATION_DOMAIN = "AetherLink production secure-session key confirmation v1"
private const val RECORD_AAD_DOMAIN = "AetherLink production secure-session record AAD v1"
private const val SHA256_BYTES = 32
private const val ROOT_OUTPUT_BYTES = 128
private const val P256_SHARED_SECRET_BYTES = 32
private const val GCM_IV_BYTES = 12
private const val GCM_TAG_BITS = 128
private const val GCM_TAG_BYTES = 16

private val TERMINAL_ENGINE_ERRORS = setOf(
    ProductionSecureSessionCryptoError.EXPIRED,
    ProductionSecureSessionCryptoError.CLOCK_REGRESSION,
    ProductionSecureSessionCryptoError.CONFIRMATION_CONFLICT,
    ProductionSecureSessionCryptoError.CRYPTO_FAILURE,
    ProductionSecureSessionCryptoError.TERMINAL,
    ProductionSecureSessionCryptoError.CLOSED,
)

private fun recordAad(bindingDigest: ByteArray, prefix: ByteArray, ciphertextByteCount: Int): ByteArray =
    ProductionC1InternalBridge.transcript(
        RECORD_AAD_DOMAIN,
        bindingDigest + prefix.size.toUInt32Bytes() + prefix + ciphertextByteCount.toUInt32Bytes(),
    )

private fun epochContext(bindingDigest: ByteArray, role: P2pNatRole, epoch: UInt): ByteArray =
    bindingDigest + byteArrayOf(role.cryptoRoleByte()) + epoch.toUInt32Bytes()

private fun P2pNatRole.cryptoRoleByte(): Byte = when (this) {
    P2pNatRole.CLIENT -> 1
    P2pNatRole.RUNTIME -> 2
}

private fun cryptoRole(value: Int): P2pNatRole = when (value) {
    1 -> P2pNatRole.CLIENT
    2 -> P2pNatRole.RUNTIME
    else -> cryptoFail(ProductionSecureSessionCryptoError.INVALID_VALUE)
}

private fun P2pNatRole.peer(): P2pNatRole = when (this) {
    P2pNatRole.CLIENT -> P2pNatRole.RUNTIME
    P2pNatRole.RUNTIME -> P2pNatRole.CLIENT
}

private fun sha256(value: ByteArray): ByteArray = MessageDigest.getInstance("SHA-256").digest(value)

private fun cryptoHmac(algorithm: String, key: ByteArray, value: ByteArray): ByteArray = try {
    Mac.getInstance(algorithm).run {
        init(SecretKeySpec(key, algorithm))
        doFinal(value)
    }
} catch (error: Exception) {
    throw ProductionSecureSessionCryptoException(ProductionSecureSessionCryptoError.CRYPTO_FAILURE, error)
}

private fun hkdfExpand(
    macAlgorithm: String,
    prk: ByteArray,
    info: ByteArray,
    outputByteCount: Int,
): ByteArray {
    cryptoRequire(
        outputByteCount in 1..(255 * SHA256_BYTES),
        ProductionSecureSessionCryptoError.INVALID_VALUE,
    )
    val output = ByteArray(outputByteCount)
    var previous = ByteArray(0)
    var offset = 0
    var blockIndex = 1
    try {
        while (offset < outputByteCount) {
            val next = cryptoHmac(
                macAlgorithm,
                prk,
                previous + info + byteArrayOf(blockIndex.toByte()),
            )
            previous.wipe()
            previous = next
            val count = minOf(previous.size, outputByteCount - offset)
            previous.copyInto(output, destinationOffset = offset, endIndex = count)
            offset += count
            blockIndex += 1
        }
        return output
    } finally {
        previous.wipe()
    }
}

private fun checkedAdd(left: ULong, right: ULong): ULong {
    cryptoRequire(left <= ULong.MAX_VALUE - right, ProductionSecureSessionCryptoError.LIMIT_EXCEEDED)
    return left + right
}

private fun Int.toUInt32Bytes(): ByteArray = toUInt().toUInt32Bytes()

private fun UInt.toUInt32Bytes(): ByteArray =
    ByteBuffer.allocate(UInt.SIZE_BYTES).order(ByteOrder.BIG_ENDIAN).putInt(toInt()).array()

private fun ULong.toUInt64Bytes(): ByteArray =
    ByteBuffer.allocate(ULong.SIZE_BYTES).order(ByteOrder.BIG_ENDIAN).putLong(toLong()).array()

private fun String.isLowerHex(length: Int): Boolean =
    this.length == length && all { it in '0'..'9' || it in 'a'..'f' }

private fun ByteArray.wipe() {
    fill(0)
}

private fun cryptoRequire(condition: Boolean, reason: ProductionSecureSessionCryptoError) {
    if (!condition) cryptoFail(reason)
}

private fun cryptoFail(
    reason: ProductionSecureSessionCryptoError,
    cause: Throwable? = null,
): Nothing = throw ProductionSecureSessionCryptoException(reason, cause)
