# Production P2P/NAT Security Hardening Context

This directory is a selection-gated security-design portfolio for the future
production P2P/NAT milestone. It is derived from current source, not a
vulnerability scan, implementation plan, or claim that production NAT traversal
exists.

No production design has been selected. The recommended protocol behavior is
not implemented.

## Source Identity

- Local source root: `/Users/hanchangha/Desktop/project`
- Git branch: `main`
- Git HEAD: `1f839e44b261f7fdc86009bd6389777eda0f65e5`
- Evidence manifest: `evidence.sha256`
- Evidence manifest SHA-256:
  `2b2a44f2ac7a2f081a5fbc7856a5b3d7dbe1585cec59c871282c98c9d4e33cbd`
- Evidence artifacts: 13 source, schema, and fixture files.
- Manifest verification: all 13 entries matched the current files when this
  portfolio was prepared.
- Source drift: **present**. The worktree contains unrelated tracked changes and
  untracked source, including transport and connection-manager work. The
  manifest binds this review to the exact current bytes of the 13 inventoried
  files; Git HEAD alone does not describe them.
- Evidence mode: source review plus existing no-device tests and documentation.
  No physical device or public-network experiment was performed for this
  portfolio.

## Evidence Registry

| ID | Title | Claim type | Primary evidence | What it establishes |
| --- | --- | --- | --- | --- |
| `E001` | Same-authority P2P-first route planning | Observed | `apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeRemoteRoutePlanner.kt:31`, `apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeRemoteRoutePlanner.kt:36` | Pending pairing material takes authority over trusted stored state, identity matching is required, and prepared P2P routes precede relay routes; no candidate is interpreted. |
| `E002` | Trusted P2P route persistence boundary | Observed | `apps/android/core/pairing/src/main/java/com/localagentbridge/android/core/pairing/PairingStore.kt:501`, `apps/android/core/pairing/src/main/java/com/localagentbridge/android/core/pairing/PairingStore.kt:533` | Persisted P2P material is restored only when complete, canonical, version 1, and fresh. This is storage validation, not candidate or service authentication. |
| `E003` | QR P2P family validation | Observed | `apps/android/core/pairing/src/main/java/com/localagentbridge/android/core/pairing/RuntimePairingPayload.kt:121`, `apps/android/core/pairing/src/main/java/com/localagentbridge/android/core/pairing/RuntimePairingPayload.kt:197` | Android accepts only a complete, bounded `p2p_rendezvous` field family and rejects unsupported class/version and incomplete material. It defines no candidate grammar or target policy. |
| `E004` | Injected P2P connector and fallback seam | Observed | `apps/android/core/transport/src/main/java/com/localagentbridge/android/core/transport/RuntimeConnectionManager.kt:158`, `apps/android/core/transport/src/main/java/com/localagentbridge/android/core/transport/RuntimeConnectionManager.kt:181`, `apps/android/core/transport/src/main/java/com/localagentbridge/android/core/transport/RuntimeConnectionManager.kt:288`, `apps/android/core/transport/src/main/java/com/localagentbridge/android/core/transport/RuntimeConnectionManager.kt:396` | The manager validates identity, token separation, and expiration, delegates P2P behavior to an optional connector, and can proceed to relay after failure. No production connector is supplied. |
| `E005` | Opaque P2P route envelope | Observed | `apps/android/core/transport/src/main/java/com/localagentbridge/android/core/transport/RuntimePeerToPeerRoutePreparation.kt:3` | Current preparation carries a record id, a field named encrypted candidate material, expiration, nonce, and protocol version; it checks shape, freshness, and route-token separation but does not interpret candidates or prove encryption. |
| `E006` | macOS route and pair lifecycle owner | Observed | `apps/macos/CompanionCore/Sources/CompanionAppModel.swift:700`, `apps/macos/CompanionCore/Sources/CompanionAppModel.swift:873`, `apps/macos/CompanionCore/Sources/CompanionAppModel.swift:1799` | The app model owns the connection manager and starts pair-scoped private-overlay and relay transports, but the inventoried source does not provide production candidate gathering or traversal. |
| `E007` | Authenticated route-refresh envelope | Observed | `apps/macos/CompanionCore/Sources/LocalRuntimeMessageRouter.swift:3447` | The runtime can return a complete fresh P2P opaque field family through authenticated route refresh, with canonicality and expiration checks. This does not authenticate a candidate service. |
| `E008` | Pair-scoped private-overlay lifecycle seam | Observed | `apps/macos/CompanionCore/Sources/MacRuntimeConnectionManager.swift:17`, `apps/macos/CompanionCore/Sources/MacRuntimeConnectionManager.swift:98` | Current uncommitted source defines injected per-pair private-overlay and relay transport ownership with lifecycle isolation. It does not establish ICE, TURN, or secure path migration. |
| `E009` | macOS pairing and QR serialization boundary | Observed | `apps/macos/Pairing/Sources/PairingCoordinator.swift:186` | macOS emits canonical, complete opaque P2P QR material from a pairing boundary that has long-term device identity context. The encrypted body's producer and cryptographic meaning remain outside this code. |
| `E010` | Common runtime transport boundary | Observed | `apps/macos/Transport/Sources/RuntimeTransport.swift:4`, `apps/macos/Transport/Sources/RuntimeTransport.swift:8` | Runtime transports share lifecycle and disconnect contracts, providing an integration boundary but no production P2P identity transcript or traversal semantics. |
| `E011` | Pairing QR opaque-family schema | Observed | `packages/protocol-schema/pairing-qr.schema.json:430`, `packages/protocol-schema/pairing-qr.schema.json:561`, `packages/protocol-schema/pairing-qr.schema.json:655` | The pairing schema carries a complete opaque P2P record family rather than executable ICE credentials or a plaintext candidate grammar. |
| `E012` | Shared all-or-nothing protocol schema | Observed | `packages/protocol-schema/protocol.schema.json:608`, `packages/protocol-schema/protocol.schema.json:639`, `packages/protocol-schema/protocol.schema.json:657` | The schema requires the P2P family together and fixes its class/version, but defines no ICE, STUN, TURN, consent, nomination, path migration, or transport-neutral session protocol. |
| `E013` | Compact cross-platform fixture | Observed | `shared/protocol/fixtures/macos-compact-p2p-rendezvous-pairing-uri.txt:1` | Swift/Kotlin compatibility covers serialization of opaque P2P fields; `opaque-candidate-1` is test material, not evidence of encryption or NAT traversal. |

