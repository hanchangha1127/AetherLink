# Wave16 bounded dependency identity and acquisition decision v1

Date: 2026-07-27

Status: the authoritative combined-v14 result fixes three exact non-selected
frontier tuples. The decision describes six future request shapes and records
structural acquisition readiness, but grants no acquisition, networking,
execution, publication, authentication, or user-action authority. No Wave16
acquisition has run.

## Direct predecessor

The direct predecessor is the exact pinned read-only combined-v14 candidate:

- checker raw SHA-256:
  `bf729f8dbfc0508fa977893eb1c7c30e07d15fa751a29856d4c4d386f1001292`
- checker normalized SHA-256:
  `8be3cf62cc66c2aaf780c658acf5b6e242fcbd52e44dd6fd90a11e3eeba505ec`
- tests raw SHA-256:
  `17adc7ea0f75eff26108187bb50a2f250655f0e190f5b51cbe1f5ea9c57896e3`
- candidate content SHA-256:
  `e77b120d6e367e03beb847eb36cbf64b37d32fe00539b029ae809310818d5b9c`
- combined input-set SHA-256:
  `c62222562f7a248398aa8677c5c4b81c41a74f3b48dbae7a1da54eea887f9d7d`
- source-bindings SHA-256:
  `a360afdc5d94502f53f5e393503198bb7ce6adf4d21a0c64245a1b7e49be9eae`
- graph SHA-256:
  `7458344c93152bea86360d2742456a28ebfc6849994bf68db30214611f020798`
- frontier SHA-256:
  `5544db5bdf34f4afadce7d91f7c56998988e68810ed96b454048bf62dc07c452`

Combined-v14 holds 351 source bindings: one root archive, 175 external
`go.mod` files, and 175 dependency archives. Their aggregate raw size is
327,603,241 bytes. The candidate records 26 cumulative full-source
reconstructions and 3,338 cumulative graph archive opens.

The predecessor namespace anchor is
`build/offline-source/pion-ice-v4.3.0/dependencies/.wave-15-v1.claim` at raw
SHA-256
`88e55eda37f5186f373ca402f574789fde93405ad588cab8f5c865c3831837a5`.
This binds the completed Wave15 acquisition boundary without claiming that
current-path identity was guaranteed through manifest publication.

## Exact frontier identity

`selectedByGraphAlgorithm` is a graph fact, not an authority selector. All
three tuples remain non-selected, require a separate wave decision, and keep
acquisition authority false. Decision tuple orders are local 1 through 3;
future combined-v15 source bindings assign global orders 176 through 178.

| Local | Global | Module | Version | Graph selected |
|---:|---:|---|---|:---:|
| 1 | 176 | `golang.org/x/crypto` | `v0.39.0` | false |
| 2 | 177 | `golang.org/x/term` | `v0.32.0` | false |
| 3 | 178 | `golang.org/x/text` | `v0.26.0` | false |

Each tuple has one parent declaration, one `go.mod` H1 witness, and one
module-ZIP H1 witness, all from the retained Wave15
`golang.org/x/net@v0.41.0` archive:

| Module | `go.mod` H1 | module-ZIP H1 |
|---|---|---|
| `golang.org/x/crypto@v0.39.0` | `h1:L+Xg3Wf6HoL4Bn4238Z6ft6KfEpN0tJGo53AAPC632U=` | `h1:SHs+kF4LP+f+p14esP5jAoDpHU8Gu/v9lFRK6IT5imM=` |
| `golang.org/x/term@v0.32.0` | `h1:uZG1FhGx848Sqfsq4/DlJr3xGGsYMu/L5GW4abiaEPQ=` | `h1:DR4lr0TjUs3epypdhTOkMmuF5CDFJ/8pOnbzMZPQ7bg=` |
| `golang.org/x/text@v0.26.0` | `h1:QK15LZJUUQVJxhz7wXgxSy/CJaTFjd0G+YLonydOVQA=` | `h1:P42AVeLghgTYr4+xUnTRKDMqpar+PtX7KWuNQL21L8M=` |

The retained-input scan observes 123 ZIP-contained `go.sum` files. Its exact
witness seals are:

- compact identity:
  `c26e87fc8722908203c01bdc91fadc26637731792301994820164a2c2c8333de`
- full witness:
  `f93d6a39cf668889fc555db8c4bebac264a1f24548f7dd7549a064b049ff14ec`
- declaration witness:
  `62a0b0bb3b457c1fb3bc985f1a45eab0b0e5a55cc55eea7ae45194a1b05e03be`
- `go.mod` H1 witness:
  `2db8d2026b0ba9437a7e47df58b0af6d90cbd94b2508220cf7da894ea592ec8b`
- module-ZIP H1 witness:
  `26d4f215903b0b1397c20b69708112910d8f1869a07328ce4761984d5f01da09`

Retained `go.sum` evidence is not fresh checksum-database inclusion proof and
does not authorize an external checksum lookup.

## Structural acquisition preparation

The decision describes six ordered HTTPS GET shapes: `.mod`, then ZIP, for
each local tuple order. Every request targets `proxy.golang.org`, carries the
sealed retained-input H1 value, and keeps authentication, networking, and
acquisition authority false. The request-set SHA-256 is
`b26cb50ac5070782744dec5a5c05f0cb07512ee421d69c52c6400946a28bd627`.

Expected accepted-file stems are:

- `001-d8646b84ee028858cb63`
- `002-2407cf4d97ca8382d3c5`
- `003-d0a18208476fea968bb8`

A later one-use gate must independently bind all six expected H1 values,
resource limits, no-overwrite staging, atomic no-replace promotion, and
post-consumption readback. This decision reserves no namespace, performs no
request, and asks for no credentials, ownership proof, keys, signatures,
tokens, passwords, or other authentication.

## Verification accounting and boundary

The combined-v14 candidate accounts for 2,986 inherited plus 352 current
graph archive opens, totaling 3,338. Two retained-input identity scans add
352 read-only archive opens, for 3,690 overall decision-execution archive
opens. The package uses seven descriptor-identity barriers and two namespace
snapshots.

Dependency source is not acquired, extracted, loaded, executed, or compiled.
Network, product-runtime network, socket, subprocess, authentication,
filesystem-write, and archive-extraction counters remain zero.

Only after the package seals and both independent identity scans agree may
`wave16IdentityResolved` and `wave16AcquisitionReady` be true. Even then,
`wave16AcquisitionComplete`, dependency fixed point, dependency closure,
semantic closure, rung-three completion, candidate selection, library
selection, and release readiness remain false.

The next bounded action is preparation of a separate one-use six-resource
Wave16 acquisition permit, checker, runner, and tests. It is not authorized
by this decision.

## Package seals

The checker, checker tests, reader, and decision content are sealed to their
final package bytes. No all-zero package placeholder remains. The predecessor
and identity/witness seals above are independently derived exact values.
