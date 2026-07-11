# Security Hardening Proposal: Authenticate Rendezvous And Protect Candidate Exchange

## Decision

Choose how production AetherLink peers discover reachability, exchange network
candidates, and obtain direct or relayed connectivity without exposing private
addresses or turning rendezvous infrastructure into an SSRF, scanning, or
amplification service.

## Executive Recommendation

We have three serious options. **Option 1: Relay-Only Sealed Signaling Baseline**
removes direct candidates from the first production release and uses an
authenticated mailbox plus blind relay. **Option 2: Authenticated Encrypted
ICE+TURN** adds direct traversal with sealed, pair-scoped candidate exchange and
bounded relay fallback. **Option 3: Decentralized Rendezvous** distributes
sealed rendezvous records across multiple nodes.

I recommend Option 2. It matches the product requirement to attempt direct P2P
before relay while making candidate confidentiality, consent freshness, target
validation, and abuse accounting explicit protocol invariants. Option 1 is the
safe rollout baseline and emergency fallback. Option 3 should remain a later
availability and metadata-distribution step, not a prerequisite for secure
traversal.

The recommended machine option ID is `authenticated-encrypted-ice-turn`.

## Evidence

The evidence set is the 13 source artifacts pinned by
`docs/security-hardening/production-p2p-nat-v1/evidence.sha256`. The identifiers
below are descriptive references used throughout this proposal.

| Evidence | Repository source | What it establishes |
| --- | --- | --- |
| `E001` | `apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeRemoteRoutePlanner.kt` | Pending QR material or trusted state yields P2P before relay; complete opaque values, expiry, nonce, version, and identity matching are checked, but no candidates are decrypted or validated. |
| `E002` | `apps/android/core/pairing/src/main/java/com/localagentbridge/android/core/pairing/PairingStore.kt` | Android persists the opaque P2P record, encrypted body, expiry, nonce, and version with the trusted runtime while keeping relay secrets behind a separate secret-store boundary. |
| `E003` | `apps/android/core/pairing/src/main/java/com/localagentbridge/android/core/pairing/RuntimePairingPayload.kt` | QR parsing requires a complete `p2p_rendezvous` field family and canonical opaque values but defines no candidate schema, sender authentication, or network-target policy. |
| `E004` | `apps/android/core/transport/src/main/java/com/localagentbridge/android/core/transport/RuntimeConnectionManager.kt` | The connection manager orders prepared P2P and relay candidates, rejects identity mismatch, pairing-token reuse, and expiry, and falls through after connector failure. The P2P connector is only an injected interface. |
| `E005` | `apps/android/core/transport/src/main/java/com/localagentbridge/android/core/transport/RuntimePeerToPeerRoutePreparation.kt` | P2P preparation treats candidate material as opaque and enforces size, whitespace, version, expiry, nonce, and route-token separation; it contains no real signaling, ICE state, consent, or path checks. |
| `E006` | `apps/macos/CompanionCore/Sources/CompanionAppModel.swift` | Runtime route generation/refresh and pair lifecycle can carry P2P fields and coordinate overlay/relay resources, but production candidate gathering and rendezvous are intentionally absent. |
| `E007` | `apps/macos/CompanionCore/Sources/LocalRuntimeMessageRouter.swift` | Runtime commands pass through pairing and authentication gates, and route refresh is an authenticated application operation; this is an authorization anchor, not candidate-service authentication. |
| `E008` | `apps/macos/CompanionCore/Sources/MacRuntimeConnectionManager.swift` | macOS owns separate pair-scoped private-overlay and relay transports with generation leases, stop ownership, and disconnect propagation, providing a lifecycle seam for fallback without choosing traversal semantics. |
| `E009` | `apps/macos/Pairing/Sources/PairingCoordinator.swift` | Pairing establishes long-term runtime/client identity material and signed proof context that can derive a pair-scoped rendezvous authorization root. |
| `E010` | `apps/macos/Transport/Sources/RuntimeTransport.swift` | Runtime transport exposes lifecycle and disconnect interfaces but no protocol channel or security context; production rendezvous and candidate protection require a new adapter above this seam. |
| `E011` | `packages/protocol-schema/pairing-qr.schema.json` | The QR schema admits only a complete opaque P2P record family with protocol version and expiry; it deliberately does not standardize plaintext IP candidates. |
| `E012` | `packages/protocol-schema/protocol.schema.json` | `route.refresh` can carry complete relay and opaque P2P families and existing auth messages can carry transport bindings, but there is no offer/answer generation, consent, nominated path, or traversal error schema. |
| `E013` | `shared/protocol/fixtures/macos-compact-p2p-rendezvous-pairing-uri.txt` | The cross-platform fixture proves compact opaque rendezvous carriage only; `opaque-candidate-1` is test material, not evidence of encryption or NAT traversal. |

