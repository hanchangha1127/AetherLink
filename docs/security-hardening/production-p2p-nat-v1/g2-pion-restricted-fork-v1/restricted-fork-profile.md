# G2 Pion Restricted-Fork Profile v1

Recorded: 2026-07-23 KST

## Result

This rung-one profile is complete enough to prepare a separate official-source
identity and acquisition decision. It does not select Pion, approve a fork, or
open source acquisition. Unmodified Pion ICE v4.3.0 remains rejected. The
requirements below are not implemented, and every runtime verification row is
still `not_executed`.

Among the three reviewed Pion v4.3.0 shapes, only an AetherLink-maintained,
exact-base restricted fork remains suitable for rung-two consideration. A new
exact library or future upstream release may still start its own rung-one
review. A wrapper around the current exact base is insufficient because it
cannot own all internal I/O, ingress, event, diagnostic, and shutdown paths.

## Evidence and exact upstream baseline

The ordered [evidence manifest](evidence-manifest-v1.json) binds the G2 as-is
review, the G0 V1 platform decision, and the current roadmap and handoff bytes.
Those sources establish the rejected upstream baseline, sequential G2 scope,
V1 architectures, and personal-project boundary without turning this design
into implementation evidence.

- Repository: `https://github.com/pion/ice`
- Module: `github.com/pion/ice/v4`
- Tag/version: `v4.3.0`
- Commit: `1e8716372f2bb52e45bf2a7172e4fb1004251c46`
- Go directive: `1.24.0`
- License observed from the official project: MIT
- Release date observed: 2026-07-13
- Review date: 2026-07-23

The exact base is immutable for this profile. No automatic upstream merge is
permitted. A version update starts a new source-identity decision and offline
review; it cannot inherit future evidence from this version.

## Required fork changes

The proposed patch series is a requirement, not a completed change:

1. Split network control into an egress capability immediately before socket
   create, bind, connect, TLS handshake, or write, and an ingress admission
   gate after a bounded read but before any state mutation or payload delivery.
2. Remove the remote ICE-password diagnostic and use a closed, source-free
   reason-code allowlist.
3. Replace arbitrary callbacks and growing callback queues with a bounded pull
   event queue plus an independent sticky terminal latch.
4. Make context cancellation, socket revocation, internal worker drain, and
   `Close` obey one 2,500 ms total deadline.
5. Remove or fail closed every path outside the feature profile.
6. Accept only bounded caller-supplied resolver, interface, and signed TURN TLS
   identity inputs.
7. Issue a one-use pre-auth path capability and permit application records only
   after exact AetherLink endpoint confirmation atomically promotes that path.

The mobile bridge remains narrow. Upstream API compatibility is secondary to
the destination, ingress, endpoint-identity, secret, resource, and lifetime
invariants.

## Closed feature profile

Allowed behavior is full ICE at both endpoints, regular nomination, one
component, UDP4/UDP6 connectivity checks, server-reflexive, peer-reflexive, and
relay candidates, ordered generation-scoped trickle, STUN and TURN through both
policy directions, and exact-tuple consent freshness.

Host candidates stay disabled by default. A future same-link host candidate
requires an explicit per-session capability. Before endpoint confirmation, a
nominated path may carry only bounded AetherLink secure-session confirmation
and carrier-negotiation datagrams. Application records require a distinct
generation-and-tuple-bound capability issued after both endpoint confirmations.

The fork must reject ICE Lite, aggressive nomination, all ICE-TCP candidates,
SOCKS and HTTP CONNECT proxies, UDP/TCP muxes, mDNS, automatic redirects or
alternate servers, internal system DNS, UPnP/NAT-PMP/PCP, telemetry, and hidden
bootstrap behavior.

## Egress capability and ingress admission

An egress capability binds the session digest, generation, purpose, transport,
interface, scope, signed service and candidate digests, resolution provenance,
and exact local/remote tuple. It is issued after resolution and consumed once
immediately before socket create, per-interface bind, read-loop arm, connect,
TURN TLS handshake, credential write, connectivity check, consent, handshake
datagram, or authenticated record-fragment write. It is invalid after any
re-resolution, tuple, generation, transport, purpose, or credential-class
change. Wildcard bind and redirects are disabled.

Ingress cannot be approved before the peer's source is known. Each allowed UDP
or TURN stream read therefore uses a fixed maximum buffer and bounded header
parse first. Before state mutation, event creation, or payload delivery, the
ingress gate checks the bound socket capability, source tuple and interface,
message class and length, expected transaction, required integrity/fingerprint,
TURN allocation/permission/channel, generation and nominated tuple, and the
pre-auth or authenticated content capability. Invalid input is dropped with a
saturating reason counter only.

The path inventory covers STUN requests and responses, ICE connectivity and
consent in both directions, TURN UDP responses, bounded TURN TCP/TLS frames,
TURN Data Indication and ChannelData, peer-reflexive tuples, pre-auth handshake
datagrams, and authenticated direct/relay record fragments. Rung three must
show that every Pion/STUN/TURN read loop and every create/bind/connect/write
edge maps to this inventory.

## TURN TLS service identity

