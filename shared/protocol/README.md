# Shared Protocol

Protocol definitions shared by AetherLink clients and runtime hosts.

The working protocol notes live in [docs/protocol.md](../../docs/protocol.md). The versioned JSON schema lives in [packages/protocol-schema/protocol.schema.json](../../packages/protocol-schema/protocol.schema.json).

v0.1 protocol scope:

- JSON message envelope.
- Connection and pairing messages.
- Model list messages.
- Streaming chat messages.
- Cancel generation messages.
- Basic runtime-owned memory messages.
- Error messages.

MCP, skills, web search, advanced memory search/reflection, and other future roadmap namespaces are reserved only. They are not active protocol capabilities yet.

## Production Secure-Session Route-Binding Vectors

`fixtures/production-secure-session-route-binding-v1-vectors.json` is the
cross-platform G1a-A oracle for the socket-free `ALS1` canonical contract. It
contains all six typed route authorizations and their six 21-field endpoint
secure-session transcripts, with canonical byte counts, exact lowercase hex,
and SHA-256 digests. Swift and Kotlin tests decode, re-encode, digest, bind, and
mutate these vectors independently.

These objects are not active JSON messages and do not open a socket, signaling
namespace, connector, STUN/TURN transaction, relay, key derivation, or encrypted
record path. Product pairing and endpoint authentication remain required.

## Production Pair-State And Admission Vectors

`fixtures/production-pair-state-admission-v1-vectors.json` is the G1a-B
cross-platform oracle for `ALS1` type-8 authority state and type-9 local
snapshots. It pins one authority, its empty snapshot, one admitted snapshot and
permit, five transition cases, and seven admission/malformed cases. Eight Swift
tests and eight Kotlin tests independently verify canonical bytes and SHA-256,
monotonic transition outcomes, replay/revocation/capacity rejection, lifetime
transition-ID reuse rejection, epoch-advance denial, and exact admission parity.

The authority object carries product pair state; the snapshot additionally
carries local durable revision and at most 64 consumed session/transcript
tombstones. An advanced snapshot also carries at most 20 prior transition ID
and request-digest pairs; an empty history retains the original five-field
canonical bytes, while a non-empty history uses the bounded seven-field form.
Epoch advancement remains fail-closed until signed fresh-pair proof is defined.
These objects are not active JSON or wire messages, do not verify a signature
by themselves, and do not construct a production connection, derive keys,
protect records, or perform network I/O.

## Production G1a-C Authority, Candidate, Receipt, And Grant Vectors

`fixtures/production-g1a-c-v1-vectors.json` is the base G1a-C authority/route
oracle at SHA-256
`c25c0f4d74b0029f060bcedf31b19ef95c57a0a0e6708a741175c8cedeb611f3`.
`fixtures/production-g1a-c-candidate-v1-vectors.json` is the additive candidate
oracle at SHA-256
`e6bc666dbf9fded82d5681fdcfdc2c4c9cd5fa197135fc0673569d35656236af`.
The latter preserves the former byte-for-byte and adds exact canonical objects
23 through 28 plus the object-7 candidate-session transcript.

Independent Swift and Kotlin consumers verify the root-signed service keyset,
signed object-23/24 candidate capabilities, object-27 endpoint proofs, and four
fixed-order signed post-commit object-28 receipts on one adjacent revision/state
ledger. They then derive unsigned object-25 grant evidence, project unsigned
object-26 authorization, and require object 7 to commit to the exact SHA-256 of
object 26. Same-version keyset forks, receipt reordering/duplication/cross-ledger
mixing, legacy object-4 transcript authority, special-purpose destinations, and
generic P2P admission fail closed.

The candidate fixture explicitly records
`durabilityScope=synthetic_contract_readiness_only` and
`productionDurabilityClaim=false`. These vectors do not activate a session,
derive keys, protect records, create sockets, perform network I/O, prove a
physical device, authorize deployment, or establish production readiness.

## Production Secure-Session Crypto Vectors

