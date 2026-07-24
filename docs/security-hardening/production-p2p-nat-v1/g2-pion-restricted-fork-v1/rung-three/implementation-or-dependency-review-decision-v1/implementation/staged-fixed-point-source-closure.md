# Implementation Plan: Staged Fixed-Point Dependency Source Closure

<!-- aetherlink-decision-summary:v1
status=dependency_review_selected_acquisition_not_authorized
result=staged_fixed_point_dependency_review_selected_all_19_findings_remain_open
decisionLane=dependency_review_selection
selectedPortfolioOption=staged-fixed-point-source-closure
selectedTreatmentUnit=dependency_source_license_security_closure_review
selectedPortfolioOptionCount=1
unselectedPortfolioOptionCount=7
selectedTreatmentUnitCount=1
unselectedRootPatchUnitCount=7
findingsClosedBySelection=0
dependencyAcquisitionAuthorized=false
sourceModificationAuthorized=false
networkAuthorized=false
gitWriteAuthorized=false
externalAuthenticationRequired=false
userActionRequired=false
dependencyClosureComplete=false
candidateSelected=false
librarySelected=false
nextAction=prepare_separate_versioned_bounded_dependency_source_identity_and_acquisition_decision
-->

## Selected Design And Constraints

We selected the dependency-review lane before restricted-fork implementation.
The selected portfolio option is `staged-fixed-point-source-closure`, and the
selected treatment unit is
`dependency_source_license_security_closure_review`. The three recommended root
architecture options and all seven root patch units remain deferred rather than
implicitly selected.

This order is deliberate. The retained root metadata identifies 19 requirements
and 44 checksum records, but it does not prove the complete production-reachable
graph. Resolver, TURN, logging, queue, shutdown, native-code, and initialization
behavior owned by dependencies can change the restricted-fork boundary or reject
the candidate before a root patch is worth implementing. We therefore close the
dependency evidence first and return to a separate root implementation decision
only if the fixed graph remains acceptable.

This plan grants no source modification, source extraction, dependency
acquisition, package-manager, compiler, source load, source execution, socket,
network, device, deployment, or Git-write authority. It requires no repository
identity proof, external authentication, signature, execution permit, or user
action. Product endpoint authentication remains a later runtime invariant and is
not satisfied by this plan.

All 19 canonical findings remain open. Selection of a review lane is not semantic
closure, dependency closure, rung-three completion, candidate selection, or
library selection.

## Source Revision And Drift Check

The plan is bound to:

- Pion ICE `v4.3.0`, upstream commit
  `1e8716372f2bb52e45bf2a7172e4fb1004251c46`;
- retained archive SHA-256
  `f95ef3ce2e0063c13925f478bf8d188833725b2f0a7ecb1e695dee8ab61ef63c`;
- bounded source-tree SHA-256
  `b44b1277937432822d005632dc0ac77b0c733959c871d998fac5e3964ce39244`;
- root `go.mod` SHA-256
  `5044428710b5a718aad517eed5c08e1933378efa3d9b4245853cfb312560aca4`;
- root `go.sum` SHA-256
  `b47d7d5f3bb8c8b85b3283585f97ea6bd0a8b97427b49068b9f5685ddd953887`;
- the immutable patch/dependency preparation decision and its complete
  19-file hardening portfolio.

Before each later work package, the runner must independently re-read these
bytes and the latest dependency decision. Any mismatch, replacement, symlink,
unexpected file, graph tuple, build profile, or selected version stops that
package. A changed source or graph requires a new versioned decision; it must not
be repaired by editing this plan or a prior receipt.

## Affected Components

This selected lane affects review artifacts only:

- versioned dependency source-identity and acquisition decisions;
- bounded immutable source archives and their provenance records;
- exact module graph and production-reachability manifests;
- two independent semantic review records;
- license notices and compatibility decisions;
- an SPDX 2.3 SBOM;
- manifest-last publication and independent byte readback;
- the later root implementation selection decision.

It does not yet affect the retained Pion source, AetherLink source, build graphs,
runtime routing, relay fallback, Android, macOS, or production deployment.

## Ordered Work Packages

### WP1 — Freeze The Root Seed And Review Profiles

The next decision must bind the exact 19 root requirements, 44 checksum records,
23 module/version tuples, 21 source hashes, 23 `go.mod` hashes, and four
checksum-only context tuples. The context tuples remain unselected unless a
later fixed-point expansion proves them production-reachable.

That decision must also name the Android and macOS production build profiles,
Go version, build tags, target operating systems and architectures, cgo policy,
test/tool exclusion rules, replacement/exclude directives, and graph traversal
algorithm. No profile may be inferred after acquisition.

Exit criteria:

- the root seed byte-for-byte matches the predecessor;
- production reachability rules are explicit and deterministic;
- archive, file, entry, path, redirect, retry, timeout, and aggregate bounds are
  exact integers;
- provenance roots, TLS policy, no-proxy policy, no-credential policy,
  no-overwrite policy, and first-mismatch stop conditions are explicit;
- acquisition remains unexecuted until that separate decision passes.

### WP2 — Prepare The First Bounded Source-Identity Decision

The first wave decision names every selected module/version tuple and its
authoritative source endpoint, expected immutable identity, expected checksum
root, retained destination, and validation method. It must distinguish checksum
evidence from source identity and must not treat `go.sum` as a complete graph or
license receipt.

The decision must use one atomic, no-overwrite output set. Partial downloads,
redirects, proxy use, credentials, undeclared hosts, undeclared tuples, content
over a declared bound, and any digest or identity mismatch fail closed. Failure
evidence contains no credentials or raw sensitive transport material.

Exit criteria:

- every request and output is predeclared;
- the one bounded wave has an exact maximum request count;
- no package manager, compiler, source loader, or source executor is part of the
  acquisition runner;
- the decision names the next action but does not claim it occurred.

### WP3 — Acquire And Retain One Immutable Wave

Only a later versioned technical decision may execute this work package. The
runner consumes exactly its declared request set, validates transport and source
identity, retains exact regular-file bytes, and emits a manifest-last receipt.
It performs no source build, initialization, test, generator, hook, or executable
load.

The wave stops on the first undeclared redirect, request, response type, tuple,
file, path, archive entry, size, digest, signature state, or output collision.
Previously retained accepted bytes remain immutable; a retry requires a new
decision version rather than mutable continuation.

Exit criteria:

- every selected tuple has one retained source artifact and provenance record;
- observed bytes match the decision or are recorded as a closed failure;
- no unselected tuple is promoted;
- an independent reader reproduces the exact wave manifest from retained bytes.

### WP4 — Expand The Exact Graph To A Fixed Point

Each accepted wave is inspected without executing source. Its exact module
metadata is normalized under the frozen production profiles. Newly reachable
tuples become the input to a new versioned wave decision. Test-only, tool-only,
example-only, checksum-only, replaced, excluded, platform-specific, generated,
native, and vendored edges remain separately classified.

The loop reaches a fixed point only when a full deterministic pass discovers no
new selected tuple and the same graph digest is reproduced independently. A
single root `go.mod`, a single `go.sum`, one wave, or a dependency manager's
local cache is not fixed-point evidence.

Exit criteria:

- the selected graph is finite, ordered, and uniquely keyed by module and
  immutable version identity;
- every edge records its source metadata and production-reachability reason;
- all newly discovered selected tuples have completed their own bounded wave;
- two independent graph builders reproduce the exact node, edge, and graph
  digests.

### WP5 — Run Two-Pass Source, License, And Security Review

Two non-attesting passes review every production-reachable source body and
declared generated/native component. The passes cover license obligations,
initialization, network egress and ingress, resolver control, TURN/TLS identity,
redirects, proxies, diagnostics, secrets, queues, callbacks, resource ceilings,
shutdown, concurrency, randomness, cryptography, filesystem effects, process
effects, unsafe/cgo/assembly, generators, and build scripts.

Disagreements remain unresolved. Dependency behavior that cannot meet the
restricted profile rejects the candidate or requires a separately versioned
containment design; it is never silently assigned to a future root patch.

Exit criteria:

- coverage includes every selected graph node and production-reachable file;
- every observation maps to an exact source location and review invariant;
- every disagreement and missing mechanism is explicit;
- no unresolved P0/P1 or profile-blocking behavior remains;
- every accepted license is compatible with the intended distribution channel.

### WP6 — Publish SBOM, Source Manifest, And Independent Readback

The final dependency evidence includes an SPDX 2.3 SBOM, retained-source
manifest, provenance map, license inventory, finding disposition set, review
coverage, and graph digest over the same fixed graph. The publication manifest
is written last.

An independent read-only checker opens every expected regular file without
following symlinks, rejects missing or unexpected artifacts, verifies exact
sizes and SHA-256 digests, recomputes semantic cross-bindings, and retains file
and ancestor identities through its final readback.

Exit criteria:

- the SBOM, graph, source, license, review, and manifest node sets are identical;
- all required bytes are independently reproduced and read back;
- dependency closure is true only if every required acceptance criterion holds;
- a failed criterion leaves dependency closure false and records a bounded
  failure result.

### WP7 — Return To Root Implementation Selection

