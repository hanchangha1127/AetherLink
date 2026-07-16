import Foundation

public enum RuntimeResearchNotebookLifecycle: String, Codable, Equatable, Sendable {
    case active
    case archived
}

public enum RuntimeResearchNotebookLifecycleMutation: String, Codable, Equatable, Sendable {
    case create
    case archive
    case restore
    case delete

    init(_ mutation: RuntimeChatSessionMutation) {
        switch mutation {
        case .archive: self = .archive
        case .restore: self = .restore
        case .delete: self = .delete
        }
    }
}

public struct RuntimeResearchNotebookLifecycleIntent: Equatable, Sendable {
    public let ownerDeviceID: String
    public let notebookID: String
    public let backingSessionID: String
    public let mutation: RuntimeResearchNotebookLifecycleMutation
    public let coordinatorID: String
    public let operationID: String
    public let leaseExpiresAt: Date

    public init(
        ownerDeviceID: String,
        notebookID: String,
        backingSessionID: String,
        mutation: RuntimeResearchNotebookLifecycleMutation,
        coordinatorID: String,
        operationID: String,
        leaseExpiresAt: Date
    ) {
        self.ownerDeviceID = ownerDeviceID
        self.notebookID = notebookID
        self.backingSessionID = backingSessionID
        self.mutation = mutation
        self.coordinatorID = coordinatorID
        self.operationID = operationID
        self.leaseExpiresAt = leaseExpiresAt
    }
}

public struct RuntimeResearchNotebook: Equatable, Sendable {
    public static let notebookIDPrefix = "research_notebook_"
    public static let trustedSourceGrantIDPrefix = "trusted_source_"
    public static let maximumOwnerDeviceIDUTF8Bytes = 512
    public static let maximumBackingSessionIDUTF8Bytes = 1_024
    public static let maximumTitleUTF8Bytes = 1_024
    public static let maximumModelUTF8Bytes = 1_024
    public static let maximumBackingSessionIDCharacters = 256
    public static let maximumTitleCharacters = 256
    public static let maximumModelCharacters = 256
    public static let maximumTrustedSourceGrantCount = 8
    public static let maximumListLimit = 100
    public static let maximumStoreListLimit = 10_000
    public static let maximumRowsPerOwner = maximumStoreListLimit

    public let notebookID: String
    public let ownerDeviceID: String
    public let backingSessionID: String
    public let title: String
    public let model: String
    public let promptSkillBinding: RuntimePromptSkillBinding
    public let trustedSourceGrantIDs: [String]
    public let lifecycle: RuntimeResearchNotebookLifecycle
    public let createdAt: Date
    public let updatedAt: Date

    public static func isCanonicalNotebookID(_ value: String) -> Bool {
        isCanonicalPrefixedHexID(value, prefix: notebookIDPrefix)
    }

    public static func isCanonicalTrustedSourceGrantID(_ value: String) -> Bool {
        isCanonicalPrefixedHexID(value, prefix: trustedSourceGrantIDPrefix)
    }

    public static func makeNotebookID() -> String {
        notebookIDPrefix + UUID().uuidString.replacingOccurrences(of: "-", with: "").lowercased()
    }

    init(
        notebookID: String,
        ownerDeviceID: String,
        backingSessionID: String,
        title: String,
        model: String,
        promptSkillBinding: RuntimePromptSkillBinding,
        trustedSourceGrantIDs: [String],
        lifecycle: RuntimeResearchNotebookLifecycle,
        createdAt: Date,
        updatedAt: Date
    ) {
        self.notebookID = notebookID
        self.ownerDeviceID = ownerDeviceID
        self.backingSessionID = backingSessionID
        self.title = title
        self.model = model
        self.promptSkillBinding = promptSkillBinding
        self.trustedSourceGrantIDs = trustedSourceGrantIDs
        self.lifecycle = lifecycle
        self.createdAt = createdAt
        self.updatedAt = updatedAt
    }
}

public enum RuntimeResearchNotebookStoreError: Error, Equatable, LocalizedError, Sendable {
    case invalidField(String)
    case notebookIDCollision
    case backingSessionIDCollision
    case rowLimitReached
    case corruptPersistence
    case storageFailure(String)

