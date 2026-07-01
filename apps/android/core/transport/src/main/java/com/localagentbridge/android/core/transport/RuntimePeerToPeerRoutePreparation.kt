package com.localagentbridge.android.core.transport

data class RuntimePeerToPeerRoutePreparation(
    val recordId: String?,
    val encryptedCandidateMaterial: String?,
    val expiresAtEpochMillis: Long? = null,
    val antiReplayNonce: String? = null,
    val protocolVersion: Int? = CURRENT_P2P_RENDEZVOUS_PROTOCOL_VERSION,
)

class RuntimePeerToPeerRoutePreparer(
    private val nowEpochMillis: () -> Long = { System.currentTimeMillis() },
    private val routePreparationsForIdentity: (PairedRuntimeIdentity) -> List<RuntimePeerToPeerRoutePreparation>,
) : RuntimeRemoteRoutePreparer {
    override fun prepareRemoteRoutes(identity: PairedRuntimeIdentity): List<PreparedRemoteRuntimeRoute> {
        return routePreparationsForIdentity(identity).mapNotNull { preparation ->
            preparation.toPreparedPeerToPeerRouteOrNull(identity, nowEpochMillis = nowEpochMillis())
        }
    }
}

fun RuntimePeerToPeerRoutePreparation.toPreparedPeerToPeerRouteOrNull(
    identity: PairedRuntimeIdentity,
    nowEpochMillis: Long = System.currentTimeMillis(),
): PreparedRemoteRuntimeRoute.PeerToPeer? {
    if (protocolVersion != CURRENT_P2P_RENDEZVOUS_PROTOCOL_VERSION) return null
    val routeRecordId = recordId.opaqueRouteRecordValueOrNull() ?: return null
    val candidateMaterial = encryptedCandidateMaterial.opaqueRouteRecordValueOrNull() ?: return null
    val expiresAt = expiresAtEpochMillis?.takeIf { it > nowEpochMillis } ?: return null
    val nonce = antiReplayNonce.opaqueRouteRecordValueOrNull() ?: return null
    return PreparedRemoteRuntimeRoute.PeerToPeer(
        identity = identity,
        sessionId = routeRecordId,
        encryptedCandidateMaterial = candidateMaterial,
        security = RemoteRouteSecurityContext(
            rendezvousToken = routeRecordId,
            expiresAtEpochMillis = expiresAt,
            antiReplayNonce = nonce,
        ),
    )
}

private fun String?.opaqueRouteRecordValueOrNull(): String? {
    val value = this ?: return null
    return value.takeIf {
        it.isNotEmpty() &&
            it == it.trim() &&
            it.none(Char::isWhitespace)
    }
}

const val CURRENT_P2P_RENDEZVOUS_PROTOCOL_VERSION = 1
