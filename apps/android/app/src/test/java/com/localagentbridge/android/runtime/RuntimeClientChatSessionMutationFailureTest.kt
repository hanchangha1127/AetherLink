package com.localagentbridge.android.runtime

import android.app.Application
import com.localagentbridge.android.core.pairing.DeviceIdentity
import com.localagentbridge.android.core.pairing.TrustedRuntime
import com.localagentbridge.android.core.protocol.ChatMessagesListRequestPayload
import com.localagentbridge.android.core.protocol.ChatMessagesListResultPayload
import com.localagentbridge.android.core.protocol.ChatSessionLifecyclePayload
import com.localagentbridge.android.core.protocol.ChatSessionRenamePayload
import com.localagentbridge.android.core.protocol.ChatSessionSummaryPayload
import com.localagentbridge.android.core.protocol.ChatSessionsListResultPayload
import com.localagentbridge.android.core.protocol.ErrorPayload
import com.localagentbridge.android.core.protocol.MessageType
import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import com.localagentbridge.android.core.transport.DiscoveredRuntime
import com.localagentbridge.android.core.transport.RuntimeProtocolChannel
import com.localagentbridge.android.core.transport.RuntimeRelayConnector
import com.localagentbridge.android.core.transport.RuntimeTransportClient
import com.localagentbridge.android.core.transport.RuntimeTransportConnector
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import kotlinx.serialization.encodeToString
import kotlinx.serialization.KSerializer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.encodeToJsonElement
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.put
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.security.KeyPairGenerator
import java.security.spec.ECGenParameterSpec