    public var errorDescription: String? {
        switch self {
        case .invalidField(let field):
            return "The research notebook field \(field) is invalid."
        case .notebookIDCollision:
            return "The research notebook ID already exists."
        case .backingSessionIDCollision:
            return "The research notebook backing session already has a notebook for this owner."
        case .rowLimitReached:
            return "The research notebook row limit has been reached for this owner."
        case .corruptPersistence:
            return "The research notebook metadata store is corrupt."
        case .storageFailure(let message):
            return message
        }
    }
}

public protocol RuntimeResearchNotebookStoring: AnyObject, Sendable {
    func withLifecycleCoordination<Result>(
        _ body: () throws -> Result
    ) rethrows -> Result

    @discardableResult
    func create(
        ownerDeviceID: String,
        notebookID: String,
        backingSessionID: String,
        title: String,
        model: String,
        promptSkillBinding: RuntimePromptSkillBinding,
        trustedSourceGrantIDs: [String]
    ) throws -> RuntimeResearchNotebook

    func createPendingChatPersistence(
        ownerDeviceID: String,
        notebookID: String,
        backingSessionID: String,
        title: String,
        model: String,
        promptSkillBinding: RuntimePromptSkillBinding,
        trustedSourceGrantIDs: [String],
        coordinatorID: String,
        operationID: String,
        leaseExpiresAt: Date
    ) throws -> RuntimeResearchNotebookLifecycleIntent

    func get(
        ownerDeviceID: String,
        notebookID: String
    ) throws -> RuntimeResearchNotebook?

    func getByBackingSessionID(
        ownerDeviceID: String,
        backingSessionID: String
    ) throws -> RuntimeResearchNotebook?

    func list(
        ownerDeviceID: String,
        lifecycle: RuntimeResearchNotebookLifecycle?,
        limit: Int
    ) throws -> [RuntimeResearchNotebook]

    @discardableResult
    func archive(
        ownerDeviceID: String,
        notebookID: String
    ) throws -> RuntimeResearchNotebook?

    @discardableResult
    func restore(
        ownerDeviceID: String,
        notebookID: String
    ) throws -> RuntimeResearchNotebook?

    @discardableResult
    func delete(
        ownerDeviceID: String,
        notebookID: String
    ) throws -> Bool

    func prepareLifecycleMutation(
        ownerDeviceID: String,
        backingSessionID: String,
        mutation: RuntimeResearchNotebookLifecycleMutation,
        coordinatorID: String,
        operationID: String,
        leaseExpiresAt: Date
    ) throws -> RuntimeResearchNotebookLifecycleIntent?

    func renewLifecycleMutation(
        _ intent: RuntimeResearchNotebookLifecycleIntent,
        leaseExpiresAt: Date
    ) throws -> RuntimeResearchNotebookLifecycleIntent

    func completeLifecycleMutation(
        _ intent: RuntimeResearchNotebookLifecycleIntent
    ) throws

    func cancelLifecycleMutation(
        _ intent: RuntimeResearchNotebookLifecycleIntent
    ) throws

    func pendingLifecycleMutations(
        ownerDeviceID: String
    ) throws -> [RuntimeResearchNotebookLifecycleIntent]
}

public extension RuntimeResearchNotebookStoring {
    func list(ownerDeviceID: String) throws -> [RuntimeResearchNotebook] {
        try list(
            ownerDeviceID: ownerDeviceID,
            lifecycle: nil,
            limit: RuntimeResearchNotebook.maximumListLimit
        )
    }

    func list(
        ownerDeviceID: String,
        lifecycle: RuntimeResearchNotebookLifecycle?
    ) throws -> [RuntimeResearchNotebook] {
        try list(
            ownerDeviceID: ownerDeviceID,
            lifecycle: lifecycle,
            limit: RuntimeResearchNotebook.maximumListLimit
        )
    }

    func list(
        ownerDeviceID: String,
        limit: Int
    ) throws -> [RuntimeResearchNotebook] {
        try list(ownerDeviceID: ownerDeviceID, lifecycle: nil, limit: limit)
    }
}