Observed: current code validates the envelope around opaque rendezvous material
and attempts an injected P2P connector before relay. Observed: no source in the
evidence set implements candidate gathering, authenticated address discovery,
hole punching, consent freshness, or a production P2P connector. Inferred: if a
future connector interpreted candidate bytes without a stricter design, a
compromised peer or rendezvous service could induce internal scans, reflect
traffic, expose private topology, or keep stale mappings alive.

## Current Design And Failure Mode

The current design is a deliberate seam. QR and authenticated `route.refresh`
carry a record ID, opaque body, expiry, anti-replay nonce, and version. Android
persists and prepares that record for the paired runtime identity. A connector,
if injected, receives the blob; failure proceeds to relay. This proves route
selection and lifecycle behavior, not safe signaling.

The missing security boundary is between opaque record validation and network
I/O. Candidate syntax alone cannot authorize a destination. An attacker who can
publish or replay a candidate set may try loopback, link-local, private, multicast,
broadcast, or privileged service targets and turn the endpoint into an SSRF or
port scanner. A public discovery service can be abused for reflection or
amplification if responses exceed authenticated requests. Plaintext host and
server-reflexive candidates reveal local and public addressing to the rendezvous
operator, logs, or unrelated lookup clients. A one-time successful path check is
also insufficient: NAT bindings and peer ownership change, so data must stop
when consent freshness fails.

## Desired Invariants

- Only the paired runtime and client can publish, fetch, decrypt, and authenticate
  candidate generations for their pair and protocol purpose.
- Rendezvous lookup keys are unlinkable across time windows where practical and
  never contain device fingerprints, route tokens, raw IP addresses, account
  names, or AI payload metadata.
- Candidate records use end to end authenticated encryption, are padded to bounded classes, expire
  quickly, carry generation and nonce, and cannot be replayed across pair,
  direction, session, or protocol version.
- The rendezvous service remains an untrusted rendezvous boundary. A received
  address is an untrusted hint. Endpoints send connectivity checks only
  under a pair-authorized transaction with strict destination classes, bounded
  ports, bounded fanout, and no arbitrary URL, hostname resolution, redirect, or
  application payload.
- Address discovery and relay allocation require authentication, quotas, request
  integrity, transaction matching, and response-size bounds that prevent useful
  scanning or amplification.
- A direct path becomes nominated only after bidirectional cryptographic checks
  bind both paired identities, both candidate generations, both path endpoints,
  and the current session attempt.
- Consent freshness continues after nomination. Missed authenticated consent
  checks close the direct path; they never cause unauthenticated downgrade.
- Relay fallback uses a separate short-lived pair-scoped capability and preserves
  the same endpoint identity and payload-encryption requirements.
- Expiry, pair removal, revocation, or higher-generation route activation stops
  publication, lookup, checks, allocations, and active paths for older state.
- Production routes never fall back to plaintext candidates, unauthenticated
  discovery, legacy signaling, or a relay that can read application frames.

## Constraints And Non-Goals

