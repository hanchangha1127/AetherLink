# Security Hardening Proposal: Bounded Resource Lifecycle

## Decision

We need to decide whether a future restricted fork should enforce candidate,
pair, request, task, event, worker, and shutdown bounds independently at their
current owners or move those responsibilities to one per-agent resource
supervisor. Option 1 adds local ceilings and timeouts while retaining the
present lifecycle shape. Option 2 requires reservations from one supervisor,
replaces push callback queues with bounded pull events, and applies one total
close deadline.

This proposal prepares that choice only. It selects no option, changes no
source, executes no validation, and closes no finding.

## Executive Recommendation

**Option 1: Independent local ceilings** is the baseline. Candidate, pair,
pending-request, task, notifier, gather, and socket owners would each gain a
fixed limit or timeout. It preserves familiar APIs and lets us patch the
recorded growth and wait points in smaller reviews.

**Option 2: Owned resource supervisor** is the structural alternative. One
per-agent supervisor would reserve capacity before allocation or scheduling,
account across current, draining, and closing generations, own a bounded pull
event queue and independent sticky terminal latch, and spend one 2,500 ms
deadline across shutdown.

I conditionally recommend Option 2 when exact per-agent and two-session process
totals are non-negotiable. It gives us one place to test admission, release,
overflow, terminal state, and close. Option 1 remains a credible short-lived
migration layer if API compatibility is more important than aggregate proofs,
but independent limits cannot be summed reliably without another owner.

## Evidence

I inspected the retained Pion ICE v4.3.0 archive read-only around the recorded
resource and shutdown paths. The canonical records are the
[semantic classifications](../../semantic-source-review-classifications-v1.json)
and [semantic result](../../semantic-source-review-result-v1.json). Source
locations use the retained archive prefix
`github.com/pion/ice/v4@v4.3.0/`.

| Evidence | Finding | Exact referenced source locations |
| --- | --- | --- |
| `G2SR1-F-964c63e397f00eeecc36` | Partial close and abort controls exist | `candidate_base.go:401-429` (primary sink `candidate_base.go:401`) |
| `G2SR1-F-04b73f19b3e2520c5c13` | Push events and graceful close are unbounded | `agent_handlers.go:69-86`, `agent_handlers.go:116-120` (primary sink `agent_handlers.go:116`), `agent_handlers.go:151-155`, `agent_handlers.go:151-190`, `agent_handlers.go:186-190`, `agent_handlers_test.go:15-71` |
| `G2SR1-F-9206ffd24b3357f7cda5` | Candidate processing resources are unbounded | `agent.go:110`, `agent.go:114`, `agent.go:133`, `agent.go:879-886`, `agent.go:960-1000`, `agent.go:986`, `agent.go:991-1000`, `agent.go:1260-1305` (primary sink `agent.go:1290`), `agent.go:1329-1367`, `agent.go:1574-1599`, `agent_handlers.go:49-190`, `agent_handlers_test.go:15-71`, `internal/taskloop/taskloop.go:90-104` |
| `G2SR1-F-9c7a12eced69a28176a4` | Shutdown lacks one total 2,500 ms budget | `agent.go:1478-1500`, `agent_handlers.go:69-86` (primary sink `agent_handlers.go:73`), `gather.go:261-285`, `gather.go:610`, `gather.go:726`, `gather.go:836`, `gather.go:966`, `internal/taskloop/taskloop.go:76-86`, `tcp_mux.go:329-354`, `tcp_packet_conn.go:310-342` |

Observed controls matter here. `candidateBase.abortIO` closes the candidate,
sets a deadline, and can abort a blocked write. The application buffer is also
bounded elsewhere in the reviewed source. We should preserve these controls
rather than replace them merely to make ownership look uniform.