public final class RuntimeResearchNotebookStore: RuntimeResearchNotebookStoring, @unchecked Sendable {
    private struct OwnerSessionKey: Hashable {
        let ownerDeviceID: String
        let backingSessionID: String
    }

    private var notebooksByID: [String: RuntimeResearchNotebook] = [:]
    private var notebookIDByOwnerSession: [OwnerSessionKey: String] = [:]
    private var lifecycleIntentsByNotebookID: [String: RuntimeResearchNotebookLifecycleIntent] = [:]
    private let rowLimitPerOwner: Int
    private let now: @Sendable () -> Date
    private let lock = NSRecursiveLock()

    public init(
        rowLimitPerOwner: Int = RuntimeResearchNotebook.maximumRowsPerOwner,
        now: @escaping @Sendable () -> Date = { Date() }
    ) {
        self.rowLimitPerOwner = max(
            1,
            min(rowLimitPerOwner, RuntimeResearchNotebook.maximumRowsPerOwner)
        )
        self.now = now
    }

    public func withLifecycleCoordination<Result>(
        _ body: () throws -> Result
    ) rethrows -> Result {
        try lock.withLock(body)
    }

    @discardableResult
    public func create(
        ownerDeviceID: String,
        notebookID: String,
        backingSessionID: String,
        title: String,
        model: String,
        promptSkillBinding: RuntimePromptSkillBinding,
        trustedSourceGrantIDs: [String]
    ) throws -> RuntimeResearchNotebook {
        try runtimeResearchNotebookValidateCreateFields(
            ownerDeviceID: ownerDeviceID,
            notebookID: notebookID,
            backingSessionID: backingSessionID,
            title: title,
            model: model,
            promptSkillBinding: promptSkillBinding,
            trustedSourceGrantIDs: trustedSourceGrantIDs
        )

        return try lock.withLock {
            try createLocked(
                ownerDeviceID: ownerDeviceID,
                notebookID: notebookID,
                backingSessionID: backingSessionID,
                title: title,
                model: model,
                promptSkillBinding: promptSkillBinding,
                trustedSourceGrantIDs: trustedSourceGrantIDs
            )
        }
    }

    public func createPendingChatPersistence(
        ownerDeviceID: String,
        notebookID: String,
        backingSessionID: String,
        title: String,
        model: String,
        promptSkillBinding: RuntimePromptSkillBinding,
        trustedSourceGrantIDs: [String],
        coordinatorID: String,
        operationID: String,
        leaseExpiresAt: Date
    ) throws -> RuntimeResearchNotebookLifecycleIntent {
        try runtimeResearchNotebookValidateCreateFields(
            ownerDeviceID: ownerDeviceID,
            notebookID: notebookID,
            backingSessionID: backingSessionID,
            title: title,
            model: model,
            promptSkillBinding: promptSkillBinding,
            trustedSourceGrantIDs: trustedSourceGrantIDs
        )
        try runtimeResearchNotebookValidateLifecycleIdentity(
            coordinatorID: coordinatorID,
            operationID: operationID,
            leaseExpiresAt: leaseExpiresAt
        )
        return try lock.withLock {
            let notebook = try createLocked(
                ownerDeviceID: ownerDeviceID,
                notebookID: notebookID,
                backingSessionID: backingSessionID,
                title: title,
                model: model,
                promptSkillBinding: promptSkillBinding,
                trustedSourceGrantIDs: trustedSourceGrantIDs
            )
            let intent = RuntimeResearchNotebookLifecycleIntent(
                ownerDeviceID: ownerDeviceID,
                notebookID: notebook.notebookID,
                backingSessionID: backingSessionID,
                mutation: .create,
                coordinatorID: coordinatorID,
                operationID: operationID,
                leaseExpiresAt: leaseExpiresAt
            )
            lifecycleIntentsByNotebookID[notebook.notebookID] = intent
            return intent
        }
    }

    public func get(
        ownerDeviceID: String,
        notebookID: String
    ) throws -> RuntimeResearchNotebook? {
        try runtimeResearchNotebookValidateOwner(ownerDeviceID)
        try runtimeResearchNotebookValidateID(notebookID)
        return lock.withLock {
            guard let notebook = notebooksByID[notebookID],
                  notebook.ownerDeviceID == ownerDeviceID else {
                return nil
            }
            return notebook
        }
    }

