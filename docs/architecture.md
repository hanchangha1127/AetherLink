# AetherLink Architecture

AetherLink is a local-first Android-to-Mac AI companion. The Mac owns runtime execution and backend access. Android controls the session and renders the UI.

## System Shape

```text
Android Client
  Pairing/connection UI
  Runtime status UI
  Model picker
  Chat UI
  Local chat history
  User-managed local memory notes
  Cancel control
        |
        | authenticated JSON protocol over replaceable transport
        | local direct, remote P2P, or encrypted blind relay fallback
        v
Mac Companion Runtime
  Transport listener
  Connection manager
  Protocol router
  Trusted-device boundary
  Backend abstraction
  Model lifecycle manager
  Permission boundary for future tools
        |
        +--> Ollama Adapter -> local Ollama
        |
        +--> LM Studio Adapter -> local LM Studio server
```

There is no cloud AI backend in v0.1. Android must not call Ollama or LM Studio directly. Any future signaling, relay, or TURN-style service is connection metadata infrastructure only, not an AI backend.

## Remote Connectivity Architecture

AetherLink must not be designed around same-network fixed IPs. Smooth 1:1 connectivity should work when the Android client and Mac runtime are on different networks, while keeping AI execution local to the user's runtime. Fixed host/port values and mDNS/Bonjour service records are v0.1 development hints or local fast-path hints, not durable product addressing.

Target connection order:

1. Pairing binds device identities and public keys. The Android device trusts a specific Mac runtime identity, and the Mac trusts a specific Android identity.
2. A route resolver takes the paired peer identity and returns ordered route candidates for that identity.
3. Local direct candidates come first. These can use local discovery, mDNS/Bonjour, LAN addresses, USB reverse, hotspot, or a scanned development endpoint when available.
4. If local direct connection is unavailable, future resolver candidates should cover remote P2P NAT traversal using the paired device identities, short-lived session metadata, and authenticated key exchange.
5. If direct P2P fails, future resolver candidates may fall back to an encrypted blind relay or TURN-style path.

Current implementation status: the code has the identity-first connection target and v0.1 direct endpoint hint boundary, but remote connectivity pieces are still placeholders. It does not implement real NAT traversal, signaling, encrypted relay transport, or production end-to-end transport encryption yet. Today, direct endpoint hints are still selected for the existing local TCP transport. They are candidates, not durable product addresses. The Android resolver now wires current Bonjour/local discovery results and explicitly selected local/dev endpoints into route candidates before stale trusted last-known endpoint hints; that slice is still same-network/local-direct only, not real remote P2P or NAT traversal.

Bonjour/local discovery route candidates should carry minimal routing hints when available. The preferred hint is a pairing-derived `route_token` that Android learned from QR pairing; stable device id and fingerprint TXT values are legacy/development fallbacks rather than the production privacy target. Android may automatically route a trusted runtime identity only to discovered endpoints whose hints match the pinned trusted runtime record. Discovered endpoints without identity metadata are local/dev/manual reachability candidates only; they must not be treated as automatic trusted-identity matches.

Discovery identity hints are not secrets and must not expose backend URLs, model names, provider status, prompts, files, memory, or other runtime details. They are only pre-auth routing hints that help Android choose which local endpoint to try before the authenticated session starts. They do not replace QR pairing, pinned identity, challenge-response authentication, or end-to-end encrypted transport.

Bitcoin-network analogy note: the useful similarity is peer identity and discovery instead of a client pinned to one fixed server address. AetherLink is still a private trusted-device network, not a public untrusted open network; only QR-paired devices may discover, authenticate, and exchange runtime traffic.

The relay/signaling component, if used, is not a cloud AI service and must not receive or inspect AI protocol payloads. It can coordinate reachability, exchange connection candidates, or forward encrypted packets, but end-to-end encryption between the paired Android client and Mac runtime must prevent it from reading model lists, prompts, responses, files, memory, backend credentials, or any runtime command payload. Until that encrypted relay path exists, relay/signaling references in these docs describe the target architecture rather than implemented behavior.

Fixed IP entry, manual host/port entry, `127.0.0.1:43170`, USB reverse, and raw mDNS host records are development and diagnostics tools only. They can produce v0.1 direct route candidates, but they are not the product connectivity model. Pure mDNS/local IP discovery cannot guarantee reliable different-network connectivity because mDNS is link-local and private IPs are usually unroutable across NATs, carrier networks, VPNs, and separate Wi-Fi networks.

