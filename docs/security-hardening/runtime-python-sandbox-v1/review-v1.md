# Runtime Python Sandbox Review v1

## Status

`runtime_python_sandbox_v1_recommended` is `proposed_not_selected`. This packet
is ready for a design-selection decision, but it authorizes no source
acquisition, executable target, Python artifact, action registration, protocol
message, process, XPC service, file access, network access, or code execution.

## Recommendation

Use a separately signed, minimum-privilege, one-shot XPC worker with its own App
Sandbox. The XPC process itself accepts exactly one approved operation, contains
a pinned signed embedded CPython artifact loaded before untrusted source, and
then exits. It does not launch a separate interpreter process, and Python has
zero child-process authority. The worker has no network, App Group, shared
Keychain, user-selected-file, or automation authority. Writable helper state is
attacker-controlled after a run and must be reset and verified before the next
run.

App Sandbox is not an executable-identity allowlist. The design therefore does
not claim that a native compromise cannot replace the current process image.
Such an `exec` remains residual risk and must be tested to retain the same App
Sandbox, resource ceilings, and bounded untrusted-result authority. It cannot be
treated as an approved interpreter or language-profile path.

The first language surface should be the versioned
`deterministic_calculation_v1` restricted profile. Static syntax and builtin
allowlists are defense in depth inside the OS sandbox, not a substitute for it.
The interpreter starts with a pinned equivalent of Python `-I -S -B` before any
untrusted source is parsed. Those flags, resource limits, and audit hooks remain
defense in depth rather than the containment boundary.

## Rejected Options

### In-Process Subinterpreter

Rejected because it shares the runtime host process, address space, file
descriptors, native extensions, and crash domain. Interpreter isolation is not
OS privilege separation and cannot protect the runtime host from malicious or
resource-exhausting code.

### Plain Process With System Python

Rejected because `Process` alone does not create an independently restricted
App Sandbox, and a host-installed interpreter, environment, import path, and
site packages are not a pinned execution artifact. Python `-I -S -B` reduces
ambient language configuration, site initialization, and bytecode writes but
does not remove OS file, network, process, or user-data authority.

### Sandboxed XPC Service With Bundled Python

Recommended for selection, subject to the unresolved packaging, code-signing,
entitlement, interpreter supply-chain, language-profile, resource-portability,
and adversarial escape evidence in `review-v1.json`. The one-shot worker must
receive only bounded IPC values and never receive runtime credentials, model
backend handles, security-scoped bookmarks, user files, or host file
descriptors. Worker stdin is closed.

## Approval, Cancellation, And Audit Boundary

Every operation requires macOS-host-local approval over the exact action and
policy revision, authenticated authority, language profile, execution-closure
digest, worker executable digest, designated-requirement digest, entitlement
digest, interpreter digest, source digest, input digest, and resource-limit
digest. The exact source is
ephemeral host-review data and never durable audit data. Source containing bidi
controls, default-ignorable code points, or non-ASCII line separators is rejected
before digest and display. The viewer uses line numbers, visible whitespace, and
token-aware Unicode escapes bound to the exact digest. Remote self-approval and
standing grants remain forbidden.

The existing `RuntimeHostApprovalCoordinator` supplies useful approval-state
invariants but cannot be reused unchanged. Python needs an action-specific claim
instead of the model-pull digest, a separate bounded execution lane, a closed
terminal outcome taxonomy, and a cancellation handle. Approval expiry remains
separate from the three-second worker execution deadline. Forced termination has
a separate one-second monotonic cleanup deadline, including the 250 ms grace,
exact XPC connection invalidation, audit-token-bound worker termination, pipe
drain, reap, and scratch cleanup. It never uses an ambient process-group target.
A cleanup
deadline breach records `cleanup_failed`, blocks the Python lane, and never
publishes output.

A Python-specific adapter and persistence design must preserve durable
reservation before worker start, terminal audit before result publication, no
retry after restart, authority-drift termination, and storage-degraded fail
closure. Durable audit contains digests and stable event codes, never source,
input, structured result, stdout, stderr, paths, environment, or credentials. A
success audit binds the result-schema revision, canonical result digest, and
exact publication-envelope digest before that envelope can publish. stdout and
stderr are bounded host diagnostics only and are not client results.

The approval binds the expected execution closure before durable reservation.
After reservation starts the worker, the host verifies the XPC audit token and
exact worker code identity before handing off any untrusted request, binds that
worker instance to the reservation, and rechecks identity before accepting any
result. Identity or closure drift terminates only that exact worker and
suppresses publication. The durable audit records execution-closure and
worker-identity digests.

## Selection Effect

Approving this recommendation would select the review requirements only. It
would not authorize downloading or bundling Python, adding an executable or XPC
target, registering `python_deterministic_calculation_v1`, activating the
proposed `python.run` message, running code, granting file/network/process
authority, or claiming sandbox effectiveness. Each requires the versioned
follow-up artifacts and evidence listed in the packet. `python.exec` is not a
second proposed message.

## Evidence Boundary

The evidence manifest describes the current source boundary: one model-pull
action, an internal action-neutral lifecycle, no Python runner target, and no
active `python.*` protocol message. Static validation cannot prove App Sandbox
containment, resource-limit effectiveness, code-signing behavior, interpreter
supply-chain integrity, cancellation under real execution, or resistance to a
sandbox escape.
