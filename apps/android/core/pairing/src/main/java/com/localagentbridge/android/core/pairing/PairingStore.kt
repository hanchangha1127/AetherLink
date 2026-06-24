package com.localagentbridge.android.core.pairing

import android.content.Context
import androidx.datastore.preferences.core.MutablePreferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

internal val Context.localAgentBridgeDataStore by preferencesDataStore("local_agent_bridge")

class PairingStore(private val context: Context) {
    val trustedRuntime: Flow<TrustedRuntime?> = context.localAgentBridgeDataStore.data.map { prefs ->
        val id = prefs[Keys.runtimeDeviceId] ?: prefs[LegacyKeys.runtimeDeviceId] ?: return@map null
        val name = prefs[Keys.runtimeName] ?: prefs[LegacyKeys.runtimeName] ?: "AetherLink Runtime"
        val fingerprint = prefs[Keys.runtimeFingerprint] ?: prefs[LegacyKeys.runtimeFingerprint] ?: return@map null
        val publicKeyBase64 = prefs[Keys.runtimePublicKey] ?: prefs[LegacyKeys.runtimePublicKey]
        val routeToken = prefs[Keys.runtimeRouteToken] ?: prefs[LegacyKeys.runtimeRouteToken]
        val host = prefs[Keys.runtimeHost] ?: prefs[LegacyKeys.runtimeHost]
        val port = prefs[Keys.runtimePort] ?: prefs[LegacyKeys.runtimePort]
        TrustedRuntime(id, name, fingerprint, publicKeyBase64, routeToken, host, port)
    }

    suspend fun trustRuntime(runtime: TrustedRuntime) {
        context.localAgentBridgeDataStore.edit { prefs ->
            prefs[Keys.runtimeDeviceId] = runtime.deviceId
            prefs[Keys.runtimeName] = runtime.name
            prefs[Keys.runtimeFingerprint] = runtime.fingerprint
            val publicKeyBase64 = runtime.publicKeyBase64
            if (!publicKeyBase64.isNullOrBlank()) {
                prefs[Keys.runtimePublicKey] = publicKeyBase64
            } else {
                prefs.remove(Keys.runtimePublicKey)
            }
            val routeToken = runtime.routeToken
            if (!routeToken.isNullOrBlank()) {
                prefs[Keys.runtimeRouteToken] = routeToken
            } else {
                prefs.remove(Keys.runtimeRouteToken)
            }
            prefs.remove(Keys.runtimeHost)
            prefs.remove(Keys.runtimePort)
            prefs.removeLegacyRuntimeKeys()
        }
    }

    suspend fun forgetRuntime() {
        context.localAgentBridgeDataStore.edit { prefs ->
            prefs.removeRuntimeKeys()
            prefs.removeLegacyRuntimeKeys()
        }
    }

    private object Keys {
        val runtimeDeviceId = stringPreferencesKey("runtime_device_id")
        val runtimeName = stringPreferencesKey("runtime_name")
        val runtimeFingerprint = stringPreferencesKey("runtime_fingerprint")
        val runtimePublicKey = stringPreferencesKey("runtime_public_key")
        val runtimeRouteToken = stringPreferencesKey("runtime_route_token")
        val runtimeHost = stringPreferencesKey("runtime_host")
        val runtimePort = intPreferencesKey("runtime_port")
    }

    private object LegacyKeys {
        val runtimeDeviceId = stringPreferencesKey("mac_device_id")
        val runtimeName = stringPreferencesKey("mac_name")
        val runtimeFingerprint = stringPreferencesKey("mac_fingerprint")
        val runtimePublicKey = stringPreferencesKey("mac_public_key")
        val runtimeRouteToken = stringPreferencesKey("mac_route_token")
        val runtimeHost = stringPreferencesKey("mac_host")
        val runtimePort = intPreferencesKey("mac_port")
    }

    private fun MutablePreferences.removeRuntimeKeys() {
        remove(Keys.runtimeDeviceId)
        remove(Keys.runtimeName)
        remove(Keys.runtimeFingerprint)
        remove(Keys.runtimePublicKey)
        remove(Keys.runtimeRouteToken)
        remove(Keys.runtimeHost)
        remove(Keys.runtimePort)
    }

    private fun MutablePreferences.removeLegacyRuntimeKeys() {
        remove(LegacyKeys.runtimeDeviceId)
        remove(LegacyKeys.runtimeName)
        remove(LegacyKeys.runtimeFingerprint)
        remove(LegacyKeys.runtimePublicKey)
        remove(LegacyKeys.runtimeRouteToken)
        remove(LegacyKeys.runtimeHost)
        remove(LegacyKeys.runtimePort)
    }
}
