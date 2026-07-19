# Production P2P/NAT Security Hardening Context

This directory is a selection-gated security-design portfolio for the future
production P2P/NAT milestone. It is derived from current source, not a
vulnerability scan, implementation plan, or claim that production NAT traversal
exists.

The recommended profile and its seven pre-network recommendations have explicit
user approval for bounded design and policy handoffs. The production protocol
behavior remains not implemented.
`selection-profile.md`, `selection-profile.json`, and the closed immutable
`selection-decision.json` pin the selected options and authorization boundary.
The closed `implementation/handoff-v1.json` and `handoff-v1.md` authorized
canonical-contract execution first. The immutable `handoff-v2` records both
canonical contracts and no-network conformance as completed. The versioned
`handoff-v3` records that all seven pre-network recommendations are selected
while keeping socket execution, network I/O, library selection, and production
deployment unauthorized. The closed
`controlled-network-spike/review-v1` pair preserves the zero-selection proposal.
The separate closed `controlled-network-spike/decision-v1` and
`implementation/handoff-v4` select all four recommendations only for offline
Phase A inspection, compile-only, cryptographic-vector, and static-policy work.
The later `controlled-network-spike/decision-v2` and `implementation/handoff-v5`
authorized one exact acquisition of the official libjuice v1.7.2 source and
Android NDK r28c. That authority was consumed, and the mandatory source audit
rejected libjuice before compilation. The versioned `decision-v4`/`handoff-v7`
and `decision-v5`/`handoff-v8` records then authorized and consumed exact
read-only intake of libnice 0.1.23 and GLib 2.64.2. Two independent static
reviews rejected libnice before compilation. The closed `decision-v6` and
`implementation/handoff-v9` now keep replacement acquisition, compiler, socket,
runtime and harness network I/O, Phase B, measurement, and production deployment
unauthorized.
`route.refresh` remains the only active
traversal-related namespace.

## Current Phase A Progress Authority

`implementation/handoff-v4.json` remains the immutable four-recommendation
approval snapshot, while `handoff-v5`, `handoff-v7`, and `handoff-v8` preserve
the consumed one-shot acquisition authorities. The current authority is the
closed `implementation/handoff-v9.json`; current evidence status is recorded by
`controlled-network-spike/phase-a/progress-v8.json`. Neither record rewrites its
predecessors.

The exact official libjuice v1.7.2 archive and Android NDK r28c were acquired,
and the NDK was installed. Read-only source inspection found five P1 profile
failures and rejected libjuice before compilation. The later exact libnice
0.1.23 archive and detached-signature bytes plus the GLib 2.64.2 checksum and
archive were also acquired under bounded, consumed authorities. Two independent
static reviews found four P1 production-profile failures and rejected libnice
before any configure step, build system, compiler, archiver, linker, symbol tool,
test executable, socket, or runtime network operation. No networking library or
next candidate is selected.

The current static contract applies an execution-before-import SHA-256 preflight
to 44 files, including the acquisition and rejection records. The earlier
22-file `progress-v1` result remains historical and is not retroactively
changed.

The final aggregate log
`build/qa/check-no-device-quality-p2p-libjuice-source-audit-rejection-final-20260717.log`
exits 0 with exactly one overall success marker. It includes a
read-only rehash of the retained libjuice archive, byte-equivalent 81-file
source tree, NDK archive, installed NDK tools, Apple tools, and both manifest
copies. Existing development-relay loopback checks in that aggregate are a
separate regression surface; they do not execute libjuice or establish P2P
Phase A runtime or live-network evidence.

The one-shot source and toolchain acquisition authority is consumed; additional
acquisition, source execution, compiler/archive invocation, socket creation,
runtime/harness/controlled-spike network I/O, Phase B
execution/network/socket authority, external egress, production network I/O,
and production deployment are all `false`. This is current no-device static and
local regression evidence only, not physical Android or live-network proof. It
establishes exact acquisition and static rejection, not compilation, ABI,
library execution, sockets, ICE/STUN/TURN traffic, NAT traversal, Phase B,
external egress, production networking, or deployment.

## Source Identity

