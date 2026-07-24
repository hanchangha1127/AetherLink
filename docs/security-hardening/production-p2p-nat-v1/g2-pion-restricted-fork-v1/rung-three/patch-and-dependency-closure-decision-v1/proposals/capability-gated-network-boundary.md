# Security Hardening Proposal: Capability-Gated Network Boundary

## Decision

We need to decide where a future restricted Pion fork would own network
authority and the transition from an untrusted ICE path to an
AetherLink-authenticated application path. This proposal presents exactly two
choices. Option 1 retains the current call structure and places guards at every
known sink. Option 2 changes the fork API so one typed state machine owns
admission, capability consumption, promotion, and revocation.

This is a preparation-only design decision. Neither option is selected,
implemented, or verified here, and this proposal closes none of the findings.

## Executive Recommendation

**Option 1: Distributed sink guards** is the compatibility baseline. We would
add checks immediately before the current ingress mutations, resolver calls,
dials, listens, writes, TURN handshakes, and application delivery paths. Its
strongest case is a small, reviewable first patch that preserves most upstream
types and call sequences.

**Option 2: Typed capability state machine** is the structural alternative. We
would make an immutable restricted profile and an admission/promotion owner
prerequisites for every privileged transition. The owner would issue
generation- and tuple-bound one-use capabilities, consume them at the exact
side-effect boundary, and revoke them when any binding changes.

Under the current requirement for exact bidirectional policy and atomic
pre-auth promotion, I conditionally recommend Option 2. It becomes preferable
only if we accept a fork-level API and state-model change and can later validate
every source path, race, and dependency boundary. Option 1 is reasonable as a
time-bounded migration layer when compatibility or review capacity dominates,
but it should not be treated as equivalent structural closure.

## Evidence

I inspected the retained Pion ICE v4.3.0 source archive read-only around the
recorded sinks. The canonical finding set and dispositions come from the
[semantic classifications](../../semantic-source-review-classifications-v1.json);
the execution and non-closure state comes from the
[semantic result](../../semantic-source-review-result-v1.json). Source
locations below are relative to the retained archive prefix
`github.com/pion/ice/v4@v4.3.0/`.

| Evidence | Finding | Exact referenced source locations |
| --- | --- | --- |
| `G2SR1-F-8a09ee9cfc2ec2968e9c` | Binding indication can influence liveness before integrity admission | `agent.go:901-940`, `agent.go:1704-1732` (primary sink `agent.go:1731`), `candidate_base.go:537-560` |
| `G2SR1-F-2eef005a63ea93252f5d` | Partial ingress defenses exist | `candidate_base.go:256-262`, `candidate_base.go:264-294`, `candidate_base.go:296-308`, `candidate_base.go:329-380` (recorded primary sink `candidate_base.go:256`) |
| `G2SR1-F-bfc6cef606dab975ede3` | Partial defensive controls already exist | `agent.go:527-530`, `agent.go:1742-1780`, `candidate_base.go:256-262`, `candidate_base.go:264-293`, `candidate_base.go:329-379`, `candidate_base.go:401-428`, `selection.go:159-209`, `selection.go:386-438` (primary sink `candidate_base.go:283`) |
| `G2SR1-F-263f18372976e5bfaa73` | Exact one-attempt egress capability is absent | `active_tcp.go:25-101`, `active_tcp.go:53`, `agent.go:1051`, `candidate_base.go:431-444`, `candidate_base.go:432` (primary sink), `gather.go:1030-1166`, `gather.go:1046`, `gather.go:1057`, `internal/stun/stun.go:38`, `net.go:130-179` |
| `G2SR1-F-b077f40a5a605032af05` | Pre-auth ingress reaches the application path | `agent.go:1704-1733`, `agent.go:1837-1848`, `candidate_base.go:256-262`, `candidate_base.go:264-294`, `candidate_base.go:296-308`, `candidate_base.go:329-379`, `candidate_base.go:329-380` (primary sink `candidate_base.go:367`), `candidatepair.go:142-150`, `transport.go:112-155`, `transport.go:184-224`, `transport_test.go:635` |
| `G2SR1-F-4189417f18abce71d56a` | Nonprofile network paths remain reachable | `agent.go:442-461` (primary sink `agent.go:456`), `agent.go:1260-1305`, `agent_config.go:61-63`, `agent_options.go:579-628`, `agent_options.go:668-681`, `agent_test.go:3820`, `gather.go:36-41`, `networktype.go:21-27` |
| `G2SR1-F-29bea0297021e485b7b0` | Required one-use mechanism is unproven | No source location or primary sink is recorded; this is the semantic missing-mechanism gap created after no lexical or equivalent one-use mechanism was proven |
| `G2SR1-F-9b119ebd5dad38048abc` | Atomic one-use promotion is absent | `agent.go:768-789` (primary sink `agent.go:768`) |
| `G2SR1-F-9650aac47015cf5758c9` | Application write lacks atomic pre-auth promotion | `candidatepair.go:142-150`, `transport.go:125-155` (primary sink `transport.go:149`), `transport.go:184-224` |
| `G2SR1-F-7e744b8ee19e7de9b7c3` | Ambient resolution lacks provenance-bound admission | `agent.go:486-487`, `agent.go:486-507`, `gather.go:850-895`, `gather.go:1030-1152`, `gather.go:1074` (primary sink), `gather.go:1093`, `gather.go:1135`, `net.go:130-179` |
| `G2SR1-F-7d678ddf77ac89e04ae4` | TURN service identity is insufficiently constrained | `agent_config.go:194-196` (primary sink `agent_config.go:196`), `gather.go:1092-1166`, `gather.go:1107-1109`, `gather.go:1149-1151` |

