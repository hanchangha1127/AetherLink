# Phase A libjuice Source Audit v1

## Outcome

`libjuice-1.7.2-static-c-abi` is rejected before compilation. The audit used the exact official-tag archive and 81-file extracted tree pinned by `libjuice-source-manifest-v1.json`. It did not compile, link, load, or execute source and did not create sockets or perform runtime network I/O.

The result activates the existing failure policy: reject libjuice and open a new versioned review for `libnice-0.1.23-glib-c-abi`. The fallback is not selected, its source has not been acquired, and no fallback compilation or implementation is authorized.

## Independent Rejection Blockers

- Android and macOS both fall back to realtime-seeded `random()` for ICE credentials, tie-breakers, and STUN/TURN transaction IDs (`src/random.c:17-101`, `src/ice.c:165-168`, `src/agent.c:143-151`).
- A failed integrity check writes the active ICE password at the default `WARN` level (`src/log.c:34-36`, `src/agent.c:1302-1310`).
- Binding error responses can bypass integrity and then change role or fail a pair (`src/agent.c:1265-1271`, `src/agent.c:1605-1652`).
- Non-400 TURN errors bypass integrity; an unauthenticated 300 response can replace the destination and trigger a send to that tuple (`src/agent.c:1319-1325`, `src/agent.c:1907-1945`, `src/agent.c:2006-2008`). Redirects are prohibited by the selected profile.
- The public API accepts string endpoints, internal resolution uses `getaddrinfo` without `AI_NUMERICHOST`, and there is no per-tuple authorization hook before the library socket boundary (`include/juice/juice.h:80-119`, `src/addr.c:253-266`, `src/agent.c:219-247`).

These issues require a reviewed source/API fork. A C ABI wrapper alone cannot repair the internal entropy, authentication, redirect, and pre-I/O policy paths. No source fork is authorized by the current decision chain.

## Required Protocol Topics

Regular nomination and RFC 7675 timing mechanisms are present. A successful pair is selected, then a distinct `USE-CANDIDATE` check is scheduled, and consent uses a 4-to-6-second interval with 30-second expiry. These mechanisms do not rescue the candidate: application data can be admitted before nomination, the consent scheduler uses the rejected random source, and consent can be disabled at compile time.

Role handling fails because the controlled-role conflict branch compares `ice_controlling` instead of `ice_controlled` (`src/agent.c:1474-1484`). TURN authentication and destination handling fail the profile because unverified error attributes can update nonce or redirect state. Parser memory bounds exist, but several fixed-format attributes accept noncanonical lengths. Cancellation and callback teardown lack the bounded, nonreentrant contract required by the proposed ABI.

## Supply Chain And Tool Receipt

- libjuice annotated tag object: `0f823d8210ea9dfe62a1c248da2b3219f6d8568d`.
- libjuice commit: `3c40a3545b6b1b62c7adee7f8f2bd58aa290afd6`.
- archive SHA-256: `75159867c4a5a689a6559e11aa0d30c9eba12ce73a4ae3d898b521467e1f635d`.
- extracted tree/file-set SHA-256: `c17e0d6d3855e9584718584ab644f030939448d0e8f6a8bf5ca9883da719a330`.
- Android NDK package: `ndk;28.2.13676358` (`r28c`), retained archive SHA-256 `0d4599e8bbf1a1668a0d51a541729b2246360f350018a2081d0b302dbb594f2a`.

The project license is MPL-2.0. The manifest separately records the public-domain `picohash.h`, BSD-style `FindNettle.cmake`, and excluded LGPL-noticed fuzzer. No generated C/header input was accepted. Nettle, ambient `/usr/local/include`, CMake, Make, configure, and package-manager fallback are outside the closed dependency and build plan.

## Closed Boundary

No compiler or static-archive invocation occurred. No compile-only contract v2 is created because the source audit failed first. Socket execution, runtime or harness networking, Phase B, libnice acquisition, production networking, and deployment remain prohibited. This is source and supply-chain rejection evidence, not Android/macOS compile proof, ABI proof, runtime ICE/STUN/TURN evidence, NAT traversal, physical-device evidence, or production readiness.
