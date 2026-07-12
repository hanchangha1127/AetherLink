# Production P2P/NAT V1 Pre-Network Approval Decision V1

## Immutable Approval

The user explicitly approved all seven recommended options in
`production_p2p_nat_v1_pre_network_review_v1` for profile
`production_p2p_nat_v1_recommended`. This closed decision records
`explicit_user_instruction` as the approval source and resolves each decision to
the review's exact `recommendedOptionId`. It does not alter or reopen the source
review, `selection-decision.json`, or `handoff-v2`.

## Resolutions

1. `service-ownership-and-trust`: `first-party-tls13-signed-service-config`
2. `pair-authorization-and-retention`: `opaque-generation-scoped-capabilities`
3. `candidate-privacy-and-scope`: `e2e-limited-direct`
4. `ice-and-consent-policy`: `full-ice-regular-nomination-runtime-initiator`
5. `turn-credential-and-abuse-policy`: `short-lived-pair-scoped-turn`
6. `session-transition-semantics`: `between-request-cutover-fail-inflight`
7. `release-budgets`: `measured-matrix-with-hard-stop-budgets`

## Authorization Boundary

This approval authorizes creation of `handoff-v3` only. It does not authorize
network I/O, socket execution for `controlled-network-spike`, selection of a
networking or session-cryptography library, production deployment, or claims of
measured performance. The proposal remains unmeasured. The next step is a
separate review of the networking library and isolated harness before any socket
execution.

## Source Records

- Review: `review-v1.json`
- Source handoff: `../implementation/handoff-v2.json`

Both source records remain closed and immutable.
