# AetherLink Architecture

AetherLink is a local-first Android-to-Mac AI companion. The Mac owns runtime execution and backend access. Android controls the session and renders the UI.

## System Shape

```text
Android Client
  Pairing/connection UI
  Runtime status UI
  Model picker
  Chat UI
  Local chat history
  User-managed local memory notes
  Cancel control
        |
        | v0.1 local authenticated JSON transport
        | future encrypted P2P/pairing transport
        v
Mac Companion Runtime
  Transport listener
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

There is no cloud backend in v0.1. Android must not call Ollama or LM Studio directly.

## Future Platform Shape

The v0.1 implementation starts with a Mac companion runtime and Android client. The long-term product direction is broader:

- Runtime/server targets: macOS first, then Windows and DGX OS-class AI workstations or servers.
- Client/controller targets: Android first, then iOS.
- Serving backends: Ollama and LM Studio first, then additional local or self-hosted AI serving systems.

The invariant stays the same as platforms expand: client apps are controllers, and model serving is mediated by a trusted runtime/server. Mobile clients should not directly call backend-specific model URLs.

## Mac Companion Runtime

The Mac runtime is responsible for:

- Starting the local runtime transport.
- Receiving Android protocol messages.
- Checking runtime health.
- Listing models through backend adapters.
- Listing embedding models separately from chat/text-generation models.
- Returning installed backend models exactly as backend adapters report them, including Ollama cloud models from `/api/tags` and LM Studio local models from its Mac-side server.
- Pulling arbitrary Ollama model names through Mac-side pull requests.
- Forwarding chat requests to the active backend.
- Streaming response deltas back to Android.
- Cancelling in-flight generations.
- Managing model residency: unload the previous model before loading a newly selected model, and unload the active model after 10 or more minutes without chat activity.
- Owning trusted-device and pairing boundaries.

The runtime is also the future home for memory, file inputs, image inputs, internal Python tool execution, skills, MCP, web search, tool permissions, and audit logging.

## Android Client

The Android app is responsible for:

- Pairing/discovery UI.
- Connection status.
- Model selection.
- Install action that sends model pull requests to the Mac runtime.
- Chat input and transcript rendering.
- Previous chat list and local transcript restoration.
- User-managed local memory notes that can be included as chat context.
- Streaming delta rendering.
- Cancel action.
- Displaying runtime and backend errors.

Android sends high-level protocol messages only. It does not execute tools, read files, call MCP servers, perform web search, or call local model backend URLs. Android never calls Ollama `/api/tags`, `/api/ps`, `/api/pull`, `/api/chat`, or LM Studio endpoints directly. Android-side local memory is limited to user-managed notes and chat transcripts; when enabled, those notes are included in the same `chat.send` message path through the Mac runtime.

In Korean terms: Android는 조작 화면이고, Mac companion이 실행 경계입니다. Android가 Ollama/LM Studio 서버 주소를 직접 다루는 흐름은 v0.1 제품 방향이 아닙니다.

Future image inputs and file inputs follow the same boundary: Android may capture, choose, or approve inputs in the UI, but ingestion, parsing, indexing, and backend calls run through the Mac runtime. Android must not upload files or images directly to Ollama, LM Studio, future serving backends, or research/indexing services.

## Ollama Backend Adapter

The Mac-side adapter owns:

- Health check against `localhost:11434`.
- Model list via `/api/tags`.
- Running model detection via `/api/ps` when available.
- Model install via `/api/pull`.
- Streaming chat via `/api/chat`.
- Generation cancellation abstraction.
- Structured backend errors.

The adapter is behind a backend interface so the protocol and Android UI do not depend on Ollama-specific HTTP details.

The model list is backend-derived. Local Ollama models are the main path. AetherLink does not hardcode recommended/default local or cloud Ollama models when `/api/tags` is empty. Ollama cloud models are not generic suggestions; they are selectable installed models with `source = cloud` only after the user-side Ollama pull/sign-in flow makes local Mac `/api/tags` return them. Android still sends `models.pull` and `chat.send` to the Mac runtime, and only the Mac calls Ollama `/api/pull` or `/api/chat`.

## LM Studio Backend Adapter

LM Studio support is Mac-side local backend support. It is not direct Android access, not MCP, not memory, not skills, and not web search.

The Mac-side adapter owns:

- Health check against the local LM Studio server.
- Model list via native `GET /api/v1/models`, falling back to OpenAI-compatible `GET /v1/models` if native shape differs.
- Streaming chat via native `POST /api/v1/chat`, falling back to OpenAI-compatible `POST /v1/chat/completions` when needed.
- Generation cancellation through the same runtime cancellation registry shape as other backends.
- Structured errors for unavailable server, no models, bad backend responses, and cancelled generation.

LM Studio is started by the user on the Mac from the Developer tab or with `lms server start`. Android sees only Mac runtime protocol health, model metadata, streaming deltas, and cancellation results.

## Future Serving Backend Expansion

Additional serving backends should be added behind the runtime backend interface rather than exposed directly to mobile clients. Candidate categories include local OpenAI-compatible servers, vendor workstation runtimes, multi-GPU serving stacks, and future self-hosted inference gateways. Each backend must report health, model list, streaming chat, cancellation behavior, structured errors, and capability metadata through the shared runtime protocol.

## Future Memory, Research, Skills, MCP, And Web Search Layers

These layers are not v0.1:

- Memory: Mac-side session history, SQLite/FTS, long-term facts, and later vector retrieval.
- Project workspaces: project-scoped chats, files, instructions, memories, indexes, model/backend preferences, and trusted-source controls. The Mac/runtime/server owns indexing, retrieval, research, and backend calls; Android and iOS are controllers for choosing sources, approving access, and viewing status/results.
- Scheduling and automation: user-created scheduled tasks, reminders, monitors, recurring automations, and runtime-triggered jobs. The Mac/runtime/server owns the scheduler and job runner; mobile clients provide approval, status, pause/resume, cancellation, and result review surfaces.
- Archived sessions: archive is distinct from delete. Archived chats remain retained, but they are excluded from memory, reflection, research, and compaction inputs unless the user explicitly restores them or selects them as a source.
- Session compaction: when one conversation grows beyond a model context window, the Mac runtime should compact older turns into structured summaries while preserving recent messages, user-approved memories, reasoning summaries where useful, and citations back to original transcript segments. Longer inactivity criteria should later trigger modern compact memory summaries for chat history; this is separate from the 10 minute model-unload rule.
- Embedding and research: embedding models must be listed and selected separately from general text-generation/chat models. If the user registers or selects an embedding model, the Mac runtime can use that selected embedding model for retrieval, ranking, knowledge indexing, semantic search over prior chats, memory clustering, source collection notebooks, research briefs, duplicate finding, and citations over indexed local/user-approved material.
- Internal Python tools: deterministic tasks such as calculations may run through a future Mac-runtime Python execution tool. Runtime-side permissions, scoping, and audit logs govern this execution; Android remains only the approval and result surface.
- Skills: permissioned executable units loaded and run by the Mac runtime.
- MCP: Mac-side MCP host/client manager with Android approval UI.
- Web search: Mac-side provider abstraction with user-configured providers.

All future layers must go through the Mac runtime permission boundary. Android remains a controller and approval surface.

Project files, project indexes, scheduled jobs, and automation definitions are sensitive runtime-controlled assets. Access to them should be explicit, scoped to the project or job, revocable, and audit logged. A scheduled job must re-enter the same permission broker as an interactive action before it reads files, uses a model backend, runs a tool, performs web search, calls MCP, or executes terminal/Python work.

## Replaceable Transport

v0.1 may use a local socket transport while the product hardens authentication and encryption. The transport must stay replaceable:

- Protocol routing is separate from socket implementation.
- Runtime commands flow through a router rather than directly through UI code.
- Pairing/auth checks can be inserted before dispatch.
- Encrypted P2P or authenticated local socket can replace the development transport without changing Android feature screens.
- Same-network unauthenticated access remains forbidden even if discovery or pairing starts as a minimal v0.1 implementation.
