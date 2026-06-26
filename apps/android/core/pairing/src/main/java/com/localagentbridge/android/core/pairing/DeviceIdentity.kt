package com.localagentbridge.android.core.pairing

import android.util.Base64
import java.security.KeyPair
import java.security.KeyPairGenerator
import java.security.KeyFactory
import java.security.MessageDigest
import java.security.SecureRandom
import java.security.Signature
import java.security.spec.ECGenParameterSpec
import java.security.spec.X509EncodedKeySpec
import java.util.UUID

data class DeviceIdentity(
    val deviceId: String,
    val deviceName: String,
    val publicKeyBase64: String,
    private val keyPair: KeyPair,
) {
    fun sign(nonce: ByteArray): String {
        val signature = Signature.getInstance("SHA256withECDSA")
        signature.initSign(keyPair.private)
        signature.update(nonce)
        return Base64.encodeToString(signature.sign(), Base64.NO_WRAP)
    }
}

object DeviceIdentityFactory {
    fun create(deviceName: String): DeviceIdentity {
        val keyPairGenerator = KeyPairGenerator.getInstance("EC")
        keyPairGenerator.initialize(ECGenParameterSpec("secp256r1"), SecureRandom())
        val keyPair = keyPairGenerator.generateKeyPair()
        val publicKey = Base64.encodeToString(keyPair.public.encoded, Base64.NO_WRAP)
        return DeviceIdentity(
            deviceId = UUID.randomUUID().toString(),
            deviceName = deviceName,
            publicKeyBase64 = publicKey,
            keyPair = keyPair,
        )
    }
}

object RuntimeIdentityProofVerifier {
    fun verifyChallenge(
        runtimePublicKeyBase64: String,
        expectedFingerprint: String?,
        deviceId: String,
        nonce: String,
        signatureBase64: String,
    ): Boolean {
        return runCatching {
            val publicKeyBytes = java.util.Base64.getDecoder().decode(runtimePublicKeyBase64)
            val expected = expectedFingerprint?.takeIf { it.isNotBlank() }
            if (expected != null && !fingerprint(publicKeyBytes).equals(expected, ignoreCase = true)) {
                return false
            }
            val publicKey = KeyFactory.getInstance("EC")
                .generatePublic(X509EncodedKeySpec(publicKeyBytes))
            val verifier = Signature.getInstance("SHA256withECDSA")
            verifier.initVerify(publicKey)
            verifier.update(authenticationChallengeMessage(deviceId, nonce))
            verifier.verify(java.util.Base64.getDecoder().decode(signatureBase64))
        }.getOrDefault(false)
    }

    fun authenticationChallengeMessage(deviceId: String, nonce: String): ByteArray {
        return "$AUTHENTICATION_CHALLENGE_CONTEXT\n$deviceId\n$nonce".toByteArray(Charsets.UTF_8)
    }

    private fun fingerprint(publicKeyBytes: ByteArray): String {
        return MessageDigest.getInstance("SHA-256")
            .digest(publicKeyBytes)
            .joinToString("") { "%02x".format(it) }
    }

    private const val AUTHENTICATION_CHALLENGE_CONTEXT = "AetherLink runtime auth challenge v1"
}

data class TrustedRuntime(
    val deviceId: String,
    val name: String,
    val fingerprint: String,
    val publicKeyBase64: String? = null,
    val routeToken: String? = null,
    val host: String? = null,
    val port: Int? = null,
    val relayHost: String? = null,
    val relayPort: Int? = null,
    val relayId: String? = null,
    val relaySecret: String? = null,
    val relayExpiresAtEpochMillis: Long? = null,
    val relayNonce: String? = null,
    val relayScope: String? = null,
)
