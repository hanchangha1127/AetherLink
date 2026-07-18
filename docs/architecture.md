# AetherLink Architecture

AetherLink is a local-first AI companion built around a client device and a runtime host. The runtime host owns execution and backend access. The client device controls the session and renders the UI. The current v0.1 implementation has mobile-client and desktop-runtime targets.

## System Shape

```text
Client Device
  Pairing/connection UI
  Runtime status UI
  Model picker
  Chat UI
  Local chat cache
  Runtime-owned user memory notes
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
  Chat processing event store
  Backend abstraction
  Model lifecycle manager
  Permission boundary for future tools
        |
        +--> Ollama Adapter -> local Ollama
        |
        +--> LM Studio Adapter -> local LM Studio server
```

There is no cloud AI backend in v0.1. The client device must not call Ollama or LM Studio directly. Any future signaling, relay, or TURN-style service is connection metadata infrastructure only, not an AI backend.

## Hot-Path Efficiency Invariants

- Relay frame cryptography treats epoch material as immutable derived state. Each send/receive direction caches only its current epoch key and epoch-bound AAD prefix; sequence-specific nonce and AAD suffixes are still rebuilt for every frame, and counters advance only after successful encryption or authentication.
- The macOS pairing timeline owns expiry presentation only. QR rasterization is cached by the exact compact payload, so layout alternatives and one-second countdown updates cannot regenerate unchanged pairing bytes.
- Android length-prefixed protocol reads allocate the validated exact body size once and fill that destination across fragmented `InputStream` reads. Frame bounds and EOF failure remain codec-owned.
- SQLite chat append transactions continue to decode and validate the complete durable event log. Only after that fail-closed pass does indexing group validated events and refresh the affected owner/session keys, leaving unrelated FTS rows untouched.
- The macOS localization layer resolves one immutable resource bundle per supported language while selecting the current language and string on every lookup. A runtime language change therefore changes the next lookup without repeating `.lproj` discovery.
- Relay bridges receive into one reusable 64 KiB buffer and send its valid raw prefix directly. Android relay protocol frames keep the existing send mutex and 1 MiB body ceiling while the four-byte prefix and body are written separately; relay write failure already closes the channel. Direct Android transport retains one complete-frame write because its existing failure policy leaves the socket open.
- Android local persistence retains immediate save timing. Every save re-reads the latest persisted pending secret reference so interleaved store instances remove the current handle, while one sanitized projection strips runtime-owned data before the write.
- Aggregate no-device suites are executable evidence units. Once a complete test class has run, named class selectors are traceability metadata rather than additional executions; copy hygiene requires each retained Android selector to be unique and to name an actual Kotlin `@Test` method.

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

Current implementation status: the code has the identity-first connection target, a v0.1 direct endpoint hint boundary, and a temporary outbound TCP relay path for development different-network testing. It does not implement real NAT traversal, decentralized signaling, hardened relay allocation, or production end-to-end transport encryption yet. Direct endpoint hints remain diagnostics/local fast paths, not durable product addresses. The current client resolver wires QR-provisioned relay material, Bonjour/local discovery results, USB/emulator forwarding, and explicitly selected local/dev endpoints into route candidates, but it no longer promotes stale trusted last-known private IPs as automatic reconnect routes.

Bonjour/local discovery route candidates should carry minimal routing hints when available. The preferred hint is a pairing-derived `route_token` that the client learned from QR pairing; stable device id and fingerprint TXT values are legacy/development fallbacks rather than the production privacy target. The client may automatically route a trusted runtime identity only to discovered endpoints whose hints match the pinned trusted runtime record. Discovered endpoints without identity metadata are local/dev/manual reachability candidates only; they must not be treated as automatic trusted-identity matches.

Discovery identity hints are not secrets and must not expose backend URLs, model names, provider status, prompts, files, memory, or other runtime details. They are only pre-auth routing hints that help the client choose which local endpoint to try before the authenticated session starts. They do not replace QR pairing, pinned identity, challenge-response authentication, or end-to-end encrypted transport.

