# Production P2P/NAT V1 Bounded Handoff V4

## Closed Status

This immutable handoff supersedes `handoff-v3` after explicit user approval of
all four controlled-spike recommendations. It authorizes bounded phase A
evidence work only. The production design remains `not_implemented`, no
measurement exists, and `route.refresh` remains the only active
traversal-related protocol namespace.

## Preserved Evidence

The completed `canonical-contracts` and `no-network-conformance` packages,
their exact evidence paths and SHA-256 values, and all seven pre-network
resolutions are preserved from `handoff-v3`.

## Authorized Phase A

The controlled-spike package may inspect and hash-pin exact reviewed libjuice
source supplied by the user out of band or already present in the workspace,
perform line-referenced supply-chain and protocol audits, compile the C ABI
adapter for Android minSdk 26 and macOS without sockets, implement
cross-platform transport-neutral session-cryptography fixed vectors, and
implement static harness, resource-ceiling, numeric endpoint, deny-all egress,
packet-assertion, kill-switch, and content-free evidence policy.

This handoff does not authorize `git clone`, `git fetch`, `curl`, `wget`,
package-manager download, or any other network source acquisition. Inspected
dependency code may not execute. Compile-only and static policy work must not
resolve a hostname, use a proxy, create a socket, send a packet, or run the Linux
network-namespace phase.

## Closed Network Boundary

- `controlledSpikeNetworkIOAllowed=false`
- `sourceAcquisitionNetworkIOAllowed=false`
- `controlledSpikeSocketExecutionAuthorized=false`
- `phaseBExecutionAuthorized=false`
- `productionNetworkIOAllowed=false`
- `productionDeploymentAuthorized=false`

There is no candidate exchange, STUN, TURN, ICE connectivity check, consent
traffic, hole punching, direct application traffic, external egress, physical
device execution, or live-network measurement under this handoff.

## Next Decision

The source audit, Android/macOS compile-only integration, session cryptography
vectors, static harness and egress evidence, and an independent phase A security
review must all pass. A separate versioned decision is then required before any
socket creation, controlled network I/O, Linux phase B execution, measurement,
or production deployment.
