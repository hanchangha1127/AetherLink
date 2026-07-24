# G2 Rung-Three Bounded Dependency Source Identity And Acquisition Decision v1

Recorded: 2026-07-24 KST

## Decision

This decision freezes the first staged fixed-point dependency wave for Pion ICE
`v4.3.0`. The wave contains exactly the 19 requirements recorded in the retained
root `go.mod`; the four checksum-only context tuples remain quarantined and are
not selected.

The decision prepares one future, bounded, sequential acquisition wave from the
public Go module proxy. It does not authorize or claim any request, download,
source review, graph expansion, compilation, or runtime operation. A separate
versioned one-use execution permit must bind this decision, its checker, the
runner, and their tests before any source-acquisition network I/O is allowed.

The wave is intentionally a conservative root seed. Test-only, tool-only,
example-only, platform-specific, generated, native, vendored, replaced, and
excluded sources are classified only after immutable source bytes are retained.
Selecting a tuple for this bounded intake is not a production-reachability,
license-compatibility, dependency-closure, candidate-selection, or
library-selection claim.

## Bound Predecessor

The decision directly binds:

- the current implementation-or-dependency review decision and its content
  binding;
- the selected staged fixed-point implementation plan;
- the current decision checker and its tests;
- the complete patch/dependency preparation portfolio and semantic-review
  triad through the current predecessor;
- the retained Pion archive, tree, `go.mod`, and `go.sum` identities;
- the restricted-fork target profile;
- the historical Pion SumDB provenance observation, source-acquisition
  decision, and successful retained-archive receipt.

Any predecessor, profile, source-snapshot, root-seed, checker, or plan drift
requires a new version. This record is append-only and must not be edited to
adapt to later source or graph observations.

The read-only checker must open the retained root ZIP through one stable,
no-follow, single-link descriptor. It rehashes the exact 293,023 ZIP bytes,
reads all 129 in-memory entries without filesystem extraction, recomputes the
1,131,286-byte source-tree digest, and independently rehashes the embedded
`go.mod` and `go.sum`. It also proves that the wave claim, staging prefix,
accepted directory, success receipt, failure receipt, and manifest are absent
both before validation and at the final identity barrier. A missing or changed
root ZIP, or any premature execution artifact, fails the preparation check.

## Frozen Production Review Profiles

The dependency graph is evaluated as the union of these V1 compile targets:

| Profile | GOOS | GOARCH | cgo | Platform floor | Explicit build tags |
| --- | --- | --- | --- | --- | --- |
| Android V1 | `android` | `arm64` | enabled | API 26 through 36 | none |
| macOS V1 | `darwin` | `arm64` | enabled | macOS 14 or newer | none |

Both profiles use Go `1.24.0`, the `gc` compiler constraint, the platform's
implicit `unix`, architecture, cgo, and release tags through `go1.24`, and no
caller-supplied tags. `_test.go` files, external test packages, examples,
commands, tools, benchmarks, and fuzz entry points do not establish production
reachability. Generated, assembly, cgo, native, vendored, and build-script
inputs are never silently omitted; they are separately classified and remain
review-required when selected by either profile.

The exact root metadata contains no `replace`, `exclude`, `retract`,
`toolchain`, `vendor`, or workspace directive. A later selected module may
introduce supported directives only through a newly versioned graph decision.
Unknown or conflicting module directives fail closed.

Graph expansion uses deterministic Go 1.24 minimum-version selection over the
union of both profile import graphs. Every module/version node and directed
require/import reason is canonicalized and ordered. A newly selected tuple,
version change, replacement, exclusion, or profile change requires a new
bounded decision before another request. A fixed point requires two independent
builders to reproduce the exact node, edge, and graph digests.

## First Wave Source Identities

Every selected tuple has exactly one HTTPS ZIP request, one expected module ZIP
`h1`, one expected `go.mod` `h1`, and one no-overwrite output path.

