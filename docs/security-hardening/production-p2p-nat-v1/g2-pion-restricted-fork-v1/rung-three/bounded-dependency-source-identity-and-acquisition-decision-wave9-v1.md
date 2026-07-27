# Wave9 Dependency Identity and Acquisition Decision

Status: the exact ten-tuple Wave9 frontier is identity-complete and
acquisition-ready, but this decision grants no acquisition or execution
authority.

## Scope

The pinned combined-v7 checker reconstructed the retained root ZIP, 128
external `go.mod` files, and 128 dependency ZIPs and produced a non-fixed
ten-tuple frontier. The Wave9 decision checker reopens all 257 exact source
inputs with no-follow descriptors, reads every input twice, and retains those
descriptors through two identity scans and the final identity barrier.

Each scan reads parent declarations from the root and external `go.mod` bytes
and searches 90 ZIP-contained `go.sum` files. Both scans reproduce 11 parent
declarations, 73 `go.mod` H1 witnesses, and 11 module-ZIP H1 witnesses. All ten
identity pairs are complete, with no missing or conflicting H1 values. Every
graph selector is `false`.

The retained `go.sum` witnesses are deterministic acquisition inputs, not
fresh checksum-database inclusion, source-authorship, or owner proofs.

## Exact Wave9 tuples

Tuple identity is the exact `(module, version)` pair. Order and
version-specific duplicates are preserved; no module-only or MVS collapse is
allowed. In particular, the two `x/net` versions remain distinct even though
their `go.mod` H1 values match.

| Order | Module | Version | `go.mod` H1 | module ZIP H1 |
|---:|---|---|---|---|
| 1 | `golang.org/x/crypto` | `v0.0.0-20210921155107-089bfa567519` | `h1:GvvjBRRGRdwPK5ydBHafDWAxML/pGHZbMvKqRZ5+Abc=` | `h1:7I4JAnoQBe7ZtJcBaYHi5UtiO8tQHbUSXxL+pnGRANg=` |
| 2 | `golang.org/x/mod` | `v0.28.0` | `h1:yfB/L0NOf/kmEbXjzCPOx1iK1fRutOydrCMsqRhEBxI=` | `h1:gQBtGhjxykdjY9YhZpSlZIsbnaE2+PgjfLWUQTnoZ1U=` |
| 3 | `golang.org/x/net` | `v0.44.0` | `h1:ECOoLqd5U3Lhyeyo/QDCEVQ4sNgYsqvCZ722XogGieY=` | `h1:evd8IRDyfNBMBTTY5XRF1vaZlD+EmWx6x8PkhR04H/I=` |
| 4 | `golang.org/x/net` | `v0.45.0` | `h1:ECOoLqd5U3Lhyeyo/QDCEVQ4sNgYsqvCZ722XogGieY=` | `h1:RLBg5JKixCy82FtLJpeNlVM0nrSqpCRYzVU1n8kj0tM=` |
| 5 | `golang.org/x/sys` | `v0.0.0-20220520151302-bc2c85ada10a` | `h1:oPkhp1MJrh7nUepCBck5+mAzfO9JrbApNNgaTdGDITg=` | `h1:dGzPydgVsqGcTRVwiLJ1jVbufYwmzD3LfVPLKsKg+0k=` |
| 6 | `golang.org/x/sys` | `v0.36.0` | `h1:OgkHotnGiDImocRcuBABYBEXf8A9a87e/uXjp9XT3ks=` | `h1:KVRy2GtZBrk1cBYA7MKu5bEZFxQk4NIDV6RLVcC8o0k=` |
| 7 | `golang.org/x/telemetry` | `v0.0.0-20250908211612-aef8a434d053` | `h1:+nZKN+XVh4LCiA9DV3ywrzN4gumyCnKjau3NGb9SGoE=` | `h1:dHQOQddU4YHS5gY33/6klKjq7Gp3WwMyOXGNp5nzRj8=` |
| 8 | `golang.org/x/term` | `v0.0.0-20210927222741-03fcf44c2211` | `h1:jbD1KX2456YbFQfuXm/mYQcufACuNUgVhRMnK/tPxf8=` | `h1:JGgROgKl9N8DuW20oFS5gxc+lE67/N3FcwmBPMe7ArY=` |
| 9 | `golang.org/x/tools` | `v0.0.0-20180917221912-90fa682c2a6e` | `h1:n7NCudcB/nEzxVGmLbDWY5pfWTLqBcC2KZ6jyYvM4mQ=` | `h1:FDhOuMEY4JVRztM/gsbk+IKUQ8kj74bxZrgw87eMMVc=` |
| 10 | `golang.org/x/tools` | `v0.0.0-20191119224855-298f0cb1881e` | `h1:b+2E5dAYhXwXZwtnZ6UAqBI28+e2cm9otk0dWdXHAEo=` | `h1:aZzprAO9/8oim3qStq3wc1Xuxx4QmAGriC4VU4ojemQ=` |

