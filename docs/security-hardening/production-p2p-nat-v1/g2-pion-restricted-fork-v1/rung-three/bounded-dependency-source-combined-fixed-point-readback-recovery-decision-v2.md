# Combined fixed-point readback recovery decision v2

Status: **recovery selected; execution not authorized**.

The consumed evaluation succeeded and its exact claim, result, and manifest
are preserved. The result is not a fixed point: its graph has sixteen new
tuples. The original readback check produced an `E_NAMESPACE` diagnostic
because the original permit context invokes the preparation decision's
clean-future-namespace computation even when terminal-aware checking was
requested. That CLI diagnostic records the observed failure only; it is not
accepted as terminal or semantic evidence.

This decision selects a versioned recovery design. It validates the original
decision and permit through their pure expected-payload paths, binds every
original tool and all 69 held source inputs, and binds the successful terminal
byte-for-byte. It does not modify, delete, retry, resume, backfill, execute, or
record anything.

A separate v2 recovery readback checker, tests, and one-use execution permit
must be prepared and independently reviewed. Until then, readback recording,
network use, source execution, filesystem extraction, subprocesses, Git
writes, authentication, signatures, private keys, tokens, passwords, and user
action remain unauthorized.
