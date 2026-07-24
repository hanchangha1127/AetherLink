# Security Hardening Proposal: Fixed-Point Dependency Source Closure

## Decision

We need to decide how a future, separately authorized review could turn the
retained Pion ICE v4.3.0 root-module metadata into an exact, reviewable
dependency graph. The choice is between **Option 1: Single-Wave Inventory
Review**, which reviews one bounded seed wave and leaves newly discovered
tuples for a later decision, and **Option 2: Staged Fixed-Point Source
Closure**, which repeats immutable, versioned waves until the selected module
graph stops expanding and only then performs the complete source, license,
SBOM, and readback review.

This proposal does not select either option. It does not acquire dependency
source, open the network, install a package, invoke a compiler, implement a
patch, or close a finding. It also does not select Pion as a candidate or
library. Every current closure and selection flag remains false.

## Executive Recommendation

I conditionally recommend **Option 2: Staged Fixed-Point Source Closure** if a
later local technical decision chooses to continue dependency review. Its
strongest property is not that it downloads more material; it is that every
new module tuple becomes a visible decision input instead of arriving through
ambient package-manager behavior. That lets us preserve the G2 rule that a
later rung is never authorized merely because an earlier rung passed.

**Option 1: Single-Wave Inventory Review** remains a legitimate narrower
choice when the immediate goal is only to reduce uncertainty around the 19
root requirements under one small, predeclared bound. We should choose it only
if we are comfortable ending with an intentionally incomplete graph and a new
decision for any transitive tuple. It cannot support a dependency-closure
claim.

Option 2 becomes preferable only after exact acquisition limits, provenance
rules, and a no-overwrite failure policy are recorded. If those inputs cannot
be fixed without credentials, external identity proof, or user action, the
technical process must stop; it must not request them. Neither option changes
product endpoint authentication, which remains separate from source review.

## Evidence

I inspected the tracked semantic artifacts and the retained archive metadata
read-only. The evidence that most influenced this diagnosis is the combination
of one explicit missing-dependency-source finding, two behavior findings marked
as dependency-blocked, and a `go.sum` that contains more tuples than the root
`go.mod` requires. That combination shows why checksum inventory and source
closure must remain different states.

The local evidence collection and its hashes are recorded in
[context.md](../context.md). The following map defines each identifier used in
this proposal.

| Evidence | Finding or document | What it establishes |
| --- | --- | --- |
| `G2PD001` | [Semantic source-review classifications](../../semantic-source-review-classifications-v1.json), SHA-256 `e76e8c9fa0a78c8c5c4beae1ebfd4c4f8144b411689a3a8bd5f8804ebf61c8c9` | Defines the 19 canonical findings, including the three dependency-blocked findings and the lexical false-positive boundary described below. |
| `G2PD002` | [Semantic source-review result](../../semantic-source-review-result-v1.json), SHA-256 `a01b3518f1354d438542ae77c06aa92d8f0936d516b4070d19c5bf27791e8a98` | Records 7 `patch_required`, 12 `unresolved`, and all semantic, dependency, rung-three, candidate, and library closure flags as false. |
| `G2PD003` | [Semantic source-review manifest](../../semantic-source-review-manifest-v1.json), SHA-256 `300da97505b4715576d665846b23dd8363b36d416ed5d24ed4a7d4e77f098e6f` | Binds the two non-attesting semantic passes and preserves non-claims; it is not dependency-source evidence. |
| `G2PD006` | Retained Pion ICE v4.3.0 root archive, SHA-256 `f95ef3ce2e0063c13925f478bf8d188833725b2f0a7ecb1e695dee8ab61ef63c` | Contains the root module only. Its recorded source-tree SHA-256 is `b44b1277937432822d005632dc0ac77b0c733959c871d998fac5e3964ce39244`; it does not contain reviewed dependency source. |
| Tracked dependency metadata | [Offline source-review result v3](../../offline-source-review-result-v3.json), raw SHA-256 `ef4b8d88ec57501377a7bc9db066c04a1a379041ee1b11999f5d16c7d4447933` | Records inventory-only root `go.mod` and `go.sum` metadata, with no dependency acquisition or license conclusion. |
| G2 authority ladder | [Canonical roadmap](../../../../../../roadmap.md) and [restricted-fork profile](../../../restricted-fork-profile.md) | Separates offline source review from dependency/license/SBOM closure and keeps compile, sockets, and controlled-network evaluation in later independently authorized rungs. |

