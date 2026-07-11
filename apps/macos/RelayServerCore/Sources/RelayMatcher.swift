import Foundation

public struct RelayRoomBinding: Equatable, Sendable {
    public let relayID: String
    public let ticketGeneration: Int64
    public let relayNonce: String
    public let runtimeKeyFingerprint: String
    public let pairedClientKeyFingerprint: String?

    public init(
        relayID: String,
        ticketGeneration: Int64,
        relayNonce: String,
        runtimeKeyFingerprint: String,
        pairedClientKeyFingerprint: String? = nil
    ) {
        self.relayID = relayID
        self.ticketGeneration = ticketGeneration
        self.relayNonce = relayNonce
        self.runtimeKeyFingerprint = runtimeKeyFingerprint
        self.pairedClientKeyFingerprint = pairedClientKeyFingerprint
    }

    public init(allocationBinding: RelayAllocationBinding) {
        self.init(
            relayID: allocationBinding.relayID,
            ticketGeneration: allocationBinding.ticketGeneration,
            relayNonce: allocationBinding.relayNonce,
            runtimeKeyFingerprint: allocationBinding.runtimeKeyFingerprint,
            pairedClientKeyFingerprint: allocationBinding.pairedClientKeyFingerprint
        )
    }
}

public struct RelayPeerRegistration: Equatable, Sendable {
    public let id: UUID
    public let role: RelayRole
    public let relayID: String
    public let roomBinding: RelayRoomBinding?
    public let sessionNonce: String?
    public let ephemeralKey: String?
    public let runtimeKeyFingerprint: String?
    let authenticatedIdentity: RelayAuthenticatedPeerIdentity?

    public init(
        id: UUID = UUID(),
        role: RelayRole,
        relayID: String,
        roomBinding: RelayRoomBinding? = nil
    ) {
        self.id = id
        self.role = role
        self.relayID = relayID
        self.roomBinding = roomBinding
        self.sessionNonce = nil
        self.ephemeralKey = nil
        self.runtimeKeyFingerprint = nil
        self.authenticatedIdentity = nil
    }

    public init(
        id: UUID = UUID(),
        role: RelayRole,
        relayID: String,
        roomBinding: RelayRoomBinding? = nil,
        sessionNonce: String,
        ephemeralKey: String,
        runtimeKeyFingerprint: String? = nil
    ) {
        self.id = id
        self.role = role
        self.relayID = relayID
        self.roomBinding = roomBinding
        self.sessionNonce = sessionNonce
        self.ephemeralKey = ephemeralKey
        self.runtimeKeyFingerprint = runtimeKeyFingerprint
        self.authenticatedIdentity = nil
    }

    init(
        id: UUID = UUID(),
        role: RelayRole,
        relayID: String,
        roomBinding: RelayRoomBinding?,
        sessionNonce: String,
        ephemeralKey: String,
        runtimeKeyFingerprint: String? = nil,
        authenticatedIdentity: RelayAuthenticatedPeerIdentity?
    ) {
        self.id = id
        self.role = role
        self.relayID = relayID
        self.roomBinding = roomBinding
        self.sessionNonce = sessionNonce
        self.ephemeralKey = ephemeralKey
        self.runtimeKeyFingerprint = runtimeKeyFingerprint
        self.authenticatedIdentity = authenticatedIdentity
    }

    init(
        id: UUID = UUID(),
        role: RelayRole,
        relayID: String,
        roomBinding: RelayRoomBinding?,
        authenticatedIdentity: RelayAuthenticatedPeerIdentity?
    ) {
        self.id = id
        self.role = role
        self.relayID = relayID
        self.roomBinding = roomBinding
        self.sessionNonce = nil
        self.ephemeralKey = nil
        self.runtimeKeyFingerprint = nil
        self.authenticatedIdentity = authenticatedIdentity
    }
}

public struct RelayMatchToken: Hashable, Sendable {
    fileprivate let rawValue: UUID

    fileprivate init(rawValue: UUID = UUID()) {
        self.rawValue = rawValue
    }
}

