# Security Hardening Proposal: Pair Epoch Recovery And Immediate Revocation

## Decision

Choose how AetherLink invalidates a compromised or lost paired device, closes
active relay sessions, rotates trust to replacement keys, and rejects replay or
rollback across offline periods without introducing an account recovery service.

## Executive Recommendation

We have three options. **Option 1: Short Leases And Manual Re-Pair** tightens the
existing generation model but leaves revocation eventual. **Option 2: Monotonic
Pair Epoch State Machine** adds deny-only emergency revocation and requires a
fresh QR ceremony for key replacement. **Option 3: Threshold Recovery** permits
two-of-N trusted devices or an offline recovery key to authorize replacement.

I recommend Option 2. It fits the current one-runtime/one-client trust model,
keeps QR as the out-of-band recovery authority, and makes the dangerous
transition explicit: a single current key may stop access, but it may not replace
the other key or lower the pair epoch. Option 3 should remain deferred until the
product has a real multi-client or offline recovery-key requirement.

## Evidence

I inspected paired allocation state, QR-pinned identity, route persistence,
matcher lifetime, and shared protocol fields. The current system has strong
generation continuity inside one lease lifecycle, but no durable state machine
for replacing a compromised long-term key.

| Evidence | Finding or document | What it establishes |
| --- | --- | --- |
| `E004` | Runtime/client co-authorized paired lease continuity | Paired renewal requires both current endpoint keys and binds exact current/next lease state. |
| `E005` | QR-pinned mutual device identity | Initial pairing is the existing user-authorized out-of-band ceremony for both long-term keys. |
| `E006` | Paired admission and strict frame activation | Client/runtime identity proofs bind current session nonce, ephemeral key, lease, and transport state before encrypted frames. |
| `E007` | Durable generation and consumed-bootstrap CAS | The registry persists monotonic generation and prevents consumed bootstrap recreation, but it has no pair epoch or revocation counter. |
| `E008` | Client route and secret persistence | Android stores pinned runtime identity, lease generation, nonce, expiry, and secret handle; lower-level storage has no rollback-resistant pair epoch. |
| `E009` | Missing recovery transition in shared schema | The protocol has allocation authorization and transport binding but no recovery, revocation receipt, pair epoch, or service keyset contract. |
| `E010` | Development-relay source-aware allocation controls | Paired claim/renew attempts, including malformed renewal records, consume the allocation-mutation source bucket before full parsing, authorization, and proof work; burst capacity cannot reset before full refill. This adds no recovery authority or epoch state. |
| `E011` | Development-relay source peer quotas | Exact-source accepted connections and unmatched waiters are bounded with pre-waiter headroom, atomic waiting-insertion checks, global/source reserve provenance, counterpart-only admission for immediate matches or authenticated same-source waiting replacement, rejection when per-source reserve targets another source, cross-source reserve replacement rejection, and matcher-atomic release. This adds no recovery authority, pair epoch, revocation transition, or signed state receipt. |
| `E012` | Development-relay bounded waiting and authenticated identity fairness | First-insertion monotonic waiting deadlines are lease-capped, registration/readiness decisions atomically expire late rooms before matching or replacement, and waiting results carry the deadline without a post-publication room lookup. Verified runtime and paired-client identities receive role-separated cross-source waiting quotas after proof. Bootstrap and legacy peers remain source-only and active bridges are uncharged. This adds no recovery authority, pair epoch, revocation transition, or signed state receipt. |

Observed: lease renewals advance generation and nonce; client/runtime trust can be
removed locally; waiting generations can be invalidated. Observed: an active
relay room has no service-wide signed revocation transition. Inferred: a copied
endpoint state or compromised long-term key can remain useful until lease expiry
or local removal reaches every relevant component, and a restored old backup has
no monotonic pair epoch with which to detect rollback.

## Current Design And Failure Mode

The current pair claim rotates a runtime-only bootstrap allocation into a
deterministic runtime/client room. Later renewal requires both device signatures,
increments generation, advances expiry, and changes nonce. This blocks a stale
writer from silently replacing the winning lease. Runtime application sessions
also re-check trusted-device state and clear authentication after local removal.

Those controls do not define compromise recovery. If a client key is stolen, the
runtime can remove it locally, but the allocation service does not receive a
signed emergency revocation that closes all active and waiting rooms immediately.
If the runtime key is stolen, the Android client has no protocol state stating
that a fresh QR-authorized runtime key at epoch N+1 supersedes every lease and
proof from epoch N. Restoring an old device backup can also restore old trust and
route metadata without a service receipt proving it is below the current epoch.
The relay currently commits paired allocation state before returning the final
response, while each endpoint persists the new generation later. A lost response
can therefore leave the authority at N+1 and both endpoints at N without a
read-only signed reconciliation operation.

## Desired Invariants

