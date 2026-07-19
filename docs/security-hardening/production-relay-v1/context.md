# Production Relay Security Hardening Context

This is a derived design analysis for the next transport milestone in
`docs/roadmap.md`. It is not a vulnerability scan and does not claim that a
production relay protocol has been implemented.

## Source Identity

- Local source root: `/Users/hanchangha/Desktop/project`
- Git base revision observed before this source refresh: `abd638482ea01d2b5f4d38eb78be04f734814c71`
- Source drift: present. The roadmap worktree intentionally contains uncommitted
  relay, pairing, protocol, Android, script, and documentation changes.
- Evidence manifest: `evidence.sha256`
- Evidence collection SHA-256:
  `e188e1b885419e376b9dcea85282b4aafb1d48692b134edc13aff2eedfbf6b66`
- Evidence artifacts: 17 source/schema files.
- Runtime constraint: the Android phone is disconnected. No physical optical QR,
  public relay, or real different-network evidence was used.
- Authority boundary: this is an evidence-only refresh. The selection-gated
  production design remains not implemented, and this snapshot grants no
  deployment, socket or live-network authorization, Phase B execution, or
  production-readiness claim.

## Evidence Inventory

| ID | Title | Primary source evidence |
| --- | --- | --- |
| `E001` | Plain allocation transport, bounded control lines, and unsigned lease response | `apps/macos/CompanionCore/Sources/RemoteRelayAllocationClient.swift:190`, `apps/macos/CompanionCore/Sources/RemoteRelayAllocationClient.swift:235`, `apps/macos/CompanionCore/Sources/RemoteRelayAllocationClient.swift:835`, `apps/macos/Transport/Sources/RelayPeerClient.swift:250`, `apps/macos/Transport/Sources/RelayPeerClient.swift:665`, `apps/macos/Transport/Sources/RelayPeerClient.swift:760` |
| `E002` | Endpoint-owned traffic secret and PSK-mixed ephemeral ECDH | `apps/macos/CompanionCore/Sources/CompanionAppModel.swift:18`, `apps/macos/CompanionCore/Sources/CompanionAppModel.swift:555`, `apps/macos/Protocol/Sources/RelaySessionCrypto.swift:96`, `apps/android/core/transport/src/main/java/com/localagentbridge/android/core/transport/RelaySessionCrypto.kt:100` |
| `E003` | Validated runtime identity decoding and signed allocation/registration challenges | `apps/macos/Protocol/Sources/RelayIdentityAuthorization.swift:19`, `apps/macos/Protocol/Sources/RelayIdentityAuthorization.swift:92`, `apps/macos/Protocol/Sources/RelayIdentityAuthorization.swift:209`, `apps/macos/Protocol/Sources/RelayIdentityAuthorization.swift:312` |
| `E004` | Runtime/client co-authorized paired lease continuity with fresh registration revalidation | `apps/macos/CompanionCore/Sources/RemoteRelayAllocationClient.swift:286`, `apps/macos/Protocol/Sources/PairedRelayAllocationAuthorization.swift:267`, `apps/macos/RelayServerCore/Sources/RelayAllocation.swift:946`, `apps/macos/RelayServerCore/Sources/RelayAllocation.swift:1059`, `apps/macos/RelayServerCore/Sources/RelayServer.swift:439` |
| `E005` | QR-pinned mutual device identity | `apps/macos/Pairing/Sources/InitialPairingProof.swift:99`, `apps/macos/Pairing/Sources/InitialPairingProof.swift:246` |
| `E006` | DNS-scope-validated paired admission, bounded strict controls, and frame activation | `apps/android/core/transport/src/main/java/com/localagentbridge/android/core/transport/RuntimeRelayTcpClient.kt:86`, `apps/android/core/transport/src/main/java/com/localagentbridge/android/core/transport/RuntimeRelayTcpClient.kt:242`, `apps/android/core/transport/src/main/java/com/localagentbridge/android/core/transport/RuntimeRelayTcpClient.kt:280`, `apps/macos/Transport/Sources/RelayPeerClient.swift:665`, `apps/macos/Transport/Sources/RelayPeerClient.swift:760` |
| `E007` | Strict allocation JSON, bounded TTL, durable generation, and consumed-bootstrap CAS | `apps/macos/RelayServerCore/Sources/RelayAllocation.swift:349`, `apps/macos/RelayServerCore/Sources/RelayAllocation.swift:474`, `apps/macos/RelayServerCore/Sources/RelayAllocation.swift:919`, `apps/macos/RelayServerCore/Sources/RelayAllocation.swift:1017`, `apps/macos/RelayServerCore/Sources/RelayAllocation.swift:1059`, `apps/macos/RelayServerCore/Sources/RelayAllocation.swift:1198`, `apps/macos/RelayServerCore/Sources/RelayAllocation.swift:1310`, `apps/macos/RelayServerCore/Sources/RelayAllocation.swift:1706` |
| `E008` | Client route identity, lease, nonce, and secret persistence | `apps/android/core/pairing/src/main/java/com/localagentbridge/android/core/pairing/PairingStore.kt:70`, `apps/android/core/pairing/src/main/java/com/localagentbridge/android/core/pairing/PairingStore.kt:172` |
| `E009` | Schema reserves transport binding but has no service lease or recovery epoch | `packages/protocol-schema/protocol.schema.json:204`, `packages/protocol-schema/protocol.schema.json:686` |
| `E010` | Development-relay source-aware allocation/preflight throttling | `apps/macos/RelayServerCore/Sources/RelaySourceRateLimiter.swift:4`, `apps/macos/RelayServerCore/Sources/RelaySourceRateLimiter.swift:194`, `apps/macos/RelayServerCore/Sources/RelayServer.swift:820`, `apps/macos/RelayServerCore/Sources/RelayServer.swift:835` |
| `E011` | Development-relay source connection and waiting-peer quotas | `apps/macos/RelayServerCore/Sources/RelaySourceQuotaLimiter.swift:181`, `apps/macos/RelayServerCore/Sources/RelaySourceQuotaLimiter.swift:316`, `apps/macos/RelayServerCore/Sources/RelayMatcher.swift:576`, `apps/macos/RelayServerCore/Sources/RelayServer.swift:1110`, `apps/macos/RelayServerCore/Sources/RelayServer.swift:1122` |
| `E012` | Development-relay bounded waiting and authenticated identity fairness | `apps/macos/RelayServerCore/Sources/RelayWaitingPeerPolicy.swift:134`, `apps/macos/RelayServerCore/Sources/RelayMatcher.swift:455`, `apps/macos/RelayServerCore/Sources/RelayMatcher.swift:579`, `apps/macos/RelayServerCore/Sources/RelayServer.swift:439`, `apps/macos/RelayServerCore/Sources/RelayServer.swift:491` |

