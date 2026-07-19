# Security Hardening Proposal: Authenticate Allocation And Bind Service-Issued Leases

## Decision

Choose how production AetherLink endpoints authenticate the allocation service,
protect allocation credentials and route tokens in transit, and verify that a
lease was issued by the intended service without giving the relay access to the
endpoint-owned traffic secret or AI payloads.

## Executive Recommendation

We have three serious options. **Option 1: Signed TCP Inside An Authenticated
Private Overlay** adds service signatures to the existing control lines and
delegates channel protection to the overlay. **Option 2: TLS 1.3 Plus Signed Lease Capabilities**
protects the channel and makes each lease independently verifiable. **Option 3:
Split Allocation Authority And Blind Relay** separates control-plane authority
from ciphertext forwarding and minimizes relay metadata.

I recommend Option 2 under the current constraints. It closes the immediate
server-authentication and credential-confidentiality gaps while preserving the
existing endpoint PSK-mixed ECDH data plane. We should define its lease as an
opaque signed capability that Option 3 can later consume without changing the
endpoint transcript again.

## Evidence

I inspected the allocation callers, strict relay transports, device proof
contracts, and shared schema. The most important distinction is that the
allocation control plane is unauthenticated while the endpoint data plane is
already protected from the service.

| Evidence | Finding or document | What it establishes |
| --- | --- | --- |
| `E001` | Plain allocation transport, bounded controls, and unsigned lease response | `TCPRelayServiceRouteAllocator` opens a TCP socket, sends bearer allocation material, byte-bounds control-line reads, and validates response fields against an unsigned challenge; `RelayPeerClient` also creates a plain TCP `NWConnection` with bounded registration and confirmation lines. |
| `E002` | Endpoint-owned traffic secret and PSK-mixed ECDH | The runtime generates the 32-byte secret locally; Swift and Kotlin derive confirmation and traffic keys from ECDH plus that secret. |
| `E003` | Validated runtime identity and signed allocation/registration challenges | Runtime identity decoding re-enters the validating initializer and proofs bind allocation and runtime registration fields, but they authenticate the runtime to the service, not the service to the runtime. |
| `E004` | Runtime/client co-authorized paired lease continuity | Paired renewal binds current/next IDs, generations, nonces, both device fingerprints, and the live transport binding; matcher registration freshly revalidates the exact lease and expiry under coordinated store state. |
| `E005` | QR-pinned mutual device identity | Initial pairing proves both long-term device keys and binds them to the confirmed endpoint transport. |
| `E006` | DNS-scope-validated relay admission before strict frame activation | Android resolves once, requires every returned address to satisfy the declared public, private-overlay, or debug-loopback scope, connects to the exact validated address, bounds strict control lines and outgoing frame bodies, and then binds paired endpoint proofs to each ephemeral registration. The relay still terminates those identity checks; persistent identity signatures are not directly peer-verifiable in the ECDH transcript. |
| `E009` | No service lease identity in the shared schema | The schema carries transport bindings and paired allocation messages but no service key id, lease signature, or signed lease digest. |
| `E010` | Development-relay source-aware allocation controls | Allocation- and renewal-prefixed attempts consume separate bounded source buckets before full parsing. Exact strict preflight classification, shared overflow, full-refill-before-idle validation, and source-free counters are tactical defense in depth, not service authentication. |
| `E011` | Development-relay source peer quotas | Canonical accepted sources have bounded live connections and matcher-owned waiters; pre-waiter headroom plus atomic waiting-insertion checks reserve counterpart-only admission for an immediate match or authenticated same-source waiting replacement. Global/source reserve provenance prevents per-source reserve from discharging another source's waiter, while cross-source/nonmatching candidates close with source-free counters. This is tactical admission defense, not service authentication or lease integrity. |
| `E012` | Development-relay bounded waiting and authenticated identity fairness | First-insertion monotonic waiting deadlines are capped by lease expiry, registration/readiness decisions atomically expire late rooms before matching or replacement, and waiting results carry the deadline without a post-publication room lookup. Role-separated verified runtime or paired-client identities have cross-source waiting quotas. Bootstrap and legacy peers remain source-only, while active bridges are uncharged. This is tactical fairness, not service authentication, signed lease integrity, or peer-verifiable identity KEX. |