Bitcoin-network analogy note: the useful similarity is peer identity and discovery instead of a client pinned to one fixed server address. AetherLink is still a private trusted-device network, not a public untrusted open network; only QR-paired devices may discover, authenticate, and exchange runtime traffic.

The relay/signaling component, if used, is not a cloud AI service and must not receive or inspect AI protocol payloads. It can coordinate reachability, exchange STUN-like connection candidates, allocate TURN-like relay paths, or forward encrypted packets, but end-to-end encryption between the paired client device and runtime host must prevent it from reading model lists, prompts, responses, files, memory, backend credentials, or any runtime command payload. Until that encrypted relay path exists, relay/signaling references in these docs describe the target architecture rather than implemented behavior.

Fixed IP entry, manual host/port entry, `127.0.0.1:43170`, USB reverse, and raw mDNS host records are development and diagnostics tools only. They can produce v0.1 direct route candidates, but they are not the product connectivity model and should not be presented as normal onboarding. Pure mDNS/local IP discovery and raw local sockets cannot guarantee reliable different-network connectivity because mDNS is link-local and private IPs are usually unroutable across NATs, carrier networks, VPNs, and separate Wi-Fi networks.

### Connectivity Implementation Status

| Capability | Current Status | Implementation Notes |
| --- | --- | --- |
| Client persistent keypair | Implemented | The client uses a persistent client identity and signs runtime challenges. |
| Runtime persistent keypair | Partially implemented | The current desktop runtime can create a Keychain-backed P-256 identity key and expose its public key/fingerprint in QR pairing metadata. Production encrypted transport still needs to bind sessions to this key. |
| QR trusted-device pairing | Implemented for v0.1 | QR pairing creates a trusted client/runtime record and can carry runtime public-key metadata, identity-first route data, remote-route material, and optional development endpoint hints. |
| Runtime command authentication | Implemented for v0.1 | Runtime commands are rejected until pairing and challenge-response authentication succeed. |
| Local direct endpoint hints | Implemented as development/local fast path | USB reverse, emulator, Bonjour/local discovery, explicitly scoped diagnostic QR host/port, and manual diagnostics can produce direct TCP route candidates. These hints are not persisted as normal trusted reconnect routes and are not a solution for unrelated networks. |
| Identity-first reconnect | Partially implemented | The client treats paired runtime identity as the primary target and starts local discovery when restoring a trusted runtime, even if a stable endpoint is not available. |
| Route-token matched local discovery | Partially implemented | Bonjour/local discovery can advertise a pairing-derived route token; the client only auto-routes discovered runtimes whose route hints match the trusted runtime record. |
| Production encrypted transport | Not implemented | The active transport remains development TCP. TLS or Noise-style encryption bound to paired identities is required. |
| Remote P2P NAT traversal | Interface scaffolded, transport not implemented | `PeerToPeer` route candidates and connector injection are modeled so a future NAT traversal transport can be attempted by the same connection manager. Client transport connectors return a common framed `RuntimeProtocolChannel`, so a future P2P connector can feed the same protocol stream as direct TCP. Actual STUN-like address discovery, authenticated hole punching, replay protection, and session-key binding to paired identities are not implemented. |
| DHT/bootstrap peer discovery | Not implemented | Future bootstrap or DHT-like discovery may publish only short-lived rendezvous records derived from paired-device secrets. It must not expose stable public runtime directories or backend URLs. |
| Signaling service | Not implemented | Future signaling may exchange only reachability metadata, never AI protocol payloads. |
| Encrypted blind relay/TURN fallback | Development relay implemented, production relay not complete | `Relay` route candidates, a QR-provisioned TCP relay client, relay allocation, and AES-GCM frame-body encryption exist for development testing. It is not yet the production blind relay/TURN design, and NAT traversal plus hardened session encryption remain future work. |
| QR-only normal onboarding | In progress | Normal UX is QR/trusted-runtime oriented and must support different-network route bootstrap through overlay/rendezvous/relay material. Compatibility paths keep host/port hints only for explicit development diagnostics. |

## Future Platform Shape

The v0.1 implementation starts with one runtime target and one client target. The long-term product direction is broader:

