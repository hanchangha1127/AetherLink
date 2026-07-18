# P2P/NAT implementation handoff v7

## Authorized work

This handoff carries the explicit user approval into one-shot acquisition and read-only inspection of the official libnice 0.1.23 release archive and detached signature. The exact URLs, destinations, and size limits are locked in `decision-v4.json` and `handoff-v7.json`.

The candidate remains not selected. The handoff authorizes evidence collection for a later compile-eligibility decision, not implementation or production use.

## Dependency gate

The user's approval includes the minimum required GLib-family source closure. Dependency acquisition remains disabled until the pinned libnice build metadata yields exact minimum versions and a new versioned decision and handoff lock the official dependency URLs. Any dependency outside that scope requires explicit scope expansion.

## Execution boundary

Read-only source inspection, safe archive extraction, hashing, and manifest generation are allowed. Compiler, static-library archiver, build system, configure, source, and test execution are forbidden. Source forks, sockets, runtime or harness networking, controlled-spike socket execution, Phase B, and production are forbidden.

The next handoff may be created only after a completed libnice intake and a read-only dependency-closure record. It cannot open compile, socket, runtime, Phase B, or production authority.
