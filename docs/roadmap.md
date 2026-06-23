# Roadmap

## v0.1 Local Chat Link

- Android scans a Mac-displayed QR code and pairs with the Mac companion.
- Mac detects Ollama health.
- Mac lists Ollama models.
- Android selects a model and sends chat messages.
- Mac streams Ollama responses back to Android.
- Mac preserves Ollama reasoning/think chunks separately from final answer text.
- Android shows reasoning/think text in a muted, compact section that expands on demand.
- Android can cancel generation.
- Only trusted devices can control the Mac runtime.
- Android never connects directly to Ollama or LM Studio.

## Current LM Studio Backend Support

- LM Studio is supported as a Mac-mediated local backend.
- Android sees LM Studio models through runtime health, `models.list`, and provider-prefixed `chat.send` model ids.
- LM Studio support is not MCP, memory, skills, web search, or direct Android backend access.

## v0.2 Session and Memory Base

- Mac-side SQLite conversation storage.
- Session list, rename, delete, and search.
- Android session list and resume UI.
- Preserve reasoning/think text separately from final assistant answer text in session storage.

## v0.3 Backend Selection Polish

- Backend selector and model capability display.
- Android still talks only to the Mac companion runtime.

## v0.4 Permission Broker and Skills

- Mac-side permission model.
- Prompt-only skill registry.
- Approval-required actions.
- Advanced memory and skill execution remain roadmap items, not v0.1 implementation scope.

## v0.5 Web Search

- Mac-side web search provider abstraction.
- SearXNG/custom endpoint first.
- Search result cache and citation-ready metadata.
- Web search remains a roadmap item, not v0.1 implementation scope.

## v0.6 MCP

- Mac-side MCP server registry and client manager.
- Android tool approval and result views.
- MCP remains a roadmap item, not v0.1 implementation scope.

## v0.7 Workspace/RAG

- Project folder registration.
- File indexer and document chunking.
- Search over indexed files.
