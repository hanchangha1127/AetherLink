# Bounded dependency source identity and acquisition decision Wave3 v1

This decision records the exact 16-tuple frontier reproduced from the frozen
69-source Wave1/Wave2 input set. Four tuples are graph-selected and twelve are
version-specific non-selected vertices; none may be dropped, replaced by a
higher version, or rejected.

The held evidence provides all 16 `go.mod` H1 identities and 15 module ZIP H1
identities. `github.com/kr/pty@v1.1.1` has the exact held `go.mod` H1
`h1:pFQYn66WHrOpPYNljwOMqo10TkYh1fy3cYio2l3bCsQ=` but no held ZIP H1.
Therefore Wave3 is not acquisition-ready and this document is not an execution
permit.

No dependency request, SumDB lookup, network access, file mutation, source
loading or execution, archive extraction, compilation, package-manager use,
subprocess, Git operation, device action, deployment, authentication,
credential, key, token, password, signature, or user action is authorized.
The only next action is to prepare a separate authentication-free public
checksum identity-resolution decision for the missing ZIP identity.
