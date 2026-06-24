# AetherLink Progress And Forward Plan

Last updated: 2026-06-24 KST.

This document records what has been implemented so far and what should happen next. It is intentionally broader than the original v0.1 MVP because recent work has moved the prototype toward a more complete product shape.

## Product Boundary

The concrete remote 1:1 connection architecture is now tracked in [connection-overlay.md](connection-overlay.md).

- AetherLink is local-first.
- There is no cloud model backend, account server, production rendezvous fabric, or production relay in the current implementation.
- Client apps are controllers. Runtime/server apps mediate model access, file ingestion, future tools, future web search, future project workspaces, and future automations.
- The client must not call Ollama, LM Studio, or future serving backends directly.
- Device connectivity must be based on paired device identity and keys, not on a fixed IP address.
- Same-network discovery, mDNS/Bonjour, explicit host/port values, raw local sockets, and USB/localhost forwarding are v0.1 development hints or local fast-path transports only; they cannot satisfy different-network product connectivity by themselves.
- The intended product connection model is a paired-device private P2P overlay, closer in spirit to decentralized or distributed peer discovery in networks such as Bitcoin than to a fixed server address. This analogy is only about rendezvous, peer identity, and discovery; AetherLink must not expose a public open peer network, and only QR-paired trusted devices should be able to discover, authenticate, and communicate with each other.
- The connection manager should work across different networks with a QR-only user flow: the QR bootstraps paired identity plus private overlay/rendezvous/relay material, local direct is an opportunistic fast path when available, remote peer-to-peer NAT traversal uses STUN-like address discovery and authenticated hole punching, and an end-to-end encrypted blind relay/TURN-style path handles networks where direct peer-to-peer fails. The client user should not enter hostnames, ports, Ollama URLs, LM Studio URLs, or backend URLs.
- Optional DHT/bootstrap-peer discovery can provide short-lived rendezvous records for paired devices where practical, but it must not become a public runtime directory, account system, backend URL registry, model-logic backend, or trust authority.
- Relay/signaling infrastructure must not see AI protocol payloads, model lists, prompts, files, memory, backend credentials, or backend URLs in production.
- Current code has local-direct route-candidate plumbing, development endpoint hints, and a temporary outbound TCP relay path keyed by `relay_id` for different-Wi-Fi development testing. When QR pairing supplies `relay_secret`, the Android client and runtime host encrypt relay frame bodies before the relay forwards them. A QR that only contains runtime identity can establish trust and resolve local routes, but it cannot cross unrelated networks by itself. For QR-only remote linking, the QR must carry remote-route material such as relay or future P2P rendezvous tokens. Remote P2P NAT traversal, DHT/bootstrap rendezvous, production signaling, hardened relay allocation, replay-resistant session setup, and complete production end-to-end transport encryption remain future milestones.
- Next remote-connection increment: keep the normal user flow QR-only while making the QR production route bootstrap explicit. The QR should carry runtime identity, runtime public key or certificate fingerprint, a pairing/route token, and overlay/rendezvous/relay material for different-network routes; fixed host/port remains optional development diagnostics only.
- Current first targets are the Android client and the macOS companion runtime.
- Future targets include iOS clients and runtime/server targets on Windows and DGX OS-class systems.

## Current Workstream Coordination Notes

- Do not use GPT-5.3-Codex-Spark for this workstream. Use GPT-5.5/inherited-model subagents only when delegation is useful.
- During the latest runtime-history pass, one GPT-5.5 read-only audit subagent was used for schema/docs review and then closed.
- The user will handle commits and pushes unless they explicitly ask otherwise.

## Implemented So Far

### Repository And Documentation

- Monorepo layout exists for Android, macOS, shared protocol, docs, examples, scripts, README, LICENSE, and protocol schema.
- `docs/architecture.md`, `docs/protocol.md`, `docs/security.md`, `docs/mvp-v0.1.md`, and `docs/roadmap.md` define the runtime boundary, protocol, security model, and roadmap.
- README and protocol docs now distinguish current Android/macOS implementation targets from the OS-neutral product boundary of client app, companion runtime, and runtime host.
- Protocol schema validation exists in `packages/protocol-schema/protocol.schema.json`.
- The shared protocol schema now covers active v0.1 payload shapes, not just the envelope/type enum. The checker verifies every active message type has a payload contract and still rejects roadmap namespaces such as memory, skills, MCP, and web search from the active enum.
- Security docs record local-first threat model, trusted devices, pairing design, encryption roadmap, and why same-network unauthenticated access is forbidden.

### macOS Companion Runtime

- SwiftPM macOS companion modules exist for the app shell, protocol, transport, pairing, trusted devices, companion core, Ollama backend, LM Studio backend, and document ingestion.
- The local companion runtime server exists and is the only supported gateway for Android client runtime commands.
- Runtime message router handles authenticated runtime commands.
- Runtime health supports Ollama and LM Studio provider status through the companion runtime.
- Model listing is backend-derived and does not invent default/recommended models when backend lists are empty.
- Ollama model listing uses installed local models and can classify chat vs embedding models.
- LM Studio model listing supports local LLM and embedding models through the runtime.
- Chat requests stream deltas back to the client.
- Ollama reasoning/think chunks are preserved separately from final assistant answer text.
- LM Studio native and OpenAI-compatible streaming paths now preserve common reasoning fields such as `reasoning_content`, `reasoning_delta`, `thinking_delta`, `reasoning`, `thinking`, and `thoughts` as separate reasoning events instead of dropping them or merging them into answer text.
- Cancellation is routed by request id through the backend abstraction.
- Runtime-side model residency now unloads the previous inactive model when switching providers/models and unloads the active model after 10 minutes without chat activity.
- Ollama unload is runtime-mediated through `/api/chat` with empty messages and `keep_alive = 0`; LM Studio unload is runtime-mediated through `/api/v1/models/unload` using loaded instance ids.
- Structured errors are returned through protocol `error` envelopes.
- Document ingestion exists as a standalone runtime-side module for many text/document formats, including PDF, DOCX/DOCM/DOTX, DOC best-effort, HWPX, HWP best-effort, ODT/ODS/ODP, XLSX/XLSM, XLS best-effort, PPTX/PPTM/PPSX, PPT/PPS best-effort, EPUB, RTF, WebArchive, HTML/XHTML, Markdown, AsciiDoc, reStructuredText, text/log/config, CSV/TSV, JSON/JSONL, YAML, TOML, INI/properties, XML, and best-effort Pages/Numbers/Keynote text-bearing archives.
- `chat.suggestions.request` and `chat.suggestions.result` were added so the runtime can generate suggested next questions after an assistant response without the client directly calling any model backend.

### Development Transport, Pairing, And Trust

