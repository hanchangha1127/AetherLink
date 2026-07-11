import Foundation
import RelayServerCore

var host = RelayServerConfiguration.defaultHost
var port: UInt16 = 43171
var requiresAllocation = true
var allocationStorePath = ProcessInfo.processInfo.environment["AETHERLINK_RELAY_ALLOCATION_STORE"]
var allocationToken = ProcessInfo.processInfo.environment["AETHERLINK_RELAY_ALLOCATION_TOKEN"]
var allocationTTLSeconds = RelayServerConfiguration.defaultAllocationTTLSeconds
var probePolicy = RelayProbePolicy.loopbackOnly
var controlLineReadTimeoutSeconds = RelayServerConfiguration.defaultControlLineReadTimeoutSeconds
var maximumConcurrentConnections = RelayServerConfiguration.defaultMaximumConcurrentConnections
let defaultSourceQuotas = RelaySourceQuotaConfiguration()
var maxConnectionsPerSource = defaultSourceQuotas.maximumConnectionsPerSource
var maxWaitingPeersPerSource = defaultSourceQuotas.maximumWaitingPeersPerSource
let defaultWaitingPeerPolicy = RelayWaitingPeerPolicyConfiguration()
var waitingPeerTimeoutSeconds = Int(defaultWaitingPeerPolicy.maximumDurationSeconds)
var maxWaitingPeersPerAuthenticatedIdentity =
    defaultWaitingPeerPolicy.maximumPeersPerAuthenticatedIdentity
var preflightRatePerMinute = 120
var preflightBurst = 30
var allocationRatePerMinute = 30
var allocationBurst = 10
var maximumRateLimitSources = 4_096
var usesEphemeralAllocations = false
var arguments = Array(CommandLine.arguments.dropFirst())

