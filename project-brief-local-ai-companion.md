Project Brief for Codex

0. Project Summary

We are building an open-source, local-first AI application that connects a Mac and an Android device directly.

The Mac runs the local AI runtime.
The Android app acts as the mobile chat/control client.

The first target is:

* Mac runs Ollama and/or LM Studio locally.
* Android connects to the Mac companion app.
* The user chats from Android.
* Inference happens on the Mac.
* No cloud backend.
* No account server.
* No mandatory remote API.
* Device-to-device connection only.

This is not a simple Ollama HTTP client.
This is the foundation for a local AI agent workspace similar in ambition to Odysseus: memory, skills, MCP, web search, and tool execution should be supported later.

1. Core Architecture

The system must be split into two apps:

Android App
  - Chat UI
  - Pairing UI
  - Session UI
  - Tool approval UI
  - Model picker
  - Memory viewer/editor later
        ⇅ Encrypted local P2P protocol
Mac Companion Runtime
  - Device pairing
  - Local peer server
  - Ollama adapter
  - LM Studio adapter
  - Agent orchestrator
  - Memory engine
  - Skill engine
  - MCP manager
  - Web search module
  - Permission broker
  - Audit log

The Mac app is the real runtime.
The Android app is the client/controller.

The Android app must not call Ollama or LM Studio directly by requiring the user to enter a local web URL like http://192.168.x.x:11434.

Instead, the Android app should pair with the Mac companion app first.

2. Connectivity Requirements

The intended user experience:

1. User opens the Mac companion app.
2. User opens the Android app.
3. Android discovers nearby Mac companion app.
4. User pairs the devices.
5. After pairing, Android can chat with models running on the Mac.
6. The user does not manually type IP addresses or local URLs.

Recommended technical structure:

Pairing/discovery:
- Bluetooth LE, QR code, or mDNS/Bonjour
Actual data channel:
- Local network socket over Wi-Fi/LAN
- Encrypted
- Device-authenticated

Bluetooth should be used only for discovery/pairing/key exchange if implemented.
Do not try to stream full LLM responses over BLE as the main transport.

The design should allow:

* Same Wi-Fi mode
* Android hotspot mode
* Future offline LAN/P2P mode
* Future relay mode only as optional, not required

3. Security Requirements

Security must be built into the design from the start.

Minimum requirements:

* Pairing must require user confirmation.
* Use a 6-digit pairing code or QR-based pairing.
* Each device should have a persistent device identity.
* Store trusted device public keys.
* Only paired Android devices can control the Mac runtime.
* Each connection must be encrypted.
* Mac app must have a “Remove trusted device” option.
* Tool execution must require explicit permission when dangerous.
* File access, terminal access, MCP tools, and web access must be permission-scoped.
* Keep an audit log of tool calls and sensitive actions.

Do not implement a design where any device on the same Wi-Fi can access the Mac runtime.

4. AI Backend Requirements

The Mac companion should support pluggable LLM backends.

Initial backend:

Ollama

Next backend:

LM Studio

Future backend:

OpenAI-compatible local servers
llama.cpp server
Remote APIs only as optional plugins

The LLM backend layer should be abstracted.

Suggested interface:

interface LlmBackend {
    suspend fun listModels(): List<ModelInfo>
    suspend fun chat(request: ChatRequest): Flow<ChatDelta>
    suspend fun cancel(generationId: String)
    suspend fun healthCheck(): BackendStatus
}

For the Mac app, the actual implementation may be in Swift, Kotlin, Rust, or TypeScript, but the architecture should preserve this abstraction.

5. Agent Runtime Requirements

Do not put agent logic inside the Android app.

The Mac companion runtime should eventually contain:

Agent Runtime
├─ LLM Backend Adapters
├─ Conversation Manager
├─ Memory Engine
├─ Skill Engine
├─ MCP Manager
├─ Web Search Module
├─ File/RAG Indexer
├─ Permission Broker
└─ Audit Log

