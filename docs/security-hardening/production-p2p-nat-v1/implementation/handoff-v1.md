# Production P2P/NAT V1 Bounded Handoff

## Closed Status

This immutable `handoff-v1` is closed and records the bounded authorization for
`production_p2p_nat_v1_recommended`. The production design remains
`not_implemented`. `route.refresh` is the only active traversal-related protocol
namespace. No package may perform network I/O, select a production networking or
session-cryptography library, or authorize deployment. Platform-standard digest
and HMAC primitives may be used only to verify the fixed canonical vectors.

## Package State

| Package | Authorization | Execution | Execution authorized | Network I/O |
| --- | --- | --- | --- | --- |
| `canonical-contracts` | `authorized` | `not_started` | `true` | `false` |
| `no-network-conformance` | `blocked_on_dependency` | `not_started` | `false` | `false` |
| `controlled-network-spike` | `blocked_on_separate_review` | `not_started` | `false` | `false` |

`no-network-conformance` remains blocked until `canonical-contracts` satisfies
its exit criteria. `controlled-network-spike` requires a separate review and
cannot execute under this handoff.

## Open Pre-Network Decisions

All seven decisions remain `open`:

- `service-ownership-and-trust`
- `pair-authorization-and-retention`
- `candidate-privacy-and-scope`
- `ice-and-consent-policy`
- `turn-credential-and-abuse-policy`
- `session-transition-semantics`
- `release-budgets`

## Authorization Boundary

The selected scope includes canonical contracts and later no-network conformance,
but this first handoff version authorizes execution of canonical sealed-record,
transcript, encoding, fixed-vector, replay, expiry, error, and resource-limit
contract work only. It does not authorize public rendezvous, STUN, TURN,
candidate exchange, hole punching, direct payload traffic, production deployment,
a concrete production library, or any
physical-device, optical-QR, live-network, performance, battery, or
interoperability claim.

Any scope expansion must supersede this file with a new versioned handoff after
the required review; this closed record is not edited in place.