## Evidence Limits

The source proves current data flow and validation behavior. It does not measure
public-network latency, certificate operations, service key rotation, revocation
fanout, or recovery UX. All performance and operational estimates in the
proposal are therefore source-derived or hypothetical and carry explicit
validation plans.

The refreshed artifacts also prove narrower defensive behavior. Allocation and
persisted allocation JSON reject duplicate object keys; decoded runtime identity
objects re-enter their validating initializer; allocation TTL is finite,
positive, capped at 24 hours, and checked before epoch conversion; control-line
reads are byte-bounded; and allocation binding plus expiry is freshly revalidated
under the coordinated store lock immediately before matcher registration.
Android resolves the relay host once, validates every returned address against
the route scope, and connects to the exact validated address; outgoing frame
bodies remain bounded by the protocol maximum. These controls reduce parser,
lease-race, rebinding, and memory-amplification risk. They do not authenticate the
service, sign a lease, authorize a production route, or prove network behavior.

The broader dirty worktree also validates DNS-SD TXT records by UTF-8 byte size
(`key=value` at most 255 bytes) and rejects control characters. Its
`RuntimeTransport.swift` source is not one of this exact 17-artifact collection,
so that change is recorded only as unpinned working-tree context and is not used
as portfolio evidence.

`E010` is in-process, restart-local accounting keyed by the accepted socket's
canonical address and IPv6 scope. A shared overflow bucket prevents capacity
churn from resetting exhausted buckets, and periodic idle sweeps avoid per-request
full-map scans. Only the exact strict preflight envelope selects the preflight
bucket, and accepted configurations require bursts to fully refill before idle
deletion. It does not prove public-network behavior, carrier-NAT
or VPN fairness, trusted proxy identity, coordinated multi-instance policy,
production capacity, exporter/alerting integration, or source throttling for
malformed non-allocation controls. Those controls remain covered by the global
connection cap, source peer quota, and absolute control deadline, not the
allocation source rate limiter.

