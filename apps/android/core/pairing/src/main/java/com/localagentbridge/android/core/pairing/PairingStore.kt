package com.localagentbridge.android.core.pairing

import android.annotation.SuppressLint
import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import androidx.datastore.preferences.core.MutablePreferences
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.core.stringSetPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.localagentbridge.android.core.protocol.p2pnat.ProductionC1CandidateCASDisposition
import com.localagentbridge.android.core.protocol.p2pnat.ProductionC1CandidateCapabilityError
import com.localagentbridge.android.core.protocol.p2pnat.ProductionC1CandidateCapabilityException
import com.localagentbridge.android.core.protocol.p2pnat.ProductionC1EndpointCompoundRecord
import com.localagentbridge.android.core.protocol.p2pnat.ProductionC1EndpointGrantAdmissionPreparation
import com.localagentbridge.android.core.protocol.p2pnat.ProductionC1EndpointGrantLedgerState
import com.localagentbridge.android.core.protocol.p2pnat.ProductionC1AdmissionPreparation
import com.localagentbridge.android.core.protocol.p2pnat.ProductionC1Error
import com.localagentbridge.android.core.protocol.p2pnat.ProductionC1Exception
import com.localagentbridge.android.core.protocol.p2pnat.ProductionC1FreshPairStateMachine
import com.localagentbridge.android.core.protocol.p2pnat.ProductionC1PairStateAdmission
import com.localagentbridge.android.core.protocol.p2pnat.ProductionC1EndpointGrantAdmission
import com.localagentbridge.android.core.protocol.p2pnat.ReadbackConfirmedProductionC1EndpointGrantAdmission
import com.localagentbridge.android.core.protocol.p2pnat.ProductionPairStateAdmission
import com.localagentbridge.android.core.protocol.p2pnat.ProductionPairStateContract
import com.localagentbridge.android.core.protocol.p2pnat.ProductionPairStateException
import com.localagentbridge.android.core.protocol.p2pnat.ProductionPairStateMachine
import com.localagentbridge.android.core.protocol.p2pnat.ProductionPairStateRejectionReason
import com.localagentbridge.android.core.protocol.p2pnat.ProductionPairStateSnapshot
import com.localagentbridge.android.core.protocol.p2pnat.ProductionPairStateTransition
import com.localagentbridge.android.core.protocol.p2pnat.ProductionPairStateTransitionDisposition
import com.localagentbridge.android.core.protocol.p2pnat.ProductionPairAuthorityStatus
import com.localagentbridge.android.core.protocol.p2pnat.ProductionRouteAuthorization
import com.localagentbridge.android.core.protocol.p2pnat.ProductionRouteAuthorizationKind
import com.localagentbridge.android.core.protocol.p2pnat.ProductionSecureSessionTranscript
import com.localagentbridge.android.core.protocol.p2pnat.ProductionSecureSessionCodec
import com.localagentbridge.android.core.protocol.p2pnat.ProductionSecureSessionEphemeralKey
import com.localagentbridge.android.core.protocol.p2pnat.VerifiedProductionC1CandidateP2PTranscriptBinding
import com.localagentbridge.android.core.protocol.p2pnat.VerifiedProductionC1FreshPairTransition
import com.localagentbridge.android.core.protocol.p2pnat.VerifiedProductionC1TranscriptBinding
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.nio.ByteBuffer
import java.io.IOException
import java.security.KeyStore
import java.security.MessageDigest
import java.util.Base64
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey

internal val Context.localAgentBridgeDataStore by preferencesDataStore("local_agent_bridge")

private val verifiedProductionC1AdmissionPermitMint = Any()
private val productionPairAdmissionPermitMint = Any()

internal data class ProductionC1AuthorityPersistenceHooks(
    /** Runs after the in-memory edit has been populated but before DataStore confirms commit. */
    val afterEditEnqueued: (() -> Unit)? = null,
    /** Runs after DataStore commit and before old-authority engine fencing. */
    val afterCommitBeforeFence: (suspend () -> Unit)? = null,
)

internal class ProductionPairAdmissionPermit internal constructor(
    val bindingDigest: String,
    val sessionId: String,
    val transcriptDigest: String,
    val routeAuthorizationDigest: String,
    val pairAuthorityDigest: String,
    val previousPairSnapshotDigest: String,
    val pairSnapshotDigest: String,
    provenance: Any,
) {
    init {
        check(provenance === productionPairAdmissionPermitMint) {
            "Production pair admission permit provenance mismatch"
        }
        listOf(
            bindingDigest,
            transcriptDigest,
            routeAuthorizationDigest,
            pairAuthorityDigest,
            previousPairSnapshotDigest,
            pairSnapshotDigest,
        ).forEach { digest ->
            check(digest.length == 64 && digest.all { it in '0'..'9' || it in 'a'..'f' })
        }
        check(sessionId.isNotBlank())
    }
}

/**
 * A process-local capability minted only after PairingStore has durably persisted and exactly
 * read back the replay tombstone under its trusted clock.  The protocol module intentionally
 * exposes only a non-authorizing preparation.
 */
class VerifiedProductionC1AdmissionPermit internal constructor(
    val bindingDigest: String,
    val sessionId: String,
    val transcriptDigest: String,
    val routeAuthorizationDigest: String,
    val routePlanDigest: String,
    val previousPairSnapshotDigest: String,
    val pairSnapshotDigest: String,
    val effectiveNotBeforeMs: ULong,
    val expiresAtMs: ULong,
    provenance: Any,
) {
    init {
        check(provenance === verifiedProductionC1AdmissionPermitMint) {
            "Verified production C1 admission permit provenance mismatch"
        }
        check(effectiveNotBeforeMs < expiresAtMs)
        listOf(
            bindingDigest,
            transcriptDigest,
            routeAuthorizationDigest,
            routePlanDigest,
            previousPairSnapshotDigest,
            pairSnapshotDigest,
        ).forEach { digest ->
            check(digest.length == 64 && digest.all { it in '0'..'9' || it in 'a'..'f' })
        }
        check(sessionId.isNotBlank())
    }

    override fun equals(other: Any?): Boolean =
        this === other ||
            (other is VerifiedProductionC1AdmissionPermit &&
                bindingDigest == other.bindingDigest &&
                sessionId == other.sessionId &&
                transcriptDigest == other.transcriptDigest &&
                routeAuthorizationDigest == other.routeAuthorizationDigest &&
                routePlanDigest == other.routePlanDigest &&
                previousPairSnapshotDigest == other.previousPairSnapshotDigest &&
                pairSnapshotDigest == other.pairSnapshotDigest &&
                effectiveNotBeforeMs == other.effectiveNotBeforeMs &&
                expiresAtMs == other.expiresAtMs)

    override fun hashCode(): Int = bindingDigest.hashCode()
}

