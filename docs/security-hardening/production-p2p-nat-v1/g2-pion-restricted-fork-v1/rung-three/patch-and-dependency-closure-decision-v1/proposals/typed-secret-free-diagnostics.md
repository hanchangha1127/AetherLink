# Security Hardening Proposal: Typed Secret-Free Diagnostics

## Decision

This is a preparation-only design proposal for the diagnostics portion of the
restricted Pion fork. It compares two future options, but selects neither,
authorizes no implementation, and does not close either finding. No external
authentication, repository-owner proof, execution permit, or user action is
needed to read and discuss this proposal. It also grants no source edit,
compile, test execution, network, socket, device, or Git authority.

The evidence remains immutable: this document is derived from the published
semantic-review classification, not a replacement for it. Any implementation
decision should bind the same evidence again, or a new version if the bound
source snapshot changes.

## Executive Recommendation

The complete option set is: **Option 1, delete current sensitive logs**, and
**Option 2, typed diagnostic sink**. I conditionally recommend Option 2 if a
later decision accepts a small fork-level diagnostic API boundary and funds
its migration coverage. It gives us one place to prohibit values that should
not reach diagnostics and to bound the remaining signal. That recommendation
is not a selection: both options remain unselected, unimplemented, and
insufficient to claim finding closure.

Option 1 is the narrower response when compatibility and delivery time are the
dominant constraints. It can remove the known credential and candidate paths,
but it relies on future callers continuing to remember the same rule. Option
2 becomes less attractive if the current logger is a required external API or
if a later source review shows that typed events cannot carry the operational
conditions engineers need without reintroducing free-form context.

## Evidence

I inspected the retained Pion ICE v4.3.0 archive read-only at the locations
below; it was not extracted, compiled, loaded, or executed. The published
classification is the canonical finding record. The source locations describe
the reviewed snapshot, not a claim about a later fork revision.

| Evidence | Finding or source location | What it establishes |
| --- | --- | --- |
| `G2SR1-F-6469763b45a8335ddef9` — Remote credential fields reach diagnostics | `agent.go:644-656` (`(*Agent).startConnectivityChecks`) | **Observed:** line 656 formats `remoteUfrag` and `remotePwd` into a debug diagnostic; the canonical published finding is P1, `unresolved` (its primary pass proposed `patch_required`). |
| `G2SR1-F-0b0f647a603042ba5063` — Raw candidate/hostname diagnostics lack allowlisting | `agent.go:524`, `agent.go:968`, `agent.go:976`, `agent.go:1013-1030`, and `agent.go:2087-2088` | **Observed:** diagnostics format the mDNS name, candidate address, candidate object, resolution error, and local/remote pair values; the published finding is P2, `unresolved`. |
| `G2SR1-F-6469763b45a8335ddef9` — Remote credential fields reach diagnostics | `gather.go:390-404` | **Observed:** TCP-mux diagnostics format local ufrag and address-related values, showing that the same logger boundary is reached from gathering as well as connectivity start. |

The first finding identifies a direct secret-bearing sink. The second identifies
an adjacent class of raw identity and address diagnostics whose values can be
sensitive in deployment context even when they are not passwords. **Inferred:**
the structural problem is not only a few unsafe format strings; it is that
callers own both diagnostic meaning and serialization, so the sink cannot
distinguish an allowlisted condition from a credential, hostname, candidate, or
wrapped dependency error. The proposed options below respond to that ownership
gap; they do not establish that every logger path has been found.

## Current Design And Failure Mode

The current diagnostic path lets values from candidate handling, mDNS
resolution, connectivity start, and gathering flow through free-form formatting
into the logger factory and application sink. The diagram makes the important
boundary visible: the sink receives already-rendered text, after the value type
and sensitivity have been erased.

[Before architecture: free-form diagnostic flow](../diagrams/typed-secret-free-diagnostics-before.mmd)