- Development transport uses local JSON protocol framing over the runtime transport.
- Current dev connection paths are local runtime server routes: same-network/local discovery, USB or emulator forwarding, explicit local diagnostic host/port values, and the temporary relay. They are reachability routes for the paired runtime, not the product connection model.
- Android now has a first `RuntimeConnectionManager` slice in `core/transport`.
- Android connection targets now carry paired runtime identity plus an optional endpoint hint before delegating to the existing TCP transport.
- New route-resolver milestone: a paired peer identity is now the logical connection target, and resolver output is an ordered list of route candidates for that identity rather than a single durable host/port.
- The v0.1 direct endpoint hint remains only one route candidate. Hints from QR pairing, current Bonjour/local discovery, trusted last-known records, USB reverse, emulator, or manual diagnostics are reachability candidates for the current direct TCP transport, not the product address of the runtime host.
- Android `RuntimeConnectionManager` now has injectable remote route preparation, peer-to-peer connector, and relay connector seams. This lets a future NAT traversal implementation and a future blind relay implementation plug into the same ordered route attempt flow, while the current app still ships only the direct TCP/local-development connector.
- Android transport connectors now share a `RuntimeProtocolChannel` abstraction for framed protocol send/receive/close. The existing direct TCP transport and peer socket client implement this channel, and future P2P/relay connectors must return the same channel shape instead of leaking a backend URL or a transport-specific API into chat/model code.
- Android now includes `RuntimeRelayTcpClient`, an outbound relay connector that joins a private relay room by `relay_id`, waits for `AETHERLINK_RELAY ready`, and then sends/receives length-prefixed AetherLink protocol frames. If a `relay_secret` is present, frame bodies are AES-GCM encrypted with direction-bound nonces before they leave the client.
- Android now attempts prepared remote routes, including the development relay route saved from QR pairing, before local direct routes. Future prepared P2P routes stay ahead of relay, relay now stays ahead of fresh same-network discovery, and stale trusted last-known private IP hints are fallback only. This makes the current different-network relay path the first real attempt when relay metadata exists.
- Android automatic reconnect no longer promotes a stale trusted last-known private IP address into the main product route. When there is no current discovery result or relay route, the reconnect target stays identity-first so debug USB/emulator forwarding or future P2P/relay preparation can be tried without silently falling back to an old private LAN address.
- Android connection state now records the active route kind after a successful connection, so the status UI can distinguish an active relay/P2P route from a stale saved endpoint or local diagnostic route. Relay status copy now says the encrypted relay is tried before local routes on another network.
- Android route-unavailable notices now make QR-only remote-route refresh explicit: when the runtime is already trusted, scanning a fresh remote-route QR updates the saved route instead of requiring users to delete trust or manually enter a host.
- Android first-run pairing prefers route-bearing QR payloads for immediate pairing. If a scanned QR is identity-only, the client now keeps the pending pairing state and waits for matching local discovery instead of failing before Bonjour/route discovery has time to resolve. Identity-only QR still cannot cross unrelated networks; different-network pairing or repair needs relay or future P2P rendezvous material in the QR.
- Android now distinguishes "no relay route saved" from "saved relay route failed". If a relay-backed connection attempt fails, the UI points users to the runtime's Remote Relay status and asks them to confirm that the relay host is reachable from both networks.
- Android now preserves expired remote route lease failures as `remote_route_expired` instead of flattening them into a generic connection failure. The route notice tells the user to scan the latest AetherLink Runtime QR, and expired QR pairing payloads stop retrying instead of looping on a stale relay route.
- Android accepted-pairing and route-refresh mapping now preserve QR-provided `relay_expires_at` and `relay_nonce` in the trusted runtime record, so automatic reconnect can reject stale remote route material with a clear refresh-QR path instead of silently trying an expired relay.
- Android route status and trusted-runtime settings now show the saved remote route lease. If the saved relay route has expired, the route notice becomes a warning and asks the user to scan the latest AetherLink Runtime QR instead of presenting the stale route as ready.
- Android route notices now surface the saved relay endpoint as route diagnostics for different-network debugging, while model traffic remains routed only through AetherLink Runtime.
- Android connection status now shows a distinct "Relay route saved" state when a trusted runtime has relay metadata but is not connected yet. This makes a fresh relay QR rescan visibly different from a full re-pairing and tells the user to connect through the remote route outside the local network.
- Android relay pairing now treats relay metadata as the authoritative remote route. If a QR or saved trusted runtime has `relay_host`/`relay_port`/`relay_id`, the client builds an identity-only relay target, clears stale private LAN host/port hints, ignores debug USB fallback for that relay-backed reconnect attempt, and does not persist a direct endpoint in the trusted runtime store. This prevents an old same-Wi-Fi IP or USB route from masking different-network relay behavior.
- Android reasoning output now keeps the Ollama-style thinking panel collapsed to a dim three-line preview by default, with clearer localized show/hide thinking actions and safer header layout so the action text does not crowd the label.
- Android receive-failure handling now removes an unsent blank assistant placeholder before persisting the active chat. Partial answer text or reasoning is preserved, but a relay/runtime disconnect no longer leaves an empty assistant row in chat history.
- Android chat requests now prepend a runtime capability guard system message before local memory/context. It tells the selected model that the current build does not provide live web search, browsing, MCP tools, skills, automations, Python execution, or other external tools unless explicit tool output is present, reducing false claims that roadmap capabilities are already available.
- The macOS runtime now enforces the same capability guard for `chat.send` before forwarding to Ollama or LM Studio, with deduplication when a client already sent the guard. This keeps the roadmap-feature boundary on the runtime side for future iOS/desktop clients, not only in the Android UI.
- Android no longer injects the USB reverse debug fallback into trusted-runtime reconnect unless the user explicitly selected the USB reverse diagnostic route. This prevents different-network failures from being masked as a generic localhost connection failure when the real issue is a missing relay/remote route.
- `script/run_different_network_dev_runtime.sh` starts the development runtime with relay metadata in one command and can optionally start the local relay process when the configured relay host is actually reachable from both devices.
- Client route resolution now wires current Bonjour/local discovery results and explicitly selected local/dev endpoints into route candidates before stale trusted last-known endpoint hints, while staying same-network/local-direct only. Bonjour/local candidates should carry minimal route hints when available, preferably a pairing-derived `route_token`, so the client can route a pinned trusted runtime only to matching discovered endpoints. Stable `device_id`/fingerprint TXT values are legacy/development fallbacks. Metadata-less Bonjour endpoints are not trusted identity matches and are not used as automatic or selected trusted-runtime routes; explicit USB/emulator/manual diagnostics remain the local development escape hatch. This is not real remote P2P, NAT traversal, signaling, or relay transport yet.
- Discovery identity hints are routing metadata only. They must not expose backend URLs, Ollama or LM Studio details, model inventory, provider health, prompts, files, memory, or runtime command metadata, and they do not replace QR pairing, pinned identity, challenge-response authentication, or encrypted transport.
- Android trusted runtime storage now preserves paired runtime identity even when no last-known endpoint hint is available.
- Android QR parsing accepts identity-only pairing payloads; host/port are validated only when present.
- Android QR pairing no longer fails immediately when a scanned QR contains only identity and local discovery has not emitted yet. The pending pairing remains visible as route resolution, and `connectToPendingPairingRuntimeIfNeeded()` completes pairing when a matching discovered runtime appears. Route-bearing direct/relay QR payloads still connect immediately when their route is reachable.
- While a scanned identity-only QR is waiting for route resolution, the Pairing screen keeps QR scanning available and changes the action to "Scan latest QR" so the user can replace stale/incomplete QR material with a fresh direct or relay route QR without resetting the app or deleting trust.
- Successful QR route refresh now leaves a small non-error confirmation notice in the QR pairing panel, instead of relying on a transient `route_refreshed` status that is immediately replaced by the follow-up connection attempt.
- Android pairing UI still supports route diagnostics, but the normal pairing expectation is now "scan QR -> connect through QR route -> send `pairing.request` -> persist trust"; mDNS/Bonjour is a secondary route refresh and diagnostics path, not the core first-run pairing dependency.
- Android trusted runtime writes now persist identity/key/route-token material as the source of trust. If QR pairing included a valid development/local host/port, the client also stores it as an optional last-known direct route hint for reconnect; it is still treated as a route candidate, not as the product identity or durable address.
- Android now advertises and consumes the runtime-owned chat history messages. After authentication it requests `chat.sessions.list`, merges runtime-owned session summaries into the local UI cache without deleting local-only sessions, and when a previous runtime session is opened it requests `chat.messages.list` to refresh that transcript while preserving local archive/manual-title state.
- Android now keeps local suppression records for permanently deleted runtime-owned sessions, so a server-owned chat that the user deleted from archived history does not reappear after the next `chat.sessions.list` or `chat.messages.list` sync. This is a client-side bridge until authenticated runtime archive/delete protocol messages are added.
- Authenticated runtime archive/restore/delete protocol messages now exist as `chat.session.archive`, `chat.session.restore`, and `chat.session.delete`. The macOS runtime records them as append-only session lifecycle events, hides archived/deleted sessions from default `chat.sessions.list`, allows restored sessions to reappear, and returns no transcript for deleted sessions.
- macOS `PairingSession` can still generate identity-first QR payloads for tests and compatibility, but the companion app now generates route-bearing QR payloads for normal pairing. If a remote relay route is configured and the relay client is waiting for a peer or already connected, QR includes `relay_host`/`relay_port`/`relay_id`/`relay_secret` plus `relay_expires_at`/`relay_nonce`, and omits local host/port. If no ready relay is available and the local runtime listener is advertising, QR includes the current usable local IPv4 host plus runtime port so same-network pairing does not depend on mDNS timing.
- macOS `PairingSession` can include temporary relay metadata (`relay_host`, `relay_port`, `relay_id`, optional `relay_secret`, and optional route lease fields) when a development relay is configured.
- macOS Transport now includes `RelayPeerClient`, an outbound relay client that registers the runtime side with a private `relay_id` and forwards matched client frames into the existing `LocalRuntimeMessageRouter`. With `relay_secret`, it decrypts client frame bodies and encrypts runtime response bodies without exposing AI protocol JSON to the relay.
- `RuntimeDevServer` and the SwiftUI companion model can enable the development relay from `AETHERLINK_RELAY_HOST`, `AETHERLINK_RELAY_PORT`, and optional `AETHERLINK_RELAY_ID`.
- `script/run_runtime_dev_server.sh` now generates a relay frame secret when a relay host is configured without one, and `RuntimeDevServer` no longer puts the default `127.0.0.1` development host into relay-mode pairing QR payloads unless `AETHERLINK_DEV_PAIRING_HOST` is explicitly set.
- The macOS app Status screen now exposes a Remote Relay panel. It stores a mutually reachable relay host/port, generates a relay frame secret by default, restarts the outbound relay client when the runtime is already running, and includes the relay metadata in newly generated QR pairing payloads.
- The macOS runtime now reports live Remote Relay status instead of only saved configuration: connecting, waiting for the client to join the same relay id, connected, reconnecting, failed with the relay error, or stopped. `RuntimeDevServer` prints the same lifecycle labels, so different-network failures can be separated into relay reachability, stale QR/relay id, and post-auth protocol failures.
- `AetherLinkRelay` is now the SwiftPM-native development relay executable. It listens on configurable `--host`/`--port` values, accepts the existing `AETHERLINK_RELAY runtime <relay_id>` and `AETHERLINK_RELAY client <relay_id>` handshake lines, sends `AETHERLINK_RELAY ready` after matching one runtime and one client, and blindly forwards bytes without decoding protocol frames or calling Ollama, LM Studio, or another model backend.
- `script/aetherlink_relay.py` remains as a compatibility relay for existing local scripts and smoke tests.
- `script/runtime_authenticated_mock_smoke.swift --relay` now exercises the development relay path end to end: it starts the Python relay, starts RuntimeDevServer with matching relay metadata and a relay frame secret, verifies the generated pairing info includes the relay route, then performs pairing, fresh challenge-response authentication, model list, streaming chat, and cancel over encrypted relay frame bodies.
- Android relay connection setup now applies the route timeout while waiting for the relay ready line, then removes the socket read timeout after the relay is ready so long model streams are not interrupted.
- The next remote-connection increment should preserve identity-first trust while extending QR into the only normal route bootstrap surface: pairing records the runtime identity, pinned public key/fingerprint, route token, and any overlay/rendezvous/relay material needed for different-network routing without requiring the user to scan or enter a fixed host:port.
- Runtime-side chat processing now has a Mac/server-owned JSONL event store. `chat.send` records the request, assistant deltas, reasoning deltas, completion usage, cancellation, and errors on the runtime host, with inline attachment bytes stripped before storage. Authenticated clients can query runtime-owned summaries/transcripts through `chat.sessions.list` and `chat.messages.list`, which starts moving chat processing state to the server/runtime layer instead of treating the mobile client as the source of truth.
- Runtime-owned chat history now reconstructs multi-turn transcripts from stored request/response event pairs instead of only returning the latest request. Runtime-generated chat titles are also stored as runtime metadata events, so `chat.sessions.list` can return the summarized title after the first assistant response rather than falling back to the first user prompt.
- Android now marks a newly sent chat as runtime-owned as soon as `chat.send` is sent to the authenticated runtime, then refreshes runtime session summaries after chat completion or after a generated title result. This prevents archive/delete actions made before the next reconnect from being treated as local-only history and keeps the drawer closer to the runtime host's stored session state.
- Runtime-owned session summaries now keep a neutral `New chat` title until a generated title metadata event exists, so first user prompts are not exposed verbatim as chat titles during the gap before title generation succeeds.
- QR-based pairing is implemented for the current runtime/client loop.
- Trusted runtime records persist on the client after pairing.
- The runtime can publish Keychain-backed runtime public-key/fingerprint metadata through QR pairing and accepted `pairing.result`; the client stores it with the trusted runtime and rejects pairing if the accepted runtime identity does not match the scanned QR.
- Runtime identity key persistence and deletion/rotation are covered by SwiftPM tests using isolated Keychain service/account slots, so future reset/re-pair flows can rotate the runtime identity without touching unrelated app keys.
- Runtime commands are gated behind pairing/authentication.
- Untrusted clients are rejected before runtime commands reach Ollama or LM Studio.
- Authenticated runtime commands require QR pairing and trusted-device state first, regardless of whether the current route is same-network, USB/emulator forwarding, or a manual local diagnostic endpoint.
- The development transport remains replaceable by encrypted P2P/pairing transport later. A temporary outbound TCP relay is now available for different-Wi-Fi testing, with optional pairwise frame-body encryption. Production remote P2P, NAT traversal, DHT/bootstrap signaling, relay allocation, replay protection, and full production transport encryption remain future transport work.
- Cross-network 1:1 connectivity is not solved by mDNS or fixed private IPs; it needs a connection manager that can resolve route candidates from the same paired identity, then negotiate local direct, remote P2P, and encrypted relay paths.
- Public peer-discovery ideas can inspire the design, but AetherLink discovery must be privacy-preserving:
  - do not publish stable device ids directly,
  - use rotating rendezvous tokens derived from paired-device shared secrets,
  - use DHT/bootstrap peers only for short-lived paired-device rendezvous records,
  - use STUN-like candidate discovery and authenticated hole punching before falling back to relay,
  - keep prompts, responses, files, memory, model names, and runtime commands inside the end-to-end encrypted session,
  - prevent unpaired peers from learning usable routing or runtime metadata.
  - keep relay/signaling blind to encrypted AI protocol payloads and backend details.