TURN over TLS requires a G1 trust source plus signed service configuration that
binds service ID, ASCII server name, port, transport, trust-anchor-set digest,
optional SPKI SHA-256 pins, credential scope, expiry, and configuration digest.
The required transport is TLS 1.3 with exact SNI, the `stun.turn` ALPN value,
and exact DNS-ID validation without wildcards. A signed configuration may carry
up to four SPKI pins.

No TURN username, password, or REST credential may be sent before certificate,
name, trust-digest, optional pin, ALPN, configuration-expiry, and 5,000 ms
handshake checks pass. `InsecureSkipVerify`, ambient proxies, and an ambient
trust store without the signed trust digest are prohibited.

## AetherLink secure-session promotion

Nomination yields one one-use pre-auth raw-path capability, not an application
channel and not peer authentication. That capability is bound to the exact
session, generation, transport, local and remote tuples, path receipt,
candidate capability, and expiry. It lasts at most 15 seconds and carries at
most 64 datagrams or 65,536 bytes of secure-session confirmation and carrier
negotiation.

Promotion atomically consumes that capability only after the verified secure-
session transcript, both key-confirmation digests, path receipt, generation,
and endpoint roles match. The resulting application-record capability is bound
to the same exact path and secure-session digest. ICE connectivity, Pion state,
or TURN service authentication can never perform this promotion.

Consent loss, path change, candidate restart, capability expiry, verification
failure, or session close atomically revokes both pre-auth and application
capabilities before any further I/O, state mutation, event, or payload delivery.

Pion supplies an unordered, unreliable datagram path. The Runtime needs an
ordered, reliable `RuntimeRawFrameBodyChannel`, and canonical secure-session
records may reach 1,048,576 bytes. Therefore reliable carrier selection and a
bounded fragmentation/reassembly format remain explicit blockers; the Pion
path must not attach to the Runtime channel until both are selected and
verified.

## Resource and diagnostic bounds

All limits cover current, draining, and closing generations. Two sessions are
the process maximum, and process totals are exactly the sum ceiling across both.
The profile bounds interfaces, candidates and pairs, STUN/TURN servers and
allocations, permissions and channels, resolver bytes and answers, datagram and
control-message sizes, attribute counts, packet and byte rates, transactions,
retransmits, timers, tasks, goroutines, sockets, overlapping generations,
reassembly records/bytes/fragments, events, and event bytes. Length, count,
rate, and process-total excess fails before allocation or state insertion.

The normal event queue holds at most 64 events and 256 KiB. It does not reserve
space for its own overflow event. Instead, one independent sticky terminal
latch is atomically set, nonterminal queued events are discarded, and the
generation closes without waiting for a consumer.

Diagnostics are requirements with `implementationStatus=not_implemented` and
`verificationStatus=not_executed`. Logs may contain only listed state/reason
codes and saturating counts. ICE/TURN credentials, candidates, addresses,
hostnames, certificate subjects, stable identities, pair/session identifiers,
payloads, backend credentials, and traffic keys are forbidden fields. Remote
ICE-password log removal is required; it is not recorded as already completed.

## Shutdown contract

The future close implementation must reject new work, cancel contexts and
timers, close every owned socket, invalidate egress, ingress, pre-auth, and
application capabilities, set the sticky terminal latch, discard nonterminal
events, and join only internal deadline-bound workers. It may not invoke or wait
for an untrusted callback or event consumer. Total close must return within
2,500 ms with success or a terminal timeout. Finalizers are not correctness.

## Supply chain and maintenance

Before a compile rung, the project must pin exact Go, `x/mobile`, `gomobile`,
`gobind`, Android NDK, and Xcode revisions; vendor the complete Go module graph;
produce an SPDX 2.3 JSON SBOM and license inventory; record the reviewed patch
series and egress/ingress path manifest; close the exported bridge symbols; and
decide the reliable carrier and fragmentation contract.

The future V1 compile-only matrix is Android API 26 through 36 on `arm64-v8a`
and macOS 14 or newer on `arm64`. Emulator `x86_64` and macOS Intel are not V1
release targets. Two clean isolated builds with exact inputs must eventually
produce matching digests.

AetherLink owns fork maintenance and assumes no unverified upstream security-
support promise. Releases are reviewed at least every 30 days and dependency
advisories every 14 days. A critical advisory is triaged within two business
days and fixed or mitigated within seven calendar days; an unmitigated critical
issue or profile bypass blocks release.

## Verification and next boundary

Rung three must separately prove egress, ingress, hostile resolution, TURN TLS
identity, endpoint-confirmation promotion, full resource/process bounds,
secret-free diagnostics, and deadline shutdown. Rung four closes dependencies,
licenses, SBOM, patch drift, and reproducibility. Rung five is compile-only for
the two V1 architectures. Rung six adds fuzz, malformed input, race/sanitizer,
ABI, shutdown, and zero-socket no-network conformance.

Current status is `rung1_profile_complete_candidate_not_selected`; current
result is `pion_restricted_fork_profile_ready_for_rung2_decision_only`. It is
eligible only to prepare the next technical decision. The recommended next
action is `prepare_versioned_rung2_source_identity_and_acquisition_decision`. No rung-two
decision exists yet. No library, source, dependency, compiler, load, socket,
network, device, deployment, or Git action is opened by this document. No
external identity proof or user action is required.
