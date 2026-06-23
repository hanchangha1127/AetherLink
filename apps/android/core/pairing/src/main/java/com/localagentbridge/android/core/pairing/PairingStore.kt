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
        val routeToken = prefs[Keys.macRouteToken]
        val host = prefs[Keys.macHost]
        val port = prefs[Keys.macPort]
        TrustedMac(id, name, fingerprint, routeToken, host, port)
    }

    suspend fun trustMac(mac: TrustedMac) {
        context.localAgentBridgeDataStore.edit { prefs ->
            prefs[Keys.macDeviceId] = mac.deviceId
            prefs[Keys.macName] = mac.name
            prefs[Keys.macFingerprint] = mac.fingerprint
            val routeToken = mac.routeToken
            if (!routeToken.isNullOrBlank()) {
                prefs[Keys.macRouteToken] = routeToken
            } else {
                prefs.remove(Keys.macRouteToken)
            }
            val host = mac.host
            val port = mac.port
            if (!host.isNullOrBlank() && port != null) {
                prefs[Keys.macHost] = host
                prefs[Keys.macPort] = port
            } else {
                prefs.remove(Keys.macHost)
                prefs.remove(Keys.macPort)
            }
        }
    }

    suspend fun forgetMac() {
        context.localAgentBridgeDataStore.edit { prefs ->
            prefs.remove(Keys.macDeviceId)
            prefs.remove(Keys.macName)
            prefs.remove(Keys.macFingerprint)
            prefs.remove(Keys.macRouteToken)
            prefs.remove(Keys.macHost)
            prefs.remove(Keys.macPort)
        }
    }

    private object Keys {
        val macDeviceId = stringPreferencesKey("mac_device_id")
        val macName = stringPreferencesKey("mac_name")
        val macFingerprint = stringPreferencesKey("mac_fingerprint")
        val macRouteToken = stringPreferencesKey("mac_route_token")
        val macHost = stringPreferencesKey("mac_host")
        val macPort = intPreferencesKey("mac_port")
    }
}
