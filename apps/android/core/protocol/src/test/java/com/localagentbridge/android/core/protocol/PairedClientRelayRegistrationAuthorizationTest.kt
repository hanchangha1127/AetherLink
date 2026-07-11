package com.localagentbridge.android.core.protocol

import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.math.BigInteger
import java.security.AlgorithmParameters
import java.security.KeyFactory
import java.security.Signature
import java.security.spec.ECGenParameterSpec
import java.security.spec.ECParameterSpec
import java.security.spec.ECPrivateKeySpec
import java.security.spec.X509EncodedKeySpec
import java.util.Base64

class PairedClientRelayRegistrationAuthorizationTest {
    @Test
    fun challengeControlLineParsesExactJsonAndRejectsMalformedEnvelopes() {
        val challenge = fixedChallenge()
        val json = Json.encodeToString(challenge)
        val line = PAIRED_CLIENT_RELAY_REGISTRATION_CHALLENGE_PREFIX + json

        assertEquals(
            challenge,
            PairedClientRelayRegistrationAuthorization.parseChallengeControlLine(line),
        )

        val missingField = json.replace(",\"challenge\":\"$CHALLENGE\"", "")
        assertTrue(missingField != json)
        val malformedLines = listOf(
            PAIRED_CLIENT_RELAY_REGISTRATION_CHALLENGE_PREFIX + missingField,
            PAIRED_CLIENT_RELAY_REGISTRATION_CHALLENGE_PREFIX + json.dropLast(1),
            PAIRED_CLIENT_RELAY_REGISTRATION_CHALLENGE_PREFIX +
                json.dropLast(1) + ",\"unknown\":true}",
            "AETHERLINK_RELAY client_registration_challenge extra $json",
            "client_registration_challenge AETHERLINK_RELAY $json",
            line + "\r",
            line + " ",
        )

        malformedLines.forEach { malformed ->
            assertThrows(IllegalArgumentException::class.java) {
                PairedClientRelayRegistrationAuthorization.parseChallengeControlLine(malformed)
            }
        }
    }

    @Test
    fun proofControlLineUsesExactCanonicalFormattingWithRealP256Signature() {
        val challenge = fixedChallenge()
        val signature = signChallenge(challenge)
        val proof = PairedClientRelayRegistrationProof(
            clientPublicKeyBase64 = CLIENT_PUBLIC_KEY,
            clientSignatureBase64 = signature,
        )

        assertTrue(verifyChallengeSignature(challenge, signature))
        assertEquals(
            "AETHERLINK_RELAY client_registration_proof crypto=2 challenge=$CHALLENGE " +
                "client_public_key=$CLIENT_PUBLIC_KEY client_signature=$signature\n",
            PairedClientRelayRegistrationAuthorization.proofControlLine(challenge, proof),
        )
    }

    @Test
    fun proofControlLineRejectsNoncanonicalBase64AndDer() {
        val challenge = fixedChallenge()
        val canonicalSignature = signChallenge(challenge)
        val signatureDer = Base64.getDecoder().decode(canonicalSignature)
        val longFormLengthDer = byteArrayOf(signatureDer[0], 0x81.toByte(), signatureDer[1]) +
            signatureDer.copyOfRange(2, signatureDer.size)
        val invalidProofs = listOf(
            PairedClientRelayRegistrationProof(CLIENT_PUBLIC_KEY + "\n", canonicalSignature),
            PairedClientRelayRegistrationProof(CLIENT_PUBLIC_KEY, canonicalSignature + "\n"),
            PairedClientRelayRegistrationProof(
                CLIENT_PUBLIC_KEY,
                Base64.getEncoder().encodeToString(longFormLengthDer),
            ),
            PairedClientRelayRegistrationProof(
                CLIENT_PUBLIC_KEY,
                Base64.getEncoder().encodeToString(
                    byteArrayOf(0x30, 0x06, 0x02, 0x01, 0x80.toByte(), 0x02, 0x01, 0x01),
                ),
            ),
            PairedClientRelayRegistrationProof(
                CLIENT_PUBLIC_KEY,
                Base64.getEncoder().encodeToString(
                    byteArrayOf(0x30, 0x07, 0x02, 0x02, 0x00, 0x01, 0x02, 0x01, 0x01),
                ),
            ),
            PairedClientRelayRegistrationProof(
                CLIENT_PUBLIC_KEY,
                Base64.getEncoder().encodeToString(
                    byteArrayOf(0x30, 0x06, 0x02, 0x01, 0x01, 0x02, 0x01, 0x01, 0x00),
                ),
            ),
        )

        invalidProofs.forEach { proof ->
            assertThrows(IllegalArgumentException::class.java) {
                PairedClientRelayRegistrationAuthorization.proofControlLine(challenge, proof)
            }
        }
    }

