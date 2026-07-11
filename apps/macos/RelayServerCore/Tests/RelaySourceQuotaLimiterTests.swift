import Darwin
import Foundation
import XCTest
@testable import RelayServerCore

final class RelaySourceQuotaLimiterTests: XCTestCase {
    func testConfigurationDefaultsBoundsAndCounterpartHeadroom() throws {
        let configuration = RelaySourceQuotaConfiguration()

        XCTAssertEqual(configuration.maximumConnectionsPerSource, 64)
        XCTAssertEqual(configuration.maximumWaitingPeersPerSource, 32)
        XCTAssertNoThrow(try configuration.validate())

        for value in [0, -1, RelaySourceQuotaConfiguration.maximumValue + 1] {
            var invalid = configuration
            invalid.maximumConnectionsPerSource = value
            XCTAssertThrowsError(try invalid.validate()) { error in
                XCTAssertEqual(
                    error as? RelaySourceQuotaConfigurationError,
                    .invalidMaximumConnectionsPerSource
                )
            }
        }
        for value in [0, -1, RelaySourceQuotaConfiguration.maximumValue + 1] {
            var invalid = configuration
            invalid.maximumWaitingPeersPerSource = value
            XCTAssertThrowsError(try invalid.validate()) { error in
                XCTAssertEqual(
                    error as? RelaySourceQuotaConfigurationError,
                    .invalidMaximumWaitingPeersPerSource
                )
            }
        }
        XCTAssertThrowsError(
            try RelaySourceQuotaConfiguration(
                maximumConnectionsPerSource: 63,
                maximumWaitingPeersPerSource: 32
            ).validate()
        ) { error in
            XCTAssertEqual(
                error as? RelaySourceQuotaConfigurationError,
                .insufficientCounterpartConnectionCapacity
            )
        }
    }

    func testGlobalAndSourceConnectionQuotasAreAtomicAndReleaseExactState() throws {
        let sourceA = try sourceIdentity("192.0.2.10")
        let sourceB = try sourceIdentity("192.0.2.11")
        let sourceC = try sourceIdentity("192.0.2.12")
        let log = QuotaLogCapture()
        let limiter = RelaySourceQuotaLimiter(
            maximumConnections: 4,
            configuration: RelaySourceQuotaConfiguration(
                maximumConnectionsPerSource: 3,
                maximumWaitingPeersPerSource: 1
            ),
            rejectionLog: { log.append($0) }
        )

        XCTAssertTrue(limiter.acquireConnection(source: sourceA).allowed)
        XCTAssertTrue(limiter.acquireConnection(source: sourceA).allowed)
        XCTAssertEqual(
            limiter.acquireConnection(source: sourceA),
            .init(
                allowed: false,
                rejectionReason: .sourceConnectionQuotaReached,
                reasonCount: 1
            )
        )
        XCTAssertTrue(limiter.acquireConnection(source: sourceB).allowed)
        XCTAssertEqual(
            limiter.acquireConnection(source: sourceC),
            .init(
                allowed: false,
                rejectionReason: .globalConnectionLimitReached,
                reasonCount: 1
            )
        )

        var metrics = limiter.metricsSnapshot()
        XCTAssertEqual(metrics.connectionAdmissionRequestsTotal, 5)
        XCTAssertEqual(metrics.connectionsAdmittedTotal, 3)
        XCTAssertEqual(metrics.sourceConnectionQuotaRejectionsTotal, 1)
        XCTAssertEqual(metrics.globalConnectionLimitRejectionsTotal, 1)
        XCTAssertEqual(metrics.activeConnections, 3)
        XCTAssertEqual(metrics.activeConnectionSources, 2)
        XCTAssertEqual(
            log.messages,
            [
                "reason=source_connection_quota_reached reason_count=1",
                "reason=global_connection_limit_reached reason_count=1"
            ]
        )

        limiter.releaseConnection(source: sourceA)
        limiter.releaseConnection(source: sourceA)
        limiter.releaseConnection(source: sourceB)
        metrics = limiter.metricsSnapshot()
        XCTAssertEqual(metrics.activeConnections, 0)
        XCTAssertEqual(metrics.activeConnectionSources, 0)
    }

