# AetherLink Security Model

The project is local-first: no cloud backend, no account server, and no default remote relay. The Mac is the runtime. Android is a controller/client. That split is the main security boundary.

## Local-First Threat Model

Assets to protect:

- Mac runtime access.
- Local model prompts and responses.
- Android-local chat history and user-managed memory notes.
- Future compacted session summaries and embedding indexes.
- Future project files, project instructions, trusted-source settings, and project indexes.
- Future scheduled tasks, reminders, monitors, recurring automations, runtime-triggered jobs, mobile approvals, and audit logs.
- Trusted device identities.
- Future memory, files, image inputs, Python tool calls, MCP calls, and audit logs.

Primary threats:

- Any device on the same Wi-Fi attempts to control the Mac runtime.
- A malicious client sends protocol messages directly to the local transport.
- A paired phone is lost or should no longer be trusted.
- Local chat history, memory notes, compacted summaries, or embedding indexes leak from a device backup or filesystem.
- Project files or indexes are used as model/research context without project-scoped permission or trusted-source selection.
- A scheduled job runs later with broader file, network, tool, MCP, web search, or backend access than the user approved.
- Future tool execution gains file, terminal, network, or MCP access without explicit permission.
- Future image or file input flows bypass the Mac runtime and send user data directly to a serving backend.
- A future cloud/relay shortcut weakens the local-first guarantee.

v0.1 may use a small development transport while the product matures, but it must not normalize unauthenticated same-network runtime access as the product model.

## Trusted Devices

The target design is persistent device identity on both sides:

- Mac has a stable device id and keypair.
- Android has a stable device id and keypair.
- Mac stores trusted Android public keys.
- Android pins the trusted Mac identity.
- Mac exposes remove-trusted-device controls.

Pairing creates the persistent trust record used by later runtime sessions. Removing a trusted device invalidates future authentication attempts from that Android identity.

## Pairing Design

Target pairing flow:

1. User opens pairing on the Mac companion.
2. Mac displays a QR code plus a one-time pairing code.
3. QR pairing data includes Mac device id, pairing nonce, service identity, and Mac public key or certificate fingerprint.
4. Android submits pairing nonce, code, Android device id, Android device name, and Android public key.
5. Mac stores the Android public key only if the pairing window is active and user confirmation succeeds.
6. Future sessions use challenge-response authentication before runtime commands.

v0.1 persists the scanned trusted Mac record on Android only after the Mac accepts `pairing.request` and stores the Android device as trusted. Android connects to the Mac runtime, not to Ollama or LM Studio directly.

An active pairing session allows only a bounded number of invalid nonce/code submissions. After the limit is reached, the Mac invalidates that pairing session and returns structured `pairing.result` rejection details while preserving the existing `accepted: false` response shape.

Implementation note: QR pairing and discovery can be simple in v0.1, but the docs must remain clear that the trusted-device gate is required before runtime commands execute.

Development note: `AETHERLINK_DEV_PAIRING=1` is only for local automated smoke tests with RuntimeDevServer. It opens and prints a temporary pairing session for scripts, but runtime commands still require the normal pairing/trusted-device and challenge-response path. Do not enable this flag for production or normal trusted-device use.

## Session Authentication

After pairing, each runtime connection authenticates before model or command messages are accepted:

1. Android sends `hello` with its trusted device id.
2. Mac checks the trusted-device store and returns `auth.challenge` with a one-time nonce.
3. Android signs the nonce with its paired private key and sends `auth.response`.
4. Mac verifies the signature against the stored Android public key.
5. Mac allows runtime commands only after the connection is authenticated.

Runtime commands include `runtime.health`, `models.list`, `models.pull`, `chat.send`, and `chat.cancel`. Requests sent before authentication fail with `authentication_required`; unknown or removed device ids fail with `pairing_required`; invalid signatures fail with `authentication_failed`.

## Local Chat History, Memory, And Compaction

