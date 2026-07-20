# AetherLink V1 G0 Assurance Packet

Assurance ID: aetherlink_v1_g0_assurance_v1

Status: blocked_before_g1a

Recorded: 2026-07-20

This is the human review companion to
docs/v1/g0/assurance-v1.json. The JSON record is the only machine-readable
authority. It is bound to G0 decision aetherlink_v1_g0_decision_v1,
implementation revision d32c1846eead13ab1462619145fc4da1194cce7e, and the
exact source hashes listed in that record.

This packet is a static inventory and assurance baseline only. It does not
claim that the full no-device aggregate, release compilation, physical-device
matrix, controlled external-network matrix, signed release candidate, or
production rollout has run. It does not authorize G1a implementation, source
acquisition, compilation of a P2P dependency, socket creation including
loopback, network I/O, production keys, signing, upload, or deployment.

## Evidence Boundary

The evidence classes remain deliberately separate:

1. static/no-device evidence;
2. physical-device evidence;
3. same-Wi-Fi debug evidence;
4. controlled external-network evidence;
5. signed release-candidate evidence;
6. production-rollout evidence.

Success in one class cannot satisfy another. In particular, prior same-Wi-Fi
debug pairing is not production relay, P2P, NAT, signing, or distribution
evidence.

The assurance packet hashes 29 source records. These include the immutable P2P
selection and pre-network records, current architecture and protocol
documentation, the current P2P threat and hardening records, both protocol
schemas, the Swift and Kotlin protocol models, and representative Android/macOS
local-storage boundaries. Hash drift makes the packet invalid until a reviewed
new assurance version is created.

## Protocol Inventory

The active runtime envelope is
https://aetherlink.dev/schema/protocol.v1.json; the pairing QR is a separate
https://aetherlink.dev/schema/pairing-qr.v1.json contract. The machine record
pins all 46 active message types and all 40 active error codes, then groups them
into nine review units:

| Unit | Baseline state | Acceptance boundary |
| --- | --- | --- |
| Pairing QR v1 | active current | Decode the rendered QR and validate the active route and pairing session |
| Runtime envelope v1 | active current | Schema, Swift, Kotlin, direction, and payload parity |
| Pairing and auth | active current | Identity/auth negative vectors, health, and trusted reconnect |
| Route refresh and relay allocation | active current | Development routes stay non-production; production downgrade is rejected |
| Runtime health and models | active current | Approved provider matrix with sanitized failures |
| Chat, stream, cancel, and history | active current | Streaming, terminal, cancel, attachment, and duplicate-request regression |
| Memory and retrieval | active current | Runtime-owned authority and stale-client-cache replacement |
| Error taxonomy | active current | Closed enum parity and unknown-code rejection |
| Reserved namespaces | selected, not implemented | Must remain absent from active schema and routers before G1 authority |

The namespace inventory is derived from the active protocol checker rather than
maintaining a smaller parallel list. It guards 35 prefixes: skills., mcp.,
web_search., python., projects., automation., permission., approval., audit.,
file., terminal., network., backend., embeddings., retrieval., index.,
research., citation., source_anchor., trusted_source., source_control., p2p.,
rendezvous., bootstrap., dht., nat., stun., turn., session., key_exchange.,
encrypted_session., anti_replay., transport., crypto., and route. The only
active exceptions are the exact current retrieval, index, research, citation,
source-anchor, trusted-source messages and route.refresh recorded in the
machine contract. Every other name under those guarded prefixes is rejected.

Authenticated encrypted ICE, bounded TURN, the sealed emergency fallback,
transport-neutral endpoint identity, TLS 1.3 signed capabilities, monotonic
pair_epoch, and read-only pair.status reconciliation are selected but not
implemented. P-256/HKDF-SHA-256/AES-256-GCM remains only a G1 candidate; the
exact suite, transcript, encoding, and providers are not frozen by G0.

## Route Authorization

The route authorization contract is fail-closed:

- Local direct does not need a service lease or capability.
- Service-mediated P2P candidate publication requires candidate_publish
  capability.
- Service-mediated P2P candidate fetch requires candidate_fetch capability.
- TURN and sealed relay require their exact signed capability or lease.
- A capability-free remote P2P mode is forbidden until a superseding
  versioned decision.
- A route authorization digest cannot be reinterpreted across route kinds.

Capabilities bind pair digest, endpoint role, generation, service, kind,
expiry, quota, and nonce. Revocation denies new operations immediately and
closes every retained authorization state instance within an absolute maximum
of 30,000 milliseconds. Pair recovery separately binds pair_id and pair_epoch
to every lease, registration, endpoint transcript, route refresh, and
application authentication. Replacement requires a fresh QR, a higher epoch, a
fresh endpoint traffic secret, and a rotated route-token seed. An offline
endpoint cannot reactivate until it obtains a current signed state receipt, and
pair.status remains read-only.

