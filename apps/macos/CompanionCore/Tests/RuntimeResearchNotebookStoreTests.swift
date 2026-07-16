import Foundation
@testable import CompanionCore
import XCTest

final class RuntimeResearchNotebookStoreTests: XCTestCase {
    func testCanonicalIDsAndSwiftAPIBoundsFailClosed() throws {
        XCTAssertTrue(RuntimeResearchNotebook.isCanonicalNotebookID(notebookID("a")))
        XCTAssertFalse(RuntimeResearchNotebook.isCanonicalNotebookID("research_notebook_" + String(repeating: "A", count: 32)))
        XCTAssertFalse(RuntimeResearchNotebook.isCanonicalNotebookID("research_notebook_" + String(repeating: "a", count: 31)))
        XCTAssertTrue(RuntimeResearchNotebook.isCanonicalTrustedSourceGrantID(grantID("b")))
        XCTAssertFalse(RuntimeResearchNotebook.isCanonicalTrustedSourceGrantID("trusted_source_" + String(repeating: "g", count: 32)))

        let store = RuntimeResearchNotebookStore(now: { Date(timeIntervalSince1970: 100) })
        let maximum = try store.create(
            ownerDeviceID: String(repeating: "o", count: RuntimeResearchNotebook.maximumOwnerDeviceIDUTF8Bytes),
            notebookID: notebookID("1"),
            backingSessionID: String(repeating: "s", count: RuntimeResearchNotebook.maximumBackingSessionIDCharacters),
            title: String(repeating: "t", count: RuntimeResearchNotebook.maximumTitleCharacters),
            model: String(repeating: "m", count: RuntimeResearchNotebook.maximumModelCharacters),
            promptSkillBinding: RuntimePromptSkillRegistry.researchBriefBinding,
            trustedSourceGrantIDs: (0..<8).map { grantID(String(format: "%x", $0)) }
        )
        XCTAssertEqual(maximum.trustedSourceGrantIDs.count, 8)
        XCTAssertEqual(maximum.promptSkillBinding, RuntimePromptSkillRegistry.researchBriefBinding)
        let existentialStore: any RuntimeResearchNotebookStoring = store
        XCTAssertEqual(try existentialStore.list(ownerDeviceID: maximum.ownerDeviceID), [maximum])

        let invalidCreates: [() throws -> Void] = [
            { _ = try store.create(ownerDeviceID: " owner", notebookID: self.notebookID("2"), backingSessionID: "session", title: "title", model: "model", promptSkillBinding: RuntimePromptSkillRegistry.researchBriefBinding, trustedSourceGrantIDs: [self.grantID("1")]) },
            { _ = try store.create(ownerDeviceID: "owner", notebookID: self.notebookID("2"), backingSessionID: "session\ninternal", title: "title", model: "model", promptSkillBinding: RuntimePromptSkillRegistry.researchBriefBinding, trustedSourceGrantIDs: [self.grantID("1")]) },
            { _ = try store.create(ownerDeviceID: "owner", notebookID: self.notebookID("2"), backingSessionID: "session", title: "e\u{301}", model: "model", promptSkillBinding: RuntimePromptSkillRegistry.researchBriefBinding, trustedSourceGrantIDs: [self.grantID("1")]) },
            { _ = try store.create(ownerDeviceID: "owner", notebookID: self.notebookID("2"), backingSessionID: "session", title: String(repeating: "x", count: RuntimeResearchNotebook.maximumTitleCharacters + 1), model: "model", promptSkillBinding: RuntimePromptSkillRegistry.researchBriefBinding, trustedSourceGrantIDs: [self.grantID("1")]) },
            { _ = try store.create(ownerDeviceID: "owner", notebookID: self.notebookID("2"), backingSessionID: "session", title: "title", model: "model", promptSkillBinding: RuntimePromptSkillRegistry.researchBriefBinding, trustedSourceGrantIDs: []) },
            { _ = try store.create(ownerDeviceID: "owner", notebookID: self.notebookID("2"), backingSessionID: "session", title: "title", model: "model", promptSkillBinding: RuntimePromptSkillRegistry.researchBriefBinding, trustedSourceGrantIDs: [self.grantID("1"), self.grantID("1")]) },
            { _ = try store.create(ownerDeviceID: "owner", notebookID: self.notebookID("2"), backingSessionID: "session", title: "title", model: "model", promptSkillBinding: RuntimePromptSkillRegistry.researchBriefBinding, trustedSourceGrantIDs: (0..<9).map { self.grantID(String(format: "%x", $0)) }) },
        ]
        for (index, create) in invalidCreates.enumerated() {
            XCTAssertThrowsError(try create(), "Invalid create case \(index) was accepted") { error in
                guard case RuntimeResearchNotebookStoreError.invalidField = error else {
                    return XCTFail("Unexpected error: \(error)")
                }
            }
        }
        XCTAssertThrowsError(try store.list(ownerDeviceID: maximum.ownerDeviceID, limit: 0))
        XCTAssertEqual(try store.list(ownerDeviceID: maximum.ownerDeviceID, limit: 101), [maximum])
        XCTAssertThrowsError(
            try store.list(
                ownerDeviceID: maximum.ownerDeviceID,
                limit: RuntimeResearchNotebook.maximumStoreListLimit + 1
            )
        )
    }

