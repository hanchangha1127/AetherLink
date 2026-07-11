import Darwin
import Foundation
import XCTest
@testable import RelayServerCore

final class RelaySourceRateLimiterTests: XCTestCase {
    func testConfigurationDefaultsAndValidationBounds() throws {
        let configuration = RelaySourceRateLimitConfiguration()

        XCTAssertEqual(configuration.preflightRequestsPerMinute, 120)
        XCTAssertEqual(configuration.preflightBurst, 30)
        XCTAssertEqual(configuration.allocationMutationRequestsPerMinute, 30)
        XCTAssertEqual(configuration.allocationMutationBurst, 10)
        XCTAssertEqual(configuration.maximumTrackedSources, 4_096)
        XCTAssertEqual(configuration.idleRetentionSeconds, 15 * 60)
        XCTAssertNoThrow(try configuration.validate())

        var invalid = configuration
        invalid.preflightRequestsPerMinute = 0
        XCTAssertThrowsError(try invalid.validate()) { error in
            XCTAssertEqual(
                error as? RelaySourceRateLimitConfigurationError,
                .invalidPreflightRequestsPerMinute
            )
        }
        invalid = configuration
        invalid.preflightRequestsPerMinute = .infinity
        XCTAssertThrowsError(try invalid.validate())
        invalid = configuration
        invalid.preflightBurst = RelaySourceRateLimitConfiguration.maximumBurst + 1
        XCTAssertThrowsError(try invalid.validate()) { error in
            XCTAssertEqual(
                error as? RelaySourceRateLimitConfigurationError,
                .invalidPreflightBurst
            )
        }
        invalid = configuration
        invalid.allocationMutationRequestsPerMinute = .nan
        XCTAssertThrowsError(try invalid.validate()) { error in
            XCTAssertEqual(
                error as? RelaySourceRateLimitConfigurationError,
                .invalidAllocationMutationRequestsPerMinute
            )
        }
        invalid = configuration
        invalid.allocationMutationBurst = 0
        XCTAssertThrowsError(try invalid.validate()) { error in
            XCTAssertEqual(
                error as? RelaySourceRateLimitConfigurationError,
                .invalidAllocationMutationBurst
            )
        }
        invalid = configuration
        invalid.maximumTrackedSources = 0
        XCTAssertThrowsError(try invalid.validate()) { error in
            XCTAssertEqual(
                error as? RelaySourceRateLimitConfigurationError,
                .invalidMaximumTrackedSources
            )
        }
        invalid = configuration
        invalid.idleRetentionSeconds = RelaySourceRateLimitConfiguration.maximumIdleRetentionSeconds + 1
        XCTAssertThrowsError(try invalid.validate()) { error in
            XCTAssertEqual(
                error as? RelaySourceRateLimitConfigurationError,
                .invalidIdleRetentionSeconds
            )
        }
        invalid = configuration
        invalid.preflightRequestsPerMinute = 1
        invalid.preflightBurst = 16
        invalid.idleRetentionSeconds = 15 * 60
        XCTAssertThrowsError(try invalid.validate()) { error in
            XCTAssertEqual(
                error as? RelaySourceRateLimitConfigurationError,
                .idleRetentionTooShortForBurstRefill
            )
        }
        invalid = configuration
        invalid.allocationMutationRequestsPerMinute = 1
        invalid.allocationMutationBurst = 16
        invalid.idleRetentionSeconds = 15 * 60
        XCTAssertThrowsError(try invalid.validate()) { error in
            XCTAssertEqual(
                error as? RelaySourceRateLimitConfigurationError,
                .idleRetentionTooShortForBurstRefill
            )
        }
    }

    func testTokenBurstRefillAndBackwardClockMovement() throws {
        let clock = TestMonotonicClock(100)
        let limiter = RelaySourceRateLimiter(
            configuration: RelaySourceRateLimitConfiguration(
                preflightRequestsPerMinute: 60,
                preflightBurst: 2,
                allocationMutationRequestsPerMinute: 60,
                allocationMutationBurst: 1
            ),
            monotonicNow: { clock.now() }
        )
        let source = try sourceIdentity("192.0.2.10", family: AF_INET)

        XCTAssertTrue(limiter.evaluate(source: source, kind: .preflight).allowed)
        XCTAssertTrue(limiter.evaluate(source: source, kind: .preflight).allowed)
        XCTAssertEqual(
            limiter.evaluate(source: source, kind: .preflight),
            .init(
                allowed: false,
                rejectionReason: .allocationPreflightSourceRateLimited,
                reasonCount: 1
            )
        )

        clock.set(100.5)
        XCTAssertFalse(limiter.evaluate(source: source, kind: .preflight).allowed)
        clock.set(101)
        XCTAssertTrue(limiter.evaluate(source: source, kind: .preflight).allowed)

        clock.set(90)
        XCTAssertFalse(limiter.evaluate(source: source, kind: .preflight).allowed)
        clock.set(101.5)
        XCTAssertFalse(limiter.evaluate(source: source, kind: .preflight).allowed)
        clock.set(102)
        XCTAssertTrue(limiter.evaluate(source: source, kind: .preflight).allowed)

        let metrics = limiter.metricsSnapshot()
        XCTAssertEqual(metrics.allocationPreflightRequestsTotal, 8)
        XCTAssertEqual(metrics.allocationPreflightSourceRateLimitedTotal, 4)
    }