    public func getByBackingSessionID(
        ownerDeviceID: String,
        backingSessionID: String
    ) throws -> RuntimeResearchNotebook? {
        try runtimeResearchNotebookValidateOwner(ownerDeviceID)
        try runtimeResearchNotebookValidateBackingSessionID(backingSessionID)
        return lock.withLock {
            let key = OwnerSessionKey(
                ownerDeviceID: ownerDeviceID,
                backingSessionID: backingSessionID
            )
            guard let notebookID = notebookIDByOwnerSession[key] else { return nil }
            return notebooksByID[notebookID]
        }
    }

    public func list(
        ownerDeviceID: String,
        lifecycle: RuntimeResearchNotebookLifecycle? = nil,
        limit: Int = RuntimeResearchNotebook.maximumListLimit
    ) throws -> [RuntimeResearchNotebook] {
        try runtimeResearchNotebookValidateOwner(ownerDeviceID)
        try runtimeResearchNotebookValidateListLimit(limit)
        return lock.withLock {
            notebooksByID.values
                .filter {
                    $0.ownerDeviceID == ownerDeviceID
                        && (lifecycle == nil || $0.lifecycle == lifecycle)
                }
                .sorted(by: runtimeResearchNotebookPrecedes)
                .prefix(limit)
                .map { $0 }
        }
    }

    @discardableResult
    public func archive(
        ownerDeviceID: String,
        notebookID: String
    ) throws -> RuntimeResearchNotebook? {
        try mutateLifecycle(
            ownerDeviceID: ownerDeviceID,
            notebookID: notebookID,
            lifecycle: .archived
        )
    }

    @discardableResult
    public func restore(
        ownerDeviceID: String,
        notebookID: String
    ) throws -> RuntimeResearchNotebook? {
        try mutateLifecycle(
            ownerDeviceID: ownerDeviceID,
            notebookID: notebookID,
            lifecycle: .active
        )
    }

    @discardableResult
    public func delete(
        ownerDeviceID: String,
        notebookID: String
    ) throws -> Bool {
        try runtimeResearchNotebookValidateOwner(ownerDeviceID)
        try runtimeResearchNotebookValidateID(notebookID)
        return lock.withLock {
            guard let notebook = notebooksByID[notebookID],
                  notebook.ownerDeviceID == ownerDeviceID else {
                return false
            }
            notebooksByID.removeValue(forKey: notebookID)
            lifecycleIntentsByNotebookID.removeValue(forKey: notebookID)
            notebookIDByOwnerSession.removeValue(forKey: OwnerSessionKey(
                ownerDeviceID: ownerDeviceID,
                backingSessionID: notebook.backingSessionID
            ))
            return true
        }
    }

    public func prepareLifecycleMutation(
        ownerDeviceID: String,
        backingSessionID: String,
        mutation: RuntimeResearchNotebookLifecycleMutation,
        coordinatorID: String,
        operationID: String,
        leaseExpiresAt: Date
    ) throws -> RuntimeResearchNotebookLifecycleIntent? {
        try runtimeResearchNotebookValidateOwner(ownerDeviceID)
        try runtimeResearchNotebookValidateBackingSessionID(backingSessionID)
        try runtimeResearchNotebookValidateLifecycleIdentity(
            coordinatorID: coordinatorID,
            operationID: operationID,
            leaseExpiresAt: leaseExpiresAt
        )
        return try lock.withLock {
            let key = OwnerSessionKey(
                ownerDeviceID: ownerDeviceID,
                backingSessionID: backingSessionID
            )
            guard let notebookID = notebookIDByOwnerSession[key],
                  let notebook = notebooksByID[notebookID] else {
                return nil
            }
            let intent = RuntimeResearchNotebookLifecycleIntent(
                ownerDeviceID: ownerDeviceID,
                notebookID: notebook.notebookID,
                backingSessionID: backingSessionID,
                mutation: mutation,
                coordinatorID: coordinatorID,
                operationID: operationID,
                leaseExpiresAt: leaseExpiresAt
            )
            if let current = lifecycleIntentsByNotebookID[notebookID] {
                guard current == intent else {
                    throw RuntimeResearchNotebookStoreError.storageFailure(
                        "A different research notebook lifecycle mutation is already pending."
                    )
                }
                return current
            }
            lifecycleIntentsByNotebookID[notebookID] = intent
            return intent
        }
    }

