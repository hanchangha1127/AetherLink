# Bounded dependency source acquisition Wave3 execution permit v1

This permit authorizes exactly one authentication-free acquisition attempt for
the 16-tuple, 32-resource Wave3 request sequence. For each tuple, the runner
must issue one direct HTTPS GET for `.mod`, then one for `.zip`, against the
exact canonical path on `proxy.golang.org`.

Before any DNS or network operation, the runner must create the exclusive
owner-only claim at
`build/offline-source/pion-ice-v4.3.0/dependencies/.wave-3-v1.claim` and fsync
both file and parent. The claim persists after success, failure, timeout, or
uncertainty. Retry, resume, backfill, redirects, ambient proxies,
authentication, cookies, client certificates, ranges, alternate hosts, and
extra requests are forbidden.

An existing claim is `already_consumed`. Any error after the exclusive claim
file is created but before its file-and-parent durability barrier is
`consumed_terminal_state_uncertain`; no request or failure backfill follows.
Likewise, failure-record write or parent-fsync uncertainty and any error after
final publication begins are explicit consumed terminal uncertainty, never an
ordinary recorded failure and never retryable.

All reserved paths require lexical absence, so even a broken symbolic link
occupies and blocks a name. The runner restores any pre-existing process
`ITIMER_REAL` handler and timer with elapsed-time adjustment after its bounded
attempt.

The runner independently verifies the virtual `go.mod` dirhash H1 and module
ZIP HashZip/Hash1 H1 in Python. ZIP entries must have the exact canonical
module-version prefix and pass bounded path, type, size, duplicate, encryption,
and compression checks. The validator rejects ZIP64, multidisk archives,
comments, leading or trailing bytes, directories, symlinks and special files,
NFC/case-fold/path collisions, local/central header drift, overlapping spans,
CRC drift, hidden deflate data, and malformed data descriptors. ZIP contents
may be read only for hashing; they may not be extracted, loaded, executed, or
compiled.

The fixed absolute ceilings are 1 MiB per `.mod`, 16 MiB per `.zip`, 8 MiB
across `.mod` bodies, 128 MiB across `.zip` bodies and across all response
bodies, 20,000 ZIP files, 128 MiB uncompressed per ZIP and per ZIP file,
1,024 bytes per ZIP path, 16 KiB of response headers, 30 seconds per request,
and 600 seconds for the whole attempt. These are immutable permit values: any
overflow permanently consumes this versioned attempt and requires a separately
reviewed successor rather than retry or cap relaxation.

Verified bytes are staged under an owner-only unique directory and published
with atomic no-replace semantics so the accepted path is exactly
`build/offline-source/pion-ice-v4.3.0/dependencies/wave-3-v1/accepted`.
The success receipt precedes the manifest, which is written last. A claimed
failure publishes only a bounded failure record and retains the claim and
staging directory. Independent post-consumption readback remains required.
