# Production P2P/NAT V1 Controlled-Network Spike Review V1

## Status

This closed review packet is `proposed_not_selected` and
`measurementStatus=not_started`. It addresses the four `handoff-v3` blockers
without selecting a library, implementing a harness, creating an execution
artifact, creating a handoff, or authorizing network or socket I/O. Every
decision remains `resolution=null` and `approvalSource=null`.

The packet must be superseded by a new versioned review if amended. A separate
versioned decision covering all four decision ids is required before socket
execution. Recommendations in this packet are decision-ready proposals, not
approval.

## Decision Summary

| Order | Decision | Recommended option | State |
| --- | --- | --- | --- |
| 1 | `networking_library_selection` | `libjuice-1.7.2-static-c-abi` | `proposed_not_selected` |
| 2 | `session_cryptography_library_selection` | `platform-native-p256-hkdf-sha256-aes256gcm` | `proposed_not_selected` |
| 3 | `isolated_harness_design` | `linux-netns-twin-agent-local-services` | `proposed_not_selected` |
| 4 | `socket_destination_and_egress_controls` | `numeric-endpoint-allowlist-plus-os-egress-witness` | `proposed_not_selected` |

Each decision has exactly three options and one recommendation. The complete
set has zero selected decisions and four recommendations. The
`controlled-network-spike` remains `blocked_on_explicit_selection`.

## Official Evidence

Official sources were checked on `2026-07-12`:

