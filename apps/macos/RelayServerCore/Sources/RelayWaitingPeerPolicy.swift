import Foundation
import BridgeProtocol

public struct RelayWaitingPeerPolicyConfiguration: Equatable, Sendable {
    public static let defaultMaximumDurationSeconds: TimeInterval = 60
    public static let defaultMaximumPeersPerAuthenticatedIdentity = 4
    public static let maximumDurationSeconds: TimeInterval = 3_600
    public static let maximumIdentityQuota = 65_536

    public var maximumDurationSeconds: TimeInterval
    public var maximumPeersPerAuthenticatedIdentity: Int

    public init(
        maximumDurationSeconds: TimeInterval = Self.defaultMaximumDurationSeconds,
        maximumPeersPerAuthenticatedIdentity: Int =
            Self.defaultMaximumPeersPerAuthenticatedIdentity
    ) {
        self.maximumDurationSeconds = maximumDurationSeconds
        self.maximumPeersPerAuthenticatedIdentity = maximumPeersPerAuthenticatedIdentity
    }

    public func validate() throws {
        guard maximumDurationSeconds.isFinite,
              maximumDurationSeconds > 0,
              maximumDurationSeconds <= Self.maximumDurationSeconds
        else {
            throw RelayWaitingPeerPolicyConfigurationError.invalidMaximumDuration
        }
        guard maximumPeersPerAuthenticatedIdentity > 0,
              maximumPeersPerAuthenticatedIdentity <= Self.maximumIdentityQuota
        else {
            throw RelayWaitingPeerPolicyConfigurationError.invalidAuthenticatedIdentityQuota
        }
    }
}

public enum RelayWaitingPeerPolicyConfigurationError: Error, Equatable, Sendable {
    case invalidMaximumDuration
    case invalidAuthenticatedIdentityQuota
}

enum RelayAuthenticatedPeerKind: String, Sendable {
    case runtime
    case client
}

struct RelayAuthenticatedPeerIdentity: Hashable, Sendable {
    let kind: RelayAuthenticatedPeerKind
    private let fingerprint: String

    init?(role: RelayRole, fingerprint: String?) {
        guard let fingerprint,
              RelayRuntimeIdentity.isCanonicalFingerprint(fingerprint)
        else {
            return nil
        }
        kind = role == .runtime ? .runtime : .client
        self.fingerprint = fingerprint
    }
}

public enum RelayWaitingPeerPolicyReason: String, Equatable, Sendable {
    case authenticatedIdentityWaitingQuotaReached =
        "authenticated_identity_waiting_quota_reached"
    case waitingPeerTimedOut = "waiting_peer_timed_out"
}

public enum RelayWaitingPeerPolicyMetricName: String, CaseIterable, Sendable {
    case identityWaitingAdmissionRequestsTotal =
        "identity_waiting_admission_requests_total"
    case identityWaitingPeersAdmittedTotal = "identity_waiting_peers_admitted_total"
    case identityWaitingQuotaRejectionsTotal =
        "identity_waiting_quota_rejections_total"
    case waitingPeerTimeoutsTotal = "waiting_peer_timeouts_total"
    case authenticatedIdentityWaitingPeers = "authenticated_identity_waiting_peers"
    case authenticatedIdentitiesWithWaiters = "authenticated_identities_with_waiters"
}

public struct RelayWaitingPeerPolicyMetricsSnapshot: Equatable, Sendable {
    public let identityWaitingAdmissionRequestsTotal: UInt64
    public let identityWaitingPeersAdmittedTotal: UInt64
    public let identityWaitingQuotaRejectionsTotal: UInt64
    public let waitingPeerTimeoutsTotal: UInt64
    public let authenticatedIdentityWaitingPeers: UInt64
    public let authenticatedIdentitiesWithWaiters: UInt64

    public var valuesByName: [String: UInt64] {
        [
            RelayWaitingPeerPolicyMetricName.identityWaitingAdmissionRequestsTotal.rawValue:
                identityWaitingAdmissionRequestsTotal,
            RelayWaitingPeerPolicyMetricName.identityWaitingPeersAdmittedTotal.rawValue:
                identityWaitingPeersAdmittedTotal,
            RelayWaitingPeerPolicyMetricName.identityWaitingQuotaRejectionsTotal.rawValue:
                identityWaitingQuotaRejectionsTotal,
            RelayWaitingPeerPolicyMetricName.waitingPeerTimeoutsTotal.rawValue:
                waitingPeerTimeoutsTotal,
            RelayWaitingPeerPolicyMetricName.authenticatedIdentityWaitingPeers.rawValue:
                authenticatedIdentityWaitingPeers,
            RelayWaitingPeerPolicyMetricName.authenticatedIdentitiesWithWaiters.rawValue:
                authenticatedIdentitiesWithWaiters
        ]
    }
}