- Current code now prepares that direction by advertising and matching a QR-provided `route_token` before falling back to legacy device id/fingerprint matching.
- Trusted-runtime restoration now starts local discovery from the saved runtime identity even when the saved record has no usable host/port endpoint. If a later Bonjour/local candidate advertises a matching route token or legacy identity hint, the route resolver can reconnect without treating the old fixed IP as the product address.
- Trusted-runtime restoration can also use a verified QR-provided host/port as a last-known direct route hint when present, while still blocking manual attempts to connect directly to common local model backend ports such as Ollama `11434` and LM Studio `1234`.
- Relay route preparation now consumes the same trusted runtime identity and route token to prepare a different-Wi-Fi development relay candidate. It also carries `relay_secret` when present, so Android and macOS can use matching AES-GCM relay frame encryption. Actual NAT traversal, DHT/bootstrap rendezvous, production signaling, hardened relay allocation, replay-resistant session setup, and complete production E2E session encryption are still not implemented.

### Android Client

- Kotlin/Jetpack Compose client skeleton has moved beyond basic scaffold.
- First-launch/onboarding flow is oriented around pairing instead of manual backend URL entry.
- Pairing and connection/status controls live under Settings, not as primary bottom tabs.
- A tested navigation resolver keeps first-run onboarding on Pairing, moves to Chat once a trusted runtime is established, and keeps post-onboarding pairing/status management in Settings.
- Main chat UI is closer to a ChatGPT-style layout: drawer for previous chats/settings, top model selector, composer at the bottom, and cleaner empty state.
- System light/dark appearance is supported.
- App language setting supports English, Korean, Japanese, Simplified Chinese, and French, with English as the default.
- Simplified Chinese language persistence now accepts Android/resource aliases such as `zh-rCN` and script aliases such as `zh-Hans`, normalizing them to the app's Simplified Chinese option instead of falling back to system language.
- UI strings have been cleaned to avoid hardcoded Android/Mac wording where possible.
- Model and embedding pickers now display polished provider names such as Ollama, LM Studio, and Companion runtime instead of leaking raw ids like `lm_studio`; the stale `Local runtime` resource label was removed.
- Haptic feedback is used for important controls.
- Runtime connection restores from the trusted runtime record after app restart.
- Runtime connection restoration is also retried when the client app resumes, using the trusted runtime identity as the source of truth and preferring a currently discovered matching endpoint before the saved last-known endpoint.
- Explicit user disconnect is persisted locally: lifecycle resume and app restart do not silently re-enable trusted-runtime restoration until the user reconnects or pairs again.
- The Settings connection status panel now exposes whether trusted-runtime auto reconnect is enabled and explains when it is paused after an explicit disconnect.
- The Settings connection status panel now labels connectivity as a runtime route and no longer shows the development default `127.0.0.1:43170` as the apparent product endpoint before pairing; unpaired and identity-only QR states show pair/route-resolution status instead.
- Android no longer seeds a fixed development endpoint into the default UI state. USB reverse, emulator, and lab network host/port controls are developer diagnostics only: release builds hide them, and debug builds require opening Developer routes before they appear. Normal routing is presented as paired, resolving, local-discovery, saved-hint, or development route state.
- Android connection errors now surface route diagnostics without implying remote transport is already implemented: local direct can report missing or failed endpoints, while P2P and relay are explicitly labeled as not enabled in this build.
- Android connection status now includes a route-status notice that distinguishes local discovery, QR/local routes, development routes, and the temporary relay path. Relay routes warn when frame encryption material is missing and otherwise state that production P2P remains roadmap work.
- The trusted-runtime settings panel now uses the same route-label resolver as connection status, so relay-only trusted runtimes no longer appear as indefinitely resolving.
- Trusted runtime and discovered runtime rows no longer expose raw host/port as the primary user-facing route label; those details stay in diagnostics/logging paths.
- Settings now includes an explicit auto-reconnect toggle for the trusted runtime, so users can control restore behavior instead of inferring it only from connection status.
- Trusted runtime restoration no longer depends only on stale fixed endpoint hints: when local discovery later finds a runtime whose route token or legacy identity matches the saved trusted runtime, the client can automatically reconnect through the route resolver.
- Client-facing `models.result` no longer includes backend `remote_host` metadata. The runtime may use provider host fields internally to classify Ollama cloud models, but clients receive only runtime-mediated model identifiers and never backend URLs.
- Chat model picker filters out embedding models.
- Embedding models are selected separately from chat/text-generation models in Settings.
- Embedding model settings now expose an explicit "none" path, so a saved or missing embedding selection can be cleared without selecting another embedding model.
- Selected chat and embedding model ids persist locally.
- Model-list refresh reconciliation now preserves persisted chat and embedding selections across temporary backend/discovery gaps, clears selections only when a refreshed model with the same id is the wrong type, and prevents embedding-capable models from being treated as chat models.
- The Android model selector and embedding-model settings now keep showing the saved model id/name while the companion runtime is reconnecting or refreshing model lists, with localized restoring/unavailable messages so the selection does not appear to be silently cleared.
- The closed chat top-bar model pill now also shows the saved chat model name/id while the model list is restoring, instead of falling back to "Choose model" and making the persisted selection look lost.
- Android message/code copy now uses the current Compose `LocalClipboard` API instead of deprecated `LocalClipboardManager`, keeping debug builds free of that UI deprecation warning.
- Chat supports streaming answer deltas, cancellation, and structured error display.
- Reasoning/think text is shown separately as a muted compact section that can expand.
- Android reasoning/think rendering now shows a muted inline preview with a subtle rail, collapsed to about three lines by default, with tap-to-expand full reasoning.
- Reasoning visibility now covers Ollama `message.thinking` and LM Studio/OpenAI-compatible reasoning field variants. If a selected model or mock backend does not stream reasoning fields, the UI correctly has no reasoning section to show.
- Local previous chat history exists.
- New chats no longer use the first prompt verbatim as the title. After the first assistant response completes, the client asks the runtime for a concise `chat.title.request` result and applies it only while the user has not manually renamed the chat.
- The generated title is now persisted by the runtime event store as well as reflected in the Android UI cache, which moves title ownership closer to the runtime/server side.
- The Android previous-chat drawer now archives with an undo snackbar instead of making an irreversible-feeling one-tap change. Permanent delete remains hidden in Settings behind the existing two-step confirmation path.
- Archive and delete are separate chat actions: normal previous-chat rows expose archive/removal from active history, while permanent delete is reserved for archived chats.
- Dangerous bulk history operations are hidden inside Settings chat-history management and require two confirmation steps.
- Archived chats remain retained locally but are excluded from memory/research/compaction inputs unless restored or explicitly selected in a future source picker.
- User-managed local memory notes can be added, disabled, and removed; enabled notes are included only through the runtime-mediated `chat.send` path.
- File/image attachment UI is present.
- Image input is gated to vision-capable models.
- The Android attachment picker now opens document/text types by default and includes image types only when the selected chat model advertises vision/image/multimodal support.
- Android attachment chips now show image/document type and file size, and image chips visibly indicate when the selected model requires a vision-capable replacement before sending.
- Document and image attachments are sent to the runtime boundary rather than directly to a serving backend.
- The companion runtime now rejects image attachments before backend calls unless the selected model advertises `vision`, `image`, or `multimodal`; LM Studio image attachments use native `/api/v1/chat` image input first, with OpenAI-compatible chat completions as fallback when native rejects the request shape.
- Fixed centered example prompts were removed.
- AI-generated suggested next questions now use the runtime-mediated `chat.suggestions.request` path and appear as chips under the latest assistant response. Tapping a chip fills the composer for editing/sending.
- Suggested next questions now require structured JSON from the runtime model call; invalid prose/list output becomes an empty suggestion list instead of arbitrary text chips.
- Latest Android UI polish pass applied:
  - Settings now opens with preferences, embedding model, and memory first, while connection/status and advanced endpoint controls are collapsed into secondary sections.
  - The chat composer no longer shows redundant helper or placeholder text while it is already ready for input; status text is reserved for blocked/error states.
  - The top model selector says "Choose model" when no model is selected, uses refresh wording, gives the selected model more room, and now renders as a compact pill-style control next to the drawer button.
  - The top model selector now shows a compact selected/search icon so selected vs unselected model state is easier to scan without adding extra text.
  - The left drawer now includes a compact runtime/model summary below the AetherLink title, giving users current trust/connection and selected-model context before they browse chat history.
  - Settings now presents runtime/pairing status before embedding, memory, and chat-history management, keeping the runtime-mediated product boundary visible while leaving previous chats primarily in the drawer.
  - Suggested next questions render as full-width follow-up actions instead of truncated horizontal chips.
  - Empty chat copy is more user-facing and less runtime-status-first.
  - The fully ready empty chat state is intentionally quiet: it shows only a compact centered status while keeping the bottom composer as the primary action surface until a real assistant answer can produce suggested next questions.
  - The chat composer no longer renders a generic placeholder such as "Ask anything"; the empty input stays visually quiet unless a real connection/model/file warning is needed.
  - The chat composer now keeps that quiet visual surface while adding accessibility semantics for the message field and send-button readiness, so screen readers can identify the control without reintroducing visible placeholder copy.
  - The chat composer was tightened into a compact single-row control. Generic connection/model helper text is no longer rendered inside the composer; only actionable file/model warnings can appear there.
  - The chat timeline now uses quieter neutral user bubbles, a constrained assistant reading width, tighter transcript padding, and a more docked composer surface so the default chat view feels closer to a modern/classic assistant app.
  - Assistant messages no longer show repeated assistant avatars or role labels in the timeline, making the chat surface quieter and closer to a modern assistant transcript.
  - Normal chat messages no longer show always-visible copy icons; long-press copies message text while code blocks keep an explicit copy affordance.
  - Chat-bottom route availability notices now render as a compact status chip instead of a taller two-line card, so connection-route guidance does not dominate the composer area.
  - Haptic feedback now covers more high-frequency controls, including drawer opening, chat history selection, chat history menus, model menu opening, Settings navigation, and expandable Settings sections.
  - User-facing Android copy now prefers "runtime host" over "paired computer" across supported languages, keeping the UI less tied to one operating-system pairing.
  - Chat-facing install/backend/file-type messages avoid "runtime host" implementation wording where possible.
  - Android visible model-service copy now avoids user-facing "backend" wording where practical, while preserving internal keys and structured error codes for compatibility.
  - Latest physical-device UI pass keeps empty chats from rendering as a blank screen, constrains the chat transcript and composer to a centered reading width, lowers the composer surface weight, and gives QR pairing a calmer compact card treatment.
  - Android provider health summary now uses localized readiness summaries instead of raw provider-name/status strings joined by a separator. Individual provider cards still show actionable Ollama or LM Studio detail.
