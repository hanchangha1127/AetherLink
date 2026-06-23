# AetherLink v0.1 - Local Chat Link

AetherLink v0.1 proves the smallest useful local loop: Android pairs with the Mac companion, the Mac talks to local model backends, and Android receives streamed chat output. There is no cloud backend and no direct Android-to-Ollama or Android-to-LM Studio access.

## Exact Scope

- Mac companion app runs the local runtime boundary.
- Android client app acts as controller and chat UI.
- Mac runtime mediates all model access.
- Ollama and LM Studio are Mac-mediated local model backends.
- Pairing uses a Mac-displayed QR code in v0.1; the accepted trusted Mac record persists on Android.
- Discovery remains scoped to pairing setup, while runtime access requires a trusted-device model and authenticated runtime session.
- Android can request runtime health, list models, select a model, send chat, receive streamed answer deltas, render preserved reasoning/think deltas separately as muted collapsible UI, and cancel generation.
- Model listing includes installed Ollama models from Mac `/api/tags` and optional running state from Mac `/api/ps`; local models are the main path.
- Model listing includes LM Studio local LLMs from Mac-side LM Studio REST API responses; no LM Studio defaults are invented.
- Ollama cloud models are not default recommendations or generic suggestions. They remain installed/selectable only after the user-side Ollama pull/sign-in flow makes them appear in the local Mac `/api/tags` response.
- Pulling a model is Mac-mediated through `models.pull` and Ollama `/api/pull`; LM Studio downloads remain Mac-side user actions through LM Studio or `lms`. Android never calls Ollama or LM Studio URLs directly.
- Local development transport may use length-prefixed JSON over TCP. It must remain replaceable by encrypted P2P/pairing transport later, and it must not turn same-network access into a trust model.

## Non-Goals

- MCP.
- Skills.
- Web search.
- Advanced memory, session search, RAG, or file indexing.
- Terminal execution or file tool execution.
- Cloud backend, remote relay, account server, cloud sync, or multi-user collaboration.
- Android-side local model execution.
- iOS, Windows, or Linux companion targets.
- Production encryption UX beyond the architecture needed to add it safely.

## Acceptance Criteria

- Mac companion starts a local runtime transport.
- Mac companion displays a QR pairing code and pairing state.
- Android scans the QR code, receives accepted pairing, stores the trusted Mac, and restores it after app restart.
- Android connects to the Mac runtime transport without entering an Ollama or LM Studio URL.
- Mac runtime can check whether Ollama and LM Studio are reachable through local Mac adapters.
- Android can request `runtime.health` and display runtime/backend status.
- Android can send `models.list`; Mac returns installed Ollama models from `/api/tags`, installed LM Studio local LLMs from LM Studio, and may mark running models where backend metadata supports it.
- Android can select a model from the returned list.
- With no installed local models, Android shows an empty model list until a model is pulled through the Mac runtime or appears in a Mac-side backend list; no absent local or cloud defaults are invented.
- Android can request a model pull through `models.pull`; the Mac performs Ollama `/api/pull`.
- After a successful pull, the model appears as installed in `models.list`.
- Android can send chat using the newly installed model.
- Android can send `chat.send`; Mac forwards the request to the selected local backend.
- Mac streams backend answer chunks back as `chat.delta`; Ollama reasoning/think chunks are preserved separately as reasoning deltas rather than mixed into final answer text.
- Mac sends `chat.done` when generation completes.
- Android can send `chat.cancel`; Mac cancels the active generation abstraction.
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
- `apps/android/core/transport`: Android client transport for the Mac runtime.
- `apps/android/core/pairing`: device identity and future trusted-pairing storage.
- `shared/protocol`: shared protocol documentation and future generated schema home.

## Implementation Sequence

1. Finalize v0.1 docs and protocol contracts.
2. Harden the Mac Ollama adapter tests for health, model list, streaming, cancellation, and structured errors.
3. Stabilize the Mac development transport and runtime message router.
4. Connect the Mac companion app lifecycle to start/stop the local runtime transport cleanly.
5. Implement Android runtime transport connection lifecycle and error mapping.
6. Wire Android `runtime.health` and connection status UI.
7. Wire Android `models.list`, model selection, and empty/error states.
8. Wire Android `chat.send`, `chat.delta`, and `chat.done` into the chat UI.
9. Wire Android `chat.cancel` and cancellation UI state.
10. Add acceptance notes and a smoke-test script for Mac + Android v0.1.

## Manual Smoke Test

Use this as a human-readable acceptance pass until automated end-to-end tests exist:

1. Start Ollama and/or LM Studio on the Mac. If no model is installed, confirm the model list is empty rather than populated with hardcoded defaults.
2. Launch the AetherLink Mac companion and confirm local backend status is visible.
3. Open pairing on the Mac and scan the QR code from Android.
4. Confirm Android stores the accepted Mac record and reconnects after app restart.
5. Confirm Android can list models without entering backend URLs.
6. If a model needs to be installed, request the pull from Android and verify the Mac performs it.
7. Confirm the pulled model appears installed, then send a short chat prompt with that installed model.
8. Verify streamed deltas appear, then send another prompt and cancel it mid-generation.
9. Attempt a runtime command from an untrusted client and verify it is rejected before reaching Ollama.

## Automated Local Smokes

- `python3 script/runtime_smoke_test.py 127.0.0.1 43170` checks an already-running AetherLink/RuntimeDevServer rejects unauthenticated `runtime.health` and `models.list` with `authentication_required`.
- `./script/runtime_authenticated_mock_smoke.swift` starts RuntimeDevServer with `LOCAL_AGENT_BRIDGE_MOCK_BACKEND=1` and `AETHERLINK_DEV_PAIRING=1`, pairs a temporary P-256 device identity, authenticates a fresh connection, and verifies health, model list, streamed chat, cancellation, and no backend URL leakage.
- `./script/runtime_authenticated_mock_smoke.swift --real-ollama` starts RuntimeDevServer with the real local backend aggregate, uses the same development pairing/auth path, and verifies Ollama health plus installed/running model list merging without pulling or generating.

The authenticated mock smoke proves the local protocol loop after pairing/auth. It does not automate the physical QR camera scan.
