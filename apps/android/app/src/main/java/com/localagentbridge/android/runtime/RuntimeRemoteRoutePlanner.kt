package com.localagentbridge.android.runtime

import com.localagentbridge.android.core.pairing.RuntimePairingPayload
import com.localagentbridge.android.core.pairing.isAllowedRemoteRelayScope
import com.localagentbridge.android.core.pairing.isEligibleRemoteRelayHost
import com.localagentbridge.android.core.transport.PairedRuntimeIdentity
import com.localagentbridge.android.core.transport.PreparedRemoteRuntimeRoute
import com.localagentbridge.android.core.transport.RuntimeRelayRoutePreparation
import com.localagentbridge.android.core.transport.RuntimeRelayRoutePreparer
import com.localagentbridge.android.core.transport.RuntimeRemoteRoutePreparer

internal class RuntimeRemoteRoutePlanner(
    private val pendingPairingPayload: () -> RuntimePairingPayload?,
    private val trustedRuntime: () -> RuntimeTrustedRuntime?,
    private val nowEpochMillis: () -> Long = { System.currentTimeMillis() },
) : RuntimeRemoteRoutePreparer {
    private val relayRoutePreparer = RuntimeRelayRoutePreparer(
        routePreparationsForIdentity = { identity -> relayRoutePreparations(identity) },
        nowEpochMillis = nowEpochMillis,
    )

    override fun prepareRemoteRoutes(identity: PairedRuntimeIdentity): List<PreparedRemoteRuntimeRoute> {
        return relayRoutePreparer.prepareRemoteRoutes(identity)
    }

    private fun relayRoutePreparations(identity: PairedRuntimeIdentity): List<RuntimeRelayRoutePreparation> {
        pendingPairingPayload()
            ?.takeIf { it.matchesIdentity(identity) }
            ?.let { payload ->
                return payload.toRelayRoutePreparation(nowEpochMillis())?.let(::listOf) ?: emptyList()
            }
        val preparation = trustedRuntime()
            ?.takeIf { it.matchesIdentity(identity) }
            ?.toRelayRoutePreparation(nowEpochMillis())
            ?: return emptyList()
        return listOf(preparation)
    }
}

internal fun RuntimeTrustedRuntime?.hasRelayRoute(
    nowEpochMillis: Long = System.currentTimeMillis(),
): Boolean {
    val host = this?.relayHost?.takeIf { it.isNotBlank() } ?: return false
    val expiresAt = relayExpiresAtEpochMillis
    return isAllowedRemoteRelayScope(relayScope) &&
        (isEligibleRemoteRelayHost(host, relayScope) || isDebugUsbReverseRelayRoute(host, relayScope)) &&
        relayPort != null &&
        relayPort in 1..65535 &&
        !relayId.isNullOrBlank() &&
        !relaySecret.isNullOrBlank() &&
        expiresAt != null &&
        expiresAt > nowEpochMillis &&
        !relayNonce.isNullOrBlank()
}

internal fun RuntimeTrustedRuntime?.hasExpiredRelayRoute(
    nowEpochMillis: Long = System.currentTimeMillis(),
): Boolean {
    val runtime = this ?: return false
    val expiresAt = runtime.relayExpiresAtEpochMillis ?: return false
    return runtime.hasCompleteRelayRoute() && expiresAt <= nowEpochMillis
}

internal fun RuntimePairingPayload.hasRelayRoute(
    nowEpochMillis: Long = System.currentTimeMillis(),
): Boolean {
    val expiresAt = relayExpiresAtEpochMillis
    val host = relayHost?.takeIf { it.isNotBlank() } ?: return false
    return isAllowedRemoteRelayScope(relayScope) &&
        (isEligibleRemoteRelayHost(host, relayScope) || isDebugUsbReverseRelayRoute(host, relayScope)) &&
        relayPort != null &&
        relayPort in 1..65535 &&
        !relayId.isNullOrBlank() &&
        !relaySecret.isNullOrBlank() &&
        expiresAt != null &&
        expiresAt > nowEpochMillis &&
        !relayNonce.isNullOrBlank()
}