The Android app should send high-level requests:

Send message
Cancel generation
List models
Switch model
Approve tool call
Reject tool call
View memory
Edit memory
List skills
Run skill

The Android app should not execute MCP tools directly.

6. Memory Roadmap

Memory should be Mac-side.

Memory types:

Short-term memory:
- Current conversation context
Conversation memory:
- Past chat history
- Searchable sessions
Long-term memory:
- User preferences
- Persistent facts
- Project information
Document memory:
- Indexed files
- Notes
- RAG chunks
Tool memory:
- Tool usage history
- MCP tool success/failure logs

Initial implementation:

SQLite + FTS

Later implementation:

SQLite + FTS + vector search
Hybrid search
Embedding-based retrieval

7. Skills Roadmap

Skills should be implemented as permissioned executable units.

Suggested skill structure:

skill/
├─ manifest.json
├─ prompt.md
├─ input_schema.json
├─ output_schema.json
├─ permissions.json
└─ runner

Skill manifest should include:

{
  "id": "summarize_document",
  "name": "Summarize Document",
  "description": "Summarizes a local document.",
  "permissions": ["file.read"],
  "requires_user_approval": false
}

Dangerous permissions must require approval:

file.write
terminal.execute
network.access
mcp.call
calendar.write
email.send

8. MCP Roadmap

MCP support should be added after core chat and memory are stable.

Mac companion runtime should act as:

MCP Host / MCP Client Manager

Android should act only as UI for:

- Listing MCP servers
- Listing MCP tools/resources/prompts
- Approving tool calls
- Viewing results
- Disabling tools

MCP tool execution must go through the Permission Broker.

9. Web Search Roadmap

Web search is not part of the v0.1 MVP.

Future web search should be Mac-side.

Provider adapter design:

WebSearchProvider
├─ SearXNG
├─ Brave Search
├─ Tavily
├─ SerpAPI
└─ Custom endpoint

The app has no central server, but user-configured search providers may access the internet.

Search results should include:

* Title
* URL
* Snippet
* Fetch status
* Parsed content
* Citation metadata
* Cache timestamp

10. Development Milestones

v0.1 — Local Chat Link

Goal: Android can pair with Mac and chat with an Ollama model running on the Mac.

Required:

Mac companion:

* Basic app shell
* Local runtime process
* Ollama health check
* Ollama model list
* Ollama chat streaming
* Trusted device store
* Pairing flow placeholder or QR pairing
* Local encrypted socket or initial local socket abstraction

Android:

* Basic Compose app
* Pairing screen
* Connection status
* Model picker
* Chat screen
* Streaming response rendering
* Cancel generation
* Basic settings persistence

Do not include yet:

* MCP
* Full memory
* Web search
* Skills
* File indexing
* Terminal execution

v0.2 — Session and Memory Base

Required:

Mac:

* Conversation storage
* SQLite database
* Session list
* Message history
* FTS search

Android:

* Session list UI
* Resume old chat
* Delete chat
* Rename chat
* Search chats

v0.3 — LM Studio Support

Required:

Mac:

* LM Studio backend adapter
* OpenAI-compatible chat completions adapter
* Model capability metadata
* Backend selection

Android:

* Backend selector
* Model capability display
* Error display for unsupported features

v0.4 — Permission Broker and Skills

Required:

Mac:

* Permission model
* Skill manifest loader
* Prompt-only skills
* Local skill registry
* Approval-required actions

Android:

* Skill list
* Run skill
* Approve/reject tool request
* View skill output

v0.5 — Web Search

Required:

Mac:

* WebSearchProvider abstraction
* SearXNG/custom endpoint first
* Search result cache
* Source metadata
* Citation-ready response format

Android:

* Toggle web search
* Show sources
* Open source URL
* Clear search cache

v0.6 — MCP

Required:

Mac:

* MCP server registry
* MCP client manager
* List tools/resources/prompts
* Execute MCP tools through Permission Broker
* Audit log

Android:

