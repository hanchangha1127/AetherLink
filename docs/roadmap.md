# Roadmap

## Current Implementation Snapshot

See [progress.md](progress.md) for the detailed implementation record, verification commands, known limits, and next work queue.

- AetherLink currently has a runtime-host-mediated local model loop, a mobile client implementation, localized client/runtime UI, Ollama and LM Studio backend adapters, QR pairing, trusted runtime persistence, model listing, streaming chat, cancellation, Ollama/LM Studio reasoning or think rendering, runtime-host chat processing event storage with narrow authenticated history reads, a default SQLite/FTS runtime chat event-store backend with legacy JSONL backfill, client-side UI cache/history, runtime-generated short chat titles, runtime-owned session query filtering with rank/snippet metadata, archive/delete separation, runtime-owned user memory notes, a first heuristic runtime-side context compaction slice for oversized `chat.send` histories, separate embedding model selection, broad runtime-side document ingestion, image/vision gating, a first runtime-side model residency policy, identity-based route candidates, an Android core `p2p_rendezvous` route-preparation, QR-planning, trusted-runtime restore contract for opaque expiring records, explicitly enabled authenticated `route.refresh` diagnostics for complete relay and opaque P2P rendezvous records, P2P-only Android route-refresh lease scheduling/retry/expiry lifecycle coverage under that opt-in, a matching macOS pairing QR generation contract for the shared opaque P2P field family, an Android app connection seam that can attempt injected P2P before relay fallback, and a temporary outbound TCP development relay for different-Wi-Fi testing. The deleted suggested next-question feature remains absent from active code/protocol paths and is pinned by a no-device tombstone guard. QR-provisioned relay routes require `relay_secret`, `relay_expires_at`, and `relay_nonce`, so development relay frame bodies are encrypted before forwarding, Android authenticated relay refresh validation rejects reused relay nonces or non-advancing relay leases while allowing stable relay id/secret reuse when diagnostic refresh is explicitly enabled, and the RuntimeDevServer relay smoke positively validates malformed pairing identity rejection without trust creation, consumed pairing QR reuse rejection, same-connection runtime command rejection after invalid or consumed pairing requests, history reads, title generation, session rename/archive/restore/delete lifecycle, memory CRUD, two-device owner isolation for memory and chat read/mutation boundaries, raw nonce auth-signature rejection, auth replay and superseded challenge rejection, and encrypted frame bodies for auth, model, chat, attachment, cancel, malformed-pairing, pairing-reuse, rejected-pairing auth-boundary, history, title/session mutation, memory, and owner-isolation plaintext markers while rejecting the full protected unauthenticated runtime command matrix before auth or payload handling. The P2P work currently emits/parses QR records, rejects whitespace-mutated opaque P2P record IDs, encrypted bodies, and anti-replay nonces across pending/trusted/route-refresh paths, rejects authenticated P2P `route.refresh` records that reuse the current record ID or anti-replay nonce or fail to advance the record expiry when the diagnostic path is explicitly enabled, persists pending Android route material, stores complete trusted-runtime P2P rendezvous material after accepted pairing, route-refresh QR scan, or explicit diagnostic `route.refresh`, plans opaque saved records for trusted reconnect, redacts P2P route-material fields from macOS Activity diagnostics, route diagnostics, and companion logs, and can exercise an injected app-level connector before relay fallback; it is not NAT traversal, signaling, hole punching, or a production P2P connector. Trusted runtime persistence, accepted-pairing trust creation, pending pairing route storage, trusted reconnect target generation, core transport default route resolution, and normal route UI now remove or ignore stale current and legacy fixed host/port material during restore; fixed endpoints remain diagnostics/local fast-path hints, not durable reconnect state. macOS clean first-run Pairing no longer exposes Connection Recovery address/port/key setup unless saved route diagnostics or a route-preparation issue exists, and Android product defaults no longer advertise or automatically send authenticated `route.refresh`; normal route repair stays latest-QR scan first.
- The client implementation does not call Ollama or LM Studio directly.
- MCP, skills, web search, advanced memory, project workspaces, automations, Python tools, additional client targets, Windows runtime targets, and DGX OS-class runtime targets remain roadmap work.

