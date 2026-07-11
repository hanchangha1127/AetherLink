package com.localagentbridge.android.core.pairing

import com.localagentbridge.android.core.protocol.PairedClientRelayRegistrationAuthorization
import com.localagentbridge.android.core.protocol.PairedClientRelayRegistrationChallenge
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.security.KeyFactory
import java.security.Signature
import java.security.spec.X509EncodedKeySpec
import java.util.Base64

class DeviceIdentityPairedClientRelayRegistrationTest {
    @Test
    fun signsOnlyChallengeBoundToActualCanonicalIdentityKey() {
        val identity = DeviceIdentityFactory.create("Android Device")
        val challenge = challengeFor(identity)
        val signature = identity.signPairedClientRelayRegistrationAuthorization(challenge)

        assertTrue(verify(identity.publicKeyBase64, challenge, signature))
        assertTrue(isCanonicalDer(Base64.getDecoder().decode(signature)))
        assertTrue(Base64.getEncoder().encodeToString(Base64.getDecoder().decode(signature)) == signature)

        val otherIdentity = DeviceIdentityFactory.create("Other Android Device")
        assertThrows(IllegalArgumentException::class.java) {
            otherIdentity.signPairedClientRelayRegistrationAuthorization(challenge)
        }
        assertThrows(IllegalArgumentException::class.java) {
            identity.signPairedClientRelayRegistrationAuthorization(
                challenge.copy(clientKeyFingerprint = "f".repeat(64)),
            )
        }
    }

    @Test
    fun signatureRejectsMutationWrongKeyAndNoncanonicalEncoding() {
        val identity = DeviceIdentityFactory.create("Android Device")
        val challenge = challengeFor(identity)
        val signature = identity.signPairedClientRelayRegistrationAuthorization(challenge)
        val otherIdentity = DeviceIdentityFactory.create("Other Android Device")

        assertFalse(verify(identity.publicKeyBase64, challenge.copy(ticketGeneration = 9), signature))
        assertFalse(verify(otherIdentity.publicKeyBase64, challenge, signature))
        assertFalse(verify(identity.publicKeyBase64, challenge, signature + "\n"))
    }

    @Test
    fun signingRejectsRoleAndProtocolDowngradesBeforeCryptography() {
        val identity = DeviceIdentityFactory.create("Android Device")
        val challenge = challengeFor(identity)

        listOf(
            challenge.copy(role = "runtime"),
            challenge.copy(protocolVersion = 0),
            challenge.copy(scheme = "paired-client-p256-v0"),
        ).forEach { downgraded ->
            assertThrows(IllegalArgumentException::class.java) {
                identity.signPairedClientRelayRegistrationAuthorization(downgraded)
            }
        }
    }

    private fun challengeFor(identity: DeviceIdentity): PairedClientRelayRegistrationChallenge {
        val clientFingerprint = PairedClientRelayRegistrationAuthorization
            .clientKeyFingerprint(identity.publicKeyBase64)
        val runtimeFingerprint = if (clientFingerprint == "0".repeat(64)) {
            "1".repeat(64)
        } else {
            "0".repeat(64)
        }
        return PairedClientRelayRegistrationChallenge(
            relayId = "rt2-${"a".repeat(64)}",
            relayExpiresAtEpochMillis = 1_780_003_600_000,
            relayNonce = "relay-nonce-device-test",
            runtimeKeyFingerprint = runtimeFingerprint,
            clientKeyFingerprint = clientFingerprint,
            ticketGeneration = 8,
            sessionNonce = "00112233445566778899aabbccddeeff",
            ephemeralKey =
                "047cf27b188d034f7e8a52380304b51ac3c08969e277f21b35a60b48fc4766997807775510db8ed040293d9ac69f7430dbba7dade63ce982299e04b79d227873d1",
            challenge = "0123456789abcdef".repeat(4),
            challengeExpiresAtEpochMillis = 1_780_000_000_123,
        )
    }

    private fun verify(
        publicKeyBase64: String,
        challenge: PairedClientRelayRegistrationChallenge,
        signatureBase64: String,
    ): Boolean = runCatching {
        val publicKey = KeyFactory.getInstance("EC").generatePublic(
            X509EncodedKeySpec(Base64.getDecoder().decode(publicKeyBase64)),
        )
        Signature.getInstance("SHA256withECDSA").run {
            initVerify(publicKey)
            update(challenge.transcript())
            verify(Base64.getDecoder().decode(signatureBase64))
        }
    }.getOrDefault(false)

    private fun isCanonicalDer(der: ByteArray): Boolean {
        if (der.size !in 8..72 || der[0] != 0x30.toByte() || der[1].toInt() != der.size - 2) return false
        var index = 2
        repeat(2) {
            if (index + 2 > der.size || der[index++] != 0x02.toByte()) return false
            val length = der[index++].toInt() and 0xff
            if (length !in 1..33 || index + length > der.size) return false
            if (der[index].toInt() and 0x80 != 0) return false
            if (length > 1 && der[index] == 0.toByte() && der[index + 1].toInt() and 0x80 == 0) return false
            index += length
        }
        return index == der.size
    }
}
