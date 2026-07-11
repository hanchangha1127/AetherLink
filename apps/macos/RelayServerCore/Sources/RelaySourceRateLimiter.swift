import Darwin
import Foundation

public struct RelaySourceRateLimitConfiguration: Equatable, Sendable {
    public static let defaultPreflightRequestsPerMinute: Double = 120
    public static let defaultPreflightBurst = 30
    public static let defaultAllocationMutationRequestsPerMinute: Double = 30
    public static let defaultAllocationMutationBurst = 10
    public static let defaultMaximumTrackedSources = 4_096
    public static let defaultIdleRetentionSeconds: TimeInterval = 15 * 60

    public static let maximumRequestsPerMinute: Double = 1_000_000
    public static let maximumBurst = 1_000_000
    public static let maximumTrackedSources = 65_536
    public static let maximumIdleRetentionSeconds: TimeInterval = 24 * 60 * 60

    public var preflightRequestsPerMinute: Double
    public var preflightBurst: Int
    public var allocationMutationRequestsPerMinute: Double
    public var allocationMutationBurst: Int
    public var maximumTrackedSources: Int
    public var idleRetentionSeconds: TimeInterval

    public init(
        preflightRequestsPerMinute: Double = Self.defaultPreflightRequestsPerMinute,
        preflightBurst: Int = Self.defaultPreflightBurst,
        allocationMutationRequestsPerMinute: Double = Self.defaultAllocationMutationRequestsPerMinute,
        allocationMutationBurst: Int = Self.defaultAllocationMutationBurst,
        maximumTrackedSources: Int = Self.defaultMaximumTrackedSources,
        idleRetentionSeconds: TimeInterval = Self.defaultIdleRetentionSeconds
    ) {
        self.preflightRequestsPerMinute = preflightRequestsPerMinute
        self.preflightBurst = preflightBurst
        self.allocationMutationRequestsPerMinute = allocationMutationRequestsPerMinute
        self.allocationMutationBurst = allocationMutationBurst
        self.maximumTrackedSources = maximumTrackedSources
        self.idleRetentionSeconds = idleRetentionSeconds
    }

    public func validate() throws {
        guard preflightRequestsPerMinute.isFinite,
              preflightRequestsPerMinute > 0,
              preflightRequestsPerMinute <= Self.maximumRequestsPerMinute
        else {
            throw RelaySourceRateLimitConfigurationError.invalidPreflightRequestsPerMinute
        }
        guard preflightBurst > 0,
              preflightBurst <= Self.maximumBurst
        else {
            throw RelaySourceRateLimitConfigurationError.invalidPreflightBurst
        }
        guard allocationMutationRequestsPerMinute.isFinite,
              allocationMutationRequestsPerMinute > 0,
              allocationMutationRequestsPerMinute <= Self.maximumRequestsPerMinute
        else {
            throw RelaySourceRateLimitConfigurationError.invalidAllocationMutationRequestsPerMinute
        }
        guard allocationMutationBurst > 0,
              allocationMutationBurst <= Self.maximumBurst
        else {
            throw RelaySourceRateLimitConfigurationError.invalidAllocationMutationBurst
        }
        guard maximumTrackedSources > 0,
              maximumTrackedSources <= Self.maximumTrackedSources
        else {
            throw RelaySourceRateLimitConfigurationError.invalidMaximumTrackedSources
        }
        guard idleRetentionSeconds.isFinite,
              idleRetentionSeconds > 0,
              idleRetentionSeconds <= Self.maximumIdleRetentionSeconds
        else {
            throw RelaySourceRateLimitConfigurationError.invalidIdleRetentionSeconds
        }
        let minimumRetentionForFullRefill = max(
            Double(preflightBurst) * 60 / preflightRequestsPerMinute,
            Double(allocationMutationBurst) * 60 / allocationMutationRequestsPerMinute
        )
        guard idleRetentionSeconds >= minimumRetentionForFullRefill else {
            throw RelaySourceRateLimitConfigurationError.idleRetentionTooShortForBurstRefill
        }
    }
}

public enum RelaySourceRateLimitConfigurationError: Error, Equatable, Sendable {
    case invalidPreflightRequestsPerMinute
    case invalidPreflightBurst
    case invalidAllocationMutationRequestsPerMinute
    case invalidAllocationMutationBurst
    case invalidMaximumTrackedSources
    case invalidIdleRetentionSeconds
    case idleRetentionTooShortForBurstRefill
}

