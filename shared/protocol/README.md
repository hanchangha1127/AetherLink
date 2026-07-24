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

The historical G2 official-source preflight selected no library. Unmodified Pion
ICE v4.3.0 at commit `1e8716372f2bb52e45bf2a7172e4fb1004251c46` is
`rejected_at_official_source_preflight_as_is` for destination-policy, secret-
logging, callback-bound, and deterministic-shutdown gaps. At that checkpoint,
no source was retained, compiled, loaded, or executed and no socket/network rung
was opened.
Repository-owner, GitHub, SSH, or GPG authentication is not a prerequisite for
this personal-project review; product pairing and endpoint session security are
separate requirements.

The follow-up [restricted-fork rung-one profile](../../docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/restricted-fork-profile.md)
leaves that rejection intact. It compares the as-is library, a wrapper-only
boundary, and one minimal policy-owned fork; at the recorded
`at_that_checkpoint` only
the fork shape could proceed to preparation of a separate rung-two
source-identity/acquisition decision. The
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
network behavior. Rung two has since consumed its exact one-use source request
and retained verified bytes without extraction. Rung-three v1 and v2 consumed
their distinct permits and failed closed before publication. The separate v3
one-use path completed a bounded lexical candidate inventory and tracked
readback. That predecessor recorded `rung3_v3_publication_read_back_complete`
and `prepare_separate_versioned_rung3_semantic_source_review_decision` at its
checkpoint. The tracked
[semantic-review decision v1](../../docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/semantic-source-review-decision-v1.json)
is now historical execution authority. The semantic-review checkpoint
[classifications](../../docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/semantic-source-review-classifications-v1.json),
[result](../../docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/semantic-source-review-result-v1.json),
and atomic [manifest](../../docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/semantic-source-review-manifest-v1.json)
record
`status=rung3_semantic_source_review_v1_publication_read_back_complete_semantic_closure_blocked`,
`result=two_non_attesting_full_coverage_semantic_passes_published_and_independently_read_back_patch_and_dependency_gaps_remain`,
and
`recordedNextActionAtThatCheckpoint=prepare_versioned_rung3_patch_and_dependency_closure_decision`.

That next action is now satisfied by the preparation-only
[patch/dependency decision v1](../../docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/patch-and-dependency-closure-decision-v1.json)
and its [security-hardening portfolio](../../docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/patch-and-dependency-closure-decision-v1/hardening.md).
At that checkpoint it recorded
`status=prepared_options_unselected_dependency_closure_blocked`,
`result=four_structural_recommendations_and_eight_unselected_treatment_units_prepared_all_19_findings_remain_open`,
and
`recordedNextActionAtThatCheckpoint=prepare_separate_versioned_implementation_or_dependency_review_decision`.
It maps all 19 findings to seven unselected root patch units and one unselected
dependency-review unit, and its read-only checker passes 28/28 checker tests.
The checker pins the complete 19-file portfolio, rejects unexpected artifacts,
schema claims, reader-facing effect drift, and replace-after-read drift, and
retains all input identities through its final readback.
Recommendations are not selections: all option, implementation, dependency,
closure, candidate, and library selection flags remain false. Source change,
dependency acquisition, compiler, socket, network, device, deployment, and Git
write remain unauthorized. Neither external authentication nor user action is
authorized or required.

The separate
[implementation-or-dependency review decision v1](../../docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/implementation-or-dependency-review-decision-v1.json)
and [staged fixed-point review plan](../../docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/implementation-or-dependency-review-decision-v1/implementation/staged-fixed-point-source-closure.md)
recorded at that checkpoint
`status=dependency_review_selected_acquisition_not_authorized`,
`result=staged_fixed_point_dependency_review_selected_all_19_findings_remain_open`,
and
`recordedNextActionAtThatCheckpoint=prepare_separate_versioned_bounded_dependency_source_identity_and_acquisition_decision`.
Exactly one portfolio option, `staged-fixed-point-source-closure`, and one
treatment unit, `dependency_source_license_security_closure_review`, are
selected for the dependency-review plan. The other seven portfolio options,
all seven root patch units, and the other three structural recommendations
remain unselected. The isolated read-only checker and 36/36 checker tests bind
the exact predecessor, semantic triad, retained archive and root metadata,
complete 19-file portfolio bundle, and review plan; they assert distinct raw,
selection, authority, finding, closure, contract, sequence, plan, inventory,
filesystem, and TOCTOU failure layers. All 19 findings remain open and
dependency acquisition, source modification/extraction, package management,
compilation, source load/execution, sockets, network, device, deployment, Git
writes, external authentication, and user action remain unauthorized or
unrequired.

