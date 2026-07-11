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
import java.security.KeyPairGenerator
import java.security.MessageDigest
import java.security.SecureRandom
import java.security.Signature
import java.security.spec.ECGenParameterSpec
import java.security.spec.ECParameterSpec
import java.security.spec.ECPrivateKeySpec
import java.security.spec.X509EncodedKeySpec
import java.util.Base64

class PairedRelayAllocationAuthorizationTest {
    @Test
    fun fixedRoleTranscriptsMatchContractDigestsAndFieldOrder() {
        val authorization = fixedAuthorization()

        assertEquals(RUNTIME_DIGEST, authorization.runtimeDigest())
        assertEquals(CLIENT_DIGEST, authorization.clientDigest())
        assertEquals(
            "AetherLink paired relay allocation runtime authorization v2",
            authorization.runtimeTranscript().toString(Charsets.UTF_8).lineSequence().first(),
        )
        assertEquals(
            "AetherLink paired relay allocation client authorization v2",
            authorization.clientTranscript().toString(Charsets.UTF_8).lineSequence().first(),
        )
        assertEquals(
            EXPECTED_FIELD_ORDER,
            authorization.runtimeTranscript()
                .toString(Charsets.UTF_8)
                .split('\n')
                .drop(1)
                .chunked(3)
                .map { it.first() },
        )
        assertFalse(authorization.runtimeTranscript().toString(Charsets.UTF_8).endsWith('\n'))
        assertFalse(authorization.clientTranscript().toString(Charsets.UTF_8).endsWith('\n'))
    }

    @Test
    fun pairScopedRelayIdMatchesSwiftVectorAndBindsAllInputs() {
        val runtimeFingerprint = "a".repeat(64)
        val clientFingerprint = "b".repeat(64)
        val relayId = PairedRelayAllocationAuthorizationProof.pairedRelayId(
            routeToken = "route-token",
            runtimeKeyFingerprint = runtimeFingerprint,
            clientKeyFingerprint = clientFingerprint,
        )

        assertEquals(
            "rt2-31b91c84adca190fc27f6a63fb470a1bf0f1bfea1825cbc7897cc975396cd6bc",
            relayId,
        )
        assertFalse(
            relayId == PairedRelayAllocationAuthorizationProof.pairedRelayId(
                routeToken = "route-token-2",
                runtimeKeyFingerprint = runtimeFingerprint,
                clientKeyFingerprint = clientFingerprint,
            )
        )
    }

    @Test
    fun deterministicRuntimeAndTypedClientProofsVerifyForClaimAndRenew() {
        val runtimeKeyPair = fixedKeyPair(BigInteger.ONE, RUNTIME_PUBLIC_KEY)
        val clientIdentity = fixedClientIdentity()

        listOf("claim", "renew").forEach { operation ->
            val authorization = fixedAuthorization().copy(operation = operation)
            val runtimeSignature = sign(runtimeKeyPair, authorization.runtimeTranscript())
            val clientSignature = clientIdentity.signPairedRelayAllocationAuthorization(authorization)

            assertTrue(
                PairedRelayAllocationAuthorizationProof.verifyRuntime(
                    authorization,
                    RUNTIME_PUBLIC_KEY,
                    runtimeSignature,
                ),
            )
            assertTrue(
                PairedRelayAllocationAuthorizationProof.verifyClient(
                    authorization,
                    CLIENT_PUBLIC_KEY,
                    clientSignature,
                ),
            )
        }
    }

    @Test
    fun wrongKeysAndRoleSwapsAreRejected() {
        val authorization = fixedAuthorization()
        val runtimeSignature = sign(runtimeKeyPair(), authorization.runtimeTranscript())
        val clientSignature = sign(clientKeyPair(), authorization.clientTranscript())

        assertFalse(
            PairedRelayAllocationAuthorizationProof.verifyRuntime(
                authorization,
                RUNTIME_PUBLIC_KEY,
                clientSignature,
            ),
        )
        assertFalse(
            PairedRelayAllocationAuthorizationProof.verifyClient(
                authorization,
                CLIENT_PUBLIC_KEY,
                runtimeSignature,
            ),
        )
        assertFalse(
            PairedRelayAllocationAuthorizationProof.verifyRuntime(
                authorization,
                CLIENT_PUBLIC_KEY,
                runtimeSignature,
            ),
        )

        val sharedRoleKeyAuthorization = authorization.copy(clientKeyFingerprint = RUNTIME_FINGERPRINT)
        val runtimeRoleSignature = sign(runtimeKeyPair(), sharedRoleKeyAuthorization.runtimeTranscript())
        val clientRoleSignature = sign(runtimeKeyPair(), sharedRoleKeyAuthorization.clientTranscript())
        assertFalse(
            PairedRelayAllocationAuthorizationProof.verifyClient(
                sharedRoleKeyAuthorization,
                RUNTIME_PUBLIC_KEY,
                runtimeRoleSignature,
            ),
        )
        assertFalse(
            PairedRelayAllocationAuthorizationProof.verifyRuntime(
                sharedRoleKeyAuthorization,
                RUNTIME_PUBLIC_KEY,
                clientRoleSignature,
            ),
        )
    }