- Runtime host targets: macOS first, then Windows and DGX OS-class AI workstations or servers.
- Client device targets: Android first, then iOS.
- Serving backends: Ollama and LM Studio first, then additional local or self-hosted AI serving systems.

The invariant stays the same as platforms expand: client apps are controllers, and model serving is mediated by a trusted runtime host. Client devices should not directly call backend-specific model URLs.

## Runtime Host

The runtime host is responsible for the following. In v0.1, this role is implemented by AetherLink Runtime:

- Starting the local runtime transport.
- Managing local direct, remote P2P, and encrypted relay/TURN-style connectivity through a replaceable connection manager.
- Receiving client protocol messages.
- Checking runtime health.
- Assigning non-authorizing assistant-message locators to attribution-bearing successful answers and atomically storing private historical bindings containing only `source_index`, `source_anchor_id`, `document_id`, and `source_revision`. Authenticated attribution review resolves only owner-scoped canonical history, then separately revalidates current `runtime_shared` approval and that exact historical revision before preparing the existing trusted-source review; approval state and a separate chunk identifier are not stored in the binding, and display metadata is never an authority lookup key.
- Listing models through backend adapters.
- Treating provider model catalogs as untrusted input: validating model identity and context-window metadata before either protocol publication or runtime compaction use.
- Listing embedding models separately from chat/text-generation models.
- Returning installed backend models with the exact identities and metadata accepted by backend-adapter validation while keeping normal client chat selection focused on installed runtime-host-local chat models.
- Pulling arbitrary Ollama model names through runtime-host-side pull requests.
- Forwarding chat requests to the active backend, including runtime-side context compaction before the backend call when the accepted chat payload is too large.
- Streaming response deltas back to the client.
- Cancelling in-flight generations.
- Managing model residency: unload the previous model before admitting a newly selected model, and unload the active model after the persisted host-local 5, 10, or 30 minute idle policy elapses. Ten minutes remains the default. Per-model unload operations serialize same-model provider dispatch, cancelled waiters cannot acquire residency, and host policy changes pass through one ordered update queue. Only provider-confirmed or already-absent outcomes clear runtime residency; unsupported or unconfirmed attempts retain a structured failure. The macOS host projects transient `Unloading` and `Needs attention` states without adding them to the client wire contract.
- Owning trusted-device and pairing boundaries.

The runtime is also the home for runtime-owned memory, current document/image attachment ingestion, model capability checks, and future internal Python tool execution, skills, MCP, web search, tool permissions, and audit logging.

## Client Device

The client device is responsible for the following. In v0.1, this role is implemented by the mobile client app:

- Pairing/discovery UI.
- Connection status across local direct, remote P2P, and encrypted relay fallback modes.
- Model selection.
- Install action that sends model pull requests to the runtime host.
- Chat input and transcript rendering.
- Previous chat list, local transcript cache restoration, and authenticated runtime-owned history restoration through `chat.sessions.list` / `chat.messages.list`.
- Runtime-owned user memory notes that can be included as chat context.
- Streaming delta rendering.
- Cancel action.
- Displaying runtime and backend errors.

The client sends high-level protocol messages only. It does not execute tools, read files, call MCP servers, perform web search, or call local model backend URLs. The client never calls Ollama `/api/tags`, `/api/ps`, `/api/pull`, `/api/chat`, or LM Studio endpoints directly. Client-side storage is limited to UI continuity cache; user memory is synchronized through the trusted runtime. Current clients do not serialize memory entries as `chat.send` prompt context. Before backend chat calls, the runtime injects enabled memory entries from its own store and removes any stale compatibility `Runtime user memory:` context. When a `chat.send` payload exceeds a known model-window budget, the runtime preserves mandatory context and recent client-visible turns, compacts only an oldest contiguous prefix, and may replace the bounded deterministic fallback with a same-model backend-only LLM summary. Runtime-only context stays out of user-visible chat history: the runtime records accepted client-visible messages, streamed deltas, reasoning deltas, completion, cancellation, and error state, while filtering capability guards, runtime memory prompt context, and compaction summaries from stored or returned transcripts. This keeps request/stream/done/cancel/error state from being owned only by the mobile client without exposing internal system prompts as chat content or altering the client-visible transcript.

