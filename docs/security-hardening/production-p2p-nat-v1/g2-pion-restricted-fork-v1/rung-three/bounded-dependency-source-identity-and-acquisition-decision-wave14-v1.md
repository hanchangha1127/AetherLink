# Wave14 bounded dependency identity and acquisition decision v1

Date: 2026-07-27

Status: the authoritative combined-v12 result fixes four exact non-selected
frontier tuples. The checker pins the retained-input witness bundle and the
resulting eight-request set. Successful bounded verification reports four
complete identity pairs, zero blocked tuples, zero conflicts, and structural
acquisition readiness without granting acquisition, networking, execution,
publication, authentication, or user-action authority.

## Direct predecessor

The direct predecessor is the exact pinned read-only combined-v12 candidate:

- checker raw SHA-256:
  `cc693cb0126267962813a418a53ece371aec0172d24a75ea70cf6dbe89a1db45`
- checker normalized SHA-256:
  `cfcf095861bd753e3cfb7521e339e2bb5a3e59b5a75258ff5b8ee5cfc8ba43f2`
- tests raw SHA-256:
  `43dea4e06f07a304b620f33cf9aa647e39839dc5365705756fa10433e9bd60bd`
- candidate content SHA-256:
  `176f5802b4bb56a6136f930a02ddd648774416945984af04bae4438de4e2bc17`
- combined input-set SHA-256:
  `656dcf1c1e94b09649041fa6d99b0db1d3997914dc40eba5e7ca840b35b9760d`
- source-bindings SHA-256:
  `bf043a07c5fa6d26f28de9954b8f676e583f625ccf28ca5a39d6fe23c6678592`
- graph SHA-256:
  `0ab3b47d6b4fc628a3bf83e648308591c84ddce8ad46ce8f8d6aca1797cf1e26`
- frontier SHA-256:
  `a149da341952b398d71c9a9395cb18aac2c711bb8a8d72e1eb53ca710377df63`

Combined-v12 holds 333 source bindings: one root archive, 166 external
`go.mod` files, and 166 dependency archives. The aggregate retained-input raw
size is 307,486,547 bytes. It records 22 cumulative full-source
reconstructions and 2,644 cumulative graph archive opens. Its fixed-point flag
is false and its exact frontier count is four.

V11 test bytes remain historical metadata within the V12 candidate and are
not a live held input through that historical field. The Wave14 checker
instead live-holds the exact V12 checker and V12 test bytes as direct
predecessor inputs. It executes the pinned V12 checker to reconstruct its
candidate; it does not execute V12 tests or dependency source.

The predecessor namespace anchor is
`build/offline-source/pion-ice-v4.3.0/dependencies/.wave-13-v1.claim` at raw
SHA-256
`085fdfae86d88a53526c836e61f956b89694c67cf54ea95b9ef43cb2a8566cc2`.
The materialized decision must retain that exact path and digest.

The verifier takes two bounded namespace snapshots and proves that the
Wave14 claim, staging, accepted, acquisition, and readback namespaces are
absent. The only allowed Wave14 decision namespace entries are this reader,
its JSON decision, its checker, and its tests. This is a point-in-time check,
not a namespace reservation.

## Exact frontier identity

`selectedByGraphAlgorithm` is a graph fact, not an authority selector. All
four rows are non-selected, require a separate wave decision, and keep
acquisition authority false.

| Order | Module | Version | Tuple digest | Graph selected |
|---:|---|---|---|:---:|
| 1 | `golang.org/x/crypto` | `v0.40.0` | `6ade739bf483ce7bbe3a8662064f0424184ddc24689d06ae5518df328bc76c22` | false |
| 2 | `golang.org/x/term` | `v0.33.0` | `47100744b1c211a90d139b762eb19fbb693e93a931518da4bf31d2e4d54903bf` | false |
| 3 | `golang.org/x/text` | `v0.27.0` | `1bdf857599830a828b795a288f3b70a3a54407261328b3b089bdfcd71cbba067` | false |
| 4 | `golang.org/x/tools` | `v0.34.0` | `b142b05fc3ea3268cdd3c7c02c1e43a2ad031f7464cabab1dd1a56f4b7937c1d` | false |

