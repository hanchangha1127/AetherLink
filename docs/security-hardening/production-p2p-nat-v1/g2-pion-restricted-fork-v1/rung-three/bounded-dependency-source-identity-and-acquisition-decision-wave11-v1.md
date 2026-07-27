# Wave11 bounded dependency identity and acquisition decision v1

Date: 2026-07-26

Status: nine exact frontier identities are complete and structurally ready for
a later acquisition-permit decision. This document does not authorize
acquisition, networking, execution, or publication.

## Direct predecessor

The direct predecessor is the exact pinned combined-v9 candidate:

- checker raw SHA-256:
  `c0f098cf0a047c4d1aca03f5b7f16f327306b56ed8e656d67afe32503eb117da`
- checker normalized SHA-256:
  `b4cdbfd385e0606fa2ca37017983bd80b6856dd69dfafb46df6579e76c618684`
- tests raw SHA-256:
  `fca6a0ca437356185d287816bcfaf5e110794207b3413addf95e9eb24038c217`
- candidate content SHA-256:
  `9c9e995f853a8dbbc07d55d41ce1c5660cb616d879b3565803e13b6aaf4532ba`
- combined input-set SHA-256:
  `5a08d28573b68ddd031eff34a8b6afad8f7cd9e01966f4516c22a410bbb51b71`
- source-bindings SHA-256:
  `2455ab16e4c1dd6a68127c38f25d49275d9ef955d4d12ad711d644f0d745839f`
- graph SHA-256:
  `4367fc6c4c5efb69f948d8e040c2cfa496345102631719692d31feabb794a6b5`
- frontier SHA-256:
  `171af951e3a67405b62ddceface1341bb6f64b08f370d3d216ede541bd011f06`

Combined-v9 holds 299 source bindings: one root archive, 149 external
`go.mod` files, and 149 dependency archives. It records sixteen cumulative
full-source reconstructions and 1,666 cumulative graph archive opens. V8 test
bytes remain historical metadata within the V9 candidate; this Wave11 checker
separately live-holds the exact V9 checker and V9 test bytes.

The predecessor namespace anchor is
`build/offline-source/pion-ice-v4.3.0/dependencies/.wave-10-v1.claim` at raw
SHA-256
`5260f5d7e7473013871573717848a3e8eae868a47ab2bfe538340d681ec4a6de`.
The Wave11 claim, staging, accepted, acquisition, and readback namespaces are
absent at both bounded namespace snapshots.

## Exact frontier identity

`selectedByGraphAlgorithm` is a graph fact, not an authority selector. All
nine rows are non-selected, require a separate wave decision, and keep
acquisition authority false.