- Latest discovery UI pass applied:
  - Discovered runtimes now show whether their advertised identity matches the trusted runtime, is missing, is unknown, or belongs to a different trusted runtime.
  - Known mismatched discovered runtimes cannot be selected when a trusted runtime is already saved.
  - Metadata-less local/dev discovery candidates are labeled as missing advertised identity and are not used as trusted-runtime routes.
  - Matching discovered trusted runtimes can trigger restore connection attempts, while metadata-less discoveries remain manual/dev candidates only.
- macOS companion copy now describes Bonjour/local transport status as a pairing service and keeps Local Network permission language scoped to completing local pairing, rather than implying local-network discovery is the final product connectivity model.
- macOS companion UI, menu bar actions, page headers, panels, pairing instructions, trusted-device controls, and empty-state messages are routed through localization resources for English, Korean, Japanese, Simplified Chinese, and French. Remaining source-visible system image names and log parsing tokens are implementation identifiers rather than user-facing strings.
- Latest macOS companion UI polish adds an explicit Connection Routes status card that distinguishes local routes from the temporary development relay, indicates whether relay frame-body encryption is configured, and states that production different-network P2P remains roadmap work. Runtime Logs and Trusted Devices copy now use AetherLink runtime/trust-management wording instead of visible "Companion" phrasing.
- The macOS Remote Relay panel now tells users to open Pairing, generate a new QR, and have already paired clients scan it again after relay settings change. This makes the current different-network development path clearer without exposing Ollama or LM Studio directly.
- The macOS Remote Relay panel now has a direct Generate Relay QR action. It creates a fresh pairing QR and switches to Pairing so already trusted clients can rescan and refresh their remote relay route without deleting trust.
- The macOS Remote Relay panel now enables remote-route QR generation only after the relay client is waiting for a peer or already connected. Before that point, generated pairing QR payloads stay local/identity-first rather than advertising a different-network route that is not actually reachable.
- Latest route UX copy now separates a saved remote route from an actually connected relay. Android status panels say "remote route saved" until a connection is active, Android retry errors explain that the runtime host and client are waiting to meet on the relay, and macOS overview shows "Remote relay not connected yet" instead of a generic ready state while relay connectivity is still pending.
- The macOS Remote Relay panel now blocks loopback and `.local` relay hosts from the GUI, because remote client devices cannot reach them. Private-network relay hosts are allowed with an explicit warning so VPN, tunnel, or managed overlay addresses can be used when both devices can reach that address.
- The macOS Status screen now keeps QR pairing as the primary quick action, demotes route host/secret fields into a collapsed Advanced Route Settings section, and places Remote Route Diagnostics below the normal runtime/backend/model status panels.
- The macOS Pairing QR card now uses QR-only instructions and no longer exposes the embedded 6-digit protocol code as a copyable/manual-entry affordance. The code remains inside the QR/protocol payload for pairing validation.
- The macOS Pairing QR card now states whether the current QR is identity-first/local-route only or includes a configured remote relay route, including a warning when relay frame encryption material is missing.
- The macOS Pairing QR card now shows the saved remote route lease expiration embedded in a relay QR. Relay metadata is included in newly generated QR payloads only when the configured remote route is eligible and the relay is waiting or connected; otherwise the UI tells the user to wait for relay readiness and generate a new QR. Loopback and `.local` relay hosts are still blocked from QR route material because different-network clients cannot reach them.
- Latest macOS localization polish maps remaining companion/local-runtime visible values to AetherLink Runtime or runtime-host wording across English, Korean, Japanese, Simplified Chinese, and French, while retaining legacy raw log keys only for compatibility mapping.
- Latest macOS copy polish maps visible backend/local-runtime/Companion phrasing to model provider, model service, AetherLink Runtime, or runtime-host wording across English, Korean, Japanese, Simplified Chinese, and French.
- Latest macOS localization cleanup also updates Swift fallback keys and runtime-protocol error/status messages so missing localizations or client-rendered errors no longer expose stale "backend", "Companion", "companion runtime", or "this Mac" phrasing. The UI now prefers model provider/model service/AetherLink Runtime wording at the source-key level, not only in translated values.
- New macOS runtime log events now use AetherLink Runtime wording at the source. Legacy `Companion started/stopped` raw log parsing remains only as a compatibility mapping for older in-memory events, and the copy hygiene checker now blocks those stale visible fallback keys from returning.
- Latest localization fit polish shortens pairing, route, history, status, provider, and error copy across Android and macOS locales while preserving the Android client -> AetherLink Runtime -> model provider boundary.
- Android relay route labels now use product-facing "encrypted relay route" wording across supported languages while the docs still identify the current implementation as a temporary development relay.
- Fresh relay QR payloads now include `relay_expires_at` and `relay_nonce`; Android uses that relay route security material for the pending QR attempt and rejects stale first-scan route material. After pairing succeeds, Android persists the trusted runtime identity plus stable relay host/id/secret without persisting the short QR lease as the trusted route lifetime, so scan-once pairing can survive app restarts instead of expiring after the QR lease. Older relay QR payloads remain accepted for development compatibility.
- SwiftPM now includes an `AetherLinkRelay` development relay executable in addition to the Python compatibility script. It matches one runtime and one client by `relay_id`, sends the existing ready line, and blindly forwards bytes without decoding AetherLink frames or touching model providers.
- Android pairing and transport internals now use runtime-centered names for pairing payloads, trusted runtime records, discovered runtime records, transport clients, and UI state. Legacy `mac_*` QR/query and DataStore keys remain only as compatibility aliases for existing v0.1 pairings and wire payloads.
- macOS backend, pairing, and development-server status/error messages now prefer runtime-host/client wording. New pairing defaults use `AetherLink Runtime` as the display name while legacy `mac_*` protocol fields remain accepted for compatibility.
- Android chat/model-facing copy now avoids implementation-heavy phrases such as "install on runtime host" in favor of direct action labels like "Install model" and "Open the model app, then refresh health." Runtime-host wording remains in Settings, advanced endpoint controls, and security-oriented explanations where the trust boundary matters.
- Latest physical-device check installed the debug APK on a connected Samsung device and captured the dark-mode chat shell showing QR-first route refresh copy after the connection-route notice and compact composer polish. Earlier physical-device checks also verified USB-reverse runtime reconnect plus authenticated `runtime.health` and `models.list`.

