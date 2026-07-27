# Wave8 Dependency Identity and Acquisition Decision

Status: the exact 14-tuple Wave8 frontier is identity-complete and
acquisition-ready, but this decision grants no acquisition or execution
authority.

## Scope

The pinned combined-v6 checker reconstructed the retained root ZIP, 114
external `go.mod` files, and 114 dependency ZIPs and produced a non-fixed
14-tuple frontier. The Wave8 decision checker scans all 229 retained inputs
twice. Each scan reads parent declarations from the root and external
`go.mod` bytes and searches the 81 ZIP-contained `go.sum` files. It does not
acquire, extract, load, execute, or compile dependency source.

Both scans produced the same 14 parent-declaration witnesses, 93 `go.mod` H1
witnesses, and 15 module-ZIP H1 witnesses. All 14 identity pairs are complete;
there are no missing or conflicting H1 values. Every graph selector is
`false`.

The retained `go.sum` witnesses are deterministic held evidence, not fresh
checksum-database inclusion proofs.

## Exact Wave8 tuples

Tuple identity is the exact `(module, version)` pair. Order and
version-specific duplicates are preserved; no module-only or MVS collapse is
allowed.

| Order | Module | Version | `go.mod` H1 | module ZIP H1 |
|---:|---|---|---|---|
| 1 | `github.com/davecgh/go-spew` | `v1.1.0` | `h1:J7Y8YcW2NihsgmVo/mv3lAwl/skON4iLHjSsI+c5H38=` | `h1:ZDRjVQ15GmhC3fiQ8ni8+OwkZQO4DARzQgrnXU1Liz8=` |
| 2 | `github.com/stretchr/objx` | `v0.1.0` | `h1:HFkY916IF+rwdDfMAkV7OtwuqBVzrE8GR6GFx+wExME=` | `h1:4G4v2dO3VZwixGIRoQ5Lfboy6nUhCyYzaqnIAPPhYs4=` |
| 3 | `golang.org/x/crypto` | `v0.43.0` | `h1:BFbav4mRNlXJL4wNeejLpWxB7wMbc79PdRGhWKncxR0=` | `h1:dduJYIi3A3KOfdGOHX8AVZ/jGiyPa3IbBozJ5kNuE04=` |
| 4 | `golang.org/x/mod` | `v0.6.0-dev.0.20220419223038-86c51ed26bb4` | `h1:jJ57K6gSWd91VN4djpZkiMVwK6gcyfeH4XE8wZrZaV4=` | `h1:6zppjxzCulZykYSLyVDYbneBfbaBIQPYMevg0bEwv2s=` |
| 5 | `golang.org/x/net` | `v0.0.0-20220722155237-a158d28d115b` | `h1:XRhObCWvk6IyKnWLug+ECip1KBveYUHfp+8e9klMJ9c=` | `h1:PxfKdU9lEEDYjdIzOtC4qFWgkU2rGHdKlKowJSMN9h0=` |
| 6 | `golang.org/x/sync` | `v0.0.0-20220722155255-886fb9371eb4` | `h1:RxMgew5VJxzue5/jJTE5uejpjVlOe/izrB70Jof72aM=` | `h1:uVc8UZUe6tr40fFVnUP5Oj+veunVezqYl9z7DYw9xzw=` |
| 7 | `golang.org/x/sys` | `v0.0.0-20220722155257-8c9f86f7a55f` | `h1:oPkhp1MJrh7nUepCBck5+mAzfO9JrbApNNgaTdGDITg=` | `h1:v4INt8xihDGvnrfjMDVXGxw9wrfxYyCjk0KbXjhR55s=` |
| 8 | `golang.org/x/term` | `v0.36.0` | `h1:Qu394IJq6V6dCBRgwqshf3mPF85AqzYEzofzRdZkWss=` | `h1:zMPR+aF8gfksFprF/Nc/rd1wRS1EI6nDBGyWAvDzx2Q=` |
| 9 | `golang.org/x/term` | `v0.5.0` | `h1:jMB1sMXY+tzblOD4FWmEbocvup2/aLOaQEp7JmGp78k=` | `h1:n2a8QNdAb0sZNpU9R1ALUXBbY+w51fCQDN+7EdxNBsY=` |
| 10 | `golang.org/x/text` | `v0.3.7` | `h1:u+2+/6zg+i71rQMx5EYifcz6MCKuco9NR6JIITiCfzQ=` | `h1:olpwvP2KacW1ZWvsR7uQhoyTYvKAupfQrRGBFM352Gk=` |
| 11 | `golang.org/x/text` | `v0.30.0` | `h1:yDdHFIX9t+tORqspjENWgzaCVXgk0yYnYuSZ8UzzBVM=` | `h1:yznKA/E9zq54KzlzBEAWn1NXSQ8DIp/NYMy88xJjl4k=` |
| 12 | `golang.org/x/text` | `v0.7.0` | `h1:mrYo+phRRbMaCq/xk9113O4dZlRixOauAjOtrjsXDZ8=` | `h1:4BRB4x83lYWy72KwLD/qYDuTu7q9PjSagHvijDw7cLo=` |
| 13 | `golang.org/x/tools` | `v0.37.0` | `h1:MBN5QPQtLMHVdvsbtarmTNukZDdgwdwlO5qGacAzF0w=` | `h1:DVSRzp7FwePZW356yEAChSdNcQo6Nsp+fex1SUW09lE=` |
| 14 | `gopkg.in/yaml.v3` | `v3.0.0-20200313102051-9f266ea9e77c` | `h1:K4uyk7z7BCEPqu6E+C64Yfv1cQ7kz7rIZviUmN+EgEM=` | `h1:dUUwHk2QECo/6vqA44rthZ8ie2QXMNeKRTHCNY2nXvo=` |