    public func completeLifecycleMutation(
        _ intent: RuntimeResearchNotebookLifecycleIntent
    ) throws {
        try runtimeResearchNotebookValidateLifecycleIntent(intent)
        try lock.withLock {
            guard let pending = lifecycleIntentsByNotebookID[intent.notebookID] else {
                try validateCompletedLifecycleIntentLocked(intent)
                return
            }
            guard pending == intent else {
                throw RuntimeResearchNotebookStoreError.corruptPersistence
            }
            switch intent.mutation {
            case .create:
                guard let notebook = notebooksByID[intent.notebookID],
                      notebook.ownerDeviceID == intent.ownerDeviceID,
                      notebook.backingSessionID == intent.backingSessionID else {
                    throw RuntimeResearchNotebookStoreError.corruptPersistence
                }
            case .archive:
                _ = try mutateLifecycleLocked(
                    ownerDeviceID: intent.ownerDeviceID,
                    notebookID: intent.notebookID,
                    lifecycle: .archived
                )
            case .restore:
                _ = try mutateLifecycleLocked(
                    ownerDeviceID: intent.ownerDeviceID,
                    notebookID: intent.notebookID,
                    lifecycle: .active
                )
            case .delete:
                guard let notebook = notebooksByID[intent.notebookID],
                      notebook.ownerDeviceID == intent.ownerDeviceID,
                      notebook.backingSessionID == intent.backingSessionID else {
                    throw RuntimeResearchNotebookStoreError.corruptPersistence
                }
                notebooksByID.removeValue(forKey: intent.notebookID)
                notebookIDByOwnerSession.removeValue(forKey: OwnerSessionKey(
                    ownerDeviceID: intent.ownerDeviceID,
                    backingSessionID: intent.backingSessionID
                ))
            }
            lifecycleIntentsByNotebookID.removeValue(forKey: intent.notebookID)
        }
    }

    public func renewLifecycleMutation(
        _ intent: RuntimeResearchNotebookLifecycleIntent,
        leaseExpiresAt: Date
    ) throws -> RuntimeResearchNotebookLifecycleIntent {
        try runtimeResearchNotebookValidateLifecycleIntent(intent)
        try runtimeResearchNotebookValidateLifecycleIdentity(
            coordinatorID: intent.coordinatorID,
            operationID: intent.operationID,
            leaseExpiresAt: leaseExpiresAt
        )
        return try lock.withLock {
            guard lifecycleIntentsByNotebookID[intent.notebookID] == intent else {
                throw RuntimeResearchNotebookStoreError.storageFailure(
                    "The research notebook lifecycle intent is no longer owned by this operation."
                )
            }
            let renewed = RuntimeResearchNotebookLifecycleIntent(
                ownerDeviceID: intent.ownerDeviceID,
                notebookID: intent.notebookID,
                backingSessionID: intent.backingSessionID,
                mutation: intent.mutation,
                coordinatorID: intent.coordinatorID,
                operationID: intent.operationID,
                leaseExpiresAt: leaseExpiresAt
            )
            lifecycleIntentsByNotebookID[intent.notebookID] = renewed
            return renewed
        }
    }

