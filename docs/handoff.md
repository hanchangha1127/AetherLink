# AetherLink Session Handoff

Last updated: 2026-07-31 KST.

This is the canonical first document for the next Codex session. Read it before
editing, staging, rebuilding, or making claims from older QA logs. It describes
the active personal-project governance, current V1 worktree state, the still-
valid macOS QR recovery and physical Android proof, the remaining proof
boundaries, and the shortest path to resume work.

## Contents

- [Current non-security quality lane](#current-non-security-quality-lane)
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
work prerequisite. Product security, authentication, and authorization
analysis or implementation is paused at the user's direction. Existing
material remains historical context and must not block the active non-security
product-quality lane. Sockets, external-network execution, production signing,
store upload, and deployment remain distinct technical scopes governed by
current user direction, not repository-owner identity proof.

## Current Non-Security Quality Lane

- Continue only feature, UX, accessibility, performance, build, documentation,
  and release-quality work. Do not resume security findings, threat analysis,
  owner authentication, or authority-evidence work.
- Android 13+ app-language startup is now platform-to-ViewModel only.
  A nonempty `LocaleManager.applicationLocales` snapshot becomes the fixed
  language; an empty snapshot means Follow system. API 26 through 32 retain a
  stored fixed language. OS writes happen only from user language actions, so
  an external app-language selection is no longer cleared by stale state and
  explicit English is distinct from empty/system English. The first localized
  frame uses the platform snapshot while storage converges. The storage,
  duplicate-save ViewModel, writer, and API 32/33/36 production-lifecycle
  regressions pass 6/6. A disposable API 36.1
  emulator preserved external Korean/Japanese, in-app French, explicit English,
  Follow system, and repeated cold launches. The same current Debug APK passed
  the real permission-dialog denial/recovery/settings flow and 200% font-scale
  reachability without a FATAL or ANR. Physical QR, TalkBack, OEM, signing, and
  production claims remain open.
- The current macOS Runtime lifecycle publishes
  `starting(port) -> listening(port) | failed(message)` only after listener and
  Bonjour readiness. Network.framework `.ready` starts Bonjour; `NetService`
  `didPublish` is now the only transition to advertising. Publication failure,
  a five-second timeout, or a late stop releases local ownership and permits
  same-port Retry. Listener and advertisement generations reject stale
  callbacks, and refresh while publishing uses only the latest TXT metadata.
  Reentrant or concurrent advertiser replacement is serialized, a racing
  timeout cannot overwrite confirmed publication, and an immediate
  advertisement failure after asynchronous listener readiness is still
  forwarded before cleanup. Status handlers run after lifecycle-lock release,
  allowing cross-queue stop coordination without lock inversion.
  Pairing, route allocation, relay startup, and restored-pair work stay pending
  until publication. `RuntimeDevServer` also waits to print advertising or emit
  optional development pairing and exits on publication failure. Late listener
  loss terminalizes the shared advertisement gate before stop, rejecting a
  previously captured publish callback. Seven
  advertiser tests, all 39 manager tests, two focused AppModel regressions, and
  the exact 217-test product selector pass. This is no-device local lifecycle
  evidence; no external network discovery, device, performance, security,
  signing, deployment, or release is claimed.
- Normal negotiated AppKit termination uses the first weakly recorded
  `@StateObject` Runtime lifecycle. `applicationShouldTerminate` synchronously
  closes request admission, begins model stop, and returns `.terminateLater`.
  Its bounded drain retires active and registration-racing requests, waits for
  already submitted title/summary cancellation jobs, resolves deferred
  memory-summary delivery acknowledgements before the persistence barrier, and
  cancels and joins Runtime chat-retention maintenance. It replies once after
  drain or after the five-second deadline; timeout permits exit but is not
  completion evidence. The direct `applicationWillTerminate` fallback performs
  synchronous `stop()` only. Thirteen AppDelegate tests and eight exact
  Router/model termination regressions are included in the current 217/217
  product selector. This is current-source behavior after immutable Build 24,
  not new Build 24 evidence. SIGKILL, power loss, arbitrary async work, device,
  network, signing, security, and G7 completion remain outside the claim.
- System sleep/wake is now one reversible, state-bound Runtime transition.
  AppDelegate registers one pair of `NSWorkspace` observers. A starting or
  advertising Runtime stops through the existing cleanup path and retains only
  its port as a one-use wake intent; failed and stopped states do not acquire
  that intent. Wake restarts once through the normal listener/Bonjour gate.
  Duplicate, reversed, stale pre-sleep, deferred-initial-start, and
  terminate-while-suspended cases are inert. Eight AppDelegate tests, three
  direct model regressions, and the existing model-stop/manager-stop checks
  pass 13/13; the exact product selector passes 217/217. This is injected
  current-source behavior after immutable Build 24. That sleep/wake slice does
  not itself prove physical sleep/wake, network readiness, provider restart,
  async persistence flush, device, signing, security, or release behavior.
- Active Runtime provider status now self-recovers after a provider starts
  late. Start/wake perform concurrent immediate checks, then only a
  retryable-unavailable provider is checked again after
  1/2/4/8/16/30-second capped delays. Provider-scoped single-flight joins
  manual refresh, publishes independent rows without head-of-line blocking,
  and never triggers model loading, catalog/chat work, or repeated calls to a
  healthy provider. Stop/sleep/failure/deinit cancellation plus generation and
  reservation checks reject late results. Health requests use a separate
  five-second bound, and LM Studio's native/fallback sequence shares that one
  total deadline; normal provider operations keep their previous timeout.
  Eight recovery tests, one scoped aggregate test, and two endpoint/timeout
  tests pass 11/11; the exact product selector passes 217/217. This is
  deterministic post-Build 24 current-source evidence only—no live provider,
  external network, physical device, signing, security, deployment, or release
  claim.
- Android QR camera permission is now one app-root lifecycle state instead of
  scanner-local booleans. `NeverAsked` may auto-request once;
  `RequestInFlight` disables duplicate input; `RetryRequired` keeps storage,
  launcher, and interrupted-completion failures manually recoverable; a first
  denial with rationale remains user-requestable; and a repeated or fixed
  denial uses the existing Settings recovery surface. A checked app-private
  `LaunchPending -> Recorded` transaction brackets launcher acceptance.
  Production wiring rechecks the OS grant and stale in-flight state on
  `ON_RESUME`. The scanner class passes 13/13. A dedicated controller-host
  matrix passes 4/4 on API 26, 30, 33, and 36 while driving denial, rationale,
  explicit retry, grant, later revocation, and resume reconciliation through
  the production Compose controller wiring. A separate Robolectric lifecycle
  matrix launches the manifest production `MainActivity` on the same four
  APIs. Its three paths per API pass 12/12: it retains the
  `ActivityScenario.recreate()` regression and adds saved-state-free same-JVM
  cold Activity launches that reconstruct durable `Recorded` and interrupted
  `LaunchPending` without an automatic second request. The G5 font-scale
  qualification class adds three independently reported 100%, 150%, and 200%
  results across scanner, drawer, Chat, Settings pairing, Memory, and chat
  history. All five app locales receive representative smoke coverage, while
  English and Korean receive the full state set; QR-scanner close, flashlight,
  cancel, and permission actions are held to 48 dp. The exact Android product
  selector passes 45/45 across twelve result classes. Focused result contracts
  resolve by class name, and accepted JUnit XML must strictly postdate the
  workflow, checker, Android build inputs, production source, and complete app
  test-source graph. This is current-source
  resolver/transaction/controller-host/JVM/Compose evidence after immutable
  Build 24. The complete app JVM suite also passes 1,226/1,226 through the
  exact 19-class `--rerun-tasks` runner. Its pre-run marker binds every declared
  Android input path, byte stream, and mode; the post-run gate requires the
  exact 19-report set, 1,226 unique nonempty test cases, testcase-manifest
  SHA-256
  `cc3ea9e2d72ca96e7f937b22a893d8cdaf38c409564ac8baecc5b947b8aa1b78`,
  and a canonical marker/report-byte binding with independent readback. The
  drawer test resets each locale to the app title and traverses
  `top -> header -> detail -> header` inside the actual history viewport above
  the fixed Settings footer, refreshing bounds and checking the exact merged
  accessibility summary.
  Its controlled platform seam does not prove SDK-specific OS
  permission or rationale policy, Android OS process death, a physical
  permission dialog, physical camera, optical scan, physical/OEM typography,
  TalkBack, or production release.
- The same exact current source passes clean offline strict-lock Android
  Release APK/AAB/lint generation. The unsigned APK is 9,575,138 bytes at
  `cad01315710cf2ed63962f0165b410dd16c09dc27cc44c42036318b1e1739a1f`;
  the AAB is 10,684,471 bytes at
  `736f4debe24ada3bdbfd51055a56dcd4d5ccae103568d92183d9e74c696bb62f`.
  A current-source local ad-hoc macOS Release package also builds, the source
  snapshot stays
  `d5aee95b0a7b86c73ac111653f7bbf2e2d96b4e718b4d0b8db9571bcfe7d4dce`
  across 253 files, and an isolated temporary 167,578,488-byte archive at
  SHA-256
  `c329ed6a44f1e8a459345993f5e645cefa5b8bdc730cd78efe771fc0c8500f88`
  passes independent 29-member readback. Its 15,200-byte manifest has SHA-256
  `f99521fce2f3e420265902323260a6a5b771805ddd71f3d4d1391617796efb72`,
  and its 99-byte checksum sidecar has SHA-256
  `24b860585953d9eaaf46b7b9e883d46c9b729e1e5beaba99f5bf0d8bc66dcebe`.
  This is a dirty-content,
  comparison-only candidate with `1.0.0+24` metadata; it is not stored under
  `dist/releases`, does not alter immutable Build 24 or append Build 25, and
  does not prove distribution signing, installation, device behavior,
  publication, or production release.
<!-- aetherlink-current-source-g6-lane-a-dmg-v1:start -->
**Latest current-source G6 exact Lane-A DMG handoff.** The comparison-only
run bound 254 release inputs at source SHA-256
`e2db0c96a079cceed3c6b8913d633783c8d4bf2062038694be493fac88f56923`
and execution overlay SHA-256
`0eeaa1ffcc08cbf2e7bb2e2854d8892f360f989e438aa4f25818eeff15cc680e`.
Its unequal 101- and 109-byte source roots produced the exact same
167,061,116-byte archive at SHA-256
`3300f967ba14e4703640f7b00c600f16e9a101911db60200857887f1a8db7ada`,
with a 15,200-byte manifest at
`ea3250caf41c4cd649482264ca42a2ea91380fe0bc4fe4f17db6b73d09f1c1e6`
and a 99-byte checksum sidecar at
`03070799c23b4ba16fddb43b56579c3a7ba695e9530bd5750c06e0c479fcd461`.
All archive/member equality flags are true and both difference lists are
empty. The exact 19,645-byte primary result is
`dist/reproducibility/aetherlink-1.0.0+24-local-v1-two-root-v4-prepublication-current-source-g6-lane-a-dmg.json`,
SHA-256
`427824807c66ae2e121af43f155dc0172e307ea9704823d6e556400a2eb02c3a`.

Only after exact A/B equality, the runner handed the materialized Lane-A
archive to the v2 local-DMG exercise. The exact 3,038-byte lifecycle result is
`dist/lifecycle/macos-aetherlink-1.0.0+24-local-v1-two-root-lane-a-local-dmg-install-v2-current-source-g6.json`,
SHA-256
`d5250ccd5b84de4517e6ce79234343cca6670b604cae23503ef8de61cb347fe7`.
It records one ephemeral HFS+ UDZO image, a read-only mount detached before
launch, two distinct LaunchServices processes, three SQLite integrity checks,
stable empty Runtime chat and state, and the exact ten-file installed app tree
of 21,356,326 bytes at SHA-256
`0dd6363420e79b90ffac38fdf9410cc109122800f071ca9e1e66bf579ea21145`.

The lifecycle field `archiveReadback.currentSourceCompared=false` means that
the lifecycle runner performed archive-only validation; the documentation
guard dynamically cross-binds its ZIP, manifest, and checksum identities to
the parent current-source Lane-A result. No lane archive was retained or
published, comparison-only publication stayed disabled, and the protected
Build 23 archive stayed unchanged. This proves only one same-host, per-user,
local ad-hoc exact handoff. It does not prove arbitrary cross-host or
clean-machine reproducibility, Finder/quarantine/Gatekeeper behavior,
signed/notarized distribution, N/N-1 upgrade or rollback, physical-device,
provider, network, UI/accessibility, security, deployment, or production
qualification.
<!-- aetherlink-current-source-g6-lane-a-dmg-v1:end -->

- The current Android release-quality slice adds Build 23-forward compiled
  entry-point topology and application-shell contracts. Independent builder
  and readback parsers
  require the APK and AAB to agree on exactly one exported
  `singleTask`/`never` MainActivity and exactly four launcher, pairing deep-link,
  `SEND`, and `SEND_MULTIPLE` filters with the same canonical 44 MIME types.
  They also resolve the exact label/icon/round-icon/theme/locale-config
  resources, the ordered five-locale config, and the default plus five localized
  `status_title` payloads. Direct AAB readback confirms the five references,
  localized payload, and disabled language splitting. A universal APK derived
  from that same AAB confirms the locale-config body/order and completes the
  composite AAB claim compared with the standalone APK.
  Unrelated merged dependency activities are accepted and explicitly outside
  the MainActivity claim. The archive claims are closed and exact-typed; 59
  release-archive tests pass.
  Locally present Build 21 compiled outputs exercise both real formats but are
  not current release evidence. The gate remained inactive for immutable Builds
  1 through 22, which retain their historical contracts.
  A separate source-only `/private/tmp` copy with only its copied ledger
  advanced to `1.0.0+23` now passes offline strict-lock Release APK, AAB, and
  lint generation. Builder and independent checker readback agree on the exact
  Build 23 compiled claims. The candidate APK is
  `ecbd83e71889d43134c121f057df7cf38e2e04a08a95fc7588f10e3ee6521ea9`
  (9,575,138 bytes), and the AAB is
  `af9b77eb7d13563a45cab5b7fe10bc71ba47caa633f4eaedbf719278f80e06fa`
  (10,677,911 bytes). This preflight candidate was not a canonical ledger entry
  or retained archive.
  A later ordinary-wrapper run retained
  `dist/releases/aetherlink-1.0.0+23-local-v1/`; its 166,859,521-byte ZIP has
  SHA-256
  `b9a9c3c2ebeb01fc735fed3356f1f244178fb4521c1a806dc7a93d776f83ea2e`.
  A subsequent Build 23 comparison-only candidate was not published. Its
  19,645-byte result at
  `dist/reproducibility/aetherlink-1.0.0+23-local-v1-two-root-v4-prepublication.json`
  has SHA-256
  `e82cfc2b2cf005ace6f5405065b997f7fb66a1338d1bf3d3fe082d1b9863b297`.
  Its
  166,345,274-byte ZIP SHA-256
  `f9bee58ed228e31103bfd3929d2b2ba9c4fd30cb3fbc907b6f39f2d287239ffb`
  differed from the retained ordinary-wrapper archive in exactly the macOS
  executable, dSYM DWARF member, and relocation member. Build 23 therefore
  remains a historical retained archive, while Build 24 is the canonical
  qualified lineage.
  The bounded Android product CI lane runs the complete contract suite. This
  slice includes no device run, launcher/theme visual observation,
  distribution signing, publication, permission analysis, or network claim.
- The current G6 macOS packaging lane no longer targets the running
  `dist/AetherLink.app` during package-only or release assembly.
  `build_and_run.sh --package-only` cleans and writes
  `dist/package-only/AetherLink.app`; `build_release_artifacts.sh` selects
  `dist/release-package/AetherLink.app`. Eleven fake-toolchain regressions pass
  and PID 59809 remains alive at the original development path.
  The Build 22 post-archive uninstall/reinstall harness also passed twice with
  the same 2,474-byte result and SHA-256
  `eae0cc7e6060fa8418f01c059556d2b73059234ecc0eab7c6ec0f2bf2d041a5e`.
  It removed only the exact temporary-HOME app, retained identical Application
  Support state, reinstalled and relaunched the same artifact under a distinct
  PID, then removed it again. This is not N/N-1, rollback, automatic data
  cleanup, clean-machine/Finder, provider/network, UI, or physical evidence.
- The current unreleased macOS accessibility slice adds an Increase
  Contrast-aware status palette and stronger custom borders, keeps warning text
  primary, and makes Runtime History selection non-color-only with a checkmark.
  Runtime History is now one native arrow-key selection list instead of one Tab
  stop per session. Status recovery moves keyboard and VoiceOver focus to the
  first expanded recovery field; Pairing action/menu-bar transitions use a
  consumable intent that survives asynchronous QR preparation, targets the
  keyboard action and accessibility summary, and is canceled when Pairing is
  left. The menu bar delegates generation to one main `Window`, and pending
  focus state survives locale-driven `ContentView` recreation. QR expiry
  announces once per QR lifecycle, and decorative Model Download icons are
  hidden. Eight new focused regressions, the current exact 217-test product CI Swift
  selector, and the complete 186-test accessibility run pass; Debug and Release
  AetherLink builds pass.
  The Mac was locked during attempted UI observation, so physical
  keyboard/VoiceOver traversal remains unclaimed.
- The current unreleased macOS UI routes both explicit custom animations
  through one Reduce Motion policy. Status recovery scrolls immediately and
  pairing QR expiry changes without the app animation when the OS preference is
  enabled. The test-only environment override can force reduction on but cannot
  disable a true system preference. The complete 147-test localization suite
  and 25-test render suite pass.
- The current unreleased macOS Runtime no longer latches a failed listener as
  started. Only an advertising listener enables route allocation, relay
  startup, or restored pair transports; a failed attempt leaves a localized
  Status Retry action available. If an accepted listener later fails, the
  manager releases local advertisement ownership, the app model clears its
  started state, and the same port can be retried. Exact listener generations
  keep a superseded listener callback from stopping its replacement. Peer
  admission validates and inserts under the same generation lock, so a
  connection cannot cross a concurrent stop/failure cleanup boundary. The
  focused lifecycle/action/render checks and current exact 217-test CI Swift selector
  pass with zero skips or failures.
- The repository includes `.github/workflows/product-quality.yml` as a
  bounded G7 non-security CI subset. Pull requests run two read-only hosted
  jobs with exact Swift and Android product allowlists; pushes to `main` add a
  macOS Release product build and strict-lock Android Release APK assembly plus
  lint. `script/check_product_ci.py` pins that shape and rejects broad,
  device/network, bundle/signing, publication, deployment, offline, or
  `main-full` scope expansion.
  The macOS lane uses supported `macos-26` and pins the exact Xcode 26.6
  toolchain used locally; the deprecated `macos-14` draft was removed. The
  self-test validates controlled mutations semantically with the byte pin
  disabled only for that mutation, so a generic hash mismatch cannot mask a
  missing rule. Safe YAML parsing plus a canonical parsed-semantic fingerprint
  closes the exact top-level/job mappings and complete step arrays, while raw
  checks close both job preambles and every named step body, including the
  changed-byte and platform compile commands. Its static lane also runs the
  product-only copy check before the release-ledger, icon, and license checks,
  without entering the paused mixed security checker path. A Psych AST pre-pass
  requires one YAML document and rejects duplicate or explicitly tagged
  mapping keys before safe loading. The reviewed workflow byte SHA-256 is
  `56c2417d0294e7da5ff27a904036cae94668699ed83447b2214a72b2858714ef`;
  its parsed-semantic SHA-256 is
  `563cf577cc6bea780633a99bb73416cfbdafa416cde9d0125056baeef5307305`.
  Current local parity passes 217 selected Swift tests and 45 selected Android
  tests across twelve result classes with zero skips or failures, both platform
  compile lanes, Release builds, lint, four static checks, YAML parsing, and
  the guard's mutation suite. The Android allowlist directly executes both the
  changed-session scroll-boundary regression and the three-result exact
  font-scale qualification rather than only compiling their test source.
  Hosted run
  `30525374687` completed successfully for both jobs at baseline commit
  `0f59c757d745d0b95c37c9b93aec8d354bcfef9f`. That historical 159-test
  baseline also predates commit
  `53f45d4e9909dd77520a450170eb87c7d260ea89`, which contains the first
  listener-readiness and accessibility/product-copy expansion. The current
  listener and Bonjour publication lifecycle, publication timeout/retry,
  development-server publication handling, fourteen added tests, checker, and
  documentation remain unstaged and uncommitted and are not covered by a hosted
  run.
  Canonical G7 completion remains unclaimed. The
  selectors constrain test execution, not compilation of the complete Swift
  package and Android app test-source graphs, and the Android hosted lane still
  depends on its image's preinstalled SDK 36 plus ordinary dependency
  downloads.
- The current unreleased macOS Runtime isolates provider-qualified catalog
  work. Qualified chat resolution, aggregate chat/embedding dispatch, and
  semantic embedding descriptor lookup query only the selected Ollama or LM
  Studio backend; unqualified chat still searches the complete aggregate
  catalog. Exact provider-model validation and cancellation meaning are
  preserved. All 49 aggregate/residency tests, three focused Router regressions,
  the complete 2,093-test Swift suite, and the Release `AetherLink` build pass;
  11 opt-in/live tests are skipped. The refreshed provider catalog copy-hygiene
  subguard pins the scoped protocol, both Router call/fallback pairs, aggregate
  filtering, exact call counts, and seven named regressions; the subguard and
  all seven tests pass. The full mixed copy-hygiene command then stops only on
  two historical G2 document expectations in the user-excluded security scope,
  which remain untouched. Final GPT-5.6 Sol re-review reports no P0-P3 finding.
  This proves deterministic no-device call isolation, not measured provider
  latency or live-provider behavior.
- The current unreleased Android chat treats `activeChatSessionId` as a
  transcript scroll boundary. Immediate and delayed conversation switches,
  including saved-state restoration while cached messages remain loading,
  return to the selected conversation's latest row exactly once. Same-session
  streaming updates preserve an earlier reading position and the
  jump-to-latest action. Latest assistant/user/overall message IDs are computed
  once per screen composition. The focused checks, all 296 Compose screen
  tests, the complete 1,195-test app JVM suite, Release assembly, and Release
  lint pass; lint has 0 errors and the two existing SDK-version warnings.
  Final GPT-5.6 Sol review reports no P0-P3 finding. This is no-device evidence,
  not physical rendering or measured frame-time proof.
- The previously queued Release-test fixture refactor is inactive because its
  affected accepted-endpoint types are inside the user-excluded authorization
  scope.
- Build 24 is the latest immutable ledger archive. It binds a 249-file source
  snapshot with SHA-256
  `a01d37c3be608db3a8fa588b1ec019b673b5c57bc227ffc105047b3e4548f5f2`
  and overlay SHA-256
  `9d71c5340e1809222542c59d0da96f1ee08f9b619741ae3b0f1cb4fcbc28a3cc`
  to the 166,345,274-byte ZIP with SHA-256
  `104c07b6fc1b421bcc0309657001fdf991e37bb815c282b3e5112ed98821ab1c`.
  The 15,200-byte manifest SHA-256 is
  `eccc81de7eee5d56223e7826d153617a24725344154f7c7c5dd291d25ab6369b`;
  the 99-byte checksum sidecar SHA-256 is
  `827cdc72cbe44c47b75a7abc899b6523361ed9332942a721b624509ffcea5882`.
- The v4 comparison-only prepublication result is
  `dist/reproducibility/aetherlink-1.0.0+24-local-v1-two-root-v4-prepublication.json`,
  19,645 bytes with SHA-256
  `64c21a8c345018e7fca552b1ff706ac5f9c1f19a349afb0090dae22466e9e3db`;
  it records exact two-root equality and no publication. The v4 publish-qualified result is
  `dist/reproducibility/aetherlink-1.0.0+24-local-v1-two-root-v4.json`,
  20,353 bytes with SHA-256
  `08a176bed8abe4f4c62178fa13a939059d127ee3dee4352096bcc593177cea36`;
  it records `alreadyMatched=false`, `outcome=published-verified`,
  `qualifiedArchivePublished=true`, `independentReadback=true`,
  `publishedBytesEqualLaneA=true`, and `sourceSnapshotUnchanged=true`. Exact
  prepublication binding precedes publication, and protected Build 23 identity
  `df16cc1c38a414fa0c8e09eb3954645c34ba42aba21060ca6ad5710e4b47a4f6`
  remains unchanged.
- Current readback is
  `python3 -B script/check_release_artifact_archive.py --archive-dir dist/releases/aetherlink-1.0.0+24-local-v1`.
  Builds 1 through 23 are historical; their readback requires `--historical`.
<!-- aetherlink-current-build23-to-24-isolated-upgrade-v2:start -->
- A post-archive Build 23-to-24 upgrade runner snapshots each archive's exact
  ZIP, manifest, and checksum sidecar, uses those same bytes for readback,
  extraction, and exercise, and rehashes them unchanged afterward. Under a
  temporary HOME it migrates one fixed Runtime-chat canary, replaces the exact
  app path, and performs two idempotent Build 24 SQLite-only readbacks. The
  three launches use distinct processes; all three SQLite files pass integrity;
  Application Support and runtime-identity bytes and modes remain unchanged;
  and the ten-file current tree contains no stale Build 23 file. Two complete
  runs matched the 6,469-byte canonical result
  `dist/lifecycle/macos-packaged-app-build-23-to-24-isolated-upgrade-v2.json`
  at SHA-256
  `ddec23cf048fa77c559ca7ee4f45354feb558f830ca4b01eccffa5b7786ea09c`.
  The 898-byte receipt
  `dist/lifecycle/macos-packaged-app-build-23-to-24-isolated-upgrade-repeatability-v1.json`
  has SHA-256
  `886284149745c6fdd74625fab5d97c21ad35cd9b69cc2ade4353194b4ecd1733`.
  This post-archive runner and result were created after the immutable Build 24
  source snapshot and are not Build 23 or Build 24 archive members or source
  inputs. The evidence qualifies only the recorded same-host, per-user,
  temporary-HOME, local ad-hoc Build 23-to-24 transition in which Application
  Support was retained; it does not establish automatic data cleanup. It does
  not qualify rollback, arbitrary N/N-1 versions, clean-machine or Finder/DMG
  installation, signed distribution, physical-device behavior, provider,
  network, or UI behavior, or production-release qualification.
<!-- aetherlink-current-build23-to-24-isolated-upgrade-v2:end -->

<!-- aetherlink-current-build24-clean-home-lifecycle-v1:start -->
The current G6 non-security Build 24 clean-HOME lifecycle slice executes the
latest immutable archive under a temporary per-user HOME. The installed-app
runner copied the exact ten-file manifest-matched app, completed two distinct
LaunchServices processes, verified all three SQLite files, and kept empty
Runtime chat plus every regular state-file byte and mode stable across
relaunch. The canonical 2,250-byte result is at
`dist/lifecycle/macos-packaged-app-build-24-clean-home-install-v1.json`,
SHA-256
`8646ff16bb5a152aab9c874c73a048a684d02e06fb3cbf7ed2f6172de51ff0c1`.

The state-recovery runner installed the same Build 24 tree, migrated one fixed
legacy Runtime-chat canary, removed the legacy source, and recovered the same
single SQLite row from a distinct SQLite-only relaunch. Both auxiliary
databases passed integrity checks, and the app tree plus remaining state bytes
and modes stayed unchanged. The canonical 3,364-byte result is at
`dist/lifecycle/macos-packaged-app-build-24-clean-home-state-recovery-v1.json`,
SHA-256
`d3205d662967d90d65baac6e5edc57bcc19c5f17c3963a1a3e53c95b07d44588`.
The installed-app runner and test SHA-256 values are
`55441bb84a9d8e4681af558dc7a1d017333c88fcdeb6ab2a84561c0ee093ca29`
and
`55274ad4abc958d85c4df1193cfe1508d820768fbbe48eae71a4fee8c1c020aa`;
the state-recovery runner and test SHA-256 values are
`9d05896a5dcce7e3d7642b41acba2ee4bf6d28ffda85bc8f3b2b645f2a3b273a`
and
`edfd6f89b2cecd6de5cbfcb337ba6f5643a8d74d7caf8735c467578488970664`.

These result files are post-archive execution evidence and are not Build 24
archive members. They qualify only the recorded same-host, per-user,
temporary-HOME, local ad-hoc Build 24 installation, relaunch, and fixed-canary
state-recovery observations. They do not establish clean-machine/account or
DMG/Finder installation, signing/notarization, rollback, automatic data
cleanup, physical-device behavior, provider, network, UI, accessibility, or
production-release qualification.
<!-- aetherlink-current-build24-clean-home-lifecycle-v1:end -->

<!-- aetherlink-current-build24-local-dmg-lifecycle-v2:start -->
The current G6 non-security Build 24 local-DMG lifecycle slice copied the
retained ZIP, manifest, and checksum sidecar into one private snapshot.
Archive readback, extraction, DMG creation, and the full exercise used those
same bytes, which were rehashed unchanged afterward. The runner created an
ephemeral HFS+ UDZO image with an Applications alias, mounted it read-only at
one fresh path, copied the exact ten-file manifest tree with `ditto`, detached
it before launch, and verified that no mount remained.

Two distinct LaunchServices processes completed under a temporary per-user
HOME. All three SQLite files passed integrity checks, Runtime chat remained
empty, the runtime identity was present, and every regular app/state byte and
mode stayed stable. The canonical 3,038-byte result is at
`dist/lifecycle/macos-packaged-app-build-24-local-dmg-install-v2.json`,
SHA-256
`7d4c6ae7d892bc9d639cc8dfbe5dfb02e09ff7019ee8554f652556ba7b1bb964`.
The v2 runner and ten-test module SHA-256 values are
`2ac25660c13f7a256fb2671a735255523cb8ec1c398128a53b2c46535af31b50`
and
`8b3cd5852c89735f2454cf4ae13d29024901dbbc7d915d37b4b3a58932558c91`.
Its preserved DMG primitive runner and shared snapshot-helper runner SHA-256
values are
`e082ce1aaf7f65bfb63bb2b5fd58136af1510eb6d1689faa1014c018b74129fb`
and
`abfd7bf5b0ef5154a4f001e1baafc134567a26e930714dffb0f057bcdb9fb095`.

This result is post-archive execution evidence and is not a Build 24 archive
member. It qualifies only the recorded same-host, per-user, temporary-HOME,
local ad-hoc mount/copy/relaunch observation. It does not establish Finder
drag-and-drop, downloaded-image quarantine or Gatekeeper behavior, system
`/Applications`, a clean machine/account, TCC or Keychain behavior, signed,
notarized, or stapled distribution, UI/accessibility, provider, network,
physical-device, arbitrary-history, crash/power-loss, concurrent-writer,
backup/restore/transfer, upgrade, rollback, production, or security
qualification.
<!-- aetherlink-current-build24-local-dmg-lifecycle-v2:end -->

<!-- aetherlink-current-build24-local-dmg-uninstall-reinstall-v1:start -->
The current G6 non-security Build 24 same-DMG uninstall/reinstall slice reused
one private archive snapshot and one ephemeral HFS+ UDZO image. It mounted the
same image bytes read-only at two distinct fresh mountpoints, copied the exact
ten-file manifest tree with `ditto` each time, detached before each launch, and
completed two distinct LaunchServices processes under one temporary per-user
HOME.

After each stopped launch, the runner removed only the exact temporary app
path. Across the first removal, same-image reinstall, second launch, and final
removal, Application Support, all three SQLite files, the runtime identity,
and every regular state-file byte and mode remained unchanged. Two complete
executions matched the same canonical 3,485-byte result at
`dist/lifecycle/macos-packaged-app-build-24-local-dmg-uninstall-reinstall-v1.json`,
SHA-256
`1e0daba4015ae36c8d96f11c424eb08a02855d3caa2e27b7838229cd55af5649`.
The runner and fifteen-test module SHA-256 values are
`300740d31a5b73755f6976f8fe6ce9c0f498cf274ed72d23d5d6c372104eb5ae`
and
`6e782fc128aad75b20f1b04752e4754ccbf8ceaadc9e2fcabe9cc2e537bfb703`.
The reused snapshot-bound DMG, preserved DMG primitive, exact-uninstall, and
snapshot-helper runner SHA-256 values are, respectively,
`2ac25660c13f7a256fb2671a735255523cb8ec1c398128a53b2c46535af31b50`,
`e082ce1aaf7f65bfb63bb2b5fd58136af1510eb6d1689faa1014c018b74129fb`,
`36bb3771aedc55c4c80c32a100e4feec83ee402a821dce168730543ebfd07afa`,
and
`abfd7bf5b0ef5154a4f001e1baafc134567a26e930714dffb0f057bcdb9fb095`.

This result is post-archive execution evidence and is not a Build 24 archive
member. It qualifies only the recorded same-host, per-user, temporary-HOME,
same-created-image uninstall/reinstall observation. It does not establish
Finder or system `/Applications` installation, downloaded-image quarantine or
Gatekeeper behavior, signing/notarization/stapling, a clean machine/account,
automatic Application Support cleanup, upgrade, rollback, UI/accessibility,
provider, network, physical-device, production, or security qualification.
<!-- aetherlink-current-build24-local-dmg-uninstall-reinstall-v1:end -->

<!-- aetherlink-current-build24-local-dmg-uninstall-reinstall-state-recovery-v1:start -->
The current G6 non-security Build 24 same-DMG state-recovery slice reused one
private archive snapshot and one ephemeral HFS+ UDZO image. The first
read-only mount installed the exact ten-file manifest tree. A distinct
LaunchServices process migrated the fixed 345-byte legacy Runtime-chat canary
to exactly one SQLite row, and the first exact app removal preserved the full
Application Support tree, including the legacy source, plus the runtime
identity without changing any regular-file byte or mode.

The harness then moved only that fixed legacy source into its temporary
preserved-fixture directory. A second fresh read-only mount of the same image
bytes reinstalled the identical app tree without touching the remaining
state. A distinct SQLite-only LaunchServices process read back the exact
344-byte event once; both auxiliary databases retained `integrity_check=ok`.
The second launch and final exact app removal preserved every remaining state
byte and mode. Two complete executions matched the same canonical 4,996-byte
result at
`dist/lifecycle/macos-packaged-app-build-24-local-dmg-uninstall-reinstall-state-recovery-v1.json`,
SHA-256
`e3c030df6cb83586f7401de2162ac8aa14cb44fbb7c7ca05b3305d9bb4edf17e`.
The runner and nine-test module SHA-256 values are
`31bdae72f08f1f68bc4a07cb59d194c943d56179acf0a7b149ddc2e652c68b4c`
and
`22ddc7ec39aa8c88c2b69f2dd8a390a287d85eeaff4704109784e221483faee2`.
The reused same-DMG, clean-HOME recovery, packaged-state recovery,
snapshot-bound DMG, DMG primitive, exact-uninstall, and snapshot-helper runner
SHA-256 values are, respectively,
`300740d31a5b73755f6976f8fe6ce9c0f498cf274ed72d23d5d6c372104eb5ae`,
`9d05896a5dcce7e3d7642b41acba2ee4bf6d28ffda85bc8f3b2b645f2a3b273a`,
`4f3094182ba3b87eb2bb89230df59a14ee10e1db15def87074e66c9ed68d2eca`,
`2ac25660c13f7a256fb2671a735255523cb8ec1c398128a53b2c46535af31b50`,
`e082ce1aaf7f65bfb63bb2b5fd58136af1510eb6d1689faa1014c018b74129fb`,
`36bb3771aedc55c4c80c32a100e4feec83ee402a821dce168730543ebfd07afa`,
and
`abfd7bf5b0ef5154a4f001e1baafc134567a26e930714dffb0f057bcdb9fb095`.

The DMG, captured logs, and preserved legacy fixture were temporary and are
not retained evidence. The canonical JSON is post-archive execution evidence,
not a Build 24 archive member. It proves only the fixed non-empty canary under
the recorded same-host, per-user, temporary-HOME, same-created-image flow. It
does not prove automatic legacy or Application Support cleanup, arbitrary
histories, Finder or system `/Applications`, quarantine or Gatekeeper,
signing/notarization/stapling, clean-machine/account, upgrade, rollback,
UI/accessibility, provider, network, physical-device, production, or security
qualification.
<!-- aetherlink-current-build24-local-dmg-uninstall-reinstall-state-recovery-v1:end -->

<!-- aetherlink-current-build24-local-dmg-abrupt-process-state-recovery-v1:start -->
The current G6 non-security Build 24 persisted-state abrupt-process recovery
slice reused one private archive snapshot and one ephemeral HFS+ UDZO image.
It read the retained Build 24 archive without consulting current source,
mounted the same image bytes read-only at two distinct fresh mountpoints,
copied the exact ten-file manifest tree with `ditto`, and detached before each
launch.

A first distinct LaunchServices process migrated the fixed 345-byte legacy
Runtime-chat canary to exactly one 344-byte SQLite event and exited through
bounded graceful termination. The first exact app removal preserved
Application Support and the runtime identity. The harness then moved only the
fixed legacy source into its temporary preserved-fixture directory, and a
second read-only mount of the same image reinstalled the identical app tree.

The runner launched that exact installed executable as a sandboxed owned child
in SQLite-only readback mode. Only after the exact 71-byte observation and an
independent persistence probe confirmed the committed canary and quiescent
state did it revalidate the executable identity, send `SIGKILL`, observe exit
code `-9`, reap that child, and prove its AppKit identity absent. The canary,
both auxiliary databases, runtime identity, app tree, and every recorded state
byte and mode remained unchanged immediately afterward. A third distinct
LaunchServices process then read back the same event once before final exact
app removal.

Two complete executions matched the same canonical 7,200-byte result at
`dist/lifecycle/macos-packaged-app-build-24-local-dmg-uninstall-reinstall-abrupt-process-state-recovery-v1.json`,
SHA-256
`0a7879ecea014123258a14d7f6f3790b7dc5859000941bf8faf76d2b12cb5124`.
The separate 921-byte repeatability receipt at
`dist/lifecycle/macos-packaged-app-build-24-local-dmg-uninstall-reinstall-abrupt-process-state-recovery-repeatability-v1.json`
has SHA-256
`98ec53d1018b0bebf88174a2fad514492b6ca1cff2afa1a6051e7335fabb3a36`
and binds two passed runs to those exact result bytes. The runner and
nineteen-test module SHA-256 values are
`ddd2c8286d1b78541d4ed18f125b9d1867be718e0276adb9880e60929fc15ec3`
and
`f06479f5eb4e12d3f0072e8259e9a7b1c28e8797a423ea88b092978a4142b658`.
The reused predecessor state-recovery, same-DMG, clean-HOME recovery,
packaged-state recovery, snapshot-bound DMG, DMG primitive, exact-uninstall,
and snapshot-helper runner SHA-256 values are, respectively,
`31bdae72f08f1f68bc4a07cb59d194c943d56179acf0a7b149ddc2e652c68b4c`,
`300740d31a5b73755f6976f8fe6ce9c0f498cf274ed72d23d5d6c372104eb5ae`,
`9d05896a5dcce7e3d7642b41acba2ee4bf6d28ffda85bc8f3b2b645f2a3b273a`,
`4f3094182ba3b87eb2bb89230df59a14ee10e1db15def87074e66c9ed68d2eca`,
`2ac25660c13f7a256fb2671a735255523cb8ec1c398128a53b2c46535af31b50`,
`e082ce1aaf7f65bfb63bb2b5fd58136af1510eb6d1689faa1014c018b74129fb`,
`36bb3771aedc55c4c80c32a100e4feec83ee402a821dce168730543ebfd07afa`,
and
`abfd7bf5b0ef5154a4f001e1baafc134567a26e930714dffb0f057bcdb9fb095`.

The DMG, captured logs, and preserved legacy fixture were temporary and are
not retained evidence. Both JSON files are post-archive execution evidence,
not Build 24 archive members. The signal occurred only after the fixed canary
was committed and independently observed; this is not an in-flight
transaction, hot-journal fault, write-durability, power-loss, kernel-crash,
OS-restart, UI Force Quit, arbitrary-history, or soak result. It does not
qualify automatic state cleanup, Finder or system `/Applications`, quarantine
or Gatekeeper, signing/notarization/stapling, clean-machine/account, upgrade,
rollback, UI/accessibility, provider, network, physical-device, production, or
security behavior. The canonical G6 exit and every G7 exit tier remain
incomplete.
<!-- aetherlink-current-build24-local-dmg-abrupt-process-state-recovery-v1:end -->

<!-- aetherlink-current-build24-macos-lifecycle-aggregate-readback-v1:start -->
The current Build 24 non-security macOS lifecycle aggregate is the standalone
read-only command
`python3 -I -B -S script/check_macos_build24_lifecycle_evidence.py`.
It opens and retains the repository root, seven exact directories, and all 40
unique target regular-file descriptors before hashing any target. It then
streams the exact Build 23 and Build 24 archive, manifest, and checksum
sidecars; the terminal version ledger; seven current lifecycle results; two
repeatability receipts; and 25 source files. Final entry and directory-graph
readback must match the held initial identities.

The checker independently rejects noncanonical or duplicate-key JSON,
non-exact integer, float, and boolean field types, wrong top-level schemas,
release or app-tree drift, reversed Build 23-to-24 direction, weakened
limitations, and receipt/result mismatch. It imports and executes no lifecycle
runner and performs no subprocess, image mount, app launch, file write,
network, device, or Git operation. The 12 exact focused unit modules remain
byte-bound inputs but are deliberately not executed by this static checker.

The standalone readback passed. A separate exact invocation of those 12
non-security unit modules passed 169 tests, and the aggregate checker's own 22
mutation and boundary tests passed. The 72,502-byte checker has SHA-256
`d4c81d6329e1e6869d8b352daf20e415782ff6debfb064844844e6ce8b79fd8e`;
the 31,405-byte test module has SHA-256
`96e724bf307ae83564c1169aefcade59f01f3886662f9aca954f32e5a6cfe19a`.

This gate publishes or rewrites no lifecycle result and creates no new install,
launch, DMG, upgrade, recovery, or repeatability observation. Build 23 remains
a retained historical predecessor, not a declared rollback lineage. The pass
is bounded static/no-device consistency evidence and preparation for a future
G7 deterministic check; it is not canonical G7 PR-fast completion and does
not complete the signed, physical-device, network, rollback, production, or
other remaining G6/G7 exit requirements.
<!-- aetherlink-current-build24-macos-lifecycle-aggregate-readback-v1:end -->

<!-- aetherlink-current-build24-macos-idle-resource-stability-v1:start -->
The current Build 24 non-security macOS idle-resource stability observation
used one exact packaged-app child under an isolated temporary HOME. After a
60,000 ms warm-up it retained 120 libproc samples at 5,000 ms targets across
600,000 ms. The maximum observed sample lateness was 79 ms.

The first and final 12-sample upper medians and full-run maxima were 10, 10,
and 10 open file descriptors; 142,344,192, 142,344,192, and 142,393,344
resident bytes; and 3, 3, and 4 threads. Final deltas were 0, 0, and 0;
peak deltas were 0, 49,152, and 1. All stayed within the predeclared local
regression budgets. The exact owned child accepted graceful termination,
exited with status 0, was reaped, and disappeared from AppKit. The preexisting
AetherLink app was preserved, no raw process identifier or temporary path was
retained, and the temporary root was removed before publication.

The canonical 22,534-byte result is at
`dist/lifecycle/macos-packaged-app-build-24-idle-resource-stability-v1.json`,
SHA-256
`07d28a073746731241932681630014647ad452e382afd6728938daacb39e167f`.
The 45,998-byte runner and 32,632-byte 25-test module have SHA-256 values
`073e58afa67228d6c208186d8ddca790b763a9c0a7acee9d5a681ff1f22801a9`
and
`df8a04a0e46e7ef0cc10a1f5dc29f3f8f9763e960995427304a7ccd93a2e8e4b`.

The standalone read-only command
`python3 -I -B -S script/check_macos_build24_idle_resource_stability_evidence.py`
opens 16 fixed archive, ledger, result, runner, test, and transitive-source
files before hashing. It rechecks their held path graph, rejects noncanonical
or duplicate-key JSON and boolean/integer aliasing, and independently
recomputes all 120 targets, maximum lateness, upper medians, deltas, maxima,
limits, and pass flags. Its 36,411-byte checker and 38,633-byte 25-test module
have SHA-256 values
`4b5829e4fc44f250a0cdda6586edcb6c781ec1a1c49e605d884a1210a1634bb4`
and
`9cc1992ecf4612590e33d8e20e2dd341b729a1335f488605a7cb06670ece34cf`.

This is one same-host, per-user, network-denied, point-in-time local idle
observation. It is not repeatability, load, performance-SLA, capacity,
long-soak, install, upgrade, recovery, rollback, device, provider, UI,
accessibility, production, or G7 Weekly resilience evidence. No signing or
signature verification was performed.
<!-- aetherlink-current-build24-macos-idle-resource-stability-v1:end -->

- Build 19 remains the first archive to source-bind the Runtime-chat SQLite
  cross-process helper/runner. Its deterministic timeout/rollback coverage and
  separate 48+48 writer/third-process readback observation remain Build 19
  evidence and are not relabeled as Build 22 work. Build 18 remains the first
  archive to source-bind the Android drawer-search inputs.
- Production connections use a 5-second busy timeout and normalize busy/locked
  failures to one stable retry message. Three deterministic Swift tests cover
  wait-and-release success and rollback after `BEGIN` or `COMMIT`.
- The historical live result observed 96 disjoint events exactly once with
  owner/session isolation, per-writer order, SQLite integrity, `0700`
  directory mode, and `0600` file mode. It is separate execution evidence, not
  an archive member, and does not qualify crash/power-loss, arbitrary
  histories, mixed binaries, or production behavior.

<!-- aetherlink-current-build21-abrupt-recovery-v1:start -->

- Build 21 adds the canonical 2,223-byte abrupt-process recovery result at
  `dist/lifecycle/macos-runtime-chat-sqlite-abrupt-process-recovery-build-21-v1.json`,
  SHA-256
  `db66614d7badd7a0f606c03f91a516dff6d77e539684dcb6daf52709bce0f16f`.
  Two identical executions record 24 committed events, one dirty uncommitted
  25th event and FTS row after exact child `SIGKILL`, rollback-journal recovery to
  24, and production-store resume to 48 contiguous exactly-once events. This
  is bounded same-host abrupt child-process `SIGKILL` recovery evidence,
  explicitly `not-production-append-crash-point`, not power-loss or
  kernel-crash evidence, not arbitrary-history or long-soak evidence, and not
  clean-machine, signed-distribution, or physical-device evidence.

<!-- aetherlink-current-build21-abrupt-recovery-v1:end -->

<!-- aetherlink-historical-build20-lifecycle-v1:start -->

- Build 20 retains historical same-host, per-user clean-HOME installed lifecycle
  evidence. The 2,250-byte install/relaunch result is
  `dist/lifecycle/macos-packaged-app-build-20-clean-home-install-v1.json`,
  SHA-256
  `4ce047a318e47568d647e1167cbaeebc603626073e098451a29c949086aa3d72`.
  The 3,364-byte legacy-to-SQLite-to-SQLite-only result is
  `dist/lifecycle/macos-packaged-app-build-20-clean-home-state-recovery-v1.json`,
  SHA-256
  `d12947e16e7b985515a90a13731947a5991bcd82a06039210e22bba43535bf0b`.
- The separate 2,434-byte ephemeral local-DMG result is
  `dist/lifecycle/macos-packaged-app-build-20-local-dmg-install-v1.json`,
  SHA-256
  `e78b605278d5c5b7f5601778c38f35270f1db4a9e95055ff434b71af4c33cf78`.
  It covers a verified temporary HFS+ UDZO image, one read-only fresh mount,
  exact `ditto` copy of the release tree, unmount before two distinct launches,
  SQLite integrity, empty Runtime chat, and stable installed state.
- Both clean-HOME runners were invoked twice and matched their canonical
  results.
- These historical same-host, per-user Build 20 observations do not qualify a clean
  machine/account, signed/notarized distribution, UI/accessibility,
  live-provider behavior, a physical device, arbitrary histories,
  crash/power-loss, concurrent writers, backup/transfer, rollback, or
  production readiness. The DMG run remains outside Finder UI, drag-and-drop,
  Gatekeeper quarantine/download behavior, and system `/Applications`
  evidence. PID 59809 remained alive.

<!-- aetherlink-historical-build20-lifecycle-v1:end -->

- Build 16 preserves one successful publication separately from a failed
  preceding attempt and failed confirmation. The two failures observed the same
  intermittent Swift executable/dSYM variants with reversed lane assignment.
  Build 17 does not retroactively qualify Build 16.
<!-- aetherlink-current-android-drawer-search-ux-v2:start -->

- The current unreleased Android drawer provides an explicit touch Search
  action with localized accessibility semantics and the keyboard Search action
  through one trimmed-query submission path. Blank, disconnected, streaming,
  bulk-mutation, and exact same-query pending states expose localized
  action-state descriptions without dispatching. Only the exact current
  pending query shows a polite localized progress live region and suppresses
  the no-results row; editing or clearing the query closes that request and
  invalidates its transient search authority. Only an exact current-query
  remote response is adopted; stale or absent response state falls back to
  immediate local filtering, while current remote results exclude archived
  sessions and retain global Runtime rank. The current no-device gate passes
  168 AppNavigationTest cases, 22 navigation-drawer Compose cases, 15
  search-related RuntimeClientViewModelTest cases, and the complete 1,194-test
  app JVM suite; release lint reports 0 errors and 2 SDK-version warnings.
  This source/JVM/Compose evidence is not part of the immutable Build 17 archive and is first source-bound by the immutable Build 18 archive; it does not establish physical touch, TalkBack, provider, device, network, installation, signing, or release behavior.

<!-- aetherlink-current-android-drawer-search-ux-v2:end -->
- The multilingual full-matrix V3 path now leaves the frozen V2 task, scorer,
  runner, schema-4 fixture, and failed result byte-identical while completing
  both full 80-ranking/80-repeatability maps for both exact candidates. The
  live run found and fixed V3-only `/var` path canonicalization and recovery
  snapshot-prefix defects; thirteen Python regressions now pin those boundaries
  and the recorded result. The 3,570-byte
  `docs/evidence/ollama-embedding-multilingual-full-matrix-v3.json` result has
  SHA-256
  `ca8279bafbe04a6de820caf1b855e4a2b6a09eb561602dd7773f1bfc190bda47`.
  Each exact version passes 76/80 ranking and 80/80 repeatability comparisons,
  with identical Korean and French scenario ordinal 2 ranking misses. Both
  fresh-provider recoveries pass and `sourceStatePreserved=true`. This is a
  complete failed-quality observation, not a passing multilingual claim.
- The current unreleased product slice adds a bounded semantic-similarity
  rerank after retrieval ranking for strong-revision EmbeddingGemma profiles.
  Its pool is derived from the visible limit, contains 8 through 32 available
  non-research candidates, and may reorder only primary-score groups inside an
  inclusive 0.05 cosine window.
- Scaled cosine closes finite-vector norm overflow. Exact boundary,
  strong-winner, transient/no-cache rerank, failure/profile-drift fallback,
  visible-limit, and final-snapshot research-promotion regressions pass. If
  research membership changes before final coordinated publication, the
  retained primary materialization is published before filtering and visible
  search ranks are renumbered from one. Sixteen focused checks and the
  post-review 544-test broad router/search run pass. The current full Swift run
  passes 2,084 tests with zero failures and
  11 expected opt-in/live skips.
- The frozen multilingual V2 result remains
  `qualityGatePassed=false` at Korean ordinal 2 on both exact candidates. The
  product reranker is not a model qualification and must not be described as
  one. Its recorded router/fingerprint hashes remain historical, and the live
  V2 runner correctly rejects the changed product-source bytes until a future
  versioned observation is prepared.
- Build 14 is a frozen historical ledger archive that binds the settled
  reranker, Android drawer-search inputs, dual AAB structure validation, and
  Research Notebook deletion saved-state lifecycle to its recorded 240-file
  source snapshot. Two independent two-root qualification executions
  reproduced the same archive, and source-bound readback passed when Build 14
  was current. Its archive now passes only historical readback; the complete
  Android app gate passed 1,183 tests. Its evidence does not transfer to Build
  15.
- The Research Notebook two-step permanent-delete confirmation now restores
  its target atomically and rebinds only to the same trusted Runtime, notebook,
  session, and archived state. It waits through an unresolved catalog, then
  clears for authoritative absence, active/replaced targets, or Runtime
  changes without invoking deletion. Release lint reports 0 errors and 3
  existing warnings; GPT-5.6 Sol review reports no P0-P3 finding.
- Build 14 has a frozen historical same-host, per-user clean-HOME installation
  rehearsal. The exact packaged app was copied with `ditto` to a temporary
  `Applications/AetherLink.app`; all ten manifest-bound files and the ad-hoc
  seal matched. Two exact-path LaunchServices runs reached regular activation,
  completed five-second observations, used distinct PIDs, and terminated
  cleanly. The three expected SQLite files passed integrity readback,
  Runtime-chat stayed empty, and isolated regular-file bytes and modes did not
  change across relaunch.
- The canonical result is
  `dist/lifecycle/macos-packaged-app-build-14-clean-home-install-v1.json`,
  2,250 bytes with SHA-256
  `dba559878af78be5057b50f4fb5a759e0308724f93b6c358ce2c5e6981d7f6c2`.
  Its runner and ten-test source SHA-256 values are
  `55441bb84a9d8e4681af558dc7a1d017333c88fcdeb6ab2a84561c0ee093ca29`
  and
  `56127b93951ede623f3b30a4149d83305104841717cd84b0541a44b357e6b161`.
  Existing PID 59809 remained at its original Build 4 path and was never
  selected or terminated. This is not clean-machine/account, DMG/Finder,
  signed/notarized, UI/accessibility, provider, or physical-device evidence.
- Build 14 has a separate frozen historical installed state-recovery result. The
  first exact-path LaunchServices process migrated the fixed legacy JSONL
  canary to one Runtime-chat SQLite row; after legacy removal, a distinct
  second process recovered the same row from SQLite only. Both auxiliary
  databases passed integrity checks, and the installed app tree plus all
  remaining state-file bytes and modes stayed unchanged across relaunch.
- That immutable result is
  `dist/lifecycle/macos-packaged-app-build-14-clean-home-state-recovery-v1.json`,
  3,364 bytes with SHA-256
  `434cec7c2fd396a56788abdcfa48edd913950331cedf91159a11f8acc02f657d`.
  A second complete invocation matched the published bytes. The runner and
  eleven-test source SHA-256 values are
  `9d05896a5dcce7e3d7642b41acba2ee4bf6d28ffda85bc8f3b2b645f2a3b273a`
  and
  `3a77f1773c927c9a1d7714138cb283bb2eaee5c93243dd9f558a3ca39e5245b2`.
  This remains same-host, per-user evidence and does not qualify arbitrary
  histories, crash/power loss, concurrent writers, clean-machine/account,
  DMG/Finder, UI/accessibility, provider, signing, or physical devices.
- The post-qualification fake-toolchain macOS package test now derives the
  expected marketing/build versions from its copied ledger instead of pinning
  historical Build 6. All nine `script.test_build_and_run` cases pass. This
  worktree-only test maintenance does not modify the archived Build 14 bytes.
- The exact packaged Build 13 app historically passed a two-process state-recovery
  smoke. The first isolated process migrated one fixed benign legacy JSONL
  event through the production store and model projection. After exact-PID
  termination and legacy removal, the second independent process recovered the
  same single SQLite row. The 2,185-byte result SHA-256 is
  `21f30e0b60e81bcbfb7e8a198c68ef53d6f6c739a63c80a1339278b7565ea769`.
  Build 12's marker-file attempt failed closed and published no result; Build
  13 evidence does not transfer to Build 12 or Build 14. Build 14's historical
  state-recovery observation is independently bound to Build 14 and does not
  transfer to Build 17 or Build 18.
- The current Android accessibility slice raises the existing Chat and Settings
  no-device multilingual regressions to font scale `2.0`, covering `en`, `ko`,
  `ja`, `zh-CN`, and `fr`.
- Chat is exercised at 320 x 470 dp and Settings at 260 x 760 dp. Both focused
  tests pass, and copy hygiene prevents a silent reduction of the 200%
  qualification ceiling.
- Android App Bundle language splitting is now disabled so the existing
  five-language in-app picker does not depend on Play Core language downloads.
  String parity, offline lint, and an unsigned release AAB build pass.
- All 23 shared plural resources now use locale-correct Android/CLDR category
  sets: English/default `one/other`, Korean/Japanese/Simplified Chinese
  `other`, and French `one/many/other`. Eight terminal strings use typographic
  ellipses across all six resource sets; nine additional count-sensitive
  summaries use quantity-aware singular grammar, while three nonplural cases
  have narrow per-resource ignores. A clean ten-test affected-path slice and
  independent GPT-5.6 Sol review pass.
- Android release builds now enable R8 and resource shrinking with the
  optimized defaults and dependency consumer rules, without a broad app keep
  file. A clean offline APK/AAB/lint run passes. V1 Release is arm64-only: the
  unsigned AAB is 10,667,371 bytes, has one DEX, embeds its mapping byte-for-byte,
  and retains all five locales and five JNI libraries. Production signing,
  final ID, Play delivery, and physical release launch remain unclaimed.
- Five Compose screen APIs now follow required-parameter/`modifier` ordering,
  two Modifier factories are receiver extensions, and eight integer states use
  primitive Compose state. A clean 22-test focused run passes; all three
  targeted issue IDs remain absent. After resource and localized-copy cleanup,
  current release lint is at 0 errors, 3 warnings, and 0 hints.
- Fifty unused keys per locale set and ten API-25-and-earlier launcher PNGs are
  removed. The API-26 adaptive standard/round icons include a generated
  monochrome layer, and the canonical generator/checker pins this structure.
  Three KTX findings and the locale-config warning are also gone. Physical
  launcher rendering remains unclaimed.
- The 840dp permanent-navigation breakpoint now uses the actual Compose window
  container width with density-aware `Dp` conversion. Focused breakpoint and
  top-bar behavior tests pass.
- Chat message copy-action and outer Markdown/fenced-code parsing are memoized
  by unchanged content. Seven focused parser/render/copy regressions pass; no
  benchmark claim is made.
- Chat follows Android's disabled-animation setting: streaming progress becomes
  static and automatic/manual latest-message scrolling becomes immediate.
  Policy, dual-mode multilingual streaming layout, and jump-to-latest
  regressions pass; no physical accessibility-setting claim is made.
- macOS `--package-only` now produces a no-launch Swift Release app with the
  target SwiftPM localization bundle inside `Contents/Resources`, semantic and
  build versions, and a strict local ad-hoc seal. Five packaging regressions and
  the complete 145-test localization class pass, as does real package
  structure/signature verification. Build 20 retains separate historical
  ephemeral local-DMG evidence; Developer ID/notarization,
  downloaded/quarantined Gatekeeper,
  Finder UI/drag-and-drop, and clean-machine launch remain unclaimed. Intel is
  Post-V1.
- `release/version-ledger.tsv` is now the single version source for Android
  Release and macOS packaging. The latest published qualification reads back as
  `1.0.0+24`; Android Debug stays `0.1.0+1` and builds with the ledger absent.
  Python, Bash, and lazy Gradle consumers reject noncanonical control bytes;
  strict parser, source, artifact, and fake-toolchain checks pass.
- The Build 24 qualification runner clean-builds both targets in two isolated
  source roots whose UTF-8 byte lengths are 101 and 109, and publishes
  `dist/releases/aetherlink-1.0.0+24-local-v1/`. Its 166,345,274-byte canonical
  normalized-input ZIP has SHA-256
  `104c07b6fc1b421bcc0309657001fdf991e37bb815c282b3e5112ed98821ab1c`.
  The exact v4 comparison-only and publish-qualified results listed at the start
  of this lane both record byte-identical lane output; only the canonical result
  publishes and independently reads back the archive. The publish-qualified
  result also binds the exact prepublication result and proves the protected
  Build 23 archive identity remained unchanged.
  Independent readback verifies 29 payload members, arm64-only APK badging,
  AAB mapping/JNI identity, exact `base`-only structure through
  `bundletool 1.18.3 validate`, direct base-manifest package/version/SDK and
  backup-policy fields, independent APK policy-resource resolution, and
  the arm64 app/dSYM UUID
  `3FDC3DBC-3A74-3A3B-A87D-03CB432B5D46`. Android native symbols remain
  explicitly unavailable because all five upstream JNI inputs are pre-stripped.
  The 249-file source is explicitly a `dirty-content-snapshot`; commit
  `7d72147528e334edb19b9331ed7933ac71ca424b` alone cannot reconstruct the
  archived bytes. Compliance profile `aetherlink-release-compliance-v2`
  requires a 350-package Gradle lock/POM catalog, fixed metadata, text
  inventory, and SPDX 2.3 JSON. It records 692 exact package roles: 202
  runtime, 155 build dependency, and 335 build tool. Build 7 remains readable
  under its frozen profile-less, precedence-compressed 350-relationship V1
  contract. The catalog retains POM URL/size/SHA and parsed declarations, not
  original POM bodies or license/NOTICE texts. Offline verification does not
  re-fetch or re-parse those originals and does not prove attribution
  completeness, binary/source coverage, or legal compatibility. SwiftPM has
  zero external dependencies and all third-party license conclusions remain
  `NOASSERTION`.
  R8 `resources.txt` now uses semantic reachability normalization; the other
  declared metadata surfaces retain their independent normalization contracts.
  Six Gradle locks reached a writer fixed point and passed two strict read-only
  clean Release runs unchanged; the manifest declares the one
  `kotlin-stdlib-common` compatibility exception. SwiftPM has zero external
  dependencies. Fixed Clang importer and debug compilation directories plus a
  canonical source-location alias remove the observed source-path-length byte
  dependence while retaining the dSYM. The two recorded v4 A/B executions
  produced a byte-identical ZIP, manifest, checksum sidecar, and 30-entry
  archive inventory. This is bounded evidence for two recorded same-host,
  fixed-toolchain/cache-snapshot, canonical-scratch pairs with serialized Swift
  frontend work, not a claim that
  arbitrary repeats are variance-free. Arbitrary roots or path lengths,
  cross-host reproducibility, signed artifacts, clean-machine launch, and
  physical behavior remain unclaimed. Builds 1 through 23 remain immutable,
  independently readable historical archives. The
  verifier now cross-binds Gradle lock identities to the archived source
  inventory and rejects use of historical mode for the current release.
- The historical
  `script/run_macos_packaged_app_build10_lifecycle_smoke.py` gate fixes the
  exact Build 10 ZIP, manifest, executable, and macOS UUID contract. At its
  original qualification it used then-current-source readback before extracting
  only the packaged app and completed two AppKit finished-launch →
  five-second minimum observation →
  identity-rechecked exact-PID termination cycles with zero exits. Its QA-only
  sandbox uses a temporary Core Foundation user home, verifies a temporary-root
  write, denies a non-temporary write and AF_INET bind, and has no unisolated
  fallback. The exact 1,313-byte result at
  `dist/lifecycle/macos-packaged-app-build-10-lifecycle-v1.json` has SHA-256
  `c0ea4dba08e74130f7aaa1e9855121d02459249ff5e6a0fc27cd1b01f46f0ded`.
  Expected Application Support files were present after both runs, but the
  runtime identity file was absent after both.
  The new runner reuses the exact SHA-256-pinned historical process engine
  without changing the Build 9 runner, test, or 1,311-byte result at
  `dist/lifecycle/macos-packaged-app-build-9-lifecycle-v1.json`, whose SHA-256
  remains
  `aad796ee3c768e37953f18eeea0e6642107750c3a8c398df798a46e96aabab53`.
  PID 59809 stayed alive at the same path with executable SHA-256
  `93cb550903f74e5018514870d1f4e7ac95ffc5df915fb8bde48c1ff512b382d0`.
  The Build 10 observations remain bound to Build 10 and are not reinterpreted
  as Build 14, Build 17, Build 18, or Build 19 evidence. Do not claim identity persistence, Runtime-chat
  migration/readback, UI correctness, listener/provider readiness,
  installation, clean-machine behavior, signed distribution, or
  physical-device behavior from the historical smoke.
- The versioned
  `docs/releases/1.0.0-build-24-local-v1.md` record now consolidates release
  notes, compatibility, migration, limitations, diagnostics, privacy/evidence
  boundaries, and rollback. It explicitly treats Android Debug `0.1.0+1` and
  local ad-hoc macOS packages as non-upgrade lineages. Build 6 remains a
  historical archive and owns the separate packaged-app lifecycle result; its
  standalone reproducibility result bytes were not retained. Build 7 preserves
  the first compliance inventory and documents why its one-role-per-package
  mapping was superseded. Build 8 preserves the first exact-role V2 compliance
  qualification and its bounded repeatability record. The
  fixture-rich
  `docs/releases/1.0.0-build-3-local-v1.md` historical record retains the
  canonical first-lineage fixture, which pins a null production predecessor,
  unproven N/N-1, clean install plus fresh pairing, and false
  migration/in-place-upgrade claims against the release ledger and G0
  non-security release fields.
- The same Build 3 historical record embeds the dated provider fixture. Official
  current/previous candidates are Ollama `0.32.5`/`0.32.4` and LM Studio
  `0.4.20` build 1/`0.4.19` build 2. Local schema smoke covered Ollama
  `0.32.4` and LM Studio `0.4.17-beta+3`. SHA-256-verified official Darwin
  archives for both exact Ollama candidates passed four isolated empty-catalog
  adapter runs covering cold start, exact version, health, restart, and
  stopped-endpoint unavailability. The same versioned runner's explicit
  model-backed mode selects one already-installed unloaded chat model without
  retaining its name, snapshots its manifest plus 2,138 content-addressed blobs
  through copy-on-write, and passes another four exact-candidate runs covering
  populated catalog, bounded completion, first-delta cancellation,
  post-cancel recovery, confirmed unload, installed-state preservation, health,
  byte-identical SHA-256 snapshot state, and stopped-endpoint unavailability.
  The dedicated
  `script/run_ollama_additional_chat_shape_matrix.py` runner fixes the exact
  second of three completion-capable candidates, requires its recorded
  `completion`/`thinking`/`tools` tuple and initially unloaded state, and never
  falls back. Its 991 verified blobs plus 213,712-byte manifest total
  16,679,502,421 model-artifact bytes. Both exact versions passed cold/restart
  for 4/4 chat, first-delta cancellation, recovery, unload, snapshot, and
  endpoint observations; the observed source catalog/capabilities, running set,
  selected bytes, and bound source files remained unchanged, with no model
  download or retained model name, prompt, output, path, PID, or base URL.
  The runner's separate embedding-backed profile snapshots the smallest
  already-installed unloaded embedding model as four verified blobs plus one
  manifest and passes another four exact-candidate cold/restart runs covering
  a two-input finite equal-dimension batch, residency, unload, installed-state
  preservation, health, snapshot integrity, and endpoint shutdown. Its separate
  semantic-quality gate now also passes both exact candidates against four
  fixed English ranking scenarios in two 16-text permutations. Every positive
  clears both negatives by at least 200 cosine basis points, all 16 repeated
  texts reach at least 9,990 cosine basis points, and each version then passes
  one fresh-provider ordinary embedding recovery. Each phase also proves
  exactly one matching XCTest ran, and the canonical evidence binds the
  semantic scorer plus live assertion sources by SHA-256. A third
  five-locale V2 observation leaves that English V1 record unchanged. It fixes
  four within-locale scenarios per locale and the same 200/9,990-basis-point
  thresholds before execution. Both exact candidates completed and
  shape-validated both 80-text batches, passed the four English rankings,
  then failed the positive-margin check at Korean scenario ordinal 2.
  Japanese, Simplified Chinese, French, and repeatability were not evaluated
  after the fail-closed result, and neither the task set nor thresholds were
  changed afterward. Both candidates then passed a fresh ordinary embedding
  recovery with confirmed unload and unchanged source/task/snapshot bindings.
  The V2 fixture retains only the failed locale and ordinal, not a model name,
  task text or ID, vector, dimension, score, provider output, path, PID, or
  base URL. Expected-failure classification requires one bounded regular
  UTF-8 log, exactly one matching XCTest start/failure, and one closed
  locale/ordinal diagnostic; cleanup errors always remain fatal.
  Multilingual qualification therefore remains open. A third
  vision-backed profile snapshots one already-installed unloaded
  `vision + completion` model as 997 verified blobs plus one manifest and passes
  four more cold/restart runs covering text chat, one fixed PNG attachment,
  first-delta cancellation, post-cancel recovery, residency, unload,
  installed-state preservation, health, snapshot integrity, and endpoint
  shutdown. No model download or retained model name/input/image/output/vector
  value occurred. The source provider version, observed catalog
  `name`/`digest`/`size` projection, running-model identity set, and every
  selected source-file byte remained unchanged; unselected model-store bytes
  and unprojected catalog metadata were not compared. Seven deterministic
  mocked failure regressions
  additionally prove provider stop plus snapshot recheck after an adapter
  exception, Popen/stop/snapshot-error priority, temporary-root removal before
  post-failure source readback, and rejection of provider-version,
  catalog-projection, running-set, or selected-file drift. This is mocked Python
  failure evidence, not an OS kill, power-loss, or cleanup-permission test. The
  same runner's
  opt-in duration path uses one `time.monotonic_ns` clock for the absolute
  20-second ready, 10-second stop, and observed execution boundaries. A dated
  12-phase run passed all three profiles, both versions, and cold/restart:
  provider-ready was at most 5,533ms, adapter execution at most 54,784ms, and
  stop at most 3ms. The SHA-256-pinned exact observations are not an SLA,
  average, percentile, throughput, or cross-host claim. A separate opt-in live
  path exercised unavailable-before-request, process-group termination after
  the first non-empty chat delta, and forced termination after `SIGSTOP` on
  both exact versions. All six fault observations and six full adapter/unload
  recoveries passed with process-group reap, endpoint shutdown, snapshot
  integrity, and source projection/byte preservation. Terminal-less stream EOF
  now maps to fixed retryable `ollama_transport_error`. This does not qualify
  embedding/vision faults, power loss, OS crash, cleanup-permission failure,
  concurrency, soak, or an SLA. The passing English V1 task does not establish
  broader retrieval accuracy or other model shapes, and the separate V2
  multilingual gate is an explicit failed-quality observation rather than a
  qualification. The focused suites pass 148
  of 157 tests with nine opt-in skips. Seventy-one runner tests, 42
  documentation/handoff tests, and docs hygiene pass. Exact LM Studio
  candidate execution remains deferred because the official tools expose no
  independent user-data/model-store path for a non-invasive run. Minimum
  versions, broader semantic quality, further model-shape coverage, and full
  live-provider qualification remain unresolved.
- The pre-reranker full Swift run executed 2,045 tests with zero failures and the
  nine expected opt-in skips. Docs/copy hygiene, ledger readback, 113 combined
  runner/documentation tests, Python syntax, diff whitespace, and the empty
  staging guard pass. The Build 9 archive binds that earlier settled source
  snapshot and passes historical readback. Build 24 binds the current
  reranker, Android drawer-search inputs, APK/AAB backup-policy validation, and
  Research Notebook deletion lifecycle plus the Runtime-chat SQLite
  cross-process QA sources. Build 19 remains the first archive to bind that
  cross-process QA closure; Builds 1 through 23 pass historical ledger-prefix
  readback. Build 14 and Build 13 retain only their own packaged lifecycle
  observations. No physical-device claim was made.
- The Build 24 manifest captured source HEAD and `origin/main` as
  `7d72147528e334edb19b9331ed7933ac71ca424b` at qualification time. The
  archived source inventory, not either commit alone, remains the Build 24
  source identity. Separately, at the 2026-07-31 00:03 KST refresh, `main` and
  `origin/main` both resolved to
  `7d72147528e334edb19b9331ed7933ac71ca424b`. Run
  `git rev-parse HEAD` and `git rev-parse origin/main` before making any new
  current-state claim. Codex did not stage, commit, or push. The current
  documentation remains a local workspace change; preserve it and all
  historical release/lifecycle evidence when continuing.
- Do not stage, commit, or push these local changes unless the user explicitly
  requests it.

## Current Truth Versus Historical Evidence

- This file is the current continuation contract. Its snapshot, behavior,
  evidence matrix, proof boundaries, and next-session flow take precedence over
  older chronological entries in `docs/progress.md`, `docs/qa-evidence.md`, and
  `docs/roadmap.md`.
- This handoff and the canonical section at the top of `docs/roadmap.md` carry
  the current 2026-07-28 G2 summary. `docs/progress.md` and
  `docs/qa-evidence.md` retain their dated execution snapshots. Sections
  explicitly labeled historical or superseded record what was true at that
  checkpoint; they do not override this handoff.
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

### Current G2 Rung-Three Dependency Fixed-Point Waves

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
operation occurred. Repository-owner authentication, external identity proof,
execution-permit authentication or documents, and user action remain outside
this local workflow.

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
socket, network, device, deployment, and Git write remain unauthorized.
`externalAuthenticationRequired=false` and `userActionRequired=false`.

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
`repositoryOwnerIdentityProofRequired=false`,
`externalAuthenticationRequired=false`, and `userActionRequired=false`.

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

That action was later completed in the historical
[wave2 one-use execution permit v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave2-execution-permit-v1.json)
and
[reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave2-execution-permit-v1.md).
At that unconsumed v1 checkpoint it recorded
`status=wave2_v1_dependency_source_acquisition_authorized_not_consumed`,
`result=exact_15_public_proxy_mod_then_zip_pairs_authorized_once_not_executed`,
and `nextAction=execute_bound_dependency_source_wave2_v1_once`; its focused
evidence was 37/37 decision, 41/41 permit, 50/50 runner, and 39/39 readback
checks. Those values are historical permit facts, not the current execution
state.
The versioned Wave2 recovery path subsequently retained and independently read
back 30 exact `.mod`/`.zip` resources. Wave3 then completed 16 conflict-free H1
pairs, consumed its separate one-use permit, retained 32 resources, and
completed independent readback.

Combined-v2 held 101 exact source inputs, reconstructed the graph twice, and
projected a non-fixed 16-tuple Wave4 frontier with three
graph-selected and thirteen retained version-specific vertices. The
[Wave4 identity/acquisition decision v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave4-v1.json)
and
[reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave4-v1.md)
reproduce 22 parent declarations, 24 module-ZIP H1 witnesses, and 26 `go.mod`
H1 witnesses in two identical offline scans. All 16 identity pairs are
conflict-free. The separate
[Wave4 one-use acquisition permit v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave4-execution-permit-v1.json)
and
[reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave4-execution-permit-v1.md)
bound the exact 32-request contract and was consumed once. Attempt
`4cda3d86462fff445d6e69bce4b92dec` retained all 32 resources
(16 `.mod`, 16 ZIP; 24,118,812 bytes). The separate
[Wave4 independent readback](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave4-readback-v1.json)
reopened and independently verified every byte twice; its
[manifest](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave4-readback-manifest-v1.json)
was written last.

The current combined-v3 checker holds 133 exact source inputs (root ZIP,
66 `.mod`, 66 dependency ZIP), reconstructs the graph twice, and records
`fixedPointReached=false` with an exact 15-tuple Wave5 frontier. Its input-set
SHA-256 is
`b2d981dae1576f27ae5cd292e218b0a0eb35f5bdc0d98734fb1b350408ce4eca`,
graph SHA-256 is
`ee330142d77874457cccf78d5a9fe51652c81916f1d7aabb390f321dff51e03a`,
and its focused suite passes 23/23. The separate Wave5 candidate checker
retains all 15 version-specific vertices even though all graph-selection flags
are false, and passes 10/10. The
[Wave5 identity/acquisition decision v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave5-v1.json)
and
[reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave5-v1.md)
reproduce 20 parent declarations, 20 module-ZIP H1 witnesses, and 22
`go.mod` H1 witnesses twice from the held 133-input set. All 15 identity pairs
are complete and conflict-free. The compact identity SHA-256 is
`52567cdead3fcd8029f9c1676a7f83af86a5d0110c52851b47e55b2f09af8a7d`,
the full witness SHA-256 is
`af51e067ccf3388561bfe0e2b38dae744792625cdc5f7a37b55208b41d4a5fb4`,
and its focused suite passes 11/11. At that checkpoint the decision prepared
30 distinct ordered requests without authorizing acquisition. The separate
[Wave5 one-use acquisition permit v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave5-execution-permit-v1.json)
and
[reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave5-execution-permit-v1.md)
were consumed exactly once. Acquisition attempt
`ed050bd13835ab1f9fecc0dd3cfb6e12` retained all 30 resources
(15 `.mod`, 15 ZIP; 26,123,889 bytes) without extraction, loading,
execution, or compilation. The separate
[Wave5 retained-snapshot readback](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave5-readback-v1.json)
recomputed every raw hash and H1 plus ZIP safety, CRC, root `go.mod` parity,
and aggregate counts twice before its
[manifest](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave5-readback-manifest-v1.json)
was written last. Readback attempt
`8f3813a784359883b4d93370c9041809` applies completion only to the retained
snapshot. It explicitly does not guarantee current-path identity through
manifest publication or prevent a same-UID replacement after the final
pre-manifest barrier. The current combined-v4 checker now holds the exact
163 inputs (root ZIP, 81 `.mod`, 81 dependency ZIP). Its combined input-set
SHA-256 is
`b7eca5385fd0cf811d0eb7e8a00fe467bf64f8c10fa1ab998521f00510b0b8b2`,
and module graph/frontier SHA-256 is
`a27185f3136ee694ba5e5e4d89d4eb985055b5c1d0599e826842169625d8c2e6`.
It independently records 100 module nodes, 247 edges, and
`fixedPointReached=false` with an exact 18-tuple frontier; all 18 entries are
retained version-specific vertices with `selectedByGraphAlgorithm=false`.
The focused 17/17 suite includes deeply rebound Wave5 H1, order, and selector
mutations. The
[Wave6 identity/acquisition decision v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave6-v1.json)
and
[reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave6-v1.md)
then resolve all 18 conflict-free H1 pairs from 18 parent declarations, 18
module-ZIP witnesses, and 25 `go.mod` witnesses. All selectors remain false and
the exact lexical 36-request `.mod`-then-`.zip` contract has SHA-256
`d1ea9ec1fab702b1bf405f13e1d7aaeb9a5354ff7f98a0d916870def124372a1`.
The decision accounts separately for 400 graph-lineage archive opens and 164
identity-witness opens, 564 total. Its 10/10 candidate and 12/12 decision suites
pass without acquisition at that checkpoint. The separate
[Wave6 one-use acquisition permit](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave6-execution-permit-v1.json)
was later consumed exactly once. Acquisition attempt
`5e0828c2e5dc1ce7ef2a06dd235d5076` retained all 36 resources
(18 `.mod`, 18 ZIP; 36,115,415 bytes) without extraction, loading, execution,
or compilation. The separate
[Wave6 retained-snapshot readback](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave6-readback-v1.json)
independently verified those retained bytes twice before its
[manifest](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave6-readback-manifest-v1.json)
was written last. Readback attempt
`7fc50276e880013e1ace73920397ba3f` produced receipt raw SHA-256
`6234799bbfbc608bdb5938adb36eaeaa85b5fb111b927873e825ed63947349e7`
and manifest raw SHA-256
`fe98535d35f7059a18e31d73a2e50fefefe92952bc4eece49623decea2068227`.
The separate read-only combined-v5 checker now reconstructs the exact 199 held
inputs (root ZIP, 99 `.mod`, 99 dependency ZIP) twice. Its input-set SHA-256 is
`06acb9e5395898abb1827761436b8c4b5d983d87d242eaf20622e352d0180c63`,
graph SHA-256 is
`4b424c41fbc8fa09c5bc9f91a880f14309cb409785991cfb872bb2475d94e8fe`,
and it derives `fixedPointReached=false` with an exact 15-tuple Wave7 frontier
whose canonical SHA-256 is
`1c226bfc244970e071ad2bf09d6e356cd9d42e7b542cd0cf1582fc2fdc4d9b8a`.
Its focused suite passes 25/25. The trusted pinned normal path records zero
file writes and explicitly does not claim an OS syscall sandbox. The separate
[Wave7 identity/acquisition decision v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave7-v1.json)
and
[reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave7-v1.md)
now resolve all 15 conflict-free H1 pairs from 18 parent declarations, 41
`go.mod` witnesses, and 20 module-ZIP witnesses. Every selector remains false.
The exact 30-request contract has canonical SHA-256
`8fbabe69d049992e28c687852686ae0ad28adce690443d61e335c903b87d0f48`;
decision content SHA-256 is
`dc771927a4cf8b6a8713f42c0716e98f242fdf7c277cddf0dadfe666bb02614f`,
and raw SHA-256 is
`4214aa1b0eb624ca17d3579e74be0cbb8d897027689e8dd1340d073601e28022`.
The optimized suite passes 13/13 in 358.677 seconds with one full
reconstruction, and an independent GPT-5.6 Sol static re-audit reports no
P0-P3 finding. Identity is acquisition-ready, but the decision grants no
acquisition. The separate
[Wave7 one-use acquisition permit](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave7-execution-permit-v1.json)
and
[reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave7-execution-permit-v1.md)
were prepared at `status=authorized_not_consumed`. Permit raw SHA-256 is
`1d15cb97e1ac04b4a99258ed876a0b84f71dcb9cc588f9bce5c9aaa1ba0b7a60`;
content SHA-256 is
`62339ae44907c1c28174fa55b0e5f99c95a20e10181148d30d8702288f8d940a`.
The checker passes 13/13 and the offline fake-I/O runner suite passes 36/36.
Independent GPT-5.6 Sol re-audit reports no P0-P3 finding after four
claim/teardown uncertainty findings were corrected. Acquisition attempt
`c15f4504ae880326144eca93dc91e37b` then retained all 30 resources
(15 `.mod`, 15 ZIP; 32,352,251 bytes) without extraction, loading, execution,
or compilation. Its receipt and manifest raw SHA-256 values are
`bd7f2db9500c8f8c0dc67737804d1a0ab62f722f1dacfc4b92fad48414b8a778`
and
`0af9c0adaaa5fb2bc71fed14f457be76b014fcc234ca0805a63d0bc31da9a559`.
The separate
[Wave7 readback permit](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave7-readback-execution-permit-v1.json)
binds an exact 48-file frozen snapshot. Its checker and recorder suites pass
16/16 and 45/45, and independent GPT-5.6 Sol audit reports no P0-P3 finding.
Offline readback attempt `1839537589935de087068a5a7d5c7e14` verified all 30
resources twice, completed three retained-FD pre-manifest barriers, and wrote
its
[manifest](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave7-readback-manifest-v1.json)
last. The
[receipt](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave7-readback-v1.json)
and manifest raw SHA-256 values are
`2153ef62af2dabf89467e481a35c2f50467fca37d422e70d549b9fc6d3377ba3`
and
`cb1e22055ccfde532f85842d7fd485f5b661ad4ae152f34f6247affc621a1482`.
Completion applies to the retained snapshot. Combined-v6 then holds all 229
exact source inputs (root ZIP, 114 `.mod`, 114 dependency ZIP), 45 terminal
controls, and one auxiliary Wave7 evidence file. It reconstructs the graph
twice and derives `fixedPointReached=false` with an exact 14-tuple Wave8
frontier. The combined input-set SHA-256 is
`f7ad0b43d571da61edd4941f8e504d54d014b01f3395aeca8d0d10b9b3c22349`;
the graph SHA-256 is
`3648bdf037e316e69e155615edd5748c2bb653238579216ddd8b8dce4beb9f09`;
the frontier canonical SHA-256 is
`d3c3788d6a1144bf04ea2c68e6aa4b9fdd17859bc625e2c2c51019bb3c61ff92`;
and candidate content SHA-256 is
`b33ef7a10de32dc99cea1dbbbcab1dac3a549eb466ef80b0229d2a0381ab9052`.
The final focused suite passes 25/25 in 514.493 seconds, and independent
GPT-5.6 Sol audit reports no P0-P3 finding. Its trusted pinned path records 230
direct plus 600 inherited archive opens, ten total full-source
reconstructions, and zero extraction/load/execution/compile/network/file-write
operations. The separate
[Wave8 identity/acquisition decision v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave8-v1.json)
and
[reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave8-v1.md)
then resolve all 14 exact version-specific tuples from 14 parent declarations,
93 `.mod` H1 witnesses, and 15 module-ZIP H1 witnesses. No tuple is blocked or
conflicting. The compact identity SHA-256 is
`c6aa1a974ad09f11927c103c7f2b63df0835d09b41d0dac9f6349d46d377a388`;
the canonical 28-request contract SHA-256 is
`b0f0f887864ddc4cf3ab15319a9e89dbea8c84087fa3d0e374a0332240336ddc`;
the decision content and raw SHA-256 values are
`1e1d62f03fe3137a88aa9413be8310bf7260f65a4825a09baab9a848ce6969da`
and
`45236a2ea42a4a3af59e60d27ed2f09cd5d191e34a6db992a9d81cb49316297e`.
The focused suite passes 18/18 in 512.113 seconds, and independent GPT-5.6 Sol
audit reports no P0-P3 finding. All decision selectors and acquisition
authorities are false. The separate
[Wave8 one-use acquisition permit v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave8-execution-permit-v1.json)
and
[reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave8-execution-permit-v1.md)
were prepared at `status=authorized_not_consumed` and then consumed exactly
once. The permit binds exactly 14 tuples and 28 ordered resources, resource
canonical SHA-256
`ee32b0512643b0e767f5b1e96625352fc47ea6ae7aea5d7366adfe98f4db8136`,
content SHA-256
`527a4558d069b31f92256926ea90e05c8353a33f65128b131d1c960614df925b`,
and raw SHA-256
`8595241898ebc14d563f5b03c3a4b46afdd995207bc1597d86c861e5c37bcb4c`.
The checker passes 15/15 and the network-free mock/local runner suite passes
44/44; final independent GPT-5.6 Sol re-audit reports no P0-P3 finding. The
acquisition attempt `6d8ea4473126c853b439c56a895f9c28` retained all 28
resources: 1,730 `.mod` bytes and 35,195,229 ZIP bytes, 35,196,959 bytes
total, across 4,907 ZIP entries and 144,867,307 uncompressed ZIP bytes. The
accepted-resource hash-set SHA-256 is
`7642f0b4dea8fee8eb92f573a3a4d948aa46a8736be70857097ce3b83af2eb38`;
the acquisition receipt and manifest raw SHA-256 values are
`77ca07dadeddd5578b08c1aab7b746b50f6d2e4f0ee83d0a73baa3cc4cb6ec68`
and
`5c440c55c3534c0d8b537fbbc0843b4e053f5e0c7397a568638dd043619abebe`.
The separate
[readback permit](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave8-readback-execution-permit-v1.json),
[reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave8-readback-execution-permit-v1.md),
[receipt](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave8-readback-v1.json),
and
[manifest](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave8-readback-manifest-v1.json)
record readback attempt `8618087527c005b5d19c8f902ec33557`. The 16/16 permit
and 45/45 recorder suites pass. The recorder independently verified the exact
46-file frozen snapshot twice, completed all three retained-FD publication
barriers, and wrote the manifest last. Readback claim, receipt, and manifest
raw SHA-256 values are
`aa696de4edaa8aad7e8a256dd0900680b42e3c0b6d2f877623461f6fe2bf5f6a`,
`b61738fe4ffae1b4aec7ee7fd8f7a186962cbbebf8911afd7d1fd0e94f0a5fce`,
and
`79f844b647915661b0b36fd5fa333591327ad934d6589c0fc98c912e7660d62f`.
Combined-v7 then holds all 257 exact source inputs (root ZIP, 128 `.mod`, 128
dependency ZIP), 52 terminal controls, the acquisition claim, evidence, and
readback claim, plus six direct tool inputs. It reconstructs the graph twice
and derives `fixedPointReached=false` with an exact ten-tuple Wave9 frontier.
The input-set, graph, frontier, and candidate content SHA-256 values are
`d389c84ae3b6d2d3d7dbb38d7003711972a75db3a558b9d6e0d79856249ef528`,
`c7889fbf06a01e08ba75150b85bb2cb2860ea71ce205cead432cf0a37e0d89b9`,
`03058e3aea23aca0c6208dd0023361f90421d394272f212d80bf61d587baff4e`,
and
`c71188f8d648a0f020a164002644f825e018f4c01b56d90e57011e05cc2e5202`.
The checker raw and normalized SHA-256 values are
`7264d85e1948bc8f86e8238192663706e7bf7472153d37fe812bd118620e99c7`
and
`cf4fd9d25efe04c2ecb3eea882bb24d6c40b02f2f258c4ab01d824d1373d1c02`.
Its trusted read-only path records 258 direct plus 830 inherited archive
opens, twelve total full-source reconstructions, and zero extraction,
load/execution, compile, subprocess, network, or file-write operations. The
strengthened focused suite passes 28/28 in 716.223 seconds, and the final
independent GPT-5.6 Sol re-audit reports no P0-P3 finding. Combined-v7
live-checks the seven Wave8 terminal files and exact final/accepted inventories
before and after reconstruction; the 46-file readback set is described only as
a historical descriptor-set binding, not as continuous current-path identity
after the last barrier.
The separate read-only
[Wave9 identity/acquisition decision](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave9-v1.json)
then reopens and reads all 257 inputs twice and reproduces the identity scan
twice. All ten exact frontier tuples are identity-complete, with 11 parent
declarations, 73 `go.mod` H1 witnesses, 11 module-ZIP H1 witnesses, zero
blocked/conflicting identity, compact identity SHA-256
`db31bdd4d1ae0c97ba88094502f7c0dc5e0f554e72c5f68503d917005f762753`,
and exact 20-request SHA-256
`e3922164eda6657d447f1b75ff49268265338efe35440dad39a237d1ddf643bc`.
The decision raw/content SHA-256 values are
`21ca43d44a67aec62b65a86fa44c43726eaa81fa277e07550f105e8c3b33bca8`
and
`340966e22b9759e2c1abd106e0cd9d9e9afa47b89ae3bb3929bfa6302dda18ae`.
The disk checker passes, and the focused suite passes 19/19 in 890.601
seconds. The clean namespace result is explicitly point-in-time only; every
selector and acquisition authority remains false.
The separate
[Wave9 one-use acquisition permit](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave9-execution-permit-v1.json)
and [reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave9-execution-permit-v1.md)
now bind exactly ten tuples and twenty ordered public-proxy resources. The
normalized resource projection SHA-256 is
`8758566447b9300880837d7316cf6fac319f50ec90549cb41aa36600ef2171f9`;
the permit raw/content SHA-256 values are
`026c270af575655245042998cdfae15478ac1630d5f7545ed33f66822c9c2ff5`
and
`14ac147494887a6019d8e5f66a1af2f8d9e27872a1b6560122e3bca2ff557a43`.
The disk checker passes, as do 16/16 checker tests and 44/44 injected,
network-free runner tests. The permit was consumed exactly once. Acquisition
attempt `df64a4816a083806020580efe953b9a7` retained all twenty resources
(ten `.mod`, ten ZIP; 16,285,940 bytes) without extraction, source
loading/execution, or compilation. Its claim, receipt, and manifest raw
SHA-256 values are
`84957554fe937841165f38a2418613e4e740082bea4f55538b21324dfe6d45f4`,
`55a989da9058e57fb44432e29299a3e6025f78b90e1bd011d5eb8e2141aee33c`,
and
`3acb2c48c4ba1dbc701896188f166026133e1860c4abfe58078e145574ba6514`.
The separate
[Wave9 readback permit](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave9-readback-execution-permit-v1.json),
[reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave9-readback-execution-permit-v1.md),
[receipt](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave9-readback-v1.json),
and
[manifest](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave9-readback-manifest-v1.json)
bind the exact 38-file retained snapshot. The readback permit raw/content
SHA-256 values are
`e493bfb7befa21cba3380a0c3b7147375eaa18688c1dbed78cd2e22f3c05b3eb`
and
`3c4d68ff4f5d7c7d456eeafcc495e17b3662420f75a7023c3fe8a78a84de349c`.
Its 16/16 checker and 45/45 recorder suites pass, and two independent
GPT-5.6 Sol pre-execution audits found no P0-P3 issue. Offline readback attempt
`2d61a0483984e9a2f77665dd3c624cb2` verified all twenty resources twice,
completed all three retained-FD publication barriers, and wrote the manifest
last. The readback claim, receipt, and manifest raw SHA-256 values are
`af0dab21e05292511bb105545750a61048f9d4b23e7ec7b9e7e1de5f1e7e41a7`,
`0e1816a43e2b7d8210dd90fb7349ea63637abbe830da0badc81105a03f0e439f`,
and
`7cd427780a29dc85b6ae59188c7ee2601939dbdca0393362824a2509f5878b7e`.
An independent byte readback revalidated canonical JSON, content bindings,
cross-file raw hashes, exact counts, and zero-network/zero-authentication
counters. Completion applies to the retained snapshot at the final
pre-manifest barrier; it does not claim continuous current-path identity.
Combined-v8 now holds all 277 exact source inputs (root ZIP, 138 `.mod`, 138
dependency ZIP), 59 terminal controls, three Wave9 auxiliaries, and seven
direct tool inputs. It reconstructs the graph twice and derives
`fixedPointReached=false` with an exact eleven-tuple Wave10 frontier. The
input-set, graph, frontier, and candidate content SHA-256 values are
`030743c3959a6e7466385e9f89255fcb03d65576676a1e5cd7e5e2929e9f6339`,
`721d045a10cdf015e865a84db7026115ac63462217dbb5349504fed9f1bae7b7`,
`780501bca37fbeb953590004ca7e5aad7f206083f749b920e2a9842b63675f82`,
and
`f9f683d3afbe65a77626577428c0f9ce94219e39529d0c5811b49172c51e3b37`.
The checker raw and normalized SHA-256 values are
`798a055a9a4c3957c0edd75ecbad35f0cfa9f17bf39e63cd262876dcb6103e32`
and
`cfd83cdd00b6daee857cbff915ec48fd78390bbf06098ccab963a54e8748ba4b`.
It records 278 direct plus 1,088 inherited archive opens, fourteen total
full-source reconstructions, four exact pinned legacy-build compatibility
applications, and zero extraction, load/execution, compile, subprocess,
network, or file-write operations. V7 test bytes are explicitly historical
metadata rather than a live-held V8 tool input. The checker exits zero; the
full suite passes 29/29 in 969.215 seconds, and the final audit assertions pass
AST, 23/23 fast checks, and direct test 29. Final independent GPT-5.6 Sol audit
reports no P0-P3 finding.
The separately bound read-only Wave10 identity/acquisition decision is now
complete. It reopened the 277 exact source bindings, scanned 139 archives twice,
and resolved all eleven frontier identities: one graph-selected
`golang.org/x/xerrors` tuple plus ten non-selected version vertices. The two
scans reproduced 15 parent declarations, 107 `go.mod` H1 witnesses, and 15
module-ZIP H1 witnesses with eleven complete pairs and zero blocked or
conflicting identities. The exact 22-request set is bound at SHA-256
`cf6a97651565b55bb714a713e66e6a452f7132973ce21ced254bd0d728d12a89`;
the decision content and raw SHA-256 values are
`d0bfdd7247584e116656ca4efd560e893814241e0b17be96ba0cb55151b9150e`
and
`d1c23056487d88b92f1f2fd105d219abd029079590b379f7a671317b4158b6eb`.
The checker raw/normalized, tests raw, and reader raw SHA-256 values are
`e7c3aabac84dd14f33b77b777730eb95bcd4160b6886645698ccad9060defebc`,
`165a4ce6fb946866811846e2fc6a999be646f2e1d2a52bf66dd1450a367510da`,
`9336e06a6fde88ad382a0cd54176d3cf3807c3a51c215769659c4fb7e199b9a4`,
and
`700a0ae5d4067806cfbad2f8efd6439f272c1d02e5311da7e60d153cf2d85caa`.
It records fourteen total source reconstructions, 1,366 graph archive opens,
278 identity-witness archive opens, and 1,644 overall archive opens, with zero
authentication, network, extraction, source load/compile/execution, subprocess,
or file-write operations.
The disk checker exits zero and the focused suite passes 21/21 in 922.040
seconds. The separate one-use 22-resource Wave10 source-acquisition permit
package passed its checker and offline runner gates. Its permit JSON
raw/content SHA-256 values are
`841d30e43ce839662baab07d0f47f39cfe9c52d2b4d3757e2066a128452a6c93`
and
`33edc56dcb497f9fb94d54ef1d0c07f3ff18fe04cdbaca1ff0bffd81169eabfa`;
the checker, checker-test, runner, runner-test, and reader raw SHA-256 values
are
`fe39b88609bbca78461bf7db416cb311143371d68ebab176703bbc2c7a81eaec`,
`fe4d7372b82f9fd4e50529ab4a17076ed3787ec2f663512476b846de6f6e0c3c`,
`5395afdaff0d928e786d3e7fb50cea46bf83dd78e57865196813ca1d080546b3`,
`5aa7f30a6debda432577227e86f0b933b7d668732141d78d3cf9c0a150bad747`,
and
`25b5a7cee6b0c9b4ddd633d39ed000b03a85a795b74770ecf0b28e08c4884074`.
The checker and offline runner suites pass 16/16 and 44/44, and two independent
GPT-5.6 Sol audits report no P0-P3 finding. Acquisition attempt
`ffe70ee4562fcfc9e0fd6c9c4e136bd9` consumed that permit exactly once and
retained all 22 resources (11 `.mod`, 11 ZIP; 27,773,526 bytes), including
4,872 ZIP entries and 108,563,141 uncompressed bytes, without extraction,
source load/execution, or compilation. The acquisition claim, evidence,
receipt, and manifest raw SHA-256 values are
`5260f5d7e7473013871573717848a3e8eae868a47ab2bfe538340d681ec4a6de`,
`0b3700d12d11d334e91c95dfd561d43aa8827294ab9caee0b21258ded48cf9de`,
`49f4aab3f71e52631aa48ac34ba7ee2a1ef3613814b06e87095ef75c3adaa1a1`,
and
`3f1f178d3bd48b3b8d8792ae1be57716aacd7cba16f526afccfca3d4b998643c`.

The separate Wave10 readback permit raw/content SHA-256 values are
`361fa5cc18fa167f9ebfd880a4cc1d7a0f6512a99a68712ebd85cc3de0dcbaee`
and
`7dd8a8cb7187f6d199da6c9b13173b6669a92ae3690dca2f987349b50cc13c8c`;
its reader, checker, checker-test, recorder, and recorder-test raw SHA-256
values are
`c2da54eeba369acef1a755bca756c4cb5aae99f5fad69a561209633f66e24a6a`,
`b118273738520e78c669a7f07a4639a94147134af6c9ffaffa4ac441e9e7cfd0`,
`70aab8c0489215dd5f7da6634be3b57e19f2a5019df609b5fc628c1264f352c2`,
`bbc40c85a77b94f3615f803dcb672eba825ba0ee4ce7b4d4159943d04c7cdb24`,
and
`a1abe031ad2c06c5f8428702356c06ef39556b8157e02403842bae4adac2ecf9`.
The checker and recorder suites pass 17/17 and 49/49, and two independent
GPT-5.6 Sol exact-byte audits report no P0-P3 finding. Offline readback attempt
`e74e030f7f5ef33589d7895e1b28b3b1` verified the retained resources twice,
completed all three pre-manifest retained-FD barriers, and wrote the manifest
last. The readback claim, receipt, and manifest are mode `0600` with raw
SHA-256 values
`5eaed52abe8fc9c1de5ceba356d37057b470ada00048b3f7cd5048003f82ef0f`,
`056b0b2d9bbdc19702f8400451ff5329ca7eaceff4613bba1dbfd34e93f21224`,
and
`66eb30a0d1f943b0718ee2b14a3cdaee6fae5127e796569c16a55f14ade41762`.
An independent raw-byte readback revalidated all three canonical JSON/content
bindings, their cross-pins, and all 22 accepted resource hashes and byte
counts. Both one-use actions are consumed and cannot be retried. Completion
applies to the retained snapshot at the last pre-manifest barrier; it does not
claim continuous current-path identity through manifest publication.
Runtime/product network, extraction, source load/execution/compile, Git,
device operation, release/product publication, and deployment remain closed.
Repository authentication, account login, owner proof, credentials, keys,
signatures, tokens, passwords, and user action are outside this workflow and
were neither requested nor required.

The read-only combined-v9 successor is now complete. It held the exact 299
source inputs (root ZIP, 149 `.mod`, 149 dependency ZIP), 66 terminal controls,
all three Wave10 acquisition/evidence/readback auxiliaries, and eight direct
tool inputs. It reconstructed the graph twice and derived
`fixedPointReached=false` with an exact nine-tuple Wave11 frontier. The combined
input-set, graph, frontier, candidate-content, and compact-source-binding
SHA-256 values are
`5a08d28573b68ddd031eff34a8b6afad8f7cd9e01966f4516c22a410bbb51b71`,
`4367fc6c4c5efb69f948d8e040c2cfa496345102631719692d31feabb794a6b5`,
`171af951e3a67405b62ddceface1341bb6f64b08f370d3d216ede541bd011f06`,
`9c9e995f853a8dbbc07d55d41ce1c5660cb616d879b3565803e13b6aaf4532ba`,
and
`2455ab16e4c1dd6a68127c38f25d49275d9ef955d4d12ad711d644f0d745839f`.
The checker raw/normalized and tests raw SHA-256 values are
`c0f098cf0a047c4d1aca03f5b7f16f327306b56ed8e656d67afe32503eb117da`,
`b4cdbfd385e0606fa2ca37017983bd80b6856dd69dfafb46df6579e76c618684`,
and
`fca6a0ca437356185d287816bcfaf5e110794207b3413addf95e9eb24038c217`.
The checker records sixteen total source reconstructions, 300 direct plus 1,366
inherited archive opens, 32 graph-algorithm invocations, eight hardened-module
checks, and eight provider loads. Extraction, source loading/execution,
compilation, subprocess, product/runtime network, and file-write counters all
remain zero. The exact Wave11 frontier is `golang.org/x/crypto` at
`v0.0.0-20190308221718-c2843e01d9a2`; `golang.org/x/mod` at `v0.27.0`;
`golang.org/x/net` at `v0.43.0`; `golang.org/x/sync` at `v0.16.0`;
`golang.org/x/sys` at `v0.0.0-20190215142949-d0b11bdaac8a`,
`v0.0.0-20201119102817-f84b799fce68`, and `v0.35.0`;
`golang.org/x/telemetry` at
`v0.0.0-20250807160809-1a19826ec488`; and `golang.org/x/text` at `v0.3.0`.
Every row has `selectedByGraphAlgorithm=false`,
`acquisitionAuthorized=false`, and `requiresSeparateWaveDecision=true`. The
checker exits zero, and the exact final suite passes 21/21 in 1,187.320 seconds.
Two independent GPT-5.6 Sol exact-byte audits report no P0-P3 finding. At that
checkpoint, the next gate was a separately versioned, read-only Wave11
identity/acquisition decision; it granted no acquisition, extraction,
compilation, network, authentication, Git-write, device, or user-action
authority.

The separate read-only
[Wave11 identity/acquisition decision v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave11-v1.json)
and
[reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave11-v1.md)
are now complete. The checker re-executed the exact pinned combined-v9
candidate, held all 299 source inputs, and reproduced the identity scan twice.
All nine exact frontier identities are complete and conflict-free, with zero
graph-selected rows, 12 parent declarations, 68 `go.mod` H1 witnesses, 13
module-ZIP H1 witnesses, zero blocked tuples, and zero conflicts. The compact
identity and full-witness SHA-256 values are
`8e6e8473c3938f40dbbffb090c26a73bf965c247df33c8ead5c04341b74adbc4`
and
`ea353c9595bbe020bd908347b9576bc7e8c820047735e768cc2d7ac37dc2713e`.
The exact 18-request structural contract has SHA-256
`bbde21b5f7a523bb6cddf78fbbbfdce46f8bcf61d60ebcec72a80d52dda50ba8`;
every request keeps authentication, network, and acquisition authority false.
The decision raw/content SHA-256 values are
`e1f3a82025c711694cb6551a53407aa1164493396a65f383eacf95dbf90b881a`
and
`1bdb93f69c6a44d977a701dab83ea847a5ff473bb18e41bf093ed45bc4c1647f`.
The checker raw/normalized, tests raw, reader raw, and normalized full-AST
SHA-256 values are
`d73fa27a15a2936e21bdc1dfb12ad83c0f7b4b2399a67c637e84626170698f16`,
`5b4cf2878c2f659815876965bd8ff5aefe7853e01180103854455ee06faabe4f`,
`b124eb04e26faa66ab9a194ae945583e8eedf3f4788fa23122f50e86b46a35cc`,
`a153ab49d1d6e2c0f99564fd49704b9d4000ba686b076e1e19ce7a68413c8c74`,
and
`daf9ed7b36710a442a86b5a12e7d98ca64446d106d483f1437f8a23d5215af8f`.
The exact final suite passes 25/25 in 1,157.225 seconds, and three independent
GPT-5.6 Sol final-byte audits report no P0-P3 finding. The separately bound
Wave11 acquisition checker/runner suites then passed 17/17 and 46/46.
Acquisition attempt `ac18b8fda0a80a132510efd5dd17d5b7` consumed its permit
once and retained all 18 exact resources (9 `.mod`, 9 ZIP; 16,363,894 bytes),
including 3,329 ZIP entries and 64,428,507 uncompressed bytes, without
extraction, source load/execution, or compilation. The acquisition claim,
evidence, receipt, and manifest raw SHA-256 values are
`a41663bd827b8f07e0e04e887b21a7306c0ba286396e43d854ea3f2369a3e985`,
`c4194219b35723fb61ee41fca23a10ffe5f2c18f01f82fb70856a404019fb797`,
`0c35d330476362fdaba23192229d8aa0fa096c0f47fddb39955f8976db6115a8`,
and
`ac247bed91f7cbe50c90d8a640b885ca1adaa2888fa8447f6ea0baeb4a046a15`.

The separately bound readback checker/recorder suites pass 17/17 and 50/50,
and three final GPT-5.6 Sol audits report no P0-P3 finding. Offline readback
attempt `9b4dac65f66ce9e5d53dcd8edaf4d1d4` verified the exact 36-file
retained snapshot twice, completed all three retained-FD pre-manifest barriers,
and wrote the manifest last. Its claim, receipt, and manifest raw SHA-256
values are
`752c0fdc006688a4c22dc26f54be1c9bb4498e9a94f196217aebfaff8e61dc13`,
`f89904b359aed770e89ed8de25b775d6b920d7eef3d32bdc464a486a862cc5ca`,
and
`0bda6e5da9609ddd375e20a6692a4cec46aaf930acee4861c5168efde1f18c0e`.
An independent raw-byte process revalidated all canonical JSON/content
bindings, cross-pins, and 18 resource hashes and byte counts. Both one-use
actions are consumed and cannot be retried.

The separately versioned read-only
[combined-v10 checker](../script/check_p2p_nat_g2_pion_combined_fixed_point_v10.py)
is now complete. It held 317 exact source inputs (root ZIP, 158 `.mod`, 158
dependency ZIP), 73 terminal controls, three auxiliaries, nine direct tool
inputs, and eleven transitive tool paths. Two complete reconstructions covered
159 archives, 59,494 entries, and 1,098,221,637 uncompressed bytes. The input,
compact source-binding, graph, frontier, and candidate-content SHA-256 values
are
`f946c625334ac8cf42d42c9f45f0f051eb7f89fb9ecf5dfc576114b1cba990be`,
`067808934056712884a75ea669d61189bb5d5d722d2a961c8b8c5d25345bb75c`,
`77813f467c7452290f35c4ecaa6a1041a0988d563ea37660bb6cc902bb95cdc4`,
`8b84bd2fd9201d33f4424b9dd1018aee7f8470a87306c2ba23eba0c8b6d4ff05`,
and
`d7feddd3b291756c36359b013ea05aaa2f25cb83605daaeb493c0395ff9cc4f7`.
The ordered frontier is `golang.org/x/crypto@v0.41.0`,
`golang.org/x/term@v0.34.0`, `golang.org/x/text@v0.28.0`, and
`golang.org/x/tools@v0.35.0`. Every row remains non-selected and
non-authorizing, so `fixedPointReached=false` and the route is
`next_wave_required`.

The checker raw/normalized and current
[test](../script/test_p2p_nat_g2_pion_combined_fixed_point_v10.py) raw SHA-256
values are
`11d0c2743f92d59a8417870db279edeb6a1b6c0a1af9db577e5cec4c50350985`,
`ccb5430b1c41e5fcd39e00b7345ba285a427b1b25d48c299f81f1be8ca25f751`,
and
`ab00dbe4d70fbfc596ee6553e2d87f94f75370f07ff38b93d5c5fb5652bfac35`.
The pre-audit suite passed 23/23 in 1,438.484 seconds. Test-only follow-up
hardening now independently pins both checker hashes, reaches the exact
selector-type semantic branch for every selector-bearing projection, and
proves aggregate ceiling `limit - 1` rejection; the two changed focused
boundaries pass, and an independent GPT-5.6 Sol re-audit reports no P0-P3
finding. A full 24-test rerun remains pending. The verified candidate records
18 total source reconstructions, 318 direct plus 1,666 inherited archive opens,
36 graph algorithms, nine hardened checker modules, nine provider loads, and
zero extraction, load/execution, compile, subprocess, network, or write
operations.

The separately versioned read-only Wave12 identity/acquisition decision is
complete for its bounded scope. It re-executed the exact pinned combined-v10
candidate, reproduced the V10 content, input-set, source-binding, graph, and
frontier hashes, scanned the 159 held archives twice, and resolved all four
exact frontier identities with four parent declarations, four `go.mod` H1
witnesses, four module-ZIP H1 witnesses, zero blocked tuples, and zero
conflicts. It binds exactly eight ordered `.mod`-then-ZIP request shapes at
SHA-256
`6531872e99da0c94746cbdb53fe9f5302ebc71bc82bfde1705b5e2300b2a2ee5`.
The final suite passes 26/26 in 1,366.737 seconds. Checker raw/normalized,
tests raw, reader raw, and materialized-decision content/raw SHA-256 values are
`bb9d62377d676cc6de7678db6be8e64b6d65a088c4c508269fdd51f6f9ca9b53`,
`b8702241e4455fb49d7bcae13857d6d3c2a4cad181390ecea8009d229e3d9051`,
`196fcdaf9a20a60d1b29b628492d1c3f0164805adc5df05678921437e7243def`,
`31036c0f25364c5f316c30a4541a6a649a13cdcc9952ec9df9cf2c94a1de5398`,
`9da32d6de84064039bce0438d75fb0ae7b5c9a22faff6b956c0e443f923a09a9`,
and
`230d4329170a27fd27f8eef4c33337971441726837693526b732a4847a779c0a`.
The separate
[Wave12 one-use acquisition permit](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave12-execution-permit-v1.json)
and [reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave12-execution-permit-v1.md)
were materialized before execution at `status=authorized_not_consumed`,
`structurePreparationOnly=false`, and `executionReady=true`. The package binds
the exact four tuples and eight requests at resource-canonical SHA-256
`c8ca9bc4559bea59a5a52fbceaaf068fe82ab9211fa0a888d3918aaa2dec55a2`.
Permit raw/content SHA-256 values are
`ab96943fd74a110b42099826f3555517995e4b2e1ed7f7552cbb683fbe7330a5`
and
`06b436d850c8f1d89f2f7fbc95130c9d560ddb71dda50257537f0876a164af80`.
The package checker, checker tests, runner raw/normalized bytes, runner tests,
and reader raw SHA-256 values are
`b00ea74bf16e02d429ecf9130ac15ffba9b594a0ae105aa620cd2439cda9bcc1`,
`493c85a538d86f8c78a5b08c22395e4f0d084d8bdc74960028d5f8d08115ec36`,
`d954a733dafdb9296d79a5a1bb81d7801393dc8063fcee2a70e41bf85f6961c9`,
`985d611f46e62e89341ff250aeb66849a2fc1943ae8aa45a4f31b19397567e90`,
`0590055346f99746bcdd5aef6deeadc251295fae29336a644c5fadd48044c666`,
and
`fa09ad2834fb1a145ab606a4251769a5321d17d97e6bdfb4477dd500de7ad047`.
The package checker and fake/local runner suites pass 18/18 and 48/48.
Acquisition attempt `f977ddcf8fc391e5915048b930beccbd` then consumed the
permit exactly once and retained all 8 resources: 753 `.mod` bytes,
15,035,516 ZIP bytes, 15,036,269 accepted bytes, 2,547 ZIP entries, and
55,940,531 ZIP-uncompressed bytes. The accepted hash-set SHA-256 is
`38e9b110d8857fe1644a8fc80bb4a584da540981d43ee19b62e3e9e845422a2c`;
acquisition receipt and manifest raw SHA-256 values are
`59117c663f4eff44057e74690acffa506d71dd86b07d3f4f7aa86b96704edd43`
and
`f00f4ae58f5d193bf32d8ff77661037fa6f38114c55766abb1bbd25c29b5900b`.

The separate
[Wave12 offline readback permit](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave12-readback-execution-permit-v1.json)
and [reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave12-readback-execution-permit-v1.md)
bind the exact 26-file frozen snapshot at canonical SHA-256
`3d7365fd16905b8fb3c3d8682e8803c5487b120b3ba8f49b75d16eba2bc354fd`.
Permit raw/content SHA-256 values are
`67e98623c54b61182ada2e873f953da197a94e25c59a827fa4fd33d60df218a4`
and
`6d642dbd6e72e57f45bbb20b24132e07752029ba18244d09c400ea067b14bed3`;
its checker and fake/local recorder suites pass 17/17 and 50/50. Offline
readback attempt `32ab6b747a02382f85f48f65e0c388c5` independently
verified the snapshot twice, completed all three pre-manifest retained-FD
barriers, and wrote the manifest last. Readback receipt and manifest raw
SHA-256 values are
`74b14b3eb23c3544d96f59ae1c9860f98128bb7908a547e8c98d425ef6e6d456`
and
`20126430c1041a2fbcb54b15f5b0661ab9a330b87e332355c32c95c073709d13`.
Both one-use actions are consumed and cannot be retried. No user identity,
credential, ownership proof, authentication, or interaction was required.
Extraction, source loading/execution, compilation, product/runtime networking,
general socket use, device work, deployment, Git writes, and release
publication remain closed.

The read-only combined-v11 checker then held the exact 325-input retained set
and reconstructed it twice. Input-set, source-binding, candidate-content,
graph, and exact-frontier SHA-256 values are
`124995740eb0d95e83c77f078a334bd55ac491a14453098fa70da26cf52d6caa`,
`504b3ed2a6182db6464c93999c3bd073381ee181c7238ca62da5afd2ca87269f`,
`1976ed89f18f28b0b3440a693581f171bdd574bc615f2054bea2cba1cf85b837`,
`b4b0ec50d5538e80de93e89574249ca0d49b411443ebd2c78827928704b0a44d`,
and
`3528abe3579eb1d06ba01f66f56002a6e193fe1e25e233f03eab9b8ac3e4fc32`.
It derives `fixedPointReached=false`, `route=next_wave_required`, and four
exact non-selected Wave13 tuples: `golang.org/x/mod@v0.26.0`,
`golang.org/x/net@v0.42.0`, `golang.org/x/sys@v0.34.0`, and
`golang.org/x/telemetry@v0.0.0-20250710130107-8d8967aff50b`. Cumulative
accounting is twenty full reconstructions and 2,310 graph archive opens over
163 archives, 62,041 entries, and 1,154,162,168 uncompressed bytes. The full
suite passes 24/24 in 1,676.228 seconds, and three independent GPT-5.6 Sol
audits report no P0-P3 finding.

The verification-only Wave13 identity/acquisition decision then re-executed
the exact combined-v11 predecessor and scanned the 325 retained inputs twice.
It resolved all four H1 pairs with six parent declarations, six `go.mod` H1
witnesses, six module-ZIP H1 witnesses, 113 ZIP-contained `go.sum` entries,
zero blocked tuples, and zero conflicts. It binds the exact eight-request set
at SHA-256
`eae1bb0f8645a5d698bfe50fae505a1c7d6887c78c9dcc3b088939b97e0ffce1`;
decision content and raw-file SHA-256 values are
`3d08d589ed9121128717215fe0d9583b6f64e59fc033e1c5f50477f6e59d5b83`
and
`0092e8b0290b6bb60193e0d744f4f5af8fbf2f6d02f947997e683952caf7aa65`.
Its focused suite passes 27/27 in 1,648.766 seconds, including a pinned
`109 + 4 = 113` regression. The decision is structurally acquisition-ready
but grants no acquisition, network, authentication, write, source
load/execution/compile, Git, or user-action authority. The separate one-use
eight-resource Wave13 permit package is now materialized. It binds resource
canonical SHA-256
`cdb0c96d670feb69063b50709a342313501de575e4d8d692f943dffcab176f29`,
permit content SHA-256
`d3e7fb34e17a94cd2d89249e115e4ef15122a40f1df4ff8d6c977ed9dd6cfc07`,
and raw SHA-256
`b976f9bea30a20e34df25e9d90cfa9ee4617ce825b0d28f254b5bb512b6c29a1`.
Its checker and fake/local network-denied runner suites pass 18/18 and 48/48.
Three independent GPT-5.6 Sol final-byte audits report no P0-P3 finding.
Acquisition attempt `eb05816e0b897ea8c3ad8b7089668e91` consumed the permit
exactly once and retained all 8 resources: 411 `.mod` bytes, 5,097,127 ZIP
bytes, 5,097,538 accepted bytes, 1,647 ZIP entries, and 20,065,482
ZIP-uncompressed bytes. The accepted hash-set canonical SHA-256 is
`bcb43e80159d68f179c24e87f1f8d439bb1c387d713b9a3aec0ac932f9a6ee92`.
Acquisition receipt and manifest raw SHA-256 values are
`b85a242f11255a82a8422adfda8cfe86113bd47bd9920c69fafb69985895c514`
and
`6d33bb51108da1f8e010f23ff6abfdd5eb62b398db0fd048e2a50576b7cbfa12`.

The separate Wave13 offline readback permit binds the exact 27-file snapshot
at canonical SHA-256
`a99b35472a140330847b1ff7e746a83dc060707ea63af3ef22d165a4f2ced11d`.
Its raw/content SHA-256 values are
`f6e1ed89709cb2c15640c051a74ce1ab4e549c635ced30d6621489a7559225d5`
and
`db9b97fce13b46fa0ebb5c774054b88237c8bab7b4ff729d5fcbe7e8d82f5481`;
the checker and recorder suites pass 17/17 and 50/50 after exact Wave12-drift
mutation hardening. Offline readback attempt
`8b5f92c9d90f825f5f3b46df0d006ef3` verified the snapshot twice, completed
all three pre-manifest retained-FD barriers, and wrote the manifest last.
Readback claim, receipt, and manifest raw SHA-256 values are
`11c1e04dfde8be7d7728f32912154870dc1e0305d0bbb61f1ff4167304bc5274`,
`eb5ac65c8e8dbe186d7f79d292642029f08d35241dd157a610351b5b5b7de62f`,
and
`cdb07a858e11e3c5709210794d84a793dd81d5b32ba3867b750f1e8a27369628`.
Both Wave13 one-use actions are consumed successes and cannot be retried. No
authentication, credential, network, Git, or user action was required.

The read-only combined-v12 checker then held the exact 333-input retained set
and reconstructed it twice. Input-set, source-binding, candidate-content,
graph, and exact-frontier SHA-256 values are
`656dcf1c1e94b09649041fa6d99b0db1d3997914dc40eba5e7ca840b35b9760d`,
`bf043a07c5fa6d26f28de9954b8f676e583f625ccf28ca5a39d6fe23c6678592`,
`176f5802b4bb56a6136f930a02ddd648774416945984af04bae4438de4e2bc17`,
`0ab3b47d6b4fc628a3bf83e648308591c84ddce8ad46ce8f8d6aca1797cf1e26`,
and
`a149da341952b398d71c9a9395cb18aac2c711bb8a8d72e1eb53ca710377df63`.
It derives `fixedPointReached=false`, `route=next_wave_required`, and four
exact non-selected Wave14 tuples: `golang.org/x/crypto@v0.40.0`,
`golang.org/x/term@v0.33.0`, `golang.org/x/text@v0.27.0`, and
`golang.org/x/tools@v0.34.0`. Cumulative accounting is 22 full
reconstructions and 2,644 graph archive opens over 167 archives, 63,688
entries, and 1,174,227,650 uncompressed bytes. The checker pins exact
Wave13 predecessor containers and acquisition/readback resource limits. Its
full normal-path suite passes 24/24 in 1,996.811 seconds.

The separate
[Wave14 identity/acquisition decision v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave14-v1.json)
and
[reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave14-v1.md)
now resolve all four exact H1 pairs from four parent declarations, four
`go.mod` H1 witnesses, and four module-ZIP H1 witnesses, with zero blocked or
conflicting identities. Decision raw/content SHA-256 values are
`14d6debddca620af7f628198f7a7ae2d9291adc35a6fffbe13873d3fd75dc28f`
and
`cb4201b1d0e6fd4ae2275cf5a58ceedd0ca14e33cb6af4269e798f1115f37450`;
the canonical eight-request SHA-256 is
`505587c90ec32b1dea879b1e034450de091874a2ff9db9993532f1b14d9dc3aa`.
The latest observed local full-suite run passes 27/27 in 2,030.976 seconds,
including canonical disk readback; that duration is execution observation,
not a package-attested receipt.

The separate Wave14 one-use acquisition permit then passed 18/18 checker and
48/48 fake/local network-denied runner tests. Its raw/content SHA-256 values
are
`867e1541606f67404f5066cfb6fe8f5265422024e4aec6e9c5e44db755b7fe49`
and
`60ac6693cc83c06efa1a913ed3a0cdbb7941efa4d58313e2a4919774efb79787`.
Acquisition attempt `7fef20e6c3931b698f32b2a71f8a596a` consumed the permit
exactly once, retained all eight resources without extraction, and recorded
accepted hash-set SHA-256
`23a5e8e4efaa6d0cf63549eaa686e5b9e365d38b832be5f5f14e0e8722a327ec`.
The separately sealed offline readback permit passed 17/17 checker and 50/50
recorder tests and bound the exact 27-file snapshot at canonical SHA-256
`905f7a4e90abbe1fb311385e001fac94a1dee32235b408a794e663eb049458ec`.
Readback attempt `177051373b1754fd638b5f57df2d6515` verified the snapshot
twice, completed all three retained-FD barriers, and published the manifest
last. Both Wave14 one-use actions are consumed successes and cannot be
retried.

The read-only combined-v13 checker then held the exact 341-input retained set
and reconstructed it twice. Input-set, source-binding, candidate-content,
graph, and exact-frontier SHA-256 values are
`285cfb3e8b4a73beffa551429058611a606b00ad447d75599c77fb18895a2f91`,
`fbd023d2ee5f372ef90d06d92e48c7dfa9828212e38bf942e1741aca322b9996`,
`e1f711b558642ad2167da48f25184cd4c3235314c67f06a60cfd14ceecea1988`,
`a35d9bd389a6fb9e04052eb411e4c9701a76ff0fd699e1c2d2a113d86439dfd5`,
and
`1d143e954c48cb48172cf61975868c3c76852f152d100a04745b16b02fa5e911`.
It derives `fixedPointReached=false`, `route=next_wave_required`, and five
exact non-selected Wave15 tuples: `golang.org/x/mod@v0.25.0`,
`golang.org/x/net@v0.41.0`, `golang.org/x/sync@v0.15.0`,
`golang.org/x/sys@v0.33.0`, and
`golang.org/x/telemetry@v0.0.0-20240521205824-bda55230c457`. Cumulative
accounting is 24 full reconstructions and 2,986 graph archive opens over 171
archives, 66,259 entries, and 1,230,182,064 uncompressed bytes. Checker
raw/normalized and tests raw SHA-256 values are
`0b0ea7d68ef5fc11b8c0defe56bf443c681a6952a27e2c9b6c41d9702241a80b`,
`73a778e53bdc1d15ffd34109ff02297e85eb6a91b52d1577acefe9bc1383e674`,
and
`dffb5e24cfd2ba4c561f5e8c6302c4502a75f917c1ac9d15216fd7f2ac045327`;
the full suite passes 24/24 in 2,360.584 seconds. The separate verification-
only Wave15 identity/acquisition decision is now complete at canonical content
SHA-256
`1d574152a913b067508260828f355a596fa82f5e8657c560229951f13e01b6c0`
and raw SHA-256
`73638ba5aaaad61d146e0b884e71de9609ccddf870cf81c2c01bb42c2bccee19`.
Its two retained-input scans reproduce seven parent declarations, seven
`go.mod` H1 witnesses, seven module-ZIP H1 witnesses, five complete identity
pairs, and zero blocked or conflicting pairs. It binds the exact ten-request
set at SHA-256
`106a3f88983749e5272783fc7ce1293473a8dacf2e86ef7effc374707fec0d04`
without authorizing acquisition. Extraction, acquisition, source loading/execution,
compilation, runtime sockets/product networking, Git writes, authentication,
and user action remain closed or unrequired.

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
  aligned `main` and `origin/main` at the historical starting checkpoint
  `dee5d87791ceaddb094235fbf33f7997580ddb1e`. Beyond the completed socket-free
  G1a foundations, the current worktree contains G1b-A Android normal-graph
  activation-controller ownership, injected real-fixture manager/ViewModel E2E,
  the macOS IPv4-loopback-only accepted-raw primitive, the G2 Pion v4.3.0
  official-source preflight, and the restricted-fork lineage through consumed
  Wave19 acquisition/readback and the verified read-only Combined V18
  fixed-point candidate plus its non-authorizing closure-review decision. The
  normal Android controller intentionally starts empty, the macOS primitive is
  not `CompanionAppModel`-wired, and neither path has executed a live socket or
  device. The worktree is intentionally dirty for this bounded current slice.
  At this snapshot the bounded G2 changes are
  unstaged; refresh `git status --short` because live Git output remains
  authoritative.
- Current G2 terminal state: Wave19 acquisition attempt
  `f10c20196d994afe3a8eba830eb42614` retained the exact four resources and
  11,453,955 bytes, and independent readback attempt
  `060a3d9bcd02113ef12c2c75a1e11d70` verified the exact 23-file retained
  snapshot twice, completed all three pre-manifest barriers, and published its
  manifest last. Both one-use actions are consumed successes and cannot be
  retried. No extraction, source loading/execution, compilation, readback
  network request, external authentication, or user action occurred. Combined
  V18 subsequently reconstructed the exact 369-source retained set twice and
  derived an empty-frontier fixed-point candidate with zero unmapped or
  unresolved imports. Its separate read-only closure review now accepts only
  `dependencyFixedPointReached=true`; all 19 findings and every later closure
  or selection state remain open. The fixed-point source/license preparation
  decision and zero-write adapter are complete, but both independent Sol
  passes returned `passComplete=false`, so completion remains 0/2. The next
  boundary is bounded file-by-file semantic, special-source,
  broad-license/`PATENTS`, SPDX/provenance/binary, and native-profile
  completion work.
  Readback completion applies only to the retained snapshot; continuous
  current-path identity through manifest publication and same-UID replacement
  prevention after the final barrier are not claimed.
  Historical Wave11
  acquisition attempt
  `ac18b8fda0a80a132510efd5dd17d5b7` retained all 18 exact resources, and
  offline readback attempt `9b4dac65f66ce9e5d53dcd8edaf4d1d4`
  independently verified the exact 36-file retained snapshot twice before
  manifest-last publication. Both one-use actions are consumed and cannot be
  retried. Combined-v10 subsequently reconstructed all 317 exact source inputs
  twice and derived `fixedPointReached=false` with four exact Wave12 frontier
  tuples. Wave12 identity/acquisition decision v1 is complete for its read-only
  bounded scope: all four exact H1 pairs are complete and zero are blocked or
  conflicting. That decision remains non-authorizing, while the separately
  materialized exact-eight permit passes 18/18 checker plus 48/48
  network-denied runner tests. Acquisition attempt
  `f977ddcf8fc391e5915048b930beccbd` consumed it exactly once and retained all
  8 resources. Offline readback attempt
  `32ab6b747a02382f85f48f65e0c388c5` then verified the exact 26-file
  snapshot twice before manifest-last publication. Both one-use actions are
  consumed and cannot be retried. Combined-v11 reconstructed the exact
  325-input retained set twice, and Wave13 decision v1 resolved all four
  resulting H1 pairs with zero blocked/conflicting tuples. Its decision
  content SHA-256 is
  `3d08d589ed9121128717215fe0d9583b6f64e59fc033e1c5f50477f6e59d5b83`,
  and its focused suite passes 27/27 in 1,648.766 seconds. The separate
  exact-eight Wave13 permit package is materialized at raw SHA-256
  `b976f9bea30a20e34df25e9d90cfa9ee4617ce825b0d28f254b5bb512b6c29a1`
  and passes 18/18 checker plus 48/48 fake/local network-denied runner tests.
  Acquisition attempt `eb05816e0b897ea8c3ad8b7089668e91` retained all eight
  resources, and offline readback attempt
  `8b5f92c9d90f825f5f3b46df0d006ef3` verified the exact 27-file snapshot
  twice before manifest-last publication. Both one-use actions are consumed
  successes and cannot be retried. Combined-v12 then reconstructed the exact
  333-input retained set twice and identified four exact non-selected Wave14
  tuples. Wave14 decision v1 resolves all four H1 pairs with zero
  blocked/conflicting identities, and the latest observed local suite passes
  27/27. Its separate permit passes 18/18 and 48/48, acquisition attempt
  `7fef20e6c3931b698f32b2a71f8a596a` retained all eight resources, and
  readback attempt `177051373b1754fd638b5f57df2d6515` verified the exact
  27-file snapshot twice before manifest-last publication. Both Wave14
  one-use actions are consumed and cannot be retried. Combined-v13 then
  reconstructed the exact 341-input retained set twice, passed 24/24 tests in
  2,360.584 seconds, and derived five exact non-selected Wave15 tuples at
  candidate SHA-256
  `e1f711b558642ad2167da48f25184cd4c3235314c67f06a60cfd14ceecea1988`.
  Wave15 decision v1 then reproduced five complete H1 pairs with zero blocked
  or conflicting pairs, bound ten ordered requests, and materialized canonical
  content SHA-256
  `1d574152a913b067508260828f355a596fa82f5e8657c560229951f13e01b6c0`.
  Acquisition attempt `c5db51cfd9a295b448927cca36d1ea07` retained all ten
  resources, and readback attempt `fb2b53eb42982732b0344695065c625d`
  independently verified the exact 29-file snapshot twice before manifest-last
  publication. Both actions are consumed successes and cannot be retried.
  Combined-v14 then reconstructed the exact 351-input set twice, passed 23/23
  full tests in 2,441.948 seconds plus 2/2 post-seal fast tests, and derived
  `fixedPointReached=false` with three exact non-selected Wave16 tuples:
  `golang.org/x/crypto@v0.39.0`, `golang.org/x/term@v0.32.0`, and
  `golang.org/x/text@v0.26.0`. Candidate-content, graph, and frontier SHA-256
  values are
  `e77b120d6e367e03beb847eb36cbf64b37d32fe00539b029ae809310818d5b9c`,
  `7458344c93152bea86360d2742456a28ebfc6849994bf68db30214611f020798`,
  and
  `5544db5bdf34f4afadce7d91f7c56998988e68810ed96b454048bf62dc07c452`.
  Wave16 decision v1 is now sealed at content SHA-256
  `0fa5d649f856ce9c04a3e3e14165c488eb5d467bbb2507c54cb6bc60ad989273`
  and raw SHA-256
  `ad76fbed203302ff915df56b62d655011c50a9c5d17f868bf0eb7dd752c97be6`.
  Its 27/27 tests reproduce three complete H1 pairs, zero blocked/conflicting
  pairs, and the exact six-request set SHA-256
  `b26cb50ac5070782744dec5a5c05f0cb07512ee421d69c52c6400946a28bd627`.
  The separate Wave16 acquisition permit passes 18/18 checker and 48/48
  network-denied runner tests at raw/content SHA-256
  `2fbbadf5808ca2cef8b3b9a04eceb24b98c0970a0f25b876d7f88dcfeab74dc5`
  and
  `1b009e4ae50e86bce96c8cd9062e95b9ea9d908380f9ca238ac4f37958a6bb0c`.
  Acquisition attempt `fff8d6073748eab6fd1a05c79c57a84f` retained all six
  resources without extraction: 452 `.mod` bytes, 11,475,192 ZIP bytes,
  11,475,644 total bytes, 948 ZIP entries, and 46,464,212 uncompressed bytes.
  The accepted hash-set SHA-256 is
  `f80997e5ef21d4b556667abc2fa016785bcd234dc7a79dc028f70c7d35a36159`.
  The offline readback permit passes 17/17 checker and 50/50 recorder tests at
  raw/content SHA-256
  `21914901195f2e83436ddb9aefad79137a86cc48afb22146176ff44ad1aa2aee`
  and
  `a7460624779ec3b50e39623df3d4154e38557cb65c22f2ee17632789e97419ba`.
  Readback attempt `e7c555246489b1ccd63bf3aca3e27c2f` verified the exact
  25-file snapshot at canonical SHA-256
  `b8863a58dd5db814afe94eb101c166e4f5bfb92d9b8197dbe3e32a3b1f0e99c4`
  twice, completed all three retained-FD barriers, and published the manifest
  last. Both Wave16 one-use actions are consumed successes and cannot be
  retried. Combined-v15 then held the exact 357-input retained set and
  reconstructed it twice across 179 archives, 68,852 entries, and
  1,296,608,653 ZIP-uncompressed bytes. Cumulative accounting is 28 full
  reconstructions and 3,696 graph archive opens. Input-set, source-binding,
  candidate-content, graph, and exact-frontier SHA-256 values are
  `4b12b7ca7f0a8b1556c692522e8832af033f9d2a1f00fbeb7469623a00541f1e`,
  `86512fdc6c5b8ff8b1d79e500e32c6c35c36f6c097aca5385f8ff1e06ffe18fd`,
  `4666c802e40734bb1b5b91489eb24aa782cb346710caec9605be4e0e005553ee`,
  `ffe9f910669401198b88752663055ca2e6622d19e171f2d20a2b303d06c989d7`,
  and
  `ce1be1152aabf580a211f038d80aeaf9249418117b7d12ff26ffc909f1e4d593`.
  It derives `fixedPointReached=false`, `route=next_wave_required`, and
  exactly one non-selected Wave17 frontier tuple,
  `golang.org/x/tools@v0.33.0`, with
  `selectedByGraphAlgorithm=false`. Checker raw/normalized and current tests
  raw SHA-256 values are
  `e0a8353e5bd4f40b587c2b62c563c0b679ca5261345e577d71d00fb868f08fb5`,
  `63198050500264a07082d205172c21993a309289649a5459e1c638b53fb22bf7`,
  and
  `65d7f435cef11da2cccae7e31a3c410d7a3038f6bc3261552753801a0de431b1`.
  The genuine two-pass run passed 21 of 23 tests; both failures were
  test-oracle defects. After correcting those oracles, the affected tests
  passed independently 2/2 and the fast boundary suite passed 2/2. All 23
  behaviors therefore have verification coverage across the genuine run and
  targeted reruns, but no single post-fix 23/23 full-suite run is claimed.
  Wave17 acquisition/readback attempts
  `117fb836380658986632911b9508e274` and
  `01f3117be3154e37f7f791b49002c490` are consumed successes. Combined V16
  then derived the three-tuple Wave18 frontier. Wave18 subsequently completed
  its verification-only decision, consumed exact six-resource acquisition, and
  completed independent readback without extraction. Combined V17 reconstructs
  the exact 365-source retained set twice and derives two non-selected Wave19
  frontier tuples with zero unmapped or unresolved imports. Wave19 then
  completed its verification-only decision, exact four-resource acquisition,
  and exact 23-file independent readback without extraction. The two Wave19
  one-use actions are consumed successes. Combined V18 then reconstructed the
  exact 369-source retained set twice and derived an empty-frontier fixed-point
  candidate with zero unmapped or unresolved imports. Its separate read-only
  closure review now accepts only the dependency graph fixed point. The
  fixed-point source/license preparation package is complete, but both
  independent passes remain incomplete at 0/2. The next boundary is bounded
  per-file semantic, special-source, broad-license/`PATENTS`,
  SPDX/provenance/binary, and native-profile completion work. Further
  extraction, source load/compile/execution, runtime
  socket/product network, Git write, device work, credential, authentication,
  or user action is not opened or required by this boundary.
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
  frontier. Wave2 and Wave3 then completed their versioned source acquisition
  and independent-readback paths. Combined-v2 held the root ZIP plus 100
  dependency resources and projected the non-fixed 16-tuple Wave4 frontier.
  Wave4 decision v1 binds 22 parent declarations and complete,
  conflict-free H1 pairs for all 16 tuples without acquiring Wave4 source. The
  separate one-use permit was consumed once; all 32 resources were retained
  and independently read back twice. Combined-v3 now holds 133 exact source
  inputs and projected the non-fixed 15-tuple Wave5 frontier. Wave5 decision v1
  resolved all 15 H1 pairs and prepared 30 ordered requests without acquisition
  authority at that checkpoint. The later one-use acquisition retained all 30
  resources, and readback attempt `8f3813a784359883b4d93370c9041809`
  independently verified the retained snapshot twice. Combined-v4 then held
  all 163 inputs and projected a non-fixed 18-tuple Wave6 frontier whose
  entries are all graph-unselected retained versions. Wave6 decision v1 then
  resolved all 18 H1 pairs and prepared the exact 36 ordered requests without
  acquisition authority at that checkpoint. The later one-use Wave6 acquisition
  attempt `5e0828c2e5dc1ce7ef2a06dd235d5076` retained all 36 resources,
  and readback attempt `7fc50276e880013e1ace73920397ba3f` independently
  verified the retained snapshot twice before writing its manifest last.
  Combined-v5 then reconstructed all 199 exact inputs twice and derived the
  non-fixed 15-tuple Wave7 frontier; its focused suite passes 25/25. Wave7
  decision v1 now resolves all 15 conflict-free H1 pairs, preserves every
  selector as false, and prepares 30 ordered requests without acquisition
  authority; its focused suite passes 13/13. Acquisition attempt
  `c15f4504ae880326144eca93dc91e37b` retained all 30 resources, and readback
  attempt `1839537589935de087068a5a7d5c7e14` independently verified them twice
  before writing its manifest last. Combined-v6 then reconstructed all 229
  exact source inputs twice, derived a non-fixed 14-tuple Wave8 frontier at
  SHA-256
  `d3c3788d6a1144bf04ea2c68e6aa4b9fdd17859bc625e2c2c51019bb3c61ff92`,
  and passed 25/25 focused tests. Wave8 decision v1 then resolves all 14 H1
  pairs, binds a 28-request contract, and passes 18/18 tests without granting
  acquisition. Its separate exact one-use permit package passes 15/15 checker
  and 44/44 network-free mock/local runner tests. Acquisition attempt
  `6d8ea4473126c853b439c56a895f9c28` retained all 28 resources; readback
  attempt `8618087527c005b5d19c8f902ec33557` independently verified the exact
  46-file snapshot twice and wrote its manifest last. Readback suites pass
  16/16 and 45/45, and independent GPT-5.6 Sol post-run audit reports no
  P0-P3 finding.
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
sed -n '1,90p' docs/progress.md
sed -n '1,90p' docs/qa-evidence.md
sed -n '1,230p' docs/roadmap.md
sed -n '1,420p' docs/releases/1.0.0-build-24-local-v1.md
```

Then run the cheap integrity checks:

```bash
python3 script/check_docs_hygiene.py
python3 script/check_macos_localization.py
python3 script/check_release_version_ledger.py
python3 -B script/check_release_artifact_archive.py --archive-dir dist/releases/aetherlink-1.0.0+24-local-v1
python3 -B script/run_macos_runtime_chat_cross_process_smoke.py --abrupt-recovery
python3 -B -m unittest script.test_run_macos_runtime_chat_cross_process_smoke
python3 -m unittest script.test_build_and_run
python3 -m unittest script.test_documentation_handoff_guards
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
includes the personal-governance synchronization, socket-free G1a-A/B/C/D
contracts, G1b-A stack-neutral ownership work, and the restricted-fork G2
lineage through consumed Wave19 acquisition/readback and the verified read-only
Combined V18 fixed-point candidate plus its non-authorizing closure-review
decision.
Wave12 through Wave19 one-use acquisition/readback actions are consumed
successes and cannot be retried.

Wave17 acquisition attempt `117fb836380658986632911b9508e274`
retained the exact x/tools `.mod` and ZIP pair, 3,450,700 bytes total, without
extraction. Readback attempt `01f3117be3154e37f7f791b49002c490`
independently verified the exact 21-file snapshot twice and completed all three
retained-FD barriers.

Combined V16 reconstructs the exact 359-input set twice. It covers 180
archives, 70,402 entries, and 1,305,716,657 ZIP-uncompressed bytes, with
cumulative totals of 30 full source reconstructions, 4,056 archive opens, and
60 underlying independent graph algorithms. Candidate, graph, and frontier
SHA-256 values are
`90928eb85eded2938b25a0beec82c00ebcd69147bf92733bc65a528d26c00e03`,
`db7e36664afd819c72e9c9916bd7053782282954ed4f359c550b7972b74147a2`,
and
`fe15a3ea57682b276a6f11a2c2fd998d9120640fac40038fc9c1f100e50750b5`.
It derives `fixedPointReached=false`, `route=next_wave_required`, no unmapped
or unresolved imports, and three non-selected Wave18 tuples:
`golang.org/x/mod@v0.24.0`, `golang.org/x/net@v0.40.0`, and
`golang.org/x/sync@v0.14.0`. The post-seal dry and fast boundary suites pass
13/13.

The verification-only
[Wave18 decision](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave18-v1.json)
resolves all three identity pairs, records zero conflict or blockage, and
binds the exact six-request set at SHA-256
`3c13b764b7267efe885528d9f7d4fe31d6b7bdac48839f95e60bb5bd45a7d836`.
Its content/raw SHA-256 values are
`c75e5751d3e7c67939251d56e212f95f85439d05684cd50a49701de3e099803d`
and
`c90d16a7c7194c7a6dbde2be9bd99f4101a3a8cd1722278209fe5df8bf6371fa`.
The isolated checker and 24/24 adversarial tests pass; final independent
review reports no P0-P3 findings. The decision creates no permit, runner,
claim, receipt, or manifest and grants no acquisition authority at that
checkpoint.

Wave18 acquisition attempt `4380f5bbcd3366154b05111381ccab18`
subsequently retained all six exact resources and 2,109,100 bytes without
extraction. Readback attempt `7e424a47ffdde1099227564f41d610c4`
independently verified the retained snapshot and published its manifest last.
Both one-use actions are consumed successes and cannot be retried.

Combined V17 reconstructs the resulting exact 365-source retained set twice.
It covers 183 archives, 71,373 entries, and 1,312,942,457 ZIP-uncompressed
bytes, with cumulative totals of 32 full reconstructions, 4,422 archive opens,
and 64 independent graph algorithms. Candidate, graph, and frontier SHA-256
values are
`1267edbe7f1a4f2554808376f67c6ba25a9217db0e6e2cc80a0822d780710f78`,
`cc748b6a5285321d8e74abab1c881dbc5ffd4433865ba9c75e459152f459092e`,
and
`4a7998ef0c1e5716640cccf9c5b349e92124bd787a2ca4090e3ba0920b68b006`.
It derives `fixedPointReached=false`, `route=next_wave_required`, no unmapped
or unresolved imports, and two non-selected Wave19 tuples:
`golang.org/x/crypto@v0.38.0` and `golang.org/x/text@v0.25.0`. Post-seal dry,
latent, and fast-boundary suites pass 18/18.

The verification-only
[Wave19 decision](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave19-v1.json)
resolves both exact H1 pairs, records zero conflict or blockage, binds the
exact four-request set at SHA-256
`97f4d8c1775c01c27f83f19b66af6274e0ae77b1be328456c2685ba18552b6e7`,
and passes 24/24 tests. Two independent GPT-5.6 Sol reviews report no P0-P3
finding. Wave19 acquisition attempt `f10c20196d994afe3a8eba830eb42614`
then retained all four exact resources and 11,453,955 bytes. Independent
readback attempt `060a3d9bcd02113ef12c2c75a1e11d70` verified the exact
23-file snapshot twice, completed all three retained-FD barriers, and
published its manifest last with zero network requests. Neither action
extracted, loaded, executed, or compiled retained source. Both one-use actions
are consumed successes and cannot be retried. Authentication and user action
remain false. Live Git state remains
authoritative for publication status. Completion applies only to the retained
snapshot; continuous current-path identity through manifest publication and
same-UID replacement prevention after the final barrier are not claimed.

Combined V18 reconstructs the exact 369-source retained set twice from the
exact 379-path inventory. It covers 185 archives, 72,304 entries, and
1,359,347,284 ZIP-uncompressed bytes, with cumulative totals of 34 full source
reconstructions, 4,792 archive opens, and 68 independent graph algorithms.
Candidate-content, graph, and frontier SHA-256 values are
`9dce50013314ec8934ad52ac57cb0de92e982c2334303fc77289f01bc9c285fb`,
`a865a62a7a80a0dece55aeebd537d3fb9aa73ce6ceeea10304a6a2074c2dfaba`,
and
`37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`.
It derives `fixedPointReached=true`, `route=fixed_point_candidate`, an empty
frontier, and zero new, unmapped, or unresolved tuples/imports. The dry,
latent, and fast-boundary suites pass 18/18. The genuine full class reproduced
the candidate and passed 23/24; its sole error was a stale test-chain index.
After correction, that affected legacy-Wave9 compatibility test passed
independently. No single post-fix 24/24 full-class rerun is claimed. Checker
raw/normalized and final tests raw SHA-256 values are
`35c35e98bfc0ea4b49f29b76d732a54f8f0f80dbbe20812266f35143c92da564`,
`b53fa66b34a8379216d64892502bb352220397c598cbe0b84911ca641b9e40aa`,
and
`44a62fc3771a027987320dee3c690f350a62d1eb16911fd925f56a22f09c74eb`.

The separate
[Combined V18 closure-review decision](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-combined-fixed-point-closure-review-decision-v1.json)
accepts only `dependencyFixedPointReached=true` for that exact retained
graph-discovery snapshot. Its canonical reader and self-sealed read-only
checker bind the V18 tools, semantic predecessors, and input/output digests;
the focused mutation suite passes 15/15. It creates or persists no candidate
artifact. All 19 semantic findings remain open, and dependency-source review,
dependency/semantic closure, license/security review, candidate/library
selection, rung-three completion, and release readiness remain false. At that
checkpoint, the next bounded G2 action was the separate fixed-point-snapshot
dependency source and license review decision completed below. Authentication
and user action remain false, and no
acquisition, extraction, loading, execution, compilation, network, socket,
device, publication, Git-write, or deployment authority is opened.

The separate
[fixed-point snapshot source/license review decision](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-fixed-point-snapshot-source-license-review-decision-v1.json)
and zero-write adapter are complete for their preparation-only boundary. The
adapter binds all 369 inputs, 184 dependency tuples, 185 archives, 72,304
entries, 58,478 Go files, 11,150 special-source rows, and the accepted V18
graph; its focused suite passes 14/14, while the decision checker and mutation
suite pass 15/15. Two independent GPT-5.6 Sol passes reproduced the exact
input and full scan but both returned `passComplete=false`, so completed passes
remain 0/2. Pass A's code claims are rediscoveries of existing canonical
findings. Pass B's `PATENTS` and native-profile gaps are review-completion
blockers under the existing dependency-review gap rather than new product
vulnerabilities. Initial pass B's no-P0-P3 statement meant no new finding and
did not
contradict or close the existing open P1 findings at that incomplete stage.
Resume with bounded
file-by-file semantic, special-source, broad-license,
SPDX/provenance/binary, and native-profile coverage. Do not request
authentication or user action.

Both passes subsequently completed deterministic rows 1-164: 164 files and
753,000 bytes at batch SHA-256
`e3604e20a65059f07429913d09784784493c5fd8b71b3859ca544963cdfd143a`.
Each still has 328 files remaining, so completed-pass count remains 0/2.
Cross-validation confirmed one new non-canonical P2 reliability candidate:
DTLS queues subslices of a pooled receive buffer without copying, returns the
backing buffer to `sync.Pool`, and processes the queued data later. It also
confirmed unbounded completed-handshake caching as a dependency-source
extension of existing resource finding
`G2SR1-F-9206ffd24b3357f7cda5`. No authentication bypass is claimed and neither
observation is a persisted closure result. Continue with exact batch 2 rows
165-328; never request authentication or user action.

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

### Frozen historical Build 14 packaged macOS clean-HOME evidence

These immutable results remain Build 14 evidence only. The generic runners now
target current Build 19 and must not be used to relabel Build 14. Verify the
frozen Build 14 result identities and historical archive without
reinterpreting current-run output as Build 14 evidence.

```bash
shasum -a 256 \
  script/run_macos_clean_home_installed_app_smoke.py \
  script/test_run_macos_clean_home_installed_app_smoke.py \
  script/run_macos_clean_home_installed_state_recovery_smoke.py \
  script/test_run_macos_clean_home_installed_state_recovery_smoke.py
python3 -B script/check_release_artifact_archive.py --archive-dir dist/releases/aetherlink-1.0.0+14-local-v1 --historical
python3 -B script/check_docs_hygiene.py
```

### Historical Build 10 packaged macOS lifecycle

The frozen runner's original observations remain exact Build 10 evidence only.
Because Build 19 is now current, do not invoke that runner: its fixed
current-source lane intentionally no longer matches the ledger. Verify the
historical archive, preserved test contract, and immutable result bytes
without launching the app.

```bash
python3 -B -m unittest script.test_run_macos_packaged_app_build10_lifecycle_smoke script.test_run_macos_packaged_app_lifecycle_smoke
python3 -B script/check_release_artifact_archive.py --archive-dir dist/releases/aetherlink-1.0.0+10-local-v1 --historical
python3 -B script/check_docs_hygiene.py
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

### Paused broad aggregate gate

Do not run `script/check_no_device_quality.sh` under the current user
direction. It mixes the active product-quality checks with paused work outside
this lane. Use the focused non-security commands relevant to the changed files
and report those exact results instead.

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
- The QR/device slice expanded no source-acquisition, native-library execution,
  socket destination, runtime-network, external-egress, P2P Phase B,
  production-network, or deployment authority.
- Separate bounded Wave11 source-acquisition and offline-readback authorities
  were later consumed exactly once. They are terminal, non-reusable evidence
  and do not authorize any further acquisition or product/runtime operation.
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
  `gitOperationAllowed=false`. The succeeding separately versioned waves
  through Wave12 retained and independently read back their bounded resource
  sets without mutating that rung-one profile or selecting a library.
  Combined-v10 reconstructed all 317 predecessor inputs and derived a non-fixed
  four-tuple frontier. Wave12 identity/acquisition decision v1 completed all
  four exact H1 pairs with zero blocked or conflicting rows. Acquisition
  attempt `f977ddcf8fc391e5915048b930beccbd` retained its 8 exact resources, and
  readback attempt `32ab6b747a02382f85f48f65e0c388c5` verified the exact
  26-file snapshot twice before manifest-last publication. Both Wave12 one-use
  actions are consumed and cannot be retried. Rejected or consumed authority
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

Unless the user redirects the task, use this active non-security order:

1. Re-read this handoff and refresh Git plus generated-artifact state. Do not
   infer device/process state from an older snapshot.
2. Run the focused static guards. Use
   `python3 script/check_release_artifact_archive.py --archive-dir dist/releases/aetherlink-1.0.0+24-local-v1`
   for the current Build 24 source-bound archive. Use the same command with the
   Build 23 archive path and `--historical` for frozen Build 23 integrity.
   Builds 1 through 23 require `--historical`.
3. Preserve both frozen historical Build 14 clean-HOME runner/test/result
   identities. The
   first proves two exact-path launches with stable empty SQLite state. The
   second separately proves one fixed legacy-to-SQLite canary and SQLite-only
   recovery across distinct installed-app processes. Do not widen either to
   arbitrary histories, crash/power-loss, concurrent writers, a clean
   machine/account, DMG/Finder install, UI/accessibility, signed distribution,
   provider, or physical-device claims. Current generic lifecycle runner output
   is Build 19 evidence and must not be relabeled as Build 14.
4. Preserve the historical Build 10 packaged-app lifecycle result and the
   exact Build 9 historical runner/test/result bytes. Do not run the frozen
   Build 10 lifecycle command against the Build 19 ledger. Preserve Build 12's
   failed-closed, non-published marker-file attempt. Historical Build 13 proves
   its bounded benign legacy migration and second-process SQLite readback only
   for Build 13; its bytes are not Build 14, Build 17, Build 18, or Build 19
   evidence.
5. Continue the non-security provider matrix only when live provider execution
   is in scope. Both exact Ollama candidates now
   have isolated empty-catalog plus two existing chat-model shapes, one
   embedding-model shape, and one vision-model shape
   cold/restart evidence plus bounded chat process-lifecycle fault and recovery
   evidence. Their four-scenario fixed-task embedding semantic-quality and
   fresh-provider recovery gate also passes for English V1. The separate
   five-locale V2 observation now preserves retrieval query/document roles,
   uses the recognized Ollama profile prompts, binds the effective input
   profile to result validation and V3 cache identity, accounts for profile
   prefixes in batch budgets, and binds those implementation sources. It still fails the fixed
   positive-margin check at Korean scenario ordinal 2 on both exact candidates;
   its task and thresholds remain frozen, and both follow-up recovery phases
   pass. Treat this as an explicit model-qualification gap rather than a
   passing gate. Exact LM Studio
   execution stays deferred until the official tools
   expose an independent user-data/model-store path that cannot change the
   installed app. Keep a passing multilingual result, retrieval accuracy,
   minimum-version, further-model-shape,
   embedding/vision fault, power-loss, concurrency, soak, SLA, and full
   qualification claims open.
   The current product path separately adds bounded semantic-similarity
   reranking with primary-score acceptance groups and primary fallback. Keep it
   labeled deterministic no-device product behavior until live end-to-end
   retrieval evidence exists.
6. Keep physical-device, production signing, store upload, and deployment work
   deferred until the user explicitly selects those technical slices.
7. Do not start security, authentication, governance, or owner-proof work.
   Do not stage, commit, or push unless the user explicitly asks.

### Inactive Historical Continuation Record

The numbered sequence below is preserved only as historical context. It is not
the active next-session plan while security work is paused:

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
   independent readback recorded the exact 15-tuple frontier. Wave2 and Wave3
   later completed bounded acquisition and independent readback. Combined-v2
   held 101 exact source inputs and projected the non-fixed 16-tuple Wave4
   frontier. Wave4 decision v1 reproduced 22 parent declarations and all 16
   conflict-free H1 pairs. Its separate one-use permit was consumed exactly
   once; 32 resources totaling 24,118,812 bytes were retained and independently
   read back twice. Combined-v3 now holds 133 exact inputs and projects the
   non-fixed 15-tuple Wave5 frontier. Wave5 decision v1 resolved all 15
   conflict-free H1 pairs and prepared 30 ordered requests without acquisition
   authority at that checkpoint. The later one-use acquisition retained all 30
   resources, and the retained snapshot completed its separate two-pass
   readback. Combined-v4 then held all 163 inputs and projected an exact
   non-fixed 18-tuple Wave6 frontier. Wave6 decision v1 then resolved all 18
   H1 pairs and prepared the exact 36-request contract without acquisition
   authority at that checkpoint. The later one-use Wave6 acquisition retained
   all 36 resources, and readback attempt
   `7fc50276e880013e1ace73920397ba3f` independently verified them twice.
   Combined-v5 then reconstructed the exact 199 held inputs twice, derived
   `fixedPointReached=false` with the exact 15-tuple Wave7 frontier, and passed
   25/25 focused tests. Wave7 decision v1 then resolved all 15 conflict-free H1
   pairs, preserved selector `false`, and prepared the exact 30-request
   contract without acquisition authority; its focused suite passes 13/13.
   Acquisition attempt `c15f4504ae880326144eca93dc91e37b` retained all 30
   resources, and readback attempt `1839537589935de087068a5a7d5c7e14`
   independently verified them twice before writing its manifest last.
   Combined-v6 then reconstructed all 229 exact source inputs twice, derived
   `fixedPointReached=false` with the exact 14-tuple Wave8 frontier at SHA-256
   `d3c3788d6a1144bf04ea2c68e6aa4b9fdd17859bc625e2c2c51019bb3c61ff92`,
   and passed 25/25 focused tests. Wave8 decision v1 then resolves all 14 exact
   H1 pairs and passes 18/18 tests. Its 28-request contract has SHA-256
   `b0f0f887864ddc4cf3ab15319a9e89dbea8c84087fa3d0e374a0332240336ddc`,
   with every decision selector and acquisition authority false. Its separate
   exact one-use permit package binds resource canonical SHA-256
   `ee32b0512643b0e767f5b1e96625352fc47ea6ae7aea5d7366adfe98f4db8136`,
   and passes 15/15 checker plus 44/44 network-free mock/local runner tests.
   Acquisition attempt `6d8ea4473126c853b439c56a895f9c28` retained all 28
   resources, and readback attempt `8618087527c005b5d19c8f902ec33557`
   independently verified the exact 46-file snapshot twice before manifest-last
   publication. Readback suites pass 16/16 and 45/45. Combined-v7 subsequently
   projected the exact non-fixed ten-tuple Wave9 frontier, and Wave9 decision
   v1 resolved all ten H1 pairs without acquisition authority. Its separate
   one-use 20-resource permit package passes 16/16 checker and 44/44 injected
   network-free runner tests. Acquisition attempt
   `df64a4816a083806020580efe953b9a7` retained all 20 resources, and readback
   attempt `2d61a0483984e9a2f77665dd3c624cb2` independently verified the exact
   38-file snapshot twice before manifest-last publication. Readback suites
   pass 16/16 and 45/45. Neither one-use action may be retried. Combined-v8
   then reconstructed all 277 exact source inputs twice and derived the exact
   non-fixed eleven-tuple Wave10 frontier at SHA-256
   `780501bca37fbeb953590004ca7e5aad7f206083f749b920e2a9842b63675f82`.
   Its checker exits zero and the full suite passes 29/29. Wave10 decision v1
   then resolved all eleven exact identities, including one graph-selected
   x/xerrors vertex, reproduced 15 declarations, 107 `go.mod` H1 and 15 ZIP H1
   witnesses twice, and bound the exact 22-request set at SHA-256
   `cf6a97651565b55bb714a713e66e6a452f7132973ce21ced254bd0d728d12a89`.
   Its disk checker exits zero and focused suite passes 21/21. Acquisition
   attempt `ffe70ee4562fcfc9e0fd6c9c4e136bd9` then retained all 22 exact
   resources, and offline readback attempt
   `e74e030f7f5ef33589d7895e1b28b3b1` verified them twice before manifest-last
   publication. Both one-use actions are consumed and cannot be retried.
   Combined-v9 then held 299 exact source inputs, reconstructed the graph twice,
   and derived the exact non-fixed nine-tuple Wave11 frontier at SHA-256
   `171af951e3a67405b62ddceface1341bb6f64b08f370d3d216ede541bd011f06`.
   Its exact final suite passes 21/21 and two independent GPT-5.6 Sol audits
   report no P0-P3 finding. Wave11 decision v1 then reproduced the identity scan
   twice, resolved all nine exact pairs with 12 declarations, 68 `go.mod` H1
   witnesses, 13 ZIP H1 witnesses, and zero selected, blocked, or conflicting
   rows, and bound the exact 18-request set at SHA-256
   `bbde21b5f7a523bb6cddf78fbbbfdce46f8bcf61d60ebcec72a80d52dda50ba8`.
   Its final suite passes 25/25 in 1,157.225 seconds and three independent
   GPT-5.6 Sol final-byte audits report no P0-P3 finding. Every selector and
   acquisition flag remains false.
   Wave11 acquisition attempt `ac18b8fda0a80a132510efd5dd17d5b7`
   subsequently retained all 18 exact resources (16,363,894 bytes), and
   readback attempt `9b4dac65f66ce9e5d53dcd8edaf4d1d4`
   independently verified the exact 36-file snapshot twice, completed all
   three pre-manifest retained-FD barriers, and wrote the manifest last. Both
   one-use actions are consumed and cannot be retried. Combined-v10 then held
   all 317 exact source inputs, reconstructed the graph twice, and derived the
   exact non-fixed four-tuple frontier at SHA-256
   `8b84bd2fd9201d33f4424b9dd1018aee7f8470a87306c2ba23eba0c8b6d4ff05`.
   Wave12 identity/acquisition decision v1 then re-executed that exact
   predecessor, completed all four exact H1 pairs with zero blocked or
   conflicting tuples, and bound the still-unauthorized eight-request shape at
   SHA-256
   `6531872e99da0c94746cbdb53fe9f5302ebc71bc82bfde1705b5e2300b2a2ee5`.
   Its final suite passes 26/26. The separate exact-eight permit package is
   materialized and passes 18/18 checker plus 48/48 fake/local runner tests.
   Acquisition attempt `f977ddcf8fc391e5915048b930beccbd` retained all 8
   exact resources (15,036,269 accepted bytes). Offline readback attempt
   `32ab6b747a02382f85f48f65e0c388c5` independently verified the exact
   26-file retained snapshot twice, completed all three pre-manifest retained-FD
   barriers, and wrote the manifest last. Both one-use actions are consumed and
   cannot be retried. Combined-v11 reconstructed the exact 325-input set twice,
   and Wave13 decision v1 resolved all four resulting H1 pairs with zero
   blocked/conflicting tuples. Its decision content SHA-256 is
   `3d08d589ed9121128717215fe0d9583b6f64e59fc033e1c5f50477f6e59d5b83`,
   and its focused suite passes 27/27 in 1,648.766 seconds. Its separate
   exact-eight permit package is materialized at raw SHA-256
   `b976f9bea30a20e34df25e9d90cfa9ee4617ce825b0d28f254b5bb512b6c29a1`
   and passes 18/18 checker plus 48/48 fake/local network-denied runner tests.
   Acquisition attempt `eb05816e0b897ea8c3ad8b7089668e91` retained all eight
   resources, and readback attempt `8b5f92c9d90f825f5f3b46df0d006ef3`
   independently verified the exact 27-file snapshot twice before manifest-last
   publication. Both Wave13 one-use actions are consumed successes and cannot
   be retried. Combined-v12 reconstructed the exact 333-input set twice,
   passed 24/24 normal-path tests, and identified four exact Wave14 tuples.
   Wave14 decision v1 resolves all four H1 pairs with zero blocked/conflicting
   identities, and the latest observed local suite passes 27/27 tests. Its
   one-use acquisition attempt `7fef20e6c3931b698f32b2a71f8a596a`
   retained all eight resources, and readback attempt
   `177051373b1754fd638b5f57df2d6515` independently verified the exact
   27-file snapshot twice before manifest-last publication. Both Wave14
   one-use actions are consumed successes and cannot be retried. Combined-v13
   reconstructed the exact 341-input set twice, passed 24/24 tests in
   2,360.584 seconds, and derived five exact Wave15 tuples at candidate
   SHA-256
   `e1f711b558642ad2167da48f25184cd4c3235314c67f06a60cfd14ceecea1988`.
   Wave15 decision v1 is complete at content SHA-256
   `1d574152a913b067508260828f355a596fa82f5e8657c560229951f13e01b6c0`;
   all five H1 identity pairs are complete with zero blocked/conflicting pairs,
   and its exact ten-request set was later consumed exactly once by acquisition
   attempt `c5db51cfd9a295b448927cca36d1ea07`. That attempt retained ten
   resources and 5,065,246 bytes without extraction. Readback attempt
   `fb2b53eb42982732b0344695065c625d` then verified the exact 29-file
   snapshot twice before manifest-last publication. Both actions are consumed
   successes and cannot be retried. Combined-v14 reconstructed the exact
   351-input set twice, passed 23/23 full tests in 2,441.948 seconds plus 2/2
   post-seal fast tests, and derived three exact non-selected Wave16 tuples:
   `golang.org/x/crypto@v0.39.0`, `golang.org/x/term@v0.32.0`, and
   `golang.org/x/text@v0.26.0`. Wave16 decision v1 then reproduced all three
   complete H1 pairs with zero blocked/conflicting identities and passed 27/27
   tests. Acquisition attempt `fff8d6073748eab6fd1a05c79c57a84f` then
   retained all six resources and 11,475,644 bytes without extraction.
   Readback attempt `e7c555246489b1ccd63bf3aca3e27c2f` verified the exact
   25-file snapshot twice, completed all three retained-FD barriers, and
   published the manifest last. Both actions are consumed successes and cannot
   be retried. Combined-v15 then reconstructed the exact 357-input retained set
   twice and derived one non-selected Wave17 tuple. Wave17 subsequently
   completed its verification-only decision, consumed its exact two-resource
   acquisition, and completed exact-21-file independent readback. Combined V16
   produced the three-tuple Wave18 frontier; Wave18 then completed its
   verification-only decision, consumed exact six-resource acquisition, and
   completed independent readback without extraction. Combined V17 reconstructs
   the resulting exact 365-source retained set twice and derives
   `fixedPointReached=false`, `route=next_wave_required`, and two exact
   non-selected Wave19 tuples: `golang.org/x/crypto@v0.38.0` and
   `golang.org/x/text@v0.25.0`. Wave19 subsequently completed its
   verification-only decision, exact four-resource acquisition, and exact
   23-file independent readback without extraction. The two one-use actions
   are consumed successes. Combined V18 subsequently reconstructs the exact
   369-source retained set twice and derives an empty-frontier fixed-point
   candidate. Its separate read-only closure review now accepts only
   `dependencyFixedPointReached=true`. The fixed-point source/license
   preparation package is complete, but both independent review passes returned
   `passComplete=false`; completion remains 0/2. The next bounded G2 step is
   file-by-file semantic, special-source, broad-license/`PATENTS`,
   SPDX/provenance/binary, and native-profile completion work.
   Semantic review was performed, but semantic closure, dependency closure,
   rung-three completion, candidate selection, and library selection remain
   false. Android verified-endpoint
   handoff and
   macOS `CompanionAppModel` listener wiring may continue as stack-neutral
   ownership work, but the actual P2P backend and socket proof wait for their
   G2 scopes. The retained set is terminal acquisition/readback evidence only;
   no further acquisition, materialization, reviewed-source
   compile/execution, runtime network, Git, device, deployment,
   authentication, or user action is opened or required for this local work.
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
