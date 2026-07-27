# Wave12 bounded dependency identity and acquisition decision v1

Date: 2026-07-27

Status: four exact frontier identities are complete and structurally ready for
a later acquisition-permit decision. This document does not authorize source
acquisition, networking, execution, publication, authentication, or user
action.

## Direct predecessor

The direct predecessor is the exact pinned read-only combined-v10 candidate:

- checker raw SHA-256:
  `11d0c2743f92d59a8417870db279edeb6a1b6c0a1af9db577e5cec4c50350985`
- checker normalized SHA-256:
  `ccb5430b1c41e5fcd39e00b7345ba285a427b1b25d48c299f81f1be8ca25f751`
- tests raw SHA-256:
  `ab00dbe4d70fbfc596ee6553e2d87f94f75370f07ff38b93d5c5fb5652bfac35`
- candidate content SHA-256:
  `d7feddd3b291756c36359b013ea05aaa2f25cb83605daaeb493c0395ff9cc4f7`
- combined input-set SHA-256:
  `f946c625334ac8cf42d42c9f45f0f051eb7f89fb9ecf5dfc576114b1cba990be`
- source-bindings SHA-256:
  `067808934056712884a75ea669d61189bb5d5d722d2a961c8b8c5d25345bb75c`
- graph SHA-256:
  `77813f467c7452290f35c4ecaa6a1041a0988d563ea37660bb6cc902bb95cdc4`
- frontier SHA-256:
  `8b84bd2fd9201d33f4424b9dd1018aee7f8470a87306c2ba23eba0c8b6d4ff05`

Combined-v10 holds 317 source bindings: one root archive, 158 external
`go.mod` files, and 158 dependency archives. It records eighteen cumulative
full-source reconstructions and 1,984 cumulative graph archive opens. V9 test
bytes remain historical metadata within the V10 candidate; this Wave12 checker
separately live-holds the exact V10 checker and V10 test bytes without
executing the tests or treating them as approval.

The predecessor namespace anchor is
`build/offline-source/pion-ice-v4.3.0/dependencies/.wave-11-v1.claim` at raw
SHA-256
`a41663bd827b8f07e0e04e887b21a7306c0ba286396e43d854ea3f2369a3e985`.
The materialized predecessor binding retains that exact anchor path and raw
digest.
The Wave12 claim, staging, accepted, acquisition, and readback namespaces are
absent at both bounded namespace snapshots. This is a point-in-time check, not
a namespace reservation.

## Exact frontier identity

`selectedByGraphAlgorithm` is a graph fact, not an authority selector. All four
rows are non-selected, require a separate wave decision, and keep acquisition
authority false.

| Order | Module | Version | Graph selected | `go.mod` H1 | Module ZIP H1 |
|---:|---|---|:---:|---|---|
| 1 | `golang.org/x/crypto` | `v0.41.0` | false | `h1:pO5AFd7FA68rFak7rOAGVuygIISepHftHnr8dr6+sUc=` | `h1:WKYxWedPGCTVVl5+WHSSrOBT0O8lx32+zxmHxijgXp4=` |
| 2 | `golang.org/x/term` | `v0.34.0` | false | `h1:5jC53AEywhIVebHgPVeg0mj8OD3VO9OzclacVrqpaAw=` | `h1:O/2T7POpk0ZZ7MAzMeWFSg6S5IpWd/RXDlM9hgM3DR4=` |
| 3 | `golang.org/x/text` | `v0.28.0` | false | `h1:U8nCwOR8jO/marOQ0QbDiOngZVEBB7MAiitBuMjXiNU=` | `h1:rhazDwis8INMIwQ4tpjLDzUhx6RlXqZNPEM0huQojng=` |
| 4 | `golang.org/x/tools` | `v0.35.0` | false | `h1:NKdj5HkL/73byiZSJjqJgKn3ep7KjFkBOkR/Hps3VPw=` | `h1:mBffYraMEf7aa0sB+NuKnuCy8qI/9Bughn8dC2Gu5r0=` |

Each row has one parent declaration, one `go.mod` H1 witness, and one module
ZIP H1 witness. Both scans reproduce 109 ZIP-contained `go.sum` entries, four
complete H1 pairs, zero blocked tuples, and zero conflicts.

The witness bindings are:

- compact identity:
  `23b6b188a88c5bdb87abe99325ec7a6d4580605ca69869f2614e36e134c07752`
- full witness:
  `2b13a602a2faf12ea2eb5f6d578a562033148ccded4035799756d969b96bdfa0`
- declaration witness:
  `4270ecd062e70ffa00ebcbbcec9bc65ebadcb6c6810eeb80b05eb0ab8c14e9d2`
- `go.mod` H1 witness:
  `33ad9b08e9497df211aa43bbd74895a1bc6f0f56a1cda0fcb125aa7940b3fa0e`
- module-ZIP H1 witness:
  `98a16f5f2393280c989afe77bb878676db5573d476c26fec3a59988790217e29`

Retained `go.sum` evidence is not fresh checksum-database inclusion proof.

## Structural acquisition preparation

The decision describes exactly eight ordered GET request shapes, `.mod` then
ZIP for each tuple. Their canonical SHA-256 is
`6531872e99da0c94746cbdb53fe9f5302ebc71bc82bfde1705b5e2300b2a2ee5`.
Every request keeps `selectedByGraphAlgorithm=false`,
`authenticationRequired=false`, `networkAuthorized=false`, and
`acquisitionAuthorized=false`.

A later one-use gate would have to independently bind byte limits,
no-overwrite staging, atomic no-replace promotion, and post-consumption
readback. This decision reserves no namespace, performs no request, and does
not ask the user for credentials, ownership proof, keys, signatures, tokens,
passwords, or any other authentication.

## Operation and authority boundary

The direct combined-v10 run accounts for 1,666 inherited plus 318 current graph
archive opens, totaling 1,984. Two identity scans add 318 read-only archive
opens, so overall decision accounting is 2,302 archive opens. Reconstruction
counts are sixteen inherited plus two current, totaling eighteen.

Dependency-source acquisition, extraction, loading, execution, and compilation
are all zero. Network, subprocess, authentication, filesystem write, Git write,
publication, and socket operations are also zero. No password, private key,
signature, token, repository-owner proof, external authentication, or user
action is required.
Dedicated product-runtime network and socket operation counters are both zero.

Dependency fixed point, dependency closure, semantic closure, rung-three
completion, candidate selection, library selection, and release readiness all
remain false. The next bounded action is only preparation of a separate
one-use eight-resource Wave12 acquisition permit checker, runner, and tests.
