# Wave17 bounded dependency identity and acquisition decision v1

Date: 2026-07-27

Status: the verified combined-v15 result fixes one exact non-selected frontier
tuple, `golang.org/x/tools@v0.33.0`. This verification-only decision records
its retained metadata identity and two future proxy request shapes. It grants
no acquisition, networking, execution, publication, authentication, owner
proof, or user-action authority. No Wave17 acquisition has run.

## Direct predecessor

The direct predecessor is the verified read-only combined-v15 candidate:

- checker raw SHA-256:
  `e0a8353e5bd4f40b587c2b62c563c0b679ca5261345e577d71d00fb868f08fb5`
- checker normalized SHA-256:
  `63198050500264a07082d205172c21993a309289649a5459e1c638b53fb22bf7`
- tests raw SHA-256:
  `65d7f435cef11da2cccae7e31a3c410d7a3038f6bc3261552753801a0de431b1`
- candidate content SHA-256:
  `4666c802e40734bb1b5b91489eb24aa782cb346710caec9605be4e0e005553ee`
- combined input-set SHA-256:
  `4b12b7ca7f0a8b1556c692522e8832af033f9d2a1f00fbeb7469623a00541f1e`
- source-bindings SHA-256:
  `86512fdc6c5b8ff8b1d79e500e32c6c35c36f6c097aca5385f8ff1e06ffe18fd`
- graph SHA-256:
  `ffe9f910669401198b88752663055ca2e6622d19e171f2d20a2b303d06c989d7`
- frontier SHA-256:
  `ce1be1152aabf580a211f038d80aeaf9249418117b7d12ff26ffc909f1e4d593`

Combined-v15 binds 357 retained inputs: one root archive, 178 external
`go.mod` files, and 178 dependency archives. It records 28 cumulative
full-source reconstructions and 3,696 cumulative graph archive opens. This
Wave17 checker binds those verified seals without executing the V15 checker
or reconstructing dependency source.

The completed Wave16 namespace anchor is
`build/offline-source/pion-ice-v4.3.0/dependencies/.wave-16-v1.claim`, raw
SHA-256
`df97f5d9bf8c56f3bbf08635b8332bbc18b25babd0e5f35742fee3657555f4b8`.
The namespace check is point-in-time only.

## Exact frontier identity

`selectedByGraphAlgorithm=false` is a graph fact, not an authority selector.
The sole tuple requires a separate decision and keeps acquisition authority
false:

| Local | Global | Module | Version | Graph selected |
|---:|---:|---|---|:---:|
| 1 | 179 | `golang.org/x/tools` | `v0.33.0` | false |

The retained `golang.org/x/text@v0.26.0` metadata supplies one parent
declaration and the exact H1 pair:

| Resource | H1 |
|---|---|
| `go.mod` | `h1:CIJMaWEY88juyUfo7UbgPqbC8rU2OqfAV1h2Qp0oMYI=` |
| module ZIP | `h1:4qz2S3zmRxbGIhDIAgjxvFutSvH5EfnsYrRBj0UI0bc=` |

The checker reads the exact retained x/text `go.mod` and its ZIP-contained
`go.sum` metadata twice. It does not inspect or reconstruct dependency source
code. Retained H1 evidence is not fresh checksum-database inclusion proof and
does not authorize an external checksum lookup.

## Structural acquisition preparation

The decision describes two ordered HTTPS GET shapes: `.mod`, then ZIP. Both
target `proxy.golang.org`, carry the exact retained H1 value, and keep
authentication, networking, and acquisition authority false. Expected
accepted files are:

- `001-8bd04ea612cec9787131.mod`
- `001-8bd04ea612cec9787131.zip`

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

Only after the package seals and both metadata scans agree may
`wave17IdentityResolved` and `wave17AcquisitionReady` be true. Wave17
acquisition completion, dependency fixed point, dependency closure, semantic
closure, rung-three completion, candidate selection, library selection, and
release readiness remain false.

The next bounded action is independent review of this decision package. It
does not authorize an acquisition permit, runner, or network operation.