### Branding And Assets

- App name is AetherLink.
- The user-provided AetherLink icon image is stored as `assets/brand/aetherlink_icon_source.png`.
- Android launcher PNGs, the adaptive icon foreground, the generated macOS iconset, and `apps/macos/LocalAgentBridgeApp/Sources/Resources/AppIcon.icns` are generated from that source.
- `assets/brand/generate_aetherlink_icons.swift` is the canonical offline regeneration script for app icon assets.
- Apache 2.0 is the intended license direction.

### Verification Already Run

- Android:
  - `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :core:pairing:testDebugUnitTest :core:transport:testDebugUnitTest :app:compileDebugKotlin :app:testDebugUnitTest`
  - `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:assembleDebug`
  - Result: passed.
- macOS:
  - `swift test`
  - Result: passed, 97 tests.
- Schema/localization/copy:
  - `python3 script/check_android_string_parity.py`
  - `python3 script/check_protocol_schema.py`
  - `python3 script/check_macos_localization.py`
  - `python3 script/check_copy_hygiene.py`
  - Result: passed.

## Current Known Limits

- The local transport is still development-grade and must be replaced or hardened with encrypted authenticated transport.
- Current development connections can look like same-network or fixed endpoint connections. This must be treated as temporary diagnostics/scaffolding, not the final product.
- Different-network 1:1 connectivity now has a user-configurable temporary development relay path, but production-grade connectivity is not complete. The relay host must be public or otherwise mutually reachable, and clients paired before relay setup must scan a fresh relay QR from the same pinned runtime identity, or pair again if runtime trust was removed. The next transport milestone must replace or harden the temporary relay with real local-direct, remote P2P NAT traversal, DHT/bootstrap discovery, and encrypted relay transports.
- The current relay smoke test confirms the relay path can carry authenticated pairing, challenge-response auth, runtime health, model list, streaming chat, and cancel generation. If a real different-Wi-Fi device still cannot connect, the first checks are whether the relay host is reachable from both networks, whether the runtime shows connected/waiting/failed in Remote Relay status, and whether the client scanned a fresh relay QR containing the current `relay_id`, `relay_secret`, `relay_expires_at`, and `relay_nonce`.
- Android can now treat a fresh QR from the same pinned runtime identity as a route refresh for an already trusted runtime. Relay QR payloads update relay host/id/secret/lease material, and direct local QR payloads update the saved direct host/port hint while clearing stale relay metadata. This lets existing trusted devices repair routes without deleting trust or depending on stale same-network private IPs, while still keeping model access behind AetherLink Runtime.
- Android relay QR pairing now keeps the scanned pending pairing payload after an initial relay connection failure and retries with bounded backoff instead of forcing the user to scan again immediately. The retry budget is long enough for the runtime host and client to meet on a relay after the scan, while still expiring when the QR route material expires or the runtime rejects pairing. Saved trusted relay routes also schedule reconnect after failed connection attempts, not only after an already-open protocol stream drops.
- Android now keeps a QR direct endpoint as a fallback when a QR payload contains both relay and direct route material. The connection manager still tries the prepared relay route first, but a bad relay route no longer blocks same-network QR pairing if the QR also carried a valid direct endpoint.
- Android trusted-runtime auto reconnect now prefers fresh Bonjour/local discovery for the pinned runtime identity, but falls back to the saved last-known direct endpoint when no current discovery route is available. This improves app-restart recovery for local/direct development routes without turning the endpoint into the trusted product identity; different-network use still requires a relay QR or future P2P overlay route.
- Android pairing QR parsing now rejects incomplete relay material such as `relay_secret` or `relay_id` without `relay_host`/`relay_port`, instead of silently downgrading the QR into identity-only local discovery. A fresh relay QR from the same pinned runtime identity can rotate the saved `route_token` when the runtime device id and key/fingerprint still match.
- DHT/bootstrap-peer discovery, STUN-like address discovery, authenticated hole punching, production TURN-style relay allocation, replay protection, and production end-to-end transport encryption are design targets only; none are implemented in the current transport.
- QR pairing exists, but production trust UX still needs certificate/public-key pinning polish and trusted-device management hardening.
- There is no cloud backend by design.
- A future relay/signaling service, if added for NAT traversal, must not become a cloud AI backend, account server, prompt store, model proxy, backend URL directory, or traffic observer for AI protocol payloads.
- Current code still has fixed-endpoint compatibility paths:
  - Android pairing store still persists legacy `mac_host` and `mac_port` keys only as optional last-known endpoint hints.
  - QR pairing and Bonjour discovery currently provide reachability endpoint hints.
  - Android route resolution prefers current Bonjour/local discovery candidates with matching route-token or legacy runtime identity hints before saved trusted last-known endpoint hints.
  - Bonjour/local endpoints without identity metadata are visible for diagnostics but are not used as trusted-runtime route candidates; explicit USB/emulator/manual diagnostic paths remain available for development.
  - Android `RuntimeConnectionManager` now delegates local direct routes to the existing TCP `connect(host, port)` implementation and prepared relay routes to the outbound relay connector. The connector boundary returns a common framed `RuntimeProtocolChannel` so future remote connectors can feed the same protocol stream.
  - macOS pairing QR can omit `host`/`port`, and can include development relay metadata when configured.
  These are now isolated behind identity, connection target, endpoint hint, and route-candidate concepts. The implemented remote path is still a development relay, not production P2P or encrypted relay. Production remote P2P, real NAT traversal, hardened relay fallback, and a full macOS-side connection-manager integration are not implemented yet.