The four findings covered by the dependency-closure options are:

| Finding | Reader-facing title | Observed disposition and relevance |
| --- | --- | --- |
| `G2SR1-F-65bdab86ddd0720af770` | Dependency source closure is missing | P1, `unresolved`, and dependency-blocked. The two passes report that 19 required modules and 44 checksum records have no bound dependency source review. |
| `G2SR1-F-7e744b8ee19e7de9b7c3` | Resolution behavior remains dependency-unresolved | P1, `unresolved`, and dependency-blocked. Exact dependency and ambient-resolver behavior is unavailable, while a bounded caller-supplied answer and admission patch remains necessary. |
| `G2SR1-F-7d678ddf77ac89e04ae4` | TURN TLS service identity is not exact | P1, `patch_required`, and dependency-blocked. Reviewing dependencies can expose the exact TLS/DTLS behavior, but cannot replace the required trust, host, pin, expiry, deadline, and bypass-removal patch. |
| `G2SR1-F-c9dd2e9b3fa55e3ad43b` | Lexical hits are not vulnerability counts | P3, `unresolved`, and not dependency-blocked. A fixed-point review can mitigate the risk of treating lexical candidate locations as findings, but every observation still needs an exact semantic disposition. |

The tracked root metadata is exact enough to seed a decision but not to prove a
fixed point. The root module is `github.com/pion/ice/v4`, its Go directive is
`1.24.0`, and no toolchain value is recorded. The retained `go.mod` is 794
bytes at SHA-256
`5044428710b5a718aad517eed5c08e1933378efa3d9b4245853cfb312560aca4`.
Its 19 requirement rows are:

| Exact module tuple | Root marker |
| --- | --- |
| `github.com/davecgh/go-spew@v1.1.1` | indirect |
| `github.com/google/uuid@v1.6.0` | direct |
| `github.com/kr/pretty@v0.1.0` | indirect |
| `github.com/pion/dtls/v3@v3.1.5` | direct |
| `github.com/pion/logging@v0.2.4` | direct |
| `github.com/pion/mdns/v2@v2.1.0` | direct |
| `github.com/pion/randutil@v0.1.0` | direct |
| `github.com/pion/stun/v3@v3.1.6` | direct |
| `github.com/pion/transport/v4@v4.0.2` | direct |
| `github.com/pion/turn/v5@v5.0.12` | direct |
| `github.com/pmezard/go-difflib@v1.0.0` | indirect |
| `github.com/stretchr/testify@v1.11.1` | direct |
| `github.com/wlynxg/anet@v0.0.5` | indirect |
| `golang.org/x/crypto@v0.48.0` | indirect |
| `golang.org/x/net@v0.49.0` | direct |
| `golang.org/x/sys@v0.41.0` | indirect |
| `golang.org/x/time@v0.14.0` | indirect |
| `gopkg.in/check.v1@v1.0.0-20190902080502-41f04d3bba15` | indirect |
| `gopkg.in/yaml.v3@v3.0.1` | indirect |

The retained `go.sum` is 3,675 bytes at SHA-256
`b47d7d5f3bb8c8b85b3283585f97ea6bd0a8b97427b49068b9f5685ddd953887`.
All 19 root requirements have one source checksum and one `go.mod` checksum,
accounting for 38 records. The remaining six records describe four
checksum-only tuples:

| Checksum-only tuple | Records present | Required interpretation |
| --- | --- | --- |
| `github.com/kr/pty@v1.1.1` | `go.mod` only | Context only; not a selected dependency without graph evidence. |
| `github.com/kr/text@v0.1.0` | source and `go.mod` | Context only; two checksums do not establish selection. |
| `github.com/pion/transport/v3@v3.1.1` | source and `go.mod` | Context only; it must not be merged with required `transport/v4`. |
| `gopkg.in/check.v1@v0.0.0-20161208181325-20d25e280405` | `go.mod` only | Context only; it is distinct from the required later pseudo-version. |

Thus the observed inventory is exactly 19 required tuples, 4 checksum-only
context tuples, 23 distinct module/version tuples in `go.sum`, and 44 checksum
records. We infer that dependency behavior, licenses, and the complete selected
graph remain unknown because no retained dependency sources or transitive
`go.mod` bodies are bound. We do not infer that the four checksum-only tuples
are dependencies, nor that the 19 root rows are the complete transitive graph.

