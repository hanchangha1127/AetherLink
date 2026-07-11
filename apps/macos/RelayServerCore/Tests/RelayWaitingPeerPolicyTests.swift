import XCTest
@testable import RelayServerCore

final class RelayWaitingPeerPolicyTests: XCTestCase {
    func testConfigurationDefaultsAndBounds() throws {
        let configuration = RelayWaitingPeerPolicyConfiguration()

        XCTAssertEqual(configuration.maximumDurationSeconds, 60)
        XCTAssertEqual(configuration.maximumPeersPerAuthenticatedIdentity, 4)
        XCTAssertNoThrow(try configuration.validate())

        for duration in [0, -1, 3_601, .infinity, .nan] {
            var invalid = configuration
            invalid.maximumDurationSeconds = duration
            XCTAssertThrowsError(try invalid.validate()) { error in
                XCTAssertEqual(
                    error as? RelayWaitingPeerPolicyConfigurationError,
                    .invalidMaximumDuration
                )
            }
        }
        for quota in [0, -1, 65_537] {
            var invalid = configuration
            invalid.maximumPeersPerAuthenticatedIdentity = quota
            XCTAssertThrowsError(try invalid.validate()) { error in
                XCTAssertEqual(
                    error as? RelayWaitingPeerPolicyConfigurationError,
                    .invalidAuthenticatedIdentityQuota
                )
            }
        }
    }

    func testUnauthenticatedWaitersRemainOutsideIdentityAccounting() {
        let limiter = RelayWaitingPeerLimiter(
            configuration: RelayWaitingPeerPolicyConfiguration(
                maximumDurationSeconds: 30,
                maximumPeersPerAuthenticatedIdentity: 1
            )
        )

        for _ in 0..<32 {
            XCTAssertTrue(limiter.acquireWaitingPeer(identity: nil).allowed)
            limiter.releaseWaitingPeer(identity: nil)
        }
        XCTAssertEqual(
            limiter.metricsSnapshot(),
            RelayWaitingPeerPolicyMetricsSnapshot(
                identityWaitingAdmissionRequestsTotal: 0,
                identityWaitingPeersAdmittedTotal: 0,
                identityWaitingQuotaRejectionsTotal: 0,
                waitingPeerTimeoutsTotal: 0,
                authenticatedIdentityWaitingPeers: 0,
                authenticatedIdentitiesWithWaiters: 0
            )
        )
    }

    func testIdentityQuotaIsAtomicAcrossSourcesAndRoleSeparated() throws {
        let runtimeIdentity = try XCTUnwrap(identity(.runtime, digit: "a"))
        let clientIdentity = try XCTUnwrap(identity(.client, digit: "a"))
        let limiter = RelayWaitingPeerLimiter(
            configuration: RelayWaitingPeerPolicyConfiguration(
                maximumDurationSeconds: 30,
                maximumPeersPerAuthenticatedIdentity: 8
            )
        )
        let admitted = PolicyLockedCounter()

        DispatchQueue.concurrentPerform(iterations: 128) { _ in
            if limiter.acquireWaitingPeer(identity: runtimeIdentity).allowed {
                admitted.increment()
            }
        }

        XCTAssertEqual(admitted.value, 8)
        XCTAssertTrue(limiter.acquireWaitingPeer(identity: clientIdentity).allowed)
        var metrics = limiter.metricsSnapshot()
        XCTAssertEqual(metrics.identityWaitingAdmissionRequestsTotal, 129)
        XCTAssertEqual(metrics.identityWaitingPeersAdmittedTotal, 9)
        XCTAssertEqual(metrics.identityWaitingQuotaRejectionsTotal, 120)
        XCTAssertEqual(metrics.authenticatedIdentityWaitingPeers, 9)
        XCTAssertEqual(metrics.authenticatedIdentitiesWithWaiters, 2)

        for _ in 0..<8 {
            limiter.releaseWaitingPeer(identity: runtimeIdentity)
        }
        limiter.releaseWaitingPeer(identity: clientIdentity)
        metrics = limiter.metricsSnapshot()
        XCTAssertEqual(metrics.authenticatedIdentityWaitingPeers, 0)
        XCTAssertEqual(metrics.authenticatedIdentitiesWithWaiters, 0)
    }

    func testTimeoutAndQuotaLogsExposeOnlyStableAggregateReasons() throws {
        let identity = try XCTUnwrap(identity(.runtime, digit: "b"))
        let log = WaitingPolicyLogCapture()
        let limiter = RelayWaitingPeerLimiter(
            configuration: RelayWaitingPeerPolicyConfiguration(
                maximumDurationSeconds: 30,
                maximumPeersPerAuthenticatedIdentity: 1
            ),
            rejectionLog: { log.append($0) }
        )

        XCTAssertTrue(limiter.acquireWaitingPeer(identity: identity).allowed)
        XCTAssertFalse(limiter.acquireWaitingPeer(identity: identity).allowed)
        limiter.recordWaitingPeerTimeout()

        let metrics = limiter.metricsSnapshot()
        XCTAssertEqual(metrics.identityWaitingQuotaRejectionsTotal, 1)
        XCTAssertEqual(metrics.waitingPeerTimeoutsTotal, 1)
        XCTAssertEqual(
            log.messages,
            [
                "reason=authenticated_identity_waiting_quota_reached reason_count=1",
                "reason=waiting_peer_timed_out reason_count=1"
            ]
        )
        XCTAssertFalse(log.messages.joined().contains(String(repeating: "b", count: 64)))
        XCTAssertEqual(RelayWaitingPeerLimiter.saturatingIncrement(.max), .max)
        limiter.releaseWaitingPeer(identity: identity)
    }

    private func identity(
        _ role: RelayRole,
        digit: Character
    ) -> RelayAuthenticatedPeerIdentity? {
        RelayAuthenticatedPeerIdentity(
            role: role,
            fingerprint: String(repeating: String(digit), count: 64)
        )
    }
}

private final class PolicyLockedCounter: @unchecked Sendable {
    private let lock = NSLock()
    private var storedValue = 0

    var value: Int {
        lock.lock()
        defer { lock.unlock() }
        return storedValue
    }

    func increment() {
        lock.lock()
        storedValue += 1
        lock.unlock()
    }
}

private final class WaitingPolicyLogCapture: @unchecked Sendable {
    private let lock = NSLock()
    private var storedMessages: [String] = []

    var messages: [String] {
        lock.lock()
        defer { lock.unlock() }
        return storedMessages
    }

    func append(_ message: String) {
        lock.lock()
        storedMessages.append(message)
        lock.unlock()
    }
}
