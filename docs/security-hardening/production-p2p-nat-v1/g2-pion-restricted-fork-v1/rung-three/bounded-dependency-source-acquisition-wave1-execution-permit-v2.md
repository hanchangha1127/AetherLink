# G2 Pion dependency wave-one execution permit v2

This reader accompanies
`g2-pion-ice-v4.3.0-rung3-dependency-wave1-execution-permit-v2`.
Its status is
`wave1_v2_dependency_source_acquisition_authorized_not_consumed`, its result is
`exact_19_public_proxy_zip_requests_v2_authorized_once_not_executed`, and its
single next action is `execute_bound_dependency_source_wave1_v2_once`.

No user authentication is required. Repository-owner proof, account login,
private keys, tokens, passwords, signatures, and further user action are not
part of this personal-project execution boundary. Product pairing and endpoint
authentication remain unchanged runtime requirements.

The v1 claim and failure receipt remain immutable terminal evidence. They
cannot be deleted, reused, resumed, or treated as v2 authority. V2 uses a
separate v2 claim, a separate staging prefix, a separate final directory, and
separate receipt, failure, and manifest paths. It acquires exactly 19 fresh sequential
public Go proxy ZIP responses and never resumes the deleted v1 staging set.

The v2 runner retains the complete predecessor bounds, including 16 MiB per response,
128 MiB across response bodies, 16 MiB per file, 256 MiB
uncompressed per archive, 1 GiB aggregate uncompressed data, entry, central
directory, path, retained-byte, receipt-size, and hard deadline ceilings. The
former `200:1` compatibility gate is not raised or reused as a rejection rule.
Instead, every successfully validated archive records non-gating exact-integer telemetry
for the maximum entry ratio using an ordinal and its uncompressed
and compressed byte counts. No floating-point ratio, entry name, path, or body
is recorded.

Request attempts, completed response bodies, and fully validated/staged tuples
use three distinct counters. A tuple-local failure includes its tuple ID and
order. The one-use v2 claim is created durably before the first network
attempt, persists after any attempt, and prevents retry.

Runner post-state validation accepts only exact failure, success-receipt,
source-row, telemetry, and manifest key sets. It rejects forbidden raw fields,
unknown failure codes, incomplete tuple context, invalid counter or telemetry
values, incomplete source rows, and any missing, extra, replaced, or
hash-mismatched retained ZIP. A coherent consumed failure is valid terminal
evidence but does not pass the default gate. A post-publication error is
reported as `consumed_terminal_state_uncertain`, with automatic retry disabled.

Success publishes the complete fresh set atomically and writes its manifest
last. Runner checks are not independent readback. A separate fixed-name
independent readback must validate the retained 19 ZIPs, receipt, manifest,
counters, hashes, H1 values, telemetry, namespace, and preserved v1 terminal
evidence before dependency review can continue.
