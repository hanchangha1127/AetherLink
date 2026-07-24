# Bounded dependency public checksum identity-resolution execution permit v1

This permit authorizes one metadata-only, authentication-free SumDB attempt for
the unresolved module ZIP identity of `github.com/kr/pty@v1.1.1`. The held
`go.mod` identity remains
`h1:pFQYn66WHrOpPYNljwOMqo10TkYh1fy3cYio2l3bCsQ=`. The unresolved ZIP value is
not present in this permit, its checker, its runner, or their tests.

The runner must first create and durably sync the exclusive one-use claim. It
may then issue exactly one direct HTTPS GET to
`https://sum.golang.org/lookup/github.com/kr/pty@v1.1.1`. Ambient proxies,
redirects, authentication, cookies, client certificates, query strings,
fragments, alternate mirrors, retries, resume, and backfill are forbidden.

Before any tile request, the lookup body must be strictly parsed and the signed
tree head verified with the pinned `sum.golang.org` Ed25519 note key. The
record must consist of exactly the target ZIP line followed by the exact held
`go.mod` line. Empty, duplicate, unrelated, additional, CR-containing,
NUL-containing, or trailing record content fails closed.

Only the unique hash-tile paths deterministically required for target-record
inclusion and old-to-new tree consistency may follow the lookup. Paths are
restricted to the canonical `/tile/8/...` grammar on `sum.golang.org`; data
tiles, `/latest`, further lookups, module proxy, module, ZIP, and source
requests are forbidden. The whole claimed attempt is capped at 129 requests,
4 MiB of response bodies, 15 seconds per request, and 120 seconds total.

The pinned older checkpoint has tree size `57871495` and root
`CXAe1gevwtmEqZ3aCCTvv6+nJY5F29T4UGHfB73rJTo=`. A smaller signed tree is a
rollback. An equal-sized tree must have the exact pinned root and needs no
consistency delta. A larger tree must pass RFC 6962 consistency from the pinned
checkpoint. The exact record leaf must also pass inclusion in the signed new
tree. A signed head alone is insufficient.

The claim persists after every network attempt and makes the permit
non-reusable. The runner may write only owner-only metadata evidence in the
reserved identity namespace plus one mutually exclusive success or bounded
failure terminal. Successful evidence is published with fsync and atomic
no-replace operations; the success receipt precedes the manifest, which is
written last. No source bytes, module files, or archives may be acquired,
extracted, loaded, executed, compiled, or placed in a source `accepted`
directory.

Success establishes only a locally verified identity pair and requires an
independent offline readback. It does not authorize dependency source
acquisition, fixed-point closure, semantic review, candidate or library
selection, Git, devices, deployment, product networking, credentials, or user
action.
