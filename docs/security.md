# AetherLink Security Model

The project is local-first: no cloud AI backend and no account-server requirement for model access. The runtime host owns execution and backend access. The client device is a controller/client. That split is the main security boundary. The current v0.1 implementation has desktop-runtime and mobile-client targets.

AetherLink may later use distributed rendezvous/bootstrap/DHT-style discovery, signaling, or an encrypted blind relay/TURN-style component for connectivity when paired devices are on different networks. That component is connection infrastructure only: it must not run models, proxy backend APIs in plaintext, inspect AI protocol payloads, store prompts/responses, see model lists, files, memory, or backend credentials, or become a cloud AI backend, account backend, or model-logic backend.

Current code status: remote P2P NAT traversal, decentralized/distributed rendezvous, hardened blind relay allocation, and production end-to-end transport encryption are not complete yet. Existing endpoint hints, Bonjour/mDNS records, USB reverse paths, localhost/dev-server flows, Android opaque `p2p_rendezvous` route persistence/planning/diagnostic refresh validation, and the outbound TCP development relay are development scaffolding behind the trusted-device boundary. QR-provisioned relay routes require pairwise route material including `relay_secret`, `relay_expires_at`, and `relay_nonce`; `relay_secret` plus `relay_nonce` derive the AES-GCM relay-frame key so AetherLink frame bodies are encrypted before relay forwarding and stale or mismatched QR route material can be rejected. Android P2P rendezvous records are stored only as complete opaque, expiring route material bound to the pinned runtime identity, whether they arrive through QR or explicitly enabled authenticated `route.refresh`; they are not trust authority, candidate exchange, decrypted payloads, STUN, hole punching, or a real P2P connector. Android product defaults do not advertise or automatically send authenticated `route.refresh`, so normal route repair stays latest-QR scan first. The development relay requires allocation by default, rejects unknown or expired relay ids, and can require an allocation token before it issues route material, which is useful for public/VPN/tunnel relay testing, but that token is only allocation gating and not device trust. For a stable relay id, non-advancing renewal attempts for the same relay id are ignored unless the lease expiry advances and the relay nonce changes; persisted allocation-store loading also skips malformed ticket entries and deduplicates duplicate relay ids with the same rule. The macOS runtime host applies the same advancing lease rule before replacing saved same-relay bootstrap lease material that can feed QR generation or diagnostic route refresh. That is only a foundation slice, not the final production transport security model. Loopback, `.local`, link-local, and unspecified relay hosts are not QR-ready remote routes. Carrier-grade NAT, private IPv4, and ULA IPv6 relay literals are accepted only when QR generation explicitly opts into `relay_scope=private_overlay`, meaning a user-controlled VPN, tunnel, or private overlay makes the address reachable from both paired devices.

## Local-First Threat Model

Assets to protect:

- Runtime host access.
- Local model prompts and responses.
- Runtime-host chat processing event logs, client-local UI cache, and runtime-owned user memory notes.
- Future compacted session summaries and embedding indexes.
- Future project files, project instructions, trusted-source settings, and project indexes.
- Future scheduled tasks, reminders, monitors, recurring automations, runtime-triggered jobs, client approvals, and audit logs.
- Trusted device identities.
- Future memory, files, image inputs, Python tool calls, MCP calls, and audit logs.

Primary threats:

- Any device on the same Wi-Fi attempts to control the runtime host.
- A malicious client sends protocol messages directly to the local transport.
- A paired client device is lost or should no longer be trusted.
- Runtime-host chat event logs, client-local UI cache, runtime-owned memory notes, compacted summaries, or embedding indexes leak from a device backup or filesystem.
- Project files or indexes are used as model/research context without project-scoped permission or trusted-source selection.
- A scheduled job runs later with broader file, network, tool, MCP, web search, or backend access than the user approved.
- Future tool execution gains file, terminal, network, or MCP access without explicit permission.
- Future image or file input flows bypass the runtime host and send user data directly to a serving backend.
- A future signaling/relay shortcut weakens the local-first guarantee by seeing prompts, responses, files, memory, model lists, or backend credentials.

