package com.localagentbridge.android.core.pairing

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.security.KeyPairGenerator
import java.security.MessageDigest
import java.security.Signature
import java.security.spec.ECGenParameterSpec
import java.util.Base64

class RuntimeIdentityProofVerifierTest {
    @Test
    fun deviceIdentitySignaturesUseJvmCompatibleBase64AndVerifyWithStoredPublicKey() {
        val identity = DeviceIdentityFactory.create(deviceName = "AetherLink Test Device")
        val nonce = "client-auth-nonce"
        val signature = identity.signAuthenticationResponse(nonce)

        assertTrue(signature.isNotBlank())
        assertFalse(
            RuntimeIdentityProofVerifier.verifyChallenge(
                runtimePublicKeyBase64 = identity.publicKeyBase64,
                expectedFingerprint = null,
                deviceId = "device-ignored-for-raw-nonce-signature",
                nonce = nonce,
                signatureBase64 = signature,
            )
        )
        assertTrue(
            verifyRawSignature(
                publicKeyBase64 = identity.publicKeyBase64,
                message = DeviceIdentity.authenticationResponseMessage(identity.deviceId, nonce),
                signatureBase64 = signature,
            )
        )
        assertFalse(
            verifyRawSignature(
                publicKeyBase64 = identity.publicKeyBase64,
                message = nonce.toByteArray(Charsets.UTF_8),
                signatureBase64 = signature,
            )
        )
    }

    @Test
    fun verifiesRuntimeAuthenticationChallengeSignature() {
        val keyPair = KeyPairGenerator.getInstance("EC").apply {
            initialize(ECGenParameterSpec("secp256r1"))
        }.generateKeyPair()
        val publicKeyBase64 = Base64.getEncoder().encodeToString(keyPair.public.encoded)
        val fingerprint = MessageDigest.getInstance("SHA-256")
            .digest(keyPair.public.encoded)
            .joinToString("") { "%02x".format(it) }
        val message = RuntimeIdentityProofVerifier.authenticationChallengeMessage(
            deviceId = "android-1",
            nonce = "nonce-1",
        )
        val signature = Signature.getInstance("SHA256withECDSA").run {
            initSign(keyPair.private)
            update(message)
            Base64.getEncoder().encodeToString(sign())
        }

        assertTrue(
            RuntimeIdentityProofVerifier.verifyChallenge(
                runtimePublicKeyBase64 = publicKeyBase64,
                expectedFingerprint = fingerprint,
                deviceId = "android-1",
                nonce = "nonce-1",
                signatureBase64 = signature,
            )
        )
        assertFalse(
            RuntimeIdentityProofVerifier.verifyChallenge(
                runtimePublicKeyBase64 = publicKeyBase64,
                expectedFingerprint = fingerprint,
                deviceId = "android-2",
                nonce = "nonce-1",
                signatureBase64 = signature,
            )
        )
    }

    private fun verifyRawSignature(
        publicKeyBase64: String,
        message: ByteArray,
        signatureBase64: String,
    ): Boolean {
        val publicKey = java.security.KeyFactory.getInstance("EC")
            .generatePublic(
                java.security.spec.X509EncodedKeySpec(
                    Base64.getDecoder().decode(publicKeyBase64)
                )
            )
        return Signature.getInstance("SHA256withECDSA").run {
            initVerify(publicKey)
            update(message)
            verify(Base64.getDecoder().decode(signatureBase64))
        }
    }
}
