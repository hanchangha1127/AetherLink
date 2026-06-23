package com.localagentbridge.android.core.pairing

import java.net.URI
import java.net.URLDecoder
import java.nio.charset.StandardCharsets

data class MacPairingPayload(
    val pairingNonce: String,
    val pairingCode: String,
    val macDeviceId: String,
    val macName: String,
    val fingerprint: String,
    val host: String,
    val port: Int,
    val serviceType: String?,
)

object MacPairingPayloadParser {
    fun parse(rawValue: String): MacPairingPayload {
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
        val macDeviceId = query["mac_device_id"] ?: query["device_id"]
        val macName = query["mac_name"] ?: query["name"] ?: "AetherLink Mac"
        val fingerprint = query["fingerprint"] ?: query["cert_fingerprint"]
        val host = query["host"] ?: query["runtime_host"]
        val port = (query["port"] ?: query["runtime_port"])?.toIntOrNull()

        require(!pairingNonce.isNullOrBlank()) { "Missing pairing nonce" }
        require(!pairingCode.isNullOrBlank()) { "Missing pairing code" }
        require(pairingCode.matches(Regex("\\d{6}"))) { "Invalid pairing code" }
        require(!macDeviceId.isNullOrBlank()) { "Missing Mac device id" }
        require(!fingerprint.isNullOrBlank()) { "Missing Mac fingerprint" }
        require(!host.isNullOrBlank()) { "Missing Mac runtime host" }
        require(port != null && port in 1..65535) { "Invalid Mac runtime port" }

        return MacPairingPayload(
            pairingNonce = pairingNonce,
            pairingCode = pairingCode,
            macDeviceId = macDeviceId,
            macName = macName,
            fingerprint = fingerprint,
            host = host,
            port = port,
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
                val key = rawKey.urlDecode()
                val value = rawValue.urlDecode()
                key to value
            }
            .toMap()
    }

    private fun String.urlDecode(): String =
        URLDecoder.decode(this, StandardCharsets.UTF_8.name())
}
