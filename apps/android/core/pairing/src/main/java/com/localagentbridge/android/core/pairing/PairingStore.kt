package com.localagentbridge.android.core.pairing

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

internal val Context.localAgentBridgeDataStore by preferencesDataStore("local_agent_bridge")

class PairingStore(private val context: Context) {
    val trustedMac: Flow<TrustedMac?> = context.localAgentBridgeDataStore.data.map { prefs ->
        val id = prefs[Keys.macDeviceId] ?: return@map null
        val name = prefs[Keys.macName] ?: "Mac Companion"
        val fingerprint = prefs[Keys.macFingerprint] ?: return@map null
        val host = prefs[Keys.macHost] ?: return@map null
        val port = prefs[Keys.macPort] ?: return@map null
        TrustedMac(id, name, fingerprint, host, port)
    }

    suspend fun trustMac(mac: TrustedMac) {
        context.localAgentBridgeDataStore.edit { prefs ->
            prefs[Keys.macDeviceId] = mac.deviceId
            prefs[Keys.macName] = mac.name
            prefs[Keys.macFingerprint] = mac.fingerprint
            prefs[Keys.macHost] = mac.host
            prefs[Keys.macPort] = mac.port
        }
    }

    suspend fun forgetMac() {
        context.localAgentBridgeDataStore.edit { prefs ->
            prefs.remove(Keys.macDeviceId)
            prefs.remove(Keys.macName)
            prefs.remove(Keys.macFingerprint)
            prefs.remove(Keys.macHost)
            prefs.remove(Keys.macPort)
        }
    }

    private object Keys {
        val macDeviceId = stringPreferencesKey("mac_device_id")
        val macName = stringPreferencesKey("mac_name")
        val macFingerprint = stringPreferencesKey("mac_fingerprint")
        val macHost = stringPreferencesKey("mac_host")
        val macPort = intPreferencesKey("mac_port")
    }
}
