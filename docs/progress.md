# AetherLink Progress And Forward Plan

Last updated: 2026-06-24 KST.

This document records what has been implemented so far and what should happen next. It is intentionally broader than the original v0.1 MVP because recent work has moved the prototype toward a more complete product shape.

## Product Boundary

The concrete remote 1:1 connection architecture is now tracked in [connection-overlay.md](connection-overlay.md).

- AetherLink is local-first.
- There is no cloud backend, account server, or relay in the current architecture.
- Client apps are controllers. Runtime/server apps mediate model access, file ingestion, future tools, future web search, future project workspaces, and future automations.
- The client must not call Ollama, LM Studio, or future serving backends directly.
- Device connectivity must be based on paired device identity and keys, not on a fixed IP address.
- Same-network discovery, mDNS/Bonjour, explicit host/port values, and USB/localhost forwarding are v0.1 development hints or local fast-path transports only.
- The intended product connection model is a paired-device private P2P overlay, closer in spirit to peer discovery in networks such as Bitcoin than to a fixed server address. This analogy is only about peer identity and discovery; AetherLink must not expose a public open peer network, and only QR-paired trusted devices should be able to discover, authenticate, and communicate with each other.
- The connection manager should work across different networks: local direct connection first, remote peer-to-peer NAT traversal with STUN-like address discovery and authenticated hole punching second, and an end-to-end encrypted blind relay/TURN-style fallback only when direct peer-to-peer fails.
- Optional DHT/bootstrap-peer discovery can provide short-lived rendezvous records for paired devices, but it must not become a public runtime directory, account system, backend URL registry, or trust authority.
- Relay/signaling infrastructure must not see AI protocol payloads, model lists, prompts, files, memory, backend credentials, or backend URLs.
- Current code has local-direct route-candidate plumbing and development endpoint hints only. Remote P2P NAT traversal, DHT/bootstrap rendezvous, signaling, encrypted blind relay transport, and production end-to-end transport encryption are placeholders/future milestones, not implemented capabilities.
- Next remote-connection increment: QR pairing should be identity-only by default. The QR should carry runtime identity, runtime public key or certificate fingerprint, and a pairing/route token, while host/port remain optional development reachability hints rather than required product addressing.
- Current first targets are the Android client and the macOS companion runtime.
- Future targets include iOS clients and runtime/server targets on Windows and DGX OS-class systems.

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
- Runtime message router handles authenticated runtime commands.
- Runtime health supports Ollama and LM Studio provider status through the companion runtime.
- Model listing is backend-derived and does not invent default/recommended models when backend lists are empty.
- Ollama model listing uses installed local models and can classify chat vs embedding models.
- LM Studio model listing supports local LLM and embedding models through the runtime.
- Chat requests stream deltas back to the client.
- Ollama reasoning/think chunks are preserved separately from final assistant answer text.
- Cancellation is routed by request id through the backend abstraction.
- Runtime-side model residency now unloads the previous inactive model when switching providers/models and unloads the active model after 10 minutes without chat activity.
- Ollama unload is runtime-mediated through `/api/chat` with empty messages and `keep_alive = 0`; LM Studio unload is runtime-mediated through `/api/v1/models/unload` using loaded instance ids.
- Structured errors are returned through protocol `error` envelopes.
- Document ingestion exists as a standalone runtime-side module for many text/document formats, including PDF, DOCX/DOCM/DOTX, DOC best-effort, HWPX, HWP best-effort, ODT/ODS/ODP, XLSX/XLSM, XLS best-effort, PPTX/PPTM/PPSX, PPT/PPS best-effort, EPUB, RTF, WebArchive, HTML/XHTML, Markdown, AsciiDoc, reStructuredText, text/log/config, CSV/TSV, JSON/JSONL, YAML, TOML, INI/properties, XML, and best-effort Pages/Numbers/Keynote text-bearing archives.
- `chat.suggestions.request` and `chat.suggestions.result` were added so the runtime can generate suggested next questions after an assistant response without the client directly calling any model backend.

### Development Transport, Pairing, And Trust