## Current Design And Failure Mode

The current design has a strong root identity boundary and a weak dependency
knowledge boundary. One verified archive supplies the root source, the root
metadata is recorded, and two semantic passes cover that root snapshot. Past
that boundary, we have checksums but no bound source bodies, no transitive
module edges, no dependency license conclusions, and no dependency behavior
review.

That distinction matters for the two behavior findings. Root source shows
where resolution and TURN TLS controls must be inserted, but the behavior
called through dependency packages remains outside the reviewed snapshot. If
we were to treat the 44 checksum rows as a lockfile or treat `indirect` as a
runtime-reachability classification, we could create a precise-looking SBOM
that still omits selected modules or misstates which code can run under the
Android and macOS profiles.

The structural failure mode is therefore not a single bad dependency. It is an
open-ended discovery loop without an owned fixed-point rule. A package manager
could discover another tuple, a transitive `go.mod` could alter the selected
version, or a build tag could expose a different package surface. Unless each
such change forces a new immutable decision, the review boundary can drift
while the evidence continues to look complete.

## Desired Invariants

We want the following falsifiable properties before any dependency-closure
claim could be considered:

- The initial seed is exactly the 19 root requirement tuples bound to the
  retained `go.mod` hash; the four checksum-only tuples remain a separate,
  non-selected context set.
- Every module graph vertex has an exact module path, version, source
  provenance, source/archive digest, tree digest, and retained `go.mod` body
  before its behavior or license can be called reviewed.
- Every newly discovered selected tuple stops the current wave and appears in
  a new immutable decision version before any source acquisition for that
  tuple.
- The selected graph reaches a fixed point only when an independent
  recomputation finds zero new selected tuples and every selected vertex and
  edge is bound.
- Source acquisition, source review, source-reviewed status, security
  acceptance, and dependency closure are distinct states. Completing one does
  not imply the next.
- Production reachability is derived against exact Android and macOS build
  profiles and build tags; the root `direct` and `indirect` markers are not
  substituted for that analysis.
- Every selected module receives source-integrity, license/notice, generated
  or native-code, and SBOM treatment. Every production-reachable package also
  receives two-pass behavior review for networking, resolution, TLS/DTLS,
  logging, callbacks, concurrency, resource bounds, and shutdown.
- Review and later build preparation use no ambient network or dependency
  resolution. Any future network acquisition is separately bounded and leaves
  no authorization for compilation, loading, sockets, devices, or deployment.
- A final manifest is written last and independently read back against all
  exact inputs. Any mismatch leaves every closure flag false.

## Constraints And Non-Goals

The canonical G2 ladder requires dependency closure, license inventory, SPDX
SBOM, reproducible-source manifest, and patch policy before compile-only
integration. This proposal prepares a design for part of that work; it does
not complete rung three or rung four. Unmodified Pion ICE v4.3.0 remains
rejected as-is, and the restricted-fork shape remains a proposal rather than a
selected candidate.

We have no measured dependency source size, graph breadth, review duration,
latency, memory, battery, or build budget. A future acquisition decision must
therefore fix finite per-archive and aggregate byte, entry, path, compression,
and module-count limits before it opens any transfer. Reaching a limit is a
terminal stop for that decision version, not a reason to expand the bound in
place.

This proposal has the following non-goals:

- no candidate or library selection;
- no dependency source acquisition, network, DNS, redirect, authentication,
  credential, package-manager, compiler, loader, socket, or device action;
- no patch implementation or claim that resolver or TURN TLS findings are
  fixed;
- no runtime, platform, ABI, sanitizer, fuzz, performance, or interoperability
  evidence;
- no legal conclusion from a license filename or SPDX identifier alone;
- no request for repository-owner authentication, external identity proof,
  execution-permit authentication, approval receipt, or user action; and
- no change to product endpoint authentication or session cryptography.

## Before Architecture

The [before architecture](../diagrams/fixed-point-dependency-closure-before.mmd)
shows the current asymmetry: the root archive reaches semantic review, while
the root dependency metadata terminates at an inventory with unknown source,
license, resolver, and TURN behavior. The dashed edge is important. It is
evidence of missing source binding, not an assertion that a particular
dependency is vulnerable.

## Options

### Option 1: Single-Wave Inventory Review

