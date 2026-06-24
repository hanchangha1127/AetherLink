# Roadmap

## Current Implementation Snapshot

See [progress.md](progress.md) for the detailed implementation record, verification commands, known limits, and next work queue.

- AetherLink currently has a runtime-host-mediated local model loop, an Android Compose client implementation, Ollama and LM Studio backend adapters, QR pairing, trusted runtime persistence, model listing, streaming chat, cancellation, reasoning/think rendering, local chat history, archive/delete separation, user-managed local memory notes, separate embedding model selection, broad runtime-side document ingestion, image/vision gating, runtime-mediated AI next-question suggestions, and a first runtime-side model residency policy.
- The client implementation does not call Ollama or LM Studio directly.
- MCP, skills, web search, advanced memory, project workspaces, automations, Python tools, iOS, Windows, and DGX OS-class runtime/server targets remain roadmap work.

## Immediate Next Implementation Queue

1. Physical Android device QA after the latest UI/protocol changes.
2. Screenshot-based Android UI polish for the ChatGPT-like chat surface, drawer, model selector, settings, and suggested next-question chips.
3. Capture launcher/dock screenshots on real devices to verify the generated AetherLink icon reads correctly at small sizes.
4. Harden pairing/trusted-device UX and remove manual endpoint exposure from the normal user path.
5. Replace fixed-IP development transport assumptions with a paired-device private P2P overlay:
   - paired private peer identity as the primary connection target,
   - local direct connection as the fast path,
   - remote P2P NAT traversal for different networks using STUN-like address discovery and authenticated hole punching,
   - optional DHT/bootstrap-peer rendezvous for short-lived paired-device discovery records,
   - end-to-end encrypted blind relay/TURN fallback only when direct paths fail,
   - no AI protocol payloads, model lists, prompts, files, memory, backend credentials, or model commands visible to any relay or discovery service.
6. Expand smoke tests for pairing, authenticated model list, streaming chat, cancel, suggestions, attachments, model-residency unload behavior, and untrusted-client rejection.

## v0.1 Local Chat Link

- The client scans a runtime-host-displayed QR code and pairs with the companion runtime.
- Pairing binds device identities and keys; product connectivity must not depend on manually entering or permanently storing a fixed IP address.
- Fixed host/port values and mDNS/Bonjour local discovery are v0.1 development hints or local fast paths, not the target reconnect model.
- Runtime host detects Ollama health.
- Runtime host lists Ollama models.
- Client selects a model and sends chat messages.
- Runtime host streams Ollama responses back to the client.
- Runtime host preserves Ollama reasoning/think chunks separately from final answer text.
- Client shows reasoning/think text in a muted, compact section that expands on demand.
- Client can reopen previous local chats.
- Client can store user-managed local memory notes and include enabled notes as chat context.
- Archive and delete are distinct local session actions: archived chats are retained but hidden from active memory/research/compaction inputs unless restored or explicitly selected.
- Client can cancel generation.
- Only trusted devices can control the runtime host.
- Client never connects directly to Ollama or LM Studio.

## Private Peer Connectivity Direction

The concrete phased architecture is tracked in [connection-overlay.md](connection-overlay.md).

AetherLink's 1:1 connection model is Bitcoin-like only in the narrow sense of peer identity and discovery without relying on a single fixed address. It is not a public untrusted peer network. Only QR-paired trusted devices may discover, authenticate, and communicate with each other.

The target reconnect order is paired peer identity, local direct connection, remote P2P NAT traversal, then encrypted blind relay/TURN fallback. NAT traversal should use STUN-like address discovery, authenticated hole punching, short-lived candidate exchange, and session keys bound to the paired identities. Optional DHT/bootstrap-peer discovery may provide a Bitcoin-network-like feel for finding peers without a fixed IP, but only with privacy-preserving rendezvous records for already-paired devices. Relay/signaling infrastructure must remain unable to see AI protocol payloads, model lists, prompts, files, memory, backend credentials, or backend URLs. Clients still talk only to the trusted runtime/server boundary, never directly to Ollama, LM Studio, or future serving backends.

