# Wave10 bounded dependency identity and acquisition decision v1

Date: 2026-07-26

Status: eleven exact frontier identities are complete and structurally ready
for a later acquisition permit. This decision does not authorize acquisition.

## Direct predecessor

The direct predecessor is the pinned combined-v8 candidate. Its bindings are:

- checker raw SHA-256:
  `798a055a9a4c3957c0edd75ecbad35f0cfa9f17bf39e63cd262876dcb6103e32`
- checker normalized SHA-256:
  `cfd83cdd00b6daee857cbff915ec48fd78390bbf06098ccab963a54e8748ba4b`
- tests raw SHA-256:
  `347a1e0083d2daedb40deba5fca491b63ee3137b5a7c18a56886be694ded16a0`
- candidate content SHA-256:
  `f9f683d3afbe65a77626577428c0f9ce94219e39529d0c5811b49172c51e3b37`
- combined input-set SHA-256:
  `030743c3959a6e7466385e9f89255fcb03d65576676a1e5cd7e5e2929e9f6339`
- source-bindings SHA-256:
  `a5ae07cb68ea3f0e080094b8168aa36c67715ed44824220dd4c7a94cd0f9192b`
- graph SHA-256:
  `721d045a10cdf015e865a84db7026115ac63462217dbb5349504fed9f1bae7b7`
- frontier SHA-256:
  `780501bca37fbeb953590004ca7e5aad7f206083f749b920e2a9842b63675f82`

Combined-v8 retains 277 source bindings: one root archive, 138 external
`go.mod` files, and 138 dependency archives. It records fourteen cumulative
full-source reconstructions and 1,366 cumulative graph archive opens. Its
Wave9 legacy-build compatibility policy was applied exactly four times.
V7 test bytes remain historical metadata only and are not a live-held V8
tool input. The retained Wave9 boundary binds the historical exact 38-file
snapshot and explicitly does not claim continuous current-path identity.

The predecessor namespace anchor
`build/offline-source/pion-ice-v4.3.0/dependencies/.wave-9-v1.claim`
has raw SHA-256
`84957554fe937841165f38a2418613e4e740082bea4f55538b21324dfe6d45f4`.
The Wave10 claim, staging, and accepted namespaces were absent before and
after the bounded decision observation.

## Exact frontier identity

`selectedByGraphAlgorithm` is a graph fact, not an authority selector. The
frontier contains one selected and ten non-selected version vertices. Every
acquisition, authentication, network, execution, and write selector remains
false.

| Order | Module | Version | Graph selected | `go.mod` H1 | Module ZIP H1 | Declarations | `go.mod` witnesses | ZIP witnesses |
|---:|---|---|:---:|---|---|---:|---:|---:|
| 1 | `golang.org/x/crypto` | `v0.42.0` | false | `h1:4+rDnOTJhQCx2q7/j6rAN5XDw8kPjeaXEUR2eL94ix8=` | `h1:chiH31gIWm57EkTXpwnqf8qeuMUi0yekh6mT2AvFlqI=` | 2 | 2 | 2 |
| 2 | `golang.org/x/net` | `v0.0.0-20190620200207-3b0461eec859` | false | `h1:z5CRVTTTmAJ677TzLLGU+0bjPO0LkuOLi4/5GtJWs/s=` | `h1:R/3boaszxrf1GEUWTVDzSKVwLmSJpwZ1yqXm8j0v2QI=` | 1 | 14 | 1 |
| 3 | `golang.org/x/net` | `v0.0.0-20210226172049-e18ecbb05110` | false | `h1:m0MpNAwzfU5UDzcl9v0D8zg8gWTRqZa9RBIspLL5mdg=` | `h1:qWPm9rbaAMKs8Bq/9LRpbMqxWRVUAQwMI9fVrssnTfw=` | 1 | 14 | 1 |
| 4 | `golang.org/x/sync` | `v0.0.0-20190423024810-112230192c58` | false | `h1:RxMgew5VJxzue5/jJTE5uejpjVlOe/izrB70Jof72aM=` | `h1:8gQV6CLnAEikrhgkHFbMAEhagSSnXWGV915qUMm9mrU=` | 1 | 14 | 1 |
| 5 | `golang.org/x/sys` | `v0.0.0-20210615035016-665e8c7367d1` | false | `h1:oPkhp1MJrh7nUepCBck5+mAzfO9JrbApNNgaTdGDITg=` | `h1:SrN+KX8Art/Sf4HNj6Zcz06G7VEz+7w9tdXTPOZ7+l4=` | 2 | 16 | 2 |
| 6 | `golang.org/x/term` | `v0.0.0-20201126162022-7de9c90e9dd1` | false | `h1:bj7SfCRtBDWHUb9snDiAeCFNEtKQo2Wmx5Cou7ajbmo=` | `h1:v+OssWQX+hTHEmOBgwxdZxK4zHq3yOs8F9J7mk0PY8E=` | 1 | 14 | 1 |
| 7 | `golang.org/x/term` | `v0.35.0` | false | `h1:TPGtkTLesOwf2DE8CgVYiZinHAOuy5AYUYT1lENIZnA=` | `h1:bZBVKBudEyhRcajGcNc3jIfWPqV4y/Kt2XcoigOWtDQ=` | 2 | 2 | 2 |
| 8 | `golang.org/x/text` | `v0.29.0` | false | `h1:7MhJOA9CD2qZyOKYazxdYMF85OwPdEr9jTtBpO7ydH4=` | `h1:1neNs90w9YzJ9BocxfsQNHKuAT4pkghyXc4nhZ6sJvk=` | 2 | 2 | 2 |
| 9 | `golang.org/x/text` | `v0.3.3` | false | `h1:5Zoc/QRtKVWzQhOtBMvqHzDpF6irO9z98xDceosuGiQ=` | `h1:cokOdA+Jmi5PJGXLlLllQSgYigAEfHXJAERHVMaCc2k=` | 1 | 14 | 1 |
| 10 | `golang.org/x/tools` | `v0.36.0` | false | `h1:WBDiHKJK8YgLHlcQPYQzNCkUxUypCaa5ZegCVutKm+s=` | `h1:kWS0uv/zsvHEle1LbV5LE8QujrxB3wfQyxHfhOk0Qkg=` | 1 | 1 | 1 |
| 11 | `golang.org/x/xerrors` | `v0.0.0-20190717185122-a985d3407aa7` | true | `h1:I/5z698sn9Ka8TeJc9MKroUUfqBBauWjQqLJ2OPfmY0=` | `h1:9zdDQZ7Thm29KFXgAX/+yaf3eVbP7djjWp/dXAppNCc=` | 1 | 14 | 1 |

