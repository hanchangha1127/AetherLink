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
    public var ownerDeviceID: String?

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
        error: RuntimeChatStoredError? = nil,
        ownerDeviceID: String? = nil
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
        self.ownerDeviceID = ownerDeviceID.normalizedOwnerDeviceID
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
        case ownerDeviceID = "owner_device_id"
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
    public var search: RuntimeChatStoredSessionSearch?

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
        lastErrorCode: String? = nil,
        search: RuntimeChatStoredSessionSearch? = nil
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
        self.search = search
    }
}

public struct RuntimeChatStoredSessionSearch: Equatable, Sendable {
    public var rank: Int
    public var snippet: String
    public var matchedFields: [String]

    public init(rank: Int, snippet: String, matchedFields: [String]) {
        self.rank = rank
        self.snippet = snippet
        self.matchedFields = matchedFields
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
    func listSessions(ownerDeviceID: String?, limit: Int, includeArchived: Bool) throws -> [RuntimeChatStoredSession]
    func listSessions(
        ownerDeviceID: String?,
        limit: Int,
        includeArchived: Bool,
        query: String?,
        embeddingModelID: String?
    ) throws -> [RuntimeChatStoredSession]
    func listAllSessions(limit: Int, includeArchived: Bool) throws -> [RuntimeChatStoredSession]
    func listMessages(ownerDeviceID: String?, sessionID: String, limit: Int) throws -> [RuntimeChatStoredMessage]
    func listAllMessages(sessionID: String, limit: Int) throws -> [RuntimeChatStoredMessage]
    func mutateSession(
        ownerDeviceID: String?,
        sessionID: String,
        requestID: String,
        mutation: RuntimeChatSessionMutation,
        timestamp: Date
    ) throws -> RuntimeChatSessionMutationResult
}

public enum RuntimeChatEventStoreDefaults {
    public static func productionStore(
        sqliteDatabaseURL: URL = SQLiteRuntimeChatEventStore.defaultDatabaseURL(),
        legacyJSONLFileURL: URL? = JSONLRuntimeChatEventStore.defaultFileURL()
    ) -> any RuntimeChatEventStore {
        SQLiteRuntimeChatEventStore(
            databaseURL: sqliteDatabaseURL,
            legacyJSONLFileURL: legacyJSONLFileURL
        )
    }
}

public extension RuntimeChatEventStore {
    func listSessions(limit: Int, includeArchived: Bool) throws -> [RuntimeChatStoredSession] {
        try listSessions(ownerDeviceID: nil, limit: limit, includeArchived: includeArchived)
    }

    func listSessions(
        ownerDeviceID: String?,
        limit: Int,
        includeArchived: Bool,
        query: String?
    ) throws -> [RuntimeChatStoredSession] {
        try listSessions(
            ownerDeviceID: ownerDeviceID,
            limit: limit,
            includeArchived: includeArchived,
            query: query,
            embeddingModelID: nil
        )
    }

    func listSessions(
        ownerDeviceID: String?,
        limit: Int,
        includeArchived: Bool,
        query: String?,
        embeddingModelID: String?
    ) throws -> [RuntimeChatStoredSession] {
        guard let searchQuery = RuntimeChatSessionSearchQuery(query) else {
            return try listSessions(ownerDeviceID: ownerDeviceID, limit: limit, includeArchived: includeArchived)
        }
        guard limit > 0 else { return [] }

        let candidates = try listSessions(
            ownerDeviceID: ownerDeviceID,
            limit: Int.max,
            includeArchived: includeArchived
        )
        var matches: [(session: RuntimeChatStoredSession, match: RuntimeChatSessionSearchMatch)] = []
        for session in candidates {
            let messages = try listMessages(ownerDeviceID: ownerDeviceID, sessionID: session.sessionID, limit: Int.max)
            if let match = session.runtimeSearchMatch(searchQuery, messages: messages) {
                matches.append((session, match))
            }
        }
        return matches
            .sorted { lhs, rhs in
                if lhs.match.score != rhs.match.score {
                    return lhs.match.score > rhs.match.score
                }
                return lhs.session.lastActivityAt > rhs.session.lastActivityAt
            }
            .limited(to: limit)
            .enumerated()
            .map { offset, result in
                var session = result.session
                session.search = RuntimeChatStoredSessionSearch(
                    rank: offset + 1,
                    snippet: result.match.snippet,
                    matchedFields: result.match.matchedFields
                )
                return session
            }
    }

