# Wave7 Dependency Identity and Acquisition Decision

Status: the exact 15-tuple Wave7 frontier is identity-complete and
acquisition-ready, but this decision grants no acquisition or execution
authority.

## Scope

The pinned combined-v5 checker reconstructed the retained root ZIP, 99
external `go.mod` files, and 99 dependency ZIPs and produced a non-fixed
15-tuple frontier. The Wave7 decision checker independently scans all 199
retained inputs twice. Each scan reads parent declarations from the root and
external `go.mod` bytes and searches every ZIP-contained `go.sum`. It does not
extract, load, execute, or compile dependency source.

Both scans produced the same 18 parent-declaration witnesses, 41 `go.mod` H1
witnesses, and 20 module-ZIP H1 witnesses. All 15 identity pairs are complete;
there are no missing or conflicting H1 values. Every graph selector is
`false`.

The retained `go.sum` witnesses are deterministic held evidence, not fresh
checksum-database inclusion proofs.

## Exact Wave7 tuples

| Order | Module | Version | `go.mod` H1 | module ZIP H1 |
|---:|---|---|---|---|
| 1 | `github.com/stretchr/testify` | `v1.7.1` | `h1:6Fq8oRcR53rry900zMqJjRRixrwX3KX962/h/Wwjteg=` | `h1:5TQK59W5E3v0r2duFAb7P95B6hEeOyEnHRa8MjYSMTY=` |
| 2 | `golang.org/x/crypto` | `v0.13.0` | `h1:y6Z2r+Rw4iayiXXAIxJIDAJ1zMW4yaTpebo8fPOliYc=` | `h1:mvySKfSWJ+UKUii46M40LOvyWfN0s2U+46/jDd0e6Ck=` |
| 3 | `golang.org/x/mod` | `v0.29.0` | `h1:NyhrlYXJ2H4eJiRy/WDBO6HMqZQ6q9nk4JzS3NuCK+w=` | `h1:HV8lRxZC4l2cr3Zq1LvtOsi/ThTgWnUk/y64QSs8GwA=` |
| 4 | `golang.org/x/net` | `v0.46.0` | `h1:Q9BGdFy1y4nkUwiLvT5qtyhAnEHgnQ/zd8PfU6nc210=` | `h1:giFlY12I07fugqwPuWJi68oOnpfqFnJIJzaIIm2JVV4=` |
| 5 | `golang.org/x/net` | `v0.6.0` | `h1:2Tu9+aMcznHK/AK1HMvgo6xiTLG5rD5rZLDS+rp2Bjs=` | `h1:L4ZwwTvKW9gr0ZMS1yrHD9GZhIuVjOBBnaKH+SPQK0Q=` |
| 6 | `golang.org/x/sync` | `v0.1.0` | `h1:RxMgew5VJxzue5/jJTE5uejpjVlOe/izrB70Jof72aM=` | `h1:wsuoTGHzEhffawBOhz5CYhcrV4IdKZbEyZjBMuTp12o=` |
| 7 | `golang.org/x/sync` | `v0.17.0` | `h1:9KTHXmSnoGruLpwFjVSX0lNNA75CykiMECbovNTZqGI=` | `h1:l60nONMj9l5drqw6jlhIELNv9I0A4OFgRsG9k2oT9Ug=` |
| 8 | `golang.org/x/sys` | `v0.37.0` | `h1:OgkHotnGiDImocRcuBABYBEXf8A9a87e/uXjp9XT3ks=` | `h1:fdNQudmxPjkdUTPnLn5mdQv7Zwvbvpaxqs831goi9kQ=` |
| 9 | `golang.org/x/sys` | `v0.8.0` | `h1:oPkhp1MJrh7nUepCBck5+mAzfO9JrbApNNgaTdGDITg=` | `h1:EBmGv8NaZBZTWvrbjNoL6HVt+IVy3QDQpJs7VRIw3tU=` |
| 10 | `golang.org/x/telemetry` | `v0.0.0-20251008203120-078029d740a8` | `h1:Pi4ztBfryZoJEkyFTI5/Ocsu2jXyDr6iSdgJiYE/uwE=` | `h1:LvzTn0GQhWuvKH/kVRS3R3bVAsdQWI7hvfLHGgh9+lU=` |
| 11 | `golang.org/x/term` | `v0.12.0` | `h1:owVbMEjm3cBLCHdkQu9b1opXd4ETQWc3BhuQGKgXgvU=` | `h1:/ZfYdc3zq+q02Rv9vGqTeSItdzZTSNDmfTi0mBAuidU=` |
| 12 | `golang.org/x/term` | `v0.8.0` | `h1:xPskH00ivmX89bAKVGSKKtLOWNx2+17Eiy94tnKShWo=` | `h1:n5xxQn2i3PC0yLAbjTpNT85q/Kgzcr2gIoX9OrJUols=` |
| 13 | `golang.org/x/text` | `v0.13.0` | `h1:TvPlkZtksWOMsz7fbANvkp4WM8x/WCo/om8BMLbz+aE=` | `h1:ablQoSUd0tRdKxZewP80B+BaqeKJuVhuRxj/dkrun3k=` |
| 14 | `golang.org/x/text` | `v0.9.0` | `h1:e1OnstbJyHTd6l/uOt8jFFHp6TRDWZR/bV3emEE/zU8=` | `h1:2sjJmO8cDvYveuX97RDLsxlyUxLl+GHoLxBiRdHllBE=` |
| 15 | `golang.org/x/tools` | `v0.1.12` | `h1:hNGJHUnrk76NpqgfD5Aqm5Crs+Hm0VOH/i9J2+nxYbc=` | `h1:VveCTK38A2rkS8ZqFY25HIDFscX5X9OoEhJd3quQmXU=` |