QR-first pairing, runtime ownership of model access, paired identity, P2P-first
route ordering, and blind relay fallback remain. Candidate services must not
receive prompts, responses, files, memory, model metadata, backend credentials,
or endpoint traffic secrets. This proposal does not promise anonymity against a
global observer, hide packet timing from the selected relay, solve endpoint
compromise, create an account directory, or choose a concrete networking or
cryptography library. It does not treat an overlay VPN as proof that arbitrary
candidate targets are safe.

## Before Architecture

[Before architecture](../diagrams/authenticated-rendezvous-and-candidate-protection-before.mmd)

The before view carries a validated opaque record to an injected connector seam.
No current component owns the security policy for gathering, candidate
decryption, target filtering, authenticated checks, consent, or allocation
abuse. Relay fallback exists as route-manager behavior, not as a unified
production traversal contract.

## Options

The machine option IDs are `relay-only-sealed-signaling`,
`authenticated-encrypted-ice-turn`, and `decentralized-rendezvous` in the same
reader-facing order below.

### Option 1: Relay-Only Sealed Signaling Baseline

This option deliberately ships no host or server-reflexive candidates. Each pair
uses an authenticated, write-once short-lived mailbox whose lookup key is derived
from pair secret material, purpose, direction, and time window. Records are
end-to-end sealed and contain only relay capability requests and session
coordination. Both peers connect outbound to a blind relay and establish an
identity-bound encrypted session over it.

The design sharply reduces SSRF and scanning exposure because peers do not act on
remote network targets. Mailbox writes and relay allocations remain authenticated,
fixed-size, expiry-bound, rate-limited, and non-amplifying. Candidate privacy is
strong because there are no direct candidates to reveal, although the relay sees
peer source addresses and traffic timing. Consent freshness reduces to relay
connection liveness plus application/session keepalive.

[Option 1 architecture](../diagrams/authenticated-rendezvous-and-candidate-protection-relay-only-after.mmd)

| Change | Before | After | Security consequence | Cost |
| --- | --- | --- | --- | --- |
| Signaling | Opaque unimplemented blob | Authenticated sealed mailbox | Rejects unauthorized publication and replay | Mailbox authority and key schedule |
| Candidate exposure | Unspecified | No direct candidates | Eliminates direct-candidate topology disclosure and target scanning | All remote traffic pays relay cost |
| Amplification | Unspecified | Fixed request/response classes and authenticated quotas | Bounds reflection utility | Capacity controls and abuse telemetry |
| Fallback | Development relay after P2P seam | Relay is the production baseline | Predictable availability and downgrade boundary | Relay dependence and bandwidth |

This is the safest first production route and rollback target, but it does not
meet the desired direct-path efficiency. Rollback may disable direct traversal;
it must not re-enable unsealed records or unauthenticated relay allocation.

### Option 2: Authenticated Encrypted ICE+TURN

This option implements authenticated address discovery, sealed pair-scoped
candidate exchange, direct connectivity checks, consent freshness, and bounded
TURN-style relay allocation. Candidate records use monotonically increasing
generations and per-direction nonces. The rendezvous service indexes opaque,
rotating pair keys and stores only ciphertext, expiry, size class, and abuse
metadata. It cannot read private or public candidates.

The endpoint decrypts into a strict candidate data model, never a URL or command.
Policy rejects prohibited destination classes unless a narrowly defined local
same-link mode independently proves scope. DNS names, redirects, user-info,
paths, arbitrary payloads, and unconstrained port lists are invalid. Connectivity
checks carry unpredictable transaction integrity, a pair/session binding, role,
candidate generation, and bounded response. A response nominates only the exact
source/destination tuple that passed bidirectional validation; a claimed address
cannot redirect traffic elsewhere. Check pacing, candidate caps, per-pair and
per-source quotas, and small responses bound scan and amplification value.