    @Test
    fun signedFieldMutationAndDowngradeAreRejected() {
        val authorization = fixedAuthorization()
        val runtimeSignature = sign(runtimeKeyPair(), authorization.runtimeTranscript())
        val clientSignature = fixedClientIdentity().signPairedRelayAllocationAuthorization(authorization)
        val mutated = authorization.copy(challenge = hex("79"))

        assertFalse(
            PairedRelayAllocationAuthorizationProof.verifyRuntime(
                mutated,
                RUNTIME_PUBLIC_KEY,
                runtimeSignature,
            ),
        )
        assertFalse(
            PairedRelayAllocationAuthorizationProof.verifyClient(
                mutated,
                CLIENT_PUBLIC_KEY,
                clientSignature,
            ),
        )
        assertInvalid(authorization.copy(scheme = "runtime-client-p256-v0"))
        assertInvalid(authorization.copy(protocolVersion = 0))
        assertInvalid(authorization.copy(operation = "allocate"))
        assertInvalid(authorization.copy(operation = "Claim"))
    }

    @Test
    fun typedClientSignerRequiresItsPublicKeyAndFingerprint() {
        val identity = fixedClientIdentity()

        assertThrows(IllegalArgumentException::class.java) {
            identity.signPairedRelayAllocationAuthorization(
                fixedAuthorization().copy(clientKeyFingerprint = RUNTIME_FINGERPRINT),
            )
        }

        val mismatchedIdentity = DeviceIdentity(
            deviceId = "client-fixed-1",
            deviceName = "Android Device",
            publicKeyBase64 = CLIENT_PUBLIC_KEY,
            keyPair = runtimeKeyPair(),
        )
        assertThrows(IllegalArgumentException::class.java) {
            mismatchedIdentity.signPairedRelayAllocationAuthorization(fixedAuthorization())
        }
    }

    @Test
    fun nonCanonicalBase64DerCurveAndHexAreRejected() {
        val authorization = fixedAuthorization()
        val signature = sign(runtimeKeyPair(), authorization.runtimeTranscript())

        assertFalse(
            PairedRelayAllocationAuthorizationProof.verifyRuntime(
                authorization,
                RUNTIME_PUBLIC_KEY + "\n",
                signature,
            ),
        )
        assertFalse(
            PairedRelayAllocationAuthorizationProof.verifyRuntime(
                authorization,
                RUNTIME_PUBLIC_KEY,
                signature + "\n",
            ),
        )
        assertFalse(
            PairedRelayAllocationAuthorizationProof.verifyRuntime(
                authorization,
                RUNTIME_PUBLIC_KEY,
                Base64.getEncoder().encodeToString(ByteArray(64) { 1 }),
            ),
        )
        assertFalse(
            PairedRelayAllocationAuthorizationProof.verifyRuntime(
                authorization,
                RUNTIME_PUBLIC_KEY,
                makeNonCanonicalDer(signature),
            ),
        )

        val p384Key = deterministicP384KeyPair().public.encoded
        assertFalse(
            PairedRelayAllocationAuthorizationProof.verifyRuntime(
                authorization.copy(runtimeKeyFingerprint = fingerprint(p384Key)),
                Base64.getEncoder().encodeToString(p384Key),
                signature,
            ),
        )

        assertInvalid(authorization.copy(routeTokenHash = hex("ab").uppercase()))
        assertInvalid(authorization.copy(runtimeKeyFingerprint = RUNTIME_FINGERPRINT.dropLast(1)))
        assertInvalid(authorization.copy(clientKeyFingerprint = CLIENT_FINGERPRINT.uppercase()))
        assertInvalid(authorization.copy(challenge = hex("gg")))
        assertInvalid(authorization.copy(transportBinding = hex("AB")))
    }