## Canonical bindings

- Combined-v5 checker raw SHA-256:
  `b63047c6867175655cf95710767dd930783dae5d99883dfb731aedeb59459e92`
- Combined-v5 checker normalized SHA-256:
  `63587ee84ebe68aeb579c1bf85478e3c818ceaeaa8770e499d36b05ee41fe1aa`
- Combined-v5 tests raw SHA-256:
  `bbf0ec5506ad7ac974bd07bf9a26e4bd993bf289abbbbe3d54e8ff74dfaf3549`
- Combined-v5 candidate content SHA-256:
  `87ee231bf81a403e35379624ac4275ecacf36fee9d0d1e1c5699ca390afb1ebd`
- Combined input-set SHA-256:
  `06acb9e5395898abb1827761436b8c4b5d983d87d242eaf20622e352d0180c63`
- Source-bindings digest SHA-256:
  `762e231d84ae860233f0cfa717a1c1e2b8a56ec9108eaa0bacaf7a30d361817c`
- Graph SHA-256:
  `4b424c41fbc8fa09c5bc9f91a880f14309cb409785991cfb872bb2475d94e8fe`
- Frontier canonical SHA-256:
  `1c226bfc244970e071ad2bf09d6e356cd9d42e7b542cd0cf1582fc2fdc4d9b8a`
- Compact identity SHA-256:
  `3e84f0d10c361a6520ce0746bfed49b3591be4f06a7508d48d4be4f14bb02b71`
- Full witness SHA-256:
  `61f3d4a57a80b3146d1a2728822203b47832c2bb99fa092d5127d746d6ca7b72`
- Wave7 focused tests raw SHA-256:
  `93371c63c0b9cf435aef68adeb9a7a790f25d2bf4a07b3c665af30b79913c0e0`

## Prepared request contract

The decision prepares exactly 30 ordered request descriptions: each tuple's
`mod` request immediately followed by its `zip` request. Every request keeps
`selectedByGraphAlgorithm=false`, `authenticationRequired=false`,
`networkAuthorized=false`, and `acquisitionAuthorized=false`.

Preparing the descriptions does not authorize DNS, sockets, HTTPS, file
writes, acquisition, extraction, subprocesses, source loading or execution,
compilation, Git operations, credentials, owner proof, keys, signatures,
tokens, passwords, or user action.

## Verification boundary

The checker inherits combined-v5's recursively hardened pinned classes,
immediate descriptor ownership, exhaustive close/retry behavior, and read-only
provider facade. Zero file writes are claimed only for the trusted pinned
normal reconstruction path. This is not an operating-system syscall sandbox;
`osSyscallSandboxProvided=false`.

The materialized decision is opened through the safe bootstrap descriptor pin
and receives identity barriers immediately before and after canonical semantic
validation. Focused tests also derive all 30 request rows independently from
the fixed identity tuples and reject integer substitutes for lineage booleans.

Run:

```sh
python3 -I -B -S script/check_p2p_nat_g2_pion_rung3_dependency_wave7_decision_v1.py
python3 -I -B -S script/test_p2p_nat_g2_pion_rung3_dependency_wave7_decision_v1.py
```

The next bounded action is a separate one-use 30-resource Wave7 acquisition
permit/checker/runner/tests package. This decision itself does not grant that
action.