## Immediate Next Implementation Queue

1. Physical client-device QA after the latest UI/protocol changes.
2. Screenshot-based client UI polish for a cleaner modern/classic chat surface, drawer, model selector, settings, and transcript spacing.
3. Capture launcher/dock screenshots on real devices to verify the generated AetherLink icon reads correctly at small sizes.
4. Continue hardening pairing/trusted-device UX so normal users only pair or refresh routes by scanning QR; macOS clean first-run Pairing now hides Connection Recovery setup and Android product defaults no longer advertise or automatically send authenticated `route.refresh`, but physical-device recovery flows still need review.
5. Replace the temporary relay/fixed-endpoint development assumptions with a paired-device private encrypted overlay:
   - paired private peer identity as the primary connection target,
   - QR-bootstrapped overlay/rendezvous/relay material for same-network and different-network use,
   - local direct connection as an opportunistic fast path,
   - remote P2P NAT traversal for different networks using STUN-like address discovery and authenticated hole punching,
   - optional DHT/bootstrap-peer rendezvous for short-lived paired-device discovery records,
   - end-to-end encrypted blind relay/TURN fallback only when direct paths fail,
   - no AI protocol payloads, model lists, prompts, files, memory, backend credentials, or model commands visible to any relay or discovery service.
6. Expand smoke tests for pairing, authenticated model list, streaming chat, cancel, attachments, model-residency unload behavior, and untrusted-client rejection.

## v0.1 Local Chat Link

- The client scans a runtime-host-displayed QR code and pairs with the AetherLink Runtime.
- Pairing binds device identities and keys; product connectivity must not depend on manually entering or permanently storing a fixed IP address.
- Fixed host/port values, mDNS/Bonjour local discovery, and raw local sockets are v0.1 development hints or local fast paths, not the target reconnect model and not sufficient for unrelated networks.
- Runtime host detects Ollama health.
- Runtime host lists Ollama models.
- Client selects a model and sends chat messages.
- Runtime host streams Ollama responses back to the client.
- Runtime host preserves Ollama reasoning/think chunks separately from final answer text.
- Client shows reasoning/think text in a muted, compact section that expands on demand.
- Client can reopen previous local chats.
- Client can manage user memory notes through the trusted runtime and include enabled runtime-owned notes as chat context.
- Runtime can compact oversized active `chat.send` history before backend dispatch by preserving recent user-visible messages verbatim and injecting a backend-only system summary of older active turns.
- Archive and delete are distinct local session actions: archived chats are retained but hidden from active memory/research/compaction inputs unless restored or explicitly selected.
- Client can cancel generation.
- Only trusted devices can control the runtime host.
- Client never connects directly to Ollama or LM Studio.

## Private Peer Connectivity Direction

The concrete phased architecture is tracked in [connection-overlay.md](connection-overlay.md).

AetherLink's 1:1 connection model is Bitcoin-like only in the narrow sense of peer identity and discovery without relying on a single fixed address. It is not a public untrusted peer network. Only QR-paired trusted devices may discover, authenticate, and communicate with each other.

The target reconnect model is paired peer identity plus QR-bootstrapped private overlay state, with local direct as an opportunistic fast path, remote P2P NAT traversal for different networks, and encrypted blind relay/TURN fallback. NAT traversal should use STUN-like address discovery, authenticated hole punching, short-lived candidate exchange, and session keys bound to the paired identities. Optional DHT/bootstrap-peer discovery may provide a Bitcoin-network-like feel for finding peers without a fixed IP, but only with privacy-preserving rendezvous records for already-paired devices. Relay/signaling infrastructure must remain unable to see AI protocol payloads, model lists, prompts, files, memory, backend credentials, or backend URLs. Clients still talk only to the trusted runtime boundary, never directly to Ollama, LM Studio, or future serving backends.