An attacker or a remote peer need not control the logging subsystem itself to
benefit from that structure. If a sensitive value is accepted by a normal
protocol or candidate path and the error path formats it, downstream retention,
collection, or support tooling can receive it. Existing log-level configuration
does not make this safe: it changes whether a message is emitted, not whether a
call site is capable of constructing secret-bearing text.

## Desired Invariants

- A diagnostic sink accepts only a finite, documented vocabulary of reason
  codes and bounded numeric counters; it has no parameter for credential,
  address, hostname, candidate, payload, or wrapped-error text.
- Any exceptional diagnostic that needs context is explicitly reviewed at the
  type boundary; it cannot reach the normal sink by interpolation or implicit
  `String` formatting.
- Diagnostic cardinality and emission rate are bounded so an adversary cannot
  turn a recoverable failure into unbounded diagnostic work.
- Removing or replacing a diagnostic preserves the underlying error handling,
  state transition, and protocol behavior unless a later implementation
  decision explicitly changes those behaviors.

## Constraints And Non-Goals

We have no measured logging throughput, allocation, collector, support, or
compatibility budget. The retained archive is a source snapshot, not proof of
the AetherLink fork's runtime exposure. This proposal does not redesign
observability, alter log retention, classify all possible personal data, or
approve a dependency or a logging backend. It also does not change product
authentication, network admission, source acquisition, or release authority.

Both options must retain ordinary error returns and operational failure
handling while a later implementation plan determines what safe, aggregate
signal is actually useful. During any migration, known secret-bearing calls
remain tactical removal targets rather than acceptable temporary telemetry.

## Before Architecture

The before view above is deliberately at the diagnostic-boundary level rather
than a call graph. It shows why deleting individual messages is useful but does
not create a reusable prohibition: every caller can still serialize sensitive
input before the existing logger sees it.

## Options

### Option 1: Delete current sensitive logs

Option 1 removes the known diagnostic calls identified by the two findings and
keeps the existing logger for unrelated messages. Its strongest case is a small
patch surface: it preserves the current interfaces and avoids a new event
model. We would retain error returns and state handling, but remove the
free-form candidate, hostname, credential, and pair values from the named
calls. A later review would still need to search equivalent call sites before
claiming the two findings are addressed.

[Option 1 after architecture: remove known sensitive calls](../diagrams/typed-secret-free-diagnostics-delete-current-sensitive-logs-after.mmd)

The security gain is concrete but local: the listed call sites no longer emit
the problematic strings if the future patch is correctly implemented. The
residual risk is structural drift. New code, overlooked callers, or diagnostic
wrappers can recreate the same flow because the logger continues to accept
arbitrary formatted text. Rollback would be simple because the existing logger
and APIs remain in place, but restoring a removed diagnostic must not restore
secret-bearing formatting without a renewed review.

| Change | Before | After | Security consequence | Cost |
| --- | --- | --- | --- | --- |
| Known diagnostic calls | Candidate, hostname, pair, or credential text reaches a formatter | Named sensitive calls are absent | Narrows the two observed paths | Useful debugging context is lost until a safe replacement is designed |
| Sink contract | Existing logger accepts rendered strings | Unchanged | Future callers can still construct unsafe text | Low migration and rollback cost, but control drift remains |
| Validation burden | No central proof of allowed fields | Call-site search plus regression assertions | Detects known regressions only | Ongoing review is required for every new diagnostic |

### Option 2: Typed diagnostic sink

Option 2 introduces a narrow adapter between internal conditions and the
application diagnostic sink. Callers would request a typed condition such as a
finite reason code and bounded counter; the adapter owns serialization,
allowlisting, saturation, and rate/cardinality limits. The important design
choice is negative as well as positive: its public event type has no fields for
remote credentials, candidates, addresses, hostnames, identity values, packet
payloads, or arbitrary errors. That gives us a boundary that a reviewer can
test by construction rather than relying only on formatting discipline.

[Option 2 after architecture: typed, bounded diagnostic sink](../diagrams/typed-secret-free-diagnostics-typed-diagnostic-sink-after.mmd)

