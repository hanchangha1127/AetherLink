# Wave16 bounded dependency-source acquisition permit v1

This document explains the machine-checked, one-use Wave16 acquisition permit.
The adjacent JSON file is the canonical authority record.

## Sealed execution boundary

- Creating or validating this package does not invoke the runner, create the
  claim, use DNS, TCP, TLS, or HTTPS, start a subprocess, or write acquisition
  artifacts.
- The permit reader, four Wave16 package tools, normalized runner, and permit
  content are sealed to their exact final byte digests; no zero placeholder
  remains in the canonical package.
- Acquisition can begin only through the separately pinned runner from the
  repository root with the exact bound interpreter, isolated flags, runner
  path, and sole argument `--execute`.

## Exact six-resource scope

- The permit covers exactly six public `GET` requests to
  `https://proxy.golang.org:443`: `.mod` then `.zip` for each of these exact
  tuples:

  - `golang.org/x/crypto@v0.39.0`
  - `golang.org/x/term@v0.32.0`
  - `golang.org/x/text@v0.26.0`

- The accepted filename stems are respectively
  `001-d8646b84ee028858cb63`, `002-2407cf4d97ca8382d3c5`, and
  `003-d0a18208476fea968bb8`.
- The expected `.mod`/`.zip` `h1:` pairs are respectively:

  - `h1:L+Xg3Wf6HoL4Bn4238Z6ft6KfEpN0tJGo53AAPC632U=` /
    `h1:SHs+kF4LP+f+p14esP5jAoDpHU8Gu/v9lFRK6IT5imM=`
  - `h1:uZG1FhGx848Sqfsq4/DlJr3xGGsYMu/L5GW4abiaEPQ=` /
    `h1:DR4lr0TjUs3epypdhTOkMmuF5CDFJ/8pOnbzMZPQ7bg=`
  - `h1:QK15LZJUUQVJxhz7wXgxSy/CJaTFjd0G+YLonydOVQA=` /
    `h1:P42AVeLghgTYr4+xUnTRKDMqpar+PtX7KWuNQL21L8M=`

- Every tuple has `selectedByGraphAlgorithm: false`. This is a bound graph
  fact; it neither removes the tuple nor grants product or release authority.
- Only direct HTTPS to the exact proxy is allowed. Authentication, credentials,
  authorization or proxy-authorization headers, cookies, client certificates,
  redirects, ambient proxies, alternate hosts, request bodies, ranges, query
  or fragment changes, retries, resume, and backfill are forbidden.
- Limits are 1 MiB per `.mod`, 16 MiB per ZIP, 3 MiB aggregate `.mod`, 48 MiB
  aggregate ZIP, and 51 MiB aggregate total. Across all three ZIPs, at most
  60,000 entries and 384 MiB uncompressed bytes are allowed. Accepted bytes
  require the bound `h1:` checks; ZIPs additionally require the exact
  module/version prefix, safe shape, CRC validation, expansion bounds, and
  `.mod` parity. Source extraction is not authorized.

## One-use claim and terminal records

- Before any DNS or network operation, the runner must durably and exclusively
  create
  `build/offline-source/pion-ice-v4.3.0/dependencies/.wave-16-v1.claim`
  in mode `0600`. A pre-existing claim means `already_consumed`.
- The exact historical
  `build/offline-source/pion-ice-v4.3.0/dependencies/.wave-15-v1.claim`
  predecessor anchor remains pinned throughout execution. It is not the
  Wave16 claim and does not mark this permit consumed.
- Staging names begin `.wave-16-v1-staging-`; accepted artifacts finalize
  without replacement under
  `build/offline-source/pion-ice-v4.3.0/dependencies/wave-16-v1`.
- The claim persists after success, failure, timeout, or uncertainty. A second
  execution, retry, resume, backfill, overwrite, or cleanup is not authorized.
  Success requires no active operation and exactly six committed dispatch,
  response, validation, and persistence boundaries.
- Only the claim, owner-mode staging, verified `.mod` and ZIP files, evidence,
  receipt-or-failure, and manifest-last local acquisition records may be
  written. Independent local byte readback remains required.

## Authentication and trust boundary

No account, owner proof, SSH or GPG proof, password, private key, signature,
token, cookie, client certificate, credential, or interactive approval is
required. The checker and runner must not prompt for any of them. Ordinary TLS
certificate and hostname validation authenticates only the public proxy
endpoint. Exact Python-state and macOS kernel-argument checks guard accidental
local misconfiguration; they do not authenticate invocation origin.

## Explicit non-authority

The permit does not authorize source extraction, source loading or execution,
package-manager use, compilation, subprocesses, ambient or direct socket use
outside the pinned fetch path, product-runtime networking, device work,
deployment, Git operations, or release/product publication. It does not
establish dependency fixed-point closure, semantic closure, library selection,
rung-three completion, or V1 release readiness.
