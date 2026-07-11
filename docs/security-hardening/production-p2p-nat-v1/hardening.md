# Security Hardening Review: Production P2P/NAT Connectivity

## Evidence Basis

I inspected the current Android P2P route preparation, route planner, pairing
parser and store, connection-manager seam, macOS QR and route-refresh boundaries,
shared schemas, cross-platform fixture, roadmap boundary, and the uncommitted
macOS connection-manager seam. The registry in [context.md](context.md) binds
these observations to 13 manifest-verified artifacts. Git HEAD is
`1f839e44b261f7fdc86009bd6389777eda0f65e5`, but source drift is present, so the
manifest rather than the commit alone identifies the reviewed bytes.

The strongest current property is disciplined opacity. `E005` (Opaque P2P route
envelope), `E001` (Same-authority P2P-first route planning), and `E002` (Trusted
P2P route persistence boundary) keep route records complete, bounded, fresh,
versioned, and separate from the pairing route token. `E004` (Injected P2P
connector and fallback seam)
then hands a prepared route to an optional connector. This is useful scaffolding,
but it does not establish candidate authenticity, ICE/STUN/TURN behavior,
signaling confidentiality, endpoint key confirmation, or a production data
transport. The threat model and standards map therefore label those properties
reserved rather than active.

This is a selection-gated design portfolio, not remediation evidence. The
recommendations below do not select an option or authorize source changes. No `implementation/`
directory should exist until the user selects an option and asks for an
implementation handoff. No production design has been selected, and the
recommended protocol behavior is not implemented.

## Constraints

- Preserve `Android client -> trusted macOS runtime -> Ollama/LM Studio`; no P2P,
  rendezvous, STUN, TURN, or relay component becomes a model backend.
- Preserve QR-pinned one-to-one device trust and keep pairing route tokens
  separate from candidate, ICE, TURN, and session-key material.
- Prefer direct connectivity when policy permits, but support deterministic TURN
  fallback without changing endpoint authentication or payload protection.
- Keep signaling and relay infrastructure blind to AetherLink application
  payloads and backend credentials; minimize candidate and address metadata.
- Fail closed on identity, role, generation, expiry, replay, transcript, version,
  service trust, consent, or fallback ambiguity.
- Keep the design transport-neutral until the secure-session contract is frozen.
  A QUIC spike is contingent and must not make QUIC a prerequisite.
- Keep `route.refresh` as the only active traversal-related protocol namespace
  until a selected profile defines and reviews additional message families.
- Do not select a concrete ICE, TURN, TLS, HPKE, or QUIC library in this phase.
- Use a balanced security, reliability, latency, battery, and operability profile.
  No measured performance or capacity budget was supplied.
