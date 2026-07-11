# Security Hardening Proposal: Bind Identity Across Traversal And Relay Fallback

## Decision

Choose how a production AetherLink session authenticates both paired endpoints,
binds the nominated network path, survives direct-path failure, and transitions
between P2P and blind relay without replay, downgrade, identity substitution, or
revocation gaps.

## Executive Recommendation

We have three serious options. **Option 1: Transport-Neutral Secure Session Over
Nominated Path** establishes one endpoint-owned identity session over any
validated local, P2P, or relay path. **Option 2: ICE Bootstrap + QUIC Session
Spike** evaluates a transport with native secure handshake and path migration
after ICE nomination. **Option 3: Relay-First Session Then Direct Promotion**
starts reliably on relay and promotes an existing session after direct validation.

I recommend Option 1. The security contract should not depend on which path wins
or on one transport's migration behavior. A canonical peer-verified transcript,
explicit path binding, anti-replay state, fail-closed downgrade rules, revocation,
and relay fallback can then be tested once across transport implementations.
Option 2 is a contained performance/reliability spike after that contract exists.
Option 3 is attractive when connection latency dominates relay cost, but its
promotion state machine is more complex.

The recommended machine option ID is `transport-neutral-identity-session`.

## Evidence

The evidence set is the 13 source artifacts pinned by
`docs/security-hardening/production-p2p-nat-v1/evidence.sha256`. The identifiers
below describe the current session and lifecycle facts relevant to this decision.

| Evidence | Repository source | What it establishes |
| --- | --- | --- |
| `E001` | `apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeRemoteRoutePlanner.kt` | Android prepares P2P before relay from one pending or trusted identity source and filters incomplete/expired material, but route preparation does not bind a successful path into an endpoint identity transcript. |
| `E002` | `apps/android/core/pairing/src/main/java/com/localagentbridge/android/core/pairing/PairingStore.kt` | The trusted runtime identity and current P2P/relay route state persist together; P2P expiry/nonce are durable, while no session replay window or nominated-path receipt is stored. |
| `E003` | `apps/android/core/pairing/src/main/java/com/localagentbridge/android/core/pairing/RuntimePairingPayload.kt` | QR pins runtime identity and carries opaque remote-route material, but it does not define a traversal-session suite, transcript, path-binding, or downgrade floor. |
| `E004` | `apps/android/core/transport/src/main/java/com/localagentbridge/android/core/transport/RuntimeConnectionManager.kt` | P2P and relay connectors both return `RuntimeProtocolChannel`; failed routes are attempted in order. This is a transport-neutral integration seam, not authenticated path migration. |
| `E005` | `apps/android/core/transport/src/main/java/com/localagentbridge/android/core/transport/RuntimePeerToPeerRoutePreparation.kt` | Prepared P2P state binds identity, record ID, expiry, nonce, and version before connection, but has no endpoint key exchange, consent result, or nominated tuple digest. |
| `E006` | `apps/macos/CompanionCore/Sources/CompanionAppModel.swift` | The app model coordinates pair route activation/refresh and trusted-pair removal; delayed route work is generation-guarded, providing a place to reject stale session activation. |
| `E007` | `apps/macos/CompanionCore/Sources/LocalRuntimeMessageRouter.swift` | Existing application authentication challenges and route-refresh authorization gate runtime commands and can bind a transport context, but this does not yet define a production P2P identity transcript. |
| `E008` | `apps/macos/CompanionCore/Sources/MacRuntimeConnectionManager.swift` | Pair-scoped private-overlay and relay transports have independent generation IDs, callback leases, stop claims, and disconnect forwarding; pair removal can close both resources. |
| `E009` | `apps/macos/Pairing/Sources/PairingCoordinator.swift` | QR pairing proves long-term runtime/client key possession and establishes the identities that a production traversal transcript must bind. |
| `E010` | `apps/macos/Transport/Sources/RuntimeTransport.swift` | Runtime transport exposes lifecycle and disconnect interfaces independent of route selection; it does not expose a security context, so a new secure-session adapter is required above this seam. |
| `E011` | `packages/protocol-schema/pairing-qr.schema.json` | The QR contract includes identity and route bootstrap fields but no minimum session suite, path-migration authority, or production downgrade policy. |
| `E012` | `packages/protocol-schema/protocol.schema.json` | `hello`, `auth.challenge`, `auth.response`, pairing, and relay allocation messages carry identity and optional transport bindings; no schema binds both endpoint identities and nominated traversal path in one production transcript. |
| `E013` | `shared/protocol/fixtures/macos-compact-p2p-rendezvous-pairing-uri.txt` | The fixture demonstrates QR bootstrap of runtime identity plus opaque P2P state, not a completed endpoint handshake or direct-to-relay continuity proof. |

