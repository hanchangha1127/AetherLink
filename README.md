# AetherLink

AetherLink is a local-first client-to-runtime AI companion. A paired runtime host owns the AI runtime and backend adapters; the AetherLink device app is the controller for chat, model selection, and generation control. The current implementation has mobile-client and desktop-runtime targets, but the product architecture is intentionally OS-neutral.

For continuation in a new Codex session, read [`docs/handoff.md`](docs/handoff.md)
first. The [canonical V1 roadmap](docs/roadmap.md#canonical-v1-delivery-roadmap)
is active.

This is a personal, single-owner project. Owner identity authentication is not
required for this personal project. Direct user instruction is sufficient for
repository reads, edits, builds, tests, and G1a no-network implementation. SSH
or GPG proof of control, fourteen role-scoped approval receipts, an owner TSA,
and an external owner-governance ledger are not current prerequisites. The user
normally handles staging, commits, and pushes unless they explicitly request
otherwise.

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

The current G2 official-source preflight selects no networking library.
Unmodified Pion ICE v4.3.0 at exact commit
`1e8716372f2bb52e45bf2a7172e4fb1004251c46` is
`rejected_at_official_source_preflight_as_is` for non-uniform destination-policy
enforcement, remote ICE password logging, unbounded callback queues, and
shutdown that can wait indefinitely on a blocked callback. No Pion source was
retained, compiled, loaded, or executed, and no socket or network rung was
opened. This technical result requires no repository-owner, GitHub, SSH, or GPG
authentication; product pairing and endpoint secure-session requirements remain
separate and unchanged.

The follow-up [G2 restricted-fork rung-one portfolio](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/hardening.md)
and its exact [machine profile](docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/restricted-fork-profile.md)
compare unmodified upstream, a wrapper-only gateway, and a minimal
AetherLink-maintained fork. Only the restricted-fork shape may proceed to
preparation of a separate rung-two official-source identity and acquisition
decision; Pion and every networking library remain unselected. Its schema 1.1
design requires separate egress capability and ingress admission boundaries,
authenticated TURN TLS service identity, exact AetherLink endpoint-confirmed
pre-auth promotion, bounded session/process resources with a sticky terminal
latch, secret-free diagnostics, and a 2,500 ms close deadline. Those controls
are not implemented or runtime-verified. The future compile-only matrix remains
Android `arm64-v8a` and macOS `arm64`, followed by later SBOM, license, patch,
symbol, and reproducibility evidence. The validator and all 17 mutation tests
pass, but no actual backend, reliable ordered carrier, or
fragmentation/reassembly implementation has been selected or built.

G2 restricted-fork rung-one status contract:
`status=rung1_profile_complete_candidate_not_selected`,
`result=pion_restricted_fork_profile_ready_for_rung2_decision_only`, and
`nextAction=prepare_versioned_rung2_source_identity_and_acquisition_decision`.
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