v0.1 can store previous Android chats and user-managed memory notes locally on the phone. Enabled memory notes are sent only as context inside `chat.send`, which still goes through the authenticated Mac runtime. Android must not use memory features to call Ollama, LM Studio, web search, MCP, or tools directly.

Archive is not deletion. Archived chats remain retained, but they are excluded from memory, reflection, research, and compaction inputs unless the user explicitly restores them or selects them as sources. Deleted chats should be treated as removal requests, not hidden research material.

Future Mac-side session storage, context-window compaction, embedding indexes, and deep-research-like research notebooks are sensitive data. A compacted summary or embedding index can still reveal private transcript content, so it must follow the same local-first storage, trusted-device, archive/delete, and future encryption rules as raw chat transcripts.

Embedding models must be selected separately from chat/text-generation models. Future retrieval, ranking, and knowledge indexing use the selected embedding model, and indexed sources must respect archive/delete state.

Short model inactivity and long memory inactivity are separate policies. The runtime may unload the active model after 10 or more minutes without chat activity. Longer inactivity criteria can later create compact memory summaries, but archived sessions stay excluded unless the user restores or selects them.

## Future Files, Images, And Python Tools

Future file inputs and image inputs must be mediated by the Mac runtime. Android can provide UI for choosing or approving inputs, but Android must not send those inputs directly to Ollama, LM Studio, future serving backends, or indexing services.

Future internal Python execution is a Mac-runtime tool for deterministic tasks such as calculations. The runtime must own permissions, filesystem/network scope, audit logs, and result reporting. Android remains the approval and display surface.

## Future Project And Automation Security

Project/workspace features are permissioned runtime features, not v0.1 client-only state. Project-scoped chats, files, instructions, memories, indexes, model/backend preferences, trusted-source settings, and project-level search/research must be owned by the Mac/runtime/server boundary. Android and iOS can select sources, request searches, approve actions, and display status, but they must not call file indexers, research tools, Ollama, LM Studio, future serving backends, MCP, or web search directly.

Scheduled tasks, reminders, monitors, recurring automations, and runtime-triggered jobs are also permissioned runtime actions. They can run when the user is not actively watching the UI, so each job definition must store a narrow permission scope, require explicit approval for sensitive capabilities, and write audit records for creation, edits, approvals, execution, failures, cancellations, and permission changes.

Project files and scheduled jobs are sensitive by default. A scheduled job that reads project files, uses project indexes, calls a model backend, runs Python or terminal work, performs web search, or invokes MCP must pass through the same Mac-side permission broker as an interactive request. Mobile approval/status surfaces should be treated as controllers only; approval does not move execution to the phone.

## Encryption Roadmap

v0.1 development transport:

- Local network socket with length-prefixed JSON.
- Clear runtime module boundary so transport can be replaced.
- No direct backend URL exposed to Android.
- Runtime commands rejected until the device is trusted and authenticated.

Hardening roadmap:

- TLS or Noise-style encrypted channel between Android and Mac.
- Mac identity pinning on Android.
- Android public-key challenge-response on Mac.
- Session keys derived after pairing.
- Protocol commands rejected until authenticated.
- Optional BLE/QR/mDNS only for discovery or key exchange, not LLM streaming.

## Same-Network Unauthenticated Access Is Forbidden

Same Wi-Fi is not a trust boundary. A guest phone, compromised laptop, or any local network process could otherwise send `chat.send`, list models, or later trigger tools.

Therefore:

- Runtime commands must require a trusted-device check and successful challenge-response authentication.
- Ollama remains bound to the Mac runtime adapter and is never exposed as the Android API. Android must not call Ollama `/api/tags`, `/api/ps`, `/api/pull`, `/api/chat`, or LM Studio endpoints directly.
- Model installation is also a runtime command: Android may request `models.pull`, but only the authenticated Mac runtime may call Ollama `/api/pull`.
- Future file, image, Python, terminal, MCP, skills, and web search actions must pass through a Mac-side permission broker and audit log.