The remaining observed structure has no aggregate owner. Candidate and pair
collections append independently, pending binding requests occupy their own
slice, remote-candidate admission can start goroutines and task-loop work, and
three notifier queues append while a callback drains them. Graceful notifier
close waits for callback goroutines, while task-loop, gather, mux, packet
connection, and callback waits do not spend one shared deadline.

We infer that independent allocation and lifetime ownership is the recurring
condition: no component can reject work based on the full agent or process
total, and no close path can know the remaining time available to every child.
The proposed supervisor is one response to that inference; it does not exist in
the retained source.

## Current Design And Failure Mode

Untrusted candidates and packets can expand candidate, pair, request, task, and
event work. Each subsystem decides locally whether to append, schedule, or
wait. A local limit can protect one collection while total work still grows in
another collection or generation. Pair growth is particularly coupled:
admitting a remote candidate can create work against multiple local candidates,
so a candidate ceiling alone is not a pair or task ceiling.

Push callbacks introduce a second lifetime boundary. The producer can append
faster than an arbitrary callback returns, and graceful close can wait for that
callback. A queue capacity without a terminal policy can deadlock or lose the
only overflow notification. A timeout on each child also does not prove that
sequential close completes within one total 2,500 ms budget.

The structural question is therefore not just where to add `len` checks. It is
whether reservations, overflow state, release, and deadline consumption should
be one coherent lifecycle protocol.

## Desired Invariants

- Every candidate, pair, pending transaction, task, worker, timer, socket,
  allocation, permission, channel, event, and retained event byte reserves from
  declared per-agent and process totals before allocation or state insertion.
- Totals include current, draining, and closing generations; starting a new
  generation cannot hide resources owned by an old one.
- Failed admission has no partial allocation, scheduled task, goroutine, pair,
  event, or externally visible state change.
- The normal event queue holds at most 64 events and 256 KiB. Overflow
  atomically sets an independent sticky terminal latch, discards nonterminal
  queued events, and does not require queue space for an overflow event.
- Event delivery is pull-based or otherwise cannot make close wait for an
  untrusted consumer.
- Close rejects new work, revokes capabilities, cancels timers and contexts,
  aborts sockets and writes, drains only deadline-bound internal workers, and
  returns success or terminal timeout within one total 2,500 ms budget.
- Every successful reservation is released exactly once on success, failure,
  cancellation, timeout, generation replacement, or close.
- Existing socket deadline, close, and blocked-write abort controls remain
  active beneath either option.

## Constraints And Non-Goals

This is a balanced personal-project design review. It does not require
repository-owner authentication, an external signature, or user action.
Runtime peer and service authentication are separate product invariants.

The proposal authorizes no source or dependency modification, archive
extraction, compiler or test execution, network or socket access, device
operation, Git operation, deployment, or credential action. It contains no
measured throughput, latency, memory, battery, NAT, or interoperability result.

The exact non-event ceilings still require a later decision informed by the
[restricted fork profile](../../../restricted-fork-profile.md), platform
budgets, and dependency review. This proposal does not select numeric values
where the bound evidence has not selected them. It also does not redesign
application-level reliable carrier or fragmentation/reassembly.

## Before Architecture

The [before Mermaid source](../diagrams/bounded-resource-lifecycle-before.mmd)
shows the relevant lifetime boundary. Candidate and request work, callback
queues, and shutdown waits branch from the agent but have no shared budget or
deadline owner.

The dangerous edge is cumulative. Each append or wait may look reasonable in
isolation while their sum exceeds the process ceiling or the close budget.
Both options add bounds; they differ in whether the sum remains a convention or
becomes supervised state.

## Options

### Option 1: Independent Local Ceilings

Option 1 adds a fixed capacity to each current collection and queue, a work
admission check before known goroutine and task-loop scheduling points, and a
timeout to each current shutdown participant. Candidate, pair, transaction,
task, callback, gather, mux, and socket owners remain independent. Each owner
would expose saturating reason counters for rejected work and would release its
own accounting on every exit path.

