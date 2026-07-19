package com.localagentbridge.android.runtime

import com.localagentbridge.android.core.pairing.RuntimePairingPayload
import com.localagentbridge.android.core.pairing.OPAQUE_ROUTE_BODY_MAX_CHARS
import com.localagentbridge.android.core.pairing.isAllowedRemoteRelayScope
import com.localagentbridge.android.core.pairing.isCanonicalRelayHostValue
import com.localagentbridge.android.core.pairing.isCanonicalOpaqueRouteValue
import com.localagentbridge.android.core.pairing.isEligibleRemoteRelayHost
import com.localagentbridge.android.core.transport.PairedRuntimeIdentity
import com.localagentbridge.android.core.transport.PreparedRemoteRuntimeRoute
import com.localagentbridge.android.core.transport.RuntimePeerToPeerRoutePreparation
import com.localagentbridge.android.core.transport.RuntimePeerToPeerRoutePreparer
import com.localagentbridge.android.core.transport.RuntimeRelayRoutePreparation
import com.localagentbridge.android.core.transport.RuntimeRelayRoutePreparer
import com.localagentbridge.android.core.transport.RuntimeRemoteRoutePreparer

internal class RuntimeRemoteRoutePlanner(
    private val pendingPairingPayload: () -> RuntimePairingPayload?,
    private val trustedRuntime: () -> RuntimeTrustedRuntime?,
    private val nowEpochMillis: () -> Long = { System.currentTimeMillis() },
    private val allowDebugUsbReverseRoutes: Boolean = false,
) : RuntimeRemoteRoutePreparer {
    private val peerToPeerRoutePreparer = RuntimePeerToPeerRoutePreparer(
        routePreparationsForIdentity = { identity -> peerToPeerRoutePreparations(identity) },
        nowEpochMillis = nowEpochMillis,
    )
    private val relayRoutePreparer = RuntimeRelayRoutePreparer(
        routePreparationsForIdentity = { identity -> relayRoutePreparations(identity) },
        nowEpochMillis = nowEpochMillis,
    )

    override fun prepareRemoteRoutes(identity: PairedRuntimeIdentity): List<PreparedRemoteRuntimeRoute> {
        return peerToPeerRoutePreparer.prepareRemoteRoutes(identity) +
            relayRoutePreparer.prepareRemoteRoutes(identity)
    }

    private fun peerToPeerRoutePreparations(identity: PairedRuntimeIdentity): List<RuntimePeerToPeerRoutePreparation> {
        pendingPairingPayload()
            ?.takeIf { it.matchesIdentity(identity) }
            ?.let { payload ->
                return payload.toPeerToPeerRoutePreparation(nowEpochMillis())?.let(::listOf) ?: emptyList()
            }
        val preparation = trustedRuntime()
            ?.takeIf { it.matchesIdentity(identity) }
            ?.toPeerToPeerRoutePreparation(nowEpochMillis())
            ?: return emptyList()
        return listOf(preparation)
    }

    private fun relayRoutePreparations(identity: PairedRuntimeIdentity): List<RuntimeRelayRoutePreparation> {
        pendingPairingPayload()
            ?.takeIf { it.matchesIdentity(identity) }
            ?.let { payload ->
                return payload.toRelayRoutePreparation(
                    nowEpochMillis = nowEpochMillis(),
                    allowDebugUsbReverseRoutes = allowDebugUsbReverseRoutes,
                )?.let(::listOf) ?: emptyList()
            }
        val preparation = trustedRuntime()
            ?.takeIf { it.matchesIdentity(identity) }
            ?.toRelayRoutePreparation(
                nowEpochMillis = nowEpochMillis(),
                allowDebugUsbReverseRoutes = allowDebugUsbReverseRoutes,
            )
            ?: return emptyList()
        return listOf(preparation)
    }
}

