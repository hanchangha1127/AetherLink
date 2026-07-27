# Wave11 bounded dependency-source acquisition permit v1

This document explains the machine-checked, one-use Wave11 acquisition permit.
The canonical authority record is the adjacent JSON file.

## Canonical direct invocation and local guards

- The canonical direct command is
  `["/Applications/Xcode.app/Contents/Developer/usr/bin/python3", "-I", "-B", "-S", "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave11_v1_once.py", "--execute"]`
  with the current working directory equal to the repository root. This is the
  documented operating shape, not an exclusive or origin-attested command.
- The interpreter path, isolated startup flags, runner path, and exact runner
  argument vector `["--execute"]` are independently bound in the canonical
  JSON. Argument abbreviation, duplicate `--execute`, omitted `--execute`,
  and every additional argument make the unmodified runner fail closed before
  preflight, claim creation, or network activity. These checks guard accidental
  local misconfiguration; they do not authenticate invocation origin.
- The production `main()` accepts no argument-vector override. Pure argument
  validation is tested separately and cannot dispatch execution. Both
  production `main()` and the first statement of `execute()` independently
  verify the resolved interpreter identity, repository-root working directory,
  and exact `sys.argv` as operating-shape checks.
- The execution gate also reads process arguments from macOS
  `sysctl(KERN_PROCARGS2)` under a strict size, argc, UTF-8, and NUL-parsing
  contract. The kernel executable and argv must exactly equal
  `["/Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.9/Resources/Python.app/Contents/MacOS/Python", "-I", "-B", "-S", "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave11_v1_once.py", "--execute"]`.
  An ordinary `runpy`, `-c`, or wrapper-script mismatch is rejected, but this
  observation does not authenticate the launcher against code already
  executing inside the same process.
- This personal-project model trusts local same-user code that can already
  access the repository, claim namespace, and permitted network operation.
  Same-process wrappers are inside that trust boundary. No invocation-origin
  attestation or external launcher receipt is provided or required.

## Scope

- The permit covers exactly 18 public `GET` requests to
  `https://proxy.golang.org:443`: one `.mod` and one `.zip` resource for each
  of the 9 identity-complete Wave11 module/version vertices, in exact bound
  tuple order with `.mod` immediately before `.zip`.
- Request order, paths, expected Go `h1:` values, response limits, accepted
  filenames, and the output namespace are fixed by the canonical JSON.
- Module paths and versions use the decision's lowercase-ASCII direct-proxy
  form. Pseudo-versions and multiple bound versions of one module remain
  distinct identities; this permit does not perform minimum-version selection
  or collapse them.
- Every Wave11 tuple and request carries
  `selectedByGraphAlgorithm: false`. That flag is a bound graph fact, not
  acquisition, publication, release, or product authority. A false selector
  does not drop any tuple; the permit covers all 18 exact resources.
- The claim must be created with exclusive owner-only access and made durable
  before DNS, TCP, TLS, or HTTPS begins. The claim is never removed, and the
  permit cannot be retried, resumed, backfilled, or overwritten.
- Claim creation records an attempted/may-have-consumed state before entering
  the exclusive create. A definitive no-create result clears that attempt
  state: `E_CLAIM_NOT_CREATED` remains failed-closed, while `E_CONSUMED`
  remains the known already-consumed state. Any `BaseException` after
  successful `O_EXCL` creation, including signal-mask restoration, fails
  closed as `E_CLAIM_STATE_UNCERTAIN`; interruption after a durable claim
  returns but before its held entry is assigned is also treated as possibly
  consumed. If `FileExistsError` was already observed, a simultaneous unmask
  interruption, including an acquisition-level deadline error, cannot erase
  that fact: the result remains `E_CONSUMED/already_consumed`. This known
  consumed state remains recorded independently through namespace and
  authority teardown. A teardown or process-state restoration failure changes
  the combined result to consumed terminal uncertainty, while an ordinary
  `E_CONSUMED` without another failure remains exact.