## Canonical bindings

- Combined-v6 checker raw SHA-256:
  `eee3d6bd5ec0857bc4832895f4c2d463b608ffc0a59436ebc2cde507cd9750e4`
- Combined-v6 checker normalized SHA-256:
  `3f2a9866a185d157ab4fca021b52bc55aecac914fd5a08003e2f2f34e9522eef`
- Combined-v6 tests raw SHA-256:
  `4ce508661695fd63c0e1c578a99cbfa9f369943283186958bf26b998839c7837`
- Combined-v6 candidate content SHA-256:
  `b33ef7a10de32dc99cea1dbbbcab1dac3a549eb466ef80b0229d2a0381ab9052`
- Combined input-set SHA-256:
  `f7ad0b43d571da61edd4941f8e504d54d014b01f3395aeca8d0d10b9b3c22349`
- Source-bindings digest SHA-256:
  `8358b58ad8925633d78c6c1c6160d6d52567c39a2d4c940d01a05cfc87419343`
- Graph SHA-256:
  `3648bdf037e316e69e155615edd5748c2bb653238579216ddd8b8dce4beb9f09`
- Frontier canonical SHA-256:
  `d3c3788d6a1144bf04ea2c68e6aa4b9fdd17859bc625e2c2c51019bb3c61ff92`
- Compact identity SHA-256:
  `c6aa1a974ad09f11927c103c7f2b63df0835d09b41d0dac9f6349d46d377a388`
- Full witness SHA-256:
  `044dc1dd0675d781d174825dbe8e419d7ff0fe6029b590e2d16c5edeed5f08ae`
- Request-set canonical SHA-256:
  `b0f0f887864ddc4cf3ab15319a9e89dbea8c84087fa3d0e374a0332240336ddc`
- Wave8 focused tests raw SHA-256:
  `040c9217711f826f16aaaa27964682587759fd46d53f53bf8e92cad3c75bc393`

## Prepared request contract

The decision prepares exactly 28 ordered request descriptions: each tuple's
`mod` request immediately followed by its `zip` request. Module paths and
versions are lower-ASCII direct-proxy identities; normalization or
case-folding is forbidden. Every selector and every acquisition authority is
`false`.

Preparing the descriptions does not authorize DNS, sockets, HTTPS, file
writes, acquisition, extraction, subprocesses, source loading or execution,
compilation, Git operations, credentials, owner proof, keys, signatures,
tokens, passwords, authentication, or user action.

## Verification boundary

The checker inherits combined-v6's pinned no-follow descriptor handling,
recursive checker hardening, and read-only provider facade. The combined-v6
candidate performs ten cumulative full source reconstructions and 830
cumulative graph archive opens. Two identity scans add 230 archive opens;
the overall decision path accounts for 1,060 archive opens.

Zero file writes are claimed only for the trusted pinned normal path. This is
not an operating-system syscall sandbox; `osSyscallSandboxProvided=false`.

Run:

```sh
python3 -I -B -S script/check_p2p_nat_g2_pion_rung3_dependency_wave8_decision_v1.py
python3 -I -B -S script/test_p2p_nat_g2_pion_rung3_dependency_wave8_decision_v1.py
```

The next bounded action is a separate one-use 28-resource Wave8 acquisition
permit/checker/runner/tests package. This decision itself does not grant that
action.
