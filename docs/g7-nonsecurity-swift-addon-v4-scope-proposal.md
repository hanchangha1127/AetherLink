# G7 Non-Security Swift Add-on V4 Scope Proposal

Status: reviewed proposal retained as the pre-execution scope record. The exact
selector was subsequently executed and passed in [Candidate
V4](g7-nonsecurity-merge-full-candidate-v4.md).

Recorded: 2026-08-02 KST.

This proposal starts from the passing
[G7 Candidate V3](g7-nonsecurity-merge-full-candidate-v3.md) partition of 2,173
discovered Swift identities, 1,120 distinct executed identities, 966 identities
excluded by the active scope, and 87 external-network or socket exclusions.
Two independent GPT-5.6 Sol read-only source reviews selected 53 identities that
remain deterministic, local, no-device, no-socket, and non-security.

## Exact proposed selector

The canonical proposed identity file is
[`evidence/g7-reviewed-nonsecurity-swift-addon-identities-v4-proposal.txt`](evidence/g7-reviewed-nonsecurity-swift-addon-identities-v4-proposal.txt).

- Identities: 53, ASCII sorted and unique
- LF-terminated file size: 6,324 bytes
- Raw file SHA-256:
  `1c63f6bf70e8bfeb4f966aaf7b0d8bb0b676ea36cef2afbdbd121335c663a598`
- Compact sorted JSON-array manifest SHA-256:
  `0f625c53d1045b750b8a925c969df6d3a902b9d4bd5ed65c3fb283d518f1ca4e`
- Module counts: `CompanionCoreTests` 1 and `LocalAgentBridgeTests` 52
- Class counts: `LocalRuntimeMessageRouterTests` 1,
  `AccessibilityAnnouncementTests` 1, `AetherLinkLocalizationTests` 39,
  `AetherLinkRenderSmokeTests` 11, and `PairingRouteNoticeTests` 1

The single CompanionCore identity uses an in-memory event store, injected mock
backend, and recording sink to project stored source attributions on the
development path. The LocalAgentBridge identities exercise pure copy,
localization, accessibility labels, injected state projection, render smoke,
and local QR image-cache behavior. The reviewed paths do not open sockets,
contact providers, read physical-device state, or execute authentication,
cryptography, credential, trusted-device authority, secure-channel, or pairing-
proof behavior.

## Projected partition after a passing run

These values are projections, not execution results:

| Partition | Tests | Manifest SHA-256 |
| --- | ---: | --- |
| New V4 selector | 53 | `0f625c53d1045b750b8a925c969df6d3a902b9d4bd5ed65c3fb283d518f1ca4e` |
| Distinct after add-on | 1,173 | `533de55b52fcda0f8af1871585e11fa846fdec6055c868791981ad5388711e67` |
| Scope excluded | 913 | `c67806715d2ebbbc48395eaec9308d2c62946dd4c82ae1438aec157b05ebb488` |
| External or socket excluded | 87 | `0a641f6aa0d29985b3ac2f942cd8e78267c95d65c362cf0a03ee3ace1fb1585a` |
| Remaining | 1,000 | `21353f330c03455a4cb66b55bc80846809c3505a1edfa77ea0695188fa908ee8` |

Set checks performed during review: the 53 identities are a subset of V3's
scope-excluded set, are disjoint from the 87 external/socket identities, and
produce the exact 913 + 87 = 1,000 remaining partition. The projected distinct
increase is exactly 53.

## Exclusion boundary

The review retained 48 other LocalAgentBridge identities outside this selector
because they exercise credential or secret redaction, secure-route lifecycle,
trusted-device key or ownership behavior, model-pull approval, active pairing,
secret stores, or QR decode of a live route. The remaining CompanionCore and
other protocol/transport modules were excluded when their purpose or body
crossed authentication, cryptography, permission, trusted-source audit, relay,
socket, provider, or production-route boundaries.

Implementation must treat Candidate V3 as an immutable antecedent and introduce
new V4 source files as an exact additive source delta. Before any execution, a
V4 checker must pin this 53-identity manifest, prove exact selection with no
skip filter, preserve the network-deny and serial runner profile, reject all
partition drift and boolean-as-integer aliases, and keep canonical G7/V1 claims
false. Until that implementation and run exist, every value in this proposal
remains review-only.

The implementation and run subsequently passed. The first post-V4 suite-level
review reported no non-empty V5 selector, but that conclusion was superseded by
an exact per-test execution-path audit. It examined 79 plausible assertions,
excluded 53 whose setup crossed P256, authentication, HMAC-cursor, identity-key,
or pairing-state paths, and retained 26 strict non-security/no-socket tests.
Those tests now pass as V5 inside the
[current-run successor](g7-nonsecurity-merge-full-current-run-v1.md); this file
remains only the pre-execution V4 scope record.
