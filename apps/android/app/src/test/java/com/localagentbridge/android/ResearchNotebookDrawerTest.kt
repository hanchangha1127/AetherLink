package com.localagentbridge.android

import com.localagentbridge.android.core.protocol.ResearchNotebookPayload
import org.junit.Assert.assertEquals
import org.junit.Test

class ResearchNotebookDrawerTest {
    @Test
    fun researchNotebookDrawerGroupsPreserveRuntimeOrderAndSeparateArchivedRows() {
        val first = notebook(
            idSuffix = "00112233445566778899aabbccddeeff",
            title = "Most recent",
            updatedAt = "2026-07-14T00:02:00Z",
        )
        val second = notebook(
            idSuffix = "112233445566778899aabbccddeeff00",
            title = "Earlier",
            updatedAt = "2026-07-14T00:01:00Z",
        )
        val archived = notebook(
            idSuffix = "2233445566778899aabbccddeeff0011",
            title = "Archived",
            updatedAt = "2026-07-14T00:00:00Z",
            archivedAt = "2026-07-14T00:03:00Z",
        )

        val groups = researchNotebookDrawerGroups(
            listOf(first, archived, second),
        )

        assertEquals(listOf(first, second), groups.active)
        assertEquals(listOf(archived), groups.archived)
        assertEquals(
            "aetherlink_research_notebook_${first.sessionId}",
            researchNotebookDrawerRowTestTag(first.sessionId),
        )
        assertEquals(
            "aetherlink_research_notebook_options_${archived.sessionId}",
            researchNotebookDrawerOptionsTestTag(archived.sessionId),
        )
        assertEquals(
            "aetherlink_research_notebook_delete_${archived.sessionId}",
            researchNotebookDrawerMenuItemTestTag(archived.sessionId, "delete"),
        )
    }

    private fun notebook(
        idSuffix: String,
        title: String,
        updatedAt: String,
        archivedAt: String? = null,
    ) = ResearchNotebookPayload(
        notebookId = "research_notebook_$idSuffix",
        sessionId = "research_session_$idSuffix",
        title = title,
        model = "ollama:llama3.1:8b",
        sourceCount = 1,
        createdAt = "2026-07-14T00:00:00Z",
        updatedAt = updatedAt,
        archivedAt = archivedAt,
    )
}
