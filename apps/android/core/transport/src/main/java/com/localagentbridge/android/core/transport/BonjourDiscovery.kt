package com.localagentbridge.android.core.transport

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.wifi.WifiManager
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import java.nio.charset.StandardCharsets

class BonjourDiscovery(context: Context) {
    private val appContext = context.applicationContext
    private val nsdManager = appContext.getSystemService(Context.NSD_SERVICE) as NsdManager
    private val wifiManager = appContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager

    fun discover(): Flow<List<DiscoveredRuntime>> = callbackFlow {
        val peers = linkedMapOf<String, DiscoveredRuntime>()
        val multicastLock = wifiManager
            ?.createMulticastLock("aetherlink-mdns")
            ?.also {
                it.setReferenceCounted(false)
                it.acquire()
            }

        val listener = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(serviceType: String) = Unit
            override fun onDiscoveryStopped(serviceType: String) = Unit
            override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
                close(IllegalStateException("NSD discovery failed: $errorCode"))
            }

            override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) = Unit

            override fun onServiceLost(serviceInfo: NsdServiceInfo) {
                peers.remove(serviceInfo.serviceName)
                trySend(peers.values.toList())
            }

            override fun onServiceFound(serviceInfo: NsdServiceInfo) {
                if (!serviceInfo.serviceType.startsWith(SERVICE_TYPE)) return
                nsdManager.resolveService(serviceInfo, object : NsdManager.ResolveListener {
                    override fun onResolveFailed(serviceInfo: NsdServiceInfo, errorCode: Int) = Unit

                    override fun onServiceResolved(resolved: NsdServiceInfo) {
                        val host = resolved.host?.hostAddress ?: return
                        val metadata = resolved.attributes.toBonjourTxtMetadataOrNull() ?: return
                        peers[resolved.serviceName] = DiscoveredRuntime(
                            serviceName = resolved.serviceName,
                            host = host,
                            port = resolved.port,
                            routeToken = metadata.routeToken,
                            deviceId = metadata.deviceId,
                            fingerprint = metadata.fingerprint,
                            app = metadata.app,
                            version = metadata.version,
                        )
                        trySend(peers.values.toList())
                    }
                })
            }
        }

        nsdManager.discoverServices(SERVICE_TYPE, NsdManager.PROTOCOL_DNS_SD, listener)
        awaitClose {
            runCatching { nsdManager.stopServiceDiscovery(listener) }
            multicastLock?.release()
        }
    }

    companion object {
        const val SERVICE_TYPE = "_aetherlink._tcp."
    }
}

internal data class BonjourTxtMetadata(
    val routeToken: String? = null,
    val deviceId: String? = null,
    val fingerprint: String? = null,
    val app: String? = null,
    val version: String? = null,
)

internal fun Map<String, ByteArray>.toBonjourTxtMetadataOrNull(): BonjourTxtMetadata? {
    if (containsForbiddenDiscoveryTxtAttribute()) return null
    val routeToken = canonicalIdentityTxtValueOrNull("route_token") ?: run {
        if (containsKey("route_token")) return null
        null
    }
    val deviceId = canonicalIdentityTxtValueOrNull("device_id") ?: run {
        if (containsKey("device_id")) return null
        null
    }
    val fingerprint = canonicalIdentityTxtValueOrNull("fingerprint") ?: run {
        if (containsKey("fingerprint")) return null
        null
    }

    return BonjourTxtMetadata(
        routeToken = routeToken,
        deviceId = deviceId,
        fingerprint = fingerprint,
        app = displayTxtValueOrNull("app"),
        version = displayTxtValueOrNull("version"),
    )
}

private fun Map<String, ByteArray>.canonicalIdentityTxtValueOrNull(key: String): String? {
    val value = this[key]?.decodeDiscoveryTxtStringOrNull() ?: return null
    return value.takeIf { candidate ->
        candidate.isNotEmpty() &&
            candidate.length <= DISCOVERY_TXT_VALUE_MAX_CHARS &&
            candidate.none(Char::isWhitespace) &&
            candidate.none(Character::isISOControl) &&
            !candidate.containsForbiddenDiscoveryMaterial()
    }
}

private fun Map<String, ByteArray>.displayTxtValueOrNull(key: String): String? {
    val value = this[key]
        ?.decodeDiscoveryTxtStringOrNull()
        ?.trim()
        ?: return null
    return value.takeIf { candidate ->
        candidate.isNotEmpty() &&
            candidate.length <= DISCOVERY_TXT_VALUE_MAX_CHARS &&
            candidate.none(Character::isISOControl) &&
            !candidate.containsForbiddenDiscoveryMaterial()
    }
}

private fun Map<String, ByteArray>.containsForbiddenDiscoveryTxtAttribute(): Boolean {
    return any { (key, value) ->
        key.containsForbiddenDiscoveryMaterial() ||
            value.decodeDiscoveryTxtStringOrNull()?.containsForbiddenDiscoveryMaterial() != false
    }
}

private fun ByteArray.decodeDiscoveryTxtStringOrNull(): String? {
    val value = toString(StandardCharsets.UTF_8)
    return value.takeUnless { REPLACEMENT_CHARACTER in it }
}

private fun String.containsForbiddenDiscoveryMaterial(): Boolean {
    val normalized = lowercase()
    return FORBIDDEN_DISCOVERY_TXT_FRAGMENTS.any { fragment -> fragment in normalized }
}

private const val DISCOVERY_TXT_VALUE_MAX_CHARS = 160
private const val REPLACEMENT_CHARACTER = '\uFFFD'
private val FORBIDDEN_DISCOVERY_TXT_FRAGMENTS = listOf(
    "http://",
    "https://",
    "ws://",
    "wss://",
    ":11434",
    ":1234",
    "/" + "api/",
    "/" + "v1/",
    "ollama",
    "lm studio",
    "backend_url",
    "backend-url",
    "provider_url",
    "provider-url",
    "requested_route_token",
    "route_secret",
    "route-secret",
    "relay_secret",
    "relay-secret",
    "pairing_secret",
    "pairing-secret",
    "api_key",
    "api-key",
    "authorization",
    "bearer ",
    "models.list",
    "models.pull",
    "chat.send",
    "chat.cancel",
    "memory.",
    "prompt=",
    "response=",
    "file=",
)