The observed facts are narrower than the proposed design. Binding success and
request handlers perform useful integrity and source checks, fixed receive
buffers and the bounded application buffer already exist, and socket abort
behavior is present. We must preserve those controls. At the same time,
binding indications can still reach liveness mutation, non-STUN bytes can
reach the application buffer, candidate writes call the underlying packet
connection directly, the agent can create an ambient network implementation,
and resolver, mDNS, TCP, mux, proxy, and TLS-verification choices remain
distributed through configuration and gather paths.

From those facts, we infer that the recurring condition is dispersed ownership:
the final operation does not require a value that proves policy was evaluated
against the same generation, source tuple, purpose, service identity, and
session state. That inference motivates the two options below. The typed
capabilities and state machine are proposed behavior, not observations about
the current archive.

## Current Design And Failure Mode

An untrusted peer or configured service can influence candidate receive loops,
address resolution, pair selection, TURN setup, and application I/O. The
current agent owns the mechanics, while AetherLink's restricted policy is
expressed through several configuration values and caller expectations.
Useful checks therefore occur at different depths and at different times.

This arrangement creates two related failure modes. First, a new or overlooked
call path can reach a privileged sink without the complete policy tuple.
Second, a check performed earlier can become stale after re-resolution,
generation change, nomination change, consent loss, or close. Adding more
boolean checks can reduce the known exposure, but it does not by itself make a
capability single-use or make promotion atomic with respect to application
delivery.

The TURN path illustrates why the distinction matters. Verifying a transport
service is not the same as authenticating the AetherLink endpoint, and ICE
nomination is not application-path promotion. We need both boundaries to be
explicit so that a successful TURN handshake or nominated pair cannot silently
grant application authority.

## Desired Invariants

- Every resolve, socket create, bind, connect, TURN handshake, credential
  write, connectivity check, consent message, and application write consumes
  an unexpired one-use capability bound to the exact session, generation,
  purpose, transport, interface, resolution provenance, and local/remote tuple.
- A bounded read and parse occur before admission; no unadmitted packet changes
  liveness, candidate state, events, or application-visible bytes.
- Nomination creates at most a bounded pre-auth raw-path capability. Only exact
  transcript and both endpoint key confirmations may atomically consume it and
  issue an application-record capability for the same path and generation.