## Data-Flow Inventory

Sixteen flows cover the complete current and selected V1 trust-boundary set. The
first seven cover the required user loop:

1. pairing QR/deeplink to parser, authenticated pairing, and trusted stores;
2. route selection through local or selected future transport to the
   transport-neutral authenticated runtime router;
3. authenticated route refresh to atomically replaced Android secure route
   state;
4. runtime health and model operations through macOS-only Ollama/LM Studio
   adapters;
5. chat, attachments, memory context, streaming, cancellation, and runtime
   history;
6. runtime-owned memory, retrieval, citations, research, and trusted-source
   state;
7. content-free operational, security, incident, and release observability.

Nine selected-not-implemented flows keep the production control and release
supply-chain planes explicit:

8. endpoint to rendezvous candidate publish/fetch under exact pair capability;
9. endpoint to approved STUN service for observation only, never endpoint trust;
10. endpoint to a policy-approved candidate target for bounded ICE checks;
11. endpoint to TURN or sealed relay with signed lease and opaque E2E packets;
12. endpoint to allocation authority, with service authentication before
    allocation credential, route-token, or identity-proof disclosure;
13. endpoint to pair-state authority for deny-only revoke, fresh-QR replace,
    and authenticated read-only status reconciliation;
14. allocation authority to endpoint/relay for signed configuration, keyset,
    lease, revocation state, and signed pair-state receipts;
15. Android source/CI through Play App Signing, store readback, install/update,
    and higher-version forward-fix lineage;
16. macOS source/CI through Developer ID, notarized and stapled DMG readback,
    install/update, and monotonic-state-preserving rollback.

Android never calls Ollama or LM Studio directly. Provider URLs, credentials,
prompts, responses, files, memory, model lists, and traffic keys remain outside
connectivity services. The macOS Runtime is authoritative for AI execution,
history, memory, retrieval, research, and provider state. Android persistence is
a sanitized and replaceable continuity cache except for its endpoint identity,
trusted pair metadata, and keystore-backed secret references.

Every flow records its data classes, trust boundaries, authorization gate,
persistent stores, service-visible data, forbidden data, retention rule,
failure mode, source references, owner role, acceptance method, and mapped user
loop IDs.

## Threat-Model Refresh

The packet retains existing threats T001 through T016 without rewriting their
history. It preserves the protected assets, actors, and trust boundaries from
the P2P/NAT threat model and adds:

| Threat | Added V1 concern | Release hard stop |
| --- | --- | --- |
| T017 | Allocation-service impersonation or unsigned lease substitution | Unauthorized service acceptance |
| T018 | Online signer compromise or keyset/config rollback | Security-state rollback |
| T019 | Pair epoch, revocation counter, or backup rollback | Security-state rollback |
| T020 | Silent one-sided replacement-key installation | False identity acceptance |
| T021 | Revocation fanout failure or duplicate transition | Revocation closure deadline miss |
| T022 | Pair/candidate/route correlation through logs | Protected-data leakage |
| T023 | Service-mediated publish/fetch without capability | Route-authorization bypass |
| T024 | Android namespace/signing lineage or Play artifact substitution | Unauthorized release-artifact acceptance |
| T025 | macOS bundle/Developer ID/notary/DMG substitution | Unauthorized release-artifact acceptance |
| T026 | Release CI provenance, update-lineage, or rollback artifact tampering | Release-artifact provenance failure |

The common fail-closed invariants require complete, fresh, generation-bound
route material; destination policy before candidate I/O; the same endpoint
identity authentication on direct, TURN, and sealed paths; no stale credential
or monotonic-state reuse; immediate traffic stop after consent loss; bounded
state; absolute revocation closure; and no production downgrade.
The release supply chain also fails closed on an unowned namespace or bundle
identifier, missing source-to-artifact provenance, invalid Play or Developer ID
lineage, absent notarization/stapling/readback, or exposure of release private
keys and distribution credentials.

## Risk Register

Ten release-blocking risks are registered:

1. protocol/schema/code/document drift;
2. production namespace, signing, and distribution custody;
3. service DNS, WebPKI, root, and signer compromise;
4. pair-recovery denial of service and stale state;
5. relay abuse, capacity, outage, and cost;
6. Ollama/LM Studio compatibility;
7. privacy, logging, and retention;
8. local-store corruption or stale client cache;
9. unsupported device/network/provider evidence gaps;
10. rollback of monotonic security state.

