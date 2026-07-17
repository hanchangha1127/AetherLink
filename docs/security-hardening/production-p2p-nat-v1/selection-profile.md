# Production P2P/NAT V1 Selection Profile

## Status

This profile is explicitly approved for a bounded handoff, not implemented as a
production design. Its machine-readable source is
[selection-profile.json](selection-profile.json), and the immutable approval is
recorded in [selection-decision.json](selection-decision.json). `status` is
`approved_for_bounded_handoff`, `initialBoundedHandoffAuthorized` is `true`,
current `implementationAuthorized` is `false`, and
`explicitSelectionRequired` is `false`. The initial closed
[handoff v1](implementation/handoff-v1.md) is superseded by the closed
[handoff v2](implementation/handoff-v2.md), which records the two no-network
packages as completed. `route.refresh` remains the only active traversal-related
protocol message.

The profile status and `initialBoundedHandoffAuthorized` preserve the original
bounded design approval; they are not a current execution grant. The structured
`currentExecutionAuthority` object and top-level `implementationAuthorized=false`
fail closed for machine readers. The latest controlled-spike decision is
[decision v3](controlled-network-spike/decision-v3.md), and the current handoff
is [handoff v6](implementation/handoff-v6.md). They reject libjuice v1.7.2 at
the mandatory source-audit stage before compilation. libnice 0.1.23 is
`proposed_not_selected`, with no acquisition, compile, socket, runtime-network,
Phase B, or production authority.

## Approved Choice

The combined profile `production_p2p_nat_v1_recommended` is approved:

- `authenticated-encrypted-ice-turn` for authenticated, end-to-end protected
  candidate exchange, standards-based direct checks, consent freshness, and
  bounded TURN fallback.
- `transport-neutral-identity-session` as the only application-readiness gate on
  both direct and relayed paths.
- `relay-only-sealed-signaling` as the mandatory rollback and emergency fallback.
- Defer `decentralized-rendezvous`, `ice-quic-identity-session`, and
  `relay-first-direct-promotion` until the single-path profile has measured
  security, reliability, latency, memory, battery, and operational evidence.

This approval follows the existing recommendations without turning the bounded
handoff into implementation or deployment authorization. A connected ICE, TURN,
relay, or other transport path still proves only reachability. The application
channel becomes ready only after both paired
endpoint identities, roles, pair state, ephemeral keys, nonces, generation,
suite, and selected path context are bound into one canonical transcript and key
confirmation succeeds.

## Selection Effect

This approval authorizes only a versioned implementation handoff for three
ordered packages:

1. Freeze canonical sealed-record and identity-session contracts with Swift/Kotlin
   fixed vectors and strict resource ceilings.
2. Build a no-network conformance harness for candidate policy, replay,
   transcript, fallback, and state ownership. It may not open candidate sockets
   or select a networking library.
3. Prepare controlled-spike Phase A evidence from offline user-provided or
   pre-existing workspace source, while keeping every source-acquisition,
   runtime, harness, and production network-I/O gate closed.

It does not authorize production deployment, public signaling, STUN/TURN,
candidate exchange, hole punching, direct application traffic, a concrete
library, QUIC, decentralized rendezvous, relay-first promotion, or any physical
Android, optical QR, live-network, performance, battery, or interoperability
claim.

The handoff history is closed and bounded: `canonical-contracts` and
`no-network-conformance` are completed, while historical `handoff-v4` records
the original Phase A approval and historical `handoff-v5` records the consumed
one-shot source and NDK acquisition authority. Current `handoff-v6` records the
mandatory libjuice rejection and closes implementation, replacement
acquisition, compiler, source-fork, runtime, harness, socket, Phase B, and
production authority. Any libnice source or dependency acquisition requires a
separate explicit versioned decision.

## Security Floors

- `routeToken` is never candidate, ICE, TURN, signaling, transcript, capability,
  or traffic-key material.
- Signaling service authentication and candidate-envelope authentication are
  independent checks.
- Candidate authentication never bypasses destination policy. Loopback,
  unspecified, multicast, broadcast, link-local, arbitrary URL/hostname,
  redirect, DNS-rebinding, arbitrary payload, and unconstrained fanout forms fail
  before network I/O. Private scope stays default-deny without an approved
  same-link policy.
- Direct and fallback paths enforce the same paired identity, role, transcript,
  key-confirmation, replay, version, and algorithm floor.
- Rollback disables direct traversal; it never enables plaintext signaling,
  anonymous peers, legacy production identity, or weaker session cryptography.
- Every candidate, transaction, generation, allocation, retry, timer, and session
  collection has explicit count, byte, time, and concurrency bounds.
- Signaling, STUN, TURN, and relay components never receive backend credentials,
  prompts, responses, files, memory, model lists, backend URLs, or endpoint
  traffic keys.

## Spike Exit Criteria

The first two packages are no-device and no-network work. They pass only when:

- Swift and Kotlin canonical vectors match, including negative vectors for
  omitted, duplicate, reordered, unknown, non-canonical, expired, replayed,
  cross-pair, cross-role, and lower-suite fields.
- Prohibited targets and malformed candidate forms fail before network I/O.
- Identity substitution, stale generations, path/fallback races, and downgrade
  attempts never create an application-ready channel.
- Logs, persistence, protocol projections, and diagnostics exclude raw
  candidates, route secrets, traffic keys, application payloads, and stable
  service-linkable pair identifiers.
- All state and work queues prove explicit count, byte, time, retry, and
  concurrency ceilings.

A later controlled network spike must report, rather than infer, direct and relay
success, p50/p95/p99 setup time, memory, CPU, battery, service bytes, consent
traffic, relay occupancy, revocation closure, false abuse rejection, and rollback
behavior across the approved NAT and mobility matrix.

## Open Decisions Before Network I/O

[Pre-network review v1](pre-network/review-v1.md) preserves the original
`proposed_not_selected` proposal. The separate immutable approval decision
selects all seven recommendations for service ownership and trust, pair
authorization and retention, candidate privacy and scope, ICE and consent,
TURN credentials and abuse policy, application-request transition semantics,
and measured release budgets.

The historical [controlled-spike review v1](controlled-network-spike/review-v1.md)
proposes concrete library, cryptography, harness, and egress choices and retains
zero decisions. The separate immutable [phase A approval decision](controlled-network-spike/decision-v1.md)
conditionally selects all four recommendations for source audit, compile-only,
cryptographic-vector, and static-harness evidence. `handoff-v4` authorizes that
historical bounded work. The exact acquisition decision and handoff were then
closed as `decision-v2` and `handoff-v5`. The resulting source audit rejected
libjuice, so [fallback review v2](controlled-network-spike/review-v2.md) proposes
libnice 0.1.23 without selecting it, and `decision-v3` plus `handoff-v6` close
all current implementation and execution authority. Source or dependency
acquisition, compilation, runtime/harness network I/O, sockets, Phase B,
measurement, and deployment require a later explicit versioned decision.

## Evidence Boundary

This approved bounded handoff refines the existing 13-artifact static design
portfolio. It does not add production P2P code, activate a new protocol namespace, execute the conditionally selected library, open
network sockets, exercise STUN/TURN, prove NAT traversal, or provide physical
Android, optical QR, different-network, latency, memory, battery, or production
evidence. The latest records prove only exact libjuice and NDK acquisition plus
static source-audit rejection; they do not prove compilation, ABI compatibility,
library execution, or network behavior.