Observed: route-specific connectors converge on a common protocol channel and
existing command authentication can carry a transport binding. Observed: macOS
already has independent lifecycle ownership for private-overlay and relay paths.
Inferred: without one peer-verifiable transcript and explicit transition rules,
a connector could authenticate a route record yet expose a channel for the wrong
peer, accept a replayed session on a new path, or downgrade from a failed direct
attempt to weaker relay semantics.

## Current Design And Failure Mode

Android validates prepared route identity, expiry, nonce, and separation from the
pairing route token, then asks the relevant connector for a generic protocol
channel. The route manager falls through after failure. macOS can run pair-scoped
private-overlay and relay transports independently and invalidates stale callbacks
on replacement or removal. Application authentication protects runtime commands.

What is missing is a single production session ceremony spanning traversal and
application authorization. A path may be reachable without proving it terminates
at the pinned runtime and paired client. Existing route expiry is not sufficient
anti-replay for session handshakes. A relay can forward ciphertext but could still
substitute handshake metadata unless both endpoints verify the same transcript.
Direct-to-relay fallback can accidentally become a downgrade if the relay path
accepts an older suite. Path migration can also permit off-path injection unless
the new tuple is validated and authorized by the live session. Local pair removal
must close active direct and relayed sessions, not only prevent future commands.

## Desired Invariants

- Every production session mutually proves possession of the pinned runtime key
  and paired client key before application traffic is accepted.
- The canonical identity transcript covers protocol/suite version, both long-term
  identities, both fresh ephemeral contributions, both session nonces, pair/route
  generation, rendezvous record digest, path-validation result, roles, and any
  relay capability or signed lease digest.
- Path-specific inputs are authenticated by that canonical transcript; pairing
  route tokens remain bootstrap authority and never become session keys.
- Traffic keys are endpoint-owned and independent of rendezvous, discovery, and
  relay infrastructure. Those services cannot authenticate as either endpoint or
  decrypt application frames.
- Handshake attempts have unique identifiers, narrow expiry, role separation, and
  durable or bounded replay rejection. A valid proof from one path, pair, role,
  generation, or suite fails everywhere else.
- A nominated direct path is an input to the transcript, not endpoint identity.
  Identity remains stable across paths, while every new path undergoes exact tuple
  validation and live-session authorization before carrying traffic.
- Consent freshness loss stops the affected direct path. Relay fallback creates
  or resumes only under an authenticated transition and preserves the same peer
  identities, transcript floor, and frame security.
- A direct path cannot promote itself based only on seeing encrypted packets; both
  endpoints confirm promotion and packet-number/epoch ownership before relay is
  retired.
- Production negotiation has a pinned minimum suite. Unknown, omitted, lower, or
  conflicting versions fail closed; route failure never selects development
  plaintext or identity-v1 behavior.
- Pair removal, key rotation, route supersession, expiry, or signed revocation
  invalidates pending handshakes, consent, migration, relay allocations, and
  active sessions within a measured bound.
- Duplicate, reordered, delayed, or simultaneously delivered packets across old
  and new paths cannot execute an application request twice.

## Constraints And Non-Goals

The design preserves QR-first pairing, the common protocol channel, runtime-only
model access, P2P-first planning, and blind encrypted relay fallback. It must work
across Android and macOS and tolerate interface changes and mobile sleep. It does
not choose a concrete transport or cryptography library, promise seamless session
continuity under every network failure, solve endpoint compromise, hide traffic
analysis, define account recovery, or make relay-side admission a substitute for
peer authentication.

## Before Architecture

[Before architecture](../diagrams/identity-bound-traversal-and-relay-fallback-before.mmd)

The before view has sound route ordering and resource ownership but no canonical
production handshake covering the chosen path. P2P and relay each yield a
protocol channel, after which existing authentication runs. There is no reviewed
state machine for binding, migration, simultaneous paths, packet replay across
paths, or revocation of an active session.

## Options

The reader-facing options map to machine IDs `transport-neutral-identity-session`,
`ice-quic-identity-session`, and `relay-first-direct-promotion`, respectively.

### Option 1: Transport-Neutral Secure Session Over Nominated Path

This option defines an AetherLink secure-session layer above any validated byte
or datagram path. Traversal supplies a path-validation receipt containing the
exact local/remote tuple digest, candidate generations, check transaction digest,
consent epoch, and route capability digest. The endpoint handshake combines that
receipt with both long-term identities, fresh ephemeral contributions, fresh
nonces, roles, pair state, and the minimum suite. Both peers sign the canonical
transcript and confirm derived traffic keys before exposing a protocol channel.

