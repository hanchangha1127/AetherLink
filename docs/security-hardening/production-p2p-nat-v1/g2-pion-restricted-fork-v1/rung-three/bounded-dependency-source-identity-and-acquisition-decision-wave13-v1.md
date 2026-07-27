# Wave13 bounded dependency identity and acquisition decision v1

Date: 2026-07-27

Status: the authoritative combined-v11 result fixes four exact non-selected
frontier tuples. The checker pins the retained-input witness bundle and
resulting eight-request set. Successful bounded verification reports four
complete identity pairs, zero blocked tuples, zero conflicts, and structural
acquisition readiness without granting acquisition, networking, execution,
publication, authentication, or user action authority.

## Direct predecessor

The direct predecessor is the exact pinned read-only combined-v11 candidate:

- checker raw SHA-256:
  `d330a2f7dd4f12bd4f972e6c34749e10701c594cad75308ccc7de4d3e6aba176`
- checker normalized SHA-256:
  `1ef7c9fb874c33b8b25c02f0024e6d85e3df070718c0de9861c60173697af82e`
- tests raw SHA-256:
  `7d753c0406210ca7e7bb07905533084fdba8a5ed626d23d913211021c719e922`
- candidate content SHA-256:
  `1976ed89f18f28b0b3440a693581f171bdd574bc615f2054bea2cba1cf85b837`
- combined input-set SHA-256:
  `124995740eb0d95e83c77f078a334bd55ac491a14453098fa70da26cf52d6caa`
- source-bindings SHA-256:
  `504b3ed2a6182db6464c93999c3bd073381ee181c7238ca62da5afd2ca87269f`
- graph SHA-256:
  `b4b0ec50d5538e80de93e89574249ca0d49b411443ebd2c78827928704b0a44d`
- frontier SHA-256:
  `3528abe3579eb1d06ba01f66f56002a6e193fe1e25e233f03eab9b8ac3e4fc32`

Combined-v11 holds 325 source bindings: one root archive, 162 external
`go.mod` files, and 162 dependency archives. The aggregate retained-input raw
size is 302,389,009 bytes. It records twenty cumulative full-source
reconstructions and 2,310 cumulative graph archive opens. Its fixed-point flag
is false and its exact frontier count is four.

V10 test bytes remain historical metadata within the V11 candidate and are
not a live held input through that historical field. The Wave13 checker must
instead live-hold the exact V11 checker and V11 test bytes as direct
predecessor inputs. The verification path executes only the exact pinned V11
checker to reconstruct its candidate; it does not execute the V11 tests or any
dependency source, and it does not treat held tool bytes as approval.

The predecessor namespace anchor is
`build/offline-source/pion-ice-v4.3.0/dependencies/.wave-12-v1.claim` at raw
SHA-256
`58145cf6660a9a6c3ed5ab36ec4f38df388e88d10c5a1e6820ca9416f06b8280`.
The materialized decision must retain that exact path and digest.

The verifier must take two bounded namespace snapshots and prove that the
Wave13 claim, staging, accepted, acquisition, and readback namespaces are
absent. The only allowed Wave13 decision namespace entries are this reader,
its JSON decision, its checker, and its tests. This is a point-in-time
verification requirement, not a namespace reservation.

## Exact frontier identity

`selectedByGraphAlgorithm` is a graph fact, not an authority selector. All four
rows are non-selected, require a separate wave decision, and keep acquisition
authority false.

| Order | Module | Version | Tuple digest | Graph selected |
|---:|---|---|---|:---:|
| 1 | `golang.org/x/mod` | `v0.26.0` | `867b3d6651ab1a03a470388fe892e2325b9fde01fd016dc7324042e7553c66c7` | false |
| 2 | `golang.org/x/net` | `v0.42.0` | `ca3882149832dac56a857d5fe673afc9b2db1c1743a0d9b87090e613b3c4eb37` | false |
| 3 | `golang.org/x/sys` | `v0.34.0` | `affb7f9946408283a16effdf19c1513912abe16800ddb6067f06b8833e9207eb` | false |
| 4 | `golang.org/x/telemetry` | `v0.0.0-20250710130107-8d8967aff50b` | `afa9b13f01de51bd6d80ea164e14703998c239757028ac1e75c291e2a28b63c6` | false |

The two retained-input identity scans must independently reproduce the same
ordered tuples, parent declarations, `go.mod` H1 values, module-ZIP H1 values,
and ZIP-contained `go.sum` entry count. A ready result requires four complete
H1 pairs, zero blocked tuples, and zero conflicts.