func usage(exitCode: Int32) -> Never {
    let output = exitCode == 0 ? FileHandle.standardOutput : FileHandle.standardError
    output.write(Data("""
    Usage: AetherLinkRelay [--host <host>] [--port <port>] [--require-allocation] [--allow-legacy] [--allocation-token <token>] [--allocation-ttl-seconds <seconds>] [--allocation-store <path>] [--ephemeral-allocations] [--probe-policy <disabled|loopback-only|legacy-unauthenticated>] [--control-timeout-seconds <seconds>] [--waiting-timeout-seconds <seconds>] [--max-connections <count>] [--max-connections-per-source <count>] [--max-waiting-peers-per-source <count>] [--max-waiting-peers-per-authenticated-identity <count>] [--preflight-rate-per-minute <count>] [--preflight-burst <count>] [--allocation-rate-per-minute <count>] [--allocation-burst <count>] [--max-rate-limit-sources <count>]

    Runs the AetherLink development connectivity relay. This relay pairs one
    runtime and one client by relay_id, sends AETHERLINK_RELAY ready, then
    blindly forwards bytes. It also accepts
    AETHERLINK_RELAY allocate <route_token> crypto=2
    allocation_auth=runtime-p256-v1 runtime_key_fingerprint=<fingerprint>
    runtime_public_key=<DER-base64> [allocation_token=<token>] to issue or
    renew runtime-key-bound relay route material, and
    AETHERLINK_RELAY probe <relay_id> to report whether the relay ID is known
    and whether a runtime is waiting without consuming any pending peer. Probe
    is loopback-only by default. Exposed relays close probe requests without a
    response unless --probe-policy legacy-unauthenticated is explicitly set for
    temporary diagnostics; that mode exposes a route-state oracle.
    Runtime/client handshakes for unknown or expired relay IDs are rejected by
    default. Use --allow-legacy only for old local diagnostics that intentionally
    accept arbitrary relay IDs.
    Tokenless relay binds are allowed only for loopback diagnostics on
    127.0.0.1, ::1, or localhost. Binding a wildcard, DNS, private, or public
    host requires --allocation-token or AETHERLINK_RELAY_ALLOCATION_TOKEN, and
    allocation requests must include the same token.
    Allocation tickets are short-lived by default. Use --allocation-ttl-seconds
    only for explicit development diagnostics that need a longer route lease.
    Allocation tickets persist to ~/.aetherlink-relay/allocations.json by
    default so issued QR route material can survive relay process restarts.
    Use --ephemeral-allocations only for loopback diagnostics. Strict wildcard
    and non-loopback binds require the durable allocation store so runtime-key
    ownership survives relay restarts.
    Every accepted socket counts against --max-connections until it is closed,
    including waiting and active bridge peers. Every control record must finish
    within --control-timeout-seconds; frame forwarding remains timeout-free.
    Source quotas identify accepted peers by their canonical socket IPv4/IPv6
    address. Waiting peers count against both source quotas; active bridges
    remain counted against the source connection quota, but frame forwarding is
    not throttled. Shared NAT/VPN users share source quotas. The defaults are
    development-relay guardrails, not production capacity policy. Source quota
    values must be 1...65536 with no disable value, and twice the waiting-peer
    quota must not exceed the per-source connection quota. Source quotas need
    not be at most the global maximum; effective capacity is bounded naturally
    by all applicable limits.
    Unmatched waiting peers close after --waiting-timeout-seconds. Once relay
    admission has cryptographically authenticated a runtime or paired client
    key, at most --max-waiting-peers-per-authenticated-identity unmatched peers
    may use that identity across sources. Unauthenticated bootstrap clients
    remain protected by source quotas only. Both values have no disable mode.
    Source rate limits apply only to allocation, preflight, and paired-renewal
    control records. They do not throttle peer admission or encrypted
    forwarding. Shared NAT/VPN users share one source bucket. The defaults are
    development-relay guardrails, not production capacity policy. Rate and
    burst values must be 1...1000000; tracked sources must be 1...65536. There
    is no disable value. Each burst must fully refill within the fixed 900-second
    idle retention so cleanup cannot reset capacity.
    Legacy unallocated relay mode is loopback-only even when a token is present.
    It is not a production P2P, DHT, TURN, or AI backend.

    """.utf8))
    exit(exitCode)
}

func parseCanonicalPositiveDecimal(_ value: String, maximum: Int) -> Int? {
    let bytes = value.utf8
    guard !bytes.isEmpty,
          bytes.count <= 7,
          let first = bytes.first,
          (UInt8(ascii: "1")...UInt8(ascii: "9")).contains(first),
          bytes.allSatisfy({ (UInt8(ascii: "0")...UInt8(ascii: "9")).contains($0) }),
          let parsed = Int(value),
          parsed <= maximum
    else {
        return nil
    }
    return parsed
}

