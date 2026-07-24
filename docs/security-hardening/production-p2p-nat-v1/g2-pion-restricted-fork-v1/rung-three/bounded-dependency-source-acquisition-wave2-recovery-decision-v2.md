# G2 Pion dependency wave-two v2 recovery decision

Date: 2026-07-24

Status: v2 terminal failure read back; isolated v3 telemetry design selected;
v3 network execution is not authorized by this document.

## Observed terminal state

The v2 permit was consumed exactly once. Four public proxy responses completed:
tuple one's `.mod` and `.zip`, then tuple two's `.mod` and `.zip`. The fourth
response stopped after full ZIP inspection because the v2 wrapper applied its
historical 200:1 compression-ratio rejection. Partial staging was removed and
no accepted artifact set was published. The owner-only v2 claim and bounded
failure receipt remain immutable evidence. v2 must not be retried, resumed,
backfilled, deleted, or reused.

This is not an account, repository-owner, credential, signature, or product
endpoint authentication failure.

## Selected v3 design

v3 uses a fresh claim, staging prefix, final directory, receipt, manifest, and
readback namespace. It starts again from tuple one and performs all 30 ordered
`.mod` then `.zip` requests. No v2 response or partial staging is reused.

The arbitrary 200:1 value is retained only as historical, exact-integer
telemetry. It is not a rejection gate and is not replaced by a larger guessed
ratio. Each accepted ZIP records the first maximum-ratio entry ordinal, its
uncompressed and compressed byte counts, and whether exact integer comparison
exceeds the historical value. No floating-point ratio, entry name, or entry
body is recorded.

All substantive protections remain fail-closed: response and aggregate byte
limits; entry and aggregate-entry limits; central/local header agreement;
encryption, ZIP64, symlink, special-file, path, duplicate, and casefold checks;
full streaming with CRC verification; raw SHA-256; module ZIP H1; `.mod` H1;
optional embedded `go.mod` byte parity; single-file, archive, and aggregate
uncompressed limits; request and whole-wave deadlines; atomic publication; and
post-publication descriptor and named-path barriers.

Independent readback must reopen all 30 retained files without network access,
recompute every structural and identity check, and independently reproduce the
exact compression telemetry. Runner self-checks do not qualify.

## Current authority

This decision authorizes implementation and offline verification of the v3
runner, checker, tests, and preparation of a byte-bound v3 execution permit.
Only that separate permit may authorize one bounded v3 source-intake
execution. It does not authorize package-manager use, source extraction or
execution, compilation, product networking, device work, deployment, or Git
writes.

No repository login, owner proof, private key, signature, token, password,
credential, or user action is required for this personal-project workflow.
Product endpoint authentication remains a separate runtime invariant.
