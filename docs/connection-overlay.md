# AetherLink Connection Overlay

This document makes the remote 1:1 connection model concrete without defining an implementation plan for the current codebase. It is a product and architecture boundary for future transport work.

AetherLink should feel less like "enter the computer's IP address" and more like a private peer network: a paired client asks for its paired runtime host by identity, and the connection layer finds the best route. The useful analogy to Bitcoin-style peer networks is decentralized or distributed rendezvous and peer discovery, not public access. AetherLink is still private, paired-device-only, and runtime-host-mediated.

Current implementation status: the local companion runtime server exists, and supported development routes include local direct routes plus a small outbound TCP relay. Local routes cover same-network/local discovery, USB or emulator forwarding, and explicit local diagnostic endpoints. The relay lets a paired runtime host and client join the same private `relay_id` room through outbound TCP when they are not on the same Wi-Fi. When QR pairing provides `relay_secret`, the peers encrypt AetherLink frame bodies before relay forwarding. QR pairing and trusted-device state still gate runtime commands on every route. Production per-user encrypted overlay, rendezvous, relay/TURN allocation, P2P NAT traversal, replay-resistant session setup, and production end-to-end transport encryption remain roadmap/foundation work.

QR-only pairing is the product requirement from the user's perspective. The user scans a QR to pair, refresh, or repair connectivity and never enters a host, port, Ollama URL, LM Studio URL, or backend URL in the client app. QR-only does not mean raw local sockets can cross unrelated networks. A production QR must bootstrap a private per-user encrypted overlay: paired identity, route tokens, rendezvous material, and relay/P2P allocation material sufficient for the connection layer to create a route automatically. If the QR is identity-only, it can establish trust and resolve local routes later, but it cannot by itself cross unrelated networks.

Non-negotiable boundaries:

- The Android/iOS client is a controller.
- The macOS/Windows/DGX OS-class runtime host mediates all model access.
- The client never calls Ollama, LM Studio, or future serving backend URLs directly.
- Discovery, rendezvous, bootstrap, relay, and TURN-style infrastructure must never become a cloud AI backend.
- Only QR-paired trusted devices may authenticate and exchange AetherLink protocol traffic.
- Network reachability is not trust; pairing, pinned identities, challenge-response authentication, and encrypted sessions are still required.

## Target Shape

```text
Client device
  Paired client identity
  Pinned runtime identity
  Route resolver
        |
        | choose best route for the paired runtime identity
        v
Connection overlay
  1. Local direct path
  2. Privacy-preserving rendezvous/bootstrap/DHT assist
  3. Remote NAT traversal path
  4. Blind encrypted relay fallback
        |
        | end-to-end encrypted AetherLink session
        v
Runtime host
  Paired runtime identity
  Trusted client store
  Protocol router
  Ollama/LM Studio/local backend adapters
```

The overlay resolves a route to one specific trusted runtime identity. It does not expose a searchable public directory of runtimes, a list of model hosts, an account namespace, or an API endpoint registry. The normal product target is the paired runtime identity, not a fixed IP address, mDNS host, or remembered host string.

## Phase 0: Paired Identity

Pairing is the root of trust and the input to every route decision.

The runtime host owns:

- A persistent runtime device id.
- A persistent runtime public/private keypair stored in the platform keychain when available.
- A trusted-client store containing paired client public keys, labels, revocation state, and route-token material.

The client device owns:

- A persistent client device id.
- A persistent client public/private keypair stored in platform-secure storage when available.
- A pinned trusted-runtime record containing runtime id, runtime public key or certificate fingerprint, display label, and route-token material.

QR pairing should be identity-first and route-explicit:

- Required: runtime identity, runtime public key or certificate fingerprint, pairing nonce/code material, service/protocol version, and a pairing-derived route token or token seed.
- Optional local development hints: host/port for local direct testing.
- Remote-route QR material: `relay_host`/`relay_port`/`relay_id` plus optional `relay_secret` for the current relay path, and future P2P rendezvous candidates/tokens for direct NAT traversal.
- Not allowed: Ollama URL, LM Studio URL, model list, provider health, prompt data, file paths, memory data, account identifiers, or public directory registration data.

After pairing, each session still authenticates:

1. Client connects over any candidate route.
2. Runtime checks whether the client device id is trusted.
3. Runtime returns a nonce.
4. Client signs the nonce.
5. Runtime verifies the signature before accepting runtime commands.
6. The encrypted session binds both paired identities and the selected route.

Removing a trusted device revokes future authentication on every path: local direct, P2P, rendezvous-assisted, and relay fallback.

## Phase 1: Local Direct Path

The local direct path is the fast path when both devices are reachable on the same network, USB reverse path, hotspot, emulator bridge, or manually selected diagnostic endpoint. It remains a development/local route rather than the intended product architecture.