## Future Platform Shape

The v0.1 implementation starts with a Mac companion runtime and Android client. The long-term product direction is broader:

- Runtime/server targets: macOS first, then Windows and DGX OS-class AI workstations or servers.
- Client/controller targets: Android first, then iOS.
- Serving backends: Ollama and LM Studio first, then additional local or self-hosted AI serving systems.

The invariant stays the same as platforms expand: client apps are controllers, and model serving is mediated by a trusted runtime/server. Mobile clients should not directly call backend-specific model URLs.

## Mac Companion Runtime

The Mac runtime is responsible for:

- Starting the local runtime transport.
- Managing local direct, remote P2P, and encrypted relay/TURN-style connectivity through a replaceable connection manager.
- Receiving Android protocol messages.
- Checking runtime health.
- Listing models through backend adapters.
- Listing embedding models separately from chat/text-generation models.
- Returning installed backend models exactly as backend adapters report them, including Ollama cloud models from `/api/tags` and LM Studio local models from its Mac-side server.
- Pulling arbitrary Ollama model names through Mac-side pull requests.
- Forwarding chat requests to the active backend.
- Streaming response deltas back to Android.
- Cancelling in-flight generations.
- Managing model residency: unload the previous model before loading a newly selected model, and unload the active model after 10 or more minutes without chat activity.
- Owning trusted-device and pairing boundaries.

The runtime is also the future home for memory, file inputs, image inputs, internal Python tool execution, skills, MCP, web search, tool permissions, and audit logging.

## Android Client

The Android app is responsible for:

- Pairing/discovery UI.
- Connection status across local direct, remote P2P, and encrypted relay fallback modes.
- Model selection.
- Install action that sends model pull requests to the Mac runtime.
- Chat input and transcript rendering.
- Previous chat list and local transcript restoration.
- User-managed local memory notes that can be included as chat context.
- Streaming delta rendering.
- Cancel action.
- Displaying runtime and backend errors.

Android sends high-level protocol messages only. It does not execute tools, read files, call MCP servers, perform web search, or call local model backend URLs. Android never calls Ollama `/api/tags`, `/api/ps`, `/api/pull`, `/api/chat`, or LM Studio endpoints directly. Android-side local memory is limited to user-managed notes and chat transcripts; when enabled, those notes are included in the same `chat.send` message path through the Mac runtime.

In Korean terms: Android는 조작 화면이고, Mac companion이 실행 경계입니다. Android가 Ollama/LM Studio 서버 주소를 직접 다루는 흐름은 v0.1 제품 방향이 아닙니다.

Future image inputs and file inputs follow the same boundary: Android may capture, choose, or approve inputs in the UI, but ingestion, parsing, indexing, and backend calls run through the Mac runtime. Android must not upload files or images directly to Ollama, LM Studio, future serving backends, or research/indexing services.

## Ollama Backend Adapter

The Mac-side adapter owns:

- Health check against `localhost:11434`.
- Model list via `/api/tags`.
- Running model detection via `/api/ps` when available.
- Model install via `/api/pull`.
- Streaming chat via `/api/chat`.
- Generation cancellation abstraction.
- Structured backend errors.

The adapter is behind a backend interface so the protocol and Android UI do not depend on Ollama-specific HTTP details.

The model list is backend-derived. Local Ollama models are the main path. AetherLink does not hardcode recommended/default local or cloud Ollama models when `/api/tags` is empty. Ollama cloud models are not generic suggestions; they are selectable installed models with `source = cloud` only after the user-side Ollama pull/sign-in flow makes local Mac `/api/tags` return them. Android still sends `models.pull` and `chat.send` to the Mac runtime, and only the Mac calls Ollama `/api/pull` or `/api/chat`.

## LM Studio Backend Adapter

LM Studio support is Mac-side local backend support. It is not direct Android access, not MCP, not memory, not skills, and not web search.

The Mac-side adapter owns:

- Health check against the local LM Studio server.
- Model list via native `GET /api/v1/models`, falling back to OpenAI-compatible `GET /v1/models` if native shape differs.
- Streaming chat via native `POST /api/v1/chat`, falling back to OpenAI-compatible `POST /v1/chat/completions` when needed.
- Generation cancellation through the same runtime cancellation registry shape as other backends.
- Structured errors for unavailable server, no models, bad backend responses, and cancelled generation.

