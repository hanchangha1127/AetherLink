import CryptoKit
import Foundation

public struct RuntimeLongInactivityMemorySummarizationPolicy: Equatable, Sendable {
    public static let defaultMinimumInactiveInterval: TimeInterval = 14 * 24 * 60 * 60

    public var minimumInactiveInterval: TimeInterval
    public var minimumMessageCount: Int
    public var maxCandidateCount: Int
    public var maxSourceMessageCount: Int
    public var maxDraftPreviewCharacters: Int
    public var maxSourceExcerptCharacters: Int

    public init(
        minimumInactiveInterval: TimeInterval = Self.defaultMinimumInactiveInterval,
        minimumMessageCount: Int = 6,
        maxCandidateCount: Int = 25,
        maxSourceMessageCount: Int = 12,
        maxDraftPreviewCharacters: Int = 600,
        maxSourceExcerptCharacters: Int = 160
    ) {
        self.minimumInactiveInterval = max(0, minimumInactiveInterval)
        self.minimumMessageCount = max(1, minimumMessageCount)
        self.maxCandidateCount = max(0, maxCandidateCount)
        self.maxSourceMessageCount = max(1, maxSourceMessageCount)
        self.maxDraftPreviewCharacters = max(80, maxDraftPreviewCharacters)
        self.maxSourceExcerptCharacters = max(40, maxSourceExcerptCharacters)
    }

    public func candidate(
        for session: RuntimeChatStoredSession,
        now: Date
    ) -> RuntimeLongInactivityMemorySummarizationCandidate? {
        guard session.status == "active" else { return nil }
        guard session.messageCount >= minimumMessageCount else { return nil }

        let inactiveInterval = now.timeIntervalSince(session.lastActivityAt)
        guard inactiveInterval >= minimumInactiveInterval else { return nil }

        return RuntimeLongInactivityMemorySummarizationCandidate(
            sessionID: session.sessionID,
            title: session.title,
            model: session.model,
            lastActivityAt: session.lastActivityAt,
            messageCount: session.messageCount,
            inactiveInterval: inactiveInterval
        )
    }

    public func candidates(
        from sessions: [RuntimeChatStoredSession],
        now: Date
    ) -> [RuntimeLongInactivityMemorySummarizationCandidate] {
        guard maxCandidateCount > 0 else { return [] }
        return sessions
            .compactMap { candidate(for: $0, now: now) }
            .sorted { lhs, rhs in
                if lhs.lastActivityAt != rhs.lastActivityAt {
                    return lhs.lastActivityAt < rhs.lastActivityAt
                }
                return lhs.sessionID < rhs.sessionID
            }
            .limited(to: maxCandidateCount)
    }

    public func draft(
        for candidate: RuntimeLongInactivityMemorySummarizationCandidate,
        messages: [RuntimeChatStoredMessage]
    ) -> RuntimeLongInactivityMemorySummarizationDraft? {
        let visibleMessages = visibleSourceMessages(from: messages)
        let selectedMessages = Array(visibleMessages.suffix(maxSourceMessageCount))
        guard !selectedMessages.isEmpty else { return nil }

        let sourceRangeDescription = sourceRangeDescription(
            selectedMessages: selectedMessages,
            totalMessageCount: visibleMessages.count
        )
        let sourcePointers = selectedMessages.map { message in
            RuntimeLongInactivityMemorySummarizationSourcePointer(
                sessionID: candidate.sessionID,
                messageIndex: message.ordinal,
                role: message.role,
                createdAt: message.createdAt,
                excerpt: message.content.truncated(to: maxSourceExcerptCharacters)
            )
        }
        let summaryPreview = summaryPreview(from: selectedMessages)

        return RuntimeLongInactivityMemorySummarizationDraft(
            candidate: candidate,
            id: sourceBoundDraftID(
                for: candidate,
                sourceMessageCount: selectedMessages.count,
                sourceRangeDescription: sourceRangeDescription,
                sourcePointers: sourcePointers,
                summaryPreview: summaryPreview
            ),
            sourceMessageCount: selectedMessages.count,
            sourceRangeDescription: sourceRangeDescription,
            sourcePointers: sourcePointers,
            summaryPreview: summaryPreview
        )
    }

