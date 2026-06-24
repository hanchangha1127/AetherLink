# AetherLink v0.1 - Local Chat Link

AetherLink v0.1 proves the smallest useful local loop: a client pairs with a companion runtime, the runtime host talks to local model backends, and the client receives streamed chat output. The current implementation uses an Android client and a macOS companion runtime, but there is no cloud backend and no direct client-to-Ollama or client-to-LM-Studio access.

## Exact Scope

- Companion runtime app runs the local runtime boundary.
- Client app acts as controller and chat UI.
- Runtime host mediates all model access.
- Ollama and LM Studio are runtime-mediated local model backends.
- Pairing uses a runtime-host-displayed QR code in v0.1; the accepted trusted runtime record persists on the client.
- Discovery remains scoped to pairing setup, while runtime access requires a trusted-device model and authenticated runtime session.
- The client can request runtime health, list models, select a chat model, separately select one embedding model for future retrieval features, send chat, receive streamed answer deltas, render preserved reasoning/think deltas separately as muted collapsible UI, request runtime-mediated suggested next questions, reopen previous local chats, manage user-entered local memory notes, and cancel generation.
- If archive is exposed in v0.1 local chat UX, archive is distinct from delete: archived chats are retained but excluded from memory/reflection/research/compaction inputs unless restored or explicitly selected later.
- Model listing includes installed Ollama models from runtime-host-side `/api/tags` and optional running state from runtime-host-side `/api/ps`; local models are the main path.
- Model listing includes LM Studio local LLM and embedding models from runtime-host-side LM Studio REST API responses; chat and embedding selection surfaces stay separate, and no LM Studio defaults are invented.
- Ollama cloud models are not default recommendations or generic suggestions. They remain installed/selectable only after the user-side Ollama pull/sign-in flow makes them appear in the runtime host's local `/api/tags` response.
- Pulling a model is runtime-mediated through `models.pull` and Ollama `/api/pull`; LM Studio downloads remain runtime-host user actions through LM Studio or `lms`. The client never calls Ollama or LM Studio URLs directly.
- Local development transport may use length-prefixed JSON over TCP. It must remain replaceable by a paired-device private P2P overlay later, and it must not turn same-network access, fixed IPs, or manual host entry into the product trust model.
- Product connectivity should be identity/key based, not address based: local direct connection first, remote P2P NAT traversal second, and end-to-end encrypted blind relay/TURN-style fallback only when direct paths fail.

## Non-Goals

- MCP.
- Skills.
- Web search.
- Advanced memory, embedding search, RAG, session search, automatic memory compaction, or file indexing.
- Project/workspace features such as project-scoped chats, files, instructions, memory, indexes, model/backend preferences, trusted-source controls, or project-level search/research.
- Scheduling and automation features such as scheduled tasks, reminders, monitors, recurring automations, runtime-triggered jobs, mobile approval queues, or automation audit logs.
- Context-window-aware session compaction.
- Deep-research-like retrieval, ranking, or knowledge indexing.
- Production-grade image/file indexing workflows and project source management.
- Terminal execution or file tool execution.
- Internal Python tool execution.
- Automatic model residency/resource policy beyond current backend behavior, including unload-after-inactivity.
- Cloud AI backend, account server, cloud sync, multi-user collaboration, or production remote connectivity infrastructure.
- A production relay/TURN fallback is not part of v0.1, but it remains a roadmap connection layer. If added later, it must be a blind encrypted transport relay only, not an AI backend or plaintext prompt/response proxy.
- Client-side local model execution.
- iOS client, Windows runtime/server, DGX OS-class runtime/server, or other companion targets.
- Additional AI serving backend adapters beyond Ollama and LM Studio.
- Production encryption UX beyond the architecture needed to add it safely.

## Acceptance Criteria