LM Studio is started by the user on the Mac from the Developer tab or with `lms server start`. Android sees only Mac runtime protocol health, model metadata, streaming deltas, and cancellation results.

## Future Serving Backend Expansion

Additional serving backends should be added behind the runtime backend interface rather than exposed directly to mobile clients. Candidate categories include local OpenAI-compatible servers, vendor workstation runtimes, multi-GPU serving stacks, and future self-hosted inference gateways. Each backend must report health, model list, streaming chat, cancellation behavior, structured errors, and capability metadata through the shared runtime protocol.

## Future Memory, Research, Skills, MCP, And Web Search Layers

These layers are not v0.1:

- Memory: Mac-side session history, SQLite/FTS, long-term facts, and later vector retrieval.
- Project workspaces: project-scoped chats, files, instructions, memories, indexes, model/backend preferences, and trusted-source controls. The Mac/runtime/server owns indexing, retrieval, research, and backend calls; Android and iOS are controllers for choosing sources, approving access, and viewing status/results.
- Scheduling and automation: user-created scheduled tasks, reminders, monitors, recurring automations, and runtime-triggered jobs. The Mac/runtime/server owns the scheduler and job runner; mobile clients provide approval, status, pause/resume, cancellation, and result review surfaces.
- Archived sessions: archive is distinct from delete. Archived chats remain retained, but they are excluded from memory, reflection, research, and compaction inputs unless the user explicitly restores them or selects them as a source.
- Session compaction: when one conversation grows beyond a model context window, the Mac runtime should compact older turns into structured summaries while preserving recent messages, user-approved memories, reasoning summaries where useful, and citations back to original transcript segments. Longer inactivity criteria should later trigger modern compact memory summaries for chat history; this is separate from the 10 minute model-unload rule.
- Embedding and research: embedding models are listed and selected separately from general text-generation/chat models. The selected embedding model is currently a setting for future retrieval features; later Mac runtime layers can use it for retrieval, ranking, knowledge indexing, semantic search over prior chats, memory clustering, source collection notebooks, research briefs, duplicate finding, and citations over indexed local/user-approved material.
- Internal Python tools: deterministic tasks such as calculations may run through a future Mac-runtime Python execution tool. Runtime-side permissions, scoping, and audit logs govern this execution; Android remains only the approval and result surface.
- Skills: permissioned executable units loaded and run by the Mac runtime.
- MCP: Mac-side MCP host/client manager with Android approval UI.
- Web search: Mac-side provider abstraction with user-configured providers.

All future layers must go through the Mac runtime permission boundary. Android remains a controller and approval surface.

Project files, project indexes, scheduled jobs, and automation definitions are sensitive runtime-controlled assets. Access to them should be explicit, scoped to the project or job, revocable, and audit logged. A scheduled job must re-enter the same permission broker as an interactive action before it reads files, uses a model backend, runs a tool, performs web search, calls MCP, or executes terminal/Python work.

## Replaceable Transport

v0.1 may use a local socket transport while the product hardens authentication, encryption, and remote connectivity. The transport must stay replaceable:

- Protocol routing is separate from socket implementation.
- Runtime commands flow through a router rather than directly through UI code.
- Pairing/auth checks can be inserted before dispatch.
- A route resolver can order candidates for the paired peer identity, next preferring current Bonjour/local discovery results before stale trusted last-known endpoint hints for the same-network/local-direct path, and later adding remote P2P NAT traversal plus encrypted blind relay/TURN-style forwarding without changing Android feature screens.
- Bonjour/local route candidates should include minimal runtime route hints when possible, preferably `route_token`. Android should auto-route a trusted runtime only when discovered route-token or legacy `device_id`/fingerprint metadata matches the pinned trusted identity. Metadata-less discovery results remain local/dev/manual candidates, not trusted identity matches.
- Relay/signaling servers carry only connection metadata or encrypted transport packets. They are not AI/cloud backends and cannot inspect AI protocol payloads, model lists, prompts, responses, files, memory, or backend credentials.
- Manual fixed endpoints, mDNS records, and same-network host/port assumptions are development-only hints.
- Current code stops at local-direct route candidates over the existing TCP transport; remote P2P NAT traversal, signaling, and encrypted relay forwarding remain unimplemented transport milestones.
- Same-network unauthenticated access remains forbidden even if discovery or pairing starts as a minimal v0.1 implementation.