`fixtures/production-secure-session-crypto-v1-vectors.json` is the G1a-D
socket-free cryptographic oracle at SHA-256
`d45fd920e22652d790c742de995d87a8cbfb64bb22aca3b829cbad5b23485448`.
It content-addresses the unchanged candidate fixture, binds the exact canonical
object-7 transcript and verified object-26 authorization, and pins P-256 ECDH,
HKDF-SHA-256 root and directional epoch material, role-separated object-29 key
confirmations, and object-30 AES-256-GCM application/key-update records.

Swift, Kotlin, and an independent pure-Python oracle verify the exact bytes.
Platform tests execute the 26-case negative inventory, including key mismatch
and reuse, role reflection, confirmation conflict, replay/gap/future epoch,
tag/ciphertext mutation, failed-authentication counter stability, update
skip/duplicate/final-epoch behavior, size and epoch/session ceilings, expiry,
clock rollback, invalidation, and concurrent sequence uniqueness. The maximum
plaintext is 1,048,448 bytes and the resulting maximum canonical record is
1,048,551 bytes, within the 1,048,576-byte object ceiling.

These objects are not JSON messages or active transport frames. The crypto core
is not app- or transport-wired, performs no socket or network I/O, and does not
claim a physical device, deployed service, production route, or V1 release.

The platform implementations now retain the verifier-minted key-schedule
binding inside one exact-bound authority lease and one store-owned,
single-process publication gate. Read permits cover start, confirmation,
activation, seal, open, and their pre/post authority/live-resource fences;
durable authority writers drain readers, commit, fence the coordinator, wipe
crypto, and only then release publication. Pure precommit rejection and macOS
pre-rename failure preserve the prior session. Once an Android DataStore edit
is enqueued, cancellation or ambiguous persistence failure fences and wipes the
old authority; macOS post-rename directory-sync uncertainty does the same. Swift
also zeroizes the owner-backed storage of a post-fence-suppressed confirmation,
seal, or open result before releasing the read permit; small-ciphertext plus
confirmation/seal/open retained-owner and result-copy regressions pin that
behavior. An independent `Data` snapshot
already extracted by a caller is not retroactively zeroized. Bounded no-network
app/service caller bridges now reach the composition seam, which keeps the
encrypted publication boundary inside a concrete authority-bound channel:
Android `core:transport` exposes only a manager-owned one-use raw-route lease to
the composer, not a raw-channel alias or caller-provided scope. The lease creates
`ProductionRuntimeSecureChannelAdapter` with a manager-owned execution scope;
construction failure cancels that owned scope, and the adapter is registered
before handshake suspension. Under `stateLock`, `UNDISPATCHED` acquisition
linearizes the transition with physical connector entry: cleanup that wins
first prevents connector invocation, while an entered connector that has not
returned a handle still depends on connector timeout/interruption and closes
any late handle when it returns. Detached composition uses saturating raw-route
timeout addition plus a fixed 15-second handshake budget. The adapter's internal
deadline is separate from the manager timeout, whose `IOException` is classified
as `ProductionSessionSecurityRejected`. The adapter's internal deadline uses one
`PENDING` to `COMPLETED`/`TIMED_OUT` CAS plus an `UNDISPATCHED`
watchdog. Timeout-winning `IOException` dominates and suppresses the losing
error/cancellation; completion-winning external or composer
`CancellationException` preserves the exact object. Canonical
`resume(value, onCancellation)` handoff closes only undelivered values:
pre-delivery cancellation closes once without retry, while successful transfer
survives later acquisition `Job` cancellation. No permanent caller-`Job` binding
or `InternalCoroutinesApi` is used. The one-use receipt is committed only after
exact P2P session, object-7/object-26 binding,
route-kind, manager-owned generation, pre-commit route-expiry checks, and an
admission-to-commit wall-clock rollback check. Failure cleanup is
`NonCancellable`. Even when raw ignores close until it returns, the managed raw
wrapper checks open before and after send, fails closed after close, and
the tests observe actual late body-byte zeroization. Production relay remains fail
closed without a verifier-derived exact relay
route binding. Focused Android evidence is 79/79 (49/49 manager plus 30/30
adapter). The root independently reran full `core:transport --tests '*'`: 10
suites pass 163/163 with zero failures, errors, or skips; app
`compileDebugKotlin` plus `compileDebugUnitTestKotlin` also succeed. An
independent iterative audit found and fixed six P3 availability/lifetime races
in total; a final fresh re-audit reports no P0-P3 finding. The current root-
independent full Swift rerun passes 2,003 tests with two declared skips and zero
failures in 313.440 seconds. Those focused/full-module reruns alone were not a
completed full no-device gate run; the current full no-device gate exits zero.
macOS owns an exact one-use attachment,
generation cleanup, cancellation/late-result close, raw-handler admission, and
terminal mailbox drain before removal or replacement. Terminal teardown
synchronously invalidates an available/claimed capability before replacement,
then runs asynchronous abandon/close outside registry locks; there is no
plaintext fallback. Focused macOS evidence is 39/39 (17/17 composition plus
22/22 secure-channel) and 34/34 (6/6 production-pair-coordinator plus 28/28
manager), and the release build passes. The audit-found
cancellation/replacement P2 is fixed with a deterministic delayed-abandon
regression; final independent re-audit reports no P0-P3 finding. The bounded
Android caller path uses one renewable `AndroidProductionRuntimeActivationSlot`
for both route preparation and start-material claim. It holds at most one
verifier-derived, one-use `AndroidProductionRuntimeActivationPlan` per attempt,
uses the exact same `PairingStore`, compares the manager-selected exact route
object and prepared-session reference, and exposes only the manager-owned raw
lease. A generation-bound claimed entry stays slot-owned until transfer starts.
Close or replacement winning first discards its key; transfer winning first
moves cleanup ownership exactly once to the transfer object. Cancellation and
duplicate or concurrent completion fail closed, with at most one transfer
callback. Expiry, slot close, and ViewModel clear also discard still-pending key
material; after transfer, a fresh plan can be installed for a later attempt. The
public macOS `MacRuntimeProductionAcceptedSessionService` fixes one exact
`TrustedDeviceStore`, validates a verifier-derived exact accepted-route
descriptor, claims the endpoint once, and attaches it through the manager. A
service-owned pre-attachment generation covers suspended authority creation;
targeted `stop` and `stopAll` invalidate it before attachment, while `stopAll`
rotates an epoch so a late authority return is abandoned without disturbing a
fresh same-ID attempt. Descriptor, cancellation, stop, and store-admission
failures close untransferred keys. Focused Android evidence passes 16/16
composer plus 1/1 ViewModel-clear tests; the full app suite passes 1,174, and
complete core protocol, pairing, and transport suites pass 232/232, 200/200,
and 163/163. Focused macOS evidence passes 9/9 service tests and 54/54 manager +
service + composition tests (28 + 9 + 17); the release build succeeds.