- Companion runtime starts a local runtime transport.
- Companion runtime displays a QR pairing code and pairing state.
- Client scans the QR code, receives accepted pairing, stores the trusted runtime, and restores it after app restart.
- Client connects to the runtime host transport without entering an Ollama or LM Studio URL.
- Runtime host can check whether Ollama and LM Studio are reachable through local backend adapters.
- Client can request `runtime.health` and display runtime/backend status.
- Client can send `models.list`; the runtime host returns installed Ollama models from `/api/tags`, installed LM Studio local LLMs from LM Studio, and may mark running models where backend metadata supports it.
- Client can select a model from the returned list.
- With no installed local models, the client shows an empty model list until a model is pulled through the runtime host or appears in a runtime-host-side backend list; no absent local or cloud defaults are invented.
- Client can request a model pull through `models.pull`; the runtime host performs Ollama `/api/pull`.
- After a successful pull, the model appears as installed in `models.list`.
- Client can send chat using the newly installed model.
- Client can send `chat.send`; the runtime host forwards the request to the selected local backend.
- Client can reopen local chat history from the drawer.
- Client can add, disable, and remove user-managed local memory notes; enabled notes are included only through the runtime-mediated `chat.send` path.
- Runtime host streams backend answer chunks back as `chat.delta`; Ollama reasoning/think chunks are preserved separately as reasoning deltas rather than mixed into final answer text.
- Runtime host sends `chat.done` when generation completes.
- Client can request runtime-mediated suggested next questions after `chat.done`; the runtime host returns `chat.suggestions.result`, and the client renders optional next-question chips without calling model backends directly.
- Client can send `chat.cancel`; the runtime host cancels the active generation abstraction.
- Runtime errors are returned as structured `error` messages and shown in Android UI.
- Untrusted clients receive `pairing_required` or `authentication_required` before runtime commands execute.
- README and docs clearly state v0.1 limitations and roadmap exclusions.

## Module List

- `apps/macos/LocalAgentBridgeApp`: SwiftUI shell branded as AetherLink for local runtime status, pairing, trusted devices, and logs.
- `apps/macos/CompanionCore`: runtime orchestration, protocol routing, authentication gating, and transport-to-backend dispatch.
- `apps/macos/Transport`: replaceable local transport.
- `apps/macos/OllamaBackend`: Ollama health, model list, streaming chat, cancellation, structured errors.
- `apps/macos/LMStudioBackend`: LM Studio health, model list, streaming chat, cancellation, structured errors.
- `apps/macos/Protocol`: Swift protocol envelope and frame codec.
- `apps/android/app`: Compose app shell, navigation, and runtime ViewModel.
- `apps/android/core/protocol`: Kotlin protocol envelope and payload models.
- `apps/android/core/transport`: Android client transport for the runtime host.
- `apps/android/core/pairing`: device identity and future trusted-pairing storage.
- `shared/protocol`: shared protocol documentation and future generated schema home.

## Implementation Sequence

1. Finalize v0.1 docs and protocol contracts.
2. Harden the Mac Ollama adapter tests for health, model list, streaming, cancellation, and structured errors.
3. Stabilize the Mac development transport and runtime message router.
4. Connect the companion runtime app lifecycle to start/stop the local runtime transport cleanly.
5. Implement Android runtime transport connection lifecycle and error mapping.
6. Wire Android `runtime.health` and connection status UI.
7. Wire Android `models.list`, model selection, and empty/error states.
8. Wire Android `chat.send`, `chat.delta`, and `chat.done` into the chat UI.
9. Wire Android `chat.cancel` and cancellation UI state.
10. Add acceptance notes and a smoke-test script for the first client/runtime v0.1 path.

## Manual Smoke Test

Use this as a human-readable acceptance pass until automated end-to-end tests exist:

1. Start Ollama and/or LM Studio on the runtime host. If no model is installed, confirm the model list is empty rather than populated with hardcoded defaults.
2. Launch the AetherLink Runtime companion and confirm local backend status is visible.
3. Open pairing on the runtime host and scan the QR code from the client.
4. Confirm the client stores the accepted runtime record and reconnects after app restart.
5. Confirm the client can list models without entering backend URLs.
6. If a model needs to be installed, request the pull from the client and verify the runtime host performs it.
7. Confirm the pulled model appears installed, then send a short chat prompt with that installed model.
8. Verify streamed deltas appear, then send another prompt and cancel it mid-generation.
9. Attempt a runtime command from an untrusted client and verify it is rejected before reaching Ollama.

## Automated Local Smokes

- `python3 script/runtime_smoke_test.py 127.0.0.1 43170` checks an already-running AetherLink/RuntimeDevServer rejects unauthenticated `runtime.health` and `models.list` with `authentication_required`.
- `./script/runtime_authenticated_mock_smoke.swift` starts RuntimeDevServer with `LOCAL_AGENT_BRIDGE_MOCK_BACKEND=1` and `AETHERLINK_DEV_PAIRING=1`, pairs a temporary P-256 device identity, authenticates a fresh connection, and verifies health, model list, streamed chat, cancellation, and no backend URL leakage.
- `./script/runtime_authenticated_mock_smoke.swift --real-ollama` starts RuntimeDevServer with the real local backend aggregate, uses the same development pairing/auth path, and verifies Ollama health plus installed/running model list merging without pulling or generating.

The authenticated mock smoke proves the local protocol loop after pairing/auth. It does not automate the physical QR camera scan.
