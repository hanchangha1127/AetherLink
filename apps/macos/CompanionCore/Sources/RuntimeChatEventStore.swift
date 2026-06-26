import Foundation
import OllamaBackend

public enum RuntimeChatStoredEventKind: String, Codable, Equatable, Sendable {
    case request
    case assistantDelta = "assistant_delta"
    case reasoningDelta = "reasoning_delta"
    case title
    case archived
    case restored
    case deleted
    case done
    case cancelled
    case error
}

public enum RuntimeChatSessionMutation: String, Equatable, Sendable {
    case archive = "archived"
    case restore = "restored"
    case delete = "deleted"
}

public struct RuntimeChatSessionMutationResult: Equatable, Sendable {
    public var sessionID: String
    public var mutation: RuntimeChatSessionMutation
    public var timestamp: Date

    public init(sessionID: String, mutation: RuntimeChatSessionMutation, timestamp: Date) {
        self.sessionID = sessionID
        self.mutation = mutation
        self.timestamp = timestamp
    }
}

public enum RuntimeChatEventStoreError: Error, LocalizedError, Equatable {
    case sessionNotFound(String)
    case sessionMustBeArchivedBeforeDelete(String)
    case corruptEventLog(line: Int, reason: String)

    public var errorDescription: String? {
        switch self {
        case .sessionNotFound(let sessionID):
            return "Chat session not found: \(sessionID)"
        case .sessionMustBeArchivedBeforeDelete(let sessionID):
            return "Chat session must be archived before deletion: \(sessionID)"
        case .corruptEventLog(let line, let reason):
            return "Runtime chat event log is corrupt at line \(line): \(reason)"
        }
    }
}

public struct RuntimeChatStoredUsage: Codable, Equatable, Sendable {
    public var inputTokens: Int?
    public var outputTokens: Int?

    public init(inputTokens: Int?, outputTokens: Int?) {
        self.inputTokens = inputTokens
        self.outputTokens = outputTokens
    }

    enum CodingKeys: String, CodingKey {
        case inputTokens = "input_tokens"
        case outputTokens = "output_tokens"
    }
}

public struct RuntimeChatStoredError: Codable, Equatable, Sendable {
    public var code: String
    public var message: String

    public init(code: String, message: String) {
        self.code = code
        self.message = message
    }
}

public struct RuntimeChatStoredEvent: Codable, Equatable, Sendable {
    public var id: String
    public var timestamp: Date
    public var kind: RuntimeChatStoredEventKind
    public var requestID: String
    public var sessionID: String
    public var model: String
    public var messages: [ChatMessage]?
    public var title: String?
    public var delta: String?
    public var reasoningDelta: String?
    public var finishReason: String?
    public var usage: RuntimeChatStoredUsage?
    public var error: RuntimeChatStoredError?

    public init(
        id: String = UUID().uuidString,
        timestamp: Date = Date(),
        kind: RuntimeChatStoredEventKind,
        requestID: String,
        sessionID: String,
        model: String,
        messages: [ChatMessage]? = nil,
        title: String? = nil,
        delta: String? = nil,
        reasoningDelta: String? = nil,
        finishReason: String? = nil,
        usage: RuntimeChatStoredUsage? = nil,
        error: RuntimeChatStoredError? = nil
    ) {
        self.id = id
        self.timestamp = timestamp
        self.kind = kind
        self.requestID = requestID
        self.sessionID = sessionID
        self.model = model
        self.messages = messages
        self.title = title
        self.delta = delta
        self.reasoningDelta = reasoningDelta
        self.finishReason = finishReason
        self.usage = usage
        self.error = error
    }

    enum CodingKeys: String, CodingKey {
        case id
        case timestamp
        case kind
        case requestID = "request_id"
        case sessionID = "session_id"
        case model
        case messages
        case title
        case delta
        case reasoningDelta = "reasoning_delta"
        case finishReason = "finish_reason"
        case usage
        case error
    }
}

public struct RuntimeChatStoredSession: Equatable, Sendable {
    public var sessionID: String
    public var title: String
    public var model: String
    public var lastActivityAt: Date
    public var messageCount: Int
    public var status: String
    public var archivedAt: Date?
    public var lastEvent: String?
    public var lastFinishReason: String?
    public var lastErrorCode: String?

    public init(
        sessionID: String,
        title: String,
        model: String,
        lastActivityAt: Date,
        messageCount: Int,
        status: String = "active",
        archivedAt: Date? = nil,
        lastEvent: String? = nil,
        lastFinishReason: String? = nil,
        lastErrorCode: String? = nil
    ) {
        self.sessionID = sessionID
        self.title = title
        self.model = model
        self.lastActivityAt = lastActivityAt
        self.messageCount = messageCount
        self.status = status
        self.archivedAt = archivedAt
        self.lastEvent = lastEvent
        self.lastFinishReason = lastFinishReason
        self.lastErrorCode = lastErrorCode
    }
}