public struct RelayActiveRoom: Equatable, Sendable {
    public let matchToken: RelayMatchToken
    public let runtime: RelayPeerRegistration
    public let client: RelayPeerRegistration

    public var relayID: String { runtime.relayID }
    public var roomBinding: RelayRoomBinding? { runtime.roomBinding }
}

public enum RelayRegistrationRejection: Equatable, Sendable {
    case activeRoom
    case roomBindingMismatch
    case sourceWaitingPeerQuota
    case authenticatedIdentityWaitingQuota
    case counterpartRequired
}

public enum RelayRegistrationResult: Equatable, Sendable {
    case waiting(replaced: RelayPeerRegistration?)
    case matched(
        runtime: RelayPeerRegistration,
        client: RelayPeerRegistration,
        matchToken: RelayMatchToken
    )
    case rejected(RelayRegistrationRejection)
}

public final class RelayMatcher: @unchecked Sendable {
    private struct WaitingPeer {
        let registration: RelayPeerRegistration
        let sourceIdentity: RelaySourceIdentity
        let authenticatedIdentity: RelayAuthenticatedPeerIdentity?
    }

    private struct WaitingRoom {
        let roomBinding: RelayRoomBinding?
        let deadlineUptime: TimeInterval
        var peers: [RelayRole: WaitingPeer]
    }

    private let lock = NSLock()
    private let sourceQuotaLimiter: RelaySourceQuotaLimiter?
    private let waitingPeerLimiter: RelayWaitingPeerLimiter?
    private let maximumWaitingDurationSeconds: TimeInterval
    private let monotonicNow: @Sendable () -> TimeInterval
    private var waitingRooms: [String: WaitingRoom] = [:]
    private var activeRooms: [String: RelayActiveRoom] = [:]
    private var activeRelayIDsByToken: [RelayMatchToken: String] = [:]

    public init() {
        sourceQuotaLimiter = nil
        waitingPeerLimiter = nil
        maximumWaitingDurationSeconds =
            RelayWaitingPeerPolicyConfiguration.defaultMaximumDurationSeconds
        monotonicNow = { ProcessInfo.processInfo.systemUptime }
    }

    init(
        sourceQuotaLimiter: RelaySourceQuotaLimiter,
        waitingPeerLimiter: RelayWaitingPeerLimiter? = nil,
        maximumWaitingDurationSeconds: TimeInterval =
            RelayWaitingPeerPolicyConfiguration.defaultMaximumDurationSeconds,
        monotonicNow: @escaping @Sendable () -> TimeInterval = {
            ProcessInfo.processInfo.systemUptime
        }
    ) {
        self.sourceQuotaLimiter = sourceQuotaLimiter
        self.waitingPeerLimiter = waitingPeerLimiter
        self.maximumWaitingDurationSeconds = maximumWaitingDurationSeconds
        self.monotonicNow = monotonicNow
    }

    public func register(_ peer: RelayPeerRegistration) -> RelayRegistrationResult {
        lock.withLock {
            registerLocked(
                peer,
                sourceIdentity: .unknown,
                requiresImmediateMatch: false
            )
        }
    }

    func register(
        _ peer: RelayPeerRegistration,
        sourceIdentity: RelaySourceIdentity,
        requiresImmediateMatch: Bool = false,
        requiresSameSourceCounterpart: Bool = false,
        maximumWaitingDeadlineUptime: TimeInterval? = nil
    ) -> RelayRegistrationResult {
        lock.withLock {
            registerLocked(
                peer,
                sourceIdentity: sourceIdentity,
                requiresImmediateMatch: requiresImmediateMatch,
                requiresSameSourceCounterpart: requiresSameSourceCounterpart,
                maximumWaitingDeadlineUptime: maximumWaitingDeadlineUptime
            )
        }
    }

    public func release(matchToken: RelayMatchToken) -> RelayActiveRoom? {
        lock.withLock {
            guard let relayID = activeRelayIDsByToken.removeValue(forKey: matchToken),
                  let activeRoom = activeRooms.removeValue(forKey: relayID)
            else {
                return nil
            }
            return activeRoom
        }
    }