if let ttlText = ProcessInfo.processInfo.environment["AETHERLINK_RELAY_ALLOCATION_TTL_SECONDS"]?.takeIfNotEmpty() {
    guard let parsed = TimeInterval(ttlText), parsed > 0 else {
        usage(exitCode: 2)
    }
    allocationTTLSeconds = parsed
}
if let policyText = ProcessInfo.processInfo.environment["AETHERLINK_RELAY_PROBE_POLICY"]?.takeIfNotEmpty() {
    guard let parsed = RelayProbePolicy(rawValue: policyText) else {
        usage(exitCode: 2)
    }
    probePolicy = parsed
}
if let timeoutText = ProcessInfo.processInfo.environment["AETHERLINK_RELAY_CONTROL_TIMEOUT_SECONDS"]?.takeIfNotEmpty() {
    guard let parsed = TimeInterval(timeoutText), parsed > 0, parsed <= 300 else {
        usage(exitCode: 2)
    }
    controlLineReadTimeoutSeconds = parsed
}
if let maximumText = ProcessInfo.processInfo.environment["AETHERLINK_RELAY_MAX_CONNECTIONS"]?.takeIfNotEmpty() {
    guard let parsed = parseCanonicalPositiveDecimal(maximumText, maximum: 65_536) else {
        usage(exitCode: 2)
    }
    maximumConcurrentConnections = parsed
}
if let value = ProcessInfo.processInfo.environment["AETHERLINK_RELAY_MAX_CONNECTIONS_PER_SOURCE"]?.takeIfNotEmpty() {
    guard let parsed = parseCanonicalPositiveDecimal(value, maximum: 65_536) else {
        usage(exitCode: 2)
    }
    maxConnectionsPerSource = parsed
}
if let value = ProcessInfo.processInfo.environment["AETHERLINK_RELAY_MAX_WAITING_PEERS_PER_SOURCE"]?.takeIfNotEmpty() {
    guard let parsed = parseCanonicalPositiveDecimal(value, maximum: 65_536) else {
        usage(exitCode: 2)
    }
    maxWaitingPeersPerSource = parsed
}
if let value = ProcessInfo.processInfo.environment["AETHERLINK_RELAY_WAITING_TIMEOUT_SECONDS"]?.takeIfNotEmpty() {
    guard let parsed = parseCanonicalPositiveDecimal(value, maximum: 3_600) else {
        usage(exitCode: 2)
    }
    waitingPeerTimeoutSeconds = parsed
}
if let value = ProcessInfo.processInfo.environment["AETHERLINK_RELAY_MAX_WAITING_PEERS_PER_AUTHENTICATED_IDENTITY"]?.takeIfNotEmpty() {
    guard let parsed = parseCanonicalPositiveDecimal(value, maximum: 65_536) else {
        usage(exitCode: 2)
    }
    maxWaitingPeersPerAuthenticatedIdentity = parsed
}
if let value = ProcessInfo.processInfo.environment["AETHERLINK_RELAY_PREFLIGHT_RATE_PER_MINUTE"]?.takeIfNotEmpty() {
    guard let parsed = parseCanonicalPositiveDecimal(value, maximum: 1_000_000) else {
        usage(exitCode: 2)
    }
    preflightRatePerMinute = parsed
}
if let value = ProcessInfo.processInfo.environment["AETHERLINK_RELAY_PREFLIGHT_BURST"]?.takeIfNotEmpty() {
    guard let parsed = parseCanonicalPositiveDecimal(value, maximum: 1_000_000) else {
        usage(exitCode: 2)
    }
    preflightBurst = parsed
}
if let value = ProcessInfo.processInfo.environment["AETHERLINK_RELAY_ALLOCATION_RATE_PER_MINUTE"]?.takeIfNotEmpty() {
    guard let parsed = parseCanonicalPositiveDecimal(value, maximum: 1_000_000) else {
        usage(exitCode: 2)
    }
    allocationRatePerMinute = parsed
}
if let value = ProcessInfo.processInfo.environment["AETHERLINK_RELAY_ALLOCATION_BURST"]?.takeIfNotEmpty() {
    guard let parsed = parseCanonicalPositiveDecimal(value, maximum: 1_000_000) else {
        usage(exitCode: 2)
    }
    allocationBurst = parsed
}
if let value = ProcessInfo.processInfo.environment["AETHERLINK_RELAY_MAX_RATE_LIMIT_SOURCES"]?.takeIfNotEmpty() {
    guard let parsed = parseCanonicalPositiveDecimal(value, maximum: 65_536) else {
        usage(exitCode: 2)
    }
    maximumRateLimitSources = parsed
}

