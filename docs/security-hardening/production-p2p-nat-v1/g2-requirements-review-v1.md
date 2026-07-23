# G2 New P2P/NAT Stack Requirements Review v1

Recorded: 2026-07-23 KST

## Scope And Result

This began as the first, read-only rung of the canonical G2 ladder. A bounded
follow-up then inspected the exact Pion v4.3.0 tag through public official
source pages. It did not download or retain source, install a toolchain or
dependency, compile or load third-party code, create a socket, perform network
traversal, or select a production library.

No repository-owner identity proof, GitHub authentication, SSH/GPG signature,
credential, or user-supplied approval receipt is needed for this personal-
project review. Product endpoint authentication and session encryption remain
separate AetherLink protocol requirements; an ICE credential never substitutes
for them.

Outcome: no library is selected. Unmodified Pion ICE v4.3.0 is rejected at the
official-source preflight because it does not meet AetherLink's non-bypassable
destination-policy, secret-free logging, bounded-callback, and deterministic-
shutdown requirements. PJNATH 2.17 and Google libwebrtc native remain rejected
at the requirements rung for the current AetherLink scope.

## Candidate Dispositions

### Pion ICE v4.3.0

Disposition: `rejected_at_official_source_preflight_as_is`.

- The exact v4.3.0 tag resolves to commit
  [`1e8716372f2bb52e45bf2a7172e4fb1004251c46`](https://github.com/pion/ice/commit/1e8716372f2bb52e45bf2a7172e4fb1004251c46).
  The module is `github.com/pion/ice/v4` with Go 1.24.0, and the official
  project publishes it under the MIT license.
- Its public API exposes an underlying network abstraction, local interface and
  IP filters, a remote-IP filter, candidate/network-type controls, mDNS mode,
  bounded timing/retry settings, and synchronous agent shutdown.
- A narrow Go wrapper could in principle target Android and macOS through
  `gomobile`, but the current Go Mobile module is untagged and not declared
  stable. Reproducible four-ABI packaging is therefore unproven.
- Exact tagged source confirms that those requirements are not met as-is:
  Active ICE-TCP bypasses the injected `transport.Net`; proxy and legacy mux
  paths are not uniformly context-cancellable; STUN, TURN, mDNS, and final
  sends do not cross one common post-resolution pre-I/O policy; debug logging
  includes the remote ICE password; callback queues grow without a declared
  bound; and graceful shutdown may wait indefinitely on a blocked callback.

Primary references:

- [Pion ICE v4.3.0 release](https://github.com/pion/ice/releases/tag/v4.3.0)
- [Pion ICE v4.3.0 module definition](https://github.com/pion/ice/blob/v4.3.0/go.mod#L1-L28)
- [Active ICE-TCP direct network path](https://github.com/pion/ice/blob/v4.3.0/active_tcp.go#L20-L77)
- [Remote ICE password debug log](https://github.com/pion/ice/blob/v4.3.0/agent.go#L502-L513)
- [Unbounded callback queue implementation](https://github.com/pion/ice/blob/v4.3.0/agent_handlers.go#L35-L155)
- [Pion ICE v4 API](https://pkg.go.dev/github.com/pion/ice/v4)
- [Pion ICE license](https://github.com/pion/ice/blob/main/LICENSE)
- [Go Mobile bind documentation](https://pkg.go.dev/golang.org/x/mobile/cmd/gomobile)

### PJNATH / pjproject 2.17

Disposition: `rejected_at_requirements_rung`.

- The project is maintained and provides C APIs for STUN, TURN, and ICE with
  Android and macOS build documentation.
- The available license is GPL-2.0-or-later or a separate commercial license,
  which is not accepted for the current V1 dependency profile.
- High-level ICE paths retain internal socket, resolver, keepalive, logging,
  and optional UPnP surfaces. A low-level callback wrapper could reduce that
  surface, but it would not remove the current license blocker or the larger
  lifecycle audit cost.

Primary references:

- [pjproject 2.17 release](https://github.com/pjsip/pjproject/releases/tag/2.17)
- [PJSIP licensing](https://docs.pjsip.org/en/2.17/overview/license_pjsip.html)
- [PJNATH ICE transport API](https://docs.pjsip.org/en/2.17/api/generated/pjnath/group/group__PJNATH__ICE__STREAM__TRANSPORT.html)
- [PJNATH TURN session API](https://docs.pjsip.org/en/2.17/api/generated/pjnath/group/group__PJNATH__TURN__SESSION.html)

### Google libwebrtc native

Disposition: `rejected_at_requirements_rung`.

- The upstream source remains actively maintained and supports the target
  platforms, but it is a rolling source tree rather than a small, independent
  stable ICE release.
- The official native-code guidance targets browser developers, and the build
  uses the Chromium toolchain with a multi-gigabyte dependency surface.
- Its default networking, resolver, proxy, mDNS, regather, logging, DTLS, SRTP,
  and broad C++ API surface would make a minimal auditable AetherLink ICE layer
  substantially harder to reproduce and keep separate from endpoint identity
  and application-session cryptography.

Primary references:

- [libwebrtc source](https://webrtc.googlesource.com/src/)
- [libwebrtc native-code guidance](https://webrtc.googlesource.com/src/+/refs/heads/main/docs/native-code)
- [libwebrtc development and checkout guidance](https://webrtc.googlesource.com/src/+/refs/heads/main/docs/native-code/development/README.md)
- [libwebrtc license](https://webrtc.googlesource.com/src/+/refs/heads/main/LICENSE)

## Bounded Next Technical Rung

There is no approved unmodified candidate to acquire or compile. A later G2
slice may either review a new exact library/version from rung one or propose a
minimal maintained Pion fork/restriction profile that, before acquisition,
removes the password log, funnels every resolution/dial/write path through one
destination policy, bounds and isolates callbacks, and makes proxy/mux and
shutdown paths deadline-aware. That proposal would still need exact dependency
closure, license/SBOM, patch-maintenance, reproducible Android/macOS ABI, and
offline source review before compile work.

This document does not acquire source and does not open the compile, loopback,
controlled-network, external-network, or production rungs.
