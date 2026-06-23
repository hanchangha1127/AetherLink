# Roadmap

## v0.1 Local Chat Link

- Android scans a Mac-displayed QR code and pairs with the Mac companion.
- Mac detects Ollama health.
- Mac lists Ollama models.
- Android selects a model and sends chat messages.
- Mac streams Ollama responses back to Android.
- Mac preserves Ollama reasoning/think chunks separately from final answer text.
- Android shows reasoning/think text in a muted, compact section that expands on demand.
- Android can reopen previous local chats.
- Android can store user-managed local memory notes and include enabled notes as chat context.
- Archive and delete are distinct local session actions: archived chats are retained but hidden from active memory/research/compaction inputs unless restored or explicitly selected.
- Android can cancel generation.
- Only trusted devices can control the Mac runtime.
- Android never connects directly to Ollama or LM Studio.

## Current LM Studio Backend Support

- LM Studio is supported as a Mac-mediated local backend.
- Android sees LM Studio models through runtime health, `models.list`, and provider-prefixed `chat.send` model ids.
- LM Studio support is not MCP, memory, skills, web search, or direct Android backend access.

## Future Project Workspaces

This is not v0.1 implementation scope. The product direction is a project/workspace feature similar to ChatGPT Projects, while preserving AetherLink's runtime boundary:

- Project-scoped chats, files, instructions, memories, indexes, and model/backend preferences.
- Trusted-source controls that let the user decide which files, folders, chats, notes, or external results can be used as project context.
- Project-level search and deep-research-like brief generation over indexed, user-approved material.
- Project indexes, retrieval, summarization, and research run through the Mac/runtime/server, not directly from Android or iOS.
- Mobile clients act as project controllers and approval/status surfaces; they do not call Ollama, LM Studio, future serving backends, file indexers, or tools directly.
- Project files and indexes are sensitive data and must pass through runtime permissions, source selection, audit logs, and archive/delete rules.

## Future Scheduling And Automation

This is not v0.1 implementation scope. Scheduling and automation should be Mac/runtime/server mediated:

- User-created scheduled tasks, reminders, monitors, recurring automations, and runtime-triggered jobs.
- Permission prompts before an automation can use sensitive project files, network access, tools, terminal execution, MCP, web search, or model backends.
- Audit logs for creation, edits, approvals, execution attempts, results, failures, and cancellations.
- Android and iOS provide approval, pause/resume, status, and result-review surfaces; they do not execute scheduled jobs or call backends/tools directly.
- Scheduled jobs are sensitive runtime actions because they can run later without the user actively watching the UI.

## v0.2 Session and Memory Polish

- Mac-side SQLite conversation storage.
- Session list, rename, delete, and search.
- Android session list polish, rename, delete, and search.
- Archive polish: archived chats remain retained but excluded from memory, reflection, research, and compaction inputs unless the user restores them or explicitly selects them as sources.
- Preserve reasoning/think text separately from final assistant answer text in session storage.
- Context-window-aware session compaction: when a conversation grows beyond the selected model context window, compact older turns into summaries while keeping recent messages and source pointers.
- Longer-inactivity memory summarization: define inactivity criteria that summarize chat history into modern compact memory summaries. This is separate from short model-unload inactivity.

## v0.2 Runtime Resource Policy

- When switching models, unload the previous model before loading the newly selected model.
- If there is no chat activity for 10 or more minutes, unload the active model.
- Keep model residency policy in the Mac runtime, not Android UI code.

## v0.3 Embeddings And Research Notes

- Optional embedding model registration on the Mac runtime.
- Embedding models are listed and selected separately from general text-generation/chat models.
- Semantic search over prior chats and user-approved notes.
- Memory clustering and deduplication suggestions.
- Retrieval, ranking, and knowledge indexing use the selected embedding model.
- Deep-research-like brief generation from indexed local/user-approved material.
- Research notebook sessions with source snippets, citations, and follow-up questions.
- Embedding-powered recall remains Mac-mediated; Android stays the controller UI.

## v0.4 Backend Selection Polish

- Backend selector and model capability display.
- Android still talks only to the Mac companion runtime.

## v0.5 Permission Broker and Skills

- Mac-side permission model.
- Prompt-only skill registry.
- Approval-required actions.
- Internal Python tool execution through the Mac runtime for deterministic tasks such as calculations.
- Runtime-side permissions and audit logs for Python, file, terminal, skills, MCP, and web-search actions.
- Advanced memory and skill execution remain roadmap items, not v0.1 implementation scope.

## v0.6 Web Search

- Mac-side web search provider abstraction.
- SearXNG/custom endpoint first.
- Search result cache and citation-ready metadata.
- Web search remains a roadmap item, not v0.1 implementation scope.

## v0.7 MCP

- Mac-side MCP server registry and client manager.
- Android tool approval and result views.
- MCP remains a roadmap item, not v0.1 implementation scope.

## v0.8 Workspace/RAG

- Project/workspace registration with scoped instructions, files, memory, indexes, and model/backend preferences.
- File indexer and document chunking for user-approved project sources.
- Search over indexed files, prior project chats, and trusted project memory.
- Trusted-source controls for selecting which folders, files, chats, notes, or external results can feed retrieval and research.
- Eventual project-level search and research reports with source snippets and citations.
- Future image inputs and file inputs are handled through the Mac runtime.
- Android never sends files or images directly to Ollama, LM Studio, future serving backends, or indexing services.

## v0.9 Scheduling And Automations

- Mac/runtime/server scheduler for user-created scheduled tasks, reminders, monitors, recurring automations, and runtime-triggered jobs.
- Runtime permission broker prompts for actions that touch project files, tools, terminal, MCP, web search, network, or model backends.
- Audit log entries for automation definitions, approvals, runs, failures, cancellations, and permission changes.
- Mobile approval/status surfaces for reviewing, pausing, resuming, cancelling, and approving automation runs.
- Android and iOS remain controllers; scheduled jobs execute only through the trusted runtime/server.

## v1.0 Platform Expansion

- Runtime/server targets expand from Mac runtime first to Windows and DGX OS-class workstation/server support.
- Client/controller targets expand from Android first to iOS.
- Keep the same trust boundary: clients control sessions; runtime/server targets mediate all model access.

## v1.1 Serving Backend Expansion

- Add more AI serving backend adapters beyond Ollama and LM Studio.
- Preserve a common capability model for health, installed/running models, streaming chat, cancellation, embeddings, context windows, and structured errors.
- Avoid exposing backend-specific local URLs to mobile clients.
