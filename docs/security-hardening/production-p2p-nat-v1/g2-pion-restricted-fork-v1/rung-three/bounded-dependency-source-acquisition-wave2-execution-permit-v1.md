# G2 Pion dependency source wave2 execution permit v1

## Authorized operation

This permit authorizes one fresh, sequential acquisition of the exact 15
version-specific frontier tuples recorded by the wave2 identity decision.
Each tuple has exactly two HTTPS GET resources and must be requested in
`.mod` then `.zip` order, for exactly 30 requests to `proxy.golang.org:443`.

The runner must create the exclusive `.wave-2-v1.claim` before any network
attempt. The claim persists after any request attempt or uncertain claim
creation and prevents retry. A successful run validates every response against
its held `go.sum` H1 expectation, reopens and revalidates all 30 staged files,
publishes the accepted directory without replacement, writes the success
receipt, and writes the manifest last.

## Fail-closed boundary

Redirects, retries, range or resume requests, alternate mirrors, ambient
proxies, credentials, authorization headers, cookies, authentication
challenges, client certificates, package managers, subprocesses, compilation,
archive extraction, source loading or execution, runtime/product networking,
device work, deployment, and Git operations are not authorized.

The exact resource limits are one MiB per `.mod`, sixteen MiB per ZIP,
sixty-four MiB across all responses, 20,000 entries per archive, 128 MiB
uncompressed per archive, and an integer compression-ratio ceiling of 200.

After a pre-publication failure, the runner retains the claim, removes staging
best-effort, writes one bounded failure receipt, and does not retry. Once final
publication is attempted, any uncertainty is terminal and requires read-only
inspection rather than a failure receipt or rerun.

## Independent readback and project boundary

Runner self-checks are not independent readback. The separately bound readback
checker must reopen every accepted resource twice without network access and
recompute raw SHA-256, `.mod` H1, ZIP H1 and archive structure. Record mode
performs a third full pass, retains all resource and directory descriptors
through receipt-and-manifest publication, and revalidates the named entries
after each write. It also opens and retains the published receipt and manifest
descriptors and revalidates their named entries and exact payloads before
return. Even that readback is not a dependency fixed point, source review,
semantic closure, candidate selection, or release approval; the combined graph
must be rerun separately.

This is a personal-project execution permit. No repository account login,
owner proof, credential, private key, signature, token, password, or user
authentication is required. Product endpoint authentication remains a
separate runtime invariant and is unchanged by this intake.