Each risk has affected assets, likelihood, impact, treatment, residual risk,
owner role, acceptance state, required evidence, and linked G0 blockers.
Critical and high risks remain blocked_unassigned; none is silently accepted
and none is converted into implementation authority.

Every required-evidence entry is a pair of `evidenceKind` and `requiredByGate`.
Only entries tagged `g0` participate in G0 closure. Entries tagged G2, G4, G5,
or G6 remain mandatory release evidence at those later gates, but cannot be
promoted into G0 or used to claim that a G0 owner decision has been satisfied.
The risks remain release-blocking until every gate-specific obligation is met.

## Closed Observability Schema

Unknown event kinds and unknown fields are rejected. The service allowlist is
limited to content-free version, kind, reason, outcome, bounded route/candidate
class, address-family/region buckets, version values, latency buckets, and
aggregate counts. Release-harness records have a separate allowlist for the
campaign, immutable evidence digest, exact supported platform row, measurement
contract, metric identity, raw value, threshold/operator, sample/window,
provider adapter, matrix cell/variant, route outcomes, and capacity forecast.

Every allowed field has a machine-enforced type and closed domain: fixed enums,
bounded numeric ranges, anchored patterns, or an approved registry reference.
Every event class has required fields as well as allowed fields. Region values
cannot be emitted until the approved release-region registry exists. Version,
count, byte, latency, memory, battery, and revocation values have explicit
ranges; revocation closure cannot exceed 30,000 milliseconds. Free-form strings
are not an allowed value domain.

The following are forbidden in every observability event:

- prompt, response, model list, file body/snippet, and memory;
- provider/backend URL or credential;
- traffic secret, private key, frame key, pairing code/nonce, or QR payload;
- route token, capability, TURN credential, or relay secret;
- raw candidate, IP, hostname/port, envelope, packet, or signed blob;
- device ID/name/fingerprint or stable pair/session/request identifier;
- source path or personal owner contact.

Nine closed event classes exist: route_attempt_outcome,
authenticated_session_outcome, p2p_direct_outcome, fallback_transition,
revocation_closure, service_capacity, security_hard_stop, release_gate_result,
and incident_state_transition. Every class has an exact field allowlist, maximum
field count, required-field set, value domains, retention class, deletion
trigger, and owner role. Five separate release-record classes cover network
measurements, endpoint resource/stability, abuse/capacity, security hard stops,
and rollback drills; they are
validated only against the release allowlist and cannot borrow service-event
fields. Their closed metric inventory covers every field in all four quality
measurement contracts, while device classes distinguish Android emulator APIs
26/30/33/36, the three physical Android rows, macOS 14/15/26 on arm64, and the
service control plane.

Each metric is bound to a positive minimum sample count, required context
fields, applicable platforms, and a campaign coverage rule. A record is valid
only after its content-addressed evidence bytes read back to the declared
SHA-256 digest and decode as the exact signed evidence envelope. The envelope
binds the campaign, build, record, metric, threshold, platform, closed context,
and complete finite nonnegative sample array. Its signer must exist in the
approved signer registry. Signer IDs must match the case-sensitive
`^release-evidence-[a-z0-9_-]{1,64}$` pattern before an exact registry-key
lookup, and an injected verifier must validate the Ed25519 signature over the
canonical payload. The unpadded base64url signature must strictly decode to
exactly 64 bytes and re-encode to the identical text, rejecting noncanonical
terminal bits before verifier dispatch. The registry does not exist until the
quality measurement owners activate it, so real release evidence remains
fail-closed while that G0 blocker is unresolved.

The signature input uses the machine-pinned
`aetherlink-release-evidence-canonical-json-v1` profile: UTF-8, ascending
Unicode-scalar object keys, no whitespace, minimal JSON control escaping,
literal non-ASCII UTF-8, and lowercase JSON literals. Numbers are nonnegative
base-10 integers or fractions with no exponent, at most 16 integer digits and
six fractional digits, trailing fractional zeroes removed, and negative zero
rejected. Numeric encoding is exact and independent of the ambient Decimal
precision or trap context. A fixed canonicalization test vector and a full
16-integer-plus-6-fractional-digit regression pin exact bytes for independent
harness implementations. An evidence envelope is limited to 4 MiB and 100,000
samples, and both limits are checked before signature verification or
percentile sorting.