    public func cancelLifecycleMutation(
        _ intent: RuntimeResearchNotebookLifecycleIntent
    ) throws {
        try runtimeResearchNotebookValidateLifecycleIntent(intent)
        try lock.withLock {
            guard let pending = lifecycleIntentsByNotebookID[intent.notebookID] else { return }
            guard pending == intent else {
                throw RuntimeResearchNotebookStoreError.corruptPersistence
            }
            if intent.mutation == .create {
                guard let notebook = notebooksByID[intent.notebookID],
                      notebook.ownerDeviceID == intent.ownerDeviceID,
                      notebook.backingSessionID == intent.backingSessionID else {
                    throw RuntimeResearchNotebookStoreError.corruptPersistence
                }
                notebooksByID.removeValue(forKey: intent.notebookID)
                notebookIDByOwnerSession.removeValue(forKey: OwnerSessionKey(
                    ownerDeviceID: intent.ownerDeviceID,
                    backingSessionID: intent.backingSessionID
                ))
            }
            lifecycleIntentsByNotebookID.removeValue(forKey: intent.notebookID)
        }
    }

    public func pendingLifecycleMutations(
        ownerDeviceID: String
    ) throws -> [RuntimeResearchNotebookLifecycleIntent] {
        try runtimeResearchNotebookValidateOwner(ownerDeviceID)
        return lock.withLock {
            lifecycleIntentsByNotebookID.values
                .filter { $0.ownerDeviceID == ownerDeviceID }
                .sorted {
                    if $0.backingSessionID != $1.backingSessionID {
                        return $0.backingSessionID.utf8.lexicographicallyPrecedes($1.backingSessionID.utf8)
                    }
                    return $0.notebookID.utf8.lexicographicallyPrecedes($1.notebookID.utf8)
                }
        }
    }

    private func mutateLifecycle(
        ownerDeviceID: String,
        notebookID: String,
        lifecycle: RuntimeResearchNotebookLifecycle
    ) throws -> RuntimeResearchNotebook? {
        try runtimeResearchNotebookValidateOwner(ownerDeviceID)
        try runtimeResearchNotebookValidateID(notebookID)
        return try lock.withLock {
            try mutateLifecycleLocked(
                ownerDeviceID: ownerDeviceID,
                notebookID: notebookID,
                lifecycle: lifecycle
            )
        }
    }

    private func createLocked(
        ownerDeviceID: String,
        notebookID: String,
        backingSessionID: String,
        title: String,
        model: String,
        promptSkillBinding: RuntimePromptSkillBinding,
        trustedSourceGrantIDs: [String]
    ) throws -> RuntimeResearchNotebook {
        guard notebooksByID[notebookID] == nil else {
            throw RuntimeResearchNotebookStoreError.notebookIDCollision
        }
        let ownerSessionKey = OwnerSessionKey(
            ownerDeviceID: ownerDeviceID,
            backingSessionID: backingSessionID
        )
        guard notebookIDByOwnerSession[ownerSessionKey] == nil else {
            throw RuntimeResearchNotebookStoreError.backingSessionIDCollision
        }
        guard notebooksByID.values.lazy.filter({ $0.ownerDeviceID == ownerDeviceID }).count
                < rowLimitPerOwner else {
            throw RuntimeResearchNotebookStoreError.rowLimitReached
        }
        let timestamp = now()
        let notebook = RuntimeResearchNotebook(
            notebookID: notebookID,
            ownerDeviceID: ownerDeviceID,
            backingSessionID: backingSessionID,
            title: title,
            model: model,
            promptSkillBinding: promptSkillBinding,
            trustedSourceGrantIDs: trustedSourceGrantIDs,
            lifecycle: .active,
            createdAt: timestamp,
            updatedAt: timestamp
        )
        try runtimeResearchNotebookValidate(notebook)
        notebooksByID[notebookID] = notebook
        notebookIDByOwnerSession[ownerSessionKey] = notebookID
        return notebook
    }

    private func mutateLifecycleLocked(
        ownerDeviceID: String,
        notebookID: String,
        lifecycle: RuntimeResearchNotebookLifecycle
    ) throws -> RuntimeResearchNotebook? {
        guard let current = notebooksByID[notebookID],
              current.ownerDeviceID == ownerDeviceID else {
            return nil
        }
        guard current.lifecycle != lifecycle else { return current }
        let timestamp = now()
        guard timestamp.timeIntervalSince1970.isFinite,
              timestamp >= current.updatedAt else {
            throw RuntimeResearchNotebookStoreError.invalidField("updated_at")
        }
        let updated = RuntimeResearchNotebook(
            notebookID: current.notebookID,
            ownerDeviceID: current.ownerDeviceID,
            backingSessionID: current.backingSessionID,
            title: current.title,
            model: current.model,
            promptSkillBinding: current.promptSkillBinding,
            trustedSourceGrantIDs: current.trustedSourceGrantIDs,
            lifecycle: lifecycle,
            createdAt: current.createdAt,
            updatedAt: timestamp
        )
        notebooksByID[notebookID] = updated
        return updated
    }