class PairingStore private constructor(
    private val context: Context,
    private val relaySecretStore: DurableRelaySecretStore,
    private val endpointPersistenceHooks: ProductionC1EndpointPersistenceHooks,
    private val productionTrustedClock: ProductionC1TrustedClock,
    private val authorityPersistenceHooks: ProductionC1AuthorityPersistenceHooks,
) {
    private val productionC1ExactBoundStartCoordinator = lazy(LazyThreadSafetyMode.SYNCHRONIZED) {
        ProductionC1ExactBoundStartCoordinator.storeCached(this) { productionTrustedClock.nowMs() }
    }
    private val productionAuthorityPublicationGate = ProductionC1AuthorityPublicationGate()

    constructor(
        context: Context,
        relaySecretStore: DurableRelaySecretStore = AndroidKeystoreRelaySecretStore(context),
    ) : this(
        context,
        relaySecretStore,
        ProductionC1EndpointPersistenceHooks(),
        ProductionC1SystemTrustedClock,
        ProductionC1AuthorityPersistenceHooks(),
    )

    internal constructor(
        context: Context,
        relaySecretStore: DurableRelaySecretStore,
        endpointPersistenceHooks: ProductionC1EndpointPersistenceHooks,
        productionTrustedClock: ProductionC1TrustedClock = ProductionC1SystemTrustedClock,
        authorityPersistenceHooks: ProductionC1AuthorityPersistenceHooks =
            ProductionC1AuthorityPersistenceHooks(),
        @Suppress("UNUSED_PARAMETER") testing: Unit = Unit,
    ) : this(
        context,
        relaySecretStore,
        endpointPersistenceHooks,
        productionTrustedClock,
        authorityPersistenceHooks,
    )
    val trustedRuntime: Flow<TrustedRuntime?> = flow {
        context.localAgentBridgeDataStore.data.collect { prefs ->
            val loaded = loadTrustedRuntime(prefs)
            // Invalid stored identity cleanup is authority-replacing. Route it through the same
            // non-cancellable writer/fence path as an explicit forget instead of editing inline.
            if (loaded.shouldRemoveStoredTrustedRuntime) {
                forgetRuntime()
                emit(null)
                return@collect
            }
            val hasPendingSecretCleanup =
                !prefs[Keys.runtimeRelaySecretCleanupRefs].isNullOrEmpty()
            if (
                loaded.shouldRemoveStoredRouteToken ||
                loaded.shouldRemoveStoredRelayRoute ||
                loaded.shouldRemoveStoredP2pRoute ||
                loaded.shouldRemoveStoredDirectEndpoint ||
                loaded.relaySecretRefToPersist != null ||
                hasPendingSecretCleanup
            ) {
                val cleanupReferences = linkedSetOf<String>()
                var migratedSecretReference: String? = null
                try {
                    if (loaded.relaySecretRefToPersist != null) {
                        val secret = requireNotNull(loaded.relaySecretToPersist)
                        if (relaySecretStore.readSecret(loaded.relaySecretRefToPersist) != secret) {
                            migratedSecretReference = loaded.relaySecretRefToPersist
                            check(
                                relaySecretStore.saveSecretDurably(
                                    loaded.relaySecretRefToPersist,
                                    secret,
                                )
                            ) { "Trusted runtime relay secret migration failed" }
                        }
                    }
                    productionStatePersistenceMutex.withLock {
                        context.localAgentBridgeDataStore.edit { editPrefs ->
                            if (loaded.shouldRemoveStoredRouteToken) {
                                editPrefs.removeRouteTokenKeys()
                            }
                            if (loaded.shouldRemoveStoredRelayRoute) {
                                cleanupReferences += loaded.relaySecretRefsToRemove
                                editPrefs.removeRelayRouteKeys()
                            }
                            if (loaded.shouldRemoveStoredP2pRoute) {
                                editPrefs.removeP2pRouteKeys()
                            }
                            if (loaded.shouldRemoveStoredDirectEndpoint) {
                                editPrefs.removeDirectEndpointKeys()
                            }
                            if (loaded.relaySecretRefToPersist != null) {
                                editPrefs[Keys.runtimeRelaySecretRef]
                                    ?.takeIf { it != loaded.relaySecretRefToPersist }
                                    ?.takeIf(::isOwnedTrustedRelaySecretReference)
                                    ?.let(cleanupReferences::add)
                                editPrefs[Keys.runtimeRelaySecretRef] = loaded.relaySecretRefToPersist
                                editPrefs.remove(Keys.runtimeRelaySecret)
                            }
                            editPrefs.enqueueRelaySecretCleanup(cleanupReferences)
                        }
                    }
                } catch (error: Throwable) {
                    val uncommittedReference = migratedSecretReference
                        ?.takeIf { it != prefs[Keys.runtimeRelaySecretRef] }
                    if (uncommittedReference != null) {
                        compensateUncommittedRelaySecret(uncommittedReference)
                    }
                    throw error
                }
                drainRelaySecretCleanup()
            }
            emit(loaded.trustedRuntime)
        }
    }

    private fun loadTrustedRuntime(prefs: Preferences): LoadedTrustedRuntime {
        val hasStoredRelayRoute = prefs.hasStoredRelayRoute()
        val hasStoredP2pRoute = prefs.hasStoredP2pRoute()
        val hasStoredDirectEndpoint = prefs.hasStoredDirectEndpoint()
        val rawId = prefs[Keys.runtimeDeviceId] ?: prefs[LegacyKeys.runtimeDeviceId]
            ?: return LoadedTrustedRuntime(
                null,
                shouldRemoveStoredRelayRoute = false,
                shouldRemoveStoredP2pRoute = hasStoredP2pRoute,
                shouldRemoveStoredDirectEndpoint = hasStoredDirectEndpoint,
            )
        val id = rawId.takeIf(::isCanonicalOpaqueRouteValue)
            ?: return invalidStoredTrustedRuntime()
        val name = prefs[Keys.runtimeName] ?: prefs[LegacyKeys.runtimeName] ?: "AetherLink Runtime"
        val rawFingerprint = prefs[Keys.runtimeFingerprint] ?: prefs[LegacyKeys.runtimeFingerprint]
            ?: return LoadedTrustedRuntime(
                null,
                shouldRemoveStoredRelayRoute = false,
                shouldRemoveStoredP2pRoute = hasStoredP2pRoute,
                shouldRemoveStoredDirectEndpoint = hasStoredDirectEndpoint,
            )
        val fingerprint = rawFingerprint.takeIf(::isCanonicalOpaqueRouteValue)
            ?: return invalidStoredTrustedRuntime()
        val rawPublicKeyBase64 = prefs[Keys.runtimePublicKey] ?: prefs[LegacyKeys.runtimePublicKey]
        val publicKeyBase64 = rawPublicKeyBase64?.takeIf(::isCanonicalOpaqueRouteValue)
        if (rawPublicKeyBase64 != null && publicKeyBase64 == null) {
            return invalidStoredTrustedRuntime()
        }
        val rawRouteToken = prefs[Keys.runtimeRouteToken] ?: prefs[LegacyKeys.runtimeRouteToken]
        val routeToken = rawRouteToken?.takeIf(::isCanonicalOpaqueRouteValue)
        val shouldRemoveStoredRouteToken = rawRouteToken != null && routeToken == null
        val relayHost = prefs[Keys.runtimeRelayHost]
        val relayPort = prefs[Keys.runtimeRelayPort]
        val relayId = prefs[Keys.runtimeRelayId]
        val relaySecretRef = prefs[Keys.runtimeRelaySecretRef]
        val legacyRelaySecret = prefs[Keys.runtimeRelaySecret]
        val relaySecret = relaySecretRef
            ?.let(relaySecretStore::readSecret)
            ?: legacyRelaySecret
        val relayExpiresAtEpochMillis = prefs[Keys.runtimeRelayExpiresAtEpochMillis]
        val relayNonce = prefs[Keys.runtimeRelayNonce]
        val relayScope = prefs[Keys.runtimeRelayScope]
        val relayTicketGeneration = prefs[Keys.runtimeRelayTicketGeneration]
        val p2pRouteClass = prefs[Keys.runtimeP2pRouteClass]
        val p2pRecordId = prefs[Keys.runtimeP2pRecordId]
        val p2pEncryptedBody = prefs[Keys.runtimeP2pEncryptedBody]
        val p2pExpiresAtEpochMillis = prefs[Keys.runtimeP2pExpiresAtEpochMillis]
        val p2pAntiReplayNonce = prefs[Keys.runtimeP2pAntiReplayNonce]
        val p2pProtocolVersion = prefs[Keys.runtimeP2pProtocolVersion]
        val productionPairStateLoadState = prefs.productionPairStateLoadStateForProjection(
            expectedRuntimeDeviceId = id,
            expectedRuntimeFingerprint = fingerprint,
            expectedRuntimePublicKey = publicKeyBase64,
        )
        val trusted = TrustedRuntime(
            deviceId = id,
            name = name,
            fingerprint = fingerprint,
            publicKeyBase64 = publicKeyBase64,
            routeToken = routeToken,
            host = null,
            port = null,
            relayHost = relayHost,
            relayPort = relayPort,
            relayId = relayId,
            relaySecret = relaySecret,
            relayExpiresAtEpochMillis = relayExpiresAtEpochMillis,
            relayNonce = relayNonce,
            relayScope = relayScope,
            relayTicketGeneration = relayTicketGeneration,
            p2pRouteClass = p2pRouteClass,
            p2pRecordId = p2pRecordId,
            p2pEncryptedBody = p2pEncryptedBody,
            p2pExpiresAtEpochMillis = p2pExpiresAtEpochMillis,
            p2pAntiReplayNonce = p2pAntiReplayNonce,
            p2pProtocolVersion = p2pProtocolVersion,
            productionPairStateLoadState = productionPairStateLoadState,
        )
        val trustedWithoutInvalidP2p = if (trusted.hasValidP2pRoute()) trusted else trusted.withoutP2pRoute()
        val shouldRemoveStoredP2pRoute = hasStoredP2pRoute && !trusted.hasValidP2pRoute()
        return if (trusted.hasValidRelayRoute()) {
            val relaySecretRefToPersist = if (!legacyRelaySecret.isNullOrBlank() || relaySecretRef.isNullOrBlank()) {
                relaySecretHandle(
                    deviceId = id,
                    relayId = requireNotNull(relayId),
                    relaySecret = requireNotNull(relaySecret),
                )
            } else {
                null
            }
            LoadedTrustedRuntime(
                trustedWithoutInvalidP2p,
                shouldRemoveStoredRouteToken = shouldRemoveStoredRouteToken,
                shouldRemoveStoredRelayRoute = false,
                shouldRemoveStoredP2pRoute = shouldRemoveStoredP2pRoute,
                shouldRemoveStoredDirectEndpoint = hasStoredDirectEndpoint,
                relaySecretRefToPersist = relaySecretRefToPersist,
                relaySecretToPersist = relaySecret?.takeIf { relaySecretRefToPersist != null },
                relaySecretRefsToRemove = listOfNotNull(
                    relaySecretRef
                        ?.takeIf { it != relaySecretRefToPersist }
                        ?.takeIf(::isOwnedTrustedRelaySecretReference),
                ),
            )
        } else {
            LoadedTrustedRuntime(
                trustedWithoutInvalidP2p.withoutRelayRoute(),
                shouldRemoveStoredRouteToken = shouldRemoveStoredRouteToken,
                shouldRemoveStoredRelayRoute = hasStoredRelayRoute,
                shouldRemoveStoredP2pRoute = shouldRemoveStoredP2pRoute,
                shouldRemoveStoredDirectEndpoint = hasStoredDirectEndpoint,
                relaySecretRefsToRemove = listOfNotNull(
                    relaySecretRef?.takeIf(::isOwnedTrustedRelaySecretReference),
                ),
            )
        }
    }

    suspend fun trustRuntime(runtime: TrustedRuntime) {
        val deviceId = runtime.deviceId.takeIf(::isCanonicalOpaqueRouteValue)
        val fingerprint = runtime.fingerprint.takeIf(::isCanonicalOpaqueRouteValue)
        val rawPublicKeyBase64 = runtime.publicKeyBase64
        val publicKeyBase64 = rawPublicKeyBase64
            ?.takeIf { it.isNotBlank() }
            ?.takeIf(::isCanonicalOpaqueRouteValue)
        val hasInvalidPublicKeyBase64 = !rawPublicKeyBase64.isNullOrBlank() && publicKeyBase64 == null
        val cleanupReferences = linkedSetOf<String>()
        var previousSecretReference: String? = null
        var attemptedSecretReference: String? = null
        try {
            productionStatePersistenceMutex.withLock {
                context.localAgentBridgeDataStore.edit { prefs ->
                    previousSecretReference = prefs[Keys.runtimeRelaySecretRef]
                        ?.takeIf(::isOwnedTrustedRelaySecretReference)
                    prefs.requireSafeProductionPairStateTrustWrite(
                        incomingDeviceId = deviceId,
                        incomingFingerprint = fingerprint,
                        incomingPublicKey = publicKeyBase64,
                        incomingState = runtime.productionPairStateLoadState,
                    )
                    if (deviceId == null || fingerprint == null || hasInvalidPublicKeyBase64) {
                        previousSecretReference?.let(cleanupReferences::add)
                        prefs.enqueueRelaySecretCleanup(cleanupReferences)
                        prefs.removeRuntimeKeys()
                        prefs.removeLegacyRuntimeKeys()
                        return@edit
                    }
                prefs[Keys.runtimeDeviceId] = deviceId
                prefs[Keys.runtimeName] = runtime.name
                prefs[Keys.runtimeFingerprint] = fingerprint
                if (publicKeyBase64 != null) {
                    prefs[Keys.runtimePublicKey] = publicKeyBase64
                } else {
                    prefs.remove(Keys.runtimePublicKey)
                }
                val routeToken = runtime.routeToken?.takeIf(::isCanonicalOpaqueRouteValue)
                if (routeToken != null) {
                    prefs[Keys.runtimeRouteToken] = routeToken
                } else {
                    prefs.removeRouteTokenKeys()
                }
                prefs.removeDirectEndpointKeys()
                val relayHost = runtime.relayHost
                val relayPort = runtime.relayPort
                val relayId = runtime.relayId
                val relaySecret = runtime.relaySecret
                val relayScope = runtime.relayScope
                if (runtime.hasValidRelayRoute()) {
                    val cleanRelayId = requireNotNull(relayId)
                    val cleanRelaySecret = requireNotNull(relaySecret)
                    val reference = relaySecretHandle(
                        deviceId = runtime.deviceId,
                        relayId = cleanRelayId,
                        relaySecret = cleanRelaySecret,
                    )
                    if (relaySecretStore.readSecret(reference) != cleanRelaySecret) {
                        attemptedSecretReference = reference
                        check(relaySecretStore.saveSecretDurably(reference, cleanRelaySecret)) {
                            "Trusted runtime relay secret persistence failed"
                        }
                    }
                    prefs[Keys.runtimeRelayHost] = requireNotNull(relayHost)
                    prefs[Keys.runtimeRelayPort] = requireNotNull(relayPort)
                    prefs[Keys.runtimeRelayId] = cleanRelayId
                    prefs[Keys.runtimeRelaySecretRef] = reference
                    prefs.remove(Keys.runtimeRelaySecret)
                    previousSecretReference
                        ?.takeIf { it != reference }
                        ?.let(cleanupReferences::add)
                    val relayExpiresAtEpochMillis = runtime.relayExpiresAtEpochMillis
                    if (relayExpiresAtEpochMillis != null && relayExpiresAtEpochMillis > 0L) {
                        prefs[Keys.runtimeRelayExpiresAtEpochMillis] = relayExpiresAtEpochMillis
                    } else {
                        prefs.remove(Keys.runtimeRelayExpiresAtEpochMillis)
                    }
                    val relayNonce = runtime.relayNonce
                    if (!relayNonce.isNullOrBlank()) {
                        prefs[Keys.runtimeRelayNonce] = relayNonce
                    } else {
                        prefs.remove(Keys.runtimeRelayNonce)
                    }
                    if (!relayScope.isNullOrBlank()) {
                        prefs[Keys.runtimeRelayScope] = relayScope
                    } else {
                        prefs.remove(Keys.runtimeRelayScope)
                    }
                    val relayTicketGeneration = runtime.relayTicketGeneration
                    if (relayTicketGeneration != null && relayTicketGeneration > 0L) {
                        prefs[Keys.runtimeRelayTicketGeneration] = relayTicketGeneration
                    } else {
                        prefs.remove(Keys.runtimeRelayTicketGeneration)
                    }
                } else {
                    previousSecretReference?.let(cleanupReferences::add)
                    prefs.removeRelayRouteKeys()
                }
                if (runtime.hasValidP2pRoute()) {
                    prefs[Keys.runtimeP2pRouteClass] = requireNotNull(runtime.p2pRouteClass)
                    prefs[Keys.runtimeP2pRecordId] = requireNotNull(runtime.p2pRecordId)
                    prefs[Keys.runtimeP2pEncryptedBody] = requireNotNull(runtime.p2pEncryptedBody)
                    prefs[Keys.runtimeP2pExpiresAtEpochMillis] = requireNotNull(runtime.p2pExpiresAtEpochMillis)
                    prefs[Keys.runtimeP2pAntiReplayNonce] = requireNotNull(runtime.p2pAntiReplayNonce)
                    prefs[Keys.runtimeP2pProtocolVersion] = requireNotNull(runtime.p2pProtocolVersion)
                } else {
                    prefs.removeP2pRouteKeys()
                }
                    prefs.removeLegacyRuntimeKeys()
                    prefs.enqueueRelaySecretCleanup(cleanupReferences)
                }
            }
        } catch (error: Throwable) {
            val uncommittedReference = attemptedSecretReference
                ?.takeIf { it != previousSecretReference }
            if (uncommittedReference != null) {
                compensateUncommittedRelaySecret(uncommittedReference)
            }
            throw error
        }
        drainRelaySecretCleanup()
    }

    @JvmSynthetic
    internal suspend fun applyVerifiedProductionPairTransition(
        expectedRuntimeDeviceId: String,
        expectedRuntimeFingerprint: String,
        transition: ProductionPairStateTransition,
    ): ProductionPairStateSnapshot = productionAuthorityPublicationGate.withWrite {
        var previousAuthorityDigest: String? = null
        var persistenceAttempted = false
        val snapshot = try {
            productionStatePersistenceMutex.withLock {
                val before = context.localAgentBridgeDataStore.data.first()
                before.requireExpectedRuntimeIdentity(
                    expectedRuntimeDeviceId = expectedRuntimeDeviceId,
                    expectedRuntimeFingerprint = expectedRuntimeFingerprint,
                )
                val current = before.productionPairStateStrict(
                    expectedRuntimeDeviceId,
                    expectedRuntimeFingerprint,
                )
                previousAuthorityDigest = current?.authority?.digestHex()
                check(
                    current?.authority?.runtimeIdentityFingerprint?.let { it == expectedRuntimeFingerprint }
                        ?: (transition.nextAuthority.runtimeIdentityFingerprint == expectedRuntimeFingerprint)
                ) {
                    "Production pair state runtime identity mismatch"
                }
                val result = ProductionPairStateMachine.apply(
                    transition = transition,
                    current = current,
                )
                if (result.disposition == ProductionPairStateTransitionDisposition.APPLIED) {
                    context.localAgentBridgeDataStore.edit { prefs ->
                        prefs.requireExpectedRuntimeIdentity(
                            expectedRuntimeDeviceId,
                            expectedRuntimeFingerprint,
                        )
                        check(
                            prefs.productionPairStateStrict(
                                expectedRuntimeDeviceId,
                                expectedRuntimeFingerprint,
                            ) == current,
                        ) { "Production pair state changed during authority commit" }
                        persistenceAttempted = true
                        prefs[Keys.runtimeProductionPairState] = result.snapshot.canonicalBase64()
                        prefs.remove(Keys.runtimeProductionEndpointCompoundState)
                        authorityPersistenceHooks.afterEditEnqueued?.invoke()
                    }
                    authorityPersistenceHooks.afterCommitBeforeFence?.invoke()
                }
                result.snapshot
            }
        } catch (error: Throwable) {
            if (persistenceAttempted || error is IOException) {
                runCatching {
                    fenceExactBoundStartAfterAmbiguousAuthorityMutation(previousAuthorityDigest)
                }.exceptionOrNull()?.let(error::addSuppressed)
            }
            throw error
        }
        fenceExactBoundStartAfterAuthorityMutation(previousAuthorityDigest, snapshot)
        snapshot
    }

    suspend fun applyVerifiedProductionC1FreshPairTransition(
        expectedRuntimeDeviceId: String,
        expectedRuntimeFingerprint: String,
        transition: VerifiedProductionC1FreshPairTransition,
    ): ProductionPairStateSnapshot = productionAuthorityPublicationGate.withWrite {
        var previousAuthorityDigest: String? = null
        var persistenceAttempted = false
        val snapshot = try {
            productionStatePersistenceMutex.withLock {
                val before = context.localAgentBridgeDataStore.data.first()
                before.requireExpectedRuntimeIdentity(
                    expectedRuntimeDeviceId = expectedRuntimeDeviceId,
                    expectedRuntimeFingerprint = expectedRuntimeFingerprint,
                )
                val current = before.productionPairStateStrict(
                    expectedRuntimeDeviceId,
                    expectedRuntimeFingerprint,
                ) ?: throw ProductionPairStateException(
                    ProductionPairStateRejectionReason.MISSING_CURRENT_STATE,
                )
                previousAuthorityDigest = current.authority.digestHex()
                check(
                    current.authority.runtimeIdentityFingerprint == expectedRuntimeFingerprint &&
                        transition.applyPreparation.nextSnapshot.authority.runtimeIdentityFingerprint ==
                        expectedRuntimeFingerprint
                ) {
                    "Production pair state runtime identity mismatch"
                }
                val result = ProductionC1FreshPairStateMachine.apply(
                    verified = transition,
                    current = current,
                    nowMs = productionTrustedClock.nowMs(),
                )
                if (result.disposition == ProductionPairStateTransitionDisposition.APPLIED) {
                    context.localAgentBridgeDataStore.edit { prefs ->
                        prefs.requireExpectedRuntimeIdentity(
                            expectedRuntimeDeviceId,
                            expectedRuntimeFingerprint,
                        )
                        check(
                            prefs.productionPairStateStrict(
                                expectedRuntimeDeviceId,
                                expectedRuntimeFingerprint,
                            ) == current,
                        ) { "Production pair state changed during verified authority commit" }
                        persistenceAttempted = true
                        prefs[Keys.runtimeProductionPairState] = result.snapshot.canonicalBase64()
                        prefs.remove(Keys.runtimeProductionEndpointCompoundState)
                        authorityPersistenceHooks.afterEditEnqueued?.invoke()
                    }
                    authorityPersistenceHooks.afterCommitBeforeFence?.invoke()
                }
                result.snapshot
            }
        } catch (error: Throwable) {
            if (persistenceAttempted || error is IOException) {
                runCatching {
                    fenceExactBoundStartAfterAmbiguousAuthorityMutation(previousAuthorityDigest)
                }.exceptionOrNull()?.let(error::addSuppressed)
            }
            throw error
        }
        fenceExactBoundStartAfterAuthorityMutation(previousAuthorityDigest, snapshot)
        snapshot
    }

    @JvmSynthetic
    internal suspend fun admitProductionSecureSession(
        expectedRuntimeDeviceId: String,
        expectedRuntimeFingerprint: String,
        transcript: ProductionSecureSessionTranscript,
        routeAuthorization: ProductionRouteAuthorization,
    ): ProductionPairAdmissionPermit {
        return productionStatePersistenceMutex.withLock {
            var preparation: com.localagentbridge.android.core.protocol.p2pnat.ProductionPairAdmissionPreparation? = null
            var expectedCommittedEncoding: String? = null
            context.localAgentBridgeDataStore.edit { prefs ->
                prefs.requireExpectedRuntimeIdentity(
                    expectedRuntimeDeviceId = expectedRuntimeDeviceId,
                    expectedRuntimeFingerprint = expectedRuntimeFingerprint,
                )
                val current = prefs.productionPairStateStrict(
                    expectedRuntimeDeviceId,
                    expectedRuntimeFingerprint,
                ) ?: throw ProductionPairStateException(
                    ProductionPairStateRejectionReason.MISSING_CURRENT_STATE
                )
                val prepared = ProductionPairStateAdmission.admit(
                    transcript = transcript,
                    routeAuthorization = routeAuthorization,
                    current = current,
                )
                val nextEncoding = prepared.snapshot.canonicalBase64()
                preparation = prepared
                expectedCommittedEncoding = nextEncoding
                prefs[Keys.runtimeProductionPairState] = nextEncoding
                prefs.remove(Keys.runtimeProductionEndpointCompoundState)
            }
            val prepared = checkNotNull(preparation) {
                "Production secure-session admission was not prepared"
            }
            val readbackPrefs = context.localAgentBridgeDataStore.data.first()
            readbackPrefs.requireExpectedRuntimeIdentity(
                expectedRuntimeDeviceId,
                expectedRuntimeFingerprint,
            )
            val readbackEncoding = readbackPrefs[Keys.runtimeProductionPairState]
            check(
                readbackPrefs[Keys.runtimeProductionEndpointCompoundState] == null &&
                    readbackEncoding == checkNotNull(expectedCommittedEncoding)
            ) {
                "Production secure-session exact readback mismatch"
            }
            val exactReadback = checkNotNull(readbackEncoding).decodeProductionPairStateStrict()
            check(
                exactReadback == prepared.snapshot &&
                    exactReadback.authority.digestHex() == prepared.pairAuthorityDigest &&
                    exactReadback.digestHex() == prepared.pairSnapshotDigest &&
                    exactReadback.consumedEntries.any {
                        it.sessionId == prepared.sessionId &&
                            it.transcriptDigest == prepared.transcriptDigest
                    }
            ) {
                "Production secure-session replay tombstone readback mismatch"
            }
            ProductionPairAdmissionPermit(
                bindingDigest = prepared.bindingDigest,
                sessionId = prepared.sessionId,
                transcriptDigest = prepared.transcriptDigest,
                routeAuthorizationDigest = prepared.routeAuthorizationDigest,
                pairAuthorityDigest = prepared.pairAuthorityDigest,
                previousPairSnapshotDigest = prepared.previousPairSnapshotDigest,
                pairSnapshotDigest = prepared.pairSnapshotDigest,
                provenance = productionPairAdmissionPermitMint,
            )
        }
    }

    suspend fun admitVerifiedProductionC1SecureSession(
        expectedRuntimeDeviceId: String,
        expectedRuntimeFingerprint: String,
        binding: VerifiedProductionC1TranscriptBinding,
    ): VerifiedProductionC1AdmissionPermit = productionStatePersistenceMutex.withLock {
        var preparation: ProductionC1AdmissionPreparation? = null
        var expectedCommittedEncoding: String? = null
        var committedAtMs: ULong? = null
        context.localAgentBridgeDataStore.edit { prefs ->
            prefs.requireExpectedRuntimeIdentity(
                expectedRuntimeDeviceId = expectedRuntimeDeviceId,
                expectedRuntimeFingerprint = expectedRuntimeFingerprint,
            )
            val current = prefs.productionPairStateStrict(
                expectedRuntimeDeviceId,
                expectedRuntimeFingerprint,
            ) ?: throw ProductionPairStateException(
                ProductionPairStateRejectionReason.MISSING_CURRENT_STATE,
            )
            check(current.authority.runtimeIdentityFingerprint == expectedRuntimeFingerprint) {
                "Production pair state runtime identity mismatch"
            }
            val prepared = ProductionC1PairStateAdmission.admit(
                binding = binding,
                snapshot = current,
            )
            val nextEncoding = prepared.nextSnapshot.canonicalBase64()
            val commitNowMs = productionTrustedClock.nowMs()
            requireProductionC1AdmissionWindow(prepared, commitNowMs)
            committedAtMs = commitNowMs
            preparation = prepared
            expectedCommittedEncoding = nextEncoding
            prefs[Keys.runtimeProductionPairState] = nextEncoding
            prefs.remove(Keys.runtimeProductionEndpointCompoundState)
        }

        val prepared = checkNotNull(preparation) {
            "Verified production C1 secure-session admission was not prepared"
        }
        val expectedEncoding = checkNotNull(expectedCommittedEncoding)
        val readbackPrefs = context.localAgentBridgeDataStore.data.first()
        readbackPrefs.requireExpectedRuntimeIdentity(
            expectedRuntimeDeviceId,
            expectedRuntimeFingerprint,
        )
        val readbackEncoding = readbackPrefs[Keys.runtimeProductionPairState]
        check(
            readbackPrefs[Keys.runtimeProductionEndpointCompoundState] == null &&
                readbackEncoding == expectedEncoding
        ) {
            "Verified production C1 secure-session exact readback mismatch"
        }
        val exactReadback = checkNotNull(readbackEncoding).decodeProductionPairStateStrict()
        check(
            exactReadback == prepared.nextSnapshot &&
                exactReadback.digestHex() == prepared.pairSnapshotDigest &&
                exactReadback.consumedEntries.any {
                    it.sessionId == prepared.sessionId &&
                        it.transcriptDigest == prepared.transcriptDigest
                }
        ) {
            "Verified production C1 secure-session replay tombstone readback mismatch"
        }

        val tokenNowMs = productionTrustedClock.nowMs()
        val precommitNowMs = checkNotNull(committedAtMs)
        if (tokenNowMs < precommitNowMs) {
            throw ProductionC1Exception(ProductionC1Error.STATE_MISMATCH)
        }
        requireProductionC1AdmissionWindow(prepared, tokenNowMs)
        VerifiedProductionC1AdmissionPermit(
            bindingDigest = prepared.bindingDigest,
            sessionId = prepared.sessionId,
            transcriptDigest = prepared.transcriptDigest,
            routeAuthorizationDigest = prepared.routeAuthorizationDigest,
            routePlanDigest = prepared.routePlanDigest,
            previousPairSnapshotDigest = prepared.previousPairSnapshotDigest,
            pairSnapshotDigest = prepared.pairSnapshotDigest,
            effectiveNotBeforeMs = prepared.effectiveNotBeforeMs,
            expiresAtMs = prepared.expiresAtMs,
            provenance = verifiedProductionC1AdmissionPermitMint,
        )
    }

    /**
     * Verifies, persists, and readbacks one current endpoint grant, returning only the fresh
     * process-local start token. Historical readback never mints start authority.
     */
    suspend fun admitVerifiedProductionC1EndpointGrant(
        expectedRuntimeDeviceId: String,
        expectedRuntimeFingerprint: String,
        expectedRuntimePublicKey: String,
        admissionId: String,
        binding: VerifiedProductionC1CandidateP2PTranscriptBinding,
    ): ProductionC1EndpointGrantCompoundCommitToken {
        val (currentPair, currentLedger) = productionStatePersistenceMutex.withLock {
            val prefs = context.localAgentBridgeDataStore.data.first()
            prefs.requireExpectedRuntimeIdentity(
                expectedRuntimeDeviceId,
                expectedRuntimeFingerprint,
            )
            check(prefs[Keys.runtimePublicKey] == expectedRuntimePublicKey) {
                "Trusted runtime public key mismatch"
            }
            val pair = prefs.productionPairStateStrict(
                expectedRuntimeDeviceId,
                expectedRuntimeFingerprint,
            ) ?: throw ProductionPairStateException(
                ProductionPairStateRejectionReason.MISSING_CURRENT_STATE,
            )
            val stored = prefs[Keys.runtimeProductionEndpointCompoundState]
                ?.decodeProductionEndpointCompoundStrict()
                ?.also { it.requireRuntimeIdentity(expectedRuntimeDeviceId, expectedRuntimePublicKey) }
            pair to (stored?.ledger ?: bootstrapEndpointLedger(pair))
        }

        val transcript = binding.transcript
        val evidence = binding.grant.evidence
        val transcriptDigest = exactBoundStartDigestHex(
            ProductionSecureSessionCodec.encode(transcript),
        )
        val routeAuthorizationDigest = exactBoundStartDigestHex(
            ProductionSecureSessionCodec.encode(binding.grant.routeAuthorizations.finalP2PDirect),
        )
        val bindingDigest = ProductionC1EndpointGrantAdmission.bindingDigest(
            admissionId = admissionId,
            routeGrantDigest = evidence.digestHex(),
            transcriptDigest = transcriptDigest,
            routeAuthorizationDigest = routeAuthorizationDigest,
            grantAuthorizationDigest = binding.grant.grantAuthorization.digestHex,
            connectorInputCommitmentDigest = binding.connectorInput.commitmentDigest,
        )
        val preparation = ProductionC1EndpointGrantAdmission.prepareForTrustedPersistence(
            state = currentLedger,
            expectedRevision = currentLedger.revision,
            expectedSnapshotDigest = currentLedger.snapshotDigestHex(),
            admissionId = admissionId,
            bindingDigest = bindingDigest,
            verifiedBinding = binding,
            currentPairSnapshot = currentPair,
            nowMs = productionTrustedClock.nowMs(),
        )
        return when (val outcome = commitPreparedProductionC1EndpointGrant(
            expectedRuntimeDeviceId,
            expectedRuntimeFingerprint,
            expectedRuntimePublicKey,
            preparation,
        )) {
            is ProductionC1EndpointGrantCommitOutcome.Committed -> outcome.token
            is ProductionC1EndpointGrantCommitOutcome.AlreadyCommitted ->
                throw ProductionC1CandidateCapabilityException(
                    ProductionC1CandidateCapabilityError.REPLAY,
                )
        }
    }

    internal suspend fun commitPreparedProductionC1EndpointGrant(
        expectedRuntimeDeviceId: String,
        expectedRuntimeFingerprint: String,
        expectedRuntimePublicKey: String,
        preparation: ProductionC1EndpointGrantAdmissionPreparation,
    ): ProductionC1EndpointGrantCommitOutcome = productionStatePersistenceMutex.withLock {
        var precommitNowMs: ULong? = null
        var expectedCommittedEncoding: String? = null
        var committedMarker: StoredProductionC1EndpointCommitMarker? = null
        var committedState: StoredProductionC1EndpointCompoundState? = null
        var alreadyCommitted: ProductionC1EndpointGrantCommitReadback? = null

        context.localAgentBridgeDataStore.edit { prefs ->
            prefs.requireExpectedRuntimeIdentity(
                expectedRuntimeDeviceId,
                expectedRuntimeFingerprint,
            )
            check(prefs[Keys.runtimePublicKey] == expectedRuntimePublicKey) {
                "Trusted runtime public key mismatch"
            }
            val currentPair = prefs.productionPairStateStrict(
                expectedRuntimeDeviceId,
                expectedRuntimeFingerprint,
            ) ?: throw ProductionPairStateException(
                ProductionPairStateRejectionReason.MISSING_CURRENT_STATE,
            )
            val currentStored = prefs[Keys.runtimeProductionEndpointCompoundState]
                ?.decodeProductionEndpointCompoundStrict()
                ?.also { it.requireRuntimeIdentity(expectedRuntimeDeviceId, expectedRuntimePublicKey) }
            val currentLedger = currentStored?.ledger ?: bootstrapEndpointLedger(currentPair)
            val currentCompound = ProductionC1EndpointCompoundRecord(
                grantLedger = currentLedger,
                pairSnapshot = currentPair,
            )
            endpointCommitRequire(
                preparation.expectedRevision == currentLedger.revision &&
                    preparation.expectedSnapshotDigest == currentLedger.snapshotDigestHex() &&
                    preparation.expectedPairSnapshotDigest == currentPair.digestHex() &&
                    preparation.expectedCompoundDigest == currentCompound.digestHex(),
            )

            val markers = currentStored?.markers.orEmpty()
            if (preparation.disposition == ProductionC1CandidateCASDisposition.IDEMPOTENT) {
                val marker = markers.firstOrNull {
                    it.admissionId == preparation.entry.admissionId
                }
                endpointCommitRequire(
                    preparation.nextState == currentLedger &&
                        preparation.nextPairSnapshot == currentPair &&
                        preparation.nextCompoundRecord == currentCompound &&
                        marker != null &&
                        marker.bindingDigest == preparation.entry.bindingDigest &&
                        marker.sessionId == preparation.entry.sessionId &&
                        marker.routeAuthorizationDigest == preparation.entry.routeAuthorizationDigest &&
                        marker.grantAuthorizationDigest == preparation.entry.grantAuthorizationDigest &&
                        marker.pairAuthorityDigest == currentLedger.pairAuthorityDigest &&
                        marker.pairAuthorityDigest == currentPair.authority.digestHex() &&
                        marker.effectiveNotBeforeMs == preparation.effectiveNotBeforeMs &&
                        marker.expiresAtMs == preparation.expiresAtMs,
                    ProductionC1CandidateCapabilityError.REQUEST_CONFLICT,
                )
                alreadyCommitted = marker!!.toReadback()
                return@edit
            }

            endpointCommitRequire(
                preparation.disposition == ProductionC1CandidateCASDisposition.APPLIED &&
                    preparation.nextState.entries.size == currentLedger.entries.size + 1 &&
                    preparation.nextState.entries.lastOrNull() == preparation.entry &&
                    preparation.nextPairSnapshot == preparation.nextCompoundRecord.pairSnapshot &&
                    preparation.nextState == preparation.nextCompoundRecord.grantLedger &&
                    preparation.entry.committedRevision == preparation.nextState.revision &&
                    markers.size < ProductionC1EndpointCompoundPersistenceContract.MAX_MARKERS,
            )
            val nextCompoundDigest = preparation.nextCompoundRecord.digestHex()
            val marker = StoredProductionC1EndpointCommitMarker(
                sequence = (markers.size + 1).toUInt(),
                runtimeDeviceIdDigest = endpointRuntimeIdentityDigest(
                    "AetherLink trusted-runtime identifier v1",
                    expectedRuntimeDeviceId,
                ),
                trustedPublicKeyDigest = endpointRuntimeIdentityDigest(
                    "AetherLink trusted-runtime public key v1",
                    expectedRuntimePublicKey,
                ),
                admissionId = preparation.entry.admissionId,
                bindingDigest = preparation.entry.bindingDigest,
                endpointEntryDigest = endpointGrantEntryDigest(preparation.entry),
                sessionId = preparation.entry.sessionId,
                routeAuthorizationDigest = preparation.entry.routeAuthorizationDigest,
                grantAuthorizationDigest = preparation.entry.grantAuthorizationDigest,
                pairAuthorityDigest = preparation.nextState.pairAuthorityDigest,
                effectiveNotBeforeMs = preparation.effectiveNotBeforeMs,
                expiresAtMs = preparation.expiresAtMs,
                previousMarkerDigest = markers.lastOrNull()?.digestHex(),
                expectedCompoundDigest = preparation.expectedCompoundDigest,
                committedCompoundDigest = nextCompoundDigest,
                committedPairSnapshotDigest = preparation.nextPairSnapshot.digestHex(),
                committedLedgerSnapshotDigest = preparation.nextState.snapshotDigestHex(),
                pairLocalRevision = preparation.nextPairSnapshot.localRevision,
                ledgerRevision = preparation.nextState.revision,
            )
            val nextStored = StoredProductionC1EndpointCompoundState(
                pairSnapshot = preparation.nextPairSnapshot,
                ledger = preparation.nextState,
                markers = markers + marker,
            )
            val nextEncoding = nextStored.canonicalBase64()
            endpointPersistenceHooks.beforeCommit?.invoke()
            val commitNowMs = productionTrustedClock.nowMs()
            endpointCommitRequire(
                commitNowMs >= preparation.effectiveNotBeforeMs &&
                    commitNowMs < preparation.expiresAtMs,
                ProductionC1CandidateCapabilityError.ROUTE_MISMATCH,
            )
            precommitNowMs = commitNowMs
            prefs[Keys.runtimeProductionEndpointCompoundState] = nextEncoding
            prefs.remove(Keys.runtimeProductionPairState)
            expectedCommittedEncoding = nextEncoding
            committedMarker = marker
            committedState = nextStored
        }

        alreadyCommitted?.let {
            val exactReadback = readEndpointCompoundStateStrict(
                expectedRuntimeDeviceId,
                expectedRuntimeFingerprint,
                expectedRuntimePublicKey,
            )
            val marker = exactReadback.markers.firstOrNull { marker ->
                marker.admissionId == it.admissionId && marker.bindingDigest == it.bindingDigest
            } ?: throw ProductionC1EndpointPersistenceException(
                ProductionC1EndpointPersistenceFailure.READBACK_MISMATCH,
            )
            return@withLock ProductionC1EndpointGrantCommitOutcome.AlreadyCommitted(
                marker.toReadback(),
            )
        }

        endpointPersistenceHooks.afterCommitBeforeReadback?.invoke()
        val expectedEncoding = checkNotNull(expectedCommittedEncoding)
        val expectedState = checkNotNull(committedState)
        val marker = checkNotNull(committedMarker)
        val readbackPrefs = context.localAgentBridgeDataStore.data.first()
        val readbackEncoding = readbackPrefs[Keys.runtimeProductionEndpointCompoundState]
        if (
            readbackPrefs[Keys.runtimeProductionPairState] != null ||
            readbackEncoding != expectedEncoding
        ) {
            throw ProductionC1EndpointPersistenceException(
                ProductionC1EndpointPersistenceFailure.READBACK_MISMATCH,
            )
        }
        readbackPrefs.requireExpectedRuntimeIdentity(
            expectedRuntimeDeviceId,
            expectedRuntimeFingerprint,
        )
        check(readbackPrefs[Keys.runtimePublicKey] == expectedRuntimePublicKey) {
            "Trusted runtime public key mismatch"
        }
        val exactReadback = checkNotNull(readbackEncoding)
            .decodeProductionEndpointCompoundStrict()
            .also { it.requireRuntimeIdentity(expectedRuntimeDeviceId, expectedRuntimePublicKey) }
        if (
            !exactReadback.canonicalBytes().contentEquals(expectedState.canonicalBytes()) ||
            exactReadback.pairSnapshot != preparation.nextPairSnapshot ||
            exactReadback.ledger != preparation.nextState ||
            exactReadback.markers.lastOrNull() != marker
        ) {
            throw ProductionC1EndpointPersistenceException(
                ProductionC1EndpointPersistenceFailure.READBACK_MISMATCH,
            )
        }
        ReadbackConfirmedProductionC1EndpointGrantAdmission.confirm(
            preparation = preparation,
            committedCompoundReadback = ProductionC1EndpointCompoundRecord(
                grantLedger = exactReadback.ledger,
                pairSnapshot = exactReadback.pairSnapshot,
            ),
        )
        val committedAtMs = checkNotNull(precommitNowMs)
        val tokenNowMs = productionTrustedClock.nowMs()
        endpointCommitRequire(
            marker.effectiveNotBeforeMs == preparation.effectiveNotBeforeMs &&
                marker.expiresAtMs == preparation.expiresAtMs &&
                marker.sessionId == preparation.entry.sessionId &&
                marker.routeAuthorizationDigest == preparation.entry.routeAuthorizationDigest &&
                marker.grantAuthorizationDigest == preparation.entry.grantAuthorizationDigest &&
                marker.pairAuthorityDigest == preparation.nextState.pairAuthorityDigest &&
                marker.pairAuthorityDigest == preparation.nextPairSnapshot.authority.digestHex() &&
                tokenNowMs >= committedAtMs &&
                tokenNowMs >= preparation.effectiveNotBeforeMs &&
                tokenNowMs < preparation.expiresAtMs,
            ProductionC1CandidateCapabilityError.ROUTE_MISMATCH,
        )
        ProductionC1EndpointGrantCommitOutcome.Committed(
            ProductionC1EndpointGrantCompoundCommitToken(
                admissionId = preparation.entry.admissionId,
                bindingDigest = preparation.entry.bindingDigest,
                routeGrantDigest = preparation.entry.routeGrantDigest,
                sessionId = preparation.entry.sessionId,
                transcriptDigest = preparation.entry.transcriptDigest,
                routeAuthorizationDigest = preparation.entry.routeAuthorizationDigest,
                grantAuthorizationDigest = preparation.entry.grantAuthorizationDigest,
                pairAuthorityDigest = preparation.nextState.pairAuthorityDigest,
                connectorInputCommitmentDigest = preparation.entry.connectorInputCommitmentDigest,
                pairSnapshotDigest = preparation.entry.pairSnapshotDigest,
                ledgerSnapshotDigest = preparation.nextState.snapshotDigestHex(),
                compoundCommitDigest = preparation.nextCompoundRecord.digestHex(),
                effectiveNotBeforeMs = marker.effectiveNotBeforeMs,
                expiresAtMs = marker.expiresAtMs,
                pairLocalRevision = preparation.nextPairSnapshot.localRevision,
                ledgerRevision = preparation.nextState.revision,
                markerDigest = marker.digestHex(),
            ),
        )
    }

    suspend fun readProductionC1EndpointGrantCommit(
        expectedRuntimeDeviceId: String,
        expectedRuntimeFingerprint: String,
        expectedRuntimePublicKey: String,
        admissionId: String,
        bindingDigest: String,
    ): ProductionC1EndpointGrantCommitReadback? = productionStatePersistenceMutex.withLock {
        val prefs = context.localAgentBridgeDataStore.data.first()
        prefs.requireExpectedRuntimeIdentity(
            expectedRuntimeDeviceId,
            expectedRuntimeFingerprint,
        )
        check(prefs[Keys.runtimePublicKey] == expectedRuntimePublicKey) {
            "Trusted runtime public key mismatch"
        }
        check(prefs[Keys.runtimeProductionPairState] == null ||
            prefs[Keys.runtimeProductionEndpointCompoundState] == null) {
            "Conflicting production pair-state encodings"
        }
        val encoded = prefs[Keys.runtimeProductionEndpointCompoundState] ?: return@withLock null
        val state = encoded.decodeProductionEndpointCompoundStrict()
            .also { it.requireRuntimeIdentity(expectedRuntimeDeviceId, expectedRuntimePublicKey) }
        val marker = state.markers.firstOrNull { it.admissionId == admissionId } ?: return@withLock null
        endpointCommitRequire(
            marker.bindingDigest == bindingDigest,
            ProductionC1CandidateCapabilityError.REQUEST_CONFLICT,
        )
        marker.toReadback()
    }

    /**
     * Revalidates the one current, live endpoint-grant commit for a start attempt.
     *
     * This deliberately has no readback or AlreadyCommitted overload: an historical marker is
     * useful for diagnostics, but is never authority to start a route.
     */
    @JvmSynthetic
    internal suspend fun validateProductionC1ExactBoundStart(
        request: ProductionC1ExactBoundStartRequest,
    ): ProductionC1ExactBoundStartValidation = productionStatePersistenceMutex.withLock {
        val prefs = context.localAgentBridgeDataStore.data.first()
        prefs.requireExpectedRuntimeIdentity(
            request.expectedRuntimeDeviceId,
            request.expectedRuntimeFingerprint,
        )
        exactBoundStartRequire(
            prefs[Keys.runtimePublicKey] == request.expectedRuntimePublicKey,
            ProductionC1ExactBoundStartValidationFailure.IDENTITY_MISMATCH,
        )
        exactBoundStartRequire(
            prefs[Keys.runtimeProductionPairState] == null,
            ProductionC1ExactBoundStartValidationFailure.STALE_COMMIT,
        )
        val encoded = prefs[Keys.runtimeProductionEndpointCompoundState]
            ?: throw ProductionC1ExactBoundStartValidationException(
                ProductionC1ExactBoundStartValidationFailure.NO_CURRENT_COMMIT,
            )
        val state = try {
            encoded.decodeProductionEndpointCompoundStrict()
                .also {
                    it.requireRuntimeIdentity(
                        request.expectedRuntimeDeviceId,
                        request.expectedRuntimePublicKey,
                    )
                }
        } catch (error: ProductionC1ExactBoundStartValidationException) {
            throw error
        } catch (error: Throwable) {
            throw ProductionC1ExactBoundStartValidationException(
                ProductionC1ExactBoundStartValidationFailure.NO_CURRENT_COMMIT,
                error,
            )
        }

        val token = request.token
        val binding = request.binding
        val pair = state.pairSnapshot
        val ledger = state.ledger
        val entry = ledger.entries.lastOrNull()
            ?: throw ProductionC1ExactBoundStartValidationException(
                ProductionC1ExactBoundStartValidationFailure.NO_CURRENT_COMMIT,
            )
        val marker = state.markers.lastOrNull()
            ?: throw ProductionC1ExactBoundStartValidationException(
                ProductionC1ExactBoundStartValidationFailure.NO_CURRENT_COMMIT,
            )
        val authority = pair.authority
        exactBoundStartRequire(
            authority.status == ProductionPairAuthorityStatus.ACTIVE,
            ProductionC1ExactBoundStartValidationFailure.INACTIVE_PAIR_AUTHORITY,
        )
        exactBoundStartRequire(
            authority.runtimeIdentityFingerprint == request.expectedRuntimeFingerprint,
            ProductionC1ExactBoundStartValidationFailure.IDENTITY_MISMATCH,
        )

        val evidence = binding.grant.evidence
        val transcript = binding.transcript
        val routeGrantDigest = evidence.digestHex()
        val transcriptDigest = exactBoundStartDigestHex(
            ProductionSecureSessionCodec.encode(transcript),
        )
        val routeAuthorizationDigest = exactBoundStartDigestHex(
            ProductionSecureSessionCodec.encode(binding.grant.routeAuthorizations.finalP2PDirect),
        )
        val grantAuthorizationDigest = binding.grant.grantAuthorization.digestHex
        val connectorInputCommitmentDigest = binding.connectorInput.commitmentDigest
        val recomputedBindingDigest = ProductionC1EndpointGrantAdmission.bindingDigest(
            token.admissionId,
            routeGrantDigest,
            transcriptDigest,
            routeAuthorizationDigest,
            grantAuthorizationDigest,
            connectorInputCommitmentDigest,
        )
        val pairAuthorityDigest = authority.digestHex()
        val pairSnapshotDigest = pair.digestHex()
        val ledgerSnapshotDigest = ledger.snapshotDigestHex()
        val compoundCommitDigest = ProductionC1EndpointCompoundRecord(ledger, pair).digestHex()
        val markerDigest = marker.digestHex()
        val consumed = pair.consumedEntries.lastOrNull()

        exactBoundStartRequire(
            token.admissionId == entry.admissionId &&
                token.admissionId == marker.admissionId &&
                token.bindingDigest == recomputedBindingDigest &&
                token.bindingDigest == entry.bindingDigest &&
                token.bindingDigest == marker.bindingDigest &&
                token.routeGrantDigest == routeGrantDigest &&
                token.routeGrantDigest == entry.routeGrantDigest &&
                token.sessionId == transcript.sessionId &&
                token.sessionId == evidence.sessionId &&
                token.sessionId == entry.sessionId &&
                token.sessionId == marker.sessionId &&
                token.transcriptDigest == transcriptDigest &&
                token.transcriptDigest == entry.transcriptDigest &&
                token.routeAuthorizationDigest == routeAuthorizationDigest &&
                token.routeAuthorizationDigest == entry.routeAuthorizationDigest &&
                token.routeAuthorizationDigest == marker.routeAuthorizationDigest &&
                token.grantAuthorizationDigest == grantAuthorizationDigest &&
                token.grantAuthorizationDigest == transcript.routeAuthorizationDigest &&
                token.grantAuthorizationDigest == entry.grantAuthorizationDigest &&
                token.grantAuthorizationDigest == marker.grantAuthorizationDigest &&
                token.connectorInputCommitmentDigest == connectorInputCommitmentDigest &&
                token.connectorInputCommitmentDigest == entry.connectorInputCommitmentDigest &&
                token.pairAuthorityDigest == pairAuthorityDigest &&
                token.pairAuthorityDigest == evidence.pairAuthorityDigest &&
                token.pairAuthorityDigest == ledger.pairAuthorityDigest &&
                token.pairAuthorityDigest == marker.pairAuthorityDigest &&
                token.pairSnapshotDigest == pairSnapshotDigest &&
                token.pairSnapshotDigest == entry.pairSnapshotDigest &&
                token.pairSnapshotDigest == marker.committedPairSnapshotDigest &&
                token.ledgerSnapshotDigest == ledgerSnapshotDigest &&
                token.ledgerSnapshotDigest == marker.committedLedgerSnapshotDigest &&
                token.compoundCommitDigest == compoundCommitDigest &&
                token.compoundCommitDigest == marker.committedCompoundDigest &&
                token.markerDigest == markerDigest &&
                token.pairLocalRevision == pair.localRevision &&
                token.pairLocalRevision == ledger.pairLocalRevision &&
                token.pairLocalRevision == marker.pairLocalRevision &&
                token.ledgerRevision == ledger.revision &&
                token.ledgerRevision == entry.committedRevision &&
                token.ledgerRevision == marker.ledgerRevision &&
                token.effectiveNotBeforeMs == evidence.effectiveNotBeforeMs &&
                token.effectiveNotBeforeMs == marker.effectiveNotBeforeMs &&
                token.expiresAtMs == evidence.expiresAtMs &&
                token.expiresAtMs == marker.expiresAtMs &&
                consumed?.sessionId == token.sessionId &&
                consumed.transcriptDigest == token.transcriptDigest,
            ProductionC1ExactBoundStartValidationFailure.EXACT_BINDING_MISMATCH,
        )
        exactBoundStartRequire(
            routeAuthorizationDigest == evidence.finalRouteAuthorizationDigest &&
                transcript.routeAuthorizationKind == ProductionRouteAuthorizationKind.P2P_DIRECT &&
                transcript.pairBindingDigest == authority.pairBindingDigest &&
                transcript.pairEpoch == authority.pairEpoch &&
                transcript.clientIdentityFingerprint == authority.clientIdentityFingerprint &&
                transcript.runtimeIdentityFingerprint == authority.runtimeIdentityFingerprint &&
                transcript.generation == authority.generation &&
                transcript.serviceConfigVersion == authority.serviceConfigVersion &&
                transcript.keysetVersion == authority.keysetVersion &&
                transcript.revocationCounter == authority.revocationCounter &&
                evidence.pairBindingDigest == authority.pairBindingDigest &&
                evidence.pairEpoch == authority.pairEpoch &&
                evidence.clientIdentityFingerprint == authority.clientIdentityFingerprint &&
                evidence.runtimeIdentityFingerprint == authority.runtimeIdentityFingerprint &&
                evidence.generation == authority.generation &&
                evidence.keysetVersion == authority.keysetVersion,
            ProductionC1ExactBoundStartValidationFailure.INACTIVE_PAIR_AUTHORITY,
        )
        val nowMs = productionTrustedClock.nowMs()
        if (nowMs < token.effectiveNotBeforeMs) {
            throw ProductionC1ExactBoundStartValidationException(
                ProductionC1ExactBoundStartValidationFailure.NOT_YET_VALID,
            )
        }
        if (nowMs >= token.expiresAtMs) {
            throw ProductionC1ExactBoundStartValidationException(
                ProductionC1ExactBoundStartValidationFailure.EXPIRED,
            )
        }
        ProductionC1ExactBoundStartValidation(
            runtimeDeviceId = request.expectedRuntimeDeviceId,
            pairAuthorityDigest = pairAuthorityDigest,
            markerDigest = markerDigest,
            admissionId = token.admissionId,
            bindingDigest = token.bindingDigest,
            sessionId = token.sessionId,
            effectiveNotBeforeMs = token.effectiveNotBeforeMs,
            expiresAtMs = token.expiresAtMs,
            pairLocalRevision = token.pairLocalRevision,
            ledgerRevision = token.ledgerRevision,
        )
    }

    @JvmSynthetic
    internal fun exactBoundStartCoordinator(): ProductionC1ExactBoundStartCoordinator =
        productionC1ExactBoundStartCoordinator.value

    suspend fun prepareAuthorityBoundProductionSecureSessionStart(
        expectedRuntimeDeviceId: String,
        expectedRuntimeFingerprint: String,
        expectedRuntimePublicKey: String,
        token: ProductionC1EndpointGrantCompoundCommitToken,
        binding: VerifiedProductionC1CandidateP2PTranscriptBinding,
        localEphemeralKey: ProductionSecureSessionEphemeralKey,
    ): ProductionC1AuthorityBoundSecureSessionStartCapability {
        val request = ProductionC1ExactBoundStartRequest(
            expectedRuntimeDeviceId,
            expectedRuntimeFingerprint,
            expectedRuntimePublicKey,
            token,
            binding,
        )
        validateProductionC1ExactBoundStart(request)
        return mintProductionC1AuthorityBoundSecureSessionStartCapability(
            this,
            request,
            localEphemeralKey,
        )
    }

    suspend fun beginAuthorityBoundProductionSecureSession(
        capability: ProductionC1AuthorityBoundSecureSessionStartCapability,
    ): ProductionC1AuthorityBoundSecureSessionCapability {
        val material = capability.claim(this)
        try {
            val request = material.request
            val keyScheduleBinding = request.binding.keyScheduleBinding
            val descriptor = ProductionC1AuthorityBoundSecureSessionDescriptor(
                sessionId = keyScheduleBinding.transcript.sessionId,
                expiresAtMs = keyScheduleBinding.grantAuthorization.authorization.expiresAtMs,
                object7Object26KdfBindingDigestHex =
                    keyScheduleBinding.object7Object26KdfBindingDigestHex,
            )
            val coordinator = exactBoundStartCoordinator()
            return ProductionC1AuthorityBoundSecureSession.begin(
                coordinator,
                request,
                material.localEphemeralKey,
                productionAuthorityPublicationGate,
            ) { productionTrustedClock.nowMs() }.asCapability(descriptor)
        } catch (error: Throwable) {
            material.localEphemeralKey.close()
            throw error
        }
    }

    internal fun authorityPublicationGateForTesting(): ProductionC1AuthorityPublicationGate =
        productionAuthorityPublicationGate

    private fun initializedExactBoundStartCoordinator(): ProductionC1ExactBoundStartCoordinator? =
        productionC1ExactBoundStartCoordinator.takeIf { it.isInitialized() }?.value

    private suspend fun fenceExactBoundStartAfterAuthorityMutation(
        previousAuthorityDigest: String?,
        snapshot: ProductionPairStateSnapshot,
    ) = withContext(NonCancellable) {
        val coordinator = initializedExactBoundStartCoordinator() ?: return@withContext
        val previous = previousAuthorityDigest
        if (previous != null &&
            previous != snapshot.authority.digestHex() &&
            snapshot.authority.status == ProductionPairAuthorityStatus.ACTIVE
        ) {
            coordinator.fenceAuthorityAdvance(previous)
        } else if (previous != null && previous != snapshot.authority.digestHex()) {
            coordinator.fenceRevoked(previous)
        }
        coordinator.retryPendingAborts()
    }

    private suspend fun fenceExactBoundStartAfterAmbiguousAuthorityMutation(
        previousAuthorityDigest: String?,
    ) = withContext(NonCancellable) {
        val coordinator = initializedExactBoundStartCoordinator() ?: return@withContext
        if (previousAuthorityDigest != null) {
            coordinator.fenceRevoked(previousAuthorityDigest)
        } else {
            coordinator.fenceAllUncertainAuthority()
        }
        coordinator.retryPendingAborts()
    }

    private fun Preferences.productionPairAuthorityDigestForFence(): String? = runCatching {
        val pairEncoding = this[Keys.runtimeProductionPairState]
        val endpointEncoding = this[Keys.runtimeProductionEndpointCompoundState]
        check(pairEncoding == null || endpointEncoding == null) {
            "Conflicting production pair-state encodings"
        }
        endpointEncoding
            ?.decodeProductionEndpointCompoundStrict()
            ?.pairSnapshot
            ?.authority
            ?.digestHex()
            ?: pairEncoding
                ?.decodeProductionPairStateStrict()
                ?.authority
                ?.digestHex()
    }.getOrNull()

    private suspend fun readEndpointCompoundStateStrict(
        expectedRuntimeDeviceId: String,
        expectedRuntimeFingerprint: String,
        expectedRuntimePublicKey: String,
    ): StoredProductionC1EndpointCompoundState {
        val prefs = context.localAgentBridgeDataStore.data.first()
        prefs.requireExpectedRuntimeIdentity(
            expectedRuntimeDeviceId,
            expectedRuntimeFingerprint,
        )
        check(prefs[Keys.runtimePublicKey] == expectedRuntimePublicKey) {
            "Trusted runtime public key mismatch"
        }
        check(prefs[Keys.runtimeProductionPairState] == null) {
            "Conflicting production pair-state encodings"
        }
        return prefs[Keys.runtimeProductionEndpointCompoundState]
            ?.decodeProductionEndpointCompoundStrict()
            ?.also { it.requireRuntimeIdentity(expectedRuntimeDeviceId, expectedRuntimePublicKey) }
            ?: throw ProductionPairStateException(
                ProductionPairStateRejectionReason.MISSING_CURRENT_STATE,
            )
    }

    private fun bootstrapEndpointLedger(
        pairSnapshot: ProductionPairStateSnapshot,
    ): ProductionC1EndpointGrantLedgerState {
        val capacity = ProductionPairStateContract.MAX_CONSUMED_ENTRIES
        endpointCommitRequire(
            pairSnapshot.consumedEntries.size <= capacity,
            ProductionC1CandidateCapabilityError.RETENTION_EXHAUSTED,
        )
        return ProductionC1EndpointGrantLedgerState(
            pairAuthorityDigest = pairSnapshot.authority.digestHex(),
            pairLocalRevision = pairSnapshot.localRevision,
            remainingGrants = (capacity - pairSnapshot.consumedEntries.size).toULong(),
            retentionLimit = capacity.toUInt(),
        )
    }

    suspend fun forgetRuntime() {
        val cleanupReferences = linkedSetOf<String>()
        productionAuthorityPublicationGate.withWrite {
            var previousAuthorityDigest: String? = null
            var persistenceAttempted = false
            try {
                productionStatePersistenceMutex.withLock {
                    val before = context.localAgentBridgeDataStore.data.first()
                    previousAuthorityDigest = before.productionPairAuthorityDigestForFence()
                    context.localAgentBridgeDataStore.edit { prefs ->
                        check(
                            prefs.productionPairAuthorityDigestForFence() == previousAuthorityDigest,
                        ) { "Production pair authority changed during forget commit" }
                        persistenceAttempted = true
                        prefs[Keys.runtimeRelaySecretRef]
                            ?.takeIf(::isOwnedTrustedRelaySecretReference)
                            ?.let(cleanupReferences::add)
                        prefs.enqueueRelaySecretCleanup(cleanupReferences)
                        prefs.removeRuntimeKeys()
                        prefs.remove(Keys.runtimeProductionPairState)
                        prefs.remove(Keys.runtimeProductionEndpointCompoundState)
                        prefs.removeLegacyRuntimeKeys()
                        authorityPersistenceHooks.afterEditEnqueued?.invoke()
                    }
                    authorityPersistenceHooks.afterCommitBeforeFence?.invoke()
                }
            } catch (error: Throwable) {
                if (persistenceAttempted || error is IOException) {
                    runCatching {
                        fenceExactBoundStartAfterAmbiguousAuthorityMutation(previousAuthorityDigest)
                    }.exceptionOrNull()?.let(error::addSuppressed)
                }
                throw error
            }
            withContext(NonCancellable) {
                initializedExactBoundStartCoordinator()?.let { coordinator ->
                    if (previousAuthorityDigest != null) {
                        val previous = requireNotNull(previousAuthorityDigest)
                        coordinator.fenceRevoked(previous)
                    } else {
                        coordinator.fenceAllUncertainAuthority()
                    }
                    coordinator.retryPendingAborts()
                }
            }
        }
        drainRelaySecretCleanup()
    }

    private suspend fun compensateUncommittedRelaySecret(reference: String) {
        if (relaySecretStore.removeSecretDurably(reference)) return
        context.localAgentBridgeDataStore.edit { prefs ->
            prefs.enqueueRelaySecretCleanup(setOf(reference))
        }
    }

    private suspend fun drainRelaySecretCleanup() {
        var failedReferences = emptySet<String>()
        context.localAgentBridgeDataStore.edit { prefs ->
            val currentReference = prefs[Keys.runtimeRelaySecretRef]
            val pendingReferences = prefs[Keys.runtimeRelaySecretCleanupRefs]
                .orEmpty()
                .filterTo(linkedSetOf()) { reference ->
                    reference != currentReference &&
                        isOwnedTrustedRelaySecretReference(reference)
                }
            failedReferences = pendingReferences.filterTo(linkedSetOf()) { reference ->
                !relaySecretStore.removeSecretDurably(reference)
            }
            prefs.replaceRelaySecretCleanup(failedReferences)
        }
        check(failedReferences.isEmpty()) {
            "Trusted runtime relay secret cleanup failed"
        }
    }

    private object Keys {
        val runtimeDeviceId = stringPreferencesKey("runtime_device_id")
        val runtimeName = stringPreferencesKey("runtime_name")
        val runtimeFingerprint = stringPreferencesKey("runtime_fingerprint")
        val runtimePublicKey = stringPreferencesKey("runtime_public_key")
        val runtimeRouteToken = stringPreferencesKey("runtime_route_token")
        val runtimeHost = stringPreferencesKey("runtime_host")
        val runtimePort = intPreferencesKey("runtime_port")
        val runtimeRelayHost = stringPreferencesKey("runtime_relay_host")
        val runtimeRelayPort = intPreferencesKey("runtime_relay_port")
        val runtimeRelayId = stringPreferencesKey("runtime_relay_id")
        val runtimeRelaySecret = stringPreferencesKey("runtime_relay_secret")
        val runtimeRelaySecretRef = stringPreferencesKey("runtime_relay_secret_ref")
        val runtimeRelaySecretCleanupRefs =
            stringSetPreferencesKey("runtime_relay_secret_cleanup_refs")
        val runtimeRelayExpiresAtEpochMillis = longPreferencesKey("runtime_relay_expires_at_epoch_millis")
        val runtimeRelayNonce = stringPreferencesKey("runtime_relay_nonce")
        val runtimeRelayScope = stringPreferencesKey("runtime_relay_scope")
        val runtimeRelayTicketGeneration = longPreferencesKey("runtime_relay_ticket_generation")
        val runtimeP2pRouteClass = stringPreferencesKey("runtime_p2p_route_class")
        val runtimeP2pRecordId = stringPreferencesKey("runtime_p2p_record_id")
        val runtimeP2pEncryptedBody = stringPreferencesKey("runtime_p2p_encrypted_body")
        val runtimeP2pExpiresAtEpochMillis = longPreferencesKey("runtime_p2p_expires_at_epoch_millis")
        val runtimeP2pAntiReplayNonce = stringPreferencesKey("runtime_p2p_anti_replay_nonce")
        val runtimeP2pProtocolVersion = intPreferencesKey("runtime_p2p_protocol_version")
        val runtimeProductionPairState = stringPreferencesKey("runtime_production_pair_state")
        val runtimeProductionEndpointCompoundState =
            stringPreferencesKey("runtime_production_endpoint_compound_state")
    }

    private object LegacyKeys {
        val runtimeDeviceId = stringPreferencesKey("mac_device_id")
        val runtimeName = stringPreferencesKey("mac_name")
        val runtimeFingerprint = stringPreferencesKey("mac_fingerprint")
        val runtimePublicKey = stringPreferencesKey("mac_public_key")
        val runtimeRouteToken = stringPreferencesKey("mac_route_token")
        val runtimeHost = stringPreferencesKey("mac_host")
        val runtimePort = intPreferencesKey("mac_port")
    }

    private fun MutablePreferences.removeRuntimeKeys() {
        remove(Keys.runtimeDeviceId)
        remove(Keys.runtimeName)
        remove(Keys.runtimeFingerprint)
        remove(Keys.runtimePublicKey)
        remove(Keys.runtimeRouteToken)
        removeDirectEndpointKeys()
        removeRelayRouteKeys()
        removeP2pRouteKeys()
        remove(Keys.runtimeProductionPairState)
        remove(Keys.runtimeProductionEndpointCompoundState)
    }

    private fun MutablePreferences.removeDirectEndpointKeys() {
        remove(Keys.runtimeHost)
        remove(Keys.runtimePort)
        remove(LegacyKeys.runtimeHost)
        remove(LegacyKeys.runtimePort)
    }

    private fun MutablePreferences.removeRouteTokenKeys() {
        remove(Keys.runtimeRouteToken)
        remove(LegacyKeys.runtimeRouteToken)
    }

    private fun MutablePreferences.removeRelayRouteKeys() {
        remove(Keys.runtimeRelayHost)
        remove(Keys.runtimeRelayPort)
        remove(Keys.runtimeRelayId)
        remove(Keys.runtimeRelaySecret)
        remove(Keys.runtimeRelaySecretRef)
        remove(Keys.runtimeRelayExpiresAtEpochMillis)
        remove(Keys.runtimeRelayNonce)
        remove(Keys.runtimeRelayScope)
        remove(Keys.runtimeRelayTicketGeneration)
    }

    private fun MutablePreferences.enqueueRelaySecretCleanup(references: Set<String>) {
        val cleanReferences = references.filterTo(linkedSetOf(), ::isOwnedTrustedRelaySecretReference)
        if (cleanReferences.isEmpty()) return
        this[Keys.runtimeRelaySecretCleanupRefs] =
            this[Keys.runtimeRelaySecretCleanupRefs].orEmpty() + cleanReferences
    }

    private fun MutablePreferences.replaceRelaySecretCleanup(references: Set<String>) {
        if (references.isEmpty()) {
            remove(Keys.runtimeRelaySecretCleanupRefs)
        } else {
            this[Keys.runtimeRelaySecretCleanupRefs] = references
        }
    }

    private fun MutablePreferences.removeP2pRouteKeys() {
        remove(Keys.runtimeP2pRouteClass)
        remove(Keys.runtimeP2pRecordId)
        remove(Keys.runtimeP2pEncryptedBody)
        remove(Keys.runtimeP2pExpiresAtEpochMillis)
        remove(Keys.runtimeP2pAntiReplayNonce)
        remove(Keys.runtimeP2pProtocolVersion)
    }

    private fun MutablePreferences.removeLegacyRuntimeKeys() {
        remove(LegacyKeys.runtimeDeviceId)
        remove(LegacyKeys.runtimeName)
        remove(LegacyKeys.runtimeFingerprint)
        remove(LegacyKeys.runtimePublicKey)
        remove(LegacyKeys.runtimeRouteToken)
        remove(LegacyKeys.runtimeHost)
        remove(LegacyKeys.runtimePort)
    }

    private fun Preferences.hasStoredRelayRoute(): Boolean {
        return this[Keys.runtimeRelayHost] != null ||
            this[Keys.runtimeRelayPort] != null ||
            this[Keys.runtimeRelayId] != null ||
            this[Keys.runtimeRelaySecret] != null ||
            this[Keys.runtimeRelaySecretRef] != null ||
            this[Keys.runtimeRelayExpiresAtEpochMillis] != null ||
            this[Keys.runtimeRelayNonce] != null ||
            this[Keys.runtimeRelayScope] != null ||
            this[Keys.runtimeRelayTicketGeneration] != null
    }

    private fun Preferences.hasStoredP2pRoute(): Boolean {
        return this[Keys.runtimeP2pRouteClass] != null ||
            this[Keys.runtimeP2pRecordId] != null ||
            this[Keys.runtimeP2pEncryptedBody] != null ||
            this[Keys.runtimeP2pExpiresAtEpochMillis] != null ||
            this[Keys.runtimeP2pAntiReplayNonce] != null ||
            this[Keys.runtimeP2pProtocolVersion] != null
    }

    private fun Preferences.hasStoredDirectEndpoint(): Boolean {
        return this[Keys.runtimeHost] != null ||
            this[Keys.runtimePort] != null ||
            this[LegacyKeys.runtimeHost] != null ||
            this[LegacyKeys.runtimePort] != null
    }

    private fun Preferences.productionPairStateLoadStateForProjection(
        expectedRuntimeDeviceId: String,
        expectedRuntimeFingerprint: String,
        expectedRuntimePublicKey: String?,
    ): ProductionPairStateLoadState {
        val encodedPair = this[Keys.runtimeProductionPairState]
        val encodedCompound = this[Keys.runtimeProductionEndpointCompoundState]
        if (encodedPair == null && encodedCompound == null) {
            return ProductionPairStateLoadState.Absent
        }
        return try {
            val snapshot = when {
                encodedPair != null && encodedCompound != null ->
                    throw ProductionC1EndpointPersistenceException(
                        ProductionC1EndpointPersistenceFailure.STATE_INJECTION_REJECTED,
                    )
                encodedPair != null -> encodedPair.decodeProductionPairStateStrict()
                else -> {
                    val publicKey = expectedRuntimePublicKey
                        ?: throw ProductionC1EndpointPersistenceException(
                            ProductionC1EndpointPersistenceFailure.IDENTITY_MISMATCH,
                        )
                    encodedCompound!!.decodeProductionEndpointCompoundStrict()
                        .also { it.requireRuntimeIdentity(expectedRuntimeDeviceId, publicKey) }
                        .pairSnapshot
                }
            }
            if (snapshot.authority.runtimeIdentityFingerprint == expectedRuntimeFingerprint) {
                ProductionPairStateLoadState.Valid(snapshot)
            } else {
                ProductionPairStateLoadState.InvalidPresent
            }
        } catch (_: IllegalArgumentException) {
            ProductionPairStateLoadState.InvalidPresent
        } catch (_: IllegalStateException) {
            ProductionPairStateLoadState.InvalidPresent
        }
    }

    private fun Preferences.productionPairStateStrict(
        expectedRuntimeDeviceId: String,
        expectedRuntimeFingerprint: String,
    ): ProductionPairStateSnapshot? {
        val encodedPair = this[Keys.runtimeProductionPairState]
        val encodedCompound = this[Keys.runtimeProductionEndpointCompoundState]
        check(encodedPair == null || encodedCompound == null) {
            "Conflicting production pair-state encodings"
        }
        val snapshot = when {
            encodedPair != null -> encodedPair.decodeProductionPairStateStrict()
            encodedCompound != null -> {
                val publicKey = this[Keys.runtimePublicKey]
                    ?: error("Trusted runtime public key is not stored")
                encodedCompound.decodeProductionEndpointCompoundStrict()
                    .also { it.requireRuntimeIdentity(expectedRuntimeDeviceId, publicKey) }
                    .pairSnapshot
            }
            else -> return null
        }
        check(snapshot.authority.runtimeIdentityFingerprint == expectedRuntimeFingerprint) {
            "Production pair state runtime identity mismatch"
        }
        return snapshot
    }

    private fun Preferences.requireExpectedRuntimeIdentity(
        expectedRuntimeDeviceId: String,
        expectedRuntimeFingerprint: String,
    ) {
        require(isCanonicalOpaqueRouteValue(expectedRuntimeDeviceId)) {
            "Invalid expected runtime device id"
        }
        require(isCanonicalOpaqueRouteValue(expectedRuntimeFingerprint)) {
            "Invalid expected runtime fingerprint"
        }
        val storedDeviceId = this[Keys.runtimeDeviceId] ?: this[LegacyKeys.runtimeDeviceId]
            ?: error("Trusted runtime is not stored")
        val storedFingerprint = this[Keys.runtimeFingerprint] ?: this[LegacyKeys.runtimeFingerprint]
            ?: error("Trusted runtime fingerprint is not stored")
        check(storedDeviceId == expectedRuntimeDeviceId && storedFingerprint == expectedRuntimeFingerprint) {
            "Trusted runtime identity mismatch"
        }
    }

    private fun Preferences.requireSafeProductionPairStateTrustWrite(
        incomingDeviceId: String?,
        incomingFingerprint: String?,
        incomingPublicKey: String?,
        incomingState: ProductionPairStateLoadState,
    ) {
        val storedPairEncoding = this[Keys.runtimeProductionPairState]
        val storedCompoundEncoding = this[Keys.runtimeProductionEndpointCompoundState]
        check(storedPairEncoding == null || storedCompoundEncoding == null) {
            "Conflicting production pair-state encodings"
        }
        if (storedPairEncoding == null && storedCompoundEncoding == null) {
            check(incomingState is ProductionPairStateLoadState.Absent) {
                "Production pair state requires a verified transition"
            }
            return
        }
        val storedDeviceId = this[Keys.runtimeDeviceId] ?: this[LegacyKeys.runtimeDeviceId]
        val storedFingerprint = this[Keys.runtimeFingerprint] ?: this[LegacyKeys.runtimeFingerprint]
        check(storedDeviceId == incomingDeviceId && storedFingerprint == incomingFingerprint) {
            "Trusted runtime with production pair state cannot be overwritten"
        }
        if (storedPairEncoding != null || storedCompoundEncoding != null) {
            check(this[Keys.runtimePublicKey] == incomingPublicKey) {
                "Trusted runtime with production state cannot change public key"
            }
        }
        when (incomingState) {
            ProductionPairStateLoadState.Absent -> Unit
            ProductionPairStateLoadState.InvalidPresent -> check(
                productionPairStateLoadStateForProjection(
                    expectedRuntimeDeviceId = requireNotNull(incomingDeviceId),
                    expectedRuntimeFingerprint = requireNotNull(incomingFingerprint),
                    expectedRuntimePublicKey = this[Keys.runtimePublicKey],
                ) is ProductionPairStateLoadState.InvalidPresent
            ) {
                "Production pair state projection does not match persisted state"
            }
            is ProductionPairStateLoadState.Valid -> {
                val storedState = productionPairStateStrict(
                    expectedRuntimeDeviceId = requireNotNull(incomingDeviceId),
                    expectedRuntimeFingerprint = requireNotNull(incomingFingerprint),
                ) ?: error("Production pair state is not stored")
                check(incomingState.snapshot == storedState) {
                    "Production pair state requires a verified transition"
                }
            }
        }
    }

    private fun invalidStoredTrustedRuntime(): LoadedTrustedRuntime {
        return LoadedTrustedRuntime(
            null,
            shouldRemoveStoredTrustedRuntime = true,
            shouldRemoveStoredRelayRoute = false,
        )
    }

    private data class LoadedTrustedRuntime(
        val trustedRuntime: TrustedRuntime?,
        val shouldRemoveStoredTrustedRuntime: Boolean = false,
        val shouldRemoveStoredRouteToken: Boolean = false,
        val shouldRemoveStoredRelayRoute: Boolean,
        val shouldRemoveStoredP2pRoute: Boolean = false,
        val shouldRemoveStoredDirectEndpoint: Boolean = false,
        val relaySecretRefToPersist: String? = null,
        val relaySecretToPersist: String? = null,
        val relaySecretRefsToRemove: List<String> = emptyList(),
    )

    private companion object {
        val productionStatePersistenceMutex = Mutex()
    }
}

