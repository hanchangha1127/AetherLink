# Production P2P/NAT Controlled-Spike Acquisition Decision V2

## Closed Decision

An explicit user instruction on 2026-07-17 authorizes only the official artifact acquisition needed to finish bounded Phase A compile-only evidence. This record supersedes `decision-v1` without rewriting it and retains all four prior Phase A recommendation approvals unchanged.

## Exact Acquisition

- libjuice is fixed to release tag `v1.7.2`, repository metadata at `https://github.com/paullouisageneau/libjuice.git`, and the exact GitHub codeload archive URL recorded in the JSON decision.
- Android NDK is fixed to `r28c`, package `ndk;28.2.13676358`, because that is the embedded default of this repository's AGP 9.2.1 artifact. The AGP JAR and its SHA-256 are pinned in the JSON decision, together with the exact official `dl.google.com` Darwin archive URL.
- The three allowed hosts are `github.com`, `codeload.github.com`, and `dl.google.com`. HTTPS is mandatory. Redirect following, environment proxies, package-manager acquisition, alternate mirrors, fallback versions, and unbounded discovery are prohibited.
- Acquired archives remain under `build/` and are hash-pinned before extraction or use.

## Pre-Compile Gate

Acquisition, bounded extraction, hashing, license review, dependency review, generated-file review, tool inspection, and reviewed manifest generation are authorized. Compiler and archive invocation remain false until a completed versioned source intake, exact source/tool manifests, independent review, and a new versioned compile-only contract are closed.

## Closed Execution Gates

`sourceExecutionAllowed=false`, `configureExecutionAllowed=false`, `testExecutionAllowed=false`, `socketCreationAllowed=false`, `runtimeNetworkIOAllowed=false`, `harnessNetworkIOAllowed=false`, `controlledSpikeNetworkIOAllowed=false`, `controlledSpikeSocketExecutionAuthorized=false`, `phaseBExecutionAuthorized=false`, `productionNetworkIOAllowed=false`, and `productionDeploymentAuthorized=false`.

The acquisition authorization is separate from controlled-spike traffic and is not ICE/STUN/TURN, harness, socket, runtime, Phase B, or production network authority.

## Next Gate

`handoff-v5` must hash-pin this decision before acquisition. Compilation requires a later reviewed versioned contract with exact sources, flags, tools, SDKs, object order, archive order, and export checks. Any mismatch fails closed without fallback download, execution, socket authority, or Phase B escalation.
