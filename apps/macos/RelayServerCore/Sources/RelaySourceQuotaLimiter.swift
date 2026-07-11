import Foundation

public struct RelaySourceQuotaConfiguration: Equatable, Sendable {
    public static let defaultMaximumConnectionsPerSource = 64
    public static let defaultMaximumWaitingPeersPerSource = 32
    public static let maximumValue = 65_536

    public var maximumConnectionsPerSource: Int
    public var maximumWaitingPeersPerSource: Int

    public init(
        maximumConnectionsPerSource: Int = Self.defaultMaximumConnectionsPerSource,
        maximumWaitingPeersPerSource: Int = Self.defaultMaximumWaitingPeersPerSource
    ) {
        self.maximumConnectionsPerSource = maximumConnectionsPerSource
        self.maximumWaitingPeersPerSource = maximumWaitingPeersPerSource
    }

    public func validate() throws {
        guard maximumConnectionsPerSource > 0,
              maximumConnectionsPerSource <= Self.maximumValue
        else {
            throw RelaySourceQuotaConfigurationError.invalidMaximumConnectionsPerSource
        }
        guard maximumWaitingPeersPerSource > 0,
              maximumWaitingPeersPerSource <= Self.maximumValue
        else {
            throw RelaySourceQuotaConfigurationError.invalidMaximumWaitingPeersPerSource
        }
        guard maximumWaitingPeersPerSource * 2 <= maximumConnectionsPerSource else {
            throw RelaySourceQuotaConfigurationError.insufficientCounterpartConnectionCapacity
        }
    }
}

public enum RelaySourceQuotaConfigurationError: Error, Equatable, Sendable {
    case invalidMaximumConnectionsPerSource
    case invalidMaximumWaitingPeersPerSource
    case insufficientCounterpartConnectionCapacity
}

public enum RelaySourceQuotaReason: String, Equatable, Sendable {
    case globalConnectionLimitReached = "global_connection_limit_reached"
    case sourceConnectionQuotaReached = "source_connection_quota_reached"
    case sourceWaitingPeerQuotaReached = "source_waiting_peer_quota_reached"
    case counterpartCandidateNotMatched = "counterpart_candidate_not_matched"
}

public enum RelaySourceQuotaMetricName: String, CaseIterable, Sendable {
    case connectionAdmissionRequestsTotal = "connection_admission_requests_total"
    case connectionsAdmittedTotal = "connections_admitted_total"
    case globalConnectionLimitRejectionsTotal = "global_connection_limit_rejections_total"
    case sourceConnectionQuotaRejectionsTotal = "source_connection_quota_rejections_total"
    case waitingPeerAdmissionRequestsTotal = "waiting_peer_admission_requests_total"
    case waitingPeersAdmittedTotal = "waiting_peers_admitted_total"
    case sourceWaitingPeerQuotaRejectionsTotal = "source_waiting_peer_quota_rejections_total"
    case counterpartCandidatesAdmittedTotal = "counterpart_candidates_admitted_total"
    case counterpartCandidatesConfirmedTotal = "counterpart_candidates_confirmed_total"
    case counterpartCandidatesRejectedTotal = "counterpart_candidates_rejected_total"
    case counterpartCandidatesCurrent = "counterpart_candidates_current"
    case activeConnections = "active_connections"
    case activeConnectionSources = "active_connection_sources"
    case waitingPeers = "waiting_peers"
    case waitingPeerSources = "waiting_peer_sources"
}

public struct RelaySourceQuotaMetricsSnapshot: Equatable, Sendable {
    public let connectionAdmissionRequestsTotal: UInt64
    public let connectionsAdmittedTotal: UInt64
    public let globalConnectionLimitRejectionsTotal: UInt64
    public let sourceConnectionQuotaRejectionsTotal: UInt64
    public let waitingPeerAdmissionRequestsTotal: UInt64
    public let waitingPeersAdmittedTotal: UInt64
    public let sourceWaitingPeerQuotaRejectionsTotal: UInt64
    public let counterpartCandidatesAdmittedTotal: UInt64
    public let counterpartCandidatesConfirmedTotal: UInt64
    public let counterpartCandidatesRejectedTotal: UInt64
    public let counterpartCandidatesCurrent: UInt64
    public let activeConnections: UInt64
    public let activeConnectionSources: UInt64
    public let waitingPeers: UInt64
    public let waitingPeerSources: UInt64