    func listSessions(limit: Int) throws -> [RuntimeChatStoredSession] {
        try listSessions(limit: limit, includeArchived: false)
    }

    func listAllSessions(limit: Int) throws -> [RuntimeChatStoredSession] {
        try listAllSessions(limit: limit, includeArchived: false)
    }

    func listMessages(sessionID: String, limit: Int) throws -> [RuntimeChatStoredMessage] {
        try listMessages(ownerDeviceID: nil, sessionID: sessionID, limit: limit)
    }

    func listAllMessages(sessionID: String) throws -> [RuntimeChatStoredMessage] {
        try listAllMessages(sessionID: sessionID, limit: 200)
    }

    func mutateSession(
        sessionID: String,
        requestID: String,
        mutation: RuntimeChatSessionMutation,
        timestamp: Date
    ) throws -> RuntimeChatSessionMutationResult {
        try mutateSession(
            ownerDeviceID: nil,
            sessionID: sessionID,
            requestID: requestID,
            mutation: mutation,
            timestamp: timestamp
        )
    }
}

public struct NullRuntimeChatEventStore: RuntimeChatEventStore {
    public init() {}

    public func append(_ event: RuntimeChatStoredEvent) throws {}

    public func listSessions(ownerDeviceID: String?, limit: Int, includeArchived: Bool) throws -> [RuntimeChatStoredSession] {
        []
    }

    public func listAllSessions(limit: Int, includeArchived: Bool) throws -> [RuntimeChatStoredSession] {
        []
    }

    public func listMessages(ownerDeviceID: String?, sessionID: String, limit: Int) throws -> [RuntimeChatStoredMessage] {
        []
    }

    public func listAllMessages(sessionID: String, limit: Int) throws -> [RuntimeChatStoredMessage] {
        []
    }

