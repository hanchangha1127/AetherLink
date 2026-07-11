# Production P2P/NAT Threat Model

## Scope And Security Objective

We are modeling the reserved production path from an already QR-paired Android
client to its trusted macOS runtime across different networks. The desired
system discovers a viable direct path when possible and falls back to TURN when
necessary without allowing signaling, STUN, TURN, or an on-path party to become
an endpoint identity authority or to read AetherLink application payloads.

The active implementation boundary is limited to the opaque route envelope and
injected connector described by `E005` (Opaque P2P route envelope) and `E004`
(Injected connector seam). ICE, STUN, TURN, and the identity-bound secure session
below are proposed or reserved behavior, not current claims.

Hole punching proves reachability, not identity. Reserved namespaces remain
inactive until a selected protocol profile defines their exact authentication,
replay, privacy, and failure contracts.

## Assets

| Asset | Security property |
| --- | --- |
| Long-term paired device keys and fingerprints | Confidential private keys; authentic, rollback-resistant public identity binding |
| Pair state and route authority | Integrity, freshness, monotonic generation, and one-to-one scope |
| ICE credentials and candidate generations | Confidentiality until authorized disclosure; integrity, freshness, replay resistance, and bounded lifetime |
| Host, server-reflexive, peer-reflexive, and relayed candidates | Integrity and privacy proportional to route policy; no unauthorized correlation or probing |
| TURN credentials, allocations, permissions, and channel bindings | Least privilege, short lifetime, pair/session scope, and abuse resistance |
| Secure-session transcript and traffic keys | Mutual endpoint authentication, key confirmation, forward secrecy, context binding, and erasure |
| AetherLink payloads | End-to-end confidentiality and integrity from Android client to trusted runtime on direct and relayed paths |
| Availability and resource budgets | Bounded signaling records, checks, allocations, bandwidth, retries, and memory per authorized pair |
| Metadata and diagnostics | No secrets, raw candidate sets, stable cross-session identifiers, prompts, files, backend URLs, or model commands in logs |

## Actors And Assumptions

| Actor | Trust and capability |
| --- | --- |
| Paired Android client | Trusted endpoint while its device key and local state remain uncompromised; may be offline, mobile, or behind restrictive NAT. |
| Trusted macOS runtime | Trusted endpoint and only model/backend authority; must not accept a session solely because a route connected. |
| Rendezvous/signaling service | Availability and delivery dependency, but not an endpoint identity authority. It may be honest-but-curious, compromised, replaying, withholding, reordering, or substituting records. |
| STUN service | Returns observed transport addresses. It is not trusted to authenticate the paired peer or authorize application data. |
| TURN service | Relays packets and sees transport metadata. It is not trusted with endpoint private keys, session traffic keys, or plaintext payloads. |
| Network attacker | Can observe, inject, replay, reorder, delay, fragment, redirect, and drop traffic and can attempt amplification or off-path checks. |
| Unauthorized Internet client | Can enumerate public service surfaces and spend bounded unauthenticated work, but has no pair authority. |
| Compromised paired endpoint | Holds that endpoint's current authority. The design can limit service abuse and support revocation but cannot preserve pair confidentiality against an endpoint that legitimately receives plaintext. |
| Operator and support tooling | May access bounded operational metadata; must not gain route secrets, candidate bodies, traffic keys, or application payloads through logs. |

We assume cryptographic primitives and operating-system randomness are sound.
We do not assume signaling delivery is reliable, STUN reveals a usable path,
direct traversal always succeeds, or TURN is always reachable.

Candidate, checklist, allocation, and handshake exhaustion are explicit
denial-of-service threats rather than ordinary connection failures.

## Trust Boundaries

| Boundary | Data crossing | Required control |
| --- | --- | --- |
| QR bootstrap to paired state | Device identity, initial pair authority, optional service trust roots | Explicit user ceremony, canonical signed transcript, anti-confusion binding |
| Endpoint to signaling service | Session id, encrypted candidate envelopes, sequence/generation, expiry | TLS 1.3 service authentication, endpoint authorization, replay-safe writes, bounded records |
| Signaling storage to peer | Candidate updates and end-of-candidates | End-to-end candidate-envelope integrity/confidentiality, peer and pair binding, expiry, generation checks |
| Endpoint to STUN | Binding requests and observed addresses | Standards-conformant transaction validation, response-source checks, pacing, no endpoint-authentication inference |
| Endpoint to candidate target | Fixed-format connectivity checks to an advertised address and port | Destination-class policy, authenticated candidate provenance, no URLs or redirects, bounded ports/fanout, non-amplifying STUN-only payloads |
| Endpoint to TURN | Allocation credentials and relayed traffic | Authenticated TURN, short-lived scoped credentials, permissions, quotas, transport security where applicable |
| Nominated ICE or TURN path to secure session | Untrusted datagrams/streams and path metadata | Peer-verifiable identity-bound handshake before application readiness |
| Secure session to application protocol | Authenticated encrypted channel | Key confirmation, transcript and role binding, frame limits, replay/order policy, close on failure |
| Runtime to model backend | Prompts, responses, files, memory, backend credentials | Remains local to trusted runtime; traversal components never cross this boundary |

## Threats And Required Responses