Identity witness bundle (`go.sum` count, compact identity, full witness,
declaration witness, `go.mod` H1 witness, and module-ZIP H1 witness):

- ZIP-contained `go.sum` entry count: 113
- parent declarations: 6
- `go.mod` H1 witnesses: 6
- module-ZIP H1 witnesses: 6
- compact identity SHA-256:
  `7e43930dc1781385959cdfa3812f43be4e7e922bb1ed5f078ae9bf3f4a25da87`
- full witness SHA-256:
  `22c1051a0d0ce5a31018a2b4e61fb5599849123700f1e07a886f34e509da9074`
- declaration witness SHA-256:
  `1ea6370aeedfa6838947b2f9babaabe584f7115bc4be683ce061451930a185b1`
- `go.mod` H1 witness SHA-256:
  `392c6dbcd4301a32b5fb9f278dc1718efb34899c14d9a5ab382fedc73aa6c1e7`
- module-ZIP H1 witness SHA-256:
  `4751c6aff2d3fd0426bcb9210679299215bd46d3f2784bbea52c2ae5123bc3fd`

Retained `go.sum` evidence is not fresh checksum-database inclusion proof and
does not authorize an external checksum lookup.

## Structural acquisition preparation

The decision describes exactly eight ordered HTTPS GET request shapes:
`.mod` then ZIP for each tuple in table order. Every request uses host
`proxy.golang.org`, direct lowercase ASCII module-path encoding, a 1,048,576
byte `.mod` limit, or a 16,777,216 byte ZIP limit. Each `expectedH1` must come
from the sealed retained-input witness bundle.

Request-set canonicalization is
`utf8_unescaped_sorted_keys_compact_no_trailing_lf`; its SHA-256 is
`eae1bb0f8645a5d698bfe50fae505a1c7d6887c78c9dcc3b088939b97e0ffce1`.

Every request keeps:

- `selectedByGraphAlgorithm=false`
- `authenticationRequired=false`
- `networkAuthorized=false`
- `acquisitionAuthorized=false`

A later one-use gate would have to independently bind all eight expected H1
values, byte limits, no-overwrite staging, atomic no-replace promotion, and
post-consumption readback. This decision reserves no namespace, performs no
request, and does not ask the user for credentials, ownership proof, keys,
signatures, tokens, passwords, or any other authentication.

## Verification and operation accounting

The direct combined-v11 run accounts for 1,984 inherited plus 326 current
graph archive opens, totaling 2,310. Two retained-input identity scans add 326
read-only archive opens, so overall decision accounting is 2,636 archive
opens. Reconstruction counts are eighteen inherited plus two current,
totaling twenty.

This package is verification-only. It exposes no record mode, acquisition
mode, runner mode, or state-mutating materialization mode. Dependency source is
not acquired. Archive-extraction and dependency-source load, execution, and
compilation counters are zero. Network, product-runtime network, socket,
subprocess, authentication, and filesystem-write counters are zero. DNS,
acquisition, Git write, and publication remain unauthorized.

The materialized decision must bind the checker normalized bytes, checker-test
raw bytes, and this reader's raw bytes. Those byte identities are validated by
the pinned checker rather than copied into this self-referential reader.

## Closed authority and completion boundary

The materialized authority object must keep all authority and user-input
fields false, including:

- `acquisitionAuthorityGranted=false`
- `authenticationRequired=false`
- `compileAuthorized=false`
- `decisionAuthorityGranted=false`
- `dependencySourceExecutionAuthorized=false`
- `dnsAuthorized=false`
- `executionAuthorityGranted=false`
- `externalAuthenticationRequired=false`
- `fileWriteAuthorized=false`
- `filesystemExtractionAuthorized=false`
- `gitWriteAuthorized=false`
- `networkAuthorized=false`
- `passwordRequired=false`
- `privateKeyRequired=false`
- `publicationAuthorityGranted=false`
- `repositoryOwnerIdentityProofRequired=false`
- `signatureRequired=false`
- `socketAuthorized=false`
- `sourceLoadOrExecutionAuthorized=false`
- `subprocessAuthorized=false`
- `tokenRequired=false`
- `userActionRequired=false`

Only after the independent identity scans and package seal agree may
`wave13IdentityResolved` and `wave13AcquisitionReady` become true. Even then,
`wave13AcquisitionComplete`, dependency fixed point, dependency closure,
semantic closure, rung-three completion, candidate selection, library
selection, and release readiness remain false.

The next bounded action is only preparation of a separate one-use
eight-resource Wave13 acquisition permit checker, runner, and tests. That
later action requires a distinct decision and is not authorized by this
document.
