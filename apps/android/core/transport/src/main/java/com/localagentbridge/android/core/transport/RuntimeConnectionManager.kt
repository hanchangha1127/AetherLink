package com.localagentbridge.android.core.transport

data class RuntimeEndpointHint(
    val host: String,
    val port: Int,
    val source: RuntimeEndpointSource,
) {
    init {
        require(host.isNotBlank()) { "Endpoint host must not be blank" }
        require(port in 1..65535) { "Endpoint port must be in 1..65535" }
    }
}

enum class RuntimeEndpointSource {
    TrustedLastKnown,
    PairingQr,
    BonjourDiscovery,
    UsbReverse,
    Emulator,
    Manual,
}

data class PairedRuntimeIdentity(
    val deviceId: String,
    val name: String,
    val fingerprint: String? = null,
    val publicKeyBase64: String? = null,
    val routeToken: String? = null,
) {
    init {
        require(deviceId.isNotBlank()) { "Runtime device id must not be blank" }
        require(name.isNotBlank()) { "Runtime name must not be blank" }
        require(fingerprint?.isNotBlank() != false) { "Runtime fingerprint must not be blank" }
        require(publicKeyBase64?.isNotBlank() != false) { "Runtime public key must not be blank" }
        require(routeToken?.isNotBlank() != false) { "Runtime route token must not be blank" }
    }
}

data class RuntimeConnectionTarget(
    val identity: PairedRuntimeIdentity?,
    val endpointHint: RuntimeEndpointHint? = null,
) {
    val lastKnownEndpoint: RuntimeEndpointHint
        get() = requireNotNull(endpointHint) { "Runtime endpoint hint is not available" }
}

sealed class RuntimeRouteCandidate {
    abstract val source: RuntimeRouteSource
    abstract val capability: RuntimeRouteCapability

    data class DirectTcp(
        val hint: RuntimeEndpointHint,
        override val source: RuntimeRouteSource = RuntimeRouteSource.EndpointHint,
    ) : RuntimeRouteCandidate() {
        override val capability: RuntimeRouteCapability = RuntimeRouteCapability.DirectTcp
    }

    data class LocalDirect(
        val identity: PairedRuntimeIdentity,
        override val source: RuntimeRouteSource = RuntimeRouteSource.LocalDirectDiscovery,
    ) : RuntimeRouteCandidate() {
        override val capability: RuntimeRouteCapability = RuntimeRouteCapability.DirectTcp
    }

    data class PeerToPeer(
        val identity: PairedRuntimeIdentity,
        val preparedRoute: PreparedRemoteRuntimeRoute.PeerToPeer? = null,
        override val source: RuntimeRouteSource = RuntimeRouteSource.PeerToPeer,
    ) : RuntimeRouteCandidate() {
        override val capability: RuntimeRouteCapability = RuntimeRouteCapability.PeerToPeer
    }

    data class Relay(
        val identity: PairedRuntimeIdentity,
        val preparedRoute: PreparedRemoteRuntimeRoute.Relay? = null,
        override val source: RuntimeRouteSource = RuntimeRouteSource.Relay,
    ) : RuntimeRouteCandidate() {
        override val capability: RuntimeRouteCapability = RuntimeRouteCapability.Relay
    }

    companion object {
        @Suppress("FunctionName")
        fun Endpoint(
            hint: RuntimeEndpointHint,
            source: RuntimeRouteSource = RuntimeRouteSource.EndpointHint,
        ): DirectTcp = DirectTcp(hint = hint, source = source)
    }
}

enum class RuntimeRouteCapability {
    DirectTcp,
    PeerToPeer,
    Relay,
}

sealed class PreparedRemoteRuntimeRoute {
    abstract val identity: PairedRuntimeIdentity
    abstract val capability: RuntimeRouteCapability
    abstract val security: RemoteRouteSecurityContext

    data class PeerToPeer(
        override val identity: PairedRuntimeIdentity,
        val sessionId: String,
        val encryptedCandidateMaterial: String? = null,
        override val security: RemoteRouteSecurityContext,
    ) : PreparedRemoteRuntimeRoute() {
        init {
            require(sessionId.isNotBlank()) { "Peer-to-peer session id must not be blank" }
            require(encryptedCandidateMaterial?.isNotBlank() != false) {
                "Peer-to-peer encrypted candidate material must not be blank"
            }
        }

        override val capability: RuntimeRouteCapability = RuntimeRouteCapability.PeerToPeer
    }