Relay allocation uses a distinct expiring capability bound to pair, roles,
session attempt, allocation quota, and allowed relay service. The capability
cannot authorize arbitrary third-party targets. Direct and relayed paths feed
the same identity-bound endpoint session described by the companion proposal.
Consent freshness periodically proves the peer still controls the nominated
tuple; failure closes it and invokes authenticated relay fallback.

[Option 2 architecture](../diagrams/authenticated-rendezvous-and-candidate-protection-authenticated-ice-turn-after.mmd)

| Change | Before | After | Security consequence | Cost |
| --- | --- | --- | --- | --- |
| Candidate privacy | Opaque carriage with unspecified contents | End-to-end sealed, padded generations under rotating lookup keys | Hides topology from rendezvous storage and passive readers | Key derivation, padding, and record churn |
| Target handling | Connector-defined | Typed candidates, prohibited scopes, exact tuple validation | Blocks arbitrary SSRF and narrows scan surface | Cross-platform network-policy edge cases |
| Traversal checks | None | Authenticated, paced, bounded bidirectional checks | Prevents spoofed nomination and useful amplification | Setup latency and state machine |
| Liveness | Connector-defined | Consent freshness with fail-close | Stops use after peer/path ownership is lost | Keepalive traffic and mobile wake cost |
| Fallback | Independent relay attempt | Capability-bound TURN-style allocation | Reliable fallback without weakening identity | Relay capacity and allocation operations |

Downgrade is explicit: a production route advertises one minimum traversal suite,
and failure proceeds to the sealed relay capability, never to plaintext signaling
or unauthenticated checks. Revocation invalidates rendezvous writes, fetches, new
allocations, consent renewal, and active relay bindings within a measured bound.

### Option 3: Decentralized Rendezvous

This option keeps Option 2's endpoint candidate and path rules but stores sealed
records across independently operated rendezvous nodes or a DHT-like substrate.
Peers derive blinded, epoch-specific lookup keys, publish bounded ciphertext to
multiple nodes, and require consistent fresh records or a defined quorum. No node
learns plaintext candidates or a stable pair identifier.

Distribution improves censorship and regional outage tolerance and can reduce
the metadata held by one operator. It also expands the abuse and consistency
surface. Sybil nodes can suppress or serve stale records; multi-publication
increases write amplification; revocation and deletion are eventually consistent;
and public nodes need admission tokens without gaining pair identity. Endpoints
must reject lower generation, conflicting signer identity, excess records, and
records outside narrow expiry windows regardless of node responses.

[Option 3 architecture](../diagrams/authenticated-rendezvous-and-candidate-protection-decentralized-after.mmd)

| Change | Before | After | Security consequence | Cost |
| --- | --- | --- | --- | --- |
| Availability | One unspecified record source | Multi-node sealed publication and lookup | Tolerates some outage or suppression | Consistency, bootstrap, and Sybil defenses |
| Metadata | Potentially centralized | Blinded rotating keys across operators | Reduces stable metadata concentration | More observers and traffic |
| Replay | Local opaque expiry | Signed generation plus multi-source consistency | Rejects stale and conflicting records | State retention and clock handling |
| Revocation | Local route lifecycle | Short expiry plus deny publication and node cleanup | Bounds stale availability | Not immediately globally deletable |

Relay fallback remains centrally or federatively allocatable and must not depend
on successful decentralized lookup. This option is not recommended until Option
2's single-authority security and operational budgets are measured.

## Comparison

| Dimension | Option 1: Relay-Only Sealed | Option 2: Authenticated ICE+TURN | Option 3: Decentralized Rendezvous |
| --- | --- | --- | --- |
| Security | Smallest target surface; relay observes source metadata | Strong candidate privacy, validated direct paths, bounded fallback | Same endpoint rules plus reduced single-operator metadata; larger Sybil surface |
| Performance | Predictable but all traffic relayed | Direct path when viable; checks add setup work | Additional publication/lookup latency and bandwidth |
| Memory | Bounded mailbox and relay state | Candidate generations, transactions, consent, allocations | Multi-source records, conflict and replay state |
| Reliability | Relay availability is critical | Direct plus relay; more NAT-specific failure modes | Rendezvous outage tolerance; consistency failures |
| Operability | Relay capacity and abuse response | Discovery, rendezvous, relay, revocation, NAT telemetry | Node bootstrap, admission, quorum, abuse, regional policy |
| Migration | Lowest risk production baseline | Moderate protocol and cross-platform rollout | Highest distributed-system migration |

