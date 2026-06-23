package com.localagentbridge.android.core.pairing

import android.util.Base64
import java.security.KeyPair
import java.security.KeyPairGenerator
import java.security.SecureRandom
import java.security.Signature
import java.security.spec.ECGenParameterSpec
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

data class TrustedMac(
    val deviceId: String,
    val name: String,
    val fingerprint: String,
    val host: String,
    val port: Int,
)

