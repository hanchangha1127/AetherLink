import CryptoKit
import XCTest
@testable import CompanionCore

final class RuntimeResearchNotebookPaginationTests: XCTestCase {
    func testPaginatesStable201ItemSnapshotAs100100And1() throws {
        let pagination = RuntimeResearchNotebookPagination(
            authenticationKey: SymmetricKey(data: Data(repeating: 0x11, count: 32)),
            monotonicNow: { 10 }
        )
        let connectionID = UUID()
        let notebooks = (0..<201).map(makeItem)

        let first = try pagination.createSnapshot(
            connectionID: connectionID,
            ownerDeviceID: "owner-a",
            context: RuntimeResearchNotebookSnapshotContext(includeArchived: true),
            notebooks: notebooks,
            pageLimit: 100,
            now: Date(timeIntervalSince1970: 1_000)
        )
        XCTAssertEqual(first.notebooks.count, 100)
        XCTAssertEqual(first.snapshotCount, 201)
        XCTAssertLessThanOrEqual(try XCTUnwrap(first.nextCursor).utf8.count, 512)

        let second = try pagination.continueSnapshot(
            cursor: try XCTUnwrap(first.nextCursor),
            connectionID: connectionID,
            ownerDeviceID: "owner-a",
            now: Date(timeIntervalSince1970: 1_001)
        )
        XCTAssertEqual(second.notebooks.count, 100)
        XCTAssertEqual(second.snapshotCount, 201)

        let third = try pagination.continueSnapshot(
            cursor: try XCTUnwrap(second.nextCursor),
            connectionID: connectionID,
            ownerDeviceID: "owner-a",
            now: Date(timeIntervalSince1970: 1_002)
        )
        XCTAssertEqual(third.notebooks.count, 1)
        XCTAssertEqual(third.snapshotCount, 201)
        XCTAssertNil(third.nextCursor)
        XCTAssertEqual(
            (first.notebooks + second.notebooks + third.notebooks).map(\.notebook.notebookID),
            notebooks.map(\.notebook.notebookID)
        )
    }

    func testRejectsCursorTamperingAndConnectionOwnerContextCountLimitAndOffsetDrift() throws {
        let pagination = RuntimeResearchNotebookPagination(
            authenticationKey: SymmetricKey(data: Data(repeating: 0x22, count: 32)),
            monotonicNow: { 20 }
        )
        let connectionID = UUID()
        let page = try pagination.createSnapshot(
            connectionID: connectionID,
            ownerDeviceID: "owner-a",
            context: RuntimeResearchNotebookSnapshotContext(includeArchived: false),
            notebooks: (0..<5).map(makeItem),
            pageLimit: 2,
            now: Date(timeIntervalSince1970: 2_000)
        )
        let cursor = try XCTUnwrap(page.nextCursor)

        assertInvalidCursor(
            cursor: replacingCursorField(cursor, at: 2, with: "1"),
            pagination: pagination,
            connectionID: connectionID,
            ownerDeviceID: "owner-a"
        )
        assertInvalidCursor(
            cursor: replacingCursorField(cursor, at: 3, with: "3"),
            pagination: pagination,
            connectionID: connectionID,
            ownerDeviceID: "owner-a"
        )
        assertInvalidCursor(
            cursor: replacingCursorField(cursor, at: 4, with: "4"),
            pagination: pagination,
            connectionID: connectionID,
            ownerDeviceID: "owner-a"
        )
        assertInvalidCursor(
            cursor: replacingCursorField(cursor, at: 5, with: "4"),
            pagination: pagination,
            connectionID: connectionID,
            ownerDeviceID: "owner-a"
        )
        let tamperedMAC = String(cursor.dropLast()) + (cursor.last == "0" ? "1" : "0")
        assertInvalidCursor(
            cursor: tamperedMAC,
            pagination: pagination,
            connectionID: connectionID,
            ownerDeviceID: "owner-a"
        )
        assertInvalidCursor(
            cursor: cursor,
            pagination: pagination,
            connectionID: UUID(),
            ownerDeviceID: "owner-a"
        )
        assertInvalidCursor(
            cursor: cursor,
            pagination: pagination,
            connectionID: connectionID,
            ownerDeviceID: "owner-b"
        )
        assertInvalidCursor(
            cursor: String(repeating: "x", count: 513),
            pagination: pagination,
            connectionID: connectionID,
            ownerDeviceID: "owner-a"
        )
    }