    func testPreflightAndAllocationMutationUseSeparateBuckets() throws {
        let clock = TestMonotonicClock(10)
        let limiter = RelaySourceRateLimiter(
            configuration: RelaySourceRateLimitConfiguration(
                preflightRequestsPerMinute: 6,
                preflightBurst: 1,
                allocationMutationRequestsPerMinute: 6,
                allocationMutationBurst: 1
            ),
            monotonicNow: { clock.now() }
        )
        let source = try sourceIdentity("198.51.100.7", family: AF_INET)

        XCTAssertTrue(limiter.evaluate(source: source, kind: .preflight).allowed)
        XCTAssertFalse(limiter.evaluate(source: source, kind: .preflight).allowed)
        XCTAssertTrue(limiter.evaluate(source: source, kind: .allocationMutation).allowed)
        XCTAssertFalse(limiter.evaluate(source: source, kind: .allocationMutation).allowed)

        let metrics = limiter.metricsSnapshot()
        XCTAssertEqual(metrics.allocationPreflightRequestsTotal, 2)
        XCTAssertEqual(metrics.allocationMutationRequestsTotal, 2)
        XCTAssertEqual(metrics.allocationPreflightSourceRateLimitedTotal, 1)
        XCTAssertEqual(metrics.allocationMutationSourceRateLimitedTotal, 1)
    }

    func testIPv4IPv6MappedCanonicalityAndSharedUnknownIdentity() throws {
        let ipv4 = try sourceIdentity("203.0.113.9", family: AF_INET)
        let mappedIPv4 = try sourceIdentity("::ffff:203.0.113.9", family: AF_INET6)
        let ipv6 = try sourceIdentity("2001:db8::9", family: AF_INET6)
        let sameIPv6 = try sourceIdentity("2001:db8::9", family: AF_INET6)
        let scopedIPv6A = try sourceIdentity("fe80::9", family: AF_INET6, scopeID: 4)
        let sameScopedIPv6A = try sourceIdentity("fe80::9", family: AF_INET6, scopeID: 4)
        let scopedIPv6B = try sourceIdentity("fe80::9", family: AF_INET6, scopeID: 5)

        XCTAssertEqual(ipv4, mappedIPv4)
        XCTAssertEqual(ipv6, sameIPv6)
        XCTAssertNotEqual(ipv4, ipv6)
        XCTAssertEqual(scopedIPv6A, sameScopedIPv6A)
        XCTAssertNotEqual(scopedIPv6A, scopedIPv6B)
        XCTAssertEqual(unknownSourceIdentity(family: AF_UNIX), .unknown)
        XCTAssertEqual(
            unknownSourceIdentity(family: AF_UNSPEC),
            unknownSourceIdentity(family: AF_UNIX)
        )
    }

    func testMemoryCapUsesSharedOverflowWithoutBucketResetAndCleansIdleState() throws {
        let clock = TestMonotonicClock(100)
        let limiter = RelaySourceRateLimiter(
            configuration: RelaySourceRateLimitConfiguration(
                preflightRequestsPerMinute: 1,
                preflightBurst: 1,
                allocationMutationRequestsPerMinute: 1,
                allocationMutationBurst: 1,
                maximumTrackedSources: 2,
                idleRetentionSeconds: 10
            ),
            monotonicNow: { clock.now() }
        )
        let sourceA = try sourceIdentity("192.0.2.1", family: AF_INET)
        let sourceB = try sourceIdentity("192.0.2.2", family: AF_INET)
        let sourceC = try sourceIdentity("192.0.2.3", family: AF_INET)

        XCTAssertTrue(limiter.evaluate(source: sourceA, kind: .preflight).allowed)
        XCTAssertFalse(limiter.evaluate(source: sourceA, kind: .preflight).allowed)
        XCTAssertTrue(limiter.evaluate(source: sourceB, kind: .preflight).allowed)
        XCTAssertFalse(limiter.evaluate(source: sourceC, kind: .preflight).allowed)
        XCTAssertFalse(limiter.evaluate(source: sourceA, kind: .preflight).allowed)
        XCTAssertFalse(limiter.evaluate(source: sourceB, kind: .preflight).allowed)
        var metrics = limiter.metricsSnapshot()
        XCTAssertEqual(metrics.rateLimitOverflowRequestsTotal, 3)
        XCTAssertEqual(metrics.rateLimitIdleSweepsTotal, 1)
        XCTAssertEqual(metrics.rateLimitSourceEvictionsTotal, 0)
        XCTAssertEqual(metrics.trackedSourceCount, 2)

        clock.set(120)
        metrics = limiter.metricsSnapshot()
        XCTAssertEqual(metrics.rateLimitIdleSweepsTotal, 2)
        XCTAssertEqual(metrics.rateLimitSourceEvictionsTotal, 2)
        XCTAssertEqual(metrics.trackedSourceCount, 0)
        XCTAssertTrue(limiter.evaluate(source: sourceA, kind: .preflight).allowed)
    }

