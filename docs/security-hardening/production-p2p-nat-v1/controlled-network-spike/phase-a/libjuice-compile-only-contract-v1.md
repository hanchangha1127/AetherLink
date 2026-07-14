# Phase A libjuice Compile-Only C ABI Contract v1

## Current Status

- Integration: `blocked_missing_reviewed_source`
- Execution: `not_executed`
- Evidence: `absent`
- Scope: immutable contract evidence only

The JSON records a dated `2026-07-13` creation-time filesystem snapshot: no libjuice source, header, native build integration, Android NDK, or Android CMake installation was observed, while Apple clang was observed but not invoked. The static contract checker does not revalidate that environment snapshot. Regardless of later environment drift, reviewed source remains absent, this artifact contains no compilation evidence, and it authorizes no current compiler or archive invocation. The canonical blocked state is a successful checker result; it is not a compile success.

No `juice.h`, adapter header or source, CMake file, Gradle native wiring, SwiftPM wiring, executable, native test, or smoke harness is created by this contract. Nothing in this artifact proves ICE, STUN, TURN, consent, socket, network, Android-device, or macOS runtime behavior.

## Approval Chain

- `../review-v1.json`: `production_p2p_nat_v1_controlled_network_spike_review_v1`, SHA-256 `744099ec8b0fdd8edf214283661332b0b5deffed7c79211556b98d9ddf544c62`
- `../decision-v1.json`: `production_p2p_nat_v1_controlled_network_spike_decision_v1`, SHA-256 `1fd24be7252e25381552d1732c5282f141ef0e9b02118f8c65b246b81a055228`
- `../../implementation/handoff-v4.json`: `production_p2p_nat_v1_handoff_v4`, SHA-256 `b4ecfb30491320383e7ac19cd96fdd7601b91b897bb0fa2019eba187d30509dd`

The decision and handoff authorize bounded Phase A compile-only integration, but do not authorize source acquisition network I/O, source execution, sockets, controlled-spike network execution, Phase B, production network I/O, or deployment.

## Offline Source Intake

The input `offline-source-intake-v1.json` is linked at SHA-256 `3359624f1fa1474b2bfd2acd4e3591fd1e0a8cd5840cda4372327f25dfc68850`. That artifact is itself canonical `blocked_missing_offline_source`: source is `absent`, audit is `not_started`, and compile is `not_started`. This hash pins only that blocked record and does not establish reviewed source availability.

When a completed reviewed intake exists, a new versioned compile-only contract must pin its exact SHA-256. The completed intake must lead to an independently reviewed exact source manifest before compilation. This v1 record must not be edited in place to claim that transition, and this contract does not modify the intake artifact owned by the parallel task.

## Reviewed Source Manifest Gate

Compilation remains blocked until a reviewed manifest fixes the exact upstream repository identity, release tag, commit SHA, archive and source-tree SHA-256 values, license files and hashes, ordered source and header lists with per-file hashes, generated files, complete transitive dependency closure, build defines, include directories, compiler flags, symbol exports, and platform toolchain pins.

Source discovery is only the ordered manifest list. Globs, directory scans, implicit source inclusion, implicit defines, fallback downloads, and silent fallback-library selection are prohibited. Any missing pin leaves the state `blocked_missing_reviewed_source`.

## Future Compile-Only Procedure

After the intake and reviewed manifest are hash-pinned in a new contract, each exact source is compiled once with a direct compiler `-c` invocation in manifest order. The exact ordered objects are then placed in one static archive, and `nm` inspects that archive without loading or executing code.

Configure steps, CMake execution, Gradle native build wiring, SwiftPM wiring, executable linking, ctest, native tests, smoke execution, source execution, sockets, network I/O, DNS, URLs, redirects, and every proxy path remain prohibited. Failure closes the step without configure, link, execution, download, or fallback.

## Required Platform Matrix

Android proof requires minSdk `26` for both `arm64-v8a` (`aarch64-linux-android26`) and `x86_64` (`x86_64-linux-android26`). The future manifest must exactly pin the NDK version and package digest, clang, llvm-ar, llvm-nm, sysroot, ordered sources and objects, defines, include directories, and flags.

macOS proof requires deployment target `14.0` for both `arm64` and `x86_64`. The future manifest must exactly pin Apple clang, archive and nm tools, SDK version/path/digest, ordered sources and objects, defines, include directories, and flags. All four targets must expose one identical versioned C ABI and export allowlist.

## C ABI Boundary

The public ABI uses C11, incomplete-struct pointer handles, fixed-width integers, and pointer-plus-explicit-`size_t`-length buffers. Endpoint input is numeric only: address family, packed address bytes, and a `uint16_t` port. Hostnames, URLs, and `routeToken` cannot cross or configure the boundary.

Every creator-owned handle has an explicit destroy operation. Every buffer has exactly one documented allocator and release owner. Callback execution has one documented thread, cannot reenter destroy, and cannot transfer ownership implicitly. Cancellation is idempotent and nonblocking; teardown is bounded, unregisters callbacks, releases owned memory, and permits no callback after destroy returns. Errors are bounded `int32_t` numeric codes from `0` through `255`, with unknown mapped to `255`.

Visibility is hidden by default. Only the ten symbols listed in the JSON contract may be exported. The adapter has no authority over `routeToken` and may not accept, interpret, authorize, encrypt, decrypt, or emit application payload.

## Evidence Boundary

Allowed artifacts are object files, static archives, `nm` symbol reports, and content-free command/tool/source digest records. The digest record has an exact bounded key set and retains no raw command line, environment, source content, application content, or packet content.

Executables, shared libraries, test artifacts, runtime logs, ctest/native-test results, and smoke evidence are forbidden. This v1 record has an empty compilation-evidence list.

## Checker Boundary

The checker rejects duplicate JSON keys, unknown or missing keys, value drift, and recursive type confusion such as `false == 0`, `1 == true`, or `26 == 26.0`. It pins the approval-chain hashes and the exact JSON and Markdown bytes.

The checker parses its own source and mutation tests with Python AST only. It rejects capability-bearing imports and references including process launch, sockets, HTTP, URLs, dynamic import, native loading, `eval`, `exec`, `compile`, `os.system`, and equivalent indirection. It does not execute parsed source and does not compile libjuice.
