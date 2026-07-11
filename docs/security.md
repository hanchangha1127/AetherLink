# AetherLink Security Model

## Development Relay Bounded Waiting And Authenticated Identity Fairness

Every unmatched room receives one monotonic deadline when its first peer enters the matcher. The default duration is `60` seconds, bounded to `1...3600` with no disable value, and the effective deadline is no later than the remaining allocation lease. Same-role replacement preserves the original room deadline, so repeated reconnects cannot extend the wait. Match, disconnect, generation invalidation, replacement cleanup, timeout, and close release matcher-owned waiting state before the accepted source connection permit; an active bridge cancels both waiting monitors and is not throttled.

After runtime or paired-client relay admission cryptographically verifies a key, the matcher applies a role-separated quota keyed by the verified allocation-binding fingerprint. The default is `4` unmatched waits per authenticated identity across source addresses, configurable in `1...65536` with no disable value. Runtime identity comes from the revalidated binding after runtime proof, and paired-client identity comes from the pinned binding after client proof. Bootstrap clients without paired-client proof and explicit legacy peers never create an identity bucket; they remain bounded by global/source descriptor controls and the waiting deadline. Identity admission cannot refund, enlarge, or replace the pre-auth source permit.

Stable reasons are `waiting_peer_timed_out` and `authenticated_identity_waiting_quota_reached`. Saturating metrics cover identity waiting requests, admissions, quota rejections, timeouts, current authenticated waiters, and current authenticated identities without source, fingerprint, role, relay ID, token, lease, or proof labels. Multiple valid identities remain a Sybil path and shared NAT/VPN collateral remains at the pre-auth boundary. This is process-local development fairness, not production identity service, per-user isolation, public-network capacity proof, production TLS/KEX/pair-epoch implementation, or physical Android proof; the phone is disconnected.

## Development Relay Source Peer Quotas

Every accepted development-relay socket now acquires both the existing global connection permit and a permit keyed by the canonical accepted IPv4/IPv6 source. The default source connection quota is `64`; the default unmatched waiting-peer quota is `32`. Waiting peers count against both limits, and active bridge sockets keep their source connection permits through close. Established encrypted frame forwarding is not throttled or evicted by this admission control.

The matcher owns waiting quota transitions under the same lock as room publication. Normal admission leaves one global and one per-source slot available before the first waiter, and every waiting insertion atomically requires `connections + waiting + 1 <= limit` in both scopes before consuming another normal-admission slot. A socket admitted from that reserve is counterpart-only: an immediate opposite-role match or authenticated same-source waiting replacement confirms it, while probe/allocation, cross-source replacement, and new waiting-room use close it. Reserve provenance is retained so a per-source reserve candidate can discharge only a waiter owned by that source; global-only reserve remains source-agnostic. Same-source replacement is net-zero, and cross-source replacement checks the new source before releasing the original waiter when it uses normal admission. Match, replacement, disconnect, generation invalidation, candidate rejection, and close release their exact counts. Configuration has no disable value and requires `2 * waiting <= connections` to preserve counterpart headroom.

Stable reasons are `global_connection_limit_reached`, `source_connection_quota_reached`, `source_waiting_peer_quota_reached`, and `counterpart_candidate_not_matched`. Saturating metrics report only aggregate admission, rejection, counterpart candidate, current connection/waiting, and source counts. Rejection logs contain only the reason and global reason count, never a source address, relay ID, route/allocation token, or proof field.

Shared NAT/VPN users necessarily share quotas. Defaults `64/32` are configurable development-relay fairness guardrails, not per-user isolation, production capacity/load/latency validation, IPv6-prefix aggregation, public-relay protection, live-network proof, or production TLS/KEX/pair-epoch implementation. The phone is disconnected, so this is not physical Android proof.

## Development Relay Source-Aware Allocation Controls

Allocation- and renewal-prefixed control attempts are admitted through separate token buckets keyed from the accepted socket address before full request parsing. IPv4-mapped IPv6 canonicalizes to IPv4, native IPv6 includes its scope ID, and unrecognized families share one conservative unknown-source bucket. Refill uses a monotonic clock. One shared overflow bucket plus periodic idle cleanup enforces the configured hard cap without capacity eviction resetting exhausted buckets or a full-map scan on every request.

