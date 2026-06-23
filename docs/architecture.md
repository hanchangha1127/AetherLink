# AetherLink Architecture

AetherLink is a local-first Android-to-Mac AI companion. The Mac owns runtime execution and backend access. Android controls the session and renders the UI.

## System Shape

```text
Android Client
  Pairing/connection UI
  Runtime status UI
  Model picker
  Chat UI
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
  Permission boundary for future tools
        |
        +--> Ollama Adapter -> local Ollama
        |
        +--> LM Studio Adapter -> local LM Studio server
```

There is no cloud backend in v0.1. Android must not call Ollama or LM Studio directly.

## Mac Companion Runtime

The Mac runtime is responsible for:

- Starting the local runtime transport.
- Receiving Android protocol messages.
- Checking runtime health.
- Listing models through backend adapters.
- Returning installed backend models exactly as backend adapters report them, including Ollama cloud models from `/api/tags` and LM Studio local models from its Mac-side server.
- Pulling arbitrary Ollama model names through Mac-side pull requests.
- Forwarding chat requests to the active backend.
- Streaming response deltas back to Android.
- Cancelling in-flight generations.
- Owning trusted-device and pairing boundaries.

The runtime is also the future home for memory, skills, MCP, web search, tool permissions, and audit logging.

## Android Client

The Android app is responsible for:

- Pairing/discovery UI.
- Connection status.
- Model selection.
- Install action that sends model pull requests to the Mac runtime.
- Chat input and transcript rendering.
- Streaming delta rendering.
- Cancel action.
- Displaying runtime and backend errors.

Android sends high-level protocol messages only. It does not execute tools, read files, call MCP servers, perform web search, or call local model backend URLs. Android never calls Ollama `/api/tags`, `/api/ps`, `/api/pull`, `/api/chat`, or LM Studio endpoints directly.

In Korean terms: Android는 조작 화면이고, Mac companion이 실행 경계입니다. Android가 Ollama/LM Studio 서버 주소를 직접 다루는 흐름은 v0.1 제품 방향이 아닙니다.

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

## Future Memory, Skills, MCP, And Web Search Layers

These layers are not v0.1:

- Memory: Mac-side session history, SQLite/FTS, long-term facts, and later vector retrieval.
- Skills: permissioned executable units loaded and run by the Mac runtime.
- MCP: Mac-side MCP host/client manager with Android approval UI.
- Web search: Mac-side provider abstraction with user-configured providers.

All future layers must go through the Mac runtime permission boundary. Android remains a controller and approval surface.

## Replaceable Transport

v0.1 may use a local socket transport while the product hardens authentication and encryption. The transport must stay replaceable:

- Protocol routing is separate from socket implementation.
- Runtime commands flow through a router rather than directly through UI code.
- Pairing/auth checks can be inserted before dispatch.
- Encrypted P2P or authenticated local socket can replace the development transport without changing Android feature screens.
- Same-network unauthenticated access remains forbidden even if discovery or pairing starts as a minimal v0.1 implementation.