Allowed local-direct inputs:

- Bonjour/mDNS discovery records.
- USB reverse or emulator loopback forwarding.
- A QR-provided development host/port hint.
- A last-known endpoint hint stored with the trusted runtime.
- A manual diagnostic endpoint hidden away from normal onboarding.

Local direct route candidates must be treated as reachability hints, not durable product identity. The route resolver should prefer current discovery results for the pinned runtime identity over stale last-known endpoints.

Local direct is a fast path inside the overlay, not the product foundation. A raw local socket, a remembered private IP, or mDNS alone cannot satisfy QR-only different-network connectivity. Production routing must be bootstrapped by QR and then resolved through the private encrypted overlay/rendezvous/relay layer when local reachability is absent.

Current development behavior: when a trusted runtime has a prepared relay route from QR pairing, the client tries prepared remote routes first: future P2P before the current relay, then fresh same-network discovery, then explicit local diagnostics. Automatic reconnect does not promote a previously saved private IP address as the product route. This prevents an old private IP or same-network fast path from masking the different-network relay route. If the relay is unavailable, local discovery, USB/emulator forwarding, and other diagnostics still remain available without treating the stale IP as trusted reachability.

Bonjour/mDNS records may carry minimal route hints:

- Preferred: pairing-derived `route_token`.
- Legacy/development fallback: runtime device id or public-key fingerprint.
- Forbidden: backend URLs, model names, provider status, prompts, files, memory, runtime commands, or user account data.

The client may automatically try a discovered endpoint only when its route hints match the pinned trusted runtime record. Metadata-less endpoints can remain useful for local development and manual diagnostics, but they are not automatic trusted-runtime matches.

## Phase 2: QR-Only Remote Route

Different-network connectivity requires more than mDNS, private IP addresses, or an identity-only QR. The target user experience is QR-only: the runtime generates a remote-route QR, the client scans it, and the connection layer automatically tries P2P NAT traversal before falling back to a blind encrypted relay.

Target behavior:

1. The runtime creates a QR that contains paired identity material plus remote-route material.
2. The client scans the QR and stores the remote route with the pinned runtime identity.
3. The client and runtime each derive or request short-lived rendezvous material for their paired relationship.
4. Each side gathers network candidates through STUN-like address discovery.
5. Candidate exchange happens through a privacy-preserving rendezvous/bootstrap path.
6. The peers attempt authenticated hole punching.
7. If direct P2P fails, both sides connect outbound to a blind relay/TURN-style path keyed by paired-route material.
8. The first viable path upgrades into an end-to-end encrypted AetherLink session bound to the paired identities.
9. Runtime commands remain blocked until session authentication succeeds.

Security requirements:

- Candidate exchange uses short-lived tokens derived from the paired relationship, not stable public device ids.
- Replay protection prevents old candidates or old rendezvous records from opening a new session.
- Hole punching is not authorization. It only creates reachability.
- The encrypted AetherLink session is authenticated by the paired client and runtime keys.
- Failure to create a P2P path falls through to relay fallback rather than weakening authentication.

Implementation boundary:

- This is not implemented in v0.1.
- Current route-candidate plumbing may model future P2P candidates, but it must not claim real NAT traversal until STUN-like discovery, candidate exchange, authenticated hole punching, replay protection, and encrypted session binding exist.

## Phase 2a: Development Relay

The current code includes a temporary outbound TCP relay for different-Wi-Fi development testing. It is not the production encrypted relay design.

Behavior:

1. A relay process listens on a public or otherwise mutually reachable host.
2. The runtime host connects outbound and registers `AETHERLINK_RELAY runtime <relay_id>`.
3. The client connects outbound and registers `AETHERLINK_RELAY client <relay_id>`.
4. The relay matches one runtime and one client with the same `relay_id`, sends `AETHERLINK_RELAY ready`, then pipes bytes in both directions.
5. If QR pairing supplied `relay_secret`, the client encrypts client-to-runtime frame bodies with direction `CLNT`, the runtime encrypts runtime-to-client frame bodies with direction `RUNT`, and the relay forwards only ciphertext frame bodies.
6. The existing length-prefixed AetherLink JSON frame stream runs through that pipe.

Current app wiring:

- The macOS app Status screen has a Remote Relay panel for a relay host and port that both devices can reach.
- Saving the relay route generates a frame secret when one is not provided and restarts the outbound runtime relay client if the runtime is already active.
- The macOS app now reports live relay state: connecting, waiting for the client device to join the same relay id, connected, reconnecting, failed, or stopped.
- New QR pairing payloads include `relay_host`, `relay_port`, `relay_id`, and `relay_secret` after the relay route is configured.
- The development runtime helper also generates a relay frame secret when `AETHERLINK_RELAY_HOST` is set without `AETHERLINK_RELAY_SECRET`.
- When a development relay is configured, development pairing QR payloads no longer default to `127.0.0.1`; a direct host is included only when `AETHERLINK_DEV_PAIRING_HOST` is explicitly set.
- Existing client pairings do not receive relay metadata retroactively. A client that already trusts the same pinned runtime identity can scan a fresh relay QR to refresh only the route metadata; if runtime trust was removed, pair again.

Boundaries:

- The relay does not call Ollama, LM Studio, or any model backend.
- The relay does not authenticate devices; pairing and runtime challenge-response still happen between client and runtime.
- Relay frame encryption is a development foundation slice. Production still needs short-lived allocations, key rotation, replay protection, and a session key exchange bound to paired device identities.
- The relay is a development bridge, not a cloud AI backend.
- Until production end-to-end encryption is added, do not treat this relay as safe for sensitive prompts, files, memory, or private model output on an untrusted public host.

## Phase 3: Rendezvous, Bootstrap, And DHT Option

AetherLink can use a Bitcoin-network-like feel for finding peers without one fixed server address, but the privacy model is different. Bitcoin-style public propagation is not acceptable for AetherLink runtime access.

Acceptable roles for bootstrap or DHT-like infrastructure:

- Help a paired client and runtime find short-lived rendezvous records.
- Help locate candidate exchange points when neither side has a stable public address.
- Provide multiple bootstrap entry points so discovery does not depend on one hardcoded host.
- Carry only opaque, expiring records that are useful to an already-paired device.

Unacceptable roles:

- Public runtime directory.
- Account server.
- Trust authority.
- Backend URL registry.
- Model host registry.
- Prompt, response, file, memory, or model metadata store.
- Plaintext proxy for AetherLink protocol messages.

Privacy-preserving record shape should be closer to:

```text
rendezvous_key = H(pairwise_secret, time_window, purpose)
record = encrypted_or_opaque({
  candidate_exchange_hint,
  expiration,
  anti_replay_nonce,
  protocol_version
})
```

The exact cryptographic construction is future work, but the design intent is clear: unpaired observers should not learn stable runtime identity, client identity, backend details, model inventory, or usable connection information.

The DHT/bootstrap option should remain optional. AetherLink can start with simpler rendezvous servers and later distribute bootstrap across more peers, as long as privacy and trust boundaries stay unchanged.

## Phase 4: Blind Encrypted Relay Fallback

Some networks will block direct P2P. The fallback is a blind encrypted relay or TURN-style path.

Relay responsibilities:

- Allocate a temporary relay path.
- Forward opaque encrypted packets between the paired client and runtime.
- Enforce basic abuse controls, quotas, and expiration.
- Avoid storing payloads beyond transient forwarding buffers.

Relay non-responsibilities:

- Run models.
- Terminate the AetherLink encrypted session.
- Authenticate devices as trusted.
- See prompts, responses, model lists, files, memory, backend credentials, or runtime command payloads.
- Provide Ollama, LM Studio, or OpenAI-compatible API access.

Relay selection happens after local direct and remote P2P candidates fail. Relay use should be visible in diagnostics because it affects latency and availability, but it must not change the user-facing trust model.

## Route Resolution Order

The route resolver should operate on a paired runtime identity, not on a remembered host string.

Product candidate order:

1. QR-bootstrapped private overlay state for the paired runtime identity.
2. Current local discovery candidate with matching route token or trusted identity hint, when available.
3. Remote P2P NAT traversal candidate prepared through privacy-preserving rendezvous/bootstrap/DHT assist.
4. Encrypted relay/TURN fallback candidate.

v0.1 compatibility candidates:

- USB forwarding, emulator forwarding, hotspot lab routes, QR-provided `host`/`port` hints, the temporary development relay, or last-known endpoint hints may be attempted for development, diagnostics, or local lab use.
- These hints must not outrank the paired identity as the product target and must not become normal onboarding.
- A stale fixed endpoint should never be treated as proof that the runtime identity is trusted or reachable.

Every successful route must still establish an authenticated encrypted session before runtime commands can execute.

## Route Record Contract

Route records are the connection-layer objects that make "find my paired runtime" possible without turning host/port into the product identity.

Normal product target:

```json
{
  "target": "paired_runtime_identity",
  "runtime_device_id": "runtime-1",
  "runtime_key_fingerprint": "fingerprint",
  "route_token": "pairwise-route-token"
}
```

Allowed route record classes:

- `local_direct`: current same-network, USB, hotspot, emulator, or explicit diagnostic endpoint candidates.
- `p2p_rendezvous`: short-lived remote P2P candidate-exchange records for authenticated NAT traversal.
- `relay_allocation`: short-lived blind encrypted relay or TURN-style allocation records used only after direct P2P fails.

