# Wave18 bounded dependency identity and acquisition decision v1

Date: 2026-07-28

Status: the verified combined-v16 result fixes three exact non-selected
frontier tuples. This verification-only decision records their retained
metadata identities and six future proxy request shapes. It grants no
acquisition, networking, execution, publication, authentication, owner proof,
user-action, filesystem-write, source-load, or compilation authority. No
Wave18 acquisition has run.

## Direct predecessor

The direct predecessor is the verified read-only combined-v16 candidate:

- checker raw SHA-256:
  `2e388d466c5346fa6f82b7fd23fa6dca24009acadacdd62f1fe2ba25b0a10879`
- checker normalized SHA-256:
  `7dd2c81a2032a374192f7c502afc65305d97f7c1e3699654e416b60bf64c6bd5`
- tests raw SHA-256:
  `15cf4d56a68b9f0cfd61554b24e781357066b27e63c90c871dfb0cde19c80889`
- candidate content SHA-256:
  `90928eb85eded2938b25a0beec82c00ebcd69147bf92733bc65a528d26c00e03`
- combined input-set SHA-256:
  `15705de20633cdf4bf473c82a634136f481a2c131e7960a0a6cbdeccf10397a7`
- source-bindings SHA-256:
  `401a3e85faacc150944d883495fca4b22e4cac1933c0308aedaec228a7c872ea`
- graph SHA-256:
  `db7e36664afd819c72e9c9916bd7053782282954ed4f359c550b7972b74147a2`
- frontier SHA-256:
  `fe15a3ea57682b276a6f11a2c2fd998d9120640fac40038fc9c1f100e50750b5`

Combined-v16 binds 359 retained inputs: one root archive, 179 external
`go.mod` files, and 179 dependency archives. It records 30 cumulative
full-source reconstructions and 4,056 cumulative graph archive opens. Its
exact frontier contains three tuples and `fixedPointReached=false`. This
Wave18 checker binds those verified seals without importing, compiling,
executing, or invoking the V16 checker and without reconstructing dependency
source.

The checker independently projects the three local tuple constants into the
exact five-field V16 frontier shape: `acquisitionAuthorized=false`, `module`,
`requiresSeparateWaveDecision=true`, `selectedByGraphAlgorithm=false`, and
`version`. It hashes that ordered projection as canonical sorted-key compact
JSON with one trailing LF and requires the result to equal the pinned V16
frontier SHA-256.

The completed Wave17 namespace anchor is
`build/offline-source/pion-ice-v4.3.0/dependencies/.wave-17-v1.claim`, raw
SHA-256
`3090e729d99c46c4b4d1e4242d6f25c08e2345062dfb6c15e1e87d3edf632fad`.
The namespace check is point-in-time only.

## Exact frontier identity

`selectedByGraphAlgorithm=false` is a graph fact, not an authority selector.
The three tuples remain version-specific graph vertices and require a separate
decision:

| Order | Module | Version | Graph selected |
|---:|---|---|:---:|
| 1 | `golang.org/x/mod` | `v0.24.0` | false |
| 2 | `golang.org/x/net` | `v0.40.0` | false |
| 3 | `golang.org/x/sync` | `v0.14.0` | false |

The retained `golang.org/x/tools@v0.33.0` metadata supplies one parent
declaration and one exact H1 pair for each tuple:

| Module | `go.mod` H1 | Module ZIP H1 |
|---|---|---|
| `golang.org/x/mod@v0.24.0` | `h1:IXM97Txy2VM4PJ3gI61r1YEk/gAj6zAHN3AdZt6S9Ww=` | `h1:ZfthKaKaT4NrhGVZHO1/WDTwGES4De8KtWO0SIbNJMU=` |
| `golang.org/x/net@v0.40.0` | `h1:y0hY0exeL2Pku80/zKK7tpntoX23cqL3Oa6njdgRtds=` | `h1:79Xs7wF06Gbdcg4kdCCIQArK11Z1hr5POQ6+fIYHNuY=` |
| `golang.org/x/sync@v0.14.0` | `h1:1dzgHSNfp02xaA81J2MS99Qcpr2w7fw1gpm99rleRqA=` | `h1:woo0S4Yywslg6hp4eUFjTVOyKt0RookbpAHG4c1HmhQ=` |

The checker reads the exact retained x/tools `go.mod` and only its
ZIP-contained `go.sum` metadata twice. It does not inspect or reconstruct
dependency source code. Retained H1 evidence is not fresh checksum-database
inclusion proof and does not authorize an external checksum lookup.
For each exact tuple, the complete matching parent-declaration set must be
exactly the one expected line, and each complete matching `go.sum` module-ZIP
and `/go.mod` H1 set must likewise contain exactly one expected line. An
additional conflicting H1 or alternate declaration fails closed.
Matching is performed on nonempty logical whitespace tokens, not an
exact-space prefix. Tabs and repeated spaces therefore cannot hide a second
target row; even a whitespace-varied duplicate carrying the same H1 violates
the singleton requirement.

## Structural acquisition preparation

The decision describes six ordered HTTPS GET shapes: `.mod`, then ZIP, for
each tuple in the table order. All target `proxy.golang.org`, carry one exact
retained H1 value, and keep authentication, networking, and acquisition
authority false. Expected accepted files are:

- `001-bb2025870bcef7a0c287.mod`
- `001-bb2025870bcef7a0c287.zip`
- `002-3c84a9eecca520aed886.mod`
- `002-3c84a9eecca520aed886.zip`
- `003-4615480e24f0c4184e4c.mod`
- `003-4615480e24f0c4184e4c.zip`

This decision creates no permit or runner, reserves no namespace, performs no
request, and asks for no credentials, ownership proof, keys, signatures,
tokens, passwords, or other authentication. A later separately reviewed
one-use gate would be required before any acquisition.

## Verification accounting and boundary

The checker performs metadata-only retained reads and namespace observations.
It performs no source reconstruction, source extraction, source loading,
source execution, compilation, network, socket, subprocess, authentication,
filesystem write, archive extraction to disk, Git write, or product-runtime
operation.

Its live descriptor set is bound to exactly eight paths in a fixed order:
checker, decision, reader, V16 checker, V16 tests, Wave17 namespace anchor,
retained x/tools `go.mod`, then retained x/tools ZIP. The adversarial tests pin
the checker's exact import surface and its complete AST call count and digest;
same-call-count `runpy`, `io.open`, `os.write`, and path-write substitutions
are rejected.

Only after the package seals and both metadata scans agree may
`wave18IdentityResolved` and `wave18AcquisitionReady` be true. Wave18
acquisition completion, dependency fixed point, dependency closure, semantic
closure, rung-three completion, candidate selection, library selection, and
release readiness remain false.

The next bounded action is independent review of this decision package. It
does not authorize an acquisition permit, runner, or network operation.
