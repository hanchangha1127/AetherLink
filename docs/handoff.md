# AetherLink Session Handoff

Last updated: 2026-07-21 KST.

This is the canonical first document for the next Codex session. Read it before
editing, staging, rebuilding, or making claims from older QA logs. It describes
the current V1 G0 publication/worktree state, the still-valid macOS QR recovery and physical
Android proof, the remaining proof boundaries, and the shortest safe path to
resume work.

## Contents

- [Current truth versus historical evidence](#current-truth-versus-historical-evidence)
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

## Current Truth Versus Historical Evidence

- This file is the current continuation contract. Its snapshot, behavior,
  evidence matrix, proof boundaries, and next-session flow take precedence over
  older chronological entries in `docs/progress.md`, `docs/qa-evidence.md`, and
  `docs/roadmap.md`.
- The top 2026-07-21 sections in those three documents are synchronized current
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
- Worktree: `main` and `origin/main` were clean and aligned at `b24c5ecb` after
  that readback. The current worktree is intentionally dirty only for the eight-
  path unpublished scope: four canonical truth-sync documents plus the owner-trust-
  bootstrap profile, checker, tests, and no-device aggregate registration. None
  is staged, committed, or pushed. Run `git status --short` again because live
  output is authoritative.
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
  Neither the proposal nor any publication changed owner identity, evidence,
  acceptance, activation, G0-exit, or G1a state. Owner authentication and
  acceptance remain absent. The current unpublished scope is eight paths: the
  four canonical truth-sync documents plus the owner-trust-bootstrap profile,
  checker, tests, and no-device aggregate registration. Do not reset or clean
  them. The assistant performs edits and verification only; the sole project
  owner retains staging, commit, and push control after review.
- Subagent preference for this workstream: use GPT-5.6 Sol. Do not use
  GPT-5.3-Codex-Spark.

## First Five Minutes

Run these before deciding what is current:

```bash
cd /Users/hanchangha/Desktop/project
git branch --show-current
git rev-parse --short HEAD
git status --short
sed -n '1,650p' docs/handoff.md
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
python3 -m unittest script.test_build_and_run
python3 -m unittest script.test_documentation_handoff_guards
python3 script/check_p2p_nat_security_design.py
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
The current working copy contains only the eight-path local scope described
above: four canonical truth-sync documents plus the owner-trust-bootstrap
profile, checker, tests, and no-device aggregate registration. The assistant
must leave it unstaged and uncommitted; the sole owner may commit and push it
after review.

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

G0 is `blocked_before_g1a`, not complete. Ten evidence-bearing blockers remain:

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

`script/check_v1_g0_decision.py` hash-pins the inherited security decisions,
checks the current application/platform/locale baseline, and keeps G1a plus all
source-acquisition, library, compiler, socket, network, production-key, signing,
store-upload, and deployment authorities false. Its combined decision,
assurance, and closure-amendment mutation suite contains 63 tests; the separate
V1 checkpoint suite contains 11, the dormant publication suite contains 8, and
the V3 lineage/bundle, sparse-intake, and evidence-profile suite contains 17,
forming the earlier 99-test subtotal. The baseline-evidence readiness suite adds
22 tests to form the previous 121-test subtotal; the independent-context suite
adds 9 to form 130, the repository/remote-source suite adds 8 to form 138, and
the owner-trust-bootstrap suite adds 11, so the current eight focused G0 suites
contain 149 tests total. Release
metrics fail closed without
an approved evidence signer and verifier, and percentile/scalar values are
recomputed from bounded, canonical signed samples. Required network variants
also bind one raw observation per attempt: affected plane/region, outage result
and route, ordered restore/authenticated-recovery phases, and zero downgrade
counts. Aggregate outcome fields are derived from those observations, so attempt
counts or a result string alone cannot satisfy an outage gate. No P2P candidate was selected and
no production key or credential was created.

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
above are the canonical commit-scope records. All four remote readbacks remain
bounded session observations. The only current unpublished scope is the eight-
path local scope named in the snapshot: four canonical truth-sync documents plus
the owner-trust-bootstrap profile, checker, tests, and aggregate registration.

There are no Android, macOS, runtime-protocol, transport, or relay implementation
edits in this scope. The sidecar, one-response dormant intake envelope, profile,
and scripts structurally validate the exact recorded candidate values without
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
  130, the 8-test repository/remote-source suite forms 138, and the 11-test
  owner-trust-bootstrap suite brings the current eight-suite total to 149, with
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
- The 13-artifact P2P/NAT source-evidence collection was integrity-refreshed
  after the QR changes to `CompanionAppModel.swift`; its current collection
  SHA-256 is
  `6e6dfbfc0cdb70370c30f54222584b69042a6e22b6df04c7f3e65043c38522bd`.
  `check_p2p_nat_security_design.py` and all seven Phase A progress tests pass.
  This is source-freshness synchronization only and grants no authority.
- `implementationAuthorized=false`, `compilerInvocationAuthorized=false`,
  `socketCreationAllowed=false`, and `runtimeNetworkIOAllowed=false` remain the
  operative boundary. A new candidate requires a new versioned review and an
  explicit user decision; rejected authority cannot be reused implicitly.
- AetherLink remains local-first. The client never calls Ollama or LM Studio
  directly; AetherLink Runtime mediates provider access.
- Network reachability is not authorization. Pairing, trusted-device records,
  challenge-response, and encrypted runtime sessions remain required.
- Never commit QR payloads, pairing codes, nonces, relay secrets, allocation
  tokens, runtime identity private material, provider URLs, or device-specific
  credentials.

## Recommended Next Session Flow

Unless the user redirects the task, use this decision order:

1. Re-read this handoff and refresh Git/device/process state.
2. Revalidate the published six-blob lineage, tracked dormant receipt sidecar,
   and current one-response sparse owner/catalog intake candidate. Do not
   confuse the explicit reference-only proposal or structural candidate validity
   with independent trust, owner authentication, acceptance, activation, or G1a
   authority.
3. Preserve the published seven-file `025a4ef5` truth-sync/compiler successor
   and its completed 7/7 partial-clone readback, plus the published sixteen-file
   `b24c5ecb` successor and its completed 16/16 strict readback. Keep only the
   current eight-path local scope—four canonical truth-sync documents plus the
   owner-trust-bootstrap profile, checker, tests, and aggregate registration—
   until separately reviewed and authorized; blanket staging is not the default.
4. Do not repeat publication as a prerequisite: exact remote bytes for
   `12c38154`, the nine-file `70350f5e` successor, and the seven-file
   `025a4ef5` successor plus the sixteen-file `b24c5ecb` successor were freshly
   observed. Repeat readback only for drift or a new target.
5. Preserve the exact publication proposal compiled from
   `user-input:session-20260721:item-2` and its two null artifact references.
   Preserve the immutable v1 profile and keep both selectors false. First
   independently authenticate the proposed repository owner. Only after an
   authenticated selector decision may a new versioned profile set a selector
   true; then separately create or acquire, independently anchor, and verify
   `reviewed_commit_scope` and `published_checkpoint` evidence before any
   acceptance is considered. V3 already pins the exact ten-field owner binding
   and eight-field approval receipt, so do not create duplicate owner or
   approval schemas. The local
   `docs/v1/g0/owner-trust-bootstrap-profile-v1.json` now freezes every provider,
   registry, trust-anchor, credential, snapshot, trusted-time, and detached-
   envelope selection reference at null and every authority state at false. Its
   ownership model records the user's unverified sole-human-owner declaration,
   hash-binds the canonical fourteen-role order, retains the V3 requirements for
   fourteen future unique role-scoped identity references and fourteen separate
   receipts, and requires the selected registry revision to authenticate every
   alias as a role of the same principal. Raw-ref uniqueness therefore remains
   V3-compatible and no V4
   closure amendment is needed. Its supplied-byte-only checker re-derives those
   V3 projections and cannot construct an adapter result; this is a planning/
   validation boundary, not owner authentication or provider selection. Before
   implementing the missing trust adapter, obtain an
   explicit external selection for the owner identity registry and independent
   trust anchor; the credential mechanism and proof-of-control binding among
   `ownerIdentityRef`, `credentialRef`, and the registry revision; authentication
   of the exact canonical eight-field approval receipt; authenticated registry/
   revocation snapshot acquisition, provenance, freshness, rollback, and
   `acceptedAt` validity rules; trusted time and clock-skew policy; and the exact
   bounded adapter-result/context handoff. If a signature-based credential is
   selected, separately pin its algorithm, encoding, key usage, key or
   certificate digest reference, and fail-closed validation. Any challenge or
   nonce belongs in a separately versioned detached envelope, not the exact
   eight-field receipt, and its replay relationship to the future consumed-
   bundle ledger must be decided explicitly. The release-evidence Ed25519
   envelope is a different contract and must not be reused implicitly. Never
   place a private key, raw credential, or secret in the repository. For
   other blockers, ask the user or authenticated external owner only for
   candidate versions, requirement dispositions, session-item references, and
   optional evidence artifact presence. Derive owner, evidence-input,
   change-request, and safe-path artifact references mechanically from the
   canonical role, evidence kind, or blocker; do not accept arbitrary reference
   payloads. Put actual public catalog values only in separately typed and
   reviewed evidence candidates; never put private keys, credentials, account
   tokens, QR material, personal owner contact data, or acceptance claims in the
   intake packet. After independent authentication and evidence verification
   exist, record separate receipts in a successor versioned checkpoint and derive
   all ten blocker states.
6. Only after every blocker is closed, create and validate a separate G1a
   no-network authority record. G1a may then cover dormant schema, canonical
   vectors, pure state transitions, temporary-store crash tests, and first-party
   compilation, while sockets and live services remain forbidden.
7. If the task is different-network pairing or a new P2P candidate, stop before
   execution unless its fresh versioned authority is explicit. Same-Wi-Fi local
   QR proof and this G0 packet authorize neither workstream.

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
