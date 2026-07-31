import AppKit
import XCTest
@testable import LocalAgentBridge

@MainActor
final class AppLifecycleTests: XCTestCase {
    func testApplicationTerminationDefaultTimeoutIsFiveSeconds() {
        XCTAssertEqual(
            AppDelegate.defaultApplicationTerminationTimeoutNanoseconds,
            5_000_000_000
        )
    }

    func testApplicationShouldTerminateWaitsForRuntimeDrainAndRepliesOnce()
        async
    {
        let notificationCenter = NotificationCenter()
        var replies: [Bool] = []
        let delegate = AppDelegate(
            workspaceNotificationCenter: notificationCenter,
            applicationTerminationTimeoutNanoseconds: UInt64.max,
            applicationTerminationSleeper: {
                try await Task.sleep(nanoseconds: $0)
            },
            applicationTerminationReply: { replies.append($0) }
        )
        let runtime = DrainingRuntimeApplicationLifecycle()
        delegate.installRuntimeLifecycleIfNeeded(runtime)

        XCTAssertEqual(
            delegate.applicationShouldTerminate(NSApplication.shared),
            .terminateLater
        )
        XCTAssertEqual(
            delegate.applicationShouldTerminate(NSApplication.shared),
            .terminateLater
        )
        XCTAssertEqual(runtime.beginTerminationCount, 1)
        XCTAssertEqual(runtime.stopCount, 1)
        let drainStarted = await waitUntilAppLifecycleCondition {
            runtime.drainTerminationCount == 1
        }
        XCTAssertTrue(drainStarted)
        XCTAssertEqual(replies, [])

        await runtime.releaseDrain()
        let drainReplied = await waitUntilAppLifecycleCondition {
            replies == [true]
        }
        XCTAssertTrue(drainReplied)
        XCTAssertEqual(
            delegate.applicationShouldTerminate(NSApplication.shared),
            .terminateNow
        )

        delegate.applicationWillTerminate(
            Notification(name: NSApplication.willTerminateNotification)
        )
        XCTAssertEqual(runtime.beginTerminationCount, 1)
        XCTAssertEqual(runtime.drainTerminationCount, 1)
        XCTAssertEqual(runtime.stopCount, 1)
        XCTAssertEqual(replies, [true])
    }

    func testApplicationShouldTerminateUsesBoundedTimeoutForHungDrain()
        async
    {
        var replies: [Bool] = []
        let runtime = CancellationBoundRuntimeApplicationLifecycle()
        let delegate = AppDelegate(
            workspaceNotificationCenter: NotificationCenter(),
            applicationTerminationTimeoutNanoseconds: 1,
            applicationTerminationSleeper: { _ in },
            applicationTerminationReply: { replies.append($0) }
        )
        delegate.installRuntimeLifecycleIfNeeded(runtime)

        XCTAssertEqual(
            delegate.applicationShouldTerminate(NSApplication.shared),
            .terminateLater
        )
        XCTAssertEqual(runtime.beginTerminationCount, 1)
        XCTAssertEqual(runtime.stopCount, 1)
        let timeoutReplied = await waitUntilAppLifecycleCondition {
            replies == [true]
        }
        XCTAssertTrue(timeoutReplied)
        let drainCancelled = await waitUntilAppLifecycleCondition {
            runtime.drainDidObserveCancellation
        }
        XCTAssertTrue(drainCancelled)

        delegate.applicationWillTerminate(
            Notification(name: NSApplication.willTerminateNotification)
        )
        XCTAssertEqual(runtime.beginTerminationCount, 1)
        XCTAssertEqual(runtime.stopCount, 1)
        XCTAssertEqual(replies, [true])
    }

    func testLateDrainAfterTerminationTimeoutCannotReplyTwice() async {
        var replies: [Bool] = []
        let runtime = DrainingRuntimeApplicationLifecycle()
        let delegate = AppDelegate(
            workspaceNotificationCenter: NotificationCenter(),
            applicationTerminationTimeoutNanoseconds: 1,
            applicationTerminationSleeper: { _ in },
            applicationTerminationReply: { replies.append($0) }
        )
        delegate.installRuntimeLifecycleIfNeeded(runtime)

        XCTAssertEqual(
            delegate.applicationShouldTerminate(NSApplication.shared),
            .terminateLater
        )
        let timeoutReplied = await waitUntilAppLifecycleCondition {
            replies == [true]
        }
        XCTAssertTrue(timeoutReplied)

        await runtime.releaseDrain()
        for _ in 0..<10 {
            await Task.yield()
        }

        XCTAssertEqual(runtime.beginTerminationCount, 1)
        XCTAssertEqual(runtime.stopCount, 1)
        XCTAssertEqual(replies, [true])
    }

    func testApplicationShouldTerminateWithoutInstalledRuntimeDoesNotDelay()
    {
        var replies: [Bool] = []
        let delegate = AppDelegate(
            workspaceNotificationCenter: NotificationCenter(),
            applicationTerminationReply: { replies.append($0) }
        )

        XCTAssertEqual(
            delegate.applicationShouldTerminate(NSApplication.shared),
            .terminateNow
        )
        XCTAssertEqual(replies, [])
    }

