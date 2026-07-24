# G2 Pion dependency wave2 preclaim recovery decision v1

The first wave2 v1 command stopped before claim creation, network access, or
artifact publication. The permit checker returned repository identity keys
`device`, `inode`, `uid`, and `mode`, while the retained legacy filesystem
primitive required `ownerUid` instead of `uid`. The runner forwarded the
producer object unchanged, and the readback checker contained the same latent
incompatibility.

Wave2 v1 is frozen and must not be rerun or backfilled. Its missing claim,
failure receipt, accepted directory, success receipt, manifest, and readback
artifacts remain absent. An owner-only revocation sentinel occupies the exact
legacy `.wave-2-v1-staging-*` prefix, so the frozen v1 checker and runner now
fail their clean-namespace gate with `E_NAMESPACE_STAGING`. The sentinel is a
revocation lock, not a claim, failure receipt, success artifact, or consumed
network attempt, and v2 authority readers retain its exact bytes through their
final barriers.

The selected recovery is a fresh wave2 v2 namespace. It reuses the exact 15
tuple identities, 30 ordered public proxy requests, and held H1 expectations,
but uses `.wave-2-v2.claim`, `.wave-2-v2-staging-*`,
`wave-2-v2/accepted`, and v2 receipt and manifest paths. One exact adapter must
translate the checker schema to the legacy schema, reject missing, extra,
boolean, UID, or mode drift, and be exercised by both the runner and readback.
A read-only compatibility gate must open and close the actual repository root
through that adapter before a separate v2 execution permit may authorize
network intake.

Because the original decision embeds `wave-2-v1/accepted` in every resource
path, v2 independently projects only that path prefix to
`wave-2-v2/accepted` and binds a distinct ordered resource-set digest. URLs,
H1 expectations, resource order, and all other resource fields remain exact.

No repository login, owner proof, credential, private key, signature, token,
password, or user action is required. Product endpoint authentication remains
a separate runtime invariant.