    @Test
    fun fixedSharedTranscriptAndDigestVectorMatch() {
        val fixed = fixedChallenge()
        val transcript = fixed.transcript().toString(Charsets.UTF_8)

        assertEquals(DIGEST, fixed.digest())
        assertFalse(transcript.endsWith("\n"))
        assertTrue(transcript.contains("scheme\n21\npaired-client-p256-v1"))
        assertTrue(transcript.contains("ephemeral_key\n130\n$EPHEMERAL_KEY"))
        assertEquals(CLIENT_FINGERPRINT, PairedClientRelayRegistrationAuthorization.clientKeyFingerprint(CLIENT_PUBLIC_KEY))
    }

    @Test
    fun everyTranscriptFieldMutationChangesDigest() {
        val fixed = fixedChallenge()
        val mutations = listOf(
            fixed.copy(relayId = "rt2-${"a".repeat(64)}"),
            fixed.copy(relayExpiresAtEpochMillis = fixed.relayExpiresAtEpochMillis + 1),
            fixed.copy(relayNonce = "relay-nonce-fixed-9"),
            fixed.copy(runtimeKeyFingerprint = "a".repeat(64)),
            fixed.copy(clientKeyFingerprint = "b".repeat(64)),
            fixed.copy(ticketGeneration = 9),
            fixed.copy(sessionNonce = "ffeeddccbbaa99887766554433221100"),
            fixed.copy(ephemeralKey = RUNTIME_EPHEMERAL_KEY),
            fixed.copy(challenge = "c".repeat(64)),
            fixed.copy(challengeExpiresAtEpochMillis = fixed.challengeExpiresAtEpochMillis + 1),
        )

        mutations.forEach { mutation ->
            assertTrue(mutation.digest() != fixed.digest())
        }
    }

    @Test
    fun rejectsRoleSchemeAndVersionDowngrades() {
        listOf(
            fixedChallenge().copy(role = "runtime"),
            fixedChallenge().copy(scheme = "paired-client-p256-v0"),
            fixedChallenge().copy(scheme = "runtime-p256-v1"),
            fixedChallenge().copy(protocolVersion = 0),
        ).forEach { downgraded ->
            assertThrows(IllegalArgumentException::class.java) { downgraded.validate() }
        }
    }

    @Test
    fun rejectsNoncanonicalRelayCryptoAndIdentityFields() {
        val invalid = listOf(
            fixedChallenge().copy(relayId = "rt3-${"a".repeat(64)}"),
            fixedChallenge().copy(relayId = RELAY_ID.uppercase()),
            fixedChallenge().copy(relayExpiresAtEpochMillis = 0),
            fixedChallenge().copy(relayNonce = ""),
            fixedChallenge().copy(relayNonce = "relay nonce"),
            fixedChallenge().copy(relayNonce = "n".repeat(513)),
            fixedChallenge().copy(runtimeKeyFingerprint = RUNTIME_FINGERPRINT.uppercase()),
            fixedChallenge().copy(clientKeyFingerprint = RUNTIME_FINGERPRINT),
            fixedChallenge().copy(ticketGeneration = 0),
            fixedChallenge().copy(sessionNonce = SESSION_NONCE.uppercase()),
            fixedChallenge().copy(ephemeralKey = EPHEMERAL_KEY.uppercase()),
            fixedChallenge().copy(ephemeralKey = "04" + "0".repeat(128)),
            fixedChallenge().copy(challenge = CHALLENGE.uppercase()),
            fixedChallenge().copy(challengeExpiresAtEpochMillis = 0),
        )

        invalid.forEach { value ->
            assertThrows(IllegalArgumentException::class.java) { value.validate() }
        }
    }