Observed: allocation and relay sockets are plain TCP; service responses are
shape-checked and control lines are bounded but not service-signed. Observed:
allocation/store JSON rejects duplicate keys, allocation TTL is finite and
capped, and registration revalidates the lease under coordinated state. These
are tactical parser and race controls, not production service authentication.
Observed: the traffic secret is attached
after service allocation and never enters the service request. Inferred: a
network attacker can steal an allocation token, observe route tokens, impersonate
the allocation endpoint, or suppress/replace unsigned lease metadata, but still
cannot derive confirmed endpoint traffic keys without the endpoint secret or an
endpoint private key.

## Current Design And Failure Mode

The runtime currently sends a route token, optional bearer allocation token,
runtime public key, and runtime-signed proof to the service. The runtime verifies
that the returned ID matches its deterministic derivation and that lease fields
match the service challenge. This protects the service from unauthorized runtime
claims, but the service has no authenticated voice in the exchange. A machine in
the path can terminate the plain TCP session and supply its own challenge and
lease values that satisfy local shape rules.

The data plane is materially stronger. The runtime generates the relay secret
locally, shares it through QR or authenticated refresh, and mixes it with fresh
endpoint ECDH. Both endpoint identities are bound into pairing, registration, and
paired allocation paths. We should preserve that architecture. Adding TLS must
not turn the relay certificate or allocation service into the key that decrypts
AI traffic.

## Desired Invariants

- Every production allocation request authenticates the intended service before
  disclosing allocation credentials, route tokens, or identity proofs.
- Every accepted lease is verifiable offline against a versioned service keyset
  and is bound to exact protocol suite, relay ID, pair epoch, generation, nonce,
  expiry, device ownership, and authorization digest.
- The signed lease digest and service key id are included in endpoint key
  confirmation and device identity transcripts.
- On paired reconnect, both endpoints verify peer signatures over a canonical
  key-exchange transcript containing both long-term identities, both ephemeral shares,
  both session nonces, pair epoch, generation, and signed lease digest. The relay
  may forward but cannot terminate or replace this proof.
- The service never receives the endpoint traffic secret, endpoint ECDH private
  keys, frame traffic keys, prompts, responses, files, memory, model metadata, or
  backend credentials.
- A service key rotation cannot silently roll back to an older keyset version.
- Development plain TCP remains explicitly marked and cannot be selected by a
  production route through negotiation.

## Constraints And Non-Goals

We preserve QR-first pairing, local-first runtime ownership, Android-to-runtime
model access, and the current encrypted relay fast path. This proposal does not
implement P2P NAT traversal, account recovery, global user identity, traffic
analysis resistance, or protection after both endpoint long-term keys are
compromised. It does not choose a public CA vendor. Private-overlay deployments
may use an enterprise root or a signed bootstrap manifest instead of public DNS
PKI.

## Before Architecture

[Before architecture](../diagrams/authenticated-allocation-control-plane-before.mmd)

The before view has one service process owning both allocation and forwarding.
Runtime authentication flows toward that service, but no service trust anchor
flows back. Endpoint encryption starts only after the unsigned lease has been
accepted and distributed.

## Options

### Option 1: Signed TCP Inside An Authenticated Private Overlay

This option keeps the current socket protocol behind WireGuard, Tailscale, or an
equivalently authenticated private overlay and adds a service signing key. The
service signs every challenge and final lease; endpoints pin an offline root or a
versioned delegated keyset. Firewall policy rejects non-overlay callers. The
attractive part is its narrow code change: overlay identity and encryption protect
the channel while the signed capability survives after it closes.

What gives me pause is that the guarantee is deployment configuration rather than
an application protocol invariant. A firewall or overlay routing mistake exposes
the allocation token, route token, and runtime proof on plain TCP. We would also
be maintaining a custom authenticated transport when TLS already solves channel
confidentiality, replay-resistant handshakes, and server identity negotiation.

[Option 1 architecture](../diagrams/authenticated-allocation-control-plane-signed-plain-after.mmd)