public struct RuntimeChatStoredMessage: Equatable, Sendable {
    public var role: String
    public var content: String
    public var reasoning: String?
    public var attachments: [ChatAttachment]
    public var createdAt: Date?

    public init(
        role: String,
        content: String,
        reasoning: String? = nil,
        attachments: [ChatAttachment] = [],
        createdAt: Date? = nil
    ) {
        self.role = role
        self.content = content
        self.reasoning = reasoning
        self.attachments = attachments
        self.createdAt = createdAt
    }
}

public protocol RuntimeChatEventStore: Sendable {
    func append(_ event: RuntimeChatStoredEvent) throws
    func listSessions(limit: Int, includeArchived: Bool) throws -> [RuntimeChatStoredSession]
    func listMessages(sessionID: String, limit: Int) throws -> [RuntimeChatStoredMessage]
    func mutateSession(
        sessionID: String,
        requestID: String,
        mutation: RuntimeChatSessionMutation,
        timestamp: Date
    ) throws -> RuntimeChatSessionMutationResult
}

public extension RuntimeChatEventStore {
    func listSessions(limit: Int) throws -> [RuntimeChatStoredSession] {
        try listSessions(limit: limit, includeArchived: false)
    }
}

public struct NullRuntimeChatEventStore: RuntimeChatEventStore {
    public init() {}

    public func append(_ event: RuntimeChatStoredEvent) throws {}

    public func listSessions(limit: Int, includeArchived: Bool) throws -> [RuntimeChatStoredSession] {
        []
    }

    public func listMessages(sessionID: String, limit: Int) throws -> [RuntimeChatStoredMessage] {
        []
    }

    public func mutateSession(
        sessionID: String,
        requestID: String,
        mutation: RuntimeChatSessionMutation,
        timestamp: Date
    ) throws -> RuntimeChatSessionMutationResult {
        RuntimeChatSessionMutationResult(sessionID: sessionID, mutation: mutation, timestamp: timestamp)
    }
}

public final class JSONLRuntimeChatEventStore: RuntimeChatEventStore, @unchecked Sendable {
    private let fileURL: URL
    private let encoder: JSONEncoder
    private let lock = NSLock()

    public init(fileURL: URL = JSONLRuntimeChatEventStore.defaultFileURL()) {
        self.fileURL = fileURL
        self.encoder = JSONEncoder()
        self.encoder.dateEncodingStrategy = .iso8601
        self.encoder.outputFormatting = [.sortedKeys]
    }

    public func append(_ event: RuntimeChatStoredEvent) throws {
        try lock.withLock {
            try appendUnlocked(event)
        }
    }

    public func listSessions(limit: Int = 100, includeArchived: Bool = false) throws -> [RuntimeChatStoredSession] {
        try lock.withLock {
            try Self.sessions(from: readEvents(), limit: limit, includeArchived: includeArchived)
        }
    }

    public func listMessages(sessionID: String, limit: Int = 200) throws -> [RuntimeChatStoredMessage] {
        try lock.withLock {
            try Self.messages(from: readEvents(), sessionID: sessionID, limit: limit)
        }
    }

    public func mutateSession(
        sessionID: String,
        requestID: String,
        mutation: RuntimeChatSessionMutation,
        timestamp: Date = Date()
    ) throws -> RuntimeChatSessionMutationResult {
        try lock.withLock {
            let cleanSessionID = sessionID.trimmingCharacters(in: .whitespacesAndNewlines)
            let events = try readEvents()
            let sessionEvents = events.filter { $0.sessionID == cleanSessionID }
            let lifecycleState = Self.lifecycleState(from: sessionEvents)
            guard !cleanSessionID.isEmpty,
                  !sessionEvents.isEmpty,
                  lifecycleState != .deleted else {
                throw RuntimeChatEventStoreError.sessionNotFound(sessionID)
            }
            if mutation == .delete, lifecycleState != .archived {
                throw RuntimeChatEventStoreError.sessionMustBeArchivedBeforeDelete(cleanSessionID)
            }
            try appendUnlocked(RuntimeChatStoredEvent(
                timestamp: timestamp,
                kind: mutation.eventKind,
                requestID: requestID,
                sessionID: cleanSessionID,
                model: Self.latestModel(from: sessionEvents)
            ))
            return RuntimeChatSessionMutationResult(
                sessionID: cleanSessionID,
                mutation: mutation,
                timestamp: timestamp
            )
        }
    }

    public static func defaultFileURL() -> URL {
        let baseDirectory = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support", isDirectory: true)
        return baseDirectory
            .appendingPathComponent("AetherLink", isDirectory: true)
            .appendingPathComponent("runtime-chat-events.jsonl", isDirectory: false)
    }