v0.1 may use a small development transport while the product matures, but it must not normalize unauthenticated same-network runtime access, fixed IP/manual endpoint entry, or mDNS/local discovery as the product model.

## Trusted Devices

The target design is persistent device identity on both sides:

- The runtime host has a stable device id and keypair.
- The client device has a stable device id and keypair.
- The runtime host stores trusted client public keys.
- The client pins the trusted runtime identity.
- The runtime host exposes remove-trusted-device controls.

Pairing creates the persistent trust record used by later runtime sessions and by the connection manager. Removing a trusted device invalidates future authentication attempts from that client identity across local direct, remote P2P, and relay fallback paths.

The client identity must not silently rotate across app restarts. The client may persist its public device id and display name in the local preferences store, but private signing key material must remain in the platform key store. If the key store cannot load or create the signing key, the app should surface a device-identity failure instead of overwriting the previously persisted client id/name.

## Pairing Design

Target pairing flow:

1. User opens pairing on the runtime host.
2. The runtime host displays a QR code plus a one-time pairing code.
3. QR pairing data includes runtime device id, pairing nonce, service identity, runtime public key or certificate fingerprint, and a route token. For different-network product use, it also bootstraps private overlay/rendezvous/relay material. The current QR-provisioned relay path requires `relay_host`, `relay_port`, `relay_id`, `relay_secret`, `relay_expires_at`, and `relay_nonce`. A fixed host/port is not required for the product pairing payload and is only an optional development reachability hint.
4. The client submits pairing nonce, code, client device id, client device name, and client public key.
5. The runtime host stores the client public key only if the pairing window is active and user confirmation succeeds.
6. Future sessions use challenge-response authentication before runtime commands.

v0.1 persists the scanned trusted runtime record on the client only after the runtime accepts `pairing.request` and stores the client device as trusted. When the QR and accepted `pairing.result` include runtime public-key metadata, the client verifies that the accepted runtime key/fingerprint matches the scanned QR before storing trust. The client connects to the runtime host, not to Ollama or LM Studio directly.

QR trust values must fail closed before pairing state is persisted. The client rejects whitespace-mutated pairing nonces, runtime ids, runtime fingerprints, runtime public keys, route tokens, relay ids, relay nonces, and relay scopes rather than trimming them into a different trusted identity or route. Runtime display names are normalized separately for UI, and relay frame secrets are treated as opaque secret material.

The runtime also validates submitted client identity before writing a trusted-device record. `device_id` and `public_key` are treated as opaque canonical values, the public key must decode as a P-256 DER public key compatible with the later challenge-response verifier, and display names are normalized separately. Invalid client identity material returns `pairing_invalid_device_identity` and leaves the trusted-device store unchanged.

Pending QR routes are stored with a stricter boundary than trusted route metadata. When a QR contains relay route material but pairing is not accepted yet, the client may keep the non-secret route metadata in its local runtime UI store so the app can retry after process recreation. The raw pending `relay_secret` must not be written into that JSON store. It is saved through the Android relay secret store and the pending route keeps only a deterministic secret reference. If that reference cannot be resolved on load, the pending pairing route is discarded and the user must scan a fresh QR. When a pending pairing route is cleared or replaced, the old secret-store reference must be removed as well so abandoned QR relay credentials do not linger locally.

An active pairing session allows only a bounded number of invalid nonce/code submissions. After the limit is reached, the runtime host invalidates that pairing session and returns structured `pairing.result` rejection details while preserving the existing `accepted: false` response shape.

Implementation note: QR pairing and discovery can be simple in v0.1, but the docs must remain clear that the trusted-device gate is required before runtime commands execute.

Connectivity note: pairing is identity binding plus route bootstrap, not a promise that a scanned host/port will stay reachable. Product builds must keep pairing QR-only from the user's perspective while including enough private overlay material for different-network use: runtime identity, public key/fingerprint, route token, and rendezvous or relay allocation material. Raw local sockets, mDNS, or a remembered private IP cannot satisfy this requirement. The connection manager then resolves a route for that identity through local discovery/direct when available, remote P2P NAT traversal, or encrypted blind relay/TURN-style fallback.