| Change | Before | After | Security consequence | Cost |
| --- | --- | --- | --- | --- |
| Service identity | None | Pinned signing root and delegated lease key | Detects forged service messages | Key provisioning and rotation |
| Channel secrecy | None | Authenticated private overlay | Protects bearer and route material only while overlay policy is correct | Overlay enrollment, firewall, and routing operations |
| Lease integrity | Shape checks | Signed capability | Lease mutation and spoofing fail | Canonical encoding and verification |
| Data-plane secret | Endpoint-owned | Endpoint-owned | Relay remains blind to AI frames | No material change |

Rollback is straightforward because development TCP remains, but production
must fail closed rather than silently accepting unsigned control lines.

### Option 2: TLS 1.3 Plus Signed Lease Capabilities

This option authenticates the allocation channel with TLS 1.3 and also signs the
lease as a canonical capability. TLS protects bearer tokens, route tokens, and
identity proofs from network observers. The signed lease remains verifiable by
both endpoints after the TLS connection closes and can be inserted into the
endpoint transcript. An offline service root delegates a short-lived online
lease signing key; a signed, monotonic keyset version controls rotation.

The endpoint trust source can vary without changing the wire object: an app
bundle can carry the service root for a managed public service, an enterprise
deployment can install its own root, and a private overlay can deliver a signed
bootstrap manifest through QR. Hostname validation alone is insufficient for IP
or private-overlay routes, so configuration must state which trust source owns
the route and must never fall back from a pin to opportunistic TLS.

The lease should cover `lease_version`, `service_id`, `service_key_id`,
`keyset_version`, `lease_id`, `relay_id`, `pair_id`, `pair_epoch`, runtime and
client key fingerprints, generation, nonce, expiry, allocation authorization
digest, crypto suite, and a revocation endpoint identifier. Endpoints hash the
canonical lease and include that digest in registration, ECDH binding, initial
auth, and paired renewal. The relay still forwards opaque ciphertext and never
receives the endpoint traffic secret.

The production endpoint handshake is a separate reviewed work item, not a
relay-side admission check renamed as mutual authentication. Both endpoints must
verify signatures over one canonical transcript containing both long-term
identities, both ephemeral shares, both session nonces, `pair_epoch`, generation,
and the signed lease digest before installing traffic keys. Relay-side admission
proofs remain defense in depth, but the relay is not the trust terminator. The
initial bootstrap is deliberately asymmetric: the QR pins the runtime identity;
the new client identity is accepted only through the signed pairing exchange
after the protected channel has been confirmed.

[Option 2 architecture](../diagrams/authenticated-allocation-control-plane-tls-signed-after.mmd)

| Change | Before | After | Security consequence | Cost |
| --- | --- | --- | --- | --- |
| Allocation channel | Plain TCP | TLS 1.3 with explicit trust source | Protects credentials and authenticates service | Certificate/keyset operations and handshake latency |
| Lease | Unsigned JSON/control line | Canonical signed capability | Offline verification and transcript binding | New schema and signing service |
| Key rotation | None | Offline root, delegated key, monotonic keyset | Limits online-key compromise and rollback | Root custody and overlap procedures |
| Endpoint handshake | Relay-verified admission plus PSK ECDH | Peer-verified identity transcript plus signed lease digest | Rejects relay-terminated identity substitution and lease substitution | Reviewed KEX construction, cross-language vectors, and migration |
| Relay visibility | Route/control metadata, ciphertext | Same metadata, ciphertext | Preserves payload blindness | Metadata privacy unchanged |

The principal reliability risk is trust-source or clock failure blocking
allocation. Rollout therefore needs overlapping key validity, bounded clock skew,
cached verified keysets, explicit errors, and a dual-stack observation phase in
which v2 remains available only for development routes. Rollback can disable the
new production route class, but must not make an already pinned production route
accept unsigned v2.

### Option 3: Split Allocation Authority And Blind Relay

This option separates lease authority from data forwarding. The allocation
authority authenticates endpoints and issues an opaque signed capability. The
relay sees only the capability redemption data required to admit a room, plus
ciphertext. It can verify capabilities from a cached keyset or redeem them with
the authority. The endpoint handshake remains identity-bound and includes the
capability digest.

The strongest case is compartmentalization: compromising a relay node does not
grant authority to mint leases or expose route tokens and identity proofs held by
the allocation authority. Different relay operators can serve the same authority
without sharing endpoint secrets. This is also the cleanest path to global room
isolation and multi-region relay capacity.

