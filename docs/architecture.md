# AetherLink Architecture

AetherLink is a local-first AI companion built around a client device and a runtime host. The runtime host owns execution and backend access. The client device controls the session and renders the UI. The current v0.1 implementation targets an Android client and a macOS runtime.

## System Shape

```text
Client Device
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
Runtime Host
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

There is no cloud AI backend in v0.1. The client device must not call Ollama or LM Studio directly. Any future signaling, relay, or TURN-style service is connection metadata infrastructure only, not an AI backend.

## Remote Connectivity Architecture

See [connection-overlay.md](connection-overlay.md) for the concrete phased design for paired identity, local direct routing, distributed or decentralized rendezvous/bootstrap/DHT options where possible, remote NAT traversal, and blind encrypted relay fallback.

AetherLink must not be designed around same-network fixed IPs. Smooth 1:1 connectivity should work when the client device and runtime host are on different networks, while keeping AI execution local to the user's runtime host. Pairing and route refresh are QR-only from the user's perspective; the QR bootstraps private per-user overlay, rendezvous, and relay material so the user never enters network endpoints. Fixed host/port values and mDNS/Bonjour service records are v0.1 development hints or local fast-path hints, not durable product addressing.

Target connection order:

1. Pairing binds device identities and public keys. The client device trusts a specific runtime identity, and the runtime host trusts a specific client identity.
2. A route resolver takes the paired peer identity plus QR-bootstrapped overlay state and returns ordered route candidates for that identity.
3. Local direct candidates are opportunistic fast paths when available. These can use local discovery, mDNS/Bonjour, LAN addresses, USB reverse, hotspot, or a scanned development endpoint.
4. Different-network resolver candidates use remote P2P NAT traversal with paired device identities, short-lived session metadata, STUN-like address discovery, authenticated hole punching, and authenticated key exchange.
5. If direct P2P fails, resolver candidates fall back to an encrypted blind relay or TURN-style path.

Future peer discovery can use a DHT-like or bootstrap-peer layer, but only as a privacy-preserving rendezvous fabric for paired identities. Where practical, rendezvous should be distributed or decentralized rather than pinned to one fixed service. Bootstrap peers may help a client and runtime host find each other's short-lived reachability records, but they must not become accounts, a directory of public runtime hosts, a backend URL registry, a cloud control plane, or an authority that grants trust. Trust comes only from QR pairing, pinned peer identity, challenge-response authentication, and the encrypted session.

Current implementation status: the code has the identity-first connection target and v0.1 direct endpoint hint boundary, but remote connectivity pieces are still placeholders. It does not implement real NAT traversal, signaling, encrypted relay transport, or production end-to-end transport encryption yet. Today, direct endpoint hints are still selected for the existing local TCP transport. They are candidates, not durable product addresses. The current Android resolver wires Bonjour/local discovery results and explicitly selected local/dev endpoints into route candidates before stale trusted last-known endpoint hints; that slice is still same-network/local-direct only, not real remote P2P or NAT traversal.

Bonjour/local discovery route candidates should carry minimal routing hints when available. The preferred hint is a pairing-derived `route_token` that the client learned from QR pairing; stable device id and fingerprint TXT values are legacy/development fallbacks rather than the production privacy target. The client may automatically route a trusted runtime identity only to discovered endpoints whose hints match the pinned trusted runtime record. Discovered endpoints without identity metadata are local/dev/manual reachability candidates only; they must not be treated as automatic trusted-identity matches.

Discovery identity hints are not secrets and must not expose backend URLs, model names, provider status, prompts, files, memory, or other runtime details. They are only pre-auth routing hints that help the client choose which local endpoint to try before the authenticated session starts. They do not replace QR pairing, pinned identity, challenge-response authentication, or end-to-end encrypted transport.

Bitcoin-network analogy note: the useful similarity is peer identity and discovery instead of a client pinned to one fixed server address. AetherLink is still a private trusted-device network, not a public untrusted open network; only QR-paired devices may discover, authenticate, and exchange runtime traffic.

The relay/signaling component, if used, is not a cloud AI service and must not receive or inspect AI protocol payloads. It can coordinate reachability, exchange STUN-like connection candidates, allocate TURN-like relay paths, or forward encrypted packets, but end-to-end encryption between the paired client device and runtime host must prevent it from reading model lists, prompts, responses, files, memory, backend credentials, or any runtime command payload. Until that encrypted relay path exists, relay/signaling references in these docs describe the target architecture rather than implemented behavior.

Fixed IP entry, manual host/port entry, `127.0.0.1:43170`, USB reverse, and raw mDNS host records are development and diagnostics tools only. They can produce v0.1 direct route candidates, but they are not the product connectivity model and should not be presented as normal onboarding. Pure mDNS/local IP discovery and raw local sockets cannot guarantee reliable different-network connectivity because mDNS is link-local and private IPs are usually unroutable across NATs, carrier networks, VPNs, and separate Wi-Fi networks.

### Connectivity Implementation Status

| Capability | Current Status | Implementation Notes |
| --- | --- | --- |
| Client persistent keypair | Implemented | Android uses a persistent client identity and signs runtime challenges. |
| Runtime persistent keypair | Partially implemented | The macOS runtime can create a Keychain-backed P-256 identity key and expose its public key/fingerprint in QR pairing metadata. Production encrypted transport still needs to bind sessions to this key. |
| QR trusted-device pairing | Implemented for v0.1 | QR pairing creates a trusted client/runtime record and can carry runtime public-key metadata, identity-first route data, remote-route material, and optional development endpoint hints. |
| Runtime command authentication | Implemented for v0.1 | Runtime commands are rejected until pairing and challenge-response authentication succeed. |
| Local direct endpoint hints | Implemented as development/local fast path | USB reverse, emulator, Bonjour/local discovery, pairing QR host/port, and manual diagnostics can produce direct TCP route candidates. This is the current v0.1 local/dev route, not the intended final connection design or a solution for unrelated networks. |
| Identity-first reconnect | Partially implemented | The client treats paired runtime identity as the primary target and starts local discovery when restoring a trusted runtime, even if a stable endpoint is not available. |
| Route-token matched local discovery | Partially implemented | Bonjour/local discovery can advertise a pairing-derived route token; the client only auto-routes discovered runtimes whose route hints match the trusted runtime record. |
| Production encrypted transport | Not implemented | The active transport remains development TCP. TLS or Noise-style encryption bound to paired identities is required. |
| Remote P2P NAT traversal | Interface scaffolded, transport not implemented | `PeerToPeer` route candidates and connector injection are modeled so a future NAT traversal transport can be attempted by the same connection manager. Android transport connectors return a common framed `RuntimeProtocolChannel`, so a future P2P connector can feed the same protocol stream as direct TCP. Actual STUN-like address discovery, authenticated hole punching, replay protection, and session-key binding to paired identities are not implemented. |
| DHT/bootstrap peer discovery | Not implemented | Future bootstrap or DHT-like discovery may publish only short-lived rendezvous records derived from paired-device secrets. It must not expose stable public runtime directories or backend URLs. |
| Signaling service | Not implemented | Future signaling may exchange only reachability metadata, never AI protocol payloads. |
| Encrypted blind relay/TURN fallback | Interface scaffolded, transport not implemented | `Relay` route candidates and fallback connector injection are modeled so a future blind relay transport can be attempted after direct/P2P paths fail and return the same `RuntimeProtocolChannel` abstraction. No relay allocation, forwarding, or production encryption exists yet. |
| QR-only normal onboarding | In progress | Normal UX is QR/trusted-runtime oriented and must support different-network route bootstrap through overlay/rendezvous/relay material. Compatibility paths still preserve host/port hints for v0.1 development and diagnostics. |

## Future Platform Shape

The v0.1 implementation starts with one companion runtime target and one client target. The long-term product direction is broader:

- Runtime host targets: macOS first, then Windows and DGX OS-class AI workstations or servers.
- Client device targets: Android first, then iOS.
- Serving backends: Ollama and LM Studio first, then additional local or self-hosted AI serving systems.

The invariant stays the same as platforms expand: client apps are controllers, and model serving is mediated by a trusted runtime host. Client devices should not directly call backend-specific model URLs.

## Runtime Host

The runtime host is responsible for the following. In v0.1, this role is implemented by the macOS companion runtime:

- Starting the local runtime transport.
- Managing local direct, remote P2P, and encrypted relay/TURN-style connectivity through a replaceable connection manager.
- Receiving client protocol messages.
- Checking runtime health.
- Listing models through backend adapters.
- Listing embedding models separately from chat/text-generation models.
- Returning installed backend models exactly as backend adapters report them, including Ollama cloud models from `/api/tags` and LM Studio local models from the runtime-host-side server.
- Pulling arbitrary Ollama model names through runtime-host-side pull requests.
- Forwarding chat requests to the active backend.
- Streaming response deltas back to the client.
- Cancelling in-flight generations.
- Managing model residency: unload the previous model before loading a newly selected model, and unload the active model after 10 or more minutes without chat activity.
- Owning trusted-device and pairing boundaries.

The runtime is also the future home for memory, file inputs, image inputs, internal Python tool execution, skills, MCP, web search, tool permissions, and audit logging.

## Client Device

The client device is responsible for the following. In v0.1, this role is implemented by the Android app:

- Pairing/discovery UI.
- Connection status across local direct, remote P2P, and encrypted relay fallback modes.
- Model selection.
- Install action that sends model pull requests to the runtime host.
- Chat input and transcript rendering.
- Previous chat list and local transcript restoration.
- User-managed local memory notes that can be included as chat context.
- Streaming delta rendering.
- Cancel action.
- Displaying runtime and backend errors.

The client sends high-level protocol messages only. It does not execute tools, read files, call MCP servers, perform web search, or call local model backend URLs. The client never calls Ollama `/api/tags`, `/api/ps`, `/api/pull`, `/api/chat`, or LM Studio endpoints directly. Client-side local memory is limited to user-managed notes and chat transcripts; when enabled, those notes are included in the same `chat.send` message path through the runtime host.

In Korean terms: client device는 조작 화면이고, runtime host가 실행 경계입니다. 현재 구현에서는 Android가 client이고 macOS companion이 runtime host입니다. client가 Ollama/LM Studio 서버 주소를 직접 다루는 흐름은 v0.1 제품 방향이 아닙니다.

Future image inputs and file inputs follow the same boundary: the client may capture, choose, or approve inputs in the UI, but ingestion, parsing, indexing, and backend calls run through the runtime host. The client must not upload files or images directly to Ollama, LM Studio, future serving backends, or research/indexing services.

## Ollama Backend Adapter

The runtime-host-side adapter owns:

- Health check against `localhost:11434`.
- Model list via `/api/tags`.
- Running model detection via `/api/ps` when available.
- Model install via `/api/pull`.
- Streaming chat via `/api/chat`.
- Generation cancellation abstraction.
- Structured backend errors.

The adapter is behind a backend interface so the protocol and client UI do not depend on Ollama-specific HTTP details.

The model list is backend-derived. Local Ollama models are the main path. AetherLink does not hardcode recommended/default local or cloud Ollama models when `/api/tags` is empty. Ollama cloud models are not generic suggestions; they are selectable installed models with `source = cloud` only after the user-side Ollama pull/sign-in flow makes the runtime host's local `/api/tags` return them. The client still sends `models.pull` and `chat.send` to the runtime host, and only the runtime host calls Ollama `/api/pull` or `/api/chat`.

## LM Studio Backend Adapter

LM Studio support is runtime-host-side local backend support. It is not direct client access, not MCP, not memory, not skills, and not web search.

The runtime-host-side adapter owns:

- Health check against the local LM Studio server.
- Model list via native `GET /api/v1/models`, falling back to OpenAI-compatible `GET /v1/models` if native shape differs.
- Streaming chat via native `POST /api/v1/chat`, falling back to OpenAI-compatible `POST /v1/chat/completions` when needed.
- Generation cancellation through the same runtime cancellation registry shape as other backends.
- Structured errors for unavailable server, no models, bad backend responses, and cancelled generation.

In the current macOS runtime implementation, LM Studio is started by the user from the Developer tab or with `lms server start`. The client sees only runtime protocol health, model metadata, streaming deltas, and cancellation results.

## Future Serving Backend Expansion

Additional serving backends should be added behind the runtime backend interface rather than exposed directly to client devices. Candidate categories include local OpenAI-compatible servers, vendor workstation runtimes, multi-GPU serving stacks, and future self-hosted inference gateways. Each backend must report health, model list, streaming chat, cancellation behavior, structured errors, and capability metadata through the shared runtime protocol.

## Future Memory, Research, Skills, MCP, And Web Search Layers

These layers are not v0.1:

- Memory: runtime-host-side session history, SQLite/FTS, long-term facts, and later vector retrieval.
- Project workspaces: project-scoped chats, files, instructions, memories, indexes, model/backend preferences, and trusted-source controls. The runtime host owns indexing, retrieval, research, and backend calls; client devices are controllers for choosing sources, approving access, and viewing status/results.
- Scheduling and automation: user-created scheduled tasks, reminders, monitors, recurring automations, and runtime-triggered jobs. The runtime host owns the scheduler and job runner; client devices provide approval, status, pause/resume, cancellation, and result review surfaces.
- Archived sessions: archive is distinct from delete. Archived chats remain retained, but they are excluded from memory, reflection, research, and compaction inputs unless the user explicitly restores them or selects them as a source.
- Session compaction: when one conversation grows beyond a model context window, the runtime host should compact older turns into structured summaries while preserving recent messages, user-approved memories, reasoning summaries where useful, and citations back to original transcript segments. Longer inactivity criteria should later trigger modern compact memory summaries for chat history; this is separate from the 10 minute model-unload rule.
- Embedding and research: embedding models are listed and selected separately from general text-generation/chat models. The selected embedding model is currently a setting for future retrieval features; later runtime-host layers can use it for retrieval, ranking, knowledge indexing, semantic search over prior chats, memory clustering, source collection notebooks, research briefs, duplicate finding, and citations over indexed local/user-approved material.
- Internal Python tools: deterministic tasks such as calculations may run through a future runtime-host Python execution tool. Runtime-side permissions, scoping, and audit logs govern this execution; the client remains only the approval and result surface.
- Skills: permissioned executable units loaded and run by the runtime host.
- MCP: runtime-host-side MCP host/client manager with client approval UI.
- Web search: runtime-host-side provider abstraction with user-configured providers.

All future layers must go through the runtime-host permission boundary. The client remains a controller and approval surface.

Project files, project indexes, scheduled jobs, and automation definitions are sensitive runtime-controlled assets. Access to them should be explicit, scoped to the project or job, revocable, and audit logged. A scheduled job must re-enter the same permission broker as an interactive action before it reads files, uses a model backend, runs a tool, performs web search, calls MCP, or executes terminal/Python work.

## Replaceable Transport

v0.1 may use a local socket transport while the product hardens authentication, encryption, and remote connectivity. The transport must stay replaceable:

- Protocol routing is separate from socket implementation.
- Runtime commands flow through a router rather than directly through UI code.
- Pairing/auth checks can be inserted before dispatch.
- A route resolver can order candidates for the paired peer identity, next preferring current Bonjour/local discovery results before stale trusted last-known endpoint hints for the same-network/local-direct path, and later adding remote P2P NAT traversal plus encrypted blind relay/TURN-style forwarding without changing client feature screens.
- Bonjour/local route candidates should include minimal runtime route hints when possible, preferably `route_token`. The client should route a trusted runtime only when discovered route-token or legacy `device_id`/fingerprint metadata matches the pinned trusted identity. Metadata-less Bonjour discovery results are diagnostics only, not trusted identity matches or selected trusted-runtime routes.
- Relay/signaling servers carry only connection metadata or encrypted transport packets. They are not AI/cloud backends and cannot inspect AI protocol payloads, model lists, prompts, responses, files, memory, or backend credentials.
- Manual fixed endpoints, mDNS records, and same-network host/port assumptions are development-only hints.
- Current code stops at local-direct route candidates over the existing TCP transport; remote P2P NAT traversal, signaling, and encrypted relay forwarding remain unimplemented transport milestones.
- Same-network unauthenticated access remains forbidden even if discovery or pairing starts as a minimal v0.1 implementation.