The default development policy allows preflight at `120/minute` with burst `30` and new allocation plus paired claim/renew at `30/minute` with burst `10`, retaining at most `4096` buckets for `15 minutes` idle. Stable global counters cover request, rejection, overflow, idle eviction, and tracked-bucket state and remain source-free. Logs do not include source addresses, route tokens, allocation tokens, relay IDs, or proof material.

Only the exact cheap strict preflight envelope can select the more permissive preflight bucket. Duplicate markers, mutation-like fields, malformed envelopes, and all renewals consume mutation capacity. Configuration validation also requires both bursts to fully refill within idle retention, so deleting an idle bucket cannot restore tokens sooner than monotonic refill.

The limit intentionally runs before allocation-token and signature work so invalidly authorized requests cannot force that work without spending source capacity. This also means shared NAT/VPN users share one bucket and can affect one another; it is a conservative development-relay tradeoff, not identity-level fairness. Probes, peer admission, waiting rooms, active bridges, and encrypted forwarding remain outside these rate buckets, while the separate source peer quotas above govern accepted connection and unmatched waiting admission.

This rate-limit evidence is separate from the source peer quota evidence above. Neither slice is production capacity/load/latency validation, public-relay protection, live-network proof, or implementation of the selection-gated production TLS/KEX/pair-epoch design. The phone is disconnected, so it is not physical Android proof.

## Development Relay Abuse-Control Foundation

The development relay now bounds every accepted socket with a lifetime permit that remains owned while the socket is parsing control records, waiting for its counterpart, or participating in an active bridge. Disconnected waiting peers are removed and release capacity. Every control record has one absolute monotonic read deadline and the existing 4096-byte framing limit; encrypted frame forwarding remains independent of that deadline.

Unauthenticated route-state probe is loopback-only by default. An exposed strict relay closes probe requests without reporting whether a route exists or a runtime waits, unless an operator explicitly selects `legacy-unauthenticated` for temporary physical diagnostics. Android treats a closed probe as unsupported and proceeds to the authenticated relay registration path; it does not treat that closure as route proof. Exposed unallocated legacy relay mode fails closed even when a bearer token exists.

This foundation is complemented by the bounded waiting, authenticated identity, source rate, and source peer quota controls above. It is not production TLS/KEX or public-relay abuse protection. The Android phone is disconnected, so it also provides no physical Android proof.

## Production Relay Security Design Review

The current implementation remains a development relay foundation. The reviewed [production relay security hardening portfolio](security-hardening/production-relay-v1/hardening.md) recommends two next controls, but neither is implemented yet: TLS 1.3 allocation with delegated service-signed lease capabilities, and a monotonic pair-epoch recovery state machine with deny-only emergency revocation and fresh-QR replacement.

Production endpoint key exchange must be peer-verifiable. Both endpoints must directly verify a canonical identity transcript containing both long-term identities, both ephemeral shares, both session nonces, pair epoch, lease generation, and the signed lease digest before installing traffic keys. Relay registration proofs remain defense in depth; the relay is not the trust terminator. Recovery mutations must be idempotent, close active and waiting rooms when revoked, and expose a read-only signed status operation that reconciles a committed transition when the final response is lost.

Implementation is selection-gated. The portfolio compares a private-overlay baseline, the recommended TLS/signed-lease design, and a split authority/relay design; it separately compares short leases, the recommended pair-epoch state machine, and deferred threshold recovery. The physical Android phone is disconnected, so this review contributes no physical, optical QR, public-network, or production-deployment proof.

The project is local-first: no cloud AI backend and no account-server requirement for model access. The runtime host owns execution and backend access. The client device is a controller/client. That split is the main security boundary. The current v0.1 implementation has desktop-runtime and mobile-client targets.

AetherLink may later use distributed rendezvous/bootstrap/DHT-style discovery, signaling, or an encrypted blind relay/TURN-style component for connectivity when paired devices are on different networks. That component is connection infrastructure only: it must not run models, proxy backend APIs in plaintext, inspect AI protocol payloads, store prompts/responses, see model lists, files, memory, or backend credentials, or become a cloud AI backend, account backend, or model-logic backend.

