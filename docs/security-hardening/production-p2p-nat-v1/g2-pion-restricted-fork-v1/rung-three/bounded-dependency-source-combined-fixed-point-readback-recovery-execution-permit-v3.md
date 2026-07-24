# Combined fixed-point recovery execution permit v3

This permit authorizes exactly one formal offline replacement recovery
readback. The recorder must durably create and owner-only reopen its v3 claim
before any fresh archive-member open or decode in the formal attempt.

It does not authorize retry, resume, backfill, original evaluation, network
use, source execution, extraction, subprocesses, Git, devices, deployment,
authentication, credentials, signatures, or user action. Receipt publication
attempt begins before its exclusive write; no failure may be backfilled after
that point. The manifest is written last.
