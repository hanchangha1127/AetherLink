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
    val p2pRouteClass: String? = null,
    val p2pRecordId: String? = null,
    val p2pEncryptedBody: String? = null,
    val p2pExpiresAtEpochMillis: Long? = null,
    val p2pAntiReplayNonce: String? = null,
    val p2pProtocolVersion: Int? = null,
    val serviceType: String?,
)

object RuntimePairingPayloadParser {
    fun parse(
        rawValue: String,
        allowDebugLoopbackRelay: Boolean = false,
        allowDiagnosticLocalDirectEndpoint: Boolean = false,
    ): RuntimePairingPayload {
        require(rawValue.length <= MAX_PAIRING_QR_RAW_CHARS) {
            "Pairing QR payload is too large"
        }
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
        query.requireSingleSemanticAliasPerField()
        query.requireSingleRelayAliasFamily()
        query.requireSingleP2pAliasFamily()
        val version = query["version"] ?: query["v"]
        val pairingNonce = (query["pairing_nonce"] ?: query["nonce"] ?: query["n"])
            .requiredOpaqueQrValue("Missing pairing nonce", "Invalid pairing nonce")
        val pairingCode = query["pairing_code"] ?: query["code"] ?: query["c"]
        val runtimeDeviceId = (query["runtime_device_id"] ?: query["mac_device_id"] ?: query["device_id"] ?: query["rid"])
            .requiredOpaqueQrValue("Missing runtime device id", "Invalid runtime device id")
        val runtimeName = (query["runtime_name"] ?: query["mac_name"] ?: query["name"] ?: query["rn"])
            .normalizedRuntimeName()
        val fingerprint = (query["runtime_key_fingerprint"] ?: query["fingerprint"] ?: query["cert_fingerprint"] ?: query["rf"])
            .requiredOpaqueQrValue("Missing runtime fingerprint", "Invalid runtime fingerprint")
        val runtimePublicKeyBase64 = (query["runtime_public_key"] ?: query["mac_public_key"] ?: query["public_key"] ?: query["rk"])
            .optionalOpaqueQrValue("Invalid runtime public key")
        val routeToken = (query["route_token"] ?: query["discovery_token"] ?: query["rt"])
            .optionalOpaqueQrValue("Invalid route token")
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
        val relayPort = rawRelayPort.optionalQrPortValue("Invalid relay port")
        val explicitRelayId = (
            query["relay_id"]
                ?: query["remote_id"]
                ?: query["route_id"]
                ?: query["rendezvous_id"]
                ?: query["network_id"]
                ?: query["ri"]
            ).optionalOpaqueQrValue("Invalid relay id")
        val relayId = explicitRelayId?.takeIf { it.isNotBlank() }
        val relaySecret = (
            query["relay_secret"]
                ?: query["remote_secret"]
                ?: query["route_secret"]
                ?: query["rendezvous_secret"]
                ?: query["rs"]
            ).optionalOpaqueQrValue("Invalid relay secret")
        val rawRelayExpiresAt = query["relay_expires_at"]
            ?: query["remote_expires_at"]
            ?: query["route_expires_at"]
            ?: query["rendezvous_expires_at"]
            ?: query["rx"]
        val relayExpiresAtEpochMillis = rawRelayExpiresAt
            .optionalRouteExpirationEpochMillis("Invalid relay expiration")
        val rawRelayNonce = query["relay_nonce"]
            ?: query["remote_nonce"]
            ?: query["route_nonce"]
            ?: query["rendezvous_nonce"]
            ?: query["rrn"]
        val relayNonce = rawRelayNonce.optionalOpaqueQrValue("Invalid relay nonce")
        val relayScope = (
            query["relay_scope"]
                ?: query["remote_scope"]
                ?: query["route_scope"]
                ?: query["rsc"]
            ).optionalOpaqueQrValue("Invalid relay scope")
        val p2pRouteClass = (query["p2p_class"] ?: query["pc"])
            .optionalOpaqueQrValue("Invalid P2P route class")
        val p2pRecordId = (query["p2p_record_id"] ?: query["prid"])
            .optionalOpaqueQrValue("Invalid P2P record id")
        val p2pEncryptedBody = (query["p2p_encrypted_body"] ?: query["peb"])
            .optionalOpaqueQrValue(
                "Invalid P2P encrypted body",
                maxChars = OPAQUE_ROUTE_BODY_MAX_CHARS,
            )
        val rawP2pExpiresAt = query["p2p_expires_at"] ?: query["px"]
        val p2pExpiresAtEpochMillis = rawP2pExpiresAt
            .optionalRouteExpirationEpochMillis("Invalid P2P expiration")
        val p2pAntiReplayNonce = (query["p2p_anti_replay_nonce"] ?: query["pn"])
            .optionalOpaqueQrValue("Invalid P2P anti-replay nonce")
        val rawP2pProtocolVersion = query["p2p_protocol_version"] ?: query["pv"]
        val p2pProtocolVersion = rawP2pProtocolVersion.optionalP2pProtocolVersion()
        val serviceType = query["service_type"].optionalDiscoveryServiceType()
        val hasExplicitRelayField =
            relayHost != null ||
                rawRelayPort != null ||
                explicitRelayId != null ||
                relaySecret != null ||
                rawRelayExpiresAt != null ||
                rawRelayNonce != null
        val hasExplicitP2pField =
            p2pRouteClass != null ||
                p2pRecordId != null ||
                p2pEncryptedBody != null ||
                rawP2pExpiresAt != null ||
                p2pAntiReplayNonce != null ||
                rawP2pProtocolVersion != null
        val hasExplicitRemoteRouteField = hasExplicitRelayField || hasExplicitP2pField

        require(version == "1" || (version == null && allowDiagnosticLocalDirectEndpoint)) {
            "Unsupported pairing QR version"
        }
        require(!pairingCode.isNullOrBlank()) { "Missing pairing code" }
        require(pairingCode.matches(Regex("\\d{6}"))) { "Invalid pairing code" }
        val hasDirectEndpointField = host != null || rawPort != null
        if (hasDirectEndpointField && !hasExplicitRemoteRouteField) {
            require(host != null) { "Missing local diagnostic route host" }
            require(port != null && port in 1..65535) { "Invalid runtime port" }
        }
        val keepDiagnosticDirectEndpoint =
            hasDirectEndpointField &&
                !hasExplicitRemoteRouteField &&
                allowDiagnosticLocalDirectEndpoint &&
                relayScope.isNullOrDiagnosticLocalDirectScope()
        if (hasDirectEndpointField && !hasExplicitRemoteRouteField && !keepDiagnosticDirectEndpoint) {
            throw IllegalArgumentException("Local direct endpoint QR routes are diagnostic-only")
        }
        if (relayScope != null && !hasExplicitRelayField && !keepDiagnosticDirectEndpoint) {
            throw IllegalArgumentException("Relay scope requires relay route material")
        }
        if (hasExplicitRelayField) {
            require(relayHost != null) { "Missing relay host" }
            require(isCanonicalRelayHostValue(relayHost)) { "Invalid relay host" }
            require(isAllowedRemoteRelayScope(relayScope)) { "Invalid relay scope" }
            if (relayHost.requiresPrivateOverlayRelayScope() && !relayScope.isPrivateOverlayScope()) {
                throw IllegalArgumentException(PRIVATE_OVERLAY_RELAY_SCOPE_REQUIRED_QR_ERROR)
            }
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
        if (hasExplicitP2pField) {
            require(p2pRouteClass == "p2p_rendezvous") { "Invalid P2P route class" }
            require(!p2pRecordId.isNullOrBlank()) { "Missing P2P record id" }
            require(!p2pEncryptedBody.isNullOrBlank()) { "Missing P2P encrypted body" }
            require(p2pExpiresAtEpochMillis != null && p2pExpiresAtEpochMillis > 0L) {
                "Invalid P2P expiration"
            }
            require(!p2pAntiReplayNonce.isNullOrBlank()) { "Invalid P2P anti-replay nonce" }
            require(p2pProtocolVersion == 1) { "Invalid P2P protocol version" }
        }

        return RuntimePairingPayload(
            pairingNonce = pairingNonce,
            pairingCode = pairingCode,
            runtimeDeviceId = runtimeDeviceId,
            runtimeName = runtimeName,
            fingerprint = fingerprint,
            runtimePublicKeyBase64 = runtimePublicKeyBase64,
            routeToken = routeToken,
            host = host.takeIf { keepDiagnosticDirectEndpoint },
            port = port.takeIf { keepDiagnosticDirectEndpoint },
            relayHost = relayHost,
            relayPort = relayPort,
            relayId = relayId,
            relaySecret = relaySecret,
            relayExpiresAtEpochMillis = relayExpiresAtEpochMillis,
            relayNonce = relayNonce,
            relayScope = relayScope,
            p2pRouteClass = p2pRouteClass,
            p2pRecordId = p2pRecordId,
            p2pEncryptedBody = p2pEncryptedBody,
            p2pExpiresAtEpochMillis = p2pExpiresAtEpochMillis,
            p2pAntiReplayNonce = p2pAntiReplayNonce,
            p2pProtocolVersion = p2pProtocolVersion,
            serviceType = serviceType,
        )
    }

    private fun parseQuery(rawQuery: String?): Map<String, String> {
        if (rawQuery.isNullOrBlank()) return emptyMap()
        require(rawQuery.length <= MAX_PAIRING_QR_RAW_CHARS) {
            "Pairing QR query is too large"
        }
        var segmentCount = 1
        rawQuery.forEach { character ->
            if (character == '&') {
                segmentCount += 1
                require(segmentCount <= MAX_PAIRING_QR_QUERY_SEGMENTS) {
                    "Pairing QR has too many query fields"
                }
            }
        }
        val query = linkedMapOf<String, String>()
        rawQuery
            .split("&")
            .forEach { part ->
                if (part.isBlank()) return@forEach
                val separator = part.indexOf('=')
                val rawKey = if (separator >= 0) part.substring(0, separator) else part
                val rawValue = if (separator >= 0) part.substring(separator + 1) else ""
                val key = rawKey.uriQueryDecode()
                val value = rawValue.uriQueryDecode()
                require(key in ALLOWED_PAIRING_QR_QUERY_KEYS) { "Unknown pairing QR query key" }
                require(!query.containsKey(key)) { "Duplicate pairing QR query key" }
                query[key] = value
            }
        return query
    }

    private fun Map<String, String>.requireSingleSemanticAliasPerField() {
        PAIRING_QR_SEMANTIC_ALIAS_GROUPS.values.forEach { fields ->
            require(fields.count(::containsKey) <= 1) { "Mixed pairing QR semantic alias fields" }
        }
    }

    private fun Map<String, String>.requireSingleRelayAliasFamily() {
        val activeFamilies = RELAY_ROUTE_ALIAS_FAMILIES.filter { (_, fields) ->
            fields.any(::containsKey)
        }
        require(activeFamilies.size <= 1) { "Mixed relay alias families" }
    }

    private fun Map<String, String>.requireSingleP2pAliasFamily() {
        val activeFamilies = P2P_ROUTE_ALIAS_FAMILIES.filter { (_, fields) ->
            fields.any(::containsKey)
        }
        require(activeFamilies.size <= 1) { "Mixed P2P alias families" }
    }

    private fun String.uriQueryDecode(): String =
        URLDecoder.decode(replace("+", "%2B"), StandardCharsets.UTF_8.name())

    private fun String.decodeLegacyNamePlus(): String =
        replace('+', ' ')

    private fun String?.requiredOpaqueQrValue(
        missingMessage: String,
        invalidMessage: String,
    ): String {
        val value = optionalOpaqueQrValue(invalidMessage)
        require(value != null) { missingMessage }
        return value
    }

    private fun String?.optionalOpaqueQrValue(
        invalidMessage: String,
        maxChars: Int = OPAQUE_ROUTE_VALUE_MAX_CHARS,
    ): String? {
        val value = this?.takeIf { it.isNotBlank() } ?: return null
        require(isCanonicalOpaqueRouteValue(value, maxChars = maxChars)) { invalidMessage }
        return value
    }

    private fun String?.optionalP2pProtocolVersion(): Int? {
        val value = this?.takeIf { it.isNotBlank() } ?: return null
        require(value == "1") { "Invalid P2P protocol version" }
        return 1
    }

    private fun String?.optionalQrPortValue(invalidMessage: String): Int? {
        val value = this?.takeIf { it.isNotBlank() } ?: return null
        require(value.matches(CANONICAL_QR_PORT_PATTERN)) { invalidMessage }
        return value.toIntOrNull()
    }

    private fun String?.optionalRouteExpirationEpochMillis(invalidMessage: String): Long? {
        val value = this?.takeIf { it.isNotBlank() } ?: return null
        require(value.matches(CANONICAL_ROUTE_EXPIRATION_PATTERN)) { invalidMessage }
        val parsed = value.toLongOrNull()
        require(parsed != null) { invalidMessage }
        return parsed.normalizeRouteExpirationEpochMillis()
    }

    private fun String?.normalizedRuntimeName(): String =
        this
            ?.decodeLegacyNamePlus()
            ?.trim()
            ?.replace(Regex("\\s+"), " ")
            ?.take(RUNTIME_NAME_MAX_CHARS)
            ?.takeIf { it.isNotBlank() }
            ?: DEFAULT_RUNTIME_NAME

    private fun String?.optionalDiscoveryServiceType(): String? {
        val value = this?.takeIf { it.isNotBlank() } ?: return null
        require(isAllowedDiscoveryServiceType(value)) { "Invalid service type" }
        return value
    }

    private fun isAllowedDiscoveryServiceType(value: String): Boolean =
        value.isNotBlank() &&
            value.length <= DISCOVERY_SERVICE_TYPE_MAX_CHARS &&
            value == value.trim() &&
            value.none(Char::isWhitespace) &&
            value in ALLOWED_DISCOVERY_SERVICE_TYPES

    private fun Long.normalizeRouteExpirationEpochMillis(): Long =
        if (this in 1 until MIN_REASONABLE_EPOCH_MILLIS) this * MILLIS_PER_SECOND else this

    private const val DEFAULT_RUNTIME_NAME = "AetherLink Runtime"
    private const val RUNTIME_NAME_MAX_CHARS = 80
    private const val DISCOVERY_SERVICE_TYPE_MAX_CHARS = 64
    private const val MILLIS_PER_SECOND = 1_000L
    private const val MIN_REASONABLE_EPOCH_MILLIS = 100_000_000_000L
    private val CANONICAL_QR_PORT_PATTERN = Regex("^([1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])$")
    private val CANONICAL_ROUTE_EXPIRATION_PATTERN = Regex("^[1-9][0-9]*$")
    private val ALLOWED_DISCOVERY_SERVICE_TYPES = setOf(
        "_aetherlink._tcp.",
        "_aetherlink._tcp.local.",
        "_localagentbridge._tcp.",
        "_localagentbridge._tcp.local.",
    )

    private val RELAY_ROUTE_ALIAS_FAMILIES = mapOf(
        "canonical" to setOf(
            "relay_host",
            "relay_port",
            "relay_id",
            "network_id",
            "relay_secret",
            "relay_expires_at",
            "relay_nonce",
        ),
        "remote" to setOf(
            "remote_host",
            "remote_port",
            "remote_id",
            "remote_secret",
            "remote_expires_at",
            "remote_nonce",
        ),
        "route" to setOf(
            "route_host",
            "route_port",
            "route_id",
            "route_secret",
            "route_expires_at",
            "route_nonce",
        ),
        "rendezvous" to setOf(
            "rendezvous_host",
            "rendezvous_port",
            "rendezvous_id",
            "rendezvous_secret",
            "rendezvous_expires_at",
            "rendezvous_nonce",
        ),
        "compact" to setOf(
            "rh",
            "rp",
            "ri",
            "rs",
            "rx",
            "rrn",
        ),
    )

    private val P2P_ROUTE_ALIAS_FAMILIES = mapOf(
        "canonical" to setOf(
            "p2p_class",
            "p2p_record_id",
            "p2p_encrypted_body",
            "p2p_expires_at",
            "p2p_anti_replay_nonce",
            "p2p_protocol_version",
        ),
        "compact" to setOf(
            "pc",
            "prid",
            "peb",
            "px",
            "pn",
            "pv",
        ),
    )

    private val PAIRING_QR_SEMANTIC_ALIAS_GROUPS =
        mapOf(
            "version" to setOf("version", "v"),
            "pairing_nonce" to setOf("pairing_nonce", "nonce", "n"),
            "pairing_code" to setOf("pairing_code", "code", "c"),
            "runtime_device_id" to setOf("runtime_device_id", "mac_device_id", "device_id", "rid"),
            "runtime_name" to setOf("runtime_name", "mac_name", "name", "rn"),
            "runtime_key_fingerprint" to setOf("runtime_key_fingerprint", "fingerprint", "cert_fingerprint", "rf"),
            "runtime_public_key" to setOf("runtime_public_key", "mac_public_key", "public_key", "rk"),
            "route_token" to setOf("route_token", "discovery_token", "rt"),
            "host" to setOf("host", "runtime_host", "h"),
            "port" to setOf("port", "runtime_port", "p"),
            "relay_id" to setOf("relay_id", "network_id"),
            "relay_scope" to setOf("relay_scope", "remote_scope", "route_scope", "rsc"),
        )

    private val ALLOWED_PAIRING_QR_QUERY_KEYS =
        setOf(
            "version",
            "v",
            "pairing_nonce",
            "nonce",
            "n",
            "pairing_code",
            "code",
            "c",
            "runtime_device_id",
            "mac_device_id",
            "device_id",
            "rid",
            "runtime_name",
            "mac_name",
            "name",
            "rn",
            "runtime_key_fingerprint",
            "fingerprint",
            "cert_fingerprint",
            "rf",
            "runtime_public_key",
            "mac_public_key",
            "public_key",
            "rk",
            "route_token",
            "discovery_token",
            "rt",
            "host",
            "runtime_host",
            "h",
            "port",
            "runtime_port",
            "p",
            "relay_scope",
            "remote_scope",
            "route_scope",
            "rsc",
            "service_type",
        ) +
            RELAY_ROUTE_ALIAS_FAMILIES.values.flatten() +
            P2P_ROUTE_ALIAS_FAMILIES.values.flatten()
}

const val OPAQUE_ROUTE_VALUE_MAX_CHARS = 512
const val OPAQUE_ROUTE_BODY_MAX_CHARS = 2048

fun isCanonicalOpaqueRouteValue(
    value: String?,
    maxChars: Int = OPAQUE_ROUTE_VALUE_MAX_CHARS,
): Boolean {
    return !value.isNullOrBlank() &&
        value.length <= maxChars &&
        value == value.trim() &&
        value.none(Char::isWhitespace)
}

fun isCanonicalRelayHostValue(host: String?): Boolean {
    val value = host ?: return false
    return value.isNotBlank() &&
        value.length <= MAX_RELAY_HOST_CHARS &&
        value == value.trim() &&
        value.none(Char::isWhitespace) &&
        !value.contains("://") &&
        value.none { char -> char == '/' || char == '?' || char == '#' || char == '@' } &&
        !value.normalizedRelayHost().isNonCanonicalNumericRelayHost()
}

fun isEligibleRemoteRelayHost(host: String, relayScope: String? = null): Boolean {
    if (!isCanonicalRelayHostValue(host)) return false
    val normalized = host.normalizedRelayHost()
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

private fun String.normalizedRelayHost(): String = trim()
    .removePrefix("[")
    .removeSuffix("]")
    .removeSuffix(".")
    .lowercase()

private fun String.isNonCanonicalNumericRelayHost(): Boolean =
    isNotEmpty() && all(Char::isDigit) && !contains('.')

fun isAllowedRemoteRelayScope(relayScope: String?): Boolean =
    relayScope == null || relayScope in ALLOWED_REMOTE_RELAY_SCOPES

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

private fun String.requiresPrivateOverlayRelayScope(): Boolean {
    val normalized = trim()
        .removePrefix("[")
        .removeSuffix("]")
        .removeSuffix(".")
        .lowercase()
    return normalized.isPrivateOverlayRelayLiteral()
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
    if (relayScope != DEBUG_USB_REVERSE_RELAY_SCOPE) return false
    if (!isCanonicalRelayHostValue(this)) return false
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
private const val MAX_RELAY_HOST_CHARS = 253
private const val MAX_PAIRING_QR_RAW_CHARS = 16_384
private const val MAX_PAIRING_QR_QUERY_SEGMENTS = 128
private const val PRIVATE_OVERLAY_RELAY_SCOPE_REQUIRED_QR_ERROR =
    "Private relay hosts require relay_scope=private_overlay"
private const val LOCAL_DIRECT_DIAGNOSTIC_SCOPE = "local_diagnostic"
private val ALLOWED_REMOTE_RELAY_SCOPES = setOf(
    "remote",
    PRIVATE_OVERLAY_RELAY_SCOPE,
    DEBUG_USB_REVERSE_RELAY_SCOPE,
)

private fun String?.isNullOrDiagnosticLocalDirectScope(): Boolean =
    this == null || this == LOCAL_DIRECT_DIAGNOSTIC_SCOPE

private fun String?.isPrivateOverlayScope(): Boolean =
    this == PRIVATE_OVERLAY_RELAY_SCOPE
