# AetherLink Progress And Forward Plan

Last updated: 2026-06-24 KST.

This document records what has been implemented so far and what should happen next. It is intentionally broader than the original v0.1 MVP because recent work has moved the prototype toward a more complete product shape.

## Product Boundary

- AetherLink is local-first.
- There is no cloud backend, account server, or relay in the current architecture.
- Client apps are controllers. Runtime/server apps mediate model access, file ingestion, future tools, future web search, future project workspaces, and future automations.
- The client must not call Ollama, LM Studio, or future serving backends directly.
- Device connectivity must be based on paired device identity and keys, not on a fixed IP address.
- Same-network discovery, mDNS/Bonjour, explicit host/port values, and USB/localhost forwarding are v0.1 development hints or local fast-path transports only.
- The intended product connection model is a paired-device private P2P overlay, closer in spirit to peer discovery in networks such as Bitcoin than to a fixed server address. This analogy is only about peer identity and discovery; AetherLink must not expose a public open peer network, and only QR-paired trusted devices should be able to discover, authenticate, and communicate with each other.
- The connection manager should work across different networks: local direct connection first, remote peer-to-peer NAT traversal second, and an end-to-end encrypted blind relay/TURN-style fallback only when direct peer-to-peer fails.
- Relay/signaling infrastructure must not see AI protocol payloads, model lists, prompts, files, memory, backend credentials, or backend URLs.
- Current code has local-direct route-candidate plumbing and development endpoint hints only. Remote P2P NAT traversal, signaling, encrypted blind relay transport, and production end-to-end transport encryption are placeholders/future milestones, not implemented capabilities.
- Current first targets are the Android client and the macOS companion runtime.
- Future targets include iOS clients and runtime/server targets on Windows and DGX OS-class systems.

## Implemented So Far

### Repository And Documentation

- Monorepo layout exists for Android, macOS, shared protocol, docs, examples, scripts, README, LICENSE, and protocol schema.
- `docs/architecture.md`, `docs/protocol.md`, `docs/security.md`, `docs/mvp-v0.1.md`, and `docs/roadmap.md` define the runtime boundary, protocol, security model, and roadmap.
- Protocol schema validation exists in `packages/protocol-schema/protocol.schema.json`.
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
- Ollama unload is Mac-mediated through `/api/chat` with empty messages and `keep_alive = 0`; LM Studio unload is Mac-mediated through `/api/v1/models/unload` using loaded instance ids.
- Structured errors are returned through protocol `error` envelopes.
- Document ingestion exists as a standalone runtime-side module for many text/document formats, including PDF, DOCX/DOCM/DOTX, DOC best-effort, HWPX, HWP best-effort, ODT/ODS/ODP, XLSX/XLSM, XLS best-effort, PPTX/PPTM/PPSX, PPT/PPS best-effort, EPUB, RTF, WebArchive, HTML/XHTML, Markdown, AsciiDoc, reStructuredText, text/log/config, CSV/TSV, JSON/JSONL, YAML, TOML, INI/properties, XML, and best-effort Pages/Numbers/Keynote text-bearing archives.
- `chat.suggestions.request` and `chat.suggestions.result` were added so the runtime can generate suggested next questions after an assistant response without the client directly calling any model backend.

### Development Transport, Pairing, And Trust

- Development transport uses local JSON protocol framing over the runtime transport.
- Current USB/local test flows may use localhost forwarding or explicit host/port values, but that is not the product connection model.
- Android now has a first `RuntimeConnectionManager` slice in `core/transport`.
- Android connection targets now carry paired runtime identity plus an optional endpoint hint before delegating to the existing TCP transport.
- New route-resolver milestone: a paired peer identity is now the logical connection target, and resolver output is an ordered list of route candidates for that identity rather than a single durable host/port.
- The v0.1 direct endpoint hint remains only one route candidate. Hints from QR pairing, current Bonjour/local discovery, trusted last-known records, USB reverse, emulator, or manual diagnostics are reachability candidates for the current direct TCP transport, not the product address of the Mac runtime.
- Android route resolution now wires current Bonjour/local discovery results and explicitly selected local/dev endpoints into route candidates before stale trusted last-known endpoint hints, while staying same-network/local-direct only. Bonjour/local candidates should carry minimal route hints when available, preferably a pairing-derived `route_token`, so Android can auto-route a pinned trusted runtime only to matching discovered endpoints. Stable `device_id`/fingerprint TXT values are legacy/development fallbacks. Metadata-less endpoints remain local/dev/manual candidates and are not automatic trusted identity matches. This is not real remote P2P, NAT traversal, signaling, or relay transport yet.
- Discovery identity hints are routing metadata only. They must not expose backend URLs, Ollama or LM Studio details, model inventory, provider health, prompts, files, memory, or runtime command metadata, and they do not replace QR pairing, pinned identity, challenge-response authentication, or encrypted transport.
- Android trusted runtime storage now preserves paired runtime identity even when no last-known endpoint hint is available.
- Android QR parsing accepts identity-only pairing payloads; host/port are validated only when present.
- macOS `PairingSession` can generate identity-first QR payloads without host/port and includes those endpoint hints only when supplied.
- QR-based pairing is implemented for the current runtime/client loop.
- Trusted runtime records persist on the client after pairing.
- Runtime commands are gated behind pairing/authentication.
- Untrusted clients are rejected before runtime commands reach Ollama or LM Studio.
- The development transport remains replaceable by encrypted P2P/pairing transport later; current remote P2P, NAT traversal, signaling, and relay references are target architecture placeholders rather than live transports.
- Cross-network 1:1 connectivity is not solved by mDNS or fixed private IPs; it needs a connection manager that can resolve route candidates from the same paired identity, then negotiate local direct, remote P2P, and encrypted relay paths.
- Public peer-discovery ideas can inspire the design, but AetherLink discovery must be privacy-preserving:
  - do not publish stable device ids directly,
  - use rotating rendezvous tokens derived from paired-device shared secrets,
  - keep prompts, responses, files, memory, model names, and runtime commands inside the end-to-end encrypted session,
  - prevent unpaired peers from learning usable routing or runtime metadata.
  - keep relay/signaling blind to encrypted AI protocol payloads and backend details.