    data class Relay(
        override val identity: PairedRuntimeIdentity,
        val relayId: String,
        val host: String,
        val port: Int,
        val relayFrameSecret: String? = null,
        override val security: RemoteRouteSecurityContext,
    ) : PreparedRemoteRuntimeRoute() {
        init {
            require(relayId.isNotBlank()) { "Relay id must not be blank" }
            require(host.isNotBlank()) { "Relay host must not be blank" }
            require(port in 1..65535) { "Relay port must be in 1..65535" }
            require(relayFrameSecret?.isNotBlank() != false) { "Relay frame secret must not be blank" }
        }

        override val capability: RuntimeRouteCapability = RuntimeRouteCapability.Relay
    }
}

data class RemoteRouteSecurityContext(
    val rendezvousToken: String,
    val expiresAtEpochMillis: Long,
    val antiReplayNonce: String,
) {
    init {
        require(rendezvousToken.isNotBlank()) { "Remote route rendezvous token must not be blank" }
        require(expiresAtEpochMillis > 0L) { "Remote route expiration must be positive" }
        require(antiReplayNonce.isNotBlank()) { "Remote route anti-replay nonce must not be blank" }
    }

    fun isExpired(nowEpochMillis: Long): Boolean = expiresAtEpochMillis <= nowEpochMillis
}

fun interface RuntimeRemoteRoutePreparer {
    fun prepareRemoteRoutes(identity: PairedRuntimeIdentity): List<PreparedRemoteRuntimeRoute>
}

fun interface RuntimePeerToPeerConnector {
    suspend fun connect(route: PreparedRemoteRuntimeRoute.PeerToPeer, timeoutMillis: Int): RuntimeProtocolChannel
}

fun interface RuntimeRelayConnector {
    suspend fun connect(route: PreparedRemoteRuntimeRoute.Relay, timeoutMillis: Int): RuntimeProtocolChannel
}

enum class RuntimeRouteRejectionReason {
    DirectTcpEndpointNotPrepared,
    PeerToPeerConnectorNotAvailable,
    RelayConnectorNotAvailable,
    RemoteRouteIdentityMismatch,
    RemoteRouteExpired,
}

data class RuntimeRouteRejection(
    val route: RuntimeRouteCandidate,
    val capability: RuntimeRouteCapability,
    val reason: RuntimeRouteRejectionReason,
)

private fun RuntimeRouteCandidate.connectabilityRejection(
    targetIdentity: PairedRuntimeIdentity?,
    peerToPeerConnector: RuntimePeerToPeerConnector?,
    relayConnector: RuntimeRelayConnector?,
    nowEpochMillis: Long = System.currentTimeMillis(),
): RuntimeRouteRejection? {
    val reason = when (this) {
        is RuntimeRouteCandidate.DirectTcp -> return null
        is RuntimeRouteCandidate.LocalDirect -> RuntimeRouteRejectionReason.DirectTcpEndpointNotPrepared
        is RuntimeRouteCandidate.PeerToPeer -> {
            val prepared = preparedRoute
                ?: return RuntimeRouteRejection(
                    route = this,
                    capability = capability,
                    reason = RuntimeRouteRejectionReason.PeerToPeerConnectorNotAvailable,
                )
            if (!prepared.isBoundTo(identity, targetIdentity)) {
                RuntimeRouteRejectionReason.RemoteRouteIdentityMismatch
            } else if (prepared.security.isExpired(nowEpochMillis)) {
                RuntimeRouteRejectionReason.RemoteRouteExpired
            } else if (peerToPeerConnector != null) {
                return null
            } else {
                RuntimeRouteRejectionReason.PeerToPeerConnectorNotAvailable
            }
        }
        is RuntimeRouteCandidate.Relay -> {
            val prepared = preparedRoute
                ?: return RuntimeRouteRejection(
                    route = this,
                    capability = capability,
                    reason = RuntimeRouteRejectionReason.RelayConnectorNotAvailable,
                )
            if (!prepared.isBoundTo(identity, targetIdentity)) {
                RuntimeRouteRejectionReason.RemoteRouteIdentityMismatch
            } else if (prepared.security.isExpired(nowEpochMillis)) {
                RuntimeRouteRejectionReason.RemoteRouteExpired
            } else if (relayConnector != null) {
                return null
            } else {
                RuntimeRouteRejectionReason.RelayConnectorNotAvailable
            }
        }
    }
    return RuntimeRouteRejection(
        route = this,
        capability = capability,
        reason = reason,
    )
}

enum class RuntimeRouteSource {
    EndpointHint,
    TrustedLastKnownEndpoint,
    FreshDiscovery,
    Manual,
    LocalDirectDiscovery,
    PeerToPeer,
    Relay,
}

fun interface RuntimeRouteResolver {
    fun resolveRoutes(target: RuntimeConnectionTarget): List<RuntimeRouteCandidate>
}

