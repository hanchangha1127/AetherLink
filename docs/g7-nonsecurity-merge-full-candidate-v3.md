# G7 Local Non-Security Merge-full Candidate V3

Status: passed local current-source candidate; canonical G7 and V1 remain open.

Recorded: 2026-08-02 KST.

This successor preserves the passing V2 candidate as immutable evidence for its
71 previously executed commands. It executes only four new V3 Swift add-on
commands and records those four commands as the current run. The composed
evidence count is therefore 75; the V2 commands are not represented as newly
executed.

## Candidate identity

- Path: `.build/aetherlink-g7-nonsecurity-merge-full-candidate-v3/candidate.json`
- Size: 14,457 bytes
- SHA-256: `b43b6ff584216466380a16a84dcf35cb9bc9129deda8d1d31c431610946f1575`
- Encoding and publication: canonical ASCII JSON with one trailing LF, mode
  `0600`, single-link physical file, candidate-last atomic replacement
- Source: 1,008 files, 67,776,947 bytes, SHA-256
  `7281eacaf6eec1876c81945f0e61302da243357663a75ce4bf6c1d36be1883e5`
- Bound sets: 39 artifacts and 17 implementation inputs

The runner verified the fixed source and output path contracts, V2 and V3 full
postflight, identical artifact identities before and after postflight,
unchanged source bytes, the exact V2 candidate before and after execution, and
the identity of the already-running AetherLink process at PID 59809 before and
after execution.

## Evidence composition

- V2 antecedent: 71 commands; 1,023 distinct local non-security Swift tests
- V3 successor: four commands; 97/97 newly selected Swift tests passed with
  zero failures and zero skips under the serial network-deny profile
- Composed local evidence: 75 commands; 1,120 distinct Swift identities from
  2,173 discovered identities
- Remaining Swift identities: 1,053, consisting of 966 excluded by the active
  non-security scope and 87 external-network or socket exclusions; unclassified
  count is zero
- Preserved V2 Android evidence: 19 classes, 1,226 tests, and zero lint issues
- Preserved V2 supporting evidence: 57 DocumentIngestion ASan tests, two
  mutation XCTest identities, 96 deterministic mutation cases, and 22 Release
  compliance tests

The V3 add-on result is 3,000 bytes with SHA-256
`07c2b0baec71d06d98a121c57be3489b6e19d6a20fe93e1253fac28e75d6aba6`.
The immutable V2 candidate remains 45,797 bytes with SHA-256
`4a05156b1f1d06d613a40d456f34af793c6d7647b6f639937bdf2190aaf24f45`.

## Verification performed

The candidate passed its separate checker, an implementation-independent
standard-library byte readback, and a GPT-5.6 Sol read-only audit. The byte
readback independently reconstructed the 1,008-file source snapshot and
reopened all 39 artifact and 17 implementation records from current physical
files. Contract regression tests pass 41/41, while the V3 add-on and antecedent
self-checks also pass.

Exact local commands:

```sh
python3 -B script/run_g7_nonsecurity_merge_full_candidate_v3.py --preserve-pid 59809
python3 -B script/check_g7_nonsecurity_merge_full_candidate_v3.py
```

## Claim boundary and next work

This ignored `.build` candidate is local current-source evidence, not retained
release evidence. It does not claim the complete Swift suite, hosted CI,
physical-device or production-network execution, signed artifacts, canonical
Merge-full, canonical G7 exit, RC/GA, or V1 qualification. Security,
authentication, and cryptography suites were not executed in this active
non-security slice.

The reviewed [V4 53-identity scope
proposal](g7-nonsecurity-swift-addon-v4-scope-proposal.md) was subsequently
implemented and passed as [Candidate V4](g7-nonsecurity-merge-full-candidate-v4.md).
The other 913 scope exclusions and 87 external/socket exclusions remain outside
that run; hosted, device/network, signing, and staged-release evidence remain
separate later gates.
