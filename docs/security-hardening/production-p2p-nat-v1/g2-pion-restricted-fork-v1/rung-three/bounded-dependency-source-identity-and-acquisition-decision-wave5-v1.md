# G2 Pion rung-three Wave 5 identity and acquisition decision

Status: the exact 15-tuple Wave 5 frontier is identity-complete and acquisition-ready, but acquisition is not authorized.

The checker derives all evidence from the 66 held external `go.mod` files and 67 held ZIP archives. Two identical scans found 20 parent declarations, 20 module-ZIP H1 witnesses, and 22 `go.mod` H1 witnesses. Every tuple has one conflict-free H1 pair; all fifteen version-specific graph vertices are retained even though every `selectedByGraphAlgorithm` value is false.

This decision defines a future 30-request contract in tuple order (`.mod`, then `.zip`) and reserves the `.wave-5-v1.claim`, `.wave-5-v1-staging-*`, and `wave-5-v1/accepted` namespaces. `golang.org/x/sys` v0.17.0 and v0.20.0 remain distinct tuple identities and produce distinct request paths even though their held `go.mod` H1 is shared. A separate one-use permit, checker, runner, tests, execution receipt, manifest, and independent byte readback are still required.

No network request, authentication, source acquisition, extraction, source loading or execution, compilation, filesystem write, Git write, candidate selection, library selection, fixed-point claim, rung-three completion, or release claim is authorized or performed here. No account, owner proof, SSH/GPG proof, password, private key, signature, token, or user action is required.
