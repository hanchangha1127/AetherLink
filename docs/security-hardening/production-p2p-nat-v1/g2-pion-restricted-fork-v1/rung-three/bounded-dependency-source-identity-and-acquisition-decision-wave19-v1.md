# Wave19 bounded dependency identity and acquisition decision v1

Date: 2026-07-28

Status: the verified combined-v17 result fixes two exact non-selected
frontier tuples. This verification-only decision records their retained
metadata identities and four future proxy request shapes. It grants no
acquisition, networking, execution, publication, authentication, owner proof,
user-action, filesystem-write, source-load, or compilation authority. No
Wave19 acquisition has run.

## Direct predecessor

The direct predecessor is the verified read-only combined-v17 candidate:

- checker raw SHA-256:
  `32df9bd1bf9b4b6610a2a74038956eab7e51c506198c11f45fa5058968caacb8`
- checker normalized SHA-256:
  `d2ebef7f9aad384b08a68c438320de882d640a859a7d35521853818afbcdd7ce`
- tests raw SHA-256:
  `3403ec05b1f6a9561a74a44b001352230d0d68db72789403f6155785f01588f0`
- candidate content SHA-256:
  `1267edbe7f1a4f2554808376f67c6ba25a9217db0e6e2cc80a0822d780710f78`
- combined input-set SHA-256:
  `79f2c8e28daf3f46c97d827cdc7416b77905eea49bc482911f8d234e0de3765f`
- source-bindings SHA-256:
  `72c1253423412744380ed5c7f8b74f9d5b34daaefd05caf5b384d9bb55589490`
- graph SHA-256:
  `cc748b6a5285321d8e74abab1c881dbc5ffd4433865ba9c75e459152f459092e`
- frontier SHA-256:
  `4a7998ef0c1e5716640cccf9c5b349e92124bd787a2ca4090e3ba0920b68b006`

Combined-v17 binds 365 retained source inputs: one root archive, 182 external
`go.mod` files, and 182 dependency archives. Its exact held inventory contains
375 paths after seven Wave18 terminal controls and three auxiliary evidence
files are included. It records 32 cumulative full-source reconstructions and
4,422 cumulative graph archive opens. Its exact frontier contains two tuples
and `fixedPointReached=false`. This
Wave19 checker binds those verified seals without importing, compiling,
executing, or invoking the V17 checker and without reconstructing dependency
source.

The checker independently projects the two local tuple constants into the
exact five-field V17 frontier shape: `acquisitionAuthorized=false`, `module`,
`requiresSeparateWaveDecision=true`, `selectedByGraphAlgorithm=false`, and
`version`. It hashes that ordered projection as canonical sorted-key compact
JSON with one trailing LF and requires the result to equal the pinned V17
frontier SHA-256.

The completed Wave18 namespace anchor is
`build/offline-source/pion-ice-v4.3.0/dependencies/.wave-18-v1.claim`, raw
SHA-256
`08f5134ce03805e512c2dec0dee13251ce682d793d2b87f7f8e29f6d3426d362`.
The namespace check is point-in-time only.

## Exact frontier identity

`selectedByGraphAlgorithm=false` is a graph fact, not an authority selector.
The two tuples remain version-specific graph vertices and require a separate
decision:

| Order | Module | Version | Graph selected |
|---:|---|---|:---:|
| 1 | `golang.org/x/crypto` | `v0.38.0` | false |
| 2 | `golang.org/x/text` | `v0.25.0` | false |

The retained `golang.org/x/net@v0.40.0` metadata supplies one parent
declaration and one exact H1 pair for each tuple:

| Module | `go.mod` H1 | Module ZIP H1 |
|---|---|---|
| `golang.org/x/crypto@v0.38.0` | `h1:MvrbAqul58NNYPKnOra203SB9vpuZW0e+RRZV+Ggqjw=` | `h1:jt+WWG8IZlBnVbomuhg2Mdq0+BBQaHbtqHEFEigjUV8=` |
| `golang.org/x/text@v0.25.0` | `h1:WEdwpYrmk1qmdHvhkSTNPm3app7v4rsT8F2UD6+VHIA=` | `h1:qVyWApTSYLk/drJRO5mDlNYskwQznZmkpV2c8q9zls4=` |

The checker reads the exact retained x/net `go.mod` and only its
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

The decision describes four ordered HTTPS GET shapes: `.mod`, then ZIP, for
each tuple in the table order. All target `proxy.golang.org`, carry one exact
retained H1 value, and keep authentication, networking, and acquisition
authority false. Expected accepted files are:

- `001-a26a2513c9f4c49c479c.mod`
- `001-a26a2513c9f4c49c479c.zip`
- `002-c6022d5be99f60f2428e.mod`
- `002-c6022d5be99f60f2428e.zip`

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
checker, decision, reader, V17 checker, V17 tests, Wave18 namespace anchor,
retained x/net `go.mod`, then retained x/net ZIP. The adversarial tests pin
the checker's exact import surface and its complete AST call count and digest;
same-call-count `runpy`, `io.open`, `os.write`, and path-write substitutions
are rejected.

Only after the package seals and both metadata scans agree may
`wave19IdentityResolved` and `wave19AcquisitionReady` be true. Wave19
acquisition completion, dependency fixed point, dependency closure, semantic
closure, rung-three completion, candidate selection, library selection, and
release readiness remain false.

The next bounded action is independent review of this decision package. It
does not authorize an acquisition permit, runner, or network operation.
