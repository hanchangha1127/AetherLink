package com.localagentbridge.android.core.pairing

import org.junit.Assert.assertFalse
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.security.KeyPairGenerator
import java.security.MessageDigest
import java.security.Signature
import java.security.spec.ECGenParameterSpec
import java.util.Base64

class RuntimeIdentityProofVerifierTest {
    private val transportBinding = "0123456789abcdef".repeat(4)

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

    @Test
    fun v1AuthenticationMessagesRemainExactWhenTransportBindingIsAbsent() {
        assertEquals(
            "AetherLink client auth response v1\nandroid-1\nnonce-1",
            DeviceIdentity.authenticationResponseMessage("android-1", "nonce-1").toString(Charsets.UTF_8),
        )
        assertEquals(
            "AetherLink runtime auth challenge v1\nandroid-1\nnonce-1",
            RuntimeIdentityProofVerifier.authenticationChallengeMessage("android-1", "nonce-1")
                .toString(Charsets.UTF_8),
        )
    }

    @Test
    fun signsAndVerifiesV2AuthenticationMessagesWithCanonicalTransportBinding() {
        val identity = DeviceIdentityFactory.create(deviceName = "AetherLink Test Device")
        val clientSignature = identity.signAuthenticationResponse("nonce-1", transportBinding)

        assertEquals(
            "AetherLink client auth response v2\n${identity.deviceId}\nnonce-1\n$transportBinding",
            DeviceIdentity.authenticationResponseMessage(identity.deviceId, "nonce-1", transportBinding)
                .toString(Charsets.UTF_8),
        )
        assertTrue(
            verifyRawSignature(
                publicKeyBase64 = identity.publicKeyBase64,
                message = DeviceIdentity.authenticationResponseMessage(identity.deviceId, "nonce-1", transportBinding),
                signatureBase64 = clientSignature,
            )
        )

        val runtimeKeyPair = KeyPairGenerator.getInstance("EC").apply {
            initialize(ECGenParameterSpec("secp256r1"))
        }.generateKeyPair()
        val runtimePublicKeyBase64 = Base64.getEncoder().encodeToString(runtimeKeyPair.public.encoded)
        val runtimeSignature = Signature.getInstance("SHA256withECDSA").run {
            initSign(runtimeKeyPair.private)
            update(RuntimeIdentityProofVerifier.authenticationChallengeMessage(identity.deviceId, "nonce-2", transportBinding))
            Base64.getEncoder().encodeToString(sign())
        }

        assertTrue(
            RuntimeIdentityProofVerifier.verifyChallenge(
                runtimePublicKeyBase64 = runtimePublicKeyBase64,
                expectedFingerprint = null,
                deviceId = identity.deviceId,
                nonce = "nonce-2",
                signatureBase64 = runtimeSignature,
                transportBinding = transportBinding,
            )
        )
        assertFalse(
            RuntimeIdentityProofVerifier.verifyChallenge(
                runtimePublicKeyBase64 = runtimePublicKeyBase64,
                expectedFingerprint = null,
                deviceId = identity.deviceId,
                nonce = "nonce-2",
                signatureBase64 = runtimeSignature,
                transportBinding = "f".repeat(64),
            )
        )
        assertFalse(
            RuntimeIdentityProofVerifier.verifyChallenge(
                runtimePublicKeyBase64 = runtimePublicKeyBase64,
                expectedFingerprint = null,
                deviceId = identity.deviceId,
                nonce = "nonce-2",
                signatureBase64 = runtimeSignature,
            )
        )
    }

    @Test
    fun rejectsNonCanonicalTransportBindingsBeforeSigningOrVerification() {
        val identity = DeviceIdentityFactory.create(deviceName = "AetherLink Test Device")
        val invalidBindings = listOf(
            "A".repeat(64),
            "0".repeat(63),
            "0".repeat(65),
            "0".repeat(63) + "g",
            "0".repeat(63) + "\n",
            "0".repeat(64) + "\n",
            "\uFF10".repeat(64),
        )

        invalidBindings.forEach { invalidBinding ->
            assertThrows(IllegalArgumentException::class.java) {
                identity.signAuthenticationResponse("nonce-1", invalidBinding)
            }
            assertThrows(IllegalArgumentException::class.java) {
                RuntimeIdentityProofVerifier.authenticationChallengeMessage(
                    deviceId = identity.deviceId,
                    nonce = "nonce-1",
                    transportBinding = invalidBinding,
                )
            }
            assertFalse(
                RuntimeIdentityProofVerifier.verifyChallenge(
                    runtimePublicKeyBase64 = identity.publicKeyBase64,
                    expectedFingerprint = null,
                    deviceId = identity.deviceId,
                    nonce = "nonce-1",
                    signatureBase64 = "invalid-signature",
                    transportBinding = invalidBinding,
                )
            )
        }
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
