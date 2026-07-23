package com.localagentbridge.android.core.transport

import com.localagentbridge.android.core.pairing.ProductionC1AuthorityBoundSecureSessionCapability
import com.localagentbridge.android.core.pairing.ProductionC1AuthorityBoundSecureSessionDescriptor
import com.localagentbridge.android.core.protocol.p2pnat.ProductionRouteAuthorization
import com.localagentbridge.android.core.protocol.p2pnat.ProductionRouteAuthorizationKind
import com.localagentbridge.android.core.protocol.p2pnat.ProductionC1PreauthorizationSessionContext
import com.localagentbridge.android.core.protocol.p2pnat.ProductionSecureSessionCodec
import com.localagentbridge.android.core.protocol.p2pnat.ProductionSecureSessionTranscript
import com.localagentbridge.android.core.protocol.p2pnat.VerifiedProductionC1CandidateP2PTranscriptBinding
import com.localagentbridge.android.core.protocol.p2pnat.VerifiedProductionC1CandidateP2PTransportDescriptor
import java.io.IOException
import java.util.concurrent.CancellationException
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.cancel
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull

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
    val requiresProductionSession: Boolean = false,
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
    abstract val productionSession: PreparedProductionSecureSession?

    data class PeerToPeer(
        override val identity: PairedRuntimeIdentity,
        val sessionId: String,
        val encryptedCandidateMaterial: String? = null,
        override val security: RemoteRouteSecurityContext,
        override val productionSession: PreparedProductionSecureSession? = null,
        val verifiedCandidateDescriptor:
            VerifiedProductionC1CandidateP2PTransportDescriptor? = null,
    ) : PreparedRemoteRuntimeRoute() {
        init {
            require(sessionId.isNotBlank()) { "Peer-to-peer session id must not be blank" }
            require(encryptedCandidateMaterial?.isNotBlank() != false) {
                "Peer-to-peer encrypted candidate material must not be blank"
            }
            require(
                productionSession == null ||
                    productionSession.routeAuthorization.kind == ProductionRouteAuthorizationKind.P2P_DIRECT
            ) { "Peer-to-peer connector requires p2p_direct production authorization" }
            require(
                productionSession == null ||
                    identity.fingerprint == productionSession.transcript.runtimeIdentityFingerprint
            ) { "Production peer route identity must match its secure-session transcript" }
            require(
                productionSession == null ||
                    sessionId == productionSession.expectedSessionId
            ) { "Production peer route session ID must match its secure-session transcript" }
            require(verifiedCandidateDescriptor == null || productionSession != null) {
                "Verified transport descriptor requires a production peer session"
            }
            require(
                productionSession?.verifiedCandidateDerived != true ||
                    verifiedCandidateDescriptor != null
            ) {
                "Verifier-derived production peer session requires its transport descriptor"
            }
            verifiedCandidateDescriptor?.let { descriptor ->
                require(descriptor.sessionId == sessionId)
                require(descriptor.generation == productionSession?.transcript?.generation)
                require(security.rendezvousToken == descriptor.descriptorDigest)
                require(security.antiReplayNonce == descriptor.connectorInputCommitmentDigest)
                require(descriptor.expiresAtMs <= Long.MAX_VALUE.toULong())
                require(security.expiresAtEpochMillis == descriptor.expiresAtMs.toLong())
            }
        }

        override val capability: RuntimeRouteCapability = RuntimeRouteCapability.PeerToPeer

        companion object {
            fun fromVerifiedCandidate(
                identity: PairedRuntimeIdentity,
                binding: VerifiedProductionC1CandidateP2PTranscriptBinding,
            ): PeerToPeer {
                val descriptor =
                    VerifiedProductionC1CandidateP2PTransportDescriptor.fromVerifiedBinding(binding)
                require(descriptor.expiresAtMs <= Long.MAX_VALUE.toULong()) {
                    "Production transport expiration exceeds Android clock range"
                }
                return PeerToPeer(
                    identity = identity,
                    sessionId = descriptor.sessionId,
                    security = RemoteRouteSecurityContext(
                        rendezvousToken = descriptor.descriptorDigest,
                        expiresAtEpochMillis = descriptor.expiresAtMs.toLong(),
                        antiReplayNonce = descriptor.connectorInputCommitmentDigest,
                    ),
                    productionSession = PreparedProductionSecureSession.fromVerifiedCandidate(binding),
                    verifiedCandidateDescriptor = descriptor,
                )
            }
        }
    }

    data class Relay(
        override val identity: PairedRuntimeIdentity,
        val relayId: String,
        val host: String,
        val port: Int,
        val relayFrameSecret: String? = null,
        val ticketGeneration: Long? = null,
        val relayScope: String? = null,
        override val security: RemoteRouteSecurityContext,
        override val productionSession: PreparedProductionSecureSession? = null,
    ) : PreparedRemoteRuntimeRoute() {
        init {
            require(relayId.isNotBlank()) { "Relay id must not be blank" }
            require(host.isNotBlank()) { "Relay host must not be blank" }
            require(port in 1..65535) { "Relay port must be in 1..65535" }
            require(relayFrameSecret?.isNotBlank() != false) { "Relay frame secret must not be blank" }
            require(ticketGeneration == null || ticketGeneration > 0L) {
                "Relay ticket generation must be positive"
            }
            require(relayScope.isAllowedPreparedRelayScope()) {
                "Relay scope must be remote, private_overlay, usb_reverse, or absent"
            }
            require(
                productionSession == null ||
                    productionSession.routeAuthorization.kind in setOf(
                        ProductionRouteAuthorizationKind.TURN_RELAY,
                        ProductionRouteAuthorizationKind.SEALED_RELAY,
                    )
            ) { "Relay connector requires turn_relay or sealed_relay production authorization" }
            require(
                productionSession == null ||
                    identity.fingerprint == productionSession.transcript.runtimeIdentityFingerprint
            ) { "Production relay route identity must match its secure-session transcript" }
        }

        override val capability: RuntimeRouteCapability = RuntimeRouteCapability.Relay
    }
}