Option 1 preserves the smallest possible next scope. A future, separate
technical decision would allowlist only the 19 root requirement tuples, set
finite intake bounds, and acquire and review those exact sources in one
immutable wave. The four checksum-only tuples would remain quarantined as
context. Any transitive tuple discovered in the acquired `go.mod` bodies would
be recorded as unresolved and deferred to another decision.

The attractive part of this option is its inspectability. We can know the
maximum seed count before the wave begins, contain a failure to a small source
set, and gain useful resolver, TURN, DTLS, transport, logging, and concurrency
information sooner. It does not require us to solve graph expansion mechanics
before learning from the first source set.

That same boundary is the principal security limitation. The wave can review
all 19 roots correctly and still end before the selected module graph is
known. It cannot produce a complete source manifest, license inventory, or
SBOM for the selected build. Repeating the option ad hoc would also create a
drift risk: later waves might use different limits or provenance rules unless
each is independently versioned.

There is no runtime performance cost in this proposal because no dependency
code runs. The future analysis cost is proportional to the first-wave source
size, and storage is bounded to one source set. Reliability is relatively
simple—one mismatch stops the wave—but availability of the review process is
lower when a newly discovered tuple necessarily sends the work back to a
decision boundary. Rollback is correspondingly narrow: discard or quarantine
the failed staging area, preserve the failure receipt and input decision, and
leave repository source and closure flags unchanged.

The [Option 1 after
architecture](../diagrams/fixed-point-dependency-closure-single-wave-inventory-review-after.mmd)
keeps the new-tuple edge explicitly unresolved. It improves first-wave
visibility without representing a fixed point.

| Change | Before | After | Security consequence | Cost |
| --- | --- | --- | --- | --- |
| Seed ownership | 19 requirements embedded in inventory-only root metadata | One exact 19-tuple allowlist | Prevents ambient additions to the first wave | Requires a separate bounded decision artifact |
| Checksum-only handling | Four extra tuples are mixed into the 44-record checksum file | Four tuples are explicitly quarantined as context | Prevents checksum presence from being mistaken for selection | Adds a small reconciliation ledger |
| Source evidence | No retained dependency source | Exact source for the one allowed wave, if a later decision succeeds | Narrows unknown behavior for reviewed tuples | Source storage and review time are unknown and must be bounded |
| Graph expansion | Unknown | Newly observed tuples are recorded but not acquired | Fails closed instead of silently expanding scope | Cannot complete the graph in the same decision |
| License and behavior review | Absent | Per-wave source, license, and behavior review | Can identify first-wave blockers | Cannot support complete SBOM or closure |
| Failure recovery | No dependency workflow exists | Preserve receipt; quarantine failed staging; issue a new version | Avoids overwrite and automatic retry | More decision turnover for ordinary transitive expansion |

Option 1 is strongest as an information-gathering slice. It is not a cheaper
way to assert closure; closure remains unavailable by design.

### Option 2: Staged Fixed-Point Source Closure

Option 2 turns graph expansion into an explicit state machine. The first
version begins from the same exact 19-tuple seed and quarantines the same four
checksum-only tuples. A future acquisition decision allows only that wave.
After integrity and provenance checks, retained `go.mod` bodies are parsed into
an exact edge set. If graph resolution discovers a selected tuple that lacks a
source binding, the current version stops. A new decision version binds the
expanded allowlist and repeats the bounded wave. No decision expands itself.

Once an independent graph recomputation reports zero new selected tuples, the
source review can operate over one immutable fixed-point snapshot. We would
then classify packages against the exact Android and macOS build profiles,
review every selected module for source integrity, license/notice, generated
or native code, and SBOM identity, and review every production-reachable source
body for the restricted profile’s behavioral invariants. Two independent
GPT-5.6 Sol passes would share the immutable snapshot; disagreement remains
`unresolved` rather than being averaged away. A source manifest, SPDX 2.3
SBOM, license inventory, and classifications/result set would be committed
before a manifest-last independent readback.

This option has the strongest case because it makes incompleteness observable.
New tuples, version changes, missing sources, and unknown directives are
version transitions rather than side effects. It also supplies the right
evidence boundary for the resolver and TURN findings: we can map the root call
paths to exact dependency behavior without claiming that source review itself
implements the required root controls.

