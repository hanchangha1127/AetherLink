# Wave18 bounded dependency-source acquisition permit v1

This reader explains the adjacent canonical JSON permit. Creating, checking,
or preflighting this package performs no acquisition, claim creation, DNS,
socket, TLS, HTTPS, subprocess, source extraction, source loading, source
execution, compilation, device work, product-runtime networking, Git write,
or other filesystem write.

## Exact six-resource scope

The permit covers exactly three ordered tuples and six ordered public-proxy
requests:

1. `GET https://proxy.golang.org/golang.org/x/mod/@v/v0.24.0.mod`
2. `GET https://proxy.golang.org/golang.org/x/mod/@v/v0.24.0.zip`
3. `GET https://proxy.golang.org/golang.org/x/net/@v/v0.40.0.mod`
4. `GET https://proxy.golang.org/golang.org/x/net/@v/v0.40.0.zip`
5. `GET https://proxy.golang.org/golang.org/x/sync/@v/v0.14.0.mod`
6. `GET https://proxy.golang.org/golang.org/x/sync/@v/v0.14.0.zip`

The exact tuple identities, accepted stems, and H1 pairs are:

- `golang.org/x/mod@v0.24.0`,
  `001-bb2025870bcef7a0c287`,
  `h1:IXM97Txy2VM4PJ3gI61r1YEk/gAj6zAHN3AdZt6S9Ww=`,
  `h1:ZfthKaKaT4NrhGVZHO1/WDTwGES4De8KtWO0SIbNJMU=`
- `golang.org/x/net@v0.40.0`,
  `002-3c84a9eecca520aed886`,
  `h1:y0hY0exeL2Pku80/zKK7tpntoX23cqL3Oa6njdgRtds=`,
  `h1:79Xs7wF06Gbdcg4kdCCIQArK11Z1hr5POQ6+fIYHNuY=`
- `golang.org/x/sync@v0.14.0`,
  `003-4615480e24f0c4184e4c`,
  `h1:1dzgHSNfp02xaA81J2MS99Qcpr2w7fw1gpm99rleRqA=`,
  `h1:woo0S4Yywslg6hp4eUFjTVOyKt0RookbpAHG4c1HmhQ=`

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
Aggregate limits are 3 MiB for all `.mod` responses, 48 MiB for all ZIP
responses, and 51 MiB overall. Each ZIP is limited to 20,000 entries,
128 MiB uncompressed, 128 MiB per entry, and 1,024 UTF-8 bytes per name;
the three-ZIP aggregate limits are 60,000 entries and 384 MiB uncompressed.
Acceptance requires all three exact H1 pairs, safe archive names, CRC
validation, each exact module/version prefix, and embedded `go.mod` parity.
No archive member is extracted to the filesystem.

The decision's six request rows are projected into permit resources only
through a typed, canonical digest seal. Boolean/integer aliases, cross-tuple
substitution, duplicate authority paths, reordered rows, and self-consistent
same-count rebindings fail closed.

## One-use boundary

Execution is possible only with the sealed runner and exact `--execute`
argument. The runner must exclusively create and durably sync
`build/offline-source/pion-ice-v4.3.0/dependencies/.wave-18-v1.claim` in mode
`0600` before DNS or network use. A pre-existing claim is `already_consumed`.

The claim persists after success, failure, timeout, or uncertainty. Retry,
resume, backfill, overwrite, and cleanup are unauthorized. Owner-only staging
uses prefix `.wave-18-v1-staging-`; successful bytes publish without
replacement beneath `wave-18-v1/accepted`. Evidence is staged before atomic
publication. A receipt or failure record is written without replacement, and
the terminal manifest is written last.

The completed Wave17 claim is a pinned predecessor anchor for the V16
fixed-point input. It is not the Wave18 consumption claim.

## Current state

The acquisition checker and runner may be dry-validated without `--execute`.
This package preparation has not invoked the runner's acquisition path,
created the Wave18 claim, contacted the network, or written acquisition
artifacts. Independent local byte readback remains required after any future
successful one-use execution.
