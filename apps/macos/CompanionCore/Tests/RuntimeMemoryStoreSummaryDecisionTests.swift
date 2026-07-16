import Foundation
import XCTest
@testable import CompanionCore

final class RuntimeMemoryStoreSummaryDecisionTests: XCTestCase {
    func testConcurrentCrossInstanceApproveAndDismissCommitOneTerminalDecision() async throws {
        let fileURL = try temporaryStoreURL()
        let approveStore = JSONLRuntimeMemoryStore(fileURL: fileURL)
        let dismissStore = JSONLRuntimeMemoryStore(fileURL: fileURL)
        let draftID = "long-inactivity:v2:concurrent-terminal-decision"
        let entryID = "memory-summary:\(draftID)"
        let source = memorySummarySource(draftID: draftID)
        let ready = DispatchSemaphore(value: 0)
        let start = DispatchSemaphore(value: 0)

        async let approveOutcome = Self.runDecision(ready: ready, start: start) {
            _ = try approveStore.approveMemorySummaryDraft(
                ownerDeviceID: "device-a",
                draftID: draftID,
                id: entryID,
                content: "Approved content",
                enabled: true,
                source: source,
                timestamp: Date(timeIntervalSince1970: 100)
            )
            return .approved
        }
        async let dismissOutcome = Self.runDecision(ready: ready, start: start) {
            _ = try dismissStore.dismissMemorySummaryDraft(
                ownerDeviceID: "device-a",
                draftID: draftID,
                timestamp: Date(timeIntervalSince1970: 101)
            )
            return .dismissed
        }

        XCTAssertEqual(ready.wait(timeout: .now() + 1), .success)
        XCTAssertEqual(ready.wait(timeout: .now() + 1), .success)
        start.signal()
        start.signal()

        let outcomes = [await approveOutcome, await dismissOutcome]
        XCTAssertEqual(outcomes.filter(\.isCommitted).count, 1)
        XCTAssertEqual(outcomes.filter { $0 == .conflict }.count, 1)

        let reloadedStore = JSONLRuntimeMemoryStore(fileURL: fileURL)
        let entries = try reloadedStore.list(ownerDeviceID: "device-a")
        let dismissedIDs = try reloadedStore.dismissedMemorySummaryDraftIDs(
            ownerDeviceID: "device-a"
        )
        XCTAssertEqual(entries.count + dismissedIDs.count, 1)
        XCTAssertEqual(try nonEmptyJSONLLines(at: fileURL).count, 1)
    }