In Korean terms: client device는 조작 화면이고, runtime host가 실행 경계입니다. 현재 구현은 mobile client와 desktop runtime host 대상입니다. client가 Ollama/LM Studio 서버 주소를 직접 다루는 흐름은 v0.1 제품 방향이 아닙니다.

Current file and image attachment paths follow the same boundary: the client may capture, choose, or approve inputs in the UI, but ingestion, parsing, model capability checks, indexing, and backend calls run through the runtime host. Image attachments require a vision/image/multimodal-capable model before the runtime forwards image bytes. Document ingestion is runtime-side and can expand to chunking/indexing later. The client must not upload files or images directly to Ollama, LM Studio, future serving backends, or research/indexing services.

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

The model list is backend-derived. Local Ollama models are the main path. AetherLink does not hardcode recommended/default local or cloud Ollama models when `/api/tags` is empty. Cloud/source metadata can remain in protocol data for compatibility, but normal client chat selection stays focused on installed runtime-host-local chat models. The client still sends `models.pull` and `chat.send` to the runtime host, and only the runtime host calls Ollama `/api/pull` or `/api/chat`.

Ollama catalog and running-state JSON is untrusted. `/api/tags`, `/api/ps`, and `/api/show` are streamed through a 4 MiB response ceiling that rejects an oversized positive `Content-Length` before body ingestion and stops at the first byte above the limit. They then reject malformed JSON and duplicate or escape-equivalent object names before DTO decoding. `/api/tags` and `/api/ps` each admit at most 256 rows, and their combined unique identities admit at most 256 bounded `/api/show` lookups. Cancellation is rechecked and propagated through that detail loop and through the aggregate backend instead of being treated as an unavailable detail or partial provider result. Catalog entries must have one unambiguous byte identity: exact duplicates, byte-exact canonical `:latest` duplicates, disagreeing `name`/`model` aliases, more than 512 Unicode code points in an identity field, a provider-qualified id above 522 code points, more than 32 capabilities, or a blank/exact-byte-duplicate/over-128-code-point capability fail closed without truncation. NFC/NFD-distinct identities and capabilities remain distinct rather than being merged by Swift canonical string equality. Blank-only uses one fixed Unicode code-point set shared with Android and schema, including U+200B and U+FEFF. Numeric context-window aliases from direct fields and `model_info` decode as `Decimal` and are retained only when `NSDecimalRound` plus exact equality proves every value is mathematically integral, positive, no greater than 16,777,216, and mutually equal; digit-only `parameters` `num_ctx` values remain exact. This rejects precision-rounded near-ceiling aliases while preserving exact integral decimal and scientific forms. A structurally malformed, oversized, or duplicate-key show response excludes that model from the result; invalid or conflicting context metadata in an otherwise trusted Ollama show response omits only the context value and preserves its validated capability classification.

## LM Studio Backend Adapter

LM Studio support is runtime-host-side local backend support. It is not direct client access, not MCP, not memory, not skills, and not web search.

The runtime-host-side adapter owns:

- Health check against the local LM Studio server.
- Model list via native `GET /api/v1/models`, falling back to OpenAI-compatible `GET /v1/models` only when the native endpoint returns 404, 405, or 501.
- Streaming chat via native `POST /api/v1/chat`, falling back to OpenAI-compatible `POST /v1/chat/completions` only for an explicit pre-stream native HTTP 400, 404, 405, 422, or 501 incompatibility response.
- Generation cancellation through the same runtime cancellation registry shape as other backends.
- Structured errors for unavailable server, no models, bad backend responses, and cancelled generation.

In the current desktop runtime implementation, LM Studio is started by the user from the Developer tab or with `lms server start`. The client sees only runtime protocol health, model metadata, streaming deltas, and cancellation results.