private fun StoredProductionC1EndpointCommitMarker.toReadback():
    ProductionC1EndpointGrantCommitReadback = ProductionC1EndpointGrantCommitReadback(
    admissionId = admissionId,
    bindingDigest = bindingDigest,
    sessionId = sessionId,
    routeAuthorizationDigest = routeAuthorizationDigest,
    grantAuthorizationDigest = grantAuthorizationDigest,
    pairAuthorityDigest = pairAuthorityDigest,
    compoundCommitDigest = committedCompoundDigest,
    effectiveNotBeforeMs = effectiveNotBeforeMs,
    expiresAtMs = expiresAtMs,
    pairLocalRevision = pairLocalRevision,
    ledgerRevision = ledgerRevision,
    markerDigest = digestHex(),
)

private fun endpointCommitRequire(
    condition: Boolean,
    reason: ProductionC1CandidateCapabilityError =
        ProductionC1CandidateCapabilityError.REVISION_MISMATCH,
) {
    if (!condition) throw ProductionC1CandidateCapabilityException(reason)
}

private fun exactBoundStartDigestHex(bytes: ByteArray): String =
    MessageDigest.getInstance("SHA-256")
        .digest(bytes)
        .joinToString("") { byte -> "%02x".format(byte.toInt() and 0xff) }

