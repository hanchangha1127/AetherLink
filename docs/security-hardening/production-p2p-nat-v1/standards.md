# Production P2P/NAT Standards Basis

These IETF documents are primary design references. They do not by themselves
select an implementation, protocol library, service provider, or wire profile.
Except for the current opaque envelope constraints in `E005` and `E012`, the
conformance posture below is **reserved** until an option is selected,
implemented, and tested.

## Standards Map

| Reference | Role in this portfolio | Required design use | Active vs reserved |
| --- | --- | --- | --- |
| [RFC 8445 - Interactive Connectivity Establishment (ICE)](https://www.rfc-editor.org/rfc/rfc8445.html) | Core UDP NAT traversal | Define roles, candidate gathering, checklist formation, paced connectivity checks, nomination, restart, candidate limits, and ICE credential handling. ICE path success is not endpoint application authentication. | Reserved; current source has no ICE agent. |
| [RFC 8489 - Session Traversal Utilities for NAT (STUN)](https://www.rfc-editor.org/rfc/rfc8489.html) | Address discovery and ICE connectivity-check substrate | Use transaction validation, message-integrity rules where the selected usage requires them, fingerprint/error handling, retransmission bounds, and parser limits. Never treat a mapped address as peer identity. | Reserved; current source has no STUN client/server. |
| [RFC 8656 - Traversal Using Relays around NAT (TURN)](https://www.rfc-editor.org/rfc/rfc8656.html) | Relay fallback for restrictive networks | Define authenticated allocation, refresh, permissions, channel binding, nonce/realm handling, allocation lifetime, teardown, quotas, and relay transport policy. Credentials must be short-lived and pair/session scoped. | Reserved; the active development relay is not claimed to be TURN. |
| [RFC 8838 - Trickle ICE](https://www.rfc-editor.org/rfc/rfc8838.html) | Incremental candidate exchange | Define generation-scoped incremental updates, ordering/idempotency, end-of-candidates, restart behavior, and bounded batches without exposing partial state to stale sessions. | Reserved; current opaque body has no trickle semantics. |
| [RFC 7675 - STUN Usage for Consent Freshness](https://www.rfc-editor.org/rfc/rfc7675.html) | Ongoing permission to send on a selected path | Adapt consent checks and failure behavior to stop traffic when the remote peer no longer demonstrates consent. Keep consent separate from application identity and liveness. | Reserved; no live P2P path exists. |
| [RFC 8827 - WebRTC Security Architecture](https://www.rfc-editor.org/rfc/rfc8827.html) | Security-architecture precedent | Reuse the separation between signaling, connectivity establishment, and peer-authenticated media/data security as an architectural reference. Browser, origin, SDP, DTLS-SRTP, and IdP-specific requirements are not automatically AetherLink requirements. | Reserved guidance, not a WebRTC conformance claim. |
| [RFC 8828 - WebRTC IP Address Handling Requirements](https://www.rfc-editor.org/rfc/rfc8828.html) | Candidate privacy precedent | Use its IP-exposure analysis to define direct, limited-direct, and relay-only policies; minimize host-candidate disclosure and make privacy posture explicit. | Reserved guidance; product policy must be selected. |
| [RFC 8446 - TLS 1.3](https://www.rfc-editor.org/rfc/rfc8446.html) | Authenticated encrypted signaling and service channels | Require TLS 1.3 with an explicit service trust source, hostname/pin policy, downgrade prevention, certificate rotation, and no unauthenticated fallback. TLS protects the service channel but does not replace end-to-end candidate or peer authentication. | Reserved for production P2P signaling/TURN control channels. |
| [RFC 9000 - QUIC](https://www.rfc-editor.org/rfc/rfc9000.html) | Contingent transport spike | Evaluate connection IDs, path validation, migration, stream fit, flow control, amplification limits, and close behavior only after the transport-neutral secure-session contract is stable. | Contingent reserved option; not the selected baseline. |
| [RFC 9001 - Using TLS to Secure QUIC](https://www.rfc-editor.org/rfc/rfc9001.html) | QUIC cryptographic handshake | For a QUIC spike, bind the AetherLink endpoint identity and pair transcript to the QUIC/TLS handshake or a reviewed exporter-based construction; QUIC server authentication alone must not become pair authentication. | Contingent with RFC 9000. |
| [RFC 9221 - An Unreliable Datagram Extension to QUIC](https://www.rfc-editor.org/rfc/rfc9221.html) | Optional QUIC application datagrams | If the spike requires unreliable application datagrams, evaluate explicit negotiation, size limits, congestion interaction, loss semantics, and fallback separately from RFC 9000 streams. Do not assume QUIC v1 alone provides application datagrams. | Optional contingent extension; not required by the recommended transport-neutral session. |
| [RFC 9180 - Hybrid Public Key Encryption (HPKE)](https://www.rfc-editor.org/rfc/rfc9180.html) | Optional end-to-end candidate-envelope construction | Consider an authenticated, context-bound HPKE profile for candidate confidentiality from signaling storage and operators. Bind pair/session/role/generation metadata as authenticated context and define replay state separately. HPKE is not a signaling protocol, ICE authentication, or a full secure session. | Optional reserved primitive; no ciphersuite is selected. |

## Proposed Protocol Composition

The recommended composition for opportunity 1 is authenticated encrypted
signaling over TLS 1.3, end-to-end protected candidate envelopes, ICE/STUN for
path discovery and checks, and TURN for fallback. Trickle ICE may reduce setup
latency, but its incremental state must remain generation-scoped and bounded.
Consent freshness governs continued transmission after nomination.

The recommended composition for opportunity 2 adds one transport-neutral,
peer-verifiable secure session above whichever ICE candidate pair is nominated.
The transcript must bind both paired identities and roles, pair state,
ephemeral shares, nonces, candidate generation, selected protocol/version, and
enough path context to prevent cross-transport confusion. The secure session is
the application readiness gate on direct and TURN paths.

TLS 1.3 authenticates signaling services; it does not make signaling records
end-to-end confidential from the service. HPKE can protect stored candidate
envelopes if selected, but it does not provide stateful replay protection or
replace the endpoint secure session. QUIC is a contingent transport experiment,
not a prerequisite for ICE, TURN fallback, or endpoint identity binding.

## Profile Decisions Still Required

- Full ICE versus a justified ICE-Lite role, including role-conflict behavior.
- Candidate types, caps, priorities, privacy modes, mDNS/host-candidate policy,
  IPv4/IPv6 behavior, trickle batching, and end-of-candidates semantics.
- STUN and TURN service trust, credential issuance, TLS/transport profile,
  allocation lifetime, permissions, quotas, and regional failover.
- Signaling authorization, storage retention, sequence/idempotency model,
  candidate-envelope construction, key rotation, and replay state.
- Consent interval/failure policy and interaction with mobile suspension,
  reconnect, ICE restart, and path migration.
- Transport-neutral secure-session handshake, identities, algorithms, canonical
  transcript, exporter/channel binding, resumption, rekey, and rollback state.
- QUIC spike success criteria; it must compare UDP reachability, handshake and
  migration behavior, battery, memory, latency, and fallback reliability without
  weakening the transport-neutral identity contract.

## Validation Boundary

Document review can establish that the selected profile maps to the standards;
it cannot establish interoperability or production security. Validation must
eventually include fixed cross-platform vectors, malformed packet corpora,
state-machine/property tests, replay and downgrade negatives, packet capture
review, standards interoperability, and public-network matrices across NAT,
firewall, VPN, IPv4, IPv6, NAT64, mobility, suspend/resume, consent loss, and
TURN outage. None of that evidence exists in this no-device portfolio.