    private func readEvents() throws -> [RuntimeChatStoredEvent] {
        guard FileManager.default.fileExists(atPath: fileURL.path) else { return [] }
        let data = try Data(contentsOf: fileURL)
        guard !data.isEmpty else { return [] }
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let lines = String(decoding: data, as: UTF8.self)
            .components(separatedBy: .newlines)
        var events: [RuntimeChatStoredEvent] = []
        for (index, line) in lines.enumerated() {
            guard !line.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
                continue
            }
            let lineData = Data(line.utf8)
            do {
                events.append(try decoder.decode(RuntimeChatStoredEvent.self, from: lineData))
            } catch {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: index + 1,
                    reason: Self.decodeFailureReason(error)
                )
            }
        }
        return events.sorted { $0.timestamp < $1.timestamp }
    }

    private static func decodeFailureReason(_ error: Error) -> String {
        if let decodingError = error as? DecodingError {
            switch decodingError {
            case .dataCorrupted:
                return "data corrupted"
            case .keyNotFound(let key, _):
                return "missing key '\(key.stringValue)'"
            case .typeMismatch(let type, _):
                return "type mismatch for \(type)"
            case .valueNotFound(let type, _):
                return "missing value for \(type)"
            @unknown default:
                return "decode failed"
            }
        }
        return "decode failed"
    }

    private func appendUnlocked(_ event: RuntimeChatStoredEvent) throws {
        let directory = fileURL.deletingLastPathComponent()
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let data = try encoder.encode(event.sanitizedForStorage())
        let line = data + Data([0x0A])
        if FileManager.default.fileExists(atPath: fileURL.path) {
            let handle = try FileHandle(forWritingTo: fileURL)
            defer { try? handle.close() }
            try handle.seekToEnd()
            try handle.write(contentsOf: line)
        } else {
            try line.write(to: fileURL, options: .atomic)
        }
    }

    private static func sessions(
        from events: [RuntimeChatStoredEvent],
        limit: Int,
        includeArchived: Bool
    ) throws -> [RuntimeChatStoredSession] {
        let grouped = Dictionary(grouping: events, by: \.sessionID)
        return grouped.compactMap { sessionID, events in
            let state = lifecycleState(from: events)
            guard state == .active || (includeArchived && state == .archived) else { return nil }
            let chatEvents = events.filter { !$0.kind.isSessionMetadata }
            guard let last = chatEvents.max(by: { $0.timestamp < $1.timestamp })
                    ?? events.max(by: { $0.timestamp < $1.timestamp }) else { return nil }
            let messages = messages(from: events, sessionID: sessionID, limit: Int.max)
            let archivedAt = state == .archived ? latestLifecycleEvent(from: events)?.timestamp : nil
            return RuntimeChatStoredSession(
                sessionID: sessionID,
                title: latestStoredTitle(from: events) ?? defaultSessionTitle,
                model: last.model,
                lastActivityAt: last.timestamp,
                messageCount: messages.count,
                status: state.rawValue,
                archivedAt: archivedAt,
                lastEvent: last.kind.rawValue,
                lastFinishReason: last.finishReason?.trimmingCharacters(in: .whitespacesAndNewlines).nilIfBlank,
                lastErrorCode: last.error?.code.trimmingCharacters(in: .whitespacesAndNewlines).nilIfBlank
            )
        }
        .sorted { $0.lastActivityAt > $1.lastActivityAt }
        .limited(to: limit)
    }

    private static func messages(
        from events: [RuntimeChatStoredEvent],
        sessionID: String,
        limit: Int
    ) -> [RuntimeChatStoredMessage] {
        let sessionEvents = events
            .filter { $0.sessionID == sessionID }
            .sorted { $0.timestamp < $1.timestamp }
        guard !sessionEvents.isEmpty else { return [] }
        guard lifecycleState(from: sessionEvents) != .deleted else { return [] }

        let requestEvents = sessionEvents.filter { $0.kind == .request }
        var messages: [RuntimeChatStoredMessage] = []

        for request in requestEvents {
            let requestMessages = request.messages?
                .filter { !$0.isRuntimeOnlySystemMessage }
                .map {
                    RuntimeChatStoredMessage(
                        role: $0.role,
                        content: $0.content,
                        attachments: $0.attachments.map(\.withoutInlineData),
                        createdAt: request.timestamp
                    )
                }
                ?? []
            messages = mergeTranscript(messages, withRequestMessages: requestMessages)

            let responseEvents = sessionEvents
                .filter { $0.requestID == request.requestID && $0.timestamp >= request.timestamp }
            let answer = responseEvents
                .compactMap(\.delta)
                .joined()
                .trimmingCharacters(in: .whitespacesAndNewlines)
            let reasoning = responseEvents
                .compactMap(\.reasoningDelta)
                .joined()
                .trimmingCharacters(in: .whitespacesAndNewlines)
            if !answer.isEmpty || !reasoning.isEmpty {
                messages.append(RuntimeChatStoredMessage(
                    role: "assistant",
                    content: answer,
                    reasoning: reasoning.isEmpty ? nil : reasoning,
                    createdAt: responseEvents.last?.timestamp
                ))
            }
        }

        return messages.limited(toLast: limit)
    }

    private static func mergeTranscript(
        _ existing: [RuntimeChatStoredMessage],
        withRequestMessages requestMessages: [RuntimeChatStoredMessage]
    ) -> [RuntimeChatStoredMessage] {
        guard !requestMessages.isEmpty else { return existing }
        guard !existing.isEmpty else { return requestMessages }

        let maxOverlap = min(existing.count, requestMessages.count)
        let overlap = stride(from: maxOverlap, through: 1, by: -1).first { count in
            let existingSuffix = existing.suffix(count)
            let requestPrefix = requestMessages.prefix(count)
            return zip(existingSuffix, requestPrefix).allSatisfy { existingMessage, requestMessage in
                sameMessageContent(existingMessage, requestMessage)
            }
        } ?? 0

        return existing + requestMessages.dropFirst(overlap)
    }

    private static func sameMessageContent(
        _ lhs: RuntimeChatStoredMessage,
        _ rhs: RuntimeChatStoredMessage
    ) -> Bool {
        lhs.role == rhs.role && lhs.content == rhs.content
    }

    private static func latestStoredTitle(from events: [RuntimeChatStoredEvent]) -> String? {
        events
            .filter { $0.kind == .title }
            .sorted { $0.timestamp > $1.timestamp }
            .compactMap { event in
                let title = event.title?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
                return title.isEmpty ? nil : title
            }
            .first
    }

    private static func latestModel(from events: [RuntimeChatStoredEvent]) -> String {
        events
            .reversed()
            .first { !$0.model.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }?
            .model ?? ""
    }

    private static func lifecycleState(from events: [RuntimeChatStoredEvent]) -> RuntimeChatSessionLifecycleState {
        guard let latestLifecycle = latestLifecycleEvent(from: events) else {
            return .active
        }
        switch latestLifecycle.kind {
        case .archived:
            return .archived
        case .deleted:
            return .deleted
        case .restored:
            return .active
        default:
            return .active
        }
    }

    private static func latestLifecycleEvent(from events: [RuntimeChatStoredEvent]) -> RuntimeChatStoredEvent? {
        let lifecycleEvents = events
            .enumerated()
            .filter { $0.element.kind.isSessionLifecycle }
        return lifecycleEvents
            .max(by: { lhs, rhs in
                if lhs.element.timestamp == rhs.element.timestamp {
                    return lhs.offset < rhs.offset
                }
                return lhs.element.timestamp < rhs.element.timestamp
            })?.element
    }

    private static let defaultSessionTitle = "New chat"
}

