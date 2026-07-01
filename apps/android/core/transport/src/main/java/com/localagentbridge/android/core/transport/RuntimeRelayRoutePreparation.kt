package com.localagentbridge.android.core.transport

data class RuntimeRelayRoutePreparation(
    val host: String?,
    val port: Int?,
    val relayId: String?,
    val relayFrameSecret: String?,
    val expiresAtEpochMillis: Long? = null,
    val antiReplayNonce: String? = null,
    val relayScope: String? = null,
)

class RuntimeRelayRoutePreparer(
    private val nowEpochMillis: () -> Long = { System.currentTimeMillis() },
    private val routePreparationsForIdentity: (PairedRuntimeIdentity) -> List<RuntimeRelayRoutePreparation>,
) : RuntimeRemoteRoutePreparer {
    override fun prepareRemoteRoutes(identity: PairedRuntimeIdentity): List<PreparedRemoteRuntimeRoute> {
        return routePreparationsForIdentity(identity).mapNotNull { preparation ->
            preparation.toPreparedRelayRouteOrNull(identity, nowEpochMillis = nowEpochMillis())
        }
    }
}

fun RuntimeRelayRoutePreparation.toPreparedRelayRouteOrNull(
    identity: PairedRuntimeIdentity,
    nowEpochMillis: Long = System.currentTimeMillis(),
): PreparedRemoteRuntimeRoute.Relay? {
    val routeHost = host?.takeIf { it.isNotBlank() } ?: return null
    if (!relayScope.isAllowedPreparedRelayScope()) return null
    if (!routeHost.isAllowedPreparedRelayHost(relayScope)) return null
    val routePort = port?.takeIf { it in 1..65535 } ?: return null
    val routeRelayId = relayId?.takeIf { it.isNotBlank() }
        ?: return null
    val frameSecret = relayFrameSecret?.takeIf { it.isNotBlank() } ?: return null
    val expiresAt = expiresAtEpochMillis?.takeIf { it > nowEpochMillis } ?: return null
    val nonce = antiReplayNonce?.takeIf { it.isNotBlank() } ?: return null
    return PreparedRemoteRuntimeRoute.Relay(
        identity = identity,
        relayId = routeRelayId,
        host = routeHost,
        port = routePort,
        relayFrameSecret = frameSecret,
        security = RemoteRouteSecurityContext(
            rendezvousToken = routeRelayId,
            expiresAtEpochMillis = expiresAt,
            antiReplayNonce = nonce,
        ),
    )
}

private fun String.isAllowedPreparedRelayHost(relayScope: String?): Boolean {
    val normalized = trim()
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
        return relayScope.isDebugUsbReverseScope()
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

private fun String?.isPrivateOverlayScope(): Boolean =
    this == PRIVATE_OVERLAY_RELAY_SCOPE

private fun String?.isDebugUsbReverseScope(): Boolean =
    this == DEBUG_USB_REVERSE_RELAY_SCOPE

private fun String?.isAllowedPreparedRelayScope(): Boolean =
    this == null || this in ALLOWED_PREPARED_RELAY_SCOPES

private const val PRIVATE_OVERLAY_RELAY_SCOPE = "private_overlay"
private const val DEBUG_USB_REVERSE_RELAY_SCOPE = "usb_reverse"
private val ALLOWED_PREPARED_RELAY_SCOPES = setOf(
    "remote",
    PRIVATE_OVERLAY_RELAY_SCOPE,
    DEBUG_USB_REVERSE_RELAY_SCOPE,
)
