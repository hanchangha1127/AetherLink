package com.localagentbridge.android.runtime

import android.app.Application
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertEquals
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
    }
}