- Pair trust is identified by a pseudonymous `pair_id` and monotonic positive
  `pair_epoch`; every lease, registration, endpoint transcript, route refresh,
  and application authentication binds both.
- Normal lease renewal requires both current device keys and advances generation
  within the current pair epoch.
- Either current device may issue a deny-only emergency revocation. It may close
  access and advance a revocation counter, but cannot authorize a new key.
- Key replacement requires a fresh QR ceremony, proof by the surviving/new
  endpoint keys appropriate to the recovery case, a fresh endpoint traffic
  secret, and `pair_epoch + 1`.
- A relay or endpoint rejects any lower epoch, lower revocation counter,
  non-advancing generation, service keyset rollback, or reuse of a transition id
  with different request content even if an old signature remains valid.
- Revocation closes waiting and active rooms and makes later frames from those
  room handles fail; it is not only a UI trust-store update.
- Offline endpoints can reconnect after receiving a current signed state receipt;
  they never infer recovery from wall-clock order alone.
- Every mutation binds an idempotent `transition_id` and canonical request digest.
  Repeating the same id and digest returns the original signed receipt; the same
  id with different content fails; a competing id from the same prior state
  returns the signed winning state.
- A read-only authenticated status operation returns the current signed state
  without extending a lease or authorizing a key, so response loss and crashes
  converge without guessing or creating another epoch.

## Constraints And Non-Goals

We keep QR-first, account-free trust and endpoint-owned traffic secrets. A fresh
QR ceremony is acceptable for replacement because the user must have one trusted
endpoint and the replacement endpoint present. This proposal does not recover
when both endpoints and every recovery artifact are lost, hide denial-of-service
events, or allow a compromised current key to authorize its own replacement. It
does not define multi-user ownership or cloud account recovery.

## Before Architecture

[Before architecture](../diagrams/pair-epoch-recovery-before.mmd)

The current state is distributed between endpoint trust stores and relay lease
state. Generation is monotonic within one allocation, but there is no higher
epoch that invalidates every old key and lease. Local removal and lease expiry
are therefore the recovery mechanisms.

## Options

### Option 1: Short Leases And Manual Re-Pair

This option keeps the current schema and reduces exposure through short paired
leases, aggressive renewal, local trusted-device deletion, and mandatory fresh
QR pairing after removal. The development baseline already disables exposed
probe by default, bounds global sockets, suppresses `SIGPIPE`, reclaims one-sided
active bridges, deadlines control records across `EINTR`, and rejects
exposed legacy mode. Paired renewal attempts already consume the allocation-mutation
source bucket. That tactical control supplies neither pair epoch state, revocation
authority, active/waiting room-close fanout, nor signed status reconciliation;
explicit local key deletion and audit events for renewal and trust changes remain.

The strongest case is simplicity. It uses the already-tested dual-signature
renewal and generation CAS, introduces no global state machine, and naturally
limits a stolen lease. The main weakness is that compromise of a long-term key is
not bounded by lease duration if the attacker can continue co-authorizing or use
an active session. Lowering lease duration also increases control-plane load and
makes transient service outages more visible to users.

[Option 1 architecture](../diagrams/pair-epoch-recovery-lease-only-after.mmd)

| Change | Before | After | Security consequence | Cost |
| --- | --- | --- | --- | --- |
| Lease lifetime | 15-minute default foundation | Short production paired lease | Narrows stolen lease window | More renewals and outage sensitivity |
| Revocation | Local delete and expiry | Local delete plus no automatic reuse | No global immediate closure | Manual recovery remains |
| Key replacement | Ad hoc re-pair | Explicit fresh QR | Better operator discipline | No cryptographic epoch rollback guard |
| Active rooms | Close on transport lifecycle | Same | Compromised active session may continue | No relay fanout work |

Rollback is configuration-only, but longer leases re-open the exposure window.
This remains a baseline, not the target production recovery design.

### Option 2: Monotonic Pair Epoch State Machine

This option introduces a durable pair state shared by both endpoints and the
allocation authority. Its canonical fields are `pair_id`, `pair_epoch`, runtime
and client key fingerprints, `lease_generation`, `revocation_counter`,
`transition_id`, current service keyset version, status, and a digest of the
previous accepted state. The authority signs every accepted state receipt.

Normal renewal is familiar: both current keys authorize the next generation in
the same epoch. Emergency revocation is intentionally asymmetric. Either current
device can sign a deny-only transition that increments `revocation_counter`,
tombstones all leases in that epoch, and instructs relays to close waiting and
active rooms. This grants a compromised device denial-of-service authority, but
not replacement authority. We should be explicit that this is the safer failure:
a stolen key can stop connectivity, not silently install another trusted key.