internal fun RuntimeTrustedRuntime?.hasRelayRoute(
    nowEpochMillis: Long = System.currentTimeMillis(),
): Boolean {
    val host = this?.relayHost?.takeIf { it.isNotBlank() } ?: return false
    val expiresAt = relayExpiresAtEpochMillis
    return isCanonicalRelayHostValue(host) &&
        isAllowedRemoteRelayScope(relayScope) &&
        (isEligibleRemoteRelayHost(host, relayScope) || isDebugUsbReverseRelayRoute(host, relayScope)) &&
        relayPort != null &&
        relayPort in 1..65535 &&
        isCanonicalOpaqueRouteValue(relayId) &&
        isCanonicalOpaqueRouteValue(relaySecret) &&
        expiresAt != null &&
        expiresAt > nowEpochMillis &&
        isCanonicalOpaqueRouteValue(relayNonce)
}

internal fun RuntimeTrustedRuntime?.hasPeerToPeerRoute(
    nowEpochMillis: Long = System.currentTimeMillis(),
): Boolean {
    val runtime = this ?: return false
    val expiresAt = runtime.p2pExpiresAtEpochMillis
    return runtime.hasCompletePeerToPeerRoute() &&
        expiresAt != null &&
        expiresAt > nowEpochMillis
}

internal fun RuntimeTrustedRuntime?.hasRemoteRoute(
    nowEpochMillis: Long = System.currentTimeMillis(),
): Boolean {
    return hasPeerToPeerRoute(nowEpochMillis) || hasRelayRoute(nowEpochMillis)
}

internal fun RuntimeTrustedRuntime?.activeRemoteRouteLeaseExpiresAtEpochMillis(
    nowEpochMillis: Long = System.currentTimeMillis(),
): Long? {
    val runtime = this ?: return null
    return listOfNotNull(
        runtime.relayExpiresAtEpochMillis?.takeIf { runtime.hasRelayRoute(nowEpochMillis) },
        runtime.p2pExpiresAtEpochMillis?.takeIf { runtime.hasPeerToPeerRoute(nowEpochMillis) },
    ).minOrNull()
}

internal fun RuntimeTrustedRuntime?.retryableRemoteRouteLeaseExpiresAtEpochMillis(
    nowEpochMillis: Long = System.currentTimeMillis(),
    minimumDelayMillis: Long = ROUTE_REFRESH_LEASE_MIN_DELAY_MS,
): Long? {
    val runtime = this ?: return null
    return listOfNotNull(
        runtime.relayExpiresAtEpochMillis?.takeIf {
            runtime.hasRelayRoute(nowEpochMillis) && it - nowEpochMillis > minimumDelayMillis
        },
        runtime.p2pExpiresAtEpochMillis?.takeIf {
            runtime.hasPeerToPeerRoute(nowEpochMillis) && it - nowEpochMillis > minimumDelayMillis
        },
    ).minOrNull()
}

internal fun RuntimeTrustedRuntime?.hasCompleteRemoteRouteMaterial(): Boolean {
    val runtime = this ?: return false
    return runtime.hasCompletePeerToPeerRoute() || runtime.hasCompleteRelayRoute()
}

internal fun RuntimeTrustedRuntime?.hasExpiredRelayRoute(
    nowEpochMillis: Long = System.currentTimeMillis(),
): Boolean {
    val runtime = this ?: return false
    val expiresAt = runtime.relayExpiresAtEpochMillis ?: return false
    return runtime.hasCompleteRelayRoute() && expiresAt <= nowEpochMillis
}

internal fun RuntimeTrustedRuntime?.hasExpiredPeerToPeerRoute(
    nowEpochMillis: Long = System.currentTimeMillis(),
): Boolean {
    val runtime = this ?: return false
    val expiresAt = runtime.p2pExpiresAtEpochMillis ?: return false
    return runtime.hasCompletePeerToPeerRoute() && expiresAt <= nowEpochMillis
}

