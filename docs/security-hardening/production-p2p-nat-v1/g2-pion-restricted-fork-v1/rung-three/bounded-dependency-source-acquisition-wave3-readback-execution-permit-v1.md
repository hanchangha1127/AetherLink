# Bounded dependency source acquisition Wave3 readback execution permit v1

This permit authorizes exactly one offline, independent readback of the
already-consumed successful Wave3 v1 source acquisition. It does not authorize
another acquisition attempt. The frozen acquisition attempt is
`47d76c38d865e40c7f16961c6fe8b31a`.

The readback recorder must first create
`build/offline-source/pion-ice-v4.3.0/dependencies/.wave-3-v1-readback.claim`
with exclusive no-follow creation, mode `0600`, file fsync, and parent-directory
fsync. It may open no frozen acquisition authority, claim, source, evidence,
receipt, or manifest before that durability barrier. The claim remains after
success, failure, or uncertainty. Retry, resume, replacement, and backfill are
forbidden.

After the claim is durable, the recorder independently opens and holds the
exact eight-file acquisition authority, acquisition claim, final and accepted
directories, evidence, 32 accepted files, acquisition receipt, and acquisition
manifest. Exact path, raw SHA-256, byte count, mode, owner UID, link count, and
directory inventory are required. The acquisition failure record and every
Wave3 v1 staging name must remain lexically absent.

The project root directory descriptor is retained for the complete attempt.
At every retained-FD barrier the recorder reopens the original absolute project
root with `O_NOFOLLOW` and requires the same device and inode. From that
retained root it re-resolves every held file and directory component with
`O_NOFOLLOW`, then requires the current name to resolve to the held device and
inode with the same shape, bytes, mode, owner, link count, and inventory.
Ancestor or project-root namespace replacement therefore fails closed. The
durable readback claim is created with an `O_RDWR` descriptor that remains
open; the current claim name is reopened and required to match that original
creation inode before any frozen input is opened. The original claim
descriptor remains held through manifest publication.

The recorder does not import or call the acquisition checker or acquisition
runner. It independently re-parses strict canonical JSON and all terminal
bindings, recomputes the exact 32-resource order and aggregate byte counters,
recomputes every `.mod` Hash1 H1, and recomputes every module ZIP HashZip/Hash1
H1. ZIP validation independently checks the complete module-version prefix,
central/local header parity, data descriptors, CRC and deflate boundaries,
entry paths, modes, duplicates and case-fold collisions, file/entry/aggregate
limits, ZIP64 and multidisk rejection, and root `go.mod` parity.

Two complete verification passes are required while all input file descriptors
remain held. Exactly three mandatory publication barriers run in this order:
`complete_snapshot_and_claim_immediately_before_receipt`,
`complete_snapshot_claim_and_receipt_after_receipt`, and
`complete_snapshot_claim_and_receipt_immediately_before_manifest`. All three
finish before manifest publication begins. The receipt records one completed
barrier and two remaining barriers at its publication point; the manifest
records all three as completed before its publication. No mandatory fallible
frozen-input, claim, or receipt barrier follows manifest publication.

Success is published with atomic no-replace semantics as
`bounded-dependency-source-acquisition-wave3-readback-v1.json`, followed by
`bounded-dependency-source-acquisition-wave3-readback-manifest-v1.json`; both
are mode `0600`, individually fsynced, and the manifest is last.
Each output is reopened by its final name with `O_NOFOLLOW`, checked against
the still-open temporary inode and exact bytes and shape, and held. The receipt
remains held through manifest publication. The manifest publish operation
performs rename, parent-directory fsync, and then final-name reopen and source
inode verification before returning.

Preflight and every publication barrier reject any lexical name beginning
`.bounded-dependency-source-acquisition-wave3-readback-v1.json.tmp-` or
`.bounded-dependency-source-acquisition-wave3-readback-manifest-v1.json.tmp-`.
Claim-only, receipt-only, complete, inconsistent, and stale-temporary
namespaces are distinct consumed-state observations; receipt-only and
inconsistent publication states remain terminal uncertainty.

An ordinary verification failure publishes neither success output. A failure
after the readback claim, a claim durability ambiguity, a receipt-only state,
or a publication durability ambiguity is consumed and never retryable.
Receipt-only and terminal publication gaps are explicitly reported as
uncertainty rather than as ordinary failure.

This readback is offline. DNS, sockets, network access, proxies,
authentication, credentials, private keys, source acquisition, extraction,
loading, execution, compilation, package-manager use, subprocesses, Git,
devices, deployment, and product runtime are not authorized. Successful
readback establishes only the integrity and internal consistency of the frozen
acquisition result; it does not establish dependency closure, source review,
library selection, release approval, or V1 completion.

The standalone live permit checker is a sequential diagnostic and is not an
atomic concurrent snapshot. The execution safety claim instead depends on the
recorder's retained descriptors, current-path identity checks, two complete
passes, and pre-manifest publication barriers.