This option's strongest case is incremental review. We can patch the exact
append and wait sites, preserve current callback and close APIs, and validate
one limit at a time. It is also the easier rollback posture because each change
has a narrow owner. These local checks are useful tactical protections even if
we later choose the supervisor.

The principal weakness is composition. A candidate limit does not reserve the
pairs and tasks it will create; per-generation limits do not automatically
include draining generations; three queue limits do not define one event-byte
total. Per-component timeouts can also accumulate beyond 2,500 ms, and a
bounded callback queue still leaves close dependent on callback progress unless
the callback contract changes. Option 1 mitigates the known growth points but
does not establish exact aggregate invariants.

The comparable pair is the shared
[before diagram](../diagrams/bounded-resource-lifecycle-before.mmd) and the
[Option 1 after diagram](../diagrams/bounded-resource-lifecycle-independent-local-ceilings-after.mmd).

| Change | Before | After | Security consequence | Cost |
| --- | --- | --- | --- | --- |
| Candidate and pair state | Independent slices grow as candidates are admitted | Each slice and insertion path has a local cap | Known collections stop at declared local counts | Cross-collection amplification remains |
| Requests and work | Pending requests, goroutines, and tasks have separate admission behavior | Each known scheduler and collection checks a local ceiling | Known task/process growth narrows | Reservation is not atomic across child work |
| Events | Push notifier slices can grow while callbacks block | Each callback queue has event/byte caps and a local overflow policy | Queue growth becomes bounded | Consumer dependence and cross-queue totals remain |
| Generations | Owners account primarily for their current state | Each owner is required to include its own draining state | Hidden old-generation use narrows locally | No single proof of the process sum |
| Shutdown | Task, callback, gather, mux, and socket waits are independent | Each wait has a component timeout | A single child cannot wait forever | Sequential timeouts can exceed 2,500 ms |
| Existing abort | Socket deadline, close, and write abort are local controls | Those controls are preserved and covered by regression tests | Known blocked I/O remains interruptible | Does not bound arbitrary callback or task execution |

Option 1 is a practical defensive patch, but its acceptance criteria must stay
local. We should not infer a total resource or shutdown proof by adding the
individual limits on paper. Rollback is straightforward at the patch level,
but it restores unbounded behavior and is not a safe closure claim.

### Option 2: Owned Resource Supervisor

Option 2 introduces one per-agent resource supervisor and one process-level
aggregator for the profile's two-session maximum. Work enters through a
reservation API that covers the parent operation and its possible child
objects before any allocation, append, goroutine, task, or event. Reservations
carry generation and lifecycle identity and are released exactly once through
structured completion or cancellation.

The supervisor would own the bounded pull event stream. The ordinary queue
could retain at most 64 events and 256 KiB, but the terminal condition would
not be an ordinary event. Overflow would atomically set a separate sticky
latch, discard nonterminal events, revoke new work, and begin close without
waiting for a consumer. A compatibility callback adapter could poll the queue
during migration, but the supervisor would never wait for that adapter.

Close would pass one absolute deadline, not a fresh duration, to every internal
child. The supervisor would first reject reservations, cancel and revoke,
invoke the preserved socket/write abort controls, and then join only owned
workers with the remaining budget. When the deadline expires, it would publish
the terminal timeout state and return rather than waiting for a callback or
consumer.

The attractive property is compositional accounting: candidate admission can
reserve its worst-case pair and work fan-out, and the process aggregator can
include active and draining generations across both sessions. What gives me
pause is the reliability concentration. Incorrect reservation ordering can
deadlock; a leaked token can permanently reduce capacity; a double release can
admit excess work. The supervisor itself therefore needs a small state model,
strict lock ordering, saturating arithmetic, invariant checks, and race-heavy
tests.

The comparable pair is the shared
[before diagram](../diagrams/bounded-resource-lifecycle-before.mmd) and the
[Option 2 after diagram](../diagrams/bounded-resource-lifecycle-owned-resource-supervisor-after.mmd).