    public func mutateSession(
        ownerDeviceID: String?,
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

    public func listSessions(
        ownerDeviceID: String?,
        limit: Int = 100,
        includeArchived: Bool = false
    ) throws -> [RuntimeChatStoredSession] {
        guard limit > 0 else { return [] }
        return try lock.withLock {
            try Self.sessions(
                from: readEvents(ownerDeviceID: ownerDeviceID),
                limit: limit,
                includeArchived: includeArchived
            )
        }
    }

    public func listAllSessions(
        limit: Int = 100,
        includeArchived: Bool = false
    ) throws -> [RuntimeChatStoredSession] {
        guard limit > 0 else { return [] }
        return try lock.withLock {
            try Self.sessions(
                from: readEvents(),
                limit: limit,
                includeArchived: includeArchived
            )
        }
    }

    public func listMessages(
        ownerDeviceID: String?,
        sessionID: String,
        limit: Int = 200
    ) throws -> [RuntimeChatStoredMessage] {
        guard limit > 0 else { return [] }
        return try lock.withLock {
            try Self.messages(from: readEvents(ownerDeviceID: ownerDeviceID), sessionID: sessionID, limit: limit)
        }
    }

    public func listAllMessages(
        sessionID: String,
        limit: Int = 200
    ) throws -> [RuntimeChatStoredMessage] {
        guard limit > 0 else { return [] }
        return try lock.withLock {
            try Self.messages(from: readEvents(), sessionID: sessionID, limit: limit)
        }
    }

    public func mutateSession(
        ownerDeviceID: String?,
        sessionID: String,
        requestID: String,
        mutation: RuntimeChatSessionMutation,
        timestamp: Date = Date()
    ) throws -> RuntimeChatSessionMutationResult {
        try lock.withLock {
            let cleanSessionID = sessionID.trimmingCharacters(in: .whitespacesAndNewlines)
            let scopedOwnerDeviceID = ownerDeviceID.normalizedOwnerDeviceID
            let events = try readEvents(ownerDeviceID: scopedOwnerDeviceID)
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
                model: Self.latestModel(from: sessionEvents),
                ownerDeviceID: scopedOwnerDeviceID
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

    private func readEvents(ownerDeviceID: String?) throws -> [RuntimeChatStoredEvent] {
        let scopedOwnerDeviceID = ownerDeviceID.normalizedOwnerDeviceID
        return try readEvents().filter { $0.ownerDeviceID == scopedOwnerDeviceID }
    }

    private func readEvents() throws -> [RuntimeChatStoredEvent] {
        try Self.events(from: fileURL)
    }

    static func events(from fileURL: URL) throws -> [RuntimeChatStoredEvent] {
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
                let event = try decoder.decode(RuntimeChatStoredEvent.self, from: lineData)
                try Self.validateStoredEvent(event, line: index + 1)
                events.append(event)
            } catch {
                if let storeError = error as? RuntimeChatEventStoreError {
                    throw storeError
                }
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

    static func validateStoredEvent(_ event: RuntimeChatStoredEvent, line: Int) throws {
        try requireNonBlank(event.id, line: line, reason: "chat event id is empty")
        try requireNonBlank(event.requestID, line: line, reason: "chat request id is empty")
        try requireNonBlank(event.sessionID, line: line, reason: "chat session id is empty")

        switch event.kind {
        case .request:
            guard let messages = event.messages, !messages.isEmpty else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: line,
                    reason: "chat request messages are empty"
                )
            }
            for message in messages {
                try requireNonBlank(message.role, line: line, reason: "chat request message role is empty")
            }
        case .title:
            try requireNonBlank(event.title, line: line, reason: "chat title is empty")
        case .assistantDelta:
            try requireNonBlank(event.delta, line: line, reason: "chat assistant delta is empty")
        case .reasoningDelta:
            try requireNonBlank(event.reasoningDelta, line: line, reason: "chat reasoning delta is empty")
        case .error:
            guard let error = event.error else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: line,
                    reason: "chat error payload is missing"
                )
            }
            try requireNonBlank(error.code, line: line, reason: "chat error code is empty")
            try requireNonBlank(error.message, line: line, reason: "chat error message is empty")
        case .done, .cancelled, .archived, .restored, .deleted:
            break
        }
    }

    private static func requireNonBlank(_ value: String?, line: Int, reason: String) throws {
        guard let value, !value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw RuntimeChatEventStoreError.corruptEventLog(line: line, reason: reason)
        }
    }

    private func appendUnlocked(_ event: RuntimeChatStoredEvent) throws {
        let data = try encoder.encode(event.sanitizedForStorage())
        let line = data + Data([0x0A])
        try RuntimeEventLogFileProtection.appendLine(line, to: fileURL)
    }

