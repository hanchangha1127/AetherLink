package com.localagentbridge.android.core.pairing

import android.content.Context
import androidx.datastore.preferences.core.MutablePreferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.longPreferencesKey
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
        val host: String? = null
        val port: Int? = null
        val relayHost = prefs[Keys.runtimeRelayHost]
        val relayPort = prefs[Keys.runtimeRelayPort]
        val relayId = prefs[Keys.runtimeRelayId]
        val relaySecret = prefs[Keys.runtimeRelaySecret]
        val relayExpiresAtEpochMillis = prefs[Keys.runtimeRelayExpiresAtEpochMillis]
        val relayNonce = prefs[Keys.runtimeRelayNonce]
        val relayScope = prefs[Keys.runtimeRelayScope]
        val trusted = TrustedRuntime(
            id,
            name,
            fingerprint,
            publicKeyBase64,
            routeToken,
            host,
            port,
            relayHost,
            relayPort,
            relayId,
            relaySecret,
            relayExpiresAtEpochMillis,
            relayNonce,
            relayScope,
        )
        if (trusted.hasCompleteRelayRoute()) {
            trusted
        } else {
            trusted.withoutRelayRoute()
        }
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
            val relayHost = runtime.relayHost
            val relayPort = runtime.relayPort
            val relayId = runtime.relayId
            val relaySecret = runtime.relaySecret
            val relayScope = runtime.relayScope
            if (runtime.hasValidRelayRoute()) {
                prefs[Keys.runtimeRelayHost] = requireNotNull(relayHost)
                prefs[Keys.runtimeRelayPort] = requireNotNull(relayPort)
                prefs[Keys.runtimeRelayId] = requireNotNull(relayId)
                prefs[Keys.runtimeRelaySecret] = requireNotNull(relaySecret)
                val relayExpiresAtEpochMillis = runtime.relayExpiresAtEpochMillis
                if (relayExpiresAtEpochMillis != null && relayExpiresAtEpochMillis > 0L) {
                    prefs[Keys.runtimeRelayExpiresAtEpochMillis] = relayExpiresAtEpochMillis
                } else {
                    prefs.remove(Keys.runtimeRelayExpiresAtEpochMillis)
                }
                val relayNonce = runtime.relayNonce
                if (!relayNonce.isNullOrBlank()) {
                    prefs[Keys.runtimeRelayNonce] = relayNonce
                } else {
                    prefs.remove(Keys.runtimeRelayNonce)
                }
                if (!relayScope.isNullOrBlank()) {
                    prefs[Keys.runtimeRelayScope] = relayScope
                } else {
                    prefs.remove(Keys.runtimeRelayScope)
                }
            } else {
                prefs.remove(Keys.runtimeRelayHost)
                prefs.remove(Keys.runtimeRelayPort)
                prefs.remove(Keys.runtimeRelayId)
                prefs.remove(Keys.runtimeRelaySecret)
                prefs.remove(Keys.runtimeRelayExpiresAtEpochMillis)
                prefs.remove(Keys.runtimeRelayNonce)
                prefs.remove(Keys.runtimeRelayScope)
            }
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
        val runtimeRelayHost = stringPreferencesKey("runtime_relay_host")
        val runtimeRelayPort = intPreferencesKey("runtime_relay_port")
        val runtimeRelayId = stringPreferencesKey("runtime_relay_id")
        val runtimeRelaySecret = stringPreferencesKey("runtime_relay_secret")
        val runtimeRelayExpiresAtEpochMillis = longPreferencesKey("runtime_relay_expires_at_epoch_millis")
        val runtimeRelayNonce = stringPreferencesKey("runtime_relay_nonce")
        val runtimeRelayScope = stringPreferencesKey("runtime_relay_scope")
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
        remove(Keys.runtimeRelayHost)
        remove(Keys.runtimeRelayPort)
        remove(Keys.runtimeRelayId)
        remove(Keys.runtimeRelaySecret)
        remove(Keys.runtimeRelayExpiresAtEpochMillis)
        remove(Keys.runtimeRelayNonce)
        remove(Keys.runtimeRelayScope)
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

internal data class TrustedRuntimeDirectEndpoint(
    val host: String,
    val port: Int,
)

internal fun TrustedRuntime.hasValidRelayRoute(): Boolean {
    val expiresAt = relayExpiresAtEpochMillis
    return hasCompleteRelayRoute() &&
        expiresAt != null &&
        expiresAt > System.currentTimeMillis()
}

internal fun TrustedRuntime.hasExpiredRelayRoute(
    nowEpochMillis: Long = System.currentTimeMillis(),
): Boolean {
    val expiresAt = relayExpiresAtEpochMillis ?: return false
    return hasCompleteRelayRoute() && expiresAt <= nowEpochMillis
}

private fun TrustedRuntime.hasCompleteRelayRoute(): Boolean {
    val expiresAt = relayExpiresAtEpochMillis
    return !relayHost.isNullOrBlank() &&
        (isEligibleRemoteRelayHost(relayHost, relayScope) || relayHost.isDebugUsbReverseRelayRoute(relayScope)) &&
        relayPort != null &&
        relayPort in 1..65535 &&
        !relayId.isNullOrBlank() &&
        !relaySecret.isNullOrBlank() &&
        expiresAt != null &&
        expiresAt > 0L &&
        !relayNonce.isNullOrBlank()
}

private fun TrustedRuntime.withoutRelayRoute(): TrustedRuntime {
    return copy(
        relayHost = null,
        relayPort = null,
        relayId = null,
        relaySecret = null,
        relayExpiresAtEpochMillis = null,
        relayNonce = null,
        relayScope = null,
    )
}

internal fun TrustedRuntime.validDirectEndpointOrNull(): TrustedRuntimeDirectEndpoint? {
    if (hasValidRelayRoute()) return null
    val endpointHost = host?.takeIf { it.isNotBlank() } ?: return null
    val endpointPort = port?.takeIf { it in 1..65535 } ?: return null
    return TrustedRuntimeDirectEndpoint(endpointHost, endpointPort)
}

private fun String.isDebugUsbReverseRelayRoute(relayScope: String?): Boolean {
    if (relayScope?.trim()?.lowercase() != DEBUG_USB_REVERSE_RELAY_SCOPE) return false
    val normalized = trim()
        .removePrefix("[")
        .removeSuffix("]")
        .removeSuffix(".")
        .lowercase()
    return normalized == "localhost" ||
        normalized == "::1" ||
        normalized == "0:0:0:0:0:0:0:1" ||
        normalized.startsWith("127.")
}

private const val DEBUG_USB_REVERSE_RELAY_SCOPE = "usb_reverse"