The attractive part is that it converts a dispersed convention into owned
policy. We can test the finite event vocabulary, reject implicit string
conversion, and keep operational signal aggregate. What gives me pause is the
migration surface: the adapter might encourage a false sense of completeness if
legacy logger access remains reachable, and a too-small reason taxonomy can
make incidents harder to investigate. A future implementation should therefore
either prohibit direct diagnostic-sink access for the relevant package boundary
or record every justified exception, while preserving the deletion of known
sensitive calls during the transition.

This option may add a small allocation, counter update, lock, or atomic step
per emitted event; the actual cost is unmeasured. It can also improve failure
containment if the rate limiter drops excess events without touching the
protocol path. Rollback is feasible by retaining a compatibility adapter that
maps typed events to the existing sink, but rollback must not reopen a
free-form path for secret-bearing values.

| Change | Before | After | Security consequence | Cost |
| --- | --- | --- | --- | --- |
| Control owner | Each caller renders text | Adapter owns allowed event representation | Sensitive types have no normal encoding route | New API and taxonomy require review |
| Volume control | Event volume follows caller behavior | Bounded counters and rate/cardinality policy | Limits diagnostic amplification | Possible loss/coalescing of detail under load |
| Legacy escape hatch | Existing logger is directly reachable | Direct access must be prohibited or explicitly excepted | Makes bypasses reviewable | Migration and compatibility work |

## Comparison

The following is a design comparison, not measured runtime data. It makes the
cost mechanism explicit so a later selected implementation can test it against
a baseline rather than treating these estimates as results.

| Dimension | Option 1 — delete current sensitive logs | Option 2 — typed diagnostic sink | Basis and later validation |
| --- | --- | --- | --- |
| Security | Improves the named paths but leaves arbitrary-string sink authority; residual drift is high. | Improves prevention by restricting normal event representation and bounds amplification; legacy bypasses remain a migration risk. | Source-derived; search all relevant logger factories/callbacks and add negative tests for forbidden value types. |
| Performance | Likely neutral or slightly better because messages are removed. | Unknown small overhead from event construction, counters, and rate checks. | Hypothetical; benchmark emitted and suppressed diagnostics under representative candidate churn, measuring p50/p99 protocol-path latency. |
| Memory | Likely neutral. | Bounded counter/rate state adds finite retained memory. | Hypothetical; measure peak RSS and retained entries under distinct reason-code and peer-input floods, with a declared cap. |
| Reliability | Preserves existing error control flow but removes some incident context. | Can preserve aggregate signal and fail closed for diagnostic serialization, but a bad adapter must never block protocol progress. | Source-derived; fault-inject sink failure and verify error/state behavior continues with bounded drop accounting. |
| Operability | Lower immediate burden, weaker diagnosis. | Requires reason-code documentation, dashboards/queries, and saturation visibility. | Hypothetical; have on-call review whether aggregate signals diagnose the two evidence paths without raw values. |
| Migration | Small, focused change; easy rollback, but repeated audits are needed. | API conversion and legacy-access audit; rollback through a typed-to-existing adapter. | Source-derived; inventory direct logger callers and require a no-free-form-access gate before expanding coverage. |

## Recommendation

I recommend Option 2 conditionally: it is the only option that gives us a
reusable owner for both confidentiality and diagnostic resource bounds. That is
proportionate to a P1 credential diagnostic and adjacent P2 raw candidate/
hostname diagnostics, provided a later decision explicitly accepts the API and
operability work. This is a recommendation only. It neither selects Option 2
nor authorizes its code, tests, compilation, deployment, or evidence closure.

Option 1 should win if a later constrained decision needs immediate removal of
the known messages before a typed taxonomy is ready, or if compatibility review
shows that the diagnostic interface cannot be changed safely. In that case we
should record it as a time-bounded tactical measure and keep the typed boundary
available for reconsideration rather than claiming that deletion solved future
caller drift.

## Evidence Coverage And Residual Risk