- Resolution results are caller-supplied, provenance-bound, size/count limited,
  and revalidated against the restricted address policy before use.
- TURN credentials are not transmitted before exact service-name, trust-set,
  optional pin, ALPN, expiry, and handshake-policy checks pass.
- mDNS, ICE-TCP, proxy, mux, aggressive/renomination, redirects, wildcard
  authority, and other nonprofile paths are unrepresentable or fail closed.
- Re-resolution, tuple or generation change, consent loss, verification
  failure, expiry, and close revoke pre-auth and application capabilities
  before further mutation or I/O.
- Existing fixed-buffer, STUN-integrity, source-matching, and socket-abort
  controls remain in force throughout migration.

## Constraints And Non-Goals

This is a balanced design review for a personal project. Repository-owner
authentication, external signatures for this decision, and user action are not
required. Runtime endpoint and TURN-service authentication remain product
security invariants; this document does not perform or replace them.

The retained archive stays read-only. This proposal authorizes no source or
dependency change, extraction, compiler or test execution, network or socket
operation, device action, Git operation, deployment, or credential use. We
have no measured latency, memory, battery, NAT, or interoperability budget, so
all resource effects remain source-derived or hypothetical.

The proposal does not choose the reliable carrier or fragmentation/reassembly
format, authenticate an endpoint, review dependency source, or prove source
closure. Those remain separate blockers under the
[restricted fork profile](../../../restricted-fork-profile.md).

## Before Architecture

The [before Mermaid source](../diagrams/capability-gated-network-boundary-before.mmd)
shows the shared condition at the trust boundary: ingress, resolution, network
I/O, TURN identity, and application path selection have several owners, while
the restricted policy reaches the agent mainly by convention and configuration.

The important edge is not simply “peer to agent.” It is the absence of one
required authority value on every edge that mutates state or performs I/O.
Both options retain the same Pion responsibilities; they differ in whether
policy remains distributed or becomes part of the type and state model.

## Options

### Option 1: Distributed Sink Guards

Option 1 keeps the present agent, candidate, gather, selection, and transport
shapes. We would place a local guard immediately before each recorded sink and
reject nonprofile configuration during construction. The resolver would be
wrapped with bounded inputs and address admission; TURN setup would reject
verification bypass and validate exact service inputs; ingress paths would
check message size, source, generation, and current session state before
liveness or buffer mutation.

The strongest case for this option is migration control. A focused patch can
preserve most upstream interfaces, keep the current fast path recognizable,
and attach a regression test to each known source location. Tactical fixes are
also needed regardless of the final architecture, so these guards can protect
the transition if their lifetime is explicit.

What gives me pause is that the security proof remains an inventory proof.
The egress guard at `candidateBase.writeTo` does not automatically cover a new
direct dial or listen; an ingress check near the packet buffer does not make
selection and transport promotion one atomic transition. Re-resolution or
concurrent close can also invalidate data between separate checks. This option
therefore narrows known paths but retains substantial recurrence and race risk.

The comparable pair is the shared
[before diagram](../diagrams/capability-gated-network-boundary-before.mmd) and
the [Option 1 after diagram](../diagrams/capability-gated-network-boundary-distributed-sink-guards-after.mmd).

| Change | Before | After | Security consequence | Cost |
| --- | --- | --- | --- | --- |
| Ingress checks | Integrity, source, liveness, and application checks occur at different functions | Local admission checks are added before each known mutation and delivery sink | Known pre-auth mutation paths can fail earlier, but ownership remains distributed | Repeated checks and a continuing path inventory |
| Egress checks | Resolver, dial, listen, handshake, and write calls use ordinary network objects | Each known sink calls a shared guard with the current policy tuple | Known side effects require policy approval | New sinks can omit the guard |
| Profile closure | Defaults and public options leave nonprofile paths reachable | Construction rejects forbidden modes and options | Accidental enablement is reduced | Compatibility behavior changes at construction |
| TURN identity | Service identity can be weakened by configuration | Local TURN setup validates the declared service inputs and forbids bypass | Credential exposure through known setup paths narrows | Identity logic remains coupled to each transport branch |
| Promotion | Pair selection and transport write use ordinary state checks | Selection and write sites add pre-auth and promoted-state checks | Premature application I/O is reduced | Separate checks do not prove atomic one-use consumption |
| Revocation | State changes are represented across agent fields | Each guarded sink rechecks expiry, generation, tuple, and close state | Stale use becomes less likely | Race analysis remains spread across callers |