internal fun RuntimeTrustedRuntime?.hasExpiredRemoteRoute(
    nowEpochMillis: Long = System.currentTimeMillis(),
): Boolean {
    return hasExpiredPeerToPeerRoute(nowEpochMillis) || hasExpiredRelayRoute(nowEpochMillis)
}

internal fun RuntimePairingPayload.hasRelayRoute(
    nowEpochMillis: Long = System.currentTimeMillis(),
): Boolean {
    val expiresAt = relayExpiresAtEpochMillis
    val host = relayHost?.takeIf { it.isNotBlank() } ?: return false
    return isCanonicalRelayHostValue(host) &&
        isAllowedRemoteRelayScope(relayScope) &&
        (isEligibleRemoteRelayHost(host, relayScope) || isDebugUsbReverseRelayRoute(host, relayScope)) &&
        relayPort != null &&
        relayPort in 1..65535 &&
        isCanonicalOpaqueRouteValue(relayId) &&
        isCanonicalOpaqueRouteValue(relaySecret) &&
        expiresAt != null &&
        expiresAt > nowEpochMillis &&
        isCanonicalOpaqueRouteValue(relayNonce)
}

internal fun RuntimePairingPayload.hasRemoteRoute(
    nowEpochMillis: Long = System.currentTimeMillis(),
): Boolean {
    return hasPeerToPeerRoute(nowEpochMillis) || hasRelayRoute(nowEpochMillis)
}

internal fun RuntimePairingPayload.hasAnyRelayRouteMaterial(): Boolean {
    return !relayHost.isNullOrBlank() ||
        relayPort != null ||
        !relayId.isNullOrBlank() ||
        !relaySecret.isNullOrBlank() ||
        relayExpiresAtEpochMillis != null ||
        !relayNonce.isNullOrBlank()
}

internal fun RuntimePairingPayload.hasAnyPeerToPeerRouteMaterial(): Boolean {
    return !p2pRouteClass.isNullOrBlank() ||
        !p2pRecordId.isNullOrBlank() ||
        !p2pEncryptedBody.isNullOrBlank() ||
        p2pExpiresAtEpochMillis != null ||
        !p2pAntiReplayNonce.isNullOrBlank() ||
        p2pProtocolVersion != null
}

private fun RuntimeTrustedRuntime.hasCompleteRelayRoute(): Boolean {
    val expiresAt = relayExpiresAtEpochMillis
    val host = relayHost?.takeIf { it.isNotBlank() } ?: return false
    return isCanonicalRelayHostValue(host) &&
        isAllowedRemoteRelayScope(relayScope) &&
        (isEligibleRemoteRelayHost(host, relayScope) || isDebugUsbReverseRelayRoute(host, relayScope)) &&
        relayPort != null &&
        relayPort in 1..65535 &&
        isCanonicalOpaqueRouteValue(relayId) &&
        isCanonicalOpaqueRouteValue(relaySecret) &&
        expiresAt != null &&
        expiresAt > 0L &&
        isCanonicalOpaqueRouteValue(relayNonce)
}

private fun RuntimeTrustedRuntime.hasCompletePeerToPeerRoute(): Boolean {
    val expiresAt = p2pExpiresAtEpochMillis
    return p2pRouteClass == "p2p_rendezvous" &&
        isCanonicalOpaqueRouteValue(p2pRecordId) &&
        isCanonicalOpaqueRouteValue(p2pEncryptedBody, maxChars = OPAQUE_ROUTE_BODY_MAX_CHARS) &&
        expiresAt != null &&
        expiresAt > 0L &&
        isCanonicalOpaqueRouteValue(p2pAntiReplayNonce) &&
        p2pProtocolVersion == 1
}

