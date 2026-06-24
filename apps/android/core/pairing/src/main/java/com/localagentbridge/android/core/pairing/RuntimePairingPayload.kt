package com.localagentbridge.android.core.pairing

import java.net.URI
import java.net.URLDecoder
import java.nio.charset.StandardCharsets

data class RuntimePairingPayload(
    val pairingNonce: String,
    val pairingCode: String,
    val runtimeDeviceId: String,
    val runtimeName: String,
    val fingerprint: String,
    val runtimePublicKeyBase64: String?,
    val routeToken: String?,
    val host: String?,
    val port: Int?,
    val relayHost: String? = null,
    val relayPort: Int? = null,
    val relayId: String? = null,
    val relaySecret: String? = null,
    val relayExpiresAtEpochMillis: Long? = null,
    val relayNonce: String? = null,
    val serviceType: String?,
)

object RuntimePairingPayloadParser {
    fun parse(rawValue: String): RuntimePairingPayload {
        val uri = URI(rawValue.trim())
        val scheme = uri.scheme?.lowercase()
        require(scheme == "aetherlink" || scheme == "lab") {
            "Unsupported pairing QR scheme"
        }

        val action = uri.host ?: uri.path.trim('/')
        require(action == "pair") {
            "Unsupported pairing QR action"
        }

        val query = parseQuery(uri.rawQuery)
        val pairingNonce = query["pairing_nonce"] ?: query["nonce"]
        val pairingCode = query["pairing_code"] ?: query["code"]
        val runtimeDeviceId = query["runtime_device_id"] ?: query["mac_device_id"] ?: query["device_id"]
        val runtimeName = (query["runtime_name"] ?: query["mac_name"] ?: query["name"] ?: "AetherLink Runtime")
            .decodeLegacyNamePlus()
        val fingerprint = query["runtime_key_fingerprint"] ?: query["fingerprint"] ?: query["cert_fingerprint"]
        val runtimePublicKeyBase64 = query["runtime_public_key"] ?: query["mac_public_key"]
        val routeToken = query["route_token"] ?: query["discovery_token"]
        val host = (query["host"] ?: query["runtime_host"])?.takeIf { it.isNotBlank() }
        val rawPort = (query["port"] ?: query["runtime_port"])?.takeIf { it.isNotBlank() }
        val port = rawPort?.toIntOrNull()
        val relayHost = (query["relay_host"] ?: query["rendezvous_host"])?.takeIf { it.isNotBlank() }
        val rawRelayPort = (query["relay_port"] ?: query["rendezvous_port"])?.takeIf { it.isNotBlank() }
        val relayPort = rawRelayPort?.toIntOrNull()
        val explicitRelayId = (query["relay_id"] ?: query["network_id"])?.takeIf { it.isNotBlank() }
        val relayId = (explicitRelayId ?: routeToken)?.takeIf { it.isNotBlank() }
        val relaySecret = query["relay_secret"]?.takeIf { it.isNotBlank() }
        val rawRelayExpiresAt = query["relay_expires_at"] ?: query["rendezvous_expires_at"]
        val relayExpiresAtEpochMillis = rawRelayExpiresAt
            ?.takeIf { it.isNotBlank() }
            ?.toLongOrNull()
        val rawRelayNonce = query["relay_nonce"] ?: query["rendezvous_nonce"]
        val relayNonce = rawRelayNonce?.takeIf { it.isNotBlank() }
        val hasExplicitRelayField =
            relayHost != null ||
                rawRelayPort != null ||
                explicitRelayId != null ||
                relaySecret != null ||
                rawRelayExpiresAt != null ||
                rawRelayNonce != null

        require(!pairingNonce.isNullOrBlank()) { "Missing pairing nonce" }
        require(!pairingCode.isNullOrBlank()) { "Missing pairing code" }
        require(pairingCode.matches(Regex("\\d{6}"))) { "Invalid pairing code" }
        require(!runtimeDeviceId.isNullOrBlank()) { "Missing runtime device id" }
        require(!fingerprint.isNullOrBlank()) { "Missing runtime fingerprint" }
        if (host != null || rawPort != null) {
            require(host != null) { "Missing runtime host" }
            require(port != null && port in 1..65535) { "Invalid runtime port" }
        }
        if (hasExplicitRelayField) {
            require(relayHost != null) { "Missing relay host" }
            require(relayPort != null && relayPort in 1..65535) { "Invalid relay port" }
            require(!relayId.isNullOrBlank()) { "Missing relay id" }
            if (rawRelayExpiresAt != null) {
                require(relayExpiresAtEpochMillis != null && relayExpiresAtEpochMillis > 0L) {
                    "Invalid relay expiration"
                }
            }
            if (rawRelayNonce != null) {
                require(!relayNonce.isNullOrBlank()) { "Invalid relay nonce" }
            }
        }

        return RuntimePairingPayload(
            pairingNonce = pairingNonce,
            pairingCode = pairingCode,
            runtimeDeviceId = runtimeDeviceId,
            runtimeName = runtimeName,
            fingerprint = fingerprint,
            runtimePublicKeyBase64 = runtimePublicKeyBase64?.takeIf { it.isNotBlank() },
            routeToken = routeToken?.takeIf { it.isNotBlank() },
            host = host,
            port = port,
            relayHost = relayHost,
            relayPort = relayPort,
            relayId = relayId,
            relaySecret = relaySecret,
            relayExpiresAtEpochMillis = relayExpiresAtEpochMillis,
            relayNonce = relayNonce,
            serviceType = query["service_type"],
        )
    }

    private fun parseQuery(rawQuery: String?): Map<String, String> {
        if (rawQuery.isNullOrBlank()) return emptyMap()
        return rawQuery
            .split("&")
            .mapNotNull { part ->
                if (part.isBlank()) return@mapNotNull null
                val separator = part.indexOf('=')
                val rawKey = if (separator >= 0) part.substring(0, separator) else part
                val rawValue = if (separator >= 0) part.substring(separator + 1) else ""
                val key = rawKey.uriQueryDecode()
                val value = rawValue.uriQueryDecode()
                key to value
            }
            .toMap()
    }

    private fun String.uriQueryDecode(): String =
        URLDecoder.decode(replace("+", "%2B"), StandardCharsets.UTF_8.name())

    private fun String.decodeLegacyNamePlus(): String =
        replace('+', ' ')
}