    func testOwnerIsolationAndStrictNotebookSessionAndGrantDuplicates() throws {
        let store = RuntimeResearchNotebookStore(now: { Date(timeIntervalSince1970: 100) })
        let first = try create(store, owner: "owner-a", notebook: "1", session: "session-a")

        XCTAssertThrowsError(try create(store, owner: "owner-b", notebook: "1", session: "session-b")) {
            XCTAssertEqual($0 as? RuntimeResearchNotebookStoreError, .notebookIDCollision)
        }
        XCTAssertThrowsError(try create(store, owner: "owner-a", notebook: "2", session: "session-a")) {
            XCTAssertEqual($0 as? RuntimeResearchNotebookStoreError, .backingSessionIDCollision)
        }
        let otherOwner = try create(store, owner: "owner-b", notebook: "2", session: "session-a")

        XCTAssertNil(try store.get(ownerDeviceID: "owner-b", notebookID: first.notebookID))
        XCTAssertNil(try store.getByBackingSessionID(ownerDeviceID: "owner-a", backingSessionID: "session-b"))
        XCTAssertNil(try store.archive(ownerDeviceID: "owner-b", notebookID: first.notebookID))
        XCTAssertNil(try store.restore(ownerDeviceID: "owner-b", notebookID: first.notebookID))
        XCTAssertFalse(try store.delete(ownerDeviceID: "owner-b", notebookID: first.notebookID))
        XCTAssertEqual(try store.get(ownerDeviceID: "owner-a", notebookID: first.notebookID), first)
        XCTAssertEqual(try store.getByBackingSessionID(ownerDeviceID: "owner-b", backingSessionID: "session-a"), otherOwner)
    }

    func testArchiveRestoreAreIdempotentAndUpdateTimestampsOnlyOnTransitions() throws {
        let clock = TestNotebookClock([100, 200, 300])
        let store = RuntimeResearchNotebookStore(now: { clock.now() })
        let created = try create(store, owner: "owner", notebook: "1", session: "session")
        let archived = try XCTUnwrap(try store.archive(ownerDeviceID: "owner", notebookID: created.notebookID))
        let archivedAgain = try XCTUnwrap(try store.archive(ownerDeviceID: "owner", notebookID: created.notebookID))
        let restored = try XCTUnwrap(try store.restore(ownerDeviceID: "owner", notebookID: created.notebookID))
        let restoredAgain = try XCTUnwrap(try store.restore(ownerDeviceID: "owner", notebookID: created.notebookID))

        XCTAssertEqual(created.createdAt, Date(timeIntervalSince1970: 100))
        XCTAssertEqual(created.updatedAt, created.createdAt)
        XCTAssertEqual(archived.lifecycle, .archived)
        XCTAssertEqual(archived.promptSkillBinding, created.promptSkillBinding)
        XCTAssertEqual(archived.updatedAt, Date(timeIntervalSince1970: 200))
        XCTAssertEqual(archivedAgain, archived)
        XCTAssertEqual(restored.lifecycle, .active)
        XCTAssertEqual(restored.promptSkillBinding, created.promptSkillBinding)
        XCTAssertEqual(restored.updatedAt, Date(timeIntervalSince1970: 300))
        XCTAssertEqual(restoredAgain, restored)
        XCTAssertEqual(clock.readCount, 3)
    }