Replacement requires a fresh QR. If the client is lost, the runtime removes it,
creates a new pairing code/secret, and authorizes a new client key at epoch N+1.
If the runtime key is rotated locally, the Android user scans a fresh QR that
pins the new runtime key and co-signs the transition from the currently trusted
client. If no surviving trusted key exists, the old pair is revoked and a wholly
new pair ID is created; no remote continuity claim is made. Every recovery
rotates the endpoint traffic secret and route token seed.

[Option 2 architecture](../diagrams/pair-epoch-recovery-state-machine-after.mmd)

| Change | Before | After | Security consequence | Cost |
| --- | --- | --- | --- | --- |
| Trust version | Lease generation only | Pair epoch plus generation and revocation counter | Detects key/backup rollback across lease families | New crash-safe state on endpoints and authority |
| Emergency action | Local removal | One-sided deny-only signed revocation | Immediate global closure without replacement authority | Deliberate DoS capability and fanout |
| Replacement | Re-pair without global epoch | Fresh QR epoch transition | Old keys and leases become permanently stale | Recovery UX and cross-device transaction |
| Active sessions | Transport/local trust lifecycle | Signed revocation closes active/waiting rooms | Bounds compromised live session | Relay room index and event delivery |
| Offline endpoint | Uses stored lease/trust | Must obtain current signed receipt | Rejects restored stale backups | Reconnect may require authority reachability |

Reliability depends on transactional state. Endpoint storage must persist the
highest accepted epoch/counter before activating new route material, and the
authority must make transition IDs idempotent. A crash between authority commit
and endpoint receipt is recovered by fetching the signed current state; it must
not create a second epoch. Rollback can disable new recovery creation, but an
endpoint that has accepted a higher epoch must never accept a lower one.

Planned two-phase in-band key rollover remains distinct from incident recovery.
It may require both current keys and proof of both replacement keys, but it may
not weaken one-sided deny-only revocation or substitute for fresh-QR replacement
when a current key is suspected compromised.

### Option 3: Threshold Recovery

This option adds a recovery quorum: two-of-N trusted clients, a runtime plus an
offline recovery key, or another explicit threshold can authorize an epoch
transition. It improves availability when one endpoint is lost and can avoid
requiring the compromised device to participate in replacement.

The attractive part is stronger continuity for future multi-client deployments.
The concern is authority growth. We would need enrollment, quorum membership,
offline key custody, lost-share revocation, UI that accurately explains quorum
state, and policy for conflicting recoveries. This begins to resemble an account
or organization recovery system, which the current product explicitly avoids.

[Option 3 architecture](../diagrams/pair-epoch-recovery-threshold-after.mmd)

| Change | Before | After | Security consequence | Cost |
| --- | --- | --- | --- | --- |
| Recovery authority | Current pair and fresh QR | Explicit threshold quorum | Tolerates one lost key without unilateral replacement | Multi-device/key enrollment and policy |
| Offline recovery | None | Optional offline recovery key | Survives endpoint loss | Backup theft and custody risk |
| Conflict resolution | None | Quorum transition ordering | Can reject minority recovery | Complex stale-share and partition handling |
| Product boundary | One runtime/client pair | Recovery membership plane | Enables future teams/families | Account-like UX and audit burden |

Migration would first deploy Option 2's pair epoch, then add quorum metadata in a
new epoch transition. Rollback can remove future quorum enrollment, but cannot
invalidate already accepted higher epochs or receipts.

## Comparison

| Dimension | Option 1: Short Lease | Option 2: Pair Epoch | Option 3: Threshold |
| --- | --- | --- | --- |
| Security | Narrows lease replay; long-term compromise remains | Immediate revoke, rollback rejection, QR-authorized replacement | Adds recovery availability and quorum compromise resistance |
| Performance | More frequent renewals | Small state/signature cost plus revocation events | More signatures and quorum collection |
| Memory | Current state | Bounded pair state, receipts, tombstones | Membership, shares, receipts, audit state |
| Reliability | Simple but outage-sensitive with short leases | Transaction/fanout complexity; deterministic recovery | Partition and quorum availability risks |
| Operability | Lease tuning and manual support | Revocation monitoring, recovery diagnostics, key/epoch support | Recovery-key lifecycle and quorum support |
| Migration | Configuration and UX | Protocol/schema/storage/relay transition | Foundational product and policy migration |

These effects are not measured. We should test state transition throughput,
revocation delivery time, reconnect latency after offline periods, storage growth,
and crash recovery under injected failures before setting production targets.

## Recommendation

I recommend Option 2. It gives us a falsifiable production recovery contract
without inventing an account authority. The intentional trade is that either
current endpoint can deny service. That is preferable to allowing one compromised
endpoint to replace trust. Option 3 should win only after multi-client recovery
is a product requirement with a clear owner and UX.

## Evidence Coverage And Residual Risk