The two retained-input identity scans independently reproduce the same ordered
tuples, parent declarations, `go.mod` H1 values, module-ZIP H1 values, and
ZIP-contained `go.sum` entry count. A ready result requires four complete H1
pairs, zero blocked tuples, and zero conflicts.

Identity witness bundle:

- ZIP-contained `go.sum` entry count: 116
- parent declarations: 4
- `go.mod` H1 witnesses: 4
- module-ZIP H1 witnesses: 4
- compact identity SHA-256:
  `a59b37276b85f5da5cbf2c39a560c7834582cf1f590e050d53e016ed80fb6185`
- full witness SHA-256:
  `cf39e4c68e001b3d687df829e7d7903d4ebea69b11ee60f21d5385f9591fa542`
- declaration witness SHA-256:
  `c36cb36497348686dcc2ca7881a1643b1e86c48ce8864e7656db70faf98c7136`
- `go.mod` H1 witness SHA-256:
  `5bbf09f43ba7d7d6f419ee65a5ba6958454494847fe82946b84134c209a473db`
- module-ZIP H1 witness SHA-256:
  `f9e73b0c39cb574b8f1daf858e7aa3a213a32a444d3646ebc3ee46e825b7534b`

Retained `go.sum` evidence is not fresh checksum-database inclusion proof and
does not authorize an external checksum lookup.

## Structural acquisition preparation

The decision describes exactly eight ordered HTTPS GET request shapes:
`.mod` then ZIP for each tuple in table order. Every request uses host
`proxy.golang.org`, direct lowercase ASCII module-path encoding, a 1,048,576
byte `.mod` limit, or a 16,777,216 byte ZIP limit. Each `expectedH1` comes
from the sealed retained-input witness bundle.

Request-set canonicalization is
`utf8_unescaped_sorted_keys_compact_no_trailing_lf`; its SHA-256 is
`505587c90ec32b1dea879b1e034450de091874a2ff9db9993532f1b14d9dc3aa`.

Every request keeps:

- `selectedByGraphAlgorithm=false`
- `authenticationRequired=false`
- `networkAuthorized=false`
- `acquisitionAuthorized=false`

A later one-use gate would have to independently bind all eight expected H1
values, byte limits, no-overwrite staging, atomic no-replace promotion, and
post-consumption readback. This decision reserves no namespace, performs no
request, and asks for no credentials, ownership proof, keys, signatures,
tokens, passwords, or other authentication.

## Verification and operation accounting

The direct combined-v12 run accounts for 2,310 inherited plus 334 current
graph archive opens, totaling 2,644. Two retained-input identity scans add 334
read-only archive opens, so overall decision accounting is 2,978 archive
opens. Reconstruction counts are 20 inherited plus two current, totaling 22.

This package is verification-only. It exposes no record, acquisition, runner,
or state-mutating materialization mode. Dependency source is not acquired.
Archive extraction and dependency-source load, execution, and compilation
counters are zero. Network, product-runtime network, socket, subprocess,
authentication, and filesystem-write counters are zero. DNS, acquisition,
Git write, and publication remain unauthorized.

The materialized decision binds the checker normalized bytes, checker-test raw
bytes, and this reader's raw bytes. Those byte identities are validated by the
pinned checker rather than treated as approval.

## Closed authority and completion boundary

All authority and user-input fields remain false, including acquisition,
authentication, compile, DNS, execution, filesystem extraction, file or Git
write, network, publication, socket, source load/execution, subprocess,
credential, signature, token, and user-action fields.

Only after both independent identity scans and the package seal agree may
`wave14IdentityResolved` and `wave14AcquisitionReady` become true. Even then,
`wave14AcquisitionComplete`, dependency fixed point, dependency closure,
semantic closure, rung-three completion, candidate selection, library
selection, and release readiness remain false.

The next bounded action is only preparation of a separate one-use
eight-resource Wave14 acquisition permit checker, runner, and tests. That
later action requires a distinct decision and is not authorized by this
document.
