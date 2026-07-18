# Phase A libnice Source Audit v1

## Outcome

`libnice-0.1.23-glib-c-abi` is rejected before compilation. The audit used the exact 184-file libnice 0.1.23 tree and exact 1,961-file GLib 2.64.2 tree pinned by their committed manifests. Two independent GPT-5.6 Sol reviews reached the same reject-before-compile result. No source, generator, configure step, build system, compiler, static archiver, linker, test, or library code was executed.

## Independent P1 Blockers

- ICE ufrag, password, and the 64-bit role tie-breaker use the default GLib global PRNG through `g_random_int_range()` (`random/random.c:54-59`, `random/random-glib.c:45-77`, `agent/stream.c:124-130`, `agent/agent.c:1272-1274`). The replacement factory is an internal global hook omitted from the public symbol list, so the proposed public C ABI cannot guarantee cryptographic entropy.
- Reachable diagnostics print ICE, TURN, SOCKS, and HMAC secret material (`stun/stunagent.c:317-320,656-658`, `agent/conncheck.c:1415-1425,2881-2897`, `agent/agent.c:2381-2389,3288-3291`, `socket/socks5.c:115-124`). STUN diagnostics can be enabled from process environment flags.
- STUN and TURN `ALTERNATE-SERVER` handling mutates the destination without a caller authorization callback. A TURN TCP or TLS redirect can immediately create a socket to the replacement tuple (`stun/stunagent.c:218-226`, `agent/conncheck.c:3931-3980,4027-4042`). This violates the selected no-redirect and exact-tuple pre-I/O policy.
- Consent freshness updates `last_received` for every otherwise-unmapped validated response without checking success class, the selected transaction, or source tuple (`agent/conncheck.c:4348-4358,4942-4945`). Credential-free 300, 400, 401, and 438 errors are accepted by validation (`stun/stunagent.c:218-226`).

Each item independently fails a production profile floor. A wrapper-only configuration cannot repair all four internal paths; remediation requires a reviewed source fork or an equivalent explicit internal contract, neither of which is authorized.

## Protocol And ABI Review

Regular nomination, role-conflict comparison, pair-priority recalculation, bounded STUN message parsing, 30-second consent expiry, and send blocking after recorded consent loss are present in the source. These mechanisms do not offset the four blockers.

Cancellation review also found that stream removal cancels TURN resolution but not the agent-wide STUN resolution, while the callback dereferences a possibly removed stream without a null check (`agent/agent.c:2765-2819,4030-4045`). Pseudo-TCP graceful close contains a source-documented reliably triggerable race (`agent/component.c:343-351`).

The upstream symbol surface exports agent, STUN, pseudo-TCP, and debug APIs, while public structures expose pointers and `sockaddr`-backed storage. A product boundary would require opaque handles, copied ownership, stable error mapping, serialized callbacks, hidden upstream symbols, and a reviewed entropy API. No such adapter was created or compiled.

## Supply Chain And Dependency Closure

- libnice archive SHA-256: `618fc4e8de393b719b1641c1d8eec01826d4d39d15ade92679d221c7f5e4e70d`.
- libnice tree SHA-256: `e594b0b2435e10a8df970304ba3dec24ea0353820f1eecb820a810ab56cd276a`.
- GLib archive SHA-256: `9a2f21ed8f13b9303399de13a0252b7cbcede593d26971378ec6cb90e87f2277`.
- GLib tree SHA-256: `1c36d535b42d89b62c375b60005dd3c073033ba5bb4928c6825c09a4bc61d3ac`.

The minimum remaining source set was identified as libffi 3.7.1, GNU libiconv 1.19 for Android API 26, proxy-libintl 0.1 in stub-only mode, and OpenSSL 3.5.7 LTS. Those four sources were not acquired: the candidate failed before the required scope expansion, so further supply-chain work is unnecessary for this candidate.

The detached libnice signature bytes are pinned, but cryptographic signature trust is not claimed because no trusted signing key and OpenPGP verification result were available. This caveat is separate from the security rejection.

## Closed Boundary

No compile contract is created. Additional source acquisition, source forks, compiler or static-archiver invocation, sockets, runtime or harness networking, Phase B, production networking, and deployment remain closed. This is static source and supply-chain rejection evidence, not compilation, ABI, runtime ICE/STUN/TURN, NAT traversal, physical-device, or production evidence.