while !arguments.isEmpty {
    let argument = arguments.removeFirst()
    switch argument {
    case "--host":
        guard let value = arguments.first, !value.isEmpty else { usage(exitCode: 2) }
        host = value
        arguments.removeFirst()
    case "--port":
        guard let value = arguments.first, let parsed = UInt16(value) else { usage(exitCode: 2) }
        port = parsed
        arguments.removeFirst()
    case "--require-allocation":
        requiresAllocation = true
    case "--allow-legacy":
        requiresAllocation = false
    case "--allocation-store":
        guard let value = arguments.first, !value.isEmpty else { usage(exitCode: 2) }
        allocationStorePath = value
        arguments.removeFirst()
    case "--allocation-token":
        guard let value = arguments.first, !value.isEmpty else { usage(exitCode: 2) }
        allocationToken = value
        arguments.removeFirst()
    case "--allocation-ttl-seconds":
        guard let value = arguments.first,
              let parsed = TimeInterval(value),
              parsed > 0
        else {
            usage(exitCode: 2)
        }
        allocationTTLSeconds = parsed
        arguments.removeFirst()
    case "--probe-policy":
        guard let value = arguments.first,
              let parsed = RelayProbePolicy(rawValue: value)
        else {
            usage(exitCode: 2)
        }
        probePolicy = parsed
        arguments.removeFirst()
    case "--control-timeout-seconds":
        guard let value = arguments.first,
              let parsed = TimeInterval(value),
              parsed > 0,
              parsed <= 300
        else {
            usage(exitCode: 2)
        }
        controlLineReadTimeoutSeconds = parsed
        arguments.removeFirst()
    case "--max-connections":
        guard let value = arguments.first,
              let parsed = parseCanonicalPositiveDecimal(value, maximum: 65_536)
        else {
            usage(exitCode: 2)
        }
        maximumConcurrentConnections = parsed
        arguments.removeFirst()
    case "--max-connections-per-source":
        guard let value = arguments.first,
              let parsed = parseCanonicalPositiveDecimal(value, maximum: 65_536)
        else {
            usage(exitCode: 2)
        }
        maxConnectionsPerSource = parsed
        arguments.removeFirst()
    case "--max-waiting-peers-per-source":
        guard let value = arguments.first,
              let parsed = parseCanonicalPositiveDecimal(value, maximum: 65_536)
        else {
            usage(exitCode: 2)
        }
        maxWaitingPeersPerSource = parsed
        arguments.removeFirst()
    case "--waiting-timeout-seconds":
        guard let value = arguments.first,
              let parsed = parseCanonicalPositiveDecimal(value, maximum: 3_600)
        else {
            usage(exitCode: 2)
        }
        waitingPeerTimeoutSeconds = parsed
        arguments.removeFirst()
    case "--max-waiting-peers-per-authenticated-identity":
        guard let value = arguments.first,
              let parsed = parseCanonicalPositiveDecimal(value, maximum: 65_536)
        else {
            usage(exitCode: 2)
        }
        maxWaitingPeersPerAuthenticatedIdentity = parsed
        arguments.removeFirst()
    case "--preflight-rate-per-minute":
        guard let value = arguments.first,
              let parsed = parseCanonicalPositiveDecimal(value, maximum: 1_000_000)
        else {
            usage(exitCode: 2)
        }
        preflightRatePerMinute = parsed
        arguments.removeFirst()
    case "--preflight-burst":
        guard let value = arguments.first,
              let parsed = parseCanonicalPositiveDecimal(value, maximum: 1_000_000)
        else {
            usage(exitCode: 2)
        }
        preflightBurst = parsed
        arguments.removeFirst()
    case "--allocation-rate-per-minute":
        guard let value = arguments.first,
              let parsed = parseCanonicalPositiveDecimal(value, maximum: 1_000_000)
        else {
            usage(exitCode: 2)
        }
        allocationRatePerMinute = parsed
        arguments.removeFirst()
    case "--allocation-burst":
        guard let value = arguments.first,
              let parsed = parseCanonicalPositiveDecimal(value, maximum: 1_000_000)
        else {
            usage(exitCode: 2)
        }
        allocationBurst = parsed
        arguments.removeFirst()
    case "--max-rate-limit-sources":
        guard let value = arguments.first,
              let parsed = parseCanonicalPositiveDecimal(value, maximum: 65_536)
        else {
            usage(exitCode: 2)
        }
        maximumRateLimitSources = parsed
        arguments.removeFirst()
    case "--ephemeral-allocations":
        usesEphemeralAllocations = true
    case "-h", "--help":
        usage(exitCode: 0)
    default:
        usage(exitCode: 2)
    }
}