final class RelayWaitingPeerLimiter: @unchecked Sendable {
    struct Decision: Equatable, Sendable {
        let allowed: Bool
        let rejectionReason: RelayWaitingPeerPolicyReason?
        let reasonCount: UInt64
    }

    private struct Metrics: Sendable {
        var identityWaitingAdmissionRequestsTotal: UInt64 = 0
        var identityWaitingPeersAdmittedTotal: UInt64 = 0
        var identityWaitingQuotaRejectionsTotal: UInt64 = 0
        var waitingPeerTimeoutsTotal: UInt64 = 0
    }

    private let configuration: RelayWaitingPeerPolicyConfiguration
    private let rejectionLog: @Sendable (String) -> Void
    private let lock = NSLock()
    private var waitingPeersByIdentity: [RelayAuthenticatedPeerIdentity: Int] = [:]
    private var totalAuthenticatedIdentityWaitingPeers = 0
    private var metrics = Metrics()

    init(
        configuration: RelayWaitingPeerPolicyConfiguration,
        rejectionLog: @escaping @Sendable (String) -> Void = { _ in }
    ) {
        self.configuration = configuration
        self.rejectionLog = rejectionLog
    }

    func acquireWaitingPeer(identity: RelayAuthenticatedPeerIdentity?) -> Decision {
        guard let identity else {
            return Decision(allowed: true, rejectionReason: nil, reasonCount: 0)
        }
        let decision = lock.withLock { () -> Decision in
            metrics.identityWaitingAdmissionRequestsTotal = Self.saturatingIncrement(
                metrics.identityWaitingAdmissionRequestsTotal
            )
            let current = waitingPeersByIdentity[identity] ?? 0
            guard current < configuration.maximumPeersPerAuthenticatedIdentity else {
                metrics.identityWaitingQuotaRejectionsTotal = Self.saturatingIncrement(
                    metrics.identityWaitingQuotaRejectionsTotal
                )
                return Decision(
                    allowed: false,
                    rejectionReason: .authenticatedIdentityWaitingQuotaReached,
                    reasonCount: metrics.identityWaitingQuotaRejectionsTotal
                )
            }
            waitingPeersByIdentity[identity] = current + 1
            totalAuthenticatedIdentityWaitingPeers += 1
            metrics.identityWaitingPeersAdmittedTotal = Self.saturatingIncrement(
                metrics.identityWaitingPeersAdmittedTotal
            )
            return Decision(allowed: true, rejectionReason: nil, reasonCount: 0)
        }
        logRejection(decision)
        return decision
    }

    func releaseWaitingPeer(identity: RelayAuthenticatedPeerIdentity?) {
        guard let identity else { return }
        lock.withLock {
            guard let current = waitingPeersByIdentity[identity], current > 0 else {
                preconditionFailure("released an untracked authenticated identity waiter")
            }
            if current == 1 {
                waitingPeersByIdentity.removeValue(forKey: identity)
            } else {
                waitingPeersByIdentity[identity] = current - 1
            }
            totalAuthenticatedIdentityWaitingPeers -= 1
        }
    }

    func recordWaitingPeerTimeout() {
        let count = lock.withLock { () -> UInt64 in
            metrics.waitingPeerTimeoutsTotal = Self.saturatingIncrement(
                metrics.waitingPeerTimeoutsTotal
            )
            return metrics.waitingPeerTimeoutsTotal
        }
        rejectionLog(
            "reason=\(RelayWaitingPeerPolicyReason.waitingPeerTimedOut.rawValue) " +
                "reason_count=\(count)"
        )
    }

    func metricsSnapshot() -> RelayWaitingPeerPolicyMetricsSnapshot {
        lock.withLock {
            RelayWaitingPeerPolicyMetricsSnapshot(
                identityWaitingAdmissionRequestsTotal:
                    metrics.identityWaitingAdmissionRequestsTotal,
                identityWaitingPeersAdmittedTotal: metrics.identityWaitingPeersAdmittedTotal,
                identityWaitingQuotaRejectionsTotal:
                    metrics.identityWaitingQuotaRejectionsTotal,
                waitingPeerTimeoutsTotal: metrics.waitingPeerTimeoutsTotal,
                authenticatedIdentityWaitingPeers:
                    UInt64(totalAuthenticatedIdentityWaitingPeers),
                authenticatedIdentitiesWithWaiters: UInt64(waitingPeersByIdentity.count)
            )
        }
    }

    static func saturatingIncrement(_ value: UInt64) -> UInt64 {
        value == .max ? .max : value + 1
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