The session owns ordered packet/message numbers, direction-separated key epochs,
duplicate rejection, and a path set. Adding a path requires a challenge sent and
answered on that exact tuple plus an authorization derived from the existing
session. If the original session is unavailable, fallback establishes a fresh
session with fresh nonces rather than replaying old proofs. Relay capability and
lease digests enter the same transcript when relay carries the path. The relay
can enforce admission as defense in depth but cannot terminate endpoint identity.

[Option 1 architecture](../diagrams/identity-bound-traversal-and-relay-fallback-transport-neutral-after.mmd)

| Change | Before | After | Security consequence | Cost |
| --- | --- | --- | --- | --- |
| Peer authentication | Existing channel auth after connector | Mutual signature and key confirmation over one canonical transcript | Binds identity before application traffic on every path | New cross-platform session layer |
| Path identity | Route object and connector result | Exact validated tuple receipt in transcript | Rejects path/handshake substitution | Receipt canonicalization and path state |
| Replay | Route expiry and nonce | Attempt IDs, expiry, packet epochs, bounded replay state | Rejects cross-path and stale-session proofs | Counters and persisted high-water state where needed |
| Fallback | Retry next connector | Authenticated new path or fresh session at same suite floor | No weaker relay downgrade | Transition latency and failure handling |
| Revocation | Pair lifecycle stops resources | Session-wide close and generation tombstone | Bounds active compromise | Revocation delivery and offline behavior |

Consent freshness belongs to path validity and session liveness. Losing direct
consent marks that path unusable and triggers relay acquisition; it does not
erase identity or permit a lower suite. During transition, one path is primary
and duplicate suppression spans both until an explicit cutover barrier completes.

### Option 2: ICE Bootstrap + QUIC Session Spike

This option uses authenticated ICE nomination only to obtain a path, then runs a
QUIC-based endpoint session whose handshake authenticates the paired identities
and whose connection migration validates later paths. The spike must implement
the same canonical identity inputs, suite floor, relay capability binding,
revocation behavior, and application duplicate semantics as Option 1. Native
packet protection, stream multiplexing, loss recovery, and migration may reduce
custom transport work.

The security concern is semantic mismatch. A transport certificate or resumption
ticket is not automatically the AetherLink pair identity. A connection ID is not
proof that a new path belongs to the paired peer. Zero-round-trip application
data can replay unless prohibited or restricted to explicitly idempotent messages.
Resumption after pair revocation, route generation change, or suite increase must
fail. Relay fallback may require a newly validated path or a fresh connection if
the relay path cannot safely join the existing connection.

[Option 2 architecture](../diagrams/identity-bound-traversal-and-relay-fallback-quic-after.mmd)

| Change | Before | After | Security consequence | Cost |
| --- | --- | --- | --- | --- |
| Session transport | Generic protocol channel | QUIC-based paired session | Reuses mature packet protection and recovery semantics | Platform integration and behavior audit |
| Identity | Application auth | Pair identity bound into handshake/exported transcript | Prevents certificate-only trust substitution | Custom identity binding remains required |
| Migration | None | Native migration plus AetherLink path authorization | Supports interface change if both checks pass | Complex NAT/relay edge cases |
| Early data | Not defined | Disabled for mutations by default | Avoids replayed commands | Potential reconnect latency |
| Fallback | New relay connector attempt | Migration where valid, otherwise fresh relay session | Can preserve continuity without downgrade | Two fallback modes to verify |

This is explicitly a spike, not a library choice. It succeeds only if fixed
vectors, adversarial path tests, revocation, battery, binary size, and operational
measurements show that the required semantics are simpler and safer than the
transport-neutral baseline.

### Option 3: Relay-First Session Then Direct Promotion

This option starts every remote connection over the blind relay, completes the
identity-bound secure session there, and performs candidate gathering and direct
checks in the background. A direct path is added to the live session only after
exact tuple validation, consent, and a promotion exchange authenticated by the
current session. Relay remains active until both sides acknowledge a packet-number
barrier and prove traffic on the direct path.

Relay-first reduces time-to-authenticated-session variance and lets direct checks
use the established session for authorization, making blind scans and identity
substitution harder. It increases relay load and exposes source/timing metadata
for every session. Promotion introduces dual-path races: delayed relay packets,
direct packets, retransmission, and cancellation must share one replay/duplicate
domain. If promotion or consent fails, relay continues without reauthentication;
if the relay session dies first, a fresh direct session is required.

[Option 3 architecture](../diagrams/identity-bound-traversal-and-relay-fallback-relay-promotion-after.mmd)

