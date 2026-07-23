# G2 Pion Restricted-Fork Review Context

This directory is a derived, revisable design review with
`implementationStatus=not_implemented` and runtime verification
`not_executed`. It does not modify or supersede source evidence, select a
networking library, or authorize source acquisition, dependency installation,
compilation, loading, sockets, network traffic, device execution, deployment,
or Git operations.

This is a personal, single-owner project. Repository-owner identity proof,
SSH/GPG proof, role receipts, external identity authentication, and additional
user action are not prerequisites for this design review. Product endpoint
authentication remains a separate required AetherLink security property; ICE
reachability and TURN service authentication never authenticate an endpoint.

## Evidence inventory

The ordered machine-readable registry is
[`evidence-manifest-v1.json`](evidence-manifest-v1.json). Its ordering rule is
`ascending_evidence_id`, and the collection digest input is one UTF-8/LF line
per artifact in the form
`evidence_id<TAB>sha256<TAB>repo_relative_path<LF>`.

| ID | Reader-facing title | Repository-relative path | SHA-256 | Use |
| --- | --- | --- | --- | --- |
| `G2E001` | G2 new-stack requirements and Pion v4.3.0 as-is rejection | `docs/security-hardening/production-p2p-nat-v1/g2-requirements-review-v1.md` | `1874e43121997023b64b9f370c1782f46f8409630b6096ec8175009b300c246b` | Establishes the exact upstream baseline, as-is rejection, and pre-acquisition boundary. |
| `G2E002` | AetherLink V1 G0 decision | `docs/v1/g0/decision-v1.md` | `ec22b033746083712909f58aa56d9ec72cae5131363a90ee36e6e797ea87c0fb` | Establishes the V1 platform matrix, two-plane route design, endpoint-identity floor, route authorization, and privacy boundary. |
| `G2E003` | Canonical V1 roadmap | `docs/roadmap.md` | `2fcb2e60b39d6ea843179d84c29bb57ac5219d20b2b2454c0165e420e1c462a5` | Establishes active personal-project governance, the sequential G2 technical ladder, candidate requirements, and the current no-selection/no-runtime boundary. |
| `G2E004` | Canonical session handoff | `docs/handoff.md` | `f3f43bd602660bc01d5fcbde54550423abcc72ae73ce705021d1ef3b4f4fd2d4` | Establishes the current personal-project instruction boundary and confirms that Pion source, compilation, loading, sockets, and network execution have not occurred. |

- Evidence-manifest SHA-256:
  `98e0e53955e21a833fe19852ce00f64df2dc808506bdb222c9b8a20bc8006d00`
- Ordered evidence-collection SHA-256:
  `9e395c4c4f7f61a4810d47cf96ff57b47c1908c73ea459181f1c06f26a35d704`

The four IDs and their order are fixed for this portfolio. The manifest,
roadmap, handoff, and collection values above are byte-bound as one finalized
integrity inventory; any later byte change requires all related digests to be
reviewed and refreshed together.

## Target context

- Workspace: `/Users/hanchangha/Desktop/project`
- Exact upstream shape under comparison: Pion ICE v4.3.0, commit
  `1e8716372f2bb52e45bf2a7172e4fb1004251c46`.
- Compared shapes: unmodified upstream, a wrapper-only gateway, and an
  AetherLink-maintained exact-base restricted fork.
- Recommendation scope: among those three reviewed Pion v4.3.0 shapes only.
- Status: `rung1_profile_complete_candidate_not_selected`.
- Result: `pion_restricted_fork_profile_ready_for_rung2_decision_only`.
- Next action:
  `prepare_versioned_rung2_source_identity_and_acquisition_decision`.
- Source drift: none in the finalized four-artifact evidence inventory.
- Review date: 2026-07-23 KST.
- Product targets: Android API 26 through 36 on `arm64-v8a`, and macOS 14 or
  newer on Apple Silicon `arm64`.

## Evidence limitations

- The exact upstream source archive, detached signatures, full module closure,
  and transitive licenses have not been acquired or independently verified.
- The proposed fork patches do not exist. The network, TURN TLS,
  secure-session promotion, carrier, fragmentation/reassembly, resource,
  diagnostic, event, and shutdown contracts are requirements only.
- Every runtime-verification row is `not_executed`; no source has been retained,
  compiled, loaded, or executed for this candidate.
- The reviewed public source and release pages support a pre-acquisition design
  comparison, not an upstream support-policy guarantee.
- No performance, battery, memory, NAT, socket, device, interoperability,
  implementation, selection, or production-readiness result is claimed.