NAT traversal note: the future remote path should use STUN-like address discovery and authenticated hole punching to attempt direct 1:1 connectivity. Any candidate exchange must be bound to paired device identities, short-lived rendezvous tokens, and replay protection before the encrypted AetherLink session is accepted. This is not implemented yet; current code only prepares route-candidate concepts around the paired identity.

Discovery note: Bonjour/local discovery candidates should carry minimal routing hints when possible. The preferred TXT hint is a pairing-derived `route_token`; stable device ids and public-key fingerprints are legacy/development fallback hints, not the production privacy target. The client must only auto-route a pinned trusted runtime identity to discovered LAN endpoints whose hints match the trusted runtime record. Endpoints without identity metadata, or with non-matching metadata, are local/dev/manual candidates only and must not be treated as automatically trusted.

Route-token lifecycle: production route tokens should be scoped to one trust relationship or pairing session, not to the whole runtime forever. Removing a trusted client should revoke that client's route token. Re-pairing should rotate the token. Local discovery should advertise only the minimum token needed for paired clients to recognize their runtime, and future remote rendezvous tokens should be short-lived values derived from paired-device secrets rather than stable public identifiers.

Privacy note: discovery identity hints are not an authorization layer and must stay minimal. They must not publish backend URLs, Ollama or LM Studio details, model inventory, provider health, prompts, responses, files, memory, or runtime command metadata. Pairing, pinned keys, challenge-response authentication, and encrypted transport remain mandatory before runtime commands execute.

Bitcoin-network analogy note: AetherLink should borrow only peer identity and discovery concepts. It is not a public open network; only QR-paired trusted devices may discover, authenticate, and communicate with the runtime.

DHT/bootstrap note: a future DHT-like or bootstrap-peer layer may be useful for finding a paired peer without a fixed IP, but it must publish only privacy-preserving rendezvous records. It must not expose stable runtime host directories, backend URLs, model inventory, prompts, files, memory, or any authority to mark a device as trusted.

Implementation status note: identity-only QR, local route-token matching, relay route preparation, macOS P2P QR generation, and the Android P2P rendezvous route-preparation/planning/restore contract are connection-manager increments. The P2P QR contract accepts only a separate `p2p_*` or compact `pc` / `prid` / `peb` / `px` / `pn` / `pv` field family for opaque record id, encrypted candidate material, expiration, anti-replay nonce, and protocol version 1 before pending storage, trusted-runtime storage, and prepared P2P route planning. Existing `rendezvous_*` fields remain relay aliases so P2P and relay route material do not blur. This does not yet signal candidates, perform STUN, hole punching, or real NAT traversal. A temporary outbound TCP development relay is implemented for different-Wi-Fi testing by `relay_id`; QR-provisioned relay routes require `relay_secret`, `relay_expires_at`, and `relay_nonce`, and the client plus runtime host encrypt relay frame bodies using AES-GCM before the relay sees them. The current relay-frame key derivation binds both `relay_secret` and `relay_nonce`, so replaying an old lease nonce or using a different nonce with the same secret fails to decrypt. The development relay allocation endpoint can require an allocation token, and allocation responses now return opaque relay ids instead of raw route tokens, but runtime commands still require pairing, pinned runtime identity, and challenge-response authentication. Actual private per-user overlay routing, DHT/bootstrap discovery, NAT traversal, production signaling, relay allocation, key rotation, replay-resistant session setup, and production end-to-end encryption are not complete. Local direct and the development relay remain diagnostics/development scaffolding, not the intended final same-network-IP design.

Development note: `AETHERLINK_DEV_PAIRING=1` is only for local automated smoke tests with RuntimeDevServer. It opens and prints a temporary pairing session for scripts, but runtime commands still require the normal pairing/trusted-device and challenge-response path. Do not enable this flag for production or normal trusted-device use.