G1b-A now gives the normal Android dependency graph one app-scoped
`AndroidProductionRuntimeActivationController` using the exact `PairingStore`
and trusted clock. It is intentionally empty until an upstream verifier and P2P
stack publish a verified attempt and already-connected one-use endpoint, so the
normal factory exposes no production route by itself. Injected real-fixture
tests exercise the manager and full ViewModel path through the authority-bound
secure channel, reject legacy fallback, complete the handshake, and exchange an
application record without opening an OS socket.
Publication generations are assigned before durable admission, so a delayed
older admission cannot displace a newer attempt. Close, cancellation, or
supersession reclaims the attempt-owned key and endpoint, including during
suspended admission, and displaced publication cleanup runs outside controller
locks. Focused controller tests pass 12/12; a final independent audit reports no
P0-P3 finding.

macOS now has a concrete `LocalPeerServer.startAcceptedRaw` primitive whose
listener policy is fixed to IPv4 loopback `127.0.0.1`. A bounded one-slot
authorization transfers one accepted session into the production composition
path only after handler installation; malformed, expired, stopped, or
unclaimed sessions fail closed. Its tests use injected connection I/O, do not
start the listener, and execute no socket. `CompanionAppModel` remains unwired.

This remains no live socket, network, physical-device, or production-release
evidence. The upstream verifier/candidate/secret producer and actual P2P
endpoint stack remain absent, actual socket close interruption is unproven, and
the eventual production caller must perform `seal + channel.send` inside the
same read-permit closure.