- Development transport uses local JSON protocol framing over the runtime transport.
- Current USB/local test flows may use localhost forwarding or explicit host/port values, but that is not the product connection model.
- Android now has a first `RuntimeConnectionManager` slice in `core/transport`.
- Android connection targets now carry paired runtime identity plus an optional endpoint hint before delegating to the existing TCP transport.
- New route-resolver milestone: a paired peer identity is now the logical connection target, and resolver output is an ordered list of route candidates for that identity rather than a single durable host/port.
- The v0.1 direct endpoint hint remains only one route candidate. Hints from QR pairing, current Bonjour/local discovery, trusted last-known records, USB reverse, emulator, or manual diagnostics are reachability candidates for the current direct TCP transport, not the product address of the runtime host.
- Android `RuntimeConnectionManager` now has injectable remote route preparation, peer-to-peer connector, and relay connector seams. This lets a future NAT traversal implementation and a future blind relay implementation plug into the same ordered route attempt flow, while the current app still ships only the direct TCP/local-development connector.
- Client route resolution now wires current Bonjour/local discovery results and explicitly selected local/dev endpoints into route candidates before stale trusted last-known endpoint hints, while staying same-network/local-direct only. Bonjour/local candidates should carry minimal route hints when available, preferably a pairing-derived `route_token`, so the client can auto-route a pinned trusted runtime only to matching discovered endpoints. Stable `device_id`/fingerprint TXT values are legacy/development fallbacks. Metadata-less endpoints remain local/dev/manual candidates and are not automatic trusted identity matches. This is not real remote P2P, NAT traversal, signaling, or relay transport yet.
- Discovery identity hints are routing metadata only. They must not expose backend URLs, Ollama or LM Studio details, model inventory, provider health, prompts, files, memory, or runtime command metadata, and they do not replace QR pairing, pinned identity, challenge-response authentication, or encrypted transport.
- Android trusted runtime storage now preserves paired runtime identity even when no last-known endpoint hint is available.
- Android QR parsing accepts identity-only pairing payloads; host/port are validated only when present.
- Android identity-only QR pairing no longer fails just because the QR lacks a fixed host/port. The client keeps the pending runtime identity, starts local discovery, and sends `pairing.request` after a discovered runtime advertises a matching route token or legacy identity hint.
- Android pairing UI now surfaces that pending identity-only QR state: after a QR scan without a fixed endpoint, the client shows the scanned runtime name and explains that it is resolving a local route rather than silently showing an empty discovery list.
- Android trusted runtime writes now persist identity/key/route-token material only. QR host/port hints can still be used as temporary development route candidates during the current pairing attempt, but new trusted-runtime records no longer save those hints as durable product addresses.
- macOS `PairingSession` can generate identity-first QR payloads without host/port and includes those endpoint hints only when supplied. The companion app now uses that identity-only QR shape by default instead of embedding the current local IPv4 address in normal app-generated pairing codes.
- The next remote-connection increment should preserve that identity-only QR shape: pairing records the runtime identity, pinned public key/fingerprint, and route token first; local discovery can later resolve a direct LAN endpoint for that identity without requiring the user to scan or enter a fixed host:port.
- QR-based pairing is implemented for the current runtime/client loop.
- Trusted runtime records persist on the client after pairing.
- The runtime can publish Keychain-backed runtime public-key/fingerprint metadata through QR pairing and accepted `pairing.result`; the client stores it with the trusted runtime and rejects pairing if the accepted runtime identity does not match the scanned QR.
- Runtime identity key persistence and deletion/rotation are covered by SwiftPM tests using isolated Keychain service/account slots, so future reset/re-pair flows can rotate the runtime identity without touching unrelated app keys.
- Runtime commands are gated behind pairing/authentication.
- Untrusted clients are rejected before runtime commands reach Ollama or LM Studio.
- The development transport remains replaceable by encrypted P2P/pairing transport later; current remote P2P, NAT traversal, signaling, and relay references are target architecture placeholders rather than live transports.
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
- Future P2P/relay route preparation should consume the same trusted runtime identity and route token to prepare different-network 1:1 candidates, but actual NAT traversal, DHT/bootstrap rendezvous, signaling, and relay transport are still not implemented.

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
- Trusted runtime and discovered runtime rows no longer expose raw host/port as the primary user-facing route label; those details stay in diagnostics/logging paths.
- Settings now includes an explicit auto-reconnect toggle for the trusted runtime, so users can control restore behavior instead of inferring it only from connection status.
- Trusted runtime restoration no longer depends only on stale fixed endpoint hints: when local discovery later finds a runtime whose route token or legacy identity matches the saved trusted runtime, the client can automatically reconnect through the route resolver.
- Client-facing `models.result` no longer includes backend `remote_host` metadata. The runtime may use provider host fields internally to classify Ollama cloud models, but clients receive only runtime-mediated model identifiers and never backend URLs.
- Chat model picker filters out embedding models.
- Embedding models are selected separately from chat/text-generation models in Settings.
- Selected chat and embedding model ids persist locally.
- Model-list refresh reconciliation now preserves persisted chat and embedding selections across temporary backend/discovery gaps, clears selections only when a refreshed model with the same id is the wrong type, and prevents embedding-capable models from being treated as chat models.
- The Android model selector and embedding-model settings now keep showing the saved model id/name while the companion runtime is reconnecting or refreshing model lists, with localized restoring/unavailable messages so the selection does not appear to be silently cleared.
- Android message/code copy now uses the current Compose `LocalClipboard` API instead of deprecated `LocalClipboardManager`, keeping debug builds free of that UI deprecation warning.
- Chat supports streaming answer deltas, cancellation, and structured error display.
- Reasoning/think text is shown separately as a muted compact section that can expand.
- Local previous chat history exists.
- Archive and delete are separate chat actions.
- Archived chats remain retained locally but are excluded from memory/research/compaction inputs unless restored or explicitly selected in a future source picker.
- User-managed local memory notes can be added, disabled, and removed; enabled notes are included only through the runtime-mediated `chat.send` path.
- File/image attachment UI is present.
- Image input is gated to vision-capable models.
- Android attachment chips now show image/document type and file size, and image chips visibly indicate when the selected model requires a vision-capable replacement before sending.
- Document and image attachments are sent to the runtime boundary rather than directly to a serving backend.
- The companion runtime now rejects image attachments before backend calls unless the selected model advertises `vision`, `image`, or `multimodal`; LM Studio image attachments use native `/api/v1/chat` image input first, with OpenAI-compatible chat completions as fallback when native rejects the request shape.
- Fixed centered example prompts were removed.
- AI-generated suggested next questions now use the runtime-mediated `chat.suggestions.request` path and appear as chips under the latest assistant response. Tapping a chip fills the composer for editing/sending.
- Suggested next questions now require structured JSON from the runtime model call; invalid prose/list output becomes an empty suggestion list instead of arbitrary text chips.
- Latest Android UI polish pass applied:
  - Settings now opens with preferences, embedding model, and memory first, while connection/status and advanced endpoint controls are collapsed into secondary sections.
  - The chat composer shows visible status text when sending is disabled.
  - The top model selector says "Choose model" when no model is selected, uses refresh wording, and gives the selected model more room.
  - Suggested next questions render as full-width follow-up actions instead of truncated horizontal chips.
  - Empty chat copy is more user-facing and less runtime-status-first.
  - The fully ready empty chat state is now intentionally quiet: it leaves the center blank and makes the bottom composer the primary action surface until a real assistant answer can produce suggested next questions.
  - Haptic feedback now covers more high-frequency controls, including drawer opening, chat history selection, chat history menus, model menu opening, Settings navigation, and expandable Settings sections.
  - User-facing Android copy now prefers "runtime host" over "paired computer" across supported languages, keeping the UI less tied to one operating-system pairing.
  - Chat-facing install/backend/file-type messages avoid "runtime host" implementation wording where possible.