No performance claim above is measured. Selection requires NAT-matrix success,
candidate-to-nomination latency, consent traffic, relay ratio, abuse rejection,
and battery/network cost measurements rather than an invented score.

## Recommendation

Recommend Option 2 (`authenticated-encrypted-ice-turn`), with Option 1 as a mandatory feature-gated baseline and emergency
fallback. Freeze the sealed record, authorization, and relay-capability contracts
before choosing implementation components. Defer Option 3 until centralized
rendezvous metadata or availability is a demonstrated product risk.

## Evidence Coverage And Residual Risk

| Evidence | Option 1 | Option 2 | Option 3 |
| --- | --- | --- | --- |
| `E001` planner order | Replaces P2P attempt with sealed relay | Implements P2P-first then relay | Same route order with distributed lookup |
| `E002` persisted route | Stores sealed mailbox/capability state | Stores sealed generation and expiry, not plaintext candidates | Adds multi-source replay state |
| `E003` QR envelope | Bootstraps sealed relay authorization | Bootstraps rendezvous authorization root and minimum suite | Also bootstraps node policy |
| `E004` connector/fallback | Uses relay connector only | Supplies a real bounded P2P connector and fallback | Same connector with distributed acquisition |
| `E005` opaque preparation | Preserves expiry/nonce separation | Extends into authenticated candidate state machine | Extends with node consistency |
| `E006` runtime lifecycle | Starts sealed relay pair route | Owns gathering, publication, allocation, and revocation generation | Adds multi-node lifecycle |
| `E007` authenticated router | Authorizes mailbox refresh | Authorizes pair-scoped refresh without authorizing arbitrary targets | Same under distributed records |
| `E008` transport ownership | Uses independent relay resource | Maps separate direct and relay resources to one pair lifecycle | Same, with lookup resource state |
| `E009` pairing identity | Derives pair mailbox keys | Derives pair signaling and check authorization | Derives blinded epoch lookup keys |
| `E010` lifecycle seam | Requires a relay transport adapter | Requires a nominated-path adapter | Requires the same adapter with distributed acquisition |
| `E011` QR schema | Versioned sealed baseline fields | Needs minimum traversal suite and authorization fields | Needs node/bootstrap policy fields |
| `E012` protocol schema | Adds sealed relay status/errors | Adds generations, nomination, consent, revocation, fallback errors | Adds conflict/quorum errors |
| `E013` compact fixture | Becomes sealed relay fixture | Gains real encrypted candidate vectors, not literal placeholder proof | Adds blinded lookup vectors |

Residual risks include endpoint compromise revealing local topology, traffic
analysis by networks and selected relays, denial by rendezvous or relay operators,
NAT behaviors that defeat direct traversal, mobile sleep delaying consent, shared
address false positives in abuse controls, and compromised paired keys issuing
valid scans. Sealing candidates does not hide endpoint source addresses from the
services they contact. No current evidence proves real-device, different-network,
public-service, NAT, battery, or latency behavior.

## Migration And Rollout

1. Freeze canonical sealed-record, candidate, transaction, relay-capability,
   revocation, and error encodings with strict size and count ceilings.
2. Derive a versioned pair-scoped signaling authorization root during fresh QR
   pairing or authenticated migration; do not reuse `routeToken` as record or key
   material.
3. Deploy Option 1 mailbox and blind relay in verification-only mode, then enforce
   authentication, expiry, quotas, and non-amplifying responses.