| Evidence | Option 1 | Option 2 | Option 3 |
| --- | --- | --- | --- |
| `E004` - Paired co-authorization | Preserved | Becomes normal same-epoch transition | Extended to quorum transition |
| `E005` - QR-pinned identity | Manual re-pair | Authoritative key-replacement ceremony | Enrollment/recovery ceremony input |
| `E006` - Strict admission/session | Preserved | Adds epoch/receipt binding and forced closure | Adds epoch/quorum receipt binding |
| `E007` - Generation CAS | Shorter lease only | Nested beneath pair epoch and counter | Nested beneath epoch and quorum state |
| `E008` - Route persistence | Same fields | Adds rollback-resistant highest state | Adds quorum membership/share metadata |
| `E009` - Missing recovery schema | Unaffected | Addressed | Addressed with larger authority plane |
| `E010` - Development source limits | Preserved as tactical defense in depth | Preserved as tactical defense in depth | Preserved as tactical defense in depth |
| `E011` - Development source peer quotas | Preserved as tactical defense in depth | Preserved as tactical defense in depth | Preserved as tactical defense in depth |
| `E012` - Bounded waiting and authenticated identity fairness | Preserved as tactical defense in depth | Preserved as tactical defense in depth | Preserved as tactical defense in depth |

Residual risks include a compromised endpoint issuing denial-only revocation,
authority or relay refusal to propagate revocation, traffic analysis, both
endpoint keys compromised before recovery, rollback of local secure storage that
also defeats the monotonic record, and user confusion during a fresh QR recovery.
Hardware-backed monotonic storage is not uniformly available, so the service
receipt and explicit fresh QR failure path remain necessary.

## Migration And Rollout

1. Define canonical pair state and transition receipts with fixed cross-language
   vectors; add parse-only support without activation.
2. Persist highest pair epoch, revocation counter, service keyset version, and
   receipt digest atomically on both endpoints.
3. Include pair epoch and receipt digest in signed lease, registration, endpoint
   key exchange, app auth, and route refresh.
4. Add authority-side idempotent transition storage and lower-state rejection.
5. Add a read-only authenticated `pair.status` operation that returns the current
   signed state without mutating generation, epoch, counter, or expiry.
6. Add relay revocation events that close waiting and active rooms and reject
   later registrations for tombstoned state.
7. Add fresh QR replacement ceremonies for lost client and rotated runtime cases.
8. Run observe-only receipt comparison, then enforce on production-v3 routes.
9. Retain current generation-only behavior only on explicit development routes.

Tactical controls remain during rollout: short leases, local trust-store checks,
dual-signed paired renewal, consumed-bootstrap tombstones, session-bound identity
proofs, encrypted frames, and the development relay's bounded source-aware
allocation mutation bucket. These do not implement epoch, revocation, room-close
fanout, or signed status semantics.

## Validation Plan

- State-machine model tests for every valid transition and every invalid lower,
  duplicate, conflicting, skipped, or wrong-key epoch/counter transition.
- Fixed Swift/Kotlin vectors for canonical state, transition, revocation, recovery,
  and service receipt signatures.
- Crash injection before/after authority commit, endpoint persistence, secret
  rotation, route activation, and active-room closure; drop the final response
  after commit and require `pair.status` convergence without a second mutation.
- Replay old signed leases, registrations, route refreshes, auth frames, backup
  snapshots, revocation receipts, and recovery transitions after epoch N+1.
- Compromise drills for lost client, rotated runtime, stolen one endpoint key,
  both keys lost, offline endpoint, authority outage, relay partition, and delayed
  revocation delivery.
- Measure revocation-to-room-close p50/p95/p99, reconnect after offline duration,
  transition throughput, receipt storage growth, and false lockout rate.
- Verify revocation and recovery artifacts contain no traffic secret, prompts,
  responses, files, memory, model metadata, or backend credentials.

## Implementation Work Packages

- Canonical pair state, transition, receipt, read-only status, and error protocol
  definitions.
- Crash-safe pair-state persistence for macOS, Android, and allocation authority.
- Same-epoch renewal and deny-only revocation authorization verifiers.
- Relay active/waiting room revocation index and close propagation.
- Fresh QR recovery flows for client replacement and runtime key rotation.
- Endpoint secret/route-token rotation and lower-epoch fail-close integration.
- State-machine, crash, replay, partition, performance, and UX tests.

These work packages become implementation work only after the option is selected.

## Open Questions

- Is one-sided denial-of-service an acceptable emergency revocation authority?
- What revocation-to-active-room-close target is required?
- Can Android/macOS storage provide useful rollback resistance beyond signed
  service receipts, and what happens after OS backup restore?
- Should a fully lost pair create a new `pair_id` or retain a public continuity
  marker? The safer default is a new pair with no remote continuity claim.
- Which endpoint must be present for runtime key rotation, and how is the UI
  explicit about replacing the pinned runtime identity?