    func testWaitingQuotaReplacementAndReleasePreserveExactSourceOwnership() throws {
        let sourceA = try sourceIdentity("198.51.100.20")
        let sourceB = try sourceIdentity("198.51.100.21")
        let limiter = RelaySourceQuotaLimiter(
            maximumConnections: 8,
            configuration: RelaySourceQuotaConfiguration(
                maximumConnectionsPerSource: 4,
                maximumWaitingPeersPerSource: 1
            )
        )
        XCTAssertTrue(limiter.acquireConnection(source: sourceA).allowed)
        XCTAssertTrue(limiter.acquireConnection(source: sourceA).allowed)
        XCTAssertTrue(limiter.acquireConnection(source: sourceB).allowed)
        XCTAssertTrue(limiter.acquireConnection(source: sourceB).allowed)

        XCTAssertTrue(limiter.acquireWaitingPeer(source: sourceA).allowed)
        XCTAssertFalse(limiter.acquireWaitingPeer(source: sourceA).allowed)
        XCTAssertTrue(limiter.replaceWaitingPeer(from: sourceA, with: sourceA).allowed)
        XCTAssertTrue(limiter.acquireWaitingPeer(source: sourceB).allowed)
        XCTAssertFalse(limiter.replaceWaitingPeer(from: sourceA, with: sourceB).allowed)

        limiter.releaseWaitingPeer(source: sourceB)
        XCTAssertTrue(limiter.replaceWaitingPeer(from: sourceA, with: sourceB).allowed)
        var metrics = limiter.metricsSnapshot()
        XCTAssertEqual(metrics.waitingPeerAdmissionRequestsTotal, 6)
        XCTAssertEqual(metrics.waitingPeersAdmittedTotal, 4)
        XCTAssertEqual(metrics.sourceWaitingPeerQuotaRejectionsTotal, 2)
        XCTAssertEqual(metrics.waitingPeers, 1)
        XCTAssertEqual(metrics.waitingPeerSources, 1)

        limiter.releaseWaitingPeer(source: sourceB)
        limiter.releaseConnection(source: sourceA)
        limiter.releaseConnection(source: sourceA)
        limiter.releaseConnection(source: sourceB)
        limiter.releaseConnection(source: sourceB)
        metrics = limiter.metricsSnapshot()
        XCTAssertEqual(metrics.activeConnections, 0)
        XCTAssertEqual(metrics.waitingPeers, 0)
        XCTAssertEqual(metrics.activeConnectionSources, 0)
        XCTAssertEqual(metrics.waitingPeerSources, 0)
    }