    private func sourceBoundDraftID(
        for candidate: RuntimeLongInactivityMemorySummarizationCandidate,
        sourceMessageCount: Int,
        sourceRangeDescription: String,
        sourcePointers: [RuntimeLongInactivityMemorySummarizationSourcePointer],
        summaryPreview: String
    ) -> String {
        var hasher = SHA256()

        func append(_ data: Data) {
            hasher.update(data: data)
        }

        func appendByte(_ value: UInt8) {
            append(Data([value]))
        }

        func appendCount(_ value: Int) {
            var encoded = UInt64(value).bigEndian
            append(withUnsafeBytes(of: &encoded) { Data($0) })
        }

        func appendDate(_ value: Date) {
            var encoded = value.timeIntervalSinceReferenceDate.bitPattern.bigEndian
            append(withUnsafeBytes(of: &encoded) { Data($0) })
        }

        func appendOptionalDate(_ value: Date?) {
            guard let value else {
                appendByte(0)
                return
            }
            appendByte(1)
            appendDate(value)
        }

        func appendString(_ value: String) {
            let data = Data(value.utf8)
            appendCount(data.count)
            append(data)
        }

        append(Data("AetherLink long-inactivity memory-summary source v2\0".utf8))
        appendString(candidate.sessionID)
        appendString(candidate.title)
        appendString(candidate.model)
        appendDate(candidate.lastActivityAt)
        appendCount(candidate.messageCount)
        appendCount(sourceMessageCount)
        appendString(sourceRangeDescription)
        appendCount(sourcePointers.count)
        for pointer in sourcePointers {
            appendString(pointer.sessionID)
            appendCount(pointer.messageIndex)
            appendString(pointer.role)
            appendOptionalDate(pointer.createdAt)
            appendString(pointer.excerpt)
        }
        appendString(summaryPreview)

        let digest = hasher.finalize().map { String(format: "%02x", $0) }.joined()
        return "long-inactivity:v2:\(digest)"
    }

    private func visibleSourceMessages(
        from messages: [RuntimeChatStoredMessage]
    ) -> [RuntimeLongInactivityMemorySummarizationSourceMessage] {
        let unindexedMessages: [RuntimeLongInactivityMemorySummarizationSourceMessage] = messages.compactMap { message in
            let role = message.role.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
            guard role == "user" || role == "assistant" else { return nil }
            let content = normalizedDraftContent(message.content)
            guard !content.isEmpty else { return nil }
            return RuntimeLongInactivityMemorySummarizationSourceMessage(
                ordinal: 0,
                role: role,
                content: content,
                createdAt: message.createdAt
            )
        }
        return unindexedMessages.enumerated().map { offset, message in
            RuntimeLongInactivityMemorySummarizationSourceMessage(
                ordinal: offset + 1,
                role: message.role,
                content: message.content,
                createdAt: message.createdAt
            )
        }
    }

    private func sourceRangeDescription(
        selectedMessages: [RuntimeLongInactivityMemorySummarizationSourceMessage],
        totalMessageCount: Int
    ) -> String {
        guard let first = selectedMessages.first?.ordinal,
              let last = selectedMessages.last?.ordinal else {
            return "visible messages 0-0 of \(totalMessageCount)"
        }
        if first == last {
            return "visible message \(first) of \(totalMessageCount)"
        }
        return "visible messages \(first)-\(last) of \(totalMessageCount)"
    }