    @Test
    fun freshnessAndUtf8LengthFramingUseStrictBoundaries() {
        val fixed = fixedChallenge()

        assertTrue(fixed.isFresh(1_780_000_000_000))
        assertTrue(fixed.isRelayFresh(1_780_000_000_123))
        assertFalse(fixed.isChallengeFresh(1_780_000_000_123))
        assertFalse(fixed.isFresh(1_780_000_000_123))
        assertFalse(fixed.isRelayFresh(1_780_003_600_000))
        assertFalse(fixed.isFresh(-1))

        val unicodeNonceTranscript = fixed.copy(relayNonce = "é").transcript().toString(Charsets.UTF_8)
        assertTrue(unicodeNonceTranscript.contains("relay_nonce\n2\né"))
    }

    @Test
    fun rejectsNoncanonicalOrNonP256IdentityPublicKeys() {
        assertThrows(IllegalArgumentException::class.java) {
            PairedClientRelayRegistrationAuthorization.clientKeyFingerprint(CLIENT_PUBLIC_KEY + "\n")
        }
        assertThrows(IllegalArgumentException::class.java) {
            PairedClientRelayRegistrationAuthorization.clientKeyFingerprint(
                java.util.Base64.getEncoder().encodeToString(ByteArray(32)),
            )
        }
    }

    private fun fixedChallenge() = PairedClientRelayRegistrationChallenge(
        relayId = RELAY_ID,
        relayExpiresAtEpochMillis = 1_780_003_600_000,
        relayNonce = "relay-nonce-fixed-8",
        runtimeKeyFingerprint = RUNTIME_FINGERPRINT,
        clientKeyFingerprint = CLIENT_FINGERPRINT,
        ticketGeneration = 8,
        sessionNonce = SESSION_NONCE,
        ephemeralKey = EPHEMERAL_KEY,
        challenge = CHALLENGE,
        challengeExpiresAtEpochMillis = 1_780_000_000_123,
    )

    private fun signChallenge(challenge: PairedClientRelayRegistrationChallenge): String {
        val signer = Signature.getInstance("SHA256withECDSA")
        signer.initSign(fixedClientPrivateKey())
        signer.update(challenge.transcript())
        return Base64.getEncoder().encodeToString(signer.sign())
    }

    private fun verifyChallengeSignature(
        challenge: PairedClientRelayRegistrationChallenge,
        signatureBase64: String,
    ): Boolean {
        val verifier = Signature.getInstance("SHA256withECDSA")
        verifier.initVerify(
            KeyFactory.getInstance("EC").generatePublic(
                X509EncodedKeySpec(Base64.getDecoder().decode(CLIENT_PUBLIC_KEY)),
            ),
        )
        verifier.update(challenge.transcript())
        return verifier.verify(Base64.getDecoder().decode(signatureBase64))
    }

    private fun fixedClientPrivateKey() = KeyFactory.getInstance("EC").generatePrivate(
        ECPrivateKeySpec(BigInteger.valueOf(2L), p256Parameters()),
    )

    private fun p256Parameters(): ECParameterSpec = AlgorithmParameters.getInstance("EC").run {
        init(ECGenParameterSpec("secp256r1"))
        getParameterSpec(ECParameterSpec::class.java)
    }

    companion object {
        private const val RELAY_ID =
            "rt2-bab80c6a36ca54015900f1b37def33f2c15892836cb6b2907faacc3522a78361"
        private const val RUNTIME_FINGERPRINT =
            "5cd252fb0ce8932436faf8ccd1040981b89ee4ad6b9fe9e2a2b7e71aacb27cd3"
        private const val CLIENT_FINGERPRINT =
            "dc0ce633dbcc913dafafa4b89ac44d8ce683fdfc3f60c8bdf21213b9f2b534ba"
        private const val SESSION_NONCE = "00112233445566778899aabbccddeeff"
        private const val EPHEMERAL_KEY =
            "047cf27b188d034f7e8a52380304b51ac3c08969e277f21b35a60b48fc4766997807775510db8ed040293d9ac69f7430dbba7dade63ce982299e04b79d227873d1"
        private const val RUNTIME_EPHEMERAL_KEY =
            "046b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c2964fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5"
        private const val CHALLENGE =
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        private const val DIGEST =
            "84181665e9bb332c46838e3e473ff6a98f2deb0eb74ccb1f5773b8f8d149412f"
        private const val CLIENT_PUBLIC_KEY =
            "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEfPJ7GI0DT36KUjgDBLUaw8CJaeJ38hs1pgtI/EdmmXgHd1UQ247QQCk9msafdDDbun2t5jzpgimeBLedInhz0Q=="
    }
}