`E011` is also in-process and restart-local. It bounds live exact-source
connections and matcher-owned unmatched waiters, preserves one global and
per-source slot before the first waiter, revalidates connection-plus-reservation
headroom on each waiting insertion, restricts reserve users to immediate
counterpart matching or authenticated same-source waiting replacement, rejects
per-source reserve discharge against another source's waiter and cross-source
reserve replacement, and keeps active bridge sockets counted
without throttling established frames.
It does not prove carrier-NAT/VPN fairness, IPv6 address-rotation resistance,
trusted proxy identity, coordinated multi-instance policy, production capacity,
or per-user isolation.

`E012` bounds each unmatched room from its first-insertion with a monotonic
60-second default deadline capped by the current allocation lease, and limits
waiting peers to four per role-separated authenticated fingerprint by default.
Registration and readiness probes remove expired rooms atomically under the
matcher lock before matching, replacement, or visibility decisions, so delayed
timer delivery cannot extend the deadline.
The waiting registration result carries that deadline out of the same matcher
transaction, avoiding a post-publication room lookup after a counterpart can
move the room active.
Only a runtime identity revalidated from the allocation binding after runtime
proof, or a pinned paired-client identity after client proof, enters identity
accounting. Bootstrap clients without paired proof and legacy peers remain
source-only. Same-role replacement inherits the original deadline; immediate
matches and active bridges do not consume identity waiting capacity. Metrics and
reasons contain no source, fingerprint, relay, token, lease, role, or proof
labels. This is restart-local fairness for verified identities, not account or
user isolation; multiple valid identities remain a Sybil path. It does not prove
public-network behavior, production capacity, service authentication, lease
integrity, peer-verifiable identity KEX, or recovery authority.

## Tactical Baseline Update

The refreshed `RelayServer.swift` evidence includes the no-device abuse-control
foundation completed after the first review: accepted-socket lifetime permits,
waiting-peer disconnect cleanup, `SIGPIPE` suppression, first-side active-bridge
shutdown and permit reclamation, absolute control-record deadlines that survive
`EINTR`, exposed probe disabled by default, and exposed legacy mode rejection.
Strict allocation/store JSON rejects duplicate keys, runtime identities are
validated during decoding, allocation TTL is finite and capped at 24 hours,
control lines are byte-bounded, and matcher admission uses a freshly revalidated
lease snapshot. Android relay setup validates all resolved addresses against the
declared route scope before connecting to an exact resolved address and keeps
frame bodies within the protocol limit.
Allocation- and renewal-prefixed attempts now consume a classified source bucket
before full parsing. Only the exact strict preflight envelope uses the preflight
bucket; malformed or mutation-like allocation and paired claim/renew attempts use
the mutation bucket, with bounded overflow and source-free counters. Exact-source
connection and unmatched-waiting quotas add matcher-atomic lifetime admission
without evicting active bridges. Matcher-atomic first-insertion waiting deadlines and
post-proof, role-separated authenticated identity quotas add bounded waiting and
cross-source fairness without charging bootstrap or legacy peers. These controls
reduce development-relay abuse
surface but do not add allocation TLS, service signatures, peer-verifiable
identity KEX, pair epoch recovery, trusted proxy identity, coordinated production
policy, or production deployment proof. It also grants no socket/live-network
authorization, Phase B execution, deployment authority, or production-readiness
claim.