Observed rates, Wilson lower bounds, rollback success, abuse rates, and count
metrics are recomputed from the signed samples. Latency, resource, revocation,
and soak values use nearest-rank p50/p95/p99 or the required absolute maximum
from those samples; a self-reported scalar cannot replace them. Capacity passes
only when the signed offered-load sample and closed context show offered load
divided by the approved projected peak is at least 2.0 and both
unbounded-growth and admission-weakening counts are zero. Arbitrary bytes,
unknown envelope fields, an unapproved signer, an invalid signature, a missing
sample, or a scalar/sample mismatch are rejected. The campaign validator rejects
a missing one of the 41 metrics, any required
cell/variant/provider/platform-row/route-class/region combination, a failed
record, or inconsistent campaign/build/version identity.

Required network variants cannot reuse a baseline-cell result. Baseline cell,
P2P, traversal, and handoff coverage requires `network_variant=none`; each of
the six required variants instead carries one signed raw observation per sample
and attempt. Array order is exactly one-based `attempt_index` 1 through
`sample_count`. Every observation has an affected plane or approved region,
direct and fallback results, outage-active result and route, integer
millisecond offsets measured from the start of that variant attempt, and zero
plaintext, identity, weaker-route, and post-consent-loss traffic counts. All
offsets are within 0 through 120,000 inclusive. Activation must precede its
result; variants that require recovery must then record result before restore
and restore before authenticated recovery. Non-recovery variants instead use
null restore/recovery offsets and `not_required` recovery outcomes.

Each evidence record is one homogeneous outcome-and-route cohort: every
observation's direct result, fallback result, and rule-selected outage or
recovery route must equal the record's aggregate fields. Individually valid
mixed combinations require separate records; no implicit majority, first-wins,
or worst-case aggregation is allowed. The validator then applies the decision-
bound table. TURN outage accepts only
sealed authenticated service or `none` while the outage is active, followed by
an authenticated TURN recovery after restore. Sealed-relay and single-region
outages must record `none` during the outage and recovery on the restored
approved plane; the regional case also requires the approved region in both
the record and every signed observation. Therefore a success on the plane that
was declared unavailable, a missing phase, or a bare `variant_outcome` string
cannot satisfy campaign coverage merely by reporting 30 attempts.

Retention maxima are 30 days for aggregate operational metrics, 7 days for
source-free security events, 90 days for sanitized incident evidence, and 365
days for content-free release records. Live authorization state is removed no
later than expiry plus 30 seconds.

## Release Checklist

The G0 checklist is still blocked. The assurance packet itself needs immutable
hash/readback and owner acceptance. The full no-device aggregate needs separate
socket authority because the current gate opens loopback sockets. Android and
macOS release compilation are not run. The roadmap checkpoint, namespaces,
distribution accounts and key custody, provider baseline, service identity and
signer custody, privacy/incident/quality ownership, and relay
region/capacity/cost all still require external evidence.

`assurance-checkpoint-readback-v1.json` is a content-addressed local candidate
for the first two mechanical observations: it recomputes this assurance JSON's
raw and canonical hashes and reads all 29 declared source files as exact regular
non-symlink bytes. The validator checks the decision digest before parsing,
limits JSON integers to 128 digits and each source to 4 MiB, reads and hashes on
one no-follow descriptor, then reopens the repository path to reject namespace
replacement. Its status is `candidate_observed_not_immutable`; it has no owner
acceptance or publication root, is not referenced as checklist evidence, and
does not close either G0 blocker or authorize G1a.

The machine-only `g0ClosureContract` removes promotion ambiguity by mapping all
ten decision blockers to all nine G0 checks, the fourteen accountable owner
roles, and exact G0 evidence kinds. It fixes the shapes of owner-acceptance,
evidence-catalog, gate, and publication receipts. An accepted owner receipt must
bind an opaque accountable identity reference, the SHA-256 of the exact
published checkpoint bytes, the Git commit containing that checkpoint, the
non-empty role-scoped blocker IDs, a UTC timestamp, and non-empty verified
evidence IDs. The blocked state instead requires null identity/bindings and
empty blocker/evidence lists. Gate receipts require a closed G0 check ID, exact
versioned authorization and immutable command-profile IDs, publication commit,
ordered UTC timestamps, integer zero exit status, passed result, and sanitized-log digest. Evidence catalog
records bind the implementation revision and checkpoint digest to a repository-
relative sanitized artifact and its verification result. No such receipt or
catalog exists in this candidate.

The current checker intentionally exposes no API that can accept a future
receipt. Receipt activation is forbidden until a successor adds a module-owned,
factory-only, deeply immutable validation context built from the canonical
closure contract, independently read commit-tree and remote checkpoint bytes,
authenticated evidence artifacts, exact authority/command bindings, trusted-
runner attestations over actual sanitized logs, and authenticated owner
acceptance. Receipt values may never create their own trust anchors. Partial,
duplicate, or ambiguous bundles must fail before blocker derivation.