The cost is a second service boundary, capability redemption/cache semantics,
revocation propagation, more observability, and a harder incident model. An
authority outage must not strand already valid sessions, while a revoked lease
must close quickly. We would need explicit stale-cache behavior and region-level
tests before calling this more reliable than Option 2.

[Option 3 architecture](../diagrams/authenticated-allocation-control-plane-split-after.mmd)

| Change | Before | After | Security consequence | Cost |
| --- | --- | --- | --- | --- |
| Authority ownership | Relay mints and serves lease | Separate allocation authority | Relay compromise cannot mint leases | Additional service and deployment |
| Relay metadata | Route and identity allocation inputs | Opaque capability and room metadata | Narrows relay metadata exposure | Capability design and debugging cost |
| Revocation | Lease/store local | Authority event or bounded cache expiry | Global revocation becomes possible | Fanout and cache consistency |
| Availability | One service path | Authority plus relay path | Better relay isolation, new dependency | Multi-region failover and observability |

We can introduce this after Option 2 if the signed lease is designed as a
portable capability. Rollback routes redemption back through the combined
service while preserving the same endpoint-verified lease format.

## Comparison

| Dimension | Option 1: Signed TCP In Private Overlay | Option 2: TLS + Signed Lease | Option 3: Split Authority/Relay |
| --- | --- | --- | --- |
| Security | Authenticates messages; channel secrecy depends on correct overlay policy | Authenticates service, protects credentials, binds leases, and enables peer-verifiable KEX | Adds authority isolation and metadata minimization |
| Performance | One signature verify; otherwise current path | TLS handshake plus signature verify; session resumption possible | TLS plus authority/capability validation hop or cache |
| Memory | Bounded keyset and lease bytes | Bounded TLS state, keyset, lease bytes | Adds service caches and revocation state |
| Reliability | Current topology; custom protocol risk remains | Trust/key/clock failures can fail closed | Better blast-radius isolation, more distributed failure modes |
| Operability | Signing key and rotation only | TLS, offline root, delegated key, rotation telemetry | Two services, cache/fanout, cross-region incidents |
| Migration | Narrow but not sufficient for production credentials | Moderate dual-stack protocol migration | Foundational deployment and routing migration |

No latency or resource result above is measured. The mechanism and validation
plan matter more than an invented score: benchmark cold and resumed allocation,
record p50/p95/p99 latency and peak RSS, and require the chosen option to remain
within the product's eventual QR generation and route-refresh budgets.

## Recommendation

I recommend Option 2, with a capability format and service key hierarchy that
does not prevent Option 3. It is the proportionate next milestone because it
closes the current network attacker path without redesigning the already useful
endpoint encryption boundary. Option 1 is acceptable only as an intermediate
test harness. Option 3 should win earlier if separate operators, metadata
minimization, or multi-region compromise containment are release requirements.

## Evidence Coverage And Residual Risk

| Evidence | Option 1 | Option 2 | Option 3 |
| --- | --- | --- | --- |
| `E001` - Plain allocation and unsigned lease | Mitigates spoofing, not disclosure | Addresses channel and lease authenticity | Addresses and isolates minting authority |
| `E002` - Endpoint-owned secret/ECDH | Unaffected and preserved | Unaffected and transcript-bound | Unaffected and transcript-bound |
| `E003` - Runtime identity proof | Preserved; service still sees proof | Protected by TLS and bound to lease | Protected at authority boundary |
| `E004` - Paired lease continuity | Preserved | Extended with service lease digest | Extended with portable capability |
| `E005` - QR device identity | Supplies service root/pin if chosen | Supplies explicit route trust source | Supplies authority trust source |
| `E009` - Missing service lease schema | Addressed by signed fields | Addressed by signed capability | Addressed by opaque capability |
| `E010` - Development source limits | Preserved as tactical defense in depth | Preserved as tactical defense in depth | Preserved as tactical defense in depth |
| `E011` - Development source peer quotas | Preserved as tactical defense in depth | Preserved as tactical defense in depth | Preserved as tactical defense in depth |
| `E012` - Bounded waiting and authenticated identity fairness | Preserved as tactical defense in depth | Preserved as tactical defense in depth | Preserved as tactical defense in depth |