    private func validateCompletedLifecycleIntentLocked(
        _ intent: RuntimeResearchNotebookLifecycleIntent
    ) throws {
        guard let notebook = notebooksByID[intent.notebookID] else {
            guard intent.mutation == .delete else {
                throw RuntimeResearchNotebookStoreError.corruptPersistence
            }
            return
        }
        guard notebook.ownerDeviceID == intent.ownerDeviceID,
              notebook.backingSessionID == intent.backingSessionID else {
            throw RuntimeResearchNotebookStoreError.corruptPersistence
        }
        switch intent.mutation {
        case .create:
            guard notebook.lifecycle == .active else {
                throw RuntimeResearchNotebookStoreError.corruptPersistence
            }
        case .archive:
            guard notebook.lifecycle == .archived else {
                throw RuntimeResearchNotebookStoreError.corruptPersistence
            }
        case .restore:
            guard notebook.lifecycle == .active else {
                throw RuntimeResearchNotebookStoreError.corruptPersistence
            }
        case .delete:
            throw RuntimeResearchNotebookStoreError.corruptPersistence
        }
    }
}

func runtimeResearchNotebookValidateLifecycleIntent(
    _ intent: RuntimeResearchNotebookLifecycleIntent
) throws {
    try runtimeResearchNotebookValidateOwner(intent.ownerDeviceID)
    try runtimeResearchNotebookValidateID(intent.notebookID)
    try runtimeResearchNotebookValidateBackingSessionID(intent.backingSessionID)
    try runtimeResearchNotebookValidateLifecycleIdentity(
        coordinatorID: intent.coordinatorID,
        operationID: intent.operationID,
        leaseExpiresAt: intent.leaseExpiresAt
    )
}

func runtimeResearchNotebookValidateLifecycleIdentity(
    coordinatorID: String,
    operationID: String,
    leaseExpiresAt: Date
) throws {
    let isLowercaseHex32: (String) -> Bool = { value in
        value.utf8.count == 32 && value.utf8.allSatisfy { byte in
            (48...57).contains(byte) || (97...102).contains(byte)
        }
    }
    guard isLowercaseHex32(coordinatorID),
          isLowercaseHex32(operationID),
          leaseExpiresAt.timeIntervalSince1970.isFinite else {
        throw RuntimeResearchNotebookStoreError.invalidField("lifecycle_intent")
    }
}

func runtimeResearchNotebookValidate(_ notebook: RuntimeResearchNotebook) throws {
    try runtimeResearchNotebookValidateCreateFields(
        ownerDeviceID: notebook.ownerDeviceID,
        notebookID: notebook.notebookID,
        backingSessionID: notebook.backingSessionID,
        title: notebook.title,
        model: notebook.model,
        promptSkillBinding: notebook.promptSkillBinding,
        trustedSourceGrantIDs: notebook.trustedSourceGrantIDs
    )
    guard notebook.createdAt.timeIntervalSince1970.isFinite,
          notebook.updatedAt.timeIntervalSince1970.isFinite,
          notebook.updatedAt >= notebook.createdAt else {
        throw RuntimeResearchNotebookStoreError.invalidField("timestamps")
    }
}