    @Test
    fun idsAndRelayIdMustBeBoundedAndCanonical() {
        val authorization = fixedAuthorization()

        authorization.copy(requestId = "a".repeat(512)).runtimeTranscript()
        authorization.copy(authorizationId = "a".repeat(512)).runtimeTranscript()
        assertInvalid(authorization.copy(requestId = " "))
        assertInvalid(authorization.copy(requestId = "request id"))
        assertInvalid(authorization.copy(requestId = "request\nid"))
        assertInvalid(authorization.copy(requestId = "request\u0000id"))
        assertInvalid(authorization.copy(requestId = "a".repeat(513)))
        assertInvalid(authorization.copy(authorizationId = "한".repeat(171)))
        assertInvalid(authorization.copy(currentRelayId = "rt2-" + hex("AB")))
        assertInvalid(authorization.copy(currentRelayId = "rt2-" + hex("01").dropLast(1)))
        assertInvalid(authorization.copy(nextRelayId = "relay-" + hex("02")))
    }

    @Test
    fun claimRotatesRelayIdAndRenewAllowsEqualOrDifferentIds() {
        val authorization = fixedAuthorization()

        assertInvalid(authorization.copy(nextRelayId = authorization.currentRelayId))
        authorization.copy(operation = "renew").runtimeTranscript()
        authorization.copy(
            operation = "renew",
            nextRelayId = authorization.currentRelayId,
        ).runtimeTranscript()
    }

    @Test
    fun generationsExpiriesAndNoncesMustBePositiveAdvancingAndDistinct() {
        val authorization = fixedAuthorization()

        assertInvalid(authorization.copy(currentTicketGeneration = 0))
        assertInvalid(authorization.copy(nextTicketGeneration = authorization.currentTicketGeneration))
        assertInvalid(authorization.copy(nextTicketGeneration = authorization.currentTicketGeneration + 2))
        assertInvalid(
            authorization.copy(
                currentTicketGeneration = Long.MAX_VALUE,
                nextTicketGeneration = Long.MAX_VALUE,
            ),
        )
        assertInvalid(authorization.copy(currentRelayExpiresAtEpochMillis = 0))
        assertInvalid(
            authorization.copy(
                nextRelayExpiresAtEpochMillis = authorization.currentRelayExpiresAtEpochMillis,
            ),
        )
        assertInvalid(
            authorization.copy(
                nextRelayExpiresAtEpochMillis = authorization.currentRelayExpiresAtEpochMillis - 1,
            ),
        )
        assertInvalid(authorization.copy(challengeExpiresAtEpochMillis = 0))
        assertInvalid(authorization.copy(nextRelayNonce = authorization.currentRelayNonce))
        authorization.copy(currentRelayNonce = "opaque-Nonce_1", nextRelayNonce = "opaque-Nonce_2")
            .runtimeTranscript()
        authorization.copy(currentRelayNonce = "n".repeat(512)).runtimeTranscript()
        assertInvalid(authorization.copy(currentRelayNonce = ""))
        assertInvalid(authorization.copy(currentRelayNonce = "relay nonce"))
        assertInvalid(authorization.copy(currentRelayNonce = "relay\nnonce"))
        assertInvalid(authorization.copy(nextRelayNonce = "relay\u0000nonce"))
        assertInvalid(authorization.copy(nextRelayNonce = "n".repeat(513)))
    }

    private fun fixedAuthorization() = PairedRelayAllocationAuthorization(
        operation = "claim",
        requestId = "request-fixed-1",
        authorizationId = "authorization-fixed-1",
        currentRelayId = "rt2-${hex("01")}",
        nextRelayId = "rt2-${hex("02")}",
        routeTokenHash = hex("12"),
        runtimeKeyFingerprint = RUNTIME_FINGERPRINT,
        clientKeyFingerprint = CLIENT_FINGERPRINT,
        currentTicketGeneration = 7,
        nextTicketGeneration = 8,
        currentRelayExpiresAtEpochMillis = 1_780_000_000_123,
        currentRelayNonce = hex("34"),
        nextRelayExpiresAtEpochMillis = 1_780_003_600_123,
        nextRelayNonce = hex("56"),
        challenge = hex("78"),
        challengeExpiresAtEpochMillis = 1_779_999_999_123,
        transportBinding = hex("9a"),
    )

    private fun fixedClientIdentity() = DeviceIdentity(
        deviceId = "client-fixed-1",
        deviceName = "Android Device",
        publicKeyBase64 = CLIENT_PUBLIC_KEY,
        keyPair = clientKeyPair(),
    )