Current status: the code has trusted identities, endpoint hints, Bonjour/local discovery candidates, USB/dev local paths, route-candidate plumbing, an Android core P2P rendezvous route-preparation, QR-planning, trusted-runtime restore contract, explicitly enabled authenticated P2P route-material renewal through diagnostic `route.refresh`, matching macOS compact/canonical P2P QR generation for the shared opaque field family, and a temporary outbound TCP relay keyed by private route material. This relay helps different-Wi-Fi development testing, and QR-provisioned routes require `relay_secret`, `relay_expires_at`, and `relay_nonce`; diagnostic authenticated relay refresh accepts stable relay id/secret reuse only with a fresh nonce and advancing lease, keeps the current relay route and retries when stale refresh material is rejected inside an active lease, and the authenticated relay smoke now checks that selected AI protocol and payload markers do not appear in captured encrypted relay frame bodies. The P2P work maps complete canonical opaque expiring QR or explicitly enabled authenticated-refresh records to pending or trusted route material and prepared P2P route candidates, rejecting whitespace-mutated opaque values plus replayed or non-advancing authenticated refresh records before storage or planning, while retaining the current P2P route and retrying inside the active record lease when stale authenticated refresh material is rejected under diagnostic opt-in; it is not production signaling, STUN, hole punching, or a real P2P connector. Trusted runtime persistence, accepted-pairing trust creation, pending pairing route storage, trusted reconnect target generation, core transport default route resolution, and normal route UI now remove or ignore stale current and legacy fixed host/port material during restore; direct-only diagnostic QR endpoints can remain current-session hints but are not trusted, pending restore, or normal connectable route state. The allocation path now derives `relay_id` from the paired route token and can reuse a stable frame secret, but it is not the production private overlay. Production remote P2P NAT traversal, DHT/bootstrap rendezvous, hardened relay allocation renewal, replay-resistant session setup, and production end-to-end transport encryption are not complete yet.

## Current Development Relay

- The active development relay for QR pairing is the SwiftPM `AetherLinkRelay` executable in allocation-required mode.
- `script/aetherlink_relay.py` is legacy-only, does not implement allocation leases, and must not be used for current QR pairing or different-network validation.
- Runtime hosts can register outbound with `AETHERLINK_RELAY_HOST`, `AETHERLINK_RELAY_PORT`, and optional `AETHERLINK_RELAY_ID`, or request route-token-based allocation through `AETHERLINK_BOOTSTRAP_RELAY_HOST`.
- Pairing QR payloads must carry `relay_host`, `relay_port`, `relay_id`, `relay_secret`, `relay_expires_at`, and `relay_nonce` for the current QR-provisioned relay path so the client can prepare a fresh relay route after trust is established.
- The relay matches one runtime and one client in a private room and pipes bytes; it does not call Ollama, LM Studio, or any model backend. QR relay routes require `relay_secret`, so it forwards encrypted AetherLink frame bodies.
- This is a development bridge only. It must be replaced or hardened with production session-key exchange, key-bound route tokens, replay protection, relay allocation, and a real bootstrap/NAT traversal strategy before sensitive remote use.

## Current LM Studio Backend Support

- LM Studio is supported as a runtime-mediated local backend.
- Clients see LM Studio models through runtime health, `models.list`, and provider-prefixed `chat.send` model ids.
- LM Studio support is not MCP, memory, skills, web search, or direct client backend access.

## Future Project Workspaces

This is not v0.1 implementation scope. The product direction is a project/workspace feature similar to ChatGPT Projects, while preserving AetherLink's runtime boundary:

- Project-scoped chats, files, instructions, memories, indexes, and model/backend preferences.
- Trusted-source controls that let the user decide which files, folders, chats, notes, or external results can be used as project context.
- Project-level search and deep-research-like brief generation over indexed, user-approved material.
- Project indexes, retrieval, summarization, and research run through the runtime host boundary, not directly from client apps.
- Mobile clients act as project controllers and approval/status surfaces; they do not call Ollama, LM Studio, future serving backends, file indexers, or tools directly.
- Project files and indexes are sensitive data and must pass through runtime permissions, source selection, audit logs, and archive/delete rules.

## Future Scheduling And Automation

This is not v0.1 implementation scope. Scheduling and automation should be runtime-host mediated:

- User-created scheduled tasks, reminders, monitors, recurring automations, and runtime-triggered jobs.
- Permission prompts before an automation can use sensitive project files, network access, tools, terminal execution, MCP, web search, or model backends.
- Audit logs for creation, edits, approvals, execution attempts, results, failures, and cancellations.
- Client apps provide approval, pause/resume, status, and result-review surfaces; they do not execute scheduled jobs or call backends/tools directly.
- Scheduled jobs are sensitive runtime actions because they can run later without the user actively watching the UI.

## v0.2 Session and Memory Polish

- Migrate the current runtime-owned JSONL chat event authority to SQLite/FTS while preserving authenticated `chat.sessions.list` / `chat.messages.list` reads and client-side message-body redaction.
- Implemented first slice: authenticated `chat.sessions.list` can filter runtime-owned session summaries by optional `query` over title, model id, metadata, processing state, and sanitized transcript text while preserving owner/archive/delete boundaries.
- Implemented first client slice: Android Settings > Chat history keeps local instant filtering, and the explicit refresh action forwards the current search text as runtime `query` for server-owned search.
- Implemented ranking/snippet seam: query responses can carry deterministic `search.rank`, bounded `search.snippet`, and `search.matched_fields`; Android can render snippets while redacting runtime-owned snippet text from device storage.
- Implemented SQLite/FTS parity, backfill, and default-store rollout slices: `SQLiteRuntimeChatEventStore` can persist runtime chat events, maintain a session FTS index, backfill existing JSONL runtime chat events, preserve authenticated sessions/messages/lifecycle semantics, return deterministic search metadata through the existing store protocol, and serve as the `LocalRuntimeMessageRouter` / `CompanionAppModel` production default via `RuntimeChatEventStoreDefaults.productionStore()`.
- Continue session search polish with SQLite/FTS rollout hardening, richer ranking, snippets, retention policy, and richer client sync/search UI; Android Settings search-result rows now render runtime-provided rank/snippet/matched-field context plus filtered active/archived result counts that stay stable while row actions run, the RuntimeDevServer authenticated relay smoke now validates `chat.sessions.list` query search metadata, stored assistant reasoning can be matched and labeled separately from visible answer text across JSONL router, SQLite/FTS, and Android Settings paths, and the first storage-internal SQLite deleted-session retention primitive can prune cutoff-eligible deleted sessions with owner-scoped tombstones that prevent legacy JSONL resurrection.
- Client session list polish, rename, delete, and search.
- Archive polish: archived chats remain retained but excluded from memory, reflection, research, and compaction inputs unless the user restores them or explicitly selects them as sources. Implemented runtime send gate: `chat.send` into an existing archived session now returns `chat_session_must_be_restored_before_send` before backend dispatch or chat-event mutation.
- Preserve reasoning/think text separately from final assistant answer text in session storage; no-device regressions now pin reasoning-only session search metadata and transcript reads that keep assistant answer `content` separate from assistant `reasoning`.
- Context-window-aware session compaction: first heuristic runtime slice is implemented/in progress for oversized active `chat.send` histories. It keeps recent messages verbatim and injects a backend-only summary of older active turns without altering client-visible history; runtime model metadata can now carry optional `context_window_tokens`, and macOS `chat.send` uses that hint to choose a model-aware compaction budget while Android preserves the metadata. Tokenizer-aware budgets, LLM-generated summaries, durable source pointers, and richer context-window policies remain future work.
- Longer-inactivity memory summarization: first no-device eligibility, draft, protocol-listing, Android review UI, approval/injection, approved-entry source-metadata, approved-source review UI, and durable dismiss slices are implemented. The runtime host can list owner-scoped, active, sufficiently old, sufficiently long chat sessions as future memory-summary candidates, build deterministic reviewable summary drafts with visible-transcript source pointers, expose those drafts through authenticated `memory.summary.drafts.list`, approve one current draft through `memory.summary.draft.approve` into an idempotent owner-scoped runtime memory entry, dismiss one current draft through `memory.summary.draft.dismiss` without writing memory, and persist optional source metadata on approved entries plus owner-scoped dismiss decisions for dismissed drafts. Android Settings > Memory renders suggested memories, sends approval or dismiss decisions with stale-draft guard metadata, updates runtime memory or draft state from the response, preserves approved-entry source DTO/state, shows approved-memory source metadata on demand without full transcript exposure by default, and keeps draft previews/source excerpts out of device storage. This remains separate from short model-unload inactivity. LLM-generated summaries and richer inactivity/review policy remain future work.

