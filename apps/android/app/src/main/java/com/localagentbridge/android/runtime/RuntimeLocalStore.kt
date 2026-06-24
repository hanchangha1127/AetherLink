package com.localagentbridge.android.runtime

import android.content.Context
import com.localagentbridge.android.core.protocol.ChatAttachmentPayload
import com.localagentbridge.android.core.protocol.ChatMessagePayload
import com.localagentbridge.android.core.protocol.ChatSessionSummaryPayload
import com.localagentbridge.android.core.protocol.ChatStoredMessagePayload
import kotlinx.serialization.Serializable
import kotlinx.serialization.SerializationException
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.time.Instant
import java.util.UUID

private const val STORE_NAME = "runtime_local_store"
private const val STORE_KEY = "runtime_data"
private const val SUPPRESSED_REASON_DELETED = "deleted"

class RuntimeLocalStore(
    context: Context,
    private val json: Json,
) {
    private val preferences = context.getSharedPreferences(STORE_NAME, Context.MODE_PRIVATE)

    fun load(): PersistedRuntimeData {
        val raw = preferences.getString(STORE_KEY, null) ?: return PersistedRuntimeData()
        return try {
            json.decodeFromString<PersistedRuntimeData>(raw).sanitized()
        } catch (_: SerializationException) {
            PersistedRuntimeData()
        } catch (_: IllegalArgumentException) {
            PersistedRuntimeData()
        }
    }

    fun save(data: PersistedRuntimeData) {
        preferences.edit()
            .putString(STORE_KEY, json.encodeToString(data.sanitized()))
            .apply()
    }
}

@Serializable
data class PersistedRuntimeData(
    val version: Int = 1,
    val activeSessionId: String? = null,
    val selectedModelId: String? = null,
    val selectedEmbeddingModelId: String? = null,
    val trustedRuntimeAutoReconnectEnabled: Boolean = true,
    val pairingOnboardingCompleted: Boolean = false,
    val sessions: List<PersistedChatSession> = emptyList(),
    val suppressedRuntimeSessions: List<PersistedSuppressedRuntimeSession> = emptyList(),
    val memoryEntries: List<PersistedMemoryEntry> = emptyList(),
    val appLanguageTag: String = RuntimeAppLanguage.English.languageTag,
)

@Serializable
data class PersistedChatSession(
    val id: String,
    val title: String,
    val createdAtMillis: Long,
    val updatedAtMillis: Long,
    val archivedAtMillis: Long? = null,
    val titleManuallyEdited: Boolean = false,
    val titleGenerated: Boolean = false,
    val runtimeOwned: Boolean = false,
    val messages: List<PersistedChatMessage> = emptyList(),
)

@Serializable
data class PersistedChatMessage(
    val id: String,
    val role: String,
    val content: String,
    val reasoning: String = "",
    val suggestions: List<String> = emptyList(),
    val createdAtMillis: Long,
)

@Serializable
data class PersistedSuppressedRuntimeSession(
    val sessionId: String,
    val reason: String,
    val updatedAtMillis: Long,
)

@Serializable
data class PersistedMemoryEntry(
    val id: String,
    val content: String,
    val enabled: Boolean = true,
    val createdAtMillis: Long,
    val updatedAtMillis: Long,
)