* MCP server list
* Tool approval UI
* Tool result viewer
* Enable/disable MCP servers

v0.7 — Workspace/RAG

Required:

Mac:

* Project folder registration
* File indexer
* Document chunking
* Search over indexed files
* Later vector retrieval

Android:

* Project selector
* File search UI
* Attach context from project
* Show retrieved context

11. Suggested Repository Structure

Use a monorepo.

local-agent-bridge/
├─ apps/
│  ├─ android/
│  │  ├─ app/
│  │  └─ README.md
│  └─ macos/
│     ├─ App/
│     └─ README.md
├─ crates-or-packages/
│  ├─ protocol/
│  ├─ agent-core/
│  ├─ llm-backends/
│  ├─ memory/
│  ├─ skills/
│  ├─ mcp/
│  └─ web-search/
├─ docs/
│  ├─ architecture.md
│  ├─ protocol.md
│  ├─ security.md
│  ├─ roadmap.md
│  └─ mvp.md
├─ examples/
├─ LICENSE
└─ README.md

If using Kotlin Multiplatform:

shared/
├─ protocol
├─ models
└─ serialization

If using Rust core:

crates/
├─ protocol
├─ agent-core
├─ memory
├─ llm-backends
└─ transport

12. Recommended Tech Stack

Android:

Kotlin
Jetpack Compose
Coroutines
Flow
DataStore
Room later if local Android cache is needed

Mac:

Preferred native option:

Swift
SwiftUI
MenuBarExtra
Network.framework
Core Bluetooth
SQLite

Alternative runtime-heavy option:

Rust core
Swift macOS shell
Kotlin Android client

For open-source maintainability, consider:

Rust shared core + Swift macOS wrapper + Kotlin Android app

But for fastest MVP, use:

Swift macOS companion + Kotlin Android app

13. Protocol Design

Define a typed protocol between Android and Mac.

Basic message types:

{
  "type": "chat.send",
  "request_id": "uuid",
  "session_id": "uuid",
  "model": "llama3.1:8b",
  "messages": []
}

Streaming response:

{
  "type": "chat.delta",
  "request_id": "uuid",
  "delta": "text chunk"
}

Completion:

{
  "type": "chat.done",
  "request_id": "uuid",
  "usage": {
    "input_tokens": 0,
    "output_tokens": 0
  }
}

Error:

{
  "type": "error",
  "request_id": "uuid",
  "code": "backend_unavailable",
  "message": "Ollama is not running."
}

Tool approval request:

{
  "type": "tool.approval_required",
  "request_id": "uuid",
  "tool_call_id": "uuid",
  "tool_name": "filesystem.write",
  "risk_level": "high",
  "description": "The assistant wants to write a file.",
  "input_preview": {}
}

Approval response:

{
  "type": "tool.approval_response",
  "tool_call_id": "uuid",
  "approved": true
}

14. v0.1 Acceptance Criteria

v0.1 is complete only if:

* Mac app can detect Ollama running locally.
* Mac app can list Ollama models.
* Android can pair/connect to Mac without manually entering an Ollama URL.
* Android can select a model.
* Android can send a chat message.
* Mac forwards the message to Ollama.
* Android receives streamed response chunks.
* Android can cancel generation.
* Connection errors are shown clearly.
* Only trusted/paired Android devices are allowed.
* Basic README explains setup and limitations.

15. Non-Goals for v0.1

Do not implement these in v0.1:

* Full MCP
* Full skill system
* Web search
* File indexing
* Terminal execution
* Cloud sync
* User accounts
* Remote relay server
* Multi-user collaboration
* Android-side local model execution
* iOS support
* Windows support

16. Design Principle

The project should be designed as:

Local-first
Serverless by default
Mac-powered
Android-controlled
Permissioned
Extensible
Open-source friendly

The first MVP should prove the core loop:

Pair Android with Mac
→ select local model
→ chat from Android
→ infer on Mac
→ stream response back

Everything else should be layered after this loop is stable.