| Evidence | Option 1 effect | Option 2 effect | Tactical protection still required | Residual risk |
| --- | --- | --- | --- | --- |
| `G2SR1-F-0b0f647a603042ba5063` — Raw candidate/hostname diagnostics lack allowlisting | Addresses listed calls only after a future source change; no generic allowlist exists. | Addresses raw-value recurrence and diagnostic amplification through finite types and bounds. | Remove/rewrite the listed candidate, hostname, mDNS, and pair formatting sites. | Unknown callers, logger callbacks, and support tooling remain outside this proposal's review scope. |
| `G2SR1-F-6469763b45a8335ddef9` — Remote credential fields reach diagnostics | Addresses the observed `agent.go:656` format call only if a future patch removes it. | Addresses the recurrence class when all relevant calls use the typed boundary. | Remove the known credential format call in either migration. | Other legacy/free-form loggers or dependencies may still expose credentials. |

Neither option establishes that source locations are exhaustively revalidated,
that dependency-originated errors are secret-free, or that logs are retained
safely. Both findings therefore remain open until a selected implementation is
reviewed against the then-current source and its intended runtime path.

## Migration And Rollout

A later selection should first bind the current source revision and re-check
the two findings' call sites. For Option 1, migration is a focused deletion or
replacement of the named messages while preserving errors and state transitions.
For Option 2, we should introduce the finite event vocabulary and adapter,
convert the two evidence paths, then inventory and constrain remaining direct
logger access before treating the boundary as broadly applicable.

Rollout should begin with a non-sensitive aggregate visibility check rather
than a production claim: compare reason-code counts and saturation notices with
the preselected baseline in a bounded test environment. Rollback should retain
the prior protocol behavior and typed-to-existing-sink compatibility path, but
must not re-enable credential or raw-candidate formatting. This proposal does
not authorize either rollout or rollback operation.

## Validation Plan

- Bind a selected implementation to a refreshed source snapshot; stop and
  return to design review if the reviewed functions or logger ownership drift.
- Add negative tests proving the typed API cannot accept credentials, addresses,
  hostnames, candidates, payloads, arbitrary errors, or implicit strings.
- Exercise the `startConnectivityChecks`, candidate/mDNS, nomination, and
  gathering error paths with sentinel secret values; assert diagnostics contain
  only allowlisted codes and bounded counters, while existing error/state
  behavior is preserved.
- Run static searches for direct logger factory/callback use in the affected
  package boundary, with every exception reviewed and documented.
- Benchmark a baseline and candidate under repeated diagnostic events and
  hostile cardinality inputs; record p50/p99 protocol-path latency, allocation
  rate, peak retained state, dropped/coalesced count, and a predeclared limit.
- Fault-inject diagnostic sink failure and saturation; verify it cannot block
  packet handling, create unbounded work, or restore raw-value output.

## Implementation Work Packages

These are proposed packages for a later selected option, not authorization to
perform them now.

- Rebind the two findings and all affected logger call sites to a refreshed,
  immutable source snapshot; define the allowed reason-code vocabulary and
  forbidden data types.
- For Option 1, remove or safely replace the named sensitive diagnostics while
  preserving error propagation and state transitions.
- For Option 2, add a typed adapter with finite reason codes, bounded counters,
  explicit saturation/rate behavior, and no free-form secret-bearing fields.
- Convert the two evidence paths and audit direct diagnostic sink access in the
  affected boundary; keep known sensitive-call removal as a tactical guard.
- Add unit, negative, integration, resource, and fault-injection validation;
  define acceptance thresholds before any rollout discussion.
- Prepare a reversible compatibility path and an evidence-backed review of
  remaining exceptions before considering wider adoption.

## Open Questions

- Which reason codes provide useful operations signal without encoding a remote
  identity, topology, credential, payload, or wrapped dependency message?
- Where are logger factory callbacks and application sinks implemented in the
  restricted fork, and can direct use be constrained without breaking callers?
- What are the acceptable rate, cardinality, memory, and dropped-event limits
  for candidate churn and failure storms?
- Do support, crash, or metrics paths consume the same formatted text, and what
  separate retention controls apply to them?
- Does a refreshed source snapshot add diagnostic paths not present in the
  retained v4.3.0 archive?