LM Studio native and OpenAI-compatible catalog JSON crosses the same untrusted boundary. Both catalog endpoints use the true streaming 4 MiB ceiling, admit at most 256 rows, and reject duplicate or escape-equivalent object names, exact or NFC-equivalent duplicate identities, byte-distinct `key`/`id` aliases, over-512-code-point identity fields, more than 32 capabilities, blank/exact-byte-duplicate/over-128-code-point capability values, and non-integral, nonpositive, over-ceiling, precision-rounded, or mutually inconsistent context aliases after `Decimal` decoding. Native unload lookup repeats byte-exact `key`/`id` agreement and catalog-wide exact/NFC uniqueness before selecting a target. Native `loaded_instances` state also admits at most 256 unique, nonblank, at-most-512-code-point identifiers per model before unload dispatch; the same validation runs during initial lookup and every verification poll, and acknowledgement identity is byte-exact, so provider metadata cannot create unbounded, duplicate, or canonically substituted POST fanout. Native catalog fallback to `GET /v1/models` is permitted only for HTTP 404, 405, or 501; an oversized or malformed native response, transport/auth failure, or other client or server error fails closed without fallback. Invalid LM Studio context metadata rejects that catalog rather than using the Ollama-specific omission behavior. A native chat stream completes only after explicit `chat.end` observed in the main loop or emitted by `parser.finish()`; malformed partial output and clean EOF after a delta terminate with an error and never trigger a second OpenAI-compatible provider dispatch. Across both providers, `ModelInfo` and the router revalidate the 256-row and metadata ceilings, serialize size as exact signed `Int64`, and encode the complete envelope before wire publication. A plaintext body above 1,048,560 bytes fails before the relay's 16-byte authentication tag can exceed the 1 MiB frame. An injected non-nil invalid value rejects the whole published catalog, while only genuinely absent metadata or Ollama's validated context-only omission leaves runtime chat compaction on its conservative legacy fallback.

The public `models.list` router path adds a host-wide single-flight boundary above those provider adapters. Up to eight concurrent public waiters share one provider catalog operation; a ninth receives a sanitized retryable `backend_unavailable`. Each waiter owns its request id, authentication generation, exact auth session, transport binding, trusted-device key, and tracked request-task publication check. A canceled non-last waiter returns immediately without stopping the shared operation, last-waiter cancellation stops provider work, and a canceled provider flight must retire before replacement so repeated cancellation cannot overlap scans. Completed and failed results are not cached. Internal authority model-catalog lookups remain outside this public coalescing path and therefore retain fresh security decisions.

## Future Serving Backend Expansion

Additional serving backends should be added behind the runtime backend interface rather than exposed directly to client devices. Candidate categories include local OpenAI-compatible servers, vendor workstation runtimes, multi-GPU serving stacks, and future self-hosted inference gateways. Each backend must report health, model list, streaming chat, cancellation behavior, structured errors, and capability metadata through the shared runtime protocol.

## Future Memory, Research, Skills, MCP, And Web Search Layers

These layers are not v0.1:

- Memory: runtime-host-side long-term facts, SQLite/FTS search, and later vector retrieval. Narrow runtime-owned chat history retrieval already exists through authenticated chat history messages; richer memory extraction/search remains future work.
- Project workspaces: project-scoped chats, files, instructions, memories, indexes, model/backend preferences, and trusted-source controls. The runtime host owns indexing, retrieval, research, and backend calls; client devices are controllers for choosing sources, approving access, and viewing status/results.
- Scheduling and automation: user-created scheduled tasks, reminders, monitors, recurring automations, and runtime-triggered jobs. The runtime host owns the scheduler and job runner; client devices provide approval, status, pause/resume, cancellation, and result review surfaces.
- Archived sessions: archive is distinct from delete. Archived chats remain retained, but they are excluded from memory, reflection, research, and compaction inputs unless the user explicitly restores them or selects them as a source.
- Session compaction: known model windows use conservative byte/framing/image accounting, a hard input budget, and adaptive oldest-prefix compaction in `chat.send`; missing model metadata retains the legacy character heuristic. The runtime can run a bounded same-model summary prepass, keeps its output in an untrusted assistant role, discards reasoning, propagates cancellation only from the connection that owns the active request, rejects colliding active request ids, and falls back to the deterministic summary on failure. Successful primary completion may commit that generated text to a separate owner-only SQLite cache keyed by bounded source fingerprint, full storage-safe conversation lineage, owner/session, the actually resolved provider model, and summary policy. Exact full-lineage hits skip the prepass; a verified strict-prefix lineage may evolve the prior summary from separately labeled untrusted prior-summary and newly compacted-delta input. Edit, reorder, deletion, scope mismatch, cancellation, error, or non-fitting output fails closed without publishing stale derived content, and session deletion purges the rows. Current v3 event metadata separately content-binds the request identity, storage-safe compacted prefix, and pointer ranges with a canonical SHA-256 fingerprint while keeping cache lineage and summary text out of the chat event store and search; append-only terminal resolution distinguishes planned upper bounds from effective dispatched estimates and undispatched cancellation. When a provider completion reports actual input usage, bounded generation-scoped one-shot source lookup preserves every existing stream enum case and the resolution may retain `provider_usage_calibration_v1`, bound to the router-resolved provider-qualified model and Ollama chat, LM Studio native, or LM Studio OpenAI-compatible wire mode. Event-store validation recomputes its relation to the conservative estimate and hard input budget; an actual budget exceedance or mismatched one-shot source prevents generated-summary cache commit. The OpenAI-compatible path explicitly waits for its post-finish usage-only chunk. Missing usage, cancellation, error, and legacy records remain compatible. This post-dispatch evidence does not change pre-dispatch decisions, auto-tune policy, or establish provider-tokenizer parity. Event stores bind each resolution to the preceding owner/session/request-scoped adaptive v3 request and reject estimator or budget mismatches on append and reopen. V1/v2, legacy v3 summary policy, and resolution-free records remain readable. Neither summary form rewrites client-visible history, and archived or deleted chats are excluded. Exact provider-tokenizer parity and richer automatic policy calibration remain future work.
- Compaction calibration inspection: the runtime host can aggregate only revalidated `provider_usage_calibration_v1` terminal records into a bounded local report keyed by exact provider, provider model id, wire mode, and estimator revision. It considers the newest 1,000 fully eligible records, retains at most 32 groups, exposes only relation counts, and marks 20 samples as `ready_for_review` while any hard-budget exceedance remains a warning. JSONL uses a 64 MiB/50,000-line/4 MiB-record reverse-tail ceiling; SQLite uses a 50,000-terminal scan plus at most 1,000 indexed normalized-owner and exact-session/request lookups. Scan or binding incompleteness, duplicate terminals, deterministic estimate drift, and malformed calibration fail closed. The macOS host loads this report off the main actor and clears stale content on failure. The report has no owner/session/request/event identifiers, timestamps, prompt or summary content, protocol projection, Android state, provider probe, or automatic policy consumer.
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
- A route resolver can order candidates for the paired peer identity, preferring QR-provisioned remote route material and current Bonjour/local discovery results over diagnostic direct endpoints, and later adding remote P2P NAT traversal plus production encrypted blind relay/TURN-style forwarding without changing client feature screens.
- Bonjour/local route candidates should include minimal runtime route hints when possible, preferably `route_token`. The client should route a trusted runtime only when discovered route-token or legacy `device_id`/fingerprint metadata matches the pinned trusted identity. Metadata-less Bonjour discovery results are diagnostics only, not trusted identity matches or selected trusted-runtime routes.
- Relay/signaling servers carry only connection metadata or encrypted transport packets. They are not AI/cloud backends and cannot inspect AI protocol payloads, model lists, prompts, responses, files, memory, or backend credentials.
- Manual fixed endpoints, mDNS records, and same-network host/port assumptions are development-only hints.
- Current code has local-direct route candidates and a temporary outbound TCP relay path; remote P2P NAT traversal, decentralized/bootstrap signaling, and production encrypted relay forwarding remain unfinished transport milestones.
- Same-network unauthenticated access remains forbidden even if discovery or pairing starts as a minimal v0.1 implementation.
