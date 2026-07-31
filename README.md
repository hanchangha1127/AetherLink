# AetherLink

AetherLink is a local-first client-to-runtime AI companion. A paired runtime host owns the AI runtime and backend adapters; the AetherLink device app is the controller for chat, model selection, and generation control. The current implementation has mobile-client and desktop-runtime targets, but the product architecture is intentionally OS-neutral.

For continuation in a new Codex session, read [`docs/handoff.md`](docs/handoff.md)
first. The [canonical V1 roadmap](docs/roadmap.md#canonical-v1-delivery-roadmap)
is active.

The current non-security macOS Runtime lifecycle reports
`starting(port) -> listening(port) | failed(message)` only after both local
listener readiness and Bonjour publication succeed. Network.framework
listener readiness starts Bonjour, but the app stays in its localized,
non-interactive starting state until `NetService` confirms publication.
Publication failure, a five-second timeout, or an unexpected late stop releases
local ownership and preserves same-port Retry. Generation fences make callbacks
from replaced services inert. This is local no-device lifecycle behavior, not
external-network discovery, device, signing, deployment, security, or release
evidence.

<!-- aetherlink-current-build23-to-24-isolated-upgrade-v2:start -->
The current non-security G6 lifecycle evidence exercises the preserved Build 23
macOS archive upgrading to Build 24 under one temporary HOME. Each archive's
ZIP, manifest, and checksum sidecar are copied once into a private snapshot;
archive readback, extraction, and exercise use those same bytes, which are
rehashed unchanged after the exercise. Build 23 migrates one fixed Runtime-chat
canary, Build 24 reads it back twice in distinct processes, and all three SQLite
files plus retained state bytes and modes remain unchanged.

The repeatability runner recorded two complete runs with the same 6,469-byte
canonical result at
`dist/lifecycle/macos-packaged-app-build-23-to-24-isolated-upgrade-v2.json`,
SHA-256
`ddec23cf048fa77c559ca7ee4f45354feb558f830ca4b01eccffa5b7786ea09c`.
Its 898-byte receipt is
`dist/lifecycle/macos-packaged-app-build-23-to-24-isolated-upgrade-repeatability-v1.json`,
SHA-256
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
The v2 runner and nine-test module SHA-256 values are
`515de26546ba97c6879cad1fdf62cda6f3dcbf24a668804955f95e1755d1f374`
and
`6aa2e9e2354aa36f97ff096787ac05115c95114fcf95869463b47f39dea5006c`.
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
`515de26546ba97c6879cad1fdf62cda6f3dcbf24a668804955f95e1755d1f374`,
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
`515de26546ba97c6879cad1fdf62cda6f3dcbf24a668804955f95e1755d1f374`,
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
`515de26546ba97c6879cad1fdf62cda6f3dcbf24a668804955f95e1755d1f374`,
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

This is a personal, single-owner project. Owner identity authentication is not
required for this personal project. Direct user instruction is sufficient for
repository reads, edits, builds, tests, and G1a no-network implementation. SSH
or GPG proof of control, fourteen role-scoped approval receipts, an owner TSA,
and an external owner-governance ledger are not current prerequisites. The user
normally handles staging, commits, and pushes unless they explicitly request
otherwise.

The post-Build 24 current source also passes an isolated offline strict-lock
local Release qualification. Clean Android `assembleRelease`, `bundleRelease`,
and `lintRelease` complete with zero errors and three warnings; the
9,575,138-byte unsigned APK has SHA-256
`18cd152348cae25b0409be0449371792a33292d315cfb52731fdac8c3d290273`,
and the 10,684,069-byte AAB has SHA-256
`dda35e3d86aa78bf477926417d6c4c0083b3e86d94a552bd5484f9e381416665`.
The source snapshot stayed
`512084a6b4dd213364df88d5a3a2d2465f6db519847faa36c5d87b33a2ac0551`
through the Android and macOS package builds. An isolated temporary archive
then passed independent 29-member readback at 167,566,669 bytes and SHA-256
`57ba1747dbdb6cdf9524fcdf1e2f8e7c3ca11bdfb6cd63558d40df3610ed14f7`.
This transient dirty-content candidate retains `1.0.0+24` metadata solely for
current-source qualification. It is not the immutable Build 24 archive, a
ledger append, a retained or publishable Build 25, distribution signing,
installation, device evidence, or production release.

The current Android QR scanner owns camera-permission request state above the
conditional scanner screen. A checked app-private transaction records
`LaunchPending` before the system launcher is called and finalizes `Recorded`
after acceptance. Storage failure suppresses launch; launcher failure and
interrupted completion become the explicit, manually retryable
`RetryRequired` state instead of automatic re-request or false Settings
recovery. The implementation also rechecks the OS grant on app resume. The
scanner reducer, request-transaction, and Compose suite passes 13/13. A
controller-host Robolectric matrix passes 4/4 on API 26, 30, 33, and 36 while
driving a denied Activity Result into rationale, an explicit retry into a
granted result, and a later revoked grant through `ON_RESUME` into Settings
recovery. A second Robolectric class launches the manifest production
`MainActivity` and runs three lifecycle paths per API for 12/12 results: the
existing `ActivityScenario.recreate()` case restores
`Recorded` into Settings recovery, a saved-state-free same-JVM cold Activity
launch reconstructs the same durable state, and a cold launch from a persisted
`LaunchPending` interruption exposes a manually retryable action. None issues
a duplicate CAMERA request. The exact Android product selector therefore
passes 36/36. This is post-Build 24
current-source/JVM/Compose evidence; its cold launches remain in one JVM and do
not execute Android OS process death, SDK-specific OS permission or rationale
policy, the physical permission dialog, camera, optical QR, TalkBack, or
release installation.

The versioned [G0 decision](docs/v1/g0/decision-v1.md),
[G0 assurance packet](docs/v1/g0/assurance-v1.md), owner-trust profiles, and
related checkers are preserved as historical enterprise-assurance records. Their
embedded `blocked_before_g1a` and owner-authentication state does not govern or
block current personal-project work. Product security is unchanged: QR pairing,
paired-device authentication, endpoint session encryption, replay and downgrade
protection, pair-epoch recovery, revocation, and route-capability validation
remain required. Socket or external-network work, production signing, store
upload, and deployment remain separate technical scopes; they require current
user direction and applicable technical safeguards, not proof of repository
ownership.

G1a-A now includes one socket-free `ALS1` canonical contract shared by Swift
and Kotlin for six route authorizations and a 21-field endpoint secure-session
transcript. Shared vectors pin exact bytes and digests. This foundation is not
yet an active wire message, derived session key, encrypted record path, or
network connector.

G1a-B adds byte-identical Swift/Kotlin `ALS1` authority-state and local-snapshot
contracts, monotonic verified transitions, a 20-entry lifetime transition
history, bounded replay tombstones, and durable admission. Epoch advancement is
denied unless a signed fresh-pair proof verifies. Android persists and
projects the canonical state into a production-session-required connection
target; because the verified exact-bound coordinator is not connected to the
app or a transport yet, it rejects every legacy-only route before connector
invocation. macOS reloads the locked atomic
trusted-device store before active or restored pair transport start and rejects
missing, ambiguous, corrupt, or production-state-bearing legacy starts. The
older pre-connector test seams remain internal and dormant; no non-test
production session exists yet.
Key derivation, encrypted records, sockets, and network execution remain later
work.

G1a-C now adds root-pinned service keysets; signed pair-status, fresh-pair,
route-capability, candidate-capability, endpoint-proof, and post-commit receipt
verification; and exact unsigned object-25 evidence/object-26 authorization
projection in both Swift and Kotlin. The four candidate operations must use one
canonical keyset and one adjacent durable ledger chain, and the candidate
session transcript binds the exact SHA-256 digest of object 26 rather than the
generic object-4 authorization. macOS atomically persists the pair snapshot,
endpoint ledger, and chained marker and rereads their exact bytes under one
exclusive lock before issuing a live durability token. Generic P2P admission is
closed, and Android verified wrappers can only be minted by the verifier. Both
platform stores now cache one exact-bound no-network coordinator. It accepts
only the verifier-minted binding plus an APPLIED durable compound token,
strictly revalidates the current last entry and marker at admit, before start,
and after start, and fences replay, cancellation, revocation, authority advance,
expiry, and late completion with the store-owned clock. Explicit operation-
scoped callback context prevents detached start/abort reentry from waiting on
its own cleanup. A fence during an in-flight start may invoke the generation-
scoped idempotent abort immediately and again after start returns so a late-
published resource is removed; an active fence invokes it once. Cleanup retains
the pair reservation until it finishes, and Android additionally quarantines a
failed cleanup for explicit retry. Android uses cancellation-safe handle/lease
handoff ownership; Swift preserves cooperative cancellation and the same late-
publication fence. Historical readback and `AlreadyCommitted` results cannot
authorize this path. A bounded optional caller bridge can now reach the
coordinator, but the normal app's real upstream production inputs remain
unwired and this path creates no socket. This remains
`synthetic_contract_readiness_only` with
`productionDurabilityClaim=false`. Detecting rollback to an older internally
valid whole-store image still requires an external monotonic head.

G1a-D adds the socket-free production secure-session cryptographic core on both
platforms. A verifier-minted exact object-7/object-26 binding is the only KDF
input; one-use P-256 ECDH, HKDF-SHA-256, role-separated object-29 confirmation,
and ordered object-30 AES-256-GCM records share one pinned fixture and an
independent Python oracle. The state machines enforce monotonic time, exact
sequence and epoch transitions, replay rejection, key-update reservation,
bounded epoch/session use, terminal key wiping, and authentication-failure
counter stability. This core is not app- or transport-wired and opens no socket,
so it proves deterministic no-device interoperability rather than an active
production session, network route, physical device, deployment, or release.

That core is now coupled to the exact-bound authority lease on both platforms
through a store-owned, process-local publication gate. Start, confirmation,
activation, seal, and open hold a read permit across pre/post lease and live-
resource fences. A durable authority writer blocks new readers, drains current
publications, commits, then fences the coordinator and wipes the old crypto
state before reopening publication. Pure precommit rejection and macOS
pre-rename failure preserve the old session. Once an Android DataStore edit is
enqueued, cancellation or ambiguous persistence failure instead fences and
wipes the old authority; macOS post-rename directory-sync uncertainty does the
same. Cancellation and terminal crypto failure also invalidate the session and
close its lease. When a Swift post-fence rejects a produced confirmation, seal,
or open result, its owner-backed result storage is explicitly zeroized before
the read permit is released; small-ciphertext plus confirmation/seal/open
retained-owner and result-copy regressions cover this backing storage behavior.
An independent `Data` snapshot already
extracted by a caller is a separate copy and is not retroactively zeroized. This
guarantee applies only to one single-process store/coordinator graph. Bounded
no-network app/service caller bridges now reach the implemented transport seam,
which keeps encrypted publication inside the authority-bound channel. They do
not by themselves authorize or prove a real production route.

The dormant G1a-D transport composition seam is now concrete on both platforms.
Android `core:transport` gives a composer only a manager-owned one-use raw-route
lease, never a raw-channel alias or caller-provided scope. The lease validates
the exact authority capability/session and creates
`ProductionRuntimeSecureChannelAdapter` with a manager-owned execution scope;
construction failure cancels that owned scope, and the adapter is registered
before handshake suspension. Under `stateLock`, `UNDISPATCHED` acquisition
linearizes the transition with physical connector entry: cleanup that wins
first prevents connector invocation, while an entered connector that has not
returned a handle still depends on connector timeout/interruption and closes
any late handle when it returns. Detached composition has a saturating raw-route
timeout plus a fixed 15-second handshake budget. The adapter's internal
deadline is separate from the manager timeout, whose `IOException` is
classified as `ProductionSessionSecurityRejected`. The adapter's internal
deadline uses a single `PENDING` to `COMPLETED`/`TIMED_OUT` CAS and an
`UNDISPATCHED` watchdog. When timeout wins, its `IOException` dominates and
suppresses the losing error/cancellation; when completion wins, the exact
external or composer `CancellationException` is preserved. Canonical
`resume(value, onCancellation)` handoff closes only undelivered values:
pre-delivery cancellation closes once without retry, while a successfully
transferred channel survives later acquisition `Job` cancellation. There is no
permanent caller-`Job` binding or `InternalCoroutinesApi`. Immediately before
the one-use receipt commit, the manager rechecks the exact P2P session,
object-7/object-26 binding, route kind, manager-owned connection generation,
and route expiry, and rejects admission-to-commit wall-clock rollback. Failure
cleanup runs in `NonCancellable`. Even when raw ignores close until it returns,
the managed raw wrapper checks open before and after send, fails closed after
close, and the test observes actual late body-byte zeroization. Production relay
remains fail closed because no verifier-derived
exact relay route binding exists. Focused Android evidence is 79/79 (49/49
manager plus 30/30 adapter). The root independently reran full
`core:transport --tests '*'`: 10 suites pass 163/163 with zero failures, errors,
or skips; app `compileDebugKotlin` plus `compileDebugUnitTestKotlin` also
succeed. An independent iterative audit found and fixed six P3 availability/
lifetime races in total; a final fresh re-audit reports no P0-P3 finding. The
current root-independent full Swift rerun passes 2,003 tests with two declared
skips and zero failures in 313.440 seconds. Those focused/full-module reruns
alone were not a completed full no-device gate run; the current full no-device
gate exits zero. On
macOS the manager owns the exact one-use attachment, generation cleanup,
cancellation/late-result close, raw-handler admission, and terminal mailbox
drain before removal or replacement;
terminal teardown synchronously invalidates an available/claimed capability
before replacement, with asynchronous abandon/close outside registry locks.
There is no plaintext fallback. Focused macOS evidence is 39/39 (17/17
composition plus 22/22 secure-channel) and 34/34 (6/6 production-pair-
coordinator plus 28/28 manager); the release build passes. The audit-found
cancellation/replacement P2 is fixed with a deterministic delayed-abandon
regression; final independent re-audit reports no P0-P3 finding.
The bounded no-network caller bridge is now concrete on both platforms. The
Android ViewModel's optional dependency-injection path owns one renewable
`AndroidProductionRuntimeActivationSlot` shared by route preparation and start-
material claim. The slot holds at most one verifier-derived, one-use
`AndroidProductionRuntimeActivationPlan` per attempt, requires the exact same
`PairingStore` provider, compares the manager-selected exact route object and
prepared-session reference before claim, and hands composition only the
manager-owned raw-route lease. After claim, the slot retains a generation-bound
claimed entry until PairingStore transfer starts. If close or replacement wins,
the slot discards the key; if transfer wins, ownership moves exactly once to
the transfer object. Cancellation and duplicate or concurrent completion fail
closed, and the transfer callback runs at most once. Expiry, slot close, and
ViewModel clear also discard still-pending key material, while a fresh plan can
serve a later reconnect attempt. macOS exposes
`MacRuntimeProductionAcceptedSessionService`, fixes one exact
`TrustedDeviceStore` for its lifetime, validates a verifier-derived exact
accepted-route descriptor, transfers the endpoint through a one-shot claim, and
attaches it through the manager. A service-owned pre-attachment generation
remains registered while authority creation is suspended. Targeted `stop` and
`stopAll` invalidate it before attachment; `stopAll` also rotates a service
epoch, so a late authority return is abandoned without disturbing a fresh same-
ID generation. The service and store handoff close untransferred keys on every
failure path. Focused Android evidence passes 16/16 composer plus 1/1 ViewModel-
clear tests; the full app suite passes 1,174, and complete core protocol,
pairing, and transport suites pass 232/232, 200/200, and 163/163. Focused macOS
evidence passes 9/9 service tests and 54/54 manager + service + composition
tests (28 + 9 + 17); the release build succeeds.

G1b-A now connects the normal Android dependency graph to an app-scoped
`AndroidProductionRuntimeActivationController` that shares the exact
`PairingStore` and trusted clock with the ViewModel graph. The controller is
deliberately empty in production today: it publishes no route until a future
upstream verifier and P2P stack hand it one verified activation attempt plus an
already-connected one-use endpoint. Injected real-fixture tests exercise both
`RuntimeConnectionManager` and the full ViewModel connection path through the
authority-bound secure channel, reject every legacy fallback, complete the
handshake, and exchange an application record without opening an OS socket.
Publication generations are assigned before durable admission, so a delayed
older admission cannot replace a newer attempt. Close, cancellation, or
supersession reclaims the attempt-owned key and endpoint, including while
admission is suspended, and all displaced publication cleanup runs outside
controller locks. The 12/12 focused controller tests pass, and an independent
final audit reports no P0-P3 finding.

macOS G1b-A also exposes a concrete accepted-raw primitive through
`LocalPeerServer.startAcceptedRaw`. Its listener policy is fixed to IPv4
loopback `127.0.0.1`; one bounded authorization is consumed by one accepted
session, receive delivery starts only after handler installation, and malformed,
expired, stopped, or unclaimed sessions fail closed. The focused tests use
injected connection I/O and do not start the listener or execute a socket.
`CompanionAppModel` does not call this path yet.

This is still no live socket, network, physical-device, or production-release
evidence. The upstream verifier/candidate/secret producer and actual P2P
endpoint stack remain absent, the macOS accepted-raw primitive remains
`CompanionAppModel`-unwired, and actual socket close interruption remains
unproven. The eventual production send path must keep `seal + channel.send`
inside the same read-permit closure.

The historical G2 official-source preflight selected no networking library.
Unmodified Pion ICE v4.3.0 at exact commit
`1e8716372f2bb52e45bf2a7172e4fb1004251c46` is
`rejected_at_official_source_preflight_as_is` for non-uniform destination-policy
enforcement, remote ICE password logging, unbounded callback queues, and
shutdown that can wait indefinitely on a blocked callback. At that checkpoint,
no Pion source was retained, compiled, loaded, or executed, and no socket or
network rung was opened. This technical result requires no repository-owner,
GitHub, SSH, or GPG
authentication; product pairing and endpoint secure-session requirements remain
separate and unchanged.

The follow-up [G2 restricted-fork rung-one portfolio](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/hardening.md)
and its exact [machine profile](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/restricted-fork-profile.md)
compare unmodified upstream, a wrapper-only gateway, and a minimal
AetherLink-maintained fork. At the recorded `at_that_checkpoint`, only the
restricted-fork shape could proceed to preparation of a separate rung-two
official-source identity and acquisition decision; Pion and every networking
library remained unselected. Its schema 1.1
design requires separate egress capability and ingress admission boundaries,
authenticated TURN TLS service identity, exact AetherLink endpoint-confirmed
pre-auth promotion, bounded session/process resources with a sticky terminal
latch, secret-free diagnostics, and a 2,500 ms close deadline. Those controls
are not implemented or runtime-verified. The future compile-only matrix remains
Android `arm64-v8a` and macOS `arm64`, followed by later SBOM, license, patch,
symbol, and reproducibility evidence. The validator and all 17 mutation tests
pass, but no actual backend, reliable ordered carrier, or
fragmentation/reassembly implementation has been selected or built. Rung two
has since consumed its exact one-use source request and retained verified bytes
without extraction. Rung-three v1 and v2 each consumed their own permit and
failed closed before publication. The separate v3 one-use path completed a
bounded lexical candidate inventory and tracked readback. That v3 predecessor
recorded `rung3_v3_publication_read_back_complete` and
`prepare_separate_versioned_rung3_semantic_source_review_decision` at that
checkpoint. The tracked
[semantic-review decision v1](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/semantic-source-review-decision-v1.json)
is now historical execution authority. The semantic-review checkpoint is
bound by the [classifications](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/semantic-source-review-classifications-v1.json),
[result](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/semantic-source-review-result-v1.json),
and atomic [manifest](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/semantic-source-review-manifest-v1.json):
`status=rung3_semantic_source_review_v1_publication_read_back_complete_semantic_closure_blocked`,
`result=two_non_attesting_full_coverage_semantic_passes_published_and_independently_read_back_patch_and_dependency_gaps_remain`,
and
`recordedNextActionAtThatCheckpoint=prepare_versioned_rung3_patch_and_dependency_closure_decision`.

That next action is now satisfied by the preparation-only
[patch/dependency decision v1](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/patch-and-dependency-closure-decision-v1.json)
and its [security-hardening portfolio](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/patch-and-dependency-closure-decision-v1/hardening.md).
At that checkpoint it recorded
`status=prepared_options_unselected_dependency_closure_blocked`,
`result=four_structural_recommendations_and_eight_unselected_treatment_units_prepared_all_19_findings_remain_open`,
and
`recordedNextActionAtThatCheckpoint=prepare_separate_versioned_implementation_or_dependency_review_decision`.
It maps all 19 findings to seven unselected root patch units and one unselected
dependency-review unit, and its read-only checker passes 28/28 checker tests.
The checker pins the complete 19-file portfolio, rejects unexpected artifacts,
schema claims, reader-facing effect drift, and replace-after-read drift, and
retains all input identities through its final readback.
Recommendations are not selections: all option, implementation, dependency,
closure, candidate, and library selection flags remain false. Source change,
dependency acquisition, compiler, socket, network, device, deployment, and Git
write remain unauthorized. Neither external authentication nor user action is
authorized or required.

The separate
[implementation-or-dependency review decision v1](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/implementation-or-dependency-review-decision-v1.json)
and [staged fixed-point review plan](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/implementation-or-dependency-review-decision-v1/implementation/staged-fixed-point-source-closure.md)
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
complete 19-file portfolio bundle, and review plan; they assert distinct raw,
selection, authority, finding, closure, contract, sequence, plan, inventory,
filesystem, and TOCTOU failure layers. All 19 findings remain open and
dependency acquisition, source modification/extraction, package management,
compilation, source load/execution, sockets, network, device, deployment, Git
writes, external authentication, and user action remain unauthorized or
unrequired.

The predecessor
[bounded dependency wave-one preparation decision v1](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-v1.json)
and its [reader-facing decision](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-v1.md)
record
`status=wave1_source_identity_and_request_contract_prepared_acquisition_not_authorized`,
`result=exact_19_root_requirement_source_identities_and_bounded_wave1_request_contract_prepared`,
and
`nextAction=prepare_separate_versioned_wave1_execution_permit_after_checker_runner_and_tests`.
They freeze the exact 19-tuple intake seed, four quarantined checksum-only
tuples, two V1 arm64 review profiles, deterministic fixed-point graph rules,
public-proxy request/output set, and finite failure/receipt bounds. The checker
passes 56/56 mutation tests. It also rehashes the retained root ZIP, embedded
`go.mod`/`go.sum`, and source tree, verifies that every premature wave artifact
is absent through the final barrier, and pins the exact H1 and ordered
source-set digest algorithms. This is preparation only: request count is zero,
dependency acquisition and network remain unauthorized, all 19 findings remain
open, and no candidate or library is selected. Neither external authentication
nor user action is required.

The historical successor
[bounded dependency wave-one execution permit v1](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-execution-permit-v1.json)
and its [reader contract](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-execution-permit-v1.md)
recorded, before execution,
`status=wave1_dependency_source_acquisition_authorized_not_consumed`,
`result=exact_19_public_proxy_zip_requests_authorized_once_not_executed`,
and `recordedNextActionAtThatCheckpoint=execute_bound_dependency_source_wave1_once`.
The isolated streaming runner still passes 44/44 tests. The permit suite
recorded 38/38 only at the unconsumed checkpoint; the current gate reruns its
36 state-independent cases because v1 is consumed and may not be retried.

The historical
[wave-one recovery decision v1](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-recovery-decision-v1.json)
and its [reader contract](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-recovery-decision-v1.md)
recorded, at that checkpoint,
`status=wave1_v1_failure_read_back_recovery_v2_design_selected_execution_not_authorized`,
`result=v1_ratio_policy_rejected_tuple2_after_two_responses_no_final_set_v2_bounded_telemetry_policy_selected`,
and `recordedNextActionAtThatCheckpoint=prepare_separate_v2_runner_checker_tests_and_execution_permit`.
The retained v1 claim and failure receipt show two completed response bodies,
one fully validated and staged tuple, `E_ZIP_RATIO` during the second ordered
tuple, zero accepted artifacts, and no final set. The 31/31 recovery tests
keeps v1 immutable, distinguishes HTTP completion from validation/staging, and
selects non-gating exact-integer compression telemetry while retaining every
absolute streaming and deadline bound.

The historical
[wave-one execution permit v2](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-execution-permit-v2.json)
and [reader contract](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-execution-permit-v2.md)
recorded, before its single execution,
`status=wave1_v2_dependency_source_acquisition_authorized_not_consumed`,
`result=exact_19_public_proxy_zip_requests_v2_authorized_once_not_executed`,
and `recordedNextActionAtThatCheckpoint=execute_bound_dependency_source_wave1_v2_once`.
That permit is now consumed and may not be reused. The retained v2 claim and
failure receipt record `E_GO_MOD_MISSING` on tuple 11 after 11 completed ZIP
responses, 10 validated/staged tuples, zero accepted artifacts, and no final
set.

The predecessor
[wave-one recovery decision v2](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-recovery-decision-v2.json)
and [reader contract](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-recovery-decision-v2.md)
record
`status=wave1_v2_failure_read_back_recovery_v3_design_selected_execution_not_authorized`,
`result=v2_conflated_zip_and_mod_resources_tuple11_after_eleven_responses_no_final_set_v3_zip_plus_mod_policy_selected`,
and
`recordedNextActionAtThatCheckpoint=prepare_separate_v3_runner_checker_tests_and_execution_permit`.
The checker and 39/39 mutation tests bind both terminal generations and select
a fresh 19-pair `.mod`-then-`.zip` design with 38 separately validated
resources. That preparation action is complete.

The historical
[wave-one execution permit v3](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-execution-permit-v3.json)
and [reader contract](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-execution-permit-v3.md)
recorded, before execution,
`status=wave1_v3_dependency_source_acquisition_authorized_not_consumed`,
`result=exact_19_public_proxy_mod_then_zip_pairs_v3_authorized_once_not_executed`,
and `nextAction=execute_bound_dependency_source_wave1_v3_once`. It is now
consumed and cannot be retried. The immutable
[success receipt](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-receipt-v3.json)
and [manifest](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-manifest-v3.json)
record `status=acquired_pending_independent_readback`,
`result=fresh_exact_19_dependency_zip_mod_pairs_acquired_and_hash_verified`,
38 request attempts, 38 completed bodies, and 38 accepted resources across 19
exact `.mod`/`.zip` pairs. The separate
[readback receipt](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-readback-v1.json)
and [manifest](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-readback-manifest-v1.json)
now validate `status=independent_readback_complete`, 43 regular files, and the
same 38 resources. The permit-bound 34/34 reader tests remain immutable; a
versioned recovery reader recorded the outputs once, and the
[fixed-hash post-verification decision v3](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-readback-post-verification-decision-v3.json)
plus its verification-only 9/9 suite close the discovered raw-encoding,
dispatch, TOCTOU, and typed-comparison gaps with
`fixedHashEnforcedInsideHeldValidation=true`, `verificationOnly=true`, and
`recordModeExposed=false`. That checkpoint recorded
`recordedNextActionAtThatCheckpoint=prepare_separate_dependency_source_review_wave`.
The
[dependency source-review wave-one decision v1](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-review-wave1-decision-v1.json)
then prepared the bounded review contract. It was followed by two immutable
failed-closed review attempts:
v1 recorded `E_HELD_SET`, and v2 recorded `E_ARCHIVE_STRUCTURE`; neither
published a partial result. The corrected one-use v3 review produced the
[result](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-review-wave1-result-v3.json)
and
[manifest](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-review-wave1-manifest-v3.json),
then the separate
[readback receipt](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-review-wave1-readback-v3.json)
and
[readback manifest](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-review-wave1-readback-manifest-v3.json)
were written once. That readback records
`status=dependency_source_review_wave1_readback_published_new_tuple_wave_required`;
the
`result=independent_readback_receipt_published_then_manifest_written_last_new_tuple_wave_required`;
its recorded next action was
`nextAction=prepare_separate_versioned_dependency_wave2_identity_and_acquisition_decision`.
The held review recorded graph SHA-256
`2c94906a07a40737e30ca832c215fa88d2233297c9fb0ea25755488d9a72408b`,
132 nodes/1,047 edges, a 35-node/86-edge module graph, 25 selected versions,
zero unmapped or unresolved declared external imports, and an exact 15-tuple
frontier. Five are missing selected-version sources and ten are required
version-specific vertices; all remain `acquisitionAuthorized=false` and must
not be deduplicated or replaced by a higher version. The route is
`new_tuple_wave_required`, so graph fixed point and every dependency,
semantic, rung-three, candidate, library, and release closure remain false.
All 19 findings remain open. This work uses no owner proof, credentials, keys,
signatures, tokens, passwords, or user action. Extraction, compilation, source execution,
runtime/product network, device, deployment, and Git work remain closed.

That historical preparation action is recorded in the
[wave2 identity/acquisition decision v1](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave2-v1.json)
and its
[reader](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave2-v1.md).
The read-only checker plus 37/37 offline regression checks bind all 15 exact versions,
their parent `.mod` declarations, and 30 ordered `.mod`-then-`.zip` H1
expectations from already-held, non-conflicting `go.sum` evidence. Five
MVS-selected and ten non-selected version-specific vertices remain distinct.
At that checkpoint,
`status=wave2_local_checksum_identity_and_30_resource_contract_prepared_future_bytes_unverified_acquisition_not_authorized`;
the result was
`result=exact_15_graph_frontier_tuples_30_mod_zip_requests_and_held_h1_expectations_prepared_future_bytes_unverified`;
and
`recordedNextActionAtThatCheckpoint=prepare_separate_versioned_wave2_checker_runner_tests_and_one_use_execution_permit`.

That recorded action is now complete in the
[wave2 one-use execution permit v1](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave2-execution-permit-v1.json)
and its
[reader](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave2-execution-permit-v1.md).
Current status is
`status=wave2_v1_dependency_source_acquisition_authorized_not_consumed`;
current result is
`result=exact_15_public_proxy_mod_then_zip_pairs_authorized_once_not_executed`;
and `nextAction=execute_bound_dependency_source_wave2_v1_once`.
Focused evidence passes 41/41 permit, 50/50 runner, and 39/39 independent
readback checks in addition to the 37/37 decision checks. Exact preflights
observe 15 tuples, 30 ordered public Go proxy requests, an empty namespace,
`networkUsed=false`, and no file writes. Future response bytes remain
unacquired and unverified; held H1 pairs are not fresh checksum-database proof.
Only this bounded one-use source intake is authorized. Extraction, source
loading/execution, package management, compilation, runtime/product network,
device, deployment, and Git remain closed. Repository authentication, account
login, owner proof, credential, key, signature, token, and password are outside
this workflow. Neither external authentication nor user action is authorized
or required.

The rung-two successor recorded, only `at_that_checkpoint`,
`recordedNextActionAtThatCheckpoint=prepare_versioned_rung3_offline_source_review_decision`.
That historical preparation action is complete and is not current authority.

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
`productionDeploymentAllowed=false`, and `gitOperationAllowed=false`. Schema 1.1
remains a not-yet-implemented and not-runtime-verified design. It
requires a separate single-use egress capability after resolution immediately
before socket create, bind, connect, TLS handshake, or write, plus fixed-size
bounded ingress read/parse/admission before state mutation or payload delivery.
It requires authenticated TURN TLS service identity before any credential
transmission and a bounded one-use pre-auth path whose atomic promotion occurs
only after exact AetherLink endpoint confirmation. Consent loss, path change,
candidate restart, capability expiry, verification failure, and session close
each atomically revoke both pre-auth and application capabilities before further
I/O, state mutation, event, or payload delivery. Exact per-session and process
bounds cover current, active, draining, and closing state, and event overflow
requires an independent sticky terminal latch. Secret-free diagnostics and a
2,500 ms total close deadline are requirements, not completed implementation or
runtime-verified behavior. The actual
backend, reliable ordered carrier, and fragmentation/reassembly remain unselected
and unimplemented. Only stack-neutral wiring may continue. Repository-owner,
GitHub, SSH, GPG, or
public-key identity proof is neither a prerequisite nor a future G2 rung;
`externalIdentityProofRequired=false` and `userActionRequired=false`. Product
pairing and endpoint authentication remain mandatory and separate.

The tracked rung-three [result-v3](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/offline-source-review-result-v3.json),
[runtime-manifest-v3](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/offline-source-review-runtime-manifest-v3.json),
and [execution-receipt-v3](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/offline-source-review-execution-receipt-v3.json)
bind exact readback. The result is 76,685 bytes at SHA-256
`ef4b8d88ec57501377a7bc9db066c04a1a379041ee1b11999f5d16c7d4447933`;
the runtime manifest is 2,458 bytes at SHA-256
`2dace9b59b7374423754f1f9a7345eda76db9130728d1c0579797e5a0c829055`.
The inventory observed 100 Go files, 1,077,591 source bytes, and 39,064 logical
lines. Its 19 lexical rules across seven patch units found 4,701 hits, recording
144 bounded representatives at no more than eight per rule and omitting 4,557.
All 129 archive entries use
creator system 0 metadata accepted as DOS attributes `00` and synthetic
read-only mode `100444`; no filesystem extraction occurred.

That v3 inventory remains historical lexical location evidence, not 4,701
vulnerabilities. Semantic-review v1 has since completed two non-attesting full-
coverage passes over all 100 Go source bodies and all 4,701 observations. The
29 input candidates deduplicate exactly to 19 findings: severity counts are
P0=0, P1=11, P2=3, P3=4, and none=1; dispositions are patch_required=7 and
unresolved=12. The one-use zero-hit remains a missing-required-mechanism gap,
and disagreements remain unresolved. The independent tracked-only
[post-run checker](script/check_p2p_nat_g2_pion_rung3_semantic_review_result_v1.py)
and its 25/25 mutation tests hold all eight file descriptors plus every
repository-path directory component through two stable full-set readback passes
and a final identity barrier, validate the manifest last, and observe the
failure file and four staging names absent before and after readback.
`semanticSourceReviewPerformed=true`, while
`semanticClosureComplete=false`, `dependencyClosureComplete=false`,
`rungThreeComplete=false`, `candidateSelected=false`, and
`librarySelected=false`. Semantic review was performed, but semantic closure,
dependency closure, rung-three completion, candidate selection, and library
selection remain false. The checker does not independently reproduce semantic
judgments or source-based location bounds. Same-UID concurrent mutation is not
prevented, and absence is not guaranteed after the final observation. No source
body, individual line digest, absolute path, or credential/secret value is
published. No materialization, source compilation/execution, dependency
installation, socket, network, device, deployment, or Git operation occurred.
No repository-owner
authentication, external identity proof, execution-permit authentication or
document, or user action is required.

The previous complete default no-device aggregate snapshot exits zero with
`No-device quality checks passed.` It records the initial Python batch at
182/182, 1,946 Swift tests with two declared skips and zero failures, every
Android Gradle invocation as `BUILD SUCCESSFUL`, copy hygiene across 94 files,
docs hygiene across 12 files, direct and development-relay local mock smokes,
relay freshness across 56 connections, 905 encrypted frame bodies at the
ciphertext boundary, and the final G1a-D authority-lifecycle marker. This is
no-device local evidence, not physical-device, external-network, production-
transport, or production app/service activation proof. The transport-
composition and G1b-A focused tests are newer than those snapshot counts; the
prior aggregate was not refreshed for these seams.

Older progress entries remain historical unless the handoff promotes them as
current.

The current implementation baseline remains v0.1 and is intentionally narrow.
It proves one product loop:

1. Start AetherLink Runtime on the runtime host.
2. Configure eligible remote route material and show a production pairing QR on the runtime host.
3. Scan and pair from the device app without entering an Ollama or LM Studio URL.
4. List installed local models through the trusted runtime.
5. Send chat messages from the device app.
6. Stream responses back from the runtime host.
7. Cancel an in-flight generation.
8. Reopen previous runtime-backed chats and sync user-entered memory through the trusted runtime.

There is no cloud AI backend, account server, client-side local model execution, or direct client-to-Ollama/LM Studio connection. Production QR generation requires eligible remote route material. A local direct QR is diagnostics/development only, and a small outbound TCP development relay exists for different-Wi-Fi testing. QR-provisioned relay routes must include `relay_host`, `relay_port`, `relay_id`, `relay_secret`, `relay_expires_at`, and `relay_nonce`; loopback, `.local`, link-local, carrier-grade NAT, and private-network relay IP literals are not normal QR-ready routes. Use a public, VPN, tunnel, DNS, or future private-overlay route name that both devices can reach. Relay payload frame bodies are encrypted end-to-end between the client and runtime host, while the relay still sees only `relay_id`. This is still development transport scaffolding, not a production relay, account service, model backend, or complete NAT traversal layer.

## Connectivity Direction

AetherLink should not depend on a fixed IP address or permanent same-network access. Fixed host/port values, `127.0.0.1:43170`, USB reverse, and mDNS/Bonjour local discovery are v0.1 development hints or local fast paths only. The product direction is a paired-device private P2P overlay:

1. Pair devices by QR and bind persistent device identities/keys.
2. Try local direct discovery/connection when both devices are nearby.
3. Use the temporary development relay for current different-Wi-Fi testing when explicitly configured.
4. Replace that with remote P2P NAT traversal when devices are on different networks.
5. Fall back to an end-to-end encrypted blind relay/TURN-style path only when direct P2P fails.

Bitcoin-network analogy note: AetherLink borrows only the idea that peers can be identified and discovered without depending on one fixed server address. It is not a public, untrusted, open network. Only QR-paired trusted devices should be able to discover, authenticate, and exchange runtime traffic.

Any future relay/signaling component is connection infrastructure only. It must not run AI, store or inspect AI protocol payloads, see model lists, prompts, files, memory, or backend credentials, or replace the local runtime.

Current implementation status: AetherLink has pairing, trusted runtime records, local endpoint hints, Bonjour/local discovery candidates, USB reverse/dev-server paths, a route-candidate abstraction, opaque P2P rendezvous route records for QR/authenticated refresh planning, and a temporary outbound TCP development relay keyed by private `relay_id`. QR-provisioned relay routes require `relay_secret`, `relay_expires_at`, and `relay_nonce`, so AetherLink frame bodies are encrypted before relay forwarding and stale QR route material can be rejected. Real remote P2P NAT traversal, distributed/bootstrap discovery, hardened relay allocation, replay-resistant session setup, and production end-to-end transport encryption are not complete yet.

Production pairing QRs are generated only when the runtime has eligible remote route material to include. Local direct QR payloads are diagnostics/development artifacts, not the product route for same-network or fixed-IP pairing. When a QR/trusted runtime record contains remote route metadata, the client tries prepared remote routes before local direct routes: opaque P2P records first, then the current relay, then fresh local discovery and diagnostic endpoint hints. Automatic reconnect does not promote a stale last-known private IP address as the product route; it resolves the paired runtime identity through current discovery, USB/emulator development forwarding, P2P record material, or relay metadata instead.

## Repository Layout

```text
apps/
  android/        Current Kotlin + Jetpack Compose client/controller
  macos/          Current SwiftUI runtime-host shell
packages/
  protocol-schema Versioned JSON protocol and pairing QR schemas
docs/             Architecture, protocol, security, and roadmap notes
script/           Project-local build/run and QA entrypoints
```

## v0.1 Scope

- Current mobile client UI: remote-route QR pairing, connection status, model picker, chat, runtime-backed chat history, runtime-owned user memory, streaming, cancel.
- Current desktop runtime UI: runtime status, remote-route QR pairing, trusted devices, local backend status, basic logs.
- Bonjour/mDNS service name: `_aetherlink._tcp.local.`
- Length-prefixed JSON protocol over a local authenticated socket.
- Ollama support through the runtime host's local adapter.
- Ollama reasoning/think stream chunks are preserved separately from final answer text and forwarded through AetherLink Runtime as reasoning deltas.
- LM Studio support through the runtime host's local adapter. Start LM Studio's server from the Developer tab or `lms server start`; the device app still never sees or calls the LM Studio URL.
- Pairing and discovery may be simple in v0.1, but runtime commands still require a trusted-device boundary. Same-network unauthenticated access is not an acceptable architecture.
- Remote P2P NAT traversal and production encrypted relay fallback are target connectivity milestones, not current v0.1 transport capabilities.
- The current development relay can help test devices on different Wi-Fi networks. QR-provisioned relay routes require `relay_secret`, `relay_expires_at`, and `relay_nonce`; relay payload frames are encrypted between the paired client and runtime, but the relay still lacks production-grade allocation, token rotation, replay protection, and NAT traversal.

## Model Behavior

- Installed Ollama models come from AetherLink Runtime querying Ollama `/api/tags` on the runtime host.
- Running Ollama models may be detected by AetherLink Runtime through `/api/ps` when available.
- Installed LM Studio models come from AetherLink Runtime querying LM Studio's local REST API on the runtime host. The adapter prefers native `/api/v1/models` and `/api/v1/chat`, with fallback to OpenAI-compatible `/v1/models` and `/v1/chat/completions` if native endpoint shape differs.
- Provider-qualified chat and embedding operations query only the selected
  Ollama or LM Studio catalog. Unqualified legacy chat still searches the full
  aggregate catalog.
- Local models are the main path.
- The normal chat picker shows installed runtime-host-local chat models. Ollama cloud/source metadata can remain in protocol data for compatibility, but it is not presented as a default, recommendation, or normal chat selection path.
- If backend model lists are empty, the runtime returns an empty model list and does not invent recommended/default local or cloud model cards.
- Legacy `models.pull` requests enter a macOS-host-local approval queue. A current trusted-device authority check and durable redacted one-time dispatch reservation must succeed before the host can call Ollama `/api/pull`; Android does not currently advertise or send this command.
- The device app never calls Ollama or LM Studio URLs directly, including `/api/tags`, `/api/ps`, `/api/pull`, or chat endpoints.

## Non-Goals

MCP, embedding-based research, advanced memory/RAG, skills, web search, file indexing, terminal execution, iOS, Windows/DGX OS runtime targets, additional serving backends, cloud sync, user accounts, and production remote connectivity infrastructure are roadmap features, not the v0.1 local chat backend path.

한국어 메모: v0.1에서 디바이스 앱은 Ollama나 LM Studio 주소를 직접 입력하거나 호출하지 않습니다. 항상 AetherLink Runtime을 통해 모델 목록, 채팅 스트리밍, 취소 요청을 보냅니다.

## Development Notes

AetherLink Runtime is a SwiftPM SwiftUI app and can be launched with:

```bash
./script/build_and_run.sh
```

To assemble a self-contained local Release app without stopping or launching the
running app:

```bash
./script/build_and_run.sh --package-only
```

This mode cleans the default Swift build workspace, writes the package to
`dist/package-only/AetherLink.app`, and leaves the development bundle at
`dist/AetherLink.app` untouched. Set `AETHERLINK_PACKAGE_OUTPUT_ROOT` only to
an absolute, dedicated non-app direct child of `dist/` when a separate package
lane is needed; the reserved development bundle path `dist/AetherLink.app`
is rejected before the toolchain runs. The mode embeds the SwiftPM localization bundle under
`Contents/Resources`, writes semantic/build version metadata, and applies the
same strict local ad-hoc seal used by development packaging. It is a local
qualification artifact, not Developer ID signing, notarization, or a DMG.
Both this package and the Android Release variant read
`release/version-ledger.tsv`; its current entry is marketing version `1.0.0` and shared build number `24`.
Android Debug deliberately remains `0.1.0+1`.
Its Release metadata is backed by a lazy Gradle provider, so Debug still
configures and builds when the release ledger is unavailable; a Release task
validates the ledger's LF-only printable-ASCII/tab byte format when it needs
the version.
Build 23 and later archives additionally require the compiled APK and AAB to
agree on two normalized Android claims. `entryPointTopology` closes the exact
MainActivity launch behavior, launcher and `aetherlink://pair` filters, and
identical single/multiple-share sets of 44 MIME types. `applicationShell`
resolves the compiled label, icon, round icon, theme, and locale-config
references; preserves the exact `en`, `ko`, `ja`, `zh-CN`, `fr` locale-config
order; and reads the default plus five localized `status_title` payloads.
The direct AAB check resolves the five manifest references and localized
payload and requires language splitting to remain disabled. A universal APK
derived from that same AAB independently supplies the compiled locale-config
body/order and must agree with those direct observations before the composite
AAB result is compared with the standalone APK claim.
Unrelated dependency activities remain outside the MainActivity claim. The
builder and readback checker implement these parsers independently and validate
closed, exact-type claims. At the preflight stage, this forward gate did not
alter the then-current Build 22 ledger or archive.
An isolated current-source `1.0.0+23` preflight confirmed that offline
strict-lock Release APK/AAB generation and lint pass and that the builder and
independent checker produce the same compiled claims. The temporary candidate
did not advance the canonical worktree's `release/version-ledger.tsv`, create
a retained archive, sign for distribution, install, upload, or launch the app.
Later, the ordinary release wrapper retained
`dist/releases/aetherlink-1.0.0+23-local-v1/` as an immutable Build 23 archive.
Its 166,859,521-byte ZIP has SHA-256
`b9a9c3c2ebeb01fc735fed3356f1f244178fb4521c1a806dc7a93d776f83ea2e`.
A subsequent comparison-only Build 23 candidate was not published: its
19,645-byte result at
`dist/reproducibility/aetherlink-1.0.0+23-local-v1-two-root-v4-prepublication.json`
has SHA-256
`e82cfc2b2cf005ace6f5405065b997f7fb66a1338d1bf3d3fe082d1b9863b297`.
Its
166,345,274-byte ZIP SHA-256
`f9bee58ed228e31103bfd3929d2b2ba9c4fd30cb3fbc907b6f39f2d287239ffb`
differed from the retained archive in the macOS executable, dSYM DWARF member,
and relocation member. Build 23 therefore remains a historical ordinary-wrapper
archive, not the canonical qualified two-root lineage. Build 24 appended a new
ledger entry and became that lineage without replacing Build 23.
The development application and bundle identifiers remain unchanged until
their production replacements are reserved in the selected distribution
accounts.

To build the optimized unsigned Android Release artifacts and release lint
report from a populated dependency cache:

```bash
./gradlew --offline --no-daemon --console=plain \
  :app:assembleRelease :app:bundleRelease :app:lintRelease \
  -Pkotlin.incremental=false
```

The release build enables R8 code shrinking/obfuscation and resource shrinking.
The unsigned APK and AAB are written below `apps/android/app/build/outputs`;
the R8 mapping and related outputs are below
`apps/android/app/build/outputs/mapping/release`. Preserve the exact mapping
with any signed artifact derived from that build. This command does not sign,
install, upload, or launch the app.

After generating both local release artifacts, verify their shared version
metadata against the ledger with:

```bash
python3 script/check_release_version_ledger.py --artifacts
```

To clean-build both V1 targets, enforce the recorded Release dependency graph,
package their local outputs, and perform an independent full-byte readback in
one command:

```bash
./script/build_release_artifacts.sh
```

The wrapper uses `dist/release-package/AetherLink.app` as its private macOS
staging bundle, so it never removes or replaces the development app at
`dist/AetherLink.app`.

When release inputs have changed, append a strictly higher shared build number
to `release/version-ledger.tsv` before running this command. Published local
release IDs are immutable: the packager refuses to replace an existing ID with
different bytes.

The current output is
`dist/releases/aetherlink-1.0.0+24-local-v1/`. It contains one canonical
normalized-input ZIP, an identical external manifest, and a ZIP SHA-256
sidecar.
Android Release is unsigned and `arm64-v8a`-only; the macOS app is a thin
`arm64` local ad-hoc package accompanied by its UUID-matched dSYM. The container
metadata is canonical. R8's `resources.txt` uses a semantic reachability
normalization; `seeds.txt`, `mapping.prt`, and extracted configuration roots
use their separately declared normalizations while retaining the checked
payload meaning.

The Build 24 qualification runner created two isolated lane worktrees from one
249-file `dirty-content-snapshot`. With the same host, fixed toolchains, paired
clones of one byte-identical Gradle seed, and a fixed canonical Swift scratch
policy with serialized frontend work, the separately invoked comparison-only
and publish-qualified A/B runs produced the exact 166,345,274-byte ZIP
`104c07b6fc1b421bcc0309657001fdf991e37bb815c282b3e5112ed98821ab1c`,
the exact 15,200-byte manifest
`eccc81de7eee5d56223e7826d153617a24725344154f7c7c5dd291d25ab6369b`,
and the exact 99-byte checksum sidecar
`827cdc72cbe44c47b75a7abc899b6523361ed9332942a721b624509ffcea5882`.
The 19,645-byte prepublication result
`dist/reproducibility/aetherlink-1.0.0+24-local-v1-two-root-v4-prepublication.json`
has SHA-256
`64c21a8c345018e7fca552b1ff706ac5f9c1f19a349afb0090dae22466e9e3db`
and records `executionMode=comparison-only`,
`publication.outcome=disabled-comparison-only`, and
`qualifiedArchivePublished=false`; it did not publish an archive. The
separately invoked 20,353-byte canonical result
`dist/reproducibility/aetherlink-1.0.0+24-local-v1-two-root-v4.json` has
SHA-256
`08a176bed8abe4f4c62178fa13a939059d127ee3dee4352096bcc593177cea36`
and records `executionMode=publish-qualified`,
`publication.outcome=published-verified`, `alreadyMatched=false`,
`qualifiedArchivePublished=true`, `independentReadback=true`,
`publishedBytesEqualLaneA=true`, and `sourceSnapshotUnchanged=true`. The claim is
limited to these two recorded successful same-host pairs, not variance-free
arbitrary repeats, arbitrary-root, cross-host, clean-machine, signed-artifact,
or physical-device qualification. Publication is bound to the exact canonical
prepublication result, and protected Build 23 archive identity
`df16cc1c38a414fa0c8e09eb3954645c34ba42aba21060ca6ad5710e4b47a4f6`
remained unchanged. The Git commit alone cannot reconstruct the dirty release
snapshot. The exact 249-file source digest is
`a01d37c3be608db3a8fa588b1ec019b673b5c57bc227ffc105047b3e4548f5f2`;
its overlay digest is
`9d71c5340e1809222542c59d0da96f1ee08f9b619741ae3b0f1cb4fcbc28a3cc`.
Immutable Builds 1 through 23 remain available for historical readback. The
verifier cross-binds every recorded Gradle lock identity to the archived source
inventory and keeps current and historical readback modes mutually exclusive.
Current readback is
`python3 -B script/check_release_artifact_archive.py --archive-dir dist/releases/aetherlink-1.0.0+24-local-v1`.

Build 18 first source-binds the Android drawer search release inputs. The
historical Builds 19 through 23 retained those inputs, and Build 24 retains
them.
The bound no-device evidence includes
the complete 1,194-test app JVM suite, and release lint reports 0 errors and 2
SDK 37 availability warnings.
This source/JVM/Compose evidence is not part of the immutable Build 17 archive and is first source-bound by the immutable Build 18 archive; it does not establish physical touch, TalkBack, provider, device, network, installation, signing, or release behavior.

Current unreleased Android source also resets chat scrolling at an actual
conversation boundary. Immediate and delayed session switches return to the
new transcript's latest row, including a saved-state restore while cached
messages are loading, while same-session streaming updates preserve an earlier
reading position. Latest-message action targets are computed once per screen
composition. The current no-device app suite passes 1,195 tests; Release
assembly and lint pass with 0 errors and the two existing SDK 37 availability
warnings. Build 24 source-binds the product inputs for this behavior; the
separate unit, Compose, CI, and documentation evidence is not an archive
member and does not establish physical-device rendering or measured frame-time
behavior.

Build 19 first source-bound the Runtime-chat SQLite cross-process QA closure;
Build 24 retains that source-bound closure.
Every production connection installs a 5-second SQLite busy timeout, and
`SQLITE_BUSY`/`SQLITE_LOCKED` normalize to the stable retry message
`Runtime chat history is temporarily busy. Try again.` Three deterministic
Swift tests cover wait-and-release success, `BEGIN` timeout rollback, and
`COMMIT` timeout rollback; all 90 store tests and the full 2,084-test Swift
suite pass with 11 expected opt-in/live skips. A separate live QA run launched
two independent writer processes for 48 events each and a third independent
readback process. It observed 96 disjoint exactly-once events, owner/session
isolation, per-writer append ordering, `integrity_check=ok`, directory mode
`0700`, and SQLite file mode `0600`. The live result is execution evidence,
not a retained archive member. It does not establish crash/power-loss,
arbitrary histories, mixed old/new binaries, clean-machine, signed/notarized,
physical-device, or production behavior.

<!-- aetherlink-current-build21-abrupt-recovery-v1:start -->

Build 21 adds a bounded same-host abrupt child-process recovery result at
`dist/lifecycle/macos-runtime-chat-sqlite-abrupt-process-recovery-build-21-v1.json`.
The canonical result is 2,223 bytes with SHA-256
`db66614d7badd7a0f606c03f91a516dff6d77e539684dcb6daf52709bce0f16f`.
It proves the exact QA sequence of 24 committed events, one dirty uncommitted
25th event and FTS row after child-only `SIGKILL`, rollback-journal recovery to 24,
and production-store resume to 48 contiguous exactly-once events. This is
bounded same-host abrupt child-process `SIGKILL` recovery evidence, explicitly
`not-production-append-crash-point`, not power-loss or kernel-crash evidence,
not arbitrary-history or long-soak evidence, and not clean-machine,
signed-distribution, or physical-device evidence.

<!-- aetherlink-current-build21-abrupt-recovery-v1:end -->

The historical Build 19 same-host, per-user clean-HOME observations remain
bound to Build 19. Its 2,250-byte installed-app result is
`dist/lifecycle/macos-packaged-app-build-19-clean-home-install-v1.json`,
SHA-256
`a89291227bde1f9f15caa3743339f569e9f7c79380f8f3a70df0a0fe8388b159`;
its 3,364-byte installed state-recovery result is
`dist/lifecycle/macos-packaged-app-build-19-clean-home-state-recovery-v1.json`,
SHA-256
`1c72536188ce71388319d068489f4c351521f33d5431af36e7acc5ff76bdb2b7`.
Those historical observations are not reinterpreted as Build 21 evidence.

<!-- aetherlink-historical-build20-lifecycle-v1:start -->

Build 20 retains historical same-host, per-user macOS installed-lifecycle
evidence. The clean-HOME runner copied the exact packaged app into an isolated
Applications path and exercised two distinct exact-path LaunchServices
processes. Its canonical 2,250-byte result is
`dist/lifecycle/macos-packaged-app-build-20-clean-home-install-v1.json`,
SHA-256
`4ce047a318e47568d647e1167cbaeebc603626073e098451a29c949086aa3d72`.
The separate legacy-to-SQLite-to-SQLite-only runner produced the canonical
3,364-byte
`dist/lifecycle/macos-packaged-app-build-20-clean-home-state-recovery-v1.json`,
SHA-256
`d12947e16e7b985515a90a13731947a5991bcd82a06039210e22bba43535bf0b`.
A separate ephemeral local-DMG run created and verified an HFS+ UDZO image,
mounted it read-only and without browsing, checked the Applications alias,
copied the exact release tree with `ditto`, detached the image before launch,
and exercised two distinct installed-app processes. Its canonical 2,434-byte
result is
`dist/lifecycle/macos-packaged-app-build-20-local-dmg-install-v1.json`,
SHA-256
`e78b605278d5c5b7f5601778c38f35270f1db4a9e95055ff434b71af4c33cf78`.
The image was ephemeral and was not retained. Both clean-HOME runners were
invoked twice and matched their canonical results.
These historical same-host, per-user Build 20 observations do not qualify a clean
machine/account, signed/notarized distribution, UI/accessibility,
live-provider behavior, a physical device, arbitrary histories,
crash/power-loss, concurrent writers, backup/transfer, rollback, or production
readiness. The DMG run remains outside Finder UI, drag-and-drop, Gatekeeper
quarantine/download behavior, TCC, Keychain, network behavior, and system
Applications installation evidence.

<!-- aetherlink-historical-build20-lifecycle-v1:end -->

Build 24 preserves compliance profile `aetherlink-release-compliance-v2` and four
deterministic members: a
350-coordinate Gradle lock/POM catalog, fixed creation metadata, a text
third-party license inventory, and SPDX 2.3 JSON. It emits 692 exact
package-to-root roles: 202 runtime, 155 build dependency, and 335 build tool.
Build 8 remains readable under the same exact-role V2 contract. Build 7 remains
readable under its frozen profile-less, precedence-compressed
350-relationship V1 contract. The catalog retains 379 POM URL/size/SHA records,
parsed declarations, and zero Swift external packages, but not original POM
bodies or license/NOTICE texts. Offline readback does not re-fetch or re-parse
those originals, so attribution completeness, original POM authenticity,
binary/source coverage, and legal compatibility are not claimed. Third-party
license conclusions remain `NOASSERTION`.
Refresh public POM evidence only as an explicit maintenance action with
`python3 -B script/generate_release_compliance.py refresh`, then validate the
checked-in catalog offline with
`python3 -B script/generate_release_compliance.py check`.

The historical Build 9 macOS lifecycle smoke reads back the exact Build 9
ZIP, extracts its packaged app into a temporary root, and completes two
AppKit finished-launch → minimum five-second observation → identity-rechecked
exact-PID termination cycles. Both runs exit zero. The QA-only sandbox uses a
temporary Core Foundation user home, denies non-temporary writes and AF_INET
binds, and has no unisolated fallback. Its exact 1,311-byte result is
`dist/lifecycle/macos-packaged-app-build-9-lifecycle-v1.json`, SHA-256
`aad796ee3c768e37953f18eeea0e6642107750c3a8c398df798a46e96aabab53`.
Expected Application Support files were present after each run, but the
identity-file override used the in-memory fallback; the smoke therefore makes
no identity-persistence or state-recovery claim. It also does not qualify
installation, UI correctness, runtime listeners, providers, a clean machine,
signed distribution, or physical-device behavior. Run it with
`python3 -B script/run_macos_packaged_app_lifecycle_smoke.py`.

Six generated Gradle lock files cover settings, the buildscript, and
configurations resolved by the clean Release graph. Release uses strict
read-only lock mode and never writes locks. The manifest declares the one
Gradle 9.4.1/Kotlin 2.3.21 compatibility exception,
`org.jetbrains.kotlin:kotlin-stdlib-common`; its locked parent
`kotlin-stdlib:2.3.21` remains fixed. SwiftPM currently has no external package
dependencies, so `Package.resolved` is intentionally absent.

When the declared Android dependency graph changes intentionally, regenerate
the locks only in a dedicated maintenance run by adding `--write-locks` to the
same offline four-module clean APK/AAB/lint task graph used by the release
script. Repeat that writer in a fresh process until two consecutive six-file
hash sets match, then run `build_release_artifacts.sh` twice. The normal release
script deliberately contains no `--write-locks`; it must fail rather than
silently accept a changed graph.

The builder and independent verifier each read the archived APK with `aapt2`
and the archived AAB base manifest with the AGP-pinned `bundletool 1.18.3`,
checking package, version code/name, and minimum/target SDK directly from both
artifact forms.
Current upstream JNI dependencies arrive pre-stripped; the manifest records
that native-symbol archive as unavailable instead of claiming it was retained.
This workflow does not sign, install, upload, launch, or deploy either app.
The consolidated
[1.0.0 build 24 local qualification record](docs/releases/1.0.0-build-24-local-v1.md)
defines the current release notes, compatibility matrix, migration boundary,
known limitations, rollback posture, exact artifact identity, and bounded
two-root evidence. The fixture-rich
[build 3 historical record](docs/releases/1.0.0-build-3-local-v1.md) preserves
the canonical no-device first-lineage transition and recorded-date provider
compatibility fixtures. The
[build 1 historical record](docs/releases/1.0.0-build-1-local-v1.md) preserves
its superseded archive identity, while the
[build 2 historical record](docs/releases/1.0.0-build-2-local-v1.md) preserves
its identity and historical-readback command. The
[build 4 historical record](docs/releases/1.0.0-build-4-local-v1.md) preserves
the diagnostic publication that preceded the first qualified two-root result.
The
[build 5 historical record](docs/releases/1.0.0-build-5-local-v1.md) preserves
the valid equal-length two-root qualification superseded by Build 6. The
[build 6 historical record](docs/releases/1.0.0-build-6-local-v1.md) preserves
the archive and packaged-app lifecycle evidence, while its exact standalone
two-root result bytes were not retained. The
[build 7 historical record](docs/releases/1.0.0-build-7-local-v1.md) preserves
the first compliance inventory and its documented precedence-compressed
relationship limitation superseded by Build 8. The
[build 8 historical record](docs/releases/1.0.0-build-8-local-v1.md) preserves
the first exact-role compliance qualification and its recorded repeated-run
boundary. The
[build 9 historical record](docs/releases/1.0.0-build-9-local-v1.md) preserves
the role-aware embedding source qualification and its separately bound
packaged-app lifecycle result. The
provider snapshot records official current/previous
candidates separately from local observations. Both exact Ollama candidates
passed isolated adapter health, empty-catalog, restart, and stopped-endpoint
checks from SHA-256-verified official archives. The versioned runner reproduces
that matrix on unique non-default loopback ports with temporary empty model
directories and emits a bounded canonical readback. Its explicit model-backed
mode copy-on-write snapshots one automatically selected, already-installed
unloaded chat model without retaining its name or downloading a model. Both
exact candidates pass cold-start and restart checks for populated catalog,
streamed completion, first-delta cancellation, post-cancel recovery, confirmed
unload, installed-state preservation, SHA-256 snapshot integrity, and
stopped-endpoint unavailability. A dedicated additional-shape runner then
selected the exact second of three installed completion-capable candidates,
which reports `completion`, `thinking`, and `tools` but not `vision`. Its 991
verified blobs and 213,712-byte manifest total 16,679,502,421 model-artifact
bytes; both exact versions passed cold-start and restart for 4/4 chat,
cancellation, recovery, unload, snapshot, and endpoint observations while the
observed source catalog/capabilities, running set, and selected bytes remained
unchanged. It attempted no model download and retained no model name, prompt,
output, path, process identifier, or base URL. A separate embedding-backed mode
snapshots the smallest already-installed unloaded embedding model without
retaining its name, inputs, or vector values. Both exact candidates pass cold-start and restart
checks for a two-input finite equal-dimension embedding batch, provider
residency, confirmed unload, installed-state preservation, snapshot integrity,
and stopped-endpoint unavailability. Its separate
`--embedding-backed --semantic-quality` mode evaluates 16 fixed English texts
in two permutations. Both exact candidates passed all four per-batch ranking
scenarios at the fixed 200-basis-point positive margin, all 16 repeat checks at
9,990 cosine basis points, and a fresh-provider embedding recovery. Each phase
requires exactly one matching XCTest execution, and the fixture binds the
semantic scorer and live assertion sources by SHA-256, with no retained model
name, task text, vector, or raw score. This is a bounded fixed-task
observation, not general semantic or retrieval qualification.

A separate five-locale V2 observation keeps that English V1 evidence unchanged
and predeclares the same 200-basis-point positive margin and 9,990-basis-point
repeatability threshold across `en`, `ko`, `ja`, `zh-CN`, and `fr`. Both exact
Ollama candidates completed and shape-validated both 80-text embedding
batches, passed all four English rankings, then failed the positive-margin check
at Korean scenario ordinal 2. The task set and thresholds were not changed
after observing the failure. Each candidate was stopped and reaped, then passed
a fresh ordinary embedding lifecycle recovery with confirmed unload and
unchanged source/task/snapshot bindings. The canonical V2 result retains the
failed locale and ordinal, but no model name, task text or ID, vector,
dimension, score, provider output, path, PID, or base URL. Therefore the
multilingual quality gate remains failed rather than qualified. An expected
failure is accepted only from one bounded regular UTF-8 log with exactly one
matching XCTest start/failure and one closed locale/ordinal diagnostic;
provider stop or process-group cleanup errors remain fatal. Reproduce that
bounded observation with:

```bash
python3 script/run_ollama_multilingual_semantic_matrix.py \
  --source-model-store /Users/hanchangha/.ollama/models
```

A successful runner exit means the predeclared failure and both recovery
records matched the canonical fixture; it does not mean the multilingual
quality gate passed.

The separate V3 runner completes the full five-locale matrix instead of
stopping at the first quality miss. Both exact candidates pass 76/80 ranking
comparisons and 80/80 repeatability comparisons, with identical Korean and
French scenario ordinal 2 ranking misses. Both fresh-provider recovery phases
pass and the source provider/catalog/loaded-model/selected-byte state remains
unchanged. The canonical bounded result is
[`docs/evidence/ollama-embedding-multilingual-full-matrix-v3.json`](docs/evidence/ollama-embedding-multilingual-full-matrix-v3.json),
3,570 bytes with SHA-256
`ca8279bafbe04a6de820caf1b855e4a2b6a09eb561602dd7773f1bfc190bda47`.
It records `qualityGatePassed=false`; complete observation is not a passing
quality result. Reproduce it without downloading a model with:

```bash
python3 -B script/run_ollama_multilingual_semantic_matrix_v3.py \
  --source-model-store /Users/hanchangha/.ollama/models
```

A third vision-backed mode selects the
smallest unloaded model that advertises both vision and chat/completion,
copy-on-write snapshots its exact 997 blobs plus manifest, and retains no model
name, prompt, fixed PNG bytes, or provider output. Both exact candidates pass
text chat, fixed-image attachment, first-delta cancellation, post-cancel
recovery, residency, unload, restart, snapshot-integrity, and stopped-endpoint
checks. Deterministic failure injection also proves provider stop plus snapshot
recheck after an adapter exception, temporary-root cleanup before failed-run
source readback, and rejection of provider-version plus three observed-source
drift classes; it does not claim OS-kill or power-loss behavior. An opt-in
duration path uses one `time.monotonic_ns` clock for the absolute ready/stop
budgets and observed boundaries. One dated run passed all 12
chat/embedding/vision × exact-version × cold/restart observations, with maxima
of 5,533ms ready, 54,784ms adapter, and 3ms stop. The pinned values are
single-host execution observations, not an SLA, average, percentile,
throughput, or cross-host qualification. An opt-in live fault path additionally
exercised provider unavailability before
request, process-group termination after the first non-empty chat delta, and
forced termination after `SIGSTOP` against both exact Ollama versions. All six
fault observations and six same-archive/same-snapshot adapter/unload recovery
runs passed with process-group reap, endpoint shutdown, snapshot integrity, and
source projection/byte preservation. Terminal-less stream EOF now maps to fixed
retryable `ollama_transport_error`. This bounded chat evidence does not cover
embedding/vision faults, power loss, OS crash, cleanup-permission failure,
concurrency, soak, semantic quality, or an SLA. Exact LM Studio candidate
execution remains deferred because the
official tools expose no independent user-data/model-store path for a
non-invasive run. Minimum versions, broader semantic quality, further
model-shape coverage, and full live-provider qualification remain unresolved.

For physical trusted-device development over USB, run the runtime host dev server
in one terminal:

```bash
./script/run_runtime_dev_server.sh
```

Then approve USB debugging on the phone and run:

```bash
./script/android_usb_install.sh
```

The script installs the current Android debug APK and configures `adb reverse` so the
device app connects to AetherLink Runtime at `127.0.0.1:43170`. This endpoint is
the runtime host's development transport, not Ollama or LM Studio.

To run the v0.1 USB development smoke in one terminal:

```bash
./script/android_usb_smoke.sh
```

This starts the `RuntimeDevServer`, verifies that unauthenticated
`runtime.health` and `models.list` requests fail with
`authentication_required` without exposing backend URLs or successful runtime
payloads, installs and launches the current client over USB, and then keeps the runtime
server alive. QR pairing and the physical camera scan remain manual.

Two local runtime smoke levels are available from the repository root:

```bash
# Security smoke against an already-running AetherLink/RuntimeDevServer.
python3 script/runtime_smoke_test.py 127.0.0.1 43170

# Authenticated mock E2E smoke. This starts RuntimeDevServer itself with the
# dev mock backend and a development-only pairing window.
./script/runtime_authenticated_mock_smoke.swift

# Authenticated real-local smoke. This starts RuntimeDevServer with the real
# local backend aggregate, pairs/authenticates, and validates Ollama health plus
# model list merging without pulling or generating.
./script/runtime_authenticated_mock_smoke.swift --real-ollama
```

The authenticated mock smoke is automation for the local protocol loop only:
`pairing.request`, fresh-connection `hello`/`auth.response`, `runtime.health`,
`models.list`, streamed `chat.send`, and `chat.cancel`. It uses
`AETHERLINK_DEV_PAIRING=1` and `LOCAL_AGENT_BRIDGE_MOCK_BACKEND=1`; it does not
automate the physical QR camera flow and must not be treated as production
pairing mode.

The same smoke can be routed through the temporary development relay:

```bash
./script/runtime_authenticated_mock_smoke.swift --relay
```

That command builds and starts the SwiftPM `AetherLinkRelay` in allocation
mode, starts RuntimeDevServer with relay metadata, verifies the relay fields in
development pairing info, then runs pairing, fresh authentication, model list,
streaming chat, and cancel over the relay socket.
When relay mode is enabled, frame bodies are encrypted with the same
`relay_secret` direction scheme used by the app transport.

The physical-device QR result path can also be smoke-tested over USB by
injecting the generated `aetherlink://pair` URI into the installed Android app:

```bash
JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/android_pairing_deeplink_smoke.sh --relay
```

This starts RuntimeDevServer and the development relay, installs the current
debug APK, opens the pairing deeplink on the connected device, and verifies that
the runtime receives `pairing.request` and `runtime.health` over the encrypted
relay frame path. It validates the QR result/deeplink path; it does not automate
the physical camera scan.

To smoke-test a closer different-network route, run a relay that is reachable
from both the runtime host and the Android device, then point the same Android
deeplink smoke at it:

```bash
JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" \
  ./script/android_pairing_deeplink_smoke.sh \
  --relay \
  --external-relay-host <relay-host> \
  --external-relay-port 43171
```

In this mode the script does not start a local relay and does not configure
`adb reverse` for the relay route. The Android device must reach
`<relay-host>:43171` directly through public networking, VPN, or a tunnel you
control. Loopback, `.local`, link-local, carrier-grade NAT, and private relay IP
literals are rejected for normal QR pairing because they do not prove
different-network reachability. Allocation preflight probes use `preflight=1`,
so repeated readiness checks do not persist throwaway relay leases; the runtime
still performs a normal persisted allocation when generating the actual QR.
Use `script/run_different_network_dev_runtime.sh --summary-json <path>` when
you need a machine-readable preflight report for QA; the report records the
configured relay endpoints, successful endpoint, allocation field coverage, and
the caveat that runtime-host preflight is not proof of phone-network reachability.
When a physical device is connected over USB for diagnostics, verify the device
network can open the relay TCP route before treating a pairing timeout as a QR
or app problem:

```bash
script/android_relay_reachability_probe.sh --host <relay-host> --port 43171 --json build/qa/android-relay-reachability.json
```

For the external-relay physical deeplink smoke, add
`--probe-external-relay-from-device` to run that device-side TCP probe before
the pairing URI is injected. This still does not call Ollama or LM Studio from
the device; it only checks whether the relay route in the QR is reachable from
the device network. The wrapper also passes through the Android smoke's
`--expect-chat-complete`, `--chat-complete-timeout`, `--chat-expected-terms`,
and `--chat-model-query` options so an operator-confirmed external-relay phone
run can preserve completed-chat proof in summary JSON without treating seeded
no-device wrapper self-tests as physical external-relay success.

The real-Ollama mode keeps the same development pairing/auth path, but leaves
`LOCAL_AGENT_BRIDGE_MOCK_BACKEND` unset so RuntimeDevServer talks to the local
backend aggregate. It fails by default if Ollama is unavailable; add
`--allow-unavailable` only when a local skip is intentional.

The current Android client project is rooted at `apps/android` but is also included from the repository root Gradle settings.

### Developer-Only Temporary Remote Route

Normal product flow is remote-route QR-first: configure eligible remote route
material, generate the AetherLink Runtime pairing QR, scan it from the trusted device,
and never enter Ollama, LM Studio, host, or port details on the client. Local
direct QR generation is diagnostics/development only. Current source builds do
not yet ship production P2P rendezvous or a
hardened relay allocation service. For development-only different-network
testing, run a temporary relay on a public, tunnel, or VPN-managed address that
is reachable from both peers and explicitly eligible for remote QR generation:

```bash
AETHERLINK_RELAY_ALLOCATION_TOKEN='<operator-secret>' \
  script/run_allocation_relay.sh \
  --host 0.0.0.0 \
  --port 43171 \
  --allocation-store "$HOME/.aetherlink-relay/allocations.json"
```

`AetherLinkRelay` is the SwiftPM-native development relay executable. It
requires allocation by default and rejects unknown or expired relay ids. Strict
runtime/client registration uses crypto-v2 session nonces, ephemeral P-256 keys,
and allocation-bound identity admission before the relay sends crypto-v2 ready
metadata and blindly forwards bytes in both directions. Plain three-token
`AETHERLINK_RELAY runtime|client <relay_id>` registration and plain
`AETHERLINK_RELAY ready` are available only through explicit loopback
`--allow-legacy` diagnostics. The relay does not decode AetherLink
protocol frames and never calls Ollama, LM Studio, or any other model backend.
It issues short-lived allocation tickets and persists them to
`~/.aetherlink-relay/allocations.json` by default so issued QR relay ids survive
relay process restarts during their lease; pass `--ephemeral-allocations` only
for one-shot diagnostics. The relay does not persist relay frame secrets. Use
`--allow-legacy` only for old local diagnostics that intentionally accept
arbitrary relay ids.
Accepted sockets are globally bounded, including waiting and active peers, and
every control record has an absolute read deadline. Unauthenticated relay-state
probe is loopback-only by default. Exposed probe closes without a response unless
the operator explicitly selects `--probe-policy legacy-unauthenticated` for a
temporary physical diagnostic and accepts the route-enumeration risk.
Unmatched relay rooms now have a monotonic first-registration deadline of 60
seconds by default, capped by the remaining allocation lease. Same-role
replacement inherits a live deadline rather than extending it. Registration and
readiness probes atomically expire late rooms under the matcher lock before they
can match, replace, or report readiness, independent of timer delivery. Waiting
registration returns that deadline atomically, avoiding a room-state re-read after
a counterpart can move the room active. Runtime keys and
paired-client keys that complete cryptographic relay admission may each hold at
most four unmatched waits per role-separated authenticated identity across
source addresses. Bootstrap clients without paired-client proof and explicit
legacy peers remain source-quota-only. Timeout and identity-quota rejection
close silently with source-free aggregate metrics; matched active bridges cancel
their waiting timer and remain unthrottled. Both controls are configurable with
no disable value and are development fairness guardrails, not production
identity service, per-user isolation, public-network capacity, or physical
Android proof.
Canonical accepted-socket source quotas default to 64 concurrent connections and
32 unmatched waiting peers per source. Waiting peers consume both quotas, and
active bridge sockets continue to consume source connection capacity while their
established encrypted frame forwarding is not throttled or evicted. There is no
disable value, and configuration requires twice the waiting quota to fit within
the connection quota so a shared NAT/VPN cohort retains counterpart headroom.
Each waiter removes one slot from normal admission. A socket admitted from that
reserve is counterpart-only until it immediately matches the existing opposite
role or performs an authenticated same-source waiting replacement. Probe,
allocation, cross-source replacement, and new-room attempts close it.
Before the first waiter exists, normal admission already leaves one global and
one per-source slot available; every waiting insertion then rechecks both
connection-plus-reservation bounds atomically so pre-admitted sockets cannot
strand a waiter. A candidate using per-source reserve can discharge only a
waiter owned by that same source; global-only reserve remains source-agnostic.
Quota rejections close silently and expose only source-free aggregate reasons and
metrics. These configurable values are development-relay fairness guardrails, not
per-user isolation, production capacity validation, or physical Android proof.
Allocation preflight is source-limited to 120/minute with burst 30 by default;
new allocation and paired-renewal mutations share a separate 30/minute with burst 10
bucket. At most 4096 canonical accepted IPv4/IPv6 sources are retained by default,
with one shared overflow bucket and periodic idle cleanup; capacity churn cannot
reset an exhausted source bucket. Native IPv6 scope is part of the source identity,
and malformed allocation/renewal control attempts spend source capacity before
full parsing. Shared NAT/VPN users share a source bucket. These token buckets do not throttle peer admission,
waiting rooms, active bridges, probes, or encrypted forwarding; the separate
source peer quotas above govern connection and waiting admission. They are
development-relay safeguards, not production capacity validation, and they provide
no physical Android proof. Operator-selected bursts
must fully refill within the fixed 900-second idle retention so cleanup cannot
recreate more capacity than monotonic refill would have earned.
`script/aetherlink_relay.py` is legacy-only and intentionally refuses to start
unless `--allow-legacy-no-allocation` is passed. It does not implement relay
allocation leases and must not be used for current QR pairing or
different-network validation.

Then configure the runtime app's Connection Recovery settings. Loopback,
`.local`, link-local, carrier-grade NAT, and private relay IP literals are
diagnostic/development-only and must not be presented as normal remote QR
routes. Prefer a public, VPN, tunnel, DNS, or future private-overlay route name
that both devices can reach:

1. Open AetherLink Runtime.
2. Open `Connection Recovery`.
3. Expand `Connection Setup` only if AetherLink cannot prepare connection details automatically.
4. Enter the connection address and port.
5. Save the connection details.
6. Generate the latest pairing QR and scan that QR from the trusted device app.

The connection setup panel shows whether the runtime host is connecting to the
relay, registered and waiting for the trusted device, connected through the
relay, reconnecting, or failed. If it stays waiting, the runtime reached the
relay but the client has not joined the same `relay_id` yet. If it fails, check
the connection address, port, and firewall before debugging model access.

Or start the development runtime with bootstrap relay allocation:

```bash
AETHERLINK_BOOTSTRAP_RELAY_HOST=<relay-host> AETHERLINK_BOOTSTRAP_RELAY_PORT=43171 ./script/run_runtime_dev_server.sh
```

For a single command wrapper that validates the relay settings and can also
start the local development relay process, use:

```bash
script/run_different_network_dev_runtime.sh --relay-host <relay-host> --relay-port 43171
```

Add `--start-local-relay` only when `<relay-host>:43171` really reaches this
machine from the trusted-device network, for example through a port forward,
VPN, or tunnel you control. Starting the relay on the runtime host alone is not
enough for a phone on another Wi-Fi or cellular network.

When `AETHERLINK_BOOTSTRAP_RELAY_HOST` is set, the helper and RuntimeDevServer
request an allocation from the relay before emitting a QR. Legacy
`AETHERLINK_RELAY_HOST` is still accepted, but if `AETHERLINK_RELAY_ID` and
`AETHERLINK_RELAY_SECRET` are not both supplied it is treated as an allocation
relay rather than an unallocated static route. Development pairing QR payloads
then include eligible remote route material: `relay_host`,
`relay_port`, `relay_id`, `relay_secret`, `relay_expires_at`, and `relay_nonce`,
and they no longer default to a `127.0.0.1` direct endpoint unless
`AETHERLINK_DEV_PAIRING_HOST` is explicitly set. Existing pairings created before relay setup do not gain a
remote route automatically; scan the latest QR from the same trusted runtime
identity to refresh connectivity, or pair again if the runtime no longer trusts
the device. The trusted device still connects to the paired AetherLink runtime
protocol, not to Ollama or LM Studio.
Use this only for development until production end-to-end session setup, replay
protection, NAT traversal, and hardened rendezvous are implemented.

## Verification

Repository automation is implemented in
`.github/workflows/product-quality.yml` as a bounded G7 non-security CI subset.
Pull requests run read-only macOS and Android jobs with exact product-test
allowlists and affected compilation. Pushes to `main` additionally compile the
macOS Release app and assemble/lint the unsigned Android Release APK with
strict dependency locks. The macOS job uses the supported `macos-26` image and
the exact Xcode 26.6 toolchain used by the current local verification. The
workflow does not use a device, emulator, live provider, external-network
smoke, credential, bundle/signing step, artifact upload, release publication,
or deployment environment.

Validate the workflow contract locally with:

```bash
python3 -B script/check_product_ci.py
python3 -B script/check_product_ci.py --self-test
```

The checker pins the complete reviewed workflow byte stream and separately
parses the YAML safely to validate the exact top-level/job mappings and complete
step arrays against a canonical parsed-semantic fingerprint, then validates
both job preambles plus every named step body. A pre-parse syntax-tree pass
requires one YAML document and rejects duplicate mapping keys instead of
accepting the last value; mapping keys with explicit YAML tags are also
rejected before tag resolution can create an equivalent key. Its self-test
bypasses only the byte pin for controlled mutations, then verifies the expected
semantic diagnostic, so an unrelated hash mismatch cannot conceal a broken
guard.

The macOS Status overview also supports local Runtime recovery without an app
restart. Listener and Bonjour publication startup share one explicit neutral
state; downstream route work and pairing remain unavailable until both are
ready. A listener or publication failure leaves a localized Retry action
available, and a late failure or publication stop clears stale local ownership
for same-port retry. Listener and advertisement callbacks are generation-bound
so an older attempt cannot stop its replacement. Refreshing metadata while
publication is pending replaces only that advertisement and publishes the
latest TXT data. Reentrant or concurrent advertiser replacement is serialized
before publication, a canceled timeout cannot overwrite confirmed publication,
and an immediate publication failure after asynchronous listener readiness is
still forwarded to the app. Advertisement status handlers run after the
lifecycle lock is released, so a cross-queue stop cannot deadlock behind its own
callback. The development server marks advertisement lifecycle terminal before
handling a late listener loss, preventing an already captured publish callback
from emitting stale advertising or development-pairing output. The pending
Pairing screen continues to use the neutral readiness notice. The real-loopback,
publication lifecycle, focused action, notice, localization, and compact
accessibility regressions are included in the exact 217-test CI Swift selector.

Normal negotiated AppKit termination now reaches the same Runtime model started
by the main SwiftUI scene. Before requesting startup, the app delegate weakly
records the first `@StateObject` lifecycle. `applicationShouldTerminate`
synchronously closes new Runtime request admission, cancels and retires tracked
requests, stops the model, and returns `.terminateLater`. Its bounded drain
waits for request-registration races, already submitted chat-title and
memory-summary cancellation jobs, deferred memory-summary transport
acknowledgements, the resulting persistence queue barrier, and active Runtime
chat-retention maintenance. AppKit receives exactly one affirmative reply when
that work drains or when the five-second deadline expires. Timeout permits
termination but is not proof that a non-cooperative task completed; the direct
`applicationWillTerminate` fallback can only perform synchronous `stop()`.
Repeated installation and termination callbacks remain inert, and manager
cleanup remains idempotent across listener, Bonjour, bootstrap, and pair
transports. Thirteen AppDelegate tests and eight exact Router/model termination
regressions are included in the 217/217 product selector. This is current-source
graceful-quit behavior after the immutable Build 24 snapshot, not SIGKILL,
power-loss, arbitrary asynchronous work, device, network, signing, security,
or production-release evidence.

System sleep and wake now form one reversible Runtime lifecycle transition.
The AppDelegate observes the AppKit workspace notifications, folds duplicate
or reversed events, and asks the model to suspend only a Runtime that is
starting or advertising. Suspension uses the same stop path and records the
active port; wake consumes that intent once and restarts through the existing
listener and Bonjour publication gate. Failed or already-stopped Runtime state
is not retried, pre-sleep callbacks cannot mutate the wake generation, startup
requested during sleep is deferred, and termination while suspended cannot
restart or stop the same lifecycle twice. Eight AppDelegate tests, three
model-level sleep/wake tests, and the existing model-stop and manager stop-all
regressions pass 13/13; the exact product selector passes 217/217. This is
injected deterministic current-source evidence. That sleep/wake slice does not
itself observe a physical sleep cycle, post-wake network readiness, provider
restart, asynchronous persistence flush, device, signing, security, or release
behavior.

Provider availability now also recovers without restarting AetherLink while
the Runtime is active. Runtime start and wake launch concurrent one-shot health
checks; only a provider observed as retryable-unavailable receives scoped
retries after 1, 2, 4, 8, 16, and then repeated 30-second delays. Per-provider
single-flight makes manual refresh join an in-flight check, provider rows
publish independently so a slow peer cannot block another result, and no retry
loads models or invokes unrelated catalog/chat work. Stop, sleep, failed
Runtime state, and deinitialization cancel the monitor and rotate its generation
so even a cancellation-resistant late result is ignored. Ollama and LM Studio
use a health-only five-second request bound while their ordinary data and
catalog operations retain the existing timeout. Logs are emitted only when the
reported provider status changes. LM Studio's native and compatible fallback
endpoints share one five-second health deadline rather than receiving separate
budgets.

Eight deterministic recovery regressions, one provider-scoped aggregate
regression, and the two endpoint/health-timeout regressions pass 11/11; the
exact product selector passes 217/217. This is post-Build 24 current-source
evidence with injected backoff, provider responses, and lifecycle events. It
does not relabel the immutable Build 24 archive and does not claim a live
provider process, physical sleep/wake, external network, device, signing,
security, deployment, or production-release result.

The macOS app also follows the system Reduce Motion preference for its two
custom transitions. Connection-recovery scrolling becomes immediate, and the
pairing QR expiry state changes without the app's 0.2-second animation. Native
system progress/status behavior is unchanged.

macOS status and warning surfaces also honor Increase Contrast with a fixed
light/dark palette, primary warning text, and stronger custom borders. Runtime
History selection always includes a checkmark and uses one native arrow-key
selection list instead of one Tab stop per session. Action-driven recovery and
Pairing transitions carry explicit keyboard and accessibility focus targets.
The Pairing intent survives asynchronous QR preparation, is canceled when the
screen is left, survives in-app language-driven view recreation, and the
menu-bar request has one main-window consumer. QR expiry announces once per QR
lifecycle without countdown spam. The current exact
217-test product selector and complete 186-test accessibility run pass. These
are deterministic source, unit, and render results; physical keyboard and
VoiceOver traversal remain unclaimed.

This subset intentionally does not call the mixed aggregate gate below and
does not by itself satisfy canonical G7 `PR fast` or `Merge full`. The first
hosted `main` run succeeded for baseline commit
`0f59c757d745d0b95c37c9b93aec8d354bcfef9f` in both jobs
([run 30525374687](https://github.com/hanchangha1127/AetherLink/actions/runs/30525374687)).
That run is a historical 159-test baseline and predates later commit
`53f45d4e9909dd77520a450170eb87c7d260ea89` as well as the current working-tree
follow-ups. The current 217-test Swift selector and product-copy check have
local evidence only. Test selectors limit which tests execute, while SwiftPM
and Gradle still compile their complete package/app test-source graphs.

Run these lightweight checks from the repository root before handing off changes
that touch localization, protocol schema, or platform runtime behavior:

```bash
./script/check_no_device_quality.sh
```

The no-device quality check compiles the static guard scripts, validates Android
and macOS localization, protocol schema, copy hygiene, docs hygiene, Apache 2.0
license wording, app icon assets, Android QR parser and compact-relay route
tests, targeted Android navigation tests, the macOS app product, focused macOS
localization/document extraction tests, macOS compact QR fixture generation,
trusted-route re-entry state,
runtime-owned chat history storage, archive/permanent-delete guardrails,
runtime-owned memory guardrails, runtime-mediated attachment/document/image
guardrails, Android attachment loading and composer send-policy guardrails,
vision-model attachment gating, chat/embedding model separation and persisted
model-selection guardrails, runtime-generated chat title guardrails, Android reasoning/think state
separation, and runtime reasoning/think streaming separation.
It does not require a connected phone. Because it is a no-device gate, it has
explicit caveats: it does not prove physical Android rendering on a real
handset; TalkBack or VoiceOver traversal; optical/camera QR scan reliability;
live provider-backed chat or cancel against Ollama, LM Studio, or another
runtime backend; or real different-network runtime connectivity from a phone
network without USB forwarding, loopback, or local relay shortcuts.

Run these deeper smoke checks separately when their dependencies are available:

```bash
swift test --filter RelayServerCoreTests
./script/runtime_authenticated_mock_smoke.swift --relay
swift test
```

The macOS localization check validates the five `Localizable.strings` files for
English, Korean, Japanese, Simplified Chinese, and French. It confirms the files
exist, can be linted as Apple strings property lists when `plutil` is available,
and keep the same key set and order as English without duplicate keys.

Android and macOS five-language app-language verification now covers Android
resource parity, macOS localization parity, and the shared `chat.send.locale`
handoff used by runtime-generated chat titles.
Android plural parity is locale-aware: English/default use `one/other`,
Korean, Japanese, and Simplified Chinese use `other`, and French uses
`one/many/other`.

The copy hygiene check scans user-facing Android and macOS resources plus
runtime/device-visible status strings for stale prototype wording. It blocks
regressions such as visible model-provider implementation terms, legacy
desktop-runtime wording, generic chat placeholders, or client-facing model-provider URL entry copy
where product wording should say model provider, model service, AetherLink
Runtime, trusted runtime, or runtime host.

The docs hygiene check scans current handoff docs for stale product-boundary
wording, including legacy runtime labels, hybrid runtime-vs-server wording that
could read like a cloud route, and premature production encryption claims.

Generated screenshots and XML dumps under `artifacts/` are historical unless
the latest relevant progress entry explicitly names them as fresh evidence. See
[docs/qa-evidence.md](docs/qa-evidence.md) before using an artifact as proof of
current UI, QR pairing, or route behavior.

## v0.1 Acceptance Check

Use this checklist when deciding whether a change belongs in v0.1:

- AetherLink Runtime starts and can report Ollama and LM Studio health.
- AetherLink Runtime presents pairing state and a QR code for the device app.
- The device app stores a trusted runtime record after accepted pairing.
- The device app connects to AetherLink Runtime, not to Ollama or LM Studio.
- The device app can request runtime health, list installed local models, send chat with an installed model, render streamed answer deltas, show preserved reasoning/think deltas as muted collapsible UI, and cancel an active generation. Android does not advertise or send `models.pull`.
- If no local backend models are available, the device app shows an empty model list until a model is approved and downloaded on the AetherLink Runtime host or Ollama/LM Studio reports an installed model.
- Untrusted or unauthenticated clients cannot run `runtime.health`, `models.list`, `models.pull`, `chat.send`, `chat.cancel`, `route.refresh`, chat history/title/session mutation commands, or memory list/upsert/delete commands.
- Docs and UI do not imply MCP, skills, web search, advanced memory, direct client-backend access, or future client/runtime OS targets are part of the local chat backend path.

## License

AetherLink is licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE).

## Security Baseline

Unpaired devices must not control AetherLink Runtime. Pairing uses user confirmation and persistent device identities. v0.1 includes the module boundaries and data stores for trusted devices, while the transport layer remains intentionally small so TLS/device-auth can be hardened before adding tool execution. The current docs describe the target boundary; they should not be read as a claim that production-grade transport encryption is complete.