## Session Authentication

After pairing, each runtime connection authenticates before model or command messages are accepted:

1. The client sends `hello` with its trusted device id.
2. The runtime host checks the trusted-device store and returns `auth.challenge` with a one-time nonce.
3. When the client has a pinned runtime public key from QR pairing, it verifies the runtime's challenge signature before sending a client signature.
4. The client signs the domain-separated message `AetherLink client auth response v1\n<device_id>\n<nonce>` with its paired private key and sends `auth.response`.
5. The runtime host verifies that exact message against the stored client public key. Raw nonce signatures are rejected to avoid cross-protocol signature reuse.
6. The runtime host allows runtime commands only after the connection is authenticated and the authenticated device id is still present in the trusted-device store.

Runtime commands include `runtime.health`, `models.list`, `models.pull`, `chat.send`, and `chat.cancel`. Requests sent before authentication fail with `authentication_required`; unknown or removed device ids fail with `pairing_required`; invalid client signatures fail with `authentication_failed`; invalid runtime proofs fail client-side with `runtime_authentication_failed`. Removing a trusted device must also revoke already-authenticated live sessions at the next command boundary: the runtime clears the cached auth session and returns `pairing_required` instead of letting stale connections continue.

The same authentication requirement applies on every transport. A relay or signaling server must not be trusted as an authenticator, must not terminate the end-to-end encrypted AetherLink session, and must not be able to forge either device identity.

## Runtime-Owned Local Storage

Runtime-owned chat processing logs, memory notes, trusted-device records, and fallback runtime identity files are sensitive local assets. The runtime stores these materials on the runtime host, not on a relay or model provider, and they must not be readable through group/world permissions. Current macOS chat history defaults to the SQLite/FTS runtime event store with legacy JSONL backfill; the SQLite database file is created or corrected to owner-only `0600`, its AetherLink support directory is created or corrected to `0700`, and legacy chat JSONL files use the same owner-only file policy during backfill-era coexistence. Current memory JSONL event logs are also created with owner-only `0600` permissions, their AetherLink support directory is created or corrected to `0700`, and each JSONL append reasserts file permissions so older broader-permission files are repaired lazily. The `trusted-devices.json` authorization store also creates or corrects its containing directory to `0700` and the trusted-device JSON file to `0600` before loading or after writing, without dropping valid trusted devices. The file-backed runtime identity fallback applies the same directory/file permission policy before loading or after writing, without rotating a valid existing identity key. The file-backed runtime identity fallback also signs nonce-bound auth challenges with the persisted public-key fingerprint, so fallback identity storage remains tied to the same challenge-response trust proof instead of becoming a fingerprint-only placeholder.

Runtime-owned chat history and memory are scoped to the authenticated trusted-device identity before they are listed, injected into `chat.send`, renamed, archived, restored, deleted, or title-generated. The client does not send an owner id in protocol payloads; the runtime derives `owner_device_id` from the authenticated connection and writes it to JSONL events. Legacy unscoped events remain readable only through unscoped/no-auth store calls and are intentionally not mixed into authenticated device views.

This is local filesystem hardening, not a replacement for future encrypted-at-rest storage, keychain-backed secrets, or user-controlled retention policy. Archived and deleted chat state remains runtime-owned and must not be used as memory, retrieval, research, or compaction input unless restored or explicitly selected by a future permissioned workflow.

## Remote Connectivity Security

See [connection-overlay.md](connection-overlay.md) for the phased connection-overlay design and the non-goals that keep remote discovery private, paired-device-only, and runtime-host-mediated.

Reliable different-network connectivity cannot be guaranteed with pure mDNS or local IP addressing. mDNS is local-link discovery, and private IPs usually do not route across NATs, mobile carriers, VPNs, or separate Wi-Fi networks.

Target security properties:

- The connection manager prefers local discovery and direct authenticated connections when both devices are reachable on the same network.
- Bonjour/local discovery records may advertise minimal runtime route hints for matching, preferably a pairing-derived `route_token`; the client only auto-routes to endpoints whose hints match the pinned trusted runtime identity.
- Metadata-less Bonjour/local endpoints are limited to local/dev/manual reachability candidates and are not trusted identity matches.
- Remote P2P NAT traversal uses paired identities, STUN-like address discovery, short-lived connection candidates, authenticated hole punching, and encrypted session establishment.
- Optional DHT/bootstrap-peer discovery exchanges only short-lived rendezvous records for paired identities and does not create public runtime access, accounts, backend routing, or model-logic hosting.
- Encrypted blind relay/TURN-style forwarding is a fallback for cases where direct P2P fails.
- Signaling and relay services see only connection metadata needed for reachability or opaque encrypted packets.
- End-to-end encryption is between the paired client device and runtime host, so relay infrastructure cannot read AI protocol payloads, model lists, prompts, responses, memory notes, files, or backend credentials.
- Fixed IP/manual host entry and mDNS/Bonjour local discovery are restricted to development, diagnostics, local fast paths, and emergency support flows, not normal onboarding.

Current implementation status: AetherLink has route-candidate plumbing for the target connection order, Android opaque P2P rendezvous QR/pending/trusted route planning, and a temporary outbound TCP development relay for different-Wi-Fi testing. Different-network production P2P, NAT traversal, decentralized/bootstrap signaling, encrypted blind relay fallback, and production end-to-end transport encryption remain future work.

Development preflight should fail closed for remote QR testing. `script/run_different_network_dev_runtime.sh --preflight-only` rejects accidental loopback, `.local`, unspecified, link-local, carrier-grade NAT, and private relay hosts unless an explicit private-overlay flag is used, and it checks the allocation API before RuntimeDevServer starts. When the relay requires an allocation token, preflight and RuntimeDevServer must send the same token with `--allocation-token` or `AETHERLINK_BOOTSTRAP_RELAY_ALLOCATION_TOKEN`. The app-side QR path blocks scope-less private IP relay literals and accepts them only when the QR marks `relay_scope=private_overlay`; the macOS GUI now requires an explicit private-overlay/VPN/tunnel opt-in before it emits that scope. This prevents a QR from looking remote-ready when the real blocker is the absence of reachable relay/bootstrap/overlay material.

Route-refresh handling must also fail closed. `route.refresh` responses may omit `relay_scope`, but any present value must match the protocol enum exactly: `remote`, `private_overlay`, or `usb_reverse`. The runtime must not emit unknown relay scopes, and the client must reject unknown or whitespace-mutated relay scopes before saving refreshed trusted route material. Relay fields and P2P fields are complete route-material families: partial, expired, or unsupported `p2p_rendezvous` records must be rejected before trusted storage just like malformed relay lease material. Authenticated relay refresh may reuse a stable relay id or frame secret, but it must advance the relay nonce and lease expiry before storage so an old relay lease cannot be replayed as a successful renewal.

Public access is forbidden for the same reason same-network unauthenticated access is forbidden: network reachability is not trust. A runtime host must never accept model, file, memory, tool, or backend commands just because a peer found it through local discovery, a bootstrap peer, a DHT-like record, a relay allocation, or a public address.

## Local Chat History, Memory, And Compaction

The runtime host stores chat processing events locally when it handles `chat.send`: request metadata, client-visible messages, streamed answer deltas, reasoning deltas, completion usage, cancellation, and errors. Inline attachment bytes are stripped before storage. Runtime-only system context is model-call input, not user-visible history; the capability guard and `Runtime user memory:` prompt context are filtered from stored and returned transcripts. The client may still keep a local UI cache for continuity, but user-managed memory notes are synchronized through the authenticated runtime host with `memory.list`, `memory.upsert`, and `memory.delete`. Current clients do not send memory notes as `chat.send` prompt context. Enabled memory notes are injected by the runtime from its own memory store before backend calls. Client-supplied cached memory context is compatibility input only; the runtime removes stale `Runtime user memory:` system messages and replaces them with its current enabled entries, or forwards no memory context if none are enabled. The client must not use memory features to call Ollama, LM Studio, web search, MCP, or tools directly.