| Order | Module | Version | Graph selected | `go.mod` H1 | Module ZIP H1 | Declarations | `go.mod` witnesses | ZIP witnesses |
|---:|---|---|:---:|---|---|---:|---:|---:|
| 1 | `golang.org/x/crypto` | `v0.0.0-20190308221718-c2843e01d9a2` | false | `h1:djNgcEr1/C05ACkg1iLfiJU5Ep61QUkGW8qpdssI0+w=` | `h1:VklqNMn3ovrHsnt90PveolxSbWFaJdECFbxSq0Mqo2M=` | 1 | 15 | 1 |
| 2 | `golang.org/x/mod` | `v0.27.0` | false | `h1:rWI627Fq0DEoudcK+MBkNkCe0EetEaDSwJJkCcjpazc=` | `h1:kb+q2PyFnEADO2IEF935ehFUXlWiNjJWtRNgBLSfbxQ=` | 2 | 2 | 2 |
| 3 | `golang.org/x/net` | `v0.43.0` | false | `h1:vhO1fvI4dGsIjh73sWfUVjj3N7CA9WkKJNQm2svM6Jg=` | `h1:lat02VYK2j4aLzMzecihNvTlJNQUq316m2Mr9rnM6YE=` | 2 | 2 | 2 |
| 4 | `golang.org/x/sync` | `v0.16.0` | false | `h1:1dzgHSNfp02xaA81J2MS99Qcpr2w7fw1gpm99rleRqA=` | `h1:ycBJEhp9p4vXvUZNszeOq0kGTPghopOL8q0fq3vstxw=` | 1 | 1 | 1 |
| 5 | `golang.org/x/sys` | `v0.0.0-20190215142949-d0b11bdaac8a` | false | `h1:STP8DvDyc/dI5b8T5hshtkjS+E42TnysNCUPdjciGhY=` | `h1:1BGLXjeY4akVXGgbC9HugT3Jv3hCI0z56oJR5vAMgBU=` | 1 | 15 | 2 |
| 6 | `golang.org/x/sys` | `v0.0.0-20201119102817-f84b799fce68` | false | `h1:h1NjWce9XRLGQEsW7wpKNCjG9DtNlClVuFLEZdDNbEs=` | `h1:nxC68pudNYkKU6jWhgrqdreuFiOQWj1Fs7T3VrH4Pjw=` | 2 | 16 | 2 |
| 7 | `golang.org/x/sys` | `v0.35.0` | false | `h1:BJP2sWEmIv4KK5OTEluFJCKSidICx8ciO85XgH3Ak8k=` | `h1:vz1N37gP5bs89s7He8XuIYXpyY0+QlsKmzipCbUtyxI=` | 1 | 1 | 1 |
| 8 | `golang.org/x/telemetry` | `v0.0.0-20250807160809-1a19826ec488` | false | `h1:fGb/2+tgXXjhjHsTNdVEEMZNWA0quBnfrO+AfoDSAKw=` | `h1:3doPGa+Gg4snce233aCWnbZVFsyFMo/dR40KK/6skyE=` | 1 | 1 | 1 |
| 9 | `golang.org/x/text` | `v0.3.0` | false | `h1:NqM8EUOU14njkJ3fqMW+pc6Ldnwhi/IjpwHt7yyuwOQ=` | `h1:g61tztE5qeGQ89tm6NTjjM9VPIm088od1l6aSorWRWg=` | 1 | 15 | 1 |

Both scans reproduce 105 ZIP-contained `go.sum` entries, 12 parent
declarations, 68 `go.mod` H1 witnesses, 13 module-ZIP H1 witnesses, nine
complete H1 pairs, zero blocked tuples, and zero conflicts.

The witness bindings are:

- compact identity:
  `8e6e8473c3938f40dbbffb090c26a73bf965c247df33c8ead5c04341b74adbc4`
- full witness:
  `ea353c9595bbe020bd908347b9576bc7e8c820047735e768cc2d7ac37dc2713e`
- declaration witness:
  `d36a9cf52916e2f283bdb39083503b26a10b13af1a59d678b2c4629b4c66e2f2`
- `go.mod` H1 witness:
  `93e7a293f128d0fd3990ab0dc90a963182e87e8e77a48a74ce0016f840e07c8e`
- module-ZIP H1 witness:
  `8b6e4b1169bf161cc5f6481182cf25fba5c7a2cb430d6dd1575c75b902266290`

## Structural acquisition preparation

The decision describes exactly 18 ordered GET request shapes, `mod` then
`zip` for each tuple. Their canonical SHA-256 is
`bbde21b5f7a523bb6cddf78fbbbfdce46f8bcf61d60ebcec72a80d52dda50ba8`.
Every request keeps `authenticationRequired=false`,
`networkAuthorized=false`, and `acquisitionAuthorized=false`.

A later one-use gate would have to independently bind byte limits,
no-overwrite staging, atomic no-replace promotion, and post-consumption
readback. This decision reserves no namespace and performs no request.

## Operation and authority boundary

The direct combined-v9 run accounts for 1,366 inherited plus 300 current graph
archive opens, totaling 1,666. Two identity scans add 300 read-only archive
opens, so overall decision accounting is 1,966 archive opens. Reconstruction
counts are fourteen inherited plus two current, totaling sixteen.

Dependency-source acquisition, extraction, loading, execution, and compilation
are all zero. Network, subprocess, authentication, filesystem write, Git write,
publication, and socket operations are also zero. No password, private key,
signature, token, repository-owner proof, external authentication, or user
action is required.

Dependency fixed point, dependency closure, semantic closure, rung-three
completion, candidate selection, library selection, and release readiness all
remain false. The next bounded action is only preparation of a separate
one-use 18-resource Wave11 acquisition permit checker, runner, and tests.
