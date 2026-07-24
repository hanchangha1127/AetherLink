# G2 Pion dependency wave-one v2 recovery decision

Date: 2026-07-24

Status: v2 terminal failure read back; v3 ZIP-plus-mod design selected; v3 execution not authorized by this document.

## Observed terminal state

The v2 permit was consumed exactly once. Eleven ZIP response bodies completed,
ten tuples validated into temporary staging, tuple 11
`github.com/davecgh/go-spew@v1.1.1` stopped with `E_GO_MOD_MISSING`, staging was
removed, and no accepted final set was published. The v2 claim and bounded
failure receipt remain immutable evidence. v2 must not be retried.

## Root cause

The v2 runner treated the module ZIP and module `.mod` as one resource by
requiring a root `go.mod` inside every ZIP. A valid Go proxy ZIP can omit that
file, especially for a pre-module release, while the proxy's `.mod` endpoint
supplies the separately checksummed module file. This is a resource-model
compatibility error, not an owner, credential, signature, or authentication
failure.

## Selected v3 design

For each of the same 19 ordered tuples, v3 will request the exact `.mod` and
then the exact `.zip` URL from `proxy.golang.org`. A successful wave therefore
requires exactly 38 sequential HTTPS responses, 38 separately validated and
retained resources, and 19 complete tuple pairs.

The ZIP is accepted only after its exact module ZIP H1, archive structure,
module prefix, absolute size, entry, and decompression limits pass. A ZIP-root
`go.mod` is not required. When present, it must byte-match the separately
validated `.mod` response. The exact `.mod` response bytes are accepted only
after UTF-8/NUL and exact module-directive checks and their single-`go.mod` H1
matches the existing tuple's `goModH1`. No
package manager, Go command, Git command, shell, compiler,
extraction, source loading, source execution, product network, device,
deployment, credential, or external authentication is part of this path.

v3 uses a fresh claim, staging prefix, final directory, success/failure receipt,
and manifest. Any first mismatch consumes v3, removes partial staging, publishes
no partial final set, forbids automatic retry, and requires another versioned
recovery decision. Before success publication, all 38 retained files must be
reopened without following links and independently rehashed; the manifest is
written last.

After acquisition success, a separate byte-bound checker must reopen the
published 38-file inventory and independently recompute raw SHA-256, ZIP H1,
`.mod` H1, optional embedded-mod parity, modes, link counts, and stable
identities. Runner self-checks do not qualify. That readback is network-free and
may write only its owner-only receipt and last-written manifest.
The stated counts 41 after acquisition and 43 after readback mean the exact
reserved regular-file path set, not a recursive directory-entry total.

## Current authority

This decision authorizes only implementation of the separate v3 runner,
checker, mutation tests, and preparation of a byte-bound v3 execution permit.
It does not authorize network acquisition. The later permit must bind the exact
decision, runner, checker, tests, and all immutable predecessor evidence before
it can authorize one bounded execution.

No repository-owner proof, private key, token, password, signature, or user
action is required for this personal-project workflow.