private fun RuntimeTrustedRuntime.hasCompleteRelayRoute(): Boolean {
    val expiresAt = relayExpiresAtEpochMillis
    val host = relayHost?.takeIf { it.isNotBlank() } ?: return false
    return isAllowedRemoteRelayScope(relayScope) &&
        (isEligibleRemoteRelayHost(host, relayScope) || isDebugUsbReverseRelayRoute(host, relayScope)) &&
        relayPort != null &&
        relayPort in 1..65535 &&
        !relayId.isNullOrBlank() &&
        !relaySecret.isNullOrBlank() &&
        expiresAt != null &&
        expiresAt > 0L &&
        !relayNonce.isNullOrBlank()
}

private fun isDebugUsbReverseRelayRoute(host: String, relayScope: String?): Boolean {
    if (relayScope != "usb_reverse") return false
    val normalizedHost = host.trim()
        .removePrefix("[")
        .removeSuffix("]")
        .removeSuffix(".")
        .lowercase()
    return normalizedHost == "localhost" ||
        normalizedHost == "::1" ||
        normalizedHost == "0:0:0:0:0:0:0:1" ||
        normalizedHost.startsWith("127.")
}

internal fun RuntimePairingPayload.hasExpiredRemoteRoute(
    nowEpochMillis: Long = System.currentTimeMillis(),
): Boolean {
    val expiresAt = relayExpiresAtEpochMillis ?: return false
    return expiresAt <= nowEpochMillis
}

internal fun RuntimePairingPayload.matchesIdentity(identity: PairedRuntimeIdentity): Boolean {
    return runtimeDeviceId == identity.deviceId &&
        fingerprint == identity.fingerprint &&
        runtimePublicKeyMatches(runtimePublicKeyBase64, identity.publicKeyBase64)
}

internal fun RuntimeTrustedRuntime.matchesIdentity(identity: PairedRuntimeIdentity): Boolean {
    return deviceId == identity.deviceId &&
        pinnedRuntimeIdentityFieldMatches(fingerprint, identity.fingerprint) &&
        pinnedRuntimeIdentityFieldMatches(publicKeyBase64, identity.publicKeyBase64)
}

private fun pinnedRuntimeIdentityFieldMatches(pinnedValue: String?, candidateValue: String?): Boolean {
    val normalizedPinned = pinnedValue?.trim()?.takeIf { it.isNotEmpty() } ?: return true
    val normalizedCandidate = candidateValue?.trim()?.takeIf { it.isNotEmpty() } ?: return false
    return normalizedPinned == normalizedCandidate
}

private fun RuntimePairingPayload.toRelayRoutePreparation(nowEpochMillis: Long): RuntimeRelayRoutePreparation? {
    if (!hasRelayRoute(nowEpochMillis)) return null
    return RuntimeRelayRoutePreparation(
        host = relayHost,
        port = relayPort,
        relayId = relayId,
        relayFrameSecret = relaySecret,
        expiresAtEpochMillis = relayExpiresAtEpochMillis,
        antiReplayNonce = relayNonce,
        relayScope = relayScope,
    )
}

private fun RuntimeTrustedRuntime.toRelayRoutePreparation(nowEpochMillis: Long): RuntimeRelayRoutePreparation? {
    if (!hasRelayRoute(nowEpochMillis)) return null
    return RuntimeRelayRoutePreparation(
        host = relayHost,
        port = relayPort,
        relayId = relayId,
        relayFrameSecret = relaySecret,
        routeTokenFallback = routeToken,
        expiresAtEpochMillis = relayExpiresAtEpochMillis,
        antiReplayNonce = relayNonce,
        relayScope = relayScope,
    )
}
