# G2 Pion dependency wave-one execution permit v1

This document explains
`g2-pion-ice-v4.3.0-rung3-dependency-wave1-execution-permit-v1`.
The machine-readable permit is authoritative. Its current state is
`wave1_dependency_source_acquisition_authorized_not_consumed`, its result is
`exact_19_public_proxy_zip_requests_authorized_once_not_executed`, and its next
action is `execute_bound_dependency_source_wave1_once`.

## Personal-project boundary

이 저장소는 개인 단독 소유 프로젝트다. 이 실행 허가를 준비하거나 검사하거나
소비하는 데 사용자 인증, 저장소 소유자 증명, 외부 계정 로그인, 개인 키, 토큰,
암호, 서명을 요구하지 않는다. 이 경계는 제품 내부의 기기 pairing authentication
및 secure-session 검증을 제거하거나 약화하지 않는다.

## Exact authority

The permit opens one narrow source-intake operation:

- exactly 19 sequential `GET` requests;
- exactly the 19 `.zip` URLs already frozen in the predecessor decision;
- HTTPS to `proxy.golang.org` on port 443 only;
- system trust-store TLS and hostname validation;
- no redirect, retry, range, resume, mirror, ambient proxy, credential,
  authentication header, cookie, client certificate, query, fragment, or
  user-info override; and
- the embedded ZIP `go.mod` entry is the only go.mod byte source. No `.mod` or
  `.info` endpoint is authorized.

The runner streams each response into a new owner-only file. It validates ZIP
structure and exact EOF, matching central/local headers and data descriptors,
the absence of ZIP64 in both header locations, CRC while reading every entry,
path and compression bounds, a fail-closed DOS-or-Unix creator-system policy,
file kind, module prefix, module H1, embedded
`go.mod` H1, raw byte identity, and the ordered 19-source digest. A shrinking
socket timeout plus one underlying buffered `read1` operation per loop limits
each body-read operation. A separately scoped Darwin `SIGALRM`/`setitimer`
watchdog covers the entire `opener.open` plus header and body operation, so the
per-request bound is a hard wall-clock deadline rather than an inactivity-only
timeout. The same whole-wave deadline separately arms the watchdog around every
ZIP inspection and the final pre-publication re-hash/fsync barrier, followed by
an immediate deadline check before the exclusive rename.

`wholeWaveDeadlineMilliseconds` therefore bounds source-response intake, ZIP
validation, and pre-publication integrity verification. It does not claim to
time-bound the atomic rename, post-publication revalidation, or receipt and
manifest writes. The runner refuses an occupied process timer or a non-default
alarm handler, and requires the process main thread, before any claim or network
attempt.
It performs no source extraction, source loading, source execution,
package-manager operation, Go command, Git command, shell, subprocess, compiler
invocation, product/runtime networking, device work, deployment, release
action, or Git write.

## One-use and filesystem state

The claim is created with directory-relative no-follow `O_EXCL`, mode `0600`,
and file-plus-parent fsync. Once any network attempt begins, the claim remains
and retry is forbidden. New staging and final directories are `0700`; new
files are `0600`. Existing repository ancestors need only be owned by the
current user and not group- or world-writable. The unexpected-sibling rule is
limited to the reserved staging prefix and final directory contents.

The permit checker returns the validated repository-root device, inode, owner,
and mode. Before any claim or staging write, the runner opens the root again
and requires its held descriptor to have that exact identity. All 19 downloaded
archives' verified descriptors remain open through final-directory
publication. Immediately before and after the exclusive rename, the runner
requires the exact 19-name inventory, re-hashes every held descriptor against
its recorded raw size and SHA-256, and repeats descriptor/name identity and
stable-state checks. The temporary and final directory entries must match the
held inode, owner, mode, size, modification time, and expected link count.

The final 19-file directory is published with Darwin
`renameatx_np(RENAME_EXCL)` relative to the already-held source and destination
parent descriptors, so an existing final directory is never replaced and path
ancestors are not re-resolved. Both parent directories are fsynced after the
cross-parent rename. The success receipt is written after final-set publication
and the manifest is created last. The result remains
`acquired_pending_independent_readback`; runner self-checking is not independent
readback.

The default preflight uses the checker-returned root identity and no-follow
directory descriptors to inspect the one-use state without writing. A claim,
reserved staging entry, accepted final directory, success receipt, failure
receipt, or manifest prevents another execute-next result. A coherent complete
publication reports `consumed_pending_independent_readback`; every partial or
conflicting state reports `blocked_one_use_state_present` and requires a new
versioned recovery decision.

## Crash boundary

Final-directory publication and the documentation receipt/manifest live in
different directories and cannot form one filesystem transaction. A crash or
write failure after the final directory is published is therefore classified
as `POST_PUBLISH_UNCERTAIN` and the durable state is
`consumed_terminal_state_uncertain`.

Unexpected exceptions after publication are normalized to that same bounded
state without printing raw exception text or absolute paths. Unexpected
pre-publication exceptions are likewise reduced to the bounded `E_INTERNAL`
failure code.

That state is neither success nor ordinary failure. The runner must not create
both success and failure receipts, retry automatically, issue another network
request, delete or rewrite the published set, or claim completion. Its only
next step is a new versioned recovery decision.

## What this does not establish

The permit is not execution evidence. The 19 root requirements are not the
complete dependency graph or a fixed point. Direct dependency SumDB inclusion,
repository ownership, source/license/security review, SBOM closure, dependency
closure, semantic closure, finding closure, candidate selection, library
selection, production networking, and release readiness remain unestablished.

Any later independent readback is a point-in-time verification of the accepted
bytes and manifest. It is not a permanent immutability guarantee. The local
one-use claim also does not claim protection against a hostile process running
as the same user.
