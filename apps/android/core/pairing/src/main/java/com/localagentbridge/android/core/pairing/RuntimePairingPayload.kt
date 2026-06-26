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
    val relayScope: String? = null,
    val serviceType: String?,
)

object RuntimePairingPayloadParser {
    fun parse(
        rawValue: String,
        allowDebugLoopbackRelay: Boolean = false,
        allowDiagnosticLocalDirectEndpoint: Boolean = false,
    ): RuntimePairingPayload {
        val uri = URI(rawValue.trim())
        val scheme = uri.scheme?.lowercase()
        require(scheme == "aetherlink" || scheme == "lab") {
            "Unsupported pairing QR scheme"
        }

        val action = uri.host?.lowercase()
        require(action == "pair") {
            "Unsupported pairing QR action"
        }

        val query = parseQuery(uri.rawQuery)
        val version = query["version"] ?: query["v"]
        val pairingNonce = query["pairing_nonce"] ?: query["nonce"] ?: query["n"]
        val pairingCode = query["pairing_code"] ?: query["code"] ?: query["c"]
        val runtimeDeviceId = query["runtime_device_id"] ?: query["mac_device_id"] ?: query["device_id"] ?: query["rid"]
        val runtimeName = (query["runtime_name"] ?: query["mac_name"] ?: query["name"] ?: query["rn"] ?: "AetherLink Runtime")
            .decodeLegacyNamePlus()
        val fingerprint = query["runtime_key_fingerprint"] ?: query["fingerprint"] ?: query["cert_fingerprint"] ?: query["rf"]
        val runtimePublicKeyBase64 = query["runtime_public_key"] ?: query["mac_public_key"] ?: query["public_key"] ?: query["rk"]
        val routeToken = query["route_token"] ?: query["discovery_token"] ?: query["rt"]
        val host = (query["host"] ?: query["runtime_host"] ?: query["h"])?.takeIf { it.isNotBlank() }
        val rawPort = (query["port"] ?: query["runtime_port"] ?: query["p"])?.takeIf { it.isNotBlank() }
        val port = rawPort?.toIntOrNull()
        val relayHost = (
            query["relay_host"]
                ?: query["remote_host"]
                ?: query["route_host"]
                ?: query["rendezvous_host"]
                ?: query["rh"]
            )?.takeIf { it.isNotBlank() }
        val rawRelayPort = (
            query["relay_port"]
                ?: query["remote_port"]
                ?: query["route_port"]
                ?: query["rendezvous_port"]
                ?: query["rp"]
            )?.takeIf { it.isNotBlank() }
        val relayPort = rawRelayPort?.toIntOrNull()
        val explicitRelayId = (
            query["relay_id"]
                ?: query["remote_id"]
                ?: query["route_id"]
                ?: query["rendezvous_id"]
                ?: query["network_id"]
                ?: query["ri"]
            )?.takeIf { it.isNotBlank() }
        val relayId = (explicitRelayId ?: routeToken)?.takeIf { it.isNotBlank() }
        val relaySecret = (
            query["relay_secret"]
                ?: query["remote_secret"]
                ?: query["route_secret"]
                ?: query["rendezvous_secret"]
                ?: query["rs"]
            )?.takeIf { it.isNotBlank() }
        val rawRelayExpiresAt = query["relay_expires_at"]
            ?: query["remote_expires_at"]
            ?: query["route_expires_at"]
            ?: query["rendezvous_expires_at"]
            ?: query["rx"]
        val relayExpiresAtEpochMillis = rawRelayExpiresAt
            ?.takeIf { it.isNotBlank() }
            ?.toLongOrNull()
            ?.normalizeRelayExpirationEpochMillis()
        val rawRelayNonce = query["relay_nonce"]
            ?: query["remote_nonce"]
            ?: query["route_nonce"]
            ?: query["rendezvous_nonce"]
            ?: query["rrn"]
        val relayNonce = rawRelayNonce?.takeIf { it.isNotBlank() }
        val relayScope = (
            query["relay_scope"]
                ?: query["remote_scope"]
                ?: query["route_scope"]
                ?: query["rsc"]
            )?.takeIf { it.isNotBlank() }
        val hasExplicitRelayField =
            relayHost != null ||
                rawRelayPort != null ||
                explicitRelayId != null ||
                relaySecret != null ||
                rawRelayExpiresAt != null ||
                rawRelayNonce != null

        require(version == "1") { "Unsupported pairing QR version" }
        require(!pairingNonce.isNullOrBlank()) { "Missing pairing nonce" }
        require(!pairingCode.isNullOrBlank()) { "Missing pairing code" }
        require(pairingCode.matches(Regex("\\d{6}"))) { "Invalid pairing code" }
        require(!runtimeDeviceId.isNullOrBlank()) { "Missing runtime device id" }
        require(!fingerprint.isNullOrBlank()) { "Missing runtime fingerprint" }
        val hasDirectEndpointField = host != null || rawPort != null
        if (hasDirectEndpointField && !hasExplicitRelayField) {
            require(host != null) { "Missing local diagnostic route host" }
            require(port != null && port in 1..65535) { "Invalid runtime port" }
        }
        val keepDiagnosticDirectEndpoint =
            hasDirectEndpointField &&
                !hasExplicitRelayField &&
                allowDiagnosticLocalDirectEndpoint &&
                relayScope.isDiagnosticLocalDirectScope()
        if (hasDirectEndpointField && !hasExplicitRelayField && !keepDiagnosticDirectEndpoint) {
            throw IllegalArgumentException("Local direct endpoint QR routes are diagnostic-only")
        }
        if (hasExplicitRelayField) {
            require(relayHost != null) { "Missing relay host" }
            require(
                isEligibleRemoteRelayHost(relayHost, relayScope) ||
                    relayHost.isAllowedDebugLoopbackRelay(relayScope, allowDebugLoopbackRelay)
            ) {
                "Relay host is not reachable for remote pairing"
            }
            require(relayPort != null && relayPort in 1..65535) { "Invalid relay port" }
            require(!relayId.isNullOrBlank()) { "Missing relay id" }
            require(relayId.none(Char::isWhitespace)) { "Invalid relay id" }
            require(!relaySecret.isNullOrBlank()) { "Missing relay secret" }
            require(relayExpiresAtEpochMillis != null && relayExpiresAtEpochMillis > 0L) {
                "Invalid relay expiration"
            }
            require(!relayNonce.isNullOrBlank()) { "Invalid relay nonce" }
        }

        return RuntimePairingPayload(
            pairingNonce = pairingNonce,
            pairingCode = pairingCode,
            runtimeDeviceId = runtimeDeviceId,
            runtimeName = runtimeName,
            fingerprint = fingerprint,
            runtimePublicKeyBase64 = runtimePublicKeyBase64?.takeIf { it.isNotBlank() },
            routeToken = routeToken?.takeIf { it.isNotBlank() },
            host = host.takeIf { keepDiagnosticDirectEndpoint },
            port = port.takeIf { keepDiagnosticDirectEndpoint },
            relayHost = relayHost,
            relayPort = relayPort,
            relayId = relayId,
            relaySecret = relaySecret,
            relayExpiresAtEpochMillis = relayExpiresAtEpochMillis,
            relayNonce = relayNonce,
            relayScope = relayScope,
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

    private fun Long.normalizeRelayExpirationEpochMillis(): Long =
        if (this in 1 until MIN_REASONABLE_EPOCH_MILLIS) this * MILLIS_PER_SECOND else this

    private const val MILLIS_PER_SECOND = 1_000L
    private const val MIN_REASONABLE_EPOCH_MILLIS = 100_000_000_000L
}

fun isEligibleRemoteRelayHost(host: String, relayScope: String? = null): Boolean {
    val normalized = host.trim()
        .removePrefix("[")
        .removeSuffix("]")
        .removeSuffix(".")
        .lowercase()
    if (normalized.isBlank()) return false
    if (normalized == "localhost" ||
        normalized == "::1" ||
        normalized == "0:0:0:0:0:0:0:1" ||
        normalized == "0.0.0.0" ||
        normalized == "::" ||
        normalized.startsWith("127.")
    ) {
        return false
    }
    if (normalized == "local" || normalized.endsWith(".local")) return false
    if (normalized.isPrivateOrLocalIpv4Literal() || normalized.isPrivateOrLocalIpv6Literal()) {
        return relayScope.isPrivateOverlayScope() && normalized.isPrivateOverlayRelayLiteral()
    }
    return true
}

private fun String.isPrivateOrLocalIpv4Literal(): Boolean {
    val octets = split('.')
    if (octets.size != 4) return false
    val values = octets.map { part ->
        if (part.isEmpty() || part.any { !it.isDigit() }) return false
        part.toIntOrNull()?.takeIf { it in 0..255 } ?: return false
    }
    val first = values[0]
    val second = values[1]
    return first == 0 ||
        first == 10 ||
        first == 127 ||
        first >= 224 ||
        (first == 100 && second in 64..127) ||
        (first == 169 && second == 254) ||
        (first == 172 && second in 16..31) ||
        (first == 192 && second == 168)
}

private fun String.isPrivateOrLocalIpv6Literal(): Boolean {
    if (!contains(':')) return false
    val normalized = trim()
        .removePrefix("[")
        .removeSuffix("]")
        .lowercase()
    return normalized == "::" ||
        normalized == "::1" ||
        normalized == "0:0:0:0:0:0:0:0" ||
        normalized == "0:0:0:0:0:0:0:1" ||
        normalized.startsWith("fe80:") ||
        normalized.startsWith("fc") ||
        normalized.startsWith("fd")
}

private fun String.isPrivateOverlayRelayLiteral(): Boolean {
    return isPrivateOverlayIpv4Literal() || isPrivateOverlayIpv6Literal()
}

private fun String.isPrivateOverlayIpv4Literal(): Boolean {
    val octets = split('.')
    if (octets.size != 4) return false
    val values = octets.map { part ->
        if (part.isEmpty() || part.any { !it.isDigit() }) return false
        part.toIntOrNull()?.takeIf { it in 0..255 } ?: return false
    }
    val first = values[0]
    val second = values[1]
    return first == 10 ||
        (first == 100 && second in 64..127) ||
        (first == 172 && second in 16..31) ||
        (first == 192 && second == 168)
}

private fun String.isPrivateOverlayIpv6Literal(): Boolean {
    if (!contains(':')) return false
    val normalized = trim()
        .removePrefix("[")
        .removeSuffix("]")
        .lowercase()
    return normalized.startsWith("fc") || normalized.startsWith("fd")
}

private fun String.isAllowedDebugLoopbackRelay(
    relayScope: String?,
    allowDebugLoopbackRelay: Boolean,
): Boolean {
    if (!allowDebugLoopbackRelay) return false
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
private const val PRIVATE_OVERLAY_RELAY_SCOPE = "private_overlay"
private const val LOCAL_DIRECT_DIAGNOSTIC_SCOPE = "local_diagnostic"

private fun String?.isDiagnosticLocalDirectScope(): Boolean =
    this?.trim()?.lowercase() == LOCAL_DIRECT_DIAGNOSTIC_SCOPE

private fun String?.isPrivateOverlayScope(): Boolean =
    this?.trim()?.lowercase() == PRIVATE_OVERLAY_RELAY_SCOPE
