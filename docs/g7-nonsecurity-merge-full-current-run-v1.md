# G7 Local Non-Security Merge-full Current Run V1

Status: passed local current-source two-child reviewed Swift parent; canonical
Merge-full, G7, and V1 remain open.

Recorded: 2026-08-03 KST.

## Scope decision

A fresh `swift test list` contains 2,175 identities. The reviewed historical V4
union, two current SQLite recovery regressions, the strict 26-test V5 manifest,
and the strict seven-test V6 manifest contain 1,208 identities after the
focused carrier contributes its four exact local-socket tests.
Four focused tests create real local listeners or TCP sockets and cannot run
inside the current no-socket child's OS `(deny network*)` profile.

The current selector therefore removes exactly those four identities from the
focused component with an anchored negative guard. It does not use `--skip`,
does not relax the network-deny profile, and does not alter the separate
focused CI lane that owns their socket coverage. The parent now reopens that
fresh 222-test focused marker, console, and binding; accepts only those exact
four started-to-passed identities as the focused child's contribution; and
combines them with the disjoint 1,204-test no-socket child. Both children use
the same 245,185-byte discovery file and are independently revalidated against
the final checkout. The focused carrier is not OS egress-denied, so the parent
does not claim external-network denial for that child.

## Evidence identity

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Execution contract | 134,721 | `6a865e807125a54ccff84997f5438562dae4eb116029507cb0b023887d5d2778` |
| Run marker | 364 | `39559c1e773f43532e5c1a0aecfa0f2d5fb4753e43efa6956bae0aad55a1b84c` |
| Swift console | 384,189 | `dcb3541555dd11a97412b2ea990454b177ab5d13e0f25f7957d5613804cf9b70` |
| Binding | 714 | `02706861c3619ffd27dad449ef4a0494b86f2b87f0c7d8382843adc2be727d24` |
| No-socket result | 3,389 | `4051ec72b4aaa27002c9f44485fb9777e3ab0e1f3872f5017982f6e9d57afcf0` |
| Parent result | 2,679 | `64e5526ca18702f86bada85e52c36c0fe3365627dbbf911cc4247572205a9004` |

All six files are under
`.build/aetherlink-g7-nonsecurity-merge-full-current-run-v1/`. They are local,
ignored current-source evidence rather than retained release artifacts. The
no-socket result binds 237 source inputs at aggregate SHA-256
`29e6f15b7d3aa6672f9a6df752eeba9dfb0b2c7a8ec95941cb8b360b52956e15`.
The focused child separately binds 219 source inputs at SHA-256
`0bf09c31288253851ee509b9aea602a14bfa89273a477bcade234087d095c160`.
Its marker, console, and binding are respectively 363, 67,853, and 711 bytes
with SHA-256 `6ee2a4f45bfebc46c5085a8d674bd4b15f925f120177e62eb3cc8523fb3f80e8`,
`80a84fb24cf4d5d77413434002f9ad456ce519fa1269ba6f3fea42e2f7431fe5`,
and `f3617058a946268aff0be241ea36cb209387a99368da13787f050bfd6640799b`.

## Exact selection

| Partition | Tests | Manifest SHA-256 |
| --- | ---: | --- |
| Fresh discovery | 2,175 | `a8121a99615da2b2b5b39535f5a8fb0ee03bf48fc2a4773d0aced5bac4a5041a` |
| Effective focused | 218 | `a74d9e570a3e09e243f3f5ee239db4faa555e44cfd0c99790da71ea70b61285c` |
| Expanded | 247 | `9ad12d0f8b909021046f6b00cdd989dc41010af85d02febd424a4fb6edaf861c` |
| Base distinct | 393 | `9d7784e88b7263ca0f3df34b93c59cdcfa0ed76bfe0ee8bc37edabd291966248` |
| Focused carrier | 222 | `b481e814d8e0f7a2385e50fb5d0f0f8d1602f08b608eb373bb8960ce53547815` |
| Focused/no-socket overlap | 218 | `a74d9e570a3e09e243f3f5ee239db4faa555e44cfd0c99790da71ea70b61285c` |
| Local-socket contribution | 4 | `f83d04659cc16094468c8966185750a57bd3d702429116d8412b7ab99e4e47fc` |
| Strict V5 new | 26 | `15970c0667b69b337d5fe13bfaffc36fd99e2b1fba52cb4cb99be230a7f04ede` |
| Strict V6 new | 7 | `6b4991164cab03a5575a8c0d4a0526874571994e65e5bde612d8716333482a5d` |
| No-socket child | 1,204 | `fbab18434f821237178e87aab1e84ce58bf7e82802978439ae43fc1f95e76fde` |
| Parent reviewed union | 1,208 | `ea63ec325a6125f4ae92c49c0ca9d3054e054369335bec6ebeb99c7256468846` |
| Parent remaining | 967 | `fe4c11470e53a92ff64fe31c143b7d587eacdfcdd68ac8af7c5ba7233d58e9e6` |

