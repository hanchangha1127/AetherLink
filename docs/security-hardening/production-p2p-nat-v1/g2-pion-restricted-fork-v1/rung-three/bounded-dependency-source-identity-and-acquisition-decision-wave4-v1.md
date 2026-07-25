# G2 Pion rung-three Wave 4 identity and acquisition decision

Status: the exact 16-tuple Wave 4 frontier is identity-complete and acquisition-ready, but acquisition is not authorized.

The checker derives all evidence from the 50 held external `go.mod` files and 51 held ZIP archives. Two identical scans found 22 parent declarations, 24 module-ZIP H1 witnesses, and 26 `go.mod` H1 witnesses. Every tuple has one conflict-free H1 pair; the three graph-selected and thirteen version-specific non-selected vertices are all retained.

This decision defines a future 32-request contract in tuple order (`.mod`, then `.zip`) and reserves the `.wave-4-v1.claim`, `.wave-4-v1-staging-*`, and `wave-4-v1/accepted` namespaces. A separate one-use permit, checker, runner, tests, execution receipt, manifest, and independent byte readback are still required.

No network request, authentication, source acquisition, extraction, source loading or execution, compilation, filesystem write, Git write, candidate selection, library selection, fixed-point claim, rung-three completion, or release claim is authorized or performed here. No account, owner proof, SSH/GPG proof, password, private key, signature, token, or user action is required.
