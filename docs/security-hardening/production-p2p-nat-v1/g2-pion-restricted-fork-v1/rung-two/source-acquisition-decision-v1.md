# G2 Rung-Two Source Acquisition Decision v1

Recorded: 2026-07-23 KST

## Decision

Status is `rung2_source_identity_decision_recorded_acquisition_not_executed`. This decision
authorizes one bounded HTTPS request for one exact Go proxy ZIP; it does not
record that the request occurred. The permit remains `authorized_not_consumed`,
with request count zero in
[`source-acquisition-progress-v1.json`](source-acquisition-progress-v1.json).

The exact upstream base is `github.com/pion/ice/v4` version and lightweight tag
`v4.3.0`, commit
`1e8716372f2bb52e45bf2a7172e4fb1004251c46`, and tree
`df59c87a634cfea261582cd9932554663112a975`. It is only the upstream base for
the not-yet-implemented patch series
`aetherlink-pion-ice-v4.3.0-restriction-v1`. No candidate or library is
selected.

## Parent Boundary

The decision binds the rung-one profile SHA-256
`10e9436ae9b8f24c4447d12f8087b4f121810841ae33526e08fcc3d862d60a0f`,
semantic SHA-256
`9c929d186eedb10cc890d5540597724d6df1d719f174ed1965c79e4d50324be6`,
evidence-manifest SHA-256
`98e0e53955e21a833fe19852ce00f64df2dc808506bdb222c9b8a20bc8006d00`,
and evidence-collection SHA-256
`9e395c4c4f7f61a4810d47cf96ff57b47c1908c73ea459181f1c06f26a35d704`.
It consumes only the next-action scope needed to record this decision.

## Provenance Observation

[`provenance-observation-v1.json`](provenance-observation-v1.json) records a
lightweight tag and a GitHub commit-signature observation with status
`valid_observed_only` and key fingerprint
`686e6e5f8d157de2b8dfa974a8cd240651db01b6`. That commit-signature observation
does not authenticate the Go proxy ZIP and was not locally reverified by this
artifact.

The separate Go checksum-database observation binds record `57312466`, tree
size `57871495`, the supplied verifier key, signed-tree root and signature,
record hash, raw lookup hash, and the ordered 25-hash inclusion proof. These are
provenance inputs, not an acquisition receipt. The local validator independently
recomputes the verifier-key hash, verifies the Ed25519 signed tree, recomputes
the record hash, and verifies its RFC 6962 inclusion proof against that tree.

The decision byte-binds the provenance observation. Forward references use
document identity only, avoiding cyclic hash claims; the later evidence
manifest is responsible for byte-binding the complete ordered set.

## Exact One-Use Permit

| Field | Required value |
| --- | --- |
| URL | `https://proxy.golang.org/github.com/pion/ice/v4/@v/v4.3.0.zip` |
| Host | `proxy.golang.org` only |
| Request count | Exactly one |
| Deadline | 30,000 ms total |
| Expected content length | 293,023 bytes |
| Maximum response | 524,288 bytes |
| Decision-pinned raw SHA-256 | `f95ef3ce2e0063c13925f478bf8d188833725b2f0a7ecb1e695dee8ab61ef63c` |
| Module h1 | `h1:X8l4s9zV2HeTKX33nulWAFXAEo5KhIVzOsY62/3t/LM=` |
| go.mod h1 | `h1:obAyD+J+Hzs7QA7Y8YXHp5uIn6gb7z87pKedXZkrcFU=` |
| Output | `build/offline-source/pion-ice-v4.3.0/original/github.com-pion-ice-v4@v4.3.0.zip` |

The raw SHA-256 is a byte-reproducibility value pinned from the prior public
response observation; it is not an independent upstream authentication root.
The acquired bytes are acceptable only when that decision-pinned raw SHA-256,
module h1, and go.mod h1 all match and the bound checksum-database signature
and inclusion proof verify. Both h1 values must be computed directly from the
ZIP without extracting it.

Before any network I/O, the acquisition runner must atomically claim the permit
and fail closed if a claim or final output already exists. TLS certificate and
hostname validation are mandatory.

Ambient proxies, redirects, credentials, URL queries, package managers, `go`,
`git`, shells, dependency fetches, archive extraction, and source execution are
forbidden. Any mismatch closes the permit, removes or quarantines the bytes,
and requires a new versioned decision. Automatic retry, alternate mirrors, and
wrapper fallback are forbidden.

## Execution And Authentication Boundary

This record performs no acquisition, dependency installation, compilation,
code loading, candidate socket creation, runtime network I/O, device execution,
deployment, or Git operation. `candidateSelected=false` and
`librarySelected=false`. Repository-owner authentication, external identity
proof, and user action are not required. Product endpoint authentication
remains mandatory and separate.

The only next action is the exact one-use archive request followed by an
immutable progress/receipt update. A successful byte and provenance check may
prepare a separate rung-three offline-review decision; it does not implicitly
open that rung.