- Current code now prepares that direction by advertising and matching a QR-provided `route_token` before falling back to legacy device id/fingerprint matching.

### Android Client

- Kotlin/Jetpack Compose client skeleton has moved beyond basic scaffold.
- First-launch/onboarding flow is oriented around pairing instead of manual backend URL entry.
- Pairing and connection/status controls live under Settings, not as primary bottom tabs.
- Main chat UI is closer to a ChatGPT-style layout: drawer for previous chats/settings, top model selector, composer at the bottom, and cleaner empty state.
- System light/dark appearance is supported.
- App language setting supports English, Korean, Japanese, Simplified Chinese, and French, with English as the default.
- UI strings have been cleaned to avoid hardcoded Android/Mac wording where possible.
- Haptic feedback is used for important controls.
- Runtime connection restores from the trusted runtime record after app restart.
- Chat model picker filters out embedding models.
- Embedding models are selected separately from chat/text-generation models in Settings.
- Selected chat and embedding model ids persist locally.
- Chat supports streaming answer deltas, cancellation, and structured error display.
- Reasoning/think text is shown separately as a muted compact section that can expand.
- Local previous chat history exists.
- Archive and delete are separate chat actions.
- Archived chats remain retained locally but are excluded from memory/research/compaction inputs unless restored or explicitly selected in a future source picker.
- User-managed local memory notes can be added, disabled, and removed; enabled notes are included only through the runtime-mediated `chat.send` path.
- File/image attachment UI is present.
- Image input is gated to vision-capable models.
- Document and image attachments are sent to the runtime boundary rather than directly to a serving backend.
- Fixed centered example prompts were removed.
- AI-generated suggested next questions now use the runtime-mediated `chat.suggestions.request` path and appear as chips under the latest assistant response. Tapping a chip fills the composer for editing/sending.
- Latest Android UI polish pass applied:
  - Settings now opens with preferences, embedding model, and memory first, while connection/status and advanced endpoint controls are collapsed into secondary sections.
  - The chat composer shows visible status text when sending is disabled.
  - The top model selector says "Choose model" when no model is selected, uses refresh wording, and gives the selected model more room.
  - Suggested next questions render as full-width follow-up actions instead of truncated horizontal chips.
  - Empty chat copy is more user-facing and less runtime-status-first.
  - Chat-facing install/backend/file-type messages avoid "runtime host" implementation wording where possible.
- Latest discovery UI pass applied:
  - Discovered runtimes now show whether their advertised identity matches the trusted runtime, is missing, is unknown, or belongs to a different trusted runtime.
  - Known mismatched discovered runtimes cannot be selected when a trusted runtime is already saved.
  - Metadata-less local/dev discovery candidates remain selectable but are labeled as missing advertised identity.

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
- QR pairing exists, but production trust UX still needs certificate/public-key pinning polish and trusted-device management hardening.
- There is no cloud backend by design.
- A future relay/signaling service, if added for NAT traversal, must not become a cloud AI backend, account server, prompt store, model proxy, backend URL directory, or traffic observer for AI protocol payloads.
- Current code still has fixed-endpoint compatibility paths:
  - Android pairing store still persists legacy `mac_host` and `mac_port` keys only as optional last-known endpoint hints.
  - QR pairing and Bonjour discovery currently provide reachability endpoint hints.
  - Android route resolution prefers current Bonjour/local discovery candidates with matching route-token or legacy runtime identity hints before stale trusted last-known endpoint hints.
  - Bonjour/local endpoints without identity metadata are still useful for local development, diagnostics, and manual selection, but they are not automatic trusted-runtime matches.
  - Android `RuntimeConnectionManager` still delegates the selected direct endpoint candidate to the existing TCP `connect(host, port)` implementation.
  - macOS pairing QR can omit `host`/`port`, but current companion/dev-server flows still supply local endpoint hints for the v0.1 direct TCP path.
  These are now isolated behind identity, connection target, endpoint hint, and route-candidate concepts, but the implemented/next Android path is still same-network/local-direct only. Production remote P2P, real NAT traversal, relay fallback, and macOS-side connection-manager integration are not implemented yet.
- There is no MCP implementation.
- There is no skills runtime implementation.
- There is no web search implementation.
- There is no internal Python tool execution yet.
- Memory is still user-managed local notes and local chat history, not full long-term memory, vector memory, or automatic memory compaction.
- Embedding model selection exists, but embedding-powered retrieval/research is not implemented.
- File/document ingestion is runtime-side and broad, but legacy binary formats remain best-effort until dedicated parsers are added.
- Vision input depends on model capability metadata and backend adapter support.
- AI-generated next-question suggestions depend on the selected chat model and can be skipped silently if suggestion generation fails.
- Physical-device QA and final UI screenshots still need to be repeated after the latest UI changes.
- Production packaging, signing, notarization, Play distribution, and release pipelines are not complete.

## Immediate Next Work

1. Replace the fixed-endpoint development assumption with a product connection plan:
   - define a `ConnectionManager` abstraction on client and runtime,
   - store paired runtime identity rather than a raw host/IP as the primary connection target,
   - try same-network discovery/direct connection as the fast path,
   - add a private P2P peer-discovery and NAT traversal design for different networks,
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