- libjuice: [repository](https://github.com/paullouisageneau/libjuice),
  [v1.7.2 public C header](https://github.com/paullouisageneau/libjuice/blob/v1.7.2/include/juice/juice.h),
  and [v1.7.2 release](https://github.com/paullouisageneau/libjuice/releases/tag/v1.7.2).
  The project documentation claims C support on Android and macOS, MPL-2.0,
  no required dependencies, and implementations of RFC 8445, RFC 8489,
  RFC 8656, and RFC 7675. These are upstream claims, not local proof of regular
  nomination, consent behavior, source provenance, compatibility, or fitness.
- libnice: [project and 0.1.23 release index](https://libnice.freedesktop.org/)
  and [NiceAgent reference](https://libnice.freedesktop.org/libnice/NiceAgent.html).
  The reference exposes regular-nomination and consent-freshness controls; a
  compile-only and source audit is still required before any fallback decision.
- libdatachannel: [repository](https://github.com/paullouisageneau/libdatachannel),
  [v0.24.3 release](https://github.com/paullouisageneau/libdatachannel/releases/tag/v0.24.3),
  and [native C API documentation](https://github.com/paullouisageneau/libdatachannel/blob/v0.24.3/DOC.md).
  Its broader WebRTC stack and dependency surface are reasons to retain it as
  an alternative rather than infer suitability.
- Android: [cryptography guidance](https://developer.android.com/privacy-and-security/cryptography),
  [`KeyAgreement`](https://developer.android.com/reference/javax/crypto/KeyAgreement),
  and [`KeyGenParameterSpec`](https://developer.android.com/reference/android/security/keystore/KeyGenParameterSpec).
  The project minSdk is 26, so the proposal uses provider-neutral in-memory
  ephemeral P-256 generation and does not depend on AndroidKeyStore API 31
  ephemeral ECDH functionality.
- Apple CryptoKit: [`P256`](https://developer.apple.com/documentation/cryptokit/p256),
  [`HKDF`](https://developer.apple.com/documentation/cryptokit/hkdf), and
  [`AES.GCM`](https://developer.apple.com/documentation/cryptokit/aes/gcm).
- RFC Editor: [RFC 8445](https://www.rfc-editor.org/rfc/rfc8445.html),
  [RFC 8489](https://www.rfc-editor.org/rfc/rfc8489.html),
  [RFC 8656](https://www.rfc-editor.org/rfc/rfc8656.html),
  [RFC 7675](https://www.rfc-editor.org/rfc/rfc7675.html), and
  [RFC 5869](https://www.rfc-editor.org/rfc/rfc5869.html).

Official documentation establishes review inputs only. It does not establish
that a source tree was pinned, downloaded, compiled, audited, executed, or
measured by this packet.

## Recommended Set

### Networking Library

Recommend `libjuice-1.7.2-static-c-abi`, subject to later explicit selection.
The proposed integration is a pinned static library behind a versioned C ABI on
Android minSdk 26 and macOS. Before selection, compile-only and source audit must
establish the exact release tag, commit SHA, archive digest, dependency closure,
regular nomination, RFC 7675 consent behavior, TURN authentication, parser
bounds, callback threading, cancellation, and fail-closed shutdown.

No source download or selection is authorized by this packet. A separately
authorized, bounded pre-selection source audit may later acquire an exact pin
for compile-only review without selecting the library. If any required audit
or compile-only result fails, libjuice is rejected and a new versioned review
must evaluate `libnice-0.1.23-glib-c-abi`; the fallback is not selected
implicitly. `libdatachannel-0.24.3-datachannel-stack` remains the broader-stack
alternative.

### Session Cryptography

Recommend `platform-native-p256-hkdf-sha256-aes256gcm`: macOS CryptoKit and
Android provider-neutral JCA. The contract retains the existing canonical ALP1
transport-neutral identity transcript, ephemeral P-256 ECDH, RFC 5869
HKDF-SHA-256, AES-256-GCM, and bidirectional transcript-bound key confirmation.
Direct and relay paths keep the same identity and cryptographic floor.

Android uses provider-neutral in-memory `secp256r1` key generation,
`KeyAgreement/ECDH`, `Mac/HmacSHA256`, and `Cipher/AES/GCM/NoPadding`. It must
not depend on AndroidKeyStore API 31 for ephemeral ECDH because minSdk is 26.
`pinned-boringssl-native` and `libdatachannel-dtls-session` remain alternatives;
neither may silently replace or weaken ALP1.

### Isolated Harness

Recommend `linux-netns-twin-agent-local-services` with two strictly separated
phases. Phase A is Android and macOS compile-only: no source download, socket
creation, or network I/O. Phase B remains blocked until a later versioned
decision authorizes two agent processes in separate Linux network namespaces,
local STUN/TURN only, no host network, and deny-all external egress.

Phase B ceilings are exact: 600 seconds per run, 120 seconds setup, 60 seconds
session establishment, 45 seconds consent observation, two local service
processes maximum, one CPU core, 256 MiB resident memory, 64 file descriptors,
and 16 sockets per process, plus 10,000 captured packets and 16,777,216 captured
bytes per run. A breach invalidates the run and kills all harness processes.

### Destination And Egress Controls

Recommend `numeric-endpoint-allowlist-plus-os-egress-witness`. Each run uses a
signed, immutable allowlist of exact protocol, numeric IPv4 or IPv6 address, and
port tuples. Candidate policy runs before every library or socket API. An OS
deny-all witness must be armed before a permitted operation, and packet capture
must assert every packet against the same allowlist.

DNS, mDNS, DoH, DoT, proxies, PAC, environment proxies, URLs, redirects,
wildcards, port ranges, metadata services, and default external routes are
prohibited. Policy drift, witness failure, or an unexpected packet kills the
run. Logs and retained evidence redact secrets and remain content-free.

## Security Floors

- `routeToken` remains separate from every candidate, ICE, STUN, TURN,
  endpoint, transcript, capability, traffic-key, allowlist, and application
  authority.
- Both paired endpoint identities and the ALP1 transcript are authenticated
  before application readiness. No application payload is admitted before path
  validation, endpoint identity verification, and bidirectional key
  confirmation.
- There is no plaintext, unauthenticated, anonymous, legacy, lower-suite,
  relay-specific, or DTLS-only identity downgrade.
- Destinations are default-deny. Candidate policy precedes the library, and an
  immutable exact numeric tuple allowlist precedes socket creation.
- DNS and proxy use, URL fetches, redirects, and default external routes are
  prohibited.
- The exact process, CPU, memory, descriptor, socket, packet, byte, setup,
  session, consent, and wall-clock ceilings stated above are mandatory.
- Logs are content-free: bounded reason codes, counters, durations, endpoint
  labels, and redacted digests only. No tokens, credentials, keys, nonces, raw
  candidates, packet payloads, or application content are retained.
- Any policy, route, allowlist, namespace, witness, capture, or resource drift
  kills all harness processes and invalidates the run.

## Required Evidence Before Selection

- Under a separate bounded pre-selection source-audit authorization, pin and
  review the exact upstream release tag, commit SHA, archive SHA-256, license
  set, build flags, generated files, and complete transitive dependency closure.
  This packet itself authorizes no source acquisition.
- Produce reproducible Android minSdk 26 and macOS compile-only evidence with
  source download, socket creation, and network I/O disabled.
- Complete line-referenced source audits for regular nomination, role handling,
  consent freshness and expiry, TURN authentication, parser bounds, callbacks,
  cancellation, teardown, and destination control.
- Match Swift and Kotlin vectors for P-256 validation and ECDH, RFC 5869 HKDF,
  AES-256-GCM, nonce handling, ALP1 transcript binding, and bidirectional key
  confirmation, including negative and provider-error vectors.
- Review the Linux namespace, local STUN/TURN, route, firewall, signed allowlist,
  OS witness, packet-capture, process-isolation, exact-ceiling, kill-switch, and
  content-free evidence designs without executing them.
- Prove statically that candidate policy and immutable numeric tuple checks
  occur before every library and socket boundary, and define forbidden IPv4,
  IPv6, DNS, proxy, redirect, metadata, wildcard, and route-injection vectors.

All unresolved approval inputs recorded in `review-v1.json` must have named
owners and reviewed evidence. Failure of libjuice compile-only or source audit
rejects that recommendation and requires a new versioned libnice review.

## Authorization Boundary

- `librarySelectionAuthorized=false`
- `harnessImplementationAuthorized=false`
- `networkIOAllowed=false`
- `socketExecutionAuthorized=false`
- `productionDeploymentAuthorized=false`
- `nextHandoffAuthorized=false`
- Approval boundary:
  `separate_versioned_decision_before_socket_execution`
- Required decisions, in order:
  `networking_library_selection`,
  `session_cryptography_library_selection`,
  `isolated_harness_design`, and
  `socket_destination_and_egress_controls`

Partial approval does not authorize download, selection, implementation,
network I/O, socket execution, artifact creation, a new handoff, or deployment.

## Evidence Boundary

This packet contains official-source review and proposed contracts only. It
creates no execution artifact and no handoff. It does not claim a downloaded or
selected library, Android or macOS compilation, implemented harness, opened
socket, STUN/TURN exchange, ICE checklist, consent traffic, packet capture, NAT
traversal, direct path, relay fallback, application payload, physical-device
behavior, live-network behavior, interoperability, performance, resource use,
deployment, or production readiness.

`selectedDecisionCount=0`, `recommendationCount=4`, and
`controlledNetworkSpikeStatus=blocked_on_explicit_selection` remain the complete
review outcome.