- Treat [RFC 8445](https://www.rfc-editor.org/rfc/rfc8445.html),
  [RFC 8489](https://www.rfc-editor.org/rfc/rfc8489.html),
  [RFC 8656](https://www.rfc-editor.org/rfc/rfc8656.html), and the complete
  [standards map](standards.md) as design inputs, not current compliance claims.
- Preserve the explicit no-device boundary: this portfolio proves no physical device
  QR scan,
  public signaling/STUN/TURN, real NAT traversal, different-network connection,
  mobile lifecycle, performance, battery, or production interoperability.

## Opportunity Portfolio

| Opportunity | Evidence | Options | Recommendation | Proposal |
| --- | --- | --- | --- | --- |
| `authenticated-rendezvous-and-candidate-protection` | Opaque route preparation and connector gap (`E001`, `E003`-`E005`, `E007`, `E011`-`E013`) | 1. relay-only sealed signaling baseline; 2. authenticated encrypted ICE signaling with TURN fallback; 3. decentralized rendezvous | Recommend `authenticated-encrypted-ice-turn`; **not selected** | [Authenticate rendezvous and protect candidate exchange](proposals/authenticated-rendezvous-and-candidate-protection.md) |
| `identity-bound-traversal-and-relay-fallback` | Pinned pair identity and common transport seams lack one nominated-path transcript (`E001`, `E004`, `E006`-`E010`, `E012`) | 1. transport-neutral secure session over nominated path; 2. ICE bootstrap plus QUIC session spike; 3. relay-first session then direct promotion | Recommend `transport-neutral-identity-session`, with the QUIC option contingent; **not selected** | [Bind identity across traversal and relay fallback](proposals/identity-bound-traversal-and-relay-fallback.md) |

**Opportunity 1: Authenticated rendezvous and candidate protection**

Option 1 deliberately starts production with relay-only sealed signaling. The
paired endpoints use an authenticated short-lived mailbox and a blind relay,
without publishing host or server-reflexive candidates. This is the strongest
privacy and rollout baseline because it removes direct candidate targeting and
ICE complexity from the first release while still requiring endpoint identity
and payload protection. It costs relay bandwidth and latency, makes relay
availability part of every remote connection, and does not meet the product's
P2P-first direction by itself.

Option 2 introduces authenticated encrypted signaling, endpoint-sealed and
authorized candidate generations, standards-conformant ICE/STUN traversal, and
authenticated TURN fallback. Candidate updates are bound to pair id, endpoint
role, session id, generation, sequence, expiration, and protocol version before
they can schedule checks. Signaling service authentication uses TLS 1.3 with an
explicit trust source, while end-to-end envelope protection keeps candidate
contents from becoming service authority. TURN uses short-lived scoped
credentials, permissions, refresh, quotas, and deterministic fallback. This
option has moderate implementation and operational cost, but it owns the missing
production boundary directly and meets the P2P-first product direction.

Option 3 distributes sealed rendezvous records across multiple nodes and uses
privacy-preserving lookup identifiers. Its strongest case is availability and
reduced metadata concentration after the endpoint envelope and traversal policy
are already sound. It adds lookup consistency, replay/tombstone semantics,
Sybil/poisoning resistance, multi-operator abuse handling, and substantially
harder incident response. Decentralization does not replace authenticated ICE,
TURN fallback, or the endpoint secure session, so it should not be a prerequisite
for the first production traversal path.

| Dimension | Option 1: Relay-only baseline | Option 2: Authenticated ICE + TURN | Option 3: Decentralized rendezvous |
| --- | --- | --- | --- |
| Security | Minimizes address exposure and direct-target abuse; relay metadata remains | Authenticates services/candidate authority and bounds ICE/TURN abuse | Distributes metadata concentration but adds lookup poisoning/Sybil surface |
| Performance | Relay latency and bandwidth on every remote session | Adds gathering/checks but can select a direct path | Adds multi-node publish/lookup work before the same traversal |
| Memory/battery | Low endpoint traversal state; sustained relay transport | Candidate/checklist state and paced radio/network work require caps | Similar endpoint state plus distributed client lookup state |
| Reliability | Simple endpoint policy, central relay dependency | Direct path with TURN fallback and new service dependencies | More rendezvous replicas, harder consistency and partition behavior |
| Operability | Signaling and relay capacity for every session | Signaling, STUN/TURN credentials, quotas, telemetry, and incident response | Multi-operator abuse, quorum, tombstone, and incident coordination |
| Migration/rollback | Safe initial production profile and emergency fallback | Versioned shadow parsing, opt-in route class, then production gate | Can fall back to centralized sealed rendezvous without weakening endpoint envelopes |
| Evidence basis | Source-derived | Standards-derived and hypothetical; not measured | Standards-derived and hypothetical; not measured |

**Opportunity 2: Identity-bound traversal and relay fallback**

Option 1 defines one secure-session contract above the nominated transport. Both
peers verify a canonical transcript binding their long-term paired identities,
roles, pair state, ephemeral keys, nonces, candidate generation, selected
protocol/version, and transport context before creating a ready
`RuntimeProtocolChannel`. The same state machine and key confirmation run over a
direct ICE pair or TURN relay. This preserves endpoint payload confidentiality
when signaling or TURN is compromised and makes fallback a routing decision,
not a security downgrade. The main costs are a reviewed cross-platform handshake,
canonical encoding, resumption/rekey decisions, fixed vectors, and explicit
ownership between traversal and protocol-channel layers.

Option 2 preserves that contract and runs a bounded QUIC spike under it. QUIC may
offer useful path validation, migration, stream multiplexing, and standardized
TLS integration. It may also conflict with NAT traversal assumptions, duplicate
reliability already present in the application protocol, increase platform and
library surface, or perform poorly under background/mobile conditions. The spike
is justified only after Option 1 defines transport inputs and outputs, and only
with predeclared success criteria against a simpler datagram/stream carrier. A
failed spike must leave the secure-session and TURN fallback design intact.

Option 3 starts the identity-bound session on relay for predictable time to first
connection, then performs direct checks in the background and atomically promotes
the live session after both peers authorize the new path. This can improve tail
latency under difficult NATs and avoid making the user wait for direct checks.
Its promotion state machine is the most delicate option: packet epochs, duplicate
delivery, consent, rollback, relay retirement, and simultaneous promotion must
all remain coherent. It becomes preferable only if measured connection latency
justifies that complexity and relay cost is acceptable during overlap.

| Dimension | Option 1: Transport-neutral session | Option 2: QUIC spike | Option 3: Relay-first promotion |
| --- | --- | --- | --- |
| Security | One peer-verifiable readiness gate across direct and TURN | Same invariant if QUIC binding is correct; adds downgrade/exporter-binding review | Same invariant with a larger promotion and cross-path replay surface |
| Performance | One handshake on every selected path; resumption can follow | Potential handshake/migration benefits with unmeasured overhead | Fast relay start, temporary relay cost, possible direct-path gain |
| Memory/battery | Bounded shared state plus carrier state | Adds QUIC connection, flow-control, and migration state during spike | Holds relay and direct checking state concurrently during promotion |
| Reliability | Uniform errors and fallback; handshake failure is fail closed | Could improve migration; adds UDP blocking and implementation failure modes | Predictable start, more complex overlap and rollback state |
| Operability | Shared reason taxonomy and transcript-safe diagnostics | Adds QUIC metrics, versions, key-log policy, and packet expertise | Adds promotion, overlap, duplicate, and relay-retirement telemetry |
| Migration/rollback | Verification-only state machine, vectors, then gated readiness | Non-production profile removable independently | Feature-gated promotion can fall back to relay without weakening session identity |
| Evidence basis | Source-derived inference | Source- and standards-derived; not measured | Hypothetical/analogous; not measured |

Across both opportunities, tactical checks in `E001`-`E005`, `E007`, and
`E011`-`E013` remain necessary during and after migration. The new architecture should
consume those bounds rather than reinterpret opaque legacy material as ICE.

## Recommendation Summary

I recommend Option 2 for the first opportunity and Option 1 for the second under
the current constraints, while keeping both recommendations explicitly
unselected. First, we should design
authenticated encrypted ICE signaling with standards-conformant STUN checks and
TURN fallback. Service TLS, endpoint authorization, generation-scoped replay
state, candidate limits, consent freshness, short-lived TURN credentials, and
privacy-aware candidate policy belong to one reviewed traversal boundary. If
signaling operators must not see candidate addresses, the candidate envelope
should additionally adopt an end-to-end construction such as a selected RFC 9180
profile after its key and replay model is reviewed.

Second, we should make a transport-neutral identity-bound secure session the only
gate to application readiness. Direct ICE and TURN carry the same peer-verified
session; neither signaling delivery, a successful STUN check, a TURN allocation,
nor a connected socket authenticates the paired peer. This gives us one place to
enforce the fail-closed invariants in [threat-model.md](threat-model.md) and keeps
future transports from silently weakening fallback.

The QUIC direction should remain a contingent Option 2 spike. It becomes
attractive if measured mobility, multiplexing, loss recovery, or path migration
results beat a simpler carrier without reducing traversal success or battery
life. It should not delay ICE/TURN signaling design, select a library, or define
the endpoint trust model. Conversely, relay-only candidate privacy could move
earlier if threat-model review concludes that exposing host or reflexive
addresses to signaling is unacceptable.

No recommendation closes a security gap until the selected protocol is
implemented and revalidated on real networks and devices.

## Next Decisions

Review or refine the recommended protocol profiles before a separate explicit
selection authorizes implementation.

- **Selection gate:** explicitly select, refine, combine, or reject the options
  for each opportunity. A recommendation is not selection.
- Choose signaling ownership and endpoint authorization semantics, including
  pair/session ids, roles, generations, sequence/idempotency, retention, deletion,
  service trust roots, rotation, and outage behavior.
- Choose candidate privacy modes and whether end-to-end candidate encryption is
  mandatory, optional, or replaced by relay-only operation for sensitive users.
- Define the ICE profile: roles, candidate types/caps/priorities, trickle policy,
  restart semantics, pacing, consent, IPv4/IPv6, mobility, and failure reasons.
- Define TURN credential issuance, scope, lifetime, permissions, quotas,
  transport security, regions, abuse controls, capacity targets, and outage
  fallback. Do not treat the current development relay as TURN compliance.
- Freeze the transport-neutral secure-session inputs, canonical transcript,
  algorithms, role binding, key confirmation, resumption/rekey, channel API,
  error taxonomy, and downgrade rules before evaluating a transport library.
- Decide whether to authorize a time-boxed QUIC spike and set pass/fail criteria
  for traversal success, cold/resumed latency, migration, memory, battery,
  interoperability, observability, and rollback.
- Set measurable release budgets and a real-device/public-network matrix covering
  restrictive NAT, carrier NAT, VPN, IPv4, IPv6, NAT64, Wi-Fi/cellular changes,
  suspend/resume, consent loss, TURN outage, signaling replay, and service
  compromise simulations.
- After selection only, create an implementation handoff with phased work,
  acceptance criteria, rollback, fixed cross-platform vectors, negative tests,
  packet-level review, and no-downgrade migration. Do not create
  `implementation/` or select a concrete library before that gate.
