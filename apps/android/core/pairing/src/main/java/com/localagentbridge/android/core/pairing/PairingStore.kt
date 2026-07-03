package com.localagentbridge.android.core.pairing

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import androidx.datastore.preferences.core.MutablePreferences
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import java.nio.ByteBuffer
import java.security.KeyStore
import java.security.MessageDigest
import java.util.Base64
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey

internal val Context.localAgentBridgeDataStore by preferencesDataStore("local_agent_bridge")

class PairingStore(
    private val context: Context,
    private val relaySecretStore: RelaySecretStore = AndroidKeystoreRelaySecretStore(context),
) {
    val trustedRuntime: Flow<TrustedRuntime?> = flow {
        context.localAgentBridgeDataStore.data.collect { prefs ->
            val loaded = loadTrustedRuntime(prefs)
            if (
                loaded.shouldRemoveStoredRouteToken ||
                loaded.shouldRemoveStoredRelayRoute ||
                loaded.shouldRemoveStoredP2pRoute ||
                loaded.shouldRemoveStoredDirectEndpoint ||
                loaded.relaySecretRefToPersist != null
            ) {
                context.localAgentBridgeDataStore.edit { editPrefs ->
                    if (loaded.shouldRemoveStoredRouteToken) {
                        editPrefs.removeRouteTokenKeys()
                    }
                    if (loaded.shouldRemoveStoredRelayRoute) {
                        loaded.relaySecretRefsToRemove.forEach(relaySecretStore::removeSecret)
                        editPrefs.removeRelayRouteKeys()
                    }
                    if (loaded.shouldRemoveStoredP2pRoute) {
                        editPrefs.removeP2pRouteKeys()
                    }
                    if (loaded.shouldRemoveStoredDirectEndpoint) {
                        editPrefs.removeDirectEndpointKeys()
                    }
                    if (loaded.relaySecretRefToPersist != null) {
                        editPrefs[Keys.runtimeRelaySecretRef] = loaded.relaySecretRefToPersist
                        editPrefs.remove(Keys.runtimeRelaySecret)
                    }
                }
            }
            emit(loaded.trustedRuntime)
        }
    }

    private fun loadTrustedRuntime(prefs: Preferences): LoadedTrustedRuntime {
        val hasStoredRelayRoute = prefs.hasStoredRelayRoute()
        val hasStoredP2pRoute = prefs.hasStoredP2pRoute()
        val hasStoredDirectEndpoint = prefs.hasStoredDirectEndpoint()
        val id = prefs[Keys.runtimeDeviceId] ?: prefs[LegacyKeys.runtimeDeviceId]
            ?: return LoadedTrustedRuntime(
                null,
                shouldRemoveStoredRelayRoute = false,
                shouldRemoveStoredP2pRoute = hasStoredP2pRoute,
                shouldRemoveStoredDirectEndpoint = hasStoredDirectEndpoint,
            )
        val name = prefs[Keys.runtimeName] ?: prefs[LegacyKeys.runtimeName] ?: "AetherLink Runtime"
        val fingerprint = prefs[Keys.runtimeFingerprint] ?: prefs[LegacyKeys.runtimeFingerprint]
            ?: return LoadedTrustedRuntime(
                null,
                shouldRemoveStoredRelayRoute = false,
                shouldRemoveStoredP2pRoute = hasStoredP2pRoute,
                shouldRemoveStoredDirectEndpoint = hasStoredDirectEndpoint,
            )
        val publicKeyBase64 = prefs[Keys.runtimePublicKey] ?: prefs[LegacyKeys.runtimePublicKey]
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
        val p2pRouteClass = prefs[Keys.runtimeP2pRouteClass]
        val p2pRecordId = prefs[Keys.runtimeP2pRecordId]
        val p2pEncryptedBody = prefs[Keys.runtimeP2pEncryptedBody]
        val p2pExpiresAtEpochMillis = prefs[Keys.runtimeP2pExpiresAtEpochMillis]
        val p2pAntiReplayNonce = prefs[Keys.runtimeP2pAntiReplayNonce]
        val p2pProtocolVersion = prefs[Keys.runtimeP2pProtocolVersion]
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
            p2pRouteClass = p2pRouteClass,
            p2pRecordId = p2pRecordId,
            p2pEncryptedBody = p2pEncryptedBody,
            p2pExpiresAtEpochMillis = p2pExpiresAtEpochMillis,
            p2pAntiReplayNonce = p2pAntiReplayNonce,
            p2pProtocolVersion = p2pProtocolVersion,
        )
        val trustedWithoutInvalidP2p = if (trusted.hasValidP2pRoute()) trusted else trusted.withoutP2pRoute()
        val shouldRemoveStoredP2pRoute = hasStoredP2pRoute && !trusted.hasValidP2pRoute()
        return if (trusted.hasValidRelayRoute()) {
            val relaySecretRefToPersist = if (!legacyRelaySecret.isNullOrBlank() || relaySecretRef.isNullOrBlank()) {
                val ref = relaySecretHandle(id, requireNotNull(relayId))
                relaySecretStore.saveSecret(ref, requireNotNull(relaySecret))
                ref
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
            )
        } else {
            LoadedTrustedRuntime(
                trustedWithoutInvalidP2p.withoutRelayRoute(),
                shouldRemoveStoredRouteToken = shouldRemoveStoredRouteToken,
                shouldRemoveStoredRelayRoute = hasStoredRelayRoute,
                shouldRemoveStoredP2pRoute = shouldRemoveStoredP2pRoute,
                shouldRemoveStoredDirectEndpoint = hasStoredDirectEndpoint,
                relaySecretRefsToRemove = listOfNotNull(relaySecretRef),
            )
        }
    }

    suspend fun trustRuntime(runtime: TrustedRuntime) {
        context.localAgentBridgeDataStore.edit { prefs ->
            prefs[Keys.runtimeDeviceId] = runtime.deviceId
            prefs[Keys.runtimeName] = runtime.name
            prefs[Keys.runtimeFingerprint] = runtime.fingerprint
            val publicKeyBase64 = runtime.publicKeyBase64
            if (!publicKeyBase64.isNullOrBlank()) {
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
                val oldRelaySecretRef = prefs[Keys.runtimeRelaySecretRef]
                val newRelaySecretRef = relaySecretHandle(runtime.deviceId, requireNotNull(relayId))
                relaySecretStore.saveSecret(newRelaySecretRef, requireNotNull(relaySecret))
                prefs[Keys.runtimeRelayHost] = requireNotNull(relayHost)
                prefs[Keys.runtimeRelayPort] = requireNotNull(relayPort)
                prefs[Keys.runtimeRelayId] = relayId
                prefs[Keys.runtimeRelaySecretRef] = newRelaySecretRef
                prefs.remove(Keys.runtimeRelaySecret)
                if (oldRelaySecretRef != null && oldRelaySecretRef != newRelaySecretRef) {
                    relaySecretStore.removeSecret(oldRelaySecretRef)
                }
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
            } else {
                prefs[Keys.runtimeRelaySecretRef]?.let(relaySecretStore::removeSecret)
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
        }
    }

    suspend fun forgetRuntime() {
        context.localAgentBridgeDataStore.edit { prefs ->
            prefs[Keys.runtimeRelaySecretRef]?.let(relaySecretStore::removeSecret)
            prefs.removeRuntimeKeys()
            prefs.removeLegacyRuntimeKeys()
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
        val runtimeRelayExpiresAtEpochMillis = longPreferencesKey("runtime_relay_expires_at_epoch_millis")
        val runtimeRelayNonce = stringPreferencesKey("runtime_relay_nonce")
        val runtimeRelayScope = stringPreferencesKey("runtime_relay_scope")
        val runtimeP2pRouteClass = stringPreferencesKey("runtime_p2p_route_class")
        val runtimeP2pRecordId = stringPreferencesKey("runtime_p2p_record_id")
        val runtimeP2pEncryptedBody = stringPreferencesKey("runtime_p2p_encrypted_body")
        val runtimeP2pExpiresAtEpochMillis = longPreferencesKey("runtime_p2p_expires_at_epoch_millis")
        val runtimeP2pAntiReplayNonce = stringPreferencesKey("runtime_p2p_anti_replay_nonce")
        val runtimeP2pProtocolVersion = intPreferencesKey("runtime_p2p_protocol_version")
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
            this[Keys.runtimeRelayScope] != null
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

    private data class LoadedTrustedRuntime(
        val trustedRuntime: TrustedRuntime?,
        val shouldRemoveStoredRouteToken: Boolean = false,
        val shouldRemoveStoredRelayRoute: Boolean,
        val shouldRemoveStoredP2pRoute: Boolean = false,
        val shouldRemoveStoredDirectEndpoint: Boolean = false,
        val relaySecretRefToPersist: String? = null,
        val relaySecretRefsToRemove: List<String> = emptyList(),
    )
}

interface RelaySecretStore {
    fun saveSecret(handle: String, secret: String)
    fun readSecret(handle: String): String?
    fun removeSecret(handle: String)
}

class AndroidKeystoreRelaySecretStore(context: Context) : RelaySecretStore {
    private val preferences = context.getSharedPreferences(RELAY_SECRET_STORE_NAME, Context.MODE_PRIVATE)

    override fun saveSecret(handle: String, secret: String) {
        preferences.edit()
            .putString(handle, encrypt(secret))
            .apply()
    }

    override fun readSecret(handle: String): String? {
        val encoded = preferences.getString(handle, null) ?: return null
        return runCatching { decrypt(encoded) }.getOrNull()
    }

    override fun removeSecret(handle: String) {
        preferences.edit().remove(handle).apply()
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

private fun relaySecretHandle(deviceId: String, relayId: String): String {
    val digest = MessageDigest.getInstance("SHA-256")
        .digest("$deviceId\n$relayId".toByteArray(Charsets.UTF_8))
    return "relay-v1-" + digest.joinToString("") { "%02x".format(it) }
}

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
        isCanonicalOpaqueRouteValue(relayNonce)
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
