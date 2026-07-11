package com.localagentbridge.android.core.pairing

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.math.BigInteger
import java.security.AlgorithmParameters
import java.security.KeyFactory
import java.security.KeyPair
import java.security.MessageDigest
import java.security.Signature
import java.security.spec.ECGenParameterSpec
import java.security.spec.ECParameterSpec
import java.security.spec.ECPrivateKeySpec
import java.security.spec.ECPublicKeySpec
import java.util.Base64

class InitialPairingProofTest {
    @Test
    fun fixedRequestAndResultDigestsMatchContractVectors() {
        val request = fixedRequest()
        val result = fixedResult()

        assertEquals(REQUEST_DIGEST, request.digest())
        assertEquals(RESULT_DIGEST, result.digest())
        assertFalse(request.transcript().toString(Charsets.UTF_8).endsWith("\n"))
        assertFalse(result.transcript().toString(Charsets.UTF_8).endsWith("\n"))
        assertTrue(request.transcript().toString(Charsets.UTF_8).contains("client_device_name\n14\nAndroid Device"))
    }

    @Test
    fun deviceIdentitySignsTypedRequestAndRejectsAnotherIdentity() {
        val identity = DeviceIdentityFactory.create("Android Device")
        val fingerprint = fingerprint(identity.publicKeyBase64)
        val request = fixedRequest().copy(
            clientDeviceId = identity.deviceId,
            clientPublicKey = identity.publicKeyBase64,
            clientKeyFingerprint = fingerprint,
        )

        val signature = identity.signInitialPairingRequest(request)
        assertTrue(verify(identity.publicKeyBase64, request.transcript(), signature))
        assertThrows(IllegalArgumentException::class.java) {
            identity.signInitialPairingRequest(request.copy(clientDeviceId = "replayed-client"))
        }
    }

    @Test
    fun verifiesAcceptedResultAndRejectsWrongKeyTamperingAndReplayDifferences() {
        val result = fixedResult()
        val runtimeKey = scalarKeyPair(BigInteger.ONE)
        val signature = sign(runtimeKey, result.transcript())

        assertTrue(verifyResult(result, signature))
        assertFalse(verifyResult(result.copy(message = "tampered"), signature))
        assertFalse(verifyResult(result.copy(runtimePublicKey = CLIENT_KEY, runtimeKeyFingerprint = CLIENT_FP), signature))
        assertFalse(
            InitialPairingProof.verifyAcceptedResult(
                result, signature, "request-fixed-2", REQUEST_DIGEST, "client-fixed-1", BINDING,
            )
        )
        assertFalse(
            InitialPairingProof.verifyAcceptedResult(
                result, signature, "request-fixed-1", "0".repeat(64), "client-fixed-1", BINDING,
            )
        )
        assertFalse(verifyResult(result.copy(accepted = false), signature))
    }

    @Test
    fun rejectsNonCanonicalPublicKeyFingerprintSignatureBase64AndDer() {
        val result = fixedResult()
        val signature = sign(scalarKeyPair(BigInteger.ONE), result.transcript())

        assertFalse(verifyResult(result.copy(runtimePublicKey = RUNTIME_KEY.trimEnd('=')), signature))
        assertFalse(verifyResult(result.copy(runtimePublicKey = RUNTIME_KEY + "\n"), signature))
        assertFalse(verifyResult(result.copy(runtimeKeyFingerprint = RUNTIME_FP.uppercase()), signature))
        assertFalse(verifyResult(result, signature + "\n"))
        assertFalse(verifyResult(result, makeNonCanonicalDer(signature)))
    }

    @Test
    fun supportsLiteralNoneAndCanonicalBindingButRejectsOtherBindings() {
        assertEquals(
            fixedRequest().copy(transportBinding = null).digest(),
            fixedRequest().copy(transportBinding = "none").digest(),
        )
        assertEquals(REQUEST_DIGEST, fixedRequest().digest())

        listOf("NONE", "f".repeat(63), "F".repeat(64), "g".repeat(64)).forEach { binding ->
            assertThrows(IllegalArgumentException::class.java) {
                fixedRequest().copy(transportBinding = binding).transcript()
            }
        }
    }

    private fun fixedRequest() = InitialPairingClientRequest(
        scheme = INITIAL_PAIRING_PROOF_SCHEME,
        protocolVersion = 1,
        requestId = "request-fixed-1",
        pairingNonce = "nonce-fixed-1",
        pairingCode = "123456",
        runtimeDeviceId = "runtime-fixed-1",
        runtimePublicKey = RUNTIME_KEY,
        runtimeKeyFingerprint = RUNTIME_FP,
        clientDeviceId = "client-fixed-1",
        clientDeviceName = "Android Device",
        clientPublicKey = CLIENT_KEY,
        clientKeyFingerprint = CLIENT_FP,
        transportBinding = BINDING,
    )