    func testRejectsWallAndMonotonicExpiryAndInvalidatedSnapshots() throws {
        let clock = RuntimeResearchNotebookPaginationTestClock(100)
        let pagination = RuntimeResearchNotebookPagination(
            authenticationKey: SymmetricKey(data: Data(repeating: 0x33, count: 32)),
            monotonicNow: { clock.value }
        )
        let connectionID = UUID()
        let wallExpired = try pagination.createSnapshot(
            connectionID: connectionID,
            ownerDeviceID: "owner-a",
            context: RuntimeResearchNotebookSnapshotContext(includeArchived: true),
            notebooks: (0..<3).map(makeItem),
            pageLimit: 1,
            now: Date(timeIntervalSince1970: 3_000)
        )
        assertInvalidCursor(
            cursor: try XCTUnwrap(wallExpired.nextCursor),
            pagination: pagination,
            connectionID: connectionID,
            ownerDeviceID: "owner-a",
            now: Date(timeIntervalSince1970: 3_120)
        )

        let monotonicExpired = try pagination.createSnapshot(
            connectionID: connectionID,
            ownerDeviceID: "owner-a",
            context: RuntimeResearchNotebookSnapshotContext(includeArchived: true),
            notebooks: (0..<3).map(makeItem),
            pageLimit: 1,
            now: Date(timeIntervalSince1970: 4_000)
        )
        clock.value = 220
        assertInvalidCursor(
            cursor: try XCTUnwrap(monotonicExpired.nextCursor),
            pagination: pagination,
            connectionID: connectionID,
            ownerDeviceID: "owner-a",
            now: Date(timeIntervalSince1970: 4_001)
        )

        clock.value = 300
        let ownerInvalidated = try pagination.createSnapshot(
            connectionID: connectionID,
            ownerDeviceID: "owner-a",
            context: RuntimeResearchNotebookSnapshotContext(includeArchived: false),
            notebooks: (0..<3).map(makeItem),
            pageLimit: 1,
            now: Date(timeIntervalSince1970: 5_000)
        )
        pagination.invalidateOwner("owner-a")
        assertInvalidCursor(
            cursor: try XCTUnwrap(ownerInvalidated.nextCursor),
            pagination: pagination,
            connectionID: connectionID,
            ownerDeviceID: "owner-a",
            now: Date(timeIntervalSince1970: 5_001)
        )

        let connectionInvalidated = try pagination.createSnapshot(
            connectionID: connectionID,
            ownerDeviceID: "owner-a",
            context: RuntimeResearchNotebookSnapshotContext(includeArchived: false),
            notebooks: (0..<3).map(makeItem),
            pageLimit: 1,
            now: Date(timeIntervalSince1970: 6_000)
        )
        pagination.clearConnection(connectionID)
        assertInvalidCursor(
            cursor: try XCTUnwrap(connectionInvalidated.nextCursor),
            pagination: pagination,
            connectionID: connectionID,
            ownerDeviceID: "owner-a",
            now: Date(timeIntervalSince1970: 6_001)
        )
    }

    func testEnforcesSnapshotBoundsAndOneSnapshotPerConnection() throws {
        let pagination = RuntimeResearchNotebookPagination(
            authenticationKey: SymmetricKey(data: Data(repeating: 0x44, count: 32)),
            monotonicNow: { 400 }
        )
        let connectionID = UUID()
        let first = try pagination.createSnapshot(
            connectionID: connectionID,
            ownerDeviceID: "owner-a",
            context: RuntimeResearchNotebookSnapshotContext(includeArchived: false),
            notebooks: (0..<3).map(makeItem),
            pageLimit: 1,
            now: Date(timeIntervalSince1970: 7_000)
        )
        _ = try pagination.createSnapshot(
            connectionID: connectionID,
            ownerDeviceID: "owner-a",
            context: RuntimeResearchNotebookSnapshotContext(includeArchived: true),
            notebooks: (0..<4).map(makeItem),
            pageLimit: 2,
            now: Date(timeIntervalSince1970: 7_001)
        )
        assertInvalidCursor(
            cursor: try XCTUnwrap(first.nextCursor),
            pagination: pagination,
            connectionID: connectionID,
            ownerDeviceID: "owner-a",
            now: Date(timeIntervalSince1970: 7_002)
        )

        XCTAssertThrowsError(try pagination.createSnapshot(
            connectionID: UUID(),
            ownerDeviceID: "owner-a",
            context: RuntimeResearchNotebookSnapshotContext(includeArchived: false),
            notebooks: Array(repeating: makeItem(0), count: 10_001),
            pageLimit: 200,
            now: Date(timeIntervalSince1970: 7_003)
        )) { error in
            guard case RuntimeResearchNotebookPaginationError.snapshotLimitExceeded = error else {
                return XCTFail("Expected snapshotLimitExceeded, got \(error)")
            }
        }
    }