private fun requireProductionC1AdmissionWindow(
    preparation: ProductionC1AdmissionPreparation,
    nowMs: ULong,
) {
    if (nowMs < preparation.effectiveNotBeforeMs) {
        throw ProductionC1Exception(ProductionC1Error.NOT_YET_VALID)
    }
    if (nowMs >= preparation.expiresAtMs) {
        throw ProductionC1Exception(ProductionC1Error.EXPIRED)
    }
}

private fun ProductionPairStateSnapshot.canonicalBase64(): String =
    Base64.getEncoder().encodeToString(canonicalBytes())

private fun StoredProductionC1EndpointCompoundState.canonicalBase64(): String =
    Base64.getEncoder().encodeToString(canonicalBytes())

private fun String.decodeProductionPairStateStrict(): ProductionPairStateSnapshot {
    try {
        require(length <= MAX_PRODUCTION_PAIR_STATE_BASE64_CHARS)
        val decoded = Base64.getDecoder().decode(this)
        require(decoded.size <= ProductionPairStateContract.MAX_SNAPSHOT_BYTES)
        require(Base64.getEncoder().encodeToString(decoded) == this)
        return ProductionPairStateSnapshot.decode(decoded)
    } catch (error: ProductionPairStateException) {
        throw error
    } catch (_: IllegalArgumentException) {
        throw ProductionPairStateException(
            ProductionPairStateRejectionReason.INVALID_CANONICAL_STATE
        )
    }
}

