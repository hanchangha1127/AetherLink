package com.localagentbridge.android.core.transport

data class DiscoveredRuntime(
    val serviceName: String,
    val host: String,
    val port: Int,
    val routeToken: String? = null,
    val deviceId: String? = null,
    val fingerprint: String? = null,
    val app: String? = null,
    val version: String? = null,
)

sealed interface ConnectionState {
    data object Idle : ConnectionState
    data object Discovering : ConnectionState
    data class Discovered(val peers: List<DiscoveredRuntime>) : ConnectionState
    data class Connected(val peer: DiscoveredRuntime) : ConnectionState
    data class Failed(val message: String) : ConnectionState
}