4. Add parse-only Option 2 candidate generations and reject prohibited target
   classes before any network I/O.
5. Enable authenticated checks for controlled cohorts while relay remains active;
   record nomination, failure class, fallback, and consent loss without addresses.
6. Enforce identity/path binding and consent freshness, then permit direct payload
   traffic for production-version routes.
7. Connect pair removal, route supersession, and revocation to publication denial,
   allocation denial, consent failure, and active resource closure.
8. Expand NAT/network cohorts only after abuse, battery, latency, and fallback
   thresholds pass. Disable direct traversal, not security checks, on rollback.
9. Evaluate decentralized rendezvous only after the centralized design has stable
   operational data and a concrete availability or metadata requirement.

There is no automatic downgrade: every transition either preserves the selected
production security floor or fails closed.

## Validation Plan

- Cross-language fixed vectors for record sealing, padding, lookup derivation,
  generation ordering, expiry, nonce, role, capability, and downgrade transcript.
- Parser and policy fuzzing for candidate count/size, IP families, mapped forms,
  scope IDs, ports, malformed encodings, duplicate fields, and unknown versions.
- SSRF tests proving loopback, link-local, multicast, broadcast, unspecified,
  prohibited private scope, redirects, DNS rebinding, URLs, and arbitrary payloads
  cannot produce traversal traffic.
- Scan/amplification tests measuring packets and bytes per authenticated request,
  destination fanout, pacing, quota isolation, spoofed-source behavior, and
  malformed-record cost.
- Replay tests for old QR, record, generation, nonce, transaction, nomination,
  consent response, relay capability, and revoked pair state.
- Path tests proving nomination requires exact bidirectional tuple validation and
  that peer-reflexive observations cannot redirect checks to a third party.
- Consent tests for NAT rebinding, interface change, sleep/wake, delayed packets,
  partition, and peer replacement; stale paths must close before reuse.
- Fallback tests proving every direct failure class reaches authenticated relay
  without plaintext signaling, identity downgrade, duplicate delivery, or resource
  leaks.
- Real-device NAT matrix across IPv4, IPv6, dual stack, carrier NAT, symmetric
  mappings, enterprise filtering, hotspot, and interface transitions; separately
  report direct success and relay success.
- TURN interoperability tests covering authenticated allocation, expiry,
  permission/channel state, quota enforcement, and revocation.
- Measure p50/p95/p99 setup time, relay ratio, service bytes, endpoint memory,
  battery impact, consent traffic, revocation closure, and false abuse rejection.

## Implementation Work Packages

- Canonical sealed rendezvous record and rotating pair lookup authorization.
- Typed candidate parser, network target policy, generation, replay, and expiry
  state shared by Android and macOS.
- Authenticated discovery transactions, connectivity checks, nomination, pacing,
  and consent state machine.
- Pair-scoped relay allocation capability and blind fallback integration.
- Rendezvous/relay admission quotas, response bounds, privacy-preserving metrics,
  and revocation propagation.
- Cross-platform lifecycle integration with route refresh, pair removal, resource
  generation ownership, and fail-closed downgrade handling.
- Adversarial, NAT-matrix, performance, battery, and incident validation harnesses.

These packages remain design work until the option and protocol are approved;
they do not select a concrete library.

## Open Questions

- Which candidate classes are required for the first direct-path release, and is
  any private-scope candidate acceptable outside independently verified same-link
  discovery?
- What setup-time and relay-ratio budgets justify Option 2 over the relay-only
  baseline?
- What consent interval and failure threshold are acceptable on sleeping mobile
  devices without extending stale-path ownership too far?
- Must rendezvous hide pair linkage from a single operator, or is bounded retention
  and rotating opaque lookup sufficient for the first release?
- What revocation-to-publication, allocation, and active-path closure targets are
  required?
- Which abuse limits avoid penalizing many paired users behind one shared address
  while retaining meaningful scan and amplification resistance?