    func testOrderingFiltersLimitsDeleteAndRowBound() throws {
        let clock = TestNotebookClock([100, 200, 200, 300])
        let store = RuntimeResearchNotebookStore(rowLimitPerOwner: 3, now: { clock.now() })
        let first = try create(store, owner: "owner", notebook: "3", session: "session-3")
        let second = try create(store, owner: "owner", notebook: "2", session: "session-2")
        let third = try create(store, owner: "owner", notebook: "1", session: "session-1")

        XCTAssertEqual(
            try store.list(ownerDeviceID: "owner", limit: 2).map(\.notebookID),
            [third.notebookID, second.notebookID]
        )
        let archived = try XCTUnwrap(try store.archive(ownerDeviceID: "owner", notebookID: first.notebookID))
        XCTAssertEqual(try store.list(ownerDeviceID: "owner", lifecycle: .archived).map(\.notebookID), [archived.notebookID])
        XCTAssertEqual(try store.list(ownerDeviceID: "owner", lifecycle: .active).map(\.notebookID), [third.notebookID, second.notebookID])
        XCTAssertThrowsError(try create(store, owner: "owner", notebook: "4", session: "session-4")) {
            XCTAssertEqual($0 as? RuntimeResearchNotebookStoreError, .rowLimitReached)
        }

        XCTAssertTrue(try store.delete(ownerDeviceID: "owner", notebookID: second.notebookID))
        XCTAssertFalse(try store.delete(ownerDeviceID: "owner", notebookID: second.notebookID))
        XCTAssertNil(try store.get(ownerDeviceID: "owner", notebookID: second.notebookID))
        let reused = try create(store, owner: "owner", notebook: "4", session: "session-2")
        XCTAssertEqual(try store.getByBackingSessionID(ownerDeviceID: "owner", backingSessionID: "session-2"), reused)
    }

    func testLifecycleIntentRenewalIsAtomicAndFencesLostOwnership() throws {
        let store = RuntimeResearchNotebookStore(now: { Date(timeIntervalSince1970: 10) })
        _ = try create(store, owner: "owner", notebook: "1", session: "session")
        let original = try XCTUnwrap(try store.prepareLifecycleMutation(
            ownerDeviceID: "owner",
            backingSessionID: "session",
            mutation: .archive,
            coordinatorID: String(repeating: "a", count: 32),
            operationID: String(repeating: "b", count: 32),
            leaseExpiresAt: Date(timeIntervalSince1970: 100)
        ))
        let renewed = try store.renewLifecycleMutation(
            original,
            leaseExpiresAt: Date(timeIntervalSince1970: 200)
        )
        XCTAssertEqual(renewed.leaseExpiresAt, Date(timeIntervalSince1970: 200))
        XCTAssertEqual(try store.pendingLifecycleMutations(ownerDeviceID: "owner"), [renewed])

        try store.cancelLifecycleMutation(renewed)
        let takeover = try XCTUnwrap(try store.prepareLifecycleMutation(
            ownerDeviceID: "owner",
            backingSessionID: "session",
            mutation: .archive,
            coordinatorID: String(repeating: "c", count: 32),
            operationID: String(repeating: "d", count: 32),
            leaseExpiresAt: Date(timeIntervalSince1970: 300)
        ))
        XCTAssertThrowsError(try store.renewLifecycleMutation(
            original,
            leaseExpiresAt: Date(timeIntervalSince1970: 400)
        )) { error in
            guard case RuntimeResearchNotebookStoreError.storageFailure = error else {
                return XCTFail("Expected lost-ownership fencing, got \(error)")
            }
        }
        XCTAssertEqual(try store.pendingLifecycleMutations(ownerDeviceID: "owner"), [takeover])
    }

    private func create(
        _ store: RuntimeResearchNotebookStore,
        owner: String,
        notebook: String,
        session: String
    ) throws -> RuntimeResearchNotebook {
        try store.create(
            ownerDeviceID: owner,
            notebookID: notebookID(notebook),
            backingSessionID: session,
            title: "Research title \(notebook)",
            model: "ollama:model-\(notebook)",
            promptSkillBinding: RuntimePromptSkillRegistry.researchBriefBinding,
            trustedSourceGrantIDs: [grantID(notebook)]
        )
    }

    private func notebookID(_ digit: String) -> String {
        "research_notebook_" + String(repeating: "0", count: 32 - digit.count) + digit
    }

    private func grantID(_ digit: String) -> String {
        "trusted_source_" + String(repeating: "0", count: 32 - digit.count) + digit
    }
}

private final class TestNotebookClock: @unchecked Sendable {
    private let lock = NSLock()
    private let timestamps: [TimeInterval]
    private var index = 0

    init(_ timestamps: [TimeInterval]) {
        self.timestamps = timestamps
    }

    var readCount: Int {
        lock.lock()
        defer { lock.unlock() }
        return index
    }

    func now() -> Date {
        lock.lock()
        defer { lock.unlock() }
        let timestamp = timestamps[min(index, timestamps.count - 1)]
        index += 1
        return Date(timeIntervalSince1970: timestamp)
    }
}