The delta is attractive when the immediate goal is a bounded tactical patch.
It is less attractive as the terminal design because the number of places that
must agree remains the core source of drift. Rollback would be a focused return
to the prior calls, but rollback would also restore the documented exposure and
could not be treated as a safe production state.

### Option 2: Typed Capability State Machine

Option 2 changes the ownership boundary. Agent construction would require an
immutable restricted profile and capability-typed resolver/network interfaces.
A single admission and promotion owner would represent at least unadmitted,
pre-auth admitted, promoted, revoked, and closed states. Privileged operations
would accept only the capability type valid for that transition rather than a
collection of independently checked booleans.

Nomination would issue one bounded pre-auth capability tied to the exact
session, generation, transport, local/remote tuple, path receipt, candidate
authority, and expiry. Secure-session confirmation could consume its declared
datagram and byte budget, but application records could not. Exact transcript,
role, path, generation, and both key-confirmation matches would perform one
atomic consume-and-promote operation. Any binding change would revoke the old
epoch before a successor could be used.

The same model would carry outbound authority. Resolver results would produce
typed admitted endpoints rather than ambient addresses, and an egress
capability would be consumed at the final dial, listen, handshake, credential
write, or packet-write boundary. TURN service identity would be verified before
credentials, while endpoint promotion would remain a separate later
transition. This separation is the strongest security argument for Option 2:
service reachability, ICE nomination, and application trust cannot be confused
because they produce different types.

The additional state owner is also a new trusted component. It can deadlock,
leak a capability, or revoke too late if its concurrency contract is weak.
Capability values add bounded metadata and atomic transitions to hot paths; no
measurement yet shows whether that cost is acceptable. Migration would touch
agent construction, candidate ingress, gather/network adapters, selection,
transport, TURN configuration, close, and tests. A compatibility adapter could
temporarily translate old calls, but it must not mint ambient authority.

The comparable pair is the shared
[before diagram](../diagrams/capability-gated-network-boundary-before.mmd) and
the [Option 2 after diagram](../diagrams/capability-gated-network-boundary-typed-capability-state-machine-after.mmd).

| Change | Before | After | Security consequence | Cost |
| --- | --- | --- | --- | --- |
| Policy ownership | Policy arrives through configuration and caller convention | One immutable restricted profile is mandatory at construction | Forbidden modes can become unrepresentable | Fork API break and profile-versioning work |
| Ingress authority | Parsed packets can reach several state and payload paths | One admission owner emits generation-bound admitted events | Mutation and delivery share one source/generation decision | Central concurrency and parser-boundary design |
| Egress authority | Ordinary address and network objects reach sinks | Typed resolver results and one-use I/O capabilities are required by sinks | Ambient network authority is removed from reviewed paths | Adapter work across gather, candidate, and TURN code |
| Promotion | Nomination and application I/O are linked by mutable pair state | Atomic consume-and-promote issues a path- and epoch-bound application capability | Pre-auth traffic cannot become application authority by nomination alone | New state machine, expiry, and race handling |
| TURN identity | Transport authentication and endpoint use can be conflated | Exact service identity precedes credentials; endpoint promotion stays separate | Service compromise or misconfiguration does not itself authenticate the peer | Signed configuration and trust-input integration |
| Revocation | Each caller observes mutable state independently | One owner revokes capabilities on every binding change before further use | Stale-generation and changed-tuple use narrows structurally | The owner becomes availability-critical |