- Latest discovery UI pass applied:
  - Discovered runtimes now show whether their advertised identity matches the trusted runtime, is missing, is unknown, or belongs to a different trusted runtime.
  - Known mismatched discovered runtimes cannot be selected when a trusted runtime is already saved.
  - Metadata-less local/dev discovery candidates remain selectable but are labeled as missing advertised identity.
  - Matching discovered trusted runtimes can trigger restore connection attempts, while metadata-less discoveries remain manual/dev candidates only.
- macOS companion copy now describes Bonjour/local transport status as a pairing service and keeps Local Network permission language scoped to completing local pairing, rather than implying local-network discovery is the final product connectivity model.
- Android pairing and transport internals now use runtime-centered names for pairing payloads, trusted runtime records, discovered runtime records, transport clients, and UI state. Legacy `mac_*` QR/query and DataStore keys remain only as compatibility aliases for existing v0.1 pairings and wire payloads.
- macOS backend, pairing, and development-server status/error messages now prefer runtime-host/client wording. New pairing defaults use `AetherLink Runtime` as the display name while legacy `mac_*` protocol fields remain accepted for compatibility.
- Android chat/model-facing copy now avoids implementation-heavy phrases such as "install on runtime host" in favor of direct action labels like "Install model" and "Open the model app, then refresh health." Runtime-host wording remains in Settings, advanced endpoint controls, and security-oriented explanations where the trust boundary matters.

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
  - Result: passed, 63 tests.