private fun String.decodeProductionEndpointCompoundStrict(): StoredProductionC1EndpointCompoundState {
    try {
        require(length <= MAX_PRODUCTION_ENDPOINT_COMPOUND_BASE64_CHARS)
        val decoded = Base64.getDecoder().decode(this)
        require(decoded.size <= ProductionC1EndpointCompoundPersistenceContract.MAX_ENVELOPE_BYTES)
        require(Base64.getEncoder().encodeToString(decoded) == this)
        return StoredProductionC1EndpointCompoundState.decode(decoded)
    } catch (error: ProductionC1EndpointPersistenceException) {
        throw error
    } catch (_: IllegalArgumentException) {
        throw ProductionC1EndpointPersistenceException(
            ProductionC1EndpointPersistenceFailure.MALFORMED_CANONICAL,
        )
    }
}

private const val MAX_PRODUCTION_PAIR_STATE_BASE64_CHARS =
    ((ProductionPairStateContract.MAX_SNAPSHOT_BYTES + 2) / 3) * 4

private const val MAX_PRODUCTION_ENDPOINT_COMPOUND_BASE64_CHARS =
    ((ProductionC1EndpointCompoundPersistenceContract.MAX_ENVELOPE_BYTES + 2) / 3) * 4

interface RelaySecretStore {
    fun saveSecret(handle: String, secret: String)
    fun readSecret(handle: String): String?
    fun removeSecret(handle: String)
}

