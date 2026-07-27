# Wave15 bounded dependency-source acquisition permit v1

This document explains the machine-checked, one-use Wave15 acquisition permit.
The adjacent JSON file is the canonical authority record.

## Preparation and execution boundary

- Materializing or validating the permit package does not invoke the runner,
  create the claim, use DNS, TCP, TLS, or HTTPS, start a subprocess, or write
  acquisition artifacts.
- Acquisition begins only when the separately pinned runner is invoked from
  the repository root with the exact bound interpreter, isolated flags, runner
  path, and sole argument `--execute`.
- The final permit must bind every reader and tool byte, set
  `structurePreparationOnly: false` and `executionReady: true`, and contain no
  zero digest placeholder. Any mismatch fails closed before claim creation or
  network activity.

## Exact scope

- The permit covers exactly 10 public `GET` requests to
  `https://proxy.golang.org:443`: `.mod` then `.zip` for
  `golang.org/x/mod@v0.25.0`, `golang.org/x/net@v0.41.0`,
  `golang.org/x/sync@v0.15.0`, `golang.org/x/sys@v0.33.0`, and
  `golang.org/x/telemetry@v0.0.0-20240521205824-bda55230c457`.
- Order, URL, expected `h1:`, accepted filename, per-response limit, and
  destination namespace are fixed by the canonical JSON. Every row has
  `selectedByGraphAlgorithm: false`; that is a bound graph fact. It neither
  removes a tuple nor grants product or release authority.
- Only the pinned direct-HTTPS fetch path to the exact proxy is allowed.
  Redirects, ambient proxies, alternate hosts, request bodies, ranges,
  query or fragment changes, cookies, authorization headers, client
  certificates, retries, resume, and backfill are forbidden.
- The bound limits are 1 MiB per `.mod`, 16 MiB per ZIP, 5 MiB aggregate
  `.mod`, 80 MiB aggregate ZIP, and 85 MiB aggregate total. Across all five
  ZIPs, at most 100,000 entries and 640 MiB uncompressed bytes are allowed.
  Accepted bytes require the bound `h1:` verification. ZIPs additionally
  require an exact module/version prefix, safe shape, CRC validation,
  expansion bounds, and `.mod` parity. No extraction is authorized.

## One-use claim and terminal records

- Before any DNS or network operation, the runner must durably create
  `build/offline-source/pion-ice-v4.3.0/dependencies/.wave-15-v1.claim`
  with exclusive mode-`0600` creation. A pre-existing claim means
  `already_consumed`.
- The exact historical
  `build/offline-source/pion-ice-v4.3.0/dependencies/.wave-14-v1.claim`
  predecessor anchor remains pinned throughout execution. It is not the
  Wave15 claim and does not mark this permit consumed.
- The claim persists after success, failure, timeout, or uncertainty. A second
  execution, retry, resume, backfill, overwrite, or cleanup is not authorized.
- Claim and namespace uncertainty fail closed as consumed uncertainty. Failure
  counters are committed lower bounds; an active dispatched operation is never
  reported as definitively not acquired. Success requires no active operation
  and exactly 10 committed dispatch, response, validation, and persistence
  boundaries.
- Only the claim, owner-mode staging, verified `.mod` and ZIP files, evidence,
  receipt-or-failure, and manifest-last local acquisition records may be
  written. Finalization is atomic and no-replace. Independent local byte
  readback remains required.

## Invocation and local trust boundary

- The canonical command is
  `["/Applications/Xcode.app/Contents/Developer/usr/bin/python3", "-I", "-B", "-S", "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave15_v1_once.py", "--execute"]`
  with the repository root as the current working directory.
- Exact Python-state and macOS kernel-argument checks reject accidental local
  misconfiguration; they do not authenticate invocation origin. Same-user,
  same-process code that can already access this personal-project repository
  is inside the local trust boundary. Checker and test paths cannot dispatch
  execution.

## Authentication boundary

No user identity, credential, ownership proof, or interactive approval step
exists. The checker and runner must not prompt for one. Ordinary TLS
certificate and hostname validation checks only the public proxy endpoint.

## Explicit non-authority

The permit does not authorize source extraction, source loading or execution,
package-manager execution, compilation, subprocesses, ambient or direct socket
use outside the pinned fetch path, product-runtime networking, device work,
deployment, Git operations, or release/product publication. Its local
acquisition-artifact finalization authority is not general publication
authority. It does not establish dependency fixed-point closure, semantic
closure, library selection, rung-three completion, or V1 release readiness.