If dependency closure succeeds, a separate versioned decision revisits the
three deferred structural recommendations and seven root patch units against
the fixed dependency behavior. It may then select a coherent root design and
create implementation work packages. If the dependency review rejects the
candidate, no root implementation is opened.

Exit criteria:

- the dependency outcome and exact graph are immutable inputs;
- root architecture options are explicitly selected or rejected;
- source modification remains closed until that later implementation decision;
- the authenticated sealed relay remains the rollback path.

## Compatibility And Migration

No runtime compatibility change occurs in this lane. Existing local transport
and authenticated sealed-relay behavior remain unchanged. The dependency review
must describe module API, Go/toolchain, Android, macOS, cgo, native-code,
licensing, and distribution compatibility before any fork build is considered.

Graph or license incompatibility is a candidate rejection, not a reason to
weaken the frozen profile. If a later selected root design requires dependency
API adaptation, that change belongs to the separate root implementation
decision.

## Tactical Protections During Migration

- Keep direct P2P disabled and retain the authenticated sealed relay fallback.
- Preserve the three useful existing controls recorded by the semantic review;
  do not count them as closure.
- Keep all 19 findings open until their original paths are revalidated after
  implementation.
- Keep checksum-only context tuples unselected.
- Do not log module source URLs with credentials, transport secrets, raw
  certificates, or local filesystem paths in distributable artifacts.
- Do not run dependency source, generators, tests, hooks, build scripts, or
  initialization during intake and review.
- Stop on the first provenance, graph, license, source, bound, or semantic
  mismatch.

## Tests And Security Validation

Every decision and result checker must include at least:

- strict UTF-8 JSON parsing, duplicate-key rejection, finite-number rejection,
  exact schemas, and self-bindings;
- predecessor, archive, root metadata, graph, source, license, SBOM, and
  manifest byte-drift mutations;
- missing, added, reordered, duplicate, replaced, checksum-only, and
  profile-specific tuple mutations;
- redirect, proxy, credential, retry, request-count, host, size, path, archive,
  symlink, no-overwrite, and partial-output mutations;
- graph non-convergence, hidden edge, build-profile drift, and SBOM/source-set
  mismatch mutations;
- review coverage, disagreement, severity, disposition, location, license, and
  closure-overclaim mutations;
- authority escalation, implicit root-option selection, candidate/library
  selection, external-authentication, and user-action mutations;
- replace-after-read and unexpected-artifact mutations.

Passing these tests proves only the bounded artifact contract that each checker
actually evaluates. It does not prove production network behavior, runtime
correctness, physical-device behavior, or release readiness.

## Performance And Resource Benchmarks

No latency, memory, storage, battery, or network measurement is claimed here.
Before acquisition, the next decision freezes deterministic limits for request
count, compressed bytes, expanded bytes, file count, individual file size, path
length, duration, retained storage, and graph size.

The review runner later records observed values against those limits without
executing source. Any future compiled restricted fork must separately benchmark
packet-path latency, allocation rate, aggregate memory, worker count, queue
depth, shutdown duration, battery impact, and relay fallback. Those runtime
benchmarks do not belong to dependency intake evidence.

## Rollout And Rollback

The review lane rolls out as immutable, individually verifiable work packages.
Each package consumes only the preceding accepted artifact set. A package may
stop without changing runtime or source state.

Rollback means abandoning an unaccepted staging set while retaining its
versioned decision and bounded failure evidence. Accepted predecessor artifacts
are never rewritten. No dependency result activates P2P, modifies the runtime,
selects Pion, or removes relay fallback.

## Acceptance Criteria

- Exactly one lane, `dependency_review_selection`, is selected.
- Exactly one portfolio option, `staged-fixed-point-source-closure`, is selected.
- Exactly one treatment unit,
  `dependency_source_license_security_closure_review`, is selected.
- All three root structural recommendations and seven root patch units remain
  deferred.
- The implementation handoff and decision bind the exact predecessor portfolio,
  source snapshot, 19 findings, and root metadata.
- All operational authority remains false.
- All 19 findings remain open and every completion/selection flag other than the
  review-lane selection remains false.
- The next bounded action is a separate versioned source-identity and acquisition
  decision; no acquisition occurs in this plan.
- No external authentication or user action is required.

## Open Decisions

The next bounded decision, prepared autonomously from current evidence, must
freeze:

- exact production build profiles and graph traversal semantics;
- the first wave's selected tuple set and authoritative source identities;
- per-request, per-artifact, per-file, per-wave, duration, and retained-storage
  limits;
- redirect, proxy, TLS, signature/checksum, retry, and failure policies;
- cgo, assembly, generated-source, vendored-source, and build-script treatment;
- the precise independent readback and failure-artifact contract.

These are technical fields for the next versioned artifact, not requests for
owner identity, external authentication, or user input.