| Change | Before | After | Security consequence | Cost |
| --- | --- | --- | --- | --- |
| Initial path | P2P first | Relay first | Reliable authenticated base before direct checks | Relay bandwidth and metadata for all sessions |
| Direct setup | Independent connector | Live-session-authorized background checks | Strong authorization context for traversal | More concurrent resources |
| Promotion | None | Two-sided barrier and shared replay domain | Prevents unauthenticated path takeover and duplicates | Difficult race and recovery testing |
| Fallback | Relay after P2P failure | Relay remains until direct proven | Near-zero fallback transition | Relay retirement policy and cost |

Downgrade is minimized because one established session controls promotion. Pair
revocation must still terminate both relay and candidate direct paths immediately;
keeping relay alive is not authority to outlive session or route expiry.

## Comparison

| Dimension | Option 1: Transport-Neutral Session | Option 2: ICE + QUIC Spike | Option 3: Relay-First Promotion |
| --- | --- | --- | --- |
| Security | One explicit identity/path contract across transports | Strong transport machinery if pair binding, early-data, and migration rules are correct | Strong initial authorization; largest dual-path transition surface |
| Performance | One endpoint handshake after path nomination | Potentially efficient multiplexing, recovery, and migration | Fast predictable start; all sessions initially consume relay |
| Memory | Session keys, replay window, bounded path set | Transport connection, streams, recovery, migration state | Concurrent relay/direct state during promotion |
| Reliability | Fresh fallback session is simple but may interrupt requests | Native recovery may help; platform/network variance | Relay continuity masks direct failures; relay outage remains critical at start |
| Operability | Custom session telemetry and versioning | Transport-specific diagnostics and tuning | Relay capacity plus promotion diagnostics |
| Migration | Clear dual-stack session version | Contained spike then broader integration | Requires relay-first product behavior and dual-path rollout |

No latency, battery, memory, migration-success, or relay-cost result is measured.
The options must be compared on identical NAT matrices and failure injection with
the same identity and downgrade requirements.

## Recommendation

Recommend Option 1 (`transport-neutral-identity-session`) as the normative security architecture. Define the identity
transcript, path receipt, replay domain, suite floor, revocation, and transition
state machine independently of transport. Run Option 2 only as a bounded spike
against that contract. Keep Option 3 as an operational alternative if measured
direct nomination latency or reliability makes P2P-first unacceptable.

## Evidence Coverage And Residual Risk

| Evidence | Option 1 | Option 2 | Option 3 |
| --- | --- | --- | --- |
| `E001` planner | Retains P2P-first and secure relay fallback | Retains order with ICE/QUIC connector | Intentionally changes production remote order to relay-first |
| `E002` stored state | Adds suite floor and replay/generation high-water state | Adds resumption invalidation state | Adds promotion and active-session generation state |
| `E003` QR identity | Bootstraps transcript identity and minimum suite | Also bootstraps transport identity policy | Bootstraps relay session then direct authority |
| `E004` common channel | Becomes secure-session output | Becomes QUIC session adapter output | Existing relay channel anchors promotion |
| `E005` prepared P2P | Supplies rendezvous digest and path receipt inputs | Supplies ICE inputs before QUIC | Supplies background direct inputs |
| `E006` app model lifecycle | Guards stale session activation and revocation | Also invalidates resumption/migration | Owns promotion generations and concurrent resources |
| `E007` router auth | Moves behind confirmed production session | Binds app auth to exported session transcript | Runs once on relay session and remains bound through promotion |
| `E008` manager ownership | Closes all session paths together | Coordinates QUIC and relay fallback resources | Extends independent resources with atomic promotion ownership |
| `E009` pairing proof | Supplies both long-term identities | Supplies transport identity credentials | Supplies initial relay-session identities |
| `E010` lifecycle seam | Requires a new route-independent session adapter | Requires a new QUIC adapter | Requires relay-session and direct-path adapters |
| `E011` QR schema | Needs suite floor and session bootstrap version | Needs QUIC experiment suite identifier | Needs relay-first/promotion policy |
| `E012` protocol schema | Adds transcript, path, revocation, fallback errors | Adds resumption/migration constraints | Adds promotion/barrier states |
| `E013` fixture | Gains deterministic transcript bootstrap vectors | Gains spike suite vector | Gains relay-first policy vector |

Residual risks include compromise of either endpoint, denial or traffic analysis
by network infrastructure, rollback of local replay state, clock skew, packet
duplication around failover, platform suspension delaying consent or revocation,
and flaws in canonical cross-language encoding. Relay fallback improves reachability
but does not guarantee availability. Existing no-device route/lifecycle tests do
not prove real P2P, path migration, different-network operation, physical Android,
public relay behavior, latency, or battery cost.