Current code status: remote P2P NAT traversal, decentralized/distributed rendezvous, production allocation identity/authorization, and production end-to-end transport deployment are not complete yet. Existing endpoint hints, Bonjour/mDNS records, USB reverse paths, localhost/dev-server flows, Android opaque `p2p_rendezvous` route persistence/planning/diagnostic refresh validation, and the outbound TCP development relay are development scaffolding behind the trusted-device boundary. QR-provisioned relay routes require pairwise route material including `relay_secret`, `relay_expires_at`, and `relay_nonce`; `relay_secret` plus `relay_nonce` derive the AES-GCM relay-frame key so AetherLink frame bodies are encrypted before relay forwarding and stale or mismatched QR route material can be rejected. Android P2P rendezvous records are stored only as complete opaque, expiring route material bound to the pinned runtime identity, whether they arrive through QR or explicitly enabled authenticated `route.refresh`; they are not trust authority, candidate exchange, decrypted payloads, STUN, hole punching, or a real P2P connector. Android product defaults do not advertise or automatically send authenticated `route.refresh`, so normal route repair stays latest-QR scan first. The development relay requires allocation by default, accepts only canonical `crypto=2` allocation, rejects unknown or expired relay ids, and can require an allocation token before it issues secret-free lease metadata. The runtime host generates or reuses the 32-byte traffic secret locally and delivers it only as endpoint route material; the allocation request, response, ticket store, and relay log do not contain it. The allocation token is only allocation gating and not device trust. For a stable relay id, non-advancing renewal attempts for the same relay id are ignored unless the lease expiry advances and the relay nonce changes; persisted allocation-store loading also skips malformed ticket entries and deduplicates duplicate relay ids with the same rule. Durable allocation registry operations and relay lifetime ownership now use separate byte ranges of one stable inode-bound transaction marker, so two cooperating local processes cannot split store, matcher, or active-room ownership. The macOS runtime host applies the same advancing lease rule before replacing saved same-relay bootstrap lease material that can feed QR generation or diagnostic route refresh. That is only a foundation slice, not the final production transport security model. Loopback, `.local`, link-local, and unspecified relay hosts are not QR-ready remote routes. Carrier-grade NAT, private IPv4, and ULA IPv6 relay literals are accepted only when QR generation explicitly opts into `relay_scope=private_overlay`, meaning a user-controlled VPN, tunnel, or private overlay makes the address reachable from both paired devices.

The current schema-v4 allocation registry supersedes the earlier lease-only, schema-v2 runtime-only, and schema-v3 global paired-room behavior: it stores authorization mode, pinned client ownership, ticket generation, and consumed-bootstrap tombstones; pair claim/renew uses generation compare-and-swap and fails closed on downgrade, key substitution, reuse, corrupt, duplicate, or unknown-version stores.

Strict allocated relay crypto v2 adds PSK-mixed ephemeral P-256 ECDH, fresh ordered client/runtime session nonces and public keys, canonical transcript confirmation, and paired-identity transport binding. Directional traffic secrets derive AES-GCM keys in 65,536-frame epochs; ordered replay, reordering, frame authentication failure, and counter exhaustion fail closed. If ephemeral private keys are not retained, later compromise of only the QR relay secret does not recover recorded session traffic. Endpoint-owned allocation v2 also prevents the default allocation-required relay from learning that PSK through allocation. The initial bootstrap caller is still runtime-only; only the first post-pairing claim and later renewals are co-authorized. This does not protect a leaked QR secret, provide post-compromise security or a complete unordered replay window, or turn the development relay into production end-to-end transport.

## Relay Allocation Cross-Process Ownership No-Device Gate

