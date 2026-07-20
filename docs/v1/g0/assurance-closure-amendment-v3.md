# AetherLink V1 G0 Assurance Closure Amendment V3

Recorded: 2026-07-20 KST.

Status: `candidate_not_published_not_authorized`.

This successor preserves every V1 and V2 byte. It reconstructs the exact
effective V2 assurance from the V1 parent plus the ordered V2 overlay, verifies
that assurance and closure digest, deep-copies the result, and then applies the
thirteen exact V3 operations. Any future correction must supersede this
candidate with another version; it must not rewrite the V1, V2, or V3 bytes.

## Exact V3 Contract

The V3 overlay advances the effective assurance and closure schema identities,
then pins the missing complete-receipt-bundle contracts:

- one exact bundle root with no caller-supplied result, status, activation, G0,
  or G1a outcome fields;
- fourteen owner bindings in canonical role order;
- fifteen non-derived evidence records in canonical first-occurrence order;
- two authority bindings, two runner attestations, and two gate receipts in
  executable-check order;
- fourteen accepted owner receipts covering all fifteen role/blocker pairs;
- a six-artifact publication receipt binding the V1 assurance/checkpoint, V2
  amendment/checkpoint, V3 amendment/checkpoint, effective V2/V3 assurance and
  closure digests, containing commit, and independent remote V3 checkpoint
  readback.

`owner_acceptance` and
`quality_measurement_contract_owner_approvals` are validator-derived only.
They cannot appear in the evidence catalog or in approval evidence references.
Each approval instead references the published-checkpoint evidence plus every
non-derived evidence kind relevant to its complete blocker scope. The actual
approval authentication is a separate independent verifier input over all
eight receipt fields, so it cannot refer to itself through the catalog.

## Execution And Trust Boundary

The two immutable command profiles remain unchanged and
`currentAuthorizationState` remains `not_authorized`. A future authority record
must bind the exact source commit, profile and argv digests, working-directory
digest, complete non-secret environment digest, allowed-side-effect digest,
validity interval, issuer, revocation snapshot, and provenance. A separate
trusted runner attestation must bind the same values plus exact ordered step
results, toolchain/dependency/observation manifest hashes, sanitized log hash,
and evidence references.

The bundle never supplies a trust root. A future active validator still needs
independent reviewed repository/commit identity, remote checkpoint bytes,
owner registry and revocation state, authority issuer state, trusted runner
verification, exact evidence/log/manifest bytes, and trusted observation time.
Cross-target replay is rejected by exact bindings. Same-target stateful
activation additionally requires an external consumed-bundle ledger that does
not exist in this candidate.

## Dormant Compiler

`script/check_v1_g0_receipt_bundle.py` has no public API. Its private pure
compiler accepts supplied bytes only, snapshots the six-blob lineage once,
reconstructs that immutable snapshot, and derives the complete graph from
effective V3: ten blockers, nine G0 checks, fourteen roles, fifteen
role/blocker pairs, fifteen non-derived evidence kinds, two derived evidence
kinds, and two executable checks. It cross-checks the ordered checklist and
blocker evidence unions and rejects missing, extra, reordered, duplicated,
dangling, ambiguous, resource-unbounded, cross-target, cross-profile, or
time-inconsistent records. Even an exact synthetic complete fixture returns the mandatory
`dormant_non_authorizing` failure.

It performs no receipt-directed filesystem, Git, remote, clock, registry,
signature, key, or network lookup. It stores nothing, grants no authority, and
cannot change the V1/V2/V3 acceptance records. The canonical V2 decision
checker continues to reject every supplied receipt bundle.

The V3 amendment and checkpoint have no publication receipt, complete bundle,
owner acceptance, gate execution, or independent trust inputs. G0 remains
`blocked_before_g1a`; command execution, compiler/linker use, loopback or build
IPC sockets, external network I/O, ADB/device access, production keys, signing,
upload, deployment, and G1a remain closed.
