# Security Hardening Review: G2 Pion Restricted-Fork Candidate

## Evidence Basis

This review uses the four ordered sources registered in
[context.md](context.md) and
[`evidence-manifest-v1.json`](evidence-manifest-v1.json): `G2E001` pins the
Pion ICE v4.3.0 as-is rejection; `G2E002` supplies the V1 two-plane,
endpoint-identity, route-authorization, privacy, and platform boundaries;
`G2E003` supplies the active personal-project governance and sequential G2
technical ladder; and `G2E004` supplies the current handoff and non-execution
state.

The manifest SHA-256 is
`98e0e53955e21a833fe19852ce00f64df2dc808506bdb222c9b8a20bc8006d00`,
and the ordered collection SHA-256 is
`9e395c4c4f7f61a4810d47cf96ff57b47c1908c73ea459181f1c06f26a35d704`.
The four evidence bytes are therefore bound as one finalized inventory.

This is architectural analysis only. `implementationStatus` is
`not_implemented`, every runtime check is `not_executed`, no Pion source was
retained, and no fork patch, compile, load, socket, network, or device result is
claimed.

## Constraints

The future restricted shape would need separate structural controls for both
directions:

- Egress: a single-use capability after resolution and immediately before each
  socket create, bind, connect, TURN TLS handshake, credential write, STUN/TURN
  write, consent check, pre-auth handshake, or authenticated fragment write.
- Ingress: fixed-size reading and bounded minimal parsing, followed by exact
  source, transaction, integrity/fingerprint, TURN allocation/permission/channel,
  generation, tuple, and content-capability admission before any state mutation,
  event creation, forwarding, or payload delivery.

TURN TLS must bind a G1 trust source and signed service configuration to exact
SNI, DNS-ID, trust-anchor digest, optional SPKI pins, `stun.turn` ALPN, TLS 1.3,
and a 5,000 ms handshake deadline before credentials are sent. Nomination may
issue only a bounded one-use pre-auth raw-path capability; exact AetherLink
transcript and both key confirmations must atomically promote it to an
application-record capability. Pion and ICE never authenticate the endpoint.

All packet, STUN/TURN, attribute, rate, transaction, retransmit, task,
goroutine, socket, TURN allocation/permission/channel, generation-overlap,
reassembly, event, and process-aggregate ceilings must reject before allocation
or state insertion. Event overflow must set an independent sticky terminal
latch, discard nonterminal events, and close without waiting for a consumer.
Pion exposes an unordered, unreliable datagram path while the Runtime requires
an ordered reliable channel, so carrier selection and bounded
fragmentation/reassembly remain blockers rather than implied implementation.

This personal project requires no repository-owner proof, external identity
authentication, approval receipt, or additional user action for this review.
Source acquisition, dependency installation, compilation, loading, sockets,
network execution, device execution, deployment, and Git remain outside this
portfolio's technical scope.

## Opportunity Portfolio

| Opportunity | Evidence | Options | Recommendation | Proposal |
| --- | --- | --- | --- | --- |
| Make I/O, secure-session transition, resource, diagnostics, and lifetime ownership structural in a restricted Pion fork | `G2E001` — Pion v4.3.0 as-is rejection; `G2E002` — V1 G0 decision; `G2E003` — canonical V1 roadmap; `G2E004` — canonical session handoff | 1. upstream as-is; 2. wrapper-only gateway; 3. policy-owned restricted fork | Among the three reviewed Pion v4.3.0 shapes, prepare Option 3 for a separate rung-two provenance/acquisition decision; select nothing now | [Complete proposal](proposals/pion-ice-policy-owned-restriction.md) |

## Recommendation Summary

Option 1 retains the observed egress, ingress, diagnostic, queue, shutdown, and
identity-transition gaps. Option 2 can narrow normal configuration and outer
call sites, but it cannot own upstream-internal socket/read-loop paths, TURN TLS
credential timing, inner queues, diagnostics, or close waits.

Among the three reviewed Pion v4.3.0 shapes, Option 3 is the only shape suitable
for rung-two consideration: an exact-base AetherLink-maintained restricted fork
with separate egress and ingress admission, authenticated TURN TLS service
identity, one-use pre-auth promotion, comprehensive resource ceilings, an
independent sticky terminal latch, a closed diagnostic allowlist, and deadline
shutdown. This recommendation does not establish that those controls exist.
Their `implementationStatus` remains `not_implemented`, and carrier plus
fragmentation/reassembly selection remains an open blocker.

The normalized portfolio status is
`rung1_profile_complete_candidate_not_selected`; its result is
`pion_restricted_fork_profile_ready_for_rung2_decision_only`, and its next
action is `prepare_versioned_rung2_source_identity_and_acquisition_decision`.

The recommendation narrows only the input to a future decision. It does not
select Pion, approve source acquisition, or establish runtime behavior. A new
exact library or later upstream version may begin a separate rung-one review;
the comparison makes no claim beyond the three shapes examined here.

The complete non-executable contract is recorded in
[restricted-fork-profile.md](restricted-fork-profile.md) and
[restricted-fork-profile.json](restricted-fork-profile.json).

## Next Decisions

The next artifact may prepare a versioned rung-two decision that binds one
official archive, exact checksum/signature provenance, acquisition mechanism,
complete intake limits, and rollback. It must not acquire source until that
separate decision permits it. A later offline source review must prove egress
and ingress path coverage, TURN TLS identity, secure-session promotion,
resource/process ceilings, sticky-latch behavior, diagnostics, and shutdown.

Before any Runtime attachment, a separate decision must select and validate an
ordered reliable carrier plus bounded record fragmentation/reassembly for
canonical secure records up to 1,048,576 bytes. Compile, socket,
controlled-network, physical-device, and production scopes remain later
independent gates. None requires repository-owner identity proof.