enum class RuntimeConnectionFailureReason {
    NoRoutesResolved,
    NoConnectableRoute,
    RouteAttemptsFailed,
}

data class RuntimeRouteAttemptFailure(
    val route: RuntimeRouteCandidate,
    val cause: Throwable,
)

data class RuntimeConnectionResult(
    val channel: RuntimeProtocolChannel,
    val route: RuntimeRouteCandidate,
)

class RuntimeConnectionFailure(
    val reason: RuntimeConnectionFailureReason,
    val target: RuntimeConnectionTarget,
    val routes: List<RuntimeRouteCandidate>,
    val routeRejections: List<RuntimeRouteRejection> = emptyList(),
    val attemptFailures: List<RuntimeRouteAttemptFailure> = emptyList(),
) : IllegalArgumentException(
    when (reason) {
        RuntimeConnectionFailureReason.NoRoutesResolved ->
            "No runtime routes resolved for target"
        RuntimeConnectionFailureReason.NoConnectableRoute ->
            "No connectable runtime route resolved for target"
        RuntimeConnectionFailureReason.RouteAttemptsFailed ->
            "All connectable runtime routes failed"
    },
    attemptFailures.lastOrNull()?.cause,
)

fun interface RuntimeTransportConnector {
    suspend fun connect(host: String, port: Int, timeoutMillis: Int): RuntimeProtocolChannel
}

class RuntimeConnectionManager(
    private val connector: RuntimeTransportConnector,
    private val routeResolver: RuntimeRouteResolver = DefaultRuntimeRouteResolver,
    private val remoteRoutePreparer: RuntimeRemoteRoutePreparer? = null,
    private val peerToPeerConnector: RuntimePeerToPeerConnector? = null,
    private val relayConnector: RuntimeRelayConnector? = null,
    private val currentTimeMillis: () -> Long = { System.currentTimeMillis() },
) {
    constructor(transportClient: RuntimeTransportClient) : this(
        RuntimeTransportConnector { host, port, timeoutMillis ->
            transportClient.connect(host = host, port = port, timeoutMillis = timeoutMillis)
        },
    )

    suspend fun connect(target: RuntimeConnectionTarget, timeoutMillis: Int = DEFAULT_TIMEOUT_MILLIS): RuntimeProtocolChannel {
        return connectWithRoute(target, timeoutMillis).channel
    }

    suspend fun connectWithRoute(
        target: RuntimeConnectionTarget,
        timeoutMillis: Int = DEFAULT_TIMEOUT_MILLIS,
    ): RuntimeConnectionResult {
        val routes = resolveRoutes(target)
        if (routes.isEmpty()) {
            throw RuntimeConnectionFailure(
                reason = RuntimeConnectionFailureReason.NoRoutesResolved,
                target = target,
                routes = routes,
            )
        }

        val nowEpochMillis = currentTimeMillis()
        val routeRejections = routes.mapNotNull {
            it.connectabilityRejection(
                targetIdentity = target.identity,
                peerToPeerConnector = peerToPeerConnector,
                relayConnector = relayConnector,
                nowEpochMillis = nowEpochMillis,
            )
        }
        val connectableRoutes = routes.filter { route ->
            route.connectabilityRejection(
                targetIdentity = target.identity,
                peerToPeerConnector = peerToPeerConnector,
                relayConnector = relayConnector,
                nowEpochMillis = nowEpochMillis,
            ) == null
        }
        if (connectableRoutes.isEmpty()) {
            throw RuntimeConnectionFailure(
                reason = RuntimeConnectionFailureReason.NoConnectableRoute,
                target = target,
                routes = routes,
                routeRejections = routeRejections,
            )
        }

        val failures = mutableListOf<RuntimeRouteAttemptFailure>()
        connectableRoutes.forEach { route ->
            runCatching {
                connect(route, timeoutMillis)
            }.onSuccess {
                return RuntimeConnectionResult(
                    channel = it,
                    route = route,
                )
            }.onFailure { error ->
                failures += RuntimeRouteAttemptFailure(route, error)
            }
        }

        throw RuntimeConnectionFailure(
            reason = RuntimeConnectionFailureReason.RouteAttemptsFailed,
            target = target,
            routes = routes,
            routeRejections = routeRejections,
            attemptFailures = failures,
        )
    }

    private fun resolveRoutes(target: RuntimeConnectionTarget): List<RuntimeRouteCandidate> {
        val routes = routeResolver.resolveRoutes(target).toMutableList()
        val identity = target.identity ?: return routes
        val preparedRoutes = remoteRoutePreparer?.prepareRemoteRoutes(identity).orEmpty()
        val preparedCandidates = preparedRoutes.map { preparedRoute ->
            when (preparedRoute) {
                is PreparedRemoteRuntimeRoute.PeerToPeer ->
                    RuntimeRouteCandidate.PeerToPeer(
                        identity = preparedRoute.identity,
                        preparedRoute = preparedRoute,
                    )
                is PreparedRemoteRuntimeRoute.Relay ->
                    RuntimeRouteCandidate.Relay(
                        identity = preparedRoute.identity,
                        preparedRoute = preparedRoute,
                    )
            }
        }
        if (preparedCandidates.isEmpty()) return routes

        val preparedPeerToPeerRoutes = preparedCandidates.filterIsInstance<RuntimeRouteCandidate.PeerToPeer>()
        val preparedRelayRoutes = preparedCandidates.filterIsInstance<RuntimeRouteCandidate.Relay>()
        val freshLocalRoutes = routes.filter { route ->
            route is RuntimeRouteCandidate.DirectTcp && route.source == RuntimeRouteSource.FreshDiscovery
        }
        val staleOrUnpreparedRoutes = routes.filterNot { route ->
            route is RuntimeRouteCandidate.DirectTcp && route.source == RuntimeRouteSource.FreshDiscovery
        }
        return preparedPeerToPeerRoutes + preparedRelayRoutes + freshLocalRoutes + staleOrUnpreparedRoutes
    }

    private suspend fun connect(route: RuntimeRouteCandidate, timeoutMillis: Int): RuntimeProtocolChannel {
        return when (route) {
            is RuntimeRouteCandidate.DirectTcp ->
                connector.connect(
                    host = route.hint.host,
                    port = route.hint.port,
                    timeoutMillis = timeoutMillis,
                )
            is RuntimeRouteCandidate.PeerToPeer ->
                requireNotNull(peerToPeerConnector)
                    .connect(requireNotNull(route.preparedRoute), timeoutMillis)
            is RuntimeRouteCandidate.Relay ->
                requireNotNull(relayConnector)
                    .connect(requireNotNull(route.preparedRoute), timeoutMillis)
            is RuntimeRouteCandidate.LocalDirect ->
                error("Local direct route is not prepared as a concrete transport endpoint")
        }
    }

    companion object {
        const val DEFAULT_TIMEOUT_MILLIS = 5_000

        val DefaultRuntimeRouteResolver = RuntimeRouteResolver { target ->
            val routes = mutableListOf<RuntimeRouteCandidate>()
            target.endpointHint?.takeUnless { endpoint ->
                endpoint.source == RuntimeEndpointSource.TrustedLastKnown
            }?.let { endpoint ->
                routes +=
                    RuntimeRouteCandidate.DirectTcp(
                        hint = endpoint,
                        source = endpoint.routeSource(),
                    )
            }
            target.identity?.let { identity ->
                routes += RuntimeRouteCandidate.LocalDirect(identity)
                routes += RuntimeRouteCandidate.PeerToPeer(identity)
                routes += RuntimeRouteCandidate.Relay(identity)
            }
            routes
        }
    }
}