public enum RelaySourceRateLimitReason: String, Equatable, Sendable {
    case allocationPreflightSourceRateLimited = "allocation_preflight_source_rate_limited"
    case allocationMutationSourceRateLimited = "allocation_mutation_source_rate_limited"
}

public enum RelaySourceRateLimitMetricName: String, CaseIterable, Sendable {
    case allocationPreflightRequestsTotal = "allocation_preflight_requests_total"
    case allocationMutationRequestsTotal = "allocation_mutation_requests_total"
    case allocationPreflightSourceRateLimitedTotal =
        "allocation_preflight_source_rate_limited_total"
    case allocationMutationSourceRateLimitedTotal =
        "allocation_mutation_source_rate_limited_total"
    case rateLimitOverflowRequestsTotal = "rate_limit_overflow_requests_total"
    case rateLimitIdleSweepsTotal = "rate_limit_idle_sweeps_total"
    case rateLimitSourceEvictionsTotal = "rate_limit_source_evictions_total"
    case rateLimitTrackedSources = "rate_limit_tracked_sources"
}

public struct RelaySourceRateLimitMetricsSnapshot: Equatable, Sendable {
    public let allocationPreflightRequestsTotal: UInt64
    public let allocationMutationRequestsTotal: UInt64
    public let allocationPreflightSourceRateLimitedTotal: UInt64
    public let allocationMutationSourceRateLimitedTotal: UInt64
    public let rateLimitOverflowRequestsTotal: UInt64
    public let rateLimitIdleSweepsTotal: UInt64
    public let rateLimitSourceEvictionsTotal: UInt64
    public let trackedSourceCount: UInt64

    public var valuesByName: [String: UInt64] {
        [
            RelaySourceRateLimitMetricName.allocationPreflightRequestsTotal.rawValue:
                allocationPreflightRequestsTotal,
            RelaySourceRateLimitMetricName.allocationMutationRequestsTotal.rawValue:
                allocationMutationRequestsTotal,
            RelaySourceRateLimitMetricName.allocationPreflightSourceRateLimitedTotal.rawValue:
                allocationPreflightSourceRateLimitedTotal,
            RelaySourceRateLimitMetricName.allocationMutationSourceRateLimitedTotal.rawValue:
                allocationMutationSourceRateLimitedTotal,
            RelaySourceRateLimitMetricName.rateLimitOverflowRequestsTotal.rawValue:
                rateLimitOverflowRequestsTotal,
            RelaySourceRateLimitMetricName.rateLimitIdleSweepsTotal.rawValue:
                rateLimitIdleSweepsTotal,
            RelaySourceRateLimitMetricName.rateLimitSourceEvictionsTotal.rawValue:
                rateLimitSourceEvictionsTotal,
            RelaySourceRateLimitMetricName.rateLimitTrackedSources.rawValue:
                trackedSourceCount
        ]
    }
}

struct RelaySourceIdentity: Hashable, Sendable, Comparable {
    private enum Family: UInt8, Sendable {
        case unknown
        case ipv4
        case ipv6
        case overflow
    }

    static let unknown = RelaySourceIdentity(family: .unknown, addressBytes: [])
    static let overflow = RelaySourceIdentity(family: .overflow, addressBytes: [])

    private let family: Family
    private let addressBytes: [UInt8]

