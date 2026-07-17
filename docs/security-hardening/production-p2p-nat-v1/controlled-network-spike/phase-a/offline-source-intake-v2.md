# Phase A libjuice Offline Source Intake v2

## Closed Intake

The exact approved libjuice v1.7.2 and Android NDK acquisitions are complete. This record supersedes the immutable blocked `offline-source-intake-v1` state without modifying it.

The retained libjuice archive is 108,235 bytes with SHA-256 `75159867c4a5a689a6559e11aa0d30c9eba12ce73a4ae3d898b521467e1f635d`. Its 81 regular files exactly match the extracted source records, totaling 550,494 bytes with canonical tree/file-set SHA-256 `c17e0d6d3855e9584718584ab644f030939448d0e8f6a8bf5ca9883da719a330`. No symlink, hardlink, special file, or traversal entry was accepted.

The official tag metadata recorded annotated tag object `0f823d8210ea9dfe62a1c248da2b3219f6d8568d` and commit `3c40a3545b6b1b62c7adee7f8f2bd58aa290afd6`. The record does not claim a separate cryptographic archive-to-commit binding beyond the exact official tag URL, observed metadata, retained archive digest, and byte-equivalent extracted tree.

## Reviews

`libjuice-source-manifest-v1.json` contains all 81 path, size, and SHA-256 records plus license, generated-file, dependency, build-input, Android NDK, and Apple tool receipts. The local `source-provenance.json` is byte-identical to that committed manifest.

`libjuice-source-audit-v1.json` closes the source audit as rejected before compile. It records five independent P1 blockers: target-platform predictable entropy, default-level ICE password logging, unauthenticated Binding error handling, unauthenticated TURN redirect handling, and inability to enforce numeric-only per-tuple authorization before DNS and socket boundaries.

The Android NDK `ndk;28.2.13676358` (`r28c`) archive is retained at SHA-256 `0d4599e8bbf1a1668a0d51a541729b2246360f350018a2081d0b302dbb594f2a` and installed side by side. It was inspected and hashed but never used to compile libjuice. Apple compiler and SDK metadata were likewise inspected but not invoked for compilation.

## Failure Transition

The exact acquisition authority is consumed and closed. The existing failure policy requires rejection of libjuice and a new versioned `libnice-0.1.23-glib-c-abi` fallback review. The fallback is not selected, no libnice source is acquired, and no new compile contract is created.

No source was executed, compiled, linked, loaded, archived into a static library, or inspected with `nm`. No socket or runtime network action occurred. Phase B, production networking, and deployment remain prohibited. This intake proves exact acquisition and a completed rejecting audit, not compilation, ABI compatibility, runtime ICE/STUN/TURN behavior, NAT traversal, physical Android behavior, or production readiness.