- There is no MCP implementation.
- There is no skills runtime implementation.
- There is no web search implementation.
- There is no internal Python tool execution yet.
- Memory is still user-managed local notes and local chat history, not full long-term memory, vector memory, or automatic memory compaction.
- Runtime archive/restore/delete protocol messages now exist for the authenticated runtime store. Client and runtime lifecycle state still need richer cross-device conflict handling, archived-session listing/filtering, and UI for runtime-owned archived sessions across future clients.
- Embedding model selection exists, but embedding-powered retrieval/research is not implemented.
- File/document ingestion is runtime-side and broad, but legacy binary formats remain best-effort until dedicated parsers are added.
- Vision input depends on model capability metadata and backend adapter support; Ollama and LM Studio image inputs are mediated by their runtime adapters, with LM Studio using native image input first and OpenAI-compatible multimodal fallback when needed.
- AI-generated next-question suggestions depend on the selected chat model and can be skipped silently if suggestion generation fails or returns invalid JSON.
- Full physical-device QA still needs to cover QR re-pairing, real streaming chat, cancellation, reasoning expansion, suggested next questions, attachments, and all five app languages after the latest UI changes.
- Production packaging, signing, notarization, Play distribution, and release pipelines are not complete.

## Immediate Next Work

1. Replace the temporary relay/fixed-endpoint development assumption with a production QR-bootstrapped overlay plan:
   - define a full `ConnectionManager` abstraction on client and runtime,
   - store paired runtime identity rather than a raw host/IP as the primary connection target,
   - make QR the only normal user-facing pairing and route-refresh surface,
   - include runtime identity, public key/fingerprint, route token, and overlay/rendezvous/relay material for different-network routes,
   - keep fixed host:port only as an optional local/dev diagnostic hint,
   - try same-network discovery/direct connection as an opportunistic fast path,
   - let local discovery resolve a direct LAN endpoint from the trusted runtime identity and route token instead of from a fixed scanned address,
   - add a private P2P peer-discovery and NAT traversal implementation for different networks,
   - replace the development relay with key-bound encrypted relay allocation and forwarding,
   - use Bitcoin-like peer-network inspiration only for decentralized discovery concepts, not for public visibility or untrusted command routing,
   - add an end-to-end encrypted blind relay/TURN fallback design for networks where P2P fails,
   - keep every path behind the same pairing/authentication and backend mediation boundary.