    private func summaryPreview(
        from messages: [RuntimeLongInactivityMemorySummarizationSourceMessage]
    ) -> String {
        var remainingCharacters = maxDraftPreviewCharacters
        var lines: [String] = []
        for message in messages {
            guard remainingCharacters > 0 else { break }
            let label = message.role == "assistant" ? "Assistant" : "User"
            let prefix = "\(label): "
            let availableCharacters = max(0, remainingCharacters - prefix.count)
            guard availableCharacters > 0 else { break }
            let content = message.content.truncated(to: availableCharacters)
            guard !content.isEmpty else { continue }
            let line = prefix + content
            lines.append(line)
            remainingCharacters -= line.count
            if remainingCharacters > 0 {
                remainingCharacters -= 1
            }
        }
        return lines.joined(separator: "\n")
    }

    private func normalizedDraftContent(_ content: String) -> String {
        content
            .components(separatedBy: .whitespacesAndNewlines)
            .filter { !$0.isEmpty }
            .joined(separator: " ")
    }
}

public struct RuntimeLongInactivityMemorySummarizationCandidate: Equatable, Sendable {
    public var sessionID: String
    public var title: String
    public var model: String
    public var lastActivityAt: Date
    public var messageCount: Int
    public var inactiveInterval: TimeInterval

    public init(
        sessionID: String,
        title: String,
        model: String,
        lastActivityAt: Date,
        messageCount: Int,
        inactiveInterval: TimeInterval
    ) {
        self.sessionID = sessionID
        self.title = title
        self.model = model
        self.lastActivityAt = lastActivityAt
        self.messageCount = messageCount
        self.inactiveInterval = inactiveInterval
    }
}

public struct RuntimeLongInactivityMemorySummarizationDraft: Equatable, Sendable {
    public var candidate: RuntimeLongInactivityMemorySummarizationCandidate
    public var id: String
    public var sourceMessageCount: Int
    public var sourceRangeDescription: String
    public var sourcePointers: [RuntimeLongInactivityMemorySummarizationSourcePointer]
    public var summaryPreview: String
    public var summaryMethod: String
    public var generatedAt: Date?
    public var generatedModelID: String?

    public init(
        candidate: RuntimeLongInactivityMemorySummarizationCandidate,
        id: String,
        sourceMessageCount: Int,
        sourceRangeDescription: String,
        sourcePointers: [RuntimeLongInactivityMemorySummarizationSourcePointer],
        summaryPreview: String,
        summaryMethod: String = "deterministic_preview",
        generatedAt: Date? = nil,
        generatedModelID: String? = nil
    ) {
        self.candidate = candidate
        self.id = id
        self.sourceMessageCount = sourceMessageCount
        self.sourceRangeDescription = sourceRangeDescription
        self.sourcePointers = sourcePointers
        self.summaryPreview = summaryPreview
        self.summaryMethod = summaryMethod
        self.generatedAt = generatedAt
        self.generatedModelID = generatedModelID
    }

    public func applyingGeneratedResult(
        _ generatedDraft: RuntimeGeneratedMemorySummaryDraft
    ) -> RuntimeLongInactivityMemorySummarizationDraft {
        guard generatedDraft.draftID == id,
              generatedDraft.sessionID == candidate.sessionID,
              generatedDraft.sourceMessageCount == sourceMessageCount else {
            return self
        }
        var composedDraft = self
        composedDraft.summaryPreview = generatedDraft.content
        composedDraft.summaryMethod = generatedDraft.summaryMethod
        composedDraft.generatedAt = generatedDraft.generatedAt
        composedDraft.generatedModelID = generatedDraft.modelID
        return composedDraft
    }

    public func hasSameMemorySummarySource(
        as other: RuntimeLongInactivityMemorySummarizationDraft
    ) -> Bool {
        id == other.id &&
            candidate.sessionID == other.candidate.sessionID &&
            candidate.title == other.candidate.title &&
            candidate.model == other.candidate.model &&
            candidate.lastActivityAt == other.candidate.lastActivityAt &&
            candidate.messageCount == other.candidate.messageCount &&
            sourceMessageCount == other.sourceMessageCount &&
            sourceRangeDescription == other.sourceRangeDescription &&
            sourcePointers == other.sourcePointers &&
            summaryPreview == other.summaryPreview
    }

}

