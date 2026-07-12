# Production P2P/NAT V1 Pre-Network Review V1

## Status

This is a `proposed_not_selected` review packet for the seven decisions that
block `controlled-network-spike`. It does not amend the closed `handoff-v2`,
create a new handoff, select a networking library, or authorize network I/O or
deployment. The complete recommendation set requires explicit approval,
explicit modifications plus approval, or rejection.

## Recommended Decision Set

| Decision | Recommended option | Core boundary |
| --- | --- | --- |
| `service-ownership-and-trust` | `first-party-tls13-signed-service-config` | First-party rendezvous/STUN/TURN, TLS 1.3 rendezvous plus authenticated STUN/TURN, signed expiring service configuration, no unauthenticated fallback |
| `pair-authorization-and-retention` | `opaque-generation-scoped-capabilities` | Separate 600-second publish/fetch/allocation capabilities, generation rotation, 30-second revoke and deletion closure, no stable service-visible pair id |
| `candidate-privacy-and-scope` | `e2e-limited-direct` | End-to-end candidate encryption, no host candidate by default, explicit one-session same-link consent, prohibited targets rejected before I/O |
| `ice-and-consent-policy` | `full-ice-regular-nomination-runtime-initiator` | Full ICE, macOS initiates and controls, regular nomination, generation-scoped trickle/restart, 4-6 second consent checks and 30-second expiry |
| `turn-credential-and-abuse-policy` | `short-lived-pair-scoped-turn` | Authenticated 600-second pair credentials and allocations, remote-pair-only permissions, explicit quotas, no insecure outage fallback |
| `session-transition-semantics` | `between-request-cutover-fail-inflight` | Cut over only between requests; fail active requests without automatic replay; admit new work only after full readiness |
| `release-budgets` | `measured-matrix-with-hard-stop-budgets` | 1,000 completed sessions across required cohorts, 99% authenticated traversal, explicit latency/resource/revocation/abuse/rollback hard stops |

## Standards Basis

- RFC 8445 full ICE uses one controlling and one controlled agent and regular
  nomination; aggressive nomination is not part of the first profile.
  Peer-reflexive candidates are learned from connectivity checks rather than
  proactively gathered or manufactured as signaled candidates.
- RFC 7675 consent freshness uses a default five-second interval randomized to
  4-6 seconds and expires consent after 30 seconds. Traffic stops on the
  affected 5-tuple when consent expires, and restart uses new credentials.
- RFC 8656 gives TURN allocations a default 600-second lifetime. This proposal
  keeps credentials and the first controlled allocation at that same bound.
- TLS service authentication, pair endpoint authentication, candidate-envelope
  confidentiality, ICE consent, and application readiness remain independent
  gates. Passing one never implies another.

## Review Rules

The seven decisions are one security and operability set. A review may approve
the complete recommendation, approve named modifications, or reject it. A
partial approval does not authorize sockets. Any modification must preserve:

- `routeToken` separation from candidate, ICE, TURN, transcript, capability,
  service, or application authority.
- End-to-end endpoint identity and key confirmation on both direct and relay
  paths before application readiness.
- Default-deny destination policy, bounded replay and resource state, no
  plaintext or unauthenticated downgrade, and deterministic rollback.
- No backend credential, prompt, response, file, memory, model, backend URL, or
  application payload exposure to rendezvous, STUN, or TURN control planes.

## Required Evidence Before A Network Handoff

Approval of this packet would select policies, not prove them. A later handoff
must still name an isolated non-production harness and require deterministic
service-trust rotation, pair capability, candidate policy, ICE/consent, TURN,
transition, and release-budget tests. Library selection must be reviewed
separately against the selected contracts. Production deployment remains a
different approval.

## Current Authorization Boundary

- `networkIOAllowed=false`
- `librarySelectionAuthorized=false`
- `productionDeploymentAuthorized=false`
- `nextHandoffAuthorized=false`
- `controlled-network-spike` remains `blocked_on_separate_review`

No physical Android, optical QR, public service, STUN/TURN traffic, candidate
exchange, hole punching, NAT traversal, application traffic, latency, memory,
battery, capacity, interoperability, deployment, or production readiness is
implemented or proven by this packet.