| Order | Module and version | Root class | Expected module ZIP h1 | Output file |
| --- | --- | --- | --- | --- |
| 1 | `github.com/google/uuid@v1.6.0` | direct | `h1:NIvaJDMOsjHA8n1jAhLSgzrAzy1Hgr+hNrb57e+94F0=` | `001-c7683a099605cf146d8d.zip` |
| 2 | `github.com/pion/dtls/v3@v3.1.5` | direct | `h1:9xJtVsHwMYeSjPp5Hh1FTis4DchnQWtnOa5o+6ygqfc=` | `002-c4e8ffbb48deb188a3c2.zip` |
| 3 | `github.com/pion/logging@v0.2.4` | direct | `h1:tTew+7cmQ+Mc1pTBLKH2puKsOvhm32dROumOZ655zB8=` | `003-86cd416af67cef255d1a.zip` |
| 4 | `github.com/pion/mdns/v2@v2.1.0` | direct | `h1:3IJ9+Xio6tWYjhN6WwuY142P/1jA0D5ERaIqawg/fOY=` | `004-73c3ff091d7cba5359a8.zip` |
| 5 | `github.com/pion/randutil@v0.1.0` | direct | `h1:CFG1UdESneORglEsnimhUjf33Rwjubwj6xfiOXBa3mA=` | `005-0f65ef6c49c45df3e9a5.zip` |
| 6 | `github.com/pion/stun/v3@v3.1.6` | direct | `h1:WnhsD0eHCiwCfKNkVx0VJJwr2Y3eV4Ueih3KJ+dfZy8=` | `006-d21718efc602b3f97741.zip` |
| 7 | `github.com/pion/transport/v4@v4.0.2` | direct | `h1:ifYlPqNwsy6aKQ9y8yzxXlHae5431ZrH2avkD/Rn6Tk=` | `007-6312023846b9c2bcc844.zip` |
| 8 | `github.com/pion/turn/v5@v5.0.12` | direct | `h1:6+b69ivQQXSlyfkp2AKripqD2k3W32qXK8QzCzpJWPI=` | `008-233d1d4c3997850aea8c.zip` |
| 9 | `github.com/stretchr/testify@v1.11.1` | direct | `h1:7s2iGBzp5EwR7/aIZr8ao5+dra3wiQyKjjFuvgVKu7U=` | `009-f106745b2c482a4bb91d.zip` |
| 10 | `golang.org/x/net@v0.49.0` | direct | `h1:eeHFmOGUTtaaPSGNmjBKpbng9MulQsJURQUAfUwY++o=` | `010-ec8b158caf646682189e.zip` |
| 11 | `github.com/davecgh/go-spew@v1.1.1` | indirect | `h1:vj9j/u1bqnvCEfJOwUhtlOARqs3+rkHYY13jYWTU97c=` | `011-466356e1ed2923ec3585.zip` |
| 12 | `github.com/kr/pretty@v0.1.0` | indirect | `h1:L/CwN0zerZDmRFUapSPitk6f+Q3+0za1rQkzVuMiMFI=` | `012-2055c3218667fc22d930.zip` |
| 13 | `github.com/pmezard/go-difflib@v1.0.0` | indirect | `h1:4DBwDE0NGyQoBHbLQYPwSUPoCMWR5BEzIk/f1lZbAQM=` | `013-c5393af9e4df210ac22d.zip` |
| 14 | `github.com/wlynxg/anet@v0.0.5` | indirect | `h1:J3VJGi1gvo0JwZ/P1/Yc/8p63SoW98B5dHkYDmpgvvU=` | `014-8538796efdb1b305492d.zip` |
| 15 | `golang.org/x/crypto@v0.48.0` | indirect | `h1:/VRzVqiRSggnhY7gNRxPauEQ5Drw9haKdM0jqfcCFts=` | `015-fcd48846ebac09f78d86.zip` |
| 16 | `golang.org/x/sys@v0.41.0` | indirect | `h1:Ivj+2Cp/ylzLiEU89QhWblYnOE9zerudt9Ftecq2C6k=` | `016-71145185b09936aa4220.zip` |
| 17 | `golang.org/x/time@v0.14.0` | indirect | `h1:MRx4UaLrDotUKUdCIqzPC48t1Y9hANFKIRpNx+Te8PI=` | `017-a08c27f5a82acd1e8766.zip` |
| 18 | `gopkg.in/check.v1@v1.0.0-20190902080502-41f04d3bba15` | indirect | `h1:YR8cESwS4TdDjEe65xsg0ogRM/Nc3DYOhEAlW+xobZo=` | `018-242f1321dbe83c2f336e.zip` |
| 19 | `gopkg.in/yaml.v3@v3.0.1` | indirect | `h1:fxVm/GzAzEWqLHuvctI91KS9hhNmmWOoWu0XTYJS7CA=` | `019-495087f35325ae50e341.zip` |

## Source Identity And Provenance Boundary

The retained Pion module ZIP was previously checked against its module `h1` and
a locally verified public SumDB signed-tree inclusion proof. That exact ZIP
contains the root `go.sum` bytes bound by this decision. Each wave ZIP must
therefore match the corresponding module and `go.mod` `h1` from those exact
root bytes.

This is a content-identity chain for the source-review input. It is not a direct
attestation by each dependency's repository owner, it does not prove a
repository commit or tag, and it does not prove license compatibility,
production reachability, graph closure, or safe behavior. No dependency source
is accepted merely because it came from the proxy. The ZIP structure, module
prefix, module `h1`, embedded `go.mod` `h1`, size, and all finite limits must
match.

The raw SHA-256 and observed byte length of each accepted ZIP are recorded only
in the later receipt. Those observed values provide reproducible byte identity;
they are not invented in advance and are not an independent upstream
authentication root.

## Planned Exact One-Use Wave Contract

A later execution permit may allow the runner to issue at most 19 requests,
sequentially in table order, and exactly one request per selected tuple on
success. This preparation does not grant that authority.

- Scheme: HTTPS only.
- Host: `proxy.golang.org` only.
- Path: the exact lower-case module path followed by `/@v/<version>.zip`.
- Status: HTTP 200 only.
- Response types: `application/zip` or `application/octet-stream`.
- TLS certificate and hostname validation: required.
- Redirects, ambient proxies, credentials, authentication challenges, URL
  queries, URL fragments, retries, mirrors, and fallback wrappers: forbidden.