Archive is not deletion. Archived chats remain retained, but they are excluded from memory, reflection, research, and compaction inputs unless the user explicitly restores them or selects them as sources. Deleted chats should be treated as removal requests, not hidden research material.

Runtime-host-side session storage, context-window compaction, embedding indexes, and deep-research-like research notebooks are sensitive data. A compacted summary, event log, or embedding index can still reveal private transcript content, so it must follow the same local-first storage, trusted-device, archive/delete, and future encryption rules as raw chat transcripts.

Embedding models must be selected separately from chat/text-generation models. Future retrieval, ranking, and knowledge indexing use the selected embedding model, and indexed sources must respect archive/delete state.

Short model inactivity and long memory inactivity are separate policies. The runtime may unload the active model after 10 or more minutes without chat activity. Longer inactivity criteria can later create compact memory summaries, but archived sessions stay excluded unless the user restores or selects them.

## Future Files, Images, And Python Tools

Future file inputs and image inputs must be mediated by the runtime host. The client can provide UI for choosing or approving inputs, but the client must not send those inputs directly to Ollama, LM Studio, future serving backends, or indexing services.

Future internal Python execution is a runtime-host tool for deterministic tasks such as calculations. The runtime host must own permissions, filesystem/network scope, audit logs, and result reporting. The client remains the approval and display surface.

## Future Project And Automation Security

Project/workspace features are permissioned runtime features, not v0.1 client-only state. Project-scoped chats, files, instructions, memories, indexes, model/backend preferences, trusted-source settings, and project-level search/research must be owned by the runtime-host boundary. Client devices can select sources, request searches, approve actions, and display status, but they must not call file indexers, research tools, Ollama, LM Studio, future serving backends, MCP, or web search directly.

Scheduled tasks, reminders, monitors, recurring automations, and runtime-triggered jobs are also permissioned runtime actions. They can run when the user is not actively watching the UI, so each job definition must store a narrow permission scope, require explicit approval for sensitive capabilities, and write audit records for creation, edits, approvals, execution, failures, cancellations, and permission changes.

Project files and scheduled jobs are sensitive by default. A scheduled job that reads project files, uses project indexes, calls a model backend, runs Python or terminal work, performs web search, or invokes MCP must pass through the same runtime-host-side permission broker as an interactive request. Client approval/status surfaces should be treated as controllers only; approval does not move execution to the client.

## Encryption Roadmap

v0.1 development transport:

- Local network socket with length-prefixed JSON.
- Clear runtime module boundary so transport can be replaced.
- No direct backend URL exposed to the client.
- Runtime commands rejected until the device is trusted and authenticated.

Hardening roadmap:

- TLS or Noise-style encrypted channel between the client device and runtime host.
- Runtime identity pinning on the client.
- Keychain-backed runtime public key and fingerprint confirmation during QR pairing.
- Client public-key challenge-response on the runtime host.
- Session keys derived after pairing.
- Protocol commands rejected until authenticated.
- Connection manager with local direct, remote P2P NAT traversal, and encrypted blind relay/TURN-style fallback.
- Optional BLE/QR/mDNS only for discovery, pairing, development reachability hints, or key exchange, not as the only product connectivity plan.

## Same-Network Unauthenticated Access Is Forbidden

Same Wi-Fi is not a trust boundary. A guest device, compromised laptop, or any local network process could otherwise send `chat.send`, list models, or later trigger tools.

Therefore:

- Runtime commands must require a trusted-device check and successful challenge-response authentication.
- Ollama remains bound to the runtime host adapter and is never exposed as the client API. The client must not call Ollama `/api/tags`, `/api/ps`, `/api/pull`, `/api/chat`, or LM Studio endpoints directly.
- Model installation is also a runtime command: the client may request `models.pull`, but only the authenticated runtime host may call Ollama `/api/pull`.
- Future file, image, Python, terminal, MCP, skills, and web search actions must pass through a runtime-host-side permission broker and audit log.