internal fun PersistedRuntimeData.sanitized(): PersistedRuntimeData {
    val cleanSessions = sessions
        .filter { it.id.isNotBlank() }
        .distinctBy { it.id }
        .map { session ->
            val fallbackTitle = titleForMessages(session.messages.map { it.toRuntimeChatMessage() })
            val cleanTitle = session.title.trim().takeIf(String::isNotBlank) ?: DEFAULT_CHAT_TITLE
            session.copy(
                title = cleanTitle,
                titleManuallyEdited = session.titleManuallyEdited ||
                    (
                        !session.runtimeOwned &&
                            !session.titleGenerated &&
                            cleanTitle != DEFAULT_CHAT_TITLE &&
                            cleanTitle != fallbackTitle
                    ),
                messages = session.messages.filter { it.role in CHAT_STORAGE_ROLES },
            )
        }
    val cleanMemory = memoryEntries
        .filter { it.id.isNotBlank() && it.content.isNotBlank() }
        .distinctBy { it.id }
    val cleanSuppressedRuntimeSessions = suppressedRuntimeSessions
        .mapNotNull { suppression ->
            val sessionId = suppression.sessionId.trim()
            val reason = suppression.reason.trim().takeIf(String::isNotBlank) ?: SUPPRESSED_REASON_DELETED
            if (sessionId.isBlank()) {
                null
            } else {
                suppression.copy(sessionId = sessionId, reason = reason)
            }
        }
        .distinctBy { it.sessionId }
    return copy(
        activeSessionId = activeSessionId?.takeIf { id ->
            cleanSessions.any { it.id == id && it.archivedAtMillis == null }
        },
        selectedModelId = selectedModelId?.trim()?.takeIf(String::isNotBlank),
        selectedEmbeddingModelId = selectedEmbeddingModelId?.trim()?.takeIf(String::isNotBlank),
        trustedRuntimeAutoReconnectEnabled = trustedRuntimeAutoReconnectEnabled,
        pairingOnboardingCompleted = pairingOnboardingCompleted,
        sessions = cleanSessions.sortedByDescending { it.updatedAtMillis },
        suppressedRuntimeSessions = cleanSuppressedRuntimeSessions.sortedByDescending { it.updatedAtMillis },
        memoryEntries = cleanMemory.sortedByDescending { it.updatedAtMillis },
        appLanguageTag = RuntimeAppLanguage.normalizeLanguageTag(appLanguageTag),
    )
}

internal fun PersistedRuntimeData.withSelectedModelId(modelId: String?): PersistedRuntimeData {
    return copy(selectedModelId = modelId?.trim()?.takeIf(String::isNotBlank)).sanitized()
}

internal fun PersistedRuntimeData.withSelectedEmbeddingModelId(modelId: String?): PersistedRuntimeData {
    return copy(selectedEmbeddingModelId = modelId?.trim()?.takeIf(String::isNotBlank)).sanitized()
}

internal fun PersistedRuntimeData.withTrustedRuntimeAutoReconnectEnabled(enabled: Boolean): PersistedRuntimeData {
    return copy(trustedRuntimeAutoReconnectEnabled = enabled).sanitized()
}

internal fun PersistedRuntimeData.withPairingOnboardingCompleted(): PersistedRuntimeData {
    return copy(pairingOnboardingCompleted = true).sanitized()
}

internal fun PersistedRuntimeData.withAppLanguageTag(languageTag: String): PersistedRuntimeData {
    return copy(appLanguageTag = RuntimeAppLanguage.normalizeLanguageTag(languageTag)).sanitized()
}

internal fun PersistedRuntimeData.withActiveSession(sessionId: String): PersistedRuntimeData {
    val session = sessions.firstOrNull { it.id == sessionId && it.archivedAtMillis == null } ?: return this
    return copy(activeSessionId = session.id).sanitized()
}

internal fun PersistedRuntimeData.withNoActiveSession(): PersistedRuntimeData {
    return copy(activeSessionId = null).sanitized()
}

internal fun PersistedRuntimeData.withRenamedChatSession(
    sessionId: String,
    title: String,
    nowMillis: Long,
): PersistedRuntimeData {
    val cleanTitle = title.trim()
    if (cleanTitle.isBlank()) return this
    return copy(
        sessions = sessions.map { session ->
            if (session.id == sessionId) {
                session.copy(
                    title = cleanTitle,
                    titleManuallyEdited = true,
                    titleGenerated = false,
                    updatedAtMillis = nowMillis,
                )
            } else {
                session
            }
        }
    ).sanitized()
}

internal fun PersistedRuntimeData.withArchivedChatSession(
    sessionId: String,
    nowMillis: Long,
): PersistedRuntimeData {
    return copy(
        activeSessionId = activeSessionId?.takeIf { it != sessionId },
        sessions = sessions.map { session ->
            if (session.id == sessionId) {
                session.copy(archivedAtMillis = nowMillis, updatedAtMillis = nowMillis)
            } else {
                session
            }
        },
    ).sanitized()
}

internal fun PersistedRuntimeData.withArchivedChatSessions(nowMillis: Long): PersistedRuntimeData {
    return copy(
        activeSessionId = null,
        sessions = sessions.map { session ->
            if (session.archivedAtMillis == null) {
                session.copy(archivedAtMillis = nowMillis, updatedAtMillis = nowMillis)
            } else {
                session
            }
        },
    ).sanitized()
}

