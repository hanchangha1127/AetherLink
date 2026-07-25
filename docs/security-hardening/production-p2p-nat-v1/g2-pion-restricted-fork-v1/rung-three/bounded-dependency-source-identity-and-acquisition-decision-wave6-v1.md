# G2 Pion rung-three Wave 6 identity and acquisition decision

Status: the exact 18-tuple Wave 6 frontier is identity-complete and acquisition-ready, but acquisition is not authorized.

The checker derives all evidence twice from 81 held external `go.mod` files and 82 held ZIP archives. Both scans found 18 parent declarations, 18 module-ZIP H1 witnesses, and 25 `go.mod` H1 witnesses. Every tuple has one conflict-free H1 pair; all eighteen version-specific graph vertices remain distinct and every `selectedByGraphAlgorithm` value is false.

Validation accounting keeps the graph lineage separate: the predecessor v3 graph reconstruction opened 236 archives, the current v4 graph reconstruction opened 164, and the complete v4 graph lineage opened 400. Two Wave 6 identity-witness scans opened another 164 archives, so the overall decision execution opened 564 archives. Reconstruction counts remain independently stated as 4 predecessor plus 2 current, totaling 6.

This decision defines a future 36-request contract in exact combined-v4 frontier order (`.mod`, then `.zip`) and reserves the `.wave-6-v1.claim`, `.wave-6-v1-staging-*`, and `wave-6-v1/accepted` namespaces. A separate one-use permit, checker, runner, tests, execution receipt, manifest, and independent byte readback are still required.

The semantic validator independently requires the exact reader binding, ordered checker/test bindings, raw hashes from the already-held tool bytes, and the complete ordered non-claim set. The 22 authority values must each be the JSON boolean `false`; numeric zero is not accepted as an equivalent value. Request and operation-counter integers are likewise type-strict.

No network request, authentication, source acquisition, extraction, source loading or execution, compilation, filesystem write, Git write, candidate selection, library selection, fixed-point claim, rung-three completion, or release claim is authorized or performed here. No account, owner proof, SSH/GPG proof, password, private key, signature, token, or user action is required.