    @discardableResult
    public func unregisterWaiting(peerID: UUID) -> RelayPeerRegistration? {
        lock.withLock {
            for relayID in waitingRooms.keys.sorted() {
                guard var room = waitingRooms[relayID] else { continue }
                for role in Self.orderedRoles {
                    guard room.peers[role]?.registration.id == peerID else { continue }
                    let removed = room.peers.removeValue(forKey: role)
                    if let removed {
                        sourceQuotaLimiter?.releaseWaitingPeer(source: removed.sourceIdentity)
                        waitingPeerLimiter?.releaseWaitingPeer(
                            identity: removed.authenticatedIdentity
                        )
                    }
                    if room.peers.isEmpty {
                        waitingRooms.removeValue(forKey: relayID)
                    } else {
                        waitingRooms[relayID] = room
                    }
                    return removed?.registration
                }
            }
            return nil
        }
    }

    @discardableResult
    public func invalidateWaiting(
        relayID: String,
        keeping roomBinding: RelayRoomBinding?
    ) -> [RelayPeerRegistration] {
        lock.withLock {
            guard let room = waitingRooms[relayID], room.roomBinding != roomBinding else {
                return []
            }
            waitingRooms.removeValue(forKey: relayID)
            let peers = Self.orderedWaitingPeers(room.peers)
            for peer in peers {
                sourceQuotaLimiter?.releaseWaitingPeer(source: peer.sourceIdentity)
                waitingPeerLimiter?.releaseWaitingPeer(identity: peer.authenticatedIdentity)
            }
            return peers.map(\.registration)
        }
    }

    public func pendingCount(relayID: String? = nil) -> Int {
        lock.withLock {
            if let relayID {
                return waitingRooms[relayID]?.peers.count ?? 0
            }
            return waitingRooms.values.reduce(0) { $0 + $1.peers.count }
        }
    }

    public func activeCount(relayID: String? = nil) -> Int {
        lock.withLock {
            if let relayID {
                return activeRooms[relayID] == nil ? 0 : 1
            }
            return activeRooms.count
        }
    }

    public func hasWaitingRuntime(relayID: String) -> Bool {
        lock.withLock {
            waitingRooms[relayID]?.peers[.runtime] != nil
        }
    }

    public func waitingRegistrations(relayID: String) -> [RelayPeerRegistration] {
        lock.withLock {
            guard let room = waitingRooms[relayID] else { return [] }
            return Self.orderedWaitingPeers(room.peers).map(\.registration)
        }
    }

    public func activeRoom(relayID: String) -> RelayActiveRoom? {
        lock.withLock {
            activeRooms[relayID]
        }
    }

    func waitingDeadlineUptime(relayID: String, peerID: UUID) -> TimeInterval? {
        lock.withLock {
            guard let room = waitingRooms[relayID],
                  room.peers.values.contains(where: { $0.registration.id == peerID })
            else {
                return nil
            }
            return room.deadlineUptime
        }
    }