    func testCounterpartReserveRejectsNonmatchThenConfirmsValidCandidate() throws {
        let source = try sourceIdentity("198.51.100.30")
        let log = QuotaLogCapture()
        let limiter = RelaySourceQuotaLimiter(
            maximumConnections: 4,
            configuration: RelaySourceQuotaConfiguration(
                maximumConnectionsPerSource: 4,
                maximumWaitingPeersPerSource: 2
            ),
            rejectionLog: { log.append($0) }
        )

        XCTAssertFalse(limiter.acquireConnection(source: source).usesCounterpartReserve)
        XCTAssertFalse(limiter.acquireConnection(source: source).usesCounterpartReserve)
        XCTAssertFalse(limiter.acquireConnection(source: source).usesCounterpartReserve)
        XCTAssertTrue(limiter.acquireWaitingPeer(source: source).allowed)

        let nonmatch = limiter.acquireConnection(source: source)
        XCTAssertTrue(nonmatch.allowed)
        XCTAssertTrue(nonmatch.usesCounterpartReserve)
        XCTAssertTrue(nonmatch.usesGlobalCounterpartReserve)
        XCTAssertTrue(nonmatch.usesSourceCounterpartReserve)
        limiter.releaseConnection(source: source, wasCounterpartCandidate: true)

        let counterpart = limiter.acquireConnection(source: source)
        XCTAssertTrue(counterpart.allowed)
        XCTAssertTrue(counterpart.usesCounterpartReserve)
        limiter.confirmCounterpartCandidate(source: source)
        limiter.releaseWaitingPeer(source: source)

        var metrics = limiter.metricsSnapshot()
        XCTAssertEqual(metrics.counterpartCandidatesAdmittedTotal, 2)
        XCTAssertEqual(metrics.counterpartCandidatesConfirmedTotal, 1)
        XCTAssertEqual(metrics.counterpartCandidatesRejectedTotal, 1)
        XCTAssertEqual(metrics.counterpartCandidatesCurrent, 0)
        XCTAssertEqual(
            log.messages,
            ["reason=counterpart_candidate_not_matched reason_count=1"]
        )

        for _ in 0..<4 {
            limiter.releaseConnection(source: source)
        }
        metrics = limiter.metricsSnapshot()
        XCTAssertEqual(metrics.activeConnections, 0)
        XCTAssertEqual(metrics.activeConnectionSources, 0)
    }

    func testNormalAdmissionPreservesGlobalAndSourceCounterpartCapacity() throws {
        let source = try sourceIdentity("198.51.100.31")
        do {
            let limiter = RelaySourceQuotaLimiter(
                maximumConnections: 4,
                configuration: RelaySourceQuotaConfiguration(
                    maximumConnectionsPerSource: 8,
                    maximumWaitingPeersPerSource: 1
                )
            )

            for _ in 0..<3 {
                XCTAssertTrue(limiter.acquireConnection(source: source).allowed)
            }
            XCTAssertEqual(
                limiter.acquireConnection(source: source),
                .init(
                    allowed: false,
                    rejectionReason: .globalConnectionLimitReached,
                    reasonCount: 1
                )
            )
            XCTAssertTrue(limiter.acquireWaitingPeer(source: source).allowed)
            let candidate = limiter.acquireConnection(source: source)
            XCTAssertTrue(candidate.allowed)
            XCTAssertTrue(candidate.usesCounterpartReserve)
            XCTAssertTrue(candidate.usesGlobalCounterpartReserve)
            XCTAssertFalse(candidate.usesSourceCounterpartReserve)
            limiter.confirmCounterpartCandidate(source: source)
            limiter.releaseWaitingPeer(source: source)
            for _ in 0..<4 {
                limiter.releaseConnection(source: source)
            }
        }

        do {
            let limiter = RelaySourceQuotaLimiter(
                maximumConnections: 8,
                configuration: RelaySourceQuotaConfiguration(
                    maximumConnectionsPerSource: 4,
                    maximumWaitingPeersPerSource: 1
                )
            )

            for _ in 0..<3 {
                XCTAssertTrue(limiter.acquireConnection(source: source).allowed)
            }
            XCTAssertEqual(
                limiter.acquireConnection(source: source),
                .init(
                    allowed: false,
                    rejectionReason: .sourceConnectionQuotaReached,
                    reasonCount: 1
                )
            )
            XCTAssertTrue(limiter.acquireWaitingPeer(source: source).allowed)
            let candidate = limiter.acquireConnection(source: source)
            XCTAssertTrue(candidate.allowed)
            XCTAssertTrue(candidate.usesCounterpartReserve)
            XCTAssertFalse(candidate.usesGlobalCounterpartReserve)
            XCTAssertTrue(candidate.usesSourceCounterpartReserve)
            limiter.confirmCounterpartCandidate(source: source)
            limiter.releaseWaitingPeer(source: source)
            for _ in 0..<4 {
                limiter.releaseConnection(source: source)
            }
        }

        do {
            let limiter = RelaySourceQuotaLimiter(
                maximumConnections: 1,
                configuration: RelaySourceQuotaConfiguration(
                    maximumConnectionsPerSource: 2,
                    maximumWaitingPeersPerSource: 1
                )
            )

            XCTAssertTrue(limiter.acquireConnection(source: source).allowed)
            XCTAssertEqual(
                limiter.acquireWaitingPeer(source: source),
                .init(
                    allowed: false,
                    rejectionReason: .sourceWaitingPeerQuotaReached,
                    reasonCount: 1
                )
            )
            XCTAssertEqual(limiter.metricsSnapshot().waitingPeers, 0)
            limiter.releaseConnection(source: source)
        }
    }

