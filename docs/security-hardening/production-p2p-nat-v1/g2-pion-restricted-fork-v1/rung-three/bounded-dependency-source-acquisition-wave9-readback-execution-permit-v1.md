# Bounded dependency source acquisition Wave9 readback execution permit v1

This permit authorizes exactly one offline, independent readback of the
already-consumed successful Wave9 v1 source acquisition. It does not authorize
another acquisition attempt. The frozen acquisition attempt is
`df64a4816a083806020580efe953b9a7`.

The readback recorder must first create
`build/offline-source/pion-ice-v4.3.0/dependencies/.wave-9-v1-readback.claim`
with exclusive no-follow creation, mode `0600`, file fsync, and parent-directory
fsync. It may open no frozen acquisition authority, claim, source, evidence,
receipt, or manifest before that durability barrier. The claim remains after
success, failure, or uncertainty. Retry, resume, replacement, and backfill are
forbidden.

After the claim is durable, the recorder independently opens and holds the
exact 14-file acquisition authority, acquisition claim, final and accepted
directories, evidence, 20 accepted files, acquisition receipt, and acquisition
manifest. This is an exact 38-file frozen snapshot. Exact path, raw SHA-256,
byte count, mode, owner UID, link count, and directory inventory are required.
The acquisition failure record must remain lexically absent. Every Wave9 v1
staging name is checked after NFC normalization and case folding.

The project root directory descriptor is retained for the complete attempt.
At every retained-FD barrier the recorder reopens the original absolute project
root with `O_NOFOLLOW` and requires the same device and inode. From that
retained root it re-resolves every held file and directory component with
`O_NOFOLLOW`, then requires the current name to resolve to the held device and
inode with the same shape, bytes, mode, owner, link count, and inventory.
Ancestor or project-root namespace replacement observed at a barrier therefore
fails closed. Every root-relative intermediate directory descriptor opened
for the retained snapshot remains owned through verification and cleanup.
`SIGALRM` and `SIGINT` are deferred only across the small local
open-to-owner, close-cleanup, or process-umask state transfer; validation,
reading, writing, and fsync do not run under that deferral. An exclusive
creation is recorded before owner-list registration, and a primary open result
is not hidden by a later signal-mask restoration error. Cleanup independently
attempts every owned descriptor before restoring the caller's prior signal
mask, retries an observably failed close once, and retains ownership when an FD
is still observably open. Object cleanup therefore remains retryable instead of
discarding a live descriptor. The
durable readback claim is created with an `O_RDWR` descriptor that remains
open; the current claim name is reopened and required to match that original
creation inode before any frozen input is opened. The original claim
descriptor remains open until recorder cleanup, but current-path identity is
only guaranteed at the explicit pre-manifest barriers.

The recorder does not import or call the acquisition checker or acquisition
runner. It independently re-parses strict canonical JSON and all terminal
bindings, recomputes the exact 20-resource order and aggregate byte counters,
recomputes every `.mod` Hash1 H1, and recomputes every module ZIP HashZip/Hash1
H1. ZIP validation independently checks the complete module-version prefix,
central/local header parity, data descriptors, CRC and deflate boundaries,
entry paths, modes, duplicates and case-fold collisions, file/entry/aggregate
limits, ZIP64 and multidisk rejection, and root `go.mod` parity.
The fixed totals are 10 mod files, 10 ZIP files, 1,181 mod-response bytes,
16,284,759 ZIP-response bytes, 16,285,940 accepted response bytes,
5,349 ZIP entries, and 54,936,288 ZIP-uncompressed bytes. The per-ZIP
uncompressed limit remains 128 MiB while the across-all-ZIP limit is 1 GiB;
the response-byte aggregate and uncompressed-byte aggregate are never
interchanged. Resources `003` and `004` intentionally have identical `.mod`
bytes and raw SHA-256 values; their identity remains bound by request ordinal,
accepted path, tuple, and version rather than global digest uniqueness. All
10 tuples retain
`selectedByGraphAlgorithm: false`; the decision, permit, request-set, compact-identity,
full-witness, held-source-binding, exact request-resource, and combined
fixed-point V7 predecessor digests are also recomputed or exactly bound. The
14-file authority uses the exact V7 checker and test bindings referenced by
the Wave9 acquisition permit instead of an unrelated candidate pair.

Two complete verification passes are required while all input file descriptors
remain held. Exactly three mandatory publication barriers run in this order:
`complete_snapshot_and_claim_immediately_before_receipt`,
`complete_snapshot_claim_and_receipt_after_receipt`, and
`complete_snapshot_claim_and_receipt_immediately_before_manifest_publication`.
The third barrier is the final frozen snapshot, claim, and receipt current-path
identity check and runs immediately before atomic manifest publication. The
receipt records one completed
barrier and two remaining barriers at its publication point; the manifest
records all three as completed before its publication. No mandatory fallible
frozen-input, claim, or receipt barrier follows manifest publication.
Consequently, a same-UID concurrent rename or replacement after the last
barrier is not prevented. Completion applies to the retained snapshot verified
at that barrier, not to continuous current-path identity through publication.

Success is published with atomic no-replace semantics as
`bounded-dependency-source-acquisition-wave9-readback-v1.json`, followed by
`bounded-dependency-source-acquisition-wave9-readback-manifest-v1.json`; both
are mode `0600`, individually fsynced, and the manifest is last.
Each output is reopened by its final name with `O_NOFOLLOW`, checked against
the still-open temporary inode and exact bytes and shape, and held. The receipt
FD is present at the final pre-manifest barrier; this does not claim continuous
receipt current-path identity afterward. The manifest publish operation
performs rename, parent-directory fsync, and then final-name reopen and source
inode verification before returning.

Preflight and every publication barrier compare names after NFC normalization
and case folding, and reject any portable name beginning
`.bounded-dependency-source-acquisition-wave9-readback-v1.json.tmp-` or
`.bounded-dependency-source-acquisition-wave9-readback-manifest-v1.json.tmp-`.
The acquisition staging prefix uses the same portable-name comparison.
Claim-only, receipt-only, complete, inconsistent, and stale-temporary
namespaces are distinct consumed-state observations; receipt-only and
inconsistent publication states remain terminal uncertainty.
Once an existing claim, receipt, manifest, or reserved temporary output is
observed, a simultaneous cleanup or process-state restoration failure cannot
downgrade that consumed or uncertain classification to a not-consumed result.

An ordinary verification failure publishes neither success output. Every
failure after a durable readback claim is consumed and never retryable, but a
known claim-only verification failure is reported as a consumed failure rather
than overstated as terminal uncertainty. Claim-creation ambiguity,
receipt-only state, publication ambiguity, or cleanup ambiguity after
publication is terminal uncertainty.
Receipt-only and terminal publication gaps are explicitly reported as
uncertainty rather than as ordinary failure.

This readback is offline. No account, repository-owner proof, password, private
key, signature, token, credential, or user action is required. DNS, sockets,
network access, proxies, source acquisition, extraction, loading, execution,
compilation, package-manager use, subprocesses, Git, devices, deployment, and
product runtime are not authorized. Successful readback establishes only the
integrity and internal consistency of the retained frozen acquisition snapshot
at the final pre-manifest barrier; it does
not establish dependency closure, source review, library selection, release
approval, or V1 completion.

The standalone live permit checker is a sequential diagnostic and is not an
atomic concurrent snapshot. The execution safety claim instead depends on the
recorder's retained descriptors, current-path identity checks, two complete
passes, and pre-manifest publication barriers.
