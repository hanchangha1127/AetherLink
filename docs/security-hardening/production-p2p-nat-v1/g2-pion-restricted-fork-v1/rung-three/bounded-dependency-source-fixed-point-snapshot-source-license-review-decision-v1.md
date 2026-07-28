# G2 Pion fixed-point snapshot source/license review decision v1

## Decision

The exact Combined V18 fixed-point snapshot is ready for two independent,
local, read-only GPT-5.6 Sol review passes. The review passes have not yet been
performed, and this decision does not claim dependency-source, license,
security, semantic, rung-three, candidate-selection, library-selection, or
release closure.

This is a personal-project workflow. It requires no owner authentication,
signature, key, token, password, approval, or user action.

## Exact predecessor

- Decision:
  `g2-pion-ice-v4.3.0-rung3-combined-v18-fixed-point-closure-review-decision-v1`
- Raw SHA-256:
  `affc2b60fd76b07a6e5af94a9492c5b0954d743ed26160e08fab970fbbbd42bd`
- Content SHA-256:
  `9d58b2d1411df8d3a33ae31d5b1868528bdc1b2949574a9d21e48c380666659b`
- Accepted V18 graph SHA-256:
  `a865a62a7a80a0dece55aeebd537d3fb9aa73ce6ceeea10304a6a2074c2dfaba`
- Exact frontier SHA-256:
  `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`

Only `dependencyFixedPointReached` is true. All 19 canonical findings remain
open: 7 `patch_required` and 12 `unresolved`.

## Bound snapshot

The adapter binds the following exact retained snapshot:

- 369 source inputs
- 184 module/version tuples
- 185 ZIP archives
- 72,304 archive entries
- 356,092,640 raw input bytes
- 1,359,347,284 uncompressed archive bytes
- review-binding-set SHA-256:
  `3423f30722a5d9be67774be1b3dc7f25544ddd9b452c914e891085f0e3e24d23`
- V18 source-binding SHA-256:
  `622a644a86e6ffe4596a3186034fbf141d964f34b5f3044f1b175db716d099f7`
- exact-input-inventory SHA-256:
  `a349cd67bd0f3355146b7008c5fcf595f79801bc1d7f8ab6d85f69178e565cda`

The exact profiles are Android API 26 through 36 on `arm64-v8a` and macOS 14
or newer on arm64, both using the Go 1.24 `gc`/cgo profile model.

## Adapter validation observed

The zero-write adapter preflight, its 14 tests, and its full scan passed.
The successful full scan reproduced:

- 185 exact module-coverage rows
- 58,478 Go source files
- 195 candidates under the pinned runner's narrower historical license rule
- 362 candidates under the broader fixed-snapshot filename rule
- 11,150 pinned-runner special-source rows
- 185 module-metadata rows
- 132 package-graph nodes and 1,047 package-graph edges
- 185 module nodes and 471 module edges
- 33 selected versions
- exact V18 graph SHA-256:
  `a865a62a7a80a0dece55aeebd537d3fb9aa73ce6ceeea10304a6a2074c2dfaba`

The adapter also bound two occurrences of one exact non-production legacy
build-constraint source and 30 occurrences of two exact intentionally
malformed `golang.org/x/tools` testdata files. Those compatibility cases are
accepted only by exact source hash, exact non-production classification, and
exact occurrence count.

The scan decoded archive members in memory. It did not extract archives,
execute or compile retained source, start subprocesses, use the network, write
files, or alter Git state. Its stdout projection was not persisted as a review
result artifact.

## Authorized local work

This decision authorizes only stable local reads, bounded in-memory archive
member decoding, static source inspection, exact build-profile
classification, stdout-only projections, and two independent GPT-5.6 Sol
review passes over the same immutable byte bindings.

Neither pass may see the other pass's output before both complete. The passes
do not attest authority. Any disagreement, unknown license, missing body,
ambiguous reachability, graph drift, generated/native/cgo/assembly ambiguity,
or security blocker remains unresolved.

Reading retained source bytes is not permission to load the retained source as
executable code. Loading the pinned Python inspection tool is not execution of
the retained Go, C-family, assembly, generator, test, hook, or build-script
content.

## Explicitly not authorized

No file write, publication, manifest write, claim write, readback write,
filesystem extraction, source materialization, source modification, retained
source loading or execution, generator/test/hook/build-script execution,
package-manager or Go command, compilation, shell or subprocess, DNS, socket,
network, device, deployment, or Git write is authorized.

No external authentication, repository-owner proof, signature, private key,
token, password, approval, or user action is required.

## Output boundary

The adapter defines only three canonical, ASCII-escaped, sorted-key, compact
JSON stdout document types with exactly one trailing LF:

- `aetherlink.g2-pion-fixed-point-snapshot-source-license-review-preflight`
- `aetherlink.g2-pion-fixed-point-snapshot-source-license-review-input`
- `aetherlink.g2-pion-fixed-point-snapshot-source-license-review-error`

The review-input projection is not an SPDX SBOM, a license-compatibility
decision, or a security acceptance. Persistent pass records, reconciliation,
source/provenance/profile manifest, license inventory, SPDX 2.3 SBOM, and
result-or-failure artifacts are future planned outputs only and require a
separate write/publication decision.

## Current state and next action

Independent review passes completed: `0 / 2`.

Next action:
`perform_two_independent_gpt_5_6_sol_fixed_point_snapshot_source_license_security_review_passes`.