| Change | Before | After | Security consequence | Cost |
| --- | --- | --- | --- | --- |
| Admission | Each owner allocates or schedules independently | Parent and child capacity is reserved atomically before work | Excess fails before partial resource creation | Reservation API on every resource path |
| Aggregate totals | Collections and generations expose no exact sum | One agent supervisor and process aggregator count current, draining, and closing generations | Declared agent/process ceilings become testable | Central trusted accounting component |
| Events | Push queues depend on callback progress | Bounded pull queue plus independent sticky terminal latch | Overflow and close do not depend on consumer progress | Consumer API migration and adapter |
| Terminal behavior | Errors and close state are spread across owners | One sticky terminal state rejects new work and remains observable | Overflow cannot be lost behind a full queue | Terminal precedence and idempotence design |
| Shutdown | Children wait independently | One absolute 2,500 ms deadline is consumed across cancel, abort, and join | Total close duration becomes falsifiable | All children must accept cancellation/deadline |
| Existing abort | Candidate abort is useful but local | Supervisor invokes and preserves socket/write abort before bounded join | Blocked I/O is interrupted inside the total budget | Integration and exactly-once cleanup work |

This option creates more migration work because callbacks, resource-producing
functions, and close semantics all change. It also offers the only direct path
among these two options to an exact aggregate claim. Rollback requires keeping
the local ceilings and a tested callback adapter until the supervisor has
passed resource, race, and close validation; bypassing the supervisor is not an
acceptable runtime fallback.

## Comparison

The following effects are not measured. They identify the expected mechanism
and the evidence needed before a selection can become an implementation
decision.

| Dimension | Option 1: Independent local ceilings | Option 2: Owned resource supervisor | Validation needed |
| --- | --- | --- | --- |
| Security | **Improves**, medium confidence, source-derived: known growth points stop locally, but aggregate amplification remains | **Improves**, medium confidence, source-derived: reservations and one terminal owner make aggregate overflow testable | Saturate every individual and combined limit, including fan-out and overlapping generations |
| Performance | **Regresses**, low confidence, hypothetical: each local owner adds checks and counters near current operations | **Unknown**, low confidence, hypothetical: centralized reservations add synchronization but may avoid repeated accounting | Compare candidate-add latency, packet/event throughput, close latency, CPU, contention, and allocations |
| Memory | **Improves**, medium confidence, source-derived: capped collections prevent their current unbounded growth | **Improves**, medium confidence, source-derived: aggregate caps include queues and generations, offset by bounded token/accounting state | Measure peak RSS and live objects at each local, agent, and two-session process ceiling |
| Reliability | **Improves**, low confidence, source-derived: individual exhaustion fails earlier, while per-owner policies can disagree | **Unknown**, low confidence, hypothetical: deterministic terminal behavior improves containment, but the supervisor is availability-critical | Fault reservation/release, callback, timer, gather, socket, generation, and close paths under races |
| Operability | **Regresses**, medium confidence, source-derived: several counters and overflow policies must be correlated | **Improves**, low confidence, hypothetical: one bounded snapshot and terminal reason simplify diagnosis, but new alerts are needed | Confirm bounded, secret-free counters expose limit, owner, generation class, and terminal reason |
| Migration | **Neutral**, high confidence, source-derived: focused edits preserve APIs but are numerous | **Regresses**, high confidence, source-derived: resource APIs, callbacks, generation accounting, and close contract change | Rehearse callback-adapter rollout, dual-accounting comparison, cutover, and rollback after later build authority |

Option 1 has lower coordination cost and remains valuable as migration
protection. Option 2 has higher synchronization and API risk but is much easier
to reason about when the security statement concerns a total rather than a
single slice. We should choose based on whether exact aggregate bounds and
consumer-independent close are required, not on unmeasured assumptions about
lock overhead.