## v0.2 Runtime Resource Policy

- Implemented first slice: when switching models, the aggregate runtime host asks the previous inactive provider model to unload before using the newly selected model.
- Implemented first slice: if there is no chat activity for 10 or more minutes, the aggregate runtime host asks the active provider model to unload.
- Ollama unload uses the runtime-host-side `/api/chat` path with empty messages and `keep_alive = 0`.
- LM Studio unload uses the runtime-host-side `/api/v1/models/unload` path for loaded instance ids.
- Keep model residency policy in the runtime host, not client UI code.
- Continue polishing this policy with runtime status UI, logging, user controls, and provider-specific failure reporting.

## v0.3 Embeddings And Research Notes

- Optional embedding model registration on the runtime host.
- Embedding models are listed and selected separately from general text-generation/chat models.
- Semantic search over prior chats and user-approved notes.
- Memory clustering and deduplication suggestions.
- Retrieval, ranking, and knowledge indexing use the selected embedding model.
- Deep-research-like brief generation from indexed local/user-approved material.
- Research notebook sessions with source snippets, citations, and follow-up questions.
- Embedding-powered recall remains runtime-mediated; clients stay controller UIs.

## v0.4 Backend Selection Polish

- Backend selector and model capability display.
- Clients still talk only to AetherLink Runtime.

## v0.5 Permission Broker and Skills

- Runtime-side permission model.
- Prompt-only skill registry.
- Approval-required actions.
- Internal Python tool execution through the runtime host for deterministic tasks such as calculations.
- Runtime-side permissions and audit logs for Python, file, terminal, skills, MCP, and web-search actions.
- Advanced memory and skill execution remain roadmap items, not v0.1 implementation scope.

## v0.6 Web Search

- Runtime-side web search provider abstraction.
- SearXNG/custom endpoint first.
- Search result cache and citation-ready metadata.
- Web search remains a roadmap item, not v0.1 implementation scope.

## v0.7 MCP

- Runtime-side MCP server registry and client manager.
- Client tool approval and result views.
- MCP remains a roadmap item, not v0.1 implementation scope.

## v0.8 Workspace/RAG

- Project/workspace registration with scoped instructions, files, memory, indexes, and model/backend preferences.
- File indexer and document chunking for user-approved project sources.
- Search over indexed files, prior project chats, and trusted project memory.
- Trusted-source controls for selecting which folders, files, chats, notes, or external results can feed retrieval and research.
- Eventual project-level search and research reports with source snippets and citations.
- Existing image/file attachment inputs remain runtime-mediated; workspace/RAG adds project-scoped file approval, chunking, indexing, and retrieval on top of that runtime boundary.
- Clients never send files or images directly to Ollama, LM Studio, future serving backends, or indexing services.

## v0.9 Scheduling And Automations

- Runtime-host scheduler for user-created scheduled tasks, reminders, monitors, recurring automations, and runtime-triggered jobs.
- Runtime permission broker prompts for actions that touch project files, tools, terminal, MCP, web search, network, or model backends.
- Audit log entries for automation definitions, approvals, runs, failures, cancellations, and permission changes.
- Mobile approval/status surfaces for reviewing, pausing, resuming, cancelling, and approving automation runs.
- Client apps remain controllers; scheduled jobs execute only through the trusted runtime.

## v1.0 Platform Expansion

- Runtime targets expand from the current runtime host to Windows and DGX OS-class workstation/server support.
- Client/controller targets expand from the current mobile client to iOS.
- Keep the same trust boundary: clients control sessions; runtime targets mediate all model access.
- Keep the same private P2P identity model across platforms so paired devices can reconnect across local and remote networks without exposing backend URLs or relying on OS-specific fixed endpoints or local-only discovery.

## v1.1 Serving Backend Expansion

- Add more AI serving backend adapters beyond Ollama and LM Studio.
- Preserve a common capability model for health, installed/running models, streaming chat, cancellation, embeddings, context windows, and structured errors.
- Avoid exposing backend-specific local URLs to mobile clients.