    func testConcurrentConnectionAdmissionsCannotOvershootSourceQuota() throws {
        let source = try sourceIdentity("203.0.113.30")
        let limiter = RelaySourceQuotaLimiter(
            maximumConnections: 64,
            configuration: RelaySourceQuotaConfiguration(
                maximumConnectionsPerSource: 8,
                maximumWaitingPeersPerSource: 4
            )
        )
        let admitted = LockedCounter()

        DispatchQueue.concurrentPerform(iterations: 128) { _ in
            if limiter.acquireConnection(source: source).allowed {
                admitted.increment()
            }
        }

        XCTAssertEqual(admitted.value, 7)
        XCTAssertEqual(limiter.metricsSnapshot().activeConnections, 7)
        for _ in 0..<admitted.value {
            limiter.releaseConnection(source: source)
        }
        XCTAssertEqual(limiter.metricsSnapshot().activeConnections, 0)
    }

    func testMetricsKeysSaturateAndNeverExposeSourceIdentity() throws {
        let source = try sourceIdentity("203.0.113.44")
        let limiter = RelaySourceQuotaLimiter(
            maximumConnections: 1,
            configuration: RelaySourceQuotaConfiguration(
                maximumConnectionsPerSource: 2,
                maximumWaitingPeersPerSource: 1
            )
        )
        XCTAssertTrue(limiter.acquireConnection(source: source).allowed)
        XCTAssertFalse(limiter.acquireConnection(source: source).allowed)

        let values = limiter.metricsSnapshot().valuesByName
        XCTAssertEqual(Set(values.keys), Set(RelaySourceQuotaMetricName.allCases.map(\.rawValue)))
        XCTAssertFalse(String(describing: values).contains("203.0.113.44"))
        XCTAssertEqual(RelaySourceQuotaLimiter.saturatingIncrement(UInt64.max), UInt64.max)
        XCTAssertEqual(RelaySourceQuotaLimiter.saturatingIncrement(UInt64.max - 1), UInt64.max)
        limiter.releaseConnection(source: source)
    }

    private func sourceIdentity(_ addressText: String) throws -> RelaySourceIdentity {
        var address = sockaddr_in()
        address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        address.sin_family = sa_family_t(AF_INET)
        guard inet_pton(AF_INET, addressText, &address.sin_addr) == 1 else {
            throw QuotaTestError.invalidAddress
        }
        return withUnsafePointer(to: &address) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                RelaySourceIdentity(
                    sockaddr: $0,
                    length: socklen_t(MemoryLayout<sockaddr_in>.size)
                )
            }
        }
    }
}

private final class QuotaLogCapture: @unchecked Sendable {
    private let lock = NSLock()
    private var storage: [String] = []

    var messages: [String] {
        lock.lock()
        defer { lock.unlock() }
        return storage
    }

    func append(_ message: String) {
        lock.lock()
        storage.append(message)
        lock.unlock()
    }
}

private final class LockedCounter: @unchecked Sendable {
    private let lock = NSLock()
    private var storage = 0

    var value: Int {
        lock.lock()
        defer { lock.unlock() }
        return storage
    }

    func increment() {
        lock.lock()
        storage += 1
        lock.unlock()
    }
}

private enum QuotaTestError: Error {
    case invalidAddress
}