## Recommendation

I recommend Option 2 conditionally because the desired claims are aggregate:
they cover child fan-out, overlapping generations, two sessions, event bytes,
terminal state, and one total shutdown deadline. No existing local owner has
enough information to make those claims.

I would prefer Option 1 if later measurement shows one supervisor creates
unacceptable contention and the project is willing to weaken the requirement
to independently bounded components. That would be a changed security
requirement, not an equivalent implementation. Option 1 may also be chosen as
a dated migration step while the pull-event API and reservation model are
developed.

This recommendation is not a selection or implementation authorization.

## Evidence Coverage And Residual Risk

The option effects below are conditional design mappings. They do not change
the canonical finding dispositions.

| Evidence | Option 1 effect | Option 2 effect | Tactical protection still required |
| --- | --- | --- | --- |
| `G2SR1-F-964c63e397f00eeecc36` — Partial close and abort controls | **Mitigates** regression risk by preserving and testing the local controls | **Mitigates** regression risk because the supervisor invokes and preserves them | Keep deadline, socket close, and blocked-write abort on every path |
| `G2SR1-F-04b73f19b3e2520c5c13` — Push events and graceful close unbounded | **Addresses** queue growth at inventoried sites, but callbacks and separate queues retain lifetime risk | **Addresses** in design through bounded pull events and an independent terminal latch | Cap existing queues and prevent new callback work during migration |
| `G2SR1-F-9206ffd24b3357f7cda5` — Candidate processing resources unbounded | **Mitigates** known collections and scheduling sites; aggregate fan-out remains | **Addresses** in design through pre-allocation parent/child reservations and process totals | Add local caps before every current append and schedule point |
| `G2SR1-F-9c7a12eced69a28176a4` — Shutdown lacks one 2,500 ms budget | **Mitigates** individual waits; sequential timeout sum remains | **Addresses** in design through one absolute deadline and consumer-independent close | Cancel, reject new work, and preserve abort controls before each current wait |

Residual risk remains after either design:

- `G2SR1-F-65bdab86ddd0720af770` — Dependency source closure is missing — has
  no source location or sink and is unaffected. Dependency workers, timers,
  queues, sockets, or close behavior can invalidate root-only totals.
- A supervisor can leak, double-release, under-reserve, overflow counters, or
  deadlock if reservation ordering and completion are not proven.
- Numeric ceilings other than the selected event and shutdown limits still
  require explicit platform and workload decisions; arbitrary values would
  create denial-of-service or availability risk.
- Terminal-state priority, repeated close, and simultaneous overflow/timeout
  behavior require a deterministic state model.
- OS and dependency close calls can exceed expectations; the total contract
  must return on deadline without claiming that an external resource is
  synchronously gone.
- Resource bounds do not replace ingress admission, secret-free diagnostics,
  endpoint authentication, or capability revocation.

## Migration And Rollout

A future authorized migration should begin with a refreshed source identity
and a complete ledger of every resource create, retain, schedule, release, and
wait path. Local ceilings and cancellation checks should be added first as
tactical protection, with explicit counters for attempted excess and leaked
reservations.

For Option 2, the next phase would introduce supervisor accounting in shadow
mode solely to compare expected and observed ownership; enforcement would
remain with the local limits until mismatches are zero under the approved
test suite. Resource-producing paths would then move to atomic reservations,
and the process aggregator would include both sessions and all generation
states.

Event consumers would migrate from callbacks to pull. A temporary callback
adapter could consume the bounded queue, but close would not wait for it. The
sticky terminal latch and one-deadline shutdown would be enabled only after
idempotence, race, and blocked-consumer cases pass. Local ceilings remain until
the supervisor is fully enforced.

Rollback would disable supervisor enforcement only to the tested local-ceiling
baseline and only before any release claim. It would leave closure false and
could not restore push callbacks or unbounded waits in a production-ready
profile.