## Active And Reserved Boundary

| Boundary | Active in current evidence | Reserved for a selected design |
| --- | --- | --- |
| Pair trust | QR-pinned runtime identity, paired identity fields, route-token separation | Binding both endpoint identities and pair state into a transport-neutral secure-session transcript |
| Route material | Opaque record id/body, expiration, anti-replay nonce, version, canonicality, persistence, refresh | Candidate grammar, candidate provenance, ICE username fragments/passwords, restart generations, end-of-candidates semantics |
| Traversal | Route ordering and a nullable connector interface | Candidate gathering, STUN transactions, ICE roles/checklists/nomination, NAT rebinding behavior, consent freshness |
| Fallback | A distinct development relay route exists | TURN allocation, scoped credentials, permissions, channel bindings, relay-only privacy mode, deterministic fallback policy |
| Signaling | QR and authenticated `route.refresh` can transport opaque bytes | Authenticated encrypted rendezvous sessions, replay state, candidate authorization, bounded retention, deletion, abuse controls |
| Data security | Existing local and development-relay paths have their own controls | One peer-verifiable secure session that is invariant across direct ICE and TURN paths |
| QUIC | No P2P QUIC implementation is evidenced | A contingent spike after the identity-bound session contract is frozen |

The word `encrypted` in a field name is not evidence that current code performs
or verifies encryption. We therefore treat confidentiality, peer authentication,
candidate authorization, and replay semantics inside that body as unknown.

## Evidence Limits

The source supports a narrow architectural diagnosis: it has a disciplined
opaque envelope and connector boundary that can host a future design, but it
does not reveal a production traversal implementation. The review did not prove
optical QR behavior, physical Android lifecycle behavior, public STUN or TURN
interoperability, symmetric-NAT success, IPv4/IPv6 mobility, carrier-NAT or VPN
behavior, captive-portal handling, consent freshness, relay capacity, signaling
availability, latency, memory, battery, or real different-network connectivity.

All performance, reliability, and operational statements in this portfolio are
source-derived, standards-derived, analogous, or hypothetical. None is measured.
