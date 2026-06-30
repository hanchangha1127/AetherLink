import Foundation

public struct RelayPeerRegistration: Equatable, Sendable {
    public let id: UUID
    public let role: RelayRole
    public let relayID: String

    public init(id: UUID = UUID(), role: RelayRole, relayID: String) {
        self.id = id
        self.role = role
        self.relayID = relayID
    }
}

public enum RelayRegistrationResult: Equatable, Sendable {
    case waiting(replaced: RelayPeerRegistration?)
    case matched(runtime: RelayPeerRegistration, client: RelayPeerRegistration)
}

public final class RelayMatcher: @unchecked Sendable {
    private let lock = NSLock()
    private var pending: [String: [RelayRole: RelayPeerRegistration]] = [:]

    public init() {}

    public func register(_ peer: RelayPeerRegistration) -> RelayRegistrationResult {
        lock.withLock {
            registerLocked(peer)
        }
    }

    public func pendingCount(relayID: String? = nil) -> Int {
        lock.withLock {
            if let relayID {
                return pending[relayID]?.count ?? 0
            }
            return pending.values.reduce(0) { $0 + $1.count }
        }
    }

    public func hasWaitingRuntime(relayID: String) -> Bool {
        lock.withLock {
            pending[relayID]?[.runtime] != nil
        }
    }

    private func registerLocked(_ peer: RelayPeerRegistration) -> RelayRegistrationResult {
        var room = pending[peer.relayID] ?? [:]
        let replaced = room.removeValue(forKey: peer.role)
        let otherRole: RelayRole = peer.role == .runtime ? .client : .runtime

        if let other = room.removeValue(forKey: otherRole) {
            if room.isEmpty {
                pending.removeValue(forKey: peer.relayID)
            } else {
                pending[peer.relayID] = room
            }

            switch peer.role {
            case .runtime:
                return .matched(runtime: peer, client: other)
            case .client:
                return .matched(runtime: other, client: peer)
            }
        }

        room[peer.role] = peer
        pending[peer.relayID] = room
        return .waiting(replaced: replaced)
    }
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