2. Run a physical Android device QA pass:
   - install the debug build,
   - pair through QR,
   - verify reconnect after app restart,
   - load models,
   - select chat and embedding models separately,
   - stream chat,
   - cancel generation,
   - verify reasoning/think rendering,
   - verify AI-generated suggested next questions,
   - test image/document attachments,
   - check Korean/Japanese/Chinese/English/French UI strings.
3. Capture Android UI screenshots after the QA pass and continue polishing a modern/classic interface:
   - quieter transcript spacing and typography,
   - less visually noisy message actions,
   - more refined drawer and Settings surfaces,
   - model selector that feels integrated into chat,
   - small-screen behavior and touch targets,
   - consistent light/dark treatment.
4. Continue the `ConnectionManager` work:
   - expand the route resolver from v0.1 direct endpoint candidates to real remote P2P NAT traversal candidates and encrypted relay fallback candidates,
   - keep explicit source-aware endpoint hints for USB reverse, emulator, Bonjour, and manual diagnostics,
   - keep Bonjour/local TXT route hints minimal and continue auto-routing trusted runtimes only when those hints match the pinned identity,
   - keep metadata-less discovery results as local/dev/manual candidates rather than trusted identity matches,
   - add macOS-side connection-manager boundaries,
   - preserve current USB reverse, emulator, Bonjour, and dev-server flows while removing fixed IP from the normal product path.