internal fun PersistedRuntimeData.withUnarchivedChatSession(
    sessionId: String,
    nowMillis: Long,
): PersistedRuntimeData {
    return copy(
        suppressedRuntimeSessions = suppressedRuntimeSessions.filterNot { it.sessionId == sessionId },
        sessions = sessions.map { session ->
            if (session.id == sessionId) {
                session.copy(archivedAtMillis = null, updatedAtMillis = nowMillis)
            } else {
                session
            }
        },
    ).sanitized()
}

internal fun PersistedRuntimeData.withoutChatSession(
    sessionId: String,
    nowMillis: Long? = null,
): PersistedRuntimeData {
    val deletedSession = sessions.firstOrNull { it.id == sessionId }
    return copy(
        activeSessionId = activeSessionId?.takeIf { it != sessionId },
        sessions = sessions.filterNot { it.id == sessionId },
        suppressedRuntimeSessions = suppressedRuntimeSessions.withRuntimeDeletion(
            session = deletedSession,
            nowMillis = nowMillis ?: deletedSession?.updatedAtMillis ?: 0L,
        ),
    ).sanitized()
}

internal fun PersistedRuntimeData.withGeneratedChatSessionTitle(
    sessionId: String,
    title: String,
    nowMillis: Long,
): PersistedRuntimeData {
    val cleanTitle = title.cleanedChatTitle()
    if (cleanTitle.isBlank()) return this
    return copy(
        sessions = sessions.map { session ->
            if (session.id == sessionId && !session.titleManuallyEdited) {
                session.copy(
                    title = cleanTitle,
                    titleGenerated = true,
                    updatedAtMillis = nowMillis,
                )
            } else {
                session
            }
        }
    ).sanitized()
}

internal fun PersistedRuntimeData.withoutChatSessions(
    nowMillis: Long? = null,
): PersistedRuntimeData {
    return copy(
        activeSessionId = null,
        sessions = emptyList(),
        suppressedRuntimeSessions = suppressedRuntimeSessions.withRuntimeDeletions(
            sessions = sessions,
            nowMillis = nowMillis ?: sessions.maxOfOrNull { it.updatedAtMillis } ?: 0L,
        ),
    ).sanitized()
}

internal fun PersistedRuntimeData.withoutArchivedChatSessions(
    nowMillis: Long? = null,
): PersistedRuntimeData {
    val archivedSessions = sessions.filter { it.archivedAtMillis != null }
    return copy(
        sessions = sessions.filter { it.archivedAtMillis == null },
        suppressedRuntimeSessions = suppressedRuntimeSessions.withRuntimeDeletions(
            sessions = archivedSessions,
            nowMillis = nowMillis ?: archivedSessions.maxOfOrNull { it.updatedAtMillis } ?: 0L,
        ),
    ).sanitized()
}

internal fun PersistedRuntimeData.withNewChatSession(
    nowMillis: Long,
    sessionId: String = UUID.randomUUID().toString(),
): PersistedRuntimeData {
    val session = PersistedChatSession(
        id = sessionId,
        title = DEFAULT_CHAT_TITLE,
        createdAtMillis = nowMillis,
        updatedAtMillis = nowMillis,
    )
    return copy(
        activeSessionId = sessionId,
        sessions = listOf(session) + sessions,
    ).sanitized()
}

internal fun PersistedRuntimeData.withPersistedMessages(
    sessionId: String,
    messages: List<RuntimeChatMessage>,
    nowMillis: Long,
    runtimeBacked: Boolean = false,
): PersistedRuntimeData {
    val existing = sessions.firstOrNull { it.id == sessionId }
    val createdAt = existing?.createdAtMillis ?: nowMillis
    val existingMessageTimes = existing?.messages.orEmpty().associate { it.id to it.createdAtMillis }
    val title = existing?.title?.trim()?.takeIf(String::isNotBlank) ?: DEFAULT_CHAT_TITLE
    val persistedMessages = messages
        .filter { it.role in CHAT_STORAGE_ROLES }
        .map { it.toPersistedChatMessage(existingMessageTimes[it.id] ?: nowMillis) }
    val updatedSession = PersistedChatSession(
        id = sessionId,
        title = title,
        createdAtMillis = createdAt,
        updatedAtMillis = nowMillis,
        archivedAtMillis = existing?.archivedAtMillis,
        titleManuallyEdited = existing?.titleManuallyEdited ?: false,
        titleGenerated = existing?.titleGenerated ?: false,
        runtimeOwned = existing?.runtimeOwned == true || runtimeBacked,
        messages = persistedMessages,
    )
    return copy(
        activeSessionId = sessionId,
        sessions = listOf(updatedSession) + sessions.filterNot { it.id == sessionId },
    ).sanitized()
}