@OptIn(ExperimentalCoroutinesApi::class)
class RuntimeClientChatSessionMutationFailureTest {
    private val json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
        encodeDefaults = true
    }

    @After
    fun resetMainDispatcher() {
        Dispatchers.resetMain()
    }

    @Test
    fun runtimeOwnedRenameErrorRequestsRuntimeSessionResyncAndRestoresRuntimeTitle() = runTest {
        withMainDispatcher {
            val fixture = createAuthenticatedRuntimeClientFixture(
                initialData = PersistedRuntimeData(
                    sessions = listOf(
                        PersistedChatSession(
                            id = "runtime-session",
                            title = "Runtime title",
                            modelId = "ollama:llama3.1:8b",
                            createdAtMillis = 100L,
                            updatedAtMillis = 200L,
                            runtimeOwned = true,
                            runtimeMessageCount = 2,
                        ),
                    ),
                ),
            )
            try {
            val initialSessionListCount = fixture.channel.sentEnvelopes.count { it.type == MessageType.ChatSessionsList }

            fixture.viewModel.renameChatSession("runtime-session", "Rejected local title")
            runCurrent()
            assertEquals(
                "Rejected local title",
                fixture.viewModel.state.value.chatSessions.single { it.id == "runtime-session" }.title,
            )

            val renameRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.ChatSessionRename }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.Error,
                    serializer = ErrorPayload.serializer(),
                    payload = ErrorPayload(
                        code = "chat_session_not_found",
                        message = "Runtime refused rename",
                        retryable = true,
                    ),
                    requestId = renameRequest.requestId,
                ),
            )
            runCurrent()

            assertEquals("chat_session_sync_failed", fixture.viewModel.state.value.error?.code)
            assertEquals("Runtime refused rename", fixture.viewModel.state.value.error?.technicalDetail)
            assertEquals(
                200L,
                fixture.localStore.data.sessions.single { it.id == "runtime-session" }.updatedAtMillis,
            )
            assertEquals(
                initialSessionListCount + 1,
                fixture.channel.sentEnvelopes.count { it.type == MessageType.ChatSessionsList },
            )

            completeRuntimeSessionList(
                fixture = fixture,
                title = "Runtime title",
                status = "active",
                messageCount = 2,
            )
            assertEquals(
                "Runtime title",
                fixture.viewModel.state.value.chatSessions.single { it.id == "runtime-session" }.title,
            )
            } finally {
                fixture.viewModel.disconnect()
                runCurrent()
            }
        }
    }

    @Test
    fun runtimeOwnedArchiveErrorRequestsRuntimeSessionResyncAndRestoresActiveSession() = runTest {
        withMainDispatcher {
            val fixture = createAuthenticatedRuntimeClientFixture(
                initialData = PersistedRuntimeData(
                    activeSessionId = "runtime-session",
                    sessions = listOf(
                        PersistedChatSession(
                            id = "runtime-session",
                            title = "Runtime title",
                            modelId = "ollama:llama3.1:8b",
                            createdAtMillis = 100L,
                            updatedAtMillis = 200L,
                            runtimeOwned = true,
                            runtimeMessageCount = 2,
                        ),
                    ),
                ),
            )
            try {
            val initialSessionListCount = fixture.channel.sentEnvelopes.count { it.type == MessageType.ChatSessionsList }

            fixture.viewModel.archiveChatSession("runtime-session")
            runCurrent()
            assertTrue(fixture.viewModel.state.value.chatSessions.none { it.id == "runtime-session" })
            assertEquals(listOf("runtime-session"), fixture.viewModel.state.value.archivedChatSessions.map { it.id })

            val archiveRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.ChatSessionArchive }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.Error,
                    serializer = ErrorPayload.serializer(),
                    payload = ErrorPayload(
                        code = "chat_session_not_found",
                        message = "Runtime refused archive",
                        retryable = true,
                    ),
                    requestId = archiveRequest.requestId,
                ),
            )
            runCurrent()

            assertEquals("chat_session_sync_failed", fixture.viewModel.state.value.error?.code)
            assertEquals(
                initialSessionListCount + 1,
                fixture.channel.sentEnvelopes.count { it.type == MessageType.ChatSessionsList },
            )

            completeRuntimeSessionList(
                fixture = fixture,
                title = "Runtime title",
                status = "active",
                messageCount = 2,
            )
            assertEquals(listOf("runtime-session"), fixture.viewModel.state.value.chatSessions.map { it.id })
            assertTrue(fixture.viewModel.state.value.archivedChatSessions.none { it.id == "runtime-session" })
            } finally {
                fixture.viewModel.disconnect()
                runCurrent()
            }
        }
    }

    @Test
    fun runtimeOwnedDeleteErrorRequestsRuntimeSessionResyncAndRestoresArchivedSession() = runTest {
        withMainDispatcher {
            val fixture = createAuthenticatedRuntimeClientFixture(
                initialData = PersistedRuntimeData(
                    sessions = listOf(
                        PersistedChatSession(
                            id = "runtime-archived",
                            title = "Archived runtime title",
                            modelId = "ollama:llama3.1:8b",
                            createdAtMillis = 100L,
                            updatedAtMillis = 200L,
                            archivedAtMillis = 300L,
                            runtimeOwned = true,
                            runtimeMessageCount = 2,
                        ),
                    ),
                ),
            )
            try {
            val initialSessionListCount = fixture.channel.sentEnvelopes.count { it.type == MessageType.ChatSessionsList }

            fixture.viewModel.deleteChatSession("runtime-archived")
            runCurrent()
            assertTrue(fixture.viewModel.state.value.archivedChatSessions.none { it.id == "runtime-archived" })

            val deleteRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.ChatSessionDelete }
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.Error,
                    serializer = ErrorPayload.serializer(),
                    payload = ErrorPayload(
                        code = "chat_session_not_found",
                        message = "Runtime refused delete",
                        retryable = true,
                    ),
                    requestId = deleteRequest.requestId,
                ),
            )
            runCurrent()

            assertEquals("chat_session_sync_failed", fixture.viewModel.state.value.error?.code)
            assertEquals(
                initialSessionListCount + 1,
                fixture.channel.sentEnvelopes.count { it.type == MessageType.ChatSessionsList },
            )

            completeRuntimeSessionList(
                fixture = fixture,
                sessionId = "runtime-archived",
                title = "Archived runtime title",
                status = "archived",
                archivedAt = "2026-06-23T09:05:05Z",
                messageCount = 2,
            )
            assertEquals(listOf("runtime-archived"), fixture.viewModel.state.value.archivedChatSessions.map { it.id })
            } finally {
                fixture.viewModel.disconnect()
                runCurrent()
            }
        }
    }

    @Test
    fun chatSessionRenameResultRejectsUnknownMetadataBeforeCachePublication() = runTest {
        withMainDispatcher {
            val fixture = createAuthenticatedRuntimeClientFixture(
                initialData = PersistedRuntimeData(
                    sessions = listOf(
                        PersistedChatSession(
                            id = "runtime-session",
                            title = "Runtime title",
                            modelId = "ollama:llama3.1:8b",
                            createdAtMillis = 100L,
                            updatedAtMillis = 200L,
                            runtimeOwned = true,
                            runtimeMessageCount = 2,
                        ),
                    ),
                ),
            )
            try {
                val initialSessionListCount = fixture.channel.sentEnvelopes.count {
                    it.type == MessageType.ChatSessionsList
                }

                fixture.viewModel.renameChatSession("runtime-session", "Optimistic title")
                runCurrent()

                val renameRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.ChatSessionRename }
                fixture.channel.enqueue(
                    ProtocolEnvelope(
                        type = MessageType.ChatSessionRename,
                        requestId = renameRequest.requestId,
                        payload = buildJsonObject {
                            put("session_id", "runtime-session")
                            put("title", "Leaky Runtime Title")
                            put("renamed_at", "2026-06-23T09:02:00Z")
                            put("backend_url", "http://127.0.0.1:11434")
                        },
                    ),
                )
                runCurrent()

                val rejectedState = fixture.viewModel.state.value
                assertEquals("invalid_payload", rejectedState.error?.code)
                assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("chat.session.rename"))
                assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("backend_url"))
                assertEquals(
                    "Runtime title",
                    rejectedState.chatSessions.single { it.id == "runtime-session" }.title,
                )
                assertTrue(!json.encodeToString(fixture.localStore.data).contains("Leaky Runtime Title"))
                assertTrue(!json.encodeToString(fixture.localStore.data).contains("127.0.0.1:11434"))
                assertEquals(
                    initialSessionListCount + 1,
                    fixture.channel.sentEnvelopes.count { it.type == MessageType.ChatSessionsList },
                )

                fixture.channel.enqueue(
                    envelope(
                        type = MessageType.ChatSessionRename,
                        serializer = ChatSessionRenamePayload.serializer(),
                        payload = ChatSessionRenamePayload(
                            sessionId = "runtime-session",
                            title = "Canonical Runtime Title",
                            renamedAt = "2026-06-23T09:02:00Z",
                        ),
                        requestId = renameRequest.requestId,
                    ),
                )
                runCurrent()

                val acceptedState = fixture.viewModel.state.value
                assertEquals("invalid_payload", acceptedState.error?.code)
                assertEquals(
                    "Runtime title",
                    acceptedState.chatSessions.single { it.id == "runtime-session" }.title,
                )
                assertEquals(
                    initialSessionListCount + 1,
                    fixture.channel.sentEnvelopes.count { it.type == MessageType.ChatSessionsList },
                )
            } finally {
                fixture.viewModel.disconnect()
                runCurrent()
            }
        }
    }

    @Test
    fun chatSessionLifecycleResultRejectsUnknownMetadataBeforeCachePublication() = runTest {
        withMainDispatcher {
            val fixture = createAuthenticatedRuntimeClientFixture(
                initialData = PersistedRuntimeData(
                    activeSessionId = "runtime-session",
                    sessions = listOf(
                        PersistedChatSession(
                            id = "runtime-session",
                            title = "Runtime title",
                            modelId = "ollama:llama3.1:8b",
                            createdAtMillis = 100L,
                            updatedAtMillis = 200L,
                            runtimeOwned = true,
                            runtimeMessageCount = 2,
                        ),
                    ),
                ),
            )
            try {
                val initialSessionListCount = fixture.channel.sentEnvelopes.count {
                    it.type == MessageType.ChatSessionsList
                }

                fixture.viewModel.archiveChatSession("runtime-session")
                runCurrent()

                val archiveRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.ChatSessionArchive }
                fixture.channel.enqueue(
                    ProtocolEnvelope(
                        type = MessageType.ChatSessionArchive,
                        requestId = archiveRequest.requestId,
                        payload = buildJsonObject {
                            put("session_id", "runtime-session")
                            put("status", "archived")
                            put("archived_at", "2026-06-23T09:03:00Z")
                            put("workspace_id", "workspace-canary")
                        },
                    ),
                )
                runCurrent()

                val rejectedState = fixture.viewModel.state.value
                assertEquals("invalid_payload", rejectedState.error?.code)
                assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("chat.session.archive"))
                assertTrue(rejectedState.error?.technicalDetail.orEmpty().contains("workspace_id"))
                assertEquals(null, fixture.localStore.data.sessions.single { it.id == "runtime-session" }.archivedAtMillis)
                assertTrue(!json.encodeToString(fixture.localStore.data).contains("workspace-canary"))
                assertEquals(
                    initialSessionListCount + 1,
                    fixture.channel.sentEnvelopes.count { it.type == MessageType.ChatSessionsList },
                )

                fixture.channel.enqueue(
                    envelope(
                        type = MessageType.ChatSessionArchive,
                        serializer = ChatSessionLifecyclePayload.serializer(),
                        payload = ChatSessionLifecyclePayload(
                            sessionId = "runtime-session",
                            status = "archived",
                            archivedAt = "2026-06-23T09:03:00Z",
                        ),
                        requestId = archiveRequest.requestId,
                    ),
                )
                runCurrent()

                val acceptedState = fixture.viewModel.state.value
                assertEquals("invalid_payload", acceptedState.error?.code)
                assertEquals(listOf("runtime-session"), acceptedState.chatSessions.map { it.id })
                assertEquals(null, fixture.localStore.data.sessions.single { it.id == "runtime-session" }.archivedAtMillis)
                assertEquals(
                    initialSessionListCount + 1,
                    fixture.channel.sentEnvelopes.count { it.type == MessageType.ChatSessionsList },
                )
            } finally {
                fixture.viewModel.disconnect()
                runCurrent()
            }
        }
    }

    @Test
    fun lifecycleAckMustMatchJournaledSessionAndOperation() = runTest {
        withMainDispatcher {
            val fixture = createAuthenticatedRuntimeClientFixture(
                initialData = PersistedRuntimeData(
                    sessions = listOf(
                        PersistedChatSession(
                            id = "runtime-a",
                            title = "Runtime A",
                            createdAtMillis = 100L,
                            updatedAtMillis = 200L,
                            archivedAtMillis = 300L,
                            runtimeOwned = true,
                        ),
                        PersistedChatSession(
                            id = "runtime-b",
                            title = "Runtime B",
                            createdAtMillis = 110L,
                            updatedAtMillis = 210L,
                            archivedAtMillis = 310L,
                            runtimeOwned = true,
                        ),
                    ),
                ),
            )
            try {
                val initialSessionListCount = fixture.channel.sentEnvelopes.count {
                    it.type == MessageType.ChatSessionsList
                }
                fixture.viewModel.deleteChatSession("runtime-a")
                runCurrent()
                val deleteRequest = fixture.channel.sentEnvelopes.last {
                    it.type == MessageType.ChatSessionDelete
                }

                fixture.channel.enqueue(
                    envelope(
                        type = MessageType.ChatSessionDelete,
                        serializer = ChatSessionLifecyclePayload.serializer(),
                        payload = ChatSessionLifecyclePayload(
                            sessionId = "runtime-b",
                            status = "archived",
                            archivedAt = "2026-06-23T09:03:00Z",
                        ),
                        requestId = deleteRequest.requestId,
                    ),
                )
                runCurrent()

                assertEquals("invalid_payload", fixture.viewModel.state.value.error?.code)
                assertEquals(
                    setOf("runtime-a", "runtime-b"),
                    fixture.viewModel.state.value.archivedChatSessions.mapTo(mutableSetOf()) { it.id },
                )
                assertTrue(fixture.localStore.data.suppressedRuntimeSessions.isEmpty())
                assertEquals(
                    initialSessionListCount + 1,
                    fixture.channel.sentEnvelopes.count { it.type == MessageType.ChatSessionsList },
                )
            } finally {
                fixture.viewModel.disconnect()
                runCurrent()
            }
        }
    }

    @Test
    fun renameAckMustMatchJournaledSession() = runTest {
        withMainDispatcher {
            val fixture = createAuthenticatedRuntimeClientFixture(
                initialData = PersistedRuntimeData(
                    sessions = listOf(
                        PersistedChatSession(
                            id = "runtime-a",
                            title = "Runtime A",
                            createdAtMillis = 100L,
                            updatedAtMillis = 200L,
                            runtimeOwned = true,
                        ),
                        PersistedChatSession(
                            id = "runtime-b",
                            title = "Runtime B",
                            createdAtMillis = 110L,
                            updatedAtMillis = 210L,
                            runtimeOwned = true,
                        ),
                    ),
                ),
            )
            try {
                fixture.viewModel.renameChatSession("runtime-a", "Optimistic A")
                runCurrent()
                val renameRequest = fixture.channel.sentEnvelopes.last {
                    it.type == MessageType.ChatSessionRename
                }
                fixture.channel.enqueue(
                    envelope(
                        type = MessageType.ChatSessionRename,
                        serializer = ChatSessionRenamePayload.serializer(),
                        payload = ChatSessionRenamePayload(
                            sessionId = "runtime-b",
                            title = "Must not replace B",
                        ),
                        requestId = renameRequest.requestId,
                    ),
                )
                runCurrent()

                assertEquals("invalid_payload", fixture.viewModel.state.value.error?.code)
                assertEquals(
                    mapOf("runtime-a" to "Runtime A", "runtime-b" to "Runtime B"),
                    fixture.viewModel.state.value.chatSessions.associate { it.id to it.title },
                )
            } finally {
                fixture.viewModel.disconnect()
                runCurrent()
            }
        }
    }

    @Test
    fun malformedLifecycleAckRollsBackDeleteTombstoneAndRequestsFreshFullList() = runTest {
        withMainDispatcher {
            val fixture = createAuthenticatedRuntimeClientFixture(
                initialData = PersistedRuntimeData(
                    sessions = listOf(
                        PersistedChatSession(
                            id = "runtime-archived",
                            title = "Archived runtime",
                            createdAtMillis = 100L,
                            updatedAtMillis = 200L,
                            archivedAtMillis = 300L,
                            runtimeOwned = true,
                        ),
                    ),
                ),
            )
            try {
                val initialSessionListCount = fixture.channel.sentEnvelopes.count {
                    it.type == MessageType.ChatSessionsList
                }
                fixture.viewModel.deleteChatSession("runtime-archived")
                runCurrent()
                val deleteRequest = fixture.channel.sentEnvelopes.last {
                    it.type == MessageType.ChatSessionDelete
                }
                fixture.channel.enqueue(
                    ProtocolEnvelope(
                        type = MessageType.ChatSessionDelete,
                        requestId = deleteRequest.requestId,
                        payload = buildJsonObject {
                            put("session_id", "runtime-archived")
                            put("status", "deleted")
                            put("deleted_at", "not-a-date")
                        },
                    ),
                )
                runCurrent()

                assertEquals("invalid_payload", fixture.viewModel.state.value.error?.code)
                assertEquals(
                    listOf("runtime-archived"),
                    fixture.viewModel.state.value.archivedChatSessions.map { it.id },
                )
                assertTrue(fixture.localStore.data.suppressedRuntimeSessions.isEmpty())
                assertEquals(
                    initialSessionListCount + 1,
                    fixture.channel.sentEnvelopes.count { it.type == MessageType.ChatSessionsList },
                )
            } finally {
                fixture.viewModel.disconnect()
                runCurrent()
            }
        }
    }

    @Test
    fun malformedArchiveAndRestoreTimestampsCloseExactMutationsAndKeepReceiveLoopAlive() = runTest {
        withMainDispatcher {
            val fixture = createAuthenticatedRuntimeClientFixture(
                initialData = PersistedRuntimeData(
                    activeSessionId = "runtime-active",
                    sessions = listOf(
                        PersistedChatSession(
                            id = "runtime-active",
                            title = "Active runtime",
                            createdAtMillis = 100L,
                            updatedAtMillis = 200L,
                            runtimeOwned = true,
                        ),
                        PersistedChatSession(
                            id = "runtime-archived",
                            title = "Archived runtime",
                            createdAtMillis = 110L,
                            updatedAtMillis = 210L,
                            archivedAtMillis = 300L,
                            runtimeOwned = true,
                        ),
                    ),
                ),
            )
            try {
                val initialSessionListCount = fixture.channel.sentEnvelopes.count {
                    it.type == MessageType.ChatSessionsList
                }
                fixture.viewModel.archiveChatSession("runtime-active")
                fixture.viewModel.unarchiveChatSession("runtime-archived")
                runCurrent()
                val archiveRequest = fixture.channel.sentEnvelopes.last {
                    it.type == MessageType.ChatSessionArchive
                }
                val restoreRequest = fixture.channel.sentEnvelopes.last {
                    it.type == MessageType.ChatSessionRestore
                }

                fixture.channel.enqueue(
                    ProtocolEnvelope(
                        type = MessageType.ChatSessionArchive,
                        requestId = archiveRequest.requestId,
                        payload = buildJsonObject {
                            put("session_id", "runtime-active")
                            put("status", "archived")
                            put("archived_at", "not-an-archive-timestamp")
                        },
                    ),
                )
                runCurrent()

                assertEquals("invalid_payload", fixture.viewModel.state.value.error?.code)
                assertTrue(
                    fixture.viewModel.state.value.error?.technicalDetail.orEmpty()
                        .contains("archived_at"),
                )
                assertEquals(
                    setOf("runtime-active", "runtime-archived"),
                    fixture.viewModel.state.value.chatSessions.mapTo(mutableSetOf()) { it.id },
                )
                assertTrue(fixture.viewModel.state.value.archivedChatSessions.isEmpty())

                fixture.channel.enqueue(
                    ProtocolEnvelope(
                        type = MessageType.ChatSessionRestore,
                        requestId = restoreRequest.requestId,
                        payload = buildJsonObject {
                            put("session_id", "runtime-archived")
                            put("status", "restored")
                            put("restored_at", "not-a-restore-timestamp")
                        },
                    ),
                )
                runCurrent()

                assertEquals("invalid_payload", fixture.viewModel.state.value.error?.code)
                assertTrue(
                    fixture.viewModel.state.value.error?.technicalDetail.orEmpty()
                        .contains("restored_at"),
                )
                assertEquals(
                    listOf("runtime-active"),
                    fixture.viewModel.state.value.chatSessions.map { it.id },
                )
                assertEquals(
                    listOf("runtime-archived"),
                    fixture.viewModel.state.value.archivedChatSessions.map { it.id },
                )
                assertEquals(
                    initialSessionListCount + 2,
                    fixture.channel.sentEnvelopes.count { it.type == MessageType.ChatSessionsList },
                )

                fixture.channel.enqueue(
                    envelope(
                        type = MessageType.ChatSessionArchive,
                        serializer = ChatSessionLifecyclePayload.serializer(),
                        payload = ChatSessionLifecyclePayload(
                            sessionId = "runtime-active",
                            status = "archived",
                            archivedAt = "2026-06-23T09:03:00Z",
                        ),
                        requestId = archiveRequest.requestId,
                    ),
                )
                fixture.channel.enqueue(
                    envelope(
                        type = MessageType.ChatSessionRestore,
                        serializer = ChatSessionLifecyclePayload.serializer(),
                        payload = ChatSessionLifecyclePayload(
                            sessionId = "runtime-archived",
                            status = "restored",
                            restoredAt = "2026-06-23T09:04:00Z",
                        ),
                        requestId = restoreRequest.requestId,
                    ),
                )
                runCurrent()

                assertEquals(listOf("runtime-active"), fixture.viewModel.state.value.chatSessions.map { it.id })
                assertEquals(
                    listOf("runtime-archived"),
                    fixture.viewModel.state.value.archivedChatSessions.map { it.id },
                )
            } finally {
                fixture.viewModel.disconnect()
                runCurrent()
            }
        }
    }

    @Test
    fun lifecycleWaitsForPendingListThenRequestsFreshReconciliation() = runTest {
        withMainDispatcher {
            val fixture = createAuthenticatedRuntimeClientFixture(
                initialData = PersistedRuntimeData(
                    sessions = listOf(
                        PersistedChatSession(
                            id = "runtime-session",
                            title = "Runtime title",
                            createdAtMillis = 100L,
                            updatedAtMillis = 200L,
                            runtimeOwned = true,
                        ),
                    ),
                ),
            )
            try {
                fixture.viewModel.refreshRuntimeChatHistory()
                runCurrent()
                val pendingListRequest = fixture.channel.sentEnvelopes.last {
                    it.type == MessageType.ChatSessionsList
                }
                fixture.viewModel.archiveChatSession("runtime-session")
                runCurrent()
                assertTrue(
                    fixture.channel.sentEnvelopes.none { it.type == MessageType.ChatSessionArchive },
                )
                assertEquals("chat_history_loading", fixture.viewModel.state.value.error?.code)
                fixture.channel.enqueue(
                    envelope(
                        type = MessageType.ChatSessionsList,
                        serializer = ChatSessionsListResultPayload.serializer(),
                        payload = ChatSessionsListResultPayload(
                            sessions = listOf(
                                ChatSessionSummaryPayload(
                                    sessionId = "runtime-session",
                                    title = "Runtime title",
                                    model = "ollama:llama3.1:8b",
                                    lastActivityAt = "2026-06-23T09:01:00Z",
                                    messageCount = 1,
                                    status = "active",
                                ),
                            ),
                        ),
                        requestId = pendingListRequest.requestId,
                    ),
                )
                runCurrent()

                fixture.viewModel.archiveChatSession("runtime-session")
                runCurrent()
                val archiveRequest = fixture.channel.sentEnvelopes.last {
                    it.type == MessageType.ChatSessionArchive
                }
                fixture.channel.enqueue(
                    envelope(
                        type = MessageType.ChatSessionArchive,
                        serializer = ChatSessionLifecyclePayload.serializer(),
                        payload = ChatSessionLifecyclePayload(
                            sessionId = "runtime-session",
                            status = "archived",
                            archivedAt = "2026-06-23T09:03:00Z",
                        ),
                        requestId = archiveRequest.requestId,
                    ),
                )
                runCurrent()
                val freshListRequest = fixture.channel.sentEnvelopes.last {
                    it.type == MessageType.ChatSessionsList
                }
                assertTrue(freshListRequest.requestId != pendingListRequest.requestId)

                assertEquals(
                    listOf("runtime-session"),
                    fixture.viewModel.state.value.archivedChatSessions.map { it.id },
                )
                assertTrue(fixture.viewModel.state.value.chatSessions.none { it.id == "runtime-session" })
            } finally {
                fixture.viewModel.disconnect()
                runCurrent()
            }
        }
    }

    @Test
    fun sameSessionMutationWaitsForPendingAcknowledgement() = runTest {
        withMainDispatcher {
            val fixture = createAuthenticatedRuntimeClientFixture(
                initialData = PersistedRuntimeData(
                    sessions = listOf(
                        PersistedChatSession(
                            id = "runtime-session",
                            title = "Runtime title",
                            createdAtMillis = 100L,
                            updatedAtMillis = 200L,
                            runtimeOwned = true,
                        ),
                    ),
                ),
            )
            try {
                fixture.viewModel.renameChatSession("runtime-session", "First pending title")
                fixture.viewModel.renameChatSession("runtime-session", "Second blocked title")
                runCurrent()

                assertEquals(
                    1,
                    fixture.channel.sentEnvelopes.count { it.type == MessageType.ChatSessionRename },
                )
                assertEquals(
                    "First pending title",
                    fixture.viewModel.state.value.chatSessions.single().title,
                )
                assertEquals("chat_history_loading", fixture.viewModel.state.value.error?.code)
            } finally {
                fixture.viewModel.disconnect()
                runCurrent()
            }
        }
    }

    @Test
    fun completedRenameIgnoresDelayedAuthenticationError() = runTest {
        withMainDispatcher {
            val fixture = createAuthenticatedRuntimeClientFixture(
                initialData = PersistedRuntimeData(
                    sessions = listOf(
                        PersistedChatSession(
                            id = "runtime-session",
                            title = "Runtime title",
                            createdAtMillis = 100L,
                            updatedAtMillis = 200L,
                            runtimeOwned = true,
                        ),
                    ),
                ),
            )
            try {
                fixture.viewModel.renameChatSession("runtime-session", "Accepted title")
                runCurrent()
                val renameRequest = fixture.channel.sentEnvelopes.last {
                    it.type == MessageType.ChatSessionRename
                }
                fixture.channel.enqueue(
                    envelope(
                        type = MessageType.ChatSessionRename,
                        serializer = ChatSessionRenamePayload.serializer(),
                        payload = ChatSessionRenamePayload(
                            sessionId = "runtime-session",
                            title = "Accepted title",
                        ),
                        requestId = renameRequest.requestId,
                    ),
                )
                runCurrent()
                fixture.viewModel.setPrivateField("runtimeSessionAuthorityGeneration", 1L)

                fixture.channel.enqueue(
                    envelope(
                        type = MessageType.Error,
                        serializer = ErrorPayload.serializer(),
                        payload = ErrorPayload(
                            code = "authentication_required",
                            message = "Delayed completed rename error",
                            retryable = false,
                        ),
                        requestId = renameRequest.requestId,
                    ),
                )
                runCurrent()

                assertEquals("Accepted title", fixture.viewModel.state.value.chatSessions.single().title)
                assertEquals("authenticated", fixture.viewModel.state.value.runtimeStatus)
                assertEquals(null, fixture.viewModel.state.value.error)
            } finally {
                fixture.viewModel.disconnect()
                runCurrent()
            }
        }
    }

    @Test
    fun evictedLifecycleErrorCannotRevokeAuthenticationButActiveChatErrorStillDoes() = runTest {
        withMainDispatcher {
            val sessions = (0..128).map { index ->
                PersistedChatSession(
                    id = "runtime-$index",
                    title = "Runtime $index",
                    createdAtMillis = index.toLong(),
                    updatedAtMillis = 1_000L + index,
                    runtimeOwned = true,
                )
            }
            val fixture = createAuthenticatedRuntimeClientFixture(
                initialData = PersistedRuntimeData(sessions = sessions),
            )
            try {
                sessions.forEach { session ->
                    fixture.viewModel.archiveChatSession(session.id)
                }
                runCurrent()
                val archiveRequests = fixture.channel.sentEnvelopes.filter {
                    it.type == MessageType.ChatSessionArchive
                }
                assertEquals(129, archiveRequests.size)

                archiveRequests.forEachIndexed { index, request ->
                    fixture.channel.enqueue(
                        envelope(
                            type = MessageType.ChatSessionArchive,
                            serializer = ChatSessionLifecyclePayload.serializer(),
                            payload = ChatSessionLifecyclePayload(
                                sessionId = "runtime-$index",
                                status = "archived",
                            ),
                            requestId = request.requestId,
                        ),
                    )
                }
                runCurrent()

                assertEquals(
                    128,
                    fixture.viewModel.privateField<List<*>>(
                        "closedChatSessionLifecycleRequests",
                    ).size,
                )
                fixture.channel.enqueue(
                    envelope(
                        type = MessageType.Error,
                        serializer = ErrorPayload.serializer(),
                        payload = ErrorPayload(
                            code = "pairing_required",
                            message = "Delayed error after lifecycle tombstone eviction",
                            retryable = false,
                        ),
                        requestId = archiveRequests.first().requestId,
                    ),
                )
                runCurrent()

                assertTrue(fixture.viewModel.privateField("isSessionAuthenticated"))
                assertEquals("authenticated", fixture.viewModel.state.value.runtimeStatus)
                assertTrue(fixture.viewModel.state.value.isConnected)

                fixture.viewModel.updateMutableState { current ->
                    current.copy(
                        isStreaming = true,
                        activeRequestId = "current-active-chat-request",
                        error = null,
                    )
                }
                fixture.channel.enqueue(
                    envelope(
                        type = MessageType.Error,
                        serializer = ErrorPayload.serializer(),
                        payload = ErrorPayload(
                            code = "authentication_required",
                            message = "Current active chat authentication expired",
                            retryable = false,
                        ),
                        requestId = "current-active-chat-request",
                    ),
                )
                runCurrent()

                assertTrue(!fixture.viewModel.privateField<Boolean>("isSessionAuthenticated"))
                assertEquals("pairing_required", fixture.viewModel.state.value.runtimeStatus)
                assertEquals(null, fixture.viewModel.state.value.activeRequestId)
            } finally {
                fixture.viewModel.disconnect()
                runCurrent()
            }
        }
    }

    @Test
    fun renameTimeoutRollsBackAndRejectsLateAckAndError() = runTest {
        withMainDispatcher {
            val fixture = createAuthenticatedRuntimeClientFixture(
                initialData = PersistedRuntimeData(
                    sessions = listOf(
                        PersistedChatSession(
                            id = "runtime-session",
                            title = "Runtime title",
                            createdAtMillis = 100L,
                            updatedAtMillis = 200L,
                            runtimeOwned = true,
                        ),
                    ),
                ),
            )
            try {
                val chatRefreshCount = fixture.channel.sentEnvelopes.count {
                    it.type == MessageType.ChatSessionsList
                }
                val notebookRefreshCount = fixture.channel.sentEnvelopes.count {
                    it.type == MessageType.ResearchNotebooksList
                }
                fixture.viewModel.renameChatSession("runtime-session", "Timed out title")
                runCurrent()
                val renameRequest = fixture.channel.sentEnvelopes.last {
                    it.type == MessageType.ChatSessionRename
                }

                advanceTimeBy(CHAT_SESSION_RENAME_REQUEST_TIMEOUT_MS)
                runCurrent()

                assertEquals("Runtime title", fixture.viewModel.state.value.chatSessions.single().title)
                assertEquals("chat_session_sync_failed", fixture.viewModel.state.value.error?.code)
                assertTrue(
                    fixture.channel.sentEnvelopes.count { it.type == MessageType.ChatSessionsList } >
                        chatRefreshCount,
                )
                assertTrue(
                    fixture.channel.sentEnvelopes.count { it.type == MessageType.ResearchNotebooksList } >
                        notebookRefreshCount,
                )

                fixture.channel.enqueue(
                    envelope(
                        type = MessageType.ChatSessionRename,
                        serializer = ChatSessionRenamePayload.serializer(),
                        payload = ChatSessionRenamePayload(
                            sessionId = "runtime-session",
                            title = "Late accepted title",
                        ),
                        requestId = renameRequest.requestId,
                    ),
                )
                fixture.channel.enqueue(
                    envelope(
                        type = MessageType.Error,
                        serializer = ErrorPayload.serializer(),
                        payload = ErrorPayload(
                            code = "authentication_required",
                            message = "Late timeout error",
                            retryable = false,
                        ),
                        requestId = renameRequest.requestId,
                    ),
                )
                runCurrent()

                assertEquals("Runtime title", fixture.viewModel.state.value.chatSessions.single().title)
                assertEquals("authenticated", fixture.viewModel.state.value.runtimeStatus)
                assertEquals("chat_session_sync_failed", fixture.viewModel.state.value.error?.code)
            } finally {
                fixture.viewModel.disconnect()
                runCurrent()
            }
        }
    }

    private suspend fun TestScope.withMainDispatcher(block: suspend TestScope.() -> Unit) {
        val mainDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(mainDispatcher)
        block()
    }

    private suspend fun TestScope.createAuthenticatedRuntimeClientFixture(
        initialData: PersistedRuntimeData,
    ): RuntimeClientFixture {
        val channel = ScriptedRuntimeProtocolChannel()
        val localStore = FakeRuntimeLocalDataStore(initialData = initialData)
        val viewModel = RuntimeClientViewModel(
            application = Application(),
            dependencies = RuntimeClientViewModelDependencies(
                json = json,
                transportClient = RuntimeTransportClient(),
                transportConnector = RuntimeTransportConnector { _, _, _ -> channel },
                relayConnector = RuntimeRelayConnector { _, _ ->
                    error("Relay transport should not be used by runtime mutation failure tests")
                },
                discovery = EmptyRuntimeDiscoverySource,
                trustedRuntimeStore = FakeEmittingTrustedRuntimeStore(trustedRuntimeForViewModelTests()),
                deviceIdentityProvider = FakeDeviceIdentityProvider(testDeviceIdentity()),
                localDataStore = localStore,
                lifecycleCallbacksRegistrar = NoopRuntimeLifecycleCallbacksRegistrar,
                currentTimeMillis = { 1_000L },
            ),
        )
        runCurrent()

        viewModel.setPrivateField("activeChannel", channel)
        viewModel.setPrivateField("isSessionAuthenticated", true)
        viewModel.updateMutableState {
            it.copy(
                isConnected = true,
                runtimeStatus = "authenticated",
            )
        }
        viewModel.callPrivateNoArgs("startReadLoop")
        runCurrent()

        return RuntimeClientFixture(
            viewModel = viewModel,
            channel = channel,
            localStore = localStore,
        )
    }

    private fun RuntimeClientViewModel.setPrivateField(name: String, value: Any?) {
        val field = RuntimeClientViewModel::class.java.getDeclaredField(name)
        field.isAccessible = true
        field.set(this, value)
    }

    @Suppress("UNCHECKED_CAST")
    private fun <T> RuntimeClientViewModel.privateField(name: String): T {
        val field = RuntimeClientViewModel::class.java.getDeclaredField(name)
        field.isAccessible = true
        return field.get(this) as T
    }

    private fun RuntimeClientViewModel.callPrivateNoArgs(name: String) {
        val method = RuntimeClientViewModel::class.java.getDeclaredMethod(name)
        method.isAccessible = true
        method.invoke(this)
    }

    @Suppress("UNCHECKED_CAST")
    private fun RuntimeClientViewModel.updateMutableState(transform: (RuntimeUiState) -> RuntimeUiState) {
        val field = RuntimeClientViewModel::class.java.getDeclaredField("mutableState")
        field.isAccessible = true
        val mutableState = field.get(this) as MutableStateFlow<RuntimeUiState>
        mutableState.value = transform(mutableState.value)
    }

    private fun TestScope.completeRuntimeSessionList(
        fixture: RuntimeClientFixture,
        title: String,
        messageCount: Int,
        sessionId: String = "runtime-session",
        status: String = "active",
        archivedAt: String? = null,
    ) {
        val messageRequestCountBefore = fixture.channel.sentEnvelopes.count { it.type == MessageType.ChatMessagesList }
        val sessionsRequest = fixture.channel.sentEnvelopes.last { it.type == MessageType.ChatSessionsList }
        fixture.channel.enqueue(
            envelope(
                type = MessageType.ChatSessionsList,
                serializer = ChatSessionsListResultPayload.serializer(),
                payload = ChatSessionsListResultPayload(
                    sessions = listOf(
                        ChatSessionSummaryPayload(
                            sessionId = sessionId,
                            title = title,
                            model = "ollama:llama3.1:8b",
                            lastActivityAt = "2026-06-23T09:02:05Z",
                            messageCount = messageCount,
                            status = status,
                            archivedAt = archivedAt,
                        ),
                    ),
                ),
                requestId = sessionsRequest.requestId,
            ),
        )
        runCurrent()

        val messageRequests = fixture.channel.sentEnvelopes.filter { it.type == MessageType.ChatMessagesList }
        if (messageRequests.size > messageRequestCountBefore) {
            val messagesRequest = messageRequests.last()
            val payload = json.decodeFromJsonElement(
                ChatMessagesListRequestPayload.serializer(),
                messagesRequest.payload,
            )
            fixture.channel.enqueue(
                envelope(
                    type = MessageType.ChatMessagesList,
                    serializer = ChatMessagesListResultPayload.serializer(),
                    payload = ChatMessagesListResultPayload(
                        sessionId = payload.sessionId,
                        messages = emptyList(),
                    ),
                    requestId = messagesRequest.requestId,
                ),
            )
            runCurrent()
        }
    }

    private fun <T> envelope(
        type: String,
        serializer: KSerializer<T>,
        payload: T,
        requestId: String? = null,
    ): ProtocolEnvelope {
        val encodedPayload = json.encodeToJsonElement(serializer, payload).jsonObject
        return if (requestId == null) {
            ProtocolEnvelope(
                type = type,
                payload = encodedPayload,
            )
        } else {
            ProtocolEnvelope(
                type = type,
                requestId = requestId,
                payload = encodedPayload,
            )
        }
    }

    private class ScriptedRuntimeProtocolChannel : RuntimeProtocolChannel {
        val sentEnvelopes = mutableListOf<ProtocolEnvelope>()
        private val incoming = Channel<ProtocolEnvelope>(Channel.UNLIMITED)
        private var closed = false

        override val isConnected: Boolean
            get() = !closed

        override suspend fun send(envelope: ProtocolEnvelope) {
            sentEnvelopes += envelope
        }

        override suspend fun receive(): ProtocolEnvelope = incoming.receive()

        fun enqueue(envelope: ProtocolEnvelope) {
            incoming.trySend(envelope).getOrThrow()
        }

        override fun close() {
            closed = true
            incoming.close()
        }
    }

    private class FakeRuntimeLocalDataStore(
        initialData: PersistedRuntimeData,
    ) : RuntimeLocalDataStore {
        var data: PersistedRuntimeData = initialData
            private set

        override fun load(): PersistedRuntimeData = data

        override fun save(
            data: PersistedRuntimeData,
            durability: RuntimeLocalDataWriteDurability,
        ) {
            this.data = data
        }
    }

    private class FakeEmittingTrustedRuntimeStore(
        initialTrustedRuntime: TrustedRuntime,
    ) : RuntimeTrustedRuntimeStore {
        private val trustedRuntimeFlow = MutableStateFlow<TrustedRuntime?>(initialTrustedRuntime)
        override val trustedRuntime: Flow<TrustedRuntime?> = trustedRuntimeFlow
        var trusted: TrustedRuntime? = initialTrustedRuntime
            private set

        override suspend fun trustRuntime(runtime: TrustedRuntime) {
            trusted = runtime
            trustedRuntimeFlow.value = runtime
        }

        override suspend fun forgetRuntime() {
            trusted = null
            trustedRuntimeFlow.value = null
        }
    }

    private class FakeDeviceIdentityProvider(
        private val identity: DeviceIdentity,
    ) : RuntimeDeviceIdentityProvider {
        override suspend fun loadOrCreate(): DeviceIdentity = identity
    }

    private object EmptyRuntimeDiscoverySource : RuntimeDiscoverySource {
        override fun discover(): Flow<List<DiscoveredRuntime>> = emptyFlow()
    }

    private object NoopRuntimeLifecycleCallbacksRegistrar : RuntimeLifecycleCallbacksRegistrar {
        override fun register(application: Application, callbacks: Application.ActivityLifecycleCallbacks) = Unit

        override fun unregister(application: Application, callbacks: Application.ActivityLifecycleCallbacks) = Unit
    }

    private data class RuntimeClientFixture(
        val viewModel: RuntimeClientViewModel,
        val channel: ScriptedRuntimeProtocolChannel,
        val localStore: FakeRuntimeLocalDataStore,
    )

    private fun trustedRuntimeForViewModelTests(): TrustedRuntime {
        return TrustedRuntime(
            deviceId = "runtime-1",
            name = "AetherLink Runtime",
            fingerprint = "runtime-fingerprint",
            publicKeyBase64 = "runtime-public-key",
            host = "127.0.0.1",
            port = 43170,
        )
    }

    private fun testDeviceIdentity(): DeviceIdentity {
        val keyPair = KeyPairGenerator.getInstance("EC")
            .apply { initialize(ECGenParameterSpec("secp256r1")) }
            .generateKeyPair()
        return DeviceIdentity(
            deviceId = "client-1",
            deviceName = "AetherLink Test Client",
            publicKeyBase64 = "client-public-key",
            keyPair = keyPair,
        )
    }
}
