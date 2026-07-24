# Bounded dependency public checksum identity-resolution decision v1

This decision preserves the exact Wave3 gap for
`github.com/kr/pty@v1.1.1`: its held `go.mod` identity is
`h1:pFQYn66WHrOpPYNljwOMqo10TkYh1fy3cYio2l3bCsQ=`, while its module ZIP
identity remains unknown. No ZIP H1 is guessed, inferred, or hardcoded.

The selected design is a strict deterministic adaptive one-use SumDB FSM. A
future, separately bound permit may make exactly one lookup request to
`https://sum.golang.org/lookup/github.com/kr/pty@v1.1.1`. Only after the
lookup's signed tree head is verified with the pinned key may that same claimed
attempt request the unique `/tile/8/...` hash-tile paths deterministically
needed to verify record inclusion and consistency from the pinned older tree.
The request sequence is bounded to 129 total requests and 4 MiB of response
bodies. It cannot request source, module, ZIP, proxy, latest-tree, or data-tile
resources.

The exact lookup record must contain two and only two target lines: the module
ZIP H1 line and the already-held `go.mod` H1 line. Empty, unrelated, duplicate,
or extra records fail closed. Acceptance also requires the pinned-key signed
note, RFC 6962 record inclusion, and old-to-new tree consistency. A smaller
tree is rollback and forbidden; an equal-sized tree must have the exact pinned
root; a larger tree requires a valid consistency proof. Key rotation and trust
on first use are forbidden.

This document is not a network or execution permit. Network, filesystem
mutation, source acquisition, extraction, loading, execution, compilation,
package-manager and Go command use, subprocesses, Git, devices, deployment,
authentication, credentials, and user action are all unauthorized. The
planned namespace is metadata-only and separate from every source `accepted`
directory. A claim must precede any future network attempt and survives any
attempt; retry, resume, and backfill are forbidden.

The only next action is to prepare a separately bound one-use permit, checker,
runner, and tests for this FSM. Even a successfully verified ZIP H1 would only
complete the identity pair. It would not acquire source or establish
dependency closure, review, candidate selection, library selection, or release
readiness.