interface DurableRelaySecretStore : RelaySecretStore {
    fun saveSecretDurably(handle: String, secret: String): Boolean
    fun removeSecretDurably(handle: String): Boolean
}

class AndroidKeystoreRelaySecretStore(context: Context) : DurableRelaySecretStore {
    private val preferences = context.getSharedPreferences(RELAY_SECRET_STORE_NAME, Context.MODE_PRIVATE)

    override fun saveSecret(handle: String, secret: String) {
        preferences.edit()
            .putString(handle, encrypt(secret))
            .apply()
    }

    @SuppressLint("ApplySharedPref")
    override fun saveSecretDurably(handle: String, secret: String): Boolean {
        return preferences.edit()
            .putString(handle, encrypt(secret))
            .commit()
    }

    override fun readSecret(handle: String): String? {
        val encoded = preferences.getString(handle, null) ?: return null
        return runCatching { decrypt(encoded) }.getOrNull()
    }

    override fun removeSecret(handle: String) {
        preferences.edit().remove(handle).apply()
    }

    @SuppressLint("ApplySharedPref")
    override fun removeSecretDurably(handle: String): Boolean {
        return preferences.edit().remove(handle).commit()
    }

    private fun encrypt(secret: String): String {
        val cipher = Cipher.getInstance(RELAY_SECRET_CIPHER)
        cipher.init(Cipher.ENCRYPT_MODE, getOrCreateSecretKey())
        val encrypted = cipher.doFinal(secret.toByteArray(Charsets.UTF_8))
        val iv = cipher.iv
        val packed = ByteBuffer.allocate(1 + iv.size + encrypted.size)
            .put(iv.size.toByte())
            .put(iv)
            .put(encrypted)
            .array()
        return Base64.getEncoder().encodeToString(packed)
    }