    func testApplicationTerminationStopsInstalledRuntimeExactlyOnce() {
        let delegate = AppDelegate()
        let runtime = RecordingRuntimeApplicationLifecycle()
        delegate.installRuntimeLifecycleIfNeeded(runtime)
        let notification = Notification(
            name: NSApplication.willTerminateNotification
        )

        delegate.applicationWillTerminate(notification)
        delegate.applicationWillTerminate(notification)

        XCTAssertEqual(runtime.stopCount, 1)
    }

    func testRepeatedInstallationCannotReplaceRuntimeLifecycle() {
        let delegate = AppDelegate()
        let firstRuntime = RecordingRuntimeApplicationLifecycle()
        let replacementRuntime = RecordingRuntimeApplicationLifecycle()
        delegate.installRuntimeLifecycleIfNeeded(firstRuntime)
        delegate.installRuntimeLifecycleIfNeeded(replacementRuntime)
        XCTAssertTrue(
            delegate.requestRuntimeStartForUserInterface(port: 43_199)
        )

        delegate.applicationWillTerminate(
            Notification(name: NSApplication.willTerminateNotification)
        )

        XCTAssertEqual(firstRuntime.requestedStartPorts, [43_199])
        XCTAssertEqual(replacementRuntime.requestedStartPorts, [])
        XCTAssertEqual(firstRuntime.stopCount, 1)
        XCTAssertEqual(replacementRuntime.stopCount, 0)
    }

    func testRuntimeInstalledAfterTerminationIsNeverStopped() {
        let delegate = AppDelegate()
        let notification = Notification(
            name: NSApplication.willTerminateNotification
        )
        delegate.applicationWillTerminate(notification)
        let lateRuntime = RecordingRuntimeApplicationLifecycle()

        delegate.installRuntimeLifecycleIfNeeded(lateRuntime)
        delegate.applicationWillTerminate(notification)

        XCTAssertEqual(lateRuntime.stopCount, 0)
    }

    func testDelegateDoesNotRetainInstalledRuntimeLifecycle() {
        let delegate = AppDelegate()
        weak var retainedRuntime: RecordingRuntimeApplicationLifecycle?

        do {
            let runtime = RecordingRuntimeApplicationLifecycle()
            retainedRuntime = runtime
            delegate.installRuntimeLifecycleIfNeeded(runtime)
        }

        XCTAssertNil(retainedRuntime)
        delegate.applicationWillTerminate(
            Notification(name: NSApplication.willTerminateNotification)
        )
    }

    func testWorkspaceSleepWakeSuspendsAndResumesRuntimeExactlyOnce() {
        let notificationCenter = NotificationCenter()
        let delegate = AppDelegate(
            workspaceNotificationCenter: notificationCenter
        )
        let runtime = RecordingRuntimeApplicationLifecycle(
            suspendResults: [true]
        )
        delegate.installRuntimeLifecycleIfNeeded(runtime)
        delegate.startObservingWorkspaceLifecycleIfNeeded()
        delegate.startObservingWorkspaceLifecycleIfNeeded()

        notificationCenter.post(
            name: NSWorkspace.willSleepNotification,
            object: nil
        )
        notificationCenter.post(
            name: NSWorkspace.willSleepNotification,
            object: nil
        )
        notificationCenter.post(
            name: NSWorkspace.didWakeNotification,
            object: nil
        )
        notificationCenter.post(
            name: NSWorkspace.didWakeNotification,
            object: nil
        )

        XCTAssertEqual(runtime.suspendCount, 1)
        XCTAssertEqual(runtime.resumeCount, 1)
        XCTAssertEqual(runtime.stopCount, 0)

        delegate.applicationWillTerminate(
            Notification(name: NSApplication.willTerminateNotification)
        )
        XCTAssertEqual(runtime.stopCount, 1)
    }

    func testWakeWithoutSuccessfulSleepSuspensionDoesNotStartRuntime() {
        let notificationCenter = NotificationCenter()
        let delegate = AppDelegate(
            workspaceNotificationCenter: notificationCenter
        )
        let runtime = RecordingRuntimeApplicationLifecycle(
            suspendResults: [false]
        )
        delegate.installRuntimeLifecycleIfNeeded(runtime)
        delegate.startObservingWorkspaceLifecycleIfNeeded()

        notificationCenter.post(
            name: NSWorkspace.didWakeNotification,
            object: nil
        )
        notificationCenter.post(
            name: NSWorkspace.willSleepNotification,
            object: nil
        )
        notificationCenter.post(
            name: NSWorkspace.didWakeNotification,
            object: nil
        )

        XCTAssertEqual(runtime.suspendCount, 1)
        XCTAssertEqual(runtime.resumeCount, 0)
        XCTAssertEqual(runtime.requestedStartPorts, [])

        delegate.applicationWillTerminate(
            Notification(name: NSApplication.willTerminateNotification)
        )
    }

