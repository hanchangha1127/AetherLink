package com.localagentbridge.android.core.pairing

import android.content.Context
import android.os.Build
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.withContext
import java.security.KeyPair
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.spec.ECGenParameterSpec
import java.util.Base64
import java.util.UUID

class DeviceIdentityStore internal constructor(
    private val context: Context,
    private val keyPairStore: DeviceIdentityKeyPairStore,
) {
    constructor(context: Context) : this(context, AndroidKeystoreDeviceIdentityKeyPairStore())

    suspend fun loadOrCreate(): DeviceIdentity = withContext(Dispatchers.IO) {
        val prefs = context.localAgentBridgeDataStore.data.first()
        val deviceId = prefs[Keys.deviceId] ?: UUID.randomUUID().toString()
        val deviceName = prefs[Keys.deviceName] ?: defaultDeviceName()
        val keyPair = keyPairStore.loadOrCreate()

        if (prefs[Keys.deviceId] == null || prefs[Keys.deviceName] == null) {
            context.localAgentBridgeDataStore.edit { updated ->
                updated[Keys.deviceId] = deviceId
                updated[Keys.deviceName] = deviceName
            }
        }

        DeviceIdentity(
            deviceId = deviceId,
            deviceName = deviceName,
            publicKeyBase64 = Base64.getEncoder().encodeToString(keyPair.public.encoded),
            keyPair = keyPair,
        )
    }

    private fun defaultDeviceName(): String {
        val manufacturer = Build.MANUFACTURER.orEmpty().replaceFirstChar { it.uppercase() }
        val model = Build.MODEL.orEmpty()
        return listOf(manufacturer, model)
            .filter { it.isNotBlank() }
            .joinToString(" ")
            .ifBlank { "AetherLink Client" }
    }

    private object Keys {
        val deviceId = stringPreferencesKey("android_device_id")
        val deviceName = stringPreferencesKey("android_device_name")
    }
}

internal interface DeviceIdentityKeyPairStore {
    fun loadOrCreate(): KeyPair
}

private class AndroidKeystoreDeviceIdentityKeyPairStore : DeviceIdentityKeyPairStore {
    override fun loadOrCreate(): KeyPair {
        val keyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }
        if (!keyStore.containsAlias(KEY_ALIAS)) {
            val generator = KeyPairGenerator.getInstance(
                KeyProperties.KEY_ALGORITHM_EC,
                ANDROID_KEYSTORE,
            )
            generator.initialize(
                KeyGenParameterSpec.Builder(
                    KEY_ALIAS,
                    KeyProperties.PURPOSE_SIGN or KeyProperties.PURPOSE_VERIFY,
                )
                    .setAlgorithmParameterSpec(ECGenParameterSpec("secp256r1"))
                    .setDigests(KeyProperties.DIGEST_SHA256)
                    .build(),
            )
            generator.generateKeyPair()
        }

        val entry = keyStore.getEntry(KEY_ALIAS, null) as KeyStore.PrivateKeyEntry
        return KeyPair(entry.certificate.publicKey, entry.privateKey)
    }

    private companion object {
        const val ANDROID_KEYSTORE = "AndroidKeyStore"
        const val KEY_ALIAS = "aetherlink_android_device"
    }
}