    private fun decrypt(encoded: String): String {
        val packed = ByteBuffer.wrap(Base64.getDecoder().decode(encoded))
        val ivLength = packed.get().toInt() and 0xff
        require(ivLength > 0 && ivLength <= packed.remaining()) { "Invalid relay secret IV" }
        val iv = ByteArray(ivLength)
        packed.get(iv)
        val encrypted = ByteArray(packed.remaining())
        packed.get(encrypted)
        val cipher = Cipher.getInstance(RELAY_SECRET_CIPHER)
        cipher.init(Cipher.DECRYPT_MODE, getOrCreateSecretKey(), javax.crypto.spec.GCMParameterSpec(128, iv))
        return cipher.doFinal(encrypted).toString(Charsets.UTF_8)
    }

    private fun getOrCreateSecretKey(): SecretKey {
        val keyStore = KeyStore.getInstance(ANDROID_KEYSTORE_PROVIDER).apply { load(null) }
        val existing = keyStore.getEntry(RELAY_SECRET_KEY_ALIAS, null) as? KeyStore.SecretKeyEntry
        if (existing != null) return existing.secretKey

        val keyGenerator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, ANDROID_KEYSTORE_PROVIDER)
        val keySpec = KeyGenParameterSpec.Builder(
            RELAY_SECRET_KEY_ALIAS,
            KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
        )
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setRandomizedEncryptionRequired(true)
            .build()
        keyGenerator.init(keySpec)
        return keyGenerator.generateKey()
    }

    private companion object {
        const val RELAY_SECRET_STORE_NAME = "local_agent_bridge_relay_secrets"
        const val ANDROID_KEYSTORE_PROVIDER = "AndroidKeyStore"
        const val RELAY_SECRET_KEY_ALIAS = "aetherlink_relay_secret_store_v1"
        const val RELAY_SECRET_CIPHER = "AES/GCM/NoPadding"
    }
}