    func testCrossProcessDismissLinearizesBeforeWaitingApproval() throws {
        let fileURL = try temporaryStoreURL()
        let draftID = "long-inactivity:v2:cross-process-terminal-decision"
        let source = memorySummarySource(draftID: draftID)
        let lockURL = fileURL.deletingLastPathComponent().appendingPathComponent(
            ".\(fileURL.lastPathComponent).coordination.lock"
        )
        try RuntimeEventLogFileProtection.withExclusiveFileAccess(to: fileURL) {}

        let process = Process()
        let input = Pipe()
        let output = Pipe()
        let errors = Pipe()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        process.arguments = [
            "-c",
            """
            import fcntl, json, os, sys
            lock_path, event_path, draft_id = sys.argv[1:]
            descriptor = os.open(lock_path, os.O_RDWR)
            fcntl.lockf(descriptor, fcntl.LOCK_EX)
            sys.stdout.write("READY\\n")
            sys.stdout.flush()
            sys.stdin.readline()
            event = {
                "id": draft_id,
                "kind": "dismiss_memory_summary_draft",
                "owner_device_id": "device-a",
                "timestamp": "1970-01-01T00:10:00Z",
            }
            with open(event_path, "ab", buffering=0) as event_file:
                event_file.write((json.dumps(event, separators=(",", ":"), sort_keys=True) + "\\n").encode())
                os.fsync(event_file.fileno())
            fcntl.lockf(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)
            """,
            lockURL.path,
            fileURL.path,
            draftID,
        ]
        process.standardInput = input
        process.standardOutput = output
        process.standardError = errors
        try process.run()
        defer {
            if process.isRunning {
                try? input.fileHandleForWriting.write(contentsOf: Data([0x0A]))
                process.terminate()
                process.waitUntilExit()
            }
        }
        XCTAssertEqual(
            String(data: output.fileHandleForReading.readData(ofLength: 6), encoding: .utf8),
            "READY\n"
        )

        let approvalCompleted = DispatchSemaphore(value: 0)
        let approvalOutcome = DecisionOutcomeBox()
        DispatchQueue.global(qos: .userInitiated).async {
            do {
                _ = try JSONLRuntimeMemoryStore(fileURL: fileURL)
                    .approveMemorySummaryDraft(
                        ownerDeviceID: "device-a",
                        draftID: draftID,
                        id: "memory-summary:\(draftID)",
                        content: "Must lose to process dismissal",
                        enabled: true,
                        source: source,
                        timestamp: Date(timeIntervalSince1970: 601)
                    )
                approvalOutcome.store(.approved)
            } catch RuntimeMemoryStoreError.memorySummaryDraftTerminalDecisionConflict {
                approvalOutcome.store(.conflict)
            } catch {
                approvalOutcome.store(.failed(error.localizedDescription))
            }
            approvalCompleted.signal()
        }
        XCTAssertEqual(approvalCompleted.wait(timeout: .now() + 0.2), .timedOut)

        try input.fileHandleForWriting.write(contentsOf: Data([0x0A]))
        try input.fileHandleForWriting.close()
        process.waitUntilExit()
        XCTAssertEqual(
            process.terminationStatus,
            0,
            String(data: errors.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
        )
        XCTAssertEqual(approvalCompleted.wait(timeout: .now() + 2), .success)
        XCTAssertEqual(approvalOutcome.value, .conflict)

        let reloadedStore = JSONLRuntimeMemoryStore(fileURL: fileURL)
        XCTAssertTrue(try reloadedStore.list(ownerDeviceID: "device-a").isEmpty)
        XCTAssertEqual(
            try reloadedStore.dismissedMemorySummaryDraftIDs(ownerDeviceID: "device-a"),
            Set([draftID])
        )
        XCTAssertEqual(try nonEmptyJSONLLines(at: fileURL).count, 1)
    }

    func testOppositeTerminalDecisionFailsClosedWithoutAppending() throws {
        let approveFileURL = try temporaryStoreURL()
        let approvedStore = JSONLRuntimeMemoryStore(fileURL: approveFileURL)
        let approvedDraftID = "long-inactivity:v2:approved-first"
        _ = try approvedStore.approveMemorySummaryDraft(
            ownerDeviceID: "device-a",
            draftID: approvedDraftID,
            id: "memory-summary:\(approvedDraftID)",
            content: "Approved first",
            enabled: true,
            source: memorySummarySource(draftID: approvedDraftID),
            timestamp: Date(timeIntervalSince1970: 200)
        )

        assertTerminalConflict {
            _ = try JSONLRuntimeMemoryStore(fileURL: approveFileURL)
                .dismissMemorySummaryDraft(
                    ownerDeviceID: "device-a",
                    draftID: approvedDraftID,
                    timestamp: Date(timeIntervalSince1970: 201)
                )
        }
        XCTAssertEqual(try nonEmptyJSONLLines(at: approveFileURL).count, 1)

        let dismissFileURL = try temporaryStoreURL()
        let dismissedStore = JSONLRuntimeMemoryStore(fileURL: dismissFileURL)
        let dismissedDraftID = "long-inactivity:v2:dismissed-first"
        _ = try dismissedStore.dismissMemorySummaryDraft(
            ownerDeviceID: "device-a",
            draftID: dismissedDraftID,
            timestamp: Date(timeIntervalSince1970: 300)
        )

        assertTerminalConflict {
            _ = try JSONLRuntimeMemoryStore(fileURL: dismissFileURL)
                .approveMemorySummaryDraft(
                    ownerDeviceID: "device-a",
                    draftID: dismissedDraftID,
                    id: "memory-summary:\(dismissedDraftID)",
                    content: "Must not reopen",
                    enabled: true,
                    source: memorySummarySource(draftID: dismissedDraftID),
                    timestamp: Date(timeIntervalSince1970: 301)
                )
        }
        XCTAssertEqual(try nonEmptyJSONLLines(at: dismissFileURL).count, 1)
    }

    func testApprovalRetryPreservesLaterUserEditAndDisabledState() throws {
        let fileURL = try temporaryStoreURL()
        let firstStore = JSONLRuntimeMemoryStore(fileURL: fileURL)
        let retryStore = JSONLRuntimeMemoryStore(fileURL: fileURL)
        let draftID = "long-inactivity:v2:approved-edit-preserved"
        let entryID = "memory-summary:\(draftID)"
        let source = memorySummarySource(draftID: draftID)

        _ = try firstStore.approveMemorySummaryDraft(
            ownerDeviceID: "device-a",
            draftID: draftID,
            id: entryID,
            content: "Initial approved content",
            enabled: true,
            source: source,
            timestamp: Date(timeIntervalSince1970: 400)
        )
        _ = try firstStore.upsert(
            ownerDeviceID: "device-a",
            id: entryID,
            content: "User edited content",
            enabled: false,
            source: nil,
            timestamp: Date(timeIntervalSince1970: 399)
        )

        let retryResult = try retryStore.approveMemorySummaryDraft(
            ownerDeviceID: "device-a",
            draftID: draftID,
            id: entryID,
            content: "Stale retry content",
            enabled: true,
            source: source,
            timestamp: Date(timeIntervalSince1970: 402)
        )

        XCTAssertEqual(retryResult.content, "User edited content")
        XCTAssertFalse(retryResult.enabled)
        XCTAssertEqual(retryResult.source?.draftID, draftID)
        XCTAssertEqual(try retryStore.list(ownerDeviceID: "device-a"), [retryResult])
        XCTAssertEqual(try nonEmptyJSONLLines(at: fileURL).count, 2)
    }

    func testApprovalRetryAfterRollbackTimestampDeleteDoesNotResurrectEntry() throws {
        let fileURL = try temporaryStoreURL()
        let firstStore = JSONLRuntimeMemoryStore(fileURL: fileURL)
        let retryStore = JSONLRuntimeMemoryStore(fileURL: fileURL)
        let draftID = "long-inactivity:v2:approved-delete-preserved"
        let entryID = "memory-summary:\(draftID)"
        let source = memorySummarySource(draftID: draftID)

        _ = try firstStore.approveMemorySummaryDraft(
            ownerDeviceID: "device-a",
            draftID: draftID,
            id: entryID,
            content: "Approved before delete",
            enabled: true,
            source: source,
            timestamp: Date(timeIntervalSince1970: 700)
        )
        _ = try firstStore.delete(
            ownerDeviceID: "device-a",
            id: entryID,
            timestamp: Date(timeIntervalSince1970: 699)
        )

        XCTAssertThrowsError(
            try retryStore.approveMemorySummaryDraft(
                ownerDeviceID: "device-a",
                draftID: draftID,
                id: entryID,
                content: "Must not resurrect",
                enabled: true,
                source: source,
                timestamp: Date(timeIntervalSince1970: 698)
            )
        ) { error in
            XCTAssertEqual(
                error as? RuntimeMemoryStoreError,
                .memorySummaryDraftApprovedEntryUnavailable
            )
        }
        XCTAssertTrue(try retryStore.list(ownerDeviceID: "device-a").isEmpty)
        XCTAssertEqual(try nonEmptyJSONLLines(at: fileURL).count, 2)
    }

    func testDismissRetryReturnsOriginalDecisionWithoutAppending() throws {
        let fileURL = try temporaryStoreURL()
        let firstStore = JSONLRuntimeMemoryStore(fileURL: fileURL)
        let retryStore = JSONLRuntimeMemoryStore(fileURL: fileURL)
        let draftID = "long-inactivity:v2:dismiss-retry"
        let firstTimestamp = Date(timeIntervalSince1970: 500)

        let first = try firstStore.dismissMemorySummaryDraft(
            ownerDeviceID: "device-a",
            draftID: draftID,
            timestamp: firstTimestamp
        )
        let retry = try retryStore.dismissMemorySummaryDraft(
            ownerDeviceID: "device-a",
            draftID: draftID,
            timestamp: Date(timeIntervalSince1970: 499)
        )

        XCTAssertEqual(first.dismissedAt, firstTimestamp)
        XCTAssertEqual(retry, first)
        XCTAssertEqual(try nonEmptyJSONLLines(at: fileURL).count, 1)
    }

    fileprivate enum DecisionOutcome: Equatable, Sendable {
        case approved
        case dismissed
        case conflict
        case failed(String)

        var isCommitted: Bool {
            self == .approved || self == .dismissed
        }
    }

    private static func runDecision(
        ready: DispatchSemaphore,
        start: DispatchSemaphore,
        operation: @escaping @Sendable () throws -> DecisionOutcome
    ) async -> DecisionOutcome {
        await withCheckedContinuation { continuation in
            DispatchQueue.global(qos: .userInitiated).async {
                ready.signal()
                start.wait()
                do {
                    continuation.resume(returning: try operation())
                } catch RuntimeMemoryStoreError.memorySummaryDraftTerminalDecisionConflict {
                    continuation.resume(returning: .conflict)
                } catch {
                    continuation.resume(returning: .failed(error.localizedDescription))
                }
            }
        }
    }

    private func assertTerminalConflict(
        file: StaticString = #filePath,
        line: UInt = #line,
        _ operation: () throws -> Void
    ) {
        XCTAssertThrowsError(try operation(), file: file, line: line) { error in
            XCTAssertEqual(
                error as? RuntimeMemoryStoreError,
                .memorySummaryDraftTerminalDecisionConflict,
                file: file,
                line: line
            )
        }
    }

    private func memorySummarySource(draftID: String) -> RuntimeMemoryEntrySource {
        RuntimeMemoryEntrySource(
            kind: "long_inactivity_summary_draft",
            draftID: draftID,
            summaryMethod: "deterministic_preview",
            session: RuntimeMemoryEntrySourceSession(
                sessionID: "session-a",
                title: "Session A",
                model: "model-a",
                lastActivityAt: Date(timeIntervalSince1970: 1),
                messageCount: 2,
                inactiveSeconds: 3_600
            ),
            sourceMessageCount: 2,
            sourceRange: "visible messages 1-2 of 2",
            sourcePointers: [RuntimeMemoryEntrySourcePointer(
                sessionID: "session-a",
                messageIndex: 1,
                role: "user",
                createdAt: Date(timeIntervalSince1970: 1),
                excerpt: "Remember this"
            )]
        )
    }

    private func temporaryStoreURL() throws -> URL {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        return directory.appendingPathComponent("runtime-memory-events.jsonl")
    }

    private func nonEmptyJSONLLines(at fileURL: URL) throws -> [Substring] {
        try String(contentsOf: fileURL, encoding: .utf8)
            .split(whereSeparator: { $0.isNewline })
            .filter { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
    }
}

private final class DecisionOutcomeBox: @unchecked Sendable {
    private let lock = NSLock()
    private var storedValue: RuntimeMemoryStoreSummaryDecisionTests.DecisionOutcome?

    var value: RuntimeMemoryStoreSummaryDecisionTests.DecisionOutcome? {
        lock.lock()
        defer { lock.unlock() }
        return storedValue
    }

    func store(_ value: RuntimeMemoryStoreSummaryDecisionTests.DecisionOutcome) {
        lock.lock()
        storedValue = value
        lock.unlock()
    }
}