public extension RuntimeLongInactivityMemorySummarizationPolicy {
    func applyingGeneratedResults(
        to drafts: [RuntimeLongInactivityMemorySummarizationDraft],
        generatedDrafts: [RuntimeGeneratedMemorySummaryDraft]
    ) -> [RuntimeLongInactivityMemorySummarizationDraft] {
        let generatedByID = Dictionary(
            generatedDrafts.map { ($0.draftID, $0) },
            uniquingKeysWith: { current, replacement in
                replacement.generatedAt > current.generatedAt ? replacement : current
            }
        )
        return drafts.map { draft in
            guard let generatedDraft = generatedByID[draft.id] else { return draft }
            return draft.applyingGeneratedResult(generatedDraft)
        }
    }
}

public struct RuntimeLongInactivityMemorySummarizationSourcePointer: Equatable, Sendable {
    public var sessionID: String
    public var messageIndex: Int
    public var role: String
    public var createdAt: Date?
    public var excerpt: String

    public init(
        sessionID: String,
        messageIndex: Int,
        role: String,
        createdAt: Date?,
        excerpt: String
    ) {
        self.sessionID = sessionID
        self.messageIndex = messageIndex
        self.role = role
        self.createdAt = createdAt
        self.excerpt = excerpt
    }
}

public extension RuntimeChatEventStore {
    func listLongInactivityMemorySummarizationCandidates(
        ownerDeviceID: String?,
        now: Date = Date(),
        policy: RuntimeLongInactivityMemorySummarizationPolicy = RuntimeLongInactivityMemorySummarizationPolicy()
    ) throws -> [RuntimeLongInactivityMemorySummarizationCandidate] {
        let sessions = try listSessions(
            ownerDeviceID: ownerDeviceID,
            limit: Int.max,
            includeArchived: false
        )
        return policy.candidates(from: sessions, now: now)
    }

    func listLongInactivityMemorySummarizationDrafts(
        ownerDeviceID: String?,
        now: Date = Date(),
        policy: RuntimeLongInactivityMemorySummarizationPolicy = RuntimeLongInactivityMemorySummarizationPolicy()
    ) throws -> [RuntimeLongInactivityMemorySummarizationDraft] {
        let candidates = try listLongInactivityMemorySummarizationCandidates(
            ownerDeviceID: ownerDeviceID,
            now: now,
            policy: policy
        )
        var drafts: [RuntimeLongInactivityMemorySummarizationDraft] = []
        for candidate in candidates {
            let messages = try listMessages(
                ownerDeviceID: ownerDeviceID,
                sessionID: candidate.sessionID,
                limit: Int.max
            )
            if let draft = policy.draft(for: candidate, messages: messages) {
                drafts.append(draft)
            }
        }
        return drafts
    }

    func listLongInactivityMemorySummarizationDrafts(
        ownerDeviceID: String?,
        memoryStore: any RuntimeMemoryStore,
        now: Date = Date(),
        policy: RuntimeLongInactivityMemorySummarizationPolicy = RuntimeLongInactivityMemorySummarizationPolicy()
    ) throws -> [RuntimeLongInactivityMemorySummarizationDraft] {
        let drafts = try listLongInactivityMemorySummarizationDrafts(
            ownerDeviceID: ownerDeviceID,
            now: now,
            policy: policy
        )
        let generatedDrafts = try memoryStore.generatedMemorySummaryDrafts(ownerDeviceID: ownerDeviceID)
        return policy.applyingGeneratedResults(to: drafts, generatedDrafts: generatedDrafts)
    }
}

private struct RuntimeLongInactivityMemorySummarizationSourceMessage {
    var ordinal: Int
    var role: String
    var content: String
    var createdAt: Date?
}

private extension String {
    func truncated(to limit: Int) -> String {
        guard limit > 0 else { return "" }
        guard count > limit else { return self }
        guard limit > 3 else { return String(prefix(limit)) }
        return String(prefix(limit - 3)) + "..."
    }
}
