# G2 Pion dependency source wave2 execution permit v2

## Recovery boundary

Wave2 v1 stopped before claim creation or any network request because its
permit checker emitted `uid` while the retained filesystem primitive required
`ownerUid`. V1 remains frozen and must not be retried or backfilled. V2 uses a
fresh claim, staging, accepted-directory, receipt, manifest, and readback
namespace. A single strict adapter translates the exact root identity schema,
and both runner and readback must use it. The permit checker opens and closes
the actual repository root through that adapter before authorizing execution.
An owner-only `.wave-2-v1-staging-*` revocation sentinel makes the frozen v1
clean-namespace check fail and is retained by every v2 authority lifecycle.
It is not a claim, failure receipt, or network attempt.

## Authorized operation

This permit authorizes one fresh, sequential acquisition of the same exact 15
version-specific frontier tuples recorded by the wave2 identity decision. Each
tuple has exactly two HTTPS GET resources and must be requested in `.mod` then
`.zip` order, for exactly 30 requests to `proxy.golang.org:443`.
The source decision's v1 output paths are projected only from
`wave-2-v1/accepted` to `wave-2-v2/accepted`; URLs, H1 values, order, and every
other field remain exact. The resulting v2 ordered resource-set digest is
`014e37747510d7b49482a3cbc0401f70d8760cd1ed660a2eb71993a157124a7f`.

The runner must create the exclusive `.wave-2-v2.claim` before any network
attempt. The claim persists after any request attempt or uncertain claim
creation and prevents retry. A successful run validates every response against
its held `go.sum` H1 expectation, reopens and revalidates all 30 staged files,
publishes the accepted directory without replacement, writes the v2 success
receipt, and writes the v2 manifest last. Accepted resource descriptors,
claim, receipt, manifest, and directory identities remain held and are
revalidated after the manifest write before success is returned.

## Fail-closed and readback boundary

Redirects, retries, range or resume requests, alternate mirrors, ambient
proxies, credentials, authorization headers, cookies, authentication
challenges, client certificates, package managers, subprocesses, compilation,
archive extraction, source loading or execution, runtime/product networking,
device work, deployment, and Git operations are not authorized.

The separately bound v2 readback checker must reopen every accepted resource,
recompute raw SHA-256, `.mod` H1, ZIP H1, archive structure, identity and
lineage, retain root/dependency/wave/final directory mode and identity
barriers, and publish its receipt before its manifest. Readback is not a
dependency fixed point, source review, semantic closure, candidate selection,
or release approval; the combined graph must be rerun separately.

No repository account login, owner proof, credential, private key, signature,
token, password, or user authentication is required. Product endpoint
authentication remains a separate runtime invariant.
