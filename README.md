# AetherLink

AetherLink is a local-first client-to-runtime AI companion. A paired runtime host owns the AI runtime and backend adapters; the AetherLink device app is the controller for chat, model selection, and generation control. The current implementation has mobile-client and desktop-runtime targets, but the product architecture is intentionally OS-neutral.

v0.1 is intentionally narrow. It proves one product loop:

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

Current implementation status: AetherLink has pairing, trusted runtime records, local endpoint hints, Bonjour/local discovery candidates, USB reverse/dev-server paths, a route-candidate abstraction, and a temporary outbound TCP development relay keyed by private `relay_id`. QR-provisioned relay routes require `relay_secret`, `relay_expires_at`, and `relay_nonce`, so AetherLink frame bodies are encrypted before relay forwarding and stale QR route material can be rejected. Real remote P2P NAT traversal, distributed/bootstrap discovery, hardened relay allocation, replay-resistant session setup, and production end-to-end transport encryption are not complete yet.

Production pairing QRs are generated only when the runtime has eligible remote route material to include. Local direct QR payloads are diagnostics/development artifacts, not the product route for same-network or fixed-IP pairing. When a QR/trusted runtime record contains relay metadata, the client tries prepared remote routes before local direct routes: future P2P first, then the current relay, then fresh local discovery and diagnostic endpoint hints. Automatic reconnect does not promote a stale last-known private IP address as the product route; it resolves the paired runtime identity through current discovery, USB/emulator development forwarding, or relay metadata instead.

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
- Pulling a model is requested through AetherLink Runtime with `models.pull`, which calls Ollama `/api/pull` on the runtime host for the requested Ollama model name.
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
the device network.

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
swift run AetherLinkRelay --host 0.0.0.0 --port 43171 --require-allocation
```

`AetherLinkRelay` is the SwiftPM-native development relay executable. It
accepts the same handshake lines as the compatibility Python script:
`AETHERLINK_RELAY runtime <relay_id>` and
`AETHERLINK_RELAY client <relay_id>`. After matching one runtime and one client
with the same `relay_id`, it sends `AETHERLINK_RELAY ready\n` to both sides and
blindly forwards bytes in both directions. It does not decode AetherLink
protocol frames and never calls Ollama, LM Studio, or any other model backend.
It persists allocation tickets to `~/.aetherlink-relay/allocations.json` by
default so issued QR relay ids survive relay process restarts; pass
`--ephemeral-allocations` only for one-shot diagnostics. The relay does not
persist relay frame secrets.
`script/aetherlink_relay.py` is legacy-only and intentionally refuses to start
unless `--allow-legacy-no-allocation` is passed. It does not implement relay
allocation leases and must not be used for current QR pairing or
different-network validation.

Then configure the runtime app's advanced connection setup. Loopback,
`.local`, link-local, carrier-grade NAT, and private relay IP literals are
diagnostic/development-only and must not be presented as normal remote QR
routes. Prefer a public, VPN, tunnel, DNS, or future private-overlay route name
that both devices can reach:

1. Open AetherLink Runtime.
2. Open `Advanced Connection Setup`.
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
model-selection guardrails, runtime-generated chat title guardrails,
runtime-generated next-question guardrails, Android reasoning/think state
separation, and runtime reasoning/think streaming separation.
It does not require a connected phone.

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
handoff used by runtime-generated chat titles and follow-up suggestions.

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
- The device app can request runtime health, list installed local models, request runtime-mediated Ollama model pulls, send chat with an installed model, render streamed answer deltas, show preserved reasoning/think deltas as muted collapsible UI, and cancel an active generation.
- If no local backend models are available, the device app shows an empty model list until the user pulls an Ollama model through AetherLink Runtime or Ollama/LM Studio reports an installed model.
- Untrusted or unauthenticated clients cannot run `runtime.health`, `models.list`, `models.pull`, `chat.send`, or `chat.cancel`.
- Docs and UI do not imply MCP, skills, web search, advanced memory, direct client-backend access, or future client/runtime OS targets are part of the local chat backend path.

## License

AetherLink is licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE).

## Security Baseline

Unpaired devices must not control AetherLink Runtime. Pairing uses user confirmation and persistent device identities. v0.1 includes the module boundaries and data stores for trusted devices, while the transport layer remains intentionally small so TLS/device-auth can be hardened before adding tool execution. The current docs describe the target boundary; they should not be read as a claim that production-grade transport encryption is complete.
