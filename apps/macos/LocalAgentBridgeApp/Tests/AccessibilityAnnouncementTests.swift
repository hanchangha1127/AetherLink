import AppKit
import XCTest
@testable import LocalAgentBridge

final class AccessibilityAnnouncementTests: XCTestCase {
    func testPolicyIgnoresInitialValueAndRepeatedValue() {
        var policy = AccessibilityAnnouncementPolicy()

        XCTAssertNil(policy.announcement(for: "Preparing connection details"))
        XCTAssertNil(policy.announcement(for: "Preparing connection details"))
        XCTAssertEqual(policy.lastObservedValue, "Preparing connection details")
    }

    func testPolicyAnnouncesEachDistinctNonemptyTransitionOnce() {
        var policy = AccessibilityAnnouncementPolicy()

        XCTAssertNil(policy.announcement(for: "Preparing"))
        XCTAssertEqual(policy.announcement(for: "Ready"), "Ready")
        XCTAssertNil(policy.announcement(for: " Ready "))
        XCTAssertNil(policy.announcement(for: nil))
        XCTAssertEqual(policy.announcement(for: "Ready"), "Ready")
    }

    func testObserverUsesInjectedPosterWithMediumPriority() {
        let poster = AccessibilityAnnouncementPosterSpy()
        var observer = AccessibilityAnnouncementObserver()

        observer.observe("Initial status", using: poster)
        observer.observe("Updated status", using: poster)
        observer.observe("Updated status", using: poster)

        XCTAssertEqual(poster.messages, ["Updated status"])
        XCTAssertEqual(poster.priorities, [.medium])
    }

    func testPairingRouteAnnouncementRemainsStableAcrossQRCountdownTicks() {
        let routeStatus = "Connection details are ready"
        let poster = AccessibilityAnnouncementPosterSpy()
        var observer = AccessibilityAnnouncementObserver()

        observer.observe(pairingRouteStatusAccessibilityAnnouncement(routeStatus), using: poster)
        for _ in 0..<3 {
            observer.observe(pairingRouteStatusAccessibilityAnnouncement(routeStatus), using: poster)
        }

        XCTAssertTrue(poster.messages.isEmpty)
    }

    func testScreenScopeCoalescesParentAndChildInFavorOfChildResult() {
        let poster = AccessibilityAnnouncementPosterSpy()
        let scheduler = AccessibilityAnnouncementSchedulerSpy()
        let scope = AccessibilityAnnouncementScope(poster: poster, scheduler: scheduler)

        scope.submit(message: "Runtime overview ready", priority: .parentSummary)
        scope.submit(message: "Connection details saved", priority: .childResult)

        XCTAssertTrue(poster.messages.isEmpty)
        XCTAssertEqual(scheduler.pendingCount, 1)
        scheduler.runPending()
        XCTAssertEqual(poster.messages, ["Connection details saved"])
        XCTAssertEqual(poster.priorities, [.medium])

        scope.submit(message: "Later child result", priority: .childResult)
        scope.submit(message: "Later parent summary", priority: .parentSummary)
        scheduler.runPending()
        XCTAssertEqual(
            poster.messages,
            ["Connection details saved", "Later child result"]
        )
    }

    func testScreenScopeKeepsParentOnlyChildOnlyAndSeparatedFollowUpChanges() {
        let poster = AccessibilityAnnouncementPosterSpy()
        let scheduler = AccessibilityAnnouncementSchedulerSpy()
        let scope = AccessibilityAnnouncementScope(poster: poster, scheduler: scheduler)

        scope.submit(message: "Parent only", priority: .parentSummary)
        scheduler.runPending()
        scope.submit(message: "Child later", priority: .childResult)
        scheduler.runPending()
        scope.submit(message: "Parent follow-up", priority: .parentSummary)
        scheduler.runPending()

        XCTAssertEqual(poster.messages, ["Parent only", "Child later", "Parent follow-up"])
    }

    func testSeparateScreenScopesDoNotSuppressEachOther() {
        let poster = AccessibilityAnnouncementPosterSpy()
        let firstScheduler = AccessibilityAnnouncementSchedulerSpy()
        let secondScheduler = AccessibilityAnnouncementSchedulerSpy()
        let firstScope = AccessibilityAnnouncementScope(poster: poster, scheduler: firstScheduler)
        let secondScope = AccessibilityAnnouncementScope(poster: poster, scheduler: secondScheduler)

        firstScope.submit(message: "Same status", priority: .parentSummary)
        secondScope.submit(message: "Same status", priority: .parentSummary)
        firstScheduler.runPending()
        secondScheduler.runPending()

        XCTAssertEqual(poster.messages, ["Same status", "Same status"])
    }
}

private final class AccessibilityAnnouncementPosterSpy: AccessibilityAnnouncementPosting {
    private(set) var messages: [String] = []
    private(set) var priorities: [NSAccessibilityPriorityLevel] = []

    func post(message: String, priority: NSAccessibilityPriorityLevel) {
        messages.append(message)
        priorities.append(priority)
    }
}

private final class AccessibilityAnnouncementSchedulerSpy: AccessibilityAnnouncementScheduling {
    private var actions: [() -> Void] = []
    var pendingCount: Int { actions.count }

    func schedule(_ action: @escaping () -> Void) {
        actions.append(action)
    }

    func runPending() {
        let pending = actions
        actions.removeAll()
        pending.forEach { $0() }
    }
}