- One stable mode-`0600` marker contains fixed-format `U`/`A`/`E` state and a 64-character lowercase hexadecimal coordination token that is also stored in schema v4. POSIX `F_SETLK` byte range 0 serializes reload, binding/generation compare-and-swap, and persistence; byte range 1 is the relay lifetime owner lock.
- The process lock pool keys by marker inode, reuses its pooled descriptor, and retains only duplicates that cannot safely be closed because closing any descriptor for an `F_SETLK` file can release that process's locks. Blocking acquisition has a five-second monotonic deadline. Stale process snapshots therefore cannot erase unrelated allocations or wait forever for a cooperating owner.
- Pair claim updates remain indivisible: the bootstrap removal, deterministic pair binding, and consumed-bootstrap tombstone are encoded and atomically renamed together. Competing stale claims produce one winner and one conflict, and a stale create cannot restore a consumed bootstrap ID.
- Descriptor-relative `openat`, `fstatat`, `renameat`, and `unlinkat` operations use `O_NOFOLLOW` and require current-user-owned regular files with `nlink == 1` under a parent that is not group- or world-writable. File `fsync`, atomic rename, and directory `fsync` reconcile persistence.
- Missing established stores, dangling symlinks, hard links, case/path aliases, marker replacement, and coordination-token mismatch fail closed. A valid unversioned `rt1` store is recognized but all leases are revoked into an empty token-bound schema-v4 store because legacy identity cannot be migrated.
- Interrupted first initialization recovers only a token-matched schema-v4 store beside a `U` marker. A second process fails before independent matcher state, a concurrent same-instance `run()` cannot release the live owner, and bind failure releases byte range 1. Simultaneous first startup converges to one owner, and kernel release on exit permits a successor.
- Final evidence is 64 allocation tests, 21 socket tests, 100 related relay tests, 797 full Swift tests, a TCP-verified actual-process smoke, and the passing aggregate artifact `build/qa/check-no-device-quality-relay-cross-process-ownership-20260710.log` with 41 authenticated relay connections and 688 encrypted frame bodies. This is cooperative single-host advisory locking. It does not provide distributed consensus or protection against a privileged process that ignores the lock protocol. Allocation TLS/server authentication, service-signed responses, immediate revocation, P2P/NAT traversal, and physical Android proof remain unfinished. The phone is disconnected.

## Pair-Scoped Relay Room Isolation No-Device Gate

- `runtime-client-p256-v2` binds current and next relay IDs, both identities, both lease states, generation, challenge, and live transport binding. A claim must rotate to the deterministic pair-derived ID.
- Schema v4 commits the pair allocation and consumed-bootstrap tombstone together. Wrong key, replay, stale generation, bootstrap reuse, legacy mutation, duplicate ID, corrupt persistence, and unknown fields fail closed.
- `paired-client-p256-v1` proves the persistent Android client key before matcher admission. Invalid, missing, replayed, mutated, expired, or downgraded proofs cannot replace a verified waiting runtime.
- Active matcher rooms reject second runtime/client pairs until bridge release. Two different pair IDs can bridge concurrently, and loopback socket evidence verifies frames do not cross rooms.
- macOS keeps pair routes and relay clients per client fingerprint; secrets remain in the secret store. Removing a trusted device stops and removes that pair transport locally. Relay-side allocation invalidation is still lease-based and is not yet a signed revocation transaction.
- Android checks the deterministic pair ID before co-signing, stores the rotated ID/generation, and requires pre-ready admission on reconnect.
- This remains development security. Allocation TLS/server authentication, service-signed final responses, production abuse controls, P2P/NAT traversal, and physical different-network proof are unfinished.
- No physical Android, optical QR, or real different-network evidence was produced.

### Historical Runtime-Key Allocation Foundation

- Before paired claim/renew, a successful `rt2` allocation ID is key-bound to the verified runtime-key fingerprint.
- Allocation ticket schema v2 stores the runtime-key fingerprint and a generation, and persistence failure rejects allocation rather than returning unpersisted route material. Schema v4 preserves those invariants and migrates schema-v3 paired records into pair-scoped rooms.

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
4. The client submits pairing nonce, code, client identity, proof scheme, and a P-256 signature that binds both identities, the request id, and the active transport binding.
5. The runtime host verifies client-key possession, reserves the pairing request, signs the accepted result with its QR-pinned runtime key, and stores the client public key only after signing can succeed.
6. Future sessions use challenge-response authentication before runtime commands.

v0.1 persists the scanned trusted runtime record on the client only after the accepted `pairing.result` signature matches the pending request digest, QR-pinned runtime key/fingerprint, trusted client id, and current transport binding. The runtime verifies the client proof before trusted-device persistence and releases its pairing reservation if result signing or storage fails. The client connects to the runtime host, not to Ollama or LM Studio directly.

QR trust values must fail closed before pairing state is persisted. The client rejects whitespace-mutated pairing nonces, runtime ids, runtime fingerprints, runtime public keys, route tokens, relay ids, relay nonces, and relay scopes rather than trimming them into a different trusted identity or route. Runtime display names are normalized separately for UI, and relay frame secrets are treated as opaque secret material.

The runtime also validates submitted client identity before writing a trusted-device record. `device_id` and `public_key` are treated as opaque canonical values, the public key must decode as a P-256 DER public key compatible with the later challenge-response verifier, and display names are normalized separately. Invalid client identity material returns `pairing_invalid_device_identity` and leaves the trusted-device store unchanged.

