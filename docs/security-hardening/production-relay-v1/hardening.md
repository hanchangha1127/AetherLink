# Security Hardening Review: Production Relay Control And Recovery

## Evidence Basis

I inspected the current allocation client, relay server, durable lease registry,
paired authorization, pairing proof, strict relay crypto, Android route store,
and shared schema. The evidence is anchored by `evidence.sha256`; the worktree is
dirty by design, so this review records source drift rather than pretending to
describe an immutable release.

The current design already preserves the most important product boundary: the
runtime generates the traffic secret locally, the service never receives it,
and client/runtime ECDH plus confirmation protects AI frames. The structural gap
is in the control plane. Allocation uses plain TCP, the final lease has no service
signature, and durable state has no pair recovery epoch or relay-wide immediate
revocation transition.

The refreshed development baseline now bounds accepted sockets, suppresses
`SIGPIPE`, tears down both active-bridge directions after the first peer closes,
expires control records on an `EINTR`-resistant absolute deadline, cleans up
disconnected waiting peers, disables exposed probe by default, and rejects
exposed legacy mode. Allocation- and renewal-prefixed attempts, including
malformed records, now consume separate monotonic source buckets before full
parsing. A shared overflow bucket, periodic idle cleanup, scoped IPv6 identity,
exact strict preflight classification, full-refill-before-idle validation, and
source-free reason counters bound in-memory work without capacity resets or
per-request full-map scans. Source peer quotas also bound concurrent
accepted sockets and unmatched waiters, reserve counterpart-only admission per
waiter with pre-waiter headroom and atomic waiting-insertion revalidation,
confirm immediate matches or authenticated same-source waiting replacement,
retain global/source reserve provenance, reject per-source reserve discharge
against another source and cross-source reserve replacement, and preserve established active-bridge
forwarding (`E011`). Bounded waiting gives unmatched rooms a monotonic
first-insertion deadline capped by lease expiry, with 60 seconds as the default, while each
verified authenticated identity for a runtime or paired client receives a role-separated, cross-source
waiting quotas of four by default. Identity accounting begins only after the
corresponding proof succeeds; bootstrap clients and legacy peers remain
source-only, and active bridges are not charged (`E012`). These tactical development-relay
controls do not authenticate the allocation service, protect credentials with
TLS, sign leases, establish peer-verifiable endpoint identity KEX, add pair-epoch
recovery, or change the structural recommendation below.

## Constraints

- Preserve `Android client -> trusted runtime -> Ollama/LM Studio`; the relay is
  connectivity infrastructure, never a model or account backend.
- Preserve endpoint-owned traffic secrets and end-to-end encrypted AI frames.
- Keep QR as the trust bootstrap and recovery authority for one-to-one pairing.
- Do not require an account service for device trust or key recovery.
- Keep local direct and current development relay paths available during rollout.
- Assume a balanced security/operability profile; no measured latency or memory
  budget was supplied.
- P2P NAT traversal, STUN/TURN implementation, and physical-device proof are
  separate milestones.

## Opportunity Portfolio

| Opportunity | Evidence | Options | Recommendation | Proposal |
| --- | --- | --- | --- | --- |
| Authenticate allocation and bind service-issued leases | Plain allocation channel, endpoint-owned E2E secret, runtime/client lease proofs (`E001`-`E006`) | 1. signed TCP inside a private overlay; 2. TLS plus signed lease; 3. split authority/data plane | Option 2 now, with an Option 3-compatible capability shape | [Authenticated allocation control plane](proposals/authenticated-allocation-control-plane.md) |
| Add compromise recovery and immediate revocation | Durable generation CAS, QR-pinned identities, route persistence, absent recovery epoch (`E004`-`E009`) | 1. short leases/manual re-pair; 2. pair epoch state machine; 3. threshold recovery | Option 2; defer threshold recovery until multi-client requirements exist | [Pair epoch recovery](proposals/pair-epoch-recovery.md) |

## Recommendation Summary

I recommend that we keep the existing endpoint PSK-mixed ECDH data plane and add
two orthogonal controls. First, the allocation channel should use TLS 1.3 with a
configured service trust root, while every accepted lease is also signed by an
online lease key delegated from an offline service root. The signed lease digest,
service key id, pair epoch, and generation then enter an endpoint-verifiable
identity transcript. The relay may forward that transcript, but it is not the
trust terminator for endpoint key exchange.
TLS protects bearer allocation credentials and route tokens in transit; the
signed capability makes lease integrity independently verifiable and keeps a
future split relay architecture possible.

Second, pair trust should become a monotonic `pair_epoch` state machine. Normal
renewal remains runtime/client co-authorized. Either current device may issue an
emergency deny-only revocation, which can close rooms but cannot authorize a
replacement key. Key replacement requires a fresh QR ceremony and advances the
pair epoch. Each mutation binds a transition id and canonical request digest:
an exact retry returns the original receipt, different content under the same id
fails, and a competing id returns the signed winning state. A read-only signed
status operation reconciles response loss after authority commit. This
deliberately prefers recoverable denial of service over silent trust replacement
by a compromised key.

The stronger split authority/data-plane option becomes preferable when relay
operators and allocation operators must be isolated, or when metadata minimization
outweighs deployment simplicity. Threshold recovery becomes preferable only after
the product has a real multi-client or offline recovery-key model; introducing it
now would add account-like recovery authority without a product requirement.

## Next Decisions

- Select or refine the recommended options before protocol implementation.
- Decide whether production service trust is provisioned by an app-bundled offline
  root, an enterprise/private-overlay root, or a signed QR/bootstrap manifest.
- Set lease and revocation freshness targets after public-network latency tests.
- Decide whether one-sided emergency revocation is accepted as a deliberate DoS
  capability.
- Define secure local rollback storage for `pair_epoch`, service keyset version,
  and revocation counter on Android and macOS.