This option changes more code because it changes what the code is allowed to
express. That is also why it better matches the desired invariants. A rollback
would require retaining an audited Option 1 adapter or reverting the fork patch
before rollout; silently falling back to ordinary network objects would defeat
the design.

## Comparison

No performance or resource result below is measured. “Source-derived” means
the mechanism follows from the inspected call structure; “hypothetical” means
later implementation and benchmarks could change the conclusion.

| Dimension | Option 1: Distributed sink guards | Option 2: Typed capability state machine | Validation needed |
| --- | --- | --- | --- |
| Security | **Improves**, medium confidence, source-derived: known sinks gain checks, but bypass and check/use races remain | **Improves**, medium confidence, source-derived: authority, promotion, and revocation gain one owner, but its correctness and dependency behavior are unproven | Enumerate every read, resolve, create, bind, connect, handshake, credential, and write edge; mutate every binding input |
| Performance | **Unknown**, low confidence, hypothetical: repeated policy evaluation may add checks at several hot sinks | **Unknown**, low confidence, hypothetical: capability validation and atomic transitions add bounded hot-path work but can avoid repeated policy reconstruction | Compare packet rate, latency distribution, CPU, and allocations for direct and relay paths against the retained baseline |
| Memory | **Regresses**, low confidence, hypothetical: guards retain per-call policy context and test inventory metadata | **Regresses**, low confidence, hypothetical: capability records, epochs, and revocation state are new bounded objects | Measure peak RSS and live objects at declared session, candidate, path, and generation ceilings |
| Reliability | **Improves**, low confidence, source-derived: known invalid inputs fail earlier, but inconsistent guard failure modes remain | **Unknown**, low confidence, hypothetical: atomic revocation can improve recovery, while one state owner becomes availability-critical | Inject resolver, TURN, consent, path-change, expiry, and close faults under concurrency |
| Operability | **Regresses**, medium confidence, source-derived: audits and diagnostics must correlate many guard sites | **Improves**, low confidence, hypothetical: one owner can emit bounded reason counters, but profile/capability state needs new tooling | Review whether bounded state/reason events support incident diagnosis without secret or identity fields |
| Migration | **Neutral**, medium confidence, source-derived: current APIs mostly remain, with many local edits and easy focused rollback | **Regresses**, high confidence, source-derived: construction, network adapters, selection, transport, and tests change together | Compile and compatibility matrices only after later authority; rehearse adapter removal and rollback against a refreshed source identity |

Option 1 wins primarily on near-term compatibility and reversibility. Option 2
wins on future control ownership and resistance to drift. The decision should
therefore turn on whether the project is willing to maintain a restricted fork
API, not on an assumed performance advantage that has not been measured.

## Recommendation

I recommend Option 2 conditionally because the finding set crosses both I/O
directions, service identity, and a security state transition. Local guards can
patch known lines, but they cannot make one-use consumption and exact promotion
unrepresentable outside one owner.

I would change that recommendation if source-path enumeration shows the fork
API change is materially larger than the personal project can maintain, or if
bounded benchmarks show the centralized state owner violates an agreed packet
latency or allocation budget. In that case, Option 1 should be selected only
with an explicit migration deadline, complete sink inventory, and closure
flags left false for the structural and dependency gaps.

No recommendation in this document is a selection. A later decision must name
the chosen option and refreshed source identity before any implementation work.

## Evidence Coverage And Residual Risk

The effects below describe design intent if an option is selected, implemented,
and revalidated. They do not describe the current repository state.

