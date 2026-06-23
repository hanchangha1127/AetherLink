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
    val routeToken: String? = null,
) {
    init {
        require(deviceId.isNotBlank()) { "Runtime device id must not be blank" }
        require(name.isNotBlank()) { "Runtime name must not be blank" }
        require(fingerprint?.isNotBlank() != false) { "Runtime fingerprint must not be blank" }
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

    data class PeerToPeer(
        override val identity: PairedRuntimeIdentity,
        val sessionId: String,
    ) : PreparedRemoteRuntimeRoute() {
        init {
            require(sessionId.isNotBlank()) { "Peer-to-peer session id must not be blank" }
        }

        override val capability: RuntimeRouteCapability = RuntimeRouteCapability.PeerToPeer
    }

    data class Relay(
        override val identity: PairedRuntimeIdentity,
        val relayId: String,
    ) : PreparedRemoteRuntimeRoute() {
        init {
            require(relayId.isNotBlank()) { "Relay id must not be blank" }
        }

        override val capability: RuntimeRouteCapability = RuntimeRouteCapability.Relay
    }
}

fun interface RuntimeRemoteRoutePreparer {
    fun prepareRemoteRoutes(identity: PairedRuntimeIdentity): List<PreparedRemoteRuntimeRoute>
}

enum class RuntimeRouteRejectionReason {
    DirectTcpEndpointNotPrepared,
    PeerToPeerConnectorNotAvailable,
    RelayConnectorNotAvailable,
}

data class RuntimeRouteRejection(
    val route: RuntimeRouteCandidate,
    val capability: RuntimeRouteCapability,
    val reason: RuntimeRouteRejectionReason,
)

private fun RuntimeRouteCandidate.directTcpRejection(): RuntimeRouteRejection? {
    val reason = when (this) {
        is RuntimeRouteCandidate.DirectTcp -> return null
        is RuntimeRouteCandidate.LocalDirect -> RuntimeRouteRejectionReason.DirectTcpEndpointNotPrepared
        is RuntimeRouteCandidate.PeerToPeer -> RuntimeRouteRejectionReason.PeerToPeerConnectorNotAvailable
        is RuntimeRouteCandidate.Relay -> RuntimeRouteRejectionReason.RelayConnectorNotAvailable
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
    val route: RuntimeRouteCandidate.DirectTcp,
    val cause: Throwable,
)

class RuntimeConnectionFailure(
    val reason: RuntimeConnectionFailureReason,
    val target: RuntimeConnectionTarget,
    val routes: List<RuntimeRouteCandidate>,
    val routeRejections: List<RuntimeRouteRejection> = routes.mapNotNull { it.directTcpRejection() },
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
    suspend fun connect(host: String, port: Int, timeoutMillis: Int)
}

class RuntimeConnectionManager(
    private val connector: RuntimeTransportConnector,
    private val routeResolver: RuntimeRouteResolver = DefaultRuntimeRouteResolver,
) {
    constructor(transportClient: MacRuntimeTransportClient) : this(
        RuntimeTransportConnector { host, port, timeoutMillis ->
            transportClient.connect(host = host, port = port, timeoutMillis = timeoutMillis)
        },
    )

    suspend fun connect(target: RuntimeConnectionTarget, timeoutMillis: Int = DEFAULT_TIMEOUT_MILLIS) {
        val routes = routeResolver.resolveRoutes(target)
        if (routes.isEmpty()) {
            throw RuntimeConnectionFailure(
                reason = RuntimeConnectionFailureReason.NoRoutesResolved,
                target = target,
                routes = routes,
            )
        }

        val directTcpRoutes = routes.filterIsInstance<RuntimeRouteCandidate.DirectTcp>()
        val routeRejections = routes.mapNotNull { it.directTcpRejection() }
        if (directTcpRoutes.isEmpty()) {
            throw RuntimeConnectionFailure(
                reason = RuntimeConnectionFailureReason.NoConnectableRoute,
                target = target,
                routes = routes,
                routeRejections = routeRejections,
            )
        }

        val failures = mutableListOf<RuntimeRouteAttemptFailure>()
        directTcpRoutes.forEach { route ->
            runCatching {
                connector.connect(
                    host = route.hint.host,
                    port = route.hint.port,
                    timeoutMillis = timeoutMillis,
                )
            }.onSuccess {
                return
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

    companion object {
        const val DEFAULT_TIMEOUT_MILLIS = 5_000

        val DefaultRuntimeRouteResolver = RuntimeRouteResolver { target ->
            val routes = mutableListOf<RuntimeRouteCandidate>()
            target.endpointHint?.let { endpoint ->
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
