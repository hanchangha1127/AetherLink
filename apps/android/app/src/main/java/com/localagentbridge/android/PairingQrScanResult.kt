package com.localagentbridge.android

import com.localagentbridge.android.runtime.RuntimePairingQrParseResult
import com.localagentbridge.android.runtime.parseRuntimePairingQrPayload
import java.net.URI
import java.util.Locale

internal enum class PairingQrRawValueScanResult {
    Valid,
    InvalidPairingQr,
    UnsupportedQr,
}

internal sealed interface PairingQrScanResult {
    data class Valid(val rawValue: String) : PairingQrScanResult
    data object InvalidPairingQr : PairingQrScanResult
    data object UnsupportedQr : PairingQrScanResult
}

internal fun String.isAetherLinkPairingQrValue(
    requireRemoteRoute: Boolean = true,
): Boolean {
    val result = parseRuntimePairingQrPayload(
        rawValue = trim(),
        allowDebugLoopbackRelay = BuildConfig.DEBUG,
        allowDiagnosticLocalDirectEndpoint = BuildConfig.DEBUG,
        requireRemoteRoute = requireRemoteRoute,
    )
    return result is RuntimePairingQrParseResult.Accepted
}

internal fun String.aetherLinkPairingQrRawValueScanResult(
    requireRemoteRoute: Boolean = true,
): PairingQrRawValueScanResult {
    val trimmed = trim()
    if (!trimmed.isAetherLinkPairingQrCandidateValue()) {
        return PairingQrRawValueScanResult.UnsupportedQr
    }
    return when (
        parseRuntimePairingQrPayload(
            rawValue = trimmed,
            allowDebugLoopbackRelay = BuildConfig.DEBUG,
            allowDiagnosticLocalDirectEndpoint = BuildConfig.DEBUG,
            requireRemoteRoute = requireRemoteRoute,
        )
    ) {
        is RuntimePairingQrParseResult.Accepted -> PairingQrRawValueScanResult.Valid
        is RuntimePairingQrParseResult.Rejected -> PairingQrRawValueScanResult.InvalidPairingQr
    }
}

internal fun String.isAetherLinkPairingQrCandidateValue(): Boolean {
    val uri = runCatching { URI(trim()) }.getOrNull() ?: return false
    val scheme = uri.scheme?.lowercase(Locale.US)
    if (scheme != "aetherlink" && scheme != "lab") return false
    val action = uri.host?.lowercase(Locale.US)
    return action == "pair"
}

internal fun Iterable<String?>.aetherLinkPairingScanResultOrNull(
    requireRemoteRoute: Boolean = true,
): PairingQrScanResult? {
    var sawInvalidPairingQr = false
    var sawUnsupportedQr = false
    for (rawValue in this) {
        val nonBlankRawValue = rawValue
            ?.takeIf { it.isNotBlank() }
            ?: continue
        when (nonBlankRawValue.aetherLinkPairingQrRawValueScanResult(requireRemoteRoute = requireRemoteRoute)) {
            PairingQrRawValueScanResult.Valid -> {
                return PairingQrScanResult.Valid(nonBlankRawValue)
            }
            PairingQrRawValueScanResult.InvalidPairingQr -> {
                sawInvalidPairingQr = true
            }
            PairingQrRawValueScanResult.UnsupportedQr -> {
                sawUnsupportedQr = true
            }
        }
    }
    return when {
        sawInvalidPairingQr -> PairingQrScanResult.InvalidPairingQr
        sawUnsupportedQr -> PairingQrScanResult.UnsupportedQr
        else -> null
    }
}
