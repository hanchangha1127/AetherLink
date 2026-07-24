# AetherLink Session Handoff

Last updated: 2026-07-24 KST.

This is the canonical first document for the next Codex session. Read it before
editing, staging, rebuilding, or making claims from older QA logs. It describes
the active personal-project governance, current V1 worktree state, the still-
valid macOS QR recovery and physical Android proof, the remaining proof
boundaries, and the shortest path to resume work.

## Contents

- [Current truth versus historical evidence](#current-truth-versus-historical-evidence)
- [Active personal-project governance](#active-personal-project-governance)
- [Current handoff snapshot](#current-handoff-snapshot)
- [First five minutes](#first-five-minutes)
- [V1 G0 execution status](#v1-g0-execution-status)
- [Current verified outcome](#current-verified-outcome)
- [Root causes and final design](#root-causes-and-final-design)
- [UI callback wiring matrix](#ui-callback-wiring-matrix)
- [QR recovery file map](#qr-recovery-file-map)
- [Published G0 packet and receipt/input map](#published-g0-packet-and-receiptinput-candidate-map)
- [Evidence ledger](#evidence-ledger)
- [Debug and Release evidence matrix](#debug-and-release-evidence-matrix)
- [Focused verification commands](#focused-verification-commands)
- [Physical device procedure](#physical-device-procedure-for-a-future-session)
- [Not yet proven](#not-yet-proven)
- [Authority and security boundary](#authority-and-security-boundary)
- [Recommended next session flow](#recommended-next-session-flow)
- [Handoff maintenance rule](#handoff-maintenance-rule)

## Active Personal-Project Governance

Owner identity authentication is not required for this personal project. Direct
user instruction is sufficient for repository reads, edits, builds, tests, and
G1a no-network implementation. Do not ask the user for SSH/GPG proof, fourteen
role approvals, an owner trusted timestamp, an external owner-governance ledger,
or any equivalent owner-authentication evidence.

The published G0 lineage and owner-trust profiles are historical enterprise-
assurance artifacts. Preserve their bytes and integrity tests, but do not treat
their owner-authentication, receipt, or `blocked_before_g1a` state as an active
work prerequisite. Product security and authentication are separate and remain mandatory:
QR pairing, paired-device challenge/response, endpoint encryption, replay and
downgrade protection, pair-epoch recovery, revocation, and route capabilities.
Sockets, external-network execution, production signing, store upload, and
deployment remain distinct technical scopes governed by current user direction,
not repository-owner identity proof.

## Current Truth Versus Historical Evidence

- This file is the current continuation contract. Its snapshot, behavior,
  evidence matrix, proof boundaries, and next-session flow take precedence over
  older chronological entries in `docs/progress.md`, `docs/qa-evidence.md`, and
  `docs/roadmap.md`.
- The top 2026-07-24 sections in those three documents are synchronized current
  summaries. Sections explicitly labeled historical or superseded record what
  was true at that checkpoint; they do not override this handoff.
- `docs/evidence/physical-qr-pairing-20260719.json` is a sanitized observation
  manifest. It preserves safe test metadata and claim boundaries, but it is not
  a substitute for the discarded raw logcat stream, full QR payload, or a fresh
  run from the current checkout.
- Runtime process, listener, IP address, attached-device, and worktree state are
  inherently live facts. Refresh them before use even when this document names
  the last observed value.
- The continuity marker `Android device state at handoff: disconnected` matches
  the latest `adb devices -l` refresh. The completed connected-device
  observation below is retained as bounded debug evidence, not as a current
  attachment claim, and must be rerun before any future live-device claim.

### Current G2 Rung-Three Dependency Wave-One Acquisition And Readback

Rung two consumed its one-use acquisition request. Rung-three v1 and v2 later
consumed their distinct permits and failed closed before publication; preserve
those histories and do not retry either path. The separate v3 one-use execution
completed bounded lexical candidate inventory and independent tracked readback.
That predecessor recorded `rung3_v3_publication_read_back_complete` and
`prepare_separate_versioned_rung3_semantic_source_review_decision` at its
checkpoint. The tracked
[semantic-review decision v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/semantic-source-review-decision-v1.json)
is now historical execution authority. The current
[classifications](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/semantic-source-review-classifications-v1.json),
[result](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/semantic-source-review-result-v1.json),
and atomic [manifest](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/semantic-source-review-manifest-v1.json)
historically record
`status=rung3_semantic_source_review_v1_publication_read_back_complete_semantic_closure_blocked`,
`result=two_non_attesting_full_coverage_semantic_passes_published_and_independently_read_back_patch_and_dependency_gaps_remain`,
and
`recordedNextActionAtThatCheckpoint=prepare_versioned_rung3_patch_and_dependency_closure_decision`.

The tracked [result-v3](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/offline-source-review-result-v3.json),
[runtime-manifest-v3](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/offline-source-review-runtime-manifest-v3.json),
and [execution-receipt-v3](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/offline-source-review-execution-receipt-v3.json)
bind exact readback. Result-v3 is 76,685 bytes at
`ef4b8d88ec57501377a7bc9db066c04a1a379041ee1b11999f5d16c7d4447933`;
the manifest is 2,458 bytes at
`2dace9b59b7374423754f1f9a7345eda76db9130728d1c0579797e5a0c829055`.
The inventory covers 100 Go files, 1,077,591 bytes, 39,064 logical lines, and
4,701 hits as 144 representatives, at most eight per rule, plus 4,557 omissions
across seven patch units and 19 rules. All 129 entries have creator system 0,
DOS attributes `00`, and synthetic mode `100444`.

Semantic-review v1 completed two non-attesting full-coverage passes over all
100 Go files and all 4,701 observations. The 29 candidates deduplicate to 19
findings: P0=0, P1=11, P2=3, P3=4, none=1; patch_required=7 and unresolved=12.
The `one-use` zero-hit remains a missing-required-mechanism gap. The independent
tracked-only post-run checker and 25/25 mutation tests hold all eight file
descriptors plus every repository-path directory component through two stable
full-set readback passes and a final identity barrier, validate the manifest
last, and observe the failure file plus four staging names absent before and
after readback. Semantic review was
performed, but semantic closure, dependency closure, rung-three completion,
candidate selection, and library selection remain false. The checker does not
independently reproduce semantic judgments or source-based location bounds.
Same-UID concurrent mutation is not prevented, and absence is not guaranteed
after the final observation. No extraction, materialization, dependency
install, source compile/execution, socket, network, device, deployment, or Git
operation occurred. No repository-owner authentication, external identity
proof, execution-permit authentication
or document, or user action is required.

The historical preparation-only
[patch/dependency decision v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/patch-and-dependency-closure-decision-v1.json)
and [security-hardening portfolio](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/patch-and-dependency-closure-decision-v1/hardening.md)
record `status=prepared_options_unselected_dependency_closure_blocked`,
`result=four_structural_recommendations_and_eight_unselected_treatment_units_prepared_all_19_findings_remain_open`,
and
`recordedNextActionAtThatCheckpoint=prepare_separate_versioned_implementation_or_dependency_review_decision`.
They map all 19 canonical findings to seven unselected root patch units and one
unselected dependency-review unit. The read-only checker and 28/28 checker
tests bind the predecessor artifacts, retained archive, root dependency seed,
complete 19-file portfolio, and all-false authority and closure boundary; they
also reject unexpected artifacts, reader-facing effect drift, and
replace-after-read drift. Recommendations are not selections; no implementation
plan or patch series exists. Source change, dependency acquisition, compiler,
socket, network, device, deployment, and Git write remain unauthorized. Neither
external authentication nor user action is authorized or required.

The predecessor
[implementation-or-dependency review decision v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/implementation-or-dependency-review-decision-v1.json)
and
[staged fixed-point review plan](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/implementation-or-dependency-review-decision-v1/implementation/staged-fixed-point-source-closure.md)
recorded at that checkpoint
`status=dependency_review_selected_acquisition_not_authorized`,
`result=staged_fixed_point_dependency_review_selected_all_19_findings_remain_open`,
and
`recordedNextActionAtThatCheckpoint=prepare_separate_versioned_bounded_dependency_source_identity_and_acquisition_decision`.
Exactly one portfolio option, `staged-fixed-point-source-closure`, and one
treatment unit, `dependency_source_license_security_closure_review`, are
selected for the dependency-review plan. The other seven portfolio options,
all seven root patch units, and the other three structural recommendations
remain unselected. The isolated read-only checker and 36/36 checker tests bind
the exact predecessor, semantic triad, retained archive and root metadata,
complete 19-file portfolio bundle, and review plan, including distinct raw,
selection, authority, finding, closure, contract, sequence, plan, inventory,
filesystem, and TOCTOU failure layers. All 19 findings remain open.
Dependency acquisition, source modification or extraction, package management,
compilation, source load or execution, sockets, network, device, deployment,
Git writes, external authentication, and user action remain unauthorized or
unrequired.

The predecessor
[bounded dependency wave-one preparation decision v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-v1.json)
and [reader-facing decision](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-v1.md)
record
`status=wave1_source_identity_and_request_contract_prepared_acquisition_not_authorized`,
`result=exact_19_root_requirement_source_identities_and_bounded_wave1_request_contract_prepared`,
and
`nextAction=prepare_separate_versioned_wave1_execution_permit_after_checker_runner_and_tests`.
The preparation directly binds the predecessor decision, plan, checker/tests,
restricted profile, retained source identity chain, root metadata, semantic
triad, and patch/dependency portfolio. It freezes the conservative 19-tuple
root intake seed, four quarantined checksum-only tuples, Android API 26-through-
36 arm64-v8a and macOS 14-or-newer arm64 review profiles, Go 1.24.0, cgo and
build-tag rules, deterministic profile-union MVS fixed-point semantics, 19
exact public-proxy ZIP request/output identities, finite resource ceilings, and
failure/receipt/readback contracts.

The checker and 56/56 mutation tests reject lineage, schema, profile, seed,
quarantine, H1, URL, output, identity, bounds, filesystem, receipt, sequence,
authority, execution, closure, symlink, hardlink, unexpected-artifact, and
replace-after-read drift. Direct dependency SumDB inclusion, repository-owner
attestation, raw ZIP identity, production reachability, license compatibility,
source review, and graph/dependency closure are not claimed. Request count is
zero; dependency acquisition and network remain unauthorized and unexecuted.
All 19 findings remain open, and candidate/library selection remains false.
Neither repository-owner identity proof, external authentication, nor user
action is required.

The historical successor
[bounded dependency wave-one execution permit v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-execution-permit-v1.json)
and [reader contract](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-execution-permit-v1.md)
recorded, before execution,
`status=wave1_dependency_source_acquisition_authorized_not_consumed`,
`result=exact_19_public_proxy_zip_requests_authorized_once_not_executed`,
and `recordedNextActionAtThatCheckpoint=execute_bound_dependency_source_wave1_once`.
The runner still passes 44/44 tests. The permit suite recorded 38/38 only at
the unconsumed checkpoint; the current gate reruns 36 state-independent cases
because v1 is consumed and cannot be retried.

The historical
[wave-one recovery decision v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-recovery-decision-v1.json)
and [reader contract](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-recovery-decision-v1.md)
recorded the terminal `E_ZIP_RATIO` failure after two response bodies and one
fully validated/staged tuple, with zero accepted artifacts and no final set.
They select a separate v2 implementation using exact-integer, non-gating
compression telemetry under the unchanged absolute streaming and deadline
bounds. The 31/31 recovery mutation tests pass. At that checkpoint they
recorded
`status=wave1_v1_failure_read_back_recovery_v2_design_selected_execution_not_authorized`,
`result=v1_ratio_policy_rejected_tuple2_after_two_responses_no_final_set_v2_bounded_telemetry_policy_selected`,
and `recordedNextActionAtThatCheckpoint=prepare_separate_v2_runner_checker_tests_and_execution_permit`.

The historical
[wave-one execution permit v2](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-execution-permit-v2.json)
and [reader contract](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-execution-permit-v2.md)
recorded, before execution,
`status=wave1_v2_dependency_source_acquisition_authorized_not_consumed`,
`result=exact_19_public_proxy_zip_requests_v2_authorized_once_not_executed`,
and `recordedNextActionAtThatCheckpoint=execute_bound_dependency_source_wave1_v2_once`.
The v2 permit is now consumed and cannot be retried. Its retained claim and
failure receipt record `E_GO_MOD_MISSING` on tuple 11 after 11 completed ZIP
responses, 10 validated/staged tuples, zero accepted artifacts, and no final
set.

The predecessor
[wave-one recovery decision v2](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-recovery-decision-v2.json)
and [reader contract](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-recovery-decision-v2.md)
record
`status=wave1_v2_failure_read_back_recovery_v3_design_selected_execution_not_authorized`,
`result=v2_conflated_zip_and_mod_resources_tuple11_after_eleven_responses_no_final_set_v3_zip_plus_mod_policy_selected`,
and
`recordedNextActionAtThatCheckpoint=prepare_separate_v3_runner_checker_tests_and_execution_permit`.
The checker and 39/39 mutation tests bind v1/v2 terminal bytes and select a
fresh 19-pair `.mod`-then-`.zip` design. That preparation action is complete.

The historical
[wave-one execution permit v3](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-execution-permit-v3.json)
and [reader contract](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-execution-permit-v3.md)
recorded, before execution,
`status=wave1_v3_dependency_source_acquisition_authorized_not_consumed`,
`result=exact_19_public_proxy_mod_then_zip_pairs_v3_authorized_once_not_executed`,
and `nextAction=execute_bound_dependency_source_wave1_v3_once`. It is consumed
and cannot be retried. The immutable
[success receipt](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-receipt-v3.json)
and [manifest](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-manifest-v3.json)
record `status=acquired_pending_independent_readback`,
`result=fresh_exact_19_dependency_zip_mod_pairs_acquired_and_hash_verified`,
38 request attempts, 38 completed bodies, and 38 accepted resources across 19
exact `.mod`/`.zip` pairs. The separate
[readback receipt](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-readback-v1.json)
and [manifest](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-readback-manifest-v1.json)
now validate `status=independent_readback_complete`, 43 regular files, and the
same 38 resources. The permit-bound 34/34 reader tests remain immutable; a
versioned recovery reader recorded the outputs once, and the
[fixed-hash post-verification decision v3](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-readback-post-verification-decision-v3.json)
plus its verification-only 9/9 suite close the discovered raw-encoding,
dispatch, TOCTOU, and typed-comparison gaps with
`fixedHashEnforcedInsideHeldValidation=true`, `verificationOnly=true`, and
`recordModeExposed=false`. That checkpoint recorded
`recordedNextActionAtThatCheckpoint=prepare_separate_dependency_source_review_wave`.
The
[dependency source-review wave-one decision v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-review-wave1-decision-v1.json)
then prepared the bounded review contract. It was followed by immutable v1
`E_HELD_SET` and v2
`E_ARCHIVE_STRUCTURE` failed-closed attempts, neither of which published a
partial result. The corrected one-use v3 review produced the
[result](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-review-wave1-result-v3.json)
and
[manifest](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-review-wave1-manifest-v3.json);
its separate
[readback receipt](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-review-wave1-readback-v3.json)
and
[readback manifest](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-review-wave1-readback-manifest-v3.json)
now record, at that checkpoint,
`status=dependency_source_review_wave1_readback_published_new_tuple_wave_required`
and
`result=independent_readback_receipt_published_then_manifest_written_last_new_tuple_wave_required`;
the recorded next action was
`nextAction=prepare_separate_versioned_dependency_wave2_identity_and_acquisition_decision`.
Graph SHA-256
`2c94906a07a40737e30ca832c215fa88d2233297c9fb0ea25755488d9a72408b`
binds 132 nodes/1,047 edges, 35 module nodes/86 module edges, 25 selected
versions, zero unmapped or unresolved declared external imports, and exactly
15 new tuples. Five are missing selected-version sources and ten are required
version-specific vertices; every row remains `acquisitionAuthorized=false`
and must not be collapsed or replaced by a higher version. The route is
`new_tuple_wave_required`. All 19 findings remain open; every dependency,
semantic, rung-three, candidate, library, and release closure remains open. This work uses
no owner proof, credentials, keys, signatures, tokens, passwords, or user
action.

That historical preparation action is recorded in the
[wave2 identity/acquisition decision v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave2-v1.json)
and
[reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave2-v1.md).
Its read-only checker and 37/37 offline regression checks bind the exact 15-version
frontier, every introducing parent `.mod` declaration, and 30 ordered
`.mod`-then-`.zip` H1 expectations from existing non-conflicting `go.sum`
evidence. At that checkpoint,
`status=wave2_local_checksum_identity_and_30_resource_contract_prepared_future_bytes_unverified_acquisition_not_authorized`;
the result was
`result=exact_15_graph_frontier_tuples_30_mod_zip_requests_and_held_h1_expectations_prepared_future_bytes_unverified`;
and
`recordedNextActionAtThatCheckpoint=prepare_separate_versioned_wave2_checker_runner_tests_and_one_use_execution_permit`.

That action is complete in the
[wave2 one-use execution permit v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave2-execution-permit-v1.json)
and
[reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave2-execution-permit-v1.md).
Current status is
`status=wave2_v1_dependency_source_acquisition_authorized_not_consumed`;
current result is
`result=exact_15_public_proxy_mod_then_zip_pairs_authorized_once_not_executed`;
and `nextAction=execute_bound_dependency_source_wave2_v1_once`.
The 41/41 permit, 50/50 runner, and 39/39 readback checks pass alongside the
37/37 decision checks. Exact preflights retain an empty namespace and show no
network or file write. The permit is limited to 15 tuples and 30 ordered public
Go proxy requests; response bytes remain unacquired and unverified until it is
consumed once. Extraction, source loading/execution, compilation,
runtime/product network, Git, device, and deployment remain closed. Repository
authentication, account, owner proof, credential, key, signature, token, and
password are outside this workflow. Neither external authentication nor user
action is authorized or required.

The rung-two successor recorded, only `at_that_checkpoint`,
`recordedNextActionAtThatCheckpoint=prepare_versioned_rung3_offline_source_review_decision`.
That historical preparation action is complete and authorizes no review
execution.

## Current Handoff Snapshot

- Repository: `/Users/hanchangha/Desktop/project`
- Branch at handoff: `main`
- Selected implementation baseline:
  `d32c1846eead13ab1462619145fc4da1194cce7e`. Published G0 V2/V3 checkpoint:
  `12c381547935b96d383ac39976261ea6c3ce6a5b`. Published receipt/intake successor:
  `70350f5e9e5e39d1b793862c1e58d09edf637405`. Published truth-sync and dormant
  preview-compiler successor:
  `025a4ef5e6c3e52c46a6b79ee3a06a6eb47de4e0`. The subsequent sixteen-file
  observation, two-selector, non-authorizing evidence-readiness, candidate
  independent-context, and mechanical repository/remote-source successor is
  published at `b24c5ecb77067539c185d88f0c2fbbc2cb119c15`, with `main` and
  `origin/main` aligned when refreshed.
- Publication readback: a fresh repository with no object alternates fetched
  the exact target and directly matched all 18 approved raw files. The remote
  V3 checkpoint readback ran from `2026-07-20T12:05:21Z` through `12:05:44Z`,
  producing 4,692 bytes at SHA-256
  `37462cd8303ce61742bc480d0f7d37e0ccb380ec12375cc8c8d10169aebf4dc5`.
- Successor readback: a second fresh repository with no object alternates fetched
  remote `main@70350f5e` from `2026-07-20T13:54:08Z` through `13:54:12Z` and
  directly matched all nine successor file bytes. The reproducible commit-blob
  manifest and the separately observed remote-acquisition boundary are recorded
  below.
- Follow-up readback: a third fresh no-alternates HTTPS partial clone fetched
  remote `main@025a4ef5` from `2026-07-21T01:15:22Z` through `01:15:28Z`.
  `blob:none` omitted file contents until the exact seven changed blob IDs were
  requested; their modes, blob IDs, byte counts, and raw SHA-256 values matched
  the local commit. The exact parent is `70350f5e`, tree is `e1272bdf`, and the
  ordered seven-line manifest SHA-256 is recorded below.
- Latest successor readback: a fourth strict fresh HTTPS `blob:none` partial
  clone observed remote `main@b24c5ecb` from `2026-07-21T07:55:12Z` through
  `07:55:22Z`. The clone used an exact allowlisted environment, isolated Git
  configuration, an empty template, TLS verification, no credentials, no
  alternates, grafts, replacement refs, linked worktree, or shallow state. All
  sixteen target blobs were absent before lazy fetch and then matched the exact
  local commit-object bytes, lengths, raw SHA-256 values, and recomputed Git
  object IDs. Commit, parent, and root-tree raw bytes also matched. The exact
  parent is `025a4ef5`, tree is `c8aa9e69`, and the ordered sixteen-line
  manifest SHA-256 is recorded below.
- Historical publication: the twelve-file owner-trust-bootstrap/external-readiness successor is
  published and independently read back at
  `4227204b450372fcee55e0ef970c401f10b6c98c`, with parent `b24c5ecb` and tree
  `c321c33e`. A fresh public HTTPS GitHub commit/tree API, raw-content, and
  `git ls-remote` observation from `2026-07-21T12:34:24Z` through `12:34:32Z`
  matched remote `main` plus all 12 path statuses, modes, blob IDs, byte lengths,
  raw SHA-256 values, and bytes. The ordered 1,857-byte manifest SHA-256 is
  `267be3ca8f56fe353fbb856f95c6f634e98afbc3f204b589a9935be0fe5b0a15`;
  its bytes were not persisted or signed. This remains a bounded remote-source
  observation only. Its historical owner-authentication and authority state does
  not govern current personal-project work. The current slice began from clean,
  aligned `main` and `origin/main` at
  `dee5d87791ceaddb094235fbf33f7997580ddb1e`. Beyond the completed socket-free
  G1a foundations, the current worktree contains G1b-A Android normal-graph
  activation-controller ownership, injected real-fixture manager/ViewModel E2E,
  the macOS IPv4-loopback-only accepted-raw primitive, the G2 Pion v4.3.0
  official-source preflight plus restricted-fork rung-one design, and the
  consumed rung-two acquisition receipt with retained unextracted bytes. The normal
  Android controller intentionally starts
  empty, the macOS primitive is not `CompanionAppModel`-wired, and neither path
  has executed a live socket or device. The worktree is intentionally dirty for
  this bounded current slice. All changes remain unstaged and uncommitted for
  user review.
  Run `git status --short` again because live output is authoritative.
- G1a-A no-network state: six typed `ALS1` route authorizations and one exact
  21-field endpoint secure-session transcript are implemented independently in
  Swift and Kotlin. The shared fixture pins six route plus six transcript byte
  encodings and SHA-256 digests. Four Swift and five Kotlin focused tests pass,
  including round-trip parity, strict route matching, malformed canonical input,
  size ceilings, and invalid endpoint identity/key/nonce rejection. The
  contract has no socket/network imports and is not an active wire message,
  key derivation, encrypted record path, or network operation.
- G1a-B no-network state: type-8 authority and type-9 local snapshot objects,
  exact cross-platform vectors, monotonic verified transitions, and bounded
  replay admission now match between Swift and Kotlin. A seven-field advanced
  snapshot stores up to 20 prior transition ID/request-digest pairs while the
  empty-history five-field fixture remains byte-stable; lifetime ID reuse and
  all epoch changes fail closed until signed fresh-pair proof exists. macOS
  persists state in the locked atomic trusted-device store; Android persists one
  canonical Base64 snapshot in a DataStore transaction. Both save replay
  consumption before returning an opaque permit and fail closed on corrupt or
  missing state, identity drift, rollback, replay, revoke, capacity, or
  durability failure. Android preserves state through app projection and
  rejects every legacy-only route for a stateful target. macOS reloads trust
  before active or restored pair transport start and rejects missing, ambiguous,
  corrupt, or stateful legacy starts. The older pre-connector seams remain
  internal and dormant; a bounded optional caller bridge now exists, but the
  normal app does not inject its real upstream production inputs. G1a-B itself
  performs no
  signed authority/capability verification; G1a-C below adds that contract
  readiness without activating the app path.
- G1a-C no-network state: root-pinned service keysets, signed pair status and
  fresh-pair transitions, route and four role/direction-specific object-23/24
  candidate capabilities, object-27 endpoint proofs, and four fixed-order
  signed post-commit object-28 receipts now verify independently in Swift and
  Kotlin. One canonical keyset and one adjacent durable ledger chain are
  required before deriving exact unsigned object-25 evidence and object-26
  authorization; candidate object 7 binds the exact object-26 SHA-256 rather
  than generic object 4. The base fixture SHA-256 is
  `c25c0f4d74b0029f060bcedf31b19ef95c57a0a0e6708a741175c8cedeb611f3`;
  the additive candidate fixture SHA-256 is
  `e6bc666dbf9fded82d5681fdcfdc2c4c9cd5fa197135fc0673569d35656236af`.
  Generic P2P admission is closed and Android generic verified wrappers require
  private mint provenance.
- G1a-C durability/evidence boundary: the macOS owner-only file store and
  Android DataStore each commit the pair snapshot, endpoint ledger, and chained
  marker as one canonical compound image and reread exact bytes before returning
  a live token. The token window is derived from verified object-25/26 evidence;
  a store-owned clock checks it immediately before persistence and again after
  readback, rejecting clock regression and expiry. Restart and committed retry
  are non-authorizing readback only, and raw pair/session mutation APIs are not
  exposed to production app adapters. An older internally valid whole-store
  image still requires an external monotonic head for rollback detection. The
  current test counts are recorded in the QA paragraph below.
- G1a-C exact-bound start boundary: each platform store caches one no-network
  coordinator that accepts only a verifier-minted candidate binding plus the
  opaque token returned by an APPLIED exact durable commit. It strict-decodes
  the current store and recomputes the latest ledger entry, latest marker,
  object-4/object-26 split, pair authority, compound digest, identity, and
  validity window at admission, immediately before start, and immediately after
  start. Caller time, historical marker readback, and `AlreadyCommitted` output
  are ineligible. Pair-scoped single-live admission, checked generations,
  secret-free 64-entry per-pair terminal tombstones, cancellation, revocation,
  authority advance, expiry, and late-start rollback are fail closed. Durable
  pair-state mutation fences the cached coordinator only after the store write
  succeeds. Explicit operation-scoped callback context survives detached task
  or coroutine reentry without self-waiting. A fence while start is in flight
  may invoke its generation-scoped idempotent abort immediately and again after
  start returns to catch late publication; an active fence invokes it once.
  The pair reservation remains quarantined until cleanup finishes. Android
  retains a failed cleanup for explicit retry and transfers handle/lease
  cancellation ownership without a gap; Swift retains cooperative cancellation
  semantics while waiting for its late-publication cleanup. G1b-A now places an
  empty controller and the production composer in the normal Android graph, but
  the coordinator can become live only when a future upstream producer supplies
  a verified attempt; injected real-fixture E2E exercises that path without an
  OS socket. This remains `synthetic_contract_readiness_only` with
  `productionDurabilityClaim=false`; sockets/network, device proof, deployment,
  and production readiness remain open.
- G1a-D no-network crypto state: Swift and Kotlin accept only the verifier-minted
  exact object-7/object-26 key-schedule binding, verify the local one-use P-256
  private/public match, derive the same ECDH/HKDF-SHA-256 material, require both
  role-separated object-29 confirmations, and then issue one ordered object-30
  AES-256-GCM cipher. Per-direction epoch/session record and byte ceilings,
  update reservation, epoch-15 termination, replay/gap/future-epoch rejection,
  monotonic time, expiry, failed-authentication counter stability, concurrent
  sequence uniqueness, terminal key wiping, and explicit invalidation are
  enforced. The pinned crypto fixture SHA-256 is
  `d45fd920e22652d790c742de995d87a8cbfb64bb22aca3b829cbad5b23485448`.
  This core is reachable through the bounded production-composition graph only
  after a verified attempt is supplied. The normal controller publishes none,
  and the current evidence opens no socket.
- G1a-D authority-bound lifecycle state: the verifier-minted key-schedule
  binding now stays inside an exact-bound session wrapper owned by the same
  store/coordinator graph. A store-owned process-local writer-preferred/FIFO
  publication gate holds a read permit across start, confirmation, activation,
  seal, open, and their pre/post lease and live-resource fences. Durable pair
  transition, fresh transition, and removal writers block new readers, drain
  in-flight publications, commit, synchronously fence the coordinator and wipe
  crypto, then release. Pure precommit rejection and macOS pre-rename failure
  preserve the old session. Once an Android DataStore edit is enqueued,
  cancellation or ambiguous persistence failure fences/wipes the old authority;
  macOS post-rename directory-sync uncertainty does the same.
  Cancellation or terminal crypto failure invalidates the resource and closes
  its lease. A Swift post-fence suppression explicitly zeroizes the owner-backed
  storage for confirmation, seal, and open results before releasing the read
  permit; small-ciphertext plus confirmation/seal/open retained-owner and
  result-copy regressions cover the backing allocation. An independent `Data`
  snapshot already extracted by a caller is a separate copy and is not
  retroactively zeroized. This guarantee is single-process and same-store/
  coordinator-graph only. Bounded no-network caller bridges exist, but real
  upstream production activation remains unwired.
- G1a-D transport-composition state: Android `core:transport` exposes only a
  manager-owned one-use raw-route lease to its composer, not a raw-channel
  alias or caller-provided scope. The lease validates the exact authority
  capability/session and creates `ProductionRuntimeSecureChannelAdapter` with
  a manager-owned execution scope. Construction failure cancels the owned scope,
  and the adapter is registered before handshake suspension. Under `stateLock`,
  `UNDISPATCHED` acquisition linearizes the transition with physical connector
  entry: cleanup that wins first prevents connector invocation, while an entered
  connector that has not returned a handle still depends on connector timeout/
  interruption and closes any late handle when it returns. Detached composition
  uses saturating raw-route timeout addition plus a fixed 15-second handshake
  budget. The manager timeout's `IOException` is classified as
  `ProductionSessionSecurityRejected`. The adapter's internal deadline uses one
  `PENDING` to `COMPLETED`/`TIMED_OUT` CAS plus an `UNDISPATCHED` watchdog.
  Timeout-winning `IOException` dominates and suppresses the losing error/
  cancellation; completion-winning external or composer
  `CancellationException` preserves the exact object.
  Canonical `resume(value, onCancellation)` handoff closes only undelivered
  values: pre-delivery cancellation closes once without retry, while successful
  transfer survives later acquisition `Job` cancellation. There is no permanent
  caller-`Job` binding or `InternalCoroutinesApi`. Production P2P is checked
  against the exact session, object-7/object-26 binding, route kind, and
  manager-owned connection
  generation. Route expiry is rechecked immediately before one-use receipt
  commit, admission-to-commit wall-clock rollback fails closed, and failure
  cleanup runs in `NonCancellable`. Even when raw ignores close until it returns,
  the managed raw wrapper checks open before and after send, fails closed after
  close; the tests observe actual late body-byte zeroization. Production relay
  fails closed because no verifier-derived
  exact relay route binding exists. Focused Android evidence is 79/79 (49/49
  manager plus 30/30 adapter). The root independently reran full
  `core:transport --tests '*'`: 10 suites pass 163/163 with zero failures,
  errors, or skips; app `compileDebugKotlin` plus `compileDebugUnitTestKotlin`
  also succeed. An independent iterative audit found and fixed six P3
  availability/lifetime races in total; a final fresh re-audit reports no P0-P3
  finding. The current root-independent full Swift rerun passes 2,003 tests with
  two declared skips and zero failures in 313.440 seconds. Those focused/full-
  module reruns alone were not a completed full no-device gate run; the current
  full no-device gate exits zero.
  The macOS manager owns the exact one-use attachment, generation cleanup,
  cancellation/late-result close, raw-handler admission, and terminal mailbox
  drain before removal or replacement. Terminal teardown synchronously
  invalidates an available/claimed capability before replacement, then runs
  asynchronous abandon/close outside registry locks; there is no plaintext
  fallback. Focused macOS evidence is 39/39 (17/17 composition plus 22/22
  secure-channel) and 34/34 (6/6 production-pair-coordinator plus 28/28
  manager), and the release build passes. The audit-found
  cancellation/replacement P2 is fixed with a deterministic delayed-abandon
  regression; final independent re-audit reports no P0-P3 finding. The bounded
  no-network caller bridge is now concrete. The Android ViewModel's optional DI
  path owns one renewable `AndroidProductionRuntimeActivationSlot` shared by
  route preparation and start-material claim. It holds at most one verifier-
  derived, one-use `AndroidProductionRuntimeActivationPlan` per attempt,
  requires the exact same `PairingStore` provider, compares the manager-selected
  exact route object and prepared-session reference, and reaches composition
  only through the manager-owned raw-route lease. After claim, a generation-
  bound claimed entry remains slot-owned until PairingStore transfer starts.
  Close or replacement winning first discards its key; transfer winning first
  moves cleanup ownership exactly once to the transfer object. Cancellation and
  duplicate or concurrent completion fail closed, and the transfer callback
  runs at most once. Expiry, slot close, and ViewModel clear also discard still-
  pending key material; a fresh plan may serve a later reconnect attempt. The public
  macOS `MacRuntimeProductionAcceptedSessionService` fixes one exact
  `TrustedDeviceStore`, checks a verifier-derived exact accepted-route
  descriptor, transfers the endpoint through a one-shot claim, and attaches it
  through the manager. A service-owned pre-attachment generation remains
  registered across suspended authority creation. Targeted `stop` and
  `stopAll` invalidate it before attachment, and `stopAll` rotates an epoch so a
  late authority return is abandoned without disturbing a fresh same-ID
  generation. Every pre-attachment failure closes untransferred keys. Focused
  Android evidence passes 16/16 composer plus 1/1 ViewModel-clear tests; the
  full app suite passes 1,174, and complete core protocol, pairing, and transport
  suites pass 232/232, 200/200, and 163/163. Focused macOS evidence passes 9/9
  service tests and 54/54 manager + service + composition tests (28 + 9 + 17);
  the release build succeeds. These focused results are not a refreshed full
  no-device aggregate.
- G1b-A Android state: `RuntimeClientViewModelDependencies.create` now constructs
  one app-scoped `AndroidProductionRuntimeActivationController` from the exact
  `PairingStore` and the graph's exact trusted clock. The normal ViewModel route
  preparer, raw-route connector, and composer all use that controller. It starts
  empty and returns no production route until `publishVerifiedAttempt` receives
  a verifier-derived binding, one-use key, and already-connected endpoint from a
  future P2P stack. Injected real-fixture tests exercise both
  `RuntimeConnectionManager` and the complete ViewModel connect path, reject all
  legacy connector fallbacks, finish the secure handshake, and exchange an
  application record without an OS socket.
  Publication generation is assigned before durable admission, so a delayed
  older admission cannot replace a newer attempt. Close, cancellation, or
  supersession reclaims the attempt-owned key and endpoint, including while
  admission is suspended, and displaced publication cleanup executes outside
  controller locks. The focused controller suite passes 12/12; an independent
  final audit reports no P0-P3 finding.
- G1b-A macOS state: `LocalPeerServer.startAcceptedRaw` is a concrete
  accepted-raw primitive with `127.0.0.1` as its required local endpoint. One
  bounded pending authorization may produce one accepted session; receive does
  not begin until the claimed endpoint installs its handler, and expiry,
  malformed frames, stop/delivery races, and unauthorized peers fail closed.
  `RawFrameBodySeamTests` use injected connection I/O; they do not start the
  listener or execute a socket. `CompanionAppModel` has no call site for it.
- G1b-A residual: Android still lacks the upstream verifier/candidate/secret
  producer and actual P2P endpoint stack. macOS still lacks
  `CompanionAppModel` wiring. Actual socket execution and close interruption,
  live network, physical-device, and production-release evidence remain open.
  The eventual production caller must keep `seal + channel.send` inside the same
  read-permit closure.
- Historical G2 preflight state at_that_checkpoint: unmodified Pion ICE v4.3.0 at exact commit
  `1e8716372f2bb52e45bf2a7172e4fb1004251c46` is
  `rejected_at_official_source_preflight_as_is`. Its as-is source lacks one
  non-bypassable post-resolution destination policy, logs the remote ICE
  password, has callback queues without a declared bound, and can wait
  indefinitely on a blocked callback during shutdown. No source was retained,
  compiled, loaded, or executed, no library was selected, and no socket or
  network rung was opened.
- Historical G2 restricted-fork state at_that_checkpoint: the hash-pinned
  [portfolio](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/hardening.md)
  compares upstream as-is, a wrapper-only gateway, and a minimal policy-owned
  fork. Only the fork shape is
  `pion_restricted_fork_profile_ready_for_rung2_decision_only`;
  Pion remains unselected. Schema 1.1 is a not-yet-implemented design requiring
  separate single-use egress authorization immediately before socket
  create/bind/connect/TLS/write and bounded ingress read/parse/admission before
  state mutation or delivery, authenticated TURN TLS service identity before
  credential transmission, and one-use pre-auth promotion only after exact
  AetherLink endpoint confirmation. It also requires exact current, active,
  draining, and closing session/process bounds, an independent sticky terminal
  latch, secret-free diagnostics, non-profile paths to fail before I/O, and a
  2,500 ms total close deadline; none is runtime-verified. The future compile-only
  V1 architecture matrix and later dependency/SBOM/license/patch/symbol/
  reproducibility evidence remain requirements. The validator and 17 mutation
  tests pass. At that checkpoint it opened no source, dependency, compiler,
  loading, socket, network, device, deployment, Git write, external identity
  proof, or user-action prerequisite. Rung two has since consumed its exact
  one-use source request and retained verified bytes without extraction.
  Rung-three v1/v2 failed closed before publication, while the separate v3 path
  completed bounded lexical inventory and tracked readback. Semantic-review
  decision v1 was then consumed as historical execution authority, and
  patch/dependency decision v1 completed that preparation. The historical
  dependency-review decision selected only the staged fixed-point source-closure
  plan and recorded
  `recordedNextActionAtThatCheckpoint=prepare_separate_versioned_bounded_dependency_source_identity_and_acquisition_decision`.
  The predecessor wave-one preparation decision completed that recorded next
  action without acquisition. It binds the exact 19 root-requirement source
  identities, quarantines four checksum-only context tuples, freezes the Android
  and macOS V1 graph profiles and resource limits, passes its read-only checker
  plus 56/56 mutation tests, and records
  `nextAction=prepare_separate_versioned_wave1_execution_permit_after_checker_runner_and_tests`.
  The successor execution permit satisfied that action and was consumed once.
  Recovery decision v1 completed the separate v2 preparation. The v2 permit
  was then consumed by the terminal tuple-11 `E_GO_MOD_MISSING` failure and
  cannot be retried. Recovery decision v2 recorded
  `recordedNextActionAtThatCheckpoint=prepare_separate_v3_runner_checker_tests_and_execution_permit`.
  The historical v3 permit completed that preparation and was consumed exactly
  once. Its bounded 38-request public-proxy intake retained 38 verified
  resources, and the fixed-hash post-verifier now confirms the 43-file
  acquisition/readback set. Source-review v1/v2 then failed closed without a
  partial result; v3 and its independent readback recorded the exact 15-tuple
  frontier. Wave2 decision v1 now binds those exact versions, parent
  declarations, and 30 held-H1 resource expectations without acquisition. The
  current
  `nextAction=prepare_separate_versioned_wave2_checker_runner_tests_and_one_use_execution_permit`.
- Historical G2 restricted-fork rung-one status contract at_that_checkpoint:
  `status=rung1_profile_complete_candidate_not_selected`,
  `result=pion_restricted_fork_profile_ready_for_rung2_decision_only`, and
  `recordedNextActionAtThatCheckpoint=prepare_versioned_rung2_source_identity_and_acquisition_decision`.
  Rung one completes only the design, validator, and 17 mutation tests;
  `implementationStatus=not_implemented`, `candidateSelected=false`,
  `librarySelected=false`, `sourceAcquisitionAllowed=false`,
  `dependencyInstallationAllowed=false`, `compilerInvocationAllowed=false`,
  `codeLoadingAllowed=false`, `socketCreationAllowed=false`,
  `networkIoAllowed=false`, `deviceExecutionAllowed=false`,
  `productionDeploymentAllowed=false`, and `gitOperationAllowed=false`. The
  actual backend, reliable ordered carrier, and fragmentation/reassembly remain
  unselected and unimplemented. Only stack-neutral wiring may continue. Schema
  1.1 remains a not-yet-implemented and not-runtime-verified design. It requires
  a separate single-use egress capability after resolution immediately before
  socket create, bind, connect, TLS handshake, or write, plus fixed-size bounded
  ingress read/parse/admission before state mutation or payload delivery. It
  requires authenticated TURN TLS service identity before any credential
  transmission and a bounded one-use pre-auth path whose atomic promotion occurs
  only after exact AetherLink endpoint confirmation. Consent loss, path change,
  candidate restart, capability expiry, verification failure, and session close
  each atomically revoke both pre-auth and application capabilities before further
  I/O, state mutation, event, or payload delivery. Exact per-session and process
  bounds cover current, active, draining, and closing state, and event overflow
  requires an independent sticky terminal latch. Secret-free diagnostics and a
  2,500 ms total close deadline are requirements, not completed
  implementation or runtime-verified behavior. Repository-owner, GitHub, SSH,
  GPG, or public-key identity proof is neither a
  prerequisite nor a future G2 rung; `externalIdentityProofRequired=false` and
  `userActionRequired=false`.
  Product pairing and endpoint authentication remain mandatory and separate.
- Current focused no-device evidence: the exact-bound Swift coordinator slice
  passes 31/31 and all TrustedDevices tests pass 78/78. The shared-vector slices
  pass 9/9 Swift and 7/7 Kotlin tests; the complete Swift P2PNAT contract suite
  passes 87/87, the complete Android protocol suite passes 232/232, the complete
  Android pairing module passes 200/200, and the Python crypto-oracle mutation
  suite passes 8/8.
- Previous complete default no-device aggregate snapshot: exits zero with
  `No-device quality checks passed.` after the initial Python batch passes
  182/182, all 1,946 Swift tests finish with two declared skips and zero
  failures, every Android Gradle invocation reports `BUILD SUCCESSFUL`, copy
  hygiene covers 94 files, and docs hygiene covers 12 files. Direct and
  development-relay local mock smokes pass; relay freshness spans 56
  connections and the ciphertext boundary covers 905 encrypted frame bodies.
  The final G1a-D authority-lifecycle marker is present. This is no-device local
  evidence, not physical-device, external-network, production-transport, or
  production app/service activation proof. The transport-composition and G1b-A
  focused tests are newer than this aggregate; the prior counts above were not
  refreshed for those seams.
- G1a-B integrated no-device evidence: the retained
  `build/qa/check-no-device-quality-g1ab-integrated-final-20260722.log` exits
  zero across 8,928 lines. The initial Python batch runs 182 tests; all 1,839
  Swift tests finish with two declared skips and zero failures; five selected
  Android Gradle invocations, direct and development-relay authenticated mock
  smokes, and both final markers pass. The frozen G0/P2P source validators use
  an exact path-and-current-SHA compatibility map for only seven reviewed source
  files; any other byte drift remains rejected and no historical artifact was
  rewritten.
- Android device state at handoff: disconnected; the latest `adb devices -l`
  refresh returned no attached device. Immediately before disconnect, one
  authorized USB `SM-S936N` on Android 16/API 36 had the current debug APK
  rebuilt and installed with data preservation, then cold-launched,
  force-stopped, and relaunched. ADB-injected development pairing, trusted-route
  reconnect, mock chat cancel, natural mock completion, and chat/model/drawer/
  settings UI capture passed. CAMERA was restored to granted and no adb reverse
  mappings remained. Optical QR, actual TalkBack traversal, live provider,
  external relay, and real different-network behavior remain unverified.
- macOS state at handoff: the ad-hoc `dist/AetherLink.app` process was running
  as PID 59809 and listening on TCP port 43170 when refreshed. QR visibility and
  payload decode were not rerun in G0. Process and port state are ephemeral;
  verify them again before making a live claim.
- Git publication state: the bounded G0 V2/V3 packet is published and freshly
  read back at `12c38154`; its nine-file receipt/intake successor is published and
  freshly read back at `70350f5e`; the seven-file truth-sync/compiler successor
  is published and freshly read back at `025a4ef5`; the sixteen-file successor
  is published and freshly read back at `b24c5ecb`. The tracked receipt sidecar still intentionally
  encodes the reviewed parent target/checkpoint/hash/time candidate and does not persist
  fresh-clone/no-alternates or 18-file acquisition provenance and cannot
  independently reproduce that observation. It is not a trusted or accepted
  receipt. The owner/catalog input candidate published at `70350f5e` contains no
  responses. Its published `b24c5ecb` successor contains exactly one mechanically
  compiled `roadmap_and_g0_checkpoint_publication` proposal naming only
  `owner-candidate:repository-owner:v1`; every state flag remains false.
  Neither the proposal nor any publication changed its historical state. Those
  owner/receipt fields are preserved only for byte integrity and do not block
  current personal-project work. The later twelve-file owner-trust-bootstrap/external-
  readiness slice at `4227204` has a completed 12/12 independent remote-byte
  readback with manifest SHA-256
  `267be3ca8f56fe353fbb856f95c6f634e98afbc3f204b589a9935be0fe5b0a15`.
  That historical observation changes none of its recorded fields. The current
  unpublished scope includes the socket-free G1a foundations, G1b-A Android
  normal-graph/injected-E2E work, the macOS loopback accepted-raw primitive, and
  the G2 Pion preflight plus restricted-fork rung-one design/checker portfolio
  described above. Do not reset or clean it.
  The assistant performs edits and verification only; the sole project owner
  retains staging, commit, and push control after review.
- Subagent preference for this workstream: use GPT-5.6 Sol. Do not use
  GPT-5.3-Codex-Spark.

## First Five Minutes

Run these before deciding what is current:

```bash
cd /Users/hanchangha/Desktop/project
git branch --show-current
git rev-parse --short HEAD
git status --short
sed -n '1,530p;/^## Not Yet Proven$/,/^## Handoff Maintenance Rule$/p' docs/handoff.md
sed -n '1,260p' docs/v1/g0/decision-v1.md
sed -n '1,340p' docs/v1/g0/assurance-v1.md
sed -n '1,220p' docs/v1/g0/assurance-closure-amendment-v2.md
sed -n '1,220p' docs/v1/g0/assurance-closure-amendment-v3.md
sed -n '1,90p' docs/progress.md
sed -n '1,90p' docs/qa-evidence.md
sed -n '1,230p' docs/roadmap.md
```

Then run the cheap integrity checks:

```bash
python3 script/check_docs_hygiene.py
python3 script/check_copy_hygiene.py
python3 script/check_macos_localization.py
python3 script/check_v1_g0_checkpoint.py
python3 -m unittest script.test_v1_g0_checkpoint
python3 script/check_v1_g0_decision.py
python3 -m unittest script.test_v1_g0_decision
python3 -m unittest script.test_v1_g0_publication_receipt
python3 script/check_v1_g0_receipt_bundle.py
python3 -m unittest script.test_v1_g0_receipt_bundle
python3 script/check_v1_g0_baseline_evidence_readiness.py
python3 -m unittest script.test_v1_g0_baseline_evidence_readiness
python3 script/check_v1_g0_independent_validation_context.py
python3 -m unittest script.test_v1_g0_independent_validation_context
python3 script/check_v1_g0_owner_trust_bootstrap.py
python3 -m unittest script.test_v1_g0_owner_trust_bootstrap
python3 script/check_v1_g0_owner_trust_bootstrap_v2.py
python3 -m unittest script.test_v1_g0_owner_trust_bootstrap_v2
python3 script/check_v1_g0_external_evidence_readiness.py
python3 -m unittest script.test_v1_g0_external_evidence_readiness
python3 script/check_v1_g0_repository_remote_sources.py
python3 -m unittest script.test_v1_g0_repository_remote_sources
python3 -m unittest script.test_build_and_run
python3 -m unittest script.test_documentation_handoff_guards
python3 script/check_p2p_nat_security_design.py
python3 script/check_p2p_nat_g2_restricted_fork_profile.py
python3 -m unittest script.test_p2p_nat_g2_restricted_fork_profile
python3 script/check_production_relay_security_design.py
python3 -m unittest script.test_p2p_nat_phase_a_progress
python3 -m json.tool docs/evidence/physical-qr-pairing-20260719.json >/dev/null
bash -n script/build_and_run.sh
git diff --check
```

Do not start with `git reset`, `git checkout --`, `git clean`, or blanket
staging. The receipt and empty owner/catalog candidate are tracked at
`70350f5e`, their bounded truth-sync plus dormant preview compiler/tests are
tracked at `025a4ef5`, and the sixteen-file successor is tracked at `b24c5ecb`.
The later twelve-file owner-trust-bootstrap/external-readiness slice is tracked at
`4227204`. That twelve-path set is a historical published checkpoint, not the
current worktree inventory. The current working copy includes the completed G1a
foundations, G1b-A Android normal-graph/injected-E2E work, the macOS loopback-only
accepted-raw primitive, and the G2 Pion preflight plus restricted-fork work
listed in the snapshot. Read current publication state from Git. This workflow
does not stage, commit, or push unless the user separately requests it.

## V1 G0 Execution Status

The active goal is to execute the canonical G0-G7 V1 roadmap. The current
bounded slice created
[`docs/v1/g0/decision-v1.md`](v1/g0/decision-v1.md), its closed-schema
machine record, and the versioned
[`docs/v1/g0/assurance-v1.md`](v1/g0/assurance-v1.md) review companion and
machine record. They confirm Android/macOS, the five launch locales, Ollama and
LM Studio, P2P as a GA gate, Google Play plus direct notarized macOS distribution,
clean-install/fresh-pair handling for Android development `0.1.0`, the retained
TURN plus sealed-emergency-relay profile, TLS signed leases, monotonic pair
epoch recovery, twelve required network cells, six non-omittable network/failure
variants, release-blocking direct-P2P thresholds, four measurement contracts,
and exact release targets. macOS V1 uses a signed DMG rather than leaving PKG
certificate custody unresolved.

The assurance record hash-pins 29 inputs and closes the static shapes for nine
protocol units, sixteen data flows, 35 guarded protocol namespaces, inherited
threats T001-T016 plus T017-T026, ten release risks, nine observability event
classes, five release-record classes with decision-bound metric values,
thresholds, signed raw-sample envelopes, evidence digests, and exact platform rows, the release
checklist, seven incident classes, rollback, and fourteen unassigned approval
roles. It also restores mandatory service-mediated P2P publish/fetch
capabilities, pair-id/epoch recovery binding with secret rotation and a current
signed receipt, the absolute 30-second revoked-state closure bound, rollback
success 1.0, and thirteen zero-allowance security hard stops. Android and macOS
build/sign/distribute/install/update or rollback trust boundaries are explicit
without granting signing, upload, or deployment authority.

The frozen V1 assurance record has one machine-enforced G0 closure contract that
crosswalks all ten blockers, nine checklist items, fourteen accountable roles,
and exact gate-scoped evidence kinds. Owner receipts must bind the exact
published checkpoint digest, containing commit, scoped blocker IDs, timestamp,
and non-empty verified catalog evidence. Gate and publication receipts also
require exact source commit/path/hash bindings, successful result domains, and
ordered timestamps. The separate V2 closure amendment preserves those V1 bytes
and classifies exactly two checks as executable: the full no-device aggregate
and the ordered Android/macOS release-compilation pair. Its canonical command
profiles require an egress-denied runner, offline Gradle,
preseeded dependencies, exact environment/cwd/profile digests, bounded build/
loopback side effects, and complete sanitized logs. Both profiles remain
`not_authorized`; the other seven checks close only from publication, catalog,
and accountable-owner evidence. Fresh publication/readback evidence now exists
outside the immutable V1/V2/V3 bytes, and the local sidecar encodes only its
target/checkpoint/hash/time candidate as `dormant_non_authorizing`. The current
checker exposes no receipt-acceptance API;
an independently anchored, factory-only activation context remains absent. No
owner, gate, activation, G0-exit, or G1a state changes, so the crosswalk does not
close G0.

`docs/v1/g0/assurance-checkpoint-readback-v1.json` is the separate local
candidate for assurance hash and source readback. Its validator pins the
candidate bytes, recomputes assurance raw/canonical hashes, and reads all 29
declared inputs as exact repository-relative regular non-symlink files with a
4 MiB per-file ceiling, same-descriptor hashing, and final path-identity
readback. Its eleven mutation tests reject stale or reordered records, path/
hash/symlink/identity drift, oversized sources or integers, non-finite numbers,
fabricated owner acceptance or publication, blocker removal, and authority
promotion. The embedded status remains
`candidate_observed_not_immutable`; it describes the frozen pre-publication
record and is not changed by the later remote observation. It is not owner
acceptance, receipt activation, or G0 exit.

`docs/v1/g0/assurance-closure-amendment-v2.json` is the published successor
record for the command-profile correction. It pins the unchanged parent V1
raw/canonical hashes, applies eleven exact ordered JSON Pointer operations to a
deep copy, advances both effective schema identities, and records the
independently recomputed effective V2 assurance digest. Its own V2 checkpoint
pins parent, amendment, and effective bytes; the composite publication profile
binds all four exact files. Bounded no-follow reads plus final identity/hash
readback reject symlinks and validation-time replacement. This avoids changing
either committed V1 file and still grants no execution or receipt authority.

`script/check_v1_g0_publication_receipt.py` contains a dormant, non-authorizing
private candidate matcher for only the composite publication receipt. It checks
strict receipt bytes against a factory-owned immutable snapshot of the four
exact commit blobs and separately sourced remote checkpoint bytes. It performs
no receipt-directed file, Git, or network lookup and even an exact synthetic
match returns `dormant_non_authorizing`. The canonical checker rejects every
supplied receipt bundle; the eight synthetic tests neither record publication
nor change acceptance, authority, or G0 state.

The published V3 successor preserves all V1/V2 bytes and applies thirteen exact
operations to effective V2. It pins the missing complete-bundle, owner,
evidence, authority, runner, gate, approval, and six-artifact publication
profiles. `script/check_v1_g0_receipt_bundle.py` reconstructs the six exact
lineage blobs from one immutable snapshot and privately derives ten blockers,
nine G0 checks, 14 roles, 15 role/blocker pairs, 15 non-derived evidence kinds,
two derived kinds, and two executable checks from effective V3. It also binds
the ordered checklist evidence union to the blocker evidence union. It exposes
no receipt-acceptance or activation API; even an exact complete fixture returns
`dormant_non_authorizing`.
The tracked
`docs/v1/g0/assurance-closure-publication-receipt-candidate-v3.json` sidecar now
binds the exact published target, six lineage records, V3 checkpoint raw bytes,
and observed UTC time. The checker pins its full raw SHA-256, uses no-follow
snapshot reads and a final identity/hash recheck, and still always leaves it
dormant. Neither file persists the fresh-clone/no-alternates acquisition or
18-file comparison provenance, so it cannot independently reconstruct the
remote observation. Registry, revocation, artifact, log, runner, trusted-clock,
signature, owner, and activation trust inputs remain absent.

The tracked `docs/v1/g0/owner-catalog-input-candidate-v1.json` is a separate
content-addressed, sparse intake envelope bound to the published repository,
commit, checkpoint, and effective V3 assurance/closure digests. Its published
starting form at `70350f5e` has `responses: []` and every state flag `false`.
After the user explicitly supplied the publication owner and both evidence-kind
selectors on 2026-07-21, the public dormant compiler produced the current exact
1,452-byte
working-copy candidate at raw SHA-256
`0221d2d49e4bcccfd34fb6905102117fbf5632e27d3d2f2e23d53e29f47752bc`.
It contains one `proposed_as_written` response for
`roadmap_and_g0_checkpoint_publication`, one role-bound
`owner-candidate:repository-owner:v1` reference, the canonically ordered
`reviewed_commit_scope:v1` and `published_checkpoint:v1` evidence references,
no change-request candidate, and source reference
`user-input:session-20260721:item-2`. Both supporting-artifact references are
null because both selectors were explicitly false. Every
state flag remains `false`; the packet stores no owner identity, catalog value,
accepted decision, credential, evidence byte, or acceptance. The checker
derives the allowed blocker order, accountable roles, and non-derived evidence
kinds from effective V3 rather than copying that graph into the packet. It
rejects unknown, duplicate, or reordered responses, role/reference misbinding,
repeated-role version drift, derived-evidence assertions, free-form values,
references not mechanically bound to the exact role/evidence kind/blocker and
version, unsafe artifact references, contradictory disposition fields, and any
activation-state promotion. Actual
catalog values and evidence bytes are not accepted in this envelope; a
kind-and-version-bound safe path only reserves the canonical location for a
candidate artifact that must be separately typed, created, and reviewed before
use. Even a structurally valid populated candidate
remains `draft_unverified_non_authorizing`: it is input for later authenticated
review, not owner authentication, catalog verification, receipt acceptance,
blocker closure, G0 exit, or G1a authority.
Disposition semantics are closed: `proposed_as_written` requires at least one
role-bound owner or kind-bound evidence reference and forbids a change request;
`proposed_with_changes` requires the blocker-bound change-request reference;
`not_available` requires all owner, evidence, and change candidates to be empty.
Every response still requires one canonical session-item source reference.
The user has now declared one sole human project owner. V3 requires fourteen
unique opaque `ownerIdentityRef` values, not fourteen different people, so the
same principal may be represented by fourteen registry-authenticated role-scoped
references while all role-specific bindings and receipts remain separate. This
identity-free intake envelope still does not authenticate that declaration or
store the future aliases.

The separate v2 bootstrap successor,
`docs/v1/g0/owner-trust-bootstrap-profile-v2.json`, records the user's exact
candidate choice without promoting it into an operational selector:
`github:hanchangha1127`,
GitHub numeric subject ID `243786110`, and one `ssh-ed25519` OpenSSH SSHSIG
software-key mechanism. Its fourteen deterministic role mappings each have a
unique owner-binding, opaque owner-identity, and receipt reference while all map
to the same principal. The profile is pinned at raw SHA-256
`13a3b3a5097b443620f049ad69663c486810945436e1c484f3a79cc8635c53f3`.
It defines closed-field dormant candidate shapes for exact raw plus canonical receipt digests,
role credential and independently issued challenge binding, canonical 70-character/LF
OpenSSH armor plus exact Ed25519 SSHSIG wire structure, one-way revocation-to-registry
digest binding, exact status-reference closure, null external root selectors, paired
registry/revocation high-watermarks, JCS envelope/manifest encoding, RFC 3161 time
evidence, atomic replay consumption, and fail-closed successor transitions. Structural
SSHSIG parsing is not cryptographic verification. This owner-bootstrap SSH credential path forbids private-key
generation, discovery, paths, agent use, environment or Keychain lookup, and
project-driven signing. All ten operational
selection references remain null, every authority state remains false, and the
adapter remains `not_implemented`; the missing independently pinned public key,
registry root, TSA, and external ledger still prevent owner authentication.

A repeated, non-authorizing GitHub public-key observation on 2026-07-22 read
`https://github.com/hanchangha1127.keys` twice with matching bytes. The mutable
endpoint returned one `ssh-ed25519` line: 81 response bytes at SHA-256
`18932433bb8a1ea9219ec94f677a17d7e695f286f5ab9e1145d708db6326048e`,
containing a 51-byte OpenSSH public-key wire blob at SHA-256
`6ba489f21ff7d6ca504f74ff8cf8af656016adb8307fe4b2faeb08af8e7edca8`
and fingerprint `SHA256:a6SJ8h/31spQT3T/jPivZWAWrbgwf+Sy+usIr45+3Kg`.
The response and public-key bytes were not persisted. This mutable endpoint
observation is supplemental provenance only: `credentialRefCandidate`,
`publicKeyBlobSha256`, `openSshPublicKeyFingerprint`, and `trustAnchorRef`
remain null, and it is not an authenticated selector, proof of control, trust
anchor, owner authentication, receipt acceptance, G0 exit, or G1a authority.

The module's sole public helper,
`compile_dormant_owner_catalog_input_preview`, snapshots and strictly parses a
bounded JSON selector request, derives blocker/role/evidence references and
optional safe artifact paths only from the exact six-blob V3 graph,
canonicalizes ordering, and returns deterministic candidate bytes plus SHA-256.
It performs no file, network, or process I/O, persists nothing, keeps all seven
state fields false, and requires the existing validator to return the exact
dormant result before returning.
This is a proposal-construction API, not authentication, evidence verification,
receipt acceptance, blocker closure, or G1a authority.

The new
`docs/v1/g0/evidence-supporting-artifact-candidate-profile-v1.json` is a
17,353-byte custom profile at raw SHA-256
`f8ad6742fcb569f408b5f4087b20f11f32cb497a8f9eec2fc3f255d8b22c226f`.
It defines closed, compact, supplied-bytes-only envelopes for the two future
candidate artifacts while creating neither artifact instance. The
`reviewed_commit_scope` profile binds the exact `12c38154` parent/tree, all 18
ordered paths including `100755` script modes, blob IDs, byte lengths, raw
hashes, and scope-list digest. The `published_checkpoint` profile binds the
4,692-byte V3 checkpoint, commit blob, observed remote hash/window, and dormant
receipt sidecar while requiring a null standalone transcript reference. Both
profiles require session-observation-only trust, enumerate the missing
independent inputs, reserve verifier/provenance/hash fields for a later private
catalog validator, and keep all seven authority states false. The profile now
also hash-binds the exact item-2 owner/catalog selector snapshot and projects
its blocker, source, owner/evidence reference, candidate version, selector
index, reserved path, and false/null artifact state into each future envelope.
Any selector transition requires a new profile; an artifact instance remains
forbidden under this profile while its selector reference is null. The pure
validator reads only supplied profile, selector, and artifact bytes, rejects
snapshot/source/ref/version/path/presence drift, subject drift, injected
authority, unsafe or reordered scope, noncanonical JSON, and caller-buffer
mutation, and always returns a non-authorizing sentinel even for a valid
in-memory fixture.

The separate
`docs/v1/g0/baseline-gate-evidence-readiness-profile-v1.json` is a
19,697-byte readiness profile at raw SHA-256
`a0c8f45167e9a8f3a4fccbba65afbb928b29b88df2ea2090cc96043ba960af17`.
It derives the `g0_assurance_artifacts_and_baseline_gate` contract from the
unchanged six-blob effective V3 lineage and defines one common bounded envelope
for the five non-derived evidence kinds: two static assurance/source
observations plus the full no-device, Android release-compile, and macOS
release-compile result observations. The two executable plans are cross-bound
to their exact command-profile, ordered-argv, environment, toolchain,
side-effect, precondition, and step digests while both canonical profiles remain
`not_authorized`. Its pure compiler deterministically produces a 3,640-byte
`prepared_unverified_non_authorizing` plan at SHA-256
`ce679bbb4ebf01e4f838726d4c8f224e48cdd8170b3b205e89a4a54ce2d32227`;
all authority/runner references are null, all execution/acquisition flags are
false, and the plan is never written as evidence. The five candidate paths are
reserved but absent. The pure static compiler returns the fixed-order
`canonical_assurance_hash` candidate as 5,763 compact bytes at SHA-256
`2d193cb2f3bddf4d202129b4a746a3bd3cbba05f1a879e748f8001eb5c138db4`
and the `source_hash_readback` candidate as 10,771 compact bytes at SHA-256
`5df6ba51f3177424407078424fcff90dc2faa8d1c1d4e80e79e96486c3a54fc6`.
Its pair validator requires both exact kinds and shared profile, contract,
trust, state, and check binding while remaining dormant. The 22 mutation tests
supply and rehash the actual 29 source blobs and all synthetic execution-
manifest blobs, represent egress and
process observations as one canonical composite manifest, cross-bind every
payload digest to those immutable snapshots, require the full-gate success
marker exactly once, and reject source/lineage/manifest/profile/step/session/
time/state/raw-encoding/size drift plus mutable pair re-snapshot. Even an exact
shape returns one final dormant sentinel. No
`evidenceId`, verifier, provenance, authority, runner, gate, approval, catalog,
receipt, blocker-closure, G0-exit, or G1a state is created.

`script/check_v1_g0_independent_validation_context.py` now defines the private
candidate handoff boundary for the exact seven effective-V3 trust-input kinds.
Adapter results and the context are factory-owned opaque identities whose
deep-immutable payloads remain in module-owned stores; supplied canonical
subject and observation bytes are bounded and snapshotted once. The matcher
cross-binds the exact six lineage and remote checkpoint bytes, repository and
commit target, owner/approval and authority records, runner/gate records, all
fifteen artifact bytes, both runners' manifest/log bytes, and trusted-time
ceiling. Missing, reordered, duplicate, ambiguous, orphan, mutable, oversized,
or coherently self-asserted drift fails closed. All nine mutation tests pass,
including no-I/O/clock and malformed-context coverage. Exact synthetic input
still returns only the distinct candidate-only dormant sentinel. This module
implements no external trust adapter or consumed-bundle ledger, exports no
acceptance or activation API, and cannot close G0 or derive G1a.

`script/check_v1_g0_repository_remote_sources.py` adds a separate source-specific
boundary instead of treating the generic candidate factory as authentication.
Its default checker performs actual read-only inspection of the literal
`12c38154` Git object, exact parent/tree, all 18 scope entries, and the six
canonical lineage blobs. It reconstructs the scope from Git, recomputes object
IDs, byte lengths, raw/canonical hashes and the pinned scope digest, and rejects
replace refs, alternates, grafts, shallow or promisor/lazy-fetch state before
and after object reads without consulting HEAD, the index, or worktree document
bytes. This evidence collector intentionally supports only a normal checkout
with a complete local object store; shallow clones and linked worktrees fail
closed. Git stdout/stderr limits are enforced while streaming. The separate
remote matcher has no socket client and accepts only supplied, explicitly
unauthenticated bytes for mechanical conformance checks. Its eight tests cover
bounds, exact-byte binding, clock ordering, mutation failures, worktree/network
I/O absence, and 2/7 context rejection. No live HTTPS readback, remote-ref
reachability proof, authenticated collector/verifier, owner/registry/revocation
proof, trust-adapter result, or partial context exists.

The V3 consumed-bundle prerequisite remains deliberately unimplemented. A
caller-selected host-local directory and same-UID `O_EXCL` marker cannot provide
one global irreversible namespace: alternate directories, rename/replacement,
snapshot rollback, backup restore, multiple hosts, or an unauthenticated early
claim can permit reuse or permanent denial of service. Any future active ledger
must be separately provisioned under an authenticated sole writer/coordinator,
pin one versioned namespace, serialize all hosts, resist or reconcile rollback,
cross-bind only the canonical target/bundle accepted by the complete 7/7 trust
context, and prove parent-entry durability. No local marker implementation or
activation API is present in this worktree.

The immutable G0 machine records remain `blocked_before_g1a` as a historical
enterprise release state. Their ten recorded evidence gaps are:

1. published assurance/checkpoint owner acceptance plus
   separately authorized full no-device and release-compile passes;
2. activation-capable acceptance of the recorded publication observation;
3. production Android and macOS application namespaces;
4. actual Google Play, Apple Developer, and release-key owners;
5. a named provider-compatibility owner and versioned Ollama/LM Studio baseline;
6. owned service domains plus DNS and WebPKI lifecycle owners;
7. service-root, online-signer, rotation, and emergency-revoke owners;
8. privacy, retention, and incident owners;
9. named owners for the four quality measurement contracts;
10. initial relay region, projected peak, capacity target, and cost ceiling.

The active 2026-07-22 personal-project decision makes owner authentication,
role-scoped receipts, trusted-time proof, and an owner-governance ledger not
applicable. Those historical gaps do not block local source work, first-party
compilation, tests, or G1a no-network implementation. Production identifiers,
accounts, signing, live infrastructure, store upload, and deployment are later
release inputs. Socket and external-network work remains a separately bounded
technical decision.

`script/check_v1_g0_decision.py` hash-pins the inherited security decisions,
checks the current application/platform/locale baseline, and keeps G1a plus all
source-acquisition, library, compiler, socket, network, production-key, signing,
store-upload, and deployment authorities false. Its combined decision,
assurance, and closure-amendment mutation suite contains 63 tests; the separate
V1 checkpoint suite contains 11, the dormant publication suite contains 8, and
the V3 lineage/bundle, sparse-intake, and evidence-profile suite contains 17,
forming the earlier 99-test subtotal. The baseline-evidence readiness suite adds
22 tests to form the previous 121-test subtotal; the independent-context suite
adds 9 to form 130, the repository/remote-source suite adds 8 to form 138, the
owner-trust-bootstrap suite adds 11 to form 149, and the external-evidence
readiness suite adds 11 to form 160. The owner-trust-bootstrap v2 suite adds 25,
so the current ten focused G0 suites contain 185 tests total. Release
metrics fail closed without
an approved evidence signer and verifier, and percentile/scalar values are
recomputed from bounded, canonical signed samples. Required network variants
also bind one raw observation per attempt: affected plane/region, outage result
and route, ordered restore/authenticated-recovery phases, and zero downgrade
counts. Aggregate outcome fields are derived from those observations, so attempt
counts or a result string alone cannot satisfy an outage gate. No P2P candidate was selected and
no production key or credential was created.

The 25,552-byte
`docs/v1/g0/external-evidence-candidate-profile-v1.json` is pinned at raw
SHA-256 `8670a9c5a948b5c0e89ffd3fcd6561f4dcb51776a6d5c174f6a12c5a587c9848`.
It validates the exact existing five-kind baseline and two-kind supporting
profile bytes before subtracting those seven kinds from effective V3 and
deriving the remaining eight non-derived kinds. Typed candidate readiness is
therefore 15/15, but eight candidate artifacts remain absent. Every intake
selector is null/false, every trust and authority state is false, and each
candidate-reference field requires its own exact class, literal SHA-256, and
version. Root/signer candidates project both decision custody policies and a
distinct release-signing assignment; privacy includes the exact 30-second
expired-authorization deletion SLA; provider current and previous versions must
differ without forbidding minimum equals previous. The v1 currency set is
closed to a synthetic `KRW` fixture; selecting a real billing currency requires
a new v2 profile. The
profile and supplied-byte checker create no external value, authenticated owner,
catalog evidence, accepted receipt, blocker closure, G0 exit, or G1a authority.

## Current Verified Outcome

The immediate user-reported problem is fixed in the bounded local-development
scope:

1. A clean macOS debug app can start AetherLink Runtime and generate a visible
   QR without configured relay bootstrap material.
2. The visible QR is a valid `aetherlink://pair` payload with explicit
   `route_scope=local_diagnostic`, a nonloopback host, and the actual listener
   port.
3. Android debug camera/deeplink admission accepts that explicit local route;
   Android release builds continue to require canonical remote route material.
4. A physical `SM-S936N` camera scan recognized the displayed QR and completed
   pairing, trust admission, challenge-response authentication, and
   `runtime.health`. No URI or deep-link injection was used for the optical
   pairing claim.
5. Android force-stop and relaunch then rediscovered the runtime through
   Bonjour, authenticated with the stored trust relationship, and received
   `runtime.health` without rescanning.
6. After the phone was released, the final UI-only callback and macOS launcher
   fixes were reverified on the Mac: the app remained responsive, listened on
   port 43170, exposed accessibility ID `pairing-active-qr`, and its actual
   screen capture decoded to `192.168.0.113:43170` with local-diagnostic scope.
   That IP was a time-specific LAN address, not a value to persist or reuse.

## Root Causes And Final Design

### 1. macOS pairing never reached the renderer

The normal UI previously used only `remoteRequired`. A clean development host
without remote bootstrap, allocation, lease, or protected relay secret could
not create a `PairingSession`, so there was no payload for the QR renderer.

Final behavior in `CompanionAppModel`:

- `requestPairingForUserInterface()` prefers already-ready remote material.
- In a debug assertion build only, it may use an explicit local-diagnostic
  route when no complete remote route is ready.
- It starts the runtime when needed and generates a QR only after the transport
  reaches `advertising`.
- It validates a nonempty, nonloopback connection address and uses the real listener
  port.
- A constructor override cannot enable this path in a release build.
- The default connection-address selector rejects virtual interfaces and prioritizes
  SystemConfiguration's primary IPv4 interface before other physical
  candidates.
- A failed explicit remote preparation no longer traps the generic debug action
  in repeated allocator attempts; the generic action can recover locally.

### 2. Android recognized the QR but rejected it before pairing

The lower QR parser already supported explicit local diagnostics in debug, but
`MainActivity` hardcoded remote-route enforcement for the optical/deeplink entry
path. The camera could recognize a valid QR and still surface invalid, expired,
or failed pairing behavior before the view model received it.

Final behavior:

- `pairingQrRequiresRemoteRoute(isDebugBuild = BuildConfig.DEBUG)` returns
  `false` only for debug builds.
- Release remains remote-required.
- Tests prove the same compact local QR is accepted only when remote route
  enforcement is disabled.

### 3. Explicit Connection Recovery could call the generic action

After local fallback was introduced, `Generate Latest QR` in Connection
Recovery could receive a generic callback and silently generate a local QR.

Final behavior:

- Pairing and Status quick actions use the generic pairing decision.
- Connection Recovery uses a separately named remote-only callback.
- `PairingView`'s main QR button calls the generic action, while its nested
  Connection Recovery panel calls `requestRemotePairingForUserInterface()`
  directly.
- `StatusView` receives separate generic and remote callbacks from
  `ContentView`.
- Copy hygiene extracts and validates every callback block listed in the matrix;
  comments or string literals cannot satisfy the contract.

### 4. Ad-hoc macOS launches could stall or prompt for Keychain access

Changing ad-hoc signatures can make the Keychain runtime-identity path request
authorization and prevent the listener from becoming ready. LaunchServices
`open --env` also reproduced a startup stall while direct execution was healthy.

Final development-launch behavior:

- `script/build_and_run.sh` supplies an owner-only file-backed debug runtime
  identity outside the repository.
- It launches the signed bundle executable under `nohup`, waits through a fixed
  five-second launch-settle delay, and checks only that the exact launch PID is
  still alive before returning.
- `--verify` does not establish listener readiness, UI responsiveness, QR
  generation, or QR decode. Those require the separate process, port,
  accessibility, screenshot, and Vision checks below.
- Production runtime identity behavior remains Keychain-first.

## UI Callback Wiring Matrix

| Surface and action | Concrete wiring | Required behavior |
| --- | --- | --- |
| `PairingView` main `Generate Pairing QR` / `Generate New QR` button | `generatePairingQR()` -> `requestPairingForUserInterface()` | Ready remote route first; debug-only `local_diagnostic` fallback when remote material is unavailable. |
| Pairing nested Connection Recovery `Generate Latest QR` | `RemoteRelayRoutePanel` closure -> `requestRemotePairingForUserInterface()` | Remote-only route preparation; never silently falls back to a local QR. |
| Status Quick Actions pairing QR button | `StatusView.onGenerateRelayQRCode` -> `ContentView` -> `requestPairingForUserInterface()` | Same generic decision as the Pairing main button. |
| Status Connection Recovery `Generate Latest QR` | `StatusView.onGenerateRemoteRelayQRCode` -> `ContentView` -> `requestRemotePairingForUserInterface()` | Remote-only route preparation. |
| Main-window toolbar pairing QR command | `ContentView` -> `requestPairingForUserInterface()` | Generic decision and navigation to Pairing. |
| Menu-bar pairing QR command | `LocalAgentBridgeApp` -> `requestPairingForUserInterface()` | Generic decision and opening of the Pairing window. |

Do not simplify this to "PairingView is remote-only" or "all QR actions are
generic." Both statements are false and would reintroduce the recovery bug.

## QR Recovery File Map

Core macOS behavior:

- `apps/macos/CompanionCore/Sources/CompanionAppModel.swift`
  - generic UI pairing request
  - debug-only local allowance and release gate
  - listener readiness
  - local host selection and primary-interface priority
- `apps/macos/CompanionCore/Tests/LocalRuntimeMessageRouterTests.swift`
  - debug generation
  - failed listener closure
  - release override closure
  - explicit remote failure to generic local recovery
  - primary-interface scoring

macOS UI and render contracts:

- `apps/macos/LocalAgentBridgeApp/Sources/PairingView.swift`
- `apps/macos/LocalAgentBridgeApp/Sources/ContentView.swift`
- `apps/macos/LocalAgentBridgeApp/Sources/LocalAgentBridgeApp.swift`
- `apps/macos/LocalAgentBridgeApp/Sources/StatusView.swift`
- `apps/macos/LocalAgentBridgeApp/Sources/RemoteRelayRoutePanel.swift`
- `apps/macos/LocalAgentBridgeApp/Sources/Resources/*.lproj/Localizable.strings`
- `apps/macos/LocalAgentBridgeApp/Tests/AetherLinkLocalizationTests.swift`
- `apps/macos/LocalAgentBridgeApp/Tests/AetherLinkRenderSmokeTests.swift`

Android optical-entry policy:

- `apps/android/app/src/main/java/com/localagentbridge/android/MainActivity.kt`
- `apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt`
- `apps/android/app/src/test/java/com/localagentbridge/android/PairingQrScanResultTest.kt`

Supporting pipeline files to read even when they are not part of this QR diff:

- `apps/macos/Pairing/Sources/PairingCoordinator.swift`
  - canonical session and compact payload construction
- `apps/android/app/src/main/java/com/localagentbridge/android/PairingQrScanResult.kt`
  - camera frame classification and safe scan result
- `apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeClientViewModel.kt`
  - payload parsing, endpoint connection, pairing request, authentication, and
    trusted reconnect
- `apps/android/core/pairing/src/main/java/com/localagentbridge/android/core/pairing/RuntimePairingPayload.kt`
  - canonical compact/full payload and route policy rules
- `script/verify_pairing_qr.swift`
  - actual-screen QR decode and structural validation

Development launch and static contracts:

- `script/build_and_run.sh`
- `script/test_build_and_run.py`
- `script/test_documentation_handoff_guards.py`
- `script/check_copy_hygiene.py`

Current evidence and planning:

- `docs/handoff.md`
- `docs/v1/g0/decision-v1.md`
- `docs/v1/g0/decision-v1.json`
- `docs/v1/g0/assurance-checkpoint-readback-v1.json`
- `docs/v1/g0/assurance-closure-amendment-v2.md`
- `docs/v1/g0/assurance-closure-amendment-v2.json`
- `docs/v1/g0/assurance-closure-amendment-checkpoint-v2.json`
- `docs/v1/g0/assurance-closure-amendment-v3.md`
- `docs/v1/g0/assurance-closure-amendment-v3.json`
- `docs/v1/g0/assurance-closure-amendment-checkpoint-v3.json`
- `docs/v1/g0/assurance-closure-publication-receipt-candidate-v3.json`
- `docs/v1/g0/owner-catalog-input-candidate-v1.json`
- `docs/evidence/physical-qr-pairing-20260719.json`
- `docs/progress.md`
- `docs/qa-evidence.md`
- `docs/roadmap.md`
- `script/check_v1_g0_checkpoint.py`
- `script/test_v1_g0_checkpoint.py`
- `script/check_v1_g0_decision.py`
- `script/test_v1_g0_decision.py`
- `script/check_v1_g0_publication_receipt.py`
- `script/test_v1_g0_publication_receipt.py`
- `script/check_v1_g0_receipt_bundle.py`
- `script/test_v1_g0_receipt_bundle.py`
- `script/check_docs_hygiene.py`

## Published G0 Packet And Receipt/Input Candidate Map

The earlier QR, persistence, and security-governance work is part of the
published `d32c1846` baseline. The bounded V2/V3 contract and validation packet
is published at `12c38154`; all V1/V2/V3 lineage bytes remain unchanged. The
following exact nine-file successor is published at `70350f5e` and passed
fresh 9/9 remote byte readback. The manifest serialization is deterministic:
sort paths as raw bytes under `LC_ALL=C`; hash each exact commit blob; emit one
line as `<lowercase SHA-256><two ASCII spaces><path><LF>`; concatenate those
lines in path order; then SHA-256 the complete manifest bytes.

```text
ab692ed38ba2697ff7cff141d1311e4eeffdde32043aad1ca79c3b578ad997d3  docs/handoff.md
8b7faa8cf687250042845e8fd6ba5228cf8b6026653897c20c6194ab3b4831e9  docs/progress.md
0f780e9ac2e7a345f91b007e4ee74033fa8d1f2f72eff8cf41612c5e91e824e4  docs/qa-evidence.md
3251e8de622f49abb0e42b2112a0cffa77467d515169372ed6dfc10bb307a860  docs/roadmap.md
d9d6c43713a4550f88080306a0150a6a7325f7575e369b2d80cd18902b272856  docs/v1/g0/assurance-closure-publication-receipt-candidate-v3.json
fa8037c975e76c64c7a3e6e33274c6ac7a91f49c49b5ec35e0133477972d35a0  docs/v1/g0/owner-catalog-input-candidate-v1.json
6e34c3fed2027a9d3729db11537466a37ca6cdc259542bea8abdfd94bc3f55b7  script/check_no_device_quality.sh
c4605bfb5f2c50799b4f0951c94fa96b7960a3bd721a3f68666aaebcd2159f5b  script/check_v1_g0_receipt_bundle.py
2c90e70b7424e9c3a63281fec7c98f2c2a5c8ffa390f5f1309175488edc67622  script/test_v1_g0_receipt_bundle.py
```

Those bytes produce manifest SHA-256
`feffe729aba826c4692fb408f9e4b4f42f7f4823f92dc6325587c0aac7a8dd46`.
The manifest is reproducible from commit `70350f5e`. The fresh HTTPS fetch,
no-alternates check, timestamps, and nine remote-versus-commit comparisons are
a separate session observation; no standalone acquisition transcript or trusted
receipt is persisted, so the repository cannot independently replay that
observation.

The subsequent exact seven-file truth-sync and dormant preview-compiler scope
is published at `025a4ef5e6c3e52c46a6b79ee3a06a6eb47de4e0`, with parent
`70350f5e9e5e39d1b793862c1e58d09edf637405` and tree
`e1272bdf9346161c904e6e3adc1ef9e25865197d`. It uses the same canonical
`<lowercase SHA-256><two ASCII spaces><path><LF>` manifest serialization:

```text
d76b393a6fc1df0cd72b195b00a7d758db97236e1f4a31543c09285c04c8b372  docs/handoff.md
751e13f585dec928252bb5cd16d91ddb9f58c1cf031ab406425ea233e02e51dd  docs/progress.md
2bb73ceffa8148bd34e48a1dcf4c64d06c5645a9d9948759793dd7ad6d0ce88c  docs/qa-evidence.md
af01f6e6f2c75a354e4258b1b9e3b63652b5bce84c40ac01f96ac29de04489d4  docs/roadmap.md
41937293cb9bf71cc294cdd31db4f5b58ec936b456abc16d8635b9eea0884e57  script/check_no_device_quality.sh
939c4c84e66eb5b77538684e7e3d7784dfc10fb720772ae901b85c4c072d8c4d  script/check_v1_g0_receipt_bundle.py
63eb3ce9c2cca37c21f3dcc2717f2c21ce256110ef621a63099f05871c5fd48b  script/test_v1_g0_receipt_bundle.py
```

Those bytes produce manifest SHA-256
`d534e068f412bed2ea4926f5eb206b6a4343fa4ed8d04f87c11193bc4a5cdb25`.
A fresh HTTPS `blob:none` partial clone with no object alternates resolved remote
`main` to that exact commit from `2026-07-21T01:15:22Z` through `01:15:28Z`.
The clone first matched the commit, parent, tree, ordered seven-path diff, modes,
and blob IDs, then lazy-fetched only those seven blob contents and matched their
byte counts and raw SHA-256 values. This remains a session observation rather
than a persisted independent trust receipt and changes no owner, evidence,
activation, G0-exit, or G1a state.

The subsequent exact sixteen-file successor is published at
`b24c5ecb77067539c185d88f0c2fbbc2cb119c15`, with parent
`025a4ef5e6c3e52c46a6b79ee3a06a6eb47de4e0` and tree
`c8aa9e69cbbe7f72374a33713f11902e6f2e21bb`. It uses the same canonical
manifest serialization:

```text
870aa81cb8e4ec9a726e20aebe4eb21e158691be85fc3917a0152c5afaf0df7e  docs/handoff.md
4197d7cb11a1dd8d55fb6a991c3d63db024b95d79847fb79911ccec00cf117f6  docs/progress.md
ac23780ad750bc412267a14717af8787655ccd72be08d2ba5cdd3a539af66c95  docs/qa-evidence.md
2ee2897ba41a5e0685c6254d74d367feb6b54e26e94943fc41c798d5231cbbad  docs/roadmap.md
a0c8f45167e9a8f3a4fccbba65afbb928b29b88df2ea2090cc96043ba960af17  docs/v1/g0/baseline-gate-evidence-readiness-profile-v1.json
f8ad6742fcb569f408b5f4087b20f11f32cb497a8f9eec2fc3f255d8b22c226f  docs/v1/g0/evidence-supporting-artifact-candidate-profile-v1.json
0221d2d49e4bcccfd34fb6905102117fbf5632e27d3d2f2e23d53e29f47752bc  docs/v1/g0/owner-catalog-input-candidate-v1.json
dff40a2aa6f53f7cbefb1c2b3eedcdb182c45170c447fbe4d298c73ab1561baa  script/check_no_device_quality.sh
f32e233512af265b2dd0c0c0a4df570c7a798773ae095326bb37f1c9b0910414  script/check_v1_g0_baseline_evidence_readiness.py
2ef51168b62baedf28cb3d0456dcc30d1ee4b88bbbfa81c912ccb73d5745d50f  script/check_v1_g0_independent_validation_context.py
afc1c3776486053cb4886b80c7121e0e6927138ba048bf8709b22d60de6d43cc  script/check_v1_g0_receipt_bundle.py
89f518312cafe24db094e8af8774cb53a9786b0ab300803ad8c27e0d5bd888f4  script/check_v1_g0_repository_remote_sources.py
f78a7d35cc97e3fd5b7d9088c137faa2116704bcf5bcab5064f18c6c48950dd5  script/test_v1_g0_baseline_evidence_readiness.py
d217a2b533d374c499000b70314f471a11fdfb31ac4ac644456383b13d636a81  script/test_v1_g0_independent_validation_context.py
2a3bc9dd36a6df85f0340e95f268886036b2d79d97c384a2191fd45775b558a0  script/test_v1_g0_receipt_bundle.py
7f25e5fd825b5d05e8147832b9ded74157747b5d39fb1500a7a79a411228d807  script/test_v1_g0_repository_remote_sources.py
```

Those 1,706 manifest bytes produce SHA-256
`1b91a321de9a39faf9fb519b47ffa6e82ce85dd48595f092a63581875c9d4a37`.
A strict fresh HTTPS `blob:none` clone observed remote `main` at that exact
commit from `2026-07-21T07:55:12Z` through `07:55:22Z`. All sixteen target
blobs were absent with lazy fetch disabled before acquisition; after explicit
readback, every blob byte count, raw SHA-256, and recomputed Git object ID
matched the local exact-OID object. The 274-byte commit, 297-byte parent commit,
and 787-byte root tree also matched their local raw bytes and recomputed object
IDs. The in-session 9,265-byte canonical command transcript had SHA-256
`98d08c6bd76289c4d89218d689d50e788cc8b4167b559cb618ddd7c9ae886690`,
but its bytes were not persisted or signed. Therefore this is independently
acquired only with respect to the existing worktree and local object database;
it is a bounded session observation, not an authenticated independent collector
receipt, owner acceptance, evidence verification, receipt activation, G0 exit,
or G1a authority.

The immutable `70350f5e` commit subject and later generic `b24c5ecb` subject do
not describe their G0-only scopes; the exact parents and reproducible manifests
above are the canonical commit-scope records. All five remote readbacks remain
bounded session observations. The latest twelve-file owner-trust-bootstrap/
external-readiness slice at `4227204` has a completed 12/12 public HTTPS
commit/tree API, raw-content, and `git ls-remote` readback. Remote `main`, parent
`b24c5ecb`, tree `c321c33e`, and all target bytes matched from
`2026-07-21T12:34:24Z` through `12:34:32Z`; its unpersisted, unsigned 1,857-byte
manifest SHA-256 is
`267be3ca8f56fe353fbb856f95c6f634e98afbc3f204b589a9935be0fe5b0a15`.
That twelve-path publication remains historical. The current unpublished scope
is the personal-governance synchronization plus the socket-free G1a-A/B/C/D
Swift and Kotlin contracts, five shared fixtures, pair/endpoint-ledger
persistence, transition history, legacy-downgrade guards, dormant internal pre-
connector admission seams, G1b-A stack-neutral ownership work, the G2 Pion
preflight and restricted-fork rung-one design/checker portfolio, tests,
documentation, and gate integration described in the snapshot.

The historical sidecar, one-response dormant intake envelope, profile, and
scripts structurally validate the exact recorded candidate values without
reconstructing remote acquisition provenance, authenticating an owner,
verifying evidence, or accepting the proposed disposition; every later
authority remains closed.

The published nine-file set contains no actual
local username, device serial, private LAN address, credential, or personal
contact. If repository visibility changes or these full historical documents
are exported to a new audience, run a separate history-wide redaction review;
older tracked evidence contains environment-specific identifiers.

Practical review rule:

```bash
git diff -- <specific-file>
git diff --stat
git status --short
```

Review and stage by explicit file list. Do not use a broad diff as evidence that
all current changes form one atomic feature.

## Evidence Ledger

### Current 2026-07-21 V1 G0 and physical Android evidence

- The integrated G0 checker passes against nine decision source hashes, 29
  assurance source hashes, the live Android/macOS configuration and locale
  baseline, and protocol-schema message/error parity.
- Its 63 mutation tests pass and reject premature G1a/network/deployment
  authority, nested unknown fields, security downgrades, missing hard stops,
  fallback or platform drift, network-cell/variant/measurement-contract/blocker
  removal, missing protocol/threat/user-loop inventory, forbidden observability
  fields, invented approvals, evidence-free checklist passes, and weakened
  human wording.
- The bounded G0 V2/V3 packet is intentionally published at `12c38154`. A fresh
  no-alternates repository matched all 18 approved remote file bytes, including
  the 4,692-byte V3 checkpoint at SHA-256
  `37462cd8303ce61742bc480d0f7d37e0ccb380ec12375cc8c8d10169aebf4dc5`.
  The receipt-bundle suite passes 17 tests, the earlier four focused G0 suites
  form a 99-test subtotal, the 22-test baseline-evidence readiness suite forms
  the previous 121-test subtotal, the 9-test independent-context suite forms
  130, the 8-test repository/remote-source suite forms 138, the 11-test
  owner-trust-bootstrap suite forms 149, the 11-test external-evidence readiness
  suite forms 160, and the 25-test owner-trust-bootstrap v2 suite brings the
  current ten-suite total to 185, with
  the tracked receipt sidecar
  remaining exactly `dormant_non_authorizing` and the current one-response sparse intake
  envelope remaining exactly `draft_unverified_non_authorizing`; neither
  authenticates an owner, verifies catalog evidence, accepts the proposed
  disposition, activates a receipt, or independently reproduces the session's
  remote acquisition provenance. The exact non-authorizing artifact profile is
  hash-pinned, both reserved artifact instances remain absent, and valid
  in-memory fixtures still return only the mandatory dormant sentinel. The
  published `70350f5e` intake blob remains the distinct historical empty
  envelope.
- The external-evidence candidate profile is the 25,552-byte file at raw
  SHA-256 `8670a9c5a948b5c0e89ffd3fcd6561f4dcb51776a6d5c174f6a12c5a587c9848`.
  Its checker content-addresses the prior five-kind and two-kind profiles plus
  the six lineage files, derives the remaining eight effective-V3 kinds, and
  proves typed readiness for 15/15 kinds while eight candidate artifacts remain
  absent. Its eleven tests and the nine directly executable G0 checker
  invocations pass; the publication-receipt checker/test pair is exercised
  through its suite and intentionally has no executable `main`. This
  result is limited to a synthetic, unverified, non-authorizing schema boundary;
  it does not authenticate an owner, supply an external fact, verify evidence,
  accept or activate a receipt, close G0, or grant G1a.
- The earlier pre-v2 complete expanded default no-device aggregate exited zero
  after the then-final profile/checker/test bytes were present and before its
  evidence-only wording correction. Its initial Python batch ran 192 tests; all
  1,809 Swift tests
  completed with two environment-dependent skips and zero failures; all 23
  macOS render smokes, selected offline Android suites/build tasks, and both
  Swift products passed. The aggregate stdout was not persisted or signed.
  Fresh copy/docs/diff guards, not that aggregate, cover the current document
  bytes.
- A later v2-inclusive but pre-final-hardening complete default no-device
  aggregate also exited zero. Its initial Python batch ran 207 tests, followed
  by the same 1,809-test Swift, 23-render-smoke, selected offline Android, and
  Swift-product stages. It covered the earlier 15-test v2 suite, not the ten
  later registry/type/SSHSIG hardening tests; its temporary stdout was deleted
  because it contained ephemeral pairing material and was neither persisted nor
  signed.
- The final post-hardening complete default no-device aggregate also exited zero
  on the current 25-test v2 bytes. Its initial 217-test Python batch passed, as
  did the gate's full-Swift completion assertion, render-smoke, selected offline
  Android, Swift-product, copy/docs, and final success-marker stages. The
  temporary stdout was deleted because it contained ephemeral pairing material
  and was neither persisted nor signed.
- The exact nine-file receipt/intake successor is published at `70350f5e`. A
  distinct fresh no-alternates HTTPS fetch matched all nine remote bytes from
  `2026-07-20T13:54:08Z` through `13:54:12Z`; its ordered remote file-manifest
  SHA-256 is `feffe729aba826c4692fb408f9e4b4f42f7f4823f92dc6325587c0aac7a8dd46`.
  This publication does not rebind or activate the parent-targeted receipt and
  changes no owner/catalog/G0/G1a state.
- The exact seven-file truth-sync/compiler successor is published at
  `025a4ef5`. A fresh no-alternates HTTPS `blob:none` partial clone matched the
  commit, parent, tree, ordered path set, modes, blob IDs, byte counts, and all
  seven raw blob hashes from `2026-07-21T01:15:22Z` through `01:15:28Z`; its
  canonical manifest SHA-256 is
  `d534e068f412bed2ea4926f5eb206b6a4343fa4ed8d04f87c11193bc4a5cdb25`.
  Publication and readback grant no owner, evidence, execution, or transition
  authority.
- The non-socket static batch passes: copy hygiene across 92 user-facing files,
  docs hygiene across 12 current documents, Android and macOS five-locale parity,
  protocol schemas, the closed P2P/NAT and production-relay design validators,
  21 documentation/launcher/Phase-A unit tests, shell syntax, and diff hygiene.
- The complete integrated no-device aggregate was rerun on the current G0 scope
  and exited zero with its final `No-device quality checks passed.` marker after
  the full Swift, Android, QR, and local-development relay checks. Its interactive
  output was not persisted or signed, so this remains bounded session evidence
  and does not authenticate an owner, authorize execution, or close G0/G1a.
- On the connected `SM-S936N`/Android 16 device, `:app:assembleDebug` completed
  92 tasks successfully, `adb install -r` preserved app data, and cold launches
  completed in 632 ms and 612 ms. The unpaired and Settings views rendered at
  1440x3120 with 54 and 62 nodes; force-stop removed the PID, relaunch allocated
  a new PID, and the saved trusted-runtime/QR-required/auto-reconnect state was
  visible again. Three local development relay smokes then passed: pairing plus
  reconnect, physical UI send/delta/cancel/done plus five-screen capture, and
  send/three-delta/natural-done plus reconnect. App chat/model/drawer/settings
  XML had zero enabled unlabeled click targets and zero out-of-screen bounds.
  CAMERA revoke reached the Android permission dialog and the cleanup trap
  restored `granted=true`; actual denial-after-dialog recovery was not completed.
  USB ADB briefly re-enumerated during early capture and recovered. No production
  credential, signing identity, store action, external relay, production
  service, or deployment was used.

### Current 2026-07-20 optimization evidence

- Android runtime session-summary merge lookup is linear in incoming summaries,
  persisted sessions, and deletion suppressions. A deterministic counting-list
  regression uses 1,003 persisted rows and 1,001 suppression rows while also
  proving first-wins legacy state, local collision, and deletion behavior.
- Three focused merge regressions and all 634 `RuntimeClientViewModelTest` tests
  pass. `build/qa/android-session-summary-linear-full-20260720.log` records the
  broad Android run and debug assembly succeeding in 30 seconds; the refreshed
  JUnit XML reports contain 1,141 app, 162 protocol, 95 transport, and 130
  pairing JVM tests with no skips or failures.
- The standalone documentation-handoff guard passes 11/11 after its Status
  fixture was aligned with `performRuntimeOverviewAction`. Copy/docs hygiene,
  macOS localization parity, shell syntax, and `git diff --check` pass.
- `build/qa/check-no-device-quality-session-summary-linear-final-20260720.log`
  exits zero across 8,806 lines in 580.459 seconds. It records the overall
  success marker and session-summary linear-merge marker once each, 1,809 Swift
  tests with two explicit environment-dependent skips and zero failures, the
  complete Android ViewModel selection, authenticated direct/relay smokes, and
  both Swift product builds. None of this local evidence is physical-device or
  external-network proof.

### Physical Android evidence completed

The following was observed on one `SM-S936N` on the same Wi-Fi as the runtime
host:

- Debug APK installation and foreground launch.
- Physical camera scan of the QR actually shown by AetherLink Runtime.
- Android log source `PairingQr` connecting to the QR endpoint.
- `pairing.request` sent and `pairing.result` received.
- hello sent, `auth.challenge` received, `auth.response` sent and received.
- `runtime.health` sent and received.
- macOS reported one trusted device.
- After force-stop/relaunch, log source `BonjourDiscovery` connected to the same
  runtime identity and repeated authentication plus `runtime.health`.

The sanitized manifest at
`docs/evidence/physical-qr-pairing-20260719.json` records the device/OS class,
dirty source revision, debug build variant, same-Wi-Fi topology, on-screen QR
digest, observed protocol milestones, retention state, and explicit limits. It
contains no device serial, full QR URI, pairing code, nonce, secret, token, or
private identity material. Because the raw logcat and screenshot were not
retained, the manifest is a bounded record of the observed session rather than
independent replayable proof. Docs hygiene rejects duplicate JSON keys, enforces
an exact closed schema, rejects sensitive keys and credential-like string
values, pins every safe value, and requires its QR digest to match the current
progress and QA records.

This proves one same-Wi-Fi debug route. It does not prove a different network,
remote relay, production route, multiple devices, or every camera condition.

### Mac-only verification after the phone was released

- Final ad-hoc app build, deep signature verification, and stable launch.
- Listener observed on TCP 43170.
- Final live UI exposed `pairing-active-qr`.
- The actual screen QR decoded as one valid `aetherlink://pair` URI with 11 query
  keys, local-diagnostic scope, primary-interface host, and listener port.
- No QR payload, pairing code, nonce, relay secret, or token was committed.
  No payload or screenshot artifact was retained in the repository, and the
  assistant-created `/tmp` payload/screenshot copies were removed.
- The physical logcat stream and complete QR payload were intentionally not
  retained as durable artifacts. This section records an observed run, not a
  replayable cryptographic evidence bundle.
- `build/qa` is ignored local output. Existing historical v3-v5 no-device logs
  predate the final local-debug QR path and cannot substitute for a new physical
  run from another checkout, build, device, or network.

### Completed automated evidence

- `LocalRuntimeMessageRouterTests`: 525/525 passed before the final review
  remediations. The final five QR policy/route regressions then passed 5/5.
- `AetherLinkLocalizationTests`: 137/137 passed after final UI wiring.
- Active QR render: all five languages and three appearances rendered; Vision
  decoded the English/light bitmap to the exact active compact payload.
- Primary companion surfaces: all five languages and three appearances passed,
  including Connection Recovery.
- `swift build -c release --product AetherLink` passed on final source.
- Android focused QR policy/parser tests passed.
- Android `:app:assembleRelease` passed including `lintVital`.
- Android `:app:installDebug` passed on the attached phone before it was
  disconnected.
- Final documentation refresh checks passed: docs hygiene across 12 current
  docs, copy hygiene across 91 source/resource files, five-locale macOS parity,
  all three launcher unit tests, 11 handoff contract mutation tests, manifest
  JSON parsing, the 13-artifact P2P/NAT security design validator, all seven
  Phase A progress tests, the 17-artifact production-relay design validator,
  shell syntax, and `git diff --check`.
- Final GPT-5.6 Sol review reported no remaining P0-P2 finding.

Do not convert the earlier 525/525 result into a claim that the entire suite was
rerun after every UI-only or documentation edit. Rerun the full selection when
future core behavior changes and before committing or publishing this combined
core/UI recovery:

```bash
swift test --filter LocalRuntimeMessageRouterTests
```

## Debug And Release Evidence Matrix

| Scope | Debug evidence completed | Release evidence completed | Still not established |
| --- | --- | --- | --- |
| macOS | Focused model policy tests; ad-hoc app build and exact-PID launch; listener observed on 43170; live accessibility ID; actual screen QR decoded as `local_diagnostic`. | `swift build -c release --product AetherLink`; test-only release gate proves constructor overrides cannot enable local fallback. | Installed/notarized distribution build, release UI pairing, deployment signing, and production remote-route operation. |
| Android | Focused parser/policy tests; `:app:installDebug`; physical camera pairing, authentication, health, and stored-trust Bonjour reconnect on one `SM-S936N`. | `:app:assembleRelease` including `lintVital`; release policy tests require remote route material. | Installing the release APK, scanning with its camera path, release-to-release pairing, broader devices, and production deployment. |
| Cross-platform | One same-Wi-Fi debug optical pairing and trusted reconnect. | No release end-to-end cross-platform run was performed. | Different-network, external relay, P2P/NAT, Phase B, production capacity/reliability, or readiness. |

Compilation and policy tests are not a substitute for installing and exercising
release artifacts. The physical claim in this handoff is explicitly a debug
APK paired with the development macOS app.

## Focused Verification Commands

### macOS core QR regressions

```bash
swift test --filter 'LocalRuntimeMessageRouterTests/(testCompanionAppModelDebugUserInterfaceGeneratesLocalDiagnosticQRCodeWithoutRemoteRoute|testCompanionAppModelDebugUserInterfaceDoesNotGenerateQRCodeWhenRuntimeListenerFails|testCompanionAppModelReleaseUserInterfaceDoesNotEnableLocalDiagnosticFallback|testCompanionAppModelDebugUserInterfaceUsesLocalDiagnosticAfterExplicitRemoteFailure|testCompanionAppModelLocalPairingInterfaceScorePrefersPrimaryPhysicalRoute)'
```

### macOS localization, render, and release

```bash
swift test --filter AetherLinkLocalizationTests
swift test --filter AetherLinkRenderSmokeTests/testActivePairingQRCodeRendersAtCompactDetailSizeAcrossLanguagesAndAppearances
swift test --filter AetherLinkRenderSmokeTests/testPrimaryCompanionSurfacesRenderAtMinimumDetailSizeAcrossLanguagesAndAppearances
swift build -c release --product AetherLink
```

### Android debug/release QR policy

Use Android Studio's JBR:

```bash
JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" \
ANDROID_HOME="$HOME/Library/Android/sdk" \
./gradlew --no-daemon :app:testDebugUnitTest \
  --tests com.localagentbridge.android.AppNavigationTest.pairingQrRoutePolicyAllowsLocalDiagnosticOnlyInDebugBuilds \
  --tests com.localagentbridge.android.PairingQrScanResultTest.compactLocalDiagnosticQrIsValidOnlyWhenRemoteRouteIsNotRequired \
  -Pkotlin.incremental=false

JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" \
ANDROID_HOME="$HOME/Library/Android/sdk" \
./gradlew --offline --no-daemon :app:assembleRelease -Pkotlin.incremental=false
```

### Build and inspect the live macOS app

This is not a read-only check. It rebuilds `dist/AetherLink.app`, terminates an
existing AetherLink process, launches a new process, and may create or reuse the
owner-only debug identity file outside the repository.

```bash
./script/build_and_run.sh --verify
pgrep -fl '/dist/AetherLink.app/Contents/MacOS/AetherLink'
lsof -nP -iTCP:43170 -sTCP:LISTEN
```

Generate the QR through the actual UI. For a screenshot captured from the live
window, validate the displayed code rather than a frame-only fixture:

```bash
script/verify_pairing_qr.swift --image <actual-aetherlink-window-screenshot>
```

The verifier prints the complete payload. Treat its output as sensitive and do
not paste it into docs, logs, commits, or chat. Record only safe fields such as
scheme, action, query-key count, route scope, host/port, and a payload digest.

### Full no-device gate

Run only when broad fresh-source evidence is needed. It is intentionally much
slower than the focused commands:

```bash
JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" \
ANDROID_HOME="$HOME/Library/Android/sdk" \
bash script/check_no_device_quality.sh
```

Inspect the final log and exit status before claiming completion. A started or
partially observed gate is not a passing final-source result.

## Physical Device Procedure For A Future Session

Run this only when `adb devices -l` reports an authorized device and the user
has said the phone is connected.

1. Confirm the runtime host and phone are on the intended network.
2. Install the current debug APK; installation alone is not pairing proof.
3. Launch the current macOS app and generate the QR through its UI.
4. Decode the actual on-screen QR separately to prove render correctness.
5. Scan with the physical camera. Do not inject the URI if claiming optical
   proof.
6. Verify `PairingQr`, `pairing.request`, `pairing.result`, hello,
   `auth.challenge`, `auth.response`, and `runtime.health` in logs.
7. Confirm the runtime reports the trusted device.
8. Clear logcat, force-stop, and relaunch Android.
9. Verify `BonjourDiscovery`, stored-trust authentication, and
   `runtime.health` without rescanning.
10. Record device model, OS/API, network topology, exact build, and proof
    boundary. Do not persist secrets or the full QR payload.

## Not Yet Proven

Do not claim the following from the current evidence:

- Expired or rotated QR recovery on a physical device.
- Camera denial and permission regrant recovery.
- Real TalkBack or VoiceOver traversal.
- Physical rendering across more Android models or OS versions.
- Network handoff during an authenticated session.
- Pairing while the devices are on unrelated networks.
- Live external relay allocation or production relay operations.
- P2P/NAT traversal, ICE/STUN/TURN behavior, Phase B, or deployment.
- An upstream production P2P producer or actual endpoint stack, execution of the
  macOS accepted-raw listener, actual socket close interruption, or
  `CompanionAppModel` integration of that primitive.
- Production performance, capacity, reliability, or readiness.
- Live provider-backed chat/cancel as part of this QR recovery proof.

## Authority And Security Boundary

- The new local QR is debug-only and must remain explicitly
  `local_diagnostic`.
- Release/default product pairing remains remote-required.
- Connection Recovery remains the explicit remote-route path.
- No source-acquisition, native-library execution, socket destination,
  runtime-network, external-egress, P2P Phase B, production-network, or
  deployment authority was expanded.
- The canonical P2P/NAT authority records are:
  - `docs/security-hardening/production-p2p-nat-v1/controlled-network-spike/phase-a/progress-v8.json`
  - `docs/security-hardening/production-p2p-nat-v1/controlled-network-spike/decision-v6.json`
  - `docs/security-hardening/production-p2p-nat-v1/implementation/handoff-v9.json`
- Those records reject both `libjuice-1.7.2-static-c-abi` and
  `libnice-0.1.23-glib-c-abi` before compile and leave the selected networking
  library `null`. The exact one-shot acquisition authorities are consumed;
  compile-only integration was not run.
- The historical G2 preflight
  `docs/security-hardening/production-p2p-nat-v1/g2-requirements-review-v1.md`
  also rejects unmodified Pion ICE v4.3.0 at exact commit
  `1e8716372f2bb52e45bf2a7172e4fb1004251c46` as-is at official-source
  preflight. At that checkpoint it selected no library, retained no Pion source, and opened no
  compile, load, socket, network, device, Git, or deployment operation.
- Its historical follow-up
  `docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/`
  portfolio completed only the rung-one candidate-shape decision. At that
  checkpoint the minimal policy-owned fork could be used to prepare a separate
  rung-two provenance and acquisition record; it was not a selected or acquired
  dependency. The focused
  validator and 17 mutation tests pass with every execution scope false.
- The 13-artifact P2P/NAT source-evidence collection was integrity-refreshed
  after the QR changes to `CompanionAppModel.swift`; its current collection
  SHA-256 is
  `6e6dfbfc0cdb70370c30f54222584b69042a6e22b6df04c7f3e65043c38522bd`.
  `check_p2p_nat_security_design.py` and all seven Phase A progress tests pass.
  This is source-freshness synchronization only and grants no authority.
- The historical Phase A fields `implementationAuthorized=false`,
  `compilerInvocationAuthorized=false`, `socketCreationAllowed=false`, and
  `runtimeNetworkIOAllowed=false` remain false and superseded as current
  candidate guidance. The current restricted-fork profile additionally fixes
  `candidateSelected=false`, `librarySelected=false`,
  `sourceAcquisitionAllowed=false`, `dependencyInstallationAllowed=false`,
  `compilerInvocationAllowed=false`, `codeLoadingAllowed=false`,
  `socketCreationAllowed=false`, `networkIoAllowed=false`,
  `deviceExecutionAllowed=false`, `productionDeploymentAllowed=false`, and
  `gitOperationAllowed=false`. The succeeding rung-two decision has now consumed
  exactly one bounded request without selecting a library. Rejected authority
  cannot be reused implicitly, and
  no repository-owner, GitHub, SSH, GPG, public-key proof, or additional user
  decision is required; `externalIdentityProofRequired=false` and
  `userActionRequired=false`.
- AetherLink remains local-first. The client never calls Ollama or LM Studio
  directly; AetherLink Runtime mediates provider access.
- Network reachability is not authorization. Pairing, trusted-device records,
  challenge-response, and encrypted runtime sessions remain required.
- Never commit QR payloads, pairing codes, nonces, relay secrets, allocation
  tokens, runtime identity private material, provider URLs, or device-specific
  credentials.

## Recommended Next Session Flow

Unless the user redirects the task, use this decision order:

1. Re-read this handoff and refresh Git, device, and process state.
2. Preserve historical G0/owner-trust bytes, but do not run an owner-
   authentication workflow or ask the user for authentication evidence.
3. Treat the completed G1a-A route/transcript, G1a-B pair-state/admission, and
   G1a-C signed authority/candidate/receipt/grant contracts as the base; do not
   duplicate or activate their canonical objects as JSON messages.
4. Treat dual-platform compound endpoint-ledger persistence, trusted-time token
   issuance, the exact-bound coordinator, G1a-D KDF/confirmation/record/rekey,
   and the authority-bound process-local publication lifecycle as complete no-
   network foundations. The normal Android graph now owns an empty exact-store/
   exact-clock activation controller, and injected real-fixture manager/ViewModel
   E2E proves composition without a socket. macOS owns a tested loopback-only
   accepted-raw primitive that is not `CompanionAppModel`-wired or socket-
   executed. The eventual adapter must keep `seal + channel.send` inside one
   publication read permit. Never derive authority from an
   unverified transcript, capability digest, raw object 26, independently
   supplied connector route, or readback-only retry.
5. The G2 v3 lexical inventory remains the predecessor at
   `rung3_v3_publication_read_back_complete`. Semantic-review v1 has completed
   two non-attesting full-coverage passes and independent tracked readback at
   `rung3_semantic_source_review_v1_publication_read_back_complete_semantic_closure_blocked`.
   Its 29 candidates produce 19 findings, with seven patch-required and twelve
   unresolved. Patch/dependency decision v1 completed that preparation, and the
   historical dependency-review decision selected only the staged fixed-point
   source-closure plan. The predecessor wave-one preparation decision binds the
   exact 19 source identities, four quarantined checksum-only context tuples,
   both V1 build profiles, and bounded request/output rules. Its checker and
   56/56 mutation tests pass. The checker also rehashes the retained root ZIP,
   embedded module metadata, and source tree, proves premature wave artifacts
   absent through its final barrier, and binds exact H1/source-set digest
   algorithms. Its recorded permit-preparation action is complete. The
   historical v1 runner still passes 44/44; its permit suite recorded 38/38 at
   the unconsumed checkpoint and now reruns 36 state-independent cases. V1 is
   consumed after the terminal ratio-policy failure. Recovery-v1 passes 31/31
   tests; v2 was subsequently consumed by tuple-11 `E_GO_MOD_MISSING`, with no
   final set. Recovery-v2 and its 39/39 mutation tests select a fresh
   `.mod`-then-`.zip` v3 design. The separate one-use permit was consumed
   exactly once: 38 requests and 38 bodies produced 19 verified `.mod`/`.zip`
   pairs. Independent readback is complete, and the verification-only v3
   checker confirms the fixed 43-file set without exposing record authority.
   Source-review v1/v2 then failed closed without a partial result; v3 and its
   independent readback recorded the exact 15-tuple frontier. Wave2 decision
   v1 completed that recorded preparation action: 15/15 parent declarations
   and all 30 held-H1 expectations are exact, while future bytes remain
   unacquired. Its exact
   `nextAction=prepare_separate_versioned_wave2_checker_runner_tests_and_one_use_execution_permit`,
   without retrying prior waves or asking for user authentication.
   Semantic
   review was performed, but semantic closure, dependency closure, rung-three
   completion, candidate selection, and library selection remain false. Android verified-endpoint handoff and macOS
   `CompanionAppModel` listener wiring may continue as stack-neutral ownership
   work, but the actual P2P backend and socket proof wait for their G2 scopes.
   The accepted dependency source set is intake evidence only; materialization,
   reviewed-source compile/execution, runtime network, Git, device, or other
   user action remains closed or unrequired for this local work.
6. Leave production identifiers, accounts, keys, signing, store upload, and
   deployment for their actual release slice. Their absence does not block local
   implementation.
7. Leave staging, commit, and push to the user unless explicitly requested.

The former strict-JSON allocation optimization remains a safe maintenance
candidate, but it is not the V1 critical path and must not be mixed into the G0
checkpoint.

Recommended next device slice when hardware is attached: physical
expired/rotated QR recovery, camera permission denial/regrant, TalkBack/VoiceOver
verification, and process-kill persistence. These are the closest remaining
gaps to the proven same-Wi-Fi optical pairing path and do not by themselves
expand production network authority.

### Revalidation Triggers

- If `CompanionAppModel`, Pairing/Status callback wiring, Android QR policy, or
  payload parsing changes, rerun the focused tests and both release builds.
- If a physical claim is needed after source changes, reinstall the current
  debug APK and repeat actual camera scan, authentication/health, and relaunch
  reconnect. An earlier device run does not transfer to a later binary.
- If `script/build_and_run.sh` changes, rerun its Python tests and shell syntax,
  then separately verify exact PID, listener, visible QR, and screen decode.
- If any P2P/NAT authority record is superseded, read the newest versioned
  progress, decision, and handoff together before acquisition, compilation, or
  networking work.
- Before commit or push, rerun the relevant full suites and inspect the exact
  staged diff. The earlier 525/525 router result predates the last UI/docs-only
  changes and must not be represented as a final combined-source rerun.

## Handoff Maintenance Rule

At the end of the next substantial session, update this file rather than adding
another stale handoff beside it. Refresh:

- date, branch, HEAD, and live worktree state;
- device attached/disconnected state;
- latest completed evidence versus tests merely started;
- root cause and final design if behavior changed;
- proof and authority boundaries;
- exact next action and conditional commands;
- closed subagent state and model preference.

Keep `docs/progress.md`, `docs/qa-evidence.md`, and `docs/roadmap.md` aligned with
the same facts.