private fun RuntimeEndpointHint.routeSource(): RuntimeRouteSource {
    return when (source) {
        RuntimeEndpointSource.TrustedLastKnown -> RuntimeRouteSource.TrustedLastKnownEndpoint
        RuntimeEndpointSource.PairingQr -> RuntimeRouteSource.EndpointHint
        RuntimeEndpointSource.BonjourDiscovery -> RuntimeRouteSource.FreshDiscovery
        RuntimeEndpointSource.UsbReverse -> RuntimeRouteSource.FreshDiscovery
        RuntimeEndpointSource.Emulator -> RuntimeRouteSource.EndpointHint
        RuntimeEndpointSource.Manual -> RuntimeRouteSource.Manual
    }
}

private fun PreparedRemoteRuntimeRoute.isBoundTo(
    candidateIdentity: PairedRuntimeIdentity,
    targetIdentity: PairedRuntimeIdentity?,
): Boolean {
    return identity.includesPinnedIdentity(candidateIdentity) &&
        (targetIdentity == null || identity.includesPinnedIdentity(targetIdentity))
}

private fun PairedRuntimeIdentity.includesPinnedIdentity(pinned: PairedRuntimeIdentity): Boolean {
    if (deviceId != pinned.deviceId) return false
    if (!matchesPinnedValue(fingerprint, pinned.fingerprint)) return false
    if (!matchesPinnedValue(publicKeyBase64, pinned.publicKeyBase64)) return false
    if (!matchesPinnedValue(routeToken, pinned.routeToken)) return false
    return true
}

private fun matchesPinnedValue(actual: String?, pinned: String?): Boolean {
    return pinned == null || actual == pinned
}