What gives me pause is the operational surface. Multiple immutable waves mean
more retained archives, manifests, failure receipts, and review state. Source
bytes and graph breadth are not yet measured, so memory and storage cost remain
unknown until the decision fixes limits. The process may also stop frequently
on normal transitive discovery. Those stops are a deliberate reliability
property for evidence integrity, but they increase calendar time and tooling
complexity.

The runtime application still receives no performance or availability change
because this proposal implements nothing. Future review tooling should stream
bounded archive inspection and retain compact indexes rather than loading an
unbounded graph or every source body simultaneously. Rollback is evidence-safe:
a failed wave cannot modify a predecessor decision, and no repository
dependency or patch is introduced. We retain the failure, remove or quarantine
only its dedicated staging area under that future decision’s rollback rule,
and start a new version if the technical preconditions can be satisfied.

The [Option 2 after
architecture](../diagrams/fixed-point-dependency-closure-staged-fixed-point-source-closure-after.mmd)
shows the key containment edge: a new tuple goes to a new versioned decision,
while only a zero-new-tuple result proceeds to source review and manifest
readback.

| Change | Before | After | Security consequence | Cost |
| --- | --- | --- | --- | --- |
| Scope authority | Root metadata has no dependency source authority | Every tuple appears in an immutable versioned allowlist | Removes ambient graph expansion from the trusted path | Requires versioned state and strict supersession rules |
| Graph completion | 19 requirements and 44 checksum records are treated as inventory only | Selected vertices and edges expand in bounded waves until zero new tuples | Makes fixed-point completeness falsifiable | Multiple acquisition/review waves may be required |
| Checksum-only context | Four tuples can be visually confused with requirements | Context quarantine never enters the selected graph without edge evidence | Prevents stale checksum rows from inflating the SBOM | Requires independent reconciliation on every version |
| Source and provenance | Dependency source is absent | Each selected vertex binds provenance, archive/source digest, tree digest, and `go.mod` | Detects source substitution and version ambiguity before review | Additional storage, hashing, and provenance work |
| Semantic coverage | Root-only semantic review | Two-pass build-profile-aware review over every production-reachable selected package | Narrows dependency behavior uncertainty without conflating it with patch completion | Higher review effort and source classification complexity |
| Supply-chain outputs | No dependency license conclusion, SBOM, or complete manifest | License inventory, SPDX 2.3 SBOM, source manifest, and manifest-last readback | Creates auditable inputs for a later closure decision | More artifacts and independent checker maintenance |
| Failure recovery | No fixed dependency workflow | Stop per wave, preserve receipt, never overwrite or auto-retry | Contains drift and makes failure history reviewable | Slower progress when upstream metadata is incomplete |

Option 2 gives us a credible route to evidence that could later support a
closure decision. It does not itself make the closure decision, and even a
complete dependency result would leave the root patch findings and later G2
rungs open.

## Comparison

The comparison below intentionally has no composite score. No runtime
benchmark was performed, and source volume is unknown. Directions describe the
expected effect of the proposed review architecture, not measured product
behavior.

| Dimension | Option 1: Single-wave inventory review | Option 2: Staged fixed-point source closure | Confidence and basis | Validation plan |
| --- | --- | --- | --- | --- |
| Security | Improves visibility for exactly 19 seed tuples but leaves transitive behavior and graph completeness unresolved | Improves control ownership by requiring every selected tuple and edge to be version-bound before full review | High, source-derived from the inventory/finding mismatch | Mutate seeds, checksums, edges, and versions; require deterministic stop and false closure flags |
| Performance | Neutral to product runtime; one future review wave minimizes analysis I/O | Neutral to product runtime; repeated waves add analysis hashing, parsing, and readback I/O | Medium, hypothetical because no source acquisition or benchmark occurred | Measure wall time and bytes read per wave against predeclared limits; runtime threshold is no product code execution |
| Memory | Bounded to one seed-wave index and source stream | Potentially higher aggregate metadata and retained-source footprint, while per-wave memory can remain bounded | Low, hypothetical until graph/source sizes are known | Record peak RSS, retained bytes, entry count, and maximum in-memory source body; stop at the decision limits |
| Reliability | Simple single-wave failure containment, but ordinary new tuples force an unresolved handoff | Strong evidence isolation and deterministic per-wave failure, with more state transitions that can fail | Medium, analogous to the existing immutable rung decisions | Inject missing archives, hash drift, duplicate tuples, interrupted publication, and newly discovered edges; require no overwrite or retry |
| Operability | Fewer artifacts and a smaller checker, but repeated manual interpretation risks drift | More manifests, receipts, graph versions, license/SBOM rows, and checker rules; provenance is clearer | Medium, source-derived for artifact count and hypothetical for maintenance load | Count artifacts and unresolved states per wave; rehearse independent readback and stale-version rejection |
| Migration | Easiest way to begin a bounded source review, but cannot transition directly to closure | Longer preparation path, but every wave can be adopted and rolled back without changing repository dependencies | High, source-derived from the no-implementation boundary | Start from the exact seed fixture, exercise expansion and rollback, and prove repository source and selection flags remain unchanged |