class PreparedProductionSecureSession internal constructor(
    val transcript: ProductionSecureSessionTranscript,
    val routeAuthorization: ProductionRouteAuthorization,
    val expectedObject7Object26BindingId: String,
    internal val verifiedCandidateDerived: Boolean = false,
    private val verifiedGrantAuthorizationDigest: String? = null,
) {
    val expectedSessionId: String = transcript.sessionId
    val expectedRouteAuthorizationKind: ProductionRouteAuthorizationKind =
        routeAuthorization.kind

    init {
        // Legacy prepared sessions bind object 7 directly to the selected route authorization.
        // G1a-C candidate sessions deliberately bind object 7 to the later, narrower object-26
        // endpoint grant while retaining object 4 as the manager's route-kind authorization.
        if (verifiedCandidateDerived) {
            val expectedGrantDigest = requireNotNull(verifiedGrantAuthorizationDigest) {
                "Verifier-derived production session requires its grant authorization digest"
            }
            require(
                expectedGrantDigest.length == 64 &&
                    expectedGrantDigest.all { it in '0'..'9' || it in 'a'..'f' } &&
                    transcript.routeAuthorizationDigest == expectedGrantDigest &&
                    transcript.pairBindingDigest == routeAuthorization.pairBindingDigest &&
                    transcript.pairEpoch == routeAuthorization.pairEpoch &&
                    (routeAuthorization.generation == null ||
                        transcript.generation == routeAuthorization.generation),
            ) { "Production transcript does not match its verified grant authorization" }
            // Force the same public transcript validation used by the legacy matching path.
            ProductionSecureSessionCodec.digest(transcript)
        } else {
            require(verifiedGrantAuthorizationDigest == null) {
                "Legacy production session cannot carry a verified grant digest"
            }
            require(ProductionSecureSessionCodec.matches(transcript, routeAuthorization)) {
                "Production transcript does not match its route authorization"
            }
        }
        require(
            expectedObject7Object26BindingId.length == 64 &&
                expectedObject7Object26BindingId.all { it in '0'..'9' || it in 'a'..'f' },
        ) { "Expected object-7/object-26 binding ID must be 64 lowercase hexadecimal characters" }
        require(expectedSessionId == transcript.sessionId) {
            "Prepared production session ID must remain transcript-bound"
        }
        require(expectedRouteAuthorizationKind == transcript.routeAuthorizationKind) {
            "Prepared production route kind must remain transcript-bound"
        }
    }

    companion object {
        /**
         * The only non-test construction path: derive every prepared-session field from one
         * verifier-minted object-7/object-26 binding rather than caller-selected digests.
         */
        fun fromVerifiedCandidate(
            binding: VerifiedProductionC1CandidateP2PTranscriptBinding,
        ): PreparedProductionSecureSession = PreparedProductionSecureSession(
            transcript = binding.transcript,
            routeAuthorization = binding.grant.routeAuthorizations.finalP2PDirect,
            expectedObject7Object26BindingId =
                binding.keyScheduleBinding.object7Object26KdfBindingDigestHex,
            verifiedCandidateDerived = true,
            verifiedGrantAuthorizationDigest =
                binding.keyScheduleBinding.grantAuthorization.digestHex,
        )
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

/**
 * Opens exactly one raw frame-body route selected by a production connection composer.
 * The connector is route-bound by RuntimeConnectionManager and rejects a second invocation.
 */
fun interface RuntimeRawRouteConnector {
    suspend fun connect(
        route: RuntimeRouteCandidate,
        timeoutMillis: Int,
    ): RuntimeRawFrameBodyChannel
}

data class RuntimeProductionConnectionRequest(
    val identity: PairedRuntimeIdentity,
    val route: RuntimeRouteCandidate,
    val session: PreparedProductionSecureSession,
    val connectionGeneration: Long,
    val timeoutMillis: Int,
) {
    init {
        require(connectionGeneration > 0L) { "Production connection generation must be positive" }
        require(timeoutMillis > 0) { "Production connection timeout must be positive" }
    }
}

/**
 * Manager-owned one-use composition surface. The raw endpoint never escapes this lease: only the
 * core production adapter receives its transferred endpoint.
 */
interface RuntimeProductionRawRouteLease {
    suspend fun compose(
        capability: ProductionC1AuthorityBoundSecureSessionCapability,
    ): RuntimeProductionChannelComposition
}

/** A production composition can only be created by its manager-owned raw-route lease. */
class RuntimeProductionChannelComposition internal constructor(
    val channel: RuntimeProtocolChannel,
    internal val receipt: RuntimeProductionCompositionReceipt,
)

internal class RuntimeProductionCompositionReceipt internal constructor(
    internal val owner: ManagedRuntimeProductionRawRouteLease,
    internal val rawChannel: RuntimeRawFrameBodyChannel,
    internal val channel: RuntimeProtocolChannel,
    internal val route: RuntimeRouteCandidate,
    internal val session: PreparedProductionSecureSession,
    internal val bindingId: String,
    internal val sessionId: String,
    internal val connectionGeneration: Long,
    internal val routeKind: ProductionRouteAuthorizationKind,
) {
    private val claimed = AtomicBoolean(false)

    internal fun claimOnce(): Boolean = claimed.compareAndSet(false, true)
}

/** Owns production composition; plaintext fallback is never permitted. */
fun interface RuntimeProductionChannelComposer {
    suspend fun connect(
        request: RuntimeProductionConnectionRequest,
        rawLease: RuntimeProductionRawRouteLease,
    ): RuntimeProductionChannelComposition
}

enum class RuntimeRouteRejectionReason {
    DirectTcpEndpointNotPrepared,
    PeerToPeerConnectorNotAvailable,
    RelayConnectorNotAvailable,
    RemoteRouteIdentityMismatch,
    RemoteRouteUsesPairingRouteToken,
    ProductionRouteNotYetValid,
    RemoteRouteExpired,
    ProductionChannelCompositionNotAvailable,
    ProductionRelayExactBindingUnavailable,
    ProductionSessionRequired,
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
    productionRawRouteConnector: RuntimeRawRouteConnector?,
    productionChannelComposer: RuntimeProductionChannelComposer?,
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
            } else if (prepared.usesPairingRouteTokenAsRouteMaterial(identity, targetIdentity)) {
                RuntimeRouteRejectionReason.RemoteRouteUsesPairingRouteToken
            } else if (
                prepared.verifiedCandidateDescriptor?.let { descriptor ->
                    nowEpochMillis < 0 || nowEpochMillis.toULong() < descriptor.effectiveNotBeforeMs
                } == true
            ) {
                RuntimeRouteRejectionReason.ProductionRouteNotYetValid
            } else if (prepared.security.isExpired(nowEpochMillis)) {
                RuntimeRouteRejectionReason.RemoteRouteExpired
            } else if (
                prepared.productionSession != null &&
                    (productionRawRouteConnector == null || productionChannelComposer == null)
            ) {
                RuntimeRouteRejectionReason.ProductionChannelCompositionNotAvailable
            } else if (prepared.productionSession != null) {
                return null
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
            } else if (prepared.usesPairingRouteTokenAsRouteMaterial(identity, targetIdentity)) {
                RuntimeRouteRejectionReason.RemoteRouteUsesPairingRouteToken
            } else if (prepared.security.isExpired(nowEpochMillis)) {
                RuntimeRouteRejectionReason.RemoteRouteExpired
            } else if (prepared.productionSession != null) {
                RuntimeRouteRejectionReason.ProductionRelayExactBindingUnavailable
            } else if (
                relayConnector != null
            ) {
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
    ProductionSessionSecurityRejected,
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
        RuntimeConnectionFailureReason.ProductionSessionSecurityRejected ->
            "Production runtime route failed secure-session composition"
    },
    attemptFailures.lastOrNull()?.cause,
)

fun interface RuntimeTransportConnector {
    suspend fun connect(host: String, port: Int, timeoutMillis: Int): RuntimeProtocolChannel
}

class RuntimeConnectionManager internal constructor(
    private val connector: RuntimeTransportConnector,
    private val routeResolver: RuntimeRouteResolver,
    private val remoteRoutePreparer: RuntimeRemoteRoutePreparer?,
    private val peerToPeerConnector: RuntimePeerToPeerConnector?,
    private val relayConnector: RuntimeRelayConnector?,
    private val productionRawRouteConnector: RuntimeRawRouteConnector?,
    private val productionChannelComposer: RuntimeProductionChannelComposer?,
    private val currentTimeMillis: () -> Long,
    private val productionCompositionHandshakeBudgetMillis: Long,
    private val afterProductionCommitBeforeReturnForTesting:
        (suspend (RuntimeProtocolChannel) -> Unit)?,
    @Suppress("UNUSED_PARAMETER") _productionBridgeMarker: Unit,
) {
    init {
        require(productionCompositionHandshakeBudgetMillis > 0L) {
            "Production composition handshake budget must be positive"
        }
    }

    constructor(
        connector: RuntimeTransportConnector,
        routeResolver: RuntimeRouteResolver = DefaultRuntimeRouteResolver,
        remoteRoutePreparer: RuntimeRemoteRoutePreparer? = null,
        peerToPeerConnector: RuntimePeerToPeerConnector? = null,
        relayConnector: RuntimeRelayConnector? = null,
        currentTimeMillis: () -> Long = { System.currentTimeMillis() },
    ) : this(
        connector = connector,
        routeResolver = routeResolver,
        remoteRoutePreparer = remoteRoutePreparer,
        peerToPeerConnector = peerToPeerConnector,
        relayConnector = relayConnector,
        productionRawRouteConnector = null,
        productionChannelComposer = null,
        currentTimeMillis = currentTimeMillis,
        productionCompositionHandshakeBudgetMillis =
            DEFAULT_PRODUCTION_COMPOSITION_HANDSHAKE_BUDGET_MILLIS,
        afterProductionCommitBeforeReturnForTesting = null,
        _productionBridgeMarker = Unit,
    )

    constructor(
        connector: RuntimeTransportConnector,
        routeResolver: RuntimeRouteResolver = DefaultRuntimeRouteResolver,
        remoteRoutePreparer: RuntimeRemoteRoutePreparer? = null,
        peerToPeerConnector: RuntimePeerToPeerConnector? = null,
        relayConnector: RuntimeRelayConnector? = null,
        productionRawRouteConnector: RuntimeRawRouteConnector,
        productionChannelComposer: RuntimeProductionChannelComposer,
        currentTimeMillis: () -> Long = { System.currentTimeMillis() },
    ) : this(
        connector = connector,
        routeResolver = routeResolver,
        remoteRoutePreparer = remoteRoutePreparer,
        peerToPeerConnector = peerToPeerConnector,
        relayConnector = relayConnector,
        productionRawRouteConnector = productionRawRouteConnector,
        productionChannelComposer = productionChannelComposer,
        currentTimeMillis = currentTimeMillis,
        productionCompositionHandshakeBudgetMillis =
            DEFAULT_PRODUCTION_COMPOSITION_HANDSHAKE_BUDGET_MILLIS,
        afterProductionCommitBeforeReturnForTesting = null,
        _productionBridgeMarker = Unit,
    )

    constructor(transportClient: RuntimeTransportClient) : this(
        RuntimeTransportConnector { host, port, timeoutMillis ->
            transportClient.connect(host = host, port = port, timeoutMillis = timeoutMillis)
        },
    )

    private val connectionGenerationCounter = AtomicLong(0L)

    suspend fun connect(
        target: RuntimeConnectionTarget,
        timeoutMillis: Int = DEFAULT_TIMEOUT_MILLIS,
    ): RuntimeProtocolChannel = cancellationSafeHandoff(
        value = connectWithManagerGeneration(
            target = target,
            timeoutMillis = timeoutMillis,
            connectionGeneration = nextConnectionGeneration(),
        ).channel,
        closeIfUndelivered = RuntimeProtocolChannel::close,
    )

    suspend fun connectWithRoute(
        target: RuntimeConnectionTarget,
        timeoutMillis: Int = DEFAULT_TIMEOUT_MILLIS,
    ): RuntimeConnectionResult = cancellationSafeHandoff(
        value = connectWithManagerGeneration(
            target = target,
            timeoutMillis = timeoutMillis,
            connectionGeneration = nextConnectionGeneration(),
        ),
        closeIfUndelivered = { it.channel.close() },
    )

    private suspend fun connectWithManagerGeneration(
        target: RuntimeConnectionTarget,
        timeoutMillis: Int,
        connectionGeneration: Long,
    ): RuntimeConnectionResult {
        require(connectionGeneration > 0L) { "Connection generation must be positive" }
        val resolvedRoutes = resolveRoutes(target)
        if (resolvedRoutes.isEmpty()) {
            throw RuntimeConnectionFailure(
                reason = RuntimeConnectionFailureReason.NoRoutesResolved,
                target = target,
                routes = resolvedRoutes,
            )
        }
        val hasProductionSession = resolvedRoutes.any(RuntimeRouteCandidate::hasProductionSession)
        if (target.requiresProductionSession && !hasProductionSession) {
            throw RuntimeConnectionFailure(
                reason = RuntimeConnectionFailureReason.NoConnectableRoute,
                target = target,
                routes = resolvedRoutes,
                routeRejections = resolvedRoutes.map { route ->
                    RuntimeRouteRejection(
                        route = route,
                        capability = route.capability,
                        reason = RuntimeRouteRejectionReason.ProductionSessionRequired,
                    )
                },
            )
        }
        val routes = if (hasProductionSession) {
            resolvedRoutes.filter(RuntimeRouteCandidate::hasProductionSession)
        } else {
            resolvedRoutes
        }

        val nowEpochMillis = currentTimeMillis()
        val routeRejections = routes.mapNotNull {
            it.connectabilityRejection(
                targetIdentity = target.identity,
                peerToPeerConnector = peerToPeerConnector,
                relayConnector = relayConnector,
                productionRawRouteConnector = productionRawRouteConnector,
                productionChannelComposer = productionChannelComposer,
                nowEpochMillis = nowEpochMillis,
            )
        }
        val connectableRoutes = routes.filter { route ->
            route.connectabilityRejection(
                targetIdentity = target.identity,
                peerToPeerConnector = peerToPeerConnector,
                relayConnector = relayConnector,
                productionRawRouteConnector = productionRawRouteConnector,
                productionChannelComposer = productionChannelComposer,
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

        if (hasProductionSession) {
            val route = connectableRoutes.first()
            return try {
                RuntimeConnectionResult(
                    channel = connectProductionRoute(
                        route = route,
                        timeoutMillis = timeoutMillis,
                        connectionGeneration = connectionGeneration,
                        admissionNowEpochMillis = nowEpochMillis,
                    ),
                    route = route,
                )
            } catch (error: CancellationException) {
                throw error
            } catch (error: Throwable) {
                throw RuntimeConnectionFailure(
                    reason = RuntimeConnectionFailureReason.ProductionSessionSecurityRejected,
                    target = target,
                    routes = routes,
                    routeRejections = routeRejections,
                    attemptFailures = listOf(RuntimeRouteAttemptFailure(route, error)),
                )
            }
        }

        val failures = mutableListOf<RuntimeRouteAttemptFailure>()
        connectableRoutes.forEach { route ->
            try {
                val channel = connect(route, timeoutMillis)
                return RuntimeConnectionResult(
                    channel = channel,
                    route = route,
                )
            } catch (error: CancellationException) {
                throw error
            } catch (error: Throwable) {
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

    private suspend fun connectProductionRoute(
        route: RuntimeRouteCandidate,
        timeoutMillis: Int,
        connectionGeneration: Long,
        admissionNowEpochMillis: Long,
    ): RuntimeProtocolChannel {
        val session = requireNotNull(route.productionSessionOrNull())
        check(route.hasExactProductionRouteBinding(session)) {
            "Production raw route does not match its prepared secure session"
        }
        val identity = route.preparedRemoteIdentityOrNull()
            ?: error("Production route identity is unavailable")
        val request = RuntimeProductionConnectionRequest(
            identity = identity,
            route = route,
            session = session,
            connectionGeneration = connectionGeneration,
            timeoutMillis = timeoutMillis,
        )
        val rawLease = ManagedRuntimeProductionRawRouteLease(
            request = request,
            delegate = requireNotNull(productionRawRouteConnector),
            currentTimeMillis = currentTimeMillis,
        )
        var returnedChannel: RuntimeProtocolChannel? = null
        var committedChannel: RuntimeProtocolChannel? = null
        val composerJob = SupervisorJob()
        val composerTask = CoroutineScope(composerJob + Dispatchers.IO).async {
            runCatching {
                requireNotNull(productionChannelComposer).connect(request, rawLease)
            }
        }
        try {
            // Keep composer-thrown CancellationException instances as values until they cross the
            // manager boundary. Deferred otherwise treats them as task cancellation and coroutine
            // stack-trace recovery may replace the exact exception object.
            // The caller-provided route timeout continues to bound raw connect. Composition then
            // receives exactly the adapter's fixed handshake budget; a saturating sum prevents a
            // future wider timeout source from wrapping into an immediate or negative deadline.
            val compositionTimeoutMillis = productionCompositionTimeoutMillis(
                rawRouteTimeoutMillis = timeoutMillis.toLong(),
                handshakeBudgetMillis = productionCompositionHandshakeBudgetMillis,
            )
            val compositionResult = withTimeoutOrNull(compositionTimeoutMillis) {
                composerTask.await()
            } ?: throw IOException(
                "Production secure-channel composition timed out after " +
                    "$compositionTimeoutMillis ms",
            )
            // Throw composer failures outside both Deferred.await and withTimeout so coroutine
            // stack-trace recovery cannot substitute a caller-observable CancellationException.
            val composition = compositionResult.getOrThrow()
            returnedChannel = composition.channel
            val commitNowEpochMillis = currentTimeMillis()
            check(commitNowEpochMillis >= admissionNowEpochMillis) {
                "Production route clock moved backwards during secure-channel composition"
            }
            check(
                route.preparedRemoteSecurityOrNull()?.isExpired(commitNowEpochMillis) == false,
            ) { "Production route expired during secure-channel composition" }
            val channel = rawLease.commit(composition)
            committedChannel = channel
            composerJob.cancel()
            afterProductionCommitBeforeReturnForTesting?.invoke(channel)
            return channel
        } catch (error: Throwable) {
            composerTask.cancel()
            composerJob.cancel()
            withContext(NonCancellable) {
                committedChannel?.let { channel ->
                    runCatching { channel.close() }.exceptionOrNull()?.let(error::addSuppressed)
                }
                rawLease.cleanup(returnedChannel).forEach(error::addSuppressed)
            }
            throw error
        }
    }

    private fun nextConnectionGeneration(): Long = connectionGenerationCounter.incrementAndGet().also {
        check(it > 0L) { "Connection generation exhausted" }
    }

    companion object {
        const val DEFAULT_TIMEOUT_MILLIS = 5_000
        internal const val DEFAULT_PRODUCTION_COMPOSITION_HANDSHAKE_BUDGET_MILLIS =
            ProductionRuntimeSecureChannelAdapter.DEFAULT_HANDSHAKE_TIMEOUT_MILLIS

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

internal class ManagedRuntimeProductionRawRouteLease(
    private val request: RuntimeProductionConnectionRequest,
    private val delegate: RuntimeRawRouteConnector,
    private val currentTimeMillis: () -> Long = { System.currentTimeMillis() },
    private val beforeAcquisitionTransitionForTesting: (() -> Unit)? = null,
    private val beforePhysicalConnectorEntryForTesting: (() -> Unit)? = null,
) : RuntimeProductionRawRouteLease {
    private val stateLock = Any()
    private val acquisitionStarted = AtomicBoolean(false)
    private val receiptIssued = AtomicBoolean(false)
    private val committed = AtomicBoolean(false)
    private val closed = AtomicBoolean(false)
    private var retainedRawChannel: ManagedRuntimeRawFrameBodyChannel? = null
    private var retainedCompositionChannel: RuntimeProductionProtocolChannel? = null

    override suspend fun compose(
        capability: ProductionC1AuthorityBoundSecureSessionCapability,
    ): RuntimeProductionChannelComposition = composeInternal(capability.descriptor) { raw ->
        ProductionRuntimeSecureChannelAdapter.createOwned(
            rawChannel = raw,
            capability = capability,
            generation = request.connectionGeneration,
            currentTimeMillis = currentTimeMillis,
        )
    }

    internal suspend fun composeForTesting(
        operations: ProductionRuntimeSecureSessionOperations,
        scope: CoroutineScope,
    ): RuntimeProductionChannelComposition = composeInternal(operations.descriptor) { raw ->
        ProductionRuntimeSecureChannelAdapter(
            rawChannel = raw,
            operations = operations,
            generation = request.connectionGeneration,
            scope = scope,
        )
    }

    private suspend fun composeInternal(
        descriptor: ProductionC1AuthorityBoundSecureSessionDescriptor,
        makeChannel: (RuntimeRawFrameBodyChannel) -> ProductionRuntimeSecureChannelAdapter,
    ): RuntimeProductionChannelComposition {
        check(descriptor.object7Object26KdfBindingDigestHex ==
            request.session.expectedObject7Object26BindingId
        ) { "Production authority capability binding mismatch" }
        check(descriptor.sessionId == request.session.expectedSessionId) {
            "Production authority capability session ID mismatch"
        }
        beforeAcquisitionTransitionForTesting?.invoke()
        val raw = coroutineScope {
            val acquisition = synchronized(stateLock) {
                check(!closed.get()) { "Production raw-route lease is closed" }
                check(acquisitionStarted.compareAndSet(false, true)) {
                    "Production raw route was already composed"
                }
                // UNDISPATCHED makes entering delegate.connect part of the locked transition.
                // Cleanup either wins before this state change (and no connector is invoked), or
                // cannot return until physical connector entry has happened. If connect then
                // suspends, its own timeout/close contract remains responsible until it returns.
                async(start = CoroutineStart.UNDISPATCHED) {
                    beforePhysicalConnectorEntryForTesting?.invoke()
                    val connected = ManagedRuntimeRawFrameBodyChannel(
                        delegate.connect(request.route, request.timeoutMillis),
                    )
                    synchronized(stateLock) {
                        if (closed.get()) {
                            connected.close()
                            error("Production raw-route lease closed during acquisition")
                        }
                        retainedRawChannel = connected
                    }
                    connected
                }
            }
            acquisition.await()
        }
        val channel = makeChannel(raw)
        val accepted = synchronized(stateLock) {
            if (closed.get()) {
                false
            } else {
                retainedCompositionChannel = channel
                true
            }
        }
        if (!accepted) {
            runCatching { channel.close() }
            raw.close()
            error("Production raw-route lease closed during channel composition")
        }
        // Retain the concrete adapter before any handshake suspension. Cancellation or the
        // manager deadline can therefore terminal-claim both adapter and raw route immediately,
        // even if the underlying receive ignores close until it returns later.
        channel.start()
        synchronized(stateLock) {
            check(!closed.get()) { "Production raw-route lease closed during channel composition" }
            check(retainedCompositionChannel === channel) {
                "Production composition channel ownership was lost"
            }
            check(receiptIssued.compareAndSet(false, true)) {
                "Production composition receipt was already issued"
            }
            return RuntimeProductionChannelComposition(
                channel = channel,
                receipt = RuntimeProductionCompositionReceipt(
                    owner = this,
                    rawChannel = raw,
                    channel = channel,
                    route = request.route,
                    session = request.session,
                    bindingId = request.session.expectedObject7Object26BindingId,
                    sessionId = request.session.expectedSessionId,
                    connectionGeneration = request.connectionGeneration,
                    routeKind = request.session.expectedRouteAuthorizationKind,
                ),
            )
        }
    }

    internal fun commit(composition: RuntimeProductionChannelComposition): RuntimeProtocolChannel {
        val receipt = composition.receipt
        val channel = composition.channel
        val productionChannel = channel as? RuntimeProductionProtocolChannel
            ?: error("Production composer returned a non-production channel")
        synchronized(stateLock) {
            check(!closed.get()) { "Production raw-route lease is closed" }
            check(receipt.owner === this) { "Production composition receipt belongs to another lease" }
            check(receipt.claimOnce()) { "Production composition receipt was already committed" }
            val raw = checkNotNull(retainedRawChannel) {
                "Production composer did not acquire its raw route"
            }
            check(receipt.rawChannel === raw) { "Production composition receipt raw identity mismatch" }
            check(receipt.channel === channel) { "Production composition receipt channel mismatch" }
            check(receipt.route === request.route && receipt.route == request.route) {
                "Production composition receipt route mismatch"
            }
            check(receipt.session === request.session) {
                "Production composition receipt session identity mismatch"
            }
            check(receipt.bindingId == request.session.expectedObject7Object26BindingId) {
                "Production composition receipt binding mismatch"
            }
            check(receipt.sessionId == request.session.expectedSessionId) {
                "Production composition receipt session ID mismatch"
            }
            check(receipt.connectionGeneration == request.connectionGeneration) {
                "Production composition receipt generation mismatch"
            }
            check(receipt.routeKind == request.session.expectedRouteAuthorizationKind &&
                request.route.matchesProductionRouteKind(receipt.routeKind)
            ) { "Production composition receipt route kind mismatch" }
            check(acquisitionStarted.get() && receiptIssued.get()) {
                "Production raw route was not consumed exactly once"
            }
            check(retainedCompositionChannel === productionChannel) {
                "Production channel was not created by this raw-route lease"
            }
            check(raw.isConnected) { "Production raw route is not connected" }
            check(channel.isConnected) {
                "Production composer returned an inactive channel"
            }
            check(
                productionChannel.productionBindingId ==
                    request.session.expectedObject7Object26BindingId,
            ) { "Production channel binding mismatch" }
            check(productionChannel.productionSessionId == request.session.expectedSessionId) {
                "Production channel session ID mismatch"
            }
            check(
                productionChannel.productionConnectionGeneration == request.connectionGeneration,
            ) { "Production channel generation mismatch" }
            check(
                channel.transportSecurityContext?.bindingId ==
                    request.session.expectedObject7Object26BindingId,
            ) { "Production composer returned a channel without exact transport security" }
            check(committed.compareAndSet(false, true)) {
                "Production raw-route lease was already committed"
            }
            retainedCompositionChannel = null
            retainedRawChannel = null
            return channel
        }
    }

    internal fun cleanup(returnedChannel: RuntimeProtocolChannel?): List<Throwable> {
        val channels = synchronized(stateLock) {
            if (committed.get()) {
                null
            } else {
                closed.set(true)
                val raw = retainedRawChannel
                retainedRawChannel = null
                val composed = retainedCompositionChannel
                retainedCompositionChannel = null
                buildList {
                    returnedChannel?.let(::add)
                    if (composed != null && composed !== returnedChannel) add(composed)
                } to raw
            }
        } ?: return emptyList()
        val failures = mutableListOf<Throwable>()
        channels.first.forEach { channel ->
            runCatching { channel.close() }.exceptionOrNull()?.let(failures::add)
        }
        channels.second?.let { raw ->
            runCatching { raw.close() }.exceptionOrNull()?.let(failures::add)
        }
        return failures
    }
}

private suspend inline fun <Value> cancellationSafeHandoff(
    value: Value,
    crossinline closeIfUndelivered: (Value) -> Unit,
): Value = suspendCancellableCoroutine { continuation ->
    continuation.resume(value) { _, undelivered, _ ->
        runCatching { closeIfUndelivered(undelivered) }
    }
}

private class ManagedRuntimeRawFrameBodyChannel(
    private val delegate: RuntimeRawFrameBodyChannel,
) : RuntimeRawFrameBodyChannel {
    private val closed = AtomicBoolean(false)

    override val isConnected: Boolean
        get() = !closed.get() && delegate.isConnected

    override val transportSecurityContext: TransportSecurityContext?
        get() = if (closed.get()) null else delegate.transportSecurityContext

    override suspend fun sendFrameBody(body: ByteArray) {
        checkOpen()
        delegate.sendFrameBody(body)
        checkOpen()
    }

    override suspend fun receiveFrameBody(): ByteArray {
        checkOpen()
        val body = delegate.receiveFrameBody()
        if (closed.get()) {
            body.fill(0)
            error("Production raw frame-body channel closed during receive")
        }
        return body
    }

    override fun close() {
        if (closed.compareAndSet(false, true)) delegate.close()
    }

    private fun checkOpen() {
        check(!closed.get()) { "Production raw frame-body channel is closed" }
    }
}

internal fun productionCompositionTimeoutMillis(
    rawRouteTimeoutMillis: Long,
    handshakeBudgetMillis: Long,
): Long {
    require(rawRouteTimeoutMillis > 0L) { "Raw route timeout must be positive" }
    require(handshakeBudgetMillis > 0L) { "Handshake budget must be positive" }
    return if (rawRouteTimeoutMillis > Long.MAX_VALUE - handshakeBudgetMillis) {
        Long.MAX_VALUE
    } else {
        rawRouteTimeoutMillis + handshakeBudgetMillis
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

private fun RuntimeRouteCandidate.hasProductionSession(): Boolean =
    productionSessionOrNull() != null

private fun RuntimeRouteCandidate.productionSessionOrNull(): PreparedProductionSecureSession? =
    when (this) {
        is RuntimeRouteCandidate.PeerToPeer -> preparedRoute?.productionSession
        is RuntimeRouteCandidate.Relay -> preparedRoute?.productionSession
        is RuntimeRouteCandidate.DirectTcp, is RuntimeRouteCandidate.LocalDirect -> null
    }

private fun RuntimeRouteCandidate.preparedRemoteIdentityOrNull(): PairedRuntimeIdentity? =
    when (this) {
        is RuntimeRouteCandidate.PeerToPeer -> preparedRoute?.identity
        is RuntimeRouteCandidate.Relay -> preparedRoute?.identity
        is RuntimeRouteCandidate.DirectTcp, is RuntimeRouteCandidate.LocalDirect -> null
    }

private fun RuntimeRouteCandidate.preparedRemoteSecurityOrNull(): RemoteRouteSecurityContext? =
    when (this) {
        is RuntimeRouteCandidate.PeerToPeer -> preparedRoute?.security
        is RuntimeRouteCandidate.Relay -> preparedRoute?.security
        is RuntimeRouteCandidate.DirectTcp, is RuntimeRouteCandidate.LocalDirect -> null
    }

private fun RuntimeRouteCandidate.matchesProductionRouteKind(
    kind: ProductionRouteAuthorizationKind,
): Boolean = when (this) {
    is RuntimeRouteCandidate.PeerToPeer -> kind == ProductionRouteAuthorizationKind.P2P_DIRECT
    is RuntimeRouteCandidate.Relay -> kind in setOf(
        ProductionRouteAuthorizationKind.TURN_RELAY,
        ProductionRouteAuthorizationKind.SEALED_RELAY,
    )
    is RuntimeRouteCandidate.DirectTcp,
    is RuntimeRouteCandidate.LocalDirect,
    -> false
}

private fun RuntimeRouteCandidate.hasExactProductionRouteBinding(
    session: PreparedProductionSecureSession,
): Boolean = when (this) {
    is RuntimeRouteCandidate.PeerToPeer -> {
        val route = preparedRoute
        if (
            route?.sessionId != session.expectedSessionId ||
            session.expectedRouteAuthorizationKind != ProductionRouteAuthorizationKind.P2P_DIRECT
        ) {
            false
        } else if (!session.verifiedCandidateDerived) {
            true
        } else {
            val descriptor = route.verifiedCandidateDescriptor
            descriptor != null &&
                route.productionSession === session &&
                descriptor.sessionId == session.expectedSessionId &&
                descriptor.generation == session.transcript.generation &&
                descriptor.securityContextDigest ==
                    ProductionC1PreauthorizationSessionContext(session.transcript).digestHex() &&
                route.security.rendezvousToken == descriptor.descriptorDigest &&
                route.security.antiReplayNonce == descriptor.connectorInputCommitmentDigest &&
                descriptor.expiresAtMs <= Long.MAX_VALUE.toULong() &&
                route.security.expiresAtEpochMillis == descriptor.expiresAtMs.toLong()
        }
    }
    is RuntimeRouteCandidate.Relay -> false
    is RuntimeRouteCandidate.DirectTcp,
    is RuntimeRouteCandidate.LocalDirect,
    -> false
}

private fun PreparedRemoteRuntimeRoute.isBoundTo(
    candidateIdentity: PairedRuntimeIdentity,
    targetIdentity: PairedRuntimeIdentity?,
): Boolean {
    return identity.includesPinnedIdentity(candidateIdentity) &&
        (targetIdentity == null || identity.includesPinnedIdentity(targetIdentity))
}

private fun PreparedRemoteRuntimeRoute.usesPairingRouteTokenAsRouteMaterial(
    candidateIdentity: PairedRuntimeIdentity,
    targetIdentity: PairedRuntimeIdentity?,
): Boolean {
    val routeTokens = listOfNotNull(
        identity.routeToken,
        candidateIdentity.routeToken,
        targetIdentity?.routeToken,
    ).toSet()
    if (routeTokens.isEmpty()) return false
    return when (this) {
        is PreparedRemoteRuntimeRoute.PeerToPeer ->
            routeTokens.any { token ->
                sessionId == token || security.rendezvousToken == token
            }
        is PreparedRemoteRuntimeRoute.Relay ->
            routeTokens.any { token ->
                relayId == token || security.rendezvousToken == token
            }
    }
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