    public var valuesByName: [String: UInt64] {
        [
            RelaySourceQuotaMetricName.connectionAdmissionRequestsTotal.rawValue:
                connectionAdmissionRequestsTotal,
            RelaySourceQuotaMetricName.connectionsAdmittedTotal.rawValue: connectionsAdmittedTotal,
            RelaySourceQuotaMetricName.globalConnectionLimitRejectionsTotal.rawValue:
                globalConnectionLimitRejectionsTotal,
            RelaySourceQuotaMetricName.sourceConnectionQuotaRejectionsTotal.rawValue:
                sourceConnectionQuotaRejectionsTotal,
            RelaySourceQuotaMetricName.waitingPeerAdmissionRequestsTotal.rawValue:
                waitingPeerAdmissionRequestsTotal,
            RelaySourceQuotaMetricName.waitingPeersAdmittedTotal.rawValue:
                waitingPeersAdmittedTotal,
            RelaySourceQuotaMetricName.sourceWaitingPeerQuotaRejectionsTotal.rawValue:
                sourceWaitingPeerQuotaRejectionsTotal,
            RelaySourceQuotaMetricName.counterpartCandidatesAdmittedTotal.rawValue:
                counterpartCandidatesAdmittedTotal,
            RelaySourceQuotaMetricName.counterpartCandidatesConfirmedTotal.rawValue:
                counterpartCandidatesConfirmedTotal,
            RelaySourceQuotaMetricName.counterpartCandidatesRejectedTotal.rawValue:
                counterpartCandidatesRejectedTotal,
            RelaySourceQuotaMetricName.counterpartCandidatesCurrent.rawValue:
                counterpartCandidatesCurrent,
            RelaySourceQuotaMetricName.activeConnections.rawValue: activeConnections,
            RelaySourceQuotaMetricName.activeConnectionSources.rawValue: activeConnectionSources,
            RelaySourceQuotaMetricName.waitingPeers.rawValue: waitingPeers,
            RelaySourceQuotaMetricName.waitingPeerSources.rawValue: waitingPeerSources
        ]
    }
}

final class RelaySourceQuotaLimiter: @unchecked Sendable {
    struct Decision: Equatable, Sendable {
        let allowed: Bool
        let rejectionReason: RelaySourceQuotaReason?
        let reasonCount: UInt64
        let usesGlobalCounterpartReserve: Bool
        let usesSourceCounterpartReserve: Bool

        var usesCounterpartReserve: Bool {
            usesGlobalCounterpartReserve || usesSourceCounterpartReserve
        }

        init(
            allowed: Bool,
            rejectionReason: RelaySourceQuotaReason?,
            reasonCount: UInt64,
            usesGlobalCounterpartReserve: Bool = false,
            usesSourceCounterpartReserve: Bool = false
        ) {
            self.allowed = allowed
            self.rejectionReason = rejectionReason
            self.reasonCount = reasonCount
            self.usesGlobalCounterpartReserve = usesGlobalCounterpartReserve
            self.usesSourceCounterpartReserve = usesSourceCounterpartReserve
        }
    }

    private struct SourceState: Sendable {
        var connections = 0
        var waitingPeers = 0
        var counterpartCandidates = 0
    }

    private struct Metrics: Sendable {
        var connectionAdmissionRequestsTotal: UInt64 = 0
        var connectionsAdmittedTotal: UInt64 = 0
        var globalConnectionLimitRejectionsTotal: UInt64 = 0
        var sourceConnectionQuotaRejectionsTotal: UInt64 = 0
        var waitingPeerAdmissionRequestsTotal: UInt64 = 0
        var waitingPeersAdmittedTotal: UInt64 = 0
        var sourceWaitingPeerQuotaRejectionsTotal: UInt64 = 0
        var counterpartCandidatesAdmittedTotal: UInt64 = 0
        var counterpartCandidatesConfirmedTotal: UInt64 = 0
        var counterpartCandidatesRejectedTotal: UInt64 = 0
    }

