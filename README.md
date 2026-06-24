# AetherLink

AetherLink is a local-first client-to-runtime AI companion. A paired runtime host owns the AI runtime and backend adapters; the client app is the controller for chat, model selection, and generation control. The current implementation targets an Android client and a macOS companion runtime, but the product architecture is intentionally OS-neutral.

v0.1 is intentionally narrow. It proves one product loop:

1. Start the companion runtime on the runtime host.
2. Show a QR pairing code on the runtime host.
3. Scan and pair from the client app without entering an Ollama or LM Studio URL.
4. List installed local models through the companion runtime.
5. Send chat messages from the client app.
6. Stream responses back from the runtime host.
7. Cancel an in-flight generation.
8. Reopen previous local chats and optionally attach user-entered local memory.

There is no cloud AI backend, account server, client-side local model execution, or direct client-to-Ollama/LM Studio connection. A small outbound TCP development relay exists for different-Wi-Fi testing. When QR pairing includes `relay_secret`, relay payload frame bodies are encrypted end-to-end between the client and runtime host, while the relay still sees only `relay_id`. This is still development transport scaffolding, not a production relay, account service, model backend, or complete NAT traversal layer.

## Connectivity Direction

AetherLink should not depend on a fixed IP address or permanent same-network access. Fixed host/port values, `127.0.0.1:43170`, USB reverse, and mDNS/Bonjour local discovery are v0.1 development hints or local fast paths only. The product direction is a paired-device private P2P overlay:

1. Pair devices by QR and bind persistent device identities/keys.
2. Try local direct discovery/connection when both devices are nearby.
3. Use the temporary development relay for current different-Wi-Fi testing when explicitly configured.
4. Replace that with remote P2P NAT traversal when devices are on different networks.
5. Fall back to an end-to-end encrypted blind relay/TURN-style path only when direct P2P fails.

Bitcoin-network analogy note: AetherLink borrows only the idea that peers can be identified and discovered without depending on one fixed server address. It is not a public, untrusted, open network. Only QR-paired trusted devices should be able to discover, authenticate, and exchange runtime traffic.

Any future relay/signaling component is connection infrastructure only. It must not run AI, store or inspect AI protocol payloads, see model lists, prompts, files, memory, or backend credentials, or replace the local runtime.

Current implementation status: AetherLink has pairing, trusted runtime records, local endpoint hints, Bonjour/local discovery candidates, USB reverse/dev-server paths, a route-candidate abstraction, and a temporary outbound TCP development relay keyed by private `relay_id`. The relay path can optionally encrypt AetherLink frame bodies with `relay_secret`, but real remote P2P NAT traversal, distributed/bootstrap discovery, hardened relay allocation, replay-resistant session setup, and production end-to-end transport encryption are not complete yet.

When a QR/trusted runtime record contains relay metadata, the client tries prepared remote routes before local direct routes: future P2P first, then the current relay, then fresh local discovery and diagnostic endpoint hints. Automatic reconnect does not promote a stale last-known private IP address as the product route; it resolves the paired runtime identity through current discovery, USB/emulator development forwarding, or relay metadata instead.

## Repository Layout

```text
apps/
  android/        Current Kotlin + Jetpack Compose client/controller
  macos/          Current SwiftUI companion/runtime shell
packages/
  protocol-schema Versioned JSON protocol schema
docs/             Architecture, protocol, security, and roadmap notes
script/           Project-local macOS build/run entrypoint
```

## v0.1 Scope

- Current Android client UI: QR pairing, connection status, model picker, chat, local chat history, user-managed local memory, streaming, cancel.
- Current macOS companion UI: runtime status, QR pairing, trusted devices, local backend status, basic logs.
- Bonjour/mDNS service name: `_aetherlink._tcp.local.`
- Length-prefixed JSON protocol over a local authenticated socket.
- Ollama support through the runtime host's local adapter.
- Ollama reasoning/think stream chunks are preserved separately from final answer text and forwarded through the companion runtime as reasoning deltas.
- LM Studio support through the runtime host's local adapter. Start LM Studio's server from the Developer tab or `lms server start`; the client app still never sees or calls the LM Studio URL.
- Pairing and discovery may be simple in v0.1, but runtime commands still require a trusted-device boundary. Same-network unauthenticated access is not an acceptable architecture.
- Remote P2P NAT traversal and production encrypted relay fallback are target connectivity milestones, not current v0.1 transport capabilities.
- The current development relay can help test devices on different Wi-Fi networks. With `relay_secret`, relay payload frames are encrypted between the paired client and runtime, but the relay still lacks production-grade allocation, token rotation, replay protection, and NAT traversal.