    private fun fixedResult() = InitialPairingAcceptedResult(
        scheme = INITIAL_PAIRING_PROOF_SCHEME,
        protocolVersion = 1,
        requestId = "request-fixed-1",
        pairingRequestDigest = REQUEST_DIGEST,
        accepted = true,
        runtimeDeviceId = "runtime-fixed-1",
        runtimePublicKey = RUNTIME_KEY,
        runtimeKeyFingerprint = RUNTIME_FP,
        trustedDeviceId = "client-fixed-1",
        message = "Android Device is now trusted by AetherLink Runtime.",
        transportBinding = BINDING,
    )

    private fun verifyResult(result: InitialPairingAcceptedResult, signature: String) =
        InitialPairingProof.verifyAcceptedResult(
            result = result,
            signatureBase64 = signature,
            expectedRequestId = "request-fixed-1",
            expectedPairingRequestDigest = REQUEST_DIGEST,
            expectedTrustedDeviceId = "client-fixed-1",
            expectedTransportBinding = BINDING,
        )

    private fun scalarKeyPair(scalar: BigInteger): KeyPair {
        val params = AlgorithmParameters.getInstance("EC").run {
            init(ECGenParameterSpec("secp256r1"))
            getParameterSpec(ECParameterSpec::class.java)
        }
        val point = when (scalar) {
            BigInteger.ONE -> params.generator
            else -> throw IllegalArgumentException("unsupported test scalar")
        }
        val factory = KeyFactory.getInstance("EC")
        return KeyPair(
            factory.generatePublic(ECPublicKeySpec(point, params)),
            factory.generatePrivate(ECPrivateKeySpec(scalar, params)),
        )
    }

    private fun sign(keyPair: KeyPair, message: ByteArray): String = Signature.getInstance("SHA256withECDSA").run {
        initSign(keyPair.private)
        update(message)
        Base64.getEncoder().encodeToString(sign())
    }

    private fun verify(publicKeyBase64: String, message: ByteArray, signatureBase64: String): Boolean =
        Signature.getInstance("SHA256withECDSA").run {
            val key = KeyFactory.getInstance("EC").generatePublic(
                java.security.spec.X509EncodedKeySpec(Base64.getDecoder().decode(publicKeyBase64)),
            )
            initVerify(key)
            update(message)
            verify(Base64.getDecoder().decode(signatureBase64))
        }

    private fun fingerprint(publicKeyBase64: String): String = MessageDigest.getInstance("SHA-256")
        .digest(Base64.getDecoder().decode(publicKeyBase64))
        .joinToString("") { "%02x".format(it) }

    private fun makeNonCanonicalDer(signatureBase64: String): String {
        val der = Base64.getDecoder().decode(signatureBase64)
        val firstIntegerLength = der[3].toInt() and 0xff
        val output = ByteArray(der.size + 1)
        output[0] = 0x30
        output[1] = (der[1] + 1).toByte()
        output[2] = 0x02
        output[3] = (firstIntegerLength + 1).toByte()
        output[4] = 0
        der.copyInto(output, 5, 4)
        return Base64.getEncoder().encodeToString(output)
    }

    companion object {
        private const val RUNTIME_KEY = "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEaxfR8uEsQkf4vOblY6RA8ncDfYEt6zOg9KE5RdiYwpZP40Li/hp/m47n60p8D54WK84zV2sxXs7LtkBoN79R9Q=="
        private const val RUNTIME_FP = "5cd252fb0ce8932436faf8ccd1040981b89ee4ad6b9fe9e2a2b7e71aacb27cd3"
        private const val CLIENT_KEY = "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEfPJ7GI0DT36KUjgDBLUaw8CJaeJ38hs1pgtI/EdmmXgHd1UQ247QQCk9msafdDDbun2t5jzpgimeBLedInhz0Q=="
        private const val CLIENT_FP = "dc0ce633dbcc913dafafa4b89ac44d8ce683fdfc3f60c8bdf21213b9f2b534ba"
        private const val BINDING = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        private const val REQUEST_DIGEST = "7ecceffa7e90feeaebdac054b6be386307bc26db9914a9b0d5660f9c671f0965"
        private const val RESULT_DIGEST = "9bf74c2179506f02c8b071f507465e29ec35530608bcdf72f325f23dd419f84f"
    }
}
