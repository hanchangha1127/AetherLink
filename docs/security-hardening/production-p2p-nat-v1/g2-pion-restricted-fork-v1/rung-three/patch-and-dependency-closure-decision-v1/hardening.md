# Security Hardening Review: Pion ICE v4.3.0 Rung-Three Patch And Dependency Closure

## Evidence Basis

We are deciding how a future AetherLink-restricted Pion fork should own its
network, session, resource, diagnostic, and dependency boundaries. I inspected
the retained Pion ICE v4.3.0 archive read-only and used the published two-pass
semantic classification as the canonical finding set. The evidence collection
is bound by SHA-256
`853bec14073a55c21980a306b748bc52aa58ec00d94da11e3a65df2533cb4a1f`;
the local inventory is recorded in [context.md](context.md).

The evidence contains 19 canonical findings: 7 `patch_required` and 12
`unresolved`. It also records useful existing controls, including fixed receive
buffers, STUN checks, source matching, and socket/write abort behavior. We must
preserve those controls, but we cannot count them as closure. The retained root
module metadata names 19 requirements and 44 checksum records, while no bound
dependency source review exists. This means the root patch design and the
dependency review can be prepared together, but neither can prove the other
complete.

## Constraints

This is a balanced, personal-project design review. Repository-owner identity,
external signatures, execution permits, and user action are not prerequisites.
Product endpoint authentication remains a runtime invariant and is not replaced
by ICE reachability or this document.

No Pion source or dependency is modified, extracted, fetched, compiled, loaded,
or executed here. No network, socket, device, deployment, Git, or credential
action is authorized. No option is selected, and no `implementation/` directory
exists. We have no measured latency, memory, battery, NAT, or interoperability
budget, so the performance and resource comparisons below remain source-derived
or hypothetical until later bounded tests.

## Opportunity Portfolio

| Opportunity | Evidence | Options | Recommendation | Proposal |
| --- | --- | --- | --- | --- |
| Capability-gated network boundary | 11 ingress, egress, path, resolution, TURN, and promotion findings | Distributed sink guards; typed capability state machine | Prefer the state machine if we accept a fork-level API change; use sink guards only as a short-lived migration layer | [Capability-gated network boundary](proposals/capability-gated-network-boundary.md) |
| Bounded resource lifecycle | Unbounded events, aggregate resources, and shutdown plus existing abort controls | Independent local ceilings; owned resource supervisor | Prefer one supervisor when exact per-agent and process totals are mandatory | [Bounded resource lifecycle](proposals/bounded-resource-lifecycle.md) |
| Typed secret-free diagnostics | Remote credential and raw candidate/hostname diagnostic findings | Delete known log calls; typed diagnostic sink | Prefer typed events because deletion alone cannot prevent new free-form sinks | [Typed secret-free diagnostics](proposals/typed-secret-free-diagnostics.md) |
| Fixed-point dependency closure | Missing review for 19 requirements and 44 checksum records; resolver and TURN behavior blocked | Single-wave inventory review; staged fixed-point source closure | Prefer staged fixed-point closure before compile authority is considered | [Fixed-point dependency closure](proposals/fixed-point-dependency-closure.md) |

## Recommendation Summary

Under the current exact-boundary requirements, I recommend the structural
option in each opportunity: a typed admission/promotion state machine, a single
resource supervisor, a typed diagnostic sink, and staged fixed-point dependency
closure. These choices move policy from caller convention to owners that can
make invalid states and bypass paths harder to represent. The attraction is not
novel machinery by itself; it is that each high-risk capability has one place
where we can later test consumption, revocation, limits, and failure.

We should still be honest about the cost. The network and lifecycle choices
alter fork APIs and concurrency semantics. The dependency choice requires
several immutable acquisition/review waves rather than one inventory pass. If a
small compatibility patch becomes the dominant constraint, the baseline
options become reasonable temporary steps, but only with an explicit migration
deadline and with closure flags left false.

These are recommendations, not selections. The versioned decision artifact
keeps every selection and implementation field false. A later implementation
handoff must name the selected option set and bind the same evidence collection
or a refreshed version if any source byte changes.

## Next Decisions

The next technical decision is whether to select the four recommended structural
options as one coherent restricted-fork design or to use any baseline option as
a time-bounded migration layer. Separately, a future dependency source-identity
and acquisition decision must predeclare immutable module tuples, provenance,
checksums, archive limits, and stop conditions. That later decision may authorize
a bounded acquisition wave, but this review does not.

If the source archive, semantic finding set, root `go.mod`, root `go.sum`, patch
series, or dependency graph changes, we should issue a new decision version
rather than editing this one in place.