## Model Behavior

- Installed Ollama models come from the companion runtime querying Ollama `/api/tags` on the runtime host.
- Running Ollama models may be detected by the companion runtime through `/api/ps` when available.
- Installed LM Studio models come from the companion runtime querying LM Studio's local REST API on the runtime host. The adapter prefers native `/api/v1/models` and `/api/v1/chat`, with fallback to OpenAI-compatible `/v1/models` and `/v1/chat/completions` if native endpoint shape differs.
- Local models are the main path.
- Ollama cloud models are not default recommendations or generic suggestions. They appear only after the user has completed the Ollama-side pull/sign-in flow and the runtime host's Ollama `/api/tags` response includes them.
- Cloud models returned by `/api/tags`, such as names ending in `:cloud`, are still selectable installed models because the companion runtime mediates Ollama access.
- If backend model lists are empty, the runtime returns an empty model list and does not invent recommended/default local or cloud model cards.
- Pulling a model is requested through the companion runtime with `models.pull`, which calls Ollama `/api/pull` on the runtime host for the requested Ollama model name.
- The client app never calls Ollama or LM Studio URLs directly, including `/api/tags`, `/api/ps`, `/api/pull`, or chat endpoints.

## Non-Goals

MCP, embedding-based research, advanced memory/RAG, skills, web search, file indexing, terminal execution, iOS, Windows/DGX OS runtime targets, additional serving backends, cloud sync, user accounts, and production remote connectivity infrastructure are roadmap features, not the v0.1 local chat backend path.

한국어 메모: v0.1에서 클라이언트 앱은 Ollama나 LM Studio 주소를 직접 입력하거나 호출하지 않습니다. 항상 companion runtime을 통해 모델 목록, 채팅 스트리밍, 취소 요청을 보냅니다.

## Development Notes

The macOS companion is a SwiftPM SwiftUI app and can be launched with:

```bash
./script/build_and_run.sh
```

For physical client device development over USB, run the runtime host dev server
in one terminal:

```bash
./script/run_runtime_dev_server.sh
```

Then approve USB debugging on the phone and run:

```bash
./script/android_usb_install.sh
```

The script installs the current Android debug APK and configures `adb reverse` so the
client app connects to the companion runtime at `127.0.0.1:43170`. This endpoint is
the runtime host's companion runtime, not Ollama or LM Studio.

To run the v0.1 USB development smoke in one terminal:

```bash
./script/android_usb_smoke.sh
```

This starts the `RuntimeDevServer`, verifies that unauthenticated
`runtime.health` and `models.list` requests fail with
`authentication_required` without exposing backend URLs or successful runtime
payloads, installs and launches the current Android client over USB, and then keeps the runtime
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

That command starts `script/aetherlink_relay.py`, starts RuntimeDevServer with
relay metadata, verifies the relay fields in development pairing info, then
runs pairing, fresh authentication, model list, streaming chat, and cancel over
the relay socket. When relay mode is enabled, frame bodies are encrypted with
the same `relay_secret` direction scheme used by the app transport.

The real-Ollama mode keeps the same development pairing/auth path, but leaves
`LOCAL_AGENT_BRIDGE_MOCK_BACKEND` unset so RuntimeDevServer talks to the local
backend aggregate. It fails by default if Ollama is unavailable; add
`--allow-unavailable` only when a local skip is intentional.

The current Android client project is rooted at `apps/android` but is also included from the repository root Gradle settings.

### Developer-Only Temporary Remote Route

Normal product flow is QR-first: show the AetherLink Runtime QR, scan it from
the client, and never enter Ollama, LM Studio, host, or port details on the
client. Current source builds do not yet ship production P2P rendezvous or a
hardened relay allocation service. For development-only different-network
testing, run a temporary relay on a public or otherwise mutually reachable
machine:

```bash
python3 script/aetherlink_relay.py --host 0.0.0.0 --port 43171
```

Then either configure the runtime app's advanced route diagnostics:

1. Open AetherLink Runtime.
2. Go to `Status` -> `Remote Route Diagnostics`.
3. Enter the route host and port.
4. Save the route.
5. Generate the latest QR and scan that QR from the client app.

The route diagnostics panel shows whether the runtime host is connecting to the
relay, registered and waiting for the client device, connected through the
relay, reconnecting, or failed. If it stays waiting, the runtime reached the
relay but the client has not joined the same `relay_id` yet. If it fails, check
the route host/port and firewall before debugging model access.

Or start the development runtime with relay metadata:

```bash
AETHERLINK_RELAY_HOST=<relay-host> AETHERLINK_RELAY_PORT=43171 ./script/run_runtime_dev_server.sh
```

For a single command wrapper that validates the relay settings and can also
start the local development relay process, use:

```bash
script/run_different_network_dev_runtime.sh --relay-host <relay-host> --relay-port 43171
```

Add `--start-local-relay` only when `<relay-host>:43171` really reaches this
machine from the client network, for example through a port forward, VPN, or
tunnel you control. Starting the relay on the Mac alone is not enough for a
phone on another Wi-Fi or cellular network.

When `AETHERLINK_RELAY_HOST` is set, the helper generates `AETHERLINK_RELAY_SECRET`
if it is missing. Development pairing QR payloads then include `relay_host`,
`relay_port`, `relay_id`, and `relay_secret`, and they no longer default to a
`127.0.0.1` direct endpoint unless `AETHERLINK_DEV_PAIRING_HOST` is explicitly
set. Existing pairings created before relay setup do not gain a
remote route automatically; scan the latest QR from the same trusted runtime
identity to refresh connectivity, or pair again if the runtime no longer trusts
the client device. The client still connects to the paired AetherLink runtime
protocol, not to Ollama or LM Studio.
Use this only for development until production end-to-end session setup, replay
protection, NAT traversal, and hardened rendezvous are implemented.

## Verification

Run these lightweight checks from the repository root before handing off changes
that touch localization, protocol schema, or platform runtime behavior:

```bash
python3 script/check_macos_localization.py
python3 script/check_protocol_schema.py
python3 script/check_android_string_parity.py
./script/runtime_authenticated_mock_smoke.swift --relay
swift test
```

The macOS localization check validates the five `Localizable.strings` files for
English, Korean, Japanese, Simplified Chinese, and French. It confirms the files
exist, can be linted as Apple strings property lists when `plutil` is available,
and keep the same key set and order as English without duplicate keys.

## v0.1 Acceptance Check

Use this checklist when deciding whether a change belongs in v0.1:

- The companion runtime starts the AetherLink runtime and can report Ollama and LM Studio health.
- The companion runtime presents pairing state and a QR code for the client app.
- The client app stores a trusted runtime record after accepted pairing.
- The client app connects to the companion runtime, not to Ollama or LM Studio.
- The client app can request runtime health, list installed local models, request runtime-mediated Ollama model pulls, send chat with an installed model, render streamed answer deltas, show preserved reasoning/think deltas as muted collapsible UI, and cancel an active generation.
- If no local backend models are available, the client app shows an empty model list until the user pulls an Ollama model through the companion runtime or Ollama/LM Studio reports an installed model.
- Untrusted or unauthenticated clients cannot run `runtime.health`, `models.list`, `models.pull`, `chat.send`, or `chat.cancel`.
- Docs and UI do not imply MCP, skills, web search, advanced memory, direct client-backend access, or future client/runtime OS targets are part of the local chat backend path.

## Security Baseline

Unpaired devices must not control the companion runtime. Pairing uses user confirmation and persistent device identities. v0.1 includes the module boundaries and data stores for trusted devices, while the transport layer remains intentionally small so TLS/device-auth can be hardened before adding tool execution. The current docs describe the target boundary; they should not be read as a claim that production-grade transport encryption is complete.
