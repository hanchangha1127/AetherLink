# Wave17 bounded dependency-source acquisition permit v1

This reader explains the adjacent canonical JSON permit. Creating, checking,
or preflighting this package performs no acquisition, claim creation, DNS,
socket, TLS, HTTPS, subprocess, source extraction, source loading, source
execution, compilation, device work, product-runtime networking, Git write,
or other filesystem write.

## Exact two-resource scope

The permit covers one tuple, `golang.org/x/tools@v0.33.0`, and exactly two
ordered public-proxy requests:

1. `GET https://proxy.golang.org/golang.org/x/tools/@v/v0.33.0.mod`
2. `GET https://proxy.golang.org/golang.org/x/tools/@v/v0.33.0.zip`

The accepted filenames are `001-8bd04ea612cec9787131.mod` and
`001-8bd04ea612cec9787131.zip`. Their retained expected H1 values are:

- `go.mod`: `h1:CIJMaWEY88juyUfo7UbgPqbC8rU2OqfAV1h2Qp0oMYI=`
- module ZIP: `h1:4qz2S3zmRxbGIhDIAgjxvFutSvH5EfnsYrRBj0UI0bc=`

`selectedByGraphAlgorithm=false` is a bound graph fact, not an authorization
selector. The permit grants only this bounded one-use acquisition. It grants
no authentication, owner-proof, credential, package-manager, extraction,
loading, execution, compilation, deployment, device, product-network, Git,
release, or publication authority outside the local acquisition records.

Only direct TLS-validated HTTPS to `proxy.golang.org:443` is permitted.
Authentication headers, proxy authorization, cookies, client certificates,
redirects, alternate hosts, ambient proxies, request bodies, range requests,
query strings, fragments, retries, resume, and backfill are forbidden.

Limits are 1 MiB for the `.mod`, 16 MiB for the ZIP, and 17 MiB aggregate.
The ZIP is limited to 20,000 entries, 128 MiB uncompressed total, and 128 MiB
per entry. Acceptance requires the exact H1 pair, safe archive names, CRC
validation, the exact module/version prefix, and embedded `go.mod` parity.
No archive member is extracted to the filesystem.

## One-use boundary

Execution is possible only with the sealed runner and exact `--execute`
argument. The runner must exclusively create and durably sync
`build/offline-source/pion-ice-v4.3.0/dependencies/.wave-17-v1.claim` in mode
`0600` before DNS or network use. A pre-existing claim is `already_consumed`.

The claim persists after success, failure, timeout, or uncertainty. Retry,
resume, backfill, overwrite, and cleanup are unauthorized. Owner-only staging
uses prefix `.wave-17-v1-staging-`; successful bytes publish without
replacement beneath `wave-17-v1/accepted`. Evidence is staged before atomic
publication. A receipt or failure record is written without replacement, and
the terminal manifest is written last.

The completed Wave16 claim is a pinned predecessor anchor. It is not the
Wave17 consumption claim.

## Current state

The acquisition checker and runner may be dry-validated without `--execute`.
This package preparation has not invoked the runner's acquisition path,
created the Wave17 claim, contacted the network, or written acquisition
artifacts. Independent local byte readback remains required after any future
successful one-use execution.

