package com.localagentbridge.android.runtime

import com.localagentbridge.android.core.protocol.ChatCancelPayload
import com.localagentbridge.android.core.protocol.ChatDeltaPayload
import com.localagentbridge.android.core.protocol.ChatDonePayload
import com.localagentbridge.android.core.protocol.ErrorPayload
import com.localagentbridge.android.core.protocol.MessageType
import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import kotlinx.serialization.KSerializer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.encodeToJsonElement
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test

class RuntimeClientViewModelTest {
    @Test
    fun trustedRuntimeConnectionTargetUsesTrustedMacInsteadOfManualHostFields() {
        val state = RuntimeUiState(
            macHost = "127.0.0.1",
            macPort = "11434",
            trustedMac = RuntimeTrustedMac(
                deviceId = "mac-1",
                name = "AetherLink Mac",
                host = "192.168.1.20",
                port = 43170,
            ),
        )

        val target = trustedRuntimeConnectionTarget(state)

        assertEquals("192.168.1.20", target?.host)
        assertEquals(43170, target?.port)
    }

    @Test
    fun staleChatDeltaAndDoneForDifferentRequestIdAreIgnored() {
        val state = RuntimeUiState(
            messages = listOf(
                RuntimeChatMessage(role = "user", content = "Hello"),
                RuntimeChatMessage(role = "assistant", content = "Partial"),
            ),
            isStreaming = true,
            activeRequestId = "active-request",
        )

        val afterDelta = state.withChatDelta(
            envelope(
                type = MessageType.ChatDelta,
                requestId = "stale-request",
                serializer = ChatDeltaPayload.serializer(),
                payload = ChatDeltaPayload(delta = " stale"),
            ),
            ChatDeltaPayload(delta = " stale"),
        )
        val afterDone = afterDelta.withChatDone(
            envelope(
                type = MessageType.ChatDone,
                requestId = "stale-request",
                serializer = ChatDonePayload.serializer(),
                payload = ChatDonePayload(),
            ),
            ChatDonePayload(),
        )

        assertSame(state, afterDelta)
        assertSame(afterDelta, afterDone)
        assertTrue(afterDone.isStreaming)
        assertEquals("active-request", afterDone.activeRequestId)
        assertEquals("Partial", afterDone.messages.last().content)
    }

    @Test
    fun chatDeltaAppendsReasoningWithoutMixingIntoAnswerContent() {
        val state = RuntimeUiState(
            messages = listOf(
                RuntimeChatMessage(role = "user", content = "Hello"),
                RuntimeChatMessage(role = "assistant", content = "Final", reasoning = "Plan"),
            ),
            isStreaming = true,
            activeRequestId = "active-request",
        )

        val afterReasoning = state.withChatDelta(
            envelope(
                type = MessageType.ChatDelta,
                requestId = "active-request",
                serializer = ChatDeltaPayload.serializer(),
                payload = ChatDeltaPayload(reasoningDelta = " step"),
            ),
            ChatDeltaPayload(reasoningDelta = " step"),
        )
        val afterAnswer = afterReasoning.withChatDelta(
            envelope(
                type = MessageType.ChatDelta,
                requestId = "active-request",
                serializer = ChatDeltaPayload.serializer(),
                payload = ChatDeltaPayload(delta = " answer"),
            ),
            ChatDeltaPayload(delta = " answer"),
        )

        val message = afterAnswer.messages.last()
        assertEquals("Final answer", message.content)
        assertEquals("Plan step", message.reasoning)
    }

    @Test
    fun thinkingDeltaAliasAppendsReasoning() {
        val state = RuntimeUiState(
            messages = listOf(RuntimeChatMessage(role = "assistant", content = "")),
            isStreaming = true,
            activeRequestId = "active-request",
        )

        val afterDelta = state.withChatDelta(
            envelope(
                type = MessageType.ChatDelta,
                requestId = "active-request",
                serializer = ChatDeltaPayload.serializer(),
                payload = ChatDeltaPayload(thinkingDelta = "Considering context"),
            ),
            ChatDeltaPayload(thinkingDelta = "Considering context"),
        )

        assertEquals("", afterDelta.messages.last().content)
        assertEquals("Considering context", afterDelta.messages.last().reasoning)
    }

