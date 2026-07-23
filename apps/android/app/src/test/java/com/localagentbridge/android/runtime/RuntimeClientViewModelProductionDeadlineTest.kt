package com.localagentbridge.android.runtime

import android.app.Application
import androidx.test.core.app.ApplicationProvider
import com.localagentbridge.android.core.transport.PairedRuntimeIdentity
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class RuntimeClientViewModelProductionDeadlineTest {
    @Test
    fun productionFactoryEnablesHostAlignedMemorySummaryDeadlines() {
        val dependencies = RuntimeClientViewModelDependencies.create(
            ApplicationProvider.getApplicationContext<Application>(),
        )

        assertEquals(
            MEMORY_MUTATION_REQUEST_TIMEOUT_MS,
            dependencies.memoryMutationRequestTimeoutMillis,
        )
        assertEquals(
            MEMORY_SUMMARY_CONTROL_REQUEST_TIMEOUT_MS,
            dependencies.memorySummaryControlRequestTimeoutMillis,
        )
        assertEquals(
            MEMORY_SUMMARY_GENERATION_REQUEST_TIMEOUT_MS,
            dependencies.memorySummaryGenerationRequestTimeoutMillis,
        )
        assertTrue(
            requireNotNull(dependencies.memorySummaryGenerationRequestTimeoutMillis) > 60_000L,
        )
        val controller = dependencies.productionActivationController
        assertNotNull(controller)
        assertTrue(requireNotNull(controller).usesClock(dependencies.currentTimeMillis))
        assertTrue(
            controller.usesPairingStore(
                (dependencies.trustedRuntimeStore as RuntimeProductionPairingStoreProvider)
                    .pairingStoreForProductionComposition(),
            ),
        )
        assertTrue(
            controller.prepareRemoteRoutes(
                PairedRuntimeIdentity(
                    deviceId = "unpublished-runtime",
                    name = "Unpublished runtime",
                ),
            ).isEmpty(),
        )
        controller.close()
    }
}