    init(storage: sockaddr_storage, length: socklen_t) {
        var storage = storage
        self = withUnsafePointer(to: &storage) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockaddrPointer in
                RelaySourceIdentity(sockaddr: sockaddrPointer, length: length)
            }
        }
    }

    init(sockaddr: UnsafePointer<sockaddr>, length: socklen_t) {
        switch Int32(sockaddr.pointee.sa_family) {
        case AF_INET where length >= socklen_t(MemoryLayout<sockaddr_in>.size):
            var address = sockaddr.withMemoryRebound(to: sockaddr_in.self, capacity: 1) {
                $0.pointee.sin_addr
            }
            self.init(
                family: .ipv4,
                addressBytes: withUnsafeBytes(of: &address) { Array($0.prefix(4)) }
            )
        case AF_INET6 where length >= socklen_t(MemoryLayout<sockaddr_in6>.size):
            let socketAddress = sockaddr.withMemoryRebound(to: sockaddr_in6.self, capacity: 1) {
                $0.pointee
            }
            var address = socketAddress.sin6_addr
            let bytes = withUnsafeBytes(of: &address) { Array($0.prefix(16)) }
            if bytes.prefix(10).allSatisfy({ $0 == 0 }),
               bytes[10] == 0xff,
               bytes[11] == 0xff {
                self.init(family: .ipv4, addressBytes: Array(bytes.suffix(4)))
            } else {
                var scopeID = socketAddress.sin6_scope_id.bigEndian
                let scopeBytes = withUnsafeBytes(of: &scopeID) { Array($0) }
                self.init(family: .ipv6, addressBytes: bytes + scopeBytes)
            }
        default:
            self = .unknown
        }
    }

    private init(family: Family, addressBytes: [UInt8]) {
        self.family = family
        self.addressBytes = addressBytes
    }

    static func < (lhs: RelaySourceIdentity, rhs: RelaySourceIdentity) -> Bool {
        if lhs.family.rawValue != rhs.family.rawValue {
            return lhs.family.rawValue < rhs.family.rawValue
        }
        return lhs.addressBytes.lexicographicallyPrecedes(rhs.addressBytes)
    }
}

final class RelaySourceRateLimiter: @unchecked Sendable {
    enum RequestKind: Sendable {
        case preflight
        case allocationMutation
    }

    struct Decision: Equatable, Sendable {
        let allowed: Bool
        let rejectionReason: RelaySourceRateLimitReason?
        let reasonCount: UInt64
    }

    private struct TokenBucket: Sendable {
        var availableTokens: Double
        var lastRefillTime: TimeInterval

        mutating func consume(
            now: TimeInterval,
            requestsPerMinute: Double,
            burst: Int
        ) -> Bool {
            let elapsed = max(0, now - lastRefillTime)
            availableTokens = min(
                Double(burst),
                availableTokens + elapsed * requestsPerMinute / 60
            )
            lastRefillTime = max(lastRefillTime, now)
            guard availableTokens >= 1 else { return false }
            availableTokens -= 1
            return true
        }
    }

    private struct SourceState: Sendable {
        var preflightBucket: TokenBucket
        var allocationMutationBucket: TokenBucket
        var lastSeenTime: TimeInterval
    }

    private struct Metrics: Sendable {
        var allocationPreflightRequestsTotal: UInt64 = 0
        var allocationMutationRequestsTotal: UInt64 = 0
        var allocationPreflightSourceRateLimitedTotal: UInt64 = 0
        var allocationMutationSourceRateLimitedTotal: UInt64 = 0
        var rateLimitOverflowRequestsTotal: UInt64 = 0
        var rateLimitIdleSweepsTotal: UInt64 = 0
        var rateLimitSourceEvictionsTotal: UInt64 = 0
    }

    private let configuration: RelaySourceRateLimitConfiguration
    private let monotonicNow: @Sendable () -> TimeInterval
    private let lock = NSLock()
    private var sources: [RelaySourceIdentity: SourceState] = [:]
    private var metrics = Metrics()
    private var lastObservedTime: TimeInterval = 0
    private var nextIdleSweepTime: TimeInterval = 0

    init(
        configuration: RelaySourceRateLimitConfiguration,
        monotonicNow: @escaping @Sendable () -> TimeInterval = {
            ProcessInfo.processInfo.systemUptime
        }
    ) {
        self.configuration = configuration
        self.monotonicNow = monotonicNow
    }