    @Test
    fun staleReasoningDeltaForDifferentRequestIdIsIgnored() {
        val state = RuntimeUiState(
            messages = listOf(
                RuntimeChatMessage(role = "assistant", content = "Partial", reasoning = "Plan"),
            ),
            isStreaming = true,
            activeRequestId = "active-request",
        )

        val afterDelta = state.withChatDelta(
            envelope(
                type = MessageType.ChatDelta,
                requestId = "stale-request",
                serializer = ChatDeltaPayload.serializer(),
                payload = ChatDeltaPayload(reasoningDelta = " stale"),
            ),
            ChatDeltaPayload(reasoningDelta = " stale"),
        )

        assertSame(state, afterDelta)
        assertEquals("Partial", afterDelta.messages.last().content)
        assertEquals("Plan", afterDelta.messages.last().reasoning)
    }

    @Test
    fun cancelAckAndErrorForUnrelatedRequestsDoNotClearActiveStreaming() {
        val state = RuntimeUiState(
            messages = listOf(RuntimeChatMessage(role = "assistant", content = "Partial")),
            isStreaming = true,
            activeRequestId = "active-request",
            isLoadingModels = true,
            installingModelId = "lm_studio:model",
        )

        val afterCancel = state.withChatCancelAck(
            envelope(
                type = MessageType.ChatCancel,
                requestId = "cancel-request",
                serializer = ChatCancelPayload.serializer(),
                payload = ChatCancelPayload(targetRequestId = "other-request"),
            ),
            ChatCancelPayload(targetRequestId = "other-request"),
        )
        val afterError = afterCancel.withRuntimeError(
            envelope(
                type = MessageType.Error,
                requestId = "other-request",
                serializer = ErrorPayload.serializer(),
                payload = ErrorPayload(
                    code = "backend_failed",
                    message = "Different request failed",
                    retryable = false,
                ),
            ),
            ErrorPayload(
                code = "backend_failed",
                message = "Different request failed",
                retryable = false,
            ),
            pendingModelPullRequestId = "model-pull-request",
        )

        assertSame(state, afterCancel)
        assertTrue(afterError.isStreaming)
        assertEquals("active-request", afterError.activeRequestId)
        assertEquals("lm_studio:model", afterError.installingModelId)
        assertFalse(afterError.isLoadingModels)
        assertEquals("backend_failed", afterError.error?.code)
        assertEquals("Different request failed", afterError.error?.detail)
    }

    @Test
    fun activeChatDoneAndCancelClearStreamingOnlyForActiveRequest() {
        val state = RuntimeUiState(
            isStreaming = true,
            activeRequestId = "active-request",
            error = RuntimeUiError("previous_error"),
        )

        val afterDone = state.withChatDone(
            envelope(
                type = MessageType.ChatDone,
                requestId = "active-request",
                serializer = ChatDonePayload.serializer(),
                payload = ChatDonePayload(finishReason = "cancelled"),
            ),
            ChatDonePayload(finishReason = "cancelled"),
        )
        val afterCancel = state.withChatCancelAck(
            envelope(
                type = MessageType.ChatCancel,
                requestId = "cancel-request",
                serializer = ChatCancelPayload.serializer(),
                payload = ChatCancelPayload(targetRequestId = "active-request"),
            ),
            ChatCancelPayload(targetRequestId = "active-request"),
        )

        assertFalse(afterDone.isStreaming)
        assertNull(afterDone.activeRequestId)
        assertEquals("generation_cancelled", afterDone.error?.code)
        assertFalse(afterCancel.isStreaming)
        assertNull(afterCancel.activeRequestId)
        assertNull(afterCancel.error)
    }