| ID | Threat | Affected assets/boundary | Required response |
| --- | --- | --- | --- |
| `T001` | Signaling record substitution or candidate injection | Candidate integrity; signaling-to-peer | Reject envelopes not authorized by the expected paired identity, pair id, session id, role, generation, and sequence. |
| `T002` | Replay of an old candidate set, ICE restart, or TURN route | Pair state; signaling | Require expiration plus monotonic generation/restart state; exact idempotent retries may succeed, divergent reuse fails. |
| `T003` | Candidate disclosure and IP correlation | Candidate privacy; signaling/operator | Encrypt candidate envelopes end to end, minimize retained candidates, support relay-only policy, and redact logs. |
| `T004` | ICE credential theft or cross-session reuse | ICE checks; signaling | Generate unpredictable per-generation credentials, disclose only to the paired peer, expire promptly, and never reuse across restart or pair. |
| `T005` | STUN response spoofing, amplification, or parser abuse | Traversal availability | Validate transaction ids/types/integrity as applicable, pace checks, cap candidates and transactions, and treat STUN as address discovery only. |
| `T006` | TURN credential theft, open-relay use, or allocation exhaustion | TURN service and availability | Use authenticated, short-lived scoped credentials, permissions, quotas, bandwidth limits, and source-/identity-aware abuse controls. |
| `T007` | Signaling or relay service impersonation | Credentials and metadata | Authenticate service channels with an explicit trust source; no opportunistic or silent downgrade. |
| `T008` | Unknown-key share or endpoint identity substitution | Secure-session transcript | Bind both long-term identities, roles, pair state, ephemeral keys, nonces, candidate generation, and selected transport context into one verified transcript. |
| `T009` | Route success mistaken for peer authentication | Application payloads | Do not expose a ready `RuntimeProtocolChannel` until mutual identity verification and key confirmation succeed. |
| `T010` | Direct-to-relay downgrade or fallback manipulation | Metadata, cost, availability | Apply a deterministic authenticated fallback policy; record reason codes without secrets; never weaken session authentication on TURN. |
| `T011` | Consent loss, NAT rebinding, or traffic sent to a stale peer address | Network third parties; availability | Maintain consent freshness, stop promptly on failure, and require authenticated path validation before migration. |
| `T012` | Candidate/check explosion and memory or battery exhaustion | Endpoint availability | Bound candidates, foundations, checklists, trickle batches, retries, time, concurrent sessions, and allocations per authorized pair. |
| `T013` | Version or algorithm downgrade | All cryptographic boundaries | Bind offered/selected versions and algorithms into authenticated transcripts; unsupported or forbidden values fail closed. |
| `T014` | Compromised signaling/TURN service reads application data | Payload confidentiality | Keep the endpoint secure session above the nominated transport; services receive no application traffic key. |
| `T015` | Diagnostic leakage | Keys, candidates, pair identity, payloads | Structured redaction, bounded correlation ids, no raw envelope/candidate/key logging, and negative log tests. |
| `T016` | A compromised paired endpoint induces probes to loopback, link-local, private, or victim destinations | Runtime-side network reachability; candidate-target boundary | Reject loopback, unspecified, multicast, broadcast, and link-local targets; default-deny private destinations unless an explicit local-network policy and candidate provenance authorize them; forbid URLs, redirects, DNS rebinding, and arbitrary payloads; cap destination ports, fanout, pace, and bytes. |

## Fail-Closed Invariants

- A route record is unusable unless it is complete, canonical, unexpired, for
  the expected pair and endpoint roles, and in the current candidate generation.
- A pairing `routeToken` is never an ICE username fragment, ICE password,
  candidate record id, TURN credential, secure-session key, or fallback token.
- Signaling authentication and candidate-envelope authentication are separate
  checks; success at one does not waive the other.
- No candidate can cause a connectivity check until its envelope is authorized,
  parsed under explicit size/count limits, and accepted for the current session.
- Candidate authentication never bypasses destination policy. Connectivity checks
  use fixed non-amplifying STUN messages only; prohibited destination classes,
  arbitrary URLs/hostnames, redirects, DNS rebinding, and application payloads
  fail before network I/O. Private destinations require an explicit local-network
  policy and authenticated candidate provenance.
- STUN success proves only an observed path property. TURN allocation success
  proves only relay authorization. Neither authenticates the application peer.
- A nominated direct or relayed path remains untrusted until the transport-neutral
  secure session verifies both paired identities and confirms keys.
- The same endpoint identity and transcript checks apply on direct ICE and TURN;
  fallback cannot select weaker cryptography, anonymous peers, or a legacy mode.
- Candidate generation changes, ICE restarts, path migration, and reconnects
  cannot reuse stale credentials, nonces, sequence numbers, or traffic keys.
- Consent or authenticated path-validation failure stops application traffic to
  that path before trying a replacement path.
- Signaling, STUN, and TURN never receive model backend credentials, prompts,
  responses, files, memory, model lists, backend URLs, or session traffic keys.
- Every unauthenticated or pair-scoped resource has explicit count, byte, time,
  and concurrency bounds; malformed input cannot trigger unbounded fanout.
- Any ambiguity in role, identity, generation, version, candidate ownership,
  transcript, or fallback policy terminates that attempt without downgrade.

## Residual Risk And Out Of Scope

The proposed boundaries do not hide all transport metadata, prevent a TURN
operator from observing timing and volume, defeat global traffic analysis,
guarantee traversal through every NAT/firewall, or protect plaintext from a
compromised paired endpoint. Account recovery, multi-device group trust, DHT or
public peer discovery, anonymous connectivity, censorship resistance, and
post-compromise pair recovery are separate designs.

No-device review cannot validate packet-level interoperability, radio changes,
background suspension, battery cost, NAT mapping lifetimes, IPv6-only/NAT64,
carrier-NAT fairness, public-service abuse controls, real consent loss, or live
fallback. Those remain release-blocking validation classes after selection and
implementation.