The focused/expanded overlap remains 72. The V2 current-new, V3, V4, strict V5,
and strict V6 components are 628, 97, 53, 26, and 7 identities respectively.
The V5 source is the sorted 2,887-byte LF manifest at
`script/g7_reviewed_nonsecurity_swift_addon_identities_v5.txt`, raw SHA-256
`295395947575e19481f62384137a6b1bda23e71d07708b62df67dc1afc8f9b2b`.
The V6 source is the sorted 732-byte ASCII LF manifest at
`script/g7_reviewed_nonsecurity_swift_addon_identities_v6.txt`, raw SHA-256
`e64e65bbbcdb371b65cf8f290a606de55864c5a48988778a1a85954e05de837c`.
The combined selector is 65,069 bytes and the command plus allowlisted
environment is 66,190 bytes, both within their fixed limits. The execution
contract is capped separately at 160 KiB.

The V5 manifest corrects the earlier suite-level claim that every remaining
identity was security/network-bound. An exact execution-path re-audit first
identified 79 plausible product assertions, then excluded 53 whose setup
actually creates P256 identities, performs challenge-response authentication,
uses HMAC cursors, or creates pairing/security state. The retained 26 are 25
pure localization/state/copy tests plus one pairing-route notice mapping test;
they start no socket, network, live provider, device, authentication, or
cryptography path.

The V6 manifest adds six pure RuntimeAdvertisementMetadata value/filtering
tests and one synchronous pre-send encoding-failure test. The metadata tests
use strings, dictionaries, and UTF-8 data only. The remaining test cancels an
unstarted NWConnection after NaN JSON encoding fails and before any writer or
connection send. These seven tests open no socket and execute no external
network, live-provider, device, security, authentication, cryptography, or
pairing path.

## Verification performed

- The fresh focused carrier passed 222/222 tests with zero failures and zero
  skips in 23.746 seconds. Its exact four local-socket identities each have one
  started event followed by one passed event.
- One serial network-denied Swift invocation passed 1,204/1,204 tests with
  zero failures and zero skips in 189.494 seconds; the bounded runner preserved
  the running app PID 59809.
- Thirty-six producer/checker regression tests passed, including the exact
  V5/V6 manifest and filter contracts, max-plus-one byte rejection, exact
  socket contribution, parent partition, stale child, chronology, and exact
  integer type rejection.
- The producer and implementation-independent checker self-tests passed.
- Product CI contract validation and its mutation self-test passed. The
  workflow raw/parsed SHA-256 values are
  `eee738acbf0b61b5fd94fb716227d376bf7de14d247ab19c78239e488b9d0895`
  and
  `d7361e671c72620957f795e4975776c1612688c72b5109facf59308d82de1d2b`.
- The standard-library-only command below independently reconstructed the
  selection, source snapshot, marker, console events, binding, and result
  bytes without importing project modules:

```sh
python3 -I -B -S script/check_g7_nonsecurity_merge_full_current.py \
  .build/aetherlink-g7-nonsecurity-merge-full-current-run-v1/result.json

python3 -I -B -S script/check_g7_nonsecurity_merge_full_current.py \
  --parent \
  .build/aetherlink-g7-nonsecurity-merge-full-current-run-v1/parent-result.json
```

## Claim boundary

This parent proves only the exact current-source local no-device reviewed
non-security union: 1,204 network-denied no-socket tests plus four local-socket
tests contributed by the separate focused carrier. It claims local-socket
execution, but not external-network denial for the focused child. It does not
claim the complete Swift suite, hosted CI, physical-device or product-network
behavior, signed artifacts, canonical Merge-full, canonical G7 exit, RC/GA, or
V1 qualification. Security, authentication, and cryptography suites were not
executed. No staging, commit, or push was performed.