The separate G2 official-source preflight selects no library. Unmodified Pion
ICE v4.3.0 at commit `1e8716372f2bb52e45bf2a7172e4fb1004251c46` is
`rejected_at_official_source_preflight_as_is` for destination-policy, secret-
logging, callback-bound, and deterministic-shutdown gaps. No source was
retained, compiled, loaded, or executed and no socket/network rung was opened.
Repository-owner, GitHub, SSH, or GPG authentication is not a prerequisite for
this personal-project review; product pairing and endpoint session security are
separate requirements.

The follow-up [restricted-fork rung-one profile](../../docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/restricted-fork-profile.md)
leaves that rejection intact. It compares the as-is library, a wrapper-only
boundary, and one minimal policy-owned fork; only the fork shape may proceed to
preparation of a separate rung-two source-identity/acquisition decision. The
schema 1.1 design requires separate egress capability and ingress admission
boundaries, authenticated TURN TLS service identity, exact AetherLink
endpoint-confirmed pre-auth promotion, bounded session/process resources with a
sticky terminal latch, secret-free diagnostics, and a 2,500 ms close deadline.
Those controls are not implemented or runtime-verified. It also records the
future compile-only V1 architecture matrix and later SPDX SBOM, license, patch,
symbol, and reproducibility evidence. Its validator and 17 mutation tests pass.
No actual P2P backend, reliable ordered carrier, or fragmentation/reassembly
implementation is selected or implemented. This is a non-executable design
record; it activates no shared wire object, protocol message, transport path, or
network behavior.

G2 restricted-fork rung-one status contract:
`status=rung1_profile_complete_candidate_not_selected`,
`result=pion_restricted_fork_profile_ready_for_rung2_decision_only`, and
`nextAction=prepare_versioned_rung2_source_identity_and_acquisition_decision`.
Rung one completes only the design, validator, and 17 mutation tests;
`implementationStatus=not_implemented`, `candidateSelected=false`,
`librarySelected=false`, `sourceAcquisitionAllowed=false`,
`dependencyInstallationAllowed=false`, `compilerInvocationAllowed=false`,
`codeLoadingAllowed=false`, `socketCreationAllowed=false`,
`networkIoAllowed=false`, `deviceExecutionAllowed=false`,
`productionDeploymentAllowed=false`, and `gitOperationAllowed=false`. Schema 1.1
remains a not-yet-implemented and not-runtime-verified design. It
requires a separate single-use egress capability after resolution immediately
before socket create, bind, connect, TLS handshake, or write, plus fixed-size
bounded ingress read/parse/admission before state mutation or payload delivery.
It requires authenticated TURN TLS service identity before any credential
transmission and a bounded one-use pre-auth path whose atomic promotion occurs
only after exact AetherLink endpoint confirmation. Consent loss, path change,
candidate restart, capability expiry, verification failure, and session close
each atomically revoke both pre-auth and application capabilities before further
I/O, state mutation, event, or payload delivery. Exact per-session and process
bounds cover current, active, draining, and closing state, and event overflow
requires an independent sticky terminal latch. Secret-free diagnostics and a
2,500 ms total close deadline are requirements, not completed implementation or
runtime-verified behavior. The actual
backend, reliable ordered carrier, and fragmentation/reassembly remain unselected
and unimplemented. Only stack-neutral wiring may continue. Repository-owner,
GitHub, SSH, GPG, or
public-key identity proof is neither a prerequisite nor a future G2 rung;
`externalIdentityProofRequired=false` and `userActionRequired=false`. Product
pairing and endpoint authentication remain mandatory and separate.

The previous complete default no-device aggregate snapshot exits zero with
`No-device quality checks passed.` It records Python 182/182, 1,946 Swift tests
with two declared skips and zero failures, all Android Gradle invocations
`BUILD SUCCESSFUL`, and copy/docs hygiene across 94/12 files. Direct and
development-relay local mock smokes pass; relay freshness across 56 connections
and 905 encrypted
frame bodies at the ciphertext boundary, and the final G1a-D authority-lifecycle
marker. It is not physical-device, external-network, production-transport, or
production app/service activation proof. The new transport-composition marker
is registered for the next full aggregate; these prior counts were not
refreshed for this seam.

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](../../LICENSE).