Current status: the code has trusted identities, endpoint hints, Bonjour/local discovery candidates, USB/dev local paths, and route-candidate plumbing. Those pieces are local-direct placeholders for the future connection manager. Production remote P2P NAT traversal, DHT/bootstrap rendezvous, signaling, encrypted blind relay transport, and production end-to-end transport encryption are not implemented yet.

## Current LM Studio Backend Support

- LM Studio is supported as a runtime-mediated local backend.
- Clients see LM Studio models through runtime health, `models.list`, and provider-prefixed `chat.send` model ids.
- LM Studio support is not MCP, memory, skills, web search, or direct client backend access.

## Future Project Workspaces

This is not v0.1 implementation scope. The product direction is a project/workspace feature similar to ChatGPT Projects, while preserving AetherLink's runtime boundary:

- Project-scoped chats, files, instructions, memories, indexes, and model/backend preferences.
- Trusted-source controls that let the user decide which files, folders, chats, notes, or external results can be used as project context.
- Project-level search and deep-research-like brief generation over indexed, user-approved material.
- Project indexes, retrieval, summarization, and research run through the runtime/server boundary, not directly from client apps.
- Mobile clients act as project controllers and approval/status surfaces; they do not call Ollama, LM Studio, future serving backends, file indexers, or tools directly.
- Project files and indexes are sensitive data and must pass through runtime permissions, source selection, audit logs, and archive/delete rules.

## Future Scheduling And Automation

This is not v0.1 implementation scope. Scheduling and automation should be runtime/server mediated:

- User-created scheduled tasks, reminders, monitors, recurring automations, and runtime-triggered jobs.
- Permission prompts before an automation can use sensitive project files, network access, tools, terminal execution, MCP, web search, or model backends.
- Audit logs for creation, edits, approvals, execution attempts, results, failures, and cancellations.
- Client apps provide approval, pause/resume, status, and result-review surfaces; they do not execute scheduled jobs or call backends/tools directly.
- Scheduled jobs are sensitive runtime actions because they can run later without the user actively watching the UI.

## v0.2 Session and Memory Polish

- Runtime-side SQLite conversation storage.
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
- Keep model residency policy in the runtime host, not Android UI code.
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
- Clients still talk only to the companion runtime.

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
- Future image inputs and file inputs are handled through the runtime host.
- Clients never send files or images directly to Ollama, LM Studio, future serving backends, or indexing services.

## v0.9 Scheduling And Automations

- Runtime/server scheduler for user-created scheduled tasks, reminders, monitors, recurring automations, and runtime-triggered jobs.
- Runtime permission broker prompts for actions that touch project files, tools, terminal, MCP, web search, network, or model backends.
- Audit log entries for automation definitions, approvals, runs, failures, cancellations, and permission changes.
- Mobile approval/status surfaces for reviewing, pausing, resuming, cancelling, and approving automation runs.
- Client apps remain controllers; scheduled jobs execute only through the trusted runtime/server.

## v1.0 Platform Expansion

- Runtime/server targets expand from runtime host first to Windows and DGX OS-class workstation/server support.
- Client/controller targets expand from Android first to iOS.
- Keep the same trust boundary: clients control sessions; runtime/server targets mediate all model access.
- Keep the same private P2P identity model across platforms so paired devices can reconnect across local and remote networks without exposing backend URLs or relying on OS-specific fixed endpoints or local-only discovery.

## v1.1 Serving Backend Expansion

- Add more AI serving backend adapters beyond Ollama and LM Studio.
- Preserve a common capability model for health, installed/running models, streaming chat, cancellation, embeddings, context windows, and structured errors.
- Avoid exposing backend-specific local URLs to mobile clients.
