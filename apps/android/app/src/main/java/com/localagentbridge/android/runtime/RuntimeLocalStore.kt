package com.localagentbridge.android.runtime

import android.content.Context
import com.localagentbridge.android.core.protocol.ChatAttachmentPayload
import com.localagentbridge.android.core.protocol.ChatMessagePayload
import kotlinx.serialization.Serializable
import kotlinx.serialization.SerializationException
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.util.UUID

private const val STORE_NAME = "runtime_local_store"
private const val STORE_KEY = "runtime_data"

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
    val sessions: List<PersistedChatSession> = emptyList(),
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
            session.copy(
                title = session.title.takeIf(String::isNotBlank)
                    ?: titleForMessages(session.messages.map { it.toRuntimeChatMessage() }),
                messages = session.messages.filter { it.role in CHAT_STORAGE_ROLES },
            )
        }
    val cleanMemory = memoryEntries
        .filter { it.id.isNotBlank() && it.content.isNotBlank() }
        .distinctBy { it.id }
    return copy(
        activeSessionId = activeSessionId?.takeIf { id ->
            cleanSessions.any { it.id == id && it.archivedAtMillis == null }
        },
        selectedModelId = selectedModelId?.trim()?.takeIf(String::isNotBlank),
        selectedEmbeddingModelId = selectedEmbeddingModelId?.trim()?.takeIf(String::isNotBlank),
        sessions = cleanSessions.sortedByDescending { it.updatedAtMillis },
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
                session.copy(title = cleanTitle, updatedAtMillis = nowMillis)
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
        sessions = sessions.map { session ->
            if (session.id == sessionId) {
                session.copy(archivedAtMillis = null, updatedAtMillis = nowMillis)
            } else {
                session
            }
        },
    ).sanitized()
}

internal fun PersistedRuntimeData.withoutChatSession(sessionId: String): PersistedRuntimeData {
    return copy(
        activeSessionId = activeSessionId?.takeIf { it != sessionId },
        sessions = sessions.filterNot { it.id == sessionId },
    ).sanitized()
}

internal fun PersistedRuntimeData.withoutChatSessions(): PersistedRuntimeData {
    return copy(
        activeSessionId = null,
        sessions = emptyList(),
    ).sanitized()
}

internal fun PersistedRuntimeData.withNewChatSession(
    nowMillis: Long,
    sessionId: String = UUID.randomUUID().toString(),
): PersistedRuntimeData {
    val session = PersistedChatSession(
        id = sessionId,
        title = "New chat",
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
): PersistedRuntimeData {
    val existing = sessions.firstOrNull { it.id == sessionId }
    val createdAt = existing?.createdAtMillis ?: nowMillis
    val existingMessageTimes = existing?.messages.orEmpty().associate { it.id to it.createdAtMillis }
    val generatedTitle = titleForMessages(messages)
    val title = existing
        ?.title
        ?.takeIf { it != titleForMessages(existing.messages.map { message -> message.toRuntimeChatMessage() }) }
        ?: generatedTitle
    val persistedMessages = messages
        .filter { it.role in CHAT_STORAGE_ROLES }
        .map { it.toPersistedChatMessage(existingMessageTimes[it.id] ?: nowMillis) }
    val updatedSession = PersistedChatSession(
        id = sessionId,
        title = title,
        createdAtMillis = createdAt,
        updatedAtMillis = nowMillis,
        archivedAtMillis = existing?.archivedAtMillis,
        messages = persistedMessages,
    )
    return copy(
        activeSessionId = sessionId,
        sessions = listOf(updatedSession) + sessions.filterNot { it.id == sessionId },
    ).sanitized()
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
    return listOfNotNull(systemContext) + conversation
}

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

private fun titleForMessages(messages: List<RuntimeChatMessage>): String {
    return messages.firstOrNull { it.role == "user" && it.content.isNotBlank() }
        ?.content
        ?.lineSequence()
        ?.firstOrNull()
        ?.trim()
        ?.take(MAX_TITLE_LENGTH)
        ?: "New chat"
}

private val CHAT_STORAGE_ROLES = setOf("user", "assistant")
private const val MAX_TITLE_LENGTH = 48
private const val MAX_SAVED_SUGGESTIONS = 3

internal fun List<String>.cleanedSuggestions(): List<String> {
    return map { it.trim() }
        .filter { it.isNotBlank() }
        .distinct()
        .take(MAX_SAVED_SUGGESTIONS)
}
