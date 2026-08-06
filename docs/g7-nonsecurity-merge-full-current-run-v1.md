# G7 Local Non-Security Merge-full Current Run V1

Status: passed local current-source two-child reviewed Swift parent; canonical
Merge-full, G7, and V1 remain open.

Recorded: 2026-08-03 KST.

## Scope decision

A fresh `swift test list` contains 2,175 identities. The reviewed historical V4
union, two current SQLite recovery regressions, the strict 26-test V5 manifest,
the strict seven-test V6 manifest, and the strict one-test V7 manifest contain
1,209 identities after the
focused carrier contributes its four exact local-socket tests.
Four focused tests create real local listeners or TCP sockets and cannot run
inside the current no-socket child's OS `(deny network*)` profile.

The current selector therefore removes exactly those four identities from the
focused component with an anchored negative guard. It does not use `--skip`,
does not relax the network-deny profile, and does not alter the separate
focused CI lane that owns their socket coverage. The parent now reopens that
fresh 222-test focused marker, console, and binding; accepts only those exact
four started-to-passed identities as the focused child's contribution; and
combines them with the disjoint 1,205-test no-socket child. Both children use
the same 245,185-byte discovery file and are independently revalidated against
the final checkout. The focused carrier is not OS egress-denied, so the parent
does not claim external-network denial for that child.

## Evidence identity

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Execution contract | 135,120 | `6bbd9b26306a005584723404cd7585a02a745247a4089138129a5c75e226b08d` |
| Run marker | 364 | `07b8050f08f2bbb7e95803b56f46def9fb7facccae591dc3466d557cecbcb11c` |
| Swift console | 384,760 | `f202dd998854e01402aeb2d8687b160b1492fb8774c0b123bb875b6520749ad3` |
| Binding | 714 | `aebb8ed37cdfdd5c096c9f31305144fb3c9956e6045c0d066fb9e09b55d3e0e4` |
| No-socket result | 3,493 | `31471496ff72b1a6ffe5c29a329bdd44dce5e78f8eeb82f1a54cf5bc3c9466e9` |
| Parent result | 2,679 | `ecc8c7463269fd85f485900f664f1b67974afbb0bb842c02600eba2ca8d9c0a1` |

All six files are under
`.build/aetherlink-g7-nonsecurity-merge-full-current-run-v1/`. They are local,
ignored current-source evidence rather than retained release artifacts. The
no-socket result binds 241 source inputs at aggregate SHA-256
`8c03de5a2f5c9d2d8b40ec0497eb33c16d519a806139fb0a67fb30c7ddc41d0e`.
The focused child separately binds 219 source inputs at SHA-256
`fb1160beeab51d1773c87222257edafd8782b484b7d32da0b4544cf6b891a06d`.
Its marker, console, and binding are respectively 363, 67,853, and 711 bytes
with SHA-256 `ebe8f7be6a3d5da990641f6391ae1556f5d160c94679ddab42fb487d0781c29e`,
`76aa3c2a26d83094d45a1daadf7b99ed986119785a57052daeb9043c147f41c3`,
and `bc5117bbd89e153bbdf25d03af29becc93c1b4899eb0392560e286f4526d7c4b`.

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
| Strict V7 new | 1 | `2f726fc2fd89ab9a4c7ec464dd94a3aeac0ee9e41811710ddf24baf5bc4ae9aa` |
| No-socket child | 1,205 | `33cf8415b21aa5bf727ac05cdaac6752c8929565fa934e2666128b35330bbd5b` |
| Parent reviewed union | 1,209 | `26e97b0bf2349883b71677dfb614d15f8a2e920d3fc42036b6e1a08add7cf6a2` |
| Parent remaining | 966 | `d6da7f2fc7954fa3cf81528028da42bc0b54ddd8320c28ebd07d757b93b2567e` |

The focused/expanded overlap remains 72. The V2 current-new, V3, V4, strict V5,
strict V6, and strict V7 components are 628, 97, 53, 26, 7, and 1 identities
respectively.
The V5 source is the sorted 2,887-byte LF manifest at
`script/g7_reviewed_nonsecurity_swift_addon_identities_v5.txt`, raw SHA-256
`295395947575e19481f62384137a6b1bda23e71d07708b62df67dc1afc8f9b2b`.
The V6 source is the sorted 732-byte ASCII LF manifest at
`script/g7_reviewed_nonsecurity_swift_addon_identities_v6.txt`, raw SHA-256
`e64e65bbbcdb371b65cf8f290a606de55864c5a48988778a1a85954e05de837c`.
The V7 source is the sorted 124-byte ASCII LF manifest at
`script/g7_reviewed_nonsecurity_swift_addon_identities_v7.txt`, raw SHA-256
`6894d0e26b04a0054f38b733dc553758e9e5b99b9f7b8df85098b6f08cbe4792`.
The combined selector is 65,200 bytes and the command plus allowlisted
environment is 66,321 bytes, both within their fixed limits. The execution
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

The V7 manifest adds exactly
`TrustedDevicesTests.ProductionC1ExactBoundStartCoordinatorTests/testCancellationAfterFinalCheckPreservesSuccessfulTaskValue`.
The test executes only Swift `Task` cancellation and its file-local
`ExactBoundVoidGate`; it does not construct the production coordinator or enter
provider, device, security, authentication, cryptography, or socket paths.

## Unit scope closure

The pinned canonical ledger at
`script/g7_nonsecurity_unit_scope_ledger_v1.json` is 1,859,933 bytes with
SHA-256
`d5ed9eaff8dd7820b97e65a104d94fd59ebba16a9d611782e5d5cc739d1e8d49`.
It classifies all 2,175 Swift identities and all 595 Android Core identities.
The final partition is 1,209 Swift eligible plus 966 excluded and 117 Android
eligible plus 478 excluded, with zero unclassified identities on both
platforms. The Android eligible partition is 96 protocol tests and 21
transport tests across four transport classes.

`script/check_g7_nonsecurity_unit_scope_ledger.py --evidence` independently
reconstructed both discoveries, the 293-file source closure, every disposition,
the Swift 1,209-test parent manifest, and both Android JUnit bindings. It passed
immediately after Android binding and again during final candidate readback.
For Android, this checker validates the binding records and eligible testcase
manifests rather than reopening raw XML, marker, or source-input bytes; the
separately ordered product-CI readbacks own those raw-byte checks.
The ledger is a per-test review attestation and explicitly does not claim that
its semantic judgement was mechanically reproduced.

## Verification performed

- The fresh focused carrier passed 222/222 tests with zero failures and zero
  skips in 23.803 seconds. Its exact four local-socket identities each have one
  started event followed by one passed event.
- One serial network-denied Swift invocation passed 1,205/1,205 tests with
  zero failures and zero skips in 191.705 seconds; the bounded runner preserved
  the running app PID 59809.
- Fifty-three producer/checker/ledger regression tests passed, including the
  exact V5/V6/V7 manifest and filter contracts, max-plus-one byte rejection, exact
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
non-security union: 1,205 network-denied no-socket tests plus four local-socket
tests contributed by the separate focused carrier. It claims local-socket
execution, but not external-network denial for the focused child. It does not
claim the complete Swift suite, hosted CI, physical-device or product-network
behavior, signed artifacts, canonical Merge-full, canonical G7 exit, RC/GA, or
V1 qualification. Security, authentication, and cryptography suites were not
executed. No staging, commit, or push was performed.
