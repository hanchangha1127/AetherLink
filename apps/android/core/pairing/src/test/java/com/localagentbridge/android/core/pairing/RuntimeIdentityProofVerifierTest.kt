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
}