## Canonical bindings

- Combined-v7 checker raw SHA-256:
  `7264d85e1948bc8f86e8238192663706e7bf7472153d37fe812bd118620e99c7`
- Combined-v7 checker normalized SHA-256:
  `cf4fd9d25efe04c2ecb3eea882bb24d6c40b02f2f258c4ab01d824d1373d1c02`
- Combined-v7 tests raw SHA-256:
  `bb992db8e2d649dd982255f21c2c719ee4d0437818eb0495c9a11fe81f5ea79f`
- Combined-v7 candidate content SHA-256:
  `c71188f8d648a0f020a164002644f825e018f4c01b56d90e57011e05cc2e5202`
- Combined input-set SHA-256, including its canonical trailing LF:
  `d389c84ae3b6d2d3d7dbb38d7003711972a75db3a558b9d6e0d79856249ef528`
- Source-bindings compact digest SHA-256, without a trailing LF:
  `527c2e6dc235d269c92e52915135c1b2beec113cb751198ca7142c5e63d79148`
- Graph SHA-256:
  `c7889fbf06a01e08ba75150b85bb2cb2860ea71ce205cead432cf0a37e0d89b9`
- Frontier canonical SHA-256:
  `03058e3aea23aca0c6208dd0023361f90421d394272f212d80bf61d587baff4e`
- Compact identity SHA-256:
  `db31bdd4d1ae0c97ba88094502f7c0dc5e0f554e72c5f68503d917005f762753`
- Full witness SHA-256:
  `ee3657522619b1960c535fc3a9644441adb15cee473286bfd2871096fb719afe`
- Request-set compact SHA-256:
  `e3922164eda6657d447f1b75ff49268265338efe35440dad39a237d1ddf643bc`

## Prepared request contract

The decision prepares exactly 20 ordered request descriptions: each tuple's
`mod` request immediately followed by its `zip` request. Module paths and
versions use lower-ASCII direct-proxy identities; normalization or case
folding is forbidden. Every selector and every acquisition authority is
`false`.

The checker rejects an existing or portable NFC/case-fold alias of the Wave9
claim, staging, final, acquisition-document, or acquisition-tool namespace.
It checks that namespace twice. This is a point-in-time readiness check, not a
future path reservation; the later one-use permit must repeat the check.

Preparing these descriptions does not authorize DNS, sockets, HTTPS, file
writes, acquisition, extraction, subprocesses, source loading or execution,
compilation, Git operations, credentials, owner proof, keys, signatures,
tokens, passwords, authentication, or user action.

## Verification boundary

The checker binds combined-v7's 52 terminal controls, three auxiliary evidence
files, live Wave8 terminal metadata and inventories at its final barriers, and
the retained-snapshot caveat. It does not claim continuous current-path
identity after the final observation.

Combined-v7 accounts for twelve cumulative source reconstructions and 1,088
cumulative graph archive opens. Two Wave9 identity scans add 258 archive
opens, for 1,346 archive opens on the complete decision path. The decision
path uses seven descriptor identity barriers and two namespace snapshots.

Zero extraction, source load or execution, compilation, subprocess, network,
authentication, and file-write operations are recorded. Zero writes apply
only to the trusted pinned normal path; this is not an operating-system
syscall sandbox.

Run:

```sh
python3 -I -B -S script/check_p2p_nat_g2_pion_rung3_dependency_wave9_decision_v1.py
python3 -I -B -S script/test_p2p_nat_g2_pion_rung3_dependency_wave9_decision_v1.py
```

The next bounded action is a separate one-use 20-resource Wave9 acquisition
permit/checker/runner/tests package. This decision itself does not grant that
action.