    private fun runtimeKeyPair(): KeyPair = fixedKeyPair(BigInteger.ONE, RUNTIME_PUBLIC_KEY)

    private fun clientKeyPair(): KeyPair = fixedKeyPair(BigInteger.TWO, CLIENT_PUBLIC_KEY)

    private fun fixedKeyPair(scalar: BigInteger, publicKeyBase64: String): KeyPair {
        val parameters = AlgorithmParameters.getInstance("EC").run {
            init(ECGenParameterSpec("secp256r1"))
            getParameterSpec(ECParameterSpec::class.java)
        }
        val keyFactory = KeyFactory.getInstance("EC")
        return KeyPair(
            keyFactory.generatePublic(X509EncodedKeySpec(Base64.getDecoder().decode(publicKeyBase64))),
            keyFactory.generatePrivate(ECPrivateKeySpec(scalar, parameters)),
        )
    }

    private fun deterministicP384KeyPair(): KeyPair {
        val random = SecureRandom.getInstance("SHA1PRNG").apply { setSeed(byteArrayOf(3, 8, 4)) }
        return KeyPairGenerator.getInstance("EC").run {
            initialize(ECGenParameterSpec("secp384r1"), random)
            generateKeyPair()
        }
    }

    private fun sign(keyPair: KeyPair, message: ByteArray): String =
        Signature.getInstance("SHA256withECDSA").run {
            initSign(keyPair.private)
            update(message)
            Base64.getEncoder().encodeToString(sign())
        }

    private fun makeNonCanonicalDer(signatureBase64: String): String {
        val der = Base64.getDecoder().decode(signatureBase64)
        val firstIntegerLength = der[3].toInt() and 0xff
        val output = ByteArray(der.size + 1)
        output[0] = 0x30
        output[1] = (der[1] + 1).toByte()
        output[2] = 0x02
        output[3] = (firstIntegerLength + 1).toByte()
        output[4] = 0
        der.copyInto(output, destinationOffset = 5, startIndex = 4)
        return Base64.getEncoder().encodeToString(output)
    }

    private fun fingerprint(encodedPublicKey: ByteArray): String = MessageDigest.getInstance("SHA-256")
        .digest(encodedPublicKey)
        .joinToString("") { "%02x".format(it) }

    private fun assertInvalid(authorization: PairedRelayAllocationAuthorization) {
        assertThrows(IllegalArgumentException::class.java) { authorization.runtimeTranscript() }
        assertThrows(IllegalArgumentException::class.java) { authorization.clientTranscript() }
    }

    private fun hex(byte: String): String = byte.repeat(32)

    companion object {
        private const val RUNTIME_PUBLIC_KEY =
            "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEaxfR8uEsQkf4vOblY6RA8ncDfYEt6zOg9KE5RdiYwpZP40Li/hp/m47n60p8D54WK84zV2sxXs7LtkBoN79R9Q=="
        private const val RUNTIME_FINGERPRINT =
            "5cd252fb0ce8932436faf8ccd1040981b89ee4ad6b9fe9e2a2b7e71aacb27cd3"
        private const val CLIENT_PUBLIC_KEY =
            "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEfPJ7GI0DT36KUjgDBLUaw8CJaeJ38hs1pgtI/EdmmXgHd1UQ247QQCk9msafdDDbun2t5jzpgimeBLedInhz0Q=="
        private const val CLIENT_FINGERPRINT =
            "dc0ce633dbcc913dafafa4b89ac44d8ce683fdfc3f60c8bdf21213b9f2b534ba"
        private const val RUNTIME_DIGEST =
            "445ee1adc3d521b2ba9d09e39d1ab23e913a262e5a5619f813ab162abc6ec37a"
        private const val CLIENT_DIGEST =
            "fa37320c45fef6dfdea036fd0315262d9f067f51b0ce335f7a31890419d822fa"
        private val EXPECTED_FIELD_ORDER = listOf(
            "scheme",
            "protocol_version",
            "operation",
            "request_id",
            "authorization_id",
            "current_relay_id",
            "next_relay_id",
            "route_token_hash",
            "runtime_key_fingerprint",
            "client_key_fingerprint",
            "current_ticket_generation",
            "next_ticket_generation",
            "current_relay_expires_at",
            "current_relay_nonce",
            "next_relay_expires_at",
            "next_relay_nonce",
            "challenge",
            "challenge_expires_at",
            "transport_binding",
        )
    }
}