    private let maximumConnections: Int
    private let configuration: RelaySourceQuotaConfiguration
    private let rejectionLog: @Sendable (String) -> Void
    private let lock = NSLock()
    private var sources: [RelaySourceIdentity: SourceState] = [:]
    private var totalConnections = 0
    private var totalWaitingPeers = 0
    private var totalCounterpartCandidates = 0
    private var metrics = Metrics()

    init(
        maximumConnections: Int,
        configuration: RelaySourceQuotaConfiguration,
        rejectionLog: @escaping @Sendable (String) -> Void = { _ in }
    ) {
        self.maximumConnections = maximumConnections
        self.configuration = configuration
        self.rejectionLog = rejectionLog
    }

    func acquireConnection(source: RelaySourceIdentity) -> Decision {
        let decision = lock.withLock { () -> Decision in
            metrics.connectionAdmissionRequestsTotal = Self.saturatingIncrement(
                metrics.connectionAdmissionRequestsTotal
            )
            guard totalConnections < maximumConnections else {
                metrics.globalConnectionLimitRejectionsTotal = Self.saturatingIncrement(
                    metrics.globalConnectionLimitRejectionsTotal
                )
                return Decision(
                    allowed: false,
                    rejectionReason: .globalConnectionLimitReached,
                    reasonCount: metrics.globalConnectionLimitRejectionsTotal
                )
            }

            var state = sources[source] ?? SourceState()
            guard state.connections < configuration.maximumConnectionsPerSource else {
                metrics.sourceConnectionQuotaRejectionsTotal = Self.saturatingIncrement(
                    metrics.sourceConnectionQuotaRejectionsTotal
                )
                return Decision(
                    allowed: false,
                    rejectionReason: .sourceConnectionQuotaReached,
                    reasonCount: metrics.sourceConnectionQuotaRejectionsTotal
                )
            }

            let globalReservedSlots = maximumConnections > 1
                ? max(1, totalWaitingPeers)
                : 0
            let sourceReservedSlots = max(1, state.waitingPeers)
            let usesGlobalReserve = totalConnections >=
                maximumConnections - globalReservedSlots
            let usesSourceReserve = state.connections >=
                configuration.maximumConnectionsPerSource - sourceReservedSlots
            if usesGlobalReserve {
                guard totalCounterpartCandidates < totalWaitingPeers else {
                    metrics.globalConnectionLimitRejectionsTotal = Self.saturatingIncrement(
                        metrics.globalConnectionLimitRejectionsTotal
                    )
                    return Decision(
                        allowed: false,
                        rejectionReason: .globalConnectionLimitReached,
                        reasonCount: metrics.globalConnectionLimitRejectionsTotal
                    )
                }
            }
            if usesSourceReserve {
                guard state.counterpartCandidates < state.waitingPeers else {
                    metrics.sourceConnectionQuotaRejectionsTotal = Self.saturatingIncrement(
                        metrics.sourceConnectionQuotaRejectionsTotal
                    )
                    return Decision(
                        allowed: false,
                        rejectionReason: .sourceConnectionQuotaReached,
                        reasonCount: metrics.sourceConnectionQuotaRejectionsTotal
                    )
                }
            }

            let usesCounterpartReserve = usesGlobalReserve || usesSourceReserve
            state.connections += 1
            if usesCounterpartReserve {
                state.counterpartCandidates += 1
                totalCounterpartCandidates += 1
                metrics.counterpartCandidatesAdmittedTotal = Self.saturatingIncrement(
                    metrics.counterpartCandidatesAdmittedTotal
                )
            }
            totalConnections += 1
            sources[source] = state
            metrics.connectionsAdmittedTotal = Self.saturatingIncrement(
                metrics.connectionsAdmittedTotal
            )
            return Decision(
                allowed: true,
                rejectionReason: nil,
                reasonCount: 0,
                usesGlobalCounterpartReserve: usesGlobalReserve,
                usesSourceCounterpartReserve: usesSourceReserve
            )
        }
        logRejection(decision)
        return decision
    }