Pending QR routes are stored with a stricter boundary than trusted route metadata. When a QR contains relay route material but pairing is not accepted yet, the client may keep the non-secret route metadata in its local runtime UI store so the app can retry after process recreation. The raw pending `relay_secret` must not be written into that JSON store. It is saved through the Android relay secret store and the pending route keeps only a deterministic secret reference. If that reference cannot be resolved on load, the pending pairing route is discarded and the user must scan a fresh QR. When a pending pairing route is cleared or replaced, the old secret-store reference must be removed as well so abandoned QR relay credentials do not linger locally.

An active pairing session allows only a bounded number of invalid nonce/code or identity-proof submissions. After the limit is reached, the runtime host invalidates that pairing session and returns structured `pairing.result` rejection details while preserving the existing `accepted: false` response shape. Rejected results do not create trust; Android keeps pending route recovery state when displaying an unsigned rejection.

## Initial Pairing Mutual Proof

- The Android device key signs a domain-separated, length-framed transcript containing protocol/scheme, request id, QR nonce/code, runtime id/key/fingerprint, client id/name/key/fingerprint, and the exact transport binding or `none`.
- The runtime verifies canonical P-256 DER keys, SHA-256 fingerprints, canonical DER signatures, scheme/version, and transport binding before reserving the pairing session.
- The runtime identity signs an accepted result containing the original request digest, runtime identity, trusted client id, generated message, and the same transport binding before either side treats pairing as complete.
- Android compares the result to the outstanding request and QR-pinned runtime key, verifies the runtime signature, and rechecks the live transport binding immediately before trusted-runtime persistence.
- Fixed Kotlin/Swift digest vectors, wrong-key, mutation, replay/request-id, downgrade, noncanonical Base64/DER, signer-failure reservation recovery, real relay TCP, and authenticated RuntimeDevServer smoke cover the no-device boundary.
- This is initial trust binding, not paired-device relay allocation authorization, post-compromise recovery, credential revocation propagation, production P2P traversal, or physical optical QR proof.

Implementation note: QR pairing and discovery can be simple in v0.1, but the docs must remain clear that the trusted-device gate is required before runtime commands execute.

Connectivity note: pairing is identity binding plus route bootstrap, not a promise that a scanned host/port will stay reachable. Product builds must keep pairing QR-only from the user's perspective while including enough private overlay material for different-network use: runtime identity, public key/fingerprint, route token, and rendezvous or relay allocation material. Raw local sockets, mDNS, or a remembered private IP cannot satisfy this requirement. The connection manager then resolves a route for that identity through local discovery/direct when available, remote P2P NAT traversal, or encrypted blind relay/TURN-style fallback.

NAT traversal note: the future remote path should use STUN-like address discovery and authenticated hole punching to attempt direct 1:1 connectivity. Any candidate exchange must be bound to paired device identities, short-lived rendezvous tokens, and replay protection before the encrypted AetherLink session is accepted. This is not implemented yet; current code only prepares route-candidate concepts around the paired identity.

Discovery note: Bonjour/local discovery candidates should carry minimal routing hints when possible. The preferred TXT hint is a pairing-derived `route_token`; stable device ids and public-key fingerprints are legacy/development fallback hints, not the production privacy target. Current macOS Bonjour TXT advertisement follows that boundary by publishing only the pairing-derived `route_token` identity hint and omitting stable runtime `device_id` and `fingerprint` values from local discovery TXT records. Whitespace-mutated `route_token` values are omitted instead of trimmed into discovery identity hints. Android Bonjour TXT receive canonicality mirrors that boundary by dropping discovered peers with whitespace-mutated, oversized, malformed UTF-8, or forbidden identity TXT material before trusted discovery matching can fall back to legacy metadata. The client must only auto-route a pinned trusted runtime identity to discovered LAN endpoints whose hints match the trusted runtime record. Endpoints without identity metadata, or with non-matching metadata, are local/dev/manual candidates only and must not be treated as automatically trusted.

Route-token lifecycle: production route tokens should be scoped to one trust relationship or pairing session, not to the whole runtime forever. Removing a trusted client should revoke that client's route token. Re-pairing should rotate the token. Local discovery should advertise only the minimum token needed for paired clients to recognize their runtime, and future remote rendezvous tokens should be short-lived values derived from paired-device secrets rather than stable public identifiers.

