# Offline public-checksum identity readback execution permit v1

This permit authorizes one authentication-free, network-free, offline readback
of the completed SumDB identity-resolution attempt
`02e6be7ab4a6ebb6d8beba2142c81406`.

The execution permit, checker, runner, durable execution claim, eleven exact
evidence files, success receipt, and manifest are frozen by path, SHA-256,
byte length, owner, link count, and mode. The readback recorder must not invoke
the execution checker or runner because their original unused-namespace
precondition has already been consumed.

Before reading the frozen inputs, the recorder creates and durably syncs the
exclusive owner-only claim
`build/offline-source/pion-ice-v4.3.0/dependencies/.wave-3-kr-pty-sumdb-identity-readback-v1.claim`.
The claim is permanent whether verification succeeds, fails, or becomes
uncertain. Retry, resume, replacement, and backfill are forbidden.

After claiming, every frozen file is reopened with no-follow semantics and held
open through verification. The recorder independently verifies canonical JSON
content bindings, the exact evidence inventory and permissions, attempt and
authority bindings, the strict two-line lookup record, the pinned SumDB signed
tree head, the independently derived hash-tile plan, tile bodies and hashes,
RFC 6962 record inclusion, old-to-new consistency, counters, aggregate bytes,
terminal exclusivity, and receipt-to-manifest linkage. It does not import or
call the network runner.

Only after all checks pass may the recorder atomically publish the reserved
readback receipt and then the readback manifest last, both with no-replace
semantics. Failure produces no success document and leaves the readback claim
in place.

This permit authorizes no DNS, socket, network, proxy, authentication,
credentials, user action, source acquisition, archive extraction, source
loading, execution, compilation, package manager, Git, device, deployment, or
product-runtime operation. Success establishes only an independent offline
readback of the frozen identity metadata; it does not authorize source
acquisition or release.
