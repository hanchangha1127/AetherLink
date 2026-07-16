import Foundation

public enum RuntimeModelIdleUnloadPolicy: String, CaseIterable, Identifiable, Sendable {
    case fiveMinutes = "five_minutes"
    case tenMinutes = "ten_minutes"
    case thirtyMinutes = "thirty_minutes"

    public var id: String { rawValue }

    public var minutes: Int {
        switch self {
        case .fiveMinutes:
            return 5
        case .tenMinutes:
            return 10
        case .thirtyMinutes:
            return 30
        }
    }

    public var idleUnloadDelaySeconds: Int {
        minutes * 60
    }

    var idleUnloadDelayNanoseconds: UInt64 {
        UInt64(idleUnloadDelaySeconds) * 1_000_000_000
    }
}

struct RuntimeModelIdleUnloadPolicyStore {
    static let defaultsKey = "runtime.modelResidency.idleUnloadPolicy.v1"

    let defaults: UserDefaults

    func load() -> RuntimeModelIdleUnloadPolicy {
        guard let rawValue = defaults.string(forKey: Self.defaultsKey),
              let policy = RuntimeModelIdleUnloadPolicy(rawValue: rawValue)
        else {
            return .tenMinutes
        }
        return policy
    }

    func save(_ policy: RuntimeModelIdleUnloadPolicy) {
        defaults.set(policy.rawValue, forKey: Self.defaultsKey)
    }
}

@MainActor
final class RuntimeModelIdleUnloadPolicyUpdateQueue {
    private var updateSequence: UInt64 = 0
    private var tailTask: Task<Void, Never>?

    func enqueue(_ operation: @escaping @Sendable () async -> Void) async -> Bool {
        updateSequence &+= 1
        let sequence = updateSequence
        let previousTask = tailTask
        let task = Task {
            await previousTask?.value
            await operation()
        }
        tailTask = task
        await task.value

        guard sequence == updateSequence else {
            return false
        }
        tailTask = nil
        return true
    }
}
