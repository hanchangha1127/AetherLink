# Production P2P/NAT V1 Controlled-Network Spike Approval Decision V1

## Closed Decision

Explicit user instruction approves all four `review-v1` recommendations for a
bounded phase A evidence handoff. The approved candidates are
`libjuice-1.7.2-static-c-abi`,
`platform-native-p256-hkdf-sha256-aes256gcm`,
`linux-netns-twin-agent-local-services`, and
`numeric-endpoint-allowlist-plus-os-egress-witness`.

The immutable review remains the historical proposal. This decision does not
rewrite it or claim that its required source, compile, cryptographic, harness,
or egress evidence already exists.

## Phase A Authorization

`handoff-v4` may authorize only the following work:

- inspect and hash-pin exact libjuice source supplied by the user out of band or
  already present in the workspace, then complete supply-chain, license,
  generated-file, dependency, parser, nomination, consent, TURN, callback,
  cancellation, and teardown audits;
- compile the reviewed adapter for Android minSdk 26 and macOS without creating
  or using a socket;
- implement and verify transport-neutral P-256, HKDF-SHA-256, AES-256-GCM,
  nonce, transcript, and bidirectional key-confirmation fixed vectors;
- implement static phase A harness manifests, numeric endpoint policy, deny-all
  egress witness configuration, resource ceilings, and content-free evidence
  checks without executing phase B.

Offline source inspection is limited to user-provided or pre-existing workspace
material. This decision does not authorize `git clone`, `git fetch`, `curl`,
`wget`, package-manager download, or any other network source acquisition. The
inspected code may not execute or open a socket.

## Closed Execution Gates

- `controlledSpikeNetworkIOAllowed=false`
- `sourceAcquisitionNetworkIOAllowed=false`
- `controlledSpikeSocketExecutionAuthorized=false`
- `phaseBExecutionAuthorized=false`
- `productionNetworkIOAllowed=false`
- `productionDeploymentAuthorized=false`

No runtime or harness candidate exchange, DNS, proxy, STUN, TURN, ICE check,
hole punching, application traffic, Linux network-namespace execution, or
production deployment is authorized.

## Required Evidence

Phase A must produce the exact source and supply-chain audit, reproducible
Android/macOS compile-only evidence, cross-platform session-cryptography
vectors, static harness and egress-policy evidence, and an independent phase A
security review. Failure rejects the affected option and requires a new
versioned decision; it cannot silently select a fallback.

## Next Gate

A separate versioned decision is required after all phase A evidence passes and
before any socket creation, controlled network I/O, phase B harness execution,
measurement, or deployment. Approval alone is not implementation, NAT
traversal, interoperability, performance, physical-device, or production proof.