internal fun PersistedRuntimeData.withRuntimeChatSessionSummaries(
    sessions: List<ChatSessionSummaryPayload>,
    nowMillis: Long,
): PersistedRuntimeData {
    val runtimeSummaries = sessions
        .filter { it.sessionId.isNotBlank() }
        .filterNot { it.sessionId in deletedRuntimeSessionIds() }
        .distinctBy { it.sessionId }
    val localOnlySessions = this.sessions.filterNot { it.runtimeOwned }
    val mergedRuntimeSessions = runtimeSummaries.map { summary ->
        val existing = this.sessions.firstOrNull { it.id == summary.sessionId }
        val updatedAt = parseTimestampMillis(summary.lastActivityAt) ?: existing?.updatedAtMillis ?: nowMillis
        val title = summary.title.trim().takeIf(String::isNotBlank) ?: existing?.title ?: DEFAULT_CHAT_TITLE
        existing?.copy(
            title = if (existing.titleManuallyEdited) existing.title else title,
            updatedAtMillis = updatedAt,
            titleGenerated = existing.titleGenerated || !existing.titleManuallyEdited,
            runtimeOwned = true,
        ) ?: PersistedChatSession(
            id = summary.sessionId,
            title = title,
            createdAtMillis = updatedAt,
            updatedAtMillis = updatedAt,
            titleGenerated = true,
            runtimeOwned = true,
        )
    }
    return copy(
        sessions = mergedRuntimeSessions + localOnlySessions,
    ).sanitized()
}

internal fun PersistedRuntimeData.withRuntimeChatMessages(
    sessionId: String,
    messages: List<ChatStoredMessagePayload>,
    nowMillis: Long,
): PersistedRuntimeData {
    val cleanSessionId = sessionId.trim()
    if (cleanSessionId.isBlank()) return this
    if (cleanSessionId in deletedRuntimeSessionIds()) return this
    val existing = sessions.firstOrNull { it.id == cleanSessionId }
    val persistedMessages = messages
        .filter { it.role in CHAT_STORAGE_ROLES }
        .mapIndexed { index, message ->
            val createdAt = message.createdAt?.let(::parseTimestampMillis) ?: nowMillis
            PersistedChatMessage(
                id = stableRuntimeMessageId(cleanSessionId, index, message),
                role = message.role,
                content = message.content,
                reasoning = message.reasoning.orEmpty(),
                createdAtMillis = createdAt,
            )
        }
    val updatedAt = persistedMessages.maxOfOrNull { it.createdAtMillis }
        ?: existing?.updatedAtMillis
        ?: nowMillis
    val title = existing?.title?.takeIf(String::isNotBlank) ?: DEFAULT_CHAT_TITLE
    val updatedSession = PersistedChatSession(
        id = cleanSessionId,
        title = title,
        createdAtMillis = existing?.createdAtMillis ?: updatedAt,
        updatedAtMillis = updatedAt,
        archivedAtMillis = existing?.archivedAtMillis,
        titleManuallyEdited = existing?.titleManuallyEdited ?: false,
        titleGenerated = existing?.titleGenerated ?: false,
        runtimeOwned = true,
        messages = persistedMessages,
    )
    return copy(
        sessions = listOf(updatedSession) + sessions.filterNot { it.id == cleanSessionId },
    ).sanitized()
}

private fun List<PersistedSuppressedRuntimeSession>.withRuntimeDeletion(
    session: PersistedChatSession?,
    nowMillis: Long,
): List<PersistedSuppressedRuntimeSession> {
    if (session?.runtimeOwned != true) return this
    val timestamp = maxOf(nowMillis, session.updatedAtMillis)
    return filterNot { it.sessionId == session.id } + PersistedSuppressedRuntimeSession(
        sessionId = session.id,
        reason = SUPPRESSED_REASON_DELETED,
        updatedAtMillis = timestamp,
    )
}