    func testStableSourceFreeMetricsAndSaturatingCounterContract() throws {
        let clock = TestMonotonicClock(1)
        let limiter = RelaySourceRateLimiter(
            configuration: RelaySourceRateLimitConfiguration(
                preflightRequestsPerMinute: 1,
                preflightBurst: 1,
                allocationMutationRequestsPerMinute: 1,
                allocationMutationBurst: 1
            ),
            monotonicNow: { clock.now() }
        )
        let source = try sourceIdentity("203.0.113.44", family: AF_INET)
        _ = limiter.evaluate(source: source, kind: .preflight)
        _ = limiter.evaluate(source: source, kind: .preflight)
        _ = limiter.evaluate(source: source, kind: .allocationMutation)
        _ = limiter.evaluate(source: source, kind: .allocationMutation)

        let values = limiter.metricsSnapshot().valuesByName
        XCTAssertEqual(
            Set(values.keys),
            Set(RelaySourceRateLimitMetricName.allCases.map(\.rawValue))
        )
        XCTAssertEqual(values["allocation_preflight_requests_total"], 2)
        XCTAssertEqual(values["allocation_mutation_requests_total"], 2)
        XCTAssertEqual(values["allocation_preflight_source_rate_limited_total"], 1)
        XCTAssertEqual(values["allocation_mutation_source_rate_limited_total"], 1)
        XCTAssertEqual(values["rate_limit_overflow_requests_total"], 0)
        XCTAssertEqual(values["rate_limit_idle_sweeps_total"], 1)
        XCTAssertEqual(values["rate_limit_source_evictions_total"], 0)
        XCTAssertEqual(values["rate_limit_tracked_sources"], 1)
        XCTAssertFalse(String(describing: values).contains("203.0.113.44"))

        XCTAssertEqual(RelaySourceRateLimiter.saturatingIncrement(UInt64.max), UInt64.max)
        XCTAssertEqual(RelaySourceRateLimiter.saturatingIncrement(UInt64.max - 1), UInt64.max)
    }

    private func sourceIdentity(
        _ addressText: String,
        family: Int32,
        scopeID: UInt32 = 0
    ) throws -> RelaySourceIdentity {
        if family == AF_INET {
            var address = sockaddr_in()
            address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
            address.sin_family = sa_family_t(AF_INET)
            guard inet_pton(AF_INET, addressText, &address.sin_addr) == 1 else {
                throw SourceIdentityTestError.invalidAddress
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

        var address = sockaddr_in6()
        address.sin6_len = UInt8(MemoryLayout<sockaddr_in6>.size)
        address.sin6_family = sa_family_t(AF_INET6)
        address.sin6_scope_id = scopeID
        guard inet_pton(AF_INET6, addressText, &address.sin6_addr) == 1 else {
            throw SourceIdentityTestError.invalidAddress
        }
        return withUnsafePointer(to: &address) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                RelaySourceIdentity(
                    sockaddr: $0,
                    length: socklen_t(MemoryLayout<sockaddr_in6>.size)
                )
            }
        }
    }

    private func unknownSourceIdentity(family: Int32) -> RelaySourceIdentity {
        var address = sockaddr()
        address.sa_len = UInt8(MemoryLayout<sockaddr>.size)
        address.sa_family = sa_family_t(family)
        return withUnsafePointer(to: &address) {
            RelaySourceIdentity(
                sockaddr: $0,
                length: socklen_t(MemoryLayout<sockaddr>.size)
            )
        }
    }
}

private final class TestMonotonicClock: @unchecked Sendable {
    private let lock = NSLock()
    private var value: TimeInterval

    init(_ value: TimeInterval) {
        self.value = value
    }

    func now() -> TimeInterval {
        lock.lock()
        defer { lock.unlock() }
        return value
    }

    func set(_ value: TimeInterval) {
        lock.lock()
        self.value = value
        lock.unlock()
    }
}

private enum SourceIdentityTestError: Error {
    case invalidAddress
}