    private func registerLocked(
        _ peer: RelayPeerRegistration,
        sourceIdentity: RelaySourceIdentity,
        requiresImmediateMatch: Bool,
        requiresSameSourceCounterpart: Bool = false,
        maximumWaitingDeadlineUptime: TimeInterval? = nil
    ) -> RelayRegistrationResult {
        guard activeRooms[peer.relayID] == nil else {
            return .rejected(.activeRoom)
        }
        guard peer.roomBinding?.relayID == peer.relayID || peer.roomBinding == nil else {
            return .rejected(.roomBindingMismatch)
        }

        guard var room = waitingRooms[peer.relayID] else {
            guard !requiresImmediateMatch else {
                return .rejected(.counterpartRequired)
            }
            if let rejection = admitWaitingPeer(
                sourceIdentity: sourceIdentity,
                authenticatedIdentity: peer.authenticatedIdentity
            ) {
                return .rejected(rejection)
            }
            let configuredDeadline = monotonicNow() + maximumWaitingDurationSeconds
            waitingRooms[peer.relayID] = WaitingRoom(
                roomBinding: peer.roomBinding,
                deadlineUptime: min(
                    configuredDeadline,
                    maximumWaitingDeadlineUptime ?? configuredDeadline
                ),
                peers: [
                    peer.role: WaitingPeer(
                        registration: peer,
                        sourceIdentity: sourceIdentity,
                        authenticatedIdentity: peer.authenticatedIdentity
                    )
                ]
            )
            return .waiting(replaced: nil)
        }
        guard room.roomBinding == peer.roomBinding else {
            return .rejected(.roomBindingMismatch)
        }

        if let replaced = room.peers[peer.role] {
            guard replaced.authenticatedIdentity == peer.authenticatedIdentity else {
                return .rejected(.roomBindingMismatch)
            }
            guard !requiresImmediateMatch || replaced.sourceIdentity == sourceIdentity else {
                return .rejected(.counterpartRequired)
            }
            guard replaceWaitingPeer(
                from: replaced.sourceIdentity,
                with: sourceIdentity
            ) else {
                return .rejected(.sourceWaitingPeerQuota)
            }
            room.peers[peer.role] = WaitingPeer(
                registration: peer,
                sourceIdentity: sourceIdentity,
                authenticatedIdentity: peer.authenticatedIdentity
            )
            waitingRooms[peer.relayID] = room
            return .waiting(replaced: replaced.registration)
        }

        let otherRole: RelayRole = peer.role == .runtime ? .client : .runtime
        guard let other = room.peers[otherRole] else {
            guard !requiresImmediateMatch else {
                return .rejected(.counterpartRequired)
            }
            if let rejection = admitWaitingPeer(
                sourceIdentity: sourceIdentity,
                authenticatedIdentity: peer.authenticatedIdentity
            ) {
                return .rejected(rejection)
            }
            room.peers[peer.role] = WaitingPeer(
                registration: peer,
                sourceIdentity: sourceIdentity,
                authenticatedIdentity: peer.authenticatedIdentity
            )
            waitingRooms[peer.relayID] = room
            return .waiting(replaced: nil)
        }
        guard !requiresSameSourceCounterpart || other.sourceIdentity == sourceIdentity else {
            return .rejected(.counterpartRequired)
        }

        sourceQuotaLimiter?.releaseWaitingPeer(source: other.sourceIdentity)
        waitingPeerLimiter?.releaseWaitingPeer(identity: other.authenticatedIdentity)
        let runtime = peer.role == .runtime ? peer : other.registration
        let client = peer.role == .client ? peer : other.registration
        let activeRoom = RelayActiveRoom(
            matchToken: RelayMatchToken(),
            runtime: runtime,
            client: client
        )
        waitingRooms.removeValue(forKey: peer.relayID)
        activeRooms[peer.relayID] = activeRoom
        activeRelayIDsByToken[activeRoom.matchToken] = peer.relayID
        return .matched(
            runtime: runtime,
            client: client,
            matchToken: activeRoom.matchToken
        )
    }

    private static let orderedRoles: [RelayRole] = [.runtime, .client]

    private func admitWaitingPeer(
        sourceIdentity: RelaySourceIdentity,
        authenticatedIdentity: RelayAuthenticatedPeerIdentity?
    ) -> RelayRegistrationRejection? {
        guard sourceQuotaLimiter?.acquireWaitingPeer(source: sourceIdentity).allowed ?? true else {
            return .sourceWaitingPeerQuota
        }
        guard waitingPeerLimiter?.acquireWaitingPeer(
            identity: authenticatedIdentity
        ).allowed ?? true else {
            sourceQuotaLimiter?.releaseWaitingPeer(source: sourceIdentity)
            return .authenticatedIdentityWaitingQuota
        }
        return nil
    }

    private func replaceWaitingPeer(
        from oldSource: RelaySourceIdentity,
        with newSource: RelaySourceIdentity
    ) -> Bool {
        sourceQuotaLimiter?.replaceWaitingPeer(from: oldSource, with: newSource).allowed ?? true
    }

    private static func orderedWaitingPeers(
        _ peers: [RelayRole: WaitingPeer]
    ) -> [WaitingPeer] {
        orderedRoles.compactMap { peers[$0] }
    }
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
