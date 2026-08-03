# G7 Local Non-Security Merge-full Candidate V4

Status: passed local current-source candidate; canonical G7 and V1 remain open.

Recorded: 2026-08-02 KST.

This successor preserves the passing V3 candidate and its 75 composed commands
as immutable antecedent evidence. It executes only four new V4 add-on commands
for the reviewed 53-identity selector. Those four commands are the current run;
the V3 command history is not represented as newly executed.

## Candidate identity

- Path: `.build/aetherlink-g7-nonsecurity-merge-full-candidate-v4/candidate.json`
- Size: 16,718 bytes
- SHA-256: `e91edaa38b0ca05afddd2b9f55f33b916b62114b585dee8e716cf41b7adb65d5`
- Encoding and publication: canonical ASCII JSON with one trailing LF, mode
  `0600`, single-link physical file, candidate-last atomic replacement
- Source: 1,014 files, 67,959,532 bytes, SHA-256
  `9a1854b725ed43b5c8f6595f85ff9d18e39e3a98e8db39b678aec21625f2fef6`
- Bound sets: 46 artifacts and 23 implementation inputs

The runner verified the exact source and output path contracts, immutable V3
candidate bytes, all V3 artifact and implementation records before and after
execution, identical V4 artifact identities before and after postflight,
unchanged source bytes, and the identity of the already-running AetherLink
process at PID 59809 before and after execution.

## Evidence composition

- V3 antecedent: 75 composed commands and 1,120 distinct local non-security
  Swift identities
- V4 successor: four commands; 53/53 newly selected Swift tests passed with
  zero failures and zero skips under the serial network-deny profile
- V4 XCTest duration: 120.696 seconds; candidate runner V4 test gate duration:
  122.036 seconds
- Composed local evidence: 79 commands and 1,173 distinct Swift identities from
  2,173 discovered identities
- Remaining Swift identities: 1,000, consisting of 913 excluded by the active
  non-security scope and 87 external-network or socket exclusions;
  unclassified count is zero
- Preserved Android evidence: 19 classes, 1,226 tests, and zero lint issues
- Preserved supporting evidence: 57 DocumentIngestion ASan tests, two mutation
  XCTest identities, 96 deterministic mutation cases, and 22 Release
  compliance tests

The exact V4 selector contains 52 `LocalAgentBridgeTests` identities and one
`CompanionCoreTests` identity. Its class distribution is Accessibility 1,
Localization 39, render smoke 11, local runtime message routing 1, and pairing
route notice 1.

The V4 add-on result is 3,098 bytes with SHA-256
`85332fe3d82dc395737a258dbdfd13b28ce011adc98e9e00741d6ad21a3a3315`.
The immutable V3 candidate remains 14,457 bytes with SHA-256
`b43b6ff584216466380a16a84dcf35cb9bc9129deda8d1d31c431610946f1575`.

## Verification performed

- The add-on contract self-test passed.
- Forty-seven V4 mutation, exact-type, path, source-projection, independent
  schema, and failure-preservation regressions passed.
- The candidate passed its separate checker, including a bounded subprocess
  readback of the add-on result.
- An implementation-independent standard-library byte audit reconstructed the
  1,014-file source snapshot, reopened all 46 artifact and 23 implementation
  records, checked canonical JSON/mode/single-link constraints, and confirmed
  the 53-test console summary.
- Two GPT-5.6 Sol read-only audits found and verified fixes for selector-ready
  preflight, boolean-as-integer class counts, and cumulative coverage counts;
  the final re-audit reported no remaining P0-P3 issue.

Exact local commands:

```sh
python3 -B script/run_g7_nonsecurity_merge_full_candidate_v4.py --preserve-pid 59809
python3 -B script/check_g7_reviewed_nonsecurity_swift_addon_v4.py --results
python3 -B script/check_g7_nonsecurity_merge_full_candidate_v4.py
```

## Claim boundary and next work

This ignored `.build` candidate is local current-source evidence, not retained
release evidence. It does not claim the complete Swift suite, hosted CI,
physical-device or production-network execution, signed artifacts, canonical
Merge-full, canonical G7 exit, RC/GA, or V1 qualification. Security,
authentication, and cryptography suites were not executed in this active
non-security slice.

### Recorded post-V4 selector review (superseded)

After the passing run, two GPT-5.6 Sol read-only reviews and the preceding
protocol/transport review recorded the following suite-level classification of
the 1,000 remaining identities. A later exact per-test execution-path audit
found that this grouping was too coarse; the table is retained as historical
review output and is not the current selector decision:

| Reviewed partition | Identities | Security, authority, or approval boundary | Socket, network, or live-provider boundary |
| --- | ---: | ---: | ---: |
| CompanionCore excluding LocalRuntimeMessageRouter | 227 | 218 | 9 |
| LocalRuntimeMessageRouter, LocalAgentBridge, and live backend tests | 320 | 185 | 135 |
| Protocol, Pairing, P2P/NAT, Relay, Transport, and TrustedDevices | 453 | 391 | 62 |
| Total | 1,000 | 794 | 206 |

At that checkpoint the review recorded the compact eligible array as `[]`
(2 bytes, no trailing LF), SHA-256
`4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
That conclusion incorrectly classified pure LocalAgentBridge localization,
view-state, accessibility-copy, and notice-mapping tests by suite/file theme.
The successor audit examined actual setup and execution paths: 79 identities
were plausible from assertions alone, 53 were rejected because they actually
create P256 identities, authenticate, use HMAC cursors, or create pairing state,
and 26 strict non-security/no-socket identities remained. Their manifest
SHA-256 is
`15970c0667b69b337d5fe13bfaffc36fd99e2b1fba52cb4cb99be230a7f04ede`.
The research-notebook pagination class remains excluded because its cursor uses
HMAC-SHA256. Hosted, device/network, signing, staged-release, and production-
operability evidence remain separate canonical G7 requirements.

### Current-run successor

The fresh 2,175-identity checkout and its two SQLite recovery additions were
subsequently recomposed into one serial network-denied invocation. Four exact
local-socket tests were separated from that no-socket lane without `--skip` or
relaxing the sandbox. The strict V5 successor adds 26 exact tests; the resulting
1,197-test no-socket child passed with zero failures and zero skips. A fresh
focused 222-test child contributes only those exact four started-to-passed
local-socket identities through a common-test-list parent. The resulting
reviewed union is 1,201 identities with 974 remaining;
complete Swift, canonical Merge-full, and canonical G7 remain open. The result
and exact claim boundary are recorded in [G7 Local Non-Security Merge-full
Current Run V1](g7-nonsecurity-merge-full-current-run-v1.md).