private fun isDebugUsbReverseRelayRoute(host: String, relayScope: String?): Boolean {
    if (relayScope != "usb_reverse") return false
    if (!isCanonicalRelayHostValue(host)) return false
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
    val relayExpired = relayExpiresAtEpochMillis?.let { it <= nowEpochMillis } == true
    val p2pExpired = p2pExpiresAtEpochMillis?.let { expiresAt ->
        p2pRouteClass == "p2p_rendezvous" &&
            isCanonicalOpaqueRouteValue(p2pRecordId) &&
            isCanonicalOpaqueRouteValue(p2pEncryptedBody, maxChars = OPAQUE_ROUTE_BODY_MAX_CHARS) &&
            isCanonicalOpaqueRouteValue(p2pAntiReplayNonce) &&
            p2pProtocolVersion == 1 &&
            expiresAt <= nowEpochMillis
    } == true
    return relayExpired || p2pExpired
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

private fun RuntimePairingPayload.toRelayRoutePreparation(
    nowEpochMillis: Long,
    allowDebugUsbReverseRoutes: Boolean,
): RuntimeRelayRoutePreparation? {
    if (!hasRelayRoute(nowEpochMillis)) return null
    if (relayScope == "usb_reverse" && !allowDebugUsbReverseRoutes) {
        return null
    }
    return RuntimeRelayRoutePreparation(
        host = relayHost,
        port = relayPort,
        relayId = relayId,
        relayFrameSecret = relaySecret,
        expiresAtEpochMillis = relayExpiresAtEpochMillis,
        antiReplayNonce = relayNonce,
        relayScope = relayScope,
        ticketGeneration = null,
    )
}

private fun RuntimePairingPayload.toPeerToPeerRoutePreparation(nowEpochMillis: Long): RuntimePeerToPeerRoutePreparation? {
    if (!hasPeerToPeerRoute(nowEpochMillis)) return null
    return RuntimePeerToPeerRoutePreparation(
        recordId = p2pRecordId,
        encryptedCandidateMaterial = p2pEncryptedBody,
        expiresAtEpochMillis = p2pExpiresAtEpochMillis,
        antiReplayNonce = p2pAntiReplayNonce,
        protocolVersion = p2pProtocolVersion,
    )
}

internal fun RuntimePairingPayload.hasPeerToPeerRoute(
    nowEpochMillis: Long = System.currentTimeMillis(),
): Boolean {
    val expiresAt = p2pExpiresAtEpochMillis
    return p2pRouteClass == "p2p_rendezvous" &&
        isCanonicalOpaqueRouteValue(p2pRecordId) &&
        isCanonicalOpaqueRouteValue(p2pEncryptedBody, maxChars = OPAQUE_ROUTE_BODY_MAX_CHARS) &&
        expiresAt != null &&
        expiresAt > nowEpochMillis &&
        isCanonicalOpaqueRouteValue(p2pAntiReplayNonce) &&
        p2pProtocolVersion == 1
}

private fun RuntimeTrustedRuntime.toRelayRoutePreparation(
    nowEpochMillis: Long,
    allowDebugUsbReverseRoutes: Boolean,
): RuntimeRelayRoutePreparation? {
    if (!hasRelayRoute(nowEpochMillis)) return null
    if (relayScope == "usb_reverse" && !allowDebugUsbReverseRoutes) {
        return null
    }
    return RuntimeRelayRoutePreparation(
        host = relayHost,
        port = relayPort,
        relayId = relayId,
        relayFrameSecret = relaySecret,
        expiresAtEpochMillis = relayExpiresAtEpochMillis,
        antiReplayNonce = relayNonce,
        relayScope = relayScope,
        ticketGeneration = relayTicketGeneration,
    )
}

private fun RuntimeTrustedRuntime.toPeerToPeerRoutePreparation(nowEpochMillis: Long): RuntimePeerToPeerRoutePreparation? {
    if (!hasPeerToPeerRoute(nowEpochMillis)) return null
    return RuntimePeerToPeerRoutePreparation(
        recordId = p2pRecordId,
        encryptedCandidateMaterial = p2pEncryptedBody,
        expiresAtEpochMillis = p2pExpiresAtEpochMillis,
        antiReplayNonce = p2pAntiReplayNonce,
        protocolVersion = p2pProtocolVersion,
    )
}