private fun List<PersistedSuppressedRuntimeSession>.withRuntimeDeletions(
    sessions: List<PersistedChatSession>,
    nowMillis: Long,
): List<PersistedSuppressedRuntimeSession> {
    return sessions.fold(this) { suppressions, session ->
        suppressions.withRuntimeDeletion(session, nowMillis)
    }
}

private fun PersistedRuntimeData.deletedRuntimeSessionIds(): Set<String> {
    return suppressedRuntimeSessions
        .filter { it.reason == SUPPRESSED_REASON_DELETED }
        .mapTo(mutableSetOf()) { it.sessionId }
}

internal fun PersistedRuntimeData.withMemoryEntry(
    content: String,
    nowMillis: Long,
    entryId: String = UUID.randomUUID().toString(),
): PersistedRuntimeData {
    val trimmed = content.trim()
    if (trimmed.isBlank()) return this
    val entry = PersistedMemoryEntry(
        id = entryId,
        content = trimmed,
        enabled = true,
        createdAtMillis = nowMillis,
        updatedAtMillis = nowMillis,
    )
    return copy(memoryEntries = listOf(entry) + memoryEntries).sanitized()
}

internal fun PersistedRuntimeData.withoutMemoryEntry(entryId: String): PersistedRuntimeData {
    return copy(memoryEntries = memoryEntries.filterNot { it.id == entryId }).sanitized()
}

internal fun PersistedRuntimeData.withMemoryEntryEnabled(
    entryId: String,
    enabled: Boolean,
    nowMillis: Long,
): PersistedRuntimeData {
    return copy(
        memoryEntries = memoryEntries.map { entry ->
            if (entry.id == entryId) entry.copy(enabled = enabled, updatedAtMillis = nowMillis) else entry
        }
    ).sanitized()
}

internal fun activeSessionMessages(data: PersistedRuntimeData): List<RuntimeChatMessage> {
    val activeSessionId = data.activeSessionId ?: return emptyList()
    return data.sessions.firstOrNull { it.id == activeSessionId && it.archivedAtMillis == null }
        ?.messages
        ?.map { it.toRuntimeChatMessage() }
        ?: emptyList()
}

internal fun runtimeChatSessions(data: PersistedRuntimeData): List<RuntimeChatSession> {
    return data.sessions
        .filter { it.archivedAtMillis == null }
        .map { session ->
            session.toRuntimeChatSession()
        }
}

internal fun archivedRuntimeChatSessions(data: PersistedRuntimeData): List<RuntimeChatSession> {
    return data.sessions
        .filter { it.archivedAtMillis != null }
        .map { session ->
            session.toRuntimeChatSession()
        }
}

private fun PersistedChatSession.toRuntimeChatSession(): RuntimeChatSession {
    return RuntimeChatSession(
        id = id,
        title = title,
        updatedAtMillis = updatedAtMillis,
        messageCount = messages.size,
        archivedAtMillis = archivedAtMillis,
    )
}

internal fun memoryCandidateChatSessions(data: PersistedRuntimeData): List<RuntimeChatSession> {
    return runtimeChatSessions(data)
}

internal fun researchCandidateChatSessions(data: PersistedRuntimeData): List<RuntimeChatSession> {
    return runtimeChatSessions(data)
}

internal fun reflectionCandidateChatSessions(data: PersistedRuntimeData): List<RuntimeChatSession> {
    return runtimeChatSessions(data)
}

internal fun runtimeMemoryEntries(data: PersistedRuntimeData): List<RuntimeMemoryEntry> {
    return data.memoryEntries.map { entry ->
        RuntimeMemoryEntry(
            id = entry.id,
            content = entry.content,
            enabled = entry.enabled,
            createdAtMillis = entry.createdAtMillis,
            updatedAtMillis = entry.updatedAtMillis,
        )
    }
}

