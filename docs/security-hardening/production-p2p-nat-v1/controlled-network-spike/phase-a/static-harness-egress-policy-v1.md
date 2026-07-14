# Phase A Static Harness and Egress Policy v1

## Status

- Artifact status: `static_design_complete`
- Execution status: `not_executed`
- Measurement status: `not_started`
- Scope: non-executable Phase A static design evidence only

This artifact does not implement or execute network namespaces, firewall rules, STUN, TURN, packet capture, sockets, process launch, or network I/O. It records a future Phase B design boundary only.

## Immutable Sources

- `../review-v1.json`: review `production_p2p_nat_v1_controlled_network_spike_review_v1`, SHA-256 `744099ec8b0fdd8edf214283661332b0b5deffed7c79211556b98d9ddf544c62`
- `../decision-v1.json`: decision `production_p2p_nat_v1_controlled_network_spike_decision_v1`, SHA-256 `1fd24be7252e25381552d1732c5282f141ef0e9b02118f8c65b246b81a055228`
- `../../implementation/handoff-v4.json`: handoff `production_p2p_nat_v1_handoff_v4`, SHA-256 `b4ecfb30491320383e7ac19cd96fdd7601b91b897bb0fa2019eba187d30509dd`

The companion checker pins the exact SHA-256 of this Markdown artifact and the JSON artifact. Any byte drift requires a new versioned static design.

## Authorization Boundary

`staticHarnessImplementationAuthorized=true` records the approved static-design work. Every execution gate remains exactly false: source-acquisition network I/O, source execution, socket creation, runtime network I/O, harness network I/O, controlled-spike network I/O, controlled-spike socket execution, Phase B execution, Phase B network I/O, Phase B socket execution, Phase B external egress, production network I/O, and production deployment.

## Non-Executable Topology

The design has exactly three conceptual namespaces: `agent-a`, `agent-b`, and `local-services`. Their complete process ID set is exactly `agent_a`, `agent_b`, `stun_service`, and `turn_service`; the two service processes share `local-services`. Each agent has one direct link to `local-services`; there is no agent-to-agent link, host-network attachment, default route, or internet route.

All modeled addresses use documentation ranges. The `agent-a` link is `192.0.2.0/30` and `2001:db8:1::/126`; the `agent-b` link is `198.51.100.0/30` and `2001:db8:2::/126`. The JSON fixes every interface address and peer relationship.

## Exact Tuple Policy

The immutable allowlist has exactly eight bidirectional flows matching `full_ice_regular_nomination_single_component_udp`. For each agent and address family it fixes one STUN UDP flow and one TURN UDP flow to numeric port `3478`. TCP and port `5349` are not allowed. Source addresses, source ports, destination addresses, destination ports, protocol, service role, and namespace are all explicit in the JSON. Only a listed flow or its exact reverse is admissible; implicit tuples and port ranges are prohibited.

DNS, mDNS, DoH, DoT, URLs, redirects, HTTP proxies, SOCKS proxies, PAC, environment proxies, wildcard addresses, mutable endpoints, and external default routes are outside the allowlist and cannot authorize I/O.

A future Phase B run manifest and its signature are both mandatory before execution. The manifest and signature values are currently `null`, both presence flags are `false`, and execution, network I/O, and socket execution remain unauthorized.

## Deny-All Witness Design

The default witness policy is deny-all. Static intent vectors cover hostname DNS, mDNS, DoH, DoT, URL fetch, HTTP proxy, SOCKS proxy, PAC, environment proxy, redirect, wildcard, port range, malformed numeric input, default-route mutation, and allowlist mutation. Static packet vectors are an exact ordered list. Its first four entries are `external-ipv4` (TCP/IPv4), `external-ipv6` (TCP/IPv6), `external-udp-ipv4` (UDP/IPv4), and `external-udp-ipv6` (UDP/IPv6); both UDP vectors target external numeric addresses on port `3478`, so the protocol used by the allowed local fixture path cannot bypass the external-egress witness. The remaining entries cover metadata service, DNS, cross-agent traffic, wrong service port, IPv4 multicast, IPv6 multicast, IPv4-mapped IPv6, IPv4/IPv6 loopback, IPv4/IPv6 link-local, broadcast, unlisted private, and IPv4/IPv6 unspecified destinations. Missing entries, reordering, or protocol, address, and port drift are invalid.

The intent-policy witness and packet-observation witness are independent. A future approved implementation must reject before I/O or drop the packet, then kill all harness processes and invalidate the run. This document contains no implementation or execution evidence for either witness.

The companion checker uses Python AST parsing only for its owned-source policy and does not execute parsed source. Imports or references that provide network, HTTP, process-launch, native-code, or dynamic-import capability are prohibited, including `socket`, `http`, `urllib`, `requests`, `subprocess`, `os`, `ctypes`, `multiprocessing`, `importlib`, and `builtins`. Direct or indirect access to `__import__`, `eval`, `exec`, `compile`, `getattr`, `__builtins__`, or `sys.modules` is also prohibited.

## Exact Resource Ceilings

The 12 ceilings are fixed without ranges or defaults:

| Ceiling | Exact value |
| --- | ---: |
| Agent process count | 2 |
| Maximum local service process count | 2 |
| Maximum run seconds | 600 |
| Maximum setup seconds | 120 |
| Maximum session establishment seconds | 60 |
| Maximum consent observation seconds | 45 |
| Maximum CPU cores per process | 1 |
| Maximum resident memory MiB per process | 256 |
| Maximum file descriptors per process | 64 |
| Maximum sockets per process | 16 |
| Maximum captured packets per run | 10000 |
| Maximum captured bytes per run | 16777216 |

## Content-Free Evidence

Retained evidence is limited to bounded reason codes, counters, durations, numeric endpoint labels, and redacted structural SHA-256 digests. The JSON pins exact regular expressions for all four text classes, maximum duration `600000` milliseconds, maximum counter value `16777216`, and `retainedRuntimeEvents=[]`. Packet payload retention and application payload admission are both exactly zero bytes. Raw packets, raw candidates, secrets, keys, tokens, credentials, nonces, application content, hostnames, URLs, command lines, and environment values are prohibited.

## Kill on Drift

Allowlist mutation, route drift, DNS or proxy attempts, redirect attempts, witness failure, any resource or time ceiling breach, any packet outside the exact tuple set, payload observation, evidence-content violation, or namespace-topology drift applies all four exact actions: terminate `agent_a`, `agent_b`, `stun_service`, and `turn_service`; invalidate the run; discard every measurement; and retain only a content-free drift record. Continuation and valid measurement after drift are prohibited.

## Phase B Boundary

Phase B is `blocked_on_phase_a_evidence_and_separate_versioned_decision`, remains `unproven`, has not been executed, and has no measurements. `phaseBExecutionAuthorized=false`; Phase B network I/O, socket execution, and external egress are also unauthorized. A separate versioned decision after Phase A security review is required before any socket execution.