    func evaluate(source: RelaySourceIdentity, kind: RequestKind) -> Decision {
        lock.withLock {
            let candidateTime = monotonicNow()
            if candidateTime.isFinite {
                lastObservedTime = max(lastObservedTime, candidateTime)
            }
            let now = lastObservedTime
            removeIdleSourcesIfNeeded(now: now)
            let bucketSource = bucketSource(for: source)
            if bucketSource == .overflow {
                metrics.rateLimitOverflowRequestsTotal = Self.saturatingIncrement(
                    metrics.rateLimitOverflowRequestsTotal
                )
            }

            if sources[bucketSource] == nil {
                sources[bucketSource] = SourceState(
                    preflightBucket: TokenBucket(
                        availableTokens: Double(configuration.preflightBurst),
                        lastRefillTime: now
                    ),
                    allocationMutationBucket: TokenBucket(
                        availableTokens: Double(configuration.allocationMutationBurst),
                        lastRefillTime: now
                    ),
                    lastSeenTime: now
                )
            }

            var state = sources[bucketSource]!
            state.lastSeenTime = now

            let allowed: Bool
            let reason: RelaySourceRateLimitReason
            switch kind {
            case .preflight:
                metrics.allocationPreflightRequestsTotal = Self.saturatingIncrement(
                    metrics.allocationPreflightRequestsTotal
                )
                allowed = state.preflightBucket.consume(
                    now: now,
                    requestsPerMinute: configuration.preflightRequestsPerMinute,
                    burst: configuration.preflightBurst
                )
                reason = .allocationPreflightSourceRateLimited
            case .allocationMutation:
                metrics.allocationMutationRequestsTotal = Self.saturatingIncrement(
                    metrics.allocationMutationRequestsTotal
                )
                allowed = state.allocationMutationBucket.consume(
                    now: now,
                    requestsPerMinute: configuration.allocationMutationRequestsPerMinute,
                    burst: configuration.allocationMutationBurst
                )
                reason = .allocationMutationSourceRateLimited
            }
            sources[bucketSource] = state

            guard !allowed else {
                return Decision(allowed: true, rejectionReason: nil, reasonCount: 0)
            }

            let reasonCount: UInt64
            switch kind {
            case .preflight:
                metrics.allocationPreflightSourceRateLimitedTotal = Self.saturatingIncrement(
                    metrics.allocationPreflightSourceRateLimitedTotal
                )
                reasonCount = metrics.allocationPreflightSourceRateLimitedTotal
            case .allocationMutation:
                metrics.allocationMutationSourceRateLimitedTotal = Self.saturatingIncrement(
                    metrics.allocationMutationSourceRateLimitedTotal
                )
                reasonCount = metrics.allocationMutationSourceRateLimitedTotal
            }
            return Decision(
                allowed: false,
                rejectionReason: reason,
                reasonCount: reasonCount
            )
        }
    }

    func metricsSnapshot() -> RelaySourceRateLimitMetricsSnapshot {
        lock.withLock {
            let candidateTime = monotonicNow()
            if candidateTime.isFinite {
                lastObservedTime = max(lastObservedTime, candidateTime)
            }
            removeIdleSourcesIfNeeded(now: lastObservedTime)
            return RelaySourceRateLimitMetricsSnapshot(
                allocationPreflightRequestsTotal: metrics.allocationPreflightRequestsTotal,
                allocationMutationRequestsTotal: metrics.allocationMutationRequestsTotal,
                allocationPreflightSourceRateLimitedTotal:
                    metrics.allocationPreflightSourceRateLimitedTotal,
                allocationMutationSourceRateLimitedTotal:
                    metrics.allocationMutationSourceRateLimitedTotal,
                rateLimitOverflowRequestsTotal: metrics.rateLimitOverflowRequestsTotal,
                rateLimitIdleSweepsTotal: metrics.rateLimitIdleSweepsTotal,
                rateLimitSourceEvictionsTotal: metrics.rateLimitSourceEvictionsTotal,
                trackedSourceCount: UInt64(sources.count)
            )
        }
    }

    static func saturatingIncrement(_ value: UInt64) -> UInt64 {
        value == .max ? .max : value + 1
    }

    private func bucketSource(for source: RelaySourceIdentity) -> RelaySourceIdentity {
        if sources[source] != nil {
            return source
        }
        let overflowPresent = sources[.overflow] != nil
        let individualSourceCount = sources.count - (overflowPresent ? 1 : 0)
        let individualSourceCapacity = max(0, configuration.maximumTrackedSources - 1)
        return individualSourceCount < individualSourceCapacity ? source : .overflow
    }

    private func removeIdleSourcesIfNeeded(now: TimeInterval) {
        guard now >= nextIdleSweepTime else { return }
        nextIdleSweepTime = now + min(60, configuration.idleRetentionSeconds)
        metrics.rateLimitIdleSweepsTotal = Self.saturatingIncrement(
            metrics.rateLimitIdleSweepsTotal
        )
        let idleSources = sources.compactMap { source, state in
            now - state.lastSeenTime >= configuration.idleRetentionSeconds ? source : nil
        }
        for source in idleSources {
            sources.removeValue(forKey: source)
            metrics.rateLimitSourceEvictionsTotal = Self.saturatingIncrement(
                metrics.rateLimitSourceEvictionsTotal
            )
        }
    }
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