    func confirmCounterpartCandidate(source: RelaySourceIdentity) {
        lock.withLock {
            guard var state = sources[source], state.counterpartCandidates > 0 else {
                preconditionFailure("confirmed an untracked counterpart candidate")
            }
            state.counterpartCandidates -= 1
            totalCounterpartCandidates -= 1
            sources[source] = state
            metrics.counterpartCandidatesConfirmedTotal = Self.saturatingIncrement(
                metrics.counterpartCandidatesConfirmedTotal
            )
        }
    }

    func releaseConnection(
        source: RelaySourceIdentity,
        wasCounterpartCandidate: Bool = false
    ) {
        let rejection = lock.withLock { () -> Decision? in
            guard var state = sources[source], state.connections > 0 else {
                preconditionFailure("released an untracked relay source connection")
            }
            var rejection: Decision?
            if wasCounterpartCandidate {
                guard state.counterpartCandidates > 0 else {
                    preconditionFailure("released an untracked counterpart candidate")
                }
                state.counterpartCandidates -= 1
                totalCounterpartCandidates -= 1
                metrics.counterpartCandidatesRejectedTotal = Self.saturatingIncrement(
                    metrics.counterpartCandidatesRejectedTotal
                )
                rejection = Decision(
                    allowed: false,
                    rejectionReason: .counterpartCandidateNotMatched,
                    reasonCount: metrics.counterpartCandidatesRejectedTotal
                )
            }
            state.connections -= 1
            totalConnections -= 1
            updateSource(source, state: state)
            return rejection
        }
        if let rejection {
            logRejection(rejection)
        }
    }

    func acquireWaitingPeer(source: RelaySourceIdentity) -> Decision {
        let decision = lock.withLock { () -> Decision in
            metrics.waitingPeerAdmissionRequestsTotal = Self.saturatingIncrement(
                metrics.waitingPeerAdmissionRequestsTotal
            )
            guard var state = sources[source], state.connections > 0 else {
                preconditionFailure("waiting peer has no admitted source connection")
            }
            guard state.waitingPeers < configuration.maximumWaitingPeersPerSource else {
                metrics.sourceWaitingPeerQuotaRejectionsTotal = Self.saturatingIncrement(
                    metrics.sourceWaitingPeerQuotaRejectionsTotal
                )
                return Decision(
                    allowed: false,
                    rejectionReason: .sourceWaitingPeerQuotaReached,
                    reasonCount: metrics.sourceWaitingPeerQuotaRejectionsTotal
                )
            }
            guard totalConnections + totalWaitingPeers + 1 <= maximumConnections,
                  state.connections + state.waitingPeers + 1 <=
                    configuration.maximumConnectionsPerSource
            else {
                metrics.sourceWaitingPeerQuotaRejectionsTotal = Self.saturatingIncrement(
                    metrics.sourceWaitingPeerQuotaRejectionsTotal
                )
                return Decision(
                    allowed: false,
                    rejectionReason: .sourceWaitingPeerQuotaReached,
                    reasonCount: metrics.sourceWaitingPeerQuotaRejectionsTotal
                )
            }
            state.waitingPeers += 1
            totalWaitingPeers += 1
            sources[source] = state
            metrics.waitingPeersAdmittedTotal = Self.saturatingIncrement(
                metrics.waitingPeersAdmittedTotal
            )
            return Decision(allowed: true, rejectionReason: nil, reasonCount: 0)
        }
        logRejection(decision)
        return decision
    }

