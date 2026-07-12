# Production P2P/NAT V1 Bounded Handoff V2

## Closed Status

This immutable record supersedes `handoff-v1` after its canonical-contract
dependency passed. It records both `canonical-contracts` and
`no-network-conformance` as completed. The production design remains
`not_implemented`, `route.refresh` remains the only active traversal-related
namespace, and every package keeps `networkIOAllowed=false`.

## Completed No-Network Scope

- One shared fixture fixes all five `ALP1` version 1 canonical object encodings,
  transcript SHA-256, and role-bound HMAC-SHA256 values for Kotlin and Swift.
- Strict parsers enforce ordered fields, fixed scalar lengths, on-curve P-256
  points, complete frame ceilings, candidate ordering, and validation-time-bound
  freshness paths.
- Candidate policy rejects prohibited raw address classes before network I/O.
- Replay state is pair-and-role scoped, globally nonce-bound, expiry bounded, and
  capacity fail-closed without evicting live entries.
- Readiness requires path reachability, identity verification, key confirmation,
  and application readiness in exact order for one pair and generation. Invalid,
  stale, cross-pair, retry, and fallback races cannot create a ready channel.

The platform uses only standard SHA-256 and HMAC primitives to verify fixed
vectors. This record does not select a production networking or session
cryptography library.

## Remaining Block

`controlled-network-spike` remains `blocked_on_separate_review`. Service trust,
pair authorization and retention, candidate privacy and scope, ICE and consent,
TURN credentials and abuse controls, transition semantics, and measured release
budgets all remain open. A new versioned handoff is required before any socket,
candidate exchange, STUN, TURN, hole punching, or direct application traffic.

## Evidence Boundary

This is static and no-device/no-network conformance evidence. It does not prove a
concrete connector, real NAT traversal, public-network behavior, physical
Android, optical QR, latency, memory, CPU, battery, interoperability, deployment,
or production readiness.