The predecessor
[bounded dependency wave-one preparation decision v1](../../docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-v1.json)
records
`status=wave1_source_identity_and_request_contract_prepared_acquisition_not_authorized`,
`result=exact_19_root_requirement_source_identities_and_bounded_wave1_request_contract_prepared`,
and
`nextAction=prepare_separate_versioned_wave1_execution_permit_after_checker_runner_and_tests`.
It freezes the exact 19-tuple source-intake seed, four quarantined checksum-only
tuples, Android/macOS arm64 review profiles, fixed-point graph rules, request
and output identities, and finite receipt/failure bounds. Its read-only checker
passes 56/56 mutation tests. It rehashes the retained root ZIP, embedded
`go.mod`/`go.sum`, and source tree, proves all premature wave artifacts absent
through the final barrier, and pins exact H1 and ordered source-set digest
algorithms. It performs no acquisition or network I/O, closes
no finding, and selects no candidate or library. Neither external
authentication nor user action is required.

The historical successor
[bounded dependency wave-one execution permit v1](../../docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-execution-permit-v1.json)
and its [reader contract](../../docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-execution-permit-v1.md)
recorded before execution
`status=wave1_dependency_source_acquisition_authorized_not_consumed`,
`result=exact_19_public_proxy_zip_requests_authorized_once_not_executed`,
and `recordedNextActionAtThatCheckpoint=execute_bound_dependency_source_wave1_once`.
The runner still passes 44/44 tests. The permit suite recorded 38/38 only at
the unconsumed checkpoint; the current gate reruns 36 state-independent cases
because v1 is consumed and cannot be retried.

The historical
[wave-one recovery decision v1](../../docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-recovery-decision-v1.json)
and its [reader contract](../../docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-recovery-decision-v1.md)
bind, at that checkpoint, the terminal `E_ZIP_RATIO` failure after two response bodies and one fully
validated/staged tuple, with zero accepted artifacts and no final set. The
31/31 recovery mutation tests preserve v1 and select a distinct v2 namespace
plus non-gating exact-integer compression telemetry under unchanged absolute
streaming/deadline bounds. They recorded
`status=wave1_v1_failure_read_back_recovery_v2_design_selected_execution_not_authorized`,
`result=v1_ratio_policy_rejected_tuple2_after_two_responses_no_final_set_v2_bounded_telemetry_policy_selected`,
and `recordedNextActionAtThatCheckpoint=prepare_separate_v2_runner_checker_tests_and_execution_permit`.

The historical
[wave-one execution permit v2](../../docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-execution-permit-v2.json)
and [reader contract](../../docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-execution-permit-v2.md)
recorded, before execution,
`status=wave1_v2_dependency_source_acquisition_authorized_not_consumed`,
`result=exact_19_public_proxy_zip_requests_v2_authorized_once_not_executed`,
and `recordedNextActionAtThatCheckpoint=execute_bound_dependency_source_wave1_v2_once`.
The permit is now consumed and cannot be retried. Its retained claim and
failure receipt record `E_GO_MOD_MISSING` on tuple 11 after 11 completed ZIP
responses, 10 validated/staged tuples, zero accepted artifacts, and no final
set.

The predecessor
[wave-one recovery decision v2](../../docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-recovery-decision-v2.json)
and [reader contract](../../docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-recovery-decision-v2.md)
record
`status=wave1_v2_failure_read_back_recovery_v3_design_selected_execution_not_authorized`,
`result=v2_conflated_zip_and_mod_resources_tuple11_after_eleven_responses_no_final_set_v3_zip_plus_mod_policy_selected`,
and
`recordedNextActionAtThatCheckpoint=prepare_separate_v3_runner_checker_tests_and_execution_permit`.
The checker and 39/39 mutation tests select 19 fresh `.mod`-then-`.zip` pairs
and preserve both terminal generations. That preparation action is complete.

