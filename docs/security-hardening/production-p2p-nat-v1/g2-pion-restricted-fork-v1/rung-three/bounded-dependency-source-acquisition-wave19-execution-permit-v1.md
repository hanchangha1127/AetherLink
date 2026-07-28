# Wave19 bounded dependency-source acquisition permit v1

This reader explains the adjacent canonical JSON permit. Creating, checking,
or preflighting this package performs no acquisition, claim creation, DNS,
socket, TLS, HTTPS, subprocess, source extraction, source loading, source
execution, compilation, device work, product-runtime networking, Git write,
or other filesystem write.

## Exact four-resource scope

The permit covers exactly two ordered tuples and four ordered public-proxy
requests:

1. `GET https://proxy.golang.org/golang.org/x/crypto/@v/v0.38.0.mod`
2. `GET https://proxy.golang.org/golang.org/x/crypto/@v/v0.38.0.zip`
3. `GET https://proxy.golang.org/golang.org/x/text/@v/v0.25.0.mod`
4. `GET https://proxy.golang.org/golang.org/x/text/@v/v0.25.0.zip`

The exact tuple identities, accepted stems, and H1 pairs are:

- `golang.org/x/crypto@v0.38.0`,
  `001-a26a2513c9f4c49c479c`,
  `h1:MvrbAqul58NNYPKnOra203SB9vpuZW0e+RRZV+Ggqjw=`,
  `h1:jt+WWG8IZlBnVbomuhg2Mdq0+BBQaHbtqHEFEigjUV8=`
- `golang.org/x/text@v0.25.0`,
  `002-c6022d5be99f60f2428e`,
  `h1:WEdwpYrmk1qmdHvhkSTNPm3app7v4rsT8F2UD6+VHIA=`,
  `h1:qVyWApTSYLk/drJRO5mDlNYskwQznZmkpV2c8q9zls4=`

`selectedByGraphAlgorithm=false` is a bound graph fact, not an authorization
selector. The permit grants only this bounded one-use acquisition. It grants
no authentication, owner-proof, credential, package-manager, extraction,
loading, execution, compilation, deployment, device, product-network, Git,
release, or publication authority outside the local acquisition records.

Only direct TLS-validated HTTPS to `proxy.golang.org:443` is permitted.
Authentication headers, proxy authorization, cookies, client certificates,
redirects, alternate hosts, ambient proxies, request bodies, range requests,
query strings, fragments, retries, resume, and backfill are forbidden.

Per-resource limits are 1 MiB for each `.mod` and 16 MiB for each ZIP.
Aggregate limits are 2 MiB for all `.mod` responses, 32 MiB for all ZIP
responses, and 34 MiB overall. Each ZIP is limited to 20,000 entries,
128 MiB uncompressed, 128 MiB per entry, and 1,024 UTF-8 bytes per name;
the two-ZIP aggregate limits are 40,000 entries and 256 MiB uncompressed.
Acceptance requires both exact H1 pairs, safe archive names, CRC
validation, each exact module/version prefix, and embedded `go.mod` parity.
No archive member is extracted to the filesystem.

The decision's four request rows are projected into permit resources only
through a typed, canonical digest seal. Boolean/integer aliases, cross-tuple
substitution, duplicate authority paths, reordered rows, and self-consistent
same-count rebindings fail closed.

## One-use boundary

Execution is possible only with the sealed runner and exact `--execute`
argument. The runner must exclusively create and durably sync
`build/offline-source/pion-ice-v4.3.0/dependencies/.wave-19-v1.claim` in mode
`0600` before DNS or network use. A pre-existing claim is `already_consumed`.

The claim persists after success, failure, timeout, or uncertainty. Retry,
resume, backfill, overwrite, and cleanup are unauthorized. Owner-only staging
uses prefix `.wave-19-v1-staging-`; successful bytes publish without
replacement beneath `wave-19-v1/accepted`. Evidence is staged before atomic
publication. A receipt or failure record is written without replacement, and
the terminal manifest is written last.

The completed Wave18 claim is a pinned predecessor anchor for the V17
fixed-point input. It is not the Wave19 consumption claim.

## Current state

The acquisition checker and runner may be dry-validated without `--execute`.
This package preparation has not invoked the runner's acquisition path,
created the Wave19 claim, contacted the network, or written acquisition
artifacts. Independent local byte readback remains required after any future
successful one-use execution.
