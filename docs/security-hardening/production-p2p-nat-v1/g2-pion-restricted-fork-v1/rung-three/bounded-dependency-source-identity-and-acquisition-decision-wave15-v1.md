# Wave15 bounded dependency identity and acquisition decision v1

Date: 2026-07-27

Status: the authoritative combined-v13 result fixes five exact non-selected
frontier tuples. The checker pins the retained-input witness bundle and the
resulting ten-request set. Successful bounded verification reports five
complete identity pairs, zero blocked tuples, zero conflicts, and structural
acquisition readiness without granting acquisition, networking, execution,
publication, authentication, or user-action authority.

## Direct predecessor

The direct predecessor is the exact pinned read-only combined-v13 candidate:

- checker raw SHA-256:
  `0b0ea7d68ef5fc11b8c0defe56bf443c681a6952a27e2c9b6c41d9702241a80b`
- checker normalized SHA-256:
  `73a778e53bdc1d15ffd34109ff02297e85eb6a91b52d1577acefe9bc1383e674`
- tests raw SHA-256:
  `dffb5e24cfd2ba4c561f5e8c6302c4502a75f917c1ac9d15216fd7f2ac045327`
- candidate content SHA-256:
  `e1f711b558642ad2167da48f25184cd4c3235314c67f06a60cfd14ceecea1988`
- combined input-set SHA-256:
  `285cfb3e8b4a73beffa551429058611a606b00ad447d75599c77fb18895a2f91`
- source-bindings SHA-256:
  `fbd023d2ee5f372ef90d06d92e48c7dfa9828212e38bf942e1741aca322b9996`
- graph SHA-256:
  `a35d9bd389a6fb9e04052eb411e4c9701a76ff0fd699e1c2d2a113d86439dfd5`
- frontier SHA-256:
  `1d143e954c48cb48172cf61975868c3c76852f152d100a04745b16b02fa5e911`

Combined-v13 holds 341 source bindings: one root archive, 170 external
`go.mod` files, and 170 dependency archives. The aggregate retained-input raw
size is 322,537,995 bytes. It records 24 cumulative full-source
reconstructions and 2,986 cumulative graph archive opens. Its fixed-point flag
is false and its exact frontier count is five.

V12 test bytes remain historical metadata within the V13 candidate and are
not a live held input through that historical field. The Wave15 checker
instead live-holds the exact V13 checker and V13 test bytes as direct
predecessor inputs. It executes the pinned V13 checker to reconstruct its
candidate; it does not execute V13 tests or dependency source.

The predecessor namespace anchor is
`build/offline-source/pion-ice-v4.3.0/dependencies/.wave-14-v1.claim` at raw
SHA-256
`e67441825a0acd2741bf3a87d46020066a607476c08091c374b4f707059b3d40`.
The materialized decision must retain that exact path and digest.

The verifier takes two bounded namespace snapshots and proves that the
Wave15 claim, staging, accepted, acquisition, and readback namespaces are
absent before any later Wave15 acquisition. The only allowed Wave15 decision
namespace entries are this reader,
its JSON decision, its checker, and its tests. This is a point-in-time check,
not a namespace reservation.

## Exact frontier identity

`selectedByGraphAlgorithm` is a graph fact, not an authority selector. All
five rows are non-selected, require a separate wave decision, and keep
acquisition authority false.

| Order | Module | Version | Tuple digest | Graph selected |
|---:|---|---|---|:---:|
| 1 | `golang.org/x/mod` | `v0.25.0` | `5aede784ca073b95cc80b6499874618e272f72aa82c8eb962cd6760f705927b4` | false |
| 2 | `golang.org/x/net` | `v0.41.0` | `2a401d22df127014c8ff742d5f42744335cf0a25af2a06f85c56ba4ea9ff0ea0` | false |
| 3 | `golang.org/x/sync` | `v0.15.0` | `a5add74f06b2f0c08dacbb45eea368048c76163d74ded600875289aa447a4bc0` | false |
| 4 | `golang.org/x/sys` | `v0.33.0` | `5e519f9381da4b6cb760871dac6b372916de91736e7dd1e38e5c2d5080a3f782` | false |
| 5 | `golang.org/x/telemetry` | `v0.0.0-20240521205824-bda55230c457` | `e5b8406e7a0cdff66df0be1590c960a4547e88ce500ae60348d77aa0df1a4138` | false |

The two retained-input identity scans independently reproduce the same ordered
tuples, parent declarations, `go.mod` H1 values, module-ZIP H1 values, and
ZIP-contained `go.sum` entry count. A ready result requires five complete H1
pairs, zero blocked tuples, and zero conflicts.

Identity witness bundle:

- ZIP-contained `go.sum` entry count: 120
- parent declarations: 7
- `go.mod` H1 witnesses: 7
- module-ZIP H1 witnesses: 7
- compact identity SHA-256:
  `b9fc13d747fc092cf312ffdf4c792c078f4c79c783b2426a00388ae2f98d915b`
- full witness SHA-256:
  `92fc2c418b2cda6984f51d09a0c8f8e95633539ee1542c91a03cc679011e7ee7`
- declaration witness SHA-256:
  `4a2b642155cf4c8432e18ce200a4156e3160328dfee4512e4c4dfa6d4d74a495`
- `go.mod` H1 witness SHA-256:
  `53bdf82aee8012b86a554155ebebb20ba7dfdc731b59db522cfe57ae47d18014`
- module-ZIP H1 witness SHA-256:
  `631a648549e376d25238ff5229dcce3dce8d0c579cd5ce78774dae7ef256f064`

Retained `go.sum` evidence is not fresh checksum-database inclusion proof and
does not authorize an external checksum lookup.

## Structural acquisition preparation

The decision describes exactly ten ordered HTTPS GET request shapes:
`.mod` then ZIP for each tuple in table order. Every request uses host
`proxy.golang.org`, direct lowercase ASCII module-path encoding, a 1,048,576
byte `.mod` limit, or a 16,777,216 byte ZIP limit. Each `expectedH1` comes
from the sealed retained-input witness bundle.

Request-set canonicalization is
`utf8_unescaped_sorted_keys_compact_no_trailing_lf`; its SHA-256 is
`106a3f88983749e5272783fc7ce1293473a8dacf2e86ef7effc374707fec0d04`.

Every request keeps:

- `selectedByGraphAlgorithm=false`
- `authenticationRequired=false`
- `networkAuthorized=false`
- `acquisitionAuthorized=false`

A later one-use gate would have to independently bind all ten expected H1
values, byte limits, no-overwrite staging, atomic no-replace promotion, and
post-consumption readback. This decision reserves no namespace, performs no
request, and asks for no credentials, ownership proof, keys, signatures,
tokens, passwords, or other authentication.

## Verification and operation accounting

The direct combined-v13 run accounts for 2,644 inherited plus 342 current
graph archive opens, totaling 2,986. Two retained-input identity scans add 342
read-only archive opens, so overall decision accounting is 3,328 archive
opens. Reconstruction counts are 22 inherited plus two current, totaling 24.

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
`wave15IdentityResolved` and `wave15AcquisitionReady` become true. Even then,
`wave15AcquisitionComplete`, dependency fixed point, dependency closure,
semantic closure, rung-three completion, candidate selection, library
selection, and release readiness remain false.

The next bounded action is only preparation of a separate one-use
ten-resource Wave15 acquisition permit checker, runner, and tests. That
later action requires a distinct decision and is not authorized by this
document.