    static func sessions(
        from events: [RuntimeChatStoredEvent],
        limit: Int,
        includeArchived: Bool
    ) throws -> [RuntimeChatStoredSession] {
        let grouped = Dictionary(grouping: events, by: \.sessionID)
        return grouped.compactMap { sessionID, events in
            let state = lifecycleState(from: events)
            guard state == .active || (includeArchived && state == .archived) else { return nil }
            let chatEvents = events.filter { !$0.kind.isSessionMetadata }
            guard let last = latestEvent(from: chatEvents)
                    ?? latestEvent(from: events) else { return nil }
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

    static func messages(
        from events: [RuntimeChatStoredEvent],
        sessionID: String,
        limit: Int
    ) -> [RuntimeChatStoredMessage] {
        let sessionEvents = events
            .enumerated()
            .filter { $0.element.sessionID == sessionID }
            .sorted { lhs, rhs in
                if lhs.element.timestamp == rhs.element.timestamp {
                    return lhs.offset < rhs.offset
                }
                return lhs.element.timestamp < rhs.element.timestamp
            }
            .map(\.element)
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
            .enumerated()
            .filter { $0.element.kind == .title }
            .compactMap { offset, event -> (offset: Int, event: RuntimeChatStoredEvent, title: String)? in
                let title = event.title?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
                guard !title.isEmpty else { return nil }
                return (offset, event, title)
            }
            .max { lhs, rhs in
                if lhs.event.timestamp == rhs.event.timestamp {
                    return lhs.offset < rhs.offset
                }
                return lhs.event.timestamp < rhs.event.timestamp
            }?
            .title
    }

    static func latestModel(from events: [RuntimeChatStoredEvent]) -> String {
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

    private static func latestEvent(from events: [RuntimeChatStoredEvent]) -> RuntimeChatStoredEvent? {
        events
            .enumerated()
            .max { lhs, rhs in
                if lhs.element.timestamp == rhs.element.timestamp {
                    return lhs.offset < rhs.offset
                }
                return lhs.element.timestamp < rhs.element.timestamp
            }?
            .element
    }

    private static let defaultSessionTitle = "New chat"
}

private enum RuntimeChatSessionLifecycleState: String {
    case active
    case archived
    case deleted
}

extension RuntimeChatSessionMutation {
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

extension RuntimeChatStoredEvent {
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

extension ChatAttachment {
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
        let normalizedContent = lowercasedContent.trimmingCharacters(in: .whitespacesAndNewlines)
        return (
            lowercasedContent.contains("aetherlink currently provides runtime-mediated local model chat") &&
                lowercasedContent.contains("does not provide live web search")
        ) || normalizedContent.hasPrefix("runtime user memory:")
    }
}

extension Array {
    func limited(to limit: Int) -> [Element] {
        guard limit > 0 else { return [] }
        guard count > limit else { return self }
        return Array(prefix(limit))
    }

    func limited(toLast limit: Int) -> [Element] {
        guard limit > 0 else { return [] }
        guard count > limit else { return self }
        return Array(suffix(limit))
    }
}

extension String {
    var nilIfBlank: String? {
        isEmpty ? nil : self
    }

    var runtimeSearchSnippetText: String {
        components(separatedBy: .whitespacesAndNewlines)
            .filter { !$0.isEmpty }
            .joined(separator: " ")
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }

    var normalizedRuntimeSearchText: String {
        folding(options: [.caseInsensitive, .diacriticInsensitive], locale: nil)
            .lowercased()
    }
}

private extension Optional where Wrapped == String {
    var normalizedOwnerDeviceID: String? {
        guard let value = self?.trimmingCharacters(in: .whitespacesAndNewlines),
              !value.isEmpty else {
            return nil
        }
        return value
    }
}

struct RuntimeChatSessionSearchQuery {
    let terms: [String]

    init?(_ rawQuery: String?) {
        let terms = rawQuery?
            .normalizedRuntimeSearchText
            .split(whereSeparator: { $0.isWhitespace })
            .map(String.init)
            ?? []
        guard !terms.isEmpty else { return nil }
        self.terms = terms
    }
}

struct RuntimeChatSessionSearchField {
    var name: String
    var text: String
    var weight: Int
    var order: Int
}

struct RuntimeChatSessionSearchMatch {
    var score: Int
    var snippet: String
    var matchedFields: [String]
}

extension RuntimeChatStoredSession {
    func runtimeSearchMatch(
        _ query: RuntimeChatSessionSearchQuery,
        messages: [RuntimeChatStoredMessage]
    ) -> RuntimeChatSessionSearchMatch? {
        let fields = searchFields(messages: messages)
        var matchedTerms = Set<String>()
        var matchedFields: [String] = []
        var score = 0
        var snippetCandidates: [(field: RuntimeChatSessionSearchField, termCount: Int)] = []

        for field in fields {
            let normalizedText = field.text.normalizedRuntimeSearchText
            guard !normalizedText.isEmpty else { continue }
            let fieldTerms = query.terms.filter { normalizedText.contains($0) }
            guard !fieldTerms.isEmpty else { continue }

            matchedTerms.formUnion(fieldTerms)
            if !matchedFields.contains(field.name) {
                matchedFields.append(field.name)
            }
            score += field.weight * fieldTerms.count
            if fieldTerms.count == query.terms.count {
                score += 25
            }
            snippetCandidates.append((field, fieldTerms.count))
        }

        guard query.terms.allSatisfy({ matchedTerms.contains($0) }) else { return nil }

        let bestSnippetField = snippetCandidates
            .sorted { lhs, rhs in
                if lhs.termCount != rhs.termCount {
                    return lhs.termCount > rhs.termCount
                }
                if lhs.field.weight != rhs.field.weight {
                    return lhs.field.weight > rhs.field.weight
                }
                return lhs.field.order < rhs.field.order
            }
            .first?
            .field
        let snippet = bestSnippetField
            .map { Self.searchSnippet(from: $0.text, terms: query.terms) }
            ?? title

        return RuntimeChatSessionSearchMatch(
            score: score,
            snippet: snippet,
            matchedFields: matchedFields
        )
    }

    private func searchFields(messages: [RuntimeChatStoredMessage]) -> [RuntimeChatSessionSearchField] {
        var fields: [RuntimeChatSessionSearchField] = []
        func append(_ name: String, _ text: String?, weight: Int) {
            guard let text = text?.runtimeSearchSnippetText, !text.isEmpty else { return }
            fields.append(RuntimeChatSessionSearchField(name: name, text: text, weight: weight, order: fields.count))
        }

        append("title", title, weight: 100)
        append("session_id", sessionID, weight: 40)
        append("model", model, weight: 60)
        append("status", status, weight: 25)
        append("last_event", lastEvent, weight: 25)
        append("last_finish_reason", lastFinishReason, weight: 20)
        append("last_error_code", lastErrorCode, weight: 20)
        for message in messages {
            append("transcript", message.content, weight: 80)
            append("reasoning", message.reasoning, weight: 50)
            for attachment in message.attachments {
                append("attachment", attachment.name, weight: 45)
                append("attachment", attachment.mimeType, weight: 25)
                append("attachment", attachment.text, weight: 70)
            }
        }
        return fields
    }

    private static func searchSnippet(
        from text: String,
        terms: [String],
        maxCharacters: Int = 160
    ) -> String {
        let cleanText = text.runtimeSearchSnippetText
        guard !cleanText.isEmpty else { return "" }
        guard cleanText.count > maxCharacters else { return cleanText }

        let firstRange = terms
            .compactMap { term in
                cleanText.range(of: term, options: [.caseInsensitive, .diacriticInsensitive])
            }
            .min { lhs, rhs in lhs.lowerBound < rhs.lowerBound }
        let center = firstRange?.lowerBound ?? cleanText.startIndex
        let prefixCharacters = maxCharacters / 3
        let start = cleanText.index(center, offsetBy: -prefixCharacters, limitedBy: cleanText.startIndex)
            ?? cleanText.startIndex
        let end = cleanText.index(start, offsetBy: maxCharacters, limitedBy: cleanText.endIndex)
            ?? cleanText.endIndex
        let snippet = cleanText[start..<end].trimmingCharacters(in: .whitespacesAndNewlines)
        let leading = start == cleanText.startIndex ? "" : "..."
        let trailing = end == cleanText.endIndex ? "" : "..."
        return leading + snippet + trailing
    }
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