    func testNinthGlobalSnapshotEvictsOnlyTheOldestSnapshot() throws {
        let pagination = RuntimeResearchNotebookPagination(
            authenticationKey: SymmetricKey(data: Data(repeating: 0x55, count: 32)),
            monotonicNow: { 500 }
        )
        let connections = (0..<9).map { _ in UUID() }
        var cursors: [String] = []
        for (index, connectionID) in connections.enumerated() {
            let page = try pagination.createSnapshot(
                connectionID: connectionID,
                ownerDeviceID: "owner-a",
                context: RuntimeResearchNotebookSnapshotContext(includeArchived: false),
                notebooks: (0..<3).map(makeItem),
                pageLimit: 1,
                now: Date(timeIntervalSince1970: TimeInterval(8_000 + index))
            )
            cursors.append(try XCTUnwrap(page.nextCursor))
        }

        assertInvalidCursor(
            cursor: cursors[0],
            pagination: pagination,
            connectionID: connections[0],
            ownerDeviceID: "owner-a",
            now: Date(timeIntervalSince1970: 8_010)
        )
        let survivingPage = try pagination.continueSnapshot(
            cursor: cursors[1],
            connectionID: connections[1],
            ownerDeviceID: "owner-a",
            now: Date(timeIntervalSince1970: 8_010)
        )
        XCTAssertEqual(survivingPage.notebooks.count, 1)
        XCTAssertEqual(survivingPage.snapshotCount, 3)
    }
}

private func makeItem(_ index: Int) -> RuntimeResearchNotebookSnapshotItem {
    let timestamp = Date(timeIntervalSince1970: TimeInterval(10_000 - index))
    return RuntimeResearchNotebookSnapshotItem(
        notebook: RuntimeResearchNotebook(
            notebookID: "research_notebook_" + String(format: "%032x", index),
            ownerDeviceID: "owner-a",
            backingSessionID: "session-\(index)",
            title: "Notebook \(index)",
            model: "llama3.1:8b",
            promptSkillBinding: RuntimePromptSkillRegistry.researchBriefBinding,
            trustedSourceGrantIDs: [],
            lifecycle: .active,
            createdAt: timestamp,
            updatedAt: timestamp
        ),
        archivedAt: nil,
        updatedAt: timestamp
    )
}

private func replacingCursorField(_ cursor: String, at index: Int, with value: String) -> String {
    var fields = cursor.split(separator: ".", omittingEmptySubsequences: false).map(String.init)
    fields[index] = value
    return fields.joined(separator: ".")
}

private func assertInvalidCursor(
    cursor: String,
    pagination: RuntimeResearchNotebookPagination,
    connectionID: UUID,
    ownerDeviceID: String,
    now: Date = Date(timeIntervalSince1970: 2_001),
    file: StaticString = #filePath,
    line: UInt = #line
) {
    XCTAssertThrowsError(try pagination.continueSnapshot(
        cursor: cursor,
        connectionID: connectionID,
        ownerDeviceID: ownerDeviceID,
        now: now
    ), file: file, line: line) { error in
        guard case RuntimeResearchNotebookPaginationError.invalidCursor = error else {
            return XCTFail("Expected invalidCursor, got \(error)", file: file, line: line)
        }
    }
}

private final class RuntimeResearchNotebookPaginationTestClock: @unchecked Sendable {
    private let lock = NSLock()
    private var storedValue: TimeInterval

    init(_ value: TimeInterval) {
        storedValue = value
    }

    var value: TimeInterval {
        get { lock.withLock { storedValue } }
        set { lock.withLock { storedValue = newValue } }
    }
}