    func testTerminationWhileSuspendedCannotStopTwiceOrResume() {
        let notificationCenter = NotificationCenter()
        let delegate = AppDelegate(
            workspaceNotificationCenter: notificationCenter
        )
        let runtime = RecordingRuntimeApplicationLifecycle(
            suspendResults: [true]
        )
        delegate.installRuntimeLifecycleIfNeeded(runtime)
        delegate.startObservingWorkspaceLifecycleIfNeeded()
        notificationCenter.post(
            name: NSWorkspace.willSleepNotification,
            object: nil
        )

        let termination = Notification(
            name: NSApplication.willTerminateNotification
        )
        delegate.applicationWillTerminate(termination)
        delegate.applicationWillTerminate(termination)
        notificationCenter.post(
            name: NSWorkspace.didWakeNotification,
            object: nil
        )

        XCTAssertEqual(runtime.suspendCount, 1)
        XCTAssertEqual(runtime.resumeCount, 0)
        XCTAssertEqual(runtime.stopCount, 1)
    }

    func testInitialRuntimeStartIsDeferredUntilWake() {
        let notificationCenter = NotificationCenter()
        let delegate = AppDelegate(
            workspaceNotificationCenter: notificationCenter
        )
        let runtime = RecordingRuntimeApplicationLifecycle(
            suspendResults: [false]
        )
        delegate.installRuntimeLifecycleIfNeeded(runtime)
        delegate.startObservingWorkspaceLifecycleIfNeeded()
        notificationCenter.post(
            name: NSWorkspace.willSleepNotification,
            object: nil
        )

        XCTAssertFalse(
            delegate.requestRuntimeStartForUserInterface(port: 43_219)
        )
        XCTAssertEqual(runtime.requestedStartPorts, [])

        notificationCenter.post(
            name: NSWorkspace.didWakeNotification,
            object: nil
        )

        XCTAssertEqual(runtime.requestedStartPorts, [43_219])
        delegate.applicationWillTerminate(
            Notification(name: NSApplication.willTerminateNotification)
        )
    }
}

@MainActor
private func waitUntilAppLifecycleCondition(
    attempts: Int = 1_000,
    _ condition: @escaping @MainActor () -> Bool
) async -> Bool {
    for _ in 0..<attempts {
        if condition() {
            return true
        }
        await Task.yield()
    }
    return condition()
}

private actor AppLifecycleDrainGate {
    private var isReleased = false
    private var continuations: [CheckedContinuation<Void, Never>] = []

    func wait() async {
        if isReleased {
            return
        }
        await withCheckedContinuation { continuation in
            if isReleased {
                continuation.resume()
            } else {
                continuations.append(continuation)
            }
        }
    }

    func release() {
        guard !isReleased else { return }
        isReleased = true
        let continuations = self.continuations
        self.continuations.removeAll()
        continuations.forEach { $0.resume() }
    }
}

@MainActor
private final class DrainingRuntimeApplicationLifecycle:
    RuntimeApplicationLifecycle {
    private let drainGate = AppLifecycleDrainGate()
    private(set) var beginTerminationCount = 0
    private(set) var drainTerminationCount = 0
    private(set) var stopCount = 0

    func requestStartForUserInterface(port: UInt16) -> Bool {
        false
    }

    func suspendForSystemSleep() -> Bool {
        false
    }

    func resumeAfterSystemWake() -> Bool {
        false
    }

    func beginApplicationTermination() {
        beginTerminationCount += 1
        stop()
    }

    func drainApplicationTermination() async {
        drainTerminationCount += 1
        await drainGate.wait()
    }

    func stop() {
        stopCount += 1
    }

    func releaseDrain() async {
        await drainGate.release()
    }
}

@MainActor
private final class CancellationBoundRuntimeApplicationLifecycle:
    RuntimeApplicationLifecycle {
    private(set) var beginTerminationCount = 0
    private(set) var stopCount = 0
    private(set) var drainDidObserveCancellation = false

    func requestStartForUserInterface(port: UInt16) -> Bool {
        false
    }

    func suspendForSystemSleep() -> Bool {
        false
    }

    func resumeAfterSystemWake() -> Bool {
        false
    }

    func beginApplicationTermination() {
        beginTerminationCount += 1
        stop()
    }

    func drainApplicationTermination() async {
        do {
            try await Task.sleep(nanoseconds: UInt64.max)
        } catch {
            drainDidObserveCancellation = true
        }
    }

    func stop() {
        stopCount += 1
    }
}

@MainActor
private final class RecordingRuntimeApplicationLifecycle:
    RuntimeApplicationLifecycle {
    private var suspendResults: [Bool]
    private(set) var requestedStartPorts: [UInt16] = []
    private(set) var suspendCount = 0
    private(set) var resumeCount = 0
    private(set) var stopCount = 0

    init(suspendResults: [Bool] = []) {
        self.suspendResults = suspendResults
    }

    func requestStartForUserInterface(port: UInt16) -> Bool {
        requestedStartPorts.append(port)
        return true
    }

    func suspendForSystemSleep() -> Bool {
        suspendCount += 1
        return suspendResults.isEmpty ? false : suspendResults.removeFirst()
    }

    func resumeAfterSystemWake() -> Bool {
        resumeCount += 1
        return true
    }

    func stop() {
        stopCount += 1
    }
}
