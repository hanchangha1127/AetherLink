# G2 Pion dependency wave-one recovery decision v1

This document records the terminal result of the consumed wave-one v1 permit
and selects the design boundary for a separate v2 implementation. It does not
authorize network access or a retry of the v1 permit.

No user authentication is required. Repository-owner proof, an external
account login, private keys, tokens, passwords, signatures, and user action are
all outside this personal-project recovery gate. Product endpoint
authentication remains a separate runtime invariant.

## What happened

The v1 claim and failure receipt are retained verbatim. The runner attempted two
ordered requests. Tuple one, `github.com/google/uuid@v1.6.0`, completed ZIP and
module-hash validation and reached staging. Tuple two,
`github.com/pion/dtls/v3@v3.1.5`, completed its response body and entered ZIP
inspection, where an entry exceeded the uncalibrated `200:1` compression-ratio
gate. Publication never occurred, all staging files were removed, and the v1
permit was consumed without an accepted source set.

The historical receipt's `completedRequestCount=1` means one fully validated
and staged tuple, not one completed HTTP response. The response-body count is
two. `failedTupleId` is null because the v1 ZIP assertion did not attach the
tuple context; the ordered counters and ZIP phase derive
`wave1-002-c4e8ffbb48de`, but they do not establish the failed entry, its exact
sizes or ratio, or the response ZIP's raw hash.

## Selected v2 design

The arbitrary ratio threshold becomes non-gating, exact-integer telemetry.
The v2 runner must still stream every entry and retain the existing hard
ceilings: 16 MiB per response, 128 MiB aggregate response bytes, 16 MiB per
file, 256 MiB uncompressed per archive, 1 GiB aggregate uncompressed bytes,
entry-count bounds, and the 30-second request and 300-second whole-wave
deadlines. This keeps memory, retained bytes, decompression work, and elapsed
time bounded without guessing a compatibility threshold.

V2 must record separate request-attempt, response-body-complete, and
validated-and-staged counters. Tuple-local failures must include the tuple ID
and may include only bounded entry ordinal and compressed/uncompressed byte
counts; entry names and bodies stay out of failure records.

The v1 claim and failure receipt may not be deleted, reused, resumed, or
reinterpreted as authorization. V2 uses distinct claim, staging, final,
receipt, failure, and manifest paths and must acquire a fresh complete set of
19 tuples. The next action is only to prepare and test that separate v2 runner,
checker, and execution permit.