Option 1 wins when bounded first-wave learning is the only approved objective.
Option 2 wins when the objective is a review process capable of reaching and
proving a fixed point. Neither option wins if its finite limits, provenance,
and failure policy are unresolved.

## Recommendation

Under the current G2 requirement that the complete module graph be vendorable
without network dependency resolution during build, I conditionally recommend
Option 2. It aligns the dependency trust boundary with the existing versioned,
fail-closed authority ladder and gives the independent checker a concrete
property to validate: every selected tuple and edge belongs to one immutable
fixed-point snapshot.

The recommendation is conditional, not a selection. Before Option 2 could be
chosen, a local technical decision must specify exact source-provenance
mechanisms, finite resource limits, module-graph semantics, build profiles, and
failure cleanup. The recommendation should change to Option 1 if the approved
scope is explicitly limited to first-wave information gathering, or to no
acquisition if exact provenance or safe bounds cannot be established.

No external authentication or user action is a prerequisite. An authentication
challenge, credential requirement, or identity-proof dependency is a stop
condition, not a prompt to broaden authority.

## Evidence Coverage And Residual Risk

The effects below describe what each option could address if later selected,
implemented, and validated. They do not update the canonical dispositions.

| Evidence | Option 1 effect | Option 2 effect | Tactical work still required |
| --- | --- | --- | --- |
| `G2SR1-F-65bdab86ddd0720af770` — Dependency source closure is missing | Mitigates uncertainty for the exact first wave; fixed-point completeness remains unknown | Addresses the structural discovery/ownership gap if every wave, source review, license/SBOM record, and readback succeeds | A separate dependency result and closure decision; no flag changes from this proposal |
| `G2SR1-F-7e744b8ee19e7de9b7c3` — Resolution behavior remains dependency-unresolved | Unknown beyond first-wave sources | Mitigates the dependency-behavior unknown for production-reachable resolver paths | Inject bounded caller-supplied answers with provenance and revalidate immediately before use |
| `G2SR1-F-7d678ddf77ac89e04ae4` — TURN TLS service identity is not exact | Unknown beyond first-wave TLS/DTLS sources | Mitigates dependency-behavior uncertainty but does not change `patch_required` | Remove verification bypasses and require exact trust, SNI/host, pin, expiry, and deadline inputs before credentials |
| `G2SR1-F-c9dd2e9b3fa55e3ad43b` — Lexical hits are not vulnerability counts | Mitigates first-wave counting ambiguity through explicit per-observation disposition | Mitigates counting ambiguity across the fixed-point snapshot through the same per-observation rule | Keep every lexical hit unresolved until an exact semantic disposition is recorded |
| Remaining 16 canonical findings — Root source behavior and missing mechanisms | Unaffected | Unaffected | Preserve all existing `patch_required` and `unresolved` dispositions for the separate patch workstream |

Residual risk remains even after a successful future dependency review:

- A source-complete graph does not prove that the selected build uses the
  intended packages until the later exact toolchain and build-profile evidence
  exists.
- Source and license review can become stale when a module version, root
  `go.mod`, root `go.sum`, build tag, toolchain, patch series, or source byte
  changes; any such drift requires a new version.
- SPDX records and license identifiers do not by themselves establish legal
  compatibility or maintenance quality.
- Static review cannot prove runtime TLS identity, resolver admission,
  cancellation, resource bounds, or shutdown behavior.
- Dependency review does not implement the seven required root patch units,
  select a reliable ordered carrier, or authorize compile, socket, network,
  device, or controlled-network evidence.
- The independent readback can validate artifact identity and declared
  relationships, but it cannot independently reproduce every semantic
  judgment unless a separate review does so.

