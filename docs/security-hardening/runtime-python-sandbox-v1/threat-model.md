# Runtime Python Sandbox v1 Threat Model

## Scope

This threat model covers a future macOS runtime-host tool that evaluates bounded
Python for deterministic calculations after explicit host-local approval. The
current product has no Python runner, action registration, active protocol
message, bundled interpreter, or execution authorization.

## Assets

- Runtime identity keys, trusted-device state, transport bindings, and pairing
  material.
- User files, approved documents and memory, chat history, model prompts and
  responses, and backend credentials.
- Runtime availability, CPU, memory, storage, file descriptors, and process
  capacity.
- Integrity of approval decisions, action-policy revisions, audit events, and
  published results.
- Integrity and provenance of the Python interpreter and every bundled native
  component.

## Trust Boundaries

1. A paired client and model-produced source are untrusted request inputs.
2. The runtime host validates authority and owns approval, policy, and audit.
3. XPC is a bounded IPC boundary, not permission to pass host objects or file
   capabilities.
4. The separately signed XPC service has an independent minimum-privilege App
   Sandbox and no shared secrets or broad entitlements.
5. The one-shot XPC worker and its embedded interpreter are hostile after source
   execution.
6. Returned stdout, stderr, structured results, exit status, and resource
   measurements are untrusted values.

## Adversaries

- A compromised or malicious paired client submits source, input, replay, and
  cancellation races.
- A model or prompt injection produces code intended to access files, network,
  credentials, processes, clipboard, automation, Keychain, or runtime memory.
- Source intentionally consumes CPU, memory, stack, descriptors, output,
  storage, or process slots.
- Source exploits CPython, a native extension, the IPC parser, or the worker
  wrapper to escape containment.
- A local attacker tampers with the interpreter artifact, helper bundle,
  environment, writable helper state, or code-signing identity.
- Malicious output attempts log injection, terminal control, parser confusion,
  oversized values, or secret exfiltration.

## Required Invariants

- No untrusted Python executes in the runtime host process.
- App Sandbox and code-signing identity form the primary containment boundary;
  syntax filtering, Python audit hooks, isolated mode, and resource limits are
  layered controls only.
- The helper has no network, DNS, App Group, shared Keychain, user-selected file,
  clipboard, automation, camera, microphone, location, or broad hardware
  entitlement.
- The helper receives no security-scoped bookmark, open host file descriptor,
  credential, backend handle, model object, runtime store handle, or arbitrary
  path.
- The one-shot XPC process contains an exact signed embedded CPython artifact,
  accepts one operation, launches no interpreter child, and exits. Python has
  zero child-process authority; writable state is untrusted, reset, and verified
  before any later operation.
- App Sandbox is not treated as an executable-identity allowlist. Native
  compromise and same-process `exec` remain residual risk; any replacement image
  must retain the same sandbox, resource ceilings, and bounded untrusted-result
  authority.
- The interpreter starts with a pinned equivalent of `-I -S -B` before parsing
  untrusted source. This is defense in depth, not OS containment.
- Every resource has an enforceable byte, count, time, or concurrency ceiling.
  Missing or ineffective enforcement blocks execution.
- Approval expiry and the three-second worker execution deadline are separate.
  Normal handoff, startup, execution, and result parsing use that budget. Forced
  termination, drain, XPC invalidation, reap, and scratch cleanup use a separate
  one-second monotonic budget; breach blocks the Python lane without publication.
- Approval binds authenticated authority plus the exact source, input, profile,
  execution closure, worker executable, designated requirement, entitlements,
  interpreter, and limits before durable execution reservation.
- Source with bidi controls, default-ignorable code points, or non-ASCII line
  separators is rejected before digest and token-aware escaped display.
- Approval binds the expected execution closure before durable reservation.
  After reservation starts the worker, the host verifies the XPC audit token and
  exact worker code identity before untrusted request handoff and again before
  accepting a result. Cancellation or authority, policy, execution-closure, or
  worker-identity drift invalidates the connection, terminates only that exact
  audit-token-bound worker instance, and suppresses late output. Ambient
  process-group termination is forbidden.
- Python has one bounded execution lane with explicit fairness and cannot
  silently reuse or starve the existing model-pull execution lane.
- Restart never retries reserved or outcome-unknown work.
- Terminal audit commits after process reap and cleanup but before publication;
  audit storage never contains source, input, output, paths, environment, or
  credentials.
- Successful terminal audit binds the result-schema revision, canonical result
  digest, exact publication-envelope digest, execution-closure digest, and
  worker-identity digest before sending that envelope.
- Worker output is parsed as closed bounded data and never interpreted as host
  code, terminal control, log metadata, a path, or a capability.

## Abuse And Failure Cases

- Import, introspection, native-extension, serialization, environment, path,
  symlink, descriptor, IPC, and process-spawn escapes.
- Infinite loops, recursive or compiler stack exhaustion, huge integers,
  decompression bombs, output floods, fork bombs, core dumps, and mmap pressure.
- Time-of-check/time-of-use changes to trust, authentication, action policy,
  profile revision, execution closure, interpreter digest, entitlements, limits,
  XPC audit token, or worker identity.
- XPC service reuse after compromise, incomplete writable-state cleanup, stale
  result publication, double execution, double terminal events, and ambiguous
  worker termination.
- Sandbox entitlement drift that accidentally adds network, user-file, App
  Group, Keychain, automation, or device authority.
- Interpreter update or rollback that changes import behavior, resource usage,
  parser semantics, or the restricted language surface without a new revision.

## Residual Risk And Out Of Scope

OS sandbox and interpreter vulnerabilities remain possible. A successful
kernel, App Sandbox, XPC, code-signing, CPython, or native-library escape can
invalidate containment. Side channels such as CPU timing and resource pressure
cannot be eliminated completely. Static no-device review does not demonstrate
real entitlements, process ancestry, limit effectiveness, cleanup, crash
behavior, or escape resistance.

File-backed data analysis, workspace access, packages, native extensions,
network requests, terminal commands, persistent notebooks, scheduled execution,
MCP, web search, and mobile approval are separate capabilities and are not
authorized by this design.