The selected `x/xerrors` vertex is traceable to the retained Wave9 accepted
module metadata. It remains a graph observation and grants no authority.

Both scans reproduced:

- 97 ZIP-contained `go.sum` entries;
- 15 parent declarations;
- 107 `go.mod` H1 witnesses;
- 15 module-ZIP H1 witnesses;
- eleven complete H1 pairs, zero blocked tuples, and zero conflicts.

The witness bindings are:

- compact identity:
  `ae82fa0383b6492de66add1ceaffefffff51dcbe1c3ad856399ce03152067bb0`
- full witness:
  `89a1e5a1b16c01fcbfac6720f5ad9477416eb43d2c9c3a7121f60ad030cfe715`
- declaration witness:
  `a6f34fa9bc8df72a74feea7492e3afcc4a0627c35330ff518c8b81b4048f08d6`
- `go.mod` H1 witness:
  `00592de40ea011961e64795e17b7e31d6df529550851cf53418336b74337763b`
- module-ZIP H1 witness:
  `14edfb3abe3c0c8fd93806bf1cf6c3078f841f870f026c610dff6e4595ef04ff`

## Structural acquisition preparation

The decision describes exactly 22 ordered GET request shapes, `mod` then
`zip` for each tuple. Their canonical SHA-256 is
`cf6a97651565b55bb714a713e66e6a452f7132973ce21ced254bd0d728d12a89`.
Each request preserves its graph-selected fact while
`authenticationRequired=false`, `networkAuthorized=false`, and
`acquisitionAuthorized=false`.

The later one-use gate must independently bind byte limits, no-overwrite
staging, atomic no-replace promotion, and post-consumption readback. This
decision reserves no namespace and performs no request.

## Operation and authority boundary

The direct combined-v8 run accounts for 1,088 inherited plus 278 current
graph archive opens, totaling 1,366. Two identity scans add 278 read-only
archive opens, so the overall bounded decision accounting is 1,644 archive
opens. The reconstruction counts are twelve inherited plus two current,
totaling fourteen.

Network, subprocess, authentication, source acquisition, archive extraction,
dependency-source loading, execution, compilation, filesystem write, Git
write, publication, and socket operation counts are all zero. No password,
private key, signature, token, repository-owner proof, external
authentication, or user action is required.

Dependency fixed point, dependency closure, semantic closure, rung-three
completion, candidate selection, library selection, and release readiness all
remain false. The next bounded action is a separate one-use 22-resource
Wave10 acquisition permit checker, runner, and tests.
