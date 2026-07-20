# AetherLink Session Handoff

Last updated: 2026-07-20 KST.

This is the canonical first document for the next Codex session. Read it before
editing, staging, rebuilding, or making claims from older QA logs. It describes
the current V1 G0 worktree, the still-valid macOS QR recovery and physical
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
- [Dirty worktree map](#dirty-worktree-map)
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
- The top 2026-07-20 sections in those three documents are synchronized current
  summaries. Sections explicitly labeled historical or superseded record what
  was true at that checkpoint; they do not override this handoff.
- `docs/evidence/physical-qr-pairing-20260719.json` is a sanitized observation
  manifest. It preserves safe test metadata and claim boundaries, but it is not
  a substitute for the discarded raw logcat stream, full QR payload, or a fresh
  run from the current checkout.
- Runtime process, listener, IP address, attached-device, and worktree state are
  inherently live facts. Refresh them before use even when this document names
  the last observed value.

## Current Handoff Snapshot

- Repository: `/Users/hanchangha/Desktop/project`
- Branch at handoff: `main`
- Published implementation baseline at this handoff refresh:
  `d32c1846eead13ab1462619145fc4da1194cce7e`, with `main` and `origin/main`
  aligned when checked. The former `41e932e9` plus 12-file dirty snapshot was
  subsequently published and is historical.
- Worktree: intentionally dirty with the canonical V1 roadmap, versioned G0
  decision, versioned assurance packet, content-addressed local assurance
  readback candidate, machine validators, no-device gate integration, and
  synchronized current documentation. The candidate is neither published nor
  owner-accepted. There is no V1 transport implementation in this scope. Run
  `git status --short` again; live output is authoritative.
- Android device state at handoff: disconnected by the user after physical QR
  pairing and reconnect verification. Do not assume ADB is available.
- macOS state at handoff: the ad-hoc `dist/AetherLink.app` process was running
  as PID 59809 and listening on TCP port 43170 when refreshed. QR visibility and
  payload decode were not rerun in G0. Process and port state are ephemeral;
  verify them again before making a live claim.
- Git publication state: the implementation baseline is published through
  `d32c1846`; the roadmap/G0 packet is not committed or pushed. Do not reset,
  clean, stage, commit, or push it without an explicit user request and reviewed
  file scope.
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
staging. The worktree contains one bounded, unpublished V1 G0 packet.

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

The assurance record now has one machine-enforced G0 closure contract that
crosswalks all ten blockers, nine checklist items, fourteen accountable roles,
and exact gate-scoped evidence kinds. Owner receipts must bind the exact
published checkpoint digest, containing commit, scoped blocker IDs, timestamp,
and non-empty verified catalog evidence. Gate and publication receipts also
require exact source commit/path/hash bindings, successful result domains, and
ordered timestamps. The current checker accepts no receipt at all; a successor
must first implement the independently anchored, factory-only validation context
pinned by the activation policy. No receipt exists yet; the crosswalk does not
close G0.

`docs/v1/g0/assurance-checkpoint-readback-v1.json` is the separate local
candidate for assurance hash and source readback. Its validator pins the
candidate bytes, recomputes assurance raw/canonical hashes, and reads all 29
declared inputs as exact repository-relative regular non-symlink files with a
4 MiB per-file ceiling, same-descriptor hashing, and final path-identity
readback. Its eleven mutation tests reject stale or reordered records, path/
hash/symlink/identity drift, oversized sources or integers, non-finite numbers,
fabricated owner acceptance or publication, blocker removal, and authority
promotion. Status remains `candidate_observed_not_immutable`; this is not a
reviewed commit, immutable publication root, owner acceptance, or G0 exit.

G0 is `blocked_before_g1a`, not complete. Ten evidence-bearing blockers remain:

1. assurance packet immutable checkpoint/readback and owner acceptance plus
   separately authorized full no-device and release-compile passes;
2. intentional publication of the roadmap/G0 checkpoint;
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
store-upload, and deployment authorities false. Its combined decision and
assurance mutation suite contains 62 tests. Release metrics fail closed without
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
- `docs/evidence/physical-qr-pairing-20260719.json`
- `docs/progress.md`
- `docs/qa-evidence.md`
- `docs/roadmap.md`
- `script/check_v1_g0_checkpoint.py`
- `script/test_v1_g0_checkpoint.py`
- `script/check_v1_g0_decision.py`
- `script/test_v1_g0_decision.py`
- `script/check_docs_hygiene.py`

## Dirty Worktree Map

The earlier QR, persistence, and security-governance work is part of the
published `d32c1846` baseline. The optimization work is published there as well.
The intended current unpublished scope is:

- `README.md`;
- `docs/handoff.md`, `docs/progress.md`, `docs/qa-evidence.md`, and
  `docs/roadmap.md`;
- `docs/v1/g0/decision-v1.md` and `decision-v1.json`;
- `docs/v1/g0/assurance-v1.md` and `assurance-v1.json`;
- `docs/v1/g0/assurance-checkpoint-readback-v1.json`;
- `script/check_v1_g0_checkpoint.py` and `script/test_v1_g0_checkpoint.py`;
- `script/check_v1_g0_decision.py` and `script/test_v1_g0_decision.py`;
- `script/check_no_device_quality.sh` integration.

There are no Android, macOS, protocol, schema, transport, or relay
implementation edits in this scope. The documentation records the G0 decision,
its blockers, and current evidence; the scripts validate that record and keep
every later authority closed.

This publication review assumes an incremental commit to the already existing
remote repository. The current added lines and new G0 files contain no actual
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

### Current 2026-07-20 V1 G0 evidence

- The integrated G0 checker passes against nine decision source hashes, 29
  assurance source hashes, the live Android/macOS configuration and locale
  baseline, and protocol-schema message/error parity.
- Its 62 mutation tests pass and reject premature G1a/network/deployment
  authority, nested unknown fields, security downgrades, missing hard stops,
  fallback or platform drift, network-cell/variant/measurement-contract/blocker
  removal, missing protocol/threat/user-loop inventory, forbidden observability
  fields, invented approvals, evidence-free checklist passes, and weakened
  human wording.
- The non-socket static batch passes: copy hygiene across 92 user-facing files,
  docs hygiene across 12 current documents, Android and macOS five-locale parity,
  protocol schemas, the closed P2P/NAT and production-relay design validators,
  21 documentation/launcher/Phase-A unit tests, shell syntax, and diff hygiene.
- Shell syntax for the integrated no-device gate passes. The complete aggregate
  has not yet been rerun on this G0 documentation/script scope, so no fresh full
  Swift, Android, QR, or relay result is claimed here.
- No Android device is attached; no production credential, signing identity,
  store action, network service, or deployment was used.

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
./gradlew --no-daemon :app:assembleRelease -Pkotlin.incremental=false
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
2. Run the G0 validator and its mutation tests before trusting the decision
   packet, including the separate local assurance readback candidate. Do not
   confuse that candidate with publication or owner acceptance, and do not
   start G1a because the machine authority remains false.
3. If the user explicitly requests commit/push after reviewing scope, publish
   the bounded roadmap/G0 packet without unrelated implementation. Blanket
   staging is not the default.
4. Read back the exact remote repository, commit object, checkpoint path, and
   checkpoint digest. Only that verified identity may receive owner or
   authorized-gate receipts.
5. Obtain the actual account/owner/budget evidence and separately authorized
   gate results, then record non-secret receipts in a successor versioned
   checkpoint and derive all ten blocker states. Never put private keys,
   credentials, account tokens, QR material, or personal owner contact data in
   repository documents.
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