| Evidence | Option 1 effect | Option 2 effect | Tactical protection still required |
| --- | --- | --- | --- |
| `G2SR1-F-8a09ee9cfc2ec2968e9c` — Binding indication liveness before integrity | **Addresses** the known mutation with a local admission check; recurrence remains | **Addresses** by requiring an admitted event before liveness mutation | Reject unauthenticated/unbound indications during migration |
| `G2SR1-F-2eef005a63ea93252f5d` — Partial ingress defenses | **Mitigates** regression risk by preserving the fixed buffers and STUN checks | **Mitigates** regression risk by preserving them below the admission owner | Regression coverage for buffer and STUN behavior |
| `G2SR1-F-bfc6cef606dab975ede3` — Partial defensive controls | **Mitigates** regression risk by preserving existing controls at their sites | **Mitigates** regression risk by consolidating ownership without removing them | Preserve source matching, integrity, bounded buffer, and abort behavior |
| `G2SR1-F-263f18372976e5bfaa73` — Exact egress capability absent | **Addresses** known sinks, but cannot prevent a new unguarded sink | **Addresses** by making the capability a sink argument | Guard all inventoried egress until typed adapters replace them |
| `G2SR1-F-b077f40a5a605032af05` — Pre-auth ingress reaches application | **Addresses** known buffer and transport paths with local checks | **Addresses** by requiring promoted-epoch authority for application delivery | Drop pre-auth application bytes at every current entry |
| `G2SR1-F-4189417f18abce71d56a` — Nonprofile paths reachable | **Addresses** known constructors and options; public-surface drift remains | **Addresses** by excluding forbidden modes from the restricted profile types | Construction-time denylist and reachability tests |
| `G2SR1-F-29bea0297021e485b7b0` — One-use mechanism unproven | **Mitigates** the gap, but distributed checks do not establish atomic one-use consumption | **Addresses** in design through consumable capability types | Keep the gap unresolved until race and replay tests pass |
| `G2SR1-F-9b119ebd5dad38048abc` — Atomic promotion absent | **Addresses** inventoried selection sites with promotion checks | **Addresses** through one consume-and-promote transition | Prevent application attachment on nomination alone |
| `G2SR1-F-9650aac47015cf5758c9` — Application write lacks promotion | **Addresses** known writes with state checks | **Addresses** by requiring an application capability at `Write` and `WriteToPair` equivalents | Fail closed on every current transport write |
| `G2SR1-F-7e744b8ee19e7de9b7c3` — Ambient resolution lacks provenance | **Mitigates** root callsites with a wrapper | **Mitigates** by removing root ambient resolution; dependency behavior remains unknown | Reject unbound answers and complete dependency review |
| `G2SR1-F-7d678ddf77ac89e04ae4` — TURN identity insufficient | **Mitigates** configured root TLS/DTLS paths | **Mitigates** with exact typed identity before credentials; dependency behavior remains unknown | Prohibit verification bypass and pre-verification credentials |

Residual risks remain material:

- `G2SR1-F-65bdab86ddd0720af770` — Dependency source closure is missing — has
  no source location or sink and remains unaffected by both options. Reviewed
  root adapters cannot prove that transitive resolver, TLS, TURN, or socket
  behavior obeys the same boundary.
- The capability owner itself can contain race, replay, ABA, expiry, or
  revocation defects.
- Exact service authentication does not authenticate the AetherLink endpoint;
  exact secure-session confirmation remains required.
- The reliable carrier and bounded fragmentation/reassembly contract remains
  undecided, so promoted Pion datagrams cannot yet be attached to the Runtime
  channel.
- New source bytes, dependency graph changes, or upstream merges invalidate
  the path inventory and require a new review version.

## Migration And Rollout

Migration would preserve tactical checks until the structural path has passed
the same adversarial cases. In a future authorized implementation, we would
first freeze a refreshed source identity and enumerate every privileged edge.
We would then add fail-closed construction and local ingress/egress guards so
the known paths are protected while typed interfaces are introduced.

The structural transition would next move resolution and network operations
behind capability-typed adapters, introduce the pre-auth/promoted epoch model,
and route selection and transport through it. TURN service identity would be
separated from endpoint promotion before credentials are allowed. Old
configuration and transport entry points would remain only behind an audited
compatibility adapter and would be removed after path coverage and
interoperability validation.

Rollout must be local and reversible for this personal project. A later build
could gate the new fork behind a versioned internal feature choice, but there
must be no runtime fallback that mints ambient authority. Rollback means
returning to an explicitly reviewed Option 1 patch or to the prior non-release
state; it cannot support a claim that the findings remain closed.

