# Production P2P/NAT Bounded Handoff V5

## Closed Status

`handoff-v5` supersedes `handoff-v4` and hash-pins controlled-spike `decision-v2`. The selected profile remains `production_p2p_nat_v1_recommended`, production design remains `not_implemented`, measurement remains `not_started`, and `route.refresh` remains the only active traversal-related protocol namespace.

## Preserved Evidence

The canonical-contract and no-network-conformance packages, all seven pre-network decisions, and all four controlled-spike recommendation approvals are copied unchanged from `handoff-v4`. Their prior evidence hashes remain authoritative.

## Authorized Acquisition

Only the exact official libjuice `v1.7.2` GitHub archive and Android NDK r28c package `ndk;28.2.13676358` may be acquired. The decision fixes the three allowed hosts, exact URLs, archive paths, byte ceilings, AGP evidence, and install path. HTTPS is mandatory; redirects, environment proxies, package-manager fallback, mirrors, alternate versions, clone history, and unbounded discovery are prohibited.

Acquisition traffic is separate from controlled-spike traffic. `sourceAcquisitionNetworkIOAllowed=true` and `androidNdkPackageAcquisitionNetworkIOAllowed=true` apply only to those exact artifacts.

## Pre-Compile Boundary

Extraction, hashing, source and license inspection, dependency and generated-file review, tool inspection, and manifest generation are allowed. `compilerInvocationAuthorized=false` and `archiveInvocationAuthorized=false` until completed versioned intake, exact source and tool manifests, independent review, and a new compile-only contract are closed.

## Closed Network Boundary

Source execution, configure/CMake execution, executable linking, tests, sockets, runtime or harness networking, ICE/STUN/TURN, Phase B, production networking, and deployment remain prohibited. `controlledSpikeNetworkIOAllowed=false`, `controlledSpikeSocketExecutionAuthorized=false`, `phaseBExecutionAuthorized=false`, `productionNetworkIOAllowed=false`, and `productionDeploymentAuthorized=false`.

## Next Decision

After exact acquisition, a new versioned intake and tool/source manifest must be independently reviewed. Only a later compile-only contract may authorize direct `-c`, static archive creation, and `nm` inspection. Socket execution still requires complete Phase A evidence and a separate explicit versioned decision.