func runtimeResearchNotebookValidateCreateFields(
    ownerDeviceID: String,
    notebookID: String,
    backingSessionID: String,
    title: String,
    model: String,
    promptSkillBinding: RuntimePromptSkillBinding,
    trustedSourceGrantIDs: [String]
) throws {
    try runtimeResearchNotebookValidateID(notebookID)
    try runtimeResearchNotebookValidateOwner(ownerDeviceID)
    try runtimeResearchNotebookValidateBackingSessionID(backingSessionID)
    try runtimeResearchNotebookValidateCanonicalString(
        title,
        maximumUTF8Bytes: RuntimeResearchNotebook.maximumTitleUTF8Bytes,
        maximumCharacters: RuntimeResearchNotebook.maximumTitleCharacters,
        field: "title"
    )
    try runtimeResearchNotebookValidateCanonicalString(
        model,
        maximumUTF8Bytes: RuntimeResearchNotebook.maximumModelUTF8Bytes,
        maximumCharacters: RuntimeResearchNotebook.maximumModelCharacters,
        field: "model"
    )
    guard (try? RuntimePromptSkillBinding(
        identifier: promptSkillBinding.identifier,
        revision: promptSkillBinding.revision
    )) == promptSkillBinding else {
        throw RuntimeResearchNotebookStoreError.invalidField("prompt_skill_binding")
    }
    guard (1...RuntimeResearchNotebook.maximumTrustedSourceGrantCount)
        .contains(trustedSourceGrantIDs.count),
        Set(trustedSourceGrantIDs).count == trustedSourceGrantIDs.count,
        trustedSourceGrantIDs.allSatisfy(RuntimeResearchNotebook.isCanonicalTrustedSourceGrantID)
    else {
        throw RuntimeResearchNotebookStoreError.invalidField("trusted_source_grant_ids")
    }
}

func runtimeResearchNotebookValidateOwner(_ ownerDeviceID: String) throws {
    try runtimeResearchNotebookValidateCanonicalString(
        ownerDeviceID,
        maximumUTF8Bytes: RuntimeResearchNotebook.maximumOwnerDeviceIDUTF8Bytes,
        field: "owner_device_id"
    )
}

func runtimeResearchNotebookValidateBackingSessionID(_ backingSessionID: String) throws {
    try runtimeResearchNotebookValidateCanonicalString(
        backingSessionID,
        maximumUTF8Bytes: RuntimeResearchNotebook.maximumBackingSessionIDUTF8Bytes,
        maximumCharacters: RuntimeResearchNotebook.maximumBackingSessionIDCharacters,
        field: "backing_session_id"
    )
}

func runtimeResearchNotebookValidateID(_ notebookID: String) throws {
    guard RuntimeResearchNotebook.isCanonicalNotebookID(notebookID) else {
        throw RuntimeResearchNotebookStoreError.invalidField("notebook_id")
    }
}

func runtimeResearchNotebookValidateListLimit(_ limit: Int) throws {
    guard (1...RuntimeResearchNotebook.maximumStoreListLimit).contains(limit) else {
        throw RuntimeResearchNotebookStoreError.invalidField("limit")
    }
}

private func runtimeResearchNotebookValidateCanonicalString(
    _ value: String,
    maximumUTF8Bytes: Int,
    maximumCharacters: Int? = nil,
    field: String
) throws {
    guard !value.isEmpty,
          value == value.trimmingCharacters(in: .whitespacesAndNewlines),
          value.utf8.elementsEqual(value.precomposedStringWithCanonicalMapping.utf8),
          value.utf8.count <= maximumUTF8Bytes,
          maximumCharacters.map({ value.unicodeScalars.count <= $0 }) ?? true,
          value.unicodeScalars.allSatisfy({ !CharacterSet.controlCharacters.contains($0) }) else {
        throw RuntimeResearchNotebookStoreError.invalidField(field)
    }
}

func runtimeResearchNotebookPrecedes(
    _ lhs: RuntimeResearchNotebook,
    _ rhs: RuntimeResearchNotebook
) -> Bool {
    if lhs.updatedAt != rhs.updatedAt {
        return lhs.updatedAt > rhs.updatedAt
    }
    return lhs.notebookID.utf8.lexicographicallyPrecedes(rhs.notebookID.utf8)
}

private func isCanonicalPrefixedHexID(_ value: String, prefix: String) -> Bool {
    guard value.utf8.count == prefix.utf8.count + 32,
          value.hasPrefix(prefix) else {
        return false
    }
    return value.utf8.dropFirst(prefix.utf8.count).allSatisfy {
        ($0 >= 48 && $0 <= 57) || ($0 >= 97 && $0 <= 102)
    }
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