- Package managers, `go`, `git`, shells, subprocesses, compilers, source
  loaders, generators, hooks, tests, initialization, extraction, and source
  execution: forbidden.
- First mismatch: stop the wave, publish bounded failure evidence, retain no
  accepted final set, consume the permit, and require a new decision version.

The runner atomically claims the one-use permit before network I/O. It uses
owner-only directory descriptors, no-follow traversal, exclusive file creation,
single-link regular-file checks, exact ancestor identities, and an atomic
no-replace final directory publication. A pre-existing claim, staging entry,
final output, receipt, symlink, hardlink, special file, unexpected sibling, or
identity change fails before the next network request.

## Finite Limits

| Limit | Value |
| --- | ---: |
| Selected modules and maximum requests | 19 |
| Per-request deadline | 30,000 ms |
| Whole-wave deadline | 300,000 ms |
| Per-response compressed bytes | 16,777,216 |
| Aggregate compressed and retained bytes | 134,217,728 |
| Entries per archive | 16,384 |
| Entries across the wave | 131,072 |
| Central-directory bytes per archive | 8,388,608 |
| Single uncompressed file bytes | 16,777,216 |
| Uncompressed bytes per archive | 268,435,456 |
| Aggregate uncompressed bytes | 1,073,741,824 |
| Compression ratio | 200 |
| Path bytes | 1,024 |
| Path components | 64 |
| Component bytes | 255 |
| Graph nodes | 512 |
| Graph edges | 4,096 |
| JSON receipt or failure bytes | 2,097,152 |

All limits are exact integers. Booleans, floats, missing fields, zeros, negative
values, overflow, or values above the decision fail closed.

## Receipt And Failure Contract

Success publishes the complete accepted directory as one no-replace set and
then records:

- the decision and predecessor identities;
- request count, order, exact final URLs, TLS policy result, and status codes;
- each tuple, source URL, raw byte length, raw SHA-256, module `h1`, `go.mod`
  `h1`, entry count, uncompressed byte count, prefix, mode, and link count;
- the ordered source-set digest;
- zero extraction, source execution, package-manager, compiler, socket-runtime,
  device, deployment, and Git-operation counts;
- a manifest-last marker and independent stable readback.

Module ZIP H1 uses the Go
`golang.org/x/mod/sumdb/dirhash.HashZip(Hash1)` v1 algorithm after structural
validation. Explicit directory entries, duplicate names, invalid UTF-8 names,
and names containing LF are rejected before hashing. Every remaining regular
central-directory entry appears exactly once. Entries are sorted by exact
UTF-8 bytes, each row is lowercase hexadecimal SHA-256 of the uncompressed
content, two ASCII spaces, the full ZIP entry name, and LF. SHA-256 of the
concatenated rows is encoded as `h1:` plus padded RFC 4648 standard Base64.

The `go.mod` H1 uses the same Hash1 row algorithm over exactly one synthetic
filename, `go.mod`, and the exact response bytes. Its sole row is the lowercase
hexadecimal SHA-256 of those bytes, two ASCII spaces, `go.mod`, and LF; its
SHA-256 is encoded with the same `h1:` Base64 form.

The ordered source-set digest is SHA-256 of one canonical JSON document with
schema `aetherlink.g2-pion-dependency-source-set-digest.v1` and a `sources`
array in exact wave order 1 through 19. Each source object contains exactly:
`order`, `tupleId`, `module`, `version`, `url`, `outputPath`, `rawByteSize`,
`rawSha256`, `moduleZipH1`, `goModH1`, `entryCount`,
`uncompressedByteCount`, `modulePrefix`, `mode`, and `linkCount`. JSON uses
ASCII escaping, sorted object keys, compact separators, UTF-8, one final LF,
finite integers, and no digest field inside its own scope.

Failure records only bounded reason codes, the failed tuple ID, completed
request count, and safe numeric observations. It records no credentials,
cookies, authorization headers, raw certificates, response bodies, filesystem
absolute paths, or sensitive transport values. Partial bytes and staging state
are removed or quarantined outside the accepted path. Automatic retry is
forbidden.

## State And Non-Claims

At this decision checkpoint:

- source acquisition and public-proxy network I/O remain unauthorized;
- acquisition execution, source extraction, dependency review, graph
  expansion, compilation, code loading, runtime sockets, device work,
  deployment, and Git writes have not occurred;
- all 19 canonical findings remain open;
- dependency closure, semantic closure, rung-three completion, candidate
  selection, and library selection remain false;
- direct P2P remains disabled and the authenticated sealed relay remains the
  rollback path.

Neither repository-owner identity proof, external authentication, nor user
action is required. No credential, private key, signature, token, or account
login is requested. Upstream checksum and transport validation are automated
technical source-integrity checks and are not user authentication.

The only next action is to implement and validate the bounded runner and then
prepare a separate versioned one-use execution permit that binds the decision,
checker, runner, and tests. The runner may execute only after that permit passes.