Residual risks include endpoint compromise, denial by the service or network,
traffic analysis, a compromised online lease signer during its validity window,
and recovery from rollback of local endpoint state. Pair recovery is handled by
the companion proposal, not by TLS alone.

## Migration And Rollout

1. Freeze a canonical lease encoding and service keyset format with cross-language
   fixed vectors and malformed-input tests.
2. Add verification-only support on macOS and Android; do not advertise it yet.
3. Add TLS/service trust configuration and a local test authority.
4. Run v2 and production-v3 endpoints on distinct route classes or ports; never
   negotiate down on one production route.
5. Implement a reviewed endpoint identity-authenticated KEX state machine and
   bind the verified lease digest, both identities, both ephemeral shares, both
   nonces, pair epoch, and generation into its canonical transcript.
6. Keep relay-side registration proofs as defense in depth and prove that neither
   a relay nor an on-path service can substitute either endpoint identity.
7. Enable production-v3 for opt-in test routes, collect latency/failure metrics,
   then make it required for production routes.
8. Retain v2 only for explicit local development and remove any production
   fallback after the migration window.

The development baseline now provides short leases, allocation tokens, paired
co-authorization, strict response shape checks, endpoint-owned secrets,
encrypted frames, exposed-probe default disablement, `SIGPIPE` suppression,
one-sided bridge reclamation, `EINTR`-resistant absolute control deadlines, a
global connection cap, exposed legacy rejection, and separate bounded source
buckets for preflight and allocation/paired-renewal attempts before full parsing.
Migration still requires production TLS and service authentication,
service-signed leases, peer-verifiable endpoint KEX, downgrade prevention, an
explicit ban on every legacy/plain production fallback, public capacity and
carrier-NAT/VPN fairness tests, and a reviewed production abuse policy.

## Validation Plan

- Fixed Swift/Kotlin vectors for canonical lease bytes, signature, keyset update,
  TLS-exporter or channel-binding input if used, and endpoint transcript digest.
- Negative tests for wrong service root, hostname/pin mismatch, expired or
  future lease, unknown key id, lower keyset version, revoked key, mutated device
  owner, generation, nonce, expiry, suite, or revocation endpoint.
- MITM integration: forged challenge, forged final lease, replayed TLS session,
  stolen allocation token on a different channel, and downgrade to v2 must fail.
- Endpoint KEX integration: substituted runtime/client identity, ephemeral share,
  session nonce, pair epoch, generation, or lease digest must fail at the peer,
  including when a test relay admits and forwards the altered transcript.
- Bootstrap integration: a QR-pinned runtime may accept a new client only after
  protected-channel confirmation and the signed pairing exchange; the relay
  cannot select or silently replace that client identity.
- Relay blindness: capture service and relay traffic and assert no endpoint
  traffic secret, frame key, prompt, response, file, memory, model, or backend
  credential appears.
- Benchmark cold/resumed allocation latency, CPU, peak RSS, keyset refresh, and
  authority/relay failover under representative public and private-overlay RTTs.
- Rotation drill with overlapping delegated keys, offline-root-signed keyset,
  emergency key revocation, rollback attempt, and stale client recovery.

## Implementation Work Packages

- Canonical service keyset and lease-capability protocol types.
- macOS and Android trust-store, verifier, and monotonic keyset persistence.
- TLS 1.3 allocation transport with explicit route trust source.
- Service-side delegated lease signer and rotation tooling.
- Reviewed peer-verifiable identity KEX construction and state machine across
  Swift and Kotlin.
- Lease digest, identity, ephemeral, nonce, epoch, and generation binding across
  allocation, registration, session crypto, pairing, and route refresh.
- Production/development route-class separation and downgrade telemetry.
- Integration, MITM, blindness, rotation, performance, and rollback tests.

These are design work packages, not authorization to implement an option before
selection.

## Open Questions

- Which trust source owns public, enterprise, and private-overlay relay routes?
- Is public WebPKI required in addition to an AetherLink service signature, or is
  an app/QR-provisioned root sufficient for every production deployment?
- What are the maximum accepted clock skew and offline keyset age?
- Which reviewed handshake construction and maintained cross-platform crypto
  library will implement the identity-authenticated endpoint KEX?
- Must the relay validate capabilities offline, or may it redeem them online?
- What metadata must a relay retain for abuse controls without becoming an
  account or model backend?