## Validation Plan

| Area | Future validation workload | Measure and decision condition |
| --- | --- | --- |
| Local and aggregate limits | Fill each candidate, pair, transaction, task, worker, socket, and timer limit separately and in combined fan-out | Excess fails before allocation, append, goroutine, task, or visible state; counts never exceed declared totals |
| Generation/process accounting | Hold current, draining, and closing generations across the two-session process maximum | Process total equals the sum of all live generation reservations with no hidden or double-released item |
| Event overflow | Block the consumer, fill 64 events or 256 KiB, then produce concurrent excess and terminal causes | Queue never exceeds either limit; one sticky terminal state is observable without queue space; nonterminal events are discarded |
| Reservation races | Concurrent admit, cancel, timeout, completion, generation replacement, and close | Every reservation releases exactly once; no underflow, overflow, leak, deadlock, or post-terminal admission |
| Total shutdown | Block resolver, STUN, TURN, gather, task, callback adapter, socket read/write, and event consumer | Close rejects new work, invokes abort, and returns success or terminal timeout within one total 2,500 ms deadline |
| Reliability | Inject failures between parent reservation and every child allocation or schedule point | No partial child state survives a failed parent operation |
| Performance | Baseline, local-ceiling, and supervisor runs at declared direct/relay candidate and event loads | Compare throughput, p50/p95/p99 latency, CPU, contention, allocations, peak RSS, and close distribution against preselected budgets |
| Diagnostics | Trigger every limit and terminal transition | Only bounded reason codes and saturating counts are emitted; no candidate, address, hostname, credential, stable ID, or payload appears |

These validations are planned, not executed.

## Implementation Work Packages

The following packages describe a possible later handoff and do not authorize
source changes:

- **WP-R1 — Resource ledger and exact ceilings:** enumerate every root and
  reviewed-dependency resource path; select per-agent and two-session process
  limits with explicit fan-out assumptions.
- **WP-R2 — Tactical local bounds:** cap existing collections and scheduling
  sites, add cancellation, preserve `abortIO`, and add leak/overflow counters.
- **WP-R3 — Reservation model:** define parent/child atomic reservation,
  generation ownership, saturating arithmetic, release-once semantics, and lock
  ordering.
- **WP-R4 — Event and terminal contract:** implement the 64-event/256-KiB pull
  queue, independent sticky terminal latch, discard policy, and temporary
  callback adapter.
- **WP-R5 — Deadline shutdown:** pass one absolute deadline through reject,
  revoke, cancel, socket/write abort, and internal worker joins; never wait for
  the consumer.
- **WP-R6 — Process aggregation and migration:** include both sessions and all
  generation states, compare shadow and local accounting, enforce only after
  parity, and retain the local rollback baseline.
- **WP-R7 — Adversarial validation:** execute limit, race, leak, overflow,
  terminal, blocked-child, close, performance, memory, and diagnostic suites.

Acceptance would require no pre-allocation excess, exact live totals under
overlapping generations, exactly-once release, consumer-independent terminal
observation, and close return within the selected total budget. Dependency
resource paths must be reviewed before aggregate closure can be considered.

## Open Questions

- What exact ceilings should apply to candidates, pairs, transactions, tasks,
  workers, timers, sockets, TURN objects, resolver data, and packet/byte rates
  on the target Mac and Android devices?
- Must candidate admission reserve worst-case pair fan-out up front, or may a
  deterministic partial-admission policy preserve a bounded useful subset?
- Which terminal cause wins when overflow, authentication failure, consent
  loss, explicit close, and deadline expiry race?
- Can all dependency workers and I/O waits accept cancellation or an absolute
  deadline, and what containment is required when they cannot?
- How long may the callback compatibility adapter exist, and which internal
  consumers can migrate directly to pull events?
- What latency and contention budget would make independent local ceilings
  preferable despite their weaker aggregate guarantee?