- Schema/localization:
  - `python3 script/check_android_string_parity.py`
  - `python3 script/check_protocol_schema.py`
  - `python3 script/check_macos_localization.py`
  - Result: passed.

## Current Known Limits

- The local transport is still development-grade and must be replaced or hardened with encrypted authenticated transport.
- Current development connections can look like same-network or fixed endpoint connections. This must be treated as temporary scaffolding, not the final product.
- Different-network 1:1 connectivity is not implemented yet. The next transport milestone must remove fixed-IP assumptions from the normal user path and replace the current placeholders with real local-direct, remote P2P NAT traversal, and encrypted relay transports.
- DHT/bootstrap-peer discovery, STUN-like address discovery, authenticated hole punching, and TURN-style relay allocation are design targets only; none are implemented in the current transport.
- QR pairing exists, but production trust UX still needs certificate/public-key pinning polish and trusted-device management hardening.
- There is no cloud backend by design.
- A future relay/signaling service, if added for NAT traversal, must not become a cloud AI backend, account server, prompt store, model proxy, backend URL directory, or traffic observer for AI protocol payloads.
- Current code still has fixed-endpoint compatibility paths:
  - Android pairing store still persists legacy `mac_host` and `mac_port` keys only as optional last-known endpoint hints.
  - QR pairing and Bonjour discovery currently provide reachability endpoint hints.
  - Android route resolution prefers current Bonjour/local discovery candidates with matching route-token or legacy runtime identity hints before stale trusted last-known endpoint hints.
  - Bonjour/local endpoints without identity metadata are still useful for local development, diagnostics, and manual selection, but they are not automatic trusted-runtime matches.
  - Android `RuntimeConnectionManager` still delegates shipping connections to the existing TCP `connect(host, port)` implementation unless future P2P/relay connectors are injected.
  - macOS pairing QR can omit `host`/`port`, but current companion/dev-server flows still supply local endpoint hints for the v0.1 direct TCP path.
  These are now isolated behind identity, connection target, endpoint hint, and route-candidate concepts, but the implemented/next Android path is still same-network/local-direct only. Production remote P2P, real NAT traversal, relay fallback, and macOS-side connection-manager integration are not implemented yet.
- There is no MCP implementation.
- There is no skills runtime implementation.
- There is no web search implementation.
- There is no internal Python tool execution yet.
- Memory is still user-managed local notes and local chat history, not full long-term memory, vector memory, or automatic memory compaction.
- Embedding model selection exists, but embedding-powered retrieval/research is not implemented.
- File/document ingestion is runtime-side and broad, but legacy binary formats remain best-effort until dedicated parsers are added.
- Vision input depends on model capability metadata and backend adapter support; Ollama and LM Studio image inputs are mediated by their runtime adapters, with LM Studio using native image input first and OpenAI-compatible multimodal fallback when needed.
- AI-generated next-question suggestions depend on the selected chat model and can be skipped silently if suggestion generation fails or returns invalid JSON.
- Physical-device QA and final UI screenshots still need to be repeated after the latest UI changes.
- Production packaging, signing, notarization, Play distribution, and release pipelines are not complete.

## Immediate Next Work

1. Replace the fixed-endpoint development assumption with a product connection plan:
   - define a `ConnectionManager` abstraction on client and runtime,
   - store paired runtime identity rather than a raw host/IP as the primary connection target,
   - make identity-only QR the normal pairing payload: runtime identity, public key/fingerprint, and route token are required; fixed host:port is only an optional local/dev hint,
   - try same-network discovery/direct connection as the fast path,
   - let local discovery resolve a direct LAN endpoint from the trusted runtime identity and route token instead of from a fixed scanned address,
   - add a private P2P peer-discovery and NAT traversal design for different networks,
   - prepare P2P/relay route candidates for different-network 1:1 connections without claiming NAT traversal, DHT/bootstrap, signaling, or relay is implemented,
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
3. Capture Android UI screenshots after the QA pass and continue polishing spacing, typography, button affordances, drawer layout, and small-screen behavior.
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