- Execution opens the project root once, traverses every dependency and
  documentation directory component relative to held parent descriptors with
  `O_DIRECTORY|O_NOFOLLOW`, and retains every intermediate descriptor and
  initial identity through termination. Each barrier compares the held child
  with the same name under its held parent; mutable writes use only the final
  held descriptors. SIGALRM and SIGINT are deferred only for the minimal local
  `open`-to-owned-FD transfer and final owner-FD cleanup. Cleanup finishes every
  independent close and clears the held namespace before restoring the prior
  signal mask. Network work, resource inspection, validation, writes, and
  `fsync` remain outside those narrow local exceptions.
- `existingClaimState: already_consumed` defines how any pre-existing claim is
  interpreted at execution time. The separate
  `claimAbsentAtPermitPublication: true` field records only the bounded
  observation that the claim path was absent when this permit was published.
- Every accepted response is checked against its bound `h1:` value. Module ZIP
  files are also checked for their exact module/version prefix, safe names,
  structural consistency, CRCs, bounded expansion, and `.mod` parity.
- The 18-resource portfolio retains conservative fixed aggregate response
  caps: 8 MiB across all `.mod` bodies, 128 MiB across all ZIP bodies, and
  128 MiB across all responses. These are portfolio-wide ceilings in addition
  to the 1 MiB per-`.mod` and 16 MiB per-ZIP limits.
- SIGALRM remains deliverable throughout every fetch, validation, write, and
  `fsync`. The caller is rejected before preflight if it already blocks
  SIGALRM. The pinned fetch primitive receives the 30-second per-request
  deadline, and the process guard supplies the 600-second whole-attempt alarm.
- An immutable single-assignment phase ledger records dispatch boundaries and
  committed response bytes, validations, and durable resource persistence.
  Failure counts are committed lower bounds, not claims of exact completion.
  A failure also records the current resource ordinal, one of
  `fetch_may_have_completed`, `validation_may_have_completed`, or
  `persist_may_have_completed`, and `additionalCompletionUncertain`. Zero
  committed responses with an active fetch is
  `sourceAcquisitionState: unknown_after_dispatch`; it is never represented as
  a definitive “not acquired” result. Success requires no active operation and
  exactly 18 committed dispatch, response, validation, and persistence
  boundaries.
- Process-global handler, timer, umask, and signal-mask setup and teardown are
  guarded separately from resource operations. Teardown attempts timer
  cancellation and synchronously consumes any installed pending SIGALRM before
  restoring the prior handler. The prior timer is armed with elapsed adjustment
  only after that handler restoration succeeds. If pending-alarm inspection or
  consumption fails, the runner handler remains installed, SIGALRM remains
  blocked, and the unsafe prior alarm state is not restored. Umask and other
  safe restoration steps are still attempted independently. Any process-state
  restoration failure after a claim or possible terminal result is reported as
  `E_PROCESS_STATE_RESTORE_UNCERTAIN` with
  `consumed_terminal_state_uncertain`; a body or namespace-teardown failure
  after a possible terminal result is reported as
  `E_CONSUMED_TERMINAL_STATE_UNCERTAIN` with the same status. Neither can be
  reported as ordinary `failed_closed`.
- Production fetches remain reachable only through the pinned
  `Wave11 -> Wave4` wrapper. Individual, aggregate `.mod`, aggregate ZIP,
  aggregate total, and ZIP inventory limits fail closed before a resource can
  be counted as validated or persisted.
- The live predecessor binding is the exact V9 checker and V9 tests package.
  V8 tests appear only as historical metadata and are not a live-held input to
  this permit.
- Successful publication is atomic and no-replace. The acquisition manifest is
  written last. Independent local byte readback remains mandatory afterward.

## Authentication boundary

This personal-project acquisition requires no account login, owner proof, SSH
or GPG key, password, private key, signature, token, cookie, client
certificate, authorization header, external launcher receipt,
invocation-origin attestation, or user interaction. The endpoint is the public
Go module proxy and ordinary TLS certificate/hostname validation is the only
remote identity check.

## Explicit non-authority

The permit does not authorize source extraction, source loading or execution,
package-manager execution, compilation, product runtime networking, device
work, deployment, Git operations, or release/product publication. Its narrow
filesystem authority does authorize only the claim, owner-only staging,
verified acquisition outputs, receipt-or-failure, manifest-last record, and
atomic no-replace publication of those acquisition artifacts; every other
repository write remains unauthorized. It does not establish dependency
fixed-point closure, semantic closure, library selection, rung-three completion,
or V1 release readiness.
