# Roadmap

## Canonical V1 Delivery Roadmap

Last revised: 2026-08-02 KST.

This section is the canonical forward plan for the first production release of
AetherLink. It supersedes the shipping order implied by the historical feature
theme headings later in this document. Those entries remain useful product
ideas and implementation history, but `v0.x` or `v1.x` labels in older sections
are not release commitments. In particular, Windows, DGX OS, iOS, additional
serving backends, MCP, web search, skills, workspaces, and automations are
post-V1 work unless a later approved scope decision explicitly changes that.
Historical security material remains reference-only and does not govern the
active non-security lane.

### Current Non-Security Quality Lane

Active implementation is limited to non-security feature, UX, accessibility,
performance, build, and release-quality work at the user's direction. The G2
security track below is paused and retained as historical roadmap context; it
is not the next action.

The newest macOS G6/G7 release-quality slice replaces the main-only bare
Release compile with a clean `--unsealed-package-only` producer, exact
source-digest-before/after comparison, and independent
`--macos-build-outputs` readback. The producer assembles a nine-file app tree,
a three-file dSYM tree, and a canonical source receipt in a private
physical staging directory, verifies that the source snapshot is unchanged,
and atomically swaps the complete three-entry generation into the fixed output
root. The reader captures the source and receipt with stable no-follow reads
before and after the app/dSYM readback, binds the receipt to ledger `1.0.0+24`
and the current source, validates the closed plist/locale/mode trees twice,
and invokes `lipo`/`dwarfdump` only on a temporary materialization. It reports
each generation's sizes, closed-tree identities, thin arm64 architecture, and
shared UUID at execution time. This generic output gate does not freeze a
future generation's linked identities; the producer-bound current-run
lifecycle successor instead derives and validates one observed generation
inside that same run. Neither contract is a bit-for-bit reproducibility claim.
The producer and reader suites pass 17/17 and 78/78; the exact portable
lifecycle command passes 54/54. On `main`, package readback is followed by the
macOS diagnostics producer/readback, then two isolated
install/launch/SIGKILL/relaunch observations and an independent held-source
current-run readback. The product CI contract and mutation
self-test pass. This closes the current-source macOS unsealed direct-output
and bounded same-host lifecycle wiring gaps. The outer app has no
`_CodeSignature` or `CodeResources`, but the
executable may retain a linker-generated ad-hoc signature; neither Developer
ID signing nor notarization is claimed. Channel-valid or clean-machine install,
supported update/rollback, device/network, hosted CI, canonical G6/G7 exit,
RC/GA, and V1 remain open.

The newest G6/G7 release-quality slice extends both pull-request and `main`
Android lanes to ordered strict-lock `assembleRelease -> bundleRelease ->
lintRelease -> direct build-output readback`. Two consecutive clean release
graphs each succeed across 171 actionable tasks and produce byte-identical
outputs. The 9,575,138-byte APK SHA-256 is
`e0a13be5c5e054e4f9ef109756d0502dfabfe6e1bd791e1ce0d6596d58ca1c66`;
the 10,687,498-byte AAB SHA-256 is
`ac4d6ec00a08530d86cc33b68de9ff176f1cece8c27e969be77efa281df89c4e`.
The independent `--android-build-outputs` mode requires no macOS archive and
reads the ledger, APK/AAB metadata, two baseline-profile API ranges and their
DM files, badging, manifests, resources/config and universal APK, six R8 files
plus raw mapping and logical
PRT identities, five arm64 JNI libraries, 191 SDK dependencies with text,
protobuf, graph and lock closure, APK/AAB DEX identity, and
merged/stripped/native-symbol state directly from fixed Gradle outputs. Its
release archive suite passes 78/78, while the product CI contract and mutation
self-test pin the shared Release steps and the separate main-only complete-unit
steps. The macOS pull-request lane also runs a clean-checkout-safe tracked
documentation contract plus its two exact mode regressions; raw ignored
`dist/` evidence remains local full-checker scope. The same lane now runs the
offline release-compliance catalog check and the exact 22-test deterministic-
render and independent-reconstruction manifest with zero skips. Those contracts
cover the closed Android Gradle lock-file universe, empty Swift external-
dependency list with no `Package.resolved`, 350 exact coordinates, 379 retained
POM records, and four compliance members,
and the SPDX 2.3 graph with 351 packages and 692 role relationships without
performing a catalog refresh. Workflow raw and parsed semantic SHA-256 values
are
`d63005795068446895e5cbf5e5ed05d9497282c698da7b86c2b96155815bdfe0`
and
`4cd318b9e42e97159910080e2b84a2ba8b19fe5b92ecb94c2a189f8a2bb72401`.
This closes the current-source APK/AAB readback gap only. It is not signing,
store publication, installation, physical/device/network or release-to-release
evidence and does not complete G6 exit, canonical G7, RC/GA, or V1.

<!-- aetherlink-current-g7-nonsecurity-merge-full-local-candidate-v1:start -->
**Current G7 local non-security Merge-full candidate status.** The
current-source local runner executes 62 exact ordered commands and publishes
`.build/aetherlink-g7-nonsecurity-merge-full-candidate-v1/candidate.json` only
after every command exits zero, all 23 artifacts and five implementation inputs
read back from current bytes, the source snapshot is unchanged across child
readbacks, and a requested running-app PID retains its exact identity. The
result uses canonical ASCII JSON, mode 0600, atomic publication, and a separate
read-only checker.

The passing local matrix covers 222 focused Swift tests, 57 DocumentIngestion
ASan tests, two mutation XCTest identities and 96 deterministic mutation cases,
19 Android classes and 1,226 tests, zero Android lint issues, and 22 Release
compliance tests. It also builds and directly reads back the unsigned Android
Release APK/AAB, the unsealed macOS app and dSYM, both diagnostics results, and
the current-unsealed macOS install/recovery lifecycle result before repeating
all final readbacks.

Only the macOS package gate receives the fixed external Swift scratch path. The
runner acquires the existing nonblocking reproducibility lock, creates a
mode-0600 no-follow exclusive lease, rejects a pre-existing scratch or lease,
and validates and removes only its owned scratch and lease in `finally`. This
keeps repository `.build` evidence and the candidate parent intact across the
package producer's clean build.

This ignored local current-source candidate is not retained release evidence.
It does not claim the complete Swift suite, device/network execution, hosted CI,
signed artifacts, security/authentication/cryptography execution, canonical
Merge-full, canonical G7 exit, RC/GA, or V1 qualification.
<!-- aetherlink-current-g7-nonsecurity-merge-full-local-candidate-v1:end -->

<!-- aetherlink-current-g6-release-diagnostics-usability-v1:start -->
**Current G6 Release diagnostics usability status.** On `main`, each
product-quality Release lane now runs a diagnostics producer after its existing
Release-output readback. The producer writes one canonical mode-0600 result;
a separate checker command reopens the result plus the live artifact, source,
and tool identities and reruns the same concrete recovery operation.

The local macOS observation produced a 2,279-byte result with SHA-256
`d8d7d36d717f070b1c1163d7b0357f4c7425e56cbbd915821f983c7749202e5f`.
The 18,888,664-byte executable and 31,884,776-byte dSYM DWARF share UUID
`6BD7228B-5EF9-3DDD-B844-49739384BB00`; `/usr/bin/atos` resolves address
`0x0000000100001a30` to
`JSONValue.encode(to:) (in AetherLink) (JSONValue.swift:29)`, bound to
`apps/macos/Protocol/Sources/JSONValue.swift:29`.

The local Android observation produced a 2,739-byte result with SHA-256
`97badb21a8a104052d117ae9d8696f5b2093f51f6b995ff15c86f5eb0d9f87e2`.
AGP 9.2.1 supplies R8 Retrace 9.2.14. Against the current 72,050,888-byte
`mapping.txt`, Retrace changes
`at fx1.A(MainActivity.kt:23)` into
`at com.localagentbridge.android.MainActivityKt.ResearchBriefCreateDialog(MainActivity.kt:3496)`,
bound to
`apps/android/app/src/main/java/com/localagentbridge/android/MainActivity.kt:3496`.

The producer/checker mutation suites pass 24/24. The product CI contract and
self-test pin the exact unit, producer, checker, platform, branch, and ordering
bodies. The reviewed workflow is 21,656 bytes with raw SHA-256
`41f1532ba6037645e8b7c29629eb665d368a4f524a034c0b8d7a26b5740de73e`
and parsed-semantic SHA-256
`c6b90de31600f813d78ec4cfeb1f363c12ccef0735e8f2f93284024b60d89bdd`.

These are local current-source supportability probes against unsigned or
unsealed Release outputs. Their ignored `.build` result files are not retained
release evidence, and no hosted run of the current workflow bytes is claimed.
They do not prove device/network behavior, signing/store delivery, production
release, canonical G6/G7 exit, RC/GA, or V1 qualification.
<!-- aetherlink-current-g6-release-diagnostics-usability-v1:end -->

<!-- aetherlink-current-g7-document-ingestion-asan-v1:start -->
**Current G7 DocumentIngestion ASan seed-corpus status.** On `main`, the
macOS product-quality job now runs exact source/test preparation, an isolated
AddressSanitizer execution, result binding, and independent readback after the
normal focused Swift result gate. The checker owns `--sanitize address`, a
separate scratch path, serial execution, a 720-second process-group deadline,
bounded console capture, and TERM-to-KILL cleanup.

The ASan selector pins 57 exact `DocumentIngestionTests` identities with
manifest SHA-256
`71b37b2f02a4b8ef65c9e82011259345c86015572480274f1417ed16f5d9b690`;
the normal non-security Swift selector pins 222 identities with manifest
SHA-256
`b481e814d8e0f7a2385e50fb5d0f0f8d1602f08b608eb373bb8960ce53547815`.
Five deterministic tests cover malformed UTF-8/XML/ZIP/PDF/RTF/HTML,
exact-versus-plus-one limits, and Unicode grapheme chunk offsets. XML parse
failure can no longer publish already-collected prefix text, and extractor
fixtures remove their temporary files.

The local ASan run and independent binding readback pass 57/57 with zero skips,
failures, or errors. This is selected in-process Swift/Foundation/PDFKit
evidence; external tools such as `/usr/bin/unzip` are outcome-checked but are
not ASan-instrumented. Ignored `.build` bytes are not retained evidence, no
hosted run is claimed, and generational fuzzing, complete Merge-full,
canonical G7 exit, RC/GA, and V1 remain open.
<!-- aetherlink-current-g7-document-ingestion-asan-v1:end -->

<!-- aetherlink-current-g7-document-ingestion-mutation-v1:start -->
**Current G7 DocumentIngestion deterministic mutation status.** On `main`, the
fixed 57-test ASan seed-corpus lane is followed by a separate exact
prepare/run/bind/readback lane. It reuses the already-built isolated ASan
scratch, selects two `DocumentIngestionGenerationalMutationTests` identities
with manifest SHA-256
`268e426f7d7c69629188c444093f044efe1952628c2e4c20923c512aaf17f05b`,
and owns a 300-second monotonic process-group deadline with TERM-to-KILL
cleanup.

Test-only SplitMix64-v1 arithmetic and golden vectors derive 96 independent
cases from root `a37e2c915b04d8f6`. The exact cross-product covers `txt`,
`xml`, `html`, `rtf`, `pdf`, `docx`, `epub`, and `webarchive` across
twelve primary operators, with one through four total operators per case and a
4,097-byte hard bound. Fixed PDF and archive fixtures are decoded from pinned
base64 bytes rather than generated during the run. The matrix includes exact
4,096-byte and plus-one 4,097-byte inputs; every plus-one case must fail at the
input-file limit with exact limit and actual counts.

Immediately before each extraction the test writes one path-free ASCII
reproduction marker. The successful console parser requires cases `000...095`
exactly once and in order inside the mutation testcase, followed by one bound
summary. Marker-lines-plus-LF have SHA-256
`bd6e38cbac664aca4e7d4d912fddd1f853b93dfc5b862751921848d885d1e379`.
Binding construction and independent readback rerun that parser. On nonzero
exit, timeout, or bounded-log overflow, the prior successful canonical log is
preserved and only the last complete grammar-valid marker is surfaced.

The local ASan run passes 2/2 XCTest identities and 96/96 cases with zero skips,
failures, errors, or sanitizer diagnostics. Binding reconstruction and
independent readback validate the current console bytes, exact two-test
selection, 96-case marker manifest, and current 219-source input set.
Swift/XCTest stdout embeds timestamps and duration measurements, so the raw
console and derived binding SHA-256 values are run-scoped and deliberately are
not promoted to cross-run documentation identities. Each G7 candidate records
and rechecks its current run bytes instead. Runner/parser mutation self-tests
cover timeout, nonzero exit, malformed markers, log overflow, exact corpus
drift, and canonical-log preservation.

The reviewed product workflow is 21,656 bytes with raw SHA-256
`41f1532ba6037645e8b7c29629eb665d368a4f524a034c0b8d7a26b5740de73e`
and parsed-semantic SHA-256
`c6b90de31600f813d78ec4cfeb1f363c12ccef0735e8f2f93284024b60d89bdd`.
This closes one bounded deterministic generational-mutation gap, not
coverage-guided fuzzing or a per-case preemption guarantee for PDFKit/AppKit.
System frameworks and `/usr/bin/unzip` or `/usr/bin/textutil` remain outside
ASan instrumentation. Ignored `.build` evidence is not retained, no hosted run
is claimed, and complete Merge-full, canonical G7 exit, RC/GA, and V1 remain
open.
<!-- aetherlink-current-g7-document-ingestion-mutation-v1:end -->

<!-- aetherlink-current-g7-android-headless-nightly-v1:start -->
**Current G7 Android headless Nightly and local lifecycle status.** The
non-security workflow is schedule-only on `main` at `37 18 * * *` (18:37 UTC).
Its producer uses an arm64 `macos-26` runner; a separate `ubuntu-24.04` job
performs downloaded-byte readback. The scheduled commit is materialized with
`git archive`, Android dependencies are prepared online, and the evidence
producer then performs the exact offline Debug build. The workflow raw and
parsed-semantic SHA-256 values are
`6ca986d8ae194d4236c41815675ad885aaeb29e47639186847645db193a773fa`
and
`cf8afa1784d703d0484e8be14e450255c35d720c8ea2b0649ffda3abcccab85b`.
The exact Nightly contract passes 97/97 tests, including all 82 lifecycle tests
and all 37 V2 successor tests, with zero skips, failures, or errors.

The local disposable arm64 API 36.1 V2 run passes background deep Doze,
same-UID app-process `SIGKILL` recovery, and same-QEMU guest reboot: 3/3 in
106.214 seconds. Its canonical 51,933-byte result is
`build/qa/android-headless-api36-1-v2-20260801T224327Z-5c1b4db2/result.json`,
SHA-256
`878c9179751f960238e8c18bc1c0cae6f3ce8b096b5f6e7db3cf5c42e36646f9`.
The bound 145-file source snapshot has SHA-256
`2a440ac4369b06163f56d07988fdb56bb79c94ae473a5016a66e09eee497b2b4`.
An independent checker holds `result.json` plus all 58 evidence files through
one descriptor-relative no-follow graph, validates only the captured bytes,
reopens the complete graph, and passes 3/3. Cleanup leaves no owned emulator or
ADB transport.

For a hosted run, the same held snapshot produces candidate provenance and one
deterministic USTAR archive, performs deep local readback, uploads the raw tar
with `archive: false`, compares the upload digest, downloads by immutable
artifact ID, and independently reads back the downloaded bytes. An uploaded
tar always remains a candidate: artifact existence or producer-job success is
not acceptance. Only a successful conclusion for the same complete workflow
run, including the downloaded-byte job, makes those bytes acceptable evidence.

At this recorded local snapshot, no successful scheduled hosted run of these
workflow bytes exists, so hosted Nightly success is not claimed. The local run
does not prove physical/OEM/API-matrix behavior, optical QR, TalkBack, a live
provider, controlled production networking, upgrade/rollback, signing/store
delivery, complete Nightly coverage, canonical G7 exit, RC/GA, or V1 release.
<!-- aetherlink-current-g7-android-headless-nightly-v1:end -->

The predecessor current-source G5/G6 Android headless lifecycle V1 record is
`build/qa/android-headless-api36-1-20260731T233701Z-8a8a1726/result.json`.
It passes 13/13 scenarios with source SHA-256
`f3ca69649cd699aae99c3cee8e58871b0402494b08d1428271861705843ac8ba`
and result SHA-256
`828f25b69825f36650a5d4cd331f1d67ba510bdcb3ca8fe4c53741a04e338870`;
a separate checker process immediately read the same bytes back. The lane now
enforces absolute UI/locale deadlines down to each ADB call, binds twelve
process observations through `stat-before -> cmdline -> stat-after` stable
PID/start-tick identities, and independently parses four retained CAMERA
`dumpsys package` files as `false / false / true / false` across denial, cold
launch, regrant, and fixed revoke. Its 45 runner/checker unit and mutation tests
pass. The disposable emulator was removed and the pre-existing
`emulator-5580` PID `78792` was preserved. This strengthens emulator evidence;
within that predecessor contract it does not satisfy background/Doze/reboot,
physical-device, signed-artifact, production-network, release-to-release,
G5/G6 exit, G7, or V1-production gates.

The current Android G5 platform-language slice closes both the Android 13+
external-selection defect found on a disposable API 36.1 emulator and the
local legacy stored-language handoff gap. A supported nonempty
`LocaleManager.applicationLocales` snapshot is authoritative. When a legacy
API 26-through-32 explicit language first reaches API 33+ with an empty list,
the app durably records a pending tag, writes it to the platform, reads it
back, and then marks the one-time migration complete. Process interruption
retries the pending tag without another save. After completion, an external
clear means Follow system and never resurrects the old language; API 26 through
32 do not start the marker or write the list. Explicit English remains distinct
from an empty English-device override, and the first localized frame uses the
reconciled persisted/platform snapshot. Three focused storage/ViewModel/writer
regressions and three API 32/33/36 production-path lifecycle regressions pass;
the API 33 path includes migration, recreation/cold launch, external clear, and
external Korean override. External Korean and Japanese, in-app French, explicit
English, Follow system, and repeated cold launches all pass on API 36.1. The
same Debug APK also passes real permission-dialog denial/recovery, app-settings
handoff, and 200% font-scale reachability without a FATAL or ANR. This is
emulator evidence, not physical optical-camera, TalkBack, OEM, signing, or
production-release proof. The migration path is JVM/Robolectric evidence, not
a physical API 32-to-33 OS-upgrade observation.

The current Android G5 camera-permission slice moves request history above the
conditional QR scanner screen and models `NeverAsked`, `RequestInFlight`,
`RetryRequired`, `RationaleRequired`, `SettingsRecovery`, and `Granted`
explicitly. A checked app-private `LaunchPending -> Recorded` transaction
precedes and follows launcher acceptance. Storage failure suppresses launch;
launcher failure and incomplete completion become manual retry rather than an
automatic loop or false Settings recovery. Production wiring also reconciles
OS permission and stale in-flight state on `ON_RESUME`. Thirteen
resolver/transaction and Compose regressions pass. A dedicated controller-host
matrix passes 4/4 on API 26, 30, 33, and 36 while driving denial, rationale,
explicit retry, grant, revocation, and resume reconciliation through production
Compose wiring. A separate Robolectric lifecycle matrix launches the manifest
production `MainActivity` on the same four APIs. Its three paths per API pass
12/12: it retains the
Activity-recreation proof and adds saved-state-free same-JVM cold Activity
launches for durable `Recorded` and interrupted `LaunchPending` reconstruction
without duplicate CAMERA requests. A separate G5 font-scale qualification
spine records three independent results at exactly 100%, 150%, and 200%.
Each result exercises scanner, drawer, Chat, Settings pairing, Memory, and
chat-history reachability across all five app locales, with expanded state
coverage in English and Korean. It also enforces 48 dp QR-scanner close,
flashlight, cancel, and permission actions. The exact 45-test Android product
selector passes across twelve result classes. Focused result contracts resolve
by class name, and accepted JUnit XML must strictly postdate the workflow,
checker, Android build inputs, production source, and complete app test-source
graph. The complete app JVM suite passes 1,226/1,226 through the exact 19-class
`--rerun-tasks` runner. Its pre-run source marker binds every declared input
path, byte stream, and mode. The post-run gate requires the exact 19-report set,
1,226 unique nonempty test cases, and testcase-manifest SHA-256
`cc3ea9e2d72ca96e7f937b22a893d8cdaf38c409564ac8baecc5b947b8aa1b78`,
then canonically binds and independently reads back the marker and every report
byte. Equality is rejected at the source/report, marker/report, and
report/binding freshness boundaries.
The drawer regression resets each locale at the app title and traverses
`top -> header -> detail -> header` inside the actual scrollable history
viewport above the fixed Settings footer. It refreshes bounds at every phase
and preserves the exact merged accessibility summary.
This is current-source evidence after
immutable Build 24. Controlled platform values do not prove SDK-specific OS
permission or rationale policy, Android OS process death, or a physical
permission dialog. Camera startup, optical QR recognition, physical/OEM
typography, TalkBack, and G5 completion remain unproven.

Build 24 is the latest immutable local G6 package qualification record for its
qualification-time snapshot. The same post-Build 24 source now passes clean
offline strict-lock Android Release APK/AAB/lint generation and a
current-source local ad-hoc macOS Release package. The source snapshot is
`d5aee95b0a7b86c73ac111653f7bbf2e2d96b4e718b4d0b8db9571bcfe7d4dce`
across 253 files; the unsigned APK and AAB are 9,575,138 and 10,684,471 bytes.
An isolated temporary local archive passes independent 29-member readback: its
167,578,488-byte ZIP has SHA-256
`c329ed6a44f1e8a459345993f5e645cefa5b8bdc730cd78efe771fc0c8500f88`,
its 15,200-byte manifest has SHA-256
`f99521fce2f3e420265902323260a6a5b771805ddd71f3d4d1391617796efb72`,
and its 99-byte checksum sidecar has SHA-256
`24b860585953d9eaaf46b7b9e883d46c9b729e1e5beaba99f5bf0d8bc66dcebe`.
This closes only current-source local release-artifact build/readback risk.
The candidate retains `1.0.0+24` metadata, is not stored under
`dist/releases`, and does not relabel immutable Build 24 or create a canonical
Build 25. Distribution signing, installation, physical-device behavior,
publication, and production release remain open.
The immutable Build 24 record below retains the publish-qualified schema-v4 executions;
this comparison candidate does not alter them.

<!-- aetherlink-current-source-g6-lifecycle-suite-v1:start -->
**Recorded predecessor G6 exact Lane-A DMG and idle-resource lifecycle-suite
handoff.** At its execution snapshot, the comparison-only run bound 266
release inputs at source SHA-256
`63eeefbd7d13bf86452f39fc69337246f8a7ed0b945b5793f7f3ed33f3974c42`
and execution overlay SHA-256
`cf674143e321be2db26d1ea3b70c15dc05c6aed2182acb25e584b8da06256de6`.
Its unequal 101- and 109-byte source roots produced the exact same
167,086,118-byte archive at SHA-256
`cabc9dc622d55d3c3217a4542fd072b5884e49c717621fcfbc96b2f9f5b17037`,
with a 15,200-byte manifest at
`96505c31782a5fc4f10544a0e18ca8db8019528f5d78caed9eaf2463725c33a9`
and a 99-byte checksum sidecar at
`9e5bf156e16d87f428d3de7484deebc29370e6fc0f920300850b547f4a19b11d`.
All archive/member equality flags are true and both difference lists are
empty. The exact 19,645-byte primary result is
`dist/reproducibility/aetherlink-1.0.0+24-local-v1-two-root-v4-prepublication-current-source-g6-macos-unsealed-gate-source-binding-one.json`,
SHA-256
`b4581b21f5626f111f0d8cd7ef6858899c01ba366de23e1c667912497e93ece3`.

Only after exact A/B equality, the runner handed the materialized Lane-A
archive to the complete local-DMG and idle-resource lifecycle suite. The exact
3,038-byte install result is
`dist/lifecycle/macos-aetherlink-1.0.0+24-local-v1-two-root-lane-a-local-dmg-install-v2-current-source-g6-macos-unsealed-gate-source-binding-one.json`,
SHA-256
`154e5fb9ae0b0cd9f07b6b34135bc6fab1ea36e61464f967995d58bf57e68e92`.
The exact 3,485-byte same-DMG uninstall/reinstall result is
`dist/lifecycle/macos-aetherlink-1.0.0+24-local-v1-two-root-lane-a-local-dmg-uninstall-reinstall-v1-current-source-g6-macos-unsealed-gate-source-binding-one.json`,
SHA-256
`4fb0fc1f48df89e600edebde7afaf78a372ffd7e417d31b788cdb6e7ef400306`.
The exact 4,996-byte state-recovery result is
`dist/lifecycle/macos-aetherlink-1.0.0+24-local-v1-two-root-lane-a-local-dmg-uninstall-reinstall-state-recovery-v1-current-source-g6-macos-unsealed-gate-source-binding-one.json`,
SHA-256
`9530e99b9597da098b70abed657b923c523cf67552e1f0c203fb3bd16e5e11c6`.
The exact 7,200-byte abrupt-process recovery result is
`dist/lifecycle/macos-aetherlink-1.0.0+24-local-v1-two-root-lane-a-local-dmg-uninstall-reinstall-abrupt-process-state-recovery-v1-current-source-g6-macos-unsealed-gate-source-binding-one.json`,
SHA-256
`fe5d2d843f69e12484bfe905b4789de5d85b5c400d83ab6bedd280f7fd00ed44`.
Its exact 1,001-byte two-run repeatability receipt is
`dist/lifecycle/macos-aetherlink-1.0.0+24-local-v1-two-root-lane-a-local-dmg-uninstall-reinstall-abrupt-process-state-recovery-repeatability-v1-current-source-g6-macos-unsealed-gate-source-binding-one.json`,
SHA-256
`77d0d6477884bc5919ec9ee3babb8182a07bbb892f18a05eb8148b5c0db1f3a5`.
The exact 22,399-byte current-source idle-resource result is
`dist/lifecycle/macos-aetherlink-1.0.0+24-local-v1-two-root-lane-a-idle-resource-stability-v1-current-source-g6-macos-unsealed-gate-source-binding-one.json`,
SHA-256
`fd06f7c618e86b3adfa57aec4966534b25347f9b984b0aef52206052cf1ce570`.

The suite executed install, same-image removal/reinstall, and fixed-canary
state recovery before two independent abrupt-process cycles. Each abrupt cycle
persisted the fixed Runtime-chat canary, reinstalled from the same image, sent
`SIGKILL(9)` only to the exact owned child after a successful persistence
probe, observed exit code `-9`, reaped the process, found no remaining AppKit
process, and recovered the unchanged canary from a third graceful process.
The two 7,200-byte canonical results were byte-identical.

The final owned, sandboxed app received a 60,000 ms warm-up and 600,000 ms
observation with 120 samples at 5,000 ms intervals; maximum sample lateness was
79 ms. Open file descriptors stayed at baseline/final/maximum 4. Threads stayed
at baseline/final/maximum 3. Resident bytes stayed at
baseline/final/maximum 140,001,280. Every final and peak delta was zero.
The idle result binds the same 266-file source snapshot and the same
ten-file installed app tree of 21,356,326 bytes at SHA-256
`2596df8daa50f962ef776032a2487dd10d431b621f08d496d67b221fac0c9b64`.
It denied network access, confined writes to its temporary root, preserved
pre-existing applications, reaped only its owned child, and removed the
temporary root before publication.

The runner published six child results followed by the parent through one
create-only exclusive-rename transaction with owner-held parent-directory
leases, staging-file fsync, child-directory fsync, parent-last commit-marker
rename, parent-directory fsync, stable readback, and retained-staging
rollback/retry. Each lifecycle field
`archiveReadback.currentSourceCompared=false` means that the child exercise
performed archive-only validation. The documentation guard pins all seven
evidence files together and dynamically cross-binds every child release, ZIP,
manifest, checksum, archive-readback projection, installed tree, source
snapshot, repeatability identity, and recomputed idle summary to the parent
current-source Lane-A result. No lane archive was retained or published,
comparison-only release publication stayed disabled, and the protected Build
23 archive stayed unchanged.

A later full unequal-root lifecycle attempt failed its A/B exact comparator
before the atomic publication step. After the runner and its contracts were
strengthened, four retained comparison-only diagnostic result files recorded
the newer 266-file source snapshot at SHA-256
`eefe8cbf522afd152529b3b4b0ee6862616e832e7e4a8f29c268434b783a7ce6`
and overlay SHA-256
`b63123aef04182da7ae7192495d92487a3b5c7957fbbc271dc2e82f63c763651`.
The four exact JSON files are retained in the `dist/reproducibility/*-swift-root-diagnostic-v1-*.json` namespace.
The same-physical 104/104-byte-root result is 19,648 bytes at SHA-256
`c10b20231d7b8cc7a2bf5cfd325c97f831b64e167c0491641be34b20d3746e85`;
the distinct-equal 101/101-byte-root result is 19,644 bytes at SHA-256
`85255949ed10573c550155779c6d47545f68cd2c95cb0380466b8f489ca6c740`;
and both retained distinct-unequal 101/109-byte-root results are the same
19,656 bytes at SHA-256
`0e7fd34a6e4a4f477a8420c9f536a22008318501245f8b0ac4acd03ee08606b0`.
All eight recorded build entries identify the exact same 167,086,073-byte
archive at SHA-256
`a4a3615717ac4786086220e5894d2c196d70e31f03892c2fc7e609ede4e50274`,
15,200-byte manifest at
`22f63e62a39c4f1a2f4ec377dc45703afc37bfb38dcc45b01102af693e6d1f50`,
and 99-byte checksum sidecar at
`1eaf24633eb3e8993768c2d4c5a4c1d234b12a8782008bc7c3a700b9911738ea`;
their complete archive inventories match, every comparison flag is true, and
both difference lists are empty. The two unequal-root result files are exact
byte copies. Publication remained disabled, no lifecycle child was created,
and the protected Build 23 archive remained unchanged.

The retained current-source lifecycle-two successor then bound the same 266
release inputs at source SHA-256
`eefe8cbf522afd152529b3b4b0ee6862616e832e7e4a8f29c268434b783a7ce6`
and execution overlay SHA-256
`ee81fd795de1728dd483f44af5afaa839bc95e61e401b4ba3bbc41925cb0fd06`.
Both v4 two-root runs used the canonical unequal 101/109-byte geometry and
recorded the same 167,086,073-byte archive, 15,200-byte manifest, 99-byte
checksum, complete member inventory, and empty difference lists as the newer
diagnostic record. Its exact 19,645-byte parent is
`dist/reproducibility/aetherlink-1.0.0+24-local-v1-two-root-v4-prepublication-current-source-g6-swift-root-matrix-lifecycle-two.json`,
SHA-256
`984e8baef1a332a0ee67cb7cabdbf196f875b9c5837ce3444dbfa801a907b43b`.

Only after that exact A/B comparison, the retained suite recorded these six
create-only lifecycle children:

- 3,038-byte install result, SHA-256
  `16d1bde4bb4499303ff2f7b114848c57e1163ef36c8b86ef9d001333e1334cde`,
  at `dist/lifecycle/macos-aetherlink-1.0.0+24-local-v1-two-root-lane-a-local-dmg-install-v2-current-source-g6-swift-root-matrix-lifecycle-two.json`;
- 3,485-byte uninstall/reinstall result, SHA-256
  `8fdb6f9dc7f41dda4d0083dea6fb6bb45644dd4560d9a98ecacb75d3836b8136`,
  at `dist/lifecycle/macos-aetherlink-1.0.0+24-local-v1-two-root-lane-a-local-dmg-uninstall-reinstall-v1-current-source-g6-swift-root-matrix-lifecycle-two.json`;
- 4,996-byte state-recovery result, SHA-256
  `a4cf9d0fcd0164fb5193f36e084110492488a50643ace63ce7f021a522b89b5a`,
  at `dist/lifecycle/macos-aetherlink-1.0.0+24-local-v1-two-root-lane-a-local-dmg-uninstall-reinstall-state-recovery-v1-current-source-g6-swift-root-matrix-lifecycle-two.json`;
- 7,200-byte abrupt-process recovery result, SHA-256
  `a1beb69b55c7c0cc909d72d4e36b8620585ad2e13e60f26c26332529a4abee3f`,
  at `dist/lifecycle/macos-aetherlink-1.0.0+24-local-v1-two-root-lane-a-local-dmg-uninstall-reinstall-abrupt-process-state-recovery-v1-current-source-g6-swift-root-matrix-lifecycle-two.json`;
- 994-byte abrupt-process repeatability receipt, SHA-256
  `8f5a97a10e5d1c267fa9fee45cba57237f5ffdb72d8ad834df01fc86ed8e77b2`,
  at `dist/lifecycle/macos-aetherlink-1.0.0+24-local-v1-two-root-lane-a-local-dmg-uninstall-reinstall-abrupt-process-state-recovery-repeatability-v1-current-source-g6-swift-root-matrix-lifecycle-two.json`;
- 22,399-byte idle-resource result, SHA-256
  `02141c8e8e734417e359d566c656af87911146d9c0e1b9c01c382dd3fc2b9b66`,
  at `dist/lifecycle/macos-aetherlink-1.0.0+24-local-v1-two-root-lane-a-idle-resource-stability-v1-current-source-g6-swift-root-matrix-lifecycle-two.json`.

The successor children cross-bind the parent archive, manifest, checksum,
source snapshot, and exact ten-file installed tree of 21,356,326 bytes at
SHA-256
`0dd6363420e79b90ffac38fdf9410cc109122800f071ca9e1e66bf579ea21145`.
The owned idle process completed a 60,000 ms warm-up and 600,000 ms observation
with 120 samples at 5,000 ms intervals and maximum lateness 84 ms. File
descriptors stayed at 4, threads at 3, and resident bytes at 140,296,192;
every recomputed final and peak delta was zero. The full documentation checker
reads and validates all six children before treating the parent as the commit
marker. It performs stable no-follow reads, pins all seven identities, reuses
the runner's closed lifecycle validators, and rereads the parent after
cross-binding. It does not invoke archive publication or physical-archive
validation.

The earlier failed lifecycle attempt remains failed and is not relabeled by
the diagnostic or successor records. Together, the retained records prove only
the exact predecessor lifecycle snapshot, the newer same-host four-file,
three-geometry comparison record, and this exact current-source parent+6
successor. They do not prove arbitrary future rerun repeatability or universal
source-root independence.
They also do not prove
in-flight transaction durability, power loss, kernel crash, OS restart,
arbitrary history or long soak, arbitrary cross-host or clean-machine
reproducibility, Finder/quarantine/Gatekeeper behavior, signed/notarized
distribution, automatic data cleanup, N/N-1 upgrade or rollback,
physical-device, provider, network, UI/accessibility, security, deployment, or
production qualification.
<!-- aetherlink-current-source-g6-lifecycle-suite-v1:end -->

The current macOS G5/G6 lifecycle slice closes both listener and Bonjour false
readiness. `LocalPeerServer` reports `.listening` only after the operating system
reports `.ready`; `BonjourAdvertiser` then reports
`publishing -> published | failed` with a five-second timeout. The connection
manager keeps the app in the existing neutral `starting` state until publication
is confirmed. Only then can route allocation, relay startup, restored-pair work,
or pairing proceed. Publication failure, timeout, or unexpected late stop
releases local ownership and retains same-port Retry. Separate listener and
advertisement generations reject callbacks from replaced attempts, and a
metadata refresh during publication restarts only the advertisement with the
latest TXT data. `RuntimeDevServer` prints advertisement readiness and permits
development pairing only after publication, and exits on initial or late
publication failure. A late listener loss terminalizes its advertisement gate
before stop, so an already captured publish callback cannot emit stale
advertising or pairing output. Publication operations serialize reentrant or concurrent
replacement, confirmed publication cannot be overwritten by a racing timeout,
and immediate advertisement failure after asynchronous listener readiness is
forwarded before ownership cleanup. Status handlers run outside the lifecycle
lock so a handler can coordinate a stop on another queue without lock
inversion. Seven advertiser tests, all 39 manager tests, two focused AppModel
regressions, and the exact 217-test non-security product
selector pass.
This is local no-device lifecycle evidence only, not external-network discovery,
device, performance, security, signing, deployment, or release qualification.

The current Android G6 release-quality slice adds Build 23-forward compiled
entry-point topology and application-shell contracts. The builder and
independent readback checker
each parse the APK `aapt2 xmltree` and AAB bundletool manifest, require one
`singleTask`/`never` exported `MainActivity`, and close its filters to launcher,
`aetherlink://pair`, `SEND`, and `SEND_MULTIPLE` with the same canonical 44
MIME types. They also resolve the exact five application-shell references,
ordered five-locale config, and default plus five localized `status_title`
payloads. The AAB bundle config must disable language splitting, and direct AAB
manifest/resource observations must match its derived universal APK where they
overlap; that derived APK supplies the locale-config body/order for the
composite AAB claim. Stored claims use closed keys and exact types. Fifty-nine
release-archive regressions pass, and the bounded
Android product CI lane executes the whole contract module. Locally present
historical Build 21 outputs produce the same topology and application shell
through the standalone APK and composite direct-plus-derived AAB paths. The
claim intentionally excludes unrelated activities merged from dependencies;
it is a closed MainActivity entry-point contract rather than a complete
application-component inventory. The
gate is deliberately inactive for immutable Builds 1 through 22. At the
preflight stage, no canonical Build 23 release existed; an isolated
current-source `1.0.0+23` candidate passed offline strict-lock APK/AAB/lint generation and
builder-versus-independent-checker real-tool parity. Its APK and AAB SHA-256
identities are
`ecbd83e71889d43134c121f057df7cf38e2e04a08a95fc7588f10e3ee6521ea9`
and
`af9b77eb7d13563a45cab5b7fe10bc71ba47caa633f4eaedbf719278f80e06fa`.
That temporary candidate did not bump the canonical ledger or create/rewrite
an archive. A later ordinary-wrapper run retained
`dist/releases/aetherlink-1.0.0+23-local-v1/`; its 166,859,521-byte ZIP SHA-256
is `b9a9c3c2ebeb01fc735fed3356f1f244178fb4521c1a806dc7a93d776f83ea2e`.
The subsequent Build 23 comparison-only candidate was not published. Its
19,645-byte result at
`dist/reproducibility/aetherlink-1.0.0+23-local-v1-two-root-v4-prepublication.json`
has SHA-256
`e82cfc2b2cf005ace6f5405065b997f7fb66a1338d1bf3d3fe082d1b9863b297`.
Its
166,345,274-byte ZIP SHA-256
`f9bee58ed228e31103bfd3929d2b2ba9c4fd30cb3fbc907b6f39f2d287239ffb`
differed from the retained archive only in the macOS executable, dSYM DWARF
member, and relocation member. Build 23 is therefore a retained historical
ordinary-wrapper archive, not the canonical qualified two-root lineage. No
device run, visual launcher/theme observation, distribution signing,
publication to an external service, permission analysis, or network claim is
part of this slice.

The current G6 non-security slice isolates macOS packaging from the running
development app. Package-only performs a clean default Swift build into
`dist/package-only/AetherLink.app`, while the release wrapper stages at
`dist/release-package/AetherLink.app`; strict direct-child path validation
prevents either flow from deleting `dist/AetherLink.app`. Eleven
fake-toolchain regressions pass. A separate Build 22 post-archive harness then
completed temporary-HOME install, launch/termination, exact app removal,
Application Support preservation, same-build reinstall/relaunch, and final
removal twice with byte-identical evidence. All three initialized SQLite files
passed integrity readback and retained state bytes and modes did not change.
This closes one bounded macOS uninstall/reinstall and packaging-isolation gap.
It does not qualify N/N-1 upgrade, rollback, automatic data cleanup,
clean-machine/Finder installation, signing/distribution, providers, networks,
UI, or physical devices.
The latest immutable ledger archive is `aetherlink-1.0.0+24-local-v1`.
Builds 1 through 23 remain separately readable historical archives.

<!-- aetherlink-current-build23-to-24-isolated-upgrade-v2:start -->
The current G6 non-security lifecycle slice adds one post-archive Build
23-to-Build 24 upgrade observation. The runner snapshots each archive's exact
ZIP, manifest, and checksum sidecar, then uses those same bytes for archive
readback, extraction, and exercise before rehashing them unchanged. It installs
Build 23 under a temporary HOME, migrates one fixed Runtime-chat canary,
replaces only the exact app path with the manifest-matched Build 24 tree, then
performs two Build 24 SQLite-only readbacks. All three SQLite files pass
integrity, the canary remains exactly once, retained state bytes and modes do
not change, three launches use distinct processes, and final removal preserves
Application Support.

Two complete runs produced the same 6,469-byte canonical result at
`dist/lifecycle/macos-packaged-app-build-23-to-24-isolated-upgrade-v2.json`,
SHA-256
`ddec23cf048fa77c559ca7ee4f45354feb558f830ca4b01eccffa5b7786ea09c`.
The 898-byte repeatability receipt at
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
It opens and retains the repository root, eleven exact directories, and all 40
unique target regular-file descriptors before hashing any target. It then
streams the exact Build 23 and Build 24 archive, manifest, and checksum
sidecars; the terminal version ledger; seven current lifecycle results; two
repeatability receipts; and 25 source files. Final entry and directory-graph
readback must match the held initial identities.

Eight runner/test files that evolved after the evidence run are read from the
non-executable `docs/evidence/macos-build24-lifecycle-source-v1` snapshot. The
checker pins commit `38027523f65f97a81044555c2f42b020eada3436`, the exact
semantic-to-storage map, every byte identity, and the closed fixture directory
inventory, so current source cannot be relabeled as Build 24 evidence.

The checker independently rejects noncanonical or duplicate-key JSON,
non-exact integer, float, and boolean field types, wrong top-level schemas,
release or app-tree drift, reversed Build 23-to-24 direction, weakened
limitations, and receipt/result mismatch. It imports and executes no lifecycle
runner and performs no subprocess, image mount, app launch, file write,
network, device, or Git operation. The 12 exact focused unit modules remain
byte-bound inputs but are deliberately not executed by this static checker.

The standalone readback passed. A separate exact invocation of those 12
non-security unit modules passed 169 tests, and the aggregate checker's own 24
mutation and boundary tests passed. The 80,890-byte checker has SHA-256
`05a9aea9388ff93cebfde53cf5c5dbd6e0034e01d7d58d28923f60c8f422d18e`;
the 38,123-byte test module has SHA-256
`46b381dda17337709879f361aa9c4957a9b00cc0db69a1ce7cfb8a7ca3bd04fb`.

This gate publishes or rewrites no lifecycle result and creates no new install,
launch, DMG, upgrade, recovery, or repeatability observation. Build 23 remains
a retained historical predecessor, not a declared rollback lineage. The pass
is bounded static/no-device consistency evidence and preparation for a future
G7 deterministic check; it is not canonical G7 PR-fast completion and does
not complete the signed, physical-device, network, rollback, production, or
other remaining G6/G7 exit requirements.
<!-- aetherlink-current-build24-macos-lifecycle-aggregate-readback-v1:end -->

<!-- aetherlink-current-build24-macos-current-unsealed-install-recovery-v1:start -->
The current-source non-security G6 companion installed the final unsealed
Build 24 generation under an isolated temporary per-user HOME. Two independent
observations each completed three distinct direct-owned launches, for six
launches total. The first launch migrated one fixed Runtime-chat canary and
terminated normally. After the harness removed only the fixed legacy fixture,
the second launch completed SQLite-only readback, held the exact installed
executable descriptor, parsed its thin arm64 Mach-O bytes in memory, required
one primary SHA-256 CodeDirectory, and recomputed every 4,096-byte code-page
hash including the partial final page before deriving its CDHash. No temporary
path or external `codesign` process was used for that held-byte identity. The
harness matched it to the actual running PID after readiness and again
immediately before signal, revalidated AppKit and physical path identity, and
sent SIGKILL only to that owned `Popen` PID. The process returned `-9`, was
reaped, and disappeared from AppKit; the exact stdout observation and empty
stderr were reread after reap and matched their pre-signal bytes. A third new
PID read the same persisted state and terminated normally. All three SQLite
files passed integrity checks at migration, pre-signal, post-signal, and
recovery readback; the canary stayed exactly once, and every retained
state-file byte and mode remained unchanged.
The exact temporary app was removed, the temporary root disappeared, and every
pre-existing AetherLink application was preserved.

The exercised generation has UUID
`2777D1B6-E198-3A60-8607-65AA068D530E`. Its nine-file, 21,444,161-byte app tree
has SHA-256
`3f4f624ef968ed017c1f74d73ba39519039de8b1d07b66482fc608e76d369321`;
its three-file, 38,283,827-byte dSYM tree has SHA-256
`e27cdaf134cca4a21bd250625a432d1bb6d18f0df5bea2b8086fb793150f80cc`.
The 268-file source snapshot has SHA-256
`99cebb6b02127c29ba71cc5190bac0543607fd6acb29d86091a21e6e25df3778`,
and its 355-byte canonical receipt has SHA-256
`15bfbd155140b2b97d8d1a4c8a44860fccc4da00fe7da17dc3ff559b0c5ef4da`.
The app has no outer bundle seal. Sandbox preflights denied AF_INET bind and
writes outside the temporary root.

Both observations produced the same canonical 7,628-byte result at
`dist/lifecycle/macos-current-source-unsealed-build-24-clean-home-install-abrupt-process-state-recovery-v1-source-closure-five.json`,
SHA-256
`9b4521b0ca765ca3d8bd8561fd9aaaafd817939d9ebf172ab61b9e2b0bc78e6b`.
The create-only 1,572-byte repeatability receipt is at
`dist/lifecycle/macos-current-source-unsealed-build-24-clean-home-install-abrupt-process-state-recovery-repeatability-v1-source-closure-five.json`,
SHA-256
`c15620728aa7f82d127e652da69fc8c58d71f488e90ff820fbc8eb9e6476a899`.
The earlier graceful source-closure-one and abrupt source-closure-two and
source-closure-three and source-closure-four result/receipt pairs remain
exact byte- and mode-preserved historical predecessors. The checker now pins,
holds, and reopens all eight files alongside the closure-five pair.

The 96,711-byte runner and 47,896-byte 35-test module have SHA-256 values
`24b8e328d6974d55a8b33034eee7667b11180e4d609234faa09411ec42ae4890`
and
`7b75e9523b78ac5d29d308bd60c3217eaef97e8e115828204866e3a8eb2792a0`.
The standalone 45,879-byte closed-generation checker and 17,694-byte 21-test module
have SHA-256 values
`975fe5e903521ee98ac57358de07daadc08a59fa9eb2a5700ae30c2655f2595e`
and
`97b524f3bf2000b6198016f2a8738dc794660b4741f10c3834367739f7200469`.
The checker imports no producer. It holds the result, receipt, eight predecessor
files, app, dSYM, source receipt, ledger, and exact eleven-file execution-source
closure through descriptor-relative no-follow reads, then reopens the complete
graph and rejects canonical/type/schema, predecessor omission/replacement,
cross-binding, symlink, hardlink, inventory, same-byte ABA, ancestor, and
replacement-race mutations. Its direct readback and all 21 tests passed against
the recorded closure-five generation. Eleven portable snapshot/schema tests and
eight current-run checker tests are clean-checkout-safe and run with the 35
runner tests on pull requests, `main`, and the local full gate, for 54 tests
total. The remaining ten static-checker tests require the superseded
closure-five ignored evidence and exact app/dSYM generation. Because
`dist/unsealed-package-only` is the mutable current output, the local full gate
does not directly invoke this historical checker or run those ten repository-
bound tests. Rebinding its pins or invoking the current-run checker without its
producer would break provenance or clean-checkout determinism.

On `main`, the G7 successor now runs after the fresh unsealed package build,
generic output readback, and Release diagnostics producer/checker. It executes
the same lifecycle producer with two independent observations. It writes only `result.json` and
`repeatability.json` as owner-only files inside the private
`.build/aetherlink-current-unsealed-lifecycle-v1` directory, then invokes a
separate current-run checker. The local parity run reproduced the same
recorded closure-five behavior against a freshly produced generation. That
2026-08-02 snapshot bound app SHA-256
`478062e2dfe1e9b01b12723b66f167b91eb6d7b2b8123e2434acba7fced4922a`,
dSYM SHA-256
`e4c4fab2e4b9efe101ce1ccfb066634f5b5ebef0a2a78979513b5ade948df90d`,
source SHA-256
`b8a9f7822b88dddaaa843d25f976e1297736e6d2a4588e959d4c10c0cff65a7d`,
and UUID `6B06A6D0-9C89-3D36-A5B9-D2381598DDC8`. Its 7,628-byte result has SHA-256
`ed412cc97a1e03ba85cb79e8cece869983f1025ac58ab2dcb3ef925635bad32e`;
its 1,468-byte repeatability receipt has SHA-256
`a89428669bdd128130e1f8102fc39f10fa5bd801b3a4e80df1146ec48cdbbc75`.
These identities describe that recorded generation and are not pins for later
mutable current output.

The 24,212-byte current-run checker and 12,189-byte eight-test module have
SHA-256 values
`ce4f5244e70ad9c00755d18e18057e409aa54623740a243006eeb269ff3bfd3f`
and
`bc6e6e4694735cf218e21bda69f7776370f323063bf7e7fc914781083eb14d43`.
The checker imports no producer. It opens the complete current source,
checker-support, result/receipt, app, dSYM, ledger, and source-receipt graph
once through descriptor-relative no-follow directories, retains every file
descriptor, and derives every dynamic size and digest from those held
descriptors. It calculates the canonical 268-file source digest directly from
the held identities, requires exact equality with the generic build-output
report, source receipt, and lifecycle result, validates the repeatability
receipt, rechecks the source path tuple around the generic readback, and
finally reopens the complete graph. The regressions reject a coherently rebound
false source, same-byte inode replacement both during acquisition and after
snapshot, symlink, hardlink, wrong mode, oversize input, and path-closure drift.
The PR/main macOS lane also runs the offline current catalog check and the
exact 22-test release-compliance manifest with zero skips. Both implementations
reject unexpected or missing Android Gradle module locks, require an empty
Swift package dependency list with no `Package.resolved`, and cover 350 exact
Gradle coordinates, 379 retained POM records, two byte-identical renders of
the four-member compliance set, and independent reconstruction of the SPDX
2.3 document with 351 packages and 692 role relationships while rejecting any
render-time `urlopen`. This is deterministic SBOM/license-contract CI
coverage, not binary artifact analysis, a license-compatibility/legal
conclusion, vulnerability or secret scanning, signed provenance, canonical
Merge full, G6/G7 exit, RC/GA, or V1 qualification.

The exact 54-test workflow command, the product CI contract and mutation
self-test, and direct readback of that recorded local current-run evidence
pass. The
reviewed workflow is 18,819 bytes with raw SHA-256
`d63005795068446895e5cbf5e5ed05d9497282c698da7b86c2b96155815bdfe0`
and parsed-semantic SHA-256
`4cd318b9e42e97159910080e2b84a2ba8b19fe5b92ecb94c2a189f8a2bb72401`.
No hosted run of these current workflow bytes is claimed.

This is same-host, per-user, temporary-HOME, unsealed and network-denied
evidence after a fully observed, already persisted SQLite readback. It is not
an in-flight write, open transaction, power-loss, kernel-crash, OS-restart,
clean-machine or separate-account, Finder/quarantine/Gatekeeper,
TCC/Keychain/user-consent, Developer ID signing/notarization,
upgrade/rollback/N/N-1, device, provider, network, UI/accessibility,
production, canonical G6/G7 exit, RC/GA, or V1 qualification.
<!-- aetherlink-current-build24-macos-current-unsealed-install-recovery-v1:end -->

<!-- aetherlink-current-build24-reverse-version-readback-v1:start -->
**Latest current execution-source successor over the preserved
Build 24-to-23-to-24 archives.** Two
independent same-host executions used private snapshots of the exact local
ad-hoc Build 24 and historical Build 23 ZIP, manifest, and checksum sidecars.
Each execution installed Build 24 under one temporary per-user HOME, created
one fixed non-security Runtime-chat canary through the test-only fixture path,
removed the exact app, read the unchanged state with Build 23, removed that
exact app, and read the same state again with Build 24.

Every installed tree matched its archive manifest. The Build 23 tree contained
10 regular files totaling 21,153,014 bytes at SHA-256
`31209251804494f54a699c5c4e8101491f02fca881cf25fba379b88eb493d8a8`;
both Build 24 installations contained 10 regular files totaling 21,151,910
bytes at SHA-256
`0c1882e653ec32a3bf5795c9369dbee818b6890157fbaaebd81c60b8c1a59fff`.
No stale bundle file remained after either exact-path replacement. Each run
used three distinct owned LaunchServices processes and confirmed that each was
gone before continuing. The fixed canary remained exactly once, all three
SQLite files passed integrity checks, and every retained state-file byte and
mode remained unchanged through all three installations and removals.

The two executions produced the same canonical 7,859-byte result at
`dist/lifecycle/macos-packaged-app-build-24-to-23-to-24-isolated-reverse-version-readback-v1-current-source-g6-macos-current-unsealed-source-closure-four.json`,
SHA-256
`dbaa422de18ab37e9f4b92d7e78631fad9719e6c6d41fe30ccb402365267d416`.
The create-only 1,277-byte repeatability receipt is at
`dist/lifecycle/macos-packaged-app-build-24-to-23-to-24-isolated-reverse-version-readback-repeatability-v1-current-source-g6-macos-current-unsealed-source-closure-four.json`,
SHA-256
`b1f4d4fa2e661eab36ba32bb81676b50af95a7139f5c89cd66aac4173dcd4113`.
The result bytes exactly match the preceding `macos-release-byte-readback-three`,
`macos-release-byte-readback-two`, and `android-release-byte-readback-one`
successors and the original unsuffixed v1 observation; all five result files
and their receipts remain unchanged. After
normalizing only `canonicalResult.fileName`, each adjacent receipt pair is
identical; their respective 1,277-, 1,268-, 1,266-, 1,268-, and 1,216-byte
identities bind only the create-only canonical result filenames.
Publication records each link intent before linking, fsyncs payloads and the
existing physical parent, rejects symlink ancestors and non-owned or
non-0600 evidence targets, rolls back only exact owned inodes on every
`BaseException`, and performs final stable no-follow byte readback.

The 44,003-byte runner and 31,118-byte 14-test module have SHA-256 values
`e22a3e32e0556428f1d0274a75b4bbe93c5f5d28fe1a60607e1537a3db1771b1`
and
`41aadb2c9e2e961b9934ebac284df0a4f9b60f7b6fa4d02992b50775da47647b`.
The standalone 34,550-byte read-only checker and 19,819-byte 17-test module
have SHA-256 values
`e01d44ab40afe65cddcbfa16cca276f19c7ceac4b0a4922898055b7ec8d65166`
and
`356b8c443813e273f8ea883e44840b021e2b24d10e9d5cff4e6e2ce21845b0e3`.
The checker retains and revalidates all five generations and their ten
evidence descriptors, the exact ledger, both three-file archive snapshots,
and the ten-file direct execution-source closure, including the current
255,305-byte release-archive checker at SHA-256
`db5ba718e2623e16b2a235bb08f336ae03a22fbc8d86ba950c79ce45b9f7b850`.
It rejects canonical/type/schema, claim-boundary, source-membership,
archive, state, tree, receipt, file-replacement, and symlink-ancestor mutations.

This is a fixed-canary compatibility observation, not an updater, downgrade,
supported migration, declared production predecessor, arbitrary N/N-1
qualification, or product rollback. The result explicitly makes no production
predecessor, N/N-1, rollback, or security qualification claim; it also records
that security state was not inspected and no security evidence was produced.
It does not qualify signed/notarized distribution, DMG/Finder/Gatekeeper,
clean-machine or cross-host behavior, pairing, device, provider, network, UI,
production release, canonical G6 exit, or any G7 exit tier.
<!-- aetherlink-current-build24-reverse-version-readback-v1:end -->

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
limits, and pass flags. The evidence-era local-DMG runner is read from the
closed non-executable Build 24 source snapshot rather than rebound to its live
successor. Its 41,228-byte checker and 43,110-byte 27-test module
have SHA-256 values
`487317907ea2b377035a9b84488627bf4ce6887f06142d05245fb0c384a05392`
and
`cdf04f75832b63f8e8279afd6d7f84c6f11011ecc3a6be7e253054f009ed8811`.

This is one same-host, per-user, network-denied, point-in-time local idle
observation. It is not repeatability, load, performance-SLA, capacity,
long-soak, install, upgrade, recovery, rollback, device, provider, UI,
accessibility, production, or G7 Weekly resilience evidence. No signing or
signature verification was performed.
<!-- aetherlink-current-build24-macos-idle-resource-stability-v1:end -->

The current macOS G5 Runtime slice closes failed-start recovery. A listener
failure no longer latches the app into an already-started state; only an
advertising listener activates route allocation, relay startup, and restored
pair transports. Status exposes localized Start and Retry actions, and the
focused lifecycle, action, localization, and compact accessibility render
regressions pass. An accepted listener that fails later now releases local
advertisement ownership and clears the app model's started state for a
same-port retry; exact listener generations make superseded callbacks inert.
Connection admission validates and inserts under the same generation lock, and
listener failure retires that generation before publishing status.
This is deterministic no-device evidence, not live socket,
physical-device, signing, deployment, security, or production proof.

The current unreleased macOS G5 lifecycle slice now connects the same
`@StateObject` Runtime model to the AppKit delegate before requesting startup.
The delegate retains only the first weak Runtime lifecycle reference. Normal
negotiated termination enters through `applicationShouldTerminate`, begins
synchronous stop and request-admission closure, returns `.terminateLater`, and
replies exactly once after its drain or the five-second deadline. The drain
retires active and registration-racing requests, waits for already submitted
chat-title and memory-summary cancellation jobs, resolves deferred
memory-summary delivery acknowledgements before its persistence barrier, and
cancels and joins active Runtime chat-retention maintenance. A timeout permits
termination but does not prove a non-cooperative operation completed. The
direct `applicationWillTerminate` fallback remains synchronous `stop()` only.
Thirteen AppDelegate regressions and eight exact Router/model termination
regressions are included in the expanded 217/217 non-security product selector.
This is a current-source graceful-quit correction made after the immutable
Build 24 source snapshot; no Build 24 archive or lifecycle result is relabeled
as evidence for it. SIGKILL, power loss, arbitrary asynchronous work, device,
network, signing, security, and G7 completion remain unclaimed.

The current macOS G5 accessibility slice closes the explicit custom-animation
part of Reduce Motion. Status recovery scrolling and pairing QR expiry share
one system-driven policy; reduced mode removes the app transition while normal
mode retains the short 0.2-second animation. A force-on-only render override
cannot disable a true OS preference. Policy and reduced-motion Status/Pairing
render regressions pass. Physical assistive-technology traversal and an
observed OS-toggle session remain later G5 evidence.

The current macOS G5 accessibility slice closes deterministic contrast,
color-independence, focus, list-navigation, and QR-expiry gaps. Custom status
and warning surfaces use an Increase Contrast-aware light/dark palette and
stronger borders while warning text remains primary. Runtime History selection
always has a checkmark and uses one native arrow-key list rather than one Tab
stop per session. Status recovery and action-driven Pairing transitions carry
separate keyboard and accessibility focus targets. Pairing intents survive
asynchronous QR preparation, are consumed on success or terminal failure, and
are canceled when the screen is left. Menu-bar generation is owned by one main
`Window`, and locale-driven view recreation preserves a pending focus handoff.
QR expiry announces once per QR lifecycle without countdown spam, and
decorative Model Download icons are hidden from the accessibility tree.
Eight new policy/announcement/render regressions, the current exact 217-test product CI
selector, and the complete 186-test accessibility run pass. Physical keyboard
and VoiceOver traversal remain unclaimed because the Mac was locked during
attempted UI observation.

The current G7 repository-automation slice prepares a two-job non-security CI
subset. Pull requests run exact macOS and Android product allowlists, affected
compilation, the 78-test release archive contract, and strict-lock Android
Release APK/AAB assembly, lint, and direct output readback. Pushes to `main`
add the macOS Release product and the exact 19-class complete Android app unit
lane with pre-run source marker and post-run result binding/readback before the
same Release steps. Both triggers also run 54 clean-checkout-safe current-
unsealed lifecycle contract tests: 35 runner tests, 11 portable
evidence-checker snapshot/schema tests, and eight portable current-run checker
tests covering dynamic running-code CDHash binding, post-reap log revalidation,
held-source cross-binding, and acquisition-time same-byte replacement without
reading ignored local evidence. On `main`, the fresh unsealed package readback
is followed by the two-observation lifecycle producer and independent
current-run readback in a private `.build` directory.
The macOS job first requires the focused filter to resolve against the
current package list to an exact 217-test identity manifest. A self-testing
source guard pins the triggers, read-only permission, concurrency, runners,
toolchains, action majors, selectors, branch-specific ordering, result gates,
and excluded scopes. The macOS job uses `macos-26` with Xcode 26.6, matching the
current local toolchain; its semantic mutation tests run independently of the
complete-byte pin. Safe YAML parsing plus a canonical parsed-semantic
fingerprint closes the top-level/job mappings and complete step arrays; raw
checks close both job preambles and every named step body, and a Psych AST
pre-pass requires one document and rejects duplicate or explicitly tagged
mapping keys. The isolated product-copy mode is included in the macOS static
lane, followed by the tracked-only 36-document contract and its two bounded
mode tests; both return before ignored-evidence and paused mixed security
checks. The Android allowlist
directly executes the
changed-session scroll-boundary regression, the dedicated three-result
100/150/200% font-scale qualification, and the API 32/33/36 app-language
lifecycle class; the exact Android lane passes 45 tests
across an exact twelve-report set and testcase manifest with zero skips,
failures, or errors. Current local parity passes the 217-test Swift discovery
manifest and 217/217 execution plus the complete Android 1,226/1,226 binding
readback. The Swift run marker now snapshots only the 27 declared package
target roots (216 files), excludes sibling build outputs, and binds a validated
serial console only after exit zero; failure-path subprocess mutations preserve
the previous canonical log. The reviewed workflow SHA-256 is
`d63005795068446895e5cbf5e5ed05d9497282c698da7b86c2b96155815bdfe0`;
its parsed-semantic SHA-256 is
`4cd318b9e42e97159910080e2b84a2ba8b19fe5b92ecb94c2a189f8a2bb72401`.
Hosted run `30525374687` completed
both jobs successfully for baseline commit
`0f59c757d745d0b95c37c9b93aec8d354bcfef9f`. That historical 159-test baseline
predates commit `53f45d4e9909dd77520a450170eb87c7d260ea89` and does not
cover the current unstaged listener/Bonjour publication lifecycle,
advertisement-timeout, same-port retry, Swift selection preflight, complete
Android main lane, checker, or documentation follow-ups. This
does not complete canonical G7 `PR fast`, `Merge full`,
nightly, controlled network, resilience, RC, or GA tiers.

The current macOS G5 Runtime slice removes unrelated-provider catalog work from
provider-qualified operations. A small model-serving capability lets
`AggregatingLlmBackend` list one exact provider. Router chat resolution,
aggregate chat/embedding routing, and semantic embedding descriptor lookup use
that scoped path for qualified IDs, while unqualified chat preserves complete
aggregate discovery. Exact provider-model validation, selected-provider error
propagation, and cancellation normalization remain intact. Pre-fix regressions
observed the unwanted calls; the final 49 aggregate/residency tests, three
focused Router regressions, 2,093-test full Swift suite, Release product build,
and GPT-5.6 Sol re-review pass. The provider catalog copy-hygiene subguard now
pins the scoped protocol, aggregate filtering, both Router scoped
call/fallback pairs, exact call counts, and seven named regressions; the
subguard and all seven tests pass. The full mixed copy-hygiene command next
stops on two historical G2 documentation expectations inside the user-excluded
security scope, which remain untouched. This closes a deterministic
call-isolation gap, not measured latency, live-provider behavior,
physical-device evidence, signing, deployment, or production proof.

The current Android G5 UX slice closes a transcript-boundary scroll defect.
`ChatScreen` now observes `activeChatSessionId`, schedules one immediate
latest-row reset for a changed conversation, defers that reset while the
selected conversation is loading, and retains the pending reset across saved
state restoration. Same-session streaming updates still preserve an earlier
reading position and the jump-to-latest action. Latest assistant, user, and
overall message IDs are computed once per screen composition instead of inside
every composed row. The regression first failed against the old behavior, then
the focused checks, all 296 Compose screen tests, and the complete 1,195-test
app JVM suite passed. Android Release assembly and lint also pass with zero
errors and the two existing SDK-version warnings. This is no-device source and
build evidence, not physical rendering, measured frame time, signing,
deployment, or production proof.

The current unreleased performance slice completes the queued
`StrictJSONDocumentValidator` allocation reduction. The validator now borrows
the input `Data` inside one synchronous `withUnsafeBytes` scope, compares JSON
literals through their static UTF-8 buffers, and scans whitespace without an
array literal. It retains the existing `JSONDecoder` Unicode/string path and
128-level nesting policy. A differential corpus pins Foundation-compatible
syntax, AetherLink's stricter trailing-comma behavior, decoded duplicate keys,
canonical Unicode equality, malformed UTF-8/surrogates, literal-heavy input,
mixed 128/129 nesting, and non-zero-offset `Data` slices. BridgeProtocol passes
54/54, the focused AddressSanitizer run passes 3/3, the Release product target
builds, and the complete Swift suite passes 2,086 tests with 11 expected
opt-in/live skips and zero failures. This is source-level explicit-allocation
and no-device behavior evidence, not measured physical-device performance,
signing, deployment, or production-release evidence.

The previously queued Release-test fixture refactor is not active because the
affected accepted-endpoint types belong to the security and authorization
scope excluded by the user. It remains untouched and does not block the active
non-security quality lane.

Build 24 is the latest immutable local G6 package qualification record for its
qualification-time source snapshot. It retains Android backup/device-transfer
exclusions and
independently verifies both compiled APK policy bodies and the same bodies in
an AAB-derived universal APK. The
reproducible package-only Swift path now supplies
`-Xswiftc -num-threads -Xswiftc 1`. Separate comparison-only and
publish-qualified schema-v4 executions reproduced the same 166,345,274-byte
archive
with SHA-256
`104c07b6fc1b421bcc0309657001fdf991e37bb815c282b3e5112ed98821ab1c`.
The v4 comparison-only prepublication result is
`dist/reproducibility/aetherlink-1.0.0+24-local-v1-two-root-v4-prepublication.json`,
19,645 bytes with SHA-256
`64c21a8c345018e7fca552b1ff706ac5f9c1f19a349afb0090dae22466e9e3db`;
it did not publish. The v4 publish-qualified result is
`dist/reproducibility/aetherlink-1.0.0+24-local-v1-two-root-v4.json`,
20,353 bytes with SHA-256
`08a176bed8abe4f4c62178fa13a939059d127ee3dee4352096bcc593177cea36`.
It
exactly binds that prepublication result, proves the protected Build 23 archive
identity remained unchanged, then publishes and independently reads back the
exact Build 24 archive. This closes the current same-host package boundary,
not arbitrary cross-host reproducibility, clean-machine installation, signed
distribution, vendor backup/transfer behavior, or physical-device proof.
The release output is `dist/releases/aetherlink-1.0.0+24-local-v1/`. Current
readback is
`python3 -B script/check_release_artifact_archive.py --archive-dir dist/releases/aetherlink-1.0.0+24-local-v1`.

The current-source macOS G5 lifecycle slice makes system sleep/wake a
reversible Runtime transition without treating every wake as startup
authority. AppDelegate observes `NSWorkspace` sleep/wake notifications once.
Only a Runtime in `starting` or `advertising` state is stopped and leaves a
same-port resume intent; failed and stopped states leave no intent. Wake
consumes that intent once through the existing UI start and Bonjour publication
gate. Duplicate or reversed notifications, pre-sleep listener callbacks,
startup requested while already asleep, and termination during suspension are
closed by explicit state transitions. Eight AppDelegate tests, three direct
model sleep/wake regressions, and the existing model-stop and manager stop-all
regressions pass 13/13. The exact non-security product selector passes 217/217.
This is deterministic injected-notification evidence after immutable Build 24.
That sleep/wake slice does not itself observe a physical sleep cycle,
post-wake network readiness, provider restart, asynchronous persistence flush,
device, signing, security, G7, or release behavior.

The current-source macOS G5 provider-recovery slice now follows that lifecycle
without adding global polling. Runtime start and wake issue concurrent immediate
health checks. Only a provider observed as retryable-unavailable is retried
after 1, 2, 4, 8, 16, and then repeated 30-second delays; non-retryable and
available states stop the loop. Provider-scoped single-flight lets manual
refresh join existing work, and partial status merging prevents a slow provider
from delaying or overwriting another provider's row. Stop, sleep, Runtime
failure, and deinitialization cancel the monitor and rotate generation and
reservation identities so cancellation-resistant late responses are rejected.
Health calls use a five-second provider-only timeout, while ordinary catalog and
data operations retain their previous bounds. LM Studio's native and compatible
fallback probes share one total five-second health deadline. Recovery never
loads models, starts chat, or repeatedly checks a healthy unrelated provider,
and unchanged status does not produce retry log spam.

Eight recovery tests, one aggregate scoped-health test, and the Ollama and LM
Studio endpoint/health-timeout tests pass 11/11. The exact product selector
passes 217/217, and its contract independently rejects removal of each new
selector. This is deterministic current-source proof using injected provider,
backoff, and lifecycle seams. It postdates and does not relabel immutable Build
24; live provider processes, external networking, physical device or sleep
cycles, signing, security, G7 completion, deployment, and production release
remain outside this result.

Build 19 first source-binds a Runtime-chat SQLite cross-process quality slice.
Build 24 retains and extends those sources.
All production store connections install a 5-second SQLite busy timeout and
normalize busy/locked failures to one stable retry message. Three deterministic
Swift regressions cover wait-and-release success, `BEGIN` timeout rollback, and
`COMMIT` timeout rollback; the 90-test store suite and the complete 2,084-test
Swift suite pass with 11 expected opt-in/live skips. A separate no-device live
smoke ran two independent 48-event writers and a third independent readback
process, observing all 96 events exactly once with disjoint IDs, owner/session
isolation, per-writer order, SQLite integrity, `0700` directory mode, and
`0600` database-file mode. That live result is separate execution evidence,
not a retained archive member. Crash/power-loss, mixed old/new binaries,
arbitrary histories, clean-machine, signed/notarized, device, and production
behavior remain unqualified.

<!-- aetherlink-current-build21-abrupt-recovery-v1:start -->

Build 21 adds one canonical bounded same-host abrupt child-process recovery
result at
`dist/lifecycle/macos-runtime-chat-sqlite-abrupt-process-recovery-build-21-v1.json`.
Two identical executions produced the 2,223-byte result with SHA-256
`db66614d7badd7a0f606c03f91a516dff6d77e539684dcb6daf52709bce0f16f`.
The exact QA sequence commits 24 events through the production store, observes
one dirty uncommitted 25th event and FTS row after child-only `SIGKILL`, recovers to
24, then resumes through the production store to 48 contiguous exactly-once
events. This is bounded same-host abrupt child-process `SIGKILL` recovery
evidence and is explicitly `not-production-append-crash-point`, not power-loss
or kernel-crash evidence, not arbitrary-history or long-soak evidence, and not
clean-machine, signed-distribution, or physical-device evidence.

<!-- aetherlink-current-build21-abrupt-recovery-v1:end -->

<!-- aetherlink-historical-build20-lifecycle-v1:start -->

Build 20 historically closed its bounded same-host, per-user macOS
installation/relaunch and installed state-recovery gap. Two invocations of the
clean-HOME runner matched the 2,250-byte
`dist/lifecycle/macos-packaged-app-build-20-clean-home-install-v1.json`
result with SHA-256
`4ce047a318e47568d647e1167cbaeebc603626073e098451a29c949086aa3d72`.
Two invocations of the legacy-to-SQLite-to-SQLite-only recovery runner matched
the 3,364-byte
`dist/lifecycle/macos-packaged-app-build-20-clean-home-state-recovery-v1.json`
result with SHA-256
`d12947e16e7b985515a90a13731947a5991bcd82a06039210e22bba43535bf0b`.
The separate 2,434-byte ephemeral local-DMG result at
`dist/lifecycle/macos-packaged-app-build-20-local-dmg-install-v1.json` has
SHA-256
`e78b605278d5c5b7f5601778c38f35270f1db4a9e95055ff434b71af4c33cf78`.
It verifies one read-only fresh HFS+ mount, exact release-tree copy, pre-launch
unmount, two distinct installed launches, SQLite integrity, and stable state.
Both clean-HOME runners were invoked twice and matched their canonical results.
These historical same-host, per-user Build 20 observations do not qualify a clean
machine/account, signed/notarized distribution, UI/accessibility,
live-provider behavior, a physical device, arbitrary histories,
crash/power-loss, concurrent writers, backup/transfer, rollback, or production
readiness. The DMG run remains outside Finder UI, drag-and-drop, Gatekeeper
quarantine/download behavior, and system `/Applications` evidence. The
observations preserved PID 59809.

<!-- aetherlink-historical-build20-lifecycle-v1:end -->

The separate V3 observation path has now completed the unresolved five-locale
matrix without rewriting V2. The frozen V2 task, scorer, runner, schema-4
fixture, and failed result keep their exact bytes. V3 validates both complete
80-embedding maps, evaluates all 80 ranking and 80 repeatability comparisons,
and accumulates bounded locale/ordinal coordinates with per-batch failure
counts while structural or numeric errors remain fatal. Its opt-in live
assertion attempts unload on every primary outcome, requires a confirmed
unload transition after successful primary work, and performs final
catalog/health checks before one marker.

The live run exposed and fixed two V3-runner-only boundary defects: macOS
`/var` versus `/private/var` temporary-path canonicalization and a recovery
snapshot prefix outside the frozen recovery assertion's admitted namespace.
The V2 runner and evidence remain unchanged. Thirteen V3 Python tests now pin
the canonical path, recovery-prefix, and recorded-result boundaries; the eight
V3 Swift tests still pass with one opt-in live skip in an ordinary non-live
run. The canonical 3,570-byte
[`docs/evidence/ollama-embedding-multilingual-full-matrix-v3.json`](evidence/ollama-embedding-multilingual-full-matrix-v3.json)
result with `schemaVersion=5`
has SHA-256
`ca8279bafbe04a6de820caf1b855e4a2b6a09eb561602dd7773f1bfc190bda47`.
Both exact Ollama candidates pass 76 of 80 ranking comparisons and all 80
repeatability comparisons. Both record the same Korean and French scenario
ordinal 2 ranking misses, one comparison in each of the two batches, and both
pass fresh-provider recovery. `sourceStatePreserved=true`; no model was
downloaded or retained. The full matrix is therefore known, but
`qualityGatePassed=false` remains the correct product-quality result.

The current unreleased G5 product-quality slice adds bounded two-stage semantic
chat search. Retrieval query/document ranking remains primary; a transient
semantic-similarity pass considers only 8 through 32 available candidates
derived from the visible limit, excludes known research backing sessions, and
reorders only primary-score groups inside an inclusive 0.05 cosine window.
Scaled cosine keeps very large finite embeddings deterministic. Backend or
model/profile drift falls back to primary ranking, drift suppresses stale cache
writes, and a research-membership change before final publication also selects
the retained primary materialization. The final filter renumbers visible search
ranks from one. Sixteen focused checks, the 544-test broad router/search
regression, the current 2,084-test full Swift run with zero failures and 11
expected opt-in/live skips, and independent GPT-5.6 Sol review pass; the frozen
multilingual V2 result remains a separate failed model-quality observation, not
a passing claim. Its live runner rejects the changed router/fingerprint source
bytes; a future observation requires a new versioned binding rather than
rewriting V2.

<!-- aetherlink-current-android-drawer-search-ux-v2:start -->

The current unreleased Android drawer provides an explicit touch Search action
with localized accessibility semantics and the keyboard Search action through
one trimmed-query submission path. Blank, disconnected, streaming,
bulk-mutation, and exact same-query pending states expose localized action-state
descriptions without dispatching. Only the exact current pending query shows a
polite localized progress live region and suppresses the no-results row;
editing or clearing the query closes that request and invalidates its transient
search authority. Only an exact current-query remote response is adopted; stale
or absent response state falls back to immediate local filtering, while current
remote results exclude archived sessions and retain global Runtime rank. The
current no-device gate passes 168 AppNavigationTest cases, 22 navigation-drawer
Compose cases, 15 search-related RuntimeClientViewModelTest cases, and the
complete 1,194-test app JVM suite; release lint reports 0 errors and 2
SDK-version warnings.
This source/JVM/Compose evidence is not part of the immutable Build 17 archive and was first source-bound by the immutable Build 18 archive; Build 19 retains it. It does not establish physical touch, TalkBack, provider, device, network, installation, signing, or release behavior.

<!-- aetherlink-current-android-drawer-search-ux-v2:end -->

The current G5 accessibility slice closes the previously under-tested 200%
font-size ceiling for core Chat and Settings controls. Existing no-device
Compose regressions now exercise all five supported locales at font scale
`2.0`, with compact Chat and Settings viewports and a copy-hygiene guard against
future downgrades. Both focused tests pass. The full no-device gate and
physical-device visual checks remain unclaimed.

The next release-packaging gap is also closed locally: Android App Bundle
language splitting is disabled so all five supported translations remain
available to the existing in-app locale picker. The parity guard, offline lint,
and unsigned release-bundle build pass. Play-generated APK delivery and
physical-device locale switching remain unclaimed.

All 23 shared plural resources now follow each supported locale's Android/CLDR
categories. Exact category/placeholder shapes are statically pinned. Eight
terminal progress strings use typographic ellipses across all six resource
sets, and nine additional count-sensitive summaries select singular grammar;
three abbreviation or independent-multi-count strings use only targeted
per-resource lint ignores. A clean ten-test affected-path slice and independent
GPT-5.6 Sol review pass. `TypographyEllipsis`, `PluralsCandidate`,
`MissingQuantity`, and `UnusedQuantity` are all zero; physical rendering and
spoken plural output remain unclaimed.

Adaptive navigation now derives the 840dp permanent-rail breakpoint from the
actual Compose window container rather than device configuration width. The
typed `Dp` boundary and top-bar behavior pass focused tests. Physical
split-screen, freeform-window, and fold-state visual checks remain unclaimed.

Unchanged chat messages now retain their outer Markdown/fenced-code parse
results across unrelated recompositions. Parser and multilingual rendering/copy
regressions pass; streaming content changes still invalidate the cache.
Physical frame-time improvement remains unmeasured.

Android's disabled-animation setting now changes chat feedback behavior rather
than merely shortening framework animation time: streaming progress becomes a
static centered segment, and both automatic and user-requested latest-message
scrolling are immediate. Standard motion is unchanged. Policy and dual-mode
multilingual Compose regressions pass; physical accessibility-setting and
screen-reader checks remain unclaimed.

The first local G6 packaging defect is also closed: macOS package-only mode now
uses a Swift Release build and embeds the SwiftPM localization bundle under the
standard signed app resource directory. The app prefers that packaged bundle,
version metadata is present, and strict local ad-hoc verification passes
without launching the app. The append-only shared ledger now supplies the same
`1.0.0+24` metadata to the current isolated macOS and Android Release
qualification while Android Debug
remains `0.1.0+1` and builds without the ledger; the three consumers share a
strict LF-only byte boundary, monotonic guard, and semantic-regression guard.
Final distribution identity, Developer ID signing, notarization, signed DMG,
and clean-machine execution remain open G6 requirements. Intel macOS remains
Post-V1 and is not a G6 obligation.

Android G6 release optimization is now explicit as well. Release-only R8 code
shrinking/obfuscation and resource shrinking use the optimized Android defaults
and dependency consumer rules without a broad app keep file. A clean offline
APK/AAB/lint build passes. V1 Release is now `arm64-v8a`-only: the current
unsigned AAB is 10,677,978 bytes, contains one DEX, retains all five app locales
and five JNI libraries, and embeds the generated mapping byte-for-byte. The
ChromeOS x86_64
lint warning is narrowly excluded because ChromeOS is outside the V1 matrix.
Final application ID, production signing, Play-generated delivery, and physical
release launch remain open G6 requirements. The two remaining lint notices
require the locally unavailable SDK 37.

One canonical local release container now retains the unsigned APK/AAB, R8
outputs, dependency report, arm64 ad-hoc macOS app, and UUID-matched dSYM with
an exact 249-file source snapshot, external checksum, immutable publication,
and independent full readback. APK identity/version/SDK/ABI and the three
backup-policy fields are independently read with aapt2; compiled policy IDs
must resolve to `xml/backup_rules` and `xml/data_extraction_rules`. The builder
and separate readback verifier now each execute
AGP-pinned `bundletool 1.18.3 validate` with a 60-second timeout against their
own AAB bytes, require only the `base` module, and then directly confirm the
base manifest package, version code/name, minimum/target SDK,
`allowBackup=false`, `fullBackupContent=@xml/backup_rules`, and
`dataExtractionRules=@xml/data_extraction_rules`. Current
dependency JNI inputs are already stripped, so Android native symbols remain
explicitly unavailable rather than falsely complete. Build 5 introduced a
closed semantic normalization for R8 `resources.txt` and remains a valid
equal-length-root historical qualification. Build 6 retained that and the
other declared normalizations in its unequal-length-root qualification.
The current manifest records `worktreeState=dirty-content-snapshot`, source
SHA-256 `a01d37c3be608db3a8fa588b1ec019b673b5c57bc227ffc105047b3e4548f5f2`,
and the qualification-time source HEAD/`origin/main`
`7d72147528e334edb19b9331ed7933ac71ca424b`. The commit alone cannot
reconstruct the release bytes; the archived source inventory is the source
identity.
Build 24 uses the same 101- and 109-byte isolated lane roots, host, fixed
toolchains, paired clones of one byte-identical Gradle seed, canonical Swift
scratch policy, and frontend serialization. Two complete qualification
executions produced four builds with the exact same 166,345,274-byte ZIP,
15,200-byte manifest, checksum sidecar, and 30-entry archive inventory. The
latest immutable ledger archive is `aetherlink-1.0.0+24-local-v1`, and
independent current-source readback passes. The comparison-only execution did
not publish; the separate publish-qualified execution exactly bound its
prepublication result, protected the prior Build 23 archive, published lane A,
and independently read it back.
Builds 1 through 23 remain separately readable historical archives. The
verifier cross-binds each Gradle lock identity to the archived source inventory
and rejects current releases in historical mode. This proves only the two
recorded successful same-host pairs; it does not establish variance-free
arbitrary repetition, arbitrary roots, cross-host, signed-release,
clean-machine, or physical-device G6 qualification.

Build 24 retains the qualification-time source-bound AAB structure-validation
evidence and the settled two-stage reranker. Build 18 first bound the Android
drawer search release inputs, which Builds 19 through 24 retain. It
also binds the Research Notebook permanent-delete confirmation's atomic
saved-state target, trusted-Runtime/notebook/session rebind checks, unresolved
catalog tolerance, and authoritative invalidation regressions. The complete
Android app gate passes 1,195 tests with zero failures and release lint reports
0 errors and 2 SDK 37 availability warnings. Build 24 additionally binds the
exact backup/cloud/device-transfer exclusion resources, APK/AAB manifest
readback, and compiled XML body readback.

Build 16 remains a historical non-transfer record. One execution successfully
published its archive, while a preceding attempt and later confirmation
observed the same two Swift executable/dSYM variants with reversed lane
assignment. Neither variant is canonical repeatability evidence, and Build 17
does not retroactively qualify Build 16.

Historical Build 14 has same-host, per-user clean-HOME installation evidence.
The exact archive app was copied with `ditto` to a temporary
`Applications/AetherLink.app`; its ten regular files, modes, hashes, metadata,
ad-hoc seal, and tree digest matched the manifest. Two absolute-path
LaunchServices launches reached regular AppKit activation, completed
five-second observations, used distinct process identifiers, and accepted
identity-bound termination. All three initialized SQLite files returned
`integrityCheck=ok`, Runtime-chat remained empty, and isolated state
regular-file bytes and modes did not change across relaunch. The canonical
2,250-byte result SHA-256 is
`dba559878af78be5057b50f4fb5a759e0308724f93b6c358ce2c5e6981d7f6c2`.
The pre-existing PID 59809 stayed at its original Build 4 path and was never
selected or terminated. This closes a local installation/relaunch rehearsal,
not clean-machine/account, DMG/Finder install, signed/notarized distribution,
UI/accessibility traversal, live-provider, or physical-device qualification.

Historical Build 14 also has a separate installed state-recovery qualification on the
same bounded path. A first exact-path LaunchServices process migrated the fixed
legacy JSONL canary to one exact Runtime-chat SQLite row. After termination and
legacy removal, a distinct second process recovered the same row using
SQLite-only state. Both auxiliary databases passed integrity checks; the
installed app tree and all remaining state-file bytes and modes stayed
unchanged. The immutable 3,364-byte result at
`dist/lifecycle/macos-packaged-app-build-14-clean-home-state-recovery-v1.json`
has SHA-256
`434cec7c2fd396a56788abdcfa48edd913950331cedf91159a11f8acc02f657d`
and was reproduced byte-for-byte by a second complete invocation. This is
frozen Build 14 evidence and is not reinterpreted as Build 17. It closes the
bounded Build 14 legacy-to-SQLite installed relaunch gap, but not
arbitrary-history, crash/power-loss, concurrent-writer, clean-machine/account,
DMG/Finder, UI/accessibility, provider, signed-distribution, or
physical-device qualification.

Historical Build 13's packaged state-recovery result observes one fixed benign legacy JSONL event
through production-store migration and model projection, terminates that
process, removes the legacy source, and observes the same exact single SQLite
row from a second independent packaged process. Both SQLite checks report
`integrityCheck=ok`; the legacy source stays absent and the row stays unchanged.
Build 12's marker-file attempt failed closed and published no state-recovery
result, so Build 13 evidence does not transfer backward or forward to Build 14;
Build 14's historical observation is independently bound to Build 14 and does
not transfer to Build 17, Build 18, or Build 19.
Arbitrary histories,
crash/power-loss recovery, concurrent old/new writers, UI correctness,
listener/provider readiness, clean-machine behavior, and physical-device
behavior remain unqualified.

Build 19 preserves the exact-role local G6 package-inventory slice introduced by
Build 8. The frozen
catalog covers 350 unique Maven coordinates from the six Gradle locks, 379 POM
byte identities, parsed POM-declared license names and URLs, and zero external
SwiftPM packages. Compliance profile
`aetherlink-release-compliance-v2` with `schemaVersion=2` emits 692 exact role
relationships: 202 runtime, 155 build dependency, and 335 build tool. Two
hundred packages have more than one role. Release generation is offline; the
separate verifier reconstructs the SPDX and text bytes, cross-binds
lock/source/member identities, and rejects catalog or relationship mutations.
Original POM bodies and license/NOTICE texts are not archived, and the offline
checker does not re-fetch or re-parse those originals. Every third-party
`licenseConcluded` remains `NOASSERTION`; attribution completeness,
binary-artifact analysis, and license compatibility remain unclaimed. Build 7
is preserved under its frozen profile-less V1 interpretation, whose 350
one-per-package relationships compressed additional roles for 200 multi-role
packages. Security analysis is excluded from this active lane.

A historical post-publication Build 10 macOS lifecycle slice remains locally
qualified only for Build 10. Its frozen versioned runner fixes the exact
Build 10 ZIP, manifest, executable, and macOS UUID; at qualification time it
used then-current-source archive readback, extracted the packaged app into a
temporary root, and completed two AppKit finished-launch, minimum five-second
observation, and identity-rechecked exact-PID termination cycles with zero
exits. Its QA-only sandbox preflight permits a temporary-root write while
denying a non-temporary write and AF_INET bind. The exact 1,313-byte result
SHA-256 is
`c0ea4dba08e74130f7aaa1e9855121d02459249ff5e6a0fc27cd1b01f46f0ded`.
The exact Build 9 runner, test, and 1,311-byte historical result remain
unchanged; the latter retains SHA-256
`aad796ee3c768e37953f18eeea0e6642107750c3a8c398df798a46e96aabab53`.
This closes only a bounded local packaged-process launch/relaunch gap. The
observed Application Support file presence does not prove second-run readback,
and the absent identity file leaves identity persistence and state recovery
unqualified. Installation, UI correctness, listener/provider readiness,
clean-machine behavior, signed distribution, and physical-device lifecycle
remain open. These observations remain bound to Build 10 and are not
reinterpreted as Build 14 evidence. PID 59809 stayed alive at the same path with executable SHA-256
`93cb550903f74e5018514870d1f4e7ac95ffc5df915fb8bde48c1ff512b382d0`;
its existing main bundle is Build 4, not Build 10.

Release-scoped dependency locking is now closed for the current checkout. Six
generated Gradle locks cover settings, buildscript, and clean Release-resolved
configurations; two byte-identical writers and two strict read-only clean
Release readers passed without lock mutation. The manifest explicitly excludes
only `org.jetbrains.kotlin:kotlin-stdlib-common`, whose configuration membership
Gradle 9.4.1 did not persist consistently, while its parent
`kotlin-stdlib:2.3.21` remains locked. SwiftPM reports zero external
dependencies, so no `Package.resolved` is required. Debug, test, androidTest,
clean-machine, and cross-machine dependency resolution remain unclaimed. The
versioned release notes/compatibility/migration/known-limitations/support/
privacy/rollback pack is now consolidated in
`docs/releases/1.0.0-build-19-local-v1.md`. It explicitly labels the current
container as a local qualification candidate rather than a production release.
`docs/releases/1.0.0-build-1-local-v1.md` retains the superseded build 1
identity, and `docs/releases/1.0.0-build-2-local-v1.md` retains the superseded
build 2 identity. Builds 3 through 5 are also historical; the fixture-rich
`docs/releases/1.0.0-build-3-local-v1.md` remains the immutable source for the
recorded provider and first-lineage transition fixtures, build 4 records the
diagnostic publication before the first qualified two-root run, and build 5
retains the superseded equal-length two-root qualification. Build 6 retains
its superseded archive and packaged-app lifecycle evidence, but the exact
17,674-byte two-root result JSON is no longer retained; only its historical
size and SHA-256 remain in the written record. Build 7 retains the superseded
profile-less compliance V1 qualification, and Build 8 retains the superseded
first exact-role compliance V2 qualification.
Build 9 retains the historical role-aware embedding source qualification and
its separate packaged-app lifecycle evidence.
Build 10 retains the historical reranker/drawer qualification and its separate
packaged-app lifecycle evidence.
Build 11 retains the first dual AAB-structure-validation qualification. Build
12 retains its successful archive/reproducibility identity and failed-closed,
non-published marker-file state-recovery attempt.
Build 15 retains the first APK/AAB backup-policy manifest qualification. Build
16 retains one successful publication and two failed repetition observations;
neither is reinterpreted as Build 17 evidence.
The Build 3 fixture document embeds one canonical first-lineage transition fixture:
there is no production predecessor, N/N-1 remains unproven, both development
baselines require clean install plus fresh pairing, and no state migration or
in-place upgrade is claimed. The checker cross-validates it against the current
ledger and the G0 version/identity/migration/compatibility fields. A second
canonical fixture now records the 2026-07-29 provider baseline: Ollama
`0.32.5`/`0.32.4` and LM Studio `0.4.20` build 1/`0.4.19` build 2 are the
official current/previous candidates, while local schema smoke covered Ollama
`0.32.4` and LM Studio `0.4.17-beta+3`. SHA-256-verified official Darwin
archives for both exact Ollama candidates now pass the AetherLink adapter's
health and empty-catalog checks after cold start and process restart, and their
endpoints close after stop. The versioned runner hash-verifies, isolates,
executes, bounds, and cleans the entire four-run matrix without touching the
installed app or default port. Its explicit model-backed mode also selects one
already-installed, unloaded completion-capable model without retaining its
name, verifies the selected blob bytes against their content-addressed SHA-256
digests, snapshots only its exact manifest and 2,138 blobs through copy-on-write,
and runs both exact candidates after cold start and restart. All four
model-backed runs pass populated-catalog, bounded streamed completion,
first-delta cancellation, post-cancel recovery, confirmed unload,
installed-state preservation, health, byte-identical SHA-256 snapshot state,
and stopped-endpoint checks without a model download. The source provider
version, observed catalog `name`/`digest`/`size` projection, running-model
identity set, and every selected source-file byte remain unchanged; unselected
model-store bytes and unprojected catalog metadata are outside the comparison.
The dedicated additional-shape runner also fixes the second of three installed
completion-capable candidates to its exact snapshot and
`completion`/`thinking`/`tools` capability tuple, requires it to be initially
unloaded, and never falls back. Its 991 blobs, 213,712-byte manifest, and
16,679,502,421 model-artifact bytes passed both exact versions after cold start
and restart: all four chat, cancellation, recovery, unload, snapshot, and
endpoint observations passed while the observed source catalog/capabilities,
running set, selected bytes, and bound source files remained unchanged. The
runner attempted no model download and retained no model name, prompt, output,
path, process identifier, or base URL. The runner's separate
embedding-backed profile applies the same exact archive, observed-source,
copy-on-write, and non-retention boundaries to the smallest
already-installed unloaded embedding-capable model. Its four-blob,
621,875,917-byte snapshot plus 741-byte manifest passed another four exact
cold-start/restart runs covering a two-input finite equal-dimension embedding
batch, provider residency, confirmed unload, installed-state preservation,
snapshot integrity, health, and stopped-endpoint unavailability without
retaining a model name, input, or vector value. A separate semantic-quality
mode now passes both exact candidates against four fixed English ranking
scenarios: two 16-text permutations, a 200-basis-point positive margin against
both negatives in every scenario, 9,990-basis-point repeatability for every
logical text, and one fresh-provider embedding recovery per version. Each
phase must execute exactly one matching XCTest, while the canonical result
binds the semantic scorer and live assertion sources by SHA-256 and retains
task-set identity, thresholds, counts, and booleans only. This does not
generalize beyond that one local model and task set.

A separate multilingual V2 task set preserves the passing English V1 record
while predeclaring four within-locale scenarios each for `en`, `ko`, `ja`,
`zh-CN`, and `fr`, using the same 200-basis-point positive-margin and
9,990-basis-point repeatability thresholds. The runtime now preserves explicit
retrieval-query, retrieval-document, and semantic-similarity roles through
aggregate routing; the Ollama adapter maps a recognized embedding profile to
its role prompts, rejects malformed profile metadata, reserves bounded prefix
headroom, and advances persistent cache identity before reuse. On both exact
Ollama candidates, both role-aware 80-text batches completed with valid shapes
and all four English rankings passed, but Korean scenario ordinal 2 still
failed the positive-margin check. Japanese, Simplified Chinese, French, and
repeatability were not evaluated after that fail-closed result. The task set
and thresholds were not weakened after observation. Both versions then passed
a fresh ordinary embedding recovery with confirmed unload and unchanged
source/task/snapshot bindings. The schema-4 canonical failure record binds the
request contract, adapter implementation, aggregate role preservation, runtime
role assignment, and profile-bound semantic fingerprint, and retains only the
failed locale and ordinal—no model name, task text or ID, vector, dimension,
score, or provider output. Its runner accepts the expected failure only from one bounded
regular UTF-8 log with exactly one matching XCTest start/failure and one closed
locale/ordinal diagnostic; cleanup errors cannot be converted into a quality
observation. Multilingual qualification remains open.

A third vision-backed profile
requires vision plus chat/completion capability and copy-on-write snapshots the
smallest matching unloaded model as 997 verified blobs totaling
21,909,210,142 bytes plus one 207,279-byte manifest. Its four exact
cold-start/restart runs pass non-empty text chat, a fixed 32 by 32 PNG
attachment, first-delta cancellation, post-cancel recovery, residency,
confirmed unload, installed-state preservation, snapshot integrity, health, and
stopped-endpoint unavailability without retaining the model name, prompt, image,
or output. An opt-in duration path now uses the same `time.monotonic_ns` clock
for deadline enforcement and measurement, with a 20-second absolute
process-start/readiness budget, one 10-second stop budget, and the existing
300-second focused-adapter timeout. One dated local run passed all 12
profile/version/cold-restart observations: provider-ready was at most 5,533ms,
adapter execution at most 54,784ms, and stop at most 3ms. Phase total includes
snapshot rehash and final endpoint readback without a release threshold. The
SHA-256-pinned exact values are single-host observations, not an SLA, average,
percentile, throughput, or cross-host qualification. Deterministic mocked
failure regressions also prove provider stop plus snapshot recheck after an
adapter exception,
Popen/stop/snapshot-error precedence, temporary-root cleanup before post-failure
source readback, and rejection of provider-version, catalog-projection,
running-set, or selected-file drift. A separate live mode then exercised
unavailability before request, process-group termination after the first
non-empty chat delta, and forced termination after `SIGSTOP` against both exact
versions. All six fault observations and six full adapter/unload recovery runs
passed with process-group reap, endpoint shutdown, snapshot integrity, and
source projection/byte preservation. It also drove the product fix that maps
terminal-less stream EOF to fixed retryable `ollama_transport_error`. This
live evidence does not cover power loss, OS crash, cleanup-permission failure,
embedding/vision faults, concurrency, soak, or an SLA. The focused backend
suites pass 148 of 157 executed tests with nine opt-in skips. Exact LM Studio
candidate
execution remains deferred because the
official tools expose no independent user-data/model-store path for a
non-invasive run. Minimum versions, a passing multilingual semantic-quality
result, retrieval accuracy, further model-shape coverage, and complete
candidate qualification remain unclaimed.

Android Compose API and primitive-state cleanup now removes 15 release-lint
issues without changing UI behavior. An independent GPT-5.6 Sol audit confirms
all 197 affected calls use named arguments; 22 focused clean no-device tests
pass, and all three targeted issue IDs remain absent. After the later localized
resource cleanup, current release lint is at 0 errors, 3 warnings, and 0 hints.
Fifty unused keys per resource set, legacy API-25 launcher PNGs, three KTX
findings, and the locale-config attribute warning are gone. Adaptive standard
and round icons now include a generated monochrome layer. Physical interaction,
launcher rendering, and frame-time improvement remain unclaimed.

### Current G2 Rung-Three Dependency Fixed-Point Waves

Rung two consumed its exact one-use source request and retained the verified
archive without extraction. Rung-three v1 and v2 then consumed their distinct
permits and failed closed before publication; those failed/consumed histories
remain retained and cannot be retried. A separate v3 one-use execution completed
the bounded lexical candidate inventory and independent tracked readback. Its
predecessor status was `rung3_v3_publication_read_back_complete`, with
`recordedNextActionAtThatCheckpoint=prepare_separate_versioned_rung3_semantic_source_review_decision`.
The tracked
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
bind exact readback. The 76,685-byte result has SHA-256
`ef4b8d88ec57501377a7bc9db066c04a1a379041ee1b11999f5d16c7d4447933`;
the 2,458-byte manifest has SHA-256
`2dace9b59b7374423754f1f9a7345eda76db9130728d1c0579797e5a0c829055`.
The inventory covers 100 Go files, 1,077,591 source bytes, and 39,064 logical
lines. Seven patch units and 19 lexical rules found 4,701 hits, represented as
144 recorded locations at no more than eight per rule plus 4,557 omissions. All
129 entries carry creator system 0 metadata with accepted DOS attributes `00`
and synthetic read-only mode `100444`.

That v3 result remains historical lexical candidate-location evidence. Semantic-
review v1 has since completed two non-attesting full-coverage passes over all
100 Go source bodies and all 4,701 observations, with source classes 52/44/4.
The 29 candidates deduplicate exactly to 19 findings: P0=0, P1=11, P2=3,
P3=4, none=1; patch_required=7 and unresolved=12. Disagreements remain
unresolved and the `one-use` zero-hit remains a missing-required-mechanism gap.
The independent tracked-only checker and 25/25 mutation tests hold all eight
file descriptors plus every repository-path directory component through two
stable full-set readback passes and a final identity barrier, validate the
manifest last, and observe the failure file plus four staging names absent
before and after readback.
`semanticSourceReviewPerformed=true`, while `semanticClosureComplete=false`,
`dependencyClosureComplete=false`, `rungThreeComplete=false`,
`candidateSelected=false`, and `librarySelected=false`. Semantic review was
performed, but semantic closure, dependency closure, rung-three completion,
candidate selection, and library selection remain false. The checker does not
independently reproduce semantic judgments or source-based location bounds.
Same-UID concurrent mutation is not prevented, and absence is not guaranteed
after the final observation. No source body, individual line digest, absolute
path, or credential/secret value is published. No extraction, materialization,
dependency installation,
reviewed-source compilation/execution, socket, network, device, deployment, or
Git operation occurred. Repository-owner authentication, external identity
proof, execution-permit authentication or documents, and user action remain
outside this local workflow.

The historical preparation-only
[patch/dependency decision v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/patch-and-dependency-closure-decision-v1.json)
and [security-hardening portfolio](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/patch-and-dependency-closure-decision-v1/hardening.md)
record `status=prepared_options_unselected_dependency_closure_blocked`,
`result=four_structural_recommendations_and_eight_unselected_treatment_units_prepared_all_19_findings_remain_open`,
and
`recordedNextActionAtThatCheckpoint=prepare_separate_versioned_implementation_or_dependency_review_decision`.
All 19 canonical findings remain open. Seven unselected root patch units and
one unselected dependency source/license/security review unit are mapped; four structural
options are conditionally recommended, not chosen. The read-only checker and
28/28 checker tests verify the exact predecessor, archive, dependency seed,
complete 19-file portfolio, selection, authority, and closure boundaries, and
reject unexpected artifacts, reader-facing effect drift, and replace-after-read
drift. No implementation plan or patch series exists. Dependency acquisition,
compile, socket, network, device, deployment, and Git write remain
unauthorized. `externalAuthenticationRequired=false` and
`userActionRequired=false`.

The historical
[implementation-or-dependency review decision v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/implementation-or-dependency-review-decision-v1.json)
and
[staged fixed-point review plan](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/implementation-or-dependency-review-decision-v1/implementation/staged-fixed-point-source-closure.md)
record
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
complete 19-file portfolio bundle, and review plan; they assert distinct raw,
selection, authority, finding, closure, contract, sequence, plan, inventory,
filesystem, and TOCTOU failure layers. All 19 findings remain open.
Dependency acquisition, source modification or extraction, package management,
compilation, source load or execution, sockets, network, device, deployment,
Git writes, external authentication, and user action remain unauthorized or
unrequired.

The predecessor
[bounded dependency source-identity and acquisition decision v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-v1.json)
and
[reader contract](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-v1.md)
record
`status=wave1_source_identity_and_request_contract_prepared_acquisition_not_authorized`,
`result=exact_19_root_requirement_source_identities_and_bounded_wave1_request_contract_prepared`,
and
`nextAction=prepare_separate_versioned_wave1_execution_permit_after_checker_runner_and_tests`.
They bind the exact 19 root requirements from the retained Pion root `go.mod`,
derive their dependency H1 identities from the exact embedded root `go.sum`,
quarantine four checksum-only context tuples, and freeze Android arm64 and
macOS arm64 V1 graph profiles plus strict graph, request, byte, path, and
filesystem bounds. A later wave is predeclared as exactly 19 public-proxy ZIP
requests and 19 new outputs, but that contract is preparation only:
`sourceAcquisitionAllowed=false`, `networkIoAllowed=false`, and observed
request/output counts remain zero. Direct dependency SumDB inclusion proof,
owner/commit attestation, dependency closure, source extraction or execution,
compile, socket, device, deployment, and Git work are not claimed. The
read-only checker and 56/56 mutation tests pass. It rehashes the retained root
ZIP, embedded module metadata, and source tree, proves all premature wave
artifacts absent through the final barrier, and fixes exact H1 and ordered
source-set digest algorithms. All 19 findings remain open and
`userActionRequired=false`.

The historical successor
[bounded dependency wave-one execution permit v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-execution-permit-v1.json)
and [reader contract](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-execution-permit-v1.md)
recorded before execution
`status=wave1_dependency_source_acquisition_authorized_not_consumed`,
`result=exact_19_public_proxy_zip_requests_authorized_once_not_executed`,
and `recordedNextActionAtThatCheckpoint=execute_bound_dependency_source_wave1_once`.
The runner still passes 44/44 tests. The permit suite recorded 38/38 only at
the unconsumed checkpoint; the current gate reruns 36 state-independent cases
because the v1 claim and failure receipt prove it is consumed and cannot be
retried.

The historical
[wave-one recovery decision v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-recovery-decision-v1.json)
and [reader contract](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-recovery-decision-v1.md)
recorded `E_ZIP_RATIO` on ordered tuple two after two response bodies, one fully
validated/staged tuple, zero accepted artifacts, and no final set. The 30/30
recovery mutation tests bind this terminal state and select non-gating
exact-integer compression telemetry while retaining all absolute
streaming/deadline bounds. The refreshed 31/31 suite also catches late v1
namespace insertion. At that checkpoint the decision recorded
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
The permit is now consumed and cannot be retried. Its claim and failure receipt
record `E_GO_MOD_MISSING` on tuple 11 after 11 completed ZIP responses, 10
validated/staged tuples, zero accepted artifacts, and no final set.

The predecessor
[wave-one recovery decision v2](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-recovery-decision-v2.json)
and [reader contract](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-recovery-decision-v2.md)
record
`status=wave1_v2_failure_read_back_recovery_v3_design_selected_execution_not_authorized`,
`result=v2_conflated_zip_and_mod_resources_tuple11_after_eleven_responses_no_final_set_v3_zip_plus_mod_policy_selected`,
and
`recordedNextActionAtThatCheckpoint=prepare_separate_v3_runner_checker_tests_and_execution_permit`.
The checker and 39/39 mutation tests preserve the terminal evidence and select
a fresh 19-pair `.mod`-then-`.zip` design. That preparation action is complete.

The historical
[wave-one execution permit v3](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-execution-permit-v3.json)
and [reader contract](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-execution-permit-v3.md)
recorded, before execution,
`status=wave1_v3_dependency_source_acquisition_authorized_not_consumed`,
`result=exact_19_public_proxy_mod_then_zip_pairs_v3_authorized_once_not_executed`,
and `nextAction=execute_bound_dependency_source_wave1_v3_once`. The reader
contract's exact bytes remain permit-bound. The permit is consumed and cannot
be retried. The immutable
[success receipt](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-receipt-v3.json)
and [manifest](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-manifest-v3.json)
record `status=acquired_pending_independent_readback`,
`result=fresh_exact_19_dependency_zip_mod_pairs_acquired_and_hash_verified`,
38 request attempts, 38 completed bodies, and 38 accepted resources across 19
exact `.mod`/`.zip` pairs. The
[readback receipt](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-readback-v1.json)
and [manifest](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-readback-manifest-v1.json)
validate `status=independent_readback_complete`, 43 regular files, and the same
38 resources. The permit-bound 34/34 reader tests remain immutable; a versioned
recovery reader recorded the outputs once, and the
[fixed-hash post-verification decision v3](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-readback-post-verification-decision-v3.json)
plus its verification-only 9/9 suite close the raw-encoding, dispatch, TOCTOU,
and typed-comparison gaps with
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
The read-only checker and 37/37 offline regression checks bind the exact 15 versioned
frontier rows, their introducing parent declarations, and all 30 ordered
`.mod`/`.zip` H1 expectations from non-conflicting already-held `go.sum`
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
checks. Those are historical permit facts, not the current execution state.
Its versioned recovery path reached the successful v3 intake: the tracked
wave2 v3 receipt retained 30 exact `.mod`/`.zip` resources and the independent
readback reopened and H1-verified all 30. Wave3 then classified a 16-tuple
frontier, completed all 32 H1 identities, consumed its separate one-use
acquisition permit, retained 32 resources, and completed independent readback.

Combined-v2 held 101 source inputs (the root ZIP plus 50 `.mod` and 50
dependency ZIP files), reconstructed the graph twice, and recorded
`fixedPointReached=false` with an exact 16-tuple Wave4 frontier: three
graph-selected vertices and thirteen retained version-specific vertices. The
[Wave4 identity/acquisition decision v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave4-v1.json)
and
[reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave4-v1.md)
derive, twice and without network, 22 parent declarations, 24 module-ZIP H1
witnesses, and 26 `go.mod` H1 witnesses. All 16 tuples have one conflict-free
H1 pair. The decision fixes the ordered 32-request future contract and passes
11/11 focused tests, but keeps acquisition, extraction, source execution,
compilation, runtime/product network, Git, device, and deployment closed.
The separate
[Wave4 one-use acquisition permit v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave4-execution-permit-v1.json)
and
[reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave4-execution-permit-v1.md)
bound that exact contract and was consumed once. Attempt
`4cda3d86462fff445d6e69bce4b92dec` retained all 32 resources
(16 `.mod`, 16 ZIP; 24,118,812 bytes), and the separate
[Wave4 independent readback](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave4-readback-v1.json)
reopened and independently verified the exact bytes twice before its
[manifest](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave4-readback-manifest-v1.json)
was written last.

The current combined-v3 read-only checker holds 133 source inputs (the root ZIP
plus 66 `.mod` and 66 dependency ZIP files), reconstructs the graph twice, and
records `fixedPointReached=false` with an exact 15-tuple Wave5 frontier. Its
input-set SHA-256 is
`b2d981dae1576f27ae5cd292e218b0a0eb35f5bdc0d98734fb1b350408ce4eca`,
graph SHA-256 is
`ee330142d77874457cccf78d5a9fe51652c81916f1d7aabb390f321dff51e03a`,
and its focused suite passes 23/23, including exact-byte reproduction and
Wave4 predecessor, attempt, H1, order, selection, and resource-mutation
failures. The separate Wave5 candidate checker retains all 15
version-specific vertices even though every
`selectedByGraphAlgorithm` value is false, and passes 10/10 focused tests.
The
[Wave5 identity/acquisition decision v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave5-v1.json)
and
[reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave5-v1.md)
reproduce 20 parent declarations, 20 module-ZIP H1 witnesses, and 22
`go.mod` H1 witnesses in two identical offline scans. All 15 identity pairs
are complete and conflict-free. The compact identity SHA-256 is
`52567cdead3fcd8029f9c1676a7f83af86a5d0110c52851b47e55b2f09af8a7d`,
the full witness SHA-256 is
`af51e067ccf3388561bfe0e2b38dae744792625cdc5f7a37b55208b41d4a5fb4`,
and the focused decision suite passes 11/11. At that checkpoint the decision
prepared 30 ordered, distinct `.mod`/`.zip` requests without authorizing
acquisition. The separate
[Wave5 one-use acquisition permit v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave5-execution-permit-v1.json)
and
[reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave5-execution-permit-v1.md)
were then consumed exactly once. Acquisition attempt
`ed050bd13835ab1f9fecc0dd3cfb6e12` retained all 30 resources
(15 `.mod`, 15 ZIP; 26,123,889 bytes) without extraction, loading,
execution, or compilation. The separate
[Wave5 retained-snapshot readback](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave5-readback-v1.json)
recomputed the raw hashes, H1 values, ZIP safety shape, root `go.mod` parity,
and aggregate counts twice before its
[manifest](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave5-readback-manifest-v1.json)
was written last. Readback attempt
`8f3813a784359883b4d93370c9041809` applies completion only to the retained
snapshot: current-path identity is not guaranteed through manifest publication,
and same-UID replacement after the final pre-manifest barrier is not prevented.
The current combined-v4 read-only checker now holds the exact 163 inputs
(root ZIP, 81 `.mod`, 81 dependency ZIP) and reconstructs the graph twice
after executing the pinned v3 predecessor. Its combined input-set SHA-256 is
`b7eca5385fd0cf811d0eb7e8a00fe467bf64f8c10fa1ab998521f00510b0b8b2`;
the module graph/frontier SHA-256 is
`a27185f3136ee694ba5e5e4d89d4eb985055b5c1d0599e826842169625d8c2e6`.
It records 100 module nodes, 247 module edges, and
`fixedPointReached=false` with an exact 18-tuple frontier whose canonical
SHA-256 is
`a966326a38b3050ac6ad7387405d359488b049d86982cde27946008dd258a6ce`.
All 18 frontier tuples are retained version-specific vertices with
`selectedByGraphAlgorithm=false`; the selected package graph remains 132
nodes and 1,047 edges with no unresolved or unmapped import. Its 17/17 focused
tests include deeply rebound Wave5 H1, order, and selector mutations. The
[Wave6 identity/acquisition decision v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave6-v1.json)
and
[reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave6-v1.md)
then resolve all 18 conflict-free H1 pairs from 18 parent declarations, 18
module-ZIP witnesses, and 25 `go.mod` witnesses. The exact lexical frontier
order is preserved, every selector remains false, and the canonical 36-request
`.mod`-then-`.zip` contract has SHA-256
`d1ea9ec1fab702b1bf405f13e1d7aaeb9a5354ff7f98a0d916870def124372a1`.
The decision checker records 400 graph-lineage archive opens plus 164
identity-witness opens, 564 total, and its 10/10 candidate plus 12/12 decision
suites pass. At that checkpoint it authorized no acquisition. The separate
[Wave6 one-use acquisition permit](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave6-execution-permit-v1.json)
was later consumed exactly once. Acquisition attempt
`5e0828c2e5dc1ce7ef2a06dd235d5076` retained all 36 resources
(18 `.mod`, 18 ZIP; 36,115,415 bytes) without extraction, loading, execution,
or compilation. The separate
[Wave6 retained-snapshot readback](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave6-readback-v1.json)
verified all 36 resources twice, including 7,758 ZIP entries and
138,523,078 uncompressed bytes, before its
[manifest](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave6-readback-manifest-v1.json)
was written last. Readback attempt
`7fc50276e880013e1ace73920397ba3f` produced receipt raw SHA-256
`6234799bbfbc608bdb5938adb36eaeaa85b5fb111b927873e825ed63947349e7`
and manifest raw SHA-256
`fe98535d35f7059a18e31d73a2e50fefefe92952bc4eece49623decea2068227`.
Completion applies only to the retained snapshot. The separate read-only
combined-v5 checker now holds the exact 199 inputs (root ZIP, 99 `.mod`, 99
dependency ZIP) and reconstructs the graph twice through four recursively
hardened predecessor-checker loads and four read-only provider-facade loads.
Its combined input-set SHA-256 is
`06acb9e5395898abb1827761436b8c4b5d983d87d242eaf20622e352d0180c63`;
the graph SHA-256 is
`4b424c41fbc8fa09c5bc9f91a880f14309cb409785991cfb872bb2475d94e8fe`.
It derives `fixedPointReached=false` and an exact 15-tuple next frontier whose
canonical SHA-256 is
`1c226bfc244970e071ad2bf09d6e356cd9d42e7b542cd0cf1582fc2fdc4d9b8a`.
The final focused suite passes 25/25. The trusted pinned normal path records
zero file writes; this is not an OS syscall sandbox. The separate
[Wave7 identity/acquisition decision v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave7-v1.json)
and
[reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave7-v1.md)
now resolve all 15 conflict-free H1 pairs from 18 parent declarations, 41
`go.mod` witnesses, and 20 module-ZIP witnesses. Every selector remains false.
The canonical 30-request `.mod`-then-`.zip` contract has SHA-256
`8fbabe69d049992e28c687852686ae0ad28adce690443d61e335c903b87d0f48`;
the decision content SHA-256 is
`dc771927a4cf8b6a8713f42c0716e98f242fdf7c277cddf0dadfe666bb02614f`,
and its raw SHA-256 is
`4214aa1b0eb624ca17d3579e74be0cbb8d897027689e8dd1340d073601e28022`.
The optimized decision suite passes 13/13 in 358.677 seconds with one full
reconstruction, and an independent GPT-5.6 Sol static re-audit reports no
P0-P3 finding. Identity is complete and acquisition-ready, but this decision
grants no acquisition. The separate
[Wave7 one-use acquisition permit](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave7-execution-permit-v1.json)
and
[reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave7-execution-permit-v1.md)
were prepared at `status=authorized_not_consumed`. The permit raw SHA-256 is
`1d15cb97e1ac04b4a99258ed876a0b84f71dcb9cc588f9bce5c9aaa1ba0b7a60`
and its content SHA-256 is
`62339ae44907c1c28174fa55b0e5f99c95a20e10181148d30d8702288f8d940a`.
The checker passes 13/13 and the offline fake-I/O runner suite passes 36/36.
Independent GPT-5.6 Sol re-audit reports no P0-P3 finding after four
claim/teardown uncertainty findings were corrected. The permit was then
consumed exactly once. Acquisition attempt
`c15f4504ae880326144eca93dc91e37b` retained all 30 resources
(15 `.mod`, 15 ZIP; 32,352,251 response bytes) without extraction, loading,
execution, or compilation. Its receipt raw SHA-256 is
`bd7f2db9500c8f8c0dc67737804d1a0ab62f722f1dacfc4b92fad48414b8a778`;
its manifest raw SHA-256 is
`0af9c0adaaa5fb2bc71fed14f457be76b014fcc234ca0805a63d0bc31da9a559`.
The separate
[Wave7 readback permit](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave7-readback-execution-permit-v1.json)
and
[reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave7-readback-execution-permit-v1.md)
bind an exact 48-file frozen snapshot. Permit raw SHA-256 is
`2d86fc8bf926340867ed92e0ecd62cdae827675f269df45bec489b0c39576a00`
and content SHA-256 is
`c57bb30921ee6cff79ca5d7e5c52d0d2341e893302230a7c6014f51aabf1a433`.
Its checker passes 16/16, its recorder suite passes 45/45, and independent
GPT-5.6 Sol audit reports no P0-P3 finding. Offline readback attempt
`1839537589935de087068a5a7d5c7e14` verified all 30 retained resources twice,
completed all three pre-manifest retained-FD barriers, and wrote the
[readback manifest](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave7-readback-manifest-v1.json)
last. The
[readback receipt](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave7-readback-v1.json)
has raw SHA-256
`2153ef62af2dabf89467e481a35c2f50467fca37d422e70d549b9fc6d3377ba3`;
the manifest has raw SHA-256
`cb1e22055ccfde532f85842d7fd485f5b661ad4ae152f34f6247affc621a1482`.
Completion applies to the retained snapshot. The separate read-only
combined-v6 checker now holds the exact 229 source inputs (root ZIP, 114
`.mod`, 114 dependency ZIP), 45 terminal controls, and one auxiliary Wave7
evidence file. It reconstructs the graph twice and derives
`fixedPointReached=false` with an exact 14-tuple Wave8 frontier. The combined
input-set SHA-256 is
`f7ad0b43d571da61edd4941f8e504d54d014b01f3395aeca8d0d10b9b3c22349`;
the graph SHA-256 is
`3648bdf037e316e69e155615edd5748c2bb653238579216ddd8b8dce4beb9f09`;
the frontier canonical SHA-256 is
`d3c3788d6a1144bf04ea2c68e6aa4b9fdd17859bc625e2c2c51019bb3c61ff92`;
and the candidate content SHA-256 is
`b33ef7a10de32dc99cea1dbbbcab1dac3a549eb466ef80b0229d2a0381ab9052`.
The final focused suite passes 25/25 in 514.493 seconds, and an independent
GPT-5.6 Sol re-audit reports no P0-P3 finding. The checker records 230 direct
plus 600 inherited archive opens, ten total full-source reconstructions, zero
extraction/load/execution/compile/network/file-write operations, and
`route=next_wave_required`. The separate
[Wave8 identity/acquisition decision v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave8-v1.json)
and
[reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave8-v1.md)
then resolve all 14 exact version-specific tuples from 14 parent declarations,
93 `.mod` H1 witnesses, and 15 module-ZIP H1 witnesses. No tuple is blocked or
conflicting, and all selectors remain false. The canonical 28-request
`.mod`-then-`.zip` contract has SHA-256
`b0f0f887864ddc4cf3ab15319a9e89dbea8c84087fa3d0e374a0332240336ddc`;
the decision content SHA-256 is
`1e1d62f03fe3137a88aa9413be8310bf7260f65a4825a09baab9a848ce6969da`,
and its raw SHA-256 is
`45236a2ea42a4a3af59e60d27ed2f09cd5d191e34a6db992a9d81cb49316297e`.
The focused suite passes 18/18 in 512.113 seconds, and independent GPT-5.6 Sol
audit reports no P0-P3 finding. Identity is acquisition-ready, but the
decision grants no acquisition and by itself materializes no permit. The
separate
[Wave8 one-use acquisition permit v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave8-execution-permit-v1.json)
and
[reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave8-execution-permit-v1.md)
were prepared at `status=authorized_not_consumed` and then consumed exactly
once. The permit binds exactly 14 tuples and 28 ordered `.mod`/`.zip` requests,
resource canonical SHA-256
`ee32b0512643b0e767f5b1e96625352fc47ea6ae7aea5d7366adfe98f4db8136`,
content SHA-256
`527a4558d069b31f92256926ea90e05c8353a33f65128b131d1c960614df925b`,
and raw SHA-256
`8595241898ebc14d563f5b03c3a4b46afdd995207bc1597d86c861e5c37bcb4c`.
Its checker passes 15/15 and its network-free mock/local runner suite passes
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
The read-only combined-v7 checker then holds the exact 257 source inputs
(root ZIP, 128 `.mod`, 128 dependency ZIP), 52 terminal controls, all three
Wave8 acquisition/evidence/readback auxiliaries, and six direct tool inputs.
It recomputes the graph twice and derives `fixedPointReached=false` with an
exact ten-tuple Wave9 frontier. The combined input-set SHA-256 is
`d389c84ae3b6d2d3d7dbb38d7003711972a75db3a558b9d6e0d79856249ef528`;
the graph SHA-256 is
`c7889fbf06a01e08ba75150b85bb2cb2860ea71ce205cead432cf0a37e0d89b9`;
the frontier canonical SHA-256 is
`03058e3aea23aca0c6208dd0023361f90421d394272f212d80bf61d587baff4e`;
and the candidate content SHA-256 is
`c71188f8d648a0f020a164002644f825e018f4c01b56d90e57011e05cc2e5202`.
The checker raw and normalized SHA-256 values are
`7264d85e1948bc8f86e8238192663706e7bf7472153d37fe812bd118620e99c7`
and
`cf4fd9d25efe04c2ecb3eea882bb24d6c40b02f2f258c4ab01d824d1373d1c02`.
It records 258 direct plus 830 inherited archive opens, twelve total
full-source reconstructions, and zero extraction, source load/execution,
compile, subprocess, network, or file-write operations. The strengthened
focused suite passes 28/28 in 716.223 seconds, and the final independent
GPT-5.6 Sol re-audit reports no P0-P3 finding. It live-checks the seven Wave8
terminal files and exact final/accepted inventories before and after
reconstruction while describing the 46-file readback set only as a historical
descriptor-set binding. It does not claim continuous current-path identity
after the last barrier.
The separate read-only
[Wave9 identity/acquisition decision](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave9-v1.json)
then reopens and reads all 257 inputs twice, reproduces the identity scan
twice, and resolves all ten exact frontier tuples with zero blocked or
conflicting identity. It binds 11 parent declarations, 73 `go.mod` H1
witnesses, 11 module-ZIP H1 witnesses, compact identity SHA-256
`db31bdd4d1ae0c97ba88094502f7c0dc5e0f554e72c5f68503d917005f762753`,
and the exact 20-request set at SHA-256
`e3922164eda6657d447f1b75ff49268265338efe35440dad39a237d1ddf643bc`.
The canonical decision raw/content SHA-256 values are
`21ca43d44a67aec62b65a86fa44c43726eaa81fa277e07550f105e8c3b33bca8`
and
`340966e22b9759e2c1abd106e0cd9d9e9afa47b89ae3bb3929bfa6302dda18ae`.
The disk checker passes, and the focused suite passes 19/19 in 890.601
seconds. The checker verifies the clean Wave9 namespace twice while stating
that this is a point-in-time observation, not a reservation. Every selector
and acquisition authority remains false.
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
loading/execution, or compilation. The acquisition claim, receipt, and
manifest raw SHA-256 values are
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
Its checker and recorder suites pass 16/16 and 45/45. Two independent
GPT-5.6 Sol pre-execution audits found no P0-P3 issue. Offline readback attempt
`2d61a0483984e9a2f77665dd3c624cb2` independently verified all twenty
resources twice, completed all three retained-FD publication barriers, and
wrote the manifest last. The readback claim, receipt, and manifest raw SHA-256
values are
`af0dab21e05292511bb105545750a61048f9d4b23e7ec7b9e7e1de5f1e7e41a7`,
`0e1816a43e2b7d8210dd90fb7349ea63637abbe830da0badc81105a03f0e439f`,
and
`7cd427780a29dc85b6ae59188c7ee2601939dbdca0393362824a2509f5878b7e`.
An independent byte readback revalidated canonical JSON, content bindings,
cross-file raw hashes, exact counts, and the zero-network/zero-authentication
counters. Completion applies to the retained snapshot at the final
pre-manifest barrier; it does not claim continuous current-path identity.
The read-only combined-v8 checker now holds the exact 277 source inputs
(root ZIP, 138 `.mod`, 138 dependency ZIP), 59 terminal controls, all three
Wave9 acquisition/evidence/readback auxiliaries, and seven direct tool inputs.
It reconstructs the graph twice and derives `fixedPointReached=false` with an
exact eleven-tuple Wave10 frontier. The combined input-set SHA-256 is
`030743c3959a6e7466385e9f89255fcb03d65576676a1e5cd7e5e2929e9f6339`;
the graph SHA-256 is
`721d045a10cdf015e865a84db7026115ac63462217dbb5349504fed9f1bae7b7`;
the frontier canonical SHA-256 is
`780501bca37fbeb953590004ca7e5aad7f206083f749b920e2a9842b63675f82`;
and the candidate content SHA-256 is
`f9f683d3afbe65a77626577428c0f9ce94219e39529d0c5811b49172c51e3b37`.
The checker raw and normalized SHA-256 values are
`798a055a9a4c3957c0edd75ecbad35f0cfa9f17bf39e63cd262876dcb6103e32`
and
`cfd83cdd00b6daee857cbff915ec48fd78390bbf06098ccab963a54e8748ba4b`.
It records 278 direct plus 1,088 inherited archive opens, fourteen total
full-source reconstructions, four exact pinned legacy-build compatibility
applications, and zero extraction, source load/execution, compile, subprocess,
network, or file-write operations. V7 test bytes are explicitly historical
metadata, not a live-held V8 tool input. The final checker exits zero. The full
suite passes 29/29 in 969.215 seconds; the final two audit-requested assertions
then pass AST, 23/23 fast checks, and direct test 29. Final independent
GPT-5.6 Sol audit reports no P0-P3 finding.
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
GPT-5.6 Sol final-byte audits report no P0-P3 finding.

The separate
[Wave11 one-use acquisition permit](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave11-execution-permit-v1.json)
and
[reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave11-execution-permit-v1.md)
are now consumed. The permit raw/content SHA-256 values are
`9d8d2aa4d5be23575ef42aecf3fd2dffb37a1af56e86a208bc85a63f167f342e`
and
`54886d2f90038608b21169806cc59dfad4038a0901031c1e7a514107ede5fe82`.
The checker, checker-test, runner, runner-test, and reader raw SHA-256 values
are
`72c6709e51dff3753f7ca92b2a64bcb6ed3057573798e05c829184f627b8fd87`,
`77ea295e4c8c1b60854cfec0170655a22c0b7f5ced09324bedda9805e18a1ac2`,
`ca6849f3ca9a47c4bb3f1e1efe477dd24e21419895fdc7ce738bbe41737b55a0`,
`79ae96707650e63dfcc73e8825e53ceb51283069b9958bf3af0949681b684aca`,
and
`0941c3e5132eacd386a90f5b2064d256bd1c3ca1f63b52fc8f4e69d900645a55`.
The checker and runner suites pass 17/17 and 46/46, and three independent
GPT-5.6 Sol final-byte audits report no P0-P3 finding. Acquisition attempt
`ac18b8fda0a80a132510efd5dd17d5b7` retained all 18 exact resources
(9 `.mod`, 9 ZIP; 16,363,894 bytes), including 3,329 ZIP entries and
64,428,507 uncompressed bytes. The acquisition claim, evidence, receipt, and
manifest raw SHA-256 values are
`a41663bd827b8f07e0e04e887b21a7306c0ba286396e43d854ea3f2369a3e985`,
`c4194219b35723fb61ee41fca23a10ffe5f2c18f01f82fb70856a404019fb797`,
`0c35d330476362fdaba23192229d8aa0fa096c0f47fddb39955f8976db6115a8`,
and
`ac247bed91f7cbe50c90d8a640b885ca1adaa2888fa8447f6ea0baeb4a046a15`.

The separate
[Wave11 readback permit](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave11-readback-execution-permit-v1.json),
[reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave11-readback-execution-permit-v1.md),
[receipt](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave11-readback-v1.json),
and
[manifest](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave11-readback-manifest-v1.json)
are also complete. The permit raw/content SHA-256 values are
`9ea9f661983668efc648bae0d854e225dfd04252b41fef0782dbd7e4a628408b`
and
`7300bdf634e665b9493609b5554e9cf239098d78d852456907698116297e9eed`.
The reader, checker, checker-test, recorder, and recorder-test raw SHA-256
values are
`911ebf509d9943efd6a73ac9105255df2690b813b1aa97c41aca09ff0eb293d4`,
`895fad76d8563ebd57d7f8ca31d8cb44d15724414550d1eb1bc22c4f3d4cc124`,
`3b8dc394bc59da6b613848b6f9f20dde3fcf4fe9fc996f73ccd5e0a94e7b7bb5`,
`5917493ad7506ce214a4df545b2326673d535969d2455cf310a019aff0a2e1d3`,
and
`c32893bb1473d102e27fa19db150839c80683f24932b48affb56da1ed58f8179`.
The checker and recorder suites pass 17/17 and 50/50. Three independent final
GPT-5.6 Sol audits report no P0-P3 finding after the exact-schema and mutation
hardening. Offline readback attempt `9b4dac65f66ce9e5d53dcd8edaf4d1d4`
verified the exact 36-file retained snapshot twice, completed all three
pre-manifest retained-FD barriers, and wrote the manifest last. The readback
claim, receipt, and manifest raw SHA-256 values are
`752c0fdc006688a4c22dc26f54be1c9bb4498e9a94f196217aebfaff8e61dc13`,
`f89904b359aed770e89ed8de25b775d6b920d7eef3d32bdc464a486a862cc5ca`,
and
`0bda6e5da9609ddd375e20a6692a4cec46aaf930acee4861c5168efde1f18c0e`.
An independent raw-byte process revalidated all four canonical JSON/content
bindings, their cross-pins, and all 18 resource hashes and byte counts. Both
one-use actions are consumed and cannot be retried. Completion applies only to
the retained snapshot at the final pre-manifest barrier.

The separately versioned read-only combined-v10 successor is now complete. The
[checker](../script/check_p2p_nat_g2_pion_combined_fixed_point_v10.py) held the
exact 317 source inputs (root ZIP, 158 `.mod`, 158 dependency ZIP), 73 terminal
controls, three Wave11 auxiliaries, nine direct tool inputs, and eleven
transitive tool paths. It reconstructed the complete source graph twice across
159 archives, 59,494 entries, and 1,098,221,637 uncompressed bytes. The
combined input-set, compact source-binding, graph, frontier, and candidate
content SHA-256 values are
`f946c625334ac8cf42d42c9f45f0f051eb7f89fb9ecf5dfc576114b1cba990be`,
`067808934056712884a75ea669d61189bb5d5d722d2a961c8b8c5d25345bb75c`,
`77813f467c7452290f35c4ecaa6a1041a0988d563ea37660bb6cc902bb95cdc4`,
`8b84bd2fd9201d33f4424b9dd1018aee7f8470a87306c2ba23eba0c8b6d4ff05`,
and
`d7feddd3b291756c36359b013ea05aaa2f25cb83605daaeb493c0395ff9cc4f7`.
The exact ordered frontier is `golang.org/x/crypto@v0.41.0`,
`golang.org/x/term@v0.34.0`, `golang.org/x/text@v0.28.0`, and
`golang.org/x/tools@v0.35.0`. Every row remains
`selectedByGraphAlgorithm=false`, `acquisitionAuthorized=false`, and
`requiresSeparateWaveDecision=true`; therefore
`fixedPointReached=false` and the route is `next_wave_required`.

The checker raw/normalized and current
[test](../script/test_p2p_nat_g2_pion_combined_fixed_point_v10.py) raw SHA-256
values are
`11d0c2743f92d59a8417870db279edeb6a1b6c0a1af9db577e5cec4c50350985`,
`ccb5430b1c41e5fcd39e00b7345ba285a427b1b25d48c299f81f1be8ca25f751`,
and
`ab00dbe4d70fbfc596ee6553e2d87f94f75370f07ff38b93d5c5fb5652bfac35`.
The pre-audit 23-test suite passed 23/23 in 1,438.484 seconds. A subsequent
test-only audit hardening independently pins both checker hashes, drives
invalid selector types through all three selector-bearing projections to
`E_WAVE11_RESOURCE`, and proves the aggregate-uncompressed ceiling rejects
`limit - 1`; the two changed focused boundaries pass, and an independent
GPT-5.6 Sol re-audit reports no P0-P3 finding. A full 24-test rerun of that
test-only successor is still pending. The verified run records 18 total
source reconstructions, 318 direct plus 1,666 inherited archive opens, 36
graph-algorithm invocations, nine hardened-module checks, and nine provider
loads. Extraction, source loading/execution, compilation, subprocess,
product/runtime network, and file-write counters remain zero.

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
The run records 18 cumulative full-source reconstructions, 1,984 graph archive
opens, 318 identity-witness archive opens, and 2,302 overall archive opens.
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
load/execution/compile, Git, or user-action authority. The separate exact-eight
Wave13 permit package is now materialized at raw SHA-256
`b976f9bea30a20e34df25e9d90cfa9ee4617ce825b0d28f254b5bb512b6c29a1`
and passes 18/18 checker plus 48/48 fake/local network-denied runner tests.
Acquisition attempt `eb05816e0b897ea8c3ad8b7089668e91` consumed that permit
exactly once and retained all 8 resources: 411 `.mod` bytes, 5,097,127 ZIP
bytes, 5,097,538 accepted bytes, 1,647 ZIP entries, and 20,065,482
ZIP-uncompressed bytes. The accepted hash-set canonical SHA-256 is
`bcb43e80159d68f179c24e87f1f8d439bb1c387d713b9a3aec0ac932f9a6ee92`;
acquisition receipt and manifest raw SHA-256 values are
`b85a242f11255a82a8422adfda8cfe86113bd47bd9920c69fafb69985895c514`
and
`6d33bb51108da1f8e010f23ff6abfdd5eb62b398db0fd048e2a50576b7cbfa12`.

The separate
[Wave13 offline readback permit](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave13-readback-execution-permit-v1.json)
and [reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave13-readback-execution-permit-v1.md)
bind the exact 27-file frozen snapshot at canonical SHA-256
`a99b35472a140330847b1ff7e746a83dc060707ea63af3ef22d165a4f2ced11d`.
Permit raw/content SHA-256 values are
`f6e1ed89709cb2c15640c051a74ce1ab4e549c635ced30d6621489a7559225d5`
and
`db9b97fce13b46fa0ebb5c774054b88237c8bab7b4ff729d5fcbe7e8d82f5481`;
its checker and recorder suites pass 17/17 and 50/50 after Wave12-drift
mutation hardening, and three independent GPT-5.6 Sol audits report no P0-P3
finding. Offline readback attempt `8b5f92c9d90f825f5f3b46df0d006ef3`
independently verified the retained snapshot twice, completed all three
pre-manifest retained-FD barriers, and wrote the manifest last. Readback claim,
receipt, and manifest raw SHA-256 values are
`11c1e04dfde8be7d7728f32912154870dc1e0305d0bbb61f1ff4167304bc5274`,
`eb5ac65c8e8dbe186d7f79d292642029f08d35241dd157a610351b5b5b7de62f`,
and
`cdb07a858e11e3c5709210794d84a793dd81d5b32ba3867b750f1e8a27369628`.
Both Wave13 one-use actions are consumed successes and cannot be retried.
No identity proof, credential, authentication, network access, or user action
was required. Extraction, source loading/execution, compilation, runtime
sockets, product networking, deployment, and Git writes remain closed.

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
full normal-path suite passes 24/24 in 1,996.811 seconds. This result opens
only preparation of a separate verification-only Wave14 identity/acquisition
decision; it does not authorize acquisition, network access, extraction,
source loading/execution/compilation, Git writes, authentication, or user
action.

That preparation action is now complete. The separate
[Wave14 identity/acquisition decision v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave14-v1.json)
and
[reader](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave14-v1.md)
revalidate the exact 333-input retained set and classify all four frontier
tuples as complete from four parent declarations, four `go.mod` H1 witnesses,
and four module-ZIP H1 witnesses, with zero blocked or conflicting identities.
The compact/full witness SHA-256 values are
`a59b37276b85f5da5cbf2c39a560c7834582cf1f590e050d53e016ed80fb6185`
and
`cf39e4c68e001b3d687df829e7d7903d4ebea69b11ee60f21d5385f9591fa542`;
the canonical eight-request SHA-256 is
`505587c90ec32b1dea879b1e034450de091874a2ff9db9993532f1b14d9dc3aa`.
Decision raw/content SHA-256 values are
`14d6debddca620af7f628198f7a7ae2d9291adc35a6fffbe13873d3fd75dc28f`
and
`cb4201b1d0e6fd4ae2275cf5a58ceedd0ca14e33cb6af4269e798f1115f37450`.
Its checker-normalized, test-raw, and reader-raw SHA-256 values are
`274cdb31412fcf56079f65a5ffd9c28a3267380846de12ff2910a8bd12885639`,
`155fed39113bb3a40e085efde1517409fba22a98e175094cee9edeefd7f380b3`,
and
`0d909c39aaf81a90c51803ad28839828e6b1df2060e7c347c34bdecda7587cce`.
The latest observed local full-suite run passes 27/27 in 2,030.976 seconds,
including canonical disk readback and adversarial mutation coverage; that
duration is execution observation, not a package-attested receipt.

The separate Wave14 one-use acquisition permit passed 18/18 checker and 48/48
fake/local network-denied runner tests. Its raw/content SHA-256 values are
`867e1541606f67404f5066cfb6fe8f5265422024e4aec6e9c5e44db755b7fe49`
and
`60ac6693cc83c06efa1a913ed3a0cdbb7941efa4d58313e2a4919774efb79787`.
Acquisition attempt `7fef20e6c3931b698f32b2a71f8a596a` consumed that permit
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
without itself authorizing acquisition.

The separate Wave15 one-use acquisition permit passed 18/18 checker and 48/48
fake/local network-denied runner tests. Its raw/content SHA-256 values are
`c123dd1d9bd1a3cf6901246efcd545fae3b43e301504ed9144ce96c4010f0396`
and
`d18a0990e266b7df23f56772403def11361c576ec319a5f0ed9340f5a0937641`.
Acquisition attempt `c5db51cfd9a295b448927cca36d1ea07` consumed the permit
exactly once, retained all ten resources without extraction, and recorded
5,065,246 accepted bytes at accepted hash-set SHA-256
`9255922769ca442cdc555467158bd4a1c1399398d4ee1f5ced42a677b35f140d`.
The separately sealed offline readback permit passed 17/17 checker and 50/50
recorder tests. Its raw/content SHA-256 values are
`0fdeaf4d105d920e7b0cd62b6fb8f5151b6489d3d7de26d1ce0ab1f3b6924f76`
and
`0e554d5291faceb54f13395767fed58d9fa2b4365e5a4a4108d3fe54fa927f07`;
readback attempt `fb2b53eb42982732b0344695065c625d` verified the exact
29-file snapshot at canonical SHA-256
`b7df25872029064c136ab99be564cd2013fef7047ecb9588175909f3b31951d8`
twice, completed all three retained-FD barriers, and published the manifest
last. Both Wave15 one-use actions are consumed successes and cannot be
retried.

The read-only combined-v14 checker then held the exact 351-input retained set
and reconstructed it twice. Input-set, source-binding, candidate-content,
graph, and exact-frontier SHA-256 values are
`c62222562f7a248398aa8677c5c4b81c41a74f3b48dbae7a1da54eea887f9d7d`,
`a360afdc5d94502f53f5e393503198bb7ce6adf4d21a0c64245a1b7e49be9eae`,
`e77b120d6e367e03beb847eb36cbf64b37d32fe00539b029ae809310818d5b9c`,
`7458344c93152bea86360d2742456a28ebfc6849994bf68db30214611f020798`,
and
`5544db5bdf34f4afadce7d91f7c56998988e68810ed96b454048bf62dc07c452`.
It derives `fixedPointReached=false`, `route=next_wave_required`, and three
exact non-selected Wave16 tuples: `golang.org/x/crypto@v0.39.0`,
`golang.org/x/term@v0.32.0`, and `golang.org/x/text@v0.26.0`. Cumulative
accounting is 26 full reconstructions and 3,338 graph archive opens over 176
archives, 67,904 entries, and 1,250,144,441 uncompressed bytes. Checker
raw/normalized and tests raw SHA-256 values are
`bf729f8dbfc0508fa977893eb1c7c30e07d15fa751a29856d4c4d386f1001292`,
`8be3cf62cc66c2aaf780c658acf5b6e242fcbd52e44dd6fd90a11e3eeba505ec`,
and
`17adc7ea0f75eff26108187bb50a2f250655f0e190f5b51cbe1f5ea9c57896e3`.
The exact full suite passes 23/23 in 2,441.948 seconds and the post-seal fast
suite passes 2/2. A separate single-pass readback reproduced the same graph
SHA-256 and exact frontier in 132.721 seconds.

The separate verification-only Wave16 decision is sealed at content SHA-256
`0fa5d649f856ce9c04a3e3e14165c488eb5d467bbb2507c54cb6bc60ad989273`
and raw SHA-256
`ad76fbed203302ff915df56b62d655011c50a9c5d17f868bf0eb7dd752c97be6`.
Its two exact retained-input metadata scans reproduce three declarations,
three go.mod H1 witnesses, three ZIP H1 witnesses, three complete identity
pairs, and zero blocked or conflicting pairs. It passes 27/27 tests in
2,432.458 seconds and binds the six-request set at SHA-256
`b26cb50ac5070782744dec5a5c05f0cb07512ee421d69c52c6400946a28bd627`.

The separate Wave16 one-use acquisition permit passed 18/18 checker and 48/48
fake/local network-denied runner tests. Its raw/content SHA-256 values are
`2fbbadf5808ca2cef8b3b9a04eceb24b98c0970a0f25b876d7f88dcfeab74dc5`
and
`1b009e4ae50e86bce96c8cd9062e95b9ea9d908380f9ca238ac4f37958a6bb0c`.
Acquisition attempt `fff8d6073748eab6fd1a05c79c57a84f` consumed the permit
exactly once and retained all six resources without extraction: 452 `.mod`
bytes plus 11,475,192 ZIP bytes, 11,475,644 bytes total, 948 ZIP entries, and
46,464,212 ZIP-uncompressed bytes. The accepted hash-set SHA-256 is
`f80997e5ef21d4b556667abc2fa016785bcd234dc7a79dc028f70c7d35a36159`.
The separately sealed offline readback permit passed 17/17 checker and 50/50
recorder tests. Its raw/content SHA-256 values are
`21914901195f2e83436ddb9aefad79137a86cc48afb22146176ff44ad1aa2aee`
and
`a7460624779ec3b50e39623df3d4154e38557cb65c22f2ee17632789e97419ba`;
readback attempt `e7c555246489b1ccd63bf3aca3e27c2f` independently verified
the exact 25-file snapshot at canonical SHA-256
`b8863a58dd5db814afe94eb101c166e4f5bfb92d9b8197dbe3e32a3b1f0e99c4`
twice, completed all three retained-FD barriers, and published the manifest
last. Both Wave16 one-use actions are consumed successes and cannot be
retried.

The read-only Combined V15 checker then held the exact 357-input retained set
and reconstructed it twice. It covered 179 archives, 68,852 entries, and
1,296,608,653 ZIP-uncompressed bytes; cumulative accounting is 28 full
reconstructions and 3,696 graph archive opens. Input-set, source-binding,
candidate-content, graph, and exact-frontier SHA-256 values are
`4b12b7ca7f0a8b1556c692522e8832af033f9d2a1f00fbeb7469623a00541f1e`,
`86512fdc6c5b8ff8b1d79e500e32c6c35c36f6c097aca5385f8ff1e06ffe18fd`,
`4666c802e40734bb1b5b91489eb24aa782cb346710caec9605be4e0e005553ee`,
`ffe9f910669401198b88752663055ca2e6622d19e171f2d20a2b303d06c989d7`,
and
`ce1be1152aabf580a211f038d80aeaf9249418117b7d12ff26ffc909f1e4d593`.
It derives `fixedPointReached=false`, `route=next_wave_required`, and exactly
one non-selected Wave17 frontier tuple:
`golang.org/x/tools@v0.33.0`, with
`selectedByGraphAlgorithm=false`. Checker raw/normalized and current tests raw
SHA-256 values are
`e0a8353e5bd4f40b587c2b62c563c0b679ca5261345e577d71d00fb868f08fb5`,
`63198050500264a07082d205172c21993a309289649a5459e1c638b53fb22bf7`,
and
`65d7f435cef11da2cccae7e31a3c410d7a3038f6bc3261552753801a0de431b1`.
The genuine two-pass run passed 21 of 23 tests; its two failures were
test-oracle defects rather than reconstruction failures. After correcting
those two oracles, the affected tests passed independently 2/2 and the fast
boundary suite passed 2/2. Thus all 23 behaviors have verification coverage
across the genuine run and targeted reruns, but no single post-fix 23/23 full
suite run is claimed.

The separate verification-only Wave17 decision resolved that exact identity,
and its later one-use acquisition and independent readback are consumed
successes that cannot be retried. Acquisition attempt
`117fb836380658986632911b9508e274` retained the exact `.mod` and ZIP pair,
3,450,700 bytes total, without extraction. Readback attempt
`01f3117be3154e37f7f791b49002c490` independently verified the exact 21-file
snapshot twice and completed all three retained-FD barriers.

The read-only Combined V16 checker then held the exact 359-input set and
reconstructed it twice. It covered 180 archives, 70,402 entries, and
1,305,716,657 ZIP-uncompressed bytes; cumulative accounting is 30 full
reconstructions, 4,056 graph archive opens, and 60 underlying independent
graph algorithms. Input-set, candidate-content, graph, and exact-frontier
SHA-256 values are
`15705de20633cdf4bf473c82a634136f481a2c131e7960a0a6cbdeccf10397a7`,
`90928eb85eded2938b25a0beec82c00ebcd69147bf92733bc65a528d26c00e03`,
`db7e36664afd819c72e9c9916bd7053782282954ed4f359c550b7972b74147a2`,
and
`fe15a3ea57682b276a6f11a2c2fd998d9120640fac40038fc9c1f100e50750b5`.
It derives `fixedPointReached=false`, `route=next_wave_required`, zero
unmapped or unresolved imports, and exactly three non-selected Wave18
frontier tuples: `golang.org/x/mod@v0.24.0`,
`golang.org/x/net@v0.40.0`, and `golang.org/x/sync@v0.14.0`.
Checker raw/normalized and tests raw SHA-256 values are
`2e388d466c5346fa6f82b7fd23fa6dca24009acadacdd62f1fe2ba25b0a10879`,
`7dd2c81a2032a374192f7c502afc65305d97f7c1e3699654e416b60bf64c6bd5`,
and
`15cf4d56a68b9f0cfd61554b24e781357066b27e63c90c871dfb0cde19c80889`.
The exact result was captured from a genuine two-pass run, and the post-seal
dry plus fast boundary suites pass 13/13 without another full reconstruction.

The separate verification-only
[Wave18 decision](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave18-v1.json)
is sealed at content/raw SHA-256
`c75e5751d3e7c67939251d56e212f95f85439d05684cd50a49701de3e099803d`
and
`c90d16a7c7194c7a6dbde2be9bd99f4101a3a8cd1722278209fe5df8bf6371fa`.
It resolves all three identity pairs with zero conflict or blockage, binds the
exact six-request set at SHA-256
`3c13b764b7267efe885528d9f7d4fe31d6b7bdac48839f95e60bb5bd45a7d836`,
and passes 24/24 adversarial tests plus independent P0-P3 review. The decision
grants no acquisition authority and creates no permit, runner, claim, receipt,
or manifest. Its recorded next action is independent package review; that
local review completed before the separately versioned one-use action.

Wave18 acquisition attempt `4380f5bbcd3366154b05111381ccab18`
subsequently retained the exact six resources and 2,109,100 bytes without
extraction. Independent readback attempt
`7e424a47ffdde1099227564f41d610c4` verified the exact retained snapshot,
completed all retained-FD barriers, and published its manifest last. Both
one-use actions are consumed successes and cannot be retried.

The read-only Combined V17 checker then reconstructed the exact 365-source
retained set twice. Its exact held inventory is 375 paths, including seven
Wave18 terminal controls and three auxiliary evidence files. It covers 183
archives, 71,373 entries, and 1,312,942,457 ZIP-uncompressed bytes, with
cumulative totals of 32 full reconstructions, 4,422 archive opens, and 64
independent graph algorithms. Candidate-content, graph, and frontier SHA-256
values are
`1267edbe7f1a4f2554808376f67c6ba25a9217db0e6e2cc80a0822d780710f78`,
`cc748b6a5285321d8e74abab1c881dbc5ffd4433865ba9c75e459152f459092e`,
and
`4a7998ef0c1e5716640cccf9c5b349e92124bd787a2ca4090e3ba0920b68b006`.
The genuine run exits zero and derives `fixedPointReached=false`,
`route=next_wave_required`, zero unmapped or unresolved imports, and exactly
two non-selected Wave19 tuples: `golang.org/x/crypto@v0.38.0` and
`golang.org/x/text@v0.25.0`. Post-seal dry, latent, and fast-boundary suites
pass 18/18.

The verification-only
[Wave19 decision](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave19-v1.json)
resolves both exact H1 pairs with zero conflict or blockage and binds four
future request shapes at SHA-256
`97f4d8c1775c01c27f83f19b66af6274e0ae77b1be328456c2685ba18552b6e7`.
Its content/raw SHA-256 values are
`39edf590a88d728a105c74ef0eeb1600c84159888d3b4edbbe4acba05e7a6f56`
and
`7486a8a4659459ce49128bcf05501abb065f2b64c542715eaebd3c1ca686a8cf`.
The checker succeeds, 24/24 adversarial tests pass, and two independent
GPT-5.6 Sol reviews report no P0-P3 finding. The decision grants no acquisition
authority and creates no permit, runner, claim, receipt, manifest, or
namespace reservation. At that checkpoint its next bounded G2 step was a
separately versioned Wave19 acquisition package; that step was subsequently
completed. No further acquisition, extraction, source loading/execution,
compilation, runtime sockets/product networking, Git writes, device work,
credentials, authentication, or user action was opened or required by the
decision.

Wave19 acquisition attempt `f10c20196d994afe3a8eba830eb42614`
subsequently retained the exact four resources and 11,453,955 bytes without
extraction, loading, execution, or compilation. Independent readback attempt
`060a3d9bcd02113ef12c2c75a1e11d70` verified the exact 23-file retained
snapshot twice, completed all three required pre-manifest retained-FD barriers,
and published its manifest last with zero network requests and zero new source
acquisitions. Both one-use actions are consumed successes and cannot be
retried. They required no external authentication or user action. Readback completion
applies only to the retained snapshot; continuous current-path identity through
manifest publication and same-UID replacement prevention after the final
barrier are not claimed.

Combined V18 subsequently reconstructed the exact 369-source retained set twice
from an exact 379-path inventory. It covers 185 archives, 72,304 entries, and
1,359,347,284 ZIP-uncompressed bytes, with cumulative totals of 34 full source
reconstructions, 4,792 archive opens, and 68 independent graph algorithms.
Candidate-content, graph, and frontier SHA-256 values are
`9dce50013314ec8934ad52ac57cb0de92e982c2334303fc77289f01bc9c285fb`,
`a865a62a7a80a0dece55aeebd537d3fb9aa73ce6ceeea10304a6a2074c2dfaba`,
and
`37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`.
It derives `fixedPointReached=true`, `route=fixed_point_candidate`, an empty
frontier, and zero new, unmapped, or unresolved tuples/imports. Extraction,
dependency-source load/execution/compilation, subprocess, network, and file
write counters are all zero. The post-seal dry, latent, and fast-boundary
suites pass 18/18. The genuine full class reproduced the candidate and passed
23/24; its only error was a stale test-chain index. After correction, the
affected legacy-Wave9 compatibility test passed independently. No single
post-fix 24/24 full-class rerun is claimed.

The separate
[Combined V18 closure-review decision](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-combined-fixed-point-closure-review-decision-v1.json)
now accepts only `dependencyFixedPointReached=true` for that exact retained
graph-discovery snapshot. Its read-only checker succeeds and its mutation
suite passes 15/15. All 19 semantic findings remain open, and dependency-source
review, dependency/semantic closure, license/security review, candidate and
library selection, rung-three completion, and V1 readiness remain false. At
that checkpoint, the next bounded G2 step was the separate fixed-point-snapshot
dependency source and license review decision completed below. No
authentication or user action is required, and no
acquisition, extraction, loading, execution, compilation, network, socket,
device, publication, Git-write, or deployment authority is opened.

The separate
[fixed-point snapshot source/license review decision](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-fixed-point-snapshot-source-license-review-decision-v1.json)
and exact zero-write adapter are now complete for their preparation boundary.
The adapter binds 369 inputs, 184 dependency tuples, 185 archives, 72,304
entries, 58,478 Go files, 11,150 special-source rows, and the accepted V18
graph. Its focused suite passes 14/14; the decision checker and mutation suite
pass 15/15. Two independent GPT-5.6 Sol passes reproduced those inputs but both
returned `passComplete=false`, so completed independent passes remain 0/2.
Pass A's code-level claims map to already-open canonical findings; pass B's
`PATENTS` inventory and native-profile observations are review-completion
blockers under the existing dependency-review gap, not new product
vulnerabilities. Initial pass B's no-P0-P3 statement meant no new finding at
that incomplete stage and did not contradict or close the existing open P1
findings. The next bounded work must
complete file-by-file semantics for 492 production-reachable Go bodies,
selected special-source review, broad
license/`PATENTS` conclusions, SPDX/provenance/binary mapping, and native
profile reachability before either pass can count as complete. No
authentication or user action is required.

Both passes have since completed deterministic rows 1-164: 164 files and
753,000 bytes at batch SHA-256
`e3604e20a65059f07429913d09784784493c5fd8b71b3859ca544963cdfd143a`.
Each still has 328 files remaining, so completion stays 0/2. Cross-validation
confirmed a new non-canonical P2 reliability candidate where DTLS retains
subsections of a pooled receive buffer for delayed processing after returning
the backing buffer to `sync.Pool`; reuse can corrupt queued handshake bytes.
It also confirmed unbounded completed-handshake caching as a new source
location extending existing resource finding
`G2SR1-F-9206ffd24b3357f7cda5`. Neither observation is a persisted closure
result, and no authentication bypass is claimed. Batch 2 is the current
bounded code-review step.

The rung-two successor recorded, only `at_that_checkpoint`,
`recordedNextActionAtThatCheckpoint=prepare_versioned_rung3_offline_source_review_decision`.
That historical action is now satisfied and is not the current next action.

### Active Personal-Project Governance

AetherLink is a personal, single-owner project. Owner identity authentication is
not required for this personal project. The owner's direct instruction is the
current governance decision and is sufficient for repository reads, edits,
builds, tests, and G1a no-network implementation. No SSH/GPG proof of control,
fourteen role-scoped approval receipts, owner RFC 3161 timestamp, or external
owner-governance replay ledger is required.

The immutable V1/V2/V3 decision and assurance lineage, owner-trust profiles, and
their validators remain byte-preserved historical enterprise-assurance records.
Their owner-authentication and `blocked_before_g1a` clauses do not block current
personal-project work. The fourteen roles remain useful responsibility labels
for one owner; they are not separate principals, signers, or approval steps.

This governance change does not weaken product security. QR pairing and device
mutual authentication, endpoint secure sessions, route-capability checks,
replay/downgrade resistance, pair epochs, revocation, re-pairing, and product
key rotation remain required. G1a no-network work is open. Socket creation,
external network execution, production signing, store upload, and deployment
remain separate technical scopes and need current user direction plus their
applicable safeguards, but never repository-owner identity proof.

### V1 Product Outcome

AetherLink V1 is a production release in which an Android controller can pair
with a macOS AetherLink Runtime by QR, reconnect without entering an Ollama or
LM Studio URL, and use the complete trusted runtime loop on the same LAN or on
unrelated networks. The supported product loop is:

1. Install signed release artifacts on a supported macOS host and Android
   device.
2. Start AetherLink Runtime and obtain a fresh production pairing QR backed by
   an authenticated, expiring route.
3. Pair identities through the physical camera, confirm trust, and establish an
   identity-bound secure session.
4. Prefer identity-matched local direct connectivity, then production P2P/NAT
   traversal, then the G0-approved end-to-end encrypted fallback profile. G0
   must either retain the currently approved TURN plus sealed-emergency-relay
   profile or explicitly supersede it with a newly reviewed profile.
5. Read runtime and backend health, list installed Ollama or LM Studio models,
   stream chat and reasoning, cancel generation, reopen runtime history, and use
   runtime-owned memory and the already-supported attachment paths.
6. Recover after app or runtime restart, network handoff, route expiry, QR
   rotation, and explicit trust revocation without falling back to an anonymous,
   development, plaintext, or stale route.

The macOS Runtime continues to own AI execution, provider URLs, credentials,
history, memory, and tool boundaries. Android remains a trusted controller and
never connects directly to Ollama or LM Studio. Reachability never establishes
authorization. Local direct, P2P, and relay transports must all terminate in the
same paired-identity and secure-session contract. A relay may observe bounded
routing metadata, timing, and ciphertext size, but must not read model lists,
prompts, responses, files, memory, provider URLs, or session traffic keys.

A V1 claim requires signed release-to-release evidence and production-like
external-network evidence. A debug QR, local authenticated smoke, release
compile, mock relay, or same-Wi-Fi camera run is valuable lower-rung evidence
but cannot independently satisfy the V1 release gate.

### Current 2026-07-28 Baseline And Gap

| Area | Current 2026-07-28 baseline | V1 gap |
| --- | --- | --- |
| Product loop | macOS Runtime and Android controller implement pairing, trust, health, installed-model selection, chat streaming/cancel, history, memory, and attachment flows. | Exercise the supported loop from clean signed release installs, with live Ollama and LM Studio, across every required route. |
| Local physical proof | One `SM-S936N` completed debug same-Wi-Fi optical QR pairing, challenge-response authentication, health, force-stop, Bonjour rediscovery, and trusted reconnect. | Expiry/rotation, camera denial/regrant, process death, TalkBack/VoiceOver, additional supported devices, and release binaries remain unproven. |
| Automated proof | The previous complete default no-device aggregate snapshot exits zero with `No-device quality checks passed.` It records Python 182/182, 1,946 Swift tests with two declared skips and zero failures, all Android Gradle invocations `BUILD SUCCESSFUL`, copy/docs hygiene across 94/12 files, direct and development-relay local mock smokes, relay freshness across 56 connections, 905 encrypted frame bodies at the ciphertext boundary, and the final G1a-D authority-lifecycle marker. Focused authority-lifecycle evidence includes 31/31 exact-bound Swift coordinator, 78/78 TrustedDevices, 9/9 Swift shared-vector, 87/87 Swift P2PNAT, 7/7 Kotlin shared-vector, 232/232 Android protocol, 200/200 Android pairing, and 8/8 Python mutation tests. Focused Android transport-composition evidence is 79/79 (49/49 manager plus 30/30 adapter). The root independently reran full `core:transport --tests '*'`: 10 suites pass 163/163 with zero failures, errors, or skips; app `compileDebugKotlin` plus `compileDebugUnitTestKotlin` also succeed. An independent iterative audit found and fixed six P3 availability/lifetime races in total; a final fresh re-audit reports no P0-P3 finding. The current root-independent full Swift rerun passes 2,003 tests with two declared skips and zero failures in 313.440 seconds. Those focused/full-module reruns alone were not a completed full no-device gate run; the current full no-device gate exits zero. Focused macOS transport-composition evidence is 39/39 (17/17 composition plus 22/22 secure-channel) and 34/34 (6/6 production-pair-coordinator plus 28/28 manager), and the release build passes. The audit-found cancellation/replacement P2 is fixed with a deterministic delayed-abandon regression; final independent re-audit reports no P0-P3 finding. Current caller-bridge evidence passes Android composer 16/16 plus ViewModel-clear 1/1, full app 1,174, and complete core protocol/pairing/transport 232/232, 200/200, and 163/163. Current macOS caller evidence passes service 9/9 and manager + service + composition 54/54; the release build succeeds. Newer G1b-A focused evidence covers the normal empty controller, injected real-fixture manager/ViewModel activation, and macOS accepted-raw primitive without live socket execution. | CI still lacks signed artifacts, physical-device, external-network, sanitizer/fuzz, soak, and production-deployment evidence. The prior aggregate is no-device local proof, not production transport or production app/service activation. Its counts were not refreshed for the transport-composition, caller-bridge, or G1b-A seams and remain snapshot facts, not permanent release thresholds. |
| Transport | Identity-first routing, local discovery, route records, a bounded encrypted development relay, socket-free G1a-A route/transcript, G1a-B monotonic pair-state/durable admission, and G1a-C root-pinned signed authority/capability/candidate/receipt verification plus exact object-25/26 grant projection exist. Compound persistence and the exact-bound coordinator protect the latest durable start boundary. G1a-D derives role-separated keys only from a verifier-minted exact object-7/object-26 binding and implements mutual object-29 confirmation plus ordered, bounded, rekeying object-30 AES-256-GCM records on both platforms. A store-owned process-local publication gate binds start and every crypto result to pre/post lease/live fences. The composition seam is concrete: Android uses a manager-owned one-use raw-route lease and `ProductionRuntimeSecureChannelAdapter`; macOS owns exact one-use accepted-session attachment with no plaintext fallback. G1b-A now installs an app-scoped empty `AndroidProductionRuntimeActivationController` in the normal factory with the exact `PairingStore` and trusted clock. It publishes no route until an upstream producer supplies a verified attempt and an already-connected one-use endpoint. Injected real-fixture manager and full ViewModel E2E tests complete the authority-bound handshake and an application record without legacy fallback or an OS socket. macOS now exposes `LocalPeerServer.startAcceptedRaw` with an IPv4-loopback-only listener policy, bounded one-slot authorization, serialized receive ownership, and injected no-socket tests. | Real production activation, hardened allocation, signaling, ICE/STUN/TURN, P2P path migration, and blind relay operations remain incomplete. Android still lacks the upstream verifier/candidate/secret producer and actual P2P endpoint stack. The macOS accepted-raw primitive is not connected to `CompanionAppModel`, and its listener has not been socket-executed. Actual socket close interruption, live network, physical-device, and production-release behavior remain unproven. The current guarantee is single-process and same-store/coordinator-graph only. The eventual production caller must keep `seal + channel.send` inside the same read-permit closure. |
| P2P library | `libjuice`, `libnice`, and unmodified Pion ICE v4.3.0 remain rejected before compile/as-is. Restricted-fork dependency acquisition/readback is consumed through Wave19. Combined V18 reconstructed 369 retained source inputs twice and produced an empty-frontier fixed-point candidate; its closure review accepts only `dependencyFixedPointReached=true`. The fixed-point source/license preparation decision and zero-write adapter pass their focused suites. Two independent Sol passes reproduced the exact input but both remain incomplete, so pass completion is 0/2. All 19 findings, semantic/dependency closure, rung-three completion, candidate selection, and library selection remain open. | Complete file-by-file semantics for 492 production-reachable Go bodies, selected special-source review, broad license and `PATENTS` conclusions, SPDX/source-provenance/binary mapping, and native profile reachability. Further extraction, reviewed-source compilation/execution, runtime sockets/product networking, and product operation remain closed until their own bounded gates. |
| Relay security | Bounded leases, identity challenges, strict JSON, encrypted frame bodies, quotas, and development lifecycle controls exist. | Allocation TLS, service-signed lease capabilities, peer-verifiable KEX, pair epoch recovery, immediate revocation, signer rotation, multi-instance operations, and deployment remain open. |
| Distribution | Android is version `0.1.0` with no production signing configuration; the macOS development bundle is ad-hoc signed. | Production application identity, signing custody, channel validation such as direct-distribution notarization or App Store review, install/update/rollback, artifact provenance, and staged distribution are required. |
| Repository state | Historical G0 lineage remains byte-preserved but does not impose owner authentication on this personal project. Current tracked history includes the socket-free G1 foundations and the Pion rejection/restricted-fork review lineage. The present working scope adds consumed Wave19 acquisition/readback evidence, the Combined V18 fixed-point/closure decision, and the source/license preparation package plus incomplete two-pass review status. | Read publication state from Git; this roadmap does not stage, commit, or push. The next local G2 boundary is bounded review-completion coverage, not another acquisition or authentication gate. Selected backend/carrier, extraction, compiler, runtime socket/product network, Git write, credential, authentication, and user action all remain outside this boundary. |

### Governing Source Records

- The current product/evidence boundary is maintained in
  [the canonical handoff](handoff.md), while the transport shape and current
  implementation gaps are maintained in [architecture](architecture.md) and
  [protocol](protocol.md).
- The current P2P/NAT profile is
  [approved only for a bounded handoff](security-hardening/production-p2p-nat-v1/selection-profile.md).
  Its latest [progress](security-hardening/production-p2p-nat-v1/controlled-network-spike/phase-a/progress-v8.json),
  [decision](security-hardening/production-p2p-nat-v1/controlled-network-spike/decision-v6.json),
  and [handoff](security-hardening/production-p2p-nat-v1/implementation/handoff-v9.json)
  leave no library selected and all execution authority closed.
- The historical G2 pre-acquisition predecessor is the hash-pinned
  [restricted-fork hardening portfolio](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/hardening.md)
  and exact [machine profile](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/restricted-fork-profile.md).
  It records only the rung-one design/checker state that preceded the now-
  consumed rung-two decision. At that checkpoint it selected or acquired
  nothing and opened no
  dependency, compiler, loader, socket, network, device, deployment, or Git
  operation.
- The current G2 successor includes the tracked rung-three
  [result-v3](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/offline-source-review-result-v3.json),
  [runtime-manifest-v3](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/offline-source-review-runtime-manifest-v3.json),
  [execution-receipt-v3](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/offline-source-review-execution-receipt-v3.json),
  historical [semantic-review decision v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/semantic-source-review-decision-v1.json),
  [classifications](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/semantic-source-review-classifications-v1.json),
  [result](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/semantic-source-review-result-v1.json),
  atomic [manifest](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/semantic-source-review-manifest-v1.json),
  historical [patch/dependency decision v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/patch-and-dependency-closure-decision-v1.json),
  historical [implementation-or-dependency review decision v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/implementation-or-dependency-review-decision-v1.json),
  its [staged fixed-point review plan](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/implementation-or-dependency-review-decision-v1/implementation/staged-fixed-point-source-closure.md),
  the predecessor [bounded dependency source-identity and acquisition decision v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-v1.json)
  with its [reader contract](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-v1.md).
  Its successor [one-use execution permit v1](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-execution-permit-v1.json)
  and [reader contract](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-execution-permit-v1.md)
  are followed by the consumed v1 claim/failure, recovery decision v1, the
  consumed v2 permit/claim/failure, recovery decision v2, the consumed v3
  permit, its 38-resource success receipt/manifest, and the fixed-hash 43-file
  independent readback. Source-review v1/v2 then failed closed without a
  partial result; v3 and its independent readback recorded the exact 15-tuple
  frontier. Wave2 and Wave3 then completed their versioned acquisition and
  independent-readback paths. Combined-v2 held the root plus 100 dependency
  resources and projected the exact non-fixed 16-tuple Wave4 frontier. The
  Wave4 decision binds 22 parent declarations and complete,
  conflict-free H1 pairs for all 16 tuples without acquiring Wave4 source.
  Its separate one-use permit was consumed once, retained all 32 resources,
  and completed a separate two-pass independent readback. Combined-v3 now
  held 133 source inputs and projected the exact non-fixed 15-tuple Wave5
  frontier. Wave5 decision v1 resolved all 15 H1 pairs and prepared 30 ordered
  requests without acquisition authority at that checkpoint. Its later one-use
  acquisition attempt retained all 30 resources, and readback attempt
  `8f3813a784359883b4d93370c9041809` independently verified the retained
  snapshot twice. Combined-v4 then reconstructed all 163 inputs twice and
  projected a non-fixed 18-tuple Wave6 frontier whose entries are all
  graph-unselected retained versions. Wave6 decision v1 then resolved all 18
  H1 pairs and prepared the exact 36 ordered requests without acquisition
  authority at that checkpoint. Its later one-use acquisition attempt
  `5e0828c2e5dc1ce7ef2a06dd235d5076` retained all 36 resources, and readback
  attempt `7fc50276e880013e1ace73920397ba3f` independently verified the retained
  snapshot twice before writing the manifest last. Combined-v5 subsequently
  reconstructed all 199 exact inputs twice, derived a non-fixed 15-tuple Wave7
  frontier, and passed 25/25 focused tests. Wave7 decision v1 now resolves all
  15 identity pairs without conflict, preserves every selector as false, and
  prepares the exact 30-request contract without granting acquisition; its
  focused suite passes 13/13. Acquisition attempt
  `c15f4504ae880326144eca93dc91e37b` then retained all 30 resources, and
  readback attempt `1839537589935de087068a5a7d5c7e14` independently verified
  them twice before writing its manifest last. The readback checker and
  recorder suites pass 16/16 and 45/45, with no P0-P3 audit finding.
  Combined-v6 then reconstructs all 229 exact source inputs twice, binds
  input-set SHA-256
  `f7ad0b43d571da61edd4941f8e504d54d014b01f3395aeca8d0d10b9b3c22349`,
  graph SHA-256
  `3648bdf037e316e69e155615edd5748c2bb653238579216ddd8b8dce4beb9f09`,
  and derives the exact non-fixed 14-tuple frontier at SHA-256
  `d3c3788d6a1144bf04ea2c68e6aa4b9fdd17859bc625e2c2c51019bb3c61ff92`.
  Its focused suite passes 25/25 with no P0-P3 audit finding. Wave8 decision
  v1 then resolves all 14 exact H1 pairs, binds the 28-request set at SHA-256
  `b0f0f887864ddc4cf3ab15319a9e89dbea8c84087fa3d0e374a0332240336ddc`,
  and passes 18/18 tests with no P0-P3 audit finding. The decision grants no
  acquisition. Its separate exact one-use permit package binds 28 resources
  at SHA-256
  `ee32b0512643b0e767f5b1e96625352fc47ea6ae7aea5d7366adfe98f4db8136`,
  and passes 15/15 checker plus 44/44 network-free mock/local runner tests.
  Acquisition attempt `6d8ea4473126c853b439c56a895f9c28` retained all 28
  resources. Readback attempt `8618087527c005b5d19c8f902ec33557`
  independently verified the 46-file snapshot twice; the readback permit and
  recorder suites pass 16/16 and 45/45, and the manifest was written last.
  Independent GPT-5.6 Sol post-run audit reports no P0-P3 finding. Combined-v7
  subsequently projected the exact non-fixed ten-tuple Wave9 frontier, and
  Wave9 decision v1 resolved all ten H1 pairs without acquisition authority.
  Its separate one-use 20-resource permit package passes 16/16 checker and
  44/44 injected network-free runner tests. Acquisition attempt
  `df64a4816a083806020580efe953b9a7` retained all twenty resources, and
  readback attempt `2d61a0483984e9a2f77665dd3c624cb2` independently
  verified the exact 38-file snapshot twice before manifest-last publication.
  Readback suites pass 16/16 and 45/45. Combined-v8 then reconstructs all 277
  exact inputs twice, binds input-set SHA-256
  `030743c3959a6e7466385e9f89255fcb03d65576676a1e5cd7e5e2929e9f6339`,
  graph SHA-256
  `721d045a10cdf015e865a84db7026115ac63462217dbb5349504fed9f1bae7b7`,
  and derives the exact non-fixed eleven-tuple Wave10 frontier at SHA-256
  `780501bca37fbeb953590004ca7e5aad7f206083f749b920e2a9842b63675f82`.
  Its checker exits zero, its full suite passes 29/29, and final independent
  audit reports no P0-P3 finding. Wave10 then completed its separately bound
  identity decision, one-use 22-resource acquisition, and two-pass retained-
  snapshot readback. Combined-v9 subsequently reconstructed the exact 299-source
  inventory twice and derived a non-fixed nine-tuple Wave11 frontier at
  SHA-256
  `171af951e3a67405b62ddceface1341bb6f64b08f370d3d216ede541bd011f06`.
  Its exact final suite passes 21/21 and two independent GPT-5.6 Sol audits
  report no P0-P3 finding. Wave11 decision v1 then re-executed the pinned V9
  candidate, reproduced the identity scan twice, resolved all nine exact pairs
  with 12 declarations, 68 `go.mod` H1 witnesses, 13 ZIP H1 witnesses, and zero
  blocked or conflicting tuples, and bound the exact 18-request contract at
  SHA-256
  `bbde21b5f7a523bb6cddf78fbbbfdce46f8bcf61d60ebcec72a80d52dda50ba8`.
  Its exact suite passes 25/25 and three independent GPT-5.6 Sol final-byte
  audits report no P0-P3 finding. The separately bound Wave11 acquisition
  attempt `ac18b8fda0a80a132510efd5dd17d5b7` then retained all 18 exact
  resources, and offline readback attempt
  `9b4dac65f66ce9e5d53dcd8edaf4d1d4` independently verified the exact
  36-file retained snapshot twice before manifest-last publication. The
  acquisition checker/runner suites pass 17/17 and 46/46; readback suites pass
  17/17 and 50/50. Both one-use actions are consumed and cannot be retried.
  Combined-v10 then reconstructed all 317 exact inputs twice and derived a
  non-fixed four-tuple Wave12 frontier at canonical SHA-256
  `8b84bd2fd9201d33f4424b9dd1018aee7f8470a87306c2ba23eba0c8b6d4ff05`.
  Wave12 decision v1 is complete for its read-only bounded scope: all four exact
  H1 pairs are complete and zero are blocked or conflicting. Its separate
  exact-eight permit package is materialized, passes 18/18 checker and 48/48
  fake/local runner tests, and was consumed exactly once by acquisition attempt
  `f977ddcf8fc391e5915048b930beccbd`, which retained all 8 resources. Offline
  readback attempt `32ab6b747a02382f85f48f65e0c388c5` verified the exact
  26-file snapshot twice before manifest-last publication. Both one-use actions
  are consumed and cannot be retried. Combined-v11 reconstructed the exact
  325-input set twice and produced the four non-selected Wave13 tuples.
  Wave13 decision v1 resolved all four H1 pairs, binds request-set SHA-256
  `eae1bb0f8645a5d698bfe50fae505a1c7d6887c78c9dcc3b088939b97e0ffce1`,
  has decision content SHA-256
  `3d08d589ed9121128717215fe0d9583b6f64e59fc033e1c5f50477f6e59d5b83`,
  and passes 27/27 tests. The separate one-use eight-resource Wave13 permit
  package is now materialized with resource canonical SHA-256
  `cdb0c96d670feb69063b50709a342313501de575e4d8d692f943dffcab176f29`,
  permit content SHA-256
  `d3e7fb34e17a94cd2d89249e115e4ef15122a40f1df4ff8d6c977ed9dd6cfc07`,
  and raw SHA-256
  `b976f9bea30a20e34df25e9d90cfa9ee4617ce825b0d28f254b5bb512b6c29a1`.
  Its checker and fake/local network-denied runner suites pass 18/18 and 48/48.
  Three independent GPT-5.6 Sol final-byte audits report no P0-P3 finding.
  Acquisition attempt `eb05816e0b897ea8c3ad8b7089668e91` retained all eight
  resources without extraction. The separately sealed readback package passes
  17/17 checker and 50/50 recorder tests and binds the exact 27-file snapshot
  at canonical SHA-256
  `a99b35472a140330847b1ff7e746a83dc060707ea63af3ef22d165a4f2ced11d`.
  Readback attempt `8b5f92c9d90f825f5f3b46df0d006ef3` verified that
  snapshot twice and completed manifest-last publication. Both Wave13 one-use
  actions are consumed and cannot be retried. Extraction, source
  loading/execution/compilation, product/runtime sockets, general filesystem/
  Git writes, publication, credentials, authentication, and user action remain
  closed or unrequired.
- The relay portfolio originally recommended
  [TLS plus signed lease capabilities](security-hardening/production-relay-v1/proposals/authenticated-allocation-control-plane.md)
  and [pair epoch recovery](security-hardening/production-relay-v1/proposals/pair-epoch-recovery.md).
  G0 now selects both as V1 requirements, while the
  [relay hardening review](security-hardening/production-relay-v1/hardening.md)
  remains implementation-, socket-, network-, key-, and deployment-gated.
- This roadmap is planning guidance. It does not itself authorize source
  acquisition, implementation, compilation, sockets, external network access,
  service deployment, production traffic, signing-key use, or publication.

### V1 Required Scope

- Android controller and macOS Runtime only. The current declared Android
  minimum is API 26 and the Swift package minimum is macOS 14; G0 must confirm
  the final supported OS and hardware matrix rather than inheriting those
  values silently.
- Ollama and LM Studio through runtime-host adapters. No direct client-provider
  traffic and no provider URL in client storage, UI, telemetry, or diagnostics.
- Production QR onboarding, trusted-device listing and revocation, route
  refresh, expiring leases, pair epoch recovery, and clean re-pairing.
- Identity-matched local direct routing, real different-network P2P/NAT
  traversal for eligible networks, and every data plane required by the
  G0-approved encrypted fallback profile.
- One versioned secure-session profile shared by all route types, including
  replay resistance, downgrade prevention, rekey/expiry, bounded clocks, and
  explicit N/N-1 migration behavior during rollout.
- Core health, installed models, chat stream/cancel, reasoning, history, memory,
  and current attachment behavior without expanding their authority model.
- Actionable connection/recovery UX, five-locale parity, large text, keyboard
  and screen-reader semantics, camera permission recovery, and lifecycle
  recovery.
- Signed Android and channel-valid signed macOS artifacts, clean install and
  declared upgrade or fresh-pair transition, rollback, privacy-safe operations,
  capacity and failure drills, and staged GA.

### Explicit V1 Non-Goals

- iOS, Windows, DGX OS, additional runtime-host platforms, or additional serving
  backends.
- Account service, cloud AI backend, cloud synchronization, organization or
  multi-tenant management, and account-based recovery.
- DHT or fully decentralized rendezvous, anonymous/public peer discovery,
  censorship resistance, universal firewall traversal, or complete
  traffic-analysis resistance.
- Multi-party/group trust, threshold recovery, or cross-user sharing. Pair epoch
  recovery is required; threshold recovery remains post-V1.
- MCP, terminal execution, general Python execution, web search, new skill
  execution, workspaces, scheduling, and automation.
- New advanced memory, research, or RAG surface expansion. Already implemented
  functionality must remain safe and compatible, but it must not displace the
  transport and release critical path.
- QUIC promotion or another transport rewrite unless the selected V1 stack and
  measured evidence make it necessary. V1 needs one proven profile, not every
  plausible transport.

### Critical Path And Planning Envelope

The dependency order is:

```text
G0 V1 contract and baseline
  -> G1 secure-session and control-plane contract
       -> G2 new NAT-stack authority and selection --\
       -> G3 production rendezvous/fallback services --> G4 endpoint route integration
  -> Q continuous product, data, accessibility, and CI hardening -----/
  -> G5 lifecycle and recovery closure
  -> G6 signed release-to-release qualification
  -> G7 RC, operations, and staged GA
```

G2 and G3 may overlap only after G1 freezes their shared identity, lease, epoch,
and transcript contracts. Product and QA work may proceed in parallel, but no
later phase inherits compile, socket, external-network, or deployment authority
from an earlier phase. An indicative planning envelope is 18 to 26 elapsed
engineering weeks when networking, service operations, application, and release
work can overlap. This is not a delivery commitment; G0 must re-estimate after
owners, infrastructure, support matrix, and service SLOs are assigned, and G2
must re-estimate after a candidate actually passes source review.

The `Q` lane starts in G0 and is owned jointly by application and QA owners. It
keeps current health/model/chat/history/memory/attachment behavior compatible,
adds CI and release evidence as contracts stabilize, and fixes release blockers
without expanding product scope. Its exit gate is continuous: every G0-G4
checkpoint must pass the affected fast and full suites with no unexplained
baseline regression, and G5 owns its final physical/product closure.

### Current Execution Status

The V1 execution goal is active. The versioned
[G0 decision](v1/g0/decision-v1.md) and its
[machine record](v1/g0/decision-v1.json) now freeze the repository-derived
product, platform, distribution, fallback, relay-control, pair-recovery,
privacy, SLO, evidence, and authority defaults. A dedicated validator and
the versioned [G0 assurance packet](v1/g0/assurance-v1.md) now hash-pin the
protocol/data-flow inventory, threat/risk refresh, observability schema, release
checklist, and incident/rollback runbooks. Its 63-test mutation suite keeps both
records fail-closed; release metrics require an approved signer, Ed25519
verification, bounded canonical raw samples, and exact signed outcomes for each
required network variant derived from ordered per-attempt outage and recovery
observations. Twelve non-omittable
network cells, including VPN and suspend/resume, plus six symmetric-NAT,
consent-loss, deliberate-failure, and outage variants now define the release
population. Native-IPv6 and home-NAT cells have a separate release-blocking
direct-P2P threshold. Four measurement contracts bind targets to owner roles,
sources, sample/window rules, and failure actions.

A closed G0 derivation contract now crosswalks all ten blockers to all nine G0
checks, all fourteen accountable roles, and exact gate-scoped evidence kinds.
It defines owner, catalog, gate, and publication receipt shapes and their exact
repository/commit/path/hash/result/timestamp bindings without fabricating any
receipt. Receipt acceptance stays disabled until a successor implements the
machine-pinned independent trust context and complete bundle aggregation. Later
G2/G4/G5/G6 risk evidence remains mandatory at its own gate and cannot be
silently promoted into, or substituted for, G0.

The separate
[G0 assurance checkpoint readback candidate](v1/g0/assurance-checkpoint-readback-v1.json)
pins its own bytes in an external validator, recomputes the assurance raw and
canonical hashes, and rehashes all 29 assurance source records in exact declared
order. Eleven mutation tests keep path, role, hash, symlink, concurrent identity
drift, the 4 MiB per-source ceiling, non-finite numeric overflow, over-128-digit
integers, recursive type confusion, owner, publication, blocker, and authority
claims fail-closed. Its status remains
`candidate_observed_not_immutable`; that embedded state and a local checker
constant alone were not publication proof. The later commit publication and
remote observation are external facts and do not rewrite this frozen record.

The committed V1 assurance/checkpoint bytes remain unchanged. The separate
[V2 closure amendment](v1/g0/assurance-closure-amendment-v2.md) and its
[content-addressed checkpoint](v1/g0/assurance-closure-amendment-checkpoint-v2.json)
bind the exact parent raw/canonical digests, apply eleven allowlisted ordered
JSON Pointer operations to a deep copy, advance the effective and nested
closure schema identities, and pin the reconstructed effective V2 assurance
digest. A composite publication receipt binds all four exact files and the
effective digest; bounded no-follow reads plus final identity/hash readback
protect the local candidate. They classify only the full no-device aggregate
and ordered Android/macOS release compilation as executable checks. Both
command profiles remain unauthorized, and the amendment has no publication or
owner receipt.

A dormant composite-publication validator now reconstructs the V2 candidate
from four supplied exact commit blobs and compares a strict 14-field receipt to
a factory-owned immutable target plus independently supplied remote checkpoint
bytes. It performs no receipt-directed I/O and returns failures only. Synthetic
matching evidence is not publication: the private matcher still returns
`dormant_non_authorizing`, the canonical checker rejects every supplied bundle,
and no acceptance, execution authority, or G0 state changes.

The separate
[V3 closure amendment](v1/g0/assurance-closure-amendment-v3.md) preserves every
V1/V2 byte and adds the previously missing complete-bundle, owner, evidence,
authority, runner, gate, approval, and six-artifact publication profiles. Its
private pure compiler snapshots the six lineage blobs once and derives exact
10-blocker, 9-check, 14-owner, 15-role/blocker-pair,
15-non-derived-evidence, 2-derived-evidence, and 2-executable-check coverage
from effective V3, including exact ordered checklist/blocker evidence union.
It rejects caller-supplied outcomes and inconsistent references/times and still
returns `dormant_non_authorizing` for an exact synthetic fixture. The unchanged
V3 amendment and checkpoint bytes are now contained in published commit
`12c38154`; their embedded pre-publication candidate state remains unchanged.
The separate exact 13-field
[publication receipt sidecar](v1/g0/assurance-closure-publication-receipt-candidate-v3.json)
encodes the reviewed repository, commit, checkpoint hashes, and completion time
drawn from the session observation and is content-addressed by the checker. It
does not persist the fresh-clone/no-alternates acquisition or 18-file comparison
provenance, independently reproduce remote readback, or establish trust,
approval, execution authority, receipt activation, G0 exit, or G1a authority.
The separate
[owner/catalog input candidate](v1/g0/owner-catalog-input-candidate-v1.json)
is a content-addressed sparse envelope bound to the same repository, commit,
checkpoint, and effective V3 digests. Its published `70350f5e` form is empty.
After explicit input review on 2026-07-21, the current exact 1,452-byte local
candidate at raw SHA-256
`0221d2d49e4bcccfd34fb6905102117fbf5632e27d3d2f2e23d53e29f47752bc`
contains one `roadmap_and_g0_checkpoint_publication`
`proposed_as_written` response, one
`owner-candidate:repository-owner:v1` reference, the ordered
`reviewed_commit_scope:v1` and `published_checkpoint:v1` evidence references,
no supporting-artifact or change-request candidate, and
`user-input:session-20260721:item-2`. It copies none of the ten-blocker
role/evidence graph: the checker derives that graph from the six immutable
lineage blobs and permits only canonical reference-only proposals mechanically
bound to exact role/evidence-kind/blocker slugs and versions. Free-form catalog
values are not fields in this envelope; a kind-and-version-bound supporting path
only reserves the canonical location for an artifact that must be separately
typed, created, and reviewed. All state flags remain false and the candidate
remains `draft_unverified_non_authorizing`; it cannot authenticate the proposed
owner, inspect or verify evidence, accept the proposed disposition or receipts,
close blockers, or grant G1a authority.
The separate exact 17,353-byte
`evidence-supporting-artifact-candidate-profile-v1.json` at raw SHA-256
`f8ad6742fcb569f408b5f4087b20f11f32cb497a8f9eec2fc3f255d8b22c226f`
defines closed, bounded, supplied-bytes-only payload profiles for those two
future evidence kinds. It pins the reviewed `12c38154` 18-entry scope and the
bounded V3 checkpoint observation. It also hash-binds the exact item-2 selector
snapshot and projects its source/ref/version/index/path/false-null state into
each envelope. Any selector change requires a new profile. Independent trust/
provenance inputs remain missing and every authority state remains false. It is
a profile, not evidence; both reserved artifact instances remain absent while
both selectors are false.
The separate 19,697-byte
`baseline-gate-evidence-readiness-profile-v1.json` at raw SHA-256
`a0c8f45167e9a8f3a4fccbba65afbb928b29b88df2ea2090cc96043ba960af17`
defines one closed envelope for the five non-derived baseline-gate evidence
kinds without creating any artifact instance. It reconstructs effective V3,
binds the two static observation shapes to the exact six-lineage and 29-source
records, and binds the three execution-result shapes to the exact two command
profiles and their ordered step digests. Both command profiles remain
`not_authorized`. Its pure compiler produces only an in-memory 3,640-byte
`prepared_unverified_non_authorizing` plan at SHA-256
`ce679bbb4ebf01e4f838726d4c8f224e48cdd8170b3b205e89a4a54ce2d32227`,
with null authority/runner refs and every execution, acquisition, catalog,
receipt, closure, G0-exit, and G1a flag false. The pure static compiler returns
fixed-order 5,763-byte canonical-assurance and 10,771-byte source-readback
candidates at SHA-256
`2d193cb2f3bddf4d202129b4a746a3bd3cbba05f1a879e748f8001eb5c138db4`
and `5df6ba51f3177424407078424fcff90dc2faa8d1c1d4e80e79e96486c3a54fc6`;
the pair remains dormant and is never written as evidence. The 22-test mutation
suite rehashes all 29 actual supplied source blobs and every ordered synthetic execution-
manifest blob, binds one canonical egress/process observation composite,
cross-binds payload/log/output digests, requires the full-gate
success marker once, and proves that all five fixtures remain dormant while
lineage, source, manifest, command, step, session, time, path, encoding,
resource, mutable-pair, and state drift fails closed. The five reserved
candidate artifacts remain absent; verifier,
provenance, owner acceptance, authority, runner, gate, approval, and catalog
records are still external prerequisites.

The separate candidate-only independent-validation module derives the exact
seven trust-input kinds from effective V3 and admits them only as factory-owned,
opaque, deep-immutable adapter-result snapshots bound to one repository,
commit, V3 checkpoint, and effective assurance/closure identity. It cross-checks
the exact six lineage bytes, independent remote checkpoint bytes and time,
owner/approval, authority, runner/gate, all fifteen artifact byte lengths and
hashes, both runners' manifest/log bytes, and the trusted validation-time
ceiling. Missing, reordered, duplicate, ambiguous, orphan, mutable, oversized,
or coherently self-asserted candidate drift fails closed. This is only the
handoff contract for future reviewed adapters: the pure matcher performs no
filesystem, process, socket, network, or clock I/O, exports no acceptance or
activation API, and an exact synthetic context returns only a distinct dormant
non-authorizing sentinel. Nine mutation tests cover this boundary. No real
independent adapter result, consumed-bundle ledger, receipt activation, G0 exit,
or G1a authority now exists.

The separate repository/remote-source checker is intentionally below that
trust boundary. Its default path now verifies the literal `12c38154` Git
commit, parent/tree, reconstructed 18-entry scope digest, and exact six-lineage
bytes using bounded streaming reads while rejecting replace, alternate, graft,
shallow, and promisor state before and after inspection. It does not consult
HEAD, the index, or worktree document bytes. This evidence path intentionally
requires a normal checkout with a complete local object store; shallow clones
and linked worktrees fail closed instead of borrowing ambiguous object provenance.
Its remote half contains no socket
client and can only match supplied bytes while recording collector/TLS
authentication and `refs/heads/main` reachability as false. Eight mutation tests
pass, but these mechanical observations cannot enter the generic context, do
not satisfy any of the seven independent trust inputs, and close no G0 blocker.

The required external consumed-bundle ledger is not a caller-selected local
directory. A same-UID marker implementation cannot guarantee one global
namespace across alternate paths or hosts and cannot by itself prevent
directory replacement, snapshot rollback, backup restore, or unauthenticated
claim exhaustion. Before any stateful activation, one separately provisioned
versioned namespace must have an authenticated sole writer/coordinator,
cross-host serialization, rollback/restore reconciliation, canonical 7/7-
validated target/bundle binding, and durable parent-entry semantics. No local
substitute is retained by the current successor.

`proposed_as_written` requires owner/evidence input and no change reference;
`proposed_with_changes` requires the exact blocker-bound change reference; and
`not_available` forbids owner, evidence, and change candidates. These are intake
dispositions only, never accepted decisions.

The immutable G0 records retain their historical `blocked_before_g1a` value and
ten enterprise release-evidence gaps. As of 2026-07-22, the active personal-
project decision supersedes those owner-governance prerequisites: local source
work, first-party compilation, tests, and G1a no-network implementation may
proceed without owner authentication, approval receipts, or a separate authority
record. Production application identifiers, distribution accounts, live service
domains, production keys, signing, store upload, and deployment remain future
release inputs rather than blockers on local implementation. Sockets and
external network execution remain closed until a bounded technical slice is
selected by current user direction.

The local owner-trust-bootstrap v2 successor,
`docs/v1/g0/owner-trust-bootstrap-profile-v2.json`, records the user's exact
candidate decision without authenticating it: sole account-control principal
`github:hanchangha1127`, GitHub numeric subject ID `243786110`, fourteen unique
role-scoped owner-binding/opaque-identity/receipt references, and software
`ssh-ed25519` OpenSSH SSHSIG. Its raw SHA-256 is
`13a3b3a5097b443620f049ad69663c486810945436e1c484f3a79cc8635c53f3`.
The static contract binds exact raw and canonical receipt digests, role
credential/public-key identity, independently issued challenges, canonical
70-character/LF OpenSSH armor and exact Ed25519 SSHSIG wire structure, one-way
revocation-to-registry digest binding, exact status-reference closure, null
external root selectors, paired registry/revocation high-watermarks, JCS envelope
and fourteen-role manifest bytes, RFC 3161 time evidence, and external atomic
replay consumption. Structural SSHSIG parsing is not cryptographic verification.
This G0 owner-bootstrap SSH credential path forbids private-key
generation, discovery, loading, storage, agent/environment/Keychain lookup, and
signing invocation. All
operational selectors remain null, all authority state remains false, and the
adapter is not implemented. Independent root/public-key enrollment, proof of
control, authenticated selector decision, registry/revocation/time adapters, and
the external consumed-bundle ledger remain external prerequisites. Twenty-five v2
mutation tests and the combined ten-suite, 185-test focused G0 run pass; nine
checker entry points pass directly while publication receipt remains suite-only
without an executable `main`. This is supplied-byte static evidence only.

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

The local readiness-only addendum
`docs/v1/g0/external-evidence-candidate-profile-v1.json` is pinned at raw
SHA-256 `8670a9c5a948b5c0e89ffd3fcd6561f4dcb51776a6d5c174f6a12c5a587c9848`.
It content-addresses the existing five-kind baseline and two-kind supporting
profiles, then derives the remaining eight non-derived V3 evidence kinds in
canonical order. This brings typed candidate readiness to 15/15 kinds without
creating any candidate instance: eight candidate artifacts remain absent. Its
null selectors, false trust/authority states, field-specific digest-only
candidate reference classes, exact offline-root/online-signer policy projection,
emergency-versus-release-signing assignment separation, the 30-second expired-
authorization deletion SLA, current-versus-previous provider-version separation,
and the synthetic v1 `KRW` fixture are enforced; selecting a real billing
currency requires a new v2 profile. The supplied-byte validator
does not provide external values, authenticate an
owner, verify evidence, accept a receipt, close a blocker, exit G0, or grant
G1a. The earlier pre-v2 complete expanded default no-device aggregate exited zero
after the then-final profile/checker/test bytes were present and before its
evidence-only wording correction. It included a 192-test initial Python batch,
all 1,809 Swift
tests with two environment-dependent skips, 23 macOS render smokes, selected
offline Android suites/build tasks, and both Swift products. Its stdout was not
persisted or signed. Fresh copy/docs/diff guards, not that aggregate, cover the
current document bytes. A later v2-inclusive but pre-final-hardening complete
aggregate also exited zero with a 207-test initial Python batch and the same
Swift/render/Android/build stages. It covered the earlier 15-test v2 suite, not
the ten later registry/type/SSHSIG hardening tests; its temporary stdout was
deleted because it contained ephemeral pairing material and was not signed.
The final post-hardening complete aggregate also exited zero on the current
25-test v2 bytes with an initial 217-test Python batch; its full-Swift completion
assertion, render-smoke, selected offline Android, Swift-product, copy/docs, and
final success-marker stages passed. The temporary stdout was deleted because it
contained ephemeral pairing material and was not signed.

### G0 - Freeze The V1 Contract And Publish A Baseline

Objective: turn the current strong v0.1 checkpoint into one reproducible base
and eliminate product, authority, and release ambiguity before cross-cutting
changes begin.

Work packages:

- Preserve `main@d32c1846` as the selected implementation baseline and
  `12c381547935b96d383ac39976261ea6c3ce6a5b` as the intentionally published G0
  V2/V3 checkpoint. Preserve every V1/V2/V3 byte. Preserve the published,
  tracked dormant publication-receipt sidecar and empty sparse owner/catalog
  input candidate at `70350f5e`; do not activate them or mix transport work into
  them. Preserve the published seven-file truth-sync and dormant preview compiler
  at `025a4ef5` and its exact remote readback. Preserve the published sixteen-file
  observation, two-selector, non-authorizing evidence-readiness, candidate
  independent-context, and mechanical repository/remote-source successor
  at `b24c5ecb` and its exact 16/16 remote readback. Preserve the historical twelve-file
  owner-trust-bootstrap/external-readiness successor at `4227204` and its exact
  12/12 public HTTPS API/raw-content remote-byte readback. Its published
  historical twelve-path scope does not constrain the current personal-project
  worktree. Follow the active queue above for G1a implementation.
- Approve the V1 definition in this section, including whether P2P is a GA gate.
  Under this canonical plan it is required for eligible networks; a relay-only
  build must remain a pre-V1 beta unless an explicit versioned product decision
  changes that rule.
- Fix the supported Android API/device/OEM, macOS version/architecture, Ollama,
  LM Studio, localization, and network matrix. Confirm whether Intel macOS is a
  supported V1 architecture rather than assuming it from Apple Silicon builds.
- Choose Android and macOS distribution channels, production application and
  bundle identifiers, version/build-number policy, update model, minimum
  rollback window, and N/N-1 compatibility policy.
- Decide the Android pre-release data transition before changing application id
  or signing lineage: either retain a compatible id/signing lineage, implement
  an explicit reviewed export/import path, or declare development `0.1.0`
  installs non-migratable and require clean install plus fresh pairing. The
  current debug-signed app with backup disabled cannot be assumed upgradeable.
- Select the production relay/control-plane option and the pair-epoch recovery
  option from their gated portfolios, and decide whether one-sided deny-only
  revoke is an accepted denial-of-service tradeoff. The currently approved
  `production_p2p_nat_v1_recommended` profile requires standards-based TURN plus
  a sealed AetherLink emergency fallback. Retaining it makes both data planes V1
  scope. Choosing a single-plane TURN or sealed-relay profile is a new product
  and security decision that must explicitly supersede the existing profile and
  selection decision; it must version and re-approve the changed fallback state
  machine, no-network vectors, security manifest, rollback policy, and release
  evidence. A generic relay selection does not silently remove either existing
  requirement.
- Approve the service trust-root owner, delegated online key custody, rotation
  overlap, emergency revocation owner, privacy policy, log retention, incident
  owner, relay-region plan, and cost/capacity owner.
- Freeze a versioned error taxonomy and measurable targets for setup,
  reconnect, handoff, revocation, crash-free operation, soak stability, and
  relay capacity. A target without an owner, measurement source, sample rule,
  and failure action is not a release SLO.
- Refresh the V1 threat model, protocol inventory, data-flow inventory, test
  matrix, risk register, and release checklist against the checkpoint commit.

Required artifacts:

- Versioned V1 scope/architecture decision and supported matrix.
- Versioned security requirements/ADR, compatibility requirements, and
  migration policy. G1 owns the exact wire/crypto profile and vectors.
- Updated threat model and privacy-safe observability schema.
- Versioned selection decisions for relay allocation, fallback profile, pair
  epoch/revocation, and their implementation boundaries. Any one-plane choice
  explicitly names the superseded profile and decision plus every replacement
  artifact; absent that supersession, the existing two-plane profile governs.
- Separate staged authority records for relay implementation and any P2P/NAT
  candidate work.
- CI tiers, device/network/provider matrix, release checklist, incident and
  rollback runbook skeletons.

Exit gate:

- The baseline is reproducible and intentionally published, or an explicit
  decision records why work continues on a dirty tree.
- Every required V1 capability and non-goal has an owner and acceptance method.
- Trust root, pair recovery, supported platforms, distribution channel,
  telemetry boundary, service ownership, and SLO decisions have no unresolved
  release-blocking question.
- Existing no-device gates and release compilation pass from the selected base.

Stop conditions: do not begin G1 implementation or live-network work while the
trust root, secure-session requirements, relay/recovery selection, pair epoch
model, supported topology, migration policy, or authority owner is unresolved.

### G1 - Production Secure Session And Allocation Contract

Objective: turn the approved G0 requirements and selections into one exact
endpoint-authenticated security contract, then implement it through separately
authorized no-network and loopback phases. The contract remains invariant
across local direct, P2P, and relay paths.

Authority split:

- G1a is no-network work: schemas, canonical encodings, vectors, parsers,
  persistent-state transitions, migration rules, and injected transport tests.
- G1b may implement and exercise loopback-only TLS and record transport only
  after the exact relay design is selected and a separate implementation,
  compilation, and loopback-socket authority is recorded.
- Controlled or external service/network execution belongs to G3 and later
  gates. Completing G1a never grants G1b or G3 authority.

Current G1b-A status (2026-07-23): the Android normal dependency graph owns an
empty `AndroidProductionRuntimeActivationController` bound to its exact
`PairingStore` and trusted clock. It is a real composition/ownership path but
publishes no production route until an external verifier and selected P2P stack
supply a verified attempt and an already-connected one-use endpoint. Injected
real-fixture manager and ViewModel E2E tests exercise that path without legacy
fallback or OS socket creation. Publication generation is assigned before
durable admission, making the latest-started attempt authoritative; close,
cancellation, or supersession reclaims attempt-owned key/endpoint material, and
displaced cleanup executes outside controller locks. The focused controller
suite passes 12/12, the full Android app suite passes 1,174, and an independent
final audit reports no P0-P3 finding. macOS implements the accepted-raw listener
primitive with an IPv4-loopback-only policy and bounded one-slot authorization;
its tests inject connection I/O, do not start the listener, and execute no
socket. `CompanionAppModel` wiring, the actual P2P endpoint stack, live socket
close-interruption proof, network evidence, and device evidence remain open.

Work packages:

- Authenticate the allocation channel with TLS 1.3 using an explicit production
  trust source. Keep development route classes, ports, credentials, and feature
  gates separate from production.
- Define two service-signed, short-lived capability states. Initial QR bootstrap
  is runtime-bound, one-use, narrowly scoped, and protected by short expiry plus
  a durable consumed tombstone because the new client identity is not known
  yet. Only after the protected pairing exchange accepts the client may the
  service issue a paired lease binding runtime and client identities and roles,
  pair epoch, generation, nonce, expiry, allocation/route data, service key id,
  and algorithm/profile identifiers.
- Establish peer-verifiable endpoint key exchange. Bind both paired identities,
  roles, ephemeral keys, pair epoch, generation, nonces, selected suite, and a
  typed `route_authorization_kind` plus its canonical digest into the transcript.
  Local direct binds QR-pinned pair state and its nominated local path receipt
  without requiring a service lease. P2P direct binds rendezvous/candidate
  generation and ICE path-validation context, plus a signed route capability
  only when one was issued. Sealed-relay and TURN-relay paths must bind their
  signed lease/capability and exact allocation/path context. No digest type may
  be accepted under another route kind.
- Add replay windows, ordered record handling, expiry, rekey, clock-skew bounds,
  transcript confirmation, and explicit downgrade rejection. Relay reachability
  or service authentication must never substitute for endpoint authentication.
- Add monotonic pair epoch and service keyset state, deny-only emergency
  revocation, fresh-QR key replacement, idempotent transition identifiers,
  signed pair-status reconciliation, and rollback-resistant local persistence.
- Define protocol N/N-1 rollout and rollback so an older client cannot lower
  the pair epoch, keyset version, generation, or secure-session profile.

Evidence and exit gate:

- Canonical Swift/Kotlin vectors cover valid handshakes, every typed route
  authorization context, applicable lease/capability verification, key
  derivation, record protection, rekey, revoke, and migration.
- Negative and mutation suites reject MITM substitution, identity/role swaps,
  altered ephemeral keys, nonce/epoch/generation/route-authorization changes,
  cross-kind digest substitution, replay, truncation, clock abuse, rollback,
  and every production-to-development downgrade before application-ready state.
- Fuzz and bounded-parser suites cover all new untrusted messages and persistent
  records; crash injection proves transactional recovery.
- After G1b receives loopback authority, packet and log inspection finds zero
  traffic keys, provider URLs, prompts, responses, files, memory, raw QR
  payloads, route secrets, or stable device identifiers.
- An independent security review has no unresolved P0/P1 finding and every P2
  has an explicit release disposition.

Stop conditions: G1a stops before socket creation. G1b stops unless its exact
selection and loopback authority exist. No later socket or external-network
phase may proceed if peers can become application-ready through a legacy/plain
fallback, relay trust is used as endpoint identity, cross-platform vectors
disagree, or lower epoch/keyset/generation state can be accepted without
detection, fail-closed behavior, and signed status reconciliation.

### G2 - Select A New P2P/NAT Stack Under Fresh Authority

Objective: select a maintained, bounded, auditable cross-platform stack without
reusing the rejected `libjuice`/`libnice` decisions or their consumed authority.

The required authority ladder is sequential and immutable:

Here, authority means a versioned local technical-scope decision. It never
means repository-owner authentication, a GitHub login, an SSH/GPG signature,
or a user-supplied approval receipt.

1. Requirements, maintenance, license, privacy, platform, and threat review.
2. Official-source identity, version/hash, signature, and acquisition decision.
3. Offline static source and dependency review with secret/logging, redirect,
   resolver, callback, threading, shutdown, and pre-I/O destination controls.
4. Dependency closure, license inventory, SBOM, reproducible-source manifest,
   and patch policy.
5. Compile-only integration for declared Android and macOS architectures.
6. ABI, sanitizer, fuzz, malformed-input, deterministic-shutdown, and
   no-network conformance.
7. Loopback-only sockets with exact process and destination policy.
8. Destination-allowlisted controlled-network execution.

Each rung needs its own input identity, commands, captured evidence, decision,
consumed authority, rollback rule, and next permitted action. A later rung is
not implicitly authorized because an earlier one passed.

G2 ends at the specifically authorized controlled-network candidate evaluation.
G4 owns a new explicit authority for external test-network P2P integration, and
G7 owns the separate production deployment decision. Listing those later gates
here would not authorize them and would make G2 depend circularly on G4/G7.

Candidate acceptance requirements:

- Supported licenses and active maintenance with a documented upgrade/CVE path.
- Bounded candidates, attributes, callbacks, tasks, timers, queues, logs, and
  shutdown time; cancellation and ownership must be explicit.
- No hidden bootstrap, telemetry, redirect, DNS, proxy, STUN, TURN, or other
  egress before destination policy approves it.
- Configurable privacy mode, candidate redaction, mDNS/host-candidate policy,
  consent freshness, credential lifetime, and log suppression.
- Clear separation between reachability and AetherLink authentication/session
  crypto. Third-party library crypto must not silently redefine the V1 endpoint
  identity contract.
- Deterministic Android/macOS build inputs and a stable minimal ABI surface.

Historical pre-acquisition result at_that_checkpoint (2026-07-23): the
[requirements and official-source preflight](security-hardening/production-p2p-nat-v1/g2-requirements-review-v1.md)
selected no library and performed no retained source acquisition, compile,
load, socket, or network operation. PJNATH 2.17 remained rejected under that
checkpoint's license and lifecycle profile, and Google libwebrtc native remained
rejected as an oversized rolling dependency surface. Exact public source for
Pion ICE v4.3.0 commit `1e8716372f2bb52e45bf2a7172e4fb1004251c46`
then established that the unmodified candidate logs the remote ICE password,
has callback queues without a declared bound, can wait indefinitely on blocked
callbacks, and lacks one non-bypassable post-resolution policy across Active
ICE-TCP, proxy/mux, STUN, TURN, mDNS, and final send paths. Its disposition is
therefore `rejected_at_official_source_preflight_as_is`. A new exact candidate
or a maintained restriction/fork proposal must restart at the appropriate
pre-acquisition rung. This result opens no acquisition, compile, socket, or
network rung.

Historical restricted-fork rung-one result at_that_checkpoint (2026-07-23): the hash-pinned
[design portfolio](security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/hardening.md)
compares unmodified upstream, a wrapper-only gateway, and a minimal
AetherLink-maintained policy-owned fork. Only the restricted-fork shape is
`pion_restricted_fork_profile_ready_for_rung2_decision_only`;
no library or source is selected. Schema 1.1 is a not-yet-implemented design:
it requires separate single-use egress authorization immediately before socket
create/bind/connect/TLS/write and bounded ingress read/parse/admission before
state mutation or delivery; authenticated TURN TLS service identity before
credential transmission; and one-use pre-auth promotion only after exact
AetherLink endpoint confirmation. It also requires exact current, active,
draining, and closing session/process bounds, an independent sticky terminal
latch, secret-free diagnostics, non-profile paths to fail before I/O, and a
2,500 ms total close deadline. None of those controls is runtime-verified. The
profile also records the future
compile-only V1 matrix for Android `arm64-v8a` API 26...36 and macOS 14+
`arm64`, plus later exact
toolchain, dependency, SPDX SBOM, license, patch, symbol, and reproducibility
evidence. Its validator and 17 mutation tests pass. At the recorded
`at_that_checkpoint`, the profile selected no library and authorized no
acquisition. The later rung-two acquisition consumed its exact one-use request
and retained verified bytes without extraction. Rung-three v1/v2 failed closed
before publication, while v3 completed bounded lexical inventory and tracked
readback. Semantic-review decision v1 was then consumed, patch/dependency
decision v1 completed its preparation-only successor, and the historical
dependency-review decision selected only the staged fixed-point source-closure
plan. The predecessor wave-one decision completed its recorded source-identity
and request-contract preparation without acquisition. Its recorded next action
was satisfied by the one-use execution permit, which is now consumed after the
terminal ratio-policy failure. Recovery decision v1 then selected the separate
v2 policy; that permit was consumed by tuple-11 `E_GO_MOD_MISSING`. Recovery
decision v2 then selected the v3 design. The v3 permit was consumed exactly
once; 38 requests retained 19 verified `.mod`/`.zip` pairs, and fixed-hash
 independent readback confirms the 43-file set. Source-review v1/v2 then failed
 closed without a partial result; v3 and its independent readback recorded the
 exact 15-tuple frontier. Wave2 and Wave3 subsequently completed bounded
 acquisition plus independent readback. Combined-v2 held 101 exact source
 inputs and recorded a non-fixed 16-tuple Wave4 frontier. Wave4 decision v1
 derived complete, conflict-free H1 pairs for all 16 tuples. Its exact one-use
 permit was consumed once; all 32 resources were retained and independently
 read back twice. Combined-v3 now holds 133 exact source inputs and records a
 non-fixed 15-tuple Wave5 frontier. Wave5 decision v1 resolves all 15
 conflict-free H1 pairs and prepared 30 ordered requests without acquisition
 authority at that checkpoint. The one-use Wave5 acquisition subsequently
 retained all 30 resources, and its retained snapshot completed a separate
 two-pass independent readback. Combined-v4 then held all 163 inputs and
 projected the exact non-fixed 18-tuple Wave6 frontier. Wave6 decision v1 then
 resolved all 18 H1 pairs and prepared the exact 36-request contract without
 acquisition authority at that checkpoint. The later one-use Wave6 acquisition
 retained all 36 resources, and readback attempt
 `7fc50276e880013e1ace73920397ba3f` independently verified those retained bytes
 twice. Combined-v5 then reconstructed the exact 199 held inputs twice and
 derived `fixedPointReached=false` with an exact 15-tuple Wave7 frontier; its
 focused suite passes 25/25. Wave7 decision v1 then resolved all 15
 conflict-free H1 pairs from 18 declarations, 41 `go.mod` witnesses, and 20
 ZIP witnesses, preserved selector `false`, and prepared 30 ordered requests
 without acquisition authority. Its focused suite passes 13/13. Acquisition
 attempt `c15f4504ae880326144eca93dc91e37b` retained all 30 resources, and
 readback attempt `1839537589935de087068a5a7d5c7e14` verified the frozen
 snapshot twice and wrote its manifest last. Combined-v6 subsequently
 reconstructed all 229 exact source inputs twice, derived a non-fixed
 14-tuple frontier, and passed 25/25 focused tests. Wave8 decision v1 then
 resolved every exact H1 pair and prepared a 28-request contract without
 acquisition authority; its focused suite passes 18/18. Its separate exact
 one-use permit package passes 15/15 checker and 44/44 network-free mock/local
 runner tests. Acquisition attempt `6d8ea4473126c853b439c56a895f9c28`
 retained all 28 resources, and readback attempt
 `8618087527c005b5d19c8f902ec33557` independently verified the exact 46-file
 snapshot twice before manifest-last publication. Readback suites pass 16/16
 and 45/45. Combined-v7 subsequently projected the exact non-fixed ten-tuple
  Wave9 frontier, and Wave9 decision v1 resolved all ten H1 pairs without
 acquisition authority. Its separate one-use 20-resource permit package passes
 16/16 checker and 44/44 injected network-free runner tests. Acquisition
 attempt `df64a4816a083806020580efe953b9a7` retained all twenty resources, and
 readback attempt `2d61a0483984e9a2f77665dd3c624cb2` independently verified
 the exact 38-file snapshot twice. Readback suites pass 16/16 and 45/45. The
 read-only combined-v8 checker then reconstructed all 277 exact inputs twice,
 derived the exact non-fixed eleven-tuple Wave10 frontier at SHA-256
 `780501bca37fbeb953590004ca7e5aad7f206083f749b920e2a9842b63675f82`,
 and passed its final checker and test gates. Wave10 decision v1 then resolved
 all eleven identities and bound the exact 22-request set. Acquisition attempt
 `ffe70ee4562fcfc9e0fd6c9c4e136bd9` retained those resources, and readback
 attempt `e74e030f7f5ef33589d7895e1b28b3b1` verified them twice before
 manifest-last publication. Combined-v9 then held 299 exact source inputs,
 reconstructed the graph twice, and derived the exact non-fixed nine-tuple
 Wave11 frontier at SHA-256
 `171af951e3a67405b62ddceface1341bb6f64b08f370d3d216ede541bd011f06`.
 Its exact final suite passes 21/21. Wave11 decision v1 then resolved all nine
 exact identities twice with zero selected, blocked, or conflicting rows and
 bound the exact 18-request contract without granting acquisition. Its final
 suite passes 25/25. Acquisition attempt
 `ac18b8fda0a80a132510efd5dd17d5b7` subsequently retained all 18 exact
 resources, and readback attempt `9b4dac65f66ce9e5d53dcd8edaf4d1d4`
 verified the exact 36-file snapshot twice before manifest-last publication.
 Both one-use actions are consumed and cannot be retried. Combined-v10 then
 reconstructed all 317 exact inputs twice and derived the exact non-fixed
 four-tuple Wave12 frontier. Wave12 decision v1 is complete for its read-only
 bounded scope: four exact H1 pairs are complete and zero are blocked or
 conflicting. Its separate exact-eight permit package is materialized, passes
 18/18 checker and 48/48 fake/local runner tests. Acquisition attempt
 `f977ddcf8fc391e5915048b930beccbd` retained all 8 exact resources, and
 readback attempt `32ab6b747a02382f85f48f65e0c388c5` verified the exact
 26-file snapshot twice before manifest-last publication. Both one-use actions
 are consumed and cannot be retried. Combined-v11 reconstructed the exact
 325-input set twice, and Wave13 decision v1 resolved all four resulting H1
 pairs with zero blocked/conflicting tuples. Its decision content SHA-256 is
 `3d08d589ed9121128717215fe0d9583b6f64e59fc033e1c5f50477f6e59d5b83`,
 and its focused suite passes 27/27. Its separate exact-eight permit package is
 materialized at raw SHA-256
 `b976f9bea30a20e34df25e9d90cfa9ee4617ce825b0d28f254b5bb512b6c29a1`
 and passes 18/18 checker plus 48/48 fake/local network-denied runner tests.
 Acquisition attempt `eb05816e0b897ea8c3ad8b7089668e91` retained all eight
 resources, and readback attempt `8b5f92c9d90f825f5f3b46df0d006ef3`
 verified the exact 27-file snapshot twice before manifest-last publication.
 Both one-use actions are consumed successes and cannot be retried.
 Extraction, source loading/execution/compilation, runtime sockets/network,
 device execution, deployment, Git writes, external identity proof,
 authentication, and user action remain closed or unrequired.

Historical G2 restricted-fork rung-one status contract at_that_checkpoint:
`status=rung1_profile_complete_candidate_not_selected`,
`result=pion_restricted_fork_profile_ready_for_rung2_decision_only`, and
`recordedNextActionAtThatCheckpoint=prepare_versioned_rung2_source_identity_and_acquisition_decision`.
Rung one completes only the design, validator, and 17 mutation tests;
`implementationStatus=not_implemented`, `candidateSelected=false`,
`librarySelected=false`, `sourceAcquisitionAllowed=false`,
`dependencyInstallationAllowed=false`, `compilerInvocationAllowed=false`,
`codeLoadingAllowed=false`, `socketCreationAllowed=false`,
`networkIoAllowed=false`, `deviceExecutionAllowed=false`,
`productionDeploymentAllowed=false`, and `gitOperationAllowed=false`. The actual
backend, reliable ordered carrier, and fragmentation/reassembly remain unselected
and unimplemented. Only stack-neutral wiring may continue. Schema 1.1 remains a
not-yet-implemented and not-runtime-verified design. It requires a separate
single-use egress capability after resolution immediately before socket create,
bind, connect, TLS handshake, or write, plus fixed-size bounded ingress
read/parse/admission before state mutation or payload delivery. It requires
authenticated TURN TLS service identity before any credential transmission and
a bounded one-use pre-auth path whose atomic promotion occurs only after exact
AetherLink endpoint confirmation. Consent loss, path change, candidate restart,
capability expiry, verification failure, and session close each atomically revoke
both pre-auth and application capabilities before further I/O, state mutation,
event, or payload delivery. Exact per-session and process bounds cover current,
active, draining, and closing state, and event overflow requires an independent
sticky terminal latch. Secret-free diagnostics and a 2,500 ms total
close deadline are requirements, not completed implementation or runtime-verified
behavior. Repository-owner, GitHub, SSH, GPG, or
public-key identity proof is neither a prerequisite nor a future G2 rung;
`externalIdentityProofRequired=false` and `userActionRequired=false`.
Product pairing and endpoint authentication remain mandatory and separate.

Exit gate: one exact candidate/version is selected with complete provenance,
all authorized no-network and controlled-network evidence passes, residual risks
are accepted, and a versioned decision explicitly opens the next rung. Otherwise
G2 remains blocked with no library selected.

### G3 - Production Rendezvous And Approved Fallback Services

Objective: make every service-side component in the G0-approved fallback
profile ready for endpoint integration while keeping AI traffic end-to-end
protected from those services. For a sealed AetherLink relay, G3 owns both the
service and its independent release-like endpoint integration. For TURN, G3
owns credentials, allocation, quota, forwarding, and standards-level service
interoperability; G4 alone owns AetherLink ICE consumption and endpoint E2E.
The currently approved profile requires TURN plus a sealed emergency relay
unless G0 explicitly supersedes it under the rules above.

Work packages:

- Build authenticated allocation and rendezvous over the G1 TLS and signed-lease
  contract. Signaling exchanges only bounded, expiring, encrypted reachability
  records.
- Forward opaque encrypted records through every required sealed-relay or TURN
  data plane. No forwarding service may mint endpoint trust or possess endpoint
  traffic keys.
- Enforce short leases, one-use bootstrap semantics, pair/session/source quotas,
  connection and byte ceilings, bounded waiters, admission fairness, expiry,
  immediate revoke, and closed-by-default overload behavior.
- Persist monotonic allocation generation, pair epoch, keyset version, and
  revocation state safely across service restart and multi-instance failover.
- Implement offline-root/delegated-key provisioning, overlap rotation,
  emergency revoke, backup/restore, disaster recovery, regional isolation, and
  rollback procedures.
- Add infrastructure-as-code, secret management, health checks, capacity
  dashboards, alerts, deploy/rollback automation, and privacy-safe diagnostics.
- Record separate implementation, loopback, controlled-network, external-test,
  and deployment decisions for the G0-selected relay requirements. This
  roadmap and G1 completion grant none of those authorities.

Evidence and exit gate:

- Common service evidence covers credential issuance, bounded allocation and
  forwarding, expiry/refresh/revoke, privacy, load, restart, and failover for
  every data plane required by the approved fallback profile.
- For a required sealed relay, two release-like AetherLink endpoints establish
  the G1 secure session through staging on unrelated networks; packet capture
  exposes no application plaintext or traffic key.
- For required TURN, standards-compliant interoperability clients prove
  credential issuance, allocation, permission, channel-bind, refresh, expiry,
  quota, and forwarding lifecycle. A synthetic endpoint-encrypted payload stays
  opaque to the service. AetherLink endpoint TURN E2E is deliberately deferred
  to G4 and is not a G3 exit condition.
- Forged, expired, replayed, wrong-role, wrong-epoch, wrong-generation, and
  revoked leases fail closed. Active and waiting rooms close on revocation.
- Restart, partial outage, regional failover, clock skew, signer rotation,
  backup/restore, duplicate requests, and split-brain attempts preserve
  monotonic state and do not recreate consumed bootstrap authority.
- Load and abuse tests demonstrate configured admission, memory, descriptor,
  task, connection, waiter, and bandwidth ceilings without an open-relay mode.
- Logs and metrics pass the V1 redaction schema and incident/rollback drills are
  executable by someone other than the implementer.

Stop conditions: no production deployment while allocation is unauthenticated,
leases are unsigned, signer rotation/revocation is untested, split-brain can
lower state, the relay can decrypt application traffic, or overload opens a
weaker path.

### G4 - P2P, ICE/STUN, Approved Fallback, And Path Migration

Objective: connect eligible peers directly across unrelated networks and fall
back deterministically through the G3 services required by the approved
fallback profile without changing identity or security semantics.

Work packages:

- Select and document the supported ICE profile, candidate types, gathering and
  trickle limits, privacy mode, STUN and, when selected, TURN credential flow,
  destination policy, consent freshness, restart, nomination, and teardown
  behavior.
- Encrypt and authenticate candidate/signaling material under the G1 contract;
  never publish stable public device directories or treat a candidate as proof
  of identity.
- Implement bounded local-direct to P2P to approved-fallback route selection.
  Preserve the current trusted identity across path changes and reject stale
  session, lease, epoch, generation, or route callbacks. Route priority,
  credential authority, quota ownership, and kill-switch behavior must name the
  applicable data plane explicitly.
- Support consent loss, interface changes, Wi-Fi/cellular handoff, suspend/resume,
  ICE restart, P2P failure, relay failover, and return to a better path only
  after validation. A kill switch may force encrypted relay-only behavior but
  may never enable development/plain/anonymous fallback.
- Produce route outcomes and failure classes that the application can explain
  without exposing raw candidates, IPs, identities, or credentials.

Required network matrix:

- Same LAN, unrelated Wi-Fi networks, Wi-Fi to cellular, cellular to Wi-Fi,
  IPv4, IPv6, NAT64, carrier-grade NAT, symmetric NAT, restrictive firewall,
  VPN, interface change, host sleep/wake, client background/Doze, consent loss,
  required-fallback outage, relay regional outage when applicable, and
  deliberate P2P failure.
- Universal NAT success is not required. P2P must work on declared eligible
  topologies, and every supported topology must still meet the approved overall
  connection target when the approved fallback profile is available.

Exit gate:

- Direct P2P and each forced fallback route required by the approved profile
  complete pairing/authentication, health, model list, chat stream/cancel, and
  reconnect with the same endpoint identities and session profile.
- Interoperability, sanitizer, malformed-signaling, packet-capture, privacy,
  path-migration, timeout, resource-bound, and shutdown evidence passes across
  the declared network matrix.
- No stale route becomes application-ready; no failed route enables a weaker
  transport; route metrics match packet-level observations without logging
  protected identifiers or candidates.

### G5 - Product Lifecycle, Recovery, Accessibility, And Data Closure

Objective: close the user-visible and durable-state gaps that no-device tests
and a single debug pairing cannot prove.

Work packages:

- Complete production QR creation, optical scan, expiry, rotation, refresh,
  stale-code rejection, transient render retry, camera denial/regrant, and
  accessible recovery on release builds.
- Verify explicit trust revoke, fresh re-pair, pair epoch reconciliation,
  service-key rotation, route loss, clock skew, offline use, and actionable
  error recovery without exposing technical secrets.
- Exercise Android background/foreground, Doze, process kill, force-stop,
  reboot, storage pressure, upgrade, and rollback. Exercise macOS app/runtime
  restart, sleep/wake, network changes, provider restart, and Keychain state.
- Prove lifecycle barriers for composer/session persistence, pairing-secret
  cleanup, history/memory mutation, attachments, cancellation, terminal events,
  and migration from only the pre-release state explicitly declared compatible
  in G0. If development `0.1.0` installs are non-migratable, verify clean install,
  stale-data non-import, and fresh pairing instead of claiming in-place upgrade.
- Run the complete live-provider loop with supported Ollama and LM Studio
  versions: health, empty and populated catalog, stream, reasoning, cancel,
  provider failure, model unload/residency, history, memory, and supported
  attachment paths.
- Complete TalkBack and VoiceOver traversal, focus order, announcements,
  headings, selected state, modal behavior, dynamic type/large font, keyboard,
  reduced-motion/high-contrast where applicable, and five-locale layout/copy.

Minimum qualification matrix:

- Android API 26, 30, 33, and 36 in automation where supported, plus physical
  coverage at the minimum supported API, a current reference device, and a
  current OEM variant including Samsung. Emulators supplement but do not replace
  camera, accessibility, lifecycle, radio, and permission evidence.
- macOS 14, latest-minus-one, and latest on every architecture declared in G0.
- Font scales 100%, 150%, and 200%; Korean, English, and smoke coverage for all
  five supported locales.
- Each supported Ollama and LM Studio compatibility target, including clean
  absence, provider unavailable, malformed/oversized metadata, and cancellation.

Exit gate:

- No P0/P1 product, data-loss, security, accessibility, or lifecycle defect is
  open; every P2 has an approved release disposition.
- Required release-device scenarios complete without crash, ANR, trust loss,
  stale secret revival, duplicate terminal event, transcript corruption, or
  unauthorized provider call.
- Sanitized evidence records source/build identity, device/OS class, route
  class, milestones, and explicit non-claims without retaining QR or secrets.

### G6 - Release Engineering And Release-To-Release Qualification

Objective: replace development artifacts with reproducible, installable,
upgradable, supportable release artifacts and prove the complete V1 loop between
them.

macOS deliverables:

- Production bundle identifier and semantic/build version policy.
- Channel-specific signing and distribution. Direct distribution requires
  Developer ID Application signing, hardened runtime, least entitlements,
  strict nested-code verification, notarization, stapling, and the G0-selected
  signed DMG. PKG and Mac App Store distribution are outside the current V1
  decision and would require a new versioned release-channel decision plus their
  own signing, custody, install, review, and update gates.
- Clean-machine install, first launch, permission and Keychain behavior,
  upgrade, rollback, uninstall, configuration migration, and recovery testing.
- Update-channel and rollback strategy with N/N-1 protocol compatibility and
  monotonic pair/keyset state protection.

Android deliverables:

- Final production application identity, versionCode/versionName policy, release
  keystore custody or Play App Signing, and signed AAB/APK.
- R8/resource-shrinking decision, mapping/native-symbol archive, dependency and
  permission review, backup/export policy, and release secret isolation.
- Clean install, upgrade only from a G0-declared compatible package/signing
  lineage, or the approved export/import or fresh-pair transition when that
  lineage is unavailable; process/reboot survival, rollback behavior,
  channel-appropriate pre-launch/internal/closed distribution checks, and final
  manifest/network-security validation.

Shared supply-chain deliverables:

- Pinned dependencies, license inventory, SBOM, vulnerability review, build
  provenance, artifact checksums/signatures, secret scan, reproducible unsigned
  payload/build-manifest comparison where practical, and retained
  symbols/mappings for incident use. Timestamped signatures and notarization or
  store receipts are provenance-tracked rather than required to be byte-identical.
- CI-generated release notes, compatibility matrix, migration notes, known
  limitations, support diagnostics, privacy disclosure, and rollback procedure.

Exit gate:

- Installed signed Android release and installed channel-valid macOS release
  complete physical camera pairing, authentication, health, model list, live
  chat stream/cancel, history/memory, restart, and trusted reconnect on local
  direct, P2P, and every forced fallback route required by the approved profile.
- Gate evidence identifies exact source and artifact digests. A locally rebuilt,
  debug, ad-hoc, or unsigned artifact cannot substitute.
- Clean install, N/N-1 upgrade for the declared release lineage, the G0-selected
  pre-release migration or fresh-pair policy, service/client rollback, and
  uninstall paths pass without lowering pair epoch, service keyset, generation,
  or transport security.

### G7 - Release Candidate, Operations, And Staged GA

Objective: prove the product and service can be observed, operated, revoked,
recovered, and rolled back under production-like load before calling it V1.

CI and evidence tiers:

| Tier | Trigger | Required coverage |
| --- | --- | --- |
| PR fast | Every change | Schema and canonical vectors, docs/copy/security contracts, focused Swift/Kotlin units, affected compilation, deterministic static checks. |
| Merge full | Every accepted merge | Complete Swift and Android unit suites, release builds, no-device aggregate, sanitizer/fuzz seed corpus, SBOM/license and secret checks. |
| Nightly product | Scheduled | Emulator/device lifecycle, accessibility, localization, live Ollama/LM Studio smoke, migration, install/upgrade, and failure injection. |
| Controlled-network nightly | Authorized environment | Local direct, P2P, every approved-profile fallback route, network handoff, revoke/expiry, packet privacy, and route-metric correlation. |
| Weekly resilience | Staging | Long soak, load, descriptor/memory/thread stability, relay restart/failover, signer rotation, backup/restore, abuse and chaos drills. |
| RC | Tagged source | Reproducible unsigned payload/build manifests plus provenance-traceable signed artifacts, release-to-release physical/device/network matrix, full security review closure, runbook rehearsal, and rollback proof. |

Current implementation status: the repository contains only a bounded G7
non-security CI subset. It covers read-only pull-request static checks, exact
Swift/Android product test allowlists, affected compilation, a 222-identity
Swift discovery preflight, the 78-test release archive contract, and Release
APK/AAB compilation, lint, and direct output readback on pull requests and
`main`. The macOS lane additionally executes an offline checked-in compliance
catalog validation and the exact 22-test deterministic SPDX/license render plus
independent reconstruction manifest with zero skips; it does not refresh network evidence or
claim binary analysis or a legal compatibility conclusion. The lane also runs
35 current-unsealed lifecycle runner tests, 11
portable evidence-checker snapshot/schema tests, and eight portable current-run
checker tests without requiring ignored evidence. After the `main`-only
unsealed package build and readback, it runs the macOS Release diagnostics
producer/readback, then two lifecycle observations and an independent
current-run checker against the private generated evidence.
It includes a tracked-only 36-document contract that
passes in a temporary tracked snapshot without `.git` or ignored `dist/`, plus
two exact mode regressions. The full local checker retains the portable
fail-closed contracts; historical raw readback is archival, while current raw
readback remains bound to its producer on `main`. The `main`-only complete Android step is ordered as pre-run source
marker, forced 19-class run, canonical result binding/readback, then the shared
`assembleRelease`, `bundleRelease`, `lintRelease`, and direct readback steps;
current local evidence passes 1,226/1,226 and 78/78. Hosted run
`30525374687` proves only that the two baseline jobs passed at commit
`0f59c757d745d0b95c37c9b93aec8d354bcfef9f`. That
historical 159-test result predates commit
`53f45d4e9909dd77520a450170eb87c7d260ea89` and does not cover the current
unstaged wrong-port/port-replacement, startup pairing gate, development-server
late-failure, Swift discovery contract, complete Android main lane, checker,
or documentation follow-ups. The canonical
rows above deliberately remain unsatisfied:
excluded security/authentication/cryptography checks are not silently
relabeled, broad mixed suites are not invoked, and no nightly, physical-device,
network, signing, publication, or deployment evidence is claimed. SwiftPM and
Gradle still compile their complete package/app test-source graphs before
applying the execution selectors, so this is not a separately built
non-security test target. The Android hosted lane also depends on its runner
image's SDK 36/Build Tools 36.0.0 inventory and normal dependency downloads;
dependency-byte hermeticity remains open.

Privacy-safe observability may record aggregate route attempt/success, fallback
reason class, setup/reconnect latency, ICE restart or consent loss, relay
occupancy/bytes, authentication rejection class, lease/revoke latency, crash or
ANR, and version/region class. It must not record raw IP/candidates, device or
key fingerprints, pair/relay identifiers, QR or route/allocation tokens, keys,
prompts, responses, files, memory, model names, or provider/backend URLs.

The selected G0 release targets below are not current product claims:

- At least 1,200 authenticated sessions complete across the twelve-cell required
  matrix, with at least 100 attempts per topology cell and 30 attempts per
  required symmetric-NAT, consent-loss, deliberate-failure, or outage variant.
  Each cell requires at least 99% observed success and a 95% Wilson lower bound
  of at least 95%.
  A separately reported usage-weighted total cannot hide a failing NAT64,
  CGNAT, restrictive-network, mobility, or outage cell. Native-IPv6 and
  home-NAT P2P-required cells additionally require at least 95% observed direct
  success and a 95% Wilson lower bound of at least 90%; fallback cannot satisfy
  that gate. Other attempt-required cells report direct P2P as a separate KPI.
- Traversal setup is at most 1.5 seconds p50, 5 seconds p95, and 10 seconds p99.
  Full cold setup is at most 8 seconds p95 and 15 seconds p99; authenticated
  reconnect is at most 5 seconds p95; network handoff is at most 10 seconds p95;
  revocation closure is at most 10 seconds p95 and 30 seconds p99.
- Zero false acceptance for stale, replayed, revoked, downgraded, wrong-identity,
  wrong-role, wrong-epoch, or wrong-generation sessions.
- Zero application plaintext, traffic key, route secret, QR payload, or provider
  URL in packet/log/privacy negative tests.
- Closed-beta crash-free and ANR-free session rates are each at least 99.5%.
  One 24-hour RC soak has zero crash or ANR, and capacity passes at twice the
  approved projected peak without unbounded RSS, descriptor, task, thread,
  room, waiter, or queue growth or a weaker admission mode.

Rollout sequence:

1. Internal dogfood with production security and staging services.
2. Closed external beta across the required device, provider, and network matrix.
3. Small production cohort, then larger cohorts, with a predeclared observation
   window and error budget at every promotion.
4. GA only after service and client rollback, signer rotation, emergency revoke,
   incident response, capacity, and disaster-recovery drills pass.

Rollback may disable P2P/direct promotion and force the G0-designated emergency
route within the approved encrypted fallback profile. It must never enable
development, plaintext, anonymous, stale, or unauthenticated fallback. Client
and service rollback must honor N/N-1 compatibility without lowering monotonic
pair, keyset, generation, or revocation state.

GA stop conditions:

- Any open P0/P1, unresolved transport/security P2, SLO miss, error-budget
  exhaustion, or incomplete release-to-release matrix.
- Signing, channel validation, artifact identity, key rotation, revocation,
  backup, restore, incident, or rollback drill failure.
- Unredacted telemetry or logs, a relay that can recover application plaintext,
  a weaker downgrade path, or a required route without privacy evidence.
- Release artifacts that do not match the reviewed source and provenance.

### Evidence Ladder And Claim Boundary

| Evidence rung | It can prove | It cannot prove |
| --- | --- | --- |
| Static and no-device | Compilation, deterministic state machines, schemas, vectors, mutation/fuzz seeds, resource ceilings, and release-build construction. | Camera, screen reader, OS lifecycle, radio behavior, external reachability, service reliability, or production readiness. |
| Physical same-LAN | Actual QR rendering/scan, permissions, paired authentication, local route, lifecycle, accessibility, and provider interaction for the tested artifacts. | Unrelated networks, P2P, approved-profile fallback routes, production service, or another device/OS. |
| Controlled external network | Exact P2P and every approved-profile fallback path, NAT/network matrix, handoff, packet privacy, failure injection, and service restart for release-like artifacts. | Signed-store distribution, production capacity, long-run reliability, or GA readiness. |
| Signed RC and staging | Install/upgrade/rollback, channel-specific signing and validation, release-to-release E2E, soak/load/chaos, key rotation, revoke, and operational runbooks. | Production outcomes outside the measured cohort, topology, duration, and capacity. |
| Production rollout | Real error budget, capacity, incident and rollback behavior for the promoted cohort. | Universal NAT traversal, zero metadata leakage, or unsupported platforms and networks. |

No evidence from a lower rung may be phrased as if it completed a higher rung.
Every retained artifact must record source identity, build identity, environment,
route class, result, and explicit non-claims without storing credentials or user
content.

### V1 Risk Register

| Risk | Current signal | Mitigation and decision gate |
| --- | --- | --- |
| No accepted P2P library | `libjuice`, `libnice`, and Pion ICE v4.3.0 as-is remain rejected. The restricted-fork review preserved the 19 findings, completed source acquisition/readback through Wave19, produced a Combined V18 empty-frontier fixed-point candidate, accepted only its dependency-graph fixed point, and completed the source/license preparation package without completing either independent review pass. | Preserve all seven patch-required and twelve unresolved findings. Complete the bounded per-file semantic, special-source, broad-license/`PATENTS`, SPDX/provenance/binary, and native-profile review coverage. Extraction, compilation, runtime sockets/product networking, and product operation remain closed until their ordered gates. |
| Security contract spans every route | Current development paths have stronger pieces but no complete production profile. | Freeze G1 before networking; use one cross-platform vector suite and prohibit route-specific downgrade. |
| Relay becomes an authority or data observer | Current allocation transport is development-grade. | TLS plus signed leases, endpoint KEX, blinded payloads, split-compatible capability shape, packet/log privacy tests, and operational key separation. |
| Infrastructure becomes the schedule bottleneck | Production allocation, signaling, relay, key custody, monitoring, and incident ownership are not deployed. | Assign an owner and service plan in G0; develop G3 alongside G2 after G1. No client-only workaround counts as progress. |
| Physical evidence is too narrow | One debug Samsung/same-Wi-Fi run is the current optical proof. | Maintain the G5/G6 device and network matrix; preserve no-device versus physical versus production labels. |
| Release pipeline is absent | Ad-hoc macOS signing, no Android production signing, and no repository CI workflows. | Begin signing/provenance/CI work during G1-G3 rather than after networking completes. |
| Advanced features displace launch work | The repository already contains broad memory, research, permission, and future-platform plans. | Treat them as maintenance-only unless required for compatibility or a release blocker; keep the canonical critical path above. |
| Historical docs or mixed work obscure truth | The implementation baseline, bounded G0 V2/V3 packet, nine-file receipt/intake successor, seven-file truth-sync/compiler successor, sixteen-file evidence-readiness/source successor, and historical twelve-file owner-bootstrap/external-readiness successor are published with fresh exact remote-byte readback for `12c38154`, `70350f5e`, `025a4ef5`, `b24c5ecb`, and `4227204`. The latest 12/12 readback manifest SHA-256 is `267be3ca8f56fe353fbb856f95c6f634e98afbc3f204b589a9935be0fe5b0a15`. The current unpublished scope adds G1b-A Android normal-graph ownership, injected manager/ViewModel E2E, the macOS loopback-only accepted-raw primitive, and the G2 restricted-fork lineage through consumed Wave19 acquisition/readback plus the Combined V18 fixed-point and closure-review decision to the completed socket-free G1a foundations; older version labels describe historical feature themes. | Keep historical G0 bytes isolated, synchronize the handoff/progress/QA current entries, and let the active personal-project queue govern implementation while the handoff governs evidence. |

### V1 Definition Of Done

V1 is complete only when all of the following are true:

- The exact supported Android, macOS, architecture, provider, locale, and network
  matrix is versioned and tested with signed release artifacts.
- Fresh production QR pairing, trust, authentication, local direct, eligible
  P2P, every fallback path required by the approved profile, route refresh,
  revoke, re-pair, restart, reconnect, and handoff meet their approved contracts
  and SLOs.
- Health, model list, live chat/reasoning stream, cancel, history, memory, and
  supported attachments work through the Runtime on both supported providers.
- Every route uses the same identity-bound secure session, rejects replay and
  downgrade, preserves monotonic epoch/keyset/generation state, and exposes no
  protected payload or secret to relay, logs, diagnostics, or client storage.
- Camera recovery, app/runtime process lifecycle, TalkBack, and VoiceOver pass
  required physical-device evidence. Keyboard, large text, localization, and
  responsive layout pass rendered/semantic automation plus the physical checks
  assigned by the G0 support matrix; rendered tests cannot substitute for the
  device-only flows.
- Clean install, declared release-lineage upgrade or approved fresh-pair
  transition, rollback, uninstall, channel-specific signing/distribution,
  provenance, SBOM, and incident artifacts are complete and reproducible.
- Required CI, device, provider, external-network, soak, load, failure, rotation,
  revocation, restore, and rollback gates pass with no open P0/P1 and an approved
  disposition for every P2.
- The staged production cohort stays inside the approved error budget and the
  go/no-go authority signs the final release record.

### Immediate Execution Queue

1. Preserve the published V1/V2/V3 and owner-trust artifacts as historical bytes;
   do not build an owner-authentication adapter, collect role receipts, request a
   signature, or create an external owner-governance ledger.
2. Completed G1a-A: Swift and Kotlin now share one socket-free canonical
   endpoint session transcript across local-direct, P2P, TURN, and sealed-relay
   routes, with route kind/digest, pair epoch, both endpoint nonces, capability
   binding, keyset/revocation state, and deterministic byte vectors.
3. Completed G1a-B: Swift and Kotlin now share canonical authority/snapshot
   bytes and transition/admission outcomes. macOS and Android persist monotonic
   pair state, a 20-entry lifetime transition ledger, and the replay tombstone
   before returning an opaque permit. Epoch advancement is denied until signed
   fresh-pair proof exists. Persisted production state forces both apps to reject
   legacy-only connection paths; the incomplete pre-connector seams are internal
   and dormant rather than active production integration.
4. Completed G1a-C contract readiness: root-pinned service keysets, signed
   pair-status/fresh-pair/route and candidate capabilities, endpoint proofs, four
   fixed-order post-commit receipts, and exact object-25/26 grant projection now
   match across Swift, Kotlin, and both pinned fixtures. Object 7 binds the exact
   object-26 digest; generic P2P admission and untrusted Android verified-wrapper
   construction fail closed. This remains
   `synthetic_contract_readiness_only` with
   `productionDurabilityClaim=false`; it proves no activation, physical-device
   behavior, socket/network operation, deployment, or production readiness.
5. Completed G1a-C compound durability parity: macOS and Android now commit the
   pair snapshot, endpoint ledger, and marker chain as one canonical store
   image, reread exact bytes before returning authority, and use a store-owned
   clock to reject not-yet-valid, expired, or regressed token issuance. Raw
   pair/session mutation APIs remain unavailable to production app adapters;
   idempotent restart and committed retry return readback only.
6. Completed exact-bound no-network coordination: each store caches one
   coordinator that accepts only a verifier-minted binding plus an APPLIED
   durable compound token, revalidates the exact latest ledger entry and marker
   three times around start, uses only the store clock, and fences replay,
   cancellation, revocation, authority advance, expiry, and late completion.
   Explicit operation-scoped callback context prevents detached self-wait;
   generation-scoped idempotent cleanup covers both immediate fencing and late
   publication, and pair admission remains quarantined until cleanup finishes.
   Android retains failed cleanup for retry and transfers handle/lease
   cancellation ownership without a gap; Swift retains cooperative cancellation.
   Historical readback and `AlreadyCommitted` results cannot enter this API.
   A bounded optional caller bridge can now reach it, but the normal app's real
   upstream production inputs remain unwired and it opens no socket.
7. Completed G1a-D no-network cryptography: both platforms accept only the
   verifier-minted exact object-7/object-26 binding, consume one-use P-256
   ephemeral keys, derive the same HKDF-SHA-256 root/directional material,
   require bilateral role-separated object-29 confirmation, and protect exact
   ordered object-30 application/key-update records with AES-256-GCM. Epoch and
   session ceilings, update reservation, expiry/clock rollback, terminal key
   wiping, authentication failure, and concurrent sequence uniqueness are
   covered by one pinned fixture, independent Python oracle, and platform tests.
   The fixture SHA-256 is
   `d45fd920e22652d790c742de995d87a8cbfb64bb22aca3b829cbad5b23485448`.
   This is not app- or transport-wired and opens no socket.
8. Completed G1a-D authority-bound crypto lifecycle: each platform keeps the
   verifier-minted key-schedule binding and raw crypto resource inside one
   exact-bound store/coordinator graph. A store-owned process-local writer-
   preferred/FIFO publication gate holds a read permit through start,
   confirmation, activation, seal, open, and pre/post lease/live fences.
   Authority writers block new readers, drain in-flight publications, commit,
   fence the coordinator, wipe crypto, and only then reopen publication.
   Pure precommit rejection and macOS pre-rename failure preserve the old
   session. Once an Android DataStore edit is enqueued, cancellation or
   ambiguous persistence failure fences/wipes the old authority; macOS post-
   rename directory-sync uncertainty does the same.
   Cancellation and terminal crypto failure invalidate the resource and close
   its lease. Swift zeroizes the owner-backed storage of a post-fence-suppressed
   confirmation, seal, or open result before releasing the read permit; small-
   ciphertext plus confirmation/seal/open retained-owner and result-copy
   regressions pin the backing storage. An already
   extracted independent `Data` snapshot is a separate copy and is not
   retroactively zeroized. This is single-process only. Bounded no-network
   caller bridges exist, but real upstream production activation remains
   unwired.
9. Completed dormant G1a-D transport composition: Android `core:transport`
   exposes only a manager-owned one-use raw-route lease to the composer, not a
   raw-channel alias or caller-provided scope. The lease checks the exact
   authority capability/session and creates
   `ProductionRuntimeSecureChannelAdapter` with a manager-owned execution scope.
   Construction failure cancels the owned scope, and the adapter is registered
   before handshake suspension. Under `stateLock`, `UNDISPATCHED` acquisition
   linearizes the transition with physical connector entry: cleanup that wins
   first prevents connector invocation, while an entered connector without a
   returned handle still depends on connector timeout/interruption and closes
   any late handle when it returns. Detached composition uses saturating raw-
   route timeout addition plus a fixed 15-second handshake budget. The manager
   timeout's `IOException` is classified as `ProductionSessionSecurityRejected`.
   The adapter's internal deadline uses one `PENDING` to `COMPLETED`/`TIMED_OUT`
   CAS plus an `UNDISPATCHED` watchdog. Timeout-winning `IOException` dominates
   and suppresses
   the losing error/cancellation; completion-winning external or composer
   `CancellationException` preserves the exact object. Canonical
   `resume(value, onCancellation)` handoff closes only undelivered values:
   pre-delivery cancellation closes once without retry, while successful transfer
   survives later acquisition `Job` cancellation. There is no permanent caller-
   `Job` binding or `InternalCoroutinesApi`. Production P2P
   requires the exact session, object-7/object-26 binding, route kind, and
   manager-owned connection generation. Route expiry is rechecked immediately
   before one-use receipt commit, admission-to-commit wall-clock rollback fails
   closed, and failure cleanup is `NonCancellable`. Even when raw ignores close
   until it returns, the managed raw wrapper checks open before and after send,
   fails closed after close, and the regression observes actual late body-byte
   zeroization. Production relay remains fail closed
   without a verifier-derived exact relay route binding. Focused Android
   evidence is 79/79 (49/49 manager plus 30/30 adapter). The root independently
   reran full `core:transport --tests '*'`: 10 suites pass 163/163 with zero
   failures, errors, or skips; app `compileDebugKotlin` plus
   `compileDebugUnitTestKotlin` also succeed. An independent iterative audit
   found and fixed six P3 availability/lifetime races in total; a final fresh
   re-audit reports no P0-P3 finding. The current root-independent full Swift
   rerun passes 2,003 tests with two declared skips and zero failures in 313.440
   seconds. Those focused/full-module reruns alone were not a completed full
   no-device gate run; the current full no-device gate exits zero. The macOS
   manager owns exact one-use attachment, generation cleanup, cancellation/
   late-result close, raw-handler admission, and terminal mailbox drain before
   removal or replacement. Terminal teardown synchronously invalidates an
   available/claimed capability before replacement and performs asynchronous
   abandon/close outside registry locks, with no plaintext fallback. Focused
   evidence is 39/39 (17/17 composition plus 22/22 secure-channel) and 34/34
   (6/6 production-pair-coordinator plus 28/28 manager); the release build
   passes. The audit-found cancellation/replacement P2 is
   fixed by a deterministic delayed-abandon regression; final independent
   re-audit reports no P0-P3 finding. The bounded no-network caller bridge is
   now concrete: Android uses one renewable
   `AndroidProductionRuntimeActivationSlot` shared by route preparation and
   start-material claim. It retains at most one verifier-derived, one-use plan
   per attempt, uses the exact same `PairingStore`, compares the manager-selected
   exact route object and prepared-session reference, and exposes only the
   manager-owned raw lease. A claimed entry remains slot-owned and generation-
   bound until PairingStore transfer starts. Close or replacement winning first
   discards its key; transfer winning first moves ownership exactly once.
   Cancellation and duplicate or concurrent completion fail closed. Expiry,
   slot close, and ViewModel clear also discard still-pending keys; a fresh plan
   can serve a later reconnect attempt. macOS fixes one exact
   `TrustedDeviceStore`, validates a verifier-derived exact accepted-route
   descriptor, one-shot claims the endpoint, and attaches it through
   `MacRuntimeProductionAcceptedSessionService`. Its service-owned pre-
   attachment generation and rotating `stopAll` epoch let targeted stop and
   stop-all invalidate suspended authority creation; a late result is abandoned
   without disturbing a fresh same-ID generation. Focused Android evidence
   passes composer 16/16 plus ViewModel-clear 1/1, full app 1,174, and complete
   core protocol/pairing/transport 232/232, 200/200, and 163/163. Focused macOS
   evidence passes service 9/9 and manager + service + composition 54/54; the
   release build succeeds. These results are not a refreshed full no-device
   aggregate. G1b-A now installs an empty activation controller in the normal
   Android graph and proves injected real-fixture manager and ViewModel E2E
   activation without legacy fallback or an OS socket. Its publication
   generation is assigned before durable admission, latest-started wins, close
   can revoke resources during suspended admission, and displaced cleanup runs
   outside controller locks. Controller tests pass 12/12 and a final independent
   audit reports no P0-P3 finding. macOS now implements a
   loopback-only accepted-raw primitive with injected connection-I/O tests. The
   Android upstream verifier/candidate/secret producer and actual P2P endpoint
   stack, the macOS `CompanionAppModel` call site, actual socket execution and
   close interruption, network, physical-device, and production-release proof
   remain open.
10. Keep this slice pure and no-network. Source reads, first-party compilation,
   local tests, temporary test storage, and deterministic crypto vectors are
   allowed; socket creation, live service calls, production credentials, and
   deployment are outside it.
11. Completed for G1b-A's bounded no-network/loopback-primitive scope: Android
   normal factory wiring owns the exact same-store controller and composer while
   returning no production route until a verified attempt is supplied; injected
   real-fixture manager and ViewModel tests prove the end-to-end composition
   path. macOS exposes an IPv4-loopback-only accepted-raw primitive, but its tests
   inject I/O and execute no socket. The next G1b slice is the upstream P2P
   producer/actual endpoint stack plus `CompanionAppModel` wiring and separately
   authorized socket-close proof. The eventual send path must preserve `seal +
   channel.send` inside the same read-permit closure. The maintained
   restricted-fork rung-one profile is historical at_that_checkpoint: Pion v4.3.0 as-is and
   the wrapper-only option remained rejected, while the minimal policy-owned
   shape selected no library. The bounded rung-two acquisition has since consumed
   its exact one-use request and retained verified bytes without extraction.
   Rung-three v1/v2 failed closed before publication, while v3 completed bounded
   lexical inventory and tracked readback. Semantic-review v1 then completed
   two non-attesting passes, and patch/dependency decision v1 completed that
   preparation step. The historical dependency-review decision selected only
   the staged fixed-point source-closure plan. The predecessor wave-one
   decision fixes the source identities and bounded request contract. Its
   historical next action was satisfied by execution permit v1, but that permit
   has since been consumed by the terminal `E_ZIP_RATIO` attempt and cannot be
   reused. Recovery decision v1 now fixes the separate v2 preparation boundary;
   no v2 network execution is currently authorized.
   No user action is a prerequisite for this local design and validation work.
12. Treat production application IDs, distribution accounts, signing custody,
   service domains, relay capacity, and store/deployment work as later release
   inputs. Their absence must not stop local product implementation.
13. Leave staging, commit, and push to the user unless they explicitly ask for a
   Git operation. Physical-device checks remain a later evidence slice.

## Android Runtime Session Summary Linear Merge

- Priority and status: implemented and broad Android-verified for the bounded no-device slice. Authoritative history can admit up to 10,000 sessions, so the former per-summary suppression reconstruction and persisted-session scan was the highest-value low-risk follow-up after the whole-codebase optimization pass.
- Implemented now: one deleted-session set, one first-wins persisted-session index, one local-only collision set, and one incoming-summary deduplication set reduce lookup work from `O(summary * (persisted + suppressed))` to `O(summary + persisted + suppressed)`. Existing first-wins legacy behavior, manual state, messages/drafts, archive/search metadata, deletion tombstones, local-only collisions, final sorting, and active-session cleanup are unchanged.
- Evidence now: a deterministic 1,003-row/1,001-suppression counting-list regression pins linear reads and semantic preservation; three focused tests and all 634 ViewModel tests pass. `build/qa/android-session-summary-linear-full-20260720.log` records the complete Android run and debug assembly succeeding in 30 seconds, while the refreshed JUnit XML reports total 1,528 tests with zero failures, errors, or skips. The 11 documentation-handoff guard tests and current static hygiene checks also pass.
- Integrated gate: `build/qa/check-no-device-quality-session-summary-linear-final-20260720.log` exits zero across 8,806 lines in 580.459 seconds with the session-summary linear-merge marker and overall success marker each exactly once. It includes 1,809 Swift tests with two explicit environment-dependent skips and zero failures, the Android ViewModel class, authenticated direct/relay smokes, and both Swift product builds.
- Next safe no-device candidate: reduce `StrictJSONDocumentValidator` input-copy and JSON-literal allocations while retaining the existing Unicode/string decoder and proving behavior against a differential corpus. That cross-cutting parser work stays separate because it protects envelopes, relay admission/allocation, and durable-memory recovery. Physical expired/rotated QR, permission regrant, TalkBack/VoiceOver, and device process-death checks remain device-dependent priorities when hardware is attached.
- Boundary: no UI/design, protocol/schema, persistence format, trust, permission, provider route, external network, P2P/NAT Phase B, production, or deployment authority changed. Access-count evidence is not a device or production performance benchmark.

## Canonical Session Continuation Baseline

- Priority and status: the selected historical implementation baseline remains `d32c1846`; the bounded G0 V2/V3 packet and its successors are published and read back through the twelve-file `main@4227204b450372fcee55e0ef970c401f10b6c98c` checkpoint. The latest 16/16 strict HTTPS `blob:none` readback produced manifest SHA-256 `1b91a321de9a39faf9fb519b47ffa6e82ce85dd48595f092a63581875c9d4a37`; the later 12/12 public HTTPS readback from `2026-07-21T12:34:24Z` through `12:34:32Z` matched parent `b24c5ecb`, tree `c321c33e`, and produced manifest SHA-256 `267be3ca8f56fe353fbb856f95c6f634e98afbc3f204b589a9935be0fe5b0a15`. Those owner/receipt flags are historical byte-integrity facts and do not govern current personal-project implementation. The current local scope includes the socket-free G1a foundations, G1b-A Android normal-graph ownership plus injected manager/ViewModel E2E, the macOS loopback-only accepted-raw primitive, and the G2 restricted-fork lineage through consumed Wave19 acquisition/readback plus the Combined V18 fixed-point and its closure-review decision. The next session must still refresh branch, HEAD, Git status, device attachment, and runtime process state instead of inheriting stale assumptions.
- Current product checkpoint: one earlier same-Wi-Fi debug QR was decoded from the real macOS screen and paired through a physical `SM-S936N` camera. On 2026-07-21 the connected authorized device also passed a preserved-data debug APK rebuild/install, cold launch, force-stop/relaunch, ADB-injected development pairing and trusted-route reconnect, mock chat cancel and natural completion, and bounded chat/model/drawer/settings UI inspection. CAMERA revoke reached the Android system permission dialog and was restored to granted; actual denial selection and post-denial recovery were not completed. These are debug/local-development observations, not G0 evidence or production proof. Optical QR in this pass, actual TalkBack/VoiceOver traversal, haptic feel, live providers, external relay, different-network behavior, release binaries, and production crypto remain unverified.
- Default next bounded slice: the G1a foundations and G1b-A ownership primitives remain complete for their stated no-network/injected-I/O scope. G2 has progressed through successful retained-snapshot readback of dependency waves 1 through 19, a Combined V18 empty-frontier fixed-point candidate over 369 retained source inputs, a decision accepting only its dependency-graph fixed point, and the exact source/license preparation package. Both independent source/license passes returned incomplete, so completion remains 0/2. The next bounded slice completes per-file semantics, selected special-source review, broad license/`PATENTS`, SPDX/provenance/binary mapping, and native profile reachability. Extraction, backend compilation/execution, and product socket proof wait for their own later G2 scopes. Authentication and user action remain false.
- Conditional next slice: different-network pairing may begin only after the exact reachable route, environment, and execution authority are established. Same-Wi-Fi `local_diagnostic` evidence is not a relay, P2P/NAT, Phase B, production-capacity, deployment, or readiness result.
- Publication rule: `12c38154`, its nine-file `70350f5e` successor, the seven-file `025a4ef5` successor, the sixteen-file `b24c5ecb` successor, and the historical twelve-file `4227204` successor have intentional publication and fresh exact remote-byte readback evidence. Preserve those bytes without treating their owner/receipt state as a current work gate. Read current publication state from Git; this workflow does not stage, commit, or push unless the user separately requests it.
- Continuity rule: update the existing canonical handoff after future substantial work and synchronize current progress, QA, and roadmap facts. GPT-5.6 Sol is the requested subagent model; GPT-5.3-Codex-Spark remains excluded for this workstream.
- Reading rule: `docs/handoff.md` and the current sections at the top of this roadmap are authoritative. Sections marked Historical Checkpoint or Superseded preserve at-checkpoint evidence only and cannot override the current Debug/Release matrix, physical observation manifest, or authority boundary.
- Authority freshness: the QR-modified P2P/NAT source snapshot is synchronized at 13-artifact collection SHA-256 `6e6dfbfc0cdb70370c30f54222584b69042a6e22b6df04c7f3e65043c38522bd`; its validator and seven Phase A progress tests pass. This does not select a library or open compiler, socket, runtime-network, Phase B, production, or deployment authority.
- G2 preflight history: [the requirements review](security-hardening/production-p2p-nat-v1/g2-requirements-review-v1.md) rejects Pion ICE v4.3.0 as-is at exact commit `1e8716372f2bb52e45bf2a7172e4fb1004251c46`. That checkpoint retained no source and opened no compile, load, socket, network, device, Git, or deployment operation.
- G2 current freshness: the tracked lexical/semantic review, patch/dependency
  decision, and staged fixed-point selection remain predecessors. Wave-one
  v1/v2 terminal failures remain canonical, while waves 1 through 11 have now
  retained and read back their exact resource sets. Combined-v8 bound 277 exact
  inputs with input-set SHA-256
  `030743c3959a6e7466385e9f89255fcb03d65576676a1e5cd7e5e2929e9f6339`,
  graph SHA-256
  `721d045a10cdf015e865a84db7026115ac63462217dbb5349504fed9f1bae7b7`,
  and exact non-fixed eleven-tuple Wave10 frontier SHA-256
  `780501bca37fbeb953590004ca7e5aad7f206083f749b920e2a9842b63675f82`.
  Wave10 decision v1 reopened all 277 bindings, reproduced 15 declarations,
  107 `go.mod` H1 and 15 module-ZIP H1 witnesses twice, resolved one selected
  and ten non-selected exact pairs, and bound the 22-request set at SHA-256
  `cf6a97651565b55bb714a713e66e6a452f7132973ce21ced254bd0d728d12a89`.
  Acquisition attempt `ffe70ee4562fcfc9e0fd6c9c4e136bd9` retained all 22
  resources without extraction, and readback attempt
  `e74e030f7f5ef33589d7895e1b28b3b1` independently verified their exact
  27,773,526 bytes twice before manifest-last publication. The readback claim,
  receipt, and manifest raw SHA-256 values are
  `5eaed52abe8fc9c1de5ceba356d37057b470ada00048b3f7cd5048003f82ef0f`,
  `056b0b2d9bbdc19702f8400451ff5329ca7eaceff4613bba1dbfd34e93f21224`,
  and
  `66eb30a0d1f943b0718ee2b14a3cdaee6fae5127e796569c16a55f14ade41762`.
  Both one-use actions are consumed and cannot be retried. Semantic closure,
  dependency closure, rung-three completion, candidate selection, and library
  selection remain false. Combined-v9 subsequently held 299 exact source
  inputs, reconstructed the graph twice, and derived the exact non-fixed
  nine-tuple Wave11 frontier at SHA-256
  `171af951e3a67405b62ddceface1341bb6f64b08f370d3d216ede541bd011f06`.
  Its input-set and graph SHA-256 values are
  `5a08d28573b68ddd031eff34a8b6afad8f7cd9e01966f4516c22a410bbb51b71`
  and
  `4367fc6c4c5efb69f948d8e040c2cfa496345102631719692d31feabb794a6b5`.
  The exact final suite passes 21/21 in 1,187.320 seconds; two independent
  GPT-5.6 Sol exact-byte audits report no P0-P3 finding. Wave11 decision v1
  subsequently reproduced 105 ZIP-contained `go.sum` entries, 12 declarations,
  68 `go.mod` H1 witnesses, and 13 module-ZIP H1 witnesses twice. It resolves
  all nine exact identities with zero selected, blocked, or conflicting rows
  and binds the 18-request set at SHA-256
  `bbde21b5f7a523bb6cddf78fbbbfdce46f8bcf61d60ebcec72a80d52dda50ba8`.
  Its decision raw/content SHA-256 values are
  `e1f3a82025c711694cb6551a53407aa1164493396a65f383eacf95dbf90b881a`
  and
  `1bdb93f69c6a44d977a701dab83ea847a5ff473bb18e41bf093ed45bc4c1647f`;
  its exact final suite passes 25/25 in 1,157.225 seconds and three independent
  GPT-5.6 Sol final-byte audits report no P0-P3 finding. Every frontier and
  request acquisition flag remains
  false. The separately bound acquisition package then passed 17/17 checker
  and 46/46 runner tests. Acquisition attempt
  `ac18b8fda0a80a132510efd5dd17d5b7` retained 18 resources totaling
  16,363,894 bytes without extraction. Its readback package passed 17/17
  checker and 50/50 recorder tests; readback attempt
  `9b4dac65f66ce9e5d53dcd8edaf4d1d4` independently verified the exact
  36-file snapshot twice and completed all three pre-manifest barriers before
  manifest-last publication. The readback claim, receipt, and manifest raw
  SHA-256 values are
  `752c0fdc006688a4c22dc26f54be1c9bb4498e9a94f196217aebfaff8e61dc13`,
  `f89904b359aed770e89ed8de25b775d6b920d7eef3d32bdc464a486a862cc5ca`,
  and
  `0bda6e5da9609ddd375e20a6692a4cec46aaf930acee4861c5168efde1f18c0e`.
  Both one-use actions are consumed and cannot be retried. Combined-v10 then
  reconstructed all 317 exact held inputs twice, with input, graph, and
  frontier SHA-256 values
  `f946c625334ac8cf42d42c9f45f0f051eb7f89fb9ecf5dfc576114b1cba990be`,
  `77813f467c7452290f35c4ecaa6a1041a0988d563ea37660bb6cc902bb95cdc4`,
  and
  `8b84bd2fd9201d33f4424b9dd1018aee7f8470a87306c2ba23eba0c8b6d4ff05`.
  It derives four exact non-selected Wave12 tuples and
  `fixedPointReached=false`. Wave12 identity/acquisition decision v1 is complete
  for its read-only bounded scope: four exact H1 pairs are complete and zero
  are blocked or conflicting. Its separate exact-eight permit package is
  materialized and passes 18/18 checker plus 48/48 fake/local runner tests.
  Acquisition attempt `f977ddcf8fc391e5915048b930beccbd` retained all 8
  exact resources, and offline readback attempt
  `32ab6b747a02382f85f48f65e0c388c5` verified the exact 26-file snapshot
  twice before manifest-last publication. Both one-use actions are consumed and
  cannot be retried. Combined-v11 reconstructed the exact 325-input set twice,
  and Wave13 decision v1 resolved all four resulting H1 pairs with zero
  blocked/conflicting tuples. Its decision content SHA-256 is
  `3d08d589ed9121128717215fe0d9583b6f64e59fc033e1c5f50477f6e59d5b83`,
  and its focused suite passes 27/27. Its separate exact-eight permit package
  is materialized at raw SHA-256
  `b976f9bea30a20e34df25e9d90cfa9ee4617ce825b0d28f254b5bb512b6c29a1`
  and passes 18/18 checker plus 48/48 fake/local network-denied runner tests.
  Acquisition attempt `eb05816e0b897ea8c3ad8b7089668e91` retained all eight
  resources, and offline readback attempt
  `8b5f92c9d90f825f5f3b46df0d006ef3` verified the exact 27-file snapshot
  twice before manifest-last publication. Both one-use actions are consumed
  successes and cannot be retried. Combined-v12 then reconstructed the exact
  333-input retained set twice, passed 24/24 normal-path tests, and identified
  four exact Wave14 tuples. Wave14 decision v1 then resolved all four H1 pairs,
  recorded zero blocked/conflicting identities, and the latest observed local
  suite passed 27/27 tests. Acquisition attempt
  `7fef20e6c3931b698f32b2a71f8a596a` retained all eight resources, and
  readback attempt `177051373b1754fd638b5f57df2d6515` independently
  verified the exact 27-file snapshot twice before manifest-last publication.
  Both Wave14 one-use actions are consumed successes and cannot be retried.
  Combined-v13 then reconstructed the exact 341-input set twice, passed 24/24
  tests in 2,360.584 seconds, and derived five exact Wave15 tuples. Wave15
  decision v1 resolves all five identities and records zero
  blocked/conflicting rows. Acquisition attempt
  `c5db51cfd9a295b448927cca36d1ea07` retained all ten resources without
  extraction, and readback attempt `fb2b53eb42982732b0344695065c625d`
  independently verified the exact 29-file snapshot twice before manifest-last
  publication. Both Wave15 one-use actions are consumed successes and cannot
  be retried. Combined-v14 reconstructed the exact 351-input set twice, passed
  23/23 full tests in 2,441.948 seconds plus 2/2 post-seal fast tests, and
  derived three exact non-selected Wave16 tuples. Wave16 then completed its
  verification-only decision, consumed six-resource acquisition, and exact
  25-file readback. Combined-v15 subsequently reconstructed the exact
  357-input set twice and derived one non-selected Wave17 tuple. Wave17 then
  completed its verification-only decision, exact two-resource acquisition,
  and exact-21-file independent readback. Combined V16 then produced the
  three-tuple Wave18 frontier. Wave18 completed its verification-only decision,
  consumed exact six-resource acquisition, and completed independent readback
  without extraction. Combined V17 reconstructed the exact 365-source retained
  set twice and derived `fixedPointReached=false` with two non-selected Wave19
  tuples: `golang.org/x/crypto@v0.38.0` and
  `golang.org/x/text@v0.25.0`. Wave19 then completed its verification-only
  decision, exact four-resource acquisition, and exact 23-file independent
  readback without extraction. Both one-use actions are consumed successes.
  Combined V18 then reconstructed the exact 369-source retained set twice and
  produced an empty-frontier fixed-point candidate with zero unmapped or
  unresolved imports. Its separate read-only closure review now accepts only
  the dependency graph fixed point. The fixed-point source/license preparation
  package is complete, while both independent passes remain incomplete at
  0/2. The next boundary is bounded per-file semantic, special-source,
  broad-license/`PATENTS`, SPDX/provenance/binary, and native-profile
  completion work. Further extraction, source load/compile/execution, runtime
  socket/product network,
  Git write, device work, credential, repository authentication, or user
  action is not opened or required by the current decision.

- G2 Wave8 freshness: decision v1 binds all 14 exact version-specific tuples
  with zero blocked/conflicting identity, compact identity SHA-256
  `c6aa1a974ad09f11927c103c7f2b63df0835d09b41d0dac9f6349d46d377a388`,
  decision content SHA-256
  `1e1d62f03fe3137a88aa9413be8310bf7260f65a4825a09baab9a848ce6969da`,
  and a 28-request contract SHA-256
  `b0f0f887864ddc4cf3ab15319a9e89dbea8c84087fa3d0e374a0332240336ddc`.
  Its focused suite passes 18/18. All decision selectors and acquisition
  authorities remain false. The separate one-use execution permit binds
  the exact 28 resources at canonical SHA-256
  `ee32b0512643b0e767f5b1e96625352fc47ea6ae7aea5d7366adfe98f4db8136`,
  has content SHA-256
  `527a4558d069b31f92256926ea90e05c8353a33f65128b131d1c960614df925b`,
  and its focused suites pass 15/15 and 44/44. Acquisition attempt
  `6d8ea4473126c853b439c56a895f9c28` retained all 28 resources with accepted
  hash-set SHA-256
  `7642f0b4dea8fee8eb92f573a3a4d948aa46a8736be70857097ce3b83af2eb38`.
  Readback attempt `8618087527c005b5d19c8f902ec33557` independently
  verified the exact 46-file frozen snapshot twice, completed all three
  pre-manifest barriers, and wrote manifest raw SHA-256
  `79f844b647915661b0b36fd5fa333591327ad934d6589c0fc98c912e7660d62f`
  last. Readback suites pass 16/16 and 45/45; independent GPT-5.6 Sol post-run
  audit reports no P0-P3 finding. No credential, authentication, Git write,
  or user action occurred.

## macOS Debug Local QR And Android Optical Pairing Recovery

- Priority and status: complete for the bounded same-Wi-Fi debug goal. A clean development host can now start its runtime, create an explicit local-diagnostic session, render a decodable QR, and pair through the physical Android camera without weakening the release route policy.
- Implemented now: ready-remote-first model-owned UI pairing with a debug-only local fallback; a release-build gate that cannot be enabled by constructor override; listener-readiness and nonloopback-host guards; primary IPv4 interface selection ahead of other physical candidates; local recovery after an explicit remote preparation failure without repeated allocator calls; separately wired generic pairing and Connection Recovery remote-only actions; explicit local-route guidance; Android debug optical/deep-link admission paired with release remote-route enforcement; and an owner-only file identity plus bounded startup-settle check for ad-hoc debug launches.
- Physical evidence: an `SM-S936N` camera scan completed pairing, challenge-response authentication, `runtime.health`, and trusted-device admission on the same Wi-Fi. Force-stop and relaunch then completed Bonjour rediscovery, stored-trust authentication, and health exchange without rescanning.
- Next product work: provision and validate a canonical remote bootstrap/allocation route before claiming different-network pairing. That requires separate execution authority and evidence for relay availability, external-network reliability, expiry/rotation/retry behavior, and production operations; the local debug fallback is not a substitute.
- Evidence split: physical Android camera QR and TalkBack are not one inherited claim. The camera QR path is complete for one same-Wi-Fi debug device; real TalkBack traversal remains unverified.
- Next device evidence: exercise expired and rotated QR recovery, camera denial/regrant, TalkBack and VoiceOver traversal, network handoff, and more device/OS combinations. Preserve the actual on-screen QR as the optical contract.
- Boundary: this milestone proves one local debug route and does not authorize or establish production relay, P2P/NAT, Phase B, external egress, deployment, production performance, or readiness.

## Android Bounded Volatile Persistence Optimization

- Priority and status: the high-frequency Android whole-state persistence slice is implemented and focused/full JVM verified. It replaces per-keystroke and per-`chat.delta` serialization with one fixed first-change window of at most 250 ms while leaving every durability-sensitive boundary immediate.
- Implemented now: a generation-based dirty/latest-state coordinator with no retained secret-bearing snapshot; exactly two coalesced call sites; durable terminal, malformed/error, rejected-send, cancel, send/session, settings, trust, approval, pairing-route, lifecycle, and clear barriers; secret-bound pending/trusted handles with metadata-failure compensation, current-safe cleanup journals, and unchanged-secret write suppression; and ordinary single Activity/ViewModel ownership through `singleTask` plus `documentLaunchMode="never"`.
- Measured regression result: 100 composer mutations collapse to one scheduled save, 100 stream deltas collapse to one scheduled save, and a mutation at 249 ms does not extend the 250 ms deadline. Immediate supersession, process recreation after lifecycle flush, terminal/error/cancel order, and secret deletion all have deterministic fake-scheduler coverage.
- Current evidence: 19 focused regressions pass. The app passes 1,125 JVM tests including 633 ViewModel, 15 local-store, and 158 navigation tests; pairing passes 130 tests, release Kotlin compilation succeeds, and the copy contract tracks 749 named Android evidence selectors. The final GPT-5.6 Sol closure review reports `No actionable P0-P3 remains`. The synchronized no-device aggregate `build/qa/check-no-device-quality-android-volatile-persistence-final-v2-20260719.log` exits 0 across 8,998 lines in 593 seconds with one overall marker, one persistence marker, five successful Gradle invocations, 56 fresh local relay connections, and 905 encrypted frame bodies.
- Residual P3: asynchronous volatile writes are not abrupt-process-death durability; main-dispatcher stalls can exceed 250 ms wall time; confirmed barriers synchronously commit and are not device-latency benchmarks; and hostile or exotic multi-task/process writers need a future application-scoped versioned repository rather than relying on Activity launch policy.
- Next evidence: run process-kill/recreation, lifecycle, typing, streaming, and pairing-route cleanup checks on an attached Android device. Physical camera QR pairing is complete for one same-Wi-Fi debug path in the current section; TalkBack and broader durability/device coverage remain separate evidence. Moving durable commits off main would require a lifecycle-safe acknowledgement design rather than weakening the confirmed barrier.
- Boundary: no wire/schema, pairing trust, secret lifetime, permission, networking, P2P Phase B, production, or deployment authority changed. Local JVM/static evidence does not establish physical-device durability, external-network behavior, production performance, or readiness.

## Whole-Codebase Optimization And Hardening

- Priority and status: the 2026-07-19 implementation slice is complete for the bounded no-device scope. It preserves QR recovery and all authority boundaries while closing validated P1 concurrency/resource-lifetime failures and low-risk measurable P2 defects found by independent GPT-5.6 Sol review of the complete tracked first-party source and core documents. A complete pre-document aggregate passes, and the synchronized final-source aggregate is recorded at `build/qa/check-no-device-quality-whole-codebase-final-20260719.log`.
- Implemented now: per-event SQLite search projection instead of full-history work on ordinary append; immediate fail-closed approval-receipt consumption and queue-wide recovery poisoning; cancellation-aware shared and self-started model unload; bounded provider bodies/deadlines/errors and four-way Ollama detail fanout; descriptor-validated document snapshots and bounded direct ingestion; bounded trusted-device persistence with duplicate-ID rejection; atomic model-owned active/completed Connection Recovery requests with exact-id consumption and invalidation cleanup; exact Android protocol-frame preflight before draft/attachment clearing; exact one-use trusted-source confirmations; durable relay supervision with bounded exact-child recovery plus ephemeral parent-liveness ownership; and pairing refresh success tied to a new session identity.
- Regression contract: approval TSan passes 29/29; approval plus SQLite passes 116/116; provider/store/approval selections total 303 tests with two explicit localhost skips; document/trusted-device passes 68/68; Android passes 1,110 JVM tests and release Kotlin compilation; localization plus residency passes 180/180; full router passes 523/523; paired route refresh passes 10/10; the monotonic TTL regression passes 50/50 repeated runs; durable no-ADB lifecycle passes 12/12; and the synchronized five-module Python selection passes 31/31. The broad 272-test approval selection and the complete no-device aggregate pass after deterministic deadline synchronization.
- Performance and lifetime result: ordinary SQLite append cost no longer grows with complete durable history, provider and attachment byte budgets are bounded, cancelled model callers do not wait for provider unload, and the durable smoke relay has causal owner-loss teardown coverage. Provider deadlines and external document helper deadlines are absolute; synchronous filesystem reads, PDFKit, and in-process rich-text parsing still cannot be forcibly interrupted by the current cooperative document deadline. These are deterministic regression properties, not production benchmarks.
- Deferred P2: replace owner-scoped `instr` and multi-delta boundary scans only through a versioned trigram/cross-event projection migration with differential JSONL evidence. Preserve one-time O(N) repair for stale/migrating stores until that migration is proven. A hard wall-clock boundary for cancellation-ignoring filesystem or in-process document parser calls requires process isolation or another interruptible parser architecture. The Android coalescing prerequisite from this checkpoint is completed in the current section above, with abrupt-process-death durability still explicitly deferred to device evidence.
- Next evidence: physical current-screen camera pairing is complete for one same-Wi-Fi debug path. Expiry/retry, TalkBack traversal, live-provider, external-network, production relay/P2P, and deployment behavior still require their own authority and evidence; they are not inherited from this completed local pass.
- Boundary: no wire/schema contract, pairing trust, secret lifetime, approval policy, provider route, source-acquisition authority, P2P candidate state, socket/runtime-network permission, Phase B, production network, or deployment state changed. Local no-device evidence is not physical Android, optical QR, live-provider, external-network, production-capacity, or deployment proof.

## Historical Checkpoint: macOS Pairing QR Recovery And Bounded Route Preparation (Superseded)

- Historical status: at this checkpoint, implementation, focused no-device verification, the final GPT-5.6 Sol delta review with no P0-P3 finding, and the v3 plus synchronized-document v4 whole-repository aggregates were complete. The current 2026-07-19 debug local QR and optical-pairing section supersedes its product-state and next-evidence wording.
- Product result at that checkpoint: macOS clean first-run Pairing exposed Connection Recovery as the one setup path while Status kept first-run diagnostics hidden. Every Pairing, toolbar, menu-bar, Status, and recovery action then used the same core availability decision and waited for a complete canonical remote route before presenting a QR. That statement is historical; the current generic-versus-remote callback matrix in `docs/handoff.md` is authoritative.
- Allocation boundary: route preparation is cancellation-aware. The built-in Network.framework allocator applies one absolute deadline to DNS, connection, request send, and bounded response reads and cancels its `NWConnection`; the model independently retains a draining state until worker completion acknowledgement and blocks asynchronous, public synchronous, and restart-driven allocation entry points. Slow trickle traffic cannot extend the deadline, and no test overstates the two contracts as one direct end-to-end trace.
- Canonicality boundary: every nonempty bootstrap endpoint must parse canonically with a valid nonzero port. QR readiness additionally requires an eligible remote host, fresh lease, complete PairingSession material, and either an exact protected-store handle/read-back or a secret explicitly supplied by the active environment route. A malformed list, failed write, wrong handle, host-only environment override, missing secret, stale lease, or incomplete route remains fail-closed and is not saved or rendered.
- Shared-state boundary: empty bootstrap removal and development/bootstrap destructive actions execute through core guards. Multiple windows cannot clear or replace shared route state while an allocation is in flight.
- UI and package result: failed renewal preserves the last visible QR, exact-payload rendering retries transient failures without direct/local fallback, stale relay callbacks are generation-bound, and the completed app bundle is ad-hoc signed only after resources and `Info.plist` are present and then strictly deep-verified.
- Regression contract: nine focused fail-closed tests cover draining retry closure, public synchronous entry closure, malformed bootstrap rejection, missing and failed-store secrets, environment-source binding and its explicit-secret control, shared-allocation destructive-action rejection, and an absolute deadline under slow trickle. The broader 54-test CompanionAppModel and 59-test cross-module selections, 128 localization tests, and 19 render tests pass; Vision decodes the actual rendered remote QR to the exact canonical payload.
- Current evidence: `build/qa/check-no-device-quality-macos-qr-recovery-final-v2-20260718.log` is a passing 11,622-line historical checkpoint that predates the final draining and secret-source changes. `build/qa/check-no-device-quality-macos-qr-recovery-final-v3-20260719.log` is the passing 11,638-line fresh-source aggregate. `build/qa/check-no-device-quality-macos-qr-recovery-final-v4-20260719.log` is the passing 11,643-line synchronized-document aggregate with one overall marker, one QR marker, the exact focused 9/9 selector in 9.651 seconds, 128/128 localization tests, 19/19 render tests in 259.729 seconds, five successful Gradle builds, 56 fresh local relay connections, and 905 encrypted frame bodies.
- Next evidence from that checkpoint: physical camera pairing and trusted relaunch are now complete for one same-Wi-Fi debug route. Expiry/retry, TalkBack/VoiceOver traversal, different-network behavior, and production route behavior still require separate authority and evidence.
- Boundary at that checkpoint: proof was local no-device Swift, loopback relay, static validation, strict local bundle-signature verification, and SwiftUI bitmap/Vision decode. The later physical debug result is recorded separately and does not retroactively make this historical aggregate physical-device proof.

## Historical Checkpoint: Cross-Platform Readiness UI Pass (Superseded)

- Historical status: implemented and focused no-device verification completed on 2026-07-18, with final GPT-5.6 Sol platform re-reviews reporting no P0-P3 findings. The product rule was one current blocker and one next action, while preserving macOS as the Runtime host and Android as the chat client.
- Implemented now: responsive non-nested macOS pairing layouts; first-device Pairing-to-Status transition; successful-only QR image caching with transient-failure retry; Android pre-trust suppression of connection diagnostics and auto reconnect; setup-QR suppression after trust; one state-appropriate connect-or-refresh pairing action; informational Settings route status; explicit Status action buttons; QR-specific Material icons; shared 8 dp readiness surfaces; and consistent `onSurfaceVariant` secondary content.
- Regression contract: macOS navigation and compact render tests cover first versus additional trusted devices, five languages, System/Light/Dark, 520 by 640 points, accessibility text, in-memory QR/renewal frame bounds, and exact active-payload QR decoding without retaining credential-bearing PNGs. The 279-test Android Compose class covers the single first-run QR action, hidden pre-trust diagnostics, trusted-state action cardinality, one-card TalkBack summaries with separate explicit route actions, QR-versus-connect icon state, 260 dp width, 1.5 font scale, and five languages.
- Final aggregate: `build/qa/check-no-device-quality-cross-platform-readiness-ui-final-20260718.log` exits 0 across 12,018 lines in 757.00 seconds with one overall marker and one readiness UI marker; post-gate `adb devices -l` is empty.
- Next evidence from that checkpoint: physical Android camera QR is now complete for one same-Wi-Fi debug path. TalkBack, current Settings/Chat-entry captures, and broader-device checks remain open. Those checks are evidence work only and do not authorize network, P2P Phase B, production, or deployment changes.
- Boundary at that checkpoint: evidence was local no-device Swift, macOS bitmap, Android JVM Compose, and static validation. The later optical run does not convert this historical UI aggregate into TalkBack, VoiceOver, external-network, production-capacity, deployment, or readiness proof.

## Historical Cross-Codebase Optimization Pass

- Status: complete for the bounded historical 2026-07-18 v2 low-risk slice. A complete 302-file baseline GPT-5.6 Sol source audit plus review of the newly added Android test accounted for the then-current 303-file inventory. The 2026-07-19 pass supersedes its current-code and follow-up descriptions.
- Implemented at that checkpoint: retained relay epoch, exact-payload QR, exact-buffer Android read, and macOS suite-deduplication work; used affected-session incremental FTS refresh; cached only supported macOS localization bundles; forwarded relay chunks directly from the reusable raw buffer; computed one Android disk projection while re-reading the latest secret ref per save; preserved direct transport's single-frame write; split only relay frame prefix/body writes; and reduced the no-device gate from 11 to 5 Gradle invocations. Current SQLite code uses the event-level projection documented above.
- Evidence contract: SQLite tests preserve unrelated-corruption rejection and JSONL search equivalence while proving unaffected FTS rowids remain stable. Localization tests prove each supported bundle resolves once while runtime language changes and key fallback stay live. Relay tests cover partial writes, `EINTR`, `EPIPE`, `ECONNRESET`, and exact 1 byte, 64 KiB, and 64 KiB plus one forwarding. Android tests cover empty/corrupt/recreated stores, secret replacement and deletion, exact 1 byte, 64 KiB, and 1 MiB frames, concurrent send serialization, and direct-versus-relay write failures.
- Gate contract: 730 unique suite-subsumed Android named selectors are retained in a reviewed non-executing snapshot with a pinned digest. Copy hygiene rejects duplicate entries and any selector that no longer names a real Kotlin `@Test` method. Complete pairing, protocol, transport, app, persistence, navigation, and Compose classes execute before the existing dynamic JUnit checks; all non-subsumed selectors remain active.
- Final aggregate: `build/qa/check-no-device-quality-cross-codebase-optimization-v2-final-r2-20260718.log` passes on the remediated source across 11,614 lines in 682.05 seconds with one overall marker, one optimization marker, five Gradle invocations and five successful builds, 126 localization tests, 16 render tests, 76 SQLite chat-event tests, 56 fresh relay connections, 88 relay match lines, and 905 encrypted frame bodies. The run is 27.33 seconds, or 3.85%, below the 709.38-second first-slice reference; this single-host comparison is regression evidence, not a benchmark or production-performance claim. Post-gate `adb devices -l` lists no attached device.
- Historical next P1 candidate: Android draft and streaming whole-state persistence coalescing was selected next and is now implemented in the current section above with deterministic scheduler and write-count evidence.
- Superseded candidate: bounded Ollama detail concurrency with deterministic ordering, cancellation propagation, partial-detail handling, and a hard maximum-in-flight test is implemented in the 2026-07-19 pass.
- Additional queue: group owner events once for multi-candidate FTS search; add stateful bounded relay control-line reads with cancellable timers; reduce strict JSON validation allocations with differential duplicate-key coverage; batch additional Swift no-device selectors; and reuse only immutable render fixtures.
- Boundary: these follow-ups do not inherit source-acquisition, socket, runtime-network, P2P Phase B, production-network, or deployment authority. Each requires its own bounded implementation and no-device evidence; live-network or physical-device claims require separate execution.

## v0.5 Model-Pull Audit Recovery Integrity

- Priority and status: implemented as the highest-value approval-safe slice found on 2026-07-18. The v2 model-pull approval store previously validated only `requested` and `dispatch_reserved` records during startup recovery, so semantic corruption in an already completed terminal audit history could survive schema and SQLite integrity checks.
- Recovery boundary: v2 schema opening pins the exact `PRAGMA foreign_key_list` relation from event `operation_id` to operation `operation_id` with `ON DELETE RESTRICT`. `recoverUnfinished(at:)` then runs `validateAllRecordHistories` inside the same `BEGIN IMMEDIATE` transaction and before `readUnfinishedRecords`. It rejects `PRAGMA foreign_key_check` violations and an independent events-to-operations anti-join, then uses one streaming `LEFT JOIN` ordered by operation and event order rather than an unbounded operation-ID array and N+1 full-history queries. Any invalid completed or unfinished event order, transition, timestamp, policy binding, or current-state projection fails recovery without terminalizing or accepting new work.
- Capacity boundary: the durable store admits at most 10,000 operations. Recovery keeps only one operation and at most three events in memory at a time; an over-limit store or new intake at the limit fails with `capacityExceeded`. The production-limit regression recovers 10,000 completed histories in 0.265 seconds on the current no-device host, then proves further intake is blocked; this is a regression budget, not production capacity evidence.
- Dispatch boundary: a recovery failure leaves `RuntimeHostApprovalCoordinator` storage-degraded. New intake returns `storageUnavailable`, creates no pending review, and performs zero provider dispatches. The broker regressions preserve an unexpected operation id and attempt approval, so removing the startup barrier reaches a real dispatcher call and fails the zero-dispatch assertion.
- Regression boundary: eight focused tests cover completed terminal timestamp corruption, orphan events inserted with foreign keys disabled, an otherwise equivalent events schema with only its required FK removed, direct broker intake/approval isolation for all three corruption classes, 10,000-operation streaming/intake capacity, and `testRecoveryRejectsAuditHistoryAboveMaximumOperationCount` for explicit 10,001-operation recovery rejection. The focused eight-test slice and all 43 model-pull approval tests pass; the adjacent permission/coordinator selection passes 29 tests.
- Durable gate: the no-device selector runs the exact eight regressions in addition to the full model-pull approval suite. Copy hygiene structurally pins the v2 verifier's single exact FK tuple, independent anti-join, immediate-transaction closure ordering, exact recovery and intake capacity comparisons, streaming implementation, each broker `enqueue` to `approve` to zero-dispatch proof, regressions, dedicated marker, and aligned roadmap/progress/QA/security records.
- Review boundary: the final GPT-5.6 Sol re-review reports `no P0-P3 findings` after remediation of the schema-definition, orphan-detection, streaming, direct-dispatch, over-limit, documentation, and guard-function-boundary findings.
- Final aggregate: `build/qa/check-no-device-quality-model-pull-audit-recovery-integrity-final-20260718.log` exits 0 across 12,192 lines with one overall marker, one dedicated model-pull audit-recovery marker, 43/43 model-pull tests, 8/8 focused regressions, 88 existing local development-relay matches, and 905 encrypted frame bodies. Post-gate `adb devices -l` lists no attached device.
- Authority boundary: this changes no schema, protocol message, capability, review UI, provider route, permission decision, source-acquisition authority, socket, or network behavior. The closed P2P Phase A and Phase B/production restrictions remain unchanged.
- Proof boundary: this is macOS Swift no-device persistence and state-machine evidence. It does not prove physical Android behavior, optical QR, live-provider download, external or production networking, P2P/NAT traversal, Phase B, capacity, deployment, or production readiness.

## Production P2P/NAT Phase A libnice Rejection And Candidate Closure (No Compilation)

- Historical authority: [progress-v8.json](security-hardening/production-p2p-nat-v1/controlled-network-spike/phase-a/progress-v8.json), [decision-v6.json](security-hardening/production-p2p-nat-v1/controlled-network-spike/decision-v6.json), and [handoff-v9.json](security-hardening/production-p2p-nat-v1/implementation/handoff-v9.json) close the libnice candidate and leave no selected networking library. At that checkpoint, the newer G2 restricted-fork rung-one record superseded them as the pre-acquisition direction; all records remain immutable history.
- Exact intake: official libnice 0.1.23 and GLib 2.64.2 were acquired under consumed one-shot authorities. The libnice archive/tree SHA-256 values are `618fc4e8de393b719b1641c1d8eec01826d4d39d15ade92679d221c7f5e4e70d` and `e594b0b2435e10a8df970304ba3dec24ea0353820f1eecb820a810ab56cd276a` for 184 files; the GLib archive/tree values are `9a2f21ed8f13b9303399de13a0252b7cbcede593d26971378ec6cb90e87f2277` and `1c36d535b42d89b62c375b60005dd3c073033ba5bb4928c6825c09a4bc61d3ac` for 1,961 files.
- Signature boundary: the detached libnice signature bytes are pinned at SHA-256 `44292ddf373bc7a962eb3949d4754987d7bbd50cb2d3a2effccb71a2d332727b`, but signature trust is not claimed because no trusted signing key and successful OpenPGP verification were available.
- Audit outcome: [libnice-source-audit-v1.json](security-hardening/production-p2p-nat-v1/controlled-network-spike/phase-a/libnice-source-audit-v1.json) rejects libnice before compilation. Four independent P1 blockers are `LN0123-P1-ENTROPY`, `LN0123-P1-SECRET-DIAGNOSTICS`, `LN0123-P1-PRE-IO-REDIRECT`, and `LN0123-P1-CONSENT-BINDING`; three P2 findings cover resolver lifetime, graceful shutdown, and ABI surface. Two independent GPT-5.6 Sol static reviews reached the same disposition.
- Dependency closure: the minimum remaining source set was identified as libffi 3.7.1, GNU libiconv 1.19 for Android API 26, proxy-libintl 0.1 in stub-only mode, and OpenSSL 3.5.7 LTS. None was acquired, checksum-pinned, extracted, or executed because the candidate failed before scope expansion.
- Compile boundary: no generator, configure step, build system, compiler, static archiver, linker, loader, symbol tool, C ABI adapter, native build wiring, test executable, socket, or runtime/harness network operation was authorized or run. `android_macos_compile_only_integration=not_run_candidate_rejected_before_compile`.
- Durable gate: the central validator pins a 57-file SHA-256 preflight, the exact libnice and GLib manifest rehashes, the acquisition-authority suites, and the 8-test libnice rejection mutation suite. `build/qa/check-no-device-quality-p2p-libnice-source-audit-rejection-final-20260717.log` exits 0 across 12,148 lines with exactly one `No-device quality checks passed.` marker, one current libnice rejection addendum, 88 existing local development-relay matches, and 905 encrypted frame bodies.
- Superseded next decision: this checkpoint required a new versioned review before any source acquisition. The later restricted-fork lineage progressed through rung two, lexical and semantic review, patch/dependency preparation, and the staged fixed-point selection. The wave-one v1 permit was consumed by the terminal ratio-policy failure, and v2 was consumed by tuple-11 `E_GO_MOD_MISSING`, with no accepted final set. Recovery decision v2 selects the v3 pair-resource design but authorizes no network execution. Rejected libjuice or libnice authority cannot be reused implicitly, dependency closure remains blocked, and no user authentication or action is required.
- Proof boundary: this is no-device exact intake, dependency-planning, and static source-rejection evidence. Post-gate `adb devices -l` lists no attached device. It does not prove signature trust, Android/macOS compilation, ABI compatibility, runtime ICE/STUN/TURN, NAT traversal, physical Android behavior, live-network behavior, Phase B, deployment, or production readiness.

## Historical Production P2P/NAT Phase A libjuice Source Audit Rejected (No Compilation)

- Historical authority: [progress-v3.json](security-hardening/production-p2p-nat-v1/controlled-network-spike/phase-a/progress-v3.json), [decision-v3.json](security-hardening/production-p2p-nat-v1/controlled-network-spike/decision-v3.json), and [handoff-v6.json](security-hardening/production-p2p-nat-v1/implementation/handoff-v6.json) record the closed libjuice checkpoint. Earlier v1/v2 records remain immutable history, and later libnice records supersede this as current authority.
- Exact acquisition: the approved official libjuice v1.7.2 archive and Android NDK `ndk;28.2.13676358` (`r28c`) were acquired and hashed. The libjuice archive SHA-256 is `75159867c4a5a689a6559e11aa0d30c9eba12ce73a4ae3d898b521467e1f635d`; its exact 81-file extracted tree SHA-256 is `c17e0d6d3855e9584718584ab644f030939448d0e8f6a8bf5ca9883da719a330`; the retained NDK archive SHA-256 is `0d4599e8bbf1a1668a0d51a541729b2246360f350018a2081d0b302dbb594f2a`.
- Audit outcome: [libjuice-source-audit-v1.json](security-hardening/production-p2p-nat-v1/controlled-network-spike/phase-a/libjuice-source-audit-v1.json) rejects libjuice before compilation. Five independent P1 profile failures cover target-platform predictable ICE randomness, default-level ICE password logging, unauthenticated Binding error handling, unauthenticated TURN redirect handling, and the absence of a numeric-only pre-I/O authorization boundary.
- Compile boundary: source inspection completed, but no compiler, static archiver, linker, loader, `nm`, adapter generation, native build wiring, source execution, socket, or runtime network operation occurred. The Android and macOS compile-only unit is `not_run_candidate_rejected_before_compile`.
- Historical fallback boundary: [review-v2.json](security-hardening/production-p2p-nat-v1/controlled-network-spike/review-v2.json) opened `libnice-0.1.23-glib-c-abi` as `proposed_not_selected`. At this checkpoint no libnice or GLib source/dependency acquisition, selection, compilation, or execution was authorized; later decision-v4 through decision-v6 consumed bounded intake authority and rejected the candidate.
- Historical state tuple: [progress-v3.json](security-hardening/production-p2p-nat-v1/controlled-network-spike/phase-a/progress-v3.json), [decision-v3.json](security-hardening/production-p2p-nat-v1/controlled-network-spike/decision-v3.json), [handoff-v6.json](security-hardening/production-p2p-nat-v1/implementation/handoff-v6.json), and [libjuice-source-audit-v1.json](security-hardening/production-p2p-nat-v1/controlled-network-spike/phase-a/libjuice-source-audit-v1.json) pin five independent P1 blockers and `android_macos_compile_only_integration=not_run_candidate_rejected_before_compile`.
- Historical final no-device aggregate: `build/qa/check-no-device-quality-p2p-libjuice-source-audit-rejection-final-20260717.log` exits 0 with exactly one `No-device quality checks passed.` marker. The run includes the 44-file preflight, 7 historical progress tests, 11 acquisition-authority tests, 12 source-rejection tests, and a read-only retained-byte rehash. Its existing development-relay loopback tests are separate from P2P Phase A and do not execute libjuice.
- Historical next decision: obtain explicit approval for exact official libnice 0.1.23 and required dependency acquisition for bounded read-only source audit only. That dependency was later satisfied in bounded form without authorizing compilation, sockets, runtime/harness networking, Phase B, production networking, or deployment.
- Proof boundary: this is no-device exact artifact intake and static rejection evidence only. It does not prove Android/macOS compilation, ABI or symbol compatibility, runtime ICE/STUN/TURN, NAT traversal, physical Android behavior, live-network behavior, Phase B, deployment, or production readiness.

## Historical Production P2P/NAT Phase A Progress V1 (Final Review Blocked)

- Historical authority: [progress-v1.json](security-hardening/production-p2p-nat-v1/controlled-network-spike/phase-a/progress-v1.json) is the immutable pre-acquisition evidence-status snapshot. [handoff-v4.json](security-hardening/production-p2p-nat-v1/implementation/handoff-v4.json) remains the immutable approval-time snapshot for the four bounded Phase A recommendations; later evidence status does not rewrite either snapshot.
- Phase A progress: 4 recommendations are approved for bounded Phase A; 2 bounded evidence groups are complete (cross_platform_session_crypto_vectors and static_harness_and_egress_policy); 2 are blocked (libjuice_supply_chain_and_source_audit=blocked_missing_offline_source and android_macos_compile_only_integration=blocked_missing_reviewed_source); the final Phase A security review is blocked_on_source_and_compile_evidence.
- Final gate evidence: `build/qa/check-no-device-quality-p2p-phase-a-progress-v1-final-reviewed-20260717.log` exits 0 across 12,108 lines with one overall success marker, one Phase A progress addendum, two successful progress validator runs, a 22-file SHA-256 preflight before import, the 7-test progress mutation suite, 88 local development-relay match lines, freshness across 56 authenticated relay connections, and 905 encrypted frame bodies.
- Historical evidence boundary: the 2026-07-13 aggregate remains an actual 19-file preflight result and is not retroactively changed by the new 22-file contract.
- Closed authority: source acquisition and source execution, compiler/archive invocation, socket creation, runtime/harness/controlled-spike network I/O, Phase B execution/network/socket authority, external egress, production network I/O, and production deployment are all `false`.
- Proof boundary: this is current no-device static and local regression evidence only. It is not physical Android or live-network proof and does not establish source acquisition, compilation, library execution, sockets, ICE/STUN/TURN traffic, NAT traversal, Phase B, external egress, production networking, or deployment.

## v0.2 Android Chat Sessions Bulk Terminal Authority

- Date: 2026-07-17.
- Status: implemented and JVM-verified. All three focused regressions, all 597 `RuntimeClientViewModelTest` tests, and all 1,071 Android app JVM tests pass under Android Studio JBR.
- Authority boundary: runtime-authoritative archive-all and delete-all terminals now require the exact pending request id, receiving channel object, connection generation, and authenticated authority generation. Success frames additionally require the pending lifecycle operation type.
- State boundary: a wrong-channel, old-connection, or prior-authentication success cannot apply local archive/delete persistence, clear bulk progress, or start reconciliation. A stale `authentication_required` error cannot revoke the current authenticated session, and stale malformed or ordinary errors cannot consume the current bulk operation.
- Send boundary: asynchronous send failures use the same matcher against the captured dispatch channel, connection generation, request id, operation type, and authenticated authority before failure handling or reconciliation.
- Regression boundary: `chatSessionsBulkLifecycleRequiresExactTerminalAuthority` injects current and prior-batch request ids through a foreign channel, a prior connection generation, and a prior authentication generation for success, authentication, ordinary, and malformed terminals before proving exact-current completion. `chatSessionsBulkMalformedCurrentErrorConsumesOnlyExactAuthority` proves an exact malformed error consumes only its own operation and makes its late success inert. `chatSessionsBulkSendFailureRequiresExactDispatchAuthority` proves exact failure closure plus delayed wrong-channel, old-connection, and prior-authentication failure isolation.
- Namespace boundary: every bulk batch uses `chat-sessions-bulk-` request ids. Noncurrent namespaced errors are discarded before generic handling even after a batch advances or the operation completes.
- Durable gate boundary: the default Android selector includes all three regressions and `check_android_chat_sessions_bulk_terminal_authority_junit` requires exactly one executed JUnit testcase for each canonical name with no skip, failure, or error. Copy hygiene pins the source-aware matcher across result, malformed-error, ordinary-error, and send-failure paths plus the executable tests, selectors, exact JUnit tuple, marker, protocol text, and aligned roadmap/progress/QA sections.
- Final aggregate evidence: `build/qa/check-no-device-quality-chat-sessions-bulk-terminal-authority-final-reviewed-20260717.log` exits 0 across 12,089 lines with one overall success marker, one dedicated bulk terminal-authority marker, one dynamic JUnit proof marker, two zero-delay registry self-tests, 88 local development-relay match lines, freshness across 56 authenticated relay connections, and 905 encrypted frame bodies.
- Approval boundary: no wire schema, capability, source acquisition, client execution, socket/network, controlled-spike Phase B, production networking, or deployment authority changes. The four controlled-spike approvals remain bounded Phase A.
- Evidence boundary: this is Android JVM no-device proof. It does not prove a physical Android device, optical QR, peer receipt, live-provider behavior, external networking, production relay/P2P, NAT traversal, performance, or deployment.

## v0.2 Android Authenticated Read Rollover And Session-List Receive Authority

- Date: 2026-07-17.
- Status: implemented and final-verified. All four focused regressions, all 594 `RuntimeClientViewModelTest` tests, and all 1,068 Android app JVM tests pass under Android Studio JBR. The final GPT-5.6 Sol re-review reports no P0-P3 findings, and the refreshed default no-device aggregate exits 0.
- Receive boundary: every `chat.sessions.list` result now requires the exact request id, receiving channel object, connection generation, and authenticated authority generation before page accounting, metadata decoding, or any history state can change. A frame from the wrong channel, old connection, or prior authentication remains inert.
- Pagination boundary: exact receive authority is checked before `pageCount`, accumulated summaries, session ids, cursors, snapshot count, malformed-terminal handling, continuation dispatch, search state, or bulk-lifecycle state can change. A stale page cannot advance pagination or force an apparent terminal failure.
- Terminal boundary: exact-current result, malformed result, protocol error, and send failure retain the existing single-use closure behavior. Duplicate and delayed terminals cannot consume a replacement request, publish an error, revoke a newer session, or mutate chat history.
- Reauthentication boundary: successful same-channel reauthentication clears pending `memory.list` and `research.notebooks.list` authority. Android-generated memory-list request ids now use the `memory-list-` namespace, so old results and errors remain inert before generic error handling; the old research timeout is canceled, and current replacement requests remain usable instead of being blocked by orphaned pending ids.
- Revocation boundary: authentication revocation now explicitly clears pending `memory.list` authority and continues to clear `research.notebooks.list` through research-session cleanup. An authentication error for a sibling request cannot leave memory refresh permanently blocked.
- Durable gate boundary: the default Android selector includes all four regressions and a dedicated JUnit XML parser requires exactly one executed testcase for every canonical name with no skip, failure, or error. Copy hygiene pins the source-aware handler, authority matcher, lifecycle clears, executable tests, selectors, JUnit tuple, marker, and aligned roadmap/progress/QA sections.
- Focused evidence: `chatSessionsListRequiresExactCurrentAuthorityAndConsumesOnce`, `chatSessionsListWrongSourceCannotAdvancePaginationOrTriggerTerminalFailure`, `sameChannelReauthenticationReplacesPendingMemoryAndResearchListAuthority`, and `siblingAuthenticationErrorClearsConcurrentPendingMemoryListAuthority` pass with `tests=4`, `skipped=0`, `failures=0`, and `errors=0`.
- Review remediation: the first GPT-5.6 Sol review found one P2 stale `memory.list` error fallthrough and one P3 copy-guard false-pass risk. The request namespace plus exact-current error branch closed those findings. A targeted re-review then found one P2 exact malformed-error correlation leak and one P3 guard-ordering gap; terminal closure before error publication, replacement-and-late-error regression coverage, and branch-local clear-before-publication inspection close both. The final GPT-5.6 Sol re-review reports no P0-P3 findings.
- Final aggregate evidence: `build/qa/check-no-device-quality-authenticated-read-rollover-authority-final-reviewed-20260717.log` exits 0 across 12,083 lines with one overall success marker, one dedicated rollover marker, one dynamic JUnit proof marker, two zero-delay registry self-tests, 88 local development-relay match lines, freshness across 56 authenticated relay connections, and 905 encrypted frame bodies.
- Approval boundary: no wire schema, capability, provider route, source acquisition, client execution, socket/network authority, controlled-spike Phase B, production networking, or deployment authority changes. All four controlled-spike approvals remain bounded Phase A.
- Evidence boundary: this is Android JVM no-device proof. It does not prove a physical Android device, optical QR, peer receipt, live-provider behavior, external networking, production relay/P2P, NAT traversal, performance, or deployment.

## v0.2 Android Authenticated Transcript And Document Read Authority

- Date: 2026-07-17.
- Status: implemented and final-verified. All ten focused authority regressions, all 590 `RuntimeClientViewModelTest` tests, and all 1,064 Android app JVM tests pass under Android Studio JBR. The refreshed default no-device aggregate exits 0, and the final GPT-5.6 Sol re-review reports no P0-P3 findings.
- Request boundary: every `chat.messages.list`, `index.documents.list`, and `retrieval.query` operation captures its exact request id, channel object, connection generation, and authenticated authority generation. A terminal can act only while all four values still match the current authenticated runtime session.
- Transcript boundary: only an exact-current `chat.messages.list` result may publish or persist transcript messages. Wrong-channel, old-connection, prior-authentication, duplicate, and superseded results remain inert; malformed exact-current results consume only their own pending authority before any retry.
- Document boundary: `index.documents.list` and `retrieval.query` results update only transient catalog or search state after the same authority check. Semantic-to-lexical fallback can run only for the exact current search error and reuses the captured request payload; it cannot be triggered by a stale response.
- Terminal boundary: exact-current results, request-specific errors, and send failures are single-use. Delayed failures for a replaced request cannot close its replacement, publish an error, revoke authentication, start fallback, mutate transient document state, publish transcript state, or write device history.
- Lifecycle boundary: successful reauthentication on the same channel, disconnect, authenticated-session revocation, receive-failure closure, and ViewModel clear remove pending transcript and document authority. A later session cannot be consumed by a terminal from the prior authentication or connection lifetime.
- Durable gate boundary: the default Android selector includes all ten authority regressions, then parses the generated JUnit XML and requires exactly one executed testcase for every name with no skip, failure, or error. It emits `Covered v0.2 addendum: Android authenticated transcript and document read current-request authority.` Copy hygiene pins the production correlation structures, request-bound send failures, tests, selectors, dynamic JUnit proof, marker, and roadmap/progress/QA contract.
- Terminal-coverage boundary: the four added tests directly prove exact-current catalog error consumption, immediate catalog send-failure retry with late-frame isolation, delayed superseded `chat.messages.list` send-failure isolation, and independent transcript authority cleanup on disconnect, revocation, and ViewModel clear. No production change was required.
- Final aggregate evidence: `build/qa/check-no-device-quality-authenticated-read-terminal-closure-final-reviewed-20260717.log` exits 0 across 12,075 lines with one overall success marker, one dedicated authority marker, one dynamic JUnit proof marker, two zero-delay registry self-tests, 88 local development-relay match lines, freshness across 56 authenticated relay connections, and 905 encrypted frame bodies. The prior six-test aggregate remains historical only.
- Review boundary: the pre-implementation GPT-5.6 Sol audit reports no P0-P3 production finding and confirms the four new tests use existing production and test seams. The first evidence review found one P3 raw-name copy-guard false-pass risk, and the first remediation review found one further P3 because source regex alone could accept ignored or commented tests. The final evidence review found one P3 because copy hygiene did not pin every canonical name into the dynamic JUnit tuple. All three are remediated: copy hygiene requires the `@Test` declaration, compares the tuple exactly with the ten ordered unique canonical names, and the no-device gate requires generated JUnit XML to contain each executed testcase with no skipped, failed, or errored result. The exact ten-selector JUnit XML records `tests=10` with zero skips, failures, or errors. The final delta re-review reports no P0-P3 findings.
- Approval boundary: the wire schema and capabilities are unchanged. The four controlled-spike approvals remain limited to bounded Phase A; source acquisition, sockets/network, Phase B, production networking, and deployment remain closed. The P2P/NAT source-independent review is exhausted until the approved offline `libjuice` source is supplied at its fixed path.
- Evidence boundary: this is Android JVM no-device proof. It does not prove a physical Android device, optical QR, peer receipt, live-provider behavior, external networking, production relay/P2P, NAT traversal, performance, or deployment.

## v0.2 Android Persistent-Memory Mutation Current-Request Authority

- Date: 2026-07-17.
- Scope: Android-local current-request authority for authenticated `memory.upsert` and `memory.delete`, using client-generated `memory-upsert-<UUID>` and `memory-delete-<UUID>` ids without changing either wire operation.
- Correlation contract: each pending mutation records the exact operation, logical target (`NewEntry` exact trimmed content or `ExistingEntry` exact id), expected result fields (`entry.id` when known, exact `entry.content`, exact `entry.enabled`, or exact deleted `id`), channel object, connection generation, and authenticated runtime-authority generation. The transmitted outbound payload is decoded in regression coverage and must match those exact request-bound values.
- Terminal contract: one exact-current valid, malformed, mismatched, protocol-error, or request-bound send-failure terminal consumes the pending record and deadline exactly once before publication. The receive-loop-captured source channel and connection generation flow unchanged through ingress dispatch. Late/duplicate/stale, wrong-channel, old-connection, prior-authentication, and delayed replaced-authority terminals are inert.
- Scheduling contract: same-target mutations are serialized while one is pending; independent targets may proceed concurrently and terminate independently.
- Full-list ordering contract: dispatch invalidates any older pending `memory.list`; a regression delivers that response while the mutation is still pending and proves it inert. A distinct list started during the mutation is invalidated when the exact mutation terminal wins. If the list publishes first, the later exact mutation applies its delta. A stale full-list response therefore cannot erase an add, revert an enable change, or resurrect a delete.
- Recovery contract: the production local deadline is 15 seconds. Timeout consumes only the exact request, publishes a bounded local error, requires fresh unqueried `memory.list` reconciliation, and never automatically retries the mutation. Independent sibling mutations defer reconciliation until the final sibling closes; invalidating an in-flight required reconciliation preserves the requirement and reissues a fresh request. Disconnect, receive failure, successful reauthentication, authentication revocation, and ViewModel clear cancel deadlines and clear pending mutation authority.
- Focused five-test proof: the explicit Gradle selection passes `memoryUpsertResultRejectsUnknownMetadataBeforeMemoryMutation`, `memoryDeleteResultRejectsUnknownMetadataBeforeMemoryMutation`, `memoryMutationResultsRequireExactCurrentAuthorityAndExpectedPayload`, `memoryMutationErrorsRequireExactCurrentAuthorityAndConsumeOnce`, and `memoryMutationSendFailureAndLifecycleCleanupRequireExactAuthority`, covering closed payloads, exact result expectations, one-shot errors, same/independent-target scheduling, timeout reconciliation, send-failure races, and lifecycle cleanup.
- Verification status: implemented and final-verified. All 600 `RuntimeClientViewModelTest` tests and all 1,074 Android app JVM tests pass with zero skips, failures, or errors. `build/qa/check-no-device-quality-memory-mutation-authority-final-reviewed-20260717.log` exits 0 across 12,101 lines with one overall success marker, one dedicated authority marker, one dynamic five-test JUnit proof marker, one dynamic production-deadline JUnit proof marker, two zero-delay registry self-tests, 88 local development-relay matches, freshness across 56 authenticated connections, and 905 encrypted frame bodies.
- Review status: the first GPT-5.6 Sol implementation review found the stale full-list overwrite P2 and existing-entry toggle binding P3. The later evidence review found sibling-timeout reconciliation cancellation, a stale-list false-pass, production-ingress and transmitted-payload proof gaps, and missing dynamic production-deadline execution evidence. Deferred required reconciliation with reissue, observable pre/during-list ordering, old-channel receive-loop ingress, decoded outbound payload assertions, and the second JUnit XML verifier remediate those findings. The final GPT-5.6 Sol re-review reports no remaining P0-P3 finding; the refreshed aggregate closes the final stale-evidence P3.
- Approval boundary: this slice changes no protocol message, schema/field, capability, host mutation semantics, provider route, client execution authority, socket/network authority, controlled-spike Phase B, production networking, or deployment authority.
- Proof boundary: no-device JVM proof does not establish physical Android, optical QR, peer receipt or exactly-once host mutation, real lost-response recovery beyond deterministic timeout, live-provider/live-network behavior, production relay/P2P/NAT, Phase B, or deployment.

## v0.2 Android `runtime.health` Current-Request Authority

- Date: 2026-07-17.
- Status: implemented and final-verified. All seven `runtimeHealth*` focused tests, all 580 `RuntimeClientViewModelTest` tests, and all 1,054 Android app JVM tests pass under Android Studio JBR. The first GPT-5.6 Sol review found no implementation defect and identified two P2 plus one P3 test-evidence gaps; those gaps are remediated, and the final GPT-5.6 Sol re-review reports no remaining P0-P3 finding.
- Request boundary: every authenticated health request uses a fresh `runtime-health-<UUID>` id and captures the exact channel object, connection generation, and authenticated runtime-authority generation. A newer request replaces pending authority for the older request.
- Terminal boundary: only the latest exact result, request-specific error, or send failure may close correlation or mutate UI/session state. Stale ids, duplicates, wrong-channel frames, old-connection frames, prior-authentication frames, superseded errors, and delayed superseded send failures are inert before payload validation, error publication, authentication revocation, or refresh fanout.
- Completion boundary: an exact malformed or unknown-metadata result is terminal. A valid exact result clears pending authority before publishing status and issuing model, chat-session, memory, memory-summary, and research refreshes once. An exact error or send failure also clears only that request.
- Lifecycle boundary: disconnect, receive-failure connection closure, authentication revocation, successful reauthentication, and ViewModel clear remove pending health authority. A replacement session starts with an independent request and cannot be consumed by the prior channel, connection, or authentication generation.
- Durable gate boundary: the default no-device Android selector includes latest-only publication, independently varied channel/connection/authentication authority, exact-current error/decoder/send-failure closure with duplicate-and-retry behavior, disconnect/revocation/ViewModel-clear cleanup, and superseded error/delayed-send-failure regressions. It emits `Covered v0.2 addendum: Android runtime.health current-request authority.` Copy hygiene pins the implementation, lifecycle clears, all five new authority regressions, selector, marker, request-id prefix assertion, and documentation boundary.
- Final aggregate evidence: `build/qa/check-no-device-quality-runtime-health-authority-final-20260717.log` exits 0 across 12,081 lines with one `No-device quality checks passed.` marker, one dedicated Android `runtime.health` current-request-authority marker, 88 local development-relay match lines, freshness across 56 authenticated relay connections, and 905 encrypted frame bodies.
- Approval boundary: the request and response schemas are unchanged. No capability, provider route, client execution, source or model permission, socket/network authority, controlled-spike Phase B, production networking, or deployment authority is added. All four controlled-spike approvals remain bounded Phase A.
- Evidence boundary: current tests are Android JVM no-device proof. They do not prove physical Android, optical QR, peer receipt, live-provider behavior, external networking, production relay/P2P, NAT traversal, performance, or deployment.

## v0.2 Fail-Closed Resource-Bounded Provider Model-Catalog Trust Boundary

- Date: 2026-07-17.
- Status: the provider ingestion and metadata boundary remains complete; the bounded public `models.list` single-flight extension is implemented and passes its seven focused regressions, all 1,615 current-source Swift tests, static/integrity checks, final GPT-5.6 Sol re-review, and the refreshed default no-device aggregate.
- Ingestion boundary: Ollama `/api/tags`, `/api/ps`, and `/api/show` plus LM Studio native and fallback catalog reads use true streaming ingestion capped at 4 MiB (4,194,304 bytes). An oversized positive `Content-Length` fails before body ingestion; unknown or inaccurate lengths stop at limit plus one. Non-catalog provider requests keep their existing paths.
- Row and fanout boundary: each catalog shape admits at most 256 rows without truncation. Ollama combines installed and running identities before any detail dispatch and rejects more than 256 unique names, so `/api/show` fanout is also capped at 256; cancellation is propagated through that loop. A successful oversized or structurally untrusted show response excludes only that model. LM Studio admits at most 256 unique nonblank `loaded_instances` identifiers of at most 512 code points per model before unload POST fanout and revalidates the same state during polling.
- Metadata and context-window trust boundary: `id`, `name`, `provider_model_id`, and present `remote_model` contain at least one code point outside the shared fixed blank/invisible set and are capped at 512 Unicode code points; `qualified_id` is capped at 522. Capabilities admit at most 32 byte-exact-after-decoding unique values with the same content rule and at most 128 code points each; NFC/NFD-distinct values remain distinct. Optional size is an exact integer in 0...9,223,372,036,854,775,807. `context_window_tokens` remains an exact integer in 1...16,777,216 after precision-safe `Decimal`, `NSDecimalRound`, and alias-consistency checks. Every limit is exact/plus-one tested and excess fails closed rather than truncating.
- Provider boundary: strict malformed and duplicate/escape-equivalent JSON rejection, Ollama exact/canonical `:latest` identity checks, LM Studio exact/NFC identity checks, and byte-exact alias agreement remain active. LM catalog fallback remains limited to native 404, 405, or 501 and never follows an oversized/malformed response or transport/auth failure. Native chat still requires explicit `chat.end`; `parser.finish()` now has a positive final-line-without-trailing-blank regression in addition to malformed-partial and terminal-less EOF rejection.
- Runtime and wire boundary: the router revalidates all row and metadata bounds, serializes `size_bytes` as exact `Int64`, and encodes the complete response before publishing the existing `models.list` shape. Plaintext above 1,048,560 bytes is rejected so the 16-byte relay authentication tag cannot push the frame above the 1 MiB codec ceiling. Any injected invalid non-nil metadata or valid-field Cartesian product above that aggregate limit rejects the whole catalog as `bad_backend_response`. Invalid LM Studio context rejects its catalog; only genuinely absent metadata or the explicit Ollama context-only omission retains conservative legacy compaction fallback. JSON Schema and Android enforce the same field rules.
- Public dispatch boundary: up to eight concurrent public `models.list` waiters share one provider catalog operation; a ninth receives a sanitized retryable `backend_unavailable`. Every waiter retains its own request id and publication authority. A canceled non-last waiter returns immediately and leaves shared work available, last-waiter cancellation stops provider work, and the canceled flight must retire before replacement. Success and failure are not cached. Internal authority catalog lookups remain outside public coalescing so their security decisions stay fresh.
- Single-flight focused evidence: `build/qa/swift-focused-model-catalog-single-flight-final-reviewed-20260717.log` records seven `LocalRuntimeMessageRouterTests/testModelsListSingleFlight*` regressions with zero failures in 0.436 seconds. They pin the eight-plus-one admission boundary, unique request ids, success/failure non-caching, partial and last-waiter cancellation, sixteen canceled-waiter churn iterations without caller accumulation or another provider call, retirement before replacement, and stale reauthentication publication suppression. This is no-device mock-backend proof, not live-provider capacity or throughput proof.
- Verification boundary: focused provider proof is URLProtocol/unit evidence and Android proof is JVM evidence. Independent review found cancellation absorption, unbounded loaded-instance unload fanout, aggregate frame overflow, integer precision loss, cross-platform blank/uniqueness drift, provider-path Unicode capability coalescing, durable-selector gaps, and canceled-waiter caller accumulation; all are remediated with exact-boundary, continuation, and fail-closed regressions. `build/qa/swift-focused-provider-catalog-resource-bounds-20260717.log` records the earlier 119-test provider selection with two expected opt-in live-provider skips and zero failures. `build/qa/swift-full-provider-catalog-single-flight-final-reviewed-20260717.log` records all 1,615 current-source Swift tests with the same two skips and zero failures in 350.641 seconds. Android Studio JBR records all 133 `ProtocolCodecTest` tests with zero failures, errors, or skips. The final GPT-5.6 Sol re-review reports no P0-P3 findings after the waiter-continuation remediation. The closed P2P/NAT collection is refreshed to `6e6dfbfc0cdb70370c30f54222584b69042a6e22b6df04c7f3e65043c38522bd`; the still-unselected production-relay collection is `e188e1b885419e376b9dcea85282b4aafb1d48692b134edc13aff2eedfbf6b66`; and the still-unselected Runtime-Python manifest/review hashes are `5d306ba9e53824a5934fc4e77ea767fdc43a644ef0c24dbd3dd943b99cebb6f6` and `ae42c42dac52fe82c0de09675d4ca51ce4dc3ac45e52e8c6266484a8dd841e75`. All three validators pass without opening execution or production authority. The prior 1,608-test full capture and older integrity captures are historical only.
- Final aggregate evidence: `build/qa/check-no-device-quality-model-catalog-single-flight-final-reviewed-20260717.log` exits 0 across 12,064 lines with one `No-device quality checks passed.` marker, one resource-bounded provider model-catalog marker, one bounded public `models.list` single-flight marker, two zero-delay registry self-tests, 88 local development-relay match log lines, freshness across 56 authenticated relay connections, and 905 encrypted frame bodies.
- Authority boundary: the schema and Android decoder tighten the existing response shape but add no protocol field, Android action, provider route, socket/network authority, controlled-spike Phase B, production networking, or deployment authority. The four controlled-spike approvals remain bounded Phase A. No physical-device, live-provider, peer-receipt, or external-network result is claimed.

## v0.2 Provider-Confirmed Runtime Model Unload State

- Date: 2026-07-16.
- Status: implemented and verified with strict provider-state parsing, exact unload acknowledgements, bounded post-unload polling, host-only transition/failure state, focused regressions, current-source opt-in localhost live-provider tests, all 1,534 Swift tests, two GPT-5.6 Sol final re-reviews, and the refreshed default no-device aggregate.
- Provider boundary: Ollama first resolves the canonical running target through `GET /api/ps`, sends an empty non-streaming `/api/chat` request with `keep_alive: 0`, requires `done: true` plus `done_reason: unload`, and then polls `/api/ps` until the target is absent. LM Studio resolves only the exact native model key and exact observed instance ids, requires each `/api/v1/models/unload` acknowledgement to return the same instance id, and then polls the native model list until no target instance remains.
- Structural boundary: every unload-specific provider response is validated before DTO decoding. Duplicate JSON object names at any depth, including escape-equivalent names, malformed JSON, excessive nesting, missing/null LM Studio residency, duplicate exact model records, mismatched acknowledgements, and persistent residency fail closed instead of becoming a false success.
- Result boundary: only a provider-confirmed or already-absent outcome clears runtime residency. Unsupported or mismatched provider/model results and thrown failures retain possibly resident state for manual and idle unloads; a failed model switch admits the requested new model but preserves the structured prior failure for diagnosis.
- Host/UI boundary: aggregate state-change events publish generation-count transitions without adding activity-log noise. macOS Status shows localized `Unloading` while provider verification is pending and `Needs attention` when absence could not be confirmed; the unload action and idle-policy picker reject overlapping intent while their corresponding update is active. Android remains status-only and no wire shape changes.
- Durable gate boundary: the default no-device selector covers strict duplicate-key rejection at initial lookup and polling, malformed or mismatched acknowledgements, already-absent/unsupported outcomes, cancellation, bounded persistent-residency failure, exact result identity, host publication with no state-only logs, policy-intent serialization, five-language localization, and compact status rendering. It emits `Covered v0.2 addendum: provider-confirmed runtime model unload state.` and deliberately excludes both live-provider selectors.
- Current focused evidence: 62 Ollama/LM Studio tests pass with two opt-in live tests skipped; the strengthened host publication regression and both Ollama duplicate-state regressions also pass. The broader host selection passes 40 tests, five-locale localization passes, and GPT-5.6 Sol verified all 119 localization tests plus 14 render smokes while reviewing this slice.
- Current full-suite evidence: `build/qa/swift-full-provider-confirmed-model-unload-final-reviewed-20260716.log` records all 1,534 current-source Swift tests with zero failures in 338.238 seconds. The only two skips are the explicitly opt-in localhost live-provider tests, which pass separately under their exact environment gates.
- Final aggregate evidence: `build/qa/check-no-device-quality-provider-confirmed-model-unload-final-reviewed-20260716.log` exits 0 across 11,829 lines with one overall success marker, one dedicated provider-confirmed unload marker, two zero-delay registry self-tests, 88 loopback development-relay matches, freshness across 56 relay connections, and 905 encrypted frame bodies.
- Live-provider boundary: `testLiveOllamaConfirmedUnload` passes in 0.318 seconds against preloaded `gemma4:e4b-mlx`; `testLiveLMStudioConfirmedUnload` passes in 0.018 seconds against native key `text-embedding-nomic-embed-text-v1.5` and its preloaded `aetherlink-live-unload-proof` instance. Their captures are `build/qa/live-ollama-model-unload-confirmation-20260716.log` and `build/qa/live-lmstudio-model-unload-confirmation-20260716.log`; neither downloads a model or belongs to the default no-device gate. Both providers report no loaded model afterward.
- Review boundary: GPT-5.6 Sol review found and remediation covered missing/null LM Studio residency, raw error exposure, exact unload-result identity, live state publication, rapid policy-intent ordering, duplicate JSON-name bypasses, and a weak no-log assertion. Final provider and host/evidence re-reviews report no P0-P3 findings; direct parser probes, the no-log assertions, all 85 default-gate filters, localization, render, static checks, and the aggregate pass.
- Evidence boundary: unit and rendering proof is no-device. Localhost Ollama/LM Studio proof is separately labeled live-provider evidence and does not prove physical Android, optical QR, peer receipt, external networking, production relay/P2P, NAT traversal, measurement, or deployment.
- Device state: Android SDK `adb devices -l` lists no attached device, so the aggregate makes no physical-device claim.
- Approval boundary: no provider route, model permission, source access, process/file authority, protocol/schema/capability, client execution, socket/network authority, controlled-spike Phase B, production networking, or deployment authority is added. All four controlled-spike approvals remain bounded Phase A.

## v0.2 Runtime Model Idle-Unload Policy User Control

- Date: 2026-07-16.
- Status: implemented with persisted runtime-host-local 5, 10, and 30 minute presets, provider-unload serialization, cancellation-aware waiters, serialized policy updates, focused backend/persistence/localization regressions, direct supported/unsupported picker rendering across five languages, and all 1,504 current-source Swift tests passing. Ten minutes remains the default.
- Timer boundary: changing the policy while a model is already idle preserves the original monotonic idle start. A shorter policy unloads immediately when its deadline has already passed; a longer policy schedules only the remaining interval. Every cancel or reschedule advances a timer generation, so a cancelled task that wakes late cannot unload the current resident model. The regression injects both the sleeper and an unload-attempt acknowledgement, then waits for the stale callback to complete before asserting state.
- In-flight/provider boundary: a policy change never unloads a model with an active generation. The selected delay is applied when that generation finishes. Once an unload is claimed under the residency lock, a same-model request waits for that provider unload to complete before provider chat or embedding dispatch; manual unload and model-switch paths use the same operation registry. Cancellation is rechecked before reservation and provider dispatch, so cancelled waiters cannot reserve residency or dispatch provider work.
- Persistence/UI boundary: `UserDefaults` stores only one closed string enum and rejects unknown values back to the 10-minute default. Both the production aggregate and an injected aggregate backend are configured with the restored value. A serialized update queue preserves host selection order and only the latest completed update refreshes published residency state. macOS Status exposes a localized compact segmented selector; unsupported providers expose a disabled control with `Unavailable` state and a provider-residency reason. Android remains a status-only client and receives the current delay through the existing `runtime.health.model_residency.idle_unload_delay_seconds` field.
- Durable gate boundary: the default no-device selector runs `RuntimeModelIdleUnloadPolicyTests`, elapsed-shortening, in-flight deferral, same-model unload serialization, cancelled same-model/cross-model chat and embedding waiters, and acknowledged stale-timer invalidation regressions. It also selects the direct picker render and injected-aggregate integration tests in addition to the full localization/render suites, then emits `Covered v0.2 addendum: runtime model idle-unload policy user control`.
- Review boundary: the GPT-5.6 Sol review sequence found six P2 implementation/evidence issues and six P3 test/guard/evidence issues in total. Current source serializes provider unload and policy updates, defers new-model admission until switch unload completion, rechecks cancellation before reservation/dispatch, applies restored policy to injected aggregates, acknowledges stale callbacks deterministically, exposes state-aware accessibility, renders the exact picker in both support states, and pins its binding/tags/accessibility in durable guards. Final core re-review reports no P0-P3 findings; final UI confirmation reports no remaining code, localization, render, selector, or guard defect.
- Current full-suite evidence: `build/qa/swift-full-runtime-model-idle-unload-policy-final-reviewed-20260716.log` records all 1,504 Swift tests passing with zero failures in 318.645 seconds, including all 14 macOS render smokes. The changed `CompanionAppModel.swift` refreshes the closed P2P/NAT 13-artifact collection to `2f1936f36c4945f74173477eb0ab65736bb0236fa2aca0eff7d0e3e210f90459`; its validator passes with the socket gate closed.
- Final aggregate evidence: `build/qa/check-no-device-quality-runtime-model-idle-unload-policy-final-reviewed-20260716.log` exits 0 across 11,678 lines with one overall success marker, one dedicated runtime model idle-unload policy marker, two zero-delay registry self-tests, 88 loopback development-relay matches, and 905 encrypted frame bodies. Android SDK `adb devices -l` lists no attached device.
- Evidence boundary: current focused proof is SwiftPM, isolated `UserDefaults`, mock backends, and sampled nonblank offscreen macOS rendering. The direct render proves the exact picker produces meaningful pixels in supported/unsupported states; it does not prove text clipping absence, VoiceOver traversal, live Ollama or LM Studio unload behavior, physical Android, optical QR, peer receipt, external networking, production relay/P2P, NAT traversal, measurement, or deployment.
- Approval boundary: this changes no protocol schema, client execution, provider route, model permission, source access, process/file scope beyond the existing host preference, socket/network authority, controlled-spike Phase B, production networking, or deployment authority.

## v0.5 Memory-Summary Durable Terminal Decision Linearization

- Date: 2026-07-16.
- Status: implemented and verified with six direct JSONL terminal-decision regressions, five focused router regressions, 98 affected memory tests, all 1,490 current-source Swift tests, a final GPT-5.6 Sol re-review reporting no P0-P3 findings, and the refreshed default no-device aggregate passing.
- Terminal boundary: the production JSONL store resolves approval and dismissal as one owner-and-draft-scoped terminal state while holding the canonical-path recursive lock and coordination-file `fcntl` write lock across history reread, decision, and append. Same-process store instances and a separate Python process prove opposite decisions cannot both commit.
- Replay boundary: event state replays in physical append order rather than wall-clock timestamp order. Approval retry therefore preserves a later edit and disabled state even after clock rollback, and a later rollback-timestamp delete remains deleted instead of being resurrected.
- Retry boundary: repeated approval returns the current surviving source-bound entry without another append; repeated dismissal returns the first persisted timestamp. Approval after dismissal, dismissal after approval, contradictory historical terminal state, and approval retry after deletion fail closed without mutation.
- Store/error boundary: the protocol default no longer falls back to generic upsert; a store without explicit atomic approval support throws a fail-closed unsupported error. The router maps terminal conflicts to `memory_summary_draft_unavailable` and every other decision-store failure to a fixed `memory_store_unavailable` response without exposing the raw store error.
- Durable gate boundary: the default no-device selector runs `RuntimeMemoryStoreSummaryDecisionTests` and emits `Covered v0.5 addendum: memory-summary durable terminal decision linearization`. Copy hygiene pins the store API, physical replay, process lock, rollback/edit/delete regressions, sanitized router mapping, five documentation surfaces, selector, and marker.
- Current full-suite evidence: `build/qa/swift-full-memory-summary-terminal-decision-final-reviewed-20260716.log` records 1,490 tests with zero failures in 286.018 seconds. Final GPT-5.6 Sol re-review reports no remaining P0-P3 findings after the atomic-default, physical-replay, sanitized-error, and real process-lock remediations.
- Final aggregate evidence: `build/qa/check-no-device-quality-memory-summary-terminal-decision-final-reviewed-20260716.log` exits 0 across 11,618 lines with one overall success marker, one dedicated terminal-linearization marker, two zero-delay registry self-tests, 88 loopback development-relay matches, and 905 encrypted frame bodies. Android SDK `adb devices -l` lists no attached device.
- Integrity refresh: the Router source pin advances the closed P2P/NAT 13-artifact manifest to `61bf5182935fb9da7a2de0a92d1d2f3f534aeb9847fc410c7e44b2fc12846b31` and the still-unselected Runtime-Python manifest/review to `d0cd4bae9f4172ceab9fa861ae94711ec2d74de57bfd099980dac519ce603783` / `53fcaf96dd294340bda34cfa50f3445bb1b2d4c005d8915342b0332ea87193ac`. Their validators pass with P2P sockets closed and Python execution/protocol activation false.
- Evidence boundary: current proof is no-device SwiftPM with temporary JSONL/SQLite plus a local helper process. It is not physical Android, optical QR, peer receipt, live-provider behavior, external networking, production relay/P2P, NAT traversal, measurement, or deployment proof.
- Approval boundary: no message, JSON field, capability, permission, provider, source access, Python product feature, process/file/socket/network authority, controlled-spike Phase B, production networking, or deployment authority is added. The Python helper is test-only local process evidence.

## v0.5 Memory-Summary Source-Bound Review Identity And Commit Linearization

- Date: 2026-07-16.
- Status: implemented and verified with focused Swift policy, SQLite reopen, approval, dismissal, lock-span, error-propagation, race, and fail-closed legacy-transition regressions; all 1,484 current-source Swift tests; final GPT-5.6 Sol re-review; and the refreshed default no-device aggregate passing.
- Draft-identity boundary: newly computed long-inactivity drafts use opaque `long-inactivity:v2:<64 lowercase hex>` identifiers. The SHA-256 input is domain-separated and length-framed over session id, title, model, exact last activity, session message count, selected source count/range, every ordered source pointer, and deterministic summary preview. Naturally advancing inactivity duration is intentionally excluded.
- Decision boundary: approve and dismiss still perform the initial owner-scoped lookup and reviewed-field checks, then revalidate the exact recomputed base draft while holding the chat store's source-current transaction across the actual memory-store mutation. JSONL holds its cross-instance source lock and SQLite holds `BEGIN IMMEDIATE`, so rename, transcript, model, lifecycle, or source-pointer changes cannot commit between review validation and approval/dismiss persistence. A separate SQLite store receives a locked/busy failure during that mutation and succeeds after release.
- Transition boundary: prior v1 approved, dismissed, and generated records remain readable historical state but none can suppress, overlay, or authorize a current v2 draft. The old session/time/count id lacks title/model/source-pointer/preview provenance, so every affected source is exposed as a deterministic v2 draft for explicit regeneration and review. Generate, approve, and dismiss requests carrying v1 ids fail before provider model-catalog access, backend dispatch, or memory mutation.
- Durable gate boundary: the default no-device selector runs the complete policy/store selection plus pre-mutation rename, approval/dismiss commit races, approval/dismiss SQLite lock-span checks, mutation-error propagation, and the full v1 generate/approve/dismiss transition matrix, then emits `Covered v0.5 addendum: memory-summary source-bound review identity and commit linearization`. Copy hygiene pins the hash contract, inactivity exception, fail-closed transition, source-current mutation helper, exact tests, five documentation surfaces, selector, and marker.
- Smoke-race remediation: the first aggregate demonstrated that the authenticated smoke could list a draft before the separately scheduled automatic title commit. Because title is deliberately part of the v2 source identity, the later commit correctly invalidated that id. The corrected fixture acknowledges an explicit stable rename before listing; a dedicated router regression proves later title drift returns unavailable before model lookup and exposes the replacement draft.
- Final evidence: GPT-5.6 Sol reports `no P0-P3 findings`. `build/qa/swift-full-memory-summary-source-bound-review-identity-final-reviewed-r2-20260716.log` records 1,484 tests with zero failures in 282.207 seconds, and `build/qa/check-no-device-quality-memory-summary-source-bound-review-identity-final-reviewed-r2-20260716.log` exits 0 across 11,605 lines with one overall marker, one dedicated marker, two zero-delay registry self-tests, 56 relay matches, and 905 encrypted frame bodies.
- Device state: Android SDK `adb devices -l` returned no attached device after the final aggregate, so no physical-device result is claimed.
- Evidence boundary: current proof is no-device SwiftPM with temporary JSONL/SQLite and deterministic checkpoints. It is not physical Android, optical QR, peer receipt, live-provider behavior, external networking, production relay/P2P, NAT traversal, measurement, or deployment proof.
- Approval boundary: no protocol message, JSON field, capability, permission, provider, source access, Python/process/file/socket/network, controlled-spike Phase B, production networking, or deployment authority is added. The draft id remains an opaque existing string field.

## v0.5 Android Memory-Summary Request Deadline Closure

- Date: 2026-07-16.
- Status: implemented and verified with six focused deadline regressions, all 34 memory-summary ViewModel checks plus the production-factory test, all 575 `RuntimeClientViewModelTest` checks, and all 1,049 Android app unit tests passing under Android Studio JBR after the host-alignment and exact-Job-cancellation review fixes.
- Deadline boundary: production-created ViewModels give control requests (`memory.summary.drafts.list`, approve, and dismiss) a 15-second deadline and generation requests a 75-second deadline. The macOS host retains its 60-second whole-generation deadline, leaving a 15-second client margin for host timeout/error delivery instead of discarding a normal host result. Each request owns one Job keyed by request id. A timeout can close only the still-pending correlation with the same channel object, connection generation, and authenticated runtime-authority generation, then removes only that request's pending/UI state and permits an explicit retry.
- Reconciliation boundary: action deadlines share the existing pending-action barrier. Earlier concurrent timeouts leave reconciliation deferred; the last timed-out action drains one deferred list refresh exactly once. The replacement list receives its own independent deadline.
- Late-terminal boundary: result, protocol-error, and send-failure paths cancel the exact deadline Job before completing their existing terminal behavior. Late result/error frames after timeout are inert: they cannot mutate drafts or memory, replace the timeout error, trigger another refresh, or revoke authentication.
- Lifecycle boundary: same-channel reauthentication, authentication revocation, disconnect, receive failure, and ViewModel clear cancel every outstanding memory-summary deadline Job and clear its correlation. A cancelled old-authority Job cannot close a replacement request created under the new authority generation.
- Host-alignment boundary: `memory.summary.draft.generate` remains pending after the 15-second control boundary and accepts a valid result at 59,999 milliseconds, cancelling its exact Job. The Android 75-second deadline is only a local fallback after the host's 60-second contract. Late result/error frames after timeout are inert and cannot revive either class of request.
- Durable gate boundary: the default no-device Android selector includes the production-factory execution test, delayed-generation acceptance, `memorySummaryProtocolErrorMalformedResultAndSendFailureCancelExactTimeoutJobs`, timeout/retry, deferred-refresh, and lifecycle/authority regressions, then emits `Covered v0.5 addendum: Android memory-summary request deadline closure`. Copy hygiene pins production enablement, the 15-second/75-second split, exact Job-object cancellation assertions, tests, docs, selectors, and marker.
- Review remediation: GPT-5.6 Sol found no product-code defect and no P0-P2 finding, but identified a P3 evidence gap because map removal alone did not prove `Job.cancel()`. The delayed-result test now preserves the exact Job and observes cancellation, while a new timeout-enabled regression directly covers protocol error, malformed result, and send failure cancellation.
- Current evidence: all six focused regressions, the 35-test memory-summary/factory selection, the 575-test ViewModel class, and the 1,049-test app suite pass with zero failures, errors, or skips, including Robolectric execution of the production dependency factory. Final GPT-5.6 Sol re-review reports `no P0-P3 findings`.
- Final aggregate evidence: `build/qa/check-no-device-quality-android-memory-summary-request-deadline-final-reviewed-r2-20260716.log` exits 0 across 11,556 lines with one `No-device quality checks passed.` marker, one deadline-closure addendum, 88 local development-relay matches, 903 encrypted frame bodies, and two zero-delay mock registry self-tests.
- Device state: Android SDK `adb devices -l` returns no attached device, so no physical-device result is claimed.
- Evidence boundary: current proof is Android JVM virtual-time/state-machine evidence only. It is not physical Android, optical QR, peer receipt, live-provider, external-network, production relay/P2P, NAT traversal, measurement, or deployment proof.
- Approval boundary: no wire/schema/capability, source, permission, provider, Python/process/file/socket/network, Phase B, production networking, or deployment authority changes. All four controlled-spike approvals remain bounded Phase A; runtime Python and semantic memory remain `proposed_not_selected`.

## v0.5 Android Memory-Summary Terminal Channel And Source-Identity Closure

- Date: 2026-07-16.
- Status: implemented and verified with the two focused Android JVM regressions, all 570 `RuntimeClientViewModelTest` checks, independent GPT-5.6 Sol review, static validators, and the refreshed default no-device aggregate passing.
- Terminal authority boundary: every list, generate, approve, and dismiss terminal remains bound to the exact client request id, channel object identity, connection generation, and authenticated runtime-authority generation. Wrong-channel and late-duplicate result/error frames are inert: they cannot consume pending state, mutate review or memory state, trigger another refresh, publish an error, or revoke authentication. The current canonical terminal consumes each pending action once.
- Source identity boundary: the new mutation matrix changes draft id; session id, title, model, last activity, and message count; source count and range; pointer count, order, session, index, role, timestamp, and excerpt. Every mutation fails closed for generated drafts and approved entry provenance. `summary_method` is also exact for approved provenance; generated output method/model/time are checked by their separate generation metadata guard. Only `inactive_seconds` is excluded from source identity because it advances with wall time.
- Durable gate boundary: the default no-device Android selector includes `memorySummarySourceIdentityRejectsEveryAuthoritativeFieldMutationExceptInactivity` and `memorySummaryDecisionFramesRequireExactChannelAndIgnoreLateDuplicates`, then emits `Covered v0.5 addendum: Android memory-summary terminal channel and source-identity closure`. Copy hygiene pins matcher structure, the intentional inactivity exception, both regressions, selector, docs, and marker.
- Review evidence: the same GPT-5.6 Sol reviewer independently rechecked the matcher bodies, both tests, reflection helper, selector, copy guard, and five documentation surfaces and reported `no P0-P3 findings`.
- Final aggregate evidence: `build/qa/check-no-device-quality-android-memory-summary-terminal-source-closure-final-reviewed-20260716.log` exits 0 across 11,557 lines with one `No-device quality checks passed.` marker, one dedicated terminal/source-identity marker, two zero-delay development-registry self-test markers, 88 local development-relay matches, and `Relay ciphertext boundary verified across 903 encrypted frame bodies.`
- Device state: Android SDK `adb devices -l` returned no attached device after the final aggregate, so no physical-device result is claimed.
- Evidence boundary: this slice is Android JVM state-machine proof only. It is not physical Android, optical QR, peer receipt, live-provider, external-network, production relay/P2P, NAT traversal, measurement, or deployment proof.
- Approval boundary: no protocol/schema, permission, source, provider, Python/file/process/terminal/socket/network/MCP/web, Phase B, production networking, or deployment authority changes. All four controlled-spike approvals remain bounded Phase A; runtime Python and semantic memory remain `proposed_not_selected`.

## v0.5 Memory-Summary Transport Completion And Persistence Coalescing

- Date: 2026-07-16.
- Status: implemented and verified with 54 memory-summary router checks, sixteen generated-draft store checks, seven direct production transport checks, one runtime-capability negotiation check, all 1,475 current-source Swift tests, independent GPT-5.6 Sol re-review, and the refreshed full no-device aggregate passing.
- Persistence boundary: each materialized candidate has an identity-bound draft and each publication owns a unique reservation ID. Publication and persistence in flight pin that exact identity across same-draft replacement and capacity cleanup. Cache-derived worker results may reserve only the exact still-present draft identity and cannot reinsert a superseded snapshot. Insertion evicts only unpinned entries and fails closed when all 256 slots are pinned, so the hard bound is not relaxed. The first successful transport completion starts persistence; one concurrent or later successful completion can request one retry only when the store declares the operation idempotent. A consumed retry cannot be rearmed, so one identity issues at most two store calls even when more successful callbacks arrive during the retry. Each new materialization receives a canonical host-private UUID persistence operation id. JSONL deduplicates the same operation under cross-instance exclusion, rejects the same id with different data, and appends a distinct operation even when all generated value fields and the second-rounded timestamp equal a historical event. Current generated-draft selection uses the physical JSONL append ordinal captured before timestamp sorting, so wall-clock rollback cannot make an older operation current after reopen. Legacy rows without the id retain exact-value retry compatibility.
- Review and approval boundary: only successful transport completion marks an in-process candidate review-visible. Listing may overlay that published candidate while durable persistence is pending. Android always sends the exact displayed `summary_preview`; it sends `summary_method` only after `auth.challenge.runtime_capabilities.v1` negotiation returns `memory.summary.approval_method.v1`. The host then requires both to select the recomputed deterministic preview or a current-source published/persisted generated candidate. Byte-identical deterministic and LLM text cannot be attributed to the wrong method. A new client talking to an older runtime omits the unsupported field, while an older client receives the legacy challenge shape. A failed transport candidate remains retry-only: it is neither listed nor approvable. Compatibility requests that omit review bindings may use only durable generated data and otherwise fall back to the deterministic preview.
- Transport boundary: `LocalPeerConnection` and `RelayPeerConnection` now have direct loopback tests for successful Network.framework `contentProcessed` completion, strict encoding failure, and cancellation-backed processing failure. Relay adds an encrypted success/decrypt round trip and a deterministic frame-counter exhaustion failure through the production send path.
- Test-seam boundary: `RelayFrameCipher` exposes its existing frame-index initializer only at Swift package scope. `RelayPeerConnection.activateFrameCipher` keeps production index zero as the default; tests alone inject `Int64.max` to prove encryption failure returns callback `false` before frame transmission.
- Gate boundary: the default no-device selector includes token/replacement binding, capacity pinning, before/after-append ambiguity, same-operation idempotence, distinct same-value generation, operation-id conflict rejection, physical-append selection under clock rollback, failed-publication approval rejection, published-candidate approval while persistence is pending, identical-content method binding, mixed-version capability negotiation, concurrent coalescing, and all seven production transport completion tests, then emits `Covered v0.5 addendum: memory-summary transport completion and persistence coalescing`. Copy hygiene pins the state machine, package-scoped counter seam, exact tests, selector, documentation, and marker.
- Full Swift evidence: `build/qa/swift-full-memory-summary-publication-identity-capability-final-reviewed-20260716.log` records all 1,475 current-source package tests passing with zero failures in 287.305 seconds.
- Final aggregate evidence: `build/qa/check-no-device-quality-memory-summary-publication-identity-capability-final-reviewed-20260716.log` exits 0 across 11,537 lines with one `No-device quality checks passed.` marker, one dedicated memory-summary transport/persistence marker, two zero-delay development-registry self-test markers, 88 local development-relay matches, and `Relay ciphertext boundary verified across 903 encrypted frame bodies.`
- Device state: Android SDK `adb devices -l` returned no attached device after the final aggregate, so no physical-device result is claimed.
- Evidence boundary: current proof is SwiftPM, loopback Network.framework, mock backend, and temporary JSONL/SQLite only. It does not prove peer receipt, physical Android, optical QR, live-provider behavior, external networking, production relay/P2P, NAT traversal, measurement, or deployment.
- Approval boundary: one optional `expected_summary_method` stale-review guard is added to the existing approval payload; it does not add a provider route, permission, source access, socket/network authorization, controlled-spike Phase B, production networking, or deployment authority. The persistence operation id is host-only and absent from wire/Android models. The loopback tests exercise existing no-device development transport only; all four controlled-spike approvals remain bounded Phase A.

## v0.5 Exact Provider Dispatch Identity And Host-Approval Publication Linearization

- Date: 2026-07-16.
- Status: implemented and verified with focused, affected, and full Swift regression sets, independent GPT-5.6 Sol re-review, and the refreshed default no-device aggregate passing.
- Dispatch boundary: the runtime resolves an installed model once to an exact provider and exact `provider_model_id`. Direct backends receive that raw provider id, while the aggregate backend receives its exact provider-qualified form. The original requested model remains the protocol-visible and event-store identity; display `id`, `name`, and `:latest` aliases cannot silently replace the pinned provider dispatch target after resolution.
- Ambiguity boundary: a provider-native id that already begins with reserved `ollama:` or `lm_studio:` qualification is invalid. Aggregate qualified routing matches only the selected provider's exact `provider_model_id`, for chat and embedding paths, so nested qualification and provider alias collisions fail closed as `model_not_installed`.
- Coverage boundary: primary chat, generated compaction prepass, memory-summary generation, and chat-title generation all use the same exact dispatch helper. Provider disappearance or same-provider alias reuse after resolution cannot redirect work to another artifact; title generation uses its deterministic fallback when exact dispatch authority is gone.
- Cache and cancellation boundary: generated memory-summary JSONL stores host-local `provider_qualified_model_id` and cache/single-flight identity binds it beside the requested model and prompt revision. Legacy rows without this field remain readable but are not reusable for new provider-bound generation. Same requested aliases across providers neither reuse nor coalesce. The shared worker returns only a candidate. When the last waiter cancels, the flight retires even if its worker already completed, while only an unfinished worker is cancelled. A later waiter starts a fresh identity-guarded flight, delayed cleanup rechecks both exact flight identity and current retired/empty state, and the first still-authorized waiter performs the one cache materialization and its response publication under the same request/flight authority transaction.
- Approval boundary: the reservation callback is a one-use capability sealed by `invalidateAndWait` when authorization returns. A wrong, repeated, or concurrent receipt fails immediately; ambiguous durability clears the pending queue, blocks approve/dismiss, and requires recovery rather than waiting indefinitely on the persistence adapter. Persistence reports whether expiry was durably terminalized instead of relying on an ambiguous thrown error. After provider execution, the adapter may only `prepareOutcomePublication`; the coordinator supplies that closure a one-use terminal-commit capability. The required sink transport-context transaction serializes current binding validation, exact lifecycle/authentication/trust/permission checks, terminal commit, and response send against binding mutation. The commit gate rechecks both deadlines and persists the exact terminal. Preparation failure, deadline drift, stale authority or transport, duplicate capability use, or unproven terminalization suppresses output and enters fail-closed recovery when durability is ambiguous.
- Focused evidence: 84 focused Swift checks pass with zero failures across aggregate routing, router dispatch/cache/title behavior, generated-draft persistence, approval coordinator, model-pull broker, and permission registry. The durable no-device selector now includes the new exact-routing, legacy-cache, unfinished/completed flight-retirement, delayed-cleanup, cache/publication transaction, concurrent-receipt, transport/authority-drift, sink-transaction linearization, expiry-proof, and approval-publication regressions and emits one dedicated marker.
- Broader evidence: all 550 affected Swift checks pass across the exact-routing/approval classes plus local and encrypted-relay transport sinks. The complete Swift package passes all 1,441 tests with zero failures in 279.331 seconds; the captured logs are `build/qa/swift-affected-provider-dispatch-approval-linearization-20260716.log` and `build/qa/swift-full-provider-dispatch-approval-linearization-20260716.log`.
- Integrity evidence: the closed P2P/NAT 13-artifact manifest is refreshed to `61bf5182935fb9da7a2de0a92d1d2f3f534aeb9847fc410c7e44b2fc12846b31`. Its design, pre-network, four-recommendation controlled-spike Phase A, session-crypto, static-harness, offline-source, compile-only, contract-vector validators, and 99 mutation tests pass with sockets/network/Phase B closed. The production-relay design manifest is refreshed to `7210f0f2f71ce029c8ca32481a39d6fd98307f7322b5d961101d5b238df455a8` while production implementation remains unselected. The still-unselected runtime-Python manifest/review are refreshed to `d0cd4bae9f4172ceab9fa861ae94711ec2d74de57bfd099980dac519ce603783` / `53fcaf96dd294340bda34cfa50f3445bb1b2d4c005d8915342b0332ea87193ac`; its validator passes with execution and protocol activation false.
- Review evidence: three GPT-5.6 Sol review tracks covered source races, approval/transport authority, tests, selectors, copy guards, docs, and proof boundaries. After remediating their provider-alias, completed-flight, cache/publication, concurrent-receipt, expiry, final-authority, transport-transaction, and test-determinism findings, the final re-reviews report no remaining P0-P3 finding. No other subagent model was used.
- Final aggregate evidence: `build/qa/check-no-device-quality-v05-provider-dispatch-approval-linearization-final-reviewed-20260716.log` exits 0 across 11,416 lines with one `No-device quality checks passed.` marker, one dedicated exact-provider-dispatch/approval-publication marker, two `Dev mock zero-delay registry self-test passed.` markers, 88 local development-relay matches, and `Relay ciphertext boundary verified across 899 encrypted frame bodies.`
- Device state: Android SDK `adb devices -l` returned no attached device after the final aggregate, so no physical-device result is claimed.
- Evidence boundary: current proof is no-device SwiftPM with mocks and temporary stores. It is not physical Android, optical QR, live-provider artifact identity, external network, production relay/P2P, NAT traversal, measurement, or deployment proof.
- Controlled-spike boundary: all four approved recommendations remain bounded Phase A. Source acquisition, inspected-source execution, socket/network I/O, Phase B, production networking, and deployment remain closed; runtime Python and semantic-memory recommendations remain `proposed_not_selected`.

## v0.5 Runtime-Authoritative Chat Title Single-Flight And Terminal Correlation

- Date: 2026-07-16.
- Status: implemented and verified with 31 focused Swift title-router tests, all 1,401 Swift package tests, 23 focused Android title/authentication tests, all 563 Android ViewModel tests, the default no-device aggregate, and two independent GPT-5.6 Sol reviews passing with no remaining P0-P3 findings.
- Authority boundary: automatic and explicit generation require a runtime-owned active placeholder session whose stored terminal state is exactly `done/stop`, then use its runtime model and first completed runtime-owned user/assistant turn. Client `model`, `messages`, and optional locale remain strict request-shape inputs only. The backend payload always carries JSON `null` for locale under canonical policy `conversation_language_v1`.
- Prompt boundary: the six-line 470-byte instruction is the immutable `prompt_only` definition `chat_title_v1`, revision `e555574060e79a450ae15bc636758be1d750a3ba5a00ff6fa08f98b4984fbd0a`. The router resolves that exact definition before backend dispatch and contains no second prompt literal.
- Single-flight boundary: automatic title work is registered before the primary `chat.done` is sent. Owner scope, session, captured title revision, runtime model, prompt binding, sorted-transcript source fingerprint, and locale policy form the single-flight key. The shared task produces only a candidate; each automatic or explicit waiter retains its own authentication and connection authority. The coordinator serializes one exact committed outcome and retains at most 128 key/outcome pairs. Replay rechecks owner, active status, exact title/revision, runtime model, prompt binding, source fingerprint, stored `done/stop`, first-turn shape, and locale policy.
- Commit and publication boundary: commit revalidates authentication, active placeholder state, exact title revision, runtime model, prompt binding, stored `done/stop`, and source fingerprint. Explicit publication additionally requires the exact committed title and revision, so a same-text rename with a later revision is stale. Authentication, transcript, manual-title, archive, deletion, or prompt drift cannot publish stale authority.
- Terminal boundary: the host applies a 10-second whole-generation deadline, including installed-model discovery, through a cancellable scheduled deadline rather than an unjoined async timeout task, and enforces a 4,096-byte raw delta cap. At most one cancellation-ignoring title worker may remain abandoned per router. A one-shot race returns without waiting for it, dispatches the exact private backend generation id through a one-at-a-time asynchronous cancellation worker, checks cancellation before dispatch, and retries cancellation if registration completed after the first cancel. One permit keeps the worker gate closed until both producer completion and asynchronous cancellation completion, so a blocked cancel cannot delay fallback or allow a later exact-ID cancel to be dropped. Only content before the first backend `done` is parsed; EOF without `done`, timeout, oversized output, malformed JSON, and empty output use the same bounded deterministic runtime-transcript fallback, while post-terminal events are ignored. Backend and fallback placeholder titles are rejected without a title event or revision increment.
- Android boundary: every title request captures exact request id, channel identity, connection generation, and authenticated authority generation. Title requests close once under a 15-second timeout. Chat/research reconciliation uses one generation, 15-second leg deadlines, a 30-second overall deadline, and one bounded retry latch consumed only by a later title terminal. Title-tagged legacy responses that omit authoritative `snapshot_count` fail closed for either leg. Success, malformed data, protocol error, send failure, timeout, supersession, authentication change, disconnect, and ViewModel clearing all close generation state and related jobs. Same-channel reauthentication discards held snapshots, cancels prior jobs, replaces both child runs, and leaves old frames inert. The queue retains up to 8 later eligible candidates in FIFO order with oldest eviction, and a 128-entry tombstone set keeps retained or evicted namespaced frames inert.
- Focused evidence: 31 Swift title-router tests and 23 Android ViewModel tests pass with zero failures. The full `RuntimeClientViewModelTest` class also passes all 563 tests. Coverage includes immutable prompt failure, completed stored-turn authority, source/model replay drift, deterministic lease-gated stale-waiter-first reauthentication, exact committed revision, bounded model lookup and abandoned-worker concurrency, a deterministic stream-ready-first scheduled deadline gate for blocking-cancel independence, post-registration cancel retry, placeholder rejection, mandatory `done`, timeout/oversize fallback, both reconciliation orders, legacy snapshot rejection on both legs, all leg terminal classes, active same-channel reauthentication replacement, current auth loss/recovery, 9-candidate FIFO eviction/drain, timeout-job cleanup, 129 terminal correlations, send failure, and local-session races.
- Full-suite evidence: all 1,401 Swift package tests pass with zero failures in 281.637 seconds; all 563 Android `RuntimeClientViewModelTest` tests pass with zero failures after 78 Gradle tasks were forcibly re-executed.
- Integrity boundary: the source-only refresh pins the closed P2P/NAT 13-artifact manifest to `83291baff0ed2d35c7e8c83a89ed06848522e4821303aadc7ed25224e6cdeb3c` and the still-unselected runtime-Python manifest/review to `58c8409ad6dc0a263a5fcef45755c5f15d42af02e7528e0d3c2c29c2547889cb` / `077021b80738a70554cf19a2d44e980a6029796f17d26ea938cd1f81cfe9c134`. Both validators and all 15 runtime-Python review mutation tests pass without opening execution, socket, protocol, or network authority.
- Review evidence: two independent GPT-5.6 Sol reviews report no remaining P0-P3 findings across the macOS deadline/permit/cancellation contract and Android legacy-reconciliation/reauthentication authority contract.
- Final aggregate evidence: `build/qa/check-no-device-quality-v05-chat-title-authority-final-reviewed-20260716.log` exits 0 across 11,258 lines with one `No-device quality checks passed.` marker, one dedicated runtime-authoritative chat-title marker, two RuntimeDevServer zero-delay registry self-test passes, 88 local development-relay matches, and `Relay ciphertext boundary verified across 899 encrypted frame bodies.` The authenticated smoke requires the distinct runtime-produced `Runtime-owned smoke title` plus a private `chat-title-generation-` audit entry bound to the pinned title prompt.
- Device state: Android SDK `adb devices -l` returned no attached device after the final aggregate, so no physical-device result is claimed.
- Wire and storage boundary: no protocol field, Android DTO, title-event schema, prompt-provenance migration, prompt-body persistence, permission action, provider route, or network capability is added.
- Evidence boundary: current evidence is no-device SwiftPM/mock-store and Android JVM state-machine work. It is not physical Android, optical QR, live-provider quality, external networking, production relay/P2P, NAT traversal, measurement, or deployment proof.
- Approval boundary: all four controlled-spike approvals remain bounded Phase A only. Source acquisition, inspected-source execution, socket/network I/O, Phase B, production networking, and deployment remain closed.

## v0.5 Memory-Summary Generation Bounded Lifecycle

- Date: 2026-07-16.
- Status: implemented and verified with focused Swift, Android, protocol-schema, RuntimeDevServer smoke, complete Swift-package, independent GPT-5.6 Sol re-review, and the refreshed default no-device aggregate passing.
- Deadline boundary: each `memory.summary.draft.generate` request has a 60-second whole-request deadline that begins before installed-model discovery and ends when the source-current response is handed to the transport for enqueue/publication intent. This boundary does not claim peer receipt or end-to-end delivery. A one-shot authority resolves operation completion, deadline expiry, and request cancellation once. Timeout returns `memory_summary_draft_generation_failed` without awaiting a noncooperative provider; timeout or disconnect before transport enqueue sends no result and schedules no durable cache write.
- Output boundary: answer and explicit reasoning deltas share a 16,384-byte raw UTF-8 ceiling before strict JSON parsing. Overflow fails closed, writes no generated-review cache or approved memory, and requests exact backend cancellation.
- Cancellation boundary: backend work uses a host-private `memory-summary-generation-<UUID>` id unrelated to the client request id. Timeout, last-waiter cancellation, and raw-output overflow dispatch that exact id at most once through a concurrent asynchronous cancellation lane. An exact generation-key permit remains held until worker and cancellation completion, so a blocking provider cancel cannot delay request failure, admit a duplicate same-key worker, or starve cancellation for an unrelated model key.
- Publication and persistence boundary: deadline authority is waiter-local. Expiring or disconnecting one waiter leaves a shared worker running for another waiter, while the last waiter retires and cancels unfinished work. JSONL holds its instance and cross-instance file locks, and SQLite holds `BEGIN IMMEDIATE`, from exact source recomputation through transport enqueue/publication intent. The authorized waiter materializes one candidate in a bounded 256-entry in-process cache and calls `RuntimeMessageSink.send` inside that source-current transaction. Production local and relay transports report Network.framework `contentProcessed` completion; only a successful completion gates the concurrent conditional durable JSONL cache write. Durable persistence is outside both the source transaction and 60-second deadline, cannot delay the response path or connection close, and may remain pending while review/approval uses the in-process candidate. A failed transport completion leaves that bounded materialized candidate available for retry, and a later successful retry can persist it without a second backend call. None of this proves peer receipt or end-to-end delivery.
- Android decision boundary: generated-source payloads accept canonical `llm_summary_v1`. Generated and approved source identity excludes only changing `inactive_seconds`; draft id, summary method where present, session id/title/model/last-activity/message count, source message count/range, and every source-pointer field remain exact. After exact request-id, channel, connection-generation, and authenticated-authority correlation, a malformed, unknown-metadata, or noncanonical approve/dismiss result is terminal: it consumes the correlation, clears the action UI, drains one deferred authoritative refresh, and causes a later canonical result carrying the old request id to be ignored.
- Focused evidence: all 43 selected Swift memory-summary checks, all 567 Android `RuntimeClientViewModelTest` checks, and all 125 Android `ProtocolCodecTest` checks pass with zero failures. The Swift regressions include `testMemorySummaryDraftGeneratePersistsOnlyAfterTransportSuccessAndRetriesMaterializedCandidate` and `testMemorySummaryDraftGenerateJSONLSourceLockCoversTransportEnqueue`; Android coverage includes the exact generated-source and terminal decision-correlation regressions named by the default gate.
- Broader evidence: `swift test --package-path apps/macos/CompanionCore` passes all 1,450 tests with zero failures in 285.575 seconds. `RuntimeDevServer` builds after the transport-completion forwarding fix, and `build/qa/runtime-authenticated-mock-smoke-memory-summary-private-id-20260716.log` passes the focused authenticated memory-summary lifecycle with a host-private generation id.
- Review evidence: independent GPT-5.6 Sol macOS and Android reviews report no remaining P0-P3 finding for that checkpoint. Its then-residual direct-test gaps were real Network.framework failure injection, concurrent same-token successful retry, wrong-channel Android decision framing, late duplicate terminal error, and exhaustive source-field mutation. The later transport-completion/persistence section closes the first two, and the current Android terminal/source-identity section closes the last three under no-device proof; no physical or live-network result is implied.
- Final aggregate evidence: the first aggregate correctly caught a stale RuntimeDevServer smoke expectation for the retired client-derived generation id. After changing the smoke to require `memory-summary-generation-`, `build/qa/check-no-device-quality-memory-summary-transport-remediation-rerun-20260716.log` exits 0 across 11,466 lines with one `No-device quality checks passed.` marker, one bounded-lifecycle marker, 88 local development-relay matches, and `Relay ciphertext boundary verified across 899 encrypted frame bodies.`
- Device state: Android SDK `adb devices -l` returned no attached device after the final aggregate, so no physical-device result is claimed.
- Gate boundary: the default no-device script selects the bounded-lifecycle Swift regressions plus the generated-source protocol and exact Android decision-binding regressions, then emits `Covered v0.5 addendum: memory-summary generation bounded lifecycle`; copy hygiene pins source/store guards, test names, marker, documentation, and unchanged client-request-id privacy.
- Integrity boundary: source-only refresh advances the closed P2P/NAT 13-artifact manifest to `61bf5182935fb9da7a2de0a92d1d2f3f534aeb9847fc410c7e44b2fc12846b31`, production relay to `7210f0f2f71ce029c8ca32481a39d6fd98307f7322b5d961101d5b238df455a8`, and the unselected Runtime Python manifest/review to `d0cd4bae9f4172ceab9fa861ae94711ec2d74de57bfd099980dac519ce603783` / `53fcaf96dd294340bda34cfa50f3445bb1b2d4c005d8915342b0332ea87193ac`. Their validators pass without opening socket, network, execution, protocol, Phase B, or production authority.
- Evidence boundary: current proof is no-device SwiftPM with a mock backend and temporary stores. It is not a live-provider guarantee, physical Android, optical QR, external network, production P2P/relay, NAT traversal, measurement, or deployment proof.
- Approval boundary: no wire/schema, model route, permission, source access, Python/file/process/terminal/socket/network/MCP/web authority, Phase B, production networking, or deployment authorization changes. All four controlled-spike approvals remain bounded Phase A only.

## v0.5 Memory-Summary Generation Stream Terminal Integrity

- Date: 2026-07-16.
- Status: implemented and verified by the two focused regressions, the 26-test memory-summary router selector, all 1,386 Swift tests, the default no-device aggregate, and a GPT-5.6 Sol review with no P0-P3 findings.
- Terminal boundary: generated memory-summary content is eligible for strict JSON parsing and host-local cache persistence only after an explicit backend `done` event. The router stops at the first `done`, flushes the bounded answer splitter once, and does not consume post-terminal events as summary output.
- Failure boundary: graceful stream exhaustion without `done`, thrown backend failure, malformed JSON, and invalid content all return `memory_summary_draft_generation_failed`. They write neither a generated review cache nor approved memory and leave the deterministic visible-source preview unchanged.
- Focused evidence: `testMemorySummaryDraftGenerateRejectsValidJSONWhenStreamEndsWithoutDone` and `testMemorySummaryDraftGenerateStopsAtDoneBeforePostTerminalEvents` pass with zero failures. The first uses otherwise valid JSON without a terminal event; the second adds trailing garbage after `done` and proves only the pre-terminal summary is cached.
- Full evidence: the complete memory-summary router selector passes 26 tests, and `swift test` passes all 1,386 package tests with zero failures in 282.468 seconds.
- Review evidence: GPT-5.6 Sol reports no P0-P3 finding in the implementation, regressions, gate, copy guard, or documentation. Residual live-provider termination, permanent nontermination, cancellation, and pre-`done` thrown-error behavior remain outside this focused mock-stream proof.
- Gate boundary: both regressions are part of the default no-device memory-summary selector, which emits `Covered v0.5 addendum: memory-summary generation terminal-event integrity`; copy hygiene pins the runtime guard, tests, documentation, and marker.
- Final aggregate evidence: `build/qa/check-no-device-quality-v05-memory-summary-terminal-integrity-final-reviewed-20260716.log` exits 0 across 11,208 lines with one overall success marker, one dedicated terminal-integrity marker, 88 local development-relay matches, and 919 encrypted frame bodies.
- Integrity boundary: source-only refresh advances the closed P2P/NAT 13-artifact manifest to `df49cac455f96a405af701496663779dd431fa0364560fc3e07dc0244320677a` and the still-unselected runtime-Python manifest/review to `6bd0275b3fa5966cee6e6c4ca84a5e91a37f236839ffd3803a111d800d0c3a33` / `687c7fac437ca420b9b67a0febbe59f87fa80af4b39752a3d79f661bd2ec2e31`. Both validators and all 15 Python review mutation tests pass without opening execution or network authority.
- Evidence boundary: current proof is in-process SwiftPM with a mock backend and temporary stores. It is not live-provider stream behavior, physical Android, optical QR, external-network, production relay/P2P, NAT traversal, measurement, or deployment proof.
- Approval boundary: no protocol field, model/provider route, permission, source access, Python/file/process/terminal/socket/network/MCP/web authority, Phase B, production networking, or deployment authorization changes. Controlled-spike approvals remain bounded Phase A only.

## v0.5 Chat Compaction Prompt-Skill Revision Binding

- Date: 2026-07-16.
- Status: implemented and verified with focused no-device checks, all 1,384 Swift tests, and the default no-device aggregate passing.
- Prompt boundary: the byte-identical existing backend-only compaction instruction is now the immutable `prompt_only` definition `chat_compaction_summary_v1`, revision `ba5659dacf9df69a1e600ce013e9aab503690883312642dad9f774d61d044ed8`. The router resolves that exact current definition before any summary-cache lookup or LLM prepass and sends only the registry-owned prompt body.
- Cache boundary: exact and strict-prefix SQLite reuse now bind the prompt-skill identifier and revision in addition to owner, session, source, lineage, provider-qualified model, and summary policy. The prior derived schema is dropped and rebuilt when prompt-binding columns are absent. A historical revision cannot satisfy current exact or prefix lookup, and the prompt body is never persisted.
- Fallback boundary: a missing or drifted current definition skips both cache access and the LLM prepass, then continues ordinary chat with the already-bounded deterministic compaction preview. Cache candidates from another binding are not used for incremental evolution, and generated rows revalidate the current binding before and during commit.
- Cancellation boundary: the derived prepass now participates in the same runtime-owned atomic registration state as the primary generation. Cancellation before registration prevents both derived and primary dispatch; cancellation during registration records the terminal intent and forces the newly returned derived stream to be cancelled before any primary dispatch; cancellation after registration targets the derived generation directly.
- Focused evidence: 11 registry tests, 13 SQLite cache tests, and five router regressions pass, totaling 29 checks. They cover exact 221-byte prompt/digest pinning, exact/prefix revision isolation, pre-prompt schema rebuild, malformed/wrong-skill cache keys, durable reuse, incremental evolution, current-binding commit, deterministic no-cache/no-prepass fallback, and cancellation before derived registration. The broader 11-test chat-cancellation selector also passes.
- Full evidence: all 1,384 Swift tests pass with zero failures in 284.103 seconds, including the five-language macOS render suites and the new registration-race regression.
- Final aggregate evidence: `build/qa/check-no-device-quality-v05-memory-summary-authority-deferred-reconciliation-final-reviewed-20260716.log` exits 0 across 11,218 lines with one overall success marker, one chat-compaction prompt-skill marker, 88 local development-relay matches, and 919 encrypted frame bodies.
- Wire and data boundary: this adds no protocol field, client-selected skill, event-log field, transcript metadata, Android storage field, permission action, source access, or network behavior. The prompt body remains registry-owned and backend-only.
- Evidence boundary: current proof is no-device SwiftPM and temporary SQLite only. It is not physical Android, optical QR, live-provider quality, external-network, production relay/P2P, NAT traversal, measurement, or deployment proof.
- Approval boundary: no Python/file/process/terminal/socket/network/MCP/web authority, source acquisition, Phase B, production networking, or deployment is opened. Controlled-spike approvals remain bounded Phase A, while the runtime-Python and semantic-memory recommendations remain separately unselected.

## v0.5 Android Memory-Summary Drafts List Authority Correlation

- Date: 2026-07-16.
- Status: implemented and verified with the two deferred-reconciliation remediation regressions, all 1,018 Android app JVM tests after all 78 Gradle tasks were forced to execute, the default no-device aggregate, and a final GPT-5.6 Sol review reporting no remaining P0-P3 finding.
- Correlation boundary: every list, generate, approve, and dismiss request captures the exact request id, channel identity, connection generation, and authenticated runtime-authority generation. Only that live tuple may publish review state or persist an approved entry; unsolicited, duplicate, superseded, disconnected, or reauthenticated responses are ignored.
- Action boundary: generation, approval, and dismissal supersede an in-flight list request. A required or manual authoritative refresh encountered while any action is pending is retained as a deferred refresh, then emitted once after the final action terminates through success, malformed result, protocol error, or send failure. A delayed pre-action list therefore cannot overwrite a generated draft, clear a model-mismatch error, or resurrect a dismissed draft, while authentication revocation, successful reauthentication, connection replacement, and receive failure clear every pending list/action correlation, deferred refresh, and UI state.
- Failure boundary: correlated error payloads reject unknown metadata before pairing/authentication handling. Namespaced client request ids absorb arbitrarily delayed list/action errors even after the bounded 64-entry closed-list history evicts an old tuple, so stale errors cannot fall through to generic UI or authentication mutation.
- Focused evidence: a wrong-model generate result while an unrelated approval remains pending defers rather than drops reconciliation, and the approval completion emits one authoritative list request. A second regression proves the same deferred request drains after strict unknown-metadata error closure and after a synthetic action send failure. Same-channel reauthentication, delayed old actions, receive failure, malformed correlated errors, bounded tombstone eviction, superseded lists, wrong-model output, and dismissal coverage remain green in the full run.
- Review evidence: GPT-5.6 Sol found and then verified remediation of two P2 variants: a refresh dropped behind another pending action and terminal strict-metadata branches that failed to drain the retained refresh. The final read-only re-review reports no remaining P0-P3 finding.
- Full evidence: `:app:testDebugUnitTest --rerun-tasks` executes 1,018 tests with zero skips, failures, or errors.
- Final aggregate evidence: `build/qa/check-no-device-quality-v05-memory-summary-authority-deferred-reconciliation-final-reviewed-20260716.log` exits 0 across 11,218 lines with one overall success marker, one Android memory-summary authority marker, 88 local development-relay matches, and 919 encrypted frame bodies.
- Evidence boundary: this is no-device Android JVM state-machine evidence. It is not physical Android, optical QR, live pairing, live-provider, external-network, production relay/P2P, NAT traversal, or deployment proof.
- Authority boundary: no protocol shape, runtime permission, model/provider route, local persistence, source approval, socket, network, Phase B, or production authorization changes.

## v0.5 Memory-Summary Draft Model And Prompt-Skill Revision Binding

- Date: 2026-07-16.
- Status: implemented and verified. The focused selector, all 1,379 Swift tests, the default no-device aggregate, and two independent GPT-5.6 Sol reviews pass with no remaining P0-P3 findings after remediation.
- Model boundary: generated review-draft reuse and in-flight generation coalescing now require the exact requested model after installed-model resolution, in addition to owner, draft identity, and current visible-source guards. A request for another model performs a new backend generation and replaces the owner-scoped cache only with that model's canonical result. Android rejects a canonical response whose `generated_model_id` differs from the pending request, clears pending state, preserves the deterministic draft, and requests an authoritative refresh.
- Prompt boundary: the existing six-line memory-summary instruction is now the second immutable `prompt_only` definition, `memory_summary_draft_v1`, revision `34e4783c082748b6d5cd8d31e62a1082479c8f4378caa861da03ae97857064ca`. Generation resolves that exact current binding before cache lookup and backend dispatch, uses only the registry prompt, and revalidates the same binding before persistence. A missing current definition returns `runtime_prompt_skill_unavailable` with zero chat dispatch.
- Persistence boundary: generated-review events store canonical `prompt_skill_id` and `prompt_skill_revision` beside the existing model id, never the prompt body. Legacy events map to a separately pinned immutable original-v1 binding only when both keys are genuinely absent. The shared strict JSON document validator rejects duplicate names, including escaped-equivalent names, before decoding; explicit `null`, partial, malformed, or wrong-skill metadata fails closed. A retained historical revision remains readable, but generation never reuses it as the current revision, and approval falls back to the deterministic preview when its exact definition is no longer available.
- Wire and authority boundary: no prompt-skill field is added to Android DTOs, protocol schema, list/generate/approve payloads, or client storage. The binding is host-local cache provenance, not a client-selected skill, permission, action, provider, file, process, Python, terminal, socket, network, MCP, web, or production-transport capability.
- Focused evidence: 53 Swift checks pass across registry, generated-draft persistence, long-inactivity policy, semantic-cache compatibility, and 24 memory-summary router regressions. Coverage includes A to B to A cache replacement, two actually concurrent different-model generations, explicit-null and duplicate/escaped-duplicate provenance rejection, and original-v1 legacy mapping. The Android wrong-model canonical-response regression also passes with Android Studio JBR after forcing all 78 Gradle tasks to execute.
- Full evidence: all 1,379 Swift tests pass with zero failures after the strict JSON provenance remediation. Android SDK `adb devices -l` lists no attached device, so no physical-device claim is made.
- Review result: the storage-focused GPT-5.6 Sol review found one P2 where optional decoding could treat explicit `null` as omitted and Foundation decoding could accept a duplicate prompt key. Strict pre-decode duplicate validation plus exact key-presence/type checks remediate it. The independent router/Android/gate review reported no P0-P3 findings, and the storage remediation re-review confirms the P2 is closed with no new P0-P3 finding.
- Final aggregate evidence: `build/qa/check-no-device-quality-v05-memory-summary-model-prompt-binding-final-reviewed-20260716.log` exits 0 across 11,194 lines with one `No-device quality checks passed.` marker, one dedicated memory-summary model/prompt-binding marker, 88 local development-relay matches, and 919 encrypted frame bodies. Copy/docs hygiene, Android/Swift regressions, authenticated direct/relay smoke, P2P/NAT and runtime-Python validators, and `git diff --check` pass.
- Integrity boundary: the refreshed current P2P/NAT 13-artifact manifest is `df49cac455f96a405af701496663779dd431fa0364560fc3e07dc0244320677a`. The runtime-Python review remains closed `proposed_not_selected`; its refreshed six-artifact manifest and review hashes are `6bd0275b3fa5966cee6e6c4ca84a5e91a37f236839ffd3803a111d800d0c3a33` and `687c7fac437ca420b9b67a0febbe59f87fa80af4b39752a3d79f661bd2ec2e31`. These are source-drift records only and open no execution, socket, or network gate.
- Evidence boundary: current proof is no-device SwiftPM, temporary JSONL/SQLite, and Android JVM unit evidence only. It does not prove physical Android, optical QR, live-provider quality, external networking, production relay/P2P, ICE/STUN/TURN, NAT traversal, deployment, or retained historical behavior when a definition is not bundled.
- Approval boundary: all four controlled-spike approvals remain bounded Phase A only. Source acquisition, inspected-source execution, sockets, network I/O or measurement, Phase B, production networking, and deployment remain closed. `runtime_python_sandbox_v1_recommended` and `memory_semantic_duplicate_acceptance_v1_recommended` remain `proposed_not_selected`.

## v0.5 Durable Research Notebook Prompt-Skill Revision Binding

- Date: 2026-07-15.
- Status: implemented and verified. The 34-test focused no-device selector, all 1,369 Swift tests, and the default no-device aggregate pass.
- Durable identity boundary: every `RuntimeResearchNotebook` now stores the canonical host-local `RuntimePromptSkillBinding` that created it. New notebooks bind the exact current `research_brief_v1` revision, while the immutable registry can retain multiple revisions for the same skill identifier and resolves follow-ups by the notebook's exact identifier-plus-revision pair.
- Migration boundary: the owner-only SQLite notebook store advances from schema v3 to v4 with `prompt_skill_id` and `prompt_skill_revision`. Valid v1, v2, and v3 rows migrate transactionally to the exact byte-identical current research binding; notebooks, ordered grants, and lifecycle intents are revalidated before commit. Corrupt legacy rows roll back to the original schema and version. Prompt bodies remain registry-owned and are not persisted.
- Runtime boundary: follow-ups resolve the stored binding before lifecycle reconciliation, trusted-source context consumption, chat-request persistence, or backend dispatch. A retained historical definition supplies its historical prompt; a missing or retired revision returns `runtime_prompt_skill_unavailable` with zero source-consumption audit, zero chat event, and zero backend call. Commit and rejected-request paths recheck the same binding with owner, lifecycle, session, model, and grants.
- Wire and authority boundary: no `prompt_skill_id` or revision is added to `chat.send`, Android models, client storage, notebook list output, or any other protocol payload. Clients cannot select a skill or revision, and this adds no permission action, approval surface, process, Python, file, terminal, socket, network, MCP, web, provider, or production-transport authority.
- Focused evidence: nine registry tests, five in-memory notebook-store tests, 16 SQLite tests, and four router regressions pass, totaling 34 checks. Coverage includes canonical binding validation, same-ID historical revision lookup, lifecycle preservation, schema-v4 reopen privacy, real v3 migration, corrupt-v3 rollback, current-binding creation, historical-prompt follow-up, missing-revision pre-consumption failure, and commit-time binding drift.
- Final aggregate evidence: `build/qa/check-no-device-quality-v05-research-notebook-prompt-skill-binding-final-reviewed-20260715.log` exits 0 across 11,170 lines with one `No-device quality checks passed.` marker, one dedicated prompt-skill revision-binding marker, 88 local development-relay matches, and 921 encrypted frame bodies.
- Review result: two independent GPT-5.6 Sol reviews report no remaining P0-P3 findings across registry/store migration safety and router/gate integration.
- Integrity boundary: refreshing the router source pin advances the current 13-artifact P2P/NAT evidence-manifest hash to `abfdfc1728b9b2fdbc3fd19394f3fbf049a9d6d41d716e28ae4e4f9c7b978e32`; the relay manifest remains `52fe7b78b402e30191329aa3bc6751671acabd09ffc25a2a0d6704852bfd3676`. This records source drift only and does not open any socket or network gate.
- Evidence boundary: current proof is no-device SwiftPM and temporary SQLite evidence only. It does not prove physical Android, optical QR, live-provider behavior, external networking, production relay/P2P, ICE/STUN/TURN, NAT traversal, deployment, or retained behavior for a future revision unless that historical definition remains bundled.
- Approval boundary: all four controlled-spike approvals remain bounded Phase A only. Source acquisition, inspected-source execution, sockets, network I/O or measurement, Phase B, production networking, and deployment remain closed. `runtime_python_sandbox_v1_recommended` and `memory_semantic_duplicate_acceptance_v1_recommended` remain `proposed_not_selected`.

## v0.5 Host-Local Approval Review Text Anti-Spoofing

- Date: 2026-07-15.
- Status: implemented and verified. The 40-test focused selector, all 1,363 Swift tests, and the default no-device aggregate pass.
- Review-text boundary: `RuntimeApprovalReviewText` is the single `CompanionCore` projection for the requesting-device label shown in host-local approval review. The router projects the current trusted-device name, the model-pull adapter applies the same idempotent projection, and `RuntimeHostApprovalCoordinator` rejects any noncanonical display string before persistence or review publication.
- Unicode boundary: output is re-normalized, re-trimmed, and projected to a bounded fixed point after filtering and 512-UTF-8-byte `Character` bounding, then must pass the same projection unchanged. Controls, line separators, bidi formatting/isolate marks, private-use/unassigned scalars, braille blank, and noncontextual default-ignorable code points are removed. ZWNJ requires either a preceding canonical `Virama` or the Unicode `Joining_Type` before/after context; ZWJ requires either a preceding canonical `Virama` or an `Extended_Pictographic` sequence. Emoji/text variation selectors require an emoji or ideographic base, CJK ideographic variation selectors are preserved, and only the RGI England/Scotland/Wales subdivision tag sequences survive. Approved tag positions are precomputed once with a linear scan rather than rescanned per scalar. An invisible-only result becomes `Trusted device`.
- Review identity boundary: the immutable permission claim derives a six-byte uppercase key fingerprint from the authority public key already bound into the request digest. The coordinator requires the review fingerprint to equal that claim value, and the UI shows it beside the safe device name. The user-controlled name is wrapped in host-owned FSI/PDI isolation so ordinary RTL text cannot reorder surrounding localized approval copy.
- Authority and data boundary: display text and the short comparison fingerprint never select an action, permission, model, resource, or authority. Production remains limited to `models_pull_ollama_v1`; raw device-name bytes and the fingerprint are not added to durable audit, wire results, or protocol state, and provider dispatch remains zero before explicit host approval.
- Focused evidence: seven policy-registry tests, eight coordinator tests, 22 model-pull broker tests, one authenticated router regression, one five-language RTL-isolation localization regression, and one five-language light/dark render regression pass, totaling 40 selected checks. Coverage includes post-filter and post-boundary fixed-point idempotence, 513-byte contextual-neighbor truncation, a 10,000-tag non-RGI linear-time rejection ceiling, internal Latin join-control and non-RGI tag rejection, trailing join/variation rejection, Persian ZWNJ, Devanagari virama ZWNJ/ZWJ, family emoji, CJK ideographic variation, all three RGI England/Scotland/Wales subdivision flags, claim-bound fingerprint display, 505-byte RTL/multilingual rendering, zero pre-approval provider calls, and unchanged requested-only redacted audit.
- Gate boundary: the default no-device selector includes the new router regression and emits `Covered v0.5 addendum: host-local approval review text anti-spoofing`; copy hygiene pins the shared projection, linear tag scanner, removal of duplicate helpers, tests, render ceiling, documents, marker, and final aggregate evidence.
- Final aggregate evidence: `build/qa/check-no-device-quality-v05-approval-review-text-anti-spoofing-final-reviewed-20260715.log` exits 0 across 11,079 lines with one success marker, one dedicated anti-spoof marker, 88 local development-relay matches, and 919 encrypted frame bodies. The refreshed P2P/NAT and relay evidence-manifest hashes are `b08720c763bb6433380853af4702944a40272ae9fd8a944557c37416bf0f842b` and `52fe7b78b402e30191329aa3bc6751671acabd09ffc25a2a0d6704852bfd3676`; both validators pass with socket and production-network gates closed.
- Review result: two final GPT-5.6 Sol passes report no remaining P0-P3 findings after claim-bound identity, bidi isolation, fixed-point truncation, Unicode join/tag context, virama preservation, and linear tag-run remediation.
- Evidence boundary: this is no-device source/unit/render evidence. It does not prove physical Android, optical QR, live-provider behavior, external network behavior, production P2P/relay, or deployment.
- Approval boundary: this slice adds no protocol message, client capability, second action, standing grant, Python/file/process/terminal/network/MCP/web authority, source acquisition, socket I/O, Phase B, or production networking authorization. The runtime Python and semantic-memory recommendations remain separately unselected.

## v0.5 Runtime Python Sandbox Security Design Review (Selection Pending)

- Date: 2026-07-15.
- Status: `runtime_python_sandbox_v1_recommended` is a closed `proposed_not_selected` review-only packet. It selects no implementation, executable, interpreter artifact, action, protocol message, process, XPC service, entitlement, file/network/process capability, or code execution.
- Isolation recommendation: reject an in-process subinterpreter and a plain `Process` using system Python. The proposed boundary is a separately signed minimum-privilege one-shot XPC worker with its own App Sandbox, no network/App Group/shared Keychain/user-file/automation authority, and one pinned signed embedded CPython artifact loaded before source. It accepts one operation, launches no interpreter child, and exits; Python has zero child-process authority. App Sandbox is not claimed as an executable-identity allowlist, so native-compromise `exec` remains explicit residual risk under the same sandbox and resource ceilings. A pinned `-I -S -B` equivalent, syntax restrictions, audit hooks, and resource limits are defense in depth.
- Language and resource recommendation: the first proposed profile is `deterministic_calculation_v1`, with closed bounded IPC/JSON, no imports or dynamic execution surface, rejection of bidi controls/default ignorables/non-ASCII line separators, fixed locale/time-zone/hash seed, no ambient clock/random/environment/files/network/process input, 16 KiB source, 64 KiB input/result/stdout, 8 KiB stderr, a three-second worker deadline plus a separate one-second forced-termination/cleanup deadline, two CPU seconds, 256 MiB address space, zero child processes/files/core dumps, 32 descriptors, and one Python execution slot. These are proposed ceilings, not active behavior.
- Approval and lifecycle recommendation: the future `python_deterministic_calculation_v1` action and proposed `python.run` message require a separate versioned decision. Every run binds exact authority, execution-closure, worker executable/designated-requirement/entitlement, profile, interpreter, source, input, and limit digests to ephemeral macOS-host review and durable redacted audit. The source viewer uses line numbers, visible whitespace, and token-aware Unicode escapes. Approval binds the expected closure before durable reservation; after reservation starts the worker, the XPC audit token and exact code identity are checked before untrusted handoff and again before result acceptance. Cancellation or drift terminates only that worker instance, never an ambient process group. A success audit binds worker identity, result-schema, canonical-result, and publication-envelope digests before publication. Approval TTL, execution deadline, and termination/cleanup deadline are separate; cleanup breach records `cleanup_failed`, blocks the lane, and never publishes. The Python lane must not implicitly reuse or starve the model-pull global execution slot.
- Evidence and validation: after refreshing the changed router source pin, the six-artifact manifest SHA-256 is `6bd0275b3fa5966cee6e6c4ca84a5e91a37f236839ffd3803a111d800d0c3a33` and the immutable review SHA-256 is `687c7fac437ca420b9b67a0febbe59f87fa80af4b39752a3d79f661bd2ec2e31`. `script/check_runtime_python_sandbox_review.py` and its 15-test mutation suite validate duplicate-key/type-confusion rejection, exact semantic arrays and closed authorization, option and floor integrity, bounded no-follow and stable-identity reads, manifest/document hashes, existing SwiftPM `Sources` closure, executable/Python resource and symlink-module closure, reserved `python.*` schema closure, and content-free failures.
- Review result: independent GPT-5.6 Sol passes found executable-identity overclaim, execution/cleanup deadline conflict, Unicode source-display spoofing, missing result/audit binding, semantic-array weakening, worker-identity and cancellation ambiguity, reservation/identity ordering conflict, unscanned executable resources and symlink modules, gate-integrity weakness, and symlink-loop diagnostic leakage. The packet now uses a one-shot embedded-CPython XPC worker with explicit residual `exec` risk, exact execution-closure and post-reservation/pre-handoff worker identity binding, exact-worker cancellation, separate execution and cleanup budgets, spoof-resistant source review, publication-bound result digests, exact semantic arrays, all-artifact source scanning, fixed-prefix gate execution, exact validator/test hashes, and content-free root failure. The final GPT-5.6 Sol re-review reports no remaining P0-P3 findings. No product code or protocol schema is changed.
- Final aggregate verification: `build/qa/check-no-device-quality-v05-runtime-python-sandbox-review-final-reviewed-20260715.log` exits 0 with 11,053 lines in the final capture, exactly one overall success marker, exactly one runtime-Python review marker, 88 loopback development-relay `matched relay_id=` records, and a ciphertext-boundary summary covering 919 encrypted frame bodies. Android SDK `adb devices -l` lists no attached device, so this remains no-device/loopback evidence and not physical Android, optical QR, external-network, or production transport proof.
- Selection effect: approving this recommendation would select design requirements only. Interpreter acquisition/bundling, XPC packaging and entitlements, runner/action/protocol implementation, live escape/resource evidence, and any execution remain separate versioned work and approvals.
- Evidence boundary: this is static/no-device review evidence only. It does not prove App Sandbox containment, code signing, interpreter supply-chain integrity, actual resource enforcement, worker cleanup/cancellation, live Python execution, physical Android, optical QR, external networking, production P2P/relay, or deployment.
- Approval boundary: all four controlled-spike approvals remain bounded Phase A only. Their source acquisition, inspected-source execution, socket/network I/O and measurement, Phase B, production networking, and deployment gates remain closed. `memory_semantic_duplicate_acceptance_v1_recommended` also remains `proposed_not_selected`.

## v0.5 Host-Local Action Approval Lifecycle Core

- Date: 2026-07-15.
- Status: implemented with focused and final aggregate no-device verification passing; GPT-5.6 Sol remediation re-review reports no remaining P0-P3 findings.
- Architecture boundary: the queue, wall/monotonic expiry, exact registered-policy check, one active irreversible reservation, terminal-before-publication ordering, result suppression, restart recovery, and storage-degraded state now live in the internal action-neutral `RuntimeHostApprovalCoordinator`. The existing public `RuntimeModelPullApprovalBroker` is the sole production adapter and remains exclusively responsible for `ModelPullDispatching`, Ollama failure redaction, and model-specific review/audit projection.
- Registration boundary: `RuntimePermissionPolicyRegistry.validates(_:)` accepts only the exact definition already held by that immutable registry and a canonical binding digest. The coordinator separately requires a compile-time `RuntimeHostApprovalActionRegistration`; production registers only `models_pull_ollama_v1` at revision `5969f34082e579a4e393bded6ce62706382e7376258b364c3afed0dbbcb163d3`. Synthetic actions exist only in `@testable` in-memory regressions and do not enter the bundled registry.
- Lifecycle boundary: the existing five-minute default TTL, maximum 32 pending reviews, one globally active execution, durable reservation as the irreversible linearization point, dual-clock expiry, deterministic replay rejection, and fail-closed recovery behavior are preserved. Ephemeral host-rendered display metadata is bounded, NFC-exact, trimmed, and control-free before review publication and is never persisted.
- Persistence boundary: the model adapter type-erases the existing model-pull persistence protocol into the action-neutral core while fixing provider authority to Ollama. The owner-only schema-v2 database, schema-v1 migration, table names, event bytes, request-binding digest prefix, action/revision constraints, and restart terminalization remain unchanged; there is no generic production journal migration in this slice.
- Wire and execution boundary: no protocol message, client capability, approval id, action id, revision, executor registry, standing grant, command, path, URL, environment, source acquisition, process, Python, file, terminal, socket, network, MCP, web-search, backend-control, or second production action is added. Existing model-download UI and wire behavior remain unchanged.
- Focused evidence: eight synthetic `RuntimeHostApprovalCoordinatorTests`, seven permission-registry tests, 19 model-broker tests, 12 unchanged store tests, five AppModel tests, and nine router `models.pull` tests pass, totaling 60 selected Swift tests with zero failures. Coverage proves unregistered-action rejection before audit/execution, exact reservation and terminal ordering, concurrent exactly-once execution, queue/display bounds, duplicate-binding isolation, authority and policy drift, dual-clock expiry, terminal-write suppression and storage degradation, restart quarantine without retry, generic claim validation, Unicode device-display normalization/bounding, and model-adapter parity.
- Review result: GPT-5.6 Sol found one P2 parity regression where valid NFD or long multibyte trusted-device names could fail the new ephemeral display check before approval intake. The model adapter now NFC-normalizes, strips controls, trims, and truncates on `Character` boundaries to 512 UTF-8 bytes before coordinator validation; the production-adapter regression covers NFD plus complex emoji. Focused tests pass and remediation re-review reports no remaining P0-P3 findings.
- Final aggregate evidence: `build/qa/check-no-device-quality-v05-host-approval-lifecycle-core-final-reviewed-20260715.log` exits 0 across 11,071 lines with one `No-device quality checks passed.` marker, one dedicated host-local action-neutral lifecycle addendum, 88 local development-relay matches, and 919 encrypted frame bodies. Protocol/copy/docs hygiene, shell/Python syntax, Android/Swift regressions, authenticated direct/relay smoke, P2P/NAT and relay design validators, and `git diff --check` pass.
- Integrity evidence: the P2P/NAT 13-artifact evidence manifest remains `63ca0efb277b07704e8ae670a21e7f3c91694e8eccf3d9be4465fbf6b257268e`; the relay evidence manifest remains `52fe7b78b402e30191329aa3bc6751671acabd09ffc25a2a0d6704852bfd3676`. Both validators pass while socket/network/Phase B/production gates remain closed.
- Evidence boundary: current proof is no-device SwiftPM and in-memory/temporary-SQLite work only. It does not prove live Ollama download behavior, physical Android, optical QR, external networking, production relay/P2P, ICE/STUN/TURN, NAT traversal, measurement, Phase B, production networking, or deployment.
- Approval boundary: all four controlled-spike approvals remain bounded Phase A only. Source acquisition, inspected-source execution, sockets, network I/O/measurement, Phase B, production networking, and deployment remain closed. `memory_semantic_duplicate_acceptance_v1_recommended` remains `proposed_not_selected`.

## v0.5 Host-Local Runtime Permission Policy Registry Foundation

- Date: 2026-07-15.
- Status: implemented with focused and final aggregate no-device verification passing; GPT-5.6 Sol integration/security final re-reviews report no remaining P0-P3 findings.
- Policy boundary: `RuntimePermissionPolicyRegistry` is an immutable host-local metadata registry. Its only bundled action is `models_pull_ollama_v1`, effect `provider_artifact_install`, decision `host_explicit_approval`, audit requirement `durable_redacted_required`, and exact revision `5969f34082e579a4e393bded6ce62706382e7376258b364c3afed0dbbcb163d3`. Unknown actions, revision drift, duplicate identity, malformed metadata, unsupported enum values, and tampered revisions fail closed.
- Claim boundary: each model-pull intake receives a length-framed, domain-separated SHA-256 claim over the exact policy definition, connection and request identity, authentication generation, trusted device and public key, optional transport binding, resource kind, and authorized model. The legacy digest prefix remains stable for existing audit readability, while no raw authority or resource value is persisted.
- Enforcement boundary: the router creates the claim only after authenticated authority capture, and the broker validates the exact registered action before audit intake, before dispatch reservation, and inside current-authority publication. A missing policy returns the existing `model_pull_approval_required` wire error with zero audit rows and zero provider calls; policy drift terminalizes locally as `permission_changed` without dispatch.
- Persistence boundary: approval schema v2 adds only fixed `action_id` and `policy_revision` metadata. A validated schema-v1 database migrates transactionally to v2 only after every operation/event row has integer schema version 1 and every complete event history passes sequence plus expiry-timeline validation; invalid row versions, expired reservations, or malformed legacy history roll the migration back without policy stamping. Restart recovery terminalizes requested work as `host_restarted` plus irreversibly reserved work as `result_suppressed` without retry. Durable rows still exclude model names, request/device identity, keys, transport bindings, URLs, credentials, provider errors, and execution material.
- Failure boundary: wall-clock and monotonic deadlines both gate approval at intake and again immediately before durable reservation, so authority-check delay and clock rollback cannot extend authority. A known duplicate authenticated request binding is rejected as replay without poisoning unrelated intake. Cancellation, reservation, terminal, suppression, dismissal, expiry, and ambiguous create failures that leave audit state uncertain put the broker into storage-degraded mode; new intake remains blocked until fail-closed recovery succeeds.
- Wire and execution boundary: successful `models.pull` retains only `model`, `status`, `installed`, `backend`, and `provider`; action, policy, operation, and review identifiers remain host-local. The policy registry itself contains no executor, and the later internal action-neutral lifecycle core adds no standing grants, generic executor registry, command/path/URL/environment metadata, source acquisition, process launch, socket, network I/O, Python, file, terminal, MCP, web-search, backend-control, client-selected permission surface, or second bundled action.
- Focused evidence: six policy-registry tests, 12 store tests, 18 broker tests, and nine router `models.pull` tests pass, totaling 45 selected Swift tests with zero failures. The Android `ModelPullPayload` decode regression also passes with Android Studio JBR. Coverage includes independent revision and digest fixtures, every authority/resource binding field, malformed and unregistered definitions, requested and reserved schema-v1 migration recovery, invalid-row-version, expired-reservation, and malformed-history migration rollback, whole-history audit reads, cross-platform printable-ASCII model parity, permission TOCTOU, delayed-authority monotonic TTL, duplicate-binding replay isolation, cancellation and double-terminal audit failures, recovery blocking, missing-policy router failure, and exact wire-key non-disclosure.
- Review result: GPT-5.6 Sol integration/security review identified schema/runtime character-byte drift, Android DTO parity, incomplete reserved migration evidence, weak registry injection pinning, authority-delay TTL crossing, duplicate-binding broker poisoning, incomplete full-history and legacy row-version validation, and missing expiry-timeline validation. All P2/P3 findings were remediated with the regressions above; both final re-reviews report no remaining P0-P3 findings.
- Final aggregate evidence: `build/qa/check-no-device-quality-v05-runtime-permission-policy-registry-final-reviewed-20260715.log` exits 0 across 11,036 lines with one `No-device quality checks passed.` marker, one dedicated runtime-permission addendum, 88 local development-relay matches, and 919 encrypted frame bodies. Protocol/copy/docs hygiene, shell/Python syntax, Android/Swift regressions, authenticated direct/relay smoke, P2P/NAT and relay design validators, and `git diff --check` pass.
- Integrity evidence: the refreshed P2P/NAT 13-artifact collection is `63ca0efb277b07704e8ae670a21e7f3c91694e8eccf3d9be4465fbf6b257268e`; the relay collection is `52fe7b78b402e30191329aa3bc6751671acabd09ffc25a2a0d6704852bfd3676`. Both design validators pass while P2P socket execution and production relay implementation remain closed.
- Evidence boundary: current proof is SwiftPM and temporary SQLite no-device work only. It does not prove physical Android, live Ollama download or failure recovery, optical QR, external networking, production relay/P2P, ICE/STUN/TURN, NAT traversal, measurement, Phase B, production networking, or deployment.
- Approval boundary: all four controlled-spike approvals remain bounded Phase A only. Source acquisition, inspected-source execution, sockets, network I/O/measurement, Phase B, production networking, and deployment remain closed. `memory_semantic_duplicate_acceptance_v1_recommended` remains `proposed_not_selected`.

## v0.5 Host-Local Prompt-Only Skill Registry Foundation

- Date: 2026-07-15.
- Status: implemented with focused and final aggregate no-device verification passing.
- Registry boundary: `RuntimePromptSkillRegistry` accepts at most 32 immutable bundled manifests with NFC-exact lowercase identifiers, exact lowercase SHA-256 revisions, bounded control-safe prompts, unique ids/revisions, and the sole allowlisted `prompt_only` effect. Unknown ids, revision drift, duplicate identity, malformed strings, unsupported effects, and oversized content fail closed.
- First migration: the byte-identical existing research-notebook instruction is now bundled as `research_brief_v1` at revision `004a2e575e7c453853ee53521b45b4865c7caa7540c0a58786d49460199f3418`. The router resolves that compile-time id and exact revision before backend dispatch. A missing or drifted definition returns `runtime_prompt_skill_unavailable` without provider calls, chat events, or notebook creation.
- Data boundary: definitions contain only validated string metadata and a non-executing effect. No executor closure, path, URL, environment, command, provider, credential, resource handle, or network capability is represented. The prompt is backend-only and does not enter chat events, history, titles, notebook metadata, mobile state, or wire responses.
- Wire boundary: `chat.send` remains limited to its existing fields. `prompt_skill_id`, `skills.*`, `permission.*`, `approval.*`, `audit.*`, `python.*`, `file.*`, `terminal.*`, `network.*`, `backend.*`, MCP, web search, and generic tool execution remain inactive and rejected. The current registry is not remote discovery or execution authority.
- Focused evidence: seven registry tests plus four `testResearchBriefCreate*` router tests pass. They cover an independent exact prompt-byte/revision fixture, lookup, sorting, collection/identifier/revision/effect/prompt bounds, Unicode byte canonicality, duplicate/tamper rejection, single backend-only injection, storage non-disclosure, missing-pinned-skill fail closure before lifecycle mutation, and normal-chat availability under that missing research definition. Android `ProtocolCodecTest`, protocol schema, copy/docs hygiene, authenticated mock smoke, syntax, and diff checks pass.
- Review result: GPT-5.6 Sol selected this non-executing foundation over a client-selected `prompt_skill_id`, then found late lifecycle validation, a missing shared/Android error-code contract, a self-referential prompt-byte gate, and overbroad failure of normal chat. All four P2 findings are remediated; final re-review reports no remaining P0-P3 findings.
- Final aggregate evidence: `build/qa/check-no-device-quality-v05-prompt-skill-registry-final-reviewed-20260715.log` exits 0 across 10,957 lines with one `No-device quality checks passed.` marker, one dedicated prompt-only skill registry addendum, 88 local development-relay matches, and 919 encrypted frame bodies. Protocol/copy/docs hygiene, shell/Python syntax, Android/Swift regressions, authenticated direct/relay smoke, P2P/NAT and relay design validators, and `git diff --check` pass.
- Integrity evidence: the refreshed P2P/NAT 13-artifact collection is `63ca0efb277b07704e8ae670a21e7f3c91694e8eccf3d9be4465fbf6b257268e`; the relay collection is `52fe7b78b402e30191329aa3bc6751671acabd09ffc25a2a0d6704852bfd3676`. Both design validators pass while P2P socket execution and production relay implementation remain closed.
- Evidence boundary: current proof is SwiftPM and static no-device work only. It does not prove live-provider prompt quality, mobile skill UI, remote registry discovery, approval-required skill execution, Python/tool sandboxing, physical Android, optical QR, external networking, production relay/P2P, ICE/STUN/TURN, NAT traversal, measurement, or deployment.
- Approval boundary: all four controlled-spike approvals remain bounded Phase A only. Source acquisition, inspected-source execution, sockets, network I/O/measurement, Phase B, production networking, and deployment remain closed. `memory_semantic_duplicate_acceptance_v1_recommended` remains `proposed_not_selected`.

## v0.5 Models Pull Host-Local Approval Broker

- Date: 2026-07-15.
- Status: implemented with focused and final aggregate no-device verification passing.
- Capability boundary: `LlmBackend` is split into serving and `ModelPullDispatching` capabilities. `LocalRuntimeMessageRouter` holds only the serving capability, while `RuntimeModelPullApprovalBroker` exclusively owns provider download dispatch. No `permission.*`, `approval.*`, `audit.*`, `skills.*`, `python.*`, `file.*`, `terminal.*`, `network.*`, or other generic execution wire namespace is activated.
- Intake boundary: authenticated legacy requests retain the closed `model` plus optional `backend=ollama` payload. The model reference must be NFC canonical, untrimmed, control-free, Ollama-bound, and at most 256 UTF-8 bytes. Android remains unable to advertise or send `models.pull`; the legacy wire path exists only for compatibility with older paired clients.
- Host boundary: a valid request creates an ephemeral macOS review containing the model and safe trusted-device display name. Status shows the pending count and an explicit confirmation checkbox with approve/dismiss controls; remote input does not open a sheet or activate the app. A five-minute TTL, 32-review cap, and one active provider dispatch bound the queue.
- Authorization boundary: approval captures the exact connection, request, authenticated session, authentication generation, trusted public key, and transport binding. Inside `TrustedDeviceStore.withTrustedDeviceSnapshot`, the router revalidates those values and commits the durable `dispatch_reserved` transition as the irreversible provider-dispatch claim before the broker calls the provider. Trust removal, reauthentication, binding drift, disconnect, duplicate request binding, expiry, store failure, or concurrent approval that linearizes before that claim yields zero provider calls; a later change cannot undo claimed work but suppresses its wire result as `result_suppressed`.
- Audit boundary: `SQLiteRuntimeModelPullApprovalStore` uses owner-only files, schema/integrity validation, allowlisted codes, a unique domain-separated request-binding digest, and `BEGIN IMMEDIATE` transitions. Durable rows contain no raw model, request/device identity, public key, transport binding, URL, credential, or backend error. Restart recovery terminalizes pending work as `host_restarted` and reserved work as `result_suppressed`; it never retries provider work.
- Publication boundary: provider success or a generic redacted failure is published only after a second authority recheck and a matching durable terminal-audit commit inside that authority boundary. Terminal-write failure, authority loss, or approval-TTL completion suppresses the wire result and records or restart-recovers `result_suppressed`. Success is rebuilt from the authorized model plus fixed `completed`/installed fields; provider-controlled success strings never reach the wire. The host model catalog is refreshed after the decision completes.
- Focused evidence: 19 store/broker tests, eight router `models.pull` tests, five `CompanionAppModel` governance tests, all seven error keys plus audit copy in five languages, and an exact explicit-confirmation regression pass. The pending-review panel bitmap and intrinsic-height smoke include each language's longest localized error across system/light/dark appearances and accessibility text size. Protocol schema, copy hygiene, and target builds pass.
- Review result: GPT-5.6 Sol first found pre-terminal wire publication, repeat startup recovery, provider-controlled success fields, authorization-crossing expiry retention, unlocalized errors, and stale active-flow documentation. A second review required explicit irreversible-claim semantics, a real router-path terminal-fault regression, complete error-key/render coverage, and current gate diagnostics. Those remediations are implemented, and final re-review reports no remaining P0-P3 findings or introduced regressions.
- Final aggregate evidence: `build/qa/check-no-device-quality-v05-models-pull-host-local-approval-broker-final-reviewed-20260715.log` exits 0 across 10,905 lines with one `No-device quality checks passed.` marker, one dedicated v0.5 broker addendum, 88 local development-relay matches, and 917 encrypted frame bodies. Protocol/copy/docs hygiene, shell/Python syntax, Android/Swift regressions, authenticated direct/relay smoke, P2P/NAT and relay design validators, and `git diff --check` pass.
- Integrity evidence: the refreshed P2P/NAT 13-artifact collection is `63ca0efb277b07704e8ae670a21e7f3c91694e8eccf3d9be4465fbf6b257268e`; the relay collection is `52fe7b78b402e30191329aa3bc6751671acabd09ffc25a2a0d6704852bfd3676`. Both design validators pass while P2P socket execution and production relay implementation remain closed.
- Evidence boundary: current proof is no-device SwiftPM, temporary SQLite, Android JVM/Robolectric/Compose, static schema/docs, macOS bitmap rendering, and loopback development smoke without a physical device or live provider. It does not prove a live Ollama download, provider bandwidth/disk behavior, process termination during an actual download, physical Android/TalkBack, optical QR, external networking, production relay/P2P, ICE/STUN/TURN, NAT traversal, measurement, or deployment.
- Approval boundary: all four controlled-spike recommendations remain bounded Phase A approvals only. Source acquisition, inspected-source execution, sockets, network I/O/measurement, Phase B, production networking, and deployment remain closed. `memory_semantic_duplicate_acceptance_v1_recommended` remains `proposed_not_selected`.

## v0.5 Models Pull Host-Approval Fail-Closed Prerequisite

- Date: 2026-07-15.
- Status: implemented as a fail-closed prerequisite with focused and final aggregate no-device verification passing.
- Runtime boundary: authenticated legacy `models.pull` requests still receive strict envelope, allowlist, nonblank-model, and `backend=ollama` validation, but the handler then returns non-retryable `model_pull_approval_required`. It contains no `backend.pullModel` call, so valid, malformed, replayed, and concurrent client requests cannot start provider download through this route.
- Android boundary: `models.pull` is no longer advertised in `RUNTIME_CLIENT_CAPABILITIES`. Selecting or directly requesting an uninstalled model does not persist selection, set installation state, or send an envelope; the previous installed model remains usable. Uninstalled chat rows are disabled and expose a localized runtime-host-approval-required state. Unsolicited legacy result frames have no active correlation and cannot mutate selection or trigger catalog refresh.
- Protocol boundary: the existing legacy request/result wire shapes remain documented for compatibility, while `model_pull_approval_required` is a canonical structured error. No `permission.*`, `approval.*`, `audit.*`, `skills.*`, `python.*`, `file.*`, `terminal.*`, `network.*`, provider-routing, or other reserved execution message has been activated.
- Reopen condition: model download can be re-enabled only through a macOS-host-local governance store and UI that atomically bind approval, current trust/authentication generation, one-time dispatch reservation, and durable redacted audit before any provider call. Android confirmation alone is explicitly insufficient because a compromised paired client could self-confirm.
- Focused evidence: five selected Swift router tests pass. The complete affected Android `RuntimeClientViewModelTest`, `AppNavigationTest`, and `ClientScreensNoDeviceComposeTest` classes pass 971 tests with zero failures, errors, or skips under the Android Studio JBR. Protocol schema, Android string parity, copy/docs hygiene, shell/Python syntax, `git diff --check`, and authenticated direct mock smoke pass. The smoke proves a valid pull returns the host-approval error and leaves the model catalog unchanged.
- Review result: GPT-5.6 Sol security and integration reviewers first found one stale active-flow statement in the protocol lifecycle. A final evidence review then found normalized-text manifest hashing and incomplete per-section Phase A boundary pins. The lifecycle, raw-byte hash check, and section-specific evidence guards are fixed; final re-review reports no remaining P0-P3 findings.
- Final aggregate evidence: `build/qa/check-no-device-quality-v05-models-pull-host-approval-fail-closed-final-reviewed-20260715.log` exits 0 across 10,740 lines with one `No-device quality checks passed.` marker, one dedicated v0.5 prerequisite marker, 88 local development-relay matches, and 919 encrypted frame bodies. Protocol/copy/docs hygiene, shell/Python syntax, Android/Swift regressions, authenticated direct/relay smoke, P2P/NAT and relay design validators, and `git diff --check` pass.
- Integrity evidence: the refreshed P2P/NAT 13-artifact collection is `63ca0efb277b07704e8ae670a21e7f3c91694e8eccf3d9be4465fbf6b257268e`; the relay collection is `52fe7b78b402e30191329aa3bc6751671acabd09ffc25a2a0d6704852bfd3676`. Both design validators pass while P2P socket execution and production relay implementation remain closed.
- Evidence boundary: all evidence is no-device SwiftPM, Android JVM/Robolectric/Compose, schema/static, and loopback development smoke. It does not prove a host approval UI or audit store, live-provider download behavior, physical Android/TalkBack, optical QR, external networking, production relay/P2P, ICE/STUN/TURN, NAT traversal, measurement, or deployment.
- Approval boundary: all four controlled-spike recommendations remain bounded Phase A approvals only; source acquisition, inspected-source execution, sockets, network I/O/measurement, Phase B, production networking, and deployment remain closed. `memory_semantic_duplicate_acceptance_v1_recommended` remains `proposed_not_selected`.

## v0.4 Android Drawer Selected-Model Capability Summary

- Date: 2026-07-15.
- Status: implemented on the Android navigation drawer with focused and final aggregate no-device verification plus independent final re-review passing.
- Contract boundary: no protocol field, model catalog, provider call, model selection, persistence, backend URL, direct client-to-provider access, or network behavior changed. The drawer consumes only the existing transient runtime-owned model catalog and current selected model id.
- Projection boundary: when the exact selected model is present in the eligible runtime-host-local chat catalog, the drawer reuses the same closed provider/Installed/Running plus Chat, optional Vision, and optional positive context-window projection as the chat model picker. Unknown raw capability values are neither rendered nor spoken, and zero context remains absent.
- Accessibility and layout: visual detail retains localized middle-dot separation while the single merged TalkBack node uses the separate localized accessibility projection. A real 300 dp drawer path at 1.5 font scale covers English, Korean, Japanese, Simplified Chinese, and French with a long LM Studio running Vision model and 131,072-token context without name/detail overlap or bounds escape.
- Recovery priority: an exact selected-model catalog miss still uses the existing saved-name plus restoring/unavailable recovery detail instead of fabricating capability metadata. The expanded five-language regression proves the unavailable-to-restoring state transition in both the unmerged visual detail node and the merged TalkBack summary, and rejects stale unavailable text after loading starts.
- Focused verification: both selected drawer regressions pass, including the forced unavailable-to-restoring transition. The complete `ClientScreensNoDeviceComposeTest` reports 279 tests with zero failures, errors, or skips in 19 seconds. Android compilation, string parity, copy/docs hygiene, shell syntax, and `git diff --check` pass.
- Review result: GPT-5.6 Sol found that restoring recovery initially lacked a regression, the first stale-unavailable canary inspected only merged semantics, and the recovery evidence plus document guards were incomplete. The product-path test now checks exact unmerged visual details and merged TalkBack summaries for both states across five languages, rejects stale unavailable text, and copy hygiene pins the complete evidence contract in each document. Final re-review reports no remaining P0-P3 findings.
- Final aggregate evidence: `build/qa/check-no-device-quality-v04-android-drawer-selected-model-capability-summary-final-reviewed-20260715.log` exits 0 across 10,724 lines with one `No-device quality checks passed.` marker, one Android drawer selected-model capability summary addendum, 88 local development-relay matches, and 922 encrypted frame bodies. Protocol/copy/docs hygiene, shell syntax, Android/Swift regressions, direct and relay authenticated smoke, P2P/NAT and relay design validators, and `git diff --check` pass.
- Durable gate: the default no-device selector already runs both drawer regressions and now emits `Covered v0.4 addendum: Android drawer selected-model capability summary`. Copy hygiene pins the shared projection, missing-model priority, localized accessibility resource, tests, marker, and evidence documents.
- Next action recorded for this completed v0.4 slice was to close or separately permission-gate authenticated `models.pull`. The v0.5 prerequisite section above now closes that provider dispatch fail-closed; it does not implement a permission system. `skills.*`, `permission.*`, `python.*`, `file.*`, `terminal.*`, and `network.*` execution surfaces remain closed.
- Evidence boundary: current proof is Android JVM/Robolectric/Compose and static source evidence only. It does not prove physical Android layout, TalkBack traversal, live-provider metadata or model capability quality, optical QR, external networking, production relay/P2P, ICE/STUN/TURN, NAT traversal, measurement, or deployment.
- Approval boundary: all four controlled-spike recommendations remain bounded Phase A approvals only. Source acquisition, inspected-source execution, sockets, network I/O/measurement, Phase B, production networking, and deployment remain closed. `memory_semantic_duplicate_acceptance_v1_recommended` remains `proposed_not_selected` and unchanged.

## v0.4 Android Research Brief Model Capability Selection

- Date: 2026-07-15.
- Status: implemented on the Android research-brief creation dialog with focused and final aggregate no-device verification plus independent final re-review passing.
- Contract boundary: no protocol field, model route, provider request, trusted-source rule, notebook persistence, global chat-model preference, backend URL, direct client-to-provider access, or network behavior changed. The dialog consumes only the existing transient runtime-owned model catalog.
- Authority boundary: the picker exposes only installed runtime-host-local chat models. Embedding, uninstalled, provider-managed, and unknown-source rows remain absent, and `createResearchBrief` independently rechecks exact catalog identity, chat kind, local source, and installation before sending `research.brief.create`.
- Display and accessibility: research rows reuse the existing closed provider/status/capability projection: Chat, optional exact Vision aliases, and optional positive context-window size. Unknown raw capabilities and other model metadata are neither rendered nor spoken. The closed control has a visible Selected model label, a localized model-purpose summary, selected state, named Choose model action, and a streaming-disabled explanation.
- Selection lifecycle: a dialog-local selection survives catalog reorder and metadata refresh while still eligible, falls back to the current eligible runtime selection only when removed, never changes the global chat-model preference, and reaches the existing Create callback exactly. Streaming or an empty eligible catalog closes an open menu, disables the picker as applicable, and does not reopen it automatically after recovery.
- Focused verification: the selected implementation tests pass after remediation. The complete `RuntimeClientViewModelTest` reports 536 tests, `ClientScreensNoDeviceComposeTest` reports 279 tests, and `ResearchNotebookDrawerTest` reports one test, for 816 tests with zero failures, errors, or skips in 20 seconds. Coverage includes direct provider-managed/unknown-source rejection, exact callback model identity, eligible catalog refresh retention, removed-model and empty-catalog recovery, streaming transition, raw-capability and nonpositive-context suppression, five-language direct row layout, and the real 320 dp by 360 dp nested dialog/popup path at 1.5 font scale including teardown.
- Review result: GPT-5.6 Sol found catalog refresh could overwrite a valid dialog-local choice, the closed picker lacked purpose and disabled-state semantics, compact coverage initially bypassed the nested popup, Create identity and nonpositive context were under-tested, and an empty eligible catalog could leave a blank popup open. The implementation and product-path regressions remediate all five issues; final re-review reports no remaining P0-P3 findings.
- Final aggregate evidence: `build/qa/check-no-device-quality-v04-android-research-brief-model-capability-selection-final-reviewed-20260715.log` exits 0 across 10,736 lines with one `No-device quality checks passed.` marker, one Android research brief model capability selection addendum, 88 local development-relay matches, and 924 encrypted frame bodies. Protocol/copy/docs hygiene, shell syntax, Android/Swift regressions, direct and relay authenticated smoke, P2P/NAT and relay design validators, and `git diff --check` pass.
- Evidence boundary: current proof is Android JVM/Robolectric/Compose and static source evidence only. It does not prove physical Android layout, TalkBack traversal, live-provider metadata, model quality, optical QR, external networking, production relay/P2P, ICE/STUN/TURN, NAT traversal, measurement, or deployment.
- Approval boundary: all four controlled-spike recommendations remain bounded Phase A approvals only. Source acquisition, inspected-source execution, sockets, network I/O/measurement, Phase B, production networking, and deployment remain closed. `memory_semantic_duplicate_acceptance_v1_recommended` remains `proposed_not_selected` and unchanged.

## v0.4 Android Authoritative Drawer Virtualization

- Date: 2026-07-14.
- Status: implemented on the Android navigation drawer with focused and final aggregate no-device verification plus independent review passing.
- Contract boundary: no protocol, pagination, ViewModel authority, persistence, model, provider, source, network, or selection behavior changed. The drawer continues to consume only the transient terminal `research.notebooks.authoritative_sync.v1` snapshot, whose existing contract allows zero through 10,000 rows.
- Virtualization boundary: the drawer's one weighted history scroll surface is now a single `LazyColumn`. Research headings, active and archived notebook rows, divider, previous-chat heading/search/empty states, chat date headings, and chat rows are separate lazy items with namespaced stable keys and content types; no nested vertical list or eager notebook group remains.
- Identity and behavior: notebook keys depend only on backing session ID across active-to-archived movement. Production research and chat overflow menus each retain one hoisted target ID instead of per-visited-row saveable state. Existing selection, rename, archive, restore, two-step permanent delete, streaming/disconnect/history lockout, localized headings and TalkBack actions, chat search/date grouping, and fixed Settings footer remain unchanged.
- Focused verification: eight selected Android Studio JBR regressions pass in 29 seconds, three controlled/fallback chat-menu regressions pass in 28 seconds, and the final complete `ClientScreensNoDeviceComposeTest` plus `ResearchNotebookDrawerTest` run passes 278 tests with zero failures, errors, or skips in 17 seconds. The 10,000-row case proves fewer than 100 matching semantics nodes are initially composed, terminal active and archived rows are absent before indexed scrolling, the terminal active row remains actionable, the first row is disposed after distant scrolling, and the terminal archived row is reachable. Separate regressions preserve active-to-archived notebook menu identity, enforce streaming lockout on an already-open controlled chat menu, clear its filtered-out target, and prove it stays closed when that session returns.
- Review result: GPT-5.6 Sol identified section-dependent notebook keys and per-row production menu state as implementation risks before the first pass. After stable session keys and hoisted research/chat menu targets, it found the controlled chat path lacked direct coverage and then that the filtered-removal assertion could false-pass through row uncomposition. The actual drawer regression now covers lockout, callback suppression, removal, reintroduction, closed-state retention, and explicit reopening. Final re-review reports no remaining P0-P3 findings.
- Final aggregate evidence: `build/qa/check-no-device-quality-v04-android-authoritative-drawer-virtualization-final-reviewed-20260714.log` exits 0 across 10,719 lines with one `No-device quality checks passed.` marker, one Android authoritative drawer virtualization addendum, 88 local development-relay matches, and 922 encrypted frame bodies. Protocol/copy/docs hygiene, shell syntax, Android/Swift regressions, direct and relay authenticated smoke, P2P/NAT and relay design validators, and `git diff --check` pass.
- Evidence boundary: current proof is Android JVM/Robolectric/Compose and static source evidence only. It demonstrates bounded composition behavior, not physical-device startup latency, frame timing, heap use, TalkBack traversal, live network/provider behavior, optical QR, production relay/P2P, ICE/STUN/TURN, NAT traversal, measurement, or deployment.
- Approval boundary: all four controlled-spike recommendations remain bounded Phase A approvals only. Source acquisition, inspected-source execution, sockets, network I/O/measurement, Phase B, production networking, and deployment remain closed. `memory_semantic_duplicate_acceptance_v1_recommended` remains separately unselected and unchanged.

## v0.4 Android Memory Indexing Model Capability Display

- Date: 2026-07-14.
- Status: implemented on the Android Settings memory-indexing model selector; focused and final aggregate no-device verification plus independent review pass.
- Contract boundary: no protocol field, provider request, model route, selection policy, semantic duplicate threshold, acceptance corpus, or direct client-to-provider path was added. The UI consumes the existing transient runtime-owned `RuntimeModel` provider, kind/capabilities, installed state, source, and positive `contextWindowTokens` metadata.
- Selection/display boundary: the menu now exposes only canonical provider-qualified, embedding-capable runtime-host-local rows, matching `selectEmbeddingModel` and selection reconciliation. Each row shows the localized known projection `Embedding` plus an exact localized context-window count only when positive. Unknown raw capabilities, noncanonical IDs, and cloud/provider-managed rows are neither shown nor spoken; saved-missing recovery and streaming lockout remain unchanged.
- Accessibility/layout: TalkBack summaries combine provider, availability, and the known capability projection with spoken punctuation independent from the visual middle dot. Capability detail wraps without ellipsis. English, Korean, Japanese, Simplified Chinese, and French regressions cover exact summaries and 260 dp at 1.5 font scale without name/detail overlap.
- Focused verification: six selected Android Studio JBR tests pass after remediation in 18 seconds, covering canonical runtime-host-local filtering, selected/uninstalled and zero/negative-context semantics, provider-managed suppression, streaming lockout, five-language accessibility, and direct plus full-Settings compact layout. Android string parity, copy/docs hygiene, shell syntax, and `git diff --check` pass. GPT-5.6 Sol's P2 canonical-ID parity and P3 nonpositive-context coverage findings are remediated; final re-review reports no remaining P0-P3 findings.
- Final aggregate evidence: `build/qa/check-no-device-quality-v04-android-memory-indexing-model-capability-display-final-reviewed-20260714.log` exits 0 across 10,715 lines with one `No-device quality checks passed.` marker, one Android memory indexing model capability display addendum, 88 local development-relay matches, and 922 encrypted frame bodies. Protocol/copy/docs hygiene, shell syntax, Android/Swift regressions, direct and relay authenticated smoke, P2P/NAT and relay design validators, and `git diff --check` pass.
- Evidence boundary: current proof is Android JVM/Robolectric/Compose and static-resource evidence only. It does not prove physical Android rendering, on-device TalkBack traversal, live-provider metadata, optical QR, external networking, production relay/P2P, ICE/STUN/TURN, NAT traversal, measurement, or deployment.
- Approval boundary: all four controlled-spike recommendations remain bounded Phase A approvals only. Source acquisition, inspected-source execution, sockets, network I/O/measurement, Phase B, production networking, and deployment remain closed. `memory_semantic_duplicate_acceptance_v1_recommended` remains `proposed_not_selected` and is unchanged.

## v0.4 macOS Runtime Model Capability Display

- Date: 2026-07-14.
- Status: implemented on the macOS Status model rows with focused and final aggregate no-device verification passing.
- Contract boundary: no protocol field, capability, model route, provider request, selection policy, or direct client-to-provider path was added. The runtime-host UI consumes the existing `ModelInfo.kind`, `capabilities`, positive `contextWindowTokens`, provider/source/running state, and size metadata already loaded by `CompanionAppModel`.
- Display boundary: the existing Chat or Embedding kind badge remains the base capability indicator. Chat models add `Vision` only for the closed `vision`, `image`, or `multimodal` aliases, and either kind adds an exact localized context-window badge only for a positive token count. Unknown raw capability values, remote model/host data, persistent embedding revisions, and backend URLs are not shown or spoken. The existing runtime-owned model ID remains visible and spoken. Installed-local filtering and Chat/Embedding grouping are unchanged.
- Accessibility and layout: VoiceOver receives the existing model type once, then optional Vision and exact context count through a separately localized capability list without repeating the kind. The compact Status render covers long model names, the maximum test context label, both model kinds, all five app languages, and system/light/dark appearances without adding truncation to capability badges.
- Focused verification: five selected localization/projection/visibility tests and the direct compact model-row render smoke across 15 language/appearance combinations pass. The projection tests reject nil, zero, and negative context windows, keep whitespace-mutated and future capability canaries hidden, and verify all supported Vision aliases. GPT-5.6 Sol independently selected this as the next unblocked v0.4 slice before implementation; its final re-review reports no remaining P0-P3 findings.
- Final aggregate evidence: `build/qa/check-no-device-quality-v04-macos-model-capability-display-final-reviewed-20260714.log` exits 0 across 10,736 lines with one `No-device quality checks passed.` marker, one macOS runtime model capability display addendum, 88 local development-relay matches, and 924 encrypted frame bodies. Protocol/copy/docs hygiene, shell syntax, Android/Swift regressions, direct and relay authenticated smoke, P2P/NAT and relay design validators, and `git diff --check` pass.
- Evidence boundary: current evidence is macOS SwiftPM/localization/render and static evidence only. It does not prove live-provider metadata quality, physical VoiceOver traversal, Android hardware, optical QR, external networking, production relay/P2P, ICE/STUN/TURN, NAT traversal, measurement, or deployment.
- Network boundary: all four controlled-spike recommendations remain approved only for bounded Phase A. Source acquisition, inspected-source execution, sockets, network I/O/measurement, Phase B, production networking, and deployment remain closed.

## v0.4 Runtime-Mediated Model Capability Display

- Date: 2026-07-14.
- Status: implemented on the Android chat-model selector. Focused and final aggregate no-device verification pass.
- Contract boundary: no protocol field, capability, model route, provider call, or client-to-backend access was added. Android consumes the existing runtime-owned `models.result` provider, `model_kind`, `capabilities`, installation/running state, and positive `context_window_tokens` metadata already accepted into transient `RuntimeModel` state.
- Display boundary: chat rows show only the localized known projection `Chat`, optional `Vision`, and optional exact context-window token count beside the existing provider and availability state. Unknown raw capability strings are not rendered or spoken. Embedding models remain outside the chat picker, cloud/provider-managed rows remain excluded, and model selection/install plus streaming and vision-recovery lockouts are unchanged.
- Accessibility and layout: visual capability punctuation and spoken list punctuation use separate localized resources. TalkBack summaries include provider, availability, and the known capability projection without reading the visual middle-dot separator. The bounded metadata detail wraps without max-line ellipsis; compact large-font tests scroll each row into view, compare the complete localized detail string, and verify row/name/detail/install-action bounds across English, Korean, Japanese, Simplified Chinese, and French.
- Focused verification: Android Studio JBR passes two existing protocol metadata tests, two model-selection/navigation tests, and five model-picker Compose tests. Android string parity, copy hygiene, shell syntax, and `git diff --check` pass. GPT-5.6 Sol identified detail ellipsis, shared visual/spoken punctuation, and an inexact detail assertion; all three are remediated and final re-review reports no P0-P3 findings.
- Final aggregate evidence: `build/qa/check-no-device-quality-v04-model-capability-display-final-reviewed-20260714.log` exits 0 across 10,699 lines with one `No-device quality checks passed.` marker, one runtime-mediated model capability display addendum, 88 local development-relay matches, and 922 encrypted frame bodies. Protocol/copy/docs hygiene, shell syntax, Android/Swift regressions, direct and relay authenticated smoke, P2P/NAT and relay design validators, and `git diff --check` pass.
- Evidence boundary: current evidence is Android JVM/Robolectric/Compose and static resource evidence only. It does not prove physical Android rendering, TalkBack traversal on a device, live-provider metadata quality, optical QR, external networking, production relay/P2P, ICE/STUN/TURN, NAT traversal, measurement, or deployment.
- Network boundary: all four controlled-spike recommendations remain approved only for bounded Phase A. Source acquisition, inspected-source execution, sockets, network I/O/measurement, Phase B, production networking, and deployment remain closed.

## v0.3 Research Notebook Rename Title Authority

- Date: 2026-07-14.
- Status: implemented across the macOS runtime projection and Android research-notebook UI. Independent review identified host publication/authentication/title-metadata, legacy replay/clock rollback, and Android delayed-response/lifecycle/refresh/CAS gaps; all identified issues are remediated, and focused plus aggregate no-device verification pass.
- Protocol contract: no new message, capability, or notebook-title mutation exists. Active and archived notebook rename actions reuse the existing authenticated `chat.session.rename` request for the backing session. `research.notebooks.list` projects that runtime-owned chat title as the single mutable title authority.
- Host boundary: rename timestamps are canonicalized before event persistence and acknowledgement. Title metadata has separate `titleUpdatedAt` and `titleRevision`; it advances notebook `updated_at` and deterministic ordering while preserving conversational `lastActivityAt` and last-event metadata and without mutating the immutable notebook-creation title. User and generated titles are NFC-normalized, trimmed, control-free, and bounded to 256 Unicode scalars at both router and JSONL/SQLite append boundaries. Explicit and automatic title generation require an existing active placeholder, capture its title revision, and revalidate owner, authentication, lifecycle, title, and revision before commit, so a concurrent rename cannot be overwritten. Successful commits invalidate chat and research cursors; title authority follows append/revision order across equal or reverse timestamps and legacy import; new mutation timestamps advance beyond the prior title update; and pre-hardening invalid title rows receive a deterministic safe projection without weakening new append validation. Explicit rename/title-result publication remains inside the same lifecycle authorization lock. Legacy/local list publication also rechecks its captured lifecycle generation, including the local-owner scope.
- Android boundary: active and archived notebook menus expose localized Rename actions and notebook-specific dialog semantics. The ViewModel applies the optimistic title only to transient notebook state, sends the backing session id through `chat.session.rename`, binds ACK/error handling to the exact request, channel, connection generation, and authenticated authority, serializes same-session lifecycle work, rolls back malformed, failed, or 15-second timed-out results, tombstones completed requests so delayed ACK/errors are ignored, and refreshes both notebook and ordinary-chat authority. Mandatory refreshes arriving during notebook pagination are queued and cause the stale terminal snapshot to be skipped. Held or paginating chat snapshots exclude every research session ID observed during the run, including IDs introduced and removed between pages. Rename success/failure uses an exact optimistic row plus local revision CAS, preserving a newer authoritative row even when its title text matches the optimistic value. Malformed lifecycle timestamps close and roll back only the exact mutation without terminating the receive loop; uncorrelated delayed pairing-required errors cannot revoke current authentication even after bounded tombstone eviction. Different-session lifecycle work remains independent. Research backing sessions and renamed titles remain absent from `RuntimeLocalStore`.
- Focused verification: the selected macOS impact run passes 85 tests with zero failures, covering title authority, separate activity/title timestamps, equal/reverse-timestamp append ordering, legacy invalid-title projection/import, legacy and authoritative publication races, automatic and explicit generated-title reauthentication/revision fencing, cursor invalidation, title bounds, owner isolation, JSONL/SQLite parity and reopen, and preservation of the immutable notebook row. Android Studio JBR passes 535 `RuntimeClientViewModelTest`, 14 `RuntimeClientChatSessionMutationFailureTest`, and one localized Compose test, with zero failures, errors, or skips. That 550-test impact run includes queued post-brief refresh, stale terminal suppression, intermediate research-authority redaction, rename CAS preservation, held-snapshot authority changes, malformed archive/restore timestamps, bounded-tombstone eviction, active correlated authentication errors, same-session serialization, different-session independence, timeout rollback, and late response rejection.
- Final aggregate evidence: `build/qa/check-no-device-quality-v03-research-notebook-rename-title-authority-final-reviewed-20260714.log` exits 0 across 10,683 lines with one `No-device quality checks passed.` marker, one research-notebook rename title-authority addendum, the 78-test aggregate Swift research/title selector, 88 local development-relay matches, and 922 encrypted frame bodies. Protocol/copy/docs hygiene, shell syntax, Android/Swift regressions, direct and relay authenticated smoke, P2P/NAT and relay design validators, and `git diff --check` pass.
- Evidence boundary: current evidence is no-device SwiftPM/JSONL/SQLite plus Android JVM/fake-channel/Compose only. It does not prove physical Android UI, optical QR, live-provider behavior, external-network behavior, production relay/P2P, ICE/STUN/TURN, NAT traversal, measurement, or deployment.
- Network boundary: all four controlled-spike recommendations remain approved only for bounded Phase A. Source acquisition, inspected-source execution, sockets, network I/O/measurement, Phase B, production networking, and deployment remain closed.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark is excluded.

## v0.3 Runtime-Authoritative Research Notebook Pagination

- Date: 2026-07-14.
- Status: implemented across the shared contract, macOS runtime, authenticated direct/relay development smoke, and Android client. Focused verification, independent GPT-5.6 Sol review, and the final aggregate no-device gate pass.
- Protocol contract: `research.notebooks.authoritative_sync.v1` augments the existing `research.notebooks.v1` list operation without changing legacy peers. Initial requests keep exact `include_archived` and `limit` fields with a capable 1 through 200 page bound; continuations are cursor-only. Capable responses add `snapshot_count` from 0 through 10,000 and an optional 512-UTF-8-byte `next_cursor`; legacy responses remain exactly `notebooks` with at most 100 rows. The bounded hello capability list now accepts at most 64 unique values and rejects 65.
- Host boundary: macOS snapshots the complete owner-scoped filtered and canonical ordered result, then signs an opaque 120-second HMAC cursor bound to the connection, authenticated owner, include-archived context, page size, snapshot count, offset, and expiry. One snapshot is retained per connection and at most eight globally. Disconnect, authentication change, notebook creation, archive, restore, and delete invalidate relevant authority; stale initial work is suppressed before publication. Backing chat summaries are fetched only for canonical notebook session ids, with a 10,000-id bound, owner-scoped batched SQLite lookup, and targeted JSONL filtering instead of an owner-wide unbounded scan.
- Android boundary: pages accumulate privately under the exact request, channel, connection generation, authentication authority, count, and cursor chain. Only a validated terminal snapshot atomically replaces notebook rows and backing-session classification, without publishing the stale completed notebook state first. Duplicate notebook or session ids, count drift or overflow, cursor loops, empty nonterminal pages, ordering drift, stale responses, per-request timeout, more than 100 pages, and capable-to-legacy downgrade fail closed without publishing partial state. A terminal zero snapshot authoritatively clears notebook and transient backing-session state. Empty or leading-whitespace no-op create deltas do not extend the authority-bound idle timeout.
- Shared fixture: `shared/protocol/fixtures/research-notebooks-authoritative-sync-smoke-v1.json` contains an exact two-page payload transcript, a legacy response, and deterministic 201-notebook `100/100/1` pagination metadata. The authenticated smoke materializes all 201 rows into temporary runtime chat/notebook stores and validates exact ids, ordering, counts, cursors, terminal state, and independent cursor-plus-limit and cursor-plus-include-archived rejection over both direct TCP and the local development relay.
- Focused verification: Android protocol passes 125 tests and the complete `RuntimeClientViewModelTest` passes 525 tests with zero failures, errors, or skips. The selected macOS router, paginator, and SQLite set passes 76 tests, and the separate hello 64/65 boundary test passes. Direct and relay authenticated development smoke both pass the actual 201-row `100/100/1` flow while preserving exact legacy behavior. Reviews found owner-wide lookup, mandatory fallback, identifier validation, provisional/legacy authority, timeout/error, no-op-delta timeout, stale terminal publication, fixture execution, negative-case isolation, and relay-client lifetime gaps; each was remediated, and final macOS and Android/protocol re-reviews report no remaining P0-P3 finding.
- Final aggregate evidence: `build/qa/check-no-device-quality-v03-research-notebook-authoritative-pagination-final-reviewed-r4-20260714.log` exits 0 across 10,608 lines with one `No-device quality checks passed.` marker, one runtime-authoritative research-notebook pagination addendum, two authenticated 201-row checks, 88 local development-relay matches, and 920 encrypted frame bodies. Protocol/copy/docs hygiene, P2P/NAT and relay design validators, shell syntax, Android/Swift regressions, authenticated smoke, and `git diff --check` pass. The current 13-artifact P2P/NAT evidence collection is `63ca0efb277b07704e8ae670a21e7f3c91694e8eccf3d9be4465fbf6b257268e`.
- Evidence boundary: current evidence is no-device Android JVM/fake-channel, schema/static, SwiftPM, and authenticated loopback-development-smoke evidence only. It does not prove physical Android, optical QR, external networking, live-provider behavior, production relay/P2P, ICE/STUN/TURN, NAT traversal, measurement, or deployment.
- Network boundary: all four controlled-spike recommendations remain approved only for bounded Phase A. Socket execution, network I/O and measurement, Phase B, production networking, and deployment remain closed.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark is excluded.

## v0.3 Runtime-Owned Research Notebooks And Brief Generation

- Date: 2026-07-14.
- Status: implemented across the shared protocol, macOS runtime/storage, authenticated development smoke, and Android client/UI. The Android mixed active/archived lifecycle slice and SQLite lifecycle lease precision fix are implemented, post-remediation reviewed, and covered by the final aggregate no-device gate.
- Protocol contract: `research.notebooks.v1` activates only `research.brief.create` and `research.notebooks.list`. Create accepts one through eight unique current-device approved source grants, a canonical notebook id, a bounded topic, and one installed local chat model. Responses reuse the original `chat.delta`/`chat.done`, cancel, history, lifecycle, and safe source-attribution contracts. `research.web.query` and every other unsupported research operation remain rejected.
- Host boundary: memory and SQLite stores keep owner-scoped metadata plus ordered private grant ids, cap each owner at 10,000 notebooks, and read the complete bounded owner candidate set before applying chat-activity ordering and the 100-row wire limit. SQLite lifecycle lease dates are canonicalized at create, prepare, and renew boundaries so sub-double `Date` precision cannot make a freshly persisted intent fail its own completion check. Follow-ups require the negotiated capability, pin the original grant order, reject client grant substitution, and revalidate authentication, notebook lifecycle/model/grants, chat lifecycle, grant revision, and approval before backend dispatch or rejected-request persistence. Shared per-database lifecycle coordination fences separate store/router instances, durable intents recover interrupted lifecycle work, research promotion invalidates existing authoritative pagination snapshots, and final list publication filters concurrent promotion/delete races. Research requests exclude general runtime memory, validate model and grants before durable creation, and roll back creation if chat request persistence fails. Runtime instructions and approved excerpts are backend-only; list responses expose safe metadata only.
- Android surface: the drawer lists runtime-owned notebooks and opens active notebooks in the existing transcript view. The mixed authoritative list requests `include_archived=true`, separates active and archived groups, exposes archive for active rows and restore plus two-step permanent delete for archived rows, and keeps archived rows nonselectable. Lifecycle requests and acknowledgements bind the exact request, channel, connection generation, and authentication authority; completed request errors are bounded and ignored after reauthentication. Successful archive/delete and authoritative archived refreshes close pending transcript authority, clear transient messages/drafts/attachments, prevent archived open/send, and refresh both notebook and ordinary-chat authority without persisting research content. Menus follow streaming/disconnect/history lockout even while open. The creation dialog still requires an installed chat model and one through eight approved sources, keeps selected rows removable at the eight-source cap, supports compact-height and enlarged-font layouts, and uses localized plurals and heading semantics.
- Current verification: `swift test --filter 'ResearchNotebook|ResearchBrief|ResearchPromotion|ExpiredLifecycleCannotTakeOver|ChatSessionsList.*Research'` passes 37 tests, the complete router class passes 373, and all 14 SQLite research-notebook store tests pass. The store regressions deterministically require a `Date` with precision beyond SQLite `Double`, then cover direct create completion, create-renew-complete, and prepare-complete lease round trips. Android Studio JBR reports 121 protocol tests plus a 950-test app impact set: 511 ViewModel, 10 mutation-failure, 156 navigation, 272 Compose, and one drawer test, all with zero failures, errors, or skips. The authenticated RuntimeDevServer direct-TCP mock smoke exits 0 and covers capability closure, create/stream/history, safe attribution, pinned follow-up, mismatch, revocation before backend, safe listing, and future `research.web.query` rejection. GPT-5.6 Sol found one P1, two P2, and one P3 in the archived lifecycle pass; all four were remediated. A later Date-regression review found one P2 test-determinism gap and one P3 stale test count; both are remediated, with no remaining P0-P3 finding.
- Final aggregate evidence: `build/qa/check-no-device-quality-v03-research-notebooks-archived-lifecycle-final-reviewed-r3-20260714.log` exits 0 across 10,448 lines with one `No-device quality checks passed.` marker, one runtime-owned research-notebooks addendum, the 37-test focused Swift selector including all 14 SQLite store tests, 87 loopback development-relay matches, and 889 encrypted frame bodies. The current 13-artifact P2P/NAT design evidence collection is `63ca0efb277b07704e8ae670a21e7f3c91694e8eccf3d9be4465fbf6b257268e`; its socket gate remains closed.
- Evidence boundary: current proof is no-device SwiftPM/store/router/mock-server and Android JVM/fake-channel evidence only. No web search, external network access, whole-document authority, physical Android interaction, optical QR, live-provider quality, production relay/P2P, ICE/STUN/TURN, or NAT traversal is claimed.
- Network boundary: all four controlled-spike recommendations remain approved only for bounded Phase A. Socket execution, network I/O and measurement, Phase B, production networking, and deployment remain closed.
- Agent state: GPT-5.6 Sol produced and reviewed the accepted implementation work. One historical nested Spark invocation was stopped by the usage limit before useful output and is not relied upon.

## v0.3 Semantic Memory Calibration Acceptance Review (Selection Pending)

- Date: 2026-07-14.
- Status: `memory_semantic_duplicate_acceptance_v1_recommended` is a closed `proposed_not_selected` review packet, not an approval or behavior change. `evidence_status=blocked_missing_representative_corpus`, measurement is not started, selected recommendation count is zero, and a separate versioned decision sourced from explicit user approval is required before corpus intake, matrix execution, threshold/default/range changes, or automatic memory mutation.
- Representative corpus recommendation: a future consented or synthetic, privacy-reviewed, opaque-ID corpus must contain at least 200 entries, 500 labeled pairs, 100 positive and 100 negative labels, five languages with at least 20 entries each, two independent reviewers per pair plus adjudication, a declared label-coverage policy, source-group-disjoint locked holdout, exact pair and complete-link cluster labels, and no raw production memory, secrets, or direct identifiers. The current 10-entry synthetic fixture remains `synthetic_evaluator_only` and is not acceptance eligible.
- Evaluator boundary: the current live evaluator caps a run at 64 entries and one embed batch, so a representative batched evaluator is an explicit unresolved input and approval prerequisite rather than an implied capability. Future reports must remain aggregate-only; representative corpus text, vectors, paths, provider payloads, and user-derived identifiers must not enter review or decision records.
- Model/artifact matrix recommendation: the proposed matrix requires at least two exact immutable artifact rows covering `lm_studio` and `ollama`. The existing `ollama:embeddinggemma:latest` observation is pinned to `ollama-sha256:85462619ee721b466c5927d109d4cb765861907d5417b9109caebc4e614679f1` but is classified `observed_synthetic_only`; it fills no production acceptance decision by itself. One exact LM Studio artifact row and representative-corpus results for every required row remain missing.
- Acceptance-floor recommendation: every required artifact must pass one shared integer threshold with overall precision at least 9,500 basis points, recall at least 8,000, F1 at least 8,500, at least 100 predicted positives and 100 actual positives, exact complete-link review clusters, and non-null precision. Same-language and cross-language strata must each independently reach precision 9,000, recall 7,000, and positive denominators of at least 20. The separate hard-negative stratum requires at least 20 actual negatives and 9,500 specificity; aggregate averaging cannot hide an artifact or stratum failure.
- Closed behavior: the Android review default remains 9,000 and the allowed range remains 8,000 through 10,000. Default/range change, protocol change, automatic merge or memory mutation, representative corpus intake, and additional live matrix execution are all unauthorized. The packet is immutable in place and may only be superseded by a new versioned review.
- Static evidence: `shared/evaluation/memory-semantic-duplicate-acceptance-review-v1.json` is SHA-256 `d959de7ce19d3557c160aaab83b53b74341b2ef7003a6e61655313a90fca4e32`. `script/check_memory_semantic_calibration_acceptance.py` strictly rejects duplicate JSON keys, unknown/missing fields, nonfinite values, bool/int/float confusion, review/fixture symlink or non-regular input, bounded-size/hash drift, present historical-report hash drift, approval or authorization escalation, matrix completion, floor weakening, averaging, selected thresholds, and blocked-state or immutability changes. Its content-free summary retains all denominator, stratum, per-artifact, and no-averaging requirements. Fifteen mutation/CLI/guard tests pass without network access, and copy hygiene applies the same tested bounded no-follow read before inspecting or hashing either calibration JSON file.
- Review result: two GPT-5.6 Sol read-only reviews found the current 64-entry single-batch limit, undefined-precision handling, absent label-coverage/privacy/holdout rules, single-artifact generalization risk, and aggregate/cohort masking gaps. The review packet now makes the batched evaluator, non-null precision, minimum denominators, independent strata, privacy review, exact artifacts, and closed authorization state explicit. Independent final code and policy re-reviews report no remaining P0-P3 finding.
- Final aggregate evidence: `build/qa/check-no-device-quality-v03-semantic-memory-acceptance-review-final-reviewed-20260714.log` exits 0 across 10,450 lines with one `No-device quality checks passed.` marker, one review-only semantic-memory acceptance-recommendation addendum, both 15-test acceptance-validator runs, 87 loopback development-relay matches, and 889 encrypted frame bodies. Copy/docs hygiene, shell/Python syntax, Android and Swift regressions, authenticated smoke, production P2P/NAT and relay design validators, and `git diff --check` pass while every production network gate remains closed.
- Next action: explicitly approve, modify and approve, or reject `memory_semantic_duplicate_acceptance_v1_recommended`. Approval would select only the review requirements; representative corpus creation/review, the missing exact artifact row, batched evaluator implementation, measurements, and any later behavior-changing decision would remain separate work.
- Evidence boundary: this is no-device/static review-contract evidence only. It does not supply a representative corpus, approve labels or floors, run a representative model matrix, validate production model quality, change a threshold, enable automatic merge, mutate memory, change protocol behavior, prove physical Android, optical QR, production relay/P2P, ICE/STUN/TURN, NAT traversal, or real-network behavior.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark is excluded.

## v0.3 Review-Only Semantic Memory Threshold Calibration Foundation

- Date: 2026-07-14.
- Status: implemented as a non-protocol, non-mutating evaluation foundation. It adds no runtime message, capability, Android state, automatic threshold change, or memory merge/edit/delete path. The Android review default remains exactly 9,000 basis points.
- Corpus contract: `shared/evaluation/memory-semantic-duplicate-calibration-v1.json` is a SHA-256-pinned five-language synthetic corpus with ten bounded entries, fourteen canonical labeled pairs, exact offline vectors, a non-transitive chain, and four complete-link review clusters. Its current SHA-256 is `d41a31045a5a4d35ad8ce4ee05af34fc0937326b114a1512fb1160be75b571ff`.
- Deterministic evaluator: Swift reuses the production normalization, nearest-away-from-zero cosine basis-point scoring, byte-exact exclusion, and complete-link implementation. Swift and an independent Python evaluator sweep every integer threshold from 8,000 through 10,000, report confusion counts plus integer precision/recall/F1, select best F1 then precision then the highest threshold, and compare the default-threshold clusters with the labeled complete-link groups. The synthetic vectors produce best threshold 9,511 and perfect 9,000 review metrics; that validates evaluator parity, not model quality.
- Optional live result: `build/qa/memory-semantic-calibration-live-ollama-embeddinggemma-20260714.json` (SHA-256 `c733979b0c721fb32a11bd997c66789ce6a6003669d89be0eb91e155e5475544`) records one explicit loopback-only run for `ollama:embeddinggemma:latest` at the pre/post-stable observed artifact fingerprint `ollama-sha256:85462619ee721b466c5927d109d4cb765861907d5417b9109caebc4e614679f1`. Within the currently allowed 8,000...10,000 range, the best labeled-pair F1 is 4,444 at 8,073 with precision 10,000 and recall 2,857; at the unchanged 9,000 default it returns no positive pair and no review cluster. This result does not authorize lowering the wire threshold or changing defaults.
- Decision boundary: the fixed corpus is intentionally small and synthetic, and no product acceptance floor, target model matrix, or user-reviewed production label set is approved. A default or range change requires a separate versioned decision backed by broader representative labels and explicit precision/recall requirements. Automatic merge remains out of scope.
- Verification: five Swift calibration tests and seventeen network-free Python tests pass. The offline CLI emits a content/vector/endpoint-free report, rejects duplicate keys and bool/int/float type confusion, and keeps `default_threshold_changed=false`, `automatic_memory_mutation=false`, and `protocol_changed=false`. The optional live path accepts only literal `127.0.0.1`, exact installed Ollama model identity, a lowercase 64-hex artifact digest, and embedding capability before one bounded `/api/embed` call; one shared monotonic deadline covers connection, response, and provider JSON parsing work, and a changed post-embed model digest fails closed.
- Review and aggregate verification: the independent Swift GPT-5.6 Sol review reports no P0-P3 findings. The Python/gate review found stale pre-embed digest attribution, per-request rather than total timeout, and a post-read parsing deadline gap; pre/post digest validation, one deadline with in-flight response closure, post-parse recheck, and three regressions remediate them, and final re-review reports no findings. `build/qa/check-no-device-quality-v03-semantic-memory-threshold-calibration-final-reviewed-20260714.log` exits 0 across 10,122 lines with `No-device quality checks passed.`, the calibration addendum, 45 selected Swift tests, 17 Python tests, Android XML totals of 115 protocol and 661 app tests with zero failures/errors/skips, 52 local-relay matches, and 859 encrypted frame bodies.
- Evidence boundary: deterministic offline evidence proves evaluator and fixture behavior only. The separate live report proves one local Ollama artifact on fourteen synthetic labeled pairs; it does not establish general model quality, a calibrated production threshold, physical Android behavior, optical QR, external networking, production relay/P2P, ICE/STUN/TURN, NAT traversal, or automatic memory safety.
- Network boundary: the aggregate validates all four controlled-spike recommendations only as approved for bounded Phase A. Socket execution, network I/O and measurement, Phase B, production networking, and deployment remain closed.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark is excluded.

## v0.3 Review-Only Semantic Memory Duplicate Clusters

- Date: 2026-07-14.
- Status: implemented across the shared schema, macOS host, and Android client/UI. Focused and aggregate no-device verification pass, the direct authenticated smoke passes, and independent macOS/Android GPT-5.6 Sol final re-reviews report no P0-P3 findings. The separate `memory.semantic_duplicate_clusters.v1` capability and `memory.semantic_duplicate_clusters.list` operation do not change the existing exact or semantic-pair operations.
- Contract: authenticated clients provide one provider-qualified installed runtime-local embedding model ID and an exact integer 8000...10000 similarity threshold. The closed response contains only `clusters`, `scanned_count`, `omitted_count`, and `truncated`; every cluster contains 2...200 canonical unique entry IDs plus its minimum pairwise basis-point score. Responses contain at most 100 disjoint clusters, scan at most 200 entries, and cap aggregate returned ID bytes at 128 KiB.
- Algorithm: macOS reuses the bounded semantic candidate, embedding, cache, model-authority, trust, source, authentication, and memory-mutation publication leases. Deterministic complete-link agglomeration requires every pair in a returned cluster to meet the threshold, excludes byte-identical content edges, orders merge ties by canonical unsigned UTF-8 ID arrays, omits singletons, and never publishes a chain whose endpoints fall below the threshold.
- Client boundary: Android keeps cluster requests and transient results independent from pair suggestions. Availability requires a current-authority unqueried memory list and a selected canonical installed local embedding model; responses must match the exact channel, connection generation, authority generation, model, and threshold. Unknown IDs or metadata, repeated IDs across clusters, noncanonical order, low scores, stale responses, and stale namespaced errors fail closed. No cluster state is persisted.
- Review surface: Settings > Memory presents a distinct model-dependent, review-only cluster scan with manual threshold control and existing explicit memory-row actions. It adds no automatic merge, edit, toggle, delete, lexical fallback, persistence, or cancel operation.
- Current verification: the focused macOS selector passes 62 tests with zero failures, including complete-link chain rejection, deterministic ordering, cancellation, response bounds, authentication/capability closure, model/source drift, cache lock ordering, batch byte ceilings, and final publication leases. Android Studio JBR runs 5 protocol plus 11 ViewModel/navigation/Compose cluster regressions with zero failures/errors/skips, including current-authority model-catalog correlation and superseded model-list send-failure isolation. The aggregate Android XML reports 115 protocol and 661 selected app tests with zero failures/errors/skips. The direct authenticated RuntimeDevServer smoke, schema, localization parity, copy hygiene, shell/Python/Swift syntax, P2P/NAT and relay design validators, and `git diff --check` pass.
- Aggregate verification: `build/qa/check-no-device-quality-v03-semantic-memory-duplicate-clusters-final-reviewed-20260714.log` records exit status 0 across 10,104 lines, `No-device quality checks passed.`, both cluster addenda, 52 fresh local-relay matches, and 859 encrypted frame bodies. The same run validates all four controlled-spike recommendations only for bounded Phase A while keeping `handoff-v4`, socket execution, network measurement, Phase B, and production gates closed.
- Evidence boundary: current evidence is no-device SwiftPM/deterministic mock and Android JVM/fake-channel/Robolectric/Compose only. It does not validate live embedding-model quality or threshold calibration, physical Android UI, optical QR, production relay/P2P, ICE/STUN/TURN, NAT traversal, or real-network behavior.
- Network boundary: all four controlled-spike recommendations remain approved only for bounded Phase A work. `handoff-v4`, socket execution, network measurement, Phase B, and production network/deployment gates remain closed.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark is excluded.

## v0.3 Review-Only Semantic Memory Duplicate Suggestions

- Date: 2026-07-14.
- Status: implemented; focused and aggregate no-device verification pass, and independent Android/macOS GPT-5.6 Sol final re-reviews report no P0-P3 findings. Authenticated Android clients advertise the separate `memory.semantic_duplicate_suggestions.v1` capability and may request `memory.semantic_duplicate_suggestions.list` without changing exact `memory.duplicate_suggestions.v1`.
- Host boundary: macOS reads at most 8 MiB of the authenticated owner's event log, considers the latest 200 persisted entries, requires each full trimmed content value to fit the selected installed runtime-local embedding model, caps selected content at 1 MiB, batches at 64 documents and 262,144 UTF-8 bytes, limits vectors to 65,536 dimensions, excludes byte-exact pairs, returns at most 100 deterministic non-transitive pairs, and caps response IDs at 128 KiB. Weak model revisions run on demand as one batch; strong fingerprints use owner/model/document/source-revision-bound cache keys. Final publication coordinates an atomic trust snapshot, canonical per-model runtime-observed descriptor generation, source identity, authentication, and runtime-owned memory mutations. Failed model lookups are not retained and valid observed model states cap at 256.
- Client boundary: Android requires a current-authority unqueried `memory.list` plus a selected installed runtime-host-local embedding model. Requests correlate channel, connection generation, authority generation, exact model ID, and an integer 8000...10000 threshold. Responses are closed to pair IDs, integer basis-point scores, scanned/omitted counts, and truncation; below-threshold scores, unknown IDs, unknown metadata, stale responses, and stale namespaced errors fail closed. Unsupported semantic operations disable only this capability for the current authority.
- Review surface: Settings > Memory keeps exact and possible-similarity review sections distinct, provides an exact 1-basis-point 80.00...100.00 threshold slider, and renders current memory rows with existing manual enable/disable and delete controls. Semantic state remains transient and is cleared by a new semantic scan, model change, memory mutation, authoritative refresh, disconnect, authentication loss, or channel replacement. No automatic merge, edit, toggle, delete, lexical fallback, or first-version cancel operation is added.
- Focused verification: 12 pure Swift suggestion tests, 15 Swift router tests, three trusted-store tests, and one strict wire-number-kind codec test pass. Eight Android protocol tests, nine ViewModel tests, and four navigation/Compose tests pass using Android Studio JBR. Full Android XML reports 137 protocol and 939 app tests with zero failures/errors. The authenticated deterministic RuntimeDevServer smoke passes, including integral-float rejection and before/after no-mutation proof. Schema validation, localization parity, copy hygiene, shell syntax, and `git diff --check` pass.
- Aggregate verification: `build/qa/check-no-device-quality-v03-semantic-memory-duplicate-suggestions-final-reviewed-20260714.log` records exit status 0 across 9,906 lines, `No-device quality checks passed.`, the authenticated and general review-only semantic duplicate addenda, 51 fresh relay connections, and 827 encrypted frame bodies. The same run validates all four controlled-spike recommendations as approved for Phase A while keeping `handoff-v4`, socket execution, network measurement, Phase B, and production gates closed.
- Evidence boundary: current evidence is no-device SwiftPM, deterministic mock embedding, Android JVM/fake-channel, and Robolectric/Compose only. It does not validate live embedding-model quality, model calibration, physical Android UI, optical QR, production relay/P2P, ICE/STUN/TURN, NAT traversal, or real-network behavior.
- Agent state: implementation and accepted focused work use GPT-5.6 Sol only; GPT-5.3-Codex-Spark is excluded.

## v0.3 Review-Only Exact Memory Duplicate Suggestions

- Date: 2026-07-14.
- Status: implemented; focused and aggregate no-device verification pass. Authenticated Android clients advertise `memory.duplicate_suggestions.v1` and may request the owner-scoped `memory.duplicate_suggestions.list` review operation.
- Host boundary: macOS deterministically orders IDs by unsigned UTF-8 bytes, considers at most the latest 200 authenticated-owner entries, groups only byte-exact stored UTF-8 content, includes enabled and disabled entries, and returns only `entry_ids`, `scanned_count`, and `truncated`. The production JSONL operation reads at most 8 MiB of event-log input, caps selected content at 1 MiB and returned ID bytes at 128 KiB, and rechecks the exact authenticated session plus trusted public key after storage work. Trust removal, same-ID key replacement, or a resource-limit breach fails closed without an ID response. It performs no case folding, whitespace normalization, Unicode normalization, tokenization, embedding, model call, merge, edit, toggle, or delete.
- Client boundary: Android exposes the action only after a current-authority unqueried `memory.list`; queried search results cannot grant availability. It accepts only the exact pending request on the current channel, connection generation, and authentication authority, and uses a dedicated request-ID namespace plus bounded closed correlations so every noncurrent scan error is discarded before global authentication handling even after history eviction. It disables the feature for the current authority on correlated `unknown_message_type` or `unsupported_operation`, enforces the shared 128 KiB aggregate UTF-8 ID budget and canonical ordering, and rejects unknown metadata, malformed/duplicate IDs, cross-group ID reuse, count overflow, and IDs absent from the current authoritative memory list. Results stay in transient `RuntimeUiState` and are cleared by a new scan, authoritative memory refresh, memory mutation, disconnect, authentication loss, or connection replacement.
- Review surface: Settings > Memory exposes a localized exact-duplicate scan and renders matching current memory rows with the existing explicit manual controls. Empty and truncated results are explicit; no automatic memory mutation is introduced.
- Focused verification: Swift `DuplicateSuggestions` runs 10 tests, Android protocol runs 6 focused tests, and Android ViewModel/navigation/Compose runs 9 focused tests, all with zero failures, errors, or skips. The complete Android protocol class also passes 102 tests and the complete ViewModel class passes 478. The direct authenticated `RuntimeDevServer` smoke passes with unauthenticated, non-empty-request, closed-response, non-disclosure, and explicit-cleanup coverage. Protocol schema validation and `git diff --check` pass.
- Aggregate verification: `build/qa/check-no-device-quality-v03-exact-memory-duplicate-suggestions-final-reviewed-20260714.log` has 9,491 lines and exits 0 with `No-device quality checks passed.`, 10 Swift duplicate-suggestion tests, 6 Android protocol tests, 9 Android ViewModel/navigation/Compose tests, the authenticated smoke and aggregate addenda, 49 fresh relay connections, and 771 encrypted frame bodies. All four bounded Phase A controlled-spike approvals remain validated with the socket gate closed. Final GPT-5.6 Sol macOS and Android re-reviews report no P0-P3 findings.
- Next action: semantic similarity clustering and the non-mutating calibration foundation are implemented. Define a representative reviewed label corpus, target model/artifact matrix, and explicit precision/recall acceptance floors before any default/range change or automatic merge policy.
- Evidence boundary: no-device macOS SwiftPM/router/storage and Android JVM/fake-channel/Compose evidence only. It does not prove semantic clustering, live embedding or chat-model quality, physical Android interaction, optical QR, production relay/P2P, ICE/STUN/TURN, NAT traversal, or real-network behavior.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark was not used.

## v0.2 Runtime-Authoritative Cross-Platform Wire Transcript Addendum

- Date: 2026-07-14.
- Contract: [chat-sessions-authoritative-sync-smoke-v1.json](../shared/protocol/fixtures/chat-sessions-authoritative-sync-smoke-v1.json) now carries an exact two-session payload transcript in addition to the separate 201-session lifecycle stress metadata. The macOS router emits the exact active pages, archive acknowledgement, archived pages, delete acknowledgement, and final empty page; only the secret HMAC cursor material and runtime timestamps are replaced with bounded non-secret representatives before exact comparison. Android injects those committed `JsonObject` payloads directly into its decoder and state machine without reconstructing them from a test helper.
- Lifecycle stress: the same fixture separately drives 201 deterministic sessions through 100/100/1 pagination, cursor-only continuation, two 200-row archive batches, archived reconciliation, two delete batches, terminal-only Android publication, and final empty reconciliation. This verifies bounded lifecycle behavior but is not described as an exact host-to-client payload transcript.
- Durable gate: the default no-device gate runs both Swift fixture tests plus the complete Android `RuntimeClientViewModelTest` class. Copy hygiene pins the fixture bytes by SHA-256, rejects duplicate JSON names and exact-type drift, preserves the Android class registration, requires direct fixture payload consumption, and keeps the documentation markers aligned.
- Focused verification: both exact-transcript tests and both 201-session lifecycle tests pass. The expanded selected Android app set contains 634 tests (471 ViewModel, 10 mutation-failure, and 153 navigation), and the direct Swift authoritative selector contains 21 tests, all with zero skips, failures, or errors.
- Aggregate verification: `build/qa/check-no-device-quality-v02-authoritative-wire-transcript-final-reviewed-20260714.log` has 9,412 lines and exits 0 with `No-device quality checks passed.`, the 21-test Swift selector, 634 selected Android app tests, 761 encrypted local-relay frame bodies, the cross-platform wire transcript addendum, all four bounded Phase A approvals, and the socket gate closed.
- Review remediation: GPT-5.6 Sol identified helper-generated payloads, unpinned Android gate registration, permissive fixture parsing, timestamp normalization that could hide invalid wire values, substring-only command checks, and text-normalized hashing as P2/P3 evidence gaps. Exact payload consumption, canonical timestamp validation, raw-byte hashing, strict JSON checks, and parsed/exact executable gate lines address them. The final non-delegating GPT-5.6 Sol-only re-review reports no P0-P3 findings.
- Evidence boundary: no-device macOS SwiftPM/router/storage and Android JVM/fake-channel evidence only. It does not prove physical Android behavior, optical QR, live-provider behavior, production relay/P2P, ICE/STUN/TURN, NAT traversal, or real-network behavior.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark was not used for this addendum.

## v0.2 Runtime-Authoritative Session Pagination And Bulk Lifecycle

- Date: 2026-07-14.
- Status: implemented and final aggregate no-device verification passed. Capability `chat.sessions.authoritative_sync.v1` upgrades `chat.sessions.list` to a complete runtime-authoritative snapshot without changing the legacy one-page response. Initial requests use the existing filters with a capable page size of 1 through 200; continuation requests are cursor-only. Capable pages add `snapshot_count` and optional `next_cursor`, while legacy peers keep the `sessions`-only response.
- Host boundary: macOS materializes at most 10,001 rows to detect the 10,000-session ceiling without truncation. HMAC cursors bind the random snapshot id, connection, normalized owner, search mode and filters, page size, snapshot count, offset, and expiry. Snapshots expire after 120 monotonic seconds while retaining a signed wall-clock expiry, are limited to one per connection and eight globally, and are invalidated on connection close, authentication challenge/cleanup, rename, or lifecycle mutation. Owner lifecycle, connection authentication, and latest initial-request generations are checked after semantic or lexical materialization, preventing reauthentication races and an older slow request from evicting a newer accepted snapshot.
- Android boundary: the client accumulates pages privately and publishes or persists only after terminal validation. It rejects duplicate session ids, cursor loops, count drift, empty nonterminal pages, final count mismatch, more than 100 pages, stale channels, stale authority generations, and a legacy response after authoritative support was established. A downgrade preserves the prior cache and disables bulk authority until a fresh unqueried capable snapshot completes. Refresh supersedes an in-flight list, reconnect or authentication loss clears the run while retaining the previous authoritative cache, and list/transcript send failures clear only their matching current operation while stale failures cannot revoke newer authority.
- Bulk boundary: capable archive uses `scope=all_active`; capable delete uses `scope=all_archived`; restore has no bulk form. The host selects deterministic owner-scoped batches of at most 200 and commits each batch atomically. Delete passes exact target ids to compaction-summary purge before commit, SQLite rolls back the full batch, and JSONL replaces the event log atomically. Android uses a fresh request id for each acknowledged batch, caps work at 50 batches and 10,000 affected rows, performs no optimistic runtime-owned bulk mutation, and requires authoritative reconciliation after malformed, lost, or error acknowledgements without automatic retry. Legacy remote and local-only offline flows remain available.
- Focused verification: Android protocol runs 96 tests; the selected Android app classes run 632 tests (469 ViewModel, 10 mutation-failure, and 153 navigation); the direct no-device Swift authoritative selector runs 19 tests; and all 55 `SQLiteRuntimeChatEventStoreTests` pass with zero failures, errors, or skips. Protocol schema, copy hygiene, and docs hygiene also pass.
- Review remediation: the first GPT-5.6 Sol review found same-connection reauthentication authority, slow-old-initial eviction, authoritative-to-legacy downgrade, cross-cancelling history send failure, and wall-clock rollback TTL gaps. A second independent review found authentication accepted from a challenge superseded during an awaited trust lookup, lifecycle mutations committing after authority or capability changed, downgrade quarantine falling back to legacy runtime-owned bulk actions, and delayed closed history errors revoking newer authority. Later split reviews found current request-id reuse masking, development mutation after connection closure, bounded closed-correlation eviction, malformed stale-error UI mutation, current malformed transcript errors retaining pending state, and unbounded closed-connection UUID tombstones. Subsequent reviews found rename authority drift, lifecycle cleanup before request cancellation, authentication/history request-ID collision, the pre-registration task-start window, and active backend generation cancellation racing task teardown. Rename captures and revalidates exact owner/authentication authority; pending authentication errors take precedence over stale-history filtering; request dispatch waits for registration; and close claims backend generations, cancels tracked tasks, then clears lifecycle authority. Owner-switch, development-close, pre-registration-close, explicit backend-cancel, and prefixed-authentication regressions pass. The fresh final non-delegating GPT-5.6 Sol-only re-review reports no P0-P3 findings; a reviewer result that delegated to Spark remains excluded.
- Aggregate verification: `build/qa/check-no-device-quality-v02-authoritative-session-sync-final-reviewed-20260714.log` has 9,410 lines and exits 0 with `No-device quality checks passed.`, 55 passing SQLite tests, the 19-test authoritative selector, 761 encrypted local-relay frame bodies, the runtime-authoritative session addendum, four bounded Phase A controlled-spike approvals, and the socket gate closed.
- Next action: continue the next unblocked roadmap slice. Production P2P/NAT Phase A source audit and actual libjuice/NDK compilation still require reviewed offline source plus a pinned offline Android NDK; socket and network execution remain separately closed.
- Evidence boundary: no-device Android JVM/fake-channel and macOS SwiftPM/JSONL/SQLite evidence only. This does not prove physical Android interaction, optical QR, live-provider behavior, production relay/P2P, ICE/STUN/TURN, NAT traversal, or real-network behavior.
- Agent state: accepted review evidence uses GPT-5.6 Sol only. One intermediate Sol reviewer delegated to GPT-5.3-Codex-Spark against the session instruction; that result is excluded and a non-delegating Sol-only final review is required.

## v0.2 Deterministic Session Search And Search-Only Sync Polish

- Date: 2026-07-14.
- Android sync boundary: an authenticated runtime query may return an older matching session outside the normal 100-row full-history cache. The client now retains only the current validated query summaries, promotes exactly the selected search-only session into the in-memory runtime cache, preserves every existing full-history row, and requests that session's `chat.messages.list` transcript instead of navigating with `chat_session_not_found`.
- Storage boundary: promotion accepts only a summary from the exact pending authenticated search response, honors deleted-session suppression, and clears pending history plus visible/internal search authority on connection replacement, receive failure, request-specific authentication loss, route expiry, disconnect, or an unqueried authoritative refresh. The same revocation seam invalidates title/lifecycle/rename acknowledgements and reverses pending optimistic mutations in dispatch-reverse order, preventing a delete tombstone from suppressing later authoritative sync. Lifecycle/rename acknowledgements must match the journaled request, session, and lifecycle operation; malformed or mismatched success rolls back and refreshes instead of retaining optimistic authority. Mutations targeting one session are serialized, rename rollback restores the exact prior ordering timestamp, and both success and failure supersede any older search/list request with a fresh unqueried full refresh. Old-channel responses and delayed old-channel send failures remain rejected after replacement. A promoted summary and its visible result row are consumed once so later archive/restore/delete state cannot be overwritten or exposed through stale search metadata. A remote summary whose id collides with a local-only session is excluded fail closed so the local title and transcript cannot be replaced or targeted as remote authority. Rank/snippet/matched-field metadata is removed before full-cache publication, and runtime-owned transcript bodies plus transient search metadata remain excluded from device persistence by the existing redaction path.
- Deterministic ordering: JSONL/base session lists now order by `lastActivityAt DESC, sessionID ASC`. JSONL and SQLite lexical results order by `score DESC, lastActivityAt DESC, sessionID ASC` before `limit`, matching the existing semantic-search total-order rule and preventing equal-score/equal-time rank drift after reopen.
- Focused verification: all 446 Android `RuntimeClientViewModelTest` tests pass, including uncached authoritative-result open/transcript loading, completed-response replay rejection, stale old-channel response, and delayed revoked-session/completed-request/completed-pairing-or-hello send-failure rejection, receive-failure/connection-replacement/history-and-memory-authentication-loss/route-expiry authority revocation, cross-session archive/delete rollback with late-ack rejection, mutation-failure rollback plus stale pending-search supersession, replacement-channel fresh history dispatch, visible-row/summary one-shot consumption across lifecycle actions, local-only identity-collision preservation, and existing transient-search/full-cache tests. All 10 `RuntimeClientChatSessionMutationFailureTest` tests pass, including ACK/session/operation binding, malformed ACK rollback, same-session serialization, exact rename timestamp restoration, and pre-mutation-list supersession. All 51 `SQLiteRuntimeChatEventStoreTests` pass, including reverse-insertion, `limit: 1`, JSONL, SQLite-reopen, FTS, and same-timestamp regressions.
- Aggregate verification: `build/qa/check-no-device-quality-v02-session-search-sync-final-reviewed-r2-20260714.log` has 9,214 lines and exits 0 with `No-device quality checks passed.`, 51 passing SQLite tests, 761 encrypted relay frame bodies, the runtime session search addendum, all four bounded Phase A controlled-spike approvals, and the socket gate closed. Final GPT-5.6 Sol re-review reports no P0-P3 findings.
- Historical next action: explicit pagination/cursors and runtime-authoritative bulk archive/delete were implemented by the later `Runtime-Authoritative Session Pagination And Bulk Lifecycle` slice above. Physical Android UI proof and P2P/NAT Phase A source/NDK work remain separate boundaries.
- Evidence boundary: no-device Android JVM/fake-channel and macOS SwiftPM/JSONL/SQLite evidence only. This does not prove physical Android interaction, live-provider search quality, production relay/P2P, optical QR, or real-network behavior.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark was not used.

## macOS Runtime Chat Retention Production Ownership

- Date: 2026-07-13.
- Status: the existing 90-day/100-session SQLite deleted-chat retention seam is now owned by the production macOS app instead of remaining test-only. `CompanionAppModel.start()` schedules immediate utility-priority maintenance and repeats it every 24 hours while the model lives; the Runtime History Inspector exposes the same operation with localized running, completion, empty, and failure states.
- Scope: each store transaction selects at most 100 candidates through metadata-only window SQL across legacy nil-owner and every device-owner scope, ordered by oldest deletion then deterministic owner/session tie-breaking. One maintenance request repeats bounded 100-session SQL batches until the current eligible backlog is empty; existing owner-scoped maintenance remains available and unchanged.
- Safety boundary: only sessions whose latest lifecycle event is `deleted` and older than 90 days are physically removed. Active, archived, recent-deleted, and same-session-id rows owned by another device remain isolated; owner/session tombstones still prevent resurrection, targeted FTS deletion avoids a full-history rebuild, and one post-drain atomic legacy JSONL compaction removes tombstoned transcript lines while preserving later non-tombstoned backfill. Current JSONL writers and the compactor share canonical-path in-process locking plus a 0600 sidecar POSIX record lock across processes; a pre-lock-protocol app version must be stopped before migration because it cannot participate in that coordination.
- Host control: Runtime History Inspector shows the fixed retention policy and a `Clean Deleted History` action. The button is disabled while maintenance is running, publishes only the content-free prune count, and keeps raw store errors in local Activity. Physical deletion does not rescan runtime summaries on the main actor because deleted sessions were already excluded from visible history before retention.
- Focused verification: 49 SQLite store tests plus the app-model 105-session multi-batch regression, no-summary-rescan regression, weak-model lifetime regression, five-language localization regression, and all-language/all-appearance Runtime History Inspector render regression pass (54 selected tests total). The race regression is cross-instance in one process; process coordination and active child cancellation are code-review/static boundaries, not separately executed process/cancellation tests.
- Review result: GPT-5.6 Sol found legacy JSONL transcript retention, one-shot scheduling/backlog truncation, all-event decode/full FTS rebuild work, concurrent append replacement loss, repeated full legacy compaction, detached-task cancellation gaps, and a main-actor full-history refresh. The remediation adds coordinated post-drain legacy compaction, 24-hour scheduling, structured cancellation, backlog draining, bounded metadata SQL, targeted FTS deletion, and content-free completion without a main-actor store rescan; focused verification passes after those fixes. A single legacy migration/compaction remains proportional to the legacy file itself rather than to the SQLite event corpus.
- Aggregate verification: `build/qa/check-no-device-quality-macos-runtime-chat-retention-production-ownership-final-reviewed-20260714.log` has 9,185 lines and exits 0 with `No-device quality checks passed.`, 49 passing SQLite tests, the app-model no-summary-rescan regression, 761 encrypted relay frame bodies, the runtime chat retention addendum, four bounded Phase A controlled-spike approvals, and the socket gate closed.
- Next action: continue v0.2 session search and sync polish. Provider-tokenizer parity and broader compaction calibration remain separate; production P2P/NAT Phase A still requires reviewed offline libjuice source and an offline pinned Android NDK before source-audit or compile-only evidence can continue.
- Evidence boundary: no-device macOS SwiftPM/storage/model/localization/render evidence only. This does not prove physical Android history UI, optical QR, live-provider chat, production relay/P2P, real-network behavior, or the blocked libjuice/NDK compile path.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark was not used.

## Production P2P/NAT Phase A Offline Source And Compile Boundary (No Source, No Compilation)

- Date: 2026-07-13.
- Source-intake contract: [offline-source-intake-v1.json](security-hardening/production-p2p-nat-v1/controlled-network-spike/phase-a/offline-source-intake-v1.json) fixes `build/offline-source/libjuice-1.7.2` as the only offline intake root and records `libjuice_supply_chain_and_source_audit=blocked_missing_offline_source`. The root is absent; tag, commit, archive, tree, and file hashes remain null and no audit completion is claimed.
- Fail-closed intake: an unexpected file, directory, or symlink at that root is rejected until a separate reviewed versioned manifest fixes exact provenance, original archive and extracted tree digests, license files, generated files, dependency closure, build flags, and bounded file inventory. The repo root and existing intake ancestors must be owner-matched, non-symlink directories without group/world write permission, and root absence is rechecked immediately before success. Official source URLs are provenance metadata only and are never fetched by this gate.
- Compile boundary: [libjuice-compile-only-contract-v1.json](security-hardening/production-p2p-nat-v1/controlled-network-spike/phase-a/libjuice-compile-only-contract-v1.json) records `android_macos_compile_only_integration=blocked_missing_reviewed_source`, `executionStatus=not_executed`, and absent evidence. It defines future direct `-c` plus static-archive proof for Android minSdk 26 `arm64-v8a`/`x86_64` and macOS 14.0 `arm64`/`x86_64`, but creates no header, adapter, native module, Gradle/SwiftPM wiring, executable, or compile result.
- ABI floor: a future reviewed adapter must use opaque handles, fixed-width integers, explicit-length buffers, numeric endpoints, explicit allocator ownership, bounded numeric errors, hidden-by-default symbols, and fixed callback, cancellation, and teardown rules. It must not accept `routeToken` as route, endpoint, ICE, STUN, TURN, transcript, key, allowlist, or application authority.
- Toolchain snapshot: on 2026-07-13 Apple clang was observed locally but not invoked, while Android NDK/CMake was not observed or pinned. The static contract does not revalidate that dated environment snapshot. Regardless of later tool installation, no compile command can be authorized or claimed until exact reviewed source, compiler, SDK, source-list, define, object, archive, and symbol hashes exist.
- Durable gate: before any Phase A validator can execute or be imported, the security-design preflight hash-pins 19 files and applies exact import/from-import allowlists plus dynamic, process, native-load, archive, file-write, network, and socket call denial. The default no-device gate then runs the strict offline-source and compile-boundary validators plus 37 mutation tests before the existing crypto and static-harness checks; copy hygiene fixes the executable command order and concrete bypass regressions.
- Review result: independent GPT-5.6 Sol review found execution-after-import AST gaps, private-module/archive/file-write and alias-import bypasses, incomplete ancestor metadata, stale current-environment wording, and variable-name-based `Path.replace` bypass. The fixes passed focused validation, and the final re-review reports no P0-P3 findings.
- Aggregate verification: `build/qa/check-no-device-quality-p2p-controlled-spike-phase-a-source-compile-boundary-final-reviewed-20260713.log` records exit status 0, `No-device quality checks passed.`, 19 offline-source tests, 18 compile-only tests, the 19-file preflight, 48 fresh relay connections, 761 encrypted relay frame bodies, and the offline-source/compile-boundary addendum.
- Next action: place an explicitly reviewed offline libjuice source package only in the fixed intake root, publish a new versioned pinned manifest, complete the line-referenced supply-chain/source audit, then install and pin an offline Android NDK before collecting actual compile-only evidence. A separate versioned decision remains mandatory before any socket or network execution.
- Evidence boundary: no-device/static blocked-state validation only. This does not prove source provenance, source audit completion, compilation, C ABI compatibility, library execution, ICE/STUN/TURN, NAT traversal, physical Android, optical QR, live network, measurement, deployment, or production readiness.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark was not used.

## Production P2P/NAT Phase A Crypto And Static Policy Evidence (No Sockets)

- Date: 2026-07-13.
- Completed evidence: [production-p2p-nat-v1-session-crypto-vectors.json](../shared/protocol/fixtures/production-p2p-nat-v1-session-crypto-vectors.json) is the shared direct/relay ALP1 fixture. Swift CryptoKit, provider-neutral Android JCA, and `script/check_p2p_nat_session_crypto_vectors.py` agree on P-256 ECDH, 32-byte leading-zero normalization, transcript-bound HKDF-SHA-256 key separation, role-bound bidirectional confirmation, and directional AES-256-GCM nonce/AAD/ciphertext/tag values.
- Negative evidence: the fixture scopes provider failure to Android and both platform suites execute their applicable malformed/off-curve key, invalid scalar, transcript/generation substitution, role reflection, replay/nonce reuse, modified-tag, incomplete-confirmation, single-use ephemeral derivation, key-owned one-shot cipher issuance across duplicate handshakes, concurrent sequence, and exhausted-counter cases. `script/test_p2p_nat_session_crypto_vectors.py` mutation-checks the fixture, exact scalar types, independent ALP1 oracle, source network/dynamic-execution ban, and Android named-provider ban.
- Static harness evidence: [static-harness-egress-policy-v1.json](security-hardening/production-p2p-nat-v1/controlled-network-spike/phase-a/static-harness-egress-policy-v1.json) is `static_design_complete`, `executionStatus=not_executed`, and `measurementStatus=not_started`. It hash-pins `review-v1`, `decision-v1`, and `handoff-v4`; fixes `agent_a`, `agent_b`, `stun_service`, and `turn_service`; allows only exact numeric UDP tuples for the selected single-component regular-nomination profile; and records `retainedRuntimeEvents=[]`.
- Egress floor: DNS, DoH, DoT, environment proxy, redirect, wildcard, port range, malformed numeric input, loopback, link-local, broadcast, unlisted private, unspecified, multicast, and general external TCP/UDP IPv4/IPv6 egress mutations are denied. Policy drift requires exact process termination and no retained runtime event content. `script/test_p2p_nat_phase_a_harness_egress.py` mutation-checks these static invariants.
- Authorization boundary: `staticHarnessImplementationAuthorized=true` permits this non-executable artifact only. Source execution, socket creation, runtime or harness network I/O, controlled-spike network I/O, Phase B execution, measurement, production network I/O, and deployment remain false. No namespace, service, packet capture, or socket was executed.
- Reviewed result: multiple GPT-5.6 Sol rounds found nonce-lifecycle, API/type-confusion, mutable-key, negative-vector, dynamic-validator, UDP-egress, concurrency-evidence, and gate-order issues; all were fixed, and the final bounded crypto/static re-review reports no remaining P0-P3 findings.
- Aggregate verification: `build/qa/check-no-device-quality-p2p-controlled-spike-phase-a-crypto-static-policy-final-reviewed-20260713.log` records exit status 0, `No-device quality checks passed.`, the direct/relay crypto checkpoint, all eight Python crypto mutation groups, all 22 static harness/egress tests, 761 encrypted relay frame bodies, and the Phase A crypto/static-policy addendum.
- Incomplete evidence: `libjuice_supply_chain_and_source_audit` is `blocked_missing_offline_source`, and `android_macos_compile_only_integration` is `blocked_missing_reviewed_source`. No reviewed libjuice source exists in the workspace, and network acquisition remains prohibited, so neither source audit nor actual C ABI compilation is claimed. The final whole-Phase-A security review cannot close until those two groups exist; the review completed here is bounded to crypto/static evidence.
- Next action: provide reviewed offline libjuice source, then collect source-audit and actual Android/macOS C ABI compile-only evidence before the whole-Phase-A review. A separate versioned decision remains mandatory before any socket, network I/O, executable Phase B harness, measurement, or deployment.
- Evidence boundary: no-device/static cryptographic interoperability and policy evidence only. This does not prove libjuice behavior, C ABI compatibility, executable netns enforcement, packet capture, ICE/STUN/TURN traffic, NAT traversal, physical Android, optical QR, live-network behavior, performance, deployment, or production readiness.

## Production P2P/NAT Controlled-Spike Phase A Approved (No Sockets)

- Date: 2026-07-13.
- Approval: [controlled-network-spike/decision-v1.json](security-hardening/production-p2p-nat-v1/controlled-network-spike/decision-v1.json) records `explicit_user_instruction` for all four recommendations in canonical order. Because the review's required source, compile, cryptographic, harness, and egress evidence is not complete, each option is `approved_for_bounded_phase_a_evidence`, not production-final or measured.
- Handoff: [handoff-v4.json](security-hardening/production-p2p-nat-v1/implementation/handoff-v4.json) supersedes `handoff-v3`, preserves the two completed no-network packages and all seven pre-network decisions, and authorizes only offline inspection/pinning of user-provided or pre-existing workspace libjuice source, Android/macOS compile-only integration, transport-neutral session-cryptography vectors, and static phase A harness/egress policy work.
- Selected phase A set: `libjuice-1.7.2-static-c-abi`, `platform-native-p256-hkdf-sha256-aes256gcm`, `linux-netns-twin-agent-local-services`, and `numeric-endpoint-allowlist-plus-os-egress-witness`.
- Closed execution boundary: network source acquisition and inspected dependency execution are prohibited; `sourceAcquisitionNetworkIOAllowed=false`, `controlledSpikeNetworkIOAllowed=false`, `controlledSpikeSocketExecutionAuthorized=false`, `phaseBExecutionAuthorized=false`, and `productionDeploymentAuthorized=false`. STUN/TURN/ICE traffic and measurement remain prohibited, `productionDesignStatus=not_implemented`, and `route.refresh` remains the only active traversal namespace.
- Durable gate: the controlled-spike validator keeps the historical review and `handoff-v3` hashes fixed, then validates the new decision and `handoff-v4`. All 17 mutation tests reject partial or reordered approval, implicit authority, source-chain drift, completed-evidence drift, offline-source or Phase A scope expansion, bool/int type confusion, Phase B/socket/network authorization, fabricated measurement, namespace expansion, mutable records, and Markdown claim drift. The independent security-design validator verifies the same current handoff boundary.
- Aggregate verification: `build/qa/check-no-device-quality-p2p-controlled-spike-phase-a-approval-final-reviewed-20260713.log` records exit status 0, `No-device quality checks passed.`, the four-option Phase A approval checkpoint, all 17 mutation tests, 48 fresh relay connections, 761 encrypted frame bodies, and the Phase A approval addendum. Final GPT-5.6 Sol re-review reports no remaining P0-P3 findings.
- Next action: collect all five phase A evidence groups. A separate versioned decision remains mandatory before any socket creation, controlled network I/O, phase B execution, measurement, or deployment.
- Evidence boundary: approval and no-device/static validation only. This does not prove source audit completion, compilation, ABI compatibility, cryptographic interoperability, an executable harness, ICE/STUN/TURN, NAT traversal, physical Android, optical QR, live network, performance, or production readiness.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark was not used.

## Production P2P/NAT Controlled-Spike Review (Historical Proposal)

- Date: 2026-07-12.
- Status: [controlled-network-spike/review-v1.json](security-hardening/production-p2p-nat-v1/controlled-network-spike/review-v1.json) is a closed `proposed_not_selected` review packet sourced from `handoff-v3`; it records four recommendations and zero selected decisions.
- Recommended set: `libjuice-1.7.2-static-c-abi` subject to exact source, regular-nomination, consent, TURN, parser, callback, and teardown audit; platform-native CryptoKit plus provider-neutral Android JCA for P-256/HKDF-SHA-256/AES-256-GCM; a two-phase compile-only then Linux-network-namespace harness; and exact numeric endpoint allowlists backed by an OS deny-all egress witness and packet-capture assertion.
- Compatibility boundary: Android minSdk 26 keeps ephemeral ECDH provider-neutral and in memory rather than depending on AndroidKeyStore API 31. The existing ALP1 transport-neutral transcript and application-readiness gate remain unchanged.
- Authorization boundary: `librarySelectionAuthorized=false`, `harnessImplementationAuthorized=false`, `networkIOAllowed=false`, `socketExecutionAuthorized=false`, `productionDeploymentAuthorized=false`, and `nextHandoffAuthorized=false`. No source acquisition, library integration, executable harness, socket, or new handoff is authorized.
- Durable gate: the strict controlled-spike validator hash-pins the closed review pair and source `handoff-v3`; 10 mutation tests reject duplicate names, missing, unknown, reordered, implicitly selected, option-drifted, source-drifted, weakened, fabricated-measurement, authorized, or mutable states. The default no-device gate executes both checks.
- Aggregate verification: `build/qa/check-no-device-quality-p2p-controlled-spike-review-final-reviewed-20260712.log` records exit status 0, `No-device quality checks passed.`, four proposed and zero selected recommendations, all 10 mutation tests, 48 fresh relay connections, 763 encrypted frame bodies, and the controlled-spike review addendum. Final GPT-5.6 Sol re-review reports no remaining P0-P3 findings.
- Historical next action: explicit approval was required. The newer `decision-v1` and `handoff-v4` complete that selection step for bounded phase A evidence only while every socket and network execution gate remains closed.
- Evidence boundary: official-source review and no-device static validation only. This does not download or compile a library, implement the harness, open a socket, exchange ICE/STUN/TURN traffic, prove NAT traversal, exercise physical Android, or establish live-network, performance, deployment, or production readiness.

## Production P2P/NAT Pre-Network Recommendations Approved (No Network)

- Date: 2026-07-12.
- Approval: [decision-v1.json](security-hardening/production-p2p-nat-v1/pre-network/decision-v1.json) records `explicit_user_instruction` and resolves all seven recommendations for `production_p2p_nat_v1_recommended` in canonical order.
- Handoff: [handoff-v3.json](security-hardening/production-p2p-nat-v1/implementation/handoff-v3.json) supersedes `handoff-v2`, preserves the completed canonical-contract and no-network-conformance evidence, and closes the policy-selection dependency.
- Selected set: first-party TLS 1.3 services with signed configuration; opaque 600-second generation capabilities; end-to-end limited-direct candidates; full ICE with regular nomination and consent; short-lived pair-scoped TURN; between-request cutover without automatic replay; and measured matrix hard-stop budgets.
- Authorization boundary: `networkIOAllowed=false`, `librarySelectionAuthorized=false`, `productionDeploymentAuthorized=false`, and `controlledNetworkSpikeSocketExecutionAuthorized=false`. `productionDesignStatus=not_implemented` and `route.refresh` remains the only active traversal-related namespace.
- Durable gate: the strict pre-network validator verifies the immutable proposal, approval decision, `handoff-v3`, every completed evidence SHA-256 including Android `P2pNatContract.kt`, and all four socket-blocking review IDs; 15 mutation tests reject duplicate JSON names, unknown fields, reordered or partial decisions, recommendation or evidence drift, weakened security floors, fabricated measurements, and unauthorized network/library/socket/deployment state. The no-network scan rejects socket-factory and Apple CFStream socket paths, the security-design validator independently verifies the complete canonical handoff closure, and the default no-device gate executes the Kotlin and Swift P2P/NAT contract and conformance suites.
- Aggregate verification: `build/qa/check-no-device-quality-p2p-pre-network-approval-final-reviewed-20260712.log` records exit status 0, `No-device quality checks passed.`, the seven-approved recommendation result, all 15 mutation tests, 48 fresh relay connections, 761 encrypted frame bodies, and the pre-network approval addendum. Final GPT-5.6 Sol re-review reports no remaining P0-P3 findings.
- Next action: separately review a concrete networking/session-cryptography library and isolated non-production harness, including destination and egress controls. A later versioned decision is still required before any socket execution.
- Evidence boundary: approval and no-device static validation only. This does not implement or prove a connector, ICE/STUN/TURN traffic, candidate exchange, NAT traversal, physical Android, optical QR, performance, battery, capacity, deployment, or production readiness.

## Production P2P/NAT Pre-Network Decision Review (Historical Proposal)

- Date: 2026-07-12.
- Status at publication: [review-v1.json](security-hardening/production-p2p-nat-v1/pre-network/review-v1.json) is the immutable `proposed_not_selected` source packet; all seven proposal rows retain `resolution=null` and `approvalSource=null`. The newer approval decision and `handoff-v3` supersede its pending action without mutating it.
- Decision-ready scope: the packet canonically orders service ownership/trust, pair capability/retention, candidate privacy/scope, ICE/consent, TURN credentials/abuse, request transition semantics, and release budgets. Each decision has three alternatives, one recommendation, unresolved approval inputs, fixed security floors, rejection conditions, and required pre-spike evidence.
- Recommended set: first-party TLS 1.3 services with signed configuration; opaque 600-second generation capabilities; end-to-end limited-direct candidates; full ICE with regular nomination and RFC 7675 consent; short-lived pair-scoped TURN; between-request cutover with in-flight failure and no automatic replay; and measured matrix hard-stop budgets.
- Durable gate: `script/check_p2p_nat_pre_network_review.py` validates the closed source decision/handoff, exact seven-decision schema, zero selected decisions, closed network/library/deployment/handoff gates, and fixed policy floors. `script/test_p2p_nat_pre_network_review.py` supplies one canonical positive test plus seven mutation groups covering missing/duplicate/unknown/reordered decisions, unauthorized resolution or authority, weakened security floors, and fabricated measured results.
- Aggregate verification: `build/qa/check-no-device-quality-p2p-pre-network-review-final-reviewed-20260712.log` records exit status 0, `No-device quality checks passed.`, the seven-proposed/zero-selected review result, eight review tests, 48 fresh relay connections, 763 encrypted frame bodies, and the pre-network review addendum. Final GPT-5.6 Sol re-review reports no remaining P0-P3 findings.
- Historical next action: explicit approval was required. The newer decision record completes that action while keeping `controlled-network-spike`, `networkIOAllowed=false`, and library selection separately gated.
- Evidence boundary: review and no-device static validation only. This does not implement or prove a connector, service, ICE/STUN/TURN, candidate exchange, consent traffic, NAT traversal, application traffic, physical Android, optical QR, latency, memory, battery, capacity, interoperability, deployment, or production readiness.

## Production P2P/NAT Approved Bounded Handoff (No Network)

- Date: 2026-07-12.
- Approval: `production_p2p_nat_v1_recommended` is `approved_for_bounded_handoff`; `implementationAuthorized=true` and `explicitSelectionRequired=false`. The choice combines `authenticated-encrypted-ice-turn` with `transport-neutral-identity-session`, requires `relay-only-sealed-signaling` rollback, and defers decentralized rendezvous, QUIC, and relay-first promotion.
- Completed scope: `handoff-v2` supersedes the initial dependency-gated `handoff-v1` and records `canonical-contracts` plus `no-network-conformance` completed. Kotlin and Swift implement the same five `ALP1` version 1 canonical objects, on-curve P-256 validation, frame/resource ceilings, validation-time-bound freshness, raw-byte candidate policy, pair-and-role replay state, and exact readiness/fallback ordering.
- Shared proof: [production-p2p-nat-v1-vectors.json](../shared/protocol/fixtures/production-p2p-nat-v1-vectors.json) carries seven positive vectors across all five object types plus nine shared negative vectors, transcript SHA-256, and client/runtime HMAC-SHA256. `script/check_p2p_nat_contract_vectors.py` independently regenerates and classifies them and rejects route-token variants or network APIs in the bounded source set.
- Authorization boundary: all packages keep `networkIOAllowed=false`; `controlled-network-spike` remains blocked on a separate review. `productionDesignStatus=not_implemented`, no production library or deployment is selected, and `route.refresh` remains the only active traversal-related protocol namespace.
- Pre-network gate: service ownership/trust, pair authorization/retention, candidate privacy/scope, ICE/consent, TURN credentials/abuse, application transition semantics, and measured release budgets remain open before any controlled socket work.
- Durable design evidence: [selection profile](security-hardening/production-p2p-nat-v1/selection-profile.md), [selection decision](security-hardening/production-p2p-nat-v1/selection-decision.json), and the versioned handoffs remain bound to the current 13-artifact collection SHA-256 `6e6dfbfc0cdb70370c30f54222584b69042a6e22b6df04c7f3e65043c38522bd`.
- Aggregate verification: `build/qa/check-no-device-quality-p2p-bounded-no-network-handoff-final-reviewed-20260712.log` records exit status 0, `No-device quality checks passed.`, seven positive and nine exactly classified negative vectors, 48 fresh relay connections, 761 encrypted frame bodies, and the bounded no-network handoff checkpoint. Final GPT-5.6 Sol re-review reports no remaining P0-P3 findings.
- Superseded next decision: the newer pre-network approval selects all seven recommendations and creates `handoff-v3`; controlled network execution still requires the separate library and isolated-harness review.
- Evidence boundary: no-device and no-network only. This does not prove a concrete connector, signaling service, STUN/TURN, candidate exchange, hole punching, NAT traversal, public-network behavior, physical Android, optical QR, latency, memory, CPU, battery, interoperability, deployment, or production readiness.

## Authenticated Historical Chat Source Attribution Review

- Date: 2026-07-12.
- Status: implemented and verified by the complete no-device gate.
- Wire boundary: add authenticated `chat.source_attribution.resolve` with exact request `{session_id, assistant_message_id, source_index}` and response `citation`, `review`, plus optional `trusted_source`. `assistant_message_id` is server-generated and non-authorizing, and appears only on attribution-bearing successful completion/history rows under `chat.source_attribution.resolve.v1`. `source_attributions` remains exactly the four safe display fields.
- Authorization boundary: atomically store the private binding fields `source_index`, `source_anchor_id`, `document_id`, and `source_revision` with the assistant terminal event; approval state and a separate chunk identifier are not binding fields. Resolve only canonical owner-scoped history, then atomically revalidate current `runtime_shared` approval and the exact historical revision before preparing review. Never infer authority from display metadata. Regenerated/deleted/legacy answers and stale, deleted, replaced, or revoked sources fail closed.
- Android boundary: attribution clicks reuse the existing source review dialog. The assistant locator may persist, but review/confirmation tokens and citation, grant, anchor, document, approval, or revision identifiers remain private transient state.
- Verification: focused Swift router/store, Android protocol/ViewModel/Compose, authenticated mock smoke, schema, copy hygiene, syntax, and full no-device selections passed. Capability omission and partial-capability response projection are router-unit evidence; live smoke uses the fully capable connection.
- Aggregate verification: `build/qa/check-no-device-quality-historical-source-attribution-review-final-reviewed-20260712.log` records exit status 0, `No-device quality checks passed.`, 48 fresh relay connections, 761 encrypted frame bodies, and the authenticated historical source-attribution review checkpoint in the complete no-device queue.
- Superseded next step: the historical attribution review/open flow is complete, and the production P2P/NAT profile has since been selected for the bounded no-network handoff recorded at the top of this roadmap. Controlled network work still requires the seven pre-network decisions and a separate versioned approval; physical Android, optical QR, and real-network acceptance remain separate gates.
- Evidence boundary: the phone is disconnected. This is no-device Swift/SQLite/JVM/Compose/development-mock evidence, not physical Android rendering or TalkBack, optical QR, live-provider citation quality, production relay/P2P, or real-network proof.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark was not used.

## Runtime-Verified Structured Answer Source Attribution

- Date: 2026-07-12.
- Status: successful nonblank `chat.done` stop completions can carry one through eight ordered `source_attributions`. Each runtime-generated entry contains only `source_index`, canonical safe `document_name`, canonical lowercase `mime_type`, and nonnegative `chunk_index` from reviewed source contexts actually supplied to generation. The same safe snapshot is stored with the terminal event and restored on authenticated history reads.
- Meaning and privacy boundary: attribution is historical provenance of context supplied to the model, not model-authored citation text, sentence-level entailment, or current authorization. Source text, grant/citation/anchor/document ids, fingerprint, revision, approval, offsets, path, workspace, project, backend, route, and credential metadata remain absent. Later revoke blocks future use but does not rewrite a completed answer; regenerate removes the prior assistant answer and attribution before using only newly selected sources.
- Completion and concurrency boundary: attribution is omitted for cancellation, backend error, context-window rejection, audit/storage failure, blank answer/reasoning, or source-free requests. Epoch-bound terminal ownership permits exactly one stop/cancel outcome across delayed cancel and connection-close races; cancel persistence failure returns a redacted `chat_store_unavailable` error instead of false success. JSONL validates the complete safe event before writing, and authenticated hello capabilities are bounded to 32 canonical entries of at most 128 UTF-8 bytes each.
- Compatibility and Android boundary: authenticated runtime connections receive attribution only after advertising `chat.source_attributions.v1`; the no-auth development path remains explicit and legacy clients retain the prior key set. Android strictly decodes unknown fields and bounds, sanitizes persisted history, clears stale attribution on regenerate/cancel/error, and renders a localized source list between answer and actions without changing copy behavior. Initial and restored authentication require a verified challenge and a successfully sent signed response on the same channel generation; delayed identity loading and unsolicited or stale accepted responses cannot cross a replacement connection or authenticate the app.
- Verification: 343 Swift router/store tests and 425 Android ViewModel tests pass, together with the complete Android protocol/app/Compose selection, direct and relay RuntimeDevServer smoke, schema/copy/docs/localization checks, and both hash-pinned production security-design validators. Two GPT-5.6 Sol review rounds found terminal races, JSONL pre-write validation, capability bounds, post-pair challenge bypass, stale response handling, replacement-channel hello dispatch, and cancel persistence failure; all have deterministic fixes and final re-reviews report no remaining P0-P3 findings.
- Aggregate verification: `build/qa/check-no-device-quality-structured-source-attribution-final-reviewed-20260712.log` records exit status 0, `No-device quality checks passed.`, 47 fresh relay connections, 745 encrypted frame bodies, and the structured answer source attribution addendum in the complete no-device queue.
- Next v0.3 work at this checkpoint was an explicit authenticated source-review/open flow for a selected historical attribution. The newer section above completes that boundary with current approval and exact revision revalidation.
- Evidence boundary: the phone is disconnected. This is no-device Swift/SQLite/JVM/Compose/development-mock evidence, not physical Android rendering or TalkBack, optical QR, live-provider citation quality, production relay/P2P, or real-network proof.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark was not used.

## Revision-Bound Trusted-Source Chat Context

- Date: 2026-07-12.
- Status: authenticated `chat.send` now accepts optional `trusted_source_grant_ids` containing one through eight unique canonical device grants. Omission preserves the legacy chat shape; raw source anchors, source text, revisions, approval state, and trusted-source objects remain invalid payload fields.
- Authorization boundary: the complete ordered grant set is validated in one in-memory lock or SQLite immediate transaction against the authenticated device, `chat_context` scope, non-revoked grant, non-stale citation, current `runtime_shared` approval and exact source revision, current document metadata, source anchor, and chunk identity. Any invalid member fails the whole request as `trusted_source_not_found`; audit/storage failure returns `document_index_unavailable`. Grants remain reusable until revoke, while every use commits one content-free `trusted_source_context_consumed` event before text leaves the store.
- Model and storage boundary: each excerpt is capped at 4,096 UTF-8 bytes and serialized with safe document name, MIME type, chunk index, and text as runtime-owned JSON reference data appended only to the backend copy of the newest user turn. Legacy or spoofed guards are removed and the current canonical system guard always says source text is data rather than instructions. Grant, citation, and anchor ids stay out of model context; source text and all authorization metadata stay out of stored request events, title inputs, transcript reads, Android persistence, and client-visible messages. Mandatory context that cannot fit fails with `chat_context_window_exceeded` before backend dispatch.
- Android boundary: Chat exposes an accessibility-checked source picker with checkboxes and removable safe-name chips, refreshes the current device grant list when opened, and selects at most eight sources. Grant ids remain in the private ViewModel map; selection is transient and clears after send/regenerate, session change, list omission, revoke, disconnect, trust reset, authentication loss, malformed trusted-source errors, or server `trusted_source_not_found`. Terminal review/revoke errors remove dead capabilities, actionable localized errors replace unknown fallback copy, a selected source without a current private grant blocks send, and dispatch-time channel plus pre-IO socket capture prevents a queued grant-bearing envelope from crossing either a replacement channel or a replacement socket on the same client.
- Focused verification: 11 citation-governance tests cover device isolation, all-or-nothing multi-source use, reopen/same-revision preservation, changed-revision/revoke blocking, content-free audit, and consumption/revoke serialization. All 306 router tests plus the 11 citation-governance tests pass together, including backend-only injection, stored-history exclusion, opaque-id model exclusion, malformed bounds, audit failure, model-window overflow, and unavailable-grant closure. Android protocol/ViewModel/Compose and core transport tests cover strict 1...8 wire validation, omission compatibility, one-shot selection, stale cleanup, picker refresh, checkboxes/chips, UI/persistence redaction, malformed-error retry, replacement-channel binding, and same-client reconnect socket capture. RuntimeDevServer smoke consumes a grant, verifies backend text, verifies stored-history exclusion, revokes it, and proves later backend dispatch is blocked. Final GPT-5.6 Sol macOS and Android re-reviews report no remaining P0-P3 findings.
- Aggregate verification: `build/qa/check-no-device-quality-trusted-source-chat-context-final-reviewed-20260712.log` records exit status 0, `No-device quality checks passed.`, 47 fresh relay connections, 747 encrypted frame bodies, and the trusted-source chat-context addendum in the complete Android/Swift/protocol/docs/static-design queue.
- Next v0.3 work at this checkpoint was runtime-verified structured answer source attribution followed by an explicit current-authority source review/open interaction. The newer sections above complete both boundaries.
- Evidence boundary: the phone is disconnected. This is no-device SQLite/Swift/JVM/Compose/development-mock evidence, not physical Android interaction, live-provider answer/citation quality, optical QR, production relay/P2P, or real-network proof.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark was not used.

## Citation And Device Trusted-Source Review

- Date: 2026-07-12.
- Status: authenticated `citation.resolve`, `trusted_source.approve`, `trusted_source.dismiss`, `trusted_source.list`, and `trusted_source.revoke` are active with closed request/response schemas. A citation resolves one current approved `source_anchor_id`; a device grant records explicit review for the exact approved revision and fixed `chat_context` scope without changing host `runtime_shared` approval.
- Wire and privacy boundary: responses expose only canonical opaque handles, safe document metadata, bounded chunk coordinates, disclosure version, scope, and timestamps. Source revision, host approval id, path, body, snippet, query, model, vector, cache, backend, workspace, and project metadata stay off the wire. Review confirmation is one-time, 256-bit operating-system CSPRNG material; replay, another device, expiry, changed revision, revoke, or delete fails closed.
- Persistence and resource boundary: same-revision reindex preserves citation/review/grant state; changed replacement, host revoke, delete, and filtered maintenance invalidate it transactionally. Expired and stale SQLite reviews are consumed before returning their terminal error. Content-free source audit is bounded identically in memory and SQLite to the newest 100,000 insertion-ordered events, trimming oldest overflow in the insertion transaction even when wall-clock time repeats or moves backward.
- Android boundary: opaque citation/review/grant ids and confirmation tokens remain private ViewModel state and clear with the authenticated session. The newer section above permits only selected grant ids in the encrypted top-level `chat.send` authorization array; they never enter client-visible messages, device persistence, accessibility text, logs, or model context. The UI distinguishes not-loaded from loaded-empty grants, rejects duplicate or mismatched identities, ignores stale list snapshots after approval/revoke, localizes review expiry, exposes named progress state, and lets a user cancel a dropped citation request while a 15-second timeout releases it automatically.
- Focused verification: seven citation-governance tests, five source-governance tests, all 302 `LocalRuntimeMessageRouterTests`, Android protocol/ViewModel/Compose regressions, shared schema, localization, copy hygiene, Swift builds, and direct RuntimeDevServer mock smoke pass. Independent GPT-5.6 Sol review findings for error-code parity, bounded audit storage, terminal-review consumption, dialog closure, stale-list races, loaded state, duplicate/mismatched grants, timeout/cancellation, accessibility progress, and localized expiry have direct fixes and regressions. Final macOS and Android re-reviews report no remaining P0-P3 findings.
- Aggregate verification: `build/qa/check-no-device-quality-citation-trusted-source-review-final-reviewed-20260712.log` records exit status 0, `No-device quality checks passed.`, 47 fresh relay connections, 738 encrypted frame bodies, and the citation/device trusted-source review addendum in the complete Android/Swift/protocol/docs/static-design queue.
- Next v0.3 work at this checkpoint was current-revision grant consumption before document text entered chat context. The newer section above completes that boundary; structured answer citation attribution remains next.
- Evidence boundary: the phone is disconnected. This is no-device SQLite/Swift/JVM/Compose/development-mock evidence, not physical Android interaction, live-provider answer/citation quality, optical QR, production relay/P2P, or real-network proof.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark was not used.


## Approved Runtime Semantic Document Retrieval

- Date: 2026-07-12.
- Status: authenticated `retrieval.query` now accepts optional provider-qualified `embedding_model_id`. Omission preserves the exact legacy lexical response key set; explicit opt-in performs semantic ranking and returns `match_kind: semantic`. Embedding, model, index, or audit failures never silently fall back to lexical ranking.
- Approval and audit boundary: only current `runtime_shared` approved chunks enter inference. A pre-inference `BEGIN IMMEDIATE` transaction revalidates candidate approval and records one content-free `semantic_accessed` event before candidate text reaches the embedding backend. A second transaction drops changed or revoked candidates and appends the final `.queried` event before response serialization. Backend failure or cancellation observed before that final commit preserves the access event without inventing a completed query event; after the commit, response serialization is not suppressed by task cancellation. Query, snippet, body, model, score, vector, revision, and cache state are absent from both records.
- Embedding and cache boundary: strong-fingerprint models consider up to 200 candidates, embed the query separately, process missing candidates in batches of at most 64 and 262,144 bytes, and persist only revision-bound candidate vectors. Providers without an immutable fingerprint, including LM Studio, remain on-demand and atomically embed one query plus at most 63 candidates in one request so vectors from different model revisions cannot be mixed. Candidate selection is deterministic round-robin across approved documents, each input is capped by the selected model budget and 4,096 UTF-8 bytes, and overflow-stable cosine similarity uses deterministic display-name/document-id/chunk-index ties and contiguous ordinal ranks. New approvals stop at 800 `runtime_shared` sources, the host management view can list and revoke every source up to that ceiling independently of the 100-row remote catalog page, and oversized legacy approval sets fail semantic reads closed. Candidate SQL selects at most 200 usable documents, distributes a hard total budget of 800 chunk rows with no corpus-sized window CTE, and installs a SQLite progress handler so connection cancellation interrupts discovery.
- Android compatibility: Android sends its selected runtime-host embedding model only with a bounded document query. If an older strict runtime returns `invalid_payload` naming `embedding_model_id`, Android retires that request and retries exactly once with the same normalized query and bounds but no hint. Other semantic failures are terminal, a second rejection cannot retry, and late retired responses are ignored.
- Verification: 19 cache tests, 12 host source-manager tests, eight semantic router tests, focused Android protocol/ViewModel tests, shared schema checks, Swift builds, all 111 localization tests, smoke typecheck, direct RuntimeDevServer mock smoke, and the complete no-device aggregate pass. GPT-5.6 Sol found and verified fixes for host management visibility beyond the 100-row remote catalog page, corpus-sized candidate SQL work, cancellation inside `sqlite3_step`, progress-handler context lifetime, and candidate-phase test precision; the final re-review reported no remaining P0-P3 findings. `build/qa/check-no-device-quality-approved-semantic-document-retrieval-final-reviewed-20260712.log` records exit status 0, `No-device quality checks passed.`, 42 fresh relay connections, 716 encrypted frame bodies, and the approved semantic document retrieval addendum in the complete Android/Swift/protocol/docs/static-design queue.
- Next v0.3 work at this checkpoint was citation envelopes and client trusted-source review. Newer sections above complete both that lifecycle and current-revision grant consumption for chat context.
- Evidence boundary: the phone is disconnected. This is no-device SQLite/Swift/JVM/development-mock evidence, not physical Android, optical QR, live Ollama/LM Studio semantic quality, production relay/P2P, or real-network proof.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark was not used.

## Semantic Document Match-Kind And Revision-Keyed Cache Foundation

- Date: 2026-07-11.
- Status: the pre-activation semantic document contract is implemented. `retrieval.query` remains deterministic lexical in production; no runtime embedding dispatch or semantic ranking path is active.
- Wire compatibility: result `match_kind` is optional and closed to `lexical` or `semantic`. A missing field is legacy lexical. Existing lexical requests retain the old response key set and non-empty `matched_terms`; an explicit semantic result may carry zero through 16 honest lexical overlaps. Android decodes the typed origin and localizes a semantic-match label, but still sends no document `embedding_model_id` hint.
- Cache boundary: candidate vectors use the same runtime document SQLite database and the shared `runtime_shared` scope, without a device owner key. Rows bind document/chunk identity, the full approved source revision, canonical provider-qualified model id, strong model fingerprint, semantic-document encoding version, and exact bounded-content SHA-256 fingerprint. Query vectors and cache metadata never enter storage or the wire.
- Invalidation and resources: replacement, revoke, deletion, and filtered maintenance remove derived rows in the document mutation transaction. Conditional writes revalidate approval scope, source revision, and bounded chunk content under `BEGIN IMMEDIATE`, then recheck cancellation before commit. Candidates are capped at 200 and 4,096 UTF-8 bytes, embedding batches at 64 candidates, rows at 2,000 per model, vector bytes at 32 MiB per model and 64 MiB per runtime database.
- Verification: 12 `SQLiteRuntimeDocumentSemanticEmbeddingCacheTests`, three Swift router contract regressions, Android protocol/ViewModel/Compose match-kind regressions, the shared protocol schema checker, copy hygiene, Swift build, and diff hygiene pass. GPT-5.6 Sol cache and compatibility reviews found concurrency, statement cleanup, valid-candidate fairness, cancellation/read bounds, old-client opt-in, blank terms, semantic UI wording, and Swift wire-test gaps. All have targeted fixes; both final re-reviews report no remaining P0-P3. `build/qa/check-no-device-quality-semantic-document-cache-foundation-final-reviewed-20260711.log` records exit status 0, `No-device quality checks passed.`, both new contract addenda, 42 fresh relay connections, 710 encrypted frame bodies, and the complete Android/Swift/protocol/docs/static-design queue.
- Next v0.3 work: integrate `embedding_model_id` semantic document ranking only with approved-source snapshot revalidation, content-free query audit, no silent lexical fallback, strong-model persistence policy, cancellation/concurrency handling, and one-time older-runtime compatibility retry. Citations and client trusted-source review remain separate contracts.
- Evidence boundary: the phone is disconnected. This is no-device contract/SQLite/JVM/Compose evidence, not physical Android, live Ollama/LM Studio semantic quality, optical QR, production relay/P2P, or real-network proof.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark was not used.

## macOS Host Document Source Review And Audit Export

- Date: 2026-07-11.
- Status: the production macOS host now has a review-gated document source inspector. File selection creates an app-private bounded snapshot under security-scoped access, extracts only safe summary metadata, and keeps the candidate in memory without changing the active approved revision.
- Approval boundary: sharing requires an explicit `runtime_shared` checkbox and a versioned, one-time review confirmation that expires after ten minutes. New sources receive random stable source ids. Replacements retain the existing approved revision until confirmation, then use source-revision compare-and-swap to rotate the same source id atomically. Cancelled, expired, forged, or stale reviews cannot approve.
- Product wiring: `CompanionAppModel` owns one injected `SQLiteRuntimeDocumentIndexStore` shared by the host manager and `LocalRuntimeMessageRouter`, so approve, replace, and remove operations immediately govern authenticated catalog, lexical retrieval, and source-anchor reads. Removal uses current-revision compare-and-swap and transactionally revokes approval, deletes the local index, and retains content-free audit tombstones.
- Audit policy: the local audit ledger retains the newest 100,000 events in both in-memory and SQLite stores and trims only oldest overflow during insertion. The inspector shows the latest 50 events and can export at most the latest 1,000 events as content-free JSON. Export omits paths, bookmarks, file bodies, queries, snippets, and candidate content.
- Verification: 11 `RuntimeDocumentSourceManagerTests`, all 111 localization tests, and both empty and populated/review document inspector render matrices across five languages and system/light/dark appearances pass. The tests cover approval gating, one-time/expiry/cancel behavior, superseded-candidate invalidation, active-revision continuity, atomic replacement/removal CAS, no-follow snapshot opening, same-store publication, removal, exact newest-first export bounds, localized failures and target labels, and path/content-free export. `build/qa/check-no-device-quality-host-document-review-final-reviewed-20260711.log` records exit status 0, `No-device quality checks passed.`, 42 fresh relay connections, 712 encrypted frame bodies, and the host review addendum in the complete Android/Swift/protocol/docs/static-design queue.
- Independent review: GPT-5.6 Sol identified non-atomic revision checks, pathname reopen after symlink validation, internal governance-detail inconsistency, duplicate approval/index labels, untranslated typed failures, ambiguous removal/expiry labels, and missing populated-state render coverage. All findings now have direct fixes or regressions; final Core and UI re-reviews reported no remaining P0-P3 findings.
- Next v0.3 work at this checkpoint was semantic match-kind response semantics and a bounded revision-keyed document vector cache. The newer sections above complete that foundation, activate approved semantic retrieval, add citation/trusted-source review, and enforce revision-bound chat-context consumption.
- Evidence boundary: the phone is disconnected. This is no-device macOS/SQLite/SwiftUI evidence, not physical Android, live-provider semantic quality, optical QR, production relay/P2P, or real-network proof.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark was not used.

## Runtime-Shared Document Source Governance Foundation

- Date: 2026-07-11.
- Status: the governance prerequisite for future semantic document retrieval is implemented. This does not activate semantic retrieval, embeddings, a document vector cache, citation generation, or a new trusted-source protocol namespace.
- Sharing boundary: an approved source has the explicit `runtime_shared` scope. Every authenticated trusted device connected to the same runtime can read its catalog metadata, lexical `retrieval.query` results, and redacted `source_anchor.resolve` envelope. This is a shared host library, not per-device isolation.
- Approval boundary at this foundation checkpoint: the host-owned `replaceDocument` operation creates a strong SHA-256 source revision over canonical document metadata and the complete normalized chunk set. SQLite keeps approval in a separate table; pre-existing rows have no approval and remain unreadable until a host replacement explicitly approves the new revision. RuntimeDevServer was then the only non-test ingestion caller; the newer section above adds the production review UI.
- Revocation and audit boundary: replacement, revoke, and deletion update document, chunk, FTS, and approval state transactionally. Each approved remote read, audit insertion, and oldest-overflow trim beyond 100,000 events linearize in one store transaction before response serialization; concurrent revoke cannot cross that point, and blocks every later catalog, lexical retrieval, and anchor read. Accepted punctuation-only or zero-limit queries still write a zero-result audit. Audit records action, authenticated device id, safe source identity/revision, anchor id, result count, and time without query text, snippet, or document body. Successful remote reads fail closed when audit persistence fails.
- Verification: 73 in-memory/SQLite/governance tests, two focused router governance tests, and all 289 `LocalRuntimeMessageRouterTests` pass. They cover legacy-unapproved hiding, revision rotation and reopen persistence, two trusted readers, catalog/query/anchor audit, zero-result query audit, content-free audit serialization, concurrent revoke linearization, revoke/delete behavior, and audit-write failure closure. GPT-5.6 Sol found and then verified fixes for the separate-read revoke race and zero-result audit bypass; its final re-review reported no P1-P3 findings. `build/qa/check-no-device-quality-runtime-document-governance-final-reviewed-20260711.log` records exit status 0, `No-device quality checks passed.`, 42 fresh relay connections, 710 encrypted frame bodies, and the new governance addendum in the complete Android/Swift/protocol/docs/static-design queue.
- Next v0.3 work at this checkpoint was explicit host source-selection/review UI and retention/export policy; that work is completed in the newer section above. Semantic match-kind response semantics and bounded revision-keyed vector caching remain next before semantic document retrieval can be enabled.
- Evidence boundary: the phone is disconnected. This is no-device Swift/SQLite/router evidence, not physical Android, live-provider, optical QR, production relay/P2P, or real-network proof.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark was not used.

## Approved Runtime Memory Semantic Search And Cache No-Device Gate

- Date: 2026-07-11.
- Status: the next v0.3 memory slice is implemented. Authenticated `memory.list` can consume the selected provider-qualified runtime-host-local embedding model, semantically rank owner-scoped approved entries, and return the existing `rank`/`snippet`/`matched_fields` shape without echoing model, vector, cache, or revision metadata.
- Approval and audit boundary: only persisted `RuntimeMemoryEntry.content` becomes a semantic document. Generated or dismissed review drafts, source titles, excerpts, source model ids, source pointers, query vectors, and audit metadata are excluded from embedding inputs. The lexical path still supports source-audit matches when no embedding hint is present.
- Persistence boundary: an owner-only SQLite sidecar keys candidate vectors by owner, memory id, canonical model, strong model fingerprint, exact bounded-content fingerprint, and full approved-entry source revision. Only canonical Ollama SHA-256 revisions persist. Current revisions are revalidated after inference and under the memory-store lock before cache commit; edits and deletes purge derived rows before the mutation, and purge failure blocks the privacy-sensitive mutation.
- Resource and compatibility boundary: semantic search considers the latest 200 approved entries, caps content documents at 4,096 UTF-8 bytes with a 1,024-byte fallback, retains the 256-character/16-term query guards, and requires the query to fit the selected model budget. Android accepts only the exact pending response id, keeps queried results transient, releases the consumed pending request before validating a matching response so malformed payloads cannot block later refreshes, and retries a strict older-runtime `embedding_model_id` rejection once as lexical search.
- Verification: 10 helper/cache tests, four router semantic-memory tests, six Android ViewModel/protocol tests, and one Compose remote-result test pass. RuntimeDevServer smoke performs a repeated semantic memory query and requires the second audit row to contain `input_count = 1` without input text. `build/qa/check-no-device-quality-approved-memory-semantic-final-reviewed-20260711.log` records exit status 0, `No-device quality checks passed.`, the approved-memory semantic-cache addendum including malformed-response pending release, 42 fresh relay connections, 710 encrypted frame bodies, and the complete Android/Swift/protocol/docs/static-design queue after GPT-5.6 Sol review remediation.
- Evidence boundary: the phone is disconnected. This is no-device SQLite/Swift/JVM/Compose/development-mock evidence, not live Ollama/LM Studio quality, physical Android rendering, optical QR, production relay/P2P, or real-network proof.
- Next v0.3 work: design semantic document retrieval and knowledge indexing with explicit source approval, citation, trusted-source review, permission, and audit contracts before activating any new retrieval/index namespace.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark was not used.

## Persistent Runtime Chat Semantic Embedding Cache No-Device Gate

- Date: 2026-07-11.
- Status: the next v0.3 prior-chat search slice is implemented. Runtime chat candidate vectors now persist in SQLite under owner, session, canonical provider-qualified embedding model, strong model fingerprint, and exact bounded-document fingerprint keys. The query vector is never persisted and the existing `rank`/`snippet`/`matched_fields` wire shape is unchanged.
- Model identity boundary: Ollama persistence requires the canonical lowercase `ollama-sha256:<64 hex>` artifact digest from `/api/tags`. Exact model ids win before `:latest` alias matching. LM Studio's documented model list has no immutable artifact digest, so LM Studio semantic search remains available but intentionally recomputes candidate vectors on demand.
- Mutation and cancellation boundary: SQLite snapshots each candidate with the owner/session event sequence, append and lifecycle mutations invalidate that session's rows, and conditional upsert rejects a stale source revision. Cache reads do not update LRU state or repair malformed rows. Writes recheck cancellation after acquiring the store lock and immediately before commit; malformed vectors, model revision changes, dimension mismatches, cache failures, and connection cancellation have direct regressions.
- Android boundary: a queried `chat.sessions.list` response is transient `RuntimeUiState` search data. It no longer replaces or saves the complete runtime history cache, and clearing or changing the UI query exposes the persisted full list again. Unqueried refresh responses remain the only path that replaces the full runtime-owned summary cache.
- Verification: focused macOS cache/router/model tests and the full Android `RuntimeClientViewModelTest` suite pass. RuntimeDevServer authenticated relay smoke repeats the same semantic query and requires the second backend audit row to contain `input_count = 1` with no input text. `build/qa/check-no-device-quality-persistent-chat-semantic-cache-final-20260711.log` records aggregate exit status 0, `No-device quality checks passed.`, the persistent semantic-cache addendum, 42 fresh relay connections, 706 encrypted frame bodies, and the complete Android/Swift/protocol/docs/static-design queue.
- Evidence boundary: the phone is disconnected. This is no-device SQLite/Swift/JVM/Compose/development-mock evidence, not live Ollama or LM Studio quality, physical Android rendering, optical QR, production relay/P2P, or real-network proof.
- Next v0.3 work: approved memory notes now use the reviewed persistent contract in the newer section above. The remaining next slice is semantic document retrieval and knowledge indexing without weakening source approval, citation, permission, or audit boundaries.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark was not used.

## Budget-Safe Adaptive Chat Context Compaction No-Device Gate

- Date: 2026-07-11.
- Status: the v0.2 model-window-aware compaction, backend-only LLM summary, request-bound richer source-pointer, and append-only effective terminal accounting slices are implemented, but the full session-compaction roadmap is not complete. Known positive `context_window_tokens` values use `conservative_utf8_bytes_vision_framing_v2`, reserve `max(512, min(4096, window / 8))`, and enforce the remainder as a hard estimator input budget.
- Retention boundary: the runtime preserves every runtime-owned non-conversation system message, the newest user turn, and all later conversation turns verbatim. It adaptively replaces only a contiguous oldest prefix of whole user/assistant turns with fixed runtime-owned system provenance plus an assistant historical summary labeled as untrusted conversation data.
- Failure and compatibility boundary: if the newest user message or mandatory runtime context cannot fit, the runtime returns nonretryable `chat_context_window_exceeded` before backend dispatch, and Android renders localized guidance. Models without context-window metadata retain the legacy 24,000-character heuristic.
- Generated-summary boundary: after a deterministic fallback fits the budget, the runtime may run a bounded prepass on the same selected local model. It discards reasoning, labels accepted output as untrusted assistant data, atomically claims cancellation only for the connection that owns the active request, persists cancellation intent across the prepass-to-primary handoff, atomically checks cancellation while registering the primary backend stream, reserves primary and derived generation ids in one namespace, rejects collisions before backend dispatch, and retains the deterministic fallback on blank, failed, oversized, or non-fitting output.
- Storage boundary: new compacted request events use `adaptive_backend_only_summary_v3`. Its canonical SHA-256 fingerprint binds request/session identity, turn ranges, and the exact storage-safe compacted message prefix; SQLite and JSONL revalidate the binding after reopen. Request accounting is explicitly a `planned_upper_bound`. Optional append-only terminal `compaction_resolution` records whether primary dispatch occurred and, when it did, the deterministic/LLM method plus effective conservative estimate. When Ollama or LM Studio reports actual input usage at completion, bounded generation-scoped one-shot source lookup preserves the original stream enum and two-value `done` contract, while `provider_usage_calibration_v1` binds the count to the router-resolved provider-qualified model plus exact wire mode before classifying it against the estimate and budget. The LM Studio OpenAI-compatible path requests and waits for the post-finish usage-only chunk. An actual budget exceedance or mismatched one-shot source blocks generated-summary cache commit. Missing usage and legacy records remain compatible, and no probe request or automatic policy change is introduced. Each resolution must follow the same owner/session/request-scoped adaptive v3 request and match its estimator and input budget on append and reopen. Legacy v1/v2 and resolution-free records remain readable. Summary text, prompt excerpts, and generated-summary hashes are not stored in chat events, exposed by `chat.messages.list`, or indexed for session search; client-visible history is not rewritten. A separate owner-only SQLite cache may retain successful generated summary text under an exact bounded-source fingerprint plus owner/session/resolved-model/policy key, but only after a stored primary `done`; cancellation, error, non-fitting output, provider-usage mismatch, and provider-reported budget exceedance do not commit, and session delete purges the derived scope.
- Verification: `build/qa/check-no-device-quality-chat-compaction-ownership-final-20260712.log` records the default no-device gate exit 0, both aggregate cancellation/reservation regressions, the backend-only LLM chat compaction addendum, 48 fresh relay connections, 761 encrypted frame bodies, and `No-device quality checks passed.` after the final GPT-5.6 Sol review reported no P0-P3 findings.
- V3 source-pointer verification: `build/qa/check-no-device-quality-chat-compaction-source-fingerprint-final-reviewed-20260712.log` records exit 0, three canonical golden regressions, SQLite and JSONL reopen/tamper validation, the adaptive v3 source-fingerprint addendum, 48 fresh relay connections, 761 encrypted frame bodies, and `No-device quality checks passed.` Final GPT-5.6 Sol review reported no P0-P3 findings.
- Effective terminal accounting verification: `build/qa/check-no-device-quality-chat-compaction-effective-resolution-final-reviewed-20260712.log` records exit 0, all 41 SQLite/JSONL chat-store tests, generated/fallback/cancellation routing regressions, owner/session/request-scoped append and reopen binding, estimator and budget mismatch rejection, the effective terminal accounting addendum, 48 fresh relay connections, 761 encrypted frame bodies, and `No-device quality checks passed.` The final GPT-5.6 Sol re-review reported no P0-P3 findings.
- Evidence boundary: current evidence is no-device Swift planner/router/store and Android protocol/Compose localization coverage. It does not prove physical Android, live-provider tokenizer parity, production relay/P2P, optical QR, or real network connectivity. The phone is disconnected.
- Durable summary-cache verification: focused cache/router tests cover exact-input full-key isolation, owner-only reopen, corrupt-row miss, bounded eviction, commit rollback, successful cross-router reuse, failed-primary non-commit, session-delete purge, resolved-provider-model binding, and backend stream registration without holding the router lock. `build/qa/check-no-device-quality-chat-compaction-durable-cache-final-reviewed-20260712.log` records the final default gate exit 0, 48 fresh relay connections, 761 encrypted frame bodies, the durable cache addendum, and `No-device quality checks passed.` after GPT-5.6 Sol reported no remaining P0-P3 findings.
- Incremental summary evolution: implemented with a reusable canonical lineage fingerprint over the exact storage-safe compacted conversation, separate from the request-bound adaptive v3 event fingerprint. Exact hits require the complete current lineage. An exact miss may evolve only from the newest verified strict prefix under the same owner/session/resolved-model/policy scope, using the previous generated summary and newly compacted whole-turn delta as separately labeled untrusted prepass input. Edit, reorder, delete, malformed lineage, scope mismatch, failure, and cancellation fail closed; only a stored primary `done` commits the evolved row. The previous derived-cache schema is dropped and rebuilt when lineage columns are absent.
- Provider usage calibration foundation: post-dispatch `provider_usage_calibration_v1` is implemented for Ollama chat, LM Studio native, and LM Studio OpenAI-compatible completions without changing the conservative pre-dispatch decision. Exact provider-tokenizer parity, live-provider acceptance measurements, and richer automatic policy calibration remain future work.
- Provider usage calibration verification: `build/qa/check-no-device-quality-provider-usage-calibration-final-reviewed-20260713.log` records exit status 0, 48 fresh relay connections, 763 encrypted frame bodies, the provider usage calibration foundation addendum, `No-device quality checks passed.`, and controlled-spike selection 0 with the socket gate closed after the final GPT-5.6 Sol review reported no P0-P3 findings.
- Host-local calibration acceptance report: implemented as an explicit macOS inspection surface over revalidated terminal events. It groups only by exact provider, canonical exact provider model id, wire mode, and estimator revision; reports aggregate relation counts only; considers at most the newest 1,000 fully eligible samples and 32 newest groups; and uses a 20-sample floor only to mark a group `ready_for_review`. Any observed hard input-budget exceedance takes precedence. `ready_for_review` is not acceptance, tokenizer parity, or permission to tune policy.
- Bounded-store boundary: JSONL scans backward under existing coordination with 64 MiB, 50,000-line, and 4 MiB-per-line ceilings; a selected request outside that tail fails closed. SQLite scans at most 50,000 newest terminal rows, then performs at most 1,000 indexed normalized-owner plus exact-session/request binding lookups and 1,000 two-row uniqueness checks. Incomplete eligible windows fail closed. Deterministic-preview estimates are request-equal, calibrated or uncalibrated duplicate compaction terminals are rejected, and malformed/wrong-type calibration never becomes an omitted sample.
- Report privacy and authority boundary: report output omits prompt/message bodies, owner, session, request, event ids, timestamps, source pointers, and summary text. It is host-local CompanionCore/macOS state, not a `BridgeProtocol` message or Android capability. It performs no probe request, provider call, automatic estimator change, client persistence, network I/O, or new approval action.
- Host publication boundary: report loading runs on a utility executor and the sheet disables overlapping refresh. Starting or failing a refresh removes prior groups; the error branch is exclusive, so timestamp-free stale results cannot remain actionable.
- Calibration report focused verification: the combined selector passes 82 tests. Six pure regressions cover grouping, floor/warning priority, sample/group caps, deterministic order, and exact encoded privacy; all 73 store regressions cover bounded eligibility, explicit JSONL/SQLite ceiling exhaustion, malformed data, deterministic and calibrated/uncalibrated duplicate terminals, exact binding, and reopen behavior; host publication, five-locale copy, and the dedicated 5-language x 3-appearance render smoke also pass.
- Calibration report final verification: `build/qa/swift-full-chat-compaction-calibration-report-final-reviewed-20260716.log` records all 1,554 Swift tests passing with two expected live-provider skips in 346.303 seconds. `build/qa/check-no-device-quality-chat-compaction-calibration-report-final-reviewed-20260716.log` exits 0 across 11,916 lines with one overall marker, one dedicated report marker, 88 loopback relay matches, and 905 encrypted frame bodies.
- Calibration report review: request binding, duplicate-terminal handling, bounded store work, off-main/stale publication, warning/privacy regressions, and explicit scan-exhaustion proof were remediated. Final GPT-5.6 Sol re-review reports no P0-P3 findings. Production-scale ceiling workloads were not directly allocated, and Android SDK reports no attached physical device.
- Current source integrity: because `CompanionAppModel.swift` is pinned P2P/NAT evidence, this slice refreshes the closed 13-artifact collection SHA-256 to `61bf5182935fb9da7a2de0a92d1d2f3f534aeb9847fc410c7e44b2fc12846b31`; bounded Phase A is unchanged and the socket/network/Phase B gate remains closed.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark was not used.

## Review-Required Long-Inactivity Memory Summary Generation No-Device Gate

- Date: 2026-07-11.
- Status: the v0.2 explicit generation slice is implemented. Authenticated `memory.summary.draft.generate` uses exact stale guards and an installed runtime-host local chat model, limits model input to bounded visible user/final-assistant excerpts, requires strict bounded JSON, strips reasoning, and revalidates the source after inference.
- Persistence boundary: generated text is an owner-scoped runtime JSONL review cache keyed by deterministic draft id, not approved memory. Repeated/reopen generation uses the cache. Approval without replacement content stores the generated text with `llm_summary_v1`; dismissal and approved/dismissed hiding retain their existing semantics.
- Android boundary: Settings > Memory exposes Generate Summary for deterministic previews, displays generated summaries as review-required, blocks conflicting decisions during generation, refreshes stale drafts, and keeps generated state out of `RuntimeLocalStore`.
- Verification: focused Swift router/store/policy, Android protocol/ViewModel/Compose, schema, and RuntimeDevServer development-relay smoke coverage is registered in the default no-device gate. Failure paths preserve the deterministic preview and write no approved entry.
- Final aggregate verification: `build/qa/check-no-device-quality-memory-summary-generation-final-reviewed-20260711.log` records exit status 0, `No-device quality checks passed.`, the review-required generation and Android transient-state addenda, authenticated success/cache/malformed/approval smoke, updated P2P/NAT and production-relay evidence validation, and the complete Android/Swift no-device queue after all GPT-5.6 Sol review fixes.
- Evidence boundary: the phone is disconnected. No physical Android interaction, optical QR, live-provider summary-quality evaluation, public-network, real different-network, production relay/session encryption, or direct Android backend behavior is proven.
- Next memory work: select a richer inactivity/review policy only after product review; automatic unreviewed extraction, reflection, embedding-backed recall, conflict resolution, and project-scoped memory remain future slices.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark was not used.

## Production P2P/NAT Security Design Static Gate (Selection Pending)

- Date: 2026-07-11.
- Reviewed portfolio: [production P2P/NAT security hardening](security-hardening/production-p2p-nat-v1/hardening.md), with machine-readable options in `hardening.json`, an explicit threat model, primary-standard references, two decision proposals, eight comparable Mermaid diagrams, and a hash-pinned 13-artifact source/schema/fixture evidence manifest. The current evidence collection SHA-256 is `b08720c763bb6433380853af4702944a40272ae9fd8a944557c37416bf0f842b` after the authenticated router gained host-local approval review anti-spoofing without changing the selection-gated P2P design or closed network boundary.
- Current boundary: Android can validate, persist, prioritize, and pass opaque expiring `p2p_rendezvous` material to an injected connector, while macOS has an optional pair-scoped overlay lifecycle slot. `route.refresh` remains the only active route-control message. Candidate exchange, STUN/TURN traffic, ICE checks, hole punching, production P2P key exchange, and a concrete connector are not implemented.
- Candidate-control recommendation: define an authenticated encrypted ICE usage with short-lived pair-scoped signaling envelopes, paced checks, consent freshness, explicit candidate filtering, and authenticated TURN fallback. Rendezvous, STUN, TURN, and relay infrastructure remain connectivity services rather than trust or traffic-key authorities.
- Session recommendation: use one transport-neutral paired-identity-bound secure-session transcript across direct and relay paths. It binds both pinned identities and roles, pair epoch, both ephemeral shares and nonces, the candidate-exchange digest, selected path, protocol offer/selection, and relay lease digest before runtime commands. A QUIC-based profile remains a measured cross-platform spike, not a selected implementation.
- Fail-closed boundary: hole punching proves reachability, not identity; raw candidates never enter QR or public indexes; replay, expiry, downgrade, consent loss, unvalidated migration, reserved namespaces, and fallback to development plaintext fail closed. Trust removal invalidates pending material and current paths. No `implementation/` directory or concrete library selection exists.
- Verification: `python3 script/check_p2p_nat_security_design.py` validates evidence hashes, the exact 13-artifact set, structured option/tradeoff coverage, proposal and diagram structure, standard references, reserved active-protocol namespaces, local-path hygiene, and absence of a design-local `implementation/` handoff. It explicitly does not infer production implementation status. The default no-device gate and copy-hygiene gate invoke the same validator.
- Final aggregate verification: `build/qa/check-no-device-quality-p2p-nat-security-design-final-20260711.log` records exit status 0, the 13-artifact/2-opportunity/6-option/8-diagram validator result, production-relay validation, copy/docs hygiene, `No-device quality checks passed.`, and the static-only P2P/NAT addendum.
- Evidence boundary: the phone is disconnected. This static design gate is not STUN/TURN interoperability, NAT behavior, direct P2P, public-network, real different-network, latency, memory, battery, optical QR, physical Android, or production cryptography proof.
- Next: select or refine the protocol profiles, then run bounded Android/macOS connector spikes for direct success rate, authenticated time-to-first-command, UDP-blocked behavior, path migration, candidate leakage, battery, and relay cost before implementation begins.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark was not used.

## macOS Pair-Scoped Private-Overlay Lifecycle Seam No-Device Gate

- Date: 2026-07-11.
- Ownership boundary: `MacRuntimeConnectionManager` can now own one optional injected `MacRuntimePrivateOverlayTransport` per client-key fingerprint beside the independently owned pair relay transport. The default app injects no implementation, so this adds lifecycle orchestration without enabling a concrete private-overlay network path.
- Pair lifecycle: accepted pair-route activation and restored non-expired pair routes enter the same `startPairScopedTransports` path. When a private-overlay factory exists, the overlay starts before the pair relay, while relay remains available as the separate fallback candidate. Removing one trusted device stops only that fingerprint's overlay and relay; repeated `stopAll()` releases current local, Bonjour, bootstrap, overlay, and relay resources once.
- Authority boundary: each overlay start receives a fresh generation and synchronized message-callback lease. Replacement invalidates old message authority before stop, late status and message callbacks cannot mutate the current generation, and a terminal stop lease prevents an already-stopped transport from receiving another stop. Runtime and per-fingerprint lifecycle generations block delayed activation after runtime stop and block route recreation after trusted-device removal; a service-committed advancing lease may still persist after runtime stop for restart recovery. Pair refresh sequence and in-flight state are separate from trust lifetime, persistence uses a captured-base compare-and-swap, and an acknowledged candidate waits for any newer request before activation. Pending activations are keyed by fingerprint. Abstract local, relay, and overlay disconnect capabilities forward exact UUIDs to `LocalRuntimeMessageRouter.connectionDidClose`. Overlay and relay failed/stopped states do not erase the other candidate's ownership.
- Verification: 28 `MacRuntimeConnectionManagerTests`, three existing model local lifecycle regressions, and ten `PairedRuntimeRouteRefreshTests` pass as a 41-test focused slice. Coverage includes missing-factory inert behavior, current status/message/disconnect forwarding, stale replacement rejection, immediate terminal-stop races, independent overlay/relay stopped and failed status handling, scoped pair stop, idempotent unified stop, accepted/restored activation order, stop-versus-refresh recovery, removal-versus-refresh rejection, overlapping fingerprint activations, same-fingerprint older-success/newer-failure reconciliation, conflicting late-response CAS rejection, and integrated shutdown. All 23 `TransportTests` and all 436 `CompanionCoreTests` pass, and `swift build --product AetherLink` passes.
- Final aggregate verification: `build/qa/check-no-device-quality-macos-private-overlay-lifecycle-final-20260711.log` records exit status 0, `No-device quality checks passed.`, all 10 pair-route refresh tests, all 28 manager tests, and the complete private-overlay lifecycle addendum.
- Protocol boundary: no `p2p.*`, `rendezvous.*`, `nat.*`, `stun.*`, or `turn.*` message was activated. No candidate exchange, endpoint discovery, hole punching, P2P KEX, concrete connector, production relay recommendation, or wire behavior was chosen or implemented.
- Evidence boundary: the phone is disconnected. This is no-device Swift lifecycle/unit/mock evidence, not a P2P connection, STUN/TURN interoperability, NAT traversal, public-network, real different-network, optical QR, physical Android, latency, or production security proof.
- Next: complete the P2P/NAT security-design static gate for authenticated candidate exchange, paired-identity-bound session establishment, replay/expiry rules, privacy metadata, path validation, and relay fallback before selecting a concrete connector or signaling implementation.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark was not used. Sol identified refresh resurrection, global pending activation, terminal-stop race, concrete disconnect-capability, and same-fingerprint refresh-supersession defects; all five now have direct regressions.

## macOS Local Listener And Bonjour Ownership Completion No-Device Gate

- Date: 2026-07-11.
- Ownership boundary: `MacRuntimeConnectionManager` now exclusively owns the injected local `RuntimeTransport`, Bonjour `RuntimeAdvertiser`, bootstrap relay transport, and fingerprint-keyed pair transports. `CompanionAppModel` retains UI state, route metadata construction, logging, backend state, and router behavior, but no transport lifecycle object or direct start/stop call.
- Local start boundary: the manager stops prior local ownership, starts the listener, snapshots the exact `PeerServerStatus`, and publishes Bonjour only when it is listening on the requested port. Failed or stopped starts invalidate their message lease, stop partially initialized local transport, explicitly stop/suppress Bonjour, and return the original failure for model UI state.
- Refresh boundary: route-token changes restart only Bonjour with the current listener port and fresh sanitized metadata. A stopped, failed, or mismatched listener invalidates message authority and tears down stale Bonjour plus local ownership; refresh never restarts the listener and returns current status to the model.
- Shutdown and routing boundary: local and relay disconnect UUIDs still reach `LocalRuntimeMessageRouter.connectionDidClose`. Thread-safe callback leases reject local, bootstrap, and pair messages after replacement, retirement, stop, or failure while preserving current handlers; external invalidation waits for an already admitted handler to finish before returning. One idempotent `stopAll()` releases current Bonjour, local listener, bootstrap relay, and pair transports exactly once. Existing relay generation, active/retiring bootstrap, pair-before-bootstrap, and scoped pair removal semantics remain intact.
- Verification: all 21 `MacRuntimeConnectionManagerTests`, three model start/failure/stop and advertisement regressions, and four `PairedRuntimeRouteRefreshTests` pass as a 28-test focused slice. The new regressions cover stale local/relay callbacks, in-flight callback drain before stop returns, failed partial-local cleanup, and asynchronous listener-failure advertisement teardown. All 423 `CompanionCoreTests` pass, and `swift build --product AetherLink` passes. The default no-device gate runs the manager suite, and copy hygiene prohibits direct local/Bonjour ownership in `CompanionAppModel` while pinning local ordering, failure cleanup, refresh, callback authority and drain, disconnect, unified stop, docs, and summary coverage. `build/qa/check-no-device-quality-macos-local-ownership-final-20260711.log` records aggregate exit `0`, all 21 manager tests, the complete ownership addendum, and `No-device quality checks passed.`
- Evidence boundary: the phone is disconnected. This is no-device Swift lifecycle/unit/mock evidence, not cross-machine Bonjour discovery, physical Android, optical QR, public-network, real different-network, production relay, production TLS/KEX/pair-epoch, or live-provider proof.
- Next: the runtime-side connection-manager ownership boundary is complete. Production relay implementation remains selection-gated; real P2P/STUN/hole punching and physical network proof remain separate roadmap work.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark was not used. Sol's final concurrency re-review reported no remaining findings after the callback lease began synchronizing admitted handler completion with invalidation.

## macOS Relay Connection Ownership And Generation No-Device Gate

- Date: 2026-07-11.
- Ownership boundary at this first slice: `MacRuntimeConnectionManager` became the single owner of the injected bootstrap relay transport and fingerprint-keyed pair-scoped transports while `CompanionAppModel` temporarily kept local listener and Bonjour ownership. The completion section above now moves those local resources into the same manager.
- Generation boundary: each bootstrap or pair start receives a fresh generation UUID. Status callbacks verify the current generation and transport identity on the main actor, so late callbacks from replaced clients cannot overwrite current state or revive old route behavior. Replacement invalidates ownership before stopping the previous transport.
- Lifecycle boundary: runtime stop releases every currently owned relay transport once, trusted-device removal stops only that fingerprint, and pair activation starts the new pair-scoped transport before bootstrap retirement. Retirement moves bootstrap ownership from active to retiring, immediately removes status authority, lets the successful refresh response drain, and retains stop ownership until runtime shutdown or replacement.
- Router boundary: concrete relay disconnects still forward their connection UUID to `LocalRuntimeMessageRouter.connectionDidClose`, and message handlers pass through unchanged. This slice changes no wire record, allocation authorization, TLS/KEX choice, pair epoch, or P2P connector.
- Verification: nine focused manager tests plus four paired-route-refresh tests and the relay-clear model regression pass as a 14-test integration slice. The retired-bootstrap regression proves a late `.failed` callback is ignored while `stopAll()` still closes the draining transport exactly once. All 411 `CompanionCoreTests` pass. The durable no-device gate runs `MacRuntimeConnectionManagerTests`, while copy hygiene pins single ownership, generation checks, scoped stop, activation order, docs, and gate registration. `build/qa/check-no-device-quality-macos-connection-manager-final-20260711.log` records the aggregate gate exiting `0` with `No-device quality checks passed.` and the ownership/generation addendum.
- Evidence boundary: the phone is disconnected. This is no-device Swift lifecycle/unit/mock evidence, not optical QR, physical Android, public-network, real different-network, production relay, production TLS/KEX/pair-epoch, or live-provider proof.
- Next at this slice: local listener and Bonjour ownership are completed in the section above.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark was not used. Sol found one stale status-authority defect in the first retirement implementation; the active/retiring split and regression test fixed it, and focused re-review reported no remaining findings.

## Relay Bounded Waiting And Authenticated Identity Fairness No-Device Gate

- Date: 2026-07-11.
- Waiting lifetime: the first unmatched matcher insertion creates one monotonic room deadline. The default is `60` seconds, configuration is bounded to `1...3600` with no disable value, and allocated rooms cannot outlive their remaining lease. Same-role replacement inherits the original deadline rather than extending it.
- Authenticated identity scope: verified strict runtimes use role-domain `runtime` plus the revalidated allocation-binding runtime fingerprint; verified paired clients use role-domain `client` plus the pinned allocation-binding client fingerprint. The default is `4` unmatched waits per authenticated identity across source addresses, configurable in `1...65536` with no disable value. Failed proofs, bootstrap clients without paired-client proof, and legacy peers never enter identity accounting.
- Source boundary: global and canonical accepted-source permits are still acquired immediately after TCP accept and retained through authentication, waiting, and active bridging. Identity rejection cannot add, refund, replace, or enlarge pre-auth descriptor capacity; unauthenticated bootstrap/legacy peers remain source/global and duration limited.
- Matcher lifecycle: identity waiting ownership and the immutable room deadline are matcher-owned. Registration and readiness probes atomically remove an expired room before replacement, matching, or visibility decisions, so delayed timer delivery cannot extend authority. A waiting result carries that same deadline out of the matcher transaction; the server never re-reads room state after publication, so a concurrent counterpart match cannot be mistaken for a missing deadline. Match, same-identity replacement, disconnect, generation invalidation, timeout, and close release exact source/identity counts. Stale peer timers address a peer UUID and cannot unregister a replacement or a newer generation. Active bridge activation cancels waiting timers and leaves encrypted forwarding unthrottled.
- Observability: stable reasons `waiting_peer_timed_out` and `authenticated_identity_waiting_quota_reached` plus saturating counters expose aggregate admission, rejection, timeout, current authenticated waiter, and identity counts without source addresses, fingerprints, roles, relay IDs, tokens, lease material, or proofs.
- Operator surface: `AetherLinkRelay` and `run_allocation_relay.sh` expose canonical positive `--waiting-timeout-seconds` and `--max-waiting-peers-per-authenticated-identity` settings, matching environment variables, and redacted `abuse_controls.waiting_peer_policy` dry-run JSON. Both controls have no disable value.
- Verification: four policy unit tests, five matcher tests, and five socket tests pass as an exact 14-test slice. All 168 `RelayServerCoreTests` pass and `AetherLinkRelay` builds. The focused coverage includes lease-capped immutable deadlines, matcher-atomic rejection of late counterparts/replacements/probe visibility despite delayed timer delivery, deadline retention across a concurrent counterpart match, timeout release/retry, match cancellation, runtime and paired-client identity fairness, failed-proof isolation, source-free logs, and active-bridge continuity. `build/qa/check-no-device-quality-relay-waiting-identity-final-20260711.log` records the aggregate no-device gate completing with exit `0` and `No-device quality checks passed.`
- Evidence boundary: the phone is disconnected. This is no-device unit/matcher/loopback development-relay fairness evidence, not carrier-NAT/VPN fairness measurement, Sybil resistance, production identity service, production capacity/load/latency, public-relay/live-network proof, production TLS/KEX/pair-epoch implementation, optical QR, or physical Android proof.
- Next abuse-control work: treat multi-identity Sybil resistance and production exporter/capacity policy as deployment design, not as a claim of per-user isolation.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark was not used. Final Sol review found no remaining actionable findings after the matcher-expiration and atomic-deadline-return race fixes.

## Relay Source Peer Quotas No-Device Gate

- Date: 2026-07-10.
- Admission scope: every accepted socket acquires the existing global permit and a canonical accepted IPv4/IPv6 source permit. Defaults are `64` concurrent connections and `32` unmatched waiting peers per source, with no disable value and `2 * waiting <= connections` counterpart-headroom validation.
- Lifetime: normal admission keeps one global and one per-source slot available before the first waiter. Every waiting insertion atomically verifies `connections + waiting + 1 <= limit` in both scopes and then removes another normal-admission slot. A socket admitted from that reserve is counterpart-only until it immediately matches the opposite role or performs an authenticated same-source waiting replacement; probe, allocation, cross-source replacement, and new waiting-room use close it. Per-source reserve candidates can discharge only same-source-owned waiters, while global-only reserve candidates may match across sources. Active bridge sockets retain source connection capacity until close, while established encrypted frame forwarding is not throttled or evicted.
- Matcher atomicity: only registrations that remain unmatched consume waiting quota. Immediate counterparts match at the cap, same-source replacement is net-zero, cross-source replacement either transfers quota or preserves the original waiter, and match, replacement, disconnect, generation invalidation, and close return exact counts.
- Fairness: exact source identity reuses IPv4/mapped-IPv6 canonicalization, native IPv6 scope, and the shared unknown family identity. No overflow bucket is needed because live source state is bounded by global accepted connections. Shared NAT/VPN users share quotas; `64/32` is a configurable development fairness hypothesis rather than per-user isolation.
- Observability: stable source-free reasons and saturating metrics cover admission requests, admitted totals, global/source rejections, counterpart candidate admission/confirmation/rejection/current state, live connections/waiters, and current source counts without source addresses, relay IDs, route/allocation tokens, or proof fields.
- Verification: seven limiter tests, five matcher lifecycle/provenance tests, and four loopback socket tests pass as an exact 16-test slice. All 155 `RelayServerCoreTests` pass, and `AetherLinkRelay` builds. The durable no-device gate pins default/custom JSON, canonical CLI/environment validation, the 2:1 invariant, pre-waiter global/source headroom, waiting-insertion revalidation, global/source reserve provenance, cross-source source-reserve rejection, real counterpart reservation beside an active bridge, nonmatching-candidate rejection, bridge continuity, and source-free telemetry. `build/qa/check-no-device-quality-relay-source-peer-quotas-20260710.log` records the aggregate gate completing with exit `0`.
- Evidence boundary: the phone is disconnected. This is no-device synthetic/unit/matcher/loopback development-relay evidence, not production capacity/load/latency validation, carrier-NAT/VPN fairness measurement, IPv6 rotation defense, public-relay/live-network proof, production TLS/KEX/pair-epoch implementation, or physical Android proof.
- Next abuse-control work: the bounded waiting and post-authenticated identity milestone is implemented in the section above.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark was not used.

## Relay Source-Aware Allocation Control No-Device Gate

- Date: 2026-07-10.
- Control-plane scope: valid allocation preflight records use one source bucket; new endpoint-owned allocation and paired claim/renew mutations use a separate source bucket. Allocation-token checks and cryptographic challenge work happen only after the applicable bucket admits the request.
- Defaults: preflight is `120/minute` with burst `30`; allocation mutations are `30/minute` with burst `10`; at most `4096` source buckets are tracked for `15 minutes` of idle retention. CLI and environment overrides are bounded, have no disable value, and require each burst to fully refill within retention so cleanup cannot reset capacity early.
- Source identity: the key comes only from the accepted socket address. IPv4 and IPv4-mapped IPv6 are canonicalized together, native IPv6 includes its scope ID, and unrecognized address families share one unknown-source bucket.
- Resource/observability contract: monotonic token refill, backward-clock resistance, periodic idle cleanup, and a shared overflow bucket keep at most the configured number of buckets without capacity-eviction resets or per-request full-map scans. Saturating counters, stable reason names, overflow accounting, and source-free metrics/logs prevent route tokens, allocation tokens, relay IDs, or source addresses from entering rejection telemetry.
- Malformed-attempt boundary: allocation- and renewal-prefixed records consume a classified source bucket before full request parsing. Only the exact cheap strict preflight envelope selects the preflight bucket; duplicate markers, mutation-like fields, malformed spacing/tokens, every other allocation attempt, and every renewal attempt select the stricter mutation bucket.
- Traffic boundary: probes, peer admission, waiting rooms, active bridges, and encrypted frame forwarding are not rate limited by this control. Shared NAT/VPN users share a source bucket, so the defaults are conservative development settings rather than a user-isolation guarantee.
- Verification: six limiter unit tests and five loopback socket tests cover defaults/bounds, refill, IPv6 scope, canonical/mapped/unknown identity, shared overflow without reset, periodic idle cleanup, stable metrics/reasons, malformed classified attempts, separate buckets, paired renewal, silent rejection, and unaffected bridge traffic. The full `RelayServerCoreTests` suite passes 139 tests.
- Durable gate: `script/check_no_device_quality.sh` pins the focused tests, wrapper default/custom JSON, invalid CLI/environment rejection, and source-free reason/counter contract; `script/check_copy_hygiene.py` binds implementation, tests, operator surfaces, docs, and proof boundaries.
- Final aggregate verification: `build/qa/check-no-device-quality-relay-source-rate-limits-20260710.log` records exit status 0, `No-device quality checks passed.`, the exact 11-test source-rate-limit slice, and all 139 `RelayServerCoreTests`.
- Evidence boundary: the phone is disconnected. This is no-device development-relay control-plane hardening, not production capacity or latency validation, public-relay/live-network proof, production TLS/KEX/pair-epoch implementation, or physical Android proof. Connection and waiting admission are now covered separately by the source peer quota section above.
- Next abuse-control work: the source peer quota and bounded waiting/authenticated identity milestones are completed in the sections above.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark was not used.

## Relay Abuse-Control Foundation No-Device Gate

- Date: 2026-07-10.
- Accepted-socket ownership: `RelayConnectionLimiter` grants one nonblocking permit at `accept`; the reference-owned connection keeps that permit through control handling, waiting-peer storage, and both sides of an active bridge. Excess sockets close immediately.
- Waiting-peer lifecycle: the socket registry is server-owned and stores a peer before matcher publication. A read monitor removes disconnected or protocol-early waiting peers and releases their socket permit; matching cancels the monitor before ready metadata and forwarding.
- Control deadline: all initial, allocation, renewal, runtime-registration, and paired-client proof records use one absolute monotonic read deadline per record. The exact 4096-byte newline-inclusive framing limit remains unchanged, and frame forwarding remains timeout-free.
- Probe policy: unauthenticated readiness probe is loopback-only by default, may be fully disabled, and requires explicit `legacy-unauthenticated` diagnostic opt-in on an exposed strict relay. Exposed default probe closes without a route-existence oracle. Android distinguishes unavailable from unsupported probe and continues to the authenticated relay connection when the oracle is disabled.
- Exposure boundary: unallocated legacy relay mode is loopback-only even when an allocation token is configured. CLI and `run_allocation_relay.sh` expose validated probe policy, control timeout, and global connection limit settings with safe defaults.
- Final verification: 128 focused Swift relay tests, the exact ten-test Swift abuse-control slice, and the focused Android relay-probe tests pass. The complete no-device aggregate exited 0 and recorded `No-device quality checks passed.` in `build/qa/check-no-device-quality-relay-abuse-controls-20260710.log`.
- Gate-driven proof cleanup: the aggregate caught a stale disabled-probe self-test message and a physical-wrapper redaction fixture that could report physical success. Disabled probe evidence now says authenticated pairing is required, route-probe support is explicit, and redaction-only runs cannot set physical external-relay success.
- Independent GPT-5.6 Sol findings applied: accepted sockets suppress `SIGPIPE`, one-sided active-bridge close shuts down both directions before descriptor close and releases both permits plus the matcher room, every interrupted poll/receive recomputes the absolute deadline, the physical helper uses a strict tri-state parser without raw response persistence, and dry-run summary generation passes token presence rather than the token in child argv.
- Final focused GPT-5.6 Sol re-review reported no actionable findings after canonical nonzero probe responses were forced to unsupported and covered by durable guards.
- Evidence boundary: the Android phone is disconnected. This is no-device development-relay hardening, not production TLS/KEX, public relay deployment, or physical Android proof. Allocation rate, source peer quota, and bounded waiting/authenticated identity milestones are completed in the sections above.
- Next abuse-control work: bounded waiting and authenticated identity fairness are implemented above without treating source quotas or identity buckets as per-user isolation.
- Agent state: GPT-5.6 Sol only; GPT-5.3-Codex-Spark was not used.

## Production Relay Security Design Review (Selection Pending)

- Date: 2026-07-10.
- Reviewed portfolio: [production relay security hardening](security-hardening/production-relay-v1/hardening.md), with machine-readable options in `hardening.json`, two decision proposals, eight before/after Mermaid diagrams, and a hash-pinned 17-file source evidence manifest. `E010`, `E011`, and `E012` record development-relay source controls as tactical defense in depth, not selected production options.
- Recommended allocation design: TLS 1.3 with an explicit service trust source plus delegated service-signed lease capabilities. The signed lease enters a reviewed, peer-verifiable identity KEX transcript; relay-side admission remains defense in depth and is not the endpoint trust terminator.
- Recommended recovery design: monotonic `pair_epoch` and `revocation_counter`, dual-signed normal renewal, one-sided deny-only emergency revocation, fresh-QR key replacement, active/waiting room closure, idempotent transition IDs, and read-only signed status reconciliation after response loss.
- Selection boundary: these are design-selected recommendations, not implemented protocol behavior. No `docs/security-hardening/production-relay-v1/implementation/` directory exists, and implementation must not begin until the option is selected or refined.
- Verification: `python3 script/check_production_relay_security_design.py` validates the evidence hashes, portfolio schema, recommendation IDs, required tradeoffs, proposal/diagram structure, local-path hygiene, and the no-implementation boundary. The default no-device gate invokes the same validator.
- Independent review: GPT-5.6 Sol initially found an idempotent-transition wording conflict and globally scoped document guards. The contract now binds transition id plus canonical request digest, the validators check complete invariants inside named sections, and the focused re-review reported no actionable findings.
- Evidence boundary: the physical Android phone is disconnected. This milestone does not claim optical QR, public-network, production-relay, live-provider, real different-network, physical-device, latency, or memory proof.
- Next decision: select or refine `tls-signed-leases` and `pair-epoch-state-machine`, choose the production service trust source and reviewed cross-platform KEX construction, then create implementation work packages.
- Agent state: GPT-5.3-Codex-Spark was not used. GPT-5.6 Sol only was used for this review.

## Relay Allocation Cross-Process Ownership No-Device Gate

- Date: 2026-07-10.
- Durable registry coordination: one stable mode-`0600` transaction marker has fixed-format `U`/`A`/`E` state and a 64-character lowercase hexadecimal coordination token bound into the schema-v4 store. POSIX `F_SETLK` byte range 0 serializes reload/compare-and-swap/persist, while byte range 1 is the `RelayServer` lifetime owner lock.
- Lock lifetime: byte-range acquisition uses a five-second monotonic retry deadline. The process pool keys by marker inode, reuses the pooled descriptor, and retains only duplicates that cannot safely be closed while process locks may exist.
- Persistence hardening: descriptor-relative `openat`, `fstatat`, `renameat`, and `unlinkat` use `O_NOFOLLOW`; store/marker targets must be current-user-owned regular files with `nlink == 1` under a parent that is not group- or world-writable. Reconciliation uses an owner-only temporary file, file `fsync`, atomic rename, and directory `fsync`.
- Fail-closed recovery: a missing established store, dangling symlink, hard link, case/path alias, marker replacement, or token mismatch is rejected. A valid unversioned `rt1` store is recognized, then all leases are revoked into an empty token-bound schema-v4 store because legacy identity cannot be migrated.
- Cross-process commit semantics: stale disjoint commits merge, while stale same-ID creates and paired claims produce one success and one `allocationConflict`. A stale create cannot restore a consumed bootstrap ID. Pair binding and its consumed-bootstrap tombstone remain one atomic schema-v4 commit, and a token-matched schema-v4 store recovers after an interrupted initial `U` to `E` transition.
- Relay process ownership: a second process sharing the store fails before independent matcher or active-room state can form, a concurrent same-instance `run()` fails without releasing the live listener, bind failure releases byte range 1, simultaneous first startup converges to one owner, and process exit permits a successor against the same marker/store.
- Verification: all 64 `RelayAllocationTests`, 21 relay socket tests, 100 related relay tests, and 797 full Swift tests passed. The TCP-verified actual-process ownership smoke and authenticated runtime smoke passed with 41 connections and 688 encrypted frame bodies. `build/qa/check-no-device-quality-relay-cross-process-ownership-20260710.log` records the passing aggregate no-device gate.
- Evidence boundary: the physical Android phone is disconnected. This cooperative single-host advisory-lock slice does not claim distributed consensus, allocation-channel TLS or server authentication, immediate revocation, production P2P/NAT traversal, or full roadmap completion.
- Agent state: GPT-5.3-Codex-Spark was not used. GPT-5.6 Sol only was used for this slice.

## Historical Roadmap Slice: Pair-Scoped Relay Room Isolation No-Device Gate

- Current contract: paired allocation claim and renewal use `runtime-client-p256-v2` and protocol version 2. The role-separated runtime/client signatures cover both `current_relay_id` and `next_relay_id`; a first claim must move from the runtime-only bootstrap ID to the deterministic pair ID, while renewal stays on that pair ID.
- Persistence boundary: allocation schema v4 replaces a consumed bootstrap record with its pair-scoped record and retains a closed `consumed_bootstrap_allocations` tombstone so the bootstrap ID cannot be reused. A schema-v3 paired record rotates to the deterministic pair ID on its next renewal.
- Admission and room isolation: `paired-client-p256-v1` proves possession of the QR-pinned Android client key before matcher insertion. Active rooms are bound to the exact pair owner, generation, lease nonce, and peer handshake state; duplicate active pairs are rejected, stale waiting generations are closed, and focused socket E2E proves two pair rooms can bridge simultaneously without cross-room frame delivery.
- macOS route lifecycle: pair routes and relay transports are keyed per client fingerprint, with traffic secrets kept in the secret store. The runtime persists the refreshed pair route, sends the successful `route.refresh` response, then activates the pair transport and rotates bootstrap material after a successful first claim.
- Android route lifecycle: Android derives and validates the expected deterministic pair ID before signing, persists the accepted pair ID and generation, and reconnects only after `paired-client-p256-v1` admission succeeds before strict relay readiness.
- Verification: targeted Android coverage passed 8 tests, full Swift coverage passed 774 tests, authenticated relay smoke passed with 41 fresh sessions and 688 encrypted frame bodies, and `build/qa/check-no-device-quality-pair-scoped-relay-room-20260710.log` records the passing aggregate no-device gate.
- Evidence boundary: this is current no-device source, unit, persistence, loopback socket, and mock integration evidence. The physical Android phone is disconnected, so there is no live-device, optical QR, live-provider, or real different-network proof.
- Remaining work: this slice does not provide cross-process compare-and-swap/store ownership, allocation-channel TLS or server authentication, server-side immediate active-session revocation, production P2P/NAT traversal, abuse controls, or full roadmap completion.

## Historical Roadmap Slice: Initial Pairing Mutual P-256 Proof

- Historical compatibility note: this exact guard-pinned heading names an earlier 2026-07-10 slice. Its v1/schema-v3 paired-allocation evidence is historical; the pair-scoped v2/schema-v4 section above is current.
- Require Android `pairing.request` to prove possession of the persistent client P-256 key over a canonical transcript containing request id, QR credentials, both identities, and the active transport binding.
- Require the runtime to verify that proof before trust, reserve the pairing session, sign the accepted result with its persistent QR-pinned key, and release the reservation on signing or persistence failure.
- Require Android to match the outstanding request id/digest, QR-pinned runtime key/fingerprint, trusted client id, result signature, and current transport binding before trusted-runtime persistence. Unsigned rejections may be displayed but do not erase pending route recovery state.
- Historical scope at this slice: the guard-pinned wording was `Android still does not co-sign allocation`; the bearer allocation token remained a plaintext service gate unless protected by outer TLS. Later v1/schema-v3 paired allocation superseded the co-signing gap, and the current pair-scoped v2/schema-v4 gate supersedes its global-room and unauthenticated-client-admission gaps. TLS/server authentication, post-compromise recovery, server-side immediate revocation, production P2P traversal, and production deployment remain incomplete.
- Preserve the completed runtime-key allocation boundary: allocation preflight returns only capability fields with no route material.
- Historical relay identity boundary at this slice: derive the `rt2` allocation ID from the verified runtime-key fingerprint, persist allocation ticket schema v2 with fingerprint plus generation, and keep runtime-role admission proof ahead of matcher admission. Required persistence must fail closed. The later schema-v3 paired authorization record and current schema-v4 pair-room record are documented separately above.
- Verification status: cross-language vectors, Android core/ViewModel/real-relay integration, Swift pairing/router/key-store suites, direct/relay RuntimeDevServer smoke, and the full no-device quality gate pass without a device. `build/qa/check-no-device-quality-initial-pairing-mutual-proof-20260710.log` records `No-device quality checks passed.` and the initial-pairing mutual-proof coverage summary. Physical optical QR and real different-network behavior are still unverified while the phone is disconnected.

## Current Implementation Snapshot

See [progress.md](progress.md) for the detailed implementation record, verification commands, known limits, and next work queue.

- AetherLink currently has a runtime-host-mediated local model loop, a mobile client implementation, localized client/runtime UI, Ollama and LM Studio backend adapters, QR pairing, trusted runtime persistence, model listing, streaming chat, cancellation, Ollama/LM Studio reasoning or think rendering, runtime-host chat processing event storage with narrow authenticated history reads, a default SQLite/FTS runtime chat event-store backend with legacy JSONL backfill, client-side UI cache/history, runtime-generated short chat titles, runtime-owned session query filtering with rank/snippet metadata, archive/delete separation, runtime-owned user memory notes with lexical query/search metadata surfaced through Android Settings Memory search, a first heuristic runtime-side context compaction slice for oversized `chat.send` histories, separate embedding model selection, an Android-selected `embedding_model_id` search hint for runtime-owned chat-history queries, broad runtime-side document ingestion, read-only Android Settings document catalog/search UI backed by transient runtime state, image/vision gating, a first runtime-side model residency policy, identity-based route candidates, an Android core `p2p_rendezvous` route-preparation, QR-planning, trusted-runtime restore contract for opaque expiring records, explicitly enabled authenticated `route.refresh` diagnostics for complete relay and opaque P2P rendezvous records, P2P-only Android route-refresh lease scheduling/retry/expiry lifecycle coverage under that opt-in, a matching macOS pairing QR generation contract for the shared opaque P2P field family, an Android app connection seam that can attempt injected P2P before relay fallback, and a temporary outbound TCP development relay for different-Wi-Fi testing. The deleted suggested next-question feature remains absent from active code/protocol paths and is pinned by a no-device tombstone guard. QR-provisioned relay routes require `relay_secret`, `relay_expires_at`, and `relay_nonce`, so development relay frame bodies are encrypted before forwarding, Android authenticated relay refresh validation rejects reused relay nonces or non-advancing relay leases while allowing stable relay id/secret reuse when diagnostic refresh is explicitly enabled, Android route diagnostics now surface mismatched saved remote-route identities and failed P2P routes without saved relay fallback as latest-QR recovery instead of generic route failures, and the RuntimeDevServer relay smoke now requires authenticated `route.refresh` to advance the QR relay lease and use a fresh relay nonce while allowing stable relay id/secret reuse. The same RuntimeDevServer smoke positively validates malformed pairing identity rejection without trust creation, consumed pairing QR reuse rejection, same-connection runtime command rejection after invalid or consumed pairing requests, accepted pairing result runtime identity confirmation, QR-pinned trusted hello runtime proof verification with `runtime_signature`, history reads, title generation, session rename/archive/restore/delete lifecycle, memory CRUD, memory.list query search metadata, future memory.search rejection, memory-summary draft listing/approval/dismissal/stale-guard/source-audit/memory-list visibility, chat.send context compaction backend-only audit and visible-history separation, two-device owner isolation for memory and chat read/mutation boundaries, authenticated future namespace rejection for reserved skills/MCP/web-search/Python/projects/automation messages, authenticated future route namespace rejection for unsupported route.* messages, raw nonce auth-signature rejection, auth replay and superseded challenge rejection, and encrypted frame bodies for auth, model, chat, attachment, cancel, malformed-pairing, pairing-reuse, rejected-pairing auth-boundary, history, title/session mutation, memory, memory-list query/search, future memory.search, memory-summary stale guard, memory source-audit, chat compaction, reserved future Python namespace, reserved future projects/automation namespace, future route namespace, and owner-isolation plaintext markers while rejecting the full protected unauthenticated runtime command matrix before auth or payload handling. Android trusted relay reconnect now rejects invalid nonce-bound runtime proof and runtime fingerprint mismatch before sending `auth.response` or `runtime.health`, while its relay preflight allows a known relay route to survive the short `runtime_waiting=false` relaunch race and wait for the runtime host to rejoin. The macOS runtime identity fallback creates owner-only file-backed identity material and signs nonce-bound auth challenges with the persisted public-key fingerprint when Keychain-backed identity storage is unavailable. The P2P work currently emits/parses QR records, pins shared route-material schema size bounds for pairing QR and authenticated `route.refresh`, rejects whitespace-mutated or oversized opaque P2P record IDs, encrypted bodies, and anti-replay nonces across parser, trusted restore, pending/trusted/route-refresh, and route-preparation paths, rejects authenticated P2P `route.refresh` records that reuse the current record ID or anti-replay nonce or fail to advance the record expiry when the diagnostic path is explicitly enabled, persists pending Android route material, stores complete trusted-runtime P2P rendezvous material after accepted pairing, route-refresh QR scan, or explicit diagnostic `route.refresh`, plans opaque saved records for trusted reconnect, suppresses Bonjour/local discovery when saved trusted P2P route material is already available, redacts P2P route-material fields from macOS Activity diagnostics, route diagnostics, and companion logs, and can exercise an injected app-level connector before relay fallback; it is not NAT traversal, signaling, hole punching, or a production P2P connector. Trusted runtime persistence, accepted-pairing trust creation, pending pairing route storage, trusted reconnect target generation, core transport default route resolution, and normal route UI now remove or ignore stale current and legacy fixed host/port material during restore; fixed endpoints remain diagnostics/local fast-path hints, not durable reconnect state. macOS clean first-run Pairing now exposes expanded Connection Recovery when remote route material is missing while Status keeps clean-first-run diagnostics quiet, and Android product defaults no longer advertise or automatically send authenticated `route.refresh`; normal route repair stays latest-QR scan first. Bonjour/local discovery TXT metadata publishes only the pairing-derived route token as the identity hint; stable runtime device ids and public-key fingerprints are no longer advertised in TXT and remain QR/pairing/authentication material instead of LAN broadcast metadata.
- The client implementation does not call Ollama or LM Studio directly.
- MCP, skills, web search, advanced memory, project workspaces, automations, Python tools, additional client targets, Windows runtime targets, and DGX OS-class runtime targets remain roadmap work.

## Immediate Next Implementation Queue

Previous initial pairing mutual P-256 proof no-device slice: Android and Swift share canonical length-framed client/result transcripts and fixed digests. Android signs the QR-pinned request, macOS verifies client key possession before reservation/trust, macOS signs the accepted result with its persistent runtime key, and Android verifies request correlation, runtime identity, signature, and transport binding before persistence. Wrong-key, mutation, replay/request-id, downgrade, noncanonical Base64/DER, signer-failure recovery, unsigned rejection state preservation, real relay TCP, and RuntimeDevServer smoke are covered. The current pair-scoped gate now covers claim/renew co-authorization, deterministic pair-room rotation, pre-match client admission, and focused active-room isolation; the current cross-process ownership gate adds durable single-host store transactions and relay lifetime ownership. Next transport work is production service hardening, post-compromise recovery, server-side immediate active-session revocation, P2P NAT traversal, and physical optical/different-network proof.
Latest endpoint-owned relay secret allocation v2 no-device gate: allocation-required relays now accept only canonical `crypto=2` allocation, return exact secret-free lease metadata, and reject versionless or requested-secret allocation before issuing an ID usable for strict registration. macOS GUI, bootstrap, lease-refresh, endpoint-fallback, and RuntimeDevServer paths generate or reuse the 32-byte traffic secret locally and attach it only after service allocation, so the allocation request, response, persisted ticket, and relay log never contain that secret. The durable gate pins strict parser/socket bypass rejection, closed response fields, forbidden service-returned `relay_secret`, local generation/reuse, and secret-free preflight output. Its historical next-work wording was `production allocation authentication and paired-identity authorization`; current v2/v4 pair-scoped claim/renew authorization, room isolation, and single-host cross-process store ownership are covered above. Remaining transport work is allocation TLS/server authentication, immediate revocation/recovery, P2P NAT traversal, and physical optical/different-network proof.
Latest strict allocated relay crypto v2 no-device gate: strict Android and macOS relay peers now generate per-connection P-256 ephemeral keys and session nonces, perform ECDH, mix the shared secret with the QR relay secret through HKDF-SHA256 over a canonical ordered transcript, and mutually confirm the resulting transport binding before frame encryption. Client/runtime traffic secrets are direction-separated, AES-GCM epoch keys rotate every 65,536-frame epochs, ordered replay or authentication failure does not advance receive state, and `Int64.max` counter exhaustion fails before cryptography. Paired-identity v2 signatures retain the confirmed binding, while strict peers reject crypto v1/plain downgrade and local direct plus legacy plaintext diagnostics remain unchanged. Shared Android/Swift vectors and focused protocol/transport/relay-server tests cover scalar keys, HKDF/proofs, both frame directions, epoch boundaries, replay, bad points, bad confirmation, counter exhaustion, and opaque relay forwarding. This supplies forward secrecy against later compromise of only the relay secret when ephemeral private keys were not retained. The reviewed production allocation, identity-first KEX, and post-compromise recovery design is now recorded above; the next transport step is explicit option selection or refinement before versioned implementation. Physical Android, optical QR, real different-network, production relay, and production end-to-end proof remain separate.
Previous strict relay foundations established per-connection session nonces, relay-secret transcript confirmation, paired-identity transport binding, and reconnect key separation. Crypto v2 supersedes their strict wire format without changing local direct or legacy plaintext compatibility.
Latest Android non-retryable route-refresh contract no-device gate: `RuntimeClientViewModelTest.authenticatedTrustedRuntimeDoesNotRetryNonRetryableRouteRefreshError` proves an authenticated relay session honors `ErrorPayload.retryable=false` instead of scheduling another `route.refresh`. The pending request and lease job clear, the current authenticated connection and trusted relay host/id/secret remain intact, and Android publishes `remote_routes_unavailable` without retaining the runtime-supplied failure detail so the existing latest-QR recovery UI is used. Existing retryable failures still retry inside the eligible lease window, and pairing/authentication failures retain their higher-priority terminal path. This is diagnostic-opt-in Android ViewModel evidence only; production route-refresh enablement, physical Android behavior, production P2P traversal, hardened relay/session infrastructure, optical QR scanning, and real different-network proof remain separate.
Latest Android mixed-route relay-fallback retry no-device gate: `RuntimeClientViewModelTest.authenticatedMixedRoutesRefreshUrgentP2pAfterRelayFallbackAndRetryWithinRelayLease` proves complete mixed routes are attempted in `[p2p, relay]` order, a failed P2P session falls back to relay, and the active relay session still sends an immediate authenticated `route.refresh` for the P2P lease at the minimum-delay boundary. After a retryable failure, the P2P lease is excluded from retry eligibility and the longer relay lease sends a distinct second request after `ROUTE_REFRESH_RETRY_DELAY_MS` without redialing either route. Both stored routes and authenticated relay state remain intact. This is diagnostic-opt-in Android ViewModel evidence only; production route-refresh enablement, physical Android behavior, production P2P traversal, hardened relay/session infrastructure, optical QR scanning, and real different-network proof remain separate.
Latest Android mixed-route lease retry fallback no-device gate: `RuntimeClientViewModelTest.authenticatedMixedRoutesRefreshUrgentRelayAndRetryWithinP2pLease` proves a trusted runtime with complete P2P and relay material connects over P2P, sends an immediate authenticated `route.refresh` for the relay lease at the minimum-delay boundary, and after a retryable failure excludes that relay lease from retry eligibility while using the longer P2P lease to send a distinct second request after `ROUTE_REFRESH_RETRY_DELAY_MS`. Relay is not dialed, both stored routes remain intact, and connected P2P state is preserved. This is diagnostic-opt-in Android ViewModel evidence only; production route-refresh enablement, physical Android behavior, production P2P traversal, hardened relay/session infrastructure, optical QR scanning, and real different-network proof remain separate.
Latest Android near-expiry route-refresh immediate dispatch no-device gate: the existing relay and P2P terminal lease tests now prove the production ViewModel consumes the urgent `0L` delay without advancing virtual time. `RuntimeClientViewModelTest.authenticatedTrustedRuntimeMarksRouteExpiredWhenRefreshErrorCannotRetryBeforeLeaseExpiry` and `authenticatedTrustedP2pRuntimeMarksRouteExpiredWhenRefreshCannotRetryBeforeRecordExpiry` capture `testScheduler.currentTime` before accepted authentication, process only current tasks, and observe exactly one `route.refresh` request at the same scheduler time before retaining their terminal retry-failure assertions. The default gate reports `Android near-expiry route-refresh immediate dispatch addendum`. This is diagnostic-opt-in Android ViewModel evidence only; production route-refresh enablement, physical Android behavior, production P2P traversal, hardened relay/session infrastructure, optical QR scanning, and real different-network proof remain separate.
Latest Android mixed remote-route lease boundary no-device gate: `runtimeRouteRefreshLeaseDelayMillis` now sends an urgent authenticated route refresh immediately when the remaining active lease cannot accommodate the normal minimum delay, instead of scheduling at or after expiry. `RuntimeClientViewModelTest.runtimeRouteRefreshLeaseDelayRefreshesImmediatelyWhenMinimumDelayWouldOutliveLease` pins that boundary, while `remoteRouteLeaseHelpersSelectEarliestEligibleMixedRouteLease` proves mixed P2P/relay state selects the earliest active lease for renewal, skips routes without retry headroom, falls back to the nearest retryable alternate lease, tracks expired complete routes independently, and ignores incomplete or null route material. This is Android no-device timing/helper evidence only; authenticated route refresh remains diagnostic opt-in, and production P2P traversal, hardened relay/session infrastructure, optical QR scanning, live phone pairing, and real different-network proof remain separate.
Latest Android pending dual-route QR authority no-device gate: `RuntimeClientViewModelTest.runtimeRemoteRoutePlannerUsesOnlyMatchingPendingDualRouteMaterial` proves a matching pending pairing QR carrying both `p2p_rendezvous` and complete relay material plans `[PeerToPeer, Relay]`, binds both prepared routes to the QR-pinned runtime identity, keeps `route_token` out of P2P record and relay rendezvous material, and supersedes previously saved trusted P2P/relay material. This is Android route-planning evidence only; production P2P signaling/NAT traversal, hardened relay/session infrastructure, optical camera QR scanning, live phone pairing, direct Android backend access, and real different-network proof remain separate.
Latest Android private-overlay QR scanner acceptance no-device gate: Android `PairingQrScanResultTest.validCompactPrivateOverlayRouteQrReturnsValid` proves scanner raw-value classification accepts `shared/protocol/fixtures/macos-compact-private-overlay-pairing-uri.txt` as `PairingQrScanResult.Valid(rawUri)` through the runtime pairing parser with the default remote-route requirement. This keeps private-overlay QR route material from being rejected by the post-ML-Kit scanner prefilter before ViewModel pairing, while optical camera QR scanning, live phone pairing, production relay/session/encryption, direct Android backend access, and real different-network proof remain separate.
Latest Android retrieval.query selected embedding-model isolation no-device gate: Android `RuntimeClientViewModel` now has focused no-device coverage proving document search stays deterministic lexical `retrieval.query` even when a memory-indexing model is selected. `RuntimeClientViewModelTest.runtimeDocumentSearchDoesNotSendSelectedEmbeddingModelHint` selects an embedding model, sends a trimmed document search, proves the payload contains `query`, `limit`, and `max_snippet_characters` only for the active request shape, and keeps `embedding_model_id`, `source_anchor_id`, plus the selected model id out of the request before semantic retrieval, embedding-backed ranking, source approval, citations, trusted-source review, permission, or audit semantics exist.
Latest Android memory.list selected embedding-model isolation no-device gate: Android `RuntimeClientViewModel` now has focused no-device coverage proving `memory.list` query refresh stays lexical even when a memory-indexing model is selected. `RuntimeClientViewModelTest.refreshRuntimeMemorySearchDoesNotSendSelectedEmbeddingModelHint` selects an embedding model, refreshes memory with a trimmed query, proves the payload contains `query` only, and keeps `embedding_model_id` plus the selected model id out of the request before semantic memory search, embedding-backed ranking, source approval, citations, trusted-source review, permission, or audit semantics exist.
Latest Android auth.challenge closed-payload app-path no-device gate: Android `RuntimeClientViewModel` now rejects unknown runtime `auth.challenge` response metadata before device identity loading, runtime proof verification, auth.response signing/sending, authenticated session state, route-refresh scheduling, or runtime health/history/memory refresh fanout, then signs a canonical challenge retry on the same trusted relay auth path. `RuntimeClientViewModelTest.authChallengeRejectsUnknownMetadataBeforeAuthResponseSigning` injects `backend_url` into an auth challenge, proves Android reports `invalid_payload`, keeps the session unauthenticated, sends no `auth.response` or authenticated refresh requests, keeps the canary out of local storage, then signs a canonical `auth.challenge` retry.
Latest Android pairing.result closed-payload app-path no-device gate: Android `RuntimeClientViewModel` now rejects unknown `pairing.result` response metadata before trusted-runtime persistence, pending route cleanup, authenticated session state, or runtime health/history/memory refresh fanout, then accepts a canonical retry on the same compact relay QR pairing path. `RuntimeClientViewModelTest.pairingResultRejectsUnknownMetadataBeforeTrustMutation` injects `backend_url` into an accepted pairing result, proves Android keeps pending route/relay-secret state intact with no trusted runtime or authenticated refresh fanout, then accepts a canonical retry and clears pending pairing state.
Latest Android auth.response result closed-payload app-path no-device gate: Android `RuntimeClientViewModel` now rejects unknown runtime `auth.response` result metadata before authenticated session state mutation, route-refresh scheduling, or runtime health/history/memory refresh fanout, then accepts a canonical retry on the same auth path. `RuntimeClientViewModelTest.authResponseResultRejectsUnknownMetadataBeforeAuthenticationStateMutation` injects `backend_url` into an accepted auth result, proves Android reports `invalid_payload`, keeps the session unauthenticated, sends no authenticated refresh requests, then accepts a canonical `auth.response` retry.
Latest Android error payload closed-payload app-path no-device gate: Android `RuntimeClientViewModel` rejects unknown `error` payload metadata before active stream termination, route/auth state mutation, or device storage mutation. `RuntimeClientViewModelTest.errorPayloadRejectsUnknownMetadataBeforePendingStateMutation` proves an exact-current namespaced `memory.list` malformed error consumes only its correlation, permits a fresh replacement, and leaves a late canonical error for the closed id inert. `RuntimeClientViewModelTest.errorPayloadRejectsUnknownMetadataBeforeActiveStreamTermination` proves an active `chat.send` stream carrying `workspace_id` remains pending for canonical same-id retry. Both keep backend/workspace canaries out of state and storage.
Latest Android memory CRUD result closed-payload app-path no-device gate: Android `RuntimeClientViewModel` now rejects unknown `memory.upsert` result metadata before runtime memory publication, rejects unknown `memory.delete` result metadata before cached memory removal, and accepts canonical retries without letting result canaries mutate state/storage. `RuntimeClientViewModelTest.memoryUpsertResultRejectsUnknownMetadataBeforeMemoryMutation` injects `entry.source.source_pointers[0].backend_url`, and `RuntimeClientViewModelTest.memoryDeleteResultRejectsUnknownMetadataBeforeMemoryMutation` injects `workspace_id`, proving Android keeps canaries out of state/storage until canonical retry on the same request path.
Latest Android memory summary draft decision result closed-payload app-path no-device gate: Android `RuntimeClientViewModel` requires `memory.summary.draft.approve` and `memory.summary.draft.dismiss` results to match the exact pending request, channel, connection generation, and authenticated authority. Unknown-metadata results are terminal after correlation: they fail before runtime memory or review-state mutation, consume the correlation, clear pending action UI, drain one deferred refresh, and make a later canonical result carrying the old request id inert. `RuntimeClientViewModelTest.memorySummaryDraftApproveResultRejectsUnknownMetadataBeforeMemoryMutation` injects `entry.source.source_pointers[0].backend_url`, and `RuntimeClientViewModelTest.memorySummaryDraftDismissResultRejectsUnknownMetadataBeforeReviewStateMutation` injects `workspace_id`, proving Android keeps canaries out of state/storage and ignores each late canonical result.
Latest Android models.pull result and chat.cancel acknowledgement closed-payload app-path no-device gate: Android `RuntimeClientViewModel` now ignores stale `models.pull` result request ids, rejects unknown `models.pull` result metadata before install state mutation or model refresh fanout, and rejects unknown `chat.cancel` acknowledgement metadata before streaming cancellation or device storage mutation while preserving pending/active request state for canonical retry. `RuntimeClientViewModelTest.modelPullResultRejectsUnknownMetadataBeforeInstallStateMutation` injects `provider_url` into a model-pull result, and `RuntimeClientViewModelTest.chatCancelAckRejectsUnknownMetadataBeforeStreamingClear` injects `backend_url` into a cancellation acknowledgement, proving Android keeps canaries out of state/storage until canonical retry on the same request path.
Latest Android chat stream closed-payload app-path no-device gate: Android `RuntimeClientViewModel` now rejects unknown `chat.delta` response metadata and unknown top-level or nested `chat.done.usage` metadata before streaming message publication, completion side effects, title/history follow-up, or device storage mutation, while preserving the active stream for canonical retry. `RuntimeClientViewModelTest.chatDeltaRejectsUnknownMetadataBeforeMessagePublication` injects `backend_url` into a delta frame, and `RuntimeClientViewModelTest.chatDoneRejectsUnknownMetadataBeforeCompletionSideEffects` injects `usage.workspace_id` into a done frame, proving Android keeps canaries out of state/storage until canonical retry on the same request id.
Latest Android chat.session mutation result closed-payload app-path no-device gate: Android `RuntimeClientViewModel` now rejects unknown `chat.session.rename` and chat-session lifecycle acknowledgement metadata before runtime session cache publication or device storage mutation, preserves pending mutation requests for canonical retry, and clears stale `invalid_payload` after accepting canonical acknowledgements. `RuntimeClientChatSessionMutationFailureTest.chatSessionRenameResultRejectsUnknownMetadataBeforeCachePublication` injects `backend_url` into a rename acknowledgement, and `RuntimeClientChatSessionMutationFailureTest.chatSessionLifecycleResultRejectsUnknownMetadataBeforeCachePublication` injects `workspace_id` into an archive acknowledgement, proving Android keeps canaries out of state/storage until the canonical retry on the same request id.
Latest Android chat.title.result closed-payload app-path no-device gate: Android `RuntimeClientViewModel` now rejects unknown `chat.title.result` response metadata before generated-title publication or device storage mutation, preserves the pending title request for canonical retry, and clears stale `invalid_payload` after accepting `ChatTitleResultPayload(title = "Canonical Generated Title")`. `RuntimeClientViewModelTest.chatTitleResultRejectsUnknownMetadataBeforeGeneratedTitlePublication` drives a real `chat.send` / `chat.done` title-request flow, injects `backend_url`, proves Android keeps the session untitled and canary-free, then accepts the canonical retry on the same request id.
Latest Android memory.summary.drafts.list closed-payload app-path no-device gate: Android `RuntimeClientViewModel` now rejects unknown top-level `memory.summary.drafts.list` response metadata, unknown per-draft metadata, unknown draft session metadata, and unknown draft source-pointer metadata before the permissive app decoder can publish memory review state. `RuntimeClientViewModelTest.memorySummaryDraftsListRejectsUnknownMetadataBeforeReviewStatePublication` injects `backend_url`, `drafts[0].workspace_id`, `drafts[0].session.backend_url`, and `drafts[0].source_pointers[0].source_path` canaries, proves Android reports `invalid_payload`, keeps review state/storage unchanged, and accepts a canonical retry.
Latest Android chat.messages.list closed-payload app-path no-device gate: Android `RuntimeClientViewModel` now rejects unknown top-level `chat.messages.list` response metadata, unknown stored-message metadata, and unknown stored-attachment metadata before the permissive app decoder can publish transcript state or mutate device storage, while preserving runtime-only `compaction_metadata`/`source_pointers` projection compatibility. `RuntimeClientViewModelTest.chatMessagesListRejectsUnknownMetadataBeforeTranscriptPublication` injects `backend_url` and `messages[0].workspace_id` canaries, proves Android reports `invalid_payload`, keeps transcript state/storage unchanged, and accepts a canonical retry.
Latest Android memory.list closed-payload app-path no-device gate: Android `RuntimeClientViewModel` now rejects unknown top-level `memory.list` response metadata, unknown per-entry metadata, unknown nested search metadata, and unknown approved-memory source/session/source-pointer metadata before the permissive app decoder can publish runtime memory state or mutate device storage. `RuntimeClientViewModelTest.memoryListRejectsUnknownMetadataBeforeMemoryStatePublication` injects `backend_url`, `entries[0].workspace_id`, `entries[0].source.source_path`, and `entries[0].source.source_pointers[0].backend_url` canaries, proves Android reports `invalid_payload`, keeps memory state/storage unchanged, and accepts a canonical retry.
Latest Android chat.messages.list stored attachment safe-metadata no-device gate: Android `ChatStoredAttachmentPayload` now keeps stored transcript attachments limited to `type`, `mime_type`, `name`, and `text`, while outbound `chat.send` still uses `ChatAttachmentPayload.dataBase64` for runtime-mediated uploads. `ProtocolCodecTest.chatMessagesListRejectsInlineStoredAttachmentBytes` proves inline stored attachment `data_base64` is rejected during protocol decode, and `RuntimeClientViewModelTest.chatMessagesListRejectsInlineStoredAttachmentBytesBeforeTranscriptPublication` proves the permissive app path reports `invalid_payload` before transcript publication or device storage mutation.
Latest Android chat.sessions.list closed-payload app-path no-device gate: Android `RuntimeClientViewModel` now rejects unknown top-level `chat.sessions.list` response metadata, unknown per-session metadata, and unknown nested search metadata before the permissive app decoder can publish runtime chat-history state or mutate device storage. `RuntimeClientViewModelTest.chatSessionsListRejectsUnknownMetadataBeforeHistoryStatePublication` injects `backend_url`, `sessions[0].workspace_id`, and `sessions[0].search.source_path` canaries, proves Android reports `invalid_payload`, keeps chat-history state/storage unchanged, and publishes a canonical retry.
Latest Android runtime.health closed-payload app-path no-device gate: Android `RuntimeClientViewModel` now rejects unknown top-level `runtime.health` response metadata, unknown provider metadata, unknown model-residency metadata, and unknown nested model-residency unload-failure metadata before the permissive app decoder can publish runtime/provider/residency state or trigger authenticated follow-up refresh fanout. `RuntimeClientViewModelTest.runtimeHealthRejectsUnknownMetadataBeforeRuntimeStatePublication` injects `backend_url`, `ollama.provider_url`, `model_residency.workspace_id`, and `model_residency.last_unload_failure.backend_url` canaries, proves Android reports `invalid_payload`, keeps prior runtime/provider/residency state, suppresses model/chat-history/memory refresh fanout on rejection, and recovers on a canonical retry.
Latest Android chat and memory timestamp date-time decode no-device gate: Android chat-history and memory protocol DTOs now reject malformed, date-only, and timezone-less timestamp metadata for chat session summaries, stored chat messages, chat session mutation result timestamps, memory entries, memory delete results, memory summary draft dismiss results, memory summary draft sessions, and memory summary draft source pointers. `ProtocolCodecTest.chatAndMemoryPayloadsRejectInvalidTimestampMetadata` proves invalid `last_activity_at`, `archived_at`, `created_at`, `renamed_at`, `restored_at`, `deleted_at`, `updated_at`, and `dismissed_at` values fail before Android chat-history state, memory review state, local persistence, source approval, citation, trusted-source review, permission/audit behavior, direct Android backend access, physical Android proof, optical QR, production relay/session/encryption, or real different-network proof.
Latest Android models.result closed-payload app-path no-device gate: Android `RuntimeClientViewModel` now rejects unknown top-level `models.result` response metadata and unknown per-model route/provider metadata before the app path can publish a refreshed model list under its permissive JSON decoder. `RuntimeClientViewModelTest.modelsResultRejectsUnknownMetadataBeforeModelStatePublication` injects `route_token`, `provider_url`, and `backend_url` canaries, proves Android reports `invalid_payload`, keeps the previous model list after rejection, and recovers on a canonical retry. Legacy Android `kind` and `description` fields remain allowed, so this is a route/provider metadata fail-closed gate rather than full strict schema parity for legacy fields.
Latest Android model modified_at date-time decode no-device gate: Android `ModelInfoPayload` now rejects malformed, date-only, and timezone-less `modified_at` values during `models.result` DTO decode, aligning Android with the shared `modelInfo.modified_at` `date-time` contract. `ProtocolCodecTest.modelInfoPayloadRejectsInvalidModifiedAtMetadata` proves invalid model timestamp metadata fails before Android model selection state, runtime-side compaction budgets, provider API access, live-provider behavior, direct Android backend access, physical Android proof, optical QR, production relay/session/encryption, or real different-network proof.
Latest Android model scalar metadata decode no-device gate: Android `ModelInfoPayload` now rejects empty `id` values, missing or empty `name` values, unsupported `backend`, `provider`, `model_kind`, and `source` values, and duplicate `capabilities` entries during `models.result` DTO decode, aligning Android with the shared `modelInfo` required-field, enum, and unique-capability contracts without claiming full strict schema parity for legacy Android-only fields. `ProtocolCodecTest.modelInfoPayloadRejectsInvalidScalarMetadata` proves invalid scalar model metadata fails before Android model selection state, runtime-side compaction budgets, provider API access, live-provider behavior, direct Android backend access, physical Android proof, optical QR, production relay/session/encryption, or real different-network proof.
Latest Android route.refresh complete route-material decode no-device gate: Android `RouteRefreshPayload` now accepts empty route-refresh responses and complete relay or P2P route-material families, but rejects identity-only, missing-runtime-identity, partial relay, `relay_scope`-only, partial P2P, and missing-`p2p_class` payloads during JSON DTO decode. `ProtocolCodecTest.routeRefreshPayloadRequiresCompleteRouteMaterialFamilies` proves this at the no-device Android JVM protocol layer before trusted route storage, route-refresh retry handling, live relay/P2P behavior, direct Android backend access, physical Android proof, optical QR, production relay/session/encryption, or real different-network proof.
Latest Android route.refresh scalar route-material decode no-device gate: Android `RouteRefreshPayload` now rejects schema-invalid scalar relay and P2P route material during JSON DTO decode, including noncanonical opaque route values, invalid relay ports, nonpositive expiries, unsupported `relay_scope` values, unsupported `p2p_class` values, oversized encrypted bodies, and unsupported `p2p_protocol_version` values before trusted route storage or route-refresh retry handling. `ProtocolCodecTest.routeRefreshPayloadRejectsInvalidScalarRouteMaterial` proves this at the no-device Android JVM protocol layer before live relay/P2P behavior, direct Android backend access, physical Android proof, optical QR, production relay/session/encryption, or real different-network proof.
Latest Android runtime.health status enum decode no-device gate: Android `RuntimeHealthPayload` now rejects unsupported `status` values outside `ok`, `degraded`, or `unavailable` during DTO decode, matching the shared `runtime.health` response enum before malformed runtime-health frames can update Android runtime status state. `script/check_protocol_schema.py` now also fails if the shared `runtime.health.status` enum drifts away from the same three values. `ProtocolCodecTest.runtimeHealthPayloadRejectsInvalidStatus` proves invalid status values fail before Android runtime-health status state, provider status UI state, live-provider behavior, direct Android backend access, physical Android proof, optical QR, production relay/session/encryption, or real different-network proof.
Latest Android runtime.health backend status minimal decode no-device gate: Android `RuntimeBackendStatusPayload` now accepts schema-valid backend health objects that carry only `available`, treating omitted `message`, `code`, and `retryable` as absent metadata before provider-status UI mapping. `script/check_protocol_schema.py` now also fails if `backendHealth` stops requiring only `available` or stops keeping `message`, `code`, and `retryable` optional typed metadata. `ProtocolCodecTest.runtimeHealthBackendStatusAcceptsSchemaMinimalPayload` proves minimal provider-health runtime responses decode before Android runtime-health provider status UI state, live-provider behavior, direct Android backend access, physical Android proof, optical QR, production relay/session/encryption, or real different-network proof.
Latest Android memory.list request bounds decode no-device gate: Android `MemoryListRequestPayload` now rejects empty `query` values during DTO decode, matching the shared `memory.list` request contract where omitted `query` means an unfiltered list but present `query` must be non-empty. `script/check_protocol_schema.py` now also fails if `memoryListPayload.query` drifts away from `nonEmptyString`. `ProtocolCodecTest.memoryListRequestRejectsInvalidBounds` proves malformed memory-list search requests fail before runtime memory-store search dispatch, local persistence, memory source approval, citations, trusted-source review, permission/audit semantics, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest Android retrieval.query response array bounds decode no-device gate: Android `RetrievalQueryResultPayload` now rejects over-100 `retrieval.query` result arrays during DTO decode, matching the shared protocol response ceiling. `ProtocolCodecTest.retrievalQueryResponseRejectsTooManyResults` proves 101-row retrieval responses fail before Android transient document search state, resolver consumption, local persistence, chat context injection, semantic retrieval, source approval, citations, trusted-source review, permission/audit semantics, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest Android document metadata response bounds decode no-device gate: Android `RuntimeDocumentIndexDocumentPayload`, `IndexDocumentsListResultPayload`, `IndexDocumentsSummaryPayload`, and `IndexDocumentsQualityCountsPayload` now reject empty or overlong document ids/display names, malformed or overlong MIME values, negative document counts, invalid quality values, `quality`/`chunk_count` mismatches, over-100 catalog document arrays, and negative summary or quality-count values during DTO decode. `ProtocolCodecTest.indexDocumentsListResponseRejectsInvalidDocumentMetadataBounds`, `ProtocolCodecTest.indexDocumentsListResponseRejectsInvalidSummaryBounds`, and `ProtocolCodecTest.retrievalAndSourceAnchorDocumentMetadataRejectsInvalidBounds` prove malformed catalog, retrieval, and source-anchor resolver document metadata fails before Android transient document state, resolver consumption, local persistence, chat context injection, semantic retrieval, source approval, citations, trusted-source review, permission/audit semantics, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest Android memory summary draft response bounds decode no-device gate: Android `MemorySummaryDraftPayload`, `MemorySummaryDraftSessionPayload`, `MemorySummaryDraftSourcePointerPayload`, `MemoryEntryPayload`, and `MemoryEntrySourcePayload` now reject empty ids, content, source ranges, source pointers, summary previews, and source excerpts, nonpositive source-message counts, negative session counters, invalid source-pointer roles, and invalid approved-memory source `kind` or `summary_method` values during DTO decode. `ProtocolCodecTest.memorySummaryDraftResponsePayloadsRejectInvalidBounds` proves malformed memory-summary draft list responses and approved-memory source metadata fail before Android memory review UI state, runtime-owned memory state, local persistence, source approval, citations, trusted-source review, permission/audit semantics, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest Android error payload code enum decode no-device gate: shared `error.payload.code` schema, protocol docs, schema hygiene, and Android `ErrorPayload` now use the same canonical protocol error code set, including active route-refresh, chat-session, document-index, source-anchor, and memory-summary draft codes. Android rejects unknown, blank, or whitespace-mutated error payload codes during DTO decode, and Android test fixtures now use canonical protocol error codes instead of ad hoc runtime error names. `ProtocolCodecTest.errorPayloadAcceptsKnownProtocolCodes` and `ProtocolCodecTest.errorPayloadRejectsUnknownCodes` prove error-code enum parity before malformed runtime error frames can update Android runtime UI state, local persistence, source approval, citations, trusted-source review, permission/audit semantics, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest Android chat.sessions.list response bounds decode no-device gate: Android `ChatSessionSummaryPayload` now rejects empty `session_id` values, negative `message_count` values, unsupported `status` values, and unsupported `last_event` values during DTO decode, while `ChatSessionSearchPayload` rejects nonpositive `rank` values, empty `matched_fields` arrays, empty matched-field entries, and duplicate `matched_fields` values. `ProtocolCodecTest.chatSessionsListResponseRejectsInvalidBounds` proves invalid `chat.sessions.list` response bounds fail before Android chat-history UI state, local persistence, workspace search, source approval, citations, trusted-source review, permission/audit semantics, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest Android runtime.health model-residency numeric bounds decode no-device gate: Android `RuntimeModelResidencyPayload` now rejects negative `in_flight_generations` values and negative `idle_unload_delay_seconds` values during DTO decode, aligning Android with the shared `runtime.health.model_residency` schema before malformed runtime-health frames can update Android runtime status or model residency UI state. `ProtocolCodecTest.runtimeHealthPayloadRejectsInvalidModelResidencyBounds` proves invalid model-residency numeric values fail before Android runtime-health status state, model residency UI, provider lifecycle hints, live-provider behavior, direct Android backend access, physical Android proof, optical QR, or real different-network proof.
Latest Android chat stream response bounds decode no-device gate: Android `ChatDeltaPayload` now rejects empty stream delta payloads, `ChatDonePayload` rejects unsupported `finish_reason` values, and `UsagePayload` rejects negative `input_tokens` or `output_tokens` values during DTO decode, aligning Android with the shared `chat.delta` and `chat.done` response schema before malformed runtime stream frames can update Android streaming UI state. `ProtocolCodecTest.chatStreamResponsePayloadsRejectInvalidBounds` proves invalid chat stream responses fail before Android streaming UI state, local persistence, title generation, live-provider behavior, production relay/session/encryption, direct Android backend access, physical Android proof, optical QR, or real different-network proof.
Latest Android chat.send request bounds decode no-device gate: Android `ChatSendPayload` now rejects blank `session_id` values, blank `model` values, empty `messages` arrays, invalid nested message `role` values, invalid attachment `type` values, and empty attachment `mime_type` values during DTO decode, aligning Android with the shared `chat.send` request schema before protocol consumers can build malformed active chat dispatch payloads. `ProtocolCodecTest.chatSendRequestRejectsInvalidBounds` proves invalid chat-send request bounds fail before runtime chat dispatch, local persistence, context compaction, live-provider behavior, production relay/session/encryption, direct Android backend access, physical Android proof, optical QR, or real different-network proof.
Latest Android model pull, chat cancel, and memory CRUD request bounds decode no-device gate: Android `ModelPullPayload` now rejects blank `model` values, `ChatCancelPayload` rejects blank `target_request_id` values, `MemoryUpsertPayload` rejects blank optional `id` values and blank `content` values, and `MemoryDeletePayload` rejects blank `id` values during DTO decode. `ProtocolCodecTest.modelPullAndChatCancelRequestsRejectInvalidBounds` and `ProtocolCodecTest.memoryCrudRequestsRejectInvalidBounds` prove invalid active model-install, cancel, and memory CRUD requests fail before runtime model installation dispatch, active generation cancellation, runtime memory-store mutation, local persistence, memory source approval, citations, trusted-source review, permission/audit semantics, physical Android proof, optical QR, production relay/session/encryption, direct Android backend access, live-provider behavior, or real different-network proof.
Latest Android chat title and session mutation request bounds decode no-device gate: Android `ChatTitleRequestPayload` now rejects blank `session_id` values, blank `model` values, and empty `messages` arrays; `ChatSessionRenamePayload` rejects blank `session_id` and `title` values; and `ChatSessionLifecyclePayload` rejects blank `session_id` values during DTO decode. `ProtocolCodecTest.chatTitleAndSessionMutationRequestsRejectInvalidBounds` proves invalid title, rename, archive, restore, and delete request bounds fail before backend title generation, runtime title mutation, runtime chat-store lifecycle mutation, local persistence, source approval, citations, trusted-source review, permission/audit semantics, physical Android proof, optical QR, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest Android memory summary draft request bounds decode no-device gate: Android `MemorySummaryDraftsListRequestPayload` now rejects negative and over-maximum `limit` values, while `MemorySummaryDraftApprovePayload` and `MemorySummaryDraftDismissPayload` reject blank `draft_id` values, blank optional `content` or `expected_session_id` values, and nonpositive `expected_source_message_count` values during DTO decode. `ProtocolCodecTest.memorySummaryDraftsListRequestRejectsInvalidBounds` and `ProtocolCodecTest.memorySummaryDraftDecisionRequestsRejectInvalidBounds` prove invalid memory-summary draft requests fail before runtime chat-store draft listing or recomputation, memory upsert, dismiss mutation, local persistence, source approval, citations, trusted-source review, permission/audit semantics, physical Android proof, optical QR, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest Android chat.messages.list request bounds decode no-device gate: Android `ChatMessagesListRequestPayload` now rejects blank `session_id` values plus negative and over-maximum `limit` values during DTO decode, aligning Android with the shared schema request contract. `ProtocolCodecTest.chatMessagesListRequestRejectsInvalidBounds` proves invalid `chat.messages.list` request bounds fail before runtime chat-store dispatch, local persistence, chat compaction metadata projection, source approval, citations, trusted-source review, permission/audit semantics, physical Android proof, optical QR, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest Android model numeric metadata decode no-device gate: Android `ModelInfoPayload` now rejects negative `size_bytes` values and nonpositive `context_window_tokens` values during `models.result` DTO decode, aligning Android with the shared schema numeric metadata contracts. `ProtocolCodecTest.modelInfoPayloadRejectsInvalidNumericMetadata` proves invalid model numeric metadata fails before Android model selection state, runtime-side compaction budgets, provider API access, live-provider behavior, direct Android backend access, physical Android proof, optical QR, production relay/session/encryption, or real different-network proof.
Latest Android chat.sessions.list request bounds decode no-device gate: Android `ChatSessionsListRequestPayload` now rejects negative and over-maximum `limit` values, empty `query` text, and empty `embedding_model_id` values during DTO decode. `ProtocolCodecTest.chatSessionsListRequestRejectsInvalidBounds` proves invalid `chat.sessions.list` request bounds fail before runtime chat-store dispatch, embedding search-hint handling, local persistence, workspace search, source approval, citations, trusted-source review, permission/audit semantics, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest Android document retrieval request bounds decode no-device gate: Android `IndexDocumentsListRequestPayload` now rejects negative and over-maximum `limit` values during DTO decode, and `RetrievalQueryRequestPayload` rejects blank or overlong `query` text, negative or over-maximum `limit` values, and negative or over-maximum `max_snippet_characters` values during DTO decode. `ProtocolCodecTest.indexDocumentsListRequestRejectsInvalidBounds` and `ProtocolCodecTest.retrievalQueryRequestRejectsInvalidBounds` prove invalid document retrieval request bounds fail before runtime dispatch, semantic retrieval, resolver dispatch, local persistence, chat context injection, source approval, citations, trusted-source review, permission/audit semantics, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest Android retrieval lexical metadata decode no-device gate: Android `RetrievalQueryResultItemPayload` now rejects empty `matched_terms` arrays, over-maximum `matched_terms` arrays, empty matched term entries, overlong matched term entries, empty snippets, and overlong snippets during DTO decode. `ProtocolCodecTest.retrievalQueryResultRejectsInvalidLexicalMetadata` and `RuntimeClientViewModelTest.runtimeDocumentSearchRejectsInvalidLexicalMetadataBeforeTransientState` prove malformed `retrieval.query` lexical metadata fails with `invalid_payload` before transient `source_anchor_id` state, resolver dispatch, local persistence, chat context injection, source approval, citations, trusted-source review, permission/audit semantics, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, semantic retrieval, or real different-network proof.
Latest Android retrieval/source-anchor coordinate decode no-device gate: Android `RetrievalQueryResultItemPayload` now rejects negative `chunk_index`, negative character offsets, end-before-start offsets, and nonpositive `rank` values during DTO decode, and `SourceAnchorChunkSummaryPayload` rejects the same invalid resolver `chunk_summary` coordinate family before resolver consumption. `ProtocolCodecTest.retrievalQueryResultRejectsInvalidCoordinatesAndRank`, `ProtocolCodecTest.sourceAnchorResolveResultRejectsInvalidChunkSummaryValues`, and `RuntimeClientViewModelTest.runtimeDocumentSearchRejectsInvalidCoordinatesAndRankBeforeTransientState` prove invalid `retrieval.query` coordinate/rank values fail with `invalid_payload` before transient `source_anchor_id` state, resolver dispatch, local persistence, chat context injection, source approval, citations, trusted-source review, permission/audit semantics, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, semantic retrieval, or real different-network proof.
Latest Android document response future-metadata fail-closed no-device gate: Android `RuntimeClientViewModel` now rejects unknown future/private metadata in active `index.documents.list` catalog responses and `retrieval.query` search responses before permissive DTO decoding can ignore it. Raw response guards accept only schema-owned catalog, summary, retrieval result, and nested document keys, and `RuntimeClientViewModelTest.runtimeDocumentResponsesRejectUnknownFutureMetadataBeforeTransientState` proves `source_path` and `retrieval_context` canaries fail with `invalid_payload` before transient document state, local persistence, chat context injection, source approval, citations, trusted-source review, permission/audit semantics, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, semantic retrieval, or real different-network proof.
Latest Android document content-fingerprint canonical decode no-device gate: Android `RuntimeDocumentIndexDocumentPayload` now rejects noncanonical `content_fingerprint` values during DTO decode with the shared 16-character lowercase hex contract. `ProtocolCodecTest.indexDocumentsListRejectsNonCanonicalContentFingerprints`, `ProtocolCodecTest.retrievalQueryResultRejectsNonCanonicalDocumentContentFingerprints`, and `ProtocolCodecTest.sourceAnchorResolveResultRejectsNonCanonicalDocumentContentFingerprints` prove malformed catalog, retrieval, and resolver document fingerprints fail before Android transient document state, resolver consumption, local persistence, chat context injection, source approval, citations, trusted-source review, permission/audit semantics, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, semantic retrieval, or real different-network proof.
Latest Android unsolicited source-anchor resolver future-metadata boundary no-device gate: Android keeps `source_anchor.resolve` protocol support at DTO parity only for now, and `RuntimeClientViewModelTest.runtimeIgnoresUnsolicitedSourceAnchorResolveResultWithoutAdvertisingOrPersisting` now injects a raw unsolicited resolver frame carrying future/private `chunk_text`, `snippet`, `source_path`, `retrieval_context`, `citations`, `trusted_source`, `approval_state`, and `backend_url` canaries. The test proves Android still does not advertise `source_anchor.resolve`, does not send resolver requests, ignores the unsolicited result, preserves existing transient `retrieval.query` rows, leaves local persistence unchanged, and keeps resolver metadata, future source/trust/citation metadata, and backend URL material out of later `chat.send` payloads before Android UI resolver consumption, source approval, citations, trusted-source review, permission/audit semantics, local persistence, chat context injection, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, semantic retrieval, or real different-network proof.
Latest Android source-anchor canonical decode no-device gate: Android protocol DTO decode now rejects noncanonical `source_anchor_id` values for `retrieval.query` results and `source_anchor.resolve` requests/responses with the shared `source_anchor_[16 lowercase hex]` contract. `ProtocolCodecTest.retrievalQueryResultRejectsNonCanonicalSourceAnchorIds`, `ProtocolCodecTest.sourceAnchorResolveRequestRejectsNonCanonicalSourceAnchorIds`, and `ProtocolCodecTest.sourceAnchorResolveResultRejectsNonCanonicalSourceAnchorIds` prove whitespace, uppercase, malformed, short, long, and empty handles fail before Android transient state, resolver dispatch, source approval, citations, trusted-source review, permission/audit semantics, UI resolver consumption, local persistence, chat context injection, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, semantic retrieval, or real different-network proof.
Latest macOS source-anchor resolver request required-field router no-device gate: authenticated `LocalRuntimeMessageRouter` now rejects `source_anchor.resolve` requests with missing, empty, whitespace-only, or non-string `source_anchor_id` values as `invalid_payload` before source-anchor store dispatch. `LocalRuntimeMessageRouterTests/testSourceAnchorResolveRejectsMissingBlankOrNonStringAnchorBeforeStoreDispatch` proves the active resolver request gate fails closed at the router boundary, aligning macOS runtime behavior with the shared schema and Android DTO required-field evidence before source approval, citations, trusted-source review, permission/audit semantics, Android UI resolver consumption, local persistence, chat context injection, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, semantic retrieval, or real different-network proof.
Latest Android source-anchor resolver request required-field decode no-device gate: Android `SourceAnchorResolveRequestPayload` now rejects missing `source_anchor_id` during DTO decode. `ProtocolCodecTest.sourceAnchorResolveRequestRejectsMissingRequiredField` runs the real Kotlin serialization DTO against an empty request payload and requires the missing-field error to name `source_anchor_id`, while Android still does not advertise, send, persist, consume, or display `source_anchor.resolve` requests. This keeps resolver request parity aligned with the shared schema before Android UI resolver consumption, local persistence, chat context injection, source approval, citations, trusted-source review, permission/audit semantics, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, semantic retrieval, or real different-network proof.
Latest Android source-anchor resolver required-field decode no-device gate: Android `SourceAnchorResolveResultPayload` now rejects missing `source_anchor_id`, `document`, `chunk_summary`, and every nested `chunk_summary` required field, including `chunk_index`, `start_character_offset`, `end_character_offset`, and `character_count`, during DTO decode. `ProtocolCodecTest.sourceAnchorResolveResultRejectsMissingRequiredFields` runs through the real Kotlin serialization DTO and names the missing field in each failure before source-anchor resolver parity can be mistaken for Android UI resolver consumption, local persistence, chat context injection, source approval, citations, trusted-source review, permission/audit semantics, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, semantic retrieval, or real different-network proof.
Latest protocol source-anchor resolver payload sample no-device gate: protocol schema hygiene now validates complete `source_anchor.resolve` request and response payload samples. Requests require only canonical `source_anchor_id`, reject response-only `document` and `chunk_summary`, reject future resolver metadata, and reject non-string or noncanonical handles. Responses require `source_anchor_id`, `document`, and `chunk_summary`, reject unknown resolver/document/chunk metadata, reject missing nested `chunk_index`, non-integer or negative chunk summary counts, and reject end-before-start offsets before source approval, citation, trusted-source review, permission/audit semantics, Android UI resolver consumption, local persistence, chat context injection, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, semantic retrieval, or real different-network proof.
Latest RuntimeDevServer reserved source-anchor namespace rejection no-device gate: `source_anchor.resolve` remains the only active read-only `source_anchor.` runtime message. Protocol schema hygiene now uses `source_anchor.metadata.get` as a synthetic future `source_anchor.*` canary, and the authenticated RuntimeDevServer relay smoke rejects the same canary with `unknown_message_type` while still accepting `source_anchor.resolve` for a seeded retrieval source anchor. This keeps future source-anchor metadata, approval, citation, trusted-source review, permission, and audit flows reserved without widening Android UI/client resolver consumption, local persistence, chat context injection, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, semantic retrieval, or real different-network proof.
Latest Android unsolicited source-anchor resolver boundary no-device gate: Android keeps `source_anchor.resolve` protocol support at DTO parity only for now. `RuntimeClientViewModelTest.runtimeIgnoresUnsolicitedSourceAnchorResolveResultWithoutAdvertisingOrPersisting` proves Android does not advertise `source_anchor.resolve` in default or diagnostic `client_capabilities`, does not send resolver requests, ignores an unsolicited `source_anchor.resolve` result, preserves existing transient `retrieval.query` rows only, leaves local persistence unchanged, and keeps resolver document metadata, `chunk_summary`, and `source_anchor_id` values out of later `chat.send` payloads. This keeps Android UI/client resolver consumption blocked until product surface, approval, citation, trusted-source review, permission, and audit semantics are designed. This is no-device Android JVM evidence only; physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, semantic retrieval, source approval, citations, trusted-source review, permission/audit behavior, Android UI consumption, local persistence, chat context injection, and real different-network proof remain separate.
Latest source_anchor.resolve protocol no-device gate: `source_anchor.resolve` is now the only active read-only `source_anchor.` runtime message. Authenticated requests accept only a canonical `source_anchor_id`, and responses return only `source_anchor_id`, safe document catalog metadata, and `chunk_summary` offsets/counts. macOS router tests, shared protocol schema hygiene, Android DTO parity tests, and RuntimeDevServer authenticated relay smoke prove malformed handles fail with `invalid_payload`, stale canonical handles fail with `source_anchor_not_found`, unknown resolver metadata is rejected before store dispatch, and chunk text, snippets, source paths, workspace/project IDs, `retrieval_context`, embeddings, citations, trusted-source fields, approval state, backend URLs, and route material stay out of resolver responses. This is no-device protocol/router/schema/DTO/smoke evidence only; physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, semantic retrieval, source approval, citations, trusted-source review, permission/audit behavior, Android UI consumption, local persistence, chat context injection, and real different-network proof remain separate.
Historical RuntimeDevServer source-anchor resolver checkpoint, superseded by the current citation/trusted-source section above: the relay smoke accepted `source_anchor.resolve` for a seeded `retrieval.query` source anchor and rejected unknown resolver metadata, malformed handles, and stale canonical handles. At that checkpoint `trusted_source.approve` intentionally returned `unknown_message_type`; the current smoke now exercises the active approve/dismiss/list/revoke lifecycle while unsupported source-anchor names remain reserved.
Latest RuntimeDevServer retrieval.query request bounds no-device smoke gate: authenticated RuntimeDevServer relay smoke rejects oversized `retrieval.query` request text longer than 1024 characters with `invalid_payload` before the seeded document-index retrieval path, and verifies the error payload names the `query` ceiling. This makes the RuntimeDevServer authenticated relay smoke exercise the same request ceiling already pinned by the shared schema and `LocalRuntimeMessageRouter`, instead of leaving that bound visible only at router/unit-test level. This keeps active document retrieval bounded before semantic retrieval, embeddings, resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, Android UI consumption, local persistence, chat context injection, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest macOS retrieval.query request bounds no-device gate: authenticated `LocalRuntimeMessageRouter` now rejects `retrieval.query` request `query` text longer than 1024 characters with `invalid_payload` before document-index store dispatch. `LocalRuntimeMessageRouterTests/testRetrievalQueryRejectsOversizedQueryBeforeStoreDispatch` proves the router enforces the same request ceiling already pinned by the shared schema and `RuntimeDocumentIndexStore`, instead of letting overlong protocol requests fall through as empty lexical results. This keeps active document retrieval bounded before semantic retrieval, embeddings, resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, Android UI consumption, local persistence, chat context injection, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest Android document catalog disconnect transient clear no-device gate: Android `RuntimeClientViewModel` now clears transient `index.documents.list` `documentCatalog` rows and summary values on explicit disconnect and receive failure. `RuntimeClientViewModelTest.runtimeDocumentCatalogClearsTransientRowsOnDisconnect` proves runtime-owned catalog metadata disappears with the closed authenticated session instead of surviving as stale document UI state. This keeps runtime document catalog metadata connection-scoped and transient before semantic retrieval, resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, local persistence, chat context injection, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest Android document search disconnect transient clear no-device gate: Android `RuntimeClientViewModel` now clears transient `retrieval.query` `documentSearchQuery`, `documentSearchResults`, and `source_anchor_id` values on explicit disconnect and receive failure. `RuntimeClientViewModelTest.runtimeDocumentSearchClearsTransientResultsAndSourceAnchorsOnDisconnect` proves canonical source anchors disappear with the closed runtime session instead of surviving as stale UI state. This keeps source-anchor handles connection-scoped and transient before resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, local persistence, chat context injection, semantic retrieval, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest Android retrieval matched-terms required decode no-device gate: Android `RetrievalQueryResultItemPayload` now requires `matched_terms` during `retrieval.query` result decode instead of supplying an empty compatibility default, and `ProtocolCodecTest.retrievalQueryResultRejectsMissingMatchedTerms` rejects result rows missing lexical matched-term metadata. This aligns Android DTO decode with the shared schema required-field contract before Android transient lexical metadata canonicalization, semantic retrieval, resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, local persistence, chat context injection, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest Android retrieval source-anchor required decode no-device gate: Android `RetrievalQueryResultItemPayload` now requires `source_anchor_id` during `retrieval.query` result decode instead of supplying an empty compatibility default, and `ProtocolCodecTest.retrievalQueryResultRejectsMissingSourceAnchorId` rejects result rows missing the response-only source anchor. This aligns Android DTO decode with the shared schema required-field contract before Android transient state, resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, local persistence, chat context injection, semantic retrieval, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest Android document search pending invalidation no-device gate: Android `RuntimeClientViewModel` now clears pending `retrieval.query` request tracking when a user submits a blank or overlong document search, so stale runtime responses from superseded invalid searches cannot repopulate transient document search state and a fresh bounded search can be sent immediately. This keeps document search cancellation-by-input local to transient `RuntimeUiState` and avoids local persistence, chat context injection, semantic retrieval, source approval, citations, trusted-source review, permission/audit behavior, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest Android client capability future Workspace/RAG/source deny-list no-device gate: Android `runtimeClientCapabilities` continues to advertise active `index.documents.list` and `retrieval.query` capabilities while the new ViewModel regression keeps future Workspace/RAG/source, tool, permission/audit, memory-search, and route-diagnostics capability strings out of both default and diagnostic hello `client_capabilities`. This prevents Android from prematurely claiming unsupported `embeddings.create`, `index.build`, `research.brief.create`, `citation.sources.list`, `source_anchor.resolve`, `trusted_source.approve`, `source_control.status`, `projects.sessions.list`, `memory.search`, or `route.candidates.exchange` semantics before the runtime protocol and product surfaces exist. This is no-device capability-contract evidence only; physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, semantic retrieval, source approval, citations, trusted-source review, permission/audit behavior, and real different-network proof remain separate.
Latest Android document response row transient-state cap no-device gate: Android `RuntimeClientViewModel` now caps decoded `index.documents.list` catalog rows at 100 and decoded `retrieval.query` search rows at 10 before they reach transient `RuntimeUiState`, matching the Android request limits even if a malformed-but-decodable runtime response exceeds the requested window. This keeps oversized document response arrays bounded before local persistence, chat context injection, semantic retrieval, resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest Android retrieval query outbound bounds no-device gate: Android `RuntimeClientViewModel` now rejects document search queries longer than 1024 characters before emitting `retrieval.query`, matching the shared protocol request ceiling and runtime document-index query resource guard before relay/runtime dispatch. This keeps Android outbound document search bounded before local persistence, chat context injection, semantic retrieval, resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest Android document catalog summary transient-state no-device gate: Android `RuntimeClientViewModel` now maps `index.documents.list` catalog summaries through an explicit summary canonicalizer so `document_count`, `chunk_count`, `extracted_character_count`, and all `quality_counts` values become nonnegative transient catalog summary counts before reaching `RuntimeUiState`. This aligns Android catalog summary state with the shared nonnegative schema and runtime summary contract before local persistence, chat context injection, semantic retrieval, resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest Android document ID/display-name transient-state no-device gate: Android `RuntimeClientViewModel` now bounds safe document label metadata before runtime-owned document catalog rows and nested `retrieval.query` search result documents reach transient `RuntimeUiState`. Document ids are trimmed, required to be nonblank, control-free, and at most 128 characters, with response-local `document_N` fallbacks for malformed ids. Display names are reduced to bounded final path components or `untitled-document`, so path-shaped, blank, dot-component, control-character, and overlong names cannot render as raw runtime metadata. This aligns Android app state with the shared document string-bounds schema and macOS runtime document-index label canonicality before local persistence, chat context injection, semantic retrieval, resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest Android document quality/chunk-count transient-state no-device gate: Android `RuntimeClientViewModel` now derives transient document quality from the nonnegative `chunk_count` envelope for runtime-owned document catalog rows and nested `retrieval.query` search result documents. Zero or negative chunks map to `no_usable_text`, one chunk maps to `single_chunk`, and two or more chunks map to `chunked`, so malformed-but-decodable quality strings cannot become Android UI metadata. This aligns Android app state with the shared quality/chunk-count schema and macOS runtime document-index derived-quality contract before local persistence, chat context injection, semantic retrieval, resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest Android retrieval lexical metadata transient-state no-device gate: Android `RuntimeClientViewModel` now bounds malformed-but-decodable `retrieval.query` lexical metadata before it reaches transient `RuntimeUiState`. Transient search rows coerce rank to positive integers, coerce offsets to nonnegative ordered ranges, cap snippets at 480 characters, and keep `matched_terms` to 16 distinct trimmed nonblank terms of 64 characters or less. This aligns Android app state with the shared retrieval schema and runtime lexical metadata contract before local persistence, chat context injection, semantic retrieval, resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest Android document MIME transient-state no-device gate: Android `RuntimeClientViewModel` now preserves only exact lowercase `type/subtype` MIME values up to 128 characters when decoding runtime-owned document catalog rows and `retrieval.query` search result documents into transient `RuntimeUiState`. Whitespace-mutated, uppercase, parameterized, URL-shaped, and overlong MIME values are replaced with `application/octet-stream` instead of being trimmed or rendered as raw runtime metadata, while document rows/snippets remain available and `chat.send` still excludes document metadata. This aligns Android app transient state with the shared JSON Schema and macOS runtime document-index MIME fallback contract before local persistence, chat context injection, semantic retrieval, resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest Android document content-fingerprint transient-state no-device gate: Android `RuntimeClientViewModel` now preserves only exact 16-character lowercase hex `content_fingerprint` values when decoding runtime-owned document catalog rows and `retrieval.query` search result documents into transient `RuntimeUiState`. Whitespace-mutated, uppercase, and overlong fingerprints are cleared instead of normalized into app state, while document rows/snippets remain available and `chat.send` still excludes document metadata. This aligns Android app transient state with the shared JSON Schema, Android protocol DTO parity, and macOS runtime document-index wire contract before local persistence, chat context injection, semantic retrieval, resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest Android document content-fingerprint protocol parity no-device gate: Android `ProtocolCodecTest` now serializes and decodes both `index.documents.list` catalog rows and nested `retrieval.query` result documents with a 16-character lowercase hex `content_fingerprint` sample, matching the shared JSON Schema and macOS runtime document-index canonicality contract instead of carrying the previous 64-character test fixture. RuntimeDevServer authenticated relay smoke now also requires seeded catalog and retrieval document fingerprints to match the same 16-lowercase-hex wire shape. This keeps Android DTO parity, schema hygiene, and runtime relay output aligned before semantic retrieval, resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, Android UI persistence, chat context injection, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest protocol document quality/chunk-count consistency no-device gate: protocol schema hygiene now binds every safe `indexDocument` row's `quality` to its `chunk_count` envelope for both `index.documents.list` catalog rows and nested `retrieval.query` result documents. `chunk_count: 0` requires `quality: no_usable_text`, `chunk_count: 1` requires `quality: single_chunk`, and `chunk_count >= 2` requires `quality: chunked`; `script/check_protocol_schema.py` rejects catalog and retrieval response samples with mismatched pairs. This keeps document quality metadata aligned with the runtime index store's derived quality before semantic retrieval, resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, Android UI persistence, chat context injection, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest protocol retrieval.query positive-rank wire-shape no-device gate: protocol schema hygiene now pins every `retrieval.query` result `rank` to a positive integer, matching the runtime lexical scoring path that only emits rows with matched terms and computes rank from matched-term and occurrence counts. `script/check_protocol_schema.py` requires the exact result integer schemas, accepts canonical positive-rank response samples, and rejects zero-rank response samples alongside missing, non-integer, boolean, fractional, and negative rank samples. This keeps lexical retrieval rank metadata aligned with runtime output before semantic retrieval, resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, Android UI persistence, chat context injection, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest protocol document MIME type wire-shape no-device gate: protocol schema hygiene now pins safe document `mime_type` metadata to the runtime-owned lowercase `type/subtype` token envelope while preserving the existing 128-character ceiling. `indexDocument.mime_type` now requires the same canonical token shape for both `index.documents.list` catalog rows and nested `retrieval.query` result documents, and `script/check_protocol_schema.py` rejects whitespace-mutated, uppercase, missing-slash, parameterized, URL-shaped, and overlong MIME samples. Existing RuntimeDocumentIndexStore and SQLiteRuntimeDocumentIndexStore MIME canonicality coverage remains the runtime proof that malformed document or chunk MIME values normalize to `application/octet-stream` before catalog/search output. This keeps protocol document metadata aligned with runtime storage before semantic retrieval, resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, Android UI persistence, chat context injection, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest protocol retrieval.query result ordering and offset sanity no-device gate: runtime document retrieval now has focused no-device coverage for `retrieval.query` result count, deterministic rank ordering, and safe character-offset relationships. `RuntimeDocumentIndexStoreTests` proves `limit: 0` returns an empty result window, positive limits cap returned rows, results stay ordered by descending deterministic lexical rank with stable display-name/chunk-index tie-breakers, and every result keeps `end_character_offset >= start_character_offset`. SQLite parity now asserts the same offset/rank invariants after reopen, `LocalRuntimeMessageRouterTests` checks serialized multi-row retrieval responses for rank and offset sanity, `script/check_protocol_schema.py` rejects end-before-start response samples, and RuntimeDevServer smoke requires seeded retrieval offsets to remain ordered. This keeps current lexical retrieval metadata deterministic before semantic retrieval, resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, Android UI persistence, chat context injection, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest protocol index.documents.list quality-count completeness no-device gate: macOS runtime catalog responses now serialize `summary.quality_counts` with all three runtime document quality buckets, `no_usable_text`, `single_chunk`, and `chunked`, including explicit zero counts while leaving the internal store summary sparse. Protocol schema hygiene requires those exact nested keys, `script/check_protocol_schema.py` rejects missing quality-count samples alongside malformed, future, non-integer, and negative quality counts, the RuntimeDevServer smoke requires all three keys on seeded catalog responses, and the no-device gate summarizes the completed wire contract. This keeps Android DTO decoding, schema validation, and macOS wire output aligned before semantic retrieval, resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, Android UI persistence, chat context injection, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest protocol document metadata string-bounds and retrieval nested-document parity no-device gate: protocol schema hygiene now caps safe document `id` and `mime_type` metadata at 128 characters and `display_name` at 256 characters, matching the runtime document-index ceilings. `script/check_protocol_schema.py` requires those exact `indexDocument` shapes, rejects overlong catalog document samples, requires `retrieval.query` result documents to keep using `#/$defs/indexDocument`, and rejects nested retrieval document samples with unknown metadata, missing quality, overlong ids, malformed content fingerprints, non-integer chunk counts, and negative extracted-character counts. This keeps catalog and retrieval document metadata bounded and parity-checked at the schema layer before semantic retrieval, resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, Android UI persistence, chat context injection, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest protocol index.documents.list content-fingerprint wire-shape no-device gate: protocol schema hygiene now pins safe catalog document `content_fingerprint` metadata to the runtime-owned 16-character lowercase hex envelope. `script/check_protocol_schema.py` requires the exact schema shape and rejects empty, whitespace-mutated, uppercase, short, long, and non-hex complete response samples with explicit content-fingerprint failures. This keeps catalog fingerprint metadata canonical at the schema layer before semantic retrieval, resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, Android UI persistence, chat context injection, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest protocol retrieval.query snippet bounds no-device gate: protocol schema hygiene now caps each `retrieval.query` result row's response `snippet` at 500 characters, matching the runtime-owned `max_snippet_characters` ceiling. `script/check_protocol_schema.py` requires the bounded non-empty snippet schema and rejects overlong 501-character snippet response samples with explicit maximum-length failures. This keeps lexical retrieval result excerpts bounded at the schema layer before semantic retrieval, resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, Android UI persistence, chat context injection, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest protocol retrieval.query matched-terms bounds no-device gate: protocol schema hygiene now caps each `retrieval.query` result row's `matched_terms` array to the runtime-owned lexical query-term envelope. `matched_terms` must be non-empty, may carry at most 16 terms, and each term is capped at 64 characters; `script/check_protocol_schema.py` rejects empty arrays, empty terms, 17-term arrays, and overlong matched terms with explicit sample failures. This keeps lexical retrieval result metadata bounded at the schema layer before semantic retrieval, resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, Android UI persistence, chat context injection, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest protocol document retrieval response array bounds no-device gate: protocol schema hygiene now caps active document retrieval response arrays at the same 100-row ceiling as their request limits. `index.documents.list` response `documents` and `retrieval.query` response `results` both carry `maxItems: 100`, and `script/check_protocol_schema.py` rejects 101-row catalog and retrieval response samples with explicit above-maximum failures. This keeps catalog and lexical retrieval responses bounded at the schema layer before semantic retrieval, resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, Android UI, local persistence, chat context injection, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest protocol index.documents.list request and response sample no-device gate: protocol schema hygiene now validates complete `index.documents.list` catalog request and response payload samples, not only router/runtime smoke behavior. Empty requests and bounded `limit` requests pass, while string, fractional, boolean, negative, and over-maximum `limit` values fail; response-only `documents` or `summary` fields and unknown request metadata such as `source_path` fail before catalog dispatch. Response samples now pin safe document metadata, summary counts, and optional quality-count entries while rejecting unknown response metadata, missing `documents` or `summary`, malformed document arrays, future document metadata, missing or invalid document quality, empty display names, non-integer or negative document counts, future summary metadata, malformed quality counts, future quality-count keys, and non-integer or negative quality-count values. This keeps `index.documents.list` catalog exchange metadata-only at the schema hygiene layer without adding semantic retrieval, resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, Android UI, local persistence, chat context injection, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest protocol retrieval.query query-length and response result sample no-device gate: protocol schema hygiene now caps `retrieval.query` request `query` text at 1024 characters, matching the runtime document-index query ceiling before the request reaches store dispatch, and rejects complete oversized query payload samples. The same checker now validates complete response result samples beyond `source_anchor_id`: unknown result metadata, missing required `rank`, empty snippets or matched terms, and string, fractional, boolean, or negative `chunk_index`, `start_character_offset`, `end_character_offset`, and `rank` samples all fail. This keeps lexical retrieval request text and response row metadata bounded at the schema hygiene layer without adding semantic retrieval, resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, Android UI, local persistence, chat context injection, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest protocol retrieval.query request bounds sample no-device gate: protocol schema hygiene now pins the `retrieval.query` request property set to exactly `query`, `limit`, and `max_snippet_characters`, then exercises the numeric request bounds through rejected complete payload samples. String, fractional, boolean, negative, and over-maximum `limit` values fail, and the same non-integer/negative/over-maximum coverage now applies to `max_snippet_characters`. This keeps lexical retrieval request windows bounded at the schema hygiene layer without adding semantic retrieval, resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, Android UI, local persistence, chat context injection, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest protocol retrieval.query source-anchor request payload sample no-device gate: protocol schema hygiene now validates complete `retrieval.query` request payload samples before response-only source anchors can be mistaken for request inputs. The request variant must require `query`, `query` must use `nonBlankString`, request payloads stay closed to unknown properties, canonical samples with bounded `limit` and `max_snippet_characters` pass, and missing, blank, non-string, or `source_anchor_id`-carrying request samples fail. This keeps `source_anchor_id` strictly response-only at the request sample layer without adding source approval, citations, trusted-source review, permission/audit semantics, Android UI, local persistence, chat context injection, semantic retrieval, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest protocol retrieval.query source-anchor response payload sample no-device gate: protocol schema hygiene now validates complete `retrieval.query` response payload samples, not only isolated source-anchor strings. The response variant must require `results`, `results.items` must reference `retrievalQueryResult`, response payloads stay closed to unknown properties, and sample `results[].source_anchor_id` values must be present and exact `source_anchor_[16 lowercase hex]`. Missing, whitespace-mutated, uppercase, short, long, non-hex, and empty result anchors fail the schema hygiene sample path. This keeps `retrieval.query` result rows aligned with the response-only source-anchor contract without adding source approval, citations, trusted-source review, permission/audit semantics, Android UI, local persistence, chat context injection, semantic retrieval, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest protocol source-anchor ID sample validation no-device gate: protocol schema hygiene now compiles the dedicated `sourceAnchorID` pattern and runs canonical plus noncanonical `source_anchor_id` samples through `fullmatch`. Lowercase 16-hex handles such as `source_anchor_0000000000000000`, `source_anchor_0123456789abcdef`, and `source_anchor_ffffffffffffffff` must pass, while whitespace, newline, uppercase, short, long, non-hex, missing-underscore, and empty variants must fail. This keeps `retrieval.query` response metadata aligned with the exact `source_anchor_[16 lowercase hex]` contract without adding resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, Android UI, local persistence, chat context injection, semantic retrieval, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest macOS document retrieval source anchor exact-shape no-device gate: macOS `RuntimeDocumentIndexStore`, `SQLiteRuntimeDocumentIndexStore`, and `LocalRuntimeMessageRouter` retrieval tests now require generated and serialized `source_anchor_id` values to pass `runtimeDocumentIndexCanonicalSourceAnchorID`, replacing prefix-only `source_anchor_` assertions with the exact `source_anchor_[16 lowercase hex]` contract. This keeps runtime-generated anchors, SQLite parity, and router `retrieval.query` responses aligned with the shared protocol schema and Android transient-state guard without adding resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, Android UI, local persistence, chat context injection, semantic retrieval, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest Android document retrieval source anchor canonical transient-state no-device gate: Android `RuntimeClientViewModel` now keeps only exact `source_anchor_[16 lowercase hex]` `retrieval.query` `source_anchor_id` values in transient document search state, and noncanonical wire values now fail DTO decode as `invalid_payload` before transient document rows are published. This keeps malformed handles from becoming approval/citation material while a later canonical retry can still populate transient search results. This remains no-device Android JVM evidence only and does not add source approval, citations, trusted-source review, permission/audit semantics, local persistence, chat context injection, semantic retrieval, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest protocol source-anchor ID wire-shape no-device gate: shared protocol schema now constrains `retrieval.query` response `source_anchor_id` values to `source_anchor_[16 lowercase hex]` through a dedicated `sourceAnchorID` definition, `script/check_protocol_schema.py` enforces the structural contract, Android `ProtocolCodecTest` asserts decoded response IDs match the same shape, and RuntimeDevServer authenticated relay smoke requires the exact regex instead of prefix-only acceptance. `retrieval.query` requests still cannot carry `source_anchor_id`, and source anchors remain response metadata only before resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, semantic retrieval, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest Android document retrieval source anchor hidden UI no-device gate: Android Settings Documents search now has a no-device Compose regression proving transient `retrieval.query` `source_anchor_id` values stay out of visible text and accessibility content descriptions while snippet, rank, matched-term, and document metadata rendering remains available. This keeps source anchors as runtime/protocol handles for future approval or citation workflows without making them user-visible IDs, chat context, local persistence, source approval, citations, trusted-source review, permission/audit semantics, semantic retrieval, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Historical protocol namespace checkpoint, superseded by the current citation/trusted-source section above: unsupported `source_anchor.*` names beyond `source_anchor.resolve` and all `trusted_source.*` names were initially reserved, and the smoke rejected them with `unknown_message_type`. The active set now includes citation resolution and trusted-source approve/dismiss/list/revoke; unsupported source-anchor, permission, and audit namespaces remain reserved. The historical evidence remains no-device only.
Latest document retrieval source anchor canonicality no-device gate: `RuntimeDocumentIndexStore` and `SQLiteRuntimeDocumentIndexStore` now reject whitespace-mutated `source_anchor_id` resolver inputs instead of trimming them into a valid future approval/citation handle, including SQLite reopen coverage. The resolver still accepts the exact runtime-derived anchor and rejects uppercase, malformed, missing, or whitespace-wrapped variants. This remains no-device evidence only and does not add resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, semantic retrieval, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest document retrieval source anchor query-window no-device gate: `RuntimeDocumentIndexStore` and `SQLiteRuntimeDocumentIndexStore` now prove `source_anchor_id` remains tied to the same safe document/chunk envelope when retrieval query terms, rank windows, result limits, and snippet bounds change, including SQLite reopen coverage. The tests show rank, matched terms, and snippets can vary while the anchor remains stable for the same document id, content fingerprint, chunk index, and character offsets. This remains no-device evidence only and does not add resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, semantic retrieval, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest document retrieval source anchor filtered-delete lifecycle no-device gate: `RuntimeDocumentIndexStore` and `SQLiteRuntimeDocumentIndexStore` now prove `source_anchor_id` handles stop resolving after display-name, MIME-type, content-fingerprint, quality, and delete-all maintenance deletes. The SQLite coverage reopens stores through the resolver path and checks deleted documents leave no FTS rows, including delete-all cleanup. This remains no-device evidence only and does not add resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, semantic retrieval, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest document retrieval source anchor lifecycle no-device gate: `RuntimeDocumentIndexStore` and `SQLiteRuntimeDocumentIndexStore` now prove stale `source_anchor_id` handles stop resolving after same-id document replacement and document deletion, including SQLite reopen/FTS cleanup evidence. `LocalRuntimeMessageRouter` also rejects client-supplied `source_anchor_id` in `retrieval.query` requests before store dispatch, and Android protocol tests keep `source_anchor_id` response-only by asserting retrieval requests do not serialize it. This remains no-device evidence only and does not add resolver protocol exposure, source approval, citations, trusted-source review, permission/audit semantics, semantic retrieval, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest document retrieval source anchor resolver no-device gate: `RuntimeDocumentIndexStore` and `SQLiteRuntimeDocumentIndexStore` now resolve an opaque `source_anchor_id` back to a redacted runtime-local envelope containing safe document catalog metadata plus chunk index, character offsets, and character count. Focused Swift tests prove the resolver omits chunk text, snippets, source paths, workspace/project IDs, `retrieval_context`, citations, trusted-source fields, approval state, and body sentinels after SQLite reopen, while `LocalRuntimeMessageRouter` rejects client-supplied `source_anchor_id` in `chat.send` before trusted-source, citation, permission, and audit semantics exist. This remains no-device evidence only and does not add protocol exposure beyond active `retrieval.query` and `index.documents.list`, source approval, citations, trusted-source review, permission/audit semantics, semantic retrieval, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest document retrieval source anchor stability no-device gate: `RuntimeDocumentIndexStore` and `SQLiteRuntimeDocumentIndexStore` now pin `source_anchor_id` stability semantics before any source approval, citation, or trusted-source workflow exists. Focused Swift tests prove the opaque anchor stays stable for the same safe document id, content fingerprint, chunk index, and character offsets across repeated query, same-content reindex, and SQLite reopen paths, then rotates when the same requested document id is reindexed with changed content. This remains no-device evidence only and does not add protocol exposure beyond active `retrieval.query`, source approval, citations, trusted-source review, permission/audit semantics, semantic retrieval, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest document retrieval source anchor no-device gate: `retrieval.query` results now include a runtime-derived `source_anchor_id` generated from the safe document id, content fingerprint, chunk index, and character offsets. Swift in-memory/SQLite/router tests, RuntimeDevServer authenticated relay smoke, Android protocol DTO tests, Android ViewModel tests, and Android trusted relay integration tests preserve the anchor through transient search state while keeping source paths, workspace/project IDs, `retrieval_context`, citations, trusted-source fields, document filenames, snippets, and chat context injection out of `chat.send`. This remains no-device evidence only and does not add source approval, citations, trusted-source review, permission/audit semantics, semantic retrieval, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest Android trusted relay document index/retrieval integration gate: Android `RuntimeClientViewModelRelayIntegrationTest.trustedPrivateOverlayRelayReconnectUsesRealRelayTcpClientAndAuthenticatedSession` now proves an authenticated trusted private-overlay relay reconnect carries `index.documents.list` and `retrieval.query` over `RuntimeRelayTcpClient`, trims the search query, preserves bounded request limits, updates transient catalog/search state, then sends `chat.send` through a selected local runtime-host model after `models.list` while keeping `retrieval_context`, source paths, workspace/project IDs, citations, trusted-source fields, document filenames, and snippets out of chat payloads. This remains no-device Android JVM evidence only and does not add chat context injection, source approval, citations, trusted-source review, permission/audit semantics, physical Android proof, optical QR, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest RuntimeDevServer seeded document catalog relay gate: RuntimeDevServer authenticated relay smoke now accepts `index.documents.list` against the seeded development document index with one bounded catalog row, summary metadata, document metadata, and quality counts. The smoke rejects response-only `documents`/`summary` payloads and future source, embedding, citation, trusted-source, and backend metadata before document-index dispatch, and it fails if private body canaries, secondary document canaries, chunk IDs, chunk text, source paths, workspace/project IDs, `retrieval_context`, embeddings, citations, or trusted-source fields leak into the catalog response. This remains no-device RuntimeDevServer evidence only and does not add runtime file access, semantic retrieval, embedding generation, source approval, citations, trusted-source review, Android chat context injection, permission/audit semantics, physical Android proof, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest RuntimeDevServer seeded document retrieval relay gate: RuntimeDevServer now supports a dev-only per-run SQLite document index for smoke runs and seeds deterministic smoke documents so authenticated `retrieval.query` returns one bounded lexical snippet with document metadata, rank, matched_terms, chunk index, and character offsets. The relay smoke rejects response-only results and future source, embedding, citation, trusted-source, and backend metadata before document-index dispatch, and it fails if private body canaries, secondary document canaries, full chunk text, chunk IDs, source paths, workspace/project IDs, `retrieval_context`, embeddings, citations, or trusted-source fields leak into the response. This remains no-device RuntimeDevServer evidence only and does not add semantic retrieval, embedding generation, source approval, citations, trusted-source review, Android chat context injection, permission/audit semantics, physical Android proof, live-provider behavior, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest Android document index/retrieval compact layout gate: Android Settings Documents catalog rows and lexical `retrieval.query` snippet rows now have compact-width, large-font no-device Compose coverage across supported app languages. The gate keeps the same read-only transient UI boundary and continues to exclude fingerprints, source paths, workspace/project IDs, `retrieval_context`, citations, trusted-source fields, local persistence, chat context injection, source approval, citation UX, trusted-source review, permission/audit semantics, production relay/session/encryption, direct Android backend access, physical Android proof, live-provider behavior, and real different-network proof.
Prior Android document index/retrieval read-only Compose UI gate: Android Settings now exposes a read-only Documents panel that renders transient `RuntimeUiState` document catalog summaries, quality counts, catalog rows, and lexical `retrieval.query` snippet rows. The UI invokes explicit refresh/search callbacks only and keeps fingerprints, source paths, workspace/project IDs, `retrieval_context`, citations, trusted-source fields, local persistence, and chat context injection out of UI behavior; source approval, citation UX, trusted-source review, permission/audit semantics, production relay/session/encryption, direct Android backend access, physical Android proof, live-provider behavior, and real different-network proof remain out of scope.
Prior Android document index/retrieval transient ViewModel wiring gate: Android `RuntimeClientViewModel` now advertises active read-only `index.documents.list` and `retrieval.query` client capabilities, sends bounded explicit catalog/search requests, and decodes catalog metadata, summary counts, lexical ranks, matched_terms, offsets, and snippets into transient `RuntimeUiState` only. `chat.send` payloads remain free of `retrieval_context`, source paths, workspace/project IDs, citations, and trusted-source fields after retrieval results are present; chat context injection, source approval, citation UX, trusted-source review, permission/audit semantics, production relay/session/encryption, direct Android backend access, physical Android proof, live-provider behavior, and real different-network proof remain out of scope.
Prior Android protocol document index/retrieval payload parity gate: Android `ProtocolModels` and `ProtocolCodecTest` serialize and decode active `index.documents.list` catalog/summary payloads and lexical `retrieval.query` snippet payloads with the shared schema field names, including document catalog metadata, quality counts, `max_snippet_characters`, `start_character_offset`, `end_character_offset`, and `matched_terms`. That gate was Android protocol DTO parity only, before the later transient ViewModel wiring; UI consumption, chat context injection, citations, trusted-source review, permission/audit semantics, production relay/session/encryption, direct Android backend access, and real different-network proof remained out of scope.
Latest runtime document retrieval.query lexical read-only protocol gate: authenticated `LocalRuntimeMessageRouter` now exposes bounded lexical runtime-owned document snippets through `retrieval.query`. Results include document catalog metadata, chunk index, chunk offsets, rank, matched_terms, and bounded snippets, while keeping full chunk text, chunk IDs, source paths, workspace/project IDs, retrieval context, embeddings, citations, trusted-source fields, Android UI, production relay/session/encryption, direct Android backend access, and real different-network proof out of scope. Response-only result payloads and future source, embedding, citation, trusted-source, or backend metadata are rejected before document-index store dispatch; unsupported `retrieval.*` beyond `retrieval.query`, `index.build`, unsupported future `index.*` messages, embeddings, semantic retrieval, citations, research, source-control, permissions, and audit semantics remain reserved.
Latest runtime document index index.documents.list read-only catalog gate: authenticated `LocalRuntimeMessageRouter` now exposes only bounded runtime-owned document catalog metadata and aggregate summary counts through `index.documents.list`. The response includes document IDs, display names, MIME types, content fingerprints, extracted-character counts, chunk counts, quality states, and summary totals, while keeping chunk text, chunk IDs, source paths, workspace/project IDs, retrieval context, embeddings, citations, trusted-source fields, Android UI, production relay/session/encryption, direct Android backend access, and real different-network proof out of scope. Response-only catalog payloads and future source metadata are rejected before document-index store dispatch; `index.build`, unsupported future `index.*` messages, unsupported future `retrieval.*` beyond active lexical `retrieval.query`, embeddings, semantic retrieval, citations, research, source-control, permissions, and audit semantics remain reserved.
Latest runtime document index requested document ID control-character canonicality gate: requested document ID control-character canonicality now rejects control-character requested IDs before runtime document-index document, chunk, or SQLite FTS storage and before document lookup, chunk reads, chunk metadata summaries, or deletion. `RuntimeDocumentIndexStore` and `SQLiteRuntimeDocumentIndexStore` fall back to deterministic stable document IDs instead of persisting forged control-character requested IDs, without adding `index.*` or `retrieval.*` protocol messages, router dispatch, Android UI, embeddings, citations, source paths, project/workspace IDs, trusted-source fields, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest runtime document index display-name control-character canonicality gate: display-name control-character canonicality now rejects labels containing control characters before runtime document-index catalog lookup, in-memory storage, chunk labels, or SQLite display-name rows. `RuntimeDocumentIndexStore` and `SQLiteRuntimeDocumentIndexStore` fall back to `untitled-document` instead of persisting forged control-character names, without adding `index.*` or `retrieval.*` protocol messages, router dispatch, Android UI, embeddings, citations, source paths, project/workspace IDs, trusted-source fields, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest DocumentIngestion direct extracted-document text ceiling gate: `DocumentIngestor` now rejects oversized direct `ExtractedDocument` text before chunk planning, summary construction, or result return while preserving extractor-owned file-ingestion resource-policy behavior. This closes the direct-ingestion bypass of the extracted-text ceiling without adding source paths, project/workspace IDs, embeddings, retrieval, citations, protocol/router integration, Android UI, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest DocumentIngestion direct extracted-document source-label canonicality gate: `DocumentIngestor` now canonicalizes direct `ExtractedDocument` file names before chunk planning, summary construction, or result return while preserving existing MIME metadata boundaries for downstream runtime-index validation. This keeps the public runtime-side ingestion envelope from preserving path-shaped direct labels while retaining the current file-extractor path behavior, without adding source paths, project/workspace IDs, embeddings, retrieval, citations, protocol/router integration, Android UI, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest DocumentIngestion archive-entry path canonicality gate: `DocumentTextExtractor` now ignores path-shaped archive entries before selected-entry fanout counting or per-entry archive extraction. This keeps compressed-document extraction focused on store-owned relative archive paths and rejects parent traversal, absolute, Windows/backslash-shaped, dot-component, oversized, and control-character entry names without adding source paths, project/workspace IDs, embeddings, retrieval, citations, protocol/router integration, Android UI, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest DocumentIngestion MIME dispatch canonicality gate: `DocumentTextExtractor` now trims attachment MIME values, strips MIME parameters, and lowercases MIME dispatch before extensionless document extraction. This keeps runtime-side MIME-only attachment ingestion resilient to SAF/share-sheet content-type formatting without adding source paths, project/workspace IDs, embeddings, retrieval, citations, protocol/router integration, Android UI, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest DocumentIngestion archive entry fanout policy gate: `DocumentTextExtractor` now rejects excessive selected archive entries before per-entry archive extraction while accepting boundary entry counts. This keeps compressed-document helper-process fanout store-owned and bounded for the runtime-side file-indexing path without adding source paths, project/workspace IDs, embeddings, retrieval, citations, protocol/router integration, Android UI, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest DocumentIngestion resource policy ceiling gate: `DocumentTextExtractor` now rejects oversized or non-positive caller-supplied resource policy limits before file reads, archive listing, archive entry extraction, `textutil` conversion, or normalized text dispatch while accepting boundary ceiling values. This keeps extraction resource windows store-owned and bounded for the runtime-side file-indexing path without adding source paths, project/workspace IDs, embeddings, retrieval, citations, protocol/router integration, Android UI, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest runtime document index display-name delete maintenance gate: `RuntimeDocumentIndexStore` and `SQLiteRuntimeDocumentIndexStore` now remove only documents matching a canonical display name while preserving unrelated catalog rows, chunk metadata, lexical query rows, summaries, and SQLite FTS candidates. This advances display-name-scoped catalog cleanup for runtime-owned file indexing without adding `index.*` or `retrieval.*` protocol messages, router dispatch, Android UI, embeddings, citations, source paths, project/workspace IDs, trusted-source fields, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest runtime document index MIME-type delete maintenance gate: `RuntimeDocumentIndexStore` and `SQLiteRuntimeDocumentIndexStore` now remove only documents matching a canonical MIME type while preserving unrelated catalog rows, chunk metadata, lexical query rows, summaries, and SQLite FTS candidates. This advances MIME-scoped catalog cleanup for runtime-owned file indexing without adding `index.*` or `retrieval.*` protocol messages, router dispatch, Android UI, embeddings, citations, source paths, project/workspace IDs, trusted-source fields, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest runtime document index content-fingerprint delete maintenance gate: `RuntimeDocumentIndexStore` and `SQLiteRuntimeDocumentIndexStore` now remove only documents matching a canonical content fingerprint while preserving unrelated catalog rows, chunk metadata, lexical query rows, summaries, and SQLite FTS candidates. This advances duplicate/reindex maintenance for runtime-owned file indexing without adding `index.*` or `retrieval.*` protocol messages, router dispatch, Android UI, embeddings, citations, source paths, project/workspace IDs, trusted-source fields, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest DocumentIngestion chunk policy ceiling gate: `DocumentChunker` now rejects oversized max-character, overlap-character, and min-chunk policy values before chunk planning, while accepting boundary ceiling values. This keeps caller-supplied chunking windows store-owned and bounded for the runtime-side file-indexing path without adding source paths, project/workspace IDs, embeddings, retrieval, citations, protocol/router integration, Android UI, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest runtime document index chunk-envelope canonicality gate: chunk indexes and offsets use store-owned envelopes before catalog lookup and storage. `RuntimeDocumentIndexStore` and `SQLiteRuntimeDocumentIndexStore` now derive contiguous chunk indexes, validate chunk offsets against document text, relocate malformed offsets from document text when possible, use derived indexes/offsets in stable chunk IDs, and bound unlocatable forged chunk offsets before in-memory or SQLite persistence. This hardens runtime document-index chunk metadata while adding no `index.*` or `retrieval.*` protocol messages, router dispatch, Android UI, embeddings, citations, source paths, project/workspace IDs, trusted-source fields, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest runtime document index display-name canonicality gate: display names use store-owned canonicality guards before catalog lookup and storage. `RuntimeDocumentIndexStore` and `SQLiteRuntimeDocumentIndexStore` now trim display-name lookup input, reduce path-shaped document labels to their final component, derive stored catalog display names and chunk display labels from the owning document file name, and fall back to `untitled-document` for blank or oversized labels. This hardens runtime document-index source-label boundaries while adding no `index.*` or `retrieval.*` protocol messages, router dispatch, Android UI, embeddings, citations, source paths, project/workspace IDs, trusted-source fields, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest runtime document index ingestion summary normalization gate: document index ingestion summaries are normalized before storage. `RuntimeDocumentIndexStore` and `SQLiteRuntimeDocumentIndexStore` now derive extracted-character count, chunk count, and quality from document text and chunks before stable content fingerprinting, catalog row creation, or SQLite persistence, so forged direct-ingestion summaries cannot persist negative or oversized counts or mismatched quality states after reopen. This hardens runtime document-index catalog and summary integrity while adding no `index.*` or `retrieval.*` protocol messages, router dispatch, Android UI, embeddings, citations, source paths, project/workspace IDs, trusted-source fields, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest runtime document index MIME-type canonicality gate: MIME types use store-owned canonicality guards before catalog lookup and storage. `RuntimeDocumentIndexStore` and `SQLiteRuntimeDocumentIndexStore` now trim MIME-type lookup input, accept only canonical lowercase `type/subtype` token strings, reject blank, whitespace-only, case-mutated, missing-slash, URL-shaped, parameterized, or oversized MIME lookup input before in-memory filtering or SQLite query dispatch, normalize document/chunk MIME metadata before storage, and persist malformed direct-ingestion MIME metadata as `application/octet-stream`. This hardens runtime document-index MIME metadata without adding `index.*` or `retrieval.*` protocol messages, router dispatch, Android UI, embeddings, citations, source paths, project/workspace IDs, trusted-source fields, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest runtime document index content-fingerprint canonicality gate: content fingerprints use store-owned canonicality guards before duplicate/reindex catalog lookup. `RuntimeDocumentIndexStore` and `SQLiteRuntimeDocumentIndexStore` now trim content-fingerprint lookup input, accept only canonical lowercase 16-hex fingerprints, reject blank, whitespace-only, wrong-length, uppercase/case-mutated, or non-hex fingerprints before in-memory filtering or SQLite query dispatch, and preserve trimmed canonical lookup parity after SQLite reopen. This hardens the existing content-fingerprint maintenance API while adding no `index.*` or `retrieval.*` protocol messages, router dispatch, Android UI, embeddings, citations, source paths, project/workspace IDs, trusted-source fields, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest runtime document index chunk read limit gate: `RuntimeDocumentIndexStore` and `SQLiteRuntimeDocumentIndexStore` now apply a store-owned maximum for full chunk text reads before returning `chunks(for:limit:)`, keeping deterministic chunk-index order, non-positive limit rejection, blank document-ID rejection, replacement/deletion visibility, and SQLite reopen parity. This closes the remaining unbounded chunk-text read seam in the document-index maintenance API while adding no `index.*` or `retrieval.*` protocol messages, router dispatch, Android UI, embeddings, citations, source paths, project/workspace IDs, trusted-source fields, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest runtime document index requested document ID canonicality gate: requested document IDs use store-owned canonicality guards before storage and maintenance. `RuntimeDocumentIndexStore` and `SQLiteRuntimeDocumentIndexStore` now trim requested document IDs, fall back to deterministic stable IDs when requested IDs are blank, whitespace-only, or over the store-owned length ceiling, and reuse the same canonicality guard for document lookup, chunk reads, chunk metadata summaries, and deletion. SQLite coverage proves blank, whitespace-mutated, and oversized requested IDs do not persist as document rows, chunk document IDs, or FTS document IDs after reopen. This advances runtime document-index maintenance hardening without adding `index.*` or `retrieval.*` protocol messages, router dispatch, Android UI, embeddings, citations, source paths, project/workspace IDs, trusted-source fields, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest runtime document index SQLite substring parity gate: public SQLite document-index query preserves substring lexical parity with `RuntimeDocumentIndexStore` by sending SQLite chunk snapshots through the shared rank/snippet helper even when internal FTS candidate rows miss substring-only matches such as `time` inside `runtime`; FTS rows remain maintained as internal maintenance and future-search infrastructure, not as an authoritative public-query filter. This keeps current lexical semantics deterministic while adding no `index.*` or `retrieval.*` protocol messages, router dispatch, Android UI, embeddings, citations, source paths, project/workspace IDs, trusted-source fields, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest runtime document index query resource guard gate: `RuntimeDocumentIndexStore` and `SQLiteRuntimeDocumentIndexStore` now enforce safe store-owned maximums for lexical query text, lexical query terms, and term length before in-memory search or SQLite search dispatch, so overlong query text, excessive deduplicated terms, and overlong individual terms return empty results while normal deduped searches keep existing lexical ranking/parity. This bounds query work and future FTS MATCH expression size while advancing runtime document-index search hardening without adding `index.*` or `retrieval.*` protocol messages, router dispatch, Android UI, embeddings, citations, source paths, project/workspace IDs, trusted-source fields, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest runtime document index quality-delete maintenance gate: `RuntimeDocumentIndexStore` and `SQLiteRuntimeDocumentIndexStore` now expose a safe store-owned quality-filtered deletion API that removes only documents matching an ingestion quality state, including their chunk metadata/text and SQLite FTS candidates, while preserving unrelated catalog rows, summaries, and lexical query results after SQLite reopen. This advances runtime document-index maintenance for failed or empty extraction cleanup while adding no `index.*` or `retrieval.*` protocol messages, router dispatch, Android UI, embeddings, citations, source paths, project/workspace IDs, trusted-source fields, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest runtime document index clear-all maintenance gate: `RuntimeDocumentIndexStore` and `SQLiteRuntimeDocumentIndexStore` now expose a safe store-owned clear-all maintenance API that removes document catalog rows, chunk metadata/text, and SQLite FTS candidates, with empty summary/query/catalog parity after SQLite reopen. This keeps runtime document-index maintenance deterministic while adding no `index.*` or `retrieval.*` protocol messages, router dispatch, Android UI, embeddings, citations, source paths, project/workspace IDs, trusted-source fields, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest runtime document index limit-ceiling gate: `RuntimeDocumentIndexStore` and `SQLiteRuntimeDocumentIndexStore` now enforce safe store-owned maximums for catalog rows, chunk metadata summaries, lexical query results, and snippets, so caller-supplied limits cannot silently turn maintenance/review APIs into unbounded reads. This keeps replacement/deletion visibility and SQLite reopen parity while adding no `index.*` or `retrieval.*` protocol messages, router dispatch, Android UI, embeddings, citations, source paths, project/workspace IDs, trusted-source fields, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest runtime document index chunk metadata summary gate: `RuntimeDocumentIndexStore` and `SQLiteRuntimeDocumentIndexStore` now expose bounded `chunkSummaries(for:limit:)` APIs for safe per-document chunk metadata summaries and review, with deterministic chunk-index ordering, character offsets, character counts, replacement/deletion visibility, SQLite reopen parity, and no chunk IDs, chunk text, source paths, project/workspace IDs, retrieval context, embeddings, citations, router dispatch, Android UI, production relay/session/encryption, direct Android backend access, or real different-network proof. This advances the file-indexing path toward runtime maintenance and future trusted-source review without exposing `index.*` or `retrieval.*` protocol messages.
Latest runtime document index display-name catalog filter gate: `RuntimeDocumentIndexStore` and `SQLiteRuntimeDocumentIndexStore` now expose bounded `documents(matchingDisplayName:limit:)` APIs for safe document catalog filtering by exact display name, with duplicate-name review, replacement/deletion visibility, SQLite reopen parity, and no chunk text, source paths, project/workspace IDs, retrieval context, embeddings, citations, router dispatch, Android UI, production relay/session/encryption, direct Android backend access, or real different-network proof. This advances the file-indexing path toward runtime maintenance and future trusted-source review without exposing `index.*` or `retrieval.*` protocol messages.
Latest runtime document index MIME-type catalog filter gate: `RuntimeDocumentIndexStore` and `SQLiteRuntimeDocumentIndexStore` now expose bounded `documents(matchingMimeType:limit:)` APIs for safe document catalog filtering by exact MIME type, with replacement/deletion visibility, SQLite reopen parity, and no chunk text, source paths, project/workspace IDs, retrieval context, embeddings, citations, router dispatch, Android UI, production relay/session/encryption, direct Android backend access, or real different-network proof. This advances the file-indexing path toward runtime maintenance and future trusted-source review without exposing `index.*` or `retrieval.*` protocol messages.
Latest runtime document index quality-filtered catalog gate: `RuntimeDocumentIndexStore` and `SQLiteRuntimeDocumentIndexStore` now expose bounded `documents(matchingQuality:limit:)` APIs for safe document catalog filtering by ingestion quality state, with replacement/deletion visibility, SQLite reopen parity, and no chunk text, source paths, project/workspace IDs, retrieval context, embeddings, citations, router dispatch, Android UI, production relay/session/encryption, direct Android backend access, or real different-network proof. This advances the file-indexing path toward runtime maintenance and future trusted-source review without exposing `index.*` or `retrieval.*` protocol messages.
Latest runtime document index content-fingerprint gate: `RuntimeDocumentIndexStore` and `SQLiteRuntimeDocumentIndexStore` now expose bounded `documents(matchingContentFingerprint:limit:)` APIs for exact-match content-fingerprint lookup using the existing safe document catalog ordering, with replacement/deletion visibility, SQLite reopen parity, and no chunk text, source paths, project/workspace IDs, retrieval context, embeddings, citations, router dispatch, Android UI, production relay/session/encryption, direct Android backend access, or real different-network proof. This advances the file-indexing path toward duplicate/reindex review and future trusted-source maintenance without exposing `index.*` or `retrieval.*` protocol messages.
Latest runtime document index summary gate: `RuntimeDocumentIndexStore` and `SQLiteRuntimeDocumentIndexStore` now expose safe runtime-owned `summary()` APIs returning document count, chunk count, extracted-character count, and ingestion quality-state counts, with SQLite reopen/replacement/deletion parity and no chunk text, source paths, project/workspace IDs, retrieval context, embeddings, citations, router dispatch, Android UI, production relay/session/encryption, direct Android backend access, or real different-network proof. This advances the file-indexing path toward runtime maintenance and future trusted-source/workspace review without exposing `index.*` or `retrieval.*` protocol messages.
Latest connected Android install/pairing/chat-cancel smoke: attached phone `R3CXC0M76VM` / `SM_S936N` accepted the current debug APK via `:app:installDebug`, launched to the Korean latest-QR scan state captured under `build/qa/android-real-device-launch-20260708.*`, passed `script/android_pairing_deeplink_smoke.sh --relay --serial R3CXC0M76VM --skip-install --expect-reconnect` with accepted pairing, `runtime.health`, `models.list`, and trusted-route reconnect verified in `build/qa/android-real-device-pairing-reconnect-20260708.json`, and passed `--expect-chat-cancel` with physical UI `chat.send`, `chat.delta`, `chat.cancel`, and `chat.done` observed in `build/qa/android-real-device-chat-cancel-20260708.json`. This is attached-phone USB `adb reverse` plus local development relay/mock-backend proof only; optical camera QR, live Ollama/LM Studio chat, public/VPN/tunnel/private-overlay relay, production relay/session/encryption, direct Android backend access, and real different-network proof remain separate.
Latest runtime document index catalog gate: `RuntimeDocumentIndexStore` and `SQLiteRuntimeDocumentIndexStore` now list indexed document catalog rows with bounded `documents(limit:)` APIs, deterministic display-name/document-id ordering, replacement/deletion visibility, SQLite reopen parity, and no chunk text, source paths, project/workspace IDs, retrieval context, embeddings, citations, router dispatch, Android UI, production relay/session/encryption, or real different-network proof. This advances the file-indexing path toward runtime maintenance and future trusted-source/workspace review without exposing `index.*` or `retrieval.*` protocol messages.
Latest SQLite runtime document index FTS candidate gate: `SQLiteRuntimeDocumentIndexStore` keeps an internal `runtime_document_index_chunk_fts` table for chunk text, updates it during replacement/deletion, and uses unicode-aware SQLite FTS candidate rows for internal maintenance/future search coverage while public query results stay governed by the shared deterministic lexical rank/snippet helper. This advances the file-indexing path from durable storage toward richer search without exposing `index.*` or `retrieval.*` protocol messages, source paths, project/workspace IDs, embeddings, citations, router dispatch, Android UI, production relay/session/encryption, or real different-network proof.
Latest SQLite runtime document index store gate: `SQLiteRuntimeDocumentIndexStore` now persists runtime-owned document/chunk records in `runtime-document-index.sqlite` with deterministic document IDs, deterministic chunk IDs, display names, MIME types, content fingerprints, extracted character counts, chunk counts, quality states, chunk offsets, owner-only SQLite file permissions, replacement/deletion cleanup, corrupt quality failure, and lexical query parity with the in-memory index store. This advances the file-indexing path from runtime-local memory into durable runtime-host storage without exposing `index.*` or `retrieval.*` protocol messages, source paths, project/workspace IDs, embeddings, citations, router dispatch, Android UI, production relay/session/encryption, or real different-network proof.
Latest runtime document index store gate: `RuntimeDocumentIndexStore` now stores runtime-owned document/chunk records from `DocumentIngestionResult` with deterministic document IDs, deterministic chunk IDs, display names, MIME types, content fingerprints, extracted character counts, chunk counts, quality states, chunk offsets, replacement/deletion, and lexical rank/snippet query results. This advances the file-indexing path without exposing `index.*` or `retrieval.*` protocol messages, source paths, project/workspace IDs, embeddings, router dispatch, Android UI, production relay/session/encryption, or real different-network proof.
Latest DocumentIngestion result envelope gate: `DocumentIngestor` now connects runtime-side text extraction and chunk planning into a `DocumentIngestionResult` with extracted document text, deterministic chunks, file name, MIME type, extracted character count, chunk count, min/max chunk lengths, and bounded quality states for no-usable-text, single-chunk, and chunked documents. This advances the file-indexing/document-chunking path while still avoiding source paths, project IDs, trusted-source approval, embeddings, retrieval, citations, protocol/router integration, Android UI, production relay/session/encryption, and real different-network proof.
Latest physical Android pairing/chat-cancel smoke after the chunk planner gate: attached phone `R3CXC0M76VM` / `SM_S936N` first showed the latest-QR recovery state for an unreachable relay route, then passed `script/android_pairing_deeplink_smoke.sh --relay --serial R3CXC0M76VM --expect-reconnect --expect-chat-cancel --capture-ui-polish` in `build/qa/android-pairing-current.json` after a fresh development relay QR-result injection. The summary records app install, app-data clear, accepted pairing, `runtime.health`, `models.list`, physical UI `chat.send`, `chat.delta`, `chat.cancel`, `chat.done`, trusted-route reconnect after relaunch, and UI polish capture coverage. This is attached-phone USB `adb reverse` plus local development relay/mock-backend proof only; optical camera QR, live Ollama/LM Studio chat, public/VPN/tunnel/private-overlay relay, production relay/session/encryption, direct Android backend access, and real different-network proof remain separate.
Latest DocumentIngestion chunk planner gate: `DocumentChunker` now provides a pure runtime-side `ExtractedDocument -> [DocumentChunk]` primitive with deterministic bounded text chunks, source labels, character offsets, sentence/word boundary preference, bounded overlap, multilingual text preservation, whitespace-only empty results, and invalid policy rejection. This starts the v0.8 file-indexing/document-chunking path without adding project IDs, source paths, embeddings, retrieval, protocol/router integration, Android UI, production relay/session/encryption, or real different-network proof.
Latest runtime compaction metadata validation gate: SQLite runtime chat event storage now has focused no-device coverage rejecting malformed `compaction_metadata.source_pointers` before persistence, including non-request metadata, blank strategies, empty pointer arrays, invalid compacted turn ranges, and invalid retained ranges. This strengthens the runtime-owned structural metadata boundary while keeping client-visible history, Android UI, optical QR, live-provider behavior, production relay/session/encryption, and real different-network proof separate.
Latest Android QR scanner decoded-result classification gate: `PairingQrScanResult.kt` now owns the post-ML-Kit raw-value batch helper, with no-device coverage proving blank/null decoded values are ignored, valid compact remote-route `aetherlink://pair` values win over invalid/unsupported values, route-less AetherLink pair values produce invalid-pairing feedback when a remote route is required, and unsupported non-AetherLink QR values do not mask invalid AetherLink QR feedback. This is deterministic decoded-result evidence only; optical camera QR recognition, physical phone pairing, production relay/session/encryption, live provider chat, direct Android backend access, and real different-network proof remain separate.
Latest connected Android install/pairing smoke after the runtime compaction slice: attached phone `R3CXC0M76VM` / `SM-S936N` on Android 16 accepted the current debug APK via `:app:installDebug`, launched to the Korean latest-QR scan prompt captured at `artifacts/android/connected-launch-2026-07-08.png`, and passed `script/android_pairing_deeplink_smoke.sh --relay --serial R3CXC0M76VM --skip-install --expect-reconnect` in `build/qa/android-pairing-deeplink-current.json` with accepted pairing, `runtime.health`, `models.list`, and trusted-route reconnect verified. This is current attached-phone install/launch plus ADB-injected QR-result pairing/reconnect proof only; optical camera QR, public/VPN/tunnel/private-overlay relay, production relay/session/encryption, direct Android backend access, live-provider chat, and real different-network proof remain separate.
Latest runtime compaction source-pointer storage slice: oversized `chat.send` compaction now persists runtime-owned `compaction_metadata.source_pointers` on request events with structural request/session/turn-range data while keeping backend-only summary text out of stored visible messages. `chat.messages.list` projections expose only client-visible transcript fields, and SQLite FTS/session search ignores the metadata-only source pointer. Focused SwiftPM coverage passed for producer metadata, visible projection separation, runtime memory/capability separation, and SQLite raw `event_json` roundtrip plus FTS exclusion. This is no-device runtime storage evidence; Android UI, optical QR, production relay/session/encryption, live provider behavior, and real different-network connectivity remain separate.
Latest Android `chat.messages.list` compaction metadata projection gate: Android now has a focused JVM regression proving raw `chat.messages.list` results with runtime-only `compaction_metadata` / `source_pointers` and a backend-summary sentinel still render and persist only visible `role`, `content`, `reasoning`, attachments, and created-time-derived message data. The default no-device gate includes the regression and reports the Android projection addendum. This is Android client projection/storage evidence only; optical QR, production relay/session/encryption, live provider behavior, and real different-network connectivity remain separate.
Latest RuntimeDevServer LM Studio 12B provider eval: authenticated RuntimeDevServer-mediated real LM Studio eval now also passes for `google/gemma-4-12b-qat` across `korean_local_runtime_summary`, `runtime_boundary_explanation`, and `structured_json_boundary`, with expected terms observed, answer/reasoning deltas, `thinking_observed=true`, redacted summary JSON, and preserved trusted-route reconnect/revocation checks in `build/qa/runtime-provider-eval-lmstudio-gemma12b-20260708-055608.json`. Together with the earlier `google/gemma-4-e4b` run, LM Studio fixed-prompt evidence now covers two installed chat models through the runtime host; Android-client model-quality proof, optical QR, production relay/session/encryption, direct Android backend access, real different-network proof, and the larger installed LM Studio `google/gemma-4-26b-a4b-qat` / `qwen/qwen3.6-35b-a3b` models remain separate.
Latest physical Android reconnected pairing/reconnect smoke: after the phone was reconnected, `R3CXC0M76VM` / `SM_S936N` passed the current debug APK `script/android_pairing_deeplink_smoke.sh --relay --expect-reconnect` path in `build/qa/android-physical-reconnected-after-wrapper-proof-boundary-20260708-055015.json`, with app install, clean app data, adb VIEW intent QR-result injection, accepted pairing, `runtime.health`, `models.list`, and trusted-route reconnect verified. This confirms the post-scan pairing/reconnect path after the wrapper proof-boundary split and full no-device gate pass, but it remains USB `adb reverse` plus local development relay and mock backend evidence; optical QR, live provider chat, production relay/session/encryption, direct Android backend access, and real different-network proof remain separate.
Latest physical external-relay wrapper proof-boundary split: `script/check_physical_external_relay_pairing.sh` wrapper summaries now expose `external_network_operator_confirmed`, `real_different_network_relay_verified`, `real_different_network_connectivity_proof`, `optical_camera_qr_scan=false`, production relay/session/encryption proof false, direct Android backend access false, and `private_or_same_lan_development_relay` so same-LAN/private development relay success cannot be read as real different-network, optical QR, production relay/session/encryption, or direct-backend proof; the no-device seeded summary in `build/qa/physical-wrapper-proof-boundary-self-test-20260708-054157.json` records all of those proof-boundary fields false while preserving safe child chat-complete proof reduction. A future public/VPN/tunnel/private-overlay run with `AETHERLINK_DIFFERENT_NETWORK_CONFIRMED=1` is still required before real different-network proof can become true.
Latest physical Android private-relay LM Studio chat-complete smoke: `R3CXC0M76VM` / `SM_S936N` passed `script/check_physical_external_relay_pairing.sh --allow-private-relay --expect-chat-complete --live-backend --chat-model-query "LM Studio"` against a same-LAN private relay at `192.168.0.102:43171`, with `adb_reverse_absence_proven=true`, Android endpoint probe and route probe success, `android_pairing_summary_no_relay_adb_reverse=true`, selected-model runtime-log confirmation, trusted reconnect, natural `chat.done`, and `chat_expected_terms_observed=["AetherLinkLANRelayLMStudioProof"]` in `build/qa/android-physical-private-relay-lmstudio-chat-complete-20260708-0532.json` plus the child summary JSON. This advances relay-route proof beyond USB-reverse local relay, but it is still adb deeplink injection over a same-LAN private development relay; optical QR, public/VPN/tunnel external relay, production relay/session/encryption, direct Android backend access, and real different-network proof remain separate.
Latest RuntimeDevServer LM Studio provider eval matrix: authenticated RuntimeDevServer-mediated real LM Studio eval now passes for `google/gemma-4-e4b` across `korean_local_runtime_summary`, `runtime_boundary_explanation`, and `structured_json_boundary`, with expected terms observed, answer/reasoning deltas, redacted summary JSON, and preserved trusted-route reconnect/revocation checks in `build/qa/runtime-provider-eval-lmstudio-20260708-052117.json`; `script/runtime_authenticated_mock_smoke.swift` now supports `--real-lmstudio-eval-models` beside the existing Ollama eval path and keeps `lm_studio_proof=true` while Android, production relay/session/encryption, and real different-network proof remain false. This is live LM Studio through the runtime host, not Android client proof, optical QR, production relay/session/encryption, or real different-network proof.
Latest physical Android live LM Studio chat-complete smoke: `R3CXC0M76VM` / `SM_S936N` passed a physical Android `--expect-chat-complete --expect-reconnect --capture-ui-polish` relay smoke using live LM Studio `google/gemma-4-e4b` in `build/qa/android-physical-live-lmstudio-chat-complete-20260708-051116.json`, with accepted pairing, `runtime.health`, `models.list`, Android model-row selection for LM Studio, selected-model runtime-log confirmation, request-id-bound chat send/delta/natural done, no `chat.cancel`, `chat_expected_terms_observed=["AetherLinkLMStudioCompleteProof"]`, trusted reconnect, and durable artifacts copied to `build/qa/android-physical-live-lmstudio-chat-complete-20260708-051116/`. This is adb-deeplink/USB-reverse/local-development-relay evidence through the runtime host, not optical QR, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest physical Android live LM Studio chat-cancel smoke: `R3CXC0M76VM` / `SM_S936N` passed a physical Android `--expect-chat-cancel --expect-reconnect --capture-ui-polish` relay smoke using live LM Studio `google/gemma-4-e4b` in `build/qa/android-physical-live-lmstudio-chat-cancel-20260708-050325.json`, with accepted pairing, `runtime.health`, `models.list`, Android model-row selection for LM Studio, selected-model runtime-log confirmation, chat send/delta/cancel/done, trusted reconnect, and a complete UI-polish artifact manifest copied to `build/qa/android-physical-live-lmstudio-chat-cancel-20260708-050325/`. This remains chat/cancel evidence through adb-deeplink/USB-reverse/local-development-relay; the later LM Studio chat-complete smoke covers expected-term completion, while optical QR, production relay/session/encryption, direct Android backend access, and real different-network proof remain separate.
Latest physical external-relay chat-complete pass-through gate: `script/check_physical_external_relay_pairing.sh` now forwards `--expect-chat-complete`, `--chat-complete-timeout`, `--chat-expected-terms`, and `--chat-model-query` into the child Android pairing smoke, preserves safe child chat-complete proof booleans in wrapper summary JSON, and keeps seeded no-device redaction self-tests separate from physical external-relay success; this prepares a future operator-confirmed public/VPN/tunnel/private-overlay relay phone run, but it is not itself external relay reachability, optical QR, production relay/session/encryption, or real different-network proof.
Latest physical Android live Ollama chat-complete smoke: `R3CXC0M76VM` / `SM_S936N` passed a physical Android `--expect-chat-complete` relay smoke using live Ollama `gemma4:e4b-mlx` in `build/qa/android-physical-live-ollama-chat-complete-20260708-042530.json`, with accepted pairing, `runtime.health`, `models.list`, selected-model runtime-log confirmation, request-id-bound chat send/delta/natural done, no `chat.cancel`, and `chat_expected_terms_observed=["AetherLinkCompleteProof"]`; durable pairing/chat-complete captures and logs were copied to `build/qa/android-physical-live-ollama-chat-complete-20260708-042530/`. This is adb-deeplink/USB-reverse/local-development-relay evidence through the runtime host, not optical QR, LM Studio, production relay/session/encryption, direct Android backend access, or real different-network proof.
Latest RuntimeDevServer Ollama provider eval matrix: authenticated RuntimeDevServer-mediated real Ollama eval now passes for `gemma4:e4b-mlx`, `gemma4:26b-mlx`, and `qwen3.6:35b-mlx` across `korean_local_runtime_summary`, `runtime_boundary_explanation`, and `structured_json_boundary`, with expected terms observed, answer/reasoning deltas, redacted summary JSON, and preserved trusted-route reconnect/revocation checks in `build/qa/runtime-provider-eval-ollama-matrix-20260708-035945.json` and `.log`; the fix also preserves whitespace-only `assistant_delta` and `reasoning_delta` chunks in JSONL/SQLite chat storage while still rejecting empty deltas. This is live Ollama through the runtime host, not Android client proof, LM Studio proof, optical QR, production relay/session/encryption, or real different-network proof.
Latest physical external-relay Android pairing summary artifact: `check_physical_external_relay_pairing` now passes a derived `--summary-json` path to the child Android pairing smoke, fails successful-looking external-relay runs when child pairing summary success is missing, and records safe child-summary proof-boundary booleans without turning no-device self-tests into physical external-relay proof; the default no-device gate passed in `build/qa/check-no-device-quality-physical-external-child-summary-20260708-031956.log`.
Latest physical Android live Qwen UI polish smoke: `R3CXC0M76VM` / `SM_S936N` passed a combined live-provider and UI-polish smoke using Ollama `qwen3.6:35b-mlx` in `build/qa/android-physical-live-qwen-ui-polish-20260708-034114.json`, with matching serials, `success=true`, live-provider chat/cancel, selected-model runtime-log confirmation, trusted reconnect, and a complete UI-polish artifact manifest copied to `build/qa/android-physical-live-qwen-ui-polish-20260708-034114/`; LM Studio was unavailable during that qwen run before the later live LM Studio chat/cancel smoke, and this is still adb-deeplink/USB-reverse/local-development-relay evidence, not optical QR, production relay/encryption, or real different-network proof.
Latest physical Android large-font UI polish smoke: `R3CXC0M76VM` / `SM_S936N` passed a temporary `font_scale=1.3` physical UI-polish smoke in `build/qa/android-physical-large-font-ui-polish-20260708-033636.json`, with chat, model selector, drawer, Settings, launcher, pairing, chat/cancel screenshots/XML copied to `build/qa/android-physical-large-font-ui-polish-20260708-033636/`; the wrapper log restored the original `font_scale=1.15`, and this remains physical rendering spot-check evidence, not physical TalkBack traversal, optical QR, live-provider, production relay, or real different-network proof.
Latest Android pairing summary JSON failure-path proof-boundary: `android_pairing_deeplink_smoke --self-test-summary-json-failure` now writes a synthetic failed summary with `success=false`, preserved nonzero `exit_status`, no observed serial, false live/physical proof booleans, and no route/backend material; `check_android_pairing_summary_json_guard` runs both success and failure summary self-tests, the default no-device gate passed in `build/qa/check-no-device-quality-summary-json-failure-path-20260708-025927.log`, and after the phone was reconnected `R3CXC0M76VM` / `SM_S936N` passed the matching physical adb-deeplink/reconnect/chat-cancel/UI-polish summary smoke in `build/qa/android-physical-summary-json-after-failure-boundary-20260708-030821.json`.
Latest Android pairing summary UI polish artifact manifest: `android_pairing_deeplink_smoke --summary-json` now records chat, model selector, drawer, Settings, and launcher PNG/XML paths under `paths.ui_polish_artifacts` when `--capture-ui-polish` artifacts exist; the no-device summary self-test validates manifest completeness without claiming physical UI proof, `R3CXC0M76VM` / `SM_S936N` passed the matching attached-phone capture with `build/qa/android-physical-ui-polish-summary-manifest-20260708-024059.json`, and the default no-device gate passed in `build/qa/check-no-device-quality-ui-polish-summary-manifest-20260708-024635.log`.
Latest QA evidence latest-entry hygiene: `script/check_docs_hygiene.py` now validates the latest dated `docs/qa-evidence.md` entry for proof-boundary wording, no-device scope, physical/live-provider separation, agent-state wording, caveat, and concrete verification commands, with `script/check_copy_hygiene.py` and the default no-device gate pinning the QA evidence latest-entry proof-boundary hygiene.
Latest Android pairing summary JSON proof-boundary: physical Android pairing smoke now emits `--summary-json` evidence with safe event counts and explicit proof booleans for adb deeplink injection, live-provider chat/cancel, selected-model runtime-log confirmation, reconnect, and UI capture, while keeping optical QR, production relay, production transport encryption, real different-network, direct Android backend access, and raw route-material proof false or absent; the no-device summary guard now self-tests both success and failure-path summaries, the default no-device gate completed with this guard in `build/qa/check-no-device-quality-summary-json-20260708-021121.log`, a fresh connected-device reinstall smoke completed in `build/qa/android-physical-live-ollama-summary-json-fresh-20260708-022103.log`, and after the external-relay child-summary gate the connected phone passed another live Ollama run in `build/qa/android-physical-live-ollama-after-external-child-summary-20260708-033112.json` with matching serials, `success=true`, live-provider chat/cancel, selected-model runtime-log confirmation, and trusted reconnect before the later LM Studio physical and RuntimeDevServer eval proofs.
Latest Swift relay allocation relay-id canonicality: RelayAllocation rejects URL-shaped, path-shaped, query, fragment, user-info, host:port, oversized, blank, and whitespace-mutated relay IDs before allocation response or persisted ticket use, matching the relay control-line canonicality rule.
Latest runtime memory.list query resource guard: authenticated memory.list now rejects overlong or excessive-term lexical queries before runtime memory-store search dispatch, keeping current memory search deterministic and bounded before future embedding-backed search work.
Latest SQLite runtime chat retention policy: production runtime chat maintenance now owner-scopes deleted-session pruning behind a 90-day/100-row default policy while preserving active/archived sessions and tombstone-backed legacy resurrection prevention; the production maintenance seam now invokes that primitive.
Latest Android pending pairing identity canonicality: pending pairing route storage rejects whitespace-mutated or oversized pairing nonces, runtime device ids, and fingerprints, and rejects whitespace-mutated pairing codes, before pending route restore or accepted-pairing identity comparison.
Latest Android pending pairing runtime public-key canonicality: pending pairing route storage rejects whitespace-mutated or oversized runtime public keys before pending route restore, route planning, or accepted-pairing identity comparison.
Latest Android Settings Connection Status TalkBack-order proxy: Settings-embedded QR scan, route recovery notice, refresh, disconnect, and auto-reconnect controls keep localized semantics and reachable bounds order at large font in no-device Compose coverage.
Latest Android route-refresh QR stale material rejection: Android route-refresh QR stale material rejection rejects reused relay nonces, reused P2P record IDs, reused P2P anti-replay nonces, and non-advancing relay or P2P expiries before trusted route storage changes.
Latest macOS Bonjour requested-route-token metadata: requested_route_token and requested-route-token debug metadata are rejected before TXT publication, so local discovery cannot advertise allocation/debug route-token fields through route_token, app, or version hints.
Latest shared pairing QR usb-reverse loopback host schema: decoded pairing QR schema checks now accept loopback relay hosts only as explicit `usb_reverse` debug route material across `relay_scope`, `remote_scope`, `route_scope`, and compact `rsc`, and QR verification rejects remote-scoped loopback artifacts even with local-relay diagnostics enabled.
Latest shared route.refresh relay_host scope eligibility schema: authenticated `route.refresh` rejects mDNS-local, unspecified, link-local, multicast, and broadcast relay hosts at schema level and requires `relay_scope=usb_reverse` for loopback refresh material before route material can validate.
Latest shared route.refresh relay_host canonicality schema: authenticated `route.refresh` `relay_host` uses a canonical host schema that rejects whitespace-mutated, URL-shaped, path, query, fragment, and user-info host values before route material can validate.
Latest macOS route.refresh relay host producer canonicality: macOS runtime-provider `route.refresh` rejects URL-shaped, path, query, fragment, user-info, port-suffixed, and whitespace-mutated relay hosts before emitting route material.
Latest Android device identity atomic persistence: first-run Android client identity creation writes no `android_device_id` or `android_device_name` until the signing keypair seam succeeds.
Latest shared pairing QR semantic alias exclusivity schema: shared QR artifact validation rejects mixed decoded aliases for the same semantic field across identity, route-token, local diagnostic endpoint, relay id, and relay scope fields before Android parser-specific handling.
Latest Android pairing QR semantic alias conflict rejection: Android QR parsing rejects mixed decoded aliases for the same semantic field, including conflicting relay-scope aliases, before field selection or route material assembly.
Latest shared QR verifier semantic alias rejection: rendered QR artifact verification rejects mixed decoded aliases for the same semantic field before route material validation, matching Android parser semantic-alias conflict rejection.
Latest shared QR verifier alias-family parity: rendered QR artifact verification rejects mixed relay and P2P alias families, accepts complete `rendezvous_*` relay route material, and rejects malformed relay secrets before no-device QR evidence can pass.
Latest macOS pairing QR relay host-scope eligibility: macOS QR generation emits relay route material only when relay host and relay scope match the shared policy: public/DNS with no scope or remote, private-overlay literals with private_overlay, and loopback with usb_reverse.
Latest macOS pairing QR relay host canonical emission: macOS QR generation emits the normalized relay host used for eligibility checks, so uppercase/trailing-dot DNS names and bracketed IPv6 literals become canonical camera QR host values before Android scans them.
Latest macOS pairing QR opaque route-material canonicality: macOS QR generation omits whitespace-mutated or oversized optional opaque route material before emitting runtime public-key, route-token, relay, or P2P query fields, while preserving canonical `+`, `/`, and `=` values.
Latest macOS pairing QR route-material numeric validity: macOS QR generation omits invalid relay ports and non-positive relay or P2P route expiries before emitting complete relay or P2P QR families.
Latest Android pairing QR unknown query-key rejection: Android QR parsing rejects decoded query keys outside the shared schema allowlist before identity, relay, P2P, backend, or model-shaped metadata can be ignored.
Latest shared QR verifier unknown query-key rejection: rendered QR artifact verification rejects decoded query keys outside the shared schema allowlist before route material validation.
Latest shared QR verifier duplicate query-key rejection: rendered QR artifact verification rejects repeated decoded query keys before route material validation, matching Android parser duplicate-key rejection.
Latest private-overlay QR scope canonicality: QR artifact verification rejects case- or whitespace-mutated `relay_scope`/`rsc` values before private-overlay QR evidence is counted.
Latest Android pairing QR P2P protocol-version canonicality: Android QR parsing rejects leading-zero, plus-prefixed, and compact non-canonical P2P protocol version values before accepting P2P rendezvous route material.
Latest Android pairing QR relay port canonicality: Android QR parsing and rendered QR verification reject signed or zero-padded relay port strings before accepting relay route material.
Latest shared route.refresh runtime identity canonicality schema: authenticated `route.refresh` `runtime_device_id` and `runtime_key_fingerprint` use the same whitespace-free, 512-character opaque value rule as route material.
Latest Android route.refresh runtime identity canonicality: authenticated Android `route.refresh` rejects whitespace-mutated or oversized runtime device ids and runtime key fingerprints before exact identity matching or trusted route storage changes.
Latest Android route.refresh malformed allowed-field retry: authenticated Android `route.refresh` responses reject malformed allowed field types without trusted route storage changes and preserve the active-lease retry path.
Latest macOS authenticated route.refresh diagnostic opt-in: macOS app runtime keeps authenticated `route.refresh` unavailable by default and exposes fresh route material only under explicit diagnostic opt-in.
Latest Android route.refresh relay material canonicality: authenticated `route.refresh` rejects whitespace-mutated, URL-shaped, oversized, private-overlay scope-mismatched, and loopback scope-mismatched relay material before trusted runtime storage changes.
Latest Android route.refresh response unknown metadata rejection: authenticated Android `route.refresh` responses reject schema-unknown payload fields such as `backend_url` before permissive client decoding or trusted runtime storage, preserving the current route for retry.
Latest macOS Bonjour TXT metadata boundary: Bonjour/local discovery TXT metadata publishes only the pairing-derived route token as the identity hint; stable runtime device ids, public-key fingerprints, backend/provider/model data, and runtime payload metadata stay out of local discovery TXT.
Latest macOS Bonjour route-token canonicality: whitespace-mutated route_token values are omitted instead of normalized, so local discovery cannot trim malformed route identity hints into trusted matches.
Latest Android Bonjour TXT receive canonicality: Android drops discovered peers with whitespace-mutated, oversized, malformed UTF-8, or forbidden `route_token` TXT metadata before `DiscoveredRuntime` can feed trusted discovery matching.
Latest Android pending pairing route-token canonicality: pending pairing route storage rejects whitespace-mutated or oversized `routeToken` values instead of trimming them into pending trusted identity material.
Latest Android pending pairing runtime public-key canonicality: pending pairing route storage rejects whitespace-mutated or oversized runtime public keys instead of trimming them into pending trusted identity material.
Latest Android stored trusted identity canonicality: PairingStore rejects whitespace-mutated or oversized stored runtime device ids, fingerprints, and public keys before trusted runtime restore or persistence.
Latest Android app relay route-material canonicality: pending route storage and RuntimeRemoteRoutePlanner reject whitespace-mutated or oversized relay hosts, relay ids, frame secrets, nonces, and scopes before pending restore, trusted reconnect target state, or prepared route planning.

1. Physical client-device QA after the latest UI/protocol changes. Current proof: `R3CXC0M76VM` / `SM_S936N` passed the post-Swift-relay-allocation-canonicality relay deeplink smoke with current debug APK install, clean app data, QR/deeplink pairing, saved trusted-route reconnect through USB `adb reverse`, Korean-locale chat send/cancel, and physical chat/model selector/drawer/Settings/launcher capture in `build/qa/android-physical-relay-post-allocation-canonicality-20260708-012939.log`; it then passed a live-backend relay smoke with `gemma4:e4b-mlx` available through Ollama, RuntimeDevServer in `Ollama + LM Studio` mode, `chat.send`, streamed `chat.delta`, `chat.cancel`, `chat.done`, and saved-route reconnect in `build/qa/android-physical-live-ollama-post-allocation-canonicality-20260708-013834.log`. The physical smoke now also supports `--chat-model-query` and passed a model-targeted live Ollama run that selected `gemma4:e4b-mlx`, confirmed `relay received chat.send model=ollama:gemma4:e4b-mlx`, streamed, cancelled, completed, and reconnected in `build/qa/android-physical-live-ollama-chat-model-query-20260708-014907.log`, while the no-device gate `build/qa/check-no-device-quality-chat-model-query-selector-20260708-015216.log` proves provider-qualified `lm_studio:target-model` row matching for future LM Studio proof without claiming phone model-selection proof. The latest summary-backed physical smoke wrote `build/qa/android-physical-live-ollama-summary-json-20260708-020828.json` with `success=true`, live-provider chat/cancel, selected-model log confirmation, trusted reconnect, and explicit false booleans for optical QR, production relay, production transport encryption, direct Android backend access, and real different-network proof; after the phone was reconnected, `build/qa/android-physical-live-ollama-summary-json-fresh-20260708-022103.json` repeated the same proof with current debug APK install, exit 0, selected screenshot/log artifacts, and matching proof-boundary booleans. The latest UI-polish summary-manifest phone run wrote `build/qa/android-physical-ui-polish-summary-manifest-20260708-024059.json` with `success=true`, matching requested/observed serials, complete `paths.ui_polish_artifacts`, chat/cancel, trusted reconnect, and copied chat/model selector/drawer/Settings/launcher screenshots/XML in `build/qa/android-physical-ui-polish-summary-manifest-20260708-024059/`. After the failure-path summary guard was added, `build/qa/android-physical-summary-json-after-failure-boundary-20260708-030821.json` passed on the same phone with `success=true`, matching serials, adb deeplink injection, accepted pairing, `runtime.health`, `models.list`, trusted reconnect, chat send/delta/cancel/done, complete UI-polish artifact manifest, and expected false booleans for live-provider, optical QR, production relay, production transport encryption, direct Android backend access, and real different-network proof. After the physical external-relay child-summary no-device gate, the currently connected phone passed another live Ollama run with `gemma4:e4b-mlx` in `build/qa/android-physical-live-ollama-after-external-child-summary-20260708-033112.json` and `build/qa/android-physical-live-ollama-after-external-child-summary-20260708-033112.log`; the summary records matching serials, `success=true`, `exit_status=0`, live-provider chat/cancel, selected-model runtime-log confirmation, and trusted reconnect, before the later LM Studio live chat/cancel and chat-complete proofs. The same phone then passed a combined live-provider/UI-polish run with Ollama `qwen3.6:35b-mlx` in `build/qa/android-physical-live-qwen-ui-polish-20260708-034114.json` and `build/qa/android-physical-live-qwen-ui-polish-20260708-034114.log`, proving qwen selected-model runtime-log confirmation, live chat/cancel, trusted reconnect, and durable chat/model selector/drawer/Settings/launcher artifacts in `build/qa/android-physical-live-qwen-ui-polish-20260708-034114/` without converting the run into LM Studio, optical QR, production relay/encryption, or real different-network proof. `build/qa/check-no-device-quality-summary-json-20260708-021121.log` covers the matching default-gate summary JSON guard. Optical camera QR scanning, external public relay, broader live provider-backed chat/cancel, chat-complete, and model-quality evaluation beyond current local-development relay proofs, and real different-network runtime connectivity still remain.
   - RuntimeDevServer-mediated Ollama and LM Studio model-quality evaluation is no longer part of the open gap for the tested fixed prompts and tested models; remaining live-provider gaps are broader multi-model comparisons, Android-client model-quality review beyond adb-deeplink smokes, optical QR, production relay/session/encryption, and real different-network proof.
2. Screenshot-based client UI polish for a cleaner modern/classic chat surface, drawer, model selector, settings, and transcript spacing. Current no-device guardrail: a representative populated Android chat surface now renders at compact width and large font across the supported app languages with top bar, transcript attachment, reasoning, latest actions, jump control, and composer bounds checked together, the closed Chat top bar now keeps long active titles bounded beside compact long-name model pickers, keeps the streaming-disabled model picker bounded beside active titles, and keeps the New Chat action bounded across ready, streaming-disabled, and pairing-required states, Chat empty states now keep compact large-font title/body/action bounds across no-model and latest-QR recovery states, assistant identity markers now have compact large-font coverage for one-glyph and two-glyph localized initials, QR recovery diagnostics now keep compact route availability notice coverage for relay-auth failure, private-overlay scope, remote identity mismatch, and failed P2P/no-relay cases, Connection Status route notices now keep saved-route and latest-QR recovery action layouts bounded across compact large-font surfaces, route-refresh saved notices now stay bounded above the docked Chat composer and inside the Settings QR pairing panel on compact large-font surfaces, Settings pending pairing route status now keeps route-incomplete QR recovery title/detail/progress bounds on compact large-font surfaces, Settings companion-only private model access now keeps title/detail bounds on compact large-font surfaces, Settings troubleshooting discovery actions now keep idle/running controls, progress, and empty-state bounds on compact large-font surfaces, Settings developer diagnostics toggle now keeps title/detail/switch bounds on compact large-font surfaces, drawer previous-chat overflow menus now keep localized visible labels and compact bounds coverage, the opened model picker now has general selected/running/uninstalled row compact coverage, the real SettingsScreen expanded Memory indexing model section now has compact large-font embedding-row coverage, Settings Memory approved-source metadata now has compact large-font bounds coverage, Settings Memory add controls now keep compact large-font bounds across disconnected, connected-empty, connected-ready, and add-success states, Settings Memory empty states now keep compact large-font bounds across disconnected, connected-empty, and streaming-lock states, Settings Chat history search-refresh header now keeps compact large-font bounds across disconnected, connected, and filtered search states, chat-history confirmation dialogs now keep localized two-step destructive action labels bounded across compact large-font surfaces, share-sheet import confirmation snackbars now stay bounded above the docked Chat composer on compact large-font surfaces, archive undo snackbars now keep localized message/action bounds above the docked Chat composer on compact large-font surfaces, the Android Chat TalkBack-order proxy now keeps transcript rows, latest message actions, jump-to-latest, ready send composer, and streaming cancel composer controls covered by localized semantics and bounds order at large font, and the Settings-embedded Connection Status TalkBack-order proxy now keeps QR scan, route recovery notice, refresh, disconnect, and auto-reconnect controls reachable with localized semantics at large font; physical screenshots on `R3CXC0M76VM` now cover chat, model selector, drawer, Settings, and launcher without visible text overlap, and the temporary `font_scale=1.3` physical smoke in `build/qa/android-physical-large-font-ui-polish-20260708-033636.json` copied the same screen families plus pairing/chat-cancel artifacts into `build/qa/android-physical-large-font-ui-polish-20260708-033636/` while restoring the original `font_scale=1.15`; broader physical device/font coverage and physical TalkBack traversal still remain.
3. Capture launcher/dock screenshots on real devices to verify the generated AetherLink icon reads correctly at small sizes. Current proof: the `R3CXC0M76VM` Samsung launcher screenshot shows the `AetherLink` icon and label, and `build/qa/aetherlink-macos-dock-visible.png` shows the `dist/AetherLink.app` bundle icon rendered in the macOS Dock with `CFBundleIconFile=AppIcon`; additional device launcher/Dock sizes and app-store metadata captures still remain.
4. Continue hardening pairing/trusted-device UX so normal users pair or refresh routes by scanning QR; macOS clean first-run Pairing now exposes Connection Recovery only where route material is missing, keeps Status diagnostics quiet, bounds remote preparation, preserves the last visible QR on failed renewal, and Vision-decodes the rendered remote-required payload in no-device tests. Android product defaults no longer advertise or automatically send authenticated `route.refresh`, and the Android Settings route-incomplete QR recovery card has no-device compact coverage, but physical-device camera and recovery flows still need review.
5. Replace the temporary relay/fixed-endpoint development assumptions with a paired-device private encrypted overlay:
   - paired private peer identity as the primary connection target,
   - QR-bootstrapped overlay/rendezvous/relay material for same-network and different-network use,
   - local direct connection as an opportunistic fast path,
   - remote P2P NAT traversal for different networks using STUN-like address discovery and authenticated hole punching,
   - optional DHT/bootstrap-peer rendezvous for short-lived paired-device discovery records,
   - end-to-end encrypted blind relay/TURN fallback only when direct paths fail,
   - no AI protocol payloads, model lists, prompts, files, memory, backend credentials, backend URLs, or model commands visible to any relay or discovery service.
6. Continue expanding smoke tests while separating no-device gate coverage from live proof gaps.
	   - Named no-device/default-gate coverage currently includes: pairing, product QR scanner route-material policy, QR pairing preemption, no-ADB QR artifact machine-readable summary coverage, no-ADB QR temporary route-material artifact summary, private-overlay QR artifact coverage, private-overlay relay scope schema guard, authenticated model list, pre-auth unknown metadata rejection, pairing.request blank allowed field rejection, empty runtime request unknown metadata rejection, RuntimeDevServer non-object payload decode rejection, RuntimeDevServer envelope version/request_id decode rejection, RuntimeDevServer envelope timestamp decode rejection, RuntimeDevServer envelope type/payload decode rejection, RuntimeDevServer envelope unknown top-level metadata decode rejection, macOS protocol envelope required-field decode, macOS protocol envelope unknown top-level field decode, Android protocol envelope required-field decode, Android protocol envelope version/request_id semantic decode, Android protocol envelope timestamp format decode, Android protocol envelope unknown top-level field decode, response-only message direction rejection, models.pull unknown metadata rejection, models.pull invalid allowed type rejection, chat.cancel acknowledgement target id schema parity, streaming chat, cancel, chat.cancel unknown metadata rejection, chat.title.request unknown metadata rejection, chat.title.request invalid allowed type rejection, chat model identifier nonblank rejection, chat.sessions.list unknown metadata rejection, chat.sessions.list invalid allowed type rejection, chat.messages.list unknown metadata rejection, chat.messages.list invalid allowed type rejection, chat.session rename unknown metadata rejection, chat.session lifecycle unknown metadata rejection, memory.list unknown metadata rejection, memory.list invalid allowed type rejection, memory.upsert unknown metadata rejection, memory.upsert invalid allowed type rejection, memory.delete unknown metadata rejection, memory.summary.drafts.list unknown metadata rejection, memory.summary.drafts.list invalid allowed type rejection, memory.summary draft decision unknown metadata rejection, memory.summary draft decision invalid allowed type rejection, memory.summary draft optional string nonblank rejection, memory.summary draft decision blank draft_id rejection, attachments, chat.send top-level payload metadata rejection, chat.send invalid allowed type rejection, chat.send message metadata rejection, attachment source metadata rejection, DocumentIngestion resource policy, protocol reserved projects/automation namespace guard, RuntimeDevServer reserved projects/automation namespace rejection, protocol generic tool namespace guard, RuntimeDevServer generic tool namespace rejection, protocol reserved permission/approval/audit namespace guard, RuntimeDevServer reserved permission/approval/audit namespace rejection, protocol reserved runtime action namespace guard, RuntimeDevServer reserved runtime action namespace rejection, protocol reserved RAG/research namespace guard, RuntimeDevServer reserved RAG/research namespace rejection, protocol reserved skills/MCP/web-search namespace guard, protocol reserved Python namespace guard, RuntimeDevServer future Python namespace rejection, protocol route namespace guard, RuntimeDevServer future route namespace rejection, macOS protocol model metadata parity, Android protocol model metadata parity, Android protocol document index/retrieval payload parity, Android selected embedding-model search hint, runtime embedding search-hint boundary, RuntimeDevServer embedding search-hint smoke, runtime memory list search, RuntimeDevServer memory.list query search metadata smoke, RuntimeDevServer memory.list query ciphertext marker, RuntimeDevServer future memory.search rejection, RuntimeDevServer memory-summary stale guard, RuntimeDevServer memory source-audit immutability, RuntimeDevServer chat compaction backend-only audit, Android Settings memory runtime search, LM Studio vision image native/fallback request shape, memory-summary draft approval/dismissal paths, Android chat-history confirmation compact dialog layout, Android Chat TalkBack-order proxy, Android Settings Connection Status TalkBack-order proxy, route.refresh relay freshness, shared route.refresh private-overlay scope schema, Android route.refresh relay payload acceptance/incomplete rejection, Android route.refresh rejected-payload retry, Android route.refresh P2P noncanonical rejection, Android route.refresh response unknown metadata rejection, route.refresh timing policy, Android authenticated relay route.refresh scheduling/retry, Android authenticated relay reconnect route.refresh fresh lease, Android trusted relay reconnect scope eligibility, Android trusted relay reconnect preflight race, Android pending relay QR planning eligibility, Android pairing relay QR direct-endpoint suppression, Android pairing P2P QR direct-endpoint suppression, Android accepted-pairing incomplete relay route, Android accepted-pairing relay secret restore boundary, Android accepted-pairing runtime identity mismatch rejection, Android client-side runtime proof rejection, Android initial pairing QR expired P2P record rejection, Android initial pairing QR expired relay lease rejection, Android saved relay reconnect pinned-identity rejection, Android saved relay lease reconnect eligibility, Android trusted remote-route target endpoint-hint suppression, Android route-refresh QR relay add-route, Android route-refresh QR P2P add-route, Android route-refresh QR optional-public-key relay update, Android route-refresh QR optional-public-key P2P update, Android route-refresh QR fixed-endpoint fallback removal, Android route-refresh QR direct-only rejection, Android route-refresh QR route-token rotation, Android route-refresh QR pinned-identity rejection, Android route-refresh QR expired-or-incomplete relay rejection, Android route-refresh QR expired-or-incomplete P2P rejection, relay client retirement, duplicate relay QR idempotency, relay/P2P route-refresh QR active-connection reuse, physical external-relay summary, physical external-relay URL host input redaction, physical external-relay probe-summary route-material redaction, requested-serial evidence binding, different-network confirmation gate, Android relay reachability probe input guard, Android relay reachability probe route-material redaction, Android pairing deeplink am-start route-material redaction, Android pairing deeplink allocation-token argv redaction, Android pairing/trusted relay host canonicality, Android relay route-material canonicality, Android app relay route-material canonicality, Android pairing QR relay alias-family isolation, shared pairing QR relay alias-family schema, shared pairing QR route-scope private-overlay schema, Android pairing QR P2P alias-family isolation, shared pairing QR P2P alias-family schema, Android stored route-token canonicality, Android stored trusted identity canonicality, Android trusted relay store canonicality, model-residency unload behavior, model-residency foreground completion cleanup, macOS unknown unqualified model routing, macOS qualified provider model routing rejection, relay allocation lease lifecycle, relay allocation opacity, relay allocation request input rejection, relay allocation base64 requested-secret, relay wrapper allocation-token argv redaction, relay allocation response field validation, relay control-line framing, relay control-line relay-id canonicality, relay readiness runtime-only probe, relay preflight opaque-id echo rejection, relay preflight output redaction, relay preflight failure-output redaction, Android route-token remote material isolation, Android direct model-provider route block, Android Bonjour discovery identity metadata boundary, Android Bonjour discovery unpinned route-token strictness, identity-only no-route transport boundary, Android relay frame cryptor nonce-bound vector, relay TCP ready timeout, Android relay concurrent encrypted send serialization, pending route-less QR no saved relay fallback, diagnostic identity-only discovery wait, prepared relay route ordering, Android P2P connector dispatch, Android P2P route-family isolation, accepted pairing incomplete P2P route, Android trusted P2P restore discovery suppression, Android opaque route material size bounds, shared route-material schema size bounds, suggested-question current docs/ops tombstone coverage, macOS pairing QR payload shape, macOS P2P QR canonical generation, macOS runtime identity fallback signing, macOS trusted hello runtime proof, remote route identity binding, remote route expiry connector guard, remote route direct transport boundary, macOS route.refresh failure redaction, macOS stale GUI relay QR renewal, unload-failure health redaction, macOS untrusted hello unit rejection, macOS pairing abuse structured rejection, and untrusted-client rejection coverage.
	   - Latest no-device coverage addendum: physical external-relay chat-complete pass-through, Android pairing chat-complete summary JSON proof-boundary, physical external-relay Android pairing summary artifact, Android pairing summary JSON failure-path proof-boundary, Android pairing summary UI polish artifact manifest, QA evidence latest-entry proof-boundary hygiene, shared pairing QR usb-reverse loopback host schema, shared route.refresh relay_host canonicality schema, shared pairing QR semantic alias exclusivity schema, Android pairing QR semantic alias conflict rejection, shared QR verifier semantic alias rejection, shared pairing QR relay-scope alias exclusivity schema, macOS pairing QR relay host-scope eligibility, macOS pairing QR relay host canonical emission, macOS pairing QR opaque route-material canonicality, macOS pairing QR route-material numeric validity, Android pairing QR P2P protocol-version canonicality, shared route.refresh runtime identity canonicality schema, Android route.refresh runtime identity canonicality, Android route.refresh malformed allowed-field retry, private-overlay QR scope canonicality, Android route.refresh relay material canonicality, Android route.refresh response unknown metadata rejection, shared pairing QR route-scope private-overlay schema, shared route.refresh private-overlay scope schema, shared pairing QR relay alias-family schema, Android pairing/trusted relay host canonicality, shared pairing QR P2P alias-family schema, different-network/no-ADB wrapper allocation-token argv redaction, Android pairing QR P2P alias-family isolation, Android stored route-token canonicality, Android stored trusted identity canonicality, Android app relay route-material canonicality, Android relay route-material size-bound, relay wrapper allocation-token argv redaction, relay allocation base64 requested-secret, relay control-line relay-id canonicality, Android pairing QR relay alias-family isolation, Android trusted relay store canonicality, macOS route.refresh opaque material size-bound, Android pairing QR relay-secret canonicality, Android pairing QR service_type discovery-hint sanitization, Android pairing QR duplicate query-key rejection, shared QR verifier duplicate query-key rejection, shared QR verifier unknown query-key rejection, Android Bonjour discovery unpinned route-token strictness, relay preflight unexpected-field rejection, relay preflight response value canonicality, relay preflight expiry type strictness, relay preflight host input guard, different-network relay endpoint input redaction, Swift relay allocation unexpected metadata rejection, relay allocation store unexpected metadata rejection, relay allocation request unexpected metadata rejection, RuntimeDevServer non-object payload decode rejection, RuntimeDevServer envelope version/request_id decode rejection, RuntimeDevServer envelope timestamp decode rejection, RuntimeDevServer envelope type/payload decode rejection, RuntimeDevServer envelope unknown top-level metadata decode rejection, macOS protocol envelope required-field decode, macOS protocol envelope unknown top-level field decode, Android protocol envelope required-field decode, Android protocol envelope version/request_id semantic decode, Android protocol envelope timestamp format decode, Android protocol envelope unknown top-level field decode, memory.summary draft optional string nonblank rejection, memory.summary draft decision blank draft_id rejection, models.pull blank model rejection, chat model identifier nonblank rejection, RuntimeDevServer memory.delete empty/blank id smoke, and chat.cancel acknowledgement target id schema parity.
   - Runtime embedding-backed chat semantic search addendum: provider batch request/response validation, installed local embedding-model routing, bounded owner-scoped cosine ranking, no vector/model-id echo, no silent lexical fallback on embedding failure, inline-byte exclusion, and RuntimeDevServer embedding semantic-search smoke are in the default no-device gate.
   - Current QR parser addendum: Android pairing QR unknown query-key rejection now aligns the Android parser with the shared QR schema's closed field set.
   - Current focused addendum: relay ciphertext sensitive-class canary coverage pins encrypted frame-body markers for backend credential, backend URL, model command payload, prompt, file payload label, model-list response, and memory plaintext markers; Android trusted relay scope canonicality pins PairingStore write/read rejection of blank, unknown, case-mutated, and whitespace-mutated `runtime_relay_scope` values before trusted relay restore or persistence; shared pairing QR route-scope private-overlay schema now aligns `route_scope=private_overlay` for `route_*` relay aliases with Android parsing; Android authenticated relay reconnect route.refresh fresh lease now proves the real relay reconnect smoke accepts and persists fresh authenticated `route.refresh` material after the relay nonce changes and the lease advances.
   - App-layer P2P size-bound addendum: Android app P2P encrypted body 2048-byte route material now stays valid through route planning, trusted reconnect dispatch, authenticated `route.refresh`, and pending route storage/restore, matching the shared P2P encrypted-body limit instead of the default 512-character opaque value limit.
   - Route-refresh QR relay-scope isolation addendum: Android route-refresh QR P2P relay-scope isolation now rejects P2P route-refresh QR material that carries stray relay scope without complete relay route material, while preserving explicit `local_diagnostic` direct QR parsing for diagnostics.
   - Route-token remote material isolation addendum: Android route-token remote material isolation now keeps paired runtime `routeToken` as identity/routing metadata and rejects raw reuse as P2P session/rendezvous material or relay route id/rendezvous material before connector use.
   - Relay reachability probe route-material redaction addendum: Android relay reachability probe route-material redaction now keeps raw relay IDs out of physical-probe JSON, stdout, and stderr while preserving safe seeded redaction-test `relay_id_present`, `route_ready`, and `reachable` evidence.
   - Android relay reachability probe self-test proof-boundary addendum: fake-ADB relay probe artifacts now mark `fake_adb_redaction_self_test`, keep observed ADB serial absent, and keep live Android relay/route proof false.
   - Relay preflight output redaction addendum: relay allocation preflight success JSON now keeps requested route tokens, relay secrets, raw relay IDs, raw relay expiries, and raw relay nonces out of long-lived output while preserving safe presence booleans.
   - different-network preflight summary allocation redaction addendum: `run_different_network_dev_runtime.sh --summary-json` now preserves only safe relay allocation presence booleans and explicit proof-boundary coverage, while keeping raw relay ids, secrets, nonces, route tokens, allocation tokens, and production/device/optical proof claims out of preflight-only evidence.
   - relay wrapper dry-run allocation-token redaction addendum: `run_allocation_relay.sh --dry-run` now has no-device coverage proving token-required mode is reported without printing raw allocation-token values or argv-form token flags.
   - relay wrapper dry-run summary proof-boundary addendum: `run_allocation_relay.sh --dry-run --summary-json` now records no relay process, production relay, trusted-device reachability, pairing, or optical QR proof while keeping allocation-token values redacted.
	   - Android pairing deeplink allocation-token argv redaction addendum: `android_pairing_deeplink_smoke.sh` and the physical external-relay wrapper now pass allocation tokens through environment variables so relay/preflight child argv omits `--allocation-token` and raw token values.
	   - No-ADB proof-boundary coverage summary addendum: no-ADB QR summary now separates runtime-host relay registration and waiting-for-peer evidence from trusted-device relay reachability, pairing, runtime.health, reconnect, and optical QR scan proof.
	   - No-ADB external-network proof-boundary summary addendum: no-ADB QR summary now keeps operator-confirmed external-network relay proof, full-run trusted-device proof, production relay proof, verified emit-only QR artifact evidence, hidden unverified self-test evidence, missing operator-confirmation caveats, and operator-confirmed no-device timeout evidence as separate machine-readable fields.
	   - No-ADB expect-reconnect emit-only summary addendum: `--emit-only --expect-reconnect` now records the reconnect expectation mode while keeping trusted-device reconnect, full-run trusted-device proof, external relay proof, production relay proof, and optical QR scan proof false.
	   - no-device production session proof-boundary addendum: no-ADB QR and different-network preflight summaries now keep production session-key exchange and production end-to-end transport encryption proof false with explicit caveats.
	   - protocol reserved encrypted-session namespace guard addendum: `session.`, `key_exchange.`, `encrypted_session.`, and `anti_replay.` active messages remain blocked by protocol schema hygiene.
	   - RuntimeDevServer reserved encrypted-session namespace rejection addendum: authenticated relay smoke rejects `session.key.exchange`, `key_exchange.begin`, `encrypted_session.open`, and `anti_replay.window.commit` with `unknown_message_type` before production encrypted-session control paths exist.
	   - protocol reserved transport/crypto namespace guard addendum: `transport.` and `crypto.` active messages remain blocked by protocol schema hygiene.
	   - RuntimeDevServer reserved transport/crypto namespace rejection addendum: authenticated relay smoke rejects `transport.handshake`, `transport.rekey`, `crypto.session.open`, and `crypto.key.rotate` with `unknown_message_type` before production transport/crypto control paths exist.
	   - response-only message direction rejection addendum: authenticated relay smoke rejects `auth.challenge`, `pairing.result`, `models.result`, `chat.delta`, `chat.done`, `chat.title.result`, and `error` with `unexpected_message_direction` before any client-supplied response frame can mutate runtime state.
	   - protocol generic tool namespace guard addendum: generic `tool.*` active messages remain blocked by protocol schema hygiene until runtime tool permissions, execution, result handling, and audit semantics are designed.
	   - RuntimeDevServer generic tool namespace rejection addendum: authenticated relay smoke rejects `tool.call`, `tool.result`, and `tool.run` with `unknown_message_type` before any runtime generic-tool execution or result path exists.
	   - protocol reserved permission/approval/audit namespace guard addendum: `permission.`, `approval.`, and `audit.` active messages remain blocked by protocol schema hygiene.
	   - RuntimeDevServer reserved permission/approval/audit namespace rejection addendum: authenticated relay smoke rejects `permission.request`, `approval.prompt`, and `audit.events.list` with `unknown_message_type` before production permission broker, mobile approval, or audit-log control paths exist.
	   - protocol reserved runtime action namespace guard addendum: `file.`, `terminal.`, `network.`, and `backend.` active messages remain blocked by protocol schema hygiene.
	   - RuntimeDevServer reserved runtime action namespace rejection addendum: authenticated relay smoke rejects `file.read`, `file.write`, `file.index`, `terminal.exec`, `terminal.kill`, `network.request`, `network.open`, `backend.call`, and `backend.configure` with `unknown_message_type` before production file, terminal, network, or backend action paths exist.
	   - protocol reserved RAG/research namespace guard addendum: `embeddings.`, unsupported `retrieval.` beyond `retrieval.query`, unsupported `index.` beyond `index.documents.list`, `research.`, `citation.`, and `source_control.` active messages remain blocked by protocol schema hygiene.
	   - RuntimeDevServer retrieval.query lexical no-device smoke addendum: authenticated relay smoke accepts `retrieval.query` against a seeded runtime document index with one bounded lexical snippet, rank, matched_terms, document metadata, and chunk offsets while rejecting response-only results plus future source, embedding, citation, trusted-source, and backend metadata before document-index dispatch.
	   - RuntimeDevServer reserved RAG/research namespace rejection addendum: authenticated relay smoke rejects `embeddings.create`, `index.build`, `research.brief.create`, `citation.sources.list`, and `source_control.status` with `unknown_message_type` before production embedding, semantic retrieval, indexing, research, citation, source-control, or trusted-source paths exist.
	   - pre-auth unknown metadata rejection addendum: active `pairing.request`, `hello`, and `auth.response` now reject response-only pairing/auth fields, forged runtime identity/proof fields, backend URL, backend credentials, provider URL, route token, relay secret, requested route token, workspace id, permission grant, source path, source-control state, and other unknown payload metadata before trust, challenge, or authentication mutation.
		   - pairing.request blank allowed field rejection addendum: active `pairing.request` now rejects blank `pairing_nonce`, `pairing_code`, `device_id`, `device_name`, and `public_key` before failed-attempt accounting or trust mutation.
		   - empty runtime request unknown metadata rejection addendum: active `runtime.health`, `models.list`, and `route.refresh` now reject response-only status, models, route material, backend URL, backend credentials, provider URL, route token, relay secret, requested route token, workspace id, permission grant, source path, source-control state, model commands, and other unknown payload metadata before backend or route-refresh dispatch.
		   - models.pull unknown metadata rejection addendum: active `models.pull` now rejects backend URL, provider URL, route token, relay secret, requested route token, workspace id, permission grant, and other unknown payload metadata before backend pull dispatch.
		   - models.pull invalid allowed type rejection addendum: active `models.pull` now rejects non-string, empty, or blank `model`, non-string legacy `backend`, and unsupported legacy backend enum values before backend pull dispatch.
		   - envelope request_id blank rejection addendum: active runtime routing now rejects blank envelope `request_id` values before authentication checks, backend dispatch, route refresh, or runtime store mutation.
		   - envelope version rejection addendum: active runtime routing now rejects unsupported envelope `version` values before authentication checks, backend dispatch, route refresh, or runtime store mutation.
		   - RuntimeDevServer envelope version/request_id decode rejection addendum: development relay frames with missing or mistyped envelope `version` or `request_id` values now return `invalid_payload` before authentication checks, backend dispatch, route refresh, or runtime store mutation while keeping the connection usable for follow-up pre-auth `runtime.health`.
		   - RuntimeDevServer envelope timestamp decode rejection addendum: development relay frames with missing, non-string, or malformed envelope `timestamp` values now return `invalid_payload` before authentication checks, backend dispatch, route refresh, or runtime store mutation while keeping the connection usable for follow-up pre-auth `runtime.health`.
		   - RuntimeDevServer envelope type/payload decode rejection addendum: development relay frames with missing or non-string envelope `type` values or missing or non-object `payload` values now return `invalid_payload` before authentication checks, backend dispatch, route refresh, or runtime store mutation while keeping the connection usable for follow-up pre-auth `runtime.health`.
		   - pre-auth invalid allowed type rejection addendum: active `hello` now rejects blank `device_id`, malformed or blank `device_name`, and malformed or duplicate `client_capabilities` before challenge creation; active `auth.response` now rejects blank or malformed `device_id`, `nonce`, and `signature` before authentication.
		   - protocol schema active request contract parity addendum: shared schema now mirrors minimal `hello`, active request nonblank identifier fields, nonblank `models.pull.model`, nonblank `chat.cancel` acknowledgement target ids, and the legacy `models.pull.backend = ollama` request enum enforced by runtime/schema gates.
		   - chat.cancel unknown metadata rejection addendum: active `chat.cancel` now rejects backend URL, route token, relay secret, workspace id, permission grant, source-control state, and other unknown payload metadata before backend cancel dispatch.
		   - chat.cancel blank target rejection addendum: active `chat.cancel` now rejects blank `target_request_id` values before backend cancel dispatch.
	   - chat session_id blank rejection addendum: active `chat.send`, `chat.title.request`, `chat.messages.list`, `chat.session.rename`, and `chat.session.archive`/`restore`/`delete` now reject blank `session_id` values before backend dispatch, title generation, chat history reads, or runtime chat-store mutation.
	   - chat.title.request unknown metadata rejection addendum: active `chat.title.request` now rejects response-only title, project id, workspace id, retrieval context, permission grant, backend URL, backend credentials, provider URL, route token, relay secret, requested route token, source path, source-control state, tool results, and other unknown payload metadata before backend title generation.
	   - chat.sessions.list unknown metadata rejection addendum: active `chat.sessions.list` now rejects backend URL, provider URL, route token, relay secret, requested route token, workspace id, permission grant, source path, source-control state, and other unknown payload metadata before runtime chat store dispatch.
	   - chat.sessions.list invalid allowed type rejection addendum: active `chat.sessions.list` now rejects string or fractional `limit`, string `include_archived`, non-string `query`, and non-string `embedding_model_id` before runtime chat store dispatch.
	   - chat.messages.list unknown metadata rejection addendum: active `chat.messages.list` now rejects backend URL, provider URL, route token, relay secret, requested route token, workspace id, permission grant, source path, source-control state, and other unknown payload metadata before runtime chat store dispatch.
	   - chat.messages.list invalid allowed type rejection addendum: active `chat.messages.list` now rejects string and fractional `limit` values before runtime chat store dispatch.
	   - chat.session rename unknown metadata rejection addendum: active `chat.session.rename` now rejects client-supplied `renamed_at`, backend URL, provider URL, route token, relay secret, requested route token, workspace id, permission grant, source path, source-control state, and other unknown payload metadata before runtime title store mutation.
	   - chat.session rename invalid allowed type rejection addendum: active `chat.session.rename` now rejects non-string or empty `title` values before runtime title store mutation.
	   - chat.session lifecycle unknown metadata rejection addendum: active `chat.session.archive`, `chat.session.restore`, and `chat.session.delete` now reject backend URL, provider URL, route token, relay secret, requested route token, workspace id, permission grant, source path, source-control state, and other unknown payload metadata before runtime chat store mutation.
	   - chat.session lifecycle invalid allowed type rejection addendum: active `chat.session.archive`, `chat.session.restore`, and `chat.session.delete` now reject non-string or empty `session_id` values before runtime chat store mutation.
	   - memory.list unknown metadata rejection addendum: active `memory.list` now rejects response-only `entries`, backend URL, provider URL, route token, relay secret, requested route token, workspace id, permission grant, source path, source-control state, and other unknown payload metadata before runtime memory store dispatch.
	   - memory.list invalid allowed type rejection addendum: active `memory.list` now rejects non-string `query` values before runtime memory store dispatch.
	   - memory.upsert unknown metadata rejection addendum: active `memory.upsert` now rejects response-only `entry`, runtime-derived `source`, backend URL, backend credentials, provider URL, route token, relay secret, requested route token, workspace id, permission grant, source path, source-control state, and other unknown payload metadata before runtime memory store mutation.
	   - memory.upsert blank allowed-field rejection addendum: active `memory.upsert` now rejects non-string, empty, or blank `id`, non-string or blank `content`, and non-boolean `enabled` values before runtime memory store mutation.
	   - memory.delete invalid allowed type rejection addendum: active `memory.delete` now rejects non-string, empty, and blank `id` values before runtime memory store mutation.
	   - memory.upsert invalid allowed type rejection addendum: active `memory.upsert` now rejects malformed allowed fields before runtime memory store mutation instead of relying on store-layer normalization.
		   - memory.delete unknown metadata rejection addendum: active `memory.delete` now rejects client-supplied `deleted_at`, backend URL, provider URL, route token, relay secret, requested route token, workspace id, permission grant, source path, source-control state, and other unknown payload metadata before runtime memory store mutation.
		   - memory.summary.drafts.list unknown metadata rejection addendum: active `memory.summary.drafts.list` now rejects response-only `drafts`, backend URL, provider URL, route token, relay secret, requested route token, workspace id, permission grant, source path, source-control state, and other unknown payload metadata before runtime chat or memory store dispatch.
		   - memory.summary.drafts.list invalid allowed type rejection addendum: active `memory.summary.drafts.list` now rejects string and fractional `limit` values before runtime chat or memory store dispatch.
			   - memory.summary draft decision unknown metadata rejection addendum: active `memory.summary.draft.approve` and `memory.summary.draft.dismiss` now reject response-only status, entry, and dismissed_at data plus backend URL, provider URL, route token, relay secret, requested route token, workspace id, permission grant, source path, source-control state, and other unknown payload metadata before runtime chat-store recomputation or memory-store mutation.
			   - memory.summary draft decision invalid allowed type rejection addendum: active `memory.summary.draft.approve` now rejects non-string or blank `content`, non-boolean `enabled`, non-string or blank `expected_session_id`, and string or fractional `expected_source_message_count`; active `memory.summary.draft.dismiss` now rejects non-string or blank `expected_session_id` and string or fractional `expected_source_message_count` before runtime chat-store recomputation or memory-store mutation.
			   - chat.send top-level payload metadata rejection addendum: active `chat.send.payload` now rejects project id, workspace id, retrieval context, permission grant, backend URL, and other unknown payload metadata before backend dispatch until project/workspace trusted-source semantics exist.
			   - chat.send invalid allowed type rejection addendum: active `chat.send` now rejects non-string `locale`, non-enum message `role`, non-enum attachment `type`, and non-string attachment `name`, `data_base64`, or `text` before backend dispatch.
			   - chat.title.request invalid allowed type rejection addendum: active `chat.title.request` now rejects non-string `locale` before backend title generation.
		   - chat.send message metadata rejection addendum: active `chat.send.messages[]` now rejects source path, workspace id, source-control status, backend URL, trusted-source, and other unknown message metadata before backend dispatch until project/workspace trusted-source semantics exist.
		   - attachment source metadata rejection addendum: active `chat.send` attachments now reject source path, workspace id, source-control status, backend URL, and other unknown metadata before backend dispatch until trusted-source semantics exist.
	   - relay probe/physical wrapper production proof-boundary addendum: Android relay reachability probe and physical external-relay wrapper summaries now keep production relay, production session-key exchange, and production end-to-end transport encryption proof false.
	   - RuntimeDevServer future route namespace rejection addendum: authenticated relay smoke now rejects `route.candidates.exchange`, `route.diagnostics.report`, `route.allocation.status`, and `route.failure.report` with `unknown_message_type` while `route.refresh` remains the only active `route.*` message.
	   - protocol reserved private-overlay namespace guard addendum: `p2p.`, `rendezvous.`, `bootstrap.`, `dht.`, `nat.`, `stun.`, and `turn.` active messages remain blocked by protocol schema hygiene.
	   - RuntimeDevServer reserved private-overlay namespace rejection addendum: authenticated relay smoke rejects `p2p.session.open`, `rendezvous.records.publish`, `bootstrap.records.lookup`, `dht.records.put`, `nat.candidates.gather`, `stun.binding.request`, and `turn.relay.allocate` with `unknown_message_type` before production P2P/rendezvous/bootstrap/NAT/STUN/TURN control paths exist.
	   - Android pairing deeplink am-start route-material redaction addendum: physical deeplink smoke now stores and prints sanitized `am start` output so long-lived QA logs keep only `aetherlink://pair?<redacted>` instead of raw pairing or relay route material.
   - Android pairing deeplink am-start sanitizer self-test proof-boundary addendum: the hidden no-device sanitizer self-test now emits `am_start_sanitizer_self_test_not_android_intent_or_phone_pairing_proof` so seeded `am start`-looking output is not mistaken for intent delivery or phone pairing proof.
   - Android pairing failure artifact redaction addendum: failed physical deeplink smoke activity/logcat artifacts and filtered stderr tails now redact pairing URI, runtime identity, relay route material, allocation-token, and compact alias values while preserving structured failure diagnostics.
   - Physical external-relay URL host input redaction addendum: wrapper `--relay-host` URL/path/query/user-info values now fail before child smoke execution while summary, log, stdout, and stderr keep only `<invalid-host>` labels instead of raw provider/backend/route-token/relay-secret input.
   - Physical external-relay probe-summary route-material redaction addendum: wrapper `probe_summaries` now defensively strip raw relay and route material from embedded child probe artifacts while preserving seeded redaction coverage and keeping self-test physical proof false.
   - Android pairing QR relay port canonicality addendum: Android QR parsing and rendered QR verification reject signed or zero-padded relay port strings before route material acceptance, matching the shared `portValue` contract.
   - Android pairing QR route expiration canonicality addendum: Android QR parsing and rendered QR verification reject signed or zero-padded relay/P2P route expiration strings before route material acceptance, matching the shared `epochMillisValue` contract.
   - macOS pairing QR relay-scope allowlist addendum: `PairingCoordinator` now emits only `remote`, `private_overlay`, `usb_reverse`, or direct-route `local_diagnostic` scopes before QR payload generation, and focused SwiftPM tests pin unsupported/case-mutated scope omission.
   - Physical external-relay probe-summary self-test proof-boundary addendum: seeded redaction self-tests now record `probe_summary_redaction_self_test=true` while keeping live Android probe proof, physical external-relay proof, physical external-relay success, and observed ADB serial evidence false or absent.
   - Physical external-relay runtime-log temporary route-material summary addendum: wrapper summaries now classify `runtime.log` as temporary pairing/route-material-bearing when it contains a parseable development pairing URI, without embedding raw pairing URI values in summary JSON.
   - Physical external-relay wrapper-log redaction summary addendum: wrapper summaries now classify durable wrapper `run.log` artifacts, verify redacted `aetherlink://pair?<redacted>` evidence, and flag missing or unredacted pairing/relay route material instead of implying wrapper-log safety.
   - No-ADB external-relay URL host input redaction addendum: no-ADB relay smoke rejects URL/path/query/user-info `--relay-host` input before artifact generation and the no-device gate verifies provider/backend/route-token/relay-secret markers stay out of rejection output.
   - No-ADB runtime-log temporary route-material summary addendum: no-ADB QR summary now marks `runtime.log` as temporary pairing/route-material-bearing only when the runtime log contains a parseable development pairing URI with nonce/code and complete relay route fields, and the no-device gate proves the unverified empty-log self-test keeps those runtime-log flags false.
   - No-ADB QR temporary pairing/route-material artifact summary addendum: no-ADB QR summary now marks pairing URI and QR PNG artifacts as temporary pairing and route-material-bearing manual-scan evidence only after route-bearing QR round-trip verification, and the no-device gate also proves stale or unverified artifacts keep those pairing/route-material flags false with a separate unverified-artifact caveat.
   - No-ADB print-uri terminal-output temporary route-material summary addendum: no-ADB QR summary now marks `--print-uri` terminal output as temporary pairing/route-material-bearing when the printed pairing URI contains parseable pairing and relay route material, while default emit-only runs keep terminal-output coverage false.
   - No-ADB relay-log redacted relay-id summary addendum: no-ADB QR summary now marks durable `relay.log` artifact coverage, verifies generated relay ids are shortened in relay logs instead of copied raw from the pairing URI, and keeps relay secret, nonce, route-token, allocation-token, and compact alias markers out of relay-log evidence.
   - macOS Dock capture dry-run summary addendum: `script/capture_macos_dock_icon.sh --dry-run --summary-json` writes no-side-effect helper-contract evidence while explicitly keeping macOS Dock screenshot proof false with `dry_run_not_macos_dock_screenshot_proof`.
   - Live/physical proof that remains separate: physical Android QR scan with the optical camera path, external public/VPN relay reachability, additional launcher/dock icon screenshots across device sizes, broader live provider-backed chat/cancel, chat-complete, and model-quality evaluation beyond the current local-development relay proofs, production relay allocation, production P2P/rendezvous traversal, and real different-network runtime connectivity.

## v0.1 Local Chat Link

- The client scans a runtime-host-displayed QR code and pairs with the AetherLink Runtime.
- Pairing binds device identities and keys; product connectivity must not depend on manually entering or permanently storing a fixed IP address.
- Fixed host/port values, mDNS/Bonjour local discovery, and raw local sockets are v0.1 development hints or local fast paths, not the target reconnect model and not sufficient for unrelated networks.
- Runtime host detects Ollama health.
- Runtime host lists Ollama models.
- Client selects a model and sends chat messages.
- Runtime host streams Ollama responses back to the client.
- Runtime host preserves Ollama reasoning/think chunks separately from final answer text.
- Client shows reasoning/think text in a muted, compact section that expands on demand.
- Client can reopen previous local chats.
- Client can manage user memory notes through the trusted runtime and include enabled runtime-owned notes as chat context.
- Runtime can compact oversized active `chat.send` history before backend dispatch by preserving recent user-visible messages verbatim and injecting a backend-only system summary of older active turns.
- Archive and delete are distinct local session actions: archived chats are retained but hidden from active memory/research/compaction inputs unless restored or explicitly selected.
- Client can cancel generation.
- Only trusted devices can control the runtime host.
- Client never connects directly to Ollama or LM Studio.

## Private Peer Connectivity Direction

The concrete phased architecture is tracked in [connection-overlay.md](connection-overlay.md).

AetherLink's 1:1 connection model is Bitcoin-like only in the narrow sense of peer identity and discovery without relying on a single fixed address. It is not a public untrusted peer network. Only QR-paired trusted devices may discover, authenticate, and communicate with each other.

The target reconnect model is paired peer identity plus QR-bootstrapped private overlay state, with local direct as an opportunistic fast path, remote P2P NAT traversal for different networks, and encrypted blind relay/TURN fallback. NAT traversal should use STUN-like address discovery, authenticated hole punching, short-lived candidate exchange, and session keys bound to the paired identities. Optional DHT/bootstrap-peer discovery may provide a Bitcoin-network-like feel for finding peers without a fixed IP, but only with privacy-preserving rendezvous records for already-paired devices. Relay/signaling infrastructure must remain unable to see AI protocol payloads, model lists, prompts, files, memory, backend credentials, backend URLs, or model commands. Clients still talk only to the trusted runtime boundary, never directly to Ollama, LM Studio, or future serving backends.

Current status: the code has trusted identities, endpoint hints, Bonjour/local discovery candidates, USB/dev local paths, route-candidate plumbing, an Android core P2P rendezvous route-preparation, QR-planning, trusted-runtime restore contract, explicitly enabled authenticated P2P route-material renewal through diagnostic `route.refresh`, matching macOS compact/canonical P2P QR generation for the shared opaque field family, and a temporary outbound TCP relay keyed by private route material. Strict allocated relay crypto v2 adds PSK-mixed ephemeral P-256 ECDH, transcript confirmation, paired-identity transport binding, direction-separated traffic secrets, 65,536-frame epochs, ordered replay rejection, and counter-exhaustion fail-close to that relay path. Diagnostic authenticated relay refresh accepts stable relay id/secret reuse only with a fresh nonce and advancing lease, keeps the current relay route and retries when stale refresh material is rejected inside an active lease, and the authenticated relay smoke checks both that sensitive protocol markers stay out of captured encrypted frame bodies and that refreshed lease material advances. The P2P work remains opaque route preparation rather than signaling, STUN, hole punching, or a real connector. The allocation path now issues opaque relay ids derived from route tokens. The allocation registry ignores non-advancing relay renewals, deduplicates persisted relay tickets on load, and uses a short default allocation TTL, persists relay leases without secrets, removes expired relay ids, and prunes expired persisted tickets on load. It still uses a development service that can observe bootstrap secret material, so production remote P2P NAT traversal, DHT/bootstrap rendezvous, hardened allocation and secret delivery, identity-first session setup, post-compromise recovery, and production end-to-end transport encryption are not complete.

## Current Development Relay

- The active development relay for QR pairing is the SwiftPM `AetherLinkRelay` executable in allocation-required mode.
- Tokenless development-relay binds are loopback-only (`127.0.0.1`, `::1`, or `localhost`); wildcard and non-loopback binds require an allocation token before the relay starts.
- `script/aetherlink_relay.py` is legacy-only, does not implement allocation leases, and must not be used for current QR pairing or different-network validation.
- Runtime hosts can register outbound with `AETHERLINK_RELAY_HOST`, `AETHERLINK_RELAY_PORT`, and optional `AETHERLINK_RELAY_ID`, or request route-token-based allocation through `AETHERLINK_BOOTSTRAP_RELAY_HOST`.
- Pairing QR payloads must carry `relay_host`, `relay_port`, `relay_id`, `relay_secret`, `relay_expires_at`, and `relay_nonce` for the current QR-provisioned relay path so the client can prepare a fresh relay route after trust is established.
- The relay matches one runtime and one client in a private room and pipes bytes; it does not call Ollama, LM Studio, or any model backend. QR relay routes require `relay_secret`, so it forwards encrypted AetherLink frame bodies.
- This is a development bridge only. Crypto v2 hardens its endpoint session, but production still requires reviewed identity-first key exchange, relay-independent secret delivery, key-bound route tokens, hardened allocation, recovery semantics, and a real bootstrap/NAT traversal strategy before sensitive remote use.

## Current LM Studio Backend Support

- LM Studio is supported as a runtime-mediated local backend.
- Clients see LM Studio models through runtime health, `models.list`, and provider-prefixed `chat.send` model ids.
- LM Studio support is not MCP, memory, skills, web search, or direct client backend access.

## Future Project Workspaces

This is not v0.1 implementation scope. The product direction is a project/workspace feature similar to ChatGPT Projects, while preserving AetherLink's runtime boundary:

- Project-scoped chats, files, instructions, memories, indexes, and model/backend preferences.
- Trusted-source controls that let the user decide which files, folders, chats, notes, or external results can be used as project context.
- Project-level search and deep-research-like brief generation over indexed, user-approved material.
- Project indexes, retrieval, summarization, and research run through the runtime host boundary, not directly from client apps.
- Mobile clients act as project controllers and approval/status surfaces; they do not call Ollama, LM Studio, future serving backends, file indexers, or tools directly.
- Project files and indexes are sensitive data and must pass through runtime permissions, source selection, audit logs, and archive/delete rules.

## Future Scheduling And Automation

This is not v0.1 implementation scope. Scheduling and automation should be runtime-host mediated:

- User-created scheduled tasks, reminders, monitors, recurring automations, and runtime-triggered jobs.
- Permission prompts before an automation can use sensitive project files, network access, tools, terminal execution, MCP, web search, or model backends.
- Audit logs for creation, edits, approvals, execution attempts, results, failures, and cancellations.
- Client apps provide approval, pause/resume, status, and result-review surfaces; they do not execute scheduled jobs or call backends/tools directly.
- Scheduled jobs are sensitive runtime actions because they can run later without the user actively watching the UI.

## v0.2 Session and Memory Polish

- Migrate the current runtime-owned JSONL chat event authority to SQLite/FTS while preserving authenticated `chat.sessions.list` / `chat.messages.list` reads and client-side message-body redaction.
- Implemented first slice: authenticated `chat.sessions.list` can filter runtime-owned session summaries by optional `query` over title, model id, metadata, processing state, and sanitized transcript text while preserving owner/archive/delete boundaries.
- Implemented first client slice: Android Settings > Chat history keeps local instant filtering, and the explicit refresh action forwards the current search text as runtime `query` for server-owned search.
- Implemented ranking/snippet seam: query responses can carry deterministic `search.rank`, bounded `search.snippet`, and `search.matched_fields`; Android can render snippets while redacting runtime-owned snippet text from device storage.
- Implemented SQLite/FTS parity, backfill, and default-store rollout slices: `SQLiteRuntimeChatEventStore` can persist runtime chat events, maintain a session FTS index, backfill existing JSONL runtime chat events, preserve authenticated sessions/messages/lifecycle semantics, return deterministic search metadata through the existing store protocol, and serve as the `LocalRuntimeMessageRouter` / `CompanionAppModel` production default via `RuntimeChatEventStoreDefaults.productionStore()`.
- Continue session search polish with SQLite/FTS rollout hardening, richer ranking, snippets, retention policy, and richer client sync/search UI; Android Settings search-result rows now render runtime-provided rank/snippet/matched-field context plus filtered active/archived result counts that stay stable while row actions run, search-only authoritative matches outside the bounded full cache can now be promoted in memory and opened without persisting search metadata, JSONL and SQLite lexical ties use session id as a stable final key, the RuntimeDevServer authenticated relay smoke validates `chat.sessions.list` query search metadata, stored assistant reasoning can be matched and labeled separately from visible answer text across JSONL router, SQLite/FTS, and Android Settings paths, and production retention now owns conservative 90-day/100-session all-owner batches.
- Client session list rename, archive, restore, delete, local/remote search, search-only open, transcript synchronization, explicit authenticated pagination/cursors, and bounded runtime-authoritative bulk archive/delete are implemented. Further polish concerns product UX and physical-device validation rather than a missing host/client protocol contract.
- Archive polish: archived chats remain retained but excluded from memory, reflection, research, and compaction inputs unless the user restores them or explicitly selects them as sources. Implemented runtime send gate: `chat.send` into an existing archived session now returns `chat_session_must_be_restored_before_send` before backend dispatch or chat-event mutation.
- Preserve reasoning/think text separately from final assistant answer text in session storage; no-device regressions now pin reasoning-only session search metadata and transcript reads that keep assistant answer `content` separate from assistant `reasoning`.
- Context-window-aware session compaction: the adaptive budget, bounded LLM summary, cancellation ownership, request-bound source-pointer, append-only terminal-resolution, durable generated-summary cache, strict-prefix incremental summary-evolution, post-dispatch provider-usage records, and bounded host-local calibration acceptance-report slices are implemented, while broader compaction work remains in progress. Known positive model windows use byte- and decoded-image-aware `conservative_utf8_bytes_vision_framing_v2`, reserve `max(512, min(4096, window / 8))`, enforce a hard estimator input budget, preserve runtime system context plus the newest user and later turns, and compact only a contiguous oldest whole-turn prefix. New `adaptive_backend_only_summary_v3` metadata binds request identity, that storage-safe prefix, and pointer ranges with a canonical SHA-256 fingerprint; terminal resolution separates the planned upper bound from effective dispatched accounting or undispatched cancellation. The owner-only sidecar cache separately binds bounded source, full compacted-prefix lineage, owner/session, resolved provider model, and summary policy. Exact hits require full lineage; verified strict extensions evolve only the prior generated summary plus newly compacted delta, both as untrusted input, and commit only after primary success. The cache remains outside `chat.messages.list` and SQLite FTS. The host report retains only bounded counts keyed by exact provider/model/wire/estimator and never changes the estimator. V1/v2, legacy v3 summary policy, and resolution-free records remain readable. Inputs that cannot fit fail before backend dispatch with nonretryable `chat_context_window_exceeded`, with localized Android guidance. Missing context metadata keeps the legacy 24,000-character heuristic. Exact provider-tokenizer parity, live-provider acceptance evidence, statistically reviewed thresholds, and automatic policy calibration remain future work.
- Longer-inactivity memory summarization: no-device eligibility, deterministic drafts, authenticated listing, explicit runtime-model generation, Android review UI, approval/injection, approved-entry source metadata, durable dismiss, and runtime memory-list lexical search slices are implemented. `memory.summary.draft.generate` requires exact owner-scoped stale guards plus an installed runtime-host local chat model, sends only bounded visible user/final-assistant excerpts, rejects malformed or oversized strict-JSON output, revalidates the exact source after inference, and stores an owner-scoped runtime JSONL cache keyed by deterministic draft id. Repeated generation and reopen use the cache; generation never auto-approves memory, and approval without client content stores the reviewed generated text with `summary_method=llm_summary_v1`. Android Settings > Memory exposes a localized Generate Summary action only for deterministic previews, shows generated summaries as review-required, blocks concurrent approve/dismiss actions, and keeps generated draft state out of `RuntimeLocalStore`. Existing deterministic approval, dismiss, lexical `memory.list`, source review, and no-device proof boundaries remain intact. This remains separate from short model-unload inactivity. Richer inactivity/review policy, automatic unreviewed extraction, reflection, embeddings, and project-scoped memory remain future work.

## v0.2 Runtime Resource Policy

- Implemented first slice: when switching models, the aggregate runtime host asks the previous inactive provider model to unload before using the newly selected model.
- Implemented first slice: if there is no chat activity for the runtime host's idle delay, the aggregate runtime host asks the active provider model to unload. The default remains 10 minutes.
- Ollama unload uses the runtime-host-side `/api/chat` path with empty messages and `keep_alive = 0`.
- LM Studio unload uses the runtime-host-side `/api/v1/models/unload` path for loaded instance ids.
- Keep model residency policy in the runtime host, not client UI code.
- Runtime status UI, logging, provider-specific failure reporting, the first runtime-host-owned manual unload control, menu-bar model-residency controls, reason-aware manual unload Activity/Status summaries, RuntimeDevServer unload-failure health redaction smoke coverage, and a persisted host-local 5/10/30 minute idle-unload selector are implemented. Policy changes preserve elapsed idle time, reschedule the current timer, and invalidate cancelled timer generations.
- Runtime-side DocumentIngestion resource policy now bounds attachment input files, helper process output, archive entry output, and normalized extracted text before backend dispatch.
- Continue polishing this policy with live-provider validation and richer controls beyond the bounded 5/10/30 minute presets.

## v0.3 Embeddings And Research Notes

- Optional embedding model registration on the runtime host.
- Embedding models are listed and selected separately from general text-generation/chat models.
- Semantic search over prior chats and user-approved notes is implemented behind runtime-host-local embedding selection. Prior-chat candidate vectors persist only with a canonical strong artifact revision and owner/session/model/document isolation; approved-memory candidate vectors use an owner-only revision-bound SQLite sidecar. Query vectors remain ephemeral, providers without a strong revision stay on demand, and lexical search remains available when no embedding hint is supplied.
- Exact, review-only memory duplicate suggestions are implemented with deterministic byte-identical grouping over at most 200 owner-scoped entries and transient Android review state. Separate review-only semantic pairs and complete-link clusters use an explicit integer threshold and selected runtime-local embedding model without changing exact v1. A SHA-256-pinned synthetic calibration foundation and one separate loopback Ollama report are implemented without changing the 9,000 default; representative live-model acceptance criteria and automatic merge policy remain future work.
- Retrieval, ranking, and approved knowledge indexing use the selected embedding model. Android carries `embedding_model_id` only with nonblank runtime-owned chat-history, approved-memory, document queries, or the explicit review-only semantic duplicate scan and keeps queried responses transient; macOS resolves the provider-qualified installed local embedding model, calls Ollama `/api/embed` or LM Studio `/v1/embeddings`, and applies bounded owner-scoped cosine ranking without response echo, vector disclosure, silent lexical fallback, or chat-model override behavior. RuntimeDevServer authenticated smoke proves repeated-query candidate cache reuse. Approved memory and revision-bound document semantic indexes are implemented under the source-approval, citation, trusted-source-review, permission, revision, and audit contracts recorded above.
- Implemented first bounded deep-research-like brief slice: `research.brief.create` accepts one through eight explicitly approved current-device trusted-source excerpts, uses the selected installed local chat model, and streams an evidence-grounded brief through existing chat events. It adds no web search, external network access, automatic project retrieval, whole-document authority, or source-free factual guarantee.
- Implemented runtime-owned chat-backed research notebook sessions: owner-scoped SQLite metadata keeps only notebook/session/title/model, ordered private grant IDs, lifecycle, and timestamps; Android lists safe summaries in the existing drawer and opens the backing chat. Follow-ups reuse the pinned grants, chat cancellation, safe source attributions, historical source review, and chat archive/restore/delete. Rich project notebooks, automatic source discovery, external research, and cross-source claim verification remain future work.
- Embedding-powered recall remains runtime-mediated; clients stay controller UIs.

## v0.4 Backend Selection Polish

- Implemented Android chat-model selector capability display: runtime-provided provider/status metadata is joined by a localized known projection of chat, vision, and exact context-window size, with separate visual and spoken punctuation, no raw unknown capability exposure, and compact five-language no-device coverage.
- Implemented macOS Status model-row capability display: existing kind/provider/source/running/size metadata now adds only allowlisted Vision aliases and exact positive context-window size, with localized VoiceOver projection, unknown capability suppression, and compact five-language appearance coverage.
- Implemented Android research-brief model selection parity: the dialog now uses the same runtime-mediated provider/status/capability projection, filters and revalidates installed runtime-host-local chat authority, preserves an eligible dialog-local choice across catalog refresh, and exposes localized picker purpose and lockout semantics.
- Continue backend-selection polish on remaining client/runtime surfaces without exposing backend URLs or allowing direct client-to-provider access.
- Clients still talk only to AetherLink Runtime.

## v0.5 Permission Broker and Skills

- Runtime-side permission model.
- Prompt-only skill registry.
- Approval-required actions.
- Internal Python tool execution through the runtime host for deterministic tasks such as calculations.
- The `python.` protocol namespace remains reserved until runtime-owned sandboxing, permission prompts, resource limits, and audit semantics are designed; protocol schema hygiene blocks active `python.*` messages and RuntimeDevServer authenticated relay smoke rejects `python.run` and `python.exec` for now.
- The `file.`, `terminal.`, `network.`, and `backend.` protocol namespaces remain reserved until runtime-owned file/workspace permissions, terminal/process controls, network access policy, backend/provider configuration policy, mobile approvals, resource limits, redaction, and audit semantics are designed; protocol schema hygiene blocks active messages under those prefixes for now.
- Runtime-side permissions and audit logs for Python, file, terminal, skills, MCP, and web-search actions.
- Advanced memory and skill execution remain roadmap items, not v0.1 implementation scope.

## v0.6 Web Search

- Runtime-side web search provider abstraction.
- SearXNG/custom endpoint first.
- Search result cache and citation-ready metadata.
- Web search remains a roadmap item, not v0.1 implementation scope.

## v0.7 MCP

- Runtime-side MCP server registry and client manager.
- Client tool approval and result views.
- MCP remains a roadmap item, not v0.1 implementation scope.

## v0.8 Workspace/RAG

- Project/workspace registration with scoped instructions, files, memory, indexes, and model/backend preferences.
- The `projects.` protocol namespace remains reserved until the project/workspace product, privacy, and permission model is ready; the protocol schema guard blocks active `projects.*` messages for now.
- File indexer and document chunking for user-approved project sources.
- Search over indexed files, prior project chats, and trusted project memory.
- Trusted-source controls for selecting which folders, files, chats, notes, or external results can feed retrieval and research.
- Eventual project-level search and research reports with source snippets and citations.
- Existing image/file attachment inputs remain runtime-mediated; workspace/RAG adds project-scoped file approval, chunking, indexing, and retrieval on top of that runtime boundary.
- Clients never send files or images directly to Ollama, LM Studio, future serving backends, or indexing services.

## v0.9 Scheduling And Automations

- Runtime-host scheduler for user-created scheduled tasks, reminders, monitors, recurring automations, and runtime-triggered jobs.
- The `automation.` protocol namespace remains reserved until scheduler permissions, audit logs, and approval flows are designed; the protocol schema guard blocks active `automation.*` messages for now.
- Runtime permission broker prompts for actions that touch project files, tools, terminal, MCP, web search, network, or model backends.
- Audit log entries for automation definitions, approvals, runs, failures, cancellations, and permission changes.
- Mobile approval/status surfaces for reviewing, pausing, resuming, cancelling, and approving automation runs.
- Client apps remain controllers; scheduled jobs execute only through the trusted runtime.

## Post-V1 Platform Expansion (Former v1.0 Placeholder)

This historical heading is superseded by the canonical V1 delivery roadmap at
the top of this file. Windows, DGX OS, and iOS are not gates for the first
production macOS Runtime plus Android Controller release. Their exact version
numbers should be assigned only after V1 GA.

- Runtime targets expand from the current runtime host to Windows and DGX OS-class workstation/server support.
- Client/controller targets expand from the current mobile client to iOS.
- Keep the same trust boundary: clients control sessions; runtime targets mediate all model access.
- Keep the same private P2P identity model across platforms so paired devices can reconnect across local and remote networks without exposing backend URLs or relying on OS-specific fixed endpoints or local-only discovery.

## Post-V1 Serving Backend Expansion

- Add more AI serving backend adapters beyond Ollama and LM Studio.
- Preserve a common capability model for health, installed/running models, streaming chat, cancellation, embeddings, context windows, and structured errors.
- Avoid exposing backend-specific local URLs to mobile clients.