The historical
[wave-one execution permit v3](../../docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-execution-permit-v3.json)
and [reader contract](../../docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-execution-permit-v3.md)
recorded, before execution,
`status=wave1_v3_dependency_source_acquisition_authorized_not_consumed`,
`result=exact_19_public_proxy_mod_then_zip_pairs_v3_authorized_once_not_executed`,
and `nextAction=execute_bound_dependency_source_wave1_v3_once`. It is consumed
and cannot be retried. The immutable
[success receipt](../../docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-receipt-v3.json)
and [manifest](../../docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-manifest-v3.json)
record `status=acquired_pending_independent_readback`,
`result=fresh_exact_19_dependency_zip_mod_pairs_acquired_and_hash_verified`,
38 request attempts, 38 completed bodies, and 38 accepted resources across 19
exact `.mod`/`.zip` pairs. The separate
[readback receipt](../../docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-readback-v1.json)
and [manifest](../../docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-readback-manifest-v1.json)
validate `status=independent_readback_complete`, 43 regular files, and the same
38 resources. The permit-bound 34/34 reader tests remain immutable; a versioned
recovery reader recorded the outputs once, and the
[fixed-hash post-verification decision v3](../../docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave1-readback-post-verification-decision-v3.json)
plus its verification-only 9/9 suite close the raw-encoding, dispatch, TOCTOU,
and typed-comparison gaps with
`fixedHashEnforcedInsideHeldValidation=true`, `verificationOnly=true`, and
`recordModeExposed=false`. The current
`nextAction=prepare_separate_dependency_source_review_wave`; source
extraction/execution, runtime/product network, device, deployment, and Git work
remain closed. No credentials or user action are involved, all 19 findings
remain open, and no candidate or library is selected.

The rung-two successor recorded, only `at_that_checkpoint`,
`recordedNextActionAtThatCheckpoint=prepare_versioned_rung3_offline_source_review_decision`.
That historical preparation action is complete and is not current authority.

Historical G2 restricted-fork rung-one status contract at_that_checkpoint:
`status=rung1_profile_complete_candidate_not_selected`,
`result=pion_restricted_fork_profile_ready_for_rung2_decision_only`, and
`recordedNextActionAtThatCheckpoint=prepare_versioned_rung2_source_identity_and_acquisition_decision`.
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

The tracked [result-v3](../../docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/offline-source-review-result-v3.json),
[runtime-manifest-v3](../../docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/offline-source-review-runtime-manifest-v3.json),
and [execution-receipt-v3](../../docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/offline-source-review-execution-receipt-v3.json)
bind exact readback. The result is 76,685 bytes at SHA-256
`ef4b8d88ec57501377a7bc9db066c04a1a379041ee1b11999f5d16c7d4447933`;
the manifest is 2,458 bytes at SHA-256
`2dace9b59b7374423754f1f9a7345eda76db9130728d1c0579797e5a0c829055`.
The inventory covers 100 Go files, 1,077,591 bytes, and 39,064 logical lines;
19 rules in seven patch units report 4,701 hits as 144 representatives, at most
eight per rule, plus 4,557 omissions. All 129 entries have creator system 0,
accepted DOS attributes `00`, and synthetic mode `100444`.

This package gains no wire message or runtime behavior. Semantic-review v1 has
now completed two non-attesting full-coverage passes over all 100 Go source
bodies and all 4,701 lexical observations, with production/test/example counts
52/44/4 and disagreements forced to `unresolved`. Its 29 candidates deduplicate
to 19 findings: P0=0, P1=11, P2=3, P3=4, none=1; patch_required=7 and
unresolved=12. The `one-use` zero-hit remains a missing-required-mechanism gap,
not a vulnerability conclusion by itself. The independent tracked-only checker
and 25/25 mutation tests hold all eight file descriptors plus every
repository-path directory component through two stable full-set readback passes
and a final identity barrier, validate the manifest last, and observe the failure
file plus four staging names absent before and after readback.
`semanticSourceReviewPerformed=true`, while
`semanticClosureComplete=false`, `dependencyClosureComplete=false`,
`rungThreeComplete=false`, `candidateSelected=false`, and
`librarySelected=false`. Semantic review was performed, but semantic closure,
dependency closure, rung-three completion, candidate selection, and library
selection remain false. It does not reproduce semantic judgments or source-
based location bounds. Same-UID concurrent mutation is not prevented, and
absence is not guaranteed after the final observation. No extraction,
materialization, dependency install, source compile/execution, socket, network,
device, deployment, or Git operation occurred. No repository-owner
authentication, external identity proof,
execution-permit authentication or document, or user action is required.

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