Privacy note: discovery identity hints are not an authorization layer and must stay minimal. They must not publish backend URLs, Ollama or LM Studio details, model inventory, provider health, prompts, responses, files, memory, or runtime command metadata. Pairing, pinned keys, challenge-response authentication, and encrypted transport remain mandatory before runtime commands execute.

Bitcoin-network analogy note: AetherLink should borrow only peer identity and discovery concepts. It is not a public open network; only QR-paired trusted devices may discover, authenticate, and communicate with the runtime.

DHT/bootstrap note: a future DHT-like or bootstrap-peer layer may be useful for finding a paired peer without a fixed IP, but it must publish only privacy-preserving rendezvous records. It must not expose stable runtime host directories, backend URLs, model inventory, prompts, files, memory, or any authority to mark a device as trusted.

Implementation status note: identity-only QR, local route-token matching, relay route preparation, macOS P2P QR generation, and the Android P2P rendezvous route-preparation/planning/restore contract are connection-manager increments. The P2P QR contract keeps opaque candidate records separate from relay aliases, but does not yet signal candidates, perform STUN, hole punching, or real NAT traversal. The temporary outbound TCP development relay uses strict crypto v2 for allocated routes: each endpoint contributes a fresh session nonce and ephemeral P-256 key, derives ECDH session material mixed with the QR relay secret, confirms the canonical transcript, and encrypts directional frames with epoch-derived AES-GCM keys. Legacy unallocated/plaintext diagnostics retain the old 3-token handshake and plain registered/ready lines. The allocation-required development endpoint can require a token, accepts only secret-free `crypto=2` bootstrap allocation, and supports paired P-256 claim/renew for one pinned client/runtime key pair. The runtime host owns and stores the bootstrap traffic secret, while runtime commands continue to require pairing, pinned runtime identity, and challenge-response authentication. Actual private per-user overlay routing, DHT/bootstrap discovery, NAT traversal, production signaling/service authentication, global room and multi-client isolation, immediate revocation, post-compromise recovery, and production end-to-end deployment are not complete.

Strict relay paired-identity transport binding note: Android and macOS bind crypto version, relay id, route nonce, ordered session nonces, and ordered ephemeral public keys into a canonical SHA-256 transcript. PSK-mixed ephemeral P-256 ECDH derives role-separated confirmation and traffic secrets; the confirmed binding is then included in v2 runtime-challenge and client-response signatures so authentication cannot be spliced onto another strict relay connection or downgraded to unbound v1. Local direct and legacy plaintext diagnostics remain on v1 because they have no confirmed transport binding. This provides forward secrecy against later compromise of only the relay secret when ephemeral private keys were not retained, and endpoint-owned allocation keeps that secret out of the default relay service. Paired allocation claim/renew now binds that exact authenticated transport to one pinned client/runtime key pair, but it does not cover a leaked endpoint/QR secret, post-compromise security, an unordered replay window, production allocation-service authentication/isolation, or complete production end-to-end deployment.

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

Current implementation status: AetherLink has route-candidate plumbing for the target connection order, Android opaque P2P rendezvous QR/pending/trusted route planning, and a temporary outbound TCP development relay for different-Wi-Fi testing. Strict allocated relay crypto v2 uses ephemeral P-256 ECDH mixed with the QR relay secret, mutual transcript confirmation, paired-identity transport binding, directional traffic secrets, and 65,536-frame epochs. Secret-free allocation v2 leaves the traffic secret at the endpoints while the relay handles only lease metadata; schema-v3 paired claim/renew adds runtime/client P-256 authorization and generation continuity for one pinned pair. Local direct and legacy relay diagnostics remain unchanged. Different-network production P2P, NAT traversal, decentralized/bootstrap signaling, allocation-service TLS/server authentication, global isolation, immediate revocation, post-compromise recovery, and production end-to-end deployment remain future work.

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

- Promote the strict relay v2 and paired claim/renew foundation through a reviewed production key-exchange and allocation design; preserve endpoint-owned traffic secrets while adding service authentication, global room/multi-client isolation, rotation, immediate revocation, and recovery.
- Define recovery, post-compromise security, traffic-secret replacement, and replay policy beyond ordered per-connection counters and derived 65,536-frame epochs.
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