5. Capture launcher/dock screenshots on real devices to verify the generated AetherLink icon reads correctly at small sizes.
6. Harden pairing and trusted-device UX:
   - trusted runtime details,
   - remove trusted device,
   - reconnect status,
   - error states,
   - no manual endpoint path for normal users.
7. Add production transport design:
   - TLS or Noise-style encrypted channel,
   - certificate/public-key pinning,
   - challenge-response from both sides,
   - replay protection,
   - device revocation.
8. Continue runtime resource policy polish:
   - surface model unload status in runtime logs/UI,
   - report provider-specific unload failures without breaking chat,
   - add manual unload controls when trusted-device UX is hardened.
9. Improve model capability metadata:
   - chat vs embedding vs vision,
   - context window,
   - reasoning/think support,
   - tool/Python/web/search support when those arrive.
10. Expand automated smoke tests for:
   - pairing,
   - authenticated model list,
   - streaming chat,
   - cancel generation,
   - suggested next questions,
   - attachment ingestion,
   - untrusted client rejection.

## Roadmap After Current v0.1-Plus Work

### v0.2 Session, History, And Memory Polish

- Search and rename previous chats.
- Improve archive/delete UX and make source inclusion rules explicit.
- Add Mac/runtime-side session storage where appropriate.
- Preserve final answer, reasoning/think text, attachments, suggested next questions, and usage metadata.
- Add context-window-aware session compaction:
  - detect when a session approaches or exceeds the selected model context window,
  - compact older turns into structured summaries,
  - keep recent messages raw,
  - preserve source pointers to original transcript segments.
- Add long-inactivity memory summarization:
  - define inactivity criteria separate from the 10-minute model-unload rule,
  - summarize long-unused chat history into modern compact memory summaries,
  - keep archived chats excluded unless restored or explicitly selected.

### v0.3 Embeddings And Research

- Keep embedding models separate from chat/text-generation models.
- Let the user choose one embedding model from the runtime-provided embedding list.
- Use the selected embedding model for:
  - semantic search over prior chats,
  - memory lookup,
  - duplicate detection,
  - clustering and deduplication suggestions,
  - retrieval over user-approved files,
  - deep-research-like notebooks and briefs.
- Add source snippets and citations for any research output.
- Keep indexing, retrieval, ranking, and research generation in the runtime/server layer.

### v0.4 File, Image, And Multimodal Workflows

- Route all file/image inputs through the runtime.
- Automatically expose image input when the selected model is vision-capable.
- Support broad document ingestion with chunking, metadata, and parse quality indicators.
- Add size limits, resumable transfer, and source permission prompts.
- Add project/workspace file source selection before using files as model context.

### v0.5 Permission Broker, Python Tools, And Skills

- Add a runtime-side permission broker for sensitive actions.
- Add internal Python execution for deterministic tasks such as calculations, tables, data inspection, and small scripts.
- Require approval and audit logs for Python, terminal, file, network, web search, MCP, and skills.
- Add a skill registry after the permission model exists.
- Keep mobile clients as approval/status surfaces, not execution environments.

### v0.6 Web Search

- Web search should be runtime-mediated.
- Do not rely on the client app calling search providers directly.
- Add a search provider abstraction so Ollama-provided web search, SearXNG/custom endpoints, browser-backed search, or future provider APIs can be swapped behind one runtime interface.
- Treat LM Studio web search as backend-dependent, not a universal assumption; if LM Studio does not expose equivalent search in the local server mode, AetherLink's runtime search abstraction should provide the feature independently.
- Store citation-ready metadata and source snippets.
- Require permission prompts when search is combined with project files, tools, or automation.

### v0.7 MCP

- Add runtime-side MCP server registry.
- Add scoped MCP permissions.
- Add mobile approval UI for tool calls.
- Keep MCP off the client and behind runtime trust boundaries.

### v0.8 Projects

- Add project/workspace objects similar to ChatGPT Projects:
  - project chats,
  - project files,
  - project instructions,
  - project memories,
  - project indexes,
  - project model/backend preferences.
- Add trusted-source controls for which files, folders, chats, memories, and search results may be used as context.
- Add project-level research reports with citations.
- Keep project indexing and retrieval in the runtime/server layer.

### v0.9 Scheduling And Automation

- Add runtime/server scheduler for:
  - scheduled tasks,
  - reminders,
  - monitors,
  - recurring automations,
  - runtime-triggered jobs.
- Add explicit permissions, audit logs, pause/resume/cancel, and result review.
- Require fresh approval before automations use sensitive files, tools, Python, terminal, web search, MCP, or model backends.

### v1.0 Platform Expansion

- Expand client/controller targets from Android to iOS.
- Expand runtime/server targets from macOS to Windows and DGX OS-class systems.
- Preserve the same trust boundary across platforms:
  - clients control and approve,
  - runtime/server targets mediate all model, file, tool, search, memory, and project access.
- Preserve the same device-identity connection model across all platforms so users do not manage IP addresses differently per operating system.

### v1.1 Serving Backend Expansion

- Add more serving backend adapters beyond Ollama and LM Studio.
- Normalize capability metadata across backends:
  - health,
  - installed/running models,
  - chat,
  - embeddings,
  - vision,
  - reasoning/think,
  - context window,
  - streaming,
  - cancellation,
  - structured errors.
- Never expose backend-specific local URLs to client apps.
