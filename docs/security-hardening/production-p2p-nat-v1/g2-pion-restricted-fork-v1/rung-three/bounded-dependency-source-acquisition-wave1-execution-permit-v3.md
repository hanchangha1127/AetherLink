# G2 Pion dependency wave-one execution permit v3

This reader accompanies
`g2-pion-ice-v4.3.0-rung3-dependency-wave1-execution-permit-v3`.
Its status is
`wave1_v3_dependency_source_acquisition_authorized_not_consumed`, its result is
`exact_19_public_proxy_mod_then_zip_pairs_v3_authorized_once_not_executed`,
and its single next action is `execute_bound_dependency_source_wave1_v3_once`.

No account login, ownership proof, private key, token, password, signature, or
user action is involved. Product pairing and endpoint authentication remain a
separate runtime concern and are unchanged.

The v1 and v2 claims and failure receipts remain immutable terminal evidence.
Neither prior permit may be reused or retried, and no prior response or staging
artifact may be resumed. V3 uses a fresh claim, staging prefix, final directory,
success receipt, failure receipt, and manifest namespace.

The one-use runner may issue exactly 38 sequential unauthenticated HTTPS GET
requests to `proxy.golang.org`: the exact `.mod` response followed by the exact
`.zip` response for each of the 19 source-decision tuples. Redirects, ambient
proxies, cookies, credentials, client certificates, range or resume requests,
automatic retries, and alternate mirrors are forbidden.

Each `.mod` response is bounded to 1 MiB and must be valid UTF-8 without NUL
bytes, contain exactly the expected module directive, and match the pinned
`goModH1`. Each ZIP is bounded to 16 MiB, must pass the complete structural and
path checks, and must match the pinned `moduleZipH1`. A ZIP need not contain a
root `go.mod`; when one is present, its bytes must exactly match the separately
acquired `.mod` response.

The aggregate retained response bound is 136 MiB, with separate 8 MiB `.mod`
and 128 MiB ZIP ceilings. The runner also retains the entry, central-directory,
single-file, decompression, path, JSON, 30-second per-request, and 600-second
whole-wave limits selected by recovery decision v2.

The one-use claim is durably created before the first request and persists
after any request attempt. A tuple-local failure records only a bounded reason,
the tuple identity and order, the failing resource kind, and safe numeric
counters. It removes partial staging, publishes no partial final set, and
disables automatic retry. Any error after final-directory publication is
terminally uncertain and also disables retry.

Success requires all six counters to equal their exact terminal values:
38 request attempts, 38 completed response bodies, 38 validated resources,
19 validated `.mod` files, 19 validated ZIPs, and 19 validated tuples. The
runner reopens, reparses, and rehashes all 38 resources before atomic
publication, then writes the success receipt followed by the manifest last.

The acquisition publication reserves exactly 41 regular-file paths: one claim,
38 resources, one success receipt, and one manifest. Independent readback adds
exactly two more paths for a 43-path post-readback set. These counts describe
the exact reserved regular-file path sets, not recursive directory counts.

Runner self-checks are not independent readback. After a successful
acquisition, the separate v3 readback checker must reopen all 38 resources,
recompute raw SHA-256, `moduleZipH1`, and `goModH1`, recheck optional embedded
`go.mod` parity and the exact inventory, then write its receipt and manifest
last without network access or source extraction.

The permit is content-bound to the recovery decision, both retained terminal
generations, the v3 runner and its 45 tests, this reader contract's exact
bytes, the strict permit checker and its 39 tests, and the independent readback
checker and its 34 tests. It authorizes only this bounded dependency-source
intake and its evidence writes. Package management, compilation,
acquired-source loading or execution, runtime or product networking, devices,
deployment, and Git writes remain outside scope.