- Local source root: `/Users/hanchangha/Desktop/project`
- Git branch: `main`
- Git HEAD: `1daf5b8f3fee7286946b813e9267d9d6f5f359a7`
- Evidence manifest: `evidence.sha256`
- Evidence manifest SHA-256:
  `d2f83be1b884cf9973037c72d2ee81f583fbf33150f6f8d843b787c7c83e29b8`
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
| `E001` | Same-authority P2P-first route planning | Observed | `apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeRemoteRoutePlanner.kt:32`, `apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeRemoteRoutePlanner.kt:38`, `apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeRemoteRoutePlanner.kt:274` | Pending identity-matched pairing material takes authority over trusted stored state, prepared P2P routes precede relay routes, and USB-reverse relay material is excluded unless an explicit debug-only flag is enabled. This is route filtering; no candidate is interpreted. |
| `E002` | Trusted P2P route persistence boundary | Observed | `apps/android/core/pairing/src/main/java/com/localagentbridge/android/core/pairing/PairingStore.kt:501`, `apps/android/core/pairing/src/main/java/com/localagentbridge/android/core/pairing/PairingStore.kt:533` | Persisted P2P material is restored only when complete, canonical, version 1, and fresh. This is storage validation, not candidate or service authentication. |
| `E003` | QR P2P family validation | Observed | `apps/android/core/pairing/src/main/java/com/localagentbridge/android/core/pairing/RuntimePairingPayload.kt:36`, `apps/android/core/pairing/src/main/java/com/localagentbridge/android/core/pairing/RuntimePairingPayload.kt:149`, `apps/android/core/pairing/src/main/java/com/localagentbridge/android/core/pairing/RuntimePairingPayload.kt:201` | Android bounds the complete QR/query input and accepts only a complete, canonical `p2p_rendezvous` field family, rejecting unsupported class/version and incomplete material. It defines no candidate grammar or target policy. |
| `E004` | Injected P2P connector and fallback seam | Observed | `apps/android/core/transport/src/main/java/com/localagentbridge/android/core/transport/RuntimeConnectionManager.kt:126`, `apps/android/core/transport/src/main/java/com/localagentbridge/android/core/transport/RuntimeConnectionManager.kt:165`, `apps/android/core/transport/src/main/java/com/localagentbridge/android/core/transport/RuntimeConnectionManager.kt:350`, `apps/android/core/transport/src/main/java/com/localagentbridge/android/core/transport/RuntimeConnectionManager.kt:395` | The manager validates identity, token separation, expiration, and the relay-scope tag; delegates P2P and relay behavior to optional connectors; preserves cancellation; and orders prepared P2P before relay fallback. The scope tag is not DNS-resolution evidence, and no production P2P connector is supplied. |
| `E005` | Opaque P2P route envelope | Observed | `apps/android/core/transport/src/main/java/com/localagentbridge/android/core/transport/RuntimePeerToPeerRoutePreparation.kt:3` | Current preparation carries a record id, a field named encrypted candidate material, expiration, nonce, and protocol version; it checks shape, freshness, and route-token separation but does not interpret candidates or prove encryption. |
| `E006` | macOS route and pair lifecycle owner | Observed | `apps/macos/CompanionCore/Sources/CompanionAppModel.swift:731`, `apps/macos/CompanionCore/Sources/CompanionAppModel.swift:910`, `apps/macos/CompanionCore/Sources/CompanionAppModel.swift:1981` | The app model owns the connection manager and starts pair-scoped private-overlay and relay transports, but the inventoried source does not provide production candidate gathering or traversal. |
| `E007` | Authenticated route-refresh envelope | Observed | `apps/macos/CompanionCore/Sources/LocalRuntimeMessageRouter.swift:11357`, `apps/macos/CompanionCore/Sources/LocalRuntimeMessageRouter.swift:11409` | The runtime can return a complete fresh P2P opaque field family through authenticated route refresh, with canonicality and expiration checks. Relay host/scope validation in the same envelope does not authenticate DNS resolution or a candidate service. |
| `E008` | Pair-scoped private-overlay lifecycle seam | Observed | `apps/macos/CompanionCore/Sources/MacRuntimeConnectionManager.swift:17`, `apps/macos/CompanionCore/Sources/MacRuntimeConnectionManager.swift:98` | Current uncommitted source defines injected per-pair private-overlay and relay transport ownership with lifecycle isolation. It does not establish ICE, TURN, or secure path migration. |
| `E009` | macOS pairing and QR serialization boundary | Observed | `apps/macos/Pairing/Sources/PairingCoordinator.swift:186` | macOS emits canonical, complete opaque P2P QR material from a pairing boundary that has long-term device identity context. The encrypted body's producer and cryptographic meaning remain outside this code. |
| `E010` | Common runtime transport boundary | Observed | `apps/macos/Transport/Sources/RuntimeTransport.swift:4`, `apps/macos/Transport/Sources/RuntimeTransport.swift:8`, `apps/macos/Transport/Sources/RuntimeTransport.swift:70` | Runtime transports share lifecycle and disconnect contracts, and discovery TXT entries are byte-bounded metadata. These are integration and metadata boundaries, not a production P2P identity transcript, DNS binding, or traversal semantics. |
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
