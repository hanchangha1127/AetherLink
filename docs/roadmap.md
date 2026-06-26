# Roadmap

## Current Implementation Snapshot

See [progress.md](progress.md) for the detailed implementation record, verification commands, known limits, and next work queue.

- AetherLink currently has a runtime-host-mediated local model loop, a mobile client implementation, localized client/runtime UI, Ollama and LM Studio backend adapters, QR pairing, trusted runtime persistence, model listing, streaming chat, cancellation, Ollama/LM Studio reasoning or think rendering, runtime-host chat processing event storage with narrow authenticated history reads, client-side UI cache/history, runtime-generated short chat titles, archive/delete separation, runtime-owned user memory notes, separate embedding model selection, broad runtime-side document ingestion, image/vision gating, runtime-mediated AI next-question suggestions, a first runtime-side model residency policy, identity-based route candidates, and a temporary outbound TCP development relay for different-Wi-Fi testing. QR-provisioned relay routes require `relay_secret`, `relay_expires_at`, and `relay_nonce`, so development relay frame bodies are encrypted before forwarding.
- The client implementation does not call Ollama or LM Studio directly.
- MCP, skills, web search, advanced memory, project workspaces, automations, Python tools, additional client targets, Windows runtime targets, and DGX OS-class runtime targets remain roadmap work.

## Immediate Next Implementation Queue

1. Physical client-device QA after the latest UI/protocol changes.
2. Screenshot-based client UI polish for a cleaner modern/classic chat surface, drawer, model selector, settings, transcript spacing, and suggested next-question actions.
3. Capture launcher/dock screenshots on real devices to verify the generated AetherLink icon reads correctly at small sizes.
4. Harden pairing/trusted-device UX so normal users only pair or refresh routes by scanning QR.
5. Replace the temporary relay/fixed-endpoint development assumptions with a paired-device private encrypted overlay:
   - paired private peer identity as the primary connection target,
   - QR-bootstrapped overlay/rendezvous/relay material for same-network and different-network use,
   - local direct connection as an opportunistic fast path,
   - remote P2P NAT traversal for different networks using STUN-like address discovery and authenticated hole punching,
   - optional DHT/bootstrap-peer rendezvous for short-lived paired-device discovery records,
   - end-to-end encrypted blind relay/TURN fallback only when direct paths fail,
   - no AI protocol payloads, model lists, prompts, files, memory, backend credentials, or model commands visible to any relay or discovery service.
6. Expand smoke tests for pairing, authenticated model list, streaming chat, cancel, suggestions, attachments, model-residency unload behavior, and untrusted-client rejection.

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
- Archive and delete are distinct local session actions: archived chats are retained but hidden from active memory/research/compaction inputs unless restored or explicitly selected.
- Client can cancel generation.
- Only trusted devices can control the runtime host.
- Client never connects directly to Ollama or LM Studio.

## Private Peer Connectivity Direction

The concrete phased architecture is tracked in [connection-overlay.md](connection-overlay.md).

AetherLink's 1:1 connection model is Bitcoin-like only in the narrow sense of peer identity and discovery without relying on a single fixed address. It is not a public untrusted peer network. Only QR-paired trusted devices may discover, authenticate, and communicate with each other.

The target reconnect model is paired peer identity plus QR-bootstrapped private overlay state, with local direct as an opportunistic fast path, remote P2P NAT traversal for different networks, and encrypted blind relay/TURN fallback. NAT traversal should use STUN-like address discovery, authenticated hole punching, short-lived candidate exchange, and session keys bound to the paired identities. Optional DHT/bootstrap-peer discovery may provide a Bitcoin-network-like feel for finding peers without a fixed IP, but only with privacy-preserving rendezvous records for already-paired devices. Relay/signaling infrastructure must remain unable to see AI protocol payloads, model lists, prompts, files, memory, backend credentials, or backend URLs. Clients still talk only to the trusted runtime boundary, never directly to Ollama, LM Studio, or future serving backends.

Current status: the code has trusted identities, endpoint hints, Bonjour/local discovery candidates, USB/dev local paths, route-candidate plumbing, and a temporary outbound TCP relay keyed by private route material. This relay helps different-Wi-Fi development testing, and QR-provisioned routes require `relay_secret`, `relay_expires_at`, and `relay_nonce`. The allocation path now derives `relay_id` from the paired route token and can reuse a stable frame secret, but it is not the production private overlay. Production remote P2P NAT traversal, DHT/bootstrap rendezvous, hardened relay allocation renewal, replay-resistant session setup, and production end-to-end transport encryption are not complete yet.

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
- Session list, rename, delete, and search.
- Client session list polish, rename, delete, and search.
- Archive polish: archived chats remain retained but excluded from memory, reflection, research, and compaction inputs unless the user restores them or explicitly selects them as sources.
- Preserve reasoning/think text separately from final assistant answer text in session storage.
- Context-window-aware session compaction: when a conversation grows beyond the selected model context window, compact older turns into summaries while keeping recent messages and source pointers.
- Longer-inactivity memory summarization: define inactivity criteria that summarize chat history into modern compact memory summaries. This is separate from short model-unload inactivity.

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