## Migration And Rollout

1. Freeze canonical transcript, path-validation receipt, suite negotiation,
   replay, revocation, transition, and error encodings with cross-language vectors.
2. Add a production session-suite floor to fresh QR and authenticated migration;
   this protocol floor is fail-closed, and legacy routes remain explicitly
   development-only.
3. Implement verification-only transcript construction on both endpoints and
   compare digests while existing development traffic remains unchanged.
4. Require mutual identity proof and key confirmation over relay-only production
   sessions; reject missing or lower-suite bindings.
5. Add direct nominated paths under Option 1 for controlled cohorts. On any
   ambiguity, close the attempt and create a fresh authenticated relay session.
6. Add bounded dual-path transition only after packet replay, duplicate request,
   cancellation, and revocation tests pass under loss and reordering.
7. Connect trusted-pair removal, key rotation, route supersession, expiry, and
   signed revocation to pending and active session closure on every path.
8. Run the Option 2 spike behind a distinct suite identifier; do not silently
   negotiate it from Option 1 or reuse incompatible resumption state.
9. Roll back by disabling direct/migration suites and using the authenticated
   relay production suite, never by accepting development identity or plaintext.

## Validation Plan

- Adversarial identity substitution, cross-path replay, and failover race tests
  must fail closed before any application request becomes ready.
- Fixed Swift/Kotlin vectors for transcript fields, roles, identity keys,
  ephemeral shares, nonces, route generation, path receipt, relay capability,
  suite floor, key confirmation, and traffic-key directions.
- Negative tests for omitted, reordered, duplicated, unknown, non-canonical, or
  lower-version fields and valid signatures replayed under another role/path/pair.
- Handshake replay tests across expiry, app restart, route refresh, pair removal,
  key rotation, relay allocation, and restored backup state.
- Path validation tests for off-path response, NAT rebinding, connection migration,
  source-address change, simultaneous interfaces, consent loss, and stale tuple
  reuse. A connection identifier alone must never authorize a new path.
- Fallback fault injection before and after key confirmation, application request,
  partial response, cancellation, packet-number barrier, direct promotion, relay
  retirement, and disconnect callback.
- Duplicate-delivery tests proving chat, model, attachment, memory, and mutation
  requests execute at most once when old/new paths overlap or reorder packets.
- Downgrade tests proving every direct failure and unsupported suite reaches only
  an equal-or-stronger authenticated relay route or a clear failure.
- Revocation tests measuring closure of pending handshakes, direct consent,
  migration, relay binding, active session, and resumed session after pair removal.
- Option 2-specific tests for early-data replay, resumption after revocation,
  migration to unvalidated paths, stream limits, connection-ID rotation, and
  fallback requiring a fresh session.
- Real-device NAT and mobility matrix with p50/p95/p99 connection, failover, and
  promotion time; memory, CPU, battery, bytes, relay occupancy, and false
  disconnect measurements reported separately from no-device proof.

## Implementation Work Packages

- Canonical transport-neutral identity transcript, suite negotiation, key
  confirmation, and cross-language vector specification.
- Path-validation receipt and bounded path lifecycle integrating nomination,
  consent freshness, relay capability, and route generation.
- Session replay/duplicate domain, direction/epoch key schedule, request
  idempotency boundary, and fail-closed counter exhaustion.
- Authenticated fallback and optional dual-path transition state machine with
  explicit primary path and cutover barrier.
- Pair removal, key rotation, route expiry/supersession, signed revocation, and
  resumption invalidation across Android and macOS resource owners.
- Transport adapter conformance harness for the baseline and the isolated
  ICE-bootstrap/QUIC spike.
- Adversarial, crash, mobility, NAT, performance, battery, and rollout telemetry
  validation.

These packages define behavior rather than selecting a concrete library, and
they begin only after the option and protocol are approved.

## Open Questions

- Must application requests survive direct-to-relay transition transparently, or
  may non-idempotent in-flight requests fail and be retried by explicit policy?
- Which transcript state must persist across process restart to reject replay
  without creating permanent lockout after legitimate recovery?
- What is the maximum acceptable revocation-to-active-session closure time when a
  device is sleeping or temporarily offline?
- Is path migration required for the first production release, or is a fresh
  identity-bound relay session an acceptable fallback?
- What measured setup latency, relay occupancy, and battery result would justify
  relay-first promotion over P2P-first nomination?
- Should the Option 2 spike prohibit all early data, or can a narrowly enumerated
  set of read-only operations be proven replay-safe?