internal fun chatSendMessages(
    messages: List<RuntimeChatMessage>,
    memoryEntries: List<RuntimeMemoryEntry>,
    attachments: List<RuntimePendingAttachment> = emptyList(),
): List<ChatMessagePayload> {
    val capabilityGuard = ChatMessagePayload(
        role = "system",
        content = AETHERLINK_RUNTIME_CAPABILITY_GUARD,
    )
    val enabledMemory = memoryEntries
        .filter { it.enabled }
        .map { it.content.trim() }
        .filter { it.isNotBlank() }
    val systemContext = enabledMemory
        .takeIf { it.isNotEmpty() }
        ?.joinToString(separator = "\n", prefix = "Local user memory:\n") { "- $it" }
        ?.let { ChatMessagePayload(role = "system", content = it) }
    val conversationMessages = messages
        .filter { it.role == "user" || it.role == "assistant" }
        .filter { it.content.isNotBlank() }
    val conversation = conversationMessages
        .mapIndexed { index, message ->
            val messageAttachments = if (index == conversationMessages.lastIndex) {
                attachments.map { attachment ->
                    ChatAttachmentPayload(
                        type = attachment.type,
                        mimeType = attachment.mimeType,
                        name = attachment.name,
                        dataBase64 = attachment.dataBase64,
                    )
                }
            } else {
                emptyList()
            }
            ChatMessagePayload(
                role = message.role,
                content = message.content,
                attachments = messageAttachments,
            )
        }
    return listOfNotNull(capabilityGuard, systemContext) + conversation
}

internal const val AETHERLINK_RUNTIME_CAPABILITY_GUARD =
    "AetherLink currently provides runtime-mediated local model chat, model listing, file/image attachment handling when supported, chat titles, and suggested next questions. " +
        "The current build does not provide live web search, browsing, MCP tools, skills, scheduled automations, Python execution, or other external tools unless explicit tool output is included in this conversation. " +
        "Do not claim that you can search the web, browse, run tools, access files, or use unavailable integrations. If asked for an unavailable capability, say it is not available in this build and offer the closest supported alternative."

private fun PersistedChatMessage.toRuntimeChatMessage(): RuntimeChatMessage {
    return RuntimeChatMessage(
        id = id,
        role = role,
        content = content,
        reasoning = reasoning,
        suggestions = suggestions.cleanedSuggestions(),
    )
}

private fun RuntimeChatMessage.toPersistedChatMessage(nowMillis: Long): PersistedChatMessage {
    return PersistedChatMessage(
        id = id,
        role = role,
        content = content,
        reasoning = reasoning,
        suggestions = suggestions.cleanedSuggestions(),
        createdAtMillis = nowMillis,
    )
}

private fun stableRuntimeMessageId(
    sessionId: String,
    index: Int,
    message: ChatStoredMessagePayload,
): String {
    val seed = listOf(
        "runtime",
        sessionId,
        index.toString(),
        message.createdAt.orEmpty(),
        message.role,
        message.content,
        message.reasoning.orEmpty(),
    ).joinToString(separator = "\u001F")
    return UUID.nameUUIDFromBytes(seed.encodeToByteArray()).toString()
}

private fun parseTimestampMillis(timestamp: String): Long? {
    return runCatching { Instant.parse(timestamp).toEpochMilli() }.getOrNull()
}

private fun titleForMessages(messages: List<RuntimeChatMessage>): String {
    return messages.firstOrNull { it.role == "user" && it.content.isNotBlank() }
        ?.content
        ?.lineSequence()
        ?.firstOrNull()
        ?.trim()
        ?.take(MAX_TITLE_LENGTH)
        ?: DEFAULT_CHAT_TITLE
}

private val CHAT_STORAGE_ROLES = setOf("user", "assistant")
private const val DEFAULT_CHAT_TITLE = "New chat"
private const val MAX_TITLE_LENGTH = 48
private const val MAX_SAVED_SUGGESTIONS = 3

internal fun List<String>.cleanedSuggestions(): List<String> {
    return map { it.trim() }
        .filter { it.isNotBlank() }
        .distinct()
        .take(MAX_SAVED_SUGGESTIONS)
}

internal fun String.cleanedChatTitle(): String {
    return trim()
        .lineSequence()
        .firstOrNull()
        ?.trim()
        ?.trim('"', '\'', '`')
        ?.take(MAX_TITLE_LENGTH)
        .orEmpty()
}