private fun relaySecretHandle(
    deviceId: String,
    relayId: String,
    relaySecret: String,
): String {
    val digest = MessageDigest.getInstance("SHA-256")
        .digest("$deviceId\n$relayId\n$relaySecret".toByteArray(Charsets.UTF_8))
    return "relay-v2-" + digest.joinToString("") { "%02x".format(it) }
}

private fun isOwnedTrustedRelaySecretReference(reference: String): Boolean {
    return TRUSTED_RELAY_SECRET_REFERENCE_PATTERN.matches(reference)
}

private val TRUSTED_RELAY_SECRET_REFERENCE_PATTERN = Regex("^relay-v[12]-[0-9a-f]{64}$")

internal fun TrustedRuntime.hasValidRelayRoute(): Boolean {
    val expiresAt = relayExpiresAtEpochMillis
    return hasCompleteRelayRoute() &&
        expiresAt != null &&
        expiresAt > System.currentTimeMillis()
}

internal fun TrustedRuntime.hasExpiredRelayRoute(
    nowEpochMillis: Long = System.currentTimeMillis(),
): Boolean {
    val expiresAt = relayExpiresAtEpochMillis ?: return false
    return hasCompleteRelayRoute() && expiresAt <= nowEpochMillis
}

internal fun TrustedRuntime.hasValidP2pRoute(
    nowEpochMillis: Long = System.currentTimeMillis(),
): Boolean {
    val expiresAt = p2pExpiresAtEpochMillis
    return hasCompleteP2pRoute() &&
        expiresAt != null &&
        expiresAt > nowEpochMillis
}

internal fun TrustedRuntime.hasExpiredP2pRoute(
    nowEpochMillis: Long = System.currentTimeMillis(),
): Boolean {
    val expiresAt = p2pExpiresAtEpochMillis ?: return false
    return hasCompleteP2pRoute() && expiresAt <= nowEpochMillis
}

private fun TrustedRuntime.hasCompleteRelayRoute(): Boolean {
    val expiresAt = relayExpiresAtEpochMillis
    return !relayHost.isNullOrBlank() &&
        isCanonicalRelayHostValue(relayHost) &&
        isAllowedRemoteRelayScope(relayScope) &&
        (isEligibleRemoteRelayHost(relayHost, relayScope) || relayHost.isDebugUsbReverseRelayRoute(relayScope)) &&
        relayPort != null &&
        relayPort in 1..65535 &&
        isCanonicalOpaqueRouteValue(relayId) &&
        isCanonicalOpaqueRouteValue(relaySecret) &&
        expiresAt != null &&
        expiresAt > 0L &&
        isCanonicalOpaqueRouteValue(relayNonce) &&
        (relayTicketGeneration == null || relayTicketGeneration > 0L)
}

private fun TrustedRuntime.hasCompleteP2pRoute(): Boolean {
    val expiresAt = p2pExpiresAtEpochMillis
    return p2pRouteClass == "p2p_rendezvous" &&
        isCanonicalOpaqueRouteValue(p2pRecordId) &&
        isCanonicalOpaqueRouteValue(p2pEncryptedBody, maxChars = OPAQUE_ROUTE_BODY_MAX_CHARS) &&
        expiresAt != null &&
        expiresAt > 0L &&
        isCanonicalOpaqueRouteValue(p2pAntiReplayNonce) &&
        p2pProtocolVersion == 1
}

private fun TrustedRuntime.withoutRelayRoute(): TrustedRuntime {
    return copy(
        relayHost = null,
        relayPort = null,
        relayId = null,
        relaySecret = null,
        relayExpiresAtEpochMillis = null,
        relayNonce = null,
        relayScope = null,
        relayTicketGeneration = null,
    )
}

private fun TrustedRuntime.withoutP2pRoute(): TrustedRuntime {
    return copy(
        p2pRouteClass = null,
        p2pRecordId = null,
        p2pEncryptedBody = null,
        p2pExpiresAtEpochMillis = null,
        p2pAntiReplayNonce = null,
        p2pProtocolVersion = null,
    )
}

private fun String.isDebugUsbReverseRelayRoute(relayScope: String?): Boolean {
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
