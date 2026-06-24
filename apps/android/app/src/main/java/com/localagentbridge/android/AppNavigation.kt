package com.localagentbridge.android

import androidx.annotation.StringRes
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.Settings
import androidx.compose.ui.graphics.vector.ImageVector

internal enum class AppDestination(
    @param:StringRes val labelRes: Int,
    val icon: ImageVector,
) {
    Chat(R.string.tab_chat, Icons.AutoMirrored.Filled.Chat),
    Pairing(R.string.tab_pairing, Icons.Filled.Link),
    Settings(R.string.tab_settings, Icons.Filled.Settings),
}

internal fun resolveAppDestination(
    current: AppDestination,
    hasTrustedRuntime: Boolean,
    pairingOnboardingCompleted: Boolean,
): AppDestination {
    if (current == AppDestination.Settings) return AppDestination.Settings
    if (!hasTrustedRuntime && !pairingOnboardingCompleted) return AppDestination.Pairing
    if (current == AppDestination.Pairing && hasTrustedRuntime) return AppDestination.Chat
    if (current == AppDestination.Pairing && pairingOnboardingCompleted) return AppDestination.Settings
    return current
}