    func replaceWaitingPeer(
        from oldSource: RelaySourceIdentity,
        with newSource: RelaySourceIdentity
    ) -> Decision {
        let decision = lock.withLock { () -> Decision in
            metrics.waitingPeerAdmissionRequestsTotal = Self.saturatingIncrement(
                metrics.waitingPeerAdmissionRequestsTotal
            )
            guard var oldState = sources[oldSource], oldState.waitingPeers > 0 else {
                preconditionFailure("replaced peer is not tracked as waiting")
            }
            guard var newState = sources[newSource], newState.connections > 0 else {
                preconditionFailure("replacement peer has no admitted source connection")
            }
            guard oldSource != newSource else {
                metrics.waitingPeersAdmittedTotal = Self.saturatingIncrement(
                    metrics.waitingPeersAdmittedTotal
                )
                return Decision(allowed: true, rejectionReason: nil, reasonCount: 0)
            }
            guard newState.waitingPeers < configuration.maximumWaitingPeersPerSource else {
                metrics.sourceWaitingPeerQuotaRejectionsTotal = Self.saturatingIncrement(
                    metrics.sourceWaitingPeerQuotaRejectionsTotal
                )
                return Decision(
                    allowed: false,
                    rejectionReason: .sourceWaitingPeerQuotaReached,
                    reasonCount: metrics.sourceWaitingPeerQuotaRejectionsTotal
                )
            }
            guard newState.connections + newState.waitingPeers + 1 <=
                configuration.maximumConnectionsPerSource
            else {
                metrics.sourceWaitingPeerQuotaRejectionsTotal = Self.saturatingIncrement(
                    metrics.sourceWaitingPeerQuotaRejectionsTotal
                )
                return Decision(
                    allowed: false,
                    rejectionReason: .sourceWaitingPeerQuotaReached,
                    reasonCount: metrics.sourceWaitingPeerQuotaRejectionsTotal
                )
            }
            oldState.waitingPeers -= 1
            newState.waitingPeers += 1
            updateSource(oldSource, state: oldState)
            sources[newSource] = newState
            metrics.waitingPeersAdmittedTotal = Self.saturatingIncrement(
                metrics.waitingPeersAdmittedTotal
            )
            return Decision(allowed: true, rejectionReason: nil, reasonCount: 0)
        }
        logRejection(decision)
        return decision
    }

    func releaseWaitingPeer(source: RelaySourceIdentity) {
        lock.withLock {
            guard var state = sources[source], state.waitingPeers > 0 else {
                preconditionFailure("released an untracked waiting peer")
            }
            state.waitingPeers -= 1
            totalWaitingPeers -= 1
            updateSource(source, state: state)
        }
    }

    func metricsSnapshot() -> RelaySourceQuotaMetricsSnapshot {
        lock.withLock {
            RelaySourceQuotaMetricsSnapshot(
                connectionAdmissionRequestsTotal: metrics.connectionAdmissionRequestsTotal,
                connectionsAdmittedTotal: metrics.connectionsAdmittedTotal,
                globalConnectionLimitRejectionsTotal:
                    metrics.globalConnectionLimitRejectionsTotal,
                sourceConnectionQuotaRejectionsTotal:
                    metrics.sourceConnectionQuotaRejectionsTotal,
                waitingPeerAdmissionRequestsTotal: metrics.waitingPeerAdmissionRequestsTotal,
                waitingPeersAdmittedTotal: metrics.waitingPeersAdmittedTotal,
                sourceWaitingPeerQuotaRejectionsTotal:
                    metrics.sourceWaitingPeerQuotaRejectionsTotal,
                counterpartCandidatesAdmittedTotal:
                    metrics.counterpartCandidatesAdmittedTotal,
                counterpartCandidatesConfirmedTotal:
                    metrics.counterpartCandidatesConfirmedTotal,
                counterpartCandidatesRejectedTotal:
                    metrics.counterpartCandidatesRejectedTotal,
                counterpartCandidatesCurrent: UInt64(totalCounterpartCandidates),
                activeConnections: UInt64(totalConnections),
                activeConnectionSources: UInt64(sources.count),
                waitingPeers: UInt64(totalWaitingPeers),
                waitingPeerSources: UInt64(
                    sources.values.lazy.filter { $0.waitingPeers > 0 }.count
                )
            )
        }
    }

    static func saturatingIncrement(_ value: UInt64) -> UInt64 {
        value == .max ? .max : value + 1
    }

    private func updateSource(_ source: RelaySourceIdentity, state: SourceState) {
        if state.connections == 0 && state.waitingPeers == 0 && state.counterpartCandidates == 0 {
            sources.removeValue(forKey: source)
        } else {
            sources[source] = state
        }
    }

    private func logRejection(_ decision: Decision) {
        guard let reason = decision.rejectionReason else { return }
        rejectionLog("reason=\(reason.rawValue) reason_count=\(decision.reasonCount)")
    }
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
