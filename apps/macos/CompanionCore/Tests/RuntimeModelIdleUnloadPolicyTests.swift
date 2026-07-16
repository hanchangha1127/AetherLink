import Foundation
@testable import CompanionCore
import XCTest

final class RuntimeModelIdleUnloadPolicyTests: XCTestCase {
    func testPolicyPresetsExposeStableDurations() {
        XCTAssertEqual(RuntimeModelIdleUnloadPolicy.allCases, [
            .fiveMinutes,
            .tenMinutes,
            .thirtyMinutes,
        ])
        XCTAssertEqual(RuntimeModelIdleUnloadPolicy.fiveMinutes.idleUnloadDelaySeconds, 300)
        XCTAssertEqual(RuntimeModelIdleUnloadPolicy.tenMinutes.idleUnloadDelaySeconds, 600)
        XCTAssertEqual(RuntimeModelIdleUnloadPolicy.thirtyMinutes.idleUnloadDelaySeconds, 1_800)
    }

    func testPolicyStoreDefaultsToTenMinutesAndRestoresKnownValue() throws {
        let suiteName = "RuntimeModelIdleUnloadPolicyTests.\(UUID().uuidString)"
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suiteName))
        defaults.removePersistentDomain(forName: suiteName)
        defer { defaults.removePersistentDomain(forName: suiteName) }
        let store = RuntimeModelIdleUnloadPolicyStore(defaults: defaults)

        XCTAssertEqual(store.load(), .tenMinutes)

        store.save(.thirtyMinutes)

        XCTAssertEqual(store.load(), .thirtyMinutes)
        XCTAssertEqual(
            defaults.string(forKey: RuntimeModelIdleUnloadPolicyStore.defaultsKey),
            RuntimeModelIdleUnloadPolicy.thirtyMinutes.rawValue
        )
    }

    func testPolicyStoreRejectsUnknownPersistedValue() throws {
        let suiteName = "RuntimeModelIdleUnloadPolicyTests.\(UUID().uuidString)"
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suiteName))
        defaults.removePersistentDomain(forName: suiteName)
        defer { defaults.removePersistentDomain(forName: suiteName) }
        let store = RuntimeModelIdleUnloadPolicyStore(defaults: defaults)
        defaults.set("sixty_minutes", forKey: RuntimeModelIdleUnloadPolicyStore.defaultsKey)

        XCTAssertEqual(store.load(), .tenMinutes)
    }

    func testPolicyUpdateQueueSerializesConcurrentChangesAndIdentifiesLatest() async {
        let queue = await RuntimeModelIdleUnloadPolicyUpdateQueue()
        let applier = ControlledPolicyUpdateApplier()

        let first = Task {
            await queue.enqueue {
                await applier.apply(300)
            }
        }
        XCTAssertTrue(applier.waitForNextStart())

        let second = Task {
            await queue.enqueue {
                await applier.apply(1_800)
            }
        }
        XCTAssertFalse(applier.waitForNextStart(timeout: 0.05))

        applier.releaseNext()
        XCTAssertTrue(applier.waitForNextStart())
        applier.releaseNext()

        let firstWasLatest = await first.value
        let secondWasLatest = await second.value
        XCTAssertFalse(firstWasLatest)
        XCTAssertTrue(secondWasLatest)
        XCTAssertEqual(applier.appliedDelays, [300, 1_800])
    }
}

private final class ControlledPolicyUpdateApplier: @unchecked Sendable {
    private let lock = NSLock()
    private let started = DispatchSemaphore(value: 0)
    private var continuations: [CheckedContinuation<Void, Never>] = []
    private var delays: [UInt64] = []

    var appliedDelays: [UInt64] {
        lock.withLock { delays }
    }

    func apply(_ delay: UInt64) async {
        await withCheckedContinuation { continuation in
            lock.withLock {
                delays.append(delay)
                continuations.append(continuation)
            }
            started.signal()
        }
    }

    func waitForNextStart(timeout: TimeInterval = 1) -> Bool {
        started.wait(timeout: .now() + timeout) == .success
    }

    func releaseNext() {
        let continuation = lock.withLock {
            continuations.isEmpty ? nil : continuations.removeFirst()
        }
        continuation?.resume()
    }
}