    @Test
    fun persistedMessagesCreateSortedSessionSummaryAndReloadActiveMessages() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "older",
                messages = listOf(RuntimeChatMessage(id = "m1", role = "user", content = "Older question")),
                nowMillis = 100L,
            )
            .withPersistedMessages(
                sessionId = "newer",
                messages = listOf(
                    RuntimeChatMessage(id = "m2", role = "user", content = "Newer question"),
                    RuntimeChatMessage(id = "m3", role = "assistant", content = "Newer answer"),
                ),
                nowMillis = 200L,
            )

        val sessions = runtimeChatSessions(data)

        assertEquals(listOf("newer", "older"), sessions.map { it.id })
        assertEquals("Newer question", sessions.first().title)
        assertEquals(2, sessions.first().messageCount)
        assertEquals("newer", data.activeSessionId)
        assertEquals("Newer answer", activeSessionMessages(data).last().content)
    }

    @Test
    fun noActiveSessionKeepsPreviousChatsButClearsCurrentMessages() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "previous",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Saved chat")),
                nowMillis = 100L,
            )
            .withNoActiveSession()

        assertNull(data.activeSessionId)
        assertEquals(listOf("previous"), runtimeChatSessions(data).map { it.id })
        assertTrue(activeSessionMessages(data).isEmpty())
    }

    @Test
    fun renamedChatSessionUsesTrimmedTitleAndMovesSessionToTop() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "older",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Older question")),
                nowMillis = 100L,
            )
            .withPersistedMessages(
                sessionId = "newer",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Newer question")),
                nowMillis = 200L,
            )
            .withRenamedChatSession(
                sessionId = "older",
                title = "  Renamed chat  ",
                nowMillis = 300L,
            )

        val sessions = runtimeChatSessions(data)

        assertEquals(listOf("older", "newer"), sessions.map { it.id })
        assertEquals("Renamed chat", sessions.first().title)
        assertEquals(300L, sessions.first().updatedAtMillis)
        assertEquals("newer", data.activeSessionId)
    }

    @Test
    fun persistedMessagesPreserveRenamedChatSessionTitle() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "session",
                messages = listOf(RuntimeChatMessage(id = "m1", role = "user", content = "Original prompt")),
                nowMillis = 100L,
            )
            .withRenamedChatSession(
                sessionId = "session",
                title = "Project notes",
                nowMillis = 200L,
            )
            .withPersistedMessages(
                sessionId = "session",
                messages = listOf(
                    RuntimeChatMessage(id = "m1", role = "user", content = "Original prompt"),
                    RuntimeChatMessage(id = "m2", role = "assistant", content = "Answer"),
                    RuntimeChatMessage(id = "m3", role = "user", content = "Follow up"),
                ),
                nowMillis = 300L,
            )

        val session = runtimeChatSessions(data).single()

        assertEquals("Project notes", session.title)
        assertEquals(3, session.messageCount)
    }

    @Test
    fun deleteActiveChatSessionClearsActiveMessagesAndKeepsOtherSessions() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "older",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Older question")),
                nowMillis = 100L,
            )
            .withPersistedMessages(
                sessionId = "active",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Active question")),
                nowMillis = 200L,
            )
            .withoutChatSession("active")

        assertNull(data.activeSessionId)
        assertEquals(listOf("older"), runtimeChatSessions(data).map { it.id })
        assertTrue(activeSessionMessages(data).isEmpty())
    }

    @Test
    fun deleteInactiveChatSessionPreservesActiveSessionAndMessages() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "inactive",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Inactive question")),
                nowMillis = 100L,
            )
            .withPersistedMessages(
                sessionId = "active",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Active question")),
                nowMillis = 200L,
            )
            .withoutChatSession("inactive")

        assertEquals("active", data.activeSessionId)
        assertEquals(listOf("active"), runtimeChatSessions(data).map { it.id })
        assertEquals("Active question", activeSessionMessages(data).single().content)
    }

    @Test
    fun archivedChatSessionIsExcludedFromPreviousChatsAndClearsActiveSession() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "older",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Older question")),
                nowMillis = 100L,
            )
            .withPersistedMessages(
                sessionId = "active",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Active question")),
                nowMillis = 200L,
            )
            .withArchivedChatSession(
                sessionId = "active",
                nowMillis = 300L,
            )

        assertNull(data.activeSessionId)
        assertEquals(listOf("older"), runtimeChatSessions(data).map { it.id })
        assertEquals(listOf("active"), archivedRuntimeChatSessions(data).map { it.id })
        assertEquals(300L, archivedRuntimeChatSessions(data).single().archivedAtMillis)
        assertTrue(activeSessionMessages(data).isEmpty())
    }

    @Test
    fun archiveAllChatSessionsRetainsSessionsAsArchivedAndKeepsMemoryCandidatesEmpty() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "first",
                messages = listOf(RuntimeChatMessage(role = "user", content = "First question")),
                nowMillis = 100L,
            )
            .withPersistedMessages(
                sessionId = "second",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Second question")),
                nowMillis = 200L,
            )
            .withArchivedChatSessions(nowMillis = 300L)

        assertNull(data.activeSessionId)
        assertTrue(runtimeChatSessions(data).isEmpty())
        assertEquals(listOf("first", "second"), archivedRuntimeChatSessions(data).map { it.id }.sorted())
        assertTrue(memoryCandidateChatSessions(data).isEmpty())
        assertTrue(reflectionCandidateChatSessions(data).isEmpty())
        assertTrue(researchCandidateChatSessions(data).isEmpty())
    }

    @Test
    fun unarchivedChatSessionReturnsToPreviousChatsWithoutBecomingActive() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "session",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Saved chat")),
                nowMillis = 100L,
            )
            .withArchivedChatSession(
                sessionId = "session",
                nowMillis = 200L,
            )
            .withUnarchivedChatSession(
                sessionId = "session",
                nowMillis = 300L,
            )

        assertNull(data.activeSessionId)
        assertEquals(listOf("session"), runtimeChatSessions(data).map { it.id })
        assertTrue(archivedRuntimeChatSessions(data).isEmpty())
        assertNull(runtimeChatSessions(data).single().archivedAtMillis)
        assertEquals(300L, runtimeChatSessions(data).single().updatedAtMillis)
    }

    @Test
    fun archivedChatSessionCannotBeSelectedAsActiveSession() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "session",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Saved chat")),
                nowMillis = 100L,
            )
            .withArchivedChatSession(
                sessionId = "session",
                nowMillis = 200L,
            )
            .withActiveSession("session")

        assertNull(data.activeSessionId)
        assertTrue(activeSessionMessages(data).isEmpty())
    }

    @Test
    fun candidateChatSessionHelpersExcludeArchivedSessions() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "active-candidate",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Candidate")),
                nowMillis = 100L,
            )
            .withPersistedMessages(
                sessionId = "archived-candidate",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Archived")),
                nowMillis = 200L,
            )
            .withArchivedChatSession(
                sessionId = "archived-candidate",
                nowMillis = 300L,
            )

        assertEquals(listOf("active-candidate"), memoryCandidateChatSessions(data).map { it.id })
        assertEquals(listOf("active-candidate"), reflectionCandidateChatSessions(data).map { it.id })
        assertEquals(listOf("active-candidate"), researchCandidateChatSessions(data).map { it.id })
    }

    @Test
    fun clearChatSessionsRemovesOnlySessionsAndActiveMessages() {
        val data = PersistedRuntimeData()
            .withPersistedMessages(
                sessionId = "session",
                messages = listOf(RuntimeChatMessage(role = "user", content = "Saved chat")),
                nowMillis = 100L,
            )
            .withMemoryEntry(
                content = "Keep memory",
                nowMillis = 200L,
                entryId = "memory-1",
            )
            .withoutChatSessions()

        assertNull(data.activeSessionId)
        assertTrue(runtimeChatSessions(data).isEmpty())
        assertTrue(activeSessionMessages(data).isEmpty())
        assertEquals("Keep memory", data.memoryEntries.single().content)
    }

    @Test
    fun chatSendMessagesPrependsOnlyEnabledMemoryAsSystemContext() {
        val messages = listOf(
            RuntimeChatMessage(role = "system", content = "UI-only system"),
            RuntimeChatMessage(role = "user", content = "Hello"),
            RuntimeChatMessage(role = "assistant", content = ""),
        )
        val memory = listOf(
            RuntimeMemoryEntry(
                id = "enabled",
                content = "Prefers concise answers",
                enabled = true,
                createdAtMillis = 1L,
                updatedAtMillis = 1L,
            ),
            RuntimeMemoryEntry(
                id = "disabled",
                content = "Disabled memory",
                enabled = false,
                createdAtMillis = 2L,
                updatedAtMillis = 2L,
            ),
        )

        val payloadMessages = chatSendMessages(messages, memory)

        assertEquals("system", payloadMessages[0].role)
        assertEquals("Local user memory:\n- Prefers concise answers", payloadMessages[0].content)
        assertEquals("user", payloadMessages[1].role)
        assertEquals("Hello", payloadMessages[1].content)
        assertEquals(2, payloadMessages.size)
    }

    @Test
    fun memoryEntryHelpersStoreRemoveAndDisableEntries() {
        val withEntry = PersistedRuntimeData().withMemoryEntry(
            content = "  Remember this locally  ",
            nowMillis = 10L,
            entryId = "memory-1",
        )
        val disabled = withEntry.withMemoryEntryEnabled(
            entryId = "memory-1",
            enabled = false,
            nowMillis = 20L,
        )
        val removed = disabled.withoutMemoryEntry("memory-1")

        assertEquals("Remember this locally", withEntry.memoryEntries.single().content)
        assertFalse(disabled.memoryEntries.single().enabled)
        assertEquals(20L, disabled.memoryEntries.single().updatedAtMillis)
        assertTrue(removed.memoryEntries.isEmpty())
    }

    private fun <T> envelope(
        type: String,
        requestId: String,
        serializer: KSerializer<T>,
        payload: T,
    ): ProtocolEnvelope {
        return ProtocolEnvelope(
            type = type,
            requestId = requestId,
            payload = json.encodeToJsonElement(serializer, payload).jsonObject,
        )
    }

    private companion object {
        val json = Json {
            ignoreUnknownKeys = true
            explicitNulls = false
            encodeDefaults = true
        }
    }
}
