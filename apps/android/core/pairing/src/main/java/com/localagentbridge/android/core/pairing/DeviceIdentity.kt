package com.localagentbridge.android.core.pairing

import com.localagentbridge.android.core.protocol.PairedClientRelayRegistrationAuthorization
import com.localagentbridge.android.core.protocol.PairedClientRelayRegistrationChallenge
import java.security.KeyPair
import java.security.KeyPairGenerator
import java.security.KeyFactory
import java.security.MessageDigest
import java.security.SecureRandom
import java.security.Signature
import java.security.spec.ECGenParameterSpec
import java.security.spec.X509EncodedKeySpec
import java.util.Base64
import java.util.UUID

data class DeviceIdentity(
    val deviceId: String,
    val deviceName: String,
    val publicKeyBase64: String,
    private val keyPair: KeyPair,
) {
    fun signInitialPairingRequest(request: InitialPairingClientRequest): String {
        require(request.clientDeviceId == deviceId) { "client device id does not match identity" }
        require(request.clientDeviceName == deviceName) { "client device name does not match identity" }
        require(request.clientPublicKey == publicKeyBase64) { "client public key does not match identity" }
        InitialPairingProof.requireCanonicalPublicKey(
            publicKeyBase64 = request.clientPublicKey,
            fingerprint = request.clientKeyFingerprint,
        )
        return sign(request.transcript())
    }

    fun signPairedRelayAllocationAuthorization(
        authorization: PairedRelayAllocationAuthorization,
    ): String {
        val encodedIdentityPublicKey = Base64.getDecoder().decode(publicKeyBase64)
        require(keyPair.public.encoded.contentEquals(encodedIdentityPublicKey)) {
            "client identity public key does not match signing key"
        }
        PairedRelayAllocationAuthorizationProof.requireCanonicalPublicKey(
            publicKeyBase64 = publicKeyBase64,
            fingerprint = authorization.clientKeyFingerprint,
        )
        return sign(authorization.clientTranscript())
    }

    fun signPairedClientRelayRegistrationAuthorization(
        challenge: PairedClientRelayRegistrationChallenge,
    ): String {
        challenge.validate()
        val encodedIdentityPublicKey = Base64.getDecoder().decode(publicKeyBase64)
        require(keyPair.public.encoded.contentEquals(encodedIdentityPublicKey)) {
            "client identity public key does not match signing key"
        }
        val actualFingerprint = PairedClientRelayRegistrationAuthorization
            .clientKeyFingerprint(publicKeyBase64)
        require(challenge.clientKeyFingerprint == actualFingerprint) {
            "challenge client key fingerprint does not match identity"
        }
        return sign(challenge.transcript())
    }

    fun signAuthenticationResponse(nonce: String, transportBinding: String? = null): String {
        return sign(authenticationResponseMessage(deviceId, nonce, transportBinding))
    }

    private fun sign(message: ByteArray): String {
        val signature = Signature.getInstance("SHA256withECDSA")
        signature.initSign(keyPair.private)
        signature.update(message)
        return Base64.getEncoder().encodeToString(signature.sign())
    }

    companion object {
        fun authenticationResponseMessage(
            deviceId: String,
            nonce: String,
            transportBinding: String? = null,
        ): ByteArray {
            val message = if (transportBinding == null) {
                "$AUTHENTICATION_RESPONSE_CONTEXT_V1\n$deviceId\n$nonce"
            } else {
                requireCanonicalTransportBinding(transportBinding)
                "$AUTHENTICATION_RESPONSE_CONTEXT_V2\n$deviceId\n$nonce\n$transportBinding"
            }
            return message.toByteArray(Charsets.UTF_8)
        }

        fun isCanonicalTransportBinding(transportBinding: String): Boolean {
            return transportBinding.length == 64 && transportBinding.all { character ->
                character in '0'..'9' || character in 'a'..'f'
            }
        }

        internal fun requireCanonicalTransportBinding(transportBinding: String) {
            require(isCanonicalTransportBinding(transportBinding)) {
                "transport binding must be 64 lowercase ASCII hex characters"
            }
        }

        private const val AUTHENTICATION_RESPONSE_CONTEXT_V1 = "AetherLink client auth response v1"
        private const val AUTHENTICATION_RESPONSE_CONTEXT_V2 = "AetherLink client auth response v2"
    }
}

object DeviceIdentityFactory {
    fun create(deviceName: String): DeviceIdentity {
        val keyPairGenerator = KeyPairGenerator.getInstance("EC")
        keyPairGenerator.initialize(ECGenParameterSpec("secp256r1"), SecureRandom())
        val keyPair = keyPairGenerator.generateKeyPair()
        val publicKey = Base64.getEncoder().encodeToString(keyPair.public.encoded)
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
        transportBinding: String? = null,
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
            verifier.update(authenticationChallengeMessage(deviceId, nonce, transportBinding))
            verifier.verify(java.util.Base64.getDecoder().decode(signatureBase64))
        }.getOrDefault(false)
    }

    fun authenticationChallengeMessage(
        deviceId: String,
        nonce: String,
        transportBinding: String? = null,
    ): ByteArray {
        val message = if (transportBinding == null) {
            "$AUTHENTICATION_CHALLENGE_CONTEXT_V1\n$deviceId\n$nonce"
        } else {
            DeviceIdentity.requireCanonicalTransportBinding(transportBinding)
            "$AUTHENTICATION_CHALLENGE_CONTEXT_V2\n$deviceId\n$nonce\n$transportBinding"
        }
        return message.toByteArray(Charsets.UTF_8)
    }

    private fun fingerprint(publicKeyBytes: ByteArray): String {
        return MessageDigest.getInstance("SHA-256")
            .digest(publicKeyBytes)
            .joinToString("") { "%02x".format(it) }
    }

    private const val AUTHENTICATION_CHALLENGE_CONTEXT_V1 = "AetherLink runtime auth challenge v1"
    private const val AUTHENTICATION_CHALLENGE_CONTEXT_V2 = "AetherLink runtime auth challenge v2"
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
    val relayTicketGeneration: Long? = null,
    val p2pRouteClass: String? = null,
    val p2pRecordId: String? = null,
    val p2pEncryptedBody: String? = null,
    val p2pExpiresAtEpochMillis: Long? = null,
    val p2pAntiReplayNonce: String? = null,
    val p2pProtocolVersion: Int? = null,
)
