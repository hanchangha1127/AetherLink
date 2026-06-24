package com.localagentbridge.android

import org.junit.Assert.assertEquals
import org.junit.Test

class AppNavigationTest {
    @Test
    fun freshInstallStartsOnPairing() {
        val destination = resolveAppDestination(
            current = AppDestination.Chat,
            hasTrustedRuntime = false,
            pairingOnboardingCompleted = false,
        )

        assertEquals(AppDestination.Pairing, destination)
    }

    @Test
    fun trustedRuntimeLoadedFromPairingOnboardingGoesToChat() {
        val destination = resolveAppDestination(
            current = AppDestination.Pairing,
            hasTrustedRuntime = true,
            pairingOnboardingCompleted = false,
        )

        assertEquals(AppDestination.Chat, destination)
    }

    @Test
    fun settingsRemainsStableDuringPairingManagement() {
        val unpairedDestination = resolveAppDestination(
            current = AppDestination.Settings,
            hasTrustedRuntime = false,
            pairingOnboardingCompleted = false,
        )
        val trustedDestination = resolveAppDestination(
            current = AppDestination.Settings,
            hasTrustedRuntime = true,
            pairingOnboardingCompleted = true,
        )

        assertEquals(AppDestination.Settings, unpairedDestination)
        assertEquals(AppDestination.Settings, trustedDestination)
    }

    @Test
    fun completedOnboardingMovesPairingRouteToSettingsWhenRuntimeIsForgotten() {
        val destination = resolveAppDestination(
            current = AppDestination.Pairing,
            hasTrustedRuntime = false,
            pairingOnboardingCompleted = true,
        )

        assertEquals(AppDestination.Settings, destination)
    }
}