## Migration And Rollout

Because no option is selected, this is a prospective evidence migration rather
than a source-code rollout. We can preserve every current artifact and add only
new versioned records if a later decision opens the work.

| Phase | Prospective transition | Required stop rule | Rollback posture |
| --- | --- | --- | --- |
| `DC-P0` | Bind G2PD001/002/003/006, result-v3, archive/tree, `go.mod`, and `go.sum` hashes into a preparation-only decision | Stop on any byte/hash/count drift or if a predecessor failure/permit is reused | Publish nothing; preserve current false flags |
| `DC-P1` | Normalize the 19-tuple seed and four-tuple checksum-only quarantine | Stop on duplicates, malformed paths/versions, missing checksum pairs, unknown directives, or any attempt to call context tuples selected | Discard the derived draft; do not alter root evidence |
| `DC-P2` | Prepare a separate future source-identity and acquisition decision with exact allowlist and finite limits | Stop if provenance, limits, rollback, or no-overwrite semantics are incomplete; stop if authentication or user action would be required | Keep acquisition closed |
| `DC-P3` | Under that later decision only, perform one immutable source wave and verify archive, path, checksum, provenance, and license-file inventory | Stop without automatic retry on redirect/domain drift, TLS/provenance failure, checksum mismatch, traversal/link anomaly, collision, or limit breach | Quarantine or remove only the dedicated future staging area as predeclared; retain failure evidence |
| `DC-P4` | Recompute graph edges from retained metadata | Every new selected tuple stops the current version and requires a new decision; unknown graph semantics remain unresolved | Preserve the completed prior wave; do not acquire the new tuple |
| `DC-P5` | At zero-new-tuple fixed point, run two independent source/build-profile reviews and create license, SBOM, and source manifests | Stop on incomplete source coverage, pass disagreement, unknown license, generated/native-code ambiguity, reachability ambiguity, or security blocker | Retain unresolved classifications and keep closure false |
| `DC-P6` | Publish result set, then manifest last, then independent tracked-only readback | Stop on any mismatch, staging residue, missing artifact, unstable readback, or checker disagreement | Do not publish a success state; preserve failure receipt |

Option 1 ends intentionally after `DC-P3` plus a first-wave review and records
any new tuple as unresolved. Option 2 repeats `DC-P2` through `DC-P4` under new
versions until the fixed-point precondition for `DC-P5` is met. Neither path
changes product binaries or repository dependencies, so rollback never depends
on a runtime downgrade.

## Validation Plan

Validation must distinguish evidence identity, graph completeness, review
coverage, and security acceptance. A later implementation should use the
following exact checks:

| Validation area | Workload and metric | Acceptance threshold |
| --- | --- | --- |
| Root identity | Rehash the bound archive, source tree, `go.mod`, `go.sum`, semantic classifications, result, and manifest | Every digest and byte/count field exactly matches this decision version |
| Seed reconciliation | Independently parse root metadata and compare module/version rows and checksum kinds | Exactly 19 required tuples: 10 direct and 9 indirect; exactly 44 checksum records; exactly four named checksum-only context tuples; every required tuple has one source and one `go.mod` checksum |
| Scope mutation | Add, remove, duplicate, or change a tuple, checksum, version, directive, or context classification in fixtures | Deterministic failure before acquisition or review; no closure or selection flag becomes true |
| Future intake safety | Exercise redirect, authentication challenge, checksum mismatch, traversal, link, collision, compression, entry, path, and byte-limit fixtures | Every invalid case stops without credential request, overwrite, automatic retry, source execution, or network-scope expansion |
| Graph fixed point | Independently recompute all selected vertices and edges from the immutable retained metadata after each wave | `newSelectedTupleCount=0`, no unknown vertex or edge, and identical graph digest from both computations |
| Build-profile classification | Resolve production, test, example, generated, native, and excluded packages for the exact declared Android/macOS profiles | Every retained source file has one reproducible class; ambiguity is unresolved and blocks progression |
| Semantic source coverage | Two independent GPT-5.6 Sol passes over one immutable snapshot | Every selected module receives supply-chain review; every production-reachable source body receives both behavior passes; disagreement remains unresolved |
| License and SBOM | Cross-check source manifest, license/notice inventory, SPDX 2.3 rows, graph vertices, and provenance | One exact row per selected vertex with no unknown or orphan record; legal compatibility remains a separate recorded decision |
| Resource behavior | Measure review wall time, bytes read, entry count, retained bytes, and peak RSS per wave | Each metric remains within the predeclared decision limit; exceeding a limit stops the version |
| Publication | Mutate, omit, reorder, replace, or stage each output and run manifest-last independent readback | Every mutation fails; stable unmodified inputs pass two complete readback passes with no staging/failure residue |
| Non-claims | Inspect every result and handoff flag | `candidateSelected=false`, `librarySelected=false`, `semanticClosureComplete=false`, `rungThreeComplete=false`; dependency flags remain false until a separate validated closure decision |