## Validation Plan

| Area | Future validation workload | Measure and decision condition |
| --- | --- | --- |
| Path coverage | Static enumeration of every root and reviewed-dependency read, resolve, create, bind, connect, TLS/DTLS handshake, credential, and write edge | Every allowed edge names one capability purpose; every forbidden edge is unreachable or deterministically rejected |
| Ingress admission | Wrong source/interface, oversized message, stale generation, missing integrity, indication, peer-reflexive, direct, and relay cases | No rejected input changes liveness, state, events, or application bytes |
| One-use promotion | Duplicate consume, concurrent promote/revoke, replay, path change, consent loss, expiry, role mismatch, and close races | Exactly one matching transition can issue application authority; every loser fails before I/O |
| Resolution and profile | Rebinding, mixed-family answers, forbidden ranges, excess answers/bytes, mDNS, TCP, mux, proxy, redirects, and wildcard cases | Only bounded provenance-approved answers and profile paths reach a network sink |
| TURN identity | Wrong name, trust digest, pin, ALPN, expiry, transport, redirect, and verification-bypass cases | No credential byte is sent before every declared service check succeeds |
| Compatibility | Direct and relay ICE behavior across the later approved platform matrix | Required profile behavior remains available; forbidden behavior remains unavailable |
| Performance and memory | Baseline versus each option at declared session, candidate, packet-rate, and relay ceilings | Review packet latency, CPU, allocations, and peak RSS against budgets selected before implementation |
| Revocation and close | Block resolver, STUN, TURN, consumer, and I/O paths while changing generation or closing | Capabilities revoke before further mutation/I/O and integrate with the separate total-close contract |

No validation in this table has been executed by this proposal.

## Implementation Work Packages

These are implementation handoff candidates, not authorization to modify the
source:

- **WP-N1 — Identity and path inventory:** bind a refreshed archive and
  dependency graph; enumerate all privileged ingress and egress edges with
  allowed purposes and forbidden profile paths.
- **WP-N2 — Restricted construction:** define the immutable profile, reject
  forbidden modes, and close old configuration entry points.
- **WP-N3 — Resolver and egress capabilities:** introduce provenance-bound
  resolver results and one-use capabilities at create, bind, connect,
  handshake, credential, consent, and write sinks.
- **WP-N4 — Ingress admission:** preserve bounded parse/integrity controls and
  add exact source, interface, generation, transaction, path, and content-class
  admission before mutation.
- **WP-N5 — Promotion and revocation:** implement pre-auth budgets, atomic
  consume-and-promote, application authority, and revocation on every binding
  change.
- **WP-N6 — TURN identity:** enforce exact service inputs before credentials
  while keeping endpoint confirmation a distinct transition.
- **WP-N7 — Verification and migration removal:** run coverage, race,
  adversarial, compatibility, and resource tests; remove the compatibility
  adapter only after acceptance criteria pass.

Acceptance would require complete root and reviewed-dependency path coverage,
deterministic forbidden-path rejection, no pre-admission mutation, exactly-once
promotion under races, no pre-verification TURN credential byte, and approved
performance/resource budgets. Until then, all affected finding dispositions
and closure flags remain unchanged.

## Open Questions

- What exact latency, CPU, allocation, and battery budgets should decide
  whether centralized capability checks are acceptable?
- Which minimum capability tuple prevents replay and ABA across ICE restarts
  without retaining identity-bearing diagnostic data?
- Should the compatibility adapter exist only in tests, or may a
  development-only build expose it during migration?
- Which signed TURN trust inputs and rotation rules are supplied by the G1
  trust boundary, and how are expiry and pin rollover represented?
- What reliable carrier and bounded fragmentation/reassembly design must be
  selected before an application capability can attach to the Runtime channel?
- Does dependency review reveal any resolver, TLS, TURN, proxy, redirect, or
  socket side effect that requires the state machine boundary to change?