private enum RuntimeChatSessionLifecycleState: String {
    case active
    case archived
    case deleted
}

private extension RuntimeChatSessionMutation {
    var eventKind: RuntimeChatStoredEventKind {
        switch self {
        case .archive:
            return .archived
        case .restore:
            return .restored
        case .delete:
            return .deleted
        }
    }
}

private extension RuntimeChatStoredEventKind {
    var isSessionLifecycle: Bool {
        switch self {
        case .archived, .restored, .deleted:
            return true
        default:
            return false
        }
    }

    var isSessionMetadata: Bool {
        self == .title || isSessionLifecycle
    }
}

private extension RuntimeChatStoredEvent {
    func sanitizedForStorage() -> RuntimeChatStoredEvent {
        var copy = self
        copy.messages = messages?.map { message in
            ChatMessage(
                role: message.role,
                content: message.content,
                attachments: message.attachments.map(\.withoutInlineData)
            )
        }
        return copy
    }
}

private extension ChatAttachment {
    var withoutInlineData: ChatAttachment {
        ChatAttachment(
            type: type,
            mimeType: mimeType,
            name: name,
            dataBase64: nil,
            text: text
        )
    }
}

private extension ChatMessage {
    var isRuntimeOnlySystemMessage: Bool {
        guard role.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() == "system" else {
            return false
        }
        let lowercasedContent = content.lowercased()
        return lowercasedContent.contains("aetherlink currently provides runtime-mediated local model chat") &&
            lowercasedContent.contains("does not provide live web search")
    }
}

private extension Array {
    func limited(to limit: Int) -> [Element] {
        guard limit > 0, count > limit else { return self }
        return Array(prefix(limit))
    }

    func limited(toLast limit: Int) -> [Element] {
        guard limit > 0, count > limit else { return self }
        return Array(suffix(limit))
    }
}

private extension String {
    var nilIfBlank: String? {
        isEmpty ? nil : self
    }
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