No validation command in this proposal is authorized for execution. The table
defines acceptance behavior for a later selected design and bounded technical
decision.

## Implementation Work Packages

These packages are an implementation handoff outline only. They neither select
an option nor create an `implementation/` artifact.

| Work package | Scope | Exit evidence | Hard stop |
| --- | --- | --- | --- |
| `WP-DC1 — Evidence and seed binder` | Bind exact evidence hashes; emit the 19 required rows and four checksum-only context rows without network or source writes | Deterministic seed and context digests plus mutation tests | Any mismatch with bound root metadata |
| `WP-DC2 — Versioned source-intake decision` | Define tuple allowlist, provenance, finite resource limits, no-follow/no-overwrite handling, failure receipt, and cleanup boundary | Preparation-only decision with every operational authority false | Missing provenance/limit/rollback field, auth requirement, or user action |
| `WP-DC3 — Bounded immutable intake` | Implement the separately authorized future per-wave transfer and archive verification path | Per-tuple receipt with exact hashes, sizes, paths, and provenance | Redirect drift, mismatch, unsafe archive entry, collision, or limit breach |
| `WP-DC4 — Fixed-point graph resolver` | Parse retained module metadata, preserve all edges, quarantine checksum-only context, and compute a canonical graph digest | Two independent equal graph digests and zero new selected tuples | Any unknown directive, vertex, edge, or new tuple |
| `WP-DC5 — Dependency review adapter` | Classify source by build profile and run two independent security/supply-chain passes on one immutable snapshot | Complete pass records with disagreements unresolved | Missing body, ambiguous reachability, unreviewed native/generated code, or pass incompleteness |
| `WP-DC6 — License, SBOM, and source manifest` | Bind one source/provenance/license/SBOM record to every selected graph vertex | Cross-consistent SPDX 2.3 SBOM, license inventory, and source manifest | Unknown/orphan row, incompatible policy result, or graph drift |
| `WP-DC7 — Result publication and checker` | Publish classifications/result before manifest-last marker and independently read back exact files and non-claims | Mutation-tested checker and stable complete readback | Any unstable read, staging residue, unexpected file, semantic disagreement represented as closure, or selection overclaim |

The packages intentionally keep acquisition, review, and closure decisions
separate. If Option 1 is later chosen, work ends after a bounded form of
`WP-DC3` and first-wave review. If Option 2 is later chosen, `WP-DC2` through
`WP-DC4` repeat under new immutable versions before `WP-DC5` can begin.

## Open Questions

- What exact official provenance and module-artifact identity mechanism can be
  fixed for each of the 19 seed tuples without authentication or credentials?
- What finite per-archive and aggregate byte, entry, path, compression, module,
  source-file, and review-time limits are safe before the first future wave?
- Which exact Android and macOS Go build tags, standard-library surface, and
  toolchain revision define production reachability for the dependency review?
- Which module-graph semantics and canonicalization will be implemented and
  independently recomputed without ambient network resolution?
- Must checksum-only context rows remain permanently quarantined, or may a
  later exact graph edge promote one under a new versioned decision?
- What recorded policy determines license compatibility, generated-source
  acceptability, cgo/assembly treatment, advisory status, and maintenance
  ownership without treating metadata as a legal or security conclusion?
- Which dependency behavior findings are resolvable by source evidence, and
  which must remain linked to the seven root patch units until post-patch
  semantic review?
- What evidence would justify changing the conditional recommendation to the
  single-wave option or to no acquisition at all?

Until these questions are answered by local technical artifacts, the bounded
state is unchanged: no dependency source is acquired or reviewed, no finding
is closed, no option is selected or implemented, and Pion remains unselected.