Every non-local route record must be:

- Pairwise: derived from one paired client/runtime relationship, not from a global runtime id.
- Opaque to infrastructure: observers should not learn stable client id, stable runtime id, backend URLs, model inventory, prompts, files, memory, or provider status.
- Expiring: bounded by a short lifetime and rejected after expiration.
- Replay protected: bound to a nonce, time window, and authenticated session establishment.
- Identity bound: usable only when the paired client and runtime complete the encrypted session and challenge-response flow.

A practical future record shape is:

```json
{
  "class": "p2p_rendezvous",
  "record_id": "opaque-pairwise-record-id",
  "encrypted_body": "opaque-candidate-material",
  "expires_at": "2026-06-24T12:00:00Z",
  "anti_replay_nonce": "nonce",
  "protocol_version": 1
}
```

`host` and `port` are never the normal product target. If a QR payload or local setting carries them, treat them as `dev_endpoint_hint` or `local_direct` candidates for compatibility and diagnostics only. Future `route.*` protocol messages should be reserved until v0.2 implementation work starts; v0.1 should not expose active route messages that imply remote P2P is already implemented.

## Threat Model

Assets:

- Runtime host control.
- Trusted device identities and keys.
- Model prompts and responses.
- Model inventory and provider health.
- Chat history, memory notes, future summaries, and future indexes.
- Files, images, future tools, future web search, future MCP, and future automations.
- Backend credentials and local backend URLs.

Threats:

- Same-network attacker attempts to send runtime commands.
- Unpaired remote peer discovers a rendezvous record and attempts to connect.
- Bootstrap/DHT observer correlates stable identifiers across time.
- Relay operator attempts to inspect AI payloads or infer model usage.
- Stale NAT candidates are replayed.
- Lost paired client remains trusted after the user expects revocation.
- Manual endpoint compatibility accidentally becomes normal onboarding.
- Client-side code attempts direct Ollama/LM Studio access for convenience.

Required mitigations:

- Pairing-derived route tokens instead of public stable identifiers.
- Short-lived rendezvous and candidate records.
- Challenge-response authentication on every session.
- End-to-end encryption between paired devices.
- Replay protection for rendezvous and NAT traversal.
- Device revocation that applies to all route types.
- Minimal discovery metadata.
- Strict runtime-host mediation for all backend calls.
- Clear diagnostics that distinguish local direct, P2P, and relay paths.

## Non-Goals

- Implementing networking in this documentation pass.
- Building a public AetherLink node network in v0.1.
- Treating any future rendezvous, bootstrap, DHT, signaling, or relay component as a model backend, account backend, or product data service.
- Making runtimes discoverable by unpaired devices.
- Adding accounts as a trust requirement.
- Moving model execution to cloud infrastructure.
- Letting clients call Ollama, LM Studio, or future serving backends directly.
- Treating mDNS, local IPs, or fixed host/port entry as the final product connection model.
- Exposing model inventory, prompts, responses, files, memory, or backend URLs through discovery or relay infrastructure.

## Version Boundaries

### v0.1

v0.1 should remain local-direct and identity-first. The current local runtime server is real, but the current local/dev routes are compatibility and validation paths, not the intended final connection design:

- QR pairing establishes trusted client/runtime identity.
- Runtime commands require trusted-device authentication.
- Client stores runtime identity as the target, with host/port only as optional endpoint hints.
- Same-network/local discovery, USB or emulator forwarding, and manual diagnostic endpoints can resolve direct route candidates.
- Bonjour/local discovery may advertise minimal route hints such as `route_token`.
- Manual endpoint entry is development/diagnostics only.
- No production NAT traversal.
- No production DHT/bootstrap rendezvous.
- No production relay path.
- No direct client access to Ollama or LM Studio.

### v0.2

v0.2 should make remote connectivity real enough to test across different networks:

- Define the production encrypted session handshake.
- Bind sessions to paired runtime and client keys.
- Add replay protection and token rotation rules.
- Add STUN-like address discovery and candidate gathering.
- Add a privacy-preserving rendezvous or bootstrap service for short-lived candidate exchange.
- Attempt authenticated direct P2P before relay.
- Add blind encrypted relay/TURN-style fallback for blocked networks.
- Add diagnostics for route type, failure reason, and relay use.
- Keep AI payloads, backend calls, model inventory, files, memory, and credentials invisible to rendezvous and relay infrastructure.

### Later

Later releases can distribute bootstrap further, support more runtime platforms, and support more client platforms. The invariant does not change: clients control sessions, runtime hosts mediate execution, and only paired identities can communicate.
