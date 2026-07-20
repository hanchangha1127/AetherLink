# AetherLink V1 G0 Decision V1

Status: `blocked_before_g1a`  
Recorded: 2026-07-20 KST  
Implementation baseline: `main@d32c1846eead13ab1462619145fc4da1194cce7e`

This is the versioned G0 product, release, security, quality, and authority
decision for the canonical V1 roadmap. The machine-readable source is
[`decision-v1.json`](decision-v1.json). The user's instruction to execute the
canonical V1 roadmap authorizes this bounded G0 decision work. It does not
silently authorize a commit, a production identity, source acquisition,
networking, signing-key use, store upload, or deployment.

## Outcome

The technical V1 profile is now concrete enough to expose the real G0 blockers,
but G0 has not exited. Product scope, supported-platform defaults, distribution
shape, fallback profile, relay-control recommendation, pair recovery, privacy
floors, and release measurements are selected below. G1a remains closed until
the required G0 assurance artifacts and baseline gates exist, the roadmap/G0
checkpoint is intentionally published, and the actual namespace, provider
baseline, account, service identity, owner, custody, measurement, region,
capacity, and cost decisions are recorded.

The current implementation baseline is published and aligned with `origin/main`.
The canonical roadmap and this G0 packet are not yet committed. No Android device
is attached. The only physical product evidence remains one debug same-Wi-Fi QR
pairing and trusted reconnect on an `SM-S936N` running Android 16/API 36. There is
no production or unrelated-network evidence.

## Product And Support Decision

V1 remains the macOS Runtime plus Android controller release defined by the
canonical roadmap. P2P is a GA gate. Android never calls Ollama or LM Studio
directly; the Runtime owns provider URLs, model execution, history, memory,
attachments, and trust boundaries.

| Area | V1 decision | Required release evidence |
| --- | --- | --- |
| Android | API 26 through target/compile API 36, phone form factor, production device ABI `arm64-v8a`, camera required for fresh product pairing | Emulator API 26/30/33/36 plus API 26 arm64, current Pixel-class, and Galaxy S/API 36 physical release runs |
| macOS | macOS 14 or newer on Apple Silicon `arm64`; Intel is Post-V1 | Signed RC on macOS 14, 15, and 26 with provider and lifecycle coverage |
| Locales | English, Korean, Japanese, Simplified Chinese, and French | Cross-platform parity, large text, localization, TalkBack, and VoiceOver evidence |
| Providers | Ollama and LM Studio through runtime-host adapters only; G0 observed Ollama `0.32.1` and LM Studio CLI commit `6041ae0`, while minimum supported versions remain unresolved | A named compatibility owner and versioned minimum/current/previous matrix, then exact RC versions with health, catalog, chat, cancel, and restart evidence |
| Version | Android and macOS marketing version `1.0.0`; strictly monotonic build numbers in one release ledger | Installed-artifact version readback and source/artifact provenance |
| Development data | Android debug `0.1.0` is non-migratable; production requires clean install and fresh pairing | Explicit clean-install procedure; no assumed debug-signing upgrade |

The Android API declaration and provider observations are baselines, not broad
compatibility proof. The current LM Studio desktop version was not resolved.
The current release APK is unsigned and the current macOS bundle is a thin
arm64 ad-hoc build. The future physical and provider matrices cannot inherit
evidence from the earlier debug Samsung run or one local provider observation.

The required release network matrix contains twelve non-omittable cells: same-LAN
IPv4 local direct; unrelated native-IPv6 direct; unrelated IPv4 home-NAT,
home-NAT-to-CGNAT, CGNAT-to-CGNAT, and NAT64-to-IPv4 routes; UDP-blocked/TCP-443
fallback; forced TURN; forced sealed emergency relay; bidirectional authenticated
Wi-Fi/cellular handoff; VPN path-change recovery; and suspend/resume
reconnect. Every cell requires at least 100 attempts, and the campaign requires
at least 1,200 completed authenticated sessions. Both
providers must appear in every cell, and every supported release platform row
must appear in every route class.

