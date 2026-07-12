# Production P2P/NAT V1 Bounded Handoff V3

## Closed Status

This immutable record supersedes `handoff-v2`. It links the unchanged
pre-network review to `decision-v1`, where explicit user instruction resolved all
seven decisions to their exact recommended options. The production design
remains `not_implemented`, the proposal remains unmeasured, and `route.refresh`
remains the only active traversal-related namespace.

## Resolved Decisions

All seven pre-network decisions are `resolved` with
`approvalSource=explicit_user_instruction`. Resolution closes the selection
questions; it does not constitute library selection, network execution,
deployment approval, or performance evidence.

## Existing No-Network Scope

The completed `canonical-contracts` and `no-network-conformance` packages retain
their handoff-v2 evidence and no-network boundaries. The canonical package also
pins the previously omitted Android `P2pNatContract.kt` limits. Every evidence
path is paired with its SHA-256 in the machine handoff so source or test drift
fails the approval gate. Their completion does not
prove a concrete connector, real NAT traversal, public-network behavior,
physical Android behavior, latency, memory, CPU, battery, interoperability,
deployment, or production readiness.

## Remaining Block

`controlled-network-spike` remains `blocked_on_separate_review` with
`executionAuthorized=false`, `networkIOAllowed=false`, and
`socketExecutionAuthorized=false`. No candidate exchange, STUN, TURN, hole
punching, direct application traffic, or other socket execution is authorized.

The next step is a separate networking and session-cryptography library review
plus isolated-harness safety review. That review must cover socket destination
and egress controls before a later versioned decision may authorize network I/O.
The machine-readable `blockedOnReviews` list contains all four exact review IDs:
`networking_library_selection`, `session_cryptography_library_selection`,
`isolated_harness_design`, and `socket_destination_and_egress_controls`.

## Authorization Boundary

- `networkIOAllowed=false`
- `librarySelectionAuthorized=false`
- `productionDeploymentAuthorized=false`
- `controlledNetworkSpikeSocketExecutionAuthorized=false`

No measurements are claimed by this handoff.
