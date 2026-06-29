package com.localagentbridge.android

import androidx.annotation.StringRes
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.filled.Settings
import androidx.compose.ui.graphics.vector.ImageVector

internal enum class AppDestination(
    @param:StringRes val labelRes: Int,
    val icon: ImageVector,
) {
    Chat(R.string.tab_chat, Icons.AutoMirrored.Filled.Chat),
    Settings(R.string.tab_settings, Icons.Filled.Settings),
}

internal fun resolveAppDestination(
    current: AppDestination,
    hasTrustedRuntime: Boolean,
): AppDestination {
    if (!hasTrustedRuntime) {
        return AppDestination.Settings
    }
    return current
}

internal fun shouldReturnToChatAfterPairing(
    returnToChatAfterPairing: Boolean,
    hasTrustedRuntime: Boolean,
    isConnected: Boolean,
    isConnecting: Boolean,
    isPairingAwaitingRoute: Boolean,
): Boolean {
    return returnToChatAfterPairing &&
        hasTrustedRuntime &&
        isConnected &&
        !isConnecting &&
        !isPairingAwaitingRoute
}

internal fun shouldTreatPairingQrAsOnboarding(
    destination: AppDestination,
    hasTrustedRuntime: Boolean,
    isPairingAwaitingRoute: Boolean,
): Boolean {
    return !hasTrustedRuntime ||
        destination == AppDestination.Chat ||
        isPairingAwaitingRoute
}

internal fun shouldLeavePairingSettingsAfterTrustedRuntimeReady(
    destination: AppDestination,
    hasTrustedRuntime: Boolean,
    settingsOpenedForPairingOnboarding: Boolean,
    isPairingAwaitingRoute: Boolean,
): Boolean {
    return hasTrustedRuntime &&
        settingsOpenedForPairingOnboarding &&
        destination == AppDestination.Settings &&
        !isPairingAwaitingRoute
}

internal fun shouldUsePermanentNavigationRail(screenWidthDp: Int): Boolean {
    return screenWidthDp >= 840
}

@StringRes
internal fun appDestinationTitleRes(
    destination: AppDestination,
    hasTrustedRuntime: Boolean,
    isPairingAwaitingRoute: Boolean,
): Int {
    return if (
        destination == AppDestination.Settings &&
        (!hasTrustedRuntime || isPairingAwaitingRoute)
    ) {
        R.string.pairing_title
    } else {
        destination.labelRes
    }
}