Six non-omittable orthogonal variants cover symmetric NAT, consent loss,
deliberate P2P failure, required TURN outage, required sealed-relay outage, and
regional relay outage, with at least 30 attempts per variant. Native-IPv6 and
distinct home-NAT cells are release-blocking P2P-success cells: direct P2P must
reach at least 95% observed success and a 95% Wilson lower bound of at least
90%. Other attempt-required cells report P2P separately while allowing an
approved fallback to satisfy supported-route success. Captive
portals before user authentication and networks blocking all outbound traffic
are outside the supported state, but neither exclusion permits omitting a
required cell or variant.

## Distribution Decision

Android uses Google Play closed testing followed by staged production with Play
App Signing, a separate upload key, and signed AABs. Store rollback means halting
the rollout and issuing a higher-version forward fix; it does not mean installing
a lower `versionCode`. The official Android signing guide explains the upload-key
and Play App Signing split:
[Android app signing](https://developer.android.com/studio/publish/app-signing).

macOS uses direct distribution for V1: Developer ID Application signing,
hardened runtime, secure timestamp, notarization, stapling, and one signed DMG.
PKG distribution is outside the V1 decision, so this plan does not require or
claim a Developer ID Installer identity. V1 uses manual signed updates rather
than adding a new updater. Apple
documents the Developer ID and notarization requirements here:
[Developer ID certificates](https://developer.apple.com/help/account/certificates/create-developer-id-certificates/)
and [macOS notarization](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution).

The current Android `targetSdk=36` already matches the Google Play requirement
announced for new apps and updates from 2026-08-31, but that policy is checked
again at every RC because store rules change:
[Google Play target API requirements](https://support.google.com/googleplay/android-developer/answer/11926878?hl=en-GB_ALL).

The final Android application ID and macOS bundle ID are deliberately `null` in
the machine record. A reverse-DNS-looking name is not treated as owned merely
because it appears in source. The IDs must be reserved in the actual Apple and
Google accounts before build configuration or migration lineage changes.

## Security And Recovery Decision

G0 retains the existing `production_p2p_nat_v1_recommended` two-plane profile
without supersession:

1. authenticated and encrypted ICE for eligible direct traversal;
2. bounded TURN as the ordinary ICE relay candidate;
3. sealed AetherLink relay-only signaling as mandatory rollback and emergency
   fallback;
4. one transport-neutral endpoint-identity session as the only
   application-readiness gate on every path.

The seven immutable pre-network choices in
`production_p2p_nat_v1_pre_network_decision_v1` remain effective. The older
selection profile still lists their original questions, so this G0 record
normalizes the effective state: policy is selected, while concrete operational
owners remain unresolved.

The relay control plane selects TLS 1.3 plus canonical signed lease
capabilities. Public endpoints use WebPKI for channel authentication, while an
app-bundled offline AetherLink root signs the versioned service configuration and
delegates a non-exportable online lease signer. Production service domains are
not yet selected; domain ownership, DNS-change authority, WebPKI issuance,
renewal/revocation, and takeover response are a separate G0 blocker. The
capability shape must remain compatible with a future split between allocation
authority and blind relay. A relay is never the endpoint trust terminator and
never receives traffic keys.

Pair recovery selects a monotonic `pair_epoch` state machine. Normal renewal is
co-authorized by runtime and client. Either current endpoint may perform
deny-only emergency revocation, accepting a deliberate denial-of-service risk
instead of allowing silent one-sided key replacement. Replacement requires a
fresh QR, a higher pair epoch, a fresh endpoint traffic secret, and a rotated
route-token seed. Every lease, registration, endpoint transcript, route refresh,
and application authentication binds both `pair_id` and `pair_epoch`. An
offline endpoint must obtain a current signed state receipt before reactivation.
Signed transition receipts and read-only `pair.status` reconciliation recover
a lost response without creating another transition.

The existing platform-native P-256, HKDF-SHA-256, and AES-256-GCM Phase A profile
is only the G1 starting input. G1 must ratify the exact provider, transcript,
canonical encoding, route authorization kind/digest, key schedule, and negative
vectors before it becomes a production profile.

## Route Authorization Contract

The common secure-session transcript carries a typed
`route_authorization_kind` and canonical digest.

- Local direct uses QR-pinned pair state and a nominated local path receipt; it
  never depends on a service lease or service capability.
- Service-mediated P2P candidate publication and fetch each require their exact
  signed, pair-scoped capability. P2P direct also binds rendezvous/candidate
  generation and ICE path validation. Capability-free remote P2P is forbidden
  without a superseding versioned decision.
- Sealed relay and TURN require the signed capability/lease and exact allocation
  and path context.
- A digest from one route kind cannot be reinterpreted as another kind.

## Privacy And Operations Floors

Production connectivity services must not receive model lists, prompts,
responses, files, memory, provider URLs, backend credentials, or traffic keys.
Network components necessarily observe bounded addressing while routing, but
raw candidates, raw IP addresses, and stable pair identifiers must not enter
application logs, metrics, or retained evidence. The selected default retention
is:

| Data class | Maximum retention |
| --- | --- |
| Aggregate operational metrics | 30 days |
| Source-free security reason events | 7 days |
| Sanitized incident evidence | 90 days |
| Content-free release records | 365 days |
| Expired capability/live authorization state | expiry plus 30 seconds |

Capabilities last at most 600 seconds with at most 30 seconds of clock skew.
The offline root requires offline HSM or cold custody and two-person approval.
The delegated signer must be non-exportable in KMS/HSM with overlap rotation.
Emergency revocation authority is separate from release-signing authority. The
actual people, service, region, and custody provider remain G0 blockers rather
than invented repository facts.

## Quality And Release Gates

The following are release targets, not current results:

- At least 1,200 completed authenticated sessions across the required network
  matrix, at least 100 attempts in every required topology cell, and at least 30
  attempts in every required orthogonal variant.
- Each cell has at least 99% observed authenticated success and a 95% Wilson
  lower bound of at least 95%; aggregate success cannot hide a failing cell.
- Each P2P-required-success cell also has at least 95% observed direct-P2P
  success and a 95% Wilson lower bound of at least 90%; fallback success cannot
  satisfy this separate release gate.
- Traversal setup: p50 at most 1.5 seconds, p95 at most 5 seconds, p99 at most
  10 seconds. Full cold setup: p95 at most 8 seconds and p99 at most 15 seconds.
- Authenticated reconnect p95 at most 5 seconds, network handoff p95 at most
  10 seconds, revocation closure p95 at most 10 seconds and p99 at most
  30 seconds. Revoked authorization retained state also has a hard absolute
  closure maximum of 30 seconds; a percentile cannot hide a slower retained
  state instance.
- Incremental memory p95 at most 24 MiB on each endpoint. Android battery use is
  at most 0.25% per hour while idle-paired and 2% per hour during an active
  session.
- Closed beta crash-free and ANR-free session rates are each at least 99.5%, and
  the RC includes at least one 24-hour soak with no crash or ANR.
- False abuse rejection is at most 0.1%. Prohibited-destination I/O, plaintext
  downgrade, false identity acceptance, duplicated non-idempotent requests, and
  protected-data leakage each have a zero allowance. Rollback failure, security
  state rollback, traffic after consent loss or revocation, unauthorized service
  acceptance, unauthorized release-artifact acceptance, release-artifact
  provenance failure, route-authorization bypass, and a revocation closure
  deadline miss also each have a zero allowance.
- Every required rollback drill must succeed; rollback success is exactly 100%.
- Capacity passes at twice the approved projected peak without unbounded growth
  or weaker admission. The projected peak and cost ceiling are still blockers.

Each target is assigned to one of four versioned measurement contracts:
network reliability/latency, endpoint resource/stability, abuse/capacity, or
security hard stops. The machine record fixes the owner role, measurement
source, sample/window rule, and failure action for each contract. The named
people or accountable teams still do not exist in repository evidence, so the
quality contracts remain a G0 blocker rather than becoming release SLOs merely
because numeric thresholds were written down.

The CI ladder is `pr_fast`, `merge_full`, `nightly_product`,
`controlled_network_nightly`, `weekly_resilience`, and `release_candidate`.
Local no-device evidence, physical same-LAN evidence, controlled external
network evidence, signed RC evidence, and production rollout evidence remain
separate claims.

## Open G0 Blockers

| Blocker | Required closure evidence |
| --- | --- |
| G0 assurance artifacts and baseline gate | Versioned threat model, protocol/data-flow inventories, risk register, release checklist, observability schema, incident/rollback runbook, plus separately authorized full no-device and release-compile passes |
| Roadmap/G0 checkpoint publication | Explicitly reviewed commit scope and an intentional published checkpoint |
| Production application namespaces | Android application ID and macOS bundle ID reserved in owned accounts |
| Distribution accounts and key owners | Named Google Play and Apple Developer owners plus custody runbook |
| Provider compatibility baseline | Named owner plus versioned minimum/current/previous Ollama and LM Studio matrix |
| Service domain, DNS, and WebPKI owners | Owned service domains plus named DNS-change, certificate issue/renew/revoke, and takeover-response owners |
| Service root and online signer owners | Named root custodian, KMS/HSM owner, rotation owner, and emergency revoker |
| Privacy, incident, and retention owners | Named approvers for redaction, deletion, retention, and incident response |
| Quality measurement owners | Named owners approving every measurement source, sample/window rule, and failure action |
| Relay region, capacity, and cost | Approved initial region, projected peak, capacity target, and cost ceiling |

These are G0 exit conditions; most are ownership decisions rather than missing
product code. G0 remains
`blocked_before_g1a` until all ten have evidence. The first blocker also prevents
the owner-only blockers from being mistaken for the whole exit gate. Minimum
provider compatibility and its named owner must close in G0; exact RC versions
are then frozen under the selected current-plus-previous policy. Missing future
physical devices are G5/G6 evidence gaps rather than G0 authority.

The assurance machine record defines the exact closure crosswalk from these ten
blockers to all nine G0 checklist items, all fourteen accountable roles, and the
evidence kinds required at G0. Risk evidence is separately tagged with its
required gate, so G2/G4/G5/G6 results remain release obligations without being
misrepresented as G0 prerequisites. This crosswalk is a derivation contract,
not evidence and not approval.

## Authority Boundary And Next Gate

This packet authorizes only G0 documentation and local static validation. It
does not authorize G1a implementation, even if that code would avoid network
I/O. It also leaves source acquisition, P2P library selection or compilation,
socket creation including loopback, DNS, STUN/TURN, ICE, runtime or external
network I/O, production keys, signing, notarization, store upload, and deployment
closed.

After all blockers close, a separate `g1a-no-network-authority-v1` record must
name the allowed first-party files, schemas, compilers, tests, and temporary
stores while continuing to forbid sockets, dependencies, live services, active
protocol advertisement, and production keys. A new P2P candidate must start a
fresh candidate/version authority chain; neither rejected candidate nor consumed
authority can be reused.

Changing to a single fallback plane requires a new versioned decision that
explicitly supersedes both the current P2P profile and immutable
`selection-decision.json`, then re-approves the fallback state machine, vectors,
security manifest, rollback, and release evidence. The pre-network decision
also requires explicit supersession if any of its seven selected policies
changes. This V1 decision performs none of those supersessions.
