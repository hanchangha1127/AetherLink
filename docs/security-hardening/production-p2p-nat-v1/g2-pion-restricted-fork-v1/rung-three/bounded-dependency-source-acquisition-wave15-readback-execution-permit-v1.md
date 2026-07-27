# Bounded dependency source acquisition Wave15 readback execution permit v1

This document explains the machine-checked, one-use Wave15 readback permit.
The adjacent JSON file is the canonical authority record. The permit covers
only an offline, independent readback of the already-consumed successful
acquisition attempt `c5db51cfd9a295b448927cca36d1ea07`; it does not authorize
another source acquisition.

## One-use claim

Before opening any frozen acquisition authority, acquisition claim, retained
source, evidence, receipt, or manifest, the recorder must create
`build/offline-source/pion-ice-v4.3.0/dependencies/.wave-15-v1-readback.claim`
with exclusive no-follow creation, mode `0600`, file fsync, and
parent-directory fsync. The claim persists after success, failure, or
uncertainty. Retry, resume, replacement, and backfill are forbidden.

## Exact frozen snapshot

The recorder independently holds an exact 29-file snapshot:

- 15 acquisition-authority files, including the Wave14 one-use claim retained
  as the V13 predecessor namespace anchor;
- the acquisition claim and evidence;
- 10 accepted `.mod` and ZIP resources;
- the acquisition receipt and manifest.

The final and accepted directory inventories are exact. The acquisition
failure record and every portable name beginning `.wave-15-v1-staging-` must
remain absent under NFC-normalized, case-folded comparison.

The project-root descriptor and every root-relative intermediate directory
descriptor remain held through verification and cleanup. Each barrier checks
the held descriptor, its retained parent/name edge, and a fresh no-follow
reopen of the complete current component prefix. Project-root, ancestor,
terminal-name, shape, bytes, mode, owner, link-count, or inventory replacement
therefore fails closed at a barrier. `SIGALRM` and `SIGINT` are deferred only
during narrow local open-to-owner, close-cleanup, and umask state transfers;
validation, reading, writing, and fsync occur outside that deferral.

## Independent verification

The recorder does not import or invoke the acquisition checker or acquisition
runner. It independently reparses strict canonical JSON, rebinds the exact
five tuples and ten ordered resources, recomputes all five `.mod` Hash1 H1
values, and recomputes all five module-ZIP HashZip/Hash1 H1 values. ZIP checks
cover the complete module-version prefix, central/local header and data
descriptor consistency, CRC and deflate boundaries, paths, modes, duplicates,
case-fold collisions, ZIP64 and multidisk rejection, inventory bounds, and
root `go.mod` parity. No source extraction is authorized.

The exact retained totals are:

- 5 `.mod` files and 5 ZIP files;
- 452 `.mod` response bytes;
- 5,064,794 ZIP response bytes;
- 5,065,246 accepted response bytes;
- 1,645 ZIP entries;
- 19,962,377 ZIP-uncompressed bytes.

The aggregate ceilings are 5 MiB for `.mod` responses, 80 MiB for ZIP
responses, and 85 MiB across all accepted responses. Across all ZIPs, no more
than 100,000 entries or 640 MiB of uncompressed bytes are permitted.

All five tuples and all ten resources carry strict
`selectedByGraphAlgorithm: false`. This is a verified graph fact, not
readback, acquisition, product, or release authority. The combined fixed-point
V13 checker and tests are live-held predecessor authority; V12 tests are
historical-only metadata.

Two complete verification passes are required while every input descriptor
remains held. Exactly three publication barriers run in this order:

1. `complete_snapshot_and_claim_immediately_before_receipt`
2. `complete_snapshot_claim_and_receipt_after_receipt`
3. `complete_snapshot_claim_and_receipt_immediately_before_manifest_publication`

The receipt records one completed and two remaining barriers at its
publication point. The manifest records all three as complete. No mandatory
fallible frozen-input, claim, or receipt barrier follows manifest publication.
Consequently, completion applies to the retained snapshot checked at the final
barrier; it is not a claim of continuous current-path identity after that
barrier.

## Atomic terminal publication

Success is published with atomic no-replace semantics as
`bounded-dependency-source-acquisition-wave15-readback-v1.json`, followed by
`bounded-dependency-source-acquisition-wave15-readback-manifest-v1.json`.
Both are mode `0600`, individually fsynced, reopened by final name with
`O_NOFOLLOW`, checked against the temporary inode and exact bytes, and held.
The manifest is published last.

Successful execution is recorded before canonicalization or stdout reporting.
If reporting then fails, the already-complete namespace is classified as
`consumed_success_reporting_failed` with `E_POST_SUCCESS_REPORTING`, phase
`reporting`, retry forbidden, and `readbackPublicationComplete: true`.
A preflight-only reporting failure remains `failed_closed_not_consumed`.

An ordinary verification failure after durable claim creation is
`consumed_failure_no_retry`. Claim-creation, receipt-only, publication, or
cleanup ambiguity is `consumed_terminal_state_uncertain`. Existing claim,
receipt, manifest, or reserved temporary output names cannot be downgraded to
an unconsumed state by a simultaneous cleanup or process-state restoration
failure.

## Authentication and non-authority

No user identity, credential, ownership proof, account, key, signature, token,
or interactive action is required, and the checker and recorder must not
prompt for one. DNS, sockets, network access, proxies, source acquisition,
extraction, loading, execution, compilation, package-manager use, subprocesses,
Git operations, devices, deployment, and product runtime are not authorized.

Successful readback establishes only the integrity and internal consistency of
the retained frozen acquisition snapshot at the final pre-manifest barrier. It
does not establish dependency closure, source-review completion, library
selection, release approval, or V1 completion. The standalone permit checker
is a sequential diagnostic, not an atomic concurrent snapshot; execution
safety depends on the recorder's retained descriptors, two complete passes,
and three pre-manifest publication barriers.