Publication is necessarily two-stage. First, an explicitly reviewed commit
publishes the current packet. A remote readback then binds that commit object to
the exact expected repository, checkpoint path, and digest, verifies that the
commit tree contains those exact checkpoint bytes, and requires the remote
readback digest to match. Owner and authorized-gate receipts can only accept
that verified published identity; a successor versioned checkpoint may then
carry those receipts and derived blocker states. Even complete G0 receipts do
not open G1a: a separate versioned G1a authority record is still required.

The future promotion checklist keeps G1 through G7 evidence separate:

- exact wire/crypto and cross-platform negative vectors;
- service identity, signed configuration, keysets, lease, and revocation;
- authenticated P2P, TURN, and sealed fallback per network cell;
- monotonic pair recovery and absolute revocation closure;
- signed Android/macOS artifacts and device/provider/localization/accessibility
  matrices;
- twelve topology cells, six orthogonal variants, soak, capacity, and outage
  results;
- all security hard stops, privacy scans, incident and rollback drills;
- provenance, staged rollout, store/service readback, and final release
  disposition.

A checklist item can become passed only with non-empty immutable evidence. A
waiver requires a versioned waiver and approver. Aggregate success cannot hide
a failed cell or variant.

## Incident Runbook

Seven incident classes are closed in the machine record:

1. endpoint loss or key compromise;
2. DNS, WebPKI, service root, or signer compromise;
3. relay abuse, capacity, or regional outage;
4. protected-data or log leakage;
5. provider compatibility regression;
6. bad Android or macOS release;
7. pair-epoch or revocation divergence.

Each class defines triggers, severity, incident commander role, containment,
fail-closed action, credential/state rotation, sanitized evidence preservation,
recovery criteria, communication owner, and drill evidence. No real
credentials, personal contacts, QR payloads, pairing secrets, or route secrets
belong in this packet.
Endpoint compromise and pair-epoch divergence recovery explicitly require a
fresh endpoint traffic secret and rotated route-token seed whenever replacement
occurs; a fresh QR and higher epoch remain mandatory.

## Rollback Runbook

Every required rollback drill must pass; rollbackSuccessMinimum is 1.0.

- Android rollback means halting rollout and shipping a newly signed AAB with a
  higher versionCode.
- macOS may restore only the current or previous approved, notarized, stapled,
  signed DMG when the state is compatible.
- Protocol floor, service-config version, keyset version, pair epoch,
  revocation counter, and lease generation never decrease.
- TLS, identity, signature, or service failures never enable plaintext,
  anonymous, unsigned, or legacy production fallback.
- An outage uses only an approved authenticated alternate plane; otherwise it
  fails closed.
- Recovery reruns artifact provenance, identity/auth, health/model, chat/cancel,
  reconnect, revoke/fresh-repair, monotonic-state readback, and all zero-budget
  security gates.

The zero-allowance hard stops are prohibited destination attempts, plaintext
downgrades, false identity acceptance, duplicate non-idempotent requests,
protected-data leakage, rollback failures, security-state rollbacks, traffic
after consent loss or revocation, unauthorized service acceptance,
unauthorized release-artifact acceptance, release-artifact provenance failures,
route-authorization bypasses, and revocation-closure deadline misses.

## Owners, Acceptance, And Remaining Gate

All accountable roles are explicit placeholders. Each `ownerIdentityRef`,
`acceptedRevision`, `acceptedPublicationCommit`, `acceptedAt`, and acceptance
evidence list remains empty; each `acceptedBlockerIds` list is empty and status
is `blocked_unassigned`. The repository contains no authority to invent people,
accounts, domains, regions, custody providers, budgets, or external approvals.

The packet currently reports no contradictions and no missing hard stops, but
that means only that its static schema is internally closed. It does not close
g0_assurance_artifacts_and_baseline_gate, because owner acceptance, a published
checkpoint, the separately authorized full no-device aggregate, and both
release compilation results remain absent. All ten G0 blockers remain listed.

The separate local readback candidate reduces ambiguity about the current
assurance bytes and their 29 source inputs only. Until an external reviewed
publication root and accountable owner acceptance exist, its validator constant
is local integrity evidence rather than immutable release provenance.

G1a remains closed. Only after every G0 blocker has immutable evidence may a
separate g1a-no-network-authority-v1 record be created. That later record must
continue to forbid sockets, live services, dependency acquisition, production
keys, active protocol advertisement, signing, upload, and deployment unless
still later gates explicitly open them.
