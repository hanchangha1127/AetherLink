import AppKit
import SwiftUI

protocol AccessibilityAnnouncementPosting {
    func post(message: String, priority: NSAccessibilityPriorityLevel)
}

protocol AccessibilityAnnouncementScheduling {
    func schedule(_ action: @escaping () -> Void)
}

struct AppKitAccessibilityAnnouncementPoster: AccessibilityAnnouncementPosting {
    func post(message: String, priority: NSAccessibilityPriorityLevel) {
        NSAccessibility.post(
            element: NSApplication.shared,
            notification: .announcementRequested,
            userInfo: [
                .announcement: message,
                .priority: NSNumber(value: priority.rawValue),
            ]
        )
    }
}

struct MainQueueAccessibilityAnnouncementScheduler: AccessibilityAnnouncementScheduling {
    func schedule(_ action: @escaping () -> Void) {
        DispatchQueue.main.async(execute: action)
    }
}

enum AccessibilityAnnouncementScopePriority: Int {
    case parentSummary
    case childResult
}

final class AccessibilityAnnouncementScope: ObservableObject {
    private struct PendingAnnouncement {
        let message: String
        let priority: AccessibilityAnnouncementScopePriority
    }

    private let poster: any AccessibilityAnnouncementPosting
    private let scheduler: any AccessibilityAnnouncementScheduling
    private var pendingAnnouncement: PendingAnnouncement?
    private var isFlushScheduled = false

    init(
        poster: any AccessibilityAnnouncementPosting = AppKitAccessibilityAnnouncementPoster(),
        scheduler: any AccessibilityAnnouncementScheduling = MainQueueAccessibilityAnnouncementScheduler()
    ) {
        self.poster = poster
        self.scheduler = scheduler
    }

    func submit(message: String, priority: AccessibilityAnnouncementScopePriority) {
        guard let message = normalizedAccessibilityAnnouncementValue(message) else { return }
        let candidate = PendingAnnouncement(message: message, priority: priority)
        if pendingAnnouncement?.priority.rawValue ?? -1 <= priority.rawValue {
            pendingAnnouncement = candidate
        }
        guard !isFlushScheduled else { return }
        isFlushScheduled = true
        scheduler.schedule { [weak self] in
            self?.flush()
        }
    }

    private func flush() {
        let announcement = pendingAnnouncement
        pendingAnnouncement = nil
        isFlushScheduled = false
        guard let announcement else { return }
        poster.post(message: announcement.message, priority: .medium)
    }
}

private struct AccessibilityAnnouncementScopeEnvironmentKey: EnvironmentKey {
    static let defaultValue: AccessibilityAnnouncementScope? = nil
}

private extension EnvironmentValues {
    var accessibilityAnnouncementScope: AccessibilityAnnouncementScope? {
        get { self[AccessibilityAnnouncementScopeEnvironmentKey.self] }
        set { self[AccessibilityAnnouncementScopeEnvironmentKey.self] = newValue }
    }
}

struct AccessibilityAnnouncementPolicy {
    private(set) var lastObservedValue: String?
    private(set) var hasObservedInitialValue = false

    mutating func announcement(for value: String?) -> String? {
        let normalizedValue = value.flatMap(normalizedAccessibilityAnnouncementValue)

        defer {
            lastObservedValue = normalizedValue
            hasObservedInitialValue = true
        }

        guard hasObservedInitialValue,
              normalizedValue != lastObservedValue,
              let normalizedValue else {
            return nil
        }
        return normalizedValue
    }
}

func normalizedAccessibilityAnnouncementValue(_ value: String) -> String? {
    let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
    return trimmed.isEmpty ? nil : trimmed
}

struct AccessibilityAnnouncementObserver {
    private(set) var policy = AccessibilityAnnouncementPolicy()

    mutating func announcement(for value: String?) -> String? {
        policy.announcement(for: value)
    }

    mutating func observe(
        _ value: String?,
        using poster: any AccessibilityAnnouncementPosting
    ) {
        guard let announcement = announcement(for: value) else { return }
        poster.post(message: announcement, priority: .medium)
    }
}

private struct PoliteAccessibilityAnnouncementModifier: ViewModifier {
    let value: String?
    let scopePriority: AccessibilityAnnouncementScopePriority
    let poster: any AccessibilityAnnouncementPosting
    @Environment(\.accessibilityAnnouncementScope) private var scope
    @State private var observer = AccessibilityAnnouncementObserver()

    func body(content: Content) -> some View {
        content
            .onChange(of: value, initial: true) { _, newValue in
                guard let announcement = observer.announcement(for: newValue) else { return }
                if let scope {
                    scope.submit(message: announcement, priority: scopePriority)
                } else {
                    poster.post(message: announcement, priority: .medium)
                }
            }
    }
}

extension View {
    func politeAccessibilityAnnouncement(
        for value: String?,
        scopePriority: AccessibilityAnnouncementScopePriority = .parentSummary,
        poster: any AccessibilityAnnouncementPosting = AppKitAccessibilityAnnouncementPoster()
    ) -> some View {
        modifier(
            PoliteAccessibilityAnnouncementModifier(
                value: value,
                scopePriority: scopePriority,
                poster: poster
            )
        )
    }

    func accessibilityAnnouncementScope(_ scope: AccessibilityAnnouncementScope) -> some View {
        environment(\.accessibilityAnnouncementScope, scope)
    }
}