guard maxWaitingPeersPerSource * 2 <= maxConnectionsPerSource else {
    usage(exitCode: 2)
}

do {
    let allocationStoreURL = usesEphemeralAllocations ? nil : URL(
        fileURLWithPath: (
            allocationStorePath?.takeIfNotEmpty()
                ?? "~/.aetherlink-relay/allocations.json"
        ).expandingTildeInPath()
    )
    let sourceRateLimits = RelaySourceRateLimitConfiguration(
        preflightRequestsPerMinute: Double(preflightRatePerMinute),
        preflightBurst: preflightBurst,
        allocationMutationRequestsPerMinute: Double(allocationRatePerMinute),
        allocationMutationBurst: allocationBurst,
        maximumTrackedSources: maximumRateLimitSources
    )
    let sourceQuotas = RelaySourceQuotaConfiguration(
        maximumConnectionsPerSource: maxConnectionsPerSource,
        maximumWaitingPeersPerSource: maxWaitingPeersPerSource
    )
    let waitingPeerPolicy = RelayWaitingPeerPolicyConfiguration(
        maximumDurationSeconds: TimeInterval(waitingPeerTimeoutSeconds),
        maximumPeersPerAuthenticatedIdentity: maxWaitingPeersPerAuthenticatedIdentity
    )
    do {
        try sourceRateLimits.validate()
        try waitingPeerPolicy.validate()
    } catch {
        usage(exitCode: 2)
    }
    print("[relay] Source rate limits: preflight=\(preflightRatePerMinute)/minute burst=\(preflightBurst), allocation/paired-renewal=\(allocationRatePerMinute)/minute burst=\(allocationBurst), tracked sources=\(maximumRateLimitSources).")
    print("[relay] Limits apply only to allocation, preflight, and paired-renewal control records; peer admission and encrypted forwarding are not throttled.")
    print("[relay] Source quotas: connection_limit=\(maxConnectionsPerSource), waiting_limit=\(maxWaitingPeersPerSource), using the accepted socket's canonical IPv4/IPv6 address.")
    print("[relay] Waiting peers count against both source quotas with counterpart headroom (2 * waiting <= connections). Active bridges remain counted against the source connection quota, but frame forwarding is not throttled.")
    print("[relay] Waiting policy: timeout_seconds=\(waitingPeerTimeoutSeconds), authenticated_identity_limit=\(maxWaitingPeersPerAuthenticatedIdentity). Unauthenticated bootstrap clients remain source-only.")
    print("[relay] Shared NAT/VPN users share source quotas and rate-limit buckets. Defaults are development-relay guardrails, not production capacity policy.")
    let server = RelayServer(configuration: RelayServerConfiguration(
        host: host,
        port: port,
        allocationTTLSeconds: allocationTTLSeconds,
        requiresAllocation: requiresAllocation,
        allocationStoreURL: allocationStoreURL,
        allocationToken: allocationToken?.takeIfNotEmpty(),
        probePolicy: probePolicy,
        controlLineReadTimeoutSeconds: controlLineReadTimeoutSeconds,
        maximumConcurrentConnections: maximumConcurrentConnections,
        sourceQuotaConfiguration: sourceQuotas,
        waitingPeerPolicyConfiguration: waitingPeerPolicy,
        sourceRateLimitConfiguration: sourceRateLimits
    ))
    try server.run()
} catch {
    FileHandle.standardError.write(Data("[relay] failed: \(error)\n".utf8))
    exit(1)
}

private extension String {
    func takeIfNotEmpty() -> String? {
        isEmpty ? nil : self
    }

    func expandingTildeInPath() -> String {
        (self as NSString).expandingTildeInPath
    }
}
