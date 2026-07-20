# AetherLink V1 G0 Assurance Closure Amendment V2

Recorded: 2026-07-20 KST.

Status: `candidate_not_published_not_authorized`.

This amendment preserves the exact committed V1 assurance and checkpoint bytes
instead of rewriting their versioned identities. The parent assurance raw and
canonical SHA-256 values, the parent checkpoint raw and canonical SHA-256
values, and the locally observed containing commit `929fda5f` are pinned in the
machine record. The local commit, tracking ref, and push reflog are not an
independent remote-byte publication receipt.

## Exact Overlay

The machine record contains eleven ordered JSON Pointer operations over a deep
copy of the exact parent assurance:

1. advance the effective assurance schema, nested closure-contract schema, and
   assurance ID to V2;
2. add one command-profile source binding;
3. classify exactly two executable and seven non-executable G0 checks;
4. add the closed command-profile schema and its two canonical profiles;
5. replace the executable gate-receipt profile;
6. replace the publication profile with a composite publication receipt that
   binds the exact parent assurance, parent checkpoint, amendment, amendment
   checkpoint, effective digest, containing commit, and independent remote
   readback; and
7. narrow the future authority-binding prerequisite from every G0 check to
   every executable G0 check.

The validator rejects any unknown operation, path, order, missing parent key,
pre-existing add target, or array-index operation. It independently deep-copies
the exact parent bytes, applies the exact operations, and recomputes the
effective V2 assurance canonical SHA-256. Neither the amendment nor its
checkpoint mutates the parent V1 files. The validator reads all four
content-addressed JSON inputs as bounded regular non-symlink files and performs
a final no-follow identity and byte-hash readback before it can pass.

## Executable Checks

Only these two checks use command and gate receipts:

- `full_no_device_aggregate` runs
  `bash script/check_no_device_quality.sh`;
- `android_and_macos_release_compilation` runs one ordered composite profile:
  `./gradlew --offline --no-daemon :app:assembleRelease
  -Pkotlin.incremental=false`, then
  `swift build -c release --product AetherLink`.

The other seven G0 checks close from exact publication, catalog evidence, and
accountable owner acceptance. The assurance-packet static validators are
pre-publication verification, not a gate receipt that can replace hash,
readback, publication, or owner evidence.

Both command profiles are `not_authorized`. They pin repository-root execution,
ordered argv, a clean full-environment digest, toolchain and dependency
attestation, allowed and forbidden side effects, required evidence kinds,
complete sanitized logs, and success conditions. Catalog presence grants no
compiler, linker, build-tool IPC socket, loopback socket, ADB, device, external
network, signing, key, upload, deployment, or G1a authority.

All five active Gradle invocations in the aggregate now use `--offline`.
Because the Gradle wrapper can still attempt to bootstrap before project flags
take effect, a future authorized run also requires preseeded hash-attested
wrapper/plugins/dependencies/SDK components and operating-system-level egress
denial. `--offline` alone is not zero-egress proof.

## Receipt Boundary

The V2 gate receipt adds the canonical command-profile SHA-256 and verified
catalog evidence references. A separate non-revoked authority must bind the
exact profile, full environment, resolved working directory, allowed side
effects, source publication commit, validity, and provenance. A trusted runner
must attest the actual ordered execution and exact sanitized-log bytes.

A dormant composite publication candidate validator now inspects only in-memory
bytes from a factory-owned immutable context: the four exact commit blobs, a
separately reviewed repository/commit target, and independent remote checkpoint
bytes with distinct provenance. It performs no Git, worktree, file, or network
lookup from receipt fields and returns only validation failures. The matcher is
private and test-only; even its exact synthetic fixture returns an explicit
`dormant_non_authorizing` failure and cannot store a receipt, change acceptance,
open authority, or activate G0. The canonical checker rejects every explicitly
supplied receipt bundle, including well-shaped input.

No receipt validator is activated by this candidate. The amendment and its
checkpoint have no actual independent remote readback, owner acceptance,
authority, gate result, or publication root. G0 remains `blocked_before_g1a`;
a separate versioned G1a authority is still required even after all G0 blockers
close.
