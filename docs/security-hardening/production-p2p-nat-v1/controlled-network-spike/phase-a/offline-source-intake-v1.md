# Phase A libjuice Offline Source Intake v1

## Current State

- Artifact status: `blocked_missing_offline_source`.
- Source presence: `absent`.
- Source audit: `not_started`.
- Compile work: `not_started`.
- Expected repo-relative intake root: `build/offline-source/libjuice-1.7.2`.

The expected intake root must not exist for this v1 blocked-state record. If the
path exists, including as a symlink, the checker fails closed without reading,
discovering, extracting, executing, compiling, or otherwise consuming it. A new
reviewed versioned manifest is required before any source inspection or compile
work can be claimed.

## Source Chain

This record pins the exact current bytes of its approval chain:

| Record | SHA-256 |
| --- | --- |
| `../review-v1.json` | `744099ec8b0fdd8edf214283661332b0b5deffed7c79211556b98d9ddf544c62` |
| `../decision-v1.json` | `1fd24be7252e25381552d1732c5282f141ef0e9b02118f8c65b246b81a055228` |
| `../../implementation/handoff-v4.json` | `b4ecfb30491320383e7ac19cd96fdd7601b91b897bb0fa2019eba187d30509dd` |

The fixed candidate is `libjuice-1.7.2-static-c-abi`, release tag `v1.7.2`.
The repository, release, and archive URLs in the JSON are provenance metadata
only. They do not authorize fetching, redirects, package-manager acquisition,
DNS, sockets, or any other network I/O.

## Future Offline Intake

A future manual intake must preserve these exact locations below the fixed root:

- `original/libjuice-1.7.2.tar.gz`: the unmodified original archive.
- `source`: the extracted source tree.
- `source-provenance.json`: the reviewed provenance record.

The future `source-provenance.json` must use exactly the keys and nested schemas
declared by `requiredFutureProvenanceSchema`. It must bind the exact `v1.7.2`
tag to a non-null 40-character lowercase commit SHA-1, the archive to a non-null
SHA-256 and exact size, and the extracted tree to a deterministic tree SHA-256,
file count, and byte count. Every regular file must have a unique normalized
relative POSIX path, mode, size, and SHA-256 in bytewise path order.

The same record must review all license files and SPDX results, classify every
source/generated/vendored-generated file, disclose direct and transitive
bundled/system/toolchain dependencies, and record ordered literal Android
minSdk 26 and macOS compiler, target, preprocessor, C, and linker flags. Network
tests and source execution remain false for both platforms.

Absolute paths, `..` traversal, backslashes, empty segments, symlinks,
hardlinks, special files, glob discovery, recursive discovery, unknown or
missing JSON names, duplicate JSON names, non-standard numbers, bool/integer
substitution, changed limits, shell expansion, response files, and environment
substitution are rejected. Exceeding a fixed limit rejects the intake; this
record does not authorize relaxing a limit.

## Proof Boundary

All current commit, archive, tree, file-set, and provenance hashes are `null`.
License, generated-file, dependency, and build-flag results are also `null`.
This record proves only the fail-closed blocked/absent intake contract. It is not
source acquisition, source audit, compilation, source execution, socket or
network execution, ICE/STUN/TURN traffic, NAT traversal, device validation,
deployment, or production-readiness evidence.